"""Published SYM global originals, supplementary to corporate Sanyang news.

An index day is the only observed publication precision. These issuer statements
are one publisher, text only, and never proof of a complete 8/3/30 news window.
"""
from collections import Counter
import csv
from datetime import date, datetime, timedelta
from hashlib import sha256
import io
import json
import math
import re
import time
import zlib
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from news_record_utils import clean_text, parse_news_datetime
from search_provider_runtime import SourceResponseError
from . import official_issuer_master as master
from .sym_issuer_news_transport import (
    SymNewsHttp, MASTER, CORPORATE, BRAND, TAIWAN, GLOBAL, INDEX, ARTICLES, ARTICLE,
    original_bytes, replay_expiry_valid, RAW_TTL,
)

TICKER = '2206.TW'
LEGAL = '三陽工業股份有限公司'
UBN = '24004006'
POLICY = 'sym-global-issuer-originals-v1'
PROVIDER = 'SYM global issuer news'
PUBLISHER = '三陽工業官網'
TAIPEI = ZoneInfo('Asia/Taipei')
CHAIN = {'corporate': CORPORATE, 'brand': BRAND, 'taiwan': TAIWAN, 'index': INDEX}
QUALIFIED = {
    ARTICLES[0]: ('The Predator on the Prowl: JEPARDO Ready to Conquer European and Global Markets', date(2026, 10, 1)),
    ARTICLES[1]: ('SYM Upgrades Global Website for a New Digital Era', date(2026, 9, 30)),
}
NAMES = {'三陽工業', LEGAL, 'sanyang motor co., ltd.', 'sanyang motor co ltd', 'sym'}
ERRORS = (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError, OverflowError, zlib.error, SourceResponseError)


def _text(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()


def validate_context(data, ticker=TICKER):
    if not isinstance(data, dict) or ticker != TICKER or data.get('ticker') != TICKER:
        return False
    identity = data.get('company_identity')
    if identity is None:
        identity = {}
    if not isinstance(identity, dict):
        return False
    expected = {'ticker': TICKER, 'stock_id': '2206', 'official_name': '三陽工業',
                'legal_name': LEGAL, 'official_ubn': UBN, 'instrument_type': 'EQUITY'}
    if any(identity.get(k) not in (None, '', v) for k, v in expected.items()):
        return False
    if any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quote_type', 'quoteType')):
        return False
    for field in ('company_name', 'raw_company_name'):
        value = data.get(field)
        if value not in (None, '') and (not isinstance(value, str) or any(p.strip().casefold() not in NAMES for p in value.split(' / '))):
            return False
    forbidden = identity.get('forbidden_aliases', [])
    return (isinstance(forbidden, (list, tuple)) and all(isinstance(x, str) for x in forbidden)
            and not NAMES.intersection(clean_text(x).casefold().strip().strip('*').strip() for x in forbidden))


def _page(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('SYM HTML size invalid')
    return BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')


def parse_master(raw, epoch, url, today):
    if url == MASTER:
        master.validate_csv(raw, epoch)
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True))
    elif url == master.JSON_URL:
        from .official_issuer_master_json import parse_rows
        rows = parse_rows(raw, epoch)
    else:
        raise ValueError('SYM master URL invalid')
    selected = [r for r in rows if r['公司代號'] == '2206']
    if len(selected) != 1:
        raise ValueError('SYM issuer not unique')
    row = selected[0]
    required = {'公司名稱': LEGAL, '公司簡稱': '三陽工業', '營利事業統一編號': UBN,
                '英文簡稱': 'SYM', '網址': 'www.sanyang.com.tw'}
    stamp = row['出表日期']
    published = date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:]))
    if any(row.get(k) != v for k, v in required.items()) or not 0 <= (today - published).days <= 14:
        raise ValueError('SYM master identity/domain/date mismatch')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': UBN,
            'master_observed_on': published.isoformat(), 'master_source_url': url,
            'master_response_sha256': sha256(raw).hexdigest()}


def _linked(soup, url, label):
    return any(a.get('href') == url and _text(a) == label for a in soup.select('a[href]'))


def _global_identity(soup):
    footers = soup.select('footer')
    if len(footers) != 1 or 'TAIWAN SANYANG MOTOR Co., Ltd.' not in _text(footers[0]) or '3 Chung Hua Road, Hukou, Hsinchu, Taiwan R.O.C' not in _text(footers[0]):
        raise ValueError('SYM global publisher unverified')


def parse_chain(raws):
    corporate, brand, taiwan = (_page(raws[k]) for k in ('corporate', 'brand', 'taiwan'))
    if ('三陽工業' not in _text(corporate) or not re.search(r'股票代碼\s*[:：]?\s*2206', _text(corporate))
            or not _linked(corporate, BRAND, 'SYM三陽機車')
            or not _linked(brand, TAIWAN, 'SYM官方網站')
            or not _linked(taiwan, GLOBAL, 'GLOBAL Site')):
        raise ValueError('SYM corporate/brand/global chain invalid')
    _global_identity(_page(raws['index']))


