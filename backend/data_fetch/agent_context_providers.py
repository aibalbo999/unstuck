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
        margin = fetch_twse_margin_short_sales(ticker, use_cache=not request.options.force_refresh)
        value = {
            "tdcc_shareholder_distribution": tdcc,
            "twse_margin_short_sales": margin,
        }
        components = {
            "tdcc": {"status": tdcc.get("status", "unknown"), "as_of": tdcc.get("as_of_date"), "provider": tdcc.get("source", "TDCC")},
            "margin_short": {"status": margin.get("status", "unknown"), "as_of": margin.get("as_of_date"), "provider": margin.get("source"),
                             "reason_code": margin.get("reason_code")},
            "borrowed_short": {"status": margin.get("borrowed_short_status", "unknown"),
                               "as_of": margin.get("borrowed_short_as_of_date"), "provider": margin.get("borrowed_short_source"),
                               "reason_code": margin.get("borrowed_short_reason_code") if margin.get("borrowed_short_status") else "status_not_reported"},
        }
        from source_observation_freshness import parse_observation_date
        unknown_dates = []
        for name, component in components.items():
            component["retrieval_status"] = "success" if component["status"] == "partial" else component["status"]
            component["date_status"] = "reported" if parse_observation_date(component.get("as_of")) else "unknown"
            if component["status"] in {"success", "partial"} and component["date_status"] == "unknown":
                component["reason_code"] = "observation_date_unknown"
                unknown_dates.append(name)
        successful = sum(item["status"] == "success" for item in components.values())
        available = sum(item["status"] in {"success", "partial"} for item in components.values())
        coverage = "success" if successful == len(components) and not unknown_dates else "partial" if available else "unavailable"
        labels = {"tdcc": "集保股權", "margin_short": "融資券", "borrowed_short": "借券"}
        date_note = ("、".join(labels[name] for name in unknown_dates) + "觀測日期未知；保留已取得數值，不能確認資料日期。") if unknown_dates else ""
        if margin.get("status") == "partial":
            date_note += "融資券核心餘額不完整；保留已取得欄位，不將缺值視為零。"
        value.update(status=coverage, component_statuses=components, coverage_notes=[date_note] if date_note else [])
        status = AUDIT_STATUS_SUCCESS if coverage == "success" else AUDIT_STATUS_DEGRADED_ENRICHMENT if available else AUDIT_STATUS_UNAVAILABLE
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=value if available else None,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": available,
                "cache_hit": False,
                "stale": False,
                "coverage_status": coverage,
                "component_statuses": components,
                "message": date_note or ("籌碼分項資料已回傳；請依各來源狀態與日期確認覆蓋。" if available else "TDCC/TWSE/TPEx 籌碼資料暫無可用結果。"),
            },
        )


