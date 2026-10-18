"""Exchange-specific volume recovery without changing saved analysis series."""
from functools import wraps


def with_exchange_volume(extract):
    @wraps(extract)
    def enriched(stock, *args, **kwargs):
        result = extract(stock, *args, **kwargs)
        ticker = str(getattr(stock, 'ticker', '') or '').upper()
        daily = result.get('daily_market_data')
        if not ticker.endswith('.TWO') or not isinstance(daily, dict):
            return result
        official = daily.get('official_observation') or {}
        bars = daily.get('bars') or []
        if official.get('status') == 'observed' or not bars:
            return result
        from data_fetch.market_sources.tpex_session_observation import official_observation
        daily['official_observation'] = official_observation(ticker, bars[-1]['date'])
        from market_price_reconciliation import reconcile
        daily['price_reconciliation'] = reconcile(daily)
        return result
    return enriched


def evaluate_volume_units(data, pipeline):
    result = {'blocking_issues': [], 'warnings': [], 'checks': []}
    if pipeline != 'v4':
        return result
    daily = data.get('daily_market_data')
    daily = daily if isinstance(daily, dict) else {}
    from market_price_reconciliation import reconcile
    if reconcile(daily)['volume']['status'] == 'unit_mismatch':
        result['warnings'].append({'id': 'v4_volume_scope_mismatch',
            'message': 'Yahoo與官方成交量單位不同或未核實，不直接相減，禁止跨來源量比／法人占比混算。'})
    return result
