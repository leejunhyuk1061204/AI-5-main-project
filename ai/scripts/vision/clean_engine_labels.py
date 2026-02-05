import os
import glob

def clean_labels(data_root, target_indices):
    """
    Removes lines starting with any of the target_indices from YOLO label files.
    This safely 'hides' classes from the model without changing the index structure.
    """
    print(f"🚀 Cleaning labels in: {data_root}")
    print(f"   Indices to be excluded (data remains 0): {target_indices}")
    
    # Target all txt files in train/valid/test labels
    label_files = glob.glob(os.path.join(data_root, "**", "labels", "*.txt"), recursive=True)
    print(f"   Found {len(label_files)} label files.")
    
    removed_count = 0
    modified_files = 0
    
    for file_path in label_files:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        file_modified = False
        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue
            
            try:
                class_idx = int(parts[0])
                if class_idx in target_indices:
                    file_modified = True
                    removed_count += 1
                else:
                    new_lines.append(line)
            except (ValueError, IndexError):
                # Skip invalid lines
                continue
        
        if file_modified:
            with open(file_path, 'w') as f:
                f.writelines(new_lines)
            modified_files += 1

    print(f"\n✅ Engine label cleaning complete!")
    print(f"   Modified Files: {modified_files}")
    print(f"   Labels Removed: {removed_count}")

if __name__ == "__main__":
    # Correct path relative to project root
    ENGINE_DATA_ROOT = "ai/data/yolo/engine"
    EXCLUDED_INDICES = [14, 17, 22, 24]
    
    if os.path.exists(ENGINE_DATA_ROOT):
        clean_labels(ENGINE_DATA_ROOT, EXCLUDED_INDICES)
    else:
        print(f"[Error] Directory not found: {ENGINE_DATA_ROOT}")
        print("Please run this script from the project root.")
