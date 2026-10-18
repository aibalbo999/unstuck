from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news, verified_issuer_news
from data_fetch.market_sources.issuer_news_transport import ROSTER_URL, SANYANG_INDEX, SINBON_INDEX
from source_content_selection import select_company_records
from news_freshness_policy import apply_news_freshness

ROOT = Path(__file__).parent / "fixtures/source_acquisition"
NOW = datetime(2026, 10, 9, 9, tzinfo=timezone.utc)
SLUG = "from-connection-to-impact-sinbon-builds-sinbon-city-at-electronica-2026-hall-a3-booth-341"
DETAIL = "https://www.sinbon.com/api/news/detail/" + SLUG
ARTICLE = "https://www.sanyang.com.tw/busnessnews-page693"


class Http:
    def __init__(self, ticker="3023.TW"):
        self.contents = {ROSTER_URL: (ROOT / "issuer_roster_selected_20261009.json").read_bytes()}
        if ticker == "3023.TW":
            self.contents.update({SINBON_INDEX: (ROOT / "issuer_sinbon_news_20261009.json").read_bytes(),
                                  DETAIL: (ROOT / "issuer_sinbon_detail_20261009.json").read_bytes()})
        else:
            self.contents.update({SANYANG_INDEX: (ROOT / "issuer_sanyang_news_20261009.html").read_bytes(),
                                  ARTICLE: (ROOT / "issuer_sanyang_article_20261009.html").read_bytes()})
        self.calls, self.components, self.http_request_count = [], [], 0

    def get(self, url):
        self.calls.append(url)
        self.http_request_count += 1
        self.components.append({"url": url, "http_request_sent": True, "cache_hit": False})
        return self.contents[url]


@pytest.mark.parametrize("ticker,original", [("3023.TW", "2026.10.06"), ("2206.TW", "Oct 02 2026")])
def test_observed_original_article_passes_identity_and_keeps_date_precision(ticker, original):
    http = Http(ticker)
    rows, audit = fetch_recent_issuer_news(ticker, now=NOW, http=http)
    assert audit["status"] == "success" and len(rows) == 1
    assert audit["http_request_count"] == 3 and audit["window_complete"] is False
    assert rows[0]["publication_date_original"]["issuer_article_date"] == original
    assert rows[0]["publication_date_precision"] == "day" and "T" not in rows[0]["date"]
    assert rows[0]["event_assessment"] == "not_assessed"
    accepted, _ = select_company_records(rows, {"ticker": ticker}, cutoff=NOW)
    assert len(accepted) == 1
    assert verified_issuer_news(rows[0], {"ticker": ticker}, today=NOW.date())


def test_official_english_alias_is_scoped_and_does_not_modify_company_identity():
    rows, _ = fetch_recent_issuer_news("3023.TW", now=NOW, http=Http())
    data = {"ticker": "3023.TW", "company_name": "信邦", "company_identity": {"official_name": "信邦", "allowed_aliases": ["信邦"]}}
    prior = deepcopy(data["company_identity"])
    apply_news_freshness(data, records=rows, cutoff=NOW)
    assert len(data["recent_catalysts"]) == 1
    assert verified_issuer_news(data["recent_catalysts"][0], data, today=NOW.date()) == "SINBON"
    assert data["company_identity"] == prior
    original = deepcopy(data["recent_catalysts"])
    apply_news_freshness(data, cutoff=NOW)
    assert data["recent_catalysts"] == original
    assert not verified_issuer_news(rows[0], {"ticker": "2206.TW"}, today=NOW.date())


@pytest.mark.parametrize("field,value", [("英文簡稱", "OTHER"), ("網址", "www.sinbon.com.evil.test"),
                                       ("出表日期", "1150801"), ("出表日期", "1151101"),
                                       ("公司名稱", "另一家股份有限公司")])
def test_invalid_official_binding_stops_before_news_http(field, value):
    http = Http()
    rows = json.loads(http.contents[ROSTER_URL])
    next(r for r in rows if r["公司代號"] == "3023")[field] = value
    http.contents[ROSTER_URL] = json.dumps(rows, ensure_ascii=False).encode()
    records, audit = fetch_recent_issuer_news("3023.TW", now=NOW, http=http)
    assert records == [] and audit["status"] == "error"
    assert http.calls == [ROSTER_URL]


def test_missing_roster_issuer_and_duplicate_issuer_fail_closed():
    for duplicate in (False, True):
        http = Http()
        rows = json.loads(http.contents[ROSTER_URL])
        rows = [r for r in rows if r["公司代號"] != "3023"] if not duplicate else [*rows, rows[-1]]
        http.contents[ROSTER_URL] = json.dumps(rows, ensure_ascii=False).encode()
        records, audit = fetch_recent_issuer_news("3023.TW", now=NOW, http=http)
        assert records == [] and audit["status"] == "error" and len(http.calls) == 1


