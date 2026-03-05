from ultralytics import YOLO
from pathlib import Path
import pandas as pd
import torch

def evaluate_new_abs(thresholds=[0.3, 0.5]):
    model_path = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze\ABS_Unit_retrained\weights\best.pt")
    test_path = Path(r"C:\Users\301\Desktop\data\classification\ABS_Unit\test")
    
    if not model_path.exists():
        print(f"[ERROR] Model not found: {model_path}")
        return

    model = YOLO(str(model_path))
    all_results = []

    for threshold in thresholds:
        metrics = {
            "threshold": threshold,
            "TP": 0, "TN": 0, "FP": 0, "FN": 0
        }
        
        for cls_name in ["normal", "abnormal"]:
            cls_dir = test_path / cls_name
            if not cls_dir.exists(): continue
            
            is_abnormal = (cls_name == "abnormal")
            files = list(cls_dir.glob("*.jpg")) + list(cls_dir.glob("*.png")) + list(cls_dir.glob("*.jpeg"))
            
            for f in files:
                res = model.predict(str(f), verbose=False)[0]
                ab_prob = float(res.probs.data[0])
                
                pred_idx = 0 if ab_prob >= threshold else 1
                
                if is_abnormal:
                    if pred_idx == 0: metrics["TP"] += 1
                    else: metrics["FN"] += 1
                else:
                    if pred_idx == 1: metrics["TN"] += 1
                    else: metrics["FP"] += 1
        
        tp, tn, fp, fn = metrics["TP"], metrics["TN"], metrics["FP"], metrics["FN"]
        total = tp + tn + fp + fn
        
        res_row = {
            "threshold": threshold,
            "Accuracy": (tp + tn) / total if total > 0 else 0,
            "Recall": tp / (tp + fn) if (tp + fn) > 0 else 0,
            "Precision": tp / (tp + fp) if (tp + fp) > 0 else 0,
            "FPR": fp / (fp + tn) if (fp + tn) > 0 else 0,
            "FNR": fn / (fn + tp) if (fn + tp) > 0 else 0
        }
        all_results.append(res_row)

    df = pd.DataFrame(all_results)
    print("\n>>> RETRAINED ABS_UNIT PERFORMANCE COMPARISON")
    print("="*60)
    print(df.to_string(index=False))
    print("="*60)

if __name__ == "__main__":
    evaluate_new_abs()
