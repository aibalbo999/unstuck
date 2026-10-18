"""Public boundary checks. Original private-data replay cases remain local."""
import asyncio
import copy
import pytest
from evidence_exit_gate import evaluate_report_evidence
from reporting import ReportRenderer, ReportRequest

def evidence_for(bundle):
    return evaluate_report_evidence(bundle.markdown, bundle.data_snapshot)

@pytest.mark.parametrize('pipeline', ['v1', 'v2', 'v3', 'v4'])
def test_gate_snapshot_contains_input_before_first_gate_all_modes(pipeline, monkeypatch):
    import reporting.renderer as module
    from analysis_input_provenance import freeze_analysis_inputs
    data = {'ticker': 'TEST', 'current_price': 100, 'quant_metrics': {'rsi': 61}}
    freeze_analysis_inputs(data, cutoff='2026-10-08T07:00:00Z')
    real = module.evaluate_report_evidence
    seen = []

    def evidence(md, snapshot):
        assert snapshot['analysis_evidence']['input_verification'] == 'hash_verified'
        seen.append(copy.deepcopy(snapshot['analysis_evidence']))
        return real(md, snapshot)

    async def html(context):
        return '<html><p>股價: 100</p></html>'
    monkeypatch.setattr(module, 'evaluate_report_evidence', evidence)
    monkeypatch.setattr(module, 'generate_html_report_async', html)
    monkeypatch.setattr(module, 'generate_markdown_report', lambda c: '- 股價: 100')
    bundle = asyncio.run(ReportRenderer().render_async(ReportRequest(context={'ticker': 'TEST', 'data': data, 'parsed': {}, 'pipeline_id': pipeline}, pipeline_id=pipeline, generated_at='2026-10-08T07:01:00Z')))
    assert seen and all((x == bundle.data_snapshot['analysis_evidence'] for x in seen))
    assert evidence_for(bundle) == bundle.data_snapshot['evidence_exit_gate']
