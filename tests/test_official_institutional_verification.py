import hashlib,json,copy
from official_institutional_source import TWSE_FIELDS,_url
from official_institutional_verification import prepare_archived_verification,evaluate_official_verification,attach_cached_verification
from institutional_claim_lineage import institutional_claim_lineage


def fixture():
    row=['1301','台塑']+['0']*17;row[4]='1234';row[18]='1234'
    body=json.dumps({'stat':'OK','date':'20261002','fields':TWSE_FIELDS,'hints':'單位：股','data':[row]}).encode()
    manifest={'ticker':'1301.TW','as_of':'2026-10-02','population':'foreign_including_foreign_dealer','unit':'shares','window_dates':['2026-10-02'],'reports':[{'date':'2026-10-02','source_url':_url('TWSE','2026-10-02'),'http_status':200,'raw_response_path':'public-test-response.json','raw_response_sha256':hashlib.sha256(body).hexdigest(),'retrieved_at':'2026-10-03T00:00:00+00:00'}]}
    proof=prepare_archived_verification(manifest,lambda _:body)
    data={'ticker':'1301.TW','institutional_trading':{'daily_category_observations':[{'date':'2026-10-02','category':'foreign','net_buy_shares':1234,'unit':'shares','source':'FinMind'}],'official_verification':proof}}
    record={'population':'foreign','window':{'kind':'day','date':'2026-10-02'},'observed_at':'2026-10-02','provider':'FinMind','value':1.23,'unit':'thousand_shares'}
    return proof,data,record


def test_real_receipt_extraction_and_match_do_not_claim_pit_or_prediction():
    proof,data,record=fixture();r=institutional_claim_lineage(data,record)
    assert r['status']=='recomputed' and r['independent_primary_source_verified']
    assert r['official_comparison']['official_total_shares']==1234
    assert not r['official_comparison']['historical_pit_verified']
    assert not r['official_comparison']['causation_or_return_verified']


def test_internally_consistent_provider_revision_still_blocked_by_official():
    proof,data,record=fixture();data['institutional_trading']['daily_category_observations'][0]['net_buy_shares']=2234;record['value']=2.23
    r=institutional_claim_lineage(data,record)
    assert r['status']=='mismatch' and r['reason']=='official_daily_observations_contradict_provider'


def test_missing_or_mutated_receipt_fails_closed():
    proof,data,record=fixture();proof['reports'].clear()
    assert institutional_claim_lineage(data,record)['status']=='unavailable'
    proof,data,record=fixture();proof['reports'][0]['source_excerpt']['data'][0][4]='999'
    assert institutional_claim_lineage(data,record)['official_comparison']['reason']=='official_evidence_payload_changed'


def test_cached_adoption_is_exact_ticker_and_endpoint_no_fetch(monkeypatch):
    proof,data,record=fixture();monkeypatch.setattr('cache_store.get_cache_json',lambda _:proof)
    value=attach_cached_verification({'latest_date':'2026-10-02'},'1301.TW');assert value['official_verification']==proof
    assert 'official_verification' not in attach_cached_verification({'latest_date':'2026-10-05'},'1301.TW')
    assert 'official_verification' not in attach_cached_verification({'latest_date':'2026-10-02'},'1513.TW')


def test_official_fallback_records_are_projected_without_invented_long_window():
    from institutional_evidence import institutional_evidence_records
    data={'institutional_trading':{'source':'TWSE T86','latest_date':'2026-10-02','lookback_trading_days':1,'net_buy_shares_by_category':{'foreign':1234}}}
    records=institutional_evidence_records(data)
    assert len(records)==1 and records[0]['provider']=='TWSE T86' and records[0]['window']['trading_days']==1
    data['institutional_trading']['source']='unknown provider'
    assert institutional_evidence_records(data)==[]
