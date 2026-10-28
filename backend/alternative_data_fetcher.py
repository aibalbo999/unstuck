"""Alternative data fetchers used to validate company expansion signals."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from external_http_client import sync_get

JOB_104_SEARCH_URL = "https://www.104.com.tw/jobs/search/"
JOB_104_API_URL = "https://www.104.com.tw/jobs/search/api/jobs"
JOB_104_SAMPLE_PAGES = 3
JOB_104_COMPANY_SAMPLE_JOBS = 5
JOB_1111_SEARCH_URL = "https://www.1111.com.tw/search/job"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 stock-agent/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
}


class _JobSearchTransportError(Exception):
    """Raised when a job-search HTTP request fails before parsing."""


def _get_job_search_response(
    url: str,
    *,
    params: dict[str, str],
    headers: dict[str, str],
    timeout: float,
    provider: str,
    session: Any | None = None,
):
    from provider_transport_receipt import record_job_transport_receipt
    started=time.monotonic()
    response=None
    try:
        if session is not None:
            response=session.get(url,params=params,headers=headers,timeout=timeout)
            response.raise_for_status()
        else:
            response=sync_get(url,params=params,headers=headers,timeout=timeout,provider=provider)
        record_job_transport_receipt(provider,started,response=response,native_call=session is None)
        return response
    except Exception as exc:
        record_job_transport_receipt(provider,started,response=getattr(exc,'response',response),native_call=session is None)
        raise _JobSearchTransportError from exc


def fetch_104_company_jobs(
    legal_name: str, *, session: Any | None = None, timeout: float = 5,
    today: str | date | None = None, official_short_name: str | None = None,
    official_ubn: str | None = None,
) -> dict[str, Any]:
    """Fetch a bounded, exact-employer recent posting sample from 104 JSON.

    Search metadata includes sponsored and fuzzy matches, so its total is not
    an issuer job count. Only individually verified rows count, and zero exact
    rows cannot establish that the employer has no open positions.
    """
    company = str(legal_name or "").strip()
    if len(company) < 4 or any(ch in company for ch in ('"', '\n', '\r')):
        return _unavailable(company, "", "104 Company Jobs API", JOB_104_API_URL,
                            "缺少可核對的公司全名。", reason_code="issuer_unknown")
    try:
        current = date.fromisoformat(today) if isinstance(today, str) else today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    except ValueError:
        return _unavailable(company, "", "104 Company Jobs API", JOB_104_API_URL,
                            "查詢日期無效。", reason_code="invalid_date")
    params = {"keyword": f'"{company}"', "kwop": "2", "page": "1", "mode": "s", "order": "15"}
    headers = {**DEFAULT_HEADERS, "Accept": "application/json", "Referer": JOB_104_SEARCH_URL}
    source_url = f"{JOB_104_API_URL}?{urlencode(params)}"
    short = str(official_short_name or "").strip()
    ubn = str(official_ubn or "").strip()
    official_alias = (f"{company}({short})" if 2 <= len(short) <= 50
                      and not any(ch in short for ch in '()（）\n\r')
                      and re.fullmatch(r"\d{8}", ubn) and int(ubn) > 0 else "")
    official_prefix_alias = f"({short}){company}" if official_alias else ""
    alias_employer_id = str(int(ubn)) + "000" if official_alias else ""
    rows: list[dict] = []
    rejected = 0
    digests = []
    last_page = 1
    declared_page_count = None
    employer_ids: set[str] = set()
    try:
        for page in range(1, JOB_104_SAMPLE_PAGES + 1):
            if page > last_page:
                break
            if page > 1 and session is None:
                time.sleep(1.5)  # The public endpoint rate limits rapid pagination.
            params["page"] = str(page)
            response = _get_job_search_response(JOB_104_API_URL, params=params,
                headers=headers, timeout=timeout, provider="104 Company Jobs API", session=session)
            raw = str(response.text or "")
            if not 0 < len(raw.encode("utf-8")) <= 300_000:
                raise ValueError("104 JSON response size invalid")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("104 JSON response shape invalid")
            pagination = payload.get("metadata", {}).get("pagination", {})
            if (not isinstance(pagination, dict)
                    or type(pagination.get("currentPage")) is not int or pagination["currentPage"] != page
                    or type(pagination.get("lastPage")) is not int
                    or not page <= pagination["lastPage"] <= 10_000):
                raise ValueError("104 pagination incomplete or ambiguous")
            if declared_page_count is not None and pagination["lastPage"] != declared_page_count:
                raise ValueError("104 pagination changed across sampled pages")
            declared_page_count = pagination["lastPage"]
            last_page = pagination["lastPage"]
            candidates = payload.get("data")
            if isinstance(candidates, dict):
                candidates = candidates.get("list")
            if not isinstance(candidates, list) or len(candidates) > 100:
                raise ValueError("104 job list shape invalid")
            digests.append(hashlib.sha256(raw.encode("utf-8")).hexdigest())
            for item in candidates:
                if not isinstance(item, dict):
                    rejected += 1
                    continue
                source_employer = item.get("custName")
                employer_id = str(item.get("custNo") or "").strip()
                exact_name = source_employer == company
                matched_alias = source_employer == official_alias and employer_id == alias_employer_id
                matched_prefix_alias = (source_employer == official_prefix_alias
                                        and employer_id == alias_employer_id)
                latin_prefix = company + " _"
                matched_latin_suffix = (bool(official_alias) and isinstance(source_employer, str)
                                        and source_employer.startswith(latin_prefix)
                                        and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 .,&'-]{2,79}",
                                                              source_employer[len(latin_prefix):]))
                                        and employer_id == alias_employer_id)
                if not exact_name and not matched_alias and not matched_prefix_alias and not matched_latin_suffix:
                    rejected += 1
                    continue
                job_no = str(item.get("jobNo") or "").strip()
                title = str(item.get("jobName") or "").strip()
                link = item.get("link")
                url = str(link.get("job") or "").strip() if isinstance(link, dict) else ""
                try:
                    published = datetime.strptime(str(item.get("appearDate") or ""), "%Y%m%d").date()
                except ValueError:
                    rejected += 1
                    continue
                if (not employer_id.isdigit() or not job_no.isdigit() or not title
                        or not re.fullmatch(r"https://www\.104\.com\.tw/job/[A-Za-z0-9]+", url)
                        or not timedelta(0) <= current - published <= timedelta(days=30)):
                    rejected += 1
                    continue
                employer_ids.add(employer_id)
                rows.append({"title": title, "url": url, "published_date": published.isoformat(),
                             "employer": company, "source_employer": source_employer,
                             "employer_match_basis": ("official_name_ubn_latin_suffix" if matched_latin_suffix
                                                      else "official_name_ubn_prefix_alias" if matched_prefix_alias
                                                      else "official_name_ubn_alias" if matched_alias
                                                      else "exact_legal_name"),
                             "employer_id": employer_id, "job_no": job_no})
    except (_JobSearchTransportError, ValueError, TypeError, AttributeError):
        return _unavailable(company, "", "104 Company Jobs API", source_url,
                            "104 公司職缺 JSON 已查詢分頁未完整且可驗證。", reason_code="api_unverified")
    if len(employer_ids) != 1:
        return {**_unavailable(company, "", "104 Company Jobs API", source_url,
                              "未找到單一可核對雇主的近期職缺；不能推定零職缺。",
                              reason_code="exact_employer_unverified"), "recent_company_job_count": None,
                "rejected_count": rejected}
    unique: dict[str, dict] = {}
    for row in rows:
        if row["job_no"] in unique:
            rejected += 1
            if unique[row["job_no"]]["url"] != row["url"]:
                return _unavailable(company, "", "104 Company Jobs API", source_url,
                                    "同一職缺代號出現衝突連結。", reason_code="job_identity_conflict")
            continue
        unique[row["job_no"]] = row
    if not unique:
        return {**_unavailable(company, "", "104 Company Jobs API", source_url,
                              "未找到可核對的近期職缺；不能推定零職缺。",
                              reason_code="no_verified_postings"), "recent_company_job_count": None,
                "rejected_count": rejected}
    return {
        "status": "success", "company_name": company, "keyword": None, "job_count": None,
        "recent_company_job_count": len(unique), "job_postings": list(unique.values()),
        "query_scope": "exact_company_recent_postings", "evidence_kind": "company_job_postings",
        "source": "104 Company Jobs API", "source_url": source_url,
        "response_sha256": hashlib.sha256("|".join(digests).encode()).hexdigest(),
        "page_count": last_page, "searched_page_count": len(digests),
        "pagination_truncated": last_page > len(digests), "rejected_count": rejected,
        "coverage_status": ("bounded_company_recent_postings_sample" if last_page > len(digests)
                            else "company_recent_postings_only"),
        "message": "僅計入已查詢分頁中全名、雇主代號、職缺連結與刊登日期可核對的 104 近期職缺樣本；不是雇主或全網職缺總數。",
    }


def _base36(value: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    encoded = ""
    while value:
        value, remainder = divmod(value, 36)
        encoded = digits[remainder] + encoded
    return encoded or "0"


def _official_104_employer_label(legal_name: str, short_name: str, source_employer: str) -> bool:
    if source_employer == legal_name:
        return True
    if not 2 <= len(short_name) <= 50 or any(ch in short_name for ch in '()（）\n\r'):
        return False
    if source_employer in (f"{legal_name}({short_name})", f"({short_name}){legal_name}"):
        return True
    prefix = legal_name + " _"
    return (source_employer.startswith(prefix)
            and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 .,&'-]{2,79}", source_employer[len(prefix):])))


def fetch_104_company_jobs_by_ubn(
    legal_name: str, official_ubn: str, *, official_short_name: str | None = None,
    session: Any | None = None, timeout: float = 5, today: str | date | None = None,
) -> dict[str, Any]:
    """Verify individual jobs from a bounded 104 company listing and details.

    104 encodes its numeric employer ID (official UBN + 000) in base 36 for
    company URLs. Neither the listing total nor an unverified row is a job
    count for the issuer; each admitted row has an exact company/detail receipt.
    """
    company = str(legal_name or "").strip()
    ubn = str(official_ubn or "").strip()
    short = str(official_short_name or "").strip()
    if (len(company) < 4 or any(ch in company for ch in ('"', '\n', '\r'))
            or not re.fullmatch(r"\d{8}", ubn) or int(ubn) <= 0):
        return _unavailable(company, "", "104 Company Jobs API", JOB_104_API_URL,
                            "缺少可核對的官方公司全名或統編。", reason_code="issuer_unknown")
    try:
        current = date.fromisoformat(today) if isinstance(today, str) else today or datetime.now(ZoneInfo("Asia/Taipei")).date()
    except ValueError:
        return _unavailable(company, "", "104 Company Jobs API", JOB_104_API_URL,
                            "查詢日期無效。", reason_code="invalid_date")
    employer_id = str(int(ubn)) + "000"
    slug = _base36(int(employer_id))
    company_url = f"https://www.104.com.tw/company/{slug}"
    source_url = f"https://www.104.com.tw/api/companies/{slug}/jobs"
    headers = {**DEFAULT_HEADERS, "Accept": "application/json", "Referer": company_url}
    rows = []
    rejected = 0
    digests = []
    total_count = 0
    total_pages = 0
    try:
        response = _get_job_search_response(source_url, params={}, headers=headers,
                                            timeout=timeout, provider="104 Company Jobs API", session=session)
        raw = str(response.text or "")
        if not 0 < len(raw.encode("utf-8")) <= 300_000:
            raise ValueError("104 company listing response size invalid")
        payload = json.loads(raw)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not all(type(data.get(k)) is int for k in
                                                ("totalCount", "totalPages", "page", "pageSize")):
            raise ValueError("104 company listing metadata invalid")
        total_count, total_pages = data["totalCount"], data["totalPages"]
        if (not 0 <= total_count <= 100_000 or not 0 <= total_pages <= 10_000
                or data["page"] != 1 or not 1 <= data["pageSize"] <= 100
                or (total_count == 0) != (total_pages == 0)):
            raise ValueError("104 company listing pagination inconsistent")
        listing = data.get("list")
        if not isinstance(listing, dict):
            raise ValueError("104 company listing jobs invalid")
        top, normal = listing.get("topJobs"), listing.get("normalJobs")
        if not isinstance(top, list) or not isinstance(normal, list) or len(top) + len(normal) > 100:
            raise ValueError("104 company listing jobs invalid")
        digests.append(hashlib.sha256(raw.encode("utf-8")).hexdigest())
        seen = set()
        for item in (top + normal)[:JOB_104_COMPANY_SAMPLE_JOBS]:
            if not isinstance(item, dict):
                rejected += 1
                continue
            job_slug = str(item.get("jobNo") or "").strip()
            title = str(item.get("jobName") or "").strip()
            job_url = f"https://www.104.com.tw/job/{job_slug}"
            listed_date = str(item.get("appearDate") or "").strip()
            if (not re.fullmatch(r"[a-z0-9]{3,12}", job_slug) or not title
                    or item.get("jobUrl") != job_url or not re.fullmatch(r"\d{1,2}/\d{1,2}", listed_date)
                    or job_slug in seen):
                rejected += 1
                continue
            seen.add(job_slug)
            if session is None and len(seen) > 1:
                time.sleep(0.5)
            detail_url = f"https://www.104.com.tw/job/ajax/content/{job_slug}"
            detail = _get_job_search_response(detail_url, params={},
                                              headers={**headers, "Referer": job_url},
                                              timeout=timeout, provider="104 Job Detail", session=session)
            detail_raw = str(detail.text or "")
            if not 0 < len(detail_raw.encode("utf-8")) <= 150_000:
                raise ValueError("104 job detail response size invalid")
            detail_payload = json.loads(detail_raw)
            detail_data = detail_payload.get("data") if isinstance(detail_payload, dict) else None
            header = detail_data.get("header") if isinstance(detail_data, dict) else None
            digests.append(hashlib.sha256(detail_raw.encode("utf-8")).hexdigest())
            if not isinstance(header, dict):
                rejected += 1
                continue
            source_employer = str(header.get("custName") or "").strip()
            try:
                published = datetime.strptime(str(header.get("appearDate") or ""), "%Y/%m/%d").date()
                listed_month, listed_day = (int(part) for part in listed_date.split("/"))
            except ValueError:
                rejected += 1
                continue
            if (detail_data.get("custNo") != slug or header.get("custUrl") != company_url
                    or header.get("jobName") != title
                    or not _official_104_employer_label(company, short, source_employer)
                    or (listed_month, listed_day) != (published.month, published.day)
                    or not timedelta(0) <= current - published <= timedelta(days=30)):
                rejected += 1
                continue
            rows.append({"title": title, "url": job_url, "published_date": published.isoformat(),
                         "employer": company, "source_employer": source_employer,
                         "employer_match_basis": "official_name_ubn_company_api",
                         "employer_id": employer_id, "source_employer_id": slug,
                         "job_no": str(int(job_slug, 36)), "source_job_no": job_slug})
    except (_JobSearchTransportError, ValueError, TypeError, AttributeError):
        return _unavailable(company, "", "104 Company Jobs API", source_url,
                            "104 公司清單或職缺詳情未完整驗證。", reason_code="company_api_unverified")
    if not rows:
        return {**_unavailable(company, "", "104 Company Jobs API", source_url,
                              "公司清單沒有已核對的近期職缺；不能推定零職缺。",
                              reason_code="no_verified_postings"), "recent_company_job_count": None,
                "rejected_count": rejected}
    return {
        "status": "success", "company_name": company, "keyword": None, "job_count": None,
        "recent_company_job_count": len(rows), "job_postings": rows,
        "query_scope": "exact_company_recent_postings", "evidence_kind": "company_job_postings",
        "source": "104 Company Jobs API", "source_url": source_url,
        "response_sha256": hashlib.sha256("|".join(digests).encode()).hexdigest(),
        "page_count": total_pages, "searched_page_count": 1,
        "pagination_truncated": total_count > len(rows), "rejected_count": rejected,
        "coverage_status": "bounded_company_recent_postings_sample",
        "message": "僅計入官方統編對應公司清單、逐筆詳情之雇主、連結與日期皆核對的近期職缺樣本；不是完整職缺總數。",
    }


def fetch_104_job_openings_count(
    company_name: str,
    keyword: str,
    *,
    session: Any | None = None,
    timeout: float = 15,
    company_context: dict | None = None,
    fallback_memo: dict | None = None,
) -> dict[str, Any]:
    """Search 104 job listings and return the total job count only. Includes fallback to Google News."""
    company = str(company_name or "").strip()
    term = str(keyword or "").strip()
    if not company or not term:
        return _unavailable(company, term, "104 Job Search", JOB_104_SEARCH_URL, "公司名稱與關鍵字都必須提供。")

    query = f"{company} {term}".strip()
    params = {"keyword": query, "order": "15", "jobsource": "stock_agent"}
    source_url = f"{JOB_104_SEARCH_URL}?{urlencode(params)}"
    headers = {**DEFAULT_HEADERS, "Referer": JOB_104_SEARCH_URL}
    try:
        response = _get_job_search_response(
            JOB_104_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=timeout,
            provider="104 Job Search",
            session=session,
        )
        diagnostic = _job_page_diagnostics(response)
        blocked = _blocked_job_page(company, term, "104 Job Search", source_url, diagnostic)
        if blocked:
            return _google_news_fallback(company, term, blocked["source"], source_url,
                                         primary=blocked, company_context=company_context, fallback_memo=fallback_memo)
        job_count = _extract_104_job_count(response.text)
        if job_count is None:
            primary = _unavailable(company, term, "104 Job Search", source_url,
                                   "104 搜尋頁未揭露可解析的職缺總數。",
                                   reason_code="parse_failure", diagnostics=diagnostic)
            return _google_news_fallback(company, term, "104 Job Search", source_url,
                                         primary=primary, company_context=company_context, fallback_memo=fallback_memo)

        return {
            **diagnostic,
            "status": "success",
            "company_name": company,
            "keyword": term,
            "job_count": int(job_count),
            "evidence_kind": "job_count",
            "result_kind": "valid_empty" if job_count == 0 else "numeric_count",
            "source": "104 Job Search",
            "source_url": source_url,
        }
    except _JobSearchTransportError:
        # Fallback on HTTP and connection errors.
        return _google_news_fallback(company, term, "104 Job Search", source_url,
                                     company_context=company_context, fallback_memo=fallback_memo)


def fetch_1111_job_openings_count(
    company_name: str,
    keyword: str,
    *,
    session: Any | None = None,
    timeout: float = 15,
    company_context: dict | None = None,
    fallback_memo: dict | None = None,
) -> dict[str, Any]:
    """Search 1111 job listings and return the total job count. Includes fallback to Google News."""
    company = str(company_name or "").strip()
    term = str(keyword or "").strip()
    if not company or not term:
        return _unavailable(company, term, "1111 Job Search", JOB_1111_SEARCH_URL, "公司名稱與關鍵字都必須提供。")

    query = f"{company} {term}".strip()
    params = {"ks": query}
    source_url = f"{JOB_1111_SEARCH_URL}?{urlencode(params)}"
    try:
        response = _get_job_search_response(
            JOB_1111_SEARCH_URL,
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            provider="1111 Job Search",
            session=session,
        )
        diagnostic = _job_page_diagnostics(response)
        blocked = _blocked_job_page(company, term, "1111 Job Search", source_url, diagnostic)
        if blocked:
            return _google_news_fallback(company, term, blocked["source"], source_url,
                                         primary=blocked, company_context=company_context, fallback_memo=fallback_memo)
        job_count = _extract_1111_job_count(response.text)
        if job_count is None:
            primary = _unavailable(company, term, "1111 Job Search", source_url,
                                   "1111 搜尋頁未揭露可解析的職缺總數。", reason_code="parse_failure", diagnostics=diagnostic)
            return _google_news_fallback(company, term, "1111 Job Search", source_url,
                                         primary=primary, company_context=company_context, fallback_memo=fallback_memo)
            
        return {
            **diagnostic,
            "status": "success",
            "company_name": company,
            "keyword": term,
            "job_count": int(job_count),
            "evidence_kind": "job_count",
            "result_kind": "valid_empty" if job_count == 0 else "numeric_count",
            "source": "1111 Job Search",
            "source_url": source_url,
        }
    except _JobSearchTransportError:
        return _google_news_fallback(company, term, "1111 Job Search", source_url,
                                     company_context=company_context, fallback_memo=fallback_memo)


def recruitment_company_name(company: str, data: dict | None = None) -> str:
    """Choose an issuer anchor, never the bilingual UI display string."""
    from company_news_queries import company_search_name
    from source_content_selection import company_aliases
    context = {**(data or {})}
    context.setdefault("company_name", company)
    verified = company_search_name(context)
    if str(context.get('ticker') or '').strip().upper() == '5314.TWO':
        return verified
    identity = context.get("company_identity") or {}
    identity = identity if isinstance(identity, dict) else {}
    allowed = company_aliases(context)
    for candidate in (identity.get("official_name"), str(company).split(" / ")[0], *allowed):
        name = str(candidate or "").strip().strip("*").strip()
        if name.casefold() in allowed:
            return name
    return ""


def unique_recruitment_records(records: list[dict]) -> list[dict]:
    """Count a repeated URL or headline once across keywords and primary sites."""
    from news_record_utils import canonical_link, clean_text
    result, links, titles = [], set(), set()
    for item in records:
        if not isinstance(item, dict):
            continue
        link = canonical_link(item.get("link") or item.get("url"))
        title = clean_text(item.get("title") or item.get("headline")).casefold()
        if not link or link in links or (title and title in titles):
            continue
        links.add(link)
        if title:
            titles.add(title)
        result.append(deepcopy(item))
    return result


def _acquire_recruitment_news(query: str, data: dict) -> dict:
    from news_fetchers import fetch_google_news_rss
    from news_record_utils import canonical_link, clean_text
    from source_content_selection import select_company_records

    raw_news = fetch_google_news_rss(query, limit=5)
    news, selection = select_company_records(raw_news, data)
    relevant, links, titles = [], set(), set()
    for item in news:
        text = ' '.join(str(item.get(k) or '') for k in ('title', 'summary', 'snippet', 'text'))
        link = canonical_link(item.get('link') or item.get('url'))
        title = clean_text(item.get('title') or item.get('headline')).casefold()
        reason = ('recruitment_topic_unverified' if not re.search(r'徵才|擴編|招募|招聘|招聘會|hiring|recruit', text, re.I)
                  else 'duplicate' if link in links or (title and title in titles) else '')
        if reason:
            selection['source_record_archive'].append({'reason': reason, 'record': item})
            reasons = selection['rejected_reason_counts']
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        links.add(link)
        if title:
            titles.add(title)
        item['content_coverage'] = 'headline_or_snippet'
        relevant.append(item)
    selection.update(usable_count=len(relevant), rejected_count=len(selection['source_record_archive']),
                     quality_status='eligible_evidence' if relevant else 'no_eligible_evidence',
                     coverage_status='partial', recent_recruitment_news=relevant,
                     fallback_status='qualitative_only' if relevant else 'no_eligible_evidence' if raw_news else 'empty_unknown')
    return selection


def _google_news_fallback(company: str, keyword: str, source_name: str, source_url: str,
                          *, primary: dict | None = None, company_context: dict | None = None,
                          fallback_memo: dict | None = None) -> dict[str, Any]:
    """Retain the primary failure and recover only verified recruitment evidence."""
    from source_content_selection import company_aliases
    data = {**(company_context or {})}
    data.setdefault('company_name', company)
    primary = deepcopy(primary) if primary else _unavailable(
        company, keyword, source_name, source_url, '職缺頁取得失敗；職缺數未知。', reason_code='transport_failure')
    anchor = recruitment_company_name(company, data)
    # The occupational keyword is metadata, not a mandatory AND condition on news.
    query = f'"{anchor}" (徵才 OR 擴編 OR 招募 OR hiring OR recruitment) when:30d' if anchor else ''
    identity = data.get('company_identity') or {}
    identity = identity if isinstance(identity, dict) else {}
    key = json.dumps([data.get('ticker'), sorted(company_aliases(data)),
                      sorted(str(v) for v in (identity.get('forbidden_aliases') or [])), query], ensure_ascii=False)
    if fallback_memo is not None and key in fallback_memo:
        selection = deepcopy(fallback_memo[key])
    else:
        try:
            selection = _acquire_recruitment_news(query, data) if query else {'fallback_status': 'issuer_unknown'}
        except ImportError:
            selection = {'fallback_status': 'not_configured'}
        except Exception:
            selection = {'fallback_status': 'error'}
        if fallback_memo is not None:
            fallback_memo[key] = deepcopy(selection)
    news = selection.get('recent_recruitment_news') or []
    reason = primary.get('reason_code') or 'transport_failure'
    result = {**primary, **selection, 'primary_status': primary['status'], 'primary_provider': source_name,
              'reason_code': reason, 'fallback_reason': reason, 'job_count': None,
              'coverage_status': 'partial' if news else 'unavailable'}
    if news:
        result.update(status='success', evidence_kind='recruitment_news', result_kind='qualitative_only',
                      actual_provider='Google News RSS', source=f'{source_name} (Fallback to News)',
                      source_url=None, requested_source_url=source_url,
                      message='職缺數未知；新聞備援僅提供已核對公司與日期的招募情報。')
    return result


def _job_page_diagnostics(response) -> dict:
    """Classify the public response before interpreting any embedded count."""
    html = str(response.text or '')
    soup = BeautifulSoup(html, 'html.parser')
    scripts = bool(soup.find('script'))
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    for node in soup(['script', 'style', 'noscript', 'title']):
        node.decompose()
    visible = soup.get_text(' ', strip=True)
    blocked = re.search(r'背景驗證中|安全驗證失敗|驗證您是否為真人|verify you are human|access denied|checking your browser|just a moment', title + ' ' + visible, re.I)
    kind = 'challenge' if blocked else 'normal_or_unknown'
    if not blocked and scripts and not visible and ('104' in title or '1111' in title):
        kind = 'client_rendered_shell'
    return {'page_kind': kind, 'http_status': getattr(response, 'status_code', None),
            'response_sha256': hashlib.sha256(html.encode()).hexdigest(),
            'response_bytes': len(html.encode()), 'parser_version': 'job-search-v2'}


def _blocked_job_page(company, keyword, source_name, source_url, diagnostics):
    kind = diagnostics['page_kind']
    if kind == 'challenge':
        return _unavailable(company, keyword, source_name, source_url,
                            '職缺來源回傳存取驗證頁，職缺數未知。',
                            reason_code='access_denied', diagnostics=diagnostics)
    if kind == 'client_rendered_shell':
        return _unavailable(company, keyword, source_name, source_url,
                            '職缺頁僅提供前端載入框架，未取得職缺總數。',
                            reason_code='client_rendered', diagnostics=diagnostics)
    return None


def _extract_104_job_count(html: str) -> int | None:
    if not html:
        return None
    patterns = (
        r'"totalCount"\s*:\s*"?([0-9,]+)"?',
        r'"total_count"\s*:\s*"?([0-9,]+)"?',
        r"共\s*([0-9,]+)\s*筆(?:工作機會|職缺|工作)?",
        r"([0-9,]+)\s*個工作機會",
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return _parse_count(match.group(1))

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    for pattern in patterns[2:]:
        match = re.search(pattern, text)
        if match:
            return _parse_count(match.group(1))
    return None


def _extract_1111_job_count(html: str) -> int | None:
    if not html:
        return None
    patterns = (
        r'共\s*([0-9,]+)\s*筆',
        r'([0-9,]+)\s*個工作機會',
        r'"totalCount"\s*:\s*"?([0-9,]+)"?',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return _parse_count(match.group(1))
    return None


def _parse_count(value: str) -> int | None:
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _unavailable(
    company_name: str,
    keyword: str,
    source_name: str,
    source_url: str,
    message: str,
    *, reason_code: str = "invalid_query", fallback_status: str | None = None, diagnostics: dict | None = None,
) -> dict[str, Any]:
    return {
        **(diagnostics or {}),
        "status": "unavailable",
        "company_name": company_name,
        "keyword": keyword,
        "job_count": None,
        "evidence_kind": "unavailable",
        "reason_code": reason_code,
        "fallback_status": fallback_status,
        "message": message,
        "source": source_name,
        "source_url": source_url,
    }
