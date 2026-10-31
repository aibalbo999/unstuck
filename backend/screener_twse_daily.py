"""Date-verified free TWSE daily fallback; never relabel a stale feed."""
from datetime import date,datetime,time
import hashlib
import json
import math
from zoneinfo import ZoneInfo
import pandas as pd
from market_screener_utils import clean_tw_stock_id,is_common_tw_stock_id,clean_company_name,twse_date_to_iso

DAILY_URL='https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
AVERAGE_URL='https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL'
DATED_URL='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'


def numeric(value):
    if isinstance(value,bool): return None
    try:
        text=str(value).strip().replace(',','')
        result=float(text)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None


def observed_date(value):
    text=twse_date_to_iso(value)
    try:return date.fromisoformat(text).isoformat()
    except (ValueError,TypeError):return ''


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def dated_rows(payload,required):
    if not isinstance(payload,dict) or payload.get('stat')!='OK' or observed_date(payload.get('date'))!=required:
        return []
    required_fields={'證券代號','證券名稱','成交股數','收盤價'}
    for table in payload.get('tables') or []:
        fields=table.get('fields') or []
        if not required_fields.issubset(fields):continue
        result=[]
        for values in table.get('data') or []:
            if not isinstance(values,list) or len(values)!=len(fields):continue
            row=dict(zip(fields,values));result.append({'Date':payload['date'],'Code':row['證券代號'],'Name':row['證券名稱'],'ClosingPrice':row['收盤價'],'TradeVolume':row['成交股數']})
        return result
    return []


def daily_frame(source,scan_date):
    from two_week_market_eligibility import completed_session
    required=completed_session(datetime.combine(scan_date,time(23,59),ZoneInfo('Asia/Taipei')))
    # The requested query date is still explicit when calendar coverage is unknown;
    # no calendar-verification or actionable claim is made in that case.
    required=required or scan_date.isoformat()
    warnings=[]
    try:rows=source._json_get(DAILY_URL)
    except Exception as exc:
        rows=[];warnings.append({'provider':source.provider_name,'operation':'daily prices','code':'openapi_daily_unavailable','message':str(exc)[:160]})
    chosen_url=DAILY_URL;chosen_payload=rows
    dates={observed_date(x.get('Date')) for x in rows if isinstance(x,dict)}
    if required not in dates:
        warnings.append({'provider':source.provider_name,'operation':'daily prices','code':'openapi_daily_date_mismatch','required_date':required,'observed_dates':sorted(dates),'message':'OpenAPI行情日期未達所需交易日；查驗指定日期官方收盤表，舊日期不重填。'})
        params={'date':required.replace('-',''),'type':'ALL','response':'json'}
        try:
            response=source._get(DATED_URL,params=params);payload=response.json();fallback=dated_rows(payload,required)
            if fallback:
                rows=fallback;chosen_payload=payload;chosen_url=DATED_URL+'?date='+params['date']+'&type=ALL&response=json'
                warnings.append({'provider':source.provider_name,'operation':'daily prices','code':'dated_daily_fallback_used','required_date':required,'message':'已使用日期核對一致的TWSE每日收盤表；成交量單位為股，未升格為合格交易候選。'})
            else:
                warnings.append({'provider':source.provider_name,'operation':'daily prices','code':'dated_daily_not_verified','required_date':required,'message':'指定日期收盤表不可驗證；保留舊資料實際日期／未知欄位，不補成當日。'})
        except Exception as exc:
            warnings.append({'provider':source.provider_name,'operation':'daily prices','code':'dated_daily_unavailable','required_date':required,'message':str(exc)[:160]})
    try:averages=source._json_get(AVERAGE_URL)
    except Exception as exc:
        averages=[];warnings.append({'provider':source.provider_name,'operation':'monthly average','code':'monthly_average_unavailable','message':str(exc)[:160]})
    average_by_key={(clean_tw_stock_id(x.get('Code')),observed_date(x.get('Date'))):numeric(x.get('MonthlyAveragePrice')) for x in averages if isinstance(x,dict)}
    average_codes={key[0] for key in average_by_key}
    sha=fingerprint(chosen_payload);records=[];mismatched_average=0
    for row in rows:
        if not isinstance(row,dict):continue
        code=clean_tw_stock_id(row.get('Code') or row.get('證券代號'))
        if not is_common_tw_stock_id(code):continue
        day=observed_date(row.get('Date'));average=average_by_key.get((code,day)) if day else None
        if average is None and code in average_codes:mismatched_average+=1
        records.append({'date':day,'stock_id':code,'company_name':clean_company_name(row.get('Name') or row.get('證券名稱')),
            'close':numeric(row.get('ClosingPrice') if 'ClosingPrice' in row else row.get('收盤價')),
            'Trading_Volume':numeric(row.get('TradeVolume') if 'TradeVolume' in row else row.get('成交股數')),
            'monthly_average_close':average,'monthly_average_observation_date':day if average is not None else None,
            'price_source_url':chosen_url,'volume_source_url':chosen_url,'latest_volume_unit':'shares',
            'price_response_sha256':sha,'response_hash_kind':'canonical_decoded_json;not archived raw HTTP bytes',
            'source_security_code':code,'source_security_policy':'twse-exact-source-code:v1'})
    if mismatched_average:
        warnings.append({'provider':source.provider_name,'operation':'monthly average','code':'monthly_average_date_not_matched','affected_rows':mismatched_average,'message':'月均價日期未對齊行情，未拿舊月均價推算當日乖離；20日歷史與量比仍未知。'})
    frame=pd.DataFrame(records);frame.attrs['source_warnings']=warnings
    return frame
