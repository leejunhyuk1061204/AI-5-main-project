# ai/app/services/visual/domains/tire/tire_llm_fallback.py
"""
Production-Grade Confidence Gating for Tire Classification

⚠️ NOTE: Classification-Only Fallback
-----------------------------------------
Tire YOLO is a CLASSIFICATION model (normal/worn only, no bbox).
This fallback is simplified compared to Detection-based fallback (engine):
- NO ambiguity detection (no top-k candidates)
- NO bbox validation (classification has no real bbox)
- NO critical condition logic (YOLO doesn't output cracked/flat/bulge)

[Current Role]
Decide whether to trust YOLO result or call LLM oracle.
LLM oracle (get_tire_analysis_from_llm) handles actual wear analysis.

[Future]
After YOLO multi-class retraining (cracked/flat/bulge), upgrade to detection fallback.

[핵심 원칙 - Simplified]
1. Confidence Gating (low/mid/high zones)
2. Conservative Thresholds (wear is subjective)
3. LLM Oracle Only (no agreement-based LLM in this domain yet)
"""

import logging
from typing import List, Dict, Optional
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration - Layered Gate Structure (Tire-Specific, Conservative)
# =============================================================================

# Gate 1a: Low Confidence
T_LOW = 0.60    # Below this = UNKNOWN (low_conf)

# Gate 1b: Wear Classification Certainty
T_WEAR_MIN = 0.78   # Below this = UNKNOWN (wear_uncertain, HIGH priority)
                    # ⚠️ Higher than Engine (0.70) because wear is more subjective

# Gate 2: High Confidence
T_HIGH = 0.85   # High confidence - Accept without LLM

# Gate 3: Middle Zone (T_WEAR_MIN <= conf < T_HIGH)
# NOTE: No critical conditions - YOLO only outputs normal/worn
# cracked/flat/bulge detection is LLM oracle's job

T_MIDDLE_ACCEPT = 0.80  # Middle zone: conf >= this → ACCEPT (skip LLM)
# ⚠️ 0.78-0.80 gap prevents false ACCEPT in uncertain zone

# Classification-specific: No ambiguity detection, no bbox validation
# (Classification models don't have real top-k candidates or bbox)

# =============================================================================
# Helper Functions
# =============================================================================

# NOTE: Helper functions removed for classification fallback
# Classification models don't have:
# - Real bbox (dummy only)
# - Top-k ambiguity (single prediction)
#
# These functions were designed for detection models.


# =============================================================================
# Main Fallback Logic
# =============================================================================

def confidence_gating_tire(
    label: str,
    confidence: float
) -> Dict:
    """
    Simplified confidence gating for Tire Classification
    
    NOTE: This is NOT LLM agreement fallback.
    This simply decides: "Should we trust YOLO or call LLM oracle?"
    
    Conservative thresholds rationale:
    - Wear assessment is subjective (vs. objective part detection)
    - 0.78-0.80 gap: Prevents false ACCEPT in uncertain zone
    - User trust > cost savings
    
    Args:
        label: YOLO prediction ("worn", "normal", "cracked")
        confidence: YOLO confidence (0.0-1.0)
    
    Returns:
        {
            "label": "worn" | "normal" | "UNKNOWN",
            "model_confidence": 0.82,
            "decision_confidence": 0.82 | None,
            "source": "model_high_conf" | "model_mid_clear" | "wear_uncertain",
            "gate": "gate2_high_confidence" | ...,
            "hard_sample": True | False,
            "retraining_priority": "HIGH" | "MEDIUM" | "LOW",
            "reason_tag": "gate1b_wear_uncertain" | ...
        }
    """
    
    # =========================================================================
    # Gate 1a: Low Confidence (General Model Uncertainty)
    # =========================================================================
    if confidence < T_LOW:
        logger.warning(f"Gate 1a FAIL: Low confidence - {label} conf={confidence:.2f} < {T_LOW}")
        return {
            "label": "UNKNOWN",
            "model_confidence": confidence,
            "decision_confidence": None,
            "source": "model_low_conf",
            "reason_tag": "gate1a_low_conf",
            "gate": "gate1a_low_confidence",
            "hard_sample": True,
            "retraining_priority": "MEDIUM"
        }
    
    logger.info(f"Gate 1a PASS: Conf={confidence:.2f} >= {T_LOW}")
    
    # =========================================================================
    # Gate 1b: Wear Classification Certainty
    # =========================================================================
    if confidence < T_WEAR_MIN:
        logger.warning(f"Gate 1b FAIL: Wear uncertain - {label} conf={confidence:.2f} < {T_WEAR_MIN}")
        return {
            "label": "UNKNOWN",
            "model_confidence": confidence,
            "decision_confidence": None,
            "source": "wear_uncertain",
            "reason_tag": "gate1b_wear_uncertain",
            "gate": "gate1b_wear_min_threshold",
            "hard_sample": True,
            "retraining_priority": "HIGH"  # Wear classification errors are critical
        }
    
    logger.info(f"Gate 1b PASS: Wear certainty OK - {label} conf={confidence:.2f} >= {T_WEAR_MIN}")
    
    # =========================================================================
    # Gate 2: High Confidence
    # =========================================================================
    if confidence >= T_HIGH:
        logger.info(f"Gate 2 PASS: High confidence - {label} {confidence:.2f} >= {T_HIGH}")
        logger.info(f"Tire condition confirmed: {label}")
        return {
            "label": label,
            "model_confidence": confidence,
            "decision_confidence": confidence,
            "source": "model_high_conf",
            "gate": "gate2_high_confidence"
        }
    
    # =========================================================================
    # Gate 3: Middle Zone (T_WEAR_MIN <= conf < T_HIGH)
    # =========================================================================
    logger.info(f"Middle Zone: {label} conf={confidence:.2f} in [{T_WEAR_MIN}, {T_HIGH})")
    
    # Middle zone: Simple threshold-based decision
    if confidence >= T_MIDDLE_ACCEPT:
        logger.info(f"Middle zone clear: conf={confidence:.2f} >= {T_MIDDLE_ACCEPT} → ACCEPT")
        return {
            "label": label,
            "model_confidence": confidence,
            "decision_confidence": confidence,
            "source": "model_mid_clear",
            "gate": "gate3_middle_zone_accept"
        }
    else:
        # Below T_MIDDLE_ACCEPT → Conservative (call LLM oracle)
        logger.info(f"Middle zone uncertain: conf={confidence:.2f} < {T_MIDDLE_ACCEPT} → UNKNOWN (call LLM)")
        return {
            "label": "UNKNOWN",
            "model_confidence": confidence,
            "decision_confidence": None,
            "source": "middle_zone_uncertain",
            "reason_tag": "middle_zone_needs_llm",
            "gate": "gate3_middle_zone_uncertain",
            "hard_sample": True,
            "retraining_priority": "MEDIUM"
        }
