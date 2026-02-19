import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest


def load_samples(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def build_windows(sample: Dict[str, Any], schema_features: List[str], window_sec: int, stride_sec: int) -> np.ndarray:
    hz = int(sample.get("sampling_hz", 1))
    data = sample["data"]
    n = min(len(data.get(feat, [])) for feat in schema_features)
    if n <= 0:
        return np.empty((0, 0, 0), dtype=np.float32)

    series = np.stack(
        [np.array(data.get(feat, [float("nan")] * n)[:n], dtype=np.float32) for feat in schema_features],
        axis=1,
    )
    wsize = window_sec * hz
    step = stride_sec * hz
    if n < wsize:
        return np.empty((0, wsize, len(schema_features)), dtype=np.float32)

    windows: List[np.ndarray] = []
    for start in range(0, n - wsize + 1, step):
        windows.append(series[start : start + wsize])
    return np.stack(windows) if windows else np.empty((0, wsize, len(schema_features)), dtype=np.float32)


def window_summary(window: np.ndarray, schema_features: List[str]) -> np.ndarray:
    vals: List[float] = []
    for fi, _ in enumerate(schema_features):
        col = window[:, fi]
        finite = np.isfinite(col)
        if not np.any(finite):
            vals.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            continue
        c = col[finite]
        mean = float(np.mean(c))
        std = float(np.std(c))
        min_v = float(np.min(c))
        max_v = float(np.max(c))
        slope = float(c[-1] - c[0]) if c.size >= 2 else 0.0
        diff_mean = float(np.mean(np.abs(np.diff(c)))) if c.size >= 2 else 0.0
        vals.extend([mean, std, min_v, max_v, slope, diff_mean])
    return np.array(vals, dtype=np.float32)


def score_to_01(raw: np.ndarray) -> np.ndarray:
    # higher anomaly score when decision_function is lower
    return 1.0 / (1.0 + np.exp(4.0 * raw))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-jsonl", required=True)
    ap.add_argument("--schema", default="app/services/obd_anomaly/models/schemas/v1/schema_core.json")
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--out-model", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--n-estimators", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    schema_payload = json.loads(Path(args.schema).read_text(encoding="utf-8-sig"))
    schema_features = [f for f in schema_payload.get("features", []) if isinstance(f, str)]
    if not schema_features:
        raise ValueError("schema features empty")

    samples = load_samples(Path(args.train_jsonl))
    samples = [s for s in samples if bool(s.get("is_normal", True))]
    if not samples:
        raise ValueError("No normal samples in train split")

    vecs: List[np.ndarray] = []
    for s in samples:
        ws = build_windows(s, schema_features, args.window_sec, args.stride_sec)
        for w in ws:
            vecs.append(window_summary(w, schema_features))
    if not vecs:
        raise ValueError("No windows generated for IF training")

    X = np.stack(vecs).astype(np.float32)

    model = IsolationForest(
        n_estimators=args.n_estimators,
        contamination="auto",
        random_state=args.seed,
        n_jobs=-1,
    )
    model.fit(X)

    Path(args.out_model).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.out_model)

    raw = model.decision_function(X)
    scores = score_to_01(raw)
    qs = np.quantile(scores, [0.5, 0.9, 0.95, 0.99]).tolist()

    report = {
        "windows": int(X.shape[0]),
        "features": int(X.shape[1]),
        "score_quantiles": {
            "q50": float(qs[0]),
            "q90": float(qs[1]),
            "q95": float(qs[2]),
            "q99": float(qs[3]),
        },
        "model": args.out_model,
    }
    Path(args.out_report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK] iforest trained")
    print(f"model={args.out_model}")
    print(f"windows={X.shape[0]}")


if __name__ == "__main__":
    main()
