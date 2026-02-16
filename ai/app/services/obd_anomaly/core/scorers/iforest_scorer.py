from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np


class IForestScorer:
    _RANGE_PRIORS: Dict[str, tuple[float, float]] = {
        "engine_coolant_temp_c": (-30.0, 130.0),
        "imap_kpa": (10.0, 220.0),
        "engine_rpm": (500.0, 7000.0),
        "vehicle_speed_kmh": (0.0, 220.0),
        "intake_air_temp_c": (-30.0, 90.0),
        "maf_gps": (0.0, 120.0),
        "throttle_pos_pct": (0.0, 100.0),
    }

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
            if len(col) > 1:
                d = np.diff(col)
                dmean = float(np.nanmean(np.abs(d))) if np.any(np.isfinite(d)) else 0.0
            else:
                dmean = 0.0
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

    def _fallback_feature_scores(self, x: np.ndarray) -> Dict[str, float]:
        feat_scores: Dict[str, float] = {}
        for fi, feat in enumerate(self.schema_features):
            col = x[:, fi]
            finite = col[np.isfinite(col)]
            if finite.size == 0:
                feat_scores[feat] = 0.0
                continue

            mean = float(np.mean(finite))
            std = float(np.std(finite))
            slope = float(finite[-1] - finite[0]) if finite.size >= 2 else 0.0
            diff_mean = float(np.mean(np.abs(np.diff(finite)))) if finite.size >= 2 else 0.0

            denom = max(abs(mean), 1.0)
            dyn = min(1.0, max(0.0, 0.5 * (std / denom) + 0.5 * max(abs(slope) / denom, diff_mean / denom)))

            lo, hi = self._RANGE_PRIORS.get(feat, (-1e9, 1e9))
            span = max(hi - lo, 1.0)
            if mean < lo:
                range_score = min(1.0, (lo - mean) / (0.5 * span))
            elif mean > hi:
                range_score = min(1.0, (mean - hi) / (0.5 * span))
            else:
                range_score = 0.0

            feat_scores[feat] = float(max(dyn, range_score))
        return feat_scores

    def score(self, x: np.ndarray) -> tuple[float, str, List[Dict[str, float]]]:
        stats, names = self._feature_stats(x)
        if not np.any(np.isfinite(stats)):
            return 0.0, "SKIPPED", []
        stats = np.nan_to_num(stats, nan=0.0, posinf=0.0, neginf=0.0)

        if self.iforest_model is not None:
            try:
                raw = float(self.iforest_model.decision_function(stats.reshape(1, -1))[0])
                score = 1.0 / (1.0 + math.exp(4.0 * raw))
                top_idx = np.argsort(np.abs(stats))[-3:][::-1]
                top = []
                denom = float(np.sum(np.abs(stats[top_idx])) + 1e-6)
                for i in top_idx:
                    feat = names[int(i)].split(":", 1)[0]
                    contrib = float(abs(stats[int(i)]) / denom)
                    top.append({"feature": feat, "contribution": contrib})
                return score, "PROCESSED", top
            except Exception:
                pass

        feat_scores = self._fallback_feature_scores(x)
        if not feat_scores:
            return 0.0, "SKIPPED", []
        ranked = sorted(feat_scores.items(), key=lambda kv: kv[1], reverse=True)
        top_feats = ranked[:3]
        score = float(min(1.0, max(0.0, np.mean([v for _, v in top_feats]))))

        top = []
        denom = float(sum(v for _, v in top_feats) + 1e-6)
        for feat, v in top_feats:
            top.append({"feature": feat, "contribution": float(v / denom)})
        return score, "PROCESSED", top

