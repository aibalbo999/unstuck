import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    ROOT / "backend" / "static" / "commercial" / "shared" / "portfolio_holdings.js"
).as_uri()


def run_holdings(expression: str):
    script = f"""
      import * as holdings from {json.dumps(MODULE)};
      process.stdout.write(JSON.stringify({{value: {expression}}}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["value"]


def test_upsert_weight_holding_adds_and_updates_without_losing_extra_columns():
    original = "ticker,weight,sector,country\n2330.TW,45,Semi,TW"
    added = run_holdings(
        f"holdings.upsertWeightHolding({json.dumps(original)}, "
        "{ticker: 'AAPL', weight: 20})"
    )

    assert added == {
        "text": "ticker,weight,sector,country\n2330.TW,45,Semi,TW\nAAPL,20,,",
        "error": "",
    }

    updated = run_holdings(
        f"holdings.upsertWeightHolding({json.dumps(added['text'])}, "
        "{ticker: '2330.TW', weight: 30})"
    )
    assert updated["error"] == ""
    assert updated["text"].count("2330.TW") == 1
    assert "2330.TW,30,Semi,TW" in updated["text"]


def test_parse_and_remove_weight_holdings_keep_csv_in_sync():
    csv_text = "ticker,weight_pct\n2330.TW,60\nCash,40"

    assert run_holdings(
        f"holdings.parseWeightHoldings({json.dumps(csv_text)})"
    ) == [
        {"ticker": "2330.TW", "weight": 60},
        {"ticker": "CASH", "weight": 40},
    ]
    assert run_holdings(
        f"holdings.removeHolding({json.dumps(csv_text)}, '2330.TW')"
    ) == "ticker,weight_pct\nCash,40"


def test_holding_selector_refuses_to_rewrite_market_value_csv():
    csv_text = "ticker,market_value\n2330.TW,3000000\nCash,2000000"

    result = run_holdings(
        f"holdings.upsertWeightHolding({json.dumps(csv_text)}, "
        "{ticker: 'AAPL', weight: 10})"
    )
    assert result["text"] == csv_text
    assert "market_value" in result["error"]
