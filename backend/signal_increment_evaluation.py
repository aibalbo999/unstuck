"""Offline, prespecified descriptive holdout comparisons; no fabricated features."""
from collections import defaultdict, Counter
from datetime import date, datetime
from statistics import mean
from backtest_session_contract import session_window

POLICY_ID = "tw_signal_increment.v1"
REQUIRED = ("ticker", "signal_date", "available_at", "entry_at", "window_end", "industry", "size_bin", "momentum_bin",
            "flow_pct", "bias_pct", "net_return_pct", "control_net_return_pct", "source_provenance", "policy_id", "control", "policy_registered_at")


def validation_manifest():
    return {"policy_id": POLICY_ID, "status": "not_validated", "required_fields": list(REQUIRED),
            "primary_horizon": 10, "training_use": "historical coverage only;thresholds frozen at zero before holdout",
            "groups": ["positive/negative_bias", "positive/nonpositive_foreign_trust_flow"],
            "matching": "controls supplied for same industry,size_bin,momentum_bin and entry/window;not auto-invented",
            "split": "caller fixed cutoff;10 verified trading session embargo;nonoverlap within ticker",
            "interpretation": "Descriptive net return minus supplied matched controls;not causal evidence, significance, or proof of profitability.",
            "historical_feature_coverage": "not_established;current screener metrics must not fill historical missing features"}


def evaluate_increment(rows, *, cutoff):
    manifest = validation_manifest()
    try:
        cutoff_day = date.fromisoformat(cutoff)
        embargo = session_window(cutoff_day, 10)
        if embargo["status"] != "verified":
            return {**manifest, "status": "unavailable", "reason": "embargo_calendar_unavailable"}
    except (ValueError, TypeError):
        return {**manifest, "status": "unavailable", "reason": "invalid_fixed_cutoff"}
    rejected, training, held, occupied = Counter(), [], [], {}
    for row in sorted(rows, key=lambda r: (str(r.get("signal_date", "")), str(r.get("ticker", "")))):
        if any(row.get(key) is None or row.get(key) == "" for key in REQUIRED):
            rejected["missing_historical_feature_or_provenance"] += 1; continue
        try:
            signal = date.fromisoformat(row["signal_date"])
            available, entry = datetime.fromisoformat(row["available_at"]), datetime.fromisoformat(row["entry_at"])
            window = session_window(signal, 10)
            numeric = [float(row[key]) for key in ("flow_pct", "bias_pct", "net_return_pct", "control_net_return_pct")]
            import math
            if not all(math.isfinite(x) for x in numeric): raise ValueError
            if row["policy_id"] != POLICY_ID or not row["source_provenance"]: raise ValueError
            registered = datetime.fromisoformat(row["policy_registered_at"])
            if registered.tzinfo is None or registered.date() > cutoff_day: raise ValueError
            control = row["control"]
            if any(control.get(key) != row[key] for key in ("industry", "size_bin", "momentum_bin", "entry_at", "window_end")): raise ValueError
            if available.tzinfo is None or entry.tzinfo is None or available > entry: raise ValueError
            if window["status"] != "verified" or row["window_end"] != window["maturity_date"]: raise ValueError
            if entry.date() <= signal or entry.date().isoformat() > window["maturity_date"]: raise ValueError
        except (ValueError, TypeError, KeyError):
            rejected["invalid_time_window_numeric_or_policy"] += 1; continue
        if row["window_end"] <= cutoff:
            training.append(row); continue
        if row["signal_date"] <= embargo["maturity_date"]:
            rejected["embargo_or_cross_split_window"] += 1; continue
        ticker = row["ticker"]
        if row["signal_date"] <= occupied.get(ticker, ""):
            rejected["overlapping_ticker_window"] += 1; continue
        occupied[ticker] = row["window_end"]
        held.append(row)
    if not training or not held:
        return {**manifest, "status": "unavailable", "reason": "missing_training_or_holdout_coverage", "rejected_counts": dict(rejected), "training_count": len(training), "holdout_count": len(held)}
    groups = defaultdict(list)
    for row in held:
        strata = (row["industry"], row["size_bin"], row["momentum_bin"])
        for factor, group in (("bias", "positive" if float(row["bias_pct"]) > 0 else "negative_or_zero"),
                              ("flow", "positive" if float(row["flow_pct"]) > 0 else "nonpositive")):
            groups[(factor, group, *strata)].append(float(row["net_return_pct"]) - float(row["control_net_return_pct"]))
    return {**manifest, "status": "descriptive_holdout_only", "cutoff": cutoff, "embargo_end": embargo["maturity_date"],
            "training_count": len(training), "holdout_count": len(held), "rejected_counts": dict(rejected),
            "groups": [{"factor": key[0], "group": key[1], "industry": key[2], "size_bin": key[3], "momentum_bin": key[4],
                        "count": len(values), "mean_net_excess_pct": round(mean(values), 4)} for key, values in sorted(groups.items())],
            "causal_effect_established": False, "statistical_significance_established": False,
            "limitation": "Provided provenance and controls are not independently authenticated;cross-stock correlation and multiple comparisons remain."}
