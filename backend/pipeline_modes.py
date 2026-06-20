"""Pipeline mode definitions shared by orchestration, audit, and rendering."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


PipelineId = Literal["v1", "v2", "v3"]
PipelineRunId = Literal["v1", "v2", "v3", "both"]


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
        "report_subtitle": "基於 9 個功能性分析模組完整研究",
        "hint_text": "請稍候，9 個 AI 分析模組正在為您撰寫深度研報...",
        "agents": (1, 2, 3, 20, 4, 5, 6, 21, 7),
        "groups": ((1,), (2,), (3, 20), (4, 5), (6,), (21,), (7,)),
        "structured_agents": {"moat": 3, "valuation": 4, "recommendation": 7},
        "debate_agents": (6,),
    },
    "v2": {
        "id": "v2",
        "label": "模式 B：實戰交易派",
        "short_label": "實戰交易派",
        "report_title": "實戰交易決策報告",
        "report_subtitle": "基於 8 個交易型分析模組完整研究",
        "hint_text": "請稍候，8 個 AI 分析模組正在整合總經、籌碼與進出場策略...",
        "agents": (11, 12, 13, 20, 14, 15, 21, 16),
        "groups": ((11,), (12, 13, 20), (14, 15), (21,), (16,)),
        "structured_agents": {"moat": 12, "valuation": 14, "recommendation": 16},
        "debate_agents": (),
    },
    "v3": {
        "id": "v3",
        "label": "模式 C：逆勢交易與泡沫狙擊",
        "short_label": "逆勢泡沫狙擊",
        "report_title": "泡沫狙擊研究報告",
        "report_subtitle": "基於 5 個逆勢分析模組檢驗市場預期、財務現實與籌碼派發",
        "hint_text": "請稍候，5 個 AI 逆勢分析模組正在檢驗題材泡沫、財務漏洞與做空觸發條件...",
        "agents": (17, 18, 20, 21, 19),
        "groups": ((17,), (18, 20), (21,), (19,)),
        "structured_agents": {"recommendation": 19},
        "debate_agents": (),
    },
}


DEFAULT_PIPELINE_ID: PipelineId = "v1"
DUAL_PIPELINE_RUN_ID: PipelineRunId = "both"


PIPELINE_RUN_LABELS: dict[str, dict[str, str]] = {
    "both": {
        "label": "連續模式：模式 A → 模式 B → 模式 C",
        "short_label": "A+B+C 連續",
        "hint_text": "將依序執行學術深度派、實戰交易派與逆勢泡沫狙擊；完成後會產出三份獨立報告。",
    }
}


def normalize_pipeline_id(value: Any) -> PipelineId:
    normalized = str(value or DEFAULT_PIPELINE_ID).strip().lower()
    if normalized in {"a", "mode_a", "mode-a", "classic", "academic", "pipeline_v1", "pipeline-v1"}:
        return "v1"
    if normalized in {"b", "mode_b", "mode-b", "trading", "practical", "pipeline_v2", "pipeline-v2"}:
        return "v2"
    if normalized in {
        "c",
        "mode_c",
        "mode-c",
        "contrarian",
        "bubble",
        "short",
        "short_selling",
        "short-selling",
        "pipeline_v3",
        "pipeline-v3",
    }:
        return "v3"
    return normalized if normalized in PIPELINE_DEFINITIONS else DEFAULT_PIPELINE_ID


def normalize_pipeline_run_id(value: Any) -> PipelineRunId:
    normalized = str(value or DEFAULT_PIPELINE_ID).strip().lower()
    if normalized in {
        "both",
        "all",
        "dual",
        "a+b",
        "a+b+c",
        "ab",
        "abc",
        "v1v2",
        "v1v2v3",
        "v1+v2",
        "v1+v2+v3",
        "v1/v2",
        "v1/v2/v3",
        "v1_v2",
        "v1_v2_v3",
        "v1-v2",
        "v1-v2-v3",
        "mode_a_b",
        "mode_a_b_c",
        "mode-a-b",
        "mode-a-b-c",
        "pipeline_both",
        "both_modes",
        "all_modes",
        "mode_ab",
        "mode_abc",
    }:
        return DUAL_PIPELINE_RUN_ID
    return normalize_pipeline_id(normalized)


def get_pipeline_run_sequence(run_id: Any = DEFAULT_PIPELINE_ID) -> tuple[PipelineId, ...]:
    normalized_run_id = normalize_pipeline_run_id(run_id)
    if normalized_run_id == DUAL_PIPELINE_RUN_ID:
        return ("v1", "v2", "v3")
    return (normalized_run_id,)


def get_pipeline_run_label(run_id: Any = DEFAULT_PIPELINE_ID) -> str:
    normalized_run_id = normalize_pipeline_run_id(run_id)
    if normalized_run_id == DUAL_PIPELINE_RUN_ID:
        return PIPELINE_RUN_LABELS[DUAL_PIPELINE_RUN_ID]["label"]
    return get_pipeline_definition(normalized_run_id)["label"]


def get_pipeline_run_hint(run_id: Any = DEFAULT_PIPELINE_ID) -> str:
    normalized_run_id = normalize_pipeline_run_id(run_id)
    if normalized_run_id == DUAL_PIPELINE_RUN_ID:
        return PIPELINE_RUN_LABELS[DUAL_PIPELINE_RUN_ID]["hint_text"]
    return get_pipeline_definition(normalized_run_id)["hint_text"]


def get_pipeline_run_agent_total(run_id: Any = DEFAULT_PIPELINE_ID) -> int:
    return sum(len(get_pipeline_definition(pipeline_id)["agents"]) for pipeline_id in get_pipeline_run_sequence(run_id))


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
