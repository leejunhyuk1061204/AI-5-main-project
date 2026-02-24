import AsyncStorage from '@react-native-async-storage/async-storage';
import EventSource from 'react-native-sse';
import { create } from 'zustand';
import { BASE_URL } from '../api/axios';
import { getDiagnosisSessionStatus, replyToDiagnosisSession, diagnoseObdOnly, AiDiagnosisResponse, DiagnosisMessage } from '../api/aiApi';

export type DiagType = 'OBD' | 'SOUND' | 'PHOTO';

export type DiagMode = 'IDLE' | 'PROCESSING' | 'REPLY_PROCESSING' | 'INTERACTIVE' | 'REPORT' | 'ACTION_REQUIRED';

// 개별 세션 정보
export interface DiagSessionState {
    currentSessionId: string | null;
    status: DiagMode;
    messages: DiagnosisMessage[];
    diagResult: AiDiagnosisResponse | null;
    requestedAction: AiDiagnosisResponse['requestedAction'] | null;
    loadingMessage: string;
    isWaitingForAi: boolean;

    sseProgress: number;
    sseStatusMessage: string;
    sseSessionId: string | null;
    sseFailedWithMessage: string | null;
}

const initialSessionState: DiagSessionState = {
    currentSessionId: null,
    status: 'IDLE',
    messages: [],
    diagResult: null,
    requestedAction: null,
    loadingMessage: '차량 진단 중...',
    isWaitingForAi: false,

    sseProgress: 0,
    sseStatusMessage: '서버 연결 대기 중...',
    sseSessionId: null,
    sseFailedWithMessage: null,
};

let sseInstances: Record<DiagType, EventSource | null> = {
    'OBD': null,
    'SOUND': null,
    'PHOTO': null,
};

interface AiDiagnosisState {
    selectedVehicleId: string | null;
    sessions: Record<DiagType, DiagSessionState>;

    // Actions
    setVehicleId: (id: string | null) => void;
    startDiagnosis: (type: DiagType, vehicleId: string, apiCall: () => Promise<any>) => Promise<string | null>;
    sendReply: (type: DiagType, reply: string) => Promise<void>;
    updateStatus: (type: DiagType, sessionId: string, cachedData?: AiDiagnosisResponse) => Promise<void>;
    setMessages: (type: DiagType, messages: DiagnosisMessage[]) => void;
    connectSse: (type: DiagType, sessionId: string) => Promise<void>;
    disconnectSse: (type: DiagType) => void;
    clearSseFailed: (type: DiagType) => void;
    reset: (type?: DiagType) => void;
}

