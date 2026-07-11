import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


import agent_runtime.prompting as prompting  # noqa: E402
import agent_runtime.prompt_config as prompt_config  # noqa: E402
import prompt_builder  # noqa: E402
import prompt_rules  # noqa: E402
from data_trust import source_record_count  # noqa: E402
from llm_rate_limits import estimate_text_tokens  # noqa: E402
from pipeline_modes import PIPELINE_DEFINITIONS  # noqa: E402
from prompt_builder import format_data_for_prompt, render_prompt_template  # noqa: E402
from state_memory import initialize_agent_state  # noqa: E402
from temporal_memory_service import build_valuation_memory_slice  # noqa: E402


def _payload_from_prompt(prompt_text: str) -> dict:
    payload_text = prompt_text.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
    return json.loads(payload_text)


class BrokenPromptString:
    def __str__(self):
        raise RuntimeError("prompt source audit string conversion unavailable")


class BrokenPromptInt:
    def __int__(self):
        raise RuntimeError("prompt source audit integer conversion unavailable")


class BrokenPromptBool:
    def __bool__(self):
        raise RuntimeError("prompt source audit bool conversion unavailable")


class BrokenPromptContext(dict):
    def __bool__(self):
        raise RuntimeError("prompt agent context truthiness unavailable")


class BrokenPromptIdentity(dict):
    def __bool__(self):
        raise RuntimeError("prompt company identity truthiness unavailable")


class BrokenPromptIdentityLength(dict):
    def __len__(self):
        raise RuntimeError("prompt company identity length unavailable")


class BrokenPromptIdentityGet(dict):
    def get(self, key, default=None):
        raise RuntimeError("prompt company identity get unavailable")


class BrokenPromptIdentityText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise RuntimeError("prompt identity text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenPromptIdentityList:
    def __getitem__(self, key):
        if isinstance(key, slice):
            return self
        raise IndexError(key)

    def __iter__(self):
        yield "SENT_ALIAS_1"
        yield "SENT_ALIAS_2"
        raise RuntimeError("prompt identity alias iterator unavailable")


class BrokenPromptIdentityNativeList(list):
    def __iter__(self):
        raise RuntimeError("prompt identity native list iterator unavailable")


class BrokenPromptFreshness(dict):
    def __bool__(self):
        raise RuntimeError("prompt freshness truthiness unavailable")


class BrokenPromptFreshnessSourceGet(dict):
    def get(self, key, default=None):
        if key in {"data_freshness", "source_freshness"}:
            raise RuntimeError("prompt freshness source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptInstitutionalTrading(dict):
    def __bool__(self):
        raise RuntimeError("prompt institutional trading truthiness unavailable")


class BrokenPromptInstitutionalTradingSourceGet(dict):
    def get(self, key, default=None):
        if key == "institutional_trading":
            raise RuntimeError("prompt institutional trading source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptRagContext(dict):
    def __bool__(self):
        raise RuntimeError("prompt rag context truthiness unavailable")


class BrokenPromptRagText:
    def __len__(self):
        raise RuntimeError("prompt rag text length unavailable")

    def __str__(self):
        return "SENT_RAG_TEXT"


class BrokenPromptTemporalReflection:
    def __bool__(self):
        raise RuntimeError("prompt temporal reflection truthiness unavailable")

    def __str__(self):
        return "SENT_TEMPORAL_REFLECTION"


class BrokenPromptTemporalBacktests:
    def __iter__(self):
        yield {"summary": "SENT_BACKTEST_SUMMARY_1"}
        yield {"summary": "SENT_BACKTEST_SUMMARY_2"}
        raise RuntimeError("prompt temporal backtests iterator unavailable")


class BrokenPromptStateViewValue:
    def __str__(self):
        return "SENT_STATE_VIEW_VALUE"


class BrokenPromptStateViewItems(dict):
    def items(self):
        raise RuntimeError("prompt state view items unavailable")


class BrokenPromptStateViewList(list):
    def __iter__(self):
        raise RuntimeError("prompt state view list iterator unavailable")


class BrokenPromptStateViewSet(set):
    def __iter__(self):
        raise RuntimeError("prompt state view set iterator unavailable")


class BrokenPromptPrimaryProbeFlag:
    def __bool__(self):
        raise RuntimeError("prompt primary probe flag truthiness unavailable")


class BrokenPromptForensicWarning:
    def __bool__(self):
        raise RuntimeError("prompt forensic warning truthiness unavailable")

    def __str__(self):
        return "SENT_FORENSIC_WARNING"


class BrokenPromptRuntimeInstruction:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise RuntimeError("prompt runtime instruction truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenPromptRuleText:
    def __str__(self):
        raise RuntimeError("prompt rule text conversion unavailable")


class BrokenPromptRuleBlockText:
    def __init__(self, text: str):
        self.text = text

    def __bool__(self):
        raise RuntimeError("prompt rule block text truthiness unavailable")

    def __str__(self):
        return self.text


class BrokenPromptRulesMapping(dict):
    def __bool__(self):
        raise RuntimeError("prompt rules mapping truthiness unavailable")

    def get(self, key, default=None):
        raise RuntimeError("prompt rules mapping get unavailable")

    def items(self):
        raise RuntimeError("prompt rules mapping items unavailable")


class BrokenPromptPipelineId:
    def __bool__(self):
        raise RuntimeError("prompt pipeline id truthiness unavailable")

    def __str__(self):
        return "v3"


class BrokenPromptDataTrustList:
    def __bool__(self):
        raise RuntimeError("prompt data trust list truthiness unavailable")

    def __iter__(self):
        yield "SENT_DATA_TRUST_ITEM_1"
        yield "SENT_DATA_TRUST_ITEM_2"
        raise RuntimeError("prompt data trust list iterator unavailable")


class BrokenPromptDataTrustGet(dict):
    def get(self, key, default=None):
        raise RuntimeError("prompt data trust get unavailable")


class BrokenPromptSourceAuditRootGet(dict):
    def get(self, key, default=None):
        if key == "source_audit":
            raise RuntimeError("prompt source audit root get unavailable")
        return dict.get(self, key, default)


class BrokenPromptSourceAuditEntryGet(dict):
    def get(self, key, default=None):
        if key in {
            "source",
            "provider",
            "status",
            "record_count",
            "message",
            "error_kind",
            "cache_hit",
            "stale",
        }:
            raise RuntimeError("prompt source audit entry get unavailable")
        return dict.get(self, key, default)


class BrokenPromptIterable:
    def __bool__(self):
        raise RuntimeError("prompt compact list truthiness unavailable")

    def __iter__(self):
        yield {"title": "SENT_COMPACT_ITEM_1"}
        yield {"title": "SENT_COMPACT_ITEM_2"}
        raise RuntimeError("prompt compact list iterator unavailable")


class BrokenPromptMarketCatalystSourceGet(dict):
    def get(self, key, default=None):
        if key == "recent_catalysts":
            raise RuntimeError("prompt market catalyst source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptDynamicPeerMetricsSourceGet(dict):
    def get(self, key, default=None):
        if key == "dynamic_peer_metrics":
            raise RuntimeError("prompt dynamic peer metrics source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptPeerDiscoverySourceGet(dict):
    def get(self, key, default=None):
        if key == "peer_discovery_results":
            raise RuntimeError("prompt peer discovery source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptMonthlyRevenueSourceGet(dict):
    def get(self, key, default=None):
        if key == "recent_monthly_revenue":
            raise RuntimeError("prompt monthly revenue source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptDataQualityNotesSourceGet(dict):
    def get(self, key, default=None):
        if key == "data_source_notes":
            raise RuntimeError("prompt data quality notes source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptPeRiverChartSourceGet(dict):
    def get(self, key, default=None):
        if key == "pe_river_chart":
            raise RuntimeError("prompt pe river chart source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptCrossCheckSourceGet(dict):
    def get(self, key, default=None):
        if key in {"dupont_identity_note", "equity_multiplier_note", "wacc_capital_structure_note"}:
            raise RuntimeError("prompt cross-check source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptMarketDataSourceGet(dict):
    def get(self, key, default=None):
        if key in {"current_price", "market_cap_raw", "week_52_high", "week_52_low"}:
            raise RuntimeError("prompt market data source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptValuationMetricsSourceGet(dict):
    def get(self, key, default=None):
        if key in {
            "pe_ratio_raw",
            "forward_pe_raw",
            "pb_ratio",
            "ps_ratio",
            "ev_ebitda",
            "shares_raw",
            "trailing_eps",
            "forward_eps",
            "dividend_yield_raw",
            "dividend_rate_raw",
            "payout_ratio_raw",
        }:
            raise RuntimeError("prompt valuation metrics source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptTtmFinancialsSourceGet(dict):
    def get(self, key, default=None):
        if key in {
            "revenue_ttm_raw",
            "net_income_ttm_raw",
            "net_income_ttm_source",
            "ebitda_raw",
            "gross_margin_raw",
            "operating_margin_raw",
            "profit_margin_raw",
            "profit_margin_provider_raw",
        }:
            raise RuntimeError("prompt ttm financials source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptCashFlowSourceGet(dict):
    def get(self, key, default=None):
        if key in {"free_cash_flow_raw", "operating_cash_flow_raw"}:
            raise RuntimeError("prompt cash flow source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptBalanceSheetSourceGet(dict):
    def get(self, key, default=None):
        if key in {"total_debt_raw", "total_cash_raw", "debt_to_equity", "current_ratio", "equity_multiplier"}:
            raise RuntimeError("prompt balance sheet source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptGrowthSourceGet(dict):
    def get(self, key, default=None):
        if key in {
            "latest_annual_revenue_growth",
            "latest_annual_net_income_growth",
            "ttm_vs_latest_annual_revenue_change",
            "yahoo_revenue_growth",
            "yahoo_earnings_growth",
            "revenue_cagr_5yr",
        }:
            raise RuntimeError("prompt growth source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptCompanyMetadataSourceGet(dict):
    def get(self, key, default=None):
        if key in {"data_schema_version", "sector", "industry", "country", "employees", "fetch_date"}:
            raise RuntimeError("prompt company metadata source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptFinancialHistorySourceGet(dict):
    def get(self, key, default=None):
        if key in {"revenue_history", "net_income_history", "fcf_history"}:
            raise RuntimeError("prompt financial history source get unavailable")
        return dict.get(self, key, default)


class BrokenPromptNotes:
    def __bool__(self):
        raise RuntimeError("prompt notes truthiness unavailable")

    def __iter__(self):
        yield "SENT_NOTE_1"
        yield "SENT_NOTE_2"
        raise RuntimeError("prompt notes iterator unavailable")


class BrokenPromptHistoryYears:
    def __bool__(self):
        raise RuntimeError("prompt history years truthiness unavailable")

    def __iter__(self):
        yield "2024"
        yield "2025"
        raise RuntimeError("prompt history years iterator unavailable")


class BrokenPromptHistoryValues:
    def __bool__(self):
        raise RuntimeError("prompt history value truthiness unavailable")

    def __iter__(self):
        yield 100
        yield 120
        raise RuntimeError("prompt history value iterator unavailable")


class BrokenPromptPeRiverYears:
    def __bool__(self):
        raise RuntimeError("prompt pe river years truthiness unavailable")

    def __iter__(self):
        yield 2020
        yield 2021
        yield 2022
        yield 2023
        yield 2024
        yield 2025
        raise RuntimeError("prompt pe river years iterator unavailable")


class BrokenPromptPeRiverChart(dict):
    def __bool__(self):
        raise RuntimeError("prompt pe river chart truthiness unavailable")


class BrokenPromptPeRiverChartGet(dict):
    def get(self, key, default=None):
        raise RuntimeError("prompt pe river chart get unavailable")


def test_render_prompt_template_warns_for_legacy_placeholders():
    with pytest.warns(DeprecationWarning, match="legacy prompt placeholder"):
        rendered = render_prompt_template("標的 {ticker}", {"ticker": "2330.TW"})

    assert rendered == "標的 2330.TW"


def test_production_analysis_prompts_use_jinja_placeholders():
    templates = {
        **prompt_config.ANALYSIS_PROMPTS,
        **prompt_config.NAMED_ANALYSIS_PROMPTS,
    }

    legacy_templates = [
        str(key)
        for key, template in templates.items()
        if prompt_builder.LEGACY_PLACEHOLDER_RE.search(template)
    ]

    assert legacy_templates == []


def test_prompt_company_identity_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": BrokenPromptIdentity({
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "allowed_aliases": ["第一金", "第一金控"],
            "forbidden_aliases": ["第一銀行"],
            "industry_categories": ["金融業"],
            "same_industry_peers": ["2884.TW"],
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))
    identity = payload["company"]["identity"]

    assert identity["stock_id"] == "2892"
    assert identity["official_name"] == "第一金融控股股份有限公司"
    assert identity["legal_name"] == "First Financial Holding Co., Ltd."
    assert identity["allowed_aliases"] == ["第一金", "第一金控"]
    assert identity["forbidden_aliases"] == ["第一銀行"]
    assert identity["industry_categories"] == ["金融業"]
    assert identity["same_industry_peers"] == ["2884.TW"]


def test_prompt_company_identity_keeps_get_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": BrokenPromptIdentityGet({
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "allowed_aliases": ["第一金", "第一金控"],
            "forbidden_aliases": ["第一銀行"],
            "industry_categories": ["金融業"],
            "same_industry_peers": ["2884.TW"],
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))
    identity = payload["company"]["identity"]

    assert identity["stock_id"] == "2892"
    assert identity["official_name"] == "第一金融控股股份有限公司"
    assert identity["legal_name"] == "First Financial Holding Co., Ltd."
    assert identity["allowed_aliases"] == ["第一金", "第一金控"]
    assert identity["forbidden_aliases"] == ["第一銀行"]
    assert identity["industry_categories"] == ["金融業"]
    assert identity["same_industry_peers"] == ["2884.TW"]


def test_prompt_company_identity_keeps_source_data_mapping_when_accessor_fails():
    data = BrokenPromptRulesMapping(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "company_identity": {
                "stock_id": "2892",
                "official_name": "第一金融控股股份有限公司",
                "legal_name": "First Financial Holding Co., Ltd.",
                "allowed_aliases": ["第一金", "第一金控"],
                "forbidden_aliases": ["第一銀行"],
                "industry_categories": ["金融業"],
                "same_industry_peers": ["2884.TW"],
            },
        }
    )

    identity = prompt_builder._prompt_company_identity(data)

    assert identity["ticker"] == "2892.TW"
    assert identity["company_name"] == "第一金"
    assert identity["stock_id"] == "2892"
    assert identity["official_name"] == "第一金融控股股份有限公司"
    assert identity["legal_name"] == "First Financial Holding Co., Ltd."
    assert identity["allowed_aliases"] == ["第一金", "第一金控"]
    assert identity["forbidden_aliases"] == ["第一銀行"]
    assert identity["industry_categories"] == ["金融業"]
    assert identity["same_industry_peers"] == ["2884.TW"]


def test_agent_runtime_identity_guard_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": BrokenPromptIdentity({
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "english_names": ["First Financial Holding"],
            "forbidden_aliases": ["第一銀行"],
        }),
    }

    guard = prompting.build_company_identity_guard(data)

    assert "第一金融控股股份有限公司" in guard
    assert "First Financial Holding Co., Ltd." in guard
    assert "First Financial Holding" in guard
    assert "第一銀行" in guard


def test_agent_runtime_identity_guard_keeps_length_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": BrokenPromptIdentityLength({
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "english_names": ["First Financial Holding"],
            "forbidden_aliases": ["第一銀行"],
        }),
    }

    guard = prompting.build_company_identity_guard(data)

    assert "第一金融控股股份有限公司" in guard
    assert "First Financial Holding Co., Ltd." in guard
    assert "First Financial Holding" in guard
    assert "第一銀行" in guard


def test_agent_runtime_identity_guard_keeps_get_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": BrokenPromptIdentityGet({
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "english_names": ["First Financial Holding"],
            "forbidden_aliases": ["第一銀行"],
        }),
    }

    guard = prompting.build_company_identity_guard(data)

    assert "第一金融控股股份有限公司" in guard
    assert "First Financial Holding Co., Ltd." in guard
    assert "First Financial Holding" in guard
    assert "第一銀行" in guard


def test_agent_runtime_identity_guard_keeps_data_mapping_when_accessor_fails():
    data = BrokenPromptRulesMapping(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "company_identity": {
                "stock_id": "2892",
                "official_name": "第一金融控股股份有限公司",
                "legal_name": "First Financial Holding Co., Ltd.",
                "english_names": ["First Financial Holding"],
                "forbidden_aliases": ["第一銀行"],
            },
        }
    )

    guard = prompting.build_company_identity_guard(data)

    assert "2892.TW" in guard
    assert "第一金融控股股份有限公司" in guard
    assert "First Financial Holding Co., Ltd." in guard
    assert "First Financial Holding" in guard
    assert "第一銀行" in guard


def test_agent_runtime_identity_guard_keeps_truthiness_broken_text_fields():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": {
            "stock_id": "2892",
            "official_name": BrokenPromptIdentityText("第一金融控股股份有限公司"),
            "legal_name": BrokenPromptIdentityText("First Financial Holding Co., Ltd."),
            "forbidden_aliases": ["第一銀行"],
        },
    }

    guard = prompting.build_company_identity_guard(data)

    assert "第一金融控股股份有限公司" in guard
    assert "First Financial Holding Co., Ltd." in guard
    assert "第一銀行" in guard


def test_agent_runtime_identity_guard_stringifies_ticker_and_stock_id_fields():
    data = {
        "ticker": BrokenPromptString(),
        "company_name": "第一金",
        "company_identity": {
            "ticker": "2892.TW",
            "stock_id": BrokenPromptString(),
            "official_name": "第一金融控股股份有限公司",
            "forbidden_aliases": ["第一銀行"],
        },
    }

    guard = prompting.build_company_identity_guard(data)

    assert "2892.TW" in guard
    assert "第一金融控股股份有限公司" in guard
    assert "第一銀行" in guard


def test_agent_runtime_identity_guard_preserves_aliases_before_iterator_failure():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": {
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "english_names": BrokenPromptIdentityList(),
            "forbidden_aliases": BrokenPromptIdentityList(),
        },
    }

    guard = prompting.build_company_identity_guard(data)

    assert "SENT_ALIAS_1" in guard
    assert "SENT_ALIAS_2" in guard


