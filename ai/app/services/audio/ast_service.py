# ai/app/services/ast_service.py
"""
AST 기반 기계 소음 분석 서비스 (Audio Spectrogram Transformer)

[역할]
1. 딥러닝 기반 소음 분류: 차량 엔진, 브레이크, 서스펜션 등에서 발생하는 소음을 스펙트로그램으로 변환하여 분류합니다.
2. 실시간 상태 판별: 정상(Normal)과 결함(Faulty) 상태를 신뢰도(Confidence)와 함께 판단합니다.
3. 자동 카테고리 매핑: 라벨 이름 패턴을 기반으로 부품 카테고릴 자동 분류합니다.

[주요 기능]
- AST 모델 추론 (run_ast_inference)
- 라벨 기반 카테고리 자동 추출 (get_category_from_label)
"""
import torch
from transformers import ASTForAudioClassification, ASTFeatureExtractor
import os
import librosa
import torch.nn.functional as F
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

# =============================================================================
# [설정] 모델 경로
# =============================================================================
MODEL_PATH = "ai/weights/audio/best_ast_model"

# =============================================================================
# [정상 소리 라벨] - 이 라벨들은 NORMAL 상태로 처리됩니다
# =============================================================================
NORMAL_LABELS = {
    "normal",     # 정상 소리
}

# =============================================================================
# [결함 라벨 → 카테고리 매핑]
# 새 데이터셋 기준: engine, brake, starter, normal
# =============================================================================
LABEL_TO_CATEGORY = {
    "normal": "NORMAL",
    "engine": "ENGINE",
    "brake": "BRAKES",
    "starter": "STARTER",
}

LABEL_TO_DESCRIPTION = {
    "normal": "정상적인 차량 소리입니다.",
    "engine": "엔진 관련 이상 소음이 감지되었습니다. 점검이 필요합니다.",
    "brake": "브레이크 관련 이상 소음이 감지되었습니다. 즉시 점검이 필요합니다.",
    "starter": "시동 관련 이상 소음이 감지되었습니다. 배터리 및 스타터 모터 점검이 필요합니다.",
}

# =============================================================================
# [자동 카테고리 매핑 함수]
# =============================================================================
def get_category_from_label(label_name: str) -> str:
    """
    라벨 이름에서 카테고리 추출
    
    새 데이터셋 라벨: normal, engine, brake, starter
    """
    label_lower = label_name.lower()
    return LABEL_TO_CATEGORY.get(label_lower, "ENGINE")


def get_description_from_label(label_name: str) -> str:
    """라벨에 해당하는 설명 반환"""
    label_lower = label_name.lower()
    return LABEL_TO_DESCRIPTION.get(label_lower, "차량 소음 분석이 필요합니다.")

# =============================================================================
# 추론 함수
# =============================================================================
async def run_ast_inference(processed_audio_buffer, ast_model_payload=None) -> AudioResponse:
    """16kHz WAV 버퍼를 받아 AST 모델로 소리 분류 (Async Wrapper)"""
    import asyncio
    loop = asyncio.get_running_loop()

    # 모델 미로드 시 Mock 응답
    if ast_model_payload is None:
        print("[AST Service] Model payload is None! Returning Mock Response.")
        label_name = "Engine_Knocking"
        category = get_category_from_label(label_name)
        
        return AudioResponse(
            status="FAULTY",
            analysis_type="AST_MOCK",
            category=category,
            detail=AudioDetail(
                diagnosed_label=label_name,
                description="테스트용: 엔진 노킹 소음 감지 (Mock)"
            ),
            confidence=0.95,
            is_critical=True
        )

    model = ast_model_payload.get("model")
    feature_extractor = ast_model_payload.get("feature_extractor")

    if model is None or feature_extractor is None:
        print("[AST Service] Model or FeatureExtractor is None! Returning Mock Response.")
        return AudioResponse(status="ERROR", analysis_type="AST", category="ERROR", detail=AudioDetail(diagnosed_label="Error", description="Model not loaded"), confidence=0, is_critical=False)

    # =========================================================================
    # 실제 추론 로직 (동기 함수)
    # =========================================================================
    def _sync_inference(audio_buffer):
        try:
            # 1. BytesIO 버퍼에서 오디오 데이터 로드 (이미 16kHz로 변환됨)
            audio_buffer.seek(0)
            audio_array, sr = librosa.load(audio_buffer, sr=16000)
            
            # 2. Feature Extractor로 전처리
            inputs = feature_extractor(
                audio_array, 
                sampling_rate=16000, 
                return_tensors="pt", 
                padding="max_length"
            )
            
            # 3. 모델 추론
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                
                # Softmax로 신뢰도(확률) 계산
                probs = F.softmax(logits, dim=-1)
                confidence = probs.max().item()
                predicted_id = logits.argmax(-1).item()
            
            # 4. 라벨 이름 변환
            label_name = model.config.id2label[predicted_id]
            category = get_category_from_label(label_name)
            description = get_description_from_label(label_name)
            
            # 5. 상태 결정 (4-class: normal, engine, brake, starter)
            label_lower = label_name.lower()
            
            if confidence < 0.5:
                status = "UNKNOWN"
                is_critical = False
                category = "UNKNOWN_SOUND"
                diagnosed_label = "UNKNOWN"
                description = "식별 불가능한 소리입니다. 재녹음을 권장합니다."
            elif label_lower == "normal":
                status = "NORMAL"
                is_critical = False
                diagnosed_label = "NORMAL"
            else:
                # engine, brake, starter → CRITICAL
                status = "CRITICAL"
                is_critical = True
                diagnosed_label = label_name.upper()
            
            return AudioResponse(
                status=status,
                analysis_type="AST",
                category=category,
                detail=AudioDetail(
                    diagnosed_label=diagnosed_label if 'diagnosed_label' in dir() else label_name.upper(),
                    description=description
                ),
                confidence=round(confidence, 4),
                is_critical=is_critical
            )
            
        except Exception as e:
            print(f"[AST Inference Error] {e}")
            return AudioResponse(
                status="UNKNOWN",
                analysis_type="AST",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(
                    diagnosed_label="Error",
                    description=f"추론 중 오류 발생: {str(e)}"
                ),
                confidence=0.0,
                is_critical=False
            )

    # 별도 스레드에서 실행
    return await loop.run_in_executor(None, _sync_inference, processed_audio_buffer)
