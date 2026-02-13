from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, conint, model_validator


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


class EventSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ---------- Request Models ----------
class ObdSample(BaseModel):
    t: conint(ge=0)
    features: Dict[str, Any]


class Options(BaseModel):
    top_signals: Literal["off", "always", "on_anomaly"] = "on_anomaly"
    top_k: conint(ge=1, le=20) = 3

    # New request contract (preferred)
    domains: List[str] = Field(default_factory=list)  # ["engine","electrical","brake","tire","idle"]
    # Legacy request contract (deprecated, backward compatibility)
    extensions: List[str] = Field(default_factory=list)  # ["electrical","brake","tire","idle"]
    return_: Literal["raw", "summary"] = Field("summary", alias="return")

    window_sec: conint(ge=1) = 60
    stride_sec: conint(ge=1) = 30

    @model_validator(mode="after")
    def merge_legacy_extensions(self):
        # If new field is absent, map legacy field to new field automatically.
        if not self.domains and self.extensions:
            self.domains = list(self.extensions)
        return self

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
    domains: Dict[str, CommonEnvelope] = Field(default_factory=dict)


class ResponseMeta(BaseModel):
    vehicle_id: str
    trip_id: str
    timestamp_unit: TimestampUnit
    total_duration_sec: int
    window_sec: int
    stride_sec: int
    num_windows: int


# ---------- New Summary Models ----------
class TopSignal(BaseModel):
    feature: str
    contribution: float


class DomainResult(BaseModel):
    domain: str
    status: EnvelopeStatus
    score: Optional[float] = None
    threshold: Optional[float] = None
    is_anomaly: bool = False
    top_signals: Optional[List[TopSignal]] = None


class AnomalyEvent(BaseModel):
    type: str
    domain: str
    feature: str
    value: Any = None
    threshold: Optional[float] = None
    window_index: Optional[int] = None
    severity: EventSeverity = EventSeverity.INFO
    message: str = ""


class ObdAnomalyResponse(BaseModel):
    meta: ResponseMeta
    is_anomaly: bool = False
    anomaly_score: Optional[float] = None
    domains: Dict[str, DomainResult] = Field(default_factory=dict)
    events: List[AnomalyEvent] = Field(default_factory=list)
    # In raw mode, service may include per-window payloads.
    window_results: List[Dict[str, Any]] = Field(default_factory=list)
