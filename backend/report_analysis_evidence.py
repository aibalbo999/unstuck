"""Bounded, immutable evidence for the analysis that produced a report.

This packet is historical evidence, never refreshed input or a freshness override.
Its digest detects accidental changes; it is not a signature or proof of provider
truth. Only a matching pre-analysis receipt identifies the frozen model input.
"""

from copy import deepcopy
import hashlib
import json
import re

from data_trust_snapshot_sanitizer import sanitize_for_snapshot


MAX_ANALYSIS_EVIDENCE_BYTES = 512 * 1024
_SECTION_NAMES = {"analysis_input", "quant_metrics", "render_quant_metrics", "market_context_manifests", "trade_source_manifest"}


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _hash(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) else ""


def _seal(packet):
    packet["packet_fingerprint"] = _digest(packet)
    return packet


def _unknown(reason):
    return _seal({"schema_version": 1, "status": "unknown", "capture_boundary": "unknown",
                  "input_verification": "unknown", "reason_codes": [reason], "sections": {}})


def validate_analysis_evidence(packet):
    """Return an independent copy, or explicit unknown; never repair from current data."""
    try:
        if not isinstance(packet, dict) or len(_encoded(packet)) > MAX_ANALYSIS_EVIDENCE_BYTES:
            return _unknown("invalid_analysis_evidence")
        if packet != sanitize_for_snapshot(packet):
            return _unknown("invalid_analysis_evidence")
        payload = {key: value for key, value in packet.items() if key != "packet_fingerprint"}
        if (packet.get("schema_version") != 1 or packet.get("status") not in {"preserved", "partial", "unknown"}
                or packet.get("packet_fingerprint") != _digest(payload)):
            return _unknown("invalid_analysis_evidence")
        sections = packet.get("sections")
        if not isinstance(sections, dict) or set(sections) - _SECTION_NAMES:
            return _unknown("invalid_analysis_evidence")
        for section in sections.values():
            if not isinstance(section, dict) or section.get("status") not in {"preserved", "omitted", "unknown"}:
                return _unknown("invalid_analysis_evidence")
            if section["status"] == "preserved" and ("data" not in section or section.get("fingerprint") != _digest(section["data"])):
                return _unknown("invalid_analysis_evidence")
        return deepcopy(packet)
    except (TypeError, ValueError, RecursionError):
        return _unknown("invalid_analysis_evidence")


def _capture_render_evidence(context, *, generated_at="", legacy=False):
    """Capture once at rendering, or bootstrap an unrefreshed, hash-proven legacy input.

    Rendering proves the origin of quant/manifests, not that later-enriched data
    still equals the pre-LLM input. Mismatched input is omitted, never relabeled.
    No analyses, prompts, runtime configuration, or recursive snapshots are copied.
    """
    try:
        raw_data = context.get("data")
        if not isinstance(raw_data, dict):
            return _unknown("original_analysis_input_unavailable")
        data = sanitize_for_snapshot(raw_data)
        data.pop("analysis_evidence", None)
        receipt = _hash(data.get("analysis_input_hash"))
        candidate = {key: value for key, value in data.items() if key not in {"analysis_input_hash", "analysis_input_cutoff"}}
        verified = bool(receipt and receipt == _digest(candidate))
        if legacy and not verified:
            return _unknown("legacy_original_input_unavailable")
        rerun = context.get("rerun_context") if isinstance(context.get("rerun_context"), dict) else {}
        from market_context_manifest import market_input_fingerprint

        market_identity = (_hash(context.get("market_context_original_input_fingerprint"))
                           or market_input_fingerprint(data))
        packet = {"schema_version": 1, "status": "preserved", "capture_boundary": "legacy_hash_verified" if legacy else "report_render",
                  "original_generated_at": str(generated_at or context.get("generated_at") or "")[:128],
                  "analysis_input_hash": receipt, "analysis_input_cutoff": str(data.get("analysis_input_cutoff") or "")[:128],
                  "input_verification": "hash_verified" if verified else "unknown",
                  "market_context_original_input_fingerprint": market_identity,
                  "reason_codes": [], "sections": {}}
        values = {"quant_metrics": data.get("quant_metrics"),
                  "market_context_manifests": context.get("market_context_manifests", rerun.get("market_context_manifests")),
                  "trade_source_manifest": context.get("_trade_source_manifest", context.get("trade_source_manifest")),
                  "analysis_input": data if verified else None}
        for name, value in values.items():
            clean = sanitize_for_snapshot(value)
            if not isinstance(clean, dict) or not clean:
                packet["sections"][name] = {"status": "unknown"}
                if name == "analysis_input":
                    packet["status"] = "partial"
                    packet["reason_codes"].append("original_analysis_input_hash_unverified")
                continue
            section = {"status": "preserved", "fingerprint": _digest(clean), "data": clean}
            packet["sections"][name] = section
            # Leave bounded space for the remaining metadata and final digest.
            if len(_encoded(packet)) > MAX_ANALYSIS_EVIDENCE_BYTES - 4096:
                section.pop("data")
                section["status"] = "omitted"
                packet["status"] = "partial"
                packet["reason_codes"].append(name + "_exceeds_evidence_budget")
        return _seal(packet)
    except (TypeError, ValueError, RecursionError):
        return _unknown("original_analysis_evidence_not_serializable")


