import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd


NORMAL_LABEL_DEFAULTS = {"normal", "frei", "stau", "0", "NORMAL", 0}


def load_schema_features(schema_path: Path) -> List[str]:
    payload = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    feats = payload.get("features", [])
    return [f for f in feats if isinstance(f, str)]


def _safe_float(v: Any) -> float:
    try:
        if v is None:
            return float("nan")
        return float(v)
    except Exception:
        return float("nan")


def _ensure_group_id(item: Dict[str, Any]) -> str:
    gid = item.get("trip_id") or item.get("session_id") or item.get("group_id")
    if gid is None:
        raise ValueError("Missing group id: one of trip_id/session_id/group_id is required")
    return str(gid)


def _expand_aggregated_item(item: Dict[str, Any], schema_features: List[str], default_hz: int) -> Dict[str, Any]:
    data = item.get("data")
    if not isinstance(data, dict):
        raise ValueError("Aggregated item requires data as dict(feature -> series)")

    lengths = [len(v) for v in data.values() if isinstance(v, list)]
    if not lengths:
        raise ValueError("Aggregated item has empty series")
    n = min(lengths)

    out_series: Dict[str, List[float]] = {}
    for feat in schema_features:
        arr = data.get(feat, [])
        if not isinstance(arr, list):
            arr = []
        vals = [_safe_float(x) for x in arr[:n]]
        if len(vals) < n:
            vals.extend([float("nan")] * (n - len(vals)))
        out_series[feat] = vals

    return {
        "group_id": _ensure_group_id(item),
        "label": item.get("label", item.get("class", "normal")),
        "sampling_hz": int(item.get("sampling_hz", default_hz)),
        "data": out_series,
    }


def _from_row_dataframe(df: pd.DataFrame, schema_features: List[str], group_col: str, label_col: str | None, sampling_hz: int) -> List[Dict[str, Any]]:
    if group_col not in df.columns:
        raise ValueError(f"Missing group column: {group_col}")

    out: List[Dict[str, Any]] = []
    for gid, g in df.groupby(group_col, sort=False):
        g2 = g.sort_values("t") if "t" in g.columns else g
        series: Dict[str, List[float]] = {}
        for feat in schema_features:
            if feat in g2.columns:
                series[feat] = [_safe_float(x) for x in g2[feat].tolist()]
            elif "features" in g2.columns:
                rows = []
                for raw in g2["features"].tolist():
                    obj = raw
                    if isinstance(raw, str):
                        try:
                            obj = json.loads(raw)
                        except Exception:
                            obj = {}
                    if not isinstance(obj, dict):
                        obj = {}
                    rows.append(_safe_float(obj.get(feat)))
                series[feat] = rows
            else:
                series[feat] = [float("nan")] * len(g2)

        lbl = g2[label_col].iloc[0] if label_col and label_col in g2.columns else "normal"
        out.append(
            {
                "group_id": str(gid),
                "label": lbl,
                "sampling_hz": sampling_hz,
                "data": series,
            }
        )
    return out


def load_samples(input_path: Path, schema_features: List[str], group_col: str | None, label_col: str | None, sampling_hz: int) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []

    if input_path.suffix.lower() == ".jsonl":
        first_non_agg: List[Dict[str, Any]] = []
        with input_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if isinstance(item.get("data"), dict):
                    samples.append(_expand_aggregated_item(item, schema_features, sampling_hz))
                else:
                    first_non_agg.append(item)

        if first_non_agg:
            df = pd.DataFrame(first_non_agg)
            inferred_group = group_col or ("trip_id" if "trip_id" in df.columns else "session_id")
            if inferred_group is None:
                raise ValueError("For row-wise jsonl, --group-col is required unless trip_id/session_id exists")
            samples.extend(_from_row_dataframe(df, schema_features, inferred_group, label_col, sampling_hz))

    elif input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
        inferred_group = group_col or ("trip_id" if "trip_id" in df.columns else "session_id")
        if inferred_group is None:
            raise ValueError("For csv, --group-col is required unless trip_id/session_id exists")
        samples = _from_row_dataframe(df, schema_features, inferred_group, label_col, sampling_hz)

    else:
        raise ValueError("Unsupported input format. Use .jsonl or .csv")

    dedup: Dict[str, Dict[str, Any]] = {}
    for s in samples:
        dedup[s["group_id"]] = s
    return list(dedup.values())


