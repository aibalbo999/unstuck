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


def invalid_report_content_response(kind: str) -> HTMLResponse:
    label = "報告 Markdown" if kind == "md" else "報告 HTML"
    return secure_html_response(f"<h1>{label} 無法解析</h1>", status_code=400)


def decode_report_content(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if not isinstance(content, (bytes, bytearray, memoryview)):
        return None
    try:
        return bytes(content).decode("utf-8")
    except UnicodeDecodeError:
        return None


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


def report_file_response(
    filename: str,
    storage: ReportStorage,
    *,
    reading_notice_context: dict | None = None,
) -> HTMLResponse:
    item = load_storage_item(storage, filename, kind="html")
    if item is None:
        return missing_report_response("html")
    context = reading_notice_context
    if context is None:
        context = invalid_snapshot_notice_context(storage, filename)
    html_content = decode_report_content(item.content)
    if html_content is None:
        return invalid_report_content_response("html")
    html = repair_report_html_for_view(html_content, reading_notice_context=context)
    return secure_html_response(html)


def download_report_response(
    filename: str,
    kind: str,
    storage: ReportStorage,
    *,
    reading_notice_context: dict | None = None,
):
    if kind == "html":
        item = load_storage_item(storage, filename, kind="html")
        if item is None:
            return missing_report_response("html")
        context = reading_notice_context
        if context is None:
            context = invalid_snapshot_notice_context(storage, filename)
        html_content = decode_report_content(item.content)
        if html_content is None:
            return invalid_report_content_response("html")
        html = repair_report_html_for_view(html_content, reading_notice_context=context)
        return secure_html_response(
            html,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    if kind == "md":
        md_filename = filename[:-5] + ".md"
        item = load_storage_item(storage, filename, kind="md")
        if item is None:
            return missing_report_response("md")
        context = reading_notice_context
        if context is None:
            context = invalid_snapshot_notice_context(storage, filename)
        markdown_content = decode_report_content(item.content)
        if markdown_content is None:
            return invalid_report_content_response("md")
        markdown = repair_report_markdown_for_download(markdown_content, reading_notice_context=context)
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
