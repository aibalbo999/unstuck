"""Allowlist sanitization for report HTML fragments."""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import nh3

from ticker_links import quote_url_for_ticker, quote_url_from_autolink_href


ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

ALLOWED_ATTRIBUTES = {
    "*": {"class"},
    "a": {"href", "rel", "target", "title"},
    "span": {"aria-label", "data-source-id", "role", "tabindex"},
    "td": {"align", "colspan", "rowspan"},
    "th": {"align", "colspan", "rowspan"},
}

ALLOWED_PROTOCOLS = {"http", "https", "mailto"}
DATA_IMAGE_RE = re.compile(r"^data:image/(?:png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=\s]+$")
DANGEROUS_BLOCK_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|svg|math)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
AUTO_LINK_RE = re.compile(
    r"(?P<url>https?://[^\s<\"']+)|(?P<ticker>\b\d{4,6}\.(?:TW|TWO)\b)",
    re.IGNORECASE,
)
TRAILING_LINK_PUNCTUATION = ".,;:!?)]}，。；：！？）】"


def sanitize_report_html(html: str) -> str:
    """Strip unsafe tags and attributes from model/report HTML fragments."""
    text = _safe_input_text(html)
    if not text:
        return ""
    text = DANGEROUS_BLOCK_RE.sub("", text)
    cleaned = nh3.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_PROTOCOLS,
        strip_comments=True,
        link_rel=None,
    )
    return _linkify_sanitized_html(cleaned)


def sanitize_report_plain_text(value) -> str:
    """Strip HTML from values that should render as plain text only."""
    text = DANGEROUS_BLOCK_RE.sub("", _safe_input_text(value))
    text = nh3.clean(text, tags=set(), attributes={}, strip_comments=True)
    return re.sub(r"\s+", " ", text).strip()


def sanitize_report_image_url(value) -> str:
    """Allow only browser-safe image URLs for inline report cover styles."""
    text = _safe_input_text(value).strip()
    if not text:
        return ""
    if DATA_IMAGE_RE.match(text):
        return re.sub(r"\s+", "", text)
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text.replace("'", "%27").replace('"', "%22").replace(")", "%29")
    return ""


def _safe_input_text(value) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return ""


def _linkify_sanitized_html(html: str) -> str:
    parser = _ReportHtmlLinkifier()
    parser.feed(_safe_input_text(html))
    parser.close()
    return parser.output


class _ReportHtmlLinkifier(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_linkify_depth = 0

    @property
    def output(self) -> str:
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs):
        normalized_tag = tag.lower()
        if normalized_tag in {"a", "pre", "code"}:
            self._skip_linkify_depth += 1
        if normalized_tag == "a":
            attrs = _normalized_anchor_attrs(attrs)
        self._parts.append(_start_tag_html(normalized_tag, attrs))

    def handle_startendtag(self, tag: str, attrs):
        normalized_tag = tag.lower()
        self._parts.append(_start_tag_html(normalized_tag, attrs, closed=True))

    def handle_endtag(self, tag: str):
        normalized_tag = tag.lower()
        self._parts.append(f"</{normalized_tag}>")
        if normalized_tag in {"a", "pre", "code"} and self._skip_linkify_depth > 0:
            self._skip_linkify_depth -= 1

    def handle_data(self, data: str):
        if self._skip_linkify_depth:
            self._parts.append(escape(data, quote=False))
            return
        self._parts.append(_linkify_text(data))


def _start_tag_html(tag: str, attrs, *, closed: bool = False) -> str:
    attr_text = "".join(
        f' {escape(str(name), quote=True)}="{escape(str(value), quote=True)}"'
        for name, value in attrs
        if value is not None
    )
    suffix = " />" if closed else ">"
    return f"<{tag}{attr_text}{suffix}"


def _normalized_anchor_attrs(attrs) -> list[tuple[str, str]]:
    normalized = [(str(name), str(value)) for name, value in attrs if name]
    href = ""
    for name, value in normalized:
        if name.lower() == "href":
            href = value
            break
    if not href:
        return [(name, value) for name, value in normalized if name.lower() not in {"rel", "target"}]

    quote_url = quote_url_from_autolink_href(href)
    href = quote_url or href
    filtered = [(name, value) for name, value in normalized if name.lower() not in {"href", "rel", "target"}]
    return [("href", href), *filtered, ("rel", "nofollow noopener noreferrer"), ("target", "_blank")]


def _linkify_text(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in AUTO_LINK_RE.finditer(text):
        start, end = match.span()
        parts.append(escape(text[cursor:start], quote=False))
        token = match.group(0)
        core, trailing = _split_trailing_link_punctuation(token)
        if match.group("ticker"):
            href = quote_url_for_ticker(core)
        else:
            href = quote_url_from_autolink_href(core) or core
        parts.append(_anchor_html(href, core))
        parts.append(escape(trailing, quote=False))
        cursor = end
    parts.append(escape(text[cursor:], quote=False))
    return "".join(parts)


def _split_trailing_link_punctuation(token: str) -> tuple[str, str]:
    index = len(token)
    while index > 0 and token[index - 1] in TRAILING_LINK_PUNCTUATION:
        index -= 1
    return token[:index], token[index:]


def _anchor_html(href: str, label: str) -> str:
    return (
        f'<a href="{escape(str(href), quote=True)}" '
        'rel="nofollow noopener noreferrer" target="_blank">'
        f"{escape(str(label), quote=False)}</a>"
    )
