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

    root = Path(os.environ["CREDIBILITY_REPLAY_OUTPUT_DIR"]).resolve()
    cases = {
        "1623_a": root / "unknown-month/1623.TW/1623_TW_v1_report_job_2015d85fba52",
        "1623_d": root / "unknown-month/1623.TW/1623_TW_v4_report_job_3298c5baf555",
        "2308_c": root / "unknown-month/2308.TW/2308_TW_v3_report_job_d1a3bc998e2d",
    }
    paths = [Path(str(stem) + suffix) for stem in cases.values() for suffix in (".md", ".data.json", ".html")]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    snapshots = {name: json.loads(Path(str(stem) + ".data.json").read_text()) for name, stem in cases.items()}
    raw = snapshots["1623_a"]["data"]
    assert raw["free_cash_flow_raw"] < 0
    quant = QuantEngine.compute_all(raw)
    assert quant["dcf_intrinsic_value"] is None and quant["margin_of_safety"] is None
    results = {}
    for name in ("1623_d", "2308_c"):
        markdown = Path(str(cases[name]) + ".md").read_text()
        result = evaluate_report_evidence(markdown, snapshots[name], sample_ratio=1, max_sample=10000)
        results[name] = result
    sma_claims = [item for item in results["1623_d"]["sampled_claims"]
                  if item["reported_value"] == 205.4 and "20日均線" in item["raw_text"]]
    assert sma_claims and all(item["matched_path"] == "data.technical_indicators.sma_20" for item in sma_claims)
    horizon = [item for item in results["2308_c"]["sampled_claims"]
               if item["reported_value"] == 1380 and "最終投資建議" in item["raw_text"]]
    assert horizon and all(item["matched_path"] == "rerun_context.parsed.recommendation.中期目標（6個月）" for item in horizon)
    assert any(item["verification_reason_code"] == "confidence_metadata_not_evidence" for item in results["2308_c"]["sampled_claims"])
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    print(json.dumps({"artifact_hashes_unchanged": len(paths), "negative_fcf_dcf": "unavailable",
                      "sma_matches": len(sma_claims), "compact_6m_matches": len(horizon),
                      "gate_counts": {name: {key: result[key] for key in
                          ("sampled_count", "verified_count", "failed_count", "unverifiable_count")} for name, result in results.items()}}, ensure_ascii=False))
