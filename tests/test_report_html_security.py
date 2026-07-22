import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.html_renderer import generate_html_report  # noqa: E402
from reporting.html_sanitizer import sanitize_report_html, sanitize_report_image_url  # noqa: E402
from reporting.utils import clean_markdown, format_debate_text  # noqa: E402


def test_html_sanitizer_uses_maintained_nh3_dependency():
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    sanitizer_source = (ROOT / "backend" / "reporting" / "html_sanitizer.py").read_text(encoding="utf-8")

    assert "nh3" in requirements
    assert "bleach" not in requirements
    assert "import nh3" in sanitizer_source
    assert "import bleach" not in sanitizer_source


def test_markdown_and_debate_html_are_sanitized():
    html = clean_markdown(
        """
正常段落

<script>window.__x = 1</script>

<img src=x onerror=alert(1)>

[惡意連結](javascript:alert(1))
"""
    )
    debate_html = format_debate_text("🐂 陳博士：<img src=x onerror=1> bullish")

    combined = html + debate_html
    assert "<script" not in combined.lower()
    assert "window.__x" not in combined
    assert "onerror" not in combined.lower()
    assert "javascript:" not in combined.lower()


def test_report_html_sanitizer_uses_truthiness_safe_string_conversion():
    class BrokenHtmlTruthiness:
        def __bool__(self):
            raise KeyError("report html truthiness unavailable")

        def __str__(self):
            return "<b>台積電</b><script>alert(1)</script> https://example.com"

    html = sanitize_report_html(BrokenHtmlTruthiness())

    assert "<b>台積電</b>" in html
    assert "alert(1)" not in html
    assert 'href="https://example.com"' in html


def test_rendered_report_uses_mapping_safe_investment_thesis_payload():
    class BrokenTruthinessThesis(dict):
        def __bool__(self):
            raise KeyError("investment thesis truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
        },
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
        "investment_thesis": BrokenTruthinessThesis({
            "pipeline_id": "v1",
            "discipline_heading": "長線投資論文與決策紀律",
            "health_label": "論文健康度",
            "health_score": 6,
            "information_richness": {"grade": "B", "summary": "可用"},
            "mirror_heading": "鏡子測試五句話",
            "mirror_test": {
                "status": "pass",
                "lines": ["預先產生的鏡子測試仍有效"],
            },
            "assumptions_heading": "核心假設",
            "core_assumptions": [
                {"assumption": "預先假設", "validation": "有效驗證", "frequency": "每季"}
            ],
            "red_lines_heading": "紅線",
            "red_lines": [
                {"severity": "警告", "condition": "預先紅線", "action": "重新檢查"}
            ],
            "data_gaps": [],
            "next_review": {"trigger": "下次財報", "focus": "確認假設"},
        }),
    }

    html = generate_html_report(context)

    assert "預先產生的鏡子測試仍有效" in html


def test_rendered_report_escapes_external_and_model_strings():
    context = {
        "ticker": '2330"><img src=x onerror=1>',
        "company_name": "台積電<script>alert(1)</script>",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "sector": "<script>bad()</script>",
            "industry": '<img src=x onerror=1>',
            "current_price": 100,
            "current_price_fmt": '<img src=x onerror=1>',
            "source_audit": [],
        },
        "analyses": {
            1: "## 分析\n<script>alert(1)</script>\n<img src=x onerror=alert(1)>",
            6: "🐂 陳博士：<img src=x onerror=1> 看多",
        },
        "parsed": {
            "price_targets": {'基本情境<img src=x onerror=1>': 120},
            "recommendation": {
                "建議": "持有<script>alert(1)</script>",
                "3個月": '<img src=x onerror=1>',
                "信心": "7/10",
            },
        },
        "report_cover": {"image": "javascript:alert(1)"},
    }

    html = generate_html_report(context)

    assert "alert(1)" not in html
    assert "onerror" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "background-image: url('javascript" not in html.lower()
    assert "台積電" in html


