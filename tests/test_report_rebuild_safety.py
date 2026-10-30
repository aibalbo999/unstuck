import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def saved_input(*days):
    return {"ticker": "2356.TW", "pipeline": "v4", "data": {
        "ticker": "2356.TW", "daily_market_data": {
            "as_of": days[-1], "requested_as_of": "2026-10-27",
            "source": "yfinance 5y history", "volume_unit": "shares",
            "price_adjustment_basis": "provider adjusted",
            "bars": [{"date": day, "open": 60.5, "high": 61, "low": 60,
                      "close": 60.5, "volume": 0} for day in days],
        }}}


def test_full_rerun_refuses_saved_closed_session_without_refresh():
    from report_rerun_data import prepare_full_rerun_data
    snapshot = saved_input("2026-10-22", "2026-10-23", "2026-10-27")
    original = deepcopy(snapshot)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(prepare_full_rerun_data(snapshot, pipeline_id="v4"))
    assert caught.value.status_code == 409
    assert snapshot == original


def test_newly_fetched_closed_session_cannot_enter_rerun():
    from report_rerun_data import prepare_full_rerun_data
    snapshot = saved_input("2026-10-22")
    class Refresh:
        async def fetch_async(self, request):
            assert request.options.force_refresh
            return SimpleNamespace(data=saved_input("2026-10-23")["data"])
    with pytest.raises(HTTPException) as caught:
        asyncio.run(prepare_full_rerun_data(snapshot, pipeline_id="v4", refresh_service=Refresh()))
    assert caught.value.status_code == 409


def test_open_session_zero_volume_is_not_rejected_as_closed():
    from report_rerun_data import prepare_full_rerun_data
    snapshot = saved_input("2026-10-22", "2026-10-27")
    result = asyncio.run(prepare_full_rerun_data(snapshot, pipeline_id="v4"))
    assert len(result["daily_market_data"]["bars"]) == 2
    assert result["daily_market_data"]["bars"][0]["volume"] == 0


def preview(snapshot):
    from report_rebuild_preview import build_rebuild_preview
    return build_rebuild_preview(snapshot, filename="2356_TW_v4_report_job_example.html",
        artifact_hashes={kind: "a" * 64 for kind in ("html", "md", "data")},
        evaluated_at=datetime.fromisoformat("2026-10-27T22:00:00+08:00"))


def test_preview_only_removes_proven_closed_dates_and_keeps_original():
    snapshot = saved_input("2026-10-22", "2026-10-23", "2026-10-27")
    original = deepcopy(snapshot)
    plan = preview(snapshot)
    assert plan["comparison"]["removed_closed_dates"] == ["2026-10-23"]
    assert plan["comparison"]["preserved_open_zero_volume_dates"] == ["2026-10-22", "2026-10-27"]
    assert not plan["execution_enabled"] and not plan["publication_approved"]
    assert plan["required_scope"] == "full_report"
    assert plan["requires_new_report_version"] and plan["preserve_fixed76"]
    assert snapshot == original


@pytest.mark.parametrize("change", ["source", "plan", "expired", "future"])
def test_preview_preflight_rejects_stale_tampered_or_changed_evidence(change):
    from report_rebuild_preview import validate_rebuild_preview
    snapshot = saved_input("2026-10-22", "2026-10-23", "2026-10-27")
    plan = preview(snapshot)
    now = datetime.fromisoformat("2026-10-27T22:01:00+08:00")
    hashes = dict(plan["artifact_sha256"])
    if change == "source":
        hashes["data"] = "b" * 64
    elif change == "plan":
        plan["required_scope"] = "final_recommendation"
    elif change == "expired":
        now += timedelta(hours=3)
    else:
        now -= timedelta(hours=1)
    with pytest.raises(ValueError):
        validate_rebuild_preview(plan, snapshot, artifact_hashes=hashes, now=now)


def test_preflight_success_still_does_not_authorize_execution():
    from report_rebuild_preview import validate_rebuild_preview
    snapshot = saved_input("2026-10-22", "2026-10-27")
    plan = preview(snapshot)
    result = validate_rebuild_preview(plan, snapshot, artifact_hashes=plan["artifact_sha256"],
        now=datetime.fromisoformat("2026-10-27T22:01:00+08:00"))
    assert result == {"preflight_passed": True, "execution_authorized": False, "execution_enabled": False}


def test_preview_rejects_mismatched_report_identity():
    snapshot = saved_input("2026-10-27")
    snapshot["ticker"] = "1101.TW"
    with pytest.raises(ValueError, match="identities"):
        preview(snapshot)


