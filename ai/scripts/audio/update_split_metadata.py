"""
[파일 용도] 메타데이터 분할 정보 업데이트
`split_dataset.py` 실행 후, 원본 `metadata.csv` 내용을 바탕으로 Train/Test 폴더 구조에 맞게 경로 정보를 갱신합니다.
"""
import os
import csv
import librosa
from pathlib import Path
from tqdm import tqdm

DATA_ROOT = Path("ai/data/audio")

def get_audio_info(file_path):
    try:
        # Just get duration and SR
        # Use librosa.get_duration if possible to be faster, but load is safer for validity
        y, sr = librosa.load(file_path, sr=None)
        return len(y) / sr, sr
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0.0, 0

def scan_and_create_csv(split):
    split_dir = DATA_ROOT / split
    if not split_dir.exists():
        print(f"Skipping {split} (not found)")
        return

    print(f"Scanning {split}...")
    rows = []
    
    # We expect: normal/*.wav AND abnormal/{category}/*.wav
    
    # Normal - SKIPPED as per user request
    # normal_dir = split_dir / "normal"
    # if normal_dir.exists():
    #     for f in tqdm(list(normal_dir.glob("*.wav")), desc=f"{split}/normal"):
    #         dur, sr = get_audio_info(f)
    #         rows.append({
    #             "file_name": f.name,
    #             "split": split,
    #             "label": "normal",
    #             "subcategory": "none",
    #             "duration": round(dur, 2),
    #             "sample_rate": sr
    #         })

    # Abnormal
    abnormal_dir = split_dir / "abnormal"
    if abnormal_dir.exists():
        for sub in ["engine", "brake", "starter"]:
            sub_dir = abnormal_dir / sub
            if sub_dir.exists():
                for f in tqdm(list(sub_dir.glob("*.wav")), desc=f"{split}/abnormal/{sub}"):
                    dur, sr = get_audio_info(f)
                    rows.append({
                        "file_name": f.name,
                        "split": split,
                        "label": "abnormal",
                        "subcategory": sub,
                        "duration": round(dur, 2),
                        "sample_rate": sr
                    })
    
    # Save
    csv_path = split_dir / "metadata.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_name", "split", "label", "subcategory", "duration", "sample_rate"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Saved {csv_path} with {len(rows)} entries.")

def main():
    scan_and_create_csv("train")
    scan_and_create_csv("test")

if __name__ == "__main__":
    main()
