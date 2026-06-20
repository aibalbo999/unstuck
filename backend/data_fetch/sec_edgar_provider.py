"""SEC EDGAR data provider for US stocks."""

from __future__ import annotations

import requests
from typing import Any
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

    def __init__(self):
        self._ticker_to_cik = None

    def _load_tickers(self) -> dict[str, str]:
        if self._ticker_to_cik is not None:
            return self._ticker_to_cik
        
        try:
            r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            # Format: { "0": { "cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc." }, ... }
            mapping = {}
            for item in data.values():
                mapping[item["ticker"].upper()] = str(item["cik_str"]).zfill(10)
            self._ticker_to_cik = mapping
            return mapping
        except Exception:
            return {}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        ticker = str(request.ticker).upper().replace(".US", "")
        mapping = self._load_tickers()
        cik = mapping.get(ticker)
        
        if not cik:
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_UNAVAILABLE,
                value=None,
                audit={"source": self.source, "provider": self.name, "message": f"Cannot find CIK for ticker {ticker} in SEC EDGAR mapping.", "status": AUDIT_STATUS_UNAVAILABLE, "record_count": 0}
            )
            
        try:
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            r = requests.get(url, headers=DATA_SEC_HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            recent_filings = data.get("filings", {}).get("recent", {})
            if not recent_filings:
                raise ValueError("No recent filings found.")
                
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
