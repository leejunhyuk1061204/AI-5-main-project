import os
import torch
import pandas as pd
from ultralytics import YOLO
from pathlib import Path
import json

def calculate_detailed_metrics(base_path, model_base_path, thresholds=[0.2, 0.3, 0.5]):
    base_dir = Path(base_path)
    model_dir = Path(model_base_path)
    
    if not base_dir.exists():
        print(f"[ERROR] Path does not exist: {base_path}")
        return

    all_results = []
    components = [d for d in base_dir.iterdir() if d.is_dir()]
    
    device = 0 if torch.cuda.is_available() else "cpu"

    for threshold in thresholds:
        print(f"\n>>> Analyzing with Threshold: {threshold}")
        results = []
        for comp_dir in components:
            comp_name = comp_dir.name
            model_path = model_dir / comp_name / "weights" / "best.pt"
            
            if not model_path.exists():
                continue

            model = YOLO(str(model_path))
            test_path = comp_dir / "test"
            
            metrics = {
                "threshold": threshold,
                "component": comp_name,
                "TP": 0, "TN": 0, "FP": 0, "FN": 0,
                "accuracy": 0.0, "precision": 0.0, "recall": 0.0,
                "FPR": 0.0, "FNR": 0.0
            }

            for cls_name in ["normal", "abnormal"]:
                cls_path = test_path / cls_name
                if not cls_path.exists(): continue
                
                is_abnormal = (cls_name == "abnormal")
                files = list(cls_path.glob("*.jpg")) + list(cls_path.glob("*.png")) + list(cls_path.glob("*.jpeg"))
                
                for f in files:
                    res = model.predict(str(f), verbose=False)[0]
                    # Probability for 'abnormal' (index 0)
                    abnormal_prob = float(res.probs.data[0])
                    
                    # Custom threshold logic
                    if abnormal_prob >= threshold:
                        pred_idx = 0 # Predicted Abnormal
                    else:
                        pred_idx = 1 # Predicted Normal
                    
                    if is_abnormal:
                        if pred_idx == 0: metrics["TP"] += 1
                        else: metrics["FN"] += 1
                    else:
                        if pred_idx == 1: metrics["TN"] += 1
                        else: metrics["FP"] += 1

            tp, tn, fp, fn = metrics["TP"], metrics["TN"], metrics["FP"], metrics["FN"]
            total = tp + tn + fp + fn
            
            if total > 0:
                metrics["accuracy"] = (tp + tn) / total
                metrics["precision"] = tp / (tp + fp) if (tp + fp) > 0 else 0
                metrics["recall"] = tp / (tp + fn) if (tp + fn) > 0 else 0
                metrics["FPR"] = fp / (fp + tn) if (fp + tn) > 0 else 0
                metrics["FNR"] = fn / (fn + tp) if (fn + tp) > 0 else 0
            results.append(metrics)
        all_results.extend(results)

    # Format Output
    df = pd.DataFrame(all_results)
    for col in ["accuracy", "precision", "recall", "FPR", "FNR"]:
        df[col] = (df[col] * 100).round(2).astype(str) + "%"
    
    # Sort for better comparison
    df = df.sort_values(by=["component", "threshold"])
    
    print("\n" + "="*95)
    print(f"{'Component':<25} | {'Thres':<5} | {'Acc':<7} | {'Recall':<7} | {'FPR':<7} | {'FNR':<7}")
    print("-" * 95)
    for _, row in df.iterrows():
        print(f"{row['component']:<25} | {row['threshold']:<5} | {row['accuracy']:<7} | {row['recall']:<7} | {row['FPR']:<7} | {row['FNR']:<7}")
    print("="*95)

if __name__ == "__main__":
    DATA_PATH = r"C:\Users\301\Desktop\data\classification"
    MODEL_PATH = r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze"
    calculate_detailed_metrics(DATA_PATH, MODEL_PATH, thresholds=[0.2, 0.3, 0.5])

if __name__ == "__main__":
    DATA_PATH = r"C:\Users\301\Desktop\data\classification"
    # Unified results path discovered via find_by_name
    MODEL_PATH = r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze"
    calculate_detailed_metrics(DATA_PATH, MODEL_PATH)
