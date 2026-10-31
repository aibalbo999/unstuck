"""First-page TCFHC parent statements, with complete original-byte replay."""
from __future__ import annotations

import base64
from collections import Counter
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import math
import re
import time
import zlib
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from search_provider_runtime import SourceResponseError
from .tcfhc_annual_transport import MASTER_URL as MASTER, parse_master
from .tcfhc_conference_transport import ConferenceHttp, RAW_TTL, original_bytes

TICKER = '5880.TW'
LEGAL = '合作金庫金融控股股份有限公司'
UBN = '53021433'
PUBLISHER = 'TCFHC'
POLICY = 'tcfhc-public-parent-first-page-news-originals-v1'
HOST = 'https://www.tcfhc.com.tw'
INDEX_ROOT = HOST + '/news/message/news/'
INDEX = INDEX_ROOT + '2026'
TAIPEI = ZoneInfo('Asia/Taipei')
ARTICLE = re.compile(re.escape(INDEX_ROOT) + r'(20\d{2})/(\d{8}|\d{3}-\d{7})\Z')
PARENTS = ('合庫金控', '合作金庫金控', LEGAL)
CHILDREN = ('合庫銀行', '合作金庫銀行', '合作金庫商業銀行', '合庫人壽', '合作金庫人壽',
            '合庫證券', '合庫票券', '合庫資產管理', '合庫投信')
_ERRORS = (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError,
           OverflowError, zlib.error, SourceResponseError)


def url_contract(url):
    if url == MASTER:
        return 2_500_000, {'text/csv', 'application/csv', 'application/octet-stream'}
    if isinstance(url, str) and re.fullmatch(re.escape(INDEX_ROOT) + r'20\d{2}', url):
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if isinstance(url, str) and ARTICLE.fullmatch(url):
        _url_day(url)
        return 500_000, {'text/html', 'application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')


def _url_day(url):
    match = ARTICLE.fullmatch(url)
    if not match:
        raise SourceResponseError('transport_url_invalid')
    year, slug = match.groups()
    try:
        stamp = slug.split('-')[-1]
        observed = (date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:])) if len(stamp) == 8
                    else date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:])))
        if observed.year != int(year):
            raise ValueError('year mismatch')
        return observed
    except ValueError as exc:
        raise SourceResponseError('transport_url_invalid') from exc


class NewsHttp(ConferenceHttp):
    """Share TCFHC's existing per-URL admission/error cache and host cooldown."""
    route_contract = staticmethod(url_contract)

    def download_original(self, url, diagnostic):
        try:
            value = super().download_original(url, diagnostic)
        except SourceResponseError as exc:
            if exc.status_code is not None:
                diagnostic.update(http_status=exc.status_code, http_status_observed=True, request_method='GET')
            raise
        diagnostic.update(http_status=200, http_status_observed=True, request_method='GET')
        raw = base64.b64decode(value['body_b64'], validate=True)
        if url != MASTER and not raw.rstrip().lower().endswith(b'</html>'):
            raise SourceResponseError('response_invalid', status_code=200)
        return value


def _clean(value):
    if hasattr(value, 'get_text'):
        value = value.get_text(' ', strip=True)
    return re.sub(r'\s+', ' ', str(value)).strip()


def validate_context(data, ticker=TICKER):
    if not isinstance(data, dict) or ticker != TICKER or data.get('ticker') != ticker:
        return False
    identity = data.get('company_identity')
    if identity is None:
        identity = {}
    if not isinstance(identity, dict):
        return False
    expected = {'ticker': TICKER, 'stock_id': '5880', 'official_name': '合庫金', 'legal_name': LEGAL,
                'official_ubn': UBN, 'instrument_type': 'EQUITY'}
    if any(identity.get(k) not in (None, '', v) for k, v in expected.items()):
        return False
    if (data.get('stock_id') not in (None, '', '5880')
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('quote_type', 'quoteType', 'instrument_type'))):
        return False
    aliases = {'合庫金', *PARENTS, 'tcfhc', 'taiwan cooperative financial holding co., ltd.',
               'taiwan cooperative financial holding co. ltd.'}
    if data.get('company_name') is not None:
        name = data['company_name']
        if (not isinstance(name, str) or not name
                or any(v.strip().casefold() not in aliases for v in name.split(' / '))):
            return False
    for key in ('allowed_aliases', 'english_names', 'forbidden_aliases'):
        values = identity.get(key, [])
        if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) for v in values):
            return False
        if key != 'forbidden_aliases' and any(any(c in v for c in CHILDREN) for v in values):
            return False
    if aliases & {v.strip('* ').casefold() for v in identity.get('forbidden_aliases', [])}:
        return False
    return True


