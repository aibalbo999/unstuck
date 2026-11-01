from copy import deepcopy
import pytest
import macro_fetcher
import free_macro_fetcher
from macro_source_router import fetch_macro_indicators


def primary(status="partial"):
    return {"status":status,"source":"FRED","indicators":{
        "vix":{"value":20,"date":"2026-10-30","status":"success","unit":"index","cache_hit":True}},
        "component_statuses":{"vix":{"status":"success"}},"retrieval_origin":{"new_fetch_attempted":False}}


def candidate(name, *, success=True, cached=False):
    return {"status":"success" if success else "unavailable","provider":"BLS" if name=="us_cpi_yoy" else "FederalReserve",
        "observation":{"value":4,"date":"2026-10-30","source_series":name,"unit":"%","original_receipt":{"status":"archived"}} if success else None,
        "metadata":{},"cache_hit":cached,"source_url":"https://example.test/original",
        "acquisition_attempted":not cached,"new_original_acquired":success and not cached,
        "transport":{"http_request_sent":not cached}}


def test_complete_primary_never_calls_alternative(monkeypatch):
    value=primary("success");monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:value)
    def forbidden(*a):pytest.fail("qualified primary must not trigger extra requests")
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",forbidden)
    assert fetch_macro_indicators() is value


def test_only_missing_components_replaced_and_primary_not_mutated(monkeypatch):
    value=primary();before=deepcopy(value);calls=[]
    monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:value)
    def fetch(name):calls.append(name);return candidate(name)
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",fetch)
    result=fetch_macro_indicators()
    assert calls==["us_10y_yield","us_cpi_yoy"]
    assert result["status"]=="success" and value==before
    assert result["indicators"]["vix"]==before["indicators"]["vix"]
    assert result["indicators"]["us_cpi_yoy"]["provider"]=="BLS"
    assert "BLS" in result["summary_text"] and result["cache_hit"] is False


def test_failed_fallback_preserves_stale_primary_and_failure(monkeypatch):
    value=primary();value["indicators"]["us_cpi_yoy"]={"value":3,"date":"2026-04-01","stale":True,"unit":"%"}
    value["component_statuses"]["us_cpi_yoy"]={"status":"stale","stale":True}
    monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:value)
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",lambda name:candidate(name,success=False))
    result=fetch_macro_indicators()
    assert result["status"]=="partial" and result["indicators"]["us_cpi_yoy"]["value"]==3
    assert result["component_statuses"]["us_cpi_yoy"]["free_fallback"]["status"]=="unavailable"


def test_no_key_can_use_free_originals_and_cached_not_new_http(monkeypatch):
    monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:{"status":"not_configured"})
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",lambda name:candidate(name,cached=True))
    result=fetch_macro_indicators()
    assert result["status"]=="success" and len(result["indicators"])==3
    assert result["cache_hit"] is True
    assert result["retrieval_origin"]["free_acquired_components"]==[]
    assert result["retrieval_origin"]["new_fetch_attempted"] is False


def test_provider_without_key_uses_router_and_correct_provider_label(monkeypatch):
    from data_fetch.agent_context_providers import MacroIndicatorsProvider
    from data_fetch.types import FetchRequest
    import macro_source_router
    monkeypatch.delenv("FRED_API_KEY",raising=False)
    monkeypatch.setattr(macro_source_router,"fetch_macro_indicators",lambda:{"status":"success","actual_provider":"BLS / Cboe / FederalReserve", "indicators":{"vix":{"value":20}},"cache_hit":True})
    provider=MacroIndicatorsProvider()
    assert not provider.requires_env
    result=provider.fetch(FetchRequest.from_ticker("1623.TW"))
    assert result.value["status"]=="success"
    assert result.audit["provider"]=="BLS / Cboe / FederalReserve"


def test_primary_failure_is_retained_and_persisted_before_recovered_result(monkeypatch):
    from provider_correlation import correlation_scope
    from data_fetch.agent_context_providers import MacroIndicatorsProvider
    from data_fetch.types import FetchRequest
    import provider_sla
    monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:{
        "status":"unavailable","indicators":{},"component_statuses":{},
        "retrieval_origin":{"new_fetch_attempted":True,"attempted_series":["DGS10"]}})
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",lambda name:candidate(name))
    recorded=[];monkeypatch.setattr(provider_sla,"record_source_audit_entries",lambda rows:recorded.extend(rows))
    with correlation_scope(ticker="1623.TW",fetch_id="synthetic-test",operation_id="synthetic-operation"):
        result=MacroIndicatorsProvider().fetch(FetchRequest.from_ticker("1623.TW"))
    assert result.status=="success"
    assert len(recorded)==1 and recorded[0]["provider"]=="FRED macro indicators"
    assert recorded[0]["status"]=="unavailable" and recorded[0]["record_count"]==0
    assert result.value["primary_provider_audit"]["status"]=="unavailable"


def test_no_native_attempts_and_no_values_is_local_block(monkeypatch):
    from data_fetch.agent_context_providers import MacroIndicatorsProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:{"status":"not_configured"})
    def locally_blocked(name):
        result=candidate(name,success=False,cached=True)
        result["transport"]={"http_request_sent":False}
        return result
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",locally_blocked)
    result=MacroIndicatorsProvider().fetch(FetchRequest.from_ticker("1623.TW"))
    assert result.audit["event_kind"]=="local_block" and result.audit["http_request_count"]==0


def test_sla_opt_out_does_not_persist_primary_failure(monkeypatch):
    from provider_correlation import correlation_scope
    from data_fetch.agent_context_providers import MacroIndicatorsProvider
    from data_fetch.types import FetchRequest
    import provider_sla
    monkeypatch.setattr(macro_fetcher,"fetch_key_macro_indicators",lambda **k:{"status":"unavailable"})
    monkeypatch.setattr(free_macro_fetcher,"fetch_free_macro_component",lambda name:candidate(name))
    def forbidden(rows):pytest.fail("SLA write must honor request opt-out")
    monkeypatch.setattr(provider_sla,"record_source_audit_entries",forbidden)
    with correlation_scope(ticker="1623.TW",fetch_id="synthetic-test",operation_id="synthetic-operation"):
        result=MacroIndicatorsProvider().fetch(FetchRequest.from_ticker("1623.TW",record_provider_sla=False))
    assert result.status=="success" and "primary_provider_audit" in result.value
