import api from './axios';

// Type Definitions
export interface VehicleConsumable {
    item: string; // Enum Code (e.g., ENGINE_OIL)
    itemDescription: string; // Display Name
    consumableItemId: number;
    remainingLifePercent: number;
    lastMaintenanceDate: string | null;
    lastMaintenanceMileage: number;
    replacementIntervalMileage: number | null;
    replacementIntervalMonths: number | null;
    predictedReplacementDate: string | null;
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
        await api.post(`/api/v1/vehicles/${vehicleId}/maintenance`, items);
        return true;
    } catch (error) {
        console.error('Error recording batch maintenance:', error);
        return false;
    }
};

export default {
    getConsumableStatus,
    recordMaintenanceBatch
};
