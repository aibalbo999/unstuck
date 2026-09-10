"""Minimal provider plan for typed watchlist triggers, retaining source audits."""
from __future__ import annotations

import math

from source_audit import audited_fetch_async


def _market_fields(snapshot, *, calendar=False):
    stock = snapshot.get('stock')
    info = snapshot.get('info') or {}
    if stock is None or snapshot.get('is_valid') is False:
        raise RuntimeError('雷達市場快照不可用')
    if calendar:
        from .yfinance_enrichment_extractors import extract_event_calendar
        events = extract_event_calendar(stock, info)
        if not events:
            raise RuntimeError('雷達日曆未取得可驗證事件')
        return {'event_calendar': events}
    history = stock.history(period='2y')
    if history is None or history.empty:
        raise RuntimeError('雷達日價資料不可用')
    rows = []
    for index, row in history.iterrows():
        close = float(row['Close'])
        volume = float(row['Volume'])
        if math.isfinite(close) and math.isfinite(volume):
            rows.append({'date': str(index.date()), 'close': close, 'volume': volume})
    if not rows:
        raise RuntimeError('雷達日價資料不可用')
    return {'daily_prices': rows, 'current_price': rows[-1]['close']}


async def fetch_radar_payload(request, sources, registry):
    data = {'ticker': request.ticker, 'source_audit': []}
    snapshot = None
    for source in sources:
        provider_source = 'market_data' if source == 'event_calendar' else source
        if provider_source == 'market_data' and snapshot is not None:
            value = snapshot
        else:
            provider = registry.first_provider(request, provider_source)
            if provider is None:
                raise RuntimeError(f'雷達缺少資料來源：{source}')
            result = await provider.fetch_async(request, {'original_ticker': request.ticker})
            data['source_audit'].append(result.audit)
            if result.status != 'success' or not result.value:
                raise RuntimeError(f'雷達資料來源暫時不可用：{source}')
            value = result.value
        if provider_source == 'market_data':
            snapshot = value
            result = await audited_fetch_async(
                source, 'yfinance radar', _market_fields, (value,),
                kwargs={'calendar': source == 'event_calendar'}, default={},
            )
            data['source_audit'].append(result['audit'])
            if not result['value']:
                raise RuntimeError(f'雷達市場資料暫時不可用：{source}')
            data.update(result['value'])
        else:
            field = 'recent_monthly_revenue' if source == 'monthly_revenue' else source
            data[field] = value
    return data
