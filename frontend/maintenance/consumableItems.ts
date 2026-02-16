/**
 * 타이어/브레이크 위치 옵션만 정의. 목록은 API → 수정(타이어·브레이크 합침) → useConsumableStore에 저장.
 */
export const TIRE_POSITION_OPTIONS: { code: string; name: string }[] = [
    { code: 'TIRE_FL', name: '앞왼쪽' },
    { code: 'TIRE_FR', name: '앞오른쪽' },
    { code: 'TIRE_RL', name: '뒤왼쪽' },
    { code: 'TIRE_RR', name: '뒤오른쪽' },
];

export const BRAKE_POSITION_OPTIONS: { code: string; name: string }[] = [
    { code: 'BRAKE_PAD_FRONT', name: '앞' },
    { code: 'BRAKE_PAD_REAR', name: '뒤' },
];

const TIRE_POSITION_CODES = ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'];
const BRAKE_POSITION_CODES = ['BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'];

export function isPositionTypeCode(code: string): boolean {
    return code === 'TIRE_POSITION' || code === 'BRAKE_POSITION';
}

/** 타이어/브레이크 개별 위치 코드 포함 (OCR이 TIRE_FL, BRAKE_PAD_FRONT 등 반환 시) */
export function isPositionTypeRow(code: string): boolean {
    return isPositionTypeCode(code) || TIRE_POSITION_CODES.includes(code) || BRAKE_POSITION_CODES.includes(code);
}

export function getPositionOptions(code: string): { code: string; name: string }[] {
    if (code === 'TIRE_POSITION' || TIRE_POSITION_CODES.includes(code)) return TIRE_POSITION_OPTIONS;
    if (code === 'BRAKE_POSITION' || BRAKE_POSITION_CODES.includes(code)) return BRAKE_POSITION_OPTIONS;
    return TIRE_POSITION_OPTIONS;
}
