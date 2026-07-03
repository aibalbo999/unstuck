"""Canonical report rendering service."""

from __future__ import annotations

from data_trust import build_data_snapshot
from data_trust_snapshot import set_snapshot_integrity
from evidence_exit_gate import evaluate_report_evidence

from .conformance import evaluate_report_conformance
from .html_renderer import generate_html_report_async
from .lint import ReportLintError, assert_report_lint_passed, scrub_structured_json_key_leaks
from .markdown_renderer import generate_markdown_report
from .types import ReportBundle, ReportRequest


def _lint_or_repair(html: str, markdown: str) -> tuple[str, str, dict]:
    try:
        report_lint = assert_report_lint_passed(html, markdown)
    except ReportLintError as exc:
        labels = {issue.get("label") for issue in exc.result.get("blocking_issues", [])}
        if labels != {"structured_json_key_leak"}:
            raise
        html = scrub_structured_json_key_leaks(html)
        markdown = scrub_structured_json_key_leaks(markdown)
        report_lint = assert_report_lint_passed(html, markdown)
    return html, markdown, report_lint


class ReportRenderer:
    async def render_async(self, request: ReportRequest) -> ReportBundle:
        html = await generate_html_report_async(request.context)
        markdown = generate_markdown_report(request.context)
        html, markdown, report_lint = _lint_or_repair(html, markdown)
        snapshot_context = dict(request.context)
        snapshot_context["report_lint"] = report_lint
        snapshot = build_data_snapshot(
            snapshot_context,
            pipeline_id=request.pipeline_id or snapshot_context.get("pipeline_id"),
            generated_at=request.generated_at,
        )
        evidence_exit_gate = evaluate_report_evidence(markdown, snapshot)
        final_context = dict(request.context)
        final_context["report_lint"] = report_lint
        final_context["evidence_exit_gate"] = evidence_exit_gate
        html = await generate_html_report_async(final_context)
        markdown = generate_markdown_report(final_context)
        html, markdown, report_lint = _lint_or_repair(html, markdown)
        snapshot_context = dict(final_context)
        snapshot_context["report_lint"] = report_lint
        snapshot = build_data_snapshot(
            snapshot_context,
            pipeline_id=request.pipeline_id or snapshot_context.get("pipeline_id"),
            generated_at=request.generated_at,
        )
        report_conformance = evaluate_report_conformance(
            html,
            markdown,
            context=final_context,
            snapshot=snapshot,
            report_lint=report_lint,
            evidence_exit_gate=evidence_exit_gate,
        )
        final_context["report_lint"] = report_lint
        final_context["report_conformance"] = report_conformance
        html = await generate_html_report_async(final_context)
        markdown = generate_markdown_report(final_context)
        html, markdown, report_lint = _lint_or_repair(html, markdown)
        snapshot_context = dict(final_context)
        snapshot_context["report_lint"] = report_lint
        snapshot = build_data_snapshot(
            snapshot_context,
            pipeline_id=request.pipeline_id or snapshot_context.get("pipeline_id"),
            generated_at=request.generated_at,
        )
        snapshot["evidence_exit_gate"] = evidence_exit_gate
        snapshot["report_conformance"] = report_conformance
        snapshot = set_snapshot_integrity(snapshot)
        metadata = {
            "filename": request.filename,
            "ticker": request.context.get("ticker"),
            "company_name": request.context.get("company_name"),
            "pipeline_id": request.pipeline_id or request.context.get("pipeline_id"),
            "data_trust": snapshot.get("data_trust", {}),
            "report_lint": report_lint,
            "evidence_exit_gate": evidence_exit_gate,
            "report_conformance": report_conformance,
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
