"""A bounded Taiwan peer fetch should reach plausible current-master candidates."""


def test_legacy_peer_attempt_order_reaches_nearby_codes_without_changing_eligibility(monkeypatch):
    from data_fetch.market_sources import peers

    candidates = [
        {"name": f"銀行 {code}", "ticker": f"{code}.TW", "comparison_status": "industry_candidate_only"}
        for code in range(2801, 2811)
    ] + [
        {"name": "同業甲", "ticker": "2881.TW", "comparison_status": "industry_candidate_only"},
        {"name": "同業乙", "ticker": "2883.TW", "comparison_status": "industry_candidate_only"},
    ]
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [])
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_args, **_kwargs: (
        candidates, {"selection_status": "selected", "selection_basis": "current_master_industry"},
    ))

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {
                "symbol": self.symbol, "quoteType": "EQUITY",
                "industry": "Insurance - Life" if self.symbol in {"2881.TW", "2883.TW"} else "Banks - Regional",
                "trailingPE": 12.0, "priceToBook": 1.5,
            }

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "2882.TW", "目標金控", "Financial Services", "Insurance - Life", {},
    )

    assert {row["ticker"] for row in result["peers"]} == {"2881.TW", "2883.TW"}
    assert result["audit"]["candidate_attempt_count"] <= 10
    assert result["audit"]["business_industry_rejected_count"] == 8


def test_reinsurer_reaches_documented_global_business_peers_before_broad_financials(monkeypatch):
    from data_fetch.market_sources import peers

    broad = [
        {"name": f"銀行 {code}", "ticker": f"{code}.TW", "comparison_status": "industry_candidate_only"}
        for code in range(2801, 2831)
    ]
    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [])
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_args, **_kwargs: (
        broad, {"selection_status": "selected", "selection_basis": "current_master_industry"},
    ))
    monkeypatch.setattr(peers, "documented_peer_candidates", lambda *_args, **_kwargs: [])

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {
                "symbol": self.symbol, "quoteType": "EQUITY",
                "industry": "Banks - Regional" if self.symbol.endswith(".TW") else "Insurance - Reinsurance",
                "trailingPE": 11.0, "priceToBook": 1.4, "returnOnEquity": 0.2,
            }

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "2851.TW", "中再保", "Financial Services", "Insurance - Reinsurance", {},
    )

    assert {row["ticker"] for row in result["peers"]} == {"RNR", "HNR1.DE", "MUV2.DE", "SREN.SW"}
    assert result["audit"]["candidate_attempt_count"] <= 10
    assert all(row["comparison_status"] == "business_industry_matched" for row in result["peers"])
    assert all(row["comparison_scope"] == "cross_market_reinsurance" for row in result["peers"])
    assert all(row["identity_source_url"].startswith("https://") for row in result["peers"])
    assert all("financial_period_unverified" in row["comparison_limitations"] for row in result["peers"])


def test_global_reinsurer_without_live_symbol_receipt_is_not_admitted(monkeypatch):
    from data_fetch.market_sources import peers

    monkeypatch.setattr(peers, "load_peer_stock_master", lambda: [])
    monkeypatch.setattr(peers, "resolve_legacy_peer_candidates", lambda *_args, **_kwargs: (
        [], {"selection_status": "no_eligible_current_peers", "selection_basis": "current_master_industry"},
    ))
    monkeypatch.setattr(peers, "documented_peer_candidates", lambda *_args, **_kwargs: [])

    class Stock:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            return {"symbol": None if self.symbol == "RNR" else self.symbol,
                    "quoteType": "EQUITY", "industry": "Insurance - Reinsurance",
                    "trailingPE": 11.0, "priceToBook": 1.4}

    monkeypatch.setattr(peers.yf, "Ticker", Stock)
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics(
        "2851.TW", "中再保", "Financial Services", "Insurance - Reinsurance", {},
    )

    assert "RNR" not in {row["ticker"] for row in result["peers"]}
    assert result["audit"]["usable_count"] == 3
    assert any(row["ticker"] == "RNR" and row["comparison_status"] == "identity_unverified"
               for row in result["audit"]["candidate_diagnostics"])
