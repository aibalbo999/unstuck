import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import reporting.legacy_report_gen as report_gen  # noqa: E402
import reporting.evidence_matrix as evidence_matrix  # noqa: E402
from data_trust import build_data_snapshot  # noqa: E402
from reporting import ReportBundle  # noqa: E402
from reporting.audit_trust import (  # noqa: E402
    build_audit_banner_html,
    build_audit_markdown,
    build_data_trust_html,
    build_data_trust_markdown,
    build_source_audit_html,
    build_source_audit_markdown,
)
from reporting.evidence import build_key_evidence_html, build_key_evidence_markdown, build_key_evidence_rows  # noqa: E402
from reporting.evidence_matrix import build_evidence_matrix_payload, build_evidence_matrix_rows  # noqa: E402
from reporting.execution_summary import build_execution_summary_html, build_execution_summary_markdown  # noqa: E402
from reporting.trust_controls import build_trust_controls_html, build_trust_controls_markdown  # noqa: E402


class BrokenExecutionSummaryGateGet(dict):
    def get(self, key, default=None):
        if key in {"status", "verdict", "summary"}:
            raise RuntimeError("execution summary gate get unavailable")
        return dict.get(self, key, default)


def minimal_context():
    data = {
        "data_schema_version": 4,
        "ticker": "2330.TW",
        "company_name": "台積電",
        "sector": "Technology",
        "industry": "Semiconductors",
        "fetch_date": "2026年06月07日",
        "current_price": 100.0,
        "current_price_fmt": "NT$100.00",
        "market_cap_fmt": "NT$100億",
        "pe_ratio": "20.0x",
        "pb_ratio": "5.00x",
        "gross_margin": "50.0%",
        "roe": "20.0%",
        "dividend_yield": "2.00%",
        "beta": "1.00",
        "years": ["2024", "2025"],
        "revenue_history": [10, 12],
        "net_income_history": [2, 3],
        "fcf_history": [1, 2],
        "gross_margin_history": [50, 52],
        "op_margin_history": [30, 31],
        "net_margin_history": [20, 25],
        "roe_history": [18, 20],
        "price_history": {"dates": [], "prices": []},
        "source_freshness": {
            "market_data": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
            "financial_statements": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
        },
        "source_audit": [
            {
                "source": "market_data",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "duration_ms": 12,
                "record_count": 4,
                "cache_hit": False,
                "stale": False,
                "error_kind": "",
                "message": "ok",
            }
        ],
        "data_trust": {
            "status": "fresh",
            "critical_failures": [],
            "stale_sources": [],
            "last_market_data_at": "2026-06-07T00:00:00+00:00",
            "notes": ["測試資料新鮮。"],
        },
    }
    return {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": data,
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$100",
                "6個月": "NT$110",
                "12個月": "NT$120",
                "信心": "7/10",
            },
            "price_targets": {},
            "moat_scores": {},
        },
        "analyses": {},
        "final_audit": {"critical": [], "warnings": [], "corrections": []},
    }


def test_report_bundle_data_trust_accepts_mapping_safe_snapshot():
    bundle = ReportBundle(
        html="",
        markdown="",
        data_snapshot=MappingProxyType(
            {
                "data_trust": MappingProxyType(
                    {
                        "status": "fresh",
                        "reason_codes": ("fresh_core_sources",),
                    }
                )
            }
        ),
    )

    assert bundle.data_trust["status"] == "fresh"
    assert bundle.data_trust["reason_codes"] == ("fresh_core_sources",)


def test_html_and_markdown_include_data_trust_and_source_audit():
    context = minimal_context()
    context["prompt_version"] = "runtime-rules:test"
    context["model_id"] = "gemini-test-model"
    context["code_commit"] = "abc123"
    context["code_dirty"] = True
    context["agent_sequence"] = [1, 2, 3]
    context["final_audit"] = {"status": "passed", "critical": [], "warnings": ["高信心需揭露資料限制"], "corrections": []}
    context["evidence_exit_gate"] = {
        "verdict": "caution",
        "summary": "部分抽樣數字無法對上資料快照，需人工確認。",
        "sampled_count": 3,
        "failed_count": 1,
    }
    context["report_conformance"] = {
        "status": "warning",
        "summary": "報告符合輸出契約，但仍需人工注意警示。",
    }

    html = report_gen.generate_html_report(context)
    markdown = report_gen.generate_markdown_report(context)

    assert "本報告資料可信度" in html
    assert "報告使用範圍與判讀限制" in html
    assert "品質 gate 有警示" in html
    assert "資料信心分數" in html
    assert "可重現資訊" in html
    assert "gemini-test-model" in html
    assert "程式碼狀態：abc123（含未提交變更）" in html
    assert "資料新鮮" in html
    assert "關鍵數據來源對照" in html
    assert "股價與市值" in html
    assert "來源審計" in html
    assert "yfinance" in html
    assert "執行邏輯與模型檢查" in html
    assert "Pipeline V1" in html
    assert "Agent 執行序列" in html
    assert "Final audit：passed" in html
    assert "Evidence gate：caution" in html
    assert "Report conformance：warning" in html
    assert "## 本報告資料可信度" in markdown
    assert "## 報告使用範圍與判讀限制" in markdown
    assert "品質 gate 有警示" in markdown
    assert "**資料信心分數:**" in markdown
    assert "**可重現資訊:**" in markdown
    assert "runtime-rules:test" in markdown
    assert "程式碼狀態：abc123（含未提交變更）" in markdown
    assert "## 關鍵數據來源對照" in markdown
    assert "## 來源審計" in markdown
    assert "## 執行邏輯與模型檢查" in markdown
    assert "**Pipeline:** V1" in markdown
    assert "**Agent 執行序列:** Agent 1 → Agent 2 → Agent 3" in markdown
    assert "**Final audit:** passed" in markdown
    assert "**Evidence gate:** caution" in markdown
    assert "**Report conformance:** warning" in markdown
    assert "| 股價與市值 | 市場資料 | yfinance | 成功 |" in markdown
    assert "| 市場資料 | yfinance | 成功 |" in markdown


