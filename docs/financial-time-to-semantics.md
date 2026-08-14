# Financial Time-to Semantics

狀態：D3374 規格已驗證

## 目的

避免報告品質 parser 把金融作業週期 KPI 的數值誤當成股票目標價，同時保留同一句中明確標示的股票 target price。這份規格只處理英文 `time to price`、`time to quote`、`time to bill`、`time to invoice`、`time to charge`，不延伸到一般 `price`、`quote`、`bill`、`invoice` 或 `charge` 欄位。

## 語意規則

1. **Cycle-time KPI**：`time to <financial root>` 後接 `target`、`forecast`、`actual`、`baseline` 或 `current`，再帶數字與作業單位時，數字屬於作業週期 metric，不得成為 target-price candidate。
2. **Explicit target price**：同一文字另有 `target price`、`price target`、`目標價`、`目標股價` 或 `合理股價` 加價格數字時，必須保留該明確價格。
3. **Context stripping**：處理 explicit target price 時，只移除 financial cycle-time KPI 的數值，不移除明確 target-price marker 與其價格。
4. **Ambiguous wording**：沒有 `time to` 結構的單獨 `price`、`quote`、`bill`、`invoice`、`charge` 不在本規格內，維持既有金融語意與既有測試。
5. **Path-level fields**：欄位名稱含 `time_to_<financial_root>` 且 value 只有 cycle-time KPI 時，不得建立 explicit target-price field；欄位 value 同時含明確 target-price marker 時，才保留該 field。

## 必測案例

測試矩陣固定為 5 roots × 4 phases × 5 states × 6 prefixes，共 600 cases。每一個 root 都要驗證：

- 純 cycle-time KPI 不產生價格候選。
- `target price NT$205 with <cycle-time KPI>` 只保留 `205`。
- recommendation calibration 不因 cycle-time KPI 改變推薦。
- content credibility、structured output 與 report target-price detector 都遵守相同邊界。
- 明確 `target price NT$205` 的既有金融案例不回歸。

## 不在本批處理

- 不修改一般 `price`、`quote`、`bill`、`invoice`、`charge` 的財務欄位解析。
- 不將金融 cycle-time KPI 推論為公司基本面或投資建議。
- 不變更 report artifact、runtime/storage、模型 routing 或資料抓取流程。

## 完成門檻

1. 五入口 RED 先證明目前至少有一個 cycle-time 數值漏入價格路徑。
2. production 修改只影響明確 `time to <financial root>` KPI branch。
3. 600-case matrix 的 `leaks=0`、`valid_misses=0`。
4. 五入口 focused、D3349 之後相鄰 regression、import boundary、docs contract、`py_compile`、`git diff --check` 均通過。

## 驗證結果

- RED：五入口 `5 failed`，確認 financial cycle-time 數值會漏入價格路徑。
- GREEN：五入口 `5 passed in 28.03s`。
- Post-fix matrix：`600 cases / leaks=0 / valid_misses=0`。
- D3349-D3374 adjacent regression：`112 passed in 1,669.41s`。
- Import boundary：`503 passed in 10.02s`。
