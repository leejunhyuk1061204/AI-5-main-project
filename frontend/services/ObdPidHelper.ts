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
    // --- 보조 지표 (Ircama car 지원, 실차 진단/모니터링용) ---
    // 01 03: Fuel system status
    FUEL_STATUS: {
        mode: '01',
        pid: '03',
        name: 'Fuel System Status',
        description: 'Fuel system status (Open/Closed Loop)',
        bytes: 2,
        decoder: (bytes) => {
            const status = (v: number) => ['Unused', 'Open', 'Closed', 'Open (drive)', 'Closed (drive)'][v] ?? `0x${v.toString(16)}`;
            const s1 = bytes[0] & 0x0F;
            const s2 = (bytes[0] >> 4) & 0x0F;
            return `${status(s1)} / ${status(s2)}`;
        }
    },
    // 01 0E: Timing advance
    TIMING_ADVANCE: {
        mode: '01',
        pid: '0E',
        name: 'Timing Advance',
        description: 'Ignition timing advance',
        bytes: 1,
        unit: '°',
        decoder: (bytes) => (bytes[0] / 2) - 64
    },
    // 01 1C: OBD compliance
    OBD_COMPLIANCE: {
        mode: '01',
        pid: '1C',
        name: 'OBD Compliance',
        description: 'OBD standards compliance',
        bytes: 1,
        decoder: (bytes) => {
            const v = bytes[0];
            const map: Record<number, string> = { 1: 'OBD-II', 2: 'OBD', 3: 'EOBD', 4: 'EOBD-II', 5: 'JOBD', 6: 'OBD-III' };
            return map[v] ?? `0x${v.toString(16)}`;
        }
    },
    // 01 21: Distance with MIL on
    DISTANCE_W_MIL: {
        mode: '01',
        pid: '21',
        name: 'Distance with MIL',
        description: 'Distance traveled with MIL on',
        bytes: 2,
        unit: 'km',
        decoder: (bytes) => (bytes[0] * 256) + bytes[1]
    },
    // 01 31: Distance since DTC clear
    DISTANCE_SINCE_DTC_CLEAR: {
        mode: '01',
        pid: '31',
        name: 'Distance since DTC clear',
        description: 'Distance traveled since codes cleared',
        bytes: 2,
        unit: 'km',
        decoder: (bytes) => (bytes[0] * 256) + bytes[1]
    },
    // 01 33: Barometric pressure
    BAROMETRIC_PRESSURE: {
        mode: '01',
        pid: '33',
        name: 'Barometric Pressure',
        description: 'Barometric pressure',
        bytes: 1,
        unit: 'kPa',
        decoder: (bytes) => bytes[0]
    },
    // 01 3C: Catalyst temp B1S1
    CATALYST_TEMP_B1S1: {
        mode: '01',
        pid: '3C',
        name: 'Catalyst Temp B1S1',
        description: 'Catalyst temperature bank 1 sensor 1',
        bytes: 2,
        unit: '°C',
        decoder: (bytes) => ((bytes[0] * 256) + bytes[1]) / 10 - 40
    },
    // 01 43: Absolute load
    ABSOLUTE_LOAD: {
        mode: '01',
        pid: '43',
        name: 'Absolute Load',
        description: 'Absolute load value',
        bytes: 2,
        unit: '%',
        decoder: (bytes) => ((bytes[0] * 256) + bytes[1]) * 100 / 255
    },
    // 01 4E: Time since DTC cleared
    TIME_SINCE_DTC_CLEARED: {
        mode: '01',
        pid: '4E',
        name: 'Time since DTC clear',
        description: 'Time since trouble codes cleared',
        bytes: 2,
        unit: 'min',
        decoder: (bytes) => (bytes[0] * 256) + bytes[1]
    },
    // 01 51: Fuel type
    FUEL_TYPE: {
        mode: '01',
        pid: '51',
        name: 'Fuel Type',
        description: 'Fuel type',
        bytes: 1,
        decoder: (bytes) => {
            const v = bytes[0];
            const map: Record<number, string> = { 0: 'Not available', 1: 'Gasoline', 2: 'Methanol', 3: 'Ethanol', 4: 'Diesel', 5: 'LPG', 6: 'CNG', 7: 'Propane', 8: 'Electric', 9: 'Bifuel' };
            return map[v] ?? `0x${v.toString(16)}`;
        }
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
        // 최소 1프레임(헤더 1바이트 + VIN 17바이트 = 18바이트)만 오더라도 파싱 가능하도록 18로 설정
        bytes: 18,
        unit: '',
        decoder: (bytes) => {
            const vinBytes = bytes.slice(1);
            let vin = '';
            for (const byte of vinBytes) {
                if (byte >= 0x20 && byte <= 0x7E) {
                    vin += String.fromCharCode(byte);
                }
            }
            return vin.trim();
        }
    },
    // 09 04: Calibration ID (CALID)
    CALID: {
        mode: '09',
        pid: '04',
        name: 'Calibration ID',
        description: 'ECU calibration/software ID',
        bytes: 4,
        unit: '',
        decoder: (bytes) => {
            const data = bytes.slice(1);
            const ascii = data.map((b) => (b >= 0x20 && b <= 0x7E) ? String.fromCharCode(b) : '').join('').trim();
            if (ascii.length > 0) return ascii;
            return data.map((b) => b.toString(16).padStart(2, '0')).join('');
        }
    },
    // 09 06: Calibration Verification Number (CVN)
    CVN: {
        mode: '09',
        pid: '06',
        name: 'CVN',
        description: 'Calibration Verification Number',
        bytes: 4,
        unit: '',
        decoder: (bytes) => {
            const data = bytes.slice(1);
            return data.map((b) => b.toString(16).padStart(2, '0')).join('');
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
