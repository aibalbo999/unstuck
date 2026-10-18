from __future__ import annotations

from datetime import datetime

import httpx
import pytest

import official_financials_irengage_conference as irengage


PAGE = '''
<html><body>
  <form id="ConferenceForm"><input name="StockCode" value="3703"></form>
  <table>
    <tr><th>日期</th><th>時間</th><th>公司</th><th>地點</th><th>訊息</th><th>下載</th></tr>
    <tr>
      <td>2026/08/10</td><td>15:00</td><td>3703 欣陸</td><td>線上法說會</td>
      <td>本公司說明第二季經營成果。</td>
      <td>
        <button onclick="window.open('https://mopsov.twse.com.tw/server-java/FileDownLoad?step=9&amp;filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&amp;fileName=370320260810M001.pdf&amp;functionName=t100sb02_1', '_blank')">中文簡報</button>
        <button onclick="window.open('https://mopsov.twse.com.tw/server-java/FileDownLoad?step=9&amp;filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&amp;fileName=370320260810E001.pdf&amp;functionName=t100sb02_1', '_blank')">英文簡報</button>
        <button onclick="window.open('https://example.invalid/370320260810M002.pdf', '_blank')">不採用的外站簡報</button>
      </td>
    </tr>
    <tr><td>2026/10/20</td><td>14:00</td><td>3703 欣陸</td><td>線上</td><td>未來場次</td><td></td></tr>
    <tr><td>2026/10/17</td><td>14:00</td><td>3703 欣陸</td><td>線上</td><td>尚未開始</td><td></td></tr>
    <tr><td>2026/08/12</td><td>10:00</td><td>37030 其他公司</td><td>台北</td><td>相似代碼</td><td></td></tr>
  </table>
</body></html>
'''


def test_parser_keeps_exact_company_completed_event_and_official_decks_only():
    events, audit = irengage.parse_irengage_conference_page(
        PAGE, '3703', requested_year=2026,
        now=datetime.fromisoformat('2026-10-17T10:00:00+08:00'),
    )
    assert len(events) == 1
    event = events[0]
    assert event['ticker'] == '3703'
    assert event['company_name'] == '欣陸'
    assert event['date'] == '2026-08-10'
    assert event['summary'] == '本公司說明第二季經營成果。'
    assert [item['label'] for item in event['materials']] == ['中文簡報檔案', '英文簡報檔案']
    assert all('mopsov.twse.com.tw/server-java/FileDownLoad' in item['url'] for item in event['materials'])
    assert audit == {
        'raw_count': 1,
        'usable_count': 1,
        'rejected_count': 0,
        'rejected_reason_counts': {},
    }


def test_parser_requires_matching_form_and_recognized_table():
    wrong_company = PAGE.replace('value="3703"', 'value="3704"')
    with pytest.raises(irengage.SourceResponseError) as caught:
        irengage.parse_irengage_conference_page(wrong_company, '3703', requested_year=2026)
    assert caught.value.error_kind == 'parse_error'

    with pytest.raises(irengage.SourceResponseError) as caught:
        irengage.parse_irengage_conference_page('<html><body>no data</body></html>', '3703', requested_year=2026)
    assert caught.value.error_kind == 'parse_error'


