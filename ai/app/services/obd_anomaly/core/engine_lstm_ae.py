from __future__ import annotations

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, ObdAnomalyRequest
from ai.app.services.obd_anomaly.core.engine_scorer import EngineScorer
from ai.app.services.obd_anomaly.windowing import Window


_SCORER = EngineScorer()


def run_engine_lstm_ae(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    return _SCORER.score_window(req, w)
