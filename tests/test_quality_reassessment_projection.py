"""Current-rule re-audit resolves exact findings without rewriting history."""
from copy import deepcopy
import pytest
from reporting.report_conformance_projection import project_report_conformance
from reporting.content_credibility_projection import merge_content_credibility_results


def recorded():
    return {'status':'warning','decision_tree':[
        {'id':'evidence_exit_gate','status':'warning'},
        {'id':'content_credibility','status':'warning'},
        {'id':'report_lint','status':'passed'}],
        'blocking_issues':[], 'warnings':[
            {'id':'evidence_exit_gate','message':'old financial sample warning'},
            {'id':'content_credibility','message':'old derived warning'}]}


def test_reaudit_resolves_only_recomputed_gates_without_mutating_record():
    old=recorded(); original=deepcopy(old)
    result=project_report_conformance(old,{'verdict':'approved'},{'status':'passed'})
    assert result['status']=='passed'
    assert result['warnings']==[]
    assert old==original


def test_unknown_recorded_warning_survives_successful_reaudit():
    old=recorded();old['warnings'].append({'id':'other_unresolved','message':'keep'})
    result=project_report_conformance(old,{'verdict':'approved'},{'status':'passed'})
    assert result['status']=='warning'
    assert {x['id'] for x in result['warnings']}=={'other_unresolved'}


def test_final_audit_block_is_never_cleared_by_financial_reaudit():
    old=recorded();old['status']='blocked';old['blocking_issues']=[{'id':'final_audit','message':'critical'}]
    old['decision_tree'].append({'id':'final_audit','status':'blocked'})
    result=project_report_conformance(old,{'verdict':'approved'},{'status':'passed'})
    assert result['status']=='blocked'
    assert result['blocking_issues'][0]['id']=='final_audit'
    assert result['warnings']==[]


def test_absent_current_content_does_not_resolve_recorded_content_warning():
    old=recorded()
    result=project_report_conformance(old,{'verdict':'approved'},None)
    assert result['status']=='warning'
    assert {x['id'] for x in result['warnings']}=={'content_credibility'}


def test_unexplained_higher_recorded_severity_remains_visible():
    old=recorded();old['status']='blocked'  # The two warnings do not account for this severity.
    result=project_report_conformance(old,{'verdict':'approved'},{'status':'passed'})
    assert result['status']=='blocked'


def test_still_failing_gate_keeps_warning_and_receives_current_details():
    result=project_report_conformance(recorded(),{'verdict':'caution','unverifiable_count':1},{'status':'warning'})
    assert result['status']=='warning'
    assert any(x['id']=='evidence_exit_gate' for x in result['warnings'])


def proof_check():
    return {'id':'recommendation_target_alignment','status':'not_applicable','details':{
        'contract_scope':'v3_explicit_no_position','contract_verified':True,
        'execution_status':'no_position','recommendation':'避免','pipeline_id':'v3',
        'analysis_completeness':'not_evaluated','current_price':30.5,'target_price':None}}


def test_strict_no_position_proof_resolves_only_old_missing_price_warning():
    old={'status':'warning','warnings':[{'id':'missing_price_alignment_inputs'}, {'id':'market_context_assessment'}]}
    projected={'status':'warning','warnings':[{'id':'market_context_assessment'}],'checks':[proof_check()]}
    result=merge_content_credibility_results(old,projected)
    assert result['status']=='warning'
    assert {x['id'] for x in result['warnings']}=={'market_context_assessment'}


@pytest.mark.parametrize('field,value',[('contract_verified',False),('contract_verified','true'),('contract_scope','unknown'),('recommendation','放空'),('execution_status','ready'),('target_price',12)])
def test_incomplete_or_contradictory_na_proof_never_hides_missing_price(field,value):
    check=proof_check();check['details'][field]=value
    old={'status':'warning','warnings':[{'id':'missing_price_alignment_inputs'}]}
    result=merge_content_credibility_results(old,{'status':'passed','checks':[check]})
    assert result['status']=='warning'
    assert result['warnings'][0]['id']=='missing_price_alignment_inputs'


def test_report_index_conformance_uses_merged_content_findings(tmp_path, monkeypatch):
    import json
    import report_index_rows

    snapshot = {
        'pipeline': 'v3', 'data': {'ticker': '5314.TWO', 'current_price': 30.5},
        'content_credibility': {'status': 'blocked', 'blocking_issues': [
            {'id': 'unresolved_source_contract', 'message': 'preserve source proof failure'}]},
        'report_conformance': {'status': 'warning', 'warnings': [
            {'id': 'evidence_exit_gate', 'message': 'old evidence warning'}]},
    }
    source = tmp_path / 'sample.data.json'
    source.write_text(json.dumps(snapshot), encoding='utf-8')
    monkeypatch.setattr(report_index_rows, 'project_evidence_exit_gate',
                        lambda *args: {'verdict': 'approved'})
    monkeypatch.setattr(report_index_rows, 'project_content_credibility_with_current_evidence',
                        lambda *args, **kwargs: {'status': 'passed'})
    row = {'filename': '5314_TWO_v3_report_sample.html', 'ticker': '5314.TWO',
           'company_name': 'sample', 'report_date': '2026-09-20 16:00',
           'timestamp': 1789891200, 'pipeline_id': 'v3',
           'recommendation_json': '{}', 'data_trust_json': '{}',
           'data_snapshot_filename': source.name, 'output_dir': str(tmp_path)}
    report = report_index_rows.row_to_report(row)
    assert report['content_credibility']['status'] == 'blocked'
    assert report['report_conformance']['status'] == 'blocked'
    assert any(issue['id'] == 'unresolved_source_contract'
               for issue in report['content_credibility']['blocking_issues'])
