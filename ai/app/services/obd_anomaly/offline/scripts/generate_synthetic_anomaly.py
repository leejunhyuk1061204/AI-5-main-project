import argparse
import copy
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple


CORE7 = [
    "engine_coolant_temp_c",
    "imap_kpa",
    "engine_rpm",
    "vehicle_speed_kmh",
    "intake_air_temp_c",
    "maf_gps",
    "throttle_pos_pct",
]


def _is_finite_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(float(v))


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _dump_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _pick_segment(n: int, hz: int, min_sec: int, max_sec: int, rng: random.Random) -> Tuple[int, int]:
    if n <= 0:
        return 0, 0
    lo = max(1, min_sec * max(1, hz))
    hi = max(lo, min(max_sec * max(1, hz), n))
    seg_len = rng.randint(lo, hi)
    if seg_len >= n:
        return 0, n
    start = rng.randint(0, n - seg_len)
    return start, start + seg_len


def _ensure_series(sample: Dict[str, Any], feat: str, n: int) -> List[float]:
    data = sample.setdefault("data", {})
    arr = data.get(feat, [])
    if not isinstance(arr, list):
        arr = []

    out: List[float] = []
    for i in range(n):
        if i < len(arr) and _is_finite_number(arr[i]):
            out.append(float(arr[i]))
        else:
            out.append(float("nan"))
    data[feat] = out
    return out


def _inject_pattern(
    sample: Dict[str, Any],
    pattern: str,
    min_sec: int,
    max_sec: int,
    rng: random.Random,
) -> Dict[str, Any]:
    out = copy.deepcopy(sample)
    hz = int(out.get("sampling_hz", 1))

    lengths = [
        len(out.get("data", {}).get(feat, []))
        for feat in CORE7
        if isinstance(out.get("data", {}).get(feat, []), list)
    ]
    if not lengths:
        return out
    n = min(lengths)
    if n <= 0:
        return out

    start, end = _pick_segment(n, hz, min_sec, max_sec, rng)
    rpm = _ensure_series(out, "engine_rpm", n)
    speed = _ensure_series(out, "vehicle_speed_kmh", n)
    coolant = _ensure_series(out, "engine_coolant_temp_c", n)
    imap = _ensure_series(out, "imap_kpa", n)
    intake = _ensure_series(out, "intake_air_temp_c", n)
    maf = _ensure_series(out, "maf_gps", n)
    throttle = _ensure_series(out, "throttle_pos_pct", n)

    for i in range(start, end):
        if pattern == "rpm_spike":
            rpm[i] = 6500.0
            throttle[i] = 95.0
            maf[i] = 120.0
            imap[i] = 250.0
        elif pattern == "stall_suspect":
            rpm[i] = 250.0
            throttle[i] = 8.0
            maf[i] = 0.8
        elif pattern == "coolant_overheat":
            coolant[i] = 135.0
            intake[i] = 85.0
            throttle[i] = 70.0
            rpm[i] = 3200.0
        elif pattern == "throttle_mismatch":
            throttle[i] = 98.0
            rpm[i] = 4200.0
            maf[i] = 140.0
        else:
            rpm[i] = 7000.0
            speed[i] = 140.0
            coolant[i] = 125.0
            throttle[i] = 95.0

    out["label"] = f"synthetic_{pattern}"
    out["is_normal"] = False
    out["group_id"] = f"{out.get('group_id', 'unknown')}__syn_{pattern}"
    out["synthetic_meta"] = {
        "pattern": pattern,
        "start_idx": start,
        "end_idx": end,
        "sampling_hz": hz,
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-jsonl", required=True)
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--anomaly-ratio", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-segment-sec", type=int, default=20)
    ap.add_argument("--max-segment-sec", type=int, default=60)
    ap.add_argument(
        "--patterns",
        default="rpm_spike,stall_suspect,coolant_overheat,throttle_mismatch",
        help="Comma-separated pattern names",
    )
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = _load_jsonl(Path(args.input_jsonl))
    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()]
    if not patterns:
        raise ValueError("No patterns provided")

    normals = [r for r in rows if bool(r.get("is_normal", True))]
    if not normals:
        raise ValueError("No normal rows found in input")

    ratio = max(0.0, min(1.0, float(args.anomaly_ratio)))
    target = max(1, int(len(normals) * ratio))
    chosen = rng.sample(normals, min(target, len(normals)))

    out_rows = list(rows)
    synthetic_count = 0
    for i, row in enumerate(chosen):
        pattern = patterns[i % len(patterns)]
        syn = _inject_pattern(
            sample=row,
            pattern=pattern,
            min_sec=args.min_segment_sec,
            max_sec=args.max_segment_sec,
            rng=rng,
        )
        out_rows.append(syn)
        synthetic_count += 1

    _dump_jsonl(Path(args.out_jsonl), out_rows)
    print("[OK] synthetic anomalies generated")
    print(f"input={args.input_jsonl}")
    print(f"output={args.out_jsonl}")
    print(f"normal_rows={len(normals)} synthetic_rows={synthetic_count} total_rows={len(out_rows)}")


if __name__ == "__main__":
    main()