def test_execution_summary_keeps_quality_gate_mappings_when_accessor_fails():
    context = minimal_context()
    context["final_audit"] = BrokenExecutionSummaryGateGet({"status": "warning"})
    context["evidence_exit_gate"] = BrokenExecutionSummaryGateGet({
        "verdict": "caution",
        "summary": "部分抽樣數字需人工確認。",
    })
    context["report_conformance"] = BrokenExecutionSummaryGateGet({
        "status": "warning",
        "summary": "報告符合主要輸出契約，但仍需人工注意警示。",
    })
    context["report_lint"] = BrokenExecutionSummaryGateGet({"status": "warning"})

    markdown = build_execution_summary_markdown(context)
    html = build_execution_summary_html(context)

    assert "**Final audit:** warning" in markdown
    assert "**Evidence gate:** caution" in markdown
    assert "**Report conformance:** warning" in markdown
    assert "**Report lint:** warning" in markdown
    assert "部分抽樣數字需人工確認。" in markdown
    assert "報告符合主要輸出契約" in markdown
    assert "Final audit：warning" in html
    assert "Evidence gate：caution" in html
    assert "Report conformance：warning" in html
    assert "Report lint：warning" in html
    assert "部分抽樣數字需人工確認。" in html


def test_execution_summary_accepts_mapping_safe_quality_gate_child_maps():
    context = minimal_context()
    context["data"] = MappingProxyType(context["data"])
    context["final_audit"] = MappingProxyType({"status": "warning"})
    context["evidence_exit_gate"] = MappingProxyType(
        {
            "verdict": "caution",
            "summary": "部分抽樣數字需人工確認。",
        }
    )
    context["report_conformance"] = MappingProxyType(
        {
            "status": "warning",
            "summary": "報告符合主要輸出契約，但仍需人工注意警示。",
        }
    )
    context["report_lint"] = MappingProxyType({"status": "warning"})

    markdown = build_execution_summary_markdown(context)
    html = build_execution_summary_html(context)

    assert "**資料可信度:** 資料新鮮（fresh）" in markdown
    assert "**Final audit:** warning" in markdown
    assert "**Evidence gate:** caution" in markdown
    assert "**Report conformance:** warning" in markdown
    assert "**Report lint:** warning" in markdown
    assert "部分抽樣數字需人工確認。" in markdown
    assert "報告符合主要輸出契約" in markdown
    assert "資料可信度：資料新鮮（fresh）" in html
    assert "Final audit：warning" in html
    assert "Evidence gate：caution" in html
    assert "Report conformance：warning" in html
    assert "Report lint：warning" in html
    assert "部分抽樣數字需人工確認。" in html


def test_execution_summary_uses_shared_text_safety_for_quality_gate_text_fields():
    context = minimal_context()
    context["final_audit"] = {"status": b"bad-final-status"}
    context["evidence_exit_gate"] = {
        "verdict": bytearray(b"bad-evidence-verdict"),
        "summary": memoryview(b"bad-evidence-summary"),
    }
    context["report_conformance"] = {
        "status": "warning",
        "summary": b"bad-conformance-summary",
    }

    markdown = build_execution_summary_markdown(context)
    html = build_execution_summary_html(context)
    rendered = markdown + html

    assert "**Final audit:** not_recorded" in markdown
    assert "**Evidence gate:** not_recorded" in markdown
    assert "Report conformance：warning" in html
    assert "bad-final-status" not in rendered
    assert "bad-evidence-verdict" not in rendered
    assert "bad-evidence-summary" not in rendered
    assert "bad-conformance-summary" not in rendered


def test_execution_summary_markdown_collapses_embedded_newlines_in_text_fields():
    context = minimal_context()
    context["final_audit"] = {"status": "passed\nwith warnings"}
    context["evidence_exit_gate"] = {
        "verdict": "caution\nmanual check",
        "summary": "抽樣數字\n需人工確認。",
    }
    context["report_conformance"] = {
        "status": "warning\nminor",
        "summary": "輸出契約\n仍可接受。",
    }
    context["report_lint"] = {"status": "clean\nreviewed"}
    context["prompt_version"] = "runtime-rules\nv2"
    context["model_id"] = "gemini\n2.5"

    markdown = build_execution_summary_markdown(context, model_routes="primary\nbackup")

    assert "- **模型路由:** primary backup" in markdown
    assert "- **Final audit:** passed with warnings" in markdown
    assert "- **Evidence gate:** caution manual check" in markdown
    assert "- **Report conformance:** warning minor" in markdown
    assert "- **Report lint:** clean reviewed" in markdown
    assert "- **Prompt / Model:** runtime-rules v2 / gemini 2.5" in markdown
    assert "- **證據抽查摘要:** 抽樣數字 需人工確認。" in markdown
    assert "- **符合性摘要:** 輸出契約 仍可接受。" in markdown
    assert "passed\nwith warnings" not in markdown
    assert "primary\nbackup" not in markdown
    assert "runtime-rules\nv2" not in markdown


def test_audit_banner_sections_use_shared_text_safety_for_abnormality_text():
    context = minimal_context()
    context["final_audit"] = {
        "critical": [b"bad-critical", "有效異常提醒。"],
        "warnings": [bytearray(b"bad-warning")],
        "corrections": [memoryview(b"bad-correction")],
    }
    context["blocking_issues"] = [bytearray(b"bad-blocking"), "有效阻斷提醒。"]
    context["audit_repair_log"] = [b"bad-repair", "有效修復紀錄。"]

    html = build_audit_banner_html(context)
    markdown = build_audit_markdown(context)
    rendered = html + markdown

    assert "有效異常提醒。" in rendered
    assert "有效阻斷提醒。" in rendered
    assert "有效修復紀錄。" in rendered
    assert "bad-critical" not in rendered
    assert "bad-warning" not in rendered
    assert "bad-correction" not in rendered
    assert "bad-blocking" not in rendered
    assert "bad-repair" not in rendered


def test_audit_markdown_collapses_embedded_newlines_in_abnormality_bullets():
    context = minimal_context()
    context["final_audit"] = {
        "critical": ["有效異常\n提醒。"],
        "warnings": ["有效非阻斷\n提醒。"],
        "corrections": ["有效校正\n紀錄。"],
    }
    context["blocking_issues"] = ["有效阻斷\n提醒。"]
    context["audit_repair_log"] = ["有效修復\n紀錄。"]

    lines = build_audit_markdown(context).splitlines()

    assert "- 有效異常 提醒。" in lines
    assert "- 有效阻斷 提醒。" in lines
    assert "- 有效修復 紀錄。" in lines
    assert "- 有效校正 紀錄。" in lines
    assert "- 有效非阻斷 提醒。" in lines
    assert all(not line.startswith(("提醒。", "紀錄。")) for line in lines)


