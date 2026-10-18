from evidence_exit_gate import evaluate_report_evidence
from reporting.evidence_ledger_view import evidence_ledger_markdown, evidence_ledger_html


def test_all_beyond_old_cap_rejects_late_mismatch():
    result = evaluate_report_evidence('\n'.join(['- 股價: NT$100.0'] * 40 + ['- 股價: NT$999.0']), {'data': {'current_price': 100}})
    assert result['sampled_count'] == result['claim_count'] == 41
    assert result['failed_count'] == 1 and result['verdict'] == 'rejected'
    assert result['coverage_complete'] and result['unchecked_count'] == 0


def test_incomplete_diagnostic_never_approved():
    result = evaluate_report_evidence('\n'.join(['- 股價: NT$100.0'] * 40), {'data': {'current_price': 100}}, max_sample=3)
    assert result['verdict'] == 'caution' and result['unchecked_count'] == 37


def test_ledger_not_reaudited_and_html_escaped():
    text = '- 股價: NT$100.0'; snapshot = {'data': {'current_price': 100}}
    result = evaluate_report_evidence(text, snapshot); context = {'evidence_exit_gate': result}
    assert evaluate_report_evidence(text + evidence_ledger_markdown(context), snapshot)['claim_count'] == 1
    assert 'data.current_price' in evidence_ledger_html(context)
    result['sampled_claims'][0]['label'] = '<script>alert(1)</script>'
    assert '<script>' not in evidence_ledger_html(context)
