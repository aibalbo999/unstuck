"""Use a company's local identity instead of AND-ing bilingual display labels."""
import re


def company_news_query(data: dict, *, lookback_days: int = 30) -> str:
    ticker = str(data.get("ticker") or "").strip().upper()
    display = str(data.get("company_name") or ticker).strip()
    if not re.fullmatch(r"\d{4,6}\.(?:TW|TWO)", ticker):
        return f"{ticker} {display}".strip()
    identity = data.get("company_identity") or {}
    identity = identity if isinstance(identity, dict) else {}
    name = str(identity.get("official_name") or display.split(" / ")[0]).strip().strip("*")
    name = re.sub(r'["\r\n]+', " ", name).strip()
    if not name or name.upper() in {ticker, ticker.split(".")[0]}:
        return f'{ticker.split(".")[0]} 股票 when:{max(1, int(lookback_days))}d'
    return f'"{name}" {ticker.split(".")[0]} when:{max(1, int(lookback_days))}d'
