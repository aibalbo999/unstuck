"""Fail-closed, structured evidence for the isolated PostgreSQL suite.

This module deliberately has no database or Docker dependencies.  It is used
as a pytest plugin inside the disposable image and by offline contract tests
on the host.  The only information it records is the information needed to
prove case coverage and lifecycle outcomes; pytest's traceback and captured
output streams never cross this boundary.
"""

from __future__ import annotations

import json
from importlib.metadata import version as distribution_version
import os
from pathlib import Path
import platform
import re
import signal
import sys
from typing import Any

import pytest


RESULT_SCHEMA = "stock-agent.pg-validation.result.v1"
RESULT_PATH = Path("/results/result.json")
BASE_IMAGE = (
    "sha256:413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650"
)
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:-]{0,127}$")
MAX_RESULT_SIZE = 1024 * 1024
CASE_FILE = "tests/test_workflow_postgres_live.py"
CASE_PREFIX = CASE_FILE + "::"
CASE_NAMES = (
    "test_pg00_native_external_endpoint_is_unreachable",
    "test_pg01_empty_setup_and_reopen_are_idempotent",
    "test_pg02_original_and_intermediate_drafts_roundtrip",
    "test_pg02_intermediate_repair_survives_repeated_deferral[structured]",
    "test_pg02_intermediate_repair_survives_repeated_deferral[identity]",
    "test_pg03_deferred_draft_resumes_gate_once[disabled]",
    "test_pg03_deferred_draft_resumes_gate_once[expired]",
    "test_pg03_deferred_draft_resumes_gate_once[disabled-expired]",
    "test_pg03_restored_draft_does_not_refresh_evidence",
    "test_pg04_cancel_after_draft_resumes_without_partial_adoption",
    "test_pg05_threads_agents_and_completed_sibling_are_isolated",
    "test_pg06_draft_restoration_tracks_upstream_fingerprint",
    "test_pg06_dependency_repair_resumes_atomic_invalidated_round",
    "test_pg07_original_draft_permission_denied_fails_closed",
    "test_pg07_intermediate_draft_permission_denied_preserves_original[structured]",
    "test_pg07_intermediate_draft_permission_denied_preserves_original[identity]",
    "test_pg08_completed_graph_reopen_does_not_repeat_work_or_publish",
)
# This is intentionally a literal registry.  Never derive it from collected
# items: a selector, skip, or collection bug must be visible as incomplete.
EXPECTED_CASES = frozenset(CASE_PREFIX + name for name in CASE_NAMES)


def valid_runtime_versions(versions: Any) -> bool:
    """Accept only the runtime identity required by the live contract."""

    if not isinstance(versions, dict) or set(versions) != {
        "python", "postgres", "psycopg", "libpq", "saver", "psycopg_impl",
    }:
        return False
    return all(
        isinstance(value, str)
        and bool(value)
        and len(value) <= 128
        and _VERSION_RE.fullmatch(value) is not None
        for value in versions.values()
    ) and versions["psycopg_impl"] == "binary"


def accepted_result(
    expected: Any,
    collected: Any,
    reports: Any,
    *,
    exit_code: Any,
    collection_errors: Any = (),
) -> bool:
    """Return true only for an exact, all-phase, all-pass pytest run.

    ``reports`` is deliberately a small list of dictionaries produced by the
    plugin.  Missing or duplicate phase reports, collection errors, xfail,
    skip, and a non-zero exit status all fail closed.
    """

    if type(exit_code) is not int or exit_code != 0:
        return False
    if not isinstance(expected, (set, frozenset, tuple, list)):
        return False
    try:
        expected_set = set(expected)
    except TypeError:
        return False
    if not expected_set:
        return False
    if not isinstance(collected, (set, frozenset, tuple, list)):
        return False
    collected_list = list(collected)
    try:
        collected_set = set(collected_list)
    except TypeError:
        return False
    if len(collected_list) != len(collected_set):
        return False
    if collected_set != expected_set:
        return False
    if not isinstance(reports, (tuple, list)):
        return False
    if collection_errors:
        return False

    phases: dict[str, dict[str, str]] = {node: {} for node in expected_set}
    for report in reports:
        if not isinstance(report, dict):
            return False
        node = report.get("nodeid")
        phase = report.get("when")
        outcome = report.get("outcome")
        if node not in phases or phase in phases[node]:
            return False
        if phase not in {"setup", "call", "teardown"}:
            return False
        if report.get("wasxfail") is not None:
            return False
        if outcome != "passed":
            return False
        phases[node][phase] = outcome
    return all(
        value == {"setup": "passed", "call": "passed", "teardown": "passed"}
        for value in phases.values()
    )


def _safe_exception(report: Any) -> dict[str, str] | None:
    """Extract only a class name and SQLSTATE from a pytest report."""

    longrepr = getattr(report, "longrepr", None)
    excinfo = getattr(report, "excinfo", None)
    exc = getattr(excinfo, "value", None)
    result: dict[str, str] = {}
    if exc is not None:
        result["class"] = type(exc).__name__
        sqlstate = getattr(exc, "sqlstate", None)
        if isinstance(sqlstate, str) and len(sqlstate) <= 16 and sqlstate.isalnum():
            result["sqlstate"] = sqlstate
    elif longrepr is not None:
        result["class"] = type(longrepr).__name__
    return result or None


