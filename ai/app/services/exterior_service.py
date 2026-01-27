# ai/app/services/exterior_service.py
"""
외관 파손 분석 서비스 (Exterior Damage Analysis)

[파일 설명]
이 파일은 차량 외관 이미지를 분석하여 파손 부위와 종류를 탐지하는 서비스입니다.
CarDD 모델로 6종 파손을 감지하고, CarParts 모델로 12종 부위를 식별한 후,
IoU 기반으로 "어느 부위에 어떤 파손"인지 매핑합니다.

[API 응답 형식]
{
  "status": "WARNING",
  "analysis_type": "SCENE_EXTERIOR",
  "category": "EXTERIOR",
  "data": {
    "damage_found": true,
    "detections": [{ part, damage_type, confidence, bbox }],
    "description": "앞 범퍼 하단에 긁힘 손상이 있습니다.",
    "repair_estimate": "부분 도색 권장"
  }
}
"""
from typing import List, Optional, Dict, Tuple, Union, Any
from PIL import Image
from ai.app.services.llm_service import analyze_general_image, generate_exterior_report
from ai.app.services.router_service import CONFIDENCE_THRESHOLD

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9

# =============================================================================
# Car Parts 클래스 (12종 부위)
# =============================================================================
CAR_PARTS_CLASSES = {
    "Front_Bumper": "앞 범퍼",
    "Rear_Bumper": "뒷 범퍼",
    "Hood": "후드(본넷)",
    "Front_Door_L": "앞문 좌측",
    "Front_Door_R": "앞문 우측",
    "Rear_Door_L": "뒷문 좌측",
    "Rear_Door_R": "뒷문 우측",
    "Fender_L": "펜더 좌측",
    "Fender_R": "펜더 우측",
    "Quarter_Panel_L": "쿼터패널 좌측",
    "Quarter_Panel_R": "쿼터패널 우측",
    "Trunk_Lid": "트렁크",
    "Roof": "지붕",
    "Side_Mirror": "사이드미러",
}

# =============================================================================
# CarDD 파손 타입 클래스 (6종)
# =============================================================================
CARDD_DAMAGE_CLASSES = {
    "dent": {"severity": "WARNING", "description": "찌그러짐", "repair": "판금 도색"},
    "scratch": {"severity": "WARNING", "description": "스크래치", "repair": "부분 도색"},
    "crack": {"severity": "CRITICAL", "description": "균열/파손", "repair": "부품 교체"},
    "glass_shatter": {"severity": "CRITICAL", "description": "유리 파손", "repair": "유리 교체"},
    "lamp_broken": {"severity": "CRITICAL", "description": "램프 파손", "repair": "램프 교체"},
    "tire_flat": {"severity": "CRITICAL", "description": "타이어 펑크", "repair": "타이어 교체"},
}


def calculate_iou(box1: List[int], box2: List[int]) -> float:
    """두 BBox의 IoU 계산 (xywh 형식)"""
    x1_1, y1_1 = box1[0] - box1[2]/2, box1[1] - box1[3]/2
    x2_1, y2_1 = box1[0] + box1[2]/2, box1[1] + box1[3]/2
    
    x1_2, y1_2 = box2[0] - box2[2]/2, box2[1] - box2[3]/2
    x2_2, y2_2 = box2[0] + box2[2]/2, box2[1] + box2[3]/2
    
    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)
    
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    
    area1 = box1[2] * box1[3]
    area2 = box2[2] * box2[3]
    union_area = area1 + area2 - inter_area
    
    return inter_area / union_area if union_area > 0 else 0


async def run_exterior_yolo(
    image: Union[str, Image.Image], 
    cardd_model, 
    carparts_model
) -> Tuple[List[Dict], List[Dict]]:
    """두 YOLO 모델로 외관 분석"""
    damages = []
    parts = []
    
    # CarDD 파손 감지
    if cardd_model is not None:
        try:
            results = cardd_model.predict(source=image, save=False, conf=0.25)
            for r in results:
                for box in r.boxes:
                    label_idx = int(box.cls[0])
                    label_name = cardd_model.names[label_idx]
                    damages.append({
                        "label": label_name,
                        "confidence": round(float(box.conf[0]), 2),
                        "bbox": [int(v) for v in box.xywh[0].tolist()]
                    })
        except Exception as e:
            print(f"[Exterior CarDD Error] {e}")
    
    # Car Parts 부위 감지
    if carparts_model is not None:
        try:
            results = carparts_model.predict(source=image, save=False, conf=0.25)
            for r in results:
                for box in r.boxes:
                    label_idx = int(box.cls[0])
                    label_name = carparts_model.names[label_idx]
                    parts.append({
                        "label": label_name,
                        "confidence": round(float(box.conf[0]), 2),
                        "bbox": [int(v) for v in box.xywh[0].tolist()]
                    })
        except Exception as e:
            print(f"[Exterior CarParts Error] {e}")
    
    return damages, parts


