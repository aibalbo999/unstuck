"""Source-only railway repair keeps original analysis and quality evidence."""
from fastapi import HTTPException
from data_fetch.market_sources.official_railway_peer_cohort import TARGET,SHORT,LEGAL,IDENTITIES,verified_candidates
from thermal_peer_source_refresh import _merge_segment_peer_source


def validate_context(data,ticker):
    from source_applicability import instrument_type
    if(ticker!=TARGET or not isinstance(data,dict)or data.get('ticker')!=TARGET
            or str(data.get('company_name')or'').split('/')[0].strip()not in{SHORT,LEGAL}
            or instrument_type(data)!='EQUITY'or not isinstance(data.get('dynamic_peer_metrics'),list)
            or any(data.get(k)not in(None,'','EQUITY')for k in('instrument_type','quoteType','quote_type'))):
        raise HTTPException(status_code=400,detail='此同業來源刷新須有一致的台灣高鐵股票身分及原指標清單')
    identity=data.get('company_identity')
    if isinstance(identity,dict):
        stock=identity.get('stock_id')
        if(identity.get('ticker')not in(None,'',TARGET)
                or stock not in(None,'')and(type(stock)not in(str,int)or str(stock)!='2633')
                or identity.get('official_name')not in(None,'',SHORT,LEGAL)):
            raise HTTPException(status_code=400,detail='原公司身分與台灣高鐵來源不一致')


def merge_source(old_data,old_audits,value,audits,ticker):
    try:
        if not isinstance(value,list)or any(r.get('quote_currency')!='JPY'or r.get('financial_currency')!='JPY'for r in value):
            raise ValueError('rail_currency_unverified')
        if any(r.get('asset_turnover')is not None and(r.get('metric_sources',{}).get('asset_turnover',{}).get('currency')!='JPY')for r in value):
            raise ValueError('rail_annual_currency_unverified')
        if len(value)<len(IDENTITIES)and any(a.get('status')=='success'for a in audits):raise ValueError('rail_partial_cohort_mislabeled')
    except(ValueError,TypeError,AttributeError)as exc:
        raise HTTPException(status_code=502,detail='鐵道同業的幣別或部分取得標示未通過核對；原快照保持')from exc
    return _merge_segment_peer_source(old_data,old_audits,value,audits,ticker,
        validate_context=validate_context,verify_candidates=verified_candidates)
