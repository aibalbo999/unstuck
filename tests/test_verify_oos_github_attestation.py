from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from oos_research.manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_oos_github_attestation.py"


def _module():
    spec = importlib.util.spec_from_file_location("verify_oos_github_attestation_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(path: Path) -> dict:
    manifest = build_manifest(
        schema_version="oos.manifest.v1",
        study_id="prospective-attested-four-mode",
        study_kind="prospective",
        registered_at="2026-09-08T00:00:00Z",
        timezone="Asia/Taipei",
        selection_period={"start": "2026-09-09", "end": "2026-09-11"},
        ticker_universe=["1623.TW"],
        pipelines=["v1"],
        horizons={"v1": [3, 6, 12]},
        policies={"missing": "retain"},
        evaluator_version="oos.evaluator.v1",
    )
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_verify_and_write_locks_policy_and_persists_only_projection(tmp_path):
    module = _module()
    manifest_path = tmp_path / "manifest.json"
    manifest = _manifest(manifest_path)
    bundle = tmp_path / "bundle.jsonl"
    trusted_root = tmp_path / "trusted-root.jsonl"
    bundle.write_text('{"bundle":true}\n', encoding="utf-8")
    trusted_root.write_text('{"root":true}\n', encoding="utf-8")
    output = tmp_path / "registration.json"
    captured = {}

    def verifier(**kwargs):
        captured.update(kwargs)
        return {"secret": "not persisted"}

    projection = {
        "external_registration_receipt": {
            "manifest_sha256": manifest["manifest_sha256"],
            "source_commit": "a" * 40,
            "verified_at": "2026-09-08T00:01:00Z",
        }
    }
    result = module.verify_and_write(
        manifest=manifest_path,
        bundle=bundle,
        trusted_root=trusted_root,
        source_commit="a" * 40,
        source_ref=module.DEFAULT_SOURCE_REF,
        output=output,
        verifier=verifier,
        projector=lambda evidence: projection,
    )

    assert result == projection
    assert json.loads(output.read_text()) == projection
    assert "secret" not in output.read_text()
    assert captured["expected_manifest_sha256"] == manifest["manifest_sha256"]
    policy = captured["policy"]
    assert policy.repository == "aibalbo999/unstuck"
    assert policy.source_commit == "a" * 40
    assert policy.source_ref == module.DEFAULT_SOURCE_REF
    assert policy.certificate_identity.endswith(
        ".github/workflows/oos-register.yml@refs/heads/codex/analysis-credibility-spec"
    )


def test_verify_and_write_never_overwrites_and_rejects_empty_projection(tmp_path):
    module = _module()
    manifest_path = tmp_path / "manifest.json"
    _manifest(manifest_path)
    bundle = tmp_path / "bundle.jsonl"
    trusted_root = tmp_path / "trusted-root.jsonl"
    bundle.write_text('{}\n', encoding="utf-8")
    trusted_root.write_text('{}\n', encoding="utf-8")
    output = tmp_path / "registration.json"
    output.write_text("valuable", encoding="utf-8")
    with pytest.raises(ValueError, match="new absolute path"):
        module.verify_and_write(
            manifest=manifest_path, bundle=bundle, trusted_root=trusted_root,
            source_commit="a" * 40, source_ref=module.DEFAULT_SOURCE_REF,
            output=output, verifier=lambda **kwargs: {}, projector=lambda evidence: {},
        )
    assert output.read_text() == "valuable"

    output.unlink()
    with pytest.raises(RuntimeError, match="no runtime-verified projection"):
        module.verify_and_write(
            manifest=manifest_path, bundle=bundle, trusted_root=trusted_root,
            source_commit="a" * 40, source_ref=module.DEFAULT_SOURCE_REF,
            output=output, verifier=lambda **kwargs: {}, projector=lambda evidence: {},
        )
    assert not output.exists()


def test_manifest_hash_loader_rejects_duplicate_keys(tmp_path):
    module = _module()
    path = tmp_path / "manifest.json"
    path.write_text('{"manifest_sha256":"' + "a" * 64 + '","manifest_sha256":"' + "a" * 64 + '"}')
    with pytest.raises(ValueError):
        module.load_manifest_sha256(path)
