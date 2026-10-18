"""Allow fixed report runtimes without trusting arbitrary artifact scripts."""

from __future__ import annotations

import base64
import hashlib
import re

from .common import render_report_template


CHART_LIBRARY_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
_LEGACY_RUNTIME_HASHES = frozenset({
    "+X8W7FUAJhbVe/HkS6EEIAsw9b3F02bOCn0s9wvFqFU=",
})


def _chart_runtime() -> str:
    return "\n    " + render_report_template("includes/report_charts.html.j2", {}) + "\n"


def upgrade_legacy_chart_runtime(html: str) -> str:
    """Replace only a pinned first-party runtime, never certify artifact code."""
    def replace(match: re.Match) -> str:
        digest = base64.b64encode(hashlib.sha256(match[1].encode("utf-8")).digest()).decode("ascii")
        return f"<script>{_chart_runtime()}</script>" if digest in _LEGACY_RUNTIME_HASHES else match[0]

    return re.sub(r"<script>(.*?)</script>", replace, html, flags=re.DOTALL)


def trusted_chart_script_sources(html: str) -> str | None:
    # Match report.html.j2's wrapper exactly; never hash scripts from the artifact.
    script = _chart_runtime()
    sources = []
    if f"<script>{script}</script>" in html:
        digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
        sources.extend((f"'sha256-{digest}'", CHART_LIBRARY_URL))
    reader = render_report_template("includes/report_reader_script.html.j2", {})
    if f'<script id="report-reader-script">{reader}</script>' in html:
        digest = base64.b64encode(hashlib.sha256(reader.encode("utf-8")).digest()).decode("ascii")
        sources.append(f"'sha256-{digest}'")
    return f"script-src {' '.join(sources)}; script-src-attr 'none'" if sources else None
