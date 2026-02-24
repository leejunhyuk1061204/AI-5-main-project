# ai/app/services/exterior_service.py
"""
외관 파손 분석 서비스 (Exterior Damage Analysis) - Type-Safe Standard Implementation

[Architecture]
1. Inference (run_exterior_yolo): Pure CV model execution.
2. Decision Layer (get_exterior_decision): Pure logic in exterior_llm_fallback.py.
3. Handler Layer (_handle_decision): Side-effects orchestration (LLM, Active Learning).

[Outcome Principles]
- Gate Numbering: Integer based (0-4).
- UNKNOWN Philosophy: Honest uncertainty is a first-class result.
"""
"""
차량 외관(Exterior) 손상 진단 메인 서비스

차량의 범퍼, 도어, 펜더, 유리 등 외판 부위의 결함을 정밀 스캔하는 서비스입니다.
주요 프로세스:
1. 1280 해상도의 고화질 이미지를 분석하여 미세 스크래치 탐지력 강화
2. YOLOv11m 모델 기반 6종 통합 시스템(Glass, Light, Bumper, Body, Surface, Mirror) 분석
3. 이상 탐지 시 실시간 Decision Layer를 통해 즉각 통보 또는 정밀 폴백 분석 수행
"""
import logging
from typing import List, Optional, Union, Dict, Any
from PIL import Image
from ai.app.services.common.llm_service import analyze_general_image
from ai.app.services.visual.yolo_utils import normalize_to_xywh, normalize_label
from ai.app.services.visual.domains.exterior.exterior_llm_fallback import (
    get_exterior_decision, 
    DecisionResult, 
    UNIFIED_CLASSES
)

# =============================================================================
# Configuration
# =============================================================================

# (Removed EXTERIOR_AL_CONF: AL is now powered by Decision Layer's Gate 4)

async def run_exterior_yolo(
    image: Union[str, Image.Image], 
    yolo_model
) -> List[Dict]:
    """Pure YOLO Inference with normalized output labels"""
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
                x1, y1, w, h = box.xywh[0].tolist()
                
                norm_label = normalize_label(label_name)
                info = UNIFIED_CLASSES.get(norm_label, {"part": "Unknown", "damage": norm_label, "severity": "WARNING"})

                # YOLOv8 xywh is [cx, cy, w, h] -> convert to [x, y, w, h] (top-left)
                detections.append({
                    "cls": label_idx,
                    "label": norm_label,
                    "part": info["part"],
                    "damage_type": info["damage"],
                    "severity": info["severity"],
                    "confidence": round(confidence, 2),
                    "bbox": [int(x1 - w/2), int(y1 - h/2), int(w), int(h)]
                })
        return detections
    except Exception as e:
        print(f"[Exterior YOLO Error] {e}")
        return []


async def analyze_exterior_image(
    image: Image.Image,
    s3_url: str, 
    exterior_model=None
) -> Dict[str, Any]:
    """Main Orchestrator following the standardized pattern"""
    
    # [Step 0] Fast Path: No Model
    if exterior_model is None:
        return await _handle_llm_fallback(s3_url)

    # [Step 1] Inference
    detections = await run_exterior_yolo(image, exterior_model)
    
    # [Step 2] Decision Layer (Pure Logic)
    decision = get_exterior_decision(
        detections=detections,
        image_width=image.width,
        image_height=image.height,
        class_names=exterior_model.names
    )
    
    # [Step 3] Handler Layer (Orchestration & Side Effects)
    return await _handle_decision(decision, detections, image, s3_url)


# =============================================================================
# Handler Layer (Side Effects & Final Assembly)
# =============================================================================

async def _handle_decision(decision: DecisionResult, detections: List[Dict], image: Image.Image, s3_url: str) -> Dict[str, Any]:
    """Execute final action based on DecisionResult status"""
    status = decision.status
    
    # [Action A] AL Trigger (Gate 4: Low-confidence but high learning-value samples)
    if decision.gate == 4:
        print(f"[Exterior] Gate 4 AL Triggered (Conf: {decision.confidence:.2f})")
        await _trigger_al_collection(s3_url, decision.confidence)

    # [Action B] Approved Results (Gates 1, 2)
    if status == "APPROVED":
        return _build_approved_response(decision, detections)

    # [Action C] Missing Results (Gate 0)
    if status == "MISS":
        return await _handle_safety_net(image, s3_url)

    # [Action D] Uncertain Flow (Gates 3, 4) -> Needs LLM
    print(f"[Exterior] Uncertain status: {decision.reason} (Gate: {decision.gate}) -> Escalating to LLM")
    return await _handle_uncertain_flow(decision, detections, s3_url, image)


