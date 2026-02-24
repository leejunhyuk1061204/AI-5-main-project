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
import platform
from ultralytics import YOLO
import shutil

# Removed global model initialization to prevent multiprocessing issues on Windows

# =============================================================================
# [Configuration] GPU Optimized Settings
# =============================================================================
# [Architecture] YOLO11m with P2 Head (Small Target Optimization)
# 4개의 Detection Head(P2, P3, P4, P5)를 사용하여 아주 작은 부품 감지력을 극대화한 구조입니다.
BASE_YAML = "ai/data/yolo/engine/yolo11m-p2.yaml"
BASE_MODEL = "yolo11m.pt"

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

DATA_YAML_PATH = os.path.join(DATA_ROOT, "yolo/engine/engine_merged.yaml")
OUTPUT_DIR = "ai/runs/engine_model"
SAVE_PATH = "ai/weights/engine/best_engine11m.pt"

# Training Hyperparameters (0.9 mAP Target + P2 Head)
DEFAULT_EPOCHS = 200
# [RunPod RTX 4070 (12GB) Optimized] 
# P2 Head + 1280px 환경에서도 12GB VRAM이면 Batch Size 16까지 충분히 가능합니다.
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))
IMG_SIZE = 1280
OPTIMIZER = "AdamW"
LR0 = 0.001
LRF = 0.01
PATIENCE = 50
# RunPod(Linux) 환경에서는 CPU 코어 활용을 위해 Workers를 8로 상향
WORKERS = 8 if platform.system() != "Windows" else 0 

# [Original RTX 4090 Reference]
# DEFAULT_EPOCHS = 150
# BATCH_SIZE = 32
# LR0 = 0.01
# LRF = 0.1
# PATIENCE = 20
# WORKERS = 8

# Augmentation (Small Dataset Optimized - 강화!)
MOSAIC = 1.0     # 최대 유지
MIXUP = 0.2      # 0.1 → 0.2 증가 (더 많은 다양성)
HSV_H = 0.02     # 0.015 → 0.02 (색조 변화 증가)
HSV_S = 0.9      # 0.7 → 0.9 (채도 변화 증가)
HSV_V = 0.6      # 0.4 → 0.6 (명도 변화 증가)
FLIPUD = 0.0     # 유지 (엔진룸은 상하 반전 X)
FLIPLR = 0.5     # 유지



# Regularization (과적합 방지)
WEIGHT_DECAY = 0.0005  # 추가!

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
    
    # Baseline은 순수 모델 성능 측정을 위해 기본 모델 사용 (imgsz만 1280 적용)
    model = YOLO(BASE_MODEL)
    
    print(f"[Info] Evaluating with base model ({BASE_MODEL})...")
    metrics = model.val(data=DATA_YAML_PATH, split='val', imgsz=IMG_SIZE, half=True)

    
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
def train_model(epochs=DEFAULT_EPOCHS, batch=BATCH_SIZE, imgsz=IMG_SIZE, workers=WORKERS, device=0):
    print("\n" + "="*60)
    print(f"[Step 2] Training Model (YOLOv8s, {epochs} epochs, batch={BATCH_SIZE})...")
    print("="*60)
    
    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] data.yaml not found at {DATA_YAML_PATH}")
        return None
    
    # [P2 Head 적용] YAML 아키텍처로 초기화 및 가중치 로드
    model = YOLO(BASE_YAML).load(BASE_MODEL)
    
    # [Weight Management] 기존 가중치가 있다면 백업 (누적 방지용)
    if os.path.exists(SAVE_PATH):
        old_path = SAVE_PATH.replace(".pt", "_old.pt")
        shutil.copy(SAVE_PATH, old_path)
        print(f"📦 기존 가중치를 백업했습니다: {old_path}")

    # Optimized Training Config
    results = model.train(
        data=DATA_YAML_PATH,
        epochs=epochs,
        imgsz=imgsz,
        batch=BATCH_SIZE,  # 상수 사용 (일관성 유지)
        device=device,  # GPU 0
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
        
        # Regularization (과적합 방지)
        weight_decay=WEIGHT_DECAY,
        
        # Optimization Protocol
        close_mosaic=20,  # 마지막 20 에폭에서 Mosaic 끄기 (정밀도 향상)
        
        # Performance
        workers=workers,  # 환경 자동 감지 (변수 사용)
        cache=False,  # RAM으로 데이터셋 캐싱 (속도 향상)
        
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
    metrics = model.val(data=DATA_YAML_PATH, split='val', imgsz=IMG_SIZE, half=True)

    
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
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=IMG_SIZE, help="Image size")
    parser.add_argument("--workers", type=int, default=WORKERS, help="Number of dataloader workers")
    parser.add_argument("--device", type=int, default=0, help="CUDA device index")
    
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
        train_model(epochs=args.epochs, batch=args.batch, imgsz=args.imgsz, workers=args.workers, device=args.device)
    
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

