# ai/scripts/create_router_dataset.py
"""
Router 분류 데이터셋 자동 생성 스크립트

기존 YOLO 데이터셋(dashboard, engine, exterior, tire)의 이미지를 수집하여
Router 분류용 데이터셋을 생성합니다.

[사용법]
python ai/scripts/create_router_dataset.py
"""

import os
import shutil
import random
from pathlib import Path

# 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOLO_DATA_DIR = os.path.join(BASE_DIR, "data", "yolo")
ROUTER_DATA_DIR = os.path.join(BASE_DIR, "data", "yolo_router")

# Router 클래스 정의
CLASSES = {
    "dashboard": 0,
    "engine": 1,
    "exterior": 2,
    "tire": 3
}

# 각 클래스별 소스 디렉토리
SOURCE_DIRS = {
    "dashboard": os.path.join(YOLO_DATA_DIR, "dashboard"),
    "engine": os.path.join(YOLO_DATA_DIR, "engine"),
    "exterior": os.path.join(YOLO_DATA_DIR, "exterior", "cardd", "CarDD_COCO"),
    "tire": os.path.join(YOLO_DATA_DIR, "tire"),
}

# Train/Val/Test 비율
SPLIT_RATIO = {"train": 0.7, "val": 0.15, "test": 0.15}


def find_images(directory, extensions=('.jpg', '.jpeg', '.png', '.bmp')):
    """디렉토리에서 이미지 파일 찾기"""
    images = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(extensions):
                images.append(os.path.join(root, file))
    return images


def create_router_dataset():
    """Router 분류 데이터셋 생성"""
    print("=" * 60)
    print("🚀 Router 분류 데이터셋 생성 시작")
    print("=" * 60)
    
    # 출력 디렉토리 생성
    for split in ["train", "val", "test"]:
        for cls_name in CLASSES.keys():
            dir_path = os.path.join(ROUTER_DATA_DIR, split, cls_name)
            os.makedirs(dir_path, exist_ok=True)
    
    total_copied = 0
    
    for cls_name, cls_id in CLASSES.items():
        src_dir = SOURCE_DIRS.get(cls_name)
        if not src_dir or not os.path.exists(src_dir):
            print(f"[Warning] {cls_name} 소스 디렉토리 없음: {src_dir}")
            continue
        
        # 이미지 수집
        images = find_images(src_dir)
        if not images:
            print(f"[Warning] {cls_name} 이미지 없음")
            continue
        
        # 셔플
        random.shuffle(images)
        
        # 분할
        n = len(images)
        n_train = int(n * SPLIT_RATIO["train"])
        n_val = int(n * SPLIT_RATIO["val"])
        
        splits = {
            "train": images[:n_train],
            "val": images[n_train:n_train + n_val],
            "test": images[n_train + n_val:]
        }
        
        print(f"\n[{cls_name}] 총 {n}개 이미지")
        
        for split_name, split_images in splits.items():
            dest_dir = os.path.join(ROUTER_DATA_DIR, split_name, cls_name)
            for i, src_path in enumerate(split_images):
                ext = os.path.splitext(src_path)[1]
                dest_path = os.path.join(dest_dir, f"{cls_name}_{i:04d}{ext}")
                shutil.copy2(src_path, dest_path)
                total_copied += 1
            print(f"  {split_name}: {len(split_images)}개 복사")
    
    # data.yaml 생성
    yaml_content = f"""# Router Classification Dataset
# Auto-generated

path: {ROUTER_DATA_DIR}
train: train
val: val
test: test

nc: {len(CLASSES)}
names: {list(CLASSES.keys())}
"""
    
    yaml_path = os.path.join(ROUTER_DATA_DIR, "data.yaml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    print(f"\n{'=' * 60}")
    print(f"✅ 완료! 총 {total_copied}개 이미지 복사됨")
    print(f"📁 출력 경로: {ROUTER_DATA_DIR}")
    print(f"📄 data.yaml 생성 완료")
    print("=" * 60)


if __name__ == "__main__":
    create_router_dataset()
