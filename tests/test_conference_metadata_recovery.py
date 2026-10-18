"""Event metadata must not suppress body discovery for a full source TTL."""
from copy import deepcopy
import time
import pytest
from data_fetch.optional_provider_plan import collect_optional_providers
from data_fetch import CallableProvider, FetchRequest, ProviderRegistry

NOW = 1792109100.


def plan(monkeypatch, *, age, call=None, ticker='6189.TW'):
    monkeypatch.setattr(time, 'time', lambda: NOW)
    data = {'ticker':ticker,'quote_type':'EQUITY','_cache_hit':True,
            'earnings_call': call or {'date':'2025-11-17','materials':[{'url':'https://example.com/event'}],
                                     'transcript_available':False,'transcript_excerpt':''},
            'source_freshness':{'earnings_call':{'fetched_at_epoch':NOW-age}}}
    provider = CallableProvider('earnings_call','fixture',lambda *a: None)
    result = collect_optional_providers(FetchRequest.from_ticker(ticker), ProviderRegistry([provider]), data, ticker,
                                       sources=('earnings_call',))
    return result, provider, data


def test_metadata_only_is_revisited_after_six_hours(monkeypatch):
    (providers, decisions), provider, _ = plan(monkeypatch, age=21600)
    assert decisions['earnings_call'] and providers == [provider]


@pytest.mark.parametrize('age', [0, 21599])
def test_recent_metadata_uses_existing_grace_period(monkeypatch, age):
    (providers, decisions), _, _ = plan(monkeypatch, age=age)
    assert providers == [] and decisions['earnings_call'] is False


@pytest.mark.parametrize('call', [
    {'transcript_excerpt':'Published actual transcript'},
    {'documents':[{'pages':[{'page_number':1,'text':'Published presentation body'}]}]},
])
def test_existing_body_keeps_original_freshness_policy(monkeypatch, call):
    (providers, decisions), _, _ = plan(monkeypatch, age=21600, call=call)
    assert providers == [] and decisions['earnings_call'] is False
