import { NativeEventEmitter, NativeModules, Platform } from 'react-native';
import type { BluetoothDevice } from 'react-native-bluetooth-classic';
let BleManager: any;

if (Platform.OS !== 'web') {
    BleManager = require('react-native-ble-manager').default;
}
import BleService from './BleService';
import ClassicBtService from './ClassicBtService';
import { OBD_PIDS, parseObdResponse, PidDefinition } from './ObdPidHelper';
import { uploadObdBatch, ObdLogRequest, ObdBatchRequest } from '../api/obdApi';
import { sendDtcReport, sendDtcBatchReport } from '../api/aiApi';
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

export type ObdQualityStatus = 'OK' | 'STALE' | 'DISCONNECTED' | 'UNSUPPORTED' | 'PARSE_ERROR';

/** [10단계] 주행 종료 감지 상태 */
export type TripState = 'RUNNING' | 'SUSPECT_END' | 'ENDED';
export type SuspectReason = 'IDLE' | 'DISCONNECT';

export interface ObdData {
    timestamp: string;
    rpm?: number;
    speed?: number;
    voltage?: number;
    coolant_temp?: number;
    engine_load?: number;
    fuel_trim_short?: number;
    fuel_trim_long?: number;
    // 신규 확장 필드
    throttle?: number;
    intake_temp?: number;
    map?: number;
    maf?: number;
    dtc_status?: string;
    engine_runtime?: number;
    // 품질 메타데이터
    status?: ObdQualityStatus;
    stale_pids?: string[];
}

type ConnectionType = 'ble' | 'classic' | null;

/**
 * 큐 우선순위 정의 (4단계)
 * 낮은 숫자 = 높은 우선순위
 */
enum QueuePriority {
    HIGH = 1,      // 긴급 (DTC 상세 수집 등)
    NORMAL = 2,    // 일반 텔레메트리
    LOW = 3        // 저우선순위 (향후 확장용)
}

/**
 * 우선순위 큐 아이템 인터페이스 (4단계)
 */
