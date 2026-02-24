from ultralytics import YOLO
import torch
from pathlib import Path
import pandas as pd

def evaluate_model(comp_name, model_path, test_data_path):
    print(f"\n>>> Evaluating {comp_name}...")
    model = YOLO(model_path)
    
    # Mapping
    # YOLO classification usually orders classes alphabetically: abnormal, normal
    # So 0: abnormal, 1: normal
    class_map = model.names # {0: 'abnormal', 1: 'normal'}
    print(f"Class Mapping: {class_map}")
    
    abnormal_idx = 0
    for idx, name in class_map.items():
        if 'abnormal' in name.lower():
            abnormal_idx = idx
            break
            
    # Test Data
    test_dir = Path(test_data_path)
    results = []
    
    # Thresholds to test
    thresholds = [0.3, 0.5]
    
    metrics_summary = []
    
    for thresh in thresholds:
        tp, fp, tn, fn = 0, 0, 0, 0
        
        # Test Abnormal
        abnormal_test = list((test_dir / "abnormal").glob("*.*"))
        for img_p in abnormal_test:
            res = model.predict(str(img_p), verbose=False)[0]
            # Prob for abnormal class
            prob_abnormal = res.probs.data[abnormal_idx].item()
            
            if prob_abnormal >= thresh:
                tp += 1
            else:
                fn += 1
                
        # Test Normal
        normal_test = list((test_dir / "normal").glob("*.*"))
        for img_p in normal_test:
            res = model.predict(str(img_p), verbose=False)[0]
            prob_abnormal = res.probs.data[abnormal_idx].item()
            
            if prob_abnormal >= thresh:
                fp += 1
            else:
                tn += 1
                
        # Calculate Metrics
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0 
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        metrics_summary.append({
            "Threshold": thresh,
            "Accuracy": f"{accuracy:.2%}",
            "Recall (TPR)": f"{recall:.2%}",
            "Precision": f"{precision:.2%}",
            "FPR": f"{fpr:.2%}",
            "FNR": f"{fnr:.2%}",
            "TP/FN/TN/FP": f"{tp}/{fn}/{tn}/{fp}"
        })
        
    df = pd.DataFrame(metrics_summary)
    print(f"\nFinal Metrics for {comp_name}:")
    print(df.to_string(index=False))
    return df

if __name__ == "__main__":
    configs = [
        {
            "name": "ABS_Unit",
            "model": r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze\ABS_Unit_v7_final\weights\best.pt",
            "test": r"C:\Users\301\Desktop\data\classification\ABS_Unit\test"
        },
        {
            "name": "Engine_Cover",
            "model": r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze\Engine_Cover_v7_final\weights\best.pt",
            "test": r"C:\Users\301\Desktop\data\classification\Engine_Cover\test"
        }
    ]
    
    for cfg in configs:
        evaluate_model(cfg["name"], cfg["model"], cfg["test"])
