from portfolio_risk import analyze_portfolio_csv, parse_portfolio_csv


def test_parse_portfolio_csv_accepts_weights_or_market_values():
    rows = parse_portfolio_csv(
        "ticker,weight,sector,country\n"
        "2330.TW,45,Semiconductors,TW\n"
        "AAPL,25,Technology,US\n"
    )

    assert rows == [
        {"ticker": "2330.TW", "weight_pct": 45.0, "sector": "Semiconductors", "country": "TW"},
        {"ticker": "AAPL", "weight_pct": 25.0, "sector": "Technology", "country": "US"},
    ]


def test_analyze_portfolio_csv_flags_concentration_and_thesis_health():
    csv_text = (
        "ticker,market_value,sector,country\n"
        "2330.TW,600000,Semiconductors,TW\n"
        "2454.TW,250000,Semiconductors,TW\n"
        "AAPL,150000,Technology,US\n"
    )
    thesis_health = {
        "2330.TW": {"status": "healthy"},
        "2454.TW": {"status": "invalidated", "reason": "毛利率紅線失守"},
    }

    report = analyze_portfolio_csv(csv_text, thesis_health=thesis_health)

    assert report["schema_version"] == "portfolio_risk.v1"
    assert report["total_positions"] == 3
    assert report["positions"][0]["weight_pct"] == 60.0
    assert report["concentration"]["top_position"]["ticker"] == "2330.TW"
    assert "single_position_over_40_pct" in report["risk_flags"]
    assert "sector_over_60_pct" in report["risk_flags"]
    assert report["thesis_health"]["invalidated"] == ["2454.TW"]


def test_watchlist_portfolio_risk_route(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api_routes.watchlist import WatchlistRouteDeps, create_watchlist_router

    app = FastAPI()
    app.include_router(create_watchlist_router(WatchlistRouteDeps(
        get_output_dir=lambda: str(tmp_path),
        get_task_queue=lambda: None,
        run_stock_analysis_job=lambda *_args: "task-id",
        create_job=lambda *_args: "job-id",
        find_active_job=lambda *_args: {},
        require_mutation_authorized=lambda _request: None,
    )))

    response = TestClient(app).post(
        "/api/watchlist/portfolio/risk",
        json={"csv": "ticker,weight,sector,country\n2330.TW,55,Semiconductors,TW\nAAPL,45,Technology,US"},
    )

    assert response.status_code == 200
    assert response.json()["risk_flags"] == ["single_position_over_40_pct"]
