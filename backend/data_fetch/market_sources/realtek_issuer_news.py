"""Realtek's anonymous English news pages, bound to their original issuer row."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import math
import re
import time

from bs4 import BeautifulSoup

from news_record_utils import clean_text, parse_news_datetime
from search_provider_runtime import SourceResponseError

INDEX = 'https://www.realtek.com/Article/News?lang=en-GB&app_id=18'
ARTICLE = re.compile(r'https://www\.realtek\.com/Article/NewsDetail\?id=([1-9]\d{0,7})&app_id=18&lang=en-GB\Z')
LISTED_LINK = re.compile(r'/Article/NewsDetail\?id=([1-9]\d{0,7})&app_id=18\Z')
POLICY = 'realtek-public-issuer-news-v1'
UBN = '22671299'
MONTHS = {name: i for i, name in enumerate((
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'), 1)}


def _clean(value):
    return re.sub(r'\s+', ' ', clean_text(value)).strip()


def index_date(value):
    if isinstance(value, str) and re.fullmatch(r'20\d{2}-\d{2}-\d{2}', value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None


def _page(raw, limit):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= limit:
        raise ValueError('realtek_response_size_invalid')
    return BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')


def parse_index(raw):
    soup = _page(raw, 400_000)
    headings = soup.select('h1.page-title')
    cards = soup.select('div.teaser-item-bg > div.floatbox > div.pos-content > div.row')
    if len(headings) != 1 or _clean(headings[0]) != 'NEWS' or not 1 <= len(cards) <= 200:
        raise ValueError('realtek_index_sections_invalid')
    rows, seen = [], {}
    for card in cards:
        stamps = card.select(':scope > div.col-md-2 > div.news-created')
        links = card.select(':scope > div.col-md-10 > div > a[href]')
        if len(stamps) != 1 or len(links) != 1:
            raise ValueError('realtek_index_fields_invalid')
        link = links[0]
        matched = LISTED_LINK.fullmatch(str(link.get('href') or ''))
        title = _clean(link)
        if not matched or not 1 <= len(title) <= 500 or _clean(link.get('title')) != title:
            raise ValueError('realtek_index_route_or_title_invalid')
        row = {'name': title, 'date_original': _clean(stamps[0]), 'id': matched[1],
               'url': 'https://www.realtek.com' + link['href'] + '&lang=en-GB'}
        if row['id'] in seen:
            if row != seen[row['id']]:
                raise ValueError('realtek_index_duplicate_conflict')
            continue
        seen[row['id']] = row
        rows.append(row)
    return rows


def parse_article(raw, listed):
    if not ARTICLE.fullmatch(str(listed.get('url') or '')):
        raise ValueError('realtek_article_route_invalid')
    soup = _page(raw, 150_000)
    boxes = soup.select('div.teaser-item-bg')
    if len(boxes) != 1:
        raise ValueError('realtek_article_section_invalid')
    titles = boxes[0].select(':scope > h1.pos-title')
    bodies = boxes[0].select(':scope > div.floatbox > div.pos-content > div.element-itemname')
    if len(titles) != 1 or len(bodies) != 1 or _clean(titles[0]) != listed['name']:
        raise ValueError('article_index_detail_mismatch')
    body = bodies[0]
    if (body.find(['script', 'iframe', 'object', 'form'])
            or any(node.name not in {'p', 'br'} for node in body.find_all(recursive=False))
            or any(str(node).strip() for node in body.find_all(string=True, recursive=False))):
        raise ValueError('realtek_article_content_invalid')
    paragraph_nodes = body.find_all('p', recursive=False)
    paragraphs = [_clean(p) for p in paragraph_nodes if _clean(p)]
    if not paragraphs:
        raise ValueError('realtek_article_body_unusable')
    if (not paragraph_nodes or not _clean(paragraph_nodes[0]) or paragraph_nodes[0].attrs
            or any(node.name not in {'strong', 'br', 'b', 'i', 'em'} or node.attrs
                   for node in paragraph_nodes[0].find_all())):
        raise ValueError('realtek_article_dateline_unverified')
    stamp = re.match(r'^HSINCHU, Taiwan [–-] ([A-Z][a-z]+) (\d{2}), (20\d{2}) [–-] ', paragraphs[0])
    try:
        published = date(int(stamp[3]), MONTHS[stamp[1]], int(stamp[2])) if stamp else None
    except (ValueError, KeyError):
        published = None
    text = '\n\n'.join(paragraphs)
    if (published is None or published != index_date(listed['date_original'])
            or not 100 <= len(text) <= 12_000 or 'Realtek Semiconductor Corporation' not in text):
        raise ValueError('realtek_article_publication_or_issuer_unverified')
    return _clean(titles[0]), text


def _identity(raw, today):
    import json
    from .issuer_news import _identity as issuer_identity
    identity = issuer_identity(raw, '2379.TW', today)
    rows = [row for row in json.loads(raw) if str(row.get('公司代號')) == '2379']
    if len(rows) != 1 or str(rows[0].get('營利事業統一編號')) != UBN:
        raise ValueError('realtek_issuer_ubn_unverified')
    return {**identity, 'official_ubn': UBN}


def _build_record(identity, listed, article_raw, title, body, proofs):
    from .issuer_news import _record
    record = _record('2379.TW', identity, article_raw, title=title, body=body,
                     published=index_date(listed['date_original']), date_original=listed['date_original'],
                     link=listed['url'], document_url=listed['url'], original_id=listed['id'])
    record['publisher'] = 'Realtek'
    record['issuer_news_receipt'].update(policy=POLICY, source_record_archive=proofs,
                                        index_response_sha256=proofs['index']['raw_response_sha256'])
    return record


def _read_proof(proof, url):
    from official_response_evidence import read_response
    from .issuer_news_transport import url_contract
    limit, _ = url_contract(url)
    epoch = proof.get('retrieved_at') if isinstance(proof, dict) else None
    if (not isinstance(proof, dict) or proof.get('status') != 'archived' or proof.get('source_url') != url
            or type(proof.get('http_status')) is not int or proof['http_status'] != 200
            or proof.get('evidence_kind') != 'raw_http_response_bytes'
            or type(proof.get('raw_response_bytes')) is not int or not 0 < proof['raw_response_bytes'] <= limit
            or type(epoch) not in (int, float) or not math.isfinite(epoch) or not 0 < epoch <= time.time()):
        raise ValueError('realtek_original_receipt_invalid')
    raw = read_response(proof)
    if len(raw) != proof['raw_response_bytes']:
        raise ValueError('realtek_original_size_mismatch')
    return raw


def verified_record(record, data, *, today):
    from .issuer_news import _canonical_day, TAIPEI
    from .issuer_news_transport import ROSTER_URL
    try:
        identity_context = data.get('company_identity')
        if identity_context is None:
            identity_context = {}
        if (data.get('ticker') != '2379.TW' or not isinstance(identity_context, dict)
                or identity_context.get('official_name') not in (None, '', '瑞昱')
                or identity_context.get('legal_name') not in (None, '', '瑞昱半導體股份有限公司')):
            return None
        forbidden = identity_context.get('forbidden_aliases', [])
        if not isinstance(forbidden, (list, tuple)) or 'realtek' in {_clean(v).strip('*').strip().casefold() for v in forbidden}:
            return None
        receipt = record['issuer_news_receipt']
        proofs = receipt['source_record_archive']
        document = record['source_document_url']
        if not ARTICLE.fullmatch(str(document)):
            return None
        master_raw = _read_proof(proofs['master'], ROSTER_URL)
        index_raw = _read_proof(proofs['index'], INDEX)
        article_raw = _read_proof(proofs['article'], document)
        identity = _identity(master_raw, today)
        if date.fromisoformat(identity['master_observed_on']) > datetime.fromtimestamp(proofs['master']['retrieved_at'], TAIPEI).date():
            return None
        listed = [row for row in parse_index(index_raw) if row['url'] == document]
        if len(listed) != 1:
            return None
        listed = listed[0]
        published = index_date(listed['date_original'])
        if published is None or any(datetime.fromtimestamp(proofs[key]['retrieved_at'], TAIPEI).date() < published
                                    for key in ('index', 'article')):
            return None
        title, body = parse_article(article_raw, listed)
        expected = _build_record(identity, listed, article_raw, title, body, proofs)
        if (_canonical_day(record.get('date')) != expected['date']
                or 'published_date' in record and _canonical_day(record['published_date']) != expected['date']
                or any(record.get(key) != value for key, value in expected.items() if key != 'date')):
            return None
        return 'Realtek'
    except (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError, OverflowError, SourceResponseError):
        return None


def fetch_recent_news(*, now, http=None):
    from .issuer_news import TAIPEI
    from .issuer_news_transport import IssuerNewsHttp, ROSTER_URL
    from official_response_evidence import archive_response
    deadline = time.monotonic() + 20
    http = http or IssuerNewsHttp(deadline)
    today = now.astimezone(TAIPEI).date()
    records, excluded = [], Counter()
    audit = {'selection_policy': POLICY, 'coverage_status': 'partial', 'window_complete': False}
    try:
        master_raw = http.get(ROSTER_URL)
        identity = _identity(master_raw, today)
        index_raw = http.get(INDEX)
        rows = parse_index(index_raw)
        audit['raw_count'] = len(rows)
        selected = []
        for row in rows:
            day = index_date(row['date_original'])
            if day is None:
                excluded['unknown_date'] += 1
            elif parse_news_datetime(day.isoformat()) > now:
                excluded['future'] += 1
            elif parse_news_datetime(day.isoformat()) < now - timedelta(days=30):
                excluded['historical'] += 1
            else:
                selected.append(row)
        def archive(raw, url):
            components = [c for c in http.components if c.get('url') == url]
            epoch = components[-1].get('fetched_at_epoch') if components else None
            proof = archive_response(raw, source_url=url, retrieved_at=epoch, http_status=200)
            if _read_proof(proof, url) != raw:
                raise ValueError('realtek_original_archive_unverified')
            return proof
        shared_proofs = None
        for row in sorted(selected, key=lambda r: r['date_original'], reverse=True)[:5]:
            if time.monotonic() >= deadline:
                raise SourceResponseError('timeout')
            original = http.get(row['url'])
            title, body = parse_article(original, row)
            if shared_proofs is None:
                shared_proofs = {'master': archive(master_raw, ROSTER_URL), 'index': archive(index_raw, INDEX)}
            proofs = {**shared_proofs, 'article': archive(original, row['url'])}
            record = _build_record(identity, row, original, title, body, proofs)
            if not verified_record(record, {'ticker': '2379.TW'}, today=today):
                raise ValueError('realtek_saved_record_unverified')
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
