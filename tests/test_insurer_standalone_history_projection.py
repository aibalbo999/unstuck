"""No-subsidiary insurer filings retain standalone scope through annual inputs."""
import copy
import json
from pathlib import Path
import pytest

FIXTURE = Path(__file__).parent / "fixtures/source_acquisition/insurer_standalone_2851_20261009.json"

def statement():
    return json.loads(FIXTURE.read_text())

class NoAnnualSdk:
    @property
    def financials(self):
        pytest.fail("verified standalone annual filings must not call the annual SDK")
    cashflow = financials
    balance_sheet = financials

@pytest.mark.parametrize("change",["none","missing","duplicate","instant","unbound","other_issuer","other_period","with_subsidiaries"])
def test_public_fetch_classifies_only_issuer_bound_no_subsidiary_notes(monkeypatch,change):
    from data_fetch.market_sources import financial_institution_xbrl as source
    from test_official_insurer_individual_xbrl import insurer_filing
    def request(_client, method, url, **_kwargs):
        if method == "POST":
            return b"index"
        year = int(url.rsplit("/",1)[1])
        raw = insurer_filing(year)
        note = ('<ix:nonNumeric name="tifrs-notes:BasisOfPreparation" contextRef="duration">'
                '1.本公司並無子公司，故本財務報告係個別財務報告，由資產負債表、'
                '綜合損益表、權益變動表及現金流量表組成。</ix:nonNumeric>')
        if year==2023:
            if change=="missing":note=""
            elif change=="duplicate":note+=note
            elif change=="instant":note=note.replace('contextRef="duration"','contextRef="instant"')
            elif change=="unbound":note=note.replace('name="tifrs-notes:BasisOfPreparation"','name="other:BasisOfPreparation"')
            elif change in {"other_issuer","other_period"}:
                foreign=insurer_filing(year if change=="other_issuer" else year-1,issuer="2882" if change=="other_issuer" else "2851")
                import re
                ctx=re.search(rb'<xbrli:context id="duration">.*?</xbrli:context>',foreign,re.S)[0].decode().replace('id="duration"','id="other"')
                note=ctx+note.replace('contextRef="duration"','contextRef="other"')
            elif change=="with_subsidiaries":note=note.replace("並無子公司","有子公司").replace("個別財務報告","個體財務報告")
        return raw.replace(b"</html>",note.encode()+b"</html>")
    monkeypatch.setattr(source, "_filing_urls", lambda _r,_i,report_id="C":
                        {} if report_id=="C" else {y:f"https://mopsov.twse.com.tw/filing/{y}" for y in range(2021,2026)})
    monkeypatch.setattr(source,"_bounded_request",request)
    result = source.fetch_financial_institution_histories("2851.TW",client=object())
    if change=="none":
        assert result["schema"] == "insurer_standalone.v1"
        assert result["report_scope"] == "standalone"
        assert all(d["standalone_scope_evidence"]["issuer"]=="2851" for d in result["documents"])
    else:
        assert result["schema"]=="insurer_individual.v1"
        assert result["report_scope"]=="individual"

def test_complete_standalone_public_extractor_avoids_sdk_and_keeps_scope(monkeypatch):
    from data_fetch import yfinance_extractors as source
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK","0")
    monkeypatch.setattr(source,"fetch_financial_institution_histories",lambda _t:statement())
    monkeypatch.setattr(source,"fetch_finmind_financial_statement_fallback",
                        lambda *a,**k:pytest.fail("redundant FinMind annual fallback"))
    result=source.extract_financial_histories(NoAnnualSdk(),"2851.TW",[],industry_context="金融保險")
    assert result["years"]==["2021","2022","2023","2024","2025"]
    assert result["revenue_history"][-1]==22.898381
    assert result["net_income_history"][-1]==2.932619
    assert result["gross_profit_history"]==result["operating_income_history"]==[None]*5
    assert result["financial_history_basis"]["report_scope"]=="standalone"
    assert result["financial_history_basis"]["field_sources"]["net_income_history"]["fact"]=="ifrs-full:ProfitLoss"
    assert result["sector_specific_financial_audit"]["report_scope"]=="standalone"
    assert result["primary_financial_audit"] is result["finmind_financial_fallback_audit"] is None

