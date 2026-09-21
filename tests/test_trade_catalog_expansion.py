import pytest
from trade_source_contract import source_catalog, reference_is_evidence, source_block
from datetime import date, timedelta


def data():
    today=date.today()
    return {'ticker':'2033.TW','daily_market_data':{'source':'fixture', 'volume_unit':'shares',
        'bars':[{'date':(today-timedelta(days=40-i)).isoformat(),'open':20+i/10,'high':21+i/10,'low':19+i/10,'close':20+i/10,'volume':1000+i} for i in range(40)]},
        'recent_catalysts':[{'date':today.isoformat(),'title':'2033 佳大公告營收','source':'company','link':'https://example.org/news'}]}


def test_technical_conditions_have_catalyst_refs_but_are_not_price_levels():
    catalog=source_catalog(data())
    for key in ['rsi_14','macd','macd_histogram','volume_ratio_20','volume_latest']:
        ref='short_term_market_context.technical_indicators.'+key
        assert reference_is_evidence(catalog,ref,'catalyst_source_refs'),key
        assert not reference_is_evidence(catalog,ref,'support_source_refs'),key
        assert not reference_is_evidence(catalog,ref,'resistance_source_refs'),key


def test_signed_and_zero_macd_remain_valid_evidence():
    catalog=source_catalog(data())
    catalog['short_term_market_context']['technical_indicators']['macd']=-1
    assert reference_is_evidence(catalog,'short_term_market_context.technical_indicators.macd','catalyst_source_refs')
    catalog['short_term_market_context']['technical_indicators']['macd']=0
    assert reference_is_evidence(catalog,'short_term_market_context.technical_indicators.macd','catalyst_source_refs')


def test_absolute_volume_requires_known_unit_but_same_source_ratio_does_not():
    value=data();value['daily_market_data'].pop('volume_unit')
    catalog=source_catalog(value)
    assert not reference_is_evidence(catalog,'short_term_market_context.technical_indicators.volume_latest','catalyst_source_refs')
    assert reference_is_evidence(catalog,'short_term_market_context.technical_indicators.volume_ratio_20','catalyst_source_refs')


def test_only_recent_issuer_linked_news_is_catalogued_as_historical_news():
    value=data();today=date.today()
    value['recent_catalysts'] += [
        {'date':today.isoformat(),'title':'9999 other issuer','source':'news','link':'https://example.org/other'},
        {'date':(today-timedelta(days=30)).isoformat(),'title':'2033 older','source':'news','link':'https://example.org/old'},
        {'date':None,'title':'2033 no date','source':'news','link':'https://example.org/undated'},
        {'date':today.isoformat(),'title':'2033 no link','source':'news'},
    ]
    catalog=source_catalog(value);news=catalog['short_term_market_context']['recent_news']['items']
    assert len(news)==1
    assert news[0]['published_at']==today.isoformat()
    assert news[0]['evidence_role']=='reported_news_not_scheduled_event'
    ref='short_term_market_context.recent_news.items[0]'
    assert reference_is_evidence(catalog,ref,'catalyst_source_refs')
    assert not reference_is_evidence(catalog,ref,'support_source_refs')
    assert ref in source_block(value)[0]


def test_chip_percent_evidence_is_typed_and_does_not_prove_a_trend():
    from trade_source_contract import bind_trade_payload
    from test_trade_source_completion import setup_payload
    value=data();value['chip_data']={'tdcc_shareholder_distribution':{
        'status':'success','source':'TDCC','as_of_date':date.today().strftime('%Y%m%d'),
        'major_holders_gt_1000_lots_pct':66.76,'retail_holders_lt_50_lots_pct':11.12}}
    block,catalog,fingerprint=source_block(value)
    ref='short_term_market_context.ownership_evidence.records[0]'
    assert reference_is_evidence(catalog,ref,'catalyst_source_refs')
    assert not reference_is_evidence(catalog,ref,'support_source_refs')
    ctx={'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':catalog}}
    payload=setup_payload();payload.update(core_catalyst='大戶持股比例66.76%，等待價格突破。',catalyst_source_refs=[ref])
    assert bind_trade_payload(payload,ctx)[1]['status']=='source_bound'
    for text in ['大戶持股比例增加至66.76%','散戶持股比例66.76%','大戶持股比例99%']:
        payload['core_catalyst']=text
        assert bind_trade_payload(payload,ctx)[1]['status']=='degraded',text


