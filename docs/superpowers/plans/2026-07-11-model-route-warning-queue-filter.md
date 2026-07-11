# 模型路由警示待辦過濾 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 `slow_route` 與 `retry_storm` 保留在維運遙測中，但不再進入「今日待處理」、watchlist 今日工作台或通知計畫。

**Architecture:** 在 `daily_decision_queue` 的模型路由警示轉換邊界加入非待辦警示集合，只阻擋兩種純效能警示。`model_route_budget` 仍產生完整 warnings；下游首頁、watchlist 與通知繼續共用過濾後的 decision queue，因此數量與內容保持一致。

**Tech Stack:** Python 3.13、pytest、FastAPI dashboard aggregation

## Current Status

此計畫的 queue policy 已在目前工作樹落地，並完成 focused 與 live 8080 projection 驗證。`model_route_budget` 仍保留完整 `slow_route` / `retry_storm` 維運警示；frontstage decision queue、watchlist 工作台與通知來源只接收可行動 warning。因工作樹含其他既有變更，本計畫不 stage 或 commit。

---

## File Map

- Modify: `backend/daily_decision_queue.py` — 決定哪些 model route warnings 能進入 operator decision queue。
- Modify: `tests/test_daily_decision_queue.py` — 鎖住兩種警示被排除、品質警示仍保留，以及既有排序契約。
- Verify only: `tests/test_model_route_budget.py` — 證明底層仍產生完整 route warnings。
- Verify only: `tests/test_daily_decision_dashboard.py`、`tests/test_free_notification_plan.py`、`tests/test_static_history_filters.py` — 證明 dashboard、通知與前端契約未被破壞。

### Task 1: 過濾非待辦模型路由警示

**Files:**
- Modify: `tests/test_daily_decision_queue.py:355`
- Modify: `backend/daily_decision_queue.py:14-20`
- Modify: `backend/daily_decision_queue.py:167-170`

- [x] **Step 1: 更新既有排序案例並加入失敗測試**

將既有排序案例中的 route warning 改為仍需顯示的品質警示：

```python
{"id": "quality_gate_failures", "route": "v2/gemini-2.5-pro", "message": "quality_gate_failures=1"}
```

在該案例後新增：

```python
def test_daily_decision_queue_excludes_latency_and_retry_route_warnings():
    queue = build_daily_decision_queue(
        reports=[],
        repair_items=[],
        rerun_reports=[],
        high_priority_watchlist=[],
        candidates=[],
        performance={"summary": {}, "details": []},
        free_mode={"enabled": True, "can_run_without_paid_keys": True, "violations": []},
        ops={
            "model_route_budget": {
                "warnings": [
                    {"id": "slow_route", "route": "v1/gemini-3.5-flash", "message": "p95_latency_ms=399974"},
                    {"id": "retry_storm", "route": "v2/gemma-4-31b-it", "message": "retry_count=7"},
                    {
                        "id": "quality_gate_failures",
                        "route": "v3/gemini-3.5-flash",
                        "message": "quality_gate_failures=1",
                    },
                ]
            }
        },
    )

    assert queue["summary"]["total_actionable"] == 1
    assert queue["summary"]["sources"] == {"model_route_budget": 1}
    assert [item["warning_id"] for item in queue["items"]] == ["quality_gate_failures"]
    assert queue["items"][0]["type"] == "model_route_warning"
```

- [x] **Step 2: 執行新測試並確認紅燈**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_daily_decision_queue.py::test_daily_decision_queue_excludes_latency_and_retry_route_warnings \
  -q
```

Expected: FAIL；目前 queue 仍包含三筆 route warnings，`total_actionable` 會是 `3` 而不是 `1`。

- [x] **Step 3: 實作最小過濾**

在 `SOURCE_ORDER` 後加入：

```python
NON_ACTIONABLE_ROUTE_WARNING_IDS = frozenset({"slow_route", "retry_storm"})
```

將 `_route_warning_items()` 改為：

```python
def _route_warning_items(ops: dict[str, Any]) -> list[dict[str, Any]]:
    raw_budget = _field(ops, "model_route_budget")
    budget = raw_budget if isinstance(raw_budget, dict) else {}
    return [
        _route_warning_payload(warning)
        for warning in _field(budget, "warnings") or []
        if isinstance(warning, dict)
        and str(_field(warning, "id") or "model_route_warning") not in NON_ACTIONABLE_ROUTE_WARNING_IDS
    ]
```

- [x] **Step 4: 執行 queue 測試並確認綠燈**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_daily_decision_queue.py -q
```

Expected: PASS，沒有 failure 或 error。

- [x] **Step 5: 驗證底層 warnings 與下游契約**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_model_route_budget.py \
  tests/test_daily_decision_dashboard.py \
  tests/test_free_notification_plan.py \
  tests/test_static_history_filters.py \
  -q
```

Expected: PASS。`test_model_route_budget_flags_retry_storm_and_slow_routes` 仍證明維運層產生 `retry_storm` 與 `slow_route`，但 decision queue 不再呈現它們。

- [x] **Step 6: 驗證目前資料的投影結果**

Run:

```bash
$(scripts/project_python.sh) - <<'PY'
import json
import sys
from urllib.request import urlopen

sys.path.insert(0, "backend")
from daily_decision_queue import _route_warning_items

ops = json.load(urlopen("http://127.0.0.1:8080/api/observability/dashboard"))
items = _route_warning_items(ops)
blocked = {"slow_route", "retry_storm"}
assert not blocked.intersection(item["warning_id"] for item in items)
print({"remaining_route_warning_ids": sorted({item["warning_id"] for item in items})})
PY
```

Expected: 輸出中的 `remaining_route_warning_ids` 不包含 `slow_route` 或 `retry_storm`；若目前沒有品質警示，可能是空清單。

- [x] **Step 7: 檢查 diff 並保留工作樹邊界**

```bash
git diff --check -- backend/daily_decision_route_warnings.py backend/daily_decision_queue.py tests/test_daily_decision_queue.py
```

結果：差異檢查通過；未 stage/commit，避免把工作樹其他既有變更納入本計畫。
