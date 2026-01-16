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

// Response interceptor
api.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        // Handle global errors here
        console.error('API Error:', error);
        return Promise.reject(error);
    }
);

export default api;
