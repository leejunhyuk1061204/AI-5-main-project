import os
import shutil
from pathlib import Path

def filter_core8_labels():
    # 1. 경로 설정
    base_path = Path("/workspace/large_data/yolo/engine")
    subsets = ["train", "valid"]
    
    # 사용자님이 지정하신 8개 핵심 클래스 (기존 인덱스 -> 새 인덱스)
    # 0: ABS_Unit (기존 10)
    # 1: Air_Filter_Cover (기존 9)
    # 2: Battery (기존 1)
    # 3: Brake_Fluid (기존 6)
    # 4: Engine_Cover (기존 15)
    # 5: Engine_Oil_Fill_Cap (기존 7)
    # 6: Radiator (기존 13)
    # 7: Windshield_Wiper_Fluid (기존 3)
    
    mapping = {
        "10": "0", # ABS_Unit
        "9": "1",  # Air_Filter_Cover
        "1": "2",  # Battery
        "6": "3",  # Brake_Fluid
        "15": "4", # Engine_Cover
        "7": "5",  # Engine_Oil_Fill_Cap
        "13": "6", # Radiator
        "3": "7"   # Windshield_Wiper_Fluid
    }
    
    core8_names = [
        "ABS_Unit", "Air_Filter_Cover", "Battery", "Brake_Fluid", 
        "Engine_Cover", "Engine_Oil_Fill_Cap", "Radiator", "Windshield_Wiper_Fluid"
    ]

    for subset in subsets:
        label_dir = base_path / subset / "labels"
        backup_dir = base_path / subset / "labels_backup_26cls"
        
        if not label_dir.exists():
            print(f"[Skip] {label_dir} not found.")
            continue
            
        # 백업 폴더가 없으면 생성하고 기존 라벨 이동
        if not backup_dir.exists():
            print(f"[Backup] Moving original labels to {backup_dir}")
            shutil.move(str(label_dir), str(backup_dir))
            os.makedirs(label_dir, exist_ok=True)
        else:
            print(f"[Info] Backup already exists at {backup_dir}. Filtering from it.")
            os.makedirs(label_dir, exist_ok=True)

        # 백업 폴더에서 파일을 읽어 필터링 후 새 폴더에 저장
        label_files = list(backup_dir.glob("*.txt"))
        count = 0
        for lf in label_files:
            new_lines = []
            with open(lf, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if not parts: continue
                    cls_idx = parts[0]
                    
                    if cls_idx in mapping:
                        # 새로운 번호 부여 후 리스트 추가
                        parts[0] = mapping[cls_idx]
                        new_lines.append(" ".join(parts))
            
            # 필터링된 라벨이 있는 경우만 파일 생성
            if new_lines:
                with open(label_dir / lf.name, 'w') as f:
                    f.write("\n".join(new_lines) + "\n")
                count += 1
        
        print(f"[OK] {subset}: Filtered {count} labels (Subset of 8 core classes).")

    # 2. data_core8.yaml 생성
    yaml_content = f"""path: {base_path.as_posix()}
train: train/images
val: valid/images

names:
"""
    for i, name in enumerate(core8_names):
        yaml_content += f"  {i}: {name}\n"
    
    yaml_path = base_path / "data_core8.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    print(f"[OK] Created new config: {yaml_path}")

if __name__ == "__main__":
    # 이 스크립트를 실행하려면 아래 주석을 풀거나 터미널에서 실행하세요.
    filter_core8_labels()
    print("Script ready. Please review the paths and run manually.")
