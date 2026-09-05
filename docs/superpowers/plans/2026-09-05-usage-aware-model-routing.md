# 每日用量納入模型路由與容量保護 Implementation Plan

> **For agentic workers:** 使用 executing-plans 在本次工作內逐項實作與驗證。

**Goal:** 依 canonical 每日用量評估免費模型，改善長輸入與 429 重試，保留報告品質門檻。

**Architecture:** 用量統計留在 operational ledger 的唯讀 service；安全配額解析留在 LLM error helper；單次容量檢查在呼叫前執行，超限只跳過當次模型路由，不停用所有 key 或截掉證據。候選模型經小量測試才調整設定。

**Tech Stack:** Python / SQLite / Google GenAI / FastAPI / pytest。

## 範圍與決策

- 使用者已同意前輪的分工方向，並要求先加入每日用量再修改。
- 比較方案：全換最新模型（未知額度與品質風險高）；只降速（無法解決單次超限）；採每日需求評估、容量保護與分工式更換（本次採用）。
- 不啟用付費，不增加 key/project，不重建既有報告，不降低 evidence/conformance gate。
- 供應商 quota 與本機操作預算是不同欄位；未知值保持未知。
- 日期統計包含台北工作日與 Pacific 配額日；今天不混入完整日平均；token 缺值不冒充零用量。
- 既有 dirty files 均保留，本次不自動提交或推送混合變更。

## Task 1: 每日需求統計

狀態：已完成。新增測試先紅後綠，canonical ledger 已按台北日與 Pacific 日重算。

- [x] 在 `tests/test_llm_daily_usage.py` 先建立 SQLite fixtures，測試 request/planned/response 不重複計數、供應商與本機錯誤分流、缺 token、時區與完整日平均。
- [x] 執行 `"$(scripts/project_python.sh)" -m pytest tests/test_llm_daily_usage.py -q`，確認缺少 daily profile 的失敗。
- [x] 新增 `backend/llm_daily_usage.py`，在 `backend/api_usage_store.py` 提供 reader，將結果加入 `backend/api_quota_service.py`。只輸出匿名彙整，不輸出 prompt/key/project。
- [x] 同一測試轉綠，對 live ledger 輸出日期、請求、錯誤、input token 分位數與覆蓋率。

## Task 2: 安全配額資訊與單次容量

狀態：已完成。配額解析、單次輸入保護與 sync/async 備援路由已通過回歸。

- [x] 在 `tests/test_llm_input_capacity.py` 及 `tests/test_llm_quota_details.py` 測試過大輸入立即拒絕、sync/async 一致、quota JSON 字串解析、多限制與敏感欄位排除。
- [x] 先執行新增測試確認失敗，再實作獨立 helper 與現有呼叫流程的整合。
- [x] 配額違規僅保存白名單化的種類、數值、model、retry delay；本機 input budget 失敗不變成 RPD/帳號失效，也不進相同輸入的重試循環。
- [x] 輸入容量計算與輸出 reserve 分開；保留既有 context evidence，不新增任意中段截斷。
- [x] 回歸 `test_llm_errors.py`、`test_llm_model_policy.py`、`test_shared_runtime_guards.py`、`test_llm_rate_limit_buckets.py`、`test_llm_call_diagnostics.py`。

## Task 3: 候選與模型設定

狀態：已完成。採用通過用途檢查的 Lite 摘要與 3.8 決策；3.7 與一般分析全面換模未採用。

- [x] 核對 Google 官方價格與模型限制，候選為 3.5 Flash-Lite、3.7 Flash、3.8 Flash。
- [x] 單一匿名 slot、順序執行、無 SDK 自動重試，使用固定資料與現有 generation/schema 路徑作小量測試；測試用量另記 diagnostic，不混作日常成功率。
- [x] 只讓通過該用途測試的模型接手相應路由；未通過者不上線，embedding 保留。
- [x] 對 4 模式的 schema、模板與圖表現有測試回歸，不宣稱 smoke 等同完整報告品質驗證。

## Task 4: 部署與交付

狀態：已完成。1401 項受影響回歸通過，受控重啟、live API、runtime doctor 與桌面 / 手機用量面板驗證完成。完整證據見 `docs/usage-aware-model-routing-2026-09-05.md`。

- [x] 跑受影響測試、runtime/settings 必跑測試與 diff 檢查。
- [x] 盤點 active jobs，使用正式 launcher 的受控重啟流程，不清空 queue/checkpoint。
- [x] 以新 API payload、載入路由與 runtime doctor 確認變更生效；記錄限制與剩餘額度未確認項目。

驗收：每日量可重算；本機攔截不冒充 provider 429；過大輸入不無限等待；未驗證的新模型不替換正式分析；原報告與品質 gate 不變。
