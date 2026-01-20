# app/services/local_service.py
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

async def process_visual_mock(file_bytes: bytes) -> VisualResponse:
    """
    로컬 테스트용 Mock Visual Analysis
    실제 모델 추론 없이 고정된 결과(손상 감지됨)를 반환합니다.
    """
    return VisualResponse(
        status="DAMAGED",
        analysis_type="VISUAL_MOCK",
        detected_count=1,
        detections=[
            DetectionItem(
                label="SCRATCH",
                confidence=0.95,
                bbox=[100, 100, 200, 50]
            )
        ],
        processed_image_url="http://localhost:8000/mock/result_image.jpg"
    )

async def process_audio_mock(file_bytes: bytes) -> AudioResponse:
    """
    로컬 테스트용 Mock Audio Analysis
    실제 모델 추론 없이 고정된 결과(이상 소음 감지됨)를 반환합니다.
    """
    return AudioResponse(
        status="FAULTY",
        analysis_type="AUDIO_MOCK",
        category="ENGINE",
        detail=AudioDetail(
            diagnosed_label="SLIP_NOISE_MOCK",
            description="Mock diagnosis: Belt slip detected."
        ),
        confidence=0.88,
        is_critical=False
    )
