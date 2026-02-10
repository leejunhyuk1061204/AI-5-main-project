from __future__ import annotations

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.windowing import Window


def run_idle(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "idle"

    if req.mode == "DRIVING":
        return CommonEnvelope(
            domain=domain,
            status=EnvelopeStatus.SKIPPED,
            method=EnvelopeMethod.rule,
            score=None,
            threshold=None,
            is_anomaly=False,
        )

    return CommonEnvelope(
        domain=domain,
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.rule,
        score=0.0,
        threshold=None,
        is_anomaly=False,
        details={"rules": [], "events": []},
    )
