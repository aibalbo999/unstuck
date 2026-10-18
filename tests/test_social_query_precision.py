"""Retired forum search indexes must not hide or replace direct original posts."""
from copy import deepcopy
from pathlib import Path
import json

import pytest
import news_fetchers
import news_freshness_policy
from news_record_utils import parse_news_datetime
from source_content_selection import select_company_records
from data_fetch.agent_context_providers import SocialSentimentProvider
from data_fetch.types import FetchRequest

CASES = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/social_query_precision.json').read_text())['cases']


@pytest.fixture(params=CASES, ids=lambda case: case['ticker'])
def captured(request, monkeypatch):
    case = deepcopy(request.param)
    monkeypatch.setattr(news_freshness_policy, 'news_cutoff', lambda value=None: parse_news_datetime(value or case['cutoff']))
    return case


def provider(case):
    return SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker(case['ticker']), {'data': case['data']})


def install_capture(monkeypatch, case, *, all_empty=False, contaminate=False):
    calls = []
    def google(query, limit):
        calls.append((query, limit))
        channel = next(c for c, expected in case['candidate_query'].items() if query == expected) if query in case['candidate_query'].values() else next(c for c, expected in case['baseline_query'].items() if query == expected)
        records = case['candidate_records'][channel] if query == case['candidate_query'][channel] else case['baseline_records'][channel]
        if contaminate and channel == 'dcard':
            records = case['baseline_records'][channel]
        return deepcopy(records if not all_empty else [])
    monkeypatch.setattr(news_fetchers, 'fetch_google_news_rss', google)
    monkeypatch.setattr(news_fetchers, 'fetch_ptt_stock_sentiment', lambda ticker, limit: [] if all_empty else deepcopy(case['ptt_records']))
    return calls


def test_unverified_forum_index_queries_are_not_sent(captured, monkeypatch):
    calls = install_capture(monkeypatch, captured)
    provider(captured)
    assert calls == []


def test_real_capture_removes_noise_without_adding_or_replacing_ptt_evidence(captured, monkeypatch):
    originals = [dict(row, social_channel=channel) for channel, rows in captured['baseline_records'].items() for row in rows]
    originals += captured['ptt_records']
    prior, prior_audit = select_company_records(originals, captured['data'], cutoff=captured['cutoff'])
    assert len(prior) == len(captured['ptt_records'])
    assert prior_audit['rejected_count'] == captured['expected_rejected'] > 0
    assert prior_audit['coverage_status'] == 'partial'

    install_capture(monkeypatch, captured)
    result = provider(captured)
    assert result.value['ptt_stock_direct'] == prior
    assert result.value['sample_count'] == len(prior)
    assert result.value['raw_count'] == result.value['usable_count'] == len(prior)
    assert result.status == 'success'
    assert result.value['rejected_count'] == 0
    assert all(result.value[channel] == [] for channel in captured['candidate_records'])
    assert result.value['sentiment_assessment'] == 'not_assessed'


def test_empty_direct_ptt_without_any_other_evidence_remains_degraded(captured, monkeypatch):
    calls = install_capture(monkeypatch, captured, all_empty=True)
    result = provider(captured)
    assert calls == []
    assert result.status == 'degraded_enrichment'
    assert result.value['sample_count'] == 0
    assert result.value['status'] == 'empty_unknown'
    assert result.value['coverage_status'] == 'partial'


def test_unverified_search_results_are_not_fetched_when_valid_ptt_exists(captured, monkeypatch):
    install_capture(monkeypatch, captured, contaminate=True)
    result = provider(captured)
    assert result.status == 'success'
    assert result.value['sample_count'] == len(captured['ptt_records'])
    assert result.value['status'] == 'success'
    assert result.value['source_record_archive'] == []


def test_bare_request_uses_resolved_context_ticker_for_local_query(captured, monkeypatch):
    calls = install_capture(monkeypatch, captured)
    bare = captured['ticker'].split('.')[0]
    SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker(bare), {'data': captured['data']})
    assert calls == []


def test_missing_resolved_context_does_not_restore_unverified_search(monkeypatch):
    calls = []
    monkeypatch.setattr(news_fetchers, 'fetch_google_news_rss', lambda query, limit: calls.append((query, limit)) or [])
    monkeypatch.setattr(news_fetchers, 'fetch_ptt_stock_sentiment', lambda *a, **k: [])
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('5314'), {'data': {'company_name': '世紀*'}})
    assert calls == []
    assert result.status == 'degraded_enrichment'


def test_5314_keeps_direct_ptt_without_indexed_forum_queries(monkeypatch):
    from datetime import datetime, timezone

    calls = []
    def google(query, limit):
        calls.append(query)
        if 'pttweb.cc' in query and '"世紀"' in query:
            return [{'title': '[情報] 注意處置股清單', 'date': datetime.now(timezone.utc).isoformat(),
                     'link': 'https://pttweb.cc/unrelated', 'source': 'PTTweb.cc'}]
        return []
    monkeypatch.setattr(news_fetchers, 'fetch_google_news_rss', google)
    monkeypatch.setattr(news_fetchers, 'fetch_ptt_stock_sentiment', lambda ticker, limit: [
        {'title': '[標的] 請問5314世紀除權', 'date': datetime.now(timezone.utc).isoformat(),
         'link': 'https://www.ptt.cc/bbs/Stock/M.123.A.ABC.html', 'source': 'PTT Stock'}])

    result = SocialSentimentProvider()._fetch_uncached(
        FetchRequest.from_ticker('5314.TWO'),
        {'data': {'ticker': '5314.TWO', 'company_name': '世紀* / Myson Century, Inc.',
                  'company_identity': {'official_name': '世紀*'}}})
    assert calls == []
    assert result.status == 'success'
    assert result.value['sample_count'] == 1
    assert result.value['rejected_count'] == 0
    assert result.value['ptt_stock_direct'][0]['title'] == '[標的] 請問5314世紀除權'
