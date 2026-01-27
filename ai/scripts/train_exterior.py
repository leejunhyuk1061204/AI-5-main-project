from ultralytics import YOLO
import argparse
import os

def train_exterior_model(mode="train", epochs=10, batch_size=16, device=0):
    """
    Train or Evaluate YOLOv8 model for unified exterior damage detection (22 classes).
    """
    # 1. Project Setup
    project_path = os.path.join("ai", "weights", "exterior", "unified_v1")
    data_yaml = os.path.join("ai", "data", "yolo", "exterior", "data.yaml")
    
    # Ensure yaml exists
    if not os.path.exists(data_yaml):
        print(f"[Error] No data.yaml found at: {data_yaml}")
        return

    # 2. Mode Selection
    if mode == "train":
        print(f"\n🚀 Starting YOLOv8 Training for Exterior Damage (22 Classes)")
        print(f"   Data: {data_yaml}")
        print(f"   Output: {project_path}")
        print(f"   Epochs: {epochs}")
        print(f"   Batch: {batch_size}")
        
        # Load Model (Nano version)
        model = YOLO("yolov8n.pt") 
        
        # Train
        model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=640,
            batch=batch_size,
            device=device,
            project=project_path,
            name="train",
            exist_ok=True, 
            plots=True,
            cache=False, 
            workers=0  # Fix for WinError 1455
        )
        print(f"\n✅ Training Completed. Best weights saved at: {project_path}/train/weights/best.pt")
        
    elif mode == "val":
        print(f"\n🔍 Starting YOLOv8 Validation (Baseline Check)")
        
        # Check if trained weights exist, otherwise use base model (Baseline)
        best_weights = os.path.join(project_path, "train", "weights", "best.pt")
        if os.path.exists(best_weights):
            print(f"   Loading Trained Weights: {best_weights}")
            model = YOLO(best_weights)
        else:
            print(f"   ⚠️ [주의] 학습된 가중치가 없어 'yolov8n.pt' (COCO Base)를 사용합니다.")
            print(f"   ⚠️ 이 모델은 COCO 데이터셋(80개 클래스) 기준이므로, 현재 데이터셋(22개)과 클래스가 일치하지 않습니다.")
            print(f"   ⚠️ 따라서 Baseline 점수는 0에 수렴하거나, 엉뚱한 클래스명(Person 등)이 표시될 수 있습니다.")
            model = YOLO("yolov8n.pt")
            
        # Validate
        metrics = model.val(data=data_yaml, split="val", workers=0)
        print(f"\n📊 Validation Results: {metrics.box.map}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train", choices=["train", "val"], help="train or val")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()
    
    train_exterior_model(mode=args.mode, epochs=args.epochs, batch_size=args.batch)