def test_agent_runtime_identity_guard_limits_alias_native_list_when_iterator_fails():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "company_identity": {
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "english_names": BrokenPromptIdentityNativeList(
                [
                    "SENT_ALIAS_NATIVE_1",
                    "SENT_ALIAS_NATIVE_2",
                    "SENT_ALIAS_NATIVE_3",
                    "SENT_ALIAS_NATIVE_4",
                ]
            ),
            "forbidden_aliases": BrokenPromptIdentityNativeList(
                [
                    "SENT_FORBIDDEN_NATIVE_1",
                    "SENT_FORBIDDEN_NATIVE_2",
                ]
            ),
        },
    }

    guard = prompting.build_company_identity_guard(data)

    assert "SENT_ALIAS_NATIVE_1" in guard
    assert "SENT_ALIAS_NATIVE_2" in guard
    assert "SENT_ALIAS_NATIVE_3" in guard
    assert "SENT_ALIAS_NATIVE_4" not in guard
    assert "SENT_FORBIDDEN_NATIVE_1" in guard
    assert "SENT_FORBIDDEN_NATIVE_2" in guard


def test_identity_guard_rule_templates_skip_malformed_template_text(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "identity_guard": {
                "title": BrokenPromptRuleBlockText("SENT_IDENTITY_TITLE"),
                "rules": [
                    "SENT_IDENTITY_BASE {ticker} {official_name}",
                    BrokenPromptRuleText(),
                ],
                "legal_name_rule": BrokenPromptRuleText(),
                "english_names_rule": "SENT_IDENTITY_ENGLISH {english_names}",
                "forbidden_aliases_rule": "SENT_IDENTITY_FORBIDDEN {forbidden_aliases}",
            }
        },
    )

    lines = prompt_rules.build_identity_guard_rule_lines(
        {
            "ticker": "2892.TW",
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "english_names": "First Financial Holding",
            "forbidden_aliases": "第一銀行",
        }
    )
    block = "\n".join(lines)

    assert "SENT_IDENTITY_TITLE" in block
    assert "SENT_IDENTITY_BASE 2892.TW 第一金融控股股份有限公司" in block
    assert "SENT_IDENTITY_ENGLISH First Financial Holding" in block
    assert "SENT_IDENTITY_FORBIDDEN 第一銀行" in block


