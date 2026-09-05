"""Allow the fixed report chart runtime without trusting artifact scripts."""

from __future__ import annotations

import base64
import hashlib

from .common import render_report_template


CHART_LIBRARY_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"


def trusted_chart_script_sources(html: str) -> str | None:
    # Match report.html.j2's wrapper exactly; never hash scripts from the artifact.
    script = "\n    " + render_report_template("includes/report_charts.html.j2", {}) + "\n"
    if f"<script>{script}</script>" not in html:
        return None
    digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    return f"script-src 'sha256-{digest}' {CHART_LIBRARY_URL}; script-src-attr 'none'"