def test_rendered_report_identity_drops_string_empty_tokens():
    context = {
        "ticker": "NaN",
        "company_name": "Infinity",
        "pipeline_id": "v1",
        "data": {
            "ticker": "NaN",
            "company_name": "Infinity",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
        },
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert ">NaN<" not in html
    assert ">Infinity<" not in html
    assert "N/A" in html


def test_rendered_report_meta_drops_string_empty_tokens():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "sector": "NaN",
            "industry": "Infinity",
            "fetch_date": "-Infinity",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
        },
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert "NaN ·" not in html
    assert "· Infinity" not in html
    assert "-Infinity" not in html
    assert "N/A · N/A" in html


def test_rendered_report_synthesis_drops_string_empty_tokens():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
        },
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
        "executive_thesis": "NaN",
        "smoothed_markdown": "Infinity",
    }

    html = generate_html_report(context)

    assert ">NaN<" not in html
    assert ">Infinity<" not in html
    assert "投資核心論點" not in html
    assert "總編輯整合觀點" not in html


def test_rendered_report_runtime_duration_drops_string_empty_tokens():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
        },
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
        "total_time": "Infinity",
    }

    html = generate_html_report(context)

    assert "分析耗時：N/A" in html
    assert "Infinity 秒" not in html


def test_rendered_report_agent_section_drops_string_empty_tokens():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "agent_sequence": [1],
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
        },
        "analyses": {1: "NaN"},
        "parsed": {
            "recommendation": {"建議": "持有", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert ">NaN<" not in html
    assert "分析進行中" in html


def test_rendered_report_embeds_safe_traceability_and_chart_payloads():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "years": ["2025", "2026"],
            "revenue_history": [10, 12],
            "net_income_history": [3, 4],
            "fcf_history": [2, 3],
            "gross_margin_history": [45, 47],
            "op_margin_history": [30, 32],
            "net_margin_history": [20, 21],
            "roe_history": [18, 19],
            "source_audit": [
                {
                    "source": "financial_statements",
                    "provider": "MOPS",
                    "status": "success",
                    "fetched_at": "2026-06-27T01:00:00+00:00",
                    "record_count": 4,
                    "message": "</script><script>alert(1)</script>",
                }
            ],
        },
        "analyses": {
            1: "## 分析\n自由現金流轉換率惡化 [source:financial_statements]",
        },
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$100",
                "6個月": "NT$110",
                "12個月": "NT$120",
                "信心": "7/10",
            },
        },
    }

    html = generate_html_report(context)

    assert 'class="source-citation"' in html
    assert 'data-source-id="financial_statements"' in html
    assert 'id="report-evidence-data" type="application/json"' in html
    assert 'id="report-chart-data" type="application/json"' in html
    assert "window.StockAgentReportTraceability" in html
    assert "JSON.parse(chartPayload.textContent" in html
    assert "alert(1)" not in html
    assert "</script><script>" not in html


def test_rendered_report_treats_mapping_safe_twse_source_audit_as_available():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": (
                MappingProxyType(
                    {
                        "source": "twse_official",
                        "provider": "TWSE/MOPS",
                        "status": "success",
                        "record_count": 1,
                    }
                ),
            ),
        },
        "analyses": {},
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$100",
                "6個月": "NT$110",
                "12個月": "NT$120",
                "信心": "7/10",
            },
        },
    }

    html = generate_html_report(context)

    assert "台股官方財務資料（TWSE/MOPS）本次未取得" not in html


