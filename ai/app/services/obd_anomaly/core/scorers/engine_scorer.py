from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.core.artifacts.loader import load_artifact_json, load_artifact_pickle
from ai.app.services.obd_anomaly.core.artifacts.registry import ArtifactRegistry
from ai.app.services.obd_anomaly.core.scorers.feature_alignment import QualityMeta, align_window
from ai.app.services.obd_anomaly.core.scorers.iforest_scorer import IForestScorer
from ai.app.services.obd_anomaly.core.scorers.lstm_ae_scorer import LSTMAEScorer
from ai.app.services.obd_anomaly.windowing import Window


@dataclass(frozen=True)
class GateDecision:
    mode: str
    ae_weight: float


class EngineScorer:
    def __init__(self) -> None:
        base = Path(__file__).resolve().parents[2]
        reg = ArtifactRegistry(base)
        p = reg.paths()

        self._schema = load_artifact_json(p["schema_core"], {"features": [], "core_min": 1})
        self._policy = load_artifact_json(p["threshold_policy"], {})
        self._scaler = self._load_scaler(p["scaler"])
        self._iforest = load_artifact_pickle(p["iforest"])
        self._ae_model = self._load_torch_model(p["lstm_ae"])

        schema_features = self._schema_features()
        self._if_scorer = IForestScorer(schema_features, self._iforest)
        self._ae_scorer = LSTMAEScorer(schema_features, self._ae_model, self._scaler, self._policy)

    def _load_scaler(self, path: Path) -> Dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_torch_model(self, path: Path) -> Any:
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
            score_if, st_if, top_if = self._if_scorer.score(x)
            score_ae, st_ae, top_ae = self._ae_scorer.score(x, mask)

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
                    "events": (
                        [
                            {
                                "type": "ENGINE_HYBRID_ANOMALY",
                                "feature": "engine_hybrid_score",
                                "value": float(final),
                                "window_index": w.window_index,
                            }
                        ]
                        if is_anom
                        else []
                    ),
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

