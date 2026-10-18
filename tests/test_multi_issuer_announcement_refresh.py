"""Synthetic native-seam fixtures; these are not production source evidence."""
import asyncio
import json

import pytest

from data_fetch.types import FetchRequest
from report_refresh_service import refresh_report_data_snapshot
from test_official_announcement_source_refresh import IssuerReplay, service, report
from test_report_refresh_acquisition_audit import init_db, events
from test_twse_announcement_progress import Replay

ISSUERS = {'1216.TW':'統一', '2308.TW':'台達電', '2881.TW':'富邦金',
           '2882.TW':'國泰金', '2885.TW':'元大金', '2891.TW':'中信金',
           '4763.TW':'材料*-KY', '6214.TW':'精誠', '9945.TW':'潤泰新'}


class MultiIssuerReplay(IssuerReplay):
    def __init__(self, monkeypatch, ticker, **kwargs):
        super().__init__(monkeypatch, **kwargs)
        self.code = ticker.split('.')[0]
        self.name = ISSUERS[ticker]
        from data_fetch.market_sources import mops_json_company_history as modern
        monkeypatch.setattr(modern, 'time', self.clock)
        for item in self.items:
            item['link'] = item['link'].replace('2851', self.code)
            item['company'] = self.name
        self.by_url = {item['link']:item for item in self.items}

    def collect(self, argv, end, **kwargs):
        from data_fetch.market_sources.twse_history_transport import ORDINARY_DETAIL_URL
        from data_fetch.market_sources.mops_json_company_history import DETAIL_TITLES
        if self.code == '1216' and argv[2] == ORDINARY_DETAIL_URL:
            self.calls.append(ORDINARY_DETAIL_URL)
            form = json.loads(argv[3]); seq = form['serialNumber']
            item = self.items[int(seq)-1]
            fields = [seq, '115/10/06', '14:15:38', '測試發言人', '發言人', '0000000000',
                      item['title'], '1', '115/10/06',
                      '本公司董事會決議辦理公開公告事項，此原文內容僅供隔離測試核對，不是正式來源資料。']
            payload = {'code':200, 'message':'查詢成功', 'result':{'marketName':'上市公司',
                'companyId':self.code, 'companyAbbreviation':self.name,
                'titles':[{'main':name} for name in DETAIL_TITLES], 'data':[fields]}}
            self.advance(self.detail_cost)
            return {'body':json.dumps(payload).encode(),
                'headers':b'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n',
                'metadata':json.dumps({'http_code':200,'url_effective':ORDINARY_DETAIL_URL,'num_redirects':0}).encode(),
                'process_started':True}, 0, None
        parts, rc, error = Replay.collect(self, argv, end, **kwargs)
        parts['body'] = (parts['body'].replace(b'2891', self.code.encode())
            .replace('中信金'.encode(), self.name.encode())
            .replace(json.dumps('中信金')[1:-1].encode(), json.dumps(self.name)[1:-1].encode()))
        return parts, rc, error


def identity(ticker):
    return {'ticker':ticker, 'company_name':ISSUERS[ticker], 'quote_type':'EQUITY',
            'company_identity':{'ticker':ticker, 'stock_id':ticker.split('.')[0],
                'official_name':ISSUERS[ticker], 'instrument_type':'EQUITY', 'forbidden_aliases':[]}}


@pytest.mark.parametrize('ticker', ISSUERS)
def test_registered_issuer_originals_admitted_before_canonical_sla(monkeypatch, ticker):
    init_db()
    replay = MultiIssuerReplay(monkeypatch, ticker)
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker(ticker),
        'official_announcements', context={'data':identity(ticker)}))
    assert len(result.data['recent_catalysts']) == 3, result.source_audit
    audit = result.source_audit[0]
    expected_calls = 5 if ticker == '1216.TW' else 4
    assert audit['status'] == 'success' and audit['http_request_count'] == expected_calls
    if ticker == '1216.TW':
        assert audit['parser_version'] == 'mops-company-json-original-v1'
        assert len(audit['requests']) == 2
        assert all(row['ticker'] == ticker for row in result.data['recent_catalysts'])
    else:
        assert audit['source_record_archive'][-1]['ticker'] == ticker
    assert len(replay.calls) == expected_calls
    assert len(events()) == 1 and events()[0]['record_count'] == 3


