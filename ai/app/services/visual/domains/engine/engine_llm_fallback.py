# ai/app/services/visual/domains/engine/engine_llm_fallback.py
"""
엔진룸 부품 분석용 LLM 폴백(Fall-back) 및 의사결정 레이어

엔진룸 내 26종(또는 통합 8종) 주요 구성 요소의 상태를 YOLO 모델이 분석한 후,
그 결과가 불충분하거나 오류 가능성이 보일 때 작동합니다.
주요 기능:
1. 부품 식별 점수가 임계치 미만일 때 LLM 상세 육안 검사 모드 전환
2. 누유, 부식 등 미세 결함에 대한 다각도 검증 로직
"""
"""
Production-Grade LLM Agreement Fallback for Engine Detection

[핵심 원칙]
1. Valid Detection Filtering (bbox area, confidence)
2. Ambiguity Detection (top1 - top2 < delta)
3. Restricted LLM Role (agreement only, no new labels)
4. Separated Confidence (model_confidence vs decision_confidence)
5. UNKNOWN Fallback (LLM disagreement or error)

[Reference]
Based on 10-year production experience with YOLO + LLM hybrid systems
"""
import logging
from typing import List, Dict, Optional
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration - Layered Gate Structure (Production-Grade)
# =============================================================================

# Gate 1a: Low Confidence
T_LOW = 0.50    # Below this = UNKNOWN (low_conf)

# Gate 1b: Part Detection Certainty
T_PART_MIN = 0.70   # Below this = UNKNOWN (part_uncertain, HIGH priority retraining)

# Gate 2: High Confidence
T_HIGH = 0.75   # High confidence - Accept without LLM

# Gate 3: Middle Zone Strategy (T_PART_MIN <= conf < T_HIGH)
CRITICAL_PARTS = {
    "Battery",
    "Brake_Fluid_Reservoir", 
    "Brake_Master_Cylinder",
    "Engine_Oil_Fill_Cap",
    "Coolant_Reservoir"
}  # Critical parts use LLM verification in middle zone

T_AMB_SKIP_LLM = 0.72  # Non-critical + clear + >= this → ACCEPT (no LLM)
# NOTE: Must be >= T_PART_MIN (0.70) to be reachable!

# Gate 4: LLM Agreement Thresholds
T_LLM_ACCEPT = 0.65      # If LLM agrees AND conf >= this, ACCEPT
FALLBACK_ACCEPT = 0.70   # If LLM unavailable, accept if conf >= this

# Gate 0: BBox Validation
MIN_BBOX_AREA_RATIO = 0.01  # 1% of image
MAX_BBOX_AREA_RATIO = 0.50  # 50% of image
MIN_CONF_FOR_CANDIDATE = 0.30  # Minimum to be considered

# Ambiguity Detection
AMBIGUITY_DELTA = 0.10  # If top1 - top2 < 0.1 → ambiguous

# =============================================================================
# Helper Functions
# =============================================================================

def calculate_bbox_area_ratio(bbox: List[float], image_width: int, image_height: int) -> float:
    """
    Calculate bbox area as ratio of image area
    
    Args:
        bbox: [x_center, y_center, width, height] in absolute pixels
        image_width: Image width
        image_height: Image height
    
    Returns:
        area_ratio: bbox_area / image_area
    """
    bbox_area = bbox[2] * bbox[3]  # width * height
    image_area = image_width * image_height
    return bbox_area / image_area if image_area > 0 else 0.0


def is_valid_detection(
    detection: Dict,
    image_width: int,
    image_height: int
) -> bool:
    """
    Filter out invalid/noise detections
    
    Invalid cases:
    - Too small (noise, artifacts)
    - Too large (full image crop)
    - Low confidence
    
    Args:
        detection: {cls, conf, bbox, ...}
        image_width, image_height: Image dimensions
    
    Returns:
        True if valid detection
    """
    conf = detection.get('confidence', detection.get('conf', 0.0))
    bbox = detection.get('bbox', [0, 0, 1, 1])  # [x, y, w, h]
    
    # Confidence check
    if conf < MIN_CONF_FOR_CANDIDATE:
        return False
    
    # BBox area check
    area_ratio = calculate_bbox_area_ratio(bbox, image_width, image_height)
    
    if area_ratio < MIN_BBOX_AREA_RATIO:
        logger.debug(f"Filtered: Too small (area={area_ratio:.4f})")
        return False
    
    if area_ratio > MAX_BBOX_AREA_RATIO:
        logger.debug(f"Filtered: Too large (area={area_ratio:.4f})")
        return False
    
    return True


