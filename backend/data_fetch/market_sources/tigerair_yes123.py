"""Pure official-linked portal parsing; not an acquisition or issuer attestation.

Production counting additionally requires complete native HTTP, independent
issuer originals, immutable receipt metadata and normal-cache handoff checks.
Update dates and portal expiry never become first-publication or employer dates.
"""
from datetime import date, datetime, timedelta
from html import unescape
import json
import math
import re
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

TICKER = '6757.TW'
SHORT = '台灣虎航'
LEGAL = '台灣虎航股份有限公司'
UBN = '54381049'
PROVIDER = 'Tigerair official-linked yes123 public careers'
PAGE = 'https://www.tigerairtw.com/zh-TW/about-tigerair/join-us'
ARTICLE = 'https://api-cms.tigerairtw.com/api/strapi-cacheable/articles?slug=join-us&type%5B%5D=page&type%5B%5D=event&locale=zh-Hant-TW'
PID = '20140325092151_Y201403028'
PROFILE = 'https://www.yes123.com.tw/wk_index/comp_info.asp?p_id=' + PID
MAX_POSTINGS = 5
MAX_BYTES = 1_000_000
TTL = 1800
TZ = ZoneInfo('Asia/Taipei')


def _text(value):
    return ' '.join(str(value).replace('\\r\\n', ' ').split())


def _one(values):
    if len(values) != 1:
        raise ValueError('yes123 element missing or ambiguous')
    return values[0]


