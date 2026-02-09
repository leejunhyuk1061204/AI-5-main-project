# ai/app/services/dashboard_service.py
"""
계기판 분석 서비스 (Dashboard Analysis) - Type-Safe Standard Implementation

[Architecture]
1. Inference (run_dashboard_yolo): Pure CV model execution.
2. Decision Layer (get_dashboard_decision): Pure logic returns DecisionResult dataclass.
3. Handler Layer (_handle_decision): Side-effects orchestration.

[Outcome Principles]
- Gate Numbering: Integer based (0-4).
- UNKNOWN Philosophy: Honest uncertainty is a first-class result.
"""
from typing import List, Optional, Union, Dict, Any
from PIL import Image
from ai.app.services.common.llm_service import analyze_general_image
from ai.app.services.visual.yolo_utils import normalize_to_xywh, normalize_label
from ai.app.services.visual.domains.dashboard.dashboard_llm_fallback import get_dashboard_decision, DecisionResult

# =============================================================================
# Configuration
# =============================================================================

# Dashboard 경고등 클래스 정의 (10종)
DASHBOARD_CLASSES = {
    "anti_lock_braking_system": {"severity": "WARNING", "color": "YELLOW", "category": "BRAKES", "description": "ABS System Issue"},
    "braking_system_issue": {"severity": "CRITICAL", "color": "RED", "category": "BRAKES", "description": "Brake System Failure"},
    "charging_system_issue": {"severity": "CRITICAL", "color": "RED", "category": "ELECTRICAL", "description": "Charging System Issue"},
    "check_engine": {"severity": "WARNING", "color": "YELLOW", "category": "ENGINE", "description": "Check Engine Required"},
    "electronic_stability_problem_esp": {"severity": "WARNING", "color": "YELLOW", "category": "SAFETY", "description": "ESP System Issue"},
    "engine_overheating_warning_light": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "Engine Overheating"},
    "low_engine_oil_warning_light": {"severity": "CRITICAL", "color": "RED", "category": "ENGINE", "description": "Low Engine Oil Warning"},
    "low_tire_pressure_warning_light": {"severity": "WARNING", "color": "YELLOW", "category": "TIRES", "description": "Low Tire Pressure"},
    "master_warning_light": {"severity": "WARNING", "color": "YELLOW", "category": "GENERAL", "description": "Master Warning Active"},
    "srs_airbag": {"severity": "CRITICAL", "color": "RED", "category": "SAFETY", "description": "Airbag System Issue"},
}