def test_analysis_overlay_display_fields_use_shared_text_safety():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
            "dynamic_peer_metrics": [
                {
                    "name": b"bad-peer-name",
                    "ticker": bytearray(b"bad-peer-ticker"),
                    "gross_margin_pct": "38%",
                    "roe_pct": "24%",
                    "asset_turnover": 0.6,
                    "pe_ttm": 28,
                    "ps_ttm": 4.2,
                },
                {
                    "name": "有效同業",
                    "ticker": "VALID",
                    "gross_margin_pct": 40,
                    "roe_pct": 20,
                },
            ],
        },
        "analyses": {},
        "structured_outputs": {
            20: {
                "guidance_tone": b"bad-management-tone",
                "confidence": 0.82,
                "highlights": [
                    {"keyword": bytearray(b"bad-highlight-keyword"), "quote": "有效管理亮點"}
                ],
            },
            21: {
                "thesis_summary": memoryview(b"bad-downside-summary"),
                "downside_risks": [
                    {
                        "title": b"bad-risk-title",
                        "evidence": "有效下行風險",
                        "impact": memoryview(b"bad-risk-impact"),
                        "severity": bytearray(b"bad-risk-severity"),
                    }
                ],
            },
        },
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert "有效管理亮點" in html
    assert "有效下行風險" in html
    assert "有效同業" in html
    assert "bad-management-tone" not in html
    assert "bad-highlight-keyword" not in html
    assert "bad-downside-summary" not in html
    assert "bad-risk-title" not in html
    assert "bad-risk-impact" not in html
    assert "bad-risk-severity" not in html
    assert "bad-peer-name" not in html
    assert "bad-peer-ticker" not in html


def test_analysis_overlay_display_fields_collapse_embedded_newlines():
    from reporting.analysis_overlays import build_downside_view, build_management_sentiment, build_peer_comparison_rows

    context = {
        "structured_outputs": {
            20: {
                "guidance_tone": "謹慎\n樂觀",
                "highlights": [{"keyword": "需求\n回溫", "quote": "AI 訂單\n恢復成長"}],
            },
            21: {
                "thesis_summary": "估值偏高\n現金流承壓",
                "downside_risks": [
                    {
                        "title": "毛利率\n下滑",
                        "evidence": "報價壓力\n仍高",
                        "impact": "目標價\n下修",
                    }
                ],
            },
        },
    }
    peers = build_peer_comparison_rows({
        "ticker": "2330\nTW",
        "company_name": "台積\n電",
        "dynamic_peer_metrics": [{"name": "同業\n甲", "ticker": "VALID\nA"}],
    })

    management = build_management_sentiment(context)
    downside = build_downside_view(context)

    assert management["tone"] == "謹慎 樂觀"
    assert management["highlights"][0]["keyword"] == "需求 回溫"
    assert management["highlights"][0]["quote"] == "AI 訂單 恢復成長"
    assert downside["summary"] == "估值偏高 現金流承壓"
    assert downside["risks"][0]["title"] == "毛利率 下滑"
    assert downside["risks"][0]["evidence"] == "報價壓力 仍高"
    assert downside["risks"][0]["impact"] == "目標價 下修"
    assert peers[0]["name"] == "台積 電"
    assert peers[0]["ticker"] == "2330 TW"
    assert peers[1]["name"] == "同業 甲"
    assert peers[1]["ticker"] == "VALID A"


def test_analysis_overlay_peer_labels_drop_string_empty_tokens():
    from reporting.analysis_overlays import build_peer_comparison_rows

    rows = build_peer_comparison_rows({
        "ticker": "NaN",
        "company_name": "Infinity",
        "dynamic_peer_metrics": [
            {"name": "N/A", "ticker": "-Infinity"},
            {"name": "有效同業", "ticker": "VALID"},
        ],
    })

    assert rows[0]["name"] == "目標公司"
    assert rows[0]["ticker"] == ""
    assert rows[1]["name"] == "同業"
    assert rows[1]["ticker"] == ""
    assert rows[2]["name"] == "有效同業"
    assert rows[2]["ticker"] == "VALID"
    assert "nan" not in str(rows).lower()
    assert "infinity" not in str(rows).lower()


