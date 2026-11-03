from copy import deepcopy
from datetime import datetime,timezone
from types import SimpleNamespace
import sqlite3
import pytest
import deployment_terminal_expiry as candidate
from deployment_rq_pause import compare,PauseError

JOB='1'*32;KEY='rq:job:analysis:'+JOB;RESULT='rq:results:analysis:'+JOB
def h(value):return value.encode().hex()
def pair():
    def item(kind,value,ttl=-1):return {'type':kind,'value':value,'pttl':ttl}
    fields={'status':'finished','origin':'watchlist','result_ttl':'120','ended_at':datetime.fromtimestamp(881,timezone.utc).isoformat(),'description':f"analysis_jobs.run_stock_analysis_job('{JOB}', '2633.TW', 'v1')",'data':'retained-pickle','meta':'retained-meta','retries_left':'2'}
    jobs={JOB:{'job_id':JOB,'ticker':'2633.TW','pipeline_id':'v1','status':'done','finished_at':881.,'updated_at':881.}}
    b={'schema':1,'server_time':1000.,'application_states':{'schema':1,'source':candidate.SOURCE,'recorded_at':1000.01,'jobs':jobs},'keys':{
        KEY:item('hash',{h(k):h(v)for k,v in fields.items()},1000),RESULT:item('stream',[[h('900-0'),{h('type'):h('1'),h('return_value'):h('retained-result')}]],1000),
        'rq:finished:watchlist':item('zset',[[h('analysis:'+JOB),1001.]])}}
    a=deepcopy(b);a['server_time']=1002.;a['application_states']['recorded_at']=1002.01
    del a['keys'][KEY];del a['keys'][RESULT]
    return b,a

def test_complete_native_terminal_expiry_is_qualified_without_relaxing_pending_work():
    b,a=pair();from test_deployment_rq_pause import pair as pending_pair
    pb,pa=pending_pair();b['keys'].update(pb['keys']);a['keys'].update(pa['keys'])
    result=compare(b,a)
    assert result['passed']and result['promoted_job_ids']==['x']
    assert result['exact_job_count']==1 and result['expired_terminal_caches'][0]['job_id']==JOB
    assert KEY in b['keys']and RESULT in b['keys']

@pytest.mark.parametrize('change',['before_sql','after_sql','sql_pending','sql_changed','sql_time','status','description','payload','ttl','early','retention','result_present','result_missing','result_failed','registry_missing','pending_queue','pending_registry'])
def test_any_missing_or_contradictory_native_witness_stays_blocked(change):
    b,a=pair();row=b['keys'][KEY]
    if change=='before_sql':b.pop('application_states')
    elif change=='after_sql':a.pop('application_states')
    elif change=='sql_pending':b['application_states']['jobs'][JOB]['status']='waiting_retry';a['application_states']['jobs'][JOB]['status']='waiting_retry'
    elif change=='sql_changed':a['application_states']['jobs'][JOB]['updated_at']=882.
    elif change=='sql_time':b['application_states']['recorded_at']=1040.
    elif change=='status':row['value'][h('status')]=h('queued')
    elif change=='description':row['value'][h('description')]=h('another job')
    elif change=='payload':row['value'][h('data')]=''
    elif change=='ttl':row['pttl']=-1
    elif change=='early':a['server_time']=1000.5;a['application_states']['recorded_at']=1000.51
    elif change=='retention':row['value'][h('result_ttl')]=h('600')
    elif change=='result_present':a['keys'][RESULT]=deepcopy(b['keys'][RESULT])
    elif change=='result_missing':b['keys'].pop(RESULT)
    elif change=='result_failed':b['keys'][RESULT]['value'][0][1][h('type')]=h('2')
    elif change=='registry_missing':b['keys'].pop('rq:finished:watchlist');a['keys'].pop('rq:finished:watchlist')
    elif change=='pending_queue':b['keys']['rq:queue:watchlist']={'type':'list','pttl':-1,'value':[h('analysis:'+JOB)]}
    else:b['keys']['rq:scheduled:watchlist']={'type':'zset','pttl':-1,'value':[[h('analysis:'+JOB),1001.]]}
    with pytest.raises(PauseError):candidate.scoped_comparison(b,a)

def test_finished_registry_cleanup_only_excuses_the_witnessed_expired_member():
    b,a=pair();a['keys'].pop('rq:finished:watchlist')
    scoped,after,proof=candidate.scoped_comparison(b,a)
    assert compare(scoped,after)['passed']and proof[0]['original_bytes_preserved_in_before_snapshot']
    b,a=pair();b['keys']['rq:finished:watchlist']['value'].append([h('other'),2000.]);a['keys'].pop('rq:finished:watchlist')
    scoped,after,_=candidate.scoped_comparison(b,a)
    with pytest.raises(PauseError):compare(scoped,after)

@pytest.mark.parametrize('change',['new_job','other_payload','other_retry','other_result'])
def test_qualified_terminal_expiry_cannot_hide_any_other_durable_change(change):
    from test_deployment_rq_pause import pair as pending_pair
    b,a=pair();pb,pa=pending_pair();b['keys'].update(pb['keys']);a['keys'].update(pa['keys'])
    if change=='new_job':a['keys']['rq:job:new']=deepcopy(a['keys']['rq:job:x'])
    elif change=='other_payload':a['keys']['rq:job:x']['value'][h('data')]=h('changed')
    elif change=='other_retry':a['keys']['rq:job:x']['value'][h('retries_left')]=h('999')
    else:a['keys']['rq:results:x']={'type':'stream','pttl':-1,'value':[]}
    scoped,after,_=candidate.scoped_comparison(b,a)
    with pytest.raises(PauseError):compare(scoped,after)

def test_application_witness_uses_canonical_readonly_database(monkeypatch,tmp_path):
    import runtime_paths
    path=tmp_path/'operational.sqlite3'
    with sqlite3.connect(path)as db:
        db.execute('CREATE TABLE analysis_jobs(job_id TEXT PRIMARY KEY,ticker TEXT,pipeline_id TEXT,status TEXT,finished_at REAL,updated_at REAL)')
        db.execute('INSERT INTO analysis_jobs VALUES(?,?,?,?,?,?)',(JOB,'2633.TW','v1','done',881.,881.))
    original=path.read_bytes();monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:SimpleNamespace(operational_db=path))
    witness=candidate.capture_application_states()
    assert witness['jobs'][JOB]['status']=='done'and path.read_bytes()==original
    monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:SimpleNamespace(operational_db=tmp_path/'absent.sqlite3'))
    with pytest.raises(PauseError):candidate.capture_application_states()
    assert not(tmp_path/'absent.sqlite3').exists()
