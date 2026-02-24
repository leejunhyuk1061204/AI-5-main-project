"""
[파일 용도] 비정상(Abnormal) 데이터 분배
전처리된 비정상 오디오 데이터를 Train/Test 셋으로 비율에 맞춰 분배하는 스크립트입니다.
데이터 누수(Leakage)를 방지하기 위해 파일명 접두사(Source ID)를 기준으로 그룹화하여 분할합니다.
"""
import os
import shutil
import random
from pathlib import Path
from tqdm import tqdm

# Config
PROCESSED_ROOT = Path("ai/data/audio/processed/abnormal")
DEST_ROOT = Path("ai/data/audio")
CATEGORIES = ["engine", "brake", "starter"]
SPLIT_RATIO = 0.8  # 80% Train, 20% Test

def clean_and_create(path: Path):
    """Safely clear directory if exists, then recreate"""
    if path.exists():
        # Only delete if it looks like a data dir (safety check)
        if "abnormal" in str(path):
            shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

def main():
    print("🚀 Starting Abnormal Data Distribution...")
    
    total_moved = {"train": 0, "test": 0}

    for category in CATEGORIES:
        src_dir = PROCESSED_ROOT / category
        if not src_dir.exists():
            print(f"⚠️ Source not found: {src_dir}")
            continue

        # Setup destinations
        train_dir = DEST_ROOT / "train" / "abnormal" / category
        test_dir = DEST_ROOT / "test" / "abnormal" / category
        
        print(f"\n📂 Processing {category}...")
        print(f"   Cleaning old data in {train_dir} & {test_dir}...")
        clean_and_create(train_dir)
        clean_and_create(test_dir)

        # Group files by source (prefix before last underscore)
        files = list(src_dir.glob("*.wav"))
        groups = {}
        for f in files:
            # "engine_01_001.wav" -> "engine_01"
            # "engine_long_name_02_005.wav" -> "engine_long_name_02"
            prefix = f.stem.rsplit("_", 1)[0]
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(f)
        
        # Shuffle Groups
        source_keys = list(groups.keys())
        random.shuffle(source_keys)
        
        # Split Groups
        split_idx = int(len(source_keys) * SPLIT_RATIO)
        train_keys = source_keys[:split_idx]
        test_keys = source_keys[split_idx:]
        
        # Flatten to file lists
        train_files = []
        for k in train_keys:
            train_files.extend(groups[k])
            
        test_files = []
        for k in test_keys:
            test_files.extend(groups[k])
        
        print(f"   Found {len(files)} files from {len(source_keys)} sources.")
        print(f"   Sources -> Train: {len(train_keys)}, Test: {len(test_keys)}")
        print(f"   Files   -> Train: {len(train_files)}, Test: {len(test_files)}")

        # Copy
        for f in tqdm(train_files, desc="   Copying Train"):
            shutil.copy2(f, train_dir / f.name)
            total_moved["train"] += 1
            
        for f in tqdm(test_files, desc="   Copying Test"):
            shutil.copy2(f, test_dir / f.name)
            total_moved["test"] += 1

    print(f"\n✅ Distribution Complete (Leakage-Free)!")
    print(f"   Total Train (Abnormal): {total_moved['train']}")
    print(f"   Total Test (Abnormal):  {total_moved['test']}")

if __name__ == "__main__":
    # Ensure random seed for reproducibility (optional)
    random.seed(42)
    main()
