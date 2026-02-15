import { create } from 'zustand';
import { getAllConsumableItems, ConsumableMaster } from '../api/masterApi';
import { TIRE_POSITION_OPTIONS, BRAKE_POSITION_OPTIONS } from '../maintenance/consumableItems';

const TIRE_CODES = ['TIRE_FL', 'TIRE_FR', 'TIRE_RL', 'TIRE_RR'];
const BRAKE_CODES = ['BRAKE_PAD_FRONT', 'BRAKE_PAD_REAR'];

/**
 * API 목록을 가져와 타이어 4개 → '타이어 (위치 선택)' 1개, 브레이크 2개 → '브레이크 패드 (위치 선택)' 1개로 수정한 뒤 저장.
 * seed 변경 시 API만 갱신하면 되고, 피커용 목록은 여기서 파생.
 */
function buildPickerListFromRaw(raw: ConsumableMaster[]): { code: string; name: string }[] {
    const rest = raw.filter(
        (m) => !TIRE_CODES.includes(m.code) && !BRAKE_CODES.includes(m.code)
    );
    const hasTire = raw.some((m) => TIRE_CODES.includes(m.code));
    const hasBrake = raw.some((m) => BRAKE_CODES.includes(m.code));

    const sorted = [...rest].sort(
        (a, b) => (a.replacementCycleKm ?? 999999) - (b.replacementCycleKm ?? 999999)
    );
    const picker: { code: string; name: string }[] = sorted.map((m) => ({ code: m.code, name: m.name }));
    if (hasTire) picker.push({ code: 'TIRE_POSITION', name: '타이어 (위치 선택)' });
    if (hasBrake) picker.push({ code: 'BRAKE_POSITION', name: '브레이크 패드 (위치 선택)' });
    return picker;
}

interface ConsumableState {
    /** API 원본 (이름/교체주기 조회용) */
    consumableMasterList: ConsumableMaster[];
    /** 타이어·브레이크 수정 후 피커용 목록 */
    consumablePickerList: { code: string; name: string }[];
    loaded: boolean;
    loadConsumableMaster: () => Promise<void>;
    getItemNameByCode: (code: string) => string;
    getConsumableMasterItem: (code: string) => ConsumableMaster | null;
}

export const useConsumableStore = create<ConsumableState>((set, get) => ({
    consumableMasterList: [],
    consumablePickerList: [],
    loaded: false,

    loadConsumableMaster: async () => {
        try {
            const raw = await getAllConsumableItems();
            const pickerList = buildPickerListFromRaw(raw);
            set({
                consumableMasterList: raw,
                consumablePickerList: pickerList,
                loaded: true,
            });
        } catch (e) {
            console.error('[useConsumableStore] loadConsumableMaster failed', e);
            set({ consumableMasterList: [], consumablePickerList: [], loaded: true });
        }
    },

    getItemNameByCode: (code: string) => {
        const list = get().consumableMasterList;
        const m = list.find((x) => x.code === code);
        if (m) return m.name;
        const tire = TIRE_POSITION_OPTIONS.find((x) => x.code === code);
        if (tire) return `타이어 ${tire.name}`;
        const brake = BRAKE_POSITION_OPTIONS.find((x) => x.code === code);
        if (brake) return `브레이크 패드 ${brake.name}`;
        return code || '기타 정비';
    },

    getConsumableMasterItem: (code: string): ConsumableMaster => {
        const list = get().consumableMasterList;
        const m = list.find((x) => x.code === code);
        if (m) return m;
        const name = get().getItemNameByCode(code);
        const category = code.startsWith('TIRE') ? 'WHEEL' : code.startsWith('BRAKE') ? 'BRAKE' : 'ENGINE';
        return { code, name, category };
    },
}));
