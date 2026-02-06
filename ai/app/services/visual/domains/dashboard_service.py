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
from ai.app.services.common.llm_service import analyze_general_image
from ai.app.services.visual.router_service import CONFIDENCE_THRESHOLD

FAST_PATH_YOLO_CONF = 0.85  # 이 값 이상이면서 NORMAL이면 LLM 건너뜀

# =============================================================================
# Dashboard 경고등 클래스 정의 (10종)
# =============================================================================
DASHBOARD_CLASSES = {
    "Anti_Lock_Braking_System": {"severity": "WARNING", "color": "YELLOW", "category": "BRAKES", "description": "ABS System Issue"},
    "Braking_System_Issue": {"severity": "CRITICAL", "color": "RED", "category": "BRAKES", "description": "Brake System Failure"},
    "Charging_System_Issue": {"severity": "CRITICAL", "color": "RED", "category": "ELECTRICAL", "description": "Charging System Issue"},
    "Check_Engine": {"severity": "WARNING", "color": "YELLOW", "category": "ENGINE", "description": "Check Engine Required"},
    "Electronic_Stability_Problem_-ESP-": {"severity": "WARNING", "color": "YELLOW", "category": "SAFETY", "description": "ESP System Issue"},
    "Engine_Overheating_Warning_Light": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "Engine Overheating"},
    "Low_Engine_Oil_Warning_Light": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "Low Engine Oil Warning"},
    "Low_Tire_Pressure_Warning_Light": {"severity": "WARNING", "color": "YELLOW", "category": "TIRES", "description": "Low Tire Pressure"},
    "Master_warning_light": {"severity": "WARNING", "color": "YELLOW", "category": "GENERAL", "description": "Master Warning Active"},
    "SRS-Airbag": {"severity": "CRITICAL", "color": "RED", "category": "SAFETY", "description": "Airbag System Issue"},
}

