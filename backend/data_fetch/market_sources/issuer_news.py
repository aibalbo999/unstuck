"""Dated first-party articles with exchange-backed, scoped issuer identity."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import re
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from news_record_utils import clean_text
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp, ROSTER_URL, SANYANG_INDEX, SINBON_INDEX, TCC_INDEX, VENTEC_INDEX, url_contract
from .official_company_legal_name import parse_roster, select_legal_name

POLICY = "first-party-issuer-news-v1"
PROVIDER = "Verified issuer news"
TAIPEI = ZoneInfo("Asia/Taipei")
PROFILES = {
    "2379.TW": {"short_name": "瑞昱", "legal_name": "瑞昱半導體股份有限公司",
                "english_alias": "RT", "host": "www.realtek.com",
                "index": "https://www.realtek.com/Article/News?lang=en-GB&app_id=18"},
    "2206.TW": {"short_name": "三陽工業", "legal_name": "三陽工業股份有限公司",
                "english_alias": "SYM", "host": "www.sanyang.com.tw", "index": SANYANG_INDEX},
    "3023.TW": {"short_name": "信邦", "legal_name": "信邦電子股份有限公司",
                "english_alias": "SINBON", "host": "www.sinbon.com", "index": SINBON_INDEX},
    "1101.TW": {"short_name": "台泥", "legal_name": "臺灣水泥股份有限公司",
                "english_alias": "TCC", "host": "www.tccgroupholdings.com", "index": TCC_INDEX,
                "website_paths": {"/tw/"}},
    "6672.TW": {"short_name": "騰輝電子-KY", "legal_name": "騰輝電子國際集團股份有限公司",
                "english_alias": "Ventec", "host": "www.ventec-group.com", "index": VENTEC_INDEX,
                "policy": "issuer-hosted-news-republication-v1"},
}


def _identity(raw, ticker, today):
    profile = PROFILES[ticker]
    parsed = parse_roster(raw, ".TW")
    anchor = select_legal_name(parsed, ticker, profile["short_name"], today=today)
    row = next((r for r in json.loads(raw) if str(r.get("公司代號")) == ticker.split(".")[0]), {})
    website = str(row.get("網址") or "").strip()
    target = urlsplit(website if "://" in website else "https://" + website)
    if (not anchor or anchor["legal_name"] != profile["legal_name"]
            or str(row.get("英文簡稱") or "").strip() != profile["english_alias"]
            or target.scheme not in {"http", "https"} or target.hostname != profile["host"] or target.username or target.password
            or target.port or target.path not in profile.get("website_paths", {"", "/"}) or target.query or target.fragment):
        raise ValueError("issuer_domain_identity_unverified")
    return {"ticker": ticker, "legal_name": anchor["legal_name"], "short_name": profile["short_name"],
            "english_alias": profile["english_alias"], "website_host": profile["host"],
            "master_observed_on": anchor["as_of"], "master_source_url": ROSTER_URL,
            "master_response_sha256": sha256(raw).hexdigest()}


def _article_date(value, ticker):
    if not isinstance(value, str):
        return None
    try:
        if ticker == "6672.TW":
            from .ventec_issuer_news import index_date
            return index_date(value)
        if ticker in {"3023.TW", "1101.TW"} and re.fullmatch(r"20\d{2}\.\d{2}\.\d{2}", value):
            return date.fromisoformat(value.replace(".", "-"))
        if ticker == "2206.TW" and re.fullmatch(r"[A-Z][a-z]{2} \d{2} 20\d{2}", value):
            return datetime.strptime(value, "%b %d %Y").date()
    except ValueError:
        pass
    return None


def _canonical_day(value):
    if isinstance(value, str) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0) and parsed.time().replace(tzinfo=None) == datetime.min.time():
            return parsed.date().isoformat()
    except (ValueError, TypeError):
        pass
    return None


def _digest(record):
    fields = {k: record.get(k) for k in (
        "title", "text", "summary", "date", "link", "source_document_url", "ticker", "source", "source_type",
        "publication_date_original", "publication_date_precision", "content_coverage", "content_truncated",
        "source_role", "event_assessment")}
    fields["date"] = _canonical_day(record.get("date"))
    if record.get("ticker") == "6672.TW":
        fields.update({key: record.get(key) for key in (
            "publisher", "publication_date_basis", "issuer_republication_date", "original_publisher_publication_date")})
    return sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _record(ticker, identity, raw, *, title, body, published, date_original, link, document_url, original_id):
    if ticker == "3023.TW" and (not isinstance(title, str) or not isinstance(body, str)):
        raise ValueError("article_content_unusable")
    title, body = clean_text(title), clean_text(body)
    if not 1 <= len(title) <= 500 or not 100 <= len(body) <= 12000:
        raise ValueError("article_content_unusable")
    record = {"ticker": ticker, "title": title, "text": body, "summary": body[:280],
              "date": published.isoformat(), "link": link, "source_document_url": document_url,
              "source": PROFILES[ticker]["short_name"] + "官網", "source_type": "first_party_issuer_news",
              "publication_date_original": {"issuer_article_date": date_original, "date": published.isoformat()},
              "publication_date_precision": "day",
              "content_coverage": "text_available", "content_truncated": False,
              "source_role": "issuer_statement", "event_assessment": "not_assessed"}
    record["issuer_news_receipt"] = {**identity, "policy": POLICY, "original_id": str(original_id),
                                     "article_response_sha256": sha256(raw).hexdigest(),
                                     "parsed_content_sha256": _digest(record)}
    return record


def verified_issuer_news(record, data, *, today=None):
    """A saved receipt admits the official alias only on its exact issuer route."""
    try:
        ticker = str(data.get("ticker") or "").upper()
        if ticker == "2206.TW":
            from .sym_issuer_news import is_marked, verified_record
            if is_marked(record):
                return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "5880.TW":
            from .tcfhc_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker in {"2201.TW", "2464.TW", "2886.TW"}:
            from .registered_issuer_articles import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "3042.TW":
            from .txc_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "2360.TW":
            from .chroma_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "2884.TW":
            from .esun_issuer_news import verified_record
            return verified_record(record, data, today=today)
        if ticker == "8150.TW":
            from .chipmos_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "2353.TW":
            from .acer_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "3443.TW":
            from .guc_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "2412.TW":
            from .cht_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "6669.TW":
            from .wiwynn_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "8069.TWO":
            from .eink_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "2379.TW":
            from .realtek_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        if ticker == "6672.TW":
            from .ventec_issuer_news import verified_record
            return verified_record(record, data, today=today or datetime.now(TAIPEI).date())
        profile = PROFILES.get(ticker)
        receipt = record.get("issuer_news_receipt")
        if not profile or not isinstance(receipt, dict):
            return None
        identity = data.get("company_identity") or {}
        if isinstance(identity, dict) and identity.get("official_name") not in (None, "", profile["short_name"]):
            return None
        if (record.get("ticker") != ticker or record.get("source_type") != "first_party_issuer_news"
                or receipt.get("policy") != POLICY or receipt.get("ticker") != ticker
                or receipt.get("legal_name") != profile["legal_name"] or receipt.get("short_name") != profile["short_name"]
                or receipt.get("english_alias") != profile["english_alias"] or receipt.get("website_host") != profile["host"]
                or receipt.get("master_source_url") != ROSTER_URL or record.get("content_truncated") is not False
                or record.get("publication_date_precision") != "day"
                or receipt.get("parsed_content_sha256") != _digest(record)
                or not all(re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(k) or ""))
                           for k in ("master_response_sha256", "article_response_sha256"))):
            return None
        observed = date.fromisoformat(receipt["master_observed_on"])
        if not 0 <= ((today or datetime.now(TAIPEI).date()) - observed).days <= 14:
            return None
        original_dates = record.get("publication_date_original")
        day = _article_date(original_dates.get("issuer_article_date") if isinstance(original_dates, dict) else None, ticker)
        if (day is None or _canonical_day(record.get("date")) != day.isoformat()
                or "published_date" in record and _canonical_day(record["published_date"]) != day.isoformat()):
            return None
        document = str(record.get("source_document_url") or "")
        url_contract(document)
        link = str(record.get("link") or "")
        if ticker == "2206.TW":
            if document != link or not re.fullmatch(r"https://www\.sanyang\.com\.tw/busnessnews-page[1-9]\d{0,7}", link):
                return None
            if receipt.get("original_id") != link.rsplit("page", 1)[1]:
                return None
        elif ticker == "1101.TW":
            from .tcc_issuer_news import ARTICLE
            if (document != link or not ARTICLE.fullmatch(link)
                    or receipt.get("original_id") != link.rsplit("/", 1)[1]
                    or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("index_response_sha256") or ""))):
                return None
        else:
            slug = document.removeprefix("https://www.sinbon.com/api/news/detail/")
            if document == slug or link != "https://www.sinbon.com/news/" + slug:
                return None
            if not re.fullmatch(r"[1-9]\d{0,8}", str(receipt.get("original_id") or "")):
                return None
        body = record.get("text")
        title = record.get("title")
        if not isinstance(body, str) or not 100 <= len(body) <= 12000 or not isinstance(title, str) or not 1 <= len(title) <= 500:
            return None
        forbidden_values = identity.get("forbidden_aliases", []) if isinstance(identity, dict) else []
        if not isinstance(forbidden_values, (list, tuple)):
            return None
        forbidden = {clean_text(value).strip().strip("*").casefold() for value in forbidden_values}
        for alias in (profile["short_name"], profile["english_alias"]):
            if alias.casefold() in forbidden:
                continue
            text = title + " " + body
            if (alias == profile["short_name"] and alias in text
                    or alias == profile["english_alias"] and re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I)):
                return alias
    except (ValueError, TypeError, KeyError, AttributeError, SourceResponseError):
        pass
    return None


def fetch_recent_issuer_news(ticker, *, now=None, http=None):
    now = now or datetime.now(TAIPEI)
    ticker = str(ticker or "").upper()
    if ticker == "5880.TW":
        from .tcfhc_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker in {"2201.TW", "2464.TW", "2886.TW"}:
        from .registered_issuer_articles import fetch_recent_news
        return fetch_recent_news(ticker, now=now, http=http)
    if ticker == "3042.TW":
        from .txc_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "2360.TW":
        from .chroma_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "2884.TW":
        from .esun_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "8150.TW":
        from .chipmos_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "2353.TW":
        from .acer_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "3443.TW":
        from .guc_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "2412.TW":
        from .cht_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "6669.TW":
        from .wiwynn_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "8069.TWO":
        from .eink_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker == "2379.TW":
        from .realtek_issuer_news import fetch_recent_news
        return fetch_recent_news(now=now, http=http)
    if ticker not in PROFILES:
        return [], {"status": "not_applicable", "http_request_sent": False, "event_kind": "local_block", "record_count": 0}
    deadline = time.monotonic() + 20
    http = http or IssuerNewsHttp(deadline)
    records, excluded = [], Counter()
    policy = PROFILES[ticker].get("policy", POLICY)
    diagnostics = {"selection_policy": policy, "coverage_status": "partial", "window_complete": False}
    try:
        identity = _identity(http.get(ROSTER_URL), ticker, now.astimezone(TAIPEI).date())
        raw = http.get(PROFILES[ticker]["index"])
        candidates = []
        if ticker == "3023.TW":
            payload = json.loads(raw)
            rows = payload.get("rows")
            if payload.get("status") != "success" or not isinstance(rows, list) or len(rows) > 1000:
                raise ValueError("news_index_invalid")
            diagnostics["raw_count"] = len(rows)
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("news_index_row_invalid")
                published = _article_date(row.get("article_date"), ticker)
                candidates.append((published, row))
        elif ticker == "1101.TW":
            from .tcc_issuer_news import parse_tcc_index
            rows = parse_tcc_index(raw)
            diagnostics["raw_count"] = len(rows)
            candidates = [(_article_date(row["date_original"], ticker), row) for row in rows]
        elif ticker == "6672.TW":
            from .ventec_issuer_news import parse_index
            rows = parse_index(raw)
            diagnostics["raw_count"] = len(rows)
            candidates = [(_article_date(row["date_original"], ticker), row) for row in rows]
        else:
            soup = BeautifulSoup(raw, "html.parser")
            anchors = soup.select("h4.blog_title a[href]")
            if not anchors or len(anchors) > 100:
                raise ValueError("news_index_invalid")
            diagnostics["raw_count"] = len(anchors)
            for anchor in anchors:
                dates = re.findall(r"\b[A-Z][a-z]{2} \d{2} 20\d{2}\b", anchor.parent.parent.get_text(" ", strip=True))
                original = dates[0] if len(dates) == 1 else None
                candidates.append((_article_date(original, ticker), {"name": clean_text(anchor), "url": anchor["href"], "date_original": original}))
        today = now.astimezone(TAIPEI).date()
        selected, seen = [], set()
        for published, row in candidates:
            if published is None:
                excluded["unknown_date"] += 1
            elif published > today:
                excluded["future"] += 1
            elif published < today - timedelta(days=30):
                excluded["historical"] += 1
            else:
                key = row.get("id") if ticker == "3023.TW" else row.get("url")
                if key in seen:
                    excluded["duplicate"] += 1
                else:
                    seen.add(key)
                    selected.append((published, row))
        for published, row in sorted(selected, key=lambda pair: pair[0], reverse=True)[:5]:
            if time.monotonic() >= deadline:
                raise SourceResponseError("timeout")
            if ticker == "3023.TW":
                slug = row.get("slug")
                document = "https://www.sinbon.com/api/news/detail/" + str(slug or "")
                url_contract(document)
                original = http.get(document)
                detail = json.loads(original)
                item = detail.get("row")
                if (detail.get("status") != "success" or not isinstance(item, dict)
                        or any(item.get(k) != row.get(k) for k in ("id", "slug", "name", "article_date", "description"))):
                    raise ValueError("article_index_detail_mismatch")
                record = _record(ticker, identity, original, title=item["name"], body=item["description"], published=published,
                                 date_original=item["article_date"], link="https://www.sinbon.com/news/" + slug,
                                 document_url=document, original_id=item["id"])
            elif ticker == "1101.TW":
                from .tcc_issuer_news import parse_tcc_article
                document = row["url"]
                url_contract(document)
                original = http.get(document)
                title, body = parse_tcc_article(original, row)
                record = _record(ticker, identity, original, title=title, body=body, published=published,
                                 date_original=row["date_original"], link=document, document_url=document,
                                 original_id=document.rsplit("/", 1)[1])
                record["issuer_news_receipt"]["index_response_sha256"] = sha256(raw).hexdigest()
            elif ticker == "6672.TW":
                from .ventec_issuer_news import parse_article, build_record
                document = row["url"]
                url_contract(document)
                original = http.get(document)
                parsed = parse_article(original, row)
                record = build_record(identity, raw, original, row, parsed, published)
            else:
                document = row["url"]
                url_contract(document)
                if not document.startswith("https://www.sanyang.com.tw/busnessnews-page"):
                    raise ValueError("article_route_mismatch")
                original = http.get(document)
                soup = BeautifulSoup(original, "html.parser")
                title, stamp, body = (soup.select(selector) for selector in (
                    "h2.page-header", "article.blog-post-details .post_header .data", "article.blog-post-details .post_content"))
                if (len(title) != 1 or len(stamp) != 1 or len(body) != 1
                        or clean_text(title[0]) != row["name"] or clean_text(stamp[0]) != row["date_original"]):
                    raise ValueError("article_index_detail_mismatch")
                record = _record(ticker, identity, original, title=title[0], body=body[0], published=published,
                                 date_original=row["date_original"], link=document, document_url=document,
                                 original_id=document.rsplit("page", 1)[1])
            if not verified_issuer_news(record, {"ticker": ticker}, today=today):
                raise ValueError("article_issuer_unverified")
            records.append(record)
        if time.monotonic() >= deadline:
            raise SourceResponseError("timeout")
        diagnostics["status"] = "success" if records else "unavailable"
    except (ValueError, TypeError, KeyError, AttributeError, SourceResponseError) as exc:
        diagnostics.update(status="degraded_enrichment" if records else "error",
                           error_kind=getattr(exc, "error_kind", "parse_error"), error_message=str(exc)[:150])
    components = getattr(http, "components", [])
    sent = getattr(http, "http_request_count", 0)
    cached = bool(components) and all(c.get("cache_hit") for c in components)
    if diagnostics.get("status") == "success" and cached and not sent:
        diagnostics["status"] = "skipped_fresh_cache"
    epochs = [c["fetched_at_epoch"] for c in components if type(c.get("fetched_at_epoch")) in (int, float)]
    diagnostics.update(http_request_sent=bool(sent), http_request_count=sent,
                       event_kind="http_request" if sent else "cache_hit" if cached else "local_block",
                       cache_hit=cached, stale=False, record_count=len(records), usable_count=len(records),
                       fetched_at_epoch=min(epochs) if epochs else None, parser_version=policy,
                       excluded_reason_counts=dict(excluded), component_receipts=components)
    return records, diagnostics
