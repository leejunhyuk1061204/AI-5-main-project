from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


class LSTMAEScorer:
    def __init__(self, schema_features: List[str], ae_model: Any, scaler: Dict[str, Any] | None, policy: Dict[str, Any]) -> None:
        self.schema_features = schema_features
        self.ae_model = ae_model
        self.scaler = scaler
        self.policy = policy

    def _impute(self, x: np.ndarray, mask: np.ndarray) -> np.ndarray:
        out = x.copy()
        for fi in range(out.shape[1]):
            col = out[:, fi]
            valid = mask[:, fi] > 0
            if np.any(valid):
                m = float(np.nanmean(col[valid]))
            else:
                m = 0.0
            col[~valid] = m
            out[:, fi] = col
        return out

    def _apply_scaler(self, x: np.ndarray) -> np.ndarray:
        if not self.scaler:
            return x
        mean = np.array(self.scaler.get("mean", []), dtype=np.float32)
        std = np.array(self.scaler.get("std", []), dtype=np.float32)
        if mean.shape[0] != x.shape[1] or std.shape[0] != x.shape[1]:
            return x
        std = np.where(std == 0, 1.0, std)
        return (x - mean.reshape(1, -1)) / std.reshape(1, -1)

    def score(self, x: np.ndarray, mask: np.ndarray) -> tuple[Optional[float], str, List[Dict[str, float]]]:
        if self.ae_model is None:
            return None, "SKIPPED", []

        x_imp = self._impute(x, mask)
        x_scaled = self._apply_scaler(x_imp)

        try:
            import torch

            if hasattr(self.ae_model, "eval") and hasattr(self.ae_model, "__call__"):
                model = self.ae_model
                model.eval()
                inp = torch.from_numpy(x_scaled.astype(np.float32)).unsqueeze(0)
                with torch.no_grad():
                    recon = model(inp)
                    rec = recon.detach().cpu().numpy()[0]
            else:
                return None, "SKIPPED", []
        except Exception:
            return None, "SKIPPED", []

        err_mat = (rec - x_scaled) ** 2
        err = float(np.mean(err_mat))
        ae_cfg = self.policy.get("ae_score", {})
        e0 = float(ae_cfg.get("error_min", 0.0))
        e1 = float(max(ae_cfg.get("error_max", 0.2), e0 + 1e-6))
        score = float(min(1.0, max(0.0, (err - e0) / (e1 - e0))))

        feat_err = np.mean(err_mat, axis=0)
        top_idx = np.argsort(feat_err)[-3:][::-1]
        denom = float(np.sum(feat_err[top_idx]) + 1e-6)
        top = []
        for i in top_idx:
            feat = self.schema_features[int(i)] if int(i) < len(self.schema_features) else f"f{int(i)}"
            top.append({"feature": feat, "contribution": float(feat_err[int(i)] / denom)})
        return score, "PROCESSED", top