@pytest.mark.parametrize("stamp", ["2026/10", None, "2026.11.01", "2026.08.01", True])
def test_unknown_month_future_and_historical_dates_do_not_fetch_original(stamp):
    http = Http()
    payload = json.loads(http.contents[SINBON_INDEX]); payload["rows"] = payload["rows"][:1]
    payload["rows"][0]["article_date"] = stamp
    http.contents[SINBON_INDEX] = json.dumps(payload).encode()
    rows, audit = fetch_recent_issuer_news("3023.TW", now=NOW, http=http)
    assert rows == [] and audit["status"] == "unavailable"
    assert http.calls == [ROSTER_URL, SINBON_INDEX]


@pytest.mark.parametrize("field,value", [("id", "999"), ("article_date", "2026.10.05"),
                                       ("description", "SINBON unrelated changed body"), ("slug", "other-article")])
def test_original_must_match_listed_id_date_slug_and_body(field, value):
    http = Http()
    payload = json.loads(http.contents[DETAIL]); payload["row"][field] = value
    http.contents[DETAIL] = json.dumps(payload).encode()
    rows, audit = fetch_recent_issuer_news("3023.TW", now=NOW, http=http)
    assert rows == [] and audit["status"] == "error"


@pytest.mark.parametrize("field,value", [("summary", "made up result"), ("text", "fake SINBON body" * 20),
                                       ("link", "https://evil.test/story"), ("source", "Independent third party")])
def test_saved_record_mutations_are_not_admitted(field, value):
    rows, _ = fetch_recent_issuer_news("3023.TW", now=NOW, http=Http())
    rows[0][field] = value
    selected, _ = select_company_records(rows, {"ticker": "3023.TW"}, cutoff=NOW)
    assert selected == []


def test_wrong_market_is_zero_http():
    http = Http()
    rows, audit = fetch_recent_issuer_news("3023.TWO", now=NOW, http=http)
    assert not rows and audit["status"] == "not_applicable" and http.calls == []


def test_wholly_cached_fetch_keeps_original_acquisition_epoch_and_is_zero_http():
    class CachedHttp(Http):
        def get(self, url):
            self.components.append({"url": url, "cache_hit": True, "http_request_sent": False,
                                    "fetched_at_epoch": NOW.timestamp() - 300})
            return self.contents[url]
    rows, audit = fetch_recent_issuer_news("3023.TW", now=NOW, http=CachedHttp())
    assert len(rows) == 1 and audit["status"] == "skipped_fresh_cache"
    assert audit["fetched_at_epoch"] == NOW.timestamp() - 300
    assert audit["http_request_sent"] is False and audit["http_request_count"] == 0


@pytest.mark.parametrize("forbidden", ["sinbon", " SINBON ", "<b>sinbon</b>"])
def test_official_alias_does_not_bypass_existing_forbidden_alias(forbidden):
    rows, _ = fetch_recent_issuer_news("3023.TW", now=NOW, http=Http())
    data = {"ticker": "3023.TW", "company_identity": {"official_name": "信邦", "forbidden_aliases": [forbidden]}}
    selected, _ = select_company_records(rows, data, cutoff=NOW)
    assert selected == []


def test_receipts_survive_real_optional_bundle_and_async_workflow(monkeypatch):
    import asyncio
    import data_fetch.workflow as workflow
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from unittest.mock import patch
    from data_fetch.market_sources import issuer_news

    real_fetch = issuer_news.fetch_recent_issuer_news
    monkeypatch.setattr(issuer_news, "fetch_recent_issuer_news", lambda ticker: real_fetch(ticker, now=NOW, http=Http()))
    monkeypatch.setattr(workflow, "cache_financial_payload", lambda *a: None)
    monkeypatch.setattr(workflow, "finalize_data_trust", lambda *a: None)
    monkeypatch.setattr(workflow, "_merge_optional_http_bundle", lambda data, bundle, **kwargs: _merge_optional_http_bundle(data, bundle))
    data = {"ticker": "3023.TW", "company_name": "信邦", "company_identity": {"official_name": "信邦"}}
    with patch("news_freshness_policy.news_cutoff", return_value=NOW):
        out = asyncio.run(workflow._run_optional_provider_plan(FetchRequest.from_ticker("3023.TW"), ProviderRegistry([IssuerNewsProvider()]), data, sources=("recent_catalysts",)))
    assert len(out["recent_catalysts"]) == 1
    assert any(a["provider"] == "Verified issuer news" and a["record_count"] == 1 for a in out["source_audit"])
