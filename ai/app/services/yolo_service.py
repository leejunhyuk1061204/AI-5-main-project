# app/services/yolo_service.py
from ultralytics import YOLO
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
import os

# =============================================================================
# [설정] 모델 경로
# =============================================================================
MODEL_PATH = "ai/weights/dashboard/best.pt"

# =============================================================================
# [자동 카테고리 매핑 함수]
# 라벨 이름 패턴에서 카테고리를 자동으로 추출합니다.
# 재학습 시 코드 수정 불필요!
# =============================================================================
def get_category_from_label(label_name: str) -> str:
    """
    라벨 이름에서 카테고리 자동 추출
    
    규칙:
    - 접두사 DASH_, EXT_, TIRE_ 등으로 시작하면 해당 카테고리
    - 또는 키워드 포함 여부로 판단
    """
    label_upper = label_name.upper()
    
    # 1. 접두사 규칙 (권장: 학습 데이터에 접두사 사용)
    if label_upper.startswith("DASH_"):
        return "DASHBOARD"
    elif label_upper.startswith("EXT_"):
        return "EXTERIOR"
    elif label_upper.startswith("TIRE_"):
        return "TIRES_WHEELS_IMAGE"
    elif label_upper.startswith("GLASS_"):
        return "GLASS_WINDOWS"
    elif label_upper.startswith("LIGHT_"):
        return "LIGHTS"
    elif label_upper.startswith("ENG_"):
        return "ENGINE_ROOM"
    elif label_upper.startswith("UNDER_"):
        return "UNDERBODY"
    elif label_upper.startswith("INT_"):
        return "INTERIOR"
    
    # 2. 키워드 규칙 (기존 Roboflow 데이터용)
    dashboard_keywords = ["ENGINE", "OIL", "BATTERY", "ABS", "AIRBAG", "TEMP", "FUEL", "BRAKE", "DOOR", "SEATBELT"]
    exterior_keywords = ["SCRATCH", "DENT", "CRACK", "RUST", "PAINT"]
    tire_keywords = ["TIRE", "WHEEL", "FLAT", "WORN"]
    
    for kw in dashboard_keywords:
        if kw in label_upper:
            return "DASHBOARD"
    for kw in exterior_keywords:
        if kw in label_upper:
            return "EXTERIOR"
    for kw in tire_keywords:
        if kw in label_upper:
            return "TIRES_WHEELS_IMAGE"
    
    # 3. 기본값
    return "UNKNOWN_IMAGE"

# =============================================================================
# 추론 함수
# =============================================================================
async def run_yolo_inference(s3_url: str, model=None) -> VisualResponse:
    """S3 URL 이미지를 받아 YOLOv8 모델로 감지합니다."""
    
    # 모델 미로드 시 Mock 응답 또는 에러 처리
    if model is None:
        print("[YOLO Service] Model is None! Returning Mock Response.")
        return VisualResponse(
            status="WARNING",
            analysis_type="YOLO_MOCK",
            category="DASHBOARD",
            detected_count=1,
            detections=[
                DetectionItem(
                    label="Check Engine (Mock)",
                    confidence=0.98,
                    bbox=[100, 100, 50, 50]
                )
            ],
            processed_image_url=s3_url
        )

    # YOLO 추론
    try:
        results = model.predict(source=s3_url, save=False, conf=0.25)
    except Exception as e:
        print(f"[YOLO Service] Inference Error: {e}")
        # 에러 발생 시 안전하게 빈 응답 반환 or Mock
        return VisualResponse(status="ERROR", analysis_type="YOLO", category="ERROR", detected_count=0, detections=[], processed_image_url=s3_url)
    
    detections = []
    detected_categories = set()
    
    for r in results:
        for box in r.boxes:
            label_idx = int(box.cls[0])
            label_name = model.names[label_idx]
            confidence = float(box.conf[0])
            bbox = box.xywh[0].tolist()
            
            # 자동 카테고리 매핑!
            category = get_category_from_label(label_name)
            detected_categories.add(category)

            detections.append(DetectionItem(
                label=label_name,
                confidence=round(confidence, 2),
                bbox=[int(v) for v in bbox]
            ))

    # 최종 카테고리 결정
    final_category = list(detected_categories)[0] if detected_categories else "UNKNOWN_IMAGE"
    status = "WARNING" if len(detections) > 0 else "NORMAL"
    
    return VisualResponse(
        status=status,
        analysis_type="YOLO",
        category=final_category,
        detected_count=len(detections),
        detections=detections,
        processed_image_url=s3_url
    )
