"""Account for native clock notices without treating them as financial evidence.

Only saved-field consistency is checked. This does not establish a new request,
source-byte authenticity, provider publication, source freshness or admission.
"""
from datetime import date,datetime,timedelta
from urllib.parse import urlsplit,parse_qs
import math
import re
from evidence_claim_types import public_metadata_claim

_SECTION='## 報告使用範圍與判讀限制'
_ROW=re.compile(r'^\s*-\s+\*\*(原始擷取時間（台北）|報告保存與刷新（台北）|法人採用政策)[:：]\*\*\s*(.+)\s*$')
_STAMP=r'20\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{2}:\d{2}'
_FIELDS={'行情':('price_retrieved_at','data.market_data_fetched_at'),
         '法人主來源':('primary_retrieved_at','data.institutional_trading.source_provenance.retrieved_at'),
         '法人官方回應':('official_retrieved_at','data.institutional_trading.official_recovery.reports.raw_evidence.retrieved_at'),
         '保存':('report_saved_at','report_saved_at'),
         '資料截止':('analysis_input_cutoff','data.analysis_input_cutoff'),
         '來源刷新':('snapshot_refreshed_at','snapshot_refreshed_at')}


def _aware(value):
    if not isinstance(value,str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)',value):return None
    try:
        parsed=datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None and parsed.utcoffset()is not None else None
    except (ValueError,OverflowError):return None


def _map(value):return value if isinstance(value,dict)else{}

def _day(value):
    try:return date.fromisoformat(value).isoformat()if isinstance(value,str)else None
    except ValueError:return None


def _security(snapshot,data):
    values=[v for v in (snapshot.get('ticker'),data.get('ticker'),_map(data.get('company_identity')).get('ticker'))if v is not None and v!='']
    if not values or any(not isinstance(v,str)or not re.fullmatch(r'[0-9A-Z]{4,8}\.(?:TW|TWO)',v)for v in values):return None
    return values[0]if len(set(values))==1 else None


def _official_url(url,ticker,day):
    try:
        p=urlsplit(url)
        if p.scheme!='https'or p.username or p.password or p.port is not None or p.fragment:return False
        query=parse_qs(p.query,keep_blank_values=True)
    except (ValueError,TypeError,AttributeError):return False
    if ticker.endswith('.TW'):
        return (p.hostname in {'www.twse.com.tw','wwwc.twse.com.tw'}and p.path=='/rwd/zh/fund/T86'
                and query=={'response':['json'],'date':[day.replace('-','')],'selectType':['ALLBUT0999']})
    if p.hostname!='www.tpex.org.tw':return False
    return ((p.path=='/www/zh-tw/insti/dailyTrade'and query=={'date':[day.replace('-','/')],'type':['Daily'],'sect':['EW'],'response':['json']})
            or p.path=='/openapi/v1/tpex_3insti_daily_trading'and not query)


def _receipt_clock(snapshot,data,field):
    ticker=_security(snapshot,data);inst=_map(data.get('institutional_trading'))
    if ticker is None:return None,''
    if field=='primary_retrieved_at':
        raw=inst.get('source_provenance');path='data.institutional_trading.source_provenance'
        # Only genuine absence permits the explicitly named legacy archive.
        if raw is None:
            archive=inst.get('_source_record_archive')
            if not isinstance(archive,dict)or 'primary_sdk'not in archive:return None,path+'.retrieved_at'
            raw=archive['primary_sdk'];path='data.institutional_trading._source_record_archive.primary_sdk'
        row=_map(raw);query=_map(row.get('query'));start=_day(query.get('start_date'));end=_day(query.get('end_date'))
        if (row.get('status')!='archived'or row.get('source_url')not in {'https://api.finmindtrade.com/api/v3/data','https://api.finmindtrade.com/api/v4/data'}
                or query.get('dataset')!='TaiwanStockInstitutionalInvestorsBuySell'or query.get('data_id')!=ticker.split('.')[0]
                or not start or not end or start>end):return None,path+'.retrieved_at'
        return row.get('retrieved_at'),path+'.retrieved_at'
    target=_day(_map(data.get('daily_market_data')).get('as_of'))
    if target is None:return None,''
    audits=data.get('source_audit')or snapshot.get('source_audit')or[]
    audit=next((x for x in reversed(audits)if isinstance(x,dict)and x.get('source')=='institutional_trading'),{})if isinstance(audits,list)else{}
    recovery=inst.get('official_recovery')
    if recovery is None:recovery=audit.get('official_recovery')
    if recovery is not None and not isinstance(recovery,dict):return None,''
    reports=_map(recovery).get('reports');current=[]
    if reports is not None:
        if not isinstance(reports,list)or any(not isinstance(x,dict)or not _day(x.get('date'))for x in reports):return None,''
        current=[(x,f'data.institutional_trading.official_recovery.reports[{i}]')for i,x in enumerate(reports)if x['date']==target]
    if len(current)>1:return None,''
    latest=inst.get('latest_official_observation')
    if latest is not None and not isinstance(latest,dict):return None,''
    candidates=current+([(latest,'data.institutional_trading.latest_official_observation')]if latest is not None else[])
    if not candidates:return None,''
    def failed(item):
        row=item[0]
        return bool(row.get('error_kind')or str(row.get('status')or'').lower()in {'unavailable','failed','failure','error','blocked','timeout','cooldown'})
    row,path=next((x for x in candidates if failed(x)),candidates[0])
    proof=_map(row.get('raw_evidence'));url=proof.get('source_url');market='TPEX'if ticker.endswith('.TWO')else'TWSE'
    if (row.get('date')!=target or row.get('ticker')not in (None,'',ticker)or row.get('market')not in (None,'',market)
            or proof.get('status')!='archived'or type(proof.get('http_status'))is not int or proof['http_status']!=200
            or row.get('source_url')not in (None,'',url)or not _official_url(url,ticker,target)):
        return None,path+'.raw_evidence.retrieved_at'
    return proof.get('retrieved_at'),path+'.raw_evidence.retrieved_at'


