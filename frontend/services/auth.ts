import AsyncStorage from '@react-native-async-storage/async-storage';
import api, { BASE_URL } from '../api/axios';

// DTO Interfaces based on Spec
export interface SignupRequest {
    email: string;
    password: string;
    nickname: string;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface TokenResponse {
    accessToken: string;
    refreshToken: string;
}

export interface UserResponse {
    id: string;
    email: string;
    nickname: string;
    role: string;
    membership: string;
    membershipExpiry: string | null;
}

export interface ApiResponse<T> {
    success: boolean;
    data: T | null;
    error: {
        code: string;
        message: string;
    } | null;
}

// Auth API Service
export const authService = {
    signup: async (data: SignupRequest): Promise<ApiResponse<UserResponse>> => {
        const response = await api.post<ApiResponse<UserResponse>>('/api/v1/auth/signup', data);
        return response.data;
    },

    login: async (data: LoginRequest): Promise<ApiResponse<TokenResponse>> => {
        const response = await api.post<ApiResponse<TokenResponse>>('/api/v1/auth/login', data);
        return response.data;
    },

    socialLogin: async (provider: string, token: string): Promise<ApiResponse<TokenResponse>> => {
        const response = await api.post<ApiResponse<TokenResponse>>('/api/v1/auth/social-login', { provider, token });
        return response.data;
    },

    getProfile: async (token?: string): Promise<ApiResponse<UserResponse>> => {
        const response = await api.get<ApiResponse<UserResponse>>('/api/v1/auth/me');
        return response.data;
    },

    updateProfile: async (nickname?: string, password?: string): Promise<ApiResponse<string>> => {
        const payload: { nickname?: string; password?: string } = {};
        if (nickname) payload.nickname = nickname;
        if (password) payload.password = password;

        const response = await api.patch<ApiResponse<string>>('/api/v1/auth/me', payload);
        return response.data;
    },

    // FCM 토큰 등록/업데이트
    updateFcmToken: async (fcmToken: string): Promise<ApiResponse<string>> => {
        const response = await api.patch<ApiResponse<string>>('/api/v1/auth/fcm-token', { fcmToken });
        return response.data;
    },

    deleteAccount: async (token: string): Promise<ApiResponse<string>> => {
        const response = await api.delete<ApiResponse<string>>('/api/v1/auth/me');
        return response.data;
    },

    /**
     * refreshToken으로 새 accessToken을 발급받아 저장한다.
     * 차량/프로필 등 인증 API 호출 전에 호출하면 만료된 토큰으로 인한 401을 방지할 수 있다.
     * @returns 새 accessToken 또는 실패 시 null
     */
    refreshAccessToken: async (): Promise<string | null> => {
        const refreshToken = await AsyncStorage.getItem('refreshToken');
        if (!refreshToken) return null;

        const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refreshToken }),
        });

        if (!response.ok) return null;

        const body = await response.json();
        const data = body?.data;
        if (!data?.accessToken) return null;

        await AsyncStorage.setItem('accessToken', data.accessToken);
        if (data.refreshToken) {
            await AsyncStorage.setItem('refreshToken', data.refreshToken);
        }
        return data.accessToken;
    },
};
