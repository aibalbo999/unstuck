# 四模式品質缺口：後續根因調查

狀態：**根因調查完成，第一批修正方向已獲同意；書面規格待檢視，尚未修改正式程式。**

使用者已同意先處理「缺資料不產出 DCF、上游更正後重跑下游、補齊新聞與證據契約」。具體設計收斂於 `docs/superpowers/specs/2026-09-06-analysis-credibility-followup-design.md`；歷史重建範圍仍待選擇。

本紀錄延續 `remaining-analysis-delivery-2026-09-06.md` 的保留問題，不取代前一輪交付紀錄，也不表示舊報告已修復。查驗 checkout 為 `/Volumes/X10 Pro Mac/stock-agent`，基準為 `main` 的 `5f44bce0`。

## 1. 優先問題：占位 DCF、單位誤用與下游舊結論

### 正式 1623 A 的可重現因果

1. `backend/analysis_jobs.py:104` 將 `QuantEngine.compute_all(data)` 寫入 `data.quant_metrics` 與任務 `metrics_snapshot`。
2. `backend/quant_engine.py:163` 讀取格式化的 `shares_outstanding`，而不是 `shares_raw`。`NT$0.66億` 被 `_safe_float()` 去掉單位後變成 `0.66`，計算端的 `int(shares) or 100` 又變成 100 股。
3. 同模組 `:165`、`:171` 在缺少 `total_equity`、`free_cash_flows` 時代入 1000 與 `[100, 110, 120, 130, 140]`；`total_debt="NT$28.98億"` 同樣被解析為 `28.98`。正式原始資料其實有 `shares_raw=66000000`、`free_cash_flow_raw=-461411616` TWD，不能由示範值取代。
4. 以上輸入可精確重現系統的每股 DCF：熊市 9.39、基本 14.34、牛市 20.59。雖然同 payload 有 fallback 警告，數值仍可被分析及稽核消費，警告不足以阻止誤用。
5. 修復前 Agent 4 又把每股 14.34 誤讀成「14.34 billion TWD」，除以 6600 萬股得到 217.27；同樣換算產生 142.27／311.97。它自稱 `normalized_dcf`，但此例沒有對應的正規化 FCF 計算證據。
6. 最終稽核修復 Agent 4 後，其主方法改為 `relative_valuation`，目標為 174.5／216.1／241；Agent 7 卻沒有重跑，仍引用舊的 142.27／217.27／311.97。
7. `backend/final_audit_dcf.py:9` 只要 Agent 4 全文含 DCF，就抽取前三個目標價和系統 DCF 相比。因此又把相對估值目標誤報成三項 DCF 來源衝突。這是另一個比較口徑問題，不能只消除此警告而忽略前述真錯誤。

現有另一條 `backend/financial_tools.py:179` 路徑採原始單位，取得 base FCF 約 -0.4614 billion TWD；三情境回報 `base_fcf_billion_twd must be positive`。後續修正應保留既有模型不適用的邊界，不新造正 FCF 或替代估值。

### 下游未更新的證據

- 任務：`analysis-1623tw-v1-1788626177401-43b63dfd`。
- 修復前 checkpoint：`1f1a949a-b17f-6eda-800f-35ff75896929`，Agent 4 為 `normalized_dcf`，Agent 7 已引用 217.27。
- 事件 `936376`：`repair_agents=[2,4]`；`936574`、`936702` 分別記錄修復成功。
- 修復後 checkpoint：`1f1a94a3-6895-687e-8010-7fc7374675fc`，Agent 4 已改為相對估值；Agent 7 仍為相同的 3132 字並保留舊 DCF，直到最終 checkpoint。
- `backend/agent_runtime/audit_repair.py:105` 只執行被列入的修復 Agent。`repair_state.py:12` 更新該 Agent state；`context_dependencies.py:117` 清除依賴摘要，但沒有使已完成的下游分析失效。
- `backend/final_audit.py:161` 的目標範圍檢查無法證明引用來源版本一致，故沒有攔下這份舊結論。

