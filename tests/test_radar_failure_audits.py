"""Radar failures keep actual observations without changing retry decisions."""
import asyncio
from types import SimpleNamespace
import pytest
import provider_sla
import data_fetch.service as service
from data_fetch.types import FetchRequest,ProviderResult
from provider_correlation import current_correlation,current_source_identity,correlation_scope


class Provider:
    def __init__(self,source,status='success',value=None,audit=None,error=None):
        self.source=source;self.name='Test '+source;self.status=status
        self.value={'observed':True}if value is None else value
        self.audit=audit;self.error=error;self.calls=0;self.context=None
    async def fetch_async(self,request,context):
        self.calls+=1;self.context=current_correlation()
        assert current_source_identity()==(self.source,self.name)
        if self.error is not None:raise self.error
        audit=self.audit if self.audit is not None else {
            'source':self.source,'provider':self.name,'status':self.status,
            'record_count':int(bool(self.value)),'cache_hit':False,'event_kind':'fetch'}
        return ProviderResult(self.source,self.name,self.status,self.value,audit)


def app(providers):
    return service.StockDataService(registry=SimpleNamespace(first_provider=lambda request,source:providers.get(source)))


@pytest.fixture
def events(monkeypatch):
    rows=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:rows.extend(entries))
    monkeypatch.setattr(service,'record_source_audit_entries',lambda entries:rows.extend(entries))
    return rows


@pytest.mark.parametrize('status',['error','degraded_enrichment','unavailable','success'])
@pytest.mark.parametrize('enabled',[True,False])
def test_unusable_result_keeps_exact_audit_and_rejection(events,status,enabled):
    p=Provider('taiwan_open_data',status=status,value={})
    with pytest.raises(RuntimeError,match='雷達資料來源暫時不可用'):
        asyncio.run(app({p.source:p}).fetch_radar_async(FetchRequest.from_ticker('1623.TW',record_provider_sla=enabled),(p.source,)))
    assert p.calls==1 and len(events)==int(enabled)
    if enabled:
        assert events[0]['status']==status and events[0]['operation_id']==p.context['operation_id']
        assert events[0]['record_count']==0 and 'http_request_sent' not in events[0]


@pytest.mark.parametrize('enabled',[True,False])
@pytest.mark.parametrize('error',[TimeoutError('private token=secret'),RuntimeError('private token=secret'),asyncio.CancelledError('cancelled')])
def test_thrown_error_is_same_object_with_unknown_transport_and_restored_scope(events,error,enabled):
    p=Provider('taiwan_open_data',error=error)
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='outer'):
        before=current_correlation()
        with pytest.raises(type(error))as caught:
            asyncio.run(app({p.source:p}).fetch_radar_async(FetchRequest.from_ticker('1623.TW',record_provider_sla=enabled),(p.source,)))
        assert caught.value is error and current_correlation()==before and current_source_identity()is None
    assert p.calls==1 and len(events)==int(enabled)
    if not enabled:return
    row=events[0]
    assert row['operation_id']==p.context['operation_id'] and row['fetch_id']==p.context['fetch_id']
    assert row['status']==('unknown'if isinstance(error,asyncio.CancelledError)else'error')
    assert row['error_kind']==type(error).__name__ and row['record_count']==0
    assert 'http_request_sent' not in row and 'http_status' not in row and 'private token' not in str(row)


def test_completed_sources_and_related_audits_survive_later_failure(events):
    related={'source':'esg_occupational_safety','provider':'related','status':'partial','record_count':1,'cache_hit':True}
    first=Provider('annual_workforce',audit={'source':'annual_workforce','provider':'annual','status':'success','record_count':1,'related_entries':[related]})
    last=Provider('macro_indicators',status='error',value={})
    with pytest.raises(RuntimeError):
        asyncio.run(app({p.source:p for p in(first,last)}).fetch_radar_async(FetchRequest.from_ticker('1623.TW'),(first.source,last.source)))
    assert [row['source']for row in events]==['esg_occupational_safety','annual_workforce','macro_indicators']
    assert [p.calls for p in(first,last)]==[1,1] and events[0]==related


