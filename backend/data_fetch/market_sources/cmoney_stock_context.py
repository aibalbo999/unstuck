"""Original single-stock context for the ambiguous 5314 exchange shorthand.

The source's exact stock tag is retained separately from an author's title.
This receipt is only created after the existing original-page parser succeeds.
"""
from hashlib import sha256
import json
import re

from news_record_utils import clean_text

POLICY = "cmoney-single-stock-context-v1"
BASIS = "verified_cmoney_single_stock_context"
TARGET, CODE, COMPANY = "5314.TWO", "5314", "世紀*"


def _digest(record, heading):
    from .cmoney_stock_posts import _date
    fields = {key: record.get(key) for key in (
        "title", "text", "source", "link", "source_tag", "source_tags", "source_listing",
        "evidence_kind", "response_sha256", "response_bytes", "parser_version", "sentiment_assessment",
        "issuer_evidence_basis",
    )}
    stamp = _date(record.get("date"))
    fields.update(date=stamp.isoformat() if stamp else None, original_heading=heading)
    return sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def build_stock_context(record, *, heading):
    return {"policy": POLICY, "stock_id": CODE, "company": COMPANY,
            "original_heading": heading, "article_response_sha256": record["response_sha256"],
            "parsed_content_sha256": _digest(record, heading)}


def verified_stock_context(record, data):
    from .cmoney_stock_posts import ARTICLE_URL, MAX_BYTES, PROVIDER, _date
    try:
        receipt = record.get("cmoney_stock_context")
        identity = data.get("company_identity")
        identity = {} if identity is None else identity
        if not isinstance(receipt, dict) or not isinstance(identity, dict):
            return None
        name = identity.get("official_name")
        if name is None or name == "":
            company_name = data.get("company_name")
            if not isinstance(company_name, str):
                return None
            name = company_name.split(" / ")[0].strip()
        elif not isinstance(name, str):
            return None
        stock_id = identity.get("stock_id")
        if stock_id is None or stock_id == "":
            stock_id = CODE
        elif not isinstance(stock_id, str):
            return None
        if (data.get("ticker") != TARGET or name != COMPANY
                or identity.get("ticker") not in (None, "", TARGET)
                or stock_id != CODE
                or identity.get("instrument_type") not in (None, "", "EQUITY")
                or receipt.get("policy") != POLICY or receipt.get("stock_id") != CODE
                or receipt.get("company") != COMPANY
                or record.get("issuer_evidence_basis") != BASIS
                or record.get("source") != PROVIDER
                or record.get("social_channel") not in (None, "cmoney_stock_direct")
                or record.get("source_tag") != CODE + COMPANY or record.get("source_tags") != [CODE + COMPANY]
                or record.get("evidence_kind") != "single_stock_forum_post"
                or record.get("parser_version") != "cmoney-stock-posts-v2"
                or record.get("sentiment_assessment") != "not_assessed"
                or record.get("source_listing") not in {
                    "https://forum-web.cmoney.tw/stocks/5314", "https://www.cmoney.tw/finance/5314/f00025"}
                or not ARTICLE_URL.fullmatch(str(record.get("link") or ""))
                or type(record.get("response_bytes")) is not int or not 0 < record["response_bytes"] <= MAX_BYTES
                or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("response_sha256") or ""))
                or receipt.get("article_response_sha256") != record.get("response_sha256")
                or _date(record.get("date")) is None):
            return None
        title, body, heading = record.get("title"), record.get("text"), receipt.get("original_heading")
        if (not isinstance(title, str) or not 1 <= len(title) <= 200
                or not isinstance(body, str) or not 5 <= len(body) <= 5000
                or re.search(r"https?://|www\.", body, re.I)
                or not isinstance(heading, str) or not 1 <= len(heading) <= 300 or COMPANY not in heading
                or receipt.get("parsed_content_sha256") != _digest(record, heading)):
            return None
        forbidden = identity.get("forbidden_aliases", [])
        if not isinstance(forbidden, (list, tuple)) or any(not isinstance(x, str) for x in forbidden):
            return None
        if COMPANY.strip("*").casefold() in {clean_text(x).strip().strip("*").casefold() for x in forbidden}:
            return None
        return COMPANY
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None
