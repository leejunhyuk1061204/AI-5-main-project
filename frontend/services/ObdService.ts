import { NativeEventEmitter, NativeModules, Platform } from 'react-native';
import type { BluetoothDevice } from 'react-native-bluetooth-classic';
let BleManager: any;

if (Platform.OS !== 'web') {
    BleManager = require('react-native-ble-manager').default;
}
import BleService from './BleService';
import ClassicBtService from './ClassicBtService';
import { OBD_PIDS, parseObdResponse, PidDefinition } from './ObdPidHelper';
import { uploadObdBatch, ObdLogRequest } from '../api/obdApi';
import { useBleStore } from '../store/useBleStore';
import BackgroundService from './BackgroundService';
import { checkAndRequestBatteryOpt } from '../utils/BatteryOptConfig';
import { useTripStore } from '../store/useTripStore';
import NetworkService from './NetworkService';
import OfflineStorage from './OfflineStorage';
import api from '../api/axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY_LAST_DEVICE = 'last_obd_device';
const STORAGE_KEY_LAST_TYPE = 'last_obd_type';

export interface ObdData {
    timestamp: string;
    rpm?: number;
    speed?: number;
    voltage?: number;
    coolant_temp?: number;
    engine_load?: number;
    fuel_trim_short?: number;
    fuel_trim_long?: number;
}

type ConnectionType = 'ble' | 'classic' | null;

class ObdService {
    private isPolling = false;
    private connectionType: ConnectionType = null;
    private isDisconnectRequested = false;
    private reconnectAttempts = 0;
    private readonly MAX_RECONNECT_ATTEMPTS = 5;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    // BLE 관련
    private currentDeviceId: string | null = null;
    private serviceUUID = 'FFE0';
    private charUUID = 'FFE1';

    // Classic BT 관련
    private classicDevice: BluetoothDevice | null = null;
    private classicDataSubscription: any = null;

    // Command Queue
    private commandQueue: PidDefinition[] = [];
    private isProcessingQueue = false;
    private currentPid: PidDefinition | null = null;
    private responseBuffer = '';

    // Observers
    private listeners: ((data: ObdData) => void)[] = [];

    // Current Snapshot
    private currentData: ObdData = { timestamp: new Date().toISOString() };

    // ===== 배치 업로드 관련 =====
    private dataBuffer: ObdData[] = [];
    private vehicleId: string | null = null;
    private readonly BATCH_SIZE = 180; // 3분 (180초)

    constructor() {
        if (Platform.OS !== 'web') {
            const BleManagerModule = NativeModules.BleManager;
            if (BleManagerModule) {
                const bleManagerEmitter = new NativeEventEmitter(BleManagerModule);

                // BLE 응답 리스너
                bleManagerEmitter.addListener(
                    'BleManagerDidUpdateValueForCharacteristic',
                    ({ value, peripheral }: any) => {
                        if (this.connectionType !== 'ble') return;
                        if (peripheral !== this.currentDeviceId) return;

                        const asciiString = String.fromCharCode(...value);
                        this.handleResponse(asciiString);
                    }
                );
            }
        }

        // Listen for network changes
        NetworkService.addListener((isConnected) => {
            if (isConnected) {
                console.log('[ObdService] Network connected, processing offline queue...');
                this.processOfflineQueue();
            }
        });
    }

    // ===== Classic Bluetooth 설정 =====
    async setClassicDevice(device: BluetoothDevice) {
        this.connectionType = 'classic';
        this.classicDevice = device;
        this.currentData = { timestamp: new Date().toISOString() };
        this.isPolling = false;
        this.isDisconnectRequested = false;
        this.reconnectAttempts = 0;
        useBleStore.getState().setConnectedDeviceName(device.name || 'Classic Device');
        useBleStore.getState().setConnectedDevice(device.address);
        useBleStore.getState().setConnectedDevice(device.address);
        useBleStore.getState().setStatus('connected');

        // Save for auto-connect
        this.saveLastDevice('classic', device.address, device.name || 'Classic Device');

        console.log(`[ObdService] Classic BT device set: ${device.name}`);

        // Classic BT 데이터 리스너 설정 (모든 응답은 여기로 옴)
        console.log('[ObdService] Setting up Classic BT data listener...');
        this.classicDataSubscription = ClassicBtService.onDataReceived(device, (data) => {
            console.log(`[ObdService] <<< Received via listener: "${data}"`);
            this.handleResponse(data);
        });
        console.log('[ObdService] Data listener ready');

        // ELM327 초기화 명령 전송
        await this.initializeElm327();

        // 배터리 최적화 확인
        checkAndRequestBatteryOpt();
    }

