from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from data_fetch.market_sources import official_company_legal_name as identity
from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
from source_content_selection import select_company_records

NOW = datetime(2026, 10, 10, 17, 40, tzinfo=ZoneInfo('Asia/Taipei'))
FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition'
INDEX = 'https://mops.twse.com.tw/mops/api/t05st01'
DETAIL = 'https://mops.twse.com.tw/mops/api/t59sb01_detail'
PDF = 'https://mopsov.twse.com.tw/nas/t59/t59sa01/9103_2026100901_FIM.pdf'


def _fixture():
    return json.loads((FIXTURES / 'tdr_mops_9103_20261010.json').read_text())


def _source(monkeypatch, fixture=None):
    from data_fetch.market_sources import tdr_mops_history as tdr
    # The saved source/roster fixture has a fixed acquisition date. Keep its
    # freshness clock fixed as well; wall-clock deadlines still use monotonic.
    monkeypatch.setattr(tdr.time, 'time', lambda: NOW.timestamp())
    f = deepcopy(fixture or _fixture())
    raw = json.dumps(f['selected_master'], ensure_ascii=False).encode()
    monkeypatch.setattr(identity, 'read_cached_listed_roster_bytes', lambda: (raw, {
        'fetched_at_epoch': NOW.timestamp() - 3600, 'cache_hit': True, 'stale': False,
        'source_payload_sha256': sha256(raw).hexdigest(),
        'source_url': identity.URLS['.TW']}))
    monkeypatch.setattr(tdr, 'read_cached_listed_roster_bytes', identity.read_cached_listed_roster_bytes)
    calls = []

    def get(url, **kwargs):
        calls.append(('GET', url, kwargs))
        if url == identity.URLS['.TW']:
            return httpx.Response(200, content=raw, request=httpx.Request('GET', url))
        if url == PDF:
            return httpx.Response(200, content=(FIXTURES / 'tdr_mops_9103_disposal_20261009_complete.pdf').read_bytes(),
                                  request=httpx.Request('GET', url))
        assert url == 'https://wwwc.twse.com.tw/rwd/zh/IIH/company/events'
        return httpx.Response(200, json=f['iih'], request=httpx.Request('GET', url))

    def post(url, **kwargs):
        calls.append(('POST', url, kwargs))
        if url.endswith('/ezsearch_query'):
            payload = {'status': 'success', 'data': []}
        elif url == INDEX:
            payload = f['october' if kwargs['json']['month'] == '10' else 'september']
        else:
            assert url == DETAIL
            payload = f['disposal' if kwargs['json']['enterDate'] == '1151009' else 'financial']
        return httpx.Response(200, json=payload, request=httpx.Request('POST', url))
    return get, post, calls


def test_public_history_recovers_tdr_originals_without_unsupported_general_index(monkeypatch):
    get, post, calls = _source(monkeypatch)
    rows, audit = fetch_recent_company_announcements('9103.TW', now=NOW, get=get, post=post)
    assert len(rows) == 2
    assert audit['record_count'] == 2
    assert audit['bilingual_variant_count'] == 1
    assert not any('IIH/' in url or 'ezsearch' in url for _, url, _ in calls)
    assert sum(method == 'POST' and url == INDEX for method, url, _ in calls) == 2
    disposal = next(row for row in rows if '股份處分' in row['title'])
    assert disposal['date'] == '2026-10-09T17:41:18+08:00'
    assert '13,144,512 美元' in disposal['text']
    assert disposal['source_document_url'] == PDF
    assert disposal['source_role'] == 'issuer_statement'
    financial = next(row for row in rows if '注意交易' in row['title'])
    assert '單位：仟美元' in financial['text']
    assert '-4,760' in financial['text']
    assert '2026年上半年' in financial['text']