def is_ambiguous(candidates: List[Dict]) -> bool:
    """
    Check if model is uncertain between top predictions
    
    Args:
        candidates: List of valid detections sorted by confidence
    
    Returns:
        True if top1 and top2 are too close (ambiguous zone)
    """
    if len(candidates) < 2:
        return False
    
    top1_conf = candidates[0].get('confidence', candidates[0].get('conf', 0.0))
    top2_conf = candidates[1].get('confidence', candidates[1].get('conf', 0.0))
    
    delta = top1_conf - top2_conf
    
    if delta < AMBIGUITY_DELTA:
        logger.info(f"Ambiguous: top1={top1_conf:.2f}, top2={top2_conf:.2f}, delta={delta:.2f}")
        return True
    
    return False


# =============================================================================
# Main Fallback Logic
# =============================================================================

def llm_agreement_fallback(
    detections: List[Dict],
    image_width: int,
    image_height: int,
    class_names: Dict[int, str],
    crop_image: Optional[Image.Image] = None,
    llm_client: Optional[any] = None
) -> Dict:
    """
    Production-grade LLM agreement fallback
    
    Pipeline:
    1. Filter valid detections (bbox area, confidence)
    2. Sort by confidence → Top-K candidates
    3. Check confidence zones:
       - HIGH (>=0.75): Accept model
       - LOW (<0.50): Reject as UNKNOWN
       - MID: Use LLM agreement
    4. LLM asks: "Is top prediction CONSISTENT with visual evidence?"
    5. Decision rule: boost confidence if LLM agrees
    
    Args:
        detections: Raw YOLO detections
        image_width, image_height: Image dimensions
        class_names: {cls_id: class_name}
        crop_image: PIL Image for LLM (optional)
        llm_client: LLM client (optional)
    
    Returns:
        {
            "label": str,
            "model_confidence": float,
            "decision_confidence": float,
            "source": str,
            "llm_agreement": bool (optional),
            "llm_reason": str (optional)
        }
    """
    
    # Step 1: Filter valid detections
    valid_detections = [
        d for d in detections
        if is_valid_detection(d, image_width, image_height)
    ]
    
    if not valid_detections:
        logger.warning("No valid detections after filtering")
        return {
            "label": "UNKNOWN",
            "model_confidence": 0.0,
            "decision_confidence": 0.0,
            "source": "no_valid_detections"
        }
    
    # Step 2: Sort by confidence → Top-3 candidates
    candidates = sorted(
        valid_detections,
        key=lambda x: x.get('confidence', x.get('conf', 0.0)),
        reverse=True
    )[:3]
    
    top = candidates[0]
    top_conf = top.get('confidence', top.get('conf', 0.0))
    top_cls = int(top.get('cls', top.get('class', 0)))
    top_label = class_names.get(top_cls, f"class_{top_cls}")
    
    
    # =========================================================================
    # Gate 1a: Low Confidence (General Model Uncertainty)
    # =========================================================================
    if top_conf < T_LOW:
        logger.warning(f"Gate 1a FAIL: Low confidence - {top_label} conf={top_conf:.2f} < {T_LOW}")
        return {
            "label": "UNKNOWN",
            "model_confidence": top_conf,
            "decision_confidence": None,
            "source": "model_low_conf",
            "reason_tag": "gate1a_low_conf",
            "gate": "low_confidence",
            "hard_sample": True,
            "retraining_priority": "MEDIUM"  # General low confidence
        }
    
    logger.info(f"Gate 1a PASS: Conf={top_conf:.2f} >= {T_LOW}")
    
    # =========================================================================
    # Gate 1b: Part Detection Certainty
    # =========================================================================
    # Even if conf >= T_LOW, Part identification might be uncertain
    
    if top_conf < T_PART_MIN:
        logger.warning(f"Gate 1b FAIL: Part uncertain - {top_label} conf={top_conf:.2f} < {T_PART_MIN}")
        return {
            "label": "UNKNOWN",
            "model_confidence": top_conf,
            "decision_confidence": None,
            "source": "part_uncertain",
            "reason_tag": "gate1b_part_uncertain",
            "gate": "part_min_threshold",
            "hard_sample": True,
            "retraining_priority": "HIGH"  # Part errors are critical!
        }
    
    logger.info(f"Gate 1b PASS: Part certainty OK - {top_label} conf={top_conf:.2f} >= {T_PART_MIN}")
    
    # =========================================================================
    # Gate 2: High Confidence (Part 확정)
    # =========================================================================
    
    # HIGH Confidence → Accept without LLM
    if top_conf >= T_HIGH:
        logger.info(f"Gate 2 PASS: High confidence - {top_label} {top_conf:.2f} >= {T_HIGH}")
        logger.info(f"Part confirmed: {top_label}, proceeding with Defect detection")
        return {
            "label": top_label,
            "model_confidence": top_conf,
            "decision_confidence": top_conf,
            "source": "model_high_conf",
            "gate": "gate2_high_confidence"
        }
    
    # NOTE: LOW confidence (<T_LOW) already handled by Gate 1a
    # No need to check again here
    
    
    # =========================================================================
    # Gate 3: Middle Zone (T_PART_MIN <= conf < T_HIGH)
    # =========================================================================
    # Part is reasonably confident but not certain
    
    logger.info(f"Middle Zone: {top_label} conf={top_conf:.2f} in [{T_PART_MIN}, {T_HIGH})")
    
    # Check if this is a critical part
    is_critical = top_label in CRITICAL_PARTS
    
    if is_critical:
        logger.info(f"Critical part detected: {top_label} - using LLM verification")
    else:
        logger.info(f"Non-critical part: {top_label} - conservative approach")
    
    # Check ambiguity (gate LLM calls)
    is_amb = is_ambiguous(candidates)
    
    
    # Non-critical + Not ambiguous + Reasonably high → Skip LLM
    if not is_critical and not is_amb and top_conf >= T_AMB_SKIP_LLM:
        logger.info(f"Non-critical part, not ambiguous, conf={top_conf:.2f} >= {T_AMB_SKIP_LLM}, skip LLM")
        return {
            "label": top_label,
            "model_confidence": top_conf,
            "decision_confidence": top_conf,
            "source": "model_mid_conf_clear",
            "gate": "middle_zone_skip_llm"
        }
    
    # Enhanced logging for ambiguous + low-mid conf (important for analysis)
    if is_amb:
        logger.info(f"Ambiguous: top1={candidates[0].get('confidence', 0):.2f}, top2={candidates[1].get('confidence', 0):.2f}")
        if top_conf < T_LLM_ACCEPT:
            logger.warning(f"⚠️ ambiguous_low_conf: top={top_conf:.2f} < {T_LLM_ACCEPT} (high retraining value)")
    
    # Non-critical + ambiguous or lower conf → Conservative (UNKNOWN)
    if not is_critical:
        logger.info(f"Non-critical + (ambiguous or conf<{T_AMB_SKIP_LLM}) → UNKNOWN")
        return {
            "label": "UNKNOWN",
            "model_confidence": top_conf,
            "decision_confidence": None,
            "source": "middle_zone_conservative",
            "reason_tag": "non_critical_middle_zone",
            "gate": "gate3_non_critical_conservative",
            "hard_sample": True,
            "retraining_priority": "MEDIUM"
        }
    
    # Critical parts → LLM verification
    logger.info(f"Critical part in middle zone, proceeding with LLM verification")
    
    # =========================================================================
    # Gate 4: LLM Agreement Check (Critical parts only in middle zone)
    # =========================================================================
    if llm_client is None or crop_image is None:
        logger.warning("LLM not available, using fallback threshold")
        
        # LLM unavailable → Use fallback threshold (prevent service failure)
        if top_conf >= FALLBACK_ACCEPT:
            logger.info(f"LLM unavailable but conf={top_conf:.2f} >= {FALLBACK_ACCEPT}, accept")
            return {
                "label": top_label,
                "model_confidence": top_conf,
                "decision_confidence": top_conf,
                "source": "model_llm_unavailable_accept"
            }
        else:
            logger.warning(f"LLM unavailable and conf={top_conf:.2f} < {FALLBACK_ACCEPT}, reject")
            
            # Add reason_tag for better analysis
            reason_tag = "ambiguous_low_conf" if is_amb and top_conf < T_LLM_ACCEPT else "llm_unavailable_low_conf"
            
            return {
                "label": "UNKNOWN",
                "model_confidence": top_conf,
                "decision_confidence": None,  # None = no decision made
                "source": "llm_unavailable_reject",
                "reason_tag": reason_tag,
                "hard_sample": True  # Collect for retraining
            }
    
    # Build candidates text
    candidates_text = "\n".join([
        f"- {class_names.get(int(c.get('cls', c.get('class', 0))), 'unknown')}: {c.get('confidence', c.get('conf', 0.0)):.2f}"
        for c in candidates
    ])
    
    # LLM Prompt - RESTRICTED ROLE
    prompt = f"""Given the image and the candidate labels, 
is the top prediction CONSISTENT with the visual evidence?
Choose ONLY true or false.
Do NOT suggest new labels.
If you are uncertain, answer false.

Model's top prediction: {top_label} (confidence: {top_conf:.2f})

All candidates:
{candidates_text}

Answer in JSON format:
{{
  "agreement": true or false,
  "reason": "brief explanation why you agree or disagree"
}}
"""
    
    try:
        # Call LLM
        llm_response = llm_client.analyze_image(
            crop_image,
            prompt,
            response_format={"type": "json_object"}
        )
        
        agreement = llm_response.get("agreement", False)
        reason = llm_response.get("reason", "")
        
        # Step 5: Decision Rule (threshold-based, no arbitrary boost)
        if agreement and top_conf >= T_LLM_ACCEPT:
            # LLM agrees AND confidence sufficient → ACCEPT
            logger.info(f"LLM agreed + conf={top_conf:.2f} >= {T_LLM_ACCEPT}, accept")
            
            return {
                "label": top_label,
                "model_confidence": top_conf,
                "decision_confidence": top_conf,  # No boost, keep original
                "source": "model_llm_agreed",
                "llm_agreement": True,
                "llm_reason": reason
            }
        else:
            # LLM disagreed OR confidence too low → UNKNOWN
            if agreement:
                logger.info(f"LLM agreed but conf={top_conf:.2f} < {T_LLM_ACCEPT}, reject")
                reject_reason = "llm_agreed_low_conf"
                reason_tag = "ambiguous_low_conf" if is_amb else "llm_agreed_low_conf"
            else:
                logger.info(f"LLM disagreed: {reason}")
                reject_reason = "model_llm_disagreed"
                reason_tag = "ambiguous_disagreed" if is_amb else "llm_disagreed"
            
            return {
                "label": "UNKNOWN",
                "model_confidence": top_conf,
                "decision_confidence": None,  # None = no decision made
                "source": reject_reason,
                "reason_tag": reason_tag,  # For analysis
                "llm_agreement": agreement,
                "llm_reason": reason,
                "hard_sample": True  # Collect for retraining
            }
    
    except Exception as e:
        logger.error(f"LLM agreement failed: {e}")
        
        return {
            "label": "UNKNOWN",
            "model_confidence": top_conf,
            "decision_confidence": None,  # None = no decision made
            "source": "llm_error",
            "reason_tag": "llm_api_error",
            "error": str(e),
            "hard_sample": True  # Collect for retraining
        }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Example detections from YOLO
    detections = [
        {"cls": 0, "conf": 0.62, "bbox": [100, 100, 50, 50]},
        {"cls": 1, "conf": 0.58, "bbox": [150, 150, 55, 55]},
        {"cls": 2, "conf": 0.41, "bbox": [200, 200, 60, 60]},
        {"cls": 3, "conf": 0.05, "bbox": [1, 1, 2, 2]},  # Noise (too small)
    ]
    
    class_names = {
        0: "oil_leak",
        1: "dust",
        2: "rust",
        3: "artifact"
    }
    
    # Simulate
    result = llm_agreement_fallback(
        detections=detections,
        image_width=640,
        image_height=480,
        class_names=class_names,
        crop_image=None,  # Would be PIL Image in real
        llm_client=None   # Would be LLM client in real
    )
    
    print("Result:", result)
    # Expected: UNKNOWN (llm_not_available)
