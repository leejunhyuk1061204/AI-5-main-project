# ai/app/services/engine_yolo_service.py
"""
엔진룸 부품 감지 서비스 (Engine YOLO)

[역할]
1. 엔진룸 부품 식별: 오일 캡, 배터리, 냉각수 탱크 등 26가지 주요 부품의 위치를 탐지합니다.
2. 분석 대상 추출: 탐지된 각 부품의 좌표를 기반으로 이미지를 크롭하여 하위 분석 단계(이상탐지)에 전달합니다.
3. 실시간 추론: 최적화된 YOLOv8 모델을 사용하여 고속으로 부품을 찾아냅니다.

[주요 기능]
- 엔진 부품 객체 탐지 (run_yolo_inference)
"""
import torch
import os
from ultralytics import YOLO
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from PIL import Image
from typing import Optional, Union

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9  # 90% 확신할 때만 LLM 스킵

# =============================================================================
# [설정] 모델 경로 - 엔진룸 부품 감지용
# =============================================================================
MODEL_PATH = os.path.join("ai", "weights", "engine", "best.pt")

# =============================================================================
# 엔진룸 부품 카테고리 매핑
# =============================================================================
ENGINE_PARTS = {
    "Inverter_Coolant_Reservoir", "Battery", "Radiator_Cap", "Windshield_Wiper_Fluid",
    "Fuse_Box", "Power_Steering_Reservoir", "Brake_Fluid", "Engine_Oil_Fill_Cap",
    "Engine_Oil_Dip_Stick", "Air_Filter_Cover", "ABS_Unit", "Alternator",
    "Engine_Coolant_Reservoir", "Radiator", "Air_Filter", "Engine_Cover",
    "Cold_Air_Intake", "Clutch_Fluid_Reservoir", "Transmission_Oil_Dip_Stick",
    "Intercooler_Coolant_Reservoir", "Oil_Filter_Housing", "ATF_Oil_Reservoir",
    "Cabin_Air_Filter_Housing", "Secondary_Coolant_Reservoir", "Electric_Motor",
    "Oil_Filter"
}

def get_category_from_label(label_name: str) -> str:
    """
    엔진룸 부품 라벨 -> 카테고리 매핑
    """
    if label_name in ENGINE_PARTS:
        return "ENGINE_ROOM"
    
    # 부분 일치 검사 (접두사 등)
    label_upper = label_name.upper()
    if any(p.upper() in label_upper for p in ENGINE_PARTS):
        return "ENGINE_ROOM"
    
    return "ENGINE_ROOM"

# =============================================================================
# 추론 함수
# =============================================================================
async def run_yolo_inference(
    s3_url: str, 
    image: Optional[Union[str, Image.Image]] = None,
    model=None
) -> VisualResponse:
    """
    S3 URL 또는 pre-loaded 이미지를 받아 YOLOv8 모델로 엔진 부품을 감지합니다.
    """
    source = image if image is not None else s3_url
    
    # Model is None -> Return empty response (for Path B fallback)
    if model is None:
        print("[YOLO Service] Model is None! Returning empty response for Path B.")
        return VisualResponse(
            status="NORMAL",
            analysis_type="YOLO_NOT_LOADED",
            category="ENGINE_ROOM",
            detected_count=0,  # Path B로 전환되도록 0 반환
            detections=[],
            processed_image_url=s3_url
        )

    # YOLO 추론
    try:
        results = model.predict(source=source, save=False, conf=0.25)
    except Exception as e:
        print(f"[YOLO Service] Inference Error: {e}")
        return VisualResponse(
            status="ERROR", 
            analysis_type="YOLO", 
            category="ERROR", 
            detected_count=0, 
            detections=[], 
            processed_image_url=s3_url
        )
    
    detections = []
    
    for r in results:
        for box in r.boxes:
            label_idx = int(box.cls[0])
            label_name = model.names[label_idx]
            confidence = float(box.conf[0])
            bbox = box.xywh[0].tolist()

            detections.append(DetectionItem(
                label=label_name,
                confidence=round(confidence, 2),
                bbox=[int(v) for v in bbox]
            ))

    # 신뢰도 낮은 탐지 필터링 (오탐 방지)
    # [Test Mode] 0.9 -> 0.7로 임시 하향 (실제 부품 놓침 방지)
    MIN_CONFIDENCE = 0.7
    detections = [d for d in detections if d.confidence >= MIN_CONFIDENCE]

    status = "WARNING" if len(detections) > 0 else "NORMAL"
    
    return VisualResponse(
        status=status,
        analysis_type="YOLO_ENGINE",
        category="ENGINE_ROOM",
        detected_count=len(detections),
        detections=detections,
        processed_image_url=s3_url
    )

