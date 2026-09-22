"""Exercise the real browser renderers in Node without a browser or runtime API."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_execution_labels_and_terminal_ui_do_not_claim_waiting_is_running():
    node=shutil.which('node')
    if not node: pytest.skip('Node unavailable')
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
global.window={};
for (const path of process.argv.slice(1)) vm.runInThisContext(fs.readFileSync(path,'utf8'));
const labels=window.StockAgentJobExecutionLabels;
assert.equal(labels.label({execution_state:'terminal_quality'}),'品質檢查未通過，已停止');
assert.match(labels.label({execution_state:'waiting_retry',execution_health:'unknown'}),/等待重試.*待確認/);
assert.match(labels.details({execution_reason_code:'worker_heartbeat_stale'}),/心跳過久.*核對/);
assert.match(labels.details({execution_reason_code:'registry_missing'}),/找不到佇列紀錄/);
assert.match(labels.details({stall_assessment:'suspected_stall',registry:{state:'unknown'}}),/疑似停滯，需核對.*僅依更新時間.*unknown/);
let summary={textContent:''},list={innerHTML:''};
window.StockAgentActiveJobsPanel.render({jobs:[{status:'waiting_retry',execution_state:'waiting_retry',execution_health:'normal',execution_reason_code:'cooldown',retry_at:'2030-01-01T00:00:00Z',registry:{state:'scheduled'},ticker:'T'}]}, {summaryEl:summary,listEl:list,escapeHtml:String});
assert.match(summary.textContent,/未結束任務/);assert.match(list.innerHTML,/等待重試/);assert.match(list.innerHTML,/冷卻中/);assert.match(list.innerHTML,/scheduled/);
let closed=0;global.setTimeout=()=>{};
const options={loadingStatus:{},loadingMsg:{},close:()=>closed++,switchView:()=>{}};
const stream=window.StockAgentAnalysisStreamEvents.create(options);
stream.handle({type:'status',phase:'workflow_retry',retry_scheduled:true,message:'已保留進度'},'T');
assert.equal(options.loadingStatus.textContent,'等待模型恢復後重試');assert.equal(closed,0);
stream.handle({type:'error',phase:'report_quality_blocked',message:'無效來源'},'T');
assert.equal(options.loadingStatus.textContent,'品質檢查未通過，任務已停止');assert.equal(closed,1);
'''
    paths=[ROOT/'backend/static'/name for name in ('job_execution_labels.js','active_jobs_panel.js','analysis_stream_events.js')]
    subprocess.run([node,'-e',script,*map(str,paths)],check=True,capture_output=True,text=True)


@pytest.mark.parametrize('pipeline', ['v1', 'v2', 'v3', 'v4'])
def test_rerun_display_uses_source_report_identity_without_mutating_job(pipeline):
    node = shutil.which('node')
    if not node: pytest.skip('Node unavailable')
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
global.window={};
for (const path of process.argv.slice(2)) vm.runInThisContext(fs.readFileSync(path,'utf8'));
const mode=process.argv[1], labels={v1:'模式 A',v2:'模式 B',v3:'模式 C',v4:'模式 D'};
const panel=window.StockAgentActiveJobsPanel;
function render(job) {
 const summary={textContent:''},list={innerHTML:''},original=JSON.stringify(job);
 panel.render({jobs:[job]}, {summaryEl:summary,listEl:list,escapeHtml:String,pipelineModeLabel:p=>labels[p]||'模式 A'});
 assert.equal(JSON.stringify(job),original);
 return list.innerHTML;
}
for (const suffix of ['job_37d4255d2b0d', '20260922_231526']) {
 const filename=`2305_TW_${mode}_report_${suffix}.html`;
 const html=render({ticker:filename,pipeline_id:'rerun:full_report',status:'waiting_retry',execution_state:'waiting_retry'});
 assert.match(html,/2305\.TW/);assert.ok(html.includes(labels[mode]));
 assert.ok(!html.includes(filename));assert.match(html,/等待重試/);
 const otc=render({ticker:`5314_TWO_${mode}_report_${suffix}.html`,pipeline_id:'rerun:final_report',status:'running'});
 assert.match(otc,/5314\.TWO/);assert.ok(otc.includes(labels[mode]));
}
for (const filename of ['../2305_TW_v4_report_job_37d4255d2b0d.html', '2305_TW_v5_report_job_37d4255d2b0d.html', '2305_TW_report_20260922_231526.html', '2305_TW_v4_report_job_bad.html', '<img src=x onerror=alert(1)>', '2305_TW_v4_report_job_37d4255d2b0d.html/extra']) {
 const html=render({ticker:filename,pipeline_id:'rerun:full_report',status:'running'});
 assert.match(html,/來源股票未知/);assert.match(html,/模式未知/);assert.ok(!html.includes('模式 A'));
}
const ordinary=render({ticker:'2305.TW',pipeline_id:mode,status:'running'});
assert.match(ordinary,/2305\.TW/);assert.ok(ordinary.includes(labels[mode]));
assert.match(render({ticker:'2305.TW',pipeline_id:'unrecognized',status:'running'}),/模式未知/);
'''
    paths = [ROOT/'backend/static'/name for name in ('job_execution_labels.js', 'active_jobs_panel.js')]
    subprocess.run([node, '-e', script, pipeline, *map(str, paths)], check=True, capture_output=True, text=True)
