import { create } from 'zustand';

export type ErrorType = 'ERROR' | 'WARNING' | 'INFO';

interface ErrorState {
    isVisible: boolean;
    title: string;
    message: string;
    type: ErrorType;
    onRetry?: () => void;
    showError: (title: string, message: string, type?: ErrorType, onRetry?: () => void) => void;
    hideError: () => void;
}

export const useErrorStore = create<ErrorState>((set) => ({
    isVisible: false,
    title: '',
    message: '',
    type: 'ERROR',
    onRetry: undefined,

    showError: (title, message, type = 'ERROR', onRetry) =>
        set({ isVisible: true, title, message, type, onRetry }),

    hideError: () =>
        set({ isVisible: false, onRetry: undefined }),
}));
