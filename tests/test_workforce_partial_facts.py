"""Partial official facts survive, without passing the salary completeness gate."""
from datetime import date
import json
from pathlib import Path
import pytest
from data_fetch.annual_workforce_provider import AnnualWorkforceProvider,parse_workforce_dataset
from data_fetch.types import FetchRequest
from data_trust import source_record_count
from test_annual_workforce_source import LISTED

TODAY=date(2026,10,9)
FIXTURE=json.loads((Path(__file__).parent/'fixtures/source_acquisition/workforce_qualified_partial_20261009.json').read_text())

@pytest.mark.parametrize('ticker,female',[('2236.TW',22.7),('6672.TW',32.94)])
def test_real_official_female_only_row_survives_without_salary_zero(ticker,female):
    value=parse_workforce_dataset(json.dumps(FIXTURE['rows']).encode(),ticker,today=TODAY)
    assert value is not None and value['coverage_status']=='partial'
    assert value['metrics']['female_manager_percent']==female
    assert value['metrics']['employee_average_salary_thousand_twd'] is None
    assert value['metrics']['nonmanager_median_salary_thousand_twd'] is None
    assert value['available_metric_count']==1
    assert set(value['missing_metric_fields'])=={'employee_average_salary_thousand_twd','nonmanager_median_salary_thousand_twd'}
    assert source_record_count('annual_workforce',{'ticker':ticker,'annual_workforce':{**value,'status':'partial'}})==0

@pytest.mark.parametrize('ticker',[ '2236.TW','6672.TW'])
def test_fresh_cached_partial_facts_are_not_labeled_stale_or_complete(monkeypatch,ticker):
    import data_fetch.annual_workforce_provider as source
    monkeypatch.setattr(source,'_today',lambda:TODAY)
    monkeypatch.setattr(source,'shared_fetch',lambda *args,**kwargs:(json.dumps(FIXTURE['rows']),{'cache_hit':True,'stale':False,'fetched_at_epoch':FIXTURE['fetched_at_epoch']}))
    result=AnnualWorkforceProvider().fetch(FetchRequest.from_ticker(ticker,force_refresh=True))
    assert result.status=='unavailable' and result.value['status']=='partial'
    assert result.audit['record_count']==0 and result.audit['stale'] is False
    assert result.audit['coverage_status']=='partial' and result.audit['cache_hit'] is True
    assert result.value['metrics']['employee_average_salary_thousand_twd'] is None
    assert source_record_count('annual_workforce',{'ticker':ticker,'annual_workforce':result.value})==0


def test_valid_salary_partial_keeps_old_record_count_without_false_stale(monkeypatch):
    import data_fetch.annual_workforce_provider as source
    row={**LISTED,'管理職女性主管佔比':''}
    monkeypatch.setattr(source,'_today',lambda:TODAY)
    monkeypatch.setattr(source,'shared_fetch',lambda *args,**kwargs:(json.dumps([row]),{'cache_hit':True,'stale':False,'fetched_at_epoch':123.0}))
    result=AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.status=='degraded_enrichment' and result.value['status']=='partial'
    assert result.audit['stale'] is False and result.audit['coverage_status']=='partial'
    assert source_record_count('annual_workforce',{'ticker':'2330.TW','annual_workforce':result.value})==1


@pytest.mark.parametrize('bad_average',['NaN','Infinity','-1','wrong','0'])
def test_invalid_average_is_not_salvaged_as_missing(bad_average):
    row={**LISTED,'員工薪資平均數(仟元/人) ':bad_average}
    assert parse_workforce_dataset(json.dumps([row]).encode(),'2330.TW',today=TODAY) is None


def test_no_disclosed_metric_is_not_a_record():
    row={**LISTED,'員工薪資平均數(仟元/人) ':'N/A','非擔任主管之全時員工薪資中位數(仟元/人) ':'N/A','管理職女性主管佔比':''}
    assert parse_workforce_dataset(json.dumps([row]).encode(),'2330.TW',today=TODAY) is None


