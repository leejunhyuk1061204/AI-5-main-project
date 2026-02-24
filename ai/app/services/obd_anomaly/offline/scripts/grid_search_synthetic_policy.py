import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

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


def _to_request(sample: Dict[str, Any], domains: List[str]) -> ObdAnomalyRequest:
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
            if isinstance(v, (int, float)):
                feat[k] = float(v)
        rows.append(ObdSample(t=i, features=feat))

    return ObdAnomalyRequest(
        vehicle_id="veh-synth-grid",
        trip_id=str(sample.get("group_id", "trip-synth-grid")),
        mode="DRIVING",
        duration_sec=max(1, int(n / max(1, hz))),
        sampling_hz=hz,
        timestamp_unit="s",
        data=rows,
        options={
            "domains": domains,
            "return": "summary",
            "window_sec": int(sample.get("window_sec", 60)),
            "stride_sec": int(sample.get("stride_sec", 30)),
            "top_signals": "off",
        },
    )


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b != 0 else 0.0


def _evaluate(rows: List[Dict[str, Any]], domain: str) -> Dict[str, Any]:
    svc = ObdAnomalyService()

    tp = fp = tn = fn = 0
    evaluated = 0

    for row in rows:
        req = _to_request(row, domains=[domain])
        if not req.data:
            continue
        res = svc.run(req)
        y_true = not bool(row.get("is_normal", True))
        domain_res = res.domains.get(domain)
        y_pred = bool(domain_res.is_anomaly) if domain_res is not None else False

        if y_true and y_pred:
            tp += 1
        elif y_true and not y_pred:
            fn += 1
        elif not y_true and y_pred:
            fp += 1
        else:
            tn += 1
        evaluated += 1

    precision = _safe_div(float(tp), float(tp + fp))
    recall = _safe_div(float(tp), float(tp + fn))
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    fpr = _safe_div(float(fp), float(fp + tn))
    accuracy = _safe_div(float(tp + tn), float(tp + tn + fp + fn))

    return {
        "evaluated_samples": evaluated,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "fpr": fpr,
            "accuracy": accuracy,
        },
    }


def _frange(start: float, end: float, step: float) -> List[float]:
    vals: List[float] = []
    x = start
    while x <= end + 1e-12:
        vals.append(round(x, 6))
        x += step
    return vals


def _rank_key(item: Dict[str, Any]) -> Any:
    m = item["metrics"]
    # lower fpr first, then higher recall, then higher f1, then higher precision
    return (m["fpr"], -m["recall"], -m["f1"], -m["precision"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-jsonl", required=True)
    ap.add_argument("--policy-json", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--domain", default="engine")
    ap.add_argument("--th-min", type=float, default=0.84)
    ap.add_argument("--th-max", type=float, default=0.90)
    ap.add_argument("--th-step", type=float, default=0.01)
    ap.add_argument("--k-list", default="2,3")
    ap.add_argument("--warning-list", default="0.78,0.80,0.82,0.84")
    ap.add_argument("--critical-offset-list", default="0.08,0.10")
    ap.add_argument("--topk", type=int, default=10)
    args = ap.parse_args()

    rows = _load_jsonl(Path(args.input_jsonl))
    domain = args.domain.strip()

    policy_path = Path(args.policy_json)
    original_policy = json.loads(policy_path.read_text(encoding="utf-8"))

    thresholds = _frange(args.th_min, args.th_max, args.th_step)
    k_values = [int(x.strip()) for x in args.k_list.split(",") if x.strip()]
    warning_values = [float(x.strip()) for x in args.warning_list.split(",") if x.strip()]
    critical_offsets = [float(x.strip()) for x in args.critical_offset_list.split(",") if x.strip()]

    runs: List[Dict[str, Any]] = []

    try:
        for th in thresholds:
            for k in k_values:
                for warning in warning_values:
                    for off in critical_offsets:
                        critical = round(warning + off, 6)
                        if critical <= warning:
                            continue

                        pol = copy.deepcopy(original_policy)
                        pol["threshold"] = th
                        pol["k_consecutive"] = k
                        pol.setdefault("severity", {})["warning"] = warning
                        pol.setdefault("severity", {})["critical"] = critical
                        policy_path.write_text(
                            json.dumps(pol, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )

                        eval_res = _evaluate(rows, domain)
                        run = {
                            "params": {
                                "threshold": th,
                                "k_consecutive": k,
                                "warning": warning,
                                "critical": critical,
                            },
                            "evaluated_samples": eval_res["evaluated_samples"],
                            "confusion_matrix": eval_res["confusion_matrix"],
                            "metrics": eval_res["metrics"],
                        }
                        runs.append(run)
                        print(
                            "[RUN] "
                            f"th={th:.2f}, k={k}, w={warning:.2f}, c={critical:.2f} -> "
                            f"fpr={eval_res['metrics']['fpr']:.4f}, "
                            f"recall={eval_res['metrics']['recall']:.4f}, "
                            f"f1={eval_res['metrics']['f1']:.4f}"
                        )
    finally:
        policy_path.write_text(
            json.dumps(original_policy, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    ranked = sorted(runs, key=_rank_key)
    best = ranked[0] if ranked else None
    topk = ranked[: max(1, args.topk)]

    out_payload = {
        "domain": domain,
        "input_jsonl": args.input_jsonl,
        "grid": {
            "thresholds": thresholds,
            "k_values": k_values,
            "warning_values": warning_values,
            "critical_offsets": critical_offsets,
        },
        "num_runs": len(runs),
        "best": best,
        "topk": topk,
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Synthetic Grid Search Report",
        "",
        f"- domain: {domain}",
        f"- input_jsonl: {args.input_jsonl}",
        f"- num_runs: {len(runs)}",
        "",
    ]

    if best is not None:
        lines += [
            "## Best",
            f"- threshold: {best['params']['threshold']}",
            f"- k_consecutive: {best['params']['k_consecutive']}",
            f"- warning: {best['params']['warning']}",
            f"- critical: {best['params']['critical']}",
            f"- precision: {best['metrics']['precision']:.6f}",
            f"- recall: {best['metrics']['recall']:.6f}",
            f"- f1: {best['metrics']['f1']:.6f}",
            f"- fpr: {best['metrics']['fpr']:.6f}",
            f"- accuracy: {best['metrics']['accuracy']:.6f}",
            "",
        ]

    lines += ["## Top Candidates"]
    for idx, item in enumerate(topk, start=1):
        p = item["params"]
        m = item["metrics"]
        lines.append(
            f"- {idx}. th={p['threshold']}, k={p['k_consecutive']}, "
            f"w={p['warning']}, c={p['critical']} | "
            f"fpr={m['fpr']:.4f}, recall={m['recall']:.4f}, "
            f"f1={m['f1']:.4f}, precision={m['precision']:.4f}, accuracy={m['accuracy']:.4f}"
        )

    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[OK] synthetic policy grid search done")
    print(f"json={args.out_json}")
    print(f"report={args.out_report}")


if __name__ == "__main__":
    main()
