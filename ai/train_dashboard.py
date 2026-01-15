#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dashboard Warning Light Training Script (YOLOv8)
Usage:
    python train_dashboard.py --mode baseline  # 초기 모델 정밀도만 측정
    python train_dashboard.py --mode train     # 학습만 실행
    python train_dashboard.py --mode test      # 최종 모델 테스트만
    python train_dashboard.py --mode all       # 전체 실행 (기본값)
"""
import argparse
import os
from roboflow import Roboflow
from ultralytics import YOLO

# =============================================================================
# [설정] 경로 및 하이퍼파라미터
# =============================================================================
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "rshw91xj9lAScwI4FBXA")
ROBOFLOW_WORKSPACE = "teamdata"
ROBOFLOW_PROJECT = "car-dashboard-sndt9"
ROBOFLOW_VERSION = 3

BASE_MODEL = "yolov8n.pt"  # 기본 사전학습 모델
OUTPUT_DIR = "ai/runs/dashboard_model"
SAVE_PATH = "ai/weights/dashboard/best.pt"

# 전역 변수
data_yaml_path = None

# =============================================================================
# 1. 데이터 다운로드
# =============================================================================
def download_data():
    global data_yaml_path
    
    print("\n" + "="*50)
    print("[Step 1] Roboflow 데이터셋 다운로드...")
    print("="*50)
    
    rf = Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(ROBOFLOW_WORKSPACE).project(ROBOFLOW_PROJECT)
    version = project.version(ROBOFLOW_VERSION)
    dataset = version.download("yolov8")
    
    data_yaml_path = os.path.join(dataset.location, "data.yaml")
    print(f"[✓] 데이터 다운로드 완료: {dataset.location}")
    print(f"[✓] data.yaml 경로: {data_yaml_path}")
    
    return dataset.location

# =============================================================================
# 2. 초기 모델 정밀도 측정 (Baseline)
# =============================================================================
def evaluate_baseline():
    print("\n" + "="*50)
    print("[Step 2] 초기 모델(Baseline) 정밀도 측정...")
    print("="*50)
    
    if data_yaml_path is None:
        print("[Error] 먼저 데이터를 다운로드해주세요")
        return None
    
    # 사전학습 YOLO 모델 로드 (Fine-tuning 전)
    model = YOLO(BASE_MODEL)
    
    print(f"[Info] 기본 모델({BASE_MODEL})로 평가 중...")
    metrics = model.val(data=data_yaml_path, split='val')
    
    map50 = metrics.box.map50
    map50_95 = metrics.box.map
    
    print("\n" + "="*40)
    print(f"🎯 초기 모델 정밀도(Baseline):")
    print(f"   mAP50:    {map50:.4f}")
    print(f"   mAP50-95: {map50_95:.4f}")
    print("="*40 + "\n")
    
    return {"map50": map50, "map50_95": map50_95}

# =============================================================================
# 3. 모델 학습
# =============================================================================
def train_model(epochs=50):
    print("\n" + "="*50)
    print(f"[Step 3] 모델 학습 시작 ({epochs} epochs)...")
    print("="*50)
    
    if data_yaml_path is None:
        print("[Error] 먼저 데이터를 다운로드해주세요")
        return None
    
    model = YOLO(BASE_MODEL)
    
    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        imgsz=640,
        device=0,  # GPU 사용
        project=OUTPUT_DIR,
        name="run",
        exist_ok=True
    )
    
    # best.pt 복사
    best_model_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")
    if os.path.exists(best_model_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        import shutil
        shutil.copy(best_model_path, SAVE_PATH)
        print(f"[✓] 모델 저장 완료: {SAVE_PATH}")
    
    return results

# =============================================================================
# 4. 최종 모델 테스트
# =============================================================================
def evaluate_final():
    print("\n" + "="*50)
    print("[Step 4] 최종 모델 정밀도 측정...")
    print("="*50)
    
    if not os.path.exists(SAVE_PATH):
        print(f"[Error] 학습된 모델이 없습니다: {SAVE_PATH}")
        print("먼저 --mode train 으로 학습을 실행해주세요.")
        return None
    
    if data_yaml_path is None:
        print("[Error] 먼저 데이터를 다운로드해주세요")
        return None
    
    # 학습된 모델 로드
    model = YOLO(SAVE_PATH)
    
    print(f"[Info] 학습된 모델({SAVE_PATH})로 평가 중...")
    metrics = model.val(data=data_yaml_path, split='test')
    
    map50 = metrics.box.map50
    map50_95 = metrics.box.map
    
    print("\n" + "="*40)
    print(f"🎯 최종 모델 정밀도(Final):")
    print(f"   mAP50:    {map50:.4f}")
    print(f"   mAP50-95: {map50_95:.4f}")
    print("="*40 + "\n")
    
    return {"map50": map50, "map50_95": map50_95}

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLOv8 Dashboard Training Script")
    parser.add_argument("--mode", type=str, default="all",
                        choices=["baseline", "train", "test", "all"],
                        help="실행 모드: baseline(초기), train(학습), test(테스트), all(전체)")
    parser.add_argument("--epochs", type=int, default=50,
                        help="학습 에폭 수 (기본값: 50)")
    
    args = parser.parse_args()
    
    print(f"\n🚀 Dashboard Training Script 시작 (mode={args.mode}, epochs={args.epochs})")
    
    # 데이터 다운로드 (모든 모드에서 필요)
    download_data()
    
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
            print("\n" + "="*50)
            print("📊 정밀도 비교 (mAP50)")
            print("="*50)
            print(f"   초기 모델(Baseline): {baseline['map50']:.4f}")
            print(f"   최종 모델(Final):    {final['map50']:.4f}")
            print(f"   향상도:              +{(final['map50'] - baseline['map50'])*100:.2f}%")
            print("="*50 + "\n")
    
    print("✅ 완료!")