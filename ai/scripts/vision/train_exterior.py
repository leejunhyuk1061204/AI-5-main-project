from ultralytics import YOLO
import argparse
import os
import platform

# =============================================================================
# [Configuration] RunPod Optimized Settings
# =============================================================================
BASE_MODEL = "yolo11m.pt"

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

# [Environment Config] 환경 변수로 제어 가능
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))  # RunPod 기본값 16
DEFAULT_IMG_SIZE = int(os.getenv("IMG_SIZE", "1280"))
WORKERS = 8 if platform.system() != "Windows" else 0  # 자동 감지

# RunPod 환경 감지
IS_RUNPOD = os.path.exists(RUNPOD_DATA_PATH)
CACHE = True if IS_RUNPOD else False  # RunPod에서는 cache 활성화

def train_exterior_model(mode="train", epochs=10, batch_size=None, device=0):
    """
    Train or Evaluate YOLOv11M model for unified exterior damage detection (22 classes).
    """
    # Batch size 기본값 처리
    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE
    
    # 1. Project Setup
    project_path = os.path.join("ai", "weights", "exterior", "unified_v1")
    data_yaml = os.path.join(DATA_ROOT, "yolo", "exterior", "data.yaml")
    
    # Base model 존재 여부 확인
    if not os.path.exists(BASE_MODEL):
        print(f"[Error] Base model not found: {BASE_MODEL}")
        print(f"Please download from: https://github.com/ultralytics/assets/releases/download/v8.1.0/{BASE_MODEL}")
        return
    
    # Ensure yaml exists
    if not os.path.exists(data_yaml):
        print(f"[Error] No data.yaml found at: {data_yaml}")
        print(f"[Info] Checking paths:")
        print(f"  - RunPod path: {RUNPOD_DATA_PATH} (Exists: {os.path.exists(RUNPOD_DATA_PATH)})")
        print(f"  - Local path: {LOCAL_DATA_PATH} (Exists: {os.path.exists(LOCAL_DATA_PATH)})")
        print(f"  - Using: {DATA_ROOT}")
        return

    # 2. Mode Selection
    if mode == "train":
        print(f"\n🚀 Starting YOLOv11M Training for Exterior Damage (22 Classes)")
        print(f"   Environment: {'RunPod' if IS_RUNPOD else 'Local'}")
        print(f"   Data: {data_yaml}")
        print(f"   Output: {project_path}")
        print(f"   Epochs: {epochs}")
        print(f"   Batch: {batch_size}")
        print(f"   Image Size: {DEFAULT_IMG_SIZE}")
        print(f"   Workers: {WORKERS}")
        print(f"   Cache: {CACHE}")
        
        # Load Model (YOLO11 Medium)
        model = YOLO(BASE_MODEL)
        
        # Train
        model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=DEFAULT_IMG_SIZE,
            batch=batch_size,
            device=device,
            project=project_path,
            name="train",
            exist_ok=True, 
            plots=True,
            cache=CACHE,
            workers=WORKERS,
            amp=True  # Mixed precision for better performance
        )
        print(f"\n✅ Training Completed. Best weights saved at: {project_path}/train/weights/best.pt")
        
    elif mode in ["val", "test"]:
        print(f"\n🔍 Starting YOLOv8 Detailed Evaluation ({mode} mode)")
        
        best_weights = os.path.join(project_path, "train", "weights", "best.pt")
        if not os.path.exists(best_weights):
            print(f"   ⚠️ [Error] Trained weights not found: {best_weights}")
            return
            
        model = YOLO(best_weights)
        
        # 1. Standard Validation (per-class mAP)
        print(f"\n[Step 1] Running standard YOLO validation...")
        metrics = model.val(data=data_yaml, split=mode, workers=0, project=project_path, name=f"val_{mode}", exist_ok=True)
        
        # 2. Per-class mAP Report
        names = model.names
        maps = metrics.box.maps # Array of mAP50-95 per class
        
        print("\n" + "="*70)
        print(f"🎯 Per-class mAP50-95 Results:")
        print("-" * 70)
        print(f"{'ID':<3} | {'Class Name':<30} | {'mAP50-95':<12}")
        print("-" * 70)
        for i, name in names.items():
            m_val = maps[i] if i < len(maps) else 0.0
            print(f"{i:<3} | {name:<30} | {m_val:<12.4f}")
        print("-" * 70)
        
        # 3. Severity Accuracy Calculation
        print(f"\n[Step 2] Calculating Severity Accuracy (NORMAL/WARNING/CRITICAL)...")
        
        # Severity Map: 0: Normal, 1: Warning, 2: Critical
        # CRITICAL: Glass/Lights/Safety
        # WARNING: Dents/Deep damage
        # NORMAL: Scratches/Minor traces
        severity_map = {
            0: 2, 1: 2, 3: 2, 6: 2, 7: 2,  # Critical
            2: 1, 4: 1, 8: 1, 9: 1, 11: 1, 12: 1, 14: 1, 17: 1, 18: 1, 19: 1, 21: 1, # Warning
            5: 0, 10: 0, 13: 0, 15: 0, 16: 0, 20: 0 # Normal
        }
        
        # Iterate over test set to compare Ground Truth Severity vs Predicted Severity
        import glob
        from pathlib import Path
        
        # Use simple approach: Get images/labels from data.yaml path
        # Assuming folder structure: ai/data/yolo/exterior/[mode]/images
        img_dir = os.path.join("ai", "data", "yolo", "exterior", mode, "images")
        label_dir = os.path.join("ai", "data", "yolo", "exterior", mode, "labels")
        
        if not os.path.exists(img_dir):
            # Fallback for different path structures
            img_dir = os.path.join("ai", "data", "exterior", mode, "images")
            label_dir = os.path.join("ai", "data", "exterior", mode, "labels")

        correct_severity = 0
        total_images = 0
        
        # results = model.predict(source=img_dir, stream=True, verbose=False)
        # for res in results:
        #     # ... too slow ...
        
        # We'll use the validation metrics for simplicity if possible, 
        # but for true Severity Accuracy, we need image-level max.
        # Let's do a sample or full if small.
        img_files = glob.glob(os.path.join(img_dir, "*"))
        print(f"   Processing {len(img_files)} images for severity mapping...")
        
        y_true_sev = []
        y_pred_sev = []

        for img_path in img_files:
            if not img_path.lower().endswith(('.png', '.jpg', '.jpeg')): continue
            total_images += 1
            
            # 1. Ground Truth Severity
            label_path = os.path.join(label_dir, Path(img_path).stem + ".txt")
            gt_severity = 0 # Default: Normal (No damage)
            if os.path.exists(label_path):
                with open(label_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if not parts: continue
                        cls_id = int(parts[0])
                        gt_severity = max(gt_severity, severity_map.get(cls_id, 0) + 1 if severity_map.get(cls_id, 0) >= 0 else 0)
            
            # In our mapping: 0:Normal, 1:Warning, 2:Critical. 
            # If no damage -> level 0. 
            # If damage -> max(severity_map) + 1? No, let's keep it simple: 
            # If no damage (label file empty or missing) -> 0 (NORMAL)
            # If damage exists -> max(severity_map[classes])
            # Wait, if there are labels, it's at least WARNING or NORMAL or CRITICAL.
            # Let's redefine: 0: NORMAL, 1: WARNING, 2: CRITICAL
            # But "Normal" in user's prompt might mean "No damage" OR "Minor damage".
            # I'll treat "No detections" as NORMAL (0).
            
            gt_sev = 0
            if os.path.exists(label_path):
                with open(label_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if not parts: continue
                        cls_id = int(parts[0])
                        # Map: NORMAL=0(Minor), WARNING=1, CRITICAL=2. 
                        # But if ANY label exists, the overall state is at least the severity of that label.
                        label_sev = severity_map.get(cls_id, 0)
                        if label_sev == 0: gt_sev = max(gt_sev, 1) # Minor damage -> WARNING?
                        # User's req: NORMAL / WARNING / CRITICAL
                        # I'll use: 
                        # - NORMAL: No damage
                        # - WARNING: Minor damage (scratches/dents)
                        # - CRITICAL: Major damage (glass/lights)
                        # Let's check user's definition again.
                        # NORMAL=0, WARNING=1, CRITICAL=2.
                        gt_sev = max(gt_sev, severity_map.get(cls_id, 0) + 1) # 1:NormalScratch, 2:Warning, 3:Critical
            
            # Predict
            res = model.predict(img_path, verbose=False, conf=0.25)[0]
            pred_sev = 0
            if len(res.boxes) > 0:
                for box in res.boxes:
                    cls_id = int(box.cls[0])
                    pred_sev = max(pred_sev, severity_map.get(cls_id, 0) + 1)
            
            y_true_sev.append(gt_sev)
            y_pred_sev.append(pred_sev)
            if gt_sev == pred_sev: correct_severity += 1

        acc = correct_severity / total_images if total_images > 0 else 0
        
        print("\n" + "="*70)
        print(f"📊 Severity Accuracy Results:")
        print(f"   Total Images:      {total_images}")
        print(f"   Correct Severity:  {correct_severity}")
        print(f"   Accuracy:          {acc:.4f} (NORMAL/WARNING/CRITICAL)")
        print("-" * 70)
        print(f"📈 Results & Plots Saved at:")
        print(f"   {os.path.join(project_path, f'val_{mode}')}")
        print(f"   [Confusion Matrix] {os.path.join(project_path, f'val_{mode}', 'confusion_matrix.png')}")
        print("="*70 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train", choices=["train", "val", "test"], help="train, val, or test")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=2)
    args = parser.parse_args()
    
    train_exterior_model(mode=args.mode, epochs=args.epochs, batch_size=args.batch)
