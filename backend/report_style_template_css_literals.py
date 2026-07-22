"""Literal-output heuristics for active report style templates."""

from __future__ import annotations

import re

import report_style_template_css_tokens as tokens

__all__ = ("has_non_css_literal_output",)


def has_non_css_literal_output(text: str) -> bool:
    scan_text = _css_comment_scan_text(text)
    return any(
        _non_css_output_line(line.strip()) for line in scan_text.splitlines()
    )

def _non_css_output_line(line: str) -> bool:
    not_brace = not _is_css_closing_brace_line(line)
    return bool(line and not_brace and not _is_css_like_line(line))

def _is_css_like_line(line: str) -> bool:
    return (
        tokens.has_css_token(line)
        and not _has_non_css_trailing_text(line)
        and not _has_non_css_inline_rule_body(line)
    )

def _has_non_css_inline_rule_body(line: str) -> bool:
    scan_line = _css_tail_scan_text(line)
    if "{" not in scan_line or "}" not in scan_line:
        return False
    body = scan_line.split("{", 1)[1].rsplit("}", 1)[0].strip()
    segments = [part.strip() for part in body.split(";") if part.strip()]
    if segments and all(
        tokens.starts_with_css_declaration(part) for part in segments
    ):
        return False
    return bool(body and has_non_css_literal_output(body))

def _is_css_closing_brace_line(line: str) -> bool:
    return line == "}"

def _has_non_css_trailing_text(line: str) -> bool:
    tail_scan_text = _css_tail_scan_text(line)
    trailing_text = _css_trailing_text(tail_scan_text)
    return bool(trailing_text) and not _is_css_comment_tail(trailing_text)

def _css_tail_scan_text(template_line: str) -> str:
    return template_line.replace("{{", "").replace("}}", "")

def _css_comment_scan_text(text: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", text)

def _css_trailing_text(css_line: str) -> str:
    has_declaration_tail_separator = _has_declaration_tail_separator(css_line)
    has_brace_tail_separator = _has_brace_tail_separator(css_line)
    primary_tail_separator = _primary_tail_separator(
        has_declaration_tail_separator
    )
    has_primary_tail_separator = _has_primary_tail_separator(
        has_declaration_tail_separator,
        has_brace_tail_separator,
    )
    if has_primary_tail_separator:
        return _trailing_text_after_separator(css_line, primary_tail_separator)
    if _has_fallback_semicolon_tail(css_line):
        return _trailing_text_after_separator(css_line, ";")
    return ""

def _trailing_text_after_separator(css_line: str, separator: str) -> str:
    return css_line.rsplit(separator, 1)[1].strip()
def _has_primary_tail_separator(
    declaration_tail: bool,
    brace_tail: bool,
) -> bool:
    return declaration_tail or brace_tail
def _primary_tail_separator(declaration_tail: bool) -> str:
    return ";" if declaration_tail else "}"
def _has_declaration_tail_separator(css_line: str) -> bool:
    return ";" in css_line and tokens.starts_with_css_declaration(css_line)
def _has_brace_tail_separator(css_line: str) -> bool:
    return "}" in css_line
def _has_fallback_semicolon_tail(css_line: str) -> bool:
    has_rule_block_opener = "{" in css_line
    has_semicolon_tail = ";" in css_line
    return not has_rule_block_opener and has_semicolon_tail
def _is_css_comment_tail(trailing_text: str) -> bool:
    return (trailing_text[:2], trailing_text[-2:]) == ("/*", "*/")
