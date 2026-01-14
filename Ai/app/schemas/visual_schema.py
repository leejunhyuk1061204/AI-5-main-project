#app/schemas/visual_schema.py
from pydantic import BaseModel, Field
from typing import List, Optional

class DetectionItem(BaseModel):
    """개별 경고등 감지 결과"""
    label: str = Field(..., description="감지된 경고등 명칭 (예: Check Engine)")
    confidence: float = Field(..., description="모델의 확신도 (0.0 ~ 1.0)")
    bbox: List[int] = Field(..., description="감지 박스 좌표 [x, y, w, h]")

class VisionResponse(BaseModel):
    """최종 비전 분석 응답 규격"""
    status: str = Field(..., description="전체 상태 (NORMAL, WARNING, CRITICAL)")
    analysis_type: str = Field(..., description="분석 주체 (DASHBOARD 또는 GENERAL_IMAGE)")
    detected_count: int = Field(0, description="감지된 항목 개수")
    detections: List[DetectionItem] = Field([], description="감지된 상세 항목 리스트")
    
    # LLM 상세 분석 결과 (일반 이미지 분석 시 활용)
    description: Optional[str] = Field(None, description="이미지에 대한 전체적인 설명")
    recommendation: Optional[str] = Field(None, description="정비 권고 사항")
    
    # 결과 이미지 경로
    processed_image_url: Optional[str] = Field(None, description="분석 결과가 표시된 S3 이미지 URL")