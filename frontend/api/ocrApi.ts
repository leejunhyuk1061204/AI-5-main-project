import api from './axios';

// 정비 품목 1줄 (OCR items 배열 또는 편집용)
export interface MaintenanceLineItem {
    consumableItemCode: string;
    consumableItemName?: string | null;
    quantity: number;
    amount?: number | null;
    description?: string | null;
}

// OCR 분석 응답 타입
export interface OcrAnalysisResponse {
    maintenanceDate: string | null;
    mileageAtMaintenance: number | null;
    shopName: string | null;
    cost: number | null;

    // Receipt Type
    receiptType: 'MAINTENANCE' | 'FUELING';

    // Maintenance Specific (단일 품목, items 없을 때 사용)
    consumableItemCode: string | null;
    consumableItemName: string | null;
    quantity: number | null;

    // Maintenance 다품목 (있으면 목록 UI에서 사용)
    items?: MaintenanceLineItem[] | null;

    // Fueling Specific
    fuelType: string | null;
    unitPrice: number | null;
    fuelAmount: number | null;

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
    quantity: number | null;
    ocrData: string | null;
    memo: string | null;
    receiptId: string | null;
}

export interface FuelingHistoryResponse {
    id: string;
    fuelType: string;
    fuelingDate: string;
    amount: number;
    unitPrice: number;
    totalCost: number;
    mileageAtFueling: number | null;
    shopName: string | null;
    stationName: string | null;
    memo: string | null;
    receiptId: string | null;
}

export interface FuelingHistoryRequest {
    fuelingDate: string;
    mileageAtFueling: number | null;
    fuelType: string;
    amount: number | null;
    unitPrice: number | null;
    totalCost: number;
    shopName: string | null;
    memo: string | null;
    receiptId: string | null;
}

/** OCR/LLM 처리 시간 고려 타임아웃 (초) */
const OCR_REQUEST_TIMEOUT_MS = 60000;

/**
 * OCR 분석만 수행 (저장 X)
 */
export const analyzeReceipt = async (file: FormData): Promise<OcrAnalysisResponse> => {
    const response = await api.post('/api/v1/ocr/analyze', file, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        timeout: OCR_REQUEST_TIMEOUT_MS,
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
        timeout: OCR_REQUEST_TIMEOUT_MS,
    });
    return response.data.data;
};

/**
 * 정비 이력 목록 조회 (필터링 지원)
 */
export const getMaintenanceHistory = async (
    vehicleId: string,
    filters?: { itemCode?: string; startDate?: string; endDate?: string }
): Promise<MaintenanceHistoryResponse[]> => {
    try {
        const params = new URLSearchParams();
        if (filters?.itemCode) params.append('itemCode', filters.itemCode);
        if (filters?.startDate) params.append('startDate', filters.startDate);
        if (filters?.endDate) params.append('endDate', filters.endDate);

        const response = await api.get(`/api/v1/vehicles/${vehicleId}/maintenance?${params.toString()}`);
        return response.data.data || [];
    } catch (error) {
        console.error('Failed to fetch maintenance history:', error);
        return [];
    }
};

/**
 * 정비 이력 수정
 */
export const updateMaintenance = async (
    historyId: string,
    data: any
): Promise<MaintenanceHistoryResponse> => {
    const response = await api.put(`/api/v1/vehicles/maintenance/${historyId}`, data);
    return response.data.data;
};

/**
 * 정비 이력 삭제
 */
export const deleteMaintenance = async (historyId: string): Promise<void> => {
    await api.delete(`/api/v1/vehicles/maintenance/${historyId}`);
};

/**
 * 정비 이력 수동 등록
 */
export const registerMaintenanceManual = async (
    vehicleId: string,
    data: any | any[]
): Promise<MaintenanceHistoryResponse[]> => {
    const payload = Array.isArray(data) ? data : [data];
    const response = await api.post(`/api/v1/vehicles/${vehicleId}/maintenance`, payload);
    return response.data.data;
};

/**
 * 주유 내역 목록 조회
 */
export const getFuelingHistory = async (vehicleId: string): Promise<FuelingHistoryResponse[]> => {
    const response = await api.get(`/api/v1/fueling/${vehicleId}`);
    return response.data.data || [];
};

/**
 * 주유 내역 수동 등록
 */
export const registerFuelingManual = async (
    vehicleId: string,
    data: FuelingHistoryRequest
): Promise<FuelingHistoryResponse> => {
    const response = await api.post(`/api/v1/fueling/${vehicleId}`, data);
    return response.data.data;
};

/**
 * 주유 내역 삭제
 */
export const deleteFueling = async (fuelingId: string): Promise<void> => {
    await api.delete(`/api/v1/fueling/${fuelingId}`);
};

export default {
    analyzeReceipt,
    analyzeAndSaveReceipt,
    getMaintenanceHistory,
    updateMaintenance,
    deleteMaintenance,
    registerMaintenanceManual,
    getFuelingHistory,
    registerFuelingManual,
    deleteFueling,
};