def test_audit_banner_sections_do_not_depend_on_list_truthiness():
    class BrokenAuditListTruthiness(list):
        def __bool__(self):
            raise KeyError("audit list truthiness unavailable")

    context = minimal_context()
    context["final_audit"] = {
        "critical": BrokenAuditListTruthiness(["有效異常提醒。"]),
        "warnings": BrokenAuditListTruthiness(["有效非阻斷提醒。"]),
        "corrections": BrokenAuditListTruthiness(["有效校正紀錄。"]),
    }
    context["blocking_issues"] = BrokenAuditListTruthiness(["有效阻斷提醒。"])
    context["audit_repair_log"] = BrokenAuditListTruthiness(["有效修復紀錄。"])

    try:
        html = build_audit_banner_html(context)
        markdown = build_audit_markdown(context)
    except KeyError as exc:
        raise AssertionError(f"audit banner list fields should be truthiness-safe: {exc}") from exc

    rendered = html + markdown

    assert "有效異常提醒。" in rendered
    assert "有效阻斷提醒。" in rendered
    assert "有效修復紀錄。" in rendered
    assert "有效校正紀錄。" in rendered
    assert "有效非阻斷提醒。" in rendered


def test_audit_banner_sections_normalize_final_audit_child_maps_before_field_access():
    class BrokenFinalAuditGet(dict):
        def get(self, key, default=None):
            raise RuntimeError("final audit get unavailable")

    context = minimal_context()
    context["final_audit"] = BrokenFinalAuditGet({
        "critical": ["有效異常提醒。"],
        "warnings": ["有效非阻斷提醒。"],
        "corrections": ["有效校正紀錄。"],
    })

    try:
        html = build_audit_banner_html(context)
        markdown = build_audit_markdown(context)
    except RuntimeError as exc:
        raise AssertionError(f"final_audit child maps should not break audit banner sections: {exc}") from exc

    rendered = html + markdown

    assert "有效異常提醒。" in rendered
    assert "有效非阻斷提醒。" in rendered
    assert "有效校正紀錄。" in rendered


def test_audit_banner_sections_ignore_malformed_scalar_abnormality_lists():
    context = minimal_context()
    context["final_audit"] = {
        "critical": b"bad-critical",
        "warnings": bytearray(b"bad-warning"),
        "corrections": memoryview(b"bad-correction"),
    }
    context["blocking_issues"] = bytearray(b"bad-blocking")
    context["audit_repair_log"] = b"bad-repair"

    rendered = build_audit_banner_html(context) + build_audit_markdown(context)

    assert "bad-critical" not in rendered
    assert "bad-warning" not in rendered
    assert "bad-correction" not in rendered
    assert "bad-blocking" not in rendered
    assert "bad-repair" not in rendered
    assert ">98<" not in rendered
    assert "- 98" not in rendered


def test_key_evidence_prefers_successful_provider_over_later_empty_provider():
    data = minimal_context()["data"]
    data["recent_catalysts"] = [{"title": "Alternative catalyst"}]
    data["source_audit"] = [
        {
            "source": "recent_catalysts",
            "provider": "Alternative Search",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
        },
        {
            "source": "recent_catalysts",
            "provider": "FMP news",
            "status": "unavailable",
            "fetched_at": "2026-06-07T00:00:01+00:00",
            "record_count": 0,
            "cache_hit": False,
            "stale": False,
        },
    ]

    rows = build_key_evidence_rows(data)
    catalyst_row = next(row for row in rows if row["label"] == "近期催化劑")

    assert catalyst_row["status"] == "success"
    assert catalyst_row["provider"] == "Alternative Search"
    assert catalyst_row["record_count"] == 1


def test_key_evidence_rows_use_shared_text_safety_for_report_source_fields():
    data = minimal_context()["data"]
    data["source_audit"] = [
        {
            "source": "market_data",
            "provider": b"bad-provider",
            "status": "success",
            "fetched_at": memoryview(b"bad-time"),
            "record_count": 1,
            "stale": False,
        }
    ]

    rows = build_key_evidence_rows(data)
    html = build_key_evidence_html(data)
    markdown = "\n".join(build_key_evidence_markdown(data))
    market_row = next(row for row in rows if row["label"] == "股價與市值")

    assert market_row["provider"] == "未記錄"
    assert market_row["fetched_at"] == "N/A"
    assert "bad-provider" not in html
    assert "bad-provider" not in markdown


def test_key_evidence_rows_normalize_source_audit_child_maps_before_field_access():
    class BrokenKeyEvidenceAuditRowGet(dict):
        def get(self, key, default=None):
            raise RuntimeError("key evidence audit row get unavailable")

    data = minimal_context()["data"]
    data["source_audit"] = [
        BrokenKeyEvidenceAuditRowGet({
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "record_count": 4,
            "stale": False,
        })
    ]

    try:
        rows = build_key_evidence_rows(data)
    except RuntimeError as exc:
        raise AssertionError(f"source audit child maps should not break key evidence rows: {exc}") from exc

    market_row = next(row for row in rows if row["label"] == "股價與市值")

    assert market_row["provider"] == "yfinance"
    assert market_row["status"] == "success"
    assert market_row["record_count"] == 4


def test_key_evidence_rows_use_safe_bool_for_aggregated_stale_flags():
    class BrokenKeyEvidenceStaleBool:
        def __bool__(self):
            raise KeyError("key evidence stale lookup unavailable")

    data = minimal_context()["data"]
    data["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "record_count": 4,
            "stale": BrokenKeyEvidenceStaleBool(),
        }
    ]

    rows = build_key_evidence_rows(data)
    html = build_key_evidence_html(data)
    markdown = "\n".join(build_key_evidence_markdown(data))
    market_row = next(row for row in rows if row["label"] == "股價與市值")

    assert market_row["stale"] is False
    assert market_row["record_count"] == 4
    assert "<td>否</td>" in html
    assert "| 股價與市值 | 市場資料 | yfinance | 成功 | 2026-06-07T00:00:00+00:00 | 4 | 否 |" in markdown


