"""Shared numeric primitives for evidence claims, independent of path routing."""

import math
import re


NUMBER_IN_STRING_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def clean_number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def valid_claim_number(value: float) -> bool:
    return math.isfinite(value) and abs(value) < 1e15
