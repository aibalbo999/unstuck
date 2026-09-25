"""Company IR adapter; automatic acquisition awaits live text verification."""
from __future__ import annotations

from company_ir_sources import COVERAGE_NOTE, ISSUERS, LIVE_VERIFICATION, PROVIDER, fetch_company_ir_documents
from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult


class CompanyIrProvider(DataProvider):
    name = PROVIDER
    source = 'company_ir'
    markets = {'tw'}
    capabilities = {'official_company_documents'}
    freshness_seconds = 3600
    execute_in_workflow = False

    def capability(self, request: FetchRequest | None = None) -> dict:
        return {**super().capability(request), 'execute_in_workflow': False,
                'supported_tickers': sorted(ISSUERS), 'live_verification': LIVE_VERIFICATION,
                'coverage_notes': [COVERAGE_NOTE]}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        value = fetch_company_ir_documents(request.ticker, force_refresh=request.options.force_refresh)
        status = {'partial': 'degraded_enrichment', 'unsupported': 'not_applicable'}.get(value['status'], 'unavailable')
        audit = {key: item for key, item in value.items() if key not in {'documents', 'index_result'}}
        audit.update(source=self.source, provider=self.name, status=status,
                     record_count=len(value['documents']), event_kind='aggregate', message=COVERAGE_NOTE)
        audit.pop('http_request_sent', None)
        return ProviderResult(source=self.source, provider=self.name, status=status, value=value, audit=audit)