def test_key_evidence_rows_ignore_malformed_scalar_data_values():
    data = minimal_context()["data"]
    data["current_price"] = True
    data["market_cap_raw"] = memoryview(b"bad-market-cap")
    data["market_cap_fmt"] = b"bad-market-cap-fmt"

    rows = build_key_evidence_rows(data)

    assert all(row["label"] != "股價與市值" for row in rows)


def test_key_evidence_rows_use_strip_safe_string_data_values():
    class BrokenKeyEvidenceDataStrip(str):
        def strip(self, chars=None):
            raise KeyError("key evidence data strip unavailable")

    data = minimal_context()["data"]
    data["current_price"] = BrokenKeyEvidenceDataStrip("100")

    try:
        rows = build_key_evidence_rows(data)
    except KeyError as exc:
        raise AssertionError(f"malformed data string strip should not break key evidence rows: {exc}") from exc

    market_row = next(row for row in rows if row["label"] == "股價與市值")

    assert market_row["provider"] == "yfinance"
    assert market_row["status"] == "success"


def test_key_evidence_markdown_cells_escape_table_separators():
    data = minimal_context()["data"]
    data["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yf|finance\nTW",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00|local\nbatch",
            "record_count": 4,
            "stale": False,
        }
    ]

    markdown = "\n".join(build_key_evidence_markdown(data))

    assert "yf/finance TW" in markdown
    assert "2026-06-07T00:00:00+00:00/local batch" in markdown
    assert "yf|finance" not in markdown
    assert "local\nbatch" not in markdown


def test_source_audit_report_sections_use_shared_text_safety_for_audit_fields():
    data = minimal_context()["data"]
    data["source_audit"] = [
        {
            "source": "market_data",
            "provider": b"bad-provider",
            "status": bytearray(b"bad-status"),
            "fetched_at": memoryview(b"bad-time"),
            "duration_ms": 12,
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
            "message": bytearray(b"bad-message"),
        }
    ]

    html = build_source_audit_html(data)
    markdown = build_source_audit_markdown(data)
    rendered = html + markdown

    assert "來源審計" in rendered
    assert "未記錄" in rendered
    assert "bad-provider" not in rendered
    assert "bad-status" not in rendered
    assert "bad-time" not in rendered
    assert "bad-message" not in rendered


def test_source_audit_markdown_cells_escape_table_separators():
    data = minimal_context()["data"]
    data["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yf|finance\nTW",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00|local\nbatch",
            "duration_ms": 12,
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
            "message": "ok|done\nline",
        }
    ]

    markdown = build_source_audit_markdown(data)

    assert "yf/finance TW" in markdown
    assert "2026-06-07T00:00:00+00:00/local batch" in markdown
    assert "ok/done line" in markdown
    assert "yf|finance" not in markdown
    assert "local\nbatch" not in markdown
    assert "ok|done" not in markdown


def test_source_audit_report_sections_normalize_audit_child_maps_before_field_access():
    class BrokenSourceAuditRowGet(dict):
        def get(self, key, default=None):
            raise RuntimeError("source audit row get unavailable")

    data = minimal_context()["data"]
    data["source_audit"] = [
        BrokenSourceAuditRowGet({
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "duration_ms": 12,
            "record_count": 4,
            "cache_hit": False,
            "stale": False,
            "message": "ok",
        })
    ]

    try:
        html = build_source_audit_html(data)
        markdown = build_source_audit_markdown(data)
    except RuntimeError as exc:
        raise AssertionError(f"source audit child maps should not break report source audit sections: {exc}") from exc

    rendered = html + markdown

    assert "來源審計" in rendered
    assert "yfinance" in rendered
    assert "2026-06-07T00:00:00+00:00" in rendered
    assert "ok" in rendered


def test_source_audit_report_sections_use_safe_numeric_and_boolean_display_for_audit_fields():
    data = minimal_context()["data"]
    data["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "duration_ms": b"bad-duration",
            "record_count": bytearray(b"bad-count"),
            "cache_hit": memoryview(b"bad-cache"),
            "stale": b"bad-stale",
            "message": "ok",
        }
    ]

    html = build_source_audit_html(data)
    markdown = build_source_audit_markdown(data)
    rendered = html + markdown

    assert "bad-duration" not in rendered
    assert "bad-count" not in rendered
    assert "bad-cache" not in rendered
    assert "bad-stale" not in rendered
    assert "| 市場資料 | yfinance | 成功 | 2026-06-07T00:00:00+00:00 | N/A | 0 | 否 | 否 | ok |" in markdown


def test_data_trust_report_sections_use_shared_text_safety_for_trust_notes_and_metadata():
    data = minimal_context()["data"]
    data["data_trust"] = {
        "status": "fresh",
        "notes": [b"bad-note", bytearray(b"bad-note"), "有效資料可信度說明。"],
        "last_market_data_at": memoryview(b"bad-market-time"),
        "critical_failures": [],
        "stale_sources": [],
        "reason_codes": [],
    }
    data["quant_metrics"] = {
        "fallback_fields": [b"bad-field", "valid_field"],
        "data_quality_warning": bytearray(b"bad-warning"),
    }

    html = build_data_trust_html(data)
    markdown = build_data_trust_markdown(data)
    rendered = html + markdown

    assert "有效資料可信度說明。" in rendered
    assert "量化模型警示" in rendered
    assert "valid_field" in rendered
    assert "bad-note" not in rendered
    assert "bad-market-time" not in rendered
    assert "bad-field" not in rendered
    assert "bad-warning" not in rendered


