# app/services/local_service.py
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

async def process_visual_mock(file_bytes: bytes) -> VisualResponse:
    """
    로컬 테스트용 Mock Visual Analysis (표준 규격 준수)
    """
    return VisualResponse(
        status="WARNING",
        analysis_type="SCENE_EXTERIOR",
        category="EXTERIOR",
        data={
            "damage_found": True,
            "detections": [
                {
                    "part": "Front_Bumper",
                    "damage_type": "Scratch",
                    "confidence": 0.95,
                    "bbox": [100, 100, 200, 50]
                }
            ],
            "description": "앞 범퍼에 스크래치가 발견되었습니다. (Mock 데이터)",
            "repair_estimate": "부분 도색을 권장합니다."
        }
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
