from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

# script 실행 위치와 무관하게 `ai.*` import가 동작하도록 루트 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdSample
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService


def _norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _col_map() -> Dict[str, str]:
    return {
        "time": "time",
        "enginecoolanttemperaturec": "engine_coolant_temp_c",
        "intakemanifoldabsolutepressurekpa": "imap_kpa",
        "enginerpmrpm": "engine_rpm",
        "vehiclespeedsensorkmh": "vehicle_speed_kmh",
        "intakeairtemperaturec": "intake_air_temp_c",
        "airflowratefrommassflowsensorgs": "maf_gps",
        "absolutethrottleposition": "throttle_pos_pct",
        "obdmodulevoltagev": "battery_voltage_v",
    }


def _core_features() -> List[str]:
    return [
        "engine_coolant_temp_c",
        "imap_kpa",
        "engine_rpm",
        "vehicle_speed_kmh",
        "intake_air_temp_c",
        "maf_gps",
        "throttle_pos_pct",
    ]


def _extra_features() -> List[str]:
    return ["battery_voltage_v"]


def _max_missing_run(mask: List[bool]) -> int:
    best = 0
    cur = 0
    for ok in mask:
        if ok:
            cur = 0
            continue
        cur += 1
        if cur > best:
            best = cur
    return best


def load_case_samples(csv_path: Path) -> Tuple[List[ObdSample], Dict[str, Any]]:
    df = pd.read_csv(csv_path)
    norm_to_raw = {_norm_col(c): c for c in df.columns}
    raw_cols = list(df.columns)

    selected: Dict[str, pd.Series] = {}
    matched_raw_columns: Dict[str, str] = {}
    for norm_key, target in _col_map().items():
        raw = norm_to_raw.get(norm_key)
        if raw is not None:
            selected[target] = df[raw]
            matched_raw_columns[target] = raw

    # Fallback: local real-case export CSV can have Korean/mangled headers.
    # Observed index layout:
    #   0: time
    #   1: engine coolant temp
    #   2: engine rpm
    #   8: vehicle speed
    if not any(k in selected for k in _core_features()) and len(raw_cols) >= 9:
        selected["engine_coolant_temp_c"] = df[raw_cols[1]]
        selected["engine_rpm"] = df[raw_cols[2]]
        selected["vehicle_speed_kmh"] = df[raw_cols[8]]
        matched_raw_columns["engine_coolant_temp_c"] = f"{raw_cols[1]} (fallback_by_index)"
        matched_raw_columns["engine_rpm"] = f"{raw_cols[2]} (fallback_by_index)"
        matched_raw_columns["vehicle_speed_kmh"] = f"{raw_cols[8]} (fallback_by_index)"
    if "battery_voltage_v" not in selected and len(raw_cols) >= 11:
        selected["battery_voltage_v"] = df[raw_cols[10]]
        matched_raw_columns["battery_voltage_v"] = f"{raw_cols[10]} (fallback_by_index)"
    core = _core_features()
    extras = _extra_features()
    parsed_cols: Dict[str, pd.Series] = {}
    for feat in core + extras:
        if feat in selected:
            parsed_cols[feat] = pd.to_numeric(selected[feat], errors="coerce")
        else:
            parsed_cols[feat] = pd.Series([float("nan")] * len(df))

    out: List[ObdSample] = []
    for i in range(len(df)):
        features: Dict[str, float] = {}
        for feat in core + extras:
            v = parsed_cols[feat].iloc[i]
            if pd.notna(v):
                features[feat] = float(v)
        out.append(ObdSample(t=i, features=features))

    n_rows = len(df)
    feat_valid_count: Dict[str, int] = {}
    feat_coverage: Dict[str, float] = {}
    feat_max_gap: Dict[str, int] = {}
    present_feats = 0
    total_valid = 0
    for feat in core:
        ser = parsed_cols[feat]
        valid_mask = ser.notna().tolist()
        vc = int(sum(valid_mask))
        cov = float(vc / n_rows) if n_rows > 0 else 0.0
        gap = _max_missing_run(valid_mask)
        feat_valid_count[feat] = vc
        feat_coverage[feat] = cov
        feat_max_gap[feat] = gap
        if vc > 0:
            present_feats += 1
        total_valid += vc

    overall_coverage = float(total_valid / (n_rows * len(core))) if n_rows > 0 else 0.0
    debug = {
        "rows": n_rows,
        "core_features": core,
        "matched_raw_columns": matched_raw_columns,
        "n_present": present_feats,
        "core_min_target": 5,
        "overall_coverage": overall_coverage,
        "feature_valid_count": feat_valid_count,
        "feature_coverage": feat_coverage,
        "feature_max_missing_run": feat_max_gap,
    }
    return out, debug


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Real-case csv path")
    ap.add_argument("--vehicle-id", default="veh-real")
    ap.add_argument("--trip-id", default="trip-real")
    ap.add_argument("--sampling-hz", type=int, default=10)
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    data, debug = load_case_samples(csv_path)
    if args.debug:
        print("[DEBUG] input_quality")
        print(json.dumps(debug, ensure_ascii=False, indent=2))
    req = ObdAnomalyRequest(
        vehicle_id=args.vehicle_id,
        trip_id=args.trip_id,
        mode="DRIVING",
        duration_sec=max(1, int(len(data) / max(1, args.sampling_hz))),
        sampling_hz=args.sampling_hz,
        timestamp_unit="s",
        data=data,
        options={
            "domains": ["engine", "electrical", "brake", "tire", "idle"],
            "return": "summary",
            "window_sec": args.window_sec,
            "stride_sec": args.stride_sec,
            "top_signals": "on_anomaly",
            "top_k": 3,
        },
    )

    res = ObdAnomalyService().run(req)
    payload = res.model_dump(mode="json")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
