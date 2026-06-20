import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_quant_engine_emits_three_ordered_dcf_scenarios():
    from quant_engine import QuantEngine

    result = QuantEngine.compute_all({
        "current_price": 90,
        "shares_outstanding": 100,
        "total_equity": 1_000,
        "total_debt": 200,
        "tax_rate": 0.2,
        "free_cash_flows": [100, 110, 121, 133.1, 146.41],
    })

    scenarios = result["dcf_scenarios"]
    assert set(scenarios) == {"bear", "base", "bull"}
    assert scenarios["bear"]["intrinsic_value"] < scenarios["base"]["intrinsic_value"]
    assert scenarios["base"]["intrinsic_value"] < scenarios["bull"]["intrinsic_value"]
    assert scenarios["bull"]["wacc"] < scenarios["base"]["wacc"] < scenarios["bear"]["wacc"]
    assert result["dcf_intrinsic_value"] == scenarios["base"]["intrinsic_value"]


def test_dcf_audit_compares_matching_scenario_prices():
    from final_audit_dcf import dcf_conflict_warnings

    analyses = {4: "## DCF 情境\n[目標股價]\n熊市情境: NT$80\n基本情境: NT$100\n牛市情境: NT$120\n[/目標股價]"}
    data = {
        "quant_metrics": {
            "dcf_scenarios": {
                "bear": {"intrinsic_value": 80},
                "base": {"intrinsic_value": 100},
                "bull": {"intrinsic_value": 200},
            }
        }
    }

    warnings = dcf_conflict_warnings(analyses, data)

    assert len(warnings) == 1
    assert "牛市情境" in warnings[0]
    assert "NT$120" in warnings[0]
    assert "NT$200" in warnings[0]


def test_financial_tool_scenarios_apply_margin_bias_to_base_fcf():
    from financial_tools import build_financial_tool_context

    context = build_financial_tool_context({
        "revenue_history": [100, 110],
        "net_income_history": [10, 11],
        "fcf_history": [8, 10],
        "free_cash_flow_raw": 10_000_000_000,
        "market_cap_raw": 100_000_000_000,
        "total_debt_raw": 20_000_000_000,
        "total_cash_raw": 0,
        "shares_raw": 100_000_000,
    })

    scenarios = context["calculations"]["dcf_scenarios_default"]["scenarios"]
    assert scenarios["bear"]["base_fcf_billion_twd"] == 8
    assert scenarios["base"]["base_fcf_billion_twd"] == 10
    assert scenarios["bull"]["base_fcf_billion_twd"] == 12


def test_earnings_call_fetcher_parses_latest_fmp_transcript(monkeypatch):
    import data_fetch.earnings_call_fetcher as fetcher

    monkeypatch.setattr(fetcher, "FMP_API_KEY", "test-key")
    monkeypatch.setattr(
        fetcher,
        "_sync_json_get",
        lambda *_args, **_kwargs: [{
            "symbol": "NVDA",
            "date": "2026-05-20",
            "quarter": 1,
            "year": 2026,
            "content": "Demand remains strong. We are increasing AI investment while monitoring supply constraints.",
        }],
    )

    result = fetcher.fetch_latest_earnings_call("NVDA")

    assert result["ticker"] == "NVDA"
    assert result["period"] == "2026Q1"
    assert "AI investment" in result["transcript_excerpt"]
    assert result["source"] == "FMP earnings call transcript"


def test_sentiment_and_bear_agents_write_structured_state_metadata():
    from agent_state import AgentState
    from agent_runtime.bear_advocate_agent import BearAdvocateAgent
    from agent_runtime.sentiment_analysis_agent import SentimentAnalysisAgent
    from state_memory import merge_agent_report, state_view_for

    state = AgentState(run_id="run-1", ticker="2308.TW", company_name="台達電")
    state.normalized_financials["earnings_call"] = {
        "period": "2026Q1",
        "transcript_excerpt": "AI demand remains strong, but supply constraints persist.",
    }
    sentiment_report = SentimentAnalysisAgent.build_report({
        "guidance_tone": "樂觀",
        "confidence": 0.82,
        "highlights": [
            {"keyword": "AI 投資", "quote": "AI demand remains strong"},
            {"keyword": "供應鏈", "quote": "supply constraints persist"},
            {"keyword": "展望", "quote": "guidance was raised"},
        ],
        "analysis_markdown": "管理層語氣偏樂觀。",
    })
    merge_agent_report(state, sentiment_report)
    bear_report = BearAdvocateAgent.build_report({
        "thesis_summary": "估值已反映過多成長。",
        "downside_risks": [
            {"title": "估值過高", "evidence": "P/E 高於同業", "severity": "high"},
            {"title": "客戶集中", "evidence": "前三大客戶集中", "severity": "high"},
            {"title": "供應風險", "evidence": "關鍵零件短缺", "severity": "warning"},
        ],
        "analysis_markdown": "空頭觀點。",
    })
    merge_agent_report(state, bear_report)

    sentiment_view = state_view_for(20, state)
    bear_view = state_view_for(21, state)
    assert sentiment_view["earnings_call_context"]["period"] == "2026Q1"
    assert sentiment_report.extracted_facts["guidance_tone"] == "樂觀"
    assert len(bear_report.risk_flags) == 3
    assert "20" in bear_view["agent_reports"]


