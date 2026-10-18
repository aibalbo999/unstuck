from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path
from hashlib import sha256
import json,time
import pytest
from bs4 import BeautifulSoup
from data_fetch.market_sources import ltn_stock_news as ltn
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
from source_content_selection import select_company_records

F=json.loads((Path(__file__).parent/'fixtures/source_acquisition/ltn_9103_relative_selected_20261010.json').read_text())
NOW=datetime.fromisoformat(F['reference_now'])
DATA={'ticker':F['ticker'],'company_name':F['saved_identity']['display_name'],'company_identity':F['saved_identity']}

@pytest.fixture(autouse=True)
def fixed_calendar(monkeypatch):
    monkeypatch.setattr(ltn,'_today',lambda:NOW.astimezone(ltn.TAIPEI).date())

def native_boundaries(monkeypatch,*,roster=None,article=None):
    reads=[]
    def get(http,url):
        reads.append(url);http.components.append({'url':url,'cache_hit':True,'fetched_at_epoch':time.time()})
        return json.dumps(roster if roster is not None else F['selected_roster_rows'],ensure_ascii=False).encode()
    def read(url,*,deadline,diagnostics):
        reads.append(url)
        return F['selected_listing_html'].encode() if url.startswith('https://search.ltn.com.tw/list?') else (article or F['selected_article_html']).encode()
    monkeypatch.setattr(IssuerNewsHttp,'get',get);monkeypatch.setattr(ltn,'_read',read)
    return reads

def test_relative_index_time_discovers_originals_without_assigning_a_publication_date():
    rows=ltn.parse_listing(F['selected_listing_html'].encode(),'9103',now=NOW)
    assert len(rows)==3
    assert rows[0]['day'] is None and rows[0]['relative_date_hint']=='1天前'

def test_public_source_recovers_missing_legal_name_only_through_current_official_roster(monkeypatch):
    reads=native_boundaries(monkeypatch);before=deepcopy(DATA);diag={}
    rows=ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+6,diagnostics=diag,now=NOW,max_records=1)
    assert len(rows)==1
    assert DATA==before and DATA['company_identity']['legal_name'] is None
    assert len(reads)==3 and 'openapi.twse.com.tw' in reads[0]
    assert rows[0]['date']=='2026-10-08T10:15:16+00:00'
    assert rows[0]['publication_date_original']=={'article:published_time':'2026-10-08T18:15:16+08:00'}
    assert '（9103）' in rows[0]['text'] and rows[0]['impact_status']=='not_assessed'
    from news_freshness_policy import apply_news_freshness
    snapshot=deepcopy(DATA);apply_news_freshness(snapshot,records=rows,cutoff=NOW)
    restored=json.loads(json.dumps(snapshot,ensure_ascii=False))
    assert len(restored['recent_catalysts'])==1 and ltn.verified_ltn_record(restored['recent_catalysts'][0],restored)

@pytest.mark.parametrize('change',['wrong_name','wrong_code','old_date','future_date','missing_legal','duplicate_code'])
def test_unverified_official_roster_does_not_discover_articles(monkeypatch,change):
    roster=deepcopy(F['selected_roster_rows'])
    if change=='wrong_name':roster[0]['公司簡稱']='另一家公司'
    elif change=='wrong_code':roster[0]['公司代號']='9105'
    elif change=='old_date':roster[0]['出表日期']='1150901'
    elif change=='future_date':roster[0]['出表日期']='1151011'
    elif change=='missing_legal':roster[0]['公司名稱']=''
    else:roster.append(deepcopy(roster[0]))
    reads=native_boundaries(monkeypatch,roster=roster)
    assert ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+6,now=NOW)==[]
    assert len(reads)==1 and 'openapi.twse.com.tw' in reads[0]

@pytest.mark.parametrize('value',[False,0,[],{}])
def test_malformed_legal_identity_is_not_repaired_from_an_official_roster(monkeypatch,value):
    reads=native_boundaries(monkeypatch);data=deepcopy(DATA);data['company_identity']['legal_name']=value
    rows=ltn.fetch_ltn_stock_news(data,deadline=time.monotonic()+6,now=NOW)
    assert rows==[]
    if not isinstance(value,str):assert reads==[]

def test_saved_official_anchor_rejects_a_conflicting_legal_context(monkeypatch):
    native_boundaries(monkeypatch)
    row=ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+6,now=NOW,max_records=1)[0]
    changed=deepcopy(DATA);changed['company_identity']['legal_name']='其他公司股份有限公司'
    assert ltn.verified_ltn_record(row,changed) is None
    assert select_company_records([row],changed,cutoff=NOW)[0]==[]

