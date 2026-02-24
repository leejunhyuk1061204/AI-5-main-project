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
    try {
        const response = await api.get('/api/v1/master/consumables');
        return response.data.data ?? [];
    } catch (e) {
        console.warn('[masterApi] getAllConsumableItems failed', e);
        return [];
    }
};
