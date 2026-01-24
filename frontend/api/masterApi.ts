import api from './axios';

/**
 * 전역 제조사 목록 조회
 */
export const getManufacturers = async (): Promise<string[]> => {
    const response = await api.get('/api/v1/master/manufacturers');
    return response.data.data;
};

/**
 * 특정 제조사의 모델명 목록 조회
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
