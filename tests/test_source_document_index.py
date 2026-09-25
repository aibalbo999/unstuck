import hashlib
import sqlite3

import pytest

import source_document_index as index


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'operational.sqlite3'
    monkeypatch.setattr(index, '_database_path', lambda: path)
    return path


def document(**overrides):
    return dict(ticker='2330.TW', document_id='a', title='董事會決議',
                url='https://openapi.twse.com.tw/v1/opendata/t187ap04_L',
                published_at='2026-01-02T10:00:00+08:00', source='TWSE',
                source_type='official_disclosure', document_kind='announcement',
                text='董事會通過資本支出。', summary='董事會通過資本支出。',
                retrieved_at_epoch=1767400000, coverage_status='text_available', **overrides)


def changed(**overrides):
    value = document()
    value.update(overrides)
    return value


def test_read_does_not_create_database(db):
    assert index.search_source_documents('2330.TW') == []
    assert not db.exists()


def test_dedup_distinct_events_and_search_chinese(db):
    values = [document(), changed(document_id='b', title='董事異動', text='董事辭任', summary='董事辭任'),
              changed(ticker='2330.TWO', document_id='c')]
    index.upsert_source_documents(values)
    index.upsert_source_documents(values, observed_at_epoch=1767500000)
    results = index.search_source_documents('2330.TW', text='資本支出')
    assert len(results) == 1
    assert results[0]['retrieved_at_epoch'] == 1767400000
    assert results[0]['content_sha256'] == hashlib.sha256('董事會通過資本支出。'.encode()).hexdigest()
    assert len(index.search_source_documents('2330.TW')) == 2
    with sqlite3.connect(db) as conn:
        assert conn.execute('select count(*) from source_documents').fetchone()[0] == 3


def test_revisions_preserved_but_search_only_latest_and_cached_old_cannot_win(db):
    index.upsert_source_documents([document()])
    revised = changed(text='董事會修正資本支出', summary='董事會修正資本支出', retrieved_at_epoch=1767500000)
    index.upsert_source_documents([revised])
    index.upsert_source_documents([document()], observed_at_epoch=1767600000)
    assert index.search_source_documents('2330.TW')[0]['text'] == revised['text']
    assert index.search_source_documents('2330.TW', text='通過') == []
    with sqlite3.connect(db) as conn:
        assert conn.execute('select count(*) from source_documents').fetchone()[0] == 2


def test_date_filters_unknown_future_and_source_kind(db):
    index.upsert_source_documents([document(), changed(document_id='unknown', published_at=None),
        changed(document_id='ir', source_type='company_ir', document_kind='presentation'),
        changed(document_id='future', published_at='2999-01-01')])
    assert len(index.search_source_documents('2330.TW')) == 3
    results = index.search_source_documents('2330.TW', kinds=('official_disclosure',),
                                            since='2026-01-02', until='2026-01-02')
    assert [x['document_id'] for x in results] == ['a']


def test_invalid_documents_rejected_and_invalid_queries_fail_closed(db):
    result = index.upsert_source_documents([changed(ticker='2330'), changed(url='file:///etc/passwd'),
        changed(published_at='not-a-date'), changed(url='http://127.0.0.1/a'),
        changed(source_type='news'), changed(retrieved_at_epoch=float('nan'))])
    assert result['rejected'] == 6
    assert index.search_source_documents('2330.TW') == []
    for kwargs in ({'since': 'bad'}, {'limit': 101}, {'kinds': ('news',)}, {'since': '2026-02-01', 'until': '2026-01-01'}):
        with pytest.raises(ValueError):
            index.search_source_documents('2330.TW', **kwargs)
    with pytest.raises(ValueError):
        index.search_source_documents("2330.TW' OR 1=1 --")


def test_truncation_is_explicit_and_unrelated_operational_data_preserved(db):
    with sqlite3.connect(db) as conn:
        conn.execute('create table existing_job (id text)')
        conn.execute("insert into existing_job values ('job-1')")
    index.upsert_source_documents([changed(text='長' * 100000)])
    doc = index.search_source_documents('2330.TW')[0]
    assert doc['content_truncated'] is True
    assert len(doc['text']) <= 60000
    with sqlite3.connect(db) as conn:
        assert conn.execute('select id from existing_job').fetchone() == ('job-1',)