def test_identity_guard_rule_lines_preserve_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "identity_guard": BrokenPromptRulesMapping(
                {
                    "title": "SENT_IDENTITY_MAPPING_TITLE",
                    "rules": [
                        "SENT_IDENTITY_MAPPING_BASE {ticker} {official_name}",
                        BrokenPromptRuleText(),
                    ],
                    "legal_name_rule": "SENT_IDENTITY_MAPPING_LEGAL {legal_name}",
                    "english_names_rule": "SENT_IDENTITY_MAPPING_ENGLISH {english_names}",
                    "forbidden_aliases_rule": "SENT_IDENTITY_MAPPING_FORBIDDEN {forbidden_aliases}",
                }
            )
        },
    )

    lines = prompt_rules.build_identity_guard_rule_lines(
        {
            "ticker": "2892.TW",
            "stock_id": "2892",
            "official_name": "第一金融控股股份有限公司",
            "legal_name": "First Financial Holding Co., Ltd.",
            "english_names": "First Financial Holding",
            "forbidden_aliases": "第一銀行",
        }
    )
    block = "\n".join(lines)

    assert "SENT_IDENTITY_MAPPING_TITLE" in block
    assert "SENT_IDENTITY_MAPPING_BASE 2892.TW 第一金融控股股份有限公司" in block
    assert "SENT_IDENTITY_MAPPING_LEGAL First Financial Holding Co., Ltd." in block
    assert "SENT_IDENTITY_MAPPING_ENGLISH First Financial Holding" in block
    assert "SENT_IDENTITY_MAPPING_FORBIDDEN 第一銀行" in block


def test_identity_guard_rule_lines_preserve_values_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "identity_guard": {
                "title": "SENT_IDENTITY_VALUES_TITLE",
                "rules": ["SENT_IDENTITY_VALUES_BASE {ticker} {official_name}"],
                "legal_name_rule": "SENT_IDENTITY_VALUES_LEGAL {legal_name}",
                "english_names_rule": "SENT_IDENTITY_VALUES_ENGLISH {english_names}",
                "forbidden_aliases_rule": "SENT_IDENTITY_VALUES_FORBIDDEN {forbidden_aliases}",
            }
        },
    )

    lines = prompt_rules.build_identity_guard_rule_lines(
        BrokenPromptRulesMapping(
            {
                "ticker": "2892.TW",
                "stock_id": "2892",
                "official_name": "第一金融控股股份有限公司",
                "legal_name": "First Financial Holding Co., Ltd.",
                "english_names": "First Financial Holding",
                "forbidden_aliases": "第一銀行",
            }
        )
    )
    block = "\n".join(lines)

    assert "SENT_IDENTITY_VALUES_TITLE" in block
    assert "SENT_IDENTITY_VALUES_BASE 2892.TW 第一金融控股股份有限公司" in block
    assert "SENT_IDENTITY_VALUES_LEGAL First Financial Holding Co., Ltd." in block
    assert "SENT_IDENTITY_VALUES_ENGLISH First Financial Holding" in block
    assert "SENT_IDENTITY_VALUES_FORBIDDEN 第一銀行" in block


def test_prompt_data_freshness_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "data_freshness": BrokenPromptFreshness({
            "market_data": {"status": "stale", "as_of": "2026-07-09"},
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["data_freshness"] == {
        "market_data": {"status": "stale", "as_of": "2026-07-09"},
    }


def test_prompt_source_freshness_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "source_freshness": BrokenPromptFreshness({
            "yfinance": {"status": "cached", "age_seconds": 3600},
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["source_freshness"] == {
        "yfinance": {"status": "cached", "age_seconds": 3600},
    }


def test_prompt_freshness_keeps_source_data_mapping_when_accessor_fails():
    data = BrokenPromptFreshnessSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "data_freshness": {
                "market_data": {"status": "stale", "as_of": "2026-07-09"},
            },
            "source_freshness": {
                "yfinance": {"status": "cached", "age_seconds": 3600},
            },
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["data_freshness"] == {
        "market_data": {"status": "stale", "as_of": "2026-07-09"},
    }
    assert payload["source_freshness"] == {
        "yfinance": {"status": "cached", "age_seconds": 3600},
    }


def test_prompt_institutional_trading_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "institutional_trading": BrokenPromptInstitutionalTrading({
            "daily_total_net_buy_last_10": [
                {"date": "2026-07-09", "net_buy": 100},
            ],
            "summary": "SENT_INSTITUTIONAL_TRADING",
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["institutional_trading"] == {
        "daily_total_net_buy_last_10": [
            {"date": "2026-07-09", "net_buy": 100},
        ],
        "summary": "SENT_INSTITUTIONAL_TRADING",
    }


def test_prompt_institutional_trading_keeps_source_data_mapping_when_accessor_fails():
    data = BrokenPromptInstitutionalTradingSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "institutional_trading": {
                "daily_total_net_buy_last_10": [
                    {"date": "2026-07-09", "net_buy": 100},
                ],
                "summary": "SENT_INSTITUTIONAL_TRADING",
            },
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["institutional_trading"] == {
        "daily_total_net_buy_last_10": [
            {"date": "2026-07-09", "net_buy": 100},
        ],
        "summary": "SENT_INSTITUTIONAL_TRADING",
    }


@pytest.mark.parametrize("field", ["critical_failures", "stale_sources", "notes", "reason_codes"])
def test_prompt_data_trust_lists_preserve_items_before_iterator_failures(field):
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "data_trust": {
            "status": "partial",
            field: BrokenPromptDataTrustList(),
        },
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["data_trust"][field] == [
        "SENT_DATA_TRUST_ITEM_1",
        "SENT_DATA_TRUST_ITEM_2",
    ]


def test_prompt_data_trust_keeps_source_data_mapping_when_accessor_fails():
    data = BrokenPromptRulesMapping({
        "ticker": "2892.TW",
        "company_name": "第一金",
        "data_trust": {
            "status": "partial",
            "critical_failures": ["market_data_timeout"],
            "stale_sources": ["fundamentals"],
            "last_market_data_at": "2026-07-11T09:30:00+08:00",
            "notes": ["provider fallback used"],
            "reason_codes": ["provider_sla_partial"],
        },
    })

    trust = prompt_builder._prompt_data_trust(data)

    assert trust == {
        "status": "partial",
        "critical_failures": ["market_data_timeout"],
        "stale_sources": ["fundamentals"],
        "last_market_data_at": "2026-07-11T09:30:00+08:00",
        "notes": ["provider fallback used"],
        "reason_codes": ["provider_sla_partial"],
    }


def test_prompt_data_trust_keeps_field_mapping_when_accessor_fails():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "data_trust": BrokenPromptDataTrustGet({
            "status": "partial",
            "critical_failures": ["market_data_timeout"],
            "stale_sources": ["fundamentals"],
            "last_market_data_at": "2026-07-11T09:30:00+08:00",
            "notes": ["provider fallback used"],
            "reason_codes": ["provider_sla_partial"],
        }),
    }

    trust = prompt_builder._prompt_data_trust(data)

    assert trust == {
        "status": "partial",
        "critical_failures": ["market_data_timeout"],
        "stale_sources": ["fundamentals"],
        "last_market_data_at": "2026-07-11T09:30:00+08:00",
        "notes": ["provider fallback used"],
        "reason_codes": ["provider_sla_partial"],
    }


def test_data_for_agent_prompt_routes_new_context_by_role():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": {"source": "FRED"},
        "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
        "alternative_data": {"job_openings_104": {"job_count": 128}},
        "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
        "social_sentiment": {"dcard": [{"title": "Dcard 討論"}]},
        "sec_edgar": {"recent_filings": [{"form": "10-Q"}]},
        "taiwan_open_data": {"rates": {"USD": {"sell": "31.50"}}},
        "earnings_call": {"period": "2026Q1", "transcript_excerpt": "AI guidance stays strong."},
    }

    assert hasattr(prompting, "data_for_agent_prompt")
    assert "macro_indicators" in prompting.data_for_agent_prompt(11, data)
    assert "chip_data" not in prompting.data_for_agent_prompt(11, data)
    assert "chip_data" in prompting.data_for_agent_prompt(15, data)
    assert "chip_data" in prompting.data_for_agent_prompt(18, data)
    assert "sentiment_context" in prompting.data_for_agent_prompt(17, data)
    assert "social_sentiment" in prompting.data_for_agent_prompt(17, data)
    assert "alternative_data" in prompting.data_for_agent_prompt(14, data)
    assert "alternative_data" in prompting.data_for_agent_prompt(13, data)
    assert "sec_edgar" in prompting.data_for_agent_prompt(13, data)
    assert "sec_edgar" in prompting.data_for_agent_prompt(14, data)
    assert "sec_edgar" in prompting.data_for_agent_prompt(21, data)
    assert "taiwan_open_data" in prompting.data_for_agent_prompt(11, data)
    assert "earnings_call" in prompting.data_for_agent_prompt(20, data)
    assert "macro_indicators" not in prompting.data_for_agent_prompt(12, data)
    assert "chip_data" not in prompting.data_for_agent_prompt(12, data)
    assert "alternative_data" not in prompting.data_for_agent_prompt(12, data)
    assert "sentiment_context" not in prompting.data_for_agent_prompt(12, data)
    assert "social_sentiment" not in prompting.data_for_agent_prompt(12, data)
    assert "sec_edgar" not in prompting.data_for_agent_prompt(12, data)
    assert "taiwan_open_data" not in prompting.data_for_agent_prompt(12, data)
    assert "earnings_call" not in prompting.data_for_agent_prompt(12, data)


def test_valuation_agents_receive_temporal_memory_slice_only():
    temporal_memory = {
        "previous_report": {
            "target_3m": "650",
            "target_6m": "700",
            "target_12m": "800",
            "recommendation": "買入",
            "date": "2024-01-01",
            "summary": "很長的前期完整報告文字不應進入估值 Agent。",
        },
        "backtests": [{"roi_pct": 12.5, "hit": True, "summary": "完整回測說明"}],
        "reflection_prompt": "完整最終 Agent 反思 prompt",
    }
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "temporal_memory": temporal_memory,
    }

    valuation_payload = prompting.data_for_agent_prompt(4, data)
    final_payload = prompting.data_for_agent_prompt(7, data)

    assert "valuation_memory" in valuation_payload
    assert "temporal_memory" not in valuation_payload
    assert valuation_payload["valuation_memory"]["prior_target_3m"] == "650"
    assert valuation_payload["valuation_memory"]["latest_backtest_roi"] == 12.5
    assert "summary" not in valuation_payload["valuation_memory"]
    assert "temporal_memory" in final_payload
    assert "valuation_memory" not in final_payload


def test_build_valuation_memory_slice_keeps_only_valuation_fields():
    result = build_valuation_memory_slice({
        "previous_report": {"target_3m": "650", "recommendation": "買入", "date": "2024-01-01", "summary": "完整報告"},
        "backtests": [{"roi_pct": 12.5, "hit": True, "details": "long"}],
    })

    assert result["prior_target_3m"] == "650"
    assert result["latest_backtest_hit"] is True
    assert "note" in result
    assert "summary" not in result


def test_format_data_for_prompt_exposes_only_agent_routed_external_context():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": {"source": "FRED", "summary_text": "macro"},
        "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
        "alternative_data": {"job_openings_104": {"job_count": 128}},
        "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
        "social_sentiment": {"dcard": [{"title": "Dcard 討論"}]},
        "sec_edgar": {"recent_filings": [{"form": "10-Q"}]},
        "taiwan_open_data": {"rates": {"USD": {"sell": "31.50"}}},
        "earnings_call": {"period": "2026Q1", "transcript_excerpt": "法說會展望維持強勁"},
    }

    assert hasattr(prompting, "data_for_agent_prompt")
    agent_11_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(11, data)))
    agent_12_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(12, data)))
    agent_15_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(15, data)))
    agent_17_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(17, data)))
    agent_13_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(13, data)))
    agent_20_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(20, data)))

    assert agent_11_payload["agent_context"]["macro_indicators"]["source"] == "FRED"
    assert agent_11_payload["agent_context"]["taiwan_open_data"]["rates"]["USD"]["sell"] == "31.50"
    assert "chip_data" not in agent_11_payload["agent_context"]
    assert agent_15_payload["agent_context"]["chip_data"]["tdcc_shareholder_distribution"]["major_holders_gt_1000_lots_pct"] == 42.1
    assert agent_17_payload["agent_context"]["sentiment_context"]["ptt_titles"] == ["AI 題材升溫"]
    assert agent_17_payload["agent_context"]["social_sentiment"]["dcard"][0]["title"] == "Dcard 討論"
    assert agent_13_payload["agent_context"]["sec_edgar"]["recent_filings"][0]["form"] == "10-Q"
    assert agent_20_payload["agent_context"]["earnings_call"]["transcript_excerpt"] == "法說會展望維持強勁"
    assert agent_12_payload["agent_context"] == {}


