"""Archive only native issuer-bound public Yahoo JSON; never request queries."""
import json,math,re,time
from urllib.parse import urlsplit,parse_qs,unquote,quote
OWNERS={'market_data':('market_data','yfinance'),
        'global_market_context':('global_market_context','yfinance global context'),
        'dynamic_peer_metrics':('dynamic_peer_metrics','FinMind/yfinance')}
PRIVATE_KEYS={'apikey','authorization','cookie','setcookie','crumb','token','accesstoken','refreshtoken','password','credentials','sessionid','csrftoken','account','accounts','portfolio','portfolios'}

def same_public_path(left, right):
    """Only curl's literal/escaped caret in an exact chart-index path is equivalent."""
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    if left == right:
        return True
    pattern = r'/v8/finance/chart/(?:\^|%5[Ee])([A-Z][A-Z0-9.]{0,38})'
    first, second = re.fullmatch(pattern, left), re.fullmatch(pattern, right)
    return bool(first and second and first[1] == second[1])


def _public_tree(value,depth=0,budget=None):
    budget=[100000]if budget is None else budget
    budget[0]-=1
    if depth>40 or budget[0]<0:return False
    if isinstance(value,dict):
        return all(isinstance(k,str) and re.sub('[^a-z]','',k.lower())not in PRIVATE_KEYS
                   and _public_tree(v,depth+1,budget)for k,v in value.items())
    if isinstance(value,list):return all(_public_tree(v,depth+1,budget)for v in value)
    return value is None or isinstance(value,(str,bool,int)) or isinstance(value,float)and math.isfinite(value)

def capture_public_response(response,*,source,symbol):
    try:
        from curl_cffi.requests import Response
        from provider_correlation import current_correlation,current_source_identity
        from official_response_evidence import archive_response
        context=current_correlation()
        if (source not in OWNERS or current_source_identity()!=OWNERS[source]
                or not all(context.get(k)for k in ('ticker','fetch_id','operation_id'))
                or not isinstance(symbol,str)or not re.fullmatch(r'(?:\^[A-Z][A-Z0-9.]{0,38}|[A-Z0-9][A-Z0-9.^=-]{0,39})',symbol)
                or type(response)is not Response or response.status_code!=200
                or response.history or response.redirect_count or getattr(response,'from_cache',False)
                or response.queue is not None or response.stream_task is not None or response.astream_task is not None):return None
        if source=='market_data'and symbol!=context['ticker']:return None
        if source=='dynamic_peer_metrics'and symbol==context['ticker']:return None
        if source=='global_market_context':
            from data_fetch.market_sources.global_context import TECH_PROXY_SYMBOLS,BROAD_PROXY_SYMBOLS
            if symbol not in {row[0]for row in (*TECH_PROXY_SYMBOLS,*BROAD_PROXY_SYMBOLS)}:return None
        request=response.request
        if request is None or request.method!='GET'or request.headers.get('Authorization'):return None
        actual=urlsplit(response.url);sent=urlsplit(request.url)
        if (actual.scheme!='https'or actual.hostname not in {'query1.finance.yahoo.com','query2.finance.yahoo.com'}
                or actual.port not in (None,443)or actual.username or actual.password or actual.fragment
                or sent.scheme!='https'or sent.hostname!=actual.hostname or not same_public_path(sent.path,actual.path)
                or sent.username or sent.password or sent.port not in(None,443)or sent.fragment):return None
        body=response.content
        if not isinstance(body,bytes)or not 0<len(body)<=2_000_000:return None
        payload=json.loads(body)
        if not isinstance(payload,dict)or not _public_tree(payload):return None
        path=actual.path;source_url='https://'+actual.hostname+path
        if path.startswith('/v8/finance/chart/')and unquote(path[len('/v8/finance/chart/'):])==symbol:
            if set(payload)!={'chart'}:return None
            envelope=payload['chart'];kind='chart'
        elif path.startswith('/v10/finance/quoteSummary/')and unquote(path[len('/v10/finance/quoteSummary/'):])==symbol:
            if source=='global_market_context'or set(payload)!={'quoteSummary'}:return None
            envelope=payload['quoteSummary'];kind='summary'
        elif path=='/v7/finance/quote':
            if source=='global_market_context'or set(payload)!={'quoteResponse'}or parse_qs(actual.query).get('symbols')!=[symbol]:return None
            envelope=payload['quoteResponse'];kind='quote';source_url+='?symbols='+quote(symbol,safe='')
        else:return None
        if not isinstance(envelope,dict)or envelope.get('error')is not None:return None
        results=envelope.get('result')
        if not isinstance(results,list)or len(results)!=1 or not isinstance(results[0],dict):return None
        row=results[0]
        identity=(row.get('meta')or{}).get('symbol')if kind=='chart'else row.get('symbol')if kind=='quote'else (row.get('quoteType')or{}).get('symbol')or(row.get('price')or{}).get('symbol')
        if identity!=symbol:return None
        proof=archive_response(body,source_url=source_url,retrieved_at=time.time(),
                               evidence_kind='decoded_complete_http_response_body',max_bytes=2_000_000)
        if proof.get('status')!='archived':return None
        return {**proof,'http_status_observed':True,'response_complete':True,'cache_hit':False}
    except Exception:
        return None
