"""Descriptive coverage for stored outcomes; no inference about strategy skill."""
from collections import Counter


def sample_context(rows):
    scored = [row for row in rows if row.get("outcome") in {"hit", "miss"}]
    hits = sum(row.get("outcome") == "hit" for row in scored)
    reasons = Counter(str(row.get("reason") or row.get("status") or "reason_not_recorded")
                      for row in rows if row.get("outcome") not in {"hit", "miss"})
    def dates(key):
        values = sorted({str(row[key])[:10] for row in rows if row.get(key)})
        return {"start": values[0], "end": values[-1]} if values else {"start": None, "end": None}
    horizons = sorted({str(row["horizon_trading_days"]) for row in rows if row.get("horizon_trading_days")})
    months = sorted({str(row["horizon_months"]) for row in rows if row.get("horizon_months")})
    cost_known = sum(row.get("transaction_cost") is not None for row in scored)
    return {
        "scored_count": len(scored), "stored_result_count": len(rows),
        "descriptive_hit_ratio_pct": round(hits / len(scored) * 100, 2) if scored else None,
        "headline_hit_rate_pct": None,
        "sample_status": "no_scored_results" if not scored else "insufficient_sample" if len(scored) == 1 else "descriptive_only",
        "interpretation": "描述性已評分樣本比率；不代表策略勝率或統計顯著性。",
        "unscored_reason_counts": dict(sorted(reasons.items())),
        "observation_window": {"horizon_trading_days": horizons, "horizon_months": months,
                               "generated_dates": dates("generated_date"), "evaluation_dates": dates("evaluation_date"),
                               "basis": "stored_results_only", "trade_maturity_rule": "報告日後觀察到完整N根每日行情，v4分別N=5、10；非曆日兩週，未驗證完整交易所日曆覆蓋。", "pending_unstored_count": None,
                               "pending_coverage": "未成熟結果可能尚未保存；不能由此總數推算全部待到期報告。"},
        "cost_coverage": {"scored_cost_recorded": cost_known, "scored_cost_unknown": len(scored) - cost_known,
                          "hit_basis": "stored_outcome_definition", "return_basis": "gross_price_return",
                          "trade_hit_definition": "毛價格報酬大於零；不是淨報酬勝率或必然達目標。",
                          "limitations": "交易命中依毛價格報酬判定；成本未知不能當成零，月度命中使用另一套方向與目標定義。"},
    }
