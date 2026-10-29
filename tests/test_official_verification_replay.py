import copy
import hashlib
import json
from pathlib import Path

import pytest

from test_official_institutional_verification import fixture
from official_institutional_verification import prepare_archived_verification, evaluate_official_verification
from official_response_evidence import archive_response
from official_institutional_source import TWSE_FIELDS, _url


@pytest.fixture(autouse=True)
def isolated_public_archive(monkeypatch, tmp_path):
    from types import SimpleNamespace
    monkeypatch.setattr('runtime_paths.current_runtime_paths',lambda:SimpleNamespace(cache_dir=tmp_path))


def seal(proof):
    content={k:v for k,v in proof.items() if k!='evidence_payload_sha256'}
    proof['evidence_payload_sha256']=hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def lineage(population='foreign'):
    return {'population':population,'observed_at':'2026-10-02','observation_dates':['2026-10-02']}


def test_rehashed_excerpt_cannot_replace_original_bytes():
    proof,data,_=fixture()
    row=proof['reports'][0]['source_excerpt']['data'][0];row[4]='999';row[18]='999'
    data['institutional_trading']['daily_category_observations'][0]['net_buy_shares']=999
    seal(proof)
    result=evaluate_official_verification(proof,data,lineage())
    assert result['status']!='matched'


@pytest.mark.parametrize('change',['missing','outside','corrupt'])
def test_original_must_still_exist_and_replay(change):
    proof,data,_=fixture();r=proof['reports'][0]
    if change=='outside':r['raw_response_path']='/private/not-an-archive'
    elif change=='missing':Path(r['raw_response_path']).unlink()
    else:Path(r['raw_response_path']).write_bytes(b'not gzip')
    seal(proof)
    assert evaluate_official_verification(proof,data,lineage())['status']!='matched'


def test_wrong_exchange_cannot_borrow_twse_report():
    proof,data,_=fixture();proof['ticker']=data['ticker']='1301.TWO';seal(proof)
    assert evaluate_official_verification(proof,data,lineage())['status']!='matched'


def total_fixture():
    row=['1301','台塑']+['0']*17
    for index,value in [(4,1234),(10,20),(11,30),(14,15),(17,15),(18,1284)]:row[index]=str(value)
    body=json.dumps({'stat':'OK','date':'20261002','fields':TWSE_FIELDS,'hints':'單位：股','data':[row]}).encode()
    raw=archive_response(body,source_url=_url('TWSE','2026-10-02'),retrieved_at='2026-10-03T00:00:00+00:00')
    manifest={'ticker':'1301.TW','as_of':'2026-10-02','population':'all_three_institutional_categories','unit':'shares','window_dates':['2026-10-02'],'reports':[{'date':'2026-10-02',**raw}]}
    proof=prepare_archived_verification(manifest,lambda _:body)
    data={'ticker':'1301.TW','institutional_trading':{'daily_category_observations':[{'date':'2026-10-02','category':c,'net_buy_shares':n,'unit':'shares','source':'FinMind'}for c,n in [('foreign',1234),('investment_trust',20),('dealer',30)]]}}
    return proof,data


@pytest.mark.parametrize('population,total',[('foreign',1234),('investment_trust',20),('dealer',30),('total',1284)])
def test_explicit_all_category_scope_replays_exact_population(population,total):
    proof,data=total_fixture();result=evaluate_official_verification(proof,data,lineage(population))
    assert result['status']=='matched' and result['official_total_shares']==total
    assert result['historical_pit_verified'] is False and result['causation_or_return_verified'] is False


@pytest.mark.parametrize('change',['missing','duplicate','unit','boolean','mismatch'])
def test_total_requires_every_exact_category_without_substitution(change):
    proof,data=total_fixture();rows=data['institutional_trading']['daily_category_observations']
    if change=='missing':rows.pop()
    elif change=='duplicate':rows.append(copy.deepcopy(rows[0]))
    elif change=='unit':rows[-1]['unit']='thousand_shares'
    elif change=='boolean':rows[-1]['net_buy_shares']=True
    else:rows[-1]['net_buy_shares']+=1
    assert evaluate_official_verification(proof,data,lineage('total'))['status']!='matched'


def test_foreign_only_manifest_cannot_verify_total():
    proof,data=total_fixture();proof['population']='foreign_including_foreign_dealer';seal(proof)
    assert evaluate_official_verification(proof,data,lineage('total'))['status']!='matched'


def test_total_rejects_offsetting_category_errors():
    proof,data=total_fixture();rows=data['institutional_trading']['daily_category_observations']
    rows[0]['net_buy_shares']+=10
    rows[1]['net_buy_shares']-=10
    result=evaluate_official_verification(proof,data,lineage('total'))
    assert result['status']=='mismatch' and result['official_total_shares'] is None


def test_missing_day_in_multiday_window_never_matches():
    proof,data=total_fixture()
    proof['window_dates']=['2026-10-01','2026-10-02'];seal(proof)
    record=lineage('total');record['observation_dates']=['2026-10-01','2026-10-02']
    result=evaluate_official_verification(proof,data,record)
    assert result['status']=='incomplete' and result['official_total_shares'] is None


def test_prepare_does_not_trust_reader_without_original_archive():
    proof,data,_=fixture();report=proof['reports'][0]
    body=__import__('official_response_evidence').read_response(report)
    Path(report['raw_response_path']).unlink()
    with pytest.raises((ValueError,OSError)):
        prepare_archived_verification(proof,lambda _:body)
