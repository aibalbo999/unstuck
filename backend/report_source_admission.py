"""Exact latest-session admission from bound raw official evidence, not age alone."""
import json
from datetime import datetime


def institutional_admission(value, expected_date):
    value=value if isinstance(value,dict) else {}
    result={'status':'unavailable','eligible':False,'expected_date':expected_date,'observed_date':value.get('latest_date'),
            'historical_point_in_time_verified':False,'finality_guaranteed':False}
    def fail(reason):return {**result,'reason':reason}
    if not expected_date or value.get('latest_date')!=expected_date:
        return fail('latest_institutional_session_missing')
    official=value.get('latest_official_observation') or {}
    proof=official.get('raw_evidence') or {}
    if official.get('date')!=expected_date or proof.get('status')!='archived' or proof.get('evidence_kind')!='raw_http_response_bytes':
        return fail('latest_official_raw_evidence_missing')
    try:
        from market_evidence_policy import acquisition_phase
        acquired=datetime.fromisoformat(proof['retrieved_at'])
        if acquired.tzinfo is None or acquisition_phase(expected_date,acquired)!='post_cutoff':
            return fail('official_observation_is_provisional')
        from official_institutional_source import _parse_report,_url
        from official_response_evidence import read_response
        market=official['market'];ticker=official['ticker'];code=ticker.split('.')[0]
        from tpex_openapi_institutional import URL as TPEX_OPENAPI_URL, parse_latest_report
        source_url=proof['source_url']
        allowed_urls = {_url(market, expected_date)}
        if market == 'TPEX':
            allowed_urls.add(TPEX_OPENAPI_URL)
        elif market == 'TWSE':
            # The bounded transport already uses this official mirror after
            # primary failure. Keep the exact path, date, query and HTTPS.
            allowed_urls.add(_url(market, expected_date).replace('https://www.twse.com.tw/',
                                                               'https://wwwc.twse.com.tw/', 1))
        if source_url not in allowed_urls or proof.get('http_status')!=200:
            return fail('official_evidence_endpoint_mismatch')
        raw=read_response(proof)
        row=(parse_latest_report(raw,expected_date) if source_url==TPEX_OPENAPI_URL
             else _parse_report(json.loads(raw),market,expected_date))['rows'].get(code)
        if row is None:return fail('official_security_missing')
        observations=[r for r in value.get('daily_category_observations',[]) if r.get('date')==expected_date]
        for category in ('foreign','investment_trust','dealer'):
            matches=[r for r in observations if r.get('category')==category]
            if len(matches)!=1 or matches[0].get('unit')!='shares' or matches[0].get('net_buy_shares')!=row[category]:
                return fail('primary_official_latest_categories_mismatch')
    except (OSError,ValueError,KeyError,TypeError,AttributeError,EOFError):
        return fail('official_raw_evidence_invalid')
    return {**result,'status':'matched_post_cutoff_raw_observation','eligible':True,'reason':'latest_categories_match_archived_official_response',
            'raw_evidence':proof,'unit':'shares','scope':'foreign including foreign dealer;investment trust;dealer;exact date'}


def price_admission(daily, ticker):
    expected=daily.get('as_of');official=daily.get('official_observation') or {};proof=official.get('raw_evidence') or {}
    result={'eligible':False,'expected_date':expected,'historical_point_in_time_verified':False,'finality_guaranteed':False}
    def fail(reason):return {**result,'reason':reason}
    if official.get('ticker')!=ticker or official.get('date')!=expected or proof.get('status')!='archived' or proof.get('evidence_kind')!='raw_http_response_bytes':
        return fail('latest_official_price_raw_evidence_missing')
    try:
        from market_evidence_policy import acquisition_phase
        acquired=datetime.fromisoformat(proof['retrieved_at'])
        if acquired.tzinfo is None or acquisition_phase(expected,acquired)!='post_cutoff':return fail('official_price_observation_is_provisional')
        if str(ticker).endswith('.TWO'):
            from data_fetch.market_sources.tpex_session_observation import parse_observation, source_url
            from data_fetch.market_sources.twse_session_observation import DATED_URL as TWSE_URL
            if str(proof.get('source_url') or '').startswith(TWSE_URL):
                return fail('official_price_market_source_mismatch')
            if proof.get('source_url')!=source_url(ticker,expected) or proof.get('http_status')!=200:
                return fail('official_price_endpoint_mismatch')
            from official_response_evidence import read_response
            row=parse_observation(json.loads(read_response(proof)),ticker,expected)
            if any(row.get(k)!=official.get(k) for k in ('volume_unit','volume_scope')):
                return fail('official_price_excerpt_mismatch')
        else:
            from data_fetch.market_sources.twse_session_observation import parse_session,DATED_URL
            url=DATED_URL+'?date='+expected.replace('-','')+'&type=ALL&response=json'
            if proof['source_url']!=url or proof.get('http_status')!=200:return fail('official_price_endpoint_mismatch')
            from official_response_evidence import read_response
            row=parse_session(json.loads(read_response(proof)),expected).get(ticker.split('.')[0])
        if not row or any(row[k]!=official.get(k) for k in ('open','high','low','close','volume')):
            return fail('official_price_excerpt_mismatch')
    except (OSError,ValueError,KeyError,TypeError,AttributeError,EOFError):return fail('official_price_raw_evidence_invalid')
    return {**result,'eligible':True,'reason':'latest_official_price_matches_archived_response','raw_evidence':proof}


