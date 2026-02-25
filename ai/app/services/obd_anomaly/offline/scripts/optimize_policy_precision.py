import argparse
import csv
import json
import math
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdSample
from ai.app.services.obd_anomaly.core import engine_lstm_ae
from ai.app.services.obd_anomaly.core.policy.threshold_policy import apply_engine_policy
from ai.app.services.obd_anomaly.core.scorers.engine_scorer import GateDecision
from ai.app.services.obd_anomaly.windowing import make_windows


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(json.loads(s))
    return out


def safe_div(a: float, b: float) -> float:
    return (a / b) if b != 0 else 0.0


def to_request(sample: Dict[str, Any], window_sec: int, stride_sec: int) -> ObdAnomalyRequest:
    hz = int(sample.get("sampling_hz", 1))
    data_dict = sample.get("data", {})
    if not isinstance(data_dict, dict):
        data_dict = {}
    n = min((len(v) for v in data_dict.values() if isinstance(v, list)), default=0)

    rows: List[ObdSample] = []
    for i in range(n):
        feat: Dict[str, float] = {}
        for k, arr in data_dict.items():
            if not isinstance(arr, list) or i >= len(arr):
                continue
            v = arr[i]
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                feat[k] = float(v)
        t_ms = int(round((1000.0 * i) / max(1, hz)))
        rows.append(ObdSample(t=t_ms, features=feat))

    return ObdAnomalyRequest(
        vehicle_id="veh-opt",
        trip_id=str(sample.get("group_id", "trip-opt")),
        mode="DRIVING",
        duration_sec=max(1, int(n / max(1, hz))),
        sampling_hz=hz,
        timestamp_unit="ms",
        data=rows,
        options={
            "domains": ["engine"],
            "return": "summary",
            "window_sec": window_sec,
            "stride_sec": stride_sec,
            "top_signals": "off",
        },
    )


def force_mode(mode: str):
    scorer = engine_lstm_ae._SCORER
    original = scorer._decide_gate

    if mode == "HYBRID":
        class Ctx:
            def __enter__(self):
                return None
            def __exit__(self, exc_type, exc, tb):
                return False
        return Ctx()

    def _if_only(self, q):
        return GateDecision(mode="IF_ONLY", ae_weight=0.0)

    def _ae_only(self, q):
        return GateDecision(mode="AE_ONLY", ae_weight=1.0)

    patched = _if_only if mode == "IF_ONLY" else _ae_only

    class Ctx:
        def __enter__(self):
            scorer._decide_gate = types.MethodType(patched, scorer)
            return None
        def __exit__(self, exc_type, exc, tb):
            scorer._decide_gate = original
            return False
    return Ctx()


def collect_traces(mode: str, normal_rows: List[Dict[str, Any]], synth_rows: List[Dict[str, Any]], window_sec: int, stride_sec: int):
    scorer = engine_lstm_ae._SCORER
    normal_traces: List[Dict[str, Any]] = []
    synth_traces: List[Dict[str, Any]] = []

    with force_mode(mode):
        for row in normal_rows:
            req = to_request(row, window_sec, stride_sec)
            ws = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)
            scores, starts = [], []
            for w in ws:
                env = scorer.score_window(req, w)
                if env.score is None or env.status.value != "PROCESSED":
                    continue
                scores.append(float(env.score))
                starts.append(int(w.start_t))
            normal_traces.append({"duration_sec": float(req.duration_sec), "scores": scores, "starts": starts})

        for row in synth_rows:
            req = to_request(row, window_sec, stride_sec)
            ws = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)
            scores, starts = [], []
            for w in ws:
                env = scorer.score_window(req, w)
                if env.score is None or env.status.value != "PROCESSED":
                    continue
                scores.append(float(env.score))
                starts.append(int(w.start_t))
            synth_traces.append({"is_anomaly": not bool(row.get("is_normal", True)), "scores": scores, "starts": starts})

    return normal_traces, synth_traces


