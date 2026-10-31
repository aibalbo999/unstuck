"""Real corporate master transport plus saved articles: shared master is not news."""
from datetime import datetime,timezone
import time
from test_sym_issuer_news import harness, valid_data, NOW
from test_sanyang_news_bundle import corporate_http
from test_issuer_news_shared_roster import install_roster


def test_valid_one_hour_company_master_does_not_erase_fresh_corporate_and_global_news(harness, monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as transport
    from data_fetch.market_sources import sanyang_news_bundle as bundle
    raw,stamp,key,cache=install_roster(target_changes={'公司代號':'2206','公司名稱':'三陽工業股份有限公司','公司簡稱':'三陽工業','英文簡稱':'SYM','網址':'https://www.sanyang.com.tw','營利事業統一編號':'24004006'})
    fixture=corporate_http()
    http=transport.IssuerNewsHttp(time.monotonic()+20)
    real=http.get
    def get(url):
        if url==transport.ROSTER_URL:return real(url)
        result=fixture.get(url)
        http.components.append(fixture.components[-1]);http.http_request_count=fixture.http_request_count
        return result
    http.get=get
    values,audit=bundle.fetch_recent_sanyang_news(now=datetime.fromtimestamp(NOW,timezone.utc),corporate_http=http)
    assert len(values)==3,audit
    assert audit['fetched_at_epoch']==stamp
    assert bundle.guard_bundle(values,audit,valid_data())


def shared_bundle():
    from data_fetch.market_sources import issuer_news_transport as transport
    from data_fetch.market_sources import sanyang_news_bundle as bundle
    raw,stamp,key,cache=install_roster(target_changes={'公司代號':'2206','公司名稱':'三陽工業股份有限公司','公司簡稱':'三陽工業','英文簡稱':'SYM','網址':'https://www.sanyang.com.tw','營利事業統一編號':'24004006'})
    fixture=corporate_http();http=transport.IssuerNewsHttp(time.monotonic()+20);real=http.get
    def get(url):
        if url==transport.ROSTER_URL:return real(url)
        result=fixture.get(url);http.components.append(fixture.components[-1]);http.http_request_count=fixture.http_request_count;return result
    http.get=get
    values,audit=bundle.fetch_recent_sanyang_news(now=datetime.fromtimestamp(NOW,timezone.utc),corporate_http=http)
    assert len(values)==3
    return bundle,values,audit,key,cache


def test_shared_master_preserves_original_age_and_expiry(harness):
    from cache_store import get_cache_json
    bundle,values,audit,key,cache=shared_bundle()
    assert audit['status']=='success' and audit['http_request_count']==9
    assert audit['fetched_at_epoch']==NOW-3600
    assert get_cache_json(key)==cache
    assert bundle.guard_bundle(values,audit,valid_data())
    assert get_cache_json(key)==cache


import pytest
@pytest.mark.parametrize('change',['expired','different_original','shorter_expiry','extended_expiry','missing_archive'])
def test_master_owner_or_original_change_blocks_bundle_replay(harness,monkeypatch,change):
    from copy import deepcopy
    from cache_store import set_cache_json
    from runtime_paths import current_runtime_paths
    bundle,values,audit,key,cache=shared_bundle();cache=deepcopy(cache)
    if change=='expired':monkeypatch.setattr(time,'time',lambda:NOW+86400)
    elif change=='different_original':cache['value']['response_sha256']='f'*64
    elif change=='shorter_expiry':cache['fresh_until_epoch']=NOW-1
    elif change=='extended_expiry':cache['fresh_until_epoch']=NOW+86401
    else:(current_runtime_paths().cache_dir/'official-response-evidence'/(cache['value']['response_sha256']+'.gz')).unlink()
    set_cache_json(key,cache,ttl_seconds=86400)
    assert not bundle.guard_bundle(values,audit,valid_data())


@pytest.mark.parametrize('change',['article_age','master_epoch','master_hash','master_alias_on_article','record_master_mismatch'])
def test_shared_master_exception_never_extends_or_unbinds_news(harness,change):
    bundle,values,audit,key,cache=shared_bundle()
    ca=audit['component_audits']['corporate'];master=ca['component_receipts'][0]
    if change=='article_age':ca['component_receipts'][-1]['fetched_at_epoch']=NOW-3600
    elif change=='master_epoch':master['fetched_at_epoch']=NOW-10
    elif change=='master_hash':master['source_payload_sha256']='e'*64
    elif change=='master_alias_on_article':ca['component_receipts'][-1].update(master,url=ca['component_receipts'][-1]['url'])
    else:ca_records=audit['component_records']['corporate'];ca_records[0]['issuer_news_receipt']['master_response_sha256']='e'*64
    assert not bundle.guard_bundle(values,audit,valid_data())


def test_rejected_bundle_after_real_http_counts_as_failed_acquisition(harness):
    from data_fetch.market_sources import sanyang_news_bundle as bundle
    from provider_acquisition import project_acquisition_events
    import json
    http=corporate_http();real=http.get
    def get(url):
        raw=real(url)
        if '/busnessnews-page' in url:http.components[-1]['fetched_at_epoch']=NOW-3600
        return raw
    http.get=get
    values,audit=bundle.fetch_recent_sanyang_news(now=datetime.fromtimestamp(NOW,timezone.utc),corporate_http=http)
    assert not values and audit['status']=='error' and audit['http_request_count']>0
    rows=[{'source':'recent_catalysts','provider':'Verified issuer news','status':'error','record_count':0,'message':'test','created_at':NOW,'details_json':json.dumps(audit)}]
    projected=project_acquisition_events(rows,window='last_24h',now=NOW)['sources'][0]
    assert projected['failed_count']==projected['fetch_attempts']==1
    assert projected['local_block_count']==0
