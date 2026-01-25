import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { VehicleResponse } from '../api/vehicleApi';

interface VehicleState {
    primaryVehicle: Partial<VehicleResponse> | null;
    isLoading: boolean;

    setPrimaryVehicle: (vehicle: Partial<VehicleResponse>) => Promise<void>;
    loadFromStorage: () => Promise<void>;
    clearVehicle: () => Promise<void>;
}

export const useVehicleStore = create<VehicleState>((set) => ({
    primaryVehicle: null,
    isLoading: true,

    setPrimaryVehicle: async (vehicle) => {
        set({ primaryVehicle: vehicle });
        await AsyncStorage.setItem('primaryVehicle', JSON.stringify(vehicle));
    },

    loadFromStorage: async () => {
        set({ isLoading: true });
        try {
            const stored = await AsyncStorage.getItem('primaryVehicle');
            if (stored) {
                set({ primaryVehicle: JSON.parse(stored) });
            }
        } catch (e) {
            console.error('Failed to load vehicle from storage', e);
        } finally {
            set({ isLoading: false });
        }
    },

    clearVehicle: async () => {
        set({ primaryVehicle: null });
        await AsyncStorage.removeItem('primaryVehicle');
    }
}));