def parse_index(raw):
    soup = _page(raw)
    _global_identity(soup)
    cards = soup.select('a.c-news-card__content-wrap')
    if not 1 <= len(cards) <= 100:
        raise ValueError('SYM index count invalid')
    rows, seen = [], {}
    for card in cards:
        titles, dates = card.select('h2.c-news-card__title'), card.select('.c-news-card__date')
        url = card.get('href')
        if len(titles) != 1 or len(dates) != 1 or not isinstance(url, str) or not re.fullmatch(r'https://www\.sym-global\.com/(?:newsroom|news-events)-page[1-9][0-9]{0,7}', url):
            raise ValueError('SYM index route invalid')
        title, original = _text(titles[0]), _text(dates[0])
        day = datetime.strptime(original, '%b. %d %Y').date()
        if not 1 <= len(title) <= 500 or card.get('title') != title:
            raise ValueError('SYM index title invalid')
        row = {'url': url, 'title': title, 'date_original': original, 'date': day.isoformat()}
        if url in seen and seen[url] != row:
            raise ValueError('SYM repeated index conflict')
        if url not in seen:
            rows.append(row)
            seen[url] = row
        # Re-dating an already observed article is not a new recent event.
        if url in QUALIFIED and (title, day) != QUALIFIED[url]:
            raise ValueError('SYM qualified publication changed')
    return rows


def parse_article(raw, listed):
    soup = _page(raw)
    _global_identity(soup)
    url = listed['url']
    if not isinstance(url, str) or not ARTICLE.fullmatch(url):
        raise ValueError('SYM article unqualified')
    titles, bodies = soup.select('h1.page-title'), soup.select('article.blog-post-details .post_content')
    canonical, ogurl = soup.select('link[rel=canonical]'), soup.select('meta[property="og:url"]')
    if (len(titles) != 1 or _text(titles[0]) != listed['title'] or len(bodies) != 1
            or len(canonical) != 1 or canonical[0].get('href') != url
            or len(ogurl) != 1 or ogurl[0].get('content') != url):
        raise ValueError('SYM article/index mismatch')
    site = soup.select('meta[property="og:site_name"]')
    if len(site) != 1 or site[0].get('content') != 'SYM GLOBAL':
        raise ValueError('SYM article publisher mismatch')
    if bodies[0].find(['script', 'iframe', 'object', 'form']):
        raise ValueError('SYM article body invalid')
    body = _text(bodies[0])
    if not 100 <= len(body) <= 12_000 or not re.search(r'\bSYM\b', body):
        raise ValueError('SYM article subject invalid')
    return body


def _record(identity, listed, body, proofs):
    return {'ticker': TICKER, 'title': listed['title'], 'text': body, 'summary': body[:280],
            'date': listed['date'], 'link': listed['url'], 'source_document_url': listed['url'],
            'source': '三陽工業官網', 'publisher': PUBLISHER, 'source_type': 'first_party_issuer_news',
            'issuer_evidence_basis': 'verified_sym_global_brand_chain',
            'publication_date_original': {'index_card_date': listed['date_original'], 'article_date': None, 'basis': 'unique_official_index_card'},
            'publication_date_precision': 'day', 'first_publication_time_verified': False,
            'content_coverage': 'text_available', 'content_truncated': False, 'image_content_verified': False,
            'source_role': 'issuer_statement', 'event_assessment': 'not_assessed',
            'commercial_reuse_permission_verified': False,
            'issuer_news_receipt': {**identity, 'policy': POLICY, 'original_id': listed['url'].rsplit('page', 1)[1],
                                    'index_response_sha256': proofs['index']['raw_response_sha256'],
                                    'article_response_sha256': proofs['article']['raw_response_sha256'],
                                    'source_record_archive': proofs}}


def is_marked(record):
    if not isinstance(record, dict):
        return False
    proof = record.get('issuer_news_receipt')
    return (isinstance(proof, dict) and proof.get('policy') == POLICY
            or any(isinstance(record.get(k), str) and ARTICLE.fullmatch(record[k]) for k in ('source_document_url', 'link'))
            or record.get('issuer_evidence_basis') == 'verified_sym_global_brand_chain')


def _fresh(proofs, max_age, observed=None):
    observed = time.time() if observed is None else observed
    for name, proof in proofs.items():
        stamp = proof.get('retrieved_at')
        if type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= observed - stamp < max_age:
            return False
        if name == 'master':
            if not master.live_or_historical_expiry_valid(proof, max_age, observed):
                return False
        elif not replay_expiry_valid(proof, max_age, observed):
            return False
    return True