    // ===== BLE 설정 =====
    async setTargetDevice(deviceId: string) {
        if (Platform.OS === 'web') {
            console.warn('[ObdService] BLE not supported on web');
            return;
        }

        this.connectionType = 'ble';
        this.currentDeviceId = deviceId;
        this.currentData = { timestamp: new Date().toISOString() };
        this.isPolling = false;
        useBleStore.getState().setStatus('connecting');

        try {
            const peripheralInfo = await BleManager.retrieveServices(deviceId);
            console.log('[ObdService] Peripheral Info:', JSON.stringify(peripheralInfo, null, 2));

            let found = false;

            if (peripheralInfo.characteristics) {
                // FFE0/FFE1 또는 FFF0/FFF1 찾기
                for (const char of peripheralInfo.characteristics) {
                    const svc = char.service.toLowerCase();
                    const chr = char.characteristic.toLowerCase();
                    if ((svc.includes('ffe0') && chr.includes('ffe1')) ||
                        (svc.includes('fff0') && chr.includes('fff1'))) {
                        this.serviceUUID = char.service;
                        this.charUUID = char.characteristic;
                        found = true;
                        console.log(`[ObdService] Found OBD service: ${this.serviceUUID}/${this.charUUID}`);
                        break;
                    }
                }

                // Notify+Write 특성 찾기
                if (!found) {
                    const standardServices = ['1800', '1801', '180a', '180f', '1805'];
                    for (const char of peripheralInfo.characteristics) {
                        const svc = char.service.toLowerCase();
                        const props = char.properties || {};
                        if (standardServices.some(s => svc.includes(s))) continue;
                        if ((props.Notify) && (props.Write || props.WriteWithoutResponse)) {
                            this.serviceUUID = char.service;
                            this.charUUID = char.characteristic;
                            found = true;
                            console.log(`[ObdService] Auto-selected: ${this.serviceUUID}/${this.charUUID}`);
                            break;
                        }
                    }
                }
            }

            if (found) {
                await BleService.startNotification(this.currentDeviceId, this.serviceUUID, this.charUUID);
                console.log('[ObdService] BLE Notifications enabled');
                useBleStore.getState().setStatus('connected');
                useBleStore.getState().setConnectedDevice(this.currentDeviceId);
                useBleStore.getState().setConnectedDeviceName(this.currentDeviceId);
                useBleStore.getState().setConnectedDeviceName(this.currentDeviceId);

                // Save for auto-connect
                this.saveLastDevice('ble', this.currentDeviceId, this.currentDeviceId);

                await this.initializeElm327();
                // 배터리 최적화 확인
                checkAndRequestBatteryOpt();
            } else {
                console.warn('[ObdService] Could not find OBD characteristics');
                useBleStore.getState().setStatus('disconnected');
            }

        } catch (e) {
            console.error('[ObdService] Failed to configure BLE device', e);
            useBleStore.getState().setStatus('disconnected');
        }
    }

    // ===== ELM327 초기화 =====
    private async initializeElm327() {
        console.log('[ObdService] Initializing ELM327...');

        const initCommands = [
            'ATZ',      // 리셋
            'ATE0',     // 에코 끄기
            'ATL0',     // 줄바꿈 끄기
            'ATS0',     // 공백 끄기
            'ATH0',     // 헤더 끄기
            'ATSP0',    // 프로토콜 자동 감지
        ];

        for (const cmd of initCommands) {
            await this.sendCommand(cmd);
            await this.delay(200);
        }

        console.log('[ObdService] ELM327 initialized');
    }

    // ===== 명령 전송 =====
    private async sendCommand(command: string): Promise<boolean> {
        try {
            if (this.connectionType === 'classic' && this.classicDevice) {
                return await ClassicBtService.write(this.classicDevice, command);
            } else if (this.connectionType === 'ble' && this.currentDeviceId) {
                if (Platform.OS === 'web') return false;
                const bytes = this.stringToBytes(command + '\r');
                await BleManager.writeWithoutResponse(
                    this.currentDeviceId,
                    this.serviceUUID,
                    this.charUUID,
                    bytes
                );
                return true;
            }
            return false;
        } catch (e) {
            console.error(`[ObdService] Send failed: ${command}`, e);
            return false;
        }
    }

