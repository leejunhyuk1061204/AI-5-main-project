import argparse
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
        vehicle_id="veh-synth",
        trip_id=str(sample.get("group_id", "trip-synth")),
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-jsonl", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-report", required=True)
    ap.add_argument("--domain", default="engine")
    args = ap.parse_args()

    domain = args.domain.strip()
    svc = ObdAnomalyService()
    rows = _load_jsonl(Path(args.input_jsonl))

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
    tpr = recall
    accuracy = _safe_div(float(tp + tn), float(tp + tn + fp + fn))

    payload = {
        "domain": domain,
        "evaluated_samples": evaluated,
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        },
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "fpr": fpr,
            "tpr": tpr,
            "accuracy": accuracy,
        },
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Synthetic Evaluation Report",
        "",
        f"- domain: {domain}",
        f"- evaluated_samples: {evaluated}",
        "",
        "## Confusion Matrix",
        f"- TP: {tp}",
        f"- FP: {fp}",
        f"- TN: {tn}",
        f"- FN: {fn}",
        "",
        "## Metrics",
        f"- precision: {precision:.6f}",
        f"- recall: {recall:.6f}",
        f"- f1: {f1:.6f}",
        f"- fpr: {fpr:.6f}",
        f"- tpr: {tpr:.6f}",
        f"- accuracy: {accuracy:.6f}",
    ]
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[OK] synthetic metrics evaluated")
    print(f"json={args.out_json}")
    print(f"report={args.out_report}")


if __name__ == "__main__":
    main()

