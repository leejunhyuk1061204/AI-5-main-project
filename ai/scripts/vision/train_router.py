# ai/scripts/vision/train_router.py
"""
AI 분석 장면 분류 모델 학습 도구 (Router Classification Trainer - YOLO)

[역할]
1. 장면 분류 학습: 이미지가 차량의 어느 부위(엔진, 계기판, 외관, 타이어)인지 판단하는 YOLOv11M-cls 모델을 학습합니다.
2. YOLO 프레임워크: 다른 Vision 모델과 동일한 프레임워크를 사용하여 일관성을 유지합니다.
3. 데이터셋 연동: ai/data/yolo_router에 구성된 데이터를 사용하여 학습을 진행합니다.

[사용법]
python ai/scripts/vision/train_router.py --mode all --epochs 150
"""
import argparse
import os
import platform
from ultralytics import YOLO
import shutil

# =============================================================================
# [Configuration] RunPod Optimized Settings
# =============================================================================
BASE_MODEL = "yolo11m-cls.pt"

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

DATA_DIR = os.path.join(DATA_ROOT, "yolo_router")
OUTPUT_DIR = "ai/runs/router_model"
SAVE_PATH = "ai/weights/router/best.pt"

# [Environment Config] 환경 변수로 제어 가능
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))  # Classification은 큰 batch 가능
DEFAULT_IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))  # Router는 640으로도 충분
WORKERS = 4 if platform.system() != "Windows" else 0  # 자동 감지

# RunPod 환경 감지
IS_RUNPOD = os.path.exists(RUNPOD_DATA_PATH)
CACHE = False

# Training Hyperparameters
DEFAULT_EPOCHS = 150
LR0 = 0.01
LRF = 0.1

# Augmentation (Classification Optimized)
MOSAIC = 1.0
MIXUP = 0.3
HSV_H = 0.03
HSV_S = 0.9
HSV_V = 0.7

# Regularization
WEIGHT_DECAY = 0.0005


def train_model(mode="train", epochs=DEFAULT_EPOCHS, batch_size=None):
    """
    Train or Evaluate YOLOv11M-cls model for scene classification (4 classes).
    """
    # Batch size 기본값 처리
    if batch_size is None:
        batch_size = DEFAULT_BATCH_SIZE
    
    # Base model 존재 여부 확인
    if not os.path.exists(BASE_MODEL):
        print(f"[Error] Base model not found: {BASE_MODEL}")
        print(f"Please download from: https://github.com/ultralytics/assets/releases/download/v8.1.0/{BASE_MODEL}")
        return
    
    # 데이터셋 확인
    if not os.path.exists(DATA_DIR):
        print(f"[Error] Data directory not found: {DATA_DIR}")
        print(f"[Info] Checking paths:")
        print(f"  - RunPod path: {RUNPOD_DATA_PATH} (Exists: {os.path.exists(RUNPOD_DATA_PATH)})")
        print(f"  - Local path: {LOCAL_DATA_PATH} (Exists: {os.path.exists(LOCAL_DATA_PATH)})")
        print(f"  - Using: {DATA_ROOT}")
        return
    
    if mode == "train":
        print(f"\n🚀 Starting YOLOv11M-cls Training for Router (4 Classes)")
        print(f"   Environment: {'RunPod' if IS_RUNPOD else 'Local'}")
        print(f"   Data: {DATA_DIR}")
        print(f"   Output: {OUTPUT_DIR}")
        print(f"   Epochs: {epochs}")
        print(f"   Batch: {batch_size}")
        print(f"   Image Size: {DEFAULT_IMG_SIZE}")
        print(f"   Workers: {WORKERS}")
        print(f"   Cache: {CACHE}")
        
        # 기존 가중치 백업
        if os.path.exists(SAVE_PATH):
            old_path = SAVE_PATH.replace(".pt", "_old.pt")
            shutil.copy(SAVE_PATH, old_path)
            print(f"📦 기존 가중치를 백업했습니다: {old_path}")
        
        # Load Model
        model = YOLO(BASE_MODEL)
        
        # Train
        results = model.train(
            data=DATA_DIR,
            epochs=epochs,
            imgsz=DEFAULT_IMG_SIZE,
            batch=batch_size,
            device=0,
            project=OUTPUT_DIR,
            name="train",
            exist_ok=True,
            plots=True,
            cache=CACHE,
            workers=WORKERS,
            
            # Optimizer
            optimizer="AdamW",
            lr0=LR0,
            lrf=LRF,
            
            # Augmentation
            mosaic=MOSAIC,
            mixup=MIXUP,
            hsv_h=HSV_H,
            hsv_s=HSV_S,
            hsv_v=HSV_V,
            
            # Regularization
            weight_decay=WEIGHT_DECAY,
            
            # Performance
            amp=True,  # Mixed precision
        )
        
        # 가중치 저장
        if hasattr(results, 'save_dir'):
            best_path = os.path.join(results.save_dir, "weights", "best.pt")
        else:
            best_path = os.path.join(OUTPUT_DIR, "train", "weights", "best.pt")
        
        if os.path.exists(best_path):
            os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
            shutil.copy(best_path, SAVE_PATH)
            print(f"\n✅ Training Completed. Best weights saved at: {SAVE_PATH}")
        else:
            print(f"[Warning] Best model weight file not found at: {best_path}")
    
    elif mode in ["val", "test"]:
        print(f"\n🔍 Starting YOLOv11M-cls Evaluation ({mode} mode)")
        
        if not os.path.exists(SAVE_PATH):
            print(f"   ⚠️ [Error] Trained weights not found: {SAVE_PATH}")
            return
        
        model = YOLO(SAVE_PATH)
        
        # Validation
        metrics = model.val(
            data=DATA_DIR,
            split=mode,
            workers=WORKERS,
            project=OUTPUT_DIR,
            name=f"val_{mode}",
            exist_ok=True
        )
        
        # Detailed Results
        print("\n" + "="*70)
        print(f"🎯 Router Classification Results:")
        print("-" * 70)
        print(f"   Top-1 Accuracy:  {metrics.top1:.4f}")
        print(f"   Top-5 Accuracy:  {metrics.top5:.4f}")
        print("=" * 70)
        
        print(f"\n📈 Results & Plots Saved at:")
        print(f"   {os.path.join(OUTPUT_DIR, f'val_{mode}')}")
        print(f"   [Confusion Matrix] {os.path.join(OUTPUT_DIR, f'val_{mode}', 'confusion_matrix.png')}")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train", choices=["train", "val", "test"], help="train, val, or test")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE, help=f"Batch size (default: {DEFAULT_BATCH_SIZE})")
    args = parser.parse_args()
    
    train_model(mode=args.mode, epochs=args.epochs, batch_size=args.batch)
