# app/services/ast_service.py
import torch
from transformers import ASTForAudioClassification, ASTFeatureExtractor
import os
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

# 1. 모델 경로 (학습 후 생성될 경로)
MODEL_PATH = "Ai/weights/audio/best_ast_model"

# 서버 시작 시 모델 로드
if os.path.exists(MODEL_PATH):
    feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_PATH)
    model = ASTForAudioClassification.from_pretrained(MODEL_PATH)
    print(f"[AST Service] 모델 로드 완료: {MODEL_PATH}")
else:
    feature_extractor = None
    model = None
    print(f"[AST Service] Warning: {MODEL_PATH}가 없습니다. Mock 모드로 동작합니다.")

async def run_ast_inference(processed_audio_buffer) -> AudioResponse:
    """
    16kHz WAV 버퍼를 받아 AST 모델로 엔진 소리 여부 판별
    """
    if model is None:
        # [수정] 테스트를 위해 "고장(FAULTY)" 상태를 반환하도록 변경
        return AudioResponse(
            status="FAULTY",
            analysis_type="AST",
            category="ENGINE",
            detail=AudioDetail(diagnosed_label="ENGINE_KNOCKING", description="테스트용: 엔진 노킹 소음 감지"),
            confidence=0.95,
            is_critical=True
        )

    # TODO: 실제 추론 로직 (feature_extractor -> model)
    # 현재는 구조적 완성을 위해 규격에 맞는 결과를 반환하도록 설계
    return AudioResponse(
        status="FAULTY",
        analysis_type="AST",
        component="ENGINE",
        detail=AudioDetail(diagnosed_label="ENGINE_KNOCKING", description="엔진 노킹 소음 감지"),
        confidence=0.85,
        is_critical=True
    )