"""Use a company's local identity instead of AND-ing bilingual display labels."""
import re
from unicodedata import normalize


# The exchange shorthand 世紀* collapses to an unrelated common noun when
# punctuation is removed. The issuer's own site identifies it as 世紀民生.
VERIFIED_SEARCH_NAMES = {"5314.TWO": "世紀民生"}


def context_bound_bank_news_aliases(data: dict) -> tuple[str, ...]:
    """Bind FEIB's published brands to the captured 2845 issuer only.

    TWSE identifies 2845 / 遠東銀 / 遠東國際商業銀行股份有限公司 /
    86517096. Its group's full company page states 遠東商銀 and 遠銀,
    stock code 2845 and links to feib.com.tw. Legacy snapshots put EQUITY
    at the root; absence in their identity is not a conflicting type.
    """
    identity = data.get("company_identity")
    if (str(data.get("ticker") or "").strip().upper() != "2845.TW"
            or not isinstance(identity, dict)
            or identity.get("ticker") != "2845.TW" or identity.get("stock_id") != "2845"
            or identity.get("official_name") != "遠東銀"
            or data.get("instrument_type") not in (None, "EQUITY")
            or identity.get("instrument_type") not in (None, "EQUITY")
            or identity.get("legal_name") not in (None, "", "遠東國際商業銀行股份有限公司")
            or identity.get("official_ubn") not in (None, "86517096")):
        return ()
    forbidden = identity.get("forbidden_aliases")
    if forbidden is None:
        forbidden = []
    if (not isinstance(forbidden, (list, tuple))
            or any(not isinstance(name, str) for name in forbidden)):
        return ()
    from news_record_utils import clean_text
    if any(clean_text(normalize("NFKC", name)).strip().strip("*").strip() in {"遠東商銀", "遠銀"}
           for name in forbidden):
        return ()
    return ("遠東商銀", "遠銀")


def context_bound_search_alias(data: dict) -> str:
    """Keep captured issuer-label mappings local to news queries/selection.

    TWSE's current 6902 row is GOGOLOOK / 走著瞧股份有限公司 / 53755364.
    Older snapshots use GOGOLOOK-創. The unique English brand is suitable for
    searching; the everyday Chinese phrase 走著瞧 is not a generic news alias.
    TWSE's captured 2254 row is 巨鎧精密-創 / 巨鎧精密工業股份有限公司 /
    54297090. Its native RSS uses 巨鎧精密 for the same issuer. Neither mapping
    rewrites saved identities or strips other issuers' suffixes.
    """
    bank_aliases = context_bound_bank_news_aliases(data)
    if bank_aliases:
        return bank_aliases[0]
    ticker = str(data.get("ticker") or "").strip().upper()
    identity = data.get("company_identity")
    bindings = {
        "6902.TW": (("GOGOLOOK-創", "GOGOLOOK"), "走著瞧股份有限公司", "53755364", "Gogolook"),
        "2254.TW": (("巨鎧精密-創",), "巨鎧精密工業股份有限公司", "54297090", "巨鎧精密"),
    }
    binding = bindings.get(ticker)
    if binding is None or not isinstance(identity, dict):
        return ""
    names, legal_name, ubn, alias = binding
    if (identity.get("ticker") != ticker or identity.get("stock_id") != ticker.split(".")[0]
            or identity.get("instrument_type") != "EQUITY"
            or identity.get("official_name") not in names
            or identity.get("legal_name") not in (None, "", legal_name)
            or identity.get("official_ubn") not in (None, ubn)):
        return ""
    forbidden = identity.get("forbidden_aliases")
    if forbidden is None:
        forbidden = []
    if (not isinstance(forbidden, (list, tuple))
            or any(not isinstance(name, str) for name in forbidden)):
        return ""
    from news_record_utils import clean_text
    if any(clean_text(normalize("NFKC", name)).strip().strip("*").strip().casefold() == alias.casefold()
           for name in forbidden):
        return ""
    return alias


def company_search_name(data: dict) -> str:
    ticker = str(data.get("ticker") or "").strip().upper()
    if ticker in VERIFIED_SEARCH_NAMES:
        return VERIFIED_SEARCH_NAMES[ticker]
    alias = context_bound_search_alias(data)
    if alias:
        return alias
    display = str(data.get("company_name") or ticker).strip()
    identity = data.get("company_identity") or {}
    identity = identity if isinstance(identity, dict) else {}
    name = str(identity.get("official_name") or display.split(" / ")[0]).strip().strip("*")
    return re.sub(r'["\r\n]+', " ", name).strip()


def company_news_query(data: dict, *, lookback_days: int = 30) -> str:
    ticker = str(data.get("ticker") or "").strip().upper()
    display = str(data.get("company_name") or ticker).strip()
    if not re.fullmatch(r"\d{4,6}\.(?:TW|TWO)", ticker):
        return f"{ticker} {display}".strip()
    bank_aliases = context_bound_bank_news_aliases(data)
    if bank_aliases:
        # Public issuer articles use the brand without the security code.
        # Only this verified company uses the name-only query; selection
        # still binds every returned record to the original issuer/time.
        return f'"{bank_aliases[1]}" when:{max(1, int(lookback_days))}d'
    name = company_search_name(data)
    if not name or name.upper() in {ticker, ticker.split(".")[0]}:
        return f'{ticker.split(".")[0]} 股票 when:{max(1, int(lookback_days))}d'
    return f'"{name}" {ticker.split(".")[0]} when:{max(1, int(lookback_days))}d'


def company_news_brand_fallback_query(data: dict, *, lookback_days: int = 30) -> str:
    """An existing bound brand can retrieve articles omitting the stock code."""
    if data.get("instrument_type") not in (None, "EQUITY"):
        return ""
    alias = context_bound_search_alias(data)
    if not alias or context_bound_bank_news_aliases(data):
        return ""
    return f'"{alias}" when:{max(1, int(lookback_days))}d'
