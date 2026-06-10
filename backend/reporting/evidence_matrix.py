"""Conclusion-level evidence matrix for rendered reports and snapshots."""

from __future__ import annotations

from html import escape
from typing import Any

from data_trust_audit import audit_status_label, source_label
from data_trust_scoring import normalize_data_trust, trust_status_label

from .evidence import build_key_evidence_rows
from .html_sanitizer import sanitize_report_plain_text


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_notes(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _text(value: Any, default: str = "N/A") -> str:
    text = sanitize_report_plain_text(value).strip() if value is not None else ""
    return text or default


def _format_price(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"NT${value:,.0f}"
    return _text(value)


def _unique(values: list[str]) -> list[str]:
    seen = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def _latest_fetched_at(rows: list[dict]) -> str:
    values = sorted(str(row.get("fetched_at") or "") for row in rows if row.get("fetched_at") and row.get("fetched_at") != "N/A")
    return values[-1] if values else "N/A"


def _combined_status(rows: list[dict], trust_status: str) -> str:
    statuses = [str(row.get("status") or "unknown") for row in rows]
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
    stale_sources = _unique([str(row.get("source_label") or "") for row in rows if row.get("stale")])
    if stale_sources:
        notes.append("過期來源：" + "、".join(stale_sources) + "。")
    critical = _unique([source_label(source) for source in trust.get("critical_failures", []) or []])
    if critical:
        notes.append("核心異常：" + "、".join(critical) + "。")
    return "；".join(notes) if notes else "未記錄額外資料限制。"


def _source_rows_by_label(data: dict) -> dict[str, dict]:
    return {row["label"]: row for row in build_key_evidence_rows(data)}


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
    providers = _unique([str(row.get("provider") or "") for row in evidence_rows])
    sources = _unique([str(row.get("source_label") or "") for row in evidence_rows] + source_labels)
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
    return "；".join(f"{_text(scenario)}: {_format_price(price)}" for scenario, price in price_targets.items())


def _moat_basis(moat_scores: dict) -> str:
    if not moat_scores:
        return ""
    overall = moat_scores.get("整體護城河")
    parts = []
    if overall is not None:
        parts.append(f"整體護城河: {_text(overall)}/10")
    parts.extend(
        f"{_text(metric)}: {_text(score)}/10"
        for metric, score in moat_scores.items()
        if metric != "整體護城河"
    )
    return "；".join(parts)


def _recommendation_basis(recommendation: dict) -> str:
    if not recommendation:
        return ""
    fields = []
    for label in ("建議", "3個月", "6個月", "12個月", "信心"):
        value = next((item for key, item in recommendation.items() if label in str(key)), None)
        if value not in (None, "", [], {}):
            fields.append(f"{label}: {_text(value)}")
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
            source_labels=[source_label("market_data"), source_label("financial_statements")],
            evidence_rows=[
                row for row in (
                    evidence_by_label.get("股價與市值"),
                    evidence_by_label.get("年度財報"),
                    evidence_by_label.get("近期催化劑"),
                )
                if row
            ],
            data=data,
            trust=trust,
        ))

    return rows


def build_evidence_matrix_html(context: dict) -> str:
    rows = build_evidence_matrix_rows(context)
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{escape(row['claim'])}</td>"
        f"<td>{escape(str(row['basis']))}</td>"
        f"<td>{escape(str(row['source']))}</td>"
        f"<td>{escape(str(row['provider']))}</td>"
        f"<td><span class=\"audit-status audit-status-{escape(str(row['status']))}\">{escape(str(row['status_label']))}</span></td>"
        f"<td>{escape(str(row['fetched_at']))}</td>"
        f"<td>{escape(str(row['limitation']))}</td>"
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


def _markdown_cell(value: Any) -> str:
    return str(value or "N/A").replace("|", "/").replace("\n", " ")


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
