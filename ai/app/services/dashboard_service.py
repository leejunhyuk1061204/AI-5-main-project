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

FAST_PATH_YOLO_CONF = 0.85  # 이 값 이상이면서 NORMAL이면 LLM 건너뜀

# =============================================================================
# Dashboard 경고등 클래스 정의 (10종)
# =============================================================================
DASHBOARD_CLASSES = {
    "Anti Lock Braking System": {"severity": "WARNING", "color": "YELLOW", "category": "BRAKES", "description": "ABS 시스템 이상"},
    "Braking System Issue": {"severity": "CRITICAL", "color": "RED", "category": "BRAKES", "description": "브레이크 시스템 고장"},
    "Charging System Issue": {"severity": "CRITICAL", "color": "RED", "category": "ELECTRICAL", "description": "배터리/충전 시스템 이상"},
    "Check Engine": {"severity": "WARNING", "color": "YELLOW", "category": "ENGINE", "description": "엔진 점검 필요"},
    "Electronic Stability Problem -ESP-": {"severity": "WARNING", "color": "YELLOW", "category": "SAFETY", "description": "전자 안정 제어(ESP) 이상"},
    "Engine Overheating Warning Light": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "엔진 과열 - 즉시 정차 필요"},
    "Low Engine Oil Warning Light": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "엔진 오일 부족 - 즉시 정차 필요"},
    "Low Tire Pressure Warning Light": {"severity": "WARNING", "color": "YELLOW", "category": "TIRES", "description": "타이어 공기압 부족"},
    "Master warning light": {"severity": "WARNING", "color": "YELLOW", "category": "GENERAL", "description": "통합 경고 확인 필요"},
    "SRS-Airbag": {"severity": "CRITICAL", "color": "RED", "category": "SAFETY", "description": "에어백 시스템 이상"},
}

from ai.app.services.yolo_utils import normalize_bbox


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

                cx, cy, w, h = box.xywh[0].tolist()
                x1 = int(cx - w / 2)
                y1 = int(cy - h / 2)
                x2 = int(cx + w / 2)
                y2 = int(cy + h / 2)
                
                detections.append({
                    "label": label_name,
                    "color_severity": label_info.get("color", "YELLOW"),
                    "confidence": round(confidence, 2),
                    "is_blinking": None,  # 이미지로는 점멸 감지 불가
                    "meaning": label_info.get("description", "알 수 없는 경고등"),
                    "bbox": [x1, y1, x2, y2]
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
                    "severity_score": 0,
                    "description": llm_result.data.get("description") if hasattr(llm_result, 'data') else "분석 실패"
                },
                "recommendation": {
                     "primary_action": llm_result.data.get("recommendation") if hasattr(llm_result, 'data') else "정비소 방문을 권장합니다."
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
        description = "경고등이 감지되지 않았으나, 명확한 상태 판단을 위해 AI 정밀 분석이 수행되었습니다."
        
        if hasattr(llm_result, "status"):
            status = llm_result.status  # LLM이 NORMAL(정상 계기판) or ERROR(차량 아님) 판별
        
        if hasattr(llm_result, "data") and llm_result.data:
            description = llm_result.data.get("description", description)

        # [NEW] 만약 상태가 WARNING/CRITICAL인데 detections가 비어있다면, LLM에게 강제로 라벨링을 요청
        fallback_detections = []
        if status in ["WARNING", "CRITICAL"]:
            print(f"[Dashboard] YOLO Miss detected (Status: {status}). Requesting LLM Labeling...")
            from ai.app.services.llm_service import generate_training_labels
            label_result = await generate_training_labels(s3_url, "dashboard")
            
            for lbl in label_result.get("labels", []):
                # LLM 라벨을 API detection 포맷으로 변환
                # [Fix] Ratio / Pixel 명시적 구분
                bbox = lbl.get("bbox", [0,0,0,0])
                # normalize_bbox 내부에서 ratio/pixel 판단하여 변환
                pixel_bbox = normalize_bbox(bbox, image.width, image.height)

                # [Active Learning] YOLO는 놓쳤지만 LLM이 찾은 경우 -> 매우 귀중한 '학습 데이터'로 기록
                try:
                    from ai.app.services.active_learning_service import get_active_learning_service
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
                    "label": lbl.get("class", "Unknown"),
                    "color_severity": "RED" if status == "CRITICAL" else "YELLOW",
                    "confidence": 0.85,
                    "is_blinking": None,
                    "meaning": "AI 정밀 분석으로 감지된 경고등",
                    "bbox": pixel_bbox # [Fix] 이미 변환된 좌표 사용
                })

        return {
            "status": status,
            "analysis_type": "SCENE_DASHBOARD",
            "category": "DASHBOARD",
            "data": {
                "detected_count": len(fallback_detections),
                "detections": fallback_detections,
                "integrated_analysis": {
                    "severity_score": 5 if status == "WARNING" else 9 if status == "CRITICAL" else 0,
                    "description": description
                },
                "recommendation": {
                    "primary_action": (llm_result.data or {}).get("recommendation", "재촬영 후 다시 시도해주세요.")
                }
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
                "detections": detections,
                "integrated_analysis": {
                    "severity_score": 5,
                    "description": llm_result.data.get("description") if hasattr(llm_result, 'data') else "낮은 신뢰도 검출"
                },
                "recommendation": {
                     "primary_action": llm_result.data.get("recommendation") if hasattr(llm_result, 'data') else "정교한 육안 점검 필요"
                },
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
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_YOLO_CONF:
        print(f"[Dashboard] Fast Path 적용 (신뢰도: {max_confidence:.2f}). LLM 스킵.")
        integrated_analysis = {
            "severity_score": 0,
            "description": "계기판에서 경고등이 감지되지 않았습니다."
        }
        recommendation = {
            "primary_action": "안전하게 주행을 계속하셔도 좋습니다."
        }
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
            "description": llm_result.get("description", "")
        }
        
        recommendation = {
            "primary_action": llm_result.get("recommendation", None)
        }
    
    # [Active Learning] 공통 서비스 활용
    # max_confidence가 0.85 미만이고, 0보다는 큰 경우 (완전 실패는 아님)
    if detections and max_confidence < FAST_PATH_YOLO_CONF: 
         try:
             from ai.app.services.active_learning_service import get_active_learning_service
             from ai.app.services.llm_service import generate_training_labels
             
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
            "detections": detections,
            "integrated_analysis": integrated_analysis,
            "recommendation": recommendation
        }
    }
