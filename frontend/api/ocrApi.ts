import api from './axios';

// OCR 분석 응답 타입
export interface OcrAnalysisResponse {
    maintenanceDate: string | null;
    mileageAtMaintenance: number | null;
    shopName: string | null;
    cost: number | null;
    consumableItemCode: string | null;
    consumableItemName: string | null;
    ocrText: string | null;
    ocrData: string | null;
}

// 정비 이력 저장 응답 타입 (백엔드 응답과 일치)
export interface MaintenanceHistoryResponse {
    id: string;                      // 백엔드: id
    maintenanceDate: string;         // 백엔드: maintenanceDate
    mileageAtMaintenance: number | null; // 백엔드: mileageAtMaintenance
    itemDescription: string;         // 백엔드: itemDescription (소모품 이름)
    isStandardized: boolean;
    shopName: string | null;
    cost: number | null;
    ocrData: string | null;
    memo: string | null;
}

/**
 * OCR 분석만 수행 (저장 X)
 */
export const analyzeReceipt = async (file: FormData): Promise<OcrAnalysisResponse> => {
    const response = await api.post('/api/v1/ocr/analyze', file, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data.data;
};

/**
 * OCR 분석 + DB 저장 + 소모품 갱신
 */
export const analyzeAndSaveReceipt = async (
    vehicleId: string,
    file: FormData
): Promise<MaintenanceHistoryResponse> => {
    const response = await api.post(`/api/v1/ocr/${vehicleId}/analyze-save`, file, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data.data;
};

/**
 * 정비 이력 목록 조회
 */
export const getMaintenanceHistory = async (vehicleId: string): Promise<MaintenanceHistoryResponse[]> => {
    try {
        const response = await api.get(`/api/v1/vehicles/${vehicleId}/maintenance`);
        return response.data.data || [];
    } catch (error) {
        console.error('Failed to fetch maintenance history:', error);
        return [];
    }
};

export default {
    analyzeReceipt,
    analyzeAndSaveReceipt,
    getMaintenanceHistory,
};