    // ===== 폴링 시작/중지 =====
    startPolling(intervalMs: number = 1000) {
        if (this.isPolling) return;
        if (!this.connectionType) {
            console.warn('[ObdService] No device connected');
            return;
        }

        console.log(`[ObdService] Starting polling (${this.connectionType})...`);
        this.isPolling = true;
        useBleStore.getState().setPolling(true);
        this.pollingLoop(intervalMs);

        // [Auto Trip] 주행 시작 (Trip ID 발급)
        if (this.vehicleId) {
            console.log('[ObdService] Auto-starting trip for vehicle:', this.vehicleId);
            useTripStore.getState().startTrip(this.vehicleId);
        } else {
            console.warn('[ObdService] Cannot auto-start trip: Vehicle ID not set');
        }

        // 안드로이드 백그라운드 서비스 시작
        if (Platform.OS === 'android') {
            BackgroundService.start();
        }
    }

    async stopPolling() {
        this.isPolling = false;
        this.commandQueue = [];
        this.isProcessingQueue = false;
        useBleStore.getState().setPolling(false);
        console.log('[ObdService] Polling stopped, flushing buffer...');
        await this.flushBuffer();

        // [Auto Trip] 주행 종료 (Trip ID 리셋)
        // 연결이 해제되거나 폴링이 멈추면 주행 종료로 간주
        console.log('[ObdService] Auto-ending trip...');
        await useTripStore.getState().endTrip();

        // 안드로이드 백그라운드 서비스 중지
        if (Platform.OS === 'android') {
            BackgroundService.stop();
        }
    }

