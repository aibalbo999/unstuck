"""Qualify natural retention expiry of archived, successful terminal RQ caches.

Pending jobs and retries never qualify. Bytes remain in the original snapshot;
this module reads SQLite and derives comparisons, never changes Redis or TTLs.
"""
from copy import deepcopy
from datetime import datetime,timedelta
import math,re,sqlite3,time

SOURCE='canonical_operational_sqlite_readonly'

def capture_application_states():
    from runtime_paths import current_runtime_paths
    from deployment_rq_pause import PauseError
    path=current_runtime_paths().operational_db
    try:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)as db:
            db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
            columns=('job_id','ticker','pipeline_id','status','finished_at','updated_at')
            rows=db.execute('SELECT '+','.join(columns)+' FROM analysis_jobs').fetchall()
        return {'schema':1,'source':SOURCE,'recorded_at':time.time(),
                'jobs':{r[0]:dict(zip(columns,r))for r in rows}}
    except(sqlite3.Error,OSError,ValueError)as exc:
        raise PauseError('Canonical SQL terminal witness unavailable')from exc

def scoped_comparison(before,after):
    from deployment_rq_pause import PauseError
    b,a=before['keys'],after['keys']
    lost=[k for k in set(b)-set(a)if k.startswith('rq:job:')and not k.endswith(':results')]
    if not lost:return before,after,[]
    def fail(reason):raise PauseError(reason)
    def witness(snapshot,job):
        w=snapshot.get('application_states');stamp=w.get('recorded_at')if isinstance(w,dict)else None
        if(not isinstance(w,dict)or w.get('schema')!=1 or w.get('source')!=SOURCE
                or type(stamp)not in(int,float)or not math.isfinite(stamp)
                or not snapshot['server_time']-2<=stamp<=snapshot['server_time']+30
                or not isinstance(w.get('jobs'),dict)):
            fail('Original canonical SQL witness missing or unbound')
        return w['jobs'].get(job)
    scoped=deepcopy(before);proofs=[]
    for key in sorted(lost):
        match=re.fullmatch(r'rq:job:analysis:([0-9a-f]{32})',key)
        if not match:fail('Lost job is not a qualified native analysis job')
        job=match[1];old=witness(before,job);new=witness(after,job)
        if(not isinstance(old,dict)or old!=new or old.get('job_id')!=job or old.get('status')!='done'
                or not isinstance(old.get('ticker'),str)or not isinstance(old.get('pipeline_id'),str)):
            fail('Application job is not unchanged and done')
        row=b[key]
        if row['type']!='hash':fail('Original job payload type changed')
        fields=row['value']
        try:
            raw=lambda name:bytes.fromhex(fields[name.encode().hex()])
            origin=raw('origin').decode('ascii');retention=int(raw('result_ttl'));end=datetime.fromisoformat(raw('ended_at').decode().replace('Z','+00:00'))
            expected=f"analysis_jobs.run_stock_analysis_job('{job}', '{old['ticker']}', '{old['pipeline_id']}')".encode()
            if(raw('status')!=b'finished'or raw('description')!=expected or not raw('data')
                    or origin not in{'stock-analysis','analysis.high','analysis.normal','watchlist','maintenance','llm.retry'}
                    or not 1<=retention<=31_536_000 or end.utcoffset()!=timedelta(0)):
                fail('Original terminal payload binding invalid')
        except(KeyError,ValueError,TypeError,OverflowError,UnicodeError):fail('Original terminal payload incomplete')
        deadline=end.timestamp()+retention
        result_names=['rq:results:analysis:'+job,key+':results']
        present=[k for k in result_names if k in b]
        if len(present)!=1 or any(k in a for k in result_names):fail('Original result-cache pair incomplete')
        resultkey=present[0];result=b[resultkey]
        if result['type']!='stream'or not result['value']:fail('Original result bytes missing')
        if any(v[1].get(b'type'.hex())!=b'1'.hex()or not v[1].get(b'return_value'.hex())for v in result['value']):
            fail('Original result is not successful and archived')
        for item in(row,result):
            ttl=item['pttl']
            if(type(ttl)is not int or ttl<=0 or abs(before['server_time']+ttl/1000-deadline)>.25
                    or after['server_time']<before['server_time']+ttl/1000):
                fail('Result-cache loss precedes witnessed natural expiry')
        encoded=('analysis:'+job).encode().hex();registries=[]
        for registry,item in b.items():
            if registry in{key,resultkey}:continue
            if item['type']=='list'and encoded in item['value']:fail('Lost job remains pending')
            if item['type']=='zset':
                matches=[score for value,score in item['value']if value==encoded]
                if matches:
                    if registry!='rq:finished:'+origin or len(matches)!=1 or abs(matches[0]-deadline)>1.01:
                        fail('Lost job has an unqualified registry membership')
                    registries.append(registry)
        if registries!=['rq:finished:'+origin]:fail('Original finished registry witness missing')
        del scoped['keys'][key];del scoped['keys'][resultkey]
        # RQ may remove this already-expired finished-registry entry. No other
        # registry addition, removal, reordering or score change is excused.
        registry=registries[0];current=a.get(registry)
        current_values=current.get('value',[])if isinstance(current,dict)else[]
        if encoded not in{v[0]for v in current_values}:
            retained=[v for v in scoped['keys'][registry]['value']if v[0]!=encoded]
            if not retained and registry not in a:del scoped['keys'][registry]
            else:scoped['keys'][registry]['value']=retained
        proofs.append({'job_id':job,'original_keys':[key,resultkey],'sql_status':'done',
                       'original_retention_seconds':retention,'native_expiry_epoch':deadline,
                       'original_bytes_preserved_in_before_snapshot':True,
                       'classification':'witnessed_successful_terminal_cache_retention_elapsed'})
    return scoped,after,proofs
