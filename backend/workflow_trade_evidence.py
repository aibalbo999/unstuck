"""Carry successful Agent 24 prompt evidence without rebuilding its source catalog."""

from copy import deepcopy
import hashlib
import json

from analysis_dependencies import agent_value, is_agent_result_current, output_fingerprint, upstream_input_hash
from data_trust_snapshot_sanitizer import sanitize_for_snapshot


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def trade_input_fingerprint(data):
    """Identity of the actual data present when the source prompt was built."""
    try:
        return _digest(sanitize_for_snapshot(data))
    except (TypeError, ValueError, RecursionError):
        return ""


def trade_manifest_matches_input(manifest, data):
    from trade_source_contract import SUPPORTED_VERSIONS
    try:
        identity = trade_input_fingerprint(data)
        return bool(identity and isinstance(manifest, dict) and manifest.get("visible") is True
            and manifest.get("version") in SUPPORTED_VERSIONS
            and manifest.get("input_fingerprint") == identity
            and isinstance(manifest.get("catalog"), dict) and manifest["catalog"]
            and manifest.get("fingerprint") == _digest(manifest["catalog"]))
    except (TypeError, ValueError, RecursionError):
        return False


def successful_trade_evidence(context):
    """Only called after a successful node/audit; an absent receipt stays absent."""
    from agent_runtime.routing import is_agent_execution_failure

    manifest = context.get("_trade_source_manifest")
    text = agent_value(context, "analyses", 24, "")
    output = agent_value(context, "structured_outputs", 24)
    if (context.get("pipeline_id") != "v4" or not isinstance(manifest, dict)
            or not isinstance(text, str) or not text.strip() or is_agent_execution_failure(text)
            or not isinstance(output, dict) or not output or not is_agent_result_current(24, context)):
        return {}
    try:
        data_identity = trade_input_fingerprint(context.get("data", {}))
        assessment = output.get("source_assessment")
        if (not trade_manifest_matches_input(manifest, context.get("data", {}))
                or not isinstance(assessment, dict)
                or assessment.get("source_fingerprint") != manifest.get("fingerprint")):
            return {}
        return {"schema_version": 1, "input_fingerprint": data_identity,
                "upstream_fingerprint": upstream_input_hash(24, context),
                "output_fingerprint": output_fingerprint(24, context),
                "manifest": deepcopy(manifest)}
    except (TypeError, ValueError, RecursionError):
        return {}


def restore_trade_evidence(context, saved):
    """Restore only the saved prompt bound to unchanged input and successful output."""
    if not isinstance(saved, dict) or not saved:
        return
    candidate = {**context, "_trade_source_manifest": saved.get("manifest")}
    if successful_trade_evidence(candidate) == saved:
        context["_trade_source_manifest"] = deepcopy(saved["manifest"])
