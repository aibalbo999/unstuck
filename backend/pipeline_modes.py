"""Pipeline mode definitions shared by orchestration, audit, and rendering."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


PipelineId = Literal["v1", "v2"]


class PipelineDefinition(TypedDict):
    id: PipelineId
    label: str
    short_label: str
    report_title: str
    report_subtitle: str
    hint_text: str
    agents: tuple[int, ...]
    groups: tuple[tuple[int, ...], ...]
    structured_agents: dict[str, int]
    debate_agents: tuple[int, ...]


PIPELINE_DEFINITIONS: dict[str, PipelineDefinition] = {
    "v1": {
        "id": "v1",
        "label": "模式 A：學術深度派",
        "short_label": "學術深度派",
        "report_title": "華爾街深度研究報告",
        "report_subtitle": "基於 7 位頂級分析師完整研究",
        "hint_text": "請稍候，7 位 AI 分析師正在為您撰寫深度研報...",
        "agents": (1, 2, 3, 4, 5, 6, 7),
        "groups": ((1, 2, 3), (4, 5), (6,), (7,)),
        "structured_agents": {"moat": 3, "valuation": 4, "recommendation": 7},
        "debate_agents": (6,),
    },
    "v2": {
        "id": "v2",
        "label": "模式 B：實戰交易派",
        "short_label": "實戰交易派",
        "report_title": "實戰交易決策報告",
        "report_subtitle": "基於 6 位交易型分析師完整研究",
        "hint_text": "請稍候，6 位 AI 分析師正在整合總經、籌碼與進出場策略...",
        "agents": (11, 12, 13, 14, 15, 16),
        "groups": ((11,), (12, 13), (14,), (15,), (16,)),
        "structured_agents": {"moat": 12, "valuation": 14, "recommendation": 16},
        "debate_agents": (),
    },
}


DEFAULT_PIPELINE_ID: PipelineId = "v1"


def normalize_pipeline_id(value: Any) -> PipelineId:
    normalized = str(value or DEFAULT_PIPELINE_ID).strip().lower()
    if normalized in {"a", "classic", "academic", "pipeline_v1", "pipeline-v1"}:
        return "v1"
    if normalized in {"b", "trading", "practical", "pipeline_v2", "pipeline-v2"}:
        return "v2"
    return normalized if normalized in PIPELINE_DEFINITIONS else DEFAULT_PIPELINE_ID


def get_pipeline_definition(pipeline_id: Any = DEFAULT_PIPELINE_ID) -> PipelineDefinition:
    return PIPELINE_DEFINITIONS[normalize_pipeline_id(pipeline_id)]


def get_pipeline_agents(pipeline_id: Any = DEFAULT_PIPELINE_ID) -> tuple[int, ...]:
    return get_pipeline_definition(pipeline_id)["agents"]


def get_structured_agent_num(kind: str, context_or_pipeline: Any = DEFAULT_PIPELINE_ID) -> int | None:
    if isinstance(context_or_pipeline, dict):
        pipeline_id = context_or_pipeline.get("pipeline_id", DEFAULT_PIPELINE_ID)
    else:
        pipeline_id = context_or_pipeline
    return get_pipeline_definition(pipeline_id)["structured_agents"].get(kind)
