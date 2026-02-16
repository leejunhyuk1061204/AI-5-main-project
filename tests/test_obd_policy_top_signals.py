import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.core.policy.threshold_policy import apply_engine_policy
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService


def test_policy_k_consecutive_and_cooldown():
    policy = {
        "threshold": 0.7,
        "k_consecutive": 2,
        "cooldown_sec": 60,
        "severity": {
            "duration_bonus_per_window": 0.05,
            "max_bonus": 0.3,
        },
    }
    scores = [0.8, 0.82, 0.9, 0.91, 0.95]
    starts = [0, 30, 60, 90, 120]

    events = apply_engine_policy(scores, starts, policy)

    assert len(events) == 2
    assert events[0]["window_index"] == 1
    assert events[1]["window_index"] == 3
    assert events[0]["streak"] == 2
    assert events[1]["streak"] == 4


def test_policy_duration_bonus_clamped():
    policy = {
        "threshold": 0.7,
        "k_consecutive": 1,
        "cooldown_sec": 0,
        "severity": {
            "duration_bonus_per_window": 0.2,
            "max_bonus": 0.3,
        },
    }
    scores = [0.8, 0.8, 0.8, 0.8]
    starts = [0, 30, 60, 90]

    events = apply_engine_policy(scores, starts, policy)
    assert len(events) == 4
    assert abs(events[-1]["duration_bonus"] - 0.3) < 1e-9
    assert events[-1]["severity_score"] <= 1.0


def test_top_signals_normalized_in_service_extract():
    svc = ObdAnomalyService()
    req = ObdAnomalyRequest.model_validate(
        {
            "vehicle_id": "veh-1",
            "trip_id": "trip-1",
            "mode": "DRIVING",
            "duration_sec": 1,
            "sampling_hz": 1,
            "timestamp_unit": "s",
            "data": [{"t": 0, "features": {}}],
            "options": {"top_signals": "always", "top_k": 2, "domains": ["engine"]},
        }
    )
    env = CommonEnvelope(
        domain="engine",
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.hybrid,
        score=0.8,
        threshold=0.7,
        is_anomaly=True,
        details={
            "top_signals": [
                {"feature": "engine_rpm", "contribution": 2.0},
                {"feature": "maf_gps", "contribution": 1.0},
            ]
        },
    )

    top = svc._extract_top_signals(req, env)
    assert top is not None
    assert len(top) == 2
    s = sum(t.contribution for t in top)
    assert abs(s - 1.0) < 1e-6
