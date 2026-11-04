"""Report refresh intent cannot bypass or accidentally skip shared career TTLs."""
from copy import deepcopy
from dataclasses import asdict
import pytest

@pytest.mark.parametrize('ticker,module,function',[('2412.TW','data_fetch.cht_careers_provider','cht_context_result'),('2633.TW','data_fetch.thsrc_careers_provider','thsrc_context_result')])
@pytest.mark.parametrize('force',[True,False])
def test_official_career_admission_always_uses_normal_cache_and_preserves_caller(monkeypatch,ticker,module,function,force):
    from importlib import import_module
    from data_fetch.types import FetchRequest,ProviderResult
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    request=FetchRequest.from_ticker(ticker,force_refresh=force,record_provider_sla=False)
    before=asdict(request);context={'data':{'ticker':ticker},'source_only_recovery':True};prior=deepcopy(context);calls=[]
    result=ProviderResult('alternative_data','104 & 1111 job openings','success',value={'saved_epoch':123},audit={'cache_hit':True,'http_request_count':0,'fetched_at_epoch':123})
    def official(req,ctx):
        assert req.ticker==ticker and req.options.force_refresh is False
        assert req.options.record_provider_sla is False
        assert ctx is context
        calls.append(req);return result
    monkeypatch.setattr(import_module(module),function,official)
    monkeypatch.setattr(AlternativeJobOpeningsProvider,'_fetch_uncached',lambda *a:pytest.fail('usable official cache must not trigger portal request'))
    returned=AlternativeJobOpeningsProvider().fetch(request,context)
    assert returned is result and returned.audit['fetched_at_epoch']==123 and returned.audit['http_request_count']==0
    assert len(calls)==1 and asdict(request)==before and context==prior


def test_unrelated_employer_keeps_existing_portal_request_options(monkeypatch):
    from data_fetch.types import FetchRequest,ProviderResult
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch import context_provider_cache
    req=FetchRequest.from_ticker('5314.TWO',force_refresh=True);seen=[]
    def cached(provider,request,context,fn):seen.append(request);return ProviderResult('alternative_data',provider.name,'unavailable',value=None)
    monkeypatch.setattr(context_provider_cache,'cached_context_result',cached)
    AlternativeJobOpeningsProvider().fetch(req,{'data':{'ticker':'5314.TWO'}})
    assert seen==[req]and seen[0].options.force_refresh is True


@pytest.mark.parametrize('ticker,module,function',[('2412.TW','data_fetch.cht_careers_provider','cht_context_result'),('2633.TW','data_fetch.thsrc_careers_provider','thsrc_context_result')])
def test_skip_optional_http_does_not_enter_official_career_transport(monkeypatch,ticker,module,function):
    from importlib import import_module
    from data_fetch.types import FetchRequest,ProviderResult
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch import context_provider_cache
    req=FetchRequest.from_ticker(ticker,force_refresh=True,skip_optional_http=True)
    monkeypatch.setattr(import_module(module),function,lambda *a:pytest.fail('optional official source was excluded'))
    # Existing generic context path is outside this admission change; no real transport in this test.
    monkeypatch.setattr(context_provider_cache,'cached_context_result',lambda provider,*a:ProviderResult('alternative_data',provider.name,'unavailable',value=None))
    assert AlternativeJobOpeningsProvider().fetch(req,{'data':{'ticker':ticker}}).status=='unavailable'
