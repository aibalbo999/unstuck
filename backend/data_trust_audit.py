"""Source audit entry helpers and source record counting."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any, Optional

from data_trust_constants import (
    AUDIT_STATUS_LABELS,
    AUDIT_STATUS_UNAVAILABLE,
    AUDIT_STATUSES,
    SOURCE_LABELS,
)
from data_trust_values import (
    has_value,
    list_count,
    safe_bool_value as _safe_bool,
    safe_int_value as _safe_int,
    safe_text_value as _safe_text,
    set_items as _set_items,
    string_list,
)
from mapping_fields import safe_mapping_dict, safe_sequence_items


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_from_epoch(epoch: Optional[float]) -> Optional[str]:
    if isinstance(epoch, bool) or not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    try:
        epoch_value = float(epoch)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(epoch_value):
        return None
    try:
        return datetime.fromtimestamp(epoch_value, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def source_label(source: str) -> str:
    source_text = _safe_text(source).strip()
    return SOURCE_LABELS.get(source_text, source_text or "unknown")


def audit_status_label(status: str) -> str:
    status_text = _safe_text(status).strip()
    return AUDIT_STATUS_LABELS.get(status_text, status_text or "unknown")


def data_snapshot_filename_for_report(filename: str) -> str:
    return filename[:-5] + ".data.json" if filename.endswith(".html") else f"{filename}.data.json"


def duration_ms(started_at_epoch: Optional[float], finished_at_epoch: Optional[float], duration_ms_value: Optional[float]) -> Optional[int]:
    if isinstance(duration_ms_value, bool):
        pass
    elif isinstance(duration_ms_value, (int, float)):
        try:
            duration_value = float(duration_ms_value)
        except (OverflowError, TypeError, ValueError):
            pass
        else:
            if math.isfinite(duration_value):
                return max(0, int(round(duration_value)))
    if (
        isinstance(started_at_epoch, (int, float))
        and not isinstance(started_at_epoch, bool)
        and isinstance(finished_at_epoch, (int, float))
        and not isinstance(finished_at_epoch, bool)
    ):
        if iso_from_epoch(started_at_epoch) is None or iso_from_epoch(finished_at_epoch) is None:
            return None
        try:
            started_value = float(started_at_epoch)
            finished_value = float(finished_at_epoch)
        except (OverflowError, TypeError, ValueError):
            return None
        if math.isfinite(started_value) and math.isfinite(finished_value):
            return max(0, int(round((finished_value - started_value) * 1000)))
    return None


def build_source_audit_entry(
    source: str,
    provider: str,
    status: str,
    *,
    fetched_at_epoch: Optional[float] = None,
    fetched_at: Optional[str] = None,
    started_at_epoch: Optional[float] = None,
    finished_at_epoch: Optional[float] = None,
    duration_ms: Optional[float] = None,
    record_count: Optional[int] = None,
    cache_hit: bool = False,
    stale: bool = False,
    error_kind: str = "",
    message: str = "",
) -> dict:
    status_text = _safe_text(status).strip()
    normalized_status = status_text if status_text in AUDIT_STATUSES else AUDIT_STATUS_UNAVAILABLE
    raw_finished_at_epoch = finished_at_epoch
    fallback_finished_at_epoch = finished_at_epoch if iso_from_epoch(finished_at_epoch) is not None else time.time()
    duration_finished_at_epoch = fallback_finished_at_epoch if raw_finished_at_epoch is None else raw_finished_at_epoch
    fetched_at_value = _safe_text(fetched_at).strip() or iso_from_epoch(fetched_at_epoch) or iso_from_epoch(fallback_finished_at_epoch)
    from provider_correlation import current_audit_correlation
    return {
        **current_audit_correlation(),
        "source": _safe_text(source).strip() or "unknown",
        "provider": _safe_text(provider).strip(),
        "status": normalized_status,
        "fetched_at": fetched_at_value,
        "duration_ms": duration_ms_fn(started_at_epoch, duration_finished_at_epoch, duration_ms),
        "record_count": _safe_int(record_count),
        "cache_hit": _safe_bool(cache_hit),
        "stale": _safe_bool(stale),
        "error_kind": _safe_text(error_kind).strip(),
        "message": _safe_text(message).strip(),
    }


def duration_ms_fn(started_at_epoch: Optional[float], finished_at_epoch: Optional[float], value: Optional[float]) -> Optional[int]:
    return duration_ms(started_at_epoch, finished_at_epoch, value)


def append_source_audit(data: dict, entry: dict) -> dict:
    if not isinstance(data, dict):
        return data
    entries = data.get("source_audit")
    if isinstance(entries, tuple):
        entries = safe_sequence_items(entries)
    elif not isinstance(entries, list):
        entries = []
    entries.append(entry)
    data["source_audit"] = entries
    return data


def _alternative_observation_count(data: dict) -> int:
    """Count job observations and eligible unique news, never diagnostic fields."""
    from news_record_utils import canonical_link, clean_text
    from source_content_selection import select_company_records

    payload = safe_mapping_dict(data.get("alternative_data")) or {}
    philjobnet_count = 0
    if payload.get('job_openings_philjobnet') is not None:
        from data_fetch.market_sources.philjobnet_medtecs import verified_philjobnet_observation
        philjobnet_count = int(verified_philjobnet_observation(payload['job_openings_philjobnet'],data))
    numeric_count = 0
    company_jobs = set()
    news = safe_sequence_items(payload.get("recent_recruitment_news"))
    for field in ("job_openings_104", "job_openings_1111"):
        component = payload.get(field)
        entries = [component] if isinstance(component, Mapping) else safe_sequence_items(component)
        for raw in entries:
            item = safe_mapping_dict(raw) or {}
            if item.get("status") != "success":
                continue
            value = item.get("job_count")
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0 and has_value(value):
                numeric_count += 1
            if (field == "job_openings_104" and item.get("evidence_kind") == "company_job_postings"
                    and item.get("query_scope") == "exact_company_recent_postings"
                    and item.get("job_count") is None
                    and item.get("source") == "104 Company Jobs API"
                    and (_safe_text(item.get("source_url")).startswith("https://www.104.com.tw/jobs/search/api/jobs?")
                         or re.fullmatch(r"https://www\.104\.com\.tw/api/companies/[a-z0-9]+/jobs",
                                         _safe_text(item.get("source_url"))))
                    and re.fullmatch(r"[0-9a-f]{64}", _safe_text(item.get("response_sha256")))):
                identity = safe_mapping_dict(data.get("company_identity")) or {}
                legal_name = _safe_text(identity.get("legal_name")).strip()
                if not legal_name:
                    from data_fetch.market_sources.official_company_legal_name import verified_legal_name_from_evidence
                    legal_name = verified_legal_name_from_evidence(
                        safe_mapping_dict(payload.get("company_legal_name_evidence")),
                        _safe_text(data.get("ticker")), _safe_text(identity.get("official_name")),
                    )
                postings = safe_sequence_items(item.get("job_postings"))
                if (legal_name and item.get("company_name") == legal_name
                        and type(item.get("recent_company_job_count")) is int
                        and item["recent_company_job_count"] == len(postings) > 0):
                    for raw_job in safe_sequence_items(item.get("job_postings")):
                        job = safe_mapping_dict(raw_job) or {}
                        url = _safe_text(job.get("url")).strip()
                        source_employer = _safe_text(job.get("source_employer") or job.get("employer")).strip()
                        match_basis = _safe_text(job.get("employer_match_basis")).strip()
                        if match_basis == "official_name_ubn_company_api":
                            from zoneinfo import ZoneInfo
                            from data_fetch.market_sources.official_company_legal_name import (
                                verified_legal_name_from_evidence, verified_official_ubn_from_evidence,
                            )
                            receipt = safe_mapping_dict(payload.get("company_legal_name_evidence"))
                            ticker = _safe_text(data.get("ticker"))
                            short = _safe_text(identity.get("official_name")).strip()
                            ubn = verified_official_ubn_from_evidence(receipt, ticker, short)
                            slug = _safe_text(job.get("source_employer_id"))
                            job_slug = _safe_text(job.get("source_job_no"))
                            latin_prefix = legal_name + " _"
                            name_matches = (source_employer == legal_name or
                                            (2 <= len(short) <= 50 and not any(c in short for c in '()（）\n\r')
                                             and source_employer in (f"{legal_name}({short})", f"({short}){legal_name}")) or
                                            (source_employer.startswith(latin_prefix)
                                             and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 .,&'-]{2,79}",
                                                                   source_employer[len(latin_prefix):]))))
                            try:
                                published_text = _safe_text(job.get("published_date"))
                                published = date.fromisoformat(published_text) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published_text) else None
                                age = (datetime.now(ZoneInfo("Asia/Taipei")).date() - published).days if published else -1
                                ids_match = (re.fullmatch(r"[a-z0-9]{3,12}", slug) is not None
                                             and re.fullmatch(r"[a-z0-9]{3,12}", job_slug) is not None
                                             and int(slug, 36) == int(ubn) * 1000
                                             and _safe_text(job.get("employer_id")) == str(int(slug, 36))
                                             and _safe_text(job.get("job_no")) == str(int(job_slug, 36)))
                            except (ValueError, TypeError):
                                ids_match, age = False, -1
                            employer_verified = bool(ubn and
                                verified_legal_name_from_evidence(receipt, ticker, short) == legal_name
                                and name_matches and ids_match and 0 <= age <= 30
                                and item.get("source_url") == f"https://www.104.com.tw/api/companies/{slug}/jobs"
                                and url == f"https://www.104.com.tw/job/{job_slug}")
                        elif match_basis in ("official_name_ubn_alias", "official_name_ubn_prefix_alias",
                                           "official_name_ubn_latin_suffix"):
                            from data_fetch.market_sources.official_company_legal_name import verified_official_ubn_from_evidence
                            short = _safe_text(identity.get("official_name")).strip()
                            ubn = verified_official_ubn_from_evidence(
                                safe_mapping_dict(payload.get("company_legal_name_evidence")),
                                _safe_text(data.get("ticker")), short)
                            if match_basis == "official_name_ubn_latin_suffix":
                                latin_prefix = legal_name + " _"
                                name_matches = (source_employer.startswith(latin_prefix)
                                                and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 .,&'-]{2,79}",
                                                                      source_employer[len(latin_prefix):])))
                            else:
                                expected_employer = (f"({short}){legal_name}" if match_basis == "official_name_ubn_prefix_alias"
                                                     else f"{legal_name}({short})")
                                name_matches = source_employer == expected_employer
                            employer_verified = bool(ubn and name_matches
                                                     and _safe_text(job.get("employer_id")) == str(int(ubn)) + "000")
                        else:
                            employer_verified = (match_basis in ("", "exact_legal_name")
                                                 and source_employer == legal_name)
                        if (job.get("employer") == legal_name and employer_verified and job.get("title")
                                and _safe_text(job.get("employer_id")).isdigit()
                                and _safe_text(job.get("job_no")).isdigit()
                                and re.fullmatch(r"https://www\.104\.com\.tw/job/[A-Za-z0-9]+", url)):
                            company_jobs.add(url)
            if item.get("evidence_kind") == "recruitment_news":
                news.extend(safe_sequence_items(item.get("recent_recruitment_news")))
    official_count = 0
    official = safe_mapping_dict(payload.get("job_openings_official"))
    if official:
        identity = safe_mapping_dict(data.get("company_identity")) or {}
        ticker = _safe_text(data.get("ticker"))
        if (ticker in ("2882.TW", "2891.TW", "2855.TW", "2883.TW") and identity.get("ticker") == ticker
                and _safe_text(identity.get("official_name")).strip() == {"2882.TW": "國泰金", "2891.TW": "中信金", "2855.TW": "統一證", "2883.TW": "凱基金"}[ticker]
                and _safe_text(data.get("quote_type")).upper() == "EQUITY"
                and _safe_text(identity.get("instrument_type")).upper() == "EQUITY"):
            legal_name = _safe_text(identity.get("legal_name")).strip()
            if not legal_name:
                from data_fetch.market_sources.official_company_legal_name import verified_legal_name_from_evidence
                legal_name = verified_legal_name_from_evidence(
                    safe_mapping_dict(payload.get("company_legal_name_evidence")),
                    ticker, _safe_text(identity.get("official_name")),
                )
            if ticker == "2882.TW":
                from data_fetch.market_sources.cathay_careers import verified_official_job_count
                official_count = verified_official_job_count(official, ticker, legal_name)
            elif ticker == "2891.TW":
                from data_fetch.market_sources.ctbc_careers import verified_ctbc_job_count
                official_count = verified_ctbc_job_count(official, ticker, legal_name)
            elif ticker == "2883.TW":
                from data_fetch.market_sources.kgi_careers import verified_job_count, verified_issuer, UBN
                receipt = safe_mapping_dict(payload.get("company_legal_name_evidence"))
                if (data.get("instrument_type") in (None, "", "EQUITY")
                        and data.get("quoteType") in (None, "", "EQUITY")
                        and identity.get("stock_id") in (None, "", "2883")
                        and data.get("stock_id") in (None, "", "2883")
                        and identity.get("official_ubn") in (None, "", UBN)
                        and verified_issuer(receipt, ticker, "凱基金")):
                    official_count = verified_job_count(official, ticker, legal_name, UBN)
            else:
                from data_fetch.market_sources.psc_careers import (
                    verified_psc_job_count, verified_psc_issuer_receipt, UBN,
                )
                receipt = safe_mapping_dict(payload.get("company_legal_name_evidence"))
                short = _safe_text(identity.get("official_name")).strip()
                if verified_psc_issuer_receipt(receipt, ticker, short):
                    official_count = verified_psc_job_count(official, ticker, legal_name, UBN)
    taiwanjobs_count = 0
    taiwanjobs = safe_mapping_dict(payload.get("job_openings_taiwanjobs"))
    if taiwanjobs:
        identity = safe_mapping_dict(data.get("company_identity")) or {}
        ticker = _safe_text(data.get("ticker"))
        short = _safe_text(identity.get("official_name")).strip()
        from data_fetch.market_sources.official_company_legal_name import (
            verified_legal_name_from_evidence, verified_official_ubn_from_evidence,
        )
        receipt = safe_mapping_dict(payload.get("company_legal_name_evidence"))
        legal_name = verified_legal_name_from_evidence(receipt, ticker, short)
        ubn = verified_official_ubn_from_evidence(receipt, ticker, short)
        if legal_name and ubn and identity.get("ticker") == ticker:
            from data_fetch.market_sources.taiwanjobs_company_jobs import verified_taiwanjobs_job_count
            taiwanjobs_count = verified_taiwanjobs_job_count(taiwanjobs, ticker, legal_name, ubn)
    if not news:
        return numeric_count + len(company_jobs) + official_count + taiwanjobs_count + philjobnet_count
    selected, _ = select_company_records(news, data)
    links, titles = set(), set()
    for item in selected:
        text = clean_text(" ".join(str(item.get(key) or "") for key in ("title", "summary", "snippet", "text")))
        if re.search(r"徵才|擴編|招募|招聘|hiring|recruit", text, re.I):
            link = canonical_link(item.get("link") or item.get("url"))
            title = clean_text(item.get("title") or item.get("headline")).casefold()
            if not link or link in links or (title and title in titles):
                continue
            links.add(link)
            if title:
                titles.add(title)
    return numeric_count + len(company_jobs) + official_count + taiwanjobs_count + philjobnet_count + len(links)


def source_record_count(source: str, data: Any) -> int:
    data_map = safe_mapping_dict(data)
    if data_map is None:
        return 0
    data = data_map
    source = _safe_text(source).strip()
    if source == "alternative_data":
        return _alternative_observation_count(data)
    if source == "annual_workforce":
        observation = safe_mapping_dict(data.get(source)) or {}
        metrics = safe_mapping_dict(observation.get("metrics")) or {}
        average = metrics.get("employee_average_salary_thousand_twd")
        workforce_available = int(
            observation.get("observation_kind") == "annual_workforce_disclosure"
            and observation.get("ticker") == data.get("ticker")
            and observation.get("status") in {"success", "partial", "stale"}
            and isinstance(observation.get("report_year"), int)
            and not isinstance(observation.get("report_year"), bool)
            and isinstance(average, (int, float))
            and not isinstance(average, bool)
            and math.isfinite(average)
            and average > 0
        )
        from data_fetch.annual_occupational_safety import verified_occupational_safety_observation
        safety_available = verified_occupational_safety_observation(
            observation.get("esg_occupational_safety"), data.get("ticker"))
        return int(bool(workforce_available or safety_available))
    if source == "esg_occupational_safety":
        observation = safe_mapping_dict(data.get("annual_workforce")) or {}
        from data_fetch.annual_occupational_safety import verified_occupational_safety_observation
        return int(verified_occupational_safety_observation(
            observation.get("esg_occupational_safety"), data.get("ticker")))
    if source == "market_data":
        fields = ("current_price", "market_cap_raw", "pe_ratio_raw", "pb_ratio", "price_history")
        return sum(1 for field in fields if has_value(data.get(field)))
    if source == "financial_statements":
        return max(
            list_count(data.get("years")),
            list_count(data.get("revenue_history")),
            list_count(data.get("net_income_history")),
            list_count(data.get("fcf_history")),
            list_count(data.get("total_assets_history")),
            list_count(data.get("total_equity_history")),
        )
    if source == "monthly_revenue":
        return list_count(data.get("recent_monthly_revenue"))
    if source == "institutional_trading":
        value = safe_mapping_dict(data.get("institutional_trading"))
        if value is not None:
            daily = value.get("daily_total_net_buy_last_10")
            daily_count = list_count(daily)
            if daily_count:
                return daily_count
            fallback_values = [
                child
                for key, child in value.items()
                if key != "daily_total_net_buy_last_10"
            ]
            return 1 if any(has_value(child) for child in fallback_values) else 0
        return 0
    if source == "social_sentiment":
        social = safe_mapping_dict(data.get(source)) or {}
        from data_fetch.market_sources.yahoo_stock_comments import verified_sample
        yahoo_rows = social.get("yahoo_stock_direct")
        yahoo_count = sum(isinstance(row, dict) and verified_sample(row, data)
                          for row in (yahoo_rows if isinstance(yahoo_rows, list) else []))
        return yahoo_count + sum(list_count(social.get(key)) for key in
                                 ("dcard", "mobile01", "pttweb", "ptt_stock_direct", "cmoney_stock_direct"))
    if source == "dynamic_peer_metrics":
        peers = data.get("dynamic_peer_metrics")
        if not isinstance(peers, list):
            return 0
        return sum(1 for row in peers if isinstance(row, dict) and row.get("metrics_status") != "unavailable")
    if source == "pe_river_chart":
        value = safe_mapping_dict(data.get("pe_river_chart"))
        if value is None:
            return 0
        bands = value.get("bands")
        bands_map = safe_mapping_dict(bands)
        if bands_map:
            band_count = max((list_count(series) for series in bands_map.values()), default=0)
            if band_count:
                return band_count
        return list_count(value.get("years")) or list_count(value.get("eps_twd"))
    if source in {"official_disclosures", "company_ir"}:
        value = safe_mapping_dict(data.get(source)) or {}
        return list_count(value.get("documents"))
    if source == "recent_catalysts":
        return list_count(data.get("recent_catalysts"))
    if source == "global_market_context":
        value = safe_mapping_dict(data.get("global_market_context"))
        if value is not None:
            return list_count(value.get("items"))
        return 0
    if source == "international_news_context":
        value = safe_mapping_dict(data.get("international_news_context"))
        if value is not None:
            return list_count(value.get("topics"))
        return 0
    if source == "peer_discovery":
        return list_count(data.get("peer_discovery_results"))
    value = data.get(source)
    if isinstance(value, (list, tuple)):
        return list_count(value)
    if isinstance(value, (set, frozenset)):
        return sum(1 for item in _set_items(value) if has_value(item))
    if isinstance(value, Mapping):
        value_map = safe_mapping_dict(value)
        if value_map is None:
            return 0
        return sum(1 for child in value_map.values() if has_value(child))
    return 1 if has_value(value) else 0
