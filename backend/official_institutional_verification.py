"""Bounded archived official verification; never fetch 30 days during rendering."""
import hashlib
import json
from datetime import datetime
from official_institutional_source import _parse_report, _url

SCHEMA='official-institutional-verification:v1'


def cache_key(ticker, as_of):
    return f'{SCHEMA}:{ticker}:{as_of}'


def prepare_archived_verification(manifest, read_bytes):
    """Validate archived HTTP bytes before retaining a compact exact-security excerpt."""
    proof={k:manifest[k] for k in ('ticker','as_of','population','unit','window_dates')}
    proof.update(schema_version=SCHEMA, historical_pit_verified=False, reports=[])
    code=proof['ticker'].split('.')[0]
    for report in manifest['reports']:
        if not report.get('raw_response_path'):
            proof['reports'].append({'date':report['date'],'status':'unavailable'})
            continue
        body=read_bytes(report['raw_response_path'])
        assert hashlib.sha256(body).hexdigest()==report['raw_response_sha256']
        assert report['source_url']==_url('TWSE',report['date']) and report['http_status']==200
        payload=json.loads(body);parsed=_parse_report(payload,'TWSE',report['date'])
        rows=[r for r in payload['data'] if str(r[0]).strip()==code]
        excerpt={k:payload[k] for k in ('stat','date','fields','hints')}
        excerpt['data']=rows
        proof['reports'].append({k:report[k] for k in ('date','source_url','raw_response_path','raw_response_sha256','retrieved_at','http_status') } | {'source_excerpt':excerpt})
    proof['evidence_payload_sha256']=hashlib.sha256(json.dumps(proof,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return proof


def evaluate_official_verification(proof, data, lineage):
    result={'status':'unavailable','historical_pit_verified':False,'causation_or_return_verified':False}
    if not isinstance(proof,dict) or proof.get('schema_version')!=SCHEMA:
        return dict(result,reason='no_bound_official_evidence')
    content={k:v for k,v in proof.items() if k!='evidence_payload_sha256'}
    if proof.get('evidence_payload_sha256')!=hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest():
        return dict(result,reason='official_evidence_payload_changed')
    if lineage.get('population')!='foreign':
        return dict(result,reason='official_proof_covers_foreign_only')
    if (proof.get('ticker')!=data.get('ticker') or proof.get('as_of')!=lineage.get('observed_at')
            or proof.get('unit')!='shares' or proof.get('population')!='foreign_including_foreign_dealer'):
        return dict(result,reason='ticker_endpoint_population_or_unit_mismatch')
    dates=lineage.get('observation_dates') or []; reports=proof.get('reports') or []
    if not dates or not isinstance(reports,list):return dict(result,reason='window_unknown')
    if not isinstance(proof.get('window_dates'),list) or not set(dates).issubset(set(proof['window_dates'])):
        return dict(result,reason='official_window_not_bound')
    comparisons=[]
    rows=(data.get('institutional_trading') or {}).get('daily_category_observations') or []
    for day in dates:
        candidates=[r for r in reports if isinstance(r,dict) and r.get('date')==day]
        provider=[r for r in rows if isinstance(r,dict) and r.get('date')==day and r.get('category')=='foreign']
        if len(candidates)!=1 or len(provider)!=1:
            comparisons.append({'date':day,'status':'missing_or_duplicate_evidence'});continue
        r=candidates[0]
        try:
            digest=r['raw_response_sha256']
            assert isinstance(digest,str) and len(digest)==64 and int(digest,16)>=0
            assert r['http_status']==200 and r['source_url']==_url('TWSE',day)
            acquired=datetime.fromisoformat(r['retrieved_at']);assert acquired.tzinfo is not None
            parsed=_parse_report(r['source_excerpt'],'TWSE',day)
            official=parsed['rows'].get(str(data['ticker']).split('.')[0]);assert official is not None
            expected=provider[0]['net_buy_shares'];actual=official['foreign']
            comparisons.append({'date':day,'status':'matched' if actual==expected else 'mismatch',
                                'provider_shares':expected,'official_shares':actual,'delta_shares':actual-expected,
                                'source_url':r['source_url'],'raw_response_path':r['raw_response_path'],
                                'raw_response_sha256':digest,'retrieved_at':r['retrieved_at']})
        except (KeyError,AssertionError,TypeError,ValueError,OverflowError):
            comparisons.append({'date':day,'status':'missing_or_invalid_official_evidence'})
    status='mismatch' if any(r['status']=='mismatch' for r in comparisons) else 'matched' if all(r['status']=='matched' for r in comparisons) else 'incomplete'
    return dict(result,status=status,scope='official T86 foreign plus foreign dealer; exact dates/shares as acquired',
                checked_dates=dates,matched_count=sum(r['status']=='matched' for r in comparisons),comparisons=comparisons,
                official_total_shares=sum(r.get('official_shares',0) for r in comparisons) if status=='matched' else None)


def attach_cached_verification(value,ticker):
    """Only adopt a previously acquired explicit scope; no network or wider scan."""
    from cache_store import get_cache_json
    try:
        proof=get_cache_json(cache_key(ticker,value.get('latest_date')))
    except Exception:
        return value  # Missing proof remains unverified; primary acquisition survives.
    if isinstance(proof,dict) and proof.get('ticker')==ticker and proof.get('as_of')==value.get('latest_date'):
        value['official_verification']=proof
    return value