def test_data_trust_markdown_collapses_embedded_newlines_in_summary_bullets():
    data = minimal_context()["data"]
    data["data_trust"] = {
        "status": "fresh",
        "notes": ["主要資料\n已更新", "量化假設\n需留意"],
        "last_market_data_at": "2026-06-07T00:00:00\n+00:00",
        "critical_failures": [],
        "stale_sources": [],
        "reason_codes": ["source_error:market_data\nmanual"],
    }
    data["quant_metrics"] = {
        "fallback_fields": ["wacc\nfield", "terminal_growth"],
        "data_quality_warning": "DCF 欄位\n使用預設假設。",
    }

    lines = build_data_trust_markdown(data).splitlines()

    assert "- **市場資料時間:** 2026-06-07T00:00:00 +00:00" in lines
    assert "- **原因:** 來源異常：market_data manual" in lines
    assert "- **摘要:** 主要資料 已更新；量化假設 需留意" in lines
    assert "- **⚠️ 量化模型警示:** DCF 欄位 使用預設假設。" in lines
    assert all(
        not line.startswith(("+00:00", "已更新", "需留意", "manual", "使用預設假設。"))
        for line in lines
    )


def test_data_trust_report_sections_do_not_depend_on_fallback_field_truthiness():
    class BrokenFallbackFieldsTruthiness(list):
        def __bool__(self):
            raise KeyError("fallback field truthiness unavailable")

    data = minimal_context()["data"]
    data["quant_metrics"] = {
        "fallback_fields": BrokenFallbackFieldsTruthiness(["wacc", "terminal_growth"]),
    }

    try:
        html = build_data_trust_html(data)
        markdown = build_data_trust_markdown(data)
    except KeyError as exc:
        raise AssertionError(f"quant fallback fields should be truthiness-safe: {exc}") from exc

    rendered = html + markdown

    assert "量化模型警示" in rendered
    assert "wacc" in rendered
    assert "terminal_growth" in rendered


def test_data_trust_report_sections_normalize_quant_metrics_child_maps_before_field_access():
    class BrokenQuantMetricsGet(dict):
        def get(self, key, default=None):
            raise RuntimeError("quant metrics get unavailable")

    data = minimal_context()["data"]
    data["quant_metrics"] = BrokenQuantMetricsGet({
        "fallback_fields": ["wacc", "terminal_growth"],
        "data_quality_warning": "DCF 欄位使用預設假設。",
    })

    try:
        html = build_data_trust_html(data)
        markdown = build_data_trust_markdown(data)
    except RuntimeError as exc:
        raise AssertionError(f"quant_metrics child maps should not break data trust sections: {exc}") from exc

    rendered = html + markdown

    assert "量化模型警示" in rendered
    assert "DCF 欄位使用預設假設。" in rendered


def test_trust_controls_normalize_data_maps_before_data_trust_access():
    class BrokenTrustDataGet(dict):
        def get(self, key, default=None):
            if key == "data_trust":
                raise RuntimeError("data trust get unavailable")
            return dict.get(self, key, default)

    context = minimal_context()
    data = BrokenTrustDataGet(context["data"])
    data["data_trust"]["score"] = 88
    context["data"] = data
    context["model_id"] = "gemini-test-model"
    context["code_commit"] = "abc123"

    try:
        html = build_trust_controls_html(data, context)
        markdown = "\n".join(build_trust_controls_markdown(data, context))
    except RuntimeError as exc:
        raise AssertionError(f"data map accessors should not break trust controls: {exc}") from exc

    rendered = html + markdown

    assert "資料信心分數：88/100" in html
    assert "**資料信心分數:** 88/100" in markdown
    assert "gemini-test-model" in rendered
    assert "yfinance" in rendered


def test_trust_controls_do_not_depend_on_generated_at_truthiness():
    class BrokenGeneratedAtTruthiness:
        def __bool__(self):
            raise KeyError("generated_at truthiness unavailable")

        def __str__(self):
            return "2026-06-07T00:00:00+00:00"

    context = minimal_context()
    context["generated_at"] = BrokenGeneratedAtTruthiness()
    context["model_id"] = "gemini-test-model"
    context["code_commit"] = "abc123"

    try:
        html = build_trust_controls_html(context["data"], context)
        markdown = "\n".join(build_trust_controls_markdown(context["data"], context))
    except KeyError as exc:
        raise AssertionError(f"trust controls generated_at should be truthiness-safe: {exc}") from exc

    rendered = html + markdown

    assert "資料信心分數" in rendered
    assert "gemini-test-model" in rendered
    assert "abc123" in rendered


def test_trust_controls_markdown_collapses_embedded_newlines_in_reproducibility_fields():
    context = minimal_context()
    context["generated_at"] = "2026-06-07T00:00:00\n+00:00"
    context["model_id"] = "gemini\n2.5"
    context["prompt_version"] = "runtime\nv2"
    context["code_commit"] = "abcdef\n123456"
    context["data"]["data_trust"]["last_market_data_at"] = "2026-06-07T00:00:00\n+00:00"
    context["data"]["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance\nprimary",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00\n+00:00",
        }
    ]

    markdown_lines = build_trust_controls_markdown(context["data"], context)
    reproducibility_line = markdown_lines[2]

    assert reproducibility_line.startswith("- **可重現資訊:**")
    assert "Model gemini 2.5" in reproducibility_line
    assert "Prompt 版本 runtime v2" in reproducibility_line
    assert "程式碼狀態：abcdef 12345" in reproducibility_line
    assert "Provider yfinance primary" in reproducibility_line
    assert "資料時間 2026-06-07T00:00:00 +00:00" in reproducibility_line
    assert "\n" not in reproducibility_line


def test_key_evidence_includes_global_market_and_international_news_context():
    data = minimal_context()["data"]
    data["global_market_context"] = {
        "items": [{"symbol": "QQQ", "change_5d_pct": 2.4, "source": "yfinance"}],
    }
    data["international_news_context"] = {
        "topics": [{"tag": "macro", "headline": "Fed path drives risk appetite", "source": "GDELT"}],
    }
    data["source_audit"].extend([
        {
            "source": "global_market_context",
            "provider": "yfinance global context",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
        },
        {
            "source": "international_news_context",
            "provider": "GDELT",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:01+00:00",
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
        },
    ])

    rows = build_key_evidence_rows(data)

    assert any(row["label"] == "全球市場脈絡" and row["provider"] == "yfinance global context" for row in rows)
    assert any(row["label"] == "國際新聞脈絡" and row["provider"] == "GDELT" for row in rows)


