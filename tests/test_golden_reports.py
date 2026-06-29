from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import reporting.legacy_report_gen as report_gen  # noqa: E402
import reporting.markdown_renderer as markdown_renderer  # noqa: E402


GOLDEN_MARKDOWN = ROOT / "tests" / "fixtures" / "golden_reports" / "2330_v1_markdown.json"


def _normalized_markdown(markdown: str) -> str:
    return "\n".join(line.rstrip() for line in markdown.strip().splitlines()) + "\n"


def test_2330_v1_markdown_report_matches_golden_snapshot(monkeypatch):
    monkeypatch.setattr(
        markdown_renderer,
        "format_model_routes",
        lambda agent_models=None, pipeline_id="v1": "golden model route",
    )
    spec = json.loads(GOLDEN_MARKDOWN.read_text(encoding="utf-8"))
    context = deepcopy(spec["context"])

    markdown = _normalized_markdown(report_gen.generate_markdown_report(context))
    actual_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    assert actual_sha256 == spec["sha256"], (
        "Golden report snapshot drifted. If this report change is intentional, "
        f"update {GOLDEN_MARKDOWN.name} with sha256={actual_sha256}."
    )
    for marker in spec["required_markers"]:
        assert marker in markdown
