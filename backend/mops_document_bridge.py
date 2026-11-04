"""Pathless, replay-verified MOPS originals for the local document index.

This adapter performs no HTTP and records no acquisition. It validates individual
published originals; it cannot establish complete thirty-day window coverage.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import re

SCHEMA = 'mops-json-original-document.v1'
KIND = 'mops_major_announcement'
RECEIPT_KEYS = {'status','source_url','retrieved_at','http_status','raw_response_sha256',
    'raw_response_bytes','evidence_kind','historical_point_in_time_verified','finality_guaranteed'}
PACKET_KEYS = {'policy','ticker','index_query','index_row','index_receipt','detail_receipt'}
CONTEXT_KEYS = {'ticker','stock_id','instrument_type','quote_type','quoteType','company_identity'}
IDENTITY_KEYS = {'ticker','stock_id','official_name','legal_name','instrument_type','forbidden_aliases'}


def _context(data):
    if not isinstance(data,dict): raise ValueError('MOPS document context missing')
    value = {k:deepcopy(v) for k,v in data.items() if k in CONTEXT_KEYS}
    identity = value.get('company_identity')
    if isinstance(identity,dict):
        value['company_identity'] = {k:v for k,v in identity.items() if k in IDENTITY_KEYS}
    if len(json.dumps(value,ensure_ascii=False)) > 4000:
        raise ValueError('MOPS document identity over limit')
    return value


def _reference(receipt):
    if not isinstance(receipt,dict) or not RECEIPT_KEYS <= set(receipt):
        raise ValueError('MOPS original receipt missing')
    return {k:deepcopy(receipt[k]) for k in RECEIPT_KEYS}


def _restore(reference):
    from runtime_paths import current_runtime_paths
    if not isinstance(reference,dict) or set(reference) != RECEIPT_KEYS:
        raise ValueError('MOPS original receipt reference invalid')
    digest = reference['raw_response_sha256']
    if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest):
        raise ValueError('MOPS original receipt hash invalid')
    if (reference['evidence_kind'] != 'raw_http_response_bytes'
            or reference['historical_point_in_time_verified'] is not False
            or reference['finality_guaranteed'] is not False):
        raise ValueError('MOPS original evidence contract invalid')
    path = current_runtime_paths().cache_dir / 'official-response-evidence' / (digest+'.gz')
    return {**reference,'raw_response_path':str(path)}



def _pathless_master(value, *, restore=False):
    if isinstance(value,list):
        return [_pathless_master(item,restore=restore)for item in value]
    if not isinstance(value,dict):return deepcopy(value)
    if restore and 'raw_response_path' in value:
        raise ValueError('MOPS master proof contains a private path')
    result = {k:_pathless_master(v,restore=restore)for k,v in value.items()if k!='raw_response_path'}
    if restore and 'raw_response_sha256'in result:
        from runtime_paths import current_runtime_paths
        digest = result['raw_response_sha256']
        if not isinstance(digest,str)or not re.fullmatch(r'[0-9a-f]{64}',digest):
            raise ValueError('MOPS master proof hash invalid')
        result['raw_response_path'] = str(current_runtime_paths().cache_dir/'official-response-evidence'/(digest+'.gz'))
    return result


def _canonical(evidence, *, fingerprint=False):
    from data_fetch.market_sources import mops_json_company_history as source
    from data_fetch.market_sources.mops_master_bound_announcements import POLICY as MASTER_POLICY
    if (not isinstance(evidence,dict) or set(evidence) != {'schema','context','packet'}
            or evidence['schema'] != SCHEMA or not isinstance(evidence['packet'],dict)
            or set(evidence['packet']) != (PACKET_KEYS|{'issuer_master'} if evidence['packet'].get('policy')==MASTER_POLICY else PACKET_KEYS)):
        raise ValueError('MOPS document proof invalid')
    context = _context(evidence['context'])
    if context != evidence['context']:
        raise ValueError('MOPS document proof has unknown identity fields')
    packet = deepcopy(evidence['packet'])
    for key in ('index_receipt','detail_receipt'):
        packet[key] = _restore(packet[key])
    if 'issuer_master'in packet:
        packet['issuer_master'] = _pathless_master(packet['issuer_master'],restore=True)
    result = source.rebuild_json_original(packet,context)
    if result is None: raise ValueError('MOPS document original replay rejected')
    record, _ = result
    stamp, index_stamp = packet['detail_receipt']['retrieved_at'], packet['index_receipt']['retrieved_at']
    published = datetime.fromisoformat(record['published_at'])
    if (published.tzinfo is None or not published.timestamp() <= min(index_stamp,stamp)
            or type(stamp) not in (int,float) or not math.isfinite(stamp)):
        raise ValueError('MOPS document publication/acquisition order invalid')
    action = record['source_request_parameters']
    identity = json.dumps([record['ticker'],action],sort_keys=True,separators=(',',':'))
    document = {'ticker':record['ticker'],'document_id':'mops-json:'+sha256(identity.encode()).hexdigest(),
        'title':record['title'],'url':source.PAGE_URL,'published_at':record['published_at'],
        'event_date':None,'source':source.PROVIDER,'source_type':'official_disclosure','document_kind':KIND,
        'text':record['text'],'summary':record['summary'],'content_truncated':False,
        'content_sha256':sha256(record['text'].encode()).hexdigest(),'coverage_status':'text_available',
        'retrieved_at_epoch':stamp,'original_body_sha256':packet['detail_receipt']['raw_response_sha256'],
        'original_evidence':deepcopy(evidence)}
    if not fingerprint:return document
    # Preserve the entire publisher result, including unrendered fields. Only
    # the known response clock is envelope metadata rather than content.
    payload=json.loads(source._saved(packet['detail_receipt'],source.ORDINARY_DETAIL_URL))
    payload.pop('datetime',None)
    digest=sha256(json.dumps([identity,payload],ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return document,digest


def document_from_record(record, data):
    from data_fetch.market_sources.mops_json_company_history import verified_json_record
    if not verified_json_record(record,data):
        raise ValueError('MOPS record original rejected')
    original = record['mops_json_receipt']
    packet = {k:deepcopy(original[k]) for k in PACKET_KEYS}
    if 'issuer_master'in original:
        packet['issuer_master'] = _pathless_master(original['issuer_master'])
    for key in ('index_receipt','detail_receipt'): packet[key] = _reference(packet[key])
    return _canonical({'schema':SCHEMA,'context':_context(data),'packet':packet})


def validate_document(document):
    if not isinstance(document,dict): raise ValueError('MOPS document missing')
    canonical = _canonical(document.get('original_evidence'))
    if any(document.get(k) != v for k,v in canonical.items()):
        raise ValueError('MOPS document differs from its original')
    return canonical


def document_revision_fingerprint(document):
    canonical,digest=_canonical(document.get('original_evidence'),fingerprint=True)
    if any(document.get(k)!=v for k,v in canonical.items()):
        raise ValueError('MOPS document differs from its original')
    return digest


def index_records(records, data, *, persist=True):
    """Reuse exact originals without renewing their source time or HTTP count."""
    documents, rejected = [], 0
    if not isinstance(records,list) or len(records)>64:
        return [], {'accepted':0,'rejected':0,'prepared':0,'persisted':False,
            'http_request_sent':False,'http_request_count':0,'new_source_successes':0,
            'coverage_status':'individual_originals_only','index_error':'records_missing_or_over_limit'}
    for record in records if isinstance(records,list) else []:
        if not isinstance(record,dict) or 'mops_json_receipt' not in record:
            continue
        try: documents.append(document_from_record(record,data))
        except (ValueError,TypeError,KeyError,OverflowError,OSError): rejected += 1
    result = {'accepted':0,'rejected':rejected,'prepared':len(documents),'persisted':False,
        'http_request_sent':False,'http_request_count':0,'new_source_successes':0,
        'coverage_status':'individual_originals_only'}
    if persist and documents:
        from source_document_index import upsert_source_documents
        try:
            stored = upsert_source_documents(documents)
            result.update(accepted=stored['accepted'],rejected=rejected+stored['rejected'],persisted=True)
        except Exception as exc:
            result['index_error'] = type(exc).__name__
    return documents, result



def _merge_documents(prior, originals, start, end):
    """Retain this issuer's recent documents, validating typed originals again."""
    ticker = originals[0]['ticker']
    merged = {}
    for document in (prior if isinstance(prior,list) else []) + originals:
        if not isinstance(document,dict):
            continue
        document_id = document.get('document_id')
        if (document.get('ticker') != ticker or document.get('source_type') != 'official_disclosure'
                or not isinstance(document_id,str) or not document_id):
            continue
        try:
            published = datetime.fromisoformat(document['published_at'])
            if published.tzinfo is None or not start <= published <= end:
                continue
            if ('original_evidence' in document or document.get('document_kind') == KIND
                    or document_id.startswith('mops-json:')):
                validate_document(document)
        except (ValueError,TypeError,KeyError,OverflowError,OSError):
            continue
        merged[document_id] = document
    return sorted(merged.values(),key=lambda d:(d['published_at'],d['document_id']),reverse=True)[:100]


