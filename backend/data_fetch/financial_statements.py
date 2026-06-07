"""Financial-statement provider boundary.

The heavy yfinance/FinMind assembly still lives in the core snapshot module
for this migration step; this module centralizes the fallback provider surface
so callers no longer reach into root compatibility shims.
"""

from __future__ import annotations

from .market_sources.taiwan import fetch_finmind_financial_statement_fallback

__all__ = ["fetch_finmind_financial_statement_fallback"]
