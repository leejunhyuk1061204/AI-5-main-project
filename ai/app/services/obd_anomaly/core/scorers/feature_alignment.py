from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence

import numpy as np


@dataclass(frozen=True)
class QualityMeta:
    n_present: int
    coverage: float
    max_gap: int
    uniform_ts: bool
    present_features: List[str]


def _to_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    return float("nan")


def align_window(window_samples: Sequence[Any], schema_features: Sequence[str], sampling_hz: int, timestamp_unit: str = "s") -> tuple[np.ndarray, np.ndarray, QualityMeta]:
    # n_present: this window에서 schema feature key가 1회 이상 등장한 개수.
    # coverage: [time, feature] 마스크의 유효값(유한 숫자) 비율.
    # max_gap: feature별 연속 결측 길이의 최댓값(전체 feature 중 최대).
    # uniform_ts: 기대 간격 대비 timestamp jitter가 20% 이내인지 여부.
    t_len = len(window_samples)
    f_len = len(schema_features)
    x = np.full((t_len, f_len), np.nan, dtype=np.float32)
    mask = np.zeros((t_len, f_len), dtype=np.float32)

    present = set()
    ts: List[int] = []
    for ti, sample in enumerate(window_samples):
        t_val = getattr(sample, "t", None)
        if isinstance(t_val, int):
            ts.append(t_val)
        feats = getattr(sample, "features", {}) or {}
        if not isinstance(feats, dict):
            feats = {}
        for fi, feat in enumerate(schema_features):
            if feat in feats:
                present.add(feat)
            v = _to_float(feats.get(feat))
            if np.isfinite(v):
                x[ti, fi] = v
                mask[ti, fi] = 1.0

    n_present = len(present)
    coverage = float(mask.mean()) if mask.size else 0.0

    max_gap = 0
    for fi in range(f_len):
        cur = 0
        for ti in range(t_len):
            if mask[ti, fi] <= 0:
                cur += 1
                if cur > max_gap:
                    max_gap = cur
            else:
                cur = 0

    # timestamp_unit/sampling_hz 기반 기대 샘플 간격.
    expected_delta = (1000 if timestamp_unit == "ms" else 1) / max(sampling_hz, 1)
    uniform_ts = True
    if len(ts) >= 3:
        d = np.diff(np.array(ts, dtype=np.float64))
        if np.any(d <= 0):
            uniform_ts = False
        else:
            tol = max(0.2 * expected_delta, 1e-6)
            uniform_ts = bool(np.all(np.abs(d - expected_delta) <= tol))

    return x, mask, QualityMeta(
        n_present=n_present,
        coverage=coverage,
        max_gap=max_gap,
        uniform_ts=uniform_ts,
        present_features=sorted(present),
    )

