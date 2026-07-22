import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_backend_recommendation_labels_are_canonical():
    from report_index import normalize_recommendation_label

    aliases = {
        "買進": "買入",
        "強烈買入": "買入",
        "Buy": "買入",
        "中性觀望": "持有",
        "偏多觀察": "持有",
        "賣出": "避免",
        "減碼": "避免",
        "強烈放空": "放空",
        "做空": "放空",
        "Short": "放空",
    }

    for raw, expected in aliases.items():
        assert normalize_recommendation_label(raw) == expected


def test_recommendation_label_normalizer_uses_unknown_for_missing_tokens():
    from recommendation_labels import UNKNOWN_RECOMMENDATION, normalize_recommendation_label

    for raw in ("NaN", "Infinity", "-Infinity", "MISSING", "NIL", "-", "--", float("nan"), float("inf")):
        assert normalize_recommendation_label(raw) == UNKNOWN_RECOMMENDATION


def test_parse_recommendation_summary_returns_canonical_label(tmp_path):
    from report_history_service import parse_recommendation_summary

    filename = "2449_v3_report_20260702_010000.html"
    (tmp_path / filename).write_text("<html></html>", encoding="utf-8")
    (tmp_path / filename.replace(".html", ".md")).write_text(
        """# 2449.TW 測試報告

[投資建議]
建議：強烈放空
短期目標（3個月）：NT$220
中期目標（6個月）：NT$190
長期目標（12個月）：NT$160
信心指數：8/10
[/投資建議]
""",
        encoding="utf-8",
    )

    summary = parse_recommendation_summary(filename, output_dir=str(tmp_path))

    assert summary["recommendation"] == "放空"


def test_structured_output_normalizes_legacy_recommendation_aliases():
    from structured_output_normalizer import normalize_structured_output

    normalized = normalize_structured_output(19, {
        "reasoning_steps": ["題材過熱", "財務現實不支持", "籌碼派發"],
        "recommendation": {
            "建議": "強烈放空",
            "短期目標（3個月）": "NT$220",
            "中期目標（6個月）": "NT$190",
            "長期目標（12個月）": "NT$160",
            "長期潛力（5年）": "需重新驗證",
            "信心指數": "8/10",
        },
        "confidence_basis": {
            "evidence_items": ["P/E 河流圖高檔", "毛利率轉弱", "外資賣超"],
            "key_risks_acknowledged": ["軋空", "資料延遲"],
            "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "財測下修幅度超過市場預期", "action": "提高空方權重", "direction": "bearish_downgrade"},
            {"trigger_condition": "股價放量突破前高且基本面改善", "action": "回補並重新評估", "direction": "neutral_review"},
        ],
        "next_catalysts": [
            {"event_name": "法說會", "expected_timeframe": "下一季", "impact_direction": "bearish", "trigger_condition": "公司財測下修"}
        ],
        "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。",
    })

    assert normalized["recommendation"]["建議"] == "放空"


def test_recommendation_schema_and_frontend_filter_use_canonical_options():
    import json
    from structured_output_recommendation_outputs import BubbleSniperStructuredOutput

    schema_text = json.dumps(
        BubbleSniperStructuredOutput.model_json_schema(by_alias=True),
        ensure_ascii=False,
    )
    index_html = (ROOT / "backend/static/index.html").read_text(encoding="utf-8")

    assert "放空" in schema_text
    assert "強烈放空" not in schema_text
    assert '<option value="放空">放空</option>' in index_html
    assert '<option value="買進">買進</option>' not in index_html
    assert '<option value="強烈放空">強烈放空</option>' not in index_html
