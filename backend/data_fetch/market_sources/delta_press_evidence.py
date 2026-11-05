"""Pathless complete originals, immutable metadata and independent live owners."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo
import json,math,re,time
from .delta_press_parse import INDEX,TTL,contract,select_article,parse_article

RAW_PREFIX='issuer-news-raw:v1:'
BATCH_PREFIX='delta-press-batch:v1:'
RAW_SCHEMA='delta-press-native:v1'
BATCH_SCHEMA='delta-press-dataset:v1'
PROVIDER='Verified issuer news'
ARCHIVE_FIELDS={'status','source_url','retrieved_at','http_status','raw_response_sha256',
    'raw_response_bytes','evidence_kind','historical_point_in_time_verified','finality_guaranteed'}

def dump(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()

def finite(value):return type(value)in(int,float)and math.isfinite(value)
def raw_key(url):return 'shared_provider:v1:'+sha256((RAW_PREFIX+url).encode()).hexdigest()
def batch_key():return 'shared_provider:v1:'+sha256((BATCH_PREFIX+INDEX).encode()).hexdigest()
def pathless(proof):return {k:v for k,v in proof.items()if k!='raw_response_path'}

def _archive(raw,url,stamp,kind,status,limit):
    from official_response_evidence import archive_response
    proof=pathless(archive_response(raw,source_url=url,retrieved_at=stamp,evidence_kind=kind,http_status=status,max_bytes=limit))
    if proof.get('status')!='archived':raise ValueError('delta_original_archive_unavailable')
    return proof

def _read(proof,url,stamp,kind,status,limit):
    from runtime_paths import current_runtime_paths
    from official_response_evidence import read_response
    if (not isinstance(proof,dict)or set(proof)!=ARCHIVE_FIELDS or proof.get('status')!='archived'
        or proof.get('source_url')!=url or proof.get('retrieved_at')!=stamp
        or proof.get('http_status')!=status or type(proof.get('http_status'))is not type(status)
        or proof.get('evidence_kind')!=kind or proof.get('historical_point_in_time_verified')is not False
        or proof.get('finality_guaranteed')is not False):raise ValueError('delta_original_metadata_invalid')
    digest=proof.get('raw_response_sha256')
    if not isinstance(digest,str)or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('delta_original_identity')
    raw=read_response({**proof,'raw_response_path':str(current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz'))},max_bytes=limit)
    if type(proof.get('raw_response_bytes'))is not int or not 0<len(raw)==proof['raw_response_bytes']<=limit:raise ValueError('delta_complete_original_missing')
    return raw

def transport_for(raw):
    return {'http_status':200,'http_status_observed':True,'response_complete':True,'http_request_sent':True,
      'return_code':0,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'response_bytes':len(raw)}

def native_receipt(raw,url,stamp,transport):
    from provider_correlation import current_correlation,current_source_identity
    c=current_correlation()
    acquisition={'source':'recent_catalysts','provider':PROVIDER,**{k:c.get(k)for k in('ticker','fetch_id','operation_id')}}
    if current_source_identity()!=('recent_catalysts',PROVIDER)or not _acquisition_valid(acquisition):raise ValueError('delta_native_source_frame_required')
    limit,_=contract(url);expected=transport_for(raw)
    if (not isinstance(raw,bytes)or not 0<len(raw)<=limit or not finite(stamp)or stamp<=0
        or transport!=expected or any(type(transport.get(k))is not type(v)for k,v in expected.items())):raise ValueError('delta_native_complete_transport_unverified')
    receipt={'schema':RAW_SCHEMA,'url':url,'method':'GET','observed_at_epoch':stamp,'acquisition':acquisition,
        'native_transport':deepcopy(transport),'raw_receipt':_archive(raw,url,stamp,'raw_http_response_bytes',200,limit)}
    receipt['metadata_manifest']=_archive(dump(receipt),url,stamp,'private_acquisition_manifest',None,16384)
    return receipt

def _acquisition_valid(value):
    return (isinstance(value,dict)and set(value)=={'source','provider','ticker','fetch_id','operation_id'}
      and value.get('source')=='recent_catalysts'and value.get('provider')==PROVIDER and value.get('ticker')=='2308.TW'
      and all(isinstance(value.get(k),str)and re.fullmatch(r'[A-Za-z0-9_-]{1,160}',value[k])for k in('fetch_id','operation_id')))

def _owner(key,value,stamp,now,deadline,*,wrapper=False):
    from cache_store import peek_cache_json
    saved=peek_cache_json(key)
    if not isinstance(saved,dict)or saved.get('error_kind')or saved.get('value')!=value:raise ValueError('delta_independent_owner_missing_or_changed')
    start,end=saved.get('fetched_at_epoch'),saved.get('fresh_until_epoch')
    # Raw ownership follows its own HTTP receipt. A dataset wrapper may be
    # created later from live originals, but cannot change their observation or expiry.
    delay=TTL if wrapper else 20
    if (not all(finite(x)for x in(start,end,stamp,now,deadline))or not stamp<=start<=stamp+delay
        or not start<=now<end or not 0<end-start<=TTL+1 or end>deadline+1):raise ValueError('delta_owner_window_invalid')
    return saved

def receipt_body(receipt,url,now):
    limit,_=contract(url)
    fields={'schema','url','method','observed_at_epoch','acquisition','native_transport','raw_receipt','metadata_manifest'}
    if not isinstance(receipt,dict)or set(receipt)!=fields or receipt.get('schema')!=RAW_SCHEMA or receipt.get('url')!=url or receipt.get('method')!='GET':raise ValueError('delta_raw_receipt_shape')
    stamp=receipt['observed_at_epoch']
    if not _acquisition_valid(receipt['acquisition']):raise ValueError('delta_original_source_frame_invalid')
    if not finite(stamp)or not finite(now)or not 0<=now-stamp<TTL:raise ValueError('delta_original_expired_or_future')
    raw=_read(receipt['raw_receipt'],url,stamp,'raw_http_response_bytes',200,limit);expected=transport_for(raw)
    if receipt['native_transport']!=expected or any(type(receipt['native_transport'].get(k))is not type(v)for k,v in expected.items()):raise ValueError('delta_native_transport_changed')
    if _read(receipt['metadata_manifest'],url,stamp,'private_acquisition_manifest',None,16384)!=dump({k:v for k,v in receipt.items()if k!='metadata_manifest'}):raise ValueError('delta_metadata_manifest_changed')
    _owner(raw_key(url),receipt,stamp,now,stamp+TTL)
    return raw

def native_batch(originals,now):
    if not isinstance(originals,list)or len(originals)!=2:raise ValueError('delta_batch_originals')
    bodies=[receipt_body(r,r['url'],now)for r in originals]
    expected=select_article(bodies[0],datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date())
    if [r['url']for r in originals]!=[INDEX,expected]:raise ValueError('delta_batch_published_action')
    # A complete article parse is required before creating a dataset owner.
    parse_article(*bodies,expected,today=datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date())
    stamp=min(r['observed_at_epoch']for r in originals)
    batch={'schema':BATCH_SCHEMA,'source_url':INDEX,'fetched_at_epoch':stamp,'originals':deepcopy(originals)}
    batch['metadata_manifest']=_archive(dump(batch),INDEX,stamp,'private_acquisition_manifest',None,32768)
    return batch

def batch_bodies(batch,now):
    from cache_store import peek_cache_json
    if not isinstance(batch,dict)or set(batch)!={'schema','source_url','fetched_at_epoch','originals','metadata_manifest'}or batch.get('schema')!=BATCH_SCHEMA or batch.get('source_url')!=INDEX:raise ValueError('delta_batch_shape')
    originals=batch['originals'];stamp=batch['fetched_at_epoch']
    if not isinstance(originals,list)or len(originals)!=2 or not finite(stamp)or not finite(now)or not 0<=now-stamp<TTL:raise ValueError('delta_batch_window')
    urls=[r.get('url')for r in originals]
    if urls[0]!=INDEX or urls[1]==INDEX or stamp!=min(r['observed_at_epoch']for r in originals):raise ValueError('delta_batch_observation_renewed')
    bodies=[receipt_body(r,r['url'],now)for r in originals]
    if _read(batch['metadata_manifest'],INDEX,stamp,'private_acquisition_manifest',None,32768)!=dump({k:v for k,v in batch.items()if k!='metadata_manifest'}):raise ValueError('delta_batch_manifest_changed')
    if urls[1]!=select_article(bodies[0],datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date()):raise ValueError('delta_unpublished_article')
    owners=[peek_cache_json(raw_key(url))for url in urls]
    ends=[o.get('fresh_until_epoch')if isinstance(o,dict)else None for o in owners]
    if not all(finite(x)for x in ends):raise ValueError('delta_raw_deadline_missing')
    _owner(batch_key(),batch,stamp,now,min(ends),wrapper=True)
    return bodies

def valid_context(data):
    from .current_104_evidence import valid_context as exact
    return exact(data,{'ticker':'2308.TW','official_short_name':'台達電','legal_name':'台達電子工業股份有限公司','official_ubn':'34051920'})

def current_master(now):
    """Read-only full roster replay; never acquire/renew an identity in validation."""
    from cache_store import peek_cache_json
    from runtime_paths import current_runtime_paths
    from official_response_evidence import read_response
    from .official_company_legal_name import parse_roster,select_legal_name,MAX_BYTES
    key='shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest()
    saved=peek_cache_json(key)
    if not isinstance(saved,dict)or saved.get('error_kind'):raise ValueError('delta_current_master_missing')
    start,end=saved.get('fetched_at_epoch'),saved.get('fresh_until_epoch')
    if not all(finite(x)for x in(start,end,now))or not 0<=now-start<86400 or not start<=now<end or not 0<end-start<=86401:raise ValueError('delta_current_master_expired')
    roster=saved.get('value');digest=roster.get('response_sha256')if isinstance(roster,dict)else None
    if not isinstance(digest,str)or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('delta_master_original_missing')
    raw=read_response({'raw_response_sha256':digest,'raw_response_path':str(current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz'))},max_bytes=MAX_BYTES)
    if parse_roster(raw,'.TW')!=roster or len(roster.get('entries',{}))<800:raise ValueError('delta_master_full_original_changed')
    anchor=select_legal_name(roster,'2308.TW','台達電',today=datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date())
    rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='2308']
    if (not anchor or anchor['legal_name']!='台達電子工業股份有限公司'or anchor['official_ubn']!='34051920'
        or len(rows)!=1 or rows[0].get('英文簡稱')!='DELTA'or rows[0].get('網址')!='https://www.deltaww.com/zh-TW/index'):
        raise ValueError('delta_master_identity_mismatch')
    return {**anchor,'fetched_at_epoch':start}

def project(batch,data,now):
    if not valid_context(data):raise ValueError('delta_context_identity_mismatch')
    anchor=current_master(now);bodies=batch_bodies(batch,now);url=batch['originals'][1]['url']
    parsed=parse_article(*bodies,url,today=datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date())
    parsed.pop('native_owner_and_production_admission');parsed.pop('new_source_acquisition')
    return {**parsed,'date':parsed['published_on'],'link':url,'source_document_url':url,'source':'台達電官網',
      'source_type':'first_party_issuer_news','event_assessment':'not_assessed','publication_date_precision':'day',
      'publication_date_original':parsed['published_on'],'summary':parsed['text'][:280],
      'issuer_news_receipt':{'policy':'delta-native-inline-press:v1','ticker':'2308.TW'},
      'issuer_evidence':anchor,'fetched_at_epoch':batch['fetched_at_epoch'],'delta_press_receipt':deepcopy(batch)}

def verified_record(value,data,*,today=None,now=None):
    now=time.time()if now is None else now
    try:
        if today is not None and today!=datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date():return None
        if not isinstance(value,dict)or not isinstance(value.get('delta_press_receipt'),dict):return None
        expected=project(value['delta_press_receipt'],data,now)
        if dump(value)==dump(expected):return '台達電'
        # The existing freshness policy adds only its deterministic ordering
        # projection. UTC midnight here is that policy's date representation,
        # never evidence of the publisher's clock or timezone. All original
        # day-precision fields, body and private proof remain exact.
        from datetime import timezone,timedelta
        from config import CATALYST_LOOKBACK_DAYS
        from news_freshness_policy import _normalized
        reference=datetime.fromtimestamp(now,timezone.utc)
        normalized=_normalized(expected,reference,reference-timedelta(days=CATALYST_LOOKBACK_DAYS))
        return '台達電'if dump(value)==dump(normalized)else None
    except(ValueError,TypeError,KeyError,OSError,AttributeError,OverflowError,RecursionError,UnicodeError):return None
