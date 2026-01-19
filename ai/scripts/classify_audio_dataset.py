#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Audio Dataset Classification Script
카카오톡 받은 파일의 오디오 데이터셋을 train/test로 분류하여 복사

- normal이 포함된 폴더 → normal/idle/
- abnormal 폴더 → abnormal/{폴더명}/
- 80% train, 20% test 분할
"""
import os
import shutil
import random
from pathlib import Path

# 랜덤 시드 고정
random.seed(42)

# =============================================================================
# 경로 설정
# =============================================================================
SOURCE_DIR = Path(r"C:\Users\301\Documents\카카오톡 받은 파일\car diagnostics dataset (1)")
TARGET_DIR = Path(__file__).parent.parent / "data" / "ast"

# =============================================================================
# 폴더명 → 카테고리 매핑
# =============================================================================
# normal이 포함된 폴더는 자동으로 normal/idle로 분류
# 나머지는 abnormal/{폴더명}으로 분류

def classify_folder(folder_name: str) -> tuple:
    """폴더명을 기반으로 (category, subtype) 반환"""
    folder_lower = folder_name.lower()
    
    # normal이 포함되면 정상
    if "normal" in folder_lower:
        return ("normal", "idle")
    
    # 그 외는 비정상 - 폴더명을 그대로 사용
    return ("abnormal", folder_name)


def collect_audio_files(source_dir: Path) -> dict:
    """소스 디렉토리에서 모든 오디오 파일 수집 및 분류"""
    audio_extensions = (".wav", ".mp3", ".m4a", ".ogg", ".flac")
    categorized_files = {}  # {(category, subtype): [file_paths]}
    
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(audio_extensions):
                file_path = Path(root) / file
                folder_name = file_path.parent.name
                
                category, subtype = classify_folder(folder_name)
                key = (category, subtype)
                
                if key not in categorized_files:
                    categorized_files[key] = []
                categorized_files[key].append(file_path)
    
    return categorized_files


def copy_files_with_split(categorized_files: dict, target_dir: Path):
    """파일을 train/test로 분할하여 복사"""
    total_copied = 0
    
    for (category, subtype), files in categorized_files.items():
        if not files:
            continue
        
        # 랜덤 셔플 후 80/20 분할
        random.shuffle(files)
        split_idx = int(len(files) * 0.8)
        train_files = files[:split_idx]
        test_files = files[split_idx:]
        
        print(f"\n[{category}/{subtype}] 총 {len(files)}개")
        print(f"  - Train: {len(train_files)}개, Test: {len(test_files)}개")
        
        for split_name, file_list in [("train", train_files), ("test", test_files)]:
            target_subdir = target_dir / split_name / category / subtype
            target_subdir.mkdir(parents=True, exist_ok=True)
            
            for file_path in file_list:
                target_path = target_subdir / file_path.name
                
                # 파일명 충돌 방지
                if target_path.exists():
                    base = target_path.stem
                    ext = target_path.suffix
                    counter = 1
                    while target_path.exists():
                        target_path = target_subdir / f"{base}_{counter}{ext}"
                        counter += 1
                
                try:
                    shutil.copy2(file_path, target_path)
                    total_copied += 1
                except Exception as e:
                    print(f"  [Error] 복사 실패: {file_path.name} - {e}")
    
    return total_copied


def print_final_stats(target_dir: Path):
    """최종 통계 출력"""
    print("\n" + "=" * 60)
    print("📊 최종 데이터셋 현황")
    print("=" * 60)
    
    for split in ["train", "test"]:
        split_dir = target_dir / split
        if not split_dir.exists():
            continue
        
        print(f"\n[{split.upper()}]")
        total = 0
        
        for category in ["normal", "abnormal"]:
            cat_dir = split_dir / category
            if not cat_dir.exists():
                continue
            
            for subtype_dir in sorted(cat_dir.iterdir()):
                if subtype_dir.is_dir():
                    count = len([f for f in subtype_dir.iterdir() if f.is_file()])
                    total += count
                    print(f"  {category}/{subtype_dir.name}: {count}개")
        
        print(f"  [총계: {total}개]")


def main():
    print("=" * 60)
    print("🎵 오디오 데이터셋 분류 스크립트")
    print("=" * 60)
    print(f"소스: {SOURCE_DIR}")
    print(f"타겟: {TARGET_DIR}")
    
    if not SOURCE_DIR.exists():
        print(f"\n[Error] 소스 디렉토리가 존재하지 않습니다: {SOURCE_DIR}")
        return
    
    # 1. 오디오 파일 수집 및 분류
    print("\n[Step 1] 오디오 파일 수집 및 분류 중...")
    categorized_files = collect_audio_files(SOURCE_DIR)
    
    if not categorized_files:
        print("[Warning] 오디오 파일을 찾지 못했습니다.")
        return
    
    print(f"\n발견된 카테고리: {len(categorized_files)}개")
    for (category, subtype), files in categorized_files.items():
        print(f"  - {category}/{subtype}: {len(files)}개")
    
    # 2. 파일 복사 (train/test 분할)
    print("\n[Step 2] 파일 복사 중 (80% train, 20% test)...")
    total_copied = copy_files_with_split(categorized_files, TARGET_DIR)
    
    # 3. 최종 통계
    print_final_stats(TARGET_DIR)
    
    print(f"\n✅ 완료! 총 {total_copied}개 파일 복사됨")


if __name__ == "__main__":
    main()
