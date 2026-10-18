"""Published group statements that explicitly concern the listed Yulon issuer.

The group directory proves the publisher's claimed member relationship, not
ownership, consolidation, endorsement, or an independent news publisher.
"""
from datetime import date
import re

DIRECTORY = 'https://www.yulon-group.com/smart-transportation'
INDEX = 'https://www.yulon-group.com/news-list/35e09dd589fa639ffe18507f70fecbd0'
PROFILE = dict(short_name='裕隆', legal_name='裕隆汽車製造股份有限公司',
               english_name='Yulon Motor Company Ltd.', ubn='03489200',
               english_alias='YL', website='www.yulon-motor.com.tw',
               host='www.yulon-motor.com.tw', publisher='Yulon Group',
               index=INDEX, identity_url=DIRECTORY)
MONTHS = ('Jan.', 'Feb.', 'Mar.', 'Apr.', 'May.', 'Jun.',
          'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.')


def article_id(url):
    match = re.fullmatch(r'https://www\.yulon-group\.com/news-list/view/([A-Za-z0-9]{12})', str(url))
    return match[1] if match else None


def owner(soup):
    from .registered_issuer_articles import _clean
    nodes = soup.select('footer p.copyright')
    if len(nodes) != 1 or _clean(nodes[0]) != '© 2021 裕隆集團 All rights reserved.':
        raise ValueError('yulon_group_publisher_unverified')


def validate_directory(raw):
    from .registered_issuer_articles import _page, _clean
    soup = _page(raw)
    owner(soup)
    cards = soup.select('a.wisdom-link[href="https://www.yulon-motor.com.tw/"]')
    if len(cards) != 1:
        raise ValueError('yulon_group_member_link_unverified')
    names = cards[0].select('h4.wisdom-title')
    english = cards[0].select('h5.en-title')
    if (len(names) != 2 or any(_clean(n) != '裕隆汽車' for n in names)
            or len(english) != 2 or any(_clean(n) != 'Yulon Motor' for n in english)):
        raise ValueError('yulon_group_member_identity_unverified')


def day(text):
    match = re.fullmatch(r'(20\d{2}) ([A-Z][a-z]{2}\.) (\d{2})', text)
    if not match or match[2] not in MONTHS:
        raise ValueError('yulon_group_publication_date_invalid')
    return date(int(match[1]), MONTHS.index(match[2])+1, int(match[3])).isoformat()


def parse_index(soup):
    from .registered_issuer_articles import _clean
    owner(soup)
    roots = soup.select('div.main-content-block > ul.news-list')
    if len(roots) != 1:
        raise ValueError('yulon_group_index_section_invalid')
    cards = roots[0].select(':scope > li.item > a.news-link[href]')
    if not 1 <= len(cards) <= 100:
        raise ValueError('yulon_group_index_count_invalid')
    rows = []
    for card in cards:
        titles = card.select('h2.news-title')
        stamps = card.select('span.news-date')
        summaries = card.select('p.news-text')
        if (len(titles) != 1 or len(stamps) != 1 or len(summaries) != 1
                or not article_id(card['href'])):
            raise ValueError('yulon_group_index_fields_invalid')
        title, summary = _clean(titles[0]), _clean(summaries[0])
        published = day(_clean(stamps[0]))
        # "裕隆集團", other listed group members and a shopping mall alone do
        # not identify the 2201 issuer. Never infer parent revenue from them.
        if '裕隆汽車' not in title + ' ' + summary:
            continue
        rows.append({'url': card['href'], 'title': title, 'date_original': published})
    return rows


