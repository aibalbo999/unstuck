"""Full exact TXC originals reach the public consumer without becoming annual facts."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
from copy import deepcopy
from hashlib import sha256
import gzip,time
import pytest
from data_fetch.issuer_news_provider import IssuerNewsProvider
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL
from source_content_selection import select_company_records

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,12,2,55,tzinfo=timezone.utc).timestamp()
INDEX='https://www.txccorp.com/news/'
REVENUE='https://www.txccorp.com/news-detail/consolidated-revenue__47/'
INCOME='https://www.txccorp.com/news-detail/73__52/'
def raw(name):return gzip.decompress((F/name).read_bytes())
def bodies():return {ROSTER_URL:raw('nanya2408_complete_roster_20261011.json.gz'),INDEX:raw('txc3042_news_index_20261012.html.gz'),REVENUE:raw('txc3042_revenue47_20261005.html.gz'),INCOME:raw('txc3042_income52_20260915.html.gz')}
def setup_http(monkeypatch,source,calls,warm):
    def read(http,url):
        calls.append(url);body=source[url];cached=url==ROSTER_URL or warm[0]
        c={'url':url,'fetched_at_epoch':NOW-10,'cache_hit':cached,'http_request_sent':not cached,'stale':False}
        if url==ROSTER_URL:
            c.update(fetched_at_epoch=NOW-1000,evidence_kind='cached_complete_source_payload_verified_by_digest',http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=url,source_payload_sha256=sha256(body).hexdigest(),source_payload_bytes=len(body))
        else:c.update(http_status=200);http.http_request_count+=int(not cached)
        http.components.append(c);return body
    monkeypatch.setattr(time,'time',lambda:NOW);monkeypatch.setattr(IssuerNewsHttp,'get',read)

def test_public_provider_recovers_full_dated_self_reports_without_annual_financial_mutation(monkeypatch):
    calls=[];setup_http(monkeypatch,bodies(),calls,[False]);p=IssuerNewsProvider();req=SimpleNamespace(ticker='3042.TW')
    assert p.supports(req)
    data={'ticker':'3042.TW','instrument_type':'EQUITY','company_name':'晶技 / TXC Corporation','fcf_history':[1,2],'ttm_revenue':3};before=deepcopy(data)
    result=p.fetch(req,{'data':data});assert result.status=='success' and result.audit['record_count']==2
    assert calls==[ROSTER_URL,INDEX,REVENUE,INCOME] and result.audit['http_request_count']==3 and data==before
    chosen,audit=select_company_records(result.value,data,cutoff=NOW);assert len(chosen)==2
    assert {r['date']for r in chosen}=={'2026-10-05','2026-09-15'}
    assert all(r['source_role']=='issuer_statement' and r['event_assessment']=='not_assessed' and r['financial_assurance']=='not_verified_as_audited' for r in chosen)
    assert '1,415,241' in chosen[0]['text'] and '股票代碼 3042' in chosen[0]['text']
    assert '279,155' in chosen[1]['text'] and '115年08月' in chosen[1]['text'] and ' | ' in chosen[1]['text']

@pytest.fixture
def replay(monkeypatch):
    from data_fetch.market_sources import txc_issuer_news as module
    source=bodies();calls=[];warm=[False];setup_http(monkeypatch,source,calls,warm)
    data={'ticker':'3042.TW','instrument_type':'EQUITY','company_name':'晶技 / TXC Corporation'}
    return SimpleNamespace(module=module,bodies=source,calls=calls,warm=warm,data=data,fetch=lambda:module.fetch_recent_news(now=datetime.fromtimestamp(NOW,timezone.utc)))

@pytest.mark.parametrize('key',['instrument_type','quote_type','quoteType'])
def test_saved_originals_reject_every_explicit_instrument_conflict(replay,key):
    records,_=replay.fetch();selected,_=select_company_records(records,{**replay.data,key:'ETF'},cutoff=NOW);assert not selected

@pytest.mark.parametrize('field',['title','text','date','publisher','financial_assurance','event_assessment','original_id','hash','epoch','bytes'])
def test_saved_full_original_or_semantics_tampering_cannot_pass(replay,field):
    records,_=replay.fetch();record=deepcopy(records[0]);receipt=record['issuer_news_receipt']
    if field in {'title','text','date','publisher','financial_assurance','event_assessment'}:record[field]='changed'
    elif field=='original_id':receipt['original_id']='73__52'
    else:
        article=receipt['source_record_archive']['article']
        if field=='hash':article['raw_response_sha256']='0'*64
        elif field=='epoch':article['retrieved_at']=True
        else:article['raw_response_bytes']+=1
    selected,_=select_company_records([record],replay.data,cutoff=NOW);assert not selected

def test_truncated_search_description_is_not_repaired_or_used_as_body(replay):
    source=replay.bodies[INCOME]
    with pytest.raises(UnicodeDecodeError):source.decode('utf8')
    records,_=replay.fetch();income=records[1]
    assert '\ufffd' not in income['text'] and all(not 0xD800<=ord(c)<=0xDFFF for c in income['text'])
    assert '註：稅前每股盈餘係以當月底股數計算' in income['text']

def test_invalid_encoding_in_full_body_cannot_be_promoted(replay):
    h=replay;h.bodies[REVENUE]=h.bodies[REVENUE].replace(b'<span lang="EN-US">1,415,241</span>',b'<span lang="EN-US">1,415,241\xe8\xa8</span>',1)
    records,audit=h.fetch();assert not records and audit['status']=='error'
    assert h.calls==[ROSTER_URL,INDEX,REVENUE]

def test_income_table_column_headers_and_missing_cells_are_rejected(replay):
    h=replay;h.bodies[INCOME]=h.bodies[INCOME].replace('>115年08月<'.encode(),'>114年08月<'.encode(),1)
    records,audit=h.fetch();assert len(records)==1 and audit['status']=='degraded_enrichment'

def test_wrong_master_refuses_before_news(replay):
    h=replay;h.bodies[ROSTER_URL]=h.bodies[ROSTER_URL].replace('台灣晶技股份有限公司'.encode(),'其他晶技股份有限公司'.encode())
    records,audit=h.fetch();assert not records and h.calls==[ROSTER_URL]

def test_warm_read_holds_original_epochs_and_is_not_another_HTTP_success(replay):
    cold,_=replay.fetch();replay.warm[0]=True;replay.calls.clear();warm,audit=replay.fetch()
    assert warm==cold and audit['status']=='skipped_fresh_cache' and audit['http_request_count']==0 and audit['fetched_at_epoch']==NOW-1000

@pytest.mark.parametrize('url',[REVENUE+'?x=1',REVENUE+'#x',REVENUE.replace('https:','http:'),REVENUE.replace('www.','evil.'),REVENUE.replace('/news-detail/','/jp/news-detail/'),REVENUE.replace('__47','__047')])
def test_exact_transport_rejects_unobserved_aliases(replay,url):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):replay.module.url_contract(url)

def test_expired_deadline_does_not_publish_the_second_completed_response(replay,monkeypatch):
    clock=[0.];get=IssuerNewsHttp.get;monkeypatch.setattr(replay.module.time,'monotonic',lambda:clock[0])
    def late(http,url):
        raw=get(http,url)
        if url==INCOME:clock[0]=21.
        return raw
    monkeypatch.setattr(IssuerNewsHttp,'get',late)
    records,audit=replay.fetch();assert len(records)==1 and audit['status']=='degraded_enrichment' and audit['error_kind']=='timeout'

def test_historical_cards_do_not_start_detail_requests(replay):
    replay.bodies[INDEX]=replay.bodies[INDEX].replace(b'Oct 2026',b'Aug 2026').replace(b'Sep 2026',b'Aug 2026')
    records,audit=replay.fetch();assert not records and replay.calls==[ROSTER_URL,INDEX]

def test_visible_publication_day_cannot_be_replaced_by_monthly_period(replay):
    old=b'<div class="day">15</div>';assert old in replay.bodies[INCOME]
    replay.bodies[INCOME]=replay.bodies[INCOME].replace(old,b'<div class="day">14</div>',1)
    records,audit=replay.fetch();assert len(records)==1 and audit['status']=='degraded_enrichment'

@pytest.mark.parametrize('context',[{'ticker':'3042.TWO'},{'ticker':'3042.TW','company_identity':{'official_ubn':'09461025'}},
                                  {'ticker':'3042.TW','company_identity':{'forbidden_aliases':['TXC']}}])
def test_master_bound_receipt_cannot_override_explicit_company_or_market_conflict(replay,context):
    records,_=replay.fetch();selected,_=select_company_records(records,context,cutoff=NOW);assert not selected

def test_invalid_UTF8_in_identity_metadata_is_rejected(replay):
    marker=b'<meta property="og:title" content="';assert marker in replay.bodies[REVENUE]
    replay.bodies[REVENUE]=replay.bodies[REVENUE].replace(marker,marker+b'\xe8\xa8',1)
    records,audit=replay.fetch();assert not records and audit['status']=='error'

def test_prompt_does_not_include_local_original_receipts(replay):
    from prompt_evidence import prompt_evidence_copy
    records,_=replay.fetch();view=prompt_evidence_copy({'recent_catalysts':records})
    assert 'source_record_archive' not in str(view) and 'raw_response_path' not in str(view)

@pytest.mark.parametrize('field',['instrument_type','quote_type','quoteType'])
def test_source_only_instrument_conflict_stops_before_acquisition(replay,field):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    data={**replay.data,field:'ETF'};old={'ticker':'3042.TW','data':data,'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]};calls=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):calls.append(1);raise AssertionError('unsupported identity must stop before acquisition')
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'issuer_news',Service()))
    assert exc.value.status_code==400 and not calls


@pytest.fixture(autouse=True)
def replay_issuer_datetime(monkeypatch):
    from data_fetch.market_sources import issuer_news
    class ReplayDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(NOW, tz or timezone.utc)
    monkeypatch.setattr(issuer_news, 'datetime', ReplayDateTime)
