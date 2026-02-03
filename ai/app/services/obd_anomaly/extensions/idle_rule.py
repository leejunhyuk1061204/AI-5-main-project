from __future__ import annotations

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.windowing import Window


def run_idle(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "idle"

    # 명세 예시: mode=DRIVING이면 idle 도메인은 SKIPPED
    if req.mode == "DRIVING":
        return CommonEnvelope(
            domain=domain,
            status=EnvelopeStatus.SKIPPED,
            method=EnvelopeMethod.rule,
            score=None,
            threshold=None,
            is_anomaly=False,
            details={"reason": "mode=DRIVING"},
        )

    # 여기부터는 실제 idle rule (예시 placeholder)
    return CommonEnvelope(
        domain=domain,
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.rule,
        score=0.0,
        threshold=None,
        is_anomaly=False,
        details={"rules": [], "events": []},
    )
