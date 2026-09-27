"""Company news retrieval stays bounded and selects evidence before truncation."""
from datetime import datetime, timedelta, timezone

import pytest

from data_fetch.enrichment_providers import FreeNewsWaterfallProvider
from data_fetch.types import FetchRequest


def record(name, days, index):
    return {"title": f"{name} 營運新聞 {index}", "summary": name,
            "published_date": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
            "source": "Publisher", "link": f"https://publisher.example/news/{index}"}


@pytest.mark.parametrize("ticker,name,display", [
    ("5314.TWO", "世紀", "世紀* / Myson Century, Inc."),
    ("2254.TW", "巨鎧精密-創", "巨鎧精密-創 / Coplus Inc."),
    ("1623.TW", "大東電", "大東電 / Ta Tun Electric Wire & Cable Co., Ltd."),
])
def test_taiwan_company_query_can_retrieve_recent_native_name_news(monkeypatch, ticker, name, display):
    import external_data_client
    calls = []
    class Client:
        last_news_audit = []
        def get_news(self, query, **kwargs):
            calls.append((query, kwargs))
            # The archived before/after RSS probes differ on these query terms.
            matches = f'"{name}"' in query and " / " not in query and "when:30d" in query
            return [record(name, 2 if matches else 300, 1)]
    monkeypatch.setattr(external_data_client, "ExternalDataClient", Client)
    data = {"ticker": ticker, "company_name": display,
            "company_identity": {"official_name": name, "allowed_aliases": [name]}}
    result = FreeNewsWaterfallProvider().fetch(FetchRequest.from_ticker(ticker), {"data": data})
    assert len(result.value) == 1
    query, options = calls[0]
    assert ticker.split(".")[0] in query
    assert options["ticker"] == ticker
    assert len(calls) == 1


def test_older_search_hits_do_not_use_up_recent_news_slots(monkeypatch):
    import external_data_client
    rows = [record("大東電", 300, i) for i in range(5)]
    rows += [record("大東電", days, days + 10) for days in (8, 4, 1, 5, 3, 2)]
    class Client:
        last_news_audit = []
        def get_news(self, query, **kwargs):
            assert kwargs["limit"] <= 20
            return rows[:kwargs["limit"]]
    monkeypatch.setattr(external_data_client, "ExternalDataClient", Client)
    result = FreeNewsWaterfallProvider().fetch(FetchRequest.from_ticker("1623.TW"),
                                              {"data": {"ticker": "1623.TW", "company_name": "大東電"}})
    assert len(result.value) == 5
    assert [r["title"] for r in result.value] == [f"大東電 營運新聞 {i + 10}" for i in (1, 2, 3, 4, 5)]
    assert result.audit["rejected_reason_counts"]["historical"] == 5
    assert len(result.audit["source_record_archive"]) == 5
    assert result.audit["news_selection"]["eligible_count"] == 6
    assert result.audit["news_selection"]["recent_count"] == 5
    assert len(result.audit["additional_recent_catalysts"]) == 1
    assert result.audit["additional_recent_catalysts"][0]["title"] == "大東電 營運新聞 18"
    assert result.status == "degraded_enrichment"  # Rejected evidence is still disclosed.


def test_google_rss_preserves_reported_publisher_for_evidence_selection(monkeypatch):
    import news_fetchers
    from types import SimpleNamespace
    from news_freshness_policy import publisher_identity
    xml = b'''<rss version="2.0"><channel><item><title>Company update</title>
    <link>https://news.google.com/rss/articles/example</link>
    <pubDate>Fri, 25 Sep 2026 04:00:00 GMT</pubDate>
    <source url="https://publisher.example">Example News</source>
    </item></channel></rss>'''
    monkeypatch.setattr(news_fetchers, "sync_get", lambda *a, **k: SimpleNamespace(content=xml))
    rows = news_fetchers.fetch_google_news_rss("Company", limit=5)
    assert rows[0]["source"] == "Example News"
    assert publisher_identity(rows[0]) == ("Example News", "example news", "reported")
