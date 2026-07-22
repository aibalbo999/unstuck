"""Evidence-matrix row assembly for report conclusions."""

from __future__ import annotations

from typing import Any

from data_trust_audit import audit_status_label, source_label
from data_trust_scoring import normalize_data_trust
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text

from .evidence_matrix_basis import moat_basis, price_target_basis, recommendation_basis
from .evidence_matrix_limitations import (
    combined_evidence_status,
    evidence_data_limitations,
    latest_evidence_fetched_at,
    unique_evidence_texts,
)
from .html_sanitizer import sanitize_report_plain_text


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _text(value: Any, default: str = "N/A") -> str:
    text = sanitize_report_plain_text(safe_text(value)).strip()
    return text or default


def _source_rows_by_label(key_evidence_rows: list[dict]) -> dict[str, dict]:
    rows_by_label = {}
    for row in safe_sequence_items(key_evidence_rows):
        row_map = _as_dict(row)
        label = _text(row_map.get("label"), "").strip()
        if label:
            rows_by_label[label] = row_map
    return rows_by_label


def _matching_rows(rows_by_label: dict[str, dict], labels: list[str]) -> list[dict]:
    return [row for label in labels if (row := rows_by_label.get(label))]


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
    status = combined_evidence_status(evidence_rows, trust_status)
    evidence_row_maps = [_as_dict(row) for row in evidence_rows]
    providers = unique_evidence_texts([row.get("provider") for row in evidence_row_maps])
    sources = unique_evidence_texts([row.get("source_label") for row in evidence_row_maps] + source_labels)
    return {
        "claim": claim,
        "basis": basis,
        "source": " + ".join(sources) if sources else "未記錄",
        "provider": " + ".join(providers) if providers else "未記錄",
        "status": status,
        "status_label": audit_status_label(status),
        "fetched_at": latest_evidence_fetched_at(evidence_rows),
        "limitation": evidence_data_limitations(data, trust, evidence_rows),
    }


def _append_claim_row(
    rows: list[dict],
    *,
    claim: str,
    basis: str,
    source_labels: list[str],
    evidence_labels: list[str],
    evidence_by_label: dict[str, dict],
    data: dict,
    trust: dict,
) -> None:
    if not basis:
        return
    rows.append(_row(
        claim=claim,
        basis=basis,
        source_labels=source_labels,
        evidence_rows=_matching_rows(evidence_by_label, evidence_labels),
        data=data,
        trust=trust,
    ))


def build_rows_from_context(context: dict, key_evidence_rows: list[dict]) -> list[dict]:
    """Build conclusion-to-evidence rows from parsed report context and source evidence rows."""
    context = _as_dict(context)
    data = _as_dict(context.get("data"))
    parsed = _as_dict(context.get("parsed"))
    trust = normalize_data_trust(data.get("data_trust"))
    evidence_by_label = _source_rows_by_label(key_evidence_rows)

    rows: list[dict] = []
    _append_claim_row(
        rows,
        claim="估值結論",
        basis=price_target_basis(_as_dict(parsed.get("price_targets"))),
        source_labels=[source_label("market_data"), source_label("financial_statements"), source_label("pe_river_chart")],
        evidence_labels=["股價與市值", "年度財報", "P/E 河流圖"],
        evidence_by_label=evidence_by_label,
        data=data,
        trust=trust,
    )
    _append_claim_row(
        rows,
        claim="護城河評分",
        basis=moat_basis(_as_dict(parsed.get("moat_scores"))),
        source_labels=[source_label("dynamic_peer_metrics"), source_label("financial_statements")],
        evidence_labels=["同業指標", "年度財報"],
        evidence_by_label=evidence_by_label,
        data=data,
        trust=trust,
    )
    _append_claim_row(
        rows,
        claim="最終投資建議",
        basis=recommendation_basis(_as_dict(parsed.get("recommendation"))),
        source_labels=[
            source_label("market_data"),
            source_label("financial_statements"),
            source_label("recent_catalysts"),
            source_label("global_market_context"),
            source_label("international_news_context"),
        ],
        evidence_labels=["股價與市值", "年度財報", "近期催化劑", "全球市場脈絡", "國際新聞脈絡"],
        evidence_by_label=evidence_by_label,
        data=data,
        trust=trust,
    )

    return rows
