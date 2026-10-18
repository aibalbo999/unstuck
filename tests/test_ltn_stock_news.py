from pathlib import Path
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from copy import deepcopy
import json,time
import pytest
from bs4 import BeautifulSoup
from data_fetch.market_sources import ltn_stock_news as ltn
from source_content_selection import select_company_records
from test_ltn_catalyst_fallback import DATA
F=json.loads((Path(__file__).parent/'fixtures/source_acquisition/ltn_5314_selected_20261010.json').read_text());NOW=datetime.fromisoformat(F['reference_now'])

def parsed(raw=None):
    index=F['selected_index'].encode();c=ltn.parse_listing(index,'5314',now=NOW)[0]
    return ltn.parse_article(raw or F['selected_article'].encode(),c,DATA,now=NOW,index_hash=sha256(index).hexdigest())

def test_public_original_recovers_body_issuer_without_inventing_title_or_publication():
    row=parsed();assert row and '5314' not in row['title'] and '（5314）' in row['text']
    assert row['date']=='2026-09-15T03:55:27+00:00'
    assert row['impact_status']=='not_assessed' and row['content_truncated'] is False
    assert '請繼續往下閱讀' not in row['text'] and 'Youtube' not in row['text'] and '圖擷取' not in row['text']
    records,audit=select_company_records([row],DATA,cutoff=NOW)
    assert len(records)==1 and audit['rejected_count']==0
    restored=json.loads(json.dumps(records[0],ensure_ascii=False));assert ltn.verified_ltn_record(restored,DATA)

@pytest.mark.parametrize('change',['missing_clock','nested_clock','missing_meta','naive_meta','conflicting_meta','wrong_meta_url','wrong_title','wrong_day','caption_only_code','outside_body_code','duplicate_article'])
def test_article_schema_company_or_original_time_failure_is_not_recovered(change):
    soup=BeautifulSoup(F['selected_article'],'html.parser');box=soup.select_one('div.whitecon.boxText')
    if change=='missing_clock':box.select_one('span.time').decompose()
    elif change=='nested_clock':
        clock=box.select_one('span.time');clock.wrap(soup.new_tag('div'))
    elif change=='missing_meta':
        for node in soup.select('meta[property="article:published_time"]'):node.decompose()
    elif change=='naive_meta':
        for node in soup.select('meta[property="article:published_time"]'):node['content']='2026-09-15T03:55:27'
    elif change=='conflicting_meta':soup.select_one('meta[property="article:published_time"]')['content']='2026-09-16T11:55:27+08:00'
    elif change=='wrong_meta_url':soup.select_one('meta[property="og:url"]')['content']='https://ec.ltn.com.tw/article/breakingnews/1234567'
    elif change=='wrong_title':box.select_one('h1').string='另一篇新聞'
    elif change=='wrong_day':
        for node in soup.select('meta[property="article:published_time"]'):node['content']='2026-09-16T11:55:27+08:00'
    elif change in ('caption_only_code','outside_body_code'):
        for p in box.select_one(':scope > div.text').find_all('p',recursive=False):
            if not p.find('img'):p.string='這是一段其他公司資料，沒有公司股票代號，且正文長度足夠通過一般篇幅規則。'
            else:
                for v in list(p.find_all(string=True)):
                    if not v.find_parent(class_='ph_b'):v.replace_with('')
        if change=='outside_body_code':soup.body.append(BeautifulSoup('<p>世紀*（5314）</p>','html.parser'))
    elif change=='duplicate_article':soup.body.append(deepcopy(box))
    assert parsed(str(soup).encode()) is None

@pytest.mark.parametrize('field,value',[('official_name',False),('legal_name',0),('stock_id',False),('instrument_type','ETF'),('ticker','5314.TW')])
def test_malformed_or_other_market_identity_never_uses_an_issuer_fallback(field,value):
    data=deepcopy(DATA);data['company_identity'][field]=value
    assert ltn.verified_ltn_record(parsed(),data) is None

@pytest.mark.parametrize('mutation',['receipt_removed','source_type_removed','body','date','index_hash','truncated'])
def test_saved_receipt_mutation_cannot_fall_back_to_generic_company_match(mutation):
    row=parsed()
    if mutation=='receipt_removed':row.pop('ltn_original_receipt')
    elif mutation=='source_type_removed':row.pop('source_type')
    elif mutation=='body':row['text']+=' 虛構新內容。'
    elif mutation=='date':row['date']='2026-09-16T03:55:27+00:00'
    elif mutation=='index_hash':row['ltn_original_receipt']['index_response_sha256']='f'*64
    elif mutation=='truncated':row['content_truncated']=True
    records,_=select_company_records([row],DATA,cutoff=NOW);assert records==[]

def test_bounded_native_workflow_uses_selected_index_then_exact_original(monkeypatch):
    calls=[]
    def read(url,*,deadline,diagnostics):
        calls.append(url)
        return F['selected_index'].encode() if url.startswith('https://search.ltn.com.tw/list?') else F['selected_article'].encode()
    monkeypatch.setattr(ltn,'_read',read);diag={}
    rows=ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+5,diagnostics=diag,now=NOW)
    assert len(rows)==1 and len(calls)==2 and calls[-1]==F['original_article_url']
    assert len(diag['raw_reads'])==0 and diag['http_requests']==0

