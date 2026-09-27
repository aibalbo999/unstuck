"""Query precision must not change social evidence, source coverage, or status gates."""
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


def test_all_three_sites_use_official_local_identity_with_unchanged_limit(captured, monkeypatch):
    calls = install_capture(monkeypatch, captured)
    provider(captured)
    assert calls == [(query, 3) for query in captured['candidate_query'].values()]
    assert all(' / ' not in query and ' when:30d' in query for query, limit in calls)


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


def test_empty_queries_without_any_ptt_evidence_remain_degraded(captured, monkeypatch):
    calls = install_capture(monkeypatch, captured, all_empty=True)
    result = provider(captured)
    assert len(calls) == 3
    assert result.status == 'degraded_enrichment'
    assert result.value['sample_count'] == 0
    assert result.value['status'] == 'empty_unknown'
    assert result.value['coverage_status'] == 'partial'


def test_unrelated_results_still_archived_and_partial_even_with_valid_ptt(captured, monkeypatch):
    install_capture(monkeypatch, captured, contaminate=True)
    result = provider(captured)
    assert result.status == 'degraded_enrichment'
    assert result.value['sample_count'] == len(captured['ptt_records'])
    assert result.value['status'] == 'partial'
    archived = result.value['source_record_archive']
    assert archived and all(row['reason'] == 'issuer_unverified' for row in archived if row['record']['social_channel'] == 'dcard')
    assert all(row in [item['record'] for item in archived] for row in captured['baseline_records']['dcard'])


def test_bare_request_uses_resolved_context_ticker_for_local_query(captured, monkeypatch):
    calls = install_capture(monkeypatch, captured)
    bare = captured['ticker'].split('.')[0]
    SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker(bare), {'data': captured['data']})
    assert calls == [(query, 3) for query in captured['candidate_query'].values()]


def test_missing_resolved_context_still_preserves_thirty_day_search(monkeypatch):
    calls = []
    monkeypatch.setattr(news_fetchers, 'fetch_google_news_rss', lambda query, limit: calls.append((query, limit)) or [])
    monkeypatch.setattr(news_fetchers, 'fetch_ptt_stock_sentiment', lambda *a, **k: [])
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('5314'), {'data': {'company_name': '世紀*'}})
    assert len(calls) == 3
    assert all(query.endswith(' when:30d') and limit == 3 for query, limit in calls)
    assert result.status == 'degraded_enrichment'
