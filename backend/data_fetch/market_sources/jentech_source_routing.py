"""Read-only choice between independently qualified Jentech originals.

The previous request supplies failure evidence. The chosen source still performs
all its own current admission, issuer, original, parser and freshness checks.
There is no second source attempt after this invocation starts acquiring data.
"""
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
import time

POLICY='qualified-issuer-after-prior-mops-transport:v1'
_REFUSALS={'authentication','payment_required','access_denied','rate_limited',
           'context_unverified','original_unverified','parse_error'}
_RECOVERABLE={'timeout','transport_error','server_error'}
_MOPS_ENDPOINTS={sha256(url.encode()).hexdigest()for url in(
    'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1',
    'https://mopsov.twse.com.tw/server-java/FileDownLoad')}


def prior_mops_transport_failure(ticker):
    if not isinstance(ticker,str)or ticker.strip().upper()!='3653.TW':return None
    from provider_sla import TASK_DB_PATH
    path=Path(TASK_DB_PATH)
    if not path.exists():return None
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)as db:
            rows=db.execute('SELECT id,created_at,status,record_count,details_json FROM provider_sla_events '
                'WHERE source=? AND provider=? ORDER BY id DESC LIMIT 512',
                ('earnings_call','MOPS published presentation')).fetchall()
        pending=None
        wrapper_id=None
        for event_id,created,status,count,raw in rows:
            try:details=json.loads(raw or '{}')
            except (TypeError,ValueError):continue
            if not isinstance(details,dict)or details.get('ticker')!='3653.TW':continue
            if details.get('cache_hit')is True or details.get('cooldown')is True:continue
            if (type(created)not in(int,float)or not math.isfinite(created)
                    or not 0<=time.time()-created<86400):return None
            kind=details.get('error_kind')
            if status!='error' or type(count)is not int or count!=0 or kind not in _RECOVERABLE:return None
            if details.get('http_status')in(401,402,403,429):return None
            components=details.get('component_statuses')
            if isinstance(components,dict):
                if not all(isinstance(k,str)and k.isdigit()for k in components):return None
                components=[components[k]for k in sorted(components,key=int)]
            if not isinstance(components,list)or not 1<=len(components)<=20:return None
            if any(not isinstance(c,dict)or c.get('http_status')in(401,402,403,429)
                    or c.get('error_kind')in _REFUSALS for c in components):return None
            final=components[-1]
            signature=(created,status,count,kind,details.get('fetch_id'),details.get('operation_id'),
                [{k:v for k,v in c.items()if k!='request_url_sha256'}for c in components])
            if pending is not None and signature!=pending:return None
            # Older aggregate wrappers dropped the URL hash on the second
            # metadata projection. Only the identical native operation/time/
            # component facts may supply that missing field; never an older or
            # different failure. Preserve both authoritative rows unchanged.
            if final.get('request_url_sha256')is None:
                import re
                if not all(isinstance(v,str)and re.fullmatch('[0-9a-f]{32}',v)
                        for v in (details.get('fetch_id'),details.get('operation_id'))):return None
                pending=signature;wrapper_id=wrapper_id or event_id
                continue
            if (final.get('http_request_sent')is not True or final.get('error_kind')not in _RECOVERABLE
                    or final.get('request_url_sha256')not in _MOPS_ENDPOINTS
                    or final.get('request_method')!='POST' or final.get('response_complete')is True):return None
            return {'event_id':event_id,'created_at':created,'error_kind':kind,
                    'correlated_wrapper_event_id':wrapper_id}
    except (sqlite3.Error,OSError,ValueError,TypeError,OverflowError):
        pass
    return None
