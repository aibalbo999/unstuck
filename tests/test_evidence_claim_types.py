"""Date and analysis-score metadata never stand in for financial evidence."""
import pytest

from evidence_exit_gate import evaluate_report_evidence, extract_numeric_claims


SNAPSHOT = {'data': {'current_price': 100, 'pe_ratio': 20, 'revenue': 20000000}}
FINANCIAL = '- 股價: 100元\n- P/E: 20x\n- 營收: 20000000'


def test_calendar_metadata_excludes_only_its_match_and_keeps_same_line_price():
    text = '- as_of_date: 20260918；股價: 100元\n- 營收: 20000000'
    claims = extract_numeric_claims(text)
    assert [claim['reported_value'] for claim in claims] == [100, 20000000]
    assert evaluate_report_evidence(text, SNAPSHOT, sample_ratio=1)['verdict'] == 'approved'


@pytest.mark.parametrize('text', ['營收: 20260918', 'as_of_date: 20260918元',
                                 'as_of_date: 20260230', 'as_of_date: 20000000'])
def test_financial_values_or_invalid_dates_are_not_discarded(text):
    assert len(extract_numeric_claims(text)) == 1


def test_valid_scores_have_separate_checked_counts_not_financial_verification():
    result = evaluate_report_evidence(FINANCIAL + '\n資料信心分數:91/100\nFOMO評分:4/10', SNAPSHOT)
    assert result['schema_version'] == 2
    assert result['claim_count'] == result['sampled_count'] == result['verified_count'] == 3
    assert result['metadata_claim_count'] == result['metadata_checked_count'] == 2
    assert result['metadata_invalid_count'] == result['metadata_unverifiable_count'] == 0
    assert all(item['claim_type'] == 'analysis_score' and item['status'] == 'valid'
               and item['financial_evidence'] is False for item in result['metadata_claims'])
    assert result['verdict'] == 'approved'


@pytest.mark.parametrize('score', ['資料信心分數:101/100', 'FOMO評分:-1/10',
                                  'FOMO評分:11/10', 'FOMO評分:NaN', 'FOMO評分:Infinity',
                                  'FOMO評分:1e999', '信心:8/0'])
def test_invalid_scores_remain_visible_and_prevent_approval(score):
    result = evaluate_report_evidence(FINANCIAL + '\n' + score, SNAPSHOT)
    assert result['verified_count'] == 3
    assert result['metadata_invalid_count'] == 1
    assert result['metadata_claims'][0]['verification_reason_code'] in {
        'score_not_finite', 'score_out_of_range', 'score_scale_invalid'}
    assert result['verdict'] == 'caution'


@pytest.mark.parametrize('score', ['信心:0.85', 'Score:4'])
def test_unstated_scale_is_not_guessed(score):
    result = evaluate_report_evidence(FINANCIAL + '\n' + score, SNAPSHOT)
    assert result['metadata_unverifiable_count'] == 1
    assert result['metadata_claims'][0]['verification_reason_code'] == 'score_scale_unspecified'
    assert result['verdict'] == 'caution'


def test_metadata_alone_cannot_make_zero_financial_claims_approved():
    result = evaluate_report_evidence('資料信心分數:91/100\nFOMO評分:4/10', {})
    assert result['claim_count'] == result['sampled_count'] == result['verified_count'] == 0
    assert result['metadata_checked_count'] == 2
    assert result['verdict'] == 'caution'


def test_financial_mismatch_and_sampling_policy_are_preserved():
    text = FINANCIAL.replace('100元', '500元') + '\n信心:9/10\nFOMO評分:5/10'
    result = evaluate_report_evidence(text, SNAPSHOT)
    assert result['sampled_count'] == 3
    assert result['failed_count'] == 1
    assert result['verdict'] != 'approved'
    assert result['tolerance_pct'] == 1
    assert any(item['reported_value'] == 500 and item['status'] == 'mismatch' for item in result['sampled_claims'])


def test_score_on_same_line_does_not_hide_financial_claim_or_scenario_revenue():
    result = evaluate_report_evidence('信心:8/10；股價:500元\n| 保守 | 未入帳情境 | NT$357億 |', SNAPSHOT, sample_ratio=1)
    assert result['metadata_claim_count'] == 1
    assert {item['reported_value'] for item in result['sampled_claims']} == {500, 357}
    assert result['failed_count'] == 1


