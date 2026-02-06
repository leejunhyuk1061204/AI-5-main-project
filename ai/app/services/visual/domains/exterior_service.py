# ai/app/services/exterior_service.py
"""
외관 파손 분석 서비스 (Exterior Damage Analysis)

[파일 설명]
이 파일은 차량 외관 이미지를 분석하여 파손 부위와 종류를 탐지하는 서비스입니다.
단일 YOLOv8 모델(22개 클래스)을 사용하여 부위와 파손을 동시에 식별합니다.

[API 응답 형식]
{
  "status": "WARNING",
  "analysis_type": "SCENE_EXTERIOR",
  "category": "EXTERIOR",
  "data": {
    "damage_found": true,
    "detections": [{ part, damage_type, confidence, bbox }]
  }
}
"""
from typing import List, Optional, Dict, Tuple, Union, Any
from PIL import Image
from ai.app.services.common.llm_service import analyze_general_image
from ai.app.services.visual.router_service import CONFIDENCE_THRESHOLD
from ai.app.services.visual.yolo_utils import normalize_bbox

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.85

# =============================================================================
# 통합 22종 클래스 매핑 (Label -> {part, damage, severity, description})
# =============================================================================
UNIFIED_CLASSES = {
    # 1. Dent series
    "bonnet-dent": {"part": "Bonnet", "damage": "Dent", "severity": "WARNING"},
    "doorouter-dent": {"part": "Door", "damage": "Dent", "severity": "WARNING"},
    "fender-dent": {"part": "Fender", "damage": "Dent", "severity": "WARNING"},
    "front-bumper-dent": {"part": "Front_Bumper", "damage": "Dent", "severity": "WARNING"},
    "quaterpanel-dent": {"part": "Quarter_Panel", "damage": "Dent", "severity": "WARNING"},
    "rear-bumper-dent": {"part": "Rear_Bumper", "damage": "Dent", "severity": "WARNING"},
    "roof-dent": {"part": "Roof", "damage": "Dent", "severity": "WARNING"},
    "pillar-dent": {"part": "Pillar", "damage": "Dent", "severity": "CRITICAL"},
    "runningboard-dent": {"part": "Running_Board", "damage": "Dent", "severity": "WARNING"},
    "medium-bodypanel-dent": {"part": "Body_Panel", "damage": "Medium_Dent", "severity": "WARNING"},
    "major-rear-bumper-dent": {"part": "Rear_Bumper", "damage": "Major_Dent", "severity": "CRITICAL"},

    # 2. Scratch series
    "doorouter-scratch": {"part": "Door", "damage": "Scratch", "severity": "WARNING"},
    "front-bumper-scratch": {"part": "Front_Bumper", "damage": "Scratch", "severity": "WARNING"},
    "rear-bumper-scratch": {"part": "Rear_Bumper", "damage": "Scratch", "severity": "WARNING"},

    # 3. Glass & Lamp Damage
    "front-windscreen-damage": {"part": "Front_Windshield", "damage": "Glass_Broken", "severity": "CRITICAL"},
    "rear-windscreen-damage": {"part": "Rear_Windshield", "damage": "Glass_Broken", "severity": "CRITICAL"},
    "headlight-damage": {"part": "Headlight", "damage": "Broken", "severity": "CRITICAL"},
    "taillight-damage": {"part": "Taillight", "damage": "Broken", "severity": "CRITICAL"},
    "sidemirror-damage": {"part": "Sidemirror", "damage": "Broken", "severity": "WARNING"},
    "signlight-damage": {"part": "Indicator", "damage": "Broken", "severity": "WARNING"},

    # 4. Paint Damage
    "paint-chip": {"part": "General_Body", "damage": "Paint_Chip", "severity": "WARNING"},
    "paint-trace": {"part": "General_Body", "damage": "Paint_Trace", "severity": "NORMAL"},
}


async def run_exterior_yolo(
    image: Union[str, Image.Image], 
    model
) -> List[Dict]:
    """단일 YOLO 모델로 통합 파손 분석"""
    detections = []
    
    if model is None:
        return []

    try:
        # YOLOv8 추론
        results = model.predict(source=image, save=False, conf=0.25, imgsz=1280)
        
        for r in results:
            for box in r.boxes:
                label_idx = int(box.cls[0])
                # 모델의 names 딕셔너리에서 라벨 이름 가져오기
                if hasattr(model, 'names'):
                    raw_label = model.names[label_idx]
                else:
                    raw_label = str(label_idx)
                
                # 라벨 정규화 (대소문자, 특수문자 등을 유연하게 처리)
                # 예: "Front Bear" -> "front-bear", "Front_Bear" -> "front-bear"
                import re
                # 1. 소문자 변환
                normalized_label = raw_label.lower()
                # 2. 알파벳, 숫자 제외한 모든 문자를 하이픈(-)으로 변경
                normalized_label = re.sub(r'[^a-z0-9]+', '-', normalized_label)
                # 3. 양 끝 하이픈 제거
                normalized_label = normalized_label.strip('-')
                
                # 매핑 정보 조회
                info = UNIFIED_CLASSES.get(normalized_label)
                
                # 매핑되지 않은 라벨이 나올 경우의 처리 (Fallback)
                if not info:
                    # 키를 못 찾았을 때를 대비해 유사 매칭 시도 가능하지만, 일단 Unknown 처리
                    # 혹은 names 리스트의 텍스트 그대로 사용
                    info = {
                        "part": "Unknown",
                        "damage": raw_label,
                        "severity": "WARNING"
                    }

                detections.append({
                    "part": info["part"],
                    "damage_type": info["damage"],
                    "confidence": round(float(box.conf[0]), 2),
                    "bbox": [int(v) for v in box.xywh[0].tolist()], # YOLOv8 xywh is [cx, cy, w, h]
                    "_severity": info["severity"] # Internal use for status calculation
                })

        # Convert [cx, cy, w, h] -> [x, y, w, h] (top-left)
        for d in detections:
            cx, cy, w, h = d["bbox"]
            d["bbox"] = [int(cx - w/2), int(cy - h/2), int(w), int(h)]

    except Exception as e:
        print(f"[Exterior YOLO Error] {e}")
    
    return detections


