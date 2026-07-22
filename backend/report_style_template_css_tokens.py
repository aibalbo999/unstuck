"""CSS token and declaration-context heuristics for report style templates."""

from __future__ import annotations

import re

__all__ = (
    "has_css_token",
    "is_approved_style_expression_context",
    "starts_with_css_declaration",
)

_APPROVED_DECLARATION_VALUE_EXPRESSIONS = frozenset({"rec_color"})


def _css_descendant_chain(element_fragment: str) -> str:
    return rf"{element_fragment}(?:\s+{element_fragment})*"


_CSS_IDENTIFIER_RE_FRAGMENT = r"[A-Za-z][A-Za-z0-9_-]*"
_CSS_INTERACTIVE_ELEMENT_RE_FRAGMENT = r"a|button|input|select|textarea|summary"
_CSS_DECLARATION_PREFIX_RE_FRAGMENT = (
    rf"(?!(?:{_CSS_INTERACTIVE_ELEMENT_RE_FRAGMENT}):{{1,2}})"
    rf"-{{0,2}}{_CSS_IDENTIFIER_RE_FRAGMENT}\s*:"
)
_CSS_DECLARATION_START_RE = re.compile(
    rf"^\s*{_CSS_DECLARATION_PREFIX_RE_FRAGMENT}")
_CSS_LINE_START_FRAGMENT = r"(?:^|\n)\s*"
_CSS_AT_RULES_RE_FRAGMENT = (
    r"media|keyframes|supports|container|layer|page|font-face|"
    r"property|scope|starting-style|counter-style"
)
_CSS_AT_RULE_STATEMENTS_RE_FRAGMENT = r"import|charset|namespace|layer"
_CSS_SELECTOR_START_CHARS_RE_FRAGMENT = r".#*&\[>+~"
_CSS_RULE_PRELUDE_RE_FRAGMENT = r"[^;\n{{]*"
_CSS_RULE_BLOCK_OPEN_RE_FRAGMENT = rf"{_CSS_RULE_PRELUDE_RE_FRAGMENT}\{{"
_CSS_TABLE_ELEMENTS_RE_FRAGMENT = r"table|caption|thead|tbody|tfoot|tr|th|td"
_CSS_TEXT_ELEMENTS_RE_FRAGMENT = (
    r"h1|h2|h3|h4|h5|h6|p|ul|ol|li|strong|em|small|"
    r"figure|figcaption|blockquote|pre|code|hr|details|dl|dt|dd|canvas|br"
)
_CSS_LAYOUT_ELEMENTS_RE_FRAGMENT = (
    r"main|section|article|aside|header|" r"footer|nav"
)
_CSS_SVG_ELEMENTS_RE_FRAGMENT = (
    r"svg|g|path|circle|rect|line|" r"polyline|polygon|text"
)
_CSS_COMMENT_TOKEN_RE_FRAGMENT = r"^\s*/\*[\s\S]*?\*/\s*$"
_CSS_SELECTOR_BLOCK_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}"
    rf"[{_CSS_SELECTOR_START_CHARS_RE_FRAGMENT}]"
    rf"{_CSS_RULE_BLOCK_OPEN_RE_FRAGMENT}"
)
_CSS_PSEUDO_SELECTOR_RE_FRAGMENT = (
    rf":{{1,2}}-?{_CSS_IDENTIFIER_RE_FRAGMENT}"
    r"(?:\([^;\n{{}}]*\))?"
)
_CSS_ELEMENT_QUALIFIER_RE_FRAGMENT = (
    rf"(?:[.#]{_CSS_IDENTIFIER_RE_FRAGMENT}|"
    r"\[[^\]\n{{}};]+\]|"
    rf"{_CSS_PSEUDO_SELECTOR_RE_FRAGMENT})"
)
_CSS_ELEMENT_SUFFIX_RE_FRAGMENT = (
    rf"\b(?:{_CSS_ELEMENT_QUALIFIER_RE_FRAGMENT})*"
)
def _css_element(elements_fragment: str) -> str:
    return rf"(?:{elements_fragment}){_CSS_ELEMENT_SUFFIX_RE_FRAGMENT}"