def test_agent_context_keeps_truthiness_broken_context_values():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": BrokenPromptContext({"source": "FRED"}),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["agent_context"]["macro_indicators"]["source"] == "FRED"


def test_agent_context_keeps_source_data_mapping_when_accessor_fails():
    data = BrokenPromptRulesMapping(
        {
            "macro_indicators": {"source": "FRED"},
            "chip_data": {"tdcc_shareholder_distribution": {"major": 42}},
            "alternative_data": {"job_openings_104": {"job_count": 10}},
            "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
            "social_sentiment": {"dcard": [{"title": "Dcard 討論"}]},
            "sec_edgar": {"recent_filings": [{"form": "10-Q"}]},
            "taiwan_open_data": {"rates": {"USD": {"sell": "31.50"}}},
            "earnings_call": {"period": "2026Q1", "transcript_excerpt": "guidance"},
        }
    )

    context = prompt_builder._agent_context(data)

    assert context["macro_indicators"]["source"] == "FRED"
    assert context["chip_data"]["tdcc_shareholder_distribution"]["major"] == 42
    assert context["alternative_data"]["job_openings_104"]["job_count"] == 10
    assert context["sentiment_context"]["ptt_titles"] == ["AI 題材升溫"]
    assert context["social_sentiment"]["dcard"][0]["title"] == "Dcard 討論"
    assert context["sec_edgar"]["recent_filings"][0]["form"] == "10-Q"
    assert context["taiwan_open_data"]["rates"]["USD"]["sell"] == "31.50"
    assert context["earnings_call"]["transcript_excerpt"] == "guidance"


def test_build_prompt_exposes_earnings_call_via_agent_state_view():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "earnings_call": {
            "period": "2026Q1",
            "transcript_excerpt": "SENT_EARNINGS_CALL_CONTEXT",
        },
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "pipeline_id": "v1",
        "agent_state": initialize_agent_state(data, run_id="prompt-routing-test"),
    }

    agent_20_prompt = prompting.build_prompt(20, data, context)
    agent_21_prompt = prompting.build_prompt(21, data, context)
    agent_12_prompt = prompting.build_prompt(12, data, context)

    assert "earnings_call_context" in agent_20_prompt
    assert "SENT_EARNINGS_CALL_CONTEXT" in agent_20_prompt
    assert "SENT_EARNINGS_CALL_CONTEXT" in agent_21_prompt
    assert "SENT_EARNINGS_CALL_CONTEXT" not in agent_12_prompt


def test_every_pipeline_agent_receives_core_ai_data_payload():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "current_price": 123.45,
        "market_cap_raw": 9_000_000_000,
        "years": ["2024"],
        "revenue_history": [100],
        "net_income_history": [20],
        "source_audit": [{"source": "market_data", "provider": "fixture", "status": "success", "record_count": 2}],
    }
    all_agents = sorted({agent for definition in PIPELINE_DEFINITIONS.values() for agent in definition["agents"]})

    for agent_num in all_agents:
        payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(agent_num, data)))
        assert payload["market_data"]["current_price_twd"] == 123.45
        assert payload["history"]["rows"][0]["revenue_billion_twd"] == 100
        assert payload["source_audit_summary"][0]["source"] == "market_data"


def test_every_pipeline_agent_full_prompt_contains_data_payload_and_state_view():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "current_price": 123.45,
        "market_cap_raw": 9_000_000_000,
        "years": ["2024"],
        "revenue_history": [100],
        "net_income_history": [20],
        "recent_catalysts": [{"title": "SENT_CORE_AI_DATA"}],
        "source_audit": [
            {"source": "market_data", "provider": "fixture", "status": "success", "record_count": 2},
            {"source": "recent_catalysts", "provider": "fixture", "status": "success", "record_count": 1},
        ],
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "pipeline_id": "v1",
        "agent_state": initialize_agent_state(data, run_id="full-prompt-data-test"),
    }
    all_agents = sorted({agent for definition in PIPELINE_DEFINITIONS.values() for agent in definition["agents"]})

    for agent_num in all_agents:
        prompt = prompting.build_prompt(agent_num, data, context)
        assert "【財務資料 JSON】" in prompt, agent_num
        assert "source_audit_summary" in prompt, agent_num
        assert "SENT_CORE_AI_DATA" in prompt, agent_num
        assert "【AgentState view】" in prompt, agent_num


def test_source_audit_summary_exposes_actual_merged_record_count_when_latest_audit_lags():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "recent_catalysts": [
            {"title": "SENT_CATALYST_1"},
            {"title": "SENT_CATALYST_2"},
            {"title": "SENT_CATALYST_3"},
            {"title": "SENT_CATALYST_4"},
            {"title": "SENT_CATALYST_5"},
        ],
        "source_audit": [
            {
                "source": "recent_catalysts",
                "provider": "Recent catalysts providers",
                "status": "success",
                "record_count": 5,
                "cache_hit": False,
                "stale": False,
            },
            {
                "source": "recent_catalysts",
                "provider": "Yahoo Finance news",
                "status": "success",
                "record_count": 1,
                "cache_hit": False,
                "stale": False,
            },
        ],
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))
    summary = {entry["source"]: entry for entry in payload["source_audit_summary"]}

    assert summary["recent_catalysts"]["provider"] == "Yahoo Finance news"
    assert summary["recent_catalysts"]["record_count"] == 1
    assert summary["recent_catalysts"]["merged_record_count"] == 5
    assert summary["recent_catalysts"]["record_count_mismatch"] is True


def test_source_audit_summary_uses_safe_prompt_field_conversion():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "recent_catalysts": [{"title": "SENT_CATALYST"}],
        "source_audit": [
            {
                "source": "recent_catalysts",
                "provider": BrokenPromptString(),
                "status": BrokenPromptString(),
                "record_count": BrokenPromptInt(),
                "cache_hit": BrokenPromptBool(),
                "stale": BrokenPromptBool(),
                "message": BrokenPromptString(),
            }
        ],
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))
    summary = payload["source_audit_summary"][0]

    assert summary["source"] == "recent_catalysts"
    assert summary["provider"] == ""
    assert summary["status"] == ""
    assert summary["record_count"] is None
    assert summary["merged_record_count"] == 1
    assert summary["record_count_mismatch"] is False
    assert summary["cache_hit"] is None
    assert summary["stale"] is None
    assert summary["message"] == ""


def test_source_audit_summary_keeps_root_source_data_mapping_when_accessor_fails():
    data = BrokenPromptSourceAuditRootGet(
        {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 123,
            "market_cap_raw": 999_999_999,
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "fixture",
                    "status": "success",
                    "record_count": 1,
                    "cache_hit": True,
                    "stale": False,
                    "message": "market data merged",
                }
            ],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data))
    summary = payload["source_audit_summary"][0]

    assert summary["source"] == "market_data"
    assert summary["provider"] == "fixture"
    assert summary["status"] == "success"
    assert summary["record_count"] == 1
    assert summary["merged_record_count"] == 2
    assert summary["record_count_mismatch"] is False
    assert summary["cache_hit"] is True
    assert summary["stale"] is False
    assert summary["message"] == "market data merged"


def test_source_audit_summary_keeps_entry_field_mapping_when_accessor_fails():
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "current_price": 123,
        "market_cap_raw": 999_999_999,
        "source_audit": [
            BrokenPromptSourceAuditEntryGet(
                {
                    "source": "market_data",
                    "provider": "fixture",
                    "status": "success",
                    "record_count": 2,
                    "cache_hit": True,
                    "stale": False,
                    "message": "market data merged",
                }
            )
        ],
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))
    summary = payload["source_audit_summary"][0]

    assert summary["source"] == "market_data"
    assert summary["provider"] == "fixture"
    assert summary["status"] == "success"
    assert summary["record_count"] == 2
    assert summary["merged_record_count"] == 2
    assert summary["record_count_mismatch"] is False
    assert summary["cache_hit"] is True
    assert summary["stale"] is False
    assert summary["message"] == "market data merged"


def test_compact_prompt_lists_preserve_items_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "recent_catalysts": BrokenPromptIterable(),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=True))

    assert payload["market_catalysts"]["items"] == [
        {"title": "SENT_COMPACT_ITEM_1"},
        {"title": "SENT_COMPACT_ITEM_2"},
    ]


def test_full_prompt_market_catalysts_preserve_items_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "recent_catalysts": BrokenPromptIterable(),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["market_catalysts"]["items"] == [
        {"title": "SENT_COMPACT_ITEM_1"},
        {"title": "SENT_COMPACT_ITEM_2"},
    ]


@pytest.mark.parametrize(
    ("compact", "expected_titles"),
    [
        (False, ["SENT_CATALYST_1", "SENT_CATALYST_2", "SENT_CATALYST_3", "SENT_CATALYST_4"]),
        (True, ["SENT_CATALYST_1", "SENT_CATALYST_2", "SENT_CATALYST_3"]),
    ],
)
def test_prompt_market_catalysts_keep_source_data_mapping_when_accessor_fails(compact, expected_titles):
    data = BrokenPromptMarketCatalystSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "recent_catalysts": [
                {"title": "SENT_CATALYST_1"},
                {"title": "SENT_CATALYST_2"},
                {"title": "SENT_CATALYST_3"},
                {"title": "SENT_CATALYST_4"},
            ],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))

    assert [item["title"] for item in payload["market_catalysts"]["items"]] == expected_titles


