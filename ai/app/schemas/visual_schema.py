# ai/app/schemas/visual_schema.py
"""
시각 분석 API 스키마 정의

[파일 설명]
이 파일은 AI 서버의 시각 분석 API 응답 형식을 정의합니다.
프론트엔드와 백엔드가 이 스키마를 기준으로 데이터를 주고받습니다.

[주요 스키마]
- VisualResponse: 통합 응답 (status, analysis_type, category, data)
- EngineData: 엔진룸 분석 결과
- DashboardData: 계기판 분석 결과
- ExteriorData: 외관 분석 결과
- TireData: 타이어 분석 결과

[API 명세서 기준 버전]
- 2026-01-25 업데이트
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
# 1. ENGINE 관련 스키마
# =============================================================================
class EnginePartResult(BaseModel):
    """엔진룸 개별 부품 분석 결과"""
    part_name: str = Field(..., description="부품 명칭")
    bbox: List[int] = Field(..., description="바운딩 박스 [x1, y1, x2, y2]")
    is_anomaly: bool = Field(..., description="이상 여부")
    anomaly_score: float = Field(..., description="이상 점수 (0.0~1.0)")
    threshold: float = Field(..., description="이상 판정 임계값")
    defect_label: Optional[str] = Field(None, description="결함 명칭 (LLM)")
    severity: str = Field("NORMAL", description="심각도 (NORMAL/WARNING/CRITICAL)")
    description: Optional[str] = Field(None, description="상세 설명 (LLM)")
    recommended_action: Optional[str] = Field(None, description="권장 조치 (LLM)")


class EngineData(BaseModel):
    """엔진룸 분석 data 객체"""
    vehicle_type: str = Field(..., description="차량 유형 (ICE: 내연기관 / EV: 전기차)")
    parts_detected: int = Field(..., description="감지된 부품 수")
    anomalies_found: int = Field(0, description="이상 징후 부품 수")
    results: List[EnginePartResult] = Field(default_factory=list, description="부품별 분석 결과")


# =============================================================================
# 2. DASHBOARD 관련 스키마
# =============================================================================
class DashboardDetection(BaseModel):
    """계기판 경고등 개별 감지 결과"""
    label: str = Field(..., description="경고등 명칭")
    color_severity: str = Field(..., description="색상 기반 심각도 (RED/YELLOW/GREEN)")
    confidence: float = Field(..., description="모델 확신도")
    is_blinking: Optional[bool] = Field(None, description="점멸 여부")
    meaning: Optional[str] = Field(None, description="경고등 의미 (LLM)")
    bbox: List[int] = Field(..., description="바운딩 박스 [x, y, w, h]")


class VehicleContext(BaseModel):
    """차량 정보 context"""
    inferred_model: Optional[str] = Field(None, description="추론된 차종")
    dashboard_type: Optional[str] = Field(None, description="아날로그/디지털 구분")


class IntegratedAnalysis(BaseModel):
    """통합 분석 결과"""
    severity_score: int = Field(..., description="심각도 점수 (1~10)")
    description: Optional[str] = Field(None, description="종합 설명")
    short_term_risk: Optional[str] = Field(None, description="단기 위험 요소")


class DashboardRecommendation(BaseModel):
    """계기판 권장 조치"""
    primary_action: Optional[str] = Field(None, description="1차 권장 조치")
    secondary_action: Optional[str] = Field(None, description="2차 권장 조치")
    estimated_repair: Optional[str] = Field(None, description="예상 수리 내용")


class DashboardData(BaseModel):
    """계기판 분석 data 객체"""
    vehicle_context: Optional[VehicleContext] = Field(None, description="차량 정보")
    detected_count: int = Field(0, description="감지된 경고등 수")
    detections: List[DashboardDetection] = Field(default_factory=list, description="경고등 목록")
    integrated_analysis: Optional[IntegratedAnalysis] = Field(None, description="통합 분석")
    recommendation: Optional[DashboardRecommendation] = Field(None, description="권장 조치")


# =============================================================================
# 3. EXTERIOR 관련 스키마
# =============================================================================
class ExteriorDetection(BaseModel):
    """외관 파손 개별 감지 결과"""
    part: str = Field(..., description="파손 부위")
    damage_type: str = Field(..., description="파손 종류")
    confidence: float = Field(..., description="모델 확신도")
    bbox: List[int] = Field(..., description="바운딩 박스 [x, y, w, h]")


class ExteriorData(BaseModel):
    """외관 분석 data 객체"""
    damage_found: bool = Field(..., description="파손 발견 여부")
    detections: List[ExteriorDetection] = Field(default_factory=list, description="파손 목록")
    description: Optional[str] = Field(None, description="종합 설명 (LLM)")
    repair_estimate: Optional[str] = Field(None, description="예상 수리 내용 (LLM)")


class DetectionItem(BaseModel):
    """범용 객체 탐지 결과 (YOLO Raw Output)"""
    label: str = Field(..., description="객체 클래스명")
    confidence: float = Field(..., description="탐지 신뢰도")
    bbox: List[int] = Field(..., description="Bounding Box [x, y, w, h]")


# =============================================================================
# 4. TIRE 관련 스키마
# =============================================================================
class TireData(BaseModel):
    """타이어 분석 data 객체"""
    wear_status: str = Field(..., description="마모 상태 (GOOD/DANGER)")
    wear_level_pct: Optional[int] = Field(None, description="마모 진행도 (%)")
    critical_issues: Optional[List[str]] = Field(None, description="['cracked', 'flat', 'bulge', 'uneven'] 등")
    description: Optional[str] = Field(None, description="상태 설명 (LLM)")
    recommendation: Optional[str] = Field(None, description="권장 조치 (LLM)")
    is_replacement_needed: bool = Field(False, description="교체 필요 여부")


# =============================================================================
# 통합 응답 스키마
# =============================================================================
class VisualResponse(BaseModel):
    """
    통합 시각 분석 응답 규격
    
    모든 장면(ENGINE, DASHBOARD, EXTERIOR, TIRE)이 동일한 최상위 구조를 가지며,
    장면별 상세 데이터는 'data' 필드 안에 포함됩니다.
    """
    status: str = Field(..., description="상태 (NORMAL, WARNING, CRITICAL, ERROR)")
    analysis_type: str = Field(..., description="분석 타입 (SCENE_ENGINE 등)")
    category: str = Field(..., description="카테고리 (ENGINE_ROOM, DASHBOARD 등)")
    data: Optional[Dict[str, Any]] = Field(None, description="장면별 상세 데이터")
    
    # [하위 호환성 및 중간 단계용 필드]
    detected_count: Optional[int] = Field(None, description="감지된 객체 수 (Legacy or Intermediate)")
    detections: Optional[List[DetectionItem]] = Field(None, description="감지 목록 (Legacy or Intermediate)")
    processed_image_url: Optional[str] = Field(None, description="처리된 이미지 URL")


class EngineAnalysisResponse(BaseModel):
    """엔진룸 전용 분석 응답 (하위 호환용)"""
    status: str = Field(..., description="상태")
    analysis_type: str = Field("SCENE_ENGINE", description="분석 타입")
    category: str = Field("ENGINE_ROOM", description="카테고리")
    data: EngineData = Field(..., description="엔진 분석 데이터")
