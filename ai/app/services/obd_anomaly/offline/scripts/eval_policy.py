import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import torch
import torch.nn as nn


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64, latent_dim: int = 16, num_layers: int = 1):
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.to_latent = nn.Linear(hidden_dim, latent_dim)
        self.from_latent = nn.Linear(latent_dim, hidden_dim)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, num_layers, batch_first=True)
        self.out = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        enc_out, _ = self.encoder(x)
        h_last = enc_out[:, -1, :]
        z = self.to_latent(h_last)
        h = self.from_latent(z).unsqueeze(1).repeat(1, x.size(1), 1)
        dec_out, _ = self.decoder(h)
        return self.out(dec_out)


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


def impute_nan(windows: np.ndarray) -> np.ndarray:
    out = windows.copy()
    if out.size == 0:
        return out
    for wi in range(out.shape[0]):
        for fi in range(out.shape[2]):
            col = out[wi, :, fi]
            finite = np.isfinite(col)
            fill = float(np.nanmean(col[finite])) if np.any(finite) else 0.0
            col[~finite] = fill
            out[wi, :, fi] = col
    return out


def summarize_window(window: np.ndarray, schema_features: List[str]) -> Tuple[np.ndarray, List[Tuple[str, float]]]:
    vals: List[float] = []
    feat_scores: List[Tuple[str, float]] = []
    for fi, feat in enumerate(schema_features):
        col = window[:, fi]
        finite = np.isfinite(col)
        if not np.any(finite):
            vals.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            feat_scores.append((feat, 0.0))
            continue
        c = col[finite]
        mean = float(np.mean(c))
        std = float(np.std(c))
        min_v = float(np.min(c))
        max_v = float(np.max(c))
        slope = float(c[-1] - c[0]) if c.size >= 2 else 0.0
        diff_mean = float(np.mean(np.abs(np.diff(c)))) if c.size >= 2 else 0.0
        vals.extend([mean, std, min_v, max_v, slope, diff_mean])

        denom = max(abs(mean), 1.0)
        dyn = min(1.0, max(0.0, 0.5 * (std / denom) + 0.5 * max(abs(slope) / denom, diff_mean / denom)))
        feat_scores.append((feat, float(dyn)))
    return np.array(vals, dtype=np.float32), feat_scores


def if_score(model: Any, vec: np.ndarray) -> float:
    raw = float(model.decision_function(vec.reshape(1, -1))[0])
    return 1.0 / (1.0 + math.exp(4.0 * raw))


