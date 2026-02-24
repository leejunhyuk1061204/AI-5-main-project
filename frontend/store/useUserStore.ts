import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authService } from '../services/auth';
import { getVehicleList } from '../api/vehicleApi';
import { useVehicleStore } from './useVehicleStore';
import fcmService from '../services/fcmService';

/**
 * 사용자 정보 및 인증 상태를 관리하는 Store
 */
interface UserState {
    nickname: string | null;
    email: string | null;
    membership: string | null;
    membershipExpiry: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;

    // Actions
    setUser: (nickname: string | null, email?: string | null, membership?: string | null, membershipExpiry?: string | null) => Promise<void>;
    login: (nickname: string, email: string, membership: string, membershipExpiry: string | null) => Promise<void>;
    logout: () => Promise<void>;
    loadUser: () => Promise<void>;

    // Composite Actions (API + Logic)
    loginAction: (email: string, pw: string) => Promise<{ success: boolean; hasVehicle?: boolean; errorMessage?: string }>;
    socialLoginAction: (provider: string, token: string) => Promise<{ success: boolean; hasVehicle?: boolean; errorMessage?: string }>;
}

export const useUserStore = create<UserState>((set) => ({
    nickname: null,
    email: null,
    membership: null,
    membershipExpiry: null,
    isAuthenticated: false,
    isLoading: true,

    setUser: async (nickname, email = null, membership = null, membershipExpiry = null) => {
        set({ nickname, email, membership, membershipExpiry, isAuthenticated: !!nickname });
        if (nickname) {
            await AsyncStorage.setItem('userNickname', nickname);
            if (email) await AsyncStorage.setItem('userEmail', email);
            if (membership) await AsyncStorage.setItem('userMembership', membership);
            if (membershipExpiry) await AsyncStorage.setItem('userMembershipExpiry', membershipExpiry);
        } else {
            await AsyncStorage.removeItem('userNickname');
            await AsyncStorage.removeItem('userEmail');
            await AsyncStorage.removeItem('userMembership');
            await AsyncStorage.removeItem('userMembershipExpiry');
        }
    },

    login: async (nickname, email, membership, membershipExpiry) => {
        set({ nickname, email, membership, membershipExpiry, isAuthenticated: true });
        await AsyncStorage.setItem('userNickname', nickname);
        await AsyncStorage.setItem('userEmail', email);
        await AsyncStorage.setItem('userMembership', membership);
        if (membershipExpiry) await AsyncStorage.setItem('userMembershipExpiry', membershipExpiry);
    },

    logout: async () => {
        // 1. 사용자 정보 초기화
        set({ nickname: null, email: null, isAuthenticated: false });

        // 2. AsyncStorage 토큰 삭제
        await AsyncStorage.removeItem('userNickname');
        await AsyncStorage.removeItem('userEmail');
        await AsyncStorage.removeItem('userMembership');
        await AsyncStorage.removeItem('userMembershipExpiry');
        await AsyncStorage.removeItem('accessToken');
        await AsyncStorage.removeItem('refreshToken');

        // 3. OBD 연결/폴링 종료 및 모든 Store 초기화
        try {
            const { useVehicleStore } = await import('./useVehicleStore');
            const { useAiDiagnosisStore } = await import('./useAiDiagnosisStore');
            const { useBleStore } = await import('./useBleStore');
            const { useAlertStore } = await import('./useAlertStore');
            const { useRegistrationStore } = await import('./useRegistrationStore');
            const ObdService = (await import('../services/ObdService')).default;
            const BackgroundService = (await import('../services/BackgroundService')).default;

            // 폴링/백그라운드 업로드/BT 연결 정리
            await ObdService.disconnect();
            await BackgroundService.stop();

            await useVehicleStore.getState().reset();
            useAiDiagnosisStore.getState().reset();
            useBleStore.getState().reset();
            useAlertStore.getState().reset();
            useRegistrationStore.getState().reset();

            console.log('[Logout] All stores have been reset.');
        } catch (error) {
            console.error('[Logout] Failed to reset some stores:', error);
        }

        // 4. FCM 토큰 삭제
        try {
            await fcmService.deleteToken();
            console.log('[Logout] FCM token deleted.');
        } catch (error) {
            console.error('[Logout] Failed to delete FCM token:', error);
        }
    },

    loadUser: async () => {
        set({ isLoading: true });
        try {
            // 1. First, load from local storage to show UI quickly
            const nickname = await AsyncStorage.getItem('userNickname');
            const email = await AsyncStorage.getItem('userEmail');
            const membership = await AsyncStorage.getItem('userMembership');
            const membershipExpiry = await AsyncStorage.getItem('userMembershipExpiry');
            const accessToken = await AsyncStorage.getItem('accessToken');

            if (nickname) {
                set({ nickname, email, membership, membershipExpiry, isAuthenticated: true });
            }

            // 2. Then, fetch latest profile from server to sync (especially membership)
            if (accessToken) {
                const profileResponse = await authService.getProfile();
                if (profileResponse.success && profileResponse.data) {
                    const data = profileResponse.data;
                    set({
                        nickname: data.nickname,
                        email: data.email,
                        membership: data.membership,
                        membershipExpiry: data.membershipExpiry ? data.membershipExpiry.toString() : null,
                        isAuthenticated: true
                    });

                    // Sync storage
                    await AsyncStorage.setItem('userNickname', data.nickname);
                    await AsyncStorage.setItem('userEmail', data.email);
                    await AsyncStorage.setItem('userMembership', data.membership);
                    if (data.membershipExpiry) {
                        await AsyncStorage.setItem('userMembershipExpiry', data.membershipExpiry.toString());
                    }
                }
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
                // 200 OK but success: false
                return { success: false, errorMessage: response.error?.message || "이메일 또는 비밀번호를 확인해주세요." };
            }
        } catch (error) {
            const friendlyMsg = resolveErrorMessage(error as Error | Record<string, unknown>);
            return { success: false, errorMessage: friendlyMsg };
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
        } catch (error) {
            console.error("Social Login Error", error);
            const friendlyMsg = resolveErrorMessage(error as Error | Record<string, unknown>);
            return { success: false, errorMessage: friendlyMsg };
        }
    }
}));

