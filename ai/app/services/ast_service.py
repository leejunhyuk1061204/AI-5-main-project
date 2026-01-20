# app/services/ast_service.py
import torch
from transformers import ASTForAudioClassification, ASTFeatureExtractor
import os
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

# =============================================================================
# [설정] 모델 경로
# =============================================================================
MODEL_PATH = "ai/weights/audio/best_ast_model"

# =============================================================================
# [정상 소리 라벨] - 이 라벨들은 NORMAL 상태로 처리됩니다
# =============================================================================
NORMAL_LABELS = {
    "idle",       # 정상 공회전 소리
    "normal",     # 명시적 정상
    "brakes",     # 정상 브레이크 소리 (파일명에 normal_brakes면 정상)
}

# =============================================================================
# [자동 카테고리 매핑 함수]
# 라벨 이름 패턴에서 카테고리를 자동으로 추출합니다.
# 재학습 시 코드 수정 불필요!
# =============================================================================
def get_category_from_label(label_name: str) -> str:
    """
    라벨 이름에서 카테고리 자동 추출
    
    규칙:
    - 접두사 ENG_, BRAKE_, SUSP_ 등으로 시작하면 해당 카테고리
    - 또는 키워드 포함 여부로 판단
    """
    label_upper = label_name.upper()
    
    # 1. 접두사 규칙 (권장: 학습 데이터에 접두사 사용)
    if label_upper.startswith("ENG_"):
        return "ENGINE"
    elif label_upper.startswith("BRAKE_"):
        return "BRAKES"
    elif label_upper.startswith("SUSP_"):
        return "SUSPENSION"
    elif label_upper.startswith("EXHAUST_"):
        return "EXHAUST"
    elif label_upper.startswith("TIRE_"):
        return "TIRES_WHEELS_AUDIO"
    elif label_upper.startswith("BODY_"):
        return "BODY"
    
    # 2. 키워드 규칙 (기존 학습 데이터용)
    engine_keywords = ["ENGINE", "KNOCK", "MISFIRE", "BELT", "VALVE", "NORMAL"]
    brake_keywords = ["BRAKE", "SQUEAL", "GRINDING"]
    suspension_keywords = ["SUSPENSION", "CLUNK", "RATTLE"]
    exhaust_keywords = ["EXHAUST", "MUFFLER", "LEAK"]
    tire_keywords = ["TIRE", "WHEEL", "BEARING", "HUM"]
    body_keywords = ["WIND", "BODY", "RATTLE", "SQUEAK"]
    
    for kw in engine_keywords:
        if kw in label_upper:
            return "ENGINE"
    
    # 2-1. IDLE은 엔진 정상 소리
    if "IDLE" in label_upper:
        return "ENGINE"
    
    for kw in brake_keywords:
        if kw in label_upper:
            return "BRAKES"
    for kw in suspension_keywords:
        if kw in label_upper:
            return "SUSPENSION"
    for kw in exhaust_keywords:
        if kw in label_upper:
            return "EXHAUST"
    for kw in tire_keywords:
        if kw in label_upper:
            return "TIRES_WHEELS_AUDIO"
    for kw in body_keywords:
        if kw in label_upper:
            return "BODY"
    
    # 3. 기본값 - UNKNOWN 대신 ENGINE 반환 (대부분 엔진 관련)
    return "ENGINE"

# =============================================================================
# 추론 함수
# =============================================================================
async def run_ast_inference(processed_audio_buffer, ast_model_payload=None) -> AudioResponse:
    """16kHz WAV 버퍼를 받아 AST 모델로 소리 분류"""
    
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
    # 실제 추론 로직
    # =========================================================================
    try:
        import librosa
        import torch.nn.functional as F
        
        # 1. BytesIO 버퍼에서 오디오 데이터 로드 (이미 16kHz로 변환됨)
        processed_audio_buffer.seek(0)  # 버퍼 처음으로 이동
        audio_array, sr = librosa.load(processed_audio_buffer, sr=16000)
        
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
        
        # 5. 상태 결정
        label_lower = label_name.lower()
        
        # 5-1. 신뢰도가 너무 낮으면 분류 불가 (차량 소리가 아닐 수 있음)
        if confidence < 0.5:
            status = "UNKNOWN"
            is_critical = False
            category = "UNKNOWN_AUDIO"
            label_name = "unknown"  # 라벨도 unknown으로 변경
            description = "분류할 수 없는 소리입니다. 차량 관련 소리인지 확인해주세요."
        # 5-2. 정상 라벨이면 NORMAL
        elif label_lower in NORMAL_LABELS or "normal" in label_lower:
            status = "NORMAL"
            is_critical = False
            description = "정상적인 소리입니다."
        # 5-3. 그 외는 FAULTY
        else:
            status = "FAULTY"
            is_critical = True
            description = f"{label_name} 소음이 감지되었습니다. 점검이 필요합니다."
        
        return AudioResponse(
            status=status,
            analysis_type="AST",
            category=category,
            detail=AudioDetail(
                diagnosed_label=label_name,
                description=description
            ),
            confidence=round(confidence, 4),
            is_critical=is_critical
        )
        
    except Exception as e:
        print(f"[AST Inference Error] {e}")
        # 추론 실패 시 UNKNOWN 반환
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
