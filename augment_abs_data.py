import cv2
import numpy as np
import os
from pathlib import Path
import random

def augment_images(input_dir, output_dir, multiplier=10):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    images = list(input_path.glob("user_abnormal_*.png"))
    if not images:
        print("No user images found to augment.")
        return

    print(f"Augmenting {len(images)} images...")

    for img_p in images:
        img = cv2.imread(str(img_p))
        if img is None: continue
        
        base_name = img_p.stem
        
        for i in range(multiplier):
            aug_img = img.copy()
            
            # 1. Random Flip
            if random.random() > 0.5:
                aug_img = cv2.flip(aug_img, 1)
            
            # 2. Random Rotation
            angle = random.uniform(-15, 15)
            h, w = aug_img.shape[:2]
            M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1.0)
            aug_img = cv2.warpAffine(aug_img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
            
            # 3. Random Brightness/Contrast
            alpha = random.uniform(0.8, 1.2) # Contrast
            beta = random.uniform(-20, 20)   # Brightness
            aug_img = cv2.convertScaleAbs(aug_img, alpha=alpha, beta=beta)
            
            # 4. Blur (optional)
            if random.random() > 0.7:
                k = random.choice([3, 5])
                aug_img = cv2.GaussianBlur(aug_img, (k, k), 0)

            save_name = f"{base_name}_aug_{i}.jpg"
            cv2.imwrite(str(output_path / save_name), aug_img)
            
    print(f"Saved augmented images to {output_dir}")

if __name__ == "__main__":
    target_dir = r"C:\Users\301\Desktop\data\classification\ABS_Unit\train\abnormal"
    augment_images(target_dir, target_dir, multiplier=12)
