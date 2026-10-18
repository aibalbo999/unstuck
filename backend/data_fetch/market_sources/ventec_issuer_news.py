"""Dated issuer-hosted reprints preserve their publisher and distinct date basis."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_record_utils import clean_text

INDEX = 'https://www.ventec-group.com/cht/news/'
ARTICLE = re.compile(r'https://www\.ventec-group\.com/cht/news/[a-z0-9]+(?:-[a-z0-9]+){0,50}/\Z')
ORIGINAL = re.compile(r'https://www\.digitimes\.com/news/a20\d{6}[A-Z]{2}\d{3}/[a-z0-9]+(?:-[a-z0-9]+){0,40}\.html\Z')
POLICY = 'issuer-hosted-news-republication-v1'
ROLE = 'issuer_hosted_press_republication'
MONTHS = {name+'月': n for n, name in enumerate(('一','二','三','四','五','六','七','八','九','十','十一','十二'), 1)}


def _clean(value):
    return re.sub(r'\s+', ' ', clean_text(value)).strip()


def _page(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 150_000:
        raise ValueError('ventec_response_size_invalid')
    return BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')


def index_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{2}\.\d{2}\.20\d{2}', value):
        return None
    try:
        return datetime.strptime(value, '%d.%m.%Y').date()
    except ValueError:
        return None


def article_date(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'(\d{2}) (十一月|十二月|[一二三四五六七八九十]月) (20\d{2})', value)
    if not match:
        return None
    try:
        return date(int(match[3]), MONTHS[match[2]], int(match[1]))
    except (ValueError, KeyError):
        return None


def parse_index(raw):
    cards = _page(raw).select('div.news-article.news-link')
    if not 1 <= len(cards) <= 50:
        raise ValueError('ventec_index_invalid')
    rows, seen = [], {}
    for card in cards:
        titles = card.select(':scope > div.match-col > h2')
        stamps = card.select(':scope > div.match-col > p.date')
        links = card.select(':scope > a.f-position-cover[href]')
        if len(titles) != 1 or len(stamps) != 1 or len(links) != 1:
            raise ValueError('ventec_index_fields_invalid')
        row = {'name': _clean(titles[0]), 'date_original': _clean(stamps[0]),
               'url': urljoin(INDEX, links[0]['href'])}
        if not 1 <= len(row['name']) <= 500 or not ARTICLE.fullmatch(row['url']):
            raise ValueError('ventec_index_route_invalid')
        if row['url'] in seen:
            if row != seen[row['url']]:
                raise ValueError('ventec_index_duplicate_conflict')
            continue
        seen[row['url']] = row
        rows.append(row)
    return rows


def parse_article(raw, listed):
    if not ARTICLE.fullmatch(str(listed.get('url') or '')):
        raise ValueError('ventec_article_route_invalid')
    soup = _page(raw)
    titles = soup.select('section.further-hero h1')
    mains = soup.select('section.further-content div.main-content')
    if len(titles) != 1 or len(mains) != 1:
        raise ValueError('ventec_article_sections_invalid')
    main = mains[0]
    stamps = main.select(':scope > p.f-margin-bottom-remove')
    # The observed site has an unclosed img around this body div. Accept its
    # corrected sibling form too, while keeping the same exact content section.
    bodies = main.select(':scope > div, :scope > img > div')
    if (len(stamps) != 1 or len(bodies) != 1 or _clean(titles[0]) != listed['name']
            or index_date(listed['date_original']) is None
            or article_date(_clean(stamps[0])) != index_date(listed['date_original'])):
        raise ValueError('article_index_detail_mismatch')
    body = bodies[0]
    if body.find(['script', 'iframe', 'object', 'form']):
        raise ValueError('ventec_article_content_invalid')
    attribution = body.select(':scope > h5 a[href]')
    labelled = [a for a in attribution if _clean(a)]
    if (len(labelled) != 1 or not re.fullmatch(r'Digitimes 20\d{2}', _clean(labelled[0]))
            or not ORIGINAL.fullmatch(labelled[0]['href'])
            or any(a['href'] != labelled[0]['href'] for a in attribution)):
        raise ValueError('ventec_original_attribution_unverified')
    paragraphs = [_clean(p) for p in body.select(':scope > p') if _clean(p)]
    text = '\n\n'.join(paragraphs)
    if not 100 <= len(text) <= 11_700 or not re.search(r'(?<!\w)Ventec(?!\w)', text, re.I):
        raise ValueError('ventec_article_body_unusable')
    return {'title': _clean(titles[0]), 'body': text, 'article_date_original': _clean(stamps[0]),
            'original_url': labelled[0]['href']}


def build_record(identity, index_raw, article_raw, listed, parsed, published):
    from .issuer_news import _record, _digest
    stamp = published.isoformat()
    explanation = f'官網轉載日期：{stamp}；原來源：DigiTimes；原文發布日期未核對。'
    record = _record('6672.TW', identity, article_raw, title=parsed['title'],
                     body=explanation+'\n\n'+parsed['body'], published=published,
                     date_original=listed['date_original'], link=parsed['original_url'],
                     document_url=listed['url'], original_id=listed['url'].removeprefix(INDEX).rstrip('/'))
    record.update(source='騰輝電子-KY官網轉載', source_type=ROLE, source_role=ROLE, publisher='DigiTimes',
                  publication_date_basis='issuer_republication', issuer_republication_date=stamp,
                  original_publisher_publication_date=None)
    record['publication_date_original'] = {'issuer_republication_index_date': listed['date_original'],
                                         'issuer_republication_article_date': parsed['article_date_original']}
    record['issuer_news_receipt'].update(policy=POLICY, index_response_sha256=sha256(index_raw).hexdigest(),
                                        parsed_content_sha256=_digest(record))
    return record


def verified_record(record, data, *, today):
    from .issuer_news import _canonical_day, _digest, PROFILES
    from .issuer_news_transport import ROSTER_URL
    try:
        profile = PROFILES['6672.TW']
        receipt = record.get('issuer_news_receipt')
        identity = data.get('company_identity')
        if identity is None:
            identity = {}
        if (data.get('ticker') != '6672.TW' or record.get('ticker') != '6672.TW'
                or not isinstance(receipt, dict) or not isinstance(identity, dict)
                or identity.get('official_name') not in (None, '', profile['short_name'])
                or record.get('source_type') != ROLE or record.get('source_role') != ROLE
                or record.get('publication_date_basis') != 'issuer_republication'
                or record.get('original_publisher_publication_date') is not None
                or record.get('publisher') != 'DigiTimes' or record.get('source') != '騰輝電子-KY官網轉載'
                or record.get('event_assessment') != 'not_assessed' or record.get('content_truncated') is not False
                or record.get('publication_date_precision') != 'day' or receipt.get('policy') != POLICY
                or receipt.get('ticker') != '6672.TW' or receipt.get('legal_name') != profile['legal_name']
                or receipt.get('short_name') != profile['short_name'] or receipt.get('english_alias') != profile['english_alias']
                or receipt.get('website_host') != profile['host'] or receipt.get('master_source_url') != ROSTER_URL
                or receipt.get('parsed_content_sha256') != _digest(record)
                or not all(re.fullmatch(r'[0-9a-f]{64}', str(receipt.get(k) or '')) for k in
                           ('master_response_sha256', 'article_response_sha256', 'index_response_sha256'))):
            return None
        observed = date.fromisoformat(receipt['master_observed_on'])
        originals = record.get('publication_date_original')
        if not isinstance(originals, dict) or not 0 <= (today-observed).days <= 14:
            return None
        published = index_date(originals.get('issuer_republication_index_date'))
        if (published is None or article_date(originals.get('issuer_republication_article_date')) != published
                or _canonical_day(record.get('date')) != published.isoformat()
                or record.get('issuer_republication_date') != published.isoformat()
                or 'published_date' in record and _canonical_day(record['published_date']) != published.isoformat()):
            return None
        document = str(record.get('source_document_url') or '')
        if (not ARTICLE.fullmatch(document) or not ORIGINAL.fullmatch(str(record.get('link') or ''))
                or receipt.get('original_id') != document.removeprefix(INDEX).rstrip('/')):
            return None
        body, title = record.get('text'), record.get('title')
        explanation = f'官網轉載日期：{published.isoformat()}；原來源：DigiTimes；原文發布日期未核對。'
        if (not isinstance(body, str) or not 100 <= len(body) <= 12_000 or not body.startswith(explanation+'\n\n')
                or record.get('summary') != body[:280] or not isinstance(title, str) or not 1 <= len(title) <= 500
                or not re.search(r'(?<!\w)Ventec(?!\w)', body[len(explanation):], re.I)):
            return None
        forbidden = identity.get('forbidden_aliases', [])
        if not isinstance(forbidden, (list, tuple)) or 'ventec' in {_clean(v).strip('*').strip().casefold() for v in forbidden}:
            return None
        return 'Ventec'
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