def test_fetch_context_uses_bounded_public_request_and_returns_metadata_not_transcript(monkeypatch):
    calls = []
    observations = []
    monkeypatch.setattr(irengage, 'cooldown_state', lambda _key: {})
    monkeypatch.setattr(irengage, 'remember_success', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(irengage, 'record_observation', lambda *args, **kwargs: observations.append((args, kwargs)))

    def response(url, *, params, headers, timeout, provider):
        calls.append((url, params, timeout, provider))
        return httpx.Response(200, text=PAGE, request=httpx.Request('GET', url))

    monkeypatch.setattr(irengage, 'sync_get', response)
    monkeypatch.setattr(
        irengage,
        'shared_fetch',
        lambda _key, fetch, **_kwargs: (fetch(), {'cache_hit': False, 'fetched_at_epoch': 123.0}),
    )
    diagnostics = {}
    context = irengage.fetch_irengage_conference_context(
        '3703.TW', year=2026, diagnostics=diagnostics,
        now=datetime.fromisoformat('2026-10-17T10:00:00+08:00'),
    )

    assert calls == [(irengage.LIST_URL, {'StockCode': '3703', 'Year': '2026'}, (3, 8), irengage.PROVIDER)]
    assert len(observations) == 1
    assert context['ticker'] == '3703.TW'
    assert context['date'] == '2026-08-10'
    assert len(context['materials']) == 2
    assert context['transcript_available'] is False and context['transcript_excerpt'] == ''
    assert context['coverage_status'] == 'materials_available'
    assert diagnostics['actual_provider'] == irengage.PROVIDER
    assert diagnostics['http_request_sent'] is True


def test_mops_timeout_can_recover_its_notice_with_irengage_materials(monkeypatch):
    import official_financials
    import systex_conference_index
    from search_provider_runtime import SourceResponseError
    import data_fetch.earnings_call_fetcher as fetcher
    import data_fetch.market_sources.twse_iih_conference_notice as iih

    def fail_mops(*_args, **_kwargs):
        raise SourceResponseError('timeout')

    def iih_context(_ticker, *, diagnostics=None):
        if diagnostics is not None:
            diagnostics.update(status='success', actual_provider='TWSE IIH/MOPS official conference notice',
                               http_request_sent=True, http_request_count=1)
        return {
            'ticker': '3703.TW', 'date': '2026-08-10', 'period': '2026-08-10',
            'title': '欣陸法說會公告', 'summary': 'MOPS 公告正文保留。',
            'transcript_excerpt': '', 'transcript_available': False, 'materials': [],
            'source': 'TWSE IIH/MOPS official conference notice',
            'source_url': 'https://mops.twse.com.tw/example',
            'coverage_status': 'official_notice_text_only', 'coverage_notes': ['公告正文'],
        }

    def ir_context(_ticker, *, diagnostics=None, **_kwargs):
        if diagnostics is not None:
            diagnostics.update(status='success', actual_provider=irengage.PROVIDER,
                               http_request_sent=True, http_request_count=1,
                               fetched_at_epoch=456.0)
        return {
            'ticker': '3703.TW', 'date': '2026-08-10', 'period': '2026-08-10',
            'title': '欣陸法人說明會', 'summary': '簡報摘要。',
            'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'label': '中文簡報檔案', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad?fileName=370320260810M001.pdf'}],
            'source': irengage.PROVIDER, 'source_url': 'https://irengage.taiwanindex.com.tw/ConferenceList?StockCode=3703&Year=2026',
            'upstream_source': 'MOPS-derived IR Engage public listing',
            'coverage_status': 'materials_available', 'coverage_notes': [irengage.COVERAGE_NOTE],
        }

    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', fail_mops)
    monkeypatch.setattr(systex_conference_index, 'supports_systex', lambda _ticker: False)
    monkeypatch.setattr(iih, 'fetch_twse_iih_conference_notice', iih_context)
    monkeypatch.setattr(irengage, 'fetch_irengage_conference_context', ir_context)

    diagnostics = {}
    context = fetcher._fetch_official_index_context('3703.TW', diagnostics=diagnostics)

    assert context['source'] == irengage.PROVIDER
    assert context['summary'] == 'MOPS 公告正文保留。'
    assert context['materials'][0]['label'] == '中文簡報檔案'
    assert context['transcript_available'] is False
    assert diagnostics['actual_provider'] == irengage.PROVIDER
    assert diagnostics['coverage_status'] == 'materials_available'
    assert diagnostics['component_statuses']['MOPS']['error_kind'] == 'timeout'
    assert diagnostics['component_statuses']['IR_Engage']['status'] == 'success'


def test_irengage_fallback_checks_previous_year_when_current_year_is_empty(monkeypatch):
    from datetime import date
    import data_fetch.earnings_call_fetcher as fetcher

    years = []
    prior_year = date.today().year - 1

    def ir_context(_ticker, *, year=None, diagnostics=None, **_kwargs):
        years.append(year)
        if diagnostics is not None:
            diagnostics.update(status='valid_empty' if year != prior_year else 'success',
                               http_request_sent=True, http_request_count=1,
                               actual_provider=irengage.PROVIDER, event_kind='http_attempt')
        if year != prior_year:
            return {}
        return {
            'ticker': '3703.TW', 'date': f'{prior_year}-08-10', 'period': f'{prior_year}-08-10',
            'title': '欣陸法人說明會', 'summary': '前一年度公開法說資料。',
            'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'label': '中文簡報檔案', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad?fileName=370320250810M001.pdf'}],
            'source': irengage.PROVIDER,
            'source_url': f'https://irengage.taiwanindex.com.tw/ConferenceList?StockCode=3703&Year={prior_year}',
            'upstream_source': 'MOPS-derived IR Engage public listing',
            'coverage_status': 'materials_available', 'coverage_notes': [irengage.COVERAGE_NOTE],
        }

    monkeypatch.setattr(irengage, 'fetch_irengage_conference_context', ir_context)
    diagnostics = {'http_request_count': 0, 'component_statuses': {}}
    context = fetcher._fetch_irengage_fallback('3703.TW', {}, diagnostics)

    assert years == [date.today().year, prior_year]
    assert context['date'] == f'{prior_year}-08-10'
    assert diagnostics['http_request_count'] == 2
    assert diagnostics['component_statuses']['IR_Engage']['years_checked'] == years
