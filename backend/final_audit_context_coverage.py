"""Final-decision coverage checks for optional market context."""

from __future__ import annotations

from data_trust import source_record_count


FINAL_CONTEXT_COVERAGE_SOURCES = (
    (
        "global_market_context",
        "全球市場脈絡",
        ("global_market_context", "全球市場脈絡", "全球風險偏好", "美股", "總經", "匯率", "利率"),
    ),
    (
        "international_news_context",
        "國際新聞脈絡",
        ("international_news_context", "國際新聞脈絡", "國際新聞", "國際重大新聞", "GDELT", "地緣", "供應鏈"),
    ),
)


def missing_final_context_labels(data: dict, text: str) -> list[str]:
    """Return available global context labels not mentioned by final-decision text."""
    normalized_text = str(text or "")
    missing = []
    for source, label, terms in FINAL_CONTEXT_COVERAGE_SOURCES:
        if source_record_count(source, data) <= 0:
            continue
        if not any(term in normalized_text for term in terms):
            missing.append(label)
    return missing