def test_analysis_overlay_structured_outputs_use_mapping_safe_conversion():
    class BrokenStructuredOutputMap(dict):
        def get(self, key, default=None):
            raise RuntimeError("overlay structured outputs get accessor unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "structured_outputs": BrokenStructuredOutputMap({
            20: {
                "guidance_tone": "積極",
                "confidence": 0.82,
                "highlights": [{"keyword": "展望", "quote": "有效管理層亮點"}],
            },
            21: {
                "thesis_summary": "有效下行摘要",
                "downside_risks": [{"title": "競爭", "evidence": "有效下行風險"}],
            },
        }),
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    try:
        html = generate_html_report(context)
    except RuntimeError as exc:
        raise AssertionError(f"overlay structured-output map accessors should not break HTML rendering: {exc}") from exc

    assert "有效管理層亮點" in html
    assert "有效下行摘要" in html
    assert "有效下行風險" in html


def test_analysis_overlay_list_fields_preserve_rows_when_iterator_lookup_fails():
    class LookupBrokenOverlayIterator:
        def __next__(self):
            raise KeyError("overlay list iterator lookup unavailable")

    class LookupBrokenOverlayList(list):
        def __iter__(self):
            return LookupBrokenOverlayIterator()

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "structured_outputs": {
            20: {
                "guidance_tone": "積極",
                "confidence": 0.82,
                "highlights": LookupBrokenOverlayList([
                    {"keyword": "展望", "quote": "有效管理層亮點"},
                ]),
            },
            21: {
                "thesis_summary": "有效下行摘要",
                "downside_risks": LookupBrokenOverlayList([
                    {"title": "競爭", "evidence": "有效下行風險"},
                ]),
            },
        },
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert "有效管理層亮點" in html
    assert "有效下行風險" in html


def test_next_catalyst_list_fields_preserve_rows_when_iterator_lookup_fails():
    class LookupBrokenCatalystIterator:
        def __next__(self):
            raise KeyError("next catalyst list iterator lookup unavailable")

    class LookupBrokenCatalystList(list):
        def __iter__(self):
            return LookupBrokenCatalystIterator()

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "next_catalysts": LookupBrokenCatalystList([
            {
                "event_name": "法說會更新",
                "expected_timeframe": "下一季",
                "impact_direction": "bullish",
                "trigger_condition": "管理層調升毛利率指引",
            },
        ]),
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert "法說會更新" in html
    assert "管理層調升毛利率指引" in html


def test_tear_sheet_recent_catalysts_preserve_rows_when_truthiness_fails():
    class BrokenTruthinessCatalystList(list):
        def __bool__(self):
            raise KeyError("recent catalyst list truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "recent_catalysts": BrokenTruthinessCatalystList([
                {"title": "有效摘要催化事件"},
            ]),
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert "有效摘要催化事件" in html


def test_analysis_overlay_data_child_maps_use_mapping_safe_conversion():
    class BrokenOverlayDataMap(dict):
        def get(self, key, default=None):
            raise RuntimeError("overlay data child get accessor unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
            "deterministic_financial_tool_results": BrokenOverlayDataMap({
                "calculations": BrokenOverlayDataMap({
                    "dcf_scenarios_default": BrokenOverlayDataMap({
                        "scenarios": BrokenOverlayDataMap({
                            "base": BrokenOverlayDataMap({
                                "price_per_share_twd": 123.45,
                                "wacc_pct": 9.5,
                                "growth_bias_pct": 4.2,
                                "margin_bias_pct": 1.1,
                            })
                        })
                    })
                })
            }),
            "dynamic_peer_metrics": [
                BrokenOverlayDataMap({
                    "name": "有效同業",
                    "ticker": "VALID",
                    "gross_margin_pct": 40,
                    "roe_pct": 20,
                    "pe_ttm": 28,
                    "ps_ttm": 4.2,
                })
            ],
        },
        "analyses": {},
        "structured_outputs": {},
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {},
            "moat_scores": {},
        },
    }

    try:
        html = generate_html_report(context)
    except RuntimeError as exc:
        raise AssertionError(f"overlay data child maps should not break HTML rendering: {exc}") from exc

    assert "DCF 動態情境矩陣" in html
    assert "NT$123.45" in html
    assert "有效同業" in html
    assert "VALID" in html


