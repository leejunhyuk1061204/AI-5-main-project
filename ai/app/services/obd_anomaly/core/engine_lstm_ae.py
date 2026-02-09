from __future__ import annotations

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.windowing import Window


def run_engine_lstm_ae(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "engine"

    score = 0.0
    threshold = 0.70
    is_anom = score >= threshold

    return CommonEnvelope(
        domain=domain,
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.ml,
        score=score,
        threshold=threshold,
        is_anomaly=is_anom,
        details={
            "model": {"name": "lstm_ae", "version": "v1.0"},
            "score_type": "normalized_recon_error",
            "aggregation": "mean",
            "events": ([{"type": "ENGINE_LSTM_AE", "score": score}] if is_anom else []),
        },
    )
