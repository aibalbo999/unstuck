import pytest
from pydantic import ValidationError
from pathlib import Path

from agent_catalog import AGENT_NAMES
from agent_runtime.prompt_config import ANALYSIS_PROMPTS, SYSTEM_PROMPTS
from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
from config import AGENT_MODELS
from final_audit import run_final_report_audit
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from reporting.html_renderer import generate_html_report
from reporting.markdown_renderer import generate_markdown_report
from report_index_parsing import parse_report_filename
import report_history_service
from structured_output_models import SwingTradeSetup, get_structured_response_schema
from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text
from structured_output_parser import parse_structured_data


TRADE_SETUP = {
    "trade_direction": "Long",
    "entry_zone": "NT$168-172",
    "target_price": "NT$188（前高壓力區）",
    "stop_loss": "NT$162（跌破 20 日均線）",
    "core_catalyst": "下週法說會可能釋出新產品出貨上修訊號。",
    "risk_level": "Medium",
}
ROOT = Path(__file__).resolve().parents[1]


def test_v4_pipeline_definition_and_aliases_are_registered():
    definition = get_pipeline_definition("v4")

    assert definition == {
        "id": "v4",
        "label": "模式 D：極短線波段與事件驅動",
        "short_label": "短線波段派",
        "report_title": "極短線 (1-2週) 交易策略報告",
        "report_subtitle": "基於技術動能、主力籌碼與近期催化劑的狙擊計畫",
        "hint_text": "請稍候，AI 動能分析師正在比對技術突破點、籌碼集中度與近期事件催化劑...",
        "agents": (22, 23, 24),
        "groups": ((22, 23), (24,)),
        "structured_agents": {"trade_setup": 24},
        "debate_agents": (),
    }
    for alias in ("d", "swing", "short_term", "momentum", "v4"):
        assert normalize_pipeline_id(alias) == "v4"


def test_v4_agents_have_names_prompts_and_model_routes():
    for agent_num in (22, 23, 24):
        assert agent_num in AGENT_NAMES
        assert agent_num in SYSTEM_PROMPTS
        assert agent_num in ANALYSIS_PROMPTS
        assert agent_num in AGENT_MODELS

    assert "RSI" in SYSTEM_PROMPTS[22]
    assert "外資" in SYSTEM_PROMPTS[23]
    assert "stop_loss" in SYSTEM_PROMPTS[24]


def test_swing_trade_setup_is_strictly_validated_and_normalized():
    assert get_structured_response_schema(24) is SwingTradeSetup
    assert SwingTradeSetup.model_validate(TRADE_SETUP).model_dump() == TRADE_SETUP

    with pytest.raises(ValidationError):
        SwingTradeSetup.model_validate({**TRADE_SETUP, "trade_direction": "Buy"})
    with pytest.raises(ValidationError):
        SwingTradeSetup.model_validate({key: value for key, value in TRADE_SETUP.items() if key != "stop_loss"})

    assert normalize_structured_output(24, TRADE_SETUP) == TRADE_SETUP


def test_v4_trade_setup_is_parsed_and_rendered_as_report_text():
    context = {
        "pipeline_id": "v4",
        "structured_outputs": {24: TRADE_SETUP},
        "analyses": {},
        "data": {},
    }

    parsed = parse_structured_data(context)
    report_text = structured_output_to_report_text(24, TRADE_SETUP)

    assert parsed["trade_setup"] == TRADE_SETUP
    assert "交易方向：Long" in report_text
    assert "停損點：NT$162" in report_text
    assert "核心催化劑" in report_text


def test_v4_html_report_contains_trade_setup_dashboard():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v4",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "fetch_date": "2026年06月20日",
            "sector": "Technology",
            "industry": "Semiconductors",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {
            22: "## 技術動能\n價量同步轉強。",
            23: "## 籌碼\n法人連續買超。",
            24: structured_output_to_report_text(24, TRADE_SETUP),
        },
        "structured_outputs": {24: TRADE_SETUP},
        "parsed": {"moat_scores": {}, "price_targets": {}, "recommendation": {}, "trade_setup": TRADE_SETUP},
        "total_time": 1,
    }

    html = generate_html_report(context)

    assert 'class="trade-setup-dashboard"' in html
    assert "短線交易計畫看板" in html
    assert "交易方向" in html
    assert "進場區間" in html
    assert "NT$168-172" in html
    assert "🛑 停損點" in html
    assert "下週法說會可能釋出新產品出貨上修訊號。" in html
    assert "1-2週目標" in html


