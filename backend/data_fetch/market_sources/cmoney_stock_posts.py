"""Bounded public CMoney stock-page fallback for individually verified forum posts.

The stock landing page is only a candidate index. A post is usable only when
its own page names exactly one stock, matches the index time, and contains
visible original post text. No login, embedded session state, or private API
is used. These are discussion samples, never a sentiment score.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import re
import time
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from bounded_curl_process import collect_capped_process


PROVIDER = "CMoney 股市爆料同學會"
STOCK_URL = "https://forum-web.cmoney.tw/stocks/{ticker}"
FINANCE_URL = "https://www.cmoney.tw/finance/{ticker}/f00025"
ARTICLE_URL = re.compile(r"https://www\.cmoney\.tw/forum/article/[0-9]{6,12}\Z")
# The same exact public issuer name must survive both indexes and the original
# post tag. Recognize the exchange affixes, without accepting arbitrary Latin
# names or chained suffixes as an issuer identity.
COMPANY_NAME = r"[\u3400-\u9fff][\u3400-\u9fff*\-]{1,14}(?:-(?:KY|DR))?"
PAGE_TITLE = re.compile(r"(?P<ticker>[0-9]{4}) (?P<company>" + COMPANY_NAME + r") 的模範同學觀點與討論｜股市爆料同學會")
STOCK_TAG = re.compile(r"(?P<ticker>[0-9]{4})(?P<company>" + COMPANY_NAME + r")\Z")
LOCAL_DATE = re.compile(r"(?P<y>[0-9]{4})-(?P<m>[0-9]{1,2})-(?P<d>[0-9]{1,2})T(?P<h>[0-9]{1,2}):(?P<min>[0-9]{1,2}):(?P<s>[0-9]{1,2})(?P<tz>[+-][0-9]{2}:[0-9]{2})\Z")
MAX_BYTES = 1_000_000
MAX_ARTICLES = 3
MAX_FINANCE_CANDIDATES = 5
ACQUISITION_SECONDS = 12
MAX_REFERENCE_ATTEMPTS = 1
TEXT_URL = re.compile(r"https?://[^\s<>\"']+", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except ValueError:
        match = LOCAL_DATE.fullmatch(value)
        if not match:
            return None
        try:
            parts = match.groupdict()
            zone = parts["tz"]
            offset = (int(zone[1:3]) * 60 + int(zone[4:6])) * (1 if zone[0] == "+" else -1)
            return datetime(int(parts["y"]), int(parts["m"]), int(parts["d"]), int(parts["h"]),
                            int(parts["min"]), int(parts["s"]),
                            tzinfo=timezone(timedelta(minutes=offset))).astimezone(timezone.utc)
        except ValueError:
            return None


def _recent(stamp: datetime | None, now: datetime) -> bool:
    return stamp is not None and timedelta(0) <= now - stamp <= timedelta(days=30)


def parse_stock_listing(raw: bytes, ticker: str, *, now: datetime | None = None) -> tuple[str, list[tuple[str, datetime]]]:
    now = now or datetime.now(timezone.utc)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or not re.fullmatch(r"[0-9]{4}", ticker):
        return "", []
    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    identity = PAGE_TITLE.fullmatch(title)
    if not identity or identity.group("ticker") != ticker:
        return "", []
    company = identity.group("company")
    candidates = []
    seen = set()
    for anchor in soup.select('a.sv-disc-row-link[href*="/forum/article/"]'):
        url = anchor.get("href")
        clock = anchor.select_one("time[datetime]")
        stamp = _date(clock.get("datetime")) if clock else None
        if not isinstance(url, str) or not ARTICLE_URL.fullmatch(url) or not _recent(stamp, now) or url in seen:
            continue
        seen.add(url)
        candidates.append((url, stamp))
        if len(candidates) >= MAX_ARTICLES:
            break
    return company, candidates


def parse_finance_listing(raw: bytes, ticker: str) -> tuple[str, list[tuple[str, None]]]:
    """Use the public stock overview only to discover original forum URLs.

    Its relative times are not publication evidence. The linked article must
    independently provide a recent timestamp, exact stock tag, and body.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or not re.fullmatch(r"[0-9]{4}", ticker):
        return "", []
    try:
        page = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "", []
    title = re.search(r"<title>([^<]+)</title>", page, re.I)
    identity = re.fullmatch(r"(" + COMPANY_NAME + r")\(" + ticker +
                            r"\) 個股概覽 \| 個股 - 股市", title.group(1).strip()) if title else None
    if not identity:
        return "", []
    company = identity.group(1)
    block = re.search(r'<li\s+id="ForumBlock"\s+stockId="' + ticker + r'"[^>]*>', page)
    if not block:
        return "", []
    section = page[block.end():]
    if not re.search(r'<span\s+class="page-list-title__stockName">' + re.escape(company) + r'</span>討論區', section[:1000]):
        return "", []
    listing = re.search(r'<ul\s+class="comment-list"\s+id="ArticleList">|<ul\s+id="ArticleList">', section)
    if not listing:
        return "", []
    section = section[listing.end():]
    ending = section.find("</article>")
    if ending < 0:
        return "", []
    section = section[:ending]
    blocks = list(re.finditer(r'<li\s+grp="articleBlock"\s+articleId="([0-9]{6,12})"', section))
    candidates = []
    for index, match in enumerate(blocks[:MAX_FINANCE_CANDIDATES]):
        article_id = match.group(1)
        ending = blocks[index + 1].start() if index + 1 < len(blocks) else len(section)
        if re.search(r'href="/forum/article/' + article_id + r'"', section[match.end():ending]):
            candidates.append((f"https://www.cmoney.tw/forum/article/{article_id}", None))
    return company, candidates


