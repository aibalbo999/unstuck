"""Markdown decision section helpers for generated reports."""

from __future__ import annotations

from typing import Any

from .decision_context import build_decision_context
from .mode_templates import decision_markdown_heading


def build_markdown_decision_section(parsed: dict[str, Any], *, pipeline_id: str, mode_template: dict[str, Any]) -> str:
    """Build the Markdown recommendation or trade setup section."""
    context = build_decision_context(parsed, pipeline_id=pipeline_id)
    decision_heading = decision_markdown_heading(mode_template)
    if pipeline_id == "v4":
        trade_setup = context["trade_setup"]
        return "\n".join([
            decision_heading,
            f"- **交易方向:** {context['trade_direction']}",
            f"- **進場區間:** {trade_setup.get('entry_zone', 'N/A')}",
            f"- **1-2週目標:** {trade_setup.get('target_price', 'N/A')}",
            f"- **嚴格停損:** {trade_setup.get('stop_loss', 'N/A')}",
            f"- **支撐位:** {trade_setup.get('support_level', 'N/A')}",
            f"- **壓力位:** {trade_setup.get('resistance_level', 'N/A')}",
            f"- **核心催化劑:** {trade_setup.get('core_catalyst', 'N/A')}",
            f"- **短期波動風險:** {trade_setup.get('risk_level', 'High')}",
        ])
    if pipeline_id == "v2" and context["position_plan"]:
        plan = context["position_plan"]
        return "\n".join([
            decision_heading,
            f"- **操作動作:** {plan.get('action', 'N/A')}",
            f"- **進場條件:** {plan.get('entry_zone', 'N/A')}",
            f"- **部位大小:** {plan.get('position_size', 'N/A')}",
            f"- **停損條件:** {plan.get('stop_loss', 'N/A')}",
            f"- **風險報酬:** {plan.get('risk_reward', 'N/A')}",
            f"- **假設失效:** {plan.get('invalidation_condition', 'N/A')}",
            f"- **信心指數:** {context['confidence']}",
        ])
    if pipeline_id == "v3" and context["short_setup"]:
        setup = context["short_setup"]
        return "\n".join([
            decision_heading,
            f"- **空方判斷:** {context['rec_text']}",
            f"- **做空觸發:** {setup.get('entry_trigger', 'N/A')}",
            f"- **下行目標:** {setup.get('downside_target', 'N/A')}",
            f"- **回補停損:** {setup.get('cover_stop', 'N/A')}",
            f"- **軋空風險:** {setup.get('squeeze_risk', 'N/A')}",
            f"- **論點失效:** {setup.get('thesis_invalidation', 'N/A')}",
            f"- **信心指數:** {context['confidence']}",
        ])
    return "\n".join([
        decision_heading,
        f"- **綜合建議:** {context['rec_text']}",
        f"- **3個月目標:** {context['target_3m']}",
        f"- **6個月目標:** {context['target_6m']}",
        f"- **12個月目標:** {context['target_12m']}",
        f"- **信心指數:** {context['confidence']}",
    ])


__all__ = ["build_markdown_decision_section"]
