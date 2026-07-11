# 報告內容可信度系統優化方案

更新時間：2026-07-08

## HCS Plus 專案狀態

| 欄位 | 目前狀態 |
|---|---|
| 專案目標 | 優化股票研究報告的內容可信度，優先降低亂編、數字對不上、目標價/建議不自洽、高信心但低資料可信度等問題。 |
| 成功標準 | 報告在存檔前能 deterministic 地指出關鍵結論是否與 snapshot、data trust、evidence gate、parsed recommendation、price targets 互相一致。 |
| 專案內容 | 現行出口為 `ReportRenderer`：產生 HTML/Markdown、跑 `report_lint`、建立 snapshot、跑 `evidence_exit_gate`、跑 `report_conformance`，再寫入 metadata/snapshot。 |
| 工作區狀態 | Python 報告系統；既有測試包含 `tests/test_evidence_exit_gate.py`、`tests/test_report_conformance.py`、`tests/test_report_data_trust.py`、`tests/test_report_lint.py`。 |
| 限制條件 | 新流程不得直接呼叫 provider、不得猜 report artifact path、不得把測試綠燈宣稱成投資正確；實作時需依 TDD 先寫 failing tests。 |
| 已採用決策 | 使用者選擇優先方向 A：內容可信度。暫定採用 deterministic gate 為主，報告標示/降級為輔，不先大改 prompt 或模型流程。 |
| 未解問題 | 各 recommendation 對應的 upside/downside 門檻需在實作時以測試固定；初版建議用保守門檻並標為可調參數。 |
| HCS Plus 進度 | 第 1 輪 / 批判思考第一批：已處理 #拆解問題、#問對問題、#差距分析、#變數分析。下一個習慣是 #偏誤辨識。 |

## 系統優化總案

新增一個 deterministic content credibility gate，建議模組為 `backend/reporting/content_credibility.py`，輸出 `content_credibility` 結果並整合進 `ReportRenderer` 與 `report_conformance`。

核心輸入：

- `context`: `parsed.recommendation`、`parsed.price_targets`、`parsed.trade_setup`、`pipeline_id`、`final_audit`。
- `snapshot`: `data.current_price`、`data.data_trust`、`evidence_matrix`、`evidence_exit_gate`、`report_lint`。
- `markdown`: 用於必要時輔助偵測報告可見結論，但初版不依賴 LLM 或語意摘要。

核心輸出：

- `status`: `passed` / `warning` / `blocked`
- `summary`: 一句話說明是否可信。
- `blocking_issues`: 會使報告不符合輸出契約的矛盾。
- `warnings`: 需要人工注意但不必阻擋的限制。
- `checks`: 每個檢查項目的 deterministic trace。

建議檢查項目：

1. **目標價與現價一致性**：12 個月目標價、三情境目標價、短線目標價不得出現明顯單位錯誤、極端離群，且需與目前股價同口徑比較。
2. **建議與 upside/downside 一致性**：`買入` 不應同時給出低於現價的主要目標；`避免` 或 `放空` 不應同時給出高幅度上漲主要目標；`持有` 若有極端 upside/downside，需降為 warning 並要求說明。
3. **信心與資料可信度一致性**：data trust 不是 fresh、evidence gate 不是 approved、或 report conformance 有 warning 時，高信心結論需降級或警示。
4. **證據矩陣覆蓋**：最終建議、估值結論、目標價、護城河或催化劑若存在，應能在 `evidence_matrix` 找到來源、狀態與限制。
5. **模式契約一致性**：`v4` 使用 trade setup 檢查進場區間、目標、停損方向；`v1/v2/v3` 使用 recommendation 與 price targets 檢查長短期結論。
6. **資料限制不可被結論覆蓋**：若資料來源 stale/partial/error，報告仍可保留，但 `content_credibility.status` 至少為 warning；若同時有明確目標價且資料信心低於門檻，升為 blocked。

## HCS Plus 第 1 輪第一批

### #拆解問題

核心判斷：

1. 目前系統已能抽樣核對數字，但「數字有出現在 snapshot」不等於「投資結論自洽」。
2. 內容可信度至少包含四層：原始數字可信、推論方向可信、結論與風險相符、報告可見限制沒有被淡化。
3. 最小安全改法是新增獨立 gate，而不是把規則散落在 renderer、final audit 和 prompt。

落地修改：

- 本文件新增「系統優化總案」與六類檢查項目，將內容可信度拆成可測的子問題。

驗證：

- 後續實作前先新增 `tests/test_content_credibility.py`，每個子問題至少一個 failing test。

### #問對問題

核心判斷：

1. 這次真正要問的不是「報告是否好看」，而是「使用者能不能相信結論沒有違反資料與算術」。
2. gate 的主問題應是：報告的最終建議是否能被 current price、price targets、data trust、evidence gate 同時支持？
3. 初版不應要求模型解釋所有語意，只要求 deterministic 可檢查的高風險矛盾。

落地修改：

- 本文件將優化問題重新定義為「結論可被資料與算術支持」，並把 prompt/模型優化延後到 deterministic gate 之後。

驗證：

- 實作時測試名稱需直接描述問題，例如 `test_blocks_buy_recommendation_when_main_target_is_below_current_price`。

### #差距分析

