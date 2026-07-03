"""Alternative data fetchers used to validate company expansion signals."""

from __future__ import annotations

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
        job_count = _extract_104_job_count(response.text)
        if job_count is None:
            return _unavailable(
                company,
                term,
                "104 Job Search",
                source_url,
                "104 搜尋頁未揭露可解析的職缺總數。",
            )

        return {
            "status": "success",
            "company_name": company,
            "keyword": term,
            "job_count": int(job_count),
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
        job_count = _extract_1111_job_count(response.text)
        if job_count is None:
            # Fallback
            return _google_news_fallback(company, term, "1111 Job Search", source_url)
            
        return {
            "status": "success",
            "company_name": company,
            "keyword": term,
            "job_count": int(job_count),
            "source": "1111 Job Search",
            "source_url": source_url,
        }
    except Exception as exc:
        return _google_news_fallback(company, term, "1111 Job Search", source_url)


def _google_news_fallback(company: str, keyword: str, source_name: str, source_url: str) -> dict[str, Any]:
    """Uses Google News RSS to find recent recruitment news when direct scraping fails."""
    try:
        from news_fetchers import fetch_google_news_rss
        query = f'{company} {keyword} 徵才 OR 擴編 OR 招募'
        news = fetch_google_news_rss(query, limit=5)
        if news:
            return {
                "status": "success",
                "company_name": company,
                "keyword": keyword,
                "job_count": None,  # Qualitative data only
                "recent_recruitment_news": news,
                "source": f"{source_name} (Fallback to News)",
                "source_url": source_url,
                "message": "直接爬取遭阻擋，已啟用新聞聚合備援，回傳近期招募情報。"
            }
        else:
            return _unavailable(company, keyword, source_name, source_url, "網站遭阻擋且無相關招募新聞。")
    except ImportError:
        return _unavailable(company, keyword, source_name, source_url, "網站遭阻擋，且未安裝新聞模組無法備援。")


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
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "company_name": company_name,
        "keyword": keyword,
        "job_count": None,
        "message": message,
        "source": source_name,
        "source_url": source_url,
    }
