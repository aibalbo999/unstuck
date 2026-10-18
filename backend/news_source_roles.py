"""Known public URL roles, independent of a news API's publisher label."""

import re
from urllib.parse import urlsplit


def is_cmoney_forum_post_url(link: str) -> bool:
    """A direct forum article is a social post, not editorial news metadata."""
    if not isinstance(link, str):
        return False
    try:
        parsed = urlsplit(link)
        return bool(
            parsed.scheme in {"http", "https"}
            and (parsed.hostname or "").lower() in {"cmoney.tw", "www.cmoney.tw"}
            and re.fullmatch(r"/forum/article/[0-9]{1,20}/?", parsed.path)
        )
    except ValueError:
        return False


def _is_aggregated_news(record: dict) -> bool:
    source_type = record.get("source_type")
    return isinstance(source_type, str) and (source_type == "finmind_news" or source_type.endswith("_search"))


def is_finmind_forum_news_record(record: dict, link: str) -> bool:
    """API/search delivery cannot change a direct social URL into news.

    Keep the existing helper name for callers and direct social-only routes.
    """
    return _is_aggregated_news(record) and is_cmoney_forum_post_url(link)


def is_cmoney_stock_overview_url(link: str) -> bool:
    """The observed f00025 route is a stock overview, not a dated article."""
    if not isinstance(link, str):
        return False
    try:
        parsed = urlsplit(link)
        return bool(
            parsed.scheme in {"http", "https"}
            and (parsed.hostname or "").lower() in {"cmoney.tw", "www.cmoney.tw"}
            and re.fullmatch(r"/finance/[0-9]{4,6}/f00025/?", parsed.path)
        )
    except ValueError:
        return False


def is_finmind_stock_overview_record(record: dict, link: str) -> bool:
    return _is_aggregated_news(record) and is_cmoney_stock_overview_url(link)
