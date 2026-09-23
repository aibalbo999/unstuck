"""SEC EDGAR data provider for US stocks."""

from __future__ import annotations

import time
from typing import Any

from search_provider_runtime import SourceResponseError, error_details
from external_http_client import sync_get
from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult

SEC_HEADERS = {
    "User-Agent": "StockAgent/1.0 (contact@stockagent.local)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}
DATA_SEC_HEADERS = {
    "User-Agent": "StockAgent/1.0 (contact@stockagent.local)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

class SecEdgarProvider(DataProvider):
    name = "SEC EDGAR Filings"
    source = "sec_edgar"
    markets = {"us"}
    cost_tier = "free"
    capabilities = {"sec_filings", "official_filings"}

    def __init__(self):
        self._ticker_to_cik = None
        self._mapping_fetched_at = 0.0

    def _load_tickers(self) -> dict[str, str]:
        if self._ticker_to_cik is not None and time.time() - self._mapping_fetched_at < 86400:
            return self._ticker_to_cik
        
        try:
            r = sync_get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=SEC_HEADERS,
                timeout=10,
                provider="SEC EDGAR",
            )
            try:
                data = r.json()
            except ValueError as exc:
                raise SourceResponseError("mapping_parse_error", status_code=getattr(r, "status_code", None)) from exc
            # Format: { "0": { "cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc." }, ... }
            if not isinstance(data, dict) or not data:
                raise SourceResponseError("mapping_parse_error", status_code=getattr(r, "status_code", None))
            mapping = {}
            for item in data.values():
                if not isinstance(item, dict):
                    raise SourceResponseError("mapping_parse_error", status_code=getattr(r, "status_code", None))
                ticker, cik = item.get("ticker"), str(item.get("cik_str") or "")
                if not isinstance(ticker, str) or not ticker.strip() or not cik.isascii() or not cik.isdigit() or not 0 < int(cik) < 10 ** 10:
                    raise SourceResponseError("mapping_parse_error", status_code=getattr(r, "status_code", None))
                mapping[ticker.strip().upper()] = cik.zfill(10)
            self._ticker_to_cik = mapping
            self._mapping_fetched_at = time.time()
            return mapping
        except SourceResponseError:
            raise
        except Exception as exc:
            details = error_details(exc)
            raise SourceResponseError("mapping_" + details["error_kind"], status_code=details["http_status"]) from exc

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        ticker = str(request.ticker).upper().replace(".US", "")
        try:
            mapping = self._load_tickers()
        except SourceResponseError as exc:
            return ProviderResult(
                source=self.source, provider=self.name, status=AUDIT_STATUS_UNAVAILABLE, value=None,
                audit={"source": self.source, "provider": self.name, "status": AUDIT_STATUS_UNAVAILABLE,
                       "record_count": 0, "mapping_verified": False, **exc.diagnostic,
                       "message": "SEC ticker mapping unavailable; filing coverage remains unknown. " + str(exc)},
            )
        cik = mapping.get(ticker)
        
        if not cik:
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_DEGRADED_ENRICHMENT,
                value=None,
                audit={"source": self.source, "provider": self.name, "message": f"Verified SEC EDGAR ticker mapping has no CIK for {ticker}; filing coverage is unknown.", "status": AUDIT_STATUS_DEGRADED_ENRICHMENT, "record_count": 0, "mapping_verified": True, "error_kind": "cik_not_found"}
            )
            
        try:
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            r = sync_get(url, headers=DATA_SEC_HEADERS, timeout=10, provider="SEC EDGAR")
            data = r.json()
            
            recent_filings = data.get("filings", {}).get("recent", {})
            if not recent_filings:
                return ProviderResult(
                    source=self.source,
                    provider=self.name,
                    status=AUDIT_STATUS_DEGRADED_ENRICHMENT,
                    value=None,
                    audit={"source": self.source, "provider": self.name, "message": "SEC EDGAR 本次無近期 filings，已視為可接受空結果。", "status": AUDIT_STATUS_DEGRADED_ENRICHMENT, "record_count": 0},
                )
                
            # Extract the 10 most recent filings
            filings_list = []
            for i in range(min(10, len(recent_filings.get("accessionNumber", [])))):
                filings_list.append({
                    "form": recent_filings.get("form", [])[i],
                    "filingDate": recent_filings.get("filingDate", [])[i],
                    "reportDate": recent_filings.get("reportDate", [])[i] if i < len(recent_filings.get("reportDate", [])) else "",
                    "primaryDocument": recent_filings.get("primaryDocument", [])[i] if i < len(recent_filings.get("primaryDocument", [])) else ""
                })
                
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_SUCCESS,
                value={"cik": cik, "company_name": data.get("name"), "recent_filings": filings_list},
                audit={"source": self.source, "provider": self.name, "message": "SEC EDGAR filings fetched successfully.", "status": AUDIT_STATUS_SUCCESS, "record_count": len(filings_list)}
            )
        except Exception as e:
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_UNAVAILABLE,
                value=None,
                audit={"source": self.source, "provider": self.name, "message": f"Failed to fetch SEC filings: {e}", "status": AUDIT_STATUS_UNAVAILABLE, "record_count": 0}
            )
