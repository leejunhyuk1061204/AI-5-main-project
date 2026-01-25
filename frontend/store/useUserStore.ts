import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authService } from '../services/auth';
import { getVehicleList } from '../api/vehicleApi';
import { useVehicleStore } from './useVehicleStore';

/**
 * 사용자 정보 및 인증 상태를 관리하는 Store
 */
interface UserState {
    nickname: string | null;
    email: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;

    // Actions
    setUser: (nickname: string | null, email?: string | null) => Promise<void>;
    login: (nickname: string, email: string) => Promise<void>;
    logout: () => Promise<void>;
    loadUser: () => Promise<void>;

    // Composite Actions (API + Logic)
    loginAction: (email: string, pw: string) => Promise<{ success: boolean; hasVehicle?: boolean; errorMessage?: string }>;
    socialLoginAction: (provider: string, token: string) => Promise<{ success: boolean; hasVehicle?: boolean; errorMessage?: string }>;
}

export const useUserStore = create<UserState>((set) => ({
    nickname: null,
    email: null,
    isAuthenticated: false,
    isLoading: true,

    setUser: async (nickname, email = null) => {
        set({ nickname, email, isAuthenticated: !!nickname });
        if (nickname) {
            await AsyncStorage.setItem('userNickname', nickname);
            if (email) await AsyncStorage.setItem('userEmail', email);
        } else {
            await AsyncStorage.removeItem('userNickname');
            await AsyncStorage.removeItem('userEmail');
        }
    },

    login: async (nickname, email) => {
        set({ nickname, email, isAuthenticated: true });
        await AsyncStorage.setItem('userNickname', nickname);
        await AsyncStorage.setItem('userEmail', email);
    },

    logout: async () => {
        set({ nickname: null, email: null, isAuthenticated: false });
        await AsyncStorage.removeItem('userNickname');
        await AsyncStorage.removeItem('userEmail');
        await AsyncStorage.removeItem('accessToken');
        await AsyncStorage.removeItem('refreshToken');
    },

    loadUser: async () => {
        set({ isLoading: true });
        try {
            const nickname = await AsyncStorage.getItem('userNickname');
            const email = await AsyncStorage.getItem('userEmail');
            if (nickname) {
                set({ nickname, email, isAuthenticated: true });
            }
        } catch (e) {
            console.error('Failed to load user info', e);
        } finally {
            set({ isLoading: false });
        }
    },

    loginAction: async (email, password) => {
        try {
            const response = await authService.login({ email, password });
            if (response.success && response.data) {
                return await handleLoginSuccess(response.data, set);
            } else {
                return { success: false, errorMessage: response.error?.message || "이메일 또는 비밀번호를 확인해주세요." };
            }
        } catch (error: any) {
            const errorMsg = error.response?.data?.error?.message || "서버 연결에 실패했습니다.";
            return { success: false, errorMessage: errorMsg };
        }
    },

    socialLoginAction: async (provider, token) => {
        try {
            const response = await authService.socialLogin(provider, token);
            if (response.success && response.data) {
                return await handleLoginSuccess(response.data, set);
            } else {
                return { success: false, errorMessage: response.error?.message || "소셜 로그인에 실패했습니다." };
            }
        } catch (error: any) {
            console.error("Social Login Error", error);
            return { success: false, errorMessage: "소셜 로그인 중 오류가 발생했습니다." };
        }
    }
}));

// Helper function to handle common login success logic
const handleLoginSuccess = async (data: any, set: any) => {
    try {
        // 1. Store Token
        await AsyncStorage.setItem('accessToken', data.accessToken);
        if (data.refreshToken) {
            await AsyncStorage.setItem('refreshToken', data.refreshToken);
        }

        // 2. Fetch Profile & Update Store
        const profileResponse = await authService.getProfile(data.accessToken);
        if (profileResponse.success && profileResponse.data) {
            const { nickname, email } = profileResponse.data;
            set({ nickname, email, isAuthenticated: true });
            await AsyncStorage.setItem('userNickname', nickname);
            await AsyncStorage.setItem('userEmail', email);
        }

        // 3. Check Vehicles
        const vehicles = await getVehicleList();
        useVehicleStore.getState().setVehicles(vehicles); // Store update
        const hasVehicle = vehicles && vehicles.length > 0;

        return { success: true, hasVehicle };
    } catch (e) {
        console.error("Login Post-Process Error", e);
        return { success: true, hasVehicle: false }; // 로그인 자체는 성공으로 처리 (화면 이동 등은 호출 측에서 결정)
    }
};