def split_groups(samples: List[Dict[str, Any]], seed: int, train_ratio: float, val_ratio: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    groups = [s["group_id"] for s in samples]
    random.Random(seed).shuffle(groups)

    n = len(groups)
    n_train = max(1, int(n * train_ratio))
    n_val = max(1, int(n * val_ratio)) if n >= 3 else max(0, n - n_train)
    n_train = min(n_train, n)
    n_val = min(n_val, max(0, n - n_train))

    train_g = set(groups[:n_train])
    val_g = set(groups[n_train : n_train + n_val])
    test_g = set(groups[n_train + n_val :])

    train = [s for s in samples if s["group_id"] in train_g]
    val = [s for s in samples if s["group_id"] in val_g]
    test = [s for s in samples if s["group_id"] in test_g]
    return train, val, test


def is_normal_label(label: Any, normal_labels: set[str]) -> bool:
    if isinstance(label, (int, float)):
        return str(int(label)) in normal_labels or label == 0
    return str(label) in normal_labels


def dump_jsonl(path: Path, samples: Iterable[Dict[str, Any]], window_sec: int, stride_sec: int, normal_labels: set[str]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for s in samples:
            n = min(len(v) for v in s["data"].values()) if s["data"] else 0
            payload = {
                "group_id": s["group_id"],
                "label": s.get("label", "normal"),
                "is_normal": is_normal_label(s.get("label", "normal"), normal_labels),
                "sampling_hz": int(s.get("sampling_hz", 1)),
                "duration_sec": int(n / max(1, int(s.get("sampling_hz", 1)))),
                "window_sec": window_sec,
                "stride_sec": stride_sec,
                "channels": list(s["data"].keys()),
                "data": {k: v[:n] for k, v in s["data"].items()},
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_report(path: Path, train_n: int, val_n: int, test_n: int, samples: List[Dict[str, Any]]) -> None:
    total_rows = 0
    for s in samples:
        if s["data"]:
            total_rows += min(len(v) for v in s["data"].values())

    report = [
        "# Dataset Prepare Report",
        "",
        f"- groups_total: {len(samples)}",
        f"- rows_total: {total_rows}",
        f"- split_groups: train={train_n}, val={val_n}, test={test_n}",
    ]
    path.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input .jsonl or .csv")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--schema", default="app/services/obd_anomaly/models/schemas/v1/schema_core.json")
    ap.add_argument("--group-col", default=None)
    ap.add_argument("--label-col", default=None)
    ap.add_argument("--sampling-hz", type=int, default=1)
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--train-ratio", type=float, default=0.7)
    ap.add_argument("--val-ratio", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--normal-labels", default="normal,frei,stau,0,NORMAL")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_features = load_schema_features(Path(args.schema))
    normal_labels = {x.strip() for x in args.normal_labels.split(",") if x.strip()}

    samples = load_samples(in_path, schema_features, args.group_col, args.label_col, args.sampling_hz)
    if len(samples) < 2:
        raise ValueError("Need at least 2 groups for split")

    train, val, test = split_groups(samples, args.seed, args.train_ratio, args.val_ratio)

    n_train = dump_jsonl(out_dir / "train.jsonl", train, args.window_sec, args.stride_sec, normal_labels)
    n_val = dump_jsonl(out_dir / "val.jsonl", val, args.window_sec, args.stride_sec, normal_labels)
    n_test = dump_jsonl(out_dir / "test.jsonl", test, args.window_sec, args.stride_sec, normal_labels)

    write_report(out_dir / "prepare_report.md", n_train, n_val, n_test, samples)

    print("[OK] dataset prepared")
    print(f"out_dir={out_dir}")
    print(f"groups: train={n_train}, val={n_val}, test={n_test}")


if __name__ == "__main__":
    main()
