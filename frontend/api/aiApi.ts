import api from './axios';

// AI 진단 결과 타입 정의
export interface AiDiagnosisResponse {
    diagnosisId: string;
    result: string; // 'NORMAL' | 'WARNING' | 'DANGER'
    description: string;
    confidence: number;
    parts?: {
        name: string;
        status: 'NORMAL' | 'WARNING' | 'DANGER';
        confidence: number;
    }[];
    soundStatus?: string; // For sound diagnosis
    imageUrl?: string;
    audioUrl?: string; // For sound diagnosis
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
 * @param vehicleId 차량 ID (선택사항)
 */
export const diagnoseEngineSound = async (audioUri: string, vehicleId?: string): Promise<any> => {
    try {
        const formData = new FormData();
        const filename = audioUri.split('/').pop() || 'engine_sound.m4a';

        let type = 'audio/m4a';
        if (filename.endsWith('.wav')) type = 'audio/wav';
        else if (filename.endsWith('.mp3')) type = 'audio/mpeg';

        if (!vehicleId) {
            try {
                const vehicles = await getVehicleList();
                const primary = vehicles.find(v => v.isPrimary) || vehicles[0];
                if (primary) vehicleId = primary.vehicleId;
            } catch (e) {
                vehicleId = '00000000-0000-0000-0000-000000000000';
            }
        }

        formData.append('audio', {
            uri: audioUri,
            name: filename,
            type,
        } as any);

        formData.append('data', {
            string: JSON.stringify({ vehicleId }),
            type: 'application/json',
        } as any);

        const response = await api.post('/api/v1/ai/diagnose/unified', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        return response.data.data;
    } catch (error) {
        console.error('[aiApi] Sound Diagnosis failed:', error);
        throw error;
    }
};

/**
<<<<<<< Updated upstream
 * AI OBD 단독 진단 요청
 * @param vehicleId 차량 ID
 */
export const diagnoseObdOnly = async (vehicleId: string): Promise<any> => {
    try {
        const formData = new FormData();

        formData.append('data', {
            string: JSON.stringify({ vehicleId }),
            type: 'application/json',
        } as any);

        const response = await api.post('/api/v1/ai/diagnose/unified', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        return response.data;
    } catch (error) {
        console.error('[aiApi] OBD Only Diagnosis failed:', error);
        throw error;
    }
};

/**
 * 세션 상태/결과 조회
 */
export const getDiagnosisSessionStatus = async (sessionId: string): Promise<any> => {
    try {
        const response = await api.get(`/api/v1/ai/diagnose/session/${sessionId}`);
        return response.data.data;
    } catch (error) {
        console.error('[aiApi] Failed to fetch session status:', error);
        throw error;
    }
};

/**
 * INTERACTIVE 모드 답변 전송
 */
export const replyToDiagnosisSession = async (sessionId: string, replyData: { userResponse?: string, vehicleId: string }, imageUri?: string, audioUri?: string): Promise<any> => {
    try {
        const formData = new FormData();

        if (imageUri) {
            const filename = imageUri.split('/').pop() || 'reply_image.jpg';
            formData.append('image', { uri: imageUri, name: filename, type: 'image/jpeg' } as any);
        }

        if (audioUri) {
            const filename = audioUri.split('/').pop() || 'reply_audio.m4a';
            formData.append('audio', { uri: audioUri, name: filename, type: 'audio/m4a' } as any);
        }

        formData.append('data', {
            string: JSON.stringify(replyData),
            type: 'application/json',
        } as any);

        const response = await api.post(`/api/v1/ai/diagnose/session/${sessionId}/reply`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        return response.data.data;
    } catch (error) {
        console.error('[aiApi] Reply failed:', error);
        throw error;
    }
};

/**
 * AI 종합 진단 (텍스트 기반 수동 진단 포함)
 */
export const predictComprehensive = async (data: {
    vehicleId: string;
    conversation_history: { role: string; content: string }[];
    analysis_results?: any;
}) => {
    try {
        const response = await api.post('/api/v1/connect/predict/comprehensive', data);
        return response.data;
    } catch (error) {
        console.error('[aiApi] Comprehensive Prediction failed:', error);
        throw error;
    }
};
