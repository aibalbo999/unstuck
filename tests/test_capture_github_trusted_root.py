from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/capture_github_trusted_root.py"


def _module():
    spec = importlib.util.spec_from_file_location("capture_github_trusted_root_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capture_writes_valid_trusted_root_once(tmp_path):
    module = _module()
    raw = b'{"mediaType":"application/vnd.dev.sigstore.trustedroot+json;version=0.1"}\n'

    def runner(argv, **kwargs):
        assert argv == ["gh", "attestation", "trusted-root"]
        return subprocess.CompletedProcess(argv, 0, stdout=raw, stderr=b"")

    output = tmp_path / "trusted-root.jsonl"
    assert module.capture(output=output, runner=runner) == {
        "bytes": len(raw), "document_count": 1,
    }
    assert output.read_bytes() == raw
    with pytest.raises(ValueError, match="new absolute path"):
        module.capture(output=output, runner=runner)


@pytest.mark.parametrize("raw", [b"", b"not-json\n", b"[]\n"])
def test_capture_rejects_empty_or_malformed_output(tmp_path, raw):
    module = _module()

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=raw, stderr=b"")

    output = tmp_path / "trusted-root.jsonl"
    with pytest.raises(RuntimeError):
        module.capture(output=output, runner=runner)
    assert not output.exists()
