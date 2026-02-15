import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { VehicleResponse } from '../api/vehicleApi';

interface VehicleState {
    primaryVehicle: Partial<VehicleResponse> | null;
    vehicles: VehicleResponse[];
    isLoading: boolean;

    setPrimaryVehicle: (vehicle: Partial<VehicleResponse>) => Promise<void>;
    setVehicles: (vehicles: VehicleResponse[]) => void;
    fetchVehicles: () => Promise<VehicleResponse[]>;
    loadFromStorage: () => Promise<void>;
    clearVehicle: () => Promise<void>;
    reset: () => Promise<void>;
}

export const useVehicleStore = create<VehicleState>((set, get) => ({
    primaryVehicle: null,
    vehicles: [],
    isLoading: true,

    setPrimaryVehicle: async (vehicle) => {
        set({ primaryVehicle: vehicle });
        await AsyncStorage.setItem('primaryVehicle', JSON.stringify(vehicle));
    },

    setVehicles: (vehicles) => {
        const sorted = [...vehicles].sort((a, b) => (b.isPrimary ? 1 : 0) - (a.isPrimary ? 1 : 0));
        set({ vehicles: sorted });
        // Update primary vehicle if needed
        if (vehicles.length > 0) {
            const currentPrimary = get().primaryVehicle;
            if (!currentPrimary) {
                const primary = vehicles.find((v: VehicleResponse) => v.isPrimary) || vehicles[0];
                get().setPrimaryVehicle(primary);
            }
        }
    },

    fetchVehicles: async () => {
        set({ isLoading: true });
        try {
            const { getVehicleList } = require('../api/vehicleApi');
            const data = await getVehicleList();
            const sorted = [...data].sort((a, b) => (b.isPrimary ? 1 : 0) - (a.isPrimary ? 1 : 0));
            set({ vehicles: sorted });

            // 대표 차량이 설정되어 있지 않다면 첫 번째 차량이나 isPrimary인 차량을 설정
            if (data.length > 0) {
                const primary = data.find((v: VehicleResponse) => v.isPrimary) || data[0];
                set({ primaryVehicle: primary });
                await AsyncStorage.setItem('primaryVehicle', JSON.stringify(primary));
            } else {
                set({ primaryVehicle: null });
                await AsyncStorage.removeItem('primaryVehicle');
            }

            // 차량 목록과 함께 소모품 마스터 로드 (앱 전역에서 한 시점에)
            const { useConsumableStore } = require('./useConsumableStore');
            useConsumableStore.getState().loadConsumableMaster().catch(() => {});

            return data;
        } catch (e) {
            console.error('Failed to fetch vehicles', e);
            throw e; // 에러를 상위로 전파하여 App.tsx가 로그인 화면으로 이동할 수 있게 함
        } finally {
            set({ isLoading: false });
        }
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
    },

    reset: async () => {
        set({
            primaryVehicle: null,
            vehicles: [],
            isLoading: false
        });
        await AsyncStorage.removeItem('primaryVehicle');
    }
}));
