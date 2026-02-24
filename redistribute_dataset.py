import os
import shutil
import random
from pathlib import Path
import tempfile

def redistribute_data(component_name, split_ratio=(0.8, 0.1, 0.1)):
    base_dir = Path(rf"C:\Users\301\Desktop\data\classification\{component_name}")
    classes = ["normal", "abnormal"]
    
    for cls in classes:
        train_path = base_dir / "train" / cls
        val_path = base_dir / "val" / cls
        test_path = base_dir / "test" / cls
        
        # 1. Collect all images and copy to a temporary buffer
        all_files_snapshot = []
        for p in [train_path, val_path, test_path]:
            if p.exists():
                all_files_snapshot.extend([f for f in p.glob("*.*") if f.is_file()])
        
        if not all_files_snapshot:
            print(f"[SKIP] No files found for {component_name}/{cls}")
            continue

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            buffered_files = []
            
            for f in all_files_snapshot:
                tmp_f = temp_path / f.name
                # Handle potential name collisions if same name exists in different folders
                if tmp_f.exists():
                    tmp_f = temp_path / f"{f.stem}_{random.getrandbits(32)}{f.suffix}"
                shutil.copy2(f, tmp_f)
                buffered_files.append(tmp_f)
                
            # 2. Clear target folders
            for p in [train_path, val_path, test_path]:
                if p.exists():
                    for f in p.glob("*"):
                        if f.is_file(): f.unlink()
                else:
                    p.mkdir(parents=True, exist_ok=True)
                    
            # 3. Shuffle and Split
            random.seed(42)
            random.shuffle(buffered_files)
            
            total = len(buffered_files)
            train_end = int(total * split_ratio[0])
            val_end = train_end + int(total * split_ratio[1])
            
            splits = {
                "train": buffered_files[:train_end],
                "val": buffered_files[train_end:val_end],
                "test": buffered_files[val_end:]
            }
            
            # 4. Move from buffer to targets
            for split_name, files in splits.items():
                target_p = base_dir / split_name / cls
                for f in files:
                    shutil.move(str(f), str(target_p / f.name))
                    
            print(f"[SUCCESS] {component_name}/{cls}: Total {total} -> Train: {len(splits['train'])}, Val: {len(splits['val'])}, Test: {len(splits['test'])}")

if __name__ == "__main__":
    for comp in ["Engine_Cover", "ABS_Unit", "Battery", "Brake_Fluid"]:
        redistribute_data(comp)
