"""Real transport guards with only the native process boundary simulated."""
import time
import pytest
from test_shared_provider_cache import memory_cache
from test_tcfhc_conference_transport import network,response
from test_guc_conference import PDF,INDEX

@pytest.mark.parametrize('status',[403,429,503])
def test_guards_reject_normal_force_and_uncached_retries(network,monkeypatch,status):
    _,base=network
    from data_fetch.market_sources.guc_conference_transport import GucConferenceHttp
    from search_provider_runtime import SourceResponseError
    calls=[];monkeypatch.setattr(base,'remember_failure',lambda *a:{})
    def native(argv,*a,**kw):calls.append(argv);return response(argv,status)
    monkeypatch.setattr(base,'collect_capped_process',native)
    for opts in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):GucConferenceHttp(time.monotonic()+20,**opts).get_receipt(PDF)
    assert len(calls)==1

@pytest.mark.parametrize('url',[PDF+'?download=1',PDF+'#x',PDF.replace('https:','http:'),
 PDF.replace('www.guc-asic.com','www.guc-asic.com.evil.example'),PDF.replace('/2026_07_30/','/2026_07_31/'),
 PDF.replace('/2026_07_30/','/2026_99_30/'),PDF.replace('/upload/','/upload/../'),PDF.replace('8_','%38_'),
 INDEX+'?lang=zh',INDEX.replace('/en/','/zh/')])
def test_unqualified_route_never_starts_native_process(network,monkeypatch,url):
    _,base=network
    from data_fetch.market_sources.guc_conference_transport import GucConferenceHttp
    from search_provider_runtime import SourceResponseError
    monkeypatch.setattr(base,'collect_capped_process',lambda *a,**kw:pytest.fail('unexpected HTTP'))
    with pytest.raises(SourceResponseError):GucConferenceHttp(time.monotonic()+20).get_receipt(url)

def test_raw_pdf_epoch_and_normal_expiry_are_not_renewed(network,monkeypatch):
    _,base=network
    from data_fetch.market_sources.guc_conference_transport import GucConferenceHttp
    calls=[];clock={'epoch':time.time()};monkeypatch.setattr(time,'time',lambda:clock['epoch'])
    def native(argv,*a,**kw):calls.append(argv);return response(argv)
    monkeypatch.setattr(base,'collect_capped_process',native)
    first=GucConferenceHttp(time.monotonic()+20).get_receipt(PDF)[1]
    clock['epoch']+=10
    second=GucConferenceHttp(time.monotonic()+20).get_receipt(PDF)[1]
    assert second['cache_hit'] and second['retrieved_at']==first['retrieved_at'] and len(calls)==1
    args=calls[0]
    assert args[args.index('--retry')+1]=='0' and args[args.index('--max-redirs')+1]=='0'
    assert not any('authorization' in x.lower() or 'cookie' in x.lower() for x in args)
    clock['epoch']+=1801
    third=GucConferenceHttp(time.monotonic()+20).get_receipt(PDF)[1]
    assert not third['cache_hit'] and third['retrieved_at']==clock['epoch'] and len(calls)==2

def test_storage_unavailable_and_expired_deadline_never_start_http(network,monkeypatch):
    _,base=network
    import cache_store
    from data_fetch.market_sources.guc_conference_transport import GucConferenceHttp
    from search_provider_runtime import SourceResponseError
    monkeypatch.setattr(base,'collect_capped_process',lambda *a,**kw:pytest.fail('unexpected HTTP'))
    with pytest.raises(SourceResponseError) as expired:GucConferenceHttp(time.monotonic()-1).get_receipt(INDEX)
    assert expired.value.error_kind=='timeout'
    def fail(*a,**kw):raise OSError('test storage unavailable')
    monkeypatch.setattr(cache_store,'get_cache_json',fail)
    with pytest.raises(SourceResponseError) as failed:GucConferenceHttp(time.monotonic()+20).get_receipt(INDEX)
    assert failed.value.error_kind=='guard_storage_unavailable'
