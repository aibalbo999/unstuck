from __future__ import annotations

from datetime import date
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_oos_twse_sessions.py"


def _module():
    spec = importlib.util.spec_from_file_location("build_oos_twse_sessions_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_excludes_weekends_and_registered_tw_holidays():
    payload = _module().build(start=date(2026, 9, 24), end=date(2026, 9, 30))

    assert payload["session_open_local_time"] == "09:00:00"
    assert payload["sessions"] == ["2026-09-24", "2026-09-29", "2026-09-30"]
    assert len(payload["calendar_definition_sha256"]) == 64


def test_writer_is_canonical_and_never_overwrites(tmp_path):
    module = _module()
    payload = module.build(start=date(2026, 9, 9), end=date(2026, 9, 11))
    output = tmp_path / "sessions.json"
    module.write_exclusive(output, payload)
    assert json.loads(output.read_text()) == payload
    with pytest.raises(ValueError, match="new absolute path"):
        module.write_exclusive(output, payload)
