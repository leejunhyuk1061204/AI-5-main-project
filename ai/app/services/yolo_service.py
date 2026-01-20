# app/services/yolo_service.py
"""
YOLO 서비스 - 엔진룸 부품 감지 전용
(Dashboard YOLO 제거됨 - LLM이 처리)
"""
from ultralytics import YOLO
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
import os

# =============================================================================
# [설정] 모델 경로 - 엔진룸 부품 감지용
# =============================================================================
MODEL_PATH = "ai/weights/engine/best.pt"

# =============================================================================
# 엔진룸 부품 카테고리 매핑
# =============================================================================
ENGINE_PARTS = {
    # ICE Parts
    "Oil_Cap", "Engine_Oil_Filler", "Engine_Cover", "Radiator_Cap", 
    "Coolant_Reservoir", "Brake_Fluid_Reservoir", "Washer_Fluid_Reservoir",
    "Air_Filter", "Belt", "Battery", "Fuse_Box",
    # EV Parts
    "Inverter", "Electric_Motor", "Charging_Port", 
    "Inverter_Coolant_Reservoir", "Secondary_Coolant_Reservoir"
}

def get_category_from_label(label_name: str) -> str:
    """
    엔진룸 부품 라벨 -> 카테고리 매핑
    (현재는 모두 ENGINE_ROOM으로 분류)
    """
    # 모든 엔진 부품은 ENGINE_ROOM
    if label_name in ENGINE_PARTS or label_name.upper().startswith("ENG_"):
        return "ENGINE_ROOM"
    
    # 기본값
    return "ENGINE_ROOM"  # 이 서비스는 엔진 전용이므로 기본값도 ENGINE_ROOM

# =============================================================================
# 추론 함수
# =============================================================================
async def run_yolo_inference(s3_url: str, model=None) -> VisualResponse:
    """
    S3 URL 이미지를 받아 YOLOv8 모델로 엔진 부품을 감지합니다.
    
    Returns:
        VisualResponse: 감지 결과 (detected_count == 0이면 Path B로 전환)
    """
    
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
        results = model.predict(source=s3_url, save=False, conf=0.25)
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
    MIN_CONFIDENCE = 0.5
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

