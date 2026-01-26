# ai/app/services/dashboard_service.py
"""
계기판 분석 서비스 (Dashboard Analysis)

[파일 설명]
이 파일은 계기판 이미지를 분석하여 경고등을 탐지하고 해석하는 서비스입니다.
YOLO로 10종 경고등을 감지하고, LLM으로 의미와 조치 사항을 해석합니다.

[API 응답 형식]
{
  "status": "CRITICAL",
  "analysis_type": "SCENE_DASHBOARD",
  "category": "DASHBOARD",
  "data": {
    "vehicle_context": { inferred_model, dashboard_type },
    "detected_count": 2,
    "detections": [...],
    "integrated_analysis": { severity_score, description, short_term_risk },
    "recommendation": { primary_action, secondary_action, estimated_repair }
  }
}
"""
from typing import List, Optional, Union, Dict, Any
from PIL import Image
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
    "Anti_Lock_Braking_System": {"severity": "WARNING", "color": "YELLOW", "category": "BRAKES", "description": "ABS 시스템 이상"},
    "Braking_System_Issue": {"severity": "CRITICAL", "color": "RED", "category": "BRAKES", "description": "브레이크 시스템 고장"},
    "Charging_System_Issue": {"severity": "WARNING", "color": "YELLOW", "category": "ELECTRICAL", "description": "충전 시스템 이상 (배터리/알터네이터)"},
    "Check_Engine": {"severity": "WARNING", "color": "YELLOW", "category": "ENGINE", "description": "엔진 점검 필요"},
    "Electronic_Stability_Problem": {"severity": "WARNING", "color": "YELLOW", "category": "SAFETY", "description": "전자 안정 제어(ESP) 이상"},
    "Engine_Overheating": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "엔진 과열 - 즉시 정차 필요"},
    "Low_Engine_Oil": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "엔진 오일 부족 - 주행 중지 권장"},
    "Low_Tire_Pressure": {"severity": "WARNING", "color": "YELLOW", "category": "TIRES", "description": "타이어 공기압 부족"},
    "Master_Warning": {"severity": "CRITICAL", "color": "RED", "category": "GENERAL", "description": "차량 주요 시스템 경고"},
    "SRS_Airbag": {"severity": "CRITICAL", "color": "RED", "category": "SAFETY", "description": "에어백 시스템 이상"},
}


async def run_dashboard_yolo(
    image: Union[str, Image.Image], 
    yolo_model
) -> List[Dict]:
    """
    Dashboard YOLO로 경고등 감지
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
                label_info = DASHBOARD_CLASSES.get(label_name, {})
                
                detections.append({
                    "label": label_name,
                    "color_severity": label_info.get("color", "YELLOW"),
                    "confidence": round(confidence, 2),
                    "is_blinking": None,  # 이미지로는 점멸 감지 불가
                    "meaning": label_info.get("description", "알 수 없는 경고등"),
                    "bbox": [int(v) for v in bbox]
                })
        
        return detections
        
    except Exception as e:
        print(f"[Dashboard YOLO Error] {e}")
        return []


async def analyze_dashboard_image(
    image: Image.Image,
    s3_url: str, 
    yolo_model=None
) -> Dict[str, Any]:
    """
    계기판 경고등 분석 메인 함수
    
    Returns:
        API 명세서 형식의 응답 딕셔너리
    """
    # Step 0: YOLO 모델 없으면 LLM Fallback
    if yolo_model is None:
        print("[Dashboard] YOLO 모델 없음, LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "ERROR",
            "analysis_type": "SCENE_DASHBOARD",
            "category": "DASHBOARD",
            "data": {
                "vehicle_context": None,
                "detected_count": 0,
                "detections": [],
                "integrated_analysis": None,
                "recommendation": None,
                "llm_fallback": True,
                "description": llm_result.description if hasattr(llm_result, 'description') else None
            }
        }
    
    # Step 1: YOLO 감지
    detections = await run_dashboard_yolo(image, yolo_model)
    
    # Step 1-1: 감지 없으면 정상
    if len(detections) == 0:
        return {
            "status": "NORMAL",
            "analysis_type": "SCENE_DASHBOARD",
            "category": "DASHBOARD",
            "data": {
                "vehicle_context": None,
                "detected_count": 0,
                "detections": [],
                "integrated_analysis": {
                    "severity_score": 0,
                    "description": "계기판에서 경고등이 감지되지 않았습니다. 정상 상태입니다.",
                    "short_term_risk": None
                },
                "recommendation": None
            }
        }
    
    # Step 1-2: 신뢰도 체크 - 낮으면 LLM Fallback
    max_confidence = max(d["confidence"] for d in detections)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Dashboard] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "WARNING",
            "analysis_type": "SCENE_DASHBOARD",
            "category": "DASHBOARD",
            "data": {
                "vehicle_context": None,
                "detected_count": len(detections),
                "detections": detections,
                "integrated_analysis": None,
                "recommendation": None,
                "llm_fallback": True
            }
        }
    
    # Step 2: 심각도 계산
    max_severity = "NORMAL"
    severity_score = 0
    for det in detections:
        label_info = DASHBOARD_CLASSES.get(det["label"], {})
        severity = label_info.get("severity", "WARNING")
        if severity == "CRITICAL":
            max_severity = "CRITICAL"
            severity_score = max(severity_score, 9)
        elif severity == "WARNING" and max_severity != "CRITICAL":
            max_severity = "WARNING"
            severity_score = max(severity_score, 5)
    
    # Step 3: LLM 해석 (Fast Path 적용: NORMAL이고 신뢰도 높으면 스킵)
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_THRESHOLD:
        print(f"[Dashboard] Fast Path 적용 (신뢰도: {max_confidence:.2f}). LLM 스킵.")
        integrated_analysis = {
            "severity_score": 0,
            "description": "계기판에서 경고등이 감지되지 않았습니다.",
            "short_term_risk": None
        }
        recommendation = None
    else:
        # LLM 전달용 데이터 정제
        warning_list = []
        for det in detections:
            label_info = DASHBOARD_CLASSES.get(det["label"], {})
            warning_list.append({
                "name": det["label"],
                "severity": label_info.get("severity", "WARNING"),
                "description": label_info.get("description", "알 수 없는 경고등")
            })
        
        llm_result = await interpret_dashboard_warnings(warning_list)
        
        integrated_analysis = {
            "severity_score": severity_score,
            "description": llm_result.get("description", ""),
            "short_term_risk": llm_result.get("short_term_risk", None)
        }
        
        recommendation = {
            "primary_action": llm_result.get("recommendation", None),
            "secondary_action": llm_result.get("secondary_action", None),
            "estimated_repair": llm_result.get("estimated_repair", None)
        }
    
    # API 명세서 형식에 맞춤
    return {
        "status": max_severity,
        "analysis_type": "SCENE_DASHBOARD",
        "category": "DASHBOARD",
        "data": {
            "vehicle_context": None,  # TODO: LLM이 차종 추론 기능 추가 시
            "detected_count": len(detections),
            "detections": detections,
            "integrated_analysis": integrated_analysis,
            "recommendation": recommendation
        }
    }
