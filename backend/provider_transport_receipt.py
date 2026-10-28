"""Transport-only observations; never assert parsed data or add acquisitions."""
from hashlib import sha256
import time


def is_transport_receipt(entry):
    details=entry.get('details',entry)
    return (entry.get('record_count')==0 and isinstance(details,dict)
        and details.get('event_kind')=='http_transport_receipt'
        and details.get('selection_policy')=='transport-receipt-only:v1')


def record_job_transport_receipt(provider,started,*,response=None,native_call=False):
    try:
        import httpx
        from provider_correlation import current_correlation
        from provider_sla import record_source_audit_entries
        entry={**current_correlation(),'event_kind':'http_transport_receipt',
            'selection_policy':'transport-receipt-only:v1','source':'alternative_data',
            'provider':provider,'record_count':0,'status':'success',
            'duration_ms':max(0,int((time.monotonic()-started)*1000)),
            'message':'Transport receipt only; parsed acquisition is separately audited.'}
        if native_call and isinstance(response,httpx.Response):
            entry.update(http_request_sent=True,http_status=response.status_code,
                         response_bytes=len(response.content),response_sha256=sha256(response.content).hexdigest())
            if response.status_code>=400:entry['status']='error'
        elif getattr(response,'from_cache',False) is True:
            entry.update(cache_hit=True,http_request_sent=False)
        # Custom sessions and failures without responses do not prove HTTP was sent.
        record_source_audit_entries([entry])
    except Exception:
        # Diagnostics cannot change provider results or error behavior.
        pass
