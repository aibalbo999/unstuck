"""Canonical report rendering service."""

from __future__ import annotations

from data_trust import build_data_snapshot
from data_trust_snapshot import set_snapshot_integrity
from evidence_exit_gate import evaluate_report_evidence

from .html_renderer import generate_html_report_async
from .lint import ReportLintError, assert_report_lint_passed, scrub_structured_json_key_leaks
from .markdown_renderer import generate_markdown_report
from .types import ReportBundle, ReportRequest


class ReportRenderer:
    async def render_async(self, request: ReportRequest) -> ReportBundle:
        html = await generate_html_report_async(request.context)
        markdown = generate_markdown_report(request.context)
        try:
            report_lint = assert_report_lint_passed(html, markdown)
        except ReportLintError as exc:
            labels = {issue.get("label") for issue in exc.result.get("blocking_issues", [])}
            if labels != {"structured_json_key_leak"}:
                raise
            html = scrub_structured_json_key_leaks(html)
            markdown = scrub_structured_json_key_leaks(markdown)
            report_lint = assert_report_lint_passed(html, markdown)
        snapshot_context = dict(request.context)
        snapshot_context["report_lint"] = report_lint
        snapshot = build_data_snapshot(
            snapshot_context,
            pipeline_id=request.pipeline_id or snapshot_context.get("pipeline_id"),
            generated_at=request.generated_at,
        )
        evidence_exit_gate = evaluate_report_evidence(markdown, snapshot)
        snapshot["evidence_exit_gate"] = evidence_exit_gate
        snapshot = set_snapshot_integrity(snapshot)
        metadata = {
            "filename": request.filename,
            "ticker": request.context.get("ticker"),
            "company_name": request.context.get("company_name"),
            "pipeline_id": request.pipeline_id or request.context.get("pipeline_id"),
            "data_trust": snapshot.get("data_trust", {}),
            "report_lint": report_lint,
            "evidence_exit_gate": evidence_exit_gate,
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
