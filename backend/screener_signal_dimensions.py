"""Separate observed signal dimensions; no cross-unit bullish probability score."""
import math


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def separate_signals(candidate):
    from screener_security_identity import guard_candidate
    row = guard_candidate(candidate)
    metrics = dict(row.get("metrics") or {})
    foreign, trust = number(metrics.get("foreign_net_buy_shares")), number(metrics.get("investment_trust_net_buy_shares"))
    volume = number(metrics.get("latest_volume"))
    ratio = (foreign + trust) / volume * 100 if foreign is not None and trust is not None and volume and volume > 0 and metrics.get("flow_observation_date") and metrics.get("flow_observation_date") == metrics.get("volume_observation_date") else None
    metrics["normalized_flow_pct"] = ratio
    bias = number(metrics.get("bias_pct"))
    row.update(legacy_score=row.get("legacy_score", row.get("score")), score=None, metrics=metrics,
               ranking_status="separate_dimensions_not_calibrated", research_only=True, actionable=False,
               signal_dimensions={"foreign_trust_net_buy_pct_of_volume": ratio,
                                  "flow_scope": "foreign_plus_investment_trust;dealer excluded",
                                  "flow_evidence": "same_session_observations" if ratio is not None else "missing_same_session_volume_or_flow",
                                  "bias_pct": bias, "bias_direction": "positive" if bias is not None and bias > 0 else "negative" if bias is not None and bias < 0 else "flat" if bias == 0 else "unknown",
                                  "volume_ratio": number(metrics.get("volume_ratio")),
                                  "interpretation": "Separate observational dimensions; normalized flow is not causal evidence or an upward probability."})
    return row
