"""Reviewed, reversible unscored dispositions for one immutable legacy cohort.

Preview only reads SQLite. Apply is an explicit operator action; the scheduler
never creates dispositions. This journal is neither a trade result nor evidence
of PIT availability, execution, actual costs, or strategy validity.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from reporting.trade_price_grid import grid_assessment

BATCH_ID = "hcs-legacy76-df03143a097e1e25"
MANIFEST_SHA256 = "df5413aee36f3e6f142a52f0570be5036513a228fa840412b110e0808d3b7720"
TABLE = "legacy76_scope_disposition_events_v1"
TRADING_TERMINAL = frozenset({"target_first", "stop_first", "horizon_exit", "not_entered", "no_trade", "ambiguous"})
BINDING_KEYS = ("scope_id", "revision_id", "revision_payload_sha256", "original_payload_sha256", "manifest_sha256",
                "earliest_revision_id", "earliest_plan_sha256")
LIMITATIONS = [
    "historical_qualified_price_path_not_implemented",
    "point_in_time_not_verified", "actual_costs_not_verified",
    "unscored_disposition_is_not_no_trade_hit_miss_or_validated",
]


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def _connect(path, *, write=False):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=15)
    if not write:
        conn.execute("PRAGMA query_only=ON")
    return conn


def _table_exists(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone() is not None


def active_for_connection(conn, batch_id):
    """No schema creation on the scheduler/API read path; other batches untouched."""
    if batch_id != BATCH_ID or not _table_exists(conn):
        return {}
    active = {}
    for event_id, scope_id, action, raw in conn.execute(
        f"SELECT event_id,scope_id,action,payload_json FROM {TABLE} WHERE batch_id=? ORDER BY sequence", (BATCH_ID,)
    ):
        body = json.loads(raw)
        if digest(body) != event_id or body["item"]["scope_id"] != scope_id or body["item"]["action"] != action:
            raise ValueError("disposition journal integrity mismatch")
        if body["item"]["manifest_sha256"] != MANIFEST_SHA256 or body["request"]["batch_id"] != BATCH_ID:
            raise ValueError("disposition journal cohort mismatch")
        if action == "close_unscored":
            active[scope_id] = {"event_id": event_id, "reason": body["item"]["reason"],
                                "reviewer": body["request"]["reviewer"], "binding": {k: body["item"][k] for k in BINDING_KEYS}}
        elif action == "reopen" and active.get(scope_id, {}).get("event_id") == body["item"].get("reopens_event_id"):
            active.pop(scope_id)
        else:
            raise ValueError("disposition journal action/order mismatch")
    return active


def active_for_path(path):
    if not Path(path).exists():
        return {}
    with closing(_connect(path)) as conn:
        return active_for_connection(conn, BATCH_ID)


def _text(value, label, minimum=1):
    if not isinstance(value, str) or len(value.strip()) < minimum or len(value) > 4000:
        raise ValueError(f"review requires {label}")


def _review_request(request):
    if not isinstance(request, dict) or request.get("batch_id") != BATCH_ID:
        raise ValueError("only the fixed legacy76 batch can be disposed")
    if set(request) != {"batch_id", "reviewer", "review_note", "items"}:
        raise ValueError("unexpected review request fields")
    _text(request.get("reviewer"), "named reviewer")
    _text(request.get("review_note"), "explicit review note", 20)
    items = request.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 76:
        raise ValueError("review requires explicit scoped items")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("review items must be objects")
    if len({x.get("scope_id") for x in items}) != len(items):
        raise ValueError("duplicate scope in review")


def _unrecoverability_review(item):
    """A missing field alone is never evidence that its origin is unrecoverable."""
    review = item.get("evidence_review")
    if not isinstance(review, dict) or review.get("schema_version") != "legacy76-unrecoverability-review:v1":
        raise ValueError("unrecoverable closure requires an explicit evidence inventory review")
    if review.get("scope_id") != item["scope_id"] or review.get("revision_payload_sha256") != item["revision_payload_sha256"]:
        raise ValueError("evidence review binding mismatch")
    for key in ("original_contract_unrecoverable", "current_data_not_used_as_pit", "original_plan_unchanged"):
        if review.get(key) is not True:
            raise ValueError(f"evidence review must attest {key}")
    _text(review.get("conclusion"), "evidence inventory conclusion", 40)
    records = review.get("searched_records")
    if not isinstance(records, list) or len(records) < 2:
        raise ValueError("evidence review needs original inputs and historical archive search receipts")
    kinds = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("evidence search receipts must be objects")
        kinds.add(record.get("kind"))
        for key in ("source_ref", "finding", "searched_at"):
            _text(record.get(key), "search receipt " + key)
        sha = record.get("receipt_sha256", "")
        if len(sha) != 64 or any(x not in "0123456789abcdef" for x in sha):
            raise ValueError("evidence review requires hashed search receipts")
        datetime.fromisoformat(record["searched_at"])
        if record.get("result") not in {"not_found", "does_not_bind_original_contract"}:
            raise ValueError("evidence inventory does not support unrecoverability")
        receipt = record.get("receipt")
        if not isinstance(receipt, dict) or digest(receipt) != sha:
            raise ValueError("evidence review requires retained, hash-matching search receipts")
        for key in ("source_ref", "finding", "searched_at", "kind", "result"):
            if receipt.get(key) != record.get(key):
                raise ValueError("search receipt metadata mismatch")
        if receipt.get("scope_id") != item["scope_id"] or receipt.get("original_payload_sha256") != item["original_payload_sha256"]:
            raise ValueError("search receipt original scope mismatch")
    if not {"original_generation_inputs", "historical_source_archive"} <= kinds:
        raise ValueError("evidence review lacks original inputs or historical archive search")


def _preview(conn, request=None, moment=None):
    from market_evidence_policy import completed_evidence_session
    from two_week_market_eligibility import completed_session

    row = conn.execute("SELECT manifest_json,manifest_sha256,active FROM trade_evidence_revision_batches_v1 WHERE batch_id=?", (BATCH_ID,)).fetchone()
    if row is None:
        raise ValueError("fixed legacy76 batch not found")
    manifest = json.loads(row[0])
    scopes = manifest["rows"]
    if row[1] != MANIFEST_SHA256 or digest(manifest) != MANIFEST_SHA256 or len(scopes) != 76 or len({s["scope_id"] for s in scopes}) != 76:
        raise ValueError("fixed 76-row manifest/hash mismatch")
    latest = {}
    for revision in conn.execute("SELECT revision_id,scope_id,as_of_session,state,payload_json,created_at FROM trade_evidence_revisions_v1 WHERE batch_id=? ORDER BY created_at,rowid", (BATCH_ID,)):
        latest[revision[1]] = revision
    active = active_for_connection(conn, BATCH_ID)
    unscored = []
    trading_terminal = 0
    for scope in scopes:
        rev = latest.get(scope["scope_id"])
        if rev and rev[3] in TRADING_TERMINAL:
            if scope["scope_id"] in active:
                raise ValueError("disposition conflicts with a trading terminal result")
            trading_terminal += 1
            continue
        payload = json.loads(rev[4]) if rev else {}
        snapshot = payload.get("report_snapshot", {})
        data = snapshot.get("data", {})
        plan = snapshot.get("rerun_context", {}).get("parsed", {}).get("trade_setup", {})
        earliest = conn.execute("SELECT revision_id,payload_json FROM trade_evidence_revisions_v1 WHERE batch_id=? AND scope_id=? ORDER BY created_at,rowid LIMIT 1", (BATCH_ID, scope["scope_id"])).fetchone()
        earliest_payload = json.loads(earliest[1]) if earliest else {}
        earliest_snapshot = earliest_payload.get("report_snapshot", {})
        earliest_plan = earliest_snapshot.get("rerun_context", {}).get("parsed", {}).get("trade_setup", {})
        grid = grid_assessment(data, plan)
        original_grid = grid_assessment(earliest_snapshot.get("data", {}), earliest_plan)
        off_grid = (bool(plan) and earliest_plan == plan and bool(grid["invalid_levels"])
                    and grid["status"] == "off_grid_analysis_levels" and original_grid["invalid_levels"] == grid["invalid_levels"])
        binding = {"scope_id": scope["scope_id"], "revision_id": rev[0] if rev else None,
                   "revision_payload_sha256": hashlib.sha256(rev[4].encode()).hexdigest() if rev else None,
                   "original_payload_sha256": scope["original_payload_sha256"], "manifest_sha256": MANIFEST_SHA256,
                   "earliest_revision_id": earliest[0] if earliest else None, "earliest_plan_sha256": digest(earliest_plan) if earliest else None}
        unscored.append({"ticker": scope["ticker"], "report_filename": scope["report_filename"],
                         "maturity_date": scope["maturity_date"], "latest_revision_created_at": rev[5] if rev else None,
                         "revision_evidence_session": rev[2] if rev else None,
                         "recorded_reason": payload.get("metrics", {}).get("reason"),
                         "suggested_action": "review_close_unscored" if off_grid else "review_required",
                         "suggested_reason": "invalid_original_price_grid" if off_grid else "original_evidence_review_required",
                         "invalid_original_levels": grid["invalid_levels"], "price_grid_source": grid["source"],
                         "original_plan_review": {"earliest_snapshot_raw_sha256": earliest_payload.get("report_snapshot_raw_sha256"),
                                                  "same_earliest_and_latest_plan": bool(plan) and plan == earliest_plan,
                                                  "historical_point_in_time_verified": False},
                         "missing_original_fields": [k for k, value in {
                             "quote_type": data.get("quote_type"), "instrument_type_source": data.get("instrument_type_source"),
                             "price_basis": plan.get("price_basis") or data.get("daily_market_data", {}).get("price_adjustment_basis")}.items() if not value],
                         "source_admission": payload.get("source_admission", {}),
                         "request_binding": binding, "disposition": active.get(scope["scope_id"]),
                         "outcome": None, "strategy_roi_pct": None, "strategy_validated": False})
    if request is not None:
        _review_request(request)
        if not row[2]:
            raise ValueError("inactive batch cannot accept a disposition")
        candidates = {s["request_binding"]["scope_id"]: s for s in unscored}
        for item in request["items"]:
            if set(item) - {*BINDING_KEYS, "action", "reason", "reopens_event_id", "evidence_review"}:
                raise ValueError("unexpected disposition item fields")
            candidate = candidates.get(item.get("scope_id"))
            if candidate is None or any(item.get(k) != candidate["request_binding"][k] for k in BINDING_KEYS) or not item.get("revision_id"):
                raise ValueError("scope/revision binding changed or outside unscored cohort")
            scope = next(s for s in scopes if s["scope_id"] == item["scope_id"])
            original = conn.execute("SELECT payload_json FROM trade_evaluation_results_v1 WHERE report_filename=?", (scope["report_filename"],)).fetchall()
            # Other horizons may exist; exact frozen payload must still be present.
            if not any(digest(json.loads(r[0])) == item["original_payload_sha256"] for r in original):
                raise ValueError("frozen original result changed or missing")
            if item["action"] == "reopen":
                if item.get("reason") != "review_reopened" or not candidate["disposition"] or item.get("reopens_event_id") != candidate["disposition"]["event_id"]:
                    raise ValueError("reopen must reference the active disposition event")
            elif item["action"] == "close_unscored":
                if candidate["disposition"]:
                    raise ValueError("scope already disposed; explicitly reopen before a new decision")
                if item["reason"] == "invalid_original_price_grid":
                    if candidate["suggested_reason"] != "invalid_original_price_grid":
                        raise ValueError("original price grid does not support this closure")
                elif item["reason"] == "unrecoverable_original_evidence":
                    _unrecoverability_review(item)
                else:
                    raise ValueError("unsupported unscored disposition reason")
            else:
                raise ValueError("disposition cannot set a trade outcome or validated state")
    now = moment or datetime.now(ZoneInfo("Asia/Taipei"))
    result = {"schema_version": "legacy76-disposition-preview:v1", "batch_id": BATCH_ID,
              "manifest_sha256": MANIFEST_SHA256, "batch_active": bool(row[2]), "approved_scope_count": 76,
              "existing_revision_count": conn.execute("SELECT count(*) FROM trade_evidence_revisions_v1 WHERE batch_id=?", (BATCH_ID,)).fetchone()[0],
              "trading_terminal_scope_count": trading_terminal, "unscored_disposition_scope_count": len(active),
              "remaining_scope_count": 76 - trading_terminal - len(active), "unscored_scopes": unscored,
              "completed_market_session": completed_session(now), "evidence_session": completed_evidence_session(now),
              "evidence_session_policy": "Asia/Taipei 22:30 acquisition boundary;not source finality",
              "review_request": request, "approval_required_before_apply": True,
              "original_rows_modified": 0, "report_artifacts_modified": 0, "existing_revisions_modified": 0,
              "performance_substitution": False, "validated_strategy_results": 0, "limitations": LIMITATIONS}
    result["preview_sha256"] = digest(result)
    return result


def preview(path, *, request=None, moment=None):
    with closing(_connect(path)) as conn:
        conn.execute("BEGIN")
        return _preview(conn, request, moment)


def _event_body(request, item, preview_sha):
    return {"schema_version": "legacy76-disposition-event:v1", "request": request,
            "item": item, "basis_preview_sha256": preview_sha, "outcome": None,
            "strategy_validated": False, "performance_substitution": False}


def _already_applied(conn, ids, bodies):
    if _table_exists(conn) and all(conn.execute(f"SELECT payload_json FROM {TABLE} WHERE event_id=?", (eid,)).fetchone() == (encoded(body),) for eid, body in zip(ids, bodies)):
        active_for_connection(conn, BATCH_ID)
        return True
    return False


def apply(path, request, *, expected_preview_sha256, moment=None):
    """Explicit journal-only write, guarded by the reviewed preview fingerprint."""
    _review_request(request)
    bodies = [_event_body(request, item, expected_preview_sha256) for item in request["items"]]
    ids = [digest(body) for body in bodies]
    with closing(_connect(path)) as conn:
        if _already_applied(conn, ids, bodies):
            return {"already_applied": True, "appended_events": 0, "event_ids": ids}
    checked = preview(path, request=request, moment=moment)
    if checked["preview_sha256"] != expected_preview_sha256:
        raise ValueError("preview changed; review a fresh preview before apply")
    with closing(_connect(path, write=True)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        # A concurrent identical request may have committed after the RO preview.
        if _already_applied(conn, ids, bodies):
            return {"already_applied": True, "appended_events": 0, "event_ids": ids}
        if _preview(conn, request, moment)["preview_sha256"] != expected_preview_sha256:
            raise ValueError("preview changed during apply")
        conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,batch_id TEXT NOT NULL,scope_id TEXT NOT NULL,action TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL)")
        at = (moment or datetime.now(timezone.utc)).isoformat()
        for item, body, eid in zip(request["items"], bodies, ids):
            conn.execute(f"INSERT INTO {TABLE}(event_id,batch_id,scope_id,action,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                         (eid, BATCH_ID, item["scope_id"], item["action"], encoded(body), at))
    return {"already_applied": False, "appended_events": len(ids), "event_ids": ids,
            "original_rows_modified": 0, "existing_revisions_modified": 0, "performance_substitution": False}
