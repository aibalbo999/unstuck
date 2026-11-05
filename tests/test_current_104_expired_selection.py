"""A fixed complete mixed sample is evidence of eligible ads, never all jobs."""
from copy import deepcopy
import json
import pytest
from test_current_104_postings import packets,raw,ISSUER,NOW,JOB
from data_fetch.market_sources.current_104_postings import parse_snapshot,SnapshotError

OTHER='expired1'
def mixed(deadline='2024-02-22'):
    index,good=packets();bad=deepcopy(good)
    row=deepcopy(index['data']['list']['normalJobs'][0]);row.update(jobNo=OTHER,jobUrl='https://www.104.com.tw/job/'+OTHER)
    index['data']['list']['normalJobs'].append(row);index['data']['totalCount']=2
    bad['data']['closeDate']=deadline
    return index,{JOB:good,OTHER:bad}
def parse(index,details):
    return parse_snapshot(raw(index),{k:raw(v)for k,v in details.items()},issuer=ISSUER,observed_at=NOW,now=NOW)

def test_mixed_expired_deadline_is_explicit_rejection_not_eligible_ad():
    index,details=mixed();p=parse(index,details).public_value()
    assert p['schema']=='104-current-enabled-advertisements:mixed-expiry:v2'
    assert p['selected_job_ids']==[JOB,OTHER] and p['selected_detail_count']==2
    assert p['observed_sample_posting_count']==1
    assert [j['job_id']for j in p['job_postings']]==[JOB]
    assert p['excluded_postings']==[{'job_id':OTHER,'url':'https://www.104.com.tw/job/'+OTHER,'deadline':'2024-02-22','reason_code':'deadline_not_proven_future'}]
    assert p['hiring_headcount']is None and p['recent_company_job_count']is None
    assert not p['native_originals_verified']

@pytest.mark.parametrize('deadline',['2024/02/22','2026-11-05','2026/11/05'])
def test_both_typed_deadline_forms_apply_same_cutoff(deadline):
    index,details=mixed(deadline);p=parse(index,details).public_value()
    assert p['observed_sample_posting_count']==1 and p['excluded_postings'][0]['deadline']<= '2026-11-05'

def test_iso_future_deadline_is_canonical_but_header_date_grammar_is_unchanged():
    a,b=packets();b['data']['closeDate']='2026-12-01'
    p=parse(a,{JOB:b}).public_value()
    assert p['schema']=='104-current-enabled-advertisements:v1'
    assert p['job_postings'][0]['deadline']=='2026-12-01'
    assert 'excluded_postings'not in p
    b['data']['header']['appearDate']='2026-10-02'
    with pytest.raises(SnapshotError):parse(a,{JOB:b})

@pytest.mark.parametrize('deadline',['2026-2-03','2026-02/03','2026-02-30','2026-12-01T00:00:00','2026-12-01Z',' 2026-12-01','2026-12-01 ','2026-12-01/','next year'])
def test_malformed_deadline_is_batch_fatal_even_when_other_ad_is_good(deadline):
    a,d=mixed(deadline)
    with pytest.raises(SnapshotError):parse(a,d)

@pytest.mark.parametrize('mutation',['wrong_employer','wrong_title','future_appear','wrong_company','missing_deadline','pool','description','disabled','duplicate_json'])
def test_expired_record_still_must_pass_all_global_safety_checks(mutation):
    a,d=mixed();bad=d[OTHER]['data']
    if mutation=='wrong_employer':bad['header']['custName']='別家公司股份有限公司'
    if mutation=='wrong_title':bad['header']['jobName']='wrong'
    if mutation=='future_appear':bad['header']['appearDate']='2027/10/02'
    if mutation=='wrong_company':bad['custNo']='another'
    if mutation=='missing_deadline':del bad['closeDate']
    if mutation=='pool':bad['jobDetail']['jobDescription']='talent pool not currently recruiting only for future recruitment.'
    if mutation=='description':bad['jobDetail']['jobDescription']='short'
    if mutation=='disabled':bad['switch']='off'
    if mutation=='duplicate_json':
        with pytest.raises(SnapshotError):parse_snapshot(raw(a),{JOB:raw(d[JOB]),OTHER:b'{"data":{},"data":{},"metadata":{}}'},issuer=ISSUER,observed_at=NOW,now=NOW)
        return
    with pytest.raises(SnapshotError):parse(a,d)

def test_all_expired_is_no_eligible_data_and_missing_expired_body_is_fatal():
    a,d=mixed();d[JOB]['data']['closeDate']='2024-02-22'
    with pytest.raises(SnapshotError):parse(a,d)
    del d[OTHER]
    with pytest.raises(SnapshotError):parse(a,d)