def parse_stock_article(raw: bytes, ticker: str, company: str, candidate: tuple[str, datetime | None],
                        *, now: datetime | None = None) -> dict | None:
    now = now or datetime.now(timezone.utc)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or not re.fullmatch(r"[0-9]{4}", ticker):
        return None
    url, listed = candidate
    if not ARTICLE_URL.fullmatch(url) or (listed is not None and not _recent(listed, now)):
        return None
    soup = BeautifulSoup(raw, "html.parser")
    tags = [item.get("content", "").strip() for item in soup.select('meta[property="article:tag"]')]
    if not tags or tags[0] != ticker + company or len(tags) > 3 or len(tags) != len(set(tags)):
        return None
    tagged = [STOCK_TAG.fullmatch(tag) for tag in tags]
    if any(match is None for match in tagged):
        return None
    published_meta = soup.select_one('meta[property="article:published_time"]')
    published = _date(published_meta.get("content")) if published_meta else None
    if not _recent(published, now) or (listed is not None and abs(published - listed) > timedelta(minutes=1)):
        return None
    heading = soup.select_one("h2.articleTags__text")
    heading_text = heading.get_text(" ", strip=True) if heading else ""
    body = soup.select_one("pre.textRule__text")
    body_text = body.get_text(" ", strip=True) if body else ""
    if company not in heading_text or len(body_text) < 5 or len(body_text) > 5000 or re.search(r"https?://|www\.", body_text, re.I):
        return None
    if len(tags) > 1:
        # A platform tag is only an index hint. Require the target to be the
        # first tag and the only tagged issuer discussed in the original text.
        # Another tagged issuer may omit its market affix in natural prose.
        # This is an exclusion check, never an extra target identity alias.
        if company not in body_text or any(
            re.sub(r"-(?:KY|DR)\Z", "", match.group("company")) in body_text
            or re.search(r"(?<!\d)" + match.group("ticker") + r"(?!\d)", body_text)
            for match in tagged[1:]
        ):
            return None
    headline_meta = soup.select_one('meta[property="og:title"]')
    headline = headline_meta.get("content", "").strip() if headline_meta else ""
    title = headline if company in headline else heading_text
    record = {"title": title[:200], "date": published.isoformat(), "source": PROVIDER,
            "link": url, "text": body_text, "source_tag": tags[0], "source_tags": tags,
            "source_listing": (STOCK_URL if listed is not None else FINANCE_URL).format(ticker=ticker),
            "evidence_kind": "explicit_target_multitag_forum_post" if len(tags) > 1 else "single_stock_forum_post",
            "response_sha256": sha256(raw).hexdigest(), "response_bytes": len(raw),
            "parser_version": "cmoney-stock-posts-v2",
            "sentiment_assessment": "not_assessed"}
    if ticker == "5314" and company == "世紀*" and tags == ["5314世紀*"]:
        from .cmoney_stock_context import BASIS, build_stock_context
        record["issuer_evidence_basis"] = BASIS
        record["cmoney_stock_context"] = build_stock_context(record, heading=heading_text)
    return record


