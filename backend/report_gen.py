"""Deprecated report-generation facade.

New code should use reporting.ReportRenderer.
"""

import warnings

from reporting.legacy_report_gen import *  # noqa: F401,F403
from reporting import ReportBundle, ReportRenderer, ReportRequest  # noqa: F401
from reporting.html_renderer import (  # noqa: F401
    generate_html_report as _generate_html_report,
    generate_html_report_async as _generate_html_report_async,
)
from reporting.markdown_renderer import generate_markdown_report as _generate_markdown_report


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"report_gen.{name} is deprecated; use reporting.ReportRenderer instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def generate_html_report(context):
    _warn_deprecated("generate_html_report")
    return _generate_html_report(context)


async def generate_html_report_async(context):
    _warn_deprecated("generate_html_report_async")
    return await _generate_html_report_async(context)


def generate_markdown_report(context):
    _warn_deprecated("generate_markdown_report")
    return _generate_markdown_report(context)
