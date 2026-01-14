# app/services/llm_service.py
from ai.app.schemas.visual_schema import VisionResponse
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

async def analyze_general_image(s3_url: str) -> VisionResponse:
    """
    LLM(Vision)을 통한 일반 이미지 분석 결과를 규격에 맞춰 반환
    """
    # TODO: 실제 GPT-4o 등 API 호출 로직이 들어갈 자리
    
    # [Mock Data] 스키마 규격에 완벽히 일치시킴
    return VisionResponse(
        status="INFO",
        analysis_type="GENERAL_IMAGE", # 분석 주체 명시
        detected_count=0,              # LLM은 개별 탐지보다 설명을 우선함
        detections=[],
        description="이 사진은 차량의 타이어 외관 사진으로 보입니다.",
        recommendation="타이어 마모 한계선에 도달한 것으로 보이며 교체가 권장됩니다.",
        processed_image_url=s3_url
    )

async def analyze_audio_with_llm(s3_url: str) -> AudioResponse:
    """
    AST 모델이 판단하기 어려운 소리를 LLM(정비사 페르소나)이 정밀 진단
    """
    # TODO: GPT-4o-Audio 또는 Gemini 1.5 Pro 등 Audio LLM API 호출
    
    return AudioResponse(
        status="FAULTY",
        analysis_type="LLM_AUDIO",
        component="ENGINE_BELT",
        detail=AudioDetail(
            diagnosed_label="BELT_SLIP", 
            description="LLM 진단: 고주파 마찰음으로 보아 구동 벨트 노후화가 강력히 의심됩니다."
        ),
        confidence=0.95,
        is_critical=False,
        description="전문 정비사 분석: 소음의 패턴이 불규칙하며 가속 시 소리가 커지는 특징이 있습니다."
    )


