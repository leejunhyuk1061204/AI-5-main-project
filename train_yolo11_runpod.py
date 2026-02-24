import os
from ultralytics import YOLO

def train_yolo11_m_core8():
    # 1. 경로 설정 (8개 핵심 클래스 전용 YAML)
    data_yaml = "/workspace/large_data/yolo/engine/data_core8.yaml"
    model_name = "yolo11m.pt"   # Medium 모델
    epochs = 15             # 15에폭으로 설정
    imgsz = 1024
    batch = 16                  # RTX 4090에서 m 모델은 16~24 권장
    device = 0
    
    print(f"🚀 [RunPod] YOLO11m Core-8 Training Started")
    print(f"   Model: {model_name}")
    print(f"   Data: {data_yaml}")
    print(f"   Epochs: {epochs}")
    print(f"   Image Size: {imgsz}")
    print(f"   Batch Size: {batch}")
    
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
        name="yolo11m_core8_ep15_1024",
        exist_ok=True,
        cache=True
    )
    
    print("\n✅ [RunPod] YOLO11m Core-8 Training Complete!")
    print(f"   Best weight saved at: /workspace/AI-5-main-project/runs/detect/yolo11m_core8_ep15_1024/weights/best.pt")

if __name__ == "__main__":
    train_yolo11_m_core8()
