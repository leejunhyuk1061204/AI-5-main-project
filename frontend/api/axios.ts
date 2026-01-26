import axios from 'axios';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Dynamically determine the host IP from the Expo Go URI
const getBaseUrl = () => {
    // For physical device testing, hardcode the local IP
    return 'http://localhost:8080';
};

const BASE_URL = getBaseUrl();

export interface ApiResponse<T> {
    success: boolean;
    data: T;
    message: string | null;
}

// Create axios instance
const api = axios.create({
    baseURL: BASE_URL,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor
import AsyncStorage from '@react-native-async-storage/async-storage';

api.interceptors.request.use(
    async (config) => {
        try {
            const token = await AsyncStorage.getItem('accessToken');
            if (token && !config.headers.Authorization) {
                config.headers.Authorization = `Bearer ${token}`;
                console.log('Added Authorization header:', config.headers.Authorization);
            }
        } catch (error) {
            console.error('Error fetching token:', error);
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (cb: (token: string) => void) => {
    refreshSubscribers.push(cb);
};

const onRefreshed = (token: string) => {
    refreshSubscribers.forEach((cb) => cb(token));
    refreshSubscribers = [];
};

api.interceptors.response.use(
    (response) => {
        return response;
    },
    async (error) => {
        const originalRequest = error.config;

        if (
            error.response &&
            (error.response.status === 401 || error.response.status === 403) &&
            !originalRequest._retry
        ) {
            console.log('Authentication Error (401/403):', JSON.stringify(error.response.data, null, 2));

            if (isRefreshing) {
                console.log('Refresh already in progress, queuing request...');
                return new Promise((resolve) => {
                    subscribeTokenRefresh((token) => {
                        originalRequest.headers.Authorization = `Bearer ${token}`;
                        resolve(api(originalRequest));
                    });
                });
            }

            originalRequest._retry = true;
            isRefreshing = true;

            try {
                const refreshToken = await AsyncStorage.getItem('refreshToken');
                if (!refreshToken) {
                    throw new Error('No refresh token available');
                }

                console.log('Refreshing access token...');

                const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ refreshToken }),
                });

                if (!response.ok) {
                    throw new Error('Refresh failed');
                }

                const data = await response.json();

                if (data.data && data.data.accessToken) {
                    const newAccessToken = data.data.accessToken;
                    const newRefreshToken = data.data.refreshToken;

                    await AsyncStorage.setItem('accessToken', newAccessToken);
                    if (newRefreshToken) {
                        await AsyncStorage.setItem('refreshToken', newRefreshToken);
                    }

                    console.log('Token refreshed successfully');
                    isRefreshing = false;
                    onRefreshed(newAccessToken);

                    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
                    return api(originalRequest);
                }
            } catch (refreshError) {
                console.error('Token refresh failed:', refreshError);
                isRefreshing = false;
                refreshSubscribers = [];
                await AsyncStorage.multiRemove(['accessToken', 'refreshToken']);
                return Promise.reject(error);
            }
        }

        if (error.response) {
            console.error('API Error Status:', error.response.status);
            console.error('API Error Data:', JSON.stringify(error.response.data, null, 2));
        } else {
            console.error('API Error:', error.message);
        }
        return Promise.reject(error);
    }
);

export default api;
