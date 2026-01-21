import api from './axios';

// AI 진단 결과 타입 정의 (백엔드 응답 구조에 맞춰 수정 필요)
export interface AiDiagnosisResponse {
    diagnosisId: string;
    result: string;
    description: string;
    confidence: number;
    parts: {
        name: string;
        status: 'NORMAL' | 'WARNING' | 'DANGER';
        confidence: number;
    }[];
    imageUrl: string;
}

/**
 * AI 이미지 진단 요청
 * @param imageUri 촬영된 이미지의 로컬 URI
 */
export const diagnoseImage = async (imageUri: string): Promise<AiDiagnosisResponse> => {
    try {
        const formData = new FormData();
        const filename = imageUri.split('/').pop() || 'diagnosis_image.jpg';
        const match = /\.(\w+)$/.exec(filename);
        const type = match ? `image/${match[1]}` : 'image/jpeg';

        // React Native의 FormData에 파일 추가 방식
        formData.append('image', {
            uri: imageUri,
            name: filename,
            type,
        } as any);

        console.log('[aiApi] Uploading image for diagnosis:', filename);

        const response = await api.post('/api/v1/ai/diagnose', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        console.log('[aiApi] Diagnosis successful:', response.data);
        return response.data.data; // 표준 응답 구조 (status, message, data) 가정
    } catch (error) {
        console.error('[aiApi] Diagnosis failed:', error);
        throw error;
    }
};