def ae_score(model: Any, scaler: Dict[str, Any], window: np.ndarray) -> Tuple[float, np.ndarray]:
    mean = np.array(scaler.get("mean", []), dtype=np.float32)
    std = np.array(scaler.get("std", []), dtype=np.float32)
    if mean.size != window.shape[1] or std.size != window.shape[1]:
        x = window
    else:
        std = np.where(std == 0, 1.0, std)
        x = (window - mean.reshape(1, -1)) / std.reshape(1, -1)

    inp = torch.from_numpy(x.astype(np.float32)).unsqueeze(0)
    with torch.no_grad():
        rec = model(inp).detach().cpu().numpy()[0]
    err_mat = (rec - x) ** 2
    err = float(np.mean(err_mat))
    return err, np.mean(err_mat, axis=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-jsonl", required=True)
    ap.add_argument("--schema", default="app/services/obd_anomaly/models/schemas/v1/schema_core.json")
    ap.add_argument("--iforest", required=True)
    ap.add_argument("--lstm", required=True)
    ap.add_argument("--scaler", required=True)
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--cooldown-sec", type=int, default=60)
    ap.add_argument("--threshold-quantile", type=float, default=0.99)
    ap.add_argument("--out-policy", required=True)
    ap.add_argument("--out-report", required=True)
    args = ap.parse_args()

    schema_payload = json.loads(Path(args.schema).read_text(encoding="utf-8-sig"))
    schema_features = [f for f in schema_payload.get("features", []) if isinstance(f, str)]
    if not schema_features:
        raise ValueError("schema features empty")

    if_model = joblib.load(args.iforest)
    scaler = json.loads(Path(args.scaler).read_text(encoding="utf-8-sig"))

    lstm_obj = torch.load(args.lstm, map_location="cpu")
    if hasattr(lstm_obj, "eval") and hasattr(lstm_obj, "__call__"):
        ae_model = lstm_obj
    elif isinstance(lstm_obj, dict):
        ae_model = LSTMAutoencoder(len(schema_features))
        ae_model.load_state_dict(lstm_obj)
    else:
        raise ValueError("Unsupported lstm artifact format")
    ae_model.eval()

    samples = load_samples(Path(args.val_jsonl))
    samples = [s for s in samples if bool(s.get("is_normal", True))]
    if not samples:
        raise ValueError("No normal samples in val split")

    score_series: List[float] = []
    ae_errs: List[float] = []
    top_examples: List[Dict[str, Any]] = []
    starts: List[int] = []

    current_t = 0
    for s in samples:
        ws = build_windows(s, schema_features, args.window_sec, args.stride_sec)
        ws = impute_nan(ws)
        for w in ws:
            vec, if_feat = summarize_window(w, schema_features)
            s_if = if_score(if_model, vec)
            err, feat_err = ae_score(ae_model, scaler, w)
            ae_errs.append(err)

            e0 = 0.0
            e1 = max(np.quantile(np.array(ae_errs), 0.99), 1e-6)
            s_ae = float(min(1.0, max(0.0, (err - e0) / (e1 - e0))))
            score = 0.5 * s_if + 0.5 * s_ae
            score_series.append(float(score))
            starts.append(current_t)
            current_t += args.stride_sec

            top_idx = np.argsort(feat_err)[-3:][::-1]
            top = [schema_features[int(i)] for i in top_idx]
            top_examples.append({"score": float(score), "top_signals": top})

    scores_np = np.array(score_series, dtype=np.float32)
    threshold = float(np.quantile(scores_np, args.threshold_quantile))

    # alarm frequency per hour (policy simulation)
    events = 0
    streak = 0
    last = -10**9
    for i, s in enumerate(score_series):
        if s >= threshold:
            streak += 1
        else:
            streak = 0
            continue
        if streak < max(1, args.k):
            continue
        if starts[i] - last < max(0, args.cooldown_sec):
            continue
        events += 1
        last = starts[i]

    total_hours = max(1e-6, float((starts[-1] + args.stride_sec) / 3600.0)) if starts else 1e-6
    alarms_per_hour = float(events / total_hours)

    top_examples = sorted(top_examples, key=lambda x: x["score"], reverse=True)[:3]

    ae_min = float(np.quantile(np.array(ae_errs), 0.5)) if ae_errs else 0.0
    ae_max = float(np.quantile(np.array(ae_errs), 0.99)) if ae_errs else 0.2

    policy = {
        "version": "obd-anomaly-policy-v1",
        "threshold": threshold,
        "k_consecutive": int(args.k),
        "cooldown_sec": int(args.cooldown_sec),
        "severity": {
            "duration_bonus_per_window": 0.05,
            "max_bonus": 0.3,
            "critical": 0.85,
            "warning": 0.7,
        },
        "gating": {
            "ae_min_coverage": 0.8,
            "ae_max_gap": 3,
            "both_min_coverage": 0.6,
            "w_coverage_c0": 0.6,
            "w_coverage_c1": 0.95,
        },
        "ae_score": {
            "error_min": ae_min,
            "error_max": max(ae_max, ae_min + 1e-6),
        },
    }

    Path(args.out_policy).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_policy).write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Eval Policy Report",
        "",
        "## Score Quantiles",
        f"- q50: {float(np.quantile(scores_np, 0.5)):.6f}",
        f"- q90: {float(np.quantile(scores_np, 0.9)):.6f}",
        f"- q95: {float(np.quantile(scores_np, 0.95)):.6f}",
        f"- q99: {float(np.quantile(scores_np, 0.99)):.6f}",
        "",
        "## Alarm Frequency",
        f"- threshold: {threshold:.6f}",
        f"- k_consecutive: {args.k}",
        f"- cooldown_sec: {args.cooldown_sec}",
        f"- alarms_per_hour: {alarms_per_hour:.6f}",
        "",
        "## Top Signals Examples (3)",
    ]
    for i, ex in enumerate(top_examples, start=1):
        report_lines.append(f"- example_{i}: score={ex['score']:.6f}, top_signals={', '.join(ex['top_signals'])}")

    Path(args.out_report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_report).write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("[OK] policy evaluated")
    print(f"policy={args.out_policy}")
    print(f"report={args.out_report}")


if __name__ == "__main__":
    main()
