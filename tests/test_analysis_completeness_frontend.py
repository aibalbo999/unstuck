import json
import subprocess
from pathlib import Path


def test_preview_and_history_expose_completeness_without_hiding_quality_warning():
    static = Path(__file__).resolve().parents[1] / 'backend' / 'static'
    script = r'''
global.window = {StockAgentReportQualityPolicy: {dataTrustStatus: () => 'fresh'}};
require(PREVIEW); require(HISTORY);
const e = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
const report = {analysis_completeness:{status:'degraded',summary:'<script>unsafe</script>'}};
const preview = window.StockAgentReportPreviewHelpers.reportQualityBadge(report,e);
const history = window.StockAgentHistoryPanelQualityHelpers.reportActionBadge(report,e);
if (!preview.includes('資料不足降級') || !history.includes('資料不足降級')) throw Error('degradation hidden');
if (history.includes('可直接使用')) throw Error('degraded analysis mislabeled usable');
if (preview.includes('<script>') || history.includes('<script>')) throw Error('unescaped summary');
window.StockAgentReportQualityPolicy.reportQualityGateAction = () => ({label:'既有品質警告',tone:'warning',detail:'keep'});
if (!window.StockAgentReportPreviewHelpers.reportQualityBadge(report,e).includes('既有品質警告')) throw Error('gate warning hidden');
for (const [status,label] of Object.entries({complete:'分析完整',observation:'正常觀望',degraded:'資料不足降級',quality_warning:'分析品質警告'})) {
  const text = window.StockAgentReportPreviewHelpers.reportAnalysisCompletenessBadge({analysis_completeness:{status,quality_warning:true}},e);
  if (!text.includes(label)) throw Error('missing '+status);
}
if (!window.StockAgentReportPreviewHelpers.reportAnalysisCompletenessBadge({analysis_completeness:{status:'unknown'}},e).includes('完整度未確認')) throw Error('unknown promoted');
'''.replace('PREVIEW', json.dumps(str(static / 'report_preview_helpers.js'))).replace('HISTORY', json.dumps(str(static / 'history_panel_quality_helpers.js')))
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