def test_peer_metrics_include_dupont_inputs_and_ps(monkeypatch):
    import data_fetch.market_sources.peers as peer_sources
    from financial_tools import calculate_dupont

    class FakeTicker:
        def __init__(self, _ticker):
            self.info = {
                "grossMargins": 0.38,
                "operatingMargins": 0.21,
                "profitMargins": 0.16,
                "returnOnEquity": 0.24,
                "totalRevenue": 600,
                "totalAssets": 1_000,
                "trailingPE": 28.0,
                "priceToBook": 5.0,
                "priceToSalesTrailing12Months": 4.2,
            }

    monkeypatch.setattr(peer_sources.yf, "Ticker", FakeTicker)
    identity = {"same_industry_peers": [{"stock_id": "2357", "stock_name": "華碩"}]}

    records = peer_sources.fetch_dynamic_peer_metrics("2308.TW", "台達電", "Technology", "Hardware", identity)
    dupont = calculate_dupont(net_margin_pct=16, asset_turnover=0.6, equity_multiplier=2.5)

    assert records[0]["roe_pct"] == 24.0
    assert records[0]["asset_turnover"] == 0.6
    assert records[0]["ps_ttm"] == 4.2
    assert dupont["roe_pct"] == 24.0


def test_peer_agents_can_call_dupont_tool():
    from agent_runtime.routing import get_agent_function_tools

    for agent_num in (3, 12, 13, 18):
        tool_names = {tool.__name__ for tool in get_agent_function_tools(agent_num)}
        assert "calculate_dupont" in tool_names


def test_pipeline_places_sentiment_and_bear_agents_before_final_decision():
    from pipeline_modes import PIPELINE_DEFINITIONS

    for definition in PIPELINE_DEFINITIONS.values():
        if "recommendation" not in definition["structured_agents"]:
            continue
        agents = definition["agents"]
        final_agent = definition["structured_agents"]["recommendation"]
        assert 20 in agents
        assert 21 in agents
        assert agents.index(20) < agents.index(21) < agents.index(final_agent)


def test_final_decision_prompts_must_answer_bear_agent_findings():
    from prompt_loader import load_agent_prompt_config

    config = load_agent_prompt_config()
    for agent_num in (7, 16, 19):
        combined = "\n".join([
            config["system_prompts"][str(agent_num)],
            config["analysis_prompts"][str(agent_num)],
        ])
        assert "Agent 21" in combined
        assert "逐項回應" in combined


def test_report_renders_dcf_sentiment_peer_and_downside_sections():
    from reporting.html_renderer import generate_html_report

    context = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2308.TW",
            "company_name": "台達電",
            "fetch_date": "2026年06月20日",
            "current_price": 100,
            "current_price_fmt": "NT$100",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
            "quant_metrics": {
                "dcf_scenarios": {
                    "bear": {"intrinsic_value": 80, "growth_bias_pct": -20, "wacc": 0.10},
                    "base": {"intrinsic_value": 110, "growth_bias_pct": 0, "wacc": 0.09},
                    "bull": {"intrinsic_value": 150, "growth_bias_pct": 20, "wacc": 0.08},
                }
            },
            "dynamic_peer_metrics": [{
                "name": "Eaton", "ticker": "ETN", "gross_margin_pct": 38,
                "roe_pct": 24, "asset_turnover": 0.6, "pe_ttm": 28, "ps_ttm": 4.2,
            }],
        },
        "analyses": {20: "管理層語氣偏樂觀。", 21: "空頭觀點。"},
        "structured_outputs": {
            20: {
                "guidance_tone": "樂觀",
                "confidence": 0.82,
                "highlights": [{"keyword": "AI 投資", "quote": "AI demand remains strong"}],
            },
            21: {
                "thesis_summary": "估值已反映過多成長。",
                "downside_risks": [{"title": "估值過高", "evidence": "P/E 高於同業", "severity": "high"}],
            },
        },
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {"熊市情境": 80, "基本情境": 110, "牛市情境": 150},
            "moat_scores": {},
        },
        "total_time": 1,
    }

    html = generate_html_report(context)

    assert "DCF 動態情境矩陣" in html
    assert "管理層語氣與法說會亮點" in html
    assert "同業競爭力對比" in html
    assert "最大下行風險" in html
    assert "估值過高" in html
