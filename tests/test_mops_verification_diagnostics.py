"""Rejected originals expose bounded failure stages without relaxing any gate."""
from copy import deepcopy
import json
import pytest
from test_mops_presentation import harness,electronics_harness,valid_data


def test_projection_rejection_has_a_stage_and_preserves_the_boolean_contract(electronics_harness):
    from data_fetch.market_sources import mops_presentation as source
    value=source.fetch_presentation_context('2353.TW')
    changed=deepcopy(value);changed['documents'][0]['content_period']='2099Q1'
    out={}
    assert source.verify_context(changed,'2353.TW',diagnostics=out)is False
    assert out=={'verification_status':'rejected','verification_stage':'projection','verification_reason':'projection_mismatch'}


@pytest.mark.parametrize(('reason','expected'),[('timeout','parser_timeout'),('memory_accounting_unavailable','memory_accounting_unavailable')])
def test_pdf_replay_timeout_is_distinguishable_without_exception_text(electronics_harness,monkeypatch,reason,expected):
    from data_fetch.market_sources import mops_presentation as source
    from source_pdf_reader import SourcePdfError
    value=source.fetch_presentation_context('2353.TW')
    def expired(*a,**k):raise SourcePdfError(reason)
    monkeypatch.setattr(source,'native_material',expired)
    out={}
    assert source.verify_context(value,'2353.TW',diagnostics=out)is False
    assert out=={'verification_status':'rejected','verification_stage':'native_material','verification_reason':expected}
    assert 'raw_response_path'not in json.dumps(out)


def test_verified_original_keeps_exact_context_and_clears_old_diagnostic(electronics_harness):
    from data_fetch.market_sources import mops_presentation as source
    value=source.fetch_presentation_context('2353.TW');before=deepcopy(value)
    out={'verification_stage':'projection','verification_reason':'projection_mismatch'}
    assert source.verify_context(value,'2353.TW',diagnostics=out)is True
    assert out=={'verification_status':'verified','verification_stage':'complete','verification_reason':'none'}
    assert value==before


def test_provider_rejection_reaches_persisted_sla_without_raw_details(electronics_harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    import provider_sla
    def rejected(value,ticker,*,diagnostics=None,**kwargs):
        diagnostics.update(verification_status='rejected',verification_stage='native_material',verification_reason='parser_timeout')
        return False
    monkeypatch.setattr(source,'verify_context',rejected)
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2353.TW'),{'data':valid_data('2353.TW')})
    assert not result.value and result.audit['record_count']==0
    assert result.audit['error_kind']=='original_unverified'
    provider_sla.record_source_audit_entries([result.audit])
    with provider_sla._connect()as c:
        row=c.execute("select details_json from provider_sla_events where source='earnings_call'order by id desc limit 1").fetchone()
    saved=json.loads(row[0])
    assert saved['verification_stage']=='native_material'and saved['verification_reason']=='parser_timeout'
    assert 'request_body'not in saved and 'raw_response_path'not in saved


def test_verification_observation_fields_only_admit_fixed_enums():
    from provider_observation_details import observation_details
    assert observation_details({'verification_status':'rejected','verification_stage':'native_material','verification_reason':'parser_timeout'})=={
        'verification_status':'rejected','verification_stage':'native_material','verification_reason':'parser_timeout'}
    assert observation_details({'verification_status':'cookie=secret','verification_stage':'/private/file','verification_reason':'raw document'})=={}


def test_initial_parser_memory_failure_is_preserved_in_sla(electronics_harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as source
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from source_pdf_reader import SourcePdfError
    import provider_sla
    def failed(*a,**k):raise SourcePdfError('memory_accounting_unavailable')
    monkeypatch.setattr(source,'native_material',failed)
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2353.TW'),{'data':valid_data('2353.TW')})
    assert not result.value
    provider_sla.record_source_audit_entries([result.audit])
    with provider_sla._connect()as c:
        row=c.execute("select details_json from provider_sla_events where source='earnings_call'order by id desc limit 1").fetchone()
    assert json.loads(row[0])['document_error_kind']=='memory_accounting_unavailable'
