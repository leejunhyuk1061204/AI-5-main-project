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
}

const tripApi = {
    // [BE-TD-005] 주행 이력 목록 조회
    getTrips: async (vehicleId: string): Promise<ApiResponse<TripSummary[]>> => {
        try {
            const response = await api.get(`/trips?vehicleId=${vehicleId}`);
            return response.data;
        } catch (error) {
            console.error('Error fetching trips:', error);
            throw error;
        }
    },

    // [BE-TD-005] 주행 이력 상세 조회
    getTripDetail: async (tripId: string): Promise<ApiResponse<TripSummary>> => {
        try {
            const response = await api.get(`/trips/${tripId}`);
            return response.data;
        } catch (error) {
            console.error('Error fetching trip detail:', error);
            throw error;
        }
    }
};

export default tripApi;
