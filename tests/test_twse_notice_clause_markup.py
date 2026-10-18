"""Saved complete official notices: decorative clause text is usable; HTML is not."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import base64,json
import pytest

NOW=datetime(2026,10,10,5,10,tzinfo=ZoneInfo('Asia/Taipei'))
MARKUP="<font color='#FF0000'>﹝第十一款﹞</font>"
FIXTURES=Path(__file__).parent/'fixtures/source_acquisition'

@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def original(ticker):
    return (FIXTURES/f'twse_{ticker}_trading_notices_markup_20261010.json').read_bytes()


def collect(ticker,raw):
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices
    return fetch_trading_notices(ticker+'.TW',now=NOW,get=lambda url:raw)


@pytest.mark.parametrize('ticker,expected_count',[('3653',3),('2059',2)])
def test_complete_saved_official_notices_keep_all_clause_words_without_font_markup(ticker,expected_count):
    from official_response_evidence import read_response
    from data_fetch.market_sources.twse_trading_notices import verified_notice_record
    raw=original(ticker);payload=json.loads(raw);rows,audit=collect(ticker,raw)
    assert audit['status']=='success'and len(rows)==expected_count
    assert read_response(audit['raw_response_receipt'])==raw
    for row,source in zip(rows,payload['data']):
        assert row['summary']==source[4].replace(MARKUP,'﹝第十一款﹞')
        assert '<font'not in row['text']and '﹝第十一款﹞'in rows[-1]['text']
        assert row['content_truncated']is False
        assert verified_notice_record(row,{'ticker':ticker+'.TW'})==ticker
        assert row['trading_notice_receipt']['original']['raw_response_sha256']==sha256(raw).hexdigest()


def test_transport_raw_cache_accepts_verified_clause_text_and_preserves_original_epoch(monkeypatch):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices
    raw=original('3653');calls=[]
    def complete(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1;diagnostic['http_request_sent']=True
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp,'_download',complete)
    first,audit=fetch_trading_notices('3653.TW',now=NOW)
    second,warm=fetch_trading_notices('3653.TW',now=NOW)
    assert len(first)==len(second)==3 and len(calls)==1
    assert audit['status']=='success'and warm['status']=='skipped_fresh_cache'
    assert audit['fetched_at_epoch']==warm['fetched_at_epoch']
    assert warm['http_request_sent']is False


@pytest.mark.parametrize('replacement',[
    "<font color='#FF0000' onclick='bad()'>﹝第十一款﹞</font>",
    "<font color='#000000'>﹝第十一款﹞</font>",
    "<font color='#FF0000'>other text</font>",
    "<font color='#FF0000'>﹝第十一款﹞",
    "<font color='#FF0000'><b>﹝第十一款﹞</b></font>",
    "<script>bad()</script>",
    "<a href='https://evil.test/'>﹝第十一款﹞</a>",
    "&lt;font color='#FF0000'&gt;﹝第十一款﹞&lt;/font&gt;",
    "https://evil.test/",
])
def test_unknown_or_active_or_encoded_markup_never_becomes_a_notice_record(replacement):
    p=json.loads(original('3653'));p['data'][-1][4]=p['data'][-1][4].replace(MARKUP,replacement)
    rows,audit=collect('3653',json.dumps(p,ensure_ascii=False).encode())
    assert rows==[]and audit['status']=='error'and audit['record_count']==0


@pytest.mark.parametrize('change',['stock','date','duplicate','title','fields','count'])
def test_known_decoration_cannot_excuse_other_envelope_or_row_conflicts(change):
    p=json.loads(original('3653'))
    if change=='stock':p['data'][-1][1]='2059'
    elif change=='date':p['data'][-1][5]='115.09.01'
    elif change=='duplicate':p['data'][-1][5]=p['data'][0][5]
    elif change=='title':p['title']='Security verification'
    elif change=='fields':p['fields'][-1]='OTHER'
    else:p['total']=True
    rows,audit=collect('3653',json.dumps(p,ensure_ascii=False).encode())
    assert rows==[]and audit['status']=='error'


def test_saved_normalized_notice_must_still_match_original_words_and_daily_scope():
    from source_content_selection import issuer_match
    rows,_=collect('3653',original('3653'));row=deepcopy(rows[-1])
    assert issuer_match(row,{'ticker':'3653.TW','company_name':'健策'})=='3653'
    row['summary']=row['summary'].replace('1170.00','1700.00')
    assert issuer_match(row,{'ticker':'3653.TW','company_name':'健策'})is None


@pytest.mark.parametrize('suffix',[
    '&amp;lt;script&amp;gt;bad()&amp;lt;/script&amp;gt;',
    'https&amp;#58;//evil.test/',
    'HTTPS://evil.test/',
])
def test_known_decoration_cannot_hide_encoded_or_uppercase_active_content(suffix):
    p=json.loads(original('3653'));p['data'][-1][4]+=suffix
    rows,audit=collect('3653',json.dumps(p,ensure_ascii=False).encode())
    assert rows==[]and audit['status']=='error'


def test_removing_decoration_must_preserve_original_minimum_body_length():
    p=json.loads(original('3653'));p['data'][-1][4]=MARKUP
    rows,audit=collect('3653',json.dumps(p,ensure_ascii=False).encode())
    assert rows==[]and audit['status']=='error'
