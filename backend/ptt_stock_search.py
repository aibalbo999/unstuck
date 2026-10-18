"""Bounded official PTT title search with authoritative article timestamps."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import re
from urllib.parse import quote_plus, urlsplit

from bs4 import BeautifulSoup
from news_record_utils import canonical_link, clean_text, news_record
from search_provider_runtime import SourceResponseError

SEARCH_URL = 'https://www.ptt.cc/bbs/Stock/search'
ARTICLE_PATH = re.compile(r'^/bbs/Stock/M\.(\d{10})\.A\.[A-Fa-f0-9]+\.html$')
PARSER_VERSION = 'ptt-search-v4'
MAX_BODY_EXCERPT_CHARS = 2000


def _matches(title, term):
    return bool(re.search(r'(?<!\d)' + re.escape(term) + r'(?!\d)', title)) if term.isdigit() else term.casefold() in title.casefold()


def _author_body(main, link):
    """Keep original body evidence separate from handles, pushes and footer."""
    body = deepcopy(main)
    for node in body.select('.article-metaline, .article-metaline-right, .push'):
        node.decompose()
    for br in body.find_all('br'):
        br.replace_with('\n')
    # Decide structure before flattening text. A quoted ': ※ 發信站' is
    # author content; only an unquoted station plus this article's URL is its
    # platform footer. Quoter handles are metadata, not issuer evidence.
    lines = body.get_text('', strip=False).splitlines()
    station = re.compile(r'^※\s*發信站\s*:\s*批踢踢實業坊\(ptt\.cc\)(?:[,，]|$)')
    article_url = re.compile(r'^※\s*文章網址\s*:\s*' + re.escape(link) + r'\s*$')
    for index, line in enumerate(lines):
        if station.match(line.strip()) and any(
                article_url.fullmatch(value.strip()) for value in lines[index + 1:index + 7]):
            lines = lines[:index]
            break
    attribution = re.compile(r'^\s*(?:[>:：]\s*)*※\s*引述\s*《.*》\s*之銘言\s*[:：]\s*$')
    text = re.sub(r'\s+', ' ', '\n'.join(line for line in lines if not attribution.fullmatch(line))).strip()
    return re.sub(r'\s*--\s*$', '', text).strip()


def acquire_recent_posts(term, limit, *, get, headers, now, deadline, clock):
    """One search plus at most five articles; require corroborated dates."""
    diagnostics = {'parser_version': PARSER_VERSION, 'raw_count': 0, 'usable_count': 0,
                   'rejected_count': 0, 'rejected_reason_counts': {}, 'component_statuses': {}}
    reasons = Counter()
    lower = now - timedelta(days=30)
    components = diagnostics['component_statuses']

    def reject(reason):
        reasons[reason] += 1
        diagnostics.update(rejected_count=sum(reasons.values()), rejected_reason_counts=dict(reasons))

    def receipt(response, url, component):
        raw = getattr(response, 'content', None)
        raw = raw if isinstance(raw, bytes) else response.text.encode()
        components[component] = {'provider': 'PTT Stock', 'series_id': url,
                                 'http_status': getattr(response, 'status_code', None),
                                 'response_sha256': hashlib.sha256(raw).hexdigest(),
                                 'response_bytes': len(raw), 'parser_version': PARSER_VERSION}

    def request(url, component):
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('PTT acquisition deadline exhausted')
        try:
            response = get(url, headers=headers, timeout=remaining, provider='PTT Stock')
        except Exception as exc:
            if getattr(exc, 'response', None) is not None:
                receipt(exc.response, url, component)
            raise
        receipt(response, url, component)
        if clock() >= deadline:
            raise TimeoutError('PTT acquisition deadline exhausted')
        return response

    try:
        response = request(SEARCH_URL + '?q=' + quote_plus(term), 'search')
        soup = BeautifulSoup(response.text, 'html.parser')
        if not soup.select('div.r-ent, div.r-list-container'):
            raise SourceResponseError('parse_error', status_code=getattr(response, 'status_code', None),
                                      response_text=response.text, parser_version=PARSER_VERSION)
        candidates, seen = [], set()
        for row in soup.select('div.r-ent'):
            anchor = row.select_one('div.title a')
            if anchor is None:
                continue
            diagnostics['raw_count'] += 1
            title = clean_text(anchor.get_text(' ', strip=True))
            if not _matches(title, term):
                reject('ticker_mismatch')
                continue
            link = canonical_link(anchor.get('href'), SEARCH_URL)
            parsed = urlsplit(link)
            match = ARTICLE_PATH.fullmatch(parsed.path)
            if parsed.scheme != 'https' or parsed.netloc != 'www.ptt.cc' or not match or parsed.query:
                reject('invalid_article_url')
                continue
            # URL creation time bounds candidates; missing article metadata needs
            # matching index date, platform footer, and ticker text below.
            created = datetime.fromtimestamp(int(match[1]), now.tzinfo)
            if created < lower or created > now:
                reject('historical_candidate' if created < lower else 'future_candidate')
                continue
            if link in seen:
                reject('duplicate_candidate')
                continue
            seen.add(link)
            index_date = row.select_one('div.date')
            listed_date = clean_text(index_date.get_text()) if index_date is not None else ''
            candidates.append((link, created, listed_date, title))
        records = []
        for index, (link, created, listed_date, index_title) in enumerate(candidates[:min(limit, 5)], start=1):
            component = f'article_{index}'
            response = request(link, component)
            soup = BeautifulSoup(response.text, 'html.parser')
            main = soup.select_one('#main-content')
            if main is None:
                raise SourceResponseError('parse_error', status_code=getattr(response, 'status_code', None),
                                          response_text=response.text, parser_version=PARSER_VERSION)
            meta = {}
            for line in soup.select('.article-metaline'):
                key, value = line.select_one('.article-meta-tag'), line.select_one('.article-meta-value')
                if key is not None and value is not None:
                    meta[clean_text(key.get_text())] = clean_text(value.get_text())
            try:
                stamp = datetime.strptime(meta.get('時間', ''), '%a %b %d %H:%M:%S %Y').replace(tzinfo=now.tzinfo)
            except ValueError:
                stamp = None
            title = meta.get('標題', '')
            if stamp is None:
                body = main.get_text(' ', strip=True)
                platform_footer = re.search(
                    r'※\s*發信站:\s*批踢踢實業坊\(ptt\.cc\).*?※\s*文章網址:\s*'
                    + re.escape(link) + r'(?=\s|$)', body, re.S)
                listed = re.fullmatch(r'(\d{1,2})/(\d{1,2})', listed_date)
                if (listed and (int(listed[1]), int(listed[2])) == (created.month, created.day)
                        and platform_footer and _matches(body[:500], term)
                        and (not title or _matches(title, term))):
                    stamp = created
                    title = title or index_title
                    components[component]['date_basis'] = 'ptt_url_index_article_footer'
            reason = ('unknown_date' if stamp is None else 'historical' if stamp < lower else
                      'future' if stamp > now else 'ticker_mismatch' if not _matches(title, term) else '')
            if reason:
                reject(reason)
                components[component]['reason_code'] = reason
                continue
            record = news_record(title=title, link=link, published_date=stamp.isoformat(),
                                 source='PTT Stock', summary=title)
            if record:
                body = _author_body(main, link)
                record.update(
                    text=body[:MAX_BODY_EXCERPT_CHARS],
                    text_truncated=len(body) > MAX_BODY_EXCERPT_CHARS,
                    body_text_chars=len(body),
                    body_text_sha256=hashlib.sha256(body.encode()).hexdigest(),
                    response_sha256=components[component]['response_sha256'],
                    response_bytes=components[component]['response_bytes'],
                    parser_version=PARSER_VERSION,
                )
                records.append(record)
        diagnostics.update(usable_count=len(records), retrieval_status='records_received' if records else 'no_records')
        diagnostics['http_status'] = components['search']['http_status']
        return records, diagnostics
    except Exception as exc:
        exc.acquisition_details = diagnostics
        raise
