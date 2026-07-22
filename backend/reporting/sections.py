"""Split report rendering helper."""

from __future__ import annotations

from typing import Any

from analysis_types import AnalysisContext
from agent_catalog import AGENT_NAMES
from config import AGENT_MODELS
from mapping_fields import safe_mapping_dict
from pipeline_modes import get_pipeline_definition
from structured_output_normalizer import structured_output_to_report_text

from .audit_banner import _mask_blocking_issue
from .common import build_agent_model_labels
from .structured_intro import build_structured_intro_block, strip_legacy_structured_tags
from .text_tokens import is_missing_text_token
from .tear_sheet_summary import build_tear_sheet_summary
from .utils import (
    clean_markdown,
    format_debate_text,
    sanitize_report_text,
    strip_structured_blocks,
)

def _structured_block_belongs_at_tail(agent_num: int, pipeline_def: dict, structured_agents: dict) -> bool:
    return pipeline_def.get("id") == "v3" and agent_num == structured_agents.get("recommendation")


_MISSING_AGENT_VALUE = object()


def _agent_keyed_value(values: dict, agent_num: int, default: Any = None) -> Any:
    value = values.get(agent_num, _MISSING_AGENT_VALUE)
    if value is not _MISSING_AGENT_VALUE:
        return value
    return values.get(str(agent_num), default)


def _agent_sequence(context: AnalysisContext, pipeline_def: dict) -> tuple[int, ...]:
    raw_sequence = context.get("agent_sequence") or pipeline_def["agents"]
    if not isinstance(raw_sequence, (list, tuple)):
        raw_sequence = pipeline_def["agents"]
    sequence: list[int] = []
    for item in raw_sequence:
        if isinstance(item, (bool, bytes, bytearray, memoryview)):
            continue
        try:
            agent_num = int(item)
        except (TypeError, ValueError):
            continue
        if agent_num > 0:
            sequence.append(agent_num)
    return tuple(sequence) or tuple(pipeline_def["agents"])


def build_agent_sections(context: AnalysisContext, *, html: bool = True) -> list[dict]:
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    analyses = safe_mapping_dict(context.get("analyses", {})) or {}
    structured_outputs = safe_mapping_dict(context.get("structured_outputs", {})) or {}
    agent_sequence = _agent_sequence(context, pipeline_def)
    agent_model_labels = build_agent_model_labels()
    structured_agents = pipeline_def["structured_agents"]
    debate_agents = set(pipeline_def.get("debate_agents", ()))
    sections = []

    for display_num, agent_num in enumerate(agent_sequence, 1):
        raw_source = _agent_keyed_value(analyses, agent_num, "分析進行中...")
        raw_source = _mask_blocking_issue(raw_source)
        structured_intro = build_structured_intro_block(agent_num, context)
        if _structured_block_belongs_at_tail(agent_num, pipeline_def, structured_agents):
            structured = _agent_keyed_value(structured_outputs, agent_num)
            structured_map = safe_mapping_dict(structured)
            if structured_map is not None:
                raw_source = structured_output_to_report_text(agent_num, structured_map, str(raw_source))
        raw = strip_structured_blocks(sanitize_report_text(raw_source))
        raw = strip_legacy_structured_tags(raw)
        if structured_intro:
            if _structured_block_belongs_at_tail(agent_num, pipeline_def, structured_agents):
                raw = f"{raw}\n\n{structured_intro}".strip()
            elif structured_intro not in raw:
                raw = f"{structured_intro}\n\n{raw}".strip()
        if not raw.strip() or is_missing_text_token(raw):
            raw = "分析進行中..."
        if html:
            body = format_debate_text(raw) if agent_num in debate_agents else clean_markdown(raw)
        else:
            body = raw

        kind = "standard"
        if agent_num == structured_agents.get("moat"):
            kind = "moat"
        elif agent_num == structured_agents.get("valuation"):
            kind = "valuation"
        elif agent_num == structured_agents.get("recommendation"):
            kind = "final"
        elif agent_num == structured_agents.get("trade_setup"):
            kind = "trade_setup"

        sections.append({
            "display_num": display_num,
            "agent_num": agent_num,
            "title": AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
            "model_label": agent_model_labels.get(agent_num, AGENT_MODELS.get(agent_num, "N/A")),
            "body": body,
            "kind": kind,
            "is_debate": agent_num in debate_agents,
        })

    return sections
