"""Run actual panel JavaScript against versioned trading-result fixtures."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


def test_panels_preserve_trading_days_unknown_returns_and_non_scored_status():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for panel contract")
    static = Path(__file__).resolve().parents[1] / "backend/static"
    scripts = "\n".join((static / filename).read_text() for filename in ["performance_panel.js", "temporal_memory_panel.js"])
    fixture = {"summary": {}, "by_horizon": [], "trade_summary": {
        "total_evaluations": 1, "hit_rate_pct": None, "average_strategy_roi_pct": None},
        "trade_by_horizon": {"5": {"total_evaluations": 1, "hit_rate_pct": None, "average_strategy_roi_pct": None}},
        "details": [{"ticker": "TEST", "horizon_months": None, "horizon_trading_days": 5,
                     "outcome": None, "status": "ambiguous", "strategy_roi_pct": None,
                     "entry_price": 100, "exit_price": None}]}
    harness = "const window = {};\n" + scripts + "\nconst payload = " + json.dumps(fixture) + ";\n"
    harness += """
const summaryEl = {}, listEl = {}, memoryRoot = {};
window.StockAgentPerformancePanel.render(payload, {summaryEl, listEl, escapeHtml: value => String(value)});
window.StockAgentTemporalMemoryPanel.render({previous_report: {filename:'prior.html'},
    backtests: payload.details}, memoryRoot, value => String(value));
console.log(JSON.stringify({summary: summaryEl.textContent, html: listEl.innerHTML, memory: memoryRoot.innerHTML}));
"""
    result = subprocess.run([node, "-e", harness], text=True, capture_output=True, check=True)
    rendered = json.loads(result.stdout)
    assert "交易計畫" in rendered["summary"]
    for field in ("html", "memory"):
        assert "5 交易日" in rendered[field]
        assert "nullM" not in rendered[field] and "?M" not in rendered[field]
        assert "N/A" in rendered[field]
        assert "miss" not in rendered[field]
    assert "0.00%" not in rendered["html"]


def test_empty_monthly_metrics_and_original_vs_revision_denominators():
    node=shutil.which('node')
    if node is None:pytest.skip('Node.js required for panel contract')
    static=Path(__file__).resolve().parents[1]/'backend/static'
    fixture={'summary':{},'by_horizon':[{'horizon_months':3,'total':0,'scored_count':0,'hit_rate_pct':0,'average_strategy_roi_pct':0}],
        'population':{'status':'complete_index','expected_slots':1716,'independent_candidate_count':166,
            'net_result_diagnostics':{'primary_nonoverlapping_slots':{'partition':{'awaiting_maturity':71,'executed_result_unverified':13,'missing_result_or_plan':15,'no_executed_position':59,'stored_data_or_contract_failure':5,'price_or_session_evidence_quarantined':3}}}},
        'performance_evidence_quarantine':{'quarantined_count':4},
        'legacy_evidence_revisions':{'approved_scope_count':76,'revisions':5,'terminal_scope_count':5,'awaiting_maturity_count':71,'mature_unscored_scope_count':0,'revision_state_counts':{'no_trade':5}}}
    script='const window={};\n'+(static/'performance_panel.js').read_text()+'\nconst payload='+json.dumps(fixture)+';const summaryEl={},listEl={};window.StockAgentPerformancePanel.render(payload,{summaryEl,listEl,escapeHtml:v=>String(v)});console.log(JSON.stringify({summary:summaryEl.textContent,html:listEl.innerHTML}));'
    rendered=json.loads(subprocess.run([node,'-e',script],capture_output=True,text=True,check=True).stdout)
    assert '描述性命中率 N/A' in rendered['html'] and '平均 ROI N/A' in rendered['html']
    assert '0.00%' not in rendered['html']
    assert '共 166' in rendered['summary'] and '舊資料或契約未通過 5、證據隔離 3' in rendered['summary']
    assert '全歷史價格／交易日證據隔離 4' in rendered['summary']
    assert '已完成 5 筆、待成熟 71 筆、已到期待補證 0 筆' in rendered['summary']
    assert '版本未代換上列原始績效' in rendered['summary']


@pytest.mark.parametrize('phase,reports,slots', [('before', 921, 1842), ('after', 915, 1830)])
def test_retention_scope_notice_does_not_present_cross_round_counts_as_improvement(phase, reports, slots):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js required for panel contract')
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / 'tests/fixtures/performance_retention_six_reports.json').read_text())
    population = dict(fixture[phase], denominator_semantics={'kind': 'surviving_indexed_reports', 'retention_days': 30})
    payload = {'population': population, 'legacy_evidence_revisions': {
        'approved_scope_count': 76, 'revisions': 5, 'terminal_scope_count': 5,
        'awaiting_maturity_count': 71, 'mature_unscored_scope_count': 0, 'revision_state_counts': {'no_trade': 5}}}
    script = 'const window={};\n' + (root / 'backend/static/performance_panel.js').read_text()
    script += '\nconst payload=' + json.dumps(payload) + ';const summaryEl={},listEl={};window.StockAgentPerformancePanel.render(payload,{summaryEl,listEl,escapeHtml:v=>String(v)});console.log(JSON.stringify({summary:summaryEl.textContent}));'
    text = json.loads(subprocess.run([node, '-e', script], capture_output=True, text=True, check=True).stdout)['summary']
    assert f'現存索引預期 {slots} 筆' in text
    assert f'仍存索引的 {reports} 份台股 v4 報告' in text
    assert '交易日基準 2026-10-02（台北）' in text and '保留 30 天' in text
    assert '到期清理會縮小母體' in text and '不是固定完整歷史研究母體' in text
    assert '跨期變動不代表策略改善' in text
    assert '待成熟 71 筆、已到期待補證 0 筆' in text and '未驗證策略' in text


@pytest.mark.parametrize('days,label', [(None, '保留期限未確認'), (0, '到期清理已停用')])
def test_scope_notice_never_invents_retention_for_old_or_disabled_payload(days, label):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js required for panel contract')
    root = Path(__file__).resolve().parents[1]
    payload = {'population': {'status': 'complete_index', 'as_of': '2026-10-02', 'report_count': 1, 'expected_slots': 2}}
    if days is not None:
        payload['population']['denominator_semantics'] = {'retention_days': days}
    script = 'const window={};\n' + (root / 'backend/static/performance_panel.js').read_text()
    script += '\nconst summaryEl={},listEl={};window.StockAgentPerformancePanel.render(' + json.dumps(payload) + ',{summaryEl,listEl,escapeHtml:v=>String(v)});console.log(summaryEl.textContent);'
    text = subprocess.run([node, '-e', script], capture_output=True, text=True, check=True).stdout
    assert label in text and '保留 30 天' not in text and '到期清理會縮小母體' not in text
