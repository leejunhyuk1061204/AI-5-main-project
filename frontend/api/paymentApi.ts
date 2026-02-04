import api from './axios';

// 결제 준비 응답 타입
export interface KakaoReadyResponse {
    tid: string;
    next_redirect_app_url: string;
    next_redirect_mobile_url: string;
    next_redirect_pc_url: string;
    android_app_scheme: string;
    ios_app_scheme: string;
    created_at: string;
    orderId?: string; // 백엔드에서 추가 전달
}

// 결제 승인 응답 타입
export interface KakaoApproveResponse {
    aid: string;
    tid: string;
    cid: string;
    partner_order_id: string;
    partner_user_id: string;
    payment_method_type: string;
    amount: {
        total: number;
        tax_free: number;
        vat: number;
    };
    item_name: string;
    approved_at: string;
}

// 결제 준비 요청
const ready = async (itemName: string, totalAmount: number): Promise<KakaoReadyResponse> => {
    const response = await api.post('/api/v1/payment/ready', { itemName, totalAmount });
    return response.data.data;
};

// 결제 승인 요청
const approve = async (pgToken: string, orderId: string): Promise<KakaoApproveResponse> => {
    const response = await api.post('/api/v1/payment/approve', { pgToken, orderId });
    return response.data.data;
};

// 멤버십 초기화 (FREE로 변경)
const resetMembership = async (): Promise<void> => {
    await api.post('/api/v1/payment/reset');
};

export default {
    ready,
    approve,
    resetMembership
};
