"""A complete verified cached master can avoid a redundant identity HTTP hop."""
import json
import base64
from datetime import datetime
from hashlib import sha256
import time

import pytest


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def install_roster(*, target_changes=None, count=800):
    from cache_store import set_cache_json
    from data_fetch.market_sources.official_company_legal_name import parse_roster, URLS
    from official_response_evidence import archive_response
    rows = [{"公司代號": str(n), "公司名稱": "測試股份有限公司", "公司簡稱": "測試", "出表日期": "1151008"}
            for n in range(1000, 1000 + count - 1)]
    rows.append({"公司代號": "3023", "公司名稱": "信邦電子股份有限公司", "公司簡稱": "信邦", "英文簡稱": "SINBON",
                 "出表日期": "1151008", "網址": "https://www.sinbon.com", "營利事業統一編號": "23542766"})
    rows[-1].update(target_changes or {})
    raw = json.dumps(rows, ensure_ascii=False).encode()
    stamp = time.time() - 3600
    receipt = archive_response(raw, source_url=URLS[".TW"], retrieved_at=stamp)
    assert receipt["status"] == "archived"
    key = "shared_provider:v1:" + sha256(b"official-company-roster:v2:.TW").hexdigest()
    row = {"value": parse_roster(raw, ".TW"), "fetched_at_epoch": stamp, "fresh_until_epoch": stamp + 86400,
           "retained_until_epoch": stamp + 86400}
    set_cache_json(key, row, ttl_seconds=86400)
    return raw, stamp, key, row


def test_current_complete_master_reuses_bytes_and_original_epoch_without_http(monkeypatch):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp, ROSTER_URL
    from search_provider_runtime import SourceResponseError
    raw, stamp, _, _ = install_roster()
    calls = []

    def unreachable(self, url, diagnostic):
        calls.append(url)
        raise SourceResponseError("timeout")

    monkeypatch.setattr(IssuerNewsHttp, "_download", unreachable)
    http = IssuerNewsHttp(time.monotonic() + 1)
    assert http.get(ROSTER_URL) == raw
    assert calls == [] and http.http_request_count == 0
    assert http.components[0]["cache_hit"] is True
    assert http.components[0]["fetched_at_epoch"] == stamp
    assert http.components[0]["http_request_sent"] is False


@pytest.mark.parametrize("change", ["no_archive", "wrong_digest", "partial_parsed", "partial_raw", "future", "expired",
                                     "nan", "bool_epoch", "extended_expiry", "cached_error", "wrong_url"])
def test_unverified_shared_payload_uses_original_route_not_reconstructed_rows(monkeypatch, change):
    from cache_store import set_cache_json
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp, ROSTER_URL
    from runtime_paths import current_runtime_paths
    from search_provider_runtime import SourceResponseError
    raw, stamp, key, row = install_roster(count=799 if change == "partial_raw" else 800)
    if change == "no_archive":
        path = current_runtime_paths().cache_dir / "official-response-evidence" / (row["value"]["response_sha256"] + ".gz")
        path.unlink()
    elif change == "wrong_digest": row["value"]["response_sha256"] = "f" * 64
    elif change == "partial_parsed": row["value"]["entries"].pop("3023")
    elif change == "future": row["fetched_at_epoch"] = time.time() + 100
    elif change == "expired": row["fresh_until_epoch"] = time.time() - 1
    elif change == "nan": row["fetched_at_epoch"] = float("nan")
    elif change == "bool_epoch": row["fetched_at_epoch"] = True
    elif change == "extended_expiry": row["fresh_until_epoch"] = stamp + 86400 * 2
    elif change == "cached_error": row["error_kind"] = "SourceResponseError"
    elif change == "wrong_url": row["value"]["source_url"] = "https://evil.test/master"
    set_cache_json(key, row, ttl_seconds=86400)
    called = []

    def original(self, url, diagnostic):
        called.append(url)
        raise SourceResponseError("timeout")

    monkeypatch.setattr(IssuerNewsHttp, "_download", original)
    http = IssuerNewsHttp(time.monotonic() + 1)
    with pytest.raises(SourceResponseError): http.get(ROSTER_URL)
    assert called == [ROSTER_URL]


@pytest.mark.parametrize("change", [{"公司名稱": "其他股份有限公司"}, {"英文簡稱": "OTHER"},
                                     {"網址": "https://www.sinbon.com.evil.test"}, {"出表日期": "1140101"}])
def test_reused_complete_bytes_still_require_exact_issuer_domain_and_date(monkeypatch, change):
    from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news, TAIPEI
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    install_roster(target_changes=change)
    monkeypatch.setattr(IssuerNewsHttp, "_download", lambda *a, **k: pytest.fail("unverified article must not be requested"))
    values, audit = fetch_recent_issuer_news("3023.TW", now=datetime(2026, 10, 10, tzinfo=TAIPEI))
    assert values == [] and audit["status"] == "error" and audit["http_request_count"] == 0


