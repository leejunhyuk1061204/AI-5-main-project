import axios from 'axios';
import { Platform } from 'react-native';

const BASE_URL = Platform.select({
    android: 'http://192.168.0.11:8080', // Physical Device / Emulator (LAN IP)
    ios: 'http://192.168.0.11:8080', // Physical Device / Emulator (LAN IP)
    default: 'http://192.168.0.11:8080', // Fallback
});

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
