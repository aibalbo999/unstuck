"""Render Neutral provenance beside, never instead of, existing quality badges."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_node(body):
    script = "global.window={}; const root=process.argv[1]; require(root+'/backend/static/history_neutral_reason.js');\n" + body
    return json.loads(subprocess.run(['node', '-e', script, str(ROOT)], check=True,
                                    capture_output=True, text=True).stdout)


def test_compact_reason_distinguishes_original_neutral_rejection_and_age():
    result = run_node(r'''
const report={pipeline_id:'v4', neutral_explanation:{category:'source_rejection',label:'引用／語意退件',
 summary:'模型原先已選 Neutral；另有退件', original_direction:'Neutral',direction_changed_by_gate:false},
 analysis_age:{analysis_generated_at:'2026-09-23',age_calendar_days:30,over_14_calendar_days:true,conclusion_stale:true}};
process.stdout.write(JSON.stringify({html:window.StockAgentHistoryNeutralReason.render(report)}));
''')
    assert '引用／語意退件' in result['html']
    assert '原已 Neutral' in result['html']
    assert '分析距今 30 日' in result['html']
    assert '超過 14 日' in result['html']
    assert '資料已更新，結論未同步' in result['html']


def test_detail_preserves_original_direction_and_escapes_saved_text():
    result = run_node(r'''
const report={pipeline_id:'v4',neutral_explanation:{category:'source_rejection',label:'引用／語意退件',
 summary:'原 Long 未通過',original_direction:'Long',direction_changed_by_gate:true,
 evidence:[{field:'core_catalyst',text:'<img src=x onerror=alert(1)>'}]}};
process.stdout.write(JSON.stringify({html:window.StockAgentHistoryNeutralReason.render(report,undefined,{detailed:true})}));
''')
    assert '原 Long → Neutral' in result['html']
    assert '&lt;img' in result['html'] and '<img' not in result['html']
    assert '原因分類不代表品質通過' in result['html']


def test_missing_age_does_not_claim_today_and_other_modes_are_unchanged():
    result = run_node(r'''
const helper=window.StockAgentHistoryNeutralReason;
process.stdout.write(JSON.stringify({unknown:helper.render({pipeline_id:'v4',analysis_age:{age_calendar_days:null}}),
 other:helper.render({pipeline_id:'v1',neutral_explanation:{label:'fake'},analysis_age:{age_calendar_days:1}})}));
''')
    assert '分析時間未確認' in result['unknown']
    assert '今日' not in result['unknown']
    assert result['other'] == ''


def test_history_and_preview_both_render_new_payload_without_removing_quality_badges():
    result = run_node(r'''
const render=window.StockAgentHistoryNeutralReason.render;
let calls=[];window.StockAgentHistoryNeutralReason.render=(r,e,o)=>{calls.push(o||{});return render(r,e,o)};
const helper=new Proxy({},{get:()=>()=>''});
require(root+'/backend/static/history_panel_renderers.js');
const panel=window.StockAgentHistoryPanelRenderers.create({helpers:helper,renderDataTrustBadge:()=>'<span>資料品質原標示</span>'});
const report={ticker:'X',filename:'x.html',pipeline_id:'v4',neutral_explanation:{category:'model_incomplete',label:'模型結論未完成',summary:'本機備援'},analysis_age:{age_calendar_days:2}};
const html=panel.renderHistoryList([report]);
window.StockAgentReportPreviewHelpers={legacyPreview:()=>({}),reportQualityBadge:()=>'<span>品質原標示</span>',renderMetrics(){},reportReadingNotice:()=>''};
window.StockAgentReportPreviewTrackingHelpers={renderTracking(){}};
window.StockAgentReportPreviewRerunHelpers={configureRerunButtons(){}};
require(root+'/backend/static/report_preview_panel.js');
const elt=()=>({innerHTML:'',textContent:'',hidden:false,querySelector(){return null}});
const elements={root:elt(),mode:elt(),title:elt(),summary:elt()};
const preview=window.StockAgentReportPreviewPanel.create({elements,renderPipelineModeBadge:()=>'',renderDataTrustBadge:()=>'',escapeHtml:String,pipelineMeta:{}});
preview.show(report);
process.stdout.write(JSON.stringify({html,preview:elements.mode.innerHTML,calls}));
''')
    assert '模型結論未完成' in result['html']
    assert '資料品質原標示' in result['html']
    assert '模型結論未完成' in result['preview']
    assert '品質原標示' in result['preview']


def test_reason_asset_loads_before_consumers():
    html = (ROOT / 'backend/static/index.html').read_text()
    assert html.index('/static/history_neutral_reason.js?') < html.index('/static/history_panel_renderers.js?')
    assert html.index('/static/history_neutral_reason.js?') < html.index('/static/report_preview_panel.js?')
