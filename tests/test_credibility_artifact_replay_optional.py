"""Explicit opt-in artifact-only replay; never executes a job or opens a database."""

import hashlib
import json
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(not os.getenv("CREDIBILITY_REPLAY_OUTPUT_DIR"), reason="requires explicit read-only artifact replay directory")
def test_saved_1623_and_2308_credibility_boundaries():
    from evidence_exit_gate import evaluate_report_evidence
    from quant_engine import QuantEngine
    from report_artifacts import ReportArtifactLocator
    from report_history_storage import storage_for_existing_output_dir

    root = Path(os.environ["CREDIBILITY_REPLAY_OUTPUT_DIR"]).resolve()
    storage = storage_for_existing_output_dir(str(root), None)
    assert storage is not None
    locator = ReportArtifactLocator(storage)
    cases = {
        "1623_a": "1623_TW_v1_report_job_2015d85fba52.html",
        "1623_d": "1623_TW_v4_report_job_3298c5baf555.html",
        "2308_c": "2308_TW_v3_report_job_d1a3bc998e2d.html",
    }
    bundles = {name: locator.require_bundle(filename) for name, filename in cases.items()}
    keys = {name: (bundle.html_key, bundle.markdown_key, bundle.data_key) for name, bundle in bundles.items()}
    before = {key: hashlib.sha256(storage.get_report(key).content).hexdigest() for values in keys.values() for key in values if key}
    snapshots = {name: bundle.read_data_snapshot() for name, bundle in bundles.items()}
    raw = snapshots["1623_a"]["data"]
    assert raw["free_cash_flow_raw"] < 0
    quant = QuantEngine.compute_all(raw)
    assert quant["dcf_intrinsic_value"] is None and quant["margin_of_safety"] is None
    results = {}
    for name in ("1623_d", "2308_c"):
        markdown = storage.get_report(bundles[name].markdown_key).content.decode("utf-8")
        result = evaluate_report_evidence(markdown, snapshots[name], sample_ratio=1, max_sample=10000)
        results[name] = result
    sma_claims = [item for item in results["1623_d"]["sampled_claims"]
                  if item["reported_value"] == 205.4 and "20日均線" in item["raw_text"]]
    assert sma_claims and all(item["matched_path"] == "data.technical_indicators.sma_20" for item in sma_claims)
    horizon = [item for item in results["2308_c"]["sampled_claims"]
               if item["reported_value"] == 1380 and "最終投資建議" in item["raw_text"]]
    assert horizon and all(item["matched_path"] == "rerun_context.parsed.recommendation.中期目標（6個月）" for item in horizon)
    assert any(item["verification_reason_code"] == "confidence_metadata_not_evidence" for item in results["2308_c"]["sampled_claims"])
    assert before == {key: hashlib.sha256(storage.get_report(key).content).hexdigest() for values in keys.values() for key in values if key}
    print(json.dumps({"artifact_hashes_unchanged": len(before), "negative_fcf_dcf": "unavailable",
                      "sma_matches": len(sma_claims), "compact_6m_matches": len(horizon),
                      "gate_counts": {name: {key: result[key] for key in
                          ("sampled_count", "verified_count", "failed_count", "unverifiable_count")} for name, result in results.items()}}, ensure_ascii=False))
