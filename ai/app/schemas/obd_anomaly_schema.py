from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, conint


# ---------- Enums ----------
class Mode(str, Enum):
    DRIVING = "DRIVING"
    IDLE = "IDLE"


class TimestampUnit(str, Enum):
    s = "s"
    ms = "ms"


class EnvelopeStatus(str, Enum):
    PROCESSED = "PROCESSED"
    SKIPPED = "SKIPPED"
    UNSUPPORTED = "UNSUPPORTED"
    ERROR = "ERROR"


class EnvelopeMethod(str, Enum):
    ml = "ml"
    rule = "rule"
    hybrid = "hybrid"


# ---------- Request Models ----------
class ObdSample(BaseModel):
    t: conint(ge=0)
    features: Dict[str, Any]


class Options(BaseModel):
    top_signals: Literal["off", "always", "on_anomaly"] = "on_anomaly"
    top_k: conint(ge=1, le=20) = 3

    extensions: List[str] = Field(default_factory=list)  # ["electrical","brake","tire","idle"]
    return_: Literal["raw", "summary"] = Field("raw", alias="return")

    window_sec: conint(ge=1) = 60
    stride_sec: conint(ge=1) = 60

    class Config:
        populate_by_name = True


class ObdAnomalyRequest(BaseModel):
    vehicle_id: str
    trip_id: str
    mode: Mode
    duration_sec: conint(ge=1) = 900
    sampling_hz: conint(ge=1) = 1
    timestamp_unit: TimestampUnit = TimestampUnit.s

    data: List[ObdSample]
    options: Options = Field(default_factory=Options)


# ---------- Common Envelope ----------
class CommonEnvelope(BaseModel):
    domain: str
    status: EnvelopeStatus
    method: EnvelopeMethod
    score: Optional[float] = None
    threshold: Optional[float] = None
    is_anomaly: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


# ---------- Response Models ----------
class WindowResult(BaseModel):
    window_index: conint(ge=0)
    start_t: conint(ge=0)
    end_t: conint(ge=0)

    core: CommonEnvelope
    extensions: Dict[str, CommonEnvelope] = Field(default_factory=dict)


class ResponseMeta(BaseModel):
    vehicle_id: str
    trip_id: str
    timestamp_unit: TimestampUnit
    total_duration_sec: int
    window_sec: int
    stride_sec: int
    num_windows: int


class ObdAnomalyResponse(BaseModel):
    meta: ResponseMeta
    window_results: List[WindowResult] = Field(default_factory=list)

    core: CommonEnvelope
    extensions: Dict[str, CommonEnvelope] = Field(default_factory=dict)
