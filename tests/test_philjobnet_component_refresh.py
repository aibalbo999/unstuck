import asyncio
from copy import deepcopy
import json
import time

import pytest
from fastapi import HTTPException
from data_fetch.agent_context_providers import PhilJobNetJobObservationProvider
from data_fetch.service import StockDataService
from data_fetch.types import ProviderResult
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import events,init_db
from test_philjobnet_medtecs import observation,PROVIDER,NOTE


def original(storage):
    name,keys,snapshot=saved_report(storage)
    snapshot['ticker']=snapshot['data']['ticker']='9103.TW'
    snapshot['data']['company_name']='美德醫療-DR'
    snapshot['data']['company_identity']={'ticker':'9103.TW','official_name':'美德醫療-DR'}
    snapshot['data']['alternative_data']={'job_openings_104':{'status':'error','job_count':None},
        'job_openings_1111':{'status':'unavailable','job_count':None},'coverage_notes':['全球職缺數未知']}
    storage.save_report(keys.data_key,json.dumps(snapshot).encode(),content_type='application/json')
    return name,keys,snapshot


@pytest.mark.parametrize('bad',['none','scope','audit_count','audit_time',None])
def test_component_adds_one_numeric_observation_preserving_all_original_data_or_rejects(monkeypatch,tmp_path,bad):
    init_db();storage=InMemoryStorage();name,keys,old=original(storage);calls=[]
    item=observation()
    if bad=='scope':item['global_job_count']=0
    if bad=='none':item=None
    def acquire(self,request,context):
        calls.append(request.ticker)
        audit={'source':'alternative_data','provider':PROVIDER,'status':'success','record_count':1,
               'fetched_at_epoch':item['fetched_at_epoch'] if item else time.time(),
               'http_request_count':2,'http_request_sent':True}
        if bad=='audit_count':audit['record_count']=2
        if bad=='audit_time':audit['fetched_at_epoch']=time.time()
        return ProviderResult('alternative_data',PROVIDER,'success',
                              {'job_openings_philjobnet':deepcopy(item)},audit)
    monkeypatch.setattr(PhilJobNetJobObservationProvider,'_fetch_uncached',acquire)
    before=storage.get_report(keys.data_key).content
    if bad:
        with pytest.raises(HTTPException):asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),
            storage=storage,refresh_service=StockDataService(),source='philjobnet_jobs'))
        assert storage.get_report(keys.data_key).content==before
    else:
        result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
            refresh_service=StockDataService(),source='philjobnet_jobs'))
        after=json.loads(storage.get_report(keys.data_key).content)
        assert result['refresh_sources']==['philjobnet_jobs']
        for key in ('current_price','revenue_history','years','earnings_call','peer_discovery_results'):
            assert after['data'][key]==old['data'][key]
        assert after['source_audit'][:len(old['source_audit'])]==old['source_audit']
        alt=after['data']['alternative_data']
        assert alt['job_openings_104']==old['data']['alternative_data']['job_openings_104']
        assert alt['job_openings_1111']==old['data']['alternative_data']['job_openings_1111']
        assert alt['job_openings_philjobnet']['global_job_count'] is None
        assert NOTE in alt['coverage_notes'] and after['analysis_evidence']==old['analysis_evidence']
        for gate in ('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert after[gate]==old[gate]
        assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
        assert len(events())==1 and events()[0]['source']=='alternative_data'
    assert calls==['9103.TW']
