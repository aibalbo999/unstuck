from symbol_tools import parse_watchlist_import, suggest_symbols


def test_suggest_symbols_uses_free_local_universe_and_normalizes_taiwan_codes():
    suggestions = suggest_symbols("233", limit=3)

    assert suggestions["items"][0]["ticker"] == "2330.TW"
    assert suggestions["items"][0]["market"] == "TW"
    assert all("cost_tier" in row for row in suggestions["items"])


def test_parse_watchlist_import_accepts_csv_and_pasted_symbols():
    parsed = parse_watchlist_import(
        "ticker,pipeline,schedule_slots,tags\n"
        "2330.TW,v2,pre_market|post_market,core|semi\n"
        "AAPL\n"
        "2454"
    )

    assert [item["ticker"] for item in parsed["items"]] == ["2330.TW", "AAPL", "2454.TW"]
    assert parsed["items"][0]["pipeline"] == "v2"
    assert parsed["items"][0]["schedule_slots"] == ["pre_market", "post_market"]
    assert parsed["items"][0]["tags"] == ["core", "semi"]
    assert parsed["items"][2]["pipeline"] == "v1"


def test_watchlist_symbol_and_import_routes(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api_routes.watchlist import WatchlistRouteDeps, create_watchlist_router
    import watchlist_service

    monkeypatch.setattr(watchlist_service, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    watchlist_service.reset_watchlist_store_for_tests()

    app = FastAPI()
    app.include_router(create_watchlist_router(WatchlistRouteDeps(
        get_output_dir=lambda: str(tmp_path),
        get_task_queue=lambda: None,
        run_stock_analysis_job=lambda *_args: "task-id",
        create_job=lambda *_args: "job-id",
        find_active_job=lambda *_args: {},
        require_mutation_authorized=lambda _request: None,
    )))
    client = TestClient(app)

    suggestions = client.get("/api/watchlist/symbols", params={"q": "台積"})
    imported = client.post("/api/watchlist/import", json={"text": "ticker,pipeline\n2330.TW,v2\nAAPL,v1"})

    assert suggestions.status_code == 200
    assert suggestions.json()["items"][0]["ticker"] == "2330.TW"
    assert imported.status_code == 200
    assert imported.json()["imported_count"] == 2
    assert [item["ticker"] for item in imported.json()["watchlist"]["items"]] == ["2330.TW", "AAPL"]
