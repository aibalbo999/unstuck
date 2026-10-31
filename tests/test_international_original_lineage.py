import json
import pytest
from official_response_evidence import read_response
from test_international_news_transport import owner,response,Client,call
import provider_sla
from external_data_gdelt import GDELT_TOPIC_QUERIES
from urllib.parse import urlencode
PUBLIC_URL="https://news.google.com/rss/search?"+urlencode({"q":GDELT_TOPIC_QUERIES["macro"],"hl":"en-US","gl":"US","ceid":"US:en"})

def test_public_rss_body_replays_without_query_or_acquisition_credit(monkeypatch):
    rows=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    r=response('rss',url=PUBLIC_URL)
    with owner():result=call(Client(r),'rss',monkeypatch)
    assert result==[{'headline':'unchanged result','topic':'macro'}]
    assert len(rows)==1
    row=rows[0];receipt=row['raw_http_receipt']
    assert receipt['status']=='archived'and read_response(receipt)==r.content
    assert receipt['raw_response_sha256']==row['response_sha256']
    assert receipt['http_status_observed']is True and receipt['response_complete']is True
    assert row['record_count']==0
    assert 'PRIVATE_QUERY'not in json.dumps(rows)
    assert '?'not in receipt['source_url']


@pytest.mark.parametrize('mode',['auth','cookie','bad_query','private_query','html','error'])
def test_unqualified_body_never_archived(monkeypatch,mode):
    import httpx
    import official_response_evidence as archive
    rows=[];calls=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    monkeypatch.setattr(archive,'archive_response',lambda *a,**k:calls.append(1))
    headers={'authorization':'PRIVATE'}if mode=='auth'else {'cookie':'PRIVATE'}if mode=='cookie'else {}
    url=PUBLIC_URL+('&api_key=PRIVATE'if mode=='bad_query'else '')
    if mode=='private_query':url='https://news.google.com/rss/search?q=PRIVATE'
    r=httpx.Response(403 if mode=='error'else 200,content=b'<html/>'if mode=='html'else b'<rss><channel/></rss>',request=httpx.Request('GET',url,headers=headers))
    from international_news_transport import begin,record
    with owner():record(begin(url),r)
    assert len(rows)==1 and not calls
    assert rows[0].get('raw_http_receipt')is None
    assert 'PRIVATE'not in json.dumps(rows)

def test_archive_exception_preserves_transport_receipt(monkeypatch):
    import official_response_evidence as archive
    rows=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    def fail(*a,**k):raise OSError('disk error')
    monkeypatch.setattr(archive,'archive_response',fail)
    with owner():result=call(Client(response(url=PUBLIC_URL)),'rss',monkeypatch)
    assert len(rows)==1 and rows[0]['record_count']==0
    assert result==[{'headline':'unchanged result','topic':'macro'}]


def test_persisted_original_link_is_not_an_acquisition(monkeypatch,tmp_path):
    import sqlite3
    from provider_acquisition import observation_kind
    monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'events.sqlite3'))
    with owner():call(Client(response(url=PUBLIC_URL)),'rss',monkeypatch)
    with sqlite3.connect(tmp_path/'events.sqlite3')as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r)for r in db.execute('select * from provider_sla_events')]
    assert len(rows)==1
    row=rows[0];d=json.loads(row['details_json']);receipt=d['original_http_receipts'][0]
    assert receipt['response_sha256']==d['response_sha256']
    assert receipt['response_complete']is True and receipt['http_status_observed']is True
    assert receipt['original_cache_hit']is False
    assert observation_kind({**row,'details':d})=='aggregate_count'
    assert 'q='not in row['details_json'] and '<rss'not in row['details_json']

@pytest.mark.parametrize('body',[b'<!DOCTYPE rss [<!ENTITY x "secret">]><rss/>',b'<!ENTITY x "secret"><rss/>',b'<rss/>\x00',b'<html/>',b'<rss>'+b'x'*2_000_000+b'</rss>'])
def test_unsupported_xml_is_not_archived(monkeypatch,body):
    import httpx
    import official_response_evidence as archive
    from international_news_transport import begin,record
    rows=[];calls=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    monkeypatch.setattr(archive,'archive_response',lambda *a,**k:calls.append(1))
    r=httpx.Response(200,content=body,request=httpx.Request('GET',PUBLIC_URL))
    with owner():record(begin(PUBLIC_URL),r)
    assert len(rows)==1 and not calls and rows[0].get('raw_http_receipt')is None


@pytest.mark.parametrize('suffix',['&api_key=','&hl=PRIVATE'])
def test_blank_extra_or_duplicate_locale_query_cannot_enter_archive(monkeypatch,suffix):
    import official_response_evidence as archive
    from international_news_transport import begin,record
    rows=[];calls=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    monkeypatch.setattr(archive,'archive_response',lambda *a,**k:calls.append(1))
    r=response(url=PUBLIC_URL+suffix)
    with owner():record(begin(PUBLIC_URL+suffix),r)
    assert len(rows)==1 and not calls
