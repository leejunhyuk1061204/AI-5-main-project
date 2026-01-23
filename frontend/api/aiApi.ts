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

import { getVehicleList } from './vehicleApi';

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

        // 1. 차량 정보 조회 (필수: data 파트 구성을 위해)
        let vehicleId = '00000000-0000-0000-0000-000000000000'; // Default fallback
        try {
            const vehicles = await getVehicleList();
            const primary = vehicles.find(v => v.isPrimary) || vehicles[0];
            if (primary) vehicleId = primary.vehicleId;
        } catch (e) {
            console.warn('Failed to fetch vehicle info, using default ID');
        }

        // 2. 이미지 파일 추가
        formData.append('image', {
            uri: imageUri,
            name: filename,
            type,
        } as any);

        // 3. JSON 데이터 추가 (Backend requires 'data' part)
        formData.append('data', {
            string: JSON.stringify({ vehicleId }),
            type: 'application/json',
        } as any);

        console.log('[aiApi] Uploading image to unified endpoint:', filename);

        const response = await api.post('/api/v1/ai/diagnose/unified', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        console.log('[aiApi] Diagnosis successful:', response.data);
        return response.data.data;
    } catch (error) {
        console.error('[aiApi] Diagnosis failed:', error);
        throw error;
    }
};

/**
 * AI 엔진 소리 진단 요청
 * @param audioUri 녹음된 오디오 파일의 로컬 URI
 */
export const diagnoseEngineSound = async (audioUri: string): Promise<AiDiagnosisResponse> => {
    try {
        const formData = new FormData();
        const filename = audioUri.split('/').pop() || 'engine_sound.m4a';

        // Mime Type 추론
        let type = 'audio/m4a';
        if (filename.endsWith('.wav')) type = 'audio/wav';
        else if (filename.endsWith('.mp3')) type = 'audio/mpeg';

        // React Native의 FormData에 파일 추가 방식
        formData.append('audio', {
            uri: audioUri,
            name: filename,
            type,
        } as any);

        console.log('[aiApi] Uploading audio for diagnosis:', filename);

        const response = await api.post('/api/v1/ai/diagnose-sound', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });

        console.log('[aiApi] Sound Diagnosis successful:', response.data);
        return response.data.data;
    } catch (error) {
        console.error('[aiApi] Sound Diagnosis failed:', error);
        throw error;
    }
};
