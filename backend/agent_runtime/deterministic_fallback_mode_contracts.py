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
        "entry_trigger": "後續財測下修、毛利率壓縮或估值均值回歸開始發生",
        "downside_target": "資料不足，需重新產生可驗證下行目標",
        "cover_stop": "股價放量突破前高且基本面證據同步改善",
        "squeeze_risk": "借券與空單資料不足，禁止建立積極空方部位",
        "thesis_invalidation": "基本面證據改善並重新支撐目前估值",
    }


def position_plan_fallback() -> dict[str, str]:
    return {
        "action": "等待",
        "entry_zone": "資料不足，等待可驗證進場條件",
        "position_size": "0%，等待觸發",
        "stop_loss": "資料不足，暫不建立部位",
        "risk_reward": "資料不足",
        "invalidation_condition": "估值、籌碼或總經證據出現反向變化",
    }


__all__ = ["event_swing_fallback", "position_plan_fallback", "short_setup_fallback"]
