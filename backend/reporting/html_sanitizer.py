"""Allowlist sanitization for report HTML fragments."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import nh3

from .html_linkifier import linkify_sanitized_html


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
    return linkify_sanitized_html(cleaned)


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
