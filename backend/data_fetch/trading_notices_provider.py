"""Optional official risk notices when the original catalyst evidence is insufficient."""
import re,time
from .provider_base import DataProvider
from .types import ProviderResult
from .market_sources.twse_trading_notices import PROVIDER
from .market_sources.twse_market_trading_notices import fetch_market_trading_notices as fetch_trading_notices


class TradingNoticesProvider(DataProvider):
    name=PROVIDER
    source='recent_catalysts'
    markets={'tw'}
    cost_tier,capabilities='free',{'official_announcements','recent_catalysts'}
    primary_source_provider=False
    freshness_seconds=1800

    def supports(self,request):
        return bool(re.fullmatch(r'[1-9]\d{3}(?:\.TW)?',str(request.ticker or '').upper()))

    def fetch(self,request,context=None):
        raw=(context or {}).get('data') if isinstance(context,dict) else None
        data=raw if isinstance(raw,dict) else {}
        requested=str(request.ticker or '').strip().upper()
        ticker=str(data.get('ticker') or requested).strip().upper()
        same=(requested==ticker or re.fullmatch(r'[1-9]\d{3}',requested) and ticker==requested+'.TW')
        if not self.supports(request) or not re.fullmatch(r'[1-9]\d{3}\.TW',ticker) or not same:
            return ProviderResult(self.source,self.name,'not_applicable',value=[],audit={
                'source':self.source,'provider':self.name,'status':'not_applicable','record_count':0,
                'event_kind':'local_block','http_request_sent':False,'cache_hit':False,'stale':False,
                'reason_code':'request_context_issuer_or_market_mismatch',
                'message':'skip: 請求股票與正式上市市場身分無法一致核對。'})
        start=time.monotonic();records,audit=fetch_trading_notices(ticker)
        audit.update(duration_ms=max(0,round((time.monotonic()-start)*1000)))
        return ProviderResult(self.source,self.name,audit['status'],value=records,audit=audit,duration_ms=audit['duration_ms'])
