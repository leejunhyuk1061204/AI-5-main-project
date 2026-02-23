import AsyncStorage from '@react-native-async-storage/async-storage';
import EventSource from 'react-native-sse';
import { create } from 'zustand';
import { BASE_URL } from '../api/axios';
import { getDiagnosisSessionStatus, replyToDiagnosisSession, diagnoseObdOnly, AiDiagnosisResponse, DiagnosisMessage } from '../api/aiApi';

export type DiagMode = 'IDLE' | 'PROCESSING' | 'REPLY_PROCESSING' | 'INTERACTIVE' | 'REPORT' | 'ACTION_REQUIRED';

let sseInstance: EventSource | null = null;

interface AiDiagnosisState {
    // Data State
    currentSessionId: string | null;
    selectedVehicleId: string | null;
    status: DiagMode;
    messages: DiagnosisMessage[];
    diagResult: AiDiagnosisResponse | null;
    requestedAction: AiDiagnosisResponse['requestedAction'] | null;
    loadingMessage: string;
    isWaitingForAi: boolean;

    // SSE state (persists across ObdDiagLoading mount/unmount)
    sseProgress: number;
    sseStatusMessage: string;
    sseSessionId: string | null;
    sseFailedWithMessage: string | null;

    // Actions
    setVehicleId: (id: string | null) => void;
    startDiagnosis: (vehicleId: string) => Promise<string | null>;
    sendReply: (reply: string) => Promise<void>;
    updateStatus: (sessionId: string, cachedData?: AiDiagnosisResponse) => Promise<void>;
    setMessages: (messages: DiagnosisMessage[]) => void;
    connectSse: (sessionId: string) => Promise<void>;
    disconnectSse: () => void;
    clearSseFailed: () => void;
    reset: () => void;
}

