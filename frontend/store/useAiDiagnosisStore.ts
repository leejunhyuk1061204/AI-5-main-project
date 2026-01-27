import { create } from 'zustand';
import { getDiagnosisSessionStatus, replyToDiagnosisSession, diagnoseObdOnly } from '../api/aiApi';

export type DiagMode = 'IDLE' | 'PROCESSING' | 'REPLY_PROCESSING' | 'INTERACTIVE' | 'REPORT' | 'ACTION_REQUIRED';

interface AiDiagnosisState {
    // Data State
    currentSessionId: string | null;
    selectedVehicleId: string | null;
    status: DiagMode;
    messages: any[];
    diagResult: any | null;
    requestedAction: string | null;
    loadingMessage: string;
    isWaitingForAi: boolean;

    // Actions
    setVehicleId: (id: string) => void;
    startDiagnosis: (vehicleId: string) => Promise<string | null>;
    sendReply: (reply: string) => Promise<void>;
    updateStatus: (sessionId: string) => Promise<void>;
    setMessages: (messages: any[]) => void;
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

    setVehicleId: (id) => set({ selectedVehicleId: id }),

    startDiagnosis: async (vehicleId) => {
        set({ status: 'PROCESSING', loadingMessage: 'OBD 스캔을 시작합니다...', messages: [], diagResult: null, requestedAction: null });
        try {
            const response = await diagnoseObdOnly(vehicleId);
            const sessionId = response?.data?.sessionId || response?.sessionId;
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

    updateStatus: async (sessionId) => {
        try {
            const statusData = await getDiagnosisSessionStatus(sessionId);
            if (!statusData) return;

            console.log("[useAiDiagnosisStore] Polling Status:", statusData.status, "Action:", statusData.requestedAction);

            // 메시지 동기화
            let newMessages = statusData.messages || [];
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

            if (currentStatus === 'INTERACTIVE' || currentStatus === 'ACTION_REQUIRED' || currentStatus === 'REPLY_PROCESSING') {
                mode = currentStatus as DiagMode;
            } else if (['REPORT', 'DONE', 'COMPLETED', 'SUCCESS'].includes(currentStatus)) {
                mode = 'REPORT';
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

    reset: () => set({
        currentSessionId: null,
        status: 'IDLE',
        messages: [],
        diagResult: null,
        requestedAction: null,
        isWaitingForAi: false,
        loadingMessage: '차량 진단 중...'
    })
}));
