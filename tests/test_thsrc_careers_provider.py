"""Normal provider preserves source lifetimes, issuer identity and failures."""
from copy import deepcopy
from datetime import datetime
import json
import time
from zoneinfo import ZoneInfo

import pytest

from test_thsrc_official_careers import fixtures


def issuer():
    from official_response_evidence import archive_response
    from data_fetch.market_sources import thsrc_careers as s
    from data_fetch.market_sources.official_company_legal_name import parse_roster, select_legal_name, URLS
    now = time.time(); day = datetime.fromtimestamp(now, ZoneInfo('Asia/Taipei')).date()
    roc = f'{day.year - 1911:03d}{day.month:02d}{day.day:02d}'
    rows = [{'公司代號': str(n), '公司名稱': f'測試{n}股份有限公司', '公司簡稱': f'測{n}',
             '出表日期': roc, '營利事業統一編號': str(20000000 + n), '網址': 'https://example.com'}
            for n in range(1000, 1800)]
    rows.append({'公司代號': '2633', '公司名稱': s.LEGAL, '公司簡稱': s.SHORT, '出表日期': roc,
                 '營利事業統一編號': s.UBN, '網址': 'http://www.thsrc.com.tw'})
    raw = json.dumps(rows, ensure_ascii=False).encode()
    archive_response(raw, source_url=URLS['.TW'], retrieved_at=now, http_status=200)
    return {**select_legal_name(parse_roster(raw, '.TW'), s.TICKER, s.SHORT, today=day), 'fetched_at_epoch': now}


def context():
    from data_fetch.market_sources import thsrc_careers as s
    return {'ticker': s.TICKER, 'company_name': s.SHORT, 'quote_type': 'EQUITY',
            'company_identity': {'ticker': s.TICKER, 'official_name': s.SHORT, 'instrument_type': 'EQUITY'}}


def test_normal_provider_replays_exact_employer_and_skips_blocked_keyword_search(monkeypatch):
    from data_fetch.market_sources import thsrc_careers as s, official_company_legal_name as master
    from data_fetch.market_sources.thsrc_careers_transport import ThsrcCareersHttp
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest
    from data_trust import source_record_count
    from alternative_source_refresh import guard_alternative_result
    anchor = issuer(); originals, _, _ = fixtures(); calls = []
    monkeypatch.setattr(master, 'get_official_legal_name', lambda *a: anchor)
    def read(self, key):
        calls.append(key); self.http_request_count += 1
        self.components.append({'cache_hit': False, 'http_request_sent': True, 'http_status': 200})
        i = {'index': 0, 'tenant': 1, 'listing': 2}.get(key, 3)
        return deepcopy(originals[i])
    monkeypatch.setattr(ThsrcCareersHttp, 'get_receipt', read)
    monkeypatch.setattr(AlternativeJobOpeningsProvider, '_fetch_uncached',
                        lambda *a: pytest.fail('verified official sample must not trigger generic keyword search'))
    request = FetchRequest.from_ticker(s.TICKER); provider = AlternativeJobOpeningsProvider(); data = context()
    first = provider.fetch(request, {'data': data}); second = provider.fetch(request, {'data': data})
    assert first.status == second.status == 'success' and len(calls) == 4
    assert first.audit['record_count'] == source_record_count('alternative_data', {**data, 'alternative_data': first.value}) == 1
    assert second.audit['http_request_sent'] is False and second.audit['http_request_count'] == 0
    assert second.audit['cache_hit'] is True
    assert second.audit['fetched_at_epoch'] == first.audit['fetched_at_epoch']
    assert guard_alternative_result(first, data).status == 'success'
    assert guard_alternative_result(second, data).status == 'success'
    from prompt_builder import format_data_for_prompt
    text = format_data_for_prompt({**data, 'alternative_data': first.value})
    assert 'body_b64' not in text and 'scriptSessionId' not in text
    assert '車輛維修' in text and 'published_date' in text


@pytest.mark.parametrize('field,value', [('ticker', '2330.TW'), ('official_ubn', '12345678'),
    ('legal_name', '高鐵工業股份有限公司'), ('official_short_name', '高鐵'),
    ('response_sha256', 'a' * 64), ('as_of', '2025-01-01')])
