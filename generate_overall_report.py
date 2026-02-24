from ultralytics import YOLO
import torch
from pathlib import Path
import pandas as pd
import os

def get_latest_model(comp_name):
    base_runs = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze")
    
    # Priority for specialized final models
    priority_names = [f"{comp_name}_v7_final", f"{comp_name}_retrained", comp_name]
    
    for name in priority_names:
        model_p = base_runs / name / "weights" / "best.pt"
        if model_p.exists():
            return str(model_p)
    return None

def evaluate_all():
    data_root = Path(r"C:\Users\301\Desktop\data\classification")
    components = [d.name for d in data_root.iterdir() if d.is_dir()]
    
    all_metrics = []
    threshold = 0.5 # Standard comparison threshold
    
    print(f"{'Component':<25} | {'Recall':<10} | {'FNR':<10} | {'Accuracy':<10}")
    print("-" * 65)
    
    for comp in components:
        model_path = get_latest_model(comp)
        test_dir = data_root / comp / "test"
        
        if not model_path or not test_dir.exists():
            all_metrics.append({"Component": comp, "Recall": "N/A", "FNR": "N/A", "Accuracy": "N/A"})
            print(f"{comp:<25} | {'N/A':<10} | {'N/A':<10} | {'N/A':<10}")
            continue
            
        model = YOLO(model_path)
        
        # Determine abnormal class index (usually 0)
        abnormal_idx = 0
        for idx, name in model.names.items():
            if 'abnormal' in name.lower():
                abnormal_idx = idx
                break
        
        tp, fn, tn, fp = 0, 0, 0, 0
        
        # Eval Abnormal
        ab_imgs = list((test_dir / "abnormal").glob("*.*"))
        for img in ab_imgs:
            res = model.predict(str(img), verbose=False)[0]
            if res.probs.data[abnormal_idx].item() >= threshold: tp += 1
            else: fn += 1
            
        # Eval Normal
        norm_imgs = list((test_dir / "normal").glob("*.*"))
        for img in norm_imgs:
            res = model.predict(str(img), verbose=False)[0]
            if res.probs.data[abnormal_idx].item() >= threshold: fp += 1
            else: tn += 1
            
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        
        print(f"{comp:<25} | {recall:>8.1%} | {fnr:>8.1%} | {acc:>8.1%}")
        all_metrics.append({
            "Component": comp,
            "Recall": f"{recall:.1%}",
            "FNR": f"{fnr:.1%}",
            "Accuracy": f"{acc:.1%}"
        })
        
    return pd.DataFrame(all_metrics)

if __name__ == "__main__":
    df = evaluate_all()
    # Save to CSV for future reference
    df.to_csv(r"C:\Users\301\Desktop\AI-5-main-project\final_overall_report.csv", index=False)