def spatial_mapping(
    damages: List[Dict], 
    parts: List[Dict],
    iou_threshold: float = 0.1
) -> List[Dict]:
    """파손과 부위의 공간적 매핑 (IoU 기반)"""
    mappings = []
    
    for damage in damages:
        best_match = None
        best_iou = 0.0
        
        for part in parts:
            iou = calculate_iou(damage["bbox"], part["bbox"])
            if iou > best_iou and iou >= iou_threshold:
                best_iou = iou
                best_match = part
        
        damage_info = CARDD_DAMAGE_CLASSES.get(damage["label"].lower(), {})
        part_name = best_match["label"] if best_match else "Unknown_Area"
        
        # API 명세서 형식에 맞춤
        mappings.append({
            "part": part_name,
            "damage_type": damage_info.get("description", damage["label"]),
            "confidence": damage["confidence"],
            "bbox": damage["bbox"]
        })
    
    return mappings


async def analyze_exterior_image(
    image: Image.Image,
    s3_url: str, 
    cardd_model=None, 
    carparts_model=None
) -> Dict[str, Any]:
    """
    외관 파손 분석 메인 함수
    
    Returns:
        API 명세서 형식의 응답 딕셔너리
    """
    # Step 0: 두 모델 모두 없으면 LLM Fallback
    if cardd_model is None and carparts_model is None:
        print("[Exterior] YOLO 모델 없음, LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "ERROR",
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": False,
                "detections": [],
                "description": llm_result.data.get("description") if hasattr(llm_result, 'data') else "이미지 분석 실패",
                "repair_estimate": llm_result.data.get("recommendation") if hasattr(llm_result, 'data') else "전문가 점검 권장",
                "llm_fallback": True
            }
        }
    
    # Step 1: 이중 YOLO 감지
    damages, parts = await run_exterior_yolo(image, cardd_model, carparts_model)
    
    # Step 1-1: 파손 없으면 정상
    if len(damages) == 0:
        return {
            "status": "NORMAL",
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": False,
                "detections": [],
                "description": "외관에서 파손이 감지되지 않았습니다.",
                "repair_estimate": None
            }
        }
    
    # Step 1-2: 신뢰도 체크
    max_confidence = max(d["confidence"] for d in damages)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Exterior] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "WARNING",
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": True,
                "detections": [],
                "description": llm_result.data.get("description") if hasattr(llm_result, 'data') else "신뢰할 수 없는 분석 결과",
                "repair_estimate": llm_result.data.get("recommendation") if hasattr(llm_result, 'data') else "정교한 재촬영 권장",
                "llm_fallback": True
            }
        }
    
    # Step 2: Spatial Mapping (부위-파손 매핑)
    detections = spatial_mapping(damages, parts)
    
    # Step 3: 심각도 계산
    max_severity = "NORMAL"
    for damage in damages:
        damage_info = CARDD_DAMAGE_CLASSES.get(damage["label"].lower(), {})
        if damage_info.get("severity") == "CRITICAL":
            max_severity = "CRITICAL"
            break
        elif damage_info.get("severity") == "WARNING":
            max_severity = "WARNING"
    
    # Step 4: LLM 리포트 생성 (Fast Path 적용)
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_THRESHOLD:
        description = "차량 외관에서 눈에 띄는 파손이나 스크래치가 감지되지 않았습니다."
        repair_estimate = None
    else:
        # LLM 전달용 데이터 정제
        mapping_for_llm = []
        for det in detections:
            mapping_for_llm.append({
                "part": det["part"],
                "damage": det["damage_type"],
                "severity": max_severity
            })
        
        report = await generate_exterior_report(mapping_for_llm)
        description = report.get("description", "")
        repair_estimate = report.get("recommendation", "")
    
    # API 명세서 형식에 맞춤
    return {
        "status": max_severity,
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": {
            "damage_found": True,
            "detections": detections,
            "description": description,
            "repair_estimate": repair_estimate
        }
    }
