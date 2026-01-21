// Web Mock for ClassicBtService
// Native modules cause crashes on web, so we provide an empty implementation.

export interface BluetoothDevice {
    name: string;
    address: string;
    id: string;
    class: number;
    isConnected: () => Promise<boolean>;
    connect: (options?: any) => Promise<boolean>;
    disconnect: () => Promise<boolean>;
    write: (data: any) => Promise<boolean>;
    read: () => Promise<string>;
    available: () => Promise<number>;
    onDataReceived: (listener: (event: any) => void) => { remove: () => void };
}

class ClassicBtService {
    initialize() {
        console.log('[ClassicBtService-Web] Initialize (Mock)');
        return Promise.resolve();
    }

    async requestPermissions(): Promise<boolean> {
        return true;
    }

    async getBondedDevices(): Promise<BluetoothDevice[]> {
        return [];
    }

    async connect(device: BluetoothDevice): Promise<boolean> {
        console.log('[ClassicBtService-Web] connect (Mock)');
        return false;
    }

    async disconnect(device: BluetoothDevice): Promise<boolean> {
        return true;
    }

    async write(device: BluetoothDevice, command: string): Promise<boolean> {
        return false;
    }

    async read(device: BluetoothDevice): Promise<string> {
        return '';
    }

    async readAvailable(device: BluetoothDevice): Promise<string> {
        return '';
    }

    onDataReceived(device: BluetoothDevice, callback: (data: string) => void) {
        return { remove: () => { } };
    }
}

export default new ClassicBtService();
