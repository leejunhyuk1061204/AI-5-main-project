import axios from 'axios';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Dynamically determine the host IP from the Expo Go URI
const getBaseUrl = () => {
    // If we have a specific host URI from Expo (e.g., when running on a physical device)
    if (Constants.expoConfig?.hostUri) {
        const host = Constants.expoConfig.hostUri.split(':')[0];
        return `http://${host}:8080`;
    }

    // Fallback for Android Emulator (10.0.2.2 is localhost for AVD)
    if (Platform.OS === 'android') {
        return 'http://10.0.2.2:8080';
    }

    // Fallback for iOS Simulator or Web (localhost)
    return 'http://localhost:8080';
};

const BASE_URL = getBaseUrl();

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
api.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        // Handle global errors here
        console.error('API Error:', error.response?.status, error.message);
        return Promise.reject(error);
    }
);

export default api;
