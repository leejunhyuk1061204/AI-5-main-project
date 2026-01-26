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
from ultralytics import YOLO

# =============================================================================
# [Configuration] 
# =============================================================================
BASE_MODEL = "yolov8n.pt"  # 계기판은 모델이 가벼워도 충분함 (n/s 권장)
DATA_YAML_PATH = "ai/data/yolo/dashboard/data.yaml"
OUTPUT_DIR = "ai/runs/dashboard_model"
SAVE_PATH = "ai/weights/dashboard/best.pt"

DEFAULT_EPOCHS = 100
BATCH_SIZE = 8  # RTX 3050 (6GB) 에 맞게 줄임
IMG_SIZE = 640
WORKERS = 0  # Windows 메모리 문제 방지

def train_model(epochs=DEFAULT_EPOCHS):
    print(f"\n[Dashboard] 학습 시작 ({epochs} epochs)...")
    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] {DATA_YAML_PATH} 가 없습니다.")
        return
    
    model = YOLO(BASE_MODEL)
    model.train(
        data=DATA_YAML_PATH,
        epochs=epochs,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        project=OUTPUT_DIR,
        name="run",
        exist_ok=True,
        device=0,
        workers=WORKERS  # Windows 메모리 문제 방지
    )
    
    # 가중치 저장
    best_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")
    if os.path.exists(best_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        shutil.copy(best_path, SAVE_PATH)
        print(f"[✓] 모델이 저장되었습니다: {SAVE_PATH}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dashboard Warning Light Training")
    parser.add_argument("--mode", type=str, default="train", choices=["train", "test"])
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    args = parser.parse_args()
    
    if args.mode == "train":
        train_model(args.epochs)
