"""Fresh core metadata cannot hide an already verified optional document."""
from copy import deepcopy
import asyncio,time
import pytest
from test_mops_semantic_role_pages import semantic,data
from test_mops_presentation import harness

TICKER='6282.TW'
def metadata(monkeypatch):
    from data_fetch import optional_provider_plan as plan
    monkeypatch.setattr(plan,'source_is_stale',lambda *a,**k:False)
    monkeypatch.setattr(plan,'source_timestamp_epoch',lambda *a,**k:time.time())
    d=data(TICKER);d.update(_cache_hit=True,current_price=100,eps=1,
        earnings_call={'ticker':TICKER,'source':'MOPS investor conference','documents':[],
                       'transcript_excerpt':'','date':'2026-09-15'},source_audit=[])
    return d

def selected(d,ticker=TICKER):
    from data_fetch.optional_provider_plan import collect_optional_providers
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    return collect_optional_providers(FetchRequest.from_ticker(ticker),ProviderRegistry([EarningsCallProvider()]),d,ticker,sources=('earnings_call',))[1]['earnings_call']


def test_verified_body_is_reused_in_normal_optional_workflow_without_http(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    from data_fetch.workflow import _run_optional_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    old=metadata(monkeypatch);v=s.fetch_presentation_context(TICKER)
    assert selected(deepcopy(old)),'Fresh metadata must discover the already available verified body'
    semantic[1].clear()
    result=asyncio.run(_run_optional_provider_plan(FetchRequest.from_ticker(TICKER),ProviderRegistry([EarningsCallProvider()]),old,sources=('earnings_call',)))
    assert result['earnings_call']['documents'] and not semantic[1]
    assert result['earnings_call']['fetched_at_epoch']==v['fetched_at_epoch']
    assert result['current_price']==100 and result['eps']==1
    assert any(x.get('source')=='earnings_call' and x.get('cache_hit') is True for x in result['source_audit'])


def test_without_a_body_hint_metadata_keeps_normal_discovery_cadence(semantic,monkeypatch):
    assert not selected(metadata(monkeypatch))


def test_discovered_body_remains_scheduled_after_original_receipts_expire(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    from data_fetch import optional_provider_plan as plan
    from cache_store import get_cache_json
    import mops_body_cache as hints
    d=metadata(monkeypatch);s.fetch_presentation_context(TICKER)
    hint=get_cache_json(hints.PREFIX+TICKER)
    monkeypatch.setattr(time,'time',lambda:hint['valid_until_epoch']+1)
    monkeypatch.setattr(plan,'source_timestamp_epoch',lambda *a,**k:time.time()-1801)
    assert not hints.body_ready(TICKER),'Expired hints must not claim current original proofs'
    assert selected(d),'Discovery must survive proof expiry until the metadata discovery interval'


def test_discovery_marker_cannot_survive_its_own_absolute_deadline(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    from cache_store import get_cache_json
    import mops_body_cache as hints
    s.fetch_presentation_context(TICKER);hint=get_cache_json(hints.PREFIX+TICKER)
    # Retained bytes cannot extend either clock, even if a cache backend keeps them.
    monkeypatch.setattr(hints,'get_cache_json',lambda *a,**k:hint)
    monkeypatch.setattr(time,'time',lambda:hint['discovery_until_epoch'])
    assert not hints.body_discovered(TICKER) and not hints.body_ready(TICKER)


def test_expired_original_receipts_override_fresh_optional_audit(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    d=metadata(monkeypatch);d['earnings_call']=s.fetch_presentation_context(TICKER)
    assert not selected(deepcopy(d))
    now=time.time();monkeypatch.setattr(time,'time',lambda:now+1800)
    assert selected(d),'Fresh audit time cannot extend the native original lifetime'


def test_missing_role_schema_requires_safe_reassembly_from_originals(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    d=metadata(monkeypatch);d['earnings_call']=s.fetch_presentation_context(TICKER)
    d['earnings_call']['documents'][0].pop('role_page_allowlist')
    assert selected(d)


def test_hint_is_not_evidence_and_cannot_bypass_original_verification(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    from data_fetch.workflow import _run_optional_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    old=metadata(monkeypatch);s.fetch_presentation_context(TICKER)
    assert selected(deepcopy(old))
    monkeypatch.setattr(s,'verify_context',lambda *a,**k:False)
    result=asyncio.run(_run_optional_provider_plan(FetchRequest.from_ticker(TICKER),ProviderRegistry([EarningsCallProvider()]),old,sources=('earnings_call',)))
    assert not result['earnings_call'].get('documents')


@pytest.mark.parametrize(('field','wrong'),[('ticker','9945.TW'),('policy','unknown'),('observed_at_epoch',True),
                                           ('observed_at_epoch',float('nan')),('valid_until_epoch',float('inf')),
                                           ('content_sha256','bad'),('discovery_until_epoch',True),
                                           ('discovery_until_epoch',float('inf'))])
def test_corrupted_discovery_hints_fail_closed(semantic,monkeypatch,field,wrong):
    from data_fetch.market_sources import mops_presentation as s
    import mops_body_cache as hints
    from cache_store import get_cache_json
    s.fetch_presentation_context(TICKER)
    hint=get_cache_json(hints.PREFIX+TICKER);assert hints.body_ready(TICKER)
    hint[field]=wrong;monkeypatch.setattr(hints,'get_cache_json',lambda *a,**k:hint)
    assert not hints.body_ready(TICKER)


def test_hint_expires_at_earliest_original_not_new_cache_write_time(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    import mops_body_cache as hints
    from cache_store import get_cache_json
    s.fetch_presentation_context(TICKER);hint=get_cache_json(hints.PREFIX+TICKER)
    monkeypatch.setattr(hints,'get_cache_json',lambda *a,**k:hint)
    monkeypatch.setattr(time,'time',lambda:hint['valid_until_epoch'])
    assert not hints.body_ready(TICKER)


def test_hint_storage_failure_does_not_reject_a_verified_document(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    import mops_body_cache as hints
    def unavailable(*a,**k):raise OSError('cache unavailable')
    monkeypatch.setattr(hints,'set_cache_json',unavailable)
    value=s.fetch_presentation_context(TICKER)
    assert s.verify_context(value,TICKER)


def test_legacy_mops_original_expiry_is_not_hidden_by_fresh_audit(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    from test_mops_presentation import valid_data
    d=metadata(monkeypatch);d.update(valid_data('2330.TW'))
    d['earnings_call']=s.fetch_presentation_context('2330.TW')
    assert not selected(deepcopy(d),'2330.TW')
    now=time.time();monkeypatch.setattr(time,'time',lambda:now+1800)
    assert selected(d,'2330.TW')


def test_marked_but_empty_document_array_is_refreshed_without_exception(semantic,monkeypatch):
    d=metadata(monkeypatch);d['earnings_call']={'ticker':TICKER,'source':'MOPS published presentation','documents':[],'mops_material_receipt':{}}
    assert selected(d)


def test_unknown_original_policy_requires_authoritative_reassembly(semantic,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    d=metadata(monkeypatch);d['earnings_call']=s.fetch_presentation_context(TICKER)
    d['earnings_call']['mops_material_receipt']['policy']='unsupported-original-policy'
    assert selected(d)