def test_missing_tpex_legal_name_uses_only_its_own_market_roster(monkeypatch):
    from test_ltn_catalyst_fallback import DATA as OLD_DATA
    legacy=json.loads((Path(__file__).parent/'fixtures/source_acquisition/ltn_5314_selected_20261010.json').read_text())
    data=deepcopy(OLD_DATA);data['company_identity']['legal_name']=None;calls=[]
    def get(http,url):
        assert url=='https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
        calls.append(url);http.components.append({'url':url,'cache_hit':True,'fetched_at_epoch':time.time()})
        return json.dumps([{'SecuritiesCompanyCode':'5314','CompanyName':OLD_DATA['company_identity']['legal_name'],'CompanyAbbreviation':OLD_DATA['company_identity']['official_name'],'Date':'1151008'}],ensure_ascii=False).encode()
    def read(url,**kwargs):
        calls.append(url)
        return legacy['selected_index'].encode() if url.startswith('https://search.ltn.com.tw/list?') else legacy['selected_article'].encode()
    monkeypatch.setattr(IssuerNewsHttp,'get',get);monkeypatch.setattr(ltn,'_read',read)
    rows=ltn.fetch_ltn_stock_news(data,deadline=time.monotonic()+6,now=NOW,max_records=1)
    assert len(rows)==1 and len(calls)==3
    assert rows[0]['ltn_original_receipt']['official_issuer_anchor']['source_url']==calls[0]
    assert data['company_identity']['legal_name'] is None

@pytest.mark.parametrize('change',['missing_meta','naive_meta','future_meta','historical_meta','missing_clock'])
def test_relative_list_hint_cannot_replace_original_publication_evidence(monkeypatch,change):
    soup=BeautifulSoup(F['selected_article_html'],'html.parser')
    if change=='missing_clock':soup.select_one('div.function > span.time').decompose()
    else:
        nodes=soup.select('meta[property="article:published_time"]')
        for node in nodes:
            if change=='missing_meta':node.decompose()
            else:node['content']={'naive_meta':'2026-10-08T18:15:16','future_meta':'2026-10-11T18:15:16+08:00','historical_meta':'2026-08-08T18:15:16+08:00'}[change]
    native_boundaries(monkeypatch,article=str(soup))
    assert ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+6,now=NOW)==[]

@pytest.mark.parametrize('change',['remove_anchor','legal_name','official_short_name','ticker','as_of','response_sha256','epoch_nan','epoch_bool','epoch_huge','index_hint'])
def test_saved_issuer_anchor_or_relative_hint_tampering_fails_snapshot_reselection(monkeypatch,change):
    native_boundaries(monkeypatch)
    row=ltn.fetch_ltn_stock_news(DATA,deadline=time.monotonic()+6,now=NOW,max_records=1)[0]
    receipt=row['ltn_original_receipt'];anchor=receipt['official_issuer_anchor']
    if change=='remove_anchor':receipt.pop('official_issuer_anchor')
    elif change=='epoch_nan':anchor['fetched_at_epoch']=float('nan')
    elif change=='epoch_bool':anchor['fetched_at_epoch']=True
    elif change=='epoch_huge':anchor['fetched_at_epoch']=10**400
    elif change=='index_hint':receipt['index_publication_hint']['value']='未知'
    else:anchor[change]={'legal_name':'其他公司股份有限公司','official_short_name':'其他公司','ticker':'9105.TW','as_of':'2026-08-08','response_sha256':'f'*64}[change]
    assert ltn.verified_ltn_record(row,DATA) is None
    assert select_company_records([row],DATA,cutoff=NOW)[0]==[]

@pytest.mark.parametrize('failure',['deadline','lease'])
def test_official_anchor_completed_after_parent_budget_or_lease_loss_stops_news_reads(monkeypatch,failure):
    from contextlib import contextmanager
    import search_admission
    native_boundaries(monkeypatch);active=[True];clock=[0];calls=[]
    @contextmanager
    def admission(*args,**kwargs):yield lambda:active[0]
    monkeypatch.setattr(search_admission,'endpoint_admission',admission)
    monkeypatch.setattr(ltn.time,'monotonic',lambda:clock[0])
    def anchor(http,url):
        calls.append(url);http.components.append({'url':url,'fetched_at_epoch':time.time(),'cache_hit':True})
        if failure=='deadline':clock[0]=8
        else:active[0]=False
        return json.dumps(F['selected_roster_rows'],ensure_ascii=False).encode()
    monkeypatch.setattr(IssuerNewsHttp,'get',anchor)
    monkeypatch.setattr(ltn,'_read',lambda *a,**k:pytest.fail('news read after anchor budget/lease loss'))
    assert ltn.fetch_ltn_stock_news(DATA,deadline=6,now=NOW)==[]
    assert len(calls)==1