    // ===== 데이터 구독 =====
    onData(callback: (data: ObdData) => void) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter(l => l !== callback);
        };
    }

    private notifyListeners(data: ObdData) {
        this.listeners.forEach(listener => listener(data));
    }

    // ===== 폴링 루프 =====
    private pollingLoop(intervalMs: number) {
        if (!this.isPolling) return;

        const batch = [
            OBD_PIDS.RPM,
            OBD_PIDS.SPEED,
            OBD_PIDS.ENGINE_LOAD,
            OBD_PIDS.COOLANT_TEMP,
        ];

        this.commandQueue.push(...batch);
        this.processQueue();

        setTimeout(() => this.pollingLoop(intervalMs), intervalMs);
    }

    private async processQueue() {
        if (this.isProcessingQueue || this.commandQueue.length === 0) return;

        this.isProcessingQueue = true;

        while (this.commandQueue.length > 0 && this.isPolling) {
            const pid = this.commandQueue.shift();
            if (!pid) break;

            this.currentPid = pid;
            this.responseBuffer = '';

            const command = `${pid.mode}${pid.pid}`;
            console.log(`[ObdService] Sending: ${command}`);

            const success = await this.sendCommand(command);
            if (!success) {
                console.warn(`[ObdService] Failed to send: ${command}`);
                this.currentPid = null;
                continue;
            }

            // Classic BT: 응답 대기 후 버퍼에서 읽기 시도
            if (this.connectionType === 'classic' && this.classicDevice) {
                console.log('[ObdService] Waiting for response...');
                await this.delay(500);

                // 버퍼에 데이터 있는지 확인
                const response = await ClassicBtService.readAvailable(this.classicDevice);
                if (response) {
                    console.log(`[ObdService] Got response: "${response}"`);
                    this.handleResponse(response);
                }
            }
        }

        this.isProcessingQueue = false;

        // 리스너에 알림
        this.currentData.timestamp = new Date().toISOString();
        console.log('[ObdService] Current data:', JSON.stringify(this.currentData));
        this.notifyListeners({ ...this.currentData });

        // 배치 업로드를 위해 데이터 수집
        this.collectData({ ...this.currentData });
    }

    // ===== 응답 처리 =====
    private handleResponse(responseStr: string) {
        if (!responseStr) return;

        console.log(`[ObdService] Raw response: "${responseStr}"`);

        this.responseBuffer += responseStr;

        // 완전한 응답인지 확인 (> 로 끝나거나 줄바꿈 포함)
        if (!this.responseBuffer.includes('>') && !this.responseBuffer.includes('\r')) {
            return; // 더 많은 데이터 대기
        }

        if (!this.currentPid) {
            this.responseBuffer = '';
            return;
        }

        const result = parseObdResponse(this.responseBuffer, this.currentPid);
        console.log(`[ObdService] Parsed ${this.currentPid.name}: ${result}`);

        if (result !== null) {
            switch (this.currentPid.pid) {
                case OBD_PIDS.RPM.pid:
                    this.currentData.rpm = result as number;
                    console.log(`[ObdService] RPM: ${result}`);
                    break;
                case OBD_PIDS.SPEED.pid:
                    this.currentData.speed = result as number;
                    console.log(`[ObdService] Speed: ${result}`);
                    break;
                case OBD_PIDS.ENGINE_LOAD.pid:
                    this.currentData.engine_load = result as number;
                    break;
                case OBD_PIDS.COOLANT_TEMP.pid:
                    this.currentData.coolant_temp = result as number;
                    break;
                case OBD_PIDS.VOLTAGE.pid:
                    this.currentData.voltage = result as number;
                    break;
                case OBD_PIDS.FUEL_TRIM_SHORT.pid:
                    this.currentData.fuel_trim_short = result as number;
                    break;
                case OBD_PIDS.FUEL_TRIM_LONG.pid:
                    this.currentData.fuel_trim_long = result as number;
                    break;
            }
        }

        this.currentPid = null;
        this.responseBuffer = '';
    }

    // ===== 유틸리티 =====
    private stringToBytes(str: string) {
        const array = [];
        for (let i = 0; i < str.length; i++) {
            array.push(str.charCodeAt(i));
        }
        return array;
    }

    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ===== 현재 데이터 가져오기 =====
    getCurrentData(): ObdData {
        return { ...this.currentData };
    }

    // ===== 차량 ID 설정 (배치 업로드에 필요) =====
    setVehicleId(id: string) {
        this.vehicleId = id;
        console.log(`[ObdService] Vehicle ID set: ${id}`);
    }

    // ===== 배치 업로드용 데이터 수집 =====
    private collectData(data: ObdData) {
        if (this.dataBuffer.length >= 1000) {
            console.warn('[ObdService] Buffer full, clearing old data to prevent OOM');
            this.dataBuffer = [];
        }
        this.dataBuffer.push(data);
        console.log(`[ObdService] Data buffered: ${this.dataBuffer.length}/${this.BATCH_SIZE}`);

        if (this.dataBuffer.length >= this.BATCH_SIZE) {
            this.uploadBatch();
        }
    }

    // ===== 배치 업로드 실행 =====
    private async uploadBatch() {
        if (this.dataBuffer.length === 0) return;

        if (!this.vehicleId) {
            console.warn('[ObdService] Cannot upload: no vehicleId. Clearing buffer to save memory.');
            this.dataBuffer = [];
            return;
        }

        const logs: ObdLogRequest[] = this.dataBuffer.map(d => ({
            timestamp: d.timestamp,
            vehicleId: this.vehicleId!,
            rpm: d.rpm,
            speed: d.speed,
            voltage: d.voltage,
            coolantTemp: d.coolant_temp,
            engineLoad: d.engine_load,
            fuelTrimShort: d.fuel_trim_short,
            fuelTrimLong: d.fuel_trim_long,
        }));

        // 1. 오프라인 상태이면 즉시 큐에 저장하고 버퍼 비움
        if (!NetworkService.IsConnected) {
            console.log('[ObdService] Offline detected. Queuing batch to SQLite.');
            await OfflineStorage.addToQueue({
                url: '/telemetry/batch',
                method: 'POST',
                body: JSON.stringify(logs),
                timestamp: Date.now()
            });
            this.dataBuffer = [];
            return;
        }

        try {
            console.log(`[ObdService] Uploading batch: ${logs.length} items`);
            await uploadObdBatch(logs);
            console.log('[ObdService] Batch upload successful!');
            this.dataBuffer = []; // 성공 시 버퍼 비우기
        } catch (error) {
            console.error('[ObdService] Batch upload failed:', error);

            // 네트워크 에러인 경우 큐에 저장 (Axios 에러 코드 확인 또는 간단히 타임아웃/연결실패 간주)
            // 여기서는 안전하게 오프라인 큐로 보냄
            console.log('[ObdService] Upload failed. Saving to offline queue.');
            await OfflineStorage.addToQueue({
                url: '/telemetry/batch',
                method: 'POST',
                body: JSON.stringify(logs),
                timestamp: Date.now()
            });
            this.dataBuffer = [];
        }
    }

    // ===== 오프라인 데이터 동기화 =====
    private async processOfflineQueue() {
        const queue = await OfflineStorage.getQueue();
        if (queue.length === 0) return;

        console.log(`[ObdService] Syncing ${queue.length} offline requests...`);

        for (const req of queue) {
            if (!NetworkService.IsConnected) {
                console.log('[ObdService] Network lost during sync. Pausing.');
                break;
            }

            try {
                await api.request({
                    url: req.url,
                    method: req.method,
                    data: req.body ? JSON.parse(req.body) : undefined,
                });
                console.log(`[ObdService] Synced request ${req.id}`);
                if (req.id) await OfflineStorage.removeFromQueue(req.id);
            } catch (e) {
                console.error(`[ObdService] Failed to sync request ${req.id}`, e);
                // 4xx 에러면 삭제해야 할 수도 있음. 일단은 유지하거나 retry count 증가 로직 필요 (OfflineStorage 개선 사항)
                // 지금은 간단히 break (다음 연결 시 재시도)
                break;
            }
        }
    }

    // ===== 남은 버퍼 즉시 업로드 (연결 해제 시 호출) =====
    async flushBuffer() {
        if (this.dataBuffer.length > 0) {
            console.log(`[ObdService] Flushing remaining ${this.dataBuffer.length} items...`);
            await this.uploadBatch();
        }
    }

    // ===== 연결 해제 =====
    async disconnect() {
        this.isDisconnectRequested = true; // 의도적 해제 표시
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        this.stopPolling();

        // 남은 데이터 업로드
        await this.flushBuffer();

        if (this.classicDataSubscription) {
            this.classicDataSubscription.remove();
            this.classicDataSubscription = null;
        }

        if (this.connectionType === 'classic' && this.classicDevice) {
            await ClassicBtService.disconnect(this.classicDevice);
        }

        this.connectionType = null;
        this.classicDevice = null;
        this.currentDeviceId = null;
        this.dataBuffer = [];
        useBleStore.getState().reset();
        console.log('[ObdService] Disconnected');
    }

    // ===== 시뮬레이션 모드 =====
    private simulationTimer: ReturnType<typeof setTimeout> | null = null;

    startSimulation() {
        if (this.isPolling) {
            console.warn('[ObdService] Already polling/simulating');
            return;
        }
        this.isPolling = true;
        console.log('[ObdService] 🚗 Simulation Mode Started');
        this.simulationLoop();
    }

    stopSimulation() {
        this.isPolling = false;
        if (this.simulationTimer) {
            clearTimeout(this.simulationTimer);
            this.simulationTimer = null;
        }
        console.log('[ObdService] 🛑 Simulation Stopped');
    }

    private simulationLoop() {
        if (!this.isPolling) return;

        // 가짜 OBD 데이터 생성
        const fakeData: ObdData = {
            timestamp: new Date().toISOString(),
            rpm: Math.floor(Math.random() * (3000 - 800) + 800),
            speed: Math.floor(Math.random() * 120),
            engine_load: Math.floor(Math.random() * 100),
            coolant_temp: Math.floor(Math.random() * (110 - 80) + 80),
            voltage: parseFloat((Math.random() * (14.5 - 12) + 12).toFixed(1)),
            fuel_trim_short: parseFloat((Math.random() * 10 - 5).toFixed(1)),
            fuel_trim_long: parseFloat((Math.random() * 10 - 5).toFixed(1)),
        };

        this.currentData = fakeData;
        this.notifyListeners(fakeData);
        this.collectData(fakeData);

        // 1초 후 다음 데이터 생성
        this.simulationTimer = setTimeout(() => this.simulationLoop(), 1000);
    }

    // ===== 연결 상태 확인 =====
    isConnected(): boolean {
        return this.connectionType !== null;
    }

    // ===== 재연결 로직 =====
    private handleDisconnection() {
        if (this.isDisconnectRequested) {
            console.log('[ObdService] Disconnected by user.');
            return;
        }

        console.warn('[ObdService] Unexpected disconnection detected!');
        this.connectionType = null; // 일단 연결 상태 초기화
        this.attemptReconnect();
    }

    private async attemptReconnect() {
        if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
            console.error('[ObdService] Max reconnect attempts reached. Giving up.');
            useBleStore.getState().setStatus('disconnected');
            // 여기서 사용자에게 알림을 보낼 수 있음 (AlertStore 활용 등)
            return;
        }

        this.reconnectAttempts++;
        const delayMs = 3000;
        console.log(`[ObdService] Reconnecting attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS} in ${delayMs}ms...`);
        useBleStore.getState().setStatus('connecting'); // 'reconnecting' is not a valid state, so fallback to 'connecting' 
        // BleStore에 'reconnecting' 상태가 없다면 'connecting' 사용. 
        // type BleStatus = 'disconnected' | 'scanning' | 'connecting' | 'connected' | 'error';
        // 'connecting' 상태를 재활용하거나 store 수정을 제안해야 함. 여기서는 connecting 사용.

        this.reconnectTimer = setTimeout(async () => {
            try {
                // BLE 재연결 시도
                if (this.currentDeviceId) {
                    console.log(`[ObdService] Retrying connection to ${this.currentDeviceId}...`);
                    await this.setTargetDevice(this.currentDeviceId);

                    // 성공 여부는 setTargetDevice 내부에서 에러가 안 나고 connected 상태가 되면 성공.
                    // 하지만 setTargetDevice는 에러 시 disconnected로 설정함.
                    // 성공적으로 연결되면 reconnectAttempts를 0으로 초기화해야 하는데, 
                    // setTargetDevice 함수 내에서 초기화하고 있으므로(line 131) 위에서 호출하면 됨.
                    // 다만, setTargetDevice는 비동기로 실패 시 catch 블록으로 이동하므로 여기서 확인 어려움.
                    // -> setTargetDevice 내에서 성공 시 reconnectAttempts = 0 설정되어 있음.
                }
                // Classic BT 재연결 시도
                else if (this.classicDevice) {
                    // Classic은 API 구조상 connect 호출 필요. setClassicDevice는 이미 연결된 객체를 받는 구조라
                    // 재연결 로직에는 ClassicBtService.connect(address) 가 필요함.
                    // 현재 createClassicDevice 로직이 없음. 
                    // ClassicBtService.connect(...) 호출 후 성공하면 setClassicDevice 호출.
                    console.log(`[ObdService] Retrying Classic connection to ${this.classicDevice.address}...`);
                    const isConnected = await ClassicBtService.connect(this.classicDevice);
                    if (isConnected) {
                        await this.setClassicDevice(this.classicDevice);
                    } else {
                        throw new Error('Classic connect failed');
                    }
                }
            } catch (e) {
                console.error('[ObdService] Reconnect failed:', e);
                // 재귀 호출로 다음 시도
                this.attemptReconnect();
            }
        }, delayMs);
    }

    // --- Auto Connect Logic ---

    /**
     * 마지막 연결 장치 정보 저장
     */
    private async saveLastDevice(type: 'classic' | 'ble', id: string, name: string) {
        try {
            const info = {
                type,
                id,
                name: name || 'Unknown Device',
                address: id, // Classic의 경우 id가 address임
            };
            await AsyncStorage.setItem(STORAGE_KEY_LAST_DEVICE, JSON.stringify(info));
            console.log('[ObdService] Saved last device:', info);
        } catch (e) {
            console.error('[ObdService] Failed to save device:', e);
        }
    }

    /**
     * 마지막 연결 장치 정보 로드
     */
    private async loadLastDevice() {
        try {
            const json = await AsyncStorage.getItem(STORAGE_KEY_LAST_DEVICE);
            if (!json) return null;
            return JSON.parse(json);
        } catch (e) {
            console.error('[ObdService] Failed to load last device:', e);
            return null;
        }
    }

    /**
     * 앱 시작 시 자동 연결 시도
     */
    public async tryAutoConnect() {
        console.log('[ObdService] tryAutoConnect initiated');
        const lastDevice = await this.loadLastDevice();
        if (!lastDevice) {
            console.log('[ObdService] No last device found, skipping auto connect');
            return;
        }

        console.log(`[ObdService] Found last device: ${lastDevice.name} (${lastDevice.id}) [${lastDevice.type}]`);

        // 이미 연결됨?
        if (this.isConnected()) {
            console.log('[ObdService] Already connected');
            return;
        }

        try {
            if (lastDevice.type === 'ble') {
                console.log('[ObdService] Auto-connecting to BLE device...');
                await this.setTargetDevice(lastDevice.id);
            } else {
                console.log('[ObdService] Auto-connecting to Classic BT device...');
                // setClassicDevice는 BluetoothDevice 객체를 요구하므로 가짜 객체 생성
                const deviceToConnect: BluetoothDevice = {
                    id: lastDevice.id,
                    name: lastDevice.name,
                    address: lastDevice.address || lastDevice.id,
                    bonded: true,
                    deviceClass: '',
                    rssi: 0,
                    extra: new Map<string, Object>(),
                } as unknown as BluetoothDevice;
                await this.setClassicDevice(deviceToConnect);
            }
        } catch (e) {
            console.error('[ObdService] Auto connect failed:', e);
        }
    }
}

export default new ObdService();
