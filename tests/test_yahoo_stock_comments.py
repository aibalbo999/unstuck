from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
from copy import deepcopy
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from data_fetch.market_sources import yahoo_stock_comments as source

NOW = datetime(2026, 10, 9, 3, 10, tzinfo=timezone.utc)
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/source_acquisition/yahoo_comments_3587_20261009.json').read_text())
DATA = {"ticker": "3587.TWO", "company_name": "閎康", "quote_type": "EQUITY", "exchange": "TWO"}


def quote(stores=None):
    payload = {"context": {"dispatcher": {"stores": stores or deepcopy(FIXTURE['quote_stores'])}}}
    return ('<div id="commentCanvass-finmb_39965474_lang_zh"></div><script>root.App.main = '
            + json.dumps(payload, ensure_ascii=False) + ';</script>').encode()


def comments(rows=None):
    value = deepcopy(FIXTURE['messages'])
    if rows is not None:
        value['canvassMessages'], value['messagesLength'] = rows, len(rows)
    return json.dumps(value, ensure_ascii=False).encode()


def selected(rows=None):
    return source.parse_comments(comments(rows), source.quote_board(quote(), '3587.TWO', DATA), now=NOW)


def test_public_capture_retains_original_dates_ids_and_no_sentiment_labels():
    rows, audit = selected()
    assert len(rows) == 4 and audit['raw_count'] == 10
    assert audit['rejected_reason_counts'] == {'historical': 6}
    assert rows[0]['created_at_epoch'] == 1791335704
    assert rows[0]['date'] == datetime.fromtimestamp(1791335704, timezone.utc).isoformat()
    assert rows[0]['message_id'] == FIXTURE['messages']['canvassMessages'][0]['messageId']
    assert all(row['sentiment_assessment'] == 'not_assessed' and 'sentimentLabel' not in row for row in rows)
    assert all(source.verified_sample(row, DATA) for row in rows)


@pytest.mark.parametrize('field,value', [('symbol','5314.TWO'),('strippedSymbol','5314'),
    ('exchange','TAI'),('holdingType','ETF'),('symbolName','台積電'),('messageBoardId','../other')])
def test_wrong_quote_identity_does_not_supply_other_board(field, value):
    stores = deepcopy(FIXTURE['quote_stores'])
    stores['QuoteFundamental']['currentSymbolInfo'][field] = value
    with pytest.raises(ValueError):
        source.quote_board(quote(stores), '3587.TWO', DATA)


@pytest.mark.parametrize('path,value', [('namespace','yahoo_content'),('context','finmb_1_lang_zh'),
                                     ('disabled', True),('error', True)])
def test_unbound_quote_board_rejected(path, value):
    stores = deepcopy(FIXTURE['quote_stores'])
    stores['CanvassStore']['comments']['commentCanvass-finmb_39965474_lang_zh'][path] = value
    with pytest.raises(ValueError):
        source.quote_board(quote(stores), '3587.TWO', DATA)


@pytest.mark.parametrize('field,value,reason', [
    ('contextId','finmb_1_lang_zh','board_mismatch'), ('namespace','yahoo_content','board_mismatch'),
    ('messageId','not-a-message','invalid_message_id'), ('meta.visibility','PRIVATE','not_public_original_text'),
    ('meta.type','SMARTLINK','not_public_original_text'), ('meta.messageEntity','REPLY','not_public_original_text'),
    ('meta.createdAt',True,'unknown_date'), ('meta.createdAt',float('inf'),'unknown_date'),
    ('meta.createdAt',int(NOW.timestamp())+1,'future'), ('details.userText','https://example.test','unusable_text'),
    ('details.userText','<script>bad</script>','unusable_text')])
def test_bad_comment_is_excluded_without_discarding_valid_sibling(field, value, reason):
    row = deepcopy(FIXTURE['messages']['canvassMessages'][1])
    owner, _, name = field.rpartition('.')
    if owner:
        row[owner][name] = value
    else:
        row[field] = value
    if value == float('inf'):
        # Nonfinite wire values are rejected for the whole malformed response.
        with pytest.raises(ValueError):
            selected([FIXTURE['messages']['canvassMessages'][0],row])
        return
    rows, audit = selected([FIXTURE['messages']['canvassMessages'][0], row])
    assert len(rows) == 1 and audit['rejected_reason_counts'] == {reason:1}


def test_recent_edit_does_not_make_old_publication_recent():
    row = deepcopy(FIXTURE['messages']['canvassMessages'][-1])
    row['meta']['updatedAt'] = int(NOW.timestamp())
    rows, audit = selected([row])
    assert rows == [] and audit['rejected_reason_counts'] == {'historical':1}


def test_duplicate_id_not_two_samples():
    row = FIXTURE['messages']['canvassMessages'][0]
    rows, audit = selected([row, row])
    assert len(rows) == 1 and audit['rejected_reason_counts'] == {'duplicate_message_id':1}


