import axios from 'axios';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Dynamically determine the host IP from the Expo Go URI
const getBaseUrl = () => {
    // 1. Prefer environment variable if set
    if (process.env.EXPO_PUBLIC_API_URL) {
        return process.env.EXPO_PUBLIC_API_URL;
    }

    // 2. Expo 개발 서버에서 호스트 IP 추출 (실제 디바이스 + 에뮬레이터 모두 지원)
    const debuggerHost = Constants.expoConfig?.hostUri || Constants.manifest2?.extra?.expoGo?.debuggerHost;
    if (debuggerHost) {
        const hostIp = debuggerHost.split(':')[0];
        console.log('[API] Using dynamic host IP:', hostIp);
        return `http://${hostIp}:8080`;
    }

    // 3. Android Emulator fallback
    if (Platform.OS === 'android') {
        return 'http://10.0.2.2:8080';
    }

    // 4. iOS Simulator and Web default
    return 'http://localhost:8080';
};

export const BASE_URL = getBaseUrl();

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
import { useErrorStore } from '../store/useErrorStore';

api.interceptors.request.use(
    async (config) => {
        try {
            const token = await AsyncStorage.getItem('accessToken');
            if (token && !config.headers.Authorization && !config.url?.includes('/auth/')) {
                config.headers.Authorization = `Bearer ${token}`;
                // console.log('Added Authorization header:', config.headers.Authorization);
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
                        // 안전한 재요청을 위해 새 객체 생성
                        const retryConfig = {
                            method: originalRequest.method,
                            url: originalRequest.url,
                            params: originalRequest.params,
                            data: originalRequest.data,
                            headers: {
                                ...originalRequest.headers,
                                Authorization: `Bearer ${token}`
                            }
                        };
                        resolve(api(retryConfig));
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

                    console.log('[Auth] New Access Token Issued (Refresh):', newAccessToken);
                    await AsyncStorage.setItem('accessToken', newAccessToken);
                    if (newRefreshToken) {
                        console.log('[Auth] New Refresh Token Issued (Refresh):', newRefreshToken);
                        await AsyncStorage.setItem('refreshToken', newRefreshToken);
                    }

                    console.log('Token refreshed successfully. Retrying original request...');
                    isRefreshing = false;
                    onRefreshed(newAccessToken);

                    // 중요: originalRequest 객체를 그대로 쓰지 않고 필요한 속성만 추출하여 재요청
                    // (Axios 내부 객체 오염 방지)
                    const retryConfig = {
                        method: originalRequest.method,
                        url: originalRequest.url,
                        params: originalRequest.params,
                        data: originalRequest.data,
                        headers: {
                            ...originalRequest.headers,
                            Authorization: `Bearer ${newAccessToken}`
                        }
                    };

                    const retryResponse = await api(retryConfig);
                    return retryResponse;
                }
            } catch (refreshError) {
                console.error('Token refresh failed:', refreshError);
                isRefreshing = false;
                refreshSubscribers = [];
                await AsyncStorage.multiRemove(['accessToken', 'refreshToken']);

                // 리프레시 토큰 재발급도 실패한 경우:
                // - 더 이상 인증 세션이 없으므로 OBD 폴링/연결 포함 전체 세션을 종료한다.
                try {
                    const { useUserStore } = await import('../store/useUserStore');
                    await useUserStore.getState().logout();
                } catch (logoutError) {
                    console.error('[Auth] Auto logout after refresh failure failed:', logoutError);
                }

                return Promise.reject(error);
            }
        }

        if (error.response) {
            console.error('API Error Status:', error.response.status);
            console.error('API Error Data:', JSON.stringify(error.response.data, null, 2));

            const status = error.response.status;

            // 500: Server Error (전역 알림 주석: 각 화면 catch에서 맥락 있는 알림 사용)
            // if (status >= 500) {
            //     showError(
            //         '서버 오류',
            //         '서버에서 문제가 발생했습니다.\n잠시 후 다시 시도해주세요.',
            //         'ERROR'
            //     );
            // }
            // 401/403: Auth Error (전역 알림 주석: refresh 실패 시 위에서 로그아웃 처리)
            // else if (status === 401 || status === 403) {
            //     if (originalRequest.url !== '/api/v1/auth/refresh') {
            //         showError(
            //             '인증 만료',
            //             '로그인이 만료되었습니다.\n다시 로그인해주세요.',
            //             'WARNING'
            //         );
            //     }
            // }
            if (status === 400) {
                const msg = error.response.data?.message || '요청이 올바르지 않습니다.';
                // Only show critical 400s if needed, or rely on local catch
                // showError('요청 오류', msg, 'WARNING'); 
            }
        } else if (error.request) {
            // Network Error (No response) — 전역 알림 주석: 각 화면 catch에서 처리
            console.error('API No Response:', error.request);
            // useErrorStore.getState().showError(
            //     '네트워크 오류',
            //     '서버와 연결할 수 없습니다.\n인터넷 연결 상태를 확인해주세요.',
            //     'ERROR'
            // );
        } else {
            // Setup Error
            console.error('API Error:', error.message);
        }
        return Promise.reject(error);
    }
);

export default api;
