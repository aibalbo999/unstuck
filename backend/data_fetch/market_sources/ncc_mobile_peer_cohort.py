"""Dated mobile-operator leads, never whole-company financial equivalence."""
from calendar import monthrange
from datetime import date,datetime
from hashlib import sha256
import json,math,time
from zoneinfo import ZoneInfo
from official_response_evidence import read_response,archive_response
from search_provider_runtime import SourceResponseError
from .official_company_legal_name import URLS,parse_roster,select_legal_name

SOURCE_URL='https://api.ncc.gov.tw/uploaddowndoc?file=datagov/%E8%A1%8C%E5%8B%95%E5%AF%AC%E9%A0%BB%E6%9C%8D%E5%8B%99%E7%94%A8%E6%88%B6%E6%95%B8%E7%B5%B1%E8%A8%88.json&filedisplay=%E8%A1%8C%E5%8B%95%E5%AF%AC%E9%A0%BB%E6%9C%8D%E5%8B%99%E7%94%A8%E6%88%B6%E6%95%B8%E7%B5%B1%E8%A8%88.json&flag=doc'
SCOPE='dated_ncc_mobile_operator_candidates'
RECEIPT_KEY='ncc_mobile_membership_originals'
PROVIDER='NCC mobile operator membership'
LIMIT=500000
TTL=1800
IDENTITIES={'2412.TW':('中華電','中華電信股份有限公司','96979933'),
            '3045.TW':('台灣大','台灣大哥大股份有限公司','97176270'),
            '4904.TW':('遠傳','遠傳電信股份有限公司','97179430')}
FIELDS={'ym','cname','num1','num2','num21','num22','num3','num31','num32'}
SHARED_KIND='cached_complete_source_payload_verified_by_digest'


def supports_context(ticker,industry,identity):
 if ticker not in IDENTITIES or not isinstance(identity,dict):return False
 short,legal,ubn=IDENTITIES[ticker]
 return (str(industry or '').strip().casefold()=='telecom services'
   and identity.get('ticker')==ticker and identity.get('stock_id')==ticker[:4]
   and identity.get('official_name')==short and identity.get('instrument_type')=='EQUITY'
   and identity.get('legal_name')in(None,'',legal)and identity.get('official_ubn')in(None,'',ubn))


def today():return datetime.now(ZoneInfo('Asia/Taipei')).date()


