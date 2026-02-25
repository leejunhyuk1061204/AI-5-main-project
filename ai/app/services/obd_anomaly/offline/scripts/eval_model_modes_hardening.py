import argparse
import csv
import json
import math
import statistics
import time
import types
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdSample
from ai.app.services.obd_anomaly.core import engine_lstm_ae
from ai.app.services.obd_anomaly.core.policy.threshold_policy import apply_engine_policy
from ai.app.services.obd_anomaly.core.scorers.engine_scorer import GateDecision
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService
from ai.app.services.obd_anomaly.windowing import make_windows


@dataclass
class ModeEval:
    mode: str
    threshold: float
    k_consecutive: int
    cooldown_sec: int
    alarms_per_hour: float
    alert_rate_per_window: float
    q50: float
    q90: float
    q95: float
    q99: float
    qmax: float
    usable_window_rate: float
    latency_ms_per_window_mean: float
    latency_ms_per_window_p95: float
    sample_precision: float
    sample_recall: float
    sample_f1: float
    window_f1: float
    event_hit_rate: float
    ttd_mean_sec: float
    ttd_p95_sec: float
    ttd_detected: int
    ttd_total_anomaly: int
    injection_types: str
    gate_if_only_rate: float
    gate_ae_only_rate: float
    gate_both_rate: float
    sample_f1_ci_low: float
    sample_f1_ci_high: float
    alarms_per_hour_ci_low: float
    alarms_per_hour_ci_high: float


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


def f1_from_counts(tp: int, fp: int, fn: int) -> float:
    p = safe_div(float(tp), float(tp + fp))
    r = safe_div(float(tp), float(tp + fn))
    return safe_div(2.0 * p * r, p + r)


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def to_request(sample: Dict[str, Any], window_sec: int, stride_sec: int, return_raw: bool = False) -> ObdAnomalyRequest:
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
        vehicle_id="veh-eval",
        trip_id=str(sample.get("group_id", "trip-eval")),
        mode="DRIVING",
        duration_sec=max(1, int(n / max(1, hz))),
        sampling_hz=hz,
        timestamp_unit="ms",
        data=rows,
        options={
            "domains": ["engine"],
            "return": "raw" if return_raw else "summary",
            "window_sec": int(window_sec),
            "stride_sec": int(stride_sec),
            "top_signals": "off",
        },
    )


def trim_sample(sample: Dict[str, Any], seconds: int) -> Dict[str, Any]:
    hz = int(sample.get("sampling_hz", 1))
    n = max(1, hz * max(1, seconds))
    out = dict(sample)
    data = sample.get("data", {}) if isinstance(sample.get("data", {}), dict) else {}
    new_data: Dict[str, Any] = {}
    for k, arr in data.items():
        if isinstance(arr, list):
            new_data[k] = arr[:n]
    out["data"] = new_data
    out["duration_sec"] = max(1, int(n / max(1, hz)))
    return out


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


