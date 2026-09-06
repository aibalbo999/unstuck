"""The real refresh service preserves old claims without rebinding them to new evidence."""

import asyncio
import copy
import json

import pytest

from test_market_context_assessment import assessment_context, assessment_module


def _refresh(snapshot, data, tmp_path, monkeypatch):
    import report_refresh_service
    from report_persistence import report_bundle_keys_for_filename
    from storage.report_storage import InMemoryStorage

    filename = "TEST_v1_report_20260906_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage = InMemoryStorage()
    storage.save_report(keys.html_key, b"<html>Original analysis</html>", content_type="text/html")
    storage.save_report(keys.data_key, json.dumps(snapshot).encode(), content_type="application/json")
    # Only isolate the unrelated report-index write; execute snapshot refresh/persistence normally.
    monkeypatch.setattr(report_refresh_service, "upsert_report_metadata", lambda *args, **kwargs: {})
    result = asyncio.run(report_refresh_service.refresh_report_data_snapshot(
        filename, output_dir=str(tmp_path), refresh_service=None, storage=storage, refreshed_data=data))
    assert result["success"]
    assert storage.get_report(keys.html_key).content == b"<html>Original analysis</html>"
    return json.loads(storage.get_report(keys.data_key).content)


@pytest.mark.parametrize("changed", ["forged", "news", "price"])
@pytest.mark.parametrize("oversized", [False, True])
def test_refresh_keeps_raw_assertions_and_original_input_provenance(changed, oversized, tmp_path, monkeypatch):
    from data_trust_snapshot import build_data_snapshot
    from market_context_manifest import market_input_fingerprint

    data = assessment_context()["data"]
    data["large_noncore_field"] = "x" * 20_000
    context = assessment_context(data=data)
    if changed == "forged":
        context["structured_outputs"][7]["market_context_assessment"]["international_news_context"]["source_refs"] = ["FORGED"]
    original = build_data_snapshot(context, max_bytes=400 if oversized else 2_000_000)
    raw = copy.deepcopy(original["market_context_raw_assessment"])
    if oversized:
        assert "structured_outputs" not in original["rerun_context"]
        assert original["market_context_snapshot_receipts"]
    refreshed_data = copy.deepcopy(original["data"])
    if changed == "news":
        refreshed_data["international_news_context"]["topics"][0]["headline"] = "New headline"
    else:
        refreshed_data["current_price"] = 101

    refreshed = _refresh(original, refreshed_data, tmp_path, monkeypatch)
    assert assessment_module().assess_final_market_context(refreshed)["status"] == "critical"
    assert refreshed["market_context_raw_assessment"] == raw
    assert refreshed["market_context_original_input_fingerprint"] == original["market_context_original_input_fingerprint"]
    assert refreshed["market_context_original_input_fingerprint"] != market_input_fingerprint(refreshed_data)
    assert refreshed["market_context_manifests"] == original["market_context_manifests"]
    assert not refreshed.get("market_context_snapshot_receipts")


def test_refresh_does_not_upgrade_legacy_market_assessment(tmp_path, monkeypatch):
    from data_trust_snapshot import build_data_snapshot

    original = build_data_snapshot({"pipeline_id": "v1", "ticker": "TEST", "data": {"ticker": "TEST", "current_price": 100}})
    refreshed = _refresh(original, {"ticker": "TEST", "current_price": 101}, tmp_path, monkeypatch)
    assert not refreshed.get("market_context_contract_version")
    assert assessment_module().assess_final_market_context(refreshed)["status"] == "not_recorded"
