import os
from ultralytics import YOLO

def train_yolov8_runpod():
    # 1. RunPod 환경에 맞춘 경로 설정
    # 로컬에서 업로드한 데이터가 /workspace/large_data/yolo/engine에 있다고 가정합니다.
    data_yaml = "/workspace/large_data/yolo/engine/engine/data.yaml"
    model_name = "yolov8m.pt"  # RTX 4090이므로 m(Medium) 모델 권장 (더 강력한 베이스라인)
    epochs = 10
    imgsz = 1280               # RTX 4090의 24GB VRAM을 활용하여 고해상도 학습
    batch = 32                 # 4090에서는 32~64 가능
    device = 0                 # GPU 0
    
    print(f"🚀 [RunPod] YOLOv8 Baseline Training Started")
    print(f"   GPU: RTX 4090 (Detected context)")
    print(f"   Model: {model_name}")
    print(f"   Data: {data_yaml}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch: {batch}")
    print(f"   Image Size: {imgsz}")
    
    # data.yaml 경로 확인 및 자동 수정
    if not os.path.exists(data_yaml):
        print(f"[Error] data.yaml not found at {data_yaml}")
        print("💡 데이터를 /workspace/large_data/yolo/engine 폴더에 먼저 업로드해 주세요.")
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
        project="/workspace/AI-5-main-project/runs/detect",
        name="yolov8_baseline_runpod",
        exist_ok=True,
        cache=True
    )
    
    print("\n✅ [RunPod] Training Complete!")
    print(f"   Best weight saved at: /workspace/AI-5-main-project/runs/detect/yolov8_baseline_runpod/weights/best.pt")

if __name__ == "__main__":
    train_yolov8_runpod()