def data_from_projection():
    from data_fetch.financial_history_basis import project_insurer_standalone_histories
    raw=statement()
    projected=project_insurer_standalone_histories(raw,"2851.TW")
    assert projected is not None
    return {"ticker":"2851.TW","company_name":"中央再保險股份有限公司","financial_currency":"TWD",
            "sector":"Financial Services","industry":"Insurance - Reinsurance",
            "sector_specific_financials":raw,**projected}

def test_standalone_prompt_chart_and_capital_notes_keep_insurer_scope():
    from prompt_builder_helpers import _prompt_financial_institution_history
    from data_fetch.yfinance_capital_notes import build_capital_structure_notes
    from reporting.html_chart_context import build_html_chart_context
    from prompt_builder import format_data_for_prompt
    data=data_from_projection()
    prompt=_prompt_financial_institution_history(data)
    assert prompt["schema"]=="insurer_standalone.v1"
    assert prompt["report_scope"]=="standalone"
    assert "no_subsidiaries" in prompt["basis_note"]
    encoded=format_data_for_prompt(data)
    assert "保險業個別營業收入" in encoded and "保險業個別本期損益" in encoded
    chart=build_html_chart_context(data,{})
    assert chart["chart_data"]["incomeLabel"]=="保險業個別營業收入"
    assert chart["chart_data"]["netIncomeLabel"]=="個別本期損益"
    assert chart["financial_history_chart_title"]=="年度保險業個別營業收入與本期損益（億元台幣）"
    notes=build_capital_structure_notes(NoAnnualSdk(),{},
        **{k:data[k] for k in ("revenue_history","net_income_history","total_assets_history","total_equity_history")},
        market_cap=1e12,total_debt=1e11,financial_history_data=data)
    assert "個別" in notes["equity_multiplier_note"]
    assert "本期損益" in notes["dupont_identity_note"]
    assert "母公司" not in notes["dupont_identity_note"]
    assert "合併" not in notes["equity_multiplier_note"]

@pytest.mark.parametrize("change",["none","array_mismatch","missing_basis","broken_receipt"])
def test_insurer_statement_fcf_cannot_enable_general_industry_dcf(change):
    from financial_tools import build_financial_tool_context
    data={**data_from_projection(),"current_price":30,"market_cap_raw":1e10,
          "total_debt_raw":0,"total_cash_raw":0,"shares_raw":1e9,"trailing_eps":2,
          "free_cash_flow_raw":2e9}
    if change=="array_mismatch": data["fcf_history"][-1]+=1
    elif change=="missing_basis": data.pop("financial_history_basis")
    elif change=="broken_receipt": data["sector_specific_financials"]["documents"][0].pop("sha256")
    metrics=build_financial_tool_context(data)
    assert metrics["metric_status"]["dcf"]["status"]=="unavailable"
    assert any("insurer_standalone" in reason for reason in metrics["metric_status"]["dcf"]["reason_codes"])
    assert not metrics.get("dcf_scenarios")

@pytest.mark.parametrize("change",["ticker","individual","scope_note_missing","scope_note_parent","scope_note_year",
   "scope_note_issuer","scope_note_hash","scope_fact","document_scope","document_issuer","document_report",
   "duplicate_document_year","missing_hash","missing_fact","bad_fcf","bool_value","positive_capex"])
