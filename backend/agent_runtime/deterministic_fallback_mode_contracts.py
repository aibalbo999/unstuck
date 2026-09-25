"""Mode-specific payloads for deterministic structured fallbacks."""


def event_swing_fallback() -> dict[str, object]:
    return {
        "trade_direction": "Neutral",
        "entry_zone": "N/A",
        "target_price": "N/A",
        "stop_loss": "N/A",
        "support_level": "N/A",
        "resistance_level": "N/A",
        "core_catalyst": "等待可驗證事件與技術、籌碼同步確認後再重新評估",
        "observed_signal": None,
        "observed_source_refs": [],
        "event_catalyst": None,
        "recheck_condition": "等待可驗證事件與技術、籌碼同步確認後再重新評估",
        "financial_risk_flags": [],
        "risk_level": "High",
        "support_source_refs": [],
        "resistance_source_refs": [],
        "catalyst_source_refs": [],
    }


def short_setup_fallback() -> dict[str, str]:
    return {
        "entry_trigger": "等待後續財測、毛利率與估值證據確認後重新評估；目前觀望，不開倉。",
        "downside_target": "資料不足，需重新產生可驗證下行目標",
        "cover_stop": "不適用，目前不建立空方部位。",
        "squeeze_risk": "借券與空單資料不足，禁止建立積極空方部位",
        "thesis_invalidation": "若後續財報或財測顯示基本面改善，須重新評估目前估值及原先的空方假設。",
    }


def position_plan_fallback(context=None) -> dict[str, object]:
    from position_sizing import calculate_position_sizing
    from position_sizing_runtime import trusted_sizing_context

    plan = {
        "action": "等待",
        "entry_zone": "N/A",
        "position_size": "0%",
        "stop_loss": "N/A",
        "risk_reward": "N/A",
        "target_price": None,
        "transaction_cost": None,
        "horizon_trading_days": None,
        "planning_context": "unassessed",
        "invalidation_condition": "等待可驗證財報、估值與風險預算後重新評估；目前不新增部位，不推定使用者實際持倉。",
    }
    plan["sizing_evidence"] = calculate_position_sizing(plan, trusted_sizing_context(context or {}))
    return plan


__all__ = ["event_swing_fallback", "position_plan_fallback", "short_setup_fallback"]