export const useAiDiagnosisStore = create<AiDiagnosisState>((set, get) => ({
    currentSessionId: null,
    selectedVehicleId: null,
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

    setVehicleId: (id) => set({ selectedVehicleId: id }),

    startDiagnosis: async (vehicleId) => {
        set({ status: 'PROCESSING', loadingMessage: 'OBD 스캔을 시작합니다...', messages: [], diagResult: null, requestedAction: null });
        try {
            const response = await diagnoseObdOnly(vehicleId);
            const sessionId = response?.sessionId;
            if (sessionId) {
                set({ currentSessionId: sessionId, selectedVehicleId: vehicleId });
                return sessionId;
            }
            throw new Error("Session ID not found");
        } catch (error) {
            console.error("Start Diagnosis Error:", error);
            set({ status: 'IDLE' });
            return null;
        }
    },

    sendReply: async (reply) => {
        const { currentSessionId, selectedVehicleId } = get();
        if (!currentSessionId || !selectedVehicleId) return;

        // 즉각적인 UI 반영
        set(state => ({
            messages: [...state.messages, { role: 'user', content: reply }],
            isWaitingForAi: true,
            status: 'REPLY_PROCESSING', // Explicitly switch to processing mode
            requestedAction: null // 답변을 보냈으므로 요청된 액션 초기화
        }));

        try {
            await replyToDiagnosisSession(currentSessionId, {
                vehicleId: selectedVehicleId,
                userResponse: reply
            });
            // 이후 updateStatus 폴링에서 결과를 처리함
        } catch (error) {
            console.error("Send Reply Error:", error);
            set({ isWaitingForAi: false, status: 'ACTION_REQUIRED' });
        }
    },

    updateStatus: async (sessionId, cachedData) => {
        try {
            const statusData = cachedData ?? await getDiagnosisSessionStatus(sessionId);
            if (!statusData) return;

            if (!cachedData) {
                console.log("[useAiDiagnosisStore] Polling Status:", statusData.status, "Action:", statusData.requestedAction);
            }

            // 메시지 동기화
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

            // FAILED 상태 처리 (폴링 즉시 중지)
            if (currentStatus === 'FAILED' || currentStatus === 'ERROR') {
                set({
                    messages: newMessages,
                    status: 'IDLE',
                    isWaitingForAi: false,
                    requestedAction: null,
                    diagResult: null,
                    loadingMessage: statusData.progressMessage || '진단이 실패했습니다. 다시 시도해 주세요.'
                });
                return;
            }

            if (statusData.response_mode === 'REPORT' || statusData.responseMode === 'REPORT' || ['REPORT', 'DONE', 'COMPLETED', 'SUCCESS'].includes(currentStatus)) {
                mode = 'REPORT';
            } else if (currentStatus === 'INTERACTIVE' || currentStatus === 'ACTION_REQUIRED' || currentStatus === 'REPLY_PROCESSING') {
                mode = currentStatus as DiagMode;
            }

            set({
                messages: newMessages,
                status: mode,
                isWaitingForAi: mode === 'PROCESSING' || mode === 'REPLY_PROCESSING',
                requestedAction: statusData.requestedAction || null,
                diagResult: mode === 'REPORT' ? (statusData.report || statusData.result || statusData) : null,
                loadingMessage: statusData.progressMessage || '분석 중...'
            });

        } catch (error) {
            console.error("Update Status Error:", error);
            // 에러 발생 시 상태를 IDLE로 변경하여 무한 폴링 방지
            set({ status: 'IDLE', isWaitingForAi: false });
        }
    },

    setMessages: (messages) => set({ messages }),

    connectSse: async (sessionId) => {
        const { sseSessionId: connectedId } = get();
        if (sseInstance && connectedId === sessionId) return;

        get().disconnectSse();

        const token = await AsyncStorage.getItem('accessToken');
        if (!token) {
            set({ sseStatusMessage: '인증 정보를 찾을 수 없습니다.' });
            return;
        }

        set({ sseSessionId: sessionId, sseProgress: 0, sseStatusMessage: '서버 연결 대기 중...' });

        const url = `${BASE_URL}/api/v1/ai/diagnose/session/${sessionId}/sse`;
        const es = new EventSource(url, {
            headers: { Authorization: `Bearer ${token}` }
        });
        sseInstance = es;

        es.addEventListener('open' as any, () => {
            set({ sseStatusMessage: '서버 연결 성공 (진단 시작)', sseProgress: 0.1 });
        });
        es.addEventListener('step1' as any, () => set({ sseStatusMessage: '진단 요청 접수 완료', sseProgress: 0.2 }));
        es.addEventListener('step2' as any, () => set({ sseStatusMessage: '멀티미디어 데이터 전처리 완료', sseProgress: 0.4 }));
        es.addEventListener('step3' as any, () => set({ sseStatusMessage: 'AI 정밀 분석 완료 (시각/청각/OBD)', sseProgress: 0.6 }));
        es.addEventListener('step4' as any, () => set({ sseStatusMessage: '결함 원인 추론 및 지식 검색 완료', sseProgress: 0.8 }));

        es.addEventListener('failed' as any, (event: any) => {
            const message = (event?.data && String(event.data).trim()) || 'AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
            if (sseInstance === es) {
                sseInstance.close();
                sseInstance = null;
            }
            set({
                status: 'IDLE',
                currentSessionId: null,
                sseFailedWithMessage: message,
                sseProgress: 1,
                sseStatusMessage: message,
                sseSessionId: null
            });
        });

        es.addEventListener('step5' as any, async () => {
            set({ sseStatusMessage: '최종 진단 완료 (결과 확인 중)', sseProgress: 1 });
            if (sseInstance === es) {
                sseInstance.close();
                sseInstance = null;
            }
            set({ sseSessionId: null });

            const { currentSessionId: sid } = get();
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
                const reportData = data?.report || data?.result || data;
                set({
                    status: mode,
                    isWaitingForAi: false,
                    messages: newMessages,
                    requestedAction: data?.requestedAction || null,
                    diagResult: mode === 'REPORT' ? reportData : null,
                    loadingMessage: data?.progressMessage || '분석 중...'
                });
            } catch (e) {
                set({ status: 'REPORT', isWaitingForAi: false, diagResult: null });
            }
        });

        es.addEventListener('error' as any, () => {});
    },

    disconnectSse: () => {
        if (sseInstance) {
            sseInstance.close();
            sseInstance = null;
        }
        set({ sseSessionId: null, sseProgress: 0, sseStatusMessage: '서버 연결 대기 중...' });
    },

    clearSseFailed: () => set({ sseFailedWithMessage: null }),

    reset: () => {
        get().disconnectSse();
        set({
            currentSessionId: null,
            status: 'IDLE',
            messages: [],
            diagResult: null,
            requestedAction: null,
            isWaitingForAi: false,
            loadingMessage: '차량 진단 중...',
            sseFailedWithMessage: null
        });
    }
}));
