from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

# script 실행 위치와 무관하게 `ai.*` import가 동작하도록 루트 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdSample
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService


def build_sample_data(duration_sec: int = 180, sampling_hz: int = 1) -> List[ObdSample]:
    data: List[ObdSample] = []
    n = duration_sec * sampling_hz
    for i in range(n):
        # 60초 이후 강한 이상 패턴을 넣어 정책 이벤트가 보이도록 구성
        if i < 60:
            features: Dict[str, float] = {
                "engine_coolant_temp_c": 90.0,
                "imap_kpa": 42.0,
                "engine_rpm": 850.0,
                "vehicle_speed_kmh": 20.0,
                "intake_air_temp_c": 28.0,
                "maf_gps": 3.5,
                "throttle_pos_pct": 15.0,
            }
        else:
            features = {
                "engine_coolant_temp_c": 165.0,
                "imap_kpa": 310.0,
                "engine_rpm": 8800.0,
                "vehicle_speed_kmh": 250.0,
                "intake_air_temp_c": 115.0,
                "maf_gps": 170.0,
                "throttle_pos_pct": 120.0,
            }
        data.append(ObdSample(t=i, features=features))
    return data


def main() -> None:
    req = ObdAnomalyRequest(
        vehicle_id="veh-sample",
        trip_id="trip-sample",
        mode="DRIVING",
        duration_sec=180,
        sampling_hz=1,
        timestamp_unit="s",
        data=build_sample_data(),
        options={
            "domains": ["engine", "electrical", "brake", "tire", "idle"],
            "return": "summary",
            "window_sec": 60,
            "stride_sec": 30,
            "top_signals": "on_anomaly",
            "top_k": 3,
        },
    )

    res = ObdAnomalyService().run(req)
    print(json.dumps(res.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
