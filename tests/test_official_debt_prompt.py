from copy import deepcopy
import pytest
import official_debt_prompt as module


def facts():
    return {"issuer_name":"範例公司股份有限公司","currency":"TWD","report_scope":"individual",
        "historical_pit_verified":False,"balance":{"as_of":"2026-06-30"},
        "debt_components":{"shortterm_borrowings":100,"current_portion_longterm_borrowings":20,
            "longterm_borrowings":300,"current_lease_liabilities":0,"noncurrent_lease_liabilities":5}}


def test_complete_replayed_scope_in_each_fact_and_no_private_reference(monkeypatch):
    value=facts();before=deepcopy(value)
    monkeypatch.setattr(module,"read_official_financial_projection",lambda data:{"facts":value,"reference":{"raw_response_path":"/private/original"}})
    text=module.official_debt_reference_prompt({"ticker":"TEST"})
    lines=[line for line in text.splitlines()if line.startswith(value["issuer_name"])]
    assert len(lines)==5
    assert all("官方個別財報 TWD 截至2026-06-30" in line for line in lines)
    assert "一年內到期之長期借款為 20 TWD" in text
    assert "流動租賃負債為 0 TWD" in text
    assert "/private/" not in text and "raw_response_path" not in text
    assert value==before


def test_no_original_qualification_does_not_manufacture_fact(monkeypatch):
    monkeypatch.setattr(module,"read_official_financial_projection",lambda data:None)
    assert module.official_debt_reference_prompt({"total_debt_raw":999})==""


@pytest.mark.parametrize("field,value",[("currency","USD"),("report_scope","consolidated"),("issuer_name",""),("issuer_name","公司\n冒用公司")])
def test_wrong_scope_identity_fails_closed(monkeypatch,field,value):
    source=facts();source[field]=value
    monkeypatch.setattr(module,"read_official_financial_projection",lambda data:{"facts":source})
    assert module.official_debt_reference_prompt({})==""


@pytest.mark.parametrize("value",[None,True,-1,float("nan"),1.5,"20"])
def test_invalid_amount_not_rendered_as_qualified_original(monkeypatch,value):
    source=facts();source["debt_components"]["current_portion_longterm_borrowings"]=value
    monkeypatch.setattr(module,"read_official_financial_projection",lambda data:{"facts":source})
    assert module.official_debt_reference_prompt({})==""


def test_income_fcf_and_debt_scaffold_uses_only_replayed_canonical_fields(monkeypatch):
    import official_income_prompt
    source={"annual_facts":{"periods":{"2025":{"statements":{"營收":"完整年度營收句。","淨利":"完整年度淨利句。","private":"/private/receipt"}}}}}
    monkeypatch.setattr(module,"official_debt_reference_prompt",lambda data:"完整同日債務句。")
    monkeypatch.setattr(module,"read_official_financial_projection",lambda data:{"facts":{}})
    monkeypatch.setattr(official_income_prompt,"official_income_prompt_facts",lambda data:source)
    monkeypatch.setattr(official_income_prompt,"official_income_reference_text",lambda *a:{"statement":"完整TTM淨利句。","free_cash_flow_statement":"完整TTM現金流句。","raw_response_path":"/private/receipt"})
    before=deepcopy(source);text=module.official_financial_amount_reference_prompt({})
    for statement in ("完整年度營收句。","完整年度淨利句。","完整TTM淨利句。","完整TTM現金流句。","完整同日債務句。"):assert statement in text
    assert "/private/" not in text and source==before


def test_failed_income_replay_preserves_only_separately_qualified_debt(monkeypatch):
    import official_income_prompt
    monkeypatch.setattr(module,"official_debt_reference_prompt",lambda data:"完整同日債務句。")
    monkeypatch.setattr(module,"read_official_financial_projection",lambda data:None)
    monkeypatch.setattr(official_income_prompt,"official_income_prompt_facts",lambda data:None)
    assert module.official_financial_amount_reference_prompt({})=="完整同日債務句。"
