from __future__ import annotations

import logging
from types import SimpleNamespace

import external_http_client
import news_fetchers


STANDARD_KEYS = {"title", "link", "published_date", "source", "summary"}


def test_news_fetchers_use_shared_sync_http_client():
    assert news_fetchers.sync_get is external_http_client.sync_get


def test_google_news_normalizes_schema_date_and_query_url(monkeypatch):
    captured = {}
    entry = SimpleNamespace(
        title="  TSMC expands capacity  ",
        link="https://example.com/story?utm_source=rss",
        summary=" <p>Capacity update</p> ",
        published_parsed=(2026, 6, 19, 8, 30, 0, 4, 170, 0),
    )

    class Response:
        content = b"rss"

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    def fake_parse(payload):
        assert payload == b"rss"
        return SimpleNamespace(entries=[entry], bozo=False)

    monkeypatch.setattr(news_fetchers, "sync_get", fake_get)
    monkeypatch.setattr(news_fetchers.feedparser, "parse", fake_parse)

    result = news_fetchers.fetch_google_news_rss(" 台積電 2330 ", limit=1)

    assert len(result) == 1
    assert set(result[0]) == STANDARD_KEYS
    assert result[0] == {
        "title": "TSMC expands capacity",
        "link": "https://example.com/story",
        "published_date": "2026-06-19T08:30:00+00:00",
        "source": "Google News RSS",
        "summary": "Capacity update",
    }
    assert "news.google.com/rss/search?" in captured["url"]
    assert "%E5%8F%B0%E7%A9%8D%E9%9B%BB+2330" in captured["url"]
    assert captured["timeout"] == news_fetchers.REQUEST_TIMEOUT_SECONDS
    assert captured["provider"] == "Google News RSS"


def test_google_timeout_returns_empty_and_logs_warning(monkeypatch, caplog):
    def timeout(*_args, **_kwargs):
        raise TimeoutError("response body")

    monkeypatch.setattr(news_fetchers, "sync_get", timeout)

    with caplog.at_level(logging.WARNING):
        assert news_fetchers.fetch_google_news_rss("TSMC") == []

    assert "Google News RSS" in caplog.text
    assert "response body" not in caplog.text


def test_duckduckgo_maps_keys_and_removes_duplicate_links(monkeypatch):
    rows = [
        {
            "title": "First result",
            "url": "https://news.example/item?utm_campaign=x",
            "date": "2026-06-19T08:00:00Z",
            "source": "Example Wire",
            "body": "A concise summary",
        },
        {
            "title": "Duplicate",
            "url": "https://news.example/item",
            "date": "2026-06-19",
            "source": "Another source",
            "body": "Duplicate summary",
        },
    ]

    class FakeDDGS:
        def news(self, **kwargs):
            assert kwargs["query"] == "TSMC"
            assert kwargs["max_results"] == 2
            return rows

    monkeypatch.setattr(news_fetchers, "DDGS", FakeDDGS)

    result = news_fetchers.fetch_duckduckgo_news("TSMC", limit=2)

    assert result == [{
        "title": "First result",
        "link": "https://news.example/item",
        "published_date": "2026-06-19T08:00:00+00:00",
        "source": "Example Wire",
        "summary": "A concise summary",
    }]


def test_duckduckgo_reuses_client_between_calls(monkeypatch):
    instances = []

    class FakeDDGS:
        def __init__(self):
            instances.append(self)

        def news(self, **_kwargs):
            return [{"title": "News", "url": "https://example.com/news"}]

    monkeypatch.setattr(news_fetchers, "DDGS", FakeDDGS)

    assert news_fetchers.fetch_duckduckgo_news("TSMC", limit=1)
    assert news_fetchers.fetch_duckduckgo_news("TSMC", limit=1)

    assert len(instances) == 1


def test_duckduckgo_uses_provider_name_when_publisher_is_missing(monkeypatch):
    class FakeDDGS:
        def news(self, **_kwargs):
            return [{"title": "News", "url": "https://example.com/news", "source": None}]

    monkeypatch.setattr(news_fetchers, "DDGS", FakeDDGS)

    result = news_fetchers.fetch_duckduckgo_news("TSMC", limit=1)

    assert result[0]["source"] == "DuckDuckGo News"


def test_unparseable_provider_dates_normalize_to_empty(monkeypatch):
    class FakeDDGS:
        def news(self, **_kwargs):
            return [{
                "title": "News",
                "url": "https://example.com/news",
                "date": "not a date",
                "source": "Example Wire",
            }]

    monkeypatch.setattr(news_fetchers, "DDGS", FakeDDGS)

    result = news_fetchers.fetch_duckduckgo_news("TSMC", limit=1)

    assert result[0]["published_date"] == ""


