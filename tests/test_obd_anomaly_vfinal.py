import os
import sys
from typing import Callable, Dict, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdSample
from ai.app.services.obd_anomaly.core.scorers.engine_scorer import EngineScorer
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService
from ai.app.services.obd_anomaly.windowing import make_windows


CORE7 = [
    "engine_coolant_temp_c",
    "imap_kpa",
    "engine_rpm",
    "vehicle_speed_kmh",
    "intake_air_temp_c",
    "maf_gps",
    "throttle_pos_pct",
]


def _build_data(
    duration_sec: int,
    sampling_hz: int,
    feature_fn: Callable[[int], Dict[str, float]],
    t_fn: Callable[[int], int] | None = None,
) -> List[ObdSample]:
    n = duration_sec * sampling_hz
    out: List[ObdSample] = []
    for i in range(n):
        t = t_fn(i) if t_fn else i
        out.append(ObdSample(t=t, features=feature_fn(i)))
    return out


def _build_req(data: List[ObdSample], duration_sec: int = 180, sampling_hz: int = 1) -> ObdAnomalyRequest:
    return ObdAnomalyRequest(
        vehicle_id="veh-test",
        trip_id="trip-test",
        mode="DRIVING",
        duration_sec=duration_sec,
        sampling_hz=sampling_hz,
        timestamp_unit="s",
        data=data,
        options={"domains": ["engine"], "return": "raw", "window_sec": 60, "stride_sec": 30},
    )


def test_normal_data_low_alarm():
    def normal_features(_: int) -> Dict[str, float]:
        return {
            "engine_coolant_temp_c": 88.0,
            "imap_kpa": 42.0,
            "engine_rpm": 850.0,
            "vehicle_speed_kmh": 25.0,
            "intake_air_temp_c": 24.0,
            "maf_gps": 3.5,
            "throttle_pos_pct": 16.0,
        }

    req = _build_req(_build_data(180, 1, normal_features))
    res = ObdAnomalyService().run(req)

    assert "engine" in res.domains
    assert res.domains["engine"].status.value == "PROCESSED"
    assert res.is_anomaly is False


def test_column_shortage_gates_if_only():
    def sparse_features(i: int) -> Dict[str, float]:
        return {
            "engine_rpm": 900.0 + (i % 3),
            "vehicle_speed_kmh": 20.0,
            "throttle_pos_pct": 12.0,
        }

    req = _build_req(_build_data(180, 1, sparse_features))
    w = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)[0]

    env = EngineScorer().score_window(req, w)
    assert env.status.value == "PROCESSED"
    assert env.details.get("gating", {}).get("mode") == "IF_ONLY"
    assert env.details.get("status", {}).get("ae") == "SKIPPED"

    # service-level safety check
    res = ObdAnomalyService().run(req)
    assert "engine" in res.domains


def test_low_coverage_or_irregular_ts_gates_if_only():
    def low_quality_features(i: int) -> Dict[str, float]:
        if i % 2 == 0:
            return {}
        return {
            "engine_coolant_temp_c": 90.0,
            "imap_kpa": 40.0,
            "engine_rpm": 820.0,
            "vehicle_speed_kmh": 18.0,
            "intake_air_temp_c": 23.0,
            "maf_gps": 3.2,
            "throttle_pos_pct": 10.0,
        }

    def irregular_t(i: int) -> int:
        return i + (1 if i > 0 and i % 3 == 0 else 0)

    req = _build_req(_build_data(180, 1, low_quality_features, irregular_t))
    w = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)[0]

    env = EngineScorer().score_window(req, w)
    assert env.status.value == "PROCESSED"
    assert env.details.get("gating", {}).get("mode") == "IF_ONLY"

    res = ObdAnomalyService().run(req)
    assert "engine" in res.domains


def test_strong_anomaly_triggers_policy_event_after_k_consecutive():
    def pattern(i: int) -> Dict[str, float]:
        # 0~59s normal, 60s 이후 강한 이상 패턴을 지속해 K-consecutive 정책 유도.
        if i < 60:
            rpm = 850.0
            speed = 20.0
            maf = 3.5
            imap = 42.0
            throttle = 15.0
            coolant = 95.0
            intake = 30.0
        else:
            rpm = 9000.0
            speed = 260.0
            maf = 180.0
            imap = 320.0
            throttle = 120.0
            coolant = 170.0
            intake = 120.0

        return {
            "engine_coolant_temp_c": coolant,
            "imap_kpa": imap,
            "engine_rpm": rpm,
            "vehicle_speed_kmh": speed,
            "intake_air_temp_c": intake,
            "maf_gps": maf,
            "throttle_pos_pct": throttle,
        }

    req = _build_req(_build_data(180, 1, pattern))
    res = ObdAnomalyService().run(req)

    assert res.domains["engine"].is_anomaly is True
    assert any(e.type == "ENGINE_POLICY_ANOMALY" and e.domain == "engine" for e in res.events)
