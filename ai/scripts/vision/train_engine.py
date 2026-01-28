# ai/scripts/train_engine.py
"""
엔진룸 부품 감지 YOLO 모델 학습 도구 (Engine YOLO Trainer)

[역할]
1. 부품 식별 학습: 엔진룸 내 26가지 주요 부품의 위치를 탐지하는 YOLOv8 모델을 학습합니다.
# 2. GPU 최적화: RTX 환경에서 최적의 성능을 낼 수 있는 배치 사이즈와 하이퍼파라미터를 제공합니다.
# (원본 설정은 RTX 4090 24GB 기준이나, 현재 RTX 3050 6GB에 맞춰 조정됨)
3. 성능 검증: mAP50 지표를 기준으로 모델의 정확도를 정밀 측정하며, 이전 모델과의 성능 비교 기능을 포함합니다.

[사용법]
- 전체 프로세스 실행: python ai/scripts/train_engine.py --mode all
- 데이터셋 변경 시: ai/data/engine_bay/data.yaml 수정 후 실행
"""
import argparse
import os
import shutil
from ultralytics import YOLO

# =============================================================================
# [Configuration] GPU Optimized Settings
# (RTX 4090 Optimized Settings - Commented for reference)
# =============================================================================
# Phase 1: YOLOv8s (빠른 프로토타입)
# Phase 2: Hard Negative Mining 후 YOLOv8m으로 업그레이드 가능
BASE_MODEL = "yolov8s.pt"  # s: 빠른 학습, 추후 m으로 업그레이드
DATA_YAML_PATH = "ai/data/yolo/engine/data.yaml"
OUTPUT_DIR = "ai/runs/engine_model"
SAVE_PATH = "ai/weights/engine/best.pt"

# Training Hyperparameters (RTX 3050 6GB Optimized)
DEFAULT_EPOCHS = 100
BATCH_SIZE = 16  # VRAM 6GB 고려 (Original 4090: 32)
IMG_SIZE = 640
OPTIMIZER = "AdamW"
LR0 = 0.001
LRF = 0.01
PATIENCE = 50
WORKERS = 0      # Windows 메모리 충돌 방지 (Original 4090: 8)

# [Original RTX 4090 Reference]
# DEFAULT_EPOCHS = 150
# BATCH_SIZE = 32
# LR0 = 0.01
# LRF = 0.1
# PATIENCE = 20
# WORKERS = 8

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
    
    # Optimized Training Config
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
        workers=WORKERS,
        cache=True,  # RAM으로 데이터셋 캐싱 (속도 향상)
        
        # Logging
        verbose=True,
    )
    
    # Save Best Model - model.train() 결과 객체에서 실제 저장 경로를 가져옴 (가장 고신뢰 방식)
    if hasattr(results, 'save_dir'):
        best_model_run_path = os.path.join(results.save_dir, "weights", "best.pt")
    else:
        # fallback
        best_model_run_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")

    if os.path.exists(best_model_run_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        shutil.copy(best_model_run_path, SAVE_PATH)
        print(f"\n[✓] Model saved to: {SAVE_PATH}")
        print(f"[✓] Ready for deployment!")
    else:
        print(f"[Warning] Best model weight file not found at: {best_model_run_path}")
    
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

