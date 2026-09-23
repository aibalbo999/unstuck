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
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_NOT_CONFIGURED, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from macro_fetcher import fetch_key_macro_indicators

        payload = fetch_key_macro_indicators(use_cache=not request.options.force_refresh)
        status = payload.get("status") if isinstance(payload, dict) else "unavailable"
        if status == "success":
            audit_status = AUDIT_STATUS_SUCCESS
        elif status in {"partial", "stale"}:
            audit_status = AUDIT_STATUS_DEGRADED_ENRICHMENT
        elif status == "not_configured":
            audit_status = AUDIT_STATUS_NOT_CONFIGURED
        else:
            audit_status = AUDIT_STATUS_UNAVAILABLE
        indicators = payload.get("indicators", {}) if isinstance(payload, dict) else {}
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=audit_status,
            value=payload if isinstance(payload, dict) and indicators else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": audit_status,
                "record_count": len(indicators) if isinstance(indicators, dict) else 0,
                "cache_hit": payload.get("cache_hit", False),
                "stale": payload.get("stale", False),
                "coverage_status": status,
                "component_statuses": payload.get("component_statuses", {}),
                "message": payload.get("message") if isinstance(payload, dict) and payload.get("message") else "FRED macro indicators 已回傳總經指標。",
            },
        )


class ChipDataProvider(DataProvider):
    name = "TDCC/TWSE/TPEx chip data"
    source = "chip_data"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"chip_data", "institutional_context"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from chip_data_fetcher import fetch_tdcc_shareholder_distribution, fetch_twse_margin_short_sales

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        tdcc = fetch_tdcc_shareholder_distribution(ticker, data.get("tdcc_date"))
        margin = fetch_twse_margin_short_sales(ticker)
        value = {
            "tdcc_shareholder_distribution": tdcc,
            "twse_margin_short_sales": margin,
        }
        components = {
            "tdcc": {"status": tdcc.get("status", "unknown"), "as_of": tdcc.get("as_of_date"), "provider": tdcc.get("source", "TDCC")},
            "margin_short": {"status": margin.get("status", "unknown"), "as_of": margin.get("as_of_date"), "provider": margin.get("source")},
            "borrowed_short": {"status": margin.get("borrowed_short_status", "unknown"),
                               "as_of": margin.get("borrowed_short_as_of_date"), "provider": margin.get("borrowed_short_source"),
                               "reason_code": margin.get("borrowed_short_reason_code") if margin.get("borrowed_short_status") else "status_not_reported"},
        }
        successful = sum(item["status"] == "success" for item in components.values())
        coverage = "success" if successful == len(components) else "partial" if successful else "unavailable"
        value.update(status=coverage, component_statuses=components)
        status = AUDIT_STATUS_SUCCESS if coverage == "success" else AUDIT_STATUS_DEGRADED_ENRICHMENT if successful else AUDIT_STATUS_UNAVAILABLE
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
                "coverage_status": coverage,
                "component_statuses": components,
                "message": "籌碼分項資料已回傳；請依各來源狀態與日期確認覆蓋。" if successful else "TDCC/TWSE/TPEx 籌碼資料暫無可用結果。",
            },
        )