def test_invalid_standalone_receipt_keeps_projection_unverified(change):
    from data_fetch.financial_history_basis import project_insurer_standalone_histories
    raw=statement();d=raw["documents"][0];e=d["standalone_scope_evidence"]
    if change=="ticker":raw["ticker"]="2882.TW"
    elif change=="individual":raw["schema"]="insurer_individual.v1"
    elif change=="scope_note_missing":d.pop("standalone_scope_evidence")
    elif change=="scope_note_parent":e["text"]="本公司有子公司，故本財務報告係個體財務報告"
    elif change=="scope_note_year":e["year"]=2024
    elif change=="scope_note_issuer":e["issuer"]="2882"
    elif change=="scope_note_hash":e["document_sha256"]="a"*64
    elif change=="scope_fact":e["fact"]="other:BasisOfPreparation"
    elif change=="document_scope":d["report_scope"]="individual"
    elif change=="document_issuer":d["url"]=d["url"].replace("co_id=2851","co_id=2882")
    elif change=="document_report":d["url"]=d["url"].replace("report_id=A","report_id=C")
    elif change=="duplicate_document_year":raw["documents"][1]=copy.deepcopy(d)
    elif change=="missing_hash":d.pop("sha256")
    elif change=="missing_fact":raw["raw_twd_by_year"]["2021"].pop("insurance_operating_revenue")
    elif change=="bad_fcf":raw["raw_twd_by_year"]["2021"]["free_cash_flow"]+=1
    elif change=="bool_value":raw["raw_twd_by_year"]["2021"]["assets"]=True
    elif change=="positive_capex":raw["raw_twd_by_year"]["2021"]["intangible_purchase"]=1
    assert project_insurer_standalone_histories(raw,"2851.TW") is None

def test_invalid_standalone_proof_is_not_labeled_verified_in_the_prompt():
    from prompt_builder_helpers import _prompt_financial_institution_history
    data=data_from_projection()
    data["sector_specific_financials"]["documents"][0].pop("standalone_scope_evidence")
    assert _prompt_financial_institution_history(data)=={}

def test_insurer_amount_check_rejects_group_scope_and_checks_only_target_issuer():
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection()
    assert financial_money_claim_issues("2851 2025 年個別營業收入為 228.98 億元。",data)==[]
    assert financial_money_claim_issues("2851 2025 年個別營業收入為 22.898 億元。",data)
    assert financial_money_claim_issues("2851 2025 年合併營業收入為 228.98 億元。",data)
    assert financial_money_claim_issues("2025 年國泰金營收為 100 億元。",data)==[]
    assert financial_money_claim_issues("2025 年其他保險公司淨利為 10 億元。",data)==[]
    damaged=copy.deepcopy(data)
    damaged["revenue_history"][-1]+=1
    assert financial_money_claim_issues("2851 2025 年個別營業收入為 22.898 億元。",damaged)==[]

def test_unverified_standalone_extractor_keeps_sdk_fallback_and_degraded_receipt(monkeypatch):
    from data_fetch import yfinance_extractors as source
    from test_financial_statement_observation import StatementStock
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK","1")
    baseline=source.extract_financial_histories(StatementStock(),"2851.TW",[],data_loader_cls=None,industry_context="金融保險")
    raw=statement();raw["documents"][0].pop("standalone_scope_evidence")
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK","0")
    monkeypatch.setattr(source,"fetch_financial_institution_histories",lambda _t:raw)
    result=source.extract_financial_histories(StatementStock(),"2851.TW",[],data_loader_cls=None,industry_context="金融保險")
    assert result["revenue_history"]==baseline["revenue_history"]
    assert result["sector_specific_financials"] is None
    assert result["sector_specific_financial_audit"]["status"]=="degraded_enrichment"
    assert result["sector_specific_financial_audit"]["record_count"]==0

