import type { BluetoothDevice } from 'react-native-bluetooth-classic';
import { PermissionsAndroid, Platform } from 'react-native';

let RNBluetoothClassic: any;

if (Platform.OS !== 'web') {
    const ClassicModule = require('react-native-bluetooth-classic');
    RNBluetoothClassic = ClassicModule.default;
}

class ClassicBtService {
    private isInitialized = false;

    async initialize() {
        if (this.isInitialized) return;
        if (Platform.OS === 'web') {
            console.log('[ClassicBT] Web environment - mocking disabled');
            this.isInitialized = true;
            return;
        }

        try {
            const available = await RNBluetoothClassic.isBluetoothAvailable();
            console.log('[ClassicBT] Bluetooth available:', available);

            if (!available) {
                console.error('[ClassicBT] Classic Bluetooth not available on this device');
                return;
            }

            const enabled = await RNBluetoothClassic.isBluetoothEnabled();
            if (!enabled) {
                console.log('[ClassicBT] Bluetooth not enabled, requesting...');
                await RNBluetoothClassic.requestBluetoothEnabled();
            }

            this.isInitialized = true;
            console.log('[ClassicBT] Initialized successfully');
        } catch (error) {
            console.error('[ClassicBT] Initialization failed:', error);
        }
    }

    async requestPermissions(): Promise<boolean> {
        if (Platform.OS === 'android') {
            if (Platform.Version >= 31) {
                const result = await PermissionsAndroid.requestMultiple([
                    PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
                    PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
                ]);
                return (
                    result['android.permission.BLUETOOTH_CONNECT'] === PermissionsAndroid.RESULTS.GRANTED &&
                    result['android.permission.BLUETOOTH_SCAN'] === PermissionsAndroid.RESULTS.GRANTED
                );
            }
        }
        return true;
    }

    async getBondedDevices(): Promise<BluetoothDevice[]> {
        if (Platform.OS === 'web') return [];
        try {
            const hasPermission = await this.requestPermissions();
            if (!hasPermission) {
                console.warn('[ClassicBT] Permissions not granted');
                return [];
            }

            const bonded = await RNBluetoothClassic.getBondedDevices();
            console.log('[ClassicBT] Bonded devices:', bonded.length);
            return bonded;
        } catch (error) {
            console.error('[ClassicBT] Failed to get bonded devices:', error);
            return [];
        }
    }

    async connect(device: BluetoothDevice): Promise<boolean> {
        try {
            console.log(`[ClassicBT] Connecting to ${device.name} (${device.address})...`);

            // Check if already connected
            const isConnected = await device.isConnected();
            if (isConnected) {
                console.log('[ClassicBT] Already connected');
                return true;
            }

            // 여러 연결 방식 시도
            console.log('[ClassicBT] Trying RFCOMM connection...');

            // RFCOMM 연결 (기본 SPP UUID 사용)
            const connected = await device.connect({
                delimiter: '\r\n',  // ELM327은 보통 \r\n 사용
                charset: 'utf-8',
                // @ts-ignore - 라이브러리 타입 정의에 없을 수 있음
                connectorType: 'rfcomm',
                // @ts-ignore
                DELIMITER: '\r\n>',
            });

            if (connected) {
                console.log('[ClassicBT] RFCOMM connected successfully!');
                return true;
            }

            console.log('[ClassicBT] Connection result:', connected);
            return connected;
        } catch (error) {
            console.error('[ClassicBT] Connection failed:', error);

            // 첫 번째 실패 시 accept 모드로 재시도
            try {
                console.log('[ClassicBT] Retrying with accept mode...');
                const connected = await device.connect({
                    delimiter: '\r',
                    charset: 'utf-8',
                });
                return connected;
            } catch (retryError) {
                console.error('[ClassicBT] Retry also failed:', retryError);
                return false;
            }
        }
    }

    async disconnect(device: BluetoothDevice): Promise<boolean> {
        try {
            const disconnected = await device.disconnect();
            console.log('[ClassicBT] Disconnected:', disconnected);
            return disconnected;
        } catch (error) {
            console.error('[ClassicBT] Disconnect failed:', error);
            return false;
        }
    }

    async write(device: BluetoothDevice, command: string): Promise<boolean> {
        try {
            const success = await device.write(command + '\r');
            return success;
        } catch (error) {
            console.error('[ClassicBT] Write failed:', error);
            return false;
        }
    }

    async read(device: BluetoothDevice): Promise<string> {
        try {
            const data = await device.read();
            return data?.toString() || '';
        } catch (error) {
            console.error('[ClassicBT] Read failed:', error);
            return '';
        }
    }

    // 버퍼에 있는 모든 데이터 읽기
    async readAvailable(device: BluetoothDevice): Promise<string> {
        try {
            // @ts-ignore - available()이 타입에 없을 수 있음
            const available = await device.available();
            console.log(`[ClassicBT] Available bytes: ${available}`);

            if (available > 0) {
                const data = await device.read();
                console.log(`[ClassicBT] Read data: "${data}"`);
                return data?.toString() || '';
            }
            return '';
        } catch (error) {
            console.error('[ClassicBT] ReadAvailable failed:', error);
            return '';
        }
    }

    // SPP 데이터 리스너 설정
    onDataReceived(device: BluetoothDevice, callback: (data: string) => void) {
        console.log('[ClassicBT] Registering onDataReceived listener...');
        const subscription = device.onDataReceived((event) => {
            console.log(`[ClassicBT] onDataReceived event:`, event);
            callback(event.data);
        });
        console.log('[ClassicBT] Listener registered');
        return subscription;
    }
}

export default new ClassicBtService();
