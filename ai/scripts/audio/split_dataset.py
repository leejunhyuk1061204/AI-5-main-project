"""
[파일 용도] 데이터셋 분할 (Train/Test)
처리된(Processed) 오디오 데이터를 지정된 비율(예: 8:2)로 Train/Test 세트로 무작위 분할합니다.
디렉토리 구조를 유지하며, `metadata.csv` 파일도 함께 분할하여 저장합니다.
"""
import os
import shutil
import random
import csv
from pathlib import Path

def split_dataset(source_dir, train_dir, test_dir, split_ratio=0.8):
    """
    source_dir의 데이터를 train_dir과 test_dir로 8:2 비율로 분할합니다.
    디렉토리 구조와 metadata.csv를 유지합니다.
    """
    source_root = Path(source_dir)
    train_root = Path(train_dir)
    test_root = Path(test_dir)
    
    random.seed(42)  # 재현성
    
    # 모든 오디오 파일 수집 (.wav)
    files_by_category = {}
    
    for wav_path in source_root.rglob("*.wav"):
        relative_dir = wav_path.parent.relative_to(source_root)
        category = str(relative_dir)
        
        if category not in files_by_category:
            files_by_category[category] = []
        files_by_category[category].append(wav_path)

    print(f"[Split] 카테고리 수: {len(files_by_category)}")
    
    # 분할 결과 추적 (metadata.csv 생성용)
    train_files_set = set()
    test_files_set = set()

    for category, files in files_by_category.items():
        random.shuffle(files)
        
        split_idx = int(len(files) * split_ratio)
        train_files = files[:split_idx]
        test_files = files[split_idx:]
        
        print(f" - {category}: {len(files)}개 -> Train {len(train_files)}, Test {len(test_files)}")
        
        # 디렉토리 생성
        (train_root / category).mkdir(parents=True, exist_ok=True)
        (test_root / category).mkdir(parents=True, exist_ok=True)
        
        # 파일 복사
        for f in train_files:
            shutil.copy2(f, train_root / category / f.name)
            train_files_set.add(f.name)
        for f in test_files:
            shutil.copy2(f, test_root / category / f.name)
            test_files_set.add(f.name)

    # metadata.csv 분할
    metadata_path = source_root / "metadata.csv"
    if metadata_path.exists():
        print("\n[Split] metadata.csv 분할 중...")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        train_rows = [r for r in rows if r['file_name'] in train_files_set]
        test_rows = [r for r in rows if r['file_name'] in test_files_set]
        
        # folder 경로 업데이트
        for r in train_rows:
            r['folder'] = r['folder'].replace('processed', 'train')
        for r in test_rows:
            r['folder'] = r['folder'].replace('processed', 'test')
        
        # 저장
        with open(train_root / "metadata.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(train_rows)
        
        with open(test_root / "metadata.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(test_rows)
        
        print(f" - Train metadata: {len(train_rows)}개")
        print(f" - Test metadata: {len(test_rows)}개")

    print("\n✅ 데이터 분할 완료!")
    print(f" - Train 경로: {train_root}")
    print(f" - Test 경로: {test_root}")

if __name__ == "__main__":
    source = "c:/Users/301/AI-5-main-project/ai/data/audio/processed"
    train = "c:/Users/301/AI-5-main-project/ai/data/audio/train"
    test = "c:/Users/301/AI-5-main-project/ai/data/audio/test"
    
    # 기존 데이터 삭제 (중복 방지)
    if os.path.exists(train): shutil.rmtree(train)
    if os.path.exists(test): shutil.rmtree(test)
    
    split_dataset(source, train, test)