def test_standalone_client_chart_and_rendered_report_use_exact_scope_labels():
    import shutil,subprocess
    from bs4 import BeautifulSoup
    from reporting.html_chart_context import build_html_chart_context
    from reporting.html_renderer import generate_html_report
    from state_memory import initialize_agent_state,state_view_for
    data=data_from_projection()
    view=state_view_for("valuation",initialize_agent_state(data))["normalized_financials"]
    assert view["financial_history_basis"]["report_scope"]=="standalone"
    assert view["revenue_history"]==data["revenue_history"]
    html=generate_html_report({"ticker":"2851.TW","data":data,"pipeline_id":"v1","final_report":"資料來源驗證。"})
    soup=BeautifulSoup(html,"html.parser")
    payload=json.loads(soup.select_one("#report-chart-data").string)
    assert payload["netIncomeLabel"]=="個別本期損益"
    assert "年度保險業個別營業收入與本期損益（億元台幣）" in soup.get_text()
    node=shutil.which("node")
    assert node is not None, "Node required for chart behavior verification"
    templates=Path(__file__).parents[1]/"backend/templates/includes/charts"
    runtime=(templates/"runtime.html.j2").read_text().split("window.StockAgentReportTraceability",1)[0]
    financial=(templates/"financial.html.j2").read_text()
    script="""
const fs=require('fs'),vm=require('vm');const d=JSON.parse(fs.readFileSync(0,'utf8'));
const configurations=[];
const document={getElementById:id=>id==='report-chart-data'?{textContent:JSON.stringify(d.payload)}:
    ['revenueChart','marginChart','fcfChart','roeChart'].includes(id)?{getContext:()=>id}:null};
const sandbox={document,Chart:function(id,c){configurations.push({id,datasets:c.data.datasets});}};
vm.runInNewContext(d.runtime+d.financial,sandbox);process.stdout.write(JSON.stringify(configurations));
"""
    run=subprocess.run([node,"-e",script],input=json.dumps({"payload":payload,"runtime":runtime,"financial":financial}),
                       capture_output=True,text=True,check=True,timeout=5)
    datasets=next(c for c in json.loads(run.stdout) if c["id"]=="revenueChart")["datasets"]
    assert [d["label"] for d in datasets]==["保險業個別營業收入","個別本期損益"]
    assert datasets[0]["data"][-1]==pytest.approx(228.98381,abs=0.0001)

@pytest.mark.parametrize("metric",["淨利","本期損益"])
def test_target_issuer_parent_scope_is_rejected_and_other_issuer_stays_unverified(metric):
    from financial_money_claims import financial_money_claim_issues
    data=data_from_projection()
    assert financial_money_claim_issues(f"2851 2025 年母公司{metric}為 29.326 億元。",data)
    assert financial_money_claim_issues(f"國泰金 2025 年母公司{metric}為 100 億元。",data)==[]

def test_damaged_standalone_contract_without_basis_stays_dcf_unverified():
    from financial_tools import build_financial_tool_context
    data={**data_from_projection(),"current_price":30,"market_cap_raw":1e10,
          "total_debt_raw":0,"total_cash_raw":0,"shares_raw":1e9,"trailing_eps":2,
          "free_cash_flow_raw":2e9}
    data.pop("financial_history_basis")
    data["sector_specific_financials"]["documents"][0].pop("standalone_scope_evidence")
    metrics=build_financial_tool_context(data)
    assert metrics["metric_status"]["dcf"]["status"]=="unavailable"
    assert "insurer_standalone_basis_unverified" in metrics["metric_status"]["dcf"]["reason_codes"]

@pytest.mark.parametrize("note",[
 "前期本公司並無子公司，故本財務報告係個別財務報告；本期本公司有子公司，應編製個體及合併財報。",
 "本公司並非「本公司並無子公司，故本財務報告係個別財務報告」之情形，本公司有子公司。",
 "1.本公司並無子公司，故本財務報告係個別財務報告。惟本公司本期新增子公司，前述已不適用。"])
def test_quoted_prior_or_contradicted_no_subsidiary_note_is_not_scope_proof(note):
    from data_fetch.market_sources.insurer_xbrl import standalone_scope_evidence
    from data_fetch.financial_history_basis import project_insurer_standalone_histories
    from test_official_insurer_individual_xbrl import insurer_filing
    raw=insurer_filing()
    fact=f'<ix:nonNumeric name="tifrs-notes:BasisOfPreparation" contextRef="duration">{note}</ix:nonNumeric>'
    raw=raw.replace(b"</html>",fact.encode()+b"</html>")
    assert standalone_scope_evidence(raw,"2851",2025) is None
    receipt=statement()
    receipt["documents"][0]["standalone_scope_evidence"]["text"]=note
    assert project_insurer_standalone_histories(receipt,"2851.TW") is None
