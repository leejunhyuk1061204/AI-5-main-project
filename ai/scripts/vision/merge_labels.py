import os
from pathlib import Path

def merge_yolo_labels(source_dir, target_dir, mapping):
    src_path = Path(source_dir)
    dst_path = Path(target_dir)
    
    if not dst_path.exists():
        dst_path.mkdir(parents=True, exist_ok=True)

    label_files = list(src_path.glob("*.txt"))
    print(f"[{src_path.parent.name}] Processing {len(label_files)} files...")
    
    for lb in label_files:
        target = dst_path / lb.name
        new_lines = []
        with open(lb, 'r') as f:
            for line in f:
                parts = line.split()
                if not parts: continue
                try:
                    cid = int(parts[0])
                    if cid in mapping:
                        new_lines.append(f"{mapping[cid]} {' '.join(parts[1:])}")
                except: continue
        
        with open(target, 'w') as f:
            f.write("\n".join(new_lines) + "\n" if new_lines else "")

if __name__ == "__main__":
    print("🚀 TARGETING 8-CLASS CONSOLIDATION...")
    
    # 0: Cooling, 1: Oil, 2: Electrical, 3: Air, 4: Brake, 5: Power, 6: Wiper, 7: Cover
    GROUP_MAP = {
        0: 0, 12: 0, 13: 0, 2: 0, 19: 0, 23: 0, 21: 0,
        7: 1, 8: 1, 18: 1, 20: 1, 25: 1,
        1: 2, 4: 2, 11: 2, 10: 2,
        9: 3, 16: 3,
        6: 4, 5: 5, 3: 6, 15: 7
    }

    base = Path("ai/data/yolo/engine")
    for split in ["train", "valid", "test"]:
        src = base / split / "labels"
        dst = base / f"{split}_merged" / "labels"
        if src.exists():
            merge_yolo_labels(src, dst, GROUP_MAP)
        else:
            print(f"❌ Missing split: {src}")
    
    print("✅ MERGE COMPLETE.")
