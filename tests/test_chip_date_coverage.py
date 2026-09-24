"""Unknown observation dates remain usable but cannot claim complete coverage."""
import pytest

from data_fetch.agent_context_providers import ChipDataProvider
from data_fetch.types import FetchRequest
from data_fetch.enrichment_merge import _merge_optional_http_bundle
from provider_observation_details import observation_details


def _fetch(monkeypatch, margin_date):
    import chip_data_fetcher
    monkeypatch.setattr(chip_data_fetcher, 'fetch_tdcc_shareholder_distribution', lambda *a:{
        'status':'success','as_of_date':'20260918','source':'TDCC OpenData','major_holders_gt_1000_lots_pct':62.22})
    monkeypatch.setattr(chip_data_fetcher, 'fetch_twse_margin_short_sales', lambda *a, **kw:{
        'status':'success','source':'TWSE OpenAPI MI_MARGN','margin_balance':8449,
        'as_of_date':margin_date,'margin_date_status':'reported' if margin_date else 'unknown',
        'borrowed_short_status':'success','borrowed_short_as_of_date':'2026-09-22',
        'borrowed_short_source':'TWSE TWT93U','borrowed_short_sale_balance':3053000})
    return ChipDataProvider().fetch(FetchRequest.from_ticker('2305.TW'))


@pytest.mark.parametrize('margin_date',[None,'invalid-date'])
def test_unknown_date_is_partial_without_discarding_values_or_claiming_stale(monkeypatch,margin_date):
    result=_fetch(monkeypatch,margin_date)
    assert result.status == 'degraded_enrichment'
    assert result.value['status'] == 'partial'
    component=result.value['component_statuses']['margin_short']
    assert component['retrieval_status'] == 'success'
    assert component['date_status'] == 'unknown'
    assert component['reason_code'] == 'observation_date_unknown'
    assert result.value['twse_margin_short_sales']['margin_balance'] == 8449
    assert result.value['twse_margin_short_sales']['as_of_date'] == margin_date
    assert result.audit['stale'] is False
    assert '日期未知' in result.audit['message']


def test_all_reported_dates_keep_complete_coverage(monkeypatch):
    result=_fetch(monkeypatch,'2026-09-22')
    assert result.status == 'success'
    assert result.value['status'] == 'success'
    assert all(c['date_status']=='reported' for c in result.value['component_statuses'].values())


def test_unknown_date_survives_merge_and_adds_optional_warning_not_expiry(monkeypatch):
    result=_fetch(monkeypatch,None)
    data={'ticker':'2305.TW','source_audit':[result.audit]}
    merged=_merge_optional_http_bundle(data,{'chip_data':result.value},('chip_data',))
    audit=next(e for e in reversed(merged['source_audit']) if e['source']=='chip_data')
    assert audit['status'] == 'degraded_enrichment'
    assert audit['component_statuses']['margin_short']['date_status'] == 'unknown'
    assert audit['component_statuses']['margin_short']['retrieval_status'] == 'success'
    assert audit['stale'] is False
    assert 'optional_source_degraded:chip_data' in merged['data_trust']['reason_codes']
    assert 'optional_source_stale:chip_data' not in merged['data_trust']['reason_codes']
    details=observation_details(audit)
    assert details['component_statuses']['margin_short']['date_status']=='unknown'
