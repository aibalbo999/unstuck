"""Strict Pydantic validation dispatch for structured agent payloads."""

from __future__ import annotations

from typing import Optional

from pydantic import ValidationError

from structured_output_recommendation_outputs import BubbleSniperStructuredOutput, RecommendationStructuredOutput
from structured_output_risk_models import (
    BearAdvocateStructuredOutput,
    ManagementSentimentStructuredOutput,
    SwingTradeSetup,
)
from structured_output_valuation_models import MoatStructuredOutput, PriceTargetStructuredOutput


STRICT_STRUCTURED_SCHEMAS = {
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


def validated_structured_payload(agent_num: int, payload: dict) -> Optional[dict]:
    schema = STRICT_STRUCTURED_SCHEMAS.get(agent_num)
    if schema is None:
        return payload
    try:
        return schema.model_validate(payload).model_dump(by_alias=True)
    except ValidationError:
        return None
