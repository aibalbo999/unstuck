"""Canonical report rendering service."""

from __future__ import annotations

from data_trust import build_data_snapshot

from .html_renderer import generate_html_report_async
from .lint import assert_report_lint_passed
from .markdown_renderer import generate_markdown_report
from .types import ReportBundle, ReportRequest


class ReportRenderer:
    async def render_async(self, request: ReportRequest) -> ReportBundle:
        html = await generate_html_report_async(request.context)
        markdown = generate_markdown_report(request.context)
        report_lint = assert_report_lint_passed(html, markdown)
        snapshot_context = dict(request.context)
        snapshot_context["report_lint"] = report_lint
        snapshot = build_data_snapshot(
            snapshot_context,
            pipeline_id=request.pipeline_id or snapshot_context.get("pipeline_id"),
            generated_at=request.generated_at,
        )
        metadata = {
            "filename": request.filename,
            "ticker": request.context.get("ticker"),
            "company_name": request.context.get("company_name"),
            "pipeline_id": request.pipeline_id or request.context.get("pipeline_id"),
            "data_trust": snapshot.get("data_trust", {}),
            "report_lint": report_lint,
        }
        return ReportBundle(html=html, markdown=markdown, data_snapshot=snapshot, metadata=metadata)

    def render(self, request: ReportRequest) -> ReportBundle:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.render_async(request))
        raise RuntimeError("ReportRenderer.render() cannot run inside an active event loop; use render_async().")


DEFAULT_REPORT_RENDERER = ReportRenderer()