def verified_record(record, data, *, today, max_age=30 * 86400):
    """Replay saved originals; a historical receipt is never a new acquisition."""
    try:
        if not validate_context(data):
            return None
        if any(record.get(k) is not False for k in ('content_truncated', 'image_content_verified',
                                                   'first_publication_time_verified', 'commercial_reuse_permission_verified')):
            return None
        proofs = record['issuer_news_receipt']['source_record_archive']
        if not isinstance(proofs, dict) or set(proofs) != {'master', *CHAIN, 'article'}:
            return None
        url = record['source_document_url']
        if not isinstance(url, str) or not ARTICLE.fullmatch(url):
            return None
        master_url = proofs['master']['source_url']
        raw = original_bytes(proofs['master'], master_url, max_age=max_age)
        # Master identity is attested as of its real original acquisition day.
        identity = parse_master(raw, proofs['master']['retrieved_at'], master_url,
                                datetime.fromtimestamp(proofs['master']['retrieved_at'], TAIPEI).date())
        raws = {k: original_bytes(proofs[k], u, max_age=max_age) for k, u in CHAIN.items()}
        parse_chain(raws)
        listed = [r for r in parse_index(raws['index']) if r['url'] == url]
        if len(listed) != 1:
            return None
        row = listed[0]
        published = date.fromisoformat(row['date'])
        if not today - timedelta(days=30) <= published <= today:
            return None
        if any(datetime.fromtimestamp(proofs[k]['retrieved_at'], TAIPEI).date() < published for k in ('index', 'article')):
            return None
        body = parse_article(original_bytes(proofs['article'], url, max_age=max_age), row)
        expected = _record(identity, row, body, proofs)
        # Existing selection normalizes day-only dates to timestamps. Preserve
        # the exact original day marker, and compare only that same calendar day.
        for field in ('date', 'published_date'):
            if field in record:
                value = parse_news_datetime(record[field])
                if value is None or value != parse_news_datetime(row['date']):
                    return None
        if any(record.get(k) != v for k, v in expected.items() if k != 'date') or not _fresh(proofs, max_age):
            return None
        return PUBLISHER
    except ERRORS:
        return None


def fetch_recent_news(*, now, http=None, deadline=None, limit=5):
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError('SYM article limit invalid')
    end = time.monotonic() + 25
    if deadline is not None:
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('SYM deadline invalid')
        end = min(end, deadline)
    http = http or SymNewsHttp(end)
    if hasattr(http, 'deadline'):
        http.deadline = min(http.deadline, end)
    records, excluded = [], Counter()
    audit = {'selection_policy': POLICY, 'coverage_status': 'partial', 'window_complete': False}

    def check():
        if time.monotonic() >= end:
            raise SourceResponseError('timeout')

    try:
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError('SYM timezone required')
        today = now.astimezone(TAIPEI).date()
        check()
        raw, receipt = http.get_receipt(MASTER)
        identity = parse_master(raw, receipt['retrieved_at'], receipt['source_url'], today)
        shared, raws = {'master': receipt}, {}
        for name, url in CHAIN.items():
            check()
            raws[name], shared[name] = http.get_receipt(url)
        parse_chain(raws)
        rows = parse_index(raws['index'])
        audit['raw_count'] = len(rows)
        for row in sorted(rows, key=lambda r: r['date'], reverse=True):
            day = date.fromisoformat(row['date'])
            if day > today:
                excluded['future'] += 1
            elif day < today - timedelta(days=30):
                excluded['historical'] += 1
            elif not ARTICLE.fullmatch(row['url']):
                excluded['unqualified_article'] += 1
            elif len(records) >= limit:
                excluded['article_limit'] += 1
            else:
                check()
                article, proof = http.get_receipt(row['url'])
                record = _record(identity, row, parse_article(article, row), {**shared, 'article': proof})
                if not verified_record(record, {'ticker': TICKER}, today=today, max_age=RAW_TTL):
                    raise ValueError('SYM saved original verification failed')
                check()
                records.append(record)
        check()
        audit['status'] = 'success' if records else 'unavailable'
    except ERRORS as exc:
        audit.update(status='degraded_enrichment' if records else 'error', error_kind=getattr(exc, 'error_kind', 'parse_error'), error_message=str(exc)[:150])
    # Pure final check uses one instant for every original, including a partial
    # result whose later article failed; no extra I/O can create a new age gap.
    observed = time.time()
    if any(not _fresh(r['issuer_news_receipt']['source_record_archive'], RAW_TTL, observed) for r in records):
        records = []
        audit.update(status='error', error_kind='original_expired')
    components = getattr(http, 'components', [])
    sent = getattr(http, 'http_request_count', 0)
    epochs = [c['fetched_at_epoch'] for c in components if type(c.get('fetched_at_epoch')) in (int, float)]
    audit.update(http_request_sent=bool(sent), http_request_count=sent, event_kind='http_request' if sent else 'local_block',
                 cache_hit=False, stale=False, record_count=len(records), usable_count=len(records),
                 fetched_at_epoch=min(epochs) if epochs else None, parser_version=POLICY,
                 excluded_reason_counts=dict(excluded), component_receipts=components)
    return records, audit
