import json
import httpx,pytest
from provider_correlation import correlation_scope,source_operation
from chip_response_originals import capture_chip_original,PUBLIC_URLS

@pytest.mark.parametrize('url',sorted(PUBLIC_URLS))
def test_owned_native_original_can_be_replayed(url):
 from official_response_evidence import read_response
 body=b'public original response'
 response=httpx.Response(200,content=body,request=httpx.Request('GET',url))
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   proof=capture_chip_original(response,url)
 assert proof['http_status_observed'] and proof['response_complete'] and proof['cache_hit']is False
 assert read_response(proof)==body

@pytest.mark.parametrize('kind',['status','post','url','auth','cookie','cached','oversize','unowned'])
def test_ineligible_response_has_no_original(monkeypatch,kind):
 import official_response_evidence
 monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:pytest.fail('must not archive'))
 url=sorted(PUBLIC_URLS)[0];actual=url if kind!='url'else url+'&token=secret'
 r=httpx.Response(429 if kind=='status'else 200,content=b'x'*(8_000_001 if kind=='oversize'else 1),request=httpx.Request('POST'if kind=='post'else'GET',actual,headers={'Authorization':'secret'}if kind=='auth'else {'Cookie':'secret'}if kind=='cookie'else {}))
 if kind=='cached':r.extensions['from_cache']=True
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','wrong provider'if kind=='unowned'else'TDCC/TWSE/TPEx chip data'):
   assert capture_chip_original(r,url)is None

def test_tdcc_existing_parser_and_one_request_retains_body(monkeypatch):
 import chip_data_fetcher as chip
 from official_response_evidence import read_response
 body=('資料日期,證券代號,持股分級,占集保庫存數比例%\n'+''.join(f'20261030,2330,{i},{12.5 if i==1 else 0}\n'for i in range(1,9))+'20261030,2330,15,80.0\n').encode()
 calls=[]
 def get(url,**kwargs):calls.append(url);return httpx.Response(200,content=body,request=httpx.Request('GET',url))
 monkeypatch.setattr(chip,'sync_get',get)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   out=chip.fetch_tdcc_shareholder_distribution('2330.TW')
 assert calls==[chip.TDCC_SHAREHOLDER_DISTRIBUTION_CSV_URL]
 assert out['as_of_date']=='20261030' and out['major_holders_gt_1000_lots_pct']==80.0
 assert out['retail_holders_lt_50_lots_pct']==12.5
 assert read_response(out['original_receipt'])==body

def test_borrowed_existing_parser_preserves_share_unit_and_exact_body(monkeypatch):
 import chip_data_fetcher as chip
 from official_response_evidence import read_response
 body=json.dumps({'date':'20261030','data':[['2330']+[None]*8+['533000','14000',None,'16187514']]}).encode();calls=[]
 def get(url,**kwargs):calls.append(url);return httpx.Response(200,content=body,request=httpx.Request('GET',url))
 monkeypatch.setattr(chip,'sync_get',get)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='f'):
  with source_operation('chip_data','TDCC/TWSE/TPEx chip data'):
   out=chip._fetch_borrowed_short_sales(None,'2330',timeout=15)
 assert calls==[chip.TWSE_BORROWED_SHORT_URL]
 assert out['borrowed_short_as_of_date']=='2026-10-30' and out['borrowed_short_unit']=='shares'
 assert out['borrowed_short_sale_balance']==16187514
 assert read_response(out['borrowed_short_original_receipt'])==body

def test_component_projection_separates_cached_margin_from_new_other_bodies(monkeypatch):
 import chip_data_fetcher as chip
 from data_fetch.agent_context_providers import ChipDataProvider
 from data_fetch.types import FetchRequest
 from provider_observation_details import _original_http_receipts
 def proof(url):return {'status':'archived','source_url':url,'raw_response_sha256':'a'*64,'raw_response_bytes':100,'retrieved_at':123456.0,'http_status':200,'evidence_kind':'decoded_complete_http_response_body','http_status_observed':True,'response_complete':True,'cache_hit':False}
 monkeypatch.setattr(chip,'fetch_tdcc_shareholder_distribution',lambda *a:{'status':'success','as_of_date':'20261030','source':'TDCC OpenData','original_receipt':proof(chip.TDCC_SHAREHOLDER_DISTRIBUTION_CSV_URL)})
 monkeypatch.setattr(chip,'fetch_twse_margin_short_sales',lambda *a,**kw:{'status':'success','as_of_date':'2026-10-30','source':'TWSE MI_MARGN dated report','margin_cache_hit':True,'margin_original_receipt':proof('https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=ALL'),'borrowed_short_status':'success','borrowed_short_as_of_date':'2026-10-30','borrowed_short_source':'TWSE TWT93U','borrowed_short_original_receipt':proof(chip.TWSE_BORROWED_SHORT_URL)})
 out=ChipDataProvider().fetch(FetchRequest.from_ticker('2330.TW'))
 assert out.status=='success' and out.audit['record_count']==3
 components=out.audit['component_statuses']
 assert components['margin_short']['http_request_sent']is False and components['margin_short']['cache_hit']is True
 assert components['tdcc']['http_request_sent']is True and components['borrowed_short']['http_request_sent']is True
 receipts=_original_http_receipts(out.audit);assert len(receipts)==3
 assert [r['http_request_sent']for r in receipts]==[True,False,True]
 assert all(r['original_retrieved_at_epoch']==123456.0 for r in receipts)

def test_safe_observation_projection_has_no_body_or_path():
 from provider_observation_details import observation_details
 receipt={'status':'archived','source_url':sorted(PUBLIC_URLS)[0],'raw_response_sha256':'a'*64,'raw_response_bytes':100,'retrieved_at':123456.0,'http_status':200,'evidence_kind':'decoded_complete_http_response_body','http_status_observed':True,'response_complete':True,'cache_hit':False,'raw_response_path':'/private/original.gz','body':'must not persist'}
 out=observation_details({'source':'chip_data','provider':'TDCC/TWSE/TPEx chip data','component_statuses':{'tdcc':{'status':'success','provider':'TDCC OpenData','original_receipt':receipt,'http_request_sent':True,'cache_hit':False}}})
 assert len(out['original_http_receipts'])==1
 assert out['original_http_receipts'][0]['http_request_sent']is True
 assert '/private/'not in json.dumps(out) and 'must not persist'not in json.dumps(out)
 assert 'raw_response_path'not in json.dumps(out) and 'original_receipt'not in out['component_statuses']['tdcc']