def _build_approved_response(decision: DecisionResult, detections: List[Dict]) -> Dict:
    """Final assembly for approved exterior detections"""
    # Calculate overall status based on highest severity among detections
    severity_rank = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
    max_severity = "NORMAL"
    
    formatted_detections = []
    for d in detections:
        # We only include the relevant detection if single output requested, 
        # but usually exterior returns all found damages.
        # For simplicity and consistency with old behavior, return all.
        max_severity = max(max_severity, d["severity"], key=lambda x: severity_rank.get(x, 0))
        
        # Clean up internal fields
        clean_d = d.copy()
        if "severity" in clean_d: del clean_d["severity"]
        if "cls" in clean_d: del clean_d["cls"]
        if "label" in clean_d: del clean_d["label"]
        formatted_detections.append(clean_d)

    return {
        "status": max_severity,
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": {
            "damage_found": (max_severity != "NORMAL"),
            "detections": formatted_detections,
            "decision_info": {
                "gate": decision.gate,
                "reason": decision.reason,
                "confidence": decision.confidence
            }
        }
    }


async def _handle_safety_net(image: Image.Image, s3_url: str) -> Dict:
    """Safety check for MISS status - uses LLM Oracle"""
    print("[Exterior] Running Safety Net (LLM Oracle)")
    llm_result = await analyze_general_image(s3_url)
    status = getattr(llm_result, "status", "UNKNOWN")
    
    collected = []
    if status in ["WARNING", "CRITICAL"]:
        collected = await _run_llm_labeling_for_miss(s3_url, image, status)
        
    return {
        "status": status,
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": {
            "damage_found": (status != "NORMAL"),
            "detections": collected,
            "safety_net_triggered": True,
            "note": "UNKNOWN은 실패가 아니라, 시스템이 정직하게 말한 결과다."
        }
    }


async def _handle_uncertain_flow(decision: DecisionResult, detections: List[Dict], s3_url: str, image: Image.Image) -> Dict:
    """Verification for UNCERTAIN status"""
    llm_result = await analyze_general_image(s3_url)
    llm_status = getattr(llm_result, "status", "WARNING")
    
    # [Policy] 
    # Gate 3 (Middle zone/Critical): Verification only.
    # Gate 4 (Low confidence): Verification + Re-labeling (Oracle) to strengthen training data.
    final_detections = detections
    if llm_status in ["WARNING", "CRITICAL"] and decision.gate == 4:
         print("[Exterior] Gate 4 sample confirmed by LLM. Refreshing labels for high-value retraining data.")
         final_detections = await _run_llm_labeling_for_miss(s3_url, image, llm_status)

    return {
        "status": llm_status,
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": {
            "damage_found": (llm_status != "NORMAL"),
            "detections": final_detections,
            "verification_triggered": True,
            "decision_info": {
                "gate": decision.gate,
                "reason": decision.reason,
                "confidence": decision.confidence
            },
            "note": "UNKNOWN은 실패가 아니라, 시스템이 정직하게 말한 결과다." if llm_status == "UNKNOWN" else None
        }
    }


async def _handle_llm_fallback(s3_url: str) -> Dict:
    """Emergency LLM-only path"""
    llm_result = await analyze_general_image(s3_url)
    return {
        "status": getattr(llm_result, "status", "ERROR"),
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": { "llm_fallback_only": True }
    }


# =============================================================================
# Side Effects (AL & Specialized Labeling)
# =============================================================================

async def _trigger_al_collection(s3_url: str, confidence: float):
    try:
        from ai.app.services.common.llm_service import generate_training_labels
        from ai.app.services.common.active_learning_service import get_active_learning_service
        al_service = get_active_learning_service()
        oracle_labels = await generate_training_labels(s3_url, "exterior")
        if oracle_labels and oracle_labels.get("labels"):
            label_key = al_service.save_oracle_label(s3_url, oracle_labels, "exterior")
            if label_key:
                al_service.record_manifest(s3_url=s3_url, category="EXTERIOR", label_key=label_key,
                                        status=oracle_labels.get("status", "UNKNOWN"), confidence=confidence,
                                        analysis_type="LLM_ORACLE_EXTERIOR", domain="visual")
    except Exception as e:
        print(f"[AL Error] {e}")


async def _run_llm_labeling_for_miss(s3_url: str, image: Image.Image, status: str) -> List[Dict]:
    try:
        from ai.app.services.common.llm_service import generate_training_labels
        from ai.app.services.common.active_learning_service import get_active_learning_service
        al_service = get_active_learning_service()
        label_result = await generate_training_labels(s3_url, "exterior")
        collected = []
        for lbl in label_result.get("labels", []):
            pixel_bbox = normalize_to_xywh(lbl.get("bbox", [0, 0, 1, 1]), image.width, image.height)
            part = normalize_label(lbl.get("part", "Unknown"))
            damage = normalize_label(lbl.get("damage", "Damage"))
            
            collected.append({
                "part": part,
                "damage_type": damage,
                "confidence": 0.90, 
                "bbox": pixel_bbox
            })
        label_key = al_service.save_oracle_label(s3_url, label_result, "exterior")
        if label_key:
            al_service.record_manifest(s3_url=s3_url, category="EXTERIOR", label_key=label_key,
                                    status=status, confidence=0.1, analysis_type="LLM_ORACLE_e_MISS", domain="visual")
        return collected
    except Exception as e:
        print(f"[Miss Labeling Error] {e}")
        return []
