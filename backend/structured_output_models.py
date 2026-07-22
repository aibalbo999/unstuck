"""Pydantic schemas and prompt instructions for structured agents."""

from __future__ import annotations

from typing import Optional

from json_utils import extract_json_payload
from prompt_rules import build_structured_agent_instructions
from structured_output_model_base import AnalysisMarkdownMixin, StructuredModel
from structured_output_recommendation_outputs import (
    BubbleSniperRecommendationFields,
    BubbleSniperStructuredOutput,
    RecommendationFields,
    RecommendationStructuredOutput,
)
from structured_output_recommendation_types import Catalyst, ConfidenceBasis, ExecutiveThesisOutput, ScenarioTrigger
from structured_output_risk_models import (
    BearAdvocateStructuredOutput,
    DownsideRisk,
    ManagementHighlight,
    ManagementSentimentStructuredOutput,
    SwingTradeSetup,
)
from structured_output_valuation_models import (
    DcfScenarioOutput,
    MoatScores,
    MoatStructuredOutput,
    PriceTargets,
    PriceTargetStructuredOutput,
    ValuationSummary,
)


__all__ = [
    "AnalysisMarkdownMixin",
    "BearAdvocateStructuredOutput",
    "BubbleSniperRecommendationFields",
    "BubbleSniperStructuredOutput",
    "Catalyst",
    "ConfidenceBasis",
    "DcfScenarioOutput",
    "DownsideRisk",
    "ExecutiveThesisOutput",
    "ManagementHighlight",
    "ManagementSentimentStructuredOutput",
    "MoatScores",
    "MoatStructuredOutput",
    "PriceTargets",
    "PriceTargetStructuredOutput",
    "RecommendationFields",
    "RecommendationStructuredOutput",
    "STRUCTURED_AGENT_RESPONSE_SCHEMAS",
    "ScenarioTrigger",
    "StructuredModel",
    "SwingTradeSetup",
    "ValuationSummary",
    "build_structured_output_instruction",
    "get_structured_response_schema",
]


STRUCTURED_AGENT_INSTRUCTIONS = build_structured_agent_instructions()

STRUCTURED_AGENT_RESPONSE_SCHEMAS: dict[int, type[StructuredModel]] = {
    3: MoatStructuredOutput,
    4: PriceTargetStructuredOutput,
    7: RecommendationStructuredOutput,
    12: MoatStructuredOutput,
    14: PriceTargetStructuredOutput,
    16: RecommendationStructuredOutput,
    19: BubbleSniperStructuredOutput,
    20: ManagementSentimentStructuredOutput,
    21: BearAdvocateStructuredOutput,
    24: SwingTradeSetup,
}


def get_structured_response_schema(agent_num: int) -> Optional[type[StructuredModel]]:
    """Return the native response schema model for structured agents."""
    return STRUCTURED_AGENT_RESPONSE_SCHEMAS.get(agent_num)


def build_structured_output_instruction(agent_num: int) -> str:
    """Return JSON-only output instructions for agents with machine-read fields."""
    return STRUCTURED_AGENT_INSTRUCTIONS.get(agent_num, "")


def _extract_json_payload(raw_text: str) -> Optional[dict]:
    return extract_json_payload(raw_text)
