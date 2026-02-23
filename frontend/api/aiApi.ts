import api from './axios';

// 진단 대화 메시지 타입
export interface DiagnosisMessage {
    role: 'user' | 'ai';
    content: string;
    mediaType?: 'image' | 'audio';
    mediaUri?: string;
    timestamp?: number;
    isPending?: boolean;
}

// AI 진단 결과 타입
export interface AiDiagnosisResponse {
    sessionId: string;
    vehicleId: string;
    status: 'PENDING' | 'PROCESSING' | 'REPLY_PROCESSING' | 'ACTION_REQUIRED' | 'INTERACTIVE' | 'REPORT' | 'DONE' | 'COMPLETED' | 'FAILED' | 'ERROR';
    response_mode: 'REPORT' | 'INTERACTIVE';
    responseMode?: 'REPORT' | 'INTERACTIVE'; // 하위 호환성

    // 리포트 데이터 (평가 결과)
    summary?: string;
    riskLevel?: 'NORMAL' | 'CAUTION' | 'DANGER';
    description?: string;
    finalReport?: string;
    triggerType?: string;
    createdAt?: string;

    // 중첩된 리포트 구조 지원 (DiagnosisReport.tsx 대응)
    report?: {
        sessionId?: string;
        summary?: string;
        riskLevel?: 'NORMAL' | 'CAUTION' | 'DANGER';
        description?: string;
        finalReport?: string;
        triggerType?: string;
        createdAt?: string;
    };

    result?: any;
    confidence?: number;
    parts?: {
        name: string;
        status: 'NORMAL' | 'WARNING' | 'DANGER';
        confidence: number;
    }[];
    soundStatus?: string;
    imageUrl?: string;
    audioUrl?: string;

    // 인터랙티브 진단 데이터
    interactiveData?: {
        message?: string;
        conversation?: DiagnosisMessage[];
    };

    // 사용자에게 요청된 동작
    requestedAction?: 'CAPTURE_PHOTO' | 'RECORD_AUDIO' | 'ANSWER_TEXT' | 'NONE';

    // 진행 상태 메시지
    progress?: number;
    progressMessage?: string;
}



/**
 * AI 이미지 진단 요청
 * @param imageUri 촬영된 이미지의 로컬 URI
 * @param vehicleId 차량 ID
 */
export const diagnoseImage = async (imageUri: string, vehicleId: string): Promise<AiDiagnosisResponse> => {
    try {
        const formData = new FormData();
        const filename = imageUri.split('/').pop() || 'diagnosis_image.jpg';
        const match = /\.(\w+)$/.exec(filename);
        const type = match ? `image/${match[1]}` : 'image/jpeg';

        // 1. 차량 정보 (Parameter로 전달받음)
        if (!vehicleId) throw new Error("Vehicle ID is missing");

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

        const response = await api.post('/api/v1/ai/diagnose/unified?diagType=VISUAL', formData, {
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
 * @param vehicleId 차량 ID
 */
export const diagnoseEngineSound = async (audioUri: string, vehicleId: string): Promise<AiDiagnosisResponse> => {
    try {
        const formData = new FormData();
        const filename = audioUri.split('/').pop() || 'engine_sound.m4a';

        let type = 'audio/m4a';
        if (filename.endsWith('.wav')) type = 'audio/wav';
        else if (filename.endsWith('.mp3')) type = 'audio/mpeg';

        if (!vehicleId) throw new Error("Vehicle ID is missing for engine sound diagnosis");

        formData.append('audio', {
            uri: audioUri,
            name: filename,
            type,
        } as any);

        formData.append('data', {
            string: JSON.stringify({ vehicleId }),
            type: 'application/json',
        } as any);

        const response = await api.post('/api/v1/ai/diagnose/unified?diagType=AUDIO', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        return response.data.data;
    } catch (error) {
        console.error('[aiApi] Sound Diagnosis failed:', error);
        throw error;
    }
};

/**
 * AI OBD 단독 진단 요청
 * @param vehicleId 차량 ID
 */
export const diagnoseObdOnly = async (vehicleId: string): Promise<AiDiagnosisResponse> => {
    try {
        const formData = new FormData();

        formData.append('data', {
            string: JSON.stringify({ vehicleId }),
            type: 'application/json',
        } as any);

        const response = await api.post('/api/v1/ai/diagnose/unified?diagType=DATA', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        return response.data.data;
    } catch (error) {
        console.error('[aiApi] OBD Only Diagnosis failed:', error);
        throw error;
    }
};

/**
 * 세션 상태/결과 조회
 */
export const getDiagnosisSessionStatus = async (sessionId: string): Promise<AiDiagnosisResponse> => {
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
export interface ReplyResponse {
    sessionId: string;
    response_mode: 'REPORT' | 'INTERACTIVE';
    result?: string;
    description?: string;
    interactive_question?: string;
}

export const replyToDiagnosisSession = async (
    sessionId: string,
    replyData: { userResponse?: string, vehicleId: string },
    imageUri?: string,
    audioUri?: string
): Promise<ReplyResponse> => {
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
// DTC 보고 데이터 타입 (백엔드 DtcDto 매칭)
export interface DtcReportRequest {
    vehicleId: string;
    dtcCode: string;
    descriptionKo?: string;
    descriptionEn?: string;
    summaryKo?: string;
    summaryEn?: string;
    severity?: 'CRITICAL' | 'WARNING' | 'INFO';
    status?: 'ACTIVE' | 'STORED' | 'PENDING';
}

/**
 * DTC(고장 코드) 보고
 * @param data DTC 보고 요청 데이터
 */
export const sendDtcReport = async (data: DtcReportRequest): Promise<void> => {
    try {
        console.log('[aiApi] Sending DTC report:', data.dtcCode);
        await api.post('/api/v1/ai/dtc', data);
        console.log('[aiApi] DTC report sent successfully');
    } catch (error) {
        console.error('[aiApi] Failed to send DTC report:', error);
        throw error;
    }
};

/**
 * DTC 배치 및 프리즈 프레임 보고
 */
export interface DtcBatchReportRequest {
    vehicleId: string;
    dtcs: { code: string; type: string; status: string }[];
    freezeFrame?: {
        rpm?: number;
        speed?: number;
        voltage?: number;
        coolantTemp?: number;
        engineLoad?: number;
        fuelTrimShort?: number;
        fuelTrimLong?: number;
        intakeTemp?: number;
        map?: number;
        maf?: number;
        throttlePos?: number;
        engineRuntime?: number;
        ambientTemp?: number;
        fuelPressure?: number;
        pidsSnapshot?: string;
    };
}

export const sendDtcBatchReport = async (data: DtcBatchReportRequest): Promise<void> => {
    try {
        console.log('[aiApi] Sending DTC batch report, count:', data.dtcs.length);
        await api.post('/api/v1/ai/dtc/batch', data);
        console.log('[aiApi] DTC batch report sent successfully');
    } catch (error) {
        console.error('[aiApi] Failed to send DTC batch report:', error);
        throw error;
    }
};

/**
 * 차량별 진단 목록 조회
 */
export const getDiagnosisList = async (vehicleId: string): Promise<any[]> => {
    try {
        const response = await api.get('/api/v1/ai/diagnose/list', {
            params: { vehicleId }
        });
        const raw = response.data?.data;
        return Array.isArray(raw) ? raw : (raw != null ? [raw] : []);
    } catch (error) {
        console.error('[aiApi] Failed to fetch diagnosis list:', error);
        throw error;
    }
};