def test_tdr_records_retain_checked_issuer_scope_and_reject_modified_body(monkeypatch):
    get, post, _ = _source(monkeypatch)
    rows, _ = fetch_recent_company_announcements('9103.TW', now=NOW, get=get, post=post)
    assert len(rows) == 2
    data = {'ticker': '9103.TW', 'company_name': '美德醫療-DR',
            'company_identity': {'official_name': '美德醫療-DR'}}
    accepted, _ = select_company_records(rows, data, cutoff=NOW)
    assert len(accepted) == 2
    altered = deepcopy(rows[0]); altered['text'] += '\n未經核對的新主張'
    accepted, _ = select_company_records([altered], data, cutoff=NOW)
    assert accepted == []
    accepted, _ = select_company_records(rows, {'ticker': '2236.TW', 'company_name': '百達-KY'}, cutoff=NOW)
    assert accepted == []


@pytest.mark.parametrize('part', ['index_issuer','original_issuer','attachment_date','future_date'])
def test_original_boundaries_do_not_replace_rejected_document_with_guessed_data(monkeypatch,part):
    f=_fixture()
    if part=='index_issuer':
        f['october']['result']['companyId']='9102'
    elif part=='original_issuer':
        f['disposal']['result']['data'][0][3]='其他公司股份有限公司'
    elif part=='attachment_date':
        f['disposal']['result']['data'][0][7]['url']=PDF.replace('20261009','20261008')
    else:
        f['october']['result']['data'][0][2]='115/10/11'
        f['october']['result']['data'][1][2]='115/10/11'
    get,post,calls=_source(monkeypatch,f)
    rows,_=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    assert not any('股份處分' in row['title']for row in rows)
    assert not any(url==PDF for _,url,_ in calls)


def test_partial_pdf_text_is_rejected_while_complete_direct_body_survives(monkeypatch):
    from data_fetch.market_sources import tdr_mops_history as tdr
    get,post,_=_source(monkeypatch)
    partial={'coverage_status':'partial','page_count':1,'pages':[{'text':'不完整 PDF 文字'}]}
    monkeypatch.setattr(tdr,'extract_pdf_pages',lambda *a,**k:partial)
    rows,audit=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    assert len(rows)==1 and '注意交易' in rows[0]['title']
    assert audit['rejected_reason_counts']=={'original_unverified':1}


def test_refused_index_stops_without_trying_credentials_or_other_routes(monkeypatch):
    get,post,calls=_source(monkeypatch)
    blocked=[]
    def refused(url,**kwargs):
        blocked.append(url)
        return httpx.Response(403,content=b'Forbidden',request=httpx.Request('POST',url))
    rows,audit=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=refused)
    assert rows==[] and audit['status']=='error' and audit['http_status']==403
    assert blocked==[INDEX] and calls==[]


@pytest.mark.parametrize('remove', ['tdr_mops_receipt','source_type','issuer_evidence_basis'])
def test_typed_identity_cannot_fall_back_to_company_text_if_metadata_is_removed(monkeypatch,remove):
    get,post,_=_source(monkeypatch)
    rows,_=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    row=deepcopy(rows[0]);row.pop(remove)
    data={'ticker':'9103.TW','company_name':'美德醫療-DR'}
    accepted,_=select_company_records([row],data,cutoff=NOW)
    assert accepted==[]


def test_no_shared_master_triggers_one_real_profile_fetch_without_cache_restamp(monkeypatch):
    from data_fetch.market_sources import tdr_mops_history as tdr
    get,post,calls=_source(monkeypatch)
    monkeypatch.setattr(tdr,'read_cached_listed_roster_bytes',lambda:None)
    rows,_=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    assert len(rows)==2
    assert sum(url==identity.URLS['.TW']for _,url,_ in calls)==1


def test_partial_http_response_is_not_archived_as_complete_200(monkeypatch):
    get,post,_=_source(monkeypatch)
    def partial(url,**kwargs):
        response=post(url,**kwargs)
        return httpx.Response(206,content=response.content,request=response.request)
    rows,audit=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=partial)
    assert rows==[] and audit['status']=='error'
