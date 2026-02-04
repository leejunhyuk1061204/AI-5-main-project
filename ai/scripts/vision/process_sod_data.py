# ai/scripts/process_sod_data.py
"""
CarDD-SOD 비정형 데이터를 YOLO Segmentation 학습 포맷으로 변환하는 스크립트

[설기]
1. SOD 데이터(`CarDD-SOD`)는 바이너리 마스크(PNG) 형태입니다.
2. YOLOv8-Seg 모델 학습을 위해 이를 `[class_id x1 y1 x2 y2 ...]` 형태의 텍스트 파일로 변환합니다.
3. 변환된 데이터는 `ai/data/yolo/exterior/sod` 에 저장됩니다.
"""

import cv2
import os
import numpy as np
from tqdm import tqdm
from pathlib import Path

def mask_to_yolo_polygons(mask_path, class_id=0):
    """PNG 마스크를 YOLO 폴리곤 좌표로 변환"""
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return []
        
    # 컨투어 추출
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    h, w = mask.shape
    polygons = []
    
    for contour in contours:
        if len(contour) < 3:  # 최소 3개의 점 필요
            continue
            
        # 정규화 (0~1)
        poly = contour.reshape(-1, 2).astype(float)
        poly[:, 0] /= w
        poly[:, 1] /= h
        
        # YOLO 포맷 문자열 생성
        poly_str = " ".join([f"{x:.6f} {y:.6f}" for x, y in poly])
        polygons.append(f"{class_id} {poly_str}")
        
    return polygons

def process_sod_dataset(root_dir, output_dir):
    """SOD 데이터셋 전체 변환"""
    root_path = Path(root_dir)
    output_path = Path(output_dir)
    
    # split 정의 (TR, VAL, TE)
    splits = {
        "CarDD-TR": "train",
        "CarDD-VAL": "val",
        "CarDD-TE": "test"
    }
    
    for sod_split, yolo_split in splits.items():
        src_mask_dir = root_path / sod_split / f"{sod_split}-Mask"
        src_img_dir = root_path / sod_split / f"{sod_split}-Image"
        
        if not src_mask_dir.exists():
            print(f"[Skip] {src_mask_dir} 가 존재하지 않습니다.")
            continue
            
        # 출력 디렉토리 생성
        out_img_dir = output_path / yolo_split / "images"
        out_lbl_dir = output_path / yolo_split / "labels"
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing {sod_split} -> {yolo_split}...")
        masks = list(src_mask_dir.glob("*.png"))
        
        for mask_file in tqdm(masks):
            # 1. 이미지 복사/이동 (또는 심볼릭 링크) -> 여기서는 복사 권장
            img_file = src_img_dir / mask_file.with_suffix(".jpg").name
            if img_file.exists():
                os.system(f"copy /Y {str(img_file)} {str(out_img_dir / img_file.name)} >nul")
            
            # 2. 마스크 변환 및 저장
            polygons = mask_to_yolo_polygons(mask_file)
            if polygons:
                lbl_file = out_lbl_dir / mask_file.with_suffix(".txt").name
                with open(lbl_file, "w") as f:
                    f.write("\n".join(polygons))

    # data.yaml 생성
    yaml_content = f"""
path: ./exterior/sod
train: train/images
val: val/images
test: test/images

names:
  0: damage
"""
    with open(output_path / "data.yaml", "w") as f:
        f.write(yaml_content.strip())
    print(f"\n[✓] 변환 완료! data.yaml 생성됨: {output_path / 'data.yaml'}")

if __name__ == "__main__":
    SOD_ROOT = "ai/data/CarDD_release/CarDD_SOD"
    OUTPUT_ROOT = "ai/data/yolo/exterior/sod"
    process_sod_dataset(SOD_ROOT, OUTPUT_ROOT)