def test_existing_cache_provenance_not_rebound_on_later_exception(events):
    historical={'source':'taiwan_open_data','provider':'cache','status':'success','record_count':3,'cache_hit':True,'fetch_id':'old','operation_id':'old-op','fetched_at_epoch':1234}
    first=Provider('taiwan_open_data',audit=historical);last=Provider('macro_indicators',error=OSError('network'))
    with pytest.raises(OSError):
        asyncio.run(app({p.source:p for p in(first,last)}).fetch_radar_async(FetchRequest.from_ticker('1623.TW'),(first.source,last.source)))
    assert events[0]==historical and historical['fetch_id']=='old'
    assert len(events)==2 and events[1]['operation_id']==last.context['operation_id']


def test_missing_provider_preserves_prior_observation_without_fabricated_attempt(events):
    first=Provider('taiwan_open_data')
    with pytest.raises(RuntimeError,match='雷達缺少資料來源'):
        asyncio.run(app({first.source:first}).fetch_radar_async(FetchRequest.from_ticker('1623.TW'),(first.source,'macro_indicators')))
    assert len(events)==1 and events[0]['source']==first.source


def test_market_extraction_failure_preserves_snapshot_and_failed_field_audit(events):
    p=Provider('market_data',value={'stock':object(),'is_valid':False})
    with pytest.raises(RuntimeError,match='雷達市場資料暫時不可用'):
        asyncio.run(app({p.source:p}).fetch_radar_async(FetchRequest.from_ticker('1623.TW'),(p.source,)))
    assert len(events)==2 and events[0]['provider']==p.name
    assert events[1]['provider']=='yfinance radar' and events[1]['status']=='error'


@pytest.mark.parametrize('enabled',[True,False])
def test_research_option_and_successful_path_persist_at_most_once(events,enabled):
    p=Provider('taiwan_open_data')
    result=asyncio.run(app({p.source:p}).fetch_radar_async(FetchRequest.from_ticker('1623.TW',record_provider_sla=enabled),(p.source,)))
    assert len(events)==int(enabled) and p.calls==1
    assert result.data[p.source]==p.value


def test_store_failure_never_replaces_original_provider_error(monkeypatch):
    def unavailable(rows):raise RuntimeError('SLA storage unavailable')
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',unavailable)
    p=Provider('taiwan_open_data',error=TimeoutError('original'))
    with pytest.raises(TimeoutError)as caught:
        asyncio.run(app({p.source:p}).fetch_radar_async(FetchRequest.from_ticker('1623.TW'),(p.source,)))
    assert caught.value is p.error and p.calls==1


def test_actual_isolated_sql_projection_keeps_failed_denominator():
    from provider_acquisition import get_provider_acquisition_summary
    p=Provider('taiwan_open_data',status='error',value={})
    with pytest.raises(RuntimeError):
        asyncio.run(app({p.source:p}).fetch_radar_async(FetchRequest.from_ticker('1623.TW'),(p.source,)))
    group=next(r for r in get_provider_acquisition_summary('last_1h')['sources']if r['source']==p.source)
    assert group['failed_count']>=1 and group['fetch_attempts']>=1


@pytest.mark.parametrize('capture',[True,False])
def test_invalid_provider_result_keeps_old_error_behavior_and_operation(capture):
    from data_fetch.provider_execution import fetch_correlated_provider
    seen=[];observations=[]
    class Malformed:
        source='taiwan_open_data';name='Malformed provider'
        async def fetch_async(self,request,context):
            seen.append(current_correlation());return None
    with pytest.raises(AttributeError):
        asyncio.run(fetch_correlated_provider(Malformed(),FetchRequest.from_ticker('1623.TW'),{},capture_errors=capture,error_audit_sink=observations.append))
    assert len(observations)==1 and observations[0]['operation_id']==seen[0]['operation_id']
    assert observations[0]['status']=='error' and 'http_request_sent'not in observations[0]


def test_passive_error_sink_failure_keeps_original_exception():
    from data_fetch.provider_execution import fetch_correlated_provider
    error=OSError('original provider error')
    p=Provider('taiwan_open_data',error=error)
    def broken(row):raise RuntimeError('observer failed')
    with pytest.raises(OSError)as caught:
        asyncio.run(fetch_correlated_provider(p,FetchRequest.from_ticker('1623.TW'),{},error_audit_sink=broken))
    assert caught.value is error and p.calls==1