def test_newer_native_master_keeps_priority_and_its_original_epoch(monkeypatch):
    from cache_store import set_cache_json
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp, ROSTER_URL
    raw, stamp, _, _ = install_roster()
    rows = json.loads(raw);rows[-1]["出表日期"] = "1151009";new_raw = json.dumps(rows, ensure_ascii=False).encode()
    newer = time.time() - 10
    value = {"url": ROSTER_URL, "body_b64": base64.b64encode(new_raw).decode(), "sha256": sha256(new_raw).hexdigest()}
    key = "shared_provider:v1:" + sha256(("issuer-news-raw:v1:" + ROSTER_URL).encode()).hexdigest()
    set_cache_json(key, {"value": value, "fetched_at_epoch": newer, "fresh_until_epoch": newer + 1800,
                        "retained_until_epoch": newer + 1800}, ttl_seconds=1800)
    monkeypatch.setattr(IssuerNewsHttp, "_download", lambda *a, **k: pytest.fail("no new HTTP"))
    http = IssuerNewsHttp(time.monotonic() + 1)
    assert http.get(ROSTER_URL) == new_raw and http.components[0]["fetched_at_epoch"] == newer
    assert http.http_request_count == 0


def test_reuse_does_not_clear_existing_raw_failure_or_renew_master(monkeypatch):
    from cache_store import get_cache_json, set_cache_json
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp, ROSTER_URL
    raw, stamp, key, row = install_roster()
    failure_key = "shared_provider:v1:" + sha256(("issuer-news-raw:v1:" + ROSTER_URL).encode()).hexdigest()
    failure = {"error_kind": "SourceResponseError", "retry_after_epoch": time.time() + 60}
    set_cache_json(failure_key, failure, ttl_seconds=120)
    monkeypatch.setattr(IssuerNewsHttp, "_download", lambda *a, **k: pytest.fail("no HTTP on reusable original"))
    assert IssuerNewsHttp(time.monotonic() + 1).get(ROSTER_URL) == raw
    assert get_cache_json(key) == row and get_cache_json(failure_key) == failure


def test_reuse_checks_parent_deadline_after_archive_validation(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as transport
    from data_fetch.market_sources import official_company_legal_name as legal
    from search_provider_runtime import SourceResponseError
    install_roster();clock = [100.]
    original = legal.read_cached_listed_roster_bytes
    monkeypatch.setattr(transport.time, "monotonic", lambda: clock[0])

    def slow():
        result = original();clock[0] += 2
        return result

    monkeypatch.setattr(legal, "read_cached_listed_roster_bytes", slow)
    monkeypatch.setattr(transport.IssuerNewsHttp, "_download", lambda *a, **k: pytest.fail("deadline passed"))
    http = transport.IssuerNewsHttp(101.)
    with pytest.raises(SourceResponseError) as error: http.get(transport.ROSTER_URL)
    assert error.value.error_kind == "timeout" and http.http_request_count == 0


def test_valid_newer_identity_conflict_cannot_fall_back_to_older_matching_master(monkeypatch):
    from cache_store import set_cache_json
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp, ROSTER_URL
    from data_fetch.market_sources.issuer_news import fetch_recent_issuer_news, TAIPEI
    raw, _, _, _ = install_roster()
    rows = json.loads(raw);rows[-1]["公司名稱"] = "不同法人股份有限公司"
    newer_raw = json.dumps(rows, ensure_ascii=False).encode();stamp = time.time() - 10
    key = "shared_provider:v1:" + sha256(("issuer-news-raw:v1:" + ROSTER_URL).encode()).hexdigest()
    set_cache_json(key, {"value": {"url": ROSTER_URL, "body_b64": base64.b64encode(newer_raw).decode(),
                                  "sha256": sha256(newer_raw).hexdigest()},
                        "fetched_at_epoch": stamp, "fresh_until_epoch": stamp + 1800,
                        "retained_until_epoch": stamp + 1800}, ttl_seconds=1800)
    monkeypatch.setattr(IssuerNewsHttp, "_download", lambda *a, **k: pytest.fail("identity conflict must stop before article"))
    values, audit = fetch_recent_issuer_news("3023.TW", now=datetime(2026, 10, 10, tzinfo=TAIPEI))
    assert values == [] and audit["status"] == "error"
    assert audit["http_request_count"] == 0 and audit["component_receipts"][0]["fetched_at_epoch"] == stamp


@pytest.mark.parametrize('change',[{'sha256':'f'*64},{'url':'https://evil.test/master'},{'body_b64':'invalid-base64'}])
def test_invalid_newer_native_cache_does_not_block_valid_shared_roster(monkeypatch,change):
    from cache_store import set_cache_json
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL
    raw,stamp,_,_=install_roster()
    newer=time.time()-10
    value={'url':ROSTER_URL,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    value.update(change)
    key='shared_provider:v1:'+sha256(('issuer-news-raw:v1:'+ROSTER_URL).encode()).hexdigest()
    set_cache_json(key,{'value':value,'fetched_at_epoch':newer,'fresh_until_epoch':newer+1800,'retained_until_epoch':newer+1800},ttl_seconds=1800)
    monkeypatch.setattr(IssuerNewsHttp,'_download',lambda *a,**k:pytest.fail('usable verified shared roster exists'))
    http=IssuerNewsHttp(time.monotonic()+1)
    assert http.get(ROSTER_URL)==raw
    assert http.http_request_count==0
    assert http.components[0]['fetched_at_epoch']==stamp
