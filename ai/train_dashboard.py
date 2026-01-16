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
import boto3
import shutil
import glob
import random
# from roboflow import Roboflow  # 로컬 데이터를 사용하므로 주석 처리
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
    print("[Step 1] 로컬 데이터셋 준비...")
    print("="*50)
    
    # =============================================================================
    # 로컬 데이터 폴더 구조 (YOLO 표준 형식):
    #   ai/data/yolo/
    #     ├── train/
    #     │    ├── images/    (.jpg 파일들)
    #     │    └── labels/    (.txt 라벨 파일들)
    #     ├── valid/
    #     │    ├── images/
    #     │    └── labels/
    #     └── data.yaml       (클래스 정의 파일)
    # =============================================================================
    LOCAL_DATA_DIR = "./ai/data/yolo"
    
    # data.yaml 경로 확인
    data_yaml_path = os.path.join(LOCAL_DATA_DIR, "data.yaml")
    
    if not os.path.exists(data_yaml_path):
        # 폴더 구조 자동 생성
        os.makedirs(os.path.join(LOCAL_DATA_DIR, "train", "images"), exist_ok=True)
        os.makedirs(os.path.join(LOCAL_DATA_DIR, "train", "labels"), exist_ok=True)
        os.makedirs(os.path.join(LOCAL_DATA_DIR, "valid", "images"), exist_ok=True)
        os.makedirs(os.path.join(LOCAL_DATA_DIR, "valid", "labels"), exist_ok=True)
        
        # 기본 data.yaml 생성
        default_yaml = """# Car-Sentry YOLO Dataset Configuration
path: ./ai/data/yolo
train: train/images
val: valid/images

# 클래스 목록 (경고등만 우선)
names:
  0: engine_warning
  1: oil_pressure
  2: battery
  3: tire_pressure
  4: abs_brake
"""
        with open(data_yaml_path, "w", encoding="utf-8") as f:
            f.write(default_yaml)
        
        print(f"[Warning] 데이터 폴더가 없어서 생성했습니다: {LOCAL_DATA_DIR}")
        print(f"         train/images, train/labels에 이미지와 라벨을 넣어주세요.")
        print(f"         data.yaml 파일의 클래스 목록을 수정해주세요.")
        
    print(f"[✓] 데이터 폴더 확인 완료: {LOCAL_DATA_DIR}")
    print(f"[✓] data.yaml 경로: {data_yaml_path}")
    
    # (선택적) S3 수집 데이터 추가 병합 - 나중에 Active Learning 때 사용
    load_s3_visual_data(LOCAL_DATA_DIR)
    
    return LOCAL_DATA_DIR

