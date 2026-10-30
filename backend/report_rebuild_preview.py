"""Read-only, hash-bound rebuild planning; this module never runs a model or job."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from market_session_admission import assess_daily_session_integrity
from report_artifacts import ReportArtifactLocator
from report_index_parsing import is_safe_report_filename, parse_report_filename


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def assert_rebuild_identity(data, *, pipeline_id, ticker=None):
    """Bind provider/input identity before any reacquisition or checkpoint work."""
    from fastapi import HTTPException
    actual = str(data.get("ticker") or "").upper()
    ticker = str(ticker or actual).upper()
    if pipeline_id != "v4" or not ticker.endswith((".TW", ".TWO")):
        return None
    if actual != ticker:
        raise HTTPException(status_code=409, detail={"code": "rebuild_input_identity_unbound",
            "message": "資料身分缺漏或與來源報告不符，不能重用或重建。"})
    return ticker


def assert_session_inputs(data, *, pipeline_id, ticker=None):
    """Never reuse invalid TW session evidence for final-only/full/resumed reruns."""
    from fastapi import HTTPException
    ticker = assert_rebuild_identity(data, pipeline_id=pipeline_id, ticker=ticker)
    if ticker is None:
        return
    admission = assess_daily_session_integrity(data.get("daily_market_data"), ticker=ticker)
    if not admission["eligible"]:
        raise HTTPException(status_code=409, detail={
            "code": "rebuild_session_inputs_unadmitted",
            "message": "交易日序列未通過准入；需取得完整來源並完整重建，不能重用舊指標或只重跑結論。",
            "session_admission": admission,
        })


class ReadOnlyArtifactStorage:
    """No mkdir, lockfile, persistence, database or service initialization."""
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Artifact root must be an existing directory")

    def _path(self, key):
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe artifact key")
        path = self.root / relative
        if any(part.is_symlink() for part in [path, *path.parents] if part != self.root.parent):
            raise ValueError("Symlinked artifacts are not admitted")
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Artifact path escapes root")
        return path

    def exists(self, key):
        return self._path(key).is_file()

    def get_report(self, key):
        path = self._path(key)
        if not path.is_file():
            return None
        return SimpleNamespace(content=path.read_bytes())


def read_saved_bundle(output_dir, filename):
    if not is_safe_report_filename(filename, ".html"):
        raise ValueError("Invalid report filename")
    storage = ReadOnlyArtifactStorage(output_dir)
    bundle = ReportArtifactLocator(storage).require_bundle(filename)
    keys = {"html": bundle.html_key, "md": bundle.markdown_key, "data": bundle.data_key}
    payloads = {kind: storage.get_report(key).content for kind, key in keys.items()}
    snapshot = json.loads(payloads["data"])
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be an object")
    return snapshot, {kind: hashlib.sha256(value).hexdigest() for kind, value in payloads.items()}


def build_rebuild_preview(snapshot, *, filename, artifact_hashes, evaluated_at):
    """Return a proposal and in-memory counterfactual; never approve publication."""
    if evaluated_at.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    identity = parse_report_filename(filename)
    data = snapshot.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("Snapshot data must be an object")
    ticker = str(snapshot.get("ticker") or data.get("ticker") or "").upper()
    pipeline = snapshot.get("pipeline") or (snapshot.get("rerun_context") or {}).get("pipeline_id")
    if not is_safe_report_filename(filename, ".html") or not ticker or not pipeline:
        raise ValueError("Unbound report identity")
    if identity.get("ticker") != ticker or identity.get("pipeline_id") != pipeline or data.get("ticker") != ticker:
        raise ValueError("Report, snapshot and input identities must agree")
    if set(artifact_hashes) != {"html", "md", "data"} or any(
        not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
        for v in artifact_hashes.values()
    ):
        raise ValueError("All three artifact hashes are required")
    daily = data.get("daily_market_data")
    daily = daily if isinstance(daily, dict) else {}
    admission = assess_daily_session_integrity(daily, ticker=ticker)
    from data_trust_snapshot_integrity import verify_data_snapshot_integrity
    integrity = verify_data_snapshot_integrity(snapshot)
    integrity_status = ("unverified" if not integrity.get("expected_hash") else
                        "verified" if integrity.get("valid") else "invalid")
    closed = set(admission.get("closed_dates") or [])
    filtered = deepcopy(daily)
    bars = filtered.get("bars")
    bars = bars if isinstance(bars, list) else []
    filtered["bars"] = [b for b in bars if not isinstance(b, dict) or not isinstance(b.get("date"), str) or b.get("date") not in closed]
    last = filtered["bars"][-1] if filtered["bars"] else None
    filtered["as_of"] = last.get("date") if isinstance(last, dict) else None
    filtered_admission = assess_daily_session_integrity(filtered, ticker=ticker)
    metric_names = ("sma_5", "sma_10", "sma_20", "rsi_14", "macd_histogram", "volume_ratio_20")
    comparison = {"diagnostic_only": True, "removed_closed_dates": sorted(closed),
                  "before_as_of": daily.get("as_of"), "after_as_of": filtered.get("as_of"),
                  "after_session_admission": filtered_admission,
                  "source_prices_verified": False, "conclusions_regenerated": False,
                  "preserved_open_zero_volume_dates": [b.get("date") for b in filtered["bars"] if isinstance(b, dict) and b.get("volume") == 0],
                  "metrics": {}}
    if closed and filtered_admission["eligible"]:
        from short_term_technical_indicators import calculate_technical_indicators
        before = calculate_technical_indicators(daily)
        after = calculate_technical_indicators(filtered)
        comparison["metrics"] = {key: {"before": before.get(key), "after": after.get(key)} for key in metric_names}
    reasons = list(admission["reason_codes"])
    if snapshot.get("refreshed_without_analysis_rerun") or snapshot.get("decision_validity_status") == "needs_rerun":
        reasons.append("saved_analysis_requires_full_rerun")
    plan = {
        "schema_version": "report_rebuild_preview.v1", "filename": filename,
        "ticker": ticker, "pipeline_id": pipeline, "evaluated_at": evaluated_at.isoformat(),
        "expires_at": (evaluated_at + timedelta(hours=2)).isoformat(),
        "artifact_sha256": dict(artifact_hashes), "snapshot_content_sha256": _digest(snapshot),
        "rebuild_reason_codes": sorted(set(reasons)), "session_admission": admission,
        "saved_snapshot_integrity": {"status": integrity_status, "errors": integrity.get("errors", []),
                                     "scope": "saved_content_consistency_not_source_factuality"},
        "requires_snapshot_integrity_review": integrity_status != "verified",
        "requires_fresh_acquisition": True, "requires_new_report_version": True,
        "required_scope": "full_report", "allowed_partial_scope": None,
        "preserve_original_artifacts": True, "preserve_fixed76": True,
        "execution_enabled": False, "publication_approved": False,
        "future_request": {"filename": filename, "scope": "full_report"},
        "required_before_execution": ["separate_execution_authorization", "unchanged_source_hashes",
                                      "reviewed_deployed_code", "fresh_complete_source_admission",
                                      "new_job_without_old_checkpoint", "new_unique_report_filename",
                                      "normal_quality_and_publication_gates"],
        "comparison": comparison,
    }
    plan["plan_sha256"] = _digest(plan)
    return plan


def validate_rebuild_preview(plan, snapshot, *, artifact_hashes, now):
    """Detect stale/tampered previews; success is NOT authorization to execute."""
    if now.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    original = dict(plan)
    expected = original.pop("plan_sha256", None)
    if expected != _digest(original):
        raise ValueError("Preview contents changed")
    evaluated = datetime.fromisoformat(plan["evaluated_at"])
    if not evaluated <= now <= datetime.fromisoformat(plan["expires_at"]):
        raise ValueError("Preview expired or evaluated in the future")
    if plan["artifact_sha256"] != artifact_hashes or plan["snapshot_content_sha256"] != _digest(snapshot):
        raise ValueError("Source artifacts changed; rebuild the preview")
    current = assess_daily_session_integrity((snapshot.get("data") or {}).get("daily_market_data"), ticker=plan["ticker"])
    if current != plan["session_admission"]:
        raise ValueError("Calendar/admission changed; rebuild the preview")
    return {"preflight_passed": True, "execution_authorized": False, "execution_enabled": False}