def test_report_recovery_preserves_analysis_and_unrelated_data(monkeypatch, tmp_path):
    init_db()
    ticker = '2891.TW'
    replay = MultiIssuerReplay(monkeypatch, ticker)
    storage, name, keys, old = report()
    old['ticker'] = ticker
    old['data'].update(identity(ticker))
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    result = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=service(), source='official_announcements', return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert len(replay.calls) == 4 and len(saved['data']['recent_catalysts']) == 3
    for key in ('analysis_evidence','analysis_completeness','oos_evaluation_inputs','rerun_context',
                'conclusion_generated_at','report_lint','final_audit','evidence_exit_gate',
                'content_credibility','report_conformance'):
        assert saved.get(key) == old.get(key), key
    for key in ('current_price','years','revenue_history','earnings_call','peer_discovery_results'):
        assert saved['data'].get(key) == old['data'].get(key), key
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert result['analysis_text_stale'] is True and len(events()) == 1


def test_partial_recovery_fetches_only_missing_bodies_and_keeps_failure(monkeypatch):
    init_db()
    ticker = '2891.TW'
    replay = MultiIssuerReplay(monkeypatch, ticker, count=37, detail_cost=.7)
    request = FetchRequest.from_ticker(ticker)
    first = asyncio.run(service().fetch_source_async(request, 'official_announcements',
        context={'data':identity(ticker)}))
    a = first.source_audit[0]
    assert a['status'] == 'degraded_enrichment' and a['progress_resume_possible'] is True
    old = first.data['recent_catalysts']
    assert 0 < len(old) < 37
    first_calls = len(replay.calls)
    replay.advance(61)
    second = asyncio.run(service().fetch_source_async(request, 'official_announcements',
        context={'data':identity(ticker)}))
    b = second.source_audit[0]
    assert b['status'] == 'success' and b['coverage_status'] == 'window_complete'
    assert len(second.data['recent_catalysts']) == 37
    assert not {r['link'] for r in old}.intersection(replay.calls[first_calls:])
    assert b['detail_cache_hit_count'] == len(old)
    assert b['detail_new_body_count'] == 37-len(old)
    assert b['body_fetched_at_epoch'] == a['body_fetched_at_epoch']
    assert [r['status'] for r in events()] == ['degraded_enrichment', 'success']


@pytest.mark.parametrize('conflict', ['stock_id','official_name','ticker','forbidden_alias','ETF'])
def test_new_issuer_identity_conflict_rejected_before_http(monkeypatch, conflict):
    init_db()
    replay = MultiIssuerReplay(monkeypatch, '2891.TW')
    data = identity('2891.TW')
    if conflict in {'stock_id','official_name','ticker'}:
        data['company_identity'][conflict] = {'stock_id':'2881','official_name':'富邦金','ticker':'2881.TW'}[conflict]
    elif conflict == 'ETF':
        data['quote_type'] = 'ETF'
    else:
        data['company_identity']['forbidden_aliases'] = ['中信金']
    with pytest.raises(RuntimeError):
        asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2891.TW'),
            'official_announcements', context={'data':data}))
    assert replay.calls == [] and events() == []


@pytest.mark.parametrize('part', ['packet','index','body'])
def test_another_registered_issuer_originals_cannot_be_substituted(monkeypatch, part):
    from copy import deepcopy
    import time
    from official_announcement_source_refresh import verify_value
    init_db()
    MultiIssuerReplay(monkeypatch, '2891.TW')
    result = asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2891.TW'),
        'official_announcements', context={'data':identity('2891.TW')}))
    audit = deepcopy(result.source_audit[0])
    archive = audit['source_record_archive']
    if part == 'packet':
        archive[-1]['ticker'] = '2881.TW'
    elif part == 'index':
        archive[-1]['indexes'][0]['request']['params']['code'] = '2881'
    else:
        archive[0]['url'] = archive[0]['url'].replace('2891','2881')
    with pytest.raises(ValueError):
        verify_value(result.data['recent_catalysts'], audit, identity('2891.TW'), deadline=time.monotonic()+2)
