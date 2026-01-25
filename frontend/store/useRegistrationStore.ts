import { create } from 'zustand';
import { getManufacturers, getModelNames, getModelYears, getAvailableFuelTypes, getAllConsumableItems, ConsumableMaster } from '../api/masterApi';
import { registerVehicle } from '../api/vehicleApi';
import maintenanceApi from '../api/maintenanceApi';
import { useVehicleStore } from './useVehicleStore';
import { Alert } from 'react-native'; // Simple alert for logic inside store if needed, or better use useAlertStore

interface RegistrationState {
    // Step 1: Vehicle Info
    vehicleNumber: string;
    vin: string;
    manufacturer: string;
    modelName: string;
    modelYear: string;
    fuelType: string;
    totalMileage: string;

    // Step 2: Maintenance Records
    // List of selected consumables with their last replacement info
    maintenanceRecords: {
        itemCode: string;
        itemName: string;
        icon?: string;
        lastReplacementDate?: string; // YYYY-MM-DD
        lastReplacementMileage?: string; // string for input, parse to number later
    }[];

    // Master Data Options
    manufacturers: string[];
    models: string[];
    years: string[];
    availableFuels: string[];
    consumableMasterList: ConsumableMaster[];

    // UI State
    isLoading: boolean;

    // Actions
    setVehicleInfo: (field: string, value: string) => void;
    addMaintenanceRecord: (item: ConsumableMaster) => void;
    removeMaintenanceRecord: (itemCode: string) => void;
    updateMaintenanceRecord: (itemCode: string, field: 'date' | 'mileage', value: string) => void;
    clearMaintenanceRecords: () => void;

    // API Actions
    loadManufacturers: () => Promise<void>;
    loadModels: (make: string) => Promise<void>;
    loadYears: (make: string, model: string) => Promise<void>;
    loadFuels: (make: string, model: string, year: string) => Promise<void>;
    loadConsumableMaster: () => Promise<void>;

    // Final Action
    registerAll: () => Promise<{ success: boolean; message?: string }>;
    reset: () => void;
    addDefaultConsumables: () => void;
}

