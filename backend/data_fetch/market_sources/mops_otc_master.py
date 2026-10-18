"""TPEx-only master adapter retaining existing acquisition guards and receipts."""
import json
import re

from search_provider_runtime import SourceResponseError
from .auras_conference_transport import AurasConferenceHttp, MASTER as OTC_MASTER
from .tcfhc_conference_transport import original_bytes as _original_bytes
from .official_issuer_master_json import _pairs

FIELDS = {'SecuritiesCompanyCode':'公司代號', 'CompanyName':'公司名稱',
          'CompanyAbbreviation':'公司簡稱', 'UnifiedBusinessNo.':'營利事業統一編號',
          'WebAddress':'網址', 'Symbol':'英文簡稱', 'Date':'出表日期'}


def contract(url):
    if url != OTC_MASTER:
        raise SourceResponseError('transport_url_invalid')
    return 2_500_000, {'application/json','text/json'}


class OtcMasterHttp(AurasConferenceHttp):
    # Reuse the existing same-URL raw cache/admission namespace and host guard;
    # changing caller must not create a way around an earlier failed request.
    route_contract = staticmethod(contract)


def original_bytes(receipt, url, *, max_age):
    return _original_bytes(receipt, url, max_age=max_age, url_contract=contract)


def parse_rows(raw):
    rows=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=_pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite OTC master')))
    if (not isinstance(rows,list) or not 700 <= len(rows) <= 2000
            or any(not isinstance(r,dict) or not FIELDS.keys() <= r.keys()
                   or any(not isinstance(v,str) for v in r.values()) for r in rows)):
        raise ValueError('incomplete OTC master')
    codes=[r['SecuritiesCompanyCode'] for r in rows]
    if len(set(codes))!=len(codes) or any(not re.fullmatch(r'\d{4,6}',s) for s in codes):
        raise ValueError('ambiguous OTC master')
    return [{target:r[key] for key,target in FIELDS.items()} for r in rows]
