// Web Mock for BleService
// Native modules cause crashes on web, so we provide an empty implementation.

export interface Peripheral {
    id: string;
    rssi: number;
    name?: string;
    advertising: any;
}

class BleService {
    isInitialized = false;

    initialize() {
        console.log('[BleService-Web] Initialize (Mock)');
        this.isInitialized = true;
    }

    async requestPermissions() {
        return true;
    }

    async startScan() {
        console.log('[BleService-Web] startScan (Mock)');
        return Promise.resolve();
    }

    stopScan() {
        console.log('[BleService-Web] stopScan (Mock)');
        return Promise.resolve();
    }

    connect(id: string) {
        console.log('[BleService-Web] connect (Mock)', id);
        return Promise.resolve();
    }

    createBond(id: string) {
        return Promise.resolve();
    }

    removeBond(id: string) {
        return Promise.resolve();
    }

    disconnect(id: string) {
        console.log('[BleService-Web] disconnect (Mock)', id);
        return Promise.resolve();
    }

    retrieveServices(id: string) {
        return Promise.resolve({ characteristics: [] });
    }

    async startNotification(id: string, serviceUUID: string, charUUID: string) {
        return Promise.resolve();
    }

    getBondedPeripherals() {
        return Promise.resolve([]);
    }

    isPeripheralConnected(id: string, serviceUUIDs: string[] = []) {
        return Promise.resolve(false);
    }

    addListener(eventType: string, listener: (data: any) => void) {
        return { remove: () => { } };
    }

    removeListeners() {
        // no-op
    }

    stringToBytes(string: string) {
        const array = new Uint8Array(string.length);
        for (let i = 0, l = string.length; i < l; i++) {
            array[i] = string.charCodeAt(i);
        }
        return Array.from(array);
    }

    async write(id: string, serviceUUID: string, charUUID: string, command: string) {
        return Promise.resolve();
    }
}

export default new BleService();
