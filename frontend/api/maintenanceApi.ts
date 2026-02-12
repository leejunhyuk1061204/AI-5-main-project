import api from './axios';

// Type Definitions
export interface VehicleConsumable {
    itemCode: string; // Enum Code (e.g., ENGINE_OIL)
    itemDescription: string; // Display Name
    consumableItemId: number;
    remainingLifePercent: number;
    lastMaintenanceDate: string | null;
    lastMaintenanceMileage: number;
    replacementIntervalMileage: number | null;
    replacementIntervalMonths: number | null;
    predictedReplacementDate: string | null;
    unevenWearDetected?: boolean;
}

export interface MaintenanceStatusResponse {
    success: boolean;
    data: VehicleConsumable[] | null;
    message: string | null;
}

const getConsumableStatus = async (vehicleId: string): Promise<MaintenanceStatusResponse> => {
    try {
        const response = await api.get(`/api/v1/vehicles/${vehicleId}/consumables`);
        return response.data;
    } catch (error) {
        console.error('Error fetching consumable status:', error);
        return {
            success: false,
            data: null,
            message: 'Failed to fetch consumable status'
        };
    }
};

const recordMaintenanceBatch = async (vehicleId: string, items: { itemCode: string, lastReplacementDate?: string, lastReplacementMileage?: number }[]): Promise<boolean> => {
    try {
        const payload = items.map(item => ({
            maintenanceDate: item.lastReplacementDate,
            mileageAtMaintenance: item.lastReplacementMileage,
            consumableItemCode: item.itemCode,
            isStandardized: true
        }));
        await api.post(`/api/v1/vehicles/${vehicleId}/maintenance`, payload);
        return true;
    } catch (error: any) {
        console.error('Error recording batch maintenance:', error);
        throw new Error(error.response?.data?.error?.message || '정비 이력 등록 중 오류가 발생했습니다.');
    }
};

// 정비 이력 응답 타입
export interface MaintenanceHistoryResponse {
    maintenanceId: string;
    vehicleId: string;
    maintenanceDate: string;
    mileageAtMaintenance: number;
    consumableItemCode: string;
    consumableItemName?: string;
    isStandardized: boolean;
    createdAt?: string;
}

// 정비 이력 조회
const getMaintenanceHistory = async (vehicleId: string): Promise<MaintenanceHistoryResponse[]> => {
    try {
        const response = await api.get(`/api/v1/vehicles/${vehicleId}/maintenance`);
        return response.data.data || [];
    } catch (error) {
        console.error('Error fetching maintenance history:', error);
        return [];
    }
};

export default {
    getConsumableStatus,
    recordMaintenanceBatch,
    getMaintenanceHistory
};
