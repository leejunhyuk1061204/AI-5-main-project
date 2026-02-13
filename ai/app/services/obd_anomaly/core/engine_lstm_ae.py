from __future__ import annotations

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, ObdAnomalyRequest
from ai.app.services.obd_anomaly.core.scorers.engine_scorer import EngineScorer
from ai.app.services.obd_anomaly.windowing import Window


_SCORER = EngineScorer()


def run_engine_lstm_ae(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    # 기존 엔트리포인트를 유지하면서 내부 구현만 하이브리드 스코어러로 위임.
    return _SCORER.score_window(req, w)
