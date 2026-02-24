from __future__ import annotations

from typing import Optional


def fuse_risk(engine_score: Optional[float], rule_score: Optional[float]) -> Optional[float]:
    """
    Simple risk fusion:
    - if both exist: max
    - else: whichever exists
    """
    if engine_score is None and rule_score is None:
        return None
    if engine_score is None:
        return float(rule_score)
    if rule_score is None:
        return float(engine_score)
    return float(max(engine_score, rule_score))

