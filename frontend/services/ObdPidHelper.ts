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
    // 01 11: Absolute Throttle Position
    THROTTLE: {
        mode: '01',
        pid: '11',
        name: 'Throttle Position',
        description: 'Absolute Throttle Position',
        bytes: 1,
        min: 0,
        max: 100,
        unit: '%',
        decoder: (bytes) => (bytes[0] * 100) / 255
    },
    // 01 0B: Intake Manifold Absolute Pressure
    MAP: {
        mode: '01',
        pid: '0B',
        name: 'Intake MAP',
        description: 'Intake Manifold Absolute Pressure',
        bytes: 1,
        min: 0,
        max: 255,
        unit: 'kPa',
        decoder: (bytes) => bytes[0]
    },
    // 01 10: MAF Air Flow Rate
    MAF: {
        mode: '01',
        pid: '10',
        name: 'MAF Flow Rate',
        description: 'Mass Air Flow Rate',
        bytes: 2,
        min: 0,
        max: 655.35,
        unit: 'g/s',
        decoder: (bytes) => ((bytes[0] * 256) + bytes[1]) / 100
    },
    // 01 0F: Intake Air Temperature
    INTAKE_TEMP: {
        mode: '01',
        pid: '0F',
        name: 'Intake Temp',
        description: 'Intake Air Temperature',
        bytes: 1,
        min: -40,
        max: 215,
        unit: '°C',
        decoder: (bytes) => bytes[0] - 40
    },
    // 01 01: Monitor Status since DTCs cleared
    DTC_STATUS: {
        mode: '01',
        pid: '01',
        name: 'DTC Status',
        description: 'Monitor Status since DTCs cleared (includes MIL status)',
        bytes: 4,
        decoder: (bytes) => {
            // A7 = MIL status (1: ON, 0: OFF)
            const milOn = (bytes[0] & 0x80) > 0;
            const dtcCount = bytes[0] & 0x7F;
            return milOn ? `MIL ON (${dtcCount} DTCs)` : `MIL OFF (${dtcCount} DTCs)`;
        }
    },
    // 01 1F: Run time since engine start
    ENGINE_RUNTIME: {
        mode: '01',
        pid: '1F',
        name: 'Engine Runtime',
        description: 'Run time since engine start',
        bytes: 2,
        unit: 'sec',
        decoder: (bytes) => (bytes[0] * 256) + bytes[1]
    },
    // Mode 03: Request trouble codes
    GET_DTCS: {
        mode: '03',
        pid: '',
        name: 'Stored DTCs',
        description: 'Request stored trouble codes (Mode 03)',
        bytes: 2, // 최소 2바이트 (DTC 하나당 2바이트)
        decoder: (bytes) => {
            const dtcs = [];
            for (let i = 0; i < bytes.length; i += 2) {
                const b1 = bytes[i];
                const b2 = bytes[i + 1];
                if (b1 === 0 && b2 === 0) continue; // No DTC

                // 첫 2비트로 P, C, B, U 구분
                const typeCode = (b1 & 0xC0) >> 6;
                const prefix = ['P', 'C', 'B', 'U'][typeCode];
                const code = prefix +
                    ((b1 & 0x3F).toString(16).padStart(2, '0')) +
                    (b2.toString(16).padStart(2, '0'));
                dtcs.push(code.toUpperCase());
            }
            return dtcs.join(', ');
        }
    },
    // Mode 02 PID 02: DTC that caused freeze frame
    FREEZE_DTC: {
        mode: '02',
        pid: '0200', // PID 02, Frame 00
        name: 'Freeze Frame DTC',
        description: 'DTC that caused freeze frame storage',
        bytes: 2,
        decoder: (bytes) => {
            const b1 = bytes[0];
            const b2 = bytes[1];
            const typeCode = (b1 & 0xC0) >> 6;
            const prefix = ['P', 'C', 'B', 'U'][typeCode];
            return (prefix + ((b1 & 0x3F).toString(16).padStart(2, '0')) + (b2.toString(16).padStart(2, '0'))).toUpperCase();
        }
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

    // Check if valid response
    // Mode XX -> (XX + 0x40) response prefix
    const modeInt = parseInt(pidDef.mode, 16);
    const responsePrefix = (modeInt + 0x40).toString(16).toUpperCase();

    // Mode 03은 PID가 없으므로 prefix만 확인, 다른 모드는 PID까지 확인
    const expectedPrefix = pidDef.mode === '03' ? responsePrefix : responsePrefix + pidDef.pid.substring(0, 2);

    if (!cleanResponse.includes(expectedPrefix)) {
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
