# ai/app/services/tire_service.py
"""
타이어 분석 서비스 (Tire Analysis)

[역할]
1. 타이어 이미지에서 상태(정상, 마모, 균열, 펑크 등)를 감지합니다. (YOLO)
2. 감지된 상태에 따라 위험도(Severity)를 판별합니다.
3. LLM을 연동하여 타이어 관리 및 안전 관련 조언을 생성합니다.

[주요 기능]
- 타이어 상태 탐지 (run_tire_yolo)
- 타이어 종합 분석 (analyze_tire_image)
"""
from typing import List, Union, Dict
from PIL import Image
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.services.llm_service import analyze_general_image, interpret_tire_status
from ai.app.services.router_service import CONFIDENCE_THRESHOLD

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9  # 이 값 이상이면서 NORMAL이면 LLM 건너뜀

# =============================================================================
# Tire 상태 클래스
# =============================================================================
TIRE_CLASSES = {
    "normal": {"severity": "NORMAL", "description": "정상 상태", "action": "정기 점검 권장"},
    "cracked": {"severity": "CRITICAL", "description": "균열 발견", "action": "즉시 타이어 교체 필요"},
    "worn": {"severity": "WARNING", "description": "마모됨", "action": "타이어 교체 권장"},
    "flat": {"severity": "CRITICAL", "description": "펑크/공기 빠짐", "action": "즉시 교체 또는 수리 필요"},
    "bulge": {"severity": "CRITICAL", "description": "측면 팽창", "action": "즉시 타이어 교체 필요"},
}


async def run_tire_yolo(
    image: Union[str, Image.Image], 
    yolo_model
) -> List[DetectionItem]:
    """
    Tire YOLO로 타이어 상태 감지
    
    Args:
        image: S3 URL 또는 PIL Image 객체
    """
    if yolo_model is None:
        return []
    
    try:
        results = yolo_model.predict(source=image, save=False, conf=0.25)
        detections = []
        
        for r in results:
            for box in r.boxes:
                label_idx = int(box.cls[0])
                label_name = yolo_model.names[label_idx]
                confidence = float(box.conf[0])
                bbox = box.xywh[0].tolist()
                
                detections.append(DetectionItem(
                    label=label_name,
                    confidence=round(confidence, 2),
                    bbox=[int(v) for v in bbox]
                ))
        
        return detections
        
    except Exception as e:
        print(f"[Tire YOLO Error] {e}")
        return []


# interpret_tire_status 함수를 llm_service로 이전 완료


async def analyze_tire_image(
    image: Image.Image,
    s3_url: str, 
    yolo_model=None
) -> VisualResponse:
    """
    타이어 상태 분석 메인 함수 (pre-loaded image 사용)
    """
    # Step 0: YOLO 모델 없으면 LLM Fallback
    if yolo_model is None:
        print("[Tire] YOLO 모델 없음, LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 1: YOLO 감지
    detections = await run_tire_yolo(image, yolo_model)
    
    # Step 1-1: 감지 없으면 LLM Fallback (타이어가 안 보일 수 있음)
    if len(detections) == 0:
        print("[Tire] 타이어 감지 안됨, LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 1-2: 신뢰도 체크
    max_confidence = max(d.confidence for d in detections)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Tire] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 2: 심각도 계산
    max_severity = "NORMAL"
    for det in detections:
        label_lower = det.label.lower()
        status_info = TIRE_CLASSES.get(label_lower, {})
        severity = status_info.get("severity", "WARNING")
        
        if severity == "CRITICAL":
            max_severity = "CRITICAL"
            break
        elif severity == "WARNING" and max_severity == "NORMAL":
            max_severity = "WARNING"
    
    # Step 3: LLM 해석 (Fast Path 적용: NORMAL이고 신뢰도 높으면 스킵)
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_THRESHOLD:
        print(f"[Tire] Fast Path 적용 (신뢰도: {max_confidence:.2f}). LLM 스킵.")
        description = "타이어가 정상적인 상태로 보입니다. 마모나 균열이 발견되지 않았습니다."
        recommendation = "정기적인 공기압 점검을 권장합니다."
    else:
        # LLM 전달용 데이터 정제
        status_list = []
        for det in detections:
            label_lower = det.label.lower()
            status_info = TIRE_CLASSES.get(label_lower, {})
            status_list.append({
                "status": det.label,
                "description": status_info.get("description", det.label),
                "action": status_info.get("action", "점검 필요")
            })
        
        llm_result = await interpret_tire_status(status_list)
        description = llm_result.get("description", "")
        recommendation = llm_result.get("recommendation", "")
    
    return VisualResponse(
        status=max_severity,
        analysis_type="SCENE_TIRE",
        category="TIRE",
        detected_count=len(detections),
        detections=detections,
        description=description,
        recommendation=recommendation,
        processed_image_url=s3_url
    )
