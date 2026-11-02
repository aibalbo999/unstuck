from copy import deepcopy
from datetime import datetime,timezone
import json
import pytest
from data_fetch.market_sources import auras_issuer_news as news


def encoded(rows):return json.dumps({'status':True,'errorMessage':'','infos':rows,'totalCount':len(rows)}).encode()

def listing():return {'announcementId':12,'announcementStartDate':'2026/10/06','createDate':'2026/10/06','eng':{'title':'OCP Global Summit 2026'}}

def article():
    row=listing();row['eng']['content']='<p>雙鴻科技股份有限公司 Auras (3324) Date: 2026/10/13</p><p>'+('Company announced plans to showcase cooling products; no realized orders or profit is established. '*8)+'</p>'
    row['tcn']={'content':'<p>日期：2026 年 10 月 13 日</p>'}
    return row

def test_index_rejects_probe_labels_without_requesting_their_detail():
    probe=deepcopy(listing());probe.update(announcementId=13,eng={'title':'SSTI_EN_69529'})
    rows=news.parse_index(encoded([probe,listing()]))
    assert len(rows)==1 and rows[0]['original_id']==12

def test_article_uses_explicit_dateline_and_retains_other_date_semantics():
    row=news.parse_index(encoded([listing()]))[0]
    title,body,dates=news.parse_article(encoded([article()]),row)
    assert title=='OCP Global Summit 2026' and len(body)>500
    assert dates['date']=='2026-10-13T00:00:00+08:00'
    assert dates['index_display_start']==dates['cms_create_date']=='2026/10/06'
    assert dates['first_available_time_verified'] is False
    assert dates['event_occurrence_verified'] is False

@pytest.mark.parametrize('change', ['id','title','date_missing','earlier_date','language_conflict','issuer','empty','script'])
def test_article_rejects_misbound_or_incomplete_content(change):
    row=article()
    if change=='id':row['announcementId']=11
    if change=='title':row['eng']['title']='Different article'
    if change=='date_missing':row['eng']['content']=row['eng']['content'].replace('Date: 2026/10/13','')
    if change=='earlier_date':row['eng']['content']=row['eng']['content'].replace('2026/10/13','2026/10/01')
    if change=='language_conflict':row['tcn']['content']='<p>日期：2026 年 10 月 14 日</p>'
    if change=='issuer':row['eng']['content']=row['eng']['content'].replace('Auras (3324)','Auras (9999)')
    if change=='empty':row['eng']['content']=''
    if change=='script':row['eng']['content']+='<script>untrusted()</script>'
    with pytest.raises(ValueError):news.parse_article(encoded([row]),news.parse_index(encoded([listing()]))[0])

def test_only_reviewed_public_get_routes_are_allowed():
    from search_provider_runtime import SourceResponseError
    for url in [news.MASTER,news.INDEX,news.ARTICLE_BASE+'12'+news.ARTICLE_TAIL]:assert news.url_contract(url)[0]>0
    for url in ['https://other.example/news',news.ARTICLE_BASE+'12'+news.ARTICLE_TAIL+'&admin=true']:
        with pytest.raises(SourceResponseError):news.url_contract(url)

def test_native_provider_recognizes_otc_issuer():
    from data_fetch.issuer_news_provider import IssuerNewsProvider
    from data_fetch.types import FetchRequest
    assert IssuerNewsProvider().supports(FetchRequest.from_ticker('3324.TWO'))


class Http:
    def __init__(self,cached=False):
        import gzip
        from pathlib import Path
        self.contents={news.MASTER:gzip.decompress((Path(__file__).parent/'fixtures/source_acquisition/auras3324_master_20261013.gz').read_bytes()),news.INDEX:encoded([listing(),{**listing(),'announcementId':13,'eng':{'title':'SSTI_EN_69529'}}]),news.ARTICLE_BASE+'12'+news.ARTICLE_TAIL:encoded([article()])}
        self.calls=[];self.components=[];self.http_request_count=0;self.cached=cached
    def get(self,url):
        self.calls.append(url);self.http_request_count+=int(not self.cached)
        self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'fetched_at_epoch':datetime(2026,10,14,14,tzinfo=timezone.utc).timestamp()})
        return self.contents[url]


def test_full_original_chain_replays_and_keeps_probe_as_excluded_index_row():
    http=Http();records,audit=news.fetch_recent_news(now=datetime(2026,10,14,14,tzinfo=timezone.utc),http=http)
    assert len(records)==1 and audit['status']=='success',audit
    assert audit['raw_count']==2 and audit['excluded_reason_counts']['non_business_probe_index']==1
    assert audit['http_request_count']==3 and len(http.calls)==3
    record=records[0]
    assert news.verified_record(record,{'ticker':'3324.TWO'},today=datetime(2026,10,14).date())=='Auras'
    assert record['content_coverage']=='text_available' and record['content_truncated'] is False
    assert record['event_assessment']=='not_assessed'
    damaged=deepcopy(record);damaged['text']+=' invented statement'
    assert news.verified_record(damaged,{'ticker':'3324.TWO'},today=datetime(2026,10,14).date())is None
    assert news.verified_record(record,{'ticker':'3324.TW'},today=datetime(2026,10,14).date())is None


def test_cached_originals_are_not_new_http_success():
    records,audit=news.fetch_recent_news(now=datetime(2026,10,14,14,tzinfo=timezone.utc),http=Http(cached=True))
    assert len(records)==1 and audit['status']=='skipped_fresh_cache'
    assert audit['http_request_count']==0 and audit['http_request_sent'] is False


def test_official_issuer_conflict_stops_before_article():
    http=Http();rows=json.loads(http.contents[news.MASTER]);next(r for r in rows if r['SecuritiesCompanyCode']=='3324')['WebAddress']='https://other.example';http.contents[news.MASTER]=json.dumps(rows).encode()
    records,audit=news.fetch_recent_news(now=datetime(2026,10,14,14,tzinfo=timezone.utc),http=http)
    assert not records and audit['status']=='error' and http.calls==[news.MASTER]


def test_source_only_merge_preserves_finance_and_uses_full_article(monkeypatch):
    import asyncio,time
    from data_fetch.service import StockDataService
    from data_fetch.market_sources import issuer_news
    from report_source_refresh import fetch_report_source_data
    now=datetime(2026,10,14,14,tzinfo=timezone.utc)
    monkeypatch.setattr(time,'time',lambda:now.timestamp())
    real=issuer_news.fetch_recent_issuer_news
    monkeypatch.setattr(issuer_news,'fetch_recent_issuer_news',lambda ticker:real(ticker,now=now,http=Http()))
    data={'ticker':'3324.TWO','company_name':'雙鴻','instrument_type':'EQUITY','current_price':123.,'revenue_ttm_raw':123456,'recent_catalysts':[],
          'company_identity':{'ticker':'3324.TWO','stock_id':'3324','official_name':'雙鴻','legal_name':news.LEGAL,'official_ubn':news.UBN,'instrument_type':'EQUITY','allowed_aliases':['雙鴻'],'forbidden_aliases':[]}}
    original=deepcopy(data)
    result=asyncio.run(fetch_report_source_data({'ticker':'3324.TWO','data':data,'source_audit':[{'source':'market_data','provider':'saved quote','status':'success','record_count':1,'fetched_at_epoch':now.timestamp()-600}]},'issuer_news',StockDataService()))
    assert data==original
    assert result['current_price']==123. and result['revenue_ttm_raw']==123456
    assert len(result['recent_catalysts'])==1
    assert result['recent_catalysts'][0]['content_coverage']=='text_available'
