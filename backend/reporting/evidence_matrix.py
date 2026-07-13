"""Conclusion-level evidence matrix for rendered reports and snapshots."""

from __future__ import annotations

from html import escape
from math import isfinite
from typing import Any

from data_trust_audit import audit_status_label, source_label
from data_trust_scoring import normalize_data_trust, trust_status_label
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list

from .evidence import build_key_evidence_rows
from .html_sanitizer import sanitize_report_plain_text


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _as_notes(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return safe_text_list(value)
    if text := _text(value, "").strip():
        return [text]
    return []


def _text(value: Any, default: str = "N/A") -> str:
    text = sanitize_report_plain_text(safe_text(value)).strip()
    return text or default


def _has_message_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(_text(value, "").strip())
    if isinstance(value, (bytes, bytearray, memoryview, list, tuple, dict, set, frozenset)):
        try:
            return len(value) > 0
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return True


def _safe_bool_flag(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def _source_message_text(message: Any, error_kind: Any = None, source: Any = None) -> str:
    message_text = _source_message_candidate(message)
    if message_text:
        return message_text
    error_text = _source_message_candidate(error_kind)
    if error_text:
        return error_text
    if _has_message_value(message) or _has_message_value(error_kind):
        return "N/A"
    source_text = _source_message_candidate(source)
    return source_text or "N/A"


def _source_message_candidate(value: Any) -> str:
    if not _has_message_value(value):
        return ""
    return _text(value, "").strip()


def _format_price(value: Any) -> str:
    if isinstance(value, bool):
        return "N/A"
    if isinstance(value, (int, float)):
        if not isfinite(value):
            return "N/A"
        return f"NT${value:,.0f}"
    return _text(value)


def _unique(values: list[str]) -> list[str]:
    seen = []
    for value in values:
        item = _text(value, "").strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def _latest_fetched_at(rows: list[dict]) -> str:
    values = []
    for row in rows:
        row_map = _as_dict(row)
        fetched_at = _text(row_map.get("fetched_at"), "").strip()
        if fetched_at and fetched_at != "N/A":
            values.append(fetched_at)
    values = sorted(values)
    return values[-1] if values else "N/A"


def _combined_status(rows: list[dict], trust_status: str) -> str:
    statuses = [
        _text(_as_dict(row).get("status"), "unknown")
        for row in rows
    ]
    if any(status == "error" for status in statuses) or trust_status == "error":
        return "error"
    if not statuses:
        return "unknown"
    if all(status in {"success", "skipped_fresh_cache"} for status in statuses):
        return "success"
    if any(status in {"success", "skipped_fresh_cache"} for status in statuses):
        return "degraded_enrichment"
    return statuses[-1] if statuses else "unknown"


def _data_limitations(data: dict, trust: dict, rows: list[dict]) -> str:
    notes = _as_notes(data.get("data_source_notes"))
    trust_status = str(trust.get("status") or "unknown")
    if trust_status != "fresh":
        notes.append(f"資料可信度：{trust_status_label(trust_status)}。")
    stale_source_values = []
    for row in rows:
        row_map = _as_dict(row)
        if _safe_bool_flag(row_map.get("stale")):
            stale_source_values.append(row_map.get("source_label"))
    stale_sources = _unique(stale_source_values)
    if stale_sources:
        notes.append("過期來源：" + "、".join(stale_sources) + "。")
    critical = _unique([source_label(source) for source in trust.get("critical_failures", []) or []])
    if critical:
        notes.append("核心異常：" + "、".join(critical) + "。")
    return "；".join(notes) if notes else "未記錄額外資料限制。"


def _source_rows_by_label(data: dict) -> dict[str, dict]:
    rows_by_label = {}
    for row in build_key_evidence_rows(data):
        row_map = _as_dict(row)
        label = _text(row_map.get("label"), "").strip()
        if label:
            rows_by_label[label] = row_map
    return rows_by_label


def _row(
    *,
    claim: str,
    basis: str,
    source_labels: list[str],
    evidence_rows: list[dict],
    data: dict,
    trust: dict,
) -> dict:
    trust_status = str(trust.get("status") or "unknown")
    status = _combined_status(evidence_rows, trust_status)
    evidence_row_maps = [_as_dict(row) for row in evidence_rows]
    providers = _unique([row.get("provider") for row in evidence_row_maps])
    sources = _unique([row.get("source_label") for row in evidence_row_maps] + source_labels)
    return {
        "claim": claim,
        "basis": basis,
        "source": " + ".join(sources) if sources else "未記錄",
        "provider": " + ".join(providers) if providers else "未記錄",
        "status": status,
        "status_label": audit_status_label(status),
        "fetched_at": _latest_fetched_at(evidence_rows),
        "limitation": _data_limitations(data, trust, evidence_rows),
    }


def _price_target_basis(price_targets: dict) -> str:
    if not price_targets:
        return ""
    parts = []
    for scenario, price in price_targets.items():
        scenario_text = _text(scenario, "")
        if not scenario_text:
            continue
        parts.append(f"{scenario_text}: {_format_price(price)}")
    return "；".join(parts)


def _moat_basis(moat_scores: dict) -> str:
    if not moat_scores:
        return ""
    overall = moat_scores.get("整體護城河")
    parts = []
    if overall is not None:
        parts.append(f"整體護城河: {_text(overall)}/10")
    for metric, score in moat_scores.items():
        metric_text = _text(metric, "")
        if not metric_text or metric_text == "整體護城河":
            continue
        parts.append(f"{metric_text}: {_text(score)}/10")
    return "；".join(parts)


def _basis_value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _text(value, "").strip()
    if isinstance(value, (list, tuple, dict, set, frozenset)):
        try:
            if len(value) == 0:
                return ""
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return ""
    return _text(value, "").strip()


def _recommendation_basis(recommendation: dict) -> str:
    if not recommendation:
        return ""
    fields = []
    for label in ("建議", "3個月", "6個月", "12個月", "信心"):
        value = next((item for key, item in recommendation.items() if label in safe_text(key)), None)
        value_text = _basis_value_text(value)
        if value_text:
            fields.append(f"{label}: {value_text}")
    return "；".join(fields)


def build_evidence_matrix_rows(context: dict) -> list[dict]:
    """Build conclusion-to-evidence rows shared by HTML, Markdown, and snapshots."""
    context = _as_dict(context)
    data = _as_dict(context.get("data"))
    parsed = _as_dict(context.get("parsed"))
    trust = normalize_data_trust(data.get("data_trust"))
    evidence_by_label = _source_rows_by_label(data)

    rows: list[dict] = []
    price_targets = _as_dict(parsed.get("price_targets"))
    price_basis = _price_target_basis(price_targets)
    if price_basis:
        rows.append(_row(
            claim="估值結論",
            basis=price_basis,
            source_labels=[source_label("market_data"), source_label("financial_statements"), source_label("pe_river_chart")],
            evidence_rows=[
                row for row in (
                    evidence_by_label.get("股價與市值"),
                    evidence_by_label.get("年度財報"),
                    evidence_by_label.get("P/E 河流圖"),
                )
                if row
            ],
            data=data,
            trust=trust,
        ))

    moat_scores = _as_dict(parsed.get("moat_scores"))
    moat_basis = _moat_basis(moat_scores)
    if moat_basis:
        rows.append(_row(
            claim="護城河評分",
            basis=moat_basis,
            source_labels=[source_label("dynamic_peer_metrics"), source_label("financial_statements")],
            evidence_rows=[
                row for row in (
                    evidence_by_label.get("同業指標"),
                    evidence_by_label.get("年度財報"),
                )
                if row
            ],
            data=data,
            trust=trust,
        ))

    recommendation = _as_dict(parsed.get("recommendation"))
    recommendation_basis = _recommendation_basis(recommendation)
    if recommendation_basis:
        rows.append(_row(
            claim="最終投資建議",
            basis=recommendation_basis,
            source_labels=[
                source_label("market_data"),
                source_label("financial_statements"),
                source_label("recent_catalysts"),
                source_label("global_market_context"),
                source_label("international_news_context"),
            ],
            evidence_rows=[
                row for row in (
                    evidence_by_label.get("股價與市值"),
                    evidence_by_label.get("年度財報"),
                    evidence_by_label.get("近期催化劑"),
                    evidence_by_label.get("全球市場脈絡"),
                    evidence_by_label.get("國際新聞脈絡"),
                )
                if row
            ],
            data=data,
            trust=trust,
        ))

    return rows


def _source_id(value: Any) -> str:
    text = _text(value, "").strip()
    return "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-", ".", ":"})[:96]


