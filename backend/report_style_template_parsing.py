from __future__ import annotations

import re
from pathlib import Path

import report_style_template_css as css

__all__ = (
    "commentless_template_text",
    "dynamic_include_targets",
    "has_css_token",
    "has_non_css_literal_output",
    "included_templates",
    "is_approved_style_expression_context",
    "jinja_block_tags",
    "jinja_expressions",
    "literal_template_output",
    "non_canonical_include_targets",
    "optioned_static_include_targets",
    "single_include_target",
)

_INCLUDE_ONLY_RE = re.compile(r"""^\{%\s*include\s+["']([^"']+)["']\s*%\}$""")
_INCLUDE_RE = re.compile(r"""\{%\s*include\s+["']([^"']+)["']\s*%\}""")
_INCLUDE_TAG_RE = re.compile(r"""\{%\s*include\s+(.+?)\s*%\}""")
_STATIC_INCLUDE_TARGET_RE = re.compile(r"""^["'][^"']+["']$""")
_JINJA_COMMENT_RE = re.compile(r"{#.*?#}", re.S)
_JINJA_BLOCK_TAG_RE = re.compile(r"{%.*?%}", re.S)
_JINJA_EXPRESSION_TAG_RE = re.compile(r"{{\s*(.*?)\s*}}", re.S)


def commentless_template_text(path: Path) -> str:
    return _JINJA_COMMENT_RE.sub("", path.read_text(encoding="utf-8"))


def single_include_target(path: Path) -> str | None:
    match = _INCLUDE_ONLY_RE.fullmatch(commentless_template_text(path).strip())
    return match.group(1) if match else None


def has_css_token(text: str) -> bool:
    return css.has_css_token(text)


def has_non_css_literal_output(text: str) -> bool:
    return css.has_non_css_literal_output(text)


def dynamic_include_targets(path: Path) -> list[str]:
    targets: list[str] = []
    for match in _INCLUDE_TAG_RE.finditer(commentless_template_text(path)):
        target = match.group(1).strip()
        if not target.startswith(("\"", "'")):
            targets.append(target)
    return targets


def optioned_static_include_targets(path: Path) -> list[str]:
    targets: list[str] = []
    for match in _INCLUDE_TAG_RE.finditer(commentless_template_text(path)):
        target = match.group(1).strip()
        quoted_target = target.startswith(("\"", "'"))
        static_target = _STATIC_INCLUDE_TARGET_RE.fullmatch(target)
        if quoted_target and not static_target:
            targets.append(target)
    return targets


def non_canonical_include_targets(path: Path) -> list[str]:
    return [
        match.group(1).strip()
        for match in _INCLUDE_TAG_RE.finditer(commentless_template_text(path))
        if not _STATIC_INCLUDE_TARGET_RE.fullmatch(match.group(1).strip())
    ]


def included_templates(path: Path) -> list[str]:
    return _INCLUDE_RE.findall(commentless_template_text(path))


def literal_template_output(path: Path) -> str:
    return _JINJA_BLOCK_TAG_RE.sub("", commentless_template_text(path)).strip()


def _expression_prefix(text: str, match: re.Match[str]) -> str:
    return text[text.rfind("\n", 0, match.start()) + 1 : match.start()]


def jinja_expressions(path: Path) -> list[tuple[str, str]]:
    text = commentless_template_text(path)
    return [
        (match.group(1).strip(), _expression_prefix(text, match))
        for match in _JINJA_EXPRESSION_TAG_RE.finditer(text)
    ]


def is_approved_style_expression_context(expression: str, prefix: str) -> bool:
    return css.is_approved_style_expression_context(expression, prefix)


def jinja_block_tags(path: Path) -> list[str]:
    text = commentless_template_text(path)
    return [tag[2:-2].strip() for tag in _JINJA_BLOCK_TAG_RE.findall(text)]
