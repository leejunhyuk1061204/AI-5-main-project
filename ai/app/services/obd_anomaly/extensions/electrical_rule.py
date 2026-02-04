from __future__ import annotations

from typing import Any, Dict, List

from ai.app.schemas.obd_anomaly_schema import (
    CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
)
from ai.app.services.obd_anomaly.windowing import Window


def run_electrical(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "electrical"

    # 예: battery_voltage_v 최솟값을 기준으로 룰 체크
    values = []
    for s in w.samples:
        v = s.features.get("battery_voltage_v")
        if isinstance(v, (int, float)):
            values.append(float(v))

    if not values:
        return CommonEnvelope(
            domain=domain,
            status=EnvelopeStatus.UNSUPPORTED,
            method=EnvelopeMethod.rule,
            score=None,
            threshold=None,
            is_anomaly=False,
            details={"reason": "battery_voltage_v not found"},
        )

    min_v = min(values)
    threshold = 11.8
    triggered = min_v < threshold

    rules: List[Dict[str, Any]] = [{
        "id": "VOLTAGE_LOW",
        "feature": "battery_voltage_v",
        "value": min_v,
        "triggered": triggered,
    }]

    score = 1.0 if triggered else 0.0
    return CommonEnvelope(
        domain=domain,
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.rule,
        score=score,
        threshold=threshold,
        is_anomaly=triggered,
        details={
            "rules": rules,
            "events": ([{"type": "VOLTAGE_LOW", "min_v": min_v}] if triggered else []),
        },
    )
