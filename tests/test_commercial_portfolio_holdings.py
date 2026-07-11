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


def test_upsert_amount_holding_converts_weight_csv_and_balances_cash():
    original = "ticker,weight,sector,country\n2330.TW,45,Semi,TW\nCash,55,Cash,TW"
    added = run_holdings(
        f"holdings.upsertAmountHolding({json.dumps(original)}, "
        "{ticker: 'AAPL', amount: 600000, capital: 5000000})"
    )

    assert added == {
        "text": (
            "ticker,market_value,sector,country\n"
            "2330.TW,2250000,Semi,TW\n"
            "AAPL,600000,,\n"
            "CASH,2150000,Cash,TW"
        ),
        "error": "",
    }

    updated = run_holdings(
        f"holdings.upsertAmountHolding({json.dumps(added['text'])}, "
        "{ticker: 'AAPL', amount: 1000000, capital: 5000000})"
    )
    assert updated["error"] == ""
    assert updated["text"].count("AAPL") == 1
    assert "AAPL,1000000,," in updated["text"]
    assert "CASH,1750000,Cash,TW" in updated["text"]


def test_parse_and_remove_amount_holdings_show_weight_and_return_money_to_cash():
    csv_text = "ticker,market_value\n2330.TW,2250000\nAAPL,600000\nCash,2150000"

    assert run_holdings(
        f"holdings.parseAmountHoldings({json.dumps(csv_text)}, 5000000)"
    ) == [
        {"ticker": "2330.TW", "amount": 2_250_000, "weight": 45},
        {"ticker": "AAPL", "amount": 600_000, "weight": 12},
        {"ticker": "CASH", "amount": 2_150_000, "weight": 43},
    ]
    removed = run_holdings(
        f"holdings.removeAmountHolding({json.dumps(csv_text)}, 'AAPL', 5000000)"
    )
    assert removed == "ticker,market_value\n2330.TW,2250000\nCASH,2750000"


def test_amount_holding_rejects_non_cash_total_above_operator_capital():
    csv_text = "ticker,market_value\n2330.TW,3000000\nCash,2000000"

    result = run_holdings(
        f"holdings.upsertAmountHolding({json.dumps(csv_text)}, "
        "{ticker: 'AAPL', amount: 3000000, capital: 5000000})"
    )
    assert result["text"] == csv_text
    assert "超過操作資金" in result["error"]
