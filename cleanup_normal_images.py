
import os
from pathlib import Path

# 대상 부품 목록 (혹시 모를 오동작 방지 위해 한정)
TARGET_PARTS = [
    "ABS_Unit",
    "Air_Filter_Cover",
    "Battery",
    "Brake_Fluid",
    "Engine_Oil_Fill_Cap",
    "Radiator",
    "Engine_Cover",
    "Windshield_Wiper_Fluid"
]

def clean_normal_images():
    base_path = Path(r"C:\Users\301\Desktop\bad\bad")
    
    if not base_path.exists():
        print("Path not found.")
        return

    deleted_count = 0
    kept_count = 0

    for part in TARGET_PARTS:
        part_dir = base_path / part
        if not part_dir.exists():
            continue
            
        print(f"Cleaning {part}...")
        
        # 모든 파일 검사
        for file_path in part_dir.iterdir():
            if file_path.is_file():
                # 'abnormal'이나 'defect'가 포함되지 않은 파일은 정상 이미지로 간주하고 삭제
                if "abnormal" not in file_path.name and "defect" not in file_path.name:
                    try:
                        os.remove(file_path)
                        print(f"  Deleted: {file_path.name}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"  Error deleting {file_path.name}: {e}")
                else:
                    kept_count += 1
                    
    print(f"\nCleanup Finished.")
    print(f"- Deleted (Normal): {deleted_count}")
    print(f"- Kept (Abnormal/Defect): {kept_count}")

if __name__ == "__main__":
    clean_normal_images()
