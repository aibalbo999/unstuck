"""First-party company statements with exact, dated exchange identity anchors."""
import time

from .provider_base import DataProvider
from .types import ProviderResult


class IssuerNewsProvider(DataProvider):
    name = "Verified issuer news"
    source = "recent_catalysts"
    markets = {"tw"}
    cost_tier, capabilities = "free", {"news", "issuer_statements", "recent_catalysts"}
    primary_source_provider = False
    freshness_seconds = 1800

    def supports(self, request):
        if str(request.ticker or '').upper() in {'5880', '5880.TW'}:
            return True
        if str(request.ticker or '').upper() in {'2201', '2201.TW', '2464', '2886', '2464.TW', '2886.TW'}:
            return True
        return str(request.ticker or "").upper() in {"1101", "2206", "2353", "2360", "2379", "2412", "3023", "3042", "3443", "6672", "6669", "8150", "2884", "1101.TW", "2206.TW", "2353.TW", "2360.TW", "2379.TW", "2412.TW", "3023.TW", "3042.TW", "3443.TW", "6672.TW", "6669.TW", "8069.TWO", "8150.TW", "2884.TW"}

    def fetch(self, request, context=None):
        from .market_sources.issuer_news import fetch_recent_issuer_news
        requested_ticker = str(request.ticker).upper()
        if (requested_ticker in {'2206', '2206.TW'} and context is not None
                and (not isinstance(context, dict)
                     or 'data' in context and not isinstance(context['data'], dict))):
            return ProviderResult(self.source, self.name, 'unavailable', value=[], audit={
                'source': self.source, 'provider': self.name, 'status': 'unavailable',
                'event_kind': 'local_block', 'error_kind': 'context_unverified',
                'http_request_sent': False, 'http_request_count': 0, 'record_count': 0,
                'message': '三陽新聞的原股票資料格式無效，未抓取。'})
        if (str(request.ticker).upper() in {'5880', '5880.TW'} and context is not None
                and 'data' in context and not isinstance(context['data'], dict)):
            return ProviderResult(self.source, self.name, 'unavailable', value=[], audit={
                'source': self.source, 'provider': self.name, 'status': 'unavailable',
                'event_kind': 'local_block', 'error_kind': 'context_unverified',
                'http_request_sent': False, 'http_request_count': 0, 'record_count': 0,
                'message': '合庫金控母公司新聞的原股票資料格式無效，未抓取。'})
        data = (context or {}).get("data") or {}
        ticker = str(data.get("ticker") or request.ticker).upper()
        if ticker in {'2201', '2464', '2886'} and not data:
            ticker += '.TW'
        started = time.monotonic()
        requested_ticker = str(request.ticker).upper()
        if requested_ticker in {'2206', '2206.TW'} or ticker in {'2206', '2206.TW'}:
            from .market_sources.sym_issuer_news import validate_context
            if (ticker not in {'2206', '2206.TW'} or requested_ticker not in {'2206', '2206.TW'}
                    or data and not validate_context(data, '2206.TW')):
                return ProviderResult(self.source, self.name, 'unavailable', value=[], audit={
                    'source': self.source, 'provider': self.name, 'status': 'unavailable',
                    'event_kind': 'local_block', 'error_kind': 'context_unverified',
                    'http_request_sent': False, 'http_request_count': 0, 'record_count': 0,
                    'message': '三陽新聞與股票身分不一致，未抓取。'})
            ticker = '2206.TW'
        if requested_ticker in {'5880', '5880.TW'} or ticker in {'5880', '5880.TW'}:
            from .market_sources.tcfhc_issuer_news import validate_context
            if (ticker not in {'5880', '5880.TW'} or requested_ticker not in {'5880', '5880.TW'}
                    or data and not validate_context(data, '5880.TW')):
                return ProviderResult(self.source, self.name, 'unavailable', value=[], audit={
                    'source': self.source, 'provider': self.name, 'status': 'unavailable',
                    'event_kind': 'local_block', 'error_kind': 'context_unverified',
                    'http_request_sent': False, 'http_request_count': 0, 'record_count': 0,
                    'message': '合庫金控母公司新聞與股票身分不一致，未抓取。'})
            ticker = '5880.TW'
        if requested_ticker in {'2201', '2201.TW', '2464', '2886', '2464.TW', '2886.TW'} or ticker in {'2201', '2201.TW', '2464', '2886', '2464.TW', '2886.TW'}:
            from .market_sources.registered_issuer_articles import validate_context
            if (ticker not in {'2201.TW', '2464.TW', '2886.TW'}
                    or requested_ticker not in {ticker, ticker.split('.')[0]}
                    or data and not validate_context(data, ticker)):
                return ProviderResult(self.source, self.name, 'error', value=[], audit={
                    'source':self.source, 'provider':self.name, 'status':'error', 'error_kind':'context_unverified',
                    'http_request_sent':False, 'http_request_count':0, 'record_count':0,
                    'message':'發行人原文的股票身分未通過核對。'})
        if ticker == '2206.TW':
            from .market_sources.sanyang_news_bundle import fetch_recent_sanyang_news
            records, audit = fetch_recent_sanyang_news()
        else:
            records, audit = fetch_recent_issuer_news(ticker)
        duration = max(0, int((time.monotonic() - started) * 1000))
        audit.update(source=self.source, provider=self.name, duration_ms=duration,
                     message="發行人原文；公司自行陳述、事件影響未評估，未證明全部窗口覆蓋。")
        if ticker == "6672.TW":
            audit['message'] = '發行人官網轉載DigiTimes；原文發布日未核對，不新增獨立publisher，未證明全部窗口覆蓋。'
        return ProviderResult(self.source, self.name, audit["status"], value=records,
                              audit=audit, duration_ms=duration)
