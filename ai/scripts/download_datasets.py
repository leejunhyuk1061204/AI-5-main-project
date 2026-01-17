#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dataset Download Script for AST and YOLO Training
Downloads and organizes datasets with 80/20 train/test split

Usage:
    python download_datasets.py --type audio   # AST용 오디오 데이터만
    python download_datasets.py --type visual  # YOLO용 계기판 경고등 데이터만
    python download_datasets.py --type all     # 전체 다운로드 (기본값)
"""
import argparse
import os
import shutil
import random
from pathlib import Path

# =============================================================================
# [설정] 경로
# =============================================================================
BASE_DIR = Path(__file__).parent.parent  # ai/
DATA_DIR = BASE_DIR / "data"

AST_DIR = DATA_DIR / "ast"
YOLO_DIR = DATA_DIR / "yolo"

# 랜덤 시드 고정 (재현성)
random.seed(42)

# =============================================================================
# AST 오디오 데이터 라벨 매핑
# =============================================================================
# 허용되는 차량 유형 (승용차, 전기차, 하이브리드만 분석)
ALLOWED_VEHICLE_TYPES = [
    # 승용차 (Passenger Car)
    "pc", "passenger", "sedan", "suv", "hatchback",
    "petrol", "gasoline", "diesel",
    "benz", "audi", "bmw", "hyundai", "kia", "toyota", "honda",
    # 전기차 (Electric Vehicle)
    "ev", "electric", "tesla", "ioniq", "ev6", "egmp",
    # 하이브리드 (Hybrid)
    "hybrid", "hev", "phev", "prius",
]

# 제외할 차량 유형 (대형 화물차 등)
EXCLUDED_VEHICLE_TYPES = [
    "hgv", "truck", "lorry", "heavy", "bus", "commercial",
    "motorcycle", "bike", "scooter",
]

AUDIO_LABEL_MAP = {
    # 정상 엔진음 (승용차, 전기차, 하이브리드)
    "benz_normal": ("normal", "idle"),
    "audi_normal": ("normal", "idle"),
    "PC": ("normal", "idle"),
    "diesel": ("normal", "idle"),
    "petrol": ("normal", "idle"),
    "ev": ("normal", "idle"),
    "electric": ("normal", "idle"),
    "hybrid": ("normal", "idle"),
    "hev": ("normal", "idle"),
    "정상": ("normal", "idle"),
    "normal": ("normal", "idle"),
    
    # 비정상 소리
    "Knocking": ("abnormal", "knocking"),
    "knocking": ("abnormal", "knocking"),
    "Misfire": ("abnormal", "misfire"),
    "misfire": ("abnormal", "misfire"),
    "Belt": ("abnormal", "belt_issue"),
    "belt": ("abnormal", "belt_issue"),
    "소음": ("abnormal", "rattle"),
    "rattle": ("abnormal", "rattle"),
    "vibration": ("abnormal", "rattle"),
    "faulty": ("abnormal", "knocking"),
}

# =============================================================================
# YOLO 계기판 경고등 라벨 매핑
# =============================================================================
DASHBOARD_LABEL_MAP = {
    # 계기판 경고등 종류
    "engine": ("warning", "engine"),
    "engine_warning": ("warning", "engine"),
    "check_engine": ("warning", "engine"),
    "oil": ("warning", "oil"),
    "oil_pressure": ("warning", "oil"),
    "battery": ("warning", "battery"),
    "battery_warning": ("warning", "battery"),
    "tire": ("warning", "tire"),
    "tire_pressure": ("warning", "tire"),
    "tpms": ("warning", "tire"),
    "abs": ("warning", "abs"),
    "brake": ("warning", "brake"),
    "airbag": ("warning", "airbag"),
    "temperature": ("warning", "temperature"),
    "coolant": ("warning", "temperature"),
    "fuel": ("warning", "fuel"),
    "door": ("info", "door"),
    "seatbelt": ("info", "seatbelt"),
}

# =============================================================================
# 유틸리티 함수
# =============================================================================
def ensure_dirs():
    """필요한 디렉토리 구조 생성"""
    # AST 디렉토리
    for split in ["train", "test"]:
        (AST_DIR / split / "normal" / "idle").mkdir(parents=True, exist_ok=True)
        for atype in ["knocking", "misfire", "belt_issue", "rattle"]:
            (AST_DIR / split / "abnormal" / atype).mkdir(parents=True, exist_ok=True)
    
    # YOLO 계기판 경고등 디렉토리 (표준 YOLO 형식)
    (YOLO_DIR / "train" / "images").mkdir(parents=True, exist_ok=True)
    (YOLO_DIR / "train" / "labels").mkdir(parents=True, exist_ok=True)
    (YOLO_DIR / "valid" / "images").mkdir(parents=True, exist_ok=True)
    (YOLO_DIR / "valid" / "labels").mkdir(parents=True, exist_ok=True)
    
    print("[✓] 디렉토리 구조 생성 완료")


# =============================================================================
# AST 오디오 데이터 다운로드
# =============================================================================
def download_audio_datasets():
    """Kaggle에서 AST 학습용 오디오 데이터셋 다운로드"""
    print("\n" + "="*50)
    print("[AST] 오디오 데이터셋 다운로드 중...")
    print("="*50)
    
    try:
        import kagglehub
    except ImportError:
        print("[Error] kagglehub가 설치되지 않았습니다. pip install kagglehub")
        return
    
    datasets = [
        "janboubiabderrahim/vehicle-sounds-dataset",
        "amaninair/ai-mechanic-engine-condition-audio-fault-finding",
    ]
    
    all_audio_files = []
    
    for dataset_id in datasets:
        try:
            print(f"\n[Info] 다운로드 중: {dataset_id}")
            path = kagglehub.dataset_download(dataset_id)
            print(f"[✓] 다운로드 완료: {path}")
            
            # 오디오 파일 수집 (다양한 형식 지원)
            path_obj = Path(path)
            audio_files = (
                list(path_obj.rglob("*.wav")) +
                list(path_obj.rglob("*.mp3")) +
                list(path_obj.rglob("*.m4a")) +
                list(path_obj.rglob("*.ogg")) +
                list(path_obj.rglob("*.flac"))
            )
            all_audio_files.extend(audio_files)
            print(f"[Info] {len(audio_files)}개의 오디오 파일 발견")
            
        except Exception as e:
            print(f"[Warning] {dataset_id} 다운로드 실패: {e}")
    
    if all_audio_files:
        copied = copy_audio_files(all_audio_files)
        print(f"\n[✓] AST 데이터 정리 완료: {copied}개 파일 복사됨")
    else:
        print("[Warning] 오디오 파일을 찾지 못했습니다")


def is_allowed_vehicle_type(path_str: str) -> bool:
    """승용차, 전기차, 하이브리드 소리인지 확인"""
    path_lower = path_str.lower()
    
    # 1. 제외할 차량 유형 체크 (HGV, 트럭, 버스 등)
    for excluded in EXCLUDED_VEHICLE_TYPES:
        if excluded in path_lower:
            return False
    
    # 2. 허용된 차량 유형 체크 (승용차, 전기차, 하이브리드)
    for allowed in ALLOWED_VEHICLE_TYPES:
        if allowed in path_lower:
            return True
    
    # 3. 비정상 소리 관련 키워드는 차량 유형과 무관하게 허용
    abnormal_keywords = ["knocking", "misfire", "belt", "rattle", "vibration", "faulty", "소음"]
    for keyword in abnormal_keywords:
        if keyword in path_lower:
            return True
    
    # 4. 기본값: 허용하지 않음 (알 수 없는 차량 유형)
    return False


def copy_audio_files(files: list):
    """오디오 파일을 라벨별로 분류하여 복사 (승용차, 전기차, 하이브리드만)"""
    extensions = (".wav", ".mp3", ".m4a", ".ogg", ".flac")
    valid_files = [f for f in files if f.suffix.lower() in extensions]
    
    if not valid_files:
        return 0
    
    # 차량 유형 필터링: 승용차, 전기차, 하이브리드만 포함
    filtered_files = []
    skipped_count = 0
    
    for f in valid_files:
        # 전체 경로에서 차량 유형 확인
        full_path = str(f)
        if is_allowed_vehicle_type(full_path):
            filtered_files.append(f)
        else:
            skipped_count += 1
    
    if skipped_count > 0:
        print(f"[Info] 대형 화물차/기타 차량 제외: {skipped_count}개 파일 스킵됨")
    
    print(f"[Info] 승용차/전기차/하이브리드 파일: {len(filtered_files)}개")
    
    if not filtered_files:
        return 0
    
    random.shuffle(filtered_files)
    split_idx = int(len(filtered_files) * 0.8)
    train_files = filtered_files[:split_idx]
    test_files = filtered_files[split_idx:]
    
    copied = 0
    
    for split_name, file_list in [("train", train_files), ("test", test_files)]:
        for file_path in file_list:
            folder_name = file_path.parent.name.lower()
            
            # 라벨 매핑 찾기
            category, subtype = "normal", "idle"
            for key, value in AUDIO_LABEL_MAP.items():
                if key.lower() in folder_name:
                    category, subtype = value
                    break
            
            target_dir = AST_DIR / split_name / category / subtype
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / file_path.name
            
            if not target_path.exists():
                try:
                    shutil.copy2(file_path, target_path)
                    copied += 1
                except Exception as e:
                    print(f"[Error] 복사 실패: {e}")
    
    return copied


# =============================================================================
# YOLO 계기판 경고등 데이터 다운로드 (Roboflow)
# =============================================================================
def download_visual_datasets():
    """Roboflow에서 YOLO 학습용 계기판 경고등 데이터셋 다운로드"""
    print("\n" + "="*50)
    print("[YOLO] 계기판 경고등 데이터셋 다운로드 중...")
    print("="*50)
    
    try:
        from roboflow import Roboflow
    except ImportError:
        print("[Error] roboflow가 설치되지 않았습니다. pip install roboflow")
        return
    
    api_key = os.getenv("ROBOFLOW_API_KEY", "rshw91xj9lAScwI4FBXA")
    
    # 계기판 경고등 관련 데이터셋 다운로드
    roboflow_datasets = [
        # (workspace, project, version) - 계기판 경고등 데이터셋
        ("teamdata", "car-dashboard-sndt9", 3),           # 현재 사용 중
        ("bsiconsultingservices", "car-dashboard", 2),    # 18 classes - 가장 포괄적
        ("wt-qcxmo", "car-dashboard-detection", 1),       # 10 classes
        ("test-vekwl", "car-dashboard-icons", 2),         # 10 classes
        ("space-d7jln", "car-dashboard-icons-2", 1),      # 10 classes
    ]
    
    rf = Roboflow(api_key=api_key)
    
    for workspace, project, version in roboflow_datasets:
        try:
            print(f"\n[Info] Roboflow 다운로드 중: {workspace}/{project} v{version}")
            proj = rf.workspace(workspace).project(project)
            
            # YOLO 형식으로 다운로드 (train/valid 폴더에 직접 저장)
            dataset = proj.version(version).download("yolov8", location=str(YOLO_DIR))
            
            print(f"[✓] 다운로드 완료: {dataset.location}")
            print(f"[✓] data.yaml 경로: {os.path.join(dataset.location, 'data.yaml')}")
            
            # 다운받은 파일 개수 확인
            train_images = list(Path(dataset.location).rglob("train/images/*"))
            valid_images = list(Path(dataset.location).rglob("valid/images/*"))
            print(f"[Info] Train: {len(train_images)}개, Valid: {len(valid_images)}개")
            
        except Exception as e:
            print(f"[Warning] Roboflow {project} 다운로드 실패: {e}")


# =============================================================================
# 데이터셋 상태 출력
# =============================================================================
def print_dataset_stats():
    """현재 데이터셋 상태 출력"""
    print("\n" + "="*50)
    print("📊 데이터셋 현황")
    print("="*50)
    
    # AST 통계
    print("\n[AST (Audio)]")
    for split in ["train", "test"]:
        split_dir = AST_DIR / split
        if not split_dir.exists():
            continue
        
        total = 0
        for category in ["normal", "abnormal"]:
            cat_dir = split_dir / category
            if not cat_dir.exists():
                continue
            
            for subtype_dir in cat_dir.iterdir():
                if subtype_dir.is_dir():
                    count = len(list(subtype_dir.iterdir()))
                    total += count
                    if count > 0:
                        print(f"  {split}/{category}/{subtype_dir.name}: {count}개")
        
        print(f"  [{split} 총계: {total}개]")
    
    # YOLO 통계
    print("\n[YOLO (Dashboard)]")
    for split in ["train", "valid"]:
        images_dir = YOLO_DIR / split / "images"
        labels_dir = YOLO_DIR / split / "labels"
        
        if images_dir.exists():
            img_count = len(list(images_dir.iterdir()))
            lbl_count = len(list(labels_dir.iterdir())) if labels_dir.exists() else 0
            print(f"  {split}: 이미지 {img_count}개, 라벨 {lbl_count}개")


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dataset Download Script")
    parser.add_argument("--type", type=str, default="all",
                        choices=["audio", "visual", "all"],
                        help="다운로드 타입: audio(AST), visual(YOLO 계기판), all")
    
    args = parser.parse_args()
    
    print("\n🚀 데이터셋 다운로드 스크립트 시작")
    print(f"   타입: {args.type}")
    
    # 디렉토리 생성
    ensure_dirs()
    
    if args.type in ["audio", "all"]:
        download_audio_datasets()
    
    if args.type in ["visual", "all"]:
        download_visual_datasets()
    
    # 결과 출력
    print_dataset_stats()
    
    print("\n✅ 완료!")
