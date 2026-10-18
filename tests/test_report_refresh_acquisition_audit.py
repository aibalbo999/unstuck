"""Real data-refresh work is observed once; reusing a payload is not new work."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
import json
import sqlite3
import time

import provider_sla
from provider_acquisition import get_provider_acquisition_summary
from data_fetch.service import StockDataService
from report_refresh_service import refresh_report_data_snapshot
from report_persistence import report_bundle_keys_for_filename
from report_analysis_evidence import capture_analysis_evidence
from test_report_refresh_incremental import InMemoryStorage


def bundle(storage,filename):
    keys=report_bundle_keys_for_filename(filename)
    snapshot={'ticker':'5314.TWO','company_name':'世紀*','pipeline':'v3','data':{'ticker':'5314.TWO','current_price':100},
              'report_lint':{'marker':'original lint'}}
    snapshot['analysis_evidence']=capture_analysis_evidence({'data':snapshot['data'],'quant_metrics':{'SMA20':90}},generated_at=datetime.now(timezone.utc).isoformat())
    storage.save_report(keys.html_key,b'<html>original</html>',content_type='text/html')
    storage.save_report(keys.data_key,json.dumps(snapshot).encode(),content_type='application/json')
    return keys,snapshot


def payload(*,cached=False):
    now=time.time()
    return {'ticker':'5314.TWO','company_name':'世紀*','quote_type':'EQUITY','exchange':'TWO','current_price':101,
            'annual_workforce':{'ticker':'5314.TWO','metrics':{'employee_average_salary_thousand_twd':758},'coverage_status':'complete'},
            'source_audit':[
              {'source':'annual_workforce','provider':'TWSE/TPEx annual workforce OpenAPI',
               'status':'success','record_count':1,'event_kind':'fetch','http_request_sent':not cached,'cache_hit':cached,'stale':False,'fetched_at_epoch':now},
              {'source':'financial_statements','provider':'failed refresh financial source',
               'status':'error','record_count':0,'event_kind':'fetch','http_request_sent':not cached,'cache_hit':cached,'stale':False,'error_kind':'FilingError','fetched_at_epoch':now}]}


def events():
    with sqlite3.connect(provider_sla.TASK_DB_PATH)as c:
        c.row_factory=sqlite3.Row
        return [dict(r)for r in c.execute('select * from provider_sla_events order by id')]


def init_db():
    with provider_sla._connect():pass


def test_actual_report_refresh_logs_success_and_failure_once_then_reuse_adds_no_events(tmp_path):
    init_db();storage=InMemoryStorage();first='5314_TWO_v3_report_20261008_160000.html';second='5314_TWO_v2_report_20261008_160001.html'
    first_keys,original=bundle(storage,first);bundle(storage,second);calls=[]
    async def acquire(request):
        calls.append(request);return payload()
    service=StockDataService(fetcher=acquire)
    result=asyncio.run(refresh_report_data_snapshot(first,output_dir=str(tmp_path),storage=storage,refresh_service=service,return_refreshed_data=True))
    observed=events();assert len(observed)==2
    assert {(r['source'],r['status'],r['record_count'])for r in observed}=={
        ('annual_workforce','success',1),('financial_statements','error',0)}
    snapshot=json.loads(storage.get_report(first_keys.data_key).content)
    ids={json.loads(r['details_json'])['fetch_id']for r in observed}
    assert len(ids)==1 and ids=={r['fetch_id']for r in snapshot['source_audit']}
    assert snapshot['analysis_evidence']==original['analysis_evidence'] and snapshot['report_lint']==original['report_lint']
    assert storage.get_report(first_keys.html_key).content==b'<html>original</html>'
    asyncio.run(refresh_report_data_snapshot(second,output_dir=str(tmp_path),storage=storage,refresh_service=service,refreshed_data=result['refreshed_data']))
    assert len(calls)==1 and events()==observed
    summary={s['source']:s for s in get_provider_acquisition_summary('last_24h')['sources']}
    assert summary['annual_workforce']['fetch_attempts']==1 and summary['annual_workforce']['fetched_count']==1
    assert summary['financial_statements']['fetch_attempts']==1 and summary['financial_statements']['failed_count']==1


def test_cached_provider_receipts_do_not_become_new_acquisition_successes(tmp_path):
    init_db();storage=InMemoryStorage();filename='5314_TWO_v3_report_20261008_160002.html';bundle(storage,filename)
    async def acquire(request):return payload(cached=True)
    asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(fetcher=acquire)))
    summary={s['source']:s for s in get_provider_acquisition_summary('last_24h')['sources']}
    assert len(events())==2
    assert summary['annual_workforce']['fresh_cache_count']==1 and summary['annual_workforce']['fetch_attempts']==0
    assert summary['annual_workforce']['nonempty_rate'] is None
    assert summary['financial_statements']['empty_cache_count']==1 and summary['financial_statements']['fetch_attempts']==0
