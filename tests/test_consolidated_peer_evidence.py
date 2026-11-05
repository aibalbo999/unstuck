"""Synthetic normal source frames; no real HTTP or production acquisition."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import pytest

from test_peer_reference_evidence import evidence_environment, DAY
from test_consolidated_peer_profiles import reference6558, income6558, index6558
from test_peer_reference_transport import parts
from provider_correlation import correlation_scope, source_operation
from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope


@contextmanager
def normal_frame(*, observe=True, source='dynamic_peer_metrics'):
    with correlation_scope(replace=True, ticker='6409.TW', fetch_id='normal-fixture'), source_operation(source, 'FinMind/yfinance'), receipt_observation_scope(observe):
        yield


@pytest.fixture
def environment6558(evidence_environment, monkeypatch):
    from data_fetch.market_sources import peer_reference_evidence as e, peer_reference_transport as t
    store, calls, master = evidence_environment
    raw, _ = e.read_cached_listed_roster_bytes()
    rows = json.loads(raw)
    rows[-1].update({'公司代號':'6558','公司名稱':'興能高科技股份有限公司','公司簡稱':'興能高',
        '營利事業統一編號':'97430131','產業別':'31'})
    raw = json.dumps(rows, ensure_ascii=False).encode()
    master.update(source_payload_sha256=sha256(raw).hexdigest(), source_payload_bytes=len(raw))
    monkeypatch.setattr(e, 'read_cached_listed_roster_bytes', lambda:(raw, deepcopy(master)))
    old_download = t.PeerIncomeHttp._download
    def download(self, request, diagnostic):
        kind, p = request['kind'], request['params']
        if kind in {'home','methodology'}:
            return old_download(self, request, diagnostic)
        calls.append(deepcopy(request))
        if kind == 'reference': body = reference6558()
        elif kind == 'index': body = index6558(p['year'], [2] if p['year']==2026 else [2,4])
        else: body = income6558(p['year'], p['quarter'], {(2026,2):-100,(2025,2):-30,(2025,4):-70}[(p['year'],p['quarter'])])
        return self._consume(request, request['url'], parts(request, body=body), 0, None, diagnostic)
    monkeypatch.setattr(t.PeerIncomeHttp, '_download', download)
    return store, calls, master


def test_normal_producer_replays_exact6558_current_owners_without_a_numeric_PE(environment6558):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income, verified_reference_income
    with normal_frame():
        value = collect_reference_income('6558.TW', DAY.isoformat(), today=DAY)
    derived = verified_reference_income(value['source_record_archive'], ticker='6558.TW', observed_at=DAY.isoformat(), today=DAY)
    assert derived['net_income_twd'] == -140000
    assert value['scope']=='consolidated_parent_income' and 'pe_ttm'not in value
    assert len(environment6558[1])==8


@pytest.mark.parametrize('mode', ['unbound', 'research', 'wrong_source'])
def test_new_profile_never_acquires_from_an_unbound_or_research_path(environment6558, mode):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    with pytest.raises(ValueError):
        if mode=='unbound': collect_reference_income('6558.TW', DAY.isoformat(), today=DAY)
        else:
            with normal_frame(observe=mode!='research', source='financial_statements'if mode=='wrong_source'else'dynamic_peer_metrics'):
                collect_reference_income('6558.TW', DAY.isoformat(), today=DAY)
    assert not environment6558[1] and not environment6558[0]


@pytest.mark.parametrize('damage', ['issuer','amount','period','missing_owner','request','master'])
def test_new_reason_cannot_survive_broken_identity_period_or_original_owner(environment6558, damage):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income, verified_reference_income
    with normal_frame(): value=collect_reference_income('6558.TW', DAY.isoformat(), today=DAY)
    proof=deepcopy(value['source_record_archive'])
    if damage=='issuer': proof['ticker']='6230.TW'
    elif damage=='amount': proof['derived']['net_income_twd']=-1
    elif damage=='period': proof['derived']['period_end']='2026-09-30'
    elif damage=='missing_owner': environment6558[0].clear()
    elif damage=='request': proof['components']['income:2025Q2']['spec']['params']['consolidated_reference_issuer']='6230.TW'
    else: environment6558[2]['source_payload_sha256']='0'*64
    assert verified_reference_income(proof,ticker='6558.TW',observed_at=DAY.isoformat(),today=DAY)is None


def test_existing_annual_original_holds_new_profile_without_refetch_or_ttl_change(environment6558):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    store, calls, _=environment6558
    store['financial_data:6558.TW']={'source_audit':[{'source':'financial_statements','status':'success','documents':[{'year':2025}]}]}
    before=deepcopy(store)
    with normal_frame(), pytest.raises(ValueError,match='existing annual'):
        collect_reference_income('6558.TW',DAY.isoformat(),today=DAY)
    assert not calls and store==before