export const useRegistrationStore = create<RegistrationState>((set, get) => ({
    // Initial State
    vehicleNumber: '',
    vin: '',
    manufacturer: '',
    modelName: '',
    modelYear: '',
    fuelType: '',
    totalMileage: '',
    maintenanceRecords: [],

    manufacturers: [],
    models: [],
    years: [],
    availableFuels: [],
    consumableMasterList: [],

    isLoading: false,

    setVehicleInfo: (field, value) => set((state) => ({ ...state, [field]: value })),

    addMaintenanceRecord: (item) => {
        const exists = get().maintenanceRecords.find(r => r.itemCode === item.code);
        if (exists) return; // Already added

        set((state) => ({
            maintenanceRecords: [
                ...state.maintenanceRecords,
                {
                    itemCode: item.code,
                    itemName: item.name,
                    icon: item.icon,
                    lastReplacementDate: '',
                    lastReplacementMileage: ''
                }
            ]
        }));
    },

    removeMaintenanceRecord: (itemCode) => {
        set((state) => ({
            maintenanceRecords: state.maintenanceRecords.filter(r => r.itemCode !== itemCode)
        }));
    },

    updateMaintenanceRecord: (itemCode, field, value) => {
        set((state) => ({
            maintenanceRecords: state.maintenanceRecords.map(r =>
                r.itemCode === itemCode
                    ? { ...r, [field === 'date' ? 'lastReplacementDate' : 'lastReplacementMileage']: value }
                    : r
            )
        }));
    },

    clearMaintenanceRecords: () => {
        set({ maintenanceRecords: [] });
    },

    loadManufacturers: async () => {
        set({ isLoading: true });
        try {
            const data = await getManufacturers();
            set({ manufacturers: data });
        } catch (e) {
            console.error(e);
        } finally {
            set({ isLoading: false });
        }
    },

    loadModels: async (make) => {
        set({ isLoading: true });
        try {
            const data = await getModelNames(make);
            set({ models: data });
        } catch (e) {
            console.error(e);
        } finally {
            set({ isLoading: false });
        }
    },

    loadYears: async (make, model) => {
        set({ isLoading: true });
        try {
            const data = await getModelYears(make, model);
            set({ years: data.map(String) });
        } catch (e) {
            console.error(e);
        } finally {
            set({ isLoading: false });
        }
    },

    loadFuels: async (make, model, year) => {
        set({ isLoading: true });
        try {
            const data = await getAvailableFuelTypes(make, model, parseInt(year));
            set({ availableFuels: data });
            // Auto-select if only 1
            /* Logic moved to component or keep here? Let's keep data only. */
        } catch (e) {
            console.error(e);
        } finally {
            set({ isLoading: false });
        }
    },

    loadConsumableMaster: async () => {
        // Cache check could be here
        if (get().consumableMasterList.length > 0) return;

        set({ isLoading: true });
        try {
            const data = await getAllConsumableItems();
            set({ consumableMasterList: data });
        } catch (e) {
            console.error(e);
        } finally {
            set({ isLoading: false });
        }
    },

    registerAll: async () => {
        const s = get();
        set({ isLoading: true });

        try {
            // 1. Register Vehicle
            const vehicleRes = await registerVehicle({
                manufacturer: s.manufacturer,
                modelName: s.modelName,
                modelYear: parseInt(s.modelYear),
                fuelType: s.fuelType as any, // Type assertion for now
                carNumber: s.vehicleNumber,
                totalMileage: s.totalMileage ? parseInt(s.totalMileage.replace(/,/g, '')) : 0, // Send totalMileage
                memo: s.vin ? `VIN: ${s.vin}` : undefined,
                nickname: `${s.manufacturer} ${s.modelName}`,
            });

            // Assuming vehicleRes returns the created vehicle object or ID directly
            // If it returns { success: true, data: { vehicleId: ... } }
            // Let's assume standard API response wrapper or check `registerVehicle` return type.
            // vehicleApi says: returns Promise<VehicleResponse> directly on success or throws?
            // Checking vehicleApi.ts again... `const response = await api.post... return response.data.data;`
            // So it returns the Vehicle object.

            const newVehicleId = vehicleRes.vehicleId;

            // 2. Register Maintenance Records (if any)
            if (s.maintenanceRecords.length > 0) {
                const maintenancePayload = s.maintenanceRecords.map(r => ({
                    itemCode: r.itemCode,
                    lastReplacementDate: r.lastReplacementDate || undefined,
                    lastReplacementMileage: r.lastReplacementMileage ? parseInt(r.lastReplacementMileage) : undefined
                }));

                await maintenanceApi.recordMaintenanceBatch(newVehicleId, maintenancePayload);
            }

            // 3. Refresh Global Vehicle Store
            await useVehicleStore.getState().fetchVehicles();

            // 4. Reset Registration Store
            get().reset();

            return { success: true };
        } catch (e: any) {
            console.error("Registration Failed", e);
            return { success: false, message: e.message || '등록에 실패했습니다.' };
        } finally {
            set({ isLoading: false });
        }
    },

    reset: () => {
        set({
            vehicleNumber: '',
            vin: '',
            manufacturer: '',
            modelName: '',
            modelYear: '',
            fuelType: '',
            totalMileage: '',
            maintenanceRecords: [],
            manufacturers: [],
            models: [],
            years: [],
            availableFuels: []
            // Keep consumableMasterList cached
        });
    },

    addDefaultConsumables: () => {
        const { maintenanceRecords, consumableMasterList, addMaintenanceRecord } = get();
        if (maintenanceRecords.length > 0) return;

        // Defined defaults with fallback data if missing in master
        const defaults = [
            { code: 'ENGINE_OIL', name: '엔진 오일', category: 'ENGINE', icon: 'oil-barrel' }
        ];

        defaults.forEach(def => {
            const item = consumableMasterList.find(c => c.code === def.code);
            if (item) {
                addMaintenanceRecord(item);
            } else {
                // Add as custom/fallback item if not in master
                addMaintenanceRecord({
                    ...def,
                    replacementCycleKm: 0,
                    replacementCycleMonth: 0
                } as ConsumableMaster);
            }
        });
    }
}));
