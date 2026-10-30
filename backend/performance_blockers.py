"""Evidence-only partition of indexed slots; metadata absence is not price absence."""
from collections import Counter

EXECUTED = {"target_first", "stop_first", "horizon_exit"}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def net_eligible(row):
    old = _mapping(row.get("stored_result"))
    return (row.get("state") in EXECUTED
            and _mapping(old.get("session_contract")).get("status") == "verified"
            and _mapping(old.get("price_comparability")).get("status") == "verified"
            and _mapping(old.get("cost_evidence")).get("status") == "complete_declared_assumptions"
            and old.get("net_outcome") in {"hit", "miss"})


def blocker_summary(rows):
    partition, reasons, contracts = Counter(), Counter(), Counter()
    for row in rows:
        state, old = row.get("state"), _mapping(row.get("stored_result"))
        if state == "not_matured":
            bucket = "awaiting_maturity"
        elif state in {"matured_missing_result", "execution_plan_unavailable"}:
            bucket = "missing_result_or_plan"
        elif state in {"no_trade", "not_entered"}:
            bucket = "no_executed_position"
        elif state == "ambiguous":
            bucket = "intrabar_order_unknown"
        elif state == "evidence_quarantined":
            bucket = "price_or_session_evidence_quarantined"
            reasons[old.get("reason") or "evidence_contradiction"] += 1
        elif state == "insufficient_data":
            bucket = "stored_data_or_contract_failure"
            reasons[old.get("reason") or "reason_not_recorded"] += 1
        elif state in EXECUTED:
            bucket = "comparable_assumed_cost_net_result" if net_eligible(row) else "executed_result_unverified"
            for key, expected in (("session_contract", "verified"), ("price_comparability", "verified"),
                                  ("cost_evidence", "complete_declared_assumptions")):
                evidence = old.get(key)
                if not isinstance(evidence, dict) or not evidence:
                    contracts[key + ":metadata_not_saved"] += 1
                elif evidence.get("status") != expected:
                    contracts[key + ":" + str(evidence.get("reason") or evidence.get("status") or "unknown")] += 1
            if old.get("net_outcome") not in {"hit", "miss"}:
                contracts["net_outcome:not_recorded"] += 1
        else:
            bucket = "calendar_or_state_unavailable"
        partition[bucket] += 1
    return {"slot_count": len(rows), "partition": dict(sorted(partition.items())),
            "stored_failure_reasons": dict(sorted(reasons.items())),
            "executed_contract_blockers": dict(sorted(contracts.items())),
            "blocker_counts_overlap": True,
            "interpretation": "分區互斥且涵蓋全部觀察槽；合約缺口可重疊。未保存 metadata 不等於行情不存在；歷史結果不自動重算。",
            "data_vs_metadata": "Stored failure reasons describe recorded evidence only; raw bars are not retained in legacy results, so actual provider data absence cannot be inferred."}
