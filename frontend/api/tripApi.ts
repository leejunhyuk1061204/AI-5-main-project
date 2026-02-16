import api from './axios';
import { ApiResponse } from './axios';

export interface TripSummary {
    startTime: string; // ISO string
    vehicleId: string;
    tripId: string;
    endTime: string; // ISO string
    distance: number;
    driveScore: number;
    averageSpeed: number;
    topSpeed: number;
    fuelConsumed: number;

    // Detailed stats
    minBatteryVoltage?: number;
    maxCoolantTemp?: number;
    avgFuelTrim?: number;
    maxEngineLoad?: number;
    idleTime?: number;
    hardAccelCount?: number;
    hardBrakeCount?: number;
    avgRpm?: number;
    avgEngineLoad?: number;
    avgMaf?: number;
    avgThrottlePos?: number;
    overheatDurationSec?: number;
}

export interface TripObdLogDto {
    timestamp: string;
    rpm?: number;
    speed?: number;
    voltage?: number;
    coolantTemp?: number;
    engineLoad?: number;
    fuelTrimShort?: number;
    fuelTrimLong?: number;
    throttlePos?: number;
    map?: number;
    maf?: number;
    intakeTemp?: number;
    engineRuntime?: number;
}

const tripApi = {
    // [BE-TD-005] 주행 이력 목록 조회
    getTrips: async (vehicleId: string): Promise<ApiResponse<TripSummary[]>> => {
        try {
            const response = await api.get(`/api/v1/trips?vehicleId=${vehicleId}`);
            return response.data;
        } catch (error) {
            console.error('Error fetching trips:', error);
            throw error;
        }
    },

    // [BE-TD-005] 주행 이력 상세 조회
    getTripDetail: async (tripId: string): Promise<ApiResponse<TripSummary>> => {
        try {
            const response = await api.get(`/api/v1/trips/${tripId}`);
            return response.data;
        } catch (error) {
            console.error('Error fetching trip detail:', error);
            throw error;
        }
    },

    /** 주행 구간 OBD 로그 조회 (CSV 내보내기용) */
    getTripObdLogs: async (tripId: string): Promise<ApiResponse<TripObdLogDto[]>> => {
        try {
            const response = await api.get(`/api/v1/trips/${tripId}/obd-logs`);
            return response.data;
        } catch (error) {
            console.error('Error fetching trip OBD logs:', error);
            throw error;
        }
    },

    // [BE-TD-001] 주행 세션 시작
    startTrip: async (vehicleId: string): Promise<ApiResponse<TripSummary>> => {
        try {
            const response = await api.post('/api/v1/trips/start', { vehicleId });
            return response.data;
        } catch (error) {
            console.error('Error starting trip:', error);
            throw error;
        }
    },

    // [BE-TD-004] 주행 세션 종료
    endTrip: async (tripId: string): Promise<ApiResponse<TripSummary>> => {
        try {
            const response = await api.post('/api/v1/trips/end', { tripId });
            return response.data;
        } catch (error) {
            console.error('Error ending trip:', error);
            throw error;
        }
    },

    /** 주행 차량 재할당 (해당 주행 + OBD 로그를 새 차량으로 이전, 통계 재집계) */
    changeTripVehicle: async (tripId: string, newVehicleId: string): Promise<ApiResponse<TripSummary>> => {
        try {
            const response = await api.patch(`/api/v1/trips/${tripId}/vehicle`, { newVehicleId });
            return response.data;
        } catch (error) {
            console.error('Error changing trip vehicle:', error);
            throw error;
        }
    }
};

export default tripApi;
