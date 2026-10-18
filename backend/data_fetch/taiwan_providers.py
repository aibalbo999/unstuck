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
    cost_tier = "free"
    capabilities = {"financial_statements"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.taiwan import audited_finmind_financial_statement_fallback

        result = audited_finmind_financial_statement_fallback(request.ticker, audit_fetch=audited_fetch)
        return provider_result_from_audited(result, self.source, "FinMind financial statement fallback")


class TwseOfficialProvider(DataProvider):
    name = "FinMind TWSE official"
    source = "twse_official"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"official_filings", "financial_statements"}

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
    cost_tier = "free"
    capabilities = {"monthly_revenue"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from datetime import datetime, timedelta
        from .market_sources.taiwan import DataLoader

        import re
        from copy import deepcopy
        from provider_correlation import current_correlation
        from source_applicability import source_is_applicable
        from .market_sources.official_monthly_revenue import fetch_official_monthly_revenue, monthly_url

        data = (context or {}).get('data') or {}
        requested = str(request.ticker or '').strip().upper()
        ticker = str(data.get('ticker') or requested).strip().upper()
        if re.fullmatch(r'[0-9]{4,6}', ticker):
            ticker += '.TW'
        same = requested == ticker or re.fullmatch(r'[0-9]{4,6}', requested) and ticker.split('.')[0] == requested
        try:
            monthly_url(ticker)
            if not same or not source_is_applicable(self.source, data, ticker):
                raise ValueError('monthly_context_issuer_mismatch')
        except ValueError:
            return ProviderResult(self.source, self.name, 'not_applicable', value=[], audit={
                'source': self.source, 'provider': self.name, 'status': 'not_applicable',
                'record_count': 0, 'event_kind': 'local_block', 'http_request_sent': False,
                'reason_code': 'request_context_issuer_or_market_mismatch'})

        # The core collector may already have attempted this exact source in
        # this fetch. Reuse only that typed failed observation, not an old job,
        # cache, another ticker or an uncorrelated summary.
        fetch_id = current_correlation().get('fetch_id')
        previous = next((entry for entry in reversed(data.get('source_audit') or [])
                         if isinstance(entry, dict) and fetch_id and entry.get('fetch_id') == fetch_id
                         and entry.get('ticker') in {requested, ticker}
                         and entry.get('cache_hit') is False and entry.get('stale') is False
                         and entry.get('operation_id')
                         and (entry.get('event_kind') == 'aggregate' or (
                             entry.get('event_kind') == 'local_block'
                             and entry.get('provider_admission_blocked') is True
                             and entry.get('http_request_sent') is False
                             and type(entry.get('http_request_count')) is int and entry['http_request_count'] == 0
                             and type(entry.get('provider_attempt_count')) is int and entry['provider_attempt_count'] == 0
                             and entry.get('provider_attempts') == []))
                         and entry.get('source') == self.source and entry.get('provider') == self.name
                         and entry.get('status') in {'error', 'unavailable'}
                         and type(entry.get('record_count')) is int and entry['record_count'] == 0), None)
        from .market_sources.finmind_monthly_revenue import fetch_monthly_records
        result = {'value': [], 'audit': deepcopy(previous)} if previous else fetch_monthly_records(
            request.ticker, DataLoader, audit_fetch=audited_fetch,
            force_refresh=request.options.force_refresh)
        if result.get('value'):
            return provider_result_from_audited(result, self.source, self.name)
        import time
        official_deadline = time.monotonic() + 8
        fallback = fetch_official_monthly_revenue(ticker)
        if fallback.get('value'):
            if ticker == '3324.TWO':
                from .market_sources.auras_monthly_history import fetch_auras_monthly_history
                history = fetch_auras_monthly_history(ticker, fallback, deadline=official_deadline)
            elif ticker == '5314.TWO':
                from .market_sources.myson_monthly_history import fetch_myson_monthly_history
                history = fetch_myson_monthly_history(ticker, fallback, deadline=official_deadline)
            else:
                from .market_sources.twse_monthly_history import fetch_official_monthly_history
                history = fetch_official_monthly_history(ticker, fallback, deadline=official_deadline)
            if history and history.get('value'):
                history['audit']['related_entries'] = [fallback['audit']]
                if not previous:
                    history['audit']['related_entries'].insert(0, result['audit'])
                else:
                    history['audit']['primary_failure_operation_id'] = previous['operation_id']
                return provider_result_from_audited(history, self.source, history['audit']['provider'])
            if history:
                fallback['audit']['history_failure_entry'] = history['audit']
        if fallback.get('value'):
            fallback['audit']['related_entries'] = [] if previous else [result['audit']]
            if fallback['audit'].get('history_failure_entry'):
                fallback['audit']['related_entries'].append(fallback['audit'].pop('history_failure_entry'))
            if previous:
                fallback['audit']['primary_failure_operation_id'] = previous['operation_id']
            return provider_result_from_audited(fallback, self.source, self.name)
        if previous:
            # That primary observation is already in the payload. Emit only
            # this new official failure, not the same FinMind operation twice.
            fallback['audit']['primary_failure_operation_id'] = previous['operation_id']
            fallback['audit']['related_entries'] = []
            return provider_result_from_audited(fallback, self.source, self.name)
        result['audit']['related_entries'] = [fallback['audit']]
        return provider_result_from_audited(result, self.source, self.name)


class InstitutionalTradingProvider(DataProvider):
    name = "FinMind"
    source = "institutional_trading"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"institutional_trading"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .institutional_provider import fetch_institutional_result
        return fetch_institutional_result(request)
