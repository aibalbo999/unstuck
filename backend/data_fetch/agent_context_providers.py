"""Agent-scoped macro, chip, and alternative-data providers."""

from __future__ import annotations

from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult


class MacroIndicatorsProvider(DataProvider):
    name = "FRED macro indicators"
    source = "macro_indicators"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_NOT_CONFIGURED, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from macro_fetcher import fetch_key_macro_indicators

        payload = fetch_key_macro_indicators()
        status = payload.get("status") if isinstance(payload, dict) else "unavailable"
        if status == "success":
            audit_status = AUDIT_STATUS_SUCCESS
        elif status == "not_configured":
            audit_status = AUDIT_STATUS_NOT_CONFIGURED
        else:
            audit_status = AUDIT_STATUS_UNAVAILABLE
        indicators = payload.get("indicators", {}) if isinstance(payload, dict) else {}
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=audit_status,
            value=payload if isinstance(payload, dict) and status == "success" else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": audit_status,
                "record_count": len(indicators) if isinstance(indicators, dict) else 0,
                "cache_hit": False,
                "stale": False,
                "message": payload.get("message") if isinstance(payload, dict) and payload.get("message") else "FRED macro indicators 已回傳總經指標。",
            },
        )


class ChipDataProvider(DataProvider):
    name = "TDCC/TWSE chip data"
    source = "chip_data"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from chip_data_fetcher import fetch_tdcc_shareholder_distribution, fetch_twse_margin_short_sales

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        tdcc = fetch_tdcc_shareholder_distribution(ticker, data.get("tdcc_date"))
        margin = fetch_twse_margin_short_sales(ticker)
        value = {
            "tdcc_shareholder_distribution": tdcc,
            "twse_margin_short_sales": margin,
        }
        successful = sum(1 for item in value.values() if isinstance(item, dict) and item.get("status") == "success")
        status = AUDIT_STATUS_SUCCESS if successful else AUDIT_STATUS_UNAVAILABLE
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=value if successful else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": successful,
                "cache_hit": False,
                "stale": False,
                "message": "TDCC/TWSE 籌碼資料已回傳。" if successful else "TDCC/TWSE 籌碼資料暫無可用結果。",
            },
        )


class AlternativeJobOpeningsProvider(DataProvider):
    name = "104 job openings"
    source = "alternative_data"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_NOT_CONFIGURED, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from alternative_data_fetcher import fetch_104_job_openings_count

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        company_name = str(data.get("company_name") or request.ticker).strip()
        raw_keywords = data.get("alternative_data_keywords") or data.get("job_opening_keywords") or []
        if isinstance(raw_keywords, str):
            keywords = [raw_keywords]
        else:
            keywords = [str(keyword).strip() for keyword in list(raw_keywords or []) if str(keyword).strip()]
        if not keywords:
            return ProviderResult(
                source=self.source,
                provider=self.name,
                status=AUDIT_STATUS_NOT_CONFIGURED,
                value=None,
                audit={
                    "source": self.source,
                    "provider": self.name,
                    "status": AUDIT_STATUS_NOT_CONFIGURED,
                    "record_count": 0,
                    "cache_hit": False,
                    "stale": False,
                    "message": "alternative_data_keywords 未設定，略過 104 職缺探測。",
                },
            )

        results = [fetch_104_job_openings_count(company_name, keyword) for keyword in keywords[:3]]
        successful = [item for item in results if isinstance(item, dict) and item.get("status") == "success"]
        status = AUDIT_STATUS_SUCCESS if successful else AUDIT_STATUS_UNAVAILABLE
        value = {"job_openings_104": successful[0] if len(successful) == 1 else results}
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=value if successful else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": len(successful),
                "cache_hit": False,
                "stale": False,
                "message": "104 職缺探測已回傳。" if successful else "104 職缺探測未回傳可用結果。",
            },
        )
