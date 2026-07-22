"""Provider SLA policy integration for data trust scoring."""

from __future__ import annotations

from config import (
    PROVIDER_SLA_DEGRADE_LEVELS,
)
from data_trust_constants import (
    CORE_DATA_SOURCES,
    TRUST_STATUS_ERROR,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_UNKNOWN,
)
# Preserve the previous public helper surface while moving alert matching out.
from data_trust_sla_alerts import (
    current_fetch_is_healthy,
    current_provider_entries,
    current_provider_pairs,
    current_source_health,
    matched_provider_sla_alerts,
    safe_text,
    safe_text_list,
)


SLA_DEGRADE_LEVELS = {str(item).strip().lower() for item in PROVIDER_SLA_DEGRADE_LEVELS}
CORE_PROVIDER_SLA_SOURCES = set(CORE_DATA_SOURCES)


def apply_provider_sla_to_trust(data: dict, trust: dict, alerts: list[dict] | None = None) -> dict:
    matched = matched_provider_sla_alerts(data, alerts=alerts)
    if not matched:
        return trust

    trust = dict(trust)
    trust["provider_sla_alerts"] = matched
    reason_codes = safe_text_list(trust.get("reason_codes"))
    notes = safe_text_list(trust.get("notes"))
    degrading_alerts = [
        item for item in matched
        if item.get("alert_level") in SLA_DEGRADE_LEVELS and _is_core_sla_source(item.get("source"))
    ]
    optional_degrading_alerts = [
        item for item in matched
        if item.get("alert_level") in SLA_DEGRADE_LEVELS and not _is_core_sla_source(item.get("source"))
    ]
    core_health_notice_alerts = [
        item for item in matched
        if item.get("alert_level") in SLA_DEGRADE_LEVELS
        and _is_core_sla_source(item.get("source"))
        and current_fetch_is_healthy(item)
    ]
    degrading_alerts = [item for item in degrading_alerts if not current_fetch_is_healthy(item)]
    warning_alerts = [item for item in matched if item.get("alert_level") not in SLA_DEGRADE_LEVELS]
    if degrading_alerts:
        notes.append(f"來源健康度警示：{_alert_summary(degrading_alerts)}；critical provider SLA 已調降資料可信度。")
        reason_codes.append("provider_sla_critical")
    if core_health_notice_alerts:
        notes.append(f"核心來源健康度警示：{_alert_summary(core_health_notice_alerts)}；本次資料抓取成功，未調降本報告核心資料可信度。")
        reason_codes.append("provider_sla_core_health_notice")
    if optional_degrading_alerts:
        notes.append(f"補充來源健康度警示：{_alert_summary(optional_degrading_alerts)}；未調降核心資料可信度。")
        reason_codes.append("provider_sla_optional_critical")
    if warning_alerts and not degrading_alerts and not optional_degrading_alerts:
        notes.append(f"來源健康度觀察：{_alert_summary(warning_alerts)}；warning 僅列入提醒，未單獨調降可信度。")
        reason_codes.append("provider_sla_warning_note")
    trust["notes"] = notes
    trust["reason_codes"] = sorted(set(code for code in reason_codes if code))
    trust["status"] = _downgraded_status(safe_text(trust.get("status")).strip() or TRUST_STATUS_UNKNOWN, degrading_alerts)
    return trust


def _alert_summary(alerts: list[dict]) -> str:
    return "；".join(
        f"{item['source']}/{item['provider']}={item['alert_level']}({item.get('evidence_attempts', 0)}次)"
        for item in alerts[:3]
    )


def _downgraded_status(status: str, degrading_alerts: list[dict]) -> str:
    if status in {TRUST_STATUS_ERROR, TRUST_STATUS_UNKNOWN}:
        return status
    if degrading_alerts:
        return TRUST_STATUS_PARTIAL
    return status


def _is_core_sla_source(source: object) -> bool:
    return safe_text(source).strip() in CORE_PROVIDER_SLA_SOURCES
