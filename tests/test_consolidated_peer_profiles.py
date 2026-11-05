"""Explicit issuer profiles never turn an arbitrary blank P/E into a loss."""
from datetime import date
import json
import pytest
from test_peer_reference_income import reference_body, income_body, index_body
from data_fetch.market_sources import peer_reference_income as parser
from data_fetch.market_sources import peer_reference_transport as transport

DAY = date(2026, 11, 4)


def reference6558():
    value = json.loads(reference_body())
    value['data'][-1][:2] = ['6558', '興能高']
    return json.dumps(value, ensure_ascii=False).encode()


def income6558(year, quarter, value):
    return income_body(year, quarter, value).decode().replace(
        '6230 尼得科超眾 (上市電腦及週邊設備業)', '6558 興能高 (上市其他電子業)').encode()


def index6558(year, quarters):
    return index_body(year, quarters).decode('big5').replace('6230', '6558').replace('尼得科超眾', '興能高').encode('big5')


def test_qualified_consolidated_issuer_keeps_exact_period_parent_scope_and_request_identity():
    assert parser.parse_reference(reference6558(), DAY, issuer_ticker='6558.TW')['reference_quarter'] == '115/2'
    assert parser.parse_calendar_index(index6558(2025, [2,4]), 2025, [2,4], DAY, issuer_ticker='6558.TW')[4]['filename'] == '202504_6558_AI1.pdf'
    assert parser.parse_cumulative_income(income6558(2026, 2, -100), 2026, 2, issuer_ticker='6558.TW') == -100000
    request = transport.spec('income', year=2026, quarter=2, peer_ticker='6558.TW')
    assert request['data']['companyId'] == '6558 興能高'
    assert request['params']['consolidated_reference_issuer'] == '6558.TW'
    assert transport.canonical_spec(request) == request


def test_legacy_default_spec_and_common_original_keys_remain_exact():
    for kind, kwargs in [('home', {}), ('methodology', {}), ('reference', {'day': DAY})]:
        old = transport.spec(kind, **kwargs)
        assert transport.spec(kind, peer_ticker='6558.TW', **kwargs) == old
        assert transport.raw_key(old) == transport.raw_key(transport.spec(kind, peer_ticker='6558.TW', **kwargs))
    old = transport.spec('income', year=2026, quarter=2)
    assert old['params'] == {'year':2026, 'quarter':2}
    assert old['data']['companyId'] == '6230 尼得科超眾 (上市電腦及週邊設備業)'


@pytest.mark.parametrize('ticker', ['2646.TW', '6558.TWO', '2330.TW', '6558', True, None])
def test_nonqualified_or_individual_issuer_cannot_enter_consolidated_parser(ticker):
    with pytest.raises(ValueError):
        parser.parse_cumulative_income(income6558(2026,2,-100), 2026,2, issuer_ticker=ticker)


def test_issuer_profile_is_frozen_and_cannot_be_supplied_by_request_payload():
    from dataclasses import FrozenInstanceError
    from data_fetch.market_sources.peer_reference_issuers import consolidated_issuer
    profile=consolidated_issuer('6558.TW')
    with pytest.raises(FrozenInstanceError): profile.ubn='00000000'
    assert not hasattr(profile,'__dict__')
    with pytest.raises(ValueError): consolidated_issuer({'ticker':'6558.TW'})


@pytest.mark.parametrize('damage', ['issuer','scope','currency','parent_total_conflict','period'])
def test_new_profile_retains_the_same_scope_unit_and_parent_total_guards(damage):
    raw=income6558(2026,2,-100)
    if damage=='issuer':raw=raw.replace(b'6558',b'6230')
    elif damage=='scope':raw=raw.replace('合併'.encode(),'個別'.encode())
    elif damage=='currency':raw=raw.replace('新台幣'.encode(),'美元'.encode())
    elif damage=='parent_total_conflict':raw=raw.replace(b'-100</td>',b'-101</td>',1)
    else:raw=raw.replace(b'2026Q2',b'2025Q2')
    with pytest.raises(ValueError): parser.parse_cumulative_income(raw,2026,2,issuer_ticker='6558.TW')


def test_new_request_cannot_cross_consolidated_or_individual_transport_subject():
    from test_peer_reference_transport import parts
    request=transport.spec('income',year=2026,quarter=2,peer_ticker='6558.TW')
    for ticker in ('6230.TW','2646.TW'):
        with pytest.raises(ValueError): transport.PeerIncomeHttp(peer_ticker=ticker)._consume(request,request['url'],parts(request),0,None,{})
    for target in ('6230.TW','6558.TWO','2330.TW'):
        changed=json.loads(json.dumps(request));changed['params']['consolidated_reference_issuer']=target
        with pytest.raises(ValueError): transport.canonical_spec(changed)