def _soup(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('yes123 original size invalid')
    text = raw.decode('utf-8', 'strict')
    if (len(re.findall(r'<html(?:\s[^<>]*)?>', text, re.I)) != 1
            or len(re.findall(r'</html\s*>', text, re.I)) != 1
            or not re.search(r'</html\s*>\s*\Z', text, re.I)):
        raise ValueError('yes123 full HTML original required')
    return BeautifulSoup(text, 'html.parser')


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('yes123 duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def canonical_detail_url(url):
    if not isinstance(url, str) or len(url) > 500:
        raise ValueError('yes123 posting URL invalid')
    p = urlsplit(url)
    q = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != 'https' or p.netloc != 'www.yes123.com.tw'
            or p.path != '/wk_index/job.asp' or p.fragment
            or set(q) != {'p_id', 'job_id'} or q['p_id'] != [PID]
            or len(q['job_id']) != 1 or not re.fullmatch(r'[0-9]{14}_[1-9][0-9]{0,9}', q['job_id'][0])):
        raise ValueError('yes123 exact published employer posting required')
    expected = 'https://www.yes123.com.tw/wk_index/job.asp?p_id=' + PID + '&job_id=' + q['job_id'][0]
    if url != expected:
        raise ValueError('yes123 posting action is not canonical')
    return expected


def parse_mapping(page_raw, article_raw):
    soup = _soup(page_raw)
    if _one(soup.find_all('meta', attrs={'name': 'og:url'})).get('content') != PAGE:
        raise ValueError('tigerair public page identity invalid')
    if not isinstance(article_raw, bytes) or not 0 < len(article_raw) <= MAX_BYTES:
        raise ValueError('tigerair complete article required')
    entity = _one(_json(article_raw)['data']['articles']['data'])
    a = entity['attributes']
    if (entity.get('id') != '34' or a.get('title') != '加入台灣虎航'
            or a.get('type') != 'page' or a.get('slug') != 'join-us'
            or a['footerNavigatorL2']['data']['attributes']['footerNavigatorL1']['data']['attributes']['slug'] != 'about-tigerair'):
        raise ValueError('tigerair published career article invalid')
    texts = [v['richtext'] for v in a['contents']
             if v.get('__typename') == 'ComponentContentRichtext' and isinstance(v.get('richtext'), str)]
    urls = [u for text in texts for u in re.findall(r'\]\((https://www\.yes123\.com\.tw/[^\s()]+)\)', text)]
    if urls != [PROFILE]:
        raise ValueError('tigerair exact published employer link missing')
    return {'profile_url': PROFILE, 'official_article_id': '34',
            'mapping_is_not_a_current_vacancy_or_employer_deadline': True}


def parse_listing(raw):
    soup = _soup(raw)
    if _text(_one(soup.find_all('h1')).get_text(' ', strip=True)) != LEGAL:
        raise ValueError('yes123 employer profile identity invalid')
    links = [urlsplit(a['href']) for a in soup.find_all('a', href=True)]
    if not any(p.scheme in {'https', 'http'} and p.netloc in {'www.tigerairtw.com', 'tigerairtw.com'}
               and p.path in {'', '/'} and not p.query and not p.fragment for p in links):
        raise ValueError('yes123 official employer backlink missing')
    pages = re.findall(r'第([1-9][0-9]*)/([1-9][0-9]*)頁', soup.get_text())
    if (len(pages) not in (1, 2) or len(set(pages)) != 1
            or pages[0][0] != '1' or not 1 <= int(pages[0][1]) <= 100):
        raise ValueError('yes123 current first listing page unverified')
    cards = soup.select('.Job_opening a.Job_opening_block[href]')
    if not 1 <= len(cards) <= 30:
        raise ValueError('yes123 listing incomplete or empty')
    jobs, seen = [], set()
    for card in cards:
        url = canonical_detail_url(urljoin(PROFILE, card['href']))
        title = _text(_one(card.select('.Job_opening_item_title h4')).get_text(' ', strip=True))
        if url in seen or not 2 <= len(title) <= 200:
            raise ValueError('yes123 duplicate or invalid published posting')
        seen.add(url)
        jobs.append({'url': url, 'title': title})
    return {'selected': jobs[:MAX_POSTINGS], 'observed_first_page_jobs': len(jobs),
            'page_count': int(pages[0][1]), 'all_company_job_count': None}


def _day(value):
    if not isinstance(value, str) or not (m := re.fullmatch(r'([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})', value)):
        raise ValueError('yes123 absolute portal date missing')
    return date(*map(int, m.groups()))


def _field(soup, label):
    node = _one([v for v in soup.select('.left_title') if _text(v.get_text()) == label])
    value = node.find_next_sibling()
    if value is None or value.name != 'span' or 'right_main' not in value.get('class', []):
        raise ValueError('yes123 posting field body invalid')
    return _text(value.get_text(' ', strip=True))


def parse_detail(raw, candidate, *, observed_at, now):
    if (type(observed_at) not in (int, float) or type(now) not in (int, float)
            or not math.isfinite(observed_at) or not math.isfinite(now)
            or not 0 <= now - observed_at < TTL):
        raise ValueError('yes123 original observation is not current')
    url = canonical_detail_url(candidate['url'])
    soup = _soup(raw)
    job = _json(_one(soup.find_all('script', type='application/ld+json')).get_text())
    title = _text(_one(soup.find_all('h1')).get_text(' ', strip=True))
    if (job.get('@type') != 'JobPosting' or job.get('@context') not in {'http://schema.org', 'https://schema.org'}
            or title != candidate['title'] or job.get('title') != title
            or job['hiringOrganization'].get('@type') != 'Organization'
            or job['hiringOrganization'].get('name') != LEGAL
            or job['hiringOrganization'].get('sameAs') != PROFILE):
        raise ValueError('yes123 exact detail identity invalid')
    employer_links = [a for a in soup.find_all('a', href=True)
                      if urljoin(url, a['href']) == PROFILE and _text(a.get_text()) == LEGAL]
    if len(employer_links) != 1:
        raise ValueError('yes123 detail employer action missing')
    observed_day = datetime.fromtimestamp(observed_at, TZ).date()
    today = datetime.fromtimestamp(now, TZ).date()
    updated, expiry = _day(job['datePosted']), _day(job['validThrough'])
    labels = [v.get_text(strip=True) for v in soup.find_all('h2')
              if v.get_text(strip=True).startswith('職缺更新：')]
    label = _one(labels).removeprefix('職缺更新：')
    if label == '今天':
        offset = 0
    elif label == '昨天':
        offset = 1
    elif re.fullmatch(r'[2-9]天前|[12][0-9]天前|30天前', label):
        offset = int(label.removesuffix('天前'))
    else:
        raise ValueError('yes123 visible update date unknown')
    if (updated != observed_day - timedelta(days=offset) or not 0 <= (today - updated).days <= 30
            or not today < expiry or not 0 < (expiry - observed_day).days <= 370):
        raise ValueError('yes123 portal update or expiry qualification failed')
    ident = parse_qs(urlsplit(url).query)['job_id'][0]
    apply = []
    for a in soup.find_all('a', href=True):
        if _text(a.get_text()) != '我要應徵':
            continue
        p = urlsplit(urljoin(url, a['href'])); q = parse_qs(p.query, keep_blank_values=True)
        if (p.scheme == 'https' and p.netloc == 'www.yes123.com.tw'
                and p.path == '/admin/sel_job_to_apply.asp' and not p.fragment
                and q == {'todo': ['mail2'], 'fancy': ['yes'], 'sel_id': [ident]}):
            apply.append(urljoin(url, a['href']))
        else:
            raise ValueError('yes123 conflicting application action')
    # The native desktop/mobile layout repeats the same action twice.
    # These are one posting, never two observations or two vacancies.
    if len(apply) not in (1, 2) or len(set(apply)) != 1:
        raise ValueError('yes123 current application action unverified')
    content = _field(soup, '工作內容：')
    if not 15 <= len(content) <= 8000 or content not in _text(unescape(job.get('description', ''))):
        raise ValueError('yes123 complete work-content correspondence failed')
    demand = _field(soup, '需求人數：')
    return {'job_id': ident, 'company_name': LEGAL, 'title': title, 'url': url,
            'last_updated_date': updated.isoformat(), 'first_publication_date': None,
            'date_basis': 'portal_update_not_original_first_publication',
            'portal_valid_through': expiry.isoformat(), 'employer_application_deadline': None,
            'expiry_basis': 'portal_structured_listing_validity_not_employer_deadline',
            'description': content, 'declared_demand_text': demand,
            'current_listing_and_apply_action_observed': True}
