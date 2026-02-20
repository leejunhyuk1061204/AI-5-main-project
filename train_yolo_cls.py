from ultralytics import YOLO
import os
from pathlib import Path

# 데이터셋 루트 경로
DATA_ROOT = Path(r"C:\Users\301\Desktop\data\classification")
# 결과 저장 경로
PROJECT_ROOT = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\cls")

# 대상 부품 목록 (이미 학습된 5개 제외, 누락된 3개만 추가 학습)
TARGET_PARTS = [
    "Air_Filter_Cover", "Engine_Oil_Fill_Cap", "Windshield_Wiper_Fluid"
]

def train_models():
    for part in TARGET_PARTS:
        print(f"\n=== Training YOLOv8-cls for {part} ===")
        
        # 데이터셋 경로 확인
        part_data_dir = DATA_ROOT / part
        if not (part_data_dir / "train").exists():
            print(f"  [Skipped] Dataset not found for {part}")
            continue
            
        try:
            # 두 가지 실험 모드: Baseline (Freeze) vs Fine-tune (Full)
            configs = [
                {"suffix": "baseline", "freeze": 6},  # Backbone Freeze (Reduce to 6 layers to ensure Head is trainable)
                {"suffix": "finetune", "freeze": None} # Full Training
            ]
            
            for conf in configs:
                run_name = f"{part}_{conf['suffix']}"
                freeze_val = conf['freeze']
                
                print(f"  -> Starting training: {run_name} (freeze={freeze_val})")
                
                # YOLOv8n-cls 모델 로드 (매번 초기화)
                model = YOLO('yolov8n-cls.pt') 
                
                results = model.train(
                    data=str(part_data_dir),
                    epochs=10, 
                    imgsz=224,
                    project=str(PROJECT_ROOT),
                    name=run_name,
                    exist_ok=True,
                    pretrained=True,
                    freeze=freeze_val, # Freeze 옵션 적용
                    patience=5 # 조기 종료 (실험용이라 좀 더 짧게)
                )
                print(f"  -> Finished: {run_name}")
            
            print(f"  [Success] Training completed for {part}")
            
        except Exception as e:
            print(f"  [Error] Failed to train {part}: {e}")

if __name__ == "__main__":
    train_models()
