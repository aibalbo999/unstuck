"""Agent-scoped macro, chip, and alternative-data providers."""

from __future__ import annotations

from .provider_base import DataProvider
from .types import FetchRequest, ProviderResult


class MacroIndicatorsProvider(DataProvider):
    name = "FRED macro indicators"
    source = "macro_indicators"
    cost_tier = "free_with_key"
    capabilities = {"macro_indicators"}
    requires_env = ("FRED_API_KEY",)

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
    cost_tier = "free"
    capabilities = {"chip_data", "institutional_context"}

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
    name = "104 & 1111 job openings"
    source = "alternative_data"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"alternative_data", "job_openings"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_NOT_CONFIGURED, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from alternative_data_fetcher import fetch_104_job_openings_count, fetch_1111_job_openings_count

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
                    "message": "alternative_data_keywords 未設定，略過職缺探測。",
                },
            )

        results_104 = [fetch_104_job_openings_count(company_name, keyword) for keyword in keywords[:3]]
        results_1111 = [fetch_1111_job_openings_count(company_name, keyword) for keyword in keywords[:3]]
        
        successful_104 = [item for item in results_104 if isinstance(item, dict) and item.get("status") == "success"]
        successful_1111 = [item for item in results_1111 if isinstance(item, dict) and item.get("status") == "success"]
        
        status = AUDIT_STATUS_SUCCESS if (successful_104 or successful_1111) else AUDIT_STATUS_UNAVAILABLE
        value = {
            "job_openings_104": successful_104[0] if len(successful_104) == 1 else results_104,
            "job_openings_1111": successful_1111[0] if len(successful_1111) == 1 else results_1111,
        }
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=value if status == AUDIT_STATUS_SUCCESS else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": len(successful_104) + len(successful_1111),
                "cache_hit": False,
                "stale": False,
                "message": "職缺探測 (含新聞備援) 已回傳。" if status == AUDIT_STATUS_SUCCESS else "職缺探測未回傳可用結果。",
            },
        )


class SocialSentimentProvider(DataProvider):
    name = "Social Forum Sentiment (Dcard/Mobile01/PTT)"
    source = "social_sentiment"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"social_sentiment"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from news_fetchers import fetch_google_news_rss, fetch_ptt_stock_sentiment

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        company_name = str(data.get("company_name") or request.ticker).strip()
        ticker = _taiwan_stock_id(data.get("ticker") or request.ticker)

        # Dcard
        query_dcard = f"site:dcard.tw {company_name} OR {ticker}"
        dcard_news = fetch_google_news_rss(query_dcard, limit=3)

        # Mobile01
        query_m01 = f"site:mobile01.com {company_name} OR {ticker}"
        m01_news = fetch_google_news_rss(query_m01, limit=3)

        # PTTWeb (alternative to pure PTT)
        query_pttweb = f"site:pttweb.cc {company_name} OR {ticker}"
        pttweb_news = fetch_google_news_rss(query_pttweb, limit=3)
        ptt_direct = []
        if ticker.isdigit():
            for item in fetch_ptt_stock_sentiment(ticker, limit=5):
                if not isinstance(item, dict):
                    continue
                ptt_direct.append({
                    "title": str(item.get("title") or "").strip(),
                    "date": str(item.get("date") or item.get("published_date") or "").strip(),
                    "source": str(item.get("source") or "PTT Stock").strip(),
                })

        value = {
            "dcard": dcard_news,
            "mobile01": m01_news,
            "pttweb": pttweb_news,
            "ptt_stock_direct": ptt_direct,
        }
        
        total_records = len(dcard_news) + len(m01_news) + len(pttweb_news) + len(ptt_direct)
        status = AUDIT_STATUS_SUCCESS if total_records > 0 else AUDIT_STATUS_UNAVAILABLE
        
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=value if status == AUDIT_STATUS_SUCCESS else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": total_records,
                "cache_hit": False,
                "stale": False,
                "message": "社群論壇討論串已回傳。" if status == AUDIT_STATUS_SUCCESS else "近期無相關社群論壇討論。",
            },
        )


def _taiwan_stock_id(value: object) -> str:
    text = str(value or "").strip().upper()
    if text.endswith(".TWO"):
        return text[:-4]
    if text.endswith(".TW"):
        return text[:-3]
    return text
