"""
Engine Bay Training Script (YOLOv8s Optimized for RTX 4090)

[최적화 세팅]
- 모델: YOLOv8s (빠른 프로토타입, 추후 Hard Negative Mining 후 YOLOv8m으로 업그레이드)
- Batch: 32 (RTX 4090 24GB 최적)
- Epochs: 150 (s 모델 기준)
- Optimizer: AdamW (안정적)
- Augmentation: Mosaic, Mixup, HSV, Flip

[사용법 / Usage]
1. 초기 성능 확인:
   python ai/scripts/train_engine.py --mode baseline

2. 학습 (기본 150 epochs):
   python ai/scripts/train_engine.py --mode train
   
   # 커스텀 epochs:
   python ai/scripts/train_engine.py --mode train --epochs 200

3. 최종 평가:
   python ai/scripts/train_engine.py --mode test

4. 전체 실행:
   python ai/scripts/train_engine.py --mode all

[재학습 가이드 - Hard Negative Mining]
1. 실서비스에서 Path B로 빠진 ENGINE 이미지가 s3://hard_negatives/에 수집됨
2. 해당 이미지를 ai/data/engine_bay/train/images에 추가 (라벨링 필요)
3. 위 학습 명령어 재실행 → 정확도 향상

[YOLOv8m 업그레이드]
Hard Negative 수집 완료 후:
  BASE_MODEL = "yolov8m.pt"  # s → m 변경
  EPOCHS = 100  # m은 적은 epoch로도 안정
"""
import argparse
import os
import shutil
from ultralytics import YOLO

# =============================================================================
# [Configuration] RTX 4090 Optimized Settings
# =============================================================================
# Phase 1: YOLOv8s (빠른 프로토타입)
# Phase 2: Hard Negative Mining 후 YOLOv8m으로 업그레이드 가능
BASE_MODEL = "yolov8s.pt"  # s: 빠른 학습, 추후 m으로 업그레이드
DATA_YAML_PATH = "ai/data/engine_bay/data.yaml"
OUTPUT_DIR = "ai/runs/engine_model"
SAVE_PATH = "ai/weights/engine/best.pt"

# Training Hyperparameters (RTX 4090 24GB 최적화)
DEFAULT_EPOCHS = 150
BATCH_SIZE = 32
IMG_SIZE = 640
OPTIMIZER = "AdamW"
LR0 = 0.001  # Initial Learning Rate
LRF = 0.01   # Final LR = LR0 * LRF (Cosine)
PATIENCE = 20  # Early Stopping (epochs without improvement)

# Augmentation
MOSAIC = 1.0
MIXUP = 0.1
HSV_H = 0.015
HSV_S = 0.7
HSV_V = 0.4
FLIPUD = 0.0
FLIPLR = 0.5

# =============================================================================
# 1. Baseline Evaluation
# =============================================================================
def evaluate_baseline():
    print("\n" + "="*60)
    print("[Step 1] Initial Model (Baseline) Evaluation...")
    print("="*60)
    
    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] data.yaml not found at {DATA_YAML_PATH}")
        return None
    
    model = YOLO(BASE_MODEL)
    
    print(f"[Info] Evaluating with base model ({BASE_MODEL})...")
    metrics = model.val(data=DATA_YAML_PATH, split='val', imgsz=IMG_SIZE)
    
    map50 = metrics.box.map50
    map50_95 = metrics.box.map
    
    print("\n" + "="*50)
    print(f"🎯 Baseline Precision:")
    print(f"   mAP50:    {map50:.4f}")
    print(f"   mAP50-95: {map50_95:.4f}")
    print("="*50 + "\n")
    
    return {"map50": map50, "map50_95": map50_95}

