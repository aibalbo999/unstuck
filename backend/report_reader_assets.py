"""Reversible, presentation-only additions to saved HTML reports."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

START = "<!-- onstock-reader:start:v1 -->"
END = "<!-- onstock-reader:end:v1 -->"
TEMPLATES = Path(__file__).resolve().parent / "templates"


def reader_observations(snapshot: dict | None = None) -> dict:
    """Expose only bounded display facts, never private receipts or new verdicts."""
    from data_trust import source_label
    from report_evidence_gap_details import evidence_gap_details

    snapshot = snapshot if isinstance(snapshot, dict) else {}
    data = snapshot.get('data') if isinstance(snapshot.get('data'), dict) else {}
    audits = data.get('source_audit', snapshot.get('source_audit', []))
    audits = audits if isinstance(audits, list) else []
    rows = []
    for row in audits:
        if not isinstance(row, dict):
            continue
        selected = {key: row.get(key) if isinstance(row.get(key), str) else ''
                    for key in ('source', 'provider', 'status', 'error_kind', 'message', 'fetched_at')}
        selected['label'] = source_label(selected['source'])
        selected['record_count'] = row.get('record_count') if type(row.get('record_count')) is int else None
        selected['stale'] = row.get('stale') is not False
        rows.append(selected)
    raw_calendar = data.get('event_calendar')
    raw_calendar = raw_calendar if isinstance(raw_calendar, dict) else {}
    calendar = {key: raw_calendar.get(key) if isinstance(raw_calendar.get(key), str) else ''
                for key in ('as_of_date', 'status', 'calendar_fetch_status', 'calendar_error_kind')}
    calendar['coverage_complete'] = raw_calendar.get('coverage_complete') is True
    events = raw_calendar.get('events')
    calendar['events'] = [{key: event.get(key) if isinstance(event.get(key), str) else ''
                           for key in ('type', 'label', 'date', 'end_date', 'source')}
                          for event in events if isinstance(event, dict)][:30] if isinstance(events, list) else []
    return {'source_audit': rows, 'event_calendar': calendar,
            'evidence_gaps': evidence_gap_details(data, snapshot.get('_reader_institutional_reports', ()), snapshot.get('_reader_volume_observation'), snapshot.get('_reader_cash_flow_review')) if data else {},
            'analysis_not_rerun': snapshot.get('refreshed_without_analysis_rerun') is True,
            'refreshed_at': snapshot.get('snapshot_refreshed_at') if isinstance(snapshot.get('snapshot_refreshed_at'), str) else ''}


def reader_payload(snapshot: dict | None = None) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.get_template("includes/report_reader.html.j2").render(reader_observations=reader_observations(snapshot))


def remove_reader(html: str) -> str:
    if "<!-- onstock-reader:" not in html:
        return html
    if html.count(START) != 1 or html.count(END) != 1:
        raise ValueError("Unknown or incomplete reader asset block")
    start, end_start = html.index(START), html.index(END)
    if end_start < start:
        raise ValueError("Invalid reader asset block order")
    end = end_start + len(END)
    return html[:start] + html[end:]


def inject_reader(html: str, *, snapshot: dict | None = None) -> str:
    original = remove_reader(html)
    if not re.search(r'<main\b[^>]*class=["\'][^"\']*\bmain\b', original, re.I):
        raise ValueError("Unrecognized report HTML")
    closing = re.search(r"</body\s*>\s*</html\s*>\s*$", original, re.I)
    if closing is None:
        raise ValueError("Incomplete report HTML")
    return original[:closing.start()] + reader_payload(snapshot) + original[closing.start():]
