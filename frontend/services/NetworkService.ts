import NetInfo from '@react-native-community/netinfo';
import { useAlertStore } from '../store/useAlertStore';

class NetworkService {
    private static instance: NetworkService;
    private isConnected: boolean = true;
    private listeners: ((isConnected: boolean) => void)[] = [];

    private constructor() {
        NetInfo.addEventListener(state => {
            const connected = state.isConnected ?? false;
            if (this.isConnected !== connected) {
                this.isConnected = connected;
                this.notifyListeners(connected);

                if (connected) {
                    console.log('[NetworkService] Online');
                    // Helper to trigger sync if needed, though usually triggered by ObdService
                } else {
                    console.log('[NetworkService] Offline');
                    // Optional: Show toast
                }
            }
        });
    }

    public static getInstance(): NetworkService {
        if (!NetworkService.instance) {
            NetworkService.instance = new NetworkService();
        }
        return NetworkService.instance;
    }

    public get IsConnected(): boolean {
        return this.isConnected;
    }

    public addListener(callback: (isConnected: boolean) => void) {
        this.listeners.push(callback);
    }

    public removeListener(callback: (isConnected: boolean) => void) {
        this.listeners = this.listeners.filter(l => l !== callback);
    }

    private notifyListeners(isConnected: boolean) {
        this.listeners.forEach(l => l(isConnected));
    }
}

export default NetworkService.getInstance();