def test_readonly_bundle_reader_rejects_traversal_and_symlinks(tmp_path):
    from report_rebuild_preview import ReadOnlyArtifactStorage
    storage = ReadOnlyArtifactStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.get_report("../other.json")
    (tmp_path / "target.json").write_text("{}")
    (tmp_path / "alias.json").symlink_to(tmp_path / "target.json")
    with pytest.raises(ValueError):
        storage.get_report("alias.json")


def test_missing_tw_v4_input_is_not_admitted():
    from report_rebuild_preview import assert_session_inputs
    with pytest.raises(HTTPException):
        assert_session_inputs({"ticker": "2356.TW"}, pipeline_id="v4")


@pytest.mark.parametrize("ticker", [None, "1101.TW", "TEST"])
def test_full_and_final_reject_missing_or_mismatched_input_identity(ticker, tmp_path):
    from report_rerun_data import prepare_full_rerun_data
    from report_rerun_service import _build_final_rerun_context
    snapshot = saved_input("2026-10-22", "2026-10-23", "2026-10-27")
    snapshot["data"]["ticker"] = ticker
    with pytest.raises(HTTPException):
        asyncio.run(prepare_full_rerun_data(snapshot, pipeline_id="v4"))
    with pytest.raises(HTTPException):
        _build_final_rerun_context("2356_TW_v4_report_job_example.html", snapshot, str(tmp_path))


def test_resumed_full_run_checks_bound_identity_before_model(monkeypatch):
    import report_rerun_service as service
    snapshot = saved_input("2026-10-23")
    resumed = deepcopy(snapshot["data"])
    resumed.pop("ticker")
    async def checkpoint(**kwargs):
        return {}, resumed
    monkeypatch.setattr(service, "full_rerun_checkpoint", checkpoint)
    with pytest.raises(HTTPException):
        asyncio.run(service._run_full_pipeline_rerun(snapshot=snapshot, output_dir="unused",
            pipeline_runner=None, report_renderer=None, source_filename="2356_TW_v4_report_job_example.html",
            pipeline_id="v4", scope="full_report"))


def test_rerun_names_are_unique_even_in_one_second():
    import report_rerun_rendering as rendering
    first = rendering.rerun_report_filename("2356.TW", "v4")
    second = rendering.rerun_report_filename("2356.TW", "v4")
    assert first[0] != second[0]


@pytest.mark.parametrize("collision", ["source", "existing"])
def test_rebuild_refuses_colliding_version_before_render(monkeypatch, collision):
    import report_rerun_rendering as rendering
    from storage.report_storage import InMemoryStorage
    from report_paths import report_storage_key_for_filename
    filename = "2356_TW_v4_report_job_existing.html"
    monkeypatch.setattr(rendering, "rerun_report_filename", lambda *_: (filename, "unused.md", "unused.json"))
    monkeypatch.setattr(rendering, "assert_report_publishable", lambda *_: None)
    storage = InMemoryStorage()
    if collision == "existing":
        storage.save_report(report_storage_key_for_filename(filename), b"original", content_type="text/html")
    with pytest.raises(HTTPException) as caught:
        asyncio.run(rendering.render_and_save_rerun_report(context={"ticker": "2356.TW"},
            pipeline_id="v4", output_dir="unused", report_renderer=None, scope="full_report",
            source_filename=filename if collision == "source" else "2356_TW_v4_report_job_source.html", storage=storage))
    assert caught.value.status_code == 409
    if collision == "existing":
        assert storage.get_report(report_storage_key_for_filename(filename)).content == b"original"


@pytest.mark.parametrize("bad", [None, {"date": []}, {"date": {}}, "invalid"])
def test_preview_malformed_bars_cannot_become_eligible_or_compute_metrics(bad):
    snapshot = saved_input("2026-10-22", "2026-10-23", "2026-10-27")
    snapshot["data"]["daily_market_data"]["bars"].append(bad)
    plan = preview(snapshot)
    assert not plan["session_admission"]["eligible"]
    assert not plan["comparison"]["after_session_admission"]["eligible"]
    assert plan["comparison"]["metrics"] == {}


def test_all_closed_preview_has_no_last_observation_or_metrics():
    plan = preview(saved_input("2026-10-23"))
    assert plan["comparison"]["after_as_of"] is None
    assert not plan["comparison"]["after_session_admission"]["eligible"]
    assert plan["comparison"]["metrics"] == {}


def test_unbound_input_refuses_before_provider_call():
    from report_rerun_data import prepare_full_rerun_data
    snapshot = saved_input("2026-10-23")
    snapshot["data"].pop("ticker")
    class Refresh:
        async def fetch_async(self, request):
            pytest.fail("Unbound input must not request a provider")
    with pytest.raises(HTTPException):
        asyncio.run(prepare_full_rerun_data(snapshot, pipeline_id="v4", refresh_service=Refresh()))
