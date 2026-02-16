import os
import glob
from pathlib import Path

# =============================================================================
# [Data Repair] Radiator Thin Box Expansion Script
# [역할] 
# Radiator(ID 11) 박스가 너무 얇은 경우(높이 10% 미만), 
# 모델이 특징을 사전에 학습할 수 있도록 박스를 수직으로 최소 20%까지 확장합니다.
# =============================================================================

base_dir = Path(r"c:\Users\301\AI-5-main-project\ai\data\yolo\engine")
datasets = ["train_merged", "valid_merged", "test_merged"]
TARGET_ID = 11
MIN_HEIGHT = 0.20  # 최소 높이를 이미지의 20%로 설정

print(f"🚀 Fix started: Expanding thin boxes for Class {TARGET_ID} (Radiator)")

for dataset in datasets:
    labels_dir = base_dir / dataset / "labels"
    if not labels_dir.exists(): continue
    
    print(f" - Processing {dataset}...")
    files = list(labels_dir.glob("*.txt"))
    fix_count = 0
    
    for txt_file in files:
        new_lines = []
        modified = False
        
        with open(txt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            parts = line.strip().split()
            if not parts: continue
            
            cid = int(parts[0])
            if cid == TARGET_ID:
                x, y, w, h = map(float, parts[1:])
                
                # [Logic] 높이가 너무 얇으면 확장
                if h < MIN_HEIGHT:
                    # 중심점(y)은 유지하면서 높이만 확장 (이미지 밖으로 나가지 않게 클리핑)
                    h = MIN_HEIGHT
                    # y - h/2 가 0보다 작거나 y + h/2 가 1보다 크면 조정
                    if y - h/2 < 0: y = h/2
                    if y + h/2 > 1: y = 1 - h/2
                    
                    parts[2] = f"{y:.6f}"
                    parts[4] = f"{h:.6f}"
                    modified = True
                    fix_count += 1
            
            new_lines.append(" ".join(parts))
            
        if modified:
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(new_lines))

    print(f"   ✓ {dataset} 완료: {fix_count}개 박스 확장됨.")

print("\n✨ Radiator data repair complete.")
