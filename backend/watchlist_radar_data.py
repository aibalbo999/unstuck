"""Bounded, source-aware watchlist polling; never treats a fetch failure as evidence."""
from __future__ import annotations

import asyncio
import copy
import time

from data_fetch import FetchRequest
from runtime_logging import log_runtime_message, runtime_log_scope

SOURCE_TTL = {'market_data': 300, 'macro_indicators': 300,
              'institutional_trading': 900, 'monthly_revenue': 3600,
              'event_calendar': 3600, 'full': 900}
TRIGGER_SOURCES = {
    'daily_screener': (),
    'price_below_sma': ('market_data',),
    'price_near_level': ('market_data',),
    'foreign_sell_streak': ('institutional_trading',),
    'vix_above': ('macro_indicators',),
    'revenue_record_high': ('market_data', 'monthly_revenue'),
    'event_upcoming': ('event_calendar',),
}


def trigger_sources(triggers: list) -> tuple[str, ...]:
    sources = set()
    for trigger in triggers:
        if not isinstance(trigger, dict) or trigger.get('enabled') is False:
            continue
        sources.update(TRIGGER_SOURCES.get(str(trigger.get('type') or '').strip(), ('full',)))
    return tuple(sorted(sources))


class RadarDataCache:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.entries = {}
        self.inflight = {}

    async def fetch(self, service, ticker: str, sources: tuple[str, ...], evaluation_date: str) -> dict:
        if not sources:
            return {'ticker': ticker}
        key = (ticker, sources, evaluation_date)
        entry = self.entries.get(key)
        if entry and self.clock() < entry[0]:
            if entry[2]:
                raise RuntimeError(entry[2])
            return copy.deepcopy(entry[1])
        task = self.inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._load(service, ticker, sources, key))
            self.inflight[key] = task
        # A cancelled waiter must not cancel another caller's shared fetch.
        return copy.deepcopy(await asyncio.shield(task))

    async def _load(self, service, ticker, sources, key):
        try:
            with runtime_log_scope(f'背景雷達 {ticker}'):
                log_runtime_message('更新觸發條件資料：' + ', '.join(sources))
                request = FetchRequest.from_ticker(ticker, force_refresh='full' in sources)
                selective = getattr(service, 'fetch_radar_async', None)
                result = await selective(request, sources) if selective else await service.fetch_async(request)
                data = getattr(result, 'data', None)
                if not isinstance(data, dict) or not data or data.get('error') or (data.get('_cache_hit') and (data.get('data_freshness') or {}).get('stale_sources')):
                    raise RuntimeError('背景雷達未取得有效新資料；本輪不判定條件')
                ttl = min(SOURCE_TTL[source] for source in sources)
                self.entries[key] = (self.clock() + ttl, copy.deepcopy(data), '')
                # Bound memory by removing expired data and obsolete trading days.
                for old_key, entry in list(self.entries.items()):
                    if old_key != key and (old_key[2] != key[2] or entry[0] <= self.clock()):
                        self.entries.pop(old_key, None)
                if len(self.entries) > 256:
                    self.entries.pop(next(iter(self.entries)))
                log_runtime_message(f'觸發條件資料更新完成；{ttl // 60} 分鐘內共用快取')
                return data
        except Exception:
            # Failed data is never evaluated as a false condition or reused as success.
            self.entries[key] = (self.clock() + 60, None, '背景雷達資料暫時無法更新；稍後重試')
            raise
        finally:
            self.inflight.pop(key, None)


async def fetch_radar_data(service, ticker, triggers, evaluation_date):
    sources = trigger_sources(triggers)
    if not sources:
        return {'ticker': ticker}
    cache = getattr(service, '_watchlist_radar_cache', None)
    if cache is None:
        cache = RadarDataCache()
        service._watchlist_radar_cache = cache
    return await cache.fetch(service, ticker, sources, evaluation_date)
