"""A single missing optional source must not reacquire or freshen core data."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import time
import pytest
from fastapi import HTTPException

from data_fetch.provider_base import CallableProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import ProviderResult
from report_analysis_evidence import capture_analysis_evidence
from report_persistence import report_bundle_keys_for_filename
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_refresh_acquisition_audit import events, init_db


def saved_report(storage):
    filename = '6214_TW_v4_report_20261010_100000.html'
    keys = report_bundle_keys_for_filename(filename)
    old_epoch = time.time() - 3 * 86400
    old_audits = [
        {'source': 'market_data', 'provider': 'original market', 'status': 'success',
         'record_count': 1, 'fetched_at_epoch': old_epoch,
         'fetched_at': datetime.fromtimestamp(old_epoch, timezone.utc).isoformat(),
         'fetch_id': 'original-fetch', 'cache_hit': False, 'stale': True},
        {'source': 'earnings_call', 'provider': 'WebPro metadata',
         'status': 'degraded_enrichment', 'record_count': 1,
         'fetched_at_epoch': old_epoch, 'fetch_id': 'original-fetch'},
    ]
    data = {'ticker': '6214.TW', 'company_name': '精誠', 'current_price': 100,
            'revenue_history': [1, 2, 3, 4, 5], 'years': ['2021', '2022', '2023', '2024', '2025'],
            'peer_discovery_results': [{'counterparty': {'ticker': '2468.TW'}}],
            'earnings_call': {'ticker': '6214.TW', 'date': '2026-09-17',
                              'source': 'WebPro metadata', 'summary': ''},
            'source_audit': deepcopy(old_audits)}
    snapshot = {'ticker': '6214.TW', 'company_name': '精誠', 'pipeline': 'v4',
                'generated_at': datetime.fromtimestamp(old_epoch, timezone.utc).isoformat(),
                'source_audit': old_audits, 'data': data}
    for gate in ['report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        snapshot[gate] = {'original': gate}
    snapshot['analysis_evidence'] = capture_analysis_evidence({'data': data}, generated_at=snapshot['generated_at'])
    storage.save_report(keys.html_key, b'<html>original conclusions</html>', content_type='text/html')
    storage.save_report(keys.md_key, b'original conclusions', content_type='text/markdown')
    storage.save_report(keys.data_key, json.dumps(snapshot).encode(), content_type='application/json')
    return filename, keys, snapshot


def test_single_source_refresh_retains_core_age_analysis_and_other_sources(tmp_path):
    init_db()
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    calls = []

    def acquire(request, context):
        calls.append(request.ticker)
        value = {'ticker': '6214', 'date': '2026-09-17', 'source': 'MOPS investor conference',
                 'summary': 'issuer published meeting description', 'transcript_available': False}
        audit = {'source': 'earnings_call', 'provider': 'MOPS investor conference',
                 'status': 'success', 'record_count': 1, 'event_kind': 'http_request',
                 'http_request_sent': True, 'fetched_at_epoch': time.time()}
        return ProviderResult('earnings_call', audit['provider'], 'success', value=value, audit=audit)

    def forbidden(*args):
        raise AssertionError('single-source recovery must not reacquire market or financial data')

    service = StockDataService(registry=ProviderRegistry([
        CallableProvider('earnings_call', 'MOPS investor conference', acquire),
        CallableProvider('market_data', 'forbidden core fetch', forbidden),
    ]))
    response = asyncio.run(refresh_report_data_snapshot(
        filename, output_dir=str(tmp_path), storage=storage, refresh_service=service,
        source='earnings_call', return_refreshed_data=True,
    ))
    snapshot = json.loads(storage.get_report(keys.data_key).content)
    assert calls == ['6214.TW']
    assert response['refresh_sources'] == ['earnings_call']
    assert snapshot['data']['earnings_call']['summary'] == 'issuer published meeting description'
    for field in ['ticker', 'current_price', 'revenue_history', 'years', 'peer_discovery_results']:
        assert snapshot['data'][field] == old['data'][field]
    retained = next(a for a in snapshot['source_audit'] if a['source'] == 'market_data')
    assert retained == old['source_audit'][0]
    assert snapshot['data_trust']['status'] != 'fresh'
    assert 'market_data' in snapshot['data_trust']['stale_sources']
    assert snapshot['analysis_evidence'] == old['analysis_evidence']
    for gate in ['report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert snapshot[gate] == old[gate]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert response['analysis_text_stale'] is True
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call'
    new_audit = next(a for a in snapshot['source_audit'] if a['source'] == 'earnings_call')
    assert json.loads(observed[0]['details_json'])['fetch_id'] == new_audit['fetch_id']


@pytest.mark.parametrize('source', ['full', 'recent_news', ''])
def test_unsupported_source_does_not_read_or_mutate_report(tmp_path, source):
    storage = InMemoryStorage()
    filename, keys, _ = saved_report(storage)
    before = storage.get_report(keys.data_key).content
    service = StockDataService(fetcher=lambda *args: pytest.fail('unexpected full fetch'))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path),
                    storage=storage, refresh_service=service, source=source))
    assert raised.value.status_code == 400
    assert storage.get_report(keys.data_key).content == before


def test_full_fetch_override_is_rejected_before_provider_work(tmp_path):
    storage = InMemoryStorage()
    filename, keys, _ = saved_report(storage)
    before = storage.get_report(keys.data_key).content
    service = StockDataService(fetcher=lambda *args: pytest.fail('source path fell back to full fetch'))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path),
                    storage=storage, refresh_service=service, source='earnings_call'))
    assert raised.value.status_code == 503
    assert storage.get_report(keys.data_key).content == before


def test_missing_core_timestamp_rejects_source_refresh_before_fetch(tmp_path):
    storage = InMemoryStorage()
    filename, keys, original = saved_report(storage)
    original['source_audit'][0].pop('fetched_at_epoch')
    original['source_audit'][0].pop('fetched_at')
    storage.save_report(keys.data_key, json.dumps(original).encode(), content_type='application/json')
    before = storage.get_report(keys.data_key).content
    service = StockDataService(registry=ProviderRegistry([
        CallableProvider('earnings_call', 'forbidden', lambda *args: pytest.fail('undated core was freshened')),
    ]))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path),
                    storage=storage, refresh_service=service, source='earnings_call'))
    assert raised.value.status_code == 400
    assert storage.get_report(keys.data_key).content == before


def test_failed_source_keeps_original_partial_source_and_snapshot(tmp_path):
    storage = InMemoryStorage()
    filename, keys, _ = saved_report(storage)
    before = storage.get_report(keys.data_key).content
    def fail(request, context):
        return ProviderResult('earnings_call', 'MOPS investor conference', 'error', value={},
                              audit={'source': 'earnings_call', 'status': 'error', 'record_count': 0})
    service = StockDataService(registry=ProviderRegistry([
        CallableProvider('earnings_call', 'MOPS investor conference', fail),
    ]))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path),
                    storage=storage, refresh_service=service, source='earnings_call'))
    assert raised.value.status_code == 502
    assert storage.get_report(keys.data_key).content == before


def test_source_query_keeps_existing_mutation_authorization(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.reports import ReportRouteDeps, create_reports_router
    storage = InMemoryStorage()
    filename, keys, _ = saved_report(storage)
    before = storage.get_report(keys.data_key).content
    calls = []
    def authorize(request):
        if request.headers.get('X-Test-Mutation') != 'approved':
            raise HTTPException(status_code=403, detail='mutation authorization required')
    async def only_source(request, source):
        calls.append(source)
        value = {'ticker': '6214', 'date': '2026-09-17', 'source': 'MOPS investor conference'}
        audit = {'source': 'earnings_call', 'provider': 'MOPS investor conference',
                 'status': 'success', 'record_count': 1, 'fetch_id': 'test-authorized-source',
                 'fetched_at_epoch': time.time()}
        from types import SimpleNamespace
        return SimpleNamespace(data={'ticker': request.ticker, 'earnings_call': value}, source_audit=[audit])
    from types import SimpleNamespace
    service = SimpleNamespace(fetch_source_async=only_source)
    app = FastAPI()
    app.include_router(create_reports_router(ReportRouteDeps(
        get_output_dir=lambda: str(tmp_path), get_report_storage=lambda: storage,
        get_refresh_service=lambda: service, get_pipeline_runner=lambda: None,
        get_report_renderer=lambda: None, get_task_queue=lambda: None,
        run_report_rerun_job=lambda *_: '', create_job=lambda *_: 'job',
        get_job=lambda *_: {}, get_events_since=lambda *_: [],
        update_job=lambda *a, **k: None, append_event=lambda *a: None,
        request_job_cancel=lambda *_: False, print_streamed_event=lambda *_: None,
        require_mutation_authorized=authorize,
    )))
    client = TestClient(app)
    url = '/api/report/' + filename + '/refresh/data?source=earnings_call'
    assert client.post(url).status_code == 403
    assert calls == [] and storage.get_report(keys.data_key).content == before
    response = client.post(url, headers={'X-Test-Mutation': 'approved'})
    assert response.status_code == 200
    assert response.json()['refresh_sources'] == ['earnings_call']
    assert calls == ['earnings_call']


def observed_service(status='success'):
    def acquire(request, context):
        value = ({'ticker': '6214', 'source': 'MOPS investor conference',
                  'date': '2026-09-17', 'summary': 'verified issuer description'}
                 if status == 'success' else {})
        audit = {'source': 'earnings_call', 'provider': 'MOPS investor conference',
                 'status': status, 'record_count': int(bool(value)),
                 'http_request_sent': True, 'event_kind': 'http_request',
                 'fetched_at_epoch': time.time(),
                 **({'error_kind': 'server_error', 'http_status': 502} if status != 'success' else {})}
        return ProviderResult('earnings_call', audit['provider'], status, value=value, audit=audit)
    return StockDataService(registry=ProviderRegistry([
        CallableProvider('earnings_call', 'MOPS investor conference', acquire),
    ]))


def test_actual_failed_source_attempt_is_observed_once_with_snapshot_unchanged(tmp_path):
    init_db()
    storage = InMemoryStorage()
    filename, keys, _ = saved_report(storage)
    before = storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException) as caught:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                    refresh_service=observed_service('error'), source='earnings_call'))
    assert caught.value.status_code == 502 and storage.get_report(keys.data_key).content == before
    observed = events()
    assert len(observed) == 1
    assert observed[0]['source'] == 'earnings_call' and observed[0]['status'] == 'error'


@pytest.mark.parametrize(('safety_available', 'previous_safety'), [(True, False), (False, False), (False, True)])
def test_single_source_refresh_can_update_official_workforce_and_safety_bundle(tmp_path, monkeypatch, safety_available, previous_safety):
    from datetime import date
    import data_fetch.annual_workforce_provider as workforce
    import data_fetch.annual_occupational_safety as safety

    init_db()
    storage = InMemoryStorage()
    filename, keys, original = saved_report(storage)
    workforce_row = {
        '出表日期': '1151016', '報告年度': '114', '公司代號': '6214', '公司名稱': '精誠資訊',
        '員工薪資平均數(仟元/人)': '758',
        '非擔任主管之全時員工薪資中位數(仟元/人)': '712', '管理職女性主管佔比': '25.00%',
    }
    safety_row = {
        '出表日期': '1151016', '報告年度': '114', '公司代號': '6214' if safety_available else '9999', '公司名稱': '精誠資訊',
        '職業災害人數及比率-人數': '1', '職業災害人數及比率-比率': '0.10%',
        '火災件數(件)': '0', '火災死傷人數(人)': '0', '火災死傷人數占員工總人數比率': '0.00%',
    }
    from data_fetch.annual_occupational_safety import URLS as SAFETY_URLS
    previous_safety_epoch = time.time() - 365 * 86400
    if previous_safety:
        old_safety_row = {**safety_row, '出表日期': '1140301', '報告年度': '113', '公司代號': '6214'}
        old_safety = safety.parse_occupational_safety_dataset(
            json.dumps([old_safety_row]), '6214.TW', today=date(2026, 10, 17))
        old_safety['status'] = 'success'
        old_bundle = {
            'ticker': '6214.TW', 'report_year': 2024, 'published_on': '2025-03-01',
            'status': 'success', 'coverage_status': 'complete', 'observation_kind': 'annual_workforce_disclosure',
            'metrics': {'employee_average_salary_thousand_twd': 700},
            'esg_occupational_safety': old_safety,
        }
        previous_rows = [
            {'source': 'annual_workforce', 'provider': workforce.PROVIDER, 'status': 'success',
             'record_count': 1, 'fetch_id': 'old-workforce', 'fetched_at_epoch': previous_safety_epoch},
            {'source': 'esg_occupational_safety', 'provider': safety.PROVIDER, 'status': 'success',
             'record_count': 1, 'fetch_id': 'old-workforce', 'fetched_at_epoch': previous_safety_epoch},
        ]
        original['source_audit'].extend(previous_rows)
        original['data']['source_audit'].extend(deepcopy(previous_rows))
        original['data']['annual_workforce'] = old_bundle
        original['data']['source_freshness'] = {
            'annual_workforce': {'fetched_at_epoch': previous_safety_epoch},
            'esg_occupational_safety': {'fetched_at_epoch': previous_safety_epoch},
        }
        storage.save_report(keys.data_key, json.dumps(original).encode(), content_type='application/json')
    responses = {
        workforce.URLS['.TW']: json.dumps([workforce_row]),
        SAFETY_URLS['.TW']: json.dumps([safety_row]),
    }
    monkeypatch.setattr(workforce, '_today', lambda: date(2026, 10, 17))
    monkeypatch.setattr(safety, '_today', lambda: date(2026, 10, 17))
    monkeypatch.setattr(workforce, '_fetch_dataset', lambda url: responses[url])
    monkeypatch.setattr(workforce, 'shared_fetch', lambda key, callback, **kwargs: (
        callback(), {'cache_hit': False, 'stale': False, 'fetched_at_epoch': time.time(),
                     'http_request_sent': True, 'http_request_count': 1}))
    before_events = len(events())

    response = asyncio.run(refresh_report_data_snapshot(
        filename, output_dir=str(tmp_path), storage=storage, refresh_service=StockDataService(),
        source='annual_workforce',
    ))

    snapshot = json.loads(storage.get_report(keys.data_key).content)
    assert response['refresh_sources'] == ['annual_workforce']
    assert snapshot['data']['annual_workforce']['metrics']['employee_average_salary_thousand_twd'] == 758
    if safety_available:
        assert snapshot['data']['annual_workforce']['esg_occupational_safety']['metrics']['occupational_injury_count'] == 1
    elif previous_safety:
        retained = snapshot['data']['annual_workforce']['esg_occupational_safety']
        assert retained['metrics']['occupational_injury_count'] == 1
        assert retained['status'] == 'stale'
    else:
        assert snapshot['data']['annual_workforce']['esg_occupational_safety'] == {}
    assert snapshot['analysis_evidence'] == original['analysis_evidence']
    assert snapshot['report_lint'] == original['report_lint']
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    audits = [row for row in snapshot['source_audit']
              if row.get('source') in {'annual_workforce', 'esg_occupational_safety'}]
    assert {row['source'] for row in audits} == {'annual_workforce', 'esg_occupational_safety'}
    assert {row['source']: row['status'] for row in audits} == {
        'annual_workforce': 'success',
        'esg_occupational_safety': 'success' if safety_available else 'unavailable',
    }
    assert 'annual_workforce' in snapshot['data']['source_freshness']
    safety_freshness = snapshot['data']['source_freshness'].get('esg_occupational_safety', {})
    if safety_available:
        assert safety_freshness.get('fetched_at_epoch') is not None
    elif previous_safety:
        assert safety_freshness.get('fetched_at_epoch') == previous_safety_epoch
    else:
        assert safety_freshness.get('fetched_at_epoch') is None
    observed = events()[before_events:]
    assert {(row['source'], row['status'], row['record_count']) for row in observed} == {
        ('annual_workforce', 'success', 1),
        ('esg_occupational_safety', 'success', 1) if safety_available else ('esg_occupational_safety', 'unavailable', 0),
    }


def test_retained_core_ages_are_rechecked_and_old_trust_is_not_reused(tmp_path):
    init_db()
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    old['source_audit'][0]['stale'] = False
    old['data']['source_audit'] = deepcopy(old['source_audit'])
    old['data']['source_freshness'] = {'market_data': {
        'source': 'market_data', 'fetched_at_epoch': old['source_audit'][0]['fetched_at_epoch'],
        'fetched_at': old['source_audit'][0]['fetched_at'],
        'stale': False, 'is_fresh': True, 'age_seconds': 0}}
    old['data']['data_trust'] = {'status': 'fresh', 'stale_sources': [],
                              'last_market_data_at': old['source_audit'][0]['fetched_at'], 'score': 100}
    old['data_trust'] = deepcopy(old['data']['data_trust'])
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                refresh_service=observed_service(), source='earnings_call'))
    after = json.loads(storage.get_report(keys.data_key).content)
    assert after['data']['current_price'] == old['data']['current_price']
    assert after['data_trust']['status'] != 'fresh'
    market = after['data']['source_freshness']['market_data']
    assert market['stale'] is True
    assert market['fetched_at_epoch'] == old['source_audit'][0]['fetched_at_epoch']


@pytest.mark.parametrize('mode', ['audit_time_conflict', 'freshness_audit_conflict', 'market_audit_missing'])
def test_original_core_time_conflicts_cannot_freshen_old_quote(tmp_path, mode):
    init_db()
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    old['source_audit'][0]['stale'] = False
    original_epoch = old['source_audit'][0]['fetched_at_epoch']
    if mode == 'audit_time_conflict':
        old['source_audit'][0]['fetched_at_epoch'] = time.time() - 10
    elif mode == 'freshness_audit_conflict':
        old['data']['source_freshness'] = {'market_data': {
            'source': 'market_data', 'fetched_at_epoch': time.time() - 10, 'stale': False}}
    else:
        old['source_audit'] = old['source_audit'][1:]
    old['data']['source_audit'] = deepcopy(old['source_audit'])
    old['data']['data_trust'] = {'status': 'fresh', 'stale_sources': [], 'score': 100}
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    before = storage.get_report(keys.data_key).content
    try:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                    refresh_service=observed_service(), source='earnings_call'))
    except HTTPException:
        assert storage.get_report(keys.data_key).content == before
        return
    after = json.loads(storage.get_report(keys.data_key).content)
    market = after['data']['source_freshness']['market_data']
    assert market['stale'] is True
    assert market['fetched_at_epoch'] in (None, original_epoch)


@pytest.mark.parametrize('original_time', ['fresh_iso_audit', 'stale_derived', 'unknown'])
def test_optional_refresh_keeps_twse_original_freshness_without_package_retime(tmp_path,monkeypatch,original_time):
    import data_freshness
    now=1791955000.0
    monkeypatch.setattr(time,'time',lambda:now)
    init_db();storage=InMemoryStorage()
    filename,keys,old=saved_report(storage)
    ttl=data_freshness.source_max_age_seconds('twse_official','6214.TW')
    stamp=now-60 if original_time=='fresh_iso_audit'else now-ttl-10
    original_audit={'source':'twse_official','provider':'FinMind TWSE official','status':'success',
                    'record_count':1,'cache_hit':True,'stale':False,'fetch_id':'retained-original'}
    if original_time!='unknown':original_audit['fetched_at']=datetime.fromtimestamp(stamp,timezone.utc).isoformat()
    old['source_audit'].append(original_audit)
    old['data']['twse_official']={'revenue_ttm_raw':123456,'currency':'TWD','issuer':'6214'}
    old['data']['cache_generated_at_epoch']=now
    old['data']['source_freshness']={}
    if original_time=='stale_derived':
        old['data']['source_freshness']['twse_official']={'fetched_at_epoch':stamp,'cache_hit':True,'stale':False}
    # A later workflow stamp cannot replace the earlier original core ISO.
    core_stamp=now-3*86400
    old['data']['source_freshness']['market_data']={'fetched_at_epoch':now-5}
    financial={'source':'financial_statements','provider':'FinMind','status':'success','record_count':5,
               'fetched_at':datetime.fromtimestamp(core_stamp-5,timezone.utc).isoformat(),'cache_hit':False}
    old['source_audit'].append(financial)
    old['data']['source_freshness']['financial_statements']={'fetched_at_epoch':now-5}
    old['data']['source_audit']=deepcopy(old['source_audit'])
    old['analysis_evidence']=capture_analysis_evidence({'data':old['data']},generated_at=old['generated_at'])
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                refresh_service=observed_service(),source='earnings_call'))
    after=json.loads(storage.get_report(keys.data_key).content)
    entry=after['data']['source_freshness']['twse_official']
    assert entry['fetched_at_epoch']==(None if original_time=='unknown'else stamp)
    assert entry['is_fresh']is(original_time=='fresh_iso_audit')
    assert entry['stale']is(original_time!='fresh_iso_audit') and entry['cache_hit']is True
    assert entry['max_age_seconds']==ttl
    if original_time=='unknown':assert entry['fetched_at']is None and entry['age_seconds']is None
    assert after['data']['source_freshness']['market_data']['fetched_at_epoch']==core_stamp
    assert after['data']['source_freshness']['financial_statements']['fetched_at_epoch']==core_stamp-5
    assert after['source_freshness']==after['data']['source_freshness']
    assert after['data']['twse_official']==old['data']['twse_official']
    for container in (after,after['data']):
        assert [a for a in container['source_audit']if a['source']!='earnings_call']==[a for a in old['source_audit']if a['source']!='earnings_call']
    for key in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
        assert after[key]==old[key]
    for key in ('current_price','revenue_history','years','peer_discovery_results','cache_generated_at_epoch'):
        assert after['data'][key]==old['data'][key]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert len(events())==1 and events()[0]['source']=='earnings_call'
