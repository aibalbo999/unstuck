"""One complete annual component cannot certify another partial component."""
import json
from datetime import date
import pytest
from data_fetch.annual_workforce_provider import AnnualWorkforceProvider
from data_fetch.types import FetchRequest
from test_annual_occupational_safety import _row

@pytest.mark.parametrize('missing',['salary','female','safety'])
def test_component_partial_remains_visible_in_combined_annual_value(monkeypatch,missing):
    import data_fetch.annual_workforce_provider as source
    workforce={'出表日期':'1151016','報告年度':'114','公司代號':'2330','公司名稱':'台積電',
               '員工薪資平均數(仟元/人)':'4093','非擔任主管之全時員工薪資中位數(仟元/人)':'3162','管理職女性主管佔比':'15.00%'}
    safety=_row()
    if missing=='salary':workforce['員工薪資平均數(仟元/人)']='N/A'
    if missing=='female':workforce['管理職女性主管佔比']=''
    if missing=='safety':safety['火災死傷人數占員工總人數比率']=''
    monkeypatch.setattr(source,'_today',lambda:date(2026,10,17))
    monkeypatch.setattr(source,'shared_fetch',lambda key,*a,**k:(json.dumps([safety if 'occupational' in key else workforce]),{'cache_hit':True,'stale':False,'fetched_at_epoch':1792222511.0}))
    result=AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('2330.TW'))
    assert result.value['coverage_status']=='partial'
    assert result.value['esg_occupational_safety']['metrics']['occupational_injury_count']==0
    assert result.value['metrics']['employee_average_salary_thousand_twd']==(None if missing=='salary' else 4093)
    assert result.audit['record_count']==(0 if missing=='salary' else 1)
    assert not result.audit['http_request_sent']