def test_financial_unit_prevents_label_score_from_becoming_metadata():
    claims = extract_numeric_claims('股價評分:20000000元')
    assert claims[0].get('claim_type', 'financial') == 'financial'


@pytest.mark.parametrize('text', ['信心(0-1):0.85', '信心（0–100）:85',
                                 '| 信心 | 8/10 |', '| FOMO評分 | 4/10 |'])
def test_explicit_label_and_table_scales_are_validated(text):
    result = evaluate_report_evidence(text, {})
    assert result['metadata_checked_count'] == 1
    assert result['metadata_claims'][0]['status'] == 'valid'
    assert result['claim_count'] == 0


@pytest.mark.parametrize('text', ['信心(0-1):1.85', 'FOMO評分:0/10', 'FOMO評分:90/100'])
def test_explicit_ranges_and_known_agent_contracts_cannot_be_exceeded(text):
    result = evaluate_report_evidence(text, {})
    assert result['metadata_invalid_count'] == 1


def test_nonfinite_metadata_is_json_serializable_without_nan_tokens():
    import json
    result = evaluate_report_evidence('FOMO評分:NaN\n信心:1e999/100', {})
    assert result['metadata_invalid_count'] == 2
    json.dumps(result, allow_nan=False)


def test_invalid_date_metadata_is_not_silently_dropped_by_broad_label_marker():
    assert extract_numeric_claims('資料日期:20260230')[0]['reported_value'] == 20260230


def test_percentage_under_moat_dimension_is_not_assumed_to_be_a_score():
    result = evaluate_report_evidence('成本優勢:20%', {})
    assert result['claim_count'] == 1
    assert result['metadata_claim_count'] == 0
    assert result['verdict'] != 'approved'


def test_score_addition_does_not_change_seeded_financial_sampling():
    text = '\n'.join(f'股價{i}:100元' for i in range(25))
    plain = evaluate_report_evidence(text, SNAPSHOT)
    scored = evaluate_report_evidence(text + '\n信心:8/10\n資料信心分數:91/100', SNAPSHOT)
    assert plain['sampled_count'] == scored['sampled_count'] == 4
    assert [item['label'] for item in plain['sampled_claims']] == [item['label'] for item in scored['sampled_claims']]


@pytest.mark.parametrize('text', ['信心(0-1):0.85/100', '信心(0-1):0.85%', '信心:85%/10'])
def test_conflicting_explicit_score_scales_are_invalid(text):
    result = evaluate_report_evidence(text, {})
    assert result['metadata_invalid_count'] == 1
    assert result['metadata_claims'][0]['verification_reason_code'] == 'score_scale_invalid'


def test_metadata_explanation_reaches_existing_frontend_and_rendered_report():
    import json
    from pathlib import Path
    import subprocess
    from reporting.execution_summary import build_execution_summary_html, build_execution_summary_markdown

    gate = evaluate_report_evidence(FINANCIAL + '\n信心:0.85\nFOMO評分:11/10', SNAPSHOT)
    assert '財務抽查 3/3 筆' in gate['summary']
    assert '分析評分 2 筆（有效 0、無效 1、量尺未明 1）' in gate['summary']
    assert '不計入財務證據' in gate['summary']
    assert '評分超出合法範圍' in gate['summary']
    assert '評分量尺未明示' in gate['summary']
    policy = Path(__file__).resolve().parents[1] / 'backend/static/report_quality_gate_policy.js'
    script = 'global.window={};require(' + json.dumps(str(policy)) + ');process.stdout.write(JSON.stringify(window.StockAgentReportQualityGatePolicy.reportQualityGateAction({evidence_exit_gate:' + json.dumps(gate) + '})));'
    action = json.loads(subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True).stdout)
    assert action['tone'] == 'warning'
    assert action['detail'] == gate['summary']
    context = {'pipeline_id': 'v4', 'evidence_exit_gate': gate}
    assert gate['summary'] in build_execution_summary_html(context, model_routes='test')
    assert gate['summary'] in build_execution_summary_markdown(context, model_routes='test')
