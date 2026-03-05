import os
import torch
import cv2
import pandas as pd
from ultralytics import YOLO
from pathlib import Path
from tqdm import tqdm

def measure_hybrid_fpr():
    # 1. 설정
    yolo_model_path = "/workspace/AI-5-main-project/runs/detect/yolo11m_core8_optimization_ep15/weights/best.pt"
    # [수정] 파일들이 /workspace 폴더에 직접 업로드된 것을 확인하여 경로 수정
    cls_base_path = "/workspace"
    test_image_dir = "/workspace/large_data/yolo/engine/valid/images" 
    
    # 8개 핵심 부품 매핑 (YOLO 클래스 이름 : CLS 모델파일명)
    core8_map = {
        "ABS_Unit": "ABS_Unit.pt",
        "Air_Filter_Cover": "Air_Filter_Cover.pt",
        "Battery": "Battery.pt",
        "Brake_Fluid": "Brake_Fluid.pt",
        "Engine_Cover": "Engine_Cover.pt",
        "Engine_Oil_Fill_Cap": "Oil_Fill_Cap.pt",
        "Radiator": "Radiator.pt",
        "Windshield_Wiper_Fluid": "Wiper_Fluid.pt"
    }

    # 2. 모델 로드
    print("🔋 모델 로딩 중...")
    yolo_model = None
    cls_models = {}
    
    try:
        if not os.path.exists(yolo_model_path):
            print(f"❌ 에러: YOLO 가중치가 없습니다 -> {yolo_model_path}")
            return
            
        yolo_model = YOLO(yolo_model_path)
        print(f"✅ 탐지 모델 로드 완료: {yolo_model.names}")

        for cls_name, model_file in core8_map.items():
            model_path = os.path.join(cls_base_path, model_file)
            if os.path.exists(model_path):
                cls_models[cls_name] = YOLO(model_path)
                print(f"   - [로드 성공] {cls_name}")
            else:
                print(f"   - [로드 실패] {cls_name} (파일 없음: {model_path})")
                
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return

    if not cls_models:
        print("❌ 실패: 로드된 CLS 모델이 하나도 없습니다. 파일 업로드 위치를 확인하세요.")
        return

    # 3. 측정 시작
    image_paths = list(Path(test_image_dir).glob("*.jpg"))
    if not image_paths:
        print(f"❌ 에러: 이미지가 없습니다 -> {test_image_dir}")
        return
        
    print(f"🔍 총 {len(image_paths)}장의 이미지에서 측정 중...")
    stats = {name: {"yolo_detected": 0, "cls_processed": 0, "false_positives": 0} for name in core8_map.keys()}

    for img_path in tqdm(image_paths):
        results = yolo_model.predict(img_path, conf=0.25, verbose=False)[0]
        img_orig = cv2.imread(str(img_path))
        
        for box in results.boxes:
            cls_idx = int(box.cls[0])
            yolo_cls_name = yolo_model.names[cls_idx]
            
            if yolo_cls_name in stats:
                stats[yolo_cls_name]["yolo_detected"] += 1
                
                if yolo_cls_name in cls_models:
                    stats[yolo_cls_name]["cls_processed"] += 1
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    crop = img_orig[y1:y2, x1:x2]
                    
                    if crop.size == 0: continue
                    
                    cls_res = cls_models[yolo_cls_name].predict(crop, verbose=False)[0]
                    # YOLO-cls 결과: probs.top1이 0이면 Normal, 1이면 Abnormal로 가정
                    pred_idx = int(cls_res.probs.top1)
                    
                    if pred_idx == 1: 
                        stats[yolo_cls_name]["false_positives"] += 1

    # 4. 결과 정리
    print("\n--- 📊 최종 FPR 측정 결과 ---")
    summary = []
    for cls_name, data in stats.items():
        y_det = data["yolo_detected"]
        c_proc = data["cls_processed"]
        fp = data["false_positives"]
        fpr = (fp / c_proc * 100) if c_proc > 0 else 0
        
        summary.append({
            "Class": cls_name,
            "YOLO_Detected": y_det,
            "CLS_Processed": c_proc,
            "False_Positives": fp,
            "FPR(%)": f"{fpr:.2f}%"
        })
        print(f"[{cls_name}] YOLO: {y_det}, CLS: {c_proc}, FPR: {fpr:.2f}%")

    df = pd.DataFrame(summary)
    output_path = "/workspace/AI-5-main-project/hybrid_fpr_report.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✅ 리포트 저장 완료: {output_path}")

if __name__ == "__main__":
    measure_hybrid_fpr()
