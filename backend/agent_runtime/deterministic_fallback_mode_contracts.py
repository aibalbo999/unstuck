"""Mode-specific payloads for deterministic structured fallbacks."""


def event_swing_fallback() -> dict[str, object]:
    return {
        "trade_direction": "Neutral",
        "entry_zone": "N/A",
        "target_price": "N/A",
        "stop_loss": "N/A",
        "support_level": "N/A",
        "resistance_level": "N/A",
        "core_catalyst": "資料不足，等待可驗證事件與技術、籌碼同步確認；目前維持觀望，暫不交易。",
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


def position_plan_fallback() -> dict[str, str]:
    return {
        "action": "等待",
        "entry_zone": "目前觀望，等待財報、籌碼與估值證據確認後重新評估；暫不交易。",
        "position_size": "0%，等待觸發",
        "stop_loss": "資料不足，暫不建立部位",
        "risk_reward": "資料不足",
        "invalidation_condition": "估值、籌碼或總經證據出現反向變化",
    }


__all__ = ["event_swing_fallback", "position_plan_fallback", "short_setup_fallback"]