_CSS_PSEUDO_SELECTOR_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}{_CSS_PSEUDO_SELECTOR_RE_FRAGMENT}"
    rf"{_CSS_RULE_BLOCK_OPEN_RE_FRAGMENT}"
)
_CSS_ROOT_ELEMENT_RE_FRAGMENT = _css_element("html|body")
_CSS_TABLE_ELEMENT_RE_FRAGMENT = _css_element(_CSS_TABLE_ELEMENTS_RE_FRAGMENT)
_CSS_LAYOUT_ELEMENT_RE_FRAGMENT = _css_element(_CSS_LAYOUT_ELEMENTS_RE_FRAGMENT)
_CSS_SVG_ELEMENT_RE_FRAGMENT = _css_element(_CSS_SVG_ELEMENTS_RE_FRAGMENT)
_CSS_SVG_RE_FRAGMENT = _css_descendant_chain(_CSS_SVG_ELEMENT_RE_FRAGMENT)
_CSS_TABLE_RE_FRAGMENT = _css_descendant_chain(_CSS_TABLE_ELEMENT_RE_FRAGMENT)
_CSS_TEXT_ELEMENT_RE_FRAGMENT = _css_element(_CSS_TEXT_ELEMENTS_RE_FRAGMENT)
_CSS_TEXT_RE_FRAGMENT = _css_descendant_chain(_CSS_TEXT_ELEMENT_RE_FRAGMENT)
_CSS_CONTROL_RE_FRAGMENT = _css_element(_CSS_INTERACTIVE_ELEMENT_RE_FRAGMENT)
_CSS_LAYOUT_CONTENT_RE_FRAGMENT = (
    rf"{_CSS_LAYOUT_ELEMENT_RE_FRAGMENT}|{_CSS_TEXT_RE_FRAGMENT}|"
    rf"{_CSS_TABLE_RE_FRAGMENT}|{_CSS_SVG_RE_FRAGMENT}|"
    rf"{_CSS_CONTROL_RE_FRAGMENT}"
)
_CSS_LAYOUT_DESCENDANT_RE_FRAGMENT = (
    rf"{_CSS_LAYOUT_ELEMENT_RE_FRAGMENT}"
    rf"(?:\s+(?:{_CSS_LAYOUT_CONTENT_RE_FRAGMENT}))*"
)
_CSS_ELEMENT_RE_FRAGMENT = (
    rf"{_CSS_ROOT_ELEMENT_RE_FRAGMENT}|{_CSS_LAYOUT_DESCENDANT_RE_FRAGMENT}|"
    rf"{_CSS_TEXT_RE_FRAGMENT}|{_CSS_TABLE_RE_FRAGMENT}|{_CSS_SVG_RE_FRAGMENT}|"
    rf"{_CSS_CONTROL_RE_FRAGMENT}"
)
_CSS_ELEMENT_COMBINATOR_RE_FRAGMENT = (
    rf"(?:{_CSS_ELEMENT_RE_FRAGMENT})"
    rf"(?:\s*[>+~]\s*(?:{_CSS_ELEMENT_RE_FRAGMENT}))*"
)
_CSS_SELECTOR_LIST_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}"
    rf"(?:[:{_CSS_SELECTOR_START_CHARS_RE_FRAGMENT}]"
    rf"{_CSS_RULE_PRELUDE_RE_FRAGMENT}|"
    rf"{_CSS_ELEMENT_COMBINATOR_RE_FRAGMENT})\s*,\s*$"
)
_CSS_ELEMENT_PSEUDO_SELECTOR_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}(?:{_CSS_INTERACTIVE_ELEMENT_RE_FRAGMENT})"
    rf"\b{_CSS_PSEUDO_SELECTOR_RE_FRAGMENT}\s*\{{"
)
_CSS_INTERACTIVE_ELEMENT_SELECTOR_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}(?:{_CSS_INTERACTIVE_ELEMENT_RE_FRAGMENT})"
    rf"{_CSS_ELEMENT_SUFFIX_RE_FRAGMENT}\s*\{{"
)
_CSS_INTERACTIVE_ELEMENT_SELECTOR_LIST_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}(?:{_CSS_INTERACTIVE_ELEMENT_RE_FRAGMENT})"
    rf"{_CSS_ELEMENT_SUFFIX_RE_FRAGMENT}\s*,\s*$"
)
_CSS_ELEMENT_BLOCK_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}"
    rf"(?:{_CSS_ELEMENT_COMBINATOR_RE_FRAGMENT})\s*\{{"
)
_CSS_KEYFRAME_SELECTOR_RE_FRAGMENT = r"(?:from|to|\d+(?:\.\d+)?%)"
_CSS_KEYFRAME_SELECTOR_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}{_CSS_KEYFRAME_SELECTOR_RE_FRAGMENT}"
    rf"(?:\s*,\s*{_CSS_KEYFRAME_SELECTOR_RE_FRAGMENT})*\s*\{{"
)
_CSS_DECLARATION_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}{_CSS_DECLARATION_PREFIX_RE_FRAGMENT}"
    rf"[^;\n]+;"
)
_CSS_AT_RULE_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}@(?:{_CSS_AT_RULES_RE_FRAGMENT})"
    rf"\b{_CSS_RULE_BLOCK_OPEN_RE_FRAGMENT}"
)
_CSS_AT_RULE_STATEMENT_TOKEN_RE_FRAGMENT = (
    rf"{_CSS_LINE_START_FRAGMENT}@(?:{_CSS_AT_RULE_STATEMENTS_RE_FRAGMENT})"
    rf"\b{_CSS_RULE_PRELUDE_RE_FRAGMENT};\s*$"
)
_CSS_TOKEN_RE_BRANCHES = (
    _CSS_COMMENT_TOKEN_RE_FRAGMENT,
    _CSS_SELECTOR_BLOCK_TOKEN_RE_FRAGMENT,
    _CSS_SELECTOR_LIST_TOKEN_RE_FRAGMENT,
    _CSS_PSEUDO_SELECTOR_TOKEN_RE_FRAGMENT,
    _CSS_ELEMENT_PSEUDO_SELECTOR_TOKEN_RE_FRAGMENT,
    _CSS_INTERACTIVE_ELEMENT_SELECTOR_TOKEN_RE_FRAGMENT,
    _CSS_INTERACTIVE_ELEMENT_SELECTOR_LIST_TOKEN_RE_FRAGMENT,
    _CSS_ELEMENT_BLOCK_TOKEN_RE_FRAGMENT,
    _CSS_KEYFRAME_SELECTOR_TOKEN_RE_FRAGMENT,
    _CSS_DECLARATION_TOKEN_RE_FRAGMENT,
    _CSS_AT_RULE_TOKEN_RE_FRAGMENT,
    _CSS_AT_RULE_STATEMENT_TOKEN_RE_FRAGMENT,
)
_CSS_TOKEN_RE_PATTERN = "|".join(_CSS_TOKEN_RE_BRANCHES)
_CSS_TOKEN_RE = re.compile(_CSS_TOKEN_RE_PATTERN)


def has_css_token(text: str) -> bool:
    return bool(_CSS_TOKEN_RE.search(text))


def starts_with_css_declaration(text: str) -> bool:
    return bool(_CSS_DECLARATION_START_RE.match(text))


def is_approved_style_expression_context(expression: str, prefix: str) -> bool:
    declaration_segment = prefix[max(prefix.rfind("{"), prefix.rfind(";")) + 1:]
    allowed_value = expression in _APPROVED_DECLARATION_VALUE_EXPRESSIONS
    return allowed_value and starts_with_css_declaration(declaration_segment)
