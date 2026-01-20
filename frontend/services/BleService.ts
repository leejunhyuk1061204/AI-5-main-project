import BleManager from 'react-native-ble-manager';
import { NativeEventEmitter, NativeModules, Platform, PermissionsAndroid, DeviceEventEmitter, Alert } from 'react-native';

const BleManagerModule = NativeModules.BleManager;
// Fallback to DeviceEventEmitter if NativeEventEmitter fails or warns significantly
const bleManagerEmitter = new NativeEventEmitter(BleManagerModule); // Keep this for now, but we will use DeviceEventEmitter in addListener logic if needed

if (!BleManagerModule) {
    console.error('BleManagerModule is null! Native module not linked.');
} else {
    // Debug: Log available methods
    console.log('BleManagerModule keys:', Object.keys(BleManagerModule));
}

export interface Peripheral {
    id: string;
    rssi: number;
    name?: string;
    advertising: any;
}

class BleService {
    listeners: any[] = [];
    isInitialized = false;

    constructor() {
        this.initialize();
    }

    async initialize() {
        if (this.isInitialized) return;
        try {
            await BleManager.start({ showAlert: false });
            this.isInitialized = true;
            console.log('BleManager initialized');
        } catch (error) {
            console.error('Failed to initialize BleManager', error);
        }
    }

    async requestPermissions() {
        if (Platform.OS === 'android') {
            if (Platform.Version >= 31) {
                const result = await PermissionsAndroid.requestMultiple([
                    PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
                    PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
                    PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
                ]);
                // Debug Permission Results
                const isGranted = (
                    result['android.permission.BLUETOOTH_CONNECT'] === PermissionsAndroid.RESULTS.GRANTED &&
                    result['android.permission.BLUETOOTH_SCAN'] === PermissionsAndroid.RESULTS.GRANTED &&
                    result['android.permission.ACCESS_FINE_LOCATION'] === PermissionsAndroid.RESULTS.GRANTED
                );
                return isGranted;
            } else {
                const granted = await PermissionsAndroid.request(
                    PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION
                );
                return granted === PermissionsAndroid.RESULTS.GRANTED;
            }
        }
        return true; // iOS handles permissions via Info.plist and OS prompt
    }

    async startScan() {
        const hasPermission = await this.requestPermissions();
        if (!hasPermission) return;

        // Correct v12+ signature: scan(options: ScanOptions)
        return BleManager.scan({
            serviceUUIDs: [],
            seconds: 5,
            allowDuplicates: true,
            // scanMode: 2, // Low Latency / Aggressive (Removed for compatibility)
            // matchMode: 1, // Aggressive (Removed)
            // callbackType: 1 // All Matches (Removed)
        });
    }

    stopScan() {
        return BleManager.stopScan();
    }

    connect(id: string) {
        return BleManager.connect(id);
    }

    disconnect(id: string) {
        return BleManager.disconnect(id);
    }

    retrieveServices(id: string) {
        return BleManager.retrieveServices(id);
    }

    async startNotification(id: string, serviceUUID: string, charUUID: string) {
        await BleManager.startNotification(id, serviceUUID, charUUID);
    }

    addListener(eventType: string, listener: (data: any) => void) {
        // Try NativeEventEmitter first
        const subscription = bleManagerEmitter.addListener(eventType, listener);
        this.listeners.push(subscription);

        // Also add to DeviceEventEmitter just in case (for Android mostly)
        // This might cause double events if both work, but for debugging/fixing "No events" it's worth it.
        // We can debounce or dedupe in the UI side callback if needed.
        const deviceSubscription = DeviceEventEmitter.addListener(eventType, listener);
        this.listeners.push(deviceSubscription);

        return subscription;
    }

    removeListeners() {
        this.listeners.forEach(l => l.remove());
        this.listeners = [];
    }

    // OBD Command Helper (Example)
    stringToBytes(string: string) {
        const array = new Uint8Array(string.length);
        for (let i = 0, l = string.length; i < l; i++) {
            array[i] = string.charCodeAt(i);
        }
        return Array.from(array);
    }

    async write(id: string, serviceUUID: string, charUUID: string, command: string) {
        const data = this.stringToBytes(command + '\r');
        return BleManager.write(id, serviceUUID, charUUID, data);
    }
}

export default new BleService();
