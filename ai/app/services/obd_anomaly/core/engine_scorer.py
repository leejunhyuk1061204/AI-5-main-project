from __future__ import annotations

import json
import math
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.core.feature_alignment import QualityMeta, align_window
from ai.app.services.obd_anomaly.windowing import Window


@dataclass(frozen=True)
class GateDecision:
    mode: str
    ae_weight: float


class EngineScorer:
    def __init__(self) -> None:
        self._artifact_dir = Path(
            os.getenv(
                "OBD_ANOMALY_ARTIFACT_DIR",
                str(Path(__file__).resolve().parent.parent / "artifacts"),
            )
        )
        self._schema = self._load_json("schema_core.json", {"features": [], "core_min": 1})
        self._policy = self._load_json("threshold_policy.json", {})
        self._scaler = self._load_scaler()
        self._iforest = self._load_pickle("iforest.pkl")
        self._ae_model = self._load_torch_model()

    def _load_json(self, name: str, default: Dict[str, Any]) -> Dict[str, Any]:
        path = self._artifact_dir / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _load_pickle(self, name: str) -> Any:
        path = self._artifact_dir / name
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def _load_scaler(self) -> Dict[str, Any] | None:
        path = self._artifact_dir / "scaler.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_torch_model(self) -> Any:
        path = self._artifact_dir / "lstm_ae.pt"
        if not path.exists():
            return None
        try:
            import torch

            return torch.load(path, map_location="cpu")
        except Exception:
            return None

    def _threshold(self) -> float:
        return float(self._policy.get("threshold", 0.7))

    def _schema_features(self) -> List[str]:
        feats = self._schema.get("features", [])
        return [f for f in feats if isinstance(f, str)]

    def _core_min(self) -> int:
        return int(self._schema.get("core_min", 1))

    def _gating_cfg(self) -> Dict[str, float]:
        g = self._policy.get("gating", {})
        return {
            "ae_min_coverage": float(g.get("ae_min_coverage", 0.8)),
            "ae_max_gap": float(g.get("ae_max_gap", 3)),
            "both_min_coverage": float(g.get("both_min_coverage", 0.6)),
            "w_coverage_c0": float(g.get("w_coverage_c0", 0.6)),
            "w_coverage_c1": float(g.get("w_coverage_c1", 0.95)),
        }

    def _decide_gate(self, q: QualityMeta) -> GateDecision:
        cfg = self._gating_cfg()
        core_ok = q.n_present >= self._core_min()
        ae_ok = (
            core_ok
            and q.coverage >= cfg["ae_min_coverage"]
            and q.uniform_ts
            and q.max_gap <= cfg["ae_max_gap"]
        )
        if ae_ok:
            return GateDecision(mode="AE_ONLY", ae_weight=1.0)

        if (not core_ok) or (q.coverage < cfg["both_min_coverage"]) or (not q.uniform_ts):
            return GateDecision(mode="IF_ONLY", ae_weight=0.0)

        c0 = cfg["w_coverage_c0"]
        c1 = max(cfg["w_coverage_c1"], c0 + 1e-6)
        w = (q.coverage - c0) / (c1 - c0)
        w = min(1.0, max(0.0, w))
        return GateDecision(mode="BOTH", ae_weight=float(w))

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

    def _feature_stats(self, x: np.ndarray) -> tuple[np.ndarray, List[str]]:
        vals: List[float] = []
        names: List[str] = []
        schema = self._schema_features()
        for fi, feat in enumerate(schema):
            col = x[:, fi]
            mean = float(np.nanmean(col)) if np.any(np.isfinite(col)) else 0.0
            std = float(np.nanstd(col)) if np.any(np.isfinite(col)) else 0.0
            min_v = float(np.nanmin(col)) if np.any(np.isfinite(col)) else 0.0
            max_v = float(np.nanmax(col)) if np.any(np.isfinite(col)) else 0.0
            slope = float(col[-1] - col[0]) if np.isfinite(col[-1]) and np.isfinite(col[0]) else 0.0
            dmean = float(np.nanmean(np.abs(np.diff(col)))) if len(col) > 1 else 0.0
            vals.extend([mean, std, min_v, max_v, slope, dmean])
            names.extend([
                f"{feat}:mean",
                f"{feat}:std",
                f"{feat}:min",
                f"{feat}:max",
                f"{feat}:slope",
                f"{feat}:diff_mean",
            ])
        return np.array(vals, dtype=np.float32), names

    def _score_iforest(self, x: np.ndarray) -> tuple[float, str, List[Dict[str, float]]]:
        stats, names = self._feature_stats(x)
        if not np.any(np.isfinite(stats)):
            return 0.0, "SKIPPED", []
        stats = np.nan_to_num(stats, nan=0.0, posinf=0.0, neginf=0.0)

        if self._iforest is not None:
            try:
                raw = float(self._iforest.decision_function(stats.reshape(1, -1))[0])
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

    def _apply_scaler(self, x: np.ndarray) -> np.ndarray:
        if not self._scaler:
            return x
        mean = np.array(self._scaler.get("mean", []), dtype=np.float32)
        std = np.array(self._scaler.get("std", []), dtype=np.float32)
        if mean.shape[0] != x.shape[1] or std.shape[0] != x.shape[1]:
            return x
        std = np.where(std == 0, 1.0, std)
        return (x - mean.reshape(1, -1)) / std.reshape(1, -1)

    def _score_ae(self, x: np.ndarray, mask: np.ndarray) -> tuple[Optional[float], str, List[Dict[str, float]]]:
        if self._ae_model is None:
            return None, "SKIPPED", []

        x_imp = self._impute(x, mask)
        x_scaled = self._apply_scaler(x_imp)

        try:
            import torch

            if hasattr(self._ae_model, "eval") and hasattr(self._ae_model, "__call__"):
                model = self._ae_model
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
        ae_cfg = self._policy.get("ae_score", {})
        e0 = float(ae_cfg.get("error_min", 0.0))
        e1 = float(max(ae_cfg.get("error_max", 0.2), e0 + 1e-6))
        score = float(min(1.0, max(0.0, (err - e0) / (e1 - e0))))

        feat_err = np.mean(err_mat, axis=0)
        top_idx = np.argsort(feat_err)[-3:][::-1]
        schema = self._schema_features()
        denom = float(np.sum(feat_err[top_idx]) + 1e-6)
        top = []
        for i in top_idx:
            feat = schema[int(i)] if int(i) < len(schema) else f"f{int(i)}"
            top.append({"feature": feat, "contribution": float(feat_err[int(i)] / denom)})

        return score, "PROCESSED", top

    def score_window(self, req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
        try:
            schema = self._schema_features()
            if not schema:
                return CommonEnvelope(
                    domain="engine",
                    status=EnvelopeStatus.SKIPPED,
                    method=EnvelopeMethod.hybrid,
                    score=0.0,
                    threshold=self._threshold(),
                    is_anomaly=False,
                    details={"reason": "missing schema_core.json", "events": []},
                )

            x, mask, q = align_window(
                window_samples=w.samples,
                schema_features=schema,
                sampling_hz=req.sampling_hz,
                timestamp_unit=req.timestamp_unit.value,
            )

            gate = self._decide_gate(q)
            score_if, st_if, top_if = self._score_iforest(x)
            score_ae, st_ae, top_ae = self._score_ae(x, mask)

            mode = gate.mode
            final = score_if
            top_signals = top_if
            details_status = {"ae": st_ae, "if": st_if}

            if mode == "AE_ONLY":
                if score_ae is None:
                    mode = "IF_ONLY"
                else:
                    final = float(score_ae)
                    top_signals = top_ae
            if mode == "BOTH":
                if score_ae is None:
                    mode = "IF_ONLY"
                else:
                    final = float(gate.ae_weight * score_ae + (1.0 - gate.ae_weight) * score_if)
                    merged: Dict[str, float] = {}
                    for item in top_ae:
                        merged[item["feature"]] = merged.get(item["feature"], 0.0) + gate.ae_weight * float(item["contribution"])
                    for item in top_if:
                        merged[item["feature"]] = merged.get(item["feature"], 0.0) + (1.0 - gate.ae_weight) * float(item["contribution"])
                    top_signals = [
                        {"feature": k, "contribution": v}
                        for k, v in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:3]
                    ]

            threshold = self._threshold()
            is_anom = bool(final >= threshold)
            return CommonEnvelope(
                domain="engine",
                status=EnvelopeStatus.PROCESSED,
                method=EnvelopeMethod.hybrid,
                score=float(final),
                threshold=threshold,
                is_anomaly=is_anom,
                details={
                    "model": {"name": "hybrid_ae_if", "version": "vfinal"},
                    "score_type": "hybrid_quality_gated",
                    "gating": {"mode": mode, "ae_weight": gate.ae_weight},
                    "quality": {
                        "n_present": q.n_present,
                        "coverage": q.coverage,
                        "max_gap": q.max_gap,
                        "uniform_ts": q.uniform_ts,
                    },
                    "status": details_status,
                    "top_signals": top_signals,
                    "events": ([{"type": "ENGINE_HYBRID_ANOMALY", "feature": "engine_hybrid_score", "value": float(final), "window_index": w.window_index}] if is_anom else []),
                },
            )
        except Exception as exc:
            return CommonEnvelope(
                domain="engine",
                status=EnvelopeStatus.ERROR,
                method=EnvelopeMethod.hybrid,
                score=0.0,
                threshold=self._threshold(),
                is_anomaly=False,
                details={"reason": f"engine scorer error: {exc}", "events": []},
            )