def _runtime_versions() -> dict[str, str] | None:
    """Read actual runtime versions without exporting connection details."""

    try:
        import psycopg
        from .guard import load_policy

        policy_path = os.environ["STOCK_AGENT_PG_VALIDATION_POLICY"]
        owner, _app = load_policy(policy_path)
        with psycopg.connect(owner.conninfo(), autocommit=True) as conn:
            row = conn.execute("SELECT current_setting('server_version')").fetchone()
        postgres = row[0] if row else None
        versions = {
            "python": platform.python_version(),
            "postgres": postgres,
            "psycopg": psycopg.__version__,
            "libpq": str(psycopg.pq.version()),
            "saver": distribution_version("langgraph-checkpoint-postgres"),
            "psycopg_impl": str(getattr(psycopg.pq, "__impl__", "")),
        }
        if not valid_runtime_versions(versions):
            return None
        return versions
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, AttributeError):
        return None
    except Exception:
        # Do not leak driver error text into the structured result.
        return None


def _runtime_config(config: Any) -> tuple[dict[str, Any], bool]:
    run_id = os.environ.get("STOCK_AGENT_PG_VALIDATION_RUN_ID", "")
    manifest = os.environ.get("STOCK_AGENT_PG_VALIDATION_MANIFEST_SHA256", "")
    image = os.environ.get("STOCK_AGENT_PG_VALIDATION_IMAGE_ID", "")
    versions = _runtime_versions()
    return {
        "schema": RESULT_SCHEMA,
        "run_id": run_id,
        "manifest_sha256": manifest,
        "base_image": BASE_IMAGE,
        "derived_image": image,
        "network": "none",
        "socket": "unix-local-only",
        "paths": "tmpfs-and-container-layer-only",
        "versions": versions or {},
    }, versions is not None


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_RESULT_SIZE:
        raise ValueError("isolated_pg_result_too_large")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short result write")
            view = view[written:]
    finally:
        os.close(fd)


class ResultPlugin:
    """Pytest plugin that emits only structured, allowlisted evidence."""

    def __init__(self, *, result_path: Path = RESULT_PATH) -> None:
        self.result_path = result_path
        self.collected: list[str] = []
        self.reports: list[dict[str, Any]] = []
        self.collection_errors: list[dict[str, str]] = []
        self.timeout_seconds = 60
        self._old_handler: Any = None

    def pytest_collection_modifyitems(self, session: Any, config: Any, items: list[Any]) -> None:
        self.collected = [item.nodeid for item in items]

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.collection_errors.append({"phase": "collection", "outcome": "failed"})

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when not in {"setup", "call", "teardown"}:
            return
        entry: dict[str, Any] = {
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
        }
        if hasattr(report, "wasxfail"):
            entry["wasxfail"] = getattr(report, "wasxfail")
        error = _safe_exception(report)
        if error is not None:
            entry["exception"] = error
        self.reports.append(entry)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_protocol(self, item: Any, nextitem: Any):
        if sys.platform != "linux" or not hasattr(signal, "SIGALRM"):
            yield
            return
        old_handler = signal.getsignal(signal.SIGALRM)

        def timeout(_signum: int, _frame: Any) -> None:
            raise TimeoutError("isolated_pg_case_timeout")

        signal.signal(signal.SIGALRM, timeout)
        signal.setitimer(signal.ITIMER_REAL, self.timeout_seconds)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        accepted = accepted_result(
            EXPECTED_CASES,
            self.collected,
            self.reports,
            exit_code=exitstatus,
            collection_errors=self.collection_errors,
        )
        phases = [
            {
                "nodeid": report["nodeid"],
                "when": report["when"],
                "outcome": report["outcome"],
            }
            for report in self.reports
        ]
        runtime_config, versions_ok = _runtime_config(session.config)
        payload = {
            **runtime_config,
            "status": "tests_passed" if accepted and versions_ok else "tests_failed",
            "collected": sorted(self.collected),
            "expected": sorted(EXPECTED_CASES),
            "phases": phases,
            "counts": {
                "expected": len(EXPECTED_CASES),
                "collected": len(self.collected),
                "reports": len(self.reports),
                "collection_errors": len(self.collection_errors),
            },
            "assertions": {
                "native_external_endpoint": "TEST-NET-only",
                "host_network": "rejected",
                "sqlite_checkpoint": "absent",
            },
            "exit_code": int(exitstatus),
            "server_stop_status": "pending",
        }
        try:
            self.result_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _write_result(self.result_path, payload)
        except (OSError, TypeError, ValueError):
            # A missing or malformed result is intentionally a failed live run.
            session.exitstatus = 1


def pytest_configure(config: Any) -> None:
    plugin = ResultPlugin()
    config.pluginmanager.register(plugin, "stock_agent_pg_result")


__all__ = [
    "BASE_IMAGE",
    "CASE_FILE",
    "CASE_NAMES",
    "EXPECTED_CASES",
    "MAX_RESULT_SIZE",
    "RESULT_SCHEMA",
    "ResultPlugin",
    "accepted_result",
    "valid_runtime_versions",
]