@pytest.mark.parametrize('female',[0,'0','0.00%'])
def test_explicit_zero_female_percent_survives_but_missing_salary_stays_none(female):
    row={**LISTED,'員工薪資平均數(仟元/人) ':'N/A','非擔任主管之全時員工薪資中位數(仟元/人) ':'N/A','管理職女性主管佔比':female}
    value=parse_workforce_dataset(json.dumps([row]).encode(),'2330.TW',today=TODAY)
    assert value is not None and value['metrics']['female_manager_percent']==0
    assert value['metrics']['employee_average_salary_thousand_twd'] is None
    assert value['coverage_status']=='partial'


def test_partial_facts_survive_optional_merge_and_keep_salary_gate(monkeypatch):
    import data_fetch.annual_workforce_provider as source
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    monkeypatch.setattr(source, '_today', lambda: TODAY)
    monkeypatch.setattr(source, 'shared_fetch', lambda *args, **kwargs: (json.dumps(FIXTURE['rows']),
        {'cache_hit': True, 'stale': False, 'fetched_at_epoch': FIXTURE['fetched_at_epoch']}))
    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('6672.TW'))
    data = {'ticker': '6672.TW', 'company_name': '騰輝電子-KY', 'source_audit': [result.audit],
            'source_freshness': {}, 'alternative_data': {'job_openings_104': {'job_count': None}}}
    merged = _merge_optional_http_bundle(data, {'annual_workforce': result.value},
                                         refreshed_sources=('annual_workforce',))
    assert merged['annual_workforce']['metrics']['female_manager_percent'] == 32.94
    assert merged['annual_workforce']['status'] == 'partial'
    assert source_record_count('annual_workforce', merged) == 0
    assert merged['alternative_data']['job_openings_104']['job_count'] is None
    audit = merged['source_audit'][-1]
    assert audit['status'] == 'unavailable' and audit['record_count'] == 0
    assert audit['stale'] is False and audit['error_kind'] == ''
    assert merged['source_freshness']['annual_workforce']['fetched_at_epoch'] == FIXTURE['fetched_at_epoch']


@pytest.mark.parametrize('cache_hit', [False, True])
def test_female_only_partial_never_passes_legacy_provider_health(monkeypatch, tmp_path, cache_hit):
    import data_fetch.annual_workforce_provider as source
    import provider_sla
    from provider_sla_dashboard_payload import source_health_from_provider_rows
    monkeypatch.setattr(source, '_today', lambda: TODAY)
    monkeypatch.setattr(source, 'shared_fetch', lambda *args, **kwargs: (json.dumps(FIXTURE['rows']),
        {'cache_hit': cache_hit, 'stale': False, 'fetched_at_epoch': FIXTURE['fetched_at_epoch']}))
    monkeypatch.setattr(provider_sla, 'TASK_DB_PATH', str(tmp_path / 'isolated_sla.sqlite3'))
    result = AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2236.TW'))
    provider_sla.record_source_audit_entries([result.audit])
    summary = provider_sla.get_provider_sla_summary()
    rows = [row for row in summary if row['source'] == 'annual_workforce']
    assert rows and all(row['success_rate'] == 0 for row in rows)
    assert not source_health_from_provider_rows(rows).get('annual_workforce')
    assert result.value['status'] == 'partial' and result.value['available_metric_count'] == 1


@pytest.mark.parametrize('median', ['1' + '0' * 309 + '.1', '1' + '0' * 309])
def test_nonfinite_conversion_cannot_be_a_sole_partial_metric(median):
    row = {**LISTED, '員工薪資平均數(仟元/人) ': 'N/A',
           '非擔任主管之全時員工薪資中位數(仟元/人) ': median, '管理職女性主管佔比': ''}
    assert parse_workforce_dataset(json.dumps([row]).encode(), '2330.TW', today=TODAY) is None