def freeze_input_evidence(data):
    """JSON string copied by existing workflow checkpoints, excluded from all prompts.

    Always recapture this run's input, never reuse an earlier private receipt.
    The sanitizer drops the private key before hashing/copying, preventing nesting.
    """
    packet = _capture_render_evidence({"data": data}, generated_at=data.get("analysis_input_cutoff", ""))
    packet.pop("packet_fingerprint", None)
    packet["capture_boundary"] = "analysis_start"
    return _encoded(_seal(packet)).decode("utf-8")


def capture_analysis_evidence(context, *, generated_at="", legacy=False):
    packet = _capture_render_evidence(context, generated_at=generated_at, legacy=legacy)
    raw_data = context.get("data")
    if legacy or not isinstance(raw_data, dict) or "_analysis_input_evidence" not in raw_data:
        return packet
    try:
        encoded = raw_data["_analysis_input_evidence"]
        if not isinstance(encoded, str) or len(encoded.encode("utf-8")) > MAX_ANALYSIS_EVIDENCE_BYTES:
            return _unknown("invalid_frozen_analysis_evidence")
        frozen = validate_analysis_evidence(json.loads(encoded))
        if (frozen.get("capture_boundary") != "analysis_start" or frozen.get("input_verification") != "hash_verified"
                or frozen.get("analysis_input_hash") != raw_data.get("analysis_input_hash")
                or frozen.get("analysis_input_cutoff") != raw_data.get("analysis_input_cutoff")):
            return _unknown("invalid_frozen_analysis_evidence")
        if packet["status"] == "unknown":
            return packet
        packet.pop("packet_fingerprint", None)
        render_quant = packet["sections"]["quant_metrics"]
        original_quant = frozen["sections"]["quant_metrics"]
        if render_quant != original_quant:
            packet["sections"]["render_quant_metrics"] = render_quant
        for name in ("analysis_input", "quant_metrics"):
            packet["sections"][name] = deepcopy(frozen["sections"][name])
        packet["input_verification"] = "hash_verified"
        packet["frozen_market_input_fingerprint"] = frozen["market_context_original_input_fingerprint"]
        packet["reason_codes"] = [reason for reason in packet["reason_codes"]
                                  if not reason.startswith(("original_analysis_input_", "analysis_input_", "quant_metrics_"))]
        packet["reason_codes"].extend(frozen["reason_codes"])
        # Newly generated manifests must not make the merged immutable packet unbounded.
        for name in ("analysis_input", "render_quant_metrics", "trade_source_manifest", "market_context_manifests", "quant_metrics"):
            if len(_encoded(packet)) <= MAX_ANALYSIS_EVIDENCE_BYTES - 4096:
                break
            section = packet["sections"].get(name, {})
            if "data" in section:
                section.pop("data")
                section["status"] = "omitted"
                packet["reason_codes"].append(name + "_exceeds_evidence_budget")
        packet["status"] = "partial" if packet["reason_codes"] else "preserved"
        return _seal(packet)
    except (TypeError, ValueError, RecursionError):
        return _unknown("invalid_frozen_analysis_evidence")


def preserve_analysis_evidence(snapshot):
    """Preserve a stored packet before refresh replaces the current data."""
    if "analysis_evidence" in snapshot:
        return validate_analysis_evidence(snapshot["analysis_evidence"])
    if any(snapshot.get(key) for key in ("snapshot_refreshed_at", "refreshed_from_report", "refreshed_without_analysis_rerun", "snapshot_truncated")):
        return _unknown("legacy_original_input_unavailable")
    from data_trust_snapshot_integrity import verify_data_snapshot_integrity

    if not verify_data_snapshot_integrity(snapshot)["valid"]:
        return _unknown("invalid_original_snapshot")
    return capture_analysis_evidence(snapshot, legacy=True)
