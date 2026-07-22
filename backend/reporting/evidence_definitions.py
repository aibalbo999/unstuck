"""Static evidence-source definitions for report evidence rows."""

from __future__ import annotations


KEY_EVIDENCE_DEFINITIONS = (
    ("股價與市值", "market_data", ("current_price", "market_cap_raw", "market_cap_fmt")),
    ("年度財報", "financial_statements", ("years", "revenue_history", "net_income_history", "fcf_history")),
    ("月營收", "monthly_revenue", ("recent_monthly_revenue",)),
    ("法人籌碼", "institutional_trading", ("institutional_trading",)),
    ("同業指標", "dynamic_peer_metrics", ("dynamic_peer_metrics",)),
    ("P/E 河流圖", "pe_river_chart", ("pe_river_chart",)),
    ("近期催化劑", "recent_catalysts", ("recent_catalysts",)),
    ("全球市場脈絡", "global_market_context", ("global_market_context",)),
    ("國際新聞脈絡", "international_news_context", ("international_news_context",)),
)


__all__ = ["KEY_EVIDENCE_DEFINITIONS"]