def ci95(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    arr = np.array(values, dtype=np.float64)
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def compute_metrics(normal_traces: List[Dict[str, Any]], synth_traces: List[Dict[str, Any]], policy: Dict[str, Any]) -> Dict[str, float]:
    threshold = float(policy.get("threshold", 0.7))

    all_scores: List[float] = []
    alert_cnt = 0
    all_events = 0
    total_hours = 0.0

    for tr in normal_traces:
        scores = [float(s) for s in tr.get("scores", [])]
        starts = [int(t) for t in tr.get("starts", [])]
        dur = float(tr.get("duration_sec", 0.0))
        all_scores.extend(scores)
        alert_cnt += sum(1 for s in scores if s >= threshold)
        total_hours += max(0.0, dur) / 3600.0
        all_events += len(apply_engine_policy(scores, starts, policy))

    s_tp = s_fp = s_tn = s_fn = 0
    w_tp = w_fp = w_tn = w_fn = 0
    ttd_values: List[float] = []
    ttd_total = 0
    ttd_detected = 0

    for tr in synth_traces:
        is_anom = bool(tr.get("is_anomaly", False))
        scores = [float(s) for s in tr.get("scores", [])]
        starts = [int(t) for t in tr.get("starts", [])]
        events = apply_engine_policy(scores, starts, policy)
        y_pred = bool(events)

        if is_anom and y_pred:
            s_tp += 1
        elif is_anom and not y_pred:
            s_fn += 1
        elif (not is_anom) and y_pred:
            s_fp += 1
        else:
            s_tn += 1

        inj_start = tr.get("inj_start_sec")
        inj_end = tr.get("inj_end_sec")
        ranges = tr.get("win_ranges", [])
        if isinstance(inj_start, (int, float)) and isinstance(inj_end, (int, float)):
            ttd_total += 1
            if y_pred:
                ttd_detected += 1
                ttd_values.append(max(0.0, float(events[0].get("start_t", 0.0)) - float(inj_start)))

            for i, wr in enumerate(ranges):
                ws = float(wr[0])
                we = float(wr[1])
                y_true_w = overlap(ws, we, float(inj_start), float(inj_end))
                y_pred_w = bool(i < len(scores) and scores[i] >= threshold)
                if y_true_w and y_pred_w:
                    w_tp += 1
                elif y_true_w and (not y_pred_w):
                    w_fn += 1
                elif (not y_true_w) and y_pred_w:
                    w_fp += 1
                else:
                    w_tn += 1

    sample_precision = safe_div(float(s_tp), float(s_tp + s_fp))
    sample_recall = safe_div(float(s_tp), float(s_tp + s_fn))
    sample_f1 = f1_from_counts(s_tp, s_fp, s_fn)
    window_f1 = f1_from_counts(w_tp, w_fp, w_fn)
    event_hit_rate = safe_div(float(ttd_detected), float(max(1, ttd_total)))

    if all_scores:
        arr = np.array(all_scores, dtype=np.float64)
        q50 = float(np.quantile(arr, 0.5))
        q90 = float(np.quantile(arr, 0.9))
        q95 = float(np.quantile(arr, 0.95))
        q99 = float(np.quantile(arr, 0.99))
        qmax = float(np.max(arr))
    else:
        q50 = q90 = q95 = q99 = qmax = 0.0

    ttd_mean = float(np.mean(np.array(ttd_values, dtype=np.float64))) if ttd_values else 0.0
    ttd_p95 = float(np.quantile(np.array(ttd_values, dtype=np.float64), 0.95)) if ttd_values else 0.0

    return {
        "alarms_per_hour": safe_div(float(all_events), float(max(1e-6, total_hours))),
        "alert_rate_per_window": safe_div(float(alert_cnt), float(max(1, len(all_scores)))),
        "q50": q50,
        "q90": q90,
        "q95": q95,
        "q99": q99,
        "qmax": qmax,
        "sample_precision": sample_precision,
        "sample_recall": sample_recall,
        "sample_f1": sample_f1,
        "window_f1": window_f1,
        "event_hit_rate": event_hit_rate,
        "ttd_mean_sec": ttd_mean,
        "ttd_p95_sec": ttd_p95,
        "ttd_detected": float(ttd_detected),
        "ttd_total": float(ttd_total),
    }


def bootstrap_ci(normal_traces: List[Dict[str, Any]], synth_traces: List[Dict[str, Any]], policy: Dict[str, Any], boot_iters: int, seed: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    rng = np.random.default_rng(seed)
    sf1_vals: List[float] = []
    aph_vals: List[float] = []

    n_norm = len(normal_traces)
    n_syn = len(synth_traces)

    if n_norm == 0 or n_syn == 0:
        return (0.0, 0.0), (0.0, 0.0)

    for _ in range(max(1, boot_iters)):
        idx_n = rng.integers(0, n_norm, size=n_norm)
        idx_s = rng.integers(0, n_syn, size=n_syn)
        b_norm = [normal_traces[int(i)] for i in idx_n]
        b_syn = [synth_traces[int(i)] for i in idx_s]
        m = compute_metrics(b_norm, b_syn, policy)
        sf1_vals.append(float(m["sample_f1"]))
        aph_vals.append(float(m["alarms_per_hour"]))

    return ci95(sf1_vals), ci95(aph_vals)


def eval_mode(mode: str, normal_rows: List[Dict[str, Any]], synth_rows: List[Dict[str, Any]], window_sec: int, stride_sec: int, policy: Dict[str, Any], boot_iters: int, seed: int) -> Tuple[ModeEval, List[Dict[str, Any]], List[Dict[str, Any]]]:
    scorer = engine_lstm_ae._SCORER
    threshold = float(policy.get("threshold", 0.7))

    g = policy.get("gating", {})
    usable_min_cov = float(g.get("both_min_coverage", 0.6))

    total_windows = 0
    usable_windows = 0
    gate_if_only = 0
    gate_ae_only = 0
    gate_both = 0
    lat_ms: List[float] = []

    normal_traces: List[Dict[str, Any]] = []
    synth_traces: List[Dict[str, Any]] = []

    with force_mode(mode):
        for row in normal_rows:
            req = to_request(row, window_sec, stride_sec)
            windows = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)
            scores: List[float] = []
            starts: List[int] = []
            for w in windows:
                total_windows += 1
                t0 = time.perf_counter()
                env = scorer.score_window(req, w)
                lat_ms.append((time.perf_counter() - t0) * 1000.0)
                if env.score is None or env.status.value != "PROCESSED":
                    continue
                scores.append(float(env.score))
                starts.append(int(w.start_t))

                d = env.details if isinstance(env.details, dict) else {}
                q = d.get("quality", {}) if isinstance(d.get("quality", {}), dict) else {}
                gmode = str((d.get("gating", {}) if isinstance(d.get("gating", {}), dict) else {}).get("mode", ""))
                if gmode == "IF_ONLY":
                    gate_if_only += 1
                elif gmode == "AE_ONLY":
                    gate_ae_only += 1
                elif gmode == "BOTH":
                    gate_both += 1

                n_present = int(q.get("n_present", 0))
                coverage = float(q.get("coverage", 0.0))
                uniform_ts = bool(q.get("uniform_ts", False))
                if n_present >= int(scorer._core_min()) and coverage >= usable_min_cov and uniform_ts:
                    usable_windows += 1

            normal_traces.append({
                "duration_sec": float(req.duration_sec),
                "scores": scores,
                "starts": starts,
            })

        for row in synth_rows:
            req = to_request(row, window_sec, stride_sec)
            windows = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)
            scores: List[float] = []
            starts: List[int] = []
            wranges: List[Tuple[float, float]] = []

            for w in windows:
                t0 = time.perf_counter()
                env = scorer.score_window(req, w)
                lat_ms.append((time.perf_counter() - t0) * 1000.0)
                if env.score is None or env.status.value != "PROCESSED":
                    continue
                scores.append(float(env.score))
                starts.append(int(w.start_t))
                wranges.append((float(w.start_t), float(w.end_t + 1)))

            meta = row.get("synthetic_meta", {}) if isinstance(row.get("synthetic_meta", {}), dict) else {}
            hz = max(1, int(row.get("sampling_hz", 1)))
            inj_start = float(meta.get("start_idx")) / float(hz) if isinstance(meta.get("start_idx"), int) else None
            inj_end = float(meta.get("end_idx")) / float(hz) if isinstance(meta.get("end_idx"), int) else None
            pattern = str(meta.get("pattern", "UNKNOWN"))

            synth_traces.append({
                "is_anomaly": not bool(row.get("is_normal", True)),
                "pattern": pattern,
                "inj_start_sec": inj_start,
                "inj_end_sec": inj_end,
                "scores": scores,
                "starts": starts,
                "win_ranges": wranges,
            })

    m = compute_metrics(normal_traces, synth_traces, policy)
    sf1_ci, aph_ci = bootstrap_ci(normal_traces, synth_traces, policy, boot_iters=boot_iters, seed=seed)

    if lat_ms:
        larr = np.array(lat_ms, dtype=np.float64)
        lat_mean = float(np.mean(larr))
        lat_p95 = float(np.quantile(larr, 0.95))
    else:
        lat_mean = lat_p95 = 0.0

    inj_types = sorted(set(str(t.get("pattern", "UNKNOWN")) for t in synth_traces if t.get("inj_start_sec") is not None))

    out = ModeEval(
        mode=mode,
        threshold=float(policy.get("threshold", 0.7)),
        k_consecutive=int(policy.get("k_consecutive", 1)),
        cooldown_sec=int(policy.get("cooldown_sec", 0)),
        alarms_per_hour=float(m["alarms_per_hour"]),
        alert_rate_per_window=float(m["alert_rate_per_window"]),
        q50=float(m["q50"]),
        q90=float(m["q90"]),
        q95=float(m["q95"]),
        q99=float(m["q99"]),
        qmax=float(m["qmax"]),
        usable_window_rate=safe_div(float(usable_windows), float(max(1, total_windows))),
        latency_ms_per_window_mean=lat_mean,
        latency_ms_per_window_p95=lat_p95,
        sample_precision=float(m["sample_precision"]),
        sample_recall=float(m["sample_recall"]),
        sample_f1=float(m["sample_f1"]),
        window_f1=float(m["window_f1"]),
        event_hit_rate=float(m["event_hit_rate"]),
        ttd_mean_sec=float(m["ttd_mean_sec"]),
        ttd_p95_sec=float(m["ttd_p95_sec"]),
        ttd_detected=int(m["ttd_detected"]),
        ttd_total_anomaly=int(m["ttd_total"]),
        injection_types=",".join(inj_types),
        gate_if_only_rate=safe_div(float(gate_if_only), float(max(1, total_windows))),
        gate_ae_only_rate=safe_div(float(gate_ae_only), float(max(1, total_windows))),
        gate_both_rate=safe_div(float(gate_both), float(max(1, total_windows))),
        sample_f1_ci_low=float(sf1_ci[0]),
        sample_f1_ci_high=float(sf1_ci[1]),
        alarms_per_hour_ci_low=float(aph_ci[0]),
        alarms_per_hour_ci_high=float(aph_ci[1]),
    )

    return out, normal_traces, synth_traces


