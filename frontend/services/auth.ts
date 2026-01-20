import api from '../api/axios';

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

    updateProfile: async (token: string, nickname?: string, password?: string): Promise<ApiResponse<string>> => {
        const payload: any = {};
        if (nickname) payload.nickname = nickname;
        if (password) payload.password = password;

        const response = await api.patch<ApiResponse<string>>('/api/v1/auth/me', payload);
        return response.data;
    },

    deleteAccount: async (token: string): Promise<ApiResponse<string>> => {
        const response = await api.delete<ApiResponse<string>>('/api/v1/auth/me');
        return response.data;
    }
};