def test_issuer_receipt_must_replay_current_full_roster(field, value):
    from data_fetch.market_sources import thsrc_careers as s
    anchor = issuer(); assert s.verified_issuer(anchor)
    anchor[field] = value; assert not s.verified_issuer(anchor)


@pytest.mark.parametrize('change', [
    lambda d: d.update(ticker='2330.TW'), lambda d: d.update(quote_type='ETF'),
    lambda d: d.update(quoteType='ETF'), lambda d: d.update(stock_id='2330'),
    lambda d: d['company_identity'].update(ticker='2330.TW'),
    lambda d: d['company_identity'].update(official_ubn='12345678'),
    lambda d: d['company_identity'].update(legal_name='高鐵子公司股份有限公司'),
    lambda d: d['company_identity'].update(instrument_type='ETF'),
    lambda d: d.update(company_name='高鐵工業'),
])
def test_conflicting_context_cannot_load_official_cache_or_send_requests(monkeypatch, change):
    from data_fetch.thsrc_careers_provider import thsrc_context_result
    from data_fetch.types import FetchRequest
    import shared_provider_cache
    data = context(); change(data)
    monkeypatch.setattr(shared_provider_cache, 'shared_fetch', lambda *a, **k: pytest.fail('invalid issuer loaded cache'))
    assert thsrc_context_result(FetchRequest.from_ticker('2633.TW'), {'data': data}) is None


def test_outer_cache_cannot_renew_raw_original_lifetime(monkeypatch):
    from data_fetch import thsrc_careers_provider as provider
    from data_fetch.market_sources import thsrc_careers as s
    from data_fetch.types import FetchRequest
    import shared_provider_cache
    anchor = issuer(); originals, _, _ = fixtures(); value = s.parse_jobs(originals)
    payload = {'source': 'alternative_data', 'provider': provider.CANONICAL_PROVIDER, 'status': 'success',
               'value': {'company_legal_name_evidence': anchor, 'job_openings_official': value},
               'audit': {'record_count': 1, 'fetched_at_epoch': value['fetched_at_epoch']}}
    monkeypatch.setattr(shared_provider_cache, 'shared_fetch', lambda *a, **k: (
        payload, {'cache_hit': True, 'fetched_at_epoch': time.time()}))
    monkeypatch.setattr(s.time, 'time', lambda: max(r['fetched_at_epoch'] for r in originals) + 1801)
    result = provider.thsrc_context_result(FetchRequest.from_ticker(s.TICKER), {'data': context()})
    assert result.status == 'unavailable' and result.audit['record_count'] == 0
    assert result.audit['http_request_count'] == 0 and result.audit['http_request_sent'] is False


def test_failed_official_attempt_is_preserved_when_other_sources_are_tried(monkeypatch):
    from data_fetch import thsrc_careers_provider as provider
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.types import FetchRequest, ProviderResult
    from alternative_source_refresh import record_related_alternative_attempts
    import provider_sla
    failure = ProviderResult('alternative_data', provider.CANONICAL_PROVIDER, 'unavailable', value={}, audit={
        'source': 'alternative_data', 'provider': provider.CANONICAL_PROVIDER, 'status': 'unavailable',
        'record_count': 0, 'http_request_sent': True, 'http_request_count': 1, 'http_status': 429})
    fallback = ProviderResult('alternative_data', provider.CANONICAL_PROVIDER, 'unavailable', value={'old': 'kept'},
        audit={'source': 'alternative_data', 'provider': provider.CANONICAL_PROVIDER, 'status': 'unavailable', 'record_count': 0})
    monkeypatch.setattr(provider, 'thsrc_context_result', lambda *a: failure)
    monkeypatch.setattr(AlternativeJobOpeningsProvider, '_fetch_uncached', lambda *a: fallback)
    result = AlternativeJobOpeningsProvider().fetch(FetchRequest.from_ticker('2633.TW'), {'data': context()})
    child, = result.audit['related_entries']; assert child['http_status'] == 429
    assert child['provider'] == 'THSRC official public careers' and result.value['old'] == 'kept'
    recorded = []; monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda x: recorded.extend(x))
    record_related_alternative_attempts(result); assert recorded == [child]
