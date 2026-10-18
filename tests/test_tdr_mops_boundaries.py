from copy import deepcopy
from pathlib import Path
import sys, json, time
import pytest
from test_tdr_mops_history import _source, _fixture, NOW, PDF
from data_fetch.market_sources import tdr_mops_history as tdr, twse_history_transport as transport
from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
from source_content_selection import select_company_records
from news_freshness_policy import apply_news_freshness
from runtime_paths import current_runtime_paths

DATA={'ticker':'9103.TW','company_name':'美德醫療-DR','company_identity':{'official_name':'美德醫療-DR'}}

def collected(monkeypatch):
    get,post,_=_source(monkeypatch)
    return fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)[0]

def test_real_pdf_content_type_is_admitted_on_exact_pdf_route(monkeypatch):
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    for k in transport.PROXY_ENV: monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:{})
    p={'body':b'%PDF-1.7\ncomplete mock PDF','headers':b'HTTP/2 200\r\nContent-Type: application/pdf\r\n\r\n',
       'metadata':json.dumps({'http_code':200,'url_effective':PDF,'num_redirects':0}).encode(),'process_started':True}
    monkeypatch.setattr(transport,'collect_capped_process',lambda *a,**k:(p,0,None))
    assert transport.BoundedHistoryHttp(time.monotonic()+20).get(PDF).status_code==200

def test_produced_records_survive_actual_freshness_projection_and_second_selection(monkeypatch):
    rows=collected(monkeypatch)
    data=deepcopy(DATA)
    apply_news_freshness(data,records=rows,cutoff=NOW)
    assert len(data['recent_catalysts'])==len(rows)==2, data
    accepted,_=select_company_records(data['recent_catalysts'],data,cutoff=NOW)
    assert len(accepted)==2

def test_recomputed_projection_digest_cannot_change_source_currency_and_amount(monkeypatch):
    rows=collected(monkeypatch)
    row=deepcopy(next(x for x in rows if '注意交易' in x['title']))
    assert '仟美元' in row['text'] and '-4,760' in row['text']
    row['text']=row['text'].replace('仟美元','仟新台幣').replace('-4,760','4,760')
    row['summary']=row['text'][:1500]
    row['tdr_mops_receipt']['parsed_content_sha256']=tdr._digest(row)
    accepted,_=select_company_records([row],DATA,cutoff=NOW)
    assert accepted==[], accepted

def test_unavailable_original_cannot_remain_verified_saved_record(monkeypatch):
    rows=collected(monkeypatch)
    row=deepcopy(next(x for x in rows if '注意交易' in x['title']))
    for key in ('index_response_sha256','detail_response_sha256'):
        (current_runtime_paths().cache_dir/'official-response-evidence'/(row['tdr_mops_receipt'][key]+'.gz')).unlink(missing_ok=True)
    accepted,_=select_company_records([row],DATA,cutoff=NOW)
    assert accepted==[], accepted

def test_late_detail_parse_does_not_append_record_past_parent_deadline(monkeypatch):
    get,post,_=_source(monkeypatch)
    clock=[100.]
    monkeypatch.setattr(tdr.time,'monotonic',lambda:clock[0])
    original=tdr._detail
    def late(row,*a,**kw):
        answer=original(row,*a,**kw)
        if '注意交易' in row[4]: clock[0]=121.
        return answer
    monkeypatch.setattr(tdr,'_detail',late)
    rows,audit=tdr.fetch_tdr_announcements('9103.TW',now=NOW,get=get,post=post,deadline=120.)
    assert not any('注意交易' in x['title'] for x in rows), audit

@pytest.mark.parametrize('identity',[False, [], 0, ''])
def test_explicit_malformed_identity_is_not_missing(monkeypatch,identity):
    row=collected(monkeypatch)[0]
    data={**DATA,'company_identity':identity}
    accepted,_=select_company_records([row],data,cutoff=NOW)
    assert accepted==[]

