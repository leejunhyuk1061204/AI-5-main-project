# ai/app/services/visual/domains/dashboard/dashboard_llm_fallback.py
"""
[Decision Layer] Pure Logic for Dashboard Warning Light Detection (Standard v1.1)

⚠️ ARCHITECTURAL RULE:
- PURE LOGIC ONLY (No LLM, No I/O).
- Returns type-safe DecisionResult dataclass.
- Gate must be an integer (0-4).

[Standard Gate System]
Gate 0: Input Validity (BBox ratio, size)
Gate 1: Model Confidence (T_LOW, T_HIGH)
Gate 2: Domain Heuristics (Mid-zone clear path)
Gate 3: LLM Oracle / Verification (Status=UNCERTAIN)
Gate 4: AL Trigger (Status=UNCERTAIN, low-conf needing verification)
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from ai.app.services.visual.yolo_utils import normalize_label

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DecisionResult:
    """Type-safe decision container (Veteran standard)"""
    status: Literal["APPROVED", "UNCERTAIN", "MISS"]
    gate: int
    confidence: float
    label: Optional[str] = None
    reason: str = ""
    is_critical: bool = False
    is_ambiguous: bool = False

# =============================================================================
# Configuration - Standard Gate Thresholds
# =============================================================================

# BBox Validation (Gate 0)
MIN_BBOX_AREA_RATIO = 0.005  # 0.5%
MAX_BBOX_AREA_RATIO = 0.30   # 30%
MIN_CONF_FOR_CANDIDATE = 0.25

# Model Confidence (Gate 1)
T_LOW = 0.50
T_WARNING_MIN = 0.65
T_HIGH = 0.80

# Domain Heuristics (Gate 2)
T_AMB_SKIP_LLM = 0.70
AMBIGUITY_DELTA = 0.10

# Normalized Critical Labels
CRITICAL_WARNINGS = {
    "braking_system_issue",
    "srs_airbag",
    "engine_overheating_warning_light",
    "low_engine_oil_warning_light",
    "charging_system_issue"
}

# =============================================================================
# Pure Decision Logic
# =============================================================================

def get_dashboard_decision(
    detections: List[Dict],
    image_width: int,
    image_height: int,
    class_names: Dict[int, str]
) -> DecisionResult:
    """
    Evaluates detections and returns a type-safe DecisionResult.
    Follows Gate 0-4 numbering system.
    """
    
    # [Gate 0] Input Validity
    valid_candidates = []
    for d in detections:
        conf = d.get('confidence', d.get('conf', 0.0))
        bbox = d.get('bbox', [0, 0, 1, 1]) # [x, y, w, h]
        
        area_ratio = (bbox[2] * bbox[3]) / (image_width * image_height) if image_width > 0 else 0
        
        if (conf >= MIN_CONF_FOR_CANDIDATE and 
            MIN_BBOX_AREA_RATIO <= area_ratio <= MAX_BBOX_AREA_RATIO):
            valid_candidates.append(d)
            
    if not valid_candidates:
        return DecisionResult(
            status="MISS",
            gate=0,
            reason="no_valid_detections",
            confidence=0.0
        )

    # Sort candidates
    candidates = sorted(valid_candidates, key=lambda x: x.get('confidence', 0.0), reverse=True)
    top = candidates[0]
    top_conf = top.get('confidence', 0.0)
    top_cls = int(top.get('cls', top.get('class', 0)))
    top_label = normalize_label(class_names.get(top_cls, f"class_{top_cls}"))

    # [Gate 1] Base Confidence
    if top_conf >= T_HIGH:
        return DecisionResult(
            status="APPROVED",
            gate=1,
            confidence=top_conf,
            label=top_label,
            reason="high_confidence"
        )

    # [Gate 4] AL Trigger (Explicitly identify low-conf samples requiring AL)
    # If the confidence is really low, it's a high-value sample for Active Learning
    if top_conf < T_LOW:
        return DecisionResult(
            status="UNCERTAIN",
            gate=4,
            confidence=top_conf,
            label=top_label,
            reason="low_confidence_requires_al"
        )
    
    # [Gate 2] Domain Heuristics (Middle Zone)
    is_critical = top_label in CRITICAL_WARNINGS
    
    is_ambiguous = False
    if len(candidates) >= 2:
        delta = top_conf - candidates[1].get('confidence', 0.0)
        if delta < AMBIGUITY_DELTA:
            is_ambiguous = True

    # Gate 2.1: Non-critical + Clear prediction -> ACCEPT
    if not is_critical and not is_ambiguous and top_conf >= T_AMB_SKIP_LLM:
        return DecisionResult(
            status="APPROVED",
            gate=2,
            confidence=top_conf,
            label=top_label,
            reason="mid_conf_clear_prediction"
        )

    # [Gate 3] LLM Verification (Requires side-effect escalation)
    return DecisionResult(
        status="UNCERTAIN",
        gate=3,
        confidence=top_conf,
        label=top_label,
        reason="needs_llm_verification",
        is_critical=is_critical,
        is_ambiguous=is_ambiguous
    )
