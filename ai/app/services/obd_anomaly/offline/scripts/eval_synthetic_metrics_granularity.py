import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdSample
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(float(v))


def _series_len(sample: Dict[str, Any]) -> int:
    data = sample.get("data", {})
    if not isinstance(data, dict):
        return 0
    lens = [len(v) for v in data.values() if isinstance(v, list)]
    return min(lens) if lens else 0


def _slice_sample(sample: Dict[str, Any], start: int, end: int) -> Dict[str, Any]:
    out = {
        "group_id": sample.get("group_id", "trip-synth"),
        "sampling_hz": int(sample.get("sampling_hz", 1)),
        "window_sec": int(sample.get("window_sec", 60)),
        "stride_sec": int(sample.get("stride_sec", 30)),
        "is_normal": bool(sample.get("is_normal", True)),
        "data": {},
    }
    data = sample.get("data", {})
    if isinstance(data, dict):
        for k, arr in data.items():
            if isinstance(arr, list):
                out["data"][k] = arr[start:end]
    return out


def _to_request(
    sample: Dict[str, Any],
    domains: List[str],
    window_sec: Optional[int] = None,
    stride_sec: Optional[int] = None,
) -> ObdAnomalyRequest:
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
            if _is_number(v):
                feat[k] = float(v)
        rows.append(ObdSample(t=i, features=feat))

    win = int(window_sec if window_sec is not None else sample.get("window_sec", 60))
    stride = int(stride_sec if stride_sec is not None else sample.get("stride_sec", 30))
    if win <= 0:
        win = 60
    if stride <= 0:
        stride = win

    return ObdAnomalyRequest(
        vehicle_id="veh-synth-gran",
        trip_id=str(sample.get("group_id", "trip-synth-gran")),
        mode="DRIVING",
        duration_sec=max(1, int(n / max(1, hz))),
        sampling_hz=hz,
        timestamp_unit="s",
        data=rows,
        options={
            "domains": domains,
            "return": "summary",
            "window_sec": win,
            "stride_sec": stride,
            "top_signals": "off",
        },
    )


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b != 0 else 0.0


def _metrics_from_counts(tp: int, fp: int, tn: int, fn: int) -> Dict[str, float]:
    precision = _safe_div(float(tp), float(tp + fp))
    recall = _safe_div(float(tp), float(tp + fn))
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    fpr = _safe_div(float(fp), float(fp + tn))
    tpr = recall
    accuracy = _safe_div(float(tp + tn), float(tp + tn + fp + fn))
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "tpr": tpr,
        "accuracy": accuracy,
    }


