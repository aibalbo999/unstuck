from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from oos_research.manifest import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_oos_prospective_manifest.py"


def _module():
    spec = importlib.util.spec_from_file_location("build_oos_prospective_manifest_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scope(module):
    return {
        "prepare_only": True,
        "refresh_candidate_count": 28,
        "jobs": [
            {"ticker": ticker, "pipeline_id": pipeline}
            for ticker in module.TICKERS for pipeline in module.PIPELINES
        ],
    }


def test_builder_binds_exact_scope_runtime_and_horizons(tmp_path):
    module = _module()
    source = tmp_path / "scope.json"
    source.write_text(json.dumps(_scope(module)), encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    manifest = module.build(
        source=source,
        source_sha256=source_hash,
        registered_at="2026-09-08T10:00:00Z",
        production_parent_commit="c" * 40,
        prompt_fingerprint="a" * 64,
        model_route_policy_sha256="b" * 64,
    )

    validate_manifest(manifest)
    assert manifest["selection_period"] == {"start": "2026-09-09", "end": "2026-09-11"}
    assert manifest["horizons"] == {"v1": [3, 6, 12], "v2": [5], "v3": [5], "v4": [5, 10]}
    assert manifest["policies"]["cohort_source_manifest_sha256"] == source_hash
    assert manifest["policies"]["session_open_local_time"] == "09:00:00"
    assert manifest["runtime_identity"]["production_parent_commit"] == "c" * 40


def test_builder_rejects_reordered_or_wrong_hash_scope(tmp_path):
    module = _module()
    scope = _scope(module)
    scope["jobs"].reverse()
    source = tmp_path / "scope.json"
    source.write_text(json.dumps(scope), encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    kwargs = dict(
        source=source,
        registered_at="2026-09-08T10:00:00Z",
        production_parent_commit="c" * 40,
        prompt_fingerprint="a" * 64,
        model_route_policy_sha256="b" * 64,
    )
    with pytest.raises(ValueError, match="ordered"):
        module.build(source_sha256=source_hash, **kwargs)
    with pytest.raises(ValueError, match="SHA-256"):
        module.build(source_sha256="d" * 64, **kwargs)


def test_manifest_writer_never_overwrites(tmp_path):
    module = _module()
    output = tmp_path / "manifest.json"
    output.write_text("valuable")
    with pytest.raises(ValueError, match="new absolute path"):
        module.write_exclusive(output, {"replacement": True})
    assert output.read_text() == "valuable"