def _page(raw, url):
    limit, _ = url_contract(url)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= limit or not raw.rstrip().lower().endswith(b'</html>'):
        raise ValueError('tcfhc_news_complete_html_invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    urls = soup.select('meta[property="og:url"]')
    titles = soup.select('meta[property="og:title"]')
    owners = soup.select('.c-terms__copyright')
    if (not soup.html or soup.html.get('lang') != 'zh-Hant-TW' or not soup.title
            or len(urls) != 1 or urls[0].get('content') != url or len(titles) != 1
            or _clean(soup.title) != _clean(titles[0].get('content', ''))
            or len(owners) != 1 or _clean(owners[0]) != '©合作金庫金控版權所有'
            or len(soup.select('main#main')) != 1):
        raise ValueError('tcfhc_news_publisher_or_native_metadata_invalid')
    return soup


def parse_index(raw, index_url=INDEX):
    soup = _page(raw, index_url)
    year = int(index_url.rsplit('/', 1)[-1])
    heads = soup.select('main#main h2.o-pageTitle')
    lists = soup.select('main#main section[data-tc-announcement] ul.c-list--ann')
    active = soup.select('main#main .c-pager__num.is-active')
    if (len(heads) != 1 or _clean(heads[0]) != f'{year}年新聞列表'
            or _clean(soup.title) != '合庫金控官方網站' or len(lists) != 1
            or len(active) != 1 or active[0].get('data-pagination-number') != '1'
            or _clean(active[0]) != '1' or not lists[0].get('data-pagination-for')
            or active[0].get('data-pagination-for') != lists[0]['data-pagination-for']):
        raise ValueError('tcfhc_news_index_role_invalid')
    cards = lists[0].select(':scope > li.c-list__item')
    if len(cards) > 10:
        raise ValueError('tcfhc_news_first_page_count_invalid')
    rows, seen = [], set()
    for card in cards:
        titles = card.select('.c-list__title'); dates = card.select('.c-list__date')
        links = card.select('.c-list__link a[href]')
        if not len(titles) == len(dates) == len(links) == 1:
            raise ValueError('tcfhc_news_index_fields_invalid')
        title, stamp = _clean(titles[0]), _clean(dates[0])
        href = links[0]['href']; url = HOST + href if href.startswith('/news/message/news/') else href
        day = _url_day(url)
        if (not title or len(title) > 500 or stamp != day.isoformat() or day.year != year
                or _clean(links[0].get('title', '')) != '前往' + title
                or _clean(links[0]) != '查看' or url in seen):
            raise ValueError('tcfhc_news_index_publication_mismatch')
        seen.add(url)
        rows.append({'url': url, 'title': title, 'date_original': stamp, 'index_url': index_url,
                     'original_id': url.rsplit('/', 1)[-1], 'category': '新聞中心',
                     'explicit_child_title': any(c in title for c in CHILDREN) and not any(p in title for p in PARENTS)})
    return rows


def parse_article(raw, listed):
    soup = _page(raw, listed['url'])
    titles = soup.select('main#main h2.o-pageTitle')
    dates = soup.select('main#main .l-postInfo__head > span')
    blocks = soup.select('main#main section[data-tc-announcement] .l-textBlock__text')
    backs = soup.select('main#main .c-breadcrumbs a[href="' + listed['index_url'].removeprefix(HOST) + '"]')
    if not len(titles) == len(dates) == len(blocks) == len(backs) == 1:
        raise ValueError('tcfhc_news_article_fields_invalid')
    if (_clean(titles[0]) != listed['title'] or _clean(soup.title) != listed['title']
            or _clean(dates[0]) != listed['date_original'] or _url_day(listed['url']).isoformat() != listed['date_original']
            or _clean(backs[0]) != f'{_url_day(listed["url"]).year}年新聞列表'
            or blocks[0].find(['script', 'iframe', 'object', 'form', 'video'])):
        raise ValueError('tcfhc_news_article_publication_mismatch')
    body = _clean(blocks[0])
    paragraphs = [x.strip() for x in blocks[0].get_text('\n', strip=True).splitlines() if x.strip()]
    if not 80 <= len(body) <= 12000 or not paragraphs:
        raise ValueError('tcfhc_news_full_article_body_invalid')
    # A dual-role chairperson later in a bank story is not a parent event.
    lead = paragraphs[0]
    parents = [lead.find(p) for p in PARENTS if p in lead]
    children = [lead.find(c) for c in CHILDREN if c in lead]
    parent = bool(parents) and (not children or min(parents) < min(children)) and not listed['explicit_child_title']
    return listed['title'], body, parent


def _read(proof, url):
    return original_bytes(proof, url, max_age=100 * 366 * 86400, url_contract=url_contract)


def _identity(raw, epoch):
    observed = datetime.fromtimestamp(epoch, TAIPEI).date()
    identity = parse_master(raw, today=observed)
    if date.fromisoformat(identity['master_as_of']) > observed:
        raise ValueError('tcfhc_news_master_postdates_acquisition')
    return {**identity, 'master_source_url': MASTER, 'market': 'TWSE'}


def _record(identity, listed, title, body, proofs):
    proof_digest = sha256(json.dumps(proofs, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return {'ticker': TICKER, 'title': title, 'text': body, 'summary': body[:280], 'date': listed['date_original'],
            'link': listed['url'], 'source_document_url': listed['url'], 'source': '合庫金控官方新聞',
            'publisher': PUBLISHER, 'source_type': 'first_party_issuer_news', 'source_role': 'issuer_statement',
            'event_assessment': 'not_assessed', 'content_coverage': 'text_available', 'content_truncated': False,
            'publication_date_original': {'issuer_article_date': listed['date_original'], 'index_card_date': listed['date_original']},
            'publication_date_precision': 'day',
            'issuer_news_receipt': {**identity, 'policy': POLICY, 'original_id': listed['original_id'],
                'article_category': listed['category'], 'index_url': listed['index_url'],
                'article_identity_basis': 'published_URL_title_date_complete_body_explicit_parent_lead',
                'coverage_scope': 'first_page_only', 'window_complete': False,
                'index_response_sha256': proofs['index']['raw_response_sha256'],
                'article_response_sha256': proofs['article']['raw_response_sha256'],
                'original_receipts_sha256': proof_digest, 'source_record_archive': proofs}}


def verified_record(record, data, *, today):
    try:
        if not validate_context(data) or not isinstance(record, dict) or type(today) is not date:
            return None
        receipt = record['issuer_news_receipt']; proofs = receipt['source_record_archive']
        if not isinstance(proofs, dict) or set(proofs) != {'master', 'index', 'article'}:
            return None
        url = record['source_document_url']; day = _url_day(url)
        if not today - timedelta(days=30) <= day <= today:
            return None
        index_url = INDEX_ROOT + str(day.year)
        master = _read(proofs['master'], MASTER); index = _read(proofs['index'], index_url); article = _read(proofs['article'], url)
        identity = _identity(master, proofs['master']['retrieved_at'])
        listed = [r for r in parse_index(index, index_url) if r['url'] == url]
        if len(listed) != 1:
            return None
        title, body, parent = parse_article(article, listed[0])
        if not parent:
            return None
        published = datetime.combine(day, datetime.min.time(), TAIPEI).timestamp()
        if any(proofs[k]['retrieved_at'] < published for k in ('index', 'article')):
            return None
        expected = _record(identity, listed[0], title, body, proofs)
        from news_record_utils import parse_news_datetime
        published = parse_news_datetime(expected['date'])
        if (parse_news_datetime(record.get('date')) != published
                or 'published_date' in record and parse_news_datetime(record['published_date']) != published
                or any(record.get(k) != v for k, v in expected.items() if k != 'date')):
            return None
        return PUBLISHER
    except _ERRORS:
        return None


def fetch_recent_news(*, now, http=None):
    deadline = time.monotonic() + 20
    http = http or NewsHttp(deadline)
    today = now.astimezone(TAIPEI).date(); index_url = INDEX_ROOT + str(today.year)
    records, acquired, excluded = [], [], Counter()
    audit = {'selection_policy': POLICY, 'coverage_status': 'partial', 'coverage_scope': 'first_page_only',
             'window_complete': False, 'raw_count': 0, 'article_http_budget': 8}

    def check():
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')

    def get(url):
        check()
        raw, proof = http.get_receipt(url)
        if _read(proof, url) != raw:
            raise ValueError('tcfhc_news_archive_mismatch')
        acquired.append(proof)
        check()
        return raw, proof

    try:
        master, master_proof = get(MASTER)
        identity = _identity(master, master_proof['retrieved_at'])
        index, index_proof = get(index_url)
        rows = parse_index(index, index_url); audit['raw_count'] = len(rows)
        candidates = []
        for row in rows:
            day = date.fromisoformat(row['date_original'])
            if row['explicit_child_title']:
                excluded['explicit_subsidiary_title'] += 1
            elif day > today:
                excluded['future'] += 1
            elif day < today - timedelta(days=30):
                excluded['historical'] += 1
            else:
                candidates.append(row)
        candidates.sort(key=lambda r: r['date_original'], reverse=True)
        excluded['article_budget'] += max(0, len(candidates) - 8)
        for row in candidates[:8]:
            article, article_proof = get(row['url'])
            title, body, parent = parse_article(article, row)
            if not parent:
                excluded['not_explicit_parent_body_lead'] += 1
                continue
            proofs = {'master': master_proof, 'index': index_proof, 'article': article_proof}
            record = _record(identity, row, title, body, proofs)
            if verified_record(record, {'ticker': TICKER}, today=today) != PUBLISHER:
                raise ValueError('tcfhc_news_saved_original_unverified')
            check()
            records.append(record)
        audit['status'] = 'success' if records else 'unavailable'
    except _ERRORS as exc:
        audit.update(status='degraded_enrichment' if records else 'error',
                     error_kind=getattr(exc, 'error_kind', 'parse_error'), error_message=str(exc)[:150])
    components = getattr(http, 'components', []); sent = getattr(http, 'http_request_count', 0)
    # New metadata or an excluded subsidiary body does not make an already
    # cached parent article a newly fetched source observation.
    cached = (all(r['issuer_news_receipt']['source_record_archive']['article']['cache_hit'] is True for r in records)
              if records else bool(components) and all(c.get('cache_hit') is True for c in components))
    epochs = [p['retrieved_at'] for p in acquired]
    audit.update(http_request_sent=bool(sent), http_request_count=sent,
                 event_kind='http_request' if sent else 'cache_hit' if cached else 'local_block',
                 cache_hit=cached, stale=False, record_count=len(records), usable_count=len(records),
                 fetched_at_epoch=min(epochs) if epochs else None, parser_version=POLICY,
                 excluded_reason_counts={k: v for k, v in excluded.items() if v}, component_receipts=components)
    if audit['status'] == 'success' and cached:
        audit['status'] = 'skipped_fresh_cache'
    # The last boundary is after projection and diagnostics, using one clock.
    completed_at = time.time()
    try:
        check()
        if any(type(p.get('retrieved_at')) not in (int, float) or not math.isfinite(p['retrieved_at'])
               or not 0 <= completed_at - p['retrieved_at'] < RAW_TTL for p in acquired):
            raise SourceResponseError('original_expired')
    except _ERRORS as exc:
        records = []
        audit.update(status='error', record_count=0, usable_count=0, stale=True,
                     error_kind=getattr(exc, 'error_kind', 'parse_error'), error_message=str(exc)[:150])
    return records, audit