| 現況能力 | 差距 | 優化後應達成 |
|---|---|---|
| `evidence_exit_gate` 抽樣核對 Markdown 數字是否能在 snapshot 找到。 | 不檢查 recommendation、目標價方向、信心與 data trust 是否互相矛盾。 | `content_credibility` 檢查結論一致性，並提供 blocking/warning trace。 |
| `final_audit` 檢查 Agent 輸出、目標價順序、低 data confidence 明確目標價。 | 規則偏生成階段，renderer 出口缺少一個統一的報告內容可信度結果。 | renderer metadata/snapshot 固定帶有 content credibility 結果。 |
| `report_conformance` 檢查必要段落、lint、final audit、evidence gate、data trust。 | conformance 未納入「建議與估值自洽」這個報告級品質面。 | conformance decision tree 新增 `content_credibility` step。 |
| `evidence_matrix` 顯示來源與限制。 | 不保證所有關鍵結論都有 evidence row。 | content credibility 對關鍵結論做 evidence coverage 檢查。 |

落地修改：

- 本文件新增差距矩陣，明確切出 `content_credibility` 與現有 gate 的責任邊界。

驗證：

- 實作時至少跑 `tests/test_content_credibility.py`、`tests/test_report_conformance.py`、`tests/test_report_data_trust.py`。

### #變數分析

初版需要固定並測試的變數：

| 變數 | 來源 | 初版用途 |
|---|---|---|
| `current_price` | snapshot data | 判斷目標價方向、短線 target/stop 是否合理。 |
| `recommendation` | parsed recommendation | 判斷買入/持有/避免/放空與目標價是否一致。 |
| `price_targets` | parsed price targets | 判斷熊/基本/牛順序、主要目標與現價距離。 |
| `confidence` | parsed recommendation | data trust 或 evidence gate 不佳時避免高信心。 |
| `data_trust.status` / `score` | snapshot data trust | 決定明確目標價與高信心是否允許。 |
| `evidence_exit_gate.verdict` | renderer gate | verdict 非 approved 時降低內容可信度。 |
| `evidence_matrix` | snapshot/reporting | 確認關鍵結論是否有來源與限制。 |
| `pipeline_id` | context/snapshot | 決定使用長線 recommendation 還是短線 trade setup 規則。 |

落地修改：

- 本文件新增變數表，作為 `evaluate_content_credibility()` 的輸入 contract。

驗證：

- 實作時每個變數需有缺值測試；缺值預設不能造成例外，應回傳 warning 或 skipped check。

## 實作分期

### Phase 1：測試先行

新增 `tests/test_content_credibility.py`，先覆蓋：

1. 買入但主要目標價低於現價，應 blocked。
2. 避免/放空但主要目標價顯著高於現價，應 blocked 或 warning，依 pipeline 契約固定。
3. data trust 低於明確目標價門檻且報告有明確 target，應 blocked。
4. evidence gate 為 rejected 時，content credibility 至少 warning，若同時有高信心則 blocked。
5. 缺少 evidence matrix 覆蓋最終建議，應 warning。

### Phase 2：新增 gate 模組

新增 `backend/reporting/content_credibility.py`：

- `evaluate_content_credibility(context, snapshot, markdown=None) -> dict`
- 小型 helper：價格解析、confidence 解析、recommendation normalization、evidence coverage check。
- 不呼叫 provider，不讀寫檔案，不依賴 report output path。

### Phase 3：整合 renderer 與 conformance

修改：

- `backend/reporting/renderer.py`：在 evidence gate 後、conformance 前計算 `content_credibility`，並放入 context、snapshot、metadata。
- `backend/reporting/conformance.py`：decision tree 新增 `content_credibility` step；blocked 時整份報告 blocked。
- `backend/reporting/execution_summary.py`：可在摘要中顯示 `Content credibility` 狀態；若怕 golden snapshot 震盪，可第二步再做。

### Phase 4：回歸與契約文件

更新：

- `docs/pipeline-mode-contract.md`：把 content credibility 納入高顯著性機器契約通道。
- 依實際 Markdown 輸出變更決定是否更新 golden snapshot。

建議驗證命令：

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_content_credibility.py \
  tests/test_report_conformance.py \
  tests/test_report_data_trust.py \
  tests/test_evidence_exit_gate.py \
  tests/test_report_lint.py \
  -q
```

## 風險與取捨

| 取捨 | 採用 | 延後 |
|---|---|---|
| deterministic gate vs prompt 改寫 | 先採 deterministic gate，因為可測且穩定。 | prompt 優化留到 gate 找出常見錯誤後再做。 |
| blocked vs warning | 明顯算術/方向矛盾 blocked；資料限制與覆蓋不足 warning。 | 是否自動重跑先延後，避免增加模型成本。 |
| 報告可見顯示 | 初版先放 snapshot/metadata/conformance。 | 若 UI 需要，再加 HTML/Markdown 顯示區塊。 |

## 驗收標準

1. `content_credibility` 結果存在於 report metadata 與 data snapshot。
2. `report_conformance.decision_tree` 包含 `content_credibility` step。
3. 明顯目標價/建議矛盾會 blocked，不會只靠人工看報告才發現。
4. data trust 不佳時，高信心或明確目標價會被降級或阻擋。
5. 缺少關鍵 evidence coverage 時，報告至少 warning，並留下可追溯 issue。
6. 聚焦測試通過；不得宣稱投資結果正確，只能宣稱已知內容可信度契約未回退。

## 下一步

若繼續 HCS Plus，第 1 輪下一批從 #偏誤辨識、#偏誤降低、#決策樹、#目的 開始，目標是把本方案中的 blocking/warning 門檻變成更明確的決策樹，再進入 TDD 實作。
