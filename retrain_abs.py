from ultralytics import YOLO
import torch
from pathlib import Path

def retrain_abs():
    comp_name = "ABS_Unit"
    base_dir = Path(rf"C:\Users\301\Desktop\data\classification\{comp_name}")
    
    # Check GPU
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"\n>>> Retraining {comp_name} on device: {device}")

    model = YOLO('yolov8n-cls.pt')
    
    # Train
    model.train(
        data=str(base_dir),
        epochs=30,
        imgsz=224,
        batch=16,
        device=device,
        project="runs/train_analyze",
        name=f"{comp_name}_retrained",
        exist_ok=True,
        verbose=False
    )
    
    print(f"\n[DONE] Retraining for {comp_name} finished.")

if __name__ == "__main__":
    retrain_abs()
