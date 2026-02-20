from __future__ import annotations

from typing import Any, Dict, List

from ai.app.schemas.obd_anomaly_schema import (
    CommonEnvelope,
    EnvelopeMethod,
    EnvelopeStatus,
    ObdAnomalyRequest,
)
from ai.app.services.obd_anomaly.windowing import Window


def run_electrical(req: ObdAnomalyRequest, w: Window) -> CommonEnvelope:
    domain = "electrical"

    # Segment-aware battery voltage checks:
    # - OFF/near-cranking: rpm < 300
    # - ON/charging: rpm >= 300
    voltage_all: List[float] = []
    voltage_off: List[float] = []
    voltage_on: List[float] = []
    has_rpm = False

    for s in w.samples:
        v = s.features.get("battery_voltage_v")
        if not isinstance(v, (int, float)):
            continue
        vf = float(v)
        voltage_all.append(vf)

        rpm = s.features.get("engine_rpm")
        if isinstance(rpm, (int, float)):
            has_rpm = True
            if float(rpm) < 300.0:
                voltage_off.append(vf)
            else:
                voltage_on.append(vf)

    if not voltage_all:
        return CommonEnvelope(
            domain=domain,
            status=EnvelopeStatus.UNSUPPORTED,
            method=EnvelopeMethod.rule,
            score=None,
            threshold=None,
            is_anomaly=False,
            details={"reason": "battery_voltage_v not found"},
        )

    rules: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    has_warning = False
    has_critical = False

    # OFF range:
    # normal: 12.4~12.8, warning: 12.0~12.3, critical: <11.8
    if voltage_off:
        min_off = min(voltage_off)
        if min_off < 11.8:
            has_critical = True
            rules.append(
                {
                    "id": "VOLTAGE_OFF_CRITICAL_LOW",
                    "feature": "battery_voltage_v",
                    "value": min_off,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_OFF_CRITICAL_LOW", "feature": "battery_voltage_v", "value": min_off}
            )
        elif min_off < 12.4:
            has_warning = True
            rules.append(
                {
                    "id": "VOLTAGE_OFF_WARNING_LOW",
                    "feature": "battery_voltage_v",
                    "value": min_off,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_OFF_WARNING_LOW", "feature": "battery_voltage_v", "value": min_off}
            )

    # ON range:
    # normal: 13.5~14.8, warning: 12.4~13.4 or 14.9~15.1, critical: <12.4 or >=15.2
    if voltage_on:
        min_on = min(voltage_on)
        max_on = max(voltage_on)
        if min_on < 12.4:
            has_critical = True
            rules.append(
                {
                    "id": "VOLTAGE_ON_CRITICAL_LOW",
                    "feature": "battery_voltage_v",
                    "value": min_on,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_ON_CRITICAL_LOW", "feature": "battery_voltage_v", "value": min_on}
            )
        elif min_on < 13.5:
            has_warning = True
            rules.append(
                {
                    "id": "VOLTAGE_ON_WARNING_LOW",
                    "feature": "battery_voltage_v",
                    "value": min_on,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_ON_WARNING_LOW", "feature": "battery_voltage_v", "value": min_on}
            )

        if max_on >= 15.2:
            has_critical = True
            rules.append(
                {
                    "id": "VOLTAGE_ON_CRITICAL_HIGH",
                    "feature": "battery_voltage_v",
                    "value": max_on,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_ON_CRITICAL_HIGH", "feature": "battery_voltage_v", "value": max_on}
            )
        elif max_on > 14.8:
            has_warning = True
            rules.append(
                {
                    "id": "VOLTAGE_ON_WARNING_HIGH",
                    "feature": "battery_voltage_v",
                    "value": max_on,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_ON_WARNING_HIGH", "feature": "battery_voltage_v", "value": max_on}
            )

    # Fallback when rpm is unavailable in payload.
    if not has_rpm and not rules:
        min_v = min(voltage_all)
        if min_v < 11.8:
            has_critical = True
            rules.append(
                {
                    "id": "VOLTAGE_LOW_FALLBACK",
                    "feature": "battery_voltage_v",
                    "value": min_v,
                    "triggered": True,
                }
            )
            events.append(
                {"type": "VOLTAGE_LOW_FALLBACK", "feature": "battery_voltage_v", "value": min_v}
            )

    score = 1.0 if has_critical else 0.0
    is_anomaly = has_critical
    level = "CRITICAL" if has_critical else ("WARNING" if has_warning else "NORMAL")

    return CommonEnvelope(
        domain=domain,
        status=EnvelopeStatus.PROCESSED,
        method=EnvelopeMethod.rule,
        score=score,
        threshold=1.0,
        is_anomaly=is_anomaly,
        details={"rules": rules, "events": events, "voltage_level": level},
    )