def test_full_prompt_dynamic_peer_metrics_preserve_items_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "dynamic_peer_metrics": BrokenPromptIterable(),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["peer_context"]["dynamic_peer_metrics"] == [
        {"title": "SENT_COMPACT_ITEM_1"},
        {"title": "SENT_COMPACT_ITEM_2"},
    ]


@pytest.mark.parametrize(
    ("compact", "expected_tickers"),
    [
        (False, ["2317.TW", "2382.TW", "4938.TW", "3231.TW", "2324.TW", "2357.TW"]),
        (True, ["2317.TW", "2382.TW", "4938.TW", "3231.TW", "2324.TW"]),
    ],
)
def test_prompt_dynamic_peer_metrics_keep_source_data_mapping_when_accessor_fails(compact, expected_tickers):
    data = BrokenPromptDynamicPeerMetricsSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "dynamic_peer_metrics": [
                {"ticker": "2317.TW"},
                {"ticker": "2382.TW"},
                {"ticker": "4938.TW"},
                {"ticker": "3231.TW"},
                {"ticker": "2324.TW"},
                {"ticker": "2357.TW"},
            ],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))

    assert [item["ticker"] for item in payload["peer_context"]["dynamic_peer_metrics"]] == expected_tickers


def test_full_prompt_peer_discovery_preserve_items_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "peer_discovery_results": BrokenPromptIterable(),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["peer_context"]["search_discovery_results"] == [
        {"title": "SENT_COMPACT_ITEM_1"},
        {"title": "SENT_COMPACT_ITEM_2"},
    ]


def test_full_prompt_peer_discovery_keeps_source_data_mapping_when_accessor_fails():
    data = BrokenPromptPeerDiscoverySourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "peer_discovery_results": [
                {"title": "SENT_PEER_1"},
                {"title": "SENT_PEER_2"},
                {"title": "SENT_PEER_3"},
                {"title": "SENT_PEER_4"},
            ],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert [item["title"] for item in payload["peer_context"]["search_discovery_results"]] == [
        "SENT_PEER_1",
        "SENT_PEER_2",
        "SENT_PEER_3",
        "SENT_PEER_4",
    ]


def test_full_prompt_monthly_revenue_preserve_items_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "recent_monthly_revenue": BrokenPromptIterable(),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["recent_monthly_revenue_text"] == [
        {"title": "SENT_COMPACT_ITEM_1"},
        {"title": "SENT_COMPACT_ITEM_2"},
    ]


@pytest.mark.parametrize(
    ("compact", "expected_months"),
    [
        (False, ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]),
        (True, ["2026-01", "2026-02", "2026-03", "2026-04"]),
    ],
)
def test_prompt_monthly_revenue_keeps_source_data_mapping_when_accessor_fails(compact, expected_months):
    data = BrokenPromptMonthlyRevenueSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "recent_monthly_revenue": [
                {"month": "2026-01"},
                {"month": "2026-02"},
                {"month": "2026-03"},
                {"month": "2026-04"},
                {"month": "2026-05"},
            ],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))

    assert [item["month"] for item in payload["recent_monthly_revenue_text"]] == expected_months


def test_full_prompt_data_quality_notes_preserve_items_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "data_source_notes": BrokenPromptNotes(),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["data_quality_notes"] == [
        "SENT_NOTE_1",
        "SENT_NOTE_2",
    ]


@pytest.mark.parametrize(
    ("compact", "expected_notes"),
    [
        (False, ["SENT_NOTE_1", "SENT_NOTE_2", "SENT_NOTE_3", "SENT_NOTE_4", "SENT_NOTE_5", "SENT_NOTE_6"]),
        (True, ["SENT_NOTE_1", "SENT_NOTE_2", "SENT_NOTE_3", "SENT_NOTE_4", "SENT_NOTE_5"]),
    ],
)
def test_prompt_data_quality_notes_keep_source_data_mapping_when_accessor_fails(compact, expected_notes):
    data = BrokenPromptDataQualityNotesSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "data_source_notes": [
                "SENT_NOTE_1",
                "SENT_NOTE_2",
                "SENT_NOTE_3",
                "SENT_NOTE_4",
                "SENT_NOTE_5",
                "SENT_NOTE_6",
            ],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))

    assert payload["data_quality_notes"] == expected_notes


def test_history_rows_preserve_years_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "years": BrokenPromptHistoryYears(),
        "revenue_history": [100, 120],
        "net_income_history": [20, 24],
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert payload["history"]["rows"][:2] == [
        {
            "year": "2024",
            "revenue_billion_twd": 100,
            "net_income_billion_twd": 20,
            "gross_profit_billion_twd": None,
            "operating_income_billion_twd": None,
            "free_cash_flow_billion_twd": None,
            "gross_margin_pct": None,
            "operating_margin_pct": None,
            "net_margin_pct": None,
            "roe_pct": None,
            "total_assets_billion_twd": None,
            "total_equity_billion_twd": None,
        },
        {
            "year": "2025",
            "revenue_billion_twd": 120,
            "net_income_billion_twd": 24,
            "gross_profit_billion_twd": None,
            "operating_income_billion_twd": None,
            "free_cash_flow_billion_twd": None,
            "gross_margin_pct": None,
            "operating_margin_pct": None,
            "net_margin_pct": None,
            "roe_pct": None,
            "total_assets_billion_twd": None,
            "total_equity_billion_twd": None,
        },
    ]


def test_history_rows_keep_source_data_mapping_when_accessor_fails():
    data = BrokenPromptRulesMapping(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "years": ["2024", "2025"],
            "revenue_history": [100, 120],
            "net_income_history": [20, 24],
        }
    )

    rows = prompt_builder._prompt_history_rows(data)

    assert rows[:2] == [
        {
            "year": "2024",
            "revenue_billion_twd": 100,
            "net_income_billion_twd": 20,
            "gross_profit_billion_twd": None,
            "operating_income_billion_twd": None,
            "free_cash_flow_billion_twd": None,
            "gross_margin_pct": None,
            "operating_margin_pct": None,
            "net_margin_pct": None,
            "roe_pct": None,
            "total_assets_billion_twd": None,
            "total_equity_billion_twd": None,
        },
        {
            "year": "2025",
            "revenue_billion_twd": 120,
            "net_income_billion_twd": 24,
            "gross_profit_billion_twd": None,
            "operating_income_billion_twd": None,
            "free_cash_flow_billion_twd": None,
            "gross_margin_pct": None,
            "operating_margin_pct": None,
            "net_margin_pct": None,
            "roe_pct": None,
            "total_assets_billion_twd": None,
            "total_equity_billion_twd": None,
        },
    ]


def test_history_rows_preserve_values_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "years": ["2024", "2025"],
        "revenue_history": BrokenPromptHistoryValues(),
        "net_income_history": [20, 24],
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))

    assert [row["revenue_billion_twd"] for row in payload["history"]["rows"]] == [100, 120]
    assert [row["net_income_billion_twd"] for row in payload["history"]["rows"]] == [20, 24]


def test_compact_pe_river_years_preserve_tail_before_iterator_failures():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "pe_river_chart": {
            "source": "fixture",
            "years": BrokenPromptPeRiverYears(),
            "multiples": [10, 11, 12, 13, 14, 15],
            "bands": {"low": [10, 11], "mid": [15, 16]},
        },
    }

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=True))
    chart = payload["local_valuation_context"]["pe_river_chart"]

    assert chart["years"] == [2021, 2022, 2023, 2024, 2025]
    assert chart["multiples"] == [10, 11, 12, 13, 14]


def test_compact_pe_river_chart_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "pe_river_chart": BrokenPromptPeRiverChart({
            "source": "fixture",
            "years": [2024, 2025],
            "multiples": [14, 15],
            "bands": {"low": [10, 11]},
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=True))
    chart = payload["local_valuation_context"]["pe_river_chart"]

    assert chart["source"] == "fixture"
    assert chart["years"] == [2024, 2025]


def test_compact_pe_river_chart_keeps_field_mapping_when_accessor_fails():
    chart = prompt_builder._compact_pe_river(
        BrokenPromptPeRiverChartGet(
            {
                "source": "fixture",
                "years": [2023, 2024, 2025],
                "multiples": [12, 13, 14],
                "bands": {"low": [10, 11], "mid": [15, 16]},
            }
        )
    )

    assert chart == {
        "source": "fixture",
        "years": [2023, 2024, 2025],
        "multiples": [12, 13, 14],
        "band_labels": ["low", "mid"],
    }


def test_full_prompt_pe_river_chart_keeps_truthiness_broken_mapping():
    data = {
        "ticker": "2892.TW",
        "company_name": "第一金",
        "pe_river_chart": BrokenPromptPeRiverChart({
            "source": "fixture",
            "years": [2024],
            "bands": {"low": [10]},
            "note": "SENT_PE_RIVER_NOTE",
        }),
    }

    payload = _payload_from_prompt(format_data_for_prompt(data))
    chart = payload["local_valuation_context"]["pe_river_chart"]

    assert chart["source"] == "fixture"
    assert chart["years"] == [2024]
    assert chart["bands"] == {"low": [10]}
    assert chart["note"] == "SENT_PE_RIVER_NOTE"


