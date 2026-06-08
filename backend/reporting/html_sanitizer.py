"""Allowlist sanitization for report HTML fragments."""

from __future__ import annotations

import re
from html import escape
from urllib.parse import urlparse

from ticker_links import quote_url_from_autolink_href

try:
    import bleach
except Exception:  # pragma: no cover - dependency fallback for older installs
    bleach = None


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
    "*": ["class"],
    "a": ["href", "rel", "target", "title"],
    "td": ["align", "colspan", "rowspan"],
    "th": ["align", "colspan", "rowspan"],
}

ALLOWED_PROTOCOLS = {"http", "https", "mailto"}
DATA_IMAGE_RE = re.compile(r"^data:image/(?:png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=\s]+$")
DANGEROUS_BLOCK_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|svg|math)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_report_html(html: str) -> str:
    """Strip unsafe tags and attributes from model/report HTML fragments."""
    if not html:
        return ""
    html = DANGEROUS_BLOCK_RE.sub("", str(html))
    if bleach is None:
        return escape(html)
    cleaned = bleach.clean(
        str(html),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return bleach.linkify(cleaned, callbacks=[_link_attrs], skip_tags={"pre", "code"})


def sanitize_report_plain_text(value) -> str:
    """Strip HTML from values that should render as plain text only."""
    text = DANGEROUS_BLOCK_RE.sub("", str(value or ""))
    if bleach is None:
        text = re.sub(r"<[^>]*>", "", text)
    else:
        text = bleach.clean(text, tags=set(), attributes={}, strip=True, strip_comments=True)
    return re.sub(r"\s+", " ", text).strip()


def sanitize_report_image_url(value) -> str:
    """Allow only browser-safe image URLs for inline report cover styles."""
    text = str(value or "").strip()
    if not text:
        return ""
    if DATA_IMAGE_RE.match(text):
        return re.sub(r"\s+", "", text)
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text.replace("'", "%27").replace('"', "%22").replace(")", "%29")
    return ""


def _link_attrs(attrs, _new=False):
    href_key = (None, "href")
    if href_key not in attrs:
        return attrs
    quote_url = quote_url_from_autolink_href(attrs[href_key])
    if quote_url:
        attrs[href_key] = quote_url
    attrs[(None, "rel")] = "nofollow noopener noreferrer"
    attrs[(None, "target")] = "_blank"
    return attrs
