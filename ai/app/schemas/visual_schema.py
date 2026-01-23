# app/schemas/visual_schema.py
"""
시각 분석 API 스키마 정의

[SceneType]
Router가 분류하는 4가지 장면 타입

[VisualResponse]
통합 시각 분석 응답 규격
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# =============================================================================
# Scene Type Enum (Router 분류 결과)
# =============================================================================
class SceneType(str, Enum):
    """라우터가 분류하는 4가지 장면 타입"""
    SCENE_ENGINE = "SCENE_ENGINE"
    SCENE_DASHBOARD = "SCENE_DASHBOARD"
    SCENE_EXTERIOR = "SCENE_EXTERIOR"
    SCENE_TIRE = "SCENE_TIRE"


# =============================================================================
# Request Schemas
# =============================================================================
class VisualRequest(BaseModel):
    """통합 시각 분석 요청"""
    imageUrl: str = Field(..., description="S3에 저장된 이미지 URL")


class EngineAnalysisRequest(BaseModel):
    """엔진룸 전용 분석 요청"""
    imageUrl: str = Field(..., description="Engine room image S3 URL")


# =============================================================================
# Detection Item
# =============================================================================
class DetectionItem(BaseModel):
    """개별 객체 감지 결과"""
    label: str = Field(..., description="감지된 객체 명칭")
    confidence: float = Field(..., description="모델 확신도 (0.0 ~ 1.0)")
    bbox: List[int] = Field(..., description="감지 박스 좌표 [x, y, w, h]")


# =============================================================================
# Response Schemas
# =============================================================================
class VisualResponse(BaseModel):
    """
    통합 시각 분석 응답 규격
    
    analysis_type 값:
    - SCENE_ENGINE: 엔진룸 분석 결과
    - SCENE_DASHBOARD: 계기판 분석 결과
    - SCENE_EXTERIOR: 외관 분석 결과
    - SCENE_TIRE: 타이어 분석 결과
    - LLM_FALLBACK: LLM 직접 분석 결과
    """
    status: str = Field(..., description="상태 (NORMAL, WARNING, CRITICAL, ERROR)")
    analysis_type: str = Field(..., description="분석 타입")
    scene_type: Optional[SceneType] = Field(None, description="라우터가 판별한 장면 타입")
    category: Optional[str] = Field(None, description="카테고리")
    
    # 감지 결과
    detected_count: int = Field(0, description="감지된 항목 개수")
    detections: List[DetectionItem] = Field(default_factory=list, description="감지된 상세 항목")
    
    # LLM 분석 결과
    description: Optional[str] = Field(None, description="분석 설명")
    recommendation: Optional[str] = Field(None, description="권장 조치")
    
    # 결과 이미지
    processed_image_url: Optional[str] = Field(None, description="결과 이미지 URL")


class EngineAnalysisResponse(BaseModel):
    """엔진룸 전용 분석 응답"""
    status: str = Field(..., description="분석 상태 (SUCCESS/ERROR)")
    data: Dict[str, Any] = Field(..., description="분석 결과 데이터")


# =============================================================================
# 출력 예시
# =============================================================================
# {
#     "status": "WARNING",
#     "analysis_type": "SCENE_ENGINE",
#     "category": "ENGINE_ROOM",
#     "detected_count": 2,
#     "detections": [
#         {"label": "Oil_Cap", "confidence": 0.92, "bbox": [100, 200, 50, 50]}
#     ],
#     "description": "오일 캡 주변에 누유 흔적이 발견되었습니다.",
#     "recommendation": "정비소 방문 권장",
#     "processed_image_url": "https://s3.../result.jpg"
# }
