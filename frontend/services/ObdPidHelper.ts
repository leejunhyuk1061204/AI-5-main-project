export interface PidDefinition {
    mode: string;
    pid: string;
    name: string;
    description: string;
    bytes: number; // expected byte length of response data (excluding header)
    min?: number;
    max?: number;
    unit?: string;
    decoder: (bytes: number[]) => number | string;
}

export const OBD_PIDS: { [key: string]: PidDefinition } = {
    // 01 04: Calculated Engine Load
    ENGINE_LOAD: {
        mode: '01',
        pid: '04',
        name: 'Calculated Engine Load',
        description: 'Calculated Engine Load',
        bytes: 1,
        min: 0,
        max: 100,
        unit: '%',
        decoder: (bytes) => (bytes[0] * 100) / 255
    },
    // 01 05: Engine Coolant Temperature
    COOLANT_TEMP: {
        mode: '01',
        pid: '05',
        name: 'Engine Coolant Temperature',
        description: 'Engine Coolant Temperature',
        bytes: 1,
        min: -40,
        max: 215,
        unit: '°C',
        decoder: (bytes) => bytes[0] - 40
    },
    // 01 06: Short Term Fuel Trim - Bank 1
    FUEL_TRIM_SHORT: {
        mode: '01',
        pid: '06',
        name: 'Short Term Fuel Trim - Bank 1',
        description: 'Short Term Fuel Trim - Bank 1',
        bytes: 1,
        min: -100,
        max: 99.2,
        unit: '%',
        decoder: (bytes) => (bytes[0] - 128) * 100 / 128
    },
    // 01 07: Long Term Fuel Trim - Bank 1
    FUEL_TRIM_LONG: {
        mode: '01',
        pid: '07',
        name: 'Long Term Fuel Trim - Bank 1',
        description: 'Long Term Fuel Trim - Bank 1',
        bytes: 1,
        min: -100,
        max: 99.2,
        unit: '%',
        decoder: (bytes) => (bytes[0] - 128) * 100 / 128
    },
    // 01 0C: Engine RPM
    RPM: {
        mode: '01',
        pid: '0C',
        name: 'Engine RPM',
        description: 'Engine RPM',
        bytes: 2,
        min: 0,
        max: 16383,
        unit: 'rpm',
        decoder: (bytes) => ((bytes[0] * 256) + bytes[1]) / 4
    },
    // 01 0D: Vehicle Speed
    SPEED: {
        mode: '01',
        pid: '0D',
        name: 'Vehicle Speed',
        description: 'Vehicle Speed',
        bytes: 1,
        min: 0,
        max: 255,
        unit: 'km/h',
        decoder: (bytes) => bytes[0]
    },
    // 01 42: Control Module Voltage
    VOLTAGE: {
        mode: '01',
        pid: '42',
        name: 'Control Module Voltage',
        description: 'Control Module Voltage',
        bytes: 2,
        min: 0,
        max: 65.535,
        unit: 'V',
        decoder: (bytes) => ((bytes[0] * 256) + bytes[1]) / 1000
    },
    // 09 02: VIN (Vehicle Identification Number)
    VIN: {
        mode: '09',
        pid: '02',
        name: 'VIN',
        description: 'Vehicle Identification Number (17 characters)',
        bytes: 20, // VIN은 여러 프레임으로 응답됨
        unit: '',
        decoder: (bytes) => {
            // VIN은 ASCII 문자로 변환
            // 첫 번째 바이트는 메시지 카운트이므로 건너뜀
            const vinBytes = bytes.slice(1);
            let vin = '';
            for (const byte of vinBytes) {
                if (byte >= 0x20 && byte <= 0x7E) { // 출력 가능한 ASCII
                    vin += String.fromCharCode(byte);
                }
            }
            return vin.trim();
        }
    }
};

export const parseObdResponse = (hexResponse: string, pidDef: PidDefinition): number | string | null => {
    // Basic cleaning of response (remove spaces, newlines, prompt '>')
    const cleanResponse = hexResponse.replace(/[\s\r\n>]/g, '');

    // Check if valid response (usually starts with 41 + PID for Mode 01)
    // Mode 01 request -> 41 response
    const expectedPrefix = (parseInt(pidDef.mode, 16) + 0x40).toString(16).toUpperCase() + pidDef.pid;

    if (!cleanResponse.includes(expectedPrefix)) {
        // console.warn(`Invalid response for PID ${pidDef.pid}: ${hexResponse}`);
        return null;
    }

    // Extract data bytes after the prefix
    const dataIndex = cleanResponse.indexOf(expectedPrefix) + expectedPrefix.length;
    const dataHex = cleanResponse.substring(dataIndex);

    // Convert hex string to byte array
    const bytes = [];
    for (let i = 0; i < dataHex.length; i += 2) {
        bytes.push(parseInt(dataHex.substr(i, 2), 16));
    }

    if (bytes.length < pidDef.bytes) {
        return null;
    }

    return pidDef.decoder(bytes);
};
