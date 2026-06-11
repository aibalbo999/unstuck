import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch.market_sources import identity  # noqa: E402


def test_tpex_ticker_keeps_numeric_stock_id_for_company_identity(monkeypatch):
    monkeypatch.setattr(
        identity,
        "load_taiwan_stock_info_records",
        lambda: [
            {
                "stock_id": "3324",
                "stock_name": "雙鴻",
                "industry_category": "其他電子類",
                "type": "tpex",
            }
        ],
    )

    result = identity.build_company_identity("3324.TWO", {}, "Auras Technology Co., Ltd.")

    assert result["stock_id"] == "3324"
    assert result["official_name"] == "雙鴻"
    assert result["display_name"] == "雙鴻 / Auras Technology Co., Ltd."
    assert "雙鴻" in result["allowed_aliases"]
