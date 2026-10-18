"""Only called by isolated tests; a real process exits before SQLite ack."""
import os,pickle,socket,sqlite3,sys
from pathlib import Path
root=Path(sys.argv[2]).resolve()
allowed=Path(os.environ['OPERATIONAL_DB_PATH']).resolve().parent
assert root.is_relative_to(allowed)
def denied(*a,**kw):raise OSError('isolated child cannot contact runtime or providers')
socket.socket.connect=denied;socket.socket.connect_ex=denied;socket.create_connection=denied
connect=sqlite3.connect
def guarded(db,*a,**kw):
    assert str(db)==':memory:' or Path(db).resolve().is_relative_to(allowed)
    return connect(db,*a,**kw)
sqlite3.connect=guarded
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import job_store,watchlist_service
from test_watchlist_dispatch_recovery import NOW,MemoryRedis,queue,noop
from datetime import timedelta
watchlist_service.WATCHLIST_PATH=root/'watchlist.json';watchlist_service.reset_watchlist_store_for_tests()
job_store.TASK_DB_PATH=str(root/'jobs.sqlite3');job_store.reset_job_store_for_tests()
watchlist_service.time.sleep=lambda _:None
redis=MemoryRedis();q=queue(redis);saved=root/'redis-boundary.pickle'
if sys.argv[1]=='prepare':
    for ticker in ('2308.TW','3324.TWO'):
        watchlist_service.upsert_watchlist_item({'ticker':ticker,'pipeline':'v4','enabled':True,'schedule_slots':['post_market']})
    claimed=watchlist_service.claim_due_watchlist_items(NOW)
    item=claimed[0]
    stage=sys.argv[3]
    if stage != 'lease':
        jid=job_store.create_job(item['ticker'],item['pipeline'],job_id=item['dispatch_job_id'])
        if stage == 'queue':
            q.enqueue_once('analysis:'+jid,noop,jid,item['ticker'],item['pipeline'],queue_name='watchlist')
    saved.write_bytes(pickle.dumps(redis.snapshot()))
    # No ack, no finally: actual process exit in the cross-store commit window.
    os._exit(17)
redis.load(pickle.loads(saved.read_bytes()))
claimed=watchlist_service.claim_due_watchlist_items(NOW+timedelta(seconds=601))
result=watchlist_service.enqueue_watchlist_items(claimed,create_job=job_store.create_job,
    find_active_job=job_store.find_active_job,task_queue=q,run_stock_analysis_job=noop)
assert result['success'],result
saved.write_bytes(pickle.dumps(redis.snapshot()))
