import os
import shutil
import random
from pathlib import Path

# 원본 데이터 경로 (PatchCore용 구조)
SOURCE_ROOT = Path(r"C:\Users\301\Desktop\data\anomaly")
# 타겟 데이터 경로 (YOLOv8-cls용 구조)
TARGET_ROOT = Path(r"C:\Users\301\Desktop\data\classification")

# 부품명과 실제 데이터 폴더 매핑 (코드상 이름 -> 실제 폴더 이름)
PART_MAPPING = {
    "ABS_Unit": "ABS_Unit", 
    "Air_Filter_Cover": "Cold_Air_Intake", # 매핑 적용
    "Battery": "Battery", 
    "Brake_Fluid": "Brake_Fluid", 
    "Engine_Oil_Fill_Cap": "Oil_Filter_Housing", # 매핑 적용
    "Radiator": "Radiator", 
    "Engine_Cover": "Engine_Cover", 
    "Windshield_Wiper_Fluid": "Engine_Coolant_Reservoir" # 매핑 적용
}

def prepare_dataset():
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    
    print(f"Preparing YOLOv8-cls dataset at {TARGET_ROOT}...")
    
    for part_name, source_folder in PART_MAPPING.items():
        print(f"Processing {part_name} (Source: {source_folder})...")
        
        # 1. 소스 경로 설정 (train/test 모두 탐색하여 통합)
        # PatchCore 구조: data/anomaly/{source_folder}/train/good, data/anomaly/{source_folder}/test/bad 등
        
        good_images = []
        bad_images = []
        
        for split in ["train", "test"]:
            src_good_dir = SOURCE_ROOT / source_folder / split / "good"
            src_bad_dir = SOURCE_ROOT / source_folder / split / "bad"
            
            if src_good_dir.exists():
                good_images.extend(list(src_good_dir.glob("*.jpg")) + list(src_good_dir.glob("*.png")))
            
            if src_bad_dir.exists():
                bad_images.extend(list(src_bad_dir.glob("*.jpg")) + list(src_bad_dir.glob("*.png")))
        
        if not bad_images:
            print(f"  [Skipped] No 'bad' images found for {part_name} (checked train/test)")
            continue
            
        if not good_images:
            print(f"  [Warning] No 'good' images found for {part_name}. Only 'bad' images will be processed.")
            
        # 3. 데이터 분할 (Train:Val = 8:2)
        random.shuffle(good_images)
        random.shuffle(bad_images)
        
        train_good = good_images[:int(len(good_images)*0.8)]
        val_good = good_images[int(len(good_images)*0.8):]
        
        train_bad = bad_images[:int(len(bad_images)*0.8)]
        val_bad = bad_images[int(len(bad_images)*0.8):]

        
        # 4. 타겟 폴더로 복사
        # 구조: classification/{part_name}/train/normal, classification/{part_name}/train/abnormal
        
        # Train
        train_normal_dir = TARGET_ROOT / part_name / "train" / "normal"
        train_abnormal_dir = TARGET_ROOT / part_name / "train" / "abnormal"
        train_normal_dir.mkdir(parents=True, exist_ok=True)
        train_abnormal_dir.mkdir(parents=True, exist_ok=True)
        
        for img in train_good:
            shutil.copy(img, train_normal_dir / img.name)
        for img in train_bad:
            shutil.copy(img, train_abnormal_dir / img.name)
            
        # Val
        val_normal_dir = TARGET_ROOT / part_name / "val" / "normal"
        val_abnormal_dir = TARGET_ROOT / part_name / "val" / "abnormal"
        val_normal_dir.mkdir(parents=True, exist_ok=True)
        val_abnormal_dir.mkdir(parents=True, exist_ok=True)
        
        for img in val_good:
            shutil.copy(img, val_normal_dir / img.name)
        for img in val_bad:
            shutil.copy(img, val_abnormal_dir / img.name)
            
        print(f"  - Train: Normal={len(train_good)}, Abnormal={len(train_bad)}")
        print(f"  - Val  : Normal={len(val_good)}, Abnormal={len(val_bad)}")

    print("\nDataset preparation completed!")

if __name__ == "__main__":
    prepare_dataset()
