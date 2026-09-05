# 四模式分析邏輯優化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落實使用者核准的三批優化，讓未知值、不交易、交易價格、短線資料、摘要版本與模式回測保持一致且可驗證。

**Architecture:** 沿用現有 pipeline、structured outputs、final audit、content credibility 與 provider audit。新數值驗算與短線資料投影使用共用純函式；不以補造數字通過品質檢查，不改寫歷史報告。已有未提交變更屬既有工作，本次直接在現有 codex 分支增量修改，依檔案責任分工，完成後統一審查。

**Tech Stack:** Python、Pydantic、pytest、LangGraph、SQLite、既有 yfinance provider 與 HTML/Markdown renderer。

## 執行與驗證邊界

- 基準：`/Volumes/X10 Pro Mac/stock-agent`，起始 HEAD `ef876984`；起始已有 112 筆工作目錄變更。
- 測試統一使用 `"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py ... -q`，隔離 SQLite、Redis、網路及供應商；不觸發正式分析、不重建歷史產物。
- 各項先新增可重現失敗測試，再實作，最後完成既有回歸、規格審查與程式品質審查。
- 不把測試成功解讀為投資績效改善；不擅自提交混合工作、push 或重新部署。

## 第一批：數值與決策契約

### Task 1：護城河未知值

Files: `backend/structured_output_valuation_models.py`、`backend/structured_output_normalize_dispatch.py`、`backend/final_audit.py`、`backend/agent_runtime/structured_repair_contracts.py`、相關 parser/renderer；tests `tests/test_mode_moat_missing_values.py`。

- [x] 新增缺 scores、全部 null、部分 null、有效 1 分、非法數字、HTML/Markdown 顯示案例。
- [x] 觀察舊程式將未知變 1 的失敗，再保留 null/未評估；不把未評估當已完成評分。
- [x] 驗證有效評分保持原值，最終稽核辨識缺證據，不把 null 送入算術。

```python
def test_missing_moat_score_is_not_a_real_low_score():
    from structured_output_valuation_models import MoatScores
    result = MoatScores.model_validate({}).model_dump(by_alias=True)
    assert all(value is None for value in result.values())
```

### Task 2：交易驗算與不交易

Files: `backend/final_audit_mode_contracts.py`、`backend/reporting/content_credibility_trade_setup.py`、新 `backend/trade_execution_contract.py`、模式結構輸出相容層；tests `tests/test_trade_execution_contract.py`。

- [x] 新增 B 進場100/停損120/部位150%、C 放空100/目標120/停損90、D 進場115/目標110/停損95 的失敗案例。
- [x] 共用數值價格與範圍投影，依進場上下界檢查 long/short 價序、部位界線、風報比及明確成本假設；不得把日期、百分比當價格。
- [x] B 等待且0部位、D Neutral，以及 C 明確不建立空單可保留空價位；必須有等待理由/失效或重新檢查條件，不能讓 active trade 藉 placeholder 通過。
- [x] 通過合理突破 entry110–112/target125/stop105/current100；renderer、schema、final audit 使用同一不交易語意。

```python
def test_breakout_stop_uses_entry_not_spot():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment
    result = evaluate_trade_setup_alignment(trade_setup={
        "trade_direction": "Long", "entry_zone": "110-112",
        "target_price": "125", "stop_loss": "105",
    }, current_price=100)
    assert result["blocking_issues"] == []
```

## 第二批：資料與推理依賴

### Task 3：D 日線、技術與事件

Files: `backend/data_fetch/yfinance_enrichment_extractors.py` 及 provider payload/context、新 `backend/short_term_market_data.py`、`backend/prompt_builder.py`、`backend/prompts/agents.json`、相關 snapshot allowlist；tests `tests/test_short_term_market_data.py`。

