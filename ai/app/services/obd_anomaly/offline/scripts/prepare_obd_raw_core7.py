import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd


CORE7 = [
    "engine_coolant_temp_c",
    "imap_kpa",
    "engine_rpm",
    "vehicle_speed_kmh",
    "intake_air_temp_c",
    "maf_gps",
    "throttle_pos_pct",
]


def _norm_col(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _column_map() -> Dict[str, str]:
    # Raw OBD CSV headers can include mojibake/unit symbols, so match by normalized token.
    return {
        "time": "time",
        "enginecoolanttemperaturec": "engine_coolant_temp_c",
        "intakemanifoldabsolutepressurekpa": "imap_kpa",
        "enginerpmrpm": "engine_rpm",
        "vehiclespeedsensorkmh": "vehicle_speed_kmh",
        "intakeairtemperaturec": "intake_air_temp_c",
        "airflowratefrommassflowsensorgs": "maf_gps",
        "absolutethrottleposition": "throttle_pos_pct",
    }


def _to_seconds(series: pd.Series) -> pd.Series:
    ts = pd.to_timedelta(series.astype(str), errors="coerce").dt.total_seconds()
    if ts.notna().any():
        base = ts.dropna().iloc[0]
        return ts - float(base)
    return pd.Series(range(len(series)), index=series.index, dtype="float64")


def _read_one_csv(path: Path, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    norm_to_raw = {_norm_col(c): c for c in df.columns}
    cmap = _column_map()

    selected: Dict[str, pd.Series] = {}
    for nkey, target in cmap.items():
        raw = norm_to_raw.get(nkey)
        if raw is not None:
            selected[target] = df[raw]

    t = _to_seconds(selected["time"]) if "time" in selected else pd.Series(range(len(df)), dtype="float64")
    out = pd.DataFrame(index=t.index)
    out["trip_id"] = str(path.stem)
    out["label"] = str(label)
    out["t"] = t.astype("float64")

    for feat in CORE7:
        if feat in selected:
            out[feat] = pd.to_numeric(selected[feat], errors="coerce")
        else:
            out[feat] = float("nan")

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", default="data/obd/raw")
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--labels", default="normal,frei,stau")
    args = ap.parse_args()

    raw_root = Path(args.raw_root)
    labels = [x.strip() for x in args.labels.split(",") if x.strip()]

    frames: List[pd.DataFrame] = []
    for label in labels:
        d = raw_root / label
        if not d.exists():
            continue
        for fp in sorted(d.rglob("*.csv")):
            try:
                frames.append(_read_one_csv(fp, label))
            except Exception:
                # Keep preprocessing robust; skip broken files and continue.
                continue

    if not frames:
        raise ValueError("No usable raw csv files were found")

    merged = pd.concat(frames, ignore_index=True)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_csv, index=False)

    print("[OK] raw core7 csv prepared")
    print(f"rows={len(merged)}")
    print(f"trips={merged['trip_id'].nunique()}")
    print(f"output={out_csv}")


if __name__ == "__main__":
    main()
