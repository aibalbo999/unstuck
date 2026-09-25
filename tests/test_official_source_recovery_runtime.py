"""Official source successes reset only the failure history they observed."""
import pytest

from test_official_source_recovery import Response, SBL, t86


@pytest.fixture
def guarded(monkeypatch):
    import search_provider_runtime as runtime
    state, events, now = {}, [], [1000.0]
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: state.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime.time, 'time', lambda: now[0])
    monkeypatch.setattr(runtime, 'record_observation', lambda *a, **kw: events.append(kw))
    return runtime, state, events, now


def endpoint(name, monkeypatch, callback, empty=False):
    if name == 'institutional':
        import official_institutional_source as source
        import external_http_client
        monkeypatch.setattr(external_http_client, 'sync_get', callback)
        payload=t86('2026-09-24')
        if empty: payload['data']=[]
        return lambda: source._fetch_report('TWSE','2026-09-24',5), source.TWSE_SOURCE, 'institutional_daily', payload
    if name == 'borrowed':
        import tpex_borrowed_short_source as source
        return lambda: source._fetch_report(callback,5), source.SOURCE, 'borrowed_short', [] if empty else [SBL]
    import tpex_credit_source as source
    return lambda: source._fetch_report(callback,5), source.SOURCE, 'margin_balance', [] if empty else [{'Date':'1150924','SecuritiesCompanyCode':'6488'}]


@pytest.mark.parametrize('name',['institutional','borrowed','margin'])
@pytest.mark.parametrize('empty',[False,True])
def test_failure_success_failure_restarts_at_first_cooldown(name, empty, monkeypatch, guarded):
    runtime,state,events,now=guarded
    action={'error':True}
    def callback(*a,**kw):
        if action['error']: raise TimeoutError('bounded upstream timeout')
        return Response(payload)
    fetch,provider,kind,payload=endpoint(name,monkeypatch,callback,empty)
    key=runtime.scope_key(provider,endpoint=kind)
    with pytest.raises(TimeoutError): fetch()
    assert state[key]['consecutive_failures']==1
    now[0]+=61
    action['error']=False
    fetch()
    assert state[key].get('consecutive_failures',0)==0
    action['error']=True
    with pytest.raises(TimeoutError):fetch()
    assert state[key]['consecutive_failures']==1
    assert state[key]['retry_at']==now[0]+60
    assert [e['outcome'] for e in events]==['failure','valid_empty' if empty else 'results','failure']


@pytest.mark.parametrize('name',['institutional','borrowed','margin'])
def test_success_does_not_erase_newer_concurrent_failure(name, monkeypatch, guarded):
    runtime,state,events,now=guarded
    def callback(*a,**kw):
        runtime.remember_failure(key,TimeoutError('concurrent failure'))
        return Response(payload)
    fetch,provider,kind,payload=endpoint(name,monkeypatch,callback)
    key=runtime.scope_key(provider,endpoint=kind)
    runtime.remember_failure(key,TimeoutError('prior failure'))
    now[0]+=61
    fetch()
    assert state[key]['consecutive_failures']==2
    assert runtime.cooldown_state(key)['retry_at']==now[0]+120


@pytest.mark.parametrize('name',['institutional','borrowed','margin'])
def test_http_200_parse_failure_keeps_failure_history(name, monkeypatch, guarded):
    runtime,state,events,now=guarded
    fetch,provider,kind,_=endpoint(name,monkeypatch,lambda *a,**kw:Response({'unknown':'schema'}))
    key=runtime.scope_key(provider,endpoint=kind)
    runtime.remember_failure(key,TimeoutError('prior failure'))
    now[0]+=61
    with pytest.raises(ValueError):fetch()
    assert state[key]['consecutive_failures']==2
    assert state[key]['error_kind']=='parse_error'