def build_evidence_matrix_payload(context: dict) -> dict:
    """Build JSON data used by click-to-source report tooltips."""
    context = _as_dict(context)
    data = _as_dict(context.get("data"))
    sources: dict[str, dict] = {}

    entries = safe_dict_list(data.get("source_audit"))
    for entry in entries:
        source_text = _text(entry.get("source"), "")
        source_id = _source_id(source_text or _text(entry.get("provider"), ""))
        if not source_id:
            continue
        provider = _text(entry.get("provider"))
        status = _text(entry.get("status"), "unknown")
        fetched_at = _text(entry.get("fetched_at"))
        message = _source_message_text(entry.get("message"), entry.get("error_kind"), entry.get("source"))
        sources[source_id] = {
            "source_id": source_id,
            "source": source_label(source_text or source_id),
            "source_document": provider,
            "status": status,
            "status_label": audit_status_label(status),
            "fetched_at": fetched_at,
            "text": message,
        }

    rows = build_evidence_matrix_rows(context)
    for index, row in enumerate(rows, start=1):
        source_id = f"evidence:{index}"
        sources[source_id] = {
            "source_id": source_id,
            "source": _text(row.get("source")),
            "source_document": _text(row.get("provider")),
            "status": _text(row.get("status"), "unknown"),
            "status_label": _text(row.get("status_label")),
            "fetched_at": _text(row.get("fetched_at")),
            "text": _text(row.get("basis")),
            "limitation": _text(row.get("limitation")),
        }

    return {"sources": sources, "rows": rows}


