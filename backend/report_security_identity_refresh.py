"""Preserve old prices and source ages while adding a verified security type."""
from copy import deepcopy
import re
from fastapi import HTTPException
from source_applicability import instrument_type
from data_fetch.market_sources.twse_security_identity import PROVIDER,verified_security_identity


def validate_identity_refresh_context(data,ticker,audits=None):
 if not isinstance(data,dict)or data.get('ticker')!=ticker or not re.fullmatch(r'\d{4,6}\.TW(?:O)?',ticker)or instrument_type(data)!='unknown':raise HTTPException(status_code=400,detail='股別核對僅支援身分未確認的上市／上櫃快照；原明示股別保持')
 if data.get('taiwan_open_data')is not None and not isinstance(data['taiwan_open_data'],dict):raise HTTPException(status_code=400,detail='原開放資料格式無法安全保留')
 if not isinstance(data.get('data_source_notes',[]),list)or any(not isinstance(n,str)for n in data.get('data_source_notes',[])):raise HTTPException(status_code=400,detail='原資料註記格式無法安全保留')
 if audits is not None and any(a.get('source')in {'market_data','financial_statements'}and a.get('ticker')not in (None,ticker,ticker.split('.')[0])for a in audits):raise HTTPException(status_code=400,detail='保留的核心來源與股票身分不一致；原快照保持')
 identity=data.get('company_identity')
 if isinstance(identity,dict)and (identity.get('ticker')not in (None,ticker,ticker.split('.')[0])or identity.get('stock_id')not in (None,ticker.split('.')[0])):raise HTTPException(status_code=400,detail='原公司身分與股票代碼不一致；原快照保持')


def merge_security_identity(old_data,old_audits,value,audits,ticker):
 from report_source_refresh import _timestamp,_reassess_original_freshness
 validate_identity_refresh_context(old_data,ticker,old_audits)
 if not verified_security_identity(value,ticker)or not isinstance(audits,list)or len(audits)!=1:raise HTTPException(status_code=502,detail='官方股別、公司或完整原件未通過核對；原快照保持')
 identity=old_data.get('company_identity');legal=identity.get('legal_name')if isinstance(identity,dict)else None
 if legal not in (None,'')and legal!=value.get('listed_company_legal_name'):raise HTTPException(status_code=502,detail='原公司法人全名與官方主檔不一致或無法核對；原快照保持')
 audit=audits[0];usable=audit.get('status')=='success'and audit.get('cache_hit')is False and audit.get('http_request_sent')is True
 if audit.get('status')=='skipped_fresh_cache':usable=audit.get('cache_hit')is True and audit.get('http_request_sent')is False and type(audit.get('http_request_count'))is int and audit['http_request_count']==0 and audit.get('event_kind')=='cache_hit'
 if audit.get('status')=='degraded_enrichment':usable=audit.get('cache_hit')is True and audit.get('acquisition_status')=='partial_acquisition_with_cached_records'and audit.get('http_request_sent')is True
 if not usable or audit.get('source')!='taiwan_open_data'or audit.get('provider')!=PROVIDER or type(audit.get('record_count'))is not int or audit['record_count']!=1 or not audit.get('fetch_id')or audit.get('stale')is not False or _timestamp(audit)!=value['observed_at_epoch']:raise HTTPException(status_code=502,detail='官方股別取得憑據未通過核對；原快照保持')
 data=deepcopy(old_data);data.update(instrument_type=value['instrument_type'],security_identity=deepcopy(value));data['taiwan_open_data']={**(data.get('taiwan_open_data')or{}),'security_identity':deepcopy(value)}
 data['data_source_notes']=[*data.get('data_source_notes',[]),'股別採本次證交所ISIN表明示證券別及CFI；只新增股票／ETF身分，原股價、財報純量、其他開放資料與原取得時間保持，分析本文需重新執行。']
 data['source_audit']=deepcopy(old_audits)+deepcopy(audits)
 # The new component has its own receipt time. Keep the earlier aggregate
 # open-data age; this classification cannot freshen unrelated old components.
 _reassess_original_freshness(data,ticker,'instrument_identity',audits)
 return data