def test_report_artifacts_include_evidence_matrix_for_key_conclusions():
    context = minimal_context()
    context["parsed"]["price_targets"] = {
        "熊市情境": 80,
        "基本情境": 100,
        "牛市情境": 120,
    }
    context["parsed"]["moat_scores"] = {
        "品牌力": 8,
        "規模經濟": 9,
        "轉換成本": 7,
        "整體護城河": 8,
    }
    context["data"]["global_market_context"] = {"items": [{"symbol": "QQQ", "change_5d_pct": 2.4}]}
    context["data"]["international_news_context"] = {"topics": [{"tag": "macro", "headline": "Fed path"}]}
    context["data"]["source_audit"].extend([
        {"source": "global_market_context", "provider": "yfinance global context", "status": "success", "record_count": 1, "stale": False},
        {"source": "international_news_context", "provider": "GDELT", "status": "success", "record_count": 1, "stale": False},
    ])
    context["data"]["data_source_notes"] = ["TTM 淨利率已依最新財報補值。"]

    html = report_gen.generate_html_report(context)
    markdown = report_gen.generate_markdown_report(context)
    snapshot = build_data_snapshot(context, pipeline_id="v1")

    assert "報告證據矩陣" in html
    assert "估值結論" in html
    assert "TTM 淨利率已依最新財報補值。" in html
    assert "## 報告證據矩陣" in markdown
    assert "| 估值結論 |" in markdown
    assert "| 最終投資建議 |" in markdown
    assert snapshot["evidence_matrix"][0]["claim"] == "估值結論"
    assert any(row["claim"] == "最終投資建議" for row in snapshot["evidence_matrix"])
    assert any(
        row["claim"] == "最終投資建議" and "全球市場脈絡" in row["source"] and "國際新聞脈絡" in row["source"]
        for row in snapshot["evidence_matrix"]
    )
    assert any("TTM 淨利率已依最新財報補值。" in row["limitation"] for row in snapshot["evidence_matrix"])


def test_evidence_matrix_price_target_basis_skips_boolean_targets():
    context = minimal_context()
    context["parsed"]["price_targets"] = {
        "基本情境": True,
        "牛市情境": 120,
    }

    rows = build_evidence_matrix_rows(context)
    valuation_row = next(row for row in rows if row["claim"] == "估值結論")

    assert "牛市情境: NT$120" in valuation_row["basis"]
    assert "基本情境: NT$1" not in valuation_row["basis"]
    assert "基本情境: N/A" in valuation_row["basis"]


def test_evidence_matrix_price_target_basis_skips_non_finite_targets():
    context = minimal_context()
    context["parsed"]["price_targets"] = {
        "基本情境": float("nan"),
        "壓力情境": float("-inf"),
        "牛市情境": 120,
    }

    rows = build_evidence_matrix_rows(context)
    valuation_row = next(row for row in rows if row["claim"] == "估值結論")

    assert "牛市情境: NT$120" in valuation_row["basis"]
    assert "基本情境: NT$nan" not in valuation_row["basis"]
    assert "壓力情境: NT$-inf" not in valuation_row["basis"]
    assert "基本情境: N/A" in valuation_row["basis"]
    assert "壓力情境: N/A" in valuation_row["basis"]


def test_evidence_matrix_price_target_basis_skips_malformed_scenario_keys():
    context = minimal_context()
    context["parsed"]["price_targets"] = {
        memoryview(b"bad-scenario"): 120,
        "牛市情境": 150,
    }

    rows = build_evidence_matrix_rows(context)
    valuation_row = next(row for row in rows if row["claim"] == "估值結論")

    assert "牛市情境: NT$150" in valuation_row["basis"]
    assert "N/A: NT$120" not in valuation_row["basis"]
    assert "bad-scenario" not in valuation_row["basis"]


def test_evidence_matrix_recommendation_basis_uses_safe_key_text():
    class BrokenRecommendationKey:
        def __str__(self):
            raise KeyError("recommendation key text unavailable")

    context = minimal_context()
    context["parsed"]["recommendation"] = {
        BrokenRecommendationKey(): "不應中斷",
        "建議": "持有",
        "信心": "7/10",
    }

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed recommendation keys should not break evidence matrix: {exc}") from exc

    recommendation_row = next(row for row in rows if row["claim"] == "最終投資建議")
    assert "建議: 持有" in recommendation_row["basis"]
    assert "信心: 7/10" in recommendation_row["basis"]


def test_evidence_matrix_recommendation_basis_uses_truthiness_safe_values():
    class BrokenRecommendationValueEquality:
        def __eq__(self, other):
            raise KeyError("recommendation value equality unavailable")

        def __str__(self):
            return "持有"

    context = minimal_context()
    context["parsed"]["recommendation"] = {
        "建議": BrokenRecommendationValueEquality(),
        "信心": "7/10",
    }

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed recommendation values should not break evidence matrix: {exc}") from exc

    recommendation_row = next(row for row in rows if row["claim"] == "最終投資建議")
    assert "建議: 持有" in recommendation_row["basis"]
    assert "信心: 7/10" in recommendation_row["basis"]


def test_evidence_matrix_recommendation_basis_uses_strip_safe_string_values():
    class BrokenRecommendationValueStrip(str):
        def strip(self, chars=None):
            raise KeyError("recommendation value strip unavailable")

    context = minimal_context()
    context["parsed"]["recommendation"] = {
        "建議": BrokenRecommendationValueStrip("持有"),
        "信心": "7/10",
    }

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed recommendation string values should not break evidence matrix: {exc}") from exc

    recommendation_row = next(row for row in rows if row["claim"] == "最終投資建議")
    assert "建議: 持有" in recommendation_row["basis"]
    assert "信心: 7/10" in recommendation_row["basis"]


def test_evidence_matrix_moat_basis_skips_malformed_metric_keys():
    context = minimal_context()
    context["parsed"]["moat_scores"] = {
        memoryview(b"bad-moat-key"): 8,
        "整體護城河": 7,
        "轉換成本": 6,
    }

    rows = build_evidence_matrix_rows(context)
    moat_row = next(row for row in rows if row["claim"] == "護城河評分")

    assert "整體護城河: 7/10" in moat_row["basis"]
    assert "轉換成本: 6/10" in moat_row["basis"]
    assert "N/A: 8/10" not in moat_row["basis"]
    assert "bad-moat-key" not in moat_row["basis"]


