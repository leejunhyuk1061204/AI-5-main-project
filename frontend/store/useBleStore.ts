import { create } from 'zustand';

export interface BleDevice {
    id: string;
    name?: string | null;
    rssi?: number;
    advertising?: any;
}

export type ConnectionStatus = 'disconnected' | 'scanning' | 'connecting' | 'connected';

interface BleState {
    status: ConnectionStatus;
    isScanning: boolean;
    isPolling: boolean; // OBD Polling Status
    connectedDeviceId: string | null;
    connectedDeviceName: string | null; // For UI display
    scannedDevices: BleDevice[];
    error: string | null;

    // Actions
    setStatus: (status: ConnectionStatus) => void;
    setScanning: (isScanning: boolean) => void;
    setPolling: (isPolling: boolean) => void;
    setConnectedDevice: (deviceId: string | null) => void;
    setConnectedDeviceName: (name: string | null) => void;
    addDevice: (device: BleDevice) => void;
    clearDevices: () => void;
    setError: (error: string | null) => void;
    reset: () => void;
}

export const useBleStore = create<BleState>((set) => ({
    status: 'disconnected',
    isScanning: false,
    isPolling: false,
    connectedDeviceId: null,
    connectedDeviceName: null,
    scannedDevices: [],
    error: null,

    setStatus: (status) => set({ status }),
    setScanning: (isScanning) => set({ isScanning }),
    setPolling: (isPolling) => set({ isPolling }),
    setConnectedDevice: (connectedDeviceId) => set({ connectedDeviceId }),
    setConnectedDeviceName: (connectedDeviceName) => set({ connectedDeviceName }),

    addDevice: (newDevice) => set((state) => {
        // 중복 제거 (기존에 있으면 업데이트, 없으면 추가)
        const exists = state.scannedDevices.some(d => d.id === newDevice.id);
        if (exists) {
            return {
                scannedDevices: state.scannedDevices.map(d =>
                    d.id === newDevice.id ? { ...d, ...newDevice } : d
                )
            };
        }
        return { scannedDevices: [...state.scannedDevices, newDevice] };
    }),

    clearDevices: () => set({ scannedDevices: [] }),
    setError: (error) => set({ error }),
    reset: () => set({
        status: 'disconnected',
        isScanning: false,
        isPolling: false,
        connectedDeviceId: null,
        connectedDeviceName: null,
        scannedDevices: [],
        error: null
    })
}));
