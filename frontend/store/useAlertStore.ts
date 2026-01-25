import { create } from 'zustand';

interface AlertState {
    visible: boolean;
    title: string;
    message: string;
    type: 'SUCCESS' | 'ERROR' | 'INFO' | 'WARNING';
    confirmText?: string;
    cancelText?: string;
    isDestructive?: boolean;
    onConfirm?: () => void;

    showAlert: (
        title: string,
        message: string,
        type?: AlertState['type'],
        onConfirm?: () => void,
        options?: {
            confirmText?: string;
            cancelText?: string;
            isDestructive?: boolean;
        }
    ) => void;
    hideAlert: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
    visible: false,
    title: '',
    message: '',
    type: 'INFO',
    confirmText: '확인',
    cancelText: '닫기',
    isDestructive: false,
    onConfirm: undefined,

    showAlert: (title, message, type = 'INFO', onConfirm, options) => set({
        visible: true,
        title,
        message,
        type,
        onConfirm,
        confirmText: options?.confirmText || '확인',
        cancelText: options?.cancelText || '닫기',
        isDestructive: options?.isDestructive || false,
    }),

    hideAlert: () => set({
        visible: false,
        onConfirm: undefined,
        confirmText: '확인',
        cancelText: '닫기',
        isDestructive: false
    })
}));