async def run_dashboard_yolo(
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
                label_info = DASHBOARD_CLASSES.get(norm_label, {})

                detections.append({
                    "cls": label_idx,
                    "label": norm_label,
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
    """Main Orchestrator following the standardized pattern"""
    
    # [Step 0] Fast Path: No Model
    if yolo_model is None:
        return await _handle_llm_fallback(s3_url)

    # [Step 1] Inference
    detections = await run_dashboard_yolo(image, yolo_model)
    
    # [Step 2] Decision Layer (Pure Logic)
    decision = get_dashboard_decision(
        detections=detections,
        image_width=image.width,
        image_height=image.height,
        class_names=yolo_model.names
    )
    
    # [Step 3] Handler Layer (Side Effects & Final Assembly)
    return await _handle_decision(decision, detections, image, s3_url)


# =============================================================================
# Handler Layer (Side Effects & Final Assembly)
# =============================================================================

async def _handle_decision(decision: DecisionResult, detections: List[Dict], image: Image.Image, s3_url: str) -> Dict[str, Any]:
    """Execute final action based on DecisionResult status"""
    
    # [Action A] AL Trigger (Gate 4)
    if decision.gate == 4:
        print(f"[Dashboard] Gate 4 AL Triggered (Conf: {decision.confidence:.2f})")
        await _trigger_al_collection(s3_url, decision.confidence)

    # [Action B] Approved Results (Gates 1, 2)
    if decision.status == "APPROVED":
        return _build_approved_response(decision, detections)

    # [Action C] Missing Results (Gate 0)
    if decision.status == "MISS":
        return await _handle_safety_net(image, s3_url)

    # [Action D] Uncertain Flow (Gates 3, 4) -> Needs LLM
    return await _handle_uncertain_flow(decision, detections, s3_url, image)


def _build_approved_response(decision: DecisionResult, detections: List[Dict]) -> Dict:
    """Final assembly for high-confidence detections"""
    matched = next((d for d in detections if d["label"] == decision.label), detections[0])
    label_info = DASHBOARD_CLASSES.get(matched["label"], {})
    
    return {
        "status": label_info.get("severity", "WARNING"),
        "analysis_type": "SCENE_DASHBOARD",
        "category": "DASHBOARD",
        "data": {
            "detected_count": 1,
            "detections": [matched],
            "decision_info": {
                "gate": decision.gate,
                "reason": decision.reason,
                "confidence": decision.confidence
            }
        }
    }


async def _handle_safety_net(image: Image.Image, s3_url: str) -> Dict:
    """Safety check for MISS status"""
    llm_result = await analyze_general_image(s3_url)
    status = getattr(llm_result, "status", "UNKNOWN")
    
    collected = []
    if status in ["WARNING", "CRITICAL"]:
        collected = await _run_llm_labeling_for_miss(s3_url, image, status)
        
    return {
        "status": status,
        "analysis_type": "SCENE_DASHBOARD",
        "category": "DASHBOARD",
        "data": {
            "detected_count": len(collected),
            "detections": collected,
            "safety_net_triggered": True,
            "note": "UNKNOWN은 실패가 아니라, 시스템이 정직하게 말한 결과다."
        }
    }


async def _handle_uncertain_flow(decision: DecisionResult, detections: List[Dict], s3_url: str, image: Image.Image) -> Dict:
    """Verification for UNCERTAIN status"""
    llm_result = await analyze_general_image(s3_url)
    llm_status = getattr(llm_result, "status", "WARNING")
    
    return {
        "status": llm_status,
        "analysis_type": "SCENE_DASHBOARD",
        "category": "DASHBOARD",
        "data": {
            "detected_count": len(detections),
            "detections": detections,
            "verification": "llm_verification_triggered",
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
        "analysis_type": "SCENE_DASHBOARD",
        "category": "DASHBOARD",
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
        oracle_labels = await generate_training_labels(s3_url, "dashboard")
        if oracle_labels and oracle_labels.get("labels"):
            label_key = al_service.save_oracle_label(s3_url, oracle_labels, "dashboard")
            if label_key:
                al_service.record_manifest(s3_url=s3_url, category="DASHBOARD", label_key=label_key,
                                        status=oracle_labels.get("status", "UNKNOWN"), confidence=confidence,
                                        analysis_type="LLM_ORACLE_DASHBOARD", domain="visual")
    except Exception as e:
        print(f"[AL Error] {e}")


async def _run_llm_labeling_for_miss(s3_url: str, image: Image.Image, status: str) -> List[Dict]:
    try:
        from ai.app.services.common.llm_service import generate_training_labels
        from ai.app.services.common.active_learning_service import get_active_learning_service
        al_service = get_active_learning_service()
        label_result = await generate_training_labels(s3_url, "dashboard")
        collected = []
        for lbl in label_result.get("labels", []):
            pixel_bbox = normalize_to_xywh(lbl.get("bbox", [0, 0, 1, 1]), image.width, image.height)
            norm_label = normalize_label(lbl.get("part", "Unknown"))
            collected.append({
                "label": norm_label,
                "color_severity": "RED" if status == "CRITICAL" else "YELLOW",
                "confidence": 0.85, 
                "bbox": pixel_bbox
            })
        label_key = al_service.save_oracle_label(s3_url, label_result, "dashboard")
        if label_key:
            al_service.record_manifest(s3_url=s3_url, category="DASHBOARD", label_key=label_key,
                                    status=status, confidence=0.1, analysis_type="LLM_ORACLE_d_MISS", domain="visual")
        return collected
    except Exception as e:
        print(f"[Miss Labeling Error] {e}")
        return []