def test_institutional_catalyst_requires_same_population_period_and_units():
    from trade_source_contract import bind_trade_payload
    from test_trade_source_completion import setup_payload
    value=data();value['institutional_trading']={
        'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell','latest_date':date.today().isoformat(),
        'lookback_trading_days':30,'last_5_trading_days_net_buy_thousand_shares':1576.69}
    _,catalog,_=source_block(value)
    ref='short_term_market_context.institutional_evidence.records[0]'
    assert reference_is_evidence(catalog,ref,'catalyst_source_refs')
    ctx={'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':catalog}}
    payload=setup_payload();payload.update(core_catalyst='法人近5日買超1576.69張，等待價格突破。',catalyst_source_refs=[ref])
    assert bind_trade_payload(payload,ctx)[1]['status']=='source_bound'
    for text in ['外資近5日買超1576.69張','法人近5日買超1576.69千張','法人近3日買超1576.69張','外資買超','法人持續買超']:
        payload['core_catalyst']=text
        assert bind_trade_payload(payload,ctx)[1]['status']=='degraded',text

def ownership_context():
    value=data();value['chip_data']={'tdcc_shareholder_distribution':{'status':'success','source':'TDCC',
       'as_of_date':date.today().isoformat(),'major_holders_gt_1000_lots_pct':66.76}}
    _,cat,_=__import__("trade_source_contract").source_block(value)
    return {'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':cat}}


@pytest.mark.parametrize('text', ['10張以上大戶持股比例66.76%。','超過10張的大戶持股比例66.76%。','大戶持股比例66.76%（資料日期2025-01-01）。','2025年1月1日大戶持股比例66.76%。'])
def test_ownership_value_match_cannot_override_threshold_or_date(text):
    payload=__import__("test_trade_source_completion").setup_payload();payload.update(core_catalyst=text,catalyst_source_refs=['short_term_market_context.ownership_evidence.records[0]'])
    assert __import__("trade_source_contract").bind_trade_payload(payload,ownership_context())[1]['status']=='degraded'


def test_numeric_total_cannot_license_uncited_foreign_qualitative_claim():
    value=data();value['institutional_trading']={'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date':date.today().isoformat(),'lookback_trading_days':30,'last_5_trading_days_net_buy_thousand_shares':1576.69}
    _,catalog,_=__import__("trade_source_contract").source_block(value)
    ctx={'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':catalog}}
    payload=__import__("test_trade_source_completion").setup_payload();payload.update(core_catalyst='法人近5日買超1576.69張，外資大幅買超。',catalyst_source_refs=['short_term_market_context.institutional_evidence.records[0]'])
    assert __import__("trade_source_contract").bind_trade_payload(payload,ctx)[1]['status']=='degraded'



def test_failed_event_source_cannot_license_event_reference():
    from trade_source_contract import source_catalog, reference_is_evidence
    cat=source_catalog(data());cat['short_term_market_context']['event_calendar']={
       'availability':'partial','reason_codes':['event_source_failed'],
       'events':[{'date':date.today().isoformat(),'source':'failed-feed','label':'unconfirmed earnings'}]}
    assert not reference_is_evidence(cat,'short_term_market_context.event_calendar.events[0]','catalyst_source_refs')



def test_past_news_reference_cannot_become_future_scheduled_event():
    from datetime import timedelta
    value=data();_,catalog,_=__import__("trade_source_contract").source_block(value)
    ctx={'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':catalog}}
    payload=__import__("test_trade_source_completion").setup_payload();payload.update(core_catalyst=f'2033將於{(date.today()+timedelta(days=1)).isoformat()}舉行法說會。',
        catalyst_source_refs=['short_term_market_context.recent_news.items[0]'])
    assert __import__("trade_source_contract").bind_trade_payload(payload,ctx)[1]['status']=='degraded'


def test_ownership_group_threshold_must_match_the_same_cited_record():
    value=data();value['chip_data']={'tdcc_shareholder_distribution':{'status':'success','source':'TDCC',
       'as_of_date':date.today().isoformat(),'major_holders_gt_1000_lots_pct':66.76,'retail_holders_lt_50_lots_pct':11.12}}
    _,cat,_=__import__("trade_source_contract").source_block(value)
    ctx={'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':cat}}
    payload=__import__("test_trade_source_completion").setup_payload();payload.update(core_catalyst='不足50張大戶持股比例66.76%。',
        catalyst_source_refs=['short_term_market_context.ownership_evidence.records[0]','short_term_market_context.ownership_evidence.records[1]'])
    assert __import__("trade_source_contract").bind_trade_payload(payload,ctx)[1]['status']=='degraded'


def test_conjoined_qualitative_foreign_claim_does_not_borrow_numeric_total():
    value=data();value['institutional_trading']={'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date':date.today().isoformat(),'lookback_trading_days':30,'last_5_trading_days_net_buy_thousand_shares':1576.69}
    _,catalog,_=__import__("trade_source_contract").source_block(value);ctx={'_trade_source_manifest':{'version':'trade-sources:v2','visible':True,'catalog':catalog}}
    payload=__import__("test_trade_source_completion").setup_payload();payload.update(core_catalyst='法人近5日買超1576.69張且外資大幅買超。',catalyst_source_refs=['short_term_market_context.institutional_evidence.records[0]'])
    assert __import__("trade_source_contract").bind_trade_payload(payload,ctx)[1]['status']=='degraded'
