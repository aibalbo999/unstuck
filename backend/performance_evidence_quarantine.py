"""Read-only quarantine of demonstrably contradicted saved performance claims."""
from collections import Counter
from datetime import date
from backtest_session_contract import session_window

EXECUTED = {"target_first", "stop_first", "horizon_exit"}
DISPUTED_FILENAME = "2382_TW_v4_report_job_cce8792ca31a.html"
OFFICIAL_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=20260901&stockNo=2382&response=json"
OFFICIAL_SHA256 = "61924d4e86d9f022bb65acca5c836ffdc717e437b95fe5d70f67ee5614b0145d"


def project_results(rows):
    projected = []
    for old in rows:
        row = dict(old)
        reasons = []
        if row.get("status") in EXECUTED and str(row.get("ticker") or "").endswith((".TW", ".TWO")):
            try:
                window = session_window(date.fromisoformat(row["generated_date"]), row["horizon_trading_days"])
                if window["status"] == "verified":
                    for key in ("entry_date", "exit_date"):
                        if row.get(key) and row[key] not in window["sessions"]:
                            reasons.append(key + "_outside_verified_sessions")
                    if row["status"] == "horizon_exit" and row.get("exit_date") and row["exit_date"] != window["maturity_date"]:
                        reasons.append("horizon_exit_not_at_verified_maturity")
            except (KeyError, TypeError, ValueError):
                pass  # Unknown context is not fabricated into a proved contradiction.
            if (row.get("report_filename") == DISPUTED_FILENAME and row.get("horizon_trading_days") == 10
                    and row.get("exit_date") == "2026-09-18" and row.get("exit_price") == 344):
                reasons.append("saved_exit_price_contradicts_official_close")
                row["official_price_dispute"] = {"url":OFFICIAL_URL,"raw_sha256":OFFICIAL_SHA256,
                    "date":"2026-09-18","saved_exit_price":344,"official_close":343,
                    "cause":"source_or_date_alignment_unresolved;arithmetic_correct;no_lookahead_proof"}
        if reasons:
            row.update(recorded_status=old.get("status"), recorded_outcome=old.get("outcome"),
                recorded_strategy_roi_pct=old.get("strategy_roi_pct"),status="evidence_quarantined",
                reason=";".join(reasons),outcome=None,strategy_roi_pct=None,net_strategy_roi_pct=None,
                net_outcome=None,performance_evidence_status="quarantined",quarantine_reasons=reasons,
                projection_scope="current_readonly_performance;original_saved_row_unchanged")
        projected.append(row)
    return projected


def quarantine_summary(rows):
    quarantined = [r for r in rows if r.get("performance_evidence_status") == "quarantined"]
    return {"quarantined_count":len(quarantined),"reason_counts":dict(Counter(reason for r in quarantined for reason in r.get("quarantine_reasons",[]))),
            "scope":"saved performance claims with proved price/session contradiction;read-only projection",
            "reason_counts_overlap":True,"original_rows_modified":0,
            "interpretation":"確證價格／交易日矛盾不進入當前毛／淨績效主張；原結果留存，不補成通過或改選另一版本。"}
