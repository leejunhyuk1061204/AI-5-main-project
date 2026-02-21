import cv2
import numpy as np
import os
from pathlib import Path
import random

def extract_and_blend_robust():
    base_dir = Path(r"C:\Users\301\Desktop\AI-5-main-project")
    brain_dir = Path(r"C:\Users\301\.gemini\antigravity\brain\0e32816b-b4c3-4fd3-a5ce-f742dc7e5c6c")
    normal_dir = Path(r"C:\Users\301\Desktop\data\classification\ABS_Unit\train\normal")
    output_dir = Path(r"C:\Users\301\Desktop\data\classification\ABS_Unit\train\abnormal")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    source_paths = [
        brain_dir / "media__1771655717659.png",
        brain_dir / "media__1771655728479.png",
        brain_dir / "media__1771655730459.png"
    ]
    
    sources = [cv2.imread(str(p)) for p in source_paths if p.exists()]
    if not sources: return

    normal_files = list(normal_dir.glob("*.jpg")) + list(normal_dir.glob("*.png"))
    
    for idx, norm_p in enumerate(normal_files):
        target = cv2.imread(str(norm_p))
        if target is None: continue
        
        # Pick random source
        src_idx = random.randint(0, len(sources) - 1)
        src = sources[src_idx]
        
        # Simple color target for mask
        if src_idx == 1: # Leak
            mask = cv2.inRange(cv2.cvtColor(src, cv2.COLOR_BGR2HSV), (10, 50, 20), (40, 255, 150))
        else: # Corrosion
            mask = cv2.inRange(cv2.cvtColor(src, cv2.COLOR_BGR2HSV), (0, 0, 150), (180, 50, 255))
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_cnts = [c for c in contours if cv2.contourArea(c) > 500]
        
        if not valid_cnts: continue
        
        # Apply 2-3 textures
        for _ in range(random.randint(1, 3)):
            cnt = random.choice(valid_cnts)
            x, y, w, h = cv2.boundingRect(cnt)
            
            patch = src[y:y+h, x:x+w]
            p_mask = mask[y:y+h, x:x+w]
            
            # Target size (randomize)
            tw = int(w * random.uniform(0.5, 1.2))
            th = int(h * random.uniform(0.5, 1.2))
            
            # Constrain to target bounds
            tw = min(tw, target.shape[1] // 2)
            th = min(th, target.shape[0] // 2)
            
            patch = cv2.resize(patch, (tw, th))
            p_mask = cv2.resize(p_mask, (tw, th))
            
            # Target location
            tx = random.randint(0, target.shape[1] - tw)
            ty = random.randint(0, target.shape[0] - th)
            
            # Blending
            alpha = random.uniform(0.5, 0.9)
            roi = target[ty:ty+th, tx:tx+tw]
            
            inv_mask = cv2.merge([p_mask, p_mask, p_mask]) / 255.0
            blended = (roi * (1 - inv_mask * alpha) + patch * (inv_mask * alpha)).astype(np.uint8)
            target[ty:ty+th, tx:tx+tw] = blended

        cv2.imwrite(str(output_dir / f"texture_v2_{idx}.jpg"), target)
    
    print(f"Generated {len(normal_files)} high-quality textures.")

if __name__ == "__main__":
    extract_and_blend_robust()
