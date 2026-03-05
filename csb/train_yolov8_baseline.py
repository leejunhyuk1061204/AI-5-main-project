import os
from ultralytics import YOLO

def train_yolov8_baseline():
    # 1. 설정
    data_yaml = r"C:\Users\301\Desktop\data\yolo\engine\data.yaml"
    model_name = "yolov8n.pt"  # 가장 가벼운 모델 (RTX 3050 최적화)
    epochs = 100
    imgsz = 640                # RTX 3050 6GB 고려 (1280은 OOM 위험)
    batch = 16                 # imgsz 640에서는 16 가능
    device = 0                 # GPU 0
    
    print(f"🚀 YOLOv8 Baseline Training Started")
    print(f"   Model: {model_name}")
    print(f"   Data: {data_yaml}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch: {batch}")
    print(f"   Image Size: {imgsz}")
    
    # 데이터 확인
    if not os.path.exists(data_yaml):
        print(f"[Error] data.yaml not found at {data_yaml}")
        return

    # 2. 모델 로드
    model = YOLO(model_name)
    
    # 3. 학습 시작
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project="runs/detect",
        name="yolov8_baseline",
        exist_ok=True,
        cache=True    # RAM 캐싱으로 속도 향상
    )
    
    print("\n✅ YOLOv8 Baseline Training Complete!")
    print(f"   Best weight saved at: runs/detect/yolov8_baseline/weights/best.pt")

if __name__ == "__main__":
    train_yolov8_baseline()
