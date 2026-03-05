import os
from ultralytics import YOLO

def train_yolo11_core8():
    # 1. 경로 설정 (필터링된 8개 클래스용 YAML)
    data_yaml = "/workspace/large_data/yolo/engine/data_core8.yaml"
    model_name = "yolo11m.pt"
    epochs = 100                # 성능 극대화를 위해 100 에폭 권장
    imgsz = 1280
    batch = 16                 # RTX 4090 안정성 고려
    device = 0
    
    print(f"🚀 [RunPod] YOLO11 Core-8 Training Started")
    print(f"   Model: {model_name}")
    print(f"   Data: {data_yaml}")
    print(f"   Epochs: {epochs}")
    print(f"   Image Size: {imgsz}")
    
    # 2. 모델 로드
    model = YOLO(model_name)
    
    # 3. 학습 시작
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project="/workspace/AI-5-main-project/runs/detect",
        name="yolo11_core8_optimization",
        exist_ok=True,
        cache=True
    )
    
    print("\n✅ [RunPod] Core-8 Training Complete!")
    print(f"   Best weight saved at: /workspace/AI-5-main-project/runs/detect/yolo11_core8_optimization/weights/best.pt")

if __name__ == "__main__":
    train_yolo11_core8()