export const useAiDiagnosisStore = create<AiDiagnosisState>((set, get) => ({
    selectedVehicleId: null,
    sessions: {
        'OBD': { ...initialSessionState },
        'SOUND': { ...initialSessionState },
        'PHOTO': { ...initialSessionState },
    },

    setVehicleId: (id) => set({ selectedVehicleId: id }),

    startDiagnosis: async (type, vehicleId, apiCall) => {
        set((state) => ({
            sessions: {
                ...state.sessions,
                [type]: {
                    ...initialSessionState,
                    status: 'PROCESSING',
                    loadingMessage: '진단을 준비하고 있습니다...'
                }
            }
        }));

        try {
            // Caller provides the specific API call (diagnoseObdOnly vs diagnoseMulti)
            const response = await apiCall();
            const sessionId = response?.sessionId;
            if (sessionId) {
                set((state) => ({
                    selectedVehicleId: vehicleId,
                    sessions: {
                        ...state.sessions,
                        [type]: {
                            ...state.sessions[type],
                            currentSessionId: sessionId
                        }
                    }
                }));
                return sessionId;
            }
            throw new Error("Session ID not found");
        } catch (error) {
            console.error(`Start ${type} Diagnosis Error:`, error);
            set((state) => ({
                sessions: {
                    ...state.sessions,
                    [type]: { ...state.sessions[type], status: 'IDLE' }
                }
            }));
            return null;
        }
    },

    sendReply: async (type, reply) => {
        const session = get().sessions[type];
        const { selectedVehicleId } = get();
        if (!session.currentSessionId || !selectedVehicleId) return;

        set((state) => ({
            sessions: {
                ...state.sessions,
                [type]: {
                    ...state.sessions[type],
                    messages: [...state.sessions[type].messages, { role: 'user', content: reply }],
                    isWaitingForAi: true,
                    status: 'REPLY_PROCESSING',
                    requestedAction: null
                }
            }
        }));

        try {
            await replyToDiagnosisSession(session.currentSessionId, {
                vehicleId: selectedVehicleId,
                userResponse: reply
            });
        } catch (error) {
            console.error(`Send Reply Error (${type}):`, error);
            set((state) => ({
                sessions: {
                    ...state.sessions,
                    [type]: {
                        ...state.sessions[type],
                        isWaitingForAi: false,
                        status: 'ACTION_REQUIRED'
                    }
                }
            }));
        }
    },

    updateStatus: async (type, sessionId, cachedData) => {
        try {
            const statusData = cachedData ?? await getDiagnosisSessionStatus(sessionId);
            if (!statusData) return;

            let newMessages = statusData.interactiveData?.conversation || [];
            if (statusData.interactiveData) {
                const combined = [...(statusData.interactiveData.conversation || [])];
                if (statusData.interactiveData.message) {
                    const last = combined[combined.length - 1];
                    if (!last || last.content !== statusData.interactiveData.message) {
                        combined.push({ role: 'ai', content: statusData.interactiveData.message });
                    }
                }
                newMessages = combined;
            }

            const currentStatus = (statusData.status || '').toUpperCase();
            let mode: DiagMode = 'PROCESSING';

            if (currentStatus === 'FAILED' || currentStatus === 'ERROR') {
                set((state) => ({
                    sessions: {
                        ...state.sessions,
                        [type]: {
                            ...state.sessions[type],
                            messages: newMessages,
                            status: 'IDLE',
                            isWaitingForAi: false,
                            requestedAction: null,
                            diagResult: null,
                            loadingMessage: statusData.progressMessage || '진단이 실패했습니다. 다시 시도해 주세요.'
                        }
                    }
                }));
                return;
            }

            if (statusData.response_mode === 'REPORT' || statusData.responseMode === 'REPORT' || ['REPORT', 'DONE', 'COMPLETED', 'SUCCESS'].includes(currentStatus)) {
                mode = 'REPORT';
            } else if (currentStatus === 'INTERACTIVE' || currentStatus === 'ACTION_REQUIRED' || currentStatus === 'REPLY_PROCESSING') {
                mode = currentStatus as DiagMode;
            }

            set((state) => ({
                sessions: {
                    ...state.sessions,
                    [type]: {
                        ...state.sessions[type],
                        messages: newMessages,
                        status: mode,
                        isWaitingForAi: mode === 'PROCESSING' || mode === 'REPLY_PROCESSING',
                        requestedAction: statusData.requestedAction || null,
                        diagResult: mode === 'REPORT' ? (statusData.report || statusData.result || statusData) : null,
                        loadingMessage: statusData.progressMessage || '분석 중...'
                    }
                }
            }));

        } catch (error) {
            console.error(`Update Status Error (${type}):`, error);
            set((state) => ({
                sessions: {
                    ...state.sessions,
                    [type]: {
                        ...state.sessions[type],
                        status: 'IDLE',
                        isWaitingForAi: false
                    }
                }
            }));
        }
    },

    setMessages: (type, messages) => set((state) => ({
        sessions: {
            ...state.sessions,
            [type]: { ...state.sessions[type], messages }
        }
    })),

    connectSse: async (type, sessionId) => {
        console.log('[connectSse] called', { type, sessionId });
        const sessionStore = get().sessions[type];
        if (sseInstances[type] && sessionStore.sseSessionId === sessionId) {
            console.log('[connectSse] skip: already connected for same sessionId');
            return;
        }

        get().disconnectSse(type);

        const token = await AsyncStorage.getItem('accessToken');
        if (!token) {
            console.log('[connectSse] no token, abort');
            set((state) => ({
                sessions: {
                    ...state.sessions,
                    [type]: { ...state.sessions[type], sseStatusMessage: '인증 정보를 찾을 수 없습니다.' }
                }
            }));
            return;
        }

        set((state) => ({
            sessions: {
                ...state.sessions,
                [type]: {
                    ...state.sessions[type],
                    currentSessionId: sessionId,
                    sseSessionId: sessionId,
                    sseProgress: 0,
                    sseStatusMessage: '서버 연결 대기 중...'
                }
            }
        }));

        const url = `${BASE_URL}/api/v1/ai/diagnose/session/${sessionId}/sse`;
        console.log('[connectSse] EventSource open', { type, url });
        const es = new EventSource(url, {
            headers: { Authorization: `Bearer ${token}` },
            lineEndingCharacter: '\n',
            timeoutBeforeConnection: 0
        });
        sseInstances[type] = es;

        // helper logic to target specific slice with less boilerplate inside SSE events
        const updateSseState = (updates: Partial<DiagSessionState>) => {
            set((state) => ({
                sessions: { ...state.sessions, [type]: { ...state.sessions[type], ...updates } }
            }));
        };

        es.addEventListener('open' as any, () => {
            console.log('[connectSse] event: open', type);
            updateSseState({ sseStatusMessage: '서버 연결 성공 (진단 시작)', sseProgress: 0.1 });
        });
        es.addEventListener('step1' as any, () => { console.log('[connectSse] event: step1', type); updateSseState({ sseStatusMessage: '진단 요청 접수 완료', sseProgress: 0.2 }); });
        es.addEventListener('step2' as any, () => { console.log('[connectSse] event: step2', type); updateSseState({ sseStatusMessage: '멀티미디어 데이터 전처리 완료', sseProgress: 0.4 }); });
        es.addEventListener('step3' as any, () => { console.log('[connectSse] event: step3', type); updateSseState({ sseStatusMessage: 'AI 정밀 분석 완료 (시각/청각/OBD)', sseProgress: 0.6 }); });
        es.addEventListener('step4' as any, () => { console.log('[connectSse] event: step4', type); updateSseState({ sseStatusMessage: '결함 원인 추론 및 지식 검색 완료', sseProgress: 0.8 }); });

        es.addEventListener('failed' as any, (event: any) => {
            console.log('[connectSse] event: failed', type, event?.data);
            const message = (event?.data && String(event.data).trim()) || 'AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
            if (sseInstances[type] === es) {
                sseInstances[type]?.close();
                sseInstances[type] = null;
            }
            updateSseState({
                status: 'IDLE',
                currentSessionId: null,
                sseFailedWithMessage: message,
                sseProgress: 1,
                sseStatusMessage: message,
                sseSessionId: null
            });
        });

        es.addEventListener('step5' as any, async () => {
            console.log('[connectSse] event: step5', type);
            updateSseState({ sseStatusMessage: '최종 진단 완료 (결과 확인 중)', sseProgress: 1 });
            if (sseInstances[type] === es) {
                sseInstances[type]?.close();
                sseInstances[type] = null;
            }
            updateSseState({ sseSessionId: null });

            const sid = get().sessions[type].currentSessionId;
            if (!sid) return;
            try {
                const data = await getDiagnosisSessionStatus(sid);
                const currentStatus = (data?.status || '').toUpperCase();
                const responseMode = data?.responseMode || data?.response_mode || '';
                const isInteractive = currentStatus === 'ACTION_REQUIRED' || currentStatus === 'INTERACTIVE' || responseMode === 'INTERACTIVE';

                let newMessages = data?.interactiveData?.conversation || [];
                if (data?.interactiveData) {
                    const combined = [...(data.interactiveData.conversation || [])];
                    if (data.interactiveData.message) {
                        const last = combined[combined.length - 1];
                        if (!last || last.content !== data.interactiveData.message) {
                            combined.push({ role: 'ai', content: data.interactiveData.message });
                        }
                    }
                    newMessages = combined;
                }

                const mode: DiagMode = isInteractive ? (currentStatus as DiagMode) : 'REPORT';
                updateSseState({
                    status: mode,
                    isWaitingForAi: false,
                    messages: newMessages,
                    requestedAction: data?.requestedAction || null,
                    diagResult: mode === 'REPORT' ? (data?.report || data?.result || data) : null,
                    loadingMessage: data?.progressMessage || '분석 중...'
                });
            } catch (e) {
                updateSseState({ status: 'REPORT', isWaitingForAi: false, diagResult: null });
            }
        });

        es.addEventListener('error' as any, (e: any) => { console.log('[connectSse] event: error', type, e?.message || e); });
    },

    disconnectSse: (type) => {
        if (sseInstances[type]) {
            sseInstances[type]?.close();
            sseInstances[type] = null;
        }
        set((state) => ({
            sessions: {
                ...state.sessions,
                [type]: {
                    ...state.sessions[type],
                    sseSessionId: null,
                    sseProgress: 0,
                    sseStatusMessage: '서버 연결 대기 중...'
                }
            }
        }));
    },

    clearSseFailed: (type) => set((state) => ({
        sessions: { ...state.sessions, [type]: { ...state.sessions[type], sseFailedWithMessage: null } }
    })),

    // 명시적 리셋 - 특정 타입의 세션만 비우거나, 인자가 없으면 전체 초기화
    reset: (type) => {
        if (type) {
            get().disconnectSse(type);
            set((state) => ({
                sessions: {
                    ...state.sessions,
                    [type]: { ...initialSessionState }
                }
            }));
        } else {
            // 모든 세션에 대해 SSE 연결 종료 후 전체 초기화
            (['OBD', 'SOUND', 'PHOTO'] as DiagType[]).forEach((t) => get().disconnectSse(t));
            set(() => ({
                selectedVehicleId: null,
                sessions: {
                    'OBD': { ...initialSessionState },
                    'SOUND': { ...initialSessionState },
                    'PHOTO': { ...initialSessionState },
                }
            }));
        }
    }
}));

