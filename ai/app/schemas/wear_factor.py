from enum import Enum
from datetime import date as Date
from pydantic import BaseModel, Field, ConfigDict



class TargetItem(str, Enum):
    ENGINE_OIL = "ENGINE_OIL"
    BRAKE_PADS = "BRAKE_PADS"
    TIRES = "TIRES"


class FuelType(str, Enum):
    GASOLINE = "GASOLINE"
    DIESEL = "DIESEL"
    EV = "EV"
    HEV = "HEV"


class LastReplaced(BaseModel):
    replaced_date: Date = Field(..., alias="date", description="YYYY-MM-DD")
    mileage: int = Field(..., ge=0, description="마지막 교체 당시 누적 주행거리(km)")

    # alias로 들어온 값을 그대로 파싱 허용
    model_config = ConfigDict(populate_by_name=True)



class VehicleMetadata(BaseModel):
    model_year: int = Field(..., ge=1900, le=2100)
    fuel_type: FuelType
    total_mileage: int = Field(..., ge=0, description="현재 누적 주행거리(km)")


class DrivingHabits(BaseModel):
    avg_rpm: float = Field(..., ge=0, le=10000, description="최근 60초 평균 RPM")
    hard_accel_count: int = Field(..., ge=0, description="최근 60초 급가속 횟수")
    hard_brake_count: int = Field(..., ge=0, description="최근 60초 급제동 횟수")
    idle_ratio: float = Field(..., ge=0.0, le=1.0, description="최근 60초 공회전 비율(0~1)")


class WearFactorRequest(BaseModel):
    target_item: TargetItem
    last_replaced: LastReplaced
    vehicle_metadata: VehicleMetadata
    driving_habits: DrivingHabits


class WearFactorResponse(BaseModel):
    predicted_wear_factor: float = Field(..., description="표준 대비 마모 배율 (예: 1.15)")
    model_version: str
