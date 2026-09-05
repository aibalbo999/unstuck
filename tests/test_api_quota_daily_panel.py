import json
from pathlib import Path
import subprocess


def test_daily_panel_uses_provider_errors_and_keeps_local_blocks_separate():
    static = Path(__file__).resolve().parents[1] / "backend" / "static"
    script = """
global.window = {};
require(PANEL);
try { require(HELPER); } catch (error) { if (error.code !== 'MODULE_NOT_FOUND') throw error; }
const summaryEl = {}, listEl = {};
window.StockAgentApiQuotaPanel.render({ services: [{service:'Gemini / Google AI', configured:true, usage: {
 observed_calls_since_reset:10, observed_quota_errors_since_reset:30,
 daily_profile:{today:{requests:1517},complete_days:{count:13,average_requests:332.1,peak_requests:628}},
 quota_day_profile:{today:{requests:10,provider_quota_errors:1,local_blocks:3,other_errors:2,unclassified_quota_errors:0}}
}}]}, {summaryEl,listEl,escapeHtml: value=>String(value ?? '')});
process.stdout.write(JSON.stringify(listEl));
""".replace("PANEL", json.dumps(str(static / "api_quota_panel.js"))).replace("HELPER", json.dumps(str(static / "api_quota_usage_helpers.js")))
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    html = json.loads(result.stdout)["innerHTML"]
    assert "今日 1517 次" in html
    assert "日均 332.1 次" in html
    assert "供應商配額錯誤 1 次" in html
    assert "本機攔截 3 次" in html
    assert "額度錯誤 30 次" not in html
    assert "Pacific 配額日請求紀錄 10 次" in html
    assert "已送出" not in html


def test_daily_budget_label_is_explicitly_local_and_keeps_zero_remaining():
    helper = Path(__file__).resolve().parents[1] / 'backend/static/api_quota_usage_helpers.js'
    script = "global.window={};require(HELPER);process.stdout.write(window.StockAgentApiQuotaUsage.budgetLabel({available:true,models:{flash:{remaining:0,total_budget:256}}}));".replace('HELPER', json.dumps(str(helper)))
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
    assert '本機剩餘' in result.stdout
    assert 'flash 0/256' in result.stdout
    assert 'Google 剩餘' not in result.stdout


def test_quota_api_exposes_enforced_budget_not_provider_entitlement(monkeypatch):
    import api_quota_service as service
    monkeypatch.setattr(service, 'API_KEYS', ['a', 'b'])
    monkeypatch.setattr(service, 'RPD_LIMITS', {'m': 16})
    payload = service.build_api_quota_payload(lambda _: [])
    assert payload['model_policy']['rpd_enforcement'] == 'atomic_sqlite_per_key_model_pacific_day'
    assert payload['model_policy']['rpd_limits'] == {'m': 16}
    assert payload['model_policy']['provider_limits_verified'] is False
    assert payload['services'][0]['usage']['daily_budget']['models']['m']['remaining'] == 32