// Helper function to handle common login success logic
const handleLoginSuccess = async (data: import('../services/auth').TokenResponse, set: (state: Partial<UserState> | ((state: UserState) => Partial<UserState>)) => void) => {
    try {
        // 1. Store Token
        console.log('[Auth] Access Token Issued:', data.accessToken);
        await AsyncStorage.setItem('accessToken', data.accessToken);
        if (data.refreshToken) {
            console.log('[Auth] Refresh Token Issued:', data.refreshToken);
            await AsyncStorage.setItem('refreshToken', data.refreshToken);
        }

        // 2. Fetch Profile & Update Store (axios uses token from AsyncStorage set above)
        const profileResponse = await authService.getProfile(data.accessToken);
        if (profileResponse.success && profileResponse.data) {
            const { nickname, email, membership, membershipExpiry } = profileResponse.data;
            set({ nickname, email, membership, membershipExpiry, isAuthenticated: true });
            await AsyncStorage.setItem('userNickname', nickname);
            await AsyncStorage.setItem('userEmail', email);
            await AsyncStorage.setItem('userMembership', membership || 'FREE');
            if (membershipExpiry) await AsyncStorage.setItem('userMembershipExpiry', membershipExpiry.toString());
        }

        // 3. Load vehicles only after token is stored and profile is synced (avoids 401 on vehicle API)
        const vehicles = await getVehicleList();
        useVehicleStore.getState().setVehicles(vehicles); // Store update
        const hasVehicle = vehicles && vehicles.length > 0;

        // 4. FCM 토큰 등록
        try {
            await fcmService.initialize();
            console.log('[Auth] FCM initialized on login');
        } catch (e) {
            console.error('[Auth] FCM initialization failed:', e);
        }

        return { success: true, hasVehicle };
    } catch (e) {
        console.error("Login Post-Process Error", e);
        return { success: true, hasVehicle: false }; // 로그인 자체는 성공으로 처리 (화면 이동 등은 호출 측에서 결정)
    }
};

/**
 * 에러 객체를 분석하여 사용자 친화적인 메시지를 반환합니다.
 */
const resolveErrorMessage = (error: Error | Record<string, any>): string => {
    if (!error) return "알 수 없는 오류가 발생했습니다.";

    // 1. Axios Response Error
    if ('response' in error && error.response) {
        const response = error.response as any;
        const status = response.status;
        const serverMsg = response.data?.error?.message;

        switch (status) {
            case 400:
                // Bad Request - 서버에서 주는 메시지가 있으면 그것을 우선 사용, 없으면 기본 메시지
                return serverMsg || "입력 정보를 확인해주세요.";
            case 401:
                return "이메일 또는 비밀번호가 일치하지 않습니다.";
            case 403:
                return "접근 권한이 없습니다.";
            case 404:
                return "가입되지 않은 계정입니다. 회원가입을 진행해주세요.";
            case 409:
                return "이미 가입된 계정입니다.";
            case 500:
            case 502:
            case 503:
                return "서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.";
            default:
                return serverMsg || `오류가 발생했습니다. (${status})`;
        }
    }

    // 2. Network Error (Timeout, No connection)
    const errorCode = (error as any).code;
    if (errorCode === 'ECONNABORTED' || error.message?.includes('Network Error')) {
        return "네트워크 연결이 원활하지 않습니다. 인터넷 연결을 확인해주세요.";
    }

    // 3. Other
    return error.message || "로그인 중 알 수 없는 오류가 발생했습니다.";
};

