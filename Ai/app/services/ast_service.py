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
        # 모델 학습 전 임시 응답 (분석이 안되므로 신뢰도 0으로 반환하여 LLM 유도)
        return AudioResponse(
            status="UNKNOWN",
            analysis_type="AST",
            component="UNKNOWN",
            detail=AudioDetail(diagnosed_label="UNKNOWN", description="모델 준비 중입니다."),
            confidence=0.0,
            is_critical=False
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