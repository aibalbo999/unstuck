"""Allow fixed report runtimes without trusting arbitrary artifact scripts."""

from __future__ import annotations

import base64
import hashlib

from .common import render_report_template


CHART_LIBRARY_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"


def trusted_chart_script_sources(html: str) -> str | None:
    # Match report.html.j2's wrapper exactly; never hash scripts from the artifact.
    script = "\n    " + render_report_template("includes/report_charts.html.j2", {}) + "\n"
    sources = []
    if f"<script>{script}</script>" in html:
        digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
        sources.extend((f"'sha256-{digest}'", CHART_LIBRARY_URL))
    reader = render_report_template("includes/report_reader_script.html.j2", {})
    if f'<script id="report-reader-script">{reader}</script>' in html:
        digest = base64.b64encode(hashlib.sha256(reader.encode("utf-8")).digest()).decode("ascii")
        sources.append(f"'sha256-{digest}'")
    return f"script-src {' '.join(sources)}; script-src-attr 'none'" if sources else None
