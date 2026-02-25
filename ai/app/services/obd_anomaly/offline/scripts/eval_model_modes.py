import argparse
import csv
import json
import math
import time
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


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            out.append(json.loads(s))
    return out


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
        vehicle_id="veh-compare",
        trip_id=str(sample.get("group_id", "trip-compare")),
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


def safe_div(a: float, b: float) -> float:
    return (a / b) if b != 0 else 0.0


def f1_from_counts(tp: int, fp: int, fn: int) -> float:
    p = safe_div(float(tp), float(tp + fp))
    r = safe_div(float(tp), float(tp + fn))
    return safe_div(2.0 * p * r, p + r)


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


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


def eval_mode(
    mode: str,
    normal_rows: List[Dict[str, Any]],
    synth_rows: List[Dict[str, Any]],
    window_sec: int,
    stride_sec: int,
    policy: Dict[str, Any],
) -> ModeEval:
    scorer = engine_lstm_ae._SCORER
    threshold = float(policy.get("threshold", 0.7))
    k_consecutive = int(policy.get("k_consecutive", 1))
    cooldown_sec = int(policy.get("cooldown_sec", 0))

    g = policy.get("gating", {})
    usable_min_cov = float(g.get("both_min_coverage", 0.6))

    all_scores: List[float] = []
    all_latency_ms: List[float] = []
    all_starts: List[int] = []
    total_windows = 0
    usable_windows = 0
    total_normal_duration_sec = 0.0
    gate_if_only = 0
    gate_ae_only = 0
    gate_both = 0

    with force_mode(mode):
        for row in normal_rows:
            req = to_request(row, window_sec=window_sec, stride_sec=stride_sec)
            total_normal_duration_sec += float(req.duration_sec)
            windows = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)
            for w in windows:
                total_windows += 1
                t0 = time.perf_counter()
                env = scorer.score_window(req, w)
                t1 = time.perf_counter()
                all_latency_ms.append((t1 - t0) * 1000.0)

                if env.score is not None and env.status.value == "PROCESSED":
                    s = float(env.score)
                    all_scores.append(s)
                    all_starts.append(int(w.start_t))

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

        policy_events = apply_engine_policy(all_scores, all_starts, policy)
        alarms_per_hour = safe_div(float(len(policy_events)), max(1e-6, total_normal_duration_sec / 3600.0))
        alert_rate_per_window = safe_div(float(sum(1 for s in all_scores if s >= threshold)), float(len(all_scores)))

        # Synthetic KPIs
        s_tp = s_fp = s_tn = s_fn = 0
        w_tp = w_fp = w_tn = w_fn = 0
        ttd_values: List[float] = []
        ttd_total_anomaly = 0
        pattern_total: Dict[str, int] = {}
        pattern_hit: Dict[str, int] = {}

        for row in synth_rows:
            req = to_request(row, window_sec=window_sec, stride_sec=stride_sec)
            windows = make_windows(req.data, req.sampling_hz, req.options.window_sec, req.options.stride_sec)

            scores: List[float] = []
            starts: List[int] = []
            win_ranges: List[Tuple[float, float]] = []

            for w in windows:
                t0 = time.perf_counter()
                env = scorer.score_window(req, w)
                t1 = time.perf_counter()
                all_latency_ms.append((t1 - t0) * 1000.0)

                if env.score is None or env.status.value != "PROCESSED":
                    continue
                scores.append(float(env.score))
                starts.append(int(w.start_t))
                win_ranges.append((float(w.start_t), float(w.end_t + 1)))

            events = apply_engine_policy(scores, starts, policy)
            y_true = not bool(row.get("is_normal", True))
            y_pred = bool(events)

            if y_true and y_pred:
                s_tp += 1
            elif y_true and not y_pred:
                s_fn += 1
            elif not y_true and y_pred:
                s_fp += 1
            else:
                s_tn += 1

            meta = row.get("synthetic_meta", {}) if isinstance(row.get("synthetic_meta", {}), dict) else {}
            has_interval = isinstance(meta.get("start_idx"), int) and isinstance(meta.get("end_idx"), int)
            if has_interval:
                hz = max(1, int(row.get("sampling_hz", 1)))
                st = float(meta["start_idx"]) / float(hz)
                ed = float(meta["end_idx"]) / float(hz)
                patt = str(meta.get("pattern", "UNKNOWN"))
                pattern_total[patt] = pattern_total.get(patt, 0) + 1
                ttd_total_anomaly += 1
                if y_pred:
                    pattern_hit[patt] = pattern_hit.get(patt, 0) + 1
                    first_evt_sec = float(events[0].get("start_t", 0.0)) if events else 0.0
                    ttd_values.append(max(0.0, first_evt_sec - st))

                for (ws, we), sc in zip(win_ranges, scores):
                    y_true_w = overlap(ws, we, st, ed)
                    y_pred_w = bool(sc >= threshold)
                    if y_true_w and y_pred_w:
                        w_tp += 1
                    elif y_true_w and not y_pred_w:
                        w_fn += 1
                    elif not y_true_w and y_pred_w:
                        w_fp += 1
                    else:
                        w_tn += 1
            else:
                for sc in scores:
                    y_true_w = False
                    y_pred_w = bool(sc >= threshold)
                    if y_pred_w:
                        w_fp += 1
                    else:
                        w_tn += 1

    if all_scores:
        arr = np.array(all_scores, dtype=np.float32)
        q50 = float(np.quantile(arr, 0.50))
        q90 = float(np.quantile(arr, 0.90))
        q95 = float(np.quantile(arr, 0.95))
        q99 = float(np.quantile(arr, 0.99))
        qmax = float(np.max(arr))
    else:
        q50 = q90 = q95 = q99 = qmax = 0.0

    if all_latency_ms:
        lat = np.array(all_latency_ms, dtype=np.float32)
        lat_mean = float(np.mean(lat))
        lat_p95 = float(np.quantile(lat, 0.95))
    else:
        lat_mean = lat_p95 = 0.0

    s_precision = safe_div(float(s_tp), float(s_tp + s_fp))
    s_recall = safe_div(float(s_tp), float(s_tp + s_fn))
    s_f1 = f1_from_counts(s_tp, s_fp, s_fn)
    w_f1 = f1_from_counts(w_tp, w_fp, w_fn)
    event_hit_rate = safe_div(float(sum(pattern_hit.values())), float(max(1, ttd_total_anomaly)))

    if ttd_values:
        tarr = np.array(ttd_values, dtype=np.float32)
        ttd_mean = float(np.mean(tarr))
        ttd_p95 = float(np.quantile(tarr, 0.95))
    else:
        ttd_mean = 0.0
        ttd_p95 = 0.0

    inj = ",".join(sorted(pattern_total.keys())) if pattern_total else "NONE"

    return ModeEval(
        mode=mode,
        threshold=threshold,
        k_consecutive=k_consecutive,
        cooldown_sec=cooldown_sec,
        alarms_per_hour=alarms_per_hour,
        alert_rate_per_window=alert_rate_per_window,
        q50=q50,
        q90=q90,
        q95=q95,
        q99=q99,
        qmax=qmax,
        usable_window_rate=safe_div(float(usable_windows), float(max(1, total_windows))),
        latency_ms_per_window_mean=lat_mean,
        latency_ms_per_window_p95=lat_p95,
        sample_precision=s_precision,
        sample_recall=s_recall,
        sample_f1=s_f1,
        window_f1=w_f1,
        event_hit_rate=event_hit_rate,
        ttd_mean_sec=ttd_mean,
        ttd_p95_sec=ttd_p95,
        ttd_detected=len(ttd_values),
        ttd_total_anomaly=ttd_total_anomaly,
        injection_types=inj,
        gate_if_only_rate=safe_div(float(gate_if_only), float(max(1, total_windows))),
        gate_ae_only_rate=safe_div(float(gate_ae_only), float(max(1, total_windows))),
        gate_both_rate=safe_div(float(gate_both), float(max(1, total_windows))),
    )


