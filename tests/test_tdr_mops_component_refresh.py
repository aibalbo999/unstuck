import asyncio
from copy import deepcopy
import json
import time

import pytest
from fastapi import HTTPException

from data_fetch.provider_base import CallableProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import ProviderResult
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import events, init_db
from test_tdr_mops_history import _source, NOW
from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements


def saved_tdr(storage,rows):
    name,keys,snapshot=saved_report(storage)
    snapshot['ticker']=snapshot['data']['ticker']='9103.TW'
    snapshot['data']['company_name']='美德醫療-DR'
    snapshot['data']['company_identity']={'official_name':'美德醫療-DR'}
    # An existing headline for the same event must survive in the archive.
    headline={'title':rows[0]['title'],'text':'美德醫療-DR 原有新聞標題',
              'date':rows[0]['date'],'link':'https://example.org/old-headline','source':'old publisher'}
    snapshot['data']['recent_catalysts']=[headline]
    storage.save_report(keys.data_key,json.dumps(snapshot).encode(),content_type='application/json')
    return name,keys,snapshot,headline


@pytest.mark.parametrize('status',['success','degraded_enrichment'])
def test_only_missing_tdr_original_component_is_acquired_and_saved(monkeypatch,tmp_path,status):
    init_db();get,post,_=_source(monkeypatch)
    rows,_=fetch_recent_company_announcements('9103.TW',now=NOW,get=get,post=post)
    storage=InMemoryStorage();name,keys,old,headline=saved_tdr(storage,rows);calls=[]
    def fetch(request,context):
        calls.append(request.ticker)
        audit={'source':'recent_catalysts','provider':'TWSE company announcement history',
               'status':status,'record_count':len(rows),'event_kind':'aggregate','http_request_sent':True,
               'http_request_count':5,'fetched_at_epoch':time.time()}
        return ProviderResult('recent_catalysts',audit['provider'],status,value=deepcopy(rows),audit=audit)
    def forbidden(*a):raise AssertionError('component acquired an unrelated source')
    service=StockDataService(registry=ProviderRegistry([
        CallableProvider('recent_catalysts','TWSE company announcement history',fetch),
        CallableProvider('recent_catalysts','Verified issuer news',forbidden),
        CallableProvider('market_data','forbidden core',forbidden),
    ]))
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='tdr_announcements',return_refreshed_data=True))
    after=json.loads(storage.get_report(keys.data_key).content)
    assert calls==['9103.TW'] and result['refresh_sources']==['tdr_announcements']
    assert len(after['data']['recent_catalysts'])==2
    assert any(x['record']==headline for x in after['data']['source_record_archive'])
    assert after['analysis_evidence']==old['analysis_evidence']
    for k in ('current_price','revenue_history','years','earnings_call','peer_discovery_results'):
        assert after['data'][k]==old['data'][k]
    assert after['source_audit'][:len(old['source_audit'])]==old['source_audit']
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert result['analysis_text_stale'] is True
    assert len(events())==1 and events()[0]['source']=='recent_catalysts'


def test_tdr_component_does_not_apply_to_other_ticker_or_full_override(tmp_path):
    storage=InMemoryStorage();name,keys,_=saved_report(storage)
    before=storage.get_report(keys.data_key).content
    service=StockDataService(fetcher=lambda *a:pytest.fail('unexpected full fetch'))
    with pytest.raises(HTTPException):
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
            refresh_service=service,source='tdr_announcements'))
    assert storage.get_report(keys.data_key).content==before
