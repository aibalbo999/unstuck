"""Public facade for report style CSS template heuristics."""

from __future__ import annotations

import report_style_template_css_literals as literals
import report_style_template_css_tokens as tokens

__all__ = (
    "has_css_token",
    "has_non_css_literal_output",
    "is_approved_style_expression_context",
)


def has_css_token(text: str) -> bool:
    return tokens.has_css_token(text)


def has_non_css_literal_output(text: str) -> bool:
    return literals.has_non_css_literal_output(text)


def is_approved_style_expression_context(expression: str, prefix: str) -> bool:
    return tokens.is_approved_style_expression_context(expression, prefix)
