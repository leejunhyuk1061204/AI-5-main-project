import os
import shutil
import random
from pathlib import Path

def redistribute_dataset():
    base_path = Path(r"C:\Users\301\Desktop\data\classification\ABS_Unit")
    
    # 1. Collect all images
    all_files = {'normal': [], 'abnormal': []}
    
    for folder in ['train', 'val', 'test']:
        for cls in ['normal', 'abnormal']:
            cls_path = base_path / folder / cls
            if cls_path.exists():
                files = [f for f in cls_path.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.png', '.jpeg']]
                all_files[cls].extend(files)
                print(f"Collected {len(files)} files from {folder}/{cls}")

    # 2. Shuffle and redistribute
    for cls, files in all_files.items():
        random.seed(42) # For reproducibility
        random.shuffle(files)
        
        total = len(files)
        train_end = int(total * 0.8)
        val_end = train_end + int(total * 0.1)
        
        splits = {
            'train': files[:train_end],
            'val': files[train_end:val_end],
            'test': files[val_end:]
        }
        
        print(f"\nTarget splits for {cls} (total {total}):")
        for folder, split_files in splits.items():
            print(f"  {folder}: {len(split_files)} files")
            
            target_dir = base_path / folder / cls
            os.makedirs(target_dir, exist_ok=True)
            
            for f in split_files:
                target_path = target_dir / f.name
                # Ensure we don't try to move file to itself
                if f != target_path:
                    # If target exists and is different from source, it's safer to rename or overwrite
                    # In this case, we know they are the same images being shuffled across subfolders
                    shutil.move(str(f), str(target_path))

    # 3. Cleanup cache files
    for cache in base_path.glob("*.cache"):
        print(f"Removing cache: {cache}")
        os.remove(cache)

if __name__ == "__main__":
    redistribute_dataset()
