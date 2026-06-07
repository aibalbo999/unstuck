"""Company identity and Taiwan ticker helpers."""

from __future__ import annotations

from functools import lru_cache

from .common import safe_get


TAIWAN_BROAD_INDUSTRY_CATEGORIES = {
    "上市股票",
    "上櫃股票",
    "興櫃股票",
    "電子工業",
    "金融保險業",
}

TAIWAN_IDENTITY_OVERRIDES = {
    "1623": {
        "official_name": "大東電",
        "legal_name": "大東電業廠股份有限公司",
        "forbidden_aliases": ["大亞", "大亞電線電纜", "TA YA", "Ta Ya Electric"],
    },
    "1609": {
        "official_name": "大亞",
        "legal_name": "大亞電線電纜股份有限公司",
        "forbidden_aliases": ["大東電", "大東電業", "TA TUN", "Ta Tun Electric"],
    },
    "6806": {
        "official_name": "森崴能源",
        "legal_name": "森崴能源股份有限公司",
        "aliases": ["森崴能"],
        "forbidden_aliases": [],
    },
}


def _stock_id_from_ticker(ticker: str) -> str:
    return str(ticker).replace(".TW", "").replace(".TWO", "")


def is_taiwan_ticker(ticker: str) -> bool:
    stock_id = _stock_id_from_ticker(ticker)
    return str(ticker).endswith(".TW") or str(ticker).endswith(".TWO") or (stock_id.isdigit() and len(stock_id) == 4)


@lru_cache(maxsize=1)
def load_taiwan_stock_info_records() -> list[dict]:
    if not _get_data_loader():
        return []
    try:
        df = _get_data_loader()().taiwan_stock_info()
        records = []
        for _, row in df.iterrows():
            stock_id = str(row.get("stock_id", "")).strip()
            stock_name = str(row.get("stock_name", "")).strip()
            industry_category = str(row.get("industry_category", "")).strip()
            if stock_id and stock_name:
                records.append({
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "industry_category": industry_category,
                    "type": str(row.get("type", "")).strip(),
                })
        return records
    except Exception:
        return []


def unique_nonempty(values) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value is None:
            continue
        value = str(value).strip()
        if not value or value == "N/A" or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def build_company_identity(ticker: str, info: dict, company_name: str) -> dict:
    stock_id = _stock_id_from_ticker(ticker)
    override = TAIWAN_IDENTITY_OVERRIDES.get(stock_id, {})

    official_name = override.get("official_name")
    legal_name = override.get("legal_name")
    industry_categories = []
    same_industry_peers = []

    if is_taiwan_ticker(ticker):
        records = load_taiwan_stock_info_records()
        current_rows = [r for r in records if r["stock_id"] == stock_id]
        if current_rows:
            official_name = official_name or current_rows[0]["stock_name"]
            industry_categories = unique_nonempty(r["industry_category"] for r in current_rows)
            narrow_categories = [
                cat for cat in industry_categories
                if cat and cat not in TAIWAN_BROAD_INDUSTRY_CATEGORIES
            ]
            peer_categories = narrow_categories or industry_categories[:1]
            peer_seen = set()
            for row in records:
                if row["stock_id"] == stock_id or row["industry_category"] not in peer_categories:
                    continue
                peer_key = (row["stock_id"], row["stock_name"])
                if peer_key in peer_seen:
                    continue
                same_industry_peers.append({"stock_id": row["stock_id"], "stock_name": row["stock_name"]})
                peer_seen.add(peer_key)

    english_names = unique_nonempty([
        safe_get(info, "longName", None),
        safe_get(info, "shortName", None),
        company_name,
    ])

    display_name = company_name
    if official_name:
        english_display = next((name for name in english_names if official_name not in name), "")
        display_name = f"{official_name} / {english_display}" if english_display else official_name

    allowed_aliases = unique_nonempty([
        official_name,
        legal_name,
        *override.get("aliases", []),
        display_name,
        company_name,
        ticker,
        stock_id,
        *english_names,
    ])

    return {
        "ticker": ticker,
        "stock_id": stock_id,
        "official_name": official_name,
        "legal_name": legal_name,
        "display_name": display_name,
        "english_names": english_names,
        "allowed_aliases": allowed_aliases,
        "forbidden_aliases": unique_nonempty(override.get("forbidden_aliases", [])),
        "industry_categories": industry_categories,
        "same_industry_peers": same_industry_peers,
    }


def _get_data_loader():
    from .taiwan import DataLoader

    return DataLoader
