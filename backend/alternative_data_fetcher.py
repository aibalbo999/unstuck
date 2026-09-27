"""Alternative data fetchers used to validate company expansion signals."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
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
    from source_content_selection import company_aliases
    context = {**(data or {})}
    context.setdefault("company_name", company)
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
