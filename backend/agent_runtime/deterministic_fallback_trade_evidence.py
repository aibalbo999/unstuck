"""Attribute local no-trade policy without inventing provider or source success."""

from workflow_trade_evidence import trade_input_fingerprint, trade_manifest_matches_input
from trade_financial_risk import enforce_trade_financial_risk

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
        # cites its contents. Execution reference lists stay empty and status degraded.
        assessment["source_binding"] = "prompt_manifest_only"
        assessment["source_fingerprint"] = manifest["fingerprint"]
        # Local facts are observations, never a replacement model conclusion.
        # source_fact_cards probes each sentence against the same source gate.
        from trade_source_guidance import source_fact_cards
        cards = source_fact_cards(manifest["catalog"])
        selected = [card for card in cards if ".institutional_evidence.records[" in card["ref"]][:2]
        selected += [card for card in cards if ".technical_indicators." in card["ref"]][:2]
        if selected:
            structured["observed_signal"] = "；".join(card["fact"] for card in selected)
            structured["observed_source_refs"] = [card["ref"] for card in selected]
            structured["recheck_condition"] = (
                "本次為本機備援，未完成模型結論；上述日期的單筆觀測不證明兩週上漲或已確認事件。"
                "需核對各来源最新版本、補齊有日期與來源的兩週催化事件，並重新驗證價格口徑與風險後再評估。"
            )
    else:
        # The renderer must not preserve a different attempt's manifest as this
        # fallback's input evidence, even when called without a graph round-trip.
        context.pop("_trade_source_manifest", None)
    # A previous model attempt's STOP/MAX_TOKENS never describes local output.
    context.pop("_trade_completion_receipt", None)
    structured["source_assessment"] = assessment
    return enforce_trade_financial_risk(structured, data)