### 影響範圍，不等於投資結論錯誤率

唯讀盤點目前 102 個 indexed versions，其中 62 份 snapshot 保存 `quant_metrics`；這 62 份均有數值 DCF，並記錄 `total_equity`、`free_cash_flows`、`eps` fallback。49 組股票／模式最新版中，21 份有同一現象。

這只證明占位計算值進入保存資料，**不表示所有這些報告的投資建議都採用了該 DCF**。修正後仍需逐份比較引用及新產物，不能直接改寫歷史品質紀錄。

## 2. 國際新聞：有來源，但結論揭露不足

1623 A、C 正式報告快照各保存 8 則國際新聞；尚未證明模型實際讀到全部輸入。Agent 7／19 最終建議沒有清楚記錄這批新聞的影響與理由。

`backend/final_audit_context_coverage.py:22` 現在於來源筆數大於零時，只檢查關鍵詞是否出現；寫入「國際新聞」不代表真的評估過，缺少詞也不必然證明完全沒看資料。`final_audit.py:147` 只加入 warning，而既有 repair loop 在沒有 critical 時就結束。

Agent 7 提示已有此要求，Agent 19 專用規則未同步；兩種 recommendation schema 也都缺少結構化新聞評估欄位。snapshot 保存 8 則 topics，但 prompt 精簡路徑可能只保留 2 則，不能從 snapshot 推論模型實際讀到全部 8 則。

修正候選：讓最終決策保存可查驗的「影響／不影響／未納入」及理由、來源引用；引用只能對到本次輸入。缺資料保留未納入，不能自動補一句「無影響」。驗證需涵蓋有影響、有理由的不影響、來源缺失、來源引用不存在及只塞關鍵詞的反例。

## 3. 不可驗證數字：兩項可補來源，其餘保留邊界

| 項目 | 查到的同語意來源 | 後續處理 |
| --- | --- | --- |
| 1623 D：支撐 205.4（20 日均線） | `data.technical_indicators.sma_20=205.425` | 僅對明示、唯一的 SMA 期間建立 exact path；沿用現有容差，不借風險價或別的均線 |
| 2308 C：最終投資建議列的 6 個月 NT$1380 | `rerun_context.parsed.recommendation.中期目標（6個月）` | 補受「最終投資建議」上下文限制的 compact horizon mapping；它證明報告與保存結論一致，不證明未來會到價 |
| 1623 C「情緒過熱評分」、2308 C「過熱評分」 | 分析文字，沒有外部事實 scalar | 只改為 `analysis_metadata_not_evidence` 分類，仍不可驗證 |
| A／B 護城河評分及各模式信心分數 | 分析 metadata | 保留不可驗證；不以分析自己的數字自證 |

主要位置：`backend/evidence_exit_gate.py:183`、`backend/evidence_exit_gate_claims.py:234`。新增匹配必須包含缺值、多數字／多期間、新聞語境、跨 horizon／跨均線同值及真實 mismatch 反例。不得改動歷史 snapshot、抽樣門檻或把 N/A 變成零。

## 4. PostgreSQL 與樣本外驗證：分開驗收

### PostgreSQL

目前正式 checkpoint 使用 SQLite。虛擬環境雖有 `langgraph-checkpoint-postgres 3.1.0`、`psycopg 3.3.4`、`psycopg-pool 3.3.1` 的安裝記錄，但實際 import psycopg 失敗：缺 `psycopg_c`／`psycopg_binary`，且找不到 `libpq`。

本次檢查的環境與 `backend/.env` 沒有 checkpoint PostgreSQL DSN；未輸出任何憑證。`psql`／`pg_ctl`／`postgres` 不在 PATH，5432 未見 listener。Docker CLI／App 存在，未啟動或更動。