def _synthetic_interval(sample: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    meta = sample.get("synthetic_meta")
    if not isinstance(meta, dict):
        return None
    s = meta.get("start_idx")
    e = meta.get("end_idx")
    if isinstance(s, int) and isinstance(e, int) and e > s:
        return (s, e)
    return None


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def _evaluate_sample(rows: List[Dict[str, Any]], domain: str) -> Dict[str, Any]:
    svc = ObdAnomalyService()
    tp = fp = tn = fn = 0
    evaluated = 0
    for row in rows:
        req = _to_request(row, domains=[domain])
        if not req.data:
            continue
        res = svc.run(req)
        y_true = not bool(row.get("is_normal", True))
        dres = res.domains.get(domain)
        y_pred = bool(dres.is_anomaly) if dres is not None else False
        if y_true and y_pred:
            tp += 1
        elif y_true and not y_pred:
            fn += 1
        elif not y_true and y_pred:
            fp += 1
        else:
            tn += 1
        evaluated += 1
    return {
        "evaluated_units": evaluated,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "metrics": _metrics_from_counts(tp, fp, tn, fn),
    }


def _evaluate_window(rows: List[Dict[str, Any]], domain: str, window_sec: int) -> Dict[str, Any]:
    svc = ObdAnomalyService()
    tp = fp = tn = fn = 0
    evaluated = 0
    for row in rows:
        hz = int(row.get("sampling_hz", 1))
        n = _series_len(row)
        if hz <= 0 or n <= 0:
            continue
        win_n = window_sec * hz
        if win_n <= 0 or n < win_n:
            continue

        syn_iv = _synthetic_interval(row)
        for start in range(0, n - win_n + 1, win_n):
            end = start + win_n
            sub = _slice_sample(row, start, end)
            req = _to_request(sub, domains=[domain], window_sec=window_sec, stride_sec=window_sec)
            if not req.data:
                continue
            res = svc.run(req)
            y_true = False
            if syn_iv is not None:
                y_true = _overlap(start, end, syn_iv[0], syn_iv[1])
            dres = res.domains.get(domain)
            y_pred = bool(dres.is_anomaly) if dres is not None else False
            if y_true and y_pred:
                tp += 1
            elif y_true and not y_pred:
                fn += 1
            elif not y_true and y_pred:
                fp += 1
            else:
                tn += 1
            evaluated += 1
    return {
        "evaluated_units": evaluated,
        "unit_sec": window_sec,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "metrics": _metrics_from_counts(tp, fp, tn, fn),
    }


def _evaluate_chunk(rows: List[Dict[str, Any]], domain: str, chunk_sec: int) -> Dict[str, Any]:
    svc = ObdAnomalyService()
    tp = fp = tn = fn = 0
    evaluated = 0
    for row in rows:
        hz = int(row.get("sampling_hz", 1))
        n = _series_len(row)
        if hz <= 0 or n <= 0:
            continue
        chunk_n = chunk_sec * hz
        if chunk_n <= 0 or n < chunk_n:
            continue

        syn_iv = _synthetic_interval(row)
        for start in range(0, n - chunk_n + 1, chunk_n):
            end = start + chunk_n
            sub = _slice_sample(row, start, end)
            req = _to_request(sub, domains=[domain], window_sec=60, stride_sec=30)
            if not req.data:
                continue
            res = svc.run(req)
            y_true = False
            if syn_iv is not None:
                y_true = _overlap(start, end, syn_iv[0], syn_iv[1])
            dres = res.domains.get(domain)
            y_pred = bool(dres.is_anomaly) if dres is not None else False
            if y_true and y_pred:
                tp += 1
            elif y_true and not y_pred:
                fn += 1
            elif not y_true and y_pred:
                fp += 1
            else:
                tn += 1
            evaluated += 1
    return {
        "evaluated_units": evaluated,
        "unit_sec": chunk_sec,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "metrics": _metrics_from_counts(tp, fp, tn, fn),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-jsonl", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--domain", default="engine")
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--chunk-sec", type=int, default=900)
    args = ap.parse_args()

    domain = args.domain.strip()
    rows = _load_jsonl(Path(args.input_jsonl))

    sample_res = _evaluate_sample(rows, domain)
    window_res = _evaluate_window(rows, domain, args.window_sec)
    chunk_res = _evaluate_chunk(rows, domain, args.chunk_sec)

    payload = {
        "domain": domain,
        "input_jsonl": args.input_jsonl,
        "granularity_results": {
            "sample": sample_res,
            f"window_{args.window_sec}s": window_res,
            f"chunk_{args.chunk_sec}s": chunk_res,
        },
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _line_block(title: str, res: Dict[str, Any]) -> List[str]:
        m = res["metrics"]
        cm = res["confusion_matrix"]
        return [
            f"## {title}",
            f"- evaluated_units: {res['evaluated_units']}",
            f"- TP: {cm['tp']}",
            f"- FP: {cm['fp']}",
            f"- TN: {cm['tn']}",
            f"- FN: {cm['fn']}",
            f"- precision: {m['precision']:.6f}",
            f"- recall: {m['recall']:.6f}",
            f"- f1: {m['f1']:.6f}",
            f"- fpr: {m['fpr']:.6f}",
            f"- accuracy: {m['accuracy']:.6f}",
            "",
        ]

    lines: List[str] = [
        "# Synthetic Evaluation Report (Multi-Granularity)",
        "",
        f"- domain: {domain}",
        f"- input_jsonl: {args.input_jsonl}",
        "",
    ]
    lines += _line_block("Sample-Level", sample_res)
    lines += _line_block(f"Window-Level ({args.window_sec}s)", window_res)
    lines += _line_block(f"Chunk-Level ({args.chunk_sec}s)", chunk_res)

    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines), encoding="utf-8")

    print("[OK] synthetic multi-granularity metrics evaluated")
    print(f"json={args.out_json}")
    print(f"report={args.out_report}")


if __name__ == "__main__":
    main()