def test_price_target_values_use_json_safe_display_text():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {
                "熊市情境": b"bad-price-target",
                "基本情境": True,
                "牛市情境": "150",
            },
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    try:
        html = generate_html_report(context)
    except TypeError as exc:
        raise AssertionError(f"price target values should not break report JSON rendering: {exc}") from exc

    assert "NT$150" in html
    assert "bad-price-target" not in html
    assert "→ NT$1</div>" not in html


def test_chart_payload_series_use_json_safe_values():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "years": [b"bad-year", "2026"],
            "revenue_history": [10, memoryview(b"bad-revenue")],
            "net_income_history": [float("nan"), 4],
            "fcf_history": [2, bytearray(b"bad-fcf")],
            "gross_margin_history": [45, b"bad-margin"],
            "op_margin_history": [30, float("inf")],
            "net_margin_history": [20, bytearray(b"bad-net-margin")],
            "roe_history": [18, memoryview(b"bad-roe")],
            "price_history": {
                "dates": ["2026-01-02", b"bad-price-date"],
                "prices": [memoryview(b"bad-price"), 100],
            },
            "pe_river_chart": {
                "source": b"bad-river-source",
                "years": [b"bad-river-year", "2026"],
                "bands": {
                    "15x": [memoryview(b"bad-band"), 120],
                    b"bad-band-label": [80],
                },
                "eps": [bytearray(b"bad-eps"), 8],
            },
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {"品牌影響力": 7, "整體護城河": 8},
        },
    }

    try:
        html = generate_html_report(context)
    except TypeError as exc:
        raise AssertionError(f"chart payload values should not break report JSON rendering: {exc}") from exc

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["years"] == ["", "2026"]
    assert payload["revenue"] == [100, None]
    assert payload["netIncome"] == [None, 40]
    assert payload["grossMargin"] == [45, None]
    assert payload["opMargin"] == [30, None]
    assert payload["priceHistory"] == {"dates": ["2026-01-02"], "prices": [None]}
    assert payload["peRiver"]["years"] == ["", "2026"]
    assert payload["peRiver"]["bands"] == {"15x": [None, 120], "估值通道": [80]}
    assert payload["peRiver"]["eps"] == [None, 8]
    for residue in [
        "bad-year",
        "bad-revenue",
        "bad-price",
        "bad-river-source",
        "bad-band",
        "bad-eps",
    ]:
        assert residue not in html


def test_price_history_chart_payload_accepts_mapping_wrappers():
    class MappingPriceHistory(Mapping):
        def __init__(self, payload):
            self._payload = payload

        def __getitem__(self, key):
            return self._payload[key]

        def __iter__(self):
            return iter(self._payload)

        def __len__(self):
            return len(self._payload)

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "price_history": MappingPriceHistory({
                "dates": ["2026-01-02"],
                "prices": [101],
            }),
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["priceHistory"] == {"dates": ["2026-01-02"], "prices": [101]}


def test_price_history_chart_payload_preserves_series_when_truthiness_fails():
    class BrokenTruthinessPriceSeries(list):
        def __bool__(self):
            raise KeyError("price history series truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "price_history": {
                "dates": BrokenTruthinessPriceSeries(["2026-01-02"]),
                "prices": BrokenTruthinessPriceSeries([101]),
            },
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["priceHistory"] == {"dates": ["2026-01-02"], "prices": [101]}


