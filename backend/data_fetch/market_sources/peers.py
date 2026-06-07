"""Peer discovery and peer metric source helpers."""

from __future__ import annotations

import yfinance as yf

from .common import _run_named_fetches


GLOBAL_PEER_HINTS = [
    (["半導體", "Semiconductor", "晶圓", "foundry"], [("Intel", "INTC"), ("Samsung Electronics", "005930.KS"), ("UMC", "2303.TW"), ("SMIC", "0981.HK")]),
    (["記憶體", "Memory", "DRAM", "NAND"], [("Micron", "MU"), ("SK hynix", "000660.KS"), ("Samsung Electronics", "005930.KS")]),
    (["面板", "Display", "LCD", "OLED"], [("AUO", "2409.TW"), ("Innolux", "3481.TW"), ("LG Display", "LPL"), ("BOE", "000725.SZ")]),
    (["航運", "Shipping", "Marine"], [("Evergreen Marine", "2603.TW"), ("Yang Ming", "2609.TW"), ("Wan Hai", "2615.TW"), ("Maersk", "MAERSK-B.CO")]),
]


def infer_global_peer_tickers(ticker: str, company_name: str, sector: str, industry: str) -> list[tuple[str, str]]:
    signature = f"{company_name} {sector} {industry}"
    peers = []
    for keywords, candidates in GLOBAL_PEER_HINTS:
        if any(keyword.lower() in signature.lower() for keyword in keywords):
            peers.extend(candidates)
    return [(name, symbol) for name, symbol in peers if symbol.upper() != ticker.upper()][:5]


def fetch_dynamic_peer_metrics(ticker: str, company_name: str, sector: str, industry: str, identity: dict) -> list[dict]:
    peers = []
    for peer in (identity.get("same_industry_peers", []) or [])[:3]:
        stock_id = peer.get("stock_id")
        if stock_id:
            peers.append((peer.get("stock_name", stock_id), f"{stock_id}.TW"))
    peers.extend(infer_global_peer_tickers(ticker, company_name, sector, industry))

    seen = set()
    unique_peers = []
    for name, symbol in peers:
        if symbol in seen:
            continue
        seen.add(symbol)
        unique_peers.append((name, symbol))
        if len(unique_peers) >= 5:
            break

    def fetch_peer(name: str, symbol: str) -> dict:
        try:
            info = yf.Ticker(symbol).info
        except Exception:
            info = {}
        return {
            "name": name,
            "ticker": symbol,
            "source": "FinMind industry peer + yfinance metrics" if symbol.endswith(".TW") else "global peer heuristic + yfinance metrics",
            "gross_margin_pct": round(float(info.get("grossMargins")) * 100, 2) if isinstance(info.get("grossMargins"), (int, float)) else None,
            "operating_margin_pct": round(float(info.get("operatingMargins")) * 100, 2) if isinstance(info.get("operatingMargins"), (int, float)) else None,
            "profit_margin_pct": round(float(info.get("profitMargins")) * 100, 2) if isinstance(info.get("profitMargins"), (int, float)) else None,
            "pe_ttm": round(float(info.get("trailingPE")), 2) if isinstance(info.get("trailingPE"), (int, float)) else None,
            "pb": round(float(info.get("priceToBook")), 2) if isinstance(info.get("priceToBook"), (int, float)) else None,
        }

    fetches = {
        symbol: (fetch_peer, (name, symbol), None, f"{symbol} 同業指標獲取失敗")
        for name, symbol in unique_peers
    }
    results = _run_named_fetches(fetches, max_workers=5)
    return [record for record in results.values() if record]
