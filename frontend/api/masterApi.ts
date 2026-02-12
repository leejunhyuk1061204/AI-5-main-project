import api from './axios';

/**
 * 전역 제조사 목록 조회
 */
export const getManufacturers = async (): Promise<string[]> => {
    const response = await api.get('/api/v1/master/manufacturers');
    console.log('[MasterApi] getManufacturers response:', response.data);
    return response.data.data;
};

/**
 * 제조사별 차량 모델 상세 목록 (한글/영문 포함, RAG·진단용 영문 전송에 사용)
 */
export interface CarModelDto {
    modelName: string;
    modelNameKo: string;
    modelNameEn: string;
    manufacturerKo: string;
    manufacturerEn: string;
    modelYear: number;
    fuelType: string;
}

export const getModels = async (manufacturer: string): Promise<CarModelDto[]> => {
    const response = await api.get('/api/v1/master/models', {
        params: { manufacturer }
    });
    return response.data.data ?? [];
};

/**
 * 특정 제조사의 모델명 목록 조회 (한글 이름만)
 */
export const getModelNames = async (manufacturer: string): Promise<string[]> => {
    const response = await api.get('/api/v1/master/models/names', {
        params: { manufacturer }
    });
    return response.data.data;
};

/**
 * 특정 모델의 연식 목록 조회
 */
export const getModelYears = async (manufacturer: string, modelName: string): Promise<number[]> => {
    const response = await api.get('/api/v1/master/models/years', {
        params: { manufacturer, modelName }
    });
    return response.data.data;
};

/**
 * 특정 차량의 가용한 연료 타입 목록 조회
 */
export const getAvailableFuelTypes = async (manufacturer: string, modelName: string, modelYear: number): Promise<string[]> => {
    const response = await api.get('/api/v1/master/models/fuels', {
        params: { manufacturer, modelName, modelYear }
    });
    return response.data.data;
};

/**
 * 소모품 마스터 목록 조회
 */
export interface ConsumableMaster {
    code: string;
    name: string;
    category: string;
    description?: string;
    icon?: string;
    replacementCycleKm?: number;
    replacementCycleMonth?: number;
}

export const getAllConsumableItems = async (): Promise<ConsumableMaster[]> => {
    // 2025.01.26 - 백엔드 API 미구현 시 mock 데이터 사용 가능하도록 처리
    try {
        const response = await api.get('/api/v1/master/consumables');
        return response.data.data;
    } catch (e) {
        // console.warn('Fallback to local consumable list');
        // Sorted by Replacement Cycle (Shortest First)
        return [
            { code: 'ENGINE_OIL', name: '엔진 오일', category: 'ENGINE', icon: 'oil-barrel', replacementCycleKm: 10000, replacementCycleMonth: 12 },
            { code: 'TIRE_FRONT', name: '앞 타이어', category: 'WHEEL', icon: 'tire', replacementCycleKm: 40000, replacementCycleMonth: 0 },
            { code: 'TIRE_REAR', name: '뒤 타이어', category: 'WHEEL', icon: 'tire', replacementCycleKm: 50000, replacementCycleMonth: 0 },
            { code: 'BRAKE_PAD_FRONT', name: '앞 브레이크 패드', category: 'BRAKE', icon: 'disc-full', replacementCycleKm: 30000, replacementCycleMonth: 0 },
            { code: 'BRAKE_PAD_REAR', name: '뒤 브레이크 패드', category: 'BRAKE', icon: 'disc-full', replacementCycleKm: 40000, replacementCycleMonth: 0 },
            { code: 'BATTERY_12V', name: '12V 배터리', category: 'ELEC', icon: 'battery-charging-full', replacementCycleKm: 60000, replacementCycleMonth: 36 },
            { code: 'CABIN_FILTER', name: '에어컨 필터', category: 'AIR', icon: 'air', replacementCycleKm: 15000, replacementCycleMonth: 6 },
            { code: 'COOLANT', name: '냉각수', category: 'ENGINE', icon: 'coolant-temperature', replacementCycleKm: 40000, replacementCycleMonth: 0 },
            { code: 'BRAKE_FLUID', name: '브레이크 오일', category: 'BRAKE', icon: 'oil', replacementCycleKm: 40000, replacementCycleMonth: 0 },
            { code: 'SPARK_PLUG', name: '점화 플러그', category: 'ENGINE', icon: 'flash', replacementCycleKm: 100000, replacementCycleMonth: 0 }
        ];
    }
};