def test_limit_is_clamped_and_blank_input_short_circuits(monkeypatch):
    captured = {}

    class FakeDDGS:
        def news(self, **kwargs):
            captured.update(kwargs)
            return []

    monkeypatch.setattr(news_fetchers, "DDGS", FakeDDGS)

    assert news_fetchers.fetch_duckduckgo_news("TSMC", limit=999) == []
    assert captured["max_results"] == news_fetchers.MAX_RESULTS
    assert news_fetchers.fetch_duckduckgo_news("   ", limit=10) == []
    assert news_fetchers.fetch_duckduckgo_news("TSMC", limit="bad") == []
    assert captured["max_results"] == 10
    assert news_fetchers.fetch_duckduckgo_news("TSMC", limit=0) == []
    assert captured["max_results"] == 1


def test_ptt_expands_relative_links_skips_deleted_and_filters_ticker(monkeypatch):
    html = """
    <div class="r-ent"><div class="title"><a href="/bbs/Stock/M.1.html">[新聞] 2330 台積電擴產</a></div><div class="date"> 6/19</div></div>
    <div class="r-ent"><div class="title">(本文已被刪除)</div><div class="date"> 6/19</div></div>
    <div class="r-ent"><div class="title"><a href="/bbs/Stock/M.2.html">[新聞] 2317 鴻海展望</a></div><div class="date"> 6/19</div></div>
    """
    captured = {}

    class Response:
        text = html

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(news_fetchers, "sync_get", fake_get)
    monkeypatch.setattr(news_fetchers, "_current_taipei_datetime", lambda: news_fetchers.datetime(
        2026, 6, 19, 9, 0, tzinfo=news_fetchers.TAIPEI_TZ,
    ))

    result = news_fetchers.fetch_ptt_stock_sentiment("2330", limit=10)

    assert result == [{
        "title": "[新聞] 2330 台積電擴產",
        "link": "https://www.ptt.cc/bbs/Stock/M.1.html",
        "published_date": "2026-06-19T00:00:00+08:00",
        "source": "PTT Stock",
        "summary": "[新聞] 2330 台積電擴產",
    }]
    assert captured["url"].endswith("/bbs/Stock/index.html")
    assert captured["timeout"] == news_fetchers.REQUEST_TIMEOUT_SECONDS
    assert captured["provider"] == "PTT Stock"
    assert "Mozilla" in captured["headers"]["User-Agent"]
    assert news_fetchers.fetch_ptt_stock_sentiment("../../etc/passwd") == []


def test_ptt_date_rolls_back_year_when_month_day_would_be_future(monkeypatch):
    monkeypatch.setattr(news_fetchers, "_current_taipei_datetime", lambda: news_fetchers.datetime(
        2026, 1, 1, 9, 0, tzinfo=news_fetchers.TAIPEI_TZ,
    ))

    assert news_fetchers._ptt_date_to_iso("12/31") == "2025-12-31T00:00:00+08:00"


def test_google_parser_errors_return_empty_and_log_warning(monkeypatch, caplog):
    class Response:
        content = b"not-rss"

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(news_fetchers, "sync_get", lambda *_args, **_kwargs: Response())

    def broken_feed(_payload):
        raise ValueError("parser failed")

    monkeypatch.setattr(news_fetchers.feedparser, "parse", broken_feed)

    with caplog.at_level(logging.WARNING):
        assert news_fetchers.fetch_google_news_rss("TSMC") == []

    assert "Google News RSS" in caplog.text
    assert "parser failed" not in caplog.text


def test_provider_errors_return_empty_and_log_warning(monkeypatch, caplog):
    def timeout(*_args, **_kwargs):
        raise TimeoutError("private response body must not leak")

    class BrokenDDGS:
        def news(self, **_kwargs):
            raise RuntimeError("DDG unavailable")

    monkeypatch.setattr(news_fetchers, "sync_get", timeout)
    monkeypatch.setattr(news_fetchers, "DDGS", BrokenDDGS)

    with caplog.at_level(logging.WARNING):
        assert news_fetchers.fetch_google_news_rss("TSMC") == []
        assert news_fetchers.fetch_duckduckgo_news("TSMC") == []
        assert news_fetchers.fetch_ptt_stock_sentiment("2330") == []

    assert "Google News RSS" in caplog.text
    assert "DuckDuckGo News" in caplog.text
    assert "PTT Stock" in caplog.text
    assert "private response body must not leak" not in caplog.text


def test_missing_ddg_dependency_returns_empty_and_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(news_fetchers, "DDGS", None)

    with caplog.at_level(logging.WARNING):
        assert news_fetchers.fetch_duckduckgo_news("TSMC") == []

    assert "DuckDuckGo News" in caplog.text
    assert "dependency" in caplog.text