def hydrate_provider_documents(results, data, *, persist=True):
    """Join after parallel acquisition, so the daily snapshot cannot race away
    originals acquired in this same request. This local join owns no HTTP.
    """
    from dataclasses import replace
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from data_fetch.types import ProviderResult
    records = []
    for result in results:
        if (result.source == 'recent_catalysts' and result.provider == 'TWSE company announcement history'
                and result.status in {'success','degraded_enrichment','skipped_fresh_cache'}
                and isinstance(result.value,list)):
            records.extend(result.value)
    if not records:
        records = data.get('recent_catalysts') or []
    records = [r for r in records if isinstance(r,dict) and 'mops_json_receipt' in r]
    if not records: return results
    documents, receipt = index_records(records,data,persist=persist)
    if not documents: return results
    now = datetime.now(ZoneInfo('Asia/Taipei')); start = now-timedelta(days=30)
    documents = [d for d in documents if start <= datetime.fromisoformat(d['published_at']) <= now]
    if not documents: return results
    output, joined = [], False
    for result in results:
        if result.source != 'official_disclosures':
            output.append(result); continue
        original = result.value if isinstance(result.value,dict) else {}
        prior = original.get('documents') if isinstance(original.get('documents'),list) else []
        # Native MOPS action IDs stay separate from unbound daily title IDs.
        # Neither path counts as independent media or verifies a catalyst claim.
        value = {**original,'documents':_merge_documents(prior,documents,start,now),
            'status':'partial','coverage_status':'partial','local_original_documents':receipt}
        status = 'degraded_enrichment' if result.status == 'error' else result.status
        audit = {**result.audit,'status':status,'record_count':len(value['documents']),
            'local_original_documents':receipt,'event_kind':'aggregate','http_request_sent':False}
        output.append(replace(result,status=status,value=value,audit=audit)); joined = True
    if not joined:
        stamp = max(d['retrieved_at_epoch'] for d in documents)
        original = data.get('official_disclosures')
        original = original if isinstance(original,dict) else {}
        merged = _merge_documents(original.get('documents'),documents,start,now)
        value = {**original,'documents':merged,'status':'partial',
            'coverage_status':'partial','retrieval_status':'local_original_reuse','fetched_at_epoch':stamp,
            'cache_hit':True,'local_original_documents':receipt,
            'coverage_notes':['已核對的個別MOPS公告原文；不是完整歷史或獨立媒體來源。']}
        output.append(ProviderResult('official_disclosures','TWSE/TPEx official disclosures',
            'degraded_enrichment',value=value,audit={'source':'official_disclosures','provider':'TWSE/TPEx official disclosures',
                'status':'degraded_enrichment','record_count':len(merged),'fetched_at_epoch':stamp,
                'event_kind':'aggregate','http_request_sent':False,'http_request_count':0,'cache_hit':True,
                'coverage_status':'partial','local_original_documents':receipt}))
    return output