def build_evidence_matrix_html(context: dict) -> str:
    rows = build_evidence_matrix_rows(context)
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{_html_cell(row['claim'])}</td>"
        f"<td>{_html_cell(row['basis'])}</td>"
        f"<td>{_html_cell(row['source'])}</td>"
        f"<td>{_html_cell(row['provider'])}</td>"
        f"<td><span class=\"audit-status audit-status-{_html_cell(row['status'])}\">{_html_cell(row['status_label'])}</span></td>"
        f"<td>{_html_cell(row['fetched_at'])}</td>"
        f"<td>{_html_cell(row['limitation'])}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
        <div class="source-audit-block">
            <h4>報告證據矩陣</h4>
            <div class="source-audit-scroll">
                <table class="source-audit-table">
                    <thead>
                        <tr>
                            <th>結論</th><th>報告依據</th><th>資料來源</th><th>Provider</th>
                            <th>狀態</th><th>抓取時間</th><th>資料限制</th>
                        </tr>
                    </thead>
                    <tbody>{body}</tbody>
                </table>
            </div>
        </div>
    """


def _html_cell(value: Any) -> str:
    return escape(_text(value))


def _markdown_cell(value: Any) -> str:
    return _text(value).replace("|", "/").replace("\n", " ")


def build_evidence_matrix_markdown(context: dict) -> list[str]:
    rows = build_evidence_matrix_rows(context)
    if not rows:
        return []
    lines = [
        "## 報告證據矩陣",
        "",
        "| 結論 | 報告依據 | 資料來源 | Provider | 狀態 | 抓取時間 | 資料限制 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{_markdown_cell(row['claim'])} | "
            f"{_markdown_cell(row['basis'])} | "
            f"{_markdown_cell(row['source'])} | "
            f"{_markdown_cell(row['provider'])} | "
            f"{_markdown_cell(row['status_label'])} | "
            f"{_markdown_cell(row['fetched_at'])} | "
            f"{_markdown_cell(row['limitation'])} |"
        )
    lines.append("")
    return lines
