"""Allowlisted company IR acquisition, pending live parser verification.

The initial issuer endpoints returned access denied in deployment-host probes.
This adapter is deliberately disabled in the workflow until a real document is
verified. Search snippets are never accepted as article contents.
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from external_http_client import sync_get
from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                     record_observation, remember_failure, scope_key)
from shared_provider_cache import shared_fetch

PROVIDER = 'Company IR documents'
PARSER_VERSION = 'company-ir-v1'
MAX_ARTICLES = 2
MAX_DOCUMENTS = 12
MAX_TEXT_CHARS = 12000
COVERAGE_NOTE = '僅涵蓋已設定公司的公開文件；未取得文字的連結只作索引，不能視為全文或法說逐字稿。'
LIVE_VERIFICATION = 'blocked_access_denied'
ISSUERS = {
    '2330.TW': {
        'name': 'Taiwan Semiconductor Manufacturing Company',
        'identity': ('tsmc', 'taiwan semiconductor manufacturing'),
        'index_url': 'https://pr.tsmc.com/english/latest-news',
        'host': 'pr.tsmc.com',
        'article_path': r'/english/news/\d+/?',
        'index_markers': ('latest news',),
    },
    '3702.TW': {
        'name': 'WPG Holdings', 'identity': ('wpg',),
        'index_url': 'https://www.wpgholdings.com/investors_msg/index/en',
        'host': 'www.wpgholdings.com',
        'article_path': r'/investors_msg/(?:detail|view)/en/[A-Za-z0-9_-]+/?',
        'index_markers': ('material announcement', 'financial news'),
    },
}


def _today() -> date:
    return datetime.now(ZoneInfo('Asia/Taipei')).date()


def _ticker(value: str) -> str:
    return str(value or '').strip().upper()


def allowed_ir_url(value: str, ticker: str) -> str:
    """No foreign host, credentials, query redirects, fragment or arbitrary path."""
    issuer = ISSUERS.get(_ticker(ticker))
    if not issuer or not isinstance(value, str) or len(value) > 2048 or re.search(r'[\s\\<>]', value):
        return ''
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.hostname != issuer['host'] or parsed.username
                or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment):
            return ''
        if value != issuer['index_url'] and not re.fullmatch(issuer['article_path'], parsed.path):
            return ''
        return urlunsplit(('https', issuer['host'], parsed.path, '', ''))
    except ValueError:
        return ''


def _soup(html: str) -> BeautifulSoup:
    if not isinstance(html, str) or len(html.encode()) > 2_000_000:
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True).lower() if soup.title else ''
    if (any(token in title for token in ('just a moment', 'access denied', 'forbidden', 'login', 'sign in'))
            or soup.find('input', attrs={'type': 'password'})):
        raise SourceResponseError('access_denied', status_code=200, parser_version=PARSER_VERSION)
    for node in soup.select('script, style, nav, header, footer, aside, noscript'):
        node.decompose()
    return soup


def _explicit_date(value: str) -> str | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    match = re.match(r'^(\d{4})[-/](\d{2})[-/](\d{2})(?:$|[ T])', raw)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups())).isoformat()
    except ValueError as exc:
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION) from exc


def _title(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def parse_ir_index(html: str, ticker: str, *, today: date | None = None) -> list[dict]:
    ticker = _ticker(ticker)
    issuer = ISSUERS.get(ticker)
    if not issuer:
        return []
    soup = _soup(html)
    full_text = soup.get_text(' ', strip=True).lower()
    if (not any(token in full_text for token in issuer['identity'])
            or not any(token in full_text for token in issuer['index_markers'])):
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    today = today or _today()
    documents, seen = [], set()
    candidate_count = 0
    for anchor in soup.select('a[href]'):
        url = allowed_ir_url(urljoin(issuer['index_url'], anchor['href']), ticker)
        if not url or url == issuer['index_url'] or url in seen:
            continue
        label = _title(anchor.get_text(' ', strip=True))
        if not label:
            continue
        candidate_count += 1
        # Publication dates come from each row, never from the fiscal quarter.
        published = _explicit_date(label)
        if not published:
            parent = anchor.find_parent(['li', 'tr', 'article'])
            if parent:
                time_node = parent.find('time')
                if time_node:
                    published = _explicit_date(time_node.get('datetime') or time_node.get_text(' ', strip=True))
                elif re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}', parent.get_text(' ', strip=True)):
                    published = _explicit_date(parent.get_text(' ', strip=True))
        if published and date.fromisoformat(published) > today:
            continue
        title = re.sub(r'^\d{4}[-/]\d{2}[-/]\d{2}\s*', '', label)[:400]
        if not title:
            continue
        seen.add(url)
        kind = 'financial_results' if any(token in title.lower() for token in ('results', 'revenue report', 'financial report')) else 'press_release'
        documents.append({
            'ticker': ticker, 'document_id': hashlib.sha256(f'{ticker}|{url}'.encode()).hexdigest(),
            'title': title, 'url': url, 'published_at': published,
            'source': issuer['name'], 'source_type': 'company_ir', 'document_kind': kind,
            'summary': '', 'coverage_status': 'metadata_only',
            'content_sha256': None, 'retrieved_at_epoch': None,
        })
    if not candidate_count and not re.search(r'\bno (?:results|records|news)(?: found)?\b', full_text):
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    return sorted(documents, key=lambda row: row.get('published_at') or '', reverse=True)[:MAX_DOCUMENTS]


def parse_ir_article(html: str, document: dict, *, today: date | None = None) -> dict:
    ticker = _ticker(document.get('ticker'))
    if not allowed_ir_url(document.get('url'), ticker):
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    soup = _soup(html)
    headline = soup.find('h1')
    if not headline or _title(headline.get_text(' ', strip=True)).casefold() != _title(document.get('title')).casefold():
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    body = soup.select_one('[itemprop="articleBody"], .field--name-body')
    if body is None:
        # Fail closed if the article has no unambiguous body container.
        body = soup.find('article')
        if body:
            for node in body.select('h1, time'):
                node.decompose()
    if body is None:
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    paragraphs = [_title(node.get_text(' ', strip=True)) for node in body.find_all(['p', 'tr'])]
    text = '\n'.join(part for part in paragraphs if part)
    if len(text) < 50:
        raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
    published = document.get('published_at')
    date_meta = soup.find('meta', attrs={'property': 'article:published_time'})
    if date_meta and date_meta.get('content'):
        explicit = _explicit_date(date_meta['content'])
        if explicit is None:
            raise SourceResponseError('parse_error', parser_version=PARSER_VERSION)
        published = explicit
    if published and date.fromisoformat(published) > (today or _today()):
        raise SourceResponseError('future_publication', parser_version=PARSER_VERSION)
    bounded = text[:MAX_TEXT_CHARS]
    return {**document, 'published_at': published, 'text': bounded, 'summary': bounded[:600],
            'content_sha256': hashlib.sha256(bounded.encode()).hexdigest(),
            'content_truncated': len(text) > len(bounded), 'coverage_status': 'text_available'}


def _endpoint_key(ticker: str, kind: str) -> str:
    return scope_key(PROVIDER, endpoint=f'{ticker}:{kind}')


def _acquire(url: str, ticker: str, kind: str, parser):
    if not allowed_ir_url(url, ticker):
        raise SourceResponseError('unsafe_url', parser_version=PARSER_VERSION)
    started = time.monotonic()
    key = _endpoint_key(ticker, kind)
    blocked = cooldown_state(key)
    if blocked:
        record_observation(PROVIDER, started, outcome='cooldown', source='company_ir', details=blocked, sent=False)
        error = SourceResponseError(blocked['error_kind'], status_code=blocked.get('http_status'), parser_version=PARSER_VERSION)
        error.diagnostic.update(blocked, http_request_sent=False, event_kind='local_block')
        raise error
    observe_http_response(None)
    try:
        # Shared client uses httpx's no-redirect default. Never follow Location.
        response = sync_get(url, timeout=(5, 12), provider=PROVIDER)
        observe_http_response(response)
        if 300 <= response.status_code < 400:
            raise SourceResponseError('redirect_rejected', status_code=response.status_code, parser_version=PARSER_VERSION)
        response.raise_for_status()
        if str(response.url) != url:
            raise SourceResponseError('redirect_rejected', status_code=response.status_code, parser_version=PARSER_VERSION)
        if 'text/html' not in response.headers.get('content-type', '').lower():
            raise SourceResponseError('parse_error', status_code=response.status_code, parser_version=PARSER_VERSION)
        result = parser(response.text)
    except Exception as original:
        details = remember_failure(key, original)
        details.update(http_request_sent=True, event_kind='http_attempt', parser_version=PARSER_VERSION)
        record_observation(PROVIDER, started, outcome='failure', source='company_ir', details=details)
        error = SourceResponseError(details['error_kind'], status_code=details.get('http_status'), parser_version=PARSER_VERSION)
        error.diagnostic.update(details)
        raise error from original
    record_observation(PROVIDER, started, outcome='results' if result else 'valid_empty',
                       count=len(result) if isinstance(result, list) else 1, source='company_ir',
                       details={'http_status': response.status_code, 'parser_version': PARSER_VERSION})
    return result


def fetch_company_ir_documents(ticker: str, *, force_refresh: bool = False) -> dict:
    ticker = _ticker(ticker)
    base = {'documents': [], 'actual_provider': PROVIDER, 'coverage_notes': [COVERAGE_NOTE],
            'live_verification': LIVE_VERIFICATION, 'observed_at_epoch': time.time()}
    issuer = ISSUERS.get(ticker)
    if not issuer:
        return {**base, 'status': 'unsupported', 'coverage_status': 'unsupported_issuer',
                'error_kind': 'unsupported_issuer', 'http_request_sent': False}
    captured = {}
    def fetch():
        try:
            documents = _acquire(issuer['index_url'], ticker, 'index', lambda html: parse_ir_index(html, ticker))
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
        components = {}
        for index, document in enumerate(documents[:MAX_ARTICLES]):
            try:
                documents[index] = _acquire(document['url'], ticker, 'article', lambda html: parse_ir_article(html, document))
            except SourceResponseError as exc:
                components['article'] = dict(exc.diagnostic)
                # Reject future article evidence, even if the index claimed a past date.
                if exc.error_kind == 'future_publication':
                    documents[index] = None
        acquired_at = time.time()
        documents = [{**doc, 'retrieved_at_epoch': acquired_at} for doc in documents if doc]
        return {'documents': documents, 'component_statuses': components}
    value, metadata = shared_fetch(
        f'{PARSER_VERSION}:{ticker}', fetch, freshness_seconds=3600,
        use_cache=not force_refresh,
        result_ttl=lambda result: 3600 if result['documents'] and not result['component_statuses'] else 300,
    )
    if metadata.get('error_kind'):
        details = {**metadata, **cooldown_state(_endpoint_key(ticker, 'index')), **captured}
        if not captured:
            details.update(http_request_sent=False, event_kind='local_block')
        return {**base, **details, 'status': 'unavailable', 'coverage_status': 'unavailable'}
    result = {**base, **value, **metadata, 'status': 'partial', 'coverage_status': 'partial'}
    if metadata.get('cache_hit'):
        result['http_request_sent'] = False
        result['component_statuses'] = {
            name: {**detail, 'http_request_sent': False, 'event_kind': 'cache_hit'}
            for name, detail in result['component_statuses'].items()
        }
    # Index persistence is an optimization; failed indexing must not lose evidence.
    if result['documents']:
        try:
            from source_document_index import upsert_source_documents
            result['index_result'] = upsert_source_documents(result['documents'], observed_at_epoch=metadata['fetched_at_epoch'])
        except Exception:
            result['index_status'] = 'unavailable'
    return result