def test_evidence_matrix_payload_uses_shared_text_safety_for_source_audit_fields():
    context = minimal_context()
    context["data"]["source_audit"] = [
        {
            "source": "market_data",
            "provider": b"bad-provider",
            "status": "success",
            "fetched_at": memoryview(b"bad-time"),
            "message": bytearray(b"bad-message"),
            "record_count": 1,
            "stale": False,
        }
    ]

    payload = build_evidence_matrix_payload(context)
    source_payload = payload["sources"]["market_data"]

    assert source_payload["source_document"] == "N/A"
    assert source_payload["fetched_at"] == "N/A"
    assert source_payload["text"] == "N/A"
    assert "bad-provider" not in str(payload)
    assert "bad-time" not in str(payload)
    assert "bad-message" not in str(payload)


def test_evidence_matrix_payload_message_fallback_skips_text_empty_malformed_values():
    context = minimal_context()
    context["data"]["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "error",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "message": memoryview(b"bad-message"),
            "error_kind": "provider_timeout",
            "record_count": 0,
            "stale": False,
        }
    ]

    payload = build_evidence_matrix_payload(context)
    source_payload = payload["sources"]["market_data"]

    assert source_payload["text"] == "provider_timeout"
    assert "bad-message" not in str(payload)


def test_evidence_matrix_payload_message_presence_uses_length_safe_fallback():
    class BrokenEvidenceMatrixMessageLength(list):
        def __len__(self):
            raise KeyError("evidence matrix message length unavailable")

    context = minimal_context()
    context["data"]["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "error",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "message": BrokenEvidenceMatrixMessageLength(["bad-message"]),
            "error_kind": "provider_timeout",
            "record_count": 0,
            "stale": False,
        }
    ]

    try:
        payload = build_evidence_matrix_payload(context)
    except KeyError as exc:
        raise AssertionError(f"malformed message length should not break evidence matrix payload: {exc}") from exc

    source_payload = payload["sources"]["market_data"]

    assert source_payload["text"] == "provider_timeout"
    assert "bad-message" not in str(payload)


def test_evidence_matrix_payload_message_presence_uses_strip_safe_string_values():
    class BrokenEvidenceMatrixMessageStrip(str):
        def strip(self, chars=None):
            raise KeyError("evidence matrix message strip unavailable")

    context = minimal_context()
    context["data"]["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "message": BrokenEvidenceMatrixMessageStrip("有效來源訊息"),
            "error_kind": "fallback_should_not_override_present_message",
            "record_count": 1,
            "stale": False,
        }
    ]

    try:
        payload = build_evidence_matrix_payload(context)
    except KeyError as exc:
        raise AssertionError(
            f"malformed message string strip should not break evidence matrix payload: {exc}"
        ) from exc

    source_payload = payload["sources"]["market_data"]

    assert source_payload["text"] == "有效來源訊息"


def test_evidence_matrix_payload_uses_truthiness_safe_message_selection():
    class BrokenEvidenceMatrixMessageTruth:
        def __bool__(self):
            raise KeyError("evidence matrix message truthiness unavailable")

        def __str__(self):
            return "有效來源訊息"

    context = minimal_context()
    context["data"]["source_audit"] = [
        {
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "message": BrokenEvidenceMatrixMessageTruth(),
            "error_kind": "fallback_should_not_override_present_message",
            "record_count": 1,
            "stale": False,
        }
    ]

    payload = build_evidence_matrix_payload(context)
    source_payload = payload["sources"]["market_data"]

    assert source_payload["text"] == "有效來源訊息"


def test_evidence_matrix_payload_normalizes_source_audit_child_maps_before_field_access():
    class BrokenEvidenceMatrixSourceRowGet(dict):
        def get(self, key, default=None):
            raise RuntimeError("evidence matrix source row get unavailable")

    context = minimal_context()
    context["data"]["source_audit"] = [
        BrokenEvidenceMatrixSourceRowGet({
            "source": "market_data",
            "provider": "yfinance",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "message": "ok",
            "record_count": 1,
            "stale": False,
        })
    ]

    try:
        payload = build_evidence_matrix_payload(context)
    except RuntimeError as exc:
        raise AssertionError(f"source audit child maps should not break evidence matrix payload: {exc}") from exc

    source_payload = payload["sources"]["market_data"]

    assert source_payload["source_document"] == "yfinance"
    assert source_payload["status"] == "success"
    assert source_payload["fetched_at"] == "2026-06-07T00:00:00+00:00"
    assert source_payload["text"] == "ok"


