"""A single killable process bounds only the FinMind financial fallback.

No SDK, login, retry, credentials discovery or database access runs in the worker.
Completed tables cross the pipe immediately, before requesting the next table.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time

ENDPOINT = "https://api.finmindtrade.com/api/v4/data"
DATASETS = {"financials": "TaiwanStockFinancialStatements",
            "balance": "TaiwanStockBalanceSheet", "cashflow": "TaiwanStockCashFlowsStatement"}
DEADLINE_SECONDS = 20.0
INPUT_LIMIT = 4096
BODY_LIMIT = 2 * 1024 * 1024
ROW_LIMIT = 20_000
LINE_LIMIT = 3 * 1024 * 1024
STDOUT_LIMIT = 10 * 1024 * 1024
STDERR_LIMIT = 8192


class FinMindFinancialFetchError(RuntimeError):
    """A failed operation may still own previously completed, usable tables."""
    retryable = False

    def __init__(self, reason: str, *, status_code: int | None = None,
                 partial_value: dict | None = None, component_statuses: dict | None = None):
        super().__init__(f"FinMind financial statements: {reason}")
        self.status_code = status_code
        self.partial_value = partial_value or {}
        self.component_statuses = component_statuses or {}


class _WorkerFailure(Exception):
    def __init__(self, reason, status=None):
        self.reason, self.status = reason, status


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _WorkerFailure("deadline_exceeded")
    return remaining


def _validate_input(payload):
    if not isinstance(payload, dict) or set(payload) != {"stock_id", "start_date", "deadline"}:
        raise _WorkerFailure("invalid_input")
    if not isinstance(payload["stock_id"], str) or not re.fullmatch(r"[0-9A-Z]{4,8}", payload["stock_id"]):
        raise _WorkerFailure("invalid_stock_id")
    try:
        date.fromisoformat(payload["start_date"])
        deadline = float(payload["deadline"])
    except (TypeError, ValueError):
        raise _WorkerFailure("invalid_input") from None
    if not 0 < deadline - time.monotonic() <= DEADLINE_SECONDS:
        raise _WorkerFailure("deadline_exceeded")
    return deadline


def _validate_rows(rows, stock_id, deadline):
    if not isinstance(rows, list) or len(rows) > ROW_LIMIT:
        raise _WorkerFailure("invalid_or_oversized_rows")
    for index, row in enumerate(rows):
        if index % 256 == 0:
            _remaining(deadline)
        if not isinstance(row, dict) or not {"date", "stock_id", "type", "value"}.issubset(row):
            raise _WorkerFailure("invalid_row_schema")
        if str(row["stock_id"]) != stock_id or not isinstance(row["type"], str) or not row["type"].strip():
            raise _WorkerFailure("invalid_row_identity")
        try:
            date.fromisoformat(row["date"])
        except (TypeError, ValueError):
            raise _WorkerFailure("invalid_statement_date") from None


def _reject_json_constant(_value):
    raise ValueError("Non-finite JSON constant")


def _worker_fetch(payload, emit, *, session_factory=None):
    """One session, three serial GETs at most; injectable I/O for offline tests."""
    import requests

    deadline = _validate_input(payload)
    current = "financials"
    metadata = {}
    try:
        with (session_factory or requests.Session)() as session:
            # Explicitly retain this path's empty-token identity. Do not load an
            # unrelated FINMIND_TOKEN or silently accept netrc authentication.
            session.headers.update({"Authorization": "Bearer "})
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
            for current, dataset in DATASETS.items():
                metadata = {}
                remaining = _remaining(deadline)
                request = requests.Request("GET", ENDPOINT, params={
                    "dataset": dataset, "data_id": payload["stock_id"], "start_date": payload["start_date"],
                })
                prepared = session.prepare_request(request)
                if prepared.headers.get("Authorization") != "Bearer ":
                    raise _WorkerFailure("credential_identity_mismatch")
                settings = session.merge_environment_settings(prepared.url, {}, True, None, None)
                with session.send(prepared, timeout=(min(3.0, remaining), min(5.0, remaining)),
                                  allow_redirects=False, **settings) as response:
                    metadata["http_status"] = response.status_code
                    if response.status_code != 200:
                        raise _WorkerFailure("http_refused", response.status_code)
                    body = bytearray()
                    for chunk in response.iter_content(chunk_size=16384):
                        _remaining(deadline)
                        if len(body) + len(chunk) > BODY_LIMIT:
                            raise _WorkerFailure("response_too_large")
                        body.extend(chunk)
                    metadata.update(response_bytes=len(body), response_sha256=hashlib.sha256(body).hexdigest())
                    _remaining(deadline)
                    decoded = json.loads(body, parse_constant=_reject_json_constant)
                    if not isinstance(decoded, dict):
                        raise _WorkerFailure("invalid_json_schema")
                    status = decoded.get("status", 200)
                    if isinstance(status, bool) or str(status) != "200":
                        code = int(status) if str(status).isdigit() else None
                        raise _WorkerFailure("json_refused", code)
                    rows = decoded.get("data")
                    _validate_rows(rows, payload["stock_id"], deadline)
                    _remaining(deadline)
                    emit({"kind": "table", "name": current, "rows": rows,
                          "metadata": {**metadata, "status": "success" if rows else "empty",
                                       "as_of": ",".join(sorted({row["date"] for row in rows}))[:160]}})
    except _WorkerFailure as exc:
        emit({"kind": "error", "name": current, "reason": exc.reason,
              "status_code": exc.status, "metadata": metadata})
    except (ValueError, TypeError, requests.RequestException) as exc:
        # Exception text may contain URLs, credentials or provider response text.
        reason = "request_timeout" if isinstance(exc, requests.Timeout) else "invalid_response" if isinstance(exc, (ValueError, TypeError)) else "transport_error"
        emit({"kind": "error", "name": current, "reason": reason, "status_code": None,
              "metadata": metadata})
    emit({"kind": "done"})


def _worker_main():
    # The test runner's socket monkeypatch cannot cross exec. This explicit
    # inherited flag must fail closed before even importing the HTTP client.
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK") == "1":
        sys.stdout.buffer.write(b'{"kind":"fatal","reason":"test_network_disabled"}\n')
        sys.stdout.buffer.flush()
        return 2

    def emit(message):
        encoded = json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        if len(encoded) > LINE_LIMIT:
            raise _WorkerFailure("protocol_message_too_large")
        sys.stdout.buffer.write(encoded + b"\n")
        sys.stdout.buffer.flush()

    try:
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            raise _WorkerFailure("invalid_input")
        _worker_fetch(json.loads(raw), emit)
    except Exception:
        # Fixed, bounded diagnostics, including failures before the first GET.
        sys.stdout.buffer.write(b'{"kind":"fatal","reason":"worker_input_or_runtime_error"}\n')
        sys.stdout.buffer.flush()
        return 1
    return 0


def _worker_environment():
    # Retain the original requests proxy/CA environment without exposing model
    # credentials to this fixed-purpose child. No proxy rotation is introduced.
    names = {"STOCK_AGENT_TEST_NO_NETWORK", "PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "NETRC",
             "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
             "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    return {key: value for key, value in os.environ.items() if key in names}


def _run_worker(payload, *, command=None):
    """Deadline terminates this exact child, including blocked DNS/native reads."""
    deadline = payload["deadline"]
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    outcome = {"tables": {}, "components": {name: {"status": "not_attempted"} for name in DATASETS}, "error": None}
    proc = None
    selector = selectors.DefaultSelector()
    buffer = bytearray()
    stdout_bytes = stderr_bytes = 0
    done = False
    seen_error = False

    def fail(reason, status=None):
        if outcome["error"] is not None:
            # Preserve the first refusal (especially 429 for the outer cooldown)
            # when later protocol/termination cleanup also fails.
            diagnostic = outcome["components"].setdefault(
                "transport", {"status": "error", "reason_code": reason})
            if diagnostic["reason_code"] != reason:
                diagnostic.setdefault("additional_reason_codes", []).append(reason)
            return
        outcome["error"] = {"reason": reason, "status_code": status}
        remaining_names = [name for name in DATASETS if name not in outcome["tables"]]
        if remaining_names:
            name = remaining_names[0]
            outcome["components"][name] = {**outcome["components"][name], "status": "error", "reason_code": reason}

    def consume(line):
        nonlocal done, seen_error
        if len(line) > LINE_LIMIT or done:
            raise _WorkerFailure("invalid_worker_protocol")
        msg = json.loads(line, parse_constant=_reject_json_constant)
        if not isinstance(msg, dict):
            raise _WorkerFailure("invalid_worker_protocol")
        kind = msg.get("kind")
        next_names = [name for name in DATASETS if name not in outcome["tables"]]
        if kind == "done":
            if not seen_error and next_names:
                raise _WorkerFailure("incomplete_worker_result")
            done = True
            return
        if kind == "fatal":
            reason = "test_network_disabled" if msg.get("reason") == "test_network_disabled" else "worker_failed"
            raise _WorkerFailure(reason)
        name = msg.get("name")
        if seen_error or not next_names or name != next_names[0]:
            raise _WorkerFailure("invalid_worker_protocol")
        metadata = msg.get("metadata")
        if not isinstance(metadata, dict):
            raise _WorkerFailure("invalid_worker_protocol")
        metadata = {key: value for key, value in metadata.items()
                    if key in {"http_status", "response_bytes", "response_sha256", "status", "as_of"}
                    and isinstance(value, (str, int)) and not isinstance(value, bool)}
        if kind == "table":
            rows = msg.get("rows")
            _validate_rows(rows, payload["stock_id"], deadline)
            outcome["tables"][name] = rows
            outcome["components"][name] = metadata
        elif kind == "error":
            seen_error = True
            status = msg.get("status_code")
            status = status if isinstance(status, int) and not isinstance(status, bool) else None
            # The child owns a fixed vocabulary; never expose arbitrary output.
            reason = msg.get("reason")
            allowed = {"deadline_exceeded", "credential_identity_mismatch", "http_refused", "response_too_large",
                       "invalid_json_schema", "json_refused", "invalid_or_oversized_rows", "invalid_row_schema",
                       "invalid_row_identity", "invalid_statement_date", "request_timeout", "invalid_response", "transport_error"}
            reason = reason if reason in allowed else "worker_failed"
            outcome["components"][name] = metadata
            fail(reason, status)
        else:
            raise _WorkerFailure("invalid_worker_protocol")

    try:
        if len(encoded) > INPUT_LIMIT:
            raise _WorkerFailure("invalid_input")
        _remaining(deadline)
        proc = subprocess.Popen(command or [sys.executable, str(Path(__file__).resolve()), "--worker"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                shell=False, close_fds=True, env=_worker_environment())
        _remaining(deadline)
        proc.stdin.write(encoded)
        proc.stdin.close()
        for pipe in (proc.stdout, proc.stderr):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ)
        while selector.get_map() or proc.poll() is None:
            remaining = _remaining(deadline)
            for key, _ in selector.select(min(remaining, 0.05)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if key.fileobj is proc.stderr:
                    stderr_bytes += len(chunk)
                    if stderr_bytes > STDERR_LIMIT:
                        raise _WorkerFailure("worker_stderr_limit")
                else:
                    stdout_bytes += len(chunk)
                    if stdout_bytes > STDOUT_LIMIT:
                        raise _WorkerFailure("worker_stdout_limit")
                    buffer.extend(chunk)
                    while b"\n" in buffer:
                        line, _, rest = buffer.partition(b"\n")
                        buffer[:] = rest
                        consume(line)
                    if len(buffer) > LINE_LIMIT:
                        raise _WorkerFailure("worker_line_limit")
            if not selector.get_map() and proc.poll() is None:
                time.sleep(min(0.01, remaining))
        if proc.returncode or not done or buffer:
            raise _WorkerFailure("incomplete_worker_result")
        _remaining(deadline)
    except _WorkerFailure as exc:
        fail(exc.reason, exc.status)
    except Exception:
        # Runtime/pipe/protocol exceptions must not escape as retryable failures.
        fail("worker_start_or_protocol_error")
    finally:
        try:
            selector.close()
        except Exception:
            fail("worker_cleanup_failed")
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()  # reap before returning; never leave a timed-out fetch running
            except Exception:
                fail("worker_cleanup_failed")
            finally:
                for pipe in (proc.stdin, proc.stdout, proc.stderr):
                    try:
                        if pipe and not pipe.closed:
                            pipe.close()
                    except Exception:
                        fail("worker_cleanup_failed")
    return outcome


def fetch_statement_tables(stock_id: str, start_date: str) -> dict:
    payload = {"stock_id": stock_id, "start_date": start_date, "deadline": time.monotonic() + DEADLINE_SECONDS}
    return _run_worker(payload)


if __name__ == "__main__":
    raise SystemExit(_worker_main() if sys.argv[1:] == ["--worker"] else 2)
