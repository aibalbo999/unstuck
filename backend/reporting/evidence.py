"""Key data evidence tables for rendered reports."""

from __future__ import annotations

from html import escape

from data_trust import audit_status_label, source_label
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_sequence_items, safe_text


KEY_EVIDENCE_DEFINITIONS = (
    ("股價與市值", "market_data", ("current_price", "market_cap_raw", "market_cap_fmt")),
    ("年度財報", "financial_statements", ("years", "revenue_history", "net_income_history", "fcf_history")),
    ("月營收", "monthly_revenue", ("recent_monthly_revenue",)),
    ("法人籌碼", "institutional_trading", ("institutional_trading",)),
    ("同業指標", "dynamic_peer_metrics", ("dynamic_peer_metrics",)),
    ("P/E 河流圖", "pe_river_chart", ("pe_river_chart",)),
    ("近期催化劑", "recent_catalysts", ("recent_catalysts",)),
    ("全球市場脈絡", "global_market_context", ("global_market_context",)),
    ("國際新聞脈絡", "international_news_context", ("international_news_context",)),
)


def _audit_entries_by_source(data: dict) -> dict[str, list[dict]]:
    data = safe_mapping_dict(data) or {}
    entries = safe_dict_list(data.get("source_audit"))
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        source = safe_text(entry.get("source")).strip()
        if not source:
            continue
        grouped.setdefault(source, []).append(entry)
    return grouped


def _has_evidence_value(data: dict, keys: tuple[str, ...]) -> bool:
    data = safe_mapping_dict(data) or {}
    for key in keys:
        if _has_usable_evidence_value(data.get(key)):
            return True
    return False


def _has_usable_evidence_value(value) -> bool:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)):
        return False
    if isinstance(value, str):
        return bool(safe_text(value).strip())
    if isinstance(value, (list, tuple)):
        return any(_has_usable_evidence_value(item) for item in safe_sequence_items(value))
    value_map = safe_mapping_dict(value)
    if value_map is not None:
        return any(_has_usable_evidence_value(child) for child in value_map.values())
    return bool(safe_text(value).strip())


def _record_count(entry: dict) -> int:
    return max(0, safe_int(entry.get("record_count")))


def _safe_bool_flag(value) -> bool:
    return value if isinstance(value, bool) else False


def _source_evidence_entry(data: dict, source: str, keys: tuple[str, ...]) -> dict:
    data = safe_mapping_dict(data) or {}
    entries = _audit_entries_by_source(data).get(source, [])
    if not entries:
        return {}
    successful = [
        entry for entry in entries
        if safe_text(entry.get("status")).strip() in {"success", "skipped_fresh_cache"}
        and _record_count(entry) > 0
    ]
    if _has_evidence_value(data, keys) and successful:
        providers = []
        for entry in successful:
            provider = safe_text(entry.get("provider")).strip()
            if provider and provider not in providers:
                providers.append(provider)
        fetched_at = next(
            (
                text
                for entry in reversed(successful)
                if (text := safe_text(entry.get("fetched_at")).strip())
            ),
            None,
        )
        return {
            "provider": " + ".join(providers) if providers else "未記錄",
            "status": "success",
            "fetched_at": fetched_at or "N/A",
            "record_count": sum(_record_count(entry) for entry in successful),
            "stale": all(_safe_bool_flag(entry.get("stale")) for entry in successful),
        }
    return entries[-1]


def build_key_evidence_rows(data: dict) -> list[dict]:
    data = safe_mapping_dict(data)
    if data is None:
        return []
    rows = []
    for label, source, keys in KEY_EVIDENCE_DEFINITIONS:
        if not _has_evidence_value(data, keys):
            continue
        entry = _source_evidence_entry(data, source, keys)
        status = safe_text(entry.get("status")).strip() or "unknown"
        rows.append({
            "label": label,
            "source_label": source_label(source),
            "provider": safe_text(entry.get("provider")).strip() or "未記錄",
            "status": status,
            "status_label": audit_status_label(status),
            "fetched_at": safe_text(entry.get("fetched_at")).strip() or "N/A",
            "record_count": _record_count(entry),
            "stale": _safe_bool_flag(entry.get("stale")),
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


def _markdown_cell(value) -> str:
    text = safe_text(value).strip() or "N/A"
    return text.replace("|", "/").replace("\n", " ")


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
            f"{_markdown_cell(row['label'])} | "
            f"{_markdown_cell(row['source_label'])} | "
            f"{_markdown_cell(row['provider'])} | "
            f"{_markdown_cell(row['status_label'])} | "
            f"{_markdown_cell(row['fetched_at'])} | "
            f"{_markdown_cell(row['record_count'])} | "
            f"{'是' if row['stale'] else '否'} |"
        )
    lines.append("")
    return lines
