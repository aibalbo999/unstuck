"""Offline contract checks for complete PostgreSQL live evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from pg_validation.result import EXPECTED_CASES, accepted_result


def _reports(*, outcome="passed", wasxfail=None):
    reports = []
    for node in sorted(EXPECTED_CASES):
        for phase in ("setup", "call", "teardown"):
            report = {"nodeid": node, "when": phase, "outcome": outcome}
            if wasxfail is not None:
                report["wasxfail"] = wasxfail
            reports.append(report)
    return reports


def test_accepted_result_requires_the_literal_complete_registry():
    assert accepted_result(
        EXPECTED_CASES,
        sorted(EXPECTED_CASES),
        _reports(),
        exit_code=0,
    )


def test_accepted_result_rejects_empty_or_self_generated_registry():
    assert not accepted_result(set(), [], [], exit_code=0)
    collected = sorted(EXPECTED_CASES)[:-1]
    assert not accepted_result(EXPECTED_CASES, collected, _reports(), exit_code=0)


def test_accepted_result_rejects_skip_xfail_failure_and_teardown_failure():
    for reports in (
        _reports(outcome="skipped"),
        _reports(wasxfail="reason"),
        _reports(outcome="failed"),
    ):
        assert not accepted_result(
            EXPECTED_CASES,
            sorted(EXPECTED_CASES),
            reports,
            exit_code=0,
        )
    reports = _reports()
    reports[-1]["outcome"] = "failed"
    assert not accepted_result(
        EXPECTED_CASES,
        sorted(EXPECTED_CASES),
        reports,
        exit_code=0,
    )


def test_accepted_result_rejects_duplicate_phase_and_collection_errors():
    reports = _reports()
    reports.append(dict(reports[0]))
    assert not accepted_result(
        EXPECTED_CASES,
        sorted(EXPECTED_CASES),
        reports,
        exit_code=0,
    )
    assert not accepted_result(
        EXPECTED_CASES,
        sorted(EXPECTED_CASES),
        _reports(),
        exit_code=0,
        collection_errors=[{"phase": "collection", "outcome": "failed"}],
    )


def test_accepted_result_rejects_nonzero_exit_and_missing_phase():
    reports = _reports()[:-1]
    assert not accepted_result(
        EXPECTED_CASES,
        sorted(EXPECTED_CASES),
        reports,
        exit_code=0,
    )
    assert not accepted_result(
        EXPECTED_CASES,
        sorted(EXPECTED_CASES),
        _reports(),
        exit_code=1,
    )


def test_result_plugin_writer_rejects_preexisting_symlink(tmp_path: Path):
    from pg_validation.result import _write_result

    target = tmp_path / "target.json"
    target.write_text("keep")
    result = tmp_path / "result.json"
    result.symlink_to(target)
    with pytest.raises(OSError):
        _write_result(result, {"status": "tests_passed"})
    assert target.read_text() == "keep"
