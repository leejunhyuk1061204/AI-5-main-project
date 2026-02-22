
import os
from pathlib import Path
from collections import Counter

DATA_ROOT = Path("ai/data/audio")
TRAIN_DIR = DATA_ROOT / "train"
TEST_DIR = DATA_ROOT / "test"

def count_files(directory):
    if not directory.exists():
        return {}
    
    counts = Counter()
    # Normal
    normal_dir = directory / "normal"
    if normal_dir.exists():
        counts["normal"] = len(list(normal_dir.glob("*.wav")))
        
    # Abnormal
    abnormal_dir = directory / "abnormal"
    if abnormal_dir.exists():
        for cls in ["starter", "engine", "brake"]:
            cls_dir = abnormal_dir / cls
            if cls_dir.exists():
                counts[cls] = len(list(cls_dir.glob("*.wav")))
                
    return counts

print("📊 Dataset Statistics")
print("=" * 40)

# Train
train_counts = count_files(TRAIN_DIR)
print(f"🔹 Train Set: {sum(train_counts.values())}")
for cls, count in train_counts.items():
    print(f"   - {cls:<10}: {count}")

print("-" * 40)

# Test
test_counts = count_files(TEST_DIR)
print(f"🔹 Test Set: {sum(test_counts.values())}")
for cls, count in test_counts.items():
    print(f"   - {cls:<10}: {count}")

print("=" * 40)
total_all = sum(train_counts.values()) + sum(test_counts.values())
print(f"🏆 Total Audio Files: {total_all}")
