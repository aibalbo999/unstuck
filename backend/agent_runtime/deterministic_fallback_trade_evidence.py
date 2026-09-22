"""Attribute local no-trade policy without inventing provider or source success."""

from workflow_trade_evidence import trade_input_fingerprint, trade_manifest_matches_input

from .deterministic_fallback_mode_contracts import event_swing_fallback


def attributed_event_swing_fallback(data, context):
    structured = event_swing_fallback()
    assessment = {
        "status": "degraded",
        "origin": "local_deterministic_fallback",
        "reason_codes": ["deterministic_fallback", "source_evidence_unverified"],
        "source_binding": "unknown",
        "output_completion": {
            "status": "local_fallback",
            "basis": "deterministic_no_trade_policy",
            "provider_finish_observed": False,
            "finish_reasons": [],
        },
    }
    manifest = context.get("_trade_source_manifest")
    if (trade_manifest_matches_input(manifest, data)
            and trade_input_fingerprint(data) == trade_input_fingerprint(context.get("data", {}))):
        # This retains the actual prompt receipt, not proof that the local policy
        # cites its contents. All reference lists stay empty and status degraded.
        assessment["source_binding"] = "prompt_manifest_only"
        assessment["source_fingerprint"] = manifest["fingerprint"]
    else:
        # The renderer must not preserve a different attempt's manifest as this
        # fallback's input evidence, even when called without a graph round-trip.
        context.pop("_trade_source_manifest", None)
    # A previous model attempt's STOP/MAX_TOKENS never describes local output.
    context.pop("_trade_completion_receipt", None)
    structured["source_assessment"] = assessment
    return structured
