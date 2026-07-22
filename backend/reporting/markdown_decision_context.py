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
            f"- **核心催化劑:** {trade_setup.get('core_catalyst', 'N/A')}",
            f"- **短期波動風險:** {trade_setup.get('risk_level', 'High')}",
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
