import cv2
import numpy as np
import os
from pathlib import Path
import random

def augment_image(image):
    augs = []
    # 1. Flips
    augs.append(cv2.flip(image, 1)) # Horizontal
    augs.append(cv2.flip(image, 0)) # Vertical
    
    # 2. Rotations (90, 180, 270)
    for angle in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]:
        augs.append(cv2.rotate(image, angle))
        
    # 3. Brightness/Contrast
    alpha = random.uniform(0.8, 1.2) # Contrast
    beta = random.randint(-30, 30)   # Brightness
    bright_img = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    augs.append(bright_img)
    
    # 4. Blur
    blur_img = cv2.GaussianBlur(image, (5, 5), 0)
    augs.append(blur_img)
    
    return augs

def process_augmentation(comp_name, target_count=200):
    base_dir = Path(rf"C:\Users\301\Desktop\data\classification\{comp_name}\train\abnormal")
    if not base_dir.exists():
        print(f"[ERROR] {base_dir} not found")
        return

    images = list(base_dir.glob("*.jpg")) + list(base_dir.glob("*.png")) + list(base_dir.glob("*.jpeg"))
    if not images:
        print(f"[SKIP] No images found in {base_dir}")
        return

    current_count = len(images)
    print(f"\n>>> Augmenting {comp_name}: Current {current_count} files.")
    
    # If we need more images to reach target
    needed = target_count - current_count
    if needed <= 0:
        print(f"[INFO] Already has {current_count} images. Skipping.")
        return

    aug_per_img = (needed // current_count) + 1
    
    count = 0
    for img_p in images:
        if count >= needed: break
        
        img = cv2.imread(str(img_p))
        if img is None: continue
        
        augmented_list = augment_image(img)
        for i, aug_img in enumerate(augmented_list):
            if count >= needed: break
            save_path = base_dir / f"aug_{img_p.stem}_{i}.jpg"
            cv2.imwrite(str(save_path), aug_img)
            count += 1
            
    print(f"[SUCCESS] {comp_name} augmented. Total files: {len(list(base_dir.glob('*.*')))}")

if __name__ == "__main__":
    for comp in ["Battery", "Brake_Fluid"]:
        process_augmentation(comp, target_count=250)
