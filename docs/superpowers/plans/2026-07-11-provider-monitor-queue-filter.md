# Provider 非阻斷監控待辦過濾 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留完整 provider impact ledger，但讓 non-blocking `monitor_provider` 不再進入 operator decision queue。

**Architecture:** 過濾放在 `daily_decision_queue._provider_items()` 的 ledger-to-action 邊界，以 `blocks_auto_rerun` 決定是否建立待辦。Blocking `wait_provider_recovery` 繼續輸出；首頁、watchlist 與通知沿用同一份 filtered queue。

**Tech Stack:** Python 3.13、pytest、FastAPI dashboard aggregation

## Current Status

此計畫的 provider ledger-to-queue policy 已在目前工作樹落地，並完成 focused 與 live 8080 projection 驗證。ledger 保留 non-blocking monitor context；decision queue、watchlist 工作台與通知只呈現 blocking provider recovery。因工作樹含其他既有變更，本計畫不 stage 或 commit。

---

## File Map

- Modify: `backend/daily_decision_queue.py` — 只把 blocking provider impact 轉成 operator action。
- Modify: `tests/test_daily_decision_queue.py` — 鎖住 non-blocking monitor 被排除、blocking recovery 被保留。
- Verify only: `tests/test_provider_impact.py` — 證明 ledger 仍產生 `monitor_provider`。
- Verify only: `tests/test_daily_decision_dashboard.py`、`tests/test_free_notification_plan.py`、`tests/test_static_history_filters.py` — 證明下游契約一致。

### Task 1: 排除 non-blocking provider monitor

**Files:**
- Modify: `tests/test_daily_decision_queue.py:464`
- Modify: `backend/daily_decision_queue.py:88-111`

- [x] **Step 1: 新增失敗測試**

在 provider impact queue tests 前加入：

```python
def test_daily_decision_queue_excludes_nonblocking_provider_monitor():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        provider_impact_ledger={
            "items": [
                {
                    "ticker": "2324.TW",
                    "filename": "2324_monitor.html",
                    "summary": {
                        "recommended_action": "monitor_provider",
                        "blocks_auto_rerun": False,
                    },
                    "impacts": [{"message": "本次抓取健康，列為監控提醒。"}],
                },
                {
                    "ticker": "NVDA",
                    "filename": "nvda_blocked.html",
                    "summary": {
                        "recommended_action": "wait_provider_recovery",
                        "blocks_auto_rerun": True,
                    },
                    "impacts": [{"message": "核心來源暫時不可用。"}],
                },
            ]
        },
    )

    assert queue["summary"]["total_actionable"] == 1
    assert queue["summary"]["sources"] == {"provider_impact": 1}
    assert [item["ticker"] for item in queue["items"]] == ["NVDA"]
    assert queue["items"][0]["type"] == "wait_provider_recovery"
    assert queue["items"][0]["blocks_auto_rerun"] is True
```

- [x] **Step 2: 執行新測試並確認紅燈**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_daily_decision_queue.py::test_daily_decision_queue_excludes_nonblocking_provider_monitor \
  -q
```

Expected: FAIL；目前 queue 仍包含 `2324.TW` 與 `NVDA`，`total_actionable` 是 `2`。

- [x] **Step 3: 實作最小過濾**

在 `_provider_items()` 取得 `blocks_auto_rerun` 後，先排除 non-blocking row：

```python
blocks = bool(_field(summary, "blocks_auto_rerun"))
if not blocks:
    continue
action = str(_field(summary, "recommended_action") or "wait_provider_recovery")
```

其餘 blocking payload、優先序與 filename 行為保持不變。

- [x] **Step 4: 執行 queue 與 ledger 測試**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_daily_decision_queue.py \
  tests/test_provider_impact.py \
  -q
```

Expected: PASS。Queue 排除 non-blocking monitor；provider impact tests 仍證明 ledger 產生 `monitor_provider`。

- [x] **Step 5: 驗證下游與完整套件**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_daily_decision_dashboard.py \
  tests/test_free_notification_plan.py \
  tests/test_static_history_filters.py \
  -q

$(scripts/project_python.sh) -m pytest -q
```

Expected: 全部 PASS，沒有 failure 或 error。

- [x] **Step 6: 重啟正式 runtime 並驗證 live projection**

使用原本 LAN 模式重新啟動 `start_mac.command` 後，執行：

```bash
curl -fsS http://127.0.0.1:8080/api/watchlist/daily-dashboard | \
$(scripts/project_python.sh) -c '
import json, sys
payload = json.load(sys.stdin)
queue = payload.get("decision_queue") or {}
items = queue.get("items") or []
assert not any(item.get("type") == "monitor_provider" for item in items)
assert all(
    item.get("type") != "wait_provider_recovery" or item.get("blocks_auto_rerun") is True
    for item in items
)
ledger = payload.get("provider_impact_ledger") or {}
assert int((ledger.get("summary") or {}).get("monitor_reports") or 0) >= 1
print({"queue_sources": (queue.get("summary") or {}).get("sources"), "ledger_summary": ledger.get("summary")})
'
```

Expected: Queue 不含 `monitor_provider`，但 live ledger 仍有 `monitor_reports`。

- [x] **Step 7: 檢查變更範圍**

```bash
git diff --check -- backend/daily_decision_queue.py tests/test_daily_decision_queue.py
```

Expected: 無 whitespace error；不 stage 或 commit 這兩個原本未追蹤、含既有使用者工作的檔案。
