"""Independent public-boundary review; synthetic native seam, never network."""
import asyncio
from copy import deepcopy
import hashlib
import json

import pytest
from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import FetchRequest
from test_official_announcement_source_refresh import IssuerReplay, identity, service, report
from test_report_refresh_acquisition_audit import init_db, events


def test_complete_cold_originals_survive_optional_aggregate_write_outage(monkeypatch):
    import cache_store
    init_db(); replay=IssuerReplay(monkeypatch)
    write=cache_store.set_cache_json
    def no_aggregate(key,*args,**kwargs):
        if key.startswith('shared_provider:v1:'):
            raise OSError('isolated aggregate persistence outage')
        return write(key,*args,**kwargs)
    monkeypatch.setattr(cache_store,'set_cache_json',no_aggregate)
    result=asyncio.run(service().fetch_source_async(FetchRequest.from_ticker('2851.TW'),
        'official_announcements',context={'data':identity()}))
    assert len(replay.calls)==4
    assert len(result.data['recent_catalysts'])==3, result.source_audit
    assert result.source_audit[0]['status']=='success'
    assert events()[-1]['record_count']==3


def test_final_guard_cannot_return_earlier_body_after_expiry_during_later_row_read(monkeypatch):
    import official_announcement_source_refresh as subject
    from data_fetch.market_sources import twse_announcement_progress as progress
    init_db(); replay=IssuerReplay(monkeypatch)
    class LastReadDelay(TwseCompanyHistoryProvider):
        def fetch(self,request,context=None):
            result=super().fetch(request,context)
            first=result.audit['source_record_archive'][0]
            key=progress.PREFIX+first['request_fingerprint']
            value,_=replay.cache._entries[key]
            expiry=replay.epoch+.05
            replay.cache._entries[key]=(value,expiry)
            result.audit['progress_fresh_until_epoch']=expiry
            original=progress.current_admission
            calls=0
            def slow(entry,**kwargs):
                nonlocal calls
                calls+=1
                # verify_value has checked all3; guard_result's second final
                # then checks first/second. Delay only the last storage read.
                if calls==6: replay.advance(.1)
                return original(entry,**kwargs)
            monkeypatch.setattr(progress,'current_admission',slow)
            return result
    svc=StockDataService(registry=ProviderRegistry([LastReadDelay()]))
    result=asyncio.run(svc.fetch_source_async(FetchRequest.from_ticker('2851.TW'),
        'official_announcements',context={'data':identity()}))
    assert len(replay.calls)==4
    assert result.data['recent_catalysts']==[], result.source_audit
    assert events()[-1]['status']=='error' and events()[-1]['record_count']==0

def test_self_consistent_cold_receipt_retiming_cannot_replace_original_epoch(monkeypatch):
    init_db(); replay=IssuerReplay(monkeypatch)
    class Retimed(TwseCompanyHistoryProvider):
        def fetch(self,request,context=None):
            result=super().fetch(request,context)
            # All bodies really arrived at distinct native epochs. This changes
            # their metadata to completion while keeping raw bytes/hash valid.
            # Existing independent body rows retain the original receipt.
            stamp=replay.epoch
            for entry in result.audit['source_record_archive'][:-1]:
                entry['receipt']['retrieved_at']=stamp
                entry['fresh_until_epoch']=stamp+1800
                entry['reusable']=False
            result.audit['body_fetched_at_epoch']=stamp
            result.audit['fetched_at_epoch']=stamp
            result.audit['progress_fresh_until_epoch']=min(
                x['fresh_until_epoch'] for x in result.audit['source_record_archive'][-1]['indexes'])
            return result
    result=asyncio.run(StockDataService(registry=ProviderRegistry([Retimed()])).fetch_source_async(
        FetchRequest.from_ticker('2851.TW'),'official_announcements',context={'data':identity()}))
    assert len(replay.calls)==4
    assert result.data['recent_catalysts']==[], result.source_audit
    assert events()[-1]['status']=='error' and events()[-1]['record_count']==0

def test_new_complete_cold_with_expired_prior_row_and_all_cache_writes_unavailable(monkeypatch):
    init_db(); replay=IssuerReplay(monkeypatch)
    svc=service(); request=FetchRequest.from_ticker('2851.TW')
    first=asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(first.data['recent_catalysts'])==3
    first_epoch=first.source_audit[0]['fetched_at_epoch']
    replay.advance(1801)
    old_rows=deepcopy(replay.cache._entries)
    def unavailable(*args,**kwargs):
        raise OSError('isolated all cache persistence outage')
    monkeypatch.setattr(replay.cache,'set_json',unavailable)
    current=asyncio.run(svc.fetch_source_async(request,'official_announcements',context={'data':identity()}))
    assert len(replay.calls)==8
    assert len(current.data['recent_catalysts'])==3, current.source_audit
    audit=current.source_audit[0]
    assert audit['status']=='success' and audit['fetched_at_epoch']>first_epoch
    assert audit['detail_new_body_count']==3 and audit['body_cache_hit'] is False
    assert all(item['reusable'] is False for item in audit['source_record_archive'][:-1])
    for key,value in old_rows.items():
        if key.startswith('twse-announcement-original:'):
            assert replay.cache._entries[key]==value


def test_expiry_while_final_merge_reads_later_row_preserves_saved_payload(monkeypatch,tmp_path):
    from fastapi import HTTPException
    from report_refresh_service import refresh_report_data_snapshot
    from data_fetch.market_sources import twse_announcement_progress as progress
    init_db(); replay=IssuerReplay(monkeypatch)
    storage,name,keys,old=report(); before=storage.get_report(keys.data_key).content
    svc=service(); original_fetch=svc.fetch_source_async
    async def shorten_after_service(*args,**kwargs):
        result=await original_fetch(*args,**kwargs)
        first=result.source_audit[0]['source_record_archive'][0]
        key=progress.PREFIX+first['request_fingerprint'];value,_=replay.cache._entries[key]
        expiry=replay.epoch+.05;replay.cache._entries[key]=(value,expiry)
        result.source_audit[0]['progress_fresh_until_epoch']=expiry
        original=progress.current_admission;calls=0
        def slow(entry,**kw):
            nonlocal calls
            calls+=1
            if calls==6: replay.advance(.1)
            return original(entry,**kw)
        monkeypatch.setattr(progress,'current_admission',slow)
        return result
    monkeypatch.setattr(svc,'fetch_source_async',shorten_after_service)
    with pytest.raises(HTTPException) as error:
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
                    refresh_service=svc,source='official_announcements'))
    assert error.value.status_code==502
    assert storage.get_report(keys.data_key).content==before
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert len(replay.calls)==4
