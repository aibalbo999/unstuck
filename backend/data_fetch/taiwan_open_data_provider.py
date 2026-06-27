"""Taiwan Open Data (data.gov.tw / BOT) provider for macro indicators."""

from __future__ import annotations

import requests
import csv
from io import StringIO
from typing import Any
from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult

# 台灣銀行牌告匯率 Open Data CSV
BOT_EXCHANGE_RATE_URL = "https://rate.bot.com.tw/xrt/flcsv/0/day"

class TaiwanOpenDataProvider(DataProvider):
    name = "Taiwan Open Data (Exchange Rates)"
    source = "taiwan_open_data"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        
        try:
            # Fetching from the open data endpoint with a timeout
            r = requests.get(BOT_EXCHANGE_RATE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            r.raise_for_status()
            
            content = r.content.decode('utf-8-sig', errors='replace')
            reader = csv.reader(StringIO(content))
            rows = list(reader)
            
            if len(rows) < 2:
                raise ValueError("CSV data is empty or malformed.")
                
            # Parse Exchange Rates (Currency vs TWD)
            rates = {}
            for row in rows[1:]:
                currency = row[0]
                cash_buy = row[2]
                cash_sell = row[12]
                rates[currency] = {"buy": cash_buy, "sell": cash_sell}
                
            value = {
                "dataset": "Bank of Taiwan Exchange Rates (牌告匯率)",
                "source": "Open Data (rate.bot.com.tw)",
                "rates": {
                    "USD": rates.get("USD"),
                    "EUR": rates.get("EUR"),
                    "JPY": rates.get("JPY"),
                }
            }
            
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_SUCCESS,
                value=value,
                audit={"source": self.source, "provider": self.name, "message": "Successfully fetched exchange rates from Taiwan open data.", "status": AUDIT_STATUS_SUCCESS, "record_count": len(rates)}
            )
            
        except Exception as e:
            # Fallback for dynamic open data URLs that might expire or change
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_UNAVAILABLE,
                value=None,
                audit={"source": self.source, "provider": self.name, "message": f"Failed to fetch from Taiwan open data: {e}.", "status": AUDIT_STATUS_UNAVAILABLE, "record_count": 0}
            )
