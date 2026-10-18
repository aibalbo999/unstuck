"""Recover one leased scheduled dispatch without creating another model job."""
from __future__ import annotations
import watchlist_dispatch_store as intents
from job_store import get_job

class DispatchReceiptUnavailable(RuntimeError):
    pass

def dispatch_item(item, *, create_job, find_active_job, task_queue, run_stock_analysis_job):
    if not intents.renew(item):return {'kind':'skipped','reason':'dispatch_lease_lost'}
    ticker=item['ticker'];pipeline=item['pipeline'];job_id=item['dispatch_job_id']
    active=find_active_job(ticker,pipeline)
    if active and active.get('job_id') != job_id:
        receipt=task_queue.dispatch_receipt('analysis:'+active['job_id'])
        if not receipt or receipt['status'] not in {'queued','started','scheduled','deferred'}:
            raise DispatchReceiptUnavailable('active job has no verified queue receipt')
        if tuple(receipt['args']) != (active['job_id'],ticker,pipeline):
            raise DispatchReceiptUnavailable('active task identity does not match dispatch')
        if not intents.acknowledge(item,active['job_id'],'attached_active'):
            return {'kind':'skipped','reason':'dispatch_lease_lost'}
        return {'kind':'skipped','reason':'active_job','job_id':active['job_id']}
    created_id=create_job(ticker,pipeline,job_id=job_id)
    if created_id != job_id:raise DispatchReceiptUnavailable('job creator changed durable dispatch identity')
    existing=get_job(job_id)
    if existing.get('status') in {'running','waiting_retry','done','error','cancelled'}:
        # Persisted execution/terminal evidence is stronger than an expired Redis key.
        if not intents.acknowledge(item,job_id,'sql_execution_or_terminal'):
            return {'kind':'skipped','reason':'dispatch_lease_lost'}
        return {'kind':'skipped','reason':'already_started','job_id':job_id}
    receipt=task_queue.enqueue_once('analysis:'+job_id,run_stock_analysis_job,job_id,ticker,pipeline,queue_name='watchlist')
    if not receipt or receipt.get('task_id') != 'analysis:'+job_id:
        raise DispatchReceiptUnavailable('no durable queue acknowledgement')
    if not intents.acknowledge(item,job_id,'rq_created' if receipt['created'] else 'rq_existing'):
        return {'kind':'skipped','reason':'dispatch_lease_lost'}
    return {'kind':'queued','job_id':job_id,'newly_enqueued':receipt['created']}
