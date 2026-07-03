import sys
from pathlib import Path
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.text)


def test_fetch_104_job_openings_count_extracts_total_from_html():
    from alternative_data_fetcher import fetch_104_job_openings_count

    session = FakeSession(
        """
        <html>
          <body>
            <script>window.__STATE__={"totalCount":128,"other":true}</script>
            <h1>台達電 散熱 職缺</h1>
          </body>
        </html>
        """
    )

    result = fetch_104_job_openings_count("台達電", "散熱", session=session)

    assert result["job_count"] == 128
    assert result["company_name"] == "台達電"
    assert result["keyword"] == "散熱"
    assert "104.com.tw" in result["source_url"]
    headers = session.calls[0][1]["headers"]
    assert "Mozilla" in headers["User-Agent"]


def test_fetch_104_job_openings_count_falls_back_to_text_pattern():
    from alternative_data_fetcher import fetch_104_job_openings_count

    session = FakeSession("<main>搜尋結果：共 36 筆工作機會</main>")

    result = fetch_104_job_openings_count("台達電", "液冷", session=session)

    assert result["job_count"] == 36


def test_fetch_104_job_openings_count_uses_shared_http_client(monkeypatch):
    import alternative_data_fetcher
    from alternative_data_fetcher import fetch_104_job_openings_count

    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse('<script>{"totalCount":88}</script>')

    monkeypatch.setattr(alternative_data_fetcher, "sync_get", fake_get)

    result = fetch_104_job_openings_count("台達電", "散熱")

    assert result["job_count"] == 88
    assert calls[0]["provider"] == "104 Job Search"
    assert calls[0]["params"]["keyword"] == "台達電 散熱"


def test_fetch_1111_job_openings_count_uses_shared_http_client(monkeypatch):
    import alternative_data_fetcher
    from alternative_data_fetcher import fetch_1111_job_openings_count

    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return FakeResponse("<main>共 42 筆</main>")

    monkeypatch.setattr(alternative_data_fetcher, "sync_get", fake_get)

    result = fetch_1111_job_openings_count("台達電", "散熱")

    assert result["job_count"] == 42
    assert calls[0]["provider"] == "1111 Job Search"
    assert calls[0]["params"]["ks"] == "台達電 散熱"


def test_fetch_104_job_openings_count_returns_unavailable_on_parse_failure():
    from alternative_data_fetcher import fetch_104_job_openings_count

    with patch("alternative_data_fetcher._google_news_fallback") as news_fallback:
        result = fetch_104_job_openings_count("台達電", "AI", session=FakeSession("<html></html>"))

    news_fallback.assert_not_called()
    assert result["status"] == "unavailable"
    assert result["job_count"] is None
    assert "未揭露可解析的職缺總數" in result["message"]


def test_fetch_104_job_openings_count_uses_news_fallback_on_transport_failure():
    from alternative_data_fetcher import fetch_104_job_openings_count

    class FailingSession:
        def get(self, url, **kwargs):
            raise TimeoutError("offline")

    fake_news = [{"title": "台達電擴編消息"}]
    with patch("news_fetchers.fetch_google_news_rss", return_value=fake_news) as fetch_news:
        result = fetch_104_job_openings_count("台達電", "AI", session=FailingSession())

    fetch_news.assert_called_once_with("台達電 AI 徵才 OR 擴編 OR 招募", limit=5)
    assert result["status"] == "success"
    assert result["job_count"] is None
    assert result["recent_recruitment_news"] == fake_news


def test_fetch_104_job_openings_count_does_not_mask_parser_errors_with_news_fallback():
    from alternative_data_fetcher import fetch_104_job_openings_count

    with (
        patch("alternative_data_fetcher._extract_104_job_count", side_effect=ValueError("parser bug")),
        patch("alternative_data_fetcher._google_news_fallback") as news_fallback,
    ):
        with pytest.raises(ValueError, match="parser bug"):
            fetch_104_job_openings_count("台達電", "AI", session=FakeSession("<html></html>"))

    news_fallback.assert_not_called()
