import hashlib,json
import provider_sla
from provider_correlation import correlation_scope,source_operation
from official_response_evidence import read_response
from test_cmoney_native_receipts import transport,URL,module

def test_native_bytes_can_be_replayed_without_becoming_parsed_success(monkeypatch):
    events,calls,body=transport(monkeypatch)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='fetch'):
      with source_operation('social_sentiment','Social Forum Sentiment'):
        assert module._download(URL)is body
    assert len(calls)==len(events)==1
    event=events[0];receipt=event['raw_http_receipt']
    assert receipt['status']=='archived'
    assert read_response(receipt)==body
    assert receipt['raw_response_sha256']==event['response_sha256']==hashlib.sha256(body).hexdigest()
    assert receipt['http_status_observed']is True and receipt['response_complete']is True
    assert receipt['cache_hit']is False
    assert event['record_count']==0 and event['event_kind']=='http_transport_receipt'
    assert module.parse_finance_listing(read_response(receipt),'2356')==('',[])


import pytest
@pytest.mark.parametrize('mode',['exception','unavailable'])
def test_archive_failure_preserves_original_bytes_and_transport(monkeypatch,mode):
    import official_response_evidence as archive
    events,calls,body=transport(monkeypatch)
    def failed(*a,**k):
        if mode=='exception':raise OSError('disk unavailable')
        return {'status':'unavailable'}
    monkeypatch.setattr(archive,'archive_response',failed)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='fetch'):
        assert module._download(URL)is body
    assert len(events)==len(calls)==1
    assert events[0]['record_count']==0 and events[0].get('raw_http_receipt')is None

@pytest.mark.parametrize('code',[403,429,503,504])
def test_refusal_body_never_archived(monkeypatch,code):
    import official_response_evidence as archive
    events,calls,body=transport(monkeypatch,code=code,rc=22,body=b'access denied')
    archives=[];monkeypatch.setattr(archive,'archive_response',lambda *a,**k:archives.append(1))
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='fetch'):
        with pytest.raises(RuntimeError):module._download(URL)
    assert len(events)==len(calls)==1 and not archives


def test_persisted_original_is_bounded_transport_only(monkeypatch,tmp_path):
    import sqlite3
    from provider_acquisition import observation_kind
    writer=provider_sla.record_source_audit_entries
    events,calls,body=transport(monkeypatch)
    monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'events.sqlite3'))
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',writer)
    with correlation_scope(replace=True,ticker='2356.TW',fetch_id='fetch',operation_id='operation'):
        module._download(URL)
    with sqlite3.connect(tmp_path/'events.sqlite3')as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r)for r in db.execute('select * from provider_sla_events')]
    assert len(rows)==1
    row=rows[0];d=json.loads(row['details_json']);proof=d['original_http_receipts'][0]
    assert proof['response_sha256']==hashlib.sha256(body).hexdigest()
    assert proof['response_complete']is True and proof['original_cache_hit']is False
    assert proof['http_status_observed']is True and d['operation_id']=='operation'
    assert observation_kind({**row,'details':d})=='aggregate_count'
    assert 'client shell'not in row['details_json'] and 'headers'not in row['details_json']
