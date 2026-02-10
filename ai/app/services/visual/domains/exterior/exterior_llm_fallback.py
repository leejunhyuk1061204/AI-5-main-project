# ai/app/services/visual/domains/exterior/exterior_llm_fallback.py
"""
[Decision Layer] Pure Logic for Exterior Damage Detection (Standard v1.1)

⚠️ ARCHITECTURAL RULE:
- PURE LOGIC ONLY (No LLM, No I/O).
- Returns type-safe DecisionResult dataclass.
- Gate must be an integer (0-4).

[Standard Gate System]
Gate 0: Input Validity (BBox area, size)
Gate 1: Model Confidence (Static thresholds)
Gate 2: Domain Heuristics (Non-critical clear path)
Gate 3: LLM Oracle / Verification (UNCERTAIN)
Gate 4: AL Trigger (Low-conf needing verification)
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from ai.app.services.visual.yolo_utils import normalize_label

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class DecisionResult:
    """Type-safe decision container for Exterior domain"""
    status: Literal["APPROVED", "UNCERTAIN", "MISS"]
    gate: int
    confidence: float
    label: Optional[str] = None
    reason: str = ""
    is_critical: bool = False
    is_ambiguous: bool = False
    metadata: Optional[Dict] = None

# =============================================================================
# Configuration - Standard Gate Thresholds
# =============================================================================

MIN_BBOX_AREA_RATIO = 0.002  # 0.2% (Damage can be small)
MAX_BBOX_AREA_RATIO = 0.60   # 60% (Large dents/scratches possible)
MIN_CONF_FOR_CANDIDATE = 0.25

T_LOW = 0.55
T_HIGH = 0.85  # Strict for physical damage
AMBIGUITY_DELTA = 0.12 # Higher delta for complex overlap

# Unified 22 classes from legacy exterior_service.py
# Standardized to underscores via normalize_label
UNIFIED_CLASSES = {
    # 1. Dent series
    "bonnet_dent": {"part": "Bonnet", "damage": "Dent", "severity": "WARNING"},
    "doorouter_dent": {"part": "Door", "damage": "Dent", "severity": "WARNING"},
    "fender_dent": {"part": "Fender", "damage": "Dent", "severity": "WARNING"},
    "front_bumper_dent": {"part": "Front_Bumper", "damage": "Dent", "severity": "WARNING"},
    "quaterpanel_dent": {"part": "Quarter_Panel", "damage": "Dent", "severity": "WARNING"},
    "rear_bumper_dent": {"part": "Rear_Bumper", "damage": "Dent", "severity": "WARNING"},
    "roof_dent": {"part": "Roof", "damage": "Dent", "severity": "WARNING"},
    "pillar_dent": {"part": "Pillar", "damage": "Dent", "severity": "CRITICAL"},
    "runningboard_dent": {"part": "Running_Board", "damage": "Dent", "severity": "WARNING"},
    "medium_bodypanel_dent": {"part": "Body_Panel", "damage": "Medium_Dent", "severity": "WARNING"},
    "major_rear_bumper_dent": {"part": "Rear_Bumper", "damage": "Major_Dent", "severity": "CRITICAL"},

    # 2. Scratch series
    "doorouter_scratch": {"part": "Door", "damage": "Scratch", "severity": "WARNING"},
    "front_bumper_scratch": {"part": "Front_Bumper", "damage": "Scratch", "severity": "WARNING"},
    "rear_bumper_scratch": {"part": "Rear_Bumper", "damage": "Scratch", "severity": "WARNING"},

    # 3. Glass & Lamp Damage
    "front_windscreen_damage": {"part": "Front_Windshield", "damage": "Glass_Broken", "severity": "CRITICAL"},
    "rear_windscreen_damage": {"part": "Rear_Windshield", "damage": "Glass_Broken", "severity": "CRITICAL"},
    "headlight_damage": {"part": "Headlight", "damage": "Broken", "severity": "CRITICAL"},
    "taillight_damage": {"part": "Taillight", "damage": "Broken", "severity": "CRITICAL"},
    "sidemirror_damage": {"part": "Sidemirror", "damage": "Broken", "severity": "WARNING"},
    "signlight_damage": {"part": "Indicator", "damage": "Broken", "severity": "WARNING"},

    # 4. Paint Damage
    "paint_chip": {"part": "General_Body", "damage": "Paint_Chip", "severity": "WARNING"},
    "paint_trace": {"part": "General_Body", "damage": "Paint_Trace", "severity": "NORMAL"},
}

# =============================================================================
# Pure Decision Logic
# =============================================================================

def get_exterior_decision(
    detections: List[Dict],
    image_width: int,
    image_height: int,
    class_names: Dict[int, str]
) -> DecisionResult:
    """
    Evaluates exterior detections using the standard gate system.
    Returns DecisionResult status for the Handler to act upon.
    """
    
    # [Gate 0] Input Validity
    valid_candidates = []
    for d in detections:
        conf = d.get('confidence', d.get('conf', 0.0))
        bbox = d.get('bbox', [0, 0, 1, 1])
        
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

    # Sort by confidence
    candidates = sorted(valid_candidates, key=lambda x: x.get('confidence', 0.0), reverse=True)
    top = candidates[0]
    top_conf = top.get('confidence', 0.0)
    top_label = normalize_label(top.get('label', 'unknown'))
    
    # Check if critical (Pillar, Glass, Major Dents)
    info = UNIFIED_CLASSES.get(top_label, {})
    is_critical = info.get("severity") == "CRITICAL"

    # [Gate 1] Base Confidence
    if top_conf >= T_HIGH:
        return DecisionResult(
            status="APPROVED",
            gate=1,
            confidence=top_conf,
            label=top_label,
            reason="high_confidence",
            is_critical=is_critical
        )

    # [Gate 4] AL Trigger (Explicit low-conf samples)
    if top_conf < T_LOW:
        return DecisionResult(
            status="UNCERTAIN",
            gate=4,
            confidence=top_conf,
            label=top_label,
            reason="low_confidence_requires_al",
            is_critical=is_critical
        )

    # [Gate 2] Domain Heuristics (Middle Zone)
    is_ambiguous = False
    if len(candidates) >= 2:
        delta = top_conf - candidates[1].get('confidence', 0.0)
        if delta < AMBIGUITY_DELTA:
            is_ambiguous = True

    # Gate 2.1: Non-critical + Clear prediction -> ACCEPT
    if not is_critical and not is_ambiguous:
        return DecisionResult(
            status="APPROVED",
            gate=2,
            confidence=top_conf,
            label=top_label,
            reason="mid_conf_non_critical_clear",
            is_critical=False
        )

    # [Gate 3] LLM Verification (Critical or Ambiguous in mid-zone)
    return DecisionResult(
        status="UNCERTAIN",
        gate=3,
        confidence=top_conf,
        label=top_label,
        reason="critical_or_ambiguous_mid_conf",
        is_critical=is_critical,
        is_ambiguous=is_ambiguous
    )
