"""Fixed public TCC sections: article dates never come from related news."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from news_record_utils import clean_text

INDEX = "https://www.tccgroupholdings.com/news"
ARTICLE = re.compile(r"https://www\.tccgroupholdings\.com/news/[A-Za-z0-9_-]{1,80}\Z")
MAX_BYTES = 600_000


def _page(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("tcc_response_size_invalid")
    soup = BeautifulSoup(raw.decode("utf-8", errors="strict"), "html.parser")
    mains = soup.find_all("main")
    if len(mains) != 1:
        raise ValueError("tcc_article_section_invalid")
    return mains[0]


def parse_tcc_index(raw):
    main = _page(raw)
    anchors = main.select("a.group.block[href], a.m-btn--fill[href]")
    if not 1 <= len(anchors) <= 50:
        raise ValueError("tcc_index_invalid")
    rows, seen = [], {}
    for anchor in anchors:
        url = str(anchor["href"])
        if not ARTICLE.fullmatch(url):
            raise ValueError("tcc_index_route_invalid")
        feature = "m-btn--fill" in anchor.get("class", [])
        section = anchor.parent if feature else anchor
        titles = section.select(":scope > h2" if feature else ":scope > div.heading-5")
        dates = section.select(":scope > p.font-arial" if feature else ":scope > div.font-arial")
        if len(titles) != 1 or len(dates) != 1:
            raise ValueError("tcc_index_fields_invalid")
        row = {"url": url, "name": clean_text(titles[0]), "date_original": clean_text(dates[0])}
        if not 1 <= len(row["name"]) <= 500:
            raise ValueError("tcc_index_title_invalid")
        if url in seen:
            if row != seen[url]:
                raise ValueError("tcc_index_duplicate_conflict")
            continue
        seen[url] = row
        rows.append(row)
    return rows


def parse_tcc_article(raw, listed):
    if not ARTICLE.fullmatch(str(listed.get("url") or "")):
        raise ValueError("tcc_article_route_invalid")
    main = _page(raw)
    headers = [h for h in main.find_all("h2")
               if len(h.parent.find_all("a", href=INDEX)) == 1]
    bodies = main.select("div.editorPanel")
    if len(headers) != 1 or len(bodies) != 1:
        raise ValueError("tcc_article_fields_invalid")
    header = headers[0]
    dates = header.parent.select(":scope > p.font-arial")
    if (len(dates) != 1 or clean_text(header) != listed["name"]
            or clean_text(dates[0]) != listed["date_original"]):
        raise ValueError("article_index_detail_mismatch")
    if bodies[0].find(["script", "iframe", "object"]):
        raise ValueError("tcc_article_content_invalid")
    return clean_text(header), clean_text(bodies[0])
