"""Select tracking publications before evaluating current report quality.

No response cache: every lookup rereads metadata and selected snapshots. Older
versions still determine eligibility, but never incur discarded quality work.
"""
from __future__ import annotations

from report_index import query_report_metadata
from report_index_rows import _read_snapshot, row_to_report
from report_pipeline_identity import resolve_report_pipeline_id
from report_publication_identity import publication_identity
from reporting.text_tokens import first_non_missing_text


def select_latest_reports(ticker, output_dir, *, sync_metadata, pipeline_order, ticker_matches):
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return []
    rows = []
    page = 1
    while True:
        batch, total = query_report_metadata(
            page=page, limit=100, q=ticker.split(".", 1)[0], pipeline="all",
            recommendation="all", data_trust="all", include_versions=True,
            output_dir=output_dir, sync_metadata=sync_metadata if page == 1 else False,
            row_mapper=dict,
        )
        rows.extend(row for row in batch if ticker_matches(row, ticker))
        if not batch or page * 100 >= total:
            break
        page += 1
    latest = {}
    # Stable sorting preserves the index's tie order, including across pages.
    for row in sorted(rows, key=lambda row: -float(row.get("timestamp") or 0)):
        stored = first_non_missing_text(row.get("pipeline_id"))
        if stored:
            mode = resolve_report_pipeline_id(row["filename"], stored_pipeline=stored)
            if mode in latest:
                continue
        snapshot = _read_snapshot(row)
        mode = resolve_report_pipeline_id(row["filename"], stored_pipeline=row.get("pipeline_id"), snapshot=snapshot)
        if mode in latest or not publication_identity(snapshot)["prediction_eligible"]:
            continue
        # A blocked latest forecast stays blocked; do not substitute older good
        # evidence. All current projections run through the canonical mapper.
        latest[mode] = row_to_report(row, snapshot=snapshot)
    return sorted(latest.values(), key=lambda report: pipeline_order.get(report.get("pipeline_id"), 99))
