"""Legacy report snapshot construction."""

from __future__ import annotations

from typing import Optional

from data_trust_audit import utc_now_iso
from data_trust_constants import DATA_SNAPSHOT_SCHEMA_VERSION
from data_trust_scoring import unknown_data_trust
from data_trust_snapshot import apply_snapshot_size_governance, sanitize_for_snapshot


def build_legacy_report_snapshot(
    *,
    ticker: str,
    company_name: str = "",
    pipeline: str = "v1",
    generated_at: Optional[str] = None,
    recommendation: Optional[dict] = None,
) -> dict:
    trust = unknown_data_trust()
    return apply_snapshot_size_governance({
        "snapshot_schema_version": DATA_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_truncated": False,
        "snapshot_size_bytes": 0,
        "snapshot_omitted_sections": [],
        "snapshot_migrated_from_legacy": True,
        "ticker": ticker,
        "company_name": company_name or ticker,
        "pipeline": pipeline,
        "generated_at": generated_at or utc_now_iso(),
        "data_schema_version": None,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": trust,
        "data_source_notes": ["此資料快照由舊報告遷移產生，未包含原始分析資料。"],
        "legacy_report_metadata": sanitize_for_snapshot({
            "recommendation": recommendation or {},
        }),
        "rerun_context": {"analyses": {}, "structured_outputs": {}, "parsed": {}},
        "data": {
            "ticker": ticker,
            "company_name": company_name or ticker,
            "source_audit": [],
            "data_trust": trust,
            "data_source_notes": ["此資料快照由舊報告遷移產生，未包含原始分析資料。"],
        },
    })
