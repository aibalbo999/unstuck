"""Canonical presentation catalog for pipeline modes."""

from __future__ import annotations

from typing import Any

from pipeline_modes import (
    PIPELINE_DEFINITIONS,
    get_pipeline_run_agent_total,
    get_pipeline_run_hint,
    get_pipeline_run_label,
)

SCHEMA_VERSION = "pipeline_modes.v1"

_PRESENTATION = {
    "v1": {
        "codeLabel": "模式 A",
        "displayLabel": "模式 A · 學術深度派",
        "decisionLabel": "長線研究",
        "ctaLabel": "開始模式 A 分析",
        "reportSuffix": "深度分析報告",
        "intent": "適合判斷是否納入長線研究清單。",
    },
    "v2": {
        "codeLabel": "模式 B",
        "displayLabel": "模式 B · 實戰交易派",
        "decisionLabel": "部位決策",
        "ctaLabel": "開始模式 B 分析",
        "reportSuffix": "實戰交易決策報告",
        "intent": "適合決定進場、續抱或減碼。",
    },
    "v3": {
        "codeLabel": "模式 C",
        "displayLabel": "模式 C · 逆勢泡沫狙擊",
        "decisionLabel": "逆勢風控",
        "ctaLabel": "開始模式 C 分析",
        "reportSuffix": "泡沫狙擊研究報告",
        "intent": "適合檢查泡沫、避險與做空風險。",
    },
    "v4": {
        "codeLabel": "模式 D",
        "displayLabel": "模式 D · 短線波段派",
        "decisionLabel": "事件波段",
        "ctaLabel": "開始模式 D 分析",
        "reportSuffix": "極短線交易策略報告",
        "intent": "適合短線事件與波段交易計畫。",
    },
}


def _pipeline_item(pipeline_id: str) -> dict[str, Any]:
    definition = PIPELINE_DEFINITIONS[pipeline_id]
    presentation = _PRESENTATION[pipeline_id]
    agent_count = len(definition["agents"])
    return {
        "id": pipeline_id,
        "label": definition["label"],
        "shortLabel": definition["short_label"],
        "hint": definition["hint_text"],
        "agentCount": agent_count,
        "optionLabel": f"{presentation['decisionLabel']} · {agent_count} Agent",
        **presentation,
    }


def build_pipeline_mode_catalog() -> list[dict[str, Any]]:
    catalog = [_pipeline_item(pipeline_id) for pipeline_id in ("v1", "v2", "v3", "v4")]
    catalog.append({
        "id": "both",
        "label": get_pipeline_run_label("both"),
        "codeLabel": "連續 A+B+C",
        "displayLabel": "連續 A+B+C · 三份報告",
        "shortLabel": "A+B+C 連續",
        "decisionLabel": "三視角交叉檢查",
        "optionLabel": f"三視角交叉檢查 · {get_pipeline_run_agent_total('both')} 模組",
        "ctaLabel": "連續執行 A+B+C",
        "reportSuffix": "三模式分析完成",
        "intent": "適合同一檔股票需要長線、交易與逆勢三視角交叉檢查。",
        "hint": get_pipeline_run_hint("both"),
        "agentCount": get_pipeline_run_agent_total("both"),
    })
    return catalog


__all__ = ["SCHEMA_VERSION", "build_pipeline_mode_catalog"]
