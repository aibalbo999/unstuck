"""Transport-only receipts for the existing international-news GET paths.

No network, retry, cache, parsing or admission changes. Original responses stay
with the caller; only exact currently owned, materialized HTTP bytes are audited.
"""
import hashlib
import time
from urllib.parse import urlsplit, parse_qs

SOURCE='international_news_context'
OWNER=(SOURCE,'GDELT / Google News RSS')
ENDPOINTS={('api.gdeltproject.org','/api/v2/doc/doc'):'GDELT native HTTP',
           ('news.google.com','/rss/search'):'Google News international RSS native HTTP'}


def begin(url):
    try:
        from provider_correlation import current_correlation,current_source_identity
        parsed=urlsplit(str(url));context=current_correlation()
        if (current_source_identity()!=OWNER or parsed.scheme!='https' or parsed.username or parsed.password
                or parsed.port not in (None,443) or (parsed.hostname,parsed.path) not in ENDPOINTS
                or any(not context.get(k) for k in ('ticker','fetch_id','operation_id'))):
            return None
        return {'owner':OWNER,'context':context,'host':parsed.hostname,'path':parsed.path,
                'started':time.monotonic()}
    except Exception:
        return None


def record(binding,response):
    try:
        if binding is None:return
        from provider_correlation import current_correlation,current_source_identity
        from provider_sla import record_source_audit_entries
        context=current_correlation();original=binding['context']
        if (current_source_identity()!=binding['owner'] or
                any(context.get(k)!=original.get(k) for k in ('job_id','ticker','fetch_id','operation_id','attempt_id'))):
            return
        actual=urlsplit(str(response.url));request=response.request
        if (request.method!='GET' or actual.scheme!='https' or actual.username or actual.password
                or actual.port not in (None,443) or (actual.hostname,actual.path)!=(binding['host'],binding['path'])
                or getattr(response,'from_cache',False) or response.extensions.get('from_cache') is True):
            return
        body=response.content  # Never consume a stream to produce telemetry.
        if not isinstance(body,bytes):return
        status=response.status_code
        receipt = None
        if status == 200 and (actual.hostname,actual.path) == ('news.google.com','/rss/search'):
            try:
                import httpx
                from external_data_gdelt import GDELT_TOPIC_QUERIES
                from xml.etree.ElementTree import fromstring
                from official_response_evidence import archive_response
                query = parse_qs(actual.query, keep_blank_values=True)
                if (type(response) is httpx.Response and 0 < len(body) <= 2_000_000
                        and not any(request.headers.get(k) for k in ('authorization','cookie','proxy-authorization'))
                        and not actual.fragment and set(query) == {'q','hl','gl','ceid'}
                        and query.get('hl') == ['en-US'] and query.get('gl') == ['US']
                        and query.get('ceid') == ['US:en']
                        and query.get('q') in [[q] for base in GDELT_TOPIC_QUERIES.values()
                                                for q in (base, base+' when:7d')]
                        and b'\x00' not in body and b'<!DOCTYPE' not in body.upper()
                        and b'<!ENTITY' not in body.upper() and fromstring(body).tag == 'rss'):
                    receipt = archive_response(body, source_url='https://news.google.com/rss/search',
                        retrieved_at=time.time(), evidence_kind='decoded_complete_http_response_body',max_bytes=2_000_000)
                    if receipt.get('status')=='archived':
                        receipt.update(http_status_observed=True,response_complete=True,cache_hit=False)
                    else:
                        receipt = None
            except Exception:
                receipt = None
        record_source_audit_entries([{**original,'source':SOURCE,'provider':ENDPOINTS[(actual.hostname,actual.path)],
            'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
            'record_count':0,'http_request_sent':True,'http_status':status,
            'status':'success' if 200<=status<300 else 'error',
            'response_bytes':len(body),'response_sha256':hashlib.sha256(body).hexdigest(),'raw_http_receipt':receipt,
            'source_url':f'https://{actual.hostname}{actual.path}',
            'duration_ms':max(0,int((time.monotonic()-binding['started'])*1000)),
            'message':'Native international-news transport only; parsed news and acquisition success are separately audited.'}])
    except Exception:
        pass  # Telemetry must not discard or replace the existing result/error.
