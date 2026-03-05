import os
import torch
import pandas as pd
from ultralytics import YOLO
from pathlib import Path
import json

def train_and_analyze(base_path):
    base_dir = Path(base_path)
    if not base_dir.exists():
        print(f"[ERROR] Path does not exist: {base_path}")
        return

    # Results table
    results = []

    # Get component directories
    components = [d for d in base_dir.iterdir() if d.is_dir()]
    
    # Check GPU
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"\n>>> Using device: {device}")

    for comp_dir in components:
        comp_name = comp_dir.name
        print(f"\n" + "="*50)
        print(f">>> Processing Component: {comp_name}")
        print("="*50)

        train_path = comp_dir / "train"
        test_path = comp_dir / "test"

        if not train_path.exists() or not test_path.exists():
            print(f"  [SKIP] Required folders (train/test) missing in {comp_name}")
            continue

        # 1. Train YOLOv8-cls
        print(f"\n[1/2] Training YOLOv8-cls for {comp_name}...")
        model = YOLO('yolov8n-cls.pt')
        
        # Train
        train_results = model.train(
            data=str(comp_dir), # YOLO expects a folder with train/test/val subfolders
            epochs=30,          # Fast baseline
            imgsz=224,
            batch=16,
            device=device,
            project="runs/train_analyze",
            name=comp_name,
            exist_ok=True,
            verbose=False
        )

        # 2. Analyze using Test folder (Confidence Analysis)
        print(f"\n[2/2] Analyzing Test Dataset for {comp_name}...")
        
        test_metrics = {
            "component": comp_name,
            "normal_conf_avg": 0.0,
            "abnormal_conf_avg": 0.0,
            "accuracy": 0.0,
            "total_test_files": 0
        }

        correct_count = 0
        total_count = 0
        normal_confs = []
        abnormal_confs = []

        # Classes mapping (usually 0: abnormal, 1: normal or alphabetical)
        # YOLOv8-cls uses alphabetical order: abnormal(0), normal(1)
        
        for cls_name in ["normal", "abnormal"]:
            cls_path = test_path / cls_name
            if not cls_path.exists(): continue
            
            target_idx = 1 if cls_name == "normal" else 0
            
            files = list(cls_path.glob("*.jpg")) + list(cls_path.glob("*.png")) + list(cls_path.glob("*.jpeg"))
            for f in files:
                res = model.predict(str(f), verbose=False)[0]
                
                # Get index and confidence
                probs = res.probs
                pred_idx = probs.top1
                conf = float(probs.top1conf)
                
                if pred_idx == target_idx:
                    correct_count += 1
                
                if target_idx == 1: # Normal
                    # We want the confidence for the 'normal' class
                    # But top1conf gives the confidence of whatever was predicted.
                    # Let's get the specific probability for the target class.
                    prob_val = float(probs.data[1])
                    normal_confs.append(prob_val)
                else: # Abnormal
                    prob_val = float(probs.data[0])
                    abnormal_confs.append(prob_val)
                    
                total_count += 1

        if total_count > 0:
            test_metrics["accuracy"] = (correct_count / total_count) * 100
            test_metrics["normal_conf_avg"] = sum(normal_confs) / len(normal_confs) if normal_confs else 0
            test_metrics["abnormal_conf_avg"] = sum(abnormal_confs) / len(abnormal_confs) if abnormal_confs else 0
            test_metrics["total_test_files"] = total_count

        results.append(test_metrics)
        print(f"\n>>> Results for {comp_name}:")
        print(f"    - Accuracy: {test_metrics['accuracy']:.2f}%")
        print(f"    - Avg Normal Confidence: {test_metrics['normal_conf_avg']:.4f}")
        print(f"    - Avg Abnormal Confidence: {test_metrics['abnormal_conf_avg']:.4f}")

    # Final Report
    print("\n" + "="*50)
    print("FINAL PERFORMANCE REPORT")
    print("="*50)
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    # Save to JSON
    with open("training_analysis_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    
    print(f"\n[DONE] Report saved to training_analysis_report.json")

if __name__ == "__main__":
    DATA_PATH = r"C:\Users\301\Desktop\data\classification"
    train_and_analyze(DATA_PATH)
