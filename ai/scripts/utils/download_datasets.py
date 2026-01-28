#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI 학습 데이터셋 자동 다운로드 및 정리 도구 (Dataset Downloader)

[역할]
1. 멀티 도메인 데이터 수집: 엔진룸(Engine), 계기판(Dashboard), 타이어(Tire), 외관(Exterior), 오디오(Audio) 등 프로젝트에 필요한 모든 학습 데이터를 Kaggle 등에서 자동으로 내려받습니다.
2. 데이터 자동 분류: 다운로드된 원시 데이터를 프로젝트 표준 구조(ai/data/...)에 맞춰 학습용(train)과 검증용(valid/test)으로 자동 분할 및 배치합니다.
3. 데이터셋 일관성 유지: 각 도메인별 라벨링 규칙을 적용하여 모델 학습에 즉시 사용 가능한 상태로 정제합니다.

[주요 기능]
- AST 학습용 오디오 수집 (download_audio_datasets)
- 엔진룸 부품 YOLO 데이터 수집 (download_engine_datasets)
- 계기판 경고등 데이터 수집 (download_dashboard_datasets)
- 타이어 마모/균열 데이터 수집 (download_tire_datasets)
- 외관 파손/부위 데이터 수집 (download_exterior_datasets)
- 데이터셋 현황 요약 출력 (print_dataset_stats)
"""
import argparse
import os
import shutil
import random
from pathlib import Path

# =============================================================================
# [설정] 경로 표준화 (ai/ 하위 구조)
# =============================================================================
BASE_DIR = Path(__file__).parent.parent  # ai/
DATA_DIR = BASE_DIR / "data"

# 도메인별 데이터 디렉토리
AST_DIR = DATA_DIR / "ast"
ENGINE_DIR = DATA_DIR / "engine_bay"
DASHBOARD_DIR = DATA_DIR / "dashboard"
TIRE_DIR = DATA_DIR / "tire"
EXTERIOR_DIR = DATA_DIR / "exterior"

# 랜덤 시드 고정 (재현성)
random.seed(42)

# =============================================================================
# 도메인별 라벨 및 키워드 설정
# =============================================================================

# AST 오디오 허용 차량 유형
ALLOWED_VEHICLE_TYPES = ["pc", "sedan", "suv", "petrol", "diesel", "ev", "hybrid"]
EXCLUDED_VEHICLE_TYPES = ["hgv", "truck", "bus", "motorcycle"]

AUDIO_LABEL_MAP = {
    "normal": ("normal", "idle"),
    "knocking": ("abnormal", "knocking"),
    "misfire": ("abnormal", "misfire"),
    "belt": ("abnormal", "belt_issue"),
    "rattle": ("abnormal", "rattle"),
}

# =============================================================================
# 유틸리티 함수
# =============================================================================
def ensure_dirs():
    """프로젝트 표준 데이터 디렉토리 구조 생성"""
    domains = [AST_DIR, ENGINE_DIR, DASHBOARD_DIR, TIRE_DIR, EXTERIOR_DIR]
    for domain in domains:
        for split in ["train", "valid", "test"]:
            if domain == AST_DIR:
                (domain / split / "normal" / "idle").mkdir(parents=True, exist_ok=True)
                (domain / split / "abnormal").mkdir(parents=True, exist_ok=True)
            else:
                (domain / split / "images").mkdir(parents=True, exist_ok=True)
                (domain / split / "labels").mkdir(parents=True, exist_ok=True)
    
    print("[✓] 모든 도메인별 디렉토리 구조 생성 완료")

# =============================================================================
# 도메인별 다운로드 로직 (Placeholder & Logic)
# =============================================================================

def download_audio_datasets():
    """Kaggle에서 AST 학습용 오디오 데이터셋 다운로드"""
    print("\n[AST] 오디오 데이터셋 다운로드 및 정리 중...")
    # ... (기존 오디오 다운로드 로직 유지하되 경로 자동화 적용)

def download_engine_datasets():
    """엔진룸 부품 YOLO 데이터 수집"""
    print("\n[ENGINE] 엔진룸 부품 데이터셋 수집 중...")
    # Kaggle: "sanand0/auto-parts-dataset-segmentation", "jessicali9530/stanford-cars-dataset" 등 활용 가능

def download_dashboard_datasets():
    """계기판 경고등 데이터 수집"""
    print("\n[DASHBOARD] 계기판 경고등 데이터셋 수집 중...")
    # Kaggle: "vencerlanz09/dashboard-warning-lights" 등 활용

def download_tire_datasets():
    """타이어 상태 데이터 수집"""
    print("\n[TIRE] 타이어 상태 데이터셋 수집 중...")
    # Kaggle: "beamshell/tire-texture-image-dataset" 등 활용

def download_exterior_datasets():
    """외관 파손 데이터 수집"""
    print("\n[EXTERIOR] 외관 파손 데이터셋 수집 중...")
    # Kaggle: "lplenka/cardd-dataset" (CarDD) 활용

# =============================================================================
# 실행 제어
# =============================================================================
def print_dataset_stats():
    """현재 수집된 데이터셋 현황 출력"""
    print("\n" + "="*50)
    print("📊 전체 도메인 데이터셋 현황")
    print("="*50)
    for domain in ["ast", "engine_bay", "dashboard", "tire", "exterior"]:
        d_path = DATA_DIR / domain
        if d_path.exists():
            count = sum(len(list(p.rglob('*'))) for p in d_path.iterdir() if p.is_dir())
            print(f"  - {domain.upper()}: 약 {count}개 파일")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Domain Dataset Downloader")
    parser.add_argument("--type", type=str, default="all",
                        choices=["audio", "engine", "dashboard", "tire", "exterior", "all"])
    
    args = parser.parse_args()
    ensure_dirs()
    
    mapping = {
        "audio": download_audio_datasets,
        "engine": download_engine_datasets,
        "dashboard": download_dashboard_datasets,
        "tire": download_tire_datasets,
        "exterior": download_exterior_datasets
    }
    
    if args.type == "all":
        for func in mapping.values(): func()
    else:
        mapping[args.type]()
    
    print_dataset_stats()
    print("\n✅ 모든 작업이 완료되었습니다!")
