from ultralytics import YOLO
import torch
from pathlib import Path

def train_component(comp_name):
    base_dir = Path(rf"C:\Users\301\Desktop\data\classification\{comp_name}")
    
    # Check GPU
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"\n>>> Training {comp_name} on device: {device}")

    # Use yolov8n-cls as base
    model = YOLO('yolov8n-cls.pt')
    
    # Train
    results = model.train(
        data=str(base_dir),
        epochs=50,
        imgsz=224,
        batch=16,
        device=device,
        project="runs/train_analyze",
        name=f"{comp_name}_v7_final",
        exist_ok=True,
        verbose=False
    )
    
    print(f"\n[DONE] Training for {comp_name} finished.")
    return results

if __name__ == "__main__":
    # Components that significantly updated with real-world like data
    components = ["ABS_Unit", "Engine_Cover", "Battery", "Brake_Fluid"]
    for comp in components:
        train_component(comp)
