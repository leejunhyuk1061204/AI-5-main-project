import os
from pathlib import Path

def check_anomaly_data(root_path):
    print(f"{'Part Name':<30} | {'Good (Train)':<12} | {'Good (Test)':<12} | {'Defect (Test)':<12}")
    print("-" * 75)
    
    root = Path(root_path)
    if not root.exists():
        print(f"Path not found: {root_path}")
        return

    for part in sorted([d for d in root.iterdir() if d.is_dir()]):
        train_good = len(list((part / "train" / "good").glob("*"))) if (part / "train" / "good").exists() else 0
        test_good = len(list((part / "test" / "good").glob("*"))) if (part / "test" / "good").exists() else 0
        test_defect = len(list((part / "test" / "defect").glob("*"))) if (part / "test" / "defect").exists() else 0
        
        print(f"{part.name:<30} | {train_good:<12} | {test_good:<12} | {test_defect:<12}")

if __name__ == "__main__":
    check_anomaly_data("ai/data/anomaly")
