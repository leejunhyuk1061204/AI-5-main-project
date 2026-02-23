import { create } from 'zustand';
import { getManufacturers, getModels, getModelYears, getAvailableFuelTypes, ConsumableMaster, CarModelDto } from '../api/masterApi';
import { registerVehicle } from '../api/vehicleApi';
import maintenanceApi from '../api/maintenanceApi';
import { useVehicleStore } from './useVehicleStore';
import { useConsumableStore } from './useConsumableStore';

interface RegistrationState {
    // Step 1: Vehicle Info
    vehicleNumber: string;
    vin: string;
    manufacturer: string;
    manufacturerEn: string;
    modelName: string;
    modelNameEn: string;
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
    modelsFull: CarModelDto[];
    years: string[];
    availableFuels: string[];

    // UI State
    isLoading: boolean;

    // Actions
    setVehicleInfo: (field: string, value: string) => void;
    setModelSelection: (modelNameKo: string) => void;
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
    manufacturerEn: '',
    modelName: '',
    modelNameEn: '',
    modelYear: '',
    fuelType: '',
    totalMileage: '',
    maintenanceRecords: [],

    manufacturers: [],
    models: [],
    modelsFull: [],
    years: [],
    availableFuels: [],

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
        set({ isLoading: true, years: [], availableFuels: [] });
        try {
            const data = await getModels(make);
            const distinctModelNames = [...new Set(data.map((d) => d.modelNameKo))];
            const manufacturerEn = data.length > 0 ? (data[0].manufacturerEn ?? '') : '';
            set({
                modelsFull: data,
                models: distinctModelNames,
                manufacturerEn,
                modelNameEn: ''
            });
        } catch (e) {
            console.error(e);
        } finally {
            set({ isLoading: false });
        }
    },

    setModelSelection: (modelNameKo) => {
        const { modelsFull } = get();
        const match = modelsFull.find((d) => d.modelNameKo === modelNameKo);
        const modelNameEn = match?.modelNameEn ?? '';
        set({ modelName: modelNameKo, modelNameEn, availableFuels: [] });
    },

    loadYears: async (make, model) => {
        set({ isLoading: true, availableFuels: [] });
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
        await useConsumableStore.getState().loadConsumableMaster();
    },

    registerAll: async () => {
        const s = get();
        set({ isLoading: true });

        try {
            // 1. Prepare Consumables Data
            const validConsumables = s.maintenanceRecords
                .filter(r => r.lastReplacementDate || r.lastReplacementMileage)
                .map(r => ({
                    code: r.itemCode,
                    maintenanceDate: r.lastReplacementDate || undefined,
                    lastReplacedMileage: r.lastReplacementMileage ? parseInt(r.lastReplacementMileage) : undefined
                }));

            // 2. Register Vehicle & Consumables together (영문 포함 전송, 백엔드 fallback 보완)
            await registerVehicle({
                manufacturerKo: s.manufacturer,
                manufacturerEn: s.manufacturerEn || undefined,
                modelNameKo: s.modelName,
                modelNameEn: s.modelNameEn || undefined,
                modelYear: parseInt(s.modelYear),
                fuelType: s.fuelType as any,
                carNumber: s.vehicleNumber,
                totalMileage: s.totalMileage ? parseInt(s.totalMileage.replace(/,/g, '')) : 0,
                memo: s.vin ? `VIN: ${s.vin}` : undefined,
                nickname: `${s.manufacturer} ${s.modelName}`,
                consumables: validConsumables.length > 0 ? validConsumables : undefined
            });

            // 3. Refresh Global Vehicle Store
            await useVehicleStore.getState().fetchVehicles();

            // 4. Reset Registration Store
            get().reset();

            return { success: true };
        } catch (e: any) {
            console.error("Registration Failed", e);
            const errorMessage = e.response?.data?.error?.message || e.message || '등록에 실패했습니다.';
            return { success: false, message: errorMessage };
        } finally {
            set({ isLoading: false });
        }
    },

    reset: () => {
        set({
            vehicleNumber: '',
            vin: '',
            manufacturer: '',
            manufacturerEn: '',
            modelName: '',
            modelNameEn: '',
            modelYear: '',
            fuelType: '',
            totalMileage: '',
            maintenanceRecords: [],
            models: [],
            modelsFull: [],
            years: [],
            availableFuels: []
        });
    },

    addDefaultConsumables: () => {
        const { maintenanceRecords, addMaintenanceRecord } = get();
        if (maintenanceRecords.length > 0) return;

        const consumableMasterList = useConsumableStore.getState().consumableMasterList;
        const getConsumableMasterItem = useConsumableStore.getState().getConsumableMasterItem;
        const defaultCode = 'ENGINE_OIL';
        const item = consumableMasterList.find(c => c.code === defaultCode) ?? getConsumableMasterItem(defaultCode);
        if (item) addMaintenanceRecord(item);
    }
}));
