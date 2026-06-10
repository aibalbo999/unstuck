"""Key data evidence tables for rendered reports."""

from __future__ import annotations

from html import escape

from data_trust import audit_status_label, source_label


KEY_EVIDENCE_DEFINITIONS = (
    ("股價與市值", "market_data", ("current_price", "market_cap_raw", "market_cap_fmt")),
    ("年度財報", "financial_statements", ("years", "revenue_history", "net_income_history", "fcf_history")),
    ("月營收", "monthly_revenue", ("recent_monthly_revenue",)),
    ("法人籌碼", "institutional_trading", ("institutional_trading",)),
    ("同業指標", "dynamic_peer_metrics", ("dynamic_peer_metrics",)),
    ("P/E 河流圖", "pe_river_chart", ("pe_river_chart",)),
    ("近期催化劑", "recent_catalysts", ("recent_catalysts",)),
)


def _audit_entries_by_source(data: dict) -> dict[str, list[dict]]:
    entries = data.get("source_audit") if isinstance(data, dict) else []
    grouped: dict[str, list[dict]] = {}
    if not isinstance(entries, list):
        return grouped
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("source"):
            continue
        grouped.setdefault(str(entry.get("source")), []).append(entry)
    return grouped


def _has_evidence_value(data: dict, keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = data.get(key)
        if value in (None, "", [], {}):
            continue
        return True
    return False


def _record_count(entry: dict) -> int:
    try:
        return max(0, int(entry.get("record_count") or 0))
    except (TypeError, ValueError):
        return 0


def _source_evidence_entry(data: dict, source: str, keys: tuple[str, ...]) -> dict:
    entries = _audit_entries_by_source(data).get(source, [])
    if not entries:
        return {}
    successful = [
        entry for entry in entries
        if str(entry.get("status") or "") in {"success", "skipped_fresh_cache"}
        and _record_count(entry) > 0
    ]
    if _has_evidence_value(data, keys) and successful:
        providers = []
        for entry in successful:
            provider = str(entry.get("provider") or "").strip()
            if provider and provider not in providers:
                providers.append(provider)
        fetched_at = next((entry.get("fetched_at") for entry in reversed(successful) if entry.get("fetched_at")), None)
        return {
            "provider": " + ".join(providers) if providers else "未記錄",
            "status": "success",
            "fetched_at": fetched_at or "N/A",
            "record_count": sum(_record_count(entry) for entry in successful),
            "stale": all(bool(entry.get("stale")) for entry in successful),
        }
    return entries[-1]


def build_key_evidence_rows(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    rows = []
    for label, source, keys in KEY_EVIDENCE_DEFINITIONS:
        if not _has_evidence_value(data, keys):
            continue
        entry = _source_evidence_entry(data, source, keys)
        rows.append({
            "label": label,
            "source_label": source_label(source),
            "provider": entry.get("provider") or "未記錄",
            "status": entry.get("status") or "unknown",
            "status_label": audit_status_label(entry.get("status") or "unknown"),
            "fetched_at": entry.get("fetched_at") or "N/A",
            "record_count": entry.get("record_count", "N/A"),
            "stale": bool(entry.get("stale")),
        })
    return rows


def build_key_evidence_html(data: dict) -> str:
    rows = build_key_evidence_rows(data)
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{escape(row['label'])}</td>"
        f"<td>{escape(row['source_label'])}</td>"
        f"<td>{escape(str(row['provider']))}</td>"
        f"<td><span class=\"audit-status audit-status-{escape(str(row['status']))}\">{escape(str(row['status_label']))}</span></td>"
        f"<td>{escape(str(row['fetched_at']))}</td>"
        f"<td>{escape(str(row['record_count']))}</td>"
        f"<td>{'是' if row['stale'] else '否'}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
        <div class="source-audit-block">
            <h4>關鍵數據來源對照</h4>
            <div class="source-audit-scroll">
                <table class="source-audit-table">
                    <thead>
                        <tr>
                            <th>數據</th><th>來源</th><th>Provider</th><th>狀態</th>
                            <th>抓取時間</th><th>筆數</th><th>過期</th>
                        </tr>
                    </thead>
                    <tbody>{body}</tbody>
                </table>
            </div>
        </div>
    """


def build_key_evidence_markdown(data: dict) -> list[str]:
    rows = build_key_evidence_rows(data)
    if not rows:
        return []
    lines = [
        "## 關鍵數據來源對照",
        "",
        "| 數據 | 來源 | Provider | 狀態 | 抓取時間 | 筆數 | 過期 |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['label']} | "
            f"{row['source_label']} | "
            f"{row['provider']} | "
            f"{row['status_label']} | "
            f"{row['fetched_at']} | "
            f"{row['record_count']} | "
            f"{'是' if row['stale'] else '否'} |"
        )
    lines.append("")
    return lines