def strict_json(raw):
 def pairs(items):
  result={}
  for key,value in items:
   if key in result:raise ValueError('duplicate_json_field')
   result[key]=value
  return result
 return json.loads(raw.decode('utf-8-sig','strict'),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite_json')))


def parse_members(raw,*,today):
 if not isinstance(raw,bytes)or not 0<len(raw)<=LIMIT:raise ValueError('ncc_original_size')
 rows=strict_json(raw)
 if not isinstance(rows,list)or not 100<=len(rows)<=3000:raise ValueError('ncc_complete_history_shape')
 seen=set();periods={}
 for row in rows:
  if not isinstance(row,dict)or set(row)!=FIELDS or type(row['ym'])is not int:raise ValueError('ncc_row_shape')
  ym=row['ym'];year=ym//100+1911;month=ym%100
  if not 2000<=year<=today.year or not 1<=month<=12:raise ValueError('ncc_period_invalid')
  end=date(year,month,monthrange(year,month)[1])
  if end>=today:raise ValueError('ncc_future_or_incomplete_period')
  name=row['cname']
  if not isinstance(name,str)or not 4<=len(name)<=80 or name!=name.strip():raise ValueError('ncc_operator_name')
  if (ym,name)in seen:raise ValueError('ncc_duplicate_operator_period')
  seen.add((ym,name));periods.setdefault(end,[]).append(row)
  if any(not(type(row[k])is int and 0<=row[k]<=1000000000)
         and not(k in{'num21','num22','num31','num32'}and row[k]=='')for k in FIELDS-{'ym','cname'}):raise ValueError('ncc_count_invalid')
 latest=max(periods)
 if len(periods)<24 or not 0<=(today-latest).days<=62:raise ValueError('ncc_latest_period_expired')
 selected=periods[latest]
 if any(type(r[k])is not int for r in selected for k in FIELDS-{'ym','cname'}):raise ValueError('ncc_latest_missing_subcounts')
 if {r['cname']for r in selected}!={legal for _,legal,_ in IDENTITIES.values()}or len(selected)!=3:raise ValueError('ncc_latest_membership_changed')
 for r in selected:
  if not(r['num1']>0 and r['num1']==r['num2']+r['num3']and r['num2']==r['num21']+r['num22']and r['num3']==r['num31']+r['num32']):raise ValueError('ncc_latest_totals_conflict')
 return {'period_end':latest.isoformat(),'members':[r['cname']for r in selected],
         'membership_effective_date_verified':False,'raw_record_count':len(rows),
         'historical_missing_subcounts':sum(r[k]=='' for r in rows for k in('num21','num22','num31','num32'))}


def _original(proof,url):
 if not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url:raise ValueError('ncc_original_unbound')
 stamp=proof.get('retrieved_at');until=proof.get('fresh_until_epoch');shared=proof.get('evidence_kind')==SHARED_KIND
 if (type(stamp)not in(int,float)or type(until)not in(int,float)or not math.isfinite(stamp)or not math.isfinite(until)
     or not 0<stamp<=time.time()<min(until,stamp+(86400 if shared else TTL))
     or not 0<until-stamp<=(86401 if shared else TTL+1)
     or proof.get('historical_point_in_time_verified')is not False or proof.get('finality_guaranteed')is not False):raise ValueError('ncc_original_window')
 if shared:
  if url!=URLS['.TW']or proof.get('http_status')is not None or proof.get('http_status_observed')is not False:raise ValueError('ncc_cached_master_not_http')
 elif proof.get('evidence_kind')!='raw_http_response_bytes'or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('http_status_observed')is not True:raise ValueError('ncc_native_proof')
 raw=read_response(proof,max_bytes=2500000 if url==URLS['.TW']else LIMIT)
 if type(proof.get('raw_response_bytes'))is not int or len(raw)!=proof['raw_response_bytes']:raise ValueError('ncc_original_length')
 # Rebind the supplied time to the owner's independent saved observation.
 from cache_store import get_cache_json
 from .ncc_mobile_peer_transport import RAW_KEY
 key=('official-company-roster:v2:.TW'if shared else 'issuer-news-raw:v1:'+url)if url==URLS['.TW']else RAW_KEY+url
 saved=get_cache_json('shared_provider:v1:'+sha256(key.encode()).hexdigest())
 if not isinstance(saved,dict)or saved.get('error_kind'):raise ValueError('ncc_saved_observation_missing')
 start=saved.get('fetched_at_epoch');end=saved.get('fresh_until_epoch');value=saved.get('value')
 if (type(start)not in(int,float)or type(end)not in(int,float)or not math.isfinite(start)or not math.isfinite(end)
    or not 0<=start-stamp<=10 or not time.time()<end):raise ValueError('ncc_saved_observation_window')
 if url==SOURCE_URL:
  if not isinstance(value,dict)or value.get('receipt')!=proof or proof['fresh_until_epoch']!=stamp+TTL:raise ValueError('ncc_saved_receipt_changed')
 elif (start!=stamp or proof['fresh_until_epoch']!=min(end,stamp+(86400 if shared else TTL))
       or not isinstance(value,dict)or value.get('response_sha256'if shared else'sha256')!=sha256(raw).hexdigest()):raise ValueError('ncc_saved_master_changed')

 if not time.time()<min(end,proof['fresh_until_epoch'],stamp+(86400 if shared else TTL)):raise ValueError('ncc_original_expired_during_read')
 return raw


def _issuer_anchors(raw,proof,asof):
 strict_json(raw);roster=parse_roster(raw,'.TW')
 if len(roster['entries'])<800:raise ValueError('ncc_issuer_roster_incomplete')
 anchors={}
 master_day=datetime.fromtimestamp(proof['retrieved_at'],ZoneInfo('Asia/Taipei')).date()
 for symbol,(short,legal,ubn)in IDENTITIES.items():
  a=select_legal_name(roster,symbol,short,today=asof)
  if (a and a['legal_name']==legal and a['official_ubn']==ubn and date.fromisoformat(a['as_of'])<=master_day<=asof
      and 0<=(asof-date.fromisoformat(a['as_of'])).days<=7):anchors[symbol]=a
 return anchors


def _candidates(originals,ticker,asof):
 if ticker not in IDENTITIES or not isinstance(originals,dict)or set(originals)!={SOURCE_URL,URLS['.TW']}:raise ValueError('ncc_original_set')
 raw={url:_original(proof,url)for url,proof in originals.items()};members=parse_members(raw[SOURCE_URL],today=asof)
 # A response acquired before the declared latest period ended cannot become
 # valid simply by waiting and replaying it later.
 acquired_day=datetime.fromtimestamp(originals[SOURCE_URL]['retrieved_at'],ZoneInfo('Asia/Taipei')).date()
 parse_members(raw[SOURCE_URL],today=acquired_day)
 anchors=_issuer_anchors(raw[URLS['.TW']],originals[URLS['.TW']],asof)
 if ticker not in anchors:raise ValueError('ncc_target_issuer_unverified')
 rows=[]
 for symbol,(short,legal,_)in IDENTITIES.items():
  if symbol==ticker or symbol not in anchors or legal not in members['members']:continue
  rows.append({'ticker':symbol,'name':short,'identity_status':'current_exchange_master_and_dated_ncc_mobile_membership',
   'comparison_status':'industry_candidate_only','comparison_scope':SCOPE,
   'master_observed_at':anchors[symbol]['as_of'],'issuer_master_observed_at':anchors[ticker]['as_of'],
   'membership_period_end':members['period_end'],'membership_source_url':SOURCE_URL,
   'membership_effective_date_verified':False,'business_comparability_verified_current':False,'numeric_comparability_verified':False,
   'comparison_limitations':['dated_mobile_operator_leads_only','whole_company_business_mix_not_verified',
    'financial_period_comparability_not_verified','subscriber_lines_not_unique_people_or_revenue'],RECEIPT_KEY:originals})
 return rows


def verified_candidates(records,ticker,*,today):
 try:
  if not records:return False
  expected={r['ticker']:r for r in _candidates(records[0][RECEIPT_KEY],ticker,today)}
  keys=set(next(iter(expected.values())))if expected else set()
  for row in records:
   if row.get('ticker')not in expected or any(row.get(k)!=expected[row['ticker']][k]for k in keys-{'comparison_status'}):return False
   if row.get('comparison_status')not in{'industry_candidate_only','business_industry_matched'}:return False
  if len({r['ticker']for r in records})!=len(records)or not all(_original(p,u)for u,p in records[0][RECEIPT_KEY].items()):return False
  now=time.time()
  return all(p['retrieved_at']<=now<min(p['fresh_until_epoch'],p['retrieved_at']+(86400 if p['evidence_kind']==SHARED_KIND else TTL))for p in records[0][RECEIPT_KEY].values())
 except(ValueError,TypeError,KeyError,OSError,EOFError,OverflowError,UnicodeError,RecursionError):return False


def get_candidates(ticker,master_rows,*,today):
 if ticker not in IDENTITIES:return {'status':'not_applicable','candidates':[]}
 if not isinstance(master_rows,list):return {'status':'current_stock_identity_unverified','candidates':[]}
 from .peer_recovery import _current_rows
 # The separate current stock master is retained, not replaced by membership.
 relevant=[r for r in master_rows if isinstance(r,dict)and str(r.get('stock_id'))in{s[:4]for s in IDENTITIES}]
 current,reason=_current_rows(relevant,today)
 if reason:return {'status':'current_stock_identity_unverified','candidates':[]}
 for symbol,(short,_,_)in IDENTITIES.items():
  found=[r for r in current if str(r.get('stock_id'))==symbol[:4]]
  if not found or any(r.get('stock_name')!=short or str(r.get('type')).lower()!='twse'for r in found):return {'status':'current_stock_identity_unverified','candidates':[]}
 from .official_thermal_peer_cohort import ThermalHttp
 from .ncc_mobile_peer_transport import MobileHttp
 deadline=time.monotonic()+12;http=MobileHttp(deadline);master=ThermalHttp(deadline)
 try:
  raw=master.get(URLS['.TW']);meta=master.components[-1];shared=meta['evidence_kind']==SHARED_KIND
  receipt=archive_response(raw,source_url=URLS['.TW'],retrieved_at=meta['fetched_at_epoch'],
   evidence_kind=meta['evidence_kind'],http_status=None if shared else 200)
  receipt.update(fresh_until_epoch=meta['fresh_until_epoch'],http_status_observed=not shared)
  master_original=_original(receipt,URLS['.TW'])
  if ticker not in _issuer_anchors(master_original,receipt,today):raise ValueError('ncc_target_issuer_unverified')
  _,ncc=http.get();originals={URLS['.TW']:receipt,SOURCE_URL:ncc};rows=_candidates(originals,ticker,today)
  if not verified_candidates(rows,ticker,today=today):raise ValueError('ncc_final_qualification')
  if time.monotonic()>=deadline:raise SourceResponseError('timeout')
  return {'status':'success','candidates':rows,'http_request_count':http.http_request_count+master.http_request_count,
          'components':http.components+master.components,'cache_hit':all(c.get('cache_hit')is True for c in http.components+master.components)}
 except Exception as exc:
  return {'status':'ncc_membership_unavailable','candidates':[],'error_kind':getattr(exc,'error_kind',type(exc).__name__),
          'http_request_count':http.http_request_count+master.http_request_count,'components':http.components+master.components}