@pytest.mark.parametrize(
    ("compact", "expected_chart"),
    [
        (
            False,
            {
                "source": "fixture",
                "years": [2020, 2021, 2022, 2023, 2024, 2025],
                "multiples": [10, 11, 12, 13, 14, 15],
                "bands": {"low": [10, 11], "mid": [15, 16]},
                "note": "SENT_PE_RIVER_SOURCE",
            },
        ),
        (
            True,
            {
                "source": "fixture",
                "years": [2021, 2022, 2023, 2024, 2025],
                "multiples": [10, 11, 12, 13, 14],
                "band_labels": ["low", "mid"],
            },
        ),
    ],
)
def test_prompt_pe_river_chart_keeps_source_data_mapping_when_accessor_fails(compact, expected_chart):
    data = BrokenPromptPeRiverChartSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "pe_river_chart": {
                "source": "fixture",
                "years": [2020, 2021, 2022, 2023, 2024, 2025],
                "multiples": [10, 11, 12, 13, 14, 15],
                "bands": {"low": [10, 11], "mid": [15, 16]},
                "note": "SENT_PE_RIVER_SOURCE",
            },
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))

    assert payload["local_valuation_context"]["pe_river_chart"] == expected_chart


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_cross_checks_keep_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptCrossCheckSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "equity_multiplier_note": "SENT_DUPONT_FALLBACK_NOTE",
            "wacc_capital_structure_note": "SENT_WACC_NOTE",
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    cross_checks = payload["cross_checks"]

    assert cross_checks["dupont_identity_note"] == "SENT_DUPONT_FALLBACK_NOTE"
    assert cross_checks["wacc_capital_structure_note"] == "SENT_WACC_NOTE"


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_market_data_keeps_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptMarketDataSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "current_price": 123.4567,
            "market_cap_raw": 9_876_543_210,
            "week_52_high": 150.125,
            "week_52_low": 98.875,
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    market_data = payload["market_data"]

    assert market_data["current_price_twd"] == 123.4567
    assert market_data["market_cap_billion_twd"] == 9.8765
    assert market_data["week_52_high_twd"] == 150.125
    assert market_data["week_52_low_twd"] == 98.875


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_valuation_metrics_keep_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptValuationMetricsSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "sector": "Financial Services",
            "pe_ratio_raw": 14.5678,
            "forward_pe_raw": 12.3456,
            "pb_ratio": 1.2345,
            "ps_ratio": 2.3456,
            "ev_ebitda": 8.7654,
            "shares_raw": 1_234_567_890,
            "trailing_eps": 3.4567,
            "forward_eps": 4.5678,
            "dividend_yield_raw": 0.0625,
            "dividend_rate_raw": 2.75,
            "payout_ratio_raw": 0.5833,
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    valuation_metrics = payload["valuation_metrics"]

    assert valuation_metrics["pe_ttm"] == 14.5678
    assert valuation_metrics["forward_pe"] == 12.3456
    assert valuation_metrics["pb"] == 1.2345
    assert valuation_metrics["ps"] == 2.3456
    assert valuation_metrics["ev_ebitda"] == 8.7654
    assert valuation_metrics["shares_outstanding"] == 1_234_567_890
    assert valuation_metrics["trailing_eps_twd"] == 3.4567
    assert valuation_metrics["forward_eps_twd"] == 4.5678
    assert valuation_metrics["dividend_yield_pct"] == 6.25
    assert valuation_metrics["dividend_per_share_twd"] == 2.75
    assert valuation_metrics["payout_ratio_pct"] == 58.33
    ddm = payload["deterministic_financial_tool_results"]["calculations"]["ddm_scenarios_default"]
    assert ddm["dividend_yield_pct"] == 6.25


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_ttm_financials_keep_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptTtmFinancialsSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "shares_raw": 1_000_000_000,
            "forward_eps": 5.0,
            "revenue_ttm_raw": 100_000_000_000,
            "net_income_ttm_raw": 12_345_678_900,
            "net_income_ttm_source": "provider_calibrated",
            "ebitda_raw": 18_765_432_100,
            "gross_margin_raw": 0.4567,
            "operating_margin_raw": 0.2345,
            "profit_margin_raw": 0.1,
            "profit_margin_provider_raw": 0.0987,
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    ttm_financials = payload["ttm_financials"]

    assert ttm_financials["revenue_billion_twd"] == 100
    assert ttm_financials["net_income_billion_twd"] == 12.3457
    assert ttm_financials["net_income_source"] == "provider_calibrated"
    assert ttm_financials["ebitda_billion_twd"] == 18.7654
    assert ttm_financials["gross_margin_pct"] == 45.67
    assert ttm_financials["operating_margin_pct"] == 23.45
    assert ttm_financials["profit_margin_pct_calibrated"] == 10
    assert ttm_financials["profit_margin_pct_provider"] == 9.87
    assert payload["cross_checks"]["forward_eps_implied_revenue_billion_twd"] == 50
    assert payload["cross_checks"]["forward_eps_implied_revenue_growth_pct"] == -50


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_cash_flow_keeps_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptCashFlowSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "market_cap_raw": 100_000_000_000,
            "total_debt_raw": 20_000_000_000,
            "total_cash_raw": 5_000_000_000,
            "shares_raw": 1_000_000_000,
            "free_cash_flow_raw": 12_345_678_900,
            "operating_cash_flow_raw": 23_456_789_000,
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    cash_flow = payload["cash_flow"]

    assert cash_flow["free_cash_flow_billion_twd"] == 12.3457
    assert cash_flow["operating_cash_flow_billion_twd"] == 23.4568
    dcf = payload["deterministic_financial_tool_results"]["calculations"]["dcf_scenarios_default"]
    assert dcf["base_fcf_billion_twd"] == 12.3457


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_balance_sheet_keeps_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptBalanceSheetSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "market_cap_raw": 100_000_000_000,
            "total_debt_raw": 20_000_000_000,
            "total_cash_raw": 5_000_000_000,
            "shares_raw": 1_000_000_000,
            "free_cash_flow_raw": 12_000_000_000,
            "debt_to_equity": 42.5,
            "current_ratio": 1.2345,
            "equity_multiplier": 3.21,
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    balance_sheet = payload["balance_sheet"]

    assert balance_sheet["total_debt_billion_twd"] == 20
    assert balance_sheet["total_cash_billion_twd"] == 5
    assert balance_sheet["net_debt_billion_twd"] == 15
    assert balance_sheet["debt_to_equity_pct"] == 42.5
    assert balance_sheet["current_ratio"] == 1.2345
    assert balance_sheet["equity_multiplier"] == 3.21
    calculations = payload["deterministic_financial_tool_results"]["calculations"]
    assert calculations["market_value_wacc_default"]["total_debt_billion_twd"] == 20
    assert calculations["dcf_scenarios_default"]["scenarios"]["base"]["net_debt_billion_twd"] == 15


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_growth_keeps_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptGrowthSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "latest_annual_revenue_growth": 12.3456,
            "latest_annual_net_income_growth": -7.8912,
            "ttm_vs_latest_annual_revenue_change": 3.4567,
            "yahoo_revenue_growth": 0.1234,
            "yahoo_earnings_growth": -0.0567,
            "revenue_cagr_5yr": 8.7654,
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    growth = payload["growth"]

    assert growth["latest_annual_revenue_growth_pct"] == 12.3456
    assert growth["latest_annual_net_income_growth_pct"] == -7.8912
    assert growth["ttm_vs_latest_annual_revenue_change_pct"] == 3.4567
    assert growth["yahoo_recent_revenue_growth_pct"] == 0.1234
    assert growth["yahoo_recent_earnings_growth_pct"] == -0.0567
    assert growth["revenue_cagr_5yr_pct"] == 8.7654


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_company_metadata_keeps_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptCompanyMetadataSourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "data_schema_version": 7,
            "sector": "Financial Services",
            "industry": "Banks",
            "country": "TW",
            "employees": 8123,
            "fetch_date": "2026-07-11",
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))

    assert payload["schema_version"] == 7
    assert payload["company"]["sector"] == "Financial Services"
    assert payload["company"]["industry"] == "Banks"
    assert payload["company"]["country"] == "TW"
    assert payload["company"]["employees"] == 8123
    assert payload["company"]["fetch_date"] == "2026-07-11"


@pytest.mark.parametrize("compact", [False, True])
def test_prompt_financial_history_keeps_source_data_mapping_when_accessor_fails(compact):
    data = BrokenPromptFinancialHistorySourceGet(
        {
            "ticker": "2892.TW",
            "company_name": "第一金",
            "years": ["2024", "2025"],
            "revenue_history": [100, 121],
            "net_income_history": [20, 22],
            "fcf_history": [10, 11],
        }
    )

    payload = _payload_from_prompt(format_data_for_prompt(data, compact=compact))
    rows = payload["history"]["rows"]
    calculations = payload["deterministic_financial_tool_results"]["calculations"]

    assert [row["revenue_billion_twd"] for row in rows] == [100, 121]
    assert [row["net_income_billion_twd"] for row in rows] == [20, 22]
    assert [row["free_cash_flow_billion_twd"] for row in rows] == [10, 11]
    assert calculations["revenue_cagr"]["cagr_pct"] == 21
    assert calculations["latest_annual_revenue_growth"]["growth_pct"] == 21
    assert calculations["latest_fcf_conversion"]["fcf_conversion_pct"] == 50


def test_source_audit_summary_counts_are_derived_from_merged_payload_not_audit_claims():
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "current_price": 123,
        "market_cap_raw": 999_999_999,
        "pe_ratio_raw": 20,
        "years": ["2024", "2025"],
        "revenue_history": [100, 120],
        "net_income_history": [20, 24],
        "fcf_history": [15, 18],
        "recent_monthly_revenue": [{"month": "2026-05", "revenue": 50}],
        "institutional_trading": {"daily_total_net_buy_last_10": [{"date": "2026-07-01", "net_buy": 100}]},
        "dynamic_peer_metrics": [{"ticker": "2317.TW"}],
        "pe_river_chart": {"bands": {"low": [10, 11], "mid": [15, 16]}},
        "recent_catalysts": [{"title": "news"}],
        "global_market_context": {"items": [{"symbol": "QQQ"}]},
        "international_news_context": {"topics": [{"tag": "ai"}]},
        "macro_indicators": {"series": {"DGS10": 4.2}},
        "chip_data": {"tdcc_shareholder_distribution": {"major": 42}},
        "alternative_data": {"job_openings_104": {"job_count": 10}},
        "social_sentiment": {"ptt_stock_direct": [{"title": "討論"}]},
        "sec_edgar": {"recent_filings": [{"form": "10-Q"}]},
        "taiwan_open_data": {"rates": {"USD": {"sell": "31.50"}}},
        "earnings_call": {"period": "2026Q1", "transcript_excerpt": "guidance"},
        "peer_discovery_results": [{"title": "peer"}],
        "twse_official": {"revenue_ttm_raw": 1_000_000},
    }
    audited_sources = (
        "market_data",
        "financial_statements",
        "monthly_revenue",
        "institutional_trading",
        "dynamic_peer_metrics",
        "pe_river_chart",
        "recent_catalysts",
        "global_market_context",
        "international_news_context",
        "macro_indicators",
        "chip_data",
        "alternative_data",
        "social_sentiment",
        "sec_edgar",
        "taiwan_open_data",
        "earnings_call",
        "peer_discovery",
        "twse_official",
    )
    data["source_audit"] = [
        {"source": source, "provider": "fixture", "status": "success", "record_count": 999}
        for source in audited_sources
    ]

    payload = _payload_from_prompt(format_data_for_prompt(data))
    summary = {entry["source"]: entry for entry in payload["source_audit_summary"]}

    for source in audited_sources:
        assert summary[source]["merged_record_count"] == source_record_count(source, data), source
        assert summary[source]["merged_record_count"] > 0, source

    assert summary["recent_catalysts"]["record_count"] == 999
    assert summary["recent_catalysts"]["merged_record_count"] == 1
    assert summary["recent_catalysts"]["record_count_mismatch"] is True


