"""
[파일 용도] VISC (차량 내부 소음) 데이터 추출
원본 VISC 데이터셋에서 필요한 오디오 파일(ID 기준)을 선별하고, Train/Test 구조에 맞춰 `ai/data/audio`로 복사합니다.
"""
import os
import shutil
import random
from pathlib import Path

# Config
SOURCE_DIR = r"C:\Users\301\Desktop\VISC\VISC Dataset SON"
DEST_ROOT = r"C:\Users\301\AI-5-main-project\ai\data\audio"
TARGET_VIDS = ['3', '4', '7', '8']
LOG_FILE = "extraction_debug.log"

# Total counts requested
TOTAL_TRAIN = 600
TOTAL_TEST = 150

def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def setup_dirs():
    log("Starting setup_dirs...")
    for split in ["train", "test"]:
        path = os.path.join(DEST_ROOT, split, "normal")
        os.makedirs(path, exist_ok=True)
        log(f"✅ Verified directory: {path}")

def get_files_by_vid(source_dir, vids):
    files_by_vid = {vid: [] for vid in vids}
    try:
        all_files = os.listdir(source_dir)
    except Exception as e:
        log(f"Error reading source dir: {e}")
        return files_by_vid
    
    for f in all_files:
        if not f.endswith(".wav"): continue
        
        # Check start with "3 (", "4 (", etc.
        for vid in vids:
            if f.startswith(f"{vid} ("):
                files_by_vid[vid].append(f)
                break
    
    return files_by_vid

def main():
    log("🚀 Starting VISC Data Extraction...")
    setup_dirs()
    
    vid_files = get_files_by_vid(SOURCE_DIR, TARGET_VIDS)
    
    # Calculate per-VID quotas
    num_vids = len(TARGET_VIDS)
    train_per_vid = TOTAL_TRAIN // num_vids  # 600 / 4 = 150
    test_per_vid = TOTAL_TEST // num_vids    # 150 / 4 = 37 (remainder 2)
    
    log(f"📊 Plan per VID: Train={train_per_vid}, Test={test_per_vid}")
    
    total_moved = {"train": 0, "test": 0}
    
    for vid in TARGET_VIDS:
        files = vid_files[vid]
        random.shuffle(files)
        
        total_available = len(files)
        needed = train_per_vid + test_per_vid
        
        if total_available < needed:
            log(f"⚠️ Warning: VID {vid} has only {total_available} files (Need {needed}). Using all avail.")
        
        # Split
        train_files = files[:train_per_vid]
        remain = files[train_per_vid:]
        test_files = remain[:test_per_vid]
        
        # Add remainder to last vid to hit exact total if needed (optional simplicity: just approximate)
        # Verify counts
        log(f"   VID {vid}: Found {total_available} -> Train {len(train_files)}, Test {len(test_files)}")
        
        # Copy
        for f in train_files:
            src = os.path.join(SOURCE_DIR, f)
            dst = os.path.join(DEST_ROOT, "train", "normal", f"visc_{f}") # Prepend visc_ to avoid collisions
            shutil.copy2(src, dst)
            total_moved["train"] += 1
            
        for f in test_files:
            src = os.path.join(SOURCE_DIR, f)
            dst = os.path.join(DEST_ROOT, "test", "normal", f"visc_{f}")
            shutil.copy2(src, dst)
            total_moved["test"] += 1

    log(f"\n✅ Done! Copied Total: Train={total_moved['train']}, Test={total_moved['test']}")

if __name__ == "__main__":
    main()
