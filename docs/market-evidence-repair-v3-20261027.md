# 2026-10-27 V3：候選內外層市場身分一致性

狀態：V2 相鄰 P2 已修正；隔離測試完成，交原審查線複核。沒有部署、重啟、掃描、正式報告生成、供應商請求、付費模型、交易或固定76資料變更。

## 基線與修復

工作區 `/Users/balbomacmini/Documents/Codex/2026-10-27/task/stock-agent-isolated`；分支 `codex/market-evidence-integrity`。V2 基線 `c6cf505bee5523319df661685361162daf97f278`，原始隔離基線 `65163dddcac498836c26999418b4fb1b6b294a8c`。V1/V2 補丁及測試紀錄完整保留。新提交與完整／V2→V3增量補丁 hash 見 `../market-evidence-delivery-v3.json`，依實際基線擇一使用。

獨立相鄰檔 `tests/test_independent_v2_adjacent.py` 從審查副本逐位元複製，SHA-256 `96e9d3e2247078507050632bee4028fa4fdc06680b41fdd3f5e8177301d3d67f`。原樣重現 10 passed／2 failed；兩個失敗都是 TPEx 在 10/23、7/10 23:00 的內層來源說明借用 TWSE。未改反例或斷言。

1. `_source_evidence_state` 經共用 `candidate_report_identity.bound_report_ticker` 取得綁定身分，將 ticker 傳入 `session_cache_scope`。無法綁定時 expected=None、phase/state=unknown；不再默認 TWSE。
2. `load_candidate_report_observations` 同用此身分檢查。data.ticker 必須存在；可選 snapshot、latest metadata、daily、institutional、official observation 的 ticker 如有缺型或衝突即拒絕。這避免外層已對齊、內層因衝突未知的矛盾。沒有將日期對齊升級為來源准入；保存的 source_eligible 與 saved_gate_source_eligible 仍分列。
3. 廣搜找到另一逐檔漏接：`market_price_history.fetch_backtest_bars` 未把 ticker 傳給 `completed_evidence_session`。已補傳；TPEx 日曆未知在呼叫 provider 前回空，TWSE 正例與一般 TPEx 開市仍可依原契約取得。僅用假 provider 驗證，沒有執行真實回測、回填或重算。

相關呼叫檢視涵蓋 `completed_session`、`completed_evidence_session`、`session_cache_scope`、`acquisition_session_scope`、`publication_observation` 及 `session_day_status`，沒有僅搜尋第一層 helper。official_institutional_source、institutional_provider、taiwan source、cache alignment、yfinance、institutional window 與正常化／逐筆准入均有逐檔身分傳遞。未改 TWSE 專屬 screener，以及 decision_backtest_service 的批次 evaluation_day、performance／legacy76 整體摘要。此為已讀範圍的呼叫審查，不宣稱全域績效已驗收。

新增作者檔 `test_candidate_source_market_identity.py` 共19案，涵蓋內外層整合、兩個臨時休市、TWSE正例、一般TPEx開市、缺／錯格式／衝突身分、metadata衝突、不修改輸入及 provider 前置拒收。最初16案在修復前11 failed／5 passed；後加3個metadata反例。既有 `test_candidate_source_state.py` 正例原本未提供 ticker，修復後正確回 unknown，已在該正例明示2330.TW，原斷言保留；另有缺身分反例。首次相關組合83 passed／1 failed的紀錄保留。

## 驗收與獨立複核

| 批次 | 結果 | 紀錄 |
| --- | --- | --- |
| 原固定49模組，選取檔與V1逐位元相同 | 769 passed，36.97秒 | `market-evidence-validation-v3.log` |
| V2三個作者模組＋V3新增模組 | 58 passed，6.61秒 | `author-v3.log` |
| 原始獨立驗收檔 | 16 passed，7.57秒 | `independent-original-v3.log` |
| V2新增獨立相鄰檔 | 12 passed，4.37秒 | `independent-adjacent-v3-after.log` |
| 兩個指定日期反例單獨重跑 | 2 passed、10 deselected，4.33秒 | `independent-two-v3.log` |
| 直接受影響11模組 | 189 passed，7.91秒 | `candidate-source-v3-regression.log` |

各批有重疊，不能相加。原始16案檔仍是 `83765d06798e8f99f5df979cc95fb3844eea742300e750aa386eb342646e0312`。未實作本輪修正的代理另審所有上述呼叫與身分邊界，五個相關模組66 passed，未找到新的可重現缺陷；外部審查線仍須對本次凍結版再驗收。

在工作區執行：

```sh
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' scripts/validate_market_evidence_isolated.py
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_session_projection_conflicts.py tests/test_readiness_market_identity.py tests/test_institutional_cache_receipt_admission.py tests/test_candidate_source_market_identity.py -q
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_independent_market_review.py -q
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_independent_v2_adjacent.py -q
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_independent_v2_adjacent.py -k candidate_nested_source_state_does_not_borrow_twse_closure -q
```

專案 boundary runner 使用臨時SQLite、memory cache、禁止網路。審查檔將證據寫到副本的 `../evidence`（先建立該目錄）；原始16案最後一項唯讀正式報告。固定49模組仍須V1說明所列的兩個歷史fixture，未放入補丁。

## 正式保全及未核範圍

原16案再次逐欄重播V2於23:23:14建立的21份預覽，63個原artifact的hash仍與V1/V2完全一致；仍為12份至10/22、9份至10/27。本次沒有重新生成投資報告，也沒有將計畫重播冒稱新行情查核。

台北23:42:15唯讀比對正式基線4,289檔：changed=[]、missing=[]，見 `../formal-source-readback-v3.json`。lsof仍見PID76939監聽127.0.0.1:8080。這不代表正式DB自然更新停止、已載入新碼或全部209份應passed。補丁只在隔離工作區生成；正式目錄只作 `git apply --check`，結果見交付manifest。

未核範圍保持：真實供應商取得、正式22:30後自然流程、TPEx公告正文、正式完整重建與新job生命週期、全歷史PIT／價格調整／公司行動／停牌、瀏覽器視覺及固定76。部署／正式重建仍需後續明確授權。

本輪五批測試完成後，交付記錄腳本的雜湊比對誤寫成重複讀取整棵樹，造成收尾延遲，並非測試失敗。嘗試讀其已刪除的暫存腳本得到FileNotFound，未發出訊號；之後明確針對本任務隔離記錄程序PID53028的 `kill -INT 53028` 被沙箱拒絕（operation not permitted），未執行、未重試、未提權。正式PID76939從未被指定。此不是auto-review升權拒絕；不以耗時判斷任務失敗。最終收尾狀態與測試樹核對結果見交付manifest。

既有TPEx HTTP403與正式ps查詢拒絕也未重試或繞過；完整啟動時間／父程序未核。

收尾已自然完成、exit 0，無待執行程序。`market-evidence-v3-validation-result.json` 確認五批 exit 0、測試前後2,550個程式／測試檔無變動；測試樹 SHA-256 `40ea5fa744d24bc4a6e29d29dcdd159227007c3a739e7a7b615aa16c0b9a0d0f`，與後續凍結讀回相同。兩個獨立反例的合成回應前後比較見 `candidate-source-state-v3-comparison.json`。原始失敗log的pytest空白行保留，因此總diff的空白檢查僅有log內三行尾端空白；排除raw log後程式／文件diff檢查通過。
