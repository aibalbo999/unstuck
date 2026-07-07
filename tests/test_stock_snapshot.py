import pytest
import json
import math


def test_stock_snapshot_route_fetches_payload_and_returns_consumer_snapshot():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api_routes.stock_snapshot import StockSnapshotRouteDeps, create_stock_snapshot_router

    captured = {}

    async def fake_fetch_payload(request):
        captured["ticker"] = request.ticker
        captured["skip_optional_http"] = request.options.skip_optional_http
        return {
            "ticker": request.ticker,
            "company_name": "Apple Inc.",
            "current_price": 200.0,
            "current_price_fmt": "$200.00",
            "analyst_target_raw": 240.0,
            "analyst_target": "$240.00",
            "data_trust": {"status": "fresh", "score": 88},
        }

    app = FastAPI()
    app.include_router(create_stock_snapshot_router(StockSnapshotRouteDeps(fetch_payload=fake_fetch_payload)))

    response = TestClient(app).get("/api/stocks/aapl/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert captured == {"ticker": "AAPL", "skip_optional_http": False}
    assert payload["ticker"] == "AAPL"
    assert payload["identity"]["company_name"] == "Apple Inc."
    assert payload["quote"]["price"] == 200.0
    assert payload["valuation"]["analyst_target"]["upside_pct"] == 20.0
    assert payload["data_quality"]["status"] == "fresh"


def test_build_stock_snapshot_removes_non_finite_numbers_for_json_responses():
    from stock_snapshot_service import build_stock_snapshot

    snapshot = build_stock_snapshot({
        "ticker": "2330.TW",
        "company_name": "台積電",
        "current_price": math.nan,
        "previous_close": math.inf,
        "analyst_target_raw": -math.inf,
        "price_history": {
            "dates": ["2026-07-01", "2026-07-02"],
            "prices": [math.nan, 950.0],
        },
        "data_trust": {"status": "fresh", "score": math.nan},
    })

    assert snapshot["quote"]["price"] is None
    assert snapshot["market_session"]["previous_close"] is None
    assert snapshot["valuation"]["analyst_target"]["price"] is None
    assert snapshot["price_trend"]["sparkline"][0]["price"] == 950.0
    assert snapshot["data_quality"]["score"] is None
    json.dumps(snapshot, allow_nan=False)


def test_build_stock_snapshot_turns_provider_payload_into_consumer_sections():
    from stock_snapshot_service import build_stock_snapshot

    payload = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "company_summary": "台積電提供晶圓代工與先進封裝服務，服務全球無晶圓廠客戶。",
        "website": "https://www.tsmc.com",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "Taiwan",
        "exchange": "TAI",
        "currency": "TWD",
        "financial_currency": "TWD",
        "employees": 77000,
        "current_price": 950.0,
        "current_price_fmt": "NT$950.00",
        "open": 940.0,
        "previous_close": 930.0,
        "day_high": 955.0,
        "day_low": 925.0,
        "volume": 130_000_000,
        "avg_volume": 100_000_000,
        "market_cap_raw": 24_600_000_000_000,
        "market_cap_fmt": "NT$246,000億",
        "revenue_ttm_raw": 2_500_000_000_000,
        "revenue_ttm": "NT$25,000.00億",
        "latest_annual_revenue_growth": "18.4%",
        "years": ["2023", "2024", "2025", "2026"],
        "revenue_history": [1800.0, 2000.0, 2500.0, 3200.0],
        "net_income_history": [650.0, 720.0, 900.0, 1100.0],
        "fcf_history": [450.0, 550.0, 850.0, 900.0],
        "gross_margin_history": [52.0, 53.0, 56.0, 57.0],
        "op_margin_history": [40.0, 42.0, 45.0, 46.0],
        "net_margin_history": [36.1, 36.0, 36.0, 34.4],
        "roe_history": [27.0, 28.0, 30.0, 31.0],
        "gross_margin_raw": 0.56,
        "gross_margin": "56.0%",
        "operating_margin_raw": 0.45,
        "operating_margin": "45.0%",
        "profit_margin_raw": 0.38,
        "profit_margin": "38.0%",
        "roe": "31.0%",
        "roa": "16.5%",
        "free_cash_flow_raw": 850_000_000_000,
        "free_cash_flow": "NT$8,500.00億",
        "shares_outstanding_raw": 1_000_000_000,
        "float_shares": 800_000_000,
        "held_percent_insiders": 0.12,
        "held_percent_institutions": 0.70,
        "shares_short": 20_000_000,
        "short_ratio": 1.8,
        "short_percent_of_float": 0.025,
        "total_cash_raw": 1_900_000_000_000,
        "total_cash": "NT$19,000.00億",
        "total_debt_raw": 900_000_000_000,
        "total_debt": "NT$9,000.00億",
        "debt_to_equity": "28.0%",
        "current_ratio": "2.10",
        "pe_ratio_raw": 22.5,
        "pe_ratio": "22.5x",
        "forward_pe_raw": 19.8,
        "forward_pe": "19.8x",
        "pb_ratio": "6.20x",
        "ps_ratio": "9.10x",
        "week_52_high": 1000.0,
        "week_52_low": 580.0,
        "beta": "1.05",
        "dividend_yield_raw": 0.025,
        "dividend_yield": "2.50%",
        "dividend_rate_raw": 12.0,
        "dividend_rate": "NT$12.00",
        "payout_ratio_raw": 0.42,
        "payout_ratio": "42.00%",
        "event_calendar": {
            "as_of_date": "2026-07-05",
            "events": [
                {
                    "type": "earnings_date",
                    "label": "財報日",
                    "date": "2026-07-18",
                    "end_date": "2026-07-20",
                    "source": "yfinance calendar",
                },
                {
                    "type": "ex_dividend_date",
                    "label": "除息日",
                    "date": "2026-08-01",
                    "source": "yfinance calendar",
                },
                {
                    "type": "dividend_pay_date",
                    "label": "股利發放日",
                    "date": "2026-08-07",
                    "source": "yfinance info",
                },
                {
                    "type": "most_recent_quarter",
                    "label": "最近財報季度",
                    "date": "2026-03-31",
                    "source": "yfinance info",
                },
            ],
        },
        "dividend_history": {
            "years": ["2022", "2023", "2024", "2025", "2026"],
            "dividends": [8.5, 10.0, 11.5, 12.0, 13.0],
            "records": [
                {"date": "2022-07-01", "amount": 8.5},
                {"date": "2023-07-01", "amount": 10.0},
                {"date": "2024-07-01", "amount": 11.5},
                {"date": "2025-07-01", "amount": 12.0},
                {"date": "2026-07-01", "amount": 13.0},
            ],
            "source": "yfinance dividends",
        },
        "analyst_target": "NT$1050.00",
        "analyst_target_raw": 1050.0,
        "analyst_rec": "buy",
        "analyst_count": "32",
        "trailing_eps": 45.0,
        "forward_eps": 50.0,
        "yahoo_earnings_growth_raw": 0.14,
        "yahoo_earnings_growth": "14.0%",
        "pe_river_chart": {
            "years": ["2024", "2025", "2026"],
            "eps_twd": [40.0, 45.0, 50.0],
            "multiples": [15, 20, 25],
            "bands": {
                "15x": [600.0, 675.0, 750.0],
                "20x": [800.0, 900.0, 1000.0],
                "25x": [1000.0, 1125.0, 1250.0],
            },
            "source": "FinMind 5-year PER quantiles",
        },
        "recent_catalysts": [
            {"title": "先進製程需求強勁", "source": "Reuters", "published_at": "2026-07-01"},
        ],
        "recent_monthly_revenue": ["2026年6月: NT$2,100.00億"],
        "earnings_call": {"period": "2026Q1", "source": "MOPS", "transcript_excerpt": "AI demand remains strong."},
        "institutional_trading": {
            "summary": "外資連 3 日買超",
            "latest_date": "2026-07-03",
            "trend": "accumulation",
            "total_net_buy_thousand_shares": 2500.0,
            "last_5_trading_days_net_buy_thousand_shares": 1200.0,
            "net_buy_thousand_shares_by_category": {
                "foreign": 1200.0,
                "investment_trust": 800.0,
                "dealer": 500.0,
            },
            "foreign_investors": [{"date": "2026-07-03", "net_buy_thousand_shares": 1200}],
        },
        "chip_data": {
            "twse_margin_short_sales": {"status": "success", "margin_balance": 12000, "short_balance": 350},
            "tdcc_shareholder_distribution": {
                "status": "success",
                "major_holders_gt_1000_lots_pct": 78.5,
                "retail_holders_lt_50_lots_pct": 12.3,
                "as_of_date": "20260703",
            },
        },
        "dynamic_peer_metrics": [
            {
                "name": "聯電",
                "ticker": "2303.TW",
                "gross_margin_pct": 36.0,
                "roe_pct": 17.5,
                "pe_ttm": 14.0,
                "ps_ttm": 3.0,
                "source": "FinMind industry peer + yfinance metrics",
            },
            {
                "name": "Samsung Electronics",
                "ticker": "005930.KS",
                "gross_margin_pct": 42.0,
                "roe_pct": 9.2,
                "pe_ttm": 22.0,
                "ps_ttm": 2.1,
                "source": "global peer heuristic + yfinance metrics",
            },
            {
                "name": "Intel",
                "ticker": "INTC",
                "gross_margin_pct": 38.0,
                "roe_pct": 5.0,
                "pe_ttm": 30.0,
                "ps_ttm": 2.6,
                "source": "global peer heuristic + yfinance metrics",
            },
        ],
        "data_trust": {"status": "fresh", "score": 92, "reason_codes": ["fresh_core_sources"]},
        "price_history": {
            "dates": [
                "2025-08-31",
                "2025-09-30",
                "2025-10-31",
                "2025-11-30",
                "2025-12-31",
                "2026-01-31",
                "2026-02-28",
                "2026-03-31",
                "2026-04-30",
                "2026-05-31",
                "2026-06-30",
                "2026-07-31",
            ],
            "prices": [700, 720, 760, 780, 800, 820, 840, 860, 880, 900, 920, 950],
        },
        "price_history_ranges": {
            "source": "yfinance 5y history",
            "ranges": {
                "1m": {
                    "label": "1M",
                    "dates": ["2026-06-30", "2026-07-31"],
                    "prices": [920, 950],
                    "return_pct": 3.26,
                },
                "3m": {
                    "label": "3M",
                    "dates": ["2026-04-30", "2026-05-31", "2026-06-30", "2026-07-31"],
                    "prices": [880, 900, 920, 950],
                    "return_pct": 7.95,
                },
                "6m": {
                    "label": "6M",
                    "dates": ["2026-01-31", "2026-04-30", "2026-07-31"],
                    "prices": [820, 880, 950],
                    "return_pct": 15.85,
                },
                "1y": {
                    "label": "1Y",
                    "dates": ["2025-08-31", "2026-01-31", "2026-07-31"],
                    "prices": [700, 820, 950],
                    "return_pct": 35.71,
                },
                "3y": {
                    "label": "3Y",
                    "dates": ["2023-07-31", "2025-07-31", "2026-07-31"],
                    "prices": [500, 700, 950],
                    "return_pct": 90.0,
                },
                "5y": {
                    "label": "5Y",
                    "dates": ["2021-07-31", "2023-07-31", "2026-07-31"],
                    "prices": [300, 500, 950],
                    "return_pct": 216.67,
                },
            },
        },
    }

    snapshot = build_stock_snapshot(payload)

    assert snapshot["ticker"] == "2330.TW"
    assert snapshot["identity"]["company_name"] == "台積電"
    assert snapshot["company_profile"]["status"] == "available"
    assert snapshot["company_profile"]["label"] == "公司檔案"
    assert snapshot["company_profile"]["summary"] == "台積電提供晶圓代工與先進封裝服務，服務全球無晶圓廠客戶。"
    assert snapshot["company_profile"]["website"] == "https://www.tsmc.com"
    assert snapshot["company_profile"]["facts"] == [
        {"label": "產業", "value": "Technology / Semiconductors"},
        {"label": "市場", "value": "Taiwan · TAI"},
        {"label": "幣別", "value": "TWD"},
        {"label": "員工", "value": "77,000"},
    ]
    assert snapshot["quote"]["price"] == 950.0
    assert snapshot["quote"]["price_label"] == "NT$950.00"
    assert snapshot["quote"]["range_52w"] == {"high": 1000.0, "low": 580.0}
    assert snapshot["market_session"]["change"] == 20.0
    assert snapshot["market_session"]["change_pct"] == pytest.approx(2.15, rel=0.001)
    assert snapshot["market_session"]["direction"] == "up"
    assert snapshot["market_session"]["open"] == 940.0
    assert snapshot["market_session"]["previous_close"] == 930.0
    assert snapshot["market_session"]["day_range"] == {"low": 925.0, "high": 955.0}
    assert snapshot["market_session"]["day_position_pct"] == pytest.approx(83.33, rel=0.001)
    assert snapshot["market_session"]["volume"] == 130_000_000.0
    assert snapshot["market_session"]["volume_vs_avg_pct"] == pytest.approx(30.0, rel=0.001)
    assert snapshot["valuation"]["pe_ratio"]["value"] == 22.5
    assert snapshot["valuation"]["analyst_target"]["upside_pct"] == pytest.approx(10.53, rel=0.001)
    assert snapshot["analyst_outlook"]["status"] == "available"
    assert snapshot["analyst_outlook"]["label"] == "目標價上行"
    assert snapshot["analyst_outlook"]["target"]["price"] == 1050.0
    assert snapshot["analyst_outlook"]["target"]["upside_pct"] == pytest.approx(10.53, rel=0.001)
    assert snapshot["analyst_outlook"]["consensus"]["recommendation"] == "buy"
    assert snapshot["analyst_outlook"]["consensus"]["recommendation_label"] == "買進"
    assert snapshot["analyst_outlook"]["consensus"]["analyst_count"] == 32
    assert snapshot["analyst_outlook"]["valuation"]["forward_pe"]["value"] == 19.8
    assert snapshot["analyst_outlook"]["growth"]["earnings_growth"]["value"] == 14.0
    assert snapshot["analyst_outlook"]["growth"]["earnings_growth"]["label"] == "14.0%"
    assert snapshot["analyst_outlook"]["signals"] == [
        "目標價上行 +10.5%",
        "32 位分析師共識買進",
        "EPS 成長 14.0%",
    ]
    assert snapshot["earnings_forecast"]["status"] == "available"
    assert snapshot["earnings_forecast"]["label"] == "EPS 預期成長"
    assert snapshot["earnings_forecast"]["trailing_eps"]["value"] == 45.0
    assert snapshot["earnings_forecast"]["forward_eps"]["value"] == 50.0
    assert snapshot["earnings_forecast"]["forward_eps_change_pct"] == pytest.approx(11.11, rel=0.001)
    assert snapshot["earnings_forecast"]["growth"]["earnings_growth"]["value"] == 14.0
    assert snapshot["earnings_forecast"]["analyst_count"] == 32
    assert snapshot["earnings_forecast"]["next_earnings"] == {
        "type": "earnings_date",
        "label": "財報日",
        "date": "2026-07-18",
        "days_until": 13,
    }
    assert snapshot["earnings_forecast"]["signals"] == [
        "Forward EPS +11.1%",
        "EPS 成長 14.0%",
        "32 位分析師覆蓋",
    ]
    assert snapshot["share_statistics"]["status"] == "available"
    assert snapshot["share_statistics"]["label"] == "機構持股高"
    assert snapshot["share_statistics"]["shares_outstanding"] == 1_000_000_000.0
    assert snapshot["share_statistics"]["float_shares"] == 800_000_000.0
    assert snapshot["share_statistics"]["float_pct_of_shares"] == pytest.approx(80.0, rel=0.001)
    assert snapshot["share_statistics"]["insider_ownership_pct"] == pytest.approx(12.0, rel=0.001)
    assert snapshot["share_statistics"]["institutional_ownership_pct"] == pytest.approx(70.0, rel=0.001)
    assert snapshot["share_statistics"]["short_interest"] == {
        "shares_short": 20_000_000.0,
        "short_ratio": 1.8,
        "short_percent_of_float_pct": pytest.approx(2.5),
    }
    assert snapshot["share_statistics"]["signals"] == [
        "流通股 80.0%",
        "機構持股 70.0%",
        "空單占流通股 2.5%",
    ]
    assert snapshot["risk_liquidity"]["status"] == "available"
    assert snapshot["risk_liquidity"]["label"] == "流動性活躍"
    assert snapshot["risk_liquidity"]["beta"]["value"] == 1.05
    assert snapshot["risk_liquidity"]["drawdown_from_52w_high_pct"] == pytest.approx(-5.0, rel=0.001)
    assert snapshot["risk_liquidity"]["volume_vs_avg_pct"] == pytest.approx(30.0, rel=0.001)
    assert snapshot["risk_liquidity"]["debt_to_equity_pct"] == pytest.approx(28.0, rel=0.001)
    assert snapshot["risk_liquidity"]["current_ratio"]["value"] == 2.1
    assert snapshot["risk_liquidity"]["signals"] == [
        "Beta 1.05",
        "距52週高點 -5.0%",
        "成交量較均量 +30.0%",
    ]
    assert snapshot["profitability_quality"]["status"] == "available"
    assert snapshot["profitability_quality"]["label"] == "獲利品質強"
    assert snapshot["profitability_quality"]["gross_margin_pct"] == pytest.approx(56.0)
    assert snapshot["profitability_quality"]["operating_margin_pct"] == pytest.approx(45.0)
    assert snapshot["profitability_quality"]["net_margin_pct"] == pytest.approx(38.0)
    assert snapshot["profitability_quality"]["roe_pct"] == pytest.approx(31.0)
    assert snapshot["profitability_quality"]["roa_pct"] == pytest.approx(16.5)
    assert snapshot["profitability_quality"]["fcf_margin_pct"] == pytest.approx(34.0)
    assert snapshot["profitability_quality"]["signals"] == [
        "ROE 31.0%",
        "淨利率 38.0%",
        "FCF margin 34.0%",
    ]
    assert snapshot["dividends"]["yield_label"] == "2.50%"
    assert snapshot["dividend_profile"]["status"] == "available"
    assert snapshot["dividend_profile"]["label"] == "配息穩定"
    assert snapshot["dividend_profile"]["annual_dividend"]["value"] == 12.0
    assert snapshot["dividend_profile"]["yield"]["value"] == 0.025
    assert snapshot["dividend_profile"]["payout_ratio"]["value"] == 0.42
    assert snapshot["dividend_profile"]["history"]["years"] == ["2022", "2023", "2024", "2025", "2026"]
    assert snapshot["dividend_profile"]["history"]["dividends"] == [8.5, 10.0, 11.5, 12.0, 13.0]
    assert snapshot["dividend_profile"]["history"]["year_count"] == 5
    assert snapshot["dividend_profile"]["history"]["latest_annual_dividend"] == 13.0
    assert snapshot["dividend_profile"]["history"]["latest_yoy_pct"] == pytest.approx(8.33, rel=0.001)
    assert snapshot["dividend_profile"]["coverage"]["fcf_coverage_ratio"] == pytest.approx(70.83, rel=0.001)
    assert snapshot["dividend_profile"]["signals"] == [
        "連續 5 年有配息",
        "近一年配息成長 +8.3%",
        "FCF 覆蓋 70.8x",
    ]
    assert snapshot["event_calendar"]["status"] == "available"
    assert snapshot["event_calendar"]["label"] == "下一事件：財報日"
    assert snapshot["event_calendar"]["next_event"]["type"] == "earnings_date"
    assert snapshot["event_calendar"]["next_event"]["days_until"] == 13
    assert snapshot["event_calendar"]["events"][:3] == [
        {
            "type": "earnings_date",
            "label": "財報日",
            "date": "2026-07-18",
            "end_date": "2026-07-20",
            "date_label": "2026-07-18 - 2026-07-20",
            "timing": "upcoming",
            "days_until": 13,
            "source": "yfinance calendar",
        },
        {
            "type": "ex_dividend_date",
            "label": "除息日",
            "date": "2026-08-01",
            "end_date": "",
            "date_label": "2026-08-01",
            "timing": "upcoming",
            "days_until": 27,
            "source": "yfinance calendar",
        },
        {
            "type": "dividend_pay_date",
            "label": "股利發放日",
            "date": "2026-08-07",
            "end_date": "",
            "date_label": "2026-08-07",
            "timing": "upcoming",
            "days_until": 33,
            "source": "yfinance info",
        },
    ]
    assert snapshot["alert_suggestions"]["status"] == "available"
    assert snapshot["alert_suggestions"]["label"] == "建議設定 4 個提醒"
    assert [item["key"] for item in snapshot["alert_suggestions"]["suggestions"]] == [
        "event_earnings_date_2026-07-18",
        "price_analyst_target",
        "price_52w_high",
        "monthly_revenue_record",
    ]
    assert snapshot["alert_suggestions"]["suggestions"][0] == {
        "key": "event_earnings_date_2026-07-18",
        "category": "event",
        "label": "財報日前提醒",
        "detail": "財報日 2026-07-18 前 14 天提醒",
        "pipeline": "v4",
        "schedule_slots": ["pre_market"],
        "triggers": [
            {
                "type": "event_upcoming",
                "event_type": "earnings_date",
                "target_date": "2026-07-18",
                "days_before": 14,
                "label": "財報日",
            }
        ],
    }
    assert snapshot["alert_suggestions"]["suggestions"][1]["triggers"] == [
        {
            "type": "price_near_level",
            "label": "接近分析師目標價",
            "target_price": 1050.0,
            "threshold_pct": 5.0,
        }
    ]
    assert snapshot["alert_suggestions"]["suggestions"][2]["triggers"][0]["target_price"] == 1000.0
    assert snapshot["alert_suggestions"]["suggestions"][3]["triggers"] == [
        {"type": "revenue_record_high", "volume_ratio_threshold": 1.3}
    ]
    assert snapshot["financial_health"]["revenue_ttm"]["label"] == "NT$25,000.00億"
    assert snapshot["financial_health"]["revenue_growth"]["label"] == "18.4%"
    assert snapshot["financial_health"]["gross_margin"]["label"] == "56.0%"
    assert snapshot["financial_health"]["profit_margin"]["label"] == "38.0%"
    assert snapshot["financial_health"]["free_cash_flow"]["label"] == "NT$8,500.00億"
    assert snapshot["financial_health"]["balance_sheet"]["cash_label"] == "NT$19,000.00億"
    assert snapshot["financial_health"]["balance_sheet"]["debt_label"] == "NT$9,000.00億"
    assert snapshot["financial_health"]["highlights"] == ["營收成長", "FCF 為正", "現金高於負債"]
    assert snapshot["financial_trends"]["status"] == "available"
    assert snapshot["financial_trends"]["label"] == "營收與獲利成長"
    assert snapshot["financial_trends"]["period_type"] == "annual"
    assert snapshot["financial_trends"]["signals"] == [
        "營收 YoY +28.0%",
        "淨利 YoY +22.2%",
        "FCF YoY +5.9%",
    ]
    assert snapshot["financial_trends"]["rows"][-1] == {
        "period": "2026",
        "revenue": 3200.0,
        "revenue_yoy_pct": pytest.approx(28.0),
        "net_income": 1100.0,
        "net_income_yoy_pct": pytest.approx(22.22),
        "free_cash_flow": 900.0,
        "free_cash_flow_yoy_pct": pytest.approx(5.88),
        "gross_margin_pct": 57.0,
        "operating_margin_pct": 46.0,
        "net_margin_pct": 34.4,
        "roe_pct": 31.0,
    }
    assert snapshot["peer_comparison"]["summary"]["peer_count"] == 3
    assert snapshot["peer_comparison"]["summary"]["valuation_label"] == "接近同業"
    assert snapshot["peer_comparison"]["summary"]["pe_vs_peer_median_pct"] == pytest.approx(2.27, rel=0.001)
    assert snapshot["peer_comparison"]["summary"]["gross_margin_spread_pct"] == pytest.approx(18.0, rel=0.001)
    assert snapshot["peer_comparison"]["target"]["ticker"] == "2330.TW"
    assert snapshot["peer_comparison"]["target"]["gross_margin_pct"] == 56.0
    assert [row["ticker"] for row in snapshot["peer_comparison"]["peers"]] == ["2303.TW", "005930.KS", "INTC"]
    assert snapshot["valuation_range"]["status"] == "available"
    assert snapshot["valuation_range"]["label"] == "合理區間"
    assert snapshot["valuation_range"]["current_price"] == 950.0
    assert snapshot["valuation_range"]["mid_price"] == 1000.0
    assert snapshot["valuation_range"]["price_vs_mid_pct"] == pytest.approx(-5.0, rel=0.001)
    assert snapshot["valuation_range"]["bands"] == [
        {"label": "15x", "multiple": 15.0, "price": 750.0},
        {"label": "20x", "multiple": 20.0, "price": 1000.0},
        {"label": "25x", "multiple": 25.0, "price": 1250.0},
    ]
    assert snapshot["events"][0]["type"] == "monthly_revenue"
    assert snapshot["news"][0]["title"] == "先進製程需求強勁"
    assert snapshot["chip"]["institutional_summary"] == "外資連 3 日買超"
    assert snapshot["ownership_flow"]["status"] == "available"
    assert snapshot["ownership_flow"]["label"] == "法人買超"
    assert snapshot["ownership_flow"]["institutional"]["total_net_buy_thousand_shares"] == 2500.0
    assert snapshot["ownership_flow"]["institutional"]["last_5_trading_days_net_buy_thousand_shares"] == 1200.0
    assert snapshot["ownership_flow"]["institutional"]["categories"] == [
        {"key": "foreign", "label": "外資", "net_buy_thousand_shares": 1200.0},
        {"key": "investment_trust", "label": "投信", "net_buy_thousand_shares": 800.0},
        {"key": "dealer", "label": "自營商", "net_buy_thousand_shares": 500.0},
    ]
    assert snapshot["ownership_flow"]["margin"]["margin_balance"] == 12000.0
    assert snapshot["ownership_flow"]["margin"]["short_balance"] == 350.0
    assert snapshot["ownership_flow"]["holders"]["major_holders_gt_1000_lots_pct"] == 78.5
    assert snapshot["ownership_flow"]["holders"]["retail_holders_lt_50_lots_pct"] == 12.3
    assert snapshot["ownership_flow"]["signals"] == [
        "近30日法人合計買超 2,500張",
        "外資買超 1,200張",
        "千張以上大戶 78.5%",
    ]
    assert snapshot["data_quality"]["status"] == "fresh"
    assert snapshot["price_trend"]["latest_price"] == 950.0
    assert snapshot["price_trend"]["returns"]["1m"] == pytest.approx(3.26, rel=0.001)
    assert snapshot["price_trend"]["returns"]["3m"] == pytest.approx(7.95, rel=0.001)
    assert snapshot["price_trend"]["returns"]["1y"] == pytest.approx(35.71, rel=0.001)
    assert len(snapshot["price_trend"]["sparkline"]) == 12
    assert snapshot["performance_history"]["status"] == "available"
    assert snapshot["performance_history"]["label"] == "多週期走勢"
    assert snapshot["performance_history"]["default_range"] == "1y"
    assert [item["key"] for item in snapshot["performance_history"]["ranges"]] == ["1m", "3m", "6m", "1y", "3y", "5y"]
    assert snapshot["performance_history"]["ranges"][0]["return_pct"] == pytest.approx(3.26, rel=0.001)
    assert snapshot["performance_history"]["ranges"][0]["points"] == [
        {"date": "2026-06-30", "price": 920.0},
        {"date": "2026-07-31", "price": 950.0},
    ]
    assert snapshot["performance_history"]["ranges"][-1]["return_pct"] == pytest.approx(216.67, rel=0.001)
    assert snapshot["performance_history"]["source"] == "yfinance 5y history"
    assert snapshot["technical_summary"]["status"] == "available"
    assert snapshot["technical_summary"]["label"] == "上升趨勢"
    assert snapshot["technical_summary"]["moving_averages"]["ma_3m"]["value"] == pytest.approx(923.33, rel=0.001)
    assert snapshot["technical_summary"]["moving_averages"]["ma_3m"]["distance_pct"] == pytest.approx(2.89, rel=0.001)
    assert snapshot["technical_summary"]["moving_averages"]["ma_6m"]["value"] == pytest.approx(891.67, rel=0.001)
    assert snapshot["technical_summary"]["moving_averages"]["ma_12m"]["value"] == pytest.approx(827.5, rel=0.001)
    assert snapshot["technical_summary"]["range_52w"]["position_pct"] == pytest.approx(88.1, rel=0.001)
    assert snapshot["technical_summary"]["range_52w"]["drawdown_from_high_pct"] == pytest.approx(-5.0, rel=0.001)
    assert snapshot["technical_summary"]["momentum"]["3m"] == pytest.approx(7.95, rel=0.001)
    assert snapshot["technical_summary"]["signals"] == [
        "現價高於 3M / 6M 均線",
        "接近 52 週高檔",
        "3M 動能 +8.0%",
    ]
    assert [item["pipeline_id"] for item in snapshot["mode_suggestions"]] == ["v1", "v2", "v3", "v4"]


def test_dividend_profile_uses_legacy_shares_raw_for_fcf_coverage():
    from stock_snapshot_service import build_stock_snapshot

    snapshot = build_stock_snapshot(
        {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "free_cash_flow_raw": 220_000_000,
            "shares_raw": 100_000_000,
            "dividend_rate_raw": 2.0,
            "dividend_rate": "NT$2.00",
            "dividend_history": {
                "years": ["2023", "2024", "2025"],
                "dividends": [1.6, 1.8, 2.0],
            },
        }
    )

    assert snapshot["dividend_profile"]["coverage"]["shares_outstanding"] == 100_000_000
    assert snapshot["dividend_profile"]["coverage"]["dividend_cash_required"] == 200_000_000
    assert snapshot["dividend_profile"]["coverage"]["fcf_coverage_ratio"] == pytest.approx(1.1)
    assert snapshot["dividend_profile"]["signals"][-1] == "FCF 覆蓋 1.1x"
