"""An indexed original is replayable evidence, never another HTTP success."""
from copy import deepcopy
from datetime import timedelta
import json
import sqlite3
import pytest

import source_document_index as index
from test_ta_tung_mops_originals import replay, CONTEXT


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'documents.sqlite3'
    monkeypatch.setattr(index, '_database_path', lambda: path)
    return path


def documents(*, native=False):
    from mops_document_bridge import document_from_record
    rows, audit, calls, now = replay(native=native)
    return [document_from_record(row, CONTEXT) for row in rows], rows


def test_reserved_original_kind_cannot_silently_drop_unknown_proof(db):
    doc = {'ticker':'1623.TW','document_id':'forged','title':'未核對公告',
        'url':'https://mops.twse.com.tw/mops/#/web/t05st01','published_at':'2026-10-20T10:00:00+08:00',
        'source':'TWSE company announcement history','source_type':'official_disclosure',
        'document_kind':'mops_major_announcement','text':'Unverified original','summary':'Unverified original',
        'retrieved_at_epoch':1793000000,'original_evidence':{'schema':'unknown'}}
    assert index.upsert_source_documents([doc]) == {'accepted':0,'rejected':1}


@pytest.mark.parametrize('native', [False, True])
def test_two_originals_at_same_url_remain_distinct_and_proof_is_pathless(db, native):
    docs, rows = documents(native=native)
    assert len(docs) == 2 and len({d['url'] for d in docs}) == 1
    assert len({d['document_id'] for d in docs}) == 2
    assert all(d['retrieved_at_epoch'] == r['mops_json_receipt']['detail_receipt']['retrieved_at'] for d,r in zip(docs,rows))
    assert 'raw_response_path' not in json.dumps(docs)
    assert '/Volumes/' not in json.dumps(docs)
    assert index.upsert_source_documents(docs) == {'accepted':2,'rejected':0}
    found = index.search_source_documents('1623.TW')
    assert len(found) == 2
    assert {d['text'] for d in found} == {r['text'] for r in rows}
    assert all(d['content_truncated'] is False and d['original_evidence'] for d in found)


@pytest.mark.parametrize('change', ['text','publication','ticker','action','body_hash','missing_proof','unknown_proof','path','downgrade_kind'])
def test_unverified_or_forged_original_document_cannot_enter_index(db, change):
    docs, _ = documents(); doc = docs[0]
    if change == 'text': doc['text'] += 'Unverified inference'
    elif change == 'publication': doc['published_at'] = '2026-10-20T12:00:00+08:00'
    elif change == 'ticker': doc['ticker'] = '1216.TW'
    elif change == 'action': doc['original_evidence']['packet']['index_row'][5]['parameters']['serialNumber'] = '999'
    elif change == 'body_hash': doc['original_evidence']['packet']['detail_receipt']['raw_response_sha256'] = '0' * 64
    elif change == 'missing_proof': doc.pop('original_evidence')
    elif change == 'unknown_proof': doc['original_evidence']['schema'] = 'unknown'
    elif change == 'path': doc['original_evidence']['packet']['detail_receipt']['raw_response_path'] = '/tmp/forged'
    else:
        doc['document_kind'] = 'announcement'
        doc.pop('original_evidence')
    assert index.upsert_source_documents([doc]) == {'accepted':0,'rejected':1}
    assert index.search_source_documents('1623.TW') == []


def test_cache_replay_never_renews_acquisition_or_creates_content_revision(db):
    docs, _ = documents(); first = docs[0]
    index.upsert_source_documents([first])
    index.upsert_source_documents([first], observed_at_epoch=first['retrieved_at_epoch']+1000)
    found = index.search_source_documents('1623.TW')[0]
    assert found['retrieved_at_epoch'] == found['last_observed_at_epoch'] == first['retrieved_at_epoch']
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM source_documents').fetchone()[0] == 1


def test_typed_document_is_revalidated_on_read_and_not_replaced_with_older_revision(db):
    docs, _ = documents(); index.upsert_source_documents(docs)
    with sqlite3.connect(db) as c:
        raw = c.execute('SELECT rowid,document_json FROM source_documents ORDER BY rowid LIMIT 1').fetchone()
        changed = json.loads(raw[1]); changed['text'] += 'Forged stored content'
        c.execute('UPDATE source_documents SET document_json=? WHERE rowid=?',(json.dumps(changed,ensure_ascii=False),raw[0]))
    found = index.search_source_documents('1623.TW')
    assert len(found) == 1
    assert 'Forged' not in json.dumps(found)


