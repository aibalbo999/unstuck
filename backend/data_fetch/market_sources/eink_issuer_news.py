"""E Ink's complete Chinese press releases, bound to its OTC issuer originals."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import math
import re
import time

from bs4 import BeautifulSoup

from news_record_utils import clean_text, parse_news_datetime
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp
from .official_company_legal_name import URLS

TICKER = '8069.TWO'
MASTER = URLS['.TWO']
LOCALE = 'https://www.eink.com/news'
INDEX = 'https://tw.eink.com/news'
ARTICLE = re.compile(r'https://tw\.eink\.com/news/detail/([A-Z0-9]{10})\Z')
POLICY = 'eink-otc-public-issuer-news-v1'
LEGAL = '元太科技工業股份有限公司'
UBN = '22099890'
MONTHS = {name: i for i, name in enumerate(
    ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'), 1)}


def url_contract(url):
    if url == MASTER:
        return 2_500_000, {'application/json', 'text/json'}
    if url in {LOCALE, INDEX} or ARTICLE.fullmatch(str(url)):
        return 600_000, {'text/html', 'application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')


class EInkHttp(IssuerNewsHttp):
    route_contract = staticmethod(url_contract)


def _clean(value):
    return re.sub(r'\s+', ' ', clean_text(value)).strip()


def _page(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 600_000:
        raise ValueError('eink_response_size_invalid')
    return BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')


def _date(value):
    matched = re.fullmatch(r'(\d{1,2}) (20\d{2}) \. ([A-Z][a-z]{2})', value)
    try:
        return date(int(matched[2]), MONTHS[matched[3]], int(matched[1])) if matched else None
    except (KeyError, ValueError):
        return None


def _identity(raw, today, epoch):
    from .twse_security_identity import _master_name
    from .issuer_news import TAIPEI
    short, legal = _master_name(raw, TICKER, epoch)
    rows = [r for r in json.loads(raw) if r['SecuritiesCompanyCode'] == '8069']
    if len(rows) != 1:
        raise ValueError('eink_issuer_not_unique')
    row = rows[0]
    stamp = row['Date']
    published = date(int(stamp[:3]) + 1911, int(stamp[3:5]), int(stamp[5:]))
    if (short != '元太' or legal != LEGAL or row.get('UnifiedBusinessNo.') != UBN
            or row.get('WebAddress') != 'www.eink.com'
            or not 0 <= (today - published).days <= 14
            or published > datetime.fromtimestamp(epoch, TAIPEI).date()):
        raise ValueError('eink_issuer_domain_unverified')
    return {'ticker': TICKER, 'short_name': short, 'legal_name': legal, 'official_ubn': UBN,
            'website_host': 'www.eink.com', 'market': 'TPEx',
            'master_observed_on': published.isoformat(), 'master_source_url': MASTER,
            'master_response_sha256': sha256(raw).hexdigest()}


def _verify_locale(raw):
    links = _page(raw).select('a[href]')
    targets = {str(a['href']) for a in links if _clean(a) == '繁體中文'}
    if targets != {INDEX}:
        raise ValueError('eink_published_locale_unverified')


def parse_index(raw):
    lists = _page(raw).select('div.news-content > div.container > ul.news-list')
    if len(lists) != 1:
        raise ValueError('eink_index_section_invalid')
    cards = lists[0].select(':scope > li.item')
    if not 1 <= len(cards) <= 200:
        raise ValueError('eink_index_count_invalid')
    rows, seen = [], {}
    for card in cards:
        links = card.select(':scope > a[href]')
        if len(links) != 1:
            raise ValueError('eink_index_link_invalid')
        link = links[0]
        titles, stamps, roles = (link.select(selector) for selector in
                                ('.content > .main', '.side > .date', '.side > .tag'))
        if len(titles) != 1 or len(stamps) != 1 or len(roles) != 1:
            raise ValueError('eink_index_fields_invalid')
        title, stamp, role = _clean(titles[0]), _clean(stamps[0]), _clean(roles[0])
        if not 1 <= len(title) <= 500 or _date(stamp) is None:
            raise ValueError('eink_index_title_date_invalid')
        row = {'title': title, 'date_original': stamp, 'role': role, 'url': str(link['href'])}
        if role == '新聞發佈' and not ARTICLE.fullmatch(row['url']):
            raise ValueError('eink_press_route_unverified')
        if row['url'] in seen:
            if row != seen[row['url']]:
                raise ValueError('eink_index_duplicate_conflict')
            continue
        seen[row['url']] = row
        rows.append(row)
    return rows


def parse_article(raw, listed):
    if listed['role'] != '新聞發佈' or not ARTICLE.fullmatch(listed['url']):
        raise ValueError('eink_article_route_or_role_unverified')
    outlines = _page(raw).select('div.news-detail > div.news-content > div.container > div.outline')
    if len(outlines) != 1:
        raise ValueError('eink_article_outline_invalid')
    outline = outlines[0]
    titles, stamps, roles = (outline.select(selector) for selector in
                            (':scope > h1', ':scope > .date', ':scope > .tag'))
    blocks = outline.parent.select(':scope > div.wrapper > div._articleBlock')
    if len(titles) != 1 or len(stamps) != 1 or len(roles) != 1 or len(blocks) != 1:
        raise ValueError('eink_article_fields_invalid')
    if (_clean(titles[0]) != listed['title'] or _clean(roles[0]) != listed['role']
            or _date(_clean(stamps[0])) != _date(listed['date_original'])):
        raise ValueError('eink_index_article_mismatch')
    block = blocks[0]
    if block.find(['script', 'iframe', 'object', 'form']):
        raise ValueError('eink_article_body_invalid')
    text = _clean(block)
    if (not 100 <= len(text) <= 12_000 or '元太科技' not in text
            or re.search(r'(?<!\d)8069\.TW(?!\w)', text)):
        raise ValueError('eink_article_issuer_or_market_unverified')
    return _clean(titles[0]), text


def _read_original(proof, url):
    limit, _ = url_contract(url)
    epoch = proof.get('retrieved_at') if isinstance(proof, dict) else None
    if (not isinstance(proof, dict) or proof.get('status') != 'archived' or proof.get('source_url') != url
            or type(proof.get('http_status')) is not int or proof['http_status'] != 200
            or proof.get('evidence_kind') != 'raw_http_response_bytes'
            or type(proof.get('raw_response_bytes')) is not int or not 0 < proof['raw_response_bytes'] <= limit
            or type(epoch) not in (int, float) or not math.isfinite(epoch) or not 0 < epoch <= time.time()):
        raise ValueError('eink_original_receipt_invalid')
    raw = read_response(proof)
    if len(raw) != proof['raw_response_bytes']:
        raise ValueError('eink_original_size_mismatch')
    return raw


def _build_record(identity, listed, title, body, proofs):
    day = _date(listed['date_original']).isoformat()
    return {'ticker': TICKER, 'title': title, 'text': body, 'summary': body[:280],
            'date': day, 'link': listed['url'], 'source_document_url': listed['url'],
            'source': '元太官網', 'publisher': 'E Ink', 'source_type': 'first_party_issuer_news',
            'publication_date_original': {'issuer_article_date': listed['date_original'], 'date': day},
            'publication_date_precision': 'day', 'content_coverage': 'text_available',
            'content_truncated': False, 'source_role': 'issuer_statement', 'event_assessment': 'not_assessed',
            'issuer_news_receipt': {**identity, 'policy': POLICY,
                'original_id': ARTICLE.fullmatch(listed['url'])[1],
                'index_response_sha256': proofs['index']['raw_response_sha256'],
                'article_response_sha256': proofs['article']['raw_response_sha256'],
                'source_record_archive': proofs}}


def verified_record(record, data, *, today):
    from .issuer_news import TAIPEI, _canonical_day
    try:
        context = data.get('company_identity')
        if context is None:
            context = {}
        if data.get('ticker') != TICKER or not isinstance(context, dict):
            return None
        for key, expected in [('ticker', TICKER), ('stock_id', '8069'), ('official_name', '元太'),
                              ('legal_name', LEGAL), ('official_ubn', UBN), ('instrument_type', 'EQUITY')]:
            if context.get(key) not in (None, '', expected):
                return None
        if data.get('instrument_type') not in (None, '', 'EQUITY'):
            return None
        forbidden = context.get('forbidden_aliases', [])
        if (not isinstance(forbidden, (list, tuple)) or any(not isinstance(v, str) for v in forbidden)
                or {'元太', '元太科技', LEGAL, 'e ink'} & {_clean(v).casefold().strip('*').strip() for v in forbidden}):
            return None
        proofs = record['issuer_news_receipt']['source_record_archive']
        document = record['source_document_url']
        if not ARTICLE.fullmatch(str(document)):
            return None
        master = _read_original(proofs['master'], MASTER)
        locale = _read_original(proofs['locale'], LOCALE)
        index = _read_original(proofs['index'], INDEX)
        article = _read_original(proofs['article'], document)
        identity = _identity(master, today, proofs['master']['retrieved_at'])
        _verify_locale(locale)
        listed = [row for row in parse_index(index) if row['url'] == document]
        if len(listed) != 1 or listed[0]['role'] != '新聞發佈':
            return None
        listed = listed[0]
        published = _date(listed['date_original'])
        if any(datetime.fromtimestamp(proofs[key]['retrieved_at'], TAIPEI).date() < published
               for key in ('index', 'article')):
            return None
        title, text = parse_article(article, listed)
        expected = _build_record(identity, listed, title, text, proofs)
        if (_canonical_day(record.get('date')) != expected['date']
                or 'published_date' in record and _canonical_day(record['published_date']) != expected['date']
                or any(record.get(key) != value for key, value in expected.items() if key != 'date')):
            return None
        return '元太'
    except (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError, OverflowError, SourceResponseError):
        return None


def fetch_recent_news(*, now, http=None):
    from .issuer_news import TAIPEI
    deadline = time.monotonic() + 20
    http = http or EInkHttp(deadline)
    today = now.astimezone(TAIPEI).date()
    records, excluded = [], Counter()
    audit = {'selection_policy': POLICY, 'coverage_status': 'partial', 'window_complete': False}
    try:
        master_raw = http.get(MASTER)
        master_components = [c for c in http.components if c.get('url') == MASTER]
        master_epoch = master_components[-1]['fetched_at_epoch']
        identity = _identity(master_raw, today, master_epoch)
        locale_raw = http.get(LOCALE)
        _verify_locale(locale_raw)
        index_raw = http.get(INDEX)
        rows = parse_index(index_raw)
        audit['raw_count'] = len(rows)
        candidates = []
        for row in rows:
            stamp = parse_news_datetime(_date(row['date_original']).isoformat())
            if row['role'] != '新聞發佈':
                excluded['non_press_role'] += 1
            elif stamp > now:
                excluded['future'] += 1
            elif stamp < now - timedelta(days=30):
                excluded['historical'] += 1
            else:
                candidates.append(row)
        def archive(raw, url):
            components = [c for c in http.components if c.get('url') == url]
            epoch = components[-1].get('fetched_at_epoch') if components else None
            proof = archive_response(raw, source_url=url, retrieved_at=epoch, http_status=200)
            if _read_original(proof, url) != raw:
                raise ValueError('eink_original_archive_unverified')
            return proof
        shared = None
        for row in sorted(candidates, key=lambda item: _date(item['date_original']), reverse=True)[:5]:
            if time.monotonic() >= deadline:
                raise SourceResponseError('timeout')
            raw = http.get(row['url'])
            title, body = parse_article(raw, row)
            if shared is None:
                shared = {'master': archive(master_raw, MASTER), 'locale': archive(locale_raw, LOCALE),
                          'index': archive(index_raw, INDEX)}
            proofs = {**shared, 'article': archive(raw, row['url'])}
            record = _build_record(identity, row, title, body, proofs)
            if not verified_record(record, {'ticker': TICKER}, today=today):
                raise ValueError('eink_saved_original_unverified')
            if time.monotonic() >= deadline:
                raise SourceResponseError('timeout')
            records.append(record)
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        audit['status'] = 'success' if records else 'unavailable'
    except (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError, OverflowError, SourceResponseError) as exc:
        audit.update(status='degraded_enrichment' if records else 'error',
                     error_kind=getattr(exc, 'error_kind', 'parse_error'), error_message=str(exc)[:150])
    components = getattr(http, 'components', [])
    sent = getattr(http, 'http_request_count', 0)
    cached = bool(components) and all(c.get('cache_hit') for c in components)
    if audit['status'] == 'success' and cached and not sent:
        audit['status'] = 'skipped_fresh_cache'
    epochs = [c['fetched_at_epoch'] for c in components if type(c.get('fetched_at_epoch')) in (int, float)]
    audit.update(http_request_sent=bool(sent), http_request_count=sent,
                 event_kind='http_request' if sent else 'cache_hit' if cached else 'local_block',
                 cache_hit=cached, stale=False, record_count=len(records), usable_count=len(records),
                 fetched_at_epoch=min(epochs) if epochs else None, parser_version=POLICY,
                 excluded_reason_counts=dict(excluded), component_receipts=components)
    return records, audit