def test_every_workflow_source_has_ai_visible_prompt_path():
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "current_price": 123,
        "market_cap_raw": 999_999_999,
        "revenue_ttm_raw": 1_000_000_000,
        "net_income_ttm_raw": 200_000_000,
        "free_cash_flow_raw": 150_000_000,
        "gross_margin_raw": 0.55,
        "operating_margin_raw": 0.45,
        "profit_margin_raw": 0.20,
        "years": ["2024"],
        "revenue_history": [111],
        "net_income_history": [22],
        "fcf_history": [55],
        "recent_monthly_revenue": ["SENT_monthly_revenue"],
        "institutional_trading": {"daily_total_net_buy_last_10": [{"note": "SENT_institutional"}]},
        "dynamic_peer_metrics": [{"ticker": "2317.TW", "note": "SENT_peer_metrics"}],
        "pe_river_chart": {"source": "fixture", "years": [2024], "bands": {"low": [10]}, "note": "SENT_pe_river"},
        "recent_catalysts": [{"title": "SENT_recent_catalysts", "link": "https://example.test/news"}],
        "global_market_context": {"items": [{"title": "SENT_global"}]},
        "international_news_context": {"topics": [{"headline": "SENT_international"}]},
        "macro_indicators": {"summary_text": "SENT_macro"},
        "chip_data": {"tdcc_shareholder_distribution": {"note": "SENT_chip"}},
        "alternative_data": {"job_openings_104": {"note": "SENT_alternative"}},
        "social_sentiment": {"ptt_stock_direct": [{"title": "SENT_social"}]},
        "sentiment_context": {"social_sentiment": {"ptt_stock_direct": [{"title": "SENT_social"}]}},
        "sec_edgar": {"recent_filings": [{"form": "SENT_sec"}]},
        "taiwan_open_data": {"rates": {"USD": {"sell": "SENT_taiwan_open"}}},
        "earnings_call": {"transcript_excerpt": "SENT_earnings"},
        "peer_discovery_results": [{"title": "SENT_peer_discovery"}],
        "source_audit": [
            {"source": "twse_official", "provider": "fixture", "status": "success", "record_count": 7},
        ],
    }
    expected_visibility = {
        "monthly_revenue": ("SENT_monthly_revenue", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "institutional_trading": ("SENT_institutional", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "dynamic_peer_metrics": ("SENT_peer_metrics", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "pe_river_chart": ("SENT_pe_river", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "recent_catalysts": ("SENT_recent_catalysts", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "global_market_context": ("SENT_global", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "international_news_context": ("SENT_international", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
        "macro_indicators": ("SENT_macro", {11}),
        "chip_data": ("SENT_chip", {15, 18, 23, 24}),
        "alternative_data": ("SENT_alternative", {13, 14}),
        "social_sentiment": ("SENT_social", {17}),
        "sec_edgar": ("SENT_sec", {13, 14, 21}),
        "taiwan_open_data": ("SENT_taiwan_open", {11}),
        "earnings_call": ("SENT_earnings", {20, 21}),
        "peer_discovery": ("SENT_peer_discovery", {1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}),
    }
    all_agents = sorted({agent for definition in PIPELINE_DEFINITIONS.values() for agent in definition["agents"]})
    context = {
        "analyses": {},
        "structured_outputs": {},
        "pipeline_id": "v1",
        "agent_state": initialize_agent_state(data, run_id="source-coverage-test"),
    }

    for source, (sentinel, expected_agents) in expected_visibility.items():
        visible_agents = {agent_num for agent_num in all_agents if sentinel in prompting.build_prompt(agent_num, data, context)}
        assert visible_agents == expected_agents, source

    for agent_num in all_agents:
        payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(agent_num, data)))
        assert payload["ttm_financials"]["revenue_billion_twd"] == 1
        assert payload["ttm_financials"]["gross_margin_pct"] == 55
        assert payload["cash_flow"]["free_cash_flow_billion_twd"] == 0.15


def test_build_prompt_includes_final_audit_preflight_for_non_structured_agent():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {"analyses": {}, "structured_outputs": {}, "pipeline_id": "v1"}

    prompt = prompting.build_prompt(1, data, context)

    assert "最終審核前自檢" in prompt
    assert "分析進行中" in prompt
    assert "Agent 執行失敗" in prompt
    assert "不得把同業公司事實寫成標的公司事實" in prompt
    assert "不要把自檢文字寫進正式報告" in prompt


def test_build_prompt_includes_mode_specific_final_audit_preflight_contracts():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }

    mode_c_prompt = prompting.build_prompt(
        19,
        data,
        {"analyses": {}, "structured_outputs": {}, "pipeline_id": "v3"},
    )
    mode_d_prompt = prompting.build_prompt(
        24,
        data,
        {"analyses": {}, "structured_outputs": {}, "pipeline_id": "v4"},
    )

    assert "做空觸發條件（Catalyst for crash）" in mode_c_prompt
    assert "防軋空停損點（Stop-loss level）" in mode_c_prompt
    assert "[投資建議]" in mode_c_prompt
    assert "[/投資建議]" in mode_c_prompt
    assert "trade_direction" in mode_d_prompt
    assert "Long|Short|Neutral" in mode_d_prompt
    assert "risk_level" in mode_d_prompt
    assert "High|Medium|Low" in mode_d_prompt


def test_build_prompt_stringifies_pipeline_id_before_final_audit_preflight_rule():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "pipeline_id": BrokenPromptPipelineId(),
    }

    prompt = prompting.build_prompt(19, data, context)

    assert "做空觸發條件（Catalyst for crash）" in prompt
    assert "防軋空停損點（Stop-loss level）" in prompt


def test_final_audit_preflight_rule_skips_malformed_rule_text(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "final_audit_preflight_rule": {
                "title": "最終審核前自檢",
                "intro": "SENT_FINAL_AUDIT_INTRO",
                "rules": [
                    "SENT_BASE_RULE",
                    BrokenPromptRuleText(),
                ],
                "per_agent": {
                    "19": {
                        "rules": [
                            "SENT_AGENT_RULE",
                            BrokenPromptRuleText(),
                        ],
                    }
                },
                "per_pipeline": {
                    "v3": [
                        "SENT_PIPELINE_RULE",
                        BrokenPromptRuleText(),
                    ]
                },
            }
        },
    )

    block = prompt_rules.build_final_audit_preflight_rule(19, "v3")

    assert "SENT_FINAL_AUDIT_INTRO" in block
    assert "SENT_BASE_RULE" in block
    assert "SENT_AGENT_RULE" in block
    assert "SENT_PIPELINE_RULE" in block


def test_final_audit_preflight_rule_preserves_mappings_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "final_audit_preflight_rule": BrokenPromptRulesMapping(
                {
                    "title": "SENT_FINAL_AUDIT_MAPPING_TITLE",
                    "intro": "SENT_FINAL_AUDIT_MAPPING_INTRO",
                    "rules": ["SENT_FINAL_AUDIT_MAPPING_BASE"],
                    "per_agent": BrokenPromptRulesMapping(
                        {
                            "19": {"rules": ["SENT_FINAL_AUDIT_MAPPING_AGENT"]},
                        }
                    ),
                    "per_pipeline": BrokenPromptRulesMapping(
                        {
                            "v3": ["SENT_FINAL_AUDIT_MAPPING_PIPELINE"],
                        }
                    ),
                }
            )
        },
    )

    block = prompt_rules.build_final_audit_preflight_rule(19, "v3")

    assert "SENT_FINAL_AUDIT_MAPPING_TITLE" in block
    assert "SENT_FINAL_AUDIT_MAPPING_INTRO" in block
    assert "SENT_FINAL_AUDIT_MAPPING_BASE" in block
    assert "SENT_FINAL_AUDIT_MAPPING_AGENT" in block
    assert "SENT_FINAL_AUDIT_MAPPING_PIPELINE" in block


def test_agent_rule_block_stringifies_rule_block_fields(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "numeric_tool_instructions": {
                "4": {
                    "title": BrokenPromptRuleBlockText("SENT_RULE_TITLE"),
                    "intro": BrokenPromptRuleBlockText("SENT_RULE_INTRO"),
                    "schema_lines": [
                        "SENT_SCHEMA_LINE",
                        BrokenPromptRuleText(),
                    ],
                    "rules": [
                        "SENT_RULE_LINE",
                        BrokenPromptRuleText(),
                    ],
                }
            }
        },
    )

    block = prompt_rules.build_agent_rule_block("numeric_tool_instructions", 4)

    assert "SENT_RULE_TITLE" in block
    assert "SENT_RULE_INTRO" in block
    assert "SENT_SCHEMA_LINE" in block
    assert "SENT_RULE_LINE" in block


def test_agent_rule_block_preserves_config_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "numeric_tool_instructions": {
                "4": BrokenPromptRulesMapping(
                    {
                        "title": "SENT_AGENT_CONFIG_TITLE",
                        "intro": "SENT_AGENT_CONFIG_INTRO",
                        "schema_lines": ["SENT_AGENT_CONFIG_SCHEMA"],
                        "rules": ["SENT_AGENT_CONFIG_RULE"],
                    }
                )
            }
        },
    )

    block = prompt_rules.build_agent_rule_block("numeric_tool_instructions", 4)

    assert "SENT_AGENT_CONFIG_TITLE" in block
    assert "SENT_AGENT_CONFIG_INTRO" in block
    assert "SENT_AGENT_CONFIG_SCHEMA" in block
    assert "SENT_AGENT_CONFIG_RULE" in block


def test_agent_rule_block_preserves_rule_list_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "numeric_tool_instructions": {
                "4": {
                    "title": "SENT_AGENT_RULE_LIST_TITLE",
                    "rules": BrokenPromptRulesMapping(
                        {
                            "rules": [
                                "SENT_AGENT_RULE_LIST_RULE",
                                BrokenPromptRuleText(),
                            ]
                        }
                    ),
                }
            }
        },
    )

    block = prompt_rules.build_agent_rule_block("numeric_tool_instructions", 4)

    assert "SENT_AGENT_RULE_LIST_TITLE" in block
    assert "SENT_AGENT_RULE_LIST_RULE" in block


def test_agent_rule_block_preserves_section_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "numeric_tool_instructions": BrokenPromptRulesMapping(
                {
                    "4": {
                        "title": "SENT_AGENT_SECTION_TITLE",
                        "intro": "SENT_AGENT_SECTION_INTRO",
                        "rules": ["SENT_AGENT_SECTION_RULE"],
                    }
                }
            )
        },
    )

    block = prompt_rules.build_agent_rule_block("numeric_tool_instructions", 4)

    assert "SENT_AGENT_SECTION_TITLE" in block
    assert "SENT_AGENT_SECTION_INTRO" in block
    assert "SENT_AGENT_SECTION_RULE" in block


def test_structured_agent_instructions_preserve_mapping_items_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "structured_agent_instructions": BrokenPromptRulesMapping(
                {
                    "3": {
                        "title": "SENT_STRUCTURED_TITLE",
                        "intro": "SENT_STRUCTURED_INTRO",
                        "rules": ["SENT_STRUCTURED_RULE"],
                    }
                }
            )
        },
    )

    instructions = prompt_rules.build_structured_agent_instructions()

    assert 3 in instructions
    assert "SENT_STRUCTURED_TITLE" in instructions[3]
    assert "SENT_STRUCTURED_INTRO" in instructions[3]
    assert "SENT_STRUCTURED_RULE" in instructions[3]


