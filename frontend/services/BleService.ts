import { NativeEventEmitter, NativeModules, Platform, PermissionsAndroid, DeviceEventEmitter, Alert } from 'react-native';

let BleManager: any;
let BleManagerModule: any;

if (Platform.OS !== 'web') {
    BleManager = require('react-native-ble-manager').default;
    BleManagerModule = NativeModules.BleManager;
}

// Fallback for Web/No-Native environment
const bleManagerEmitter = (Platform.OS !== 'web' && BleManagerModule)
    ? new NativeEventEmitter(BleManagerModule)
    : DeviceEventEmitter;

if (Platform.OS !== 'web' && !BleManagerModule) {
    console.error('BleManagerModule is null! Native module not linked.');
} else if (Platform.OS !== 'web') {
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
        if (Platform.OS === 'web') {
            console.log('[BleService] Web environment detected - mocking BLE');
            this.isInitialized = true;
            return;
        }

        try {
            await BleManager.start({ showAlert: false });
            this.isInitialized = true;
            console.log('[BleService] BleManager initialized');

            // DEBUG: Global listener to see if ANY event comes through
            DeviceEventEmitter.addListener('BleManagerDiscoverPeripheral', (data) => {
                console.log('[BleService DEBUG] Global Listener Event:', data);
            });

        } catch (error) {
            console.error('[BleService] Failed to initialize BleManager', error);
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
        if (Platform.OS === 'web') {
            console.log('[BleService] Web scan simulated');
            return;
        }

        // Debug: Check Permissions
        const hasPermission = await this.requestPermissions();
        console.log('[BleService] Permissions granted:', hasPermission);
        // Alert.alert('Debug', `Permissions granted: ${hasPermission}`); // Uncomment if console is hard to see

        if (!hasPermission) {
            Alert.alert('Permission Error', 'Bluetooth permissions are required.');
            return;
        }

        console.log('[BleService] Starting scan with defaults...');
        // Correct v12+ signature: scan(options: ScanOptions)
        return BleManager.scan({
            serviceUUIDs: [],
            seconds: 5,
            allowDuplicates: true,
        }).then(() => {
            console.log('[BleService] Scan started successfully');
        }).catch(err => {
            console.error('[BleService] Scan failed to start', err);
            Alert.alert('Scan Error', `Failed to start scan: ${err}`);
        });
    }

    stopScan() {
        if (Platform.OS === 'web') return Promise.resolve();
        return BleManager.stopScan();
    }

    connect(id: string) {
        if (Platform.OS === 'web') return Promise.resolve();
        return BleManager.connect(id);
    }

    createBond(id: string) {
        if (Platform.OS === 'web') return Promise.resolve();
        return BleManager.createBond(id);
    }

    removeBond(id: string) {
        if (Platform.OS === 'web') return Promise.resolve();
        return BleManager.removeBond(id);
    }

    disconnect(id: string) {
        if (Platform.OS === 'web') return Promise.resolve();
        return BleManager.disconnect(id);
    }

    retrieveServices(id: string) {
        if (Platform.OS === 'web') return Promise.resolve({ characteristics: [] });
        return BleManager.retrieveServices(id);
    }

    async startNotification(id: string, serviceUUID: string, charUUID: string) {
        if (Platform.OS === 'web') return;
        await BleManager.startNotification(id, serviceUUID, charUUID);
    }

    getBondedPeripherals() {
        if (Platform.OS === 'web') return Promise.resolve([]);
        return BleManager.getBondedPeripherals();
    }

    isPeripheralConnected(id: string, serviceUUIDs: string[] = []) {
        if (Platform.OS === 'web') return Promise.resolve(false);
        return BleManager.isPeripheralConnected(id, serviceUUIDs);
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