def load_s3_visual_data(dataset_dir):
    """S3에서 수집된 시각 데이터를 다운로드하여 학습 데이터셋에 병합합니다."""
    print("\n[Active Learning] S3 수집 데이터 병합 시도...")
    
    try:
        s3 = boto3.client('s3')
        bucket_name = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
        prefix = "dataset/visual/DASHBOARD/"
        
        # 1. 파일 목록 가져오기
        objects = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' not in objects:
            print("[Info] S3에 수집된 데이터가 없습니다.")
            return

        # 2. 이미지와 라벨 쌍 찾기
        files = set()
        for obj in objects['Contents']:
            files.add(obj['Key'])
            
        valid_pairs = []
        for f in files:
            if f.endswith(".jpg"):
                label_file = f.replace(".jpg", ".txt")
                if label_file in files:
                    valid_pairs.append(f) # 이미지 키 저장
        
        if not valid_pairs:
            print("[Info] 라벨이 있는 유효한 데이터 쌍이 없습니다.")
            return
            
        print(f"[Info] {len(valid_pairs)}개의 유효한 데이터 쌍(이미지+라벨)을 발견했습니다.")
        
        # 3. Train/Val 분할 (8:2)
        random.seed(42)
        random.shuffle(valid_pairs)
        split_idx = int(len(valid_pairs) * 0.8)
        train_files = valid_pairs[:split_idx]
        val_files = valid_pairs[split_idx:]
        
        splits = [("train", train_files), ("valid", val_files)]
        
        # 4. 다운로드 및 이동
        count = 0
        for split_name, file_list in splits:
            img_dir = os.path.join(dataset_dir, split_name, "images")
            lbl_dir = os.path.join(dataset_dir, split_name, "labels")
            
            os.makedirs(img_dir, exist_ok=True)
            os.makedirs(lbl_dir, exist_ok=True)
            
            for img_key in file_list:
                lbl_key = img_key.replace(".jpg", ".txt")
                filename = os.path.basename(img_key)
                lbl_filename = os.path.basename(lbl_key)
                
                # 다운로드 (이미 파일이 있으면 건너뛰기 가능하지만, 업데이트 고려하여 덮어쓰기 or check)
                local_img_path = os.path.join(img_dir, filename)
                local_lbl_path = os.path.join(lbl_dir, lbl_filename)
                
                if not os.path.exists(local_img_path):
                    s3.download_file(bucket_name, img_key, local_img_path)
                    s3.download_file(bucket_name, lbl_key, local_lbl_path)
                    count += 1
                    
        if count > 0:
            print(f"[Info] S3에서 {count}개의 데이터 쌍을 {dataset_dir}에 추가했습니다.")
            
            # [Auto Class Detection] 새로운 클래스 ID 자동 감지 및 data.yaml 업데이트
            update_data_yaml_with_new_classes(dataset_dir)
            
    except Exception as e:
        print(f"[Warning] S3 데이터 병합 실패: {e}")


def update_data_yaml_with_new_classes(dataset_dir):
    """
    라벨 파일들을 스캔하여 새로운 class_id를 감지하고 data.yaml을 자동 업데이트합니다.
    """
    import yaml
    
    data_yaml_path = os.path.join(dataset_dir, "data.yaml")
    
    # 1. 기존 data.yaml 불러오기
    if os.path.exists(data_yaml_path):
        with open(data_yaml_path, 'r', encoding='utf-8') as f:
            data_config = yaml.safe_load(f)
    else:
        data_config = {'names': {}, 'path': dataset_dir, 'train': 'train/images', 'val': 'valid/images'}
    
    existing_classes = data_config.get('names', {})
    if isinstance(existing_classes, list):
        # 리스트 형태면 딕셔너리로 변환
        existing_classes = {i: name for i, name in enumerate(existing_classes)}
    
    # 2. 라벨 파일들에서 class_id 수집
    found_class_ids = set()
    for split in ['train', 'valid']:
        labels_dir = os.path.join(dataset_dir, split, 'labels')
        if not os.path.exists(labels_dir):
            continue
        
        for label_file in os.listdir(labels_dir):
            if not label_file.endswith('.txt'):
                continue
            
            label_path = os.path.join(labels_dir, label_file)
            try:
                with open(label_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            class_id = int(parts[0])
                            found_class_ids.add(class_id)
            except Exception:
                continue
    
    # 3. 새로운 class_id 감지 및 추가
    new_classes_added = False
    for class_id in found_class_ids:
        if class_id not in existing_classes:
            # 새 클래스 발견! 임시 이름으로 추가
            new_class_name = f"class_{class_id}"
            existing_classes[class_id] = new_class_name
            print(f"[Auto Class] 새 클래스 발견: {class_id} -> '{new_class_name}' (data.yaml에 추가됨)")
            new_classes_added = True
    
    # 4. data.yaml 업데이트
    if new_classes_added:
        data_config['names'] = existing_classes
        with open(data_yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data_config, f, allow_unicode=True, default_flow_style=False)
        print(f"[Auto Class] data.yaml 업데이트 완료: {data_yaml_path}")
        print(f"[Warning] 새 클래스명이 'class_X'로 생성되었습니다. 의미있는 이름으로 수정해주세요!")

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