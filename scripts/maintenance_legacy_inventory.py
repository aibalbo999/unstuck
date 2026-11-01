"""Bounded, logically read-only legacy dispatch metadata inventory, NOT drain.

No backend/store/env imports, migrations, Redis access, retries or reconciliation.
Paths are explicitly supplied, never discovered from runtime defaults. Existing
SQLite SHM read marks may change; the controller owns actual path/sole-writer
binding and excludes replacement during this diagnostic. A complete projection
does not prove full history, claim settlement, queue state or safe handover.
"""
from collections import defaultdict
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import stat
import time

from maintenance_readiness import ProbeUnavailable, _existing, _path, _sqlite_family


SCHEMA = "stock-agent.legacy-dispatch-inventory.v1"
BASELINE = "758242290e795146520f58f68ffa113cac35e52c"
MAX_ROWS = 10000
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_PROJECTION_BYTES = 8 * 1024 * 1024
QUERY_SECONDS = 5
TABLES = {
    "watchlist_items": ("ticker", "pipeline", "enabled", "schedule_slots_json", "last_run_dates_json", "created_at", "updated_at"),
    "watchlist_item_triggers": ("ticker", "pipeline", "triggers_json", "updated_at"),
    "watchlist_trigger_events": ("ticker", "pipeline", "trigger_key", "evaluation_date", "trigger_type", "matched", "pipeline_selected", "job_id", "created_at"),
    "watchlist_meta": ("key", "value"),
    "analysis_jobs": ("job_id", "ticker", "pipeline_id", "status", "created_at", "updated_at", "claimed_at", "worker_instance_id"),
    "analysis_events": ("id", "job_id", "event_type", "phase", "created_at"),
}
ROLE_TABLES = {
    "watchlist_db": tuple(TABLES)[:4],
    "task_db": ("analysis_jobs", "analysis_events"),
    "legacy_watchlist_db": ("watchlist_item_triggers", "watchlist_trigger_events"),
}
PATHS = (*ROLE_TABLES, "legacy_watchlist_json")
MODES = ("v1", "v2", "v3", "v4", "both")
ACTIVE = ("queued", "running", "waiting_retry")
TERMINAL = ("done", "error", "cancelled")


def _sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def _json(text, expected):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ProbeUnavailable("duplicate_json_key")
            result[key] = value
        return result
    def invalid(value):
        raise ProbeUnavailable("nonfinite_json_number")
    def floating(value):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else invalid(value)
    if type(text) not in (str, bytes) or len(text) > MAX_JSON_BYTES:
        raise ProbeUnavailable("bounded_json_required")
    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=floating)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeUnavailable("invalid_json") from None
    if type(result) is not expected:
        raise ProbeUnavailable("unexpected_json_shape")
    return result


def _identity(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value):
        raise ProbeUnavailable("invalid_record_identity")
    return value


def _mode(value):
    if value not in MODES:
        raise ProbeUnavailable("unknown_pipeline_identity")
    return value


