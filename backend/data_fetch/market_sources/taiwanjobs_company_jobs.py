"""Bounded, exact-issuer open-job sample from TaiwanJobs' public company search."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import csv
import io
import os
import re
import time
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import httpx

from external_http_client import proxy_url_for_provider


PROVIDER = "TaiwanJobs public company search"
REGIONAL_PROVIDER = "TaiwanJobs public regional open data"
SEARCH_URL = "https://job.taiwanjobs.gov.tw/internet/index/job_search_list.aspx"
REGIONAL_URL = "https://free.taiwanjobs.gov.tw/WebService_Taipei/Webservice.ashx"
RESULT_PATH = "/internet/index/jobquery_result_comp2.aspx"
COMPANY_PATH = "/internet/jobwanted/company_desc2.aspx"
DETAIL_PATH = "/internet/index/jobdetail.aspx"
MAX_BYTES = 500_000
REGIONAL_COMPANY_MAX_BYTES = 600_000
MAX_SAMPLE = 5
MAX_SECONDS = 22
REGIONAL_SECONDS = 12
REGIONAL_MAX_BYTES = 3_500_000
REGIONAL_CITIES = ("31", "15", "13", "02", "01", "33", "37", "40", "11", "12", "34",
                   "35", "38", "39", "14", "43", "32", "45", "46", "44", "23", "24")
_TICKER = re.compile(r"\d{4,6}\.(?:TW|TWO)")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[1-9]\d{0,11}")
_TZ = ZoneInfo("Asia/Taipei")


def _fcfc_employer_reconciliation(ticker: str, company: str, ubn: str) -> dict | None:
    # TWSE spells this issuer 台灣; the government employer page uses 臺灣.
    # Never extend this to a general spelling substitution or group alias.
    if (ticker, company, ubn) != ("1326.TW", "台灣化學纖維股份有限公司", "58650902"):
        return None
    return {"policy": "fcfc-taiwanjobs-legal-name-v1", "requested_legal_name": company,
            "source_legal_name": "臺灣化學纖維股份有限公司", "official_ubn": ubn}


def _unavailable(ticker: str, legal_name: str, reason: str) -> dict:
    return {"status": "unavailable", "ticker": ticker, "company_name": legal_name,
            "source": PROVIDER, "source_url": SEARCH_URL, "job_count": None,
            "current_open_job_count": None, "job_postings": [], "reason_code": reason}


def _verified_url(url: str, path: str) -> bool:
    parsed = urlsplit(str(url))
    return (parsed.scheme == "https" and parsed.netloc.lower() == "job.taiwanjobs.gov.tw"
            and parsed.path.lower() == path)


def _read(client, method: str, url: str, *, data: dict | None, deadline: float, path: str,
          max_bytes: int = MAX_BYTES):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("TaiwanJobs acquisition deadline exhausted")
    response = (client.get(url, timeout=min(remaining, 8)) if method == "GET" else
                client.post(url, data=data, timeout=min(remaining, 8)))
    response.raise_for_status()
    if not _verified_url(str(response.url), path) or not 0 < len(response.content) <= max_bytes:
        raise ValueError("TaiwanJobs response origin, path or size invalid")
    return response, BeautifulSoup(response.text, "html.parser")


def _term(soup, label: str) -> str:
    for item in soup.select("dl"):
        dt, dd = item.find("dt"), item.find("dd")
        if dt and dd and dt.get_text(" ", strip=True) == label:
            return dd.get_text(" ", strip=True)
    return ""


def _ids(url: str, *, path: str, employer_id: str | None = None) -> tuple[str, str] | None:
    if not _verified_url(url, path):
        return None
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    if any(len(values) != 1 for values in query.values()):
        return None
    if path == COMPANY_PATH:
        if set(query) != {"EMPLOYER_ID", "BRANCH_ID"} or query.get("BRANCH_ID") != [""]:
            return None
    elif set(query) != {"R2", "EMPLOYER_ID", "HIRE_ID"} or query.get("R2") != ["11"]:
        return None
    eid = (query.get("EMPLOYER_ID") or [""])[0]
    jid = (query.get("HIRE_ID") or [""])[0] if path == DETAIL_PATH else ""
    if not _ID.fullmatch(eid) or (employer_id and eid != employer_id) or (path == DETAIL_PATH and not _ID.fullmatch(jid)):
        return None
    return eid, jid


def fetch_taiwanjobs_company_jobs(
    ticker: str, legal_name: str, official_ubn: str, *, client=None,
    today: date | None = None, now: float | None = None,
) -> dict:
    """Count at most five individually confirmed open jobs; never a search total."""
    ticker, company, ubn = str(ticker or ""), str(legal_name or "").strip(), str(official_ubn or "")
    if (not _TICKER.fullmatch(ticker) or not company.endswith("股份有限公司")
            or not re.fullmatch(r"\d{8}", ubn) or int(ubn) <= 0):
        return _unavailable(ticker, company, "issuer_unknown")
    if client is None and os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        return _unavailable(ticker, company, "network_disabled")
    observed = time.time() if now is None else now
    current = today or datetime.fromtimestamp(observed, _TZ).date()
    reconciliation = _fcfc_employer_reconciliation(ticker, company, ubn)
    source_company = reconciliation["source_legal_name"] if reconciliation else company
    own_client = client is None
    if own_client:
        kwargs = {"timeout": 8, "follow_redirects": True,
                  "headers": {"User-Agent": "Mozilla/5.0 stock-agent/1.0", "Accept-Language": "zh-TW"}}
        proxy = proxy_url_for_provider(PROVIDER)
        if proxy:
            kwargs["proxy"] = proxy
        client = httpx.Client(**kwargs)
    deadline = time.monotonic() + MAX_SECONDS
    digests: list[str] = []
    try:
        start, soup = _read(client, "GET", SEARCH_URL, data=None, deadline=deadline,
                            path=urlsplit(SEARCH_URL).path.lower())
        form = soup.find("form", id="form1")
        if form is None:
            raise ValueError("TaiwanJobs search form missing")
        fields = {e.get("name"): e.get("value", "") for e in form.find_all("input")
                  if e.get("name") and (e.get("type") or "").lower() in ("hidden", "text")}
        if "__VIEWSTATE" not in fields or "ctl00$CPH1$SearchBar$txtKeywordComp" not in fields:
            raise ValueError("TaiwanJobs search form changed")
        fields.update({"ctl00$CPH1$SearchBar$rblqryType1": "comp",
                       "ctl00$CPH1$SearchBar$txtKeywordComp": source_company.removesuffix("股份有限公司"),
                       "ctl00$CPH1$SearchBar$btnQuery": "查詢"})
        result, soup = _read(client, "POST", str(start.url), data=fields, deadline=deadline,
                             path=RESULT_PATH)
        digests += [sha256(start.content).hexdigest(), sha256(result.content).hexdigest()]
        matches = []
        for anchor in soup.find_all("a", href=True):
            if anchor.get_text(" ", strip=True) != source_company:
                continue
            url = urljoin(str(result.url), anchor["href"])
            ids = _ids(url, path=COMPANY_PATH)
            if ids:
                matches.append(ids[0])
        if len(set(matches)) != 1:
            raise ValueError("TaiwanJobs exact employer absent or ambiguous")
        employer_id = matches[0]
        company_url = f"https://job.taiwanjobs.gov.tw/internet/jobwanted/company_desc2.aspx?EMPLOYER_ID={employer_id}&BRANCH_ID="
        listing, soup = _read(client, "GET", company_url, data=None, deadline=deadline,
                              path=COMPANY_PATH)
        heading = soup.select_one("#CPH1_h1_COMPNAME")
        if (heading is None or heading.get_text(" ", strip=True) != source_company
                or _term(soup, "統一編號") != ubn):
            raise ValueError("TaiwanJobs company identity mismatch")
        digests.append(sha256(listing.content).hexdigest())
        rows, seen, rejected = [], set(), 0
        anchors = soup.select('a[id^="CPH1_lv_company_job_lnk_jobDetail_"]')
        for anchor in anchors[:MAX_SAMPLE]:
            link = urljoin(str(listing.url), anchor.get("href") or "")
            ids = _ids(link, path=DETAIL_PATH, employer_id=employer_id)
            if not ids or ids[1] in seen:
                rejected += 1
                continue
            seen.add(ids[1])
            detail, page = _read(client, "GET", link, data=None, deadline=deadline,
                                 path=DETAIL_PATH)
            digests.append(sha256(detail.content).hexdigest())
            title = page.select_one("h2")
            title = title.get_text(" ", strip=True) if title else ""
            linked = anchor.get_text(" ", strip=True)
            matches_company = any(a.get_text(" ", strip=True) == source_company and
                                  _ids(urljoin(str(detail.url), a.get("href") or ""), path=COMPANY_PATH,
                                       employer_id=employer_id)
                                  for a in page.find_all("a", href=True))
            try:
                expires = datetime.strptime(_term(page, "應徵截止日期"), "%Y/%m/%d").date()
            except ValueError:
                expires = None
            if (not 1 <= len(title) <= 200 or not linked.startswith(title)
                    or _term(page, "工作代碼") != ids[1] or not matches_company
                    or expires is None or expires < current):
                rejected += 1
                continue
            canonical = f"https://job.taiwanjobs.gov.tw/internet/index/JobDetail.aspx?R2=11&EMPLOYER_ID={employer_id}&HIRE_ID={ids[1]}"
            rows.append({"title": title, "url": canonical, "job_no": ids[1],
                         "employer": company, "employer_id": employer_id,
                         "expires_on": expires.isoformat(), "is_open": True,
                         **({"source_employer": source_company} if reconciliation else {})})
        if not rows:
            raise ValueError("TaiwanJobs no verified open issuer postings")
        return {"status": "success", "ticker": ticker, "company_name": company,
                "official_ubn": ubn, "employer_id": employer_id, "source": PROVIDER,
                "source_url": company_url, "job_count": None,
                "current_open_job_count": len(rows), "job_postings": rows,
                "evidence_kind": "government_company_job_postings",
                "query_scope": "exact_issuer_current_open_postings",
                "response_sha256": sha256("|".join(digests).encode()).hexdigest(),
                "fetched_at_epoch": observed, "sample_limit": MAX_SAMPLE,
                "listing_truncated": len(anchors) > MAX_SAMPLE, "rejected_count": rejected,
                "coverage_status": "current_open_posting_sample",
                **({"source_company_name": source_company,
                    "employer_name_reconciliation": reconciliation} if reconciliation else {}),
                "message": "按官方公司全名與統編核對台灣就業通公司頁，逐筆核對開放中職缺與截止日；僅為樣本，不推定全站職缺數或刊登日。"}
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, AttributeError, KeyError):
        return _unavailable(ticker, company, "company_or_open_job_unverified")
    finally:
        if own_client:
            client.close()


def _regional_url(city: str) -> str:
    if city not in REGIONAL_CITIES:
        raise ValueError("Unknown TaiwanJobs city")
    return f"{REGIONAL_URL}?CITY={city}&COUNT=1000&T=CSV"


def _parse_regional_csv(body: bytes) -> list[dict]:
    if not isinstance(body, bytes) or not 0 < len(body) <= REGIONAL_MAX_BYTES:
        raise ValueError("TaiwanJobs regional response size invalid")
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"), newline="")))
    if not 1 <= len(rows) <= 1001 or len(rows[0]) != 19:
        raise ValueError("TaiwanJobs regional CSV shape invalid")
    header = rows[0]
    expected = {0: "OCCU_DESC", 7: "STOP_DATE", 16: "URL_QUERY", 17: "COMPNAME", 18: "TRANDATE"}
    if any(not header[index].startswith(name) for index, name in expected.items()):
        raise ValueError("TaiwanJobs regional CSV columns changed")
    result = []
    for row in rows[1:]:
        if len(row) != 19:
            raise ValueError("TaiwanJobs regional CSV row malformed")
        result.append({"title": row[0].strip(), "expires_raw": row[7].strip(),
                       "url": row[16].strip(), "employer": row[17].strip(),
                       "updated_raw": row[18].strip()})
    return result


def _regional_ids(url: str) -> tuple[str, str] | None:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc.lower() != "job.taiwanjobs.gov.tw"
            or parsed.path.lower() != "/internet/jobwanted/jobdetail.aspx"):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (set(query) != {"EMPLOYER_ID", "HIRE_ID"}
            or len(query["EMPLOYER_ID"]) != 1 or len(query["HIRE_ID"]) != 1):
        return None
    employer_id, hire_id = query["EMPLOYER_ID"][0], query["HIRE_ID"][0]
    return (employer_id, hire_id) if _ID.fullmatch(employer_id) and _ID.fullmatch(hire_id) else None


def _regional_rows(client, city: str, deadline: float) -> tuple[list[dict], str]:
    url = _regional_url(city)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("TaiwanJobs regional deadline exhausted")
    response = client.get(url, timeout=min(remaining, 8))
    response.raise_for_status()
    if (str(response.url) != url or not 0 < len(response.content) <= REGIONAL_MAX_BYTES):
        raise ValueError("TaiwanJobs regional response origin or size invalid")
    return _parse_regional_csv(response.content), sha256(response.content).hexdigest()


def fetch_taiwanjobs_regional_jobs(
    ticker: str, legal_name: str, official_ubn: str, *, client=None,
    cities: tuple[str, ...] = REGIONAL_CITIES, today: date | None = None,
    now: float | None = None,
) -> dict:
    """Bounded CSV discovery followed by exact issuer and original job verification."""
    ticker, company, ubn = str(ticker or ""), str(legal_name or "").strip(), str(official_ubn or "")
    if (not _TICKER.fullmatch(ticker) or not company.endswith("股份有限公司")
            or not re.fullmatch(r"\d{8}", ubn) or int(ubn) <= 0):
        return _unavailable(ticker, company, "issuer_unknown")
    if client is None and os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        return _unavailable(ticker, company, "network_disabled")
    if not cities or len(cities) > len(REGIONAL_CITIES) or any(city not in REGIONAL_CITIES for city in cities):
        return _unavailable(ticker, company, "city_scope_invalid")
    observed = time.time() if now is None else now
    current = today or datetime.fromtimestamp(observed, _TZ).date()
    own_client = client is None
    if own_client:
        kwargs = {"timeout": 8, "follow_redirects": False,
                  "headers": {"User-Agent": "Mozilla/5.0 stock-agent/1.0", "Accept-Language": "zh-TW"}}
        proxy = proxy_url_for_provider(REGIONAL_PROVIDER)
        if proxy:
            kwargs["proxy"] = proxy
        client = httpx.Client(**kwargs)
    deadline = time.monotonic() + REGIONAL_SECONDS
    source_urls: list[str] = []
    digests: list[str] = []
    candidates: list[tuple[str, str, str, str, date, date]] = []
    seen: set[tuple[str, str]] = set()
    rejected = 0
    try:
        for city in cities:
            if time.monotonic() >= deadline or len(candidates) >= MAX_SAMPLE:
                break
            if own_client:
                from shared_provider_cache import shared_fetch
                payload, meta = shared_fetch(
                    f"taiwanjobs-regional-csv:v1:{city}",
                    lambda c=city: _regional_rows(client, c, deadline),
                    freshness_seconds=1800, retention_seconds=1800,
                    lock_wait_seconds=min(1, max(0, deadline - time.monotonic())),
                )
                if meta.get("stale") or not isinstance(payload, (list, tuple)) or len(payload) != 2:
                    continue
                rows, digest = payload
            else:
                rows, digest = _regional_rows(client, city, deadline)
            source_urls.append(_regional_url(city))
            digests.append(digest)
            for row in rows:
                if row["employer"] != company:
                    continue
                ids = _regional_ids(row["url"])
                try:
                    updated = datetime.strptime(row["updated_raw"], "%Y%m%d").date()
                    expires = datetime.strptime(row["expires_raw"], "%Y%m%d").date()
                except ValueError:
                    updated = expires = None
                if (not ids or not 1 <= len(row["title"]) <= 200 or updated is None or expires is None
                        or not 0 <= (current - updated).days <= 30 or expires < current):
                    rejected += 1
                    continue
                if ids in seen:
                    continue
                seen.add(ids)
                candidates.append((ids[0], ids[1], row["title"], row["url"], updated, expires))
                if len(candidates) >= MAX_SAMPLE:
                    break
            if candidates:
                # This is a verified sample, not a claim about all 22 city feeds.
                break
        if not candidates:
            return _unavailable(ticker, company, "no_verified_regional_candidates")
        employer_ids = {row[0] for row in candidates}
        if len(employer_ids) != 1:
            raise ValueError("TaiwanJobs exact employer ambiguous")
        employer_id = next(iter(employer_ids))
        company_url = f"https://job.taiwanjobs.gov.tw/internet/jobwanted/company_desc2.aspx?EMPLOYER_ID={employer_id}&BRANCH_ID="
        listing, soup = _read(client, "GET", company_url, data=None, deadline=deadline, path=COMPANY_PATH,
                              max_bytes=REGIONAL_COMPANY_MAX_BYTES)
        heading = soup.select_one("#CPH1_h1_COMPNAME")
        if (heading is None or heading.get_text(" ", strip=True) != company
                or _term(soup, "統一編號") != ubn):
            raise ValueError("TaiwanJobs regional employer identity mismatch")
        digests.append(sha256(listing.content).hexdigest())
        verified = []
        for eid, jid, linked_title, _link, updated, expires in candidates:
            canonical = f"https://job.taiwanjobs.gov.tw/internet/index/JobDetail.aspx?R2=11&EMPLOYER_ID={eid}&HIRE_ID={jid}"
            detail, page = _read(client, "GET", canonical, data=None, deadline=deadline, path=DETAIL_PATH)
            digests.append(sha256(detail.content).hexdigest())
            title_tag = page.select_one("h2")
            title = title_tag.get_text(" ", strip=True) if title_tag else ""
            matches_company = any(a.get_text(" ", strip=True) == company and
                                  _ids(urljoin(str(detail.url), a.get("href") or ""), path=COMPANY_PATH,
                                       employer_id=eid)
                                  for a in page.find_all("a", href=True))
            try:
                detail_expires = datetime.strptime(_term(page, "應徵截止日期"), "%Y/%m/%d").date()
            except ValueError:
                detail_expires = None
            if (not title.startswith(linked_title) or _term(page, "工作代碼") != jid
                    or not matches_company or detail_expires != expires or detail_expires < current):
                rejected += 1
                continue
            verified.append({"title": title, "url": canonical, "job_no": jid,
                             "employer": company, "employer_id": eid,
                             "expires_on": expires.isoformat(), "updated_on": updated.isoformat(),
                             "is_open": True})
        if not verified:
            raise ValueError("TaiwanJobs regional jobs not verified")
        return {"status": "success", "ticker": ticker, "company_name": company,
                "official_ubn": ubn, "employer_id": employer_id,
                "source": REGIONAL_PROVIDER, "source_url": company_url,
                "regional_feed_urls": source_urls, "job_count": None,
                "current_open_job_count": len(verified), "job_postings": verified,
                "evidence_kind": "government_company_job_postings",
                "query_scope": "exact_issuer_current_open_postings_from_regional_csv",
                "response_sha256": sha256("|".join(digests).encode()).hexdigest(),
                "fetched_at_epoch": observed, "sample_limit": MAX_SAMPLE,
                "listing_truncated": len(candidates) >= MAX_SAMPLE,
                "rejected_count": rejected,
                "coverage_status": "current_open_posting_sample",
                "message": "分區開放資料只作職缺候選；已核對官方公司全名、統編及逐筆原頁，未推定全站總數。"}
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, AttributeError, KeyError):
        return _unavailable(ticker, company, "regional_company_or_open_job_unverified")
    finally:
        if own_client:
            client.close()


def verified_taiwanjobs_job_count(value: dict, ticker: str, legal_name: str, official_ubn: str,
                                   *, now: float | None = None) -> int:
    """Recheck the saved shape against an independently verified issuer UBN."""
    current = time.time() if now is None else now
    if not isinstance(value, dict) or value.get("status") != "success":
        return 0
    fetched, rows = value.get("fetched_at_epoch"), value.get("job_postings")
    employer_id = str(value.get("employer_id") or "")
    source = value.get("source")
    regional = source == REGIONAL_PROVIDER
    if (not _TICKER.fullmatch(str(ticker)) or value.get("ticker") != ticker
            or value.get("company_name") != legal_name or value.get("official_ubn") != official_ubn
            or not re.fullmatch(r"\d{8}", str(official_ubn)) or int(official_ubn) <= 0
            or source not in {PROVIDER, REGIONAL_PROVIDER} or value.get("job_count") is not None
            or value.get("evidence_kind") != "government_company_job_postings"
            or value.get("query_scope") != ("exact_issuer_current_open_postings_from_regional_csv" if regional else "exact_issuer_current_open_postings")
            or not _DIGEST.fullmatch(str(value.get("response_sha256") or ""))
            or not _ID.fullmatch(employer_id)
            or value.get("source_url") != f"https://job.taiwanjobs.gov.tw/internet/jobwanted/company_desc2.aspx?EMPLOYER_ID={employer_id}&BRANCH_ID="
            or type(fetched) not in (int, float) or not 0 <= current - fetched <= 86400
            or not isinstance(rows, list) or not 0 < len(rows) <= MAX_SAMPLE
            or value.get("current_open_job_count") != len(rows)):
        return 0
    if regional:
        feed_urls = value.get("regional_feed_urls")
        if (not isinstance(feed_urls, list) or not feed_urls or len(feed_urls) > len(REGIONAL_CITIES)
                or len(set(feed_urls)) != len(feed_urls)
                or any(url not in {_regional_url(city) for city in REGIONAL_CITIES} for url in feed_urls)):
            return 0
    reconciliation = None if regional else _fcfc_employer_reconciliation(ticker, legal_name, official_ubn)
    if reconciliation:
        if (value.get("employer_name_reconciliation") != reconciliation
                or value.get("source_company_name") != reconciliation["source_legal_name"]):
            return 0
    elif ("employer_name_reconciliation" in value
          or value.get("source_company_name", legal_name) != legal_name):
        return 0
    seen = set()
    today = datetime.fromtimestamp(current, _TZ).date()
    for row in rows:
        if not isinstance(row, dict):
            return 0
        job_no = str(row.get("job_no") or "")
        try:
            expires = date.fromisoformat(str(row.get("expires_on") or ""))
        except ValueError:
            return 0
        if (not _ID.fullmatch(job_no) or job_no in seen or expires < today
                or not isinstance(row.get("title"), str) or not row["title"].strip()
                or row.get("employer") != legal_name or row.get("employer_id") != employer_id
                or (reconciliation and row.get("source_employer") != reconciliation["source_legal_name"])
                or row.get("is_open") is not True
                or row.get("url") != f"https://job.taiwanjobs.gov.tw/internet/index/JobDetail.aspx?R2=11&EMPLOYER_ID={employer_id}&HIRE_ID={job_no}"):
            return 0
        seen.add(job_no)
    return len(seen)
