"""View-time repairs for legacy static report HTML."""

from __future__ import annotations

import re
from html import escape

from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
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
REPORT_READING_NOTICE_RE = re.compile(
    r'<section\b(?=[^>]*\breport-reading-notice\b)[\s\S]*?</section>',
    re.IGNORECASE,
)
EXECUTION_SUMMARY_ITEM_RE = re.compile(
    r'<div class="execution-summary-item(?P<attrs>[^>]*)>\s*'
    r'<span>(?P<label>[^<]*)</span>\s*<strong>[^<]*</strong>\s*</div>',
    re.IGNORECASE,
)
MARKDOWN_READING_NOTICE_RE = re.compile(
    r"^## 報告使用範圍與判讀限制\s*\n[\s\S]*?(?=^## |\Z)",
    re.MULTILINE,
)
BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)
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


def repair_report_reading_notice(html: str, context: dict | None = None) -> str:
    if not context:
        return html
    notice = build_report_reading_notice_html(context).strip()
    if "report-reading-notice-blocked" not in notice and "report-reading-notice-warning" not in notice:
        return html
    if REPORT_READING_NOTICE_RE.search(html):
        return REPORT_READING_NOTICE_RE.sub(notice, html, count=1)
    match = BODY_CLOSE_RE.search(html)
    if match:
        return f"{html[:match.start()]}{notice}\n{html[match.start():]}"
    return f"{notice}\n{html}"


def repair_report_execution_summary_quality(html: str, context: dict | None = None) -> str:
    """Overlay current quality gate values onto the view-only execution summary."""
    if not isinstance(context, dict) or context.get("_current_quality_projection") is not True:
        return html
    evidence = context.get("evidence_exit_gate") if isinstance(context.get("evidence_exit_gate"), dict) else {}
    content = context.get("content_credibility") if isinstance(context.get("content_credibility"), dict) else {}
    conformance = context.get("report_conformance") if isinstance(context.get("report_conformance"), dict) else {}
    values = {
        "Evidence gate": str(evidence.get("verdict") or "").strip(),
        "Content credibility": str(content.get("status") or "").strip(),
        "Report conformance": str(conformance.get("status") or "").strip(),
    }
    if not any(values.values()):
        return html

    def replace(match: re.Match) -> str:
        label = re.sub(r"\s+", " ", match.group("label") or "").strip()
        value = values.get(label)
        if not value:
            return match.group(0)
        attrs = match.group("attrs") or ""
        aria = escape(f"{label}：{value}")
        if re.search(r'\baria-label="[^"]*"', attrs, re.IGNORECASE):
            attrs = re.sub(r'\baria-label="[^"]*"', f'aria-label="{aria}"', attrs, count=1, flags=re.IGNORECASE)
        else:
            attrs = f'{attrs} aria-label="{aria}"'
        if "data-quality-source=" not in attrs:
            attrs = f'{attrs} data-quality-source="current-projection"'
        return (
            f'<div class="execution-summary-item{attrs}>'
            f'<span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        )

    return EXECUTION_SUMMARY_ITEM_RE.sub(replace, html)


def repair_report_html_for_view(html: str, reading_notice_context: dict | None = None) -> str:
    repaired = normalize_ticker_autolinks(str(html or ""))
    repaired = repair_report_reading_notice(repaired, reading_notice_context)
    repaired = repair_report_execution_summary_quality(repaired, reading_notice_context)
    return repair_sidebar_navigation(repaired)


def repair_report_markdown_for_download(markdown: str, reading_notice_context: dict | None = None) -> str:
    text = str(markdown or "")
    if not reading_notice_context:
        return text
    notice = build_report_reading_notice_markdown(reading_notice_context).strip()
    if MARKDOWN_READING_NOTICE_RE.search(text):
        return MARKDOWN_READING_NOTICE_RE.sub(f"{notice}\n\n", text, count=1)
    return f"{notice}\n\n{text}"