def _download(url: str, *, deadline: float | None = None) -> bytes:
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        raise RuntimeError("network disabled for tests")
    if not (url.startswith("https://forum-web.cmoney.tw/stocks/")
            or re.fullmatch(r"https://www\.cmoney\.tw/finance/[0-9]{4}/f00025", url)
            or ARTICLE_URL.fullmatch(url)):
        raise ValueError("unsupported forum URL")
    remaining = min(9.0, (deadline - time.monotonic()) if deadline is not None else 9.0)
    if remaining < 0.1:
        raise TimeoutError("forum acquisition deadline exhausted")
    argv = ["/usr/bin/curl", "--disable", "--silent", "--show-error", "--fail-with-body",
            "--max-time", str(remaining), "--connect-timeout", str(min(4.0, remaining)), "--max-filesize", str(MAX_BYTES),
            "--proto", "=https", "--max-redirs", "0", "--retry", "0",
            "--dump-header", "/dev/fd/{HEADER_FD}",
            "--write-out", "%{stderr}\nSTOCK_AGENT_CURL_META:%{json}\n", url]
    parts, rc, error = collect_capped_process(argv, min(time.monotonic() + 10, deadline) if deadline is not None else time.monotonic() + 10,
                                              body_limit=MAX_BYTES, headers=True)
    from cmoney_transport_receipts import observe_download
    observe_download(url, parts, rc, error, max_bytes=MAX_BYTES)
    if error or rc != 0 or not 0 < len(parts["body"]) <= MAX_BYTES:
        raise RuntimeError(error or "forum HTTP response unavailable")
    return parts["body"]


