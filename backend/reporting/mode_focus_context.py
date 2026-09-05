"""Mode-specific decision values shared by HTML and Markdown reports."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from data_trust import normalize_data_trust, trust_status_label
from mapping_fields import safe_mapping_dict
from trade_price_inputs import optional_execution_text

from .decision_context import build_decision_context
from .html_context import display_text
from .html_sanitizer import sanitize_report_plain_text
from .target_price_text import target_price_text


def _text(value: Any, default: str = "資料不足") -> str:
    return sanitize_report_plain_text(display_text(value, default)) or default


def _score(value: Any) -> str:
    if isinstance(value, Real) and not isinstance(value, bool):
        number = float(value)
        if math.isfinite(number):
            return f"{number:g}/10"
    text = _text(value)
    return f"{text}/10" if text != "資料不足" else text


def _row(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": _text(value)}


def build_mode_focus_context(context: dict, parsed: dict, *, pipeline_id: str) -> dict[str, Any]:
    """Return one authoritative set of mode-specific focus rows."""
    parsed_map = safe_mapping_dict(parsed) or {}
    data = safe_mapping_dict(context.get("data")) or {}
    decision = build_decision_context(parsed_map, pipeline_id=pipeline_id)

    if pipeline_id == "v1":
        trust = normalize_data_trust(data.get("data_trust"))
        moat = safe_mapping_dict(parsed_map.get("moat_scores")) or {}
        targets = safe_mapping_dict(parsed_map.get("price_targets")) or {}
        base_target = target_price_text(targets.get("基本情境"))
        return {"rows": [
            _row("資料可信度", trust_status_label(trust.get("status", "unknown"))),
            _row("整體護城河", _score(moat.get("整體護城河"))),
            _row("基本情境估值", base_target),
            _row("最終建議", decision["rec_text"]),
        ]}

    if pipeline_id == "v2":
        plan = safe_mapping_dict(parsed_map.get("position_plan")) or {}
        return {"rows": [
            _row("部位動作", plan.get("action")),
            _row("進場區間", plan.get("entry_zone")),
            _row("部位大小", plan.get("position_size")),
            _row("停損條件", plan.get("stop_loss")),
            _row("同期間目標", _text(optional_execution_text(plan.get("target_price")), "未驗證")),
            _row("每股來回成本", _text(optional_execution_text(plan.get("transaction_cost")), "未估計")),
            _row("風險報酬", plan.get("risk_reward")),
            _row("失效條件", plan.get("invalidation_condition")),
        ]}

    if pipeline_id == "v3":
        setup = safe_mapping_dict(parsed_map.get("short_setup")) or {}
        return {"rows": [
            _row("空方結論", decision["rec_text"]),
            _row("做空觸發", setup.get("entry_trigger")),
            _row("下行目標", setup.get("downside_target")),
            _row("防軋空停損", setup.get("cover_stop")),
            _row("軋空風險", setup.get("squeeze_risk")),
            _row("論點失效", setup.get("thesis_invalidation")),
            _row("信心指數", decision["confidence"]),
        ]}

    setup = safe_mapping_dict(parsed_map.get("trade_setup")) or {}
    return {"rows": [
        _row("交易方向", decision["trade_direction_label"]),
        _row("進場區間", setup.get("entry_zone")),
        _row("1-2 週目標", setup.get("target_price")),
        _row("嚴格停損", setup.get("stop_loss")),
        _row("支撐位", setup.get("support_level")),
        _row("壓力位", setup.get("resistance_level")),
        _row("核心催化劑", setup.get("core_catalyst")),
        _row("波動風險", setup.get("risk_level")),
    ]}


__all__ = ["build_mode_focus_context"]
