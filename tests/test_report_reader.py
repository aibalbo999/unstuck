import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.mark.parametrize("pipeline_id", ["v1", "v2", "v3", "v4"])
def test_new_reports_include_the_shared_reader_without_removing_audit(pipeline_id):
    from reporting.html_renderer import generate_html_report
    from test_report_mode_templates import _context

    html = generate_html_report(_context(pipeline_id))
    assert '<!-- onstock-reader:start:v1 -->' in html
    assert 'id="report-reader-script"' in html
    assert 'id="report-chart-data"' in html
    assert "Evidence gate" in html
    assert "Report conformance" in html


def test_legacy_injection_is_reversible_and_idempotent():
    from report_reader_assets import inject_reader, remove_reader

    original = '<!DOCTYPE html>\r\n<html><head></head><body><main class="main">品質 gate 有警示；3315.00</main><script>const x = "<tag>";</script></body></html>\r\n'
    changed = inject_reader(original)
    assert changed != original
    assert remove_reader(changed) == original
    assert inject_reader(changed) == changed


def test_reader_refuses_unknown_or_damaged_documents():
    from report_reader_assets import inject_reader

    for html in ("", "<html><body>not a report</body></html>", '<main class="main">truncated', '<html><body><main class="main"></main><!-- onstock-reader:start:v1 --></body></html>'):
        with pytest.raises(ValueError):
            inject_reader(html)


def test_formal_security_policy_allows_exact_reader_only():
    from report_history_downloads import secure_html_response
    from test_report_chart_security_policy import ScriptCollector, script_hash
    from report_reader_assets import inject_reader

    html = inject_reader('<html><body><main class="main"><div class="hero"></div></main></body></html>')
    parser = ScriptCollector()
    parser.feed(html)
    reader = next(item['text'] for item in parser.scripts if item['attrs'].get('id') == 'report-reader-script')
    malicious = 'window.untrusted = true;'
    response = secure_html_response(html + f'<script>{malicious}</script>')
    policy = response.headers['content-security-policy']
    assert script_hash(reader) in policy
    assert script_hash(malicious) not in policy
    assert "script-src-attr 'none'" in policy
    assert "script-src 'unsafe-inline'" not in policy
    changed = html.replace(reader, reader + malicious)
    assert "script-src 'none'" in secure_html_response(changed).headers['content-security-policy']


def test_reader_metadata_retains_error_kind_and_calendar_without_private_receipts():
    import json
    from report_reader_assets import inject_reader
    from test_report_chart_security_policy import ScriptCollector

    snapshot = {'source_audit': [{'source': 'earnings_call', 'provider': 'official',
        'status': 'error', 'error_kind': 'timeout', 'message': '</script><script>bad()</script>',
        'record_count': 0, 'private_receipt': 'do-not-embed'}],
        'data': {'event_calendar': {'as_of_date': '2026-10-17', 'status': 'success',
            'coverage_complete': False, 'events': [{'type': 'earnings_date', 'date': '2026-11-11'}]}},
        'refreshed_without_analysis_rerun': True}
    original = '<html><body><main class="main"><div class="hero"></div></main></body></html>'
    html = inject_reader(original, snapshot=snapshot)
    parser = ScriptCollector()
    parser.feed(html)
    observed = json.loads(next(item['text'] for item in parser.scripts if item['attrs'].get('id') == 'report-reader-observations'))
    assert observed['source_audit'][0]['error_kind'] == 'timeout'
    assert observed['event_calendar']['events'][0]['date'] == '2026-11-11'
    assert observed['analysis_not_rerun'] is True
    assert 'do-not-embed' not in html
    assert '</script><script>bad()' not in html


def test_new_report_exposes_source_failure_observations_for_readability():
    import json
    from reporting.html_renderer import generate_html_report
    from test_report_mode_templates import _context
    from test_report_chart_security_policy import ScriptCollector

    context = _context('v4')
    context['data']['source_audit'] = [{'source': 'recent_catalysts', 'provider': 'Yahoo Finance news',
        'status': 'error', 'error_kind': 'cooldown', 'message': '來源仍在冷卻期間', 'record_count': 0}]
    parser = ScriptCollector()
    parser.feed(generate_html_report(context))
    observed = json.loads(next(item['text'] for item in parser.scripts if item['attrs'].get('id') == 'report-reader-observations'))
    assert observed['source_audit'][0]['error_kind'] == 'cooldown'


@pytest.mark.parametrize('events', [None, True, {'private_receipt': 'not-an-event-list'}, 'bad-events'])
def test_reader_metadata_does_not_break_rendering_on_malformed_event_list(events):
    from reporting.html_renderer import generate_html_report
    from test_report_mode_templates import _context
    context = _context('v1')
    context['data']['event_calendar'] = {'events': events}
    assert 'id="report-reader-observations"' in generate_html_report(context)
