import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_social_sentiment_provider_directly_fetches_ptt_for_taiwan_ticker(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.types import FetchRequest

    google_calls = []
    ptt_calls = []

    def fake_google(query, limit=3):
        google_calls.append((query, limit))
        return []

    def fake_ptt(ticker, limit=5):
        ptt_calls.append((ticker, limit))
        return [
            {
                "title": "PTT 台積電討論",
                "published_date": "2026-06-27",
                "source": "PTT Stock",
                "link": "https://ptt.example/2330",
                "summary": "量價討論",
            }
        ]

    monkeypatch.setattr(news_fetchers, "fetch_google_news_rss", fake_google)
    monkeypatch.setattr(news_fetchers, "fetch_ptt_stock_sentiment", fake_ptt)

    result = SocialSentimentProvider().fetch(
        FetchRequest.from_ticker("2330.TW"),
        {"data": {"ticker": "2330.TW", "company_name": "台積電"}},
    )

    assert ptt_calls == [("2330", 5)]
    assert len(google_calls) == 3
    assert result.status == "success"
    assert result.value["ptt_stock_direct"] == [
        {"title": "PTT 台積電討論", "date": "2026-06-27", "source": "PTT Stock"}
    ]
    assert result.audit["record_count"] == 1