@pytest.mark.parametrize('url',['https://evil.test/article/breakingnews/5574307','https://ec.ltn.com.tw/article/breakingnews/5574307?redirect=evil','http://ec.ltn.com.tw/article/breakingnews/5574307','https://search.ltn.com.tw/list?keyword=5314&type=all&sort=date&start_time=20260910&end_time=20261010','https://search.ltn.com.tw/list?keyword=5314&type=business&sort=date&start_time=20250801&end_time=20261010'])
def test_unknown_route_cannot_read_cache_or_start_http(url):
    assert not ltn._url_allowed(url)

@pytest.mark.parametrize('deadline',[False,float('nan'),float('inf'),0])
def test_invalid_or_expired_deadline_does_not_start_native_http(monkeypatch,deadline):
    monkeypatch.setattr(ltn,'_read',lambda *a,**k:pytest.fail('request after invalid budget'))
    assert ltn.fetch_ltn_stock_news(DATA,deadline=deadline)==[]

def test_isolated_network_guard_stops_native_curl_even_for_a_valid_article(monkeypatch):
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','1')
    with pytest.raises(RuntimeError,match='Isolated'):
        ltn._read(F['original_article_url'],deadline=time.monotonic()+5,diagnostics={})

def test_raw_cache_revalidation_preserves_original_epoch_and_avoids_second_http(monkeypatch):
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0');calls=[]
    def transport(argv,deadline,*,body_limit,headers):
        url=argv[-1];calls.append(url);raw=F['selected_index'].encode() if url.startswith('https://search.ltn.com.tw/list?') else F['selected_article'].encode()
        return {'body':raw,'headers':b'HTTP/2 200\r\n\r\n','metadata':b'','process_started':True},0,None
    monkeypatch.setattr(ltn,'collect_capped_process',transport)
    first={};second={}
    a=ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+5,diagnostics=first,now=NOW)
    b=ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+5,diagnostics=second,now=NOW)
    assert len(a)==1 and a==b and len(calls)==2
    assert first['http_requests']==2 and second['http_requests']==0
    assert [v['fetched_at_epoch'] for v in first['raw_reads']]==[v['fetched_at_epoch'] for v in second['raw_reads']]
    assert all(v['cache_hit'] for v in second['raw_reads'])

def test_original_receipt_survives_actual_news_normalization_and_snapshot_reselection():
    from news_freshness_policy import apply_news_freshness
    data=deepcopy(DATA);apply_news_freshness(data,records=[parsed()],cutoff=NOW)
    assert len(data['recent_catalysts'])==1 and data['identity_rejected_catalysts']==[]
    assert ltn.verified_ltn_record(json.loads(json.dumps(data['recent_catalysts'][0],ensure_ascii=False)),data)

@pytest.mark.parametrize('failure',['deadline','lease'])
def test_completed_original_is_not_published_after_its_budget_or_ownership_ends(monkeypatch,failure):
    active=[True];clock=[0]
    def read(url,**kwargs):
        if not url.startswith('https://search.ltn.com.tw/list?'):
            if failure=='deadline':clock[0]=10
            else:active[0]=False
            return F['selected_article'].encode()
        return F['selected_index'].encode()
    monkeypatch.setattr(ltn,'_read',read);monkeypatch.setattr(ltn.time,'monotonic',lambda:clock[0])
    assert ltn._acquire(DATA,deadline=5,now=NOW,owns=lambda:active[0])==[]

@pytest.mark.parametrize('epoch',[False,0,float('nan'),time.time()+3600,time.time()-1900])
def test_malformed_or_expired_raw_cache_epoch_cannot_supply_a_fresh_original(monkeypatch,epoch):
    import shared_provider_cache,base64
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0');raw=F['selected_article'].encode()
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:({'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()},{'cache_hit':True,'stale':False,'fetched_at_epoch':epoch}))
    with pytest.raises(RuntimeError):ltn._read(F['original_article_url'],deadline=time.monotonic()+5,diagnostics={'http_requests':0,'raw_reads':[]})

def test_unstarted_transport_is_not_recorded_as_a_sent_http_request(monkeypatch):
    import shared_provider_cache
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda key,callback,**kwargs:(callback(),{}))
    monkeypatch.setattr(ltn,'collect_capped_process',lambda *a,**k:({'body':b'','headers':b'','process_started':False},None,'transport_error'))
    diag={'http_requests':0,'raw_reads':[],'transport_failures':[]}
    with pytest.raises(RuntimeError):ltn._read(F['original_article_url'],deadline=time.monotonic()+5,diagnostics=diag)
    assert diag['http_requests']==0 and diag['transport_failures'][0]['http_request_sent'] is False

def test_retry_after_is_preserved_by_existing_persistent_cooldown(monkeypatch):
    import shared_provider_cache,search_provider_runtime
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda key,callback,**kwargs:(callback(),{}))
    monkeypatch.setattr(search_provider_runtime,'cooldown_state',lambda key:{})
    monkeypatch.setattr(ltn,'collect_capped_process',lambda *a,**k:({'body':b'refused','headers':b'HTTP/2 429\r\nRetry-After: 3600\r\n\r\n','process_started':True},22,None))
    diag={'http_requests':0,'raw_reads':[],'transport_failures':[]};before=time.time()
    with pytest.raises(RuntimeError):ltn._read(F['original_article_url'],deadline=time.monotonic()+5,diagnostics=diag)
    state=search_provider_runtime.cooldown_state(search_provider_runtime.scope_key('LTN public originals',endpoint='public_html'))
    # Inspect the real isolated cache, after restoring the stubbed read.
    from cache_store import get_cache_json
    state=get_cache_json(search_provider_runtime.scope_key('LTN public originals',endpoint='public_html'))
    assert state['retry_at']>=before+3599
