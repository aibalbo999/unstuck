"""Compatibility facade for source audit, data trust, and snapshots."""

from __future__ import annotations

from data_trust_audit import (
    append_source_audit,
    audit_status_label,
    build_source_audit_entry,
    data_snapshot_filename_for_report,
    has_value as _has_value,
    iso_from_epoch,
    list_count as _list_count,
    source_label,
    source_record_count,
    string_list as _string_list,
    utc_now_iso,
)
from data_trust_constants import (
    AUDIT_STATUSES,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_DEGRADED_ENRICHMENT,
    AUDIT_STATUS_LABELS,
    AUDIT_STATUS_NOT_CONFIGURED,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    CORE_DATA_SOURCES,
    CRITICAL_TRUST_SOURCES,
    DATA_SNAPSHOT_SCHEMA_VERSION,
    SNAPSHOT_CORE_DATA_KEYS,
    SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS,
    SNAPSHOT_TRIMMABLE_LIST_FIELDS,
    SOURCE_AUDIT_SOURCES,
    SOURCE_LABELS,
    SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS,
    TRUST_STATUSES,
    TRUST_STATUS_ERROR,
    TRUST_STATUS_FRESH,
    TRUST_STATUS_LABELS,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_STALE,
    TRUST_STATUS_UNKNOWN,
)
from data_trust_scoring import (
    build_data_trust,
    finalize_data_trust,
    has_usable_critical_data as _has_usable_critical_data,
    last_market_data_at as _last_market_data_at,
    latest_audit_by_source as _latest_audit_by_source,
    normalize_data_trust,
    stale_sources_from as _stale_sources,
    trust_status_label,
    unknown_data_trust,
)
from data_trust_legacy_snapshot import build_legacy_report_snapshot
from data_trust_snapshot import (
    apply_snapshot_size_governance,
    build_data_snapshot,
    read_data_trust_from_snapshot,
    sanitize_for_snapshot,
    sanitize_rerun_context as _sanitize_rerun_context,
    set_stable_snapshot_size as _set_stable_snapshot_size,
    snapshot_content_hash,
    snapshot_size_bytes,
    snapshot_text as _snapshot_text,
    validate_data_snapshot,
    verify_data_snapshot_integrity,
    write_data_snapshot,
)

__all__ = [
    name
    for name in globals()
    if not name.startswith("__") and name not in {"annotations"}
]
