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
    grantType: string;
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

    getProfile: async (token: string): Promise<ApiResponse<UserResponse>> => {
        const response = await api.get<ApiResponse<UserResponse>>('/api/v1/auth/me', {
            headers: { Authorization: `Bearer ${token}` }
        });
        return response.data;
    }
};
