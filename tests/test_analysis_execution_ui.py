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
