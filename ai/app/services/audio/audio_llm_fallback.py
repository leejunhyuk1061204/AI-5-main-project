# ai/app/services/audio/audio_llm_fallback.py
"""
오디오 결함 분석용 LLM 폴백(Fall-back) 및 의사결정 레이어 서비스

본 모듈은 AST(Audio Spectrogram Transformer) 모델의 추론 결과와
사용자 오디오 스트림의 특성(음성 비율 등)을 종합하여 최종 판단을 내립니다.
주요 기능:
1. AST 예측 점수에 따른 4단계 게이트(Gate) 분류
2. 저확신 또는 모호한 상황 발생 시 LLM(GPT-4o) 분석 트리거
3. 능동 학습(Active Learning) 대상 선별 (Gate 4)

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

# =============================================================================
# Configuration - Standard Gate Thresholds
# =============================================================================

# Common thresholds for AST/Hybrid models
T_HIGH = 0.85
T_LOW = 0.60
AMBIGUITY_DELTA = 0.15

def get_audio_decision(
    confidence: float,
    label: str,
    all_probs: Optional[Dict[str, float]] = None
) -> AudioDecisionResult:
    """
    Pure logic to decide whether to trust the audio model or escalate to LLM.
    """
    
    # 0. Ambiguity Analysis (2등과의 차이 검증)
    is_ambiguous = False
    if all_probs and len(all_probs) >= 2:
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
    # Gate 1 조건(Confidence >= T_HIGH)을 만족하더라도 Ambiguous하면 여기로 빠짐
    return AudioDecisionResult(
        status="UNCERTAIN",
        gate=3,
        confidence=confidence,
        label=label,
        reason="uncertain_or_ambiguous",
        is_ambiguous=is_ambiguous
    )
