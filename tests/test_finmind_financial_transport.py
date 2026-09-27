"""FinMind transport contracts; mock rows are synthetic, not live fill evidence."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.market_sources import taiwan
from data_fetch.market_sources.finmind_financial_transport import FinMindFinancialFetchError
from data_fetch.taiwan_providers import FinMindProvider
from data_fetch.types import FetchRequest


@pytest.fixture(autouse=True)
def isolated_provider_guards(monkeypatch):
    import provider_resilience
    import provider_throttle
    monkeypatch.setattr(provider_resilience, "_CIRCUITS", {})
    monkeypatch.setattr(provider_resilience, "_SHARED_CIRCUIT_STORE", None)
    monkeypatch.setattr(provider_resilience, "load_persisted_circuit", lambda *_: None)
    monkeypatch.setattr(provider_resilience, "persist_circuit_state", lambda *_: None)
    monkeypatch.setattr(provider_throttle, "_THROTTLES", {})
    monkeypatch.setenv("PROVIDER_RETRY_ATTEMPTS", "5")


def test_provider_preserves_completed_values_when_later_table_is_denied(monkeypatch):
    partial = {"years": ["2025"], "revenue_history": [2.0], "rows_by_year": {
        "2025": {"statement_date": "2025-12-31", "revenue": 2.0}}}
    components = {"financials": {"status": "success", "as_of": "2025-12-31"},
                  "balance": {"status": "error", "http_status": 429},
                  "cashflow": {"status": "not_attempted"}}
    calls = []
    def denied(ticker):
        calls.append(ticker)
        raise FinMindFinancialFetchError("provider_refused", status_code=429,
                                       partial_value=partial, component_statuses=components)
    monkeypatch.setattr(taiwan, "fetch_finmind_financial_statement_fallback", denied)
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "error"
    assert result.value == partial
    assert result.audit["component_statuses"] == components
    assert result.audit["record_count"] == 0
    assert calls == ["5314.TWO"]


def synthetic_tables():
    def rows(values):
        return [{"date": "2025-12-31", "stock_id": "5314", "type": name, "value": value,
                 "origin_name": name} for name, value in values.items()]
    quarters = [{"date": f"2025-{suffix}", "stock_id": "5314", "type": kind, "value": value,
                 "origin_name": "淨利（淨損）歸屬於母公司業主" if kind == "EquityAttributableToOwnersOfParent" else kind}
                for suffix in ("03-31", "06-30", "09-30", "12-31")
                for kind, value in {"Revenue": 5e8, "EquityAttributableToOwnersOfParent": 1e8}.items()]
    return {"financials": quarters,
            "balance": rows({"TotalAssets": 6e9, "Equity": 3e9}),
            "cashflow": rows({"NetCashInflowFromOperatingActivities": 5e8,
                              "PropertyAndPlantAndEquipment": -1e8})}


def test_financial_fallback_uses_one_bounded_transport_without_sdk_login(monkeypatch):
    import pandas as pd
    from data_fetch.market_sources import finmind_financial_transport as transport
    tables = synthetic_tables()
    sdk_logins, transport_calls = [], []
    class OldSDK:
        def __init__(self):
            sdk_logins.append("hidden user_info")
        def taiwan_stock_financial_statement(self, **kwargs):
            return pd.DataFrame(tables["financials"])
        def taiwan_stock_balance_sheet(self, **kwargs):
            return pd.DataFrame(tables["balance"])
        def taiwan_stock_cash_flows_statement(self, **kwargs):
            return pd.DataFrame(tables["cashflow"])
    def bounded(stock_id, start_date):
        transport_calls.append((stock_id, start_date))
        return {"tables": tables, "components": {}, "error": None}
    monkeypatch.setattr(taiwan, "DataLoader", OldSDK)
    monkeypatch.setattr(transport, "fetch_statement_tables", bounded, raising=False)
    result = taiwan.fetch_finmind_financial_statement_fallback("5314.TWO")
    assert sdk_logins == []
    assert len(transport_calls) == 1
    assert transport_calls[0][0] == "5314"
    assert result["fcf_history"] == [None]
    assert result["rows_by_year"]["2025"]["operating_cash_flow"] == 5e8
    assert result["rows_by_year"]["2025"]["property_and_equipment_cash_flow"] == -1e8
    assert result["rows_by_year"]["2025"]["free_cash_flow_status"] == "capex_scope_unverified"
    assert result["revenue_history"] == [2.0]


class FakeResponse:
    def __init__(self, payload=None, *, status=200, chunks=None):
        import json
        self.status_code = status
        self.chunks = chunks if chunks is not None else [json.dumps(payload).encode()]
        self.closed = False
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.closed = True
    def iter_content(self, chunk_size):
        yield from self.chunks


class FakeSession:
    def __init__(self, responses):
        self.headers, self.responses, self.calls = {}, list(responses), []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def mount(self, prefix, adapter):
        assert adapter.max_retries.total == 0
    def prepare_request(self, request):
        request.headers = self.headers.copy()
        return request.prepare()
    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        return {"proxies": proxies, "stream": stream, "verify": True}
    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def worker_messages(session):
    import time
    from data_fetch.market_sources import finmind_financial_transport as transport
    messages = []
    transport._worker_fetch({"stock_id": "5314", "start_date": "2020-01-01", "deadline": time.monotonic() + 20},
                            messages.append, session_factory=lambda: session)
    return messages


def test_worker_three_single_stock_requests_have_no_login_or_other_credentials(monkeypatch):
    from urllib.parse import parse_qs, urlsplit
    monkeypatch.setenv("FINMIND_TOKEN", "must-not-be-used")
    session = FakeSession([FakeResponse({"status": 200, "data": rows}) for rows in synthetic_tables().values()])
    messages = worker_messages(session)
    assert [m["kind"] for m in messages] == ["table", "table", "table", "done"]
    assert len(session.calls) == 3
    for (request, options), dataset in zip(session.calls, ("TaiwanStockFinancialStatements", "TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement")):
        url = urlsplit(request.url)
        assert (url.scheme, url.netloc, url.path) == ("https", "api.finmindtrade.com", "/api/v4/data")
        assert parse_qs(url.query) == {"dataset": [dataset], "data_id": ["5314"], "start_date": ["2020-01-01"]}
        assert request.headers["Authorization"] == "Bearer "
        assert options["allow_redirects"] is False
        assert 0 < max(options["timeout"]) <= 5
        assert options["stream"] is True


@pytest.mark.parametrize("status", [401, 402, 403, 429])
@pytest.mark.parametrize("json_status", [False, True])
def test_http_or_json_refusal_retains_prior_table_and_stops_next_request(status, json_status):
    first = FakeResponse({"status": 200, "data": synthetic_tables()["financials"]})
    denied = FakeResponse({"status": status, "data": [], "msg": "secret must not be copied"},
                          status=200 if json_status else status)
    session = FakeSession([first, denied, AssertionError("must not request cashflow")])
    messages = worker_messages(session)
    assert len(session.calls) == 2
    assert messages[0]["rows"] == synthetic_tables()["financials"]
    assert messages[1]["kind"] == "error"
    assert messages[1]["status_code"] == status
    assert messages[-1] == {"kind": "done"}
    assert "secret" not in repr(messages)
    assert first.closed and denied.closed


@pytest.mark.parametrize("response", [
    FakeResponse(status=302), FakeResponse(chunks=[b'not json']),
    FakeResponse({"status": 200, "data": {}}),
    FakeResponse({"status": 200, "data": [{"date": "2025-12-31", "stock_id": "wrong", "type": "Revenue", "value": 1}]}),
])
def test_invalid_response_stops_and_is_not_reported_as_empty_success(response):
    session = FakeSession([response, AssertionError("no second request")])
    messages = worker_messages(session)
    assert len(session.calls) == 1
    assert messages[0]["kind"] == "error"
    assert response.closed


def test_response_body_limit_stops_before_next_table(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    monkeypatch.setattr(transport, "BODY_LIMIT", 8)
    session = FakeSession([FakeResponse(chunks=[b'1234', b'56789'])])
    messages = worker_messages(session)
    assert messages[0]["reason"] == "response_too_large"
    assert len(session.calls) == 1


def test_worker_budget_is_shared_across_tables(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    now = [100.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    class SlowResponse(FakeResponse):
        def iter_content(self, chunk_size):
            now[0] += 12
            yield from self.chunks
    session = FakeSession([SlowResponse({"data": rows}) for rows in synthetic_tables().values()])
    messages = []
    transport._worker_fetch({"stock_id": "5314", "start_date": "2020-01-01", "deadline": 120}, messages.append,
                            session_factory=lambda: session)
    assert [m["kind"] for m in messages] == ["table", "error", "done"]
    assert messages[1]["reason"] == "deadline_exceeded"
    assert len(session.calls) == 2


def test_guard_open_and_local_cooldown_do_not_spawn(monkeypatch):
    import provider_resilience as resilience
    import provider_throttle
    import time
    from data_fetch.market_sources import finmind_financial_transport as transport
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("guard must stop spawn"))
    key = "FinMind financial statement fallback"
    breaker = resilience.get_circuit_breaker(key)
    breaker.state, breaker.last_failure_time = "OPEN", time.time()
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "unavailable"
    assert result.audit["error_kind"] == "ProviderCircuitOpenError"
    breaker.state = "CLOSED"
    provider_throttle._THROTTLES[key] = {"last_call_at": 0, "cooldown_until": time.time() + 100}
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "unavailable"
    assert result.audit["error_kind"] == "ProviderRateLimitOpenError"


@pytest.mark.parametrize("behavior", ["half_line", "done_then_hang", "completed_then_hang", "stderr_flood", "stdout_flood"])
def test_child_protocol_failures_are_killed_reaped_and_bounded(monkeypatch, tmp_path, behavior):
    import json
    import os
    import subprocess
    import time
    from data_fetch.market_sources import finmind_financial_transport as transport
    real_popen = subprocess.Popen
    created = []
    def capture(*args, **kwargs):
        assert kwargs["shell"] is False
        process = real_popen(*args, **kwargs)
        created.append(process)
        return process
    monkeypatch.setattr(transport.subprocess, "Popen", capture)
    metadata = {"status": "success", "http_status": 200, "response_sha256": "a" * 64, "response_bytes": 120}
    first = json.dumps({"kind": "table", "name": "financials", "rows": synthetic_tables()["financials"], "metadata": metadata})
    script = "import sys,time\nsys.stdin.buffer.read()\n"
    if behavior in ("completed_then_hang", "done_then_hang"):
        script += f"print({first!r},flush=True)\n"
    if behavior == "done_then_hang":
        script += "print('{\"kind\":\"error\",\"name\":\"balance\",\"reason\":\"http_refused\",\"status_code\":429,\"metadata\":{}}',flush=True)\nprint('{\"kind\":\"done\"}',flush=True)\n"
    elif behavior == "half_line":
        script += "sys.stdout.write('{\"kind\":');sys.stdout.flush()\n"
    elif behavior == "stderr_flood":
        script += "sys.stderr.write('x'*10000);sys.stderr.flush()\n"
    elif behavior == "stdout_flood":
        monkeypatch.setattr(transport, "STDOUT_LIMIT", 1000)
        script += "sys.stdout.write('x'*10000);sys.stdout.flush()\n"
    script += "time.sleep(5)\n"
    started = time.monotonic()
    outcome = transport._run_worker({"stock_id": "5314", "start_date": "2020-01-01", "deadline": started + 0.3},
                                    command=[sys.executable, "-c", script])
    assert time.monotonic() - started < 1.5
    assert outcome["error"] is not None
    assert len(created) == 1 and created[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.kill(created[0].pid, 0)
    if behavior in ("completed_then_hang", "done_then_hang"):
        assert outcome["tables"]["financials"] == synthetic_tables()["financials"]
    if behavior == "done_then_hang":
        assert outcome["error"] == {"reason": "http_refused", "status_code": 429}
        assert outcome["components"]["balance"]["reason_code"] == "http_refused"
        assert outcome["components"]["transport"]["reason_code"] == "deadline_exceeded"


def test_unexpected_process_start_error_is_nonretryable_and_does_not_repeat(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    calls = []
    def failed(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("runtime detail must not leak")
    monkeypatch.setattr(transport.subprocess, "Popen", failed)
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "error"
    assert len(calls) == 1
    assert "runtime detail" not in result.audit["message"]


def test_real_worker_obeys_inherited_test_network_boundary(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    monkeypatch.setenv("STOCK_AGENT_TEST_NO_NETWORK", "1")
    outcome = transport.fetch_statement_tables("5314", "2020-01-01")
    assert outcome["error"]["reason"] == "test_network_disabled"
    assert outcome["tables"] == {}
    assert "FINMIND_TOKEN" not in transport._worker_environment()


def test_valid_empty_table_is_partial_without_circuit_failure(monkeypatch):
    import provider_resilience
    from data_fetch.market_sources import finmind_financial_transport as transport
    tables = synthetic_tables()
    tables["balance"] = []
    components = {name: {"status": "success" if rows else "empty"} for name, rows in tables.items()}
    monkeypatch.setattr(transport, "fetch_statement_tables", lambda *_: {"tables": tables, "components": components, "error": None})
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "degraded_enrichment"
    assert result.value["revenue_history"] == [2.0]
    assert result.value["total_assets_history"] == [None]
    assert result.audit["component_statuses"]["balance"]["status"] == "empty"
    assert provider_resilience.get_circuit_breaker("FinMind financial statement fallback").failures == 0


def test_all_empty_tables_stay_unavailable_without_circuit_failure(monkeypatch):
    import provider_resilience
    from data_fetch.market_sources import finmind_financial_transport as transport
    components = {name: {"status": "empty"} for name in transport.DATASETS}
    monkeypatch.setattr(transport, "fetch_statement_tables", lambda *_: {"tables": {name: [] for name in components}, "components": components, "error": None})
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "unavailable"
    assert result.value == {}
    assert result.audit["component_statuses"] == components
    assert provider_resilience.get_circuit_breaker("FinMind financial statement fallback").failures == 0


def test_three_nonempty_tables_with_missing_fields_are_still_partial(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    tables = synthetic_tables()  # Missing gross profit/operating income, despite 3 nonempty tables.
    monkeypatch.setattr(transport, "fetch_statement_tables", lambda *_: {
        "tables": tables, "components": {name: {"status": "success"} for name in tables}, "error": None})
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "degraded_enrichment"
    assert result.value["fcf_history"] == [None]
    assert result.value["rows_by_year"]["2025"]["operating_cash_flow"] == 5e8
    assert result.value["gross_profit_history"] == [None]
    assert result.audit["quality_status"] == "not_assessed"


def test_annual_income_zero_remains_available_but_capex_scope_keeps_partial(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    tables = synthetic_tables()
    tables["financials"] += [{"date": f"2025-{suffix}", "stock_id": "5314", "type": key, "value": 0}
                             for suffix in ("03-31", "06-30", "09-30", "12-31")
                             for key in ("GrossProfit", "OperatingIncome")]
    monkeypatch.setattr(transport, "fetch_statement_tables", lambda *_: {
        "tables": tables, "components": {name: {"status": "success"} for name in tables}, "error": None})
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "degraded_enrichment"
    assert result.value["gross_profit_history"] == [0.0]
    assert result.value["fcf_history"] == [None]
    assert result.audit["coverage_status"] == "partial"
    assert result.audit["quality_status"] == "not_assessed"


def test_partial_transport_values_reach_extractor_without_promoting_primary(monkeypatch):
    import pandas as pd
    from data_fetch.market_sources import finmind_financial_transport as transport
    from data_fetch.yfinance_extractors import extract_financial_histories
    class MissingPrimary:
        financials = cashflow = balance_sheet = pd.DataFrame()
    tables = {"financials": synthetic_tables()["financials"]}
    components = {"financials": {"status": "success"}, "balance": {"status": "error", "http_status": 403},
                  "cashflow": {"status": "not_attempted"}}
    monkeypatch.setattr(transport, "fetch_statement_tables", lambda *_: {
        "tables": tables, "components": components, "error": {"reason": "http_refused", "status_code": 403}})
    result = extract_financial_histories(MissingPrimary(), "5314.TWO", [], data_loader_cls=object)
    assert result["years"] == ["2025"]
    assert result["revenue_history"] == [2.0]
    assert result["fcf_history"] == [None]
    assert result["total_assets_history"] == [None]
    assert result["primary_financial_audit"]["status"] != "success"
    assert result["finmind_financial_fallback_audit"]["status"] == "error"
    assert result["finmind_financial_fallback_audit"]["component_statuses"] == components


def test_provider_async_keeps_event_loop_responsive(monkeypatch):
    import asyncio
    import time
    from data_fetch.market_sources import finmind_financial_transport as transport
    def slow_bounded(*_):
        time.sleep(0.08)
        return {"tables": {}, "components": {}, "error": {"reason": "deadline_exceeded", "status_code": None}}
    monkeypatch.setattr(transport, "fetch_statement_tables", slow_bounded)
    async def run():
        pending = asyncio.create_task(FinMindProvider().fetch_async(FetchRequest.from_ticker("5314.TWO")))
        ticks = 0
        while not pending.done():
            await asyncio.sleep(0.01)
            ticks += 1
        return await pending, ticks
    result, ticks = asyncio.run(run())
    assert result.status == "error"
    assert ticks >= 3


def test_unexpected_financial_parser_failure_does_not_replay_operation(monkeypatch):
    calls = []
    def broken(_ticker):
        calls.append(1)
        raise RuntimeError("arbitrary unsafe exception details")
    monkeypatch.setattr(taiwan, "fetch_finmind_financial_statement_fallback", broken)
    result = FinMindProvider().fetch(FetchRequest.from_ticker("5314.TWO"))
    assert result.status == "error"
    assert len(calls) == 1
    assert "unsafe" not in result.audit["message"]


def test_prepared_request_cannot_silently_switch_authentication():
    class ChangedIdentity(FakeSession):
        def prepare_request(self, request):
            prepared = super().prepare_request(request)
            prepared.headers["Authorization"] = "Basic unrelated-identity"
            return prepared
    session = ChangedIdentity([])
    messages = worker_messages(session)
    assert session.calls == []
    assert messages[0]["reason"] == "credential_identity_mismatch"
    assert "unrelated-identity" not in repr(messages)


def test_oversized_rows_stop_before_next_request(monkeypatch):
    from data_fetch.market_sources import finmind_financial_transport as transport
    monkeypatch.setattr(transport, "ROW_LIMIT", 1)
    session = FakeSession([FakeResponse({"data": synthetic_tables()["financials"]})])
    messages = worker_messages(session)
    assert len(session.calls) == 1
    assert messages[0]["reason"] == "invalid_or_oversized_rows"


@pytest.mark.parametrize("behavior", ["wrong_table", "duplicate", "missing_done", "nonzero"])
def test_malformed_completed_child_is_failure_with_prior_table_retained(behavior):
    import json
    import time
    from data_fetch.market_sources import finmind_financial_transport as transport
    first = {"kind": "table", "name": "financials", "rows": synthetic_tables()["financials"],
             "metadata": {"status": "success"}}
    messages = [first]
    if behavior == "wrong_table":
        messages = [{**first, "name": "cashflow"}]
    elif behavior == "duplicate":
        messages.append(first)
    elif behavior == "nonzero":
        messages.extend({"kind": "table", "name": name, "rows": rows,
                         "metadata": {"status": "success"}}
                        for name, rows in synthetic_tables().items() if name != "financials")
        messages.append({"kind": "done"})
    script = "import sys\nsys.stdin.buffer.read()\n" + "\n".join(
        f"print({json.dumps(message)!r},flush=True)" for message in messages)
    script += "\nsys.exit(2)\n" if behavior == "nonzero" else "\n"
    outcome = transport._run_worker(
        {"stock_id": "5314", "start_date": "2020-01-01", "deadline": time.monotonic() + 2},
        command=[sys.executable, "-c", script])
    assert outcome["error"] is not None
    if behavior == "wrong_table":
        assert outcome["tables"] == {}
    else:
        assert outcome["tables"]["financials"] == synthetic_tables()["financials"]


def test_oversized_parent_input_is_rejected_without_spawn(monkeypatch):
    import time
    from data_fetch.market_sources import finmind_financial_transport as transport
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("oversized input must not spawn"))
    outcome = transport._run_worker({"stock_id": "x" * 5000, "start_date": "2020-01-01",
                                     "deadline": time.monotonic() + 20})
    assert outcome["error"]["reason"] == "invalid_input"
