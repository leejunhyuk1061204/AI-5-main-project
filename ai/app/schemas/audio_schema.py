from pydantic import BaseModel, Field
from typing import Optional

class AudioRequest(BaseModel):
    """오디오 분석 요청 스키마"""
    audioUrl: str = Field(..., description="S3에 저장된 오디오 URL")
    vehicleId: Optional[str] = Field(None, description="차량 식별자 (UUID)")
    sessionId: Optional[str] = Field(None, description="진단 세션 식별자 (UUID)")

class AudioDetail(BaseModel):
    """오디오 상세 분석 내용"""
    diagnosed_label: str = Field(..., description="진단된 소리 레이블 (예: ENGINE_NORMAL, BRAKE_SQUEAL)")
    description: str = Field(..., description="소리에 대한 설명 및 상태")

class AudioResponse(BaseModel):
    """오디오 분석 최종 응답"""
    status: str = Field(..., description="상태: NORMAL, WARNING, CRITICAL")
    analysis_type: str = Field(..., description="분석 모델: AST (1차), LLM (2차)")
    category: str = Field(..., description="소리 카테고리: ENGINE, BRAKES, SUSPENSION 등")
    data: AudioDetail = Field(..., description="오디오 상세 분석 데이터 (Old: detail)")
    confidence: float = Field(..., description="분석 신뢰도 (0.0 ~ 1.0)")
    is_critical: bool = Field(False, description="긴급 점검 필요 여부")