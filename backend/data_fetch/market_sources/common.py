"""Shared helpers for market-data source modules."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from source_audit import audited_fetch


def safe_get(obj, key, default="N/A"):
    try:
        val = obj.get(key, default)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return val
    except Exception:
        return default


def is_missing_value(value) -> bool:
    if value is None or value == "N/A":
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def first_number(*values):
    for value in values:
        if is_missing_value(value):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _dedupe_records(records: list[dict], key: str = "title", limit: int = 6) -> list[dict]:
    kept = []
    seen = set()
    for record in records:
        marker = str(record.get(key) or record.get("link") or "").strip().lower()
        if not marker or marker in seen:
            continue
        kept.append(record)
        seen.add(marker)
        if len(kept) >= limit:
            break
    return kept


def _run_named_fetches(fetchers: dict[str, tuple], max_workers: int = 4, include_audit: bool = False) -> dict:
    """Run independent blocking fetches concurrently and keep failures isolated."""
    if not fetchers:
        return {"values": {}, "audit": []} if include_audit else {}

    results = {}
    audit_entries = []
    worker_count = max(1, min(max_workers, len(fetchers)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {}
        for name, spec in fetchers.items():
            func, args, default, warning = spec[:4]
            source = spec[4] if len(spec) > 4 else name
            provider = spec[5] if len(spec) > 5 else name
            if include_audit:
                futures[executor.submit(audited_fetch, source, provider, func, args, {}, default)] = (name, default, warning, True)
            else:
                futures[executor.submit(func, *args)] = (name, default, warning, False)

        for future in as_completed(futures):
            name, default, _warning, audited = futures[future]
            try:
                result = future.result()
                if audited:
                    results[name] = result.get("value", default)
                    audit_entries.append(result.get("audit", {}))
                else:
                    results[name] = result
            except Exception:
                results[name] = default

    if include_audit:
        return {"values": results, "audit": [entry for entry in audit_entries if entry]}
    return results
