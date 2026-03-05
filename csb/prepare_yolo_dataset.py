import os
import shutil
import random
from pathlib import Path

def prepare_yolo_dataset():
    base_path = Path(r"C:\Users\301\Desktop\data\yolo\engine")
    valid_path = base_path / "valid"
    train_path = base_path / "train"
    
    # 클래스 리스트 (ai/scripts/utils/sync_active_learning.py 기준)
    classes = [
        "Inverter_Coolant_Reservoir", "Battery", "Radiator_Cap", "Windshield_Wiper_Fluid", "Fuse_Box",
        "Power_Steering_Reservoir", "Brake_Fluid", "Engine_Oil_Fill_Cap", "Engine_Oil_Dip_Stick", "Air_Filter_Cover",
        "ABS_Unit", "Alternator", "Engine_Coolant_Reservoir", "Radiator", "Air_Filter", "Engine_Cover",
        "Cold_Air_Intake", "Clutch_Fluid_Reservoir", "Transmission_Oil_Dip_Stick", "Intercooler_Coolant_Reservoir",
        "Oil_Filter_Housing", "ATF_Oil_Reservoir", "Cabin_Air_Filter_Housing", "Secondary_Coolant_Reservoir",
        "Electric_Motor", "Oil_Filter"
    ]
    
    print(f"Starting YOLO dataset preparation at: {base_path}")
    
    # 1. train 폴더가 없는 경우 valid에서 분할
    if not train_path.exists():
        print("   [Info] train directory not found. Splitting valid directory (80/20).")
        os.makedirs(train_path / "images", exist_ok=True)
        os.makedirs(train_path / "labels", exist_ok=True)
        
        images = list((valid_path / "images").glob("*.jpg"))
        random.seed(42)
        random.shuffle(images)
        
        split_idx = int(len(images) * 0.8)
        train_images = images[:split_idx]
        
        for img in train_images:
            # Move images
            shutil.move(str(img), str(train_path / "images" / img.name))
            # Move labels
            label_name = img.stem + ".txt"
            label_src = valid_path / "labels" / label_name
            if label_src.exists():
                shutil.move(str(label_src), str(train_path / "labels" / label_name))
        
        print(f"   [OK] Moved {len(train_images)} images to train.")
        print(f"   [OK] {len(images) - len(train_images)} images remaining in valid.")

    # 2. data.yaml 생성
    yaml_content = f"""path: {base_path.as_posix()}
train: train/images
val: valid/images

names:
"""
    for i, name in enumerate(classes):
        yaml_content += f"  {i}: {name}\n"
    
    yaml_path = base_path / "data.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    
    print(f"   [OK] Created data.yaml at: {yaml_path}")
    
    # 3. 프로젝트 내부 (ai/data/yolo/engine) 에도 복사 (train_engine.py 호환성)
    target_yaml_dir = Path(r"C:\Users\301\Desktop\AI-5-main-project\ai\data\yolo\engine")
    os.makedirs(target_yaml_dir, exist_ok=True)
    shutil.copy(str(yaml_path), str(target_yaml_dir / "data.yaml"))
    
    print(f"   [OK] Copied data.yaml to project locally.")

if __name__ == "__main__":
    prepare_yolo_dataset()
