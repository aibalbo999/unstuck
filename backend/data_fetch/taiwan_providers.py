"""Taiwan-market FinMind providers."""

from __future__ import annotations

from source_audit import audited_fetch

from .market_sources.identity import _stock_id_from_ticker
from .provider_base import DataProvider, provider_result_from_audited
from .types import FetchRequest, ProviderResult


class FinMindProvider(DataProvider):
    name = "FinMind"
    source = "financial_statements"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.taiwan import fetch_finmind_financial_statement_fallback

        result = audited_fetch(
            self.source,
            "FinMind financial statement fallback",
            fetch_finmind_financial_statement_fallback,
            (request.ticker,),
            default={},
            unavailable_message="FinMind 財報備援未回傳可用年度資料。",
        )
        return provider_result_from_audited(result, self.source, "FinMind financial statement fallback")


class TwseOfficialProvider(DataProvider):
    name = "FinMind TWSE official"
    source = "twse_official"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        import external_data_twse

        result = audited_fetch(
            self.source,
            self.name,
            external_data_twse.fetch_twse_official_data,
            (request.ticker,),
            default={},
            unavailable_message="台股官方財務資料（TWSE/MOPS）本次未取得。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class MonthlyRevenueProvider(DataProvider):
    name = "FinMind TaiwanStockMonthRevenue"
    source = "monthly_revenue"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from datetime import datetime, timedelta
        from .market_sources.taiwan import DataLoader

        def fetch_records():
            if DataLoader is None:
                return []
            fm_dl = DataLoader()
            stock_id = _stock_id_from_ticker(request.ticker)
            start_date = (datetime.now() - timedelta(days=240)).strftime("%Y-%m-%d")
            df_rev = fm_dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date)
            records = []
            if df_rev is not None and not df_rev.empty:
                for _, row in df_rev.tail(6).iterrows():
                    year = row.get("revenue_year")
                    month = row.get("revenue_month")
                    value = row.get("revenue")
                    if year and month and value:
                        records.append(f"{year}年{month}月: NT${float(value) / 1e8:.2f}億")
            return records

        result = audited_fetch(
            self.source,
            self.name,
            fetch_records,
            default=[],
            unavailable_message="FinMind 月營收未回傳可用資料。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class InstitutionalTradingProvider(DataProvider):
    name = "FinMind"
    source = "institutional_trading"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.taiwan import fetch_institutional_trading_trend

        result = audited_fetch(
            self.source,
            self.name,
            fetch_institutional_trading_trend,
            (request.ticker,),
            default={},
            unavailable_message="法人籌碼資料暫無可用資料。",
        )
        return provider_result_from_audited(result, self.source, self.name)
