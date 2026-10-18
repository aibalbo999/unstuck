"""The exact exchange-bound issuer's complete original must reach the public provider."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
import gzip,time
from copy import deepcopy
from hashlib import sha256
import pytest
from data_fetch.issuer_news_provider import IssuerNewsProvider
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL
from source_content_selection import select_company_records

F=Path(__file__).parent/'fixtures/source_acquisition'
NOW=datetime(2026,10,12,2,20,tzinfo=timezone.utc).timestamp()
INDEX='https://www.chromaate.com/en/newsroom/news_list'
ARTICLE='https://www.chromaate.com/en/newsroom/news1189'
def raw(name):return gzip.decompress((F/name).read_bytes())


def test_public_provider_recovers_the_complete_dated_original_with_no_future_event_claim(monkeypatch):
    monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={ROSTER_URL:raw('nanya2408_complete_roster_20261011.json.gz'),
            INDEX:raw('chroma2360_news_index_20261012.html.gz'),ARTICLE:raw('chroma2360_news1189_20261007.html.gz')}
    calls=[]
    def read(http,url):
        calls.append(url);body=bodies[url]
        c={'url':url,'fetched_at_epoch':NOW-10,'cache_hit':url==ROSTER_URL,'http_request_sent':url!=ROSTER_URL,'stale':False}
        if url==ROSTER_URL:
            c.update(fetched_at_epoch=NOW-1000,evidence_kind='cached_complete_source_payload_verified_by_digest',
                     http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=url,
                     source_payload_sha256=sha256(body).hexdigest(),source_payload_bytes=len(body))
        else:c.update(http_status=200);http.http_request_count+=1
        http.components.append(c);return body
    monkeypatch.setattr(IssuerNewsHttp,'get',read)
    p=IssuerNewsProvider();req=SimpleNamespace(ticker='2360.TW')
    assert p.supports(req),'public issuer provider must admit exact exchange-bound 2360'
    data={'ticker':'2360.TW','instrument_type':'EQUITY','company_name':'致茂 / Chroma ATE Inc.'}
    result=p.fetch(req,{'data':data})
    assert result.status=='success' and result.audit['record_count']==1
    assert calls==[ROSTER_URL,INDEX,ARTICLE] and result.audit['http_request_count']==2
    record=result.value[0];assert record['date']=='2026-10-07' and record['content_truncated'] is False
    assert record['source_role']=='issuer_statement' and record['event_assessment']=='not_assessed'
    assert 'will showcase' in record['text'] and 'October 14' in record['text']
    selected,audit=select_company_records([record],data,cutoff=datetime.fromtimestamp(NOW,timezone.utc))
    assert len(selected)==1 and audit['usable_count']==1 and selected[0]['content_coverage']=='text_available'


@pytest.fixture
def replay(monkeypatch):
    from data_fetch.market_sources import chroma_issuer_news as chroma
    monkeypatch.setattr(time,'time',lambda:NOW)
    bodies={ROSTER_URL:raw('nanya2408_complete_roster_20261011.json.gz'),
            INDEX:raw('chroma2360_news_index_20261012.html.gz'),ARTICLE:raw('chroma2360_news1189_20261007.html.gz')}
    calls=[];warm=[False]
    def read(http,url):
        calls.append(url);body=bodies[url]
        cached=url==ROSTER_URL or warm[0]
        c={'url':url,'fetched_at_epoch':NOW-10,'cache_hit':cached,'http_request_sent':not cached,'stale':False}
        if url==ROSTER_URL:
            c.update(fetched_at_epoch=NOW-1000,evidence_kind='cached_complete_source_payload_verified_by_digest',
                     http_status_observed=False,cache_source='official-company-roster:v2:.TW',source_url=url,
                     source_payload_sha256=sha256(body).hexdigest(),source_payload_bytes=len(body))
        else:c.update(http_status=200);http.http_request_count+=int(not cached)
        http.components.append(c);return body
    monkeypatch.setattr(IssuerNewsHttp,'get',read)
    data={'ticker':'2360.TW','instrument_type':'EQUITY','company_name':'致茂 / Chroma ATE Inc.'}
    def fetch(now=None):return chroma.fetch_recent_news(now=now or datetime.fromtimestamp(NOW,timezone.utc))
    return SimpleNamespace(module=chroma,bodies=bodies,calls=calls,warm=warm,data=data,fetch=fetch)


@pytest.mark.parametrize('field',['title','body','summary','date','publisher','original_id','policy','bool_epoch','future_epoch','bytes','archive_url','hash'])
def test_modified_original_or_record_cannot_pass_exact_replay(replay,field):
    h=replay;records,audit=h.fetch();assert audit['status']=='success';record=deepcopy(records[0]);receipt=record['issuer_news_receipt']
    if field in ('title','body','summary'):
        key='text'if field=='body'else field;record[key]+=' invented'
    elif field=='date':record['date']='2026-10-08'
    elif field=='publisher':record['publisher']='Different Publisher'
    elif field=='original_id':receipt['original_id']='1'
    elif field=='policy':receipt['policy']='first-party-issuer-news-v1'
    else:
        original=receipt['source_record_archive']['article']
        if field=='bool_epoch':original['retrieved_at']=True
        elif field=='future_epoch':original['retrieved_at']=NOW+1
        elif field=='bytes':original['raw_response_bytes']+=1
        elif field=='archive_url':original['source_url']=ARTICLE+'?different=1'
        else:original['raw_response_sha256']='0'*64
    assert h.module.verified_record(record,h.data,today=datetime.fromtimestamp(NOW,timezone.utc).date())is None
    assert len(h.calls)==3


@pytest.mark.parametrize('context',[{'ticker':'2360.TWO'},{'ticker':'2379.TW'},{'ticker':'2360.TW','instrument_type':'ETF'},
                                 {'ticker':'2360.TW','company_identity':{'official_name':'瑞昱'}},
                                 {'ticker':'2360.TW','company_identity':{'forbidden_aliases':['CHROMA']}}])
def test_original_cannot_certify_another_company_market_or_instrument(replay,context):
    records,_=replay.fetch()
    assert replay.module.verified_record(records[0],context,today=datetime.fromtimestamp(NOW,timezone.utc).date())is None


@pytest.mark.parametrize('key',['quote_type','quoteType'])
def test_saved_original_selection_rejects_explicit_quote_alias_conflicts(replay,key):
    records,_=replay.fetch()
    data={**replay.data,key:'ETF'}
    selected,_=select_company_records(records,data,cutoff=datetime.fromtimestamp(NOW,timezone.utc))
    assert not selected


def test_wrong_current_master_stops_before_news_or_detail(replay):
    h=replay;h.bodies[ROSTER_URL]=h.bodies[ROSTER_URL].replace('致茂電子股份有限公司'.encode(),'其他電子股份有限公司'.encode())
    records,audit=h.fetch();assert not records and audit['status']=='error'
    assert h.calls==[ROSTER_URL] and audit['http_request_count']==0


def test_visible_and_structured_publication_dates_must_agree(replay):
    h=replay;old=b'"datePublished": "2026-10-07"';assert old in h.bodies[ARTICLE]
    h.bodies[ARTICLE]=h.bodies[ARTICLE].replace(old,b'"datePublished": "2026-10-06"')
    records,audit=h.fetch();assert not records and audit['status']=='error' and audit['error_kind']=='parse_error'
    assert audit['http_request_count']==2


def test_old_publications_do_not_start_another_detail_request(replay):
    assert b'Oct 2026' in replay.bodies[INDEX]
    replay.bodies[INDEX]=replay.bodies[INDEX].replace(b'Oct 2026',b'Sep 2026')
    records,audit=replay.fetch()
    assert not records and audit['status']=='unavailable' and replay.calls==[ROSTER_URL,INDEX]
    assert audit['excluded_reason_counts']['historical']==10


def test_warm_cache_preserves_all_source_epochs_and_is_not_new_HTTP_success(replay):
    h=replay;records,cold=h.fetch();h.calls.clear();h.warm[0]=True;again,warm=h.fetch()
    assert records==again and warm['status']=='skipped_fresh_cache'
    assert warm['http_request_count']==0 and warm['http_request_sent'] is False and warm['cache_hit'] is True
    assert warm['fetched_at_epoch']==cold['fetched_at_epoch']==NOW-1000


@pytest.mark.parametrize('url',[ARTICLE.replace('https:','http:'),ARTICLE+'?x=1',ARTICLE+'#x',ARTICLE.replace('chromaate.com','chroma.com'),
                              ARTICLE.replace('www.','evil.'),ARTICLE.replace('/en/','/tw/'),ARTICLE.replace('news1189','news01189')])
def test_transport_refuses_unobserved_routes_credentials_aliases_and_languages(replay,url):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError)as exc:replay.module.url_contract(url)
    assert exc.value.error_kind=='transport_url_invalid'


def test_internal_original_receipts_are_not_put_into_model_text(replay):
    from prompt_evidence import prompt_evidence_copy
    records,_=replay.fetch();before=deepcopy(records)
    view=prompt_evidence_copy({'recent_catalysts':records})
    assert 'source_record_archive'not in str(view) and 'raw_response_path'not in str(view)
    assert records==before and 'will showcase'in view['recent_catalysts'][0]['text']


def test_expired_total_deadline_cannot_publish_a_completed_detail(replay,monkeypatch):
    h=replay;clock=[0.];original_get=IssuerNewsHttp.get
    monkeypatch.setattr(h.module.time,'monotonic',lambda:clock[0])
    def late(http,url):
        value=original_get(http,url)
        if url==ARTICLE:clock[0]=21.
        return value
    monkeypatch.setattr(IssuerNewsHttp,'get',late)
    records,audit=h.fetch()
    assert not records and audit['status']=='error' and audit['error_kind']=='timeout'
    assert h.calls==[ROSTER_URL,INDEX,ARTICLE] and audit['http_request_count']==2


@pytest.mark.parametrize('field',['instrument_type','quote_type','quoteType'])
def test_source_only_refresh_rejects_conflicting_instrument_before_acquisition(replay,field):
    import asyncio
    from fastapi import HTTPException
    from report_source_refresh import fetch_report_source_data
    data={**replay.data,'quote_type':'EQUITY','quoteType':'EQUITY'};data[field]='ETF'
    old={'ticker':'2360.TW','data':data,'source_audit':[{'source':'market_data','status':'success','fetched_at_epoch':NOW-100}]}
    before=deepcopy(old);calls=[]
    class Service:
        _fetcher=None
        async def fetch_source_async(self,*a,**k):
            calls.append('provider');raise AssertionError('unsupported identity must stop before provider')
    with pytest.raises(HTTPException)as exc:asyncio.run(fetch_report_source_data(old,'issuer_news',Service()))
    assert exc.value.status_code==400 and not calls and old==before