def test_evidence_matrix_rows_use_truthiness_safe_fetched_at(monkeypatch):
    class BrokenEvidenceMatrixFetchedAtTruthiness:
        def __bool__(self):
            raise KeyError("evidence matrix fetched_at truthiness unavailable")

        def __str__(self):
            return "2026-06-07T00:00:00+00:00"

    def malformed_key_evidence_rows(data):
        return [
            {
                "label": "股價與市值",
                "source_label": "市場資料",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": BrokenEvidenceMatrixFetchedAtTruthiness(),
                "stale": False,
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_key_evidence_rows", malformed_key_evidence_rows)
    context = minimal_context()
    context["parsed"]["price_targets"] = {"基本情境": 120}

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed evidence fetched_at should not break evidence matrix: {exc}") from exc

    valuation_row = next(row for row in rows if row["claim"] == "估值結論")
    assert valuation_row["fetched_at"] == "2026-06-07T00:00:00+00:00"


def test_evidence_matrix_markdown_cells_use_truthiness_safe_text(monkeypatch):
    class BrokenEvidenceMatrixMarkdownCellTruthiness:
        def __bool__(self):
            raise KeyError("evidence matrix markdown cell truthiness unavailable")

        def __str__(self):
            return "有效依據|含分隔"

    def malformed_evidence_matrix_rows(context):
        return [
            {
                "claim": "估值結論",
                "basis": BrokenEvidenceMatrixMarkdownCellTruthiness(),
                "source": "市場資料",
                "provider": "yfinance",
                "status": "success",
                "status_label": "成功",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "limitation": "未記錄額外資料限制。",
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_evidence_matrix_rows", malformed_evidence_matrix_rows)

    try:
        markdown = "\n".join(evidence_matrix.build_evidence_matrix_markdown(minimal_context()))
    except KeyError as exc:
        raise AssertionError(f"malformed markdown cell truthiness should not break evidence matrix markdown: {exc}") from exc

    assert "有效依據/含分隔" in markdown


def test_evidence_matrix_html_cells_use_shared_text_safety(monkeypatch):
    class BrokenEvidenceMatrixHtmlCellString:
        def __str__(self):
            raise KeyError("evidence matrix html cell string unavailable")

    def malformed_evidence_matrix_rows(context):
        return [
            {
                "claim": "估值結論",
                "basis": BrokenEvidenceMatrixHtmlCellString(),
                "source": "市場資料",
                "provider": "yfinance",
                "status": "success",
                "status_label": "成功",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "limitation": "未記錄額外資料限制。",
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_evidence_matrix_rows", malformed_evidence_matrix_rows)

    try:
        html = evidence_matrix.build_evidence_matrix_html(minimal_context())
    except KeyError as exc:
        raise AssertionError(f"malformed html cell string should not break evidence matrix html: {exc}") from exc

    assert "估值結論" in html
    assert "<td>N/A</td>" in html
    assert "evidence matrix html cell string unavailable" not in html


def test_evidence_matrix_rows_use_truthiness_safe_status(monkeypatch):
    class BrokenEvidenceMatrixStatusTruthiness:
        def __bool__(self):
            raise KeyError("evidence matrix status truthiness unavailable")

        def __str__(self):
            return "success"

    def malformed_key_evidence_rows(data):
        return [
            {
                "label": "股價與市值",
                "source_label": "市場資料",
                "provider": "yfinance",
                "status": BrokenEvidenceMatrixStatusTruthiness(),
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "stale": False,
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_key_evidence_rows", malformed_key_evidence_rows)
    context = minimal_context()
    context["parsed"]["price_targets"] = {"基本情境": 120}

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed evidence status should not break evidence matrix: {exc}") from exc

    valuation_row = next(row for row in rows if row["claim"] == "估值結論")
    assert valuation_row["status"] == "success"
    assert valuation_row["status_label"] == "成功"


def test_evidence_matrix_rows_use_truthiness_safe_provider(monkeypatch):
    class BrokenEvidenceMatrixProviderTruthiness:
        def __bool__(self):
            raise KeyError("evidence matrix provider truthiness unavailable")

        def __str__(self):
            return "yfinance"

    def malformed_key_evidence_rows(data):
        return [
            {
                "label": "股價與市值",
                "source_label": "市場資料",
                "provider": BrokenEvidenceMatrixProviderTruthiness(),
                "status": "success",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "stale": False,
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_key_evidence_rows", malformed_key_evidence_rows)
    context = minimal_context()
    context["parsed"]["price_targets"] = {"基本情境": 120}

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed evidence provider should not break evidence matrix: {exc}") from exc

    valuation_row = next(row for row in rows if row["claim"] == "估值結論")
    assert valuation_row["provider"] == "yfinance"


def test_evidence_matrix_rows_use_text_safe_source_labels(monkeypatch):
    class BrokenEvidenceMatrixLabelHash:
        def __hash__(self):
            raise KeyError("evidence matrix label hash unavailable")

        def __str__(self):
            return "股價與市值"

    def malformed_key_evidence_rows(data):
        return [
            {
                "label": BrokenEvidenceMatrixLabelHash(),
                "source_label": "市場資料",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "stale": False,
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_key_evidence_rows", malformed_key_evidence_rows)
    context = minimal_context()
    context["parsed"]["price_targets"] = {"基本情境": 120}

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed evidence labels should not break evidence matrix matching: {exc}") from exc

    valuation_row = next(row for row in rows if row["claim"] == "估值結論")
    assert valuation_row["source"] == "市場資料 + 年度財報 + P/E 河流圖"
    assert valuation_row["provider"] == "yfinance"


def test_evidence_matrix_limitations_use_bool_safe_stale_flags(monkeypatch):
    class BrokenEvidenceMatrixStaleTruthiness:
        def __bool__(self):
            raise KeyError("evidence matrix stale truthiness unavailable")

        def __str__(self):
            return "bad-stale"

    def malformed_key_evidence_rows(data):
        return [
            {
                "label": "股價與市值",
                "source_label": "市場資料",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "stale": BrokenEvidenceMatrixStaleTruthiness(),
            }
        ]

    monkeypatch.setattr(evidence_matrix, "build_key_evidence_rows", malformed_key_evidence_rows)
    context = minimal_context()
    context["parsed"]["price_targets"] = {"基本情境": 120}

    try:
        rows = build_evidence_matrix_rows(context)
    except KeyError as exc:
        raise AssertionError(f"malformed evidence stale flag should not break evidence matrix: {exc}") from exc

    valuation_row = next(row for row in rows if row["claim"] == "估值結論")
    assert valuation_row["source"] == "市場資料 + 年度財報 + P/E 河流圖"
    assert valuation_row["provider"] == "yfinance"
    assert valuation_row["status"] == "success"
    assert "過期來源" not in valuation_row["limitation"]
    assert "bad-stale" not in valuation_row["limitation"]


def test_evidence_matrix_limitations_use_shared_text_safety_for_data_source_notes():
    context = minimal_context()
    context["data"]["data_source_notes"] = [
        b"bad-note",
        bytearray(b"bad-note"),
        "有效資料限制說明。",
    ]

    rows = build_evidence_matrix_rows(context)
    recommendation_row = next(row for row in rows if row["claim"] == "最終投資建議")

    assert "有效資料限制說明。" in recommendation_row["limitation"]
    assert "bad-note" not in recommendation_row["limitation"]


def test_evidence_matrix_limitations_accept_tuple_data_source_notes():
    context = minimal_context()
    context["data"]["data_source_notes"] = (
        "有效 tuple 資料限制說明。",
        b"bad-tuple-note",
    )

    rows = build_evidence_matrix_rows(context)
    recommendation_row = next(row for row in rows if row["claim"] == "最終投資建議")

    assert "有效 tuple 資料限制說明。" in recommendation_row["limitation"]
    assert "bad-tuple-note" not in recommendation_row["limitation"]