class AlternativeJobOpeningsProvider(DataProvider):
    name = "104 & 1111 job openings"
    source = "alternative_data"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"alternative_data", "job_openings"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .context_provider_cache import cached_context_result
        return cached_context_result(self, request, context, self._fetch_uncached)

    def _fetch_uncached(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS
        from alternative_data_fetcher import fetch_104_job_openings_count, fetch_1111_job_openings_count

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        company_name = str(data.get("company_name") or request.ticker).strip()
        raw_keywords = data.get("alternative_data_keywords") or data.get("job_opening_keywords") or []
        if isinstance(raw_keywords, str):
            keywords = [raw_keywords]
        else:
            keywords = [str(keyword).strip() for keyword in list(raw_keywords or []) if str(keyword).strip()]
        if not keywords:
            keywords = _default_job_opening_keywords(data)

        results_104 = [fetch_104_job_openings_count(company_name, keyword) for keyword in keywords[:3]]
        results_1111 = [fetch_1111_job_openings_count(company_name, keyword) for keyword in keywords[:3]]
        
        records = [item for item in results_104 + results_1111 if isinstance(item, dict)]
        numeric = [item for item in records if item.get("status") == "success"
                   and isinstance(item.get("job_count"), int) and not isinstance(item.get("job_count"), bool)
                   and item["job_count"] >= 0]
        news_count = sum(len(item.get("recent_recruitment_news") or []) for item in records)
        complete_numeric = len(numeric) == len(results_104) + len(results_1111)
        coverage = ("partial" if numeric and not complete_numeric else
                    "valid_empty" if numeric and all(item["job_count"] == 0 for item in numeric)
                    else "success" if numeric else "qualitative_only" if news_count else "unavailable")
        status = AUDIT_STATUS_SUCCESS if complete_numeric and numeric else AUDIT_STATUS_DEGRADED_ENRICHMENT
        value = {
            "status": coverage,
            "job_openings_104": results_104[0] if len(results_104) == 1 else results_104,
            "job_openings_1111": results_1111[0] if len(results_1111) == 1 else results_1111,
            "numeric_count_coverage": len(numeric), "recruitment_news_count": news_count,
            "coverage_notes": ["徵才新聞僅為質性訊號，不能代替職缺數；失敗不代表零職缺。"],
        }
        return ProviderResult(
            source=self.source, provider=self.name, status=status, value=value,
            audit={"source": self.source, "provider": self.name, "status": status,
                   "record_count": len(numeric), "cache_hit": False, "stale": False,
                   "coverage_status": coverage, "numeric_count_coverage": len(numeric),
                   "recruitment_news_count": news_count,
                   "message": "職缺查詢保留數量與質性備援的差別。"},
        )



class SocialSentimentProvider(DataProvider):
    name = "Social Forum Sentiment (Dcard/Mobile01/PTT)"
    source = "social_sentiment"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"social_sentiment"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .context_provider_cache import cached_context_result
        return cached_context_result(self, request, context, self._fetch_uncached)

    def _fetch_uncached(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS
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
                    "link": str(item.get("link") or item.get("url") or "").strip(),
                })

        value = {
            "dcard": dcard_news,
            "mobile01": m01_news,
            "pttweb": pttweb_news,
            "ptt_stock_direct": ptt_direct,
        }
        
        total_records = len(dcard_news) + len(m01_news) + len(pttweb_news) + len(ptt_direct)
        value.update(status="success" if total_records else "empty_unknown", sample_count=total_records,
                     sentiment_assessment="not_assessed", coverage_notes=["搜尋樣本非完整社群母體；無結果不能推定中性或無討論。"])
        status = AUDIT_STATUS_SUCCESS if total_records > 0 else AUDIT_STATUS_DEGRADED_ENRICHMENT
        
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=value,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": total_records,
                "cache_hit": False,
                "stale": False,
                "coverage_status": value["status"],
                "message": "社群論壇樣本已回傳；尚未構成情緒結論。" if total_records else "社群查詢無樣本；無法由空結果區分未找到與上游未取得。",
            },
        )


def _default_job_opening_keywords(data: dict) -> list[str]:
    signature = f"{data.get('sector') or ''} {data.get('industry') or ''}".lower()
    if any(token in signature for token in ("semiconductor", "hardware", "software", "technology", "電子", "半導體", "科技")):
        return ["工程師"]
    if any(token in signature for token in ("finance", "bank", "insurance", "金融", "銀行", "保險")):
        return ["業務"]
    if any(token in signature for token in ("retail", "consumer", "餐飲", "零售", "消費")):
        return ["門市"]
    return ["營運"]


def _taiwan_stock_id(value: object) -> str:
    text = str(value or "").strip().upper()
    if text.endswith(".TWO"):
        return text[:-4]
    if text.endswith(".TW"):
        return text[:-3]
    return text
