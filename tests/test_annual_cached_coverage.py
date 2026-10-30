"""Normalize misleading legacy combined coverage on ordinary cache reads."""
from copy import deepcopy
import pytest
from data_fetch.types import ProviderResult


def payload(missing=None):
    workforce={'employee_average_salary_thousand_twd':1000,'nonmanager_median_salary_thousand_twd':800,'female_manager_percent':0}
    safety={'occupational_injury_count':0,'occupational_injury_rate_percent':0,'fire_incident_count':0,'fire_casualty_count':0,'fire_casualty_rate_percent':0}
    if missing in workforce:workforce[missing]=None
    if missing in safety:safety[missing]=None
    return {'ticker':'1623.TW','current_price':100,'eps':5,'annual_workforce':{
        'ticker':'1623.TW','observation_kind':'annual_workforce_disclosure','coverage_status':'complete',
        'metrics':workforce,'fetched_at_epoch':123.,'missing_metric_fields':[],
        'esg_occupational_safety':{'coverage_status':'complete','status':'success','metrics':safety,'missing_metric_fields':[]}}}


def read(monkeypatch,old,fallback):
    import data_fetch.workflow_cache as cache
    # This suite tests annual-field normalization, not the separately tested
    # session planner. Mock its full boundary, including keyword arguments.
    monkeypatch.setattr(cache,'assess_session_aligned_cache',lambda *a,**kw:(True,{}))
    return cache.fallback_cached_payload('1623.TW',old,ProviderResult('quote','stub','error')) if fallback else cache.fresh_cached_payload('1623.TW',old)


@pytest.mark.parametrize('fallback',[False,True])
@pytest.mark.parametrize('missing',['nonmanager_median_salary_thousand_twd','employee_average_salary_thousand_twd','fire_casualty_rate_percent'])
def test_ordinary_cache_read_downgrades_incomplete_combination_without_fetch_or_input_mutation(monkeypatch,fallback,missing):
    old=payload(missing);before=deepcopy(old);out=read(monkeypatch,old,fallback)
    assert out['annual_workforce']['coverage_status']=='partial'
    assert old==before
    assert out['annual_workforce']['metrics']==before['annual_workforce']['metrics']
    assert out['annual_workforce']['esg_occupational_safety']==before['annual_workforce']['esg_occupational_safety']
    assert out['annual_workforce']['fetched_at_epoch']==123.
    assert out['current_price']==100 and out['eps']==5


@pytest.mark.parametrize('fallback',[False,True])
def test_complete_components_keep_coverage_and_partial_is_never_upgraded(monkeypatch,fallback):
    old=payload();out=read(monkeypatch,old,fallback)
    assert out['annual_workforce']['coverage_status']=='complete'
    old['annual_workforce']['coverage_status']='partial'
    assert read(monkeypatch,old,fallback)['annual_workforce']['coverage_status']=='partial'


@pytest.mark.parametrize('change',['absent_safety','stale_safety','declared_missing'])
def test_missing_stale_or_declared_partial_component_cannot_remain_complete(monkeypatch,change):
    old=payload()
    if change=='absent_safety':old['annual_workforce'].pop('esg_occupational_safety')
    elif change=='stale_safety':old['annual_workforce']['esg_occupational_safety']['status']='stale'
    else:old['annual_workforce']['missing_metric_fields']=['nonmanager_median_salary_thousand_twd']
    assert read(monkeypatch,old,False)['annual_workforce']['coverage_status']=='partial'