def eval_policy(normal_traces, synth_traces, threshold: float, k: int, cooldown: int):
    policy = {"threshold": threshold, "k_consecutive": k, "cooldown_sec": cooldown, "severity": {"duration_bonus_per_window": 0.05, "max_bonus": 0.3}}

    total_hours = 0.0
    n_events = 0
    for tr in normal_traces:
        total_hours += float(tr["duration_sec"]) / 3600.0
        n_events += len(apply_engine_policy(tr["scores"], tr["starts"], policy))
    alarms_per_hour = safe_div(float(n_events), max(1e-6, total_hours))

    tp = fp = tn = fn = 0
    for tr in synth_traces:
        pred = bool(apply_engine_policy(tr["scores"], tr["starts"], policy))
        true = bool(tr["is_anomaly"])
        if true and pred:
            tp += 1
        elif true and (not pred):
            fn += 1
        elif (not true) and pred:
            fp += 1
        else:
            tn += 1

    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    fpr = safe_div(fp, fp + tn)

    return {
        "threshold": threshold,
        "k_consecutive": k,
        "cooldown_sec": cooldown,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "alarms_per_hour": alarms_per_hour,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_md(path: Path, mode: str, rows: List[Dict[str, Any]], top_n: int, min_recall: float, max_alarms: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    top = rows[:top_n]
    lines = [
        "# Precision-Priority Policy Optimization",
        "",
        f"- mode: {mode}",
        f"- filter: recall>={min_recall}, alarms_per_hour<={max_alarms}",
        "",
        "| rank | threshold | k | cooldown_sec | precision | recall | f1 | fpr | alarms_per_hour | TP | FP | TN | FN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(top, start=1):
        lines.append(
            f"| {i} | {r['threshold']:.6f} | {r['k_consecutive']} | {r['cooldown_sec']} | {r['precision']:.6f} | {r['recall']:.6f} | {r['f1']:.6f} | {r['fpr']:.6f} | {r['alarms_per_hour']:.6f} | {r['tp']} | {r['fp']} | {r['tn']} | {r['fn']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-jsonl", required=True)
    ap.add_argument("--val-synthetic-jsonl", required=True)
    ap.add_argument("--mode", default="AE_ONLY", choices=["HYBRID", "IF_ONLY", "AE_ONLY"])
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--min-recall", type=float, default=0.8)
    ap.add_argument("--max-alarms-per-hour", type=float, default=2.0)
    ap.add_argument("--top-n", type=int, default=5)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    normal_rows = [r for r in load_jsonl(Path(args.val_jsonl)) if bool(r.get("is_normal", True))]
    synth_rows = load_jsonl(Path(args.val_synthetic_jsonl))

    ntr, strc = collect_traces(args.mode, normal_rows, synth_rows, args.window_sec, args.stride_sec)

    thresholds = [round(x, 6) for x in np.linspace(0.70, 0.95, 11)]
    ks = [1, 2, 3, 4]
    cooldowns = [30, 60, 120, 180]

    rows: List[Dict[str, Any]] = []
    for th in thresholds:
        for k in ks:
            for cd in cooldowns:
                r = eval_policy(ntr, strc, th, k, cd)
                r["mode"] = args.mode
                rows.append(r)

    filtered = [
        r for r in rows
        if r["recall"] >= args.min_recall and r["alarms_per_hour"] <= args.max_alarms_per_hour
    ]

    ranked = sorted(
        filtered if filtered else rows,
        key=lambda x: (-x["precision"], x["fpr"], x["alarms_per_hour"], -x["recall"], -x["f1"]),
    )

    write_csv(Path(args.out_csv), ranked)
    write_md(Path(args.out_md), args.mode, ranked, args.top_n, args.min_recall, args.max_alarms_per_hour)

    if ranked:
        best = ranked[0]
        print("[BEST]", json.dumps(best, ensure_ascii=False))
    print("[OK] precision-priority optimization complete")
    print(f"csv={args.out_csv}")
    print(f"md={args.out_md}")


if __name__ == "__main__":
    main()
