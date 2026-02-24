import os
import torch
import cv2
import pandas as pd
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from tqdm import tqdm
from anomalib.models import Patchcore
from anomalib.engine import Engine
from anomalib.data.utils import read_image
from PIL import Image

def measure_hybrid_patchcore_fpr():
    # 1. 설정
    yolo_model_path = "/workspace/AI-5-main-project/runs/detect/yolo11m_core8_optimization_ep15/weights/best.pt"
    # [수정] 사용자가 제공한 파일 경로 (RunPod 상의 /workspace/archive 기준)
    patchcore_base_dir = "/workspace/archive/patchcore_tp_crops_resplit"
    # PatchCore_fit 에 정상 이미지들이 모여있으므로 테스트 경로로 지정
    test_image_dir = "/workspace/archive/PatchCore_fit" 
    
    parts = [
        "ABS_Unit", "Air_Filter_Cover", "Battery", "Brake_Fluid", 
        "Engine_Cover", "Engine_Oil_Fill_Cap", "Radiator", "Windshield_Wiper_Fluid"
    ]

    # 2. 모델 로드
    print("🔋 모델 로딩 중 (YOLO11m + PatchCore)...")
    
    # YOLO 로드
    if not os.path.exists(yolo_model_path):
        print(f"❌ 에러: YOLO 가중치가 없습니다 -> {yolo_model_path}")
        return
    yolo_model = YOLO(yolo_model_path)
    
    # PatchCore 모델들 로드 (Anomalib Engine 활용)
    pc_models = {}
    engines = {}
    
    for part in parts:
        # 각 부품별 가중치 경로 (train_patchcore.py 저장 구조 기준)
        ckpt_path = Path(patchcore_base_dir) / part / "Patchcore" / part / "weights" / "last.ckpt"
        
        if ckpt_path.exists():
            try:
                # 모델 인스턴스 생성 (학습 시와 동일한 파라미터)
                model = Patchcore(
                    backbone="wide_resnet50_2",
                    layers=["layer2", "layer3"]
                )
                
                # Engine 생성 (추론 전용)
                engine = Engine(devices=1)
                
                pc_models[part] = model
                engines[part] = engine
                print(f"   - [로드 성공] PatchCore: {part}")
            except Exception as e:
                print(f"   - [로드 실패] {part}: {e}")
        else:
            print(f"   - [파일 없음] {part}: {ckpt_path}")

    if not pc_models:
        print("❌ 실패: 로드된 PatchCore 모델이 하나도 없습니다.")
        return

    # 3. 측정 시작
    image_paths = list(Path(test_image_dir).glob("*.jpg"))
    print(f"🔍 총 {len(image_paths)}장의 이미지에서 PatchCore FPR 측정 중...")

    stats = {name: {"yolo_detected": 0, "pc_processed": 0, "false_positives": 0} for name in parts}

    for img_path in tqdm(image_paths):
        # YOLO 탐지
        yolo_results = yolo_model.predict(img_path, conf=0.25, verbose=False)[0]
        img_orig = cv2.imread(str(img_path))
        
        for box in yolo_results.boxes:
            cls_idx = int(box.cls[0])
            yolo_cls_name = yolo_model.names[cls_idx]
            
            if yolo_cls_name in stats:
                stats[yolo_cls_name]["yolo_detected"] += 1
                
                # 해당 부품의 PatchCore 모델이 있는 경우
                if yolo_cls_name in pc_models:
                    stats[yolo_cls_name]["pc_processed"] += 1
                    
                    # 크롭 및 전처리
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    crop = img_orig[y1:y2, x1:x2]
                    if crop.size == 0: continue
                    
                    # OpenCV(BGR) -> RGB 변환 및 PIL 변환 (Anomalib 추론용)
                    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    crop_pil = Image.fromarray(crop_rgb)
                    
                    # PatchCore 추론
                    # Note: engine.predict는 내부적으로 가중치를 로드하거나 체크포인트를 활용함
                    results = engines[yolo_cls_name].predict(
                        model=pc_models[yolo_cls_name],
                        images=crop_pil,
                        ckpt_path=str(Path(patchcore_base_dir) / yolo_cls_name / "Patchcore" / yolo_cls_name / "weights" / "last.ckpt"),
                        verbose=False
                    )
                    
                    # 결과 해석: pred_labels가 True(1)이면 이상(Abnormal) 판정 -> FP
                    # Anomalib 1.0+ 기준 results는 리스트 혹은 객체일 수 있음
                    pred_label = results[0]["pred_labels"].item() if isinstance(results, list) else results.pred_labels.item()
                    
                    if pred_label: 
                        stats[yolo_cls_name]["false_positives"] += 1

    # 4. 결과 정리
    print("\n--- 📊 YOLO11m + PatchCore FPR 측정 결과 ---")
    summary = []
    for part, data in stats.items():
        y_det = data["yolo_detected"]
        p_proc = data["pc_processed"]
        fp = data["false_positives"]
        fpr = (fp / p_proc * 100) if p_proc > 0 else 0
        
        summary.append({
            "Class": part,
            "YOLO_Detected": y_det,
            "PC_Processed": p_proc,
            "False_Positives": fp,
            "FPR(%)": f"{fpr:.2f}%"
        })
        print(f"[{part}] YOLO: {y_det}, PatchCore: {p_proc}, FPR: {fpr:.2f}%")

    df = pd.DataFrame(summary)
    output_path = "/workspace/AI-5-main-project/patchcore_fpr_report.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✅ 리포트 저장 완료: {output_path}")

if __name__ == "__main__":
    measure_hybrid_patchcore_fpr()
