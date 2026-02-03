# ai/app/schemas/wear_factor.py
"""
차량 소모품 마모 진단 API 스키마 정의 (Phase 2)
"""
from enum import Enum
from datetime import date
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional


# =============================================================================
# Enum Definitions
# =============================================================================

class TargetItem(str, Enum):
    """소모품 품목 코드 (Java Backend와 일치)"""
    ENGINE_OIL = "ENGINE_OIL"
    BRAKE_PAD = "BRAKE_PAD"
    TIRE = "TIRE"
    COOLANT = "COOLANT"
    AIR_FILTER = "AIR_FILTER"


class FuelType(str, Enum):
    """연료 타입"""
    GASOLINE = "GASOLINE"
    DIESEL = "DIESEL"
    LPG = "LPG"
    ELECTRIC = "ELECTRIC"
    HYBRID = "HYBRID"


# =============================================================================
# Request Models
# =============================================================================

class VehicleMetadata(BaseModel):
    """차량 기본 정보 (5필드)"""
    model_year: int = Field(..., ge=1900, le=2100, description="연식")
    fuel_type: FuelType = Field(..., description="연료 타입")
    total_mileage_km: int = Field(..., ge=0, description="현재 누적 주행거리(km)")
    engine_displacement_cc: int = Field(..., ge=0, description="배기량(cc)")
    vehicle_age_months: int = Field(..., ge=0, description="차량 나이(월)")


class DrivingSummary(BaseModel):
    """주행 요약 통계 (15필드)"""
    # 🔴 Week 1 Required (7 fields)
    trip_distance_km: float = Field(..., ge=0, description="주행 거리(km)")
    avg_maf: float = Field(..., ge=0, description="평균 MAF(g/s) - Air Filter용")
    avg_throttle_pos: float = Field(..., ge=0, le=100, description="평균 스로틀 위치(%)")
    overheat_duration_sec: int = Field(..., ge=0, description="과열 지속시간(초) - 냉각수 95°C 초과")
    avg_coolant_temp: float = Field(..., description="평균 냉각수 온도(°C)")
    hard_accel_count: int = Field(..., ge=0, description="급가속 횟수")
    hard_brake_count: int = Field(..., ge=0, description="급제동 횟수")
    
    # 🟡 Week 2 Recommended (5 fields)
    avg_speed_kmh: float = Field(..., ge=0, description="평균 속도(km/h)")
    max_rpm: float = Field(..., ge=0, description="최대 RPM - Engine Oil용")
    avg_engine_load: float = Field(..., ge=0, le=100, description="평균 엔진 부하(%)")
    avg_rpm: float = Field(..., ge=0, description="평균 RPM")
    idle_ratio: float = Field(..., ge=0, le=1.0, description="공회전 비율(0~1) - Engine Oil용")
    
    # 🟢 Optional (3 fields)
    trip_duration_min: Optional[int] = Field(None, ge=0, description="주행 시간(분)")
    avg_map: Optional[float] = Field(None, ge=0, description="평균 MAP(kPa) - MAF fallback")
    max_coolant_temp: Optional[float] = Field(None, description="최고 냉각수 온도(°C)")


class ConsumableContext(BaseModel):
    """소모품 교체 이력 컨텍스트 (4필드)"""
    item_code: TargetItem = Field(..., description="소모품 품목 코드")
    last_replaced_date: Optional[str] = Field(None, description="마지막 교체일 (ISO 8601)")
    last_replaced_mileage: int = Field(..., ge=0, description="마지막 교체 시점 주행거리(km)")
    is_inferred: bool = Field(..., description="추정 데이터 여부 (true=추정, false=실제 기록)")


class WearFactorRequest(BaseModel):
    """마모 계수 예측 요청"""
    # 루트 레벨 필드
    vehicle_id: str = Field(..., description="차량 고유 ID")
    trip_id: str = Field(..., description="트립 고유 ID")
    timestamp: str = Field(..., description="요청 타임스탬프 (ISO 8601)")
    
    # 중첩 객체
    vehicle_metadata: VehicleMetadata
    driving_summary: DrivingSummary
    consumables_context: List[ConsumableContext] = Field(..., description="소모품 컨텍스트 배열")


# =============================================================================
# Response Models
# =============================================================================

class WearFactorResponse(BaseModel):
    """마모 계수 예측 응답"""
    wear_factors: Dict[str, float] = Field(
        ..., 
        description="소모품별 마모 계수 딕셔너리",
        json_schema_extra={
            "example": {
                "ENGINE_OIL": 1.15,
                "AIR_FILTER": 1.20,
                "COOLANT": 1.0,
                "TIRE": 1.35,
                "BRAKE_PAD": 1.08
            }
        }
    )
    model_version: str = Field(..., description="모델 버전")
