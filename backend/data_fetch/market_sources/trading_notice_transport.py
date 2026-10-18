"""One bounded anonymous official notice query; reuse the existing TLS transport."""
from datetime import datetime
import re
from urllib.parse import parse_qs,urlsplit

from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp

ENDPOINT='https://www.twse.com.tw/rwd/zh/announcement/notice'
MAX_BYTES=250_000


def query_params(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='www.twse.com.tw' or parsed.path!='/rwd/zh/announcement/notice' or parsed.fragment:
        raise ValueError('unverified official notice URL')
    values=parse_qs(parsed.query,keep_blank_values=True)
    if set(values)!={'startDate','endDate','stockNo','querytype','sortKind','response'} or any(len(v)!=1 for v in values.values()):
        raise ValueError('unverified official notice query')
    params={k:v[0] for k,v in values.items()}
    if not re.fullmatch(r'[1-9]\d{3}',params['stockNo']) or params['querytype']!='2' or params['sortKind']!='DATE' or params['response']!='json':
        raise ValueError('unverified official notice scope')
    days=[]
    for key in ('startDate','endDate'):
        if not re.fullmatch(r'20\d{6}',params[key]):raise ValueError('invalid notice query date')
        days.append(datetime.strptime(params[key],'%Y%m%d').date())
    if not 0<=(days[1]-days[0]).days<=30:raise ValueError('notice window exceeds limit')
    return params


def url_contract(url):
    try:query_params(url)
    except (ValueError,TypeError) as exc:raise SourceResponseError('transport_url_invalid') from exc
    return MAX_BYTES,{'application/json','text/json'}


class TradingNoticeHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)

    def _download(self,url,diagnostic):
        # The raw-cache callback must validate JSON identity before assigning
        # the successful 30-minute TTL. An HTTP-200 security/invalid envelope
        # remains a source error with the existing bounded retry protection.
        import base64,time
        from zoneinfo import ZoneInfo
        from official_response_evidence import archive_response
        from .twse_trading_notices import parse_notice_rows
        try:
            value=super()._download(url,diagnostic)
        except SourceResponseError as exc:
            diagnostic.update(exc.diagnostic)
            raise
        raw=base64.b64decode(value['body_b64'])
        diagnostic.update(http_status=200,raw_response_receipt=archive_response(
            raw,source_url=url,retrieved_at=time.time(),http_status=200))
        try:parse_notice_rows(raw,url,query_params(url)['stockNo']+'.TW',datetime.now(ZoneInfo('Asia/Taipei')))
        except (ValueError,TypeError,KeyError,RecursionError) as exc:
            diagnostic['error_kind']='parse_error'
            raise SourceResponseError('parse_error',status_code=200) from exc
        return value