def _day(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ProbeUnavailable("invalid_record_date")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ProbeUnavailable("invalid_record_date") from None
    return value


def _bit(value):
    if type(value) not in (int, bool) or value not in (0, 1):
        raise ProbeUnavailable("unknown_boolean_state")
    return bool(value)


def _timestamp_text(value):
    # Preserve the recorded offset (or its absence); never invent a timezone.
    if type(value) is not str or len(value) > 64 or "T" not in value:
        raise ProbeUnavailable("invalid_record_timestamp")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ProbeUnavailable("invalid_record_timestamp") from None
    return value


def _optional_exists(path):
    # An absent legacy file is an observation, not permission to create it.
    for parent in path.parents:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ProbeUnavailable("symlink_path_rejected")
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    _existing(path)
    return True


def _database_rows(path, tables):
    before, family = _existing(path), _sqlite_family(path)
    deadline = time.monotonic() + QUERY_SECONDS
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0)
    try:
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_JSON_BYTES)
        conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("BEGIN")
        placeholders = ",".join("?" for _ in tables)
        schema = {row[0]: row[1] for row in conn.execute(
            f"SELECT name, sql FROM sqlite_schema WHERE type='table' AND name IN ({placeholders})", tables)}
        result, counts, truncated, total_bytes = {}, {}, [], 0
        for table in tables:
            if table not in schema or not re.match(r"^CREATE\s+TABLE\b", schema[table] or "", re.I):
                raise ProbeUnavailable("required_plain_table_missing")
            columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            if not set(TABLES[table]).issubset(columns):
                raise ProbeUnavailable("required_columns_missing")
            selected = ", ".join('"' + name + '"' for name in TABLES[table])
            counts[table] = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            result[table] = []
            cursor = conn.execute(f'SELECT {selected} FROM "{table}" ORDER BY {selected} LIMIT ?', (MAX_ROWS,))
            try:
                for row in cursor:
                    encoded = json.dumps(row, ensure_ascii=True, allow_nan=False).encode("ascii")
                    if total_bytes + len(encoded) > MAX_PROJECTION_BYTES:
                        break
                    total_bytes += len(encoded)
                    result[table].append(dict(zip(TABLES[table], row)))
            finally:
                cursor.close()
            if counts[table] > len(result[table]):
                truncated.append(table)
        conn.rollback()
    finally:
        conn.close()
    after = _sqlite_family(path)
    if (_existing(path) != before or after[:2] != family[:2]
            or (family[2] is not None and after[2][:2] != family[2][:2])):
        raise ProbeUnavailable("storage_changed_during_inventory")
    return result, {"status": "read", "table_counts": counts, "truncated_tables": truncated,
                    "projection_sha256": _sha(result), "sqlite_mode": family[0],
                    "projection_bytes": total_bytes, "row_limit": MAX_ROWS,
                    "projection_byte_limit": MAX_PROJECTION_BYTES}


def _legacy_json(path):
    before = _existing(path)
    if before[2] > MAX_JSON_BYTES:
        raise ProbeUnavailable("bounded_json_required")
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    value = _json(raw, dict)
    if type(value.get("items")) is not list:
        raise ProbeUnavailable("legacy_items_missing")
    if _existing(path) != before:
        raise ProbeUnavailable("storage_changed_during_inventory")
    return value["items"][:MAX_ROWS], {"status": "read", "item_count": len(value["items"]),
        "truncated": len(value["items"]) > MAX_ROWS, "source_sha256": hashlib.sha256(raw).hexdigest()}


def _error(result, resource, code, *, table=None, row=None):
    result["readback_complete"] = False
    result["errors"].append({"resource": resource, "code": code,
                            **({"table": table, "row": row} if table is not None else {})})


