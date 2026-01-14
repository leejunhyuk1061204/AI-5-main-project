# Ai/train_dashboard.py
from roboflow import Roboflow
from ultralytics import YOLO
import os

# 1. Roboflow 데이터셋 다운로드
rf = Roboflow(api_key="rshw91xj9lAScwI4FBXA")
project = rf.workspace("teamdata").project("car-dashboard-sndt9")
version = project.version(3)
dataset = version.download("yolov8") # 런팟 서버에 car-dashboard-3 폴더가 생성됨

# 2. YOLOv8 학습 설정
model = YOLO('yolov8n.pt') # 가장 가벼운 모델로 시작
model.train(
    data=os.path.join(dataset.location, "data.yaml"), # 자동 생성된 경로
    epochs=50,      # 학습 횟수
    imgsz=640,      # 이미지 크기
    device=0,       # 런팟 GPU 사용
    project="Ai/runs", 
    name="dashboard_model"
)