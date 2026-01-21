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
    }

    // ===== Classic Bluetooth 설정 =====
    async setClassicDevice(device: BluetoothDevice) {
        this.connectionType = 'classic';
        this.classicDevice = device;
        this.currentData = { timestamp: new Date().toISOString() };
        this.isPolling = false;

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
    }

    // ===== BLE 설정 =====
    async setTargetDevice(deviceId: string) {
        this.connectionType = 'ble';
        this.currentDeviceId = deviceId;
        this.currentData = { timestamp: new Date().toISOString() };
        this.isPolling = false;

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
                await this.initializeElm327();
            } else {
                console.warn('[ObdService] Could not find OBD characteristics');
            }

        } catch (e) {
            console.error('[ObdService] Failed to configure BLE device', e);
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
        this.pollingLoop(intervalMs);
    }

    stopPolling() {
        this.isPolling = false;
        this.commandQueue = [];
        this.isProcessingQueue = false;
        console.log('[ObdService] Polling stopped');
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
        this.dataBuffer.push(data);
        console.log(`[ObdService] Data buffered: ${this.dataBuffer.length}/${this.BATCH_SIZE}`);

        if (this.dataBuffer.length >= this.BATCH_SIZE) {
            this.uploadBatch();
        }
    }

    // ===== 배치 업로드 실행 =====
    private async uploadBatch() {
        if (!this.vehicleId || this.dataBuffer.length === 0) {
            console.warn('[ObdService] Cannot upload: no vehicleId or empty buffer');
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

        try {
            console.log(`[ObdService] Uploading batch: ${logs.length} items`);
            await uploadObdBatch(logs);
            console.log('[ObdService] Batch upload successful!');
            this.dataBuffer = []; // 성공 시 버퍼 비우기
        } catch (error) {
            console.error('[ObdService] Batch upload failed:', error);
            // 실패 시 버퍼 유지 (다음 시도에서 재전송)
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
        console.log('[ObdService] Disconnected');
    }
}

export default new ObdService();