def test_cleaned_empty_text_is_not_a_sample():
    row = deepcopy(FIXTURE['messages']['canvassMessages'][0])
    row['details']['userText'] = '&nbsp;&nbsp;'
    rows, audit = selected([row])
    assert rows == [] and audit['rejected_reason_counts'] == {'unusable_text':1}


def test_different_original_ids_survive_same_text_reselection():
    from source_content_selection import reselect_social_context
    row = deepcopy(FIXTURE['messages']['canvassMessages'][0])
    other = deepcopy(row)
    other['messageId'] = FIXTURE['messages']['canvassMessages'][1]['messageId']
    rows, _ = selected([row,other])
    data = {**DATA, 'social_sentiment': {'yahoo_stock_direct':rows}}
    reselect_social_context(data, cutoff=NOW)
    assert data['social_sentiment']['sample_count'] == 2


def test_count_only_empty_response_does_not_become_samples():
    rows, audit = selected([])
    assert rows == [] and audit['usable_count'] == 0


@pytest.mark.parametrize('raw', [b'{"canvassMessages":[],"canvassMessages":[{}]}', b'{"bad":NaN}', b'x'*250001])
def test_ambiguous_or_oversize_payload_rejected(raw):
    with pytest.raises(ValueError):
        source.parse_comments(raw, source.quote_board(quote(), '3587.TWO', DATA), now=NOW)


def test_verified_yahoo_board_recovers_empty_social_provider(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.market_sources import cmoney_stock_posts, yahoo_stock_comments
    from data_fetch.types import FetchRequest
    from source_content_selection import reselect_social_context
    from data_trust_audit import source_record_count

    calls = []
    record = selected()[0][0]
    stamp = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    record.update(date=datetime.fromtimestamp(stamp, timezone.utc).isoformat(), created_at_epoch=stamp)
    monkeypatch.setattr(cmoney_stock_posts, "fetch_cmoney_stock_posts", lambda *a, **k: calls.append("cmoney") or [])
    monkeypatch.setattr(news_fetchers, "fetch_ptt_stock_sentiment", lambda *a, **k: calls.append("ptt") or [])
    monkeypatch.setattr(yahoo_stock_comments, "fetch_yahoo_stock_comments", lambda *a, **k: calls.append("yahoo") or [record])
    data = {"ticker": "3587.TWO", "company_name": "閎康", "quote_type": "EQUITY", "exchange": "TWO"}
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker("3587.TWO"), {"data": data})
    assert calls == ["cmoney", "yahoo"]
    assert result.status == "success"
    assert result.value["sample_count"] == 1
    assert result.value["yahoo_stock_direct"][0]["message_id"] == record["message_id"]
    snapshot = {**data, "social_sentiment": result.value}
    reselect_social_context(snapshot)
    assert snapshot["social_sentiment"]["sample_count"] == 1
    assert source_record_count("social_sentiment", snapshot) == 1


@pytest.mark.parametrize('field,value', [('quote_ticker','5314.TWO'),('quote_company','台積電'),
    ('message_id','bad'),('created_at_epoch',True),('response_sha256',None),('source_document_url','https://example.test'),
    ('message_namespace','yahoo_content'),('message_visibility','PRIVATE'),('message_type','SMARTLINK'),('message_entity','REPLY')])
def test_refresh_rejects_missing_or_wrong_receipt(field, value):
    from source_content_selection import reselect_social_context
    from data_trust_audit import source_record_count
    row = selected()[0][0]
    row[field] = value
    data = {**DATA, 'social_sentiment': {'yahoo_stock_direct':[row]}}
    assert source_record_count('social_sentiment', data) == 0
    reselect_social_context(data, cutoff=NOW)
    assert data['social_sentiment']['yahoo_stock_direct'] == []
    assert data['social_sentiment']['sample_count'] == 0


def test_existing_verified_source_does_not_fetch_yahoo(monkeypatch):
    import news_fetchers
    from data_fetch.agent_context_providers import SocialSentimentProvider
    from data_fetch.market_sources import cmoney_stock_posts
    from data_fetch.types import FetchRequest
    row = selected()[0][0]
    row['date'] = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(cmoney_stock_posts, 'fetch_cmoney_stock_posts', lambda *a, **k:[row])
    monkeypatch.setattr(news_fetchers, 'fetch_ptt_stock_sentiment', lambda *a, **k: pytest.fail('not needed'))
    monkeypatch.setattr(source, 'fetch_yahoo_stock_comments', lambda *a, **k: pytest.fail('not needed'))
    result = SocialSentimentProvider()._fetch_uncached(FetchRequest.from_ticker('3587.TWO'), {'data':DATA})
    assert result.status == 'success' and result.value['yahoo_stock_direct'] == []


