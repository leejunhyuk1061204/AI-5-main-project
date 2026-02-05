from __future__ import annotations

from typing import Any, Dict, List

from ai.app.schemas.obd_anomaly_schema import (
    AnomalyEvent,
    CommonEnvelope,
    DomainResult,
    EnvelopeMethod,
    EnvelopeStatus,
    EventSeverity,
    ObdAnomalyRequest,
    ObdAnomalyResponse,
    ResponseMeta,
    TopSignal,
    WindowResult,
)
from ai.app.services.obd_anomaly.windowing import make_windows
from ai.app.services.obd_anomaly.core.engine_lstm_ae import run_engine_lstm_ae
from ai.app.services.obd_anomaly.extensions.extension_registry import EXTENSION_REGISTRY


DEFAULT_DOMAINS = ["engine", "electrical", "brake", "tire", "idle"]


class ObdAnomalyService:
    def run(self, req: ObdAnomalyRequest) -> ObdAnomalyResponse:
        self._validate(req)
        selected_domains = self._resolve_domains(req)

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
            for domain in selected_domains:
                if domain == "engine":
                    continue

                runner = EXTENSION_REGISTRY.get(domain)
                if not runner:
                    ext_envs[domain] = CommonEnvelope(
                        domain=domain,
                        status=EnvelopeStatus.UNSUPPORTED,
                        method=EnvelopeMethod.rule,
                        score=None,
                        threshold=None,
                        is_anomaly=False,
                        details={"reason": "unknown extension"},
                    )
                    continue
                ext_envs[domain] = runner(req, w)

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

        domains = self._build_summary_domains(req, summary_core, summary_ext, selected_domains)
        events = self._collect_events({"engine": summary_core, **summary_ext}, selected_domains)
        is_anomaly = any(v.is_anomaly for v in domains.values())
        anomaly_score = self._calc_anomaly_score(summary_core, domains)

        meta = ResponseMeta(
            vehicle_id=req.vehicle_id,
            trip_id=req.trip_id,
            timestamp_unit=req.timestamp_unit,
            total_duration_sec=req.duration_sec,
            window_sec=req.options.window_sec,
            stride_sec=req.options.stride_sec,
            num_windows=len(window_results),
        )

        include_raw = req.options.return_ == "raw"

        return ObdAnomalyResponse(
            meta=meta,
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            domains=domains,
            events=events,
            window_results=self._build_raw_window_results(req, window_results, selected_domains) if include_raw else [],
        )

    def _validate(self, req: ObdAnomalyRequest) -> None:
        expected_len = req.duration_sec * req.sampling_hz
        if len(req.data) != expected_len:
            raise ValueError(f"data length mismatch: got={len(req.data)}, expected={expected_len}")

    def _resolve_domains(self, req: ObdAnomalyRequest) -> List[str]:
        domains = list(req.options.domains or DEFAULT_DOMAINS)
        if "engine" not in domains:
            domains.insert(0, "engine")

        out: List[str] = []
        for d in domains:
            if d not in out:
                out.append(d)
        return out

    def _build_summary_domains(
        self,
        req: ObdAnomalyRequest,
        summary_core: CommonEnvelope,
        summary_ext: Dict[str, CommonEnvelope],
        selected_domains: List[str],
    ) -> Dict[str, DomainResult]:
        out: Dict[str, DomainResult] = {}
        out["engine"] = self._to_domain_result(req, summary_core)

        for d in selected_domains:
            if d == "engine":
                continue
            env = summary_ext.get(d)
            if env is None:
                env = CommonEnvelope(
                    domain=d,
                    status=EnvelopeStatus.UNSUPPORTED,
                    method=EnvelopeMethod.rule,
                    score=None,
                    threshold=None,
                    is_anomaly=False,
                    details={"reason": "domain not available"},
                )
            out[d] = self._to_domain_result(req, env)

        return out

    def _to_domain_result(self, req: ObdAnomalyRequest, env: CommonEnvelope) -> DomainResult:
        return DomainResult(
            domain=env.domain,
            status=env.status,
            score=env.score,
            threshold=env.threshold,
            is_anomaly=env.is_anomaly,
            top_signals=self._extract_top_signals(req, env),
        )

    def _extract_top_signals(self, req: ObdAnomalyRequest, env: CommonEnvelope) -> List[TopSignal] | None:
        if env.domain != "engine":
            return None
        if req.options.top_signals == "off":
            return None
        if req.options.top_signals == "on_anomaly" and not env.is_anomaly:
            return None

        raw = env.details.get("top_signals", [])
        if not isinstance(raw, list):
            return None

        out: List[TopSignal] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            feature = item.get("feature")
            contribution = item.get("contribution")
            if isinstance(feature, str) and isinstance(contribution, (int, float)):
                out.append(TopSignal(feature=feature, contribution=float(contribution)))
        return out[: req.options.top_k] if out else None

    def _collect_events(
        self,
        summary_envs: Dict[str, CommonEnvelope],
        selected_domains: List[str],
    ) -> List[AnomalyEvent]:
        out: List[AnomalyEvent] = []

        for domain in selected_domains:
            env = summary_envs.get(domain)
            if env is None:
                continue

            # rule 기반 우선
            rules = env.details.get("rules", [])
            if isinstance(rules, list):
                for rule in rules:
                    if not isinstance(rule, dict) or not bool(rule.get("triggered")):
                        continue
                    feature = rule.get("feature")
                    if not isinstance(feature, str) or not feature:
                        continue
                    out.append(
                        AnomalyEvent(
                            type=str(rule.get("id", "RULE_TRIGGERED")),
                            domain=domain,
                            feature=feature,
                            value=rule.get("value"),
                            threshold=env.threshold,
                            window_index=None,
                            severity=self._severity_for_domain(domain),
                            message=f"{domain} anomaly detected on {feature}",
                        )
                    )

            # details.events fallback
            events = env.details.get("events", [])
            if isinstance(events, list):
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    feature = event.get("feature")
                    if not isinstance(feature, str) or not feature:
                        if domain == "engine":
                            feature = "engine_reconstruction_error"
                        else:
                            continue
                    out.append(
                        AnomalyEvent(
                            type=str(event.get("type", "ANOMALY_EVENT")),
                            domain=domain,
                            feature=feature,
                            value=event.get("value"),
                            threshold=env.threshold,
                            window_index=event.get("window_index"),
                            severity=self._severity_for_domain(domain),
                            message=event.get("message") or f"{domain} anomaly event",
                        )
                    )

        return out

    def _severity_for_domain(self, domain: str) -> EventSeverity:
        if domain in ("engine", "brake"):
            return EventSeverity.CRITICAL
        if domain in ("electrical", "tire"):
            return EventSeverity.WARNING
        return EventSeverity.INFO

    def _calc_anomaly_score(self, summary_core: CommonEnvelope, domains: Dict[str, DomainResult]) -> float | None:
        if summary_core.score is not None:
            return float(summary_core.score)
        scores = [d.score for d in domains.values() if d.score is not None]
        return float(max(scores)) if scores else None

    def _build_raw_window_results(
        self,
        req: ObdAnomalyRequest,
        window_results: List[WindowResult],
        selected_domains: List[str],
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for w in window_results:
            domains: Dict[str, Dict[str, Any]] = {
                "engine": self._domain_result_dict(req, w.core)
            }
            for d in selected_domains:
                if d == "engine":
                    continue
                env = w.extensions.get(d)
                if env is not None:
                    domains[d] = self._domain_result_dict(req, env)

            out.append(
                {
                    "window_index": w.window_index,
                    "start_t": w.start_t,
                    "end_t": w.end_t,
                    "domains": domains,
                }
            )
        return out

    def _domain_result_dict(self, req: ObdAnomalyRequest, env: CommonEnvelope) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "domain": env.domain,
            "status": env.status.value if isinstance(env.status, EnvelopeStatus) else env.status,
            "score": env.score,
            "threshold": env.threshold,
            "is_anomaly": env.is_anomaly,
        }
        top_signals = self._extract_top_signals(req, env)
        if top_signals:
            result["top_signals"] = [s.model_dump() for s in top_signals]
        return result

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

        scores = [e.score for e in processed if e.score is not None]
        agg_score = max(scores) if scores else None
        any_anom = any(e.is_anomaly for e in processed)

        anomaly_windows = [i for i, w in enumerate(window_results) if w.core.status == EnvelopeStatus.PROCESSED and w.core.is_anomaly]

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
                "top_signals": processed[0].details.get("top_signals", []),
                "events": events,
            },
        )

    def _aggregate_extensions(self, window_results: List[WindowResult]) -> Dict[str, CommonEnvelope]:
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
            score = 1.0 if any_anom else 0.0
            threshold = processed[0].threshold

            events = []
            rules = []
            for e in processed:
                ev = e.details.get("events", [])
                if isinstance(ev, list):
                    events.extend(ev)
                rs = e.details.get("rules", [])
                if isinstance(rs, list):
                    rules.extend(rs)

            out[k] = CommonEnvelope(
                domain=k,
                status=EnvelopeStatus.PROCESSED,
                method=processed[0].method,
                score=score if processed[0].method == EnvelopeMethod.rule else processed[0].score,
                threshold=threshold,
                is_anomaly=any_anom,
                details={
                    "aggregation": "any_triggered" if processed[0].method == EnvelopeMethod.rule else "max_over_windows",
                    "rules": rules,
                    "events": events,
                },
            )

        return out
