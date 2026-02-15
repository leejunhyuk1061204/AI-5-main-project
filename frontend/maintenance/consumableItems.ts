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

export function isPositionTypeCode(code: string): boolean {
    return code === 'TIRE_POSITION' || code === 'BRAKE_POSITION';
}

export function getPositionOptions(code: string): { code: string; name: string }[] {
    return code === 'TIRE_POSITION' ? TIRE_POSITION_OPTIONS : BRAKE_POSITION_OPTIONS;
}