# =============================================================================
# 2. Model Training (Optimized)
# =============================================================================
def train_model(epochs=DEFAULT_EPOCHS):
    print("\n" + "="*60)
    print(f"[Step 2] Training Model (YOLOv8s, {epochs} epochs, batch={BATCH_SIZE})...")
    print("="*60)
    
    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] data.yaml not found at {DATA_YAML_PATH}")
        return None
    
    model = YOLO(BASE_MODEL)
    
    # Optimized Training Config for RTX 4090
    results = model.train(
        data=DATA_YAML_PATH,
        epochs=epochs,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device=0,  # GPU 0
        project=OUTPUT_DIR,
        name="run",
        exist_ok=True,
        
        # Optimizer
        optimizer=OPTIMIZER,
        lr0=LR0,
        lrf=LRF,
        
        # Early Stopping
        patience=PATIENCE,
        
        # Augmentation
        mosaic=MOSAIC,
        mixup=MIXUP,
        hsv_h=HSV_H,
        hsv_s=HSV_S,
        hsv_v=HSV_V,
        flipud=FLIPUD,
        fliplr=FLIPLR,
        
        # Performance
        workers=8,
        cache=True,  # RAM으로 데이터셋 캐싱 (속도 향상)
        
        # Logging
        verbose=True,
    )
    
    # Save Best Model
    best_model_run_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")
    if os.path.exists(best_model_run_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        shutil.copy(best_model_run_path, SAVE_PATH)
        print(f"\n[✓] Model saved to: {SAVE_PATH}")
        print(f"[✓] Ready for deployment!")
    else:
        print("[Warning] Best model weight file not found in run directory.")
    
    return results

# =============================================================================
# 3. Final Evaluation
# =============================================================================
def evaluate_final():
    print("\n" + "="*60)
    print("[Step 3] Final Model Evaluation...")
    print("="*60)
    
    if not os.path.exists(SAVE_PATH):
        print(f"[Error] Trained model not found: {SAVE_PATH}")
        print(" -> Run with --mode train first.")
        return None
    
    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] data.yaml not found.")
        return None
    
    model = YOLO(SAVE_PATH)
    
    print(f"[Info] Evaluating with trained model ({SAVE_PATH})...")
    metrics = model.val(data=DATA_YAML_PATH, split='val', imgsz=IMG_SIZE)
    
    map50 = metrics.box.map50
    map50_95 = metrics.box.map
    
    print("\n" + "="*50)
    print(f"🎯 Final Precision:")
    print(f"   mAP50:    {map50:.4f}")
    print(f"   mAP50-95: {map50_95:.4f}")
    print("="*50 + "\n")
    
    return {"map50": map50, "map50_95": map50_95}

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLOv8s Engine Bay Training Script (RTX 4090 Optimized)")
    parser.add_argument("--mode", type=str, default="all",
                        choices=["baseline", "train", "test", "all"],
                        help="Execution Mode")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS,
                        help=f"Number of epochs (default: {DEFAULT_EPOCHS})")
    
    args = parser.parse_args()
    
    print(f"\n🚀 Engine Training Script Started")
    print(f"   Mode: {args.mode}")
    print(f"   Epochs: {args.epochs}")
    print(f"   Model: {BASE_MODEL}")
    print(f"   Batch: {BATCH_SIZE}")
    print(f"   Optimizer: {OPTIMIZER}")
    
    if args.mode == "baseline":
        evaluate_baseline()
    
    elif args.mode == "train":
        train_model(epochs=args.epochs)
    
    elif args.mode == "test":
        evaluate_final()
    
    elif args.mode == "all":
        baseline = evaluate_baseline()
        train_model(epochs=args.epochs)
        final = evaluate_final()
        
        if baseline and final:
            print("\n" + "="*60)
            print("📊 Precision Comparison (mAP50)")
            print("="*60)
            print(f"   Baseline: {baseline['map50']:.4f}")
            print(f"   Final:    {final['map50']:.4f}")
            diff = (final['map50'] - baseline['map50']) * 100
            print(f"   Improvement: {diff:+.2f}%")
            print("="*60 + "\n")
    
    print("✅ Done!")