def write_compare_csv(path: Path, rows: List[ModeEval]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(ModeEval.__annotations__.keys()))
        for r in rows:
            w.writerow([getattr(r, k) for k in ModeEval.__annotations__.keys()])


def write_compare_md(path: Path, rows: List[ModeEval], condition: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# LSTM(AE) vs IF Same-Condition Comparison")
    lines.append("")
    lines.append(f"- condition: {condition}")
    lines.append("- compare_status: VALID")
    lines.append("")
    lines.append("| mode | alarms_per_hour | alarms_ci95 | sample_f1 | sample_f1_ci95 | window_f1 | event_hit_rate | ttd_mean_sec | latency_mean_ms/window | latency_p95_ms/window |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r.mode} | {r.alarms_per_hour:.6f} | [{r.alarms_per_hour_ci_low:.6f}, {r.alarms_per_hour_ci_high:.6f}] | {r.sample_f1:.6f} | [{r.sample_f1_ci_low:.6f}, {r.sample_f1_ci_high:.6f}] | {r.window_f1:.6f} | {r.event_hit_rate:.6f} | {r.ttd_mean_sec:.3f} | {r.latency_ms_per_window_mean:.3f} | {r.latency_ms_per_window_p95:.3f} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("- one-class normal setting: synthetic PR/F1 has generalization limits to real anomaly distribution")
    lines.append("- bootstrap CI: sample-level resampling for sample_f1, normal-trip resampling for alarms_per_hour")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sensitivity_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
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


def write_latency_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
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


def policy_with(base: Dict[str, Any], threshold: float, k: int, cooldown: int) -> Dict[str, Any]:
    p = dict(base)
    p["threshold"] = float(threshold)
    p["k_consecutive"] = int(k)
    p["cooldown_sec"] = int(cooldown)
    return p


def build_sensitivity(mode: str, base_policy: Dict[str, Any], normal_traces: List[Dict[str, Any]], synth_traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bt = float(base_policy.get("threshold", 0.7))
    thresholds = sorted(set([round(max(0.0, min(1.0, bt - 0.05)), 6), round(bt, 6), round(max(0.0, min(1.0, bt + 0.05)), 6)]))
    ks = [1, 2, 3]
    cds = [30, 60, 120]
    out: List[Dict[str, Any]] = []
    for th in thresholds:
        for k in ks:
            for cd in cds:
                p = policy_with(base_policy, threshold=th, k=k, cooldown=cd)
                m = compute_metrics(normal_traces, synth_traces, p)
                out.append({
                    "mode": mode,
                    "threshold": th,
                    "k_consecutive": k,
                    "cooldown_sec": cd,
                    "alarms_per_hour": float(m["alarms_per_hour"]),
                    "sample_f1": float(m["sample_f1"]),
                    "window_f1": float(m["window_f1"]),
                    "event_hit_rate": float(m["event_hit_rate"]),
                    "ttd_mean_sec": float(m["ttd_mean_sec"]),
                })
    return out


def latency_benchmark(mode: str, sample: Dict[str, Any], window_sec: int, stride_sec: int, n_runs: int, warmup: int) -> Dict[str, Any]:
    svc = ObdAnomalyService()
    req = to_request(trim_sample(sample, seconds=90), window_sec=window_sec, stride_sec=stride_sec, return_raw=False)

    vals: List[float] = []
    with force_mode(mode):
        for i in range(n_runs + warmup):
            t0 = time.perf_counter()
            _ = svc.run(req)
            dt = (time.perf_counter() - t0) * 1000.0
            if i >= warmup:
                vals.append(dt)

    arr = np.array(vals, dtype=np.float64)
    return {
        "mode": mode,
        "runs": n_runs,
        "window_sec": window_sec,
        "stride_sec": stride_sec,
        "latency_ms_p50": float(np.quantile(arr, 0.50)),
        "latency_ms_p95": float(np.quantile(arr, 0.95)),
        "latency_ms_p99": float(np.quantile(arr, 0.99)),
        "latency_ms_mean": float(np.mean(arr)),
        "latency_ms_min": float(np.min(arr)),
        "latency_ms_max": float(np.max(arr)),
    }


def write_repro_doc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# OBD Repro Commands",
        "",
        "Run from repo root (`AI-5-main-project`).",
        "",
        "```powershell",
        "$env:PYTHONPATH='C:\\Users\\seona\\Desktop\\dev\\AI-5-main-project'",
        "C:\\Users\\seona\\miniconda3\\condabin\\conda.bat run --no-capture-output -n ai5 python ai\\app\\services\\obd_anomaly\\offline\\scripts\\eval_model_modes_hardening.py --val-jsonl ai\\app\\services\\obd_anomaly\\offline\\datasets\\vfinal\\split\\val.jsonl --val-synthetic-jsonl ai\\app\\services\\obd_anomaly\\offline\\datasets\\vfinal\\split\\val_synthetic.jsonl --policy-json ai\\app\\services\\obd_anomaly\\models\\artifacts\\v1\\threshold_policy.json --window-sec 60 --stride-sec 30 --boot-iters 500 --seed 42 --latency-runs 100 --latency-warmup 10 --out-compare-csv docs\\OBD_MODEL_COMPARE.csv --out-compare-md docs\\OBD_MODEL_COMPARE.md --out-sensitivity-csv docs\\OBD_POLICY_SENSITIVITY.csv --out-latency-csv docs\\OBD_LATENCY_BENCHMARK.csv",
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_snapshot_copy(path: Path, snapshot_date: str) -> Path:
    snap = path.with_name(f"{path.stem}_{snapshot_date}{path.suffix}")
    snap.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return snap


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-jsonl", required=True)
    ap.add_argument("--val-synthetic-jsonl", required=True)
    ap.add_argument("--policy-json", required=True)
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--boot-iters", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--latency-runs", type=int, default=100)
    ap.add_argument("--latency-warmup", type=int, default=10)
    ap.add_argument("--out-compare-csv", required=True)
    ap.add_argument("--out-compare-md", required=True)
    ap.add_argument("--out-sensitivity-csv", required=True)
    ap.add_argument("--out-latency-csv", required=True)
    ap.add_argument("--out-repro-md", default="docs/OBD_REPRO_COMMANDS.md")
    ap.add_argument("--snapshot-date", default=date.today().isoformat())
    args = ap.parse_args()

    normal_rows = [r for r in load_jsonl(Path(args.val_jsonl)) if bool(r.get("is_normal", True))]
    synth_rows = load_jsonl(Path(args.val_synthetic_jsonl))
    policy = json.loads(Path(args.policy_json).read_text(encoding="utf-8-sig"))

    modes = ["HYBRID", "IF_ONLY", "AE_ONLY"]
    mode_evals: List[ModeEval] = []
    mode_normal: Dict[str, List[Dict[str, Any]]] = {}
    mode_synth: Dict[str, List[Dict[str, Any]]] = {}

    for i, m in enumerate(modes):
        ev, ntr, strc = eval_mode(
            mode=m,
            normal_rows=normal_rows,
            synth_rows=synth_rows,
            window_sec=int(args.window_sec),
            stride_sec=int(args.stride_sec),
            policy=policy,
            boot_iters=int(args.boot_iters),
            seed=int(args.seed) + i,
        )
        mode_evals.append(ev)
        mode_normal[m] = ntr
        mode_synth[m] = strc

    sens_rows: List[Dict[str, Any]] = []
    for m in modes:
        sens_rows.extend(build_sensitivity(m, policy, mode_normal[m], mode_synth[m]))

    lat_rows: List[Dict[str, Any]] = []
    ref_sample = synth_rows[0] if synth_rows else (normal_rows[0] if normal_rows else None)
    if ref_sample is not None:
        for m in modes:
            lat_rows.append(
                latency_benchmark(
                    mode=m,
                    sample=ref_sample,
                    window_sec=int(args.window_sec),
                    stride_sec=int(args.stride_sec),
                    n_runs=int(args.latency_runs),
                    warmup=int(args.latency_warmup),
                )
            )

    condition = (
        f"window_sec={args.window_sec}, stride_sec={args.stride_sec}, "
        f"threshold={policy.get('threshold')}, k={policy.get('k_consecutive')}, cooldown={policy.get('cooldown_sec')}"
    )

    write_compare_csv(Path(args.out_compare_csv), mode_evals)
    write_compare_md(Path(args.out_compare_md), mode_evals, condition)
    write_sensitivity_csv(Path(args.out_sensitivity_csv), sens_rows)
    write_latency_csv(Path(args.out_latency_csv), lat_rows)
    write_repro_doc(Path(args.out_repro_md))

    snap_compare_csv = write_snapshot_copy(Path(args.out_compare_csv), args.snapshot_date)
    snap_compare_md = write_snapshot_copy(Path(args.out_compare_md), args.snapshot_date)
    snap_sensitivity_csv = write_snapshot_copy(Path(args.out_sensitivity_csv), args.snapshot_date)
    snap_latency_csv = write_snapshot_copy(Path(args.out_latency_csv), args.snapshot_date)
    snap_repro_md = write_snapshot_copy(Path(args.out_repro_md), args.snapshot_date)

    print("[OK] hardening artifacts generated")
    print(f"compare_csv={args.out_compare_csv}")
    print(f"compare_md={args.out_compare_md}")
    print(f"sensitivity_csv={args.out_sensitivity_csv}")
    print(f"latency_csv={args.out_latency_csv}")
    print(f"repro_md={args.out_repro_md}")
    print(f"snapshot_compare_csv={snap_compare_csv}")
    print(f"snapshot_compare_md={snap_compare_md}")
    print(f"snapshot_sensitivity_csv={snap_sensitivity_csv}")
    print(f"snapshot_latency_csv={snap_latency_csv}")
    print(f"snapshot_repro_md={snap_repro_md}")


if __name__ == "__main__":
    main()