def test_price_history_chart_payload_skips_unstringable_dates():
    class BrokenDateString:
        def __str__(self):
            raise KeyError("price history date string unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "price_history": {
                "dates": [BrokenDateString(), "2026-01-02"],
                "prices": [999, 101],
            },
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["priceHistory"] == {"dates": ["2026-01-02"], "prices": [101]}


def test_price_history_chart_payload_filters_future_mapping_dates():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "price_history": {
                "2999-01-01": 999,
                "2026-01-02": 101,
            },
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["priceHistory"] == {"2026-01-02": 101}
    assert "2999-01-01" not in html


def test_pe_river_chart_payload_preserves_mapping_when_truthiness_fails():
    class BrokenTruthinessPeRiverChart(dict):
        def __bool__(self):
            raise KeyError("pe river chart truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "pe_river_chart": BrokenTruthinessPeRiverChart({
                "source": "historical_pe",
                "years": ["2025", "2026"],
                "bands": {"15x": [90, 120]},
                "eps": [6, 8],
            }),
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["peRiver"]["years"] == ["2025", "2026"]
    assert payload["peRiver"]["bands"] == {"15x": [90, 120]}
    assert payload["peRiver"]["eps"] == [6, 8]


def test_pe_river_chart_payload_accepts_mapping_wrappers():
    class MappingPeRiverChart(Mapping):
        def __init__(self, payload):
            self._payload = payload

        def __getitem__(self, key):
            return self._payload[key]

        def __iter__(self):
            return iter(self._payload)

        def __len__(self):
            return len(self._payload)

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "pe_river_chart": MappingPeRiverChart({
                "source": "historical_pe",
                "years": ["2025", "2026"],
                "bands": MappingPeRiverChart({"15x": [90, 120]}),
                "eps": [6, 8],
            }),
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["peRiver"]["years"] == ["2025", "2026"]
    assert payload["peRiver"]["bands"] == {"15x": [90, 120]}
    assert payload["peRiver"]["eps"] == [6, 8]


def test_current_price_chart_payload_uses_finite_number_fallback():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": True,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
            "pe_river_chart": {"years": ["2026"], "bands": {"15x": [120]}},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {"牛市情境": 150},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["currentPrice"] is None
    assert "const currentPrice = CHART_DATA.currentPrice;" in html
    assert "const currentPrice = CHART_DATA.currentPrice || 0;" not in html
    assert "const currentPrice = True;" not in html
    assert "(+14900.0%)" not in html

    context["data"]["current_price"] = float("nan")
    html = generate_html_report(context)

    match = re.search(r'<script id="report-chart-data" type="application/json">(.*?)</script>', html)
    assert match
    payload = json.loads(match.group(1))
    assert payload["currentPrice"] is None
    assert "const currentPrice = CHART_DATA.currentPrice;" in html
    assert "const currentPrice = CHART_DATA.currentPrice || 0;" not in html
    assert "const currentPrice = nan;" not in html


def test_recommendation_banner_fields_use_shared_text_safety():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {
                "建議": "持有",
                "3個月": b"bad-target-3m",
                "6個月": bytearray(b"bad-target-6m"),
                "12個月": memoryview(b"bad-target-12m"),
                "信心": True,
            },
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    assert "持有" in html
    for residue in [
        "bad-target-3m",
        "bad-target-6m",
        "bad-target-12m",
        "bytearray(",
        "memory at",
        "信心指數：True",
        "<div class=\"vm-value\">True</div>",
    ]:
        assert residue not in html


def test_editor_synthesis_fields_use_shared_text_safety():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "executive_thesis": b"bad-executive-thesis",
        "smoothed_markdown": bytearray(b"bad-smoothed-markdown"),
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    html = generate_html_report(context)

    for residue in [
        "bad-executive-thesis",
        "bad-smoothed-markdown",
        "bytearray(",
    ]:
        assert residue not in html