interface PriorityQueueItem {
    pid: PidDefinition;
    priority: QueuePriority;
}

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

    // Command Queue (4단계: 우선순위 기반)
    private commandQueue: PriorityQueueItem[] = [];
    private isProcessingQueue = false;
    private currentPid: PidDefinition | null = null;
    private responseBuffer = '';

    // Observers
    private listeners: ((data: ObdData) => void)[] = [];

    // Current Snapshot
    private currentData: ObdData = { timestamp: new Date().toISOString() };
    private vin: string | null = null;
    private lastDtcCodes: string = '';
    private lastFreezeDtc: string = '';

    // 4.5 ~ 6단계: 타이밍 및 수집 제어
    private lastDtcStatusEnqueueAt: number = 0;
    private lastDtcReportAt: number = 0;
    /** 직전 01 01 응답에서의 DTC 개수 (0 -> N 변화 감지용) */
    private previousDtcCount: number = 0;
    private isReportingDtc: boolean = false;
    private normalPidIndex: number = 0; // 6단계: 인터리빙용 인덱스
    private samplingTimer: ReturnType<typeof setTimeout> | null = null; // 6단계: 정기 샘플링 타이머

    // 7단계: 데이터 고착 방지 (Freshness Check)
    private lastUpdatedAt: Map<string, number> = new Map(); // 각 필드의 마지막 업데이트 시각

    // 9단계 보강: 정밀 지터 측정
    private lastSnapshotTs: number = 0;
    private maxDriftMs: number = 0;
    private driftCheckCount: number = 0;

    // ===== 배치 업로드 관련 =====
    private dataBuffer: ObdData[] = [];
    private vehicleId: string | null = null;
    private readonly BATCH_SIZE = 180; // 3분 (180초)
    private readonly BUFFER_RECOVERY_KEY = 'obd_buffer_recovery';

    // [10단계] 주행 종료 자동 감지 상태 머신
    private tripState: TripState = 'RUNNING';
    private suspectReason: SuspectReason | null = null;
    private suspectStartedAt: number = 0;
    private isEndingTrip: boolean = false;
    private ignoreResponses: boolean = false;

    // [10단계] 연속 관측 카운터
    private idleCount: number = 0; // RPM=0 && Speed=0 연속 카운트 (초)
    private disconnectCount: number = 0; // highAgeMs > 3000 연속 카운트 (틱)

    // [10단계] Grace Period
    private readonly GRACE_PERIOD_IDLE_MS = 60000; // 60초
    private readonly GRACE_PERIOD_DISCONNECT_MS = 30000; // 30초

    // [11단계] PID 실패 관리 (Stability)
    private pidFailCount: Map<string, number> = new Map(); // mode:pid -> 실패 카운트
    private disabledPids: Set<string> = new Set(); // 비활성화된 PID 목록
    private readonly MAX_PID_FAIL_COUNT = 5; // 5회 연속 실패 시 비활성화

    // [11단계] 업로드 동시 실행 방지 (Concurrency)
    private isUploading: boolean = false;

    // [11단계 개선] 오프라인 큐 처리 동시성 제어
    private isProcessingOfflineQueue: boolean = false;

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

        // [9단계] 데이터 복구 로직 실행
        this.loadRecoveredBuffer();

        // [9단계] 앱 종료/비활성 시 안전망 (JS 수준)
        // onTaskRemoved는 네이티브 구현이 필요하지만, JS에서는 AppState로 보조
        if (Platform.OS !== 'web') {
            const { AppState } = require('react-native');
            AppState.addEventListener('change', (nextAppState: string) => {
                if (nextAppState === 'background') {
                    console.log('[ObdService] App went to background, ensuring background service is active');
                }
            });
        }
    }

    /**
     * [11단계 개선] 연결 상태 클린업 함수 (단일화)
     * 구독 해제, 타이머 클리어, 폴링 플래그 리셋 등을 통합 관리
     */
    private cleanupConnectionState() {
        // 구독 해제
        if (this.classicDataSubscription) {
            this.classicDataSubscription.remove();
            this.classicDataSubscription = null;
        }

        // 타이머 클리어
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.samplingTimer) {
            clearTimeout(this.samplingTimer);
            this.samplingTimer = null;
        }

        // 폴링 플래그 리셋
        this.isPolling = false;
        this.isProcessingQueue = false;
    }

    // ===== Classic Bluetooth 설정 =====
    async setClassicDevice(device: BluetoothDevice) {
        // [11단계 개선] 멱등성 보장: 동일 디바이스 재설정 시 no-op
        if (this.connectionType === 'classic' && this.classicDevice?.address === device.address) {
            console.log('[ObdService] Classic BT device already set, skipping');
            return;
        }

        // [11단계 개선] 기존 연결 상태 클린업
        this.cleanupConnectionState();

        this.connectionType = 'classic';
        this.classicDevice = device;
        this.currentData = { timestamp: new Date().toISOString() };
        this.isDisconnectRequested = false;
        this.reconnectAttempts = 0;
        useBleStore.getState().setConnectedDeviceName(device.name || 'Classic Device');
        useBleStore.getState().setConnectedDevice(device.address);
        useBleStore.getState().setConnectedDevice(device.address);
        useBleStore.getState().setStatus('connected');

        // Save for auto-connect
        this.saveLastDevice('classic', device.address, device.name || 'Classic Device');

        console.log(`[ObdService] Classic BT device set: ${device.name}`);

        // [추가] Classic BT 연결 시에도 ELM327 초기화 수행 (VIN 수집 등 시작)
        this.initializeElm327();

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

        // [11단계 개선] 멱등성 보장: 동일 디바이스 재설정 시 no-op
        if (this.connectionType === 'ble' && this.currentDeviceId === deviceId) {
            console.log('[ObdService] BLE device already set, skipping');
            return;
        }

        // [11단계 개선] 기존 연결 상태 클린업
        this.cleanupConnectionState();

        this.connectionType = 'ble';
        this.currentDeviceId = deviceId;
        this.currentData = { timestamp: new Date().toISOString() };
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
        console.log('[ObdService] Initializing ELM327 with optimizations...');

        const initCommands = [
            'ATZ',      // 로컬 리셋
            'ATE0',     // 에코 오프
            'ATL0',     // 줄바꿈 오프
            'ATS0',     // 공백 제거 (속도 향상)
            'ATH0',     // 헤더 오프
            'ATAT1',    // Adaptive Timing Level 1 (응답 속도 자동 최적화)
            //'ATST32',   // Timeout 설정 (~200ms, 기본값보다 타이트하게 설정하여 지연 방지)
            'ATCAF0',   // CAN Auto Filtering Off (처리 속도 향상)
            'ATSP0',    // 프로토콜 자동 감지
        ];

        for (const cmd of initCommands) {
            const success = await this.sendCommand(cmd);
            if (!success) console.warn(`[ObdService] Init command failed: ${cmd}`);
            await this.delay(150); // 초기화 안정성을 위한 짧은 대기
        }

        console.log('[ObdService] ELM327 optimization sequences completed');

        // [추가] 초기화 완료 후 VIN 요청 (Mode 09 02)
        this.enqueue(OBD_PIDS.VIN, QueuePriority.NORMAL);
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

        // [10단계] 상태 머신 초기화
        this.tripState = 'RUNNING';
        this.suspectReason = null;
        this.suspectStartedAt = 0;
        this.isEndingTrip = false;
        this.ignoreResponses = false;
        this.idleCount = 0;
        this.disconnectCount = 0;
        console.log('[TripStateChange] RUNNING (trip started)');

        // [11단계] PID 실패 관리 초기화 (A안: 주행 종료 시 리셋)
        this.pidFailCount.clear();
        this.disabledPids.clear();
        this.isUploading = false; // [11단계] 업로드 상태 초기화
        console.log('[ObdService] PID failure tracking & upload status reset');

        useBleStore.getState().setPolling(true);
        this.pollingLoop(intervalMs);
        this.samplingLoop(1000); // 6단계: 1초 고정 샘플링 시작

        // [Auto Trip] 주행 시작 (Trip ID 발급)
        if (this.vehicleId) {
            console.log('[ObdService] Auto-starting trip for vehicle:', this.vehicleId);
            useTripStore.getState().startTrip(this.vehicleId);
        } else {
            console.warn('[ObdService] Cannot auto-start trip: Vehicle ID not set');
        }

        // 안드로이드 백그라운드 서비스 시작
        if (Platform.OS === 'android') {
            (async () => {
                try {
                    // [9단계] Android 13+ 알림 권한 체크 (거부 시 중단)
                    if (Platform.Version >= 33) {
                        const { PermissionsAndroid, Alert } = require('react-native');
                        const hasPermission = await PermissionsAndroid.check('android.permission.POST_NOTIFICATIONS');
                        if (!hasPermission) {
                            const result = await PermissionsAndroid.request('android.permission.POST_NOTIFICATIONS');
                            if (result !== 'granted') {
                                Alert.alert("알림 권한 필요", "백그라운드 수집을 위해 알림 권한이 반드시 필요합니다.");
                                this.stopPolling();
                                /*
                                ## 구현 (Execution)
                                - [x] Phase 1: 주행 시작 시 Mode 09 02(VIN) 조회 및 처리 로직 추가 `[x]`
                                - [x] Phase 2: Mode 03(DTC) 상세 수집 및 보고 로직 보강 `[x]`
                                - [x] Phase 3: PID 실패 카운팅 및 자동 비활성화 로직 최적화 `[x]`
                                - [x] Phase 4: 연결 상태 클린업 및 멱등성 보장 로직 검증 `[x]`

                                ## 검증 (Verification)
                                - [x] 실제 기기 또는 안드로이드 에뮬레이터 연동 테스트 `[x]`
                                - [x] 자동 주행 종료 및 오프라인 큐 처리 검증 `[x]`
                                - [x] 최종 결과 보고 및 워크스루 작성 `[x]`
                                */
                                return;
                            }
                        }
                    }

                    // [안전망] 이미 실행 중이면 중복 start 방지
                    if (BackgroundService.isActive()) {
                        console.log('[ObdService] Foreground Service already running');
                        return;
                    }

                    // [안전망] 서비스가 확실히 시작된 후에만 루프를 신뢰
                    await BackgroundService.start();
                    console.log('[ObdService] Foreground Service started successfully');
                } catch (e) {
                    console.error('[ObdService] Critical: Failed to start Foreground Service. Stopping collection.', e);
                    this.stopPolling(); // 서비스 시작 실패 시 수집 중단 (안전 우선)
                }
            })();
        }
    }

    /**
     * [10단계] 원자적 마감 루틴
     * 중복 호출 방지 및 응답 파편 차단 보장
     */
    async finalizeTrip() {
        // 중복 마감 방지
        if (this.tripState === 'ENDED' || this.isEndingTrip) {
            console.log('[ObdService] finalizeTrip: Already ending/ended, skipping');
            return;
        }

        this.isEndingTrip = true;
        this.tripState = 'ENDED';
        console.log('[TripStateChange] ENDED (finalizing)');

        try {
            // 1. [필수] 응답 파편 차단
            this.ignoreResponses = true;

            // 2. 폴링 중단
            this.isPolling = false;
            this.commandQueue = [];
            this.isProcessingQueue = false;
            this.currentPid = null;

            if (this.samplingTimer) {
                clearTimeout(this.samplingTimer);
                this.samplingTimer = null;
            }
            useBleStore.getState().setPolling(false);

            // 3. 버퍼 플러시 (비동기 업로드 대기 안 함)
            console.log('[TripFinalize] Flushing buffer...');
            await this.flushBuffer();

            // 4. 주행 종료 (서버 포함과 무관하게 상태 ENDED 유지)
            console.log('[TripFinalize] Ending trip...');
            const tripId = useTripStore.getState().currentTripId; // Trip ID 미리 캡처
            try {
                await useTripStore.getState().endTrip();
                console.log('[TripFinalize] endTrip=ok');
            } catch (e) {
                console.error('[TripFinalize] endTrip=fail, queuing to OfflineStorage', e);
                // [10단계 보강] 서버 종료 실패 시 캡처된 tripId 사용
                if (tripId) {
                    const url = `/api/v1/trips/${tripId}/end`;
                    const isQueued = await OfflineStorage.isUrlQueued(url);
                    if (!isQueued) {
                        await OfflineStorage.addToQueue({
                            url: url,
                            method: 'POST',
                            timestamp: Date.now(),
                            body: JSON.stringify({ endTime: new Date().toISOString() })
                        });
                        console.log(`[TripFinalize] Trip end event queued for ${tripId}`);
                    } else {
                        console.log(`[TripFinalize] Trip end event already queued for ${tripId}, skipping`);
                    }
                }
            }

            // 5. Foreground Service 중단
            if (Platform.OS === 'android') {
                BackgroundService.stop();
            }

            console.log('[TripFinalize] Trip finalized successfully');
        } catch (e) {
            console.error('[TripFinalize] Error during finalization', e);
        } finally {
            this.isEndingTrip = false;
        }
    }

    async stopPolling() {
        // 사용자가 수동으로 중지할 때도 마감 루틴 사용
        await this.finalizeTrip();
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


    /**
     * 폴링 루프 시작
     * @param intervalMs 폴링 간격 (1000ms 권장)
     */
    private pollingLoop(intervalMs: number) {
        if (!this.isPolling) return;

        // 5-6단계: PID 그룹화 및 순환 인터리빙
        const highPids = [
            OBD_PIDS.RPM,
            OBD_PIDS.SPEED,
            OBD_PIDS.THROTTLE
        ];

        const normalPids = [
            OBD_PIDS.ENGINE_LOAD,
            OBD_PIDS.MAP,
            OBD_PIDS.MAF,
            OBD_PIDS.COOLANT_TEMP,
            OBD_PIDS.INTAKE_TEMP,
            OBD_PIDS.ENGINE_RUNTIME,
            OBD_PIDS.DTC_STATUS // [추가] 실시간 고장 유무 감시
        ];

        // 1. HIGH 그룹전체는 매 주기에 추가 (최신성 보장)
        // 4.5단계에서 구현된 중복 체크 로직에 의해 큐에 이미 있으면 추가되지 않음 (Backpressure)
        // [11단계] 비활성화된 PID는 제외
        highPids.forEach(pid => {
            const key = `${pid.mode}:${pid.pid}`;
            if (!this.disabledPids.has(key)) {
                this.enqueue(pid, QueuePriority.NORMAL);
            }
        });

        // 2. NORMAL 그룹은 매 주기마다 '하나씩' 돌아가며 추가 (인터리빙)
        // 이 방식은 큐가 비대해지는 것을 막으면서 모든 데이터의 수집을 보장함 (Starvation 방지)
        // [11단계] 비활성화된 PID는 제외
        if (normalPids.length > 0) {
            const pid = normalPids[this.normalPidIndex];
            const key = `${pid.mode}:${pid.pid}`;
            if (!this.disabledPids.has(key)) {
                this.enqueue(pid, QueuePriority.LOW); // 일반 데이터는 낮은 우선순위로
            }
            this.normalPidIndex = (this.normalPidIndex + 1) % normalPids.length;
        }

        // 3. DTC 상태 체크 (5초 주기)
        const now = Date.now();
        if (now - this.lastDtcStatusEnqueueAt >= 5000) {
            this.enqueue(OBD_PIDS.DTC_STATUS, QueuePriority.NORMAL);
            this.lastDtcStatusEnqueueAt = now;
        }

        setTimeout(() => this.pollingLoop(intervalMs), intervalMs);
    }

    /**
     * 6단계: 1초 정기 샘플링 루프
     * 수집 속도와 관계없이 정확히 1Hz로 데이터 스냅샷을 생성합니다.
     */
    private samplingLoop(intervalMs: number = 1000) {
        if (!this.isPolling) return;

        // 7단계: Freshness Check를 적용한 스냅샷 생성
        const now = Date.now();
        const snapshot: ObdData = { timestamp: new Date().toISOString() };

        // 각 필드별 신선도 체크 (Implementation Plan 기준)
        const freshnessThresholds: Record<string, number> = {
            // HIGH: 3초 이내 (실시간성 중요)
            'rpm': 3000,
            'speed': 3000,
            'throttle': 3000,
            // NORMAL/MID: 10초 이내
            'engine_load': 10000,
            'map': 10000,
            'maf': 10000,
            'intake_temp': 10000,
            'engine_runtime': 10000,
            'dtc_status': 10000, // DTC는 MID로 상향 조정 (지적사항 반영)
            // LOW: 30초 이내 (느리게 변하는 데이터)
            'coolant_temp': 30000,
            'voltage': 30000
        };

        // 각 필드별로 신선도 체크 후 스냅샷에 추가
        Object.keys(this.currentData).forEach(key => {
            if (key === 'timestamp') return;

            const lastUpdate = this.lastUpdatedAt.get(key);
            const threshold = freshnessThresholds[key] || 10000; // 기본 10초

            // 마지막 업데이트가 없거나 임계값을 초과한 경우 null 처리
            if (!lastUpdate || (now - lastUpdate) > threshold) {
                (snapshot as any)[key] = null;
            } else {
                (snapshot as any)[key] = this.currentData[key as keyof ObdData];
            }
        });

        // 데이터 기록 및 알림
        this.notifyListeners(snapshot);
        this.collectData(snapshot);

        // [9단계] 정밀 드리프트 측정
        if (this.lastSnapshotTs > 0) {
            const expectedInterval = intervalMs;
            const actualInterval = now - this.lastSnapshotTs;
            const driftMs = Math.abs(actualInterval - expectedInterval);
            this.maxDriftMs = Math.max(this.maxDriftMs, driftMs);
            this.driftCheckCount++;
            if (this.driftCheckCount >= 60) {
                console.log(`[ObdService] Sampling drift (60s window): max=${this.maxDriftMs}ms`);
                this.maxDriftMs = 0;
                this.driftCheckCount = 0;
            }
        }
        this.lastSnapshotTs = now;

        this.samplingTimer = setTimeout(() => this.samplingLoop(intervalMs), intervalMs);

        // [10단계] 주행 종료 자동 감지 로직 구동
        this.checkTripTermination(snapshot, now);
    }

    /**
     * [10단계] 주행 종료 상태 머신 체크
     */
    private checkTripTermination(snapshot: ObdData, now: number) {
        if (!this.isPolling || this.isEndingTrip) return;

        // highAgeMs 계산: RPM 또는 Speed 중 최근 갱신 기준
        const rpmTs = this.lastUpdatedAt.get('rpm') || 0;
        const speedTs = this.lastUpdatedAt.get('speed') || 0;
        const lastHighUpdatedAt = Math.max(rpmTs, speedTs);
        const highAgeMs = now - lastHighUpdatedAt;

        const isRpmZero = snapshot.rpm !== undefined && snapshot.rpm === 0;
        const isSpeedZero = snapshot.speed !== undefined && snapshot.speed === 0;

        if (this.tripState === 'RUNNING') {
            // Case A (IDLE): RPM=0 && Speed=0 연속 5초
            if (isRpmZero && isSpeedZero) {
                this.idleCount++;
                if (this.idleCount >= 5) {
                    console.log(`[TripStateChange] RUNNING -> SUSPECT_END (reason=IDLE, ts=${now})`);
                    this.tripState = 'SUSPECT_END';
                    this.suspectReason = 'IDLE';
                    this.suspectStartedAt = now;
                }
            } else {
                this.idleCount = 0; // 리셋
            }

            // Case B (DISCONNECT): highAgeMs > 3000ms 연속 3회
            if (highAgeMs > 3000) {
                this.disconnectCount++;
                if (this.disconnectCount >= 3) {
                    console.log(`[TripStateChange] RUNNING -> SUSPECT_END (reason=DISCONNECT, highAgeMs=${highAgeMs})`);
                    this.tripState = 'SUSPECT_END';
                    this.suspectReason = 'DISCONNECT';
                    this.suspectStartedAt = now;
                }
            } else {
                this.disconnectCount = 0; // 리셋
            }
        }
        else if (this.tripState === 'SUSPECT_END') {
            // 복귀 조건: rpm > 0 또는 speed > 0 또는 업데이트 재개
            const isActuallyActive = (snapshot.rpm !== undefined && snapshot.rpm > 0) ||
                (snapshot.speed !== undefined && snapshot.speed > 0) ||
                (highAgeMs <= 1000);

            if (isActuallyActive) {
                console.log(`[TripStateChange] SUSPECT_END -> RUNNING (activity detected, rpm=${snapshot.rpm}, speed=${snapshot.speed}, highAgeMs=${Math.floor(highAgeMs)})`);
                this.tripState = 'RUNNING';
                this.suspectReason = null;
                this.suspectStartedAt = 0;
                this.idleCount = 0;
                this.disconnectCount = 0;
            } else {
                // Grace Period 경과 체크
                const elapsedSinceSuspect = now - this.suspectStartedAt;
                const gracePeriod = this.suspectReason === 'IDLE' ?
                    this.GRACE_PERIOD_IDLE_MS : this.GRACE_PERIOD_DISCONNECT_MS;

                if (elapsedSinceSuspect >= gracePeriod) {
                    console.warn(`[TripStateChange] SUSPECT_END -> ENDED (reason=${this.suspectReason}, elapsed=${Math.floor(elapsedSinceSuspect / 1000)}s)`);
                    this.finalizeTrip();
                } else {
                    // 매 15초마다 경과 로그
                    const elapsedSec = Math.floor(elapsedSinceSuspect / 1000);
                    if (elapsedSec > 0 && elapsedSec % 15 === 0) {
                        console.log(`[SuspectTick] reason=${this.suspectReason}, elapsed=${elapsedSec}s, rpm=${snapshot.rpm}, speed=${snapshot.speed}, highAge=${Math.floor(highAgeMs)}ms`);
                    }
                }
            }
        }
    }

    /**
     * PID를 우선순위와 함께 큐에 추가 (4단계)
     * @param pid 실행할 PID 정의
     * @param priority 우선순위 (기본값: NORMAL)
     */
    private enqueue(pid: PidDefinition, priority: QueuePriority = QueuePriority.NORMAL) {
        // 4.5단계: mode:pid 조합으로 중복 체크 (더 정확)
        const key = `${pid.mode}:${pid.pid}`;
        if (priority >= QueuePriority.NORMAL && this.commandQueue.some(item => `${item.pid.mode}:${item.pid.pid}` === key)) {
            return;
        }

        // 4.5단계: sort() 대신 삽입 위치 찾아 끼워넣기 (성능 개선)
        const newItem = { pid, priority };
        let insertIndex = this.commandQueue.findIndex(item => item.priority > priority);
        if (insertIndex === -1) {
            // 모든 항목보다 낮은 우선순위 → 맨 뒤에 추가
            this.commandQueue.push(newItem);
        } else {
            // 찾은 위치에 끼워넣기
            this.commandQueue.splice(insertIndex, 0, newItem);
        }

        this.processQueue();
    }

    private async processQueue() {
        if (this.isProcessingQueue || this.commandQueue.length === 0) return;

        this.isProcessingQueue = true;

        try {
            while (this.commandQueue.length > 0 && this.isPolling) {
                const item = this.commandQueue.shift();
                if (!item) break;

                const pid = item.pid;

                this.currentPid = pid;
                this.responseBuffer = '';

                const command = `${pid.mode}${pid.pid}`;
                // console.log(`[ObdService] Sending: ${command}`);

                const success = await this.sendCommand(command);
                if (!success) {
                    // [11단계] sendCommand 실패 캘운팅
                    this.incrementPidFailCount(pid, 'sendCommand failed');
                    this.currentPid = null;
                    continue;
                }

                // 응답 처리 대기
                if (this.connectionType === 'classic' && this.classicDevice) {
                    await this.delay(200);
                    const response = await ClassicBtService.readAvailable(this.classicDevice);
                    if (response) this.handleResponse(response);
                } else {
                    // BLE는 핸들러(onDataReceived)에서 handleResponse 호출
                    let timeout = 0;
                    while (this.currentPid !== null && timeout < 20) {
                        await this.delay(50);
                        timeout++;
                    }
                    // [11단계] 타임아웃 발생 시 실패 처리
                    if (this.currentPid !== null) {
                        this.incrementPidFailCount(pid, 'response timeout');
                        this.currentPid = null;
                    }
                }
            }
        } finally {
            this.isProcessingQueue = false;
            // 6단계: 기록 로직이 samplingLoop로 이동됨
        }
    }

    // ===== 응답 처리 =====
    private async handleResponse(responseStr: string) {
        // [10단계] 마감 중 응답 파편 차단
        if (this.ignoreResponses) {
            return;
        }

        if (!responseStr || !this.currentPid) return;

        this.responseBuffer += responseStr;

        // 완전한 응답인지 확인 (> 포함 시 ELM327 응답 완료)
        if (!this.responseBuffer.includes('>')) return;

        const result = parseObdResponse(this.responseBuffer, this.currentPid);
        const pidKey = `${this.currentPid.mode}:${this.currentPid.pid}`;

        // [11단계] 실패 감지: NO DATA, ?, 빈 응답, 파싱 null
        const cleanResp = this.responseBuffer.trim().toUpperCase();
        if (cleanResp.includes('NO DATA') || cleanResp.includes('?') || cleanResp === '>' || result === null) {
            const reason = cleanResp.includes('NO DATA') ? 'NO DATA' :
                cleanResp.includes('?') ? 'unknown error (?)' :
                    cleanResp === '>' ? 'empty response' : 'parse failed';
            this.incrementPidFailCount(this.currentPid, reason);
            this.currentPid = null;
            this.responseBuffer = '';
            return;
        }

        // [11단계] 성공적으로 파싱되면 실패 카운트 리셋
        this.resetPidFailCount(pidKey);

        if (result !== null) {
            // Mode + PID 조합으로 구분 (예: "010C", "03", "020200")
            const key = this.currentPid.mode + this.currentPid.pid;

            switch (key) {
                // Mode 01: Real-time Data (7단계 보강: updateData 유틸리티 사용)
                case '010C': this.updateData('rpm', result); break;
                case '010D': this.updateData('speed', result); break;
                case '0104': this.updateData('engine_load', result); break;
                case '0105': this.updateData('coolant_temp', result); break;
                case '0142': this.updateData('voltage', result); break;
                case '0111': this.updateData('throttle', result); break;
                case '010F': this.updateData('intake_temp', result); break;
                case '010B': this.updateData('map', result); break;
                case '0110': this.updateData('maf', result); break;
                case '011F': this.updateData('engine_runtime', result); break;
                case '0101':
                    this.updateData('dtc_status', result);
                    // 01 01: DTC 개수 파싱 후 0 -> N(>0)으로 변할 때만 상세 수집 시작
                    try {
                        const text = result.toString();
                        const match = text.match(/(\d+)\s*DTCs?/i);
                        const currentCount = match ? parseInt(match[1], 10) : 0;
                        if (Number.isNaN(currentCount)) {
                            console.warn('[ObdService] Failed to parse DTC count from status:', text);
                        } else {
                            if (this.previousDtcCount === 0 && currentCount > 0) {
                                console.warn('[ObdService] DTC edge detected (0 ->', currentCount, '), collecting details...');
                                this.reportDetailedDtc(text);
                            }
                            this.previousDtcCount = currentCount;
                        }
                    } catch (e) {
                        console.error('[ObdService] Error while handling DTC_STATUS:', e);
                    }
                    break;

                // Mode 03: Stored DTCs
                case '03':
                    console.log(`[ObdService] Mode 03 response: ${result}`);
                    this.lastDtcCodes = result as string;
                    break;

                case '020200':
                    console.log(`[ObdService] Mode 02 response: ${result}`);
                    this.lastFreezeDtc = result as string;
                    break;

                // Mode 09 02: VIN
                case '0902':
                    console.log(`[ObdService] Mode 09 02 response (VIN): ${result}`);
                    this.vin = result as string;
                    // VIN이 확보되면 차량 이미지 연동 등에 활용 가능 (추후 확장)
                    break;
            }
        }

        this.currentPid = null;
        this.responseBuffer = '';
    }

    /**
     * DTC 상세 수집 및 백엔드 보고 (배치 전송 방식으로 전환)
     */
    private async reportDetailedDtc(statusSummary: string) {
        if (this.isReportingDtc) return;
        this.isReportingDtc = true;

        console.log('[ObdService] Starting detailed DTC batch collection...');

        try {
            // 1. 상세 데이터 수집 (Mode 03, 02)
            this.lastDtcCodes = '';
            this.lastFreezeDtc = '';

            // 높은 우선순위로 큐에 추가
            this.enqueue(OBD_PIDS.GET_DTCS, QueuePriority.HIGH);
            this.enqueue(OBD_PIDS.FREEZE_DTC, QueuePriority.HIGH);

            // 데이터 수집 대기 (최대 5초 - 사용자 요구사항)
            let waitCount = 0;
            const MAX_WAIT = 50; // 100ms * 50 = 5s

            while (waitCount < MAX_WAIT) {
                // 두 데이터가 모두 왔거나, 최소한 하나라도 왔는지 체크 (설계에 따라 조정 가능)
                // 여기서는 5초를 꽉 채우거나 두 데이터가 모두 올 때까지 대기
                if (this.lastDtcCodes && this.lastFreezeDtc) {
                    console.log('[ObdService] Both DTC and Freeze DTC collected');
                    break;
                }

                await this.delay(100);
                waitCount++;
            }

            if (!this.lastDtcCodes && !this.lastFreezeDtc) {
                console.log('[ObdService] No DTC data collected within 5s');
                return;
            }

            // 2. 배치 데이터 구성
            const dtcs: { code: string; type: string; status: string }[] = [];

            // Mode 03 (Stored DTCs) 파싱
            if (this.lastDtcCodes) {
                const codes = this.lastDtcCodes.split(',').map(c => c.trim()).filter(c => c && c !== 'P0000');
                codes.forEach(code => {
                    dtcs.push({ code, type: 'STORED', status: 'ACTIVE' });
                });
            }

            // Mode 02 (Freeze Frame DTC) 추가 및 중복 제거
            if (this.lastFreezeDtc && this.lastFreezeDtc !== 'P0000') {
                if (!dtcs.some(d => d.code === this.lastFreezeDtc)) {
                    dtcs.push({ code: this.lastFreezeDtc, type: 'FREEZE_FRAME', status: 'ACTIVE' });
                }
            }

            if (dtcs.length === 0) {
                console.log('[ObdService] No valid DTC codes to report after filtering');
                return;
            }

            // 3. 통합 배치 리포트 전송
            const vehicleId = this.vehicleId;
            if (!vehicleId) {
                console.error('[ObdService] Cannot report DTC: vehicleId is missing');
                return;
            }

            await sendDtcBatchReport({
                vehicleId: vehicleId,
                dtcs: dtcs,
                freezeFrame: {
                    rpm: this.currentData.rpm,
                    speed: this.currentData.speed,
                    coolantTemp: this.currentData.coolant_temp,
                    engineLoad: this.currentData.engine_load,
                    pidsSnapshot: JSON.stringify(this.currentData)
                }
            });

            console.log(`[ObdService] DTC Batch Report sent successfully (${dtcs.length} codes)`);
            this.lastDtcReportAt = Date.now();

        } catch (error) {
            console.error('[ObdService] Failed to send detailed DTC batch report:', error);
        } finally {
            this.isReportingDtc = false;
        }
    }

    // ===== 유틸리티 =====
    /**
     * 데이터를 업데이트하고 타임스탬프를 기록 (7단계 보강)
     */
    private updateData(key: keyof ObdData, value: any) {
        if (value === null || value === undefined) return;
        (this.currentData as any)[key] = value;
        this.lastUpdatedAt.set(key, Date.now());
    }

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

    /**
     * [11단계] PID 실패 카운트 증가 및 비활성화 처리
     */
    private incrementPidFailCount(pid: PidDefinition, reason: string) {
        const key = `${pid.mode}:${pid.pid}`;

        // [11단계 피드백] RPM/Speed (High PIDs)는 비활성화 대상에서 제외
        // 이유: 상태 머신(주행 종료 감지)의 핵심 지표이므로 통신이 불안정해도 계속 시도해야 함
        if (key === '01:0C' || key === '01:0D') {
            console.warn(`[PidFailIgnore] key=${key} failed but skipping disable (High PID) reason=${reason}`);
            return;
        }

        const currentCount = (this.pidFailCount.get(key) || 0) + 1;
        this.pidFailCount.set(key, currentCount);

        if (currentCount >= this.MAX_PID_FAIL_COUNT) {
            this.disabledPids.add(key);
            console.warn(`[PidDisabled] key=${key} failCount=${currentCount} reason=${reason}`);
        } else {
            console.log(`[PidFail] key=${key} failCount=${currentCount} reason=${reason}`);
        }
    }

    /**
     * [11단계] PID 실패 카운트 리셋 (성공 시)
     */
    private resetPidFailCount(pidKey: string) {
        if (this.pidFailCount.has(pidKey)) {
            this.pidFailCount.set(pidKey, 0);
        }
    }

    getCurrentData(): ObdData {
        return { ...this.currentData };
    }

    setVehicleId(id: string) {
        this.vehicleId = id;
    }

    private collectData(data: ObdData) {
        // 안전 장치: 버퍼가 비정상적으로 커지면 정리
        if (this.dataBuffer.length >= 1000) {
            console.warn('[ObdService] Buffer overflow, clearing...');
            this.dataBuffer = [];
        }

        this.dataBuffer.push(data);

        // [9단계] 주기적 버퍼 임시 저장 (안전망: 강제 종료 대비)
        if (this.dataBuffer.length % 10 === 0) {
            this.saveBufferForRecovery();
        }

        // 배치 사이즈 도달 시 업로드 실행
        if (this.dataBuffer.length >= this.BATCH_SIZE) {
            // 8단계: 버퍼 스와핑 (데이터 누락 방지)
            const logsToUpload = [...this.dataBuffer];
            this.dataBuffer = [];
            this.clearRecoveredBuffer(); // 업로드 시작 시 임시 버퍼 소거
            this.uploadBatch(logsToUpload);
        }
    }

    /**
     * [9단계] 강제 종료 대비 버퍼 임시 저장 (복사본 저장 및 메타데이터 포함)
     */
    private async saveBufferForRecovery() {
        try {
            if (this.dataBuffer.length > 0) {
                // 레이스 컨디션 방지를 위해 복사본([...]) 저장 및 메타데이터 추가
                const recoveryData = {
                    tripId: useTripStore.getState().currentTripId,
                    vehicleId: this.vehicleId,
                    lastSnapshotTs: Date.now(),
                    logs: [...this.dataBuffer]
                };
                await AsyncStorage.setItem(this.BUFFER_RECOVERY_KEY, JSON.stringify(recoveryData));
            }
        } catch (e) {
            console.error('[ObdService] Failed to save buffer for recovery', e);
        }
    }

    /**
     * [9단계] 임시 저장된 버퍼 복구
     */
    private async loadRecoveredBuffer() {
        try {
            const saved = await AsyncStorage.getItem(this.BUFFER_RECOVERY_KEY);
            if (saved) {
                const recoveryData = JSON.parse(saved);
                if (recoveryData && Array.isArray(recoveryData.logs) && recoveryData.logs.length > 0) {
                    console.log(`[ObdService] Recovered ${recoveryData.logs.length} logs (Trip: ${recoveryData.tripId}) from crash`);

                    // 기존 버퍼와 합칠 때 중복 방지 (간단히 덮어쓰거나 합치기)
                    // 여기서는 복구된 데이터를 기존 버퍼 앞에 배치 (순서 유지)
                    this.dataBuffer = [...recoveryData.logs, ...this.dataBuffer];

                    // 복구 성공 후 즉시 서버 idempotency 필터링을 타도록 flush 유도 가능
                    if (this.dataBuffer.length >= 10) {
                        this.saveBufferForRecovery(); // 현재 상태 다시 저장
                    }
                }
            }
        } catch (e) {
            console.error('[ObdService] Failed to load recovered buffer', e);
        }
    }

    /**
     * [9단계] 성공적인 배치 구성 시 임시 버퍼 소거
     */
    private async clearRecoveredBuffer() {
        try {
            await AsyncStorage.removeItem(this.BUFFER_RECOVERY_KEY);
        } catch (e) {
            console.error('[ObdService] Failed to clear recovered buffer', e);
        }
    }

    /**
     * 8단계: 배치 업로드 고도화
     * [11단계] 동시 실행 방지 및 Drain 로직 추가
     * 버퍼를 즉시 비우고 비동기로 서버에 전송합니다.
     */
    private async uploadBatch(logsToUpload: ObdData[]) {
        if (logsToUpload.length === 0 || !this.vehicleId) return;

        // [11단계] 동시 실행 방지
        if (this.isUploading) {
            console.log('[ObdService] Upload already in progress, skipping');
            return;
        }

        this.isUploading = true;

        try {
            // 8.5단계: batchId 생성 (차량ID + 타임스탬프 조합으로 중복 방지)
            const batchId = `batch-${this.vehicleId}-${Date.now()}`;
            console.log(`[ObdService] Preparing batch upload: ${batchId} (${logsToUpload.length} items)`);

            const logs: ObdLogRequest[] = logsToUpload.map(d => ({
                timestamp: d.timestamp,
                vehicleId: this.vehicleId!,
                rpm: d.rpm,
                speed: d.speed,
                voltage: d.voltage,
                coolantTemp: d.coolant_temp,
                engineLoad: d.engine_load,
                fuelTrimShort: d.fuel_trim_short,
                fuelTrimLong: d.fuel_trim_long,
                throttle: d.throttle,
                map: d.map,
                maf: d.maf,
                intakeTemp: d.intake_temp,
                engineRuntime: d.engine_runtime
            }));

            const batchRequest: ObdBatchRequest = {
                batchId,
                vehicleId: this.vehicleId,
                logs
            };

            if (!NetworkService.IsConnected) {
                console.log('[ObdService] Offline, saving to queue...');
                await OfflineStorage.addToQueue({
                    url: '/telemetry/batch',
                    method: 'POST',
                    body: JSON.stringify(batchRequest),
                    timestamp: Date.now()
                });
                return;
            }

            try {
                await uploadObdBatch(batchRequest);
                console.log(`[ObdService] Batch upload success: ${batchId}`);
            } catch (error) {
                console.error(`[ObdService] Batch upload failed (${batchId}), saving to offline queue:`, error);
                await OfflineStorage.addToQueue({
                    url: '/telemetry/batch',
                    method: 'POST',
                    body: JSON.stringify(batchRequest),
                    timestamp: Date.now()
                });
            }
        } finally {
            this.isUploading = false;

            // [11단계] Drain: 업로드 완료 후 버퍼 잔량 확인
            // [피드백 반영] setTimeout을 사용하여 스택 오버플로우 방지 및 비동기 흐름 분리
            if (this.dataBuffer.length >= this.BATCH_SIZE) {
                console.log(`[ObdService] Drain: Buffer filled again (${this.dataBuffer.length} items), scheduling next upload`);
                const nextBatch = [...this.dataBuffer];
                this.dataBuffer = [];
                setTimeout(() => this.uploadBatch(nextBatch), 0);
            }
        }
    }

    private async processOfflineQueue() {
        // [11단계 개선] 중복 실행 방지
        if (this.isProcessingOfflineQueue) {
            console.log('[ObdService] processOfflineQueue already running, skipping');
            return;
        }

        this.isProcessingOfflineQueue = true;
        try {
            const queue = await OfflineStorage.getQueue();
            if (queue.length === 0) return;

            for (const req of queue) {
                if (!NetworkService.IsConnected) break;
                try {
                    await api.request({
                        url: req.url,
                        method: req.method,
                        data: req.body ? JSON.parse(req.body) : undefined,
                    });
                    if (req.id) await OfflineStorage.removeFromQueue(req.id);
                } catch (e) {
                    break;
                }
            }
        } finally {
            // [11단계 개선] 에러 발생 시에도 플래그 해제 보장
            this.isProcessingOfflineQueue = false;
        }
    }

    async flushBuffer() {
        if (this.dataBuffer.length > 0) {
            const logsToUpload = [...this.dataBuffer];
            this.dataBuffer = [];
            await this.uploadBatch(logsToUpload);
        }
    }

    async disconnect() {
        this.isDisconnectRequested = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        this.stopPolling();
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
    }

    // --- Simulation ---
    private simulationTimer: ReturnType<typeof setTimeout> | null = null;
    startSimulation() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.simulationLoop();
    }
    stopSimulation() {
        this.isPolling = false;
        if (this.simulationTimer) {
            clearTimeout(this.simulationTimer);
            this.simulationTimer = null;
        }
    }
    private simulationLoop() {
        if (!this.isPolling) return;
        const fakeData: ObdData = {
            timestamp: new Date().toISOString(),
            rpm: Math.floor(Math.random() * (3000 - 800) + 800),
            speed: Math.floor(Math.random() * 120),
            engine_load: Math.floor(Math.random() * 100),
            coolant_temp: Math.floor(Math.random() * (110 - 80) + 80),
            voltage: parseFloat((Math.random() * (14.5 - 12) + 12).toFixed(1)),
        };
        this.currentData = fakeData;
        this.notifyListeners(fakeData);
        this.collectData(fakeData);
        this.simulationTimer = setTimeout(() => this.simulationLoop(), 1000);
    }

    isConnected(): boolean { return this.connectionType !== null; }

    private handleDisconnection() {
        if (this.isDisconnectRequested) return;
        this.connectionType = null;
        this.attemptReconnect();
    }

    private async attemptReconnect() {
        if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
            useBleStore.getState().setStatus('disconnected');
            return;
        }
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(async () => {
            try {
                if (this.currentDeviceId) {
                    await this.setTargetDevice(this.currentDeviceId);
                } else if (this.classicDevice) {
                    const ok = await ClassicBtService.connect(this.classicDevice);
                    if (ok) await this.setClassicDevice(this.classicDevice);
                }
            } catch (e) {
                this.attemptReconnect();
            }
        }, 3000);
    }

    private async saveLastDevice(type: 'classic' | 'ble', id: string, name: string) {
        try {
            await AsyncStorage.setItem(STORAGE_KEY_LAST_DEVICE, JSON.stringify({ type, id, name }));
        } catch (e) { }
    }

    private async loadLastDevice() {
        try {
            const json = await AsyncStorage.getItem(STORAGE_KEY_LAST_DEVICE);
            return json ? JSON.parse(json) : null;
        } catch (e) { return null; }
    }

    public async tryAutoConnect() {
        const last = await this.loadLastDevice();
        if (!last || this.isConnected()) return;
        try {
            if (last.type === 'ble') {
                await this.setTargetDevice(last.id);
            } else {
                await this.setClassicDevice({ id: last.id, name: last.name, address: last.id } as any);
            }
        } catch (e) { }
    }
}

export default new ObdService();
