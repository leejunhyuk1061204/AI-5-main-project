# scripts/csv_to_wear_factor.py
import argparse
import json
from pathlib import Path

import pandas as pd

WINDOW_SECONDS = 60

# 컬럼명(CSV 헤더 기준)
COL_TIME = "Time"
COL_RPM = "Engine RPM [RPM]"
COL_SPEED = "Vehicle Speed Sensor [km/h]"
COL_MAP = "Intake Manifold Absolute Pressure [kPa]"
COOLANT_PREFIX = "Engine Coolant Temperature"

# 기본 분류 폴더
CATEGORIES = ["frei", "normal", "stau"]


def find_col_startswith(columns, prefix: str):
    for c in columns:
        if str(c).startswith(prefix):
            return c
    return None


def project_root() -> Path:
    # scripts/ 아래 파일 기준: scripts의 상위가 루트
    return Path(__file__).resolve().parents[1]


def extract_features_from_csv(csv_path: Path, window_seconds: int) -> dict:
    df = pd.read_csv(csv_path)

    coolant_col = find_col_startswith(df.columns, COOLANT_PREFIX)
    if coolant_col is None:
        raise ValueError(f"Coolant column not found. columns={list(df.columns)}")

    needed = [COL_TIME, coolant_col, COL_MAP, COL_RPM, COL_SPEED]
    for c in needed:
        if c not in df.columns:
            raise ValueError(f"Missing column '{c}' in CSV. columns={list(df.columns)}")

    # 필요한 컬럼만 + 이름 표준화
    df = df[needed].copy()
    df.columns = ["time", "coolant", "map", "rpm", "speed"]

    # Time 파싱 (HH:MM:SS.mmm)
    df["time"] = pd.to_datetime(df["time"], format="%H:%M:%S.%f", errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")

    if df.empty:
        raise ValueError("No valid time rows after parsing. Check 'Time' format in CSV.")

    # 마지막 N초 윈도우
    end_time = df["time"].iloc[-1]
    start_time = end_time - pd.Timedelta(seconds=window_seconds)
    w = df[df["time"] >= start_time].copy()

    if len(w) < 5:
        raise ValueError(f"Window too small. rows={len(w)}. Check your CSV/time parsing.")

    # ---- feature 계산 ----
    avg_rpm = float(w["rpm"].mean())
    idle_ratio = float((w["rpm"] < 800).mean())

    speed_diff = w["speed"].diff()
    hard_accel_count = int((speed_diff > 5).sum())
    hard_brake_count = int((speed_diff < -5).sum())

    return {
        "avg_rpm": round(avg_rpm, 1),
        "hard_accel_count": hard_accel_count,
        "hard_brake_count": hard_brake_count,
        "idle_ratio": round(idle_ratio, 2),
        "_debug_window": {
            "window_seconds": window_seconds,
            "window_start": str(start_time.time()),
            "window_end": str(end_time.time()),
            "rows_in_window": int(len(w)),
        },
    }


def build_payload(features: dict, csv_path: Path) -> dict:
    payload = {
        "target_item": "ENGINE_OIL",
        "last_replaced": {
            "date": "2025-06-01",
            "mileage": 48000,
        },
        "vehicle_metadata": {
            "model_year": 2020,
            "fuel_type": "GASOLINE",
            "total_mileage": 52000,
        },
        "driving_habits": {
            "avg_rpm": features["avg_rpm"],
            "hard_accel_count": features["hard_accel_count"],
            "hard_brake_count": features["hard_brake_count"],
            "idle_ratio": features["idle_ratio"],
        },
        "_debug": {
            "csv_path": str(csv_path),
            **features["_debug_window"],
        },
    }
    return payload


def detect_category_from_path(csv_path: Path) -> str:
    parts = [p.lower() for p in csv_path.parts]
    for cat in CATEGORIES:
        if cat in parts:
            return cat
    return "unknown"


def main():
    base_dir = project_root()

    parser = argparse.ArgumentParser(
        description="Convert OBD CSV(s) to wear-factor input JSON(s)."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="단일 CSV 파일 경로 (지정하면 그 파일만 변환)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=CATEGORIES,
        help="frei/normal/stau 중 하나를 골라 그 폴더의 CSV들을 변환",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="frei/normal/stau 전체 폴더의 CSV를 전부 변환",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=WINDOW_SECONDS,
        help="마지막 N초 윈도우 (기본 60)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="변환할 CSV 개수 제한 (디버깅용)",
    )
    args = parser.parse_args()

    window_seconds = int(args.window)

    raw_root = base_dir / "data" / "obd" / "raw"
    out_root = base_dir / "samples" / "wear_factor" / "wear_factor_input"
    out_root.mkdir(parents=True, exist_ok=True)

    # ---- 입력 CSV 목록 만들기 ----
    csv_list: list[Path] = []

    if args.csv:
        p = Path(args.csv)
        if not p.is_absolute():
            p = (base_dir / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")
        csv_list = [p]

    elif args.all:
        for cat in CATEGORIES:
            csv_list.extend(sorted((raw_root / cat).glob("*.csv")))

    else:
        # 기본: category 지정했으면 그 폴더, 아니면 normal 폴더
        cat = args.category or "normal"
        csv_list = sorted((raw_root / cat).glob("*.csv"))

    if not csv_list:
        raise FileNotFoundError(
            f"No CSV files found. raw_root={raw_root} (category={args.category}, all={args.all})"
        )

    if args.limit is not None:
        csv_list = csv_list[: max(0, int(args.limit))]

    # ---- 변환 실행 ----
    ok = 0
    fail = 0

    for csv_path in csv_list:
        try:
            features = extract_features_from_csv(csv_path, window_seconds=window_seconds)
            payload = build_payload(features, csv_path)

            category = detect_category_from_path(csv_path)
            # 저장 파일명: <category>__<원본파일명>.json
            out_path = out_root / f"{category}__{csv_path.stem}.json"

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            ok += 1
            print(f"[OK] {csv_path.name} -> {out_path.relative_to(base_dir)}")

        except Exception as e:
            fail += 1
            print(f"[FAIL] {csv_path} :: {e}")

    print(f"\n[DONE] ok={ok}, fail={fail}, saved_dir={out_root.relative_to(base_dir)}")


if __name__ == "__main__":
    main()