def write_csv(path: Path, rows: List[ModeEval]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "mode",
            "threshold",
            "k_consecutive",
            "cooldown_sec",
            "alarms_per_hour",
            "alert_rate_per_window",
            "q50",
            "q90",
            "q95",
            "q99",
            "qmax",
            "usable_window_rate",
            "latency_ms_per_window_mean",
            "latency_ms_per_window_p95",
            "sample_precision",
            "sample_recall",
            "sample_f1",
            "window_f1",
            "event_hit_rate",
            "ttd_mean_sec",
            "ttd_p95_sec",
            "ttd_detected",
            "ttd_total_anomaly",
            "injection_types",
            "gate_if_only_rate",
            "gate_ae_only_rate",
            "gate_both_rate",
        ])
        for r in rows:
            w.writerow([
                r.mode,
                r.threshold,
                r.k_consecutive,
                r.cooldown_sec,
                r.alarms_per_hour,
                r.alert_rate_per_window,
                r.q50,
                r.q90,
                r.q95,
                r.q99,
                r.qmax,
                r.usable_window_rate,
                r.latency_ms_per_window_mean,
                r.latency_ms_per_window_p95,
                r.sample_precision,
                r.sample_recall,
                r.sample_f1,
                r.window_f1,
                r.event_hit_rate,
                r.ttd_mean_sec,
                r.ttd_p95_sec,
                r.ttd_detected,
                r.ttd_total_anomaly,
                r.injection_types,
                r.gate_if_only_rate,
                r.gate_ae_only_rate,
                r.gate_both_rate,
            ])


