"""Qualify a complete, nonempty MOPS index with fewer than five annual filings.

This proves what the original index listed, not financial values or absence of
filings elsewhere. It never qualifies an empty response or a security page.
"""
from datetime import date, datetime
from hashlib import sha256
import re
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

SCHEMA = "mops-short-annual-index.v1"
MESSAGE = "fewer than five consolidated annual filings"
INDEX_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t203sb01"
BASE = "https://mopsov.twse.com.tw"
MAX_PROOF_BYTES = 200_000
WINDOW_OPEN = re.compile(r"window\.open\('([^'\r\n]+)','[^'\r\n]*'\);")
DOWNLOAD = re.compile(r"/server-java/FileDownLoad\?[^'\"<>\s]+")


def _window_url(cell, label):
    inputs = cell.find_all("input")
    if len(inputs) != 1 or inputs[0].get("type") != "button" or inputs[0].get("value") != label:
        return None
    match = WINDOW_OPEN.fullmatch(str(inputs[0].get("onclick") or "").strip())
    return match[1] if match else None


def confirmed_short_annual_index(raw, issuer, message=MESSAGE):
    if (message != MESSAGE or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PROOF_BYTES
            or not isinstance(issuer, str) or not re.fullmatch(r"[1-9]\d{3}", issuer)):
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return None
    # A truncated response can still produce a BeautifulSoup tree.
    if not re.search(r"</html>\s*$", text, re.I) or re.search(r"captcha|security check|access denied", text, re.I):
        return None
    soup = BeautifulSoup(text, "html.parser")
    if (len(soup.find_all("html")) != 1 or len(soup.find_all("body")) != 1
            or not soup.title or soup.title.get_text(strip=True) != "公開資訊觀測站"):
        return None
    containers = soup.select("div#div01")
    if len(containers) != 1:
        return None
    container = containers[0]
    forms = container.find_all("form")
    if (len(forms) != 1 or forms[0].get("action") != "/mops/web/ajax_t203sb01"
            or forms[0].get("method") != "post"):
        return None
    markets = container.find_all("input", attrs={"name": "TYPEK"})
    if len(markets) != 1 or markets[0].get("value") not in {"sii", "otc"}:
        return None
    tables = container.find_all("table")
    if len(tables) != 1 or "hasBorder" not in tables[0].get("class", []):
        return None
    regions, headers, downloads, annual, seen = [], 0, [], {}, set()
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    for row in tables[0].find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        labels = [cell.get_text("", strip=True) for cell in cells]
        if len(cells) == 1 and cells[0].get("colspan") == "4" and labels[0] in {"IFRSs後", "IFRSs前"}:
            regions.append(labels[0])
            continue
        if labels == ["年度季別", "財報類別", "查詢", "下載"] and all(cell.name == "th" for cell in cells):
            headers += 1
            continue
        if len(cells) != 4 or not regions or regions[-1] != "IFRSs後" or not all(cell.name == "td" for cell in cells):
            return None
        period = re.fullmatch(r"(1\d{2})Q([1-4])", labels[0])
        if not period or labels[1] != "合併":
            return None
        year, quarter = int(period[1]) + 1911, int(period[2])
        month = quarter * 3
        end = date(year, month, 31 if quarter in {1, 4} else 30)
        if year < 2013 or end > today or (year, quarter) in seen or len(seen) >= 64:
            return None
        seen.add((year, quarter))
        relative = _window_url(cells[3], "下載")
        preview = _window_url(cells[2], "查詢")
        if not relative or not preview:
            return None
        parsed, display = urlsplit(relative), urlsplit(preview)
        wanted = {"functionName": ["t164sb01"], "step": ["9"], "co_id": [issuer],
                  "year": [str(year)], "season": [str(quarter)], "report_id": ["C"]}
        query = parse_qs(display.query, keep_blank_values=True)
        if (parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != "/server-java/FileDownLoad"
                or parse_qs(parsed.query, keep_blank_values=True) != wanted or display.scheme or display.netloc or display.fragment
                or display.path != "/server-java/t164sb01" or set(query) != {"step", "SYEAR", "file_name"}
                or query.get("step") != ["3"] or query.get("SYEAR") != [str(year)]
                or len(query.get("file_name", [])) != 1
                or not re.fullmatch(rf"tifrs-fr[12]-m[12]-ci-cr-{issuer}-{year}Q{quarter}\.html", query["file_name"][0])):
            return None
        downloads.append(relative)
        if quarter == 4:
            annual[year] = BASE + relative
    years = sorted(annual)
    if (regions != ["IFRSs後", "IFRSs前"] or headers != 2 or not 0 < len(years) < 5
            or years != list(range(years[0], years[-1] + 1))
            or sorted(DOWNLOAD.findall(text.replace("&amp;", "&"))) != sorted(downloads)):
        return None
    return {"schema": SCHEMA, "issuer": issuer, "message": message, "index_url": INDEX_URL,
            "index_utf8": text, "index_sha256": sha256(raw).hexdigest(), "index_bytes": len(raw),
            "available_consolidated_annual_years": years,
            "filing_urls_by_year": {str(year): annual[year] for year in years}}


def validate_short_annual_index_proof(proof, issuer, message):
    if (not isinstance(proof, dict) or proof.get("schema") != SCHEMA
            or not isinstance(proof.get("index_utf8"), str) or len(proof["index_utf8"]) > MAX_PROOF_BYTES):
        return False
    try:
        expected = confirmed_short_annual_index(proof["index_utf8"].encode("utf-8"), issuer, message)
    except (ValueError, UnicodeError):
        return False
    return expected is not None and expected == proof
