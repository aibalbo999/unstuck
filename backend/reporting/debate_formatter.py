"""Bull/bear debate HTML formatting for report agent sections."""

from __future__ import annotations

import re
from html import escape

from .html_sanitizer import sanitize_report_html, sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def _bull_content(line: str) -> str:
    content = re.sub(r"^🐂\s*", "", line).strip()
    return re.sub(r"^陳博士(?:[（(][^）)]*[）)])?[：:]\s*", "", content).strip()


def _bear_content(line: str) -> str:
    content = re.sub(r"^🐻\s*", "", line).strip()
    return re.sub(r"^李博士(?:[（(][^）)]*[）)])?[：:]\s*", "", content).strip()


def _moderator_content(line: str) -> str:
    content = re.sub(r"^[*-]*\s*主持人[總結]?[：:]\s*", "", line).replace("---", "").strip()
    content = re.sub(r"^\*+\s*主持人總結[：:]\s*\*+", "", content).strip()
    return re.sub(r"^主持人總結[：:]\s*", "", content).strip()


def _content(value: str) -> str:
    content = sanitize_report_plain_text(value).strip()
    return "" if is_missing_text_token(content) else content


def format_debate_text(text: str) -> str:
    """Format bull/bear debate text as sanitized report HTML bubbles."""
    if not text:
        return ""

    result = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if "🐂" in line or "陳博士" in line or "多頭" in line:
            content = _content(_bull_content(line))
            if content:
                result.append(
                    f"""
                <div class="debate-bubble bull-bubble">
                    <div class="debate-avatar bull-avatar">🐂 多頭</div>
                    <div class="debate-content">{escape(content)}</div>
                </div>"""
                )
            continue

        if "🐻" in line or "李博士" in line or "空頭" in line:
            content = _content(_bear_content(line))
            if content:
                result.append(
                    f"""
                <div class="debate-bubble bear-bubble">
                    <div class="debate-content">{escape(content)}</div>
                    <div class="debate-avatar bear-avatar">🐻 空頭</div>
                </div>"""
                )
            continue

        if "主持人" in line or "---" in line:
            content = _content(_moderator_content(line))
            if content:
                result.append(
                    f"""
                <div class="debate-conclusion">
                    <div class="debate-conclusion-icon">⚖️</div>
                    <div class="debate-conclusion-text"><strong>主持人總結：</strong>{escape(content)}</div>
                </div>"""
                )
            continue

        if line and not line.startswith("#") and len(line) > 10:
            content = _content(line)
            if content:
                result.append(f'<p class="debate-narration">{escape(content)}</p>')

    return sanitize_report_html("\n".join(result))