現有 Postgres adapter 測試是 fake，不是 live。後續須先補隔離驗證環境的驅動，再用專用可丟棄 DB 測草稿保存、斷線重開、版本遞增、跨 thread 隔離及失敗不發布。不切換正式 SQLite。`workflow_checkpoints.py:45` 會執行建表／migration，且現有 Python socket 禁用無法保證攔截原生 libpq，故需另設嚴格的測試 DB allowlist。

### 樣本外績效

既有回測涵蓋未成熟 pending、未成交、同根先後不明、缺 OHLC 與未知成本，但沒有預先凍結的 OOS cohort／版本／報告 hash，不能宣稱投資績效已有樣本外改善。

後續先凍結候選、切分日、程式／prompt／模型版本、交易規則、排除理由與品質快照，再於隔離資料儲存評估真實後續交易日。D 的 5／10 日同報告不是兩個獨立樣本；尚未到期不能催出成熟績效。

2308 C 的「營收年增 <30% 或跌破 1750」需要當時已發布的營收與完整條件語意；不能只抽 1750 就當整段條件可回測。未知成本不填零，沒有事件不補為已確認催化劑。

`run_due_backtests()` 會抓外部行情並寫正式 operational store，並非唯讀調查入口。本輪未呼叫。

## 5. 歷史重建範圍

目前 canonical index：102 個版本、28 個 ticker、49 組股票／模式；A／B／C／D 最新組數為 7／7／8／27。102 份均可透過 `ReportArtifactLocator` 取得完整 HTML／Markdown／snapshot，且有 analyses 與 parsed context。

啟用追蹤為 7 檔；前輪的 28 組追蹤模式工作不等於上述 49 組，也不等於 102 個歷史版本。

已詢問使用者選擇：保留歷史並補齊每組最新版，或逐份另建歷史回放副本。選擇尚未回覆時，不送出這兩種批次中的任何一種，也不刪除／覆寫舊檔。所有重建必須在內容根因修正驗證後才執行。

## 6. 建議分批方式與驗收界線

建議先完成內容可信度一批：**真實金融輸入與單位 → 同方法／同版本稽核 → 依賴更新 → 新聞評估契約 → 精確 evidence mapping**。缺資料只使不適用的估值不可用，不把有獨立證據的相對估值一併假定為錯誤；真正未更新的依賴必須重算或阻擋發布。

另一種做法是同時啟動內容、PG、OOS、歷史全量重建；雖然可並行較多工作，但在根因尚未修正前會再產生受影響報告，也使各項驗收範圍混雜。因此建議先修內容，再獨立補環境／OOS及核定的歷史批次。

以上先修內容的方向已獲同意，書面規格已建立並完成設計自我檢核。依 brainstorming 設計流程，待使用者檢視書面規格後建立實作計畫，採失敗案例先行的測試流程；不能把方向核准當成程式修正完成。

## 7. 本次已驗證與未操作

以下六檔經 project Python 與 `tests/run_prompt_boundary_tests.py`、`-B`、`-q -p no:cacheprovider` 隔離執行：

- `tests/test_mode_decision_backtest.py`
- `tests/test_outcome_calibration.py`
- `tests/test_short_term_market_data.py`
- `tests/test_workflow_checkpoint_resume.py`
- `tests/test_workflow_quality_draft_resume.py`
- `tests/test_workflow_quality_draft_cold_imports.py`

結果：獨立盤點時 **114 passed，5.70 秒**；主工作再次執行相同六檔，**114 passed，5.63 秒**。兩次不是 228 個不同測試，且僅代表既有 fixture／SQLite／fake adapter 回歸，不代表本次新發現已修好、PostgreSQL live 已驗證或投資績效已成立。

調查時 GET 驗證 `healthz=ok`、`readyz=ready`、active jobs=0。調查及設計文件沒有更動正式程式、`.env`、資料庫、報告、佇列、模型額度、容器或 runtime。文件可以單獨提交，這不代表正式程式或 runtime 已更新。