def _expected(snapshot,field):
    data=_map(snapshot.get('data'));path=next(v[1]for v in _FIELDS.values()if v[0]==field)
    if field=='analysis_input_cutoff':return data.get(field),path
    if field=='report_saved_at':return snapshot.get(field),path
    if field=='snapshot_refreshed_at':return snapshot.get(field),path
    if field=='price_retrieved_at':
        direct=data.get('market_data_fetched_at')
        return (direct,path)if direct is not None else(_map(_map(data.get('source_freshness')).get('market_data')).get('fetched_at'),'data.source_freshness.market_data.fetched_at')
    return _receipt_clock(snapshot,data,field)


def operational_time_claim(claim,snapshot):
    """Return a checked typed metadata row, or None for ordinary financial text."""
    if (claim.get('financial_heading')!=_SECTION or claim.get('unit')not in ('',None)
            or claim.get('financial_amount') or not isinstance(snapshot,dict)):return None
    raw=claim.get('raw_text');match=_ROW.fullmatch(raw)if isinstance(raw,str)else None
    if match is None:return None
    section,body=match.groups();label=str(claim.get('label')or'')
    row=public_metadata_claim(claim)
    row.update(claim_type='operational_time_metadata',original_extraction_type=claim.get('claim_type'),
               verification_scope='saved_operational_metadata_consistency_only',
               independent_primary_source_verified=False,native_acquisition=False,
               source_freshness_verified=False,source_admission_upgraded=False)
    def result(status,reason,**values):
        return {**row,'status':status,'verification_reason_code':reason,**values}
    if section=='法人採用政策':
        if label!='法人採用政策':return None
        from market_evidence_policy import RECHECK_TIME
        expected=(f'{RECHECK_TIME.isoformat(timespec="minutes")}（Asia/Taipei）為內部保守重查界線，'
                  '非官方發布 SLA；時間經過不會自動升級保存資料。')
        valid=body==expected and claim.get('reported_value')==RECHECK_TIME.hour
        return result('valid'if valid else'invalid','operational_policy_matches_current_internal_rule'if valid else'operational_policy_text_mismatch',
                      reported_time=body,expected_time=expected,metadata_field='法人採用政策',basis_path='market_evidence_policy.RECHECK_TIME')
    allowed=('行情','法人主來源','法人官方回應')if section=='原始擷取時間（台北）'else('保存','資料截止','來源刷新')
    named=re.search(r'('+'|'.join(map(re.escape,allowed))+r')\s+(20\d{2}-\d{2}-\d{2})\s+(\d{2})$',label)
    if named is None:return None  # A financial amount in the same notice stays financial.
    name,day,hour=named.groups();field,path=_FIELDS[name]
    fragments=re.findall(r'(?:^|；)'+re.escape(name)+r'\s+('+_STAMP+r')',body)
    if len(fragments)!=1:
        return result('invalid','operational_time_not_qualified_format',metadata_field=name,basis_path=path,reported_time='')
    literal=fragments[0]
    try:reported=datetime.strptime(literal,'%Y-%m-%d %H:%M:%S %z')
    except ValueError:return result('invalid','operational_time_not_qualified_format',metadata_field=name,basis_path=path,reported_time=literal)
    number=claim.get('reported_value')
    valid_number=type(number)in(int,float)and math.isfinite(number)and number==reported.minute
    if (not valid_number or literal[:10]!=day or literal[11:13]!=hour
            or reported.utcoffset()!=timedelta(hours=8)):
        return result('invalid','operational_time_value_mismatch',metadata_field=name,basis_path=path,reported_time=literal)
    expected_value,selected_path=_expected(snapshot,field)
    path=selected_path or path
    expected=_aware(expected_value)
    if expected is None:
        return result('unverifiable','operational_time_source_missing_or_naive',metadata_field=name,basis_path=path,reported_time=literal,expected_time=None)
    # The native notice prints whole seconds, truncating stored fractions.
    # Compare exactly that declared resolution; never allow another second.
    valid=reported==expected.replace(microsecond=0)
    return result('valid'if valid else'invalid','operational_time_matches_saved_metadata'if valid else'operational_time_value_mismatch',
                  metadata_field=name,basis_path=path,reported_time=literal,expected_time=expected.isoformat(),
                  expected_display_time=expected.astimezone(reported.tzinfo).strftime('%Y-%m-%d %H:%M:%S')+' +08:00',
                  display_precision='whole_seconds_truncated_by_native_formatter')
