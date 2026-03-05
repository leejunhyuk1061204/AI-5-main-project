from ultralytics import YOLO
import os
from pathlib import Path

def final_test():
    model_path = r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze\ABS_Unit_v7_final\weights\best.pt"
    if not os.path.exists(model_path):
        print(f"Model path error: {model_path}")
        return

    model = YOLO(model_path)
    threshold = 0.3 # Safety-first threshold
    
    # User's recent media files
    media_dir = Path(r"C:\Users\301\.gemini\antigravity\brain\0e32816b-b4c3-4fd3-a5ce-f742dc7e5c6c")
    user_imgs = [
        media_dir / "media__1771655717659.png",
        media_dir / "media__1771655728479.png",
        media_dir / "media__1771655730459.png"
    ]

    print("\n" + "="*50)
    print(f"USER UPLOADED ABS_UNIT TEST RESULTS (Threshold: {threshold})")
    print("="*50)

    for i, p in enumerate(user_imgs):
        if not p.exists():
            print(f"Image {i+1}: File Not Found ({p.name})")
            continue
            
        res = model.predict(str(p), verbose=False)[0]
        # Class mapping: model.names might be {0: 'abnormal', 1: 'normal'}
        # But we check the probability for 'abnormal' index directly
        prob_abnormal = res.probs.data[0].item() 
        
        status = "🔴 ABNORMAL (DEFECT)" if prob_abnormal >= threshold else "🟢 NORMAL"
        
        print(f"Image {i+1} ({p.name}):")
        print(f"  - Decision: {status}")
        print(f"  - Abnormal Prob: {prob_abnormal:.4f}")
        print("-" * 50)
    print("="*50)

if __name__ == "__main__":
    final_test()
