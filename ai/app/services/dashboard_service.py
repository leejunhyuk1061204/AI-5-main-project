# ai/app/services/dashboard_service.py
"""
계기판 분석 서비스 (Dashboard Analysis)

[역할]
1. 계기판 이미지 내의 경고등(Warning Light) 객체를 감지합니다. (YOLO)
2. 감지된 경고등의 위험도(Severity)를 판단하여 차량 상태를 결정합니다.
3. 정밀 해석이 필요한 경우 LLM을 호출하여 운전자 가이드를 생성합니다.

[주요 기능]
- 경고등 객체 탐지 (run_dashboard_yolo)
- 계기판 전체 진단 로직 (analyze_dashboard_image)
"""
from typing import List, Optional, Union, Dict
from PIL import Image
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.services.llm_service import analyze_general_image, interpret_dashboard_warnings
from ai.app.services.router_service import CONFIDENCE_THRESHOLD

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9  # 이 값 이상이면서 NORMAL이면 LLM 건너뜀

# =============================================================================
# Dashboard 경고등 클래스 정의 (10종)
# =============================================================================
DASHBOARD_CLASSES = {
    "Anti_Lock_Braking_System": {"severity": "WARNING", "category": "BRAKES", "description": "ABS 시스템 이상"},
    "Braking_System_Issue": {"severity": "CRITICAL", "category": "BRAKES", "description": "브레이크 시스템 고장"},
    "Charging_System_Issue": {"severity": "WARNING", "category": "ELECTRICAL", "description": "충전 시스템 이상 (배터리/알터네이터)"},
    "Check_Engine": {"severity": "WARNING", "category": "ENGINE", "description": "엔진 점검 필요"},
    "Electronic_Stability_Problem": {"severity": "WARNING", "category": "SAFETY", "description": "전자 안정 제어(ESP) 이상"},
    "Engine_Overheating": {"severity": "CRITICAL", "category": "ENGINE", "description": "엔진 과열 - 즉시 정차 필요"},
    "Low_Engine_Oil": {"severity": "CRITICAL", "category": "ENGINE", "description": "엔진 오일 부족 - 주행 중지 권장"},
    "Low_Tire_Pressure": {"severity": "WARNING", "category": "TIRES", "description": "타이어 공기압 부족"},
    "Master_Warning": {"severity": "CRITICAL", "category": "GENERAL", "description": "차량 주요 시스템 경고"},
    "SRS_Airbag": {"severity": "CRITICAL", "category": "SAFETY", "description": "에어백 시스템 이상"},
}


async def run_dashboard_yolo(
    image: Union[str, Image.Image], 
    yolo_model
) -> List[DetectionItem]:
    """
    Dashboard YOLO로 경고등 감지
    
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
        print(f"[Dashboard YOLO Error] {e}")
        return []


# interpret_dashboard_warnings 함수를 llm_service로 이전 완료


async def analyze_dashboard_image(
    image: Image.Image,
    s3_url: str, 
    yolo_model=None
) -> VisualResponse:
    """
    계기판 경고등 분석 메인 함수
    
    프로세스:
    1. YOLO로 경고등 감지 (pre-loaded image 사용)
    2. 심각도 기반 status 결정
    3. LLM에게 상세 해석 요청
    """
    # Step 0: YOLO 모델 없으면 LLM Fallback
    if yolo_model is None:
        print("[Dashboard] YOLO 모델 없음, LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 1: YOLO 감지
    detections = await run_dashboard_yolo(image, yolo_model)
    
    # Step 1-1: 감지 없으면 정상
    if len(detections) == 0:
        return VisualResponse(
            status="NORMAL",
            analysis_type="SCENE_DASHBOARD",
            category="DASHBOARD",
            detected_count=0,
            detections=[],
            description="계기판에서 경고등이 감지되지 않았습니다. 정상 상태입니다.",
            recommendation=None,
            processed_image_url=s3_url
        )
    
    # Step 1-2: 신뢰도 체크 - 낮으면 LLM Fallback
    max_confidence = max(d.confidence for d in detections)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Dashboard] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 2: 심각도 계산
    max_severity = "NORMAL"
    for det in detections:
        label_info = DASHBOARD_CLASSES.get(det.label, {})
        severity = label_info.get("severity", "WARNING")
        if severity == "CRITICAL":
            max_severity = "CRITICAL"
            break
        elif severity == "WARNING" and max_severity != "CRITICAL":
            max_severity = "WARNING"
    
    # Step 3: LLM 해석 (Fast Path 적용: NORMAL이고 신뢰도 높으면 스킵)
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_THRESHOLD:
        print(f"[Dashboard] Fast Path 적용 (신뢰도: {max_confidence:.2f}). LLM 스킵.")
        description = "계기판에서 경고등이 감지되지 않았습니다. 모든 시스템이 정상적으로 작동하고 있습니다."
        recommendation = "정기적인 차량 점검 스케줄을 유지하세요."
    else:
        # LLM 전달용 데이터 정제
        warning_list = []
        for det in detections:
            label_info = DASHBOARD_CLASSES.get(det.label, {})
            warning_list.append({
                "name": det.label,
                "severity": label_info.get("severity", "WARNING"),
                "description": label_info.get("description", "알 수 없는 경고등")
            })
        
        llm_result = await interpret_dashboard_warnings(warning_list)
        description = llm_result.get("description", "")
        recommendation = llm_result.get("recommendation", "")
    
    return VisualResponse(
        status=max_severity,
        analysis_type="SCENE_DASHBOARD",
        category="DASHBOARD",
        detected_count=len(detections),
        detections=detections,
        description=description,
        recommendation=recommendation,
        processed_image_url=s3_url
    )
