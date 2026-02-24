# ai/app/services/audio/audio_llm_fallback.py
"""
오디오 결함 분석용 LLM 폴백(Fall-back) 및 의사결정 레이어 서비스

본 모듈은 AST(Audio Spectrogram Transformer) 모델의 추론 결과와
사용자 오디오 스트림의 특성(음성 비율 등)을 종합하여 최종 판단을 내립니다.
주요 기능:
1. AST 예측 점수에 따른 4단계 게이트(Gate) 분류
2. 저확신 또는 모호한 상황 발생 시 LLM(GPT-4o) 분석 트리거
3. 능동 학습(Active Learning) 대상 선별 (Gate 4)
"""

"""
[Decision Layer] Pure Logic for Audio Anomaly Detection (Standard v1.0)
ARCHITECTURAL RULE:
- PURE LOGIC ONLY (No LLM, No I/O).
- Returns type-safe AudioDecisionResult dataclass.
- Gate must be an integer (0-4).

[Gate System]
Gate 1: High Model Confidence (Direct Approval)
Gate 2: Middle Confidence (Approved if not clear/ambiguous)
Gate 3: Low Confidence / Uncertain (Trigger LLM Verification)
Gate 4: Active Learning Trigger
"""
from dataclasses import dataclass
from typing import Optional, Literal, Dict

@dataclass(frozen=True)
class AudioDecisionResult:
    """Type-safe decision container for Audio domain"""
    status: Literal["APPROVED", "UNCERTAIN", "UNKNOWN"]
    gate: int
    confidence: float
    label: Optional[str] = None
    reason: str = ""
    is_ambiguous: bool = False
    is_mock: bool = False

# =============================================================================
# Configuration - Standard Gate Thresholds
# =============================================================================

import math

# Common thresholds for AST/Hybrid models
T_HIGH = 0.85
T_LOW = 0.60
AMBIGUITY_DELTA = 0.15
ENTROPY_THRESHOLD = 0.8  # [New] Entropy > 0.8 is considered ambiguous
TOPK_RATIO_THRESHOLD = 1.5 # [New] 1st prob / 2nd prob < 1.5 is ambiguous

def _calculate_entropy(probs: Dict[str, float]) -> float:
    """Softmax Entropy calculation (Pure Python)"""
    p_values = [v for v in probs.values() if v > 0]
    if not p_values: return 0.0
    return -sum(p * math.log2(p) for p in p_values)

def _calculate_topk_ratio(probs: Dict[str, float]) -> float:
    """1st prob / 2nd prob calculation"""
    if len(probs) < 2: return 999.0 # Not ambiguous
    sorted_probs = sorted(probs.values(), reverse=True)
    return sorted_probs[0] / (sorted_probs[1] + 1e-9)

def get_audio_decision(
    confidence: float,
    label: str,
    all_probs: Optional[Dict[str, float]] = None,
    speech_ratio: float = 0.0 # [New] Metric to detect Out-of-Distribution (Speech)
) -> AudioDecisionResult:
    """
    Pure logic to decide whether to trust the audio model or escalate to LLM.
    """
    
    # 0. Speech (OOD) Analysis
    # [Refinement] 음성 비율이 너무 높으면 모델이 overconfident 하더라도 UNCERTAIN 처리
    if speech_ratio > 0.20:
        return AudioDecisionResult(
            status="UNCERTAIN",
            gate=3,
            confidence=confidence,
            label=label,
            reason=f"high_speech_ratio ({speech_ratio:.2%})",
            is_ambiguous=False
        )
    
    # 0. Ambiguity Analysis (Enhanced with Entropy & Top-k Ratio)
    is_ambiguous = False
    ambiguity_reason = ""
    if all_probs and len(all_probs) >= 2:
        # A. Entropy Check (다중 클래스 모호성)
        entropy = _calculate_entropy(all_probs)
        if entropy > ENTROPY_THRESHOLD:
            is_ambiguous = True
            ambiguity_reason = f"high_entropy({entropy:.2f})"
        
        # B. Top-k Ratio Check (1, 2등간의 확신도 차이)
        ratio = _calculate_topk_ratio(all_probs)
        if ratio < TOPK_RATIO_THRESHOLD:
            is_ambiguous = True
            ambiguity_reason += f" low_topk_ratio({ratio:.2f})" if ambiguity_reason else f"low_topk_ratio({ratio:.2f})"

        # C. Traditional Delta Check (Fallback check)
        values = sorted(all_probs.values(), reverse=True)
        delta = values[0] - values[1]
        if delta < AMBIGUITY_DELTA:
            is_ambiguous = True

    # [Gate 1] High Confidence (Approval only if not ambiguous)
    # [Refinement] AST에서는 2등 클래스 점수와 충분한 차이가 있어야만 자동 승인 (Gate 1) 처리
    if confidence >= T_HIGH and not is_ambiguous:
        return AudioDecisionResult(
            status="APPROVED",
            gate=1,
            confidence=confidence,
            label=label,
            reason="high_confidence"
        )
    
    # [Gate 4] Active Learning Trigger (Very Low Confidence)
    # [Refinement] AST 특성 반영: 노이즈 환경에서 0.3대를 보이는 경우가 많으므로 임계값 상향 (0.30 -> 0.35)
    if confidence < 0.35:
        return AudioDecisionResult(
            status="UNCERTAIN",
            gate=4,
            confidence=confidence,
            label=label,
            reason="al_trigger_low_conf"
        )

    # Gate 2: Middle confidence but clear prediction
    if confidence >= T_LOW and not is_ambiguous:
        return AudioDecisionResult(
            status="APPROVED",
            gate=2,
            confidence=confidence,
            label=label,
            reason="mid_conf_clear_prediction"
        )

    # Gate 3: Uncertain (Low confidence or Ambiguous)
    reason = "uncertain_or_ambiguous"
    if is_ambiguous and ambiguity_reason:
        reason = f"ambiguous: {ambiguity_reason}"

    return AudioDecisionResult(
        status="UNCERTAIN",
        gate=3,
        confidence=confidence,
        label=label,
        reason=reason,
        is_ambiguous=is_ambiguous
    )
