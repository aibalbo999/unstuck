"""Alternative data fetchers used to validate company expansion signals."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from external_http_client import sync_get

JOB_104_SEARCH_URL = "https://www.104.com.tw/jobs/search/"
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
    try:
        if session is not None:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        return sync_get(url, params=params, headers=headers, timeout=timeout, provider=provider)
    except Exception as exc:
        raise _JobSearchTransportError from exc


def fetch_104_job_openings_count(
    company_name: str,
    keyword: str,
    *,
    session: Any | None = None,
    timeout: float = 15,
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
            return blocked
        job_count = _extract_104_job_count(response.text)
        if job_count is None:
            return _unavailable(
                company,
                term,
                "104 Job Search",
                source_url,
                "104 搜尋頁未揭露可解析的職缺總數。",
                reason_code="parse_failure", diagnostics=diagnostic,
            )

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
        return _google_news_fallback(company, term, "104 Job Search", source_url)


def fetch_1111_job_openings_count(
    company_name: str,
    keyword: str,
    *,
    session: Any | None = None,
    timeout: float = 15,
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
            return blocked
        job_count = _extract_1111_job_count(response.text)
        if job_count is None:
            return _unavailable(company, term, "1111 Job Search", source_url, "1111 搜尋頁未揭露可解析的職缺總數。", reason_code="parse_failure", diagnostics=diagnostic)
            
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
        return _google_news_fallback(company, term, "1111 Job Search", source_url)


def _google_news_fallback(company: str, keyword: str, source_name: str, source_url: str) -> dict[str, Any]:
    """Uses Google News RSS to find recent recruitment news when direct scraping fails."""
    try:
        from news_fetchers import fetch_google_news_rss
        query = f'{company} {keyword} (徵才 OR 擴編 OR 招募)'
        raw_news = fetch_google_news_rss(query, limit=5)
        from source_content_selection import select_company_records
        news, selection = select_company_records(raw_news, {'company_name': company})
        # A company news match alone is not recruitment evidence.
        relevant = []
        for item in news:
            text = ' '.join(str(item.get(k) or '') for k in ('title', 'summary', 'snippet', 'text'))
            if re.search(r'徵才|擴編|招募|招聘|招聘會|hiring|recruit', text, re.I):
                item['content_coverage'] = 'headline_or_snippet'
                relevant.append(item)
            else:
                selection['source_record_archive'].append({'reason': 'recruitment_topic_unverified', 'record': item})
                reasons = selection['rejected_reason_counts']
                reasons['recruitment_topic_unverified'] = reasons.get('recruitment_topic_unverified', 0) + 1
        news = relevant
        selection.update(usable_count=len(news), rejected_count=len(selection['source_record_archive']),
                         quality_status='eligible_evidence' if news else 'no_eligible_evidence',
                         coverage_status='partial' if len(news) != len(raw_news or []) or not news else 'success')
        if news:
            return {
                **selection,
                "status": "success",
                "company_name": company,
                "keyword": keyword,
                "job_count": None,
                "evidence_kind": "recruitment_news",
                "result_kind": "qualitative_only",
                "fallback_reason": "transport_failure",
                "actual_provider": "Google News RSS",
                "recent_recruitment_news": news,
                "source": f"{source_name} (Fallback to News)",
                "source_url": None,
                "requested_source_url": source_url,
                "message": "職缺頁取得失敗；新聞備援僅提供招募情報，無法確認職缺總數。"
            }
        else:
            return _unavailable(company, keyword, source_name, source_url, "職缺頁取得失敗且新聞備援無結果；職缺數未知。", reason_code="transport_failure", fallback_status="no_eligible_evidence" if raw_news else "empty_unknown", diagnostics=selection)
    except ImportError:
        return _unavailable(company, keyword, source_name, source_url, "職缺頁取得失敗且新聞備援未設定。", reason_code="transport_failure", fallback_status="not_configured")
    except Exception:
        return _unavailable(company, keyword, source_name, source_url, "職缺頁與新聞備援均取得失敗。", reason_code="transport_failure", fallback_status="error")


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