def _stock_reference(raw: bytes, ticker: str, company: str, candidate: tuple[str, datetime | None],
                     *, now: datetime) -> dict | None:
    """A dated single-stock reshare is an index hint, never an admitted post.

    Follow only one public original on this same host. The referenced original
    must independently pass parse_stock_article; no recursive discovery occurs.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        return None
    parent, listed = candidate
    if not ARTICLE_URL.fullmatch(parent):
        return None
    soup = BeautifulSoup(raw, "html.parser")
    tags = [item.get("content", "").strip() for item in soup.select('meta[property="article:tag"]')]
    if tags != [ticker + company] or not STOCK_TAG.fullmatch(tags[0]):
        return None
    clock = soup.select_one('meta[property="article:published_time"]')
    published = _date(clock.get("content")) if clock else None
    if not _recent(published, now) or (listed is not None and (
            not _recent(listed, now) or abs(published - listed) > timedelta(minutes=1))):
        return None
    heading = soup.select_one("h2.articleTags__text")
    body = soup.select_one("pre.textRule__text")
    text = body.get_text(" ", strip=True) if body else ""
    if not heading or company not in heading.get_text(" ", strip=True) or len(text) > 5000:
        return None
    links = TEXT_URL.findall(text)
    if len(links) != 1 or len(TEXT_URL.sub("", text).strip()) < 5:
        return None
    if re.search(r"https?://|www\.", TEXT_URL.sub("", text), re.I):
        return None
    anchors = body.select("a[href]")
    if len(anchors) > 1 or any(not isinstance(anchor.get("href"), str)
                             or anchor["href"].strip() != links[0] for anchor in anchors):
        return None
    try:
        parts = urlsplit(links[0])
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    if parts.scheme != "https" or parts.netloc != "www.cmoney.tw" or parts.fragment:
        return None
    if any(key not in {"utm_source", "utm_medium"} or values != [
            "forum_app" if key == "utm_source" else "share"] for key, values in query.items()):
        return None
    url = "https://www.cmoney.tw" + parts.path
    if not ARTICLE_URL.fullmatch(url) or url == parent:
        return None
    return {"url": url, "parent": parent, "parent_date": published.isoformat(),
            "parent_sha256": sha256(raw).hexdigest()}


def fetch_cmoney_stock_posts(ticker: str) -> list[dict]:
    if not re.fullmatch(r"[0-9]{4}", ticker) or os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        return []
    now = _now()
    deadline = time.monotonic() + ACQUISITION_SECONDS
    failed_originals = []
    retry_urls = set()
    original_bytes = {}
    reference_attempts = 0

    def read_original(url: str) -> bytes:
        # At most five finance, three stock-index and one reference URL. Reuse
        # completed bytes, then reapply each candidate's own company/time gate.
        # Failed transports are not cached and retain the existing recovery.
        if url not in original_bytes:
            original_bytes[url] = _download(url, deadline=deadline)
        return original_bytes[url]
    for listing_url, parse in ((FINANCE_URL, lambda raw: parse_finance_listing(raw, ticker)),
                               (STOCK_URL, lambda raw: parse_stock_listing(raw, ticker, now=now))):
        rows = []
        accepted_urls = set()
        try:
            company, candidates = parse(_download(listing_url.format(ticker=ticker), deadline=deadline))
            for candidate in candidates:
                if candidate[0] in accepted_urls:
                    continue
                try:
                    raw = read_original(candidate[0])
                except RuntimeError:
                    # The index already supplied an original URL. A transient
                    # transport failure is different from rejected article
                    # content; make one recovery pass after the other index.
                    if candidate[0] not in retry_urls:
                        failed_originals.append((company, candidate))
                        retry_urls.add(candidate[0])
                    continue
                except (ValueError, TimeoutError):
                    continue
                record = parse_stock_article(raw, ticker, company, candidate, now=now)
                if record is None and not rows and reference_attempts < MAX_REFERENCE_ATTEMPTS:
                    reference = _stock_reference(raw, ticker, company, candidate, now=now)
                    if reference and deadline - time.monotonic() >= 0.1:
                        reference_attempts += 1
                        try:
                            original = read_original(reference["url"])
                            record = parse_stock_article(original, ticker, company, (reference["url"], None), now=now)
                            if record:
                                record.update(source_discovery_kind="same_stock_original_reference",
                                              discovered_from=reference["parent"],
                                              discovery_parent_date=reference["parent_date"],
                                              discovery_parent_response_sha256=reference["parent_sha256"],
                                              discovery_parser_version="cmoney-stock-reference-v1")
                        except (RuntimeError, ValueError, TimeoutError):
                            pass
                if record:
                    accepted_urls.add(record["link"])
                    rows.append(record)
                    if len(rows) >= MAX_ARTICLES:
                        break
            if rows:
                return rows
        except (RuntimeError, ValueError, TimeoutError):
            continue
    recovered = []
    for company, candidate in failed_originals[:MAX_FINANCE_CANDIDATES]:
        if deadline - time.monotonic() < 0.1:
            break
        try:
            record = parse_stock_article(read_original(candidate[0]),
                                         ticker, company, candidate, now=now)
            if record:
                recovered.append(record)
                if len(recovered) >= MAX_ARTICLES:
                    break
        except (RuntimeError, ValueError, TimeoutError):
            continue
    if recovered:
        return recovered
    return []