def test_actual_acquisition_binds_quote_and_comments(monkeypatch):
    urls = []
    monkeypatch.setattr(source, '_now',lambda:NOW)
    monkeypatch.setattr(source, '_download', lambda url, deadline, diag: urls.append(url) or (quote() if len(urls)==1 else comments()))
    diag = {}
    rows = source.fetch_yahoo_stock_comments('3587.TWO', DATA, diagnostics=diag)
    assert len(rows) == 4 and len(urls) == 2
    assert urls[1] == source.comment_url('finmb_39965474_lang_zh')
    assert diag['raw_count'] == 10 and diag['rejected_reason_counts'] == {'historical':6}


def test_received_429_stops_before_second_request_and_preserves_cooldown(monkeypatch):
    import httpx
    from search_provider_runtime import SourceResponseError
    calls = []
    def refusal(*args):
        exc = SourceResponseError('rate_limited',status_code=429)
        exc.response = httpx.Response(429, headers={'Retry-After':'3600'}, request=httpx.Request('GET',args[0]))
        raise exc
    monkeypatch.setattr(source, '_download',refusal)
    monkeypatch.setattr(source, 'remember_failure', lambda key, exc:calls.append((key,exc.response.headers['Retry-After'])))
    diag = {}
    assert source.fetch_yahoo_stock_comments('3587.TWO', DATA, diagnostics=diag) == []
    assert diag['error_kind'] == 'rate_limited' and diag['http_status'] == 429
    assert calls == [(source.GUARD,'3600')]


def test_cooldown_has_zero_network(monkeypatch):
    monkeypatch.setattr(source, 'cooldown_state',lambda *a: {'until':9999999999})
    monkeypatch.setattr(source, '_download', lambda *a: pytest.fail('blocked'))
    diag = {}
    assert source.fetch_yahoo_stock_comments('3587.TWO', DATA, diagnostics=diag) == []
    assert diag['status'] == 'cooldown' and diag['http_request_sent'] is False


@pytest.mark.parametrize('failure', ['lease_lost', 'timeout'])
def test_parse_completion_cannot_publish_after_ownership_or_deadline_loss(monkeypatch, failure):
    from contextlib import contextmanager
    alive, calls = [True], []
    @contextmanager
    def admission(*a, **k):
        yield lambda:alive[0]
    monkeypatch.setattr(source, 'endpoint_admission', admission)
    monkeypatch.setattr(source, '_download', lambda *a: calls.append(1) or (quote() if len(calls)==1 else comments()))
    parse = source.parse_comments
    def delayed_parse(*a, **k):
        out = parse(*a, **k)
        if failure == 'lease_lost':
            alive[0] = False
        else:
            monkeypatch.setattr(source.time, 'monotonic', lambda: 9999999999999.)
        return out
    monkeypatch.setattr(source, 'parse_comments', delayed_parse)
    diag = {}
    assert source.fetch_yahoo_stock_comments('3587.TWO', DATA, diagnostics=diag) == []
    assert diag['error_kind'] == failure


@pytest.mark.parametrize('url', ['https://tw.stock.yahoo.com/quote/3587.TWO',
                               source.comment_url('finmb_39965474_lang_zh')])
def test_public_transport_additions_use_same_bounded_unsigned_request(monkeypatch, url):
    import time
    from data_fetch.market_sources import yahoo_taiwan_transport as transport
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for key in transport.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(transport, '_curl_version',lambda *a:'8.7.1')
    calls = []
    def collect(argv, deadline, **kwargs):
        calls.append((argv,deadline,kwargs))
        meta = {'http_code':200,'url_effective':url,'num_redirects':0,'http_version':'2'}
        return {'body':b'public','headers':b'HTTP/2 200\r\n\r\n',
                'metadata':json.dumps(meta).encode(),'process_started':True},0,None
    monkeypatch.setattr(transport, '_collect', collect)
    with transport.curl_stream('GET',url,deadline=time.monotonic()+15,diagnostics={}) as response:
        assert response.content == b'public'
    assert len(calls) == 1 and calls[0][2]['body_limit'] == 2*1024*1024
    argv = calls[0][0]
    assert float(argv[argv.index('--max-time')+1]) <= 9
    assert argv[argv.index('--retry')+1] == '0' and argv[argv.index('--max-redirs')+1] == '0'
    assert not any(x in argv for x in ['--cookie','--header','--user','--insecure','--location'])


@pytest.mark.parametrize('url', [source.comment_url('finmb_39965474_lang_zh').replace('count=10','count=100'),
    source.comment_url('finmb_39965474_lang_zh')+'?credential=secret',
    'https://tw.stock.yahoo.com/quote/3587.TWO/profile', 'https://finance.yahoo.com/quote/3587.TWO'])
def test_transport_does_not_accept_other_resources_or_credentials(monkeypatch, url):
    import time
    from data_fetch.market_sources import yahoo_taiwan_transport as transport
    from search_provider_runtime import SourceResponseError
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    monkeypatch.setattr(transport, '_collect',lambda *a, **k:pytest.fail('no transfer'))
    with pytest.raises(SourceResponseError) as captured:
        with transport.curl_stream('GET',url,deadline=time.monotonic()+15,diagnostics={}):
            pass
    assert captured.value.error_kind == 'transport_url_invalid'
