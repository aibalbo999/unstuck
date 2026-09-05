# 模型使用效益優化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按使用者指定的 16 個獨立免費專案假設，落實每日預算、減少失敗重試、分散備援負載；不增加並行、不更換 key、不降報告品質門檻。

**Architecture:** KeyRotator 在取得分鐘額度後，以 canonical operational SQLite 原子保留每日請求預算；用 hash 隔離 key/model，Pacific 日切換，初始化納入現有匿名請求紀錄。沿用現有延後/備援流程，區分本機攔截與供應商 429。路由 profile 是配置來源，API 顯示實際載入的預算。

**Tech Stack:** Python、SQLite WAL、pytest、既有 Redis/RQ 與 macOS launcher。

## 1. 每日預算
- [x] 建立 `tests/test_llm_daily_budget.py`：重啟持續、跨連線競爭、Pacific/DST 日切換、歷史初始化一次、hash 不含 key、sync/async、分鐘等待不消耗、容量預檢不消耗、DB 失敗停止送出。
- [x] 執行 `$(scripts/project_python.sh) -m pytest tests/test_llm_daily_budget.py -q`，確認 RED。
- [x] 新增 `backend/llm_daily_budget.py`，整合 `backend/llm_rate_limits.py`，原子 SQL 核心：`UPDATE llm_daily_budgets SET used=used+1 WHERE quota_day=? AND model_id=? AND key_hash=? AND used<?`。
- [x] 本機預算錯誤整合 retry 與 daily ledger 分類，不發布供應商全 key 熔斷。
- [x] 重跑上述測試確認 GREEN。

## 2. 模型效率配置
- [x] `tests/test_usage_aware_model_routes.py` 增加 80% RPD、TPM、備援分散斷言；`tests/test_llm_model_policy.py` 增加 opt-in retry cap 不宣稱全 key 耗盡的案例。
- [x] 更新 profile 與 allowlisted `.env`：3.8/Preview/3.6 各 16 RPD，Lite 400，Gemma 11520，Embedding 800；TPM Gemini 200000、Gemma 16000、Embedding 24000。
- [x] `backend/settings/models.py` 載入 profile retry cap；`model_policy.py` 以 4 次 quota 失敗切換，server 失敗以 profile 2 次切換，保留其他 profile 既有預設。
- [x] 一般分析的偶數 Agent 優先 3.6、奇數優先 Preview；決策只使用既有驗證的模型。不要截斷證據以強迫使用 Gemma。

## 3. Embedding 與可觀測性
- [x] 新增 embedding 分批測試，每批估計輸入不超過 24000；保留索引、快取及 async 對齊，單筆過大維持明確拒絕。
- [x] 修改 `backend/rag_runtime/embeddings.py` 以 token batch 迭代原有 API/快取合併流程。
- [x] `backend/api_quota_service.py` 顯示 RPD 執行狀態、16 專案假設及當日剩餘本機預算，不冒稱 Google 實際剩餘。

## 4. 交付驗證
- [x] 執行每日預算、重試、RAG、settings/storage/runtime、API、報告模板/圖表/品質回歸；檢查 diff/語法。最終隔離整合回歸 1507 passed，工具/預算/embedding/model policy/transport 113 passed 且 warning-as-error。
- [x] 確認工作與 RQ 為空，保存 Redis RDB，再以正式 `start_mac.command` 重啟 API/Worker，保持 LAN_ACCESS=1；RDB 載回 634 筆、到期 0 筆。
- [x] runtime doctor、8080 API 與已載入設定驗證。正式 API 已回傳 RPD enforcement、完整 RPM/TPM/RPD map 與 daily budget；歷史 ledger 不完整、外部使用無法扣帳、3 倍尖峰不保證完成。
- [x] 更新交付說明；本輪不自行 commit/push，不動既有報告與無關 dirty files。

2026-09-05：另一個同 checkout 任務「分析4種模式邏輯優化空間」完成整合驗證後解除重啟等待；本任務於台北 23:13 完成唯一一次受控重啟與 live 驗證。

## 獨立審查後補強
- [x] embedding 後續批次失敗時保留已掛入的快取與成功向量；新增 sync/async 與 provider quota/local budget 拒絕四個 RED/GREEN 案例，embedding/RAG 共 18 passed。
- [x] SDK 工具迴圈的每次後續請求，依包含工具結果的 request input 執行原 key/model 分鐘限流；使用公開 SDK/HTTPX hooks，不關閉工具或重寫工具引擎。首輪不 double-count，RPD 已預留 6 筆不重複扣。
- [x] 新增工具限流後，完成 isolated transport 測試、獨立審查及 scoped 回歸，並向另一任務發送「模型效率修補可重啟」；獨立審查兩項 P2 均 resolved。
