from __future__ import annotations

from typing import Callable, Dict

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, ObdAnomalyRequest
from ai.app.services.obd_anomaly.windowing import Window

from .brake_rule import run_brake
from .electrical_rule import run_electrical
from .idle_rule import run_idle
from .tire_rule import run_tire

DomainRunner = Callable[[ObdAnomalyRequest, Window], CommonEnvelope]

DOMAIN_REGISTRY: Dict[str, DomainRunner] = {
    "brake": run_brake,
    "electrical": run_electrical,
    "tire": run_tire,
    "idle": run_idle,
}
