from __future__ import annotations

from typing import Any, Dict, List

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.windowing import Window


def run_brake(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "brake"

    # 예: brake_pressure_kpa 값이 말도 안 되게 튀는지 (샘플)
    values = []
    for s in w.samples:
        v = s.features.get("brake_pressure_kpa")
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
            details={"reason": "brake_pressure_kpa not found"},
        )

    max_p = max(values)
    # 예시 임계 (실제값은 config로 빼는 게 좋음)
    threshold = 20000.0
    triggered = max_p > threshold

    rules: List[Dict[str, Any]] = [{
        "id": "BRAKE_PRESSURE_RANGE",
        "feature": "brake_pressure_kpa",
        "value": max_p,
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
        details={"rules": rules, "events": ([{"type": "BRAKE_PRESSURE_RANGE", "max_p": max_p}] if triggered else [])},
    )