def test_v4_final_audit_accepts_trade_setup_without_long_term_recommendation():
    context = {
        "pipeline_id": "v4",
        "agent_sequence": (22, 23, 24),
        "data": {"data_trust": {"status": "fresh"}},
        "analyses": {
            22: "## 技術動能\n價量同步轉強。",
            23: "## 主力籌碼\n法人連續買超。",
            24: structured_output_to_report_text(24, TRADE_SETUP),
        },
        "structured_outputs": {24: TRADE_SETUP},
        "parsed": {"moat_scores": {}, "price_targets": {}, "recommendation": {}, "trade_setup": TRADE_SETUP},
    }

    audit = run_final_report_audit(context, append_section=False)

    assert audit["critical"] == []


def test_v4_markdown_uses_short_term_trade_setup():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v4",
        "data": {"ticker": "2330.TW", "company_name": "台積電", "data_trust": {}},
        "analyses": {22: "技術。", 23: "籌碼。", 24: structured_output_to_report_text(24, TRADE_SETUP)},
        "structured_outputs": {24: TRADE_SETUP},
        "parsed": {"moat_scores": {}, "price_targets": {}, "recommendation": {}, "trade_setup": TRADE_SETUP},
    }

    markdown = generate_markdown_report(context)

    assert "## 極短線交易計畫" in markdown
    assert "**交易方向:** Long" in markdown
    assert "**嚴格停損:** NT$162" in markdown
    assert "## 🎯 最終投資建議" not in markdown


def test_v4_is_available_in_ui_history_and_report_filenames(tmp_path):
    index_html = (ROOT / "backend" / "static" / "index.html").read_text(encoding="utf-8")
    pipeline_mode_fallback = (ROOT / "backend" / "static" / "pipeline_mode_fallback.js").read_text(encoding="utf-8")
    ui_helpers = (ROOT / "backend" / "static" / "ui_helpers.js").read_text(encoding="utf-8")
    app_js = (ROOT / "backend" / "static" / "app.js").read_text(encoding="utf-8")
    app_pipeline_controls = (ROOT / "backend" / "static" / "app_pipeline_controls.js").read_text(encoding="utf-8")

    assert 'name="pipeline-mode" value="v4"' in index_html
    assert '<option value="v4">模式 D' in index_html
    assert "模式 D：極短線波段與事件驅動" in pipeline_mode_fallback
    assert "開始模式 D 分析" in pipeline_mode_fallback
    assert "pipelineControls.getSelectedPipeline" in app_js
    assert "ui.pipelineCtaLabel(getSelectedPipeline())" in app_pipeline_controls
    assert parse_report_filename("2330_TW_v4_report_20260620_120000.html")["pipeline_id"] == "v4"

    class FakeRepository:
        def __init__(self):
            self.query_arg = None

        def query(self, query):
            self.query_arg = query
            return [], 0

    repository = FakeRepository()
    report_history_service.list_reports(
        page=1,
        limit=10,
        q="",
        pipeline="swing",
        recommendation="all",
        data_trust="all",
        output_dir=str(tmp_path),
        report_cache={},
        repository=repository,
    )

    assert repository.query_arg.pipeline == "v4"


def test_v4_deterministic_fallback_preserves_strict_risk_control():
    context = {
        "pipeline_id": "v4",
        "analyses": {24: "無法解析的模型輸出"},
        "structured_outputs": {},
        "blocking_issues": ["Agent 24 未提供 JSON"],
    }

    ok, _message = _deterministic_structured_fallback(24, {}, context, context["analyses"][24])

    assert ok is True
    assert context["structured_outputs"][24]["trade_direction"] == "Neutral"
    assert context["structured_outputs"][24]["risk_level"] == "High"
    assert "停損" in context["structured_outputs"][24]["stop_loss"]
    assert "N/A" not in context["structured_outputs"][24]["stop_loss"]
