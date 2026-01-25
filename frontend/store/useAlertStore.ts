import { create } from 'zustand';

interface AlertState {
    visible: boolean;
    title: string;
    message: string;
    type: 'SUCCESS' | 'ERROR' | 'INFO' | 'WARNING';
    onConfirm?: () => void;

    showAlert: (title: string, message: string, type?: AlertState['type'], onConfirm?: () => void) => void;
    hideAlert: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
    visible: false,
    title: '',
    message: '',
    type: 'INFO',
    onConfirm: undefined,

    showAlert: (title, message, type = 'INFO', onConfirm) => set({
        visible: true,
        title,
        message,
        type,
        onConfirm
    }),

    hideAlert: () => set({ visible: false, onConfirm: undefined })
}));
