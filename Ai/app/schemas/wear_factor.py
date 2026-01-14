from enum import Enum
from datetime import date as dt_date
from pydantic import BaseModel, Field


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
    date: dt_date = Field(..., description="YYYY-MM-DD")
    mileage: int = Field(..., ge=0)


class VehicleMetadata(BaseModel):
    model_year: int
    fuel_type: FuelType
    total_mileage: int = Field(..., ge=0)


class DrivingHabits(BaseModel):
    avg_rpm: float = Field(..., ge=0)
    hard_accel_count: int = Field(..., ge=0)
    hard_brake_count: int = Field(..., ge=0)
    idle_ratio: float = Field(..., ge=0.0, le=1.0)


class WearFactorRequest(BaseModel):
    target_item: TargetItem
    last_replaced: LastReplaced
    vehicle_metadata: VehicleMetadata
    driving_habits: DrivingHabits


class WearFactorResponse(BaseModel):
    predicted_wear_factor: float
    model_version: str