class PhilJobNetJobObservationProvider(DataProvider):
    name = 'PhilJobNet exact employer portal observation'
    source = 'alternative_data'
    markets = {'tw'}
    cost_tier = 'free'
    capabilities = {'alternative_data', 'job_openings'}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .context_provider_cache import cached_context_result
        return cached_context_result(self, request, context, self._fetch_uncached)

    def _fetch_uncached(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.philjobnet_medtecs import fetch_philjobnet_observation
        value, audit = fetch_philjobnet_observation(request.ticker)
        payload = {'job_openings_philjobnet':value, 'coverage_status':value['coverage_status'],
                   'coverage_notes':[value['coverage_note']],
                   'component_statuses':{'philjobnet':{'status':'valid_empty','provider':self.name,
                                                       'query_scope':value['query_scope']}}} if value else None
        return ProviderResult(self.source,self.name,audit['status'],value=payload,audit=audit)


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
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS, source_record_count
        from alternative_data_fetcher import (fetch_104_company_jobs, fetch_104_company_jobs_by_ubn,
                                              fetch_104_job_openings_count, fetch_1111_job_openings_count,
                                              recruitment_company_name, unique_recruitment_records)

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        company_name = recruitment_company_name(str(data.get("company_name") or request.ticker),
                                                {**data, "ticker": data.get("ticker") or request.ticker})
        company_name = company_name or str(data.get("company_name") or request.ticker).strip()
        company_context = {**data, "ticker": request.ticker}
        philjobnet_attempt = None
        if request.ticker == '9103.TW':
            from .market_sources.philjobnet_medtecs import verified_philjobnet_observation
            observation = PhilJobNetJobObservationProvider()._fetch_uncached(request,context)
            philjobnet_attempt = observation.audit
            if observation.status == 'success' and verified_philjobnet_observation(
                    observation.value['job_openings_philjobnet'],company_context,require_fresh=True):
                return observation
        fallback_memo = {}
        raw_keywords = data.get("alternative_data_keywords") or data.get("job_opening_keywords") or []
        if isinstance(raw_keywords, str):
            keywords = [raw_keywords]
        else:
            keywords = [str(keyword).strip() for keyword in list(raw_keywords or []) if str(keyword).strip()]
        if not keywords:
            keywords = _default_job_opening_keywords(data)

        identity = data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {}
        legal_name = str(identity.get("legal_name") or "").strip()
        legal_name_evidence = None
        if (identity.get("ticker") == request.ticker
                and str(data.get("quote_type") or identity.get("instrument_type") or "").upper() == "EQUITY"
                and str(identity.get("official_name") or "").strip()):
            from .market_sources.official_company_legal_name import get_official_legal_name
            anchor = get_official_legal_name(request.ticker, identity["official_name"])
            # A supplied legal name does not carry the roster's UBN receipt.
            # Recover the same official anchor without replacing a conflicting name.
            if anchor and (not legal_name or legal_name == anchor.get("legal_name")):
                legal_name_evidence = anchor
                legal_name = anchor["legal_name"]
        verified_ubn = ""
        if legal_name_evidence and legal_name:
            from .market_sources.official_company_legal_name import (
                verified_legal_name_from_evidence, verified_official_ubn_from_evidence,
            )
            official_short = str(identity.get("official_name") or "").strip()
            if verified_legal_name_from_evidence(legal_name_evidence, request.ticker, official_short) == legal_name:
                verified_ubn = verified_official_ubn_from_evidence(
                    legal_name_evidence, request.ticker, official_short)
        company_jobs = (fetch_104_company_jobs(legal_name,
                        official_short_name=str(identity.get("official_name") or "").strip(),
                        official_ubn=verified_ubn) if verified_ubn else
                        fetch_104_company_jobs(legal_name)) if legal_name else None
        if (verified_ubn and isinstance(company_jobs, dict)
                and company_jobs.get("status") != "success"):
            company_fallback = fetch_104_company_jobs_by_ubn(
                legal_name, verified_ubn,
                official_short_name=str(identity.get("official_name") or "").strip())
            if company_fallback.get("status") == "success":
                company_jobs = {**company_fallback,
                                "primary_status": company_jobs.get("status"),
                                "primary_reason_code": company_jobs.get("reason_code")}
        taiwanjobs = None
        if verified_ubn and legal_name and not (isinstance(company_jobs, dict) and company_jobs.get("status") == "success"):
            from .market_sources.taiwanjobs_company_jobs import fetch_taiwanjobs_company_jobs
            taiwanjobs = fetch_taiwanjobs_company_jobs(request.ticker, legal_name, verified_ubn)
        official_jobs = None
        if (request.ticker == "2882.TW" and legal_name == "國泰金融控股股份有限公司"
                and identity.get("ticker") == request.ticker
                and str(identity.get("official_name") or "").strip() == "國泰金"
                and str(data.get("quote_type") or "").upper() == "EQUITY"
                and str(identity.get("instrument_type") or "").upper() == "EQUITY"):
            from .market_sources.cathay_careers import fetch_official_cathay_jobs
            official_jobs = fetch_official_cathay_jobs(request.ticker)
        psc_verified_count = 0
        if (request.ticker == "2855.TW" and legal_name == "統一綜合證券股份有限公司"
                and identity.get("ticker") == request.ticker
                and str(identity.get("official_name") or "").strip() == "統一證"
                and str(data.get("quote_type") or "").upper() == "EQUITY"
                and str(identity.get("instrument_type") or "").upper() == "EQUITY"):
            from .market_sources.psc_careers import (
                fetch_official_psc_jobs, verified_psc_job_count, verified_psc_issuer_receipt,
            )
            primary_count = source_record_count(self.source, {
                **company_context, self.source: {
                    "company_legal_name_evidence": legal_name_evidence,
                    "job_openings_104": [{**company_jobs, "recent_recruitment_news": []}]
                        if isinstance(company_jobs, dict) and company_jobs.get("evidence_kind") == "company_job_postings"
                        and company_jobs.get("job_count") is None else [],
                    "job_openings_taiwanjobs": taiwanjobs,
                },
            })
            if not primary_count:
                if not verified_psc_issuer_receipt(legal_name_evidence, request.ticker, "統一證"):
                    from .market_sources.official_company_legal_name import get_official_legal_name
                    current_anchor = get_official_legal_name(request.ticker, "統一證")
                    if verified_psc_issuer_receipt(current_anchor, request.ticker, "統一證"):
                        legal_name_evidence = current_anchor
                        verified_ubn = current_anchor["official_ubn"]
                if verified_psc_issuer_receipt(legal_name_evidence, request.ticker, "統一證"):
                    official_jobs = fetch_official_psc_jobs(request.ticker, legal_name, verified_ubn)
                    psc_verified_count = verified_psc_job_count(official_jobs, request.ticker, legal_name, verified_ubn)
        kgi_verified_count = 0
        if (request.ticker == "2883.TW" and data.get("ticker") == request.ticker
                and identity.get("ticker") == request.ticker and identity.get("official_name") == "凱基金"
                and data.get("quote_type") == "EQUITY" and identity.get("instrument_type") == "EQUITY"
                and identity.get("stock_id") in (None, "", "2883")
                and data.get("stock_id") in (None, "", "2883")
                and identity.get("official_ubn") in (None, "", "70827383")
                and data.get("instrument_type") in (None, "", "EQUITY")
                and data.get("quoteType") in (None, "", "EQUITY")):
            from .market_sources.kgi_careers import fetch_official_jobs, verified_job_count, verified_issuer, LEGAL, UBN
            primary_count = source_record_count(self.source, {
                **company_context, self.source: {
                    "company_legal_name_evidence": legal_name_evidence,
                    "job_openings_104": [{**company_jobs, "recent_recruitment_news": []}]
                        if isinstance(company_jobs, dict) and company_jobs.get("evidence_kind") == "company_job_postings"
                        and company_jobs.get("job_count") is None else [],
                    "job_openings_taiwanjobs": taiwanjobs,
                },
            })
            if not primary_count:
                if not verified_issuer(legal_name_evidence, request.ticker, "凱基金"):
                    from .market_sources.official_company_legal_name import get_official_legal_name
                    current_anchor = get_official_legal_name(request.ticker, "凱基金")
                    if verified_issuer(current_anchor, request.ticker, "凱基金"):
                        legal_name_evidence = current_anchor
                if verified_issuer(legal_name_evidence, request.ticker, "凱基金") and legal_name in ("", LEGAL):
                    legal_name, verified_ubn = LEGAL, UBN
                    official_jobs = fetch_official_jobs(request.ticker, legal_name, verified_ubn)
                    kgi_verified_count = verified_job_count(official_jobs, request.ticker, legal_name, verified_ubn)
        skip_keyword_search = bool(psc_verified_count or kgi_verified_count)
        results_104 = (([company_jobs] if isinstance(company_jobs, dict) else []) if skip_keyword_search else
                       [company_jobs] if isinstance(company_jobs, dict) and company_jobs.get("status") == "success" else
                       [fetch_104_job_openings_count(company_name, keyword, company_context=company_context, fallback_memo=fallback_memo) for keyword in keywords[:3]])
        results_1111 = ([] if skip_keyword_search else
                        [fetch_1111_job_openings_count(company_name, keyword, company_context=company_context, fallback_memo=fallback_memo) for keyword in keywords[:3]])
        
        records = [item for item in results_104 + results_1111 if isinstance(item, dict)]
        numeric = [item for item in records if item.get("status") == "success"
                   and isinstance(item.get("job_count"), int) and not isinstance(item.get("job_count"), bool)
                   and item["job_count"] >= 0]
        verified_jobs = [row for item in records if item.get("status") == "success"
                         and item.get("evidence_kind") == "company_job_postings"
                         for row in (item.get("job_postings") or []) if isinstance(row, dict)]
        official_verified_jobs = ((official_jobs.get("job_postings") or []) if isinstance(official_jobs, dict)
                                  and official_jobs.get("status") == "success"
                                  and (request.ticker != "2855.TW" or psc_verified_count)
                                  and (request.ticker != "2883.TW" or kgi_verified_count) else [])
        if (request.ticker == "2891.TW"
                and legal_name == "中國信託金融控股股份有限公司"
                and identity.get("ticker") == request.ticker
                and str(identity.get("official_name") or "").strip() == "中信金"
                and str(data.get("quote_type") or "").upper() == "EQUITY"
                and str(identity.get("instrument_type") or "").upper() == "EQUITY"):
            from .market_sources.ctbc_careers import fetch_official_ctbc_jobs, verified_ctbc_job_count
            primary_count = source_record_count(self.source, {
                **company_context,
                self.source: {
                    "company_legal_name_evidence": legal_name_evidence,
                    "job_openings_104": [
                        {**item, "recent_recruitment_news": []} for item in results_104
                        if isinstance(item, dict) and item.get("evidence_kind") == "company_job_postings"
                        and item.get("job_count") is None
                    ],
                },
            })
            if not primary_count:
                official_jobs = fetch_official_ctbc_jobs(request.ticker)
                if verified_ctbc_job_count(official_jobs, request.ticker, legal_name):
                    official_verified_jobs = official_jobs["job_postings"]
        if (taiwanjobs is not None and taiwanjobs.get("status") != "success"
                and not verified_jobs and not official_verified_jobs):
            from .market_sources.taiwanjobs_company_jobs import fetch_taiwanjobs_regional_jobs
            regional = fetch_taiwanjobs_regional_jobs(request.ticker, legal_name, verified_ubn)
            if regional.get("status") == "success":
                taiwanjobs = {**regional, "primary_status": taiwanjobs.get("status"),
                              "primary_reason_code": taiwanjobs.get("reason_code")}
        taiwanjobs_verified_jobs = (taiwanjobs.get("job_postings") or []) if isinstance(taiwanjobs, dict) and taiwanjobs.get("status") == "success" else []
        recruitment_news = unique_recruitment_records([row for item in records for row in (item.get("recent_recruitment_news") or [])])
        news_count = len(recruitment_news)
        complete_numeric = len(numeric) == len(results_104) + len(results_1111)
        components = {}
        if philjobnet_attempt is not None:
            components['philjobnet'] = philjobnet_attempt
        for provider, results in (("104", results_104), ("1111", results_1111)):
            for index, raw in enumerate(results, start=1):
                item = raw if isinstance(raw, dict) else {}
                count = item.get("job_count")
                valid_count = (item.get("status") == "success" and isinstance(count, int)
                               and not isinstance(count, bool) and count >= 0)
                verified_postings = (item.get("status") == "success"
                                     and item.get("evidence_kind") == "company_job_postings"
                                     and bool(item.get("job_postings")))
                component_status = ("valid_empty" if valid_count and count == 0 else
                                    "success" if valid_count else
                                    "verified_company_postings" if verified_postings else
                                    "qualitative_only" if item.get("recent_recruitment_news") else "unavailable")
                components[f"{provider}_{index}"] = {
                    "status": component_status,
                    "provider": str(item.get("actual_provider") or f"{provider} Job Search"),
                    **{k:item[k] for k in ("page_kind", "http_status", "response_sha256", "response_bytes", "parser_version",
                                           "primary_provider", "primary_status", "fallback_status") if k in item},
                    "reason_code": str(item.get("reason_code") or item.get("fallback_reason")
                                       or ("numeric_count" if valid_count else "count_not_reported")),
                }
        if official_jobs is not None:
            components["official_careers"] = {
                "status": "verified_company_postings" if official_verified_jobs else "unavailable",
                "provider": str(official_jobs.get("source") or "Cathay Financial Holdings official careers"),
                "reason_code": str(official_jobs.get("reason_code") or
                                   ("exact_open_issuer_postings" if official_verified_jobs else "official_career_unverified")),
                **{key: official_jobs[key] for key in ("source_url", "response_sha256", "fetched_at_epoch",
                                                    "current_open_job_count", "rejected_count", "http_request_count",
                                                    "component_receipts", "partial_failure_reasons", "detail_rejected_count") if key in official_jobs},
            }
        if skip_keyword_search:
            components["keyword_searches"] = {"status": "local_block", "provider": "104/1111 keyword searches",
                "http_request_sent": False, "reason_code": "verified_current_open_issuer_details_available"}
        if taiwanjobs is not None:
            components["taiwanjobs"] = {
                "status": "verified_company_postings" if taiwanjobs_verified_jobs else "unavailable",
                "provider": str(taiwanjobs.get("source") or "TaiwanJobs public company search"),
                "reason_code": str(taiwanjobs.get("reason_code") or
                                   ("exact_open_issuer_postings" if taiwanjobs_verified_jobs else "company_or_open_job_unverified")),
                **{key: taiwanjobs[key] for key in ("source_url", "response_sha256", "fetched_at_epoch",
                                                    "current_open_job_count", "rejected_count") if key in taiwanjobs},
            }
        coverage = ("partial" if numeric and not complete_numeric else
                    "valid_empty" if numeric and all(item["job_count"] == 0 for item in numeric)
                    else "success" if numeric and complete_numeric else
                    "partial" if verified_jobs or official_verified_jobs or taiwanjobs_verified_jobs or numeric else
                    "qualitative_only" if news_count else "unavailable")
        status = AUDIT_STATUS_SUCCESS if verified_jobs or official_verified_jobs or taiwanjobs_verified_jobs or (complete_numeric and numeric) else AUDIT_STATUS_DEGRADED_ENRICHMENT
        value = {
            "status": coverage,
            "job_openings_104": results_104[0] if len(results_104) == 1 else results_104,
            "job_openings_1111": results_1111[0] if len(results_1111) == 1 else results_1111,
            "job_openings_official": official_jobs,
            "job_openings_taiwanjobs": taiwanjobs,
            "numeric_count_coverage": len(numeric), "recruitment_news_count": news_count,
            "recent_company_job_count_104": len(verified_jobs) if verified_jobs else None,
            "current_open_job_count_official": official_jobs.get("current_open_job_count") if official_verified_jobs else None,
            "current_open_job_count_taiwanjobs": taiwanjobs.get("current_open_job_count") if taiwanjobs_verified_jobs else None,
            "recent_recruitment_news": recruitment_news,
            "component_statuses": components,
            "company_legal_name_evidence": legal_name_evidence,
            "coverage_notes": ["104 公司職缺只代表精確雇主近期刊登樣本；台灣就業通與官方職缺只代表核對過公司身分的當時開放職缺樣本，不含子公司、不推定刊登日期；均非全網總數。徵才新聞僅為質性訊號；失敗不代表零職缺。"],
        }
        return ProviderResult(
            source=self.source, provider=self.name, status=status, value=value,
            audit={"source": self.source, "provider": self.name, "status": status,
                   "record_count": source_record_count(self.source, {**company_context, self.source: value}),
                   "cache_hit": False, "stale": False,
                   **({"fetched_at_epoch": official_jobs["fetched_at_epoch"],
                       "cache_hit": bool(official_jobs.get("component_receipts")) and all(
                           row.get("cache_hit") is True for row in official_jobs["component_receipts"]),
                       "http_request_count": official_jobs["http_request_count"],
                       "http_request_sent": official_jobs["http_request_count"] > 0,
                       "actual_provider": official_jobs["source"]} if kgi_verified_count else {}),
                   "coverage_status": coverage, "numeric_count_coverage": len(numeric),
                   "verified_company_postings": len(verified_jobs),
                   "verified_official_company_postings": len(official_verified_jobs),
                   "verified_taiwanjobs_company_postings": len(taiwanjobs_verified_jobs),
                   "recruitment_news_count": news_count,
                   "company_legal_name_basis": "official_company_profile" if legal_name_evidence else
                       "existing_identity" if legal_name else "unavailable",
                   "company_legal_name_source_url": legal_name_evidence.get("source_url") if legal_name_evidence else None,
                   "company_legal_name_response_sha256": legal_name_evidence.get("response_sha256") if legal_name_evidence else None,
                   "component_statuses": components,
                   "message": "職缺查詢保留數量與質性備援的差別。"},
        )



class SocialSentimentProvider(DataProvider):
    name = "Social Forum Sentiment (Dcard/Mobile01/PTT/CMoney/Yahoo)"
    source = "social_sentiment"
    markets = {"tw"}
    cost_tier = "free"
    capabilities = {"social_sentiment"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .context_provider_cache import cached_context_result
        return cached_context_result(self, request, context, self._fetch_uncached)

    def _fetch_uncached(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS
        from news_fetchers import fetch_ptt_stock_sentiment

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = _taiwan_stock_id(data.get("ticker") or request.ticker)
        # Google News RSS gives an index timestamp and a wrapper URL, neither
        # of which attests an original forum post. Retain the channel shape for
        # cached data, but do not spend network calls on inadmissible results.
        value = {
            "dcard": [],
            "mobile01": [],
            "pttweb": [],
            "ptt_stock_direct": [],
            "cmoney_stock_direct": [],
            "yahoo_stock_direct": [],
        }

        from source_content_selection import select_company_records
        if ticker.isdigit():
            from .market_sources.cmoney_stock_posts import fetch_cmoney_stock_posts
            value["cmoney_stock_direct"] = fetch_cmoney_stock_posts(ticker)
        originals = [dict(item, social_channel=channel) for channel, items in value.items() for item in items]
        selected, selection = select_company_records(originals, {**data, "ticker": request.ticker})
        yahoo_diagnostic = {}
        if not selected and ticker.isdigit():
            from .market_sources.yahoo_stock_comments import fetch_yahoo_stock_comments
            value["yahoo_stock_direct"] = fetch_yahoo_stock_comments(
                request.ticker, data, diagnostics=yahoo_diagnostic)
            originals = [dict(item, social_channel=channel) for channel, items in value.items() for item in items]
            selected, selection = select_company_records(originals, {**data, "ticker": request.ticker})
        if not selected and ticker.isdigit():
            # A verified original makes an additional PTT request unnecessary;
            # PTT remains the fallback when neither public board survives.
            for item in fetch_ptt_stock_sentiment(ticker, limit=5):
                if not isinstance(item, dict):
                    continue
                value["ptt_stock_direct"].append({
                    "title": str(item.get("title") or "").strip(),
                    "date": str(item.get("date") or item.get("published_date") or "").strip(),
                    "source": str(item.get("source") or "PTT Stock").strip(),
                    "link": str(item.get("link") or item.get("url") or "").strip(),
                    **{key: item[key] for key in (
                        "summary", "text", "text_truncated", "body_text_chars",
                        "body_text_sha256", "response_sha256", "response_bytes", "parser_version",
                    ) if key in item},
                })
            originals = [dict(item, social_channel=channel) for channel, items in value.items() for item in items]
            selected, selection = select_company_records(originals, {**data, "ticker": request.ticker})
        value = {channel: [item for item in selected if item['social_channel'] == channel] for channel in value}
        total_records = len(selected)
        value.update(status="partial" if selection["rejected_count"] else "success" if total_records else "empty_unknown", sample_count=total_records,
                     sentiment_assessment="not_assessed", coverage_notes=[
                         "直接原文樣本非完整社群母體；無結果不能推定中性或無討論。",
                         "PTT只保留發文者正文最多2,000字元，節錄與原回應hash明示；作者帳號、推文與平台尾註不作正文公司身分證據。",
                     ])
        status = AUDIT_STATUS_SUCCESS if total_records > 0 and not selection["rejected_count"] else AUDIT_STATUS_DEGRADED_ENRICHMENT
        
        value.update(selection)
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
                **selection,
                "cache_hit": False,
                "stale": False,
                "component_statuses": {"yahoo_stock_comments": yahoo_diagnostic} if yahoo_diagnostic else {},
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
