import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from agent_runtime.prompting import data_for_agent_prompt  # noqa: E402
from prompt_builder import format_data_for_prompt  # noqa: E402


def _payload_from_prompt(prompt_text: str) -> dict:
    payload_text = prompt_text.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
    return json.loads(payload_text)


def _history_payload() -> dict:
    years = [str(year) for year in range(2014, 2026)]
    return {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "years": years,
        "revenue_history": list(range(len(years))),
        "net_income_history": list(range(len(years))),
        "gross_profit_history": list(range(len(years))),
        "operating_income_history": list(range(len(years))),
        "fcf_history": list(range(len(years))),
        "gross_margin_history": list(range(len(years))),
        "op_margin_history": list(range(len(years))),
        "net_margin_history": list(range(len(years))),
        "roe_history": list(range(len(years))),
        "total_assets_history": list(range(len(years))),
        "total_equity_history": list(range(len(years))),
    }


def test_macro_agent_receives_recent_three_year_history_window():
    prompt_data = data_for_agent_prompt(11, _history_payload())

    rows = _payload_from_prompt(format_data_for_prompt(prompt_data))["history"]["rows"]

    assert [row["year"] for row in rows] == ["2023", "2024", "2025"]


def test_valuation_agent_receives_deeper_ten_year_history_window():
    prompt_data = data_for_agent_prompt(14, _history_payload())

    rows = _payload_from_prompt(format_data_for_prompt(prompt_data))["history"]["rows"]

    assert [row["year"] for row in rows] == [str(year) for year in range(2016, 2026)]


def test_direct_prompt_formatting_keeps_full_history_without_agent_window():
    rows = _payload_from_prompt(format_data_for_prompt(_history_payload()))["history"]["rows"]

    assert [row["year"] for row in rows] == [str(year) for year in range(2014, 2026)]
