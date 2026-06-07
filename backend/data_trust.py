"""Source audit, data-trust summary, and data snapshot helpers."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DATA_SNAPSHOT_SCHEMA_VERSION = 3
SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS = {1, 2, DATA_SNAPSHOT_SCHEMA_VERSION}
SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS = 12000
SNAPSHOT_TRIMMABLE_LIST_FIELDS = (
    "recent_catalysts",
    "peer_discovery_results",
    "dynamic_peer_metrics",
)
SNAPSHOT_CORE_DATA_KEYS = {
    "data_schema_version",
    "ticker",
    "company_name",
    "raw_company_name",
    "company_identity",
    "sector",
    "industry",
    "country",
    "fetch_date",
    "current_price",
    "current_price_fmt",
    "market_cap_raw",
    "market_cap_fmt",
    "pe_ratio",
    "pe_ratio_raw",
    "forward_pe",
    "forward_pe_raw",
    "pb_ratio",
    "ps_ratio",
    "ev_ebitda",
    "shares_raw",
    "forward_eps",
    "trailing_eps",
    "revenue_ttm_raw",
    "net_income_ttm_raw",
    "free_cash_flow_raw",
    "total_debt_raw",
    "total_cash_raw",
    "years",
    "revenue_history",
    "net_income_history",
    "gross_profit_history",
    "operating_income_history",
    "fcf_history",
    "gross_margin_history",
    "op_margin_history",
    "net_margin_history",
    "roe_history",
    "total_equity_history",
    "total_assets_history",
    "recent_monthly_revenue",
    "institutional_trading",
    "pe_river_chart",
    "data_source_notes",
    "data_freshness",
    "source_freshness",
    "source_audit",
    "data_trust",
}

AUDIT_STATUS_SUCCESS = "success"
AUDIT_STATUS_ERROR = "error"
AUDIT_STATUS_SKIPPED_FRESH_CACHE = "skipped_fresh_cache"
AUDIT_STATUS_UNAVAILABLE = "unavailable"
AUDIT_STATUSES = {
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_UNAVAILABLE,
}

SOURCE_AUDIT_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
    "recent_catalysts",
    "peer_discovery",
)
CORE_DATA_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
)
CRITICAL_TRUST_SOURCES = ("market_data", "financial_statements")

TRUST_STATUS_FRESH = "fresh"
TRUST_STATUS_PARTIAL = "partial"
TRUST_STATUS_STALE = "stale"
TRUST_STATUS_ERROR = "error"
TRUST_STATUS_UNKNOWN = "unknown"
TRUST_STATUSES = {
    TRUST_STATUS_FRESH,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_STALE,
    TRUST_STATUS_ERROR,
    TRUST_STATUS_UNKNOWN,
}

SOURCE_LABELS = {
    "market_data": "市場資料",
    "financial_statements": "年度財報",
    "monthly_revenue": "月營收",
    "institutional_trading": "法人籌碼",
    "dynamic_peer_metrics": "同業指標",
    "pe_river_chart": "P/E 河流圖",
    "recent_catalysts": "近期催化劑",
    "peer_discovery": "同業搜尋",
}

AUDIT_STATUS_LABELS = {
    AUDIT_STATUS_SUCCESS: "成功",
    AUDIT_STATUS_ERROR: "異常",
    AUDIT_STATUS_SKIPPED_FRESH_CACHE: "新鮮快取",
    AUDIT_STATUS_UNAVAILABLE: "無可用資料",
}

TRUST_STATUS_LABELS = {
    TRUST_STATUS_FRESH: "資料新鮮",
    TRUST_STATUS_PARTIAL: "部分異常",
    TRUST_STATUS_STALE: "部分過期",
    TRUST_STATUS_ERROR: "來源異常",
    TRUST_STATUS_UNKNOWN: "未記錄",
}

_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|secret|password|token|authorization|prompt|retry|env(?:iron)?(?:ment)?)",
    re.IGNORECASE,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_from_epoch(epoch: Optional[float]) -> Optional[str]:
    if not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(str(source or ""), str(source or "unknown"))


def audit_status_label(status: str) -> str:
    return AUDIT_STATUS_LABELS.get(str(status or ""), str(status or "unknown"))


def trust_status_label(status: str) -> str:
    return TRUST_STATUS_LABELS.get(str(status or ""), str(status or "unknown"))


def data_snapshot_filename_for_report(filename: str) -> str:
    return filename[:-5] + ".data.json" if filename.endswith(".html") else f"{filename}.data.json"


def _duration_ms(started_at_epoch: Optional[float], finished_at_epoch: Optional[float], duration_ms: Optional[float]) -> Optional[int]:
    if isinstance(duration_ms, (int, float)):
        return max(0, int(round(float(duration_ms))))
    if isinstance(started_at_epoch, (int, float)) and isinstance(finished_at_epoch, (int, float)):
        return max(0, int(round((float(finished_at_epoch) - float(started_at_epoch)) * 1000)))
    return None


def build_source_audit_entry(
    source: str,
    provider: str,
    status: str,
    *,
    fetched_at_epoch: Optional[float] = None,
    fetched_at: Optional[str] = None,
    started_at_epoch: Optional[float] = None,
    finished_at_epoch: Optional[float] = None,
    duration_ms: Optional[float] = None,
    record_count: Optional[int] = None,
    cache_hit: bool = False,
    stale: bool = False,
    error_kind: str = "",
    message: str = "",
) -> dict:
    normalized_status = status if status in AUDIT_STATUSES else AUDIT_STATUS_UNAVAILABLE
    finished_at_epoch = finished_at_epoch if isinstance(finished_at_epoch, (int, float)) else time.time()
    fetched_at_value = fetched_at or iso_from_epoch(fetched_at_epoch or finished_at_epoch)
    return {
        "source": str(source or "unknown"),
        "provider": str(provider or ""),
        "status": normalized_status,
        "fetched_at": fetched_at_value,
        "duration_ms": _duration_ms(started_at_epoch, finished_at_epoch, duration_ms),
        "record_count": int(record_count or 0),
        "cache_hit": bool(cache_hit),
        "stale": bool(stale),
        "error_kind": str(error_kind or ""),
        "message": str(message or ""),
    }


def append_source_audit(data: dict, entry: dict) -> dict:
    if not isinstance(data, dict):
        return data
    entries = data.get("source_audit")
    if not isinstance(entries, list):
        entries = []
    entries.append(entry)
    data["source_audit"] = entries
    return data


def source_record_count(source: str, data: dict) -> int:
    if not isinstance(data, dict):
        return 0
    source = str(source or "")
    if source == "market_data":
        fields = ("current_price", "market_cap_raw", "pe_ratio_raw", "pb_ratio", "price_history")
        return sum(1 for field in fields if _has_value(data.get(field)))
    if source == "financial_statements":
        return max(
            _list_count(data.get("years")),
            _list_count(data.get("revenue_history")),
            _list_count(data.get("net_income_history")),
            _list_count(data.get("fcf_history")),
            _list_count(data.get("total_assets_history")),
            _list_count(data.get("total_equity_history")),
        )
    if source == "monthly_revenue":
        return _list_count(data.get("recent_monthly_revenue"))
    if source == "institutional_trading":
        value = data.get("institutional_trading")
        if isinstance(value, dict):
            daily = value.get("daily_total_net_buy_last_10")
            return _list_count(daily) or (1 if value else 0)
        return 0
    if source == "dynamic_peer_metrics":
        return _list_count(data.get("dynamic_peer_metrics"))
    if source == "pe_river_chart":
        value = data.get("pe_river_chart")
        if not isinstance(value, dict):
            return 0
        bands = value.get("bands")
        if isinstance(bands, dict) and bands:
            return max((_list_count(series) for series in bands.values()), default=0)
        return _list_count(value.get("years")) or _list_count(value.get("eps_twd"))
    if source == "recent_catalysts":
        return _list_count(data.get("recent_catalysts"))
    if source == "peer_discovery":
        return _list_count(data.get("peer_discovery_results"))
    value = data.get(source)
    if isinstance(value, list):
        return _list_count(value)
    if isinstance(value, dict):
        return len(value)
    return 1 if _has_value(value) else 0


def normalize_data_trust(value: Any) -> dict:
    if not isinstance(value, dict):
        return unknown_data_trust()

    status = str(value.get("status") or TRUST_STATUS_UNKNOWN)
    if status not in TRUST_STATUSES:
        status = TRUST_STATUS_UNKNOWN
    notes = value.get("notes", [])
    if isinstance(notes, str):
        notes = [notes]
    elif not isinstance(notes, list):
        notes = []

    return {
        "status": status,
        "critical_failures": _string_list(value.get("critical_failures")),
        "stale_sources": _string_list(value.get("stale_sources")),
        "last_market_data_at": value.get("last_market_data_at"),
        "notes": [str(item) for item in notes if str(item).strip()],
    }


def unknown_data_trust() -> dict:
    return {
        "status": TRUST_STATUS_UNKNOWN,
        "critical_failures": [],
        "stale_sources": [],
        "last_market_data_at": None,
        "notes": ["未記錄資料可信度快照。"],
    }


def build_data_trust(data: dict) -> dict:
    if not isinstance(data, dict):
        return unknown_data_trust()

    source_freshness = data.get("source_freshness") if isinstance(data.get("source_freshness"), dict) else {}
    audit_entries = data.get("source_audit") if isinstance(data.get("source_audit"), list) else []
    if not source_freshness and not audit_entries:
        return unknown_data_trust()

    latest_audit = _latest_audit_by_source(audit_entries)
    critical_failures = [
        source
        for source in CRITICAL_TRUST_SOURCES
        if latest_audit.get(source, {}).get("status") == AUDIT_STATUS_ERROR
    ]
    core_failures = [
        source
        for source in CORE_DATA_SOURCES
        if latest_audit.get(source, {}).get("status") == AUDIT_STATUS_ERROR
    ]
    stale_sources = _stale_sources(source_freshness, latest_audit)
    error_sources = sorted({
        str(entry.get("source") or "")
        for entry in audit_entries
        if isinstance(entry, dict) and entry.get("status") == AUDIT_STATUS_ERROR and entry.get("source")
    })

    if critical_failures and not _has_usable_critical_data(data, latest_audit):
        status = TRUST_STATUS_ERROR
        notes = ["核心市場或財報來源失敗，且沒有足夠可用資料。"]
    elif critical_failures or core_failures or error_sources:
        status = TRUST_STATUS_PARTIAL
        notes = ["部分來源異常或使用備援資料，請搭配來源審計表檢視。"]
    elif stale_sources:
        status = TRUST_STATUS_STALE
        notes = ["部分資料來源超過新鮮度門檻，分析已保留過期標記。"]
    else:
        status = TRUST_STATUS_FRESH
        notes = ["核心資料在新鮮度門檻內，來源審計未見主要異常。"]

    if data.get("data_source_notes"):
        notes.append("另有資料口徑或備援補值註記，詳見報告參考資料區。")

    return {
        "status": status,
        "critical_failures": core_failures,
        "stale_sources": stale_sources,
        "last_market_data_at": _last_market_data_at(data, source_freshness, latest_audit),
        "notes": notes,
    }


def finalize_data_trust(data: dict) -> dict:
    if isinstance(data, dict):
        data["data_trust"] = build_data_trust(data)
    return data


def sanitize_for_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str.startswith("_") or _SENSITIVE_KEY_RE.search(key_str):
                continue
            clean[key_str] = sanitize_for_snapshot(item)
        return clean
    if isinstance(value, list):
        return [sanitize_for_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_snapshot(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _snapshot_text(value: Any, *, max_chars: int = SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[Snapshot truncated for size]"


def _sanitize_rerun_context(context: dict) -> dict:
    if not isinstance(context, dict):
        return {"analyses": {}, "structured_outputs": {}, "parsed": {}}

    analyses = {}
    raw_analyses = context.get("analyses", {})
    if isinstance(raw_analyses, dict):
        for agent_num, text in raw_analyses.items():
            if text is None:
                continue
            analyses[str(agent_num)] = _snapshot_text(text)

    return sanitize_for_snapshot({
        "analyses": analyses,
        "structured_outputs": context.get("structured_outputs", {}),
        "parsed": context.get("parsed", {}),
        "pipeline_id": context.get("pipeline_id"),
        "pipeline_label": context.get("pipeline_label"),
        "agent_sequence": context.get("agent_sequence"),
    })


def build_data_snapshot(
    context: dict,
    pipeline_id: Optional[str] = None,
    generated_at: Optional[str] = None,
    max_bytes: Optional[int] = None,
) -> dict:
    data = context.get("data", {}) if isinstance(context, dict) else {}
    if not isinstance(data, dict):
        data = {}
    data_trust = normalize_data_trust(data.get("data_trust")) if data.get("data_trust") else build_data_trust(data)
    snapshot = {
        "snapshot_schema_version": DATA_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_truncated": False,
        "snapshot_size_bytes": 0,
        "snapshot_omitted_sections": [],
        "snapshot_migrated_from_legacy": False,
        "ticker": context.get("ticker") or data.get("ticker"),
        "company_name": context.get("company_name") or data.get("company_name"),
        "pipeline": pipeline_id or context.get("pipeline_id"),
        "generated_at": generated_at or utc_now_iso(),
        "refreshed_from_report": sanitize_for_snapshot(context.get("refreshed_from_report", "")),
        "data_schema_version": data.get("data_schema_version"),
        "source_freshness": sanitize_for_snapshot(data.get("source_freshness", {})),
        "source_audit": sanitize_for_snapshot(data.get("source_audit", [])),
        "data_trust": data_trust,
        "data_source_notes": sanitize_for_snapshot(data.get("data_source_notes", [])),
        "deterministic_fallbacks": sanitize_for_snapshot(context.get("deterministic_fallbacks", [])),
        "report_lint": sanitize_for_snapshot(context.get("report_lint", {})),
        "rerun_context": _sanitize_rerun_context(context),
        "data": sanitize_for_snapshot(data),
    }
    return apply_snapshot_size_governance(snapshot, max_bytes=max_bytes)


def snapshot_size_bytes(snapshot: dict) -> int:
    return len(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _set_stable_snapshot_size(snapshot: dict) -> dict:
    previous_size = -1
    while True:
        size = snapshot_size_bytes(snapshot)
        snapshot["snapshot_size_bytes"] = size
        if size == previous_size:
            return snapshot
        previous_size = size


def validate_data_snapshot(snapshot: Any) -> dict:
    errors = []
    if not isinstance(snapshot, dict):
        return {"valid": False, "errors": ["snapshot must be an object"]}
    if snapshot.get("snapshot_schema_version") not in SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS:
        errors.append("unsupported snapshot_schema_version")
    for key in (
        "ticker",
        "pipeline",
        "generated_at",
        "data_schema_version",
        "source_freshness",
        "source_audit",
        "data_trust",
        "data",
    ):
        if key not in snapshot:
            errors.append(f"missing {key}")
    if not isinstance(snapshot.get("source_audit", []), list):
        errors.append("source_audit must be a list")
    if not isinstance(snapshot.get("data_trust", {}), dict):
        errors.append("data_trust must be an object")
    return {"valid": not errors, "errors": errors}


def apply_snapshot_size_governance(snapshot: dict, max_bytes: Optional[int] = None) -> dict:
    try:
        from config import DATA_SNAPSHOT_MAX_BYTES
        limit = int(max_bytes or DATA_SNAPSHOT_MAX_BYTES)
    except Exception:
        limit = int(max_bytes or 2 * 1024 * 1024)

    governed = json.loads(json.dumps(snapshot, ensure_ascii=False, default=str))
    governed["snapshot_truncated"] = False
    governed["snapshot_omitted_sections"] = []
    governed["snapshot_size_bytes"] = 0

    size = snapshot_size_bytes(governed)
    if size <= limit:
        return _set_stable_snapshot_size(governed)

    governed["snapshot_truncated"] = True
    data = governed.get("data") if isinstance(governed.get("data"), dict) else {}
    for key in SNAPSHOT_TRIMMABLE_LIST_FIELDS:
        value = data.get(key)
        if isinstance(value, list) and len(value) > 3:
            omitted = len(value) - 3
            data[key] = value[:3]
            governed["snapshot_omitted_sections"].append(f"data.{key}:{omitted}")

    size = snapshot_size_bytes(governed)
    if size > limit and isinstance(data, dict):
        removed_keys = sorted(key for key in data if key not in SNAPSHOT_CORE_DATA_KEYS)
        governed["data"] = {key: data[key] for key in data if key in SNAPSHOT_CORE_DATA_KEYS}
        if removed_keys:
            governed["snapshot_omitted_sections"].append(f"data.non_core_fields:{len(removed_keys)}")

    size = snapshot_size_bytes(governed)
    rerun_context = governed.get("rerun_context") if isinstance(governed.get("rerun_context"), dict) else {}
    analyses = rerun_context.get("analyses") if isinstance(rerun_context.get("analyses"), dict) else {}
    if size > limit and analyses:
        shortened = {}
        omitted_chars = 0
        for agent_num, text in analyses.items():
            text_value = str(text or "")
            shortened_text = _snapshot_text(text_value, max_chars=2000)
            omitted_chars += max(0, len(text_value) - len(shortened_text))
            shortened[str(agent_num)] = shortened_text
        rerun_context["analyses"] = shortened
        if omitted_chars:
            governed["snapshot_omitted_sections"].append(f"rerun_context.analyses_chars:{omitted_chars}")

    size = snapshot_size_bytes(governed)
    if size > limit and rerun_context:
        removed_keys = [key for key in ("parsed", "structured_outputs") if key in rerun_context]
        for key in removed_keys:
            rerun_context.pop(key, None)
        if removed_keys:
            governed["snapshot_omitted_sections"].append(f"rerun_context.non_essential:{len(removed_keys)}")

    return _set_stable_snapshot_size(governed)


def write_data_snapshot(path: str | Path, context: dict, pipeline_id: Optional[str] = None) -> dict:
    snapshot = build_data_snapshot(context, pipeline_id=pipeline_id)
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def read_data_trust_from_snapshot(path: str | Path) -> dict:
    path_obj = Path(path)
    if not path_obj.exists():
        return unknown_data_trust()
    try:
        snapshot = json.loads(path_obj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return unknown_data_trust()
    return normalize_data_trust(snapshot.get("data_trust") if isinstance(snapshot, dict) else {})


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


def _latest_audit_by_source(entries: list) -> dict:
    latest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        if source:
            latest[source] = entry
    return latest


def _stale_sources(source_freshness: dict, latest_audit: dict) -> list[str]:
    sources = set()
    for source, entry in source_freshness.items():
        if isinstance(entry, dict) and entry.get("stale"):
            sources.add(str(source))
    for source, entry in latest_audit.items():
        if isinstance(entry, dict) and entry.get("stale"):
            sources.add(str(source))
    return sorted(sources)


def _last_market_data_at(data: dict, source_freshness: dict, latest_audit: dict) -> Optional[str]:
    market = source_freshness.get("market_data") if isinstance(source_freshness.get("market_data"), dict) else {}
    return (
        market.get("fetched_at")
        or data.get("market_data_fetched_at")
        or latest_audit.get("market_data", {}).get("fetched_at")
    )


def _has_usable_critical_data(data: dict, latest_audit: dict) -> bool:
    market_entry = latest_audit.get("market_data", {})
    financial_entry = latest_audit.get("financial_statements", {})
    market_ok = market_entry.get("status") in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE} or source_record_count("market_data", data) > 0
    financial_ok = financial_entry.get("status") in {AUDIT_STATUS_SUCCESS, AUDIT_STATUS_SKIPPED_FRESH_CACHE} or source_record_count("financial_statements", data) > 0
    return market_ok and financial_ok


def _list_count(value: Any) -> int:
    if isinstance(value, list):
        return len([item for item in value if _has_value(item)])
    return 0


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().upper() != "N/A"
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []
