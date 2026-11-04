"""Receipt times, complete bodies and issuer identity cannot be re-authored."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json

import pytest

from test_tigerair_yes123 import synthetic_protocol


def bound(monkeypatch):
    from data_fetch.market_sources import tigerair_yes123_evidence as e
    from data_fetch.market_sources.official_company_legal_name import parse_roster, select_legal_name, URLS
    from official_response_evidence import archive_response
    import cache_store
    now=datetime.fromisoformat('2026-11-04T23:38:00+08:00').timestamp();owners={}
    monkeypatch.setattr(cache_store,'get_cache_json',lambda key:deepcopy(owners.get(key)))
    rows=[{'公司代號':str(1000+i),'公司名稱':'合成'+str(i)+'股份有限公司','公司簡稱':'合成'+str(i),
           '營利事業統一編號':'12345678','出表日期':'1151103','網址':'https://synthetic.example'}for i in range(800)]
    rows.append({'公司代號':'6757','公司名稱':e.LEGAL,'公司簡稱':e.SHORT,'營利事業統一編號':e.UBN,
                 '出表日期':'1151103','網址':'https://www.tigerairtw.com'})
    raw=json.dumps(rows,ensure_ascii=False).encode();archive_response(raw,source_url=URLS['.TW'],retrieved_at=now-60,http_status=200)
    roster=parse_roster(raw,'.TW');issuer=select_legal_name(roster,e.TICKER,e.SHORT,today=datetime.fromtimestamp(now,e.TZ).date())
    issuer.update(fetched_at_epoch=now-60,cache_hit=True)
    owners['shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest()]={
        'value':roster,'fetched_at_epoch':now-60,'fresh_until_epoch':now-60+86400}
    page,article,profile,detail,candidate=synthetic_protocol();receipts=[]
    for i,(body,url)in enumerate([(page,e.PAGE),(article,e.ARTICLE),(profile,e.PROFILE),(detail,candidate['url'])]):
        stamp=now-10+i
        native={'http_status':200,'http_status_observed':True,'response_complete':True,'http_request_sent':True,
                'return_code':0,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'response_bytes':len(body)}
        receipt=e.native_receipt(body,url,stamp,native);receipts.append(receipt)
        owners['shared_provider:v1:'+sha256((e.RAW_PREFIX+url).encode()).hexdigest()]={
            'value':deepcopy(receipt),'fetched_at_epoch':stamp+.001,'fresh_until_epoch':stamp+.001+e.TTL}
    data={'ticker':e.TICKER,'company_name':e.SHORT,'quote_type':'EQUITY',
          'company_identity':{'ticker':e.TICKER,'stock_id':'6757','instrument_type':'EQUITY',
                              'official_name':e.SHORT,'legal_name':e.LEGAL,'official_ubn':e.UBN}}
    value=e.parse_receipts(receipts,now=now)
    return e,now,owners,issuer,data,value


def test_complete_owned_source_and_master_replay_without_job_total_or_deadline_inference(monkeypatch):
    e,now,owners,issuer,data,value=bound(monkeypatch);before=deepcopy(value)
    assert e.verified_issuer(issuer,now=now)
    assert e.verified_job_count(value,data,issuer,now=now)==1
    assert value['current_open_job_count']is None and value['job_count']is None
    assert value['first_publication_verified']is value['employer_deadline_verified']is False
    assert value==before
    from prompt_evidence import prompt_evidence_copy
    assert 'raw_response_path'not in json.dumps(prompt_evidence_copy(value))


@pytest.mark.parametrize('damage',['stamp','raw_hash','manifest','issuer_ubn','issuer_name','issuer_stamp','master_owner',
    'receipt_owner','expired_owner','extended_owner','body_projection','count','bool_count','foreign_company','missing_receipt'])
def test_supplied_fields_or_cache_metadata_cannot_replace_independent_originals(damage,monkeypatch):
    e,now,owners,issuer,data,value=bound(monkeypatch);receipts=value['source_record_archive']['receipts']
    if damage=='stamp':receipts[-1]['fetched_at_epoch']+=1;receipts[-1]['raw_receipt']['retrieved_at']+=1
    elif damage=='raw_hash':receipts[-1]['raw_receipt']['raw_response_sha256']='0'*64
    elif damage=='manifest':receipts[-1]['metadata_manifest']['raw_response_sha256']='0'*64
    elif damage=='issuer_ubn':issuer['official_ubn']='12345678'
    elif damage=='issuer_name':issuer['legal_name']='其他股份有限公司'
    elif damage=='issuer_stamp':issuer['fetched_at_epoch']+=1
    elif damage=='master_owner':owners.pop('shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest())
    elif damage in('receipt_owner','expired_owner','extended_owner'):
        owner=owners['shared_provider:v1:'+sha256((e.RAW_PREFIX+receipts[-1]['url']).encode()).hexdigest()]
        if damage=='receipt_owner':owner['value']=None
        elif damage=='expired_owner':owner['fresh_until_epoch']=now-1
        else:owner['fresh_until_epoch']=now+86400
    elif damage=='body_projection':value['job_postings'][0]['title']='改寫內容'
    elif damage=='count':value['verified_sample_job_count']=2
    elif damage=='bool_count':value['verified_sample_job_count']=True
    elif damage=='foreign_company':data['company_identity']['stock_id']='2610'
    else:receipts.pop()
    assert e.verified_job_count(value,data,issuer,now=now)==0


def test_receipt_expiry_is_not_extended_by_owner_cache_rounding(monkeypatch):
    e,now,owners,issuer,data,value=bound(monkeypatch)
    stamp=value['source_record_archive']['receipts'][0]['fetched_at_epoch']
    assert e.verified_job_count(value,data,issuer,now=stamp+e.TTL)==0


@pytest.mark.parametrize('damage',['response_complete','ssl_verify_result','proxy_used','num_redirects','return_code','http_status','response_bytes'])
def test_partial_or_non_native_transport_cannot_create_a_receipt(damage):
    from data_fetch.market_sources import tigerair_yes123_evidence as e
    raw=synthetic_protocol()[0];native={'http_status':200,'http_status_observed':True,'response_complete':True,
        'http_request_sent':True,'return_code':0,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'response_bytes':len(raw)}
    native[damage]=False if damage=='response_complete'else 1
    with pytest.raises(ValueError):e.native_receipt(raw,e.PAGE,1.,native)
