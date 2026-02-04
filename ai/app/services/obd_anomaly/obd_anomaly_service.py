from __future__ import annotations

from typing import Dict, List

from ai.app.schemas.obd_anomaly_schema import (
    CommonEnvelope,
    EnvelopeMethod,
    EnvelopeStatus,
    ObdAnomalyRequest,
    ObdAnomalyResponse,
    ResponseMeta,
    WindowResult,
)
from ai.app.services.obd_anomaly.windowing import make_windows
from ai.app.services.obd_anomaly.core.engine_lstm_ae import run_engine_lstm_ae
from ai.app.services.obd_anomaly.extensions.extension_registry import EXTENSION_REGISTRY


class ObdAnomalyService:
    def run(self, req: ObdAnomalyRequest) -> ObdAnomalyResponse:
        self._validate(req)

        windows = make_windows(
            data=req.data,
            sampling_hz=req.sampling_hz,
            window_sec=req.options.window_sec,
            stride_sec=req.options.stride_sec,
        )

        window_results: List[WindowResult] = []
        for w in windows:
            core_env = run_engine_lstm_ae(req, w)

            ext_envs: Dict[str, CommonEnvelope] = {}
            for ext_name in req.options.extensions:
                runner = EXTENSION_REGISTRY.get(ext_name)
                if not runner:
                    ext_envs[ext_name] = CommonEnvelope(
                        domain=ext_name,
                        status=EnvelopeStatus.UNSUPPORTED,
                        method=EnvelopeMethod.rule,
                        score=None,
                        threshold=None,
                        is_anomaly=False,
                        details={"reason": "unknown extension"},
                    )
                    continue
                ext_envs[ext_name] = runner(req, w)

            window_results.append(
                WindowResult(
                    window_index=w.window_index,
                    start_t=w.start_t,
                    end_t=w.end_t,
                    core=core_env,
                    extensions=ext_envs,
                )
            )

        summary_core = self._aggregate_core(window_results)
        summary_ext = self._aggregate_extensions(window_results)

        meta = ResponseMeta(
            vehicle_id=req.vehicle_id,
            trip_id=req.trip_id,
            timestamp_unit=req.timestamp_unit,
            total_duration_sec=req.duration_sec,
            window_sec=req.options.window_sec,
            stride_sec=req.options.stride_sec,
            num_windows=len(window_results),
        )

        include_raw = (req.options.return_ == "raw")

        return ObdAnomalyResponse(
            meta=meta,
            window_results=window_results if include_raw else [],
            core=summary_core,
            extensions=summary_ext,
        )

    def _validate(self, req: ObdAnomalyRequest) -> None:
        expected_len = req.duration_sec * req.sampling_hz
        if len(req.data) != expected_len:
            raise ValueError(f"data length mismatch: got={len(req.data)}, expected={expected_len}")

        # timestamp_unit v1에서는 "s"만 허용하려면 여기에 강제 가능
        # if req.timestamp_unit != "s": raise ValueError("v1 only supports seconds")

    def _aggregate_core(self, window_results: List[WindowResult]) -> CommonEnvelope:
        envs = [w.core for w in window_results]
        processed = [e for e in envs if e.status == EnvelopeStatus.PROCESSED]
        errors = [e for e in envs if e.status == EnvelopeStatus.ERROR]

        if errors:
            return CommonEnvelope(
                domain="engine",
                status=EnvelopeStatus.ERROR,
                method=EnvelopeMethod.hybrid,
                score=None,
                threshold=None,
                is_anomaly=False,
                details={"reason": "one or more windows errored", "events": []},
            )

        if not processed:
            # 전부 SKIPPED/UNSUPPORTED
            status = envs[0].status if envs else EnvelopeStatus.SKIPPED
            return CommonEnvelope(
                domain="engine",
                status=status,
                method=EnvelopeMethod.hybrid,
                score=None,
                threshold=None,
                is_anomaly=False,
                details={"events": []},
            )

        # summary 규칙(예시): score=max, anomaly=any_true
        scores = [e.score for e in processed if e.score is not None]
        agg_score = max(scores) if scores else None
        any_anom = any(e.is_anomaly for e in processed)

        # anomaly_windows
        anomaly_windows = [i for i, w in enumerate(window_results) if w.core.status == EnvelopeStatus.PROCESSED and w.core.is_anomaly]

        # events flatten
        events = []
        for e in processed:
            ev = e.details.get("events", [])
            if isinstance(ev, list):
                events.extend(ev)

        return CommonEnvelope(
            domain="engine",
            status=EnvelopeStatus.PROCESSED,
            method=processed[0].method,
            score=agg_score,
            threshold=processed[0].threshold,
            is_anomaly=any_anom,
            details={
                "aggregation": "max_over_windows",
                "anomaly_windows": anomaly_windows,
                "model": processed[0].details.get("model", {}),
                "score_type": processed[0].details.get("score_type"),
                "events": events,
            },
        )

    def _aggregate_extensions(self, window_results: List[WindowResult]) -> Dict[str, CommonEnvelope]:
        # 모든 window의 extension key union
        keys = set()
        for w in window_results:
            keys.update(w.extensions.keys())

        out: Dict[str, CommonEnvelope] = {}

        for k in keys:
            envs = [w.extensions[k] for w in window_results if k in w.extensions]
            processed = [e for e in envs if e.status == EnvelopeStatus.PROCESSED]
            errors = [e for e in envs if e.status == EnvelopeStatus.ERROR]

            if errors:
                out[k] = CommonEnvelope(
                    domain=k,
                    status=EnvelopeStatus.ERROR,
                    method=EnvelopeMethod.hybrid,
                    score=None,
                    threshold=None,
                    is_anomaly=False,
                    details={"reason": "one or more windows errored", "events": []},
                )
                continue

            if not processed:
                status = envs[0].status if envs else EnvelopeStatus.SKIPPED
                out[k] = CommonEnvelope(
                    domain=k,
                    status=status,
                    method=EnvelopeMethod.hybrid,
                    score=None,
                    threshold=None,
                    is_anomaly=False,
                    details={"events": []},
                )
                continue

            any_anom = any(e.is_anomaly for e in processed)
            score = 1.0 if any_anom else 0.0  # rule은 0/1로 요약하는 게 자연스러움
            threshold = processed[0].threshold

            events = []
            for e in processed:
                ev = e.details.get("events", [])
                if isinstance(ev, list):
                    events.extend(ev)

            out[k] = CommonEnvelope(
                domain=k,
                status=EnvelopeStatus.PROCESSED,
                method=processed[0].method,
                score=score if processed[0].method == EnvelopeMethod.rule else processed[0].score,
                threshold=threshold,
                is_anomaly=any_anom,
                details={
                    "aggregation": "any_triggered" if processed[0].method == EnvelopeMethod.rule else "max_over_windows",
                    "events": events,
                },
            )

        return out