def test_forbidden_alias_with_html_star_spaces_is_not_removed_from_blocklist(monkeypatch):
    row=collected(monkeypatch)[0]
    data={**DATA,'company_identity':{'official_name':'美德醫療-DR','forbidden_aliases':['<b>* 美德醫療-DR *</b>']}}
    accepted,_=select_company_records([row],data,cutoff=NOW)
    assert accepted==[]

def test_distinct_direct_announcements_do_not_share_generic_link_and_disappear(monkeypatch):
    import httpx
    from test_tdr_mops_history import INDEX, DETAIL
    f=_fixture()
    second=deepcopy(f['september']['result']['data'][0])
    second[2]='115/09/25'; second[3]='15:10:00'; second[4]='第二件不同重大訊息公告'
    second[5]['parameters']['enterDate']='1150925';second[5]['parameters']['serialNumber']='2'
    f['september']['result']['data'].append(second)
    get,original_post,_=_source(monkeypatch,f)
    def post(url,**kwargs):
        if url==DETAIL and kwargs['json']['enterDate']=='1150925':
            p=deepcopy(f['financial']); row=p['result']['data'][0]
            row[1]=2;row[2]='民國115年9月25日';row[4]=second[4]
            return httpx.Response(200,json=p,request=httpx.Request('POST',url))
        return original_post(url,**kwargs)
    rows,_=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    assert len(rows)==3
    selected,_=select_company_records(rows,DATA,cutoff=NOW)
    assert len(selected)==3
    data=deepcopy(DATA)
    apply_news_freshness(data,records=rows,cutoff=NOW)
    # Count also rejected records to isolate URL dedupe from the separate UTC bug.
    retained=data['recent_catalysts']+data['identity_rejected_catalysts']
    assert len(retained)==3, [(r['title'],r['link']) for r in retained]


@pytest.mark.parametrize('field',['master_response_sha256','pdf_response_sha256'])
def test_every_required_original_must_still_exist(monkeypatch,field):
    row=deepcopy(next(x for x in collected(monkeypatch) if '股份處分' in x['title']))
    (current_runtime_paths().cache_dir/'official-response-evidence'/(row['tdr_mops_receipt'][field]+'.gz')).unlink()
    accepted,_=select_company_records([row],DATA,cutoff=NOW)
    assert accepted==[]


def test_recomputed_pdf_projection_cannot_replace_disposal_amount(monkeypatch):
    row=deepcopy(next(x for x in collected(monkeypatch) if '股份處分' in x['title']))
    row['text']=row['text'].replace('13,144,512','99,999,999')
    row['summary']=row['text'][:1500]
    row['tdr_mops_receipt']['parsed_content_sha256']=tdr._digest(row)
    assert select_company_records([row],DATA,cutoff=NOW)[0]==[]


def test_changed_date_cannot_be_hidden_by_recomputed_projection_digest(monkeypatch):
    row=deepcopy(collected(monkeypatch)[0])
    row['date']='2026-10-09T09:41:19+00:00'
    row['tdr_mops_receipt']['parsed_content_sha256']=tdr._digest(row)
    assert select_company_records([row],DATA,cutoff=NOW)[0]==[]


def test_pdf_reader_failure_rejects_saved_evidence_without_crashing_selector(monkeypatch):
    from source_pdf_reader import SourcePdfError
    row=next(x for x in collected(monkeypatch) if '股份處分' in x['title'])
    def fail(*a,**k):raise SourcePdfError('worker_diagnostic')
    monkeypatch.setattr(tdr,'extract_pdf_pages',fail)
    assert select_company_records([row],DATA,cutoff=NOW)[0]==[]


def test_receipt_stays_outside_prompt_while_original_text_and_url_remain(monkeypatch):
    from prompt_evidence import prompt_evidence_copy
    rows=collected(monkeypatch)
    before=deepcopy(rows)
    projected=prompt_evidence_copy({'recent_catalysts':rows})
    assert rows==before
    for raw,visible in zip(rows,projected['recent_catalysts']):
        assert 'tdr_mops_receipt' not in visible
        assert visible['text']==raw['text'] and visible['source_document_url']==raw['source_document_url']
        assert 'index_row' not in json.dumps(visible,ensure_ascii=False)
