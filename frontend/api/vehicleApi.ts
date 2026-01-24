import api from './axios';

// 차량 정보 타입 (백엔드 VehicleDto.Response 매칭)
export interface VehicleResponse {
    vehicleId: string;
    userId: string;
    manufacturer: string;
    modelName: string;
    modelYear: number;
    fuelType: 'GASOLINE' | 'DIESEL' | 'LPG' | 'EV' | 'HEV' | null;
    totalMileage: number;
    carNumber: string | null;
    nickname: string | null;
    memo: string | null;
    isPrimary: boolean;
    registrationSource: 'MANUAL' | 'OBD' | 'CLOUD';
    obdDeviceId: string | null;

    // Spec info
    length?: number;
    width?: number;
    height?: number;
    displacement?: number;
    engineType?: string;
    maxPower?: number;
    maxTorque?: number;
    tireSizeFront?: string;
    tireSizeRear?: string;
    officialFuelEconomy?: number;

    // Added
    vin: string | null;
}

// OBD 기반 차량 등록 요청
export interface ObdRegistrationRequest {
    vin: string;
}

// 수동 차량 등록 요청
export interface ManualRegistrationRequest {
    manufacturer: string;
    modelName: string;
    modelYear: number;
    fuelType: 'GASOLINE' | 'DIESEL' | 'LPG' | 'EV' | 'HEV';
    totalMileage?: number;
    carNumber?: string;
    nickname?: string;
    memo?: string;
    obdDeviceId?: string;
}

// 차량 정보 수정 요청
export interface VehicleUpdateRequest {
    nickname?: string;
    memo?: string;
    carNumber?: string;
    vin?: string;
}

/**
 * 사용자의 모든 차량 목록 조회
 */
export const getVehicleList = async (): Promise<VehicleResponse[]> => {
    try {
        const response = await api.get('/api/v1/vehicles');
        console.log('[vehicleApi] Vehicle list fetched:', response.data);
        return response.data.data || [];
    } catch (error) {
        console.error('[vehicleApi] Failed to fetch vehicle list:', error);
        throw error;
    }
};

/**
 * 특정 차량 상세 정보 조회
 */
export const getVehicleDetail = async (vehicleId: string): Promise<VehicleResponse> => {
    const response = await api.get(`/api/v1/vehicles/${vehicleId}`);
    return response.data.data;
};

/**
 * OBD 기반 차량 자동 등록 (VIN으로 차종 자동 식별)
 */
export const registerVehicleByObd = async (vin: string): Promise<VehicleResponse> => {
    try {
        console.log('[vehicleApi] Registering vehicle by OBD with VIN:', vin);
        const response = await api.post('/api/v1/vehicles/obd', { vin });
        console.log('[vehicleApi] Vehicle registered:', response.data);
        return response.data.data;
    } catch (error) {
        console.error('[vehicleApi] OBD registration failed:', error);
        throw error;
    }
};

/**
 * 수동 차량 등록
 */
export const registerVehicle = async (request: ManualRegistrationRequest): Promise<VehicleResponse> => {
    const response = await api.post('/api/v1/vehicles', request);
    return response.data.data;
};

/**
 * 차량 정보 수정
 */
export const updateVehicle = async (vehicleId: string, request: VehicleUpdateRequest): Promise<VehicleResponse> => {
    const response = await api.put(`/api/v1/vehicles/${vehicleId}`, request);
    return response.data.data;
};

/**
 * 대표 차량으로 설정
 */
export const setPrimaryVehicle = async (vehicleId: string): Promise<void> => {
    try {
        console.log('[vehicleApi] Setting primary vehicle:', vehicleId);
        await api.patch('/api/v1/vehicles/primary', { vehicleId });
        console.log('[vehicleApi] Primary vehicle set successfully');
    } catch (error) {
        console.error('[vehicleApi] Failed to set primary vehicle:', error);
        throw error;
    }
};

/**
 * 차량 삭제
 */
export const deleteVehicle = async (vehicleId: string): Promise<void> => {
    await api.delete(`/api/v1/vehicles/${vehicleId}`);
};