def test_report_cover_metadata_uses_mapping_safe_conversion():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "report_cover": b"bad-cover-image",
        "analyses": {},
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
    }

    try:
        html = generate_html_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed report cover metadata should not break HTML rendering: {exc}") from exc

    assert "台積電" in html
    assert "bad-cover-image" not in html


def test_parsed_payload_uses_mapping_safe_conversion():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "parsed": b"bad-parsed-payload",
        "analyses": {},
    }

    try:
        html = generate_html_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed parsed payload should not break HTML rendering: {exc}") from exc

    assert "台積電" in html
    assert "bad-parsed-payload" not in html


def test_parsed_child_maps_use_mapping_safe_conversion():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "parsed": {
            "price_targets": b"bad-price-target-map",
            "recommendation": bytearray(b"bad-recommendation-map"),
            "moat_scores": memoryview(b"bad-moat-score-map"),
            "trade_setup": b"bad-trade-setup-map",
        },
        "analyses": {},
    }

    try:
        html = generate_html_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed parsed child maps should not break HTML rendering: {exc}") from exc

    assert "台積電" in html
    for residue in [
        "bad-price-target-map",
        "bad-recommendation-map",
        "bad-moat-score-map",
        "bad-trade-setup-map",
    ]:
        assert residue not in html


def test_data_payload_uses_mapping_safe_conversion():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": b"bad-data-payload",
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
        "analyses": {},
    }

    try:
        html = generate_html_report(context)
    except (TypeError, ValueError, AttributeError) as exc:
        raise AssertionError(f"malformed data payload should not break HTML rendering: {exc}") from exc

    assert "台積電" in html
    assert "bad-data-payload" not in html


def test_data_child_maps_use_mapping_safe_conversion():
    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
            "institutional_trading": bytearray(b"bad-institutional-map"),
            "pe_river_chart": memoryview(b"bad-pe-river-map"),
        },
        "parsed": {
            "price_targets": {},
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "moat_scores": {},
        },
        "analyses": {},
    }

    try:
        html = generate_html_report(context)
    except AttributeError as exc:
        raise AssertionError(f"malformed data child maps should not break HTML rendering: {exc}") from exc

    assert "台積電" in html
    assert "bad-institutional-map" not in html
    assert "bad-pe-river-map" not in html


def test_report_cover_image_url_allowlist():
    data_url = "data:image/png;base64,QUJDRA=="

    assert sanitize_report_image_url(data_url) == data_url
    assert sanitize_report_image_url("https://example.com/cover.jpg") == "https://example.com/cover.jpg"
    assert sanitize_report_image_url("javascript:alert(1)") == ""


def test_report_cover_image_url_uses_truthiness_safe_string_conversion():
    class BrokenCoverImageTruthiness:
        def __bool__(self):
            raise KeyError("report cover image truthiness unavailable")

        def __str__(self):
            return "https://example.com/cover.jpg"

    assert sanitize_report_image_url(BrokenCoverImageTruthiness()) == "https://example.com/cover.jpg"


def test_taiwan_ticker_autolinks_use_real_quote_pages():
    html = sanitize_report_html("主要競爭對手包括台達電（2308.TW）與 https://example.com")

    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in html
    assert 'href="http://2308.TW"' not in html
    assert 'href="https://example.com"' in html


def test_report_html_sanitizer_does_not_double_escape_entities():
    html = sanitize_report_html("AT&T & 台積電 https://example.com?a=1&b=2")

    assert "AT&amp;T &amp; 台積電" in html
    assert "&amp;amp;" not in html
    assert 'href="https://example.com?a=1&amp;b=2"' in html


def test_report_html_response_includes_security_headers(tmp_path):
    import report_history_service

    filename = "2330_TW_v1_report_20260628_010000.html"
    (tmp_path / filename).write_text("<html><body>report</body></html>", encoding="utf-8")

    response = report_history_service.get_report_file(filename, str(tmp_path))

    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert "script-src 'none'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" not in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
