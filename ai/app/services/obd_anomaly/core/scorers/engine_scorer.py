from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import torch
import torch.nn as nn

from ai.app.schemas.obd_anomaly_schema import CommonEnvelope, EnvelopeMethod, EnvelopeStatus, ObdAnomalyRequest
from ai.app.services.obd_anomaly.core.artifacts.loader import load_artifact_json, load_artifact_pickle
from ai.app.services.obd_anomaly.core.artifacts.registry import ArtifactRegistry
from ai.app.services.obd_anomaly.core.scorers.feature_alignment import QualityMeta, align_window
from ai.app.services.obd_anomaly.core.scorers.iforest_scorer import IForestScorer
from ai.app.services.obd_anomaly.core.scorers.lstm_ae_scorer import LSTMAEScorer
from ai.app.services.obd_anomaly.windowing import Window


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64, latent_dim: int = 16, num_layers: int = 1):
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.to_latent = nn.Linear(hidden_dim, latent_dim)
        self.from_latent = nn.Linear(latent_dim, hidden_dim)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, num_layers, batch_first=True)
        self.out = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        enc_out, _ = self.encoder(x)
        h_last = enc_out[:, -1, :]
        z = self.to_latent(h_last)
        h = self.from_latent(z).unsqueeze(1).repeat(1, x.size(1), 1)
        dec_out, _ = self.decoder(h)
        return self.out(dec_out)


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
        schema_features = self._schema_features()
        self._iforest = load_artifact_pickle(p["iforest"])
        self._ae_model = self._load_torch_model(p["lstm_ae"], input_dim=len(schema_features))

        self._if_scorer = IForestScorer(schema_features, self._iforest)
        self._ae_scorer = LSTMAEScorer(schema_features, self._ae_model, self._scaler, self._policy)

    def _load_scaler(self, path: Path) -> Dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None

    def _load_torch_model(self, path: Path, input_dim: int) -> Any:
        if not path.exists():
            return None
        try:
            try:
                obj = torch.load(path, map_location="cpu", weights_only=True)
            except TypeError:
                obj = torch.load(path, map_location="cpu")
        except Exception:
            try:
                import __main__

                setattr(__main__, "LSTMAutoencoder", LSTMAutoencoder)
                obj = torch.load(path, map_location="cpu")
            except Exception:
                return None

        if hasattr(obj, "eval") and hasattr(obj, "__call__"):
            return obj
        if isinstance(obj, dict):
            try:
                model = LSTMAutoencoder(max(1, int(input_dim)))
                model.load_state_dict(obj)
                model.eval()
                return model
            except Exception:
                return None
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

    def _normalize_top_signals(self, top: List[Dict[str, float]], top_k: int = 3) -> List[Dict[str, float]]:
        merged: Dict[str, float] = {}
        for item in top:
            feat = item.get("feature")
            contrib = item.get("contribution")
            if isinstance(feat, str) and isinstance(contrib, (int, float)):
                merged[feat] = merged.get(feat, 0.0) + max(0.0, float(contrib))
        ranked = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        if not ranked:
            return []
        denom = float(sum(v for _, v in ranked))
        if denom <= 0.0:
            w = 1.0 / float(len(ranked))
            return [{"feature": f, "contribution": w} for f, _ in ranked]
        return [{"feature": f, "contribution": float(v / denom)} for f, v in ranked]

    def _detect_hard_limit_event(self, w: Window) -> Dict[str, Any] | None:
        # Physical hard-limit guardrail for clearly impossible values.
        hard_limits = {
            "engine_rpm": 8000.0,
            "vehicle_speed_kmh": 240.0,
            "throttle_pos_pct": 100.0,
            "imap_kpa": 250.0,
            "engine_coolant_temp_c": 150.0,
            "intake_air_temp_c": 100.0,
            "maf_gps": 150.0,
        }
        for s in w.samples:
            for feat, limit in hard_limits.items():
                v = s.features.get(feat)
                if isinstance(v, (int, float)) and float(v) > limit:
                    return {
                        "type": "ENGINE_HARD_LIMIT_ANOMALY",
                        "feature": feat,
                        "value": float(v),
                        "window_index": w.window_index,
                        "severity": "CRITICAL",
                        "message": f"hard-limit exceeded: {feat}>{limit}",
                    }
        return None

    def _detect_stall_event(self, w: Window) -> Dict[str, Any] | None:
        rpms: List[float] = []
        speeds: List[float] = []
        for s in w.samples:
            rv = s.features.get("engine_rpm")
            sv = s.features.get("vehicle_speed_kmh")
            rpms.append(float(rv) if isinstance(rv, (int, float)) else float("nan"))
            speeds.append(float(sv) if isinstance(sv, (int, float)) else float("nan"))

        if len(rpms) < 3:
            return None

        for i in range(1, len(rpms)):
            prev_rpm = rpms[i - 1]
            cur_rpm = rpms[i]
            if not (prev_rpm == prev_rpm and cur_rpm == cur_rpm):  # nan check
                continue
            # Stall-like drop: high rpm -> near-zero rpm within one step.
            if prev_rpm >= 1200.0 and cur_rpm <= 400.0:
                cur_spd = speeds[i]
                prev_spd = speeds[i - 1]
                if not (cur_spd == cur_spd):  # nan check
                    continue
                # Vehicle still moving/rolling while rpm collapses.
                if cur_spd >= 20.0 and ((prev_spd != prev_spd) or ((prev_spd - cur_spd) <= 15.0)):
                    return {
                        "type": "ENGINE_STALL_SUSPECT",
                        "feature": "engine_rpm",
                        "value": float(cur_rpm),
                        "window_index": w.window_index,
                        "severity": "WARNING",
                        "message": "rpm sudden drop while vehicle is moving; possible engine stall",
                    }
        return None

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
            score_if, st_if, top_if = 0.0, "SKIPPED", []
            score_ae, st_ae, top_ae = None, "SKIPPED", []

            mode = gate.mode
            final = 0.0
            top_signals: List[Dict[str, float]] = []

            if mode in ("IF_ONLY", "BOTH"):
                score_if, st_if, top_if = self._if_scorer.score(x)
            if mode in ("AE_ONLY", "BOTH"):
                score_ae, st_ae, top_ae = self._ae_scorer.score(x, mask)

            if mode == "AE_ONLY":
                if score_ae is None:
                    mode = "IF_ONLY"
                    score_if, st_if, top_if = self._if_scorer.score(x)
                    final = float(score_if)
                    top_signals = top_if
                else:
                    final = float(score_ae)
                    top_signals = self._normalize_top_signals(top_ae)
            elif mode == "IF_ONLY":
                final = float(score_if)
                top_signals = self._normalize_top_signals(top_if)
            elif mode == "BOTH":
                if score_ae is None:
                    mode = "IF_ONLY"
                    final = float(score_if)
                    top_signals = self._normalize_top_signals(top_if)
                else:
                    final = float(gate.ae_weight * score_ae + (1.0 - gate.ae_weight) * score_if)
                    merged: Dict[str, float] = {}
                    for item in top_ae:
                        merged[item["feature"]] = merged.get(item["feature"], 0.0) + gate.ae_weight * float(item["contribution"])
                    for item in top_if:
                        merged[item["feature"]] = merged.get(item["feature"], 0.0) + (1.0 - gate.ae_weight) * float(item["contribution"])
                    top_signals = self._normalize_top_signals([
                        {"feature": k, "contribution": v}
                        for k, v in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:3]
                    ])
            details_status = {"ae": st_ae, "if": st_if}

            threshold = self._threshold()
            is_anom = bool(final >= threshold)
            hard_limit_event = self._detect_hard_limit_event(w)
            stall_event = self._detect_stall_event(w)
            if hard_limit_event is not None:
                # Keep decision score-driven: no direct is_anomaly force.
                # Hard-limit exceedance adds a strong score bonus.
                final = min(1.0, max(final, float(final + 0.3)))
                is_anom = bool(final >= threshold)
            missing_features: List[str] = []
            if q.n_present < self._core_min():
                missing_features = [
                    feat
                    for idx, feat in enumerate(schema)
                    if idx < mask.shape[1] and float(mask[:, idx].sum()) <= 0.0
                ]

            events: List[Dict[str, Any]] = []
            if q.n_present < self._core_min():
                events.append(
                    {
                        "type": "INSUFFICIENT_CORE_FEATURES",
                        "feature": "core7_quality",
                        "value": float(q.n_present),
                        "window_index": w.window_index,
                        "message": "core feature shortage; degraded IF_ONLY path",
                        "n_present": int(q.n_present),
                        "core_min_target": int(self._core_min()),
                        "missing_features": missing_features,
                    }
                )
            if hard_limit_event is not None:
                events.append(hard_limit_event)
            if stall_event is not None:
                events.append(stall_event)
            if is_anom:
                events.append(
                    {
                        "type": "ENGINE_HYBRID_ANOMALY",
                        "feature": "engine_hybrid_score",
                        "value": float(final),
                        "window_index": w.window_index,
                    }
                )
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
                    "events": events,
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

