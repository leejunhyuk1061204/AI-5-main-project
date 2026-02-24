import { NativeEventEmitter, NativeModules, Platform } from 'react-native';
import type { BluetoothDevice } from 'react-native-bluetooth-classic';
let BleManager: any;

if (Platform.OS !== 'web') {
    BleManager = require('react-native-ble-manager').default;
}
import BleService from './BleService';
import ClassicBtService from './ClassicBtService';
import { OBD_PIDS, parseObdResponse, PidDefinition } from './ObdPidHelper';
import { uploadObdBatch, ObdLogRequest, ObdBatchRequest, obdDeviceApi } from '../api/obdApi';
import { sendDtcReport, sendDtcBatchReport } from '../api/aiApi';
import { useBleStore } from '../store/useBleStore';
import BackgroundService from './BackgroundService';
import { useTripStore } from '../store/useTripStore';
import NetworkService from './NetworkService';
import OfflineStorage from './OfflineStorage';
import api from '../api/axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY_LAST_DEVICE = 'last_obd_device';
const STORAGE_KEY_LAST_TYPE = 'last_obd_type';
const STORAGE_KEY_OBD_DEVICES = 'obd_devices_cache';

export type ObdQualityStatus = 'OK' | 'STALE' | 'DISCONNECTED' | 'UNSUPPORTED' | 'PARSE_ERROR';