async def analyze_exterior_image(
    image: Image.Image,
    s3_url: str, 
    exterior_model=None
) -> Dict[str, Any]:
    """
    외관 파손 분석 메인 함수 (Single Model Version)
    
    Args:
        exterior_model: CarDD+CarParts 통합 YOLO 모델
    """
    # Step 0: 모델 없으면 LLM Fallback
    if exterior_model is None:
        print("[Exterior] YOLO 모델 없음, LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "ERROR",
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": False,
                "detections": [],
                "llm_fallback": True
            }
        }
    
    # Step 1: YOLO 추론
    detections = await run_exterior_yolo(image, exterior_model)
    
    # Step 1-1: 파손이 감지되지 않으면, LLM으로 '진짜 외관인지' + '미세 파손은 없는지' 2차 확인 (Safety Net)
    if len(detections) == 0:
        print("[Exterior] 감지된 파손 없음. LLM Safety Check 진행.")
        llm_result = await analyze_general_image(s3_url)
        
        status = "UNKNOWN"
        
        if hasattr(llm_result, "status"):
            status = llm_result.status
            


        # [NEW] 만약 상태가 WARNING/CRITICAL인데 detections가 비어있다면, LLM에게 강제로 라벨링을 요청
        fallback_detections = []
        if status in ["WARNING", "CRITICAL"]:
            print(f"[Exterior] YOLO Miss detected (Status: {status}). Requesting LLM Labeling...")
            from ai.app.services.common.llm_service import generate_training_labels
            label_result = await generate_training_labels(s3_url, "exterior")
            
            for lbl in label_result.get("labels", []):
                # [Fix] Use underscore labels
                part = lbl.get("part", "Unknown").replace(" ", "_")
                damage = lbl.get("damage", "Damage").replace(" ", "_")
                
                # BBox 변환 [x, y, w, h]
                bbox = lbl.get("bbox", [0,0,0,0])
                from ai.app.services.visual.yolo_utils import normalize_to_xywh
                
                fallback_detections.append({
                    "part": part,
                    "damage_type": damage,
                    "confidence": 0.9, # LLM 판단 신뢰도
                    "bbox": normalize_to_xywh(bbox, image.width, image.height)
                })

        return {
            "status": status,
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": (status != "NORMAL"),
                "detections": fallback_detections
            }
        }
    
    # Step 1-2: 신뢰도 체크
    max_confidence = max(d["confidence"] for d in detections)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Exterior] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        status = llm_result.status if hasattr(llm_result, 'status') else "WARNING"
        
        fallback_detections = []
        if status in ["WARNING", "CRITICAL"]:
            print(f"[Exterior] Low Confidence ({max_confidence:.2f}). Requesting LLM Labeling for verification...")
            from ai.app.services.common.llm_service import generate_training_labels
            label_result = await generate_training_labels(s3_url, "exterior")
            
            for lbl in label_result.get("labels", []):
                # [Fix] Use underscore labels
                part = lbl.get("part", "Unknown").replace(" ", "_")
                damage = lbl.get("damage", "Damage").replace(" ", "_")
                
                # BBox 변환 [x, y, w, h]
                bbox = lbl.get("bbox", [0,0,0,0])
                from ai.app.services.visual.yolo_utils import normalize_to_xywh
                
                fallback_detections.append({
                    "part": part,
                    "damage_type": damage,
                    "confidence": 0.85, 
                    "bbox": normalize_to_xywh(bbox, image.width, image.height)
                })

        return {
            "status": status,
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": (status != "NORMAL"),
                "detections": fallback_detections
            }
        }
    
    # Step 2: 심각도 계산 (가장 높은 심각도 기준)
    severity_rank = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
    max_severity = "NORMAL"
    
    for d in detections:
        current_sev = d.get("_severity", "NORMAL")
        if severity_rank[current_sev] > severity_rank[max_severity]:
            max_severity = current_sev
        # Remove internal field
        if "_severity" in d:
            del d["_severity"]
            
            
    # Step 3: LLM 리포트 생성 - 제거됨 (description/repair_estimate가 API 응답에 미포함)
    # 참고: 이 LLM 호출은 토큰만 소모하고 결과가 사용되지 않았음
    
    return {
        "status": max_severity,
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": {
            "damage_found": True,
            "detections": detections
        }
    }
