"""View-time repairs for legacy static report HTML."""

from __future__ import annotations

import re
from html import escape

from ticker_links import quote_url_from_autolink_href


TICKER_HREF_RE = re.compile(r'href="(?P<href>https?://\d{4,6}\.(?:TW|TWO))"', re.IGNORECASE)
NAV_HREF_RE = re.compile(r'<a class="nav-item" href="#(?P<id>[^"]+)"')
NAV_SECTION_RE = re.compile(
    r'(?P<prefix><div class="nav-section">\s*<div class="nav-section-title">[^<]*</div>)(?P<body>.*?)(?P<suffix>\s*</div>\s*<div class="sidebar-footer">)',
    re.DOTALL,
)
REPORT_SECTION_RE = re.compile(
    r'<div class="section" id="(?P<id>section-\d+)">\s*<div class="section-header">\s*'
    r'<div class="section-num">(?P<num>.*?)</div>\s*<div class="section-title">(?P<title>.*?)</div>',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def normalize_ticker_autolinks(html: str) -> str:
    def replace(match: re.Match) -> str:
        quote_url = quote_url_from_autolink_href(match.group("href"))
        return f'href="{quote_url or match.group("href")}"'

    return TICKER_HREF_RE.sub(replace, html)


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub("", value or "")).strip()


def _report_sections(html: str) -> list[tuple[str, str, str]]:
    return [
        (match.group("id"), _plain(match.group("num")), _plain(match.group("title")))
        for match in REPORT_SECTION_RE.finditer(html)
    ]


def _nav_needs_rebuild(html: str, sections: list[tuple[str, str, str]]) -> bool:
    actual_ids = {"overview", *(section_id for section_id, _, _ in sections)}
    nav_ids = [match.group("id") for match in NAV_HREF_RE.finditer(html)]
    return bool(nav_ids) and any(nav_id not in actual_ids for nav_id in nav_ids)


def _nav_item(target_id: str, number: str, label: str) -> str:
    return (
        f'        <a class="nav-item" href="#{escape(target_id)}">\n'
        f'            <span class="nav-num">{escape(number)}</span>\n'
        f'            <span class="nav-label">{escape(label)}</span>\n'
        "        </a>"
    )


def repair_sidebar_navigation(html: str) -> str:
    sections = _report_sections(html)
    if not sections or not _nav_needs_rebuild(html, sections):
        return html
    items = [_nav_item("overview", "0", "概覽總覽")]
    items.extend(_nav_item(section_id, number, title) for section_id, number, title in sections)
    nav_html = "\n" + "\n".join(items)
    return NAV_SECTION_RE.sub(lambda match: f"{match.group('prefix')}{nav_html}{match.group('suffix')}", html, count=1)


def repair_report_html_for_view(html: str) -> str:
    return repair_sidebar_navigation(normalize_ticker_autolinks(str(html or "")))
