"""Bounded Federal Reserve RSS metadata; never issuer events or article bodies."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from xml.etree import ElementTree

FEED_URL = 'https://www.federalreserve.gov/feeds/press_monetary.xml'

def parse_policy_feed(raw: bytes, *, tag: str, now: datetime, lookback_days: int = 7) -> list[dict]:
    if tag not in {'macro', 'rates_fx'} or type(raw) is not bytes or not 0 < len(raw) <= 1_000_000:
        return []
    if now.tzinfo is None or type(lookback_days) is not int or not 1 <= lookback_days <= 7:
        return []
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        return []
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return []
    if root.tag != 'rss' or len(root.findall('./channel')) != 1:
        return []
    items = root.findall('./channel/item')
    if len(items) > 500:
        return []
    kept, seen = [], set()
    for item in items:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        stamp = (item.findtext('pubDate') or '').strip()
        if not title or len(title) > 1000 or not re.fullmatch(r'https://www\.federalreserve\.gov/newsevents/pressreleases/monetary20\d{6}[a-z]\.htm', link):
            continue
        try:
            date = parsedate_to_datetime(stamp)
            if date.tzinfo is None:
                continue
            age = (now - date).total_seconds()
        except (TypeError, ValueError, OverflowError):
            continue
        if not 0 <= age <= lookback_days * 86400 or link in seen:
            continue
        seen.add(link)
        kept.append({'tag': tag, 'headline': title, 'summary': 'Federal Reserve monetary-policy release metadata',
                     'published_at': date.astimezone(timezone.utc).isoformat(), 'source': 'Federal Reserve Monetary Policy RSS',
                     'url': link, 'evidence_coverage': 'headline_metadata_only', 'article_body_verified': False,
                     'published_at_basis': 'official_rss_pubDate', 'event_date': None, 'event_date_verified': False,
                     'event_date_basis': 'not_established_by_news_metadata'})
        if len(kept) == 3:
            break
    return kept
