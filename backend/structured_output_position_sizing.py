"""Additive sizing receipt schema; absent legacy fields remain readable."""

from typing import Literal

from pydantic import Field

from structured_output_model_base import StructuredModel


class PositionSizingEvidence(StructuredModel):
    status: Literal["calculated", "unassessed"]
    reason: str = Field(..., min_length=1)
    method: str | None = None
    formula: str | None = None
    source_ref: str | None = None
    context_sha256: str | None = None
    capital_amount: float | None = Field(default=None, strict=True, gt=0, allow_inf_nan=False)
    risk_budget_amount: float | None = Field(default=None, strict=True, gt=0, allow_inf_nan=False)
    currency: str | None = None
    scenario_type: Literal["research", "actual", "unassessed"] = "unassessed"
    position_state: Literal["no_position", "holding", "unknown"] = "unknown"
    existing_position_percent: float | None = Field(default=None, strict=True, ge=0, le=100, allow_inf_nan=False)
    risk_per_share: float | None = Field(default=None, strict=True, gt=0, allow_inf_nan=False)
    entry_reference: float | None = Field(default=None, strict=True, gt=0, allow_inf_nan=False)
    round_trip_cost: float | None = Field(default=None, strict=True, ge=0, allow_inf_nan=False)
    position_percent: float | None = Field(default=None, strict=True, gt=0, le=100, allow_inf_nan=False)
    risk_limit_percent: float | None = Field(default=None, strict=True, gt=0, le=100, allow_inf_nan=False)
    trade_direction: Literal["Long", "Short"] | None = None
    horizon_trading_days: int | None = Field(default=None, strict=True, ge=1, le=252)
