from __future__ import annotations

from pathlib import Path
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
from ai.app.services.obd_anomaly.core.artifacts.registry import ArtifactRegistry
from ai.app.services.obd_anomaly.core.policy.threshold_policy import apply_engine_policy, load_threshold_policy
from ai.app.services.obd_anomaly.domains.domain_registry import DOMAIN_REGISTRY


DEFAULT_DOMAINS = ["engine", "electrical", "brake", "tire", "idle"]


class ObdAnomalyService:
    def __init__(self) -> None:
        self._engine_policy_cache: Dict[str, Any] | None = None

    def run(self, req: ObdAnomalyRequest) -> ObdAnomalyResponse:
        self._validate(req)
        effective_duration_sec = self._effective_duration_sec(req)
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

            domain_envs: Dict[str, CommonEnvelope] = {}
            for domain in selected_domains:
                if domain == "engine":
                    continue

                runner = DOMAIN_REGISTRY.get(domain)
                if not runner:
                    domain_envs[domain] = CommonEnvelope(
                        domain=domain,
                        status=EnvelopeStatus.UNSUPPORTED,
                        method=EnvelopeMethod.rule,
                        score=None,
                        threshold=None,
                        is_anomaly=False,
                        details={"reason": "unknown domain"},
                    )
                    continue
                domain_envs[domain] = runner(req, w)

            window_results.append(
                WindowResult(
                    window_index=w.window_index,
                    start_t=w.start_t,
                    end_t=w.end_t,
                    core=core_env,
                    domains=domain_envs,
                )
            )

        summary_core = self._aggregate_core(window_results)
        summary_ext = self._aggregate_domains(window_results)
        summary_core, engine_policy_events = self._apply_engine_policy(summary_core, window_results)

        domains = self._build_summary_domains(req, summary_core, summary_ext, selected_domains)
        events = self._collect_events({"engine": summary_core, **summary_ext}, selected_domains)
        events.extend(self._collect_engine_info_events(summary_core))
        events.extend(engine_policy_events)
        events = self._compact_events(events)
        is_anomaly = any(v.is_anomaly for v in domains.values())
        anomaly_score = self._calc_anomaly_score(summary_core, domains)

        meta = ResponseMeta(
            vehicle_id=req.vehicle_id,
            trip_id=req.trip_id,
            timestamp_unit=req.timestamp_unit,
            total_duration_sec=effective_duration_sec,
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

    def _apply_engine_policy(
        self,
        summary_core: CommonEnvelope,
        window_results: List[WindowResult],
    ) -> tuple[CommonEnvelope, List[AnomalyEvent]]:
        if summary_core.status != EnvelopeStatus.PROCESSED:
            return summary_core, []

        policy = self._load_engine_policy()
        threshold = float(policy.get("threshold", summary_core.threshold if summary_core.threshold is not None else 0.7))
        scores: List[float] = []
        starts: List[int] = []
        for w in window_results:
            if w.core.status != EnvelopeStatus.PROCESSED or w.core.score is None:
                continue
            scores.append(float(w.core.score))
            starts.append(int(w.start_t))

        if not scores:
            return summary_core, []

        pe = apply_engine_policy(scores, starts, policy)
        policy_events: List[AnomalyEvent] = []
        for e in pe:
            sev = self._severity_from_score(float(e.get("severity_score", 0.0)), policy)
            policy_events.append(
                AnomalyEvent(
                    type=str(e.get("type", "ENGINE_POLICY_ANOMALY")),
                    domain="engine",
                    feature=str(e.get("feature", "engine_hybrid_score")),
                    value=e.get("value"),
                    threshold=threshold,
                    window_index=e.get("window_index"),
                    severity=sev,
                    message=f"engine anomaly confirmed by policy ({sev.value})",
                )
            )

        summary_core.threshold = threshold
        summary_core.is_anomaly = bool(policy_events)
        summary_core.details["policy"] = {
            "threshold": threshold,
            "k_consecutive": int(policy.get("k_consecutive", 1)),
            "cooldown_sec": int(policy.get("cooldown_sec", 0)),
        }
        return summary_core, policy_events

    def _load_engine_policy(self) -> Dict[str, Any]:
        if self._engine_policy_cache is not None:
            return self._engine_policy_cache
        base_dir = Path(__file__).resolve().parent
        reg = ArtifactRegistry(base_dir)
        paths = reg.paths()
        self._engine_policy_cache = load_threshold_policy(paths["threshold_policy"])
        return self._engine_policy_cache

    def _severity_from_score(self, score: float, policy: Dict[str, Any] | None = None) -> EventSeverity:
        sev_cfg = (policy or {}).get("severity", {})
        critical = float(sev_cfg.get("critical", 0.85))
        warning = float(sev_cfg.get("warning", 0.7))
        if score >= critical:
            return EventSeverity.CRITICAL
        if score >= warning:
            return EventSeverity.WARNING
        return EventSeverity.INFO

    def _validate(self, req: ObdAnomalyRequest) -> None:
        if not req.data:
            raise ValueError("data must not be empty")
        # Backend may send variable-length trailing chunks (not always 900s).
        # Keep request tolerant and use actual payload length as effective duration.

    def _effective_duration_sec(self, req: ObdAnomalyRequest) -> int:
        return int(len(req.data) / max(1, req.sampling_hz))

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
        if not out:
            return None
        top = out[: req.options.top_k]
        s = sum(max(0.0, t.contribution) for t in top)
        if s > 0:
            top = [TopSignal(feature=t.feature, contribution=max(0.0, t.contribution) / s) for t in top]
        else:
            w = 1.0 / float(len(top))
            top = [TopSignal(feature=t.feature, contribution=w) for t in top]
        return top

    def _collect_events(
        self,
        summary_envs: Dict[str, CommonEnvelope],
        selected_domains: List[str],
    ) -> List[AnomalyEvent]:
        out: List[AnomalyEvent] = []
        seen: set[tuple[str, str, str, str, str, str]] = set()

        def add_event_once(event: AnomalyEvent) -> None:
            key = (
                event.type,
                event.domain,
                event.feature,
                str(event.window_index),
                str(event.value),
                str(event.threshold),
            )
            if key in seen:
                return
            seen.add(key)
            out.append(event)

        for domain in selected_domains:
            env = summary_envs.get(domain)
            if env is None:
                continue

            # Engine final anomaly/event emission is policy-driven.
            # Engine policy events are appended in run(), so skip engine here
            # to avoid score/event/flag mismatch in summary responses.
            if domain == "engine":
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
                    add_event_once(
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
                    add_event_once(
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

    def _collect_engine_info_events(self, summary_core: CommonEnvelope) -> List[AnomalyEvent]:
        out: List[AnomalyEvent] = []
        events = summary_core.details.get("events", [])
        if not isinstance(events, list):
            return out

        grouped: Dict[tuple[str, str, str, str], Dict[str, Any]] = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            etype = str(event.get("type", "ANOMALY_EVENT"))
            if etype == "ENGINE_HYBRID_ANOMALY":
                continue
            feature = event.get("feature")
            if not isinstance(feature, str) or not feature:
                feature = "engine_quality"
            value = event.get("value")
            sev_raw = str(event.get("severity", "INFO")).upper()
            sev = EventSeverity.INFO
            if sev_raw in ("WARNING", "CRITICAL", "INFO"):
                sev = EventSeverity(sev_raw)
            key = (etype, feature, str(value), sev.value)
            if key not in grouped:
                grouped[key] = {
                    "value": value,
                    "message": event.get("message") or "engine quality advisory",
                    "windows": set(),
                    "severity": sev,
                }
            win = event.get("window_index")
            if isinstance(win, int):
                grouped[key]["windows"].add(win)

        for (etype, feature, _, _), info in grouped.items():
            wins = sorted(list(info["windows"]))
            msg = str(info["message"])
            if wins:
                msg = f"{msg} (affected_windows={len(wins)})"
            out.append(
                AnomalyEvent(
                    type=etype,
                    domain="engine",
                    feature=feature,
                    value=info["value"],
                    threshold=summary_core.threshold,
                    window_index=None,
                    severity=info["severity"],
                    message=msg,
                )
            )
        return out

    def _severity_for_domain(self, domain: str) -> EventSeverity:
        if domain in ("engine", "brake"):
            return EventSeverity.CRITICAL
        if domain in ("electrical", "tire"):
            return EventSeverity.WARNING
        return EventSeverity.INFO

    def _compact_events(self, events: List[AnomalyEvent]) -> List[AnomalyEvent]:
        grouped: Dict[tuple[str, str, str, str], List[AnomalyEvent]] = {}
        for e in events:
            key = (e.type, e.domain, e.feature, e.severity.value)
            grouped.setdefault(key, []).append(e)

        out: List[AnomalyEvent] = []
        for (_, _, _, _), group in grouped.items():
            if len(group) == 1:
                out.append(group[0])
                continue

            base = group[0]
            nums = [float(g.value) for g in group if isinstance(g.value, (int, float))]
            value: float | int | str | None = base.value
            if nums:
                value = float(min(nums))

            out.append(
                AnomalyEvent(
                    type=base.type,
                    domain=base.domain,
                    feature=base.feature,
                    value=value,
                    threshold=base.threshold,
                    window_index=None,
                    severity=base.severity,
                    message=f"{base.message} (occurrences={len(group)})",
                )
            )
        return out

    def _calc_anomaly_score(self, summary_core: CommonEnvelope, domains: Dict[str, DomainResult]) -> float | None:
        # Keep top-level score consistent with final anomaly decision.
        # - if no domain is finally anomalous -> score 0.0
        # - if anomalous -> use max score among anomalous domains
        final_anomaly = any(d.is_anomaly for d in domains.values())
        if not final_anomaly:
            return 0.0

        scores = [float(d.score) for d in domains.values() if d.is_anomaly and d.score is not None]
        if scores:
            return float(max(scores))

        # Safety fallback when anomaly flag exists without numeric score.
        return 1.0

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
                env = w.domains.get(d)
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

    def _aggregate_domains(self, window_results: List[WindowResult]) -> Dict[str, CommonEnvelope]:
        keys = set()
        for w in window_results:
            keys.update(w.domains.keys())

        out: Dict[str, CommonEnvelope] = {}

        for k in keys:
            envs = [w.domains[k] for w in window_results if k in w.domains]
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
