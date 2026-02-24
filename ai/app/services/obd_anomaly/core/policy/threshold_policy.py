from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def load_threshold_policy(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}


def apply_engine_policy(
    window_scores: List[float],
    window_start_ts: List[int],
    policy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Applies K-consecutive and cooldown to per-window scores.
    Returns generated event dicts.
    """
    t = float(policy.get("threshold", 0.7))
    k = max(1, int(policy.get("k_consecutive", 1)))
    cooldown = max(0, int(policy.get("cooldown_sec", 0)))
    sev_cfg = policy.get("severity", {})
    bonus_per = float(sev_cfg.get("duration_bonus_per_window", 0.05))
    max_bonus = float(sev_cfg.get("max_bonus", 0.3))

    events: List[Dict[str, Any]] = []
    streak = 0
    last_event_ts = -10**12
    for i, score in enumerate(window_scores):
        if score >= t:
            streak += 1
        else:
            streak = 0
            continue
        if streak < k:
            continue
        now_ts = window_start_ts[i] if i < len(window_start_ts) else i
        if now_ts - last_event_ts < cooldown:
            continue

        bonus = min(max_bonus, max(0.0, (streak - k + 1) * bonus_per))
        severity_score = min(1.0, score + bonus)
        events.append(
            {
                "type": "ENGINE_POLICY_ANOMALY",
                "feature": "engine_hybrid_score",
                "window_index": i,
                "value": score,
                "severity_score": severity_score,
                "duration_bonus": bonus,
                "streak": streak,
                "start_t": now_ts,
            }
        )
        last_event_ts = now_ts
    return events