def read_legacy_inventory(manifest):
    """Inventory current metadata only; never infer zero unresolved claims."""
    if (type(manifest) is not dict or set(manifest) != {"schema_version", "backend_revision", "control_sha256", "paths"}
            or manifest["schema_version"] != SCHEMA or manifest["backend_revision"] != BASELINE
            or type(manifest["control_sha256"]) is not str
            or not re.fullmatch(r"[a-f0-9]{64}", manifest["control_sha256"])
            or type(manifest["paths"]) is not dict or set(manifest["paths"]) != set(PATHS)):
        raise ProbeUnavailable("exact_supported_legacy_manifest_required")
    paths = {role: _path(path) for role, path in manifest["paths"].items()}
    result = {"schema_version": SCHEMA, "backend_revision": BASELINE, "manifest_sha256": _sha(manifest),
        "readback_complete": True, "readback_scope": "listed_paths_projected_metadata_only",
        "history_complete": False, "settlement_proven": False, "pending_count": None,
        "legacy_handover_verified": False, "production_ready": False, "queue_readback_performed": False,
        "filesystem_inert": False, "resources": {}, "schedule_marks": [], "trigger_events": [],
        "trigger_configs": [], "meta_markers": [], "jobs": [], "job_event_counts": {}, "errors": [],
        "limitations": ["legacy_claim_and_completion_share_date_marker", "trigger_record_can_precede_job",
            "terminal_or_matching_jobs_do_not_prove_dispatch", "deleted_or_expired_history_unrecoverable",
            "no_queue_or_process_settlement_readback", "cross_database_snapshot_not_atomic",
            "controller_must_bind_actual_paths_and_exclude_replacement", "existing_SHM_read_marks_may_change"]}
    groups = defaultdict(list)
    for role in ROLE_TABLES:
        groups[paths[role]].append(role)
    rows_by_role = {}
    for path, roles in groups.items():
        try:
            exists = _optional_exists(path)
            if not exists and roles == ["legacy_watchlist_db"]:
                result["resources"][roles[0]] = {"status": "absent"}
                continue
            if not exists:
                raise ProbeUnavailable("required_database_missing")
            required = tuple(dict.fromkeys(table for role in roles for table in ROLE_TABLES[role]))
            rows, receipt = _database_rows(path, required)
            for role in roles:
                result["resources"][role] = {**receipt, "shared_roles": roles}
                if role == "legacy_watchlist_db" and "watchlist_db" in roles:
                    result["resources"][role]["alias_of"] = "watchlist_db"
                else:
                    rows_by_role[role] = {table: rows[table] for table in ROLE_TABLES[role]}
                if receipt["truncated_tables"]:
                    _error(result, role, "row_limit_reached")
        except (ProbeUnavailable, OSError, sqlite3.Error, ValueError, TypeError):
            # Never include sqlite errors, paths, raw metadata or backend secrets.
            for role in roles:
                result["resources"][role] = {"status": "unavailable"}
                _error(result, role, "database_readback_unavailable")

    legacy_items = []
    role = "legacy_watchlist_json"
    try:
        if _optional_exists(paths[role]):
            legacy_items, receipt = _legacy_json(paths[role])
            result["resources"][role] = receipt
            if receipt["truncated"]:
                _error(result, role, "row_limit_reached")
        else:
            result["resources"][role] = {"status": "absent"}
    except (ProbeUnavailable, OSError, ValueError, TypeError):
        result["resources"][role] = {"status": "unavailable"}
        _error(result, role, "legacy_json_readback_unavailable")

    def consume(role, table, callback):
        for index, row in enumerate(rows_by_role.get(role, {}).get(table, [])):
            try:
                callback(row)
            except (ProbeUnavailable, ValueError, TypeError, KeyError):
                _error(result, role, "invalid_projected_record", table=table, row=index)

    items = set()
    def item(row, role="watchlist_db", legacy=False):
        ticker, pipeline = _identity(row["ticker"]), _mode(row["pipeline"])
        enabled = _bit(row["enabled"])
        slots = row["schedule_slots"] if legacy else _json(row["schedule_slots_json"], list)
        marks = row["last_run_dates"] if legacy else _json(row["last_run_dates_json"], dict)
        if type(slots) is not list or type(marks) is not dict or any(slot not in ("pre_market", "post_market") for slot in slots):
            raise ProbeUnavailable("unknown_schedule_state")
        items.add((role, ticker, pipeline))
        for slot, day in marks.items():
            result["schedule_marks"].append({"resource": role, "ticker": ticker, "pipeline": pipeline,
                "enabled": enabled, "slot": _identity(slot), "run_date": _day(day),
                "currently_scheduled": slot in slots, "dispatch_status": "unknown"})
    consume("watchlist_db", "watchlist_items", item)
    for index, row in enumerate(legacy_items):
        try:
            item(row, "legacy_watchlist_json", True)
        except (ProbeUnavailable, ValueError, TypeError, KeyError):
            _error(result, "legacy_watchlist_json", "invalid_projected_record", table="items", row=index)

    jobs, candidates = {}, defaultdict(list)
    def job(row):
        row = dict(row)
        key = _identity(row["job_id"])
        _identity(row["ticker"])
        _mode(row["pipeline_id"])
        if row["status"] not in (*ACTIVE, *TERMINAL) or key in jobs:
            raise ProbeUnavailable("unknown_or_duplicate_job_state")
        for field in ("created_at", "updated_at", "claimed_at"):
            if row[field] is None and field == "claimed_at":
                continue
            if type(row[field]) not in (int, float) or not math.isfinite(row[field]):
                raise ProbeUnavailable("invalid_job_timestamp")
        if row["worker_instance_id"] is not None:
            _identity(row["worker_instance_id"])
        row["worker_identity_sha256"] = _sha(row.pop("worker_instance_id"))
        jobs[key] = row
        candidates[(row["ticker"], row["pipeline_id"])].append(key)
        result["jobs"].append(row)
    consume("task_db", "analysis_jobs", job)

    def event(row, role):
        value = dict(row)
        ticker, pipeline = _identity(row["ticker"]), _mode(row["pipeline"])
        selected = _mode(row["pipeline_selected"])
        _identity(row["trigger_key"])
        _identity(row["trigger_type"])
        _day(row["evaluation_date"])
        _timestamp_text(row["created_at"])
        matched = _bit(row["matched"])
        job_id = row["job_id"]
        if job_id != "":
            _identity(job_id)
        linked = jobs.get(job_id)
        reference = "none" if not job_id else "missing_job" if linked is None else (
            "identity_mismatch" if (linked["ticker"], linked["pipeline_id"]) != (ticker, selected)
            else "present_active" if linked["status"] in ACTIVE else "present_terminal")
        ids = candidates.get((ticker, selected), [])
        value.update(resource=role, matched=matched, orphan_item=("watchlist_db", ticker, pipeline) not in items,
            dispatch_status="unknown" if matched else "not_matched_record",
            job_reference_status=reference, candidate_job_count=len(ids), candidate_job_ids=ids[:20],
            candidate_links_proven=False)
        result["trigger_events"].append(value)

    for role in ("watchlist_db", "legacy_watchlist_db"):
        def config(row, role=role):
            ticker, pipeline = _identity(row["ticker"]), _mode(row["pipeline"])
            triggers = _json(row["triggers_json"], list)
            result["trigger_configs"].append({"resource": role, "ticker": ticker, "pipeline": pipeline,
                "trigger_count": len(triggers), "config_sha256": _sha(triggers)})
        consume(role, "watchlist_item_triggers", config)
        consume(role, "watchlist_trigger_events", lambda row, role=role: event(row, role))

    def meta(row):
        key, value = row["key"], row["value"]
        if type(key) is not str or type(value) is not str:
            raise ProbeUnavailable("invalid_meta_marker")
        result["meta_markers"].append({"key_sha256": _sha(key), "value_sha256": _sha(value),
            "kind": "legacy_migration" if key.startswith("legacy_") else "screener" if "screener" in key else "other"})
    consume("watchlist_db", "watchlist_meta", meta)
    def job_event(row):
        key = _identity(row["job_id"])
        if (type(row["id"]) is not int or row["id"] < 0
                or type(row["created_at"]) not in (float, int) or not math.isfinite(row["created_at"])):
            raise ProbeUnavailable("invalid_event_identity_or_time")
        for field in ("event_type", "phase"):
            if row[field] not in (None, ""):
                _identity(row[field])
        summary = result["job_event_counts"].setdefault(key, {"count": 0, "job_present": key in jobs,
            "first_created_at": row["created_at"], "last_created_at": row["created_at"], "types": {}, "phases": {}})
        summary["count"] += 1
        summary["first_created_at"] = min(summary["first_created_at"], row["created_at"])
        summary["last_created_at"] = max(summary["last_created_at"], row["created_at"])
        for field, output in (("event_type", "types"), ("phase", "phases")):
            value = row[field] or "unknown"
            summary[output][value] = summary[output].get(value, 0) + 1
    consume("task_db", "analysis_events", job_event)
    result["observed_ambiguous_claims"] = len(result["schedule_marks"]) + sum(event["matched"] for event in result["trigger_events"])
    result["summary_zh"] = ("指定紀錄盤點完成；仍無法證明舊排程已安全結束。" if result["readback_complete"] else
                            "指定紀錄盤點不完整；不能據此進行正式移交。")
    return result