from ai.app.services.visual.yolo_utils import normalize_bbox


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
        results = yolo_model.predict(source=image, save=False, conf=0.25, imgsz=1280)
        detections = []
        
        for r in results:
            for box in r.boxes:
                label_idx = int(box.cls[0])
                label_name = yolo_model.names[label_idx]
                confidence = float(box.conf[0])
                bbox = box.xywh[0].tolist()
                label_info = DASHBOARD_CLASSES.get(label_name, {})

                x1, y1, w, h = box.xywh[0].tolist()
                
                detections.append({
                    "label": label_name.replace(" ", "_"),
                    "color_severity": label_info.get("color", "YELLOW"),
                    "confidence": round(confidence, 2),
                    "bbox": [int(x1 - w/2), int(y1 - h/2), int(w), int(h)]
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
                "detected_count": 0,
                "detections": [],
                "integrated_analysis": {
                    "severity_score": 0
                },
                "llm_fallback": True
            }
        }
    
    # Step 1: YOLO 감지
    detections = await run_dashboard_yolo(image, yolo_model)
    
    # Step 1-1: 감지된 경고등이 없으면, LLM으로 '진짜 계기판인지' + '다른 문제는 없는지' 2차 확인 (Safety Net)
    if len(detections) == 0:
        print("[Dashboard] 감지된 경고등 없음. LLM Safety Check 진행.")
        llm_result = await analyze_general_image(s3_url)
        
        # 기본 상태는 UNKNOWN (YOLO가 아무것도 못 찾았으므로, 정상인지 모델 실패인지 엉뚱한 사진인지 모름)
        # LLM 분석 결과에 따라 상태를 결정함
        status = "UNKNOWN"
        
        if hasattr(llm_result, "status"):
            status = llm_result.status  # LLM이 NORMAL(정상 계기판) or ERROR(차량 아님) 판별
        


        # [NEW] 만약 상태가 WARNING/CRITICAL인데 detections가 비어있다면, LLM에게 강제로 라벨링을 요청
        fallback_detections = []
        if status in ["WARNING", "CRITICAL"]:
            print(f"[Dashboard] YOLO Miss detected (Status: {status}). Requesting LLM Labeling...")
            from ai.app.services.common.llm_service import generate_training_labels
            label_result = await generate_training_labels(s3_url, "dashboard")
            
            for lbl in label_result.get("labels", []):
                # LLM 라벨을 API detection 포맷으로 변환
                bbox = lbl.get("bbox", [0, 0, 0, 0])
                from ai.app.services.visual.yolo_utils import normalize_to_xywh
                pixel_bbox = normalize_to_xywh(bbox, image.width, image.height)

                # [Active Learning] YOLO는 놓쳤지만 LLM이 찾은 경우 -> 매우 귀중한 '학습 데이터'로 기록
                try:
                    from ai.app.services.common.active_learning_service import get_active_learning_service
                    al_service = get_active_learning_service()
                    
                    # 이미 위에서 generate_training_labels 결과를 label_result로 가지고 있음
                    # label_result 구조: {"status":..., "labels": [...]}
                    
                    label_key = al_service.save_oracle_label(s3_url, label_result, "dashboard")
                    if label_key:
                        al_service.record_manifest(
                            s3_url=s3_url,
                            category="DASHBOARD",
                            label_key=label_key,
                            status=status,
                            confidence=0.1, # YOLO는 못 찾았으므로 낮은 신뢰도 부여 (우선순위 상향)
                            analysis_type="LLM_ORACLE_d_MISS", # YOLO Miss 특수 마킹
                            domain="visual"
                        )
                except Exception as e:
                    print(f"[Dashboard AL] Miss-detection 기록 실패: {e}")

                fallback_detections.append({
                    "label": lbl.get("part", "Unknown").replace(" ", "_"),
                    "color_severity": "RED" if status == "CRITICAL" else "YELLOW",
                    "confidence": 0.85,
                    "bbox": pixel_bbox
                })

        return {
            "status": status,
            "analysis_type": "SCENE_DASHBOARD",
            "category": "DASHBOARD",
            "data": {
                "detected_count": len(fallback_detections),
                "detections": fallback_detections
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
                "detected_count": len(detections),
                "detections": detections
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
    
    # Step 3: 경고등 분석 (LLM 호출 제거 - API 응답에 미포함되어 토큰 낭비)
    # 참고: integrated_analysis, recommendation은 API 응답에 포함되지 않음
    
    # [Active Learning] 공통 서비스 활용
    # max_confidence가 0.85 미만이고, 0보다는 큰 경우 (완전 실패는 아님)
    if detections and max_confidence < FAST_PATH_YOLO_CONF: 
         try:
             from ai.app.services.common.active_learning_service import get_active_learning_service
             from ai.app.services.common.llm_service import generate_training_labels
             
             al_service = get_active_learning_service()
             print(f"[Dashboard] Active Learning 대상 감지 (Conf: {max_confidence})")
             
             oracle_labels = await generate_training_labels(s3_url, "dashboard")
             
             if not oracle_labels or not oracle_labels.get("labels"):
                 return
             
             # [Fix] 안전한 Key 사용 (추정이 아닌 반환값 사용)
             label_key = al_service.save_oracle_label(s3_url, oracle_labels, "dashboard")
             if label_key:
                 al_service.record_manifest(
                     s3_url=s3_url,
                     category="DASHBOARD",
                     label_key=label_key,
                     status=oracle_labels.get("status", "UNKNOWN"),
                     confidence=max_confidence,
                     analysis_type="LLM_ORACLE_DASHBOARD",
                     domain="visual"
                     )
         except Exception as e:
             print(f"AL Fail: {e}")

    # API 명세서 형식에 맞춤
    return {
        "status": max_severity,
        "analysis_type": "SCENE_DASHBOARD",
        "category": "DASHBOARD",
        "data": {
            "detected_count": len(detections),
            "detections": detections
        }
    }
