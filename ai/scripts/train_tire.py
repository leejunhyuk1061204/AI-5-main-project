# ai/scripts/train_tire.py
"""
타이어 상태 분석 YOLO 모델 학습 도구 (Tire YOLO Trainer)

[역할]
1. 결함 탐지 학습: 타이어의 고무 상태(정상, 마모, 균열) 및 측면 파손 등을 감지하는 YOLOv8 모델을 학습합니다.
2. 미세 패턴 식별: 타이어 패턴의 세밀한 변화를 학습할 수 있도록 고해상도(imgsz 640/1280) 설정을 지원합니다.
3. 데이터셋 연동: ai/data/tire 구조에 저장된 이미지와 라벨을 사용하여 학습을 진행합니다.

[사용법]
python ai/scripts/train_tire.py --mode train --epochs 150
"""
import argparse
import os
import shutil
from ultralytics import YOLO

# =============================================================================
# [Configuration] 
# =============================================================================
BASE_MODEL = "yolov8s-cls.pt"  # 타이어 상태 분류를 위해 Classification 모델 사용
DATA_DIR = "ai/data/yolo/tire" # 분류 모델은 폴더 구조(normal/cracked)를 직접 읽음
OUTPUT_DIR = "ai/runs/tire_model"
SAVE_PATH = "ai/weights/tire/best.pt"

DEFAULT_EPOCHS = 100
BATCH_SIZE = 32  # Classification은 Detection보다 배치를 크게 가져가도 됨
IMG_SIZE = 224   # YOLO 분류 모델 표준 사이즈

def train_model(epochs=DEFAULT_EPOCHS):
    print(f"\n[Tire Classification] 학습 시작 ({epochs} epochs)...")
    if not os.path.exists(DATA_DIR):
        print(f"[Error] 데이터 디렉토리 {DATA_DIR} 가 없습니다.")
        return
    
    model = YOLO(BASE_MODEL)
    results = model.train(
        data=DATA_DIR,
        epochs=epochs,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        project=OUTPUT_DIR,
        name="run",
        exist_ok=True,
        device=0
    )
    
    # 가중치 저장 - 실제 저장 경로를 동적으로 추적
    if hasattr(results, 'save_dir'):
        best_path = os.path.join(results.save_dir, "weights", "best.pt")
    else:
        best_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")

    if os.path.exists(best_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        shutil.copy(best_path, SAVE_PATH)
        print(f"[✓] 분류 모델이 저장되었습니다: {SAVE_PATH}")
    else:
        print(f"[Warning] Best model weight file not found at: {best_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tire Status Analysis Training")
    parser.add_argument("--mode", type=str, default="train", choices=["train", "test"])
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    args = parser.parse_args()
    
    if args.mode == "train":
        train_model(args.epochs)
