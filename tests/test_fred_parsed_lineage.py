import httpx,pytest
import macro_fetcher as m
import provider_sla
from provider_correlation import correlation_scope,source_operation

@pytest.mark.parametrize('body,usable',[(b'{"observations":[{"date":"2026-10-30","value":"4.25"}]}',1),(b'{"observations":[{"date":"2026-10-30","value":"."}]}',0)])
def test_original_native_body_is_bound_to_existing_parser_without_success_credit(monkeypatch,body,usable):
    rows=[]
    response=httpx.Response(200,content=body,request=httpx.Request('GET',m.FRED_OBSERVATIONS_URL+'?series_id=DGS10&api_key=PRIVATE'))
    monkeypatch.setattr(m,'sync_get',lambda *a,**k:response)
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      with source_operation('macro_indicators','FRED macro indicators'):
        result=m._fred_observations(None,'PRIVATE','DGS10',timeout=15,limit=10,sort_order='desc')
    assert result==response.json()['observations']
    transport=[r for r in rows if r['event_kind']=='http_transport_receipt']
    parsed=[r for r in rows if r['event_kind']=='http_parsed_receipt']
    assert len(transport)==len(parsed)==1
    assert parsed[0]['operation_id']==transport[0]['operation_id']
    assert parsed[0]['response_sha256']==transport[0]['response_sha256']
    assert parsed[0]['usable_count']==usable
    assert parsed[0]['record_count']==0
    assert 'PRIVATE' not in str(rows)
    from provider_acquisition import observation_kind
    row=parsed[0]
    assert observation_kind({**row,'details':row})=='aggregate_count'


@pytest.mark.parametrize('change',['cache','wrong_series','non_native','missing_operation','different_payload','error'])
def test_ambiguous_or_failed_responses_cannot_bind_parsed_evidence(monkeypatch,change):
    from fred_transport_receipts import observe_parsed_response
    rows=[];body=b'{"observations":[{"date":"2026-10-30","value":"4.25"}]}'
    response=httpx.Response(429 if change=='error'else 200,content=body,request=httpx.Request('GET',m.FRED_OBSERVATIONS_URL+'?series_id=DGS10&api_key=PRIVATE'))
    response.from_cache=change=='cache'
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    obs=response.json()['observations'] if change!='different_payload'else []
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch',**({}if change=='missing_operation'else {'operation_id':'operation'})):
        observe_parsed_response(response,series_id='VIXCLS'if change=='wrong_series'else 'DGS10',observations=obs,native_call=change!='non_native')
    assert rows==[]

def test_telemetry_error_does_not_change_provider_result(monkeypatch):
    body=b'{"observations":[{"date":"2026-10-30","value":"4.25"}]}'
    response=httpx.Response(200,content=body,request=httpx.Request('GET',m.FRED_OBSERVATIONS_URL+'?series_id=DGS10'))
    monkeypatch.setattr(m,'sync_get',lambda *a,**k:response)
    def fail(*a,**k):raise RuntimeError('audit unavailable')
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',fail)
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch',operation_id='operation'):
        assert m._fred_observations(None,'PRIVATE','DGS10',timeout=15,limit=10,sort_order='desc')==response.json()['observations']


def test_persisted_diagnostic_keeps_count_and_series_without_counting_acquisition(monkeypatch,tmp_path):
    import json,sqlite3
    from provider_acquisition import observation_kind
    monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'audit.sqlite3'))
    body=b'{"observations":[{"date":"2026-10-30","value":"4.25"}]}'
    response=httpx.Response(200,content=body,request=httpx.Request('GET',m.FRED_OBSERVATIONS_URL+'?series_id=DGS10&api_key=PRIVATE'))
    monkeypatch.setattr(m,'sync_get',lambda *a,**k:response)
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch',operation_id='operation'):
        m._fred_observations(None,'PRIVATE','DGS10',timeout=15,limit=10,sort_order='desc')
    with sqlite3.connect(tmp_path/'audit.sqlite3')as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r)for r in db.execute('select * from provider_sla_events')]
    parsed=[r for r in rows if json.loads(r['details_json']).get('event_kind')=='http_parsed_receipt']
    assert len(parsed)==1
    row=parsed[0];details=json.loads(row['details_json'])
    assert details['usable_count']==1
    assert details['component_statuses']['DGS10']['series_id']=='DGS10'
    originals=details['original_http_receipts']
    assert len(originals)==1
    assert originals[0]['response_sha256']==details['response_sha256']
    assert originals[0]['response_complete']is True and originals[0]['http_status_observed']is True
    assert originals[0]['original_cache_hit']is False
    assert 'PRIVATE' not in row['details_json'] and 'api_key'not in row['details_json']
    assert observation_kind({**row,'details':details})=='aggregate_count'


def test_archive_exact_public_bytes_and_replay_parser(monkeypatch,tmp_path):
    import json
    from fred_public_original import archive_public_response
    from official_response_evidence import read_response
    body=b'{"observations":[{"date":"2026-10-30","value":"4.25"}]}'
    response=httpx.Response(200,content=body)
    proof=archive_public_response(response,series_id='DGS10',payload=response.json())
    assert proof['status']=='archived'
    assert read_response(proof,max_bytes=2_000_000)==body
    assert m._parse_observation(json.loads(read_response(proof))['observations'][0])=={'date':'2026-10-30','value':4.25}
    assert 'api_key'not in str(proof)

@pytest.mark.parametrize('payload',[{'observations':[],'api_key':'PRIVATE'},{'observations':[{'date':'2026-10-30','value':'PRIVATE'}]},{'observations':[],'units':'PRIVATE'}])
def test_nonpublic_schema_never_enters_archive(monkeypatch,payload):
    import official_response_evidence as archive
    from fred_public_original import archive_public_response
    calls=[];monkeypatch.setattr(archive,'archive_response',lambda *a,**k:calls.append(1))
    assert archive_public_response(httpx.Response(200,json=payload),series_id='DGS10',payload=payload)is None
    assert not calls


def test_archive_rejects_payload_mismatch_and_unapproved_series(monkeypatch):
    import official_response_evidence as archive
    from fred_public_original import archive_public_response
    calls=[];monkeypatch.setattr(archive,'archive_response',lambda *a,**k:calls.append(1))
    response=httpx.Response(200,json={'observations':[]})
    assert archive_public_response(response,series_id='DGS10&api_key=PRIVATE',payload=response.json())is None
    assert archive_public_response(response,series_id='DGS10',payload={'observations':[{'date':'2026-10-30','value':'4.25'}]})is None
    assert not calls
