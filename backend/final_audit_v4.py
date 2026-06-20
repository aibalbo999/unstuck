"""Pipeline v4 trade setup contract checks."""

from __future__ import annotations


REQUIRED_TRADE_SETUP_FIELDS = {
    "trade_direction",
    "entry_zone",
    "target_price",
    "stop_loss",
    "core_catalyst",
    "risk_level",
}


def v4_trade_setup_contract_issues(trade_setup: dict) -> list[str]:
    issues = []
    missing = sorted(
        key for key in REQUIRED_TRADE_SETUP_FIELDS if not str(trade_setup.get(key, "")).strip()
    )
    if missing:
        issues.append(f"缺少極短線交易欄位：{', '.join(missing)}")
    if trade_setup.get("trade_direction") not in {"Long", "Short", "Neutral"}:
        issues.append(f"trade_direction 不在允許值內：{trade_setup.get('trade_direction') or '空白'}")
    if trade_setup.get("risk_level") not in {"High", "Medium", "Low"}:
        issues.append(f"risk_level 不在允許值內：{trade_setup.get('risk_level') or '空白'}")
    return issues