def test_output_cleanliness_rule_skips_malformed_rule_text(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "output_cleanliness_rule": {
                "title": "SENT_OUTPUT_CLEANLINESS_TITLE",
                "rules": [
                    "SENT_OUTPUT_CLEANLINESS_RULE",
                    BrokenPromptRuleText(),
                ],
            }
        },
    )

    block = prompt_rules.build_output_cleanliness_rule()

    assert "SENT_OUTPUT_CLEANLINESS_TITLE" in block
    assert "SENT_OUTPUT_CLEANLINESS_RULE" in block


def test_output_cleanliness_rule_preserves_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "output_cleanliness_rule": BrokenPromptRulesMapping(
                {
                    "title": "SENT_OUTPUT_CLEANLINESS_MAPPING_TITLE",
                    "rules": ["SENT_OUTPUT_CLEANLINESS_MAPPING_RULE"],
                }
            )
        },
    )

    block = prompt_rules.build_output_cleanliness_rule()

    assert "SENT_OUTPUT_CLEANLINESS_MAPPING_TITLE" in block
    assert "SENT_OUTPUT_CLEANLINESS_MAPPING_RULE" in block


def test_output_cleanliness_rule_preserves_top_level_mapping_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: BrokenPromptRulesMapping(
            {
                "output_cleanliness_rule": {
                    "title": "SENT_TOP_LEVEL_RULES_TITLE",
                    "rules": ["SENT_TOP_LEVEL_RULES_RULE"],
                }
            }
        ),
    )

    block = prompt_rules.build_output_cleanliness_rule()

    assert "SENT_TOP_LEVEL_RULES_TITLE" in block
    assert "SENT_TOP_LEVEL_RULES_RULE" in block


def test_assistant_task_prompt_helpers_stringify_and_skip_malformed_text(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "assistant_task_prompts": {
                "tear_sheet": {
                    "system_instruction": BrokenPromptRuleBlockText("SENT_TASK_SYSTEM"),
                    "instruction_lines": [
                        "SENT_TASK_LINE",
                        BrokenPromptRuleText(),
                    ],
                }
            }
        },
    )

    system_instruction = prompt_rules.get_task_system_instruction("tear_sheet", "DEFAULT_TASK_SYSTEM")
    instruction_lines = prompt_rules.get_task_instruction_lines("tear_sheet")

    assert system_instruction == "SENT_TASK_SYSTEM"
    assert instruction_lines == ["SENT_TASK_LINE"]


def test_assistant_task_prompt_helpers_preserve_mappings_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompt_rules,
        "load_runtime_prompt_rules",
        lambda: {
            "assistant_task_prompts": BrokenPromptRulesMapping(
                {
                    "tear_sheet": BrokenPromptRulesMapping(
                        {
                            "system_instruction": BrokenPromptRuleBlockText("SENT_TASK_MAPPING_SYSTEM"),
                            "instruction_lines": [
                                "SENT_TASK_MAPPING_LINE",
                                BrokenPromptRuleText(),
                            ],
                        }
                    )
                }
            )
        },
    )

    system_instruction = prompt_rules.get_task_system_instruction("tear_sheet", "DEFAULT_TASK_SYSTEM")
    instruction_lines = prompt_rules.get_task_instruction_lines("tear_sheet")

    assert system_instruction == "SENT_TASK_MAPPING_SYSTEM"
    assert instruction_lines == ["SENT_TASK_MAPPING_LINE"]


def test_build_prompt_keeps_truthiness_broken_rag_context_mapping():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "rag_context": BrokenPromptRagContext({4: "SENT_RAG_CONTEXT"}),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert "SENT_RAG_CONTEXT" in prompt


def test_build_prompt_stringifies_rag_context_before_compact_length_check():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "rag_context": {4: BrokenPromptRagText()},
        "_primary_probe_prompt": True,
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert "SENT_RAG_TEXT" in prompt


def test_build_prompt_stringifies_temporal_memory_reflection_prompt():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "temporal_memory": {
            "reflection_prompt": BrokenPromptTemporalReflection(),
            "backtests": [{"summary": "SENT_BACKTEST_SUMMARY"}],
        },
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(7, data, context)

    assert "SENT_TEMPORAL_REFLECTION" in prompt
    assert "SENT_BACKTEST_SUMMARY" in prompt


def test_build_prompt_preserves_temporal_memory_backtests_before_iterator_failure():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "temporal_memory": {
            "reflection_prompt": "SENT_TEMPORAL_REFLECTION",
            "backtests": BrokenPromptTemporalBacktests(),
        },
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(7, data, context)

    assert "SENT_BACKTEST_SUMMARY_1" in prompt
    assert "SENT_BACKTEST_SUMMARY_2" in prompt


def test_build_prompt_stringifies_non_json_state_view_values(monkeypatch):
    monkeypatch.setattr(
        prompting,
        "state_view_for",
        lambda _agent_num, _state: {
            "valid_path": "SENT_STATE_VIEW_OK",
            "nested": {"broken_leaf": BrokenPromptStateViewValue()},
        },
    )
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "agent_state": object(),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert "SENT_STATE_VIEW_OK" in prompt
    assert "SENT_STATE_VIEW_VALUE" in prompt


def test_build_prompt_preserves_state_view_dict_items_when_accessor_fails(monkeypatch):
    monkeypatch.setattr(
        prompting,
        "state_view_for",
        lambda _agent_num, _state: BrokenPromptStateViewItems(
            {
                "valid_path": "SENT_STATE_VIEW_DICT_ITEM",
                "nested": {"valid_leaf": "SENT_STATE_VIEW_DICT_LEAF"},
            }
        ),
    )
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "agent_state": object(),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert "SENT_STATE_VIEW_DICT_ITEM" in prompt
    assert "SENT_STATE_VIEW_DICT_LEAF" in prompt


def test_build_prompt_preserves_state_view_list_items_when_iterator_fails(monkeypatch):
    monkeypatch.setattr(
        prompting,
        "state_view_for",
        lambda _agent_num, _state: {
            "valid_sequence": BrokenPromptStateViewList(
                [
                    "SENT_STATE_VIEW_LIST_ITEM",
                    {"valid_leaf": "SENT_STATE_VIEW_LIST_LEAF"},
                ]
            ),
        },
    )
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "agent_state": object(),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert '"valid_sequence": [' in prompt
    assert '"SENT_STATE_VIEW_LIST_ITEM"' in prompt
    assert '"valid_leaf": "SENT_STATE_VIEW_LIST_LEAF"' in prompt


def test_build_prompt_preserves_state_view_set_items_when_iterator_fails(monkeypatch):
    monkeypatch.setattr(
        prompting,
        "state_view_for",
        lambda _agent_num, _state: {
            "valid_collection": BrokenPromptStateViewSet(
                {
                    "SENT_STATE_VIEW_SET_ITEM",
                    "SENT_STATE_VIEW_SET_LEAF",
                }
            ),
        },
    )
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "agent_state": object(),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert '"valid_collection": [' in prompt
    assert '"SENT_STATE_VIEW_SET_ITEM"' in prompt
    assert '"SENT_STATE_VIEW_SET_LEAF"' in prompt


def test_build_prompt_falls_back_when_primary_probe_flag_truthiness_fails():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "recent_catalysts": ["SENT_PRIMARY_PROBE_FLAG_CONTEXT"],
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "_primary_probe_prompt": BrokenPromptPrimaryProbeFlag(),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert "SENT_PRIMARY_PROBE_FLAG_CONTEXT" in prompt
    assert "RAG 片段截斷" not in prompt


def test_build_prompt_stringifies_forensic_warning_before_truthiness_check():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "_v2_forensic_warning": BrokenPromptForensicWarning(),
        "pipeline_id": "v2",
    }

    prompt = prompting.build_prompt(14, data, context)

    assert "財務排雷品質警示" in prompt
    assert "SENT_FORENSIC_WARNING" in prompt


def test_build_prompt_stringifies_runtime_instruction_fields_before_prompt_part_filter():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {
        "analyses": {},
        "structured_outputs": {},
        "_identity_retry_instruction": BrokenPromptRuntimeInstruction("SENT_IDENTITY_RETRY_INSTRUCTION"),
        "_audit_reflection_instruction": BrokenPromptRuntimeInstruction("SENT_AUDIT_REFLECTION_INSTRUCTION"),
        "_audit_retry_instruction": BrokenPromptRuntimeInstruction("SENT_AUDIT_RETRY_INSTRUCTION"),
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert "SENT_IDENTITY_RETRY_INSTRUCTION" in prompt
    assert "SENT_AUDIT_REFLECTION_INSTRUCTION" in prompt
    assert "SENT_AUDIT_RETRY_INSTRUCTION" in prompt


def test_build_prompt_applies_token_budget_guard_before_llm_call(monkeypatch):
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _agent_num: 700, raising=False)
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "recent_catalysts": ["大型新聞段落 " * 80 for _ in range(20)],
        "dynamic_peer_metrics": [{"note": "同業補充 " * 120} for _ in range(10)],
    }
    context = {
        "analyses": {1: "前序分析重要片段 " * 1200},
        "structured_outputs": {},
        "rag_context": {4: "RAG 補充片段 " * 1200},
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert estimate_text_tokens(prompt) <= 700
    assert "Prompt budget guard" in prompt
    assert prompt.count("RAG 補充片段") < 100


def test_runtime_rules_cover_common_final_audit_failure_modes():
    rules = json.loads((ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8"))

    preflight = rules["final_audit_preflight_rule"]
    common_text = "\n".join(preflight["rules"])
    assert "分析進行中" in common_text
    assert "prompt/system/task/meta-talk" in common_text
    assert "同業公司事實" in common_text

    structured_rules = rules["structured_agent_instructions"]
    for agent_num in ("4", "14"):
        valuation_text = "\n".join(structured_rules[agent_num]["rules"])
        assert "熊市情境 <= 基本情境 <= 牛市情境" in valuation_text
    for agent_num in ("7", "16"):
        recommendation_text = "\n".join(structured_rules[agent_num]["rules"])
        assert "短期目標（3個月）" in recommendation_text
        assert "建議只能使用 schema 允許值" in recommendation_text

    mode_c_text = "\n".join(structured_rules["19"]["rules"])
    assert "做空觸發條件（Catalyst for crash）" in mode_c_text
    assert "[/投資建議] 後" in mode_c_text

    mode_d_text = "\n".join(structured_rules["24"]["rules"])
    assert "只有六個欄位" in mode_d_text
    assert "Neutral + High" in mode_d_text