def write_md(path: Path, rows: List[ModeEval], condition_note: str, compare_valid: bool, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# LSTM(AE) vs IF Same-Condition Comparison")
    lines.append("")
    lines.append(f"- condition: {condition_note}")
    lines.append(f"- compare_status: {'VALID' if compare_valid else 'NOT_COMPARABLE'}")
    if reason:
        lines.append(f"- reason: {reason}")
    lines.append("")
    lines.append("| mode | alarms_per_hour | alert_rate_per_window | q50 | q90 | q95 | q99 | qmax | usable_window_rate | latency_mean_ms/window | latency_p95_ms/window | sample_f1 | window_f1 | event_hit_rate | ttd_mean_sec | ttd_p95_sec | gate_if_only_rate | gate_ae_only_rate | gate_both_rate |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r.mode} | {r.alarms_per_hour:.6f} | {r.alert_rate_per_window:.6f} | {r.q50:.6f} | {r.q90:.6f} | {r.q95:.6f} | {r.q99:.6f} | {r.qmax:.6f} | {r.usable_window_rate:.6f} | {r.latency_ms_per_window_mean:.3f} | {r.latency_ms_per_window_p95:.3f} | {r.sample_f1:.6f} | {r.window_f1:.6f} | {r.event_hit_rate:.6f} | {r.ttd_mean_sec:.3f} | {r.ttd_p95_sec:.3f} | {r.gate_if_only_rate:.6f} | {r.gate_ae_only_rate:.6f} | {r.gate_both_rate:.6f} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("- synthetic injection types are taken from val_synthetic synthetic_meta.pattern")
    lines.append("- one-class normal setting: synthetic PR/F1 has generalization limits to real anomaly distribution")
    lines.append("- policy fixed for all modes from threshold_policy.json")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-jsonl", required=True)
    ap.add_argument("--val-synthetic-jsonl", required=True)
    ap.add_argument("--policy-json", required=True)
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    normal_rows = [r for r in load_jsonl(Path(args.val_jsonl)) if bool(r.get("is_normal", True))]
    synth_rows = load_jsonl(Path(args.val_synthetic_jsonl))
    policy = json.loads(Path(args.policy_json).read_text(encoding="utf-8-sig"))

    modes = ["HYBRID", "IF_ONLY", "AE_ONLY"]
    results = [
        eval_mode(
            mode=m,
            normal_rows=normal_rows,
            synth_rows=synth_rows,
            window_sec=int(args.window_sec),
            stride_sec=int(args.stride_sec),
            policy=policy,
        )
        for m in modes
    ]

    inj_sets = {r.injection_types for r in results}
    inj_ok = len(inj_sets) == 1 and list(inj_sets)[0] != "NONE" and len(list(inj_sets)[0].split(",")) >= 3
    ae_used = any(r.gate_ae_only_rate > 0.0 or r.gate_both_rate > 0.0 for r in results)
    compare_valid = bool(inj_ok and ae_used)
    if compare_valid:
        reason = ""
    elif not inj_ok:
        reason = "injection types < 3 or inconsistent condition"
    else:
        reason = "AE path not exercised (all windows fell to IF_ONLY)"

    cond = (
        f"window_sec={args.window_sec}, stride_sec={args.stride_sec}, "
        f"threshold={policy.get('threshold')}, k={policy.get('k_consecutive')}, cooldown={policy.get('cooldown_sec')}"
    )

    write_csv(Path(args.out_csv), results)
    write_md(Path(args.out_md), results, condition_note=cond, compare_valid=compare_valid, reason=reason)

    print("[OK] model-mode comparison finished")
    print(f"csv={args.out_csv}")
    print(f"md={args.out_md}")


if __name__ == "__main__":
    main()