def parse_article(soup, listed):
    from .registered_issuer_articles import _clean
    owner(soup)
    titles = soup.select('div.content-header h1.content-title')
    stamps = soup.select('div.content-header span.news-date')
    blocks = soup.select('body.news-content > div.body-container > div.editor-block')
    if len(titles) != 1 or len(stamps) != 1 or len(blocks) != 1:
        raise ValueError('yulon_group_article_section_invalid')
    block = blocks[0]
    if block.find(['script', 'iframe', 'object', 'form', 'audio', 'video', 'table']):
        raise ValueError('yulon_group_article_text_scope_unverified')
    title, body, stamp = _clean(titles[0]), _clean(block), _clean(stamps[0])
    if (title != listed['title'] or day(stamp) != listed['date_original']
            or '裕隆汽車' not in body or not 100 <= len(body) <= 12000):
        raise ValueError('yulon_group_article_subject_date_or_body_invalid')
    return title, body, {'date': day(stamp), 'group_article_date': stamp,
        'index_card_date': listed['date_original'], 'image_count': len(block.find_all('img')),
        'images_independently_verified': False,
        'original_issuer_publication_date_verified': False,
        'event_date_independently_verified': False}


def record_fields():
    return {'source': '裕隆集團官網', 'source_type': 'group_published_issuer_news',
            'source_role': 'related_group_statement',
            'publication_date_basis': 'group_page_displayed_day',
            'source_scope_caution': '集團發布且明確提及裕隆汽車；不是獨立報導。刊登日不等於活動日或首次發布日；集團其他公司的收入、資產與活動不得歸入裕隆汽車。'}


from .tcfhc_conference_transport import ConferenceHttp


class YulonNewsHttp(ConferenceHttp):
    """No HTTP response cache: all observed group pages require no-store.

    An immutable private audit archive is used only to replay source claims;
    it is never a substitute for the next collection's native HTTP request.
    """
    raw_cache_prefix = 'yulon-news-no-store:v1:'
    admission_prefix = 'yulon-news-admission:v1:'

    @staticmethod
    def route_contract(url):
        from search_provider_runtime import SourceResponseError
        if url in {DIRECTORY, INDEX} or article_id(url):
            return 500_000, {'text/html', 'application/xhtml+xml'}
        raise SourceResponseError('transport_url_invalid')

    def get_receipt(self, url):
        import base64
        import time
        from hashlib import sha256
        from search_admission import endpoint_admission
        from search_provider_runtime import SourceResponseError, scope_key
        from .issuer_news_transport import PROVIDER
        limit, _ = self.route_contract(url)
        diagnostic = {'url': url, 'http_request_sent': False, 'cache_hit': False,
                      'stale': False, 'response_cache_policy': 'no-store'}
        self.components.append(diagnostic)

        def check():
            if time.monotonic() >= self.deadline:
                raise SourceResponseError('timeout')

        check()
        guard = scope_key(PROVIDER, endpoint='www.yulon-group.com')
        with endpoint_admission(guard, timeout_seconds=self.deadline-time.monotonic()) as owns:
            if not owns:
                raise SourceResponseError('single_flight_busy')
            check()
            value = self._download(url, diagnostic)
            check()
            if not owns():
                raise SourceResponseError('lease_lost')
            if (not isinstance(value, dict) or value.get('url') != url
                    or type(value.get('http_status')) is not int or value['http_status'] != 200
                    or value.get('request_method') != 'GET' or value.get('response_complete') is not True
                    or value.get('http_status_observed') is not True):
                raise SourceResponseError('original_unverified')
            encoded = value.get('body_b64')
            if not isinstance(encoded, str) or len(encoded) > (limit+2)//3*4:
                raise SourceResponseError('original_unverified')
            raw = base64.b64decode(encoded, validate=True)
            if not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value.get('sha256'):
                raise SourceResponseError('original_unverified')
            receipt = self.archive_original(raw, url, value)
            receipt.update(http_status_observed=True, request_method='GET', response_complete=True, cache_hit=False)
            if self.read_original(receipt, url, max_age=1800) != raw:
                raise SourceResponseError('original_unverified')
            diagnostic.update(fetched_at_epoch=value['fetched_at_epoch'], original_receipt=receipt,
                              http_status=200, http_status_observed=True)
        check()
        return raw, receipt