def test_changed_discovery_only_does_not_renew_body_time_or_content_revision(db):
    from mops_document_bridge import validate_document
    docs, _ = documents(); doc = docs[0]
    index.upsert_source_documents([doc])
    changed = deepcopy(doc)
    old_body_time = doc['retrieved_at_epoch']
    changed['original_evidence']['packet']['index_receipt']['retrieved_at'] = old_body_time + 1
    validate_document(changed)
    index.upsert_source_documents([changed], observed_at_epoch=old_body_time+100)
    result = index.search_source_documents('1623.TW')[0]
    assert result['retrieved_at_epoch'] == result['last_observed_at_epoch'] == old_body_time
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM source_documents').fetchone()[0] == 1


def test_source_correction_is_revision_and_old_cache_cannot_overwrite_it(db):
    from mops_document_bridge import document_from_record
    docs, _ = documents(); index.upsert_source_documents(docs)
    def correct(originals):
        raw = next(x for x in originals if x['url'].endswith('_detail'))
        body = json.loads(raw['raw_body_utf8']); body['result']['data'][0][9] += '\n修正內容保留完整原文。'
        raw['raw_body_utf8'] = json.dumps(body,ensure_ascii=False)
    rows, _, _, _ = replay(correct)
    revised = [document_from_record(row,CONTEXT) for row in rows]
    index.upsert_source_documents(revised)
    index.upsert_source_documents(docs)
    result = index.search_source_documents('1623.TW')
    assert any('修正內容保留完整原文' in d['text'] for d in result)
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM source_documents').fetchone()[0] == 3


def test_research_prepares_documents_without_operational_writes(db):
    from mops_document_bridge import index_records
    _, rows = documents()
    docs, audit = index_records(rows,CONTEXT,persist=False)
    assert len(docs) == 2 and audit['prepared'] == 2
    assert audit['http_request_count'] == audit['new_source_successes'] == 0
    assert not audit['persisted'] and not db.exists()


def test_post_acquisition_join_exposes_body_even_when_daily_snapshot_finished_first(db, monkeypatch):
    import asyncio
    import time
    from datetime import datetime
    import mops_document_bridge as bridge
    import data_fetch.workflow as workflow
    from data_fetch.provider_base import DataProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest, ProviderResult
    rows, _, _, cutoff = replay()
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return cutoff.astimezone(tz) if tz else cutoff.replace(tzinfo=None)
    monkeypatch.setattr(bridge,'datetime',Clock)
    calls = []
    class Daily(DataProvider):
        source, name = 'official_disclosures', 'TWSE/TPEx official disclosures'
        def fetch(self, request, context=None):
            calls.append('daily')
            return ProviderResult(self.source,self.name,'degraded_enrichment',value={'status':'partial','documents':[],
                'retrieval_status':'valid_empty','fetched_at_epoch':time.time(),'cache_hit':True},
                audit={'source':self.source,'provider':self.name,'status':'degraded_enrichment','record_count':0,
                    'event_kind':'aggregate','http_request_sent':False,'cache_hit':True,'fetched_at_epoch':time.time()})
    class History(DataProvider):
        source, name = 'recent_catalysts', 'TWSE company announcement history'
        async def fetch_async(self, request, context=None):
            await asyncio.sleep(.01)
            calls.append('history')
            assert 'daily' in calls
            return ProviderResult(self.source,self.name,'skipped_fresh_cache',value=rows,
                audit={'source':self.source,'provider':self.name,'status':'skipped_fresh_cache','record_count':2,
                    'event_kind':'cache_hit','cache_hit':True,'http_request_sent':False,'http_request_count':0,
                    'fetched_at_epoch':rows[0]['mops_json_receipt']['detail_receipt']['retrieved_at']})
    cached = {**CONTEXT,'_cache_hit':True,'current_price':43,'recent_catalysts':[],'source_audit':[]}
    monkeypatch.setattr(workflow,'schema_compatible_cached_payload',lambda *_:deepcopy(cached))
    monkeypatch.setattr(workflow,'fresh_cached_payload',lambda *a:deepcopy(cached))
    monkeypatch.setattr(workflow,'cache_financial_payload',lambda *a:None)
    out = asyncio.run(workflow.fetch_payload_async(FetchRequest.from_ticker('1623.TW'),ProviderRegistry([Daily(),History()])))
    assert calls == ['daily','history']
    assert len(out['official_disclosures']['documents']) == 2
    assert out['official_disclosures']['coverage_status'] == 'partial'
    assert out['current_price'] == 43
    assert len(index.search_source_documents('1623.TW')) == 2
    from provider_acquisition import observation_kind
    for entry in out['source_audit']:
        if entry.get('source') == 'official_disclosures':
            assert observation_kind({'message':'',**entry,'details':entry}) in {'aggregate_count','fresh_cache_count'}
            assert entry.get('http_request_sent') is not True


