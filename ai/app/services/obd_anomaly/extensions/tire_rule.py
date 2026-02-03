from __future__ import annotations

from typing import Any, Dict, List

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.windowing import Window


def run_tire(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "tire"
    keys = ["tire_pressure_fl_kpa", "tire_pressure_fr_kpa", "tire_pressure_rl_kpa", "tire_pressure_rr_kpa"]

    found = {}
    for k in keys:
        vals = []
        for s in w.samples:
            v = s.features.get(k)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if vals:
            found[k] = min(vals)

    if not found:
        return CommonEnvelope(
            domain=domain,
            status=EnvelopeStatus.UNSUPPORTED,
            method=EnvelopeMethod.rule,
            score=None,
            threshold=None,
            is_anomaly=False,
            details={"reason": "no tire pressure signals"},
        )

    threshold = 200.0
    rules: List[Dict[str, Any]] = []
    events = []
    any_triggered = False

    for feat, min_v in found.items():
        triggered = min_v < threshold
        any_triggered = any_triggered or triggered
        rules.append({"id": "TIRE_PRESSURE_LOW", "feature": feat, "value": min_v, "triggered": triggered})
        if triggered:
            events.append({"type": "TIRE_PRESSURE_LOW", "feature": feat, "min_kpa": min_v})

    score = 1.0 if any_triggered else 0.0
    return CommonEnvelope(
        domain=domain,
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.rule,
        score=score,
        threshold=threshold,
        is_anomaly=any_triggered,
        details={"rules": rules, "events": events},
    )
