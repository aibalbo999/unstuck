import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


import prompt_builder  # noqa: E402


def test_render_prompt_template_reuses_compiled_template(monkeypatch):
    calls = []
    original_from_string = prompt_builder.PROMPT_ENV.from_string
    prompt_builder._get_compiled_prompt_template.cache_clear()

    def tracking_from_string(template):
        calls.append(template)
        return original_from_string(template)

    monkeypatch.setattr(prompt_builder.PROMPT_ENV, "from_string", tracking_from_string)

    with pytest.warns(DeprecationWarning, match="legacy prompt placeholder"):
        assert prompt_builder.render_prompt_template("標的 {ticker}", {"ticker": "2330.TW"}) == "標的 2330.TW"
    with pytest.warns(DeprecationWarning, match="legacy prompt placeholder"):
        assert prompt_builder.render_prompt_template("標的 {ticker}", {"ticker": "2308.TW"}) == "標的 2308.TW"

    assert calls == ["標的 {{ ticker }}"]

    prompt_builder._get_compiled_prompt_template.cache_clear()
