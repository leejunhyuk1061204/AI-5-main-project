import { NativeEventEmitter, NativeModules, Platform, PermissionsAndroid, DeviceEventEmitter } from 'react-native';
import { useAlertStore } from '../store/useAlertStore';
import { useBleStore } from '../store/useBleStore';

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
    console.error('[BleService] BleManager native module not linked.');
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
            this.isInitialized = true;
            return;
        }

        try {
            await BleManager.start({ showAlert: false });
            this.isInitialized = true;
            DeviceEventEmitter.addListener('BleManagerDiscoverPeripheral', (data) => {
                useBleStore.getState().addDevice(data);
            });

            DeviceEventEmitter.addListener('BleManagerStopScan', () => {
                useBleStore.getState().setScanning(false);
            });

            DeviceEventEmitter.addListener('BleManagerConnectPeripheral', (data: any) => {
                useBleStore.getState().setStatus('connected');
                useBleStore.getState().setConnectedDevice(data.peripheral);
            });

            DeviceEventEmitter.addListener('BleManagerDisconnectPeripheral', () => {
                useBleStore.getState().setStatus('disconnected');
                useBleStore.getState().setConnectedDevice(null);
                useBleStore.getState().setConnectedVehicleId(null);
            });

        } catch (error) {
            console.error('[BleService] Failed to initialize BleManager', error);
            useBleStore.getState().setError('Failed to initialize BLE');
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
            useBleStore.getState().setScanning(true);
            setTimeout(() => {
                useBleStore.getState().addDevice({ id: 'WEB-SIM-1', name: 'Simulated OBD', rssi: -50 } as any);
                useBleStore.getState().addDevice({ id: 'WEB-SIM-2', name: 'Simulated Device 2' } as any);
                useBleStore.getState().setScanning(false);
            }, 2000);
            return;
        }

        // Debug: Check Permissions
        const hasPermission = await this.requestPermissions();
        if (!hasPermission) {
            useAlertStore.getState().showAlert('Permission Error', 'Bluetooth permissions are required.', 'ERROR');
            return;
        }

        useBleStore.getState().setScanning(true);
        useBleStore.getState().setStatus('scanning');
        useBleStore.getState().clearDevices();
        console.log('[BleService] scan started');
        return BleManager.scan({
            serviceUUIDs: [],
            seconds: 5,
            allowDuplicates: true,
        }).then(() => {
            console.log('[BleService] scan completed');
        }).catch((err: any) => {
            const msg = err?.message ?? String(err);
            console.error('[BleService] scan failed. reason=', msg);
            useAlertStore.getState().showAlert('Scan Error', `Failed to start scan: ${msg}`, 'ERROR');
            useBleStore.getState().setScanning(false);
            useBleStore.getState().setStatus('disconnected');
            useBleStore.getState().setConnectedVehicleId(null);
        });
    }

    stopScan() {
        if (Platform.OS === 'web') return Promise.resolve();
        return BleManager.stopScan();
    }

    connect(id: string) {
        if (Platform.OS === 'web') return Promise.resolve();
        useBleStore.getState().setStatus('connecting');
        console.log('[BleService] connecting id=', id);
        return BleManager.connect(id)
            .then(() => {
                console.log('[BleService] connected id=', id);
                useBleStore.getState().setStatus('connected');
                useBleStore.getState().setConnectedDevice(id);
            })
            .catch((err: any) => {
                const msg = err?.message ?? String(err);
                console.error('[BleService] connect failed. id=', id, 'reason=', msg);
                useBleStore.getState().setStatus('disconnected');
                useBleStore.getState().setConnectedVehicleId(null);
                useBleStore.getState().setError(`Connection failed: ${msg}`);
                throw err;
            });
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
        return BleManager.disconnect(id).then(() => {
            console.log('[BleService] disconnected id=', id);
            useBleStore.getState().setStatus('disconnected');
            useBleStore.getState().setConnectedDevice(null);
            useBleStore.getState().setConnectedVehicleId(null);
        });
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
