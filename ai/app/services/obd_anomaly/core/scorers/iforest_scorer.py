from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np


class IForestScorer:
    def __init__(self, schema_features: List[str], iforest_model: Any) -> None:
        self.schema_features = schema_features
        self.iforest_model = iforest_model

    def _feature_stats(self, x: np.ndarray) -> tuple[np.ndarray, List[str]]:
        vals: List[float] = []
        names: List[str] = []
        for fi, feat in enumerate(self.schema_features):
            col = x[:, fi]
            mean = float(np.nanmean(col)) if np.any(np.isfinite(col)) else 0.0
            std = float(np.nanstd(col)) if np.any(np.isfinite(col)) else 0.0
            min_v = float(np.nanmin(col)) if np.any(np.isfinite(col)) else 0.0
            max_v = float(np.nanmax(col)) if np.any(np.isfinite(col)) else 0.0
            slope = float(col[-1] - col[0]) if np.isfinite(col[-1]) and np.isfinite(col[0]) else 0.0
            dmean = float(np.nanmean(np.abs(np.diff(col)))) if len(col) > 1 else 0.0
            vals.extend([mean, std, min_v, max_v, slope, dmean])
            names.extend(
                [
                    f"{feat}:mean",
                    f"{feat}:std",
                    f"{feat}:min",
                    f"{feat}:max",
                    f"{feat}:slope",
                    f"{feat}:diff_mean",
                ]
            )
        return np.array(vals, dtype=np.float32), names

    def score(self, x: np.ndarray) -> tuple[float, str, List[Dict[str, float]]]:
        stats, names = self._feature_stats(x)
        if not np.any(np.isfinite(stats)):
            return 0.0, "SKIPPED", []
        stats = np.nan_to_num(stats, nan=0.0, posinf=0.0, neginf=0.0)

        if self.iforest_model is not None:
            try:
                raw = float(self.iforest_model.decision_function(stats.reshape(1, -1))[0])
                score = 1.0 / (1.0 + math.exp(4.0 * raw))
            except Exception:
                score = float(min(1.0, max(0.0, np.mean(np.abs(stats)) / 10.0)))
        else:
            score = float(min(1.0, max(0.0, np.mean(np.abs(stats)) / 10.0)))

        top_idx = np.argsort(np.abs(stats))[-3:][::-1]
        top = []
        denom = float(np.sum(np.abs(stats[top_idx])) + 1e-6)
        for i in top_idx:
            feat = names[int(i)].split(":", 1)[0]
            contrib = float(abs(stats[int(i)]) / denom)
            top.append({"feature": feat, "contribution": contrib})
        return score, "PROCESSED", top

