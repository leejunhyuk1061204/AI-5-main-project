import argparse
import os
import re
from pathlib import Path
import json
import numpy as np
from PIL import Image
from ultralytics import YOLO

# =============================================================================
# Domain Configurations & Mappings
# =============================================================================

EXTERIOR_SEVERITY = {
    "pillar-dent": "CRITICAL", "front-windscreen-damage": "CRITICAL", "rear-windscreen-damage": "CRITICAL",
    "headlight-damage": "CRITICAL", "taillight-damage": "CRITICAL", "major-rear-bumper-dent": "CRITICAL",
    "bonnet-dent": "WARNING", "doorouter-dent": "WARNING", "fender-dent": "WARNING",
    "front-bumper-dent": "WARNING", "quaterpanel-dent": "WARNING", "rear-bumper-dent": "WARNING",
    "roof-dent": "WARNING", "runningboard-dent": "WARNING", "medium-bodypanel-dent": "WARNING",
    "doorouter-scratch": "WARNING", "front-bumper-scratch": "WARNING", "rear-bumper-scratch": "WARNING",
    "sidemirror-damage": "WARNING", "signlight-damage": "WARNING", "paint-chip": "WARNING",
    "paint-trace": "NORMAL"
}

DASHBOARD_INFO = {
    "Anti Lock Braking System": "WARNING", "Braking System Issue": "CRITICAL",
    "Charging System Issue": "CRITICAL", "Check Engine": "WARNING",
    "Electronic Stability Problem -ESP-": "WARNING", "Engine Overheating Warning Light": "CRITICAL",
    "Low Engine Oil Warning Light": "CRITICAL", "Low Tire Pressure Warning Light": "WARNING",
    "Master warning light": "WARNING", "SRS-Airbag": "CRITICAL"
}

def normalize_label(label):
    label = label.lower()
    label = re.sub(r'[^a-z0-9]+', '-', label)
    return label.strip('-')

