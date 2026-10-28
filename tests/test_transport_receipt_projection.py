from provider_acquisition import observation_kind

def receipt(status='success'):
 return {'source':'alternative_data','provider':'104 Company Jobs API','status':status,'record_count':0,'message':'Transport only; content remains separately audited','details':{'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1','http_request_sent':True}}

def test_transport_diagnostics_never_add_data_success_or_failed_denominators():
 for status in ['success','error','unavailable']:
  assert observation_kind(receipt(status))=='aggregate_count'

def test_existing_failed_and_empty_observations_keep_their_denominators():
 row=receipt('error');row['details']['event_kind']='http_attempt'
 assert observation_kind(row)=='failed_count'
 row=receipt();row['details']['selection_policy']='untrusted-other-policy'
 assert observation_kind(row)=='empty_count'


def test_receipt_is_retained_without_changing_existing_sla_stats_or_api_units():
 import provider_sla as sla
 from provider_transport_receipt import record_job_transport_receipt
 import httpx,time
 sla.record_source_audit_entries([{'source':'alternative_data','provider':'104 Company Jobs API','status':'error','record_count':0}])
 with sla._connect() as db:
  before_stats=list(db.execute('SELECT * FROM provider_sla_stats'))
  before_usage=db.execute('SELECT count(*) FROM api_usage_events').fetchone()[0]
 record_job_transport_receipt('104 Company Jobs API',time.monotonic(),response=httpx.Response(200,content=b'body'),native_call=True)
 with sla._connect() as db:
  assert [tuple(r)for r in db.execute('SELECT * FROM provider_sla_stats')]==[tuple(r)for r in before_stats]
  assert db.execute('SELECT count(*) FROM api_usage_events').fetchone()[0]==before_usage
  assert db.execute('SELECT count(*) FROM provider_sla_events').fetchone()[0]==2
  windows=sla._window_stats_for_provider(db,'alternative_data','104 Company Jobs API',time.time())
  assert windows['last_24h']['attempts']==1 and windows['last_24h']['error_count']==1
