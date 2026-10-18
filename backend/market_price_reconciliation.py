"""Pure per-field comparison; no trading approval or acquisition during rendering."""
import math

CONTRACT='market_price_basis.v2'


def number(value):
    if value is None or isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None


def reconcile(daily):
    raw=daily.get('provider_raw_observation') or {};official=daily.get('official_observation') or {}
    bars=daily.get('bars') or [];adjusted=bars[-1] if bars else {}
    same=bool(raw.get('date') and raw.get('date')==official.get('date')==adjusted.get('date') and raw.get('ticker') and raw.get('ticker')==official.get('ticker') and official.get('status')=='observed')
    prices={};volumes={};adjustments={}
    for key in ('open','high','low','close','volume'):
        p,o,a=number(raw.get(key)),number(official.get(key)),number(adjusted.get(key))
        known=same and p is not None and o is not None
        tolerance=0.0 if key=='volume' else max(.0001,abs(o or 0)*1e-7)
        item={'provider_raw':p,'official_raw':o,'delta':p-o if known else None,'tolerance':tolerance,'status':'unverified' if not known else 'match' if abs(p-o)<=tolerance else 'different'}
        if key == 'volume' and known and (raw.get('volume_unit') != official.get('volume_unit')
                or raw.get('volume_unit') not in {'shares', 'lots'}):
            item.update(status='unit_mismatch', delta=None)
        (volumes if key=='volume' else prices)[key]=item
        if key!='volume':adjustments[key]={'provider_raw':p,'provider_adjusted':a,'factor':a/p if p and a is not None else None,'status':'unknown' if not p or a is None else 'same' if abs(p-a)<=max(.0001,abs(p)*1e-7) else 'adjusted'}
    price_status='unverified' if not same or any(x['status']=='unverified' for x in prices.values()) else 'different' if any(x['status']=='different' for x in prices.values()) else 'matched_sample_session'
    volume=volumes['volume']
    scope_match=bool(raw.get('volume_scope_verified') is True and official.get('volume_scope_verified') is True and raw.get('volume_scope') and raw.get('volume_scope')==official.get('volume_scope'))
    value_match=bool(same and volume['status']=='match')
    comparable=value_match and raw.get('volume_unit')==official.get('volume_unit')=='shares' and scope_match
    volume.update(value_match=value_match,scope_verified=scope_match,provider_scope=raw.get('volume_scope') or 'unknown',official_scope=official.get('volume_scope') or 'unknown')
    return {'schema_version':CONTRACT,'session_aligned':same,'price_status':price_status,'prices':prices,'volume':volume,'adjustments':adjustments,'cross_provider_volume_comparable':comparable,'volume_scope_status':'verified_same_scope' if scope_match else 'unverified_transaction_scope','cross_provider_flow_normalization_allowed':comparable,'technical_price_use':'adjusted analysis series;never automatically executable','technical_volume_use':'provider volumes throughout the same stored window;official latest volume not spliced into provider baseline','execution_price_use':'official raw sample observation only;plan basis, tick grid, trigger and fill remain unverified','sample_date':official.get('date') if same else None,'actionable':False,'historical_point_in_time_verified':False,'strategy_results_verified':False}


def observation_rows(daily):
    result=reconcile(daily);official=daily.get('official_observation') or {};raw=daily.get('provider_raw_observation') or {}
    labels={'open':'開','high':'高','low':'低','close':'收'}
    statuses={'match':'一致','different':'不符','unverified':'未核'}
    price='／'.join(f'{labels[k]} {statuses[v["status"]]}' for k,v in result['prices'].items());volume=result['volume']
    volume_text=f'Yahoo {volume["provider_raw"]:,.0f}／官方 {volume["official_raw"]:,.0f} 股；差 {volume["delta"]:+,.0f} 股，口徑未確認，禁止跨來源混算' if volume['status']=='different' else '雙方成交量單位不同或未核實，不直接相減，也不作跨來源占比' if volume['status']=='unit_mismatch' else '同日成交量數值一致；僅此抽樣日' if result['cross_provider_volume_comparable'] else '同日成交量數值一致，但交易時段／類型口徑未核實；不可跨來源混算' if volume['status']=='match' else '未取得可比較的同日成交量'
    url=official.get('source_url') or ''
    base,separator,query=url.partition('?')
    source_text=base+'；查詢參數 '+query.replace('&','、') if separator else url
    return [{'label':'原始OHLC逐項核對','value':f'{result["sample_date"] or "未確認同日"}；{price}；僅抽樣交易日，非全歷史驗價'}, {'label':'成交量來源與基準','value':volume_text+'；官方 '+(official.get('volume_scope_note') or '交易類型口徑未保存')+'；技術量比使用同一Yahoo歷史窗，未拼接官方當日量'}, {'label':'實際取得時間','value':f'Yahoo {raw.get("retrieved_at") or "未記錄"}；官方 {official.get("retrieved_at") or "未取得"}；快取沿用原取得時間，非歷史PIT證明'}, {'label':'官方核對來源','value':source_text or '未取得；讀取既存報告不補抓或改寫證據'}]
