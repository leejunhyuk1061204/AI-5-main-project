import { create } from 'zustand';

interface UIState {
    isKeyboardVisible: boolean;
    bottomNavVisible: boolean;

    setKeyboardVisible: (visible: boolean) => void;
    setBottomNavVisible: (visible: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
    isKeyboardVisible: false,
    bottomNavVisible: true,

    setKeyboardVisible: (visible) => set({
        isKeyboardVisible: visible,
        // 키보드가 보이면 하단바는 무조건 숨기는 것이 기본 전략
        bottomNavVisible: !visible
    }),

    setBottomNavVisible: (visible) => set({ bottomNavVisible: visible })
}));