@pytest.mark.parametrize('persist', [False,True])
def test_normal_source_only_handoff_indexes_after_original_guard_without_another_http(db, persist):
    import asyncio
    import time
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest, ProviderResult
    rows, _, _, _ = replay()
    calls = []
    class RetainedHistory(TwseCompanyHistoryProvider):
        def fetch(self, request, context=None):
            calls.append(request)
            return ProviderResult(self.source,self.name,'skipped_fresh_cache',value=rows,
                audit={'source':self.source,'provider':self.name,'status':'skipped_fresh_cache','record_count':2,
                    'fetched_at_epoch':time.time(),'cache_hit':True,'stale':False,'http_request_count':0,'http_request_sent':False})
    result = asyncio.run(StockDataService(ProviderRegistry([RetainedHistory()])).fetch_source_async(
        FetchRequest.from_ticker('1623.TW',force_refresh=False,record_provider_sla=persist),
        'official_announcements',context={'data':CONTEXT}))
    assert len(calls) == 1 and result.source_audit[0]['http_request_count'] == 0
    assert result.source_audit[0]['local_original_documents']['new_source_successes'] == 0
    assert len(index.search_source_documents('1623.TW')) == (2 if persist else 0)
    assert db.exists() is persist


def test_search_api_returns_verified_originals_without_private_paths_or_acquisition(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.observability import ObservabilityRouteDeps, create_observability_router
    docs, _ = documents(); index.upsert_source_documents(docs)
    app = FastAPI(); app.include_router(create_observability_router(ObservabilityRouteDeps(lambda *_:[],lambda *_:[],lambda:None)))
    with TestClient(app) as client:
        response = client.get('/api/observability/source-documents',params={'ticker':'1623.TW'})
    assert response.status_code == 200
    value = response.json()
    assert value['acquisition_triggered'] is False and value['status'] == 'partial'
    assert len(value['documents']) == 2
    assert 'raw_response_path' not in json.dumps(value) and '/Volumes/' not in json.dumps(value)


@pytest.mark.parametrize('prior_kind', ['valid', 'invalid_container'])
def test_local_join_without_daily_provider_preserves_prior_issuer_documents(db, prior_kind):
    from mops_document_bridge import hydrate_provider_documents
    docs, rows = documents()
    prior = {'ticker':'1623.TW','document_id':'daily-original','source_type':'official_disclosure',
        'published_at':docs[0]['published_at'],'title':'原有官方公告','text':'保留已取得公告'}
    data = {**CONTEXT,'recent_catalysts':rows,
        'official_disclosures':{'documents':[prior]} if prior_kind == 'valid' else ['malformed']}
    output = hydrate_provider_documents([],data,persist=False)
    result = output[0]
    ids = {d['document_id'] for d in result.value['documents']}
    assert len(ids) == (3 if prior_kind == 'valid' else 2)
    assert ('daily-original' in ids) is (prior_kind == 'valid')
    assert result.value['coverage_status'] == 'partial'
    assert result.audit['http_request_count'] == 0
    assert result.audit['local_original_documents']['new_source_successes'] == 0
    assert not db.exists()


def test_corrupt_latest_revision_does_not_fall_back_to_superseded_claim(db):
    from mops_document_bridge import document_from_record
    docs, _ = documents()
    def correct(originals):
        raw = next(x for x in originals if x['url'].endswith('_detail'))
        body = json.loads(raw['raw_body_utf8'])
        body['result']['data'][0][9] += '\n已發布的更新版本。'
        raw['raw_body_utf8'] = json.dumps(body,ensure_ascii=False)
    rows, _, _, _ = replay(correct)
    revised = document_from_record(next(row for row in rows if '已發布的更新版本' in row['text']),CONTEXT)
    original = next(doc for doc in docs if doc['document_id'] == revised['document_id'])
    index.upsert_source_documents([original])
    index.upsert_source_documents([revised])
    with sqlite3.connect(db) as c:
        raw = c.execute('SELECT rowid,document_json FROM source_documents ORDER BY rowid DESC LIMIT 1').fetchone()
        bad = json.loads(raw[1]); bad['original_evidence']['packet']['detail_receipt']['raw_response_sha256'] = '0'*64
        c.execute('UPDATE source_documents SET document_json=? WHERE rowid=?',(json.dumps(bad),raw[0]))
    assert index.search_source_documents('1623.TW') == []
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM source_documents').fetchone()[0] == 2


def test_merge_rejects_foreign_out_of_window_or_forged_saved_originals(db):
    from mops_document_bridge import hydrate_provider_documents
    docs, rows = documents()
    foreign = {**docs[0],'ticker':'2330.TW','document_id':'foreign'}
    expired = {**docs[0],'document_id':'expired','published_at':'2020-01-01T00:00:00+08:00'}
    forged = {**docs[0],'document_id':'mops-json:forged','text':'未經核實'}
    data = {**CONTEXT,'recent_catalysts':rows,'official_disclosures':{'documents':[foreign,expired,forged,{'document_id':[]}]}}
    result = hydrate_provider_documents([],data,persist=False)[0]
    assert {d['document_id'] for d in result.value['documents']} == {d['document_id'] for d in docs}
    assert not db.exists()


def changed_envelope_documents(*, change_result=False):
    from mops_document_bridge import document_from_record
    def change(originals):
        for item in originals:
            if not item['url'].endswith('_detail'):continue
            value=json.loads(item['raw_body_utf8'])
            value['datetime']='115/11/04 19:00:00'  # Offline response-clock variation only.
            if change_result:value['result']['data'][0][3]+='更新發言人'
            item['raw_body_utf8']=json.dumps(value,ensure_ascii=False)
    rows,_,_,_=replay(change)
    return [document_from_record(row,CONTEXT)for row in rows]


def test_response_clock_keeps_content_revision_and_retains_both_originals(db):
    docs,_=documents();index.upsert_source_documents(docs)
    with sqlite3.connect(db)as c:
        original=c.execute('SELECT document_json FROM source_documents ORDER BY document_id').fetchall()
    newer=changed_envelope_documents()
    assert docs[0]['original_body_sha256']!=newer[0]['original_body_sha256']
    index.upsert_source_documents(newer)
    index.upsert_source_documents(docs,observed_at_epoch=docs[0]['retrieved_at_epoch']+200)
    with sqlite3.connect(db)as c:
        assert c.execute('SELECT document_json FROM source_documents ORDER BY document_id').fetchall()==original
        assert c.execute('SELECT count(*) FROM source_documents').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM source_document_observations').fetchone()[0]==4
    found=index.search_source_documents('1623.TW')
    assert len(found)==2
    for doc in found:
        new=next(d for d in newer if d['document_id']==doc['document_id'])
        assert doc['last_observed_at_epoch']==new['retrieved_at_epoch']
        assert doc['last_observation']['original_body_sha256']==new['original_body_sha256']
    assert 'raw_response_path'not in json.dumps(found)


def test_unrendered_publisher_result_change_is_a_real_revision(db):
    docs,_=documents();index.upsert_source_documents(docs)
    newer=changed_envelope_documents(change_result=True)
    assert [d['text']for d in docs]==[d['text']for d in newer]
    index.upsert_source_documents(newer)
    with sqlite3.connect(db)as c:
        assert c.execute('SELECT count(*) FROM source_documents').fetchone()[0]==4


def test_corrupt_latest_observation_cannot_fall_back_to_previous_original(db):
    docs,_=documents();index.upsert_source_documents(docs)
    newer=changed_envelope_documents();index.upsert_source_documents(newer)
    with sqlite3.connect(db)as c:
        c.execute("UPDATE source_document_observations SET document_json='{}' WHERE original_body_sha256 IN (?,?)",
            tuple(d['original_body_sha256']for d in newer))
    assert index.search_source_documents('1623.TW')==[]


def test_existing_version_without_observation_table_is_not_rewritten(db):
    docs,_=documents();index.upsert_source_documents(docs)
    with sqlite3.connect(db)as c:
        c.execute('DROP TABLE source_document_observations')  # Isolated old-schema fixture.
        originals=c.execute('SELECT revision_sha256,document_json FROM source_documents ORDER BY document_id').fetchall()
    assert len(index.search_source_documents('1623.TW'))==2
    index.upsert_source_documents(changed_envelope_documents())
    with sqlite3.connect(db)as c:
        assert c.execute('SELECT revision_sha256,document_json FROM source_documents ORDER BY document_id').fetchall()==originals
        assert c.execute('SELECT count(*) FROM source_document_observations').fetchone()[0]==2
