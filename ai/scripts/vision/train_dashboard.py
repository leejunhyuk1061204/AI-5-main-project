# ai/scripts/train_dashboard.py
"""
계기판 경고등 감지 YOLO 모델 학습 도구 (Dashboard YOLO Trainer)

[역할]
1. 경고등 식별 학습: 계기판의 주요 경고등(엔진 check, 오일, 배터리, 타이어압 등 10종)의 위치와 종류를 탐지하는 YOLOv8 모델을 학습합니다.
2. 실무 데이터 최적화: 다양한 차량 계기판 이미지에 대응할 수 있는 Augmentation 설정이 포함되어 있습니다.
3. 성능 리포트: mAP50을 기준으로 학습 성능을 측정하고 최적의 가중치(best.pt)를 저장합니다.

[사용법]
python ai/scripts/train_dashboard.py --mode train --epochs 100
"""
import argparse
import os
import shutil
import platform
from ultralytics import YOLO
import shutil

# =============================================================================
# [Configuration] 
# =============================================================================
BASE_MODEL = "yolo11m.pt"

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

DATA_YAML_PATH = os.path.join(DATA_ROOT, "yolo/dashboard/data.yaml")
OUTPUT_DIR = "ai/runs/dashboard_model"
SAVE_PATH = "ai/weights/dashboard/best.pt"

DEFAULT_EPOCHS = 10
BATCH_SIZE = 16  # 데이터 적을 때 최적화 (기존 2)
IMG_SIZE = 1080
WORKERS = 4 if platform.system() != "Windows" else 0  # 환경 자동 감지

# Augmentation (Small Dataset Optimized)
MOSAIC = 1.0
MIXUP = 0.2      # 증가
HSV_H = 0.02     # 증가
HSV_S = 0.9      # 증가
HSV_V = 0.6      # 증가

# Regularization
WEIGHT_DECAY = 0.0005

def train_model(epochs=DEFAULT_EPOCHS, batch=BATCH_SIZE, imgsz=IMG_SIZE, workers=WORKERS, device=0):
    print(f"\n[Dashboard] 학습 시작 ({epochs} epochs)...")
    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] {DATA_YAML_PATH} 가 없습니다.")
        return
    
    model = YOLO(BASE_MODEL)

    # [Weight Management] 기존 가중치가 있다면 백업 (누적 방지용)
    if os.path.exists(SAVE_PATH):
        old_path = SAVE_PATH.replace(".pt", "_old.pt")
        shutil.copy(SAVE_PATH, old_path)
        print(f"📦 기존 가중치를 백업했습니다: {old_path}")

    results = model.train(
        data=DATA_YAML_PATH,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,          # 데이터 적을 때 최적화 (기존 32)
        project=OUTPUT_DIR,
        name="run",
        exist_ok=True,     # 기존 폴더 덮어쓰기 (run1, run2... 누적 방지)
        device=device,
        workers=workers,         # 리눅스 환경 상향 조정 (기존 0)
        
        # Augmentation
        mosaic=MOSAIC,
        mixup=MIXUP,
        hsv_h=HSV_H,
        hsv_s=HSV_S,
        hsv_v=HSV_V,
        
        # Regularization
        weight_decay=WEIGHT_DECAY
    )
    
    # 가중치 저장 - 실제 저장 경로를 동적으로 추적
    if hasattr(results, 'save_dir'):
        best_path = os.path.join(results.save_dir, "weights", "best.pt")
    else:
        best_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")

    if os.path.exists(best_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        shutil.copy(best_path, SAVE_PATH)
        print(f"[✓] 모델이 저장되었습니다: {SAVE_PATH}")
    else:
        print(f"[Warning] Best model weight file not found at: {best_path}")

def evaluate_model():
    print(f"\n[Dashboard] 테스트 시작...")
    if not os.path.exists(SAVE_PATH):
        print(f"[Error] 학습된 모델이 없습니다: {SAVE_PATH}")
        return
    
    # Ensure output directory exists for validation plots
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    model = YOLO(SAVE_PATH)
    metrics = model.val(
        data=DATA_YAML_PATH, 
        split='test', 
        imgsz=1280, 
        project=OUTPUT_DIR, 
        name="val_test",
        exist_ok=True
    )
    
    # Detailed Metrics Extraction
    names = model.names
    precision = metrics.box.p  # Array of precision per class
    recall = metrics.box.r     # Array of recall per class
    
    print("\n" + "="*60)
    print(f"🎯 Dashboard Detailed Evaluation Results:")
    print("-" * 60)
    print(f"{'Class Name':<25} | {'Precision':<12} | {'Recall':<12}")
    print("-" * 60)
    
    for i, name in names.items():
        p_val = precision[i] if i < len(precision) else 0.0
        r_val = recall[i] if i < len(recall) else 0.0
        print(f"{name:<25} | {p_val:<12.4f} | {r_val:<12.4f}")
    
    print("-" * 60)
    print(f"💡 mAP50:    {metrics.box.map50:.4f}")
    print(f"💡 mAP50-95: {metrics.box.map:.4f}")
    print("="*60)
    
    print(f"\n📈 상세 분석 차트 저장 위치:")
    print(f"   [Confusion Matrix] {os.path.join(OUTPUT_DIR, 'val_test', 'confusion_matrix.png')}")
    print(f"   [Confidence-Recall] {os.path.join(OUTPUT_DIR, 'val_test', 'R_curve.png')} (추천)")
    print(f"   [Precision-Recall] {os.path.join(OUTPUT_DIR, 'val_test', 'PR_curve.png')}")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dashboard Warning Light Training")
    parser.add_argument("--mode", type=str, default="train", choices=["train", "test"])
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=IMG_SIZE, help="Image size")
    parser.add_argument("--workers", type=int, default=WORKERS, help="Number of dataloader workers")
    parser.add_argument("--device", type=int, default=0, help="CUDA device index")
    
    args = parser.parse_args()
    
    if args.mode == "train":
        train_model(
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            workers=args.workers,
            device=args.device
            )
    elif args.mode == "test":
        evaluate_model()