def test_official_budget_is_rechecked_after_cache_access(monkeypatch):
    import official_institutional_source as source
    import shared_provider_cache
    clock=[0.0]; calls=[]
    monkeypatch.setattr(source.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(source,'expected_sessions',lambda *a:['2026-09-24'])
    monkeypatch.setattr(source,'_fetch_report',lambda *a:calls.append(a) or {'date':'2026-09-24','rows':{}})
    def delayed_cache(key,fetch,**kwargs):
        assert kwargs['lock_wait_seconds']==0
        clock[0]=13.0
        return shared_provider_cache._uncached(fetch)
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',delayed_cache)
    _,diagnostic=source.recover_institutional_observations('2330.TW',{},now_epoch=1790300000,limit=30)
    assert not calls
    assert diagnostic['budget_exhausted'] is True


@pytest.mark.parametrize('name',['institutional','borrowed','margin'])
def test_same_endpoint_is_held_through_success_state_write(name, monkeypatch, guarded):
    """Pause after reset's state read: a contender must not reach HTTP or write."""
    import threading
    runtime,state,events,now=guarded
    at_write=threading.Event(); release=threading.Event(); requests=[]; errors=[]
    first_reads=[0]
    def get(key):
        value=state.get(key)
        if threading.current_thread().name=='official-first':
            first_reads[0]+=1
            if first_reads[0]==3:
                at_write.set()
                assert release.wait(3), 'test must release state write'
        return value
    monkeypatch.setattr(runtime,'get_cache_json',get)
    def callback(*a,**kw):
        requests.append(threading.current_thread().name)
        if threading.current_thread().name!='official-first':raise TimeoutError('next actual request failed')
        return Response(payload)
    fetch,provider,kind,payload=endpoint(name,monkeypatch,callback)
    key=runtime.scope_key(provider,endpoint=kind)
    runtime.remember_failure(key,TimeoutError('old failure'));now[0]+=61
    def first():
        try:fetch()
        except Exception as exc:errors.append(exc)
    worker=threading.Thread(target=first,name='official-first')
    worker.start()
    try:
        assert at_write.wait(3), 'first request must reach success state write'
        with pytest.raises(runtime.SourceResponseError) as caught:fetch()
        assert caught.value.error_kind=='single_flight_busy'
        assert requests==['official-first']
        assert state[key]['consecutive_failures']==1  # Existing history untouched while busy.
    finally:
        release.set();worker.join(3)
    assert not worker.is_alive() and not errors
    assert state[key]['consecutive_failures']==0
    with pytest.raises(TimeoutError):fetch()
    assert state[key]['consecutive_failures']==1
    assert state[key]['retry_at']==now[0]+60
    assert [e for e in events if e.get('outcome')=='busy'][0]['sent'] is False


@pytest.mark.parametrize('name',['institutional','borrowed','margin'])
@pytest.mark.parametrize('fails',[False,True])
def test_lost_endpoint_ownership_prevents_all_failure_state_writes(name,fails,monkeypatch,guarded):
    from contextlib import contextmanager
    import search_admission
    runtime,state,events,now=guarded
    owned=[True]
    @contextmanager
    def admission(key,**kwargs):yield lambda:owned[0]
    monkeypatch.setattr(search_admission,'endpoint_admission',admission)
    def callback(*a,**kw):
        owned[0]=False
        # Represents the new owner publishing an authoritative cooldown.
        state[key]={'consecutive_failures':7,'retry_at':now[0]+999,'error_kind':'rate_limited'}
        if fails:raise TimeoutError('stale lease result')
        return Response(payload)
    fetch,provider,kind,payload=endpoint(name,monkeypatch,callback)
    key=runtime.scope_key(provider,endpoint=kind)
    if fails:
        with pytest.raises(TimeoutError):fetch()
    else:fetch()
    assert state[key]=={'consecutive_failures':7,'retry_at':now[0]+999,'error_kind':'rate_limited'}
    if fails:assert events[-1]['details']['state_write_skipped']=='lease_lost'


@pytest.mark.parametrize('name',['institutional','borrowed','margin'])
def test_unreadable_endpoint_guard_does_not_send_http_or_write_failure(name,monkeypatch,guarded):
    runtime,state,events,now=guarded
    requests=[]
    fetch,provider,kind,_=endpoint(name,monkeypatch,lambda *a,**kw:requests.append(1))
    monkeypatch.setattr(runtime,'get_cache_json',lambda key:(_ for _ in ()).throw(OSError('guard unavailable')))
    with pytest.raises(runtime.SourceResponseError) as caught:fetch()
    assert caught.value.error_kind=='guard_storage_unavailable'
    assert not requests and not state
    assert events[-1]['sent'] is False
