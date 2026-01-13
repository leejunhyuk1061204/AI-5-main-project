from pydantic import BaseModel, Field
from typing import List, Optional

class AnomalyRequest(BaseModel):
    vehicle_id: str = Field(..., examples=["VH123"])
    sampling_hz: float = Field(default=10.0, description="Sampling rate (Hz)")
    window_sec: int = Field(default=60, description="Window length in seconds")
    signals: List[str] = Field(..., description="Signal names in order")
    # 각 row: [timestamp(optional), v1, v2, ...]
    sequence: List[List[Optional[float]]]

class AnomalyResponse(BaseModel):
    vehicle_id: str
    anomaly_score: float
    threshold: float
    is_anomaly: bool
    model_version: str = "mock-0.0.1"
