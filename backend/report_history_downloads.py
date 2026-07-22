"""Download and view responses for report history files."""

from __future__ import annotations

from fastapi.responses import HTMLResponse, Response

from data_trust import data_snapshot_filename_for_report
from report_history_snapshot_notice import invalid_snapshot_notice_context
from report_history_storage import load_storage_item
from report_view_repair import repair_report_html_for_view, repair_report_markdown_for_download
from storage.report_storage import ReportStorage


REPORT_HTML_SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'none'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def secure_html_response(content: str, *, status_code: int = 200, headers: dict | None = None) -> HTMLResponse:
    response_headers = dict(REPORT_HTML_SECURITY_HEADERS)
    response_headers.update(headers or {})
    return HTMLResponse(content, status_code=status_code, media_type="text/html", headers=response_headers)


def missing_report_response(kind: str = "html") -> HTMLResponse:
    if kind == "md":
        return secure_html_response("<h1>找不到報告 Markdown 版本</h1>", status_code=404)
    if kind == "data":
        return secure_html_response("<h1>找不到報告資料快照</h1>", status_code=404)
    if kind == "html":
        return secure_html_response("<h1>找不到報告</h1>", status_code=404)
    raise ValueError(f"Unknown report download kind: {kind}")


def report_file_response(filename: str, storage: ReportStorage) -> HTMLResponse:
    item = load_storage_item(storage, filename, kind="html")
    if item is None:
        return missing_report_response("html")
    html = repair_report_html_for_view(
        item.content.decode("utf-8"),
        reading_notice_context=invalid_snapshot_notice_context(storage, filename),
    )
    return secure_html_response(html)


def download_report_response(filename: str, kind: str, storage: ReportStorage):
    if kind == "html":
        item = load_storage_item(storage, filename, kind="html")
        if item is None:
            return missing_report_response("html")
        html = repair_report_html_for_view(
            item.content.decode("utf-8"),
            reading_notice_context=invalid_snapshot_notice_context(storage, filename),
        )
        return secure_html_response(
            html,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if kind == "md":
        md_filename = filename[:-5] + ".md"
        item = load_storage_item(storage, filename, kind="md")
        if item is None:
            return missing_report_response("md")
        markdown = repair_report_markdown_for_download(
            item.content.decode("utf-8"),
            reading_notice_context=invalid_snapshot_notice_context(storage, filename),
        )
        return Response(
            content=markdown.encode("utf-8"),
            media_type=item.metadata.content_type,
            headers={"Content-Disposition": f"attachment; filename={md_filename}"},
        )
    if kind == "data":
        data_filename = data_snapshot_filename_for_report(filename)
        item = load_storage_item(storage, filename, kind="data")
        if item is None:
            return missing_report_response("data")
        return Response(
            content=item.content,
            media_type=item.metadata.content_type,
            headers={"Content-Disposition": f"attachment; filename={data_filename}"},
        )
    raise ValueError(f"Unknown report download kind: {kind}")


__all__ = [
    "download_report_response",
    "missing_report_response",
    "report_file_response",
    "secure_html_response",
]
