"""Operator-facing data trust score policy."""

from __future__ import annotations

from data_trust_constants import (
    TRUST_STATUS_ERROR,
    TRUST_STATUS_FRESH,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_STALE,
    TRUST_STATUS_UNKNOWN,
)


def score_for_trust(
    *,
    status: str,
    critical_failures: list[str],
    stale_sources: list[str],
    reason_codes: list[str],
) -> tuple[int, list[str]]:
    """Return a compact 0-100 operator-facing trust score."""
    base_scores = {
        TRUST_STATUS_FRESH: 95,
        TRUST_STATUS_PARTIAL: 72,
        TRUST_STATUS_STALE: 62,
        TRUST_STATUS_ERROR: 20,
        TRUST_STATUS_UNKNOWN: 35,
    }
    score = base_scores.get(status, 35)
    reasons: list[str] = []

    if status == TRUST_STATUS_FRESH:
        reasons.append("核心資料新鮮且未見主要來源異常。")
    elif status == TRUST_STATUS_PARTIAL:
        reasons.append("部分來源異常或使用備援資料。")
    elif status == TRUST_STATUS_STALE:
        reasons.append("部分來源超過新鮮度門檻。")
    elif status == TRUST_STATUS_ERROR:
        reasons.append("核心資料來源異常，分析可信度偏低。")
    else:
        reasons.append("缺少完整資料可信度紀錄。")

    if critical_failures:
        score -= min(30, 12 * len(critical_failures))
        reasons.append("核心來源異常：" + "、".join(critical_failures[:4]))
    if stale_sources:
        score -= min(24, 6 * len(stale_sources))
        reasons.append("過期來源：" + "、".join(stale_sources[:4]))

    reason_set = set(reason_codes or [])
    if "data_source_notes_present" in reason_set:
        score -= 4
        reasons.append("含資料口徑或備援補值註記。")
    if "provider_sla_critical" in reason_set:
        score -= 12
        reasons.append("全系統來源健康度曾達 critical。")
    if "provider_sla_warning_note" in reason_set:
        score -= 3
        reasons.append("全系統來源健康度有 warning。")
    if "missing_usable_critical_data" in reason_set:
        score -= 18
        reasons.append("缺少可用核心資料。")
    if "missing_data_trust_snapshot" in reason_set:
        score = min(score, 35)

    return max(0, min(int(round(score)), 100)), reasons[:6]
