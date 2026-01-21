// Web Mock for ObdService
// Native modules cause crashes on web.

export interface ObdData {
    timestamp: string;
    rpm?: number;
    speed?: number;
    voltage?: number;
    coolant_temp?: number;
    engine_load?: number;
    fuel_trim_short?: number;
    fuel_trim_long?: number;
}

class ObdService {
    setClassicDevice(device: any) {
        console.log('[ObdService-Web] setClassicDevice (Mock)');
        return Promise.resolve();
    }

    setTargetDevice(deviceId: string) {
        console.log('[ObdService-Web] setTargetDevice (Mock)');
        return Promise.resolve();
    }

    startPolling(intervalMs: number = 1000) {
        console.log('[ObdService-Web] startPolling (Mock)');
    }

    stopPolling() {
        console.log('[ObdService-Web] stopPolling (Mock)');
    }

    onData(callback: (data: ObdData) => void) {
        return () => { };
    }

    getCurrentData(): ObdData {
        return { timestamp: new Date().toISOString() };
    }

    setVehicleId(id: string) {
        console.log('[ObdService-Web] setVehicleId (Mock)');
    }

    async flushBuffer() {
        // no-op
    }

    async disconnect() {
        console.log('[ObdService-Web] disconnect (Mock)');
    }
}

export default new ObdService();
