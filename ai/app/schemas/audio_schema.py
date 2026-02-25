from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class AudioRequest(BaseModel):
    """오디오 분석 요청 스키마"""
    audioUrl: str = Field(..., description="S3에 저장된 오디오 URL")
    vehicleId: Optional[str] = Field(None, description="차량 식별자 (UUID)")
    sessionId: Optional[str] = Field(None, description="진단 세션 식별자 (UUID)")


class AudioDetail(BaseModel):
    """오디오 상세 분석 내용"""
    diagnosed_label: str = Field(
        ...,
        description="진단된 소리 레이블 (NORMAL_SOUND 또는 FAULTY_SOUND)"
    )


class AudioResponse(BaseModel):
    """오디오 분석 최종 응답 (기존 스펙 100% 유지)"""

    status: str = Field(..., description="NORMAL, WARNING, CRITICAL, ERROR")
    analysis_type: str = Field(..., description="AST 또는 LLM")
    category: str = Field(..., description="ENGINE, BRAKES 등")
    detail: AudioDetail = Field(..., description="오디오 상세 분석 데이터")
    confidence: float = Field(..., description="0.0 ~ 1.0")
    is_critical: bool = Field(False, description="긴급 점검 필요 여부")

    class Config:
        extra = "ignore"  # 혹시 내부적으로 더 많은 필드가 들어와도 JSON에는 안 나감