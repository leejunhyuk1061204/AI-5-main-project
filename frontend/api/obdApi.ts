import api from './axios';
import { ApiResponse } from './axios';

export interface ObdDeviceDto {
    id: string;
    deviceId: string;
    deviceType: string;
    name: string;
    createdAt: string;
    updatedAt: string;
}

export interface ObdDeviceRegisterRequest {
    deviceId: string;
    deviceType: 'ble' | 'classic';
    name?: string;
}

export interface ConnectHistoryRequest {
    vehicleId: string;
    calid?: string;
    cvn?: string;
}

export interface ResolveVehicleRequest {
    deviceId: string;
    vin?: string;
    calid?: string;
    cvn?: string;
}

export interface ConnectionStatusResponse {
    vehicleId: string;
    isConnected: boolean;
    lastHeartbeatAt?: string;
}

const obdDeviceApi = {
    getDevices: async (): Promise<ApiResponse<ObdDeviceDto[]>> => {
        const response = await api.get('/api/v1/obd/devices');
        return response.data;
    },
    registerDevice: async (request: ObdDeviceRegisterRequest): Promise<ApiResponse<ObdDeviceDto>> => {
        const response = await api.post('/api/v1/obd/devices', request);
        return response.data;
    },
    recordConnect: async (deviceId: string, request: ConnectHistoryRequest): Promise<void> => {
        await api.put(`/api/v1/obd/devices/${encodeURIComponent(deviceId)}/connect`, request);
    },
    resolveVehicle: async (request: ResolveVehicleRequest): Promise<ApiResponse<{ vehicleId: string }>> => {
        const response = await api.post('/api/v1/obd/resolve-vehicle', request);
        return response.data;
    }
};

// OBD 로그 요청 인터페이스 (백엔드 ObdLogDto와 매칭)
export interface ObdLogRequest {
    timestamp: string; // ISO 8601 형식 (예: "2026-01-20T15:00:00")
    vehicleId: string; // UUID 문자열
    rpm?: number;
    speed?: number;
    voltage?: number;
    coolantTemp?: number;
    engineLoad?: number;
    fuelTrimShort?: number;
    fuelTrimLong?: number;
    throttle?: number;
    map?: number;
    maf?: number;
    intakeTemp?: number;
    engineRuntime?: number;
}

/**
 * 8.5단계: Idempotency(중복 방지)를 위한 배치 요청 구조
 */
export interface ObdBatchRequest {
    batchId: string;
    vehicleId: string;
    logs: ObdLogRequest[];
}

/**
 * OBD 로그 배치 업로드
 * @param data - ObdBatchRequest (batchId 포함)
 */
export const uploadObdBatch = async (data: ObdBatchRequest): Promise<void> => {
    try {
        console.log(`[obdApi] Uploading batch ${data.batchId} (${data.logs.length} logs)...`);
        const response = await api.post('/api/v1/telemetry/batch', data);
        console.log('[obdApi] Batch upload successful:', response.status);
    } catch (error) {
        console.error('[obdApi] Batch upload failed:', error);
        throw error;
    }
};

/**
 * 차량 연결 상태 조회
 * @param vehicleId - 차량 UUID
 */
export const getConnectionStatus = async (vehicleId: string): Promise<ApiResponse<ConnectionStatusResponse>> => {
    const response = await api.get(`/api/v1/telemetry/status/${vehicleId}`);
    return response.data;
};

/**
 * 차량 연결 해제
 * @param vehicleId - 차량 UUID
 */
export const disconnectVehicle = async (vehicleId: string): Promise<void> => {
    await api.post(`/api/v1/telemetry/status/${vehicleId}/disconnect`);
};

export { obdDeviceApi };
