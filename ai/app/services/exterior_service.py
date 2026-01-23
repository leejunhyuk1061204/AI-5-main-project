# ai/app/services/exterior_service.py
"""
외관 파손 분석 서비스 (Exterior Damage Analysis)

[역할]
1. 차량 부위 감지: 12가지 주요 외판 부위를 식별합니다. (YOLO)
2. 파손 타입 감지: 6가지 파손 종류(스크래치, 찌그러짐 등)를 탐지합니다. (YOLO)
3. 공간 매핑: IoU를 기반으로 '어느 부위'에 '어떤 파손'이 있는지 판단합니다.
4. 리포트 생성: LLM을 통해 사용자에게 자연스러운 파손 리포트를 제공합니다.

[주요 기능]
- 파손 및 부위 동시 탐지 (run_exterior_yolo)
- 부위-파손 매핑 로직 (spatial_mapping)
- 외관 종합 진단 (analyze_exterior_image)
"""
from typing import List, Optional, Dict, Tuple, Union
from PIL import Image
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.services.llm_service import analyze_general_image, generate_exterior_report
from ai.app.services.router_service import CONFIDENCE_THRESHOLD

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9  # 이 값 이상이면서 NORMAL이면 LLM 건너뜀

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
    """
    두 BBox의 IoU(Intersection over Union) 계산
    
    Args:
        box1, box2: [x_center, y_center, width, height] 형식
    """
    # xywh to xyxy 변환
    x1_1, y1_1 = box1[0] - box1[2]/2, box1[1] - box1[3]/2
    x2_1, y2_1 = box1[0] + box1[2]/2, box1[1] + box1[3]/2
    
    x1_2, y1_2 = box2[0] - box2[2]/2, box2[1] - box2[3]/2
    x2_2, y2_2 = box2[0] + box2[2]/2, box2[1] + box2[3]/2
    
    # Intersection
    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)
    
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    
    # Union
    area1 = box1[2] * box1[3]
    area2 = box2[2] * box2[3]
    union_area = area1 + area2 - inter_area
    
    return inter_area / union_area if union_area > 0 else 0


async def run_exterior_yolo(
    image: Union[str, Image.Image], 
    cardd_model, 
    carparts_model
) -> Tuple[List[DetectionItem], List[DetectionItem]]:
    """
    두 YOLO 모델로 외관 분석
    
    Args:
        image: S3 URL 또는 PIL Image 객체
    """
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
                    damages.append(DetectionItem(
                        label=label_name,
                        confidence=round(float(box.conf[0]), 2),
                        bbox=[int(v) for v in box.xywh[0].tolist()]
                    ))
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
                    parts.append(DetectionItem(
                        label=label_name,
                        confidence=round(float(box.conf[0]), 2),
                        bbox=[int(v) for v in box.xywh[0].tolist()]
                    ))
        except Exception as e:
            print(f"[Exterior CarParts Error] {e}")
    
    return damages, parts


def spatial_mapping(
    damages: List[DetectionItem], 
    parts: List[DetectionItem],
    iou_threshold: float = 0.1
) -> List[Dict]:
    """
    파손과 부위의 공간적 매핑 (IoU 기반)
    
    Returns:
        List of {"part": "...", "damage": "...", "severity": "..."}
    """
    mappings = []
    
    for damage in damages:
        best_match = None
        best_iou = 0.0
        
        for part in parts:
            iou = calculate_iou(damage.bbox, part.bbox)
            if iou > best_iou and iou >= iou_threshold:
                best_iou = iou
                best_match = part
        
        damage_info = CARDD_DAMAGE_CLASSES.get(damage.label.lower(), {})
        part_name = best_match.label if best_match else "Unknown_Area"
        part_name_kr = CAR_PARTS_CLASSES.get(part_name, part_name)
        
        mappings.append({
            "part": part_name,
            "part_kr": part_name_kr,
            "damage": damage.label,
            "damage_kr": damage_info.get("description", damage.label),
            "severity": damage_info.get("severity", "WARNING"),
            "repair": damage_info.get("repair", "점검 필요"),
            "confidence": damage.confidence
        })
    
    return mappings


# generate_exterior_report 함수를 llm_service로 이전 완료


async def analyze_exterior_image(
    image: Image.Image,
    s3_url: str, 
    cardd_model=None, 
    carparts_model=None
) -> VisualResponse:
    """
    외관 파손 분석 메인 함수 (pre-loaded image 사용)
    """
    # Step 0: 두 모델 모두 없으면 LLM Fallback
    if cardd_model is None and carparts_model is None:
        print("[Exterior] YOLO 모델 없음, LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 1: 이중 YOLO 감지
    damages, parts = await run_exterior_yolo(image, cardd_model, carparts_model)
    
    # Step 1-1: 파손 없으면 정상
    if len(damages) == 0:
        return VisualResponse(
            status="NORMAL",
            analysis_type="SCENE_EXTERIOR",
            category="EXTERIOR",
            detected_count=0,
            detections=[],
            description="외관에서 파손이 감지되지 않았습니다.",
            recommendation=None,
            processed_image_url=s3_url
        )
    
    # Step 1-2: 신뢰도 체크
    max_confidence = max(d.confidence for d in damages)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Exterior] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        return await analyze_general_image(s3_url)
    
    # Step 2: Spatial Mapping
    mappings = spatial_mapping(damages, parts)
    
    # Step 3: 심각도 계산
    max_severity = "NORMAL"
    for m in mappings:
        if m["severity"] == "CRITICAL":
            max_severity = "CRITICAL"
            break
        elif m["severity"] == "WARNING":
            max_severity = "WARNING"
    
    # Step 4: LLM 리포트 생성 (Fast Path 적용: NORMAL이고 신뢰도 높으면 스킵)
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_THRESHOLD:
        print(f"[Exterior] Fast Path 적용 (신뢰도: {max_confidence:.2f}). LLM 스킵.")
        description = "차량 외관에서 눈에 띄는 파손이나 스크래치가 감지되지 않았습니다."
        recommendation = "청결한 외관 유지를 위해 주기적인 세차를 권장합니다."
    else:
        report = await generate_exterior_report(mappings)
        description = report.get("description", "")
        recommendation = report.get("recommendation", "")
    
    # 전체 detections 합치기
    all_detections = damages + parts
    
    return VisualResponse(
        status=max_severity,
        analysis_type="SCENE_EXTERIOR",
        category="EXTERIOR",
        detected_count=len(damages),
        detections=all_detections,
        description=description,
        recommendation=recommendation,
        processed_image_url=s3_url
    )
