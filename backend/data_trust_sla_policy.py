"""Provider SLA policy integration for data trust scoring."""

from __future__ import annotations

from contextlib import suppress

from data_trust_constants import TRUST_STATUS_ERROR, TRUST_STATUS_FRESH, TRUST_STATUS_PARTIAL, TRUST_STATUS_STALE, TRUST_STATUS_UNKNOWN


def current_provider_pairs(data: dict) -> set[tuple[str, str]]:
    entries = data.get("source_audit") if isinstance(data.get("source_audit"), list) else []
    pairs = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "").strip()
        provider = str(entry.get("provider") or "").strip().lower()
        if source and provider:
            pairs.add((source, provider))
    return pairs


def matched_provider_sla_alerts(data: dict, alerts: list[dict] | None = None) -> list[dict]:
    pairs = current_provider_pairs(data)
    if not pairs:
        return []
    if alerts is None:
        with suppress(Exception):
            from provider_sla import get_provider_sla_alerts

            alerts = get_provider_sla_alerts(limit=100)
    matched = []
    for alert in alerts or []:
        if not isinstance(alert, dict):
            continue
        source = str(alert.get("source") or "").strip()
        provider = str(alert.get("provider") or "").strip().lower()
        level = str(alert.get("alert_level") or "").strip().lower()
        if level not in {"warning", "critical"}:
            continue
        if (source, provider) in pairs:
            matched.append(_compact_alert(alert))
    return matched


def apply_provider_sla_to_trust(data: dict, trust: dict, alerts: list[dict] | None = None) -> dict:
    matched = matched_provider_sla_alerts(data, alerts=alerts)
    if not matched:
        return trust

    trust = dict(trust)
    trust["provider_sla_alerts"] = matched
    notes = list(trust.get("notes") or [])
    alert_summary = "；".join(
        f"{item['source']}/{item['provider']}={item['alert_level']}"
        for item in matched[:3]
    )
    notes.append(f"來源健康度警示：{alert_summary}；已依近期 provider 成功率調降資料可信度。")
    trust["notes"] = notes
    trust["status"] = _downgraded_status(str(trust.get("status") or TRUST_STATUS_UNKNOWN), matched)
    return trust


def _downgraded_status(status: str, alerts: list[dict]) -> str:
    if status in {TRUST_STATUS_ERROR, TRUST_STATUS_UNKNOWN}:
        return status
    if any(item.get("alert_level") == "critical" for item in alerts):
        return TRUST_STATUS_PARTIAL
    if status == TRUST_STATUS_FRESH:
        return TRUST_STATUS_PARTIAL
    if status == TRUST_STATUS_STALE:
        return TRUST_STATUS_PARTIAL
    return status


def _compact_alert(alert: dict) -> dict:
    return {
        "source": str(alert.get("source") or "unknown"),
        "provider": str(alert.get("provider") or "unknown"),
        "alert_level": str(alert.get("alert_level") or "warning"),
        "alert_message": str(alert.get("alert_message") or "")[:180],
        "success_rate": alert.get("success_rate"),
        "last_status": alert.get("last_status"),
        "alert_basis": alert.get("alert_basis"),
    }