def report_source_admission(data, setup):
    daily=data.get('daily_market_data') or {};expected=daily.get('as_of')
    institutional=institutional_admission(data.get('institutional_trading'),expected)
    price=price_admission(daily,str(data.get('ticker') or ''))
    from reporting.trade_price_grid import grid_assessment, proposed_order_contract
    grid=grid_assessment(data,setup)
    blockers=[]
    applicable=str(data.get('ticker') or '').endswith(('.TW','.TWO'))
    order_gate=applicable and setup.get('trade_direction') in {'Long','Short'}
    source_eligible=institutional['eligible'] and price['eligible'] if applicable else None
    warnings=[item['reason'] for item in (institutional,price) if applicable and not item['eligible']]
    if order_gate:
        if not institutional['eligible']:blockers.append(institutional['reason'])
        if not price['eligible']:blockers.append(price['reason'])
        if grid['status']!='grid_aligned_analysis_levels':blockers.append('executable_price_grid_not_verified')
    return {'eligible':bool(source_eligible and not blockers) if applicable else not blockers,
            'source_eligible':source_eligible,'source_warnings':warnings,'order_gate_applicable':order_gate,
            'status':'not_applicable' if not applicable else 'verified_sources' if source_eligible else 'sources_unverified',
            'blockers':blockers,'institutional':institutional,'price':price,'price_grid':grid,
            'order_review_proposal':proposed_order_contract(data,setup),'actionable':False}


REASON_LABELS={
 'support_level_source_value_mismatch':'支撐數值與原引用來源不符',
 'resistance_level_source_value_mismatch':'壓力數值與原引用來源不符',
 'latest_institutional_session_missing':'法人觀測日未達行情交易日',
 'latest_official_raw_evidence_missing':'缺最新官方法人原始回應憑據',
 'official_observation_is_provisional':'法人原始回應在保守重查前取得，尚不可採用',
 'primary_official_latest_categories_mismatch':'法人分類數值與官方原文不符',
 'official_raw_evidence_invalid':'法人原始憑據缺漏或雜湊不符',
 'latest_official_price_raw_evidence_missing':'缺最新官方行情原始回應憑據',
 'official_price_observation_is_provisional':'行情原始回應在保守重查前取得，尚不可採用',
 'official_price_raw_evidence_invalid':'行情原始憑據缺漏或雜湊不符',
 'executable_price_grid_not_verified':'交易價位不合格點或商品類型未確認',
 'latest_categories_match_archived_official_response':'最新法人分類與已保存官方原文相符；不保證後續不修正',
}

def admission_reason_label(reason):
    if reason.startswith(('support_level_source_', 'resistance_level_source_')):
        level = '支撐' if reason.startswith('support') else '壓力'
        descriptions = {'date_mismatch':'日期與原引用來源不符', 'period_mismatch':'期間與原引用來源不符',
                        'scope_mismatch':'價格基準與原引用來源不符', 'input_refs_mismatch':'推導輸入與引用清單不符',
                        'value_mismatch':'數值與原引用來源或可重算公式不符'}
        suffix = reason.split('_source_',1)[1]
        return level + descriptions.get(suffix, '引用型別或推導尚未完整核驗')
    return REASON_LABELS.get(reason,'來源與原始憑據尚未完整核對')