- [x] 用確定的歷史 OHLCV fixture 證明至少60日均線、RSI14、MACD、ATR14、量能與日期可計算，資料不足保持 null。
- [x] 從既有 history fetch 同次結果提供最多120個交易日 OHLCV，不額外增加獨立網路抓取。
- [x] Agent22/24取得日線摘要與技術指標；Agent24取得未來14日事件、日期/來源/確認程度；既有月線展示維持相容。
- [x] 未來資料排除、舊事件不冒充未來事件；缺少OHLCV/事件時產生可用性說明。

### Task 4：摘要版本及依賴

Files: `backend/context_digest_runtime.py`、`backend/context_digest_tasks.py`、`backend/context_digest_payload.py`、`backend/assistant_context.py`、`backend/agent_runtime/repair_context.py` 及小型共用 dependency helper；tests `tests/test_context_digest_dependencies.py`。

- [x] 證明正文500字後、structured目標、Agent20/21證據改變都會使適用摘要版本改變。
- [x] 使用真實 pipeline groups 建立前序依賴，不用Agent編號大小；同群保持獨立，修復上游不讀下游結論。
- [x] 既有摘要只有版本相同才可沿用；legacy無版本摘要不可默認新鮮。修復後重新產生或移除過時摘要。
- [x] 前序structured輸出納入總預算，不讓長下游結論擠掉原始證據；保留既有不可序列化資料安全邊界。

## 第三批：模式一致性與成效

### Task 5：A/C 提示與避免語意

Files: `backend/prompts/agents.json`、`backend/forward_consistency_checker.py`、`backend/reporting/content_credibility_alignment.py`、相關 recommendation calibration；tests `tests/test_mode_reasoning_contracts.py`。

- [x] A保留既有帶建議研究的schema，移除禁止該schema允許值的矛盾指令；數值仍須有證據。
- [x] C仍檢查泡沫，但允許未發現泡沫；Agent21在C挑戰空方論點，最終分開高估、下跌催化、可建立空單。
- [x] 避免不是放空：上行潛力不直接要求改成買入；明確買入/放空仍維持方向一致性。

### Task 6：分模式回測與回饋

Files: `backend/decision_backtest.py`、`backend/decision_backtest_service.py`、`backend/decision_tracking_store.py`、`backend/market_price_history.py`、`backend/outcome_calibration.py`、`backend/temporal_memory_service.py`、新的小型交易路徑 evaluator/store；tests `tests/test_mode_decision_backtest.py`。

- [x] 避免是未持倉0報酬，持有按股價變動計算；不再將避免虛構成放空收益。
- [x] 長線保留3/6/12月；B/C有可執行計畫時依計畫價格驗證觸發/停損/退出，D以5/10交易日OHLC路徑評估。未觸發、資料不足及同根價格先後不明各自保留狀態，不捏造成交順序。
- [x] 新交易評估採獨立版本化持久資料，legacy月回測列原樣保留；報表與服務可讀新結果。
- [x] 沒有benchmark時超額報酬保持null，不把策略報酬冒充超額報酬；歷史記憶按同模式取得，讀正確strategy_roi_pct/outcome欄位。
- [x] 回測使用注入價格fixture完成端到端驗證，不連接供應商或寫正式DB。

## 整合驗收

- [x] 新失敗案例皆轉綠，既有受影響測試通過。
- [x] 每一批依序做規格與品質審查，修復實際缺口。
- [x] 執行四模式、prompt、structured output、audit、report renderer、workflow、回測、runtime/storage與模組邊界回歸。
- [x] 執行變更範圍與差異檢查，寫入交付說明與剩餘限制；不宣稱未執行的live分析或歷史報告重建完成。

最終整合：40 個測試檔案，2762 passed、1 skipped、75 subtests passed（275.95 秒）。跳過的是需另行啟用的真實 Chart.js 瀏覽器測試，不屬離線驗證。六項任務的獨立規格與品質審查皆通過；完整交付邊界見 `docs/four-mode-analysis-logic-2026-09-05.md`。

使用者另行核准commit／push後，基於 `740d3ebe` 拆分87個四模式相關檔案；提交版乾淨副本的45檔回歸為2802 passed、75 subtests passed（308.63秒），無跳過。原有其他任務變更保持未暫存。
