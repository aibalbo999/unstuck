"""Collector integration with synthetic originals; no real HTTP/acquisition credit."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import httpx
import pytest

import free_macro_fetcher as fetcher


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def vix_body():
    day=datetime.now(timezone.utc).strftime("%m/%d/%Y")
    return f"DATE,OPEN,HIGH,LOW,CLOSE\n{day},18,21,17,20\n".encode()


def install_original(monkeypatch, body=None):
    calls=[]
    def read(url,**kwargs):
        calls.append((url,kwargs));kwargs["trace"].update(http_request_sent=True,http_status=200,response_complete=True)
        return body or vix_body(),datetime.now(timezone.utc).timestamp()
    monkeypatch.setattr(fetcher,"_read_original",read)
    return calls


def test_normal_global_cache_replays_original_without_second_request(monkeypatch):
    calls=install_original(monkeypatch)
    first=fetcher.fetch_free_macro_component("vix")
    second=fetcher.fetch_free_macro_component("vix")
    assert first["status"]==second["status"]=="success"
    assert first["new_original_acquired"] is True
    assert second["new_original_acquired"] is False and second["cache_hit"] is True
    assert len(calls)==1
    receipt=first["observation"]["original_receipt"]
    assert receipt["raw_response_sha256"]==hashlib.sha256(vix_body()).hexdigest()


def test_corrupt_saved_original_never_counts_as_success(monkeypatch):
    import official_response_evidence
    calls=install_original(monkeypatch)
    assert fetcher.fetch_free_macro_component("vix")["status"]=="success"
    monkeypatch.setattr(official_response_evidence,"read_response",lambda *a,**k:b"wrong saved body")
    result=fetcher.fetch_free_macro_component("vix")
    assert result["status"]=="unavailable" and result["new_original_acquired"] is False
    assert result["qualification_error"]=="original_replay_failed" and len(calls)==1


def test_failed_parse_does_not_store_success_or_repeat_during_cooldown(monkeypatch):
    calls=install_original(monkeypatch,b"wrong provider format")
    first=fetcher.fetch_free_macro_component("vix")
    second=fetcher.fetch_free_macro_component("vix")
    assert first["status"]==second["status"]=="unavailable"
    assert first["new_original_acquired"] is second["new_original_acquired"] is False
    assert len(calls)==1 and second["acquisition_attempted"] is False


def test_singleflight_busy_does_not_send(monkeypatch):
    import shared_provider_cache
    @contextmanager
    def busy(*a,**k):yield False
    monkeypatch.setattr(shared_provider_cache,"_process_lock",busy)
    calls=install_original(monkeypatch)
    result=fetcher.fetch_free_macro_component("vix")
    assert result["status"]=="unavailable" and not calls
    assert result["metadata"]["error_kind"]=="single_flight_busy"


def test_bls_admission_refusal_precedes_http_client(monkeypatch):
    import bls_request_admission
    import external_http_client
    monkeypatch.setattr(external_http_client,"proxy_url_for_request",lambda *a:None)
    def refuse(self):raise bls_request_admission.BlsAdmissionBlocked("rolling_24h_limit")
    monkeypatch.setattr(bls_request_admission.BlsAdmissionStore,"reserve",refuse)
    clients=[]
    monkeypatch.setattr(fetcher.httpx,"Client",lambda **k:clients.append(k))
    result=fetcher.fetch_free_macro_component("us_cpi_yoy")
    assert result["status"]=="unavailable" and not clients
    assert result["metadata"]["error_kind"]=="BlsAdmissionBlocked"
    assert result["new_original_acquired"] is False


@pytest.mark.parametrize("status,body",[(302,b"redirect"),(429,b"quota"),(200,b""),(200,b"123456")])
def test_transport_rejects_redirect_error_empty_or_over_limit(monkeypatch,status,body):
    import external_http_client
    import provider_throttle
    real_client=httpx.Client;calls=[]
    def handler(request):calls.append(request);return httpx.Response(status,content=body)
    monkeypatch.setattr(external_http_client,"proxy_url_for_request",lambda *a:None)
    monkeypatch.setattr(provider_throttle,"enforce_provider_throttle",lambda *a:None)
    monkeypatch.setattr(fetcher.httpx,"Client",lambda **k:real_client(transport=httpx.MockTransport(handler),**k))
    with pytest.raises((ValueError,httpx.HTTPStatusError)):
        fetcher._read_original("https://example.test/original",provider="test",maximum=5,timeout=5)
    assert len(calls)==1


@pytest.mark.parametrize("timeout",[0,-1,float("nan"),float("inf"),31,True])
def test_invalid_timeout_fails_before_cache_or_network(timeout):
    with pytest.raises(ValueError):fetcher.fetch_free_macro_component("vix",timeout=timeout)


def test_private_receipt_paths_do_not_enter_prompt_projection(monkeypatch):
    import json
    from prompt_evidence import prompt_evidence_copy
    install_original(monkeypatch)
    result=fetcher.fetch_free_macro_component("vix")
    public=json.dumps(prompt_evidence_copy(result),ensure_ascii=False)
    assert "raw_response_path" not in public and "/Volumes/" not in public
    assert "Cboe" in public and "historical_pit_verified" in public


def test_same_original_reuses_parser_without_sharing_mutable_result(monkeypatch):
    calls=install_original(monkeypatch);parses=[]
    definition=fetcher.DEFINITIONS["vix"];real=definition[2]
    def parser(raw,asof):parses.append((raw,asof));return real(raw,asof)
    monkeypatch.setitem(fetcher.DEFINITIONS,"vix",(*definition[:2],parser,*definition[3:]))
    first=fetcher.fetch_free_macro_component("vix")
    first["observation"]["value"]=99
    second=fetcher.fetch_free_macro_component("vix")
    assert len(calls)==1 and len(parses)==1
    assert second["observation"]["value"]==20 and second["cache_hit"] is True


def test_parser_memo_is_bound_to_raw_bytes_parser_and_evaluation_date():
    from datetime import date
    calls=[]
    def parse(raw,asof):calls.append((raw,asof));return {"values":[len(raw)]}
    first=fetcher._parse_original(parse,b"a",date(2026,11,1));first["values"].append(999)
    assert fetcher._parse_original(parse,b"a",date(2026,11,1))=={"values":[1]}
    fetcher._parse_original(parse,b"ab",date(2026,11,1))
    fetcher._parse_original(parse,b"a",date(2026,11,2))
    assert len(calls)==3