class YOLOValidator:
    def __init__(self, domain, conf=0.25):
        self.domain = domain
        self.conf = conf

    def calculate_iou(self, box1, box2):
        x1, y1 = max(box1[0], box2[0]), max(box1[1], box2[1])
        x2, y2 = min(box1[2], box2[2]), min(box1[3], box2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2]-box1[0]) * (box1[3]-box1[1])
        area2 = (box2[2]-box2[0]) * (box2[3]-box2[1])
        return inter / float(area1 + area2 - inter) if (area1 + area2 - inter) > 0 else 0

    def get_gt(self, label_path, w, h):
        gt = []
        if not os.path.exists(label_path): return gt
        with open(label_path, 'r') as f:
            for l in f:
                p = l.strip().split()
                if len(p) < 5: continue
                cid, cx, cy, bw, bh = int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4])
                gt.append([cid, (cx-bw/2)*w, (cy-bh/2)*h, (cx+bw/2)*w, (cy+bh/2)*h])
        return gt

    def evaluate(self, model_path, img_dir, lbl_dir, tire_mode="auto"):
        print(f"\nEvaluating Model: {model_path}...")
        model = YOLO(model_path)
        names = model.names
        images = list(Path(img_dir).glob("*.jpg")) + list(Path(img_dir).glob("*.png"))
        
        metrics = {}
        if self.domain == "exterior":
            metrics = self._eval_exterior(model, names, images, lbl_dir)
        elif self.domain == "dashboard":
            metrics = self._eval_dashboard(model, names, images, lbl_dir)
        elif self.domain == "tire":
            metrics = self._eval_tire(model, names, images, lbl_dir, tire_mode)
        elif self.domain == "engine":
            metrics = self._eval_engine(model, names, images, lbl_dir)
        return metrics

    def _eval_exterior(self, model, names, images, lbl_dir):
        # Severity Accuracy & Critical Recall
        correct, processed = 0, 0
        crit_tp, crit_fn = 0, 0
        rank = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
        inv_rank = {0: "NORMAL", 1: "WARNING", 2: "CRITICAL"}
        CRIT_CONF = max(self.conf, 0.45)

        for img_p in images:
            img = Image.open(img_p); w, h = img.size
            gt = self.get_gt(Path(lbl_dir)/(img_p.stem+".txt"), w, h)
            gt_status = inv_rank[max([rank[EXTERIOR_SEVERITY.get(normalize_label(names[g[0]]), "WARNING")] for g in gt] + [0])]
            
            res = model.predict(img_p, conf=self.conf, verbose=False)
            pred_rank = 0
            for r in res:
                for b in r.boxes:
                    s = EXTERIOR_SEVERITY.get(normalize_label(names[int(b.cls[0])]), "WARNING")
                    if s == "CRITICAL" and b.conf[0] < CRIT_CONF: s = "WARNING"
                    pred_rank = max(pred_rank, rank[s])
            pred_status = inv_rank[pred_rank]
            
            if gt_status == "CRITICAL":
                if pred_status == "CRITICAL": crit_tp += 1
                else: crit_fn += 1
            if gt_status == pred_status: correct += 1
            processed += 1
            
        return {"Severity Acc": correct/processed if processed>0 else 0, 
                "Critical Recall": crit_tp/(crit_tp+crit_fn) if (crit_tp+crit_fn)>0 else 0}

    def _eval_dashboard(self, model, names, images, lbl_dir):
        # Overall & Critical Recall
        tp, total, c_tp, c_total = 0, 0, 0, 0
        crit_ids = [i for i, n in names.items() if DASHBOARD_INFO.get(n) == "CRITICAL"]

        for img_p in images:
            img = Image.open(img_p); w, h = img.size
            gt = self.get_gt(Path(lbl_dir)/(img_p.stem+".txt"), w, h)
            total += len(gt)
            c_gt = [g for g in gt if g[0] in crit_ids]
            c_total += len(c_gt)
            
            res = model.predict(img_p, conf=self.conf, verbose=False)
            preds = [[int(b.cls[0])] + b.xyxy[0].tolist() for r in res for b in r.boxes]
            matched = [False] * len(gt)
            for p in preds:
                for i, g in enumerate(gt):
                    if not matched[i] and p[0] == g[0] and self.calculate_iou(p[1:], g[1:]) >= 0.5:
                        tp += 1; matched[i] = True
                        if g[0] in crit_ids: c_tp += 1
                        break
        return {"Overall Recall": tp/total if total>0 else 0, "Critical Recall": c_tp/c_total if c_total>0 else 0}

    def _eval_tire(self, model, names, images, lbl_dir, mode):
        tp, fn, fp, tn = 0, 0, 0, 0
        for img_p in images:
            lbl = Path(lbl_dir)/(img_p.stem+".txt")
            gt_is_danger = False
            if os.path.exists(lbl):
                with open(lbl, 'r') as f:
                    for l in f:
                        if int(l.split()[0]) == 1: gt_is_danger = True; break
            res = model.predict(img_p, conf=self.conf, verbose=False)
            is_danger = False
            for r in res:
                if len(r.boxes)>0:
                    for b in r.boxes: 
                        if int(b.cls[0]) == 1: is_danger = True
                elif hasattr(r, 'probs') and r.probs is not None:
                    if int(r.probs.top1) == 1 and r.probs.top1conf >= self.conf: is_danger = True
            if gt_is_danger and is_danger: tp += 1
            elif gt_is_danger and not is_danger: fn += 1
            elif not gt_is_danger and is_danger: fp += 1
            else: tn += 1
        return {"Danger Recall": tp/(tp+fn) if (tp+fn)>0 else 0, "F1": (2*tp/(2*tp+fp+fn)) if (2*tp+fp+fn)>0 else 0}

    def _eval_engine(self, model, names, images, lbl_dir):
        tp75, total = 0, 0
        for img_p in images:
            img = Image.open(img_p); w, h = img.size
            gt = self.get_gt(Path(lbl_dir)/(img_p.stem+".txt"), w, h)
            total += len(gt)
            res = model.predict(img_p, conf=self.conf, verbose=False)
            preds = [[int(b.cls[0])] + b.xyxy[0].tolist() for r in res for b in r.boxes]
            for g in gt:
                best = max([self.calculate_iou(p[1:], g[1:]) for p in preds if p[0] == g[0]] + [0])
                if best >= 0.75: tp75 += 1
        return {"Recall @ 0.75": tp75/total if total>0 else 0}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--domain", required=True, choices=["exterior", "dashboard", "tire", "engine"])
    p.add_argument("--baseline", help="Path to baseline model (.pt)")
    p.add_argument("--finetuned", help="Path to fine-tuned model (.pt)")
    p.add_argument("--img_dir", required=True)
    p.add_argument("--lbl_dir", required=True)
    p.add_argument("--conf", type=float, default=0.25)
    args = p.parse_args()

    v = YOLOValidator(args.domain, args.conf)
    results = {}
    if args.baseline: results["Baseline"] = v.evaluate(args.baseline, args.img_dir, args.lbl_dir)
    if args.finetuned: results["Fine-tuned"] = v.evaluate(args.finetuned, args.img_dir, args.lbl_dir)

    if args.baseline and args.finetuned:
        print(f"\n### {args.domain.upper()} Comparison Report")
        metrics = results["Baseline"].keys()
        print(f"| Metric | Baseline | Fine-tuned | Δ |")
        print(f"| --- | --- | --- | --- |")
        for m in metrics:
            b, f = results["Baseline"][m], results["Fine-tuned"][m]
            print(f"| {m} | {b:.4f} | {f:.4f} | {f-b:+.4f} |")