/** [10단계] 주행 종료 감지 상태 (WAITING_START: 연결됐으나 RPM+전압 조건 미충족) */
export type TripState = 'WAITING_START' | 'RUNNING' | 'SUSPECT_END' | 'ENDED';
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
    // 보조 지표 (Ircama/실차 진단용)
    fuel_status?: string;
    timing_advance?: number;
    obd_compliance?: string;
    distance_w_mil?: number;
    distance_since_dtc_clear?: number;
    barometric_pressure?: number;
    catalyst_temp_b1s1?: number;
    absolute_load?: number;
    time_since_dtc_cleared?: number;
    fuel_type?: string;
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
    // 타임아웃/소켓 오류 시 무한 재시도 방지 (3회 × 3초 후 포기)
    private readonly MAX_RECONNECT_ATTEMPTS = 3;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    // 연결 에러/해제 감지용 상태
    private connectionErrorCount: number = 0;
    private readonly MAX_CONNECTION_ERROR_BEFORE_DISCONNECT = 3;
    private disconnectionHandled: boolean = false;

    /** 수동 연결(설정 UI)로 붙인 세션: 끊기면 재연결 시도 안 함 */
    private manualConnectSession: boolean = false;

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
    private pidRequestStartTime: number | null = null;
    /** P1: BLE 응답 대기용 resolver (Promise.race에서 10초 보장) */
    private responseResolve: (() => void) | null = null;

    // Observers
    private listeners: ((data: ObdData) => void)[] = [];

    /**
     * 백엔드가 LocalDateTime(타임존 정보 없음)으로 파싱하므로,
     * 클라이언트 로컬 시각 기준 ISO-8601 문자열(YYYY-MM-DDTHH:mm:ss.SSS)을 생성한다.
     * (toISOString()은 UTC 기준이라 서버 로컬 시간과 9시간 어긋나는 문제가 있음)
     */
    private getLocalTimestamp(): string {
        const now = new Date();
        const pad = (n: number) => n.toString().padStart(2, '0');
        const padMs = (n: number) => n.toString().padStart(3, '0');

        return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` +
            `T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}.` +
            `${padMs(now.getMilliseconds())}`;
    }

    // Current Snapshot
    private currentData: ObdData = { timestamp: this.getLocalTimestamp() };
    private vin: string | null = null;
    private calid: string | null = null;
    private cvn: string | null = null;
    private resolveVehicleTimer: ReturnType<typeof setTimeout> | null = null;
    private resolveVehicleFallbackTimer: ReturnType<typeof setTimeout> | null = null;
    private resolveVehicleFired = false;
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
    // 주행 시작 조건: RPM > 300 연속 4초 후 startTrip 1회 호출
    private tripStartConditionCount: number = 0;
    private tripStartTriggered: boolean = false;

    // [10단계] Grace Period (IDLE/DISCONNECT 동일 30초)
    private readonly GRACE_PERIOD_IDLE_MS = 30000; // 30초
    private readonly GRACE_PERIOD_DISCONNECT_MS = 30000; // 30초

    // [11단계] PID 실패 관리 (Stability)
    private pidFailCount: Map<string, number> = new Map(); // mode:pid -> 실패 카운트
    private disabledPids: Set<string> = new Set(); // 비활성화된 PID 목록
    private readonly MAX_PID_FAIL_COUNT = 5; // 5회 연속 실패 시 비활성화

    // [11단계] 업로드 동시 실행 방지 (Concurrency)
    private isUploading: boolean = false;

    // [11단계 개선] 오프라인 큐 처리 동시성 제어
    private isProcessingOfflineQueue: boolean = false;

    /** ELM327 테스트 화면용: true면 resolve/recordConnect 등 백엔드 호출 스킵 */
    private testMode = false;

    setTestMode(value: boolean): void {
        this.testMode = value;
        console.log('[ObdService] testMode=', value);
    }

    /** 수동 연결(ObdConnectFlow)로 붙었을 때 true. 끊기면 attemptReconnect 하지 않음 */
    setManualConnectSession(value: boolean): void {
        this.manualConnectSession = value;
    }


    constructor() {
        if (Platform.OS !== 'web') {
            const BleManagerModule = NativeModules.BleManager;
            if (BleManagerModule) {
                const bleManagerEmitter = new NativeEventEmitter(BleManagerModule);

                // BLE 응답 리스너 (진단: 수신 여부 확인용)
                bleManagerEmitter.addListener(
                    'BleManagerDidUpdateValueForCharacteristic',
                    ({ value, peripheral, service, characteristic }: { value: number[], peripheral: string, service: string, characteristic: string }) => {
                        if (this.connectionType !== 'ble') return;
                        if (peripheral !== this.currentDeviceId) return;

                        const asciiString = value?.length ? String.fromCharCode(...value) : '';
                        if (this.currentPid && value?.length) {
                            console.log('[ObdService] BLE notify', value.length, 'b for', this.currentPid.mode + ':' + this.currentPid.pid);
                        }
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
        if (this.resolveVehicleTimer) {
            clearTimeout(this.resolveVehicleTimer);
            this.resolveVehicleTimer = null;
        }
        if (this.resolveVehicleFallbackTimer) {
            clearTimeout(this.resolveVehicleFallbackTimer);
            this.resolveVehicleFallbackTimer = null;
        }

        // 폴링 플래그 리셋
        this.isPolling = false;
        this.isProcessingQueue = false;
    }

    private getDeviceId(): string | null {
        if (this.connectionType === 'classic' && this.classicDevice) return this.classicDevice.address;
        if (this.connectionType === 'ble' && this.currentDeviceId) return this.currentDeviceId;
        return null;
    }

    private async doResolveAndConnect() {
        if (this.resolveVehicleTimer) {
            clearTimeout(this.resolveVehicleTimer);
            this.resolveVehicleTimer = null;
        }
        if (this.resolveVehicleFallbackTimer) {
            clearTimeout(this.resolveVehicleFallbackTimer);
            this.resolveVehicleFallbackTimer = null;
        }
        if (this.resolveVehicleFired) {
            console.log('[ObdService] doResolveAndConnect already fired, skip');
            return;
        }
        this.resolveVehicleFired = true;

        if (this.testMode) {
            console.log('[ObdService] doResolveAndConnect skip (testMode)');
            return;
        }
        const deviceId = this.getDeviceId();
        if (!deviceId) {
            console.warn('[ObdService] doResolveAndConnect no deviceId, skip');
            return;
        }

        const vin = this.vin || undefined;
        const calid = this.calid || undefined;
        const cvn = this.cvn || undefined;
        console.log('[ObdService] doResolveAndConnect call resolveVehicle deviceId=', deviceId, 'vin=', vin ? '***' : null, 'calid=', calid ? '***' : null, 'cvn=', cvn ? '***' : null);

        try {
            await obdDeviceApi.registerDevice({
                deviceId,
                deviceType: this.connectionType === 'classic' ? 'classic' : 'ble',
                name: useBleStore.getState().connectedDeviceName || deviceId,
            });
            const res = await obdDeviceApi.resolveVehicle({
                deviceId,
                vin,
                calid,
                cvn
            });
            if (!res.success || !res.data?.vehicleId) {
                console.warn('[ObdService] resolveVehicle no vehicleId in response');
                return;
            }
            const vehicleId = res.data.vehicleId;
            console.log('[ObdService] resolveVehicle success vehicleId=', vehicleId);

            await obdDeviceApi.recordConnect(deviceId, {
                vehicleId,
                vin: this.vin || undefined,
                calid: this.calid || undefined,
                cvn: this.cvn || undefined
            });
            this.setVehicleId(vehicleId);
            useBleStore.getState().setConnectedVehicleId(vehicleId);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] resolve-vehicle or recordConnect failed. reason=', msg);
        }
    }

    private tryResolveWhenIdentifiersReady() {
        if (this.calid !== null && this.cvn !== null) {
            if (this.resolveVehicleTimer) {
                clearTimeout(this.resolveVehicleTimer);
                this.resolveVehicleTimer = null;
            }
            console.log('[ObdService] CALID+CVN both received, trigger doResolveAndConnect');
            this.doResolveAndConnect();
        }
    }

    // ===== Classic Bluetooth 설정 =====
    async setClassicDevice(device: BluetoothDevice) {
        // [11단계 개선] 멱등성 보장: 동일 디바이스 재설정 시 no-op
        if (this.connectionType === 'classic' && this.classicDevice?.address === device.address) return;

        // [11단계 개선] 기존 연결 상태 클린업
        this.cleanupConnectionState();

        this.connectionType = 'classic';
        this.classicDevice = device;
        this.currentData = { timestamp: this.getLocalTimestamp() };
        this.isDisconnectRequested = false;
        this.connectionErrorCount = 0;
        this.disconnectionHandled = false;
        useBleStore.getState().setConnectedDeviceName(device.name || 'Classic Device');
        useBleStore.getState().setConnectedDevice(device.address);
        useBleStore.getState().setStatus('connected');

        this.saveLastDevice('classic', device.address, device.name || 'Classic Device');
        console.log('[ObdService] classic connected name=', device.name, 'address=', device.address);
        this.classicDataSubscription = ClassicBtService.onDataReceived(device, (data) => {
            this.handleResponse(data);
        });

        await this.initializeElm327();
    }

    // ===== BLE 설정 =====
    async setTargetDevice(deviceId: string) {
        if (Platform.OS === 'web') {
            console.warn('[ObdService] BLE not supported on web');
            return;
        }

        // [11단계 개선] 멱등성 보장: 동일 디바이스 재설정 시 no-op
        if (this.connectionType === 'ble' && this.currentDeviceId === deviceId) return;

        // [11단계 개선] 기존 연결 상태 클린업
        this.cleanupConnectionState();

        this.connectionType = 'ble';
        this.currentDeviceId = deviceId;
        this.currentData = { timestamp: this.getLocalTimestamp() };
        this.isDisconnectRequested = false;
        // reconnectAttempts는 재연결 시도 흐름( handleDisconnection/attemptReconnect )에서만 관리
        this.connectionErrorCount = 0;
        this.disconnectionHandled = false;
        useBleStore.getState().setStatus('connecting');

        try {
            const peripheralInfo = await BleManager.retrieveServices(deviceId);
            let found = false;

            if (peripheralInfo.characteristics) {
                // 1) 표준 FFE0/FFE1 또는 FFF0/FFF1 우선
                for (const char of peripheralInfo.characteristics) {
                    const svc = char.service.toLowerCase();
                    const chr = char.characteristic.toLowerCase();
                    if ((svc.includes('ffe0') && chr.includes('ffe1')) ||
                        (svc.includes('fff0') && chr.includes('fff1'))) {
                        this.serviceUUID = char.service;
                        this.charUUID = char.characteristic;
                        found = true;
                        console.log('[ObdService] BLE: using standard', this.serviceUUID, this.charUUID);
                        break;
                    }
                }

                // 2) 없으면 Notify+Write 한 개짜리
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
                            break;
                        }
                    }
                }
            }

            if (found) {
                await BleService.startNotification(this.currentDeviceId, this.serviceUUID, this.charUUID);
                console.log('[ObdService] BLE connected deviceId=', this.currentDeviceId, 'notify on', this.serviceUUID, this.charUUID);
                useBleStore.getState().setStatus('connected');
                useBleStore.getState().setConnectedDevice(this.currentDeviceId);
                useBleStore.getState().setConnectedDeviceName(this.currentDeviceId);
                this.saveLastDevice('ble', this.currentDeviceId, this.currentDeviceId);

                await this.initializeElm327();
            } else {
                console.warn('[ObdService] OBD characteristics not found. deviceId=', this.currentDeviceId);
                useBleStore.getState().setStatus('disconnected');
                useBleStore.getState().setConnectedVehicleId(null);
            }

        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] BLE configure failed. reason=', msg);
            useBleStore.getState().setStatus('disconnected');
            useBleStore.getState().setConnectedVehicleId(null);
        }
    }

    // ===== ELM327 초기화 =====
    private async initializeElm327() {
        const initCommands = [
            'ATZ',      // 로컬 리셋
            'ATE0',     // 에코 오프
            'ATL0',     // 줄바꿈 오프
            'ATS0',     // 공백 제거 (속도 향상)
            'ATH0',     // 헤더 오프
            'ATAT1',    // Adaptive Timing Level 1
            'ATCAF1',   // CAN Auto Formatting ON
            'ATSP0',    // 프로토콜 자동 감지
        ];
        for (const cmd of initCommands) {
            await this.sendCommand(cmd);
            await this.delay(150);
        }
        this.resolveVehicleFired = false;
        this.enqueue(OBD_PIDS.VIN, QueuePriority.NORMAL);
        this.enqueue(OBD_PIDS.CALID, QueuePriority.NORMAL);
        this.enqueue(OBD_PIDS.CVN, QueuePriority.NORMAL);
        if (this.resolveVehicleFallbackTimer) clearTimeout(this.resolveVehicleFallbackTimer);
        this.resolveVehicleFallbackTimer = setTimeout(() => {
            this.resolveVehicleFallbackTimer = null;
            if (!this.resolveVehicleFired) {
                console.log('[ObdService] resolve fallback 12s: no 09 response in time, call doResolveAndConnect');
                this.doResolveAndConnect();
            }
        }, 12000);
    }

    // ===== 명령 전송 =====
    private async sendCommand(command: string): Promise<boolean> {
        try {
            let ok = false;

            if (this.connectionType === 'classic' && this.classicDevice) {
                ok = await ClassicBtService.write(this.classicDevice, command);
            } else if (this.connectionType === 'ble' && this.currentDeviceId) {
                if (Platform.OS === 'web') return false;
                const bytes = this.stringToBytes(command + '\r');
                await BleManager.writeWithoutResponse(this.currentDeviceId, this.serviceUUID, this.charUUID, bytes);
                ok = true;
            } else {
                return false;
            }

            if (ok) {
                return true;
            }
            // ok === false 인 경우 (Classic write 실패 등)
            return false;
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.warn('[ObdService] send failed cmd=', command, 'reason=', msg);
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

        this.isPolling = true;

        this.tripState = 'WAITING_START';
        this.suspectReason = null;
        this.suspectStartedAt = 0;
        this.isEndingTrip = false;
        this.ignoreResponses = false;
        this.idleCount = 0;
        this.disconnectCount = 0;
        this.tripStartConditionCount = 0;
        this.tripStartTriggered = false;

        this.pidFailCount.clear();
        this.disabledPids.clear();
        this.isUploading = false;

        console.log('[ObdService] polling started type=', this.connectionType);
        useBleStore.getState().setPolling(true);
        this.pollingLoop(intervalMs);
        // 일반 주행 모드: 1초 고정 스냅샷 (서버 업로드/주행 상태 머신용)
        // ELM327 테스트 화면(testMode)에서는 응답이 올 때마다 스냅샷을 내보내도록 samplingLoop를 사용하지 않는다.
        if (!this.testMode) {
            this.samplingLoop(1000); // 6단계: 1초 고정 샘플링 시작
        }

        // 안드로이드 백그라운드 서비스 시작 (P0: 권한은 호출 측에서 먼저 요청, 여기서는 체크만)
        if (Platform.OS === 'android') {
            (async () => {
                try {
                    if (Platform.Version >= 33) {
                        const { PermissionsAndroid } = require('react-native');
                        const hasPermission = await PermissionsAndroid.check('android.permission.POST_NOTIFICATIONS');
                        if (!hasPermission) {
                            return;
                        }
                    }
                    if (BackgroundService.isActive()) return;
                    await BackgroundService.start();
                } catch (e) {
                    const msg = e instanceof Error ? e.message : String(e);
                    console.warn('[ObdService] Foreground Service start failed, continuing polling without background reconnect. reason=', msg);
                }
            })();
        }
    }

    /** Android 13+ 알림 권한 요청. 폴링 시작 전(ObdConnect 등)에서 호출. */
    async ensureNotificationPermissionForPolling(): Promise<boolean> {
        if (Platform.OS !== 'android' || (Platform.Version as number) < 33) return true;
        const { PermissionsAndroid, Alert } = require('react-native');
        const hasPermission = await PermissionsAndroid.check('android.permission.POST_NOTIFICATIONS');
        if (hasPermission) return true;
        const result = await PermissionsAndroid.request('android.permission.POST_NOTIFICATIONS');
        if (result === 'granted') return true;
        Alert.alert("알림 권한 필요", "백그라운드 수집 및 주행 알림을 위해 알림 권한이 반드시 필요합니다.");
        return false;
    }

    /**
     * [10단계] 원자적 마감 루틴
     * 중복 호출 방지 및 응답 파편 차단 보장
     */
    async finalizeTrip() {
        // 중복 마감 방지
        if (this.tripState === 'ENDED' || this.isEndingTrip) return;

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

            await this.flushBuffer();

            const tripId = useTripStore.getState().currentTripId;
            try {
                await useTripStore.getState().endTrip();
            } catch (e) {
                const msg = e instanceof Error ? e.message : String(e);
                console.error('[ObdService] endTrip failed, queuing. reason=', msg);
                if (tripId) {
                    const url = `/api/v1/trips/${tripId}/end`;
                    const isQueued = await OfflineStorage.isUrlQueued(url);
                    if (!isQueued) {
                        await OfflineStorage.addToQueue({
                            url: url,
                            method: 'POST',
                            timestamp: Date.now(),
                            body: JSON.stringify({ endTime: this.getLocalTimestamp() })
                        });
                    }
                }
            }

            // 주행 종료 후 연결 해제 → 다음 출발 시 Heartbeat의 tryAutoConnectFromCache가 재연결·폴링 재개하도록 함
            await this.disconnect();
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] finalizeTrip error. reason=', msg);
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

        // anomaly + wear_factor + DTC + freezeFrame에 실제로 쓰는 PID만
        const normalPids = [
            OBD_PIDS.ENGINE_LOAD,
            OBD_PIDS.MAP,
            OBD_PIDS.MAF,
            OBD_PIDS.COOLANT_TEMP,
            OBD_PIDS.INTAKE_TEMP,
            OBD_PIDS.ENGINE_RUNTIME,
            OBD_PIDS.FUEL_TRIM_SHORT,
            OBD_PIDS.FUEL_TRIM_LONG,
            OBD_PIDS.VOLTAGE,
            OBD_PIDS.DTC_STATUS,
            // --- 주석 처리 (미사용) ---
            // OBD_PIDS.FUEL_STATUS,
            // OBD_PIDS.TIMING_ADVANCE,
            // OBD_PIDS.OBD_COMPLIANCE,
            // OBD_PIDS.DISTANCE_W_MIL,
            // OBD_PIDS.DISTANCE_SINCE_DTC_CLEAR,
            // OBD_PIDS.BAROMETRIC_PRESSURE,
            // OBD_PIDS.CATALYST_TEMP_B1S1,
            // OBD_PIDS.ABSOLUTE_LOAD,
            // OBD_PIDS.TIME_SINCE_DTC_CLEARED,
            // OBD_PIDS.FUEL_TYPE,
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
        const snapshot: ObdData = { timestamp: this.getLocalTimestamp() };

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
                (snapshot as any)[key] = undefined; // 타입 안정성을 위해 null 대신 undefined 또는 타입에 맞는 값 권장
            } else {
                (snapshot as any)[key] = this.currentData[key as keyof ObdData];
            }
        });

        // [10단계] SUSPECT_END 시 기록/전송용 스냅샷을 null로 — 배치에 키 포함·백엔드 NULL 기록
        if (this.tripState === 'SUSPECT_END') {
            const s = snapshot as unknown as Record<string, unknown>;
            s.rpm = null;
            s.speed = null;
            s.voltage = null;
            s.coolant_temp = null;
            s.engine_load = null;
            s.fuel_trim_short = null;
            s.fuel_trim_long = null;
            s.throttle = null;
            s.map = null;
            s.maf = null;
            s.intake_temp = null;
            s.engine_runtime = null;
        }

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
                this.maxDriftMs = 0;
                this.driftCheckCount = 0;
            }
        }
        this.lastSnapshotTs = now;

        this.samplingTimer = setTimeout(() => this.samplingLoop(intervalMs), intervalMs);

        // [10단계] 주행 시작 조건: RPM > 300 연속 4초 후 startTrip 1회
        if (this.tripState === 'WAITING_START' && this.vehicleId && !useTripStore.getState().isDriving && !this.tripStartTriggered) {
            const rpmOk = snapshot.rpm !== undefined && snapshot.rpm > 300;
            if (rpmOk) {
                this.tripStartConditionCount++;
                if (this.tripStartConditionCount >= 4) {
                    this.tripStartTriggered = true;
                    this.tripState = 'RUNNING';
                    useTripStore.getState().startTrip(this.vehicleId);
                }
            } else {
                this.tripStartConditionCount = 0;
            }
        }

        // [10단계] 주행 종료 자동 감지 로직 (이미 주행 시작된 경우만)
        this.checkTripTermination(snapshot, now);
    }

    /**
     * [10단계] 주행 종료 상태 머신 체크
     */
    private checkTripTermination(snapshot: ObdData, now: number) {
        if (!this.isPolling || this.isEndingTrip) return;
        if (this.tripState !== 'RUNNING' && this.tripState !== 'SUSPECT_END') return;

        // highAgeMs 계산: RPM 또는 Speed 중 최근 갱신 기준 (실제 수신 데이터 갱신 시각)
        const rpmTs = this.lastUpdatedAt.get('rpm') || 0;
        const speedTs = this.lastUpdatedAt.get('speed') || 0;
        const lastHighUpdatedAt = Math.max(rpmTs, speedTs);
        const highAgeMs = now - lastHighUpdatedAt;

        const isRpmZero = snapshot.rpm !== undefined && snapshot.rpm === 0;
        const isSpeedZero = snapshot.speed !== undefined && snapshot.speed === 0;

        if (this.tripState === 'RUNNING') {
            // Case A (IDLE): RPM=0 && Speed=0 연속 1분 (60초)
            if (isRpmZero && isSpeedZero) {
                this.idleCount++;
                if (this.idleCount >= 60) { // 1분 = 60초
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
                    this.tripState = 'SUSPECT_END';
                    this.suspectReason = 'DISCONNECT';
                    this.suspectStartedAt = now;
                }
            } else {
                this.disconnectCount = 0; // 리셋
            }
        }
        else if (this.tripState === 'SUSPECT_END') {
            // 복귀 조건: 실제 수신 데이터(currentData) 기준 — 스냅샷은 SUSPECT_END 시 0으로 덮어씌워져 DB용
            const currentRpm = this.currentData.rpm;
            const currentSpeed = this.currentData.speed;
            const isActuallyActive = (currentRpm !== undefined && currentRpm > 0) ||
                (currentSpeed !== undefined && currentSpeed > 0);

            if (isActuallyActive) {
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
                    this.finalizeTrip();
                } else {
                    // 매 15초마다 경과 로그
                    const elapsedSec = Math.floor(elapsedSinceSuspect / 1000);
                    if (elapsedSec > 0 && elapsedSec % 15 === 0) {
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
                this.pidRequestStartTime = Date.now();

                // Ircama ELM327-emulator Request 패턴(^010C, ^0902 등)과 맞추기 위해 공백 없이 전송
                const command = `${pid.mode}${pid.pid}`;

                const success = await this.sendCommand(command);
                if (!success) {
                    // [11단계] sendCommand 실패 캘운팅
                    this.pidRequestStartTime = null;
                    this.incrementPidFailCount(pid, 'sendCommand failed');
                    this.currentPid = null;
                    continue;
                }
                console.log('[ObdService] sent', command);

                // 응답 처리 대기 (BLE/Classic 공통: 응답 기반, onDataReceived 또는 notify로 responseResolve 호출)
                const maxWaitMs = 10000;
                const responsePromise = new Promise<void>(r => { this.responseResolve = r; });
                await Promise.race([responsePromise, this.delay(maxWaitMs)]);
                if (this.currentPid !== null) {
                    console.warn(`[ObdService] PID ${pid.mode}:${pid.pid} response timeout after ${maxWaitMs}ms`);
                    this.pidRequestStartTime = null;
                    this.incrementPidFailCount(pid, 'response timeout');
                    this.currentPid = null;
                }
                this.responseResolve = null;
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
        const pidKey = `${this.currentPid.mode}:${this.currentPid.pid}`;
        console.log('[ObdService] rx', pidKey, '+', responseStr.length, 'b buf=', this.responseBuffer.length);

        // 완전한 응답인지 확인: '>' 포함 시 ELM327 완료. Classic은 delimiter '>'로 분리되어 '>' 없이 전달되므로 \r\r 또는 내용 있으면 완료로 간주
        const hasPrompt = this.responseBuffer.includes('>');
        const classicComplete = this.connectionType === 'classic' && this.responseBuffer.trim().length > 0;
        if (!hasPrompt && !classicComplete) return;

        const rawPreview = this.responseBuffer.trim().replace(/\s+/g, ' ').slice(0, 60);
        console.log('[ObdService] complete', pidKey, 'raw=', rawPreview);

        const result = parseObdResponse(this.responseBuffer, this.currentPid);

        // [11단계] 실패 감지: NO DATA, ?, 빈 응답, 파싱 null
        const cleanResp = this.responseBuffer.trim().toUpperCase();
        if (cleanResp.includes('NO DATA') || cleanResp.includes('?') || cleanResp === '>' || result === null) {
            const reason = cleanResp.includes('NO DATA') ? 'NO DATA' :
                cleanResp.includes('?') ? 'unknown error (?)' :
                    cleanResp === '>' ? 'empty response' : 'parse failed';
            this.logPidRoundTrip(pidKey, false);
            this.incrementPidFailCount(this.currentPid, reason);
            this.responseResolve?.();
            this.responseResolve = null;
            this.currentPid = null;
            this.responseBuffer = '';
            return;
        }

        // [11단계] 성공적으로 파싱되면 실패 카운트/연결 에러 카운트 리셋
        this.resetPidFailCount(pidKey);
        this.connectionErrorCount = 0;
        this.disconnectionHandled = false;

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
                case '0106': this.updateData('fuel_trim_short', result); break;
                case '0107': this.updateData('fuel_trim_long', result); break;
                case '0103': this.updateData('fuel_status', result); break;
                case '010E': this.updateData('timing_advance', result); break;
                case '011C': this.updateData('obd_compliance', result); break;
                case '0121': this.updateData('distance_w_mil', result); break;
                case '0131': this.updateData('distance_since_dtc_clear', result); break;
                case '0133': this.updateData('barometric_pressure', result); break;
                case '013C': this.updateData('catalyst_temp_b1s1', result); break;
                case '0143': this.updateData('absolute_load', result); break;
                case '014E': this.updateData('time_since_dtc_cleared', result); break;
                case '0151': this.updateData('fuel_type', result); break;
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
                        const msg = e instanceof Error ? e.message : String(e);
                        console.error('[ObdService] DTC_STATUS handle error. reason=', msg);
                    }
                    break;

                // Mode 03: Stored DTCs
                case '03':
                    this.lastDtcCodes = result as string;
                    break;

                case '020200':
                    this.lastFreezeDtc = result as string;
                    break;

                // Mode 09 02: VIN → 차량 특정용 (0904/0906은 초기화 시 이미 enqueue됨)
                case '0902':
                    this.vin = result as string;
                    console.log('[ObdService] 0902 VIN received');
                    if (this.resolveVehicleTimer) clearTimeout(this.resolveVehicleTimer);
                    if (this.resolveVehicleFallbackTimer) {
                        clearTimeout(this.resolveVehicleFallbackTimer);
                        this.resolveVehicleFallbackTimer = null;
                    }
                    this.resolveVehicleTimer = setTimeout(() => this.doResolveAndConnect(), 5000);
                    break;
                case '0904':
                    this.calid = (result as string)?.toString() || null;
                    console.log('[ObdService] 0904 CALID received');
                    this.tryResolveWhenIdentifiersReady();
                    break;
                case '0906':
                    this.cvn = (result as string)?.toString() || null;
                    console.log('[ObdService] 0906 CVN received');
                    this.tryResolveWhenIdentifiersReady();
                    break;
            }
        }

        // 테스트 모드(ELM327 테스트 화면)에서는 1초 타이머 대신
        // 각 01 모드 응답이 올 때마다 최신 스냅샷을 바로 내보낸다.
        if (this.testMode && this.currentPid && this.currentPid.mode === '01') {
            const snapshot: ObdData = { timestamp: this.getLocalTimestamp() };
            Object.keys(this.currentData).forEach(key => {
                if (key === 'timestamp') return;
                (snapshot as any)[key] = (this.currentData as any)[key];
            });
            this.notifyListeners(snapshot);
        }

        this.logPidRoundTrip(pidKey, true);
        this.responseResolve?.();
        this.responseResolve = null;
        this.currentPid = null;
        this.responseBuffer = '';
    }

    private logPidRoundTrip(pidKey: string, ok: boolean) {
        if (this.pidRequestStartTime === null) return;
        const elapsed = Date.now() - this.pidRequestStartTime;
        this.pidRequestStartTime = null;
        console.log(`[ObdService] PID ${pidKey} round-trip ${elapsed}ms ${ok ? 'ok' : 'fail'}`);
    }

    /**
     * DTC 상세 수집 및 백엔드 보고 (배치 전송 방식으로 전환)
     */
    private async reportDetailedDtc(statusSummary: string) {
        if (this.isReportingDtc) return;
        this.isReportingDtc = true;


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
                    break;
                }

                await this.delay(100);
                waitCount++;
            }

            if (!this.lastDtcCodes && !this.lastFreezeDtc) {
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
                return;
            }

            // 3. 통합 배치 리포트 전송
            const vehicleId = this.vehicleId;
            if (!vehicleId) {
                console.error('[ObdService] Cannot report DTC: vehicleId is missing');
                return;
            }

            const reportData = {
                vehicleId: vehicleId,
                dtcs: dtcs,
                freezeFrame: {
                    rpm: this.currentData.rpm,
                    speed: this.currentData.speed,
                    voltage: this.currentData.voltage,
                    coolantTemp: this.currentData.coolant_temp,
                    engineLoad: this.currentData.engine_load,
                    fuelTrimShort: this.currentData.fuel_trim_short,
                    fuelTrimLong: this.currentData.fuel_trim_long,
                    intakeTemp: this.currentData.intake_temp,
                    map: this.currentData.map,
                    maf: this.currentData.maf,
                    throttlePos: this.currentData.throttle,
                    engineRuntime: this.currentData.engine_runtime,
                    pidsSnapshot: JSON.stringify(this.currentData)
                }
            };

            const url = '/api/v1/ai/dtc/batch';

            // [Offline Mode] 네트워크 연결 없으면 큐에 저장
            if (!NetworkService.IsConnected) {
                console.log('[ObdService] Offline, queuing DTC report');
                await OfflineStorage.addToQueue({
                    url,
                    method: 'POST',
                    body: JSON.stringify(reportData),
                    timestamp: Date.now()
                });
                return;
            }

            try {
                await sendDtcBatchReport(reportData);
                this.lastDtcReportAt = Date.now();
            } catch (error) {
                const msg = error instanceof Error ? error.message : String(error);
                console.error('[ObdService] DTC report upload failed, queuing for retry. reason=', msg);
                // [Failover] 전송 실패 시에도 큐에 저장하여 재시도 보장
                await OfflineStorage.addToQueue({
                    url,
                    method: 'POST',
                    body: JSON.stringify(reportData),
                    timestamp: Date.now()
                });
            }

        } catch (error) {
            const msg = error instanceof Error ? error.message : String(error);
            console.error('[ObdService] DTC batch report failed. reason=', msg);
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

        // 보내기/받기 모두 실패 시 연결 에러 카운트에 포함
        this.connectionErrorCount++;
        console.warn('[ObdService] connection error detected. count=', this.connectionErrorCount, 'reason=', reason, 'pid=', key);
        if (!this.disconnectionHandled &&
            this.connectionErrorCount >= this.MAX_CONNECTION_ERROR_BEFORE_DISCONNECT) {
            this.disconnectionHandled = true;
            this.handleDisconnection();
        }

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

    /**
     * 03(Stored DTC) / 02(Freeze Frame DTC) 1회 요청 후 결과 반환.
     * Ircama에서는 샘플 응답, 실차에서는 DTC 없으면 null/빈 문자열 올 수 있음.
     */
    async runTest03And02(): Promise<{ storedDtc: string | null; freezeDtc: string | null }> {
        this.lastDtcCodes = '';
        this.lastFreezeDtc = '';
        this.enqueue(OBD_PIDS.GET_DTCS, QueuePriority.HIGH);
        this.enqueue(OBD_PIDS.FREEZE_DTC, QueuePriority.HIGH);
        await this.delay(5000);
        return {
            storedDtc: this.lastDtcCodes.trim() !== '' ? this.lastDtcCodes.trim() : null,
            freezeDtc: this.lastFreezeDtc.trim() !== '' ? this.lastFreezeDtc.trim() : null,
        };
    }

    setVehicleId(id: string) {
        this.vehicleId = id;
    }

    getCalid(): string | null {
        return this.calid;
    }

    getCvn(): string | null {
        return this.cvn;
    }

    /**
     * 연결 차량 변경 시 09 모드(CALID/CVN) 재요청.
     * 호출 후 일정 시간 대기하면 최신 calid/cvn이 채워지므로, 그 다음 recordConnect 시 사용.
     */
    async requestCalidCvnRefresh(): Promise<void> {
        this.enqueue(OBD_PIDS.CALID, QueuePriority.HIGH);
        this.enqueue(OBD_PIDS.CVN, QueuePriority.HIGH);
        await this.delay(5000);
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
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] save buffer recovery failed. reason=', msg);
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
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] load recovered buffer failed. reason=', msg);
        }
    }

    /**
     * [9단계] 성공적인 배치 구성 시 임시 버퍼 소거
     */
    private async clearRecoveredBuffer() {
        try {
            await AsyncStorage.removeItem(this.BUFFER_RECOVERY_KEY);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] clear recovered buffer failed. reason=', msg);
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
            return;
        }

        this.isUploading = true;

        try {
            // 8.5단계: batchId 생성 (차량ID + 타임스탬프 조합으로 중복 방지)
            const batchId = `batch-${this.vehicleId}-${Date.now()}`;

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
                await OfflineStorage.addToQueue({
                    url: '/api/v1/telemetry/batch',
                    method: 'POST',
                    body: JSON.stringify(batchRequest),
                    timestamp: Date.now()
                });
                return;
            }

            try {
                await uploadObdBatch(batchRequest);
            } catch (error) {
                const msg = error instanceof Error ? error.message : String(error);
                console.error('[ObdService] batch upload failed, saving to queue. batchId=', batchId, 'reason=', msg);
                await OfflineStorage.addToQueue({
                    url: '/api/v1/telemetry/batch',
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
                const nextBatch = [...this.dataBuffer];
                this.dataBuffer = [];
                setTimeout(() => this.uploadBatch(nextBatch), 0);
            }
        }
    }

    private async processOfflineQueue() {
        // [11단계 개선] 중복 실행 방지
        if (this.isProcessingOfflineQueue) {
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
        console.log('[ObdService] disconnect requested');
        this.isDisconnectRequested = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // 재시도/에러 관련 상태를 완전히 초기화하여, 이후 새 세션에서 다시 공정하게 시도할 수 있도록 한다.
        this.reconnectAttempts = 0;
        this.connectionErrorCount = 0;
        this.disconnectionHandled = false;
        this.manualConnectSession = false;

        // 주행 마감 / 배치 업로드 / BackgroundService.stop 등이 모두 끝난 뒤에
        // 실제 BT disconnect를 수행하기 위해, stopPolling을 반드시 기다린다.
        await this.stopPolling();
        await this.flushBuffer();

        if (this.classicDataSubscription) {
            this.classicDataSubscription.remove();
            this.classicDataSubscription = null;
        }

        try {
            if (this.connectionType === 'classic' && this.classicDevice) {
                await ClassicBtService.disconnect(this.classicDevice);
            } else if (this.connectionType === 'ble' && this.currentDeviceId) {
                try {
                    await BleService.disconnect(this.currentDeviceId);
                } catch (e) {
                    const msg = e instanceof Error ? e.message : String(e);
                    console.error('[ObdService] BLE disconnect failed. reason=', msg);
                }
            }
        } finally {
            this.connectionType = null;
            this.classicDevice = null;
            this.currentDeviceId = null;
            this.dataBuffer = [];
            useBleStore.getState().reset();
        }
        console.log('[ObdService] disconnect done, state reset');
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
            timestamp: this.getLocalTimestamp(),
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

        if (this.isPolling) {
            this.stopPolling();
        }

        if (this.manualConnectSession || this.testMode) {
            this.manualConnectSession = false;
            this.connectionType = null;
            this.currentDeviceId = null;
            this.classicDevice = null;
            if (this.classicDataSubscription) {
                this.classicDataSubscription.remove();
                this.classicDataSubscription = null;
            }
            useBleStore.getState().reset();
            console.warn('[ObdService] handleDisconnection: manual/test session, no reconnect');
            return;
        }

        console.warn('[ObdService] handleDisconnection: connection loss, scheduling reconnect.');
        this.connectionType = null;
        this.attemptReconnect();
    }

    private async attemptReconnect() {
        if (this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
            console.warn('[ObdService] attemptReconnect: max attempts reached. Forcing trip end and disconnect.');
            // 재시도 한계를 넘으면 현재 주행/연결만 정리한다.
            // 백그라운드 재연결은 별도의 앱 플로우(자동로그인/설정 화면 등)에서 시작/유지한다.
            try {
                await this.disconnect();
            } catch (e) {
                const msg = e instanceof Error ? e.message : String(e);
                console.warn('[ObdService] attemptReconnect: disconnect failed. reason=', msg);
            }
            return;
        }
        this.reconnectAttempts++;
        console.log('[ObdService] attemptReconnect scheduled. attempt=', this.reconnectAttempts);
        this.reconnectTimer = setTimeout(async () => {
            try {
                if (this.currentDeviceId) {
                    console.log('[ObdService] attemptReconnect BLE. deviceId=', this.currentDeviceId);
                    await this.setTargetDevice(this.currentDeviceId);
                    console.log('[ObdService] attemptReconnect BLE success. deviceId=', this.currentDeviceId);
                    if (!this.isPolling) {
                        this.startPolling(1000);
                    }
                } else if (this.classicDevice) {
                    console.log('[ObdService] attemptReconnect Classic. address=', this.classicDevice.address);
                    await ClassicBtService.disconnect(this.classicDevice);
                    await this.delay(500);
                    const ok = await ClassicBtService.connect(this.classicDevice);
                    if (ok) {
                        await this.setClassicDevice(this.classicDevice);
                        console.log('[ObdService] attemptReconnect Classic success. address=', this.classicDevice.address);
                        if (!this.isPolling) {
                            this.startPolling(1000);
                        }
                    } else {
                        console.warn('[ObdService] attemptReconnect Classic connect() returned false. address=', this.classicDevice.address);
                        // 예외 없이 false만 반환된 경우에도 재시도 카운터에 포함되도록 다음 시도 스케줄링
                        this.attemptReconnect();
                    }
                }
            } catch (e) {
                const msg = e instanceof Error ? e.message : String(e);
                console.warn('[ObdService] attemptReconnect error. reason=', msg);
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
                console.log('[ObdService] tryAutoConnect BLE. deviceId=', last.id);
                await this.setTargetDevice(last.id);
            } else {
                console.log('[ObdService] tryAutoConnect Classic. address=', last.id);
                // last.id는 address 문자열만 가지고 있으므로, 실제 BluetoothDevice 인스턴스를 다시 조회해야 한다.
                const bonded = await ClassicBtService.getBondedDevices();
                const match = bonded.find((d: { address: string }) => d.address === last.id);
                if (!match) {
                    console.warn('[ObdService] tryAutoConnect Classic: no bonded device found for address=', last.id);
                    return;
                }
                const ok = await ClassicBtService.connect(match);
                if (!ok) {
                    console.warn('[ObdService] tryAutoConnect Classic: connect() returned false. address=', last.id);
                    return;
                }
                await this.setClassicDevice(match);
            }
            console.log('[ObdService] tryAutoConnect success. type=', last.type, 'id=', last.id);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.warn('[ObdService] tryAutoConnect failed. type=', last.type, 'id=', last.id, 'reason=', msg);
        }
    }

    /** 서버에서 OBD 장치 목록 조회 후 캐시 저장 (앱 시작 시 1회 호출) */
    public async loadAndCacheDevices(): Promise<void> {
        try {
            console.log('[ObdService] loadAndCacheDevices: fetching /obd/devices ...');
            const res = await obdDeviceApi.getDevices();
            if (res.success && res.data) {
                await AsyncStorage.setItem(STORAGE_KEY_OBD_DEVICES, JSON.stringify(res.data));
                console.log('[ObdService] loadAndCacheDevices: cached devices count=', res.data.length);
            } else {
                console.warn('[ObdService] loadAndCacheDevices: unexpected response. success=', res.success);
            }
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.warn('[ObdService] loadAndCacheDevices failed. reason=', msg);
        }
    }

    /** 캐시된 OBD 장치 목록 반환 (재연결 등에서 사용) */
    public async getCachedDevices(): Promise<Array<{ deviceId: string; deviceType: string; name: string }>> {
        try {
            const json = await AsyncStorage.getItem(STORAGE_KEY_OBD_DEVICES);
            if (!json) return [];
            const list = JSON.parse(json);
            return Array.isArray(list) ? list.map((d: any) => ({
                deviceId: d.deviceId,
                deviceType: d.deviceType || 'classic',
                name: d.name || d.deviceId
            })) : [];
        } catch (e) {
            return [];
        }
    }

    /** 주기 재연결 간격(ms): 다중 장치 1분, 단일 2분 */
    public async getReconnectIntervalMs(): Promise<number> {
        const list = await this.getCachedDevices();
        return list.length > 1 ? 60000 : 120000;
    }

    /**
     * 로그인/앱 시작 시: 캐시된 장치 목록이 있으면
     * 백그라운드 재연결 서비스를 시작한다.
     * (실제 폴링/연결은 tryAutoConnectFromCache 내부에서 처리)
     */
    public async startBackgroundReconnectIfNeeded(): Promise<void> {
        if (Platform.OS !== 'android') return;

        const list = await this.getCachedDevices();
        if (list.length === 0) return;

        if (BackgroundService.isActive()) return;

        try {
            await BackgroundService.start();
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.error('[ObdService] startBackgroundReconnectIfNeeded failed. reason=', msg);
        }
    }

    private cacheRoundRobinIndex = 0;

    /** 캐시된 장치 목록 기준 라운드로빈으로 1대 직접 연결 시도 (스캔 없음) */
    public async tryAutoConnectFromCache(): Promise<void> {
        if (this.isConnected()) return;
        const list = await this.getCachedDevices();
        if (list.length === 0) return;
        const index = this.cacheRoundRobinIndex % list.length;
        this.cacheRoundRobinIndex = index + 1;
        const device = list[index];
        console.log('[ObdService] tryAutoConnectFromCache selected device=', device.deviceId, 'type=', device.deviceType);
        try {
            if (device.deviceType === 'ble') {
                await this.setTargetDevice(device.deviceId);
                console.log('[ObdService] tryAutoConnectFromCache BLE success. deviceId=', device.deviceId);
                if (!this.isPolling) {
                    this.startPolling(1000);
                }
            } else {
                const bonded = await ClassicBtService.getBondedDevices();
                const match = bonded.find((d: { address: string }) => d.address === device.deviceId);
                if (match) {
                    const ok = await ClassicBtService.connect(match);
                    if (ok) {
                        await this.setClassicDevice(match);
                        console.log('[ObdService] tryAutoConnectFromCache Classic success. address=', match.address);
                        if (!this.isPolling) {
                            this.startPolling(1000);
                        }
                    } else {
                        console.warn('[ObdService] tryAutoConnectFromCache Classic connect() returned false. address=', match.address);
                    }
                }
            }
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            console.warn('[ObdService] tryAutoConnectFromCache failed. deviceId=', device.deviceId, 'reason=', msg);
        }
    }
}

export default new ObdService();
