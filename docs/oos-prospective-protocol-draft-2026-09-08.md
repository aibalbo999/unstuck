# 四模式內容可信度前瞻研究 Protocol 草案

日期：2026-09-08（Asia/Taipei）。狀態：**draft_unactivated／prospective_unverified**。

本文件把 F4 的 28 組正式重建候選安排成第一個真實 prospective cohort，避免另產生一批報告與模型成本。它不是事前登記 receipt，也未授權 push、runtime reload、Job 送件或資料訂閱；在遠端 receipt 形成前，樣本數固定為 0。

## 1. 研究問題與判定界線

研究問題：目前四模式的內容可信度與證據邊界，在未來資料到期後，能否產生可重現、分母完整且不靠事後選樣的分析結果。

本研究先量測品質與結果，不以命中率自動調整 prompt、模型或交易規則。F6 只有在完整 cohort 顯示可重現缺陷或形成事前可檢驗假設時，才另開版本實作；同一 study 不回寫規則。

不得宣稱：投資獲利保證、四模式彼此可直接比較、少量樣本具統計顯著性，或合成 OOS 已證明真實效果。

## 2. 固定 cohort

- 候選來源：[`report-update-candidates-2026-09-08.json`](./report-update-candidates-2026-09-08.json)。
- 來源 SHA-256：`f9d697eacc525ba8c0bbd7d8d4dde0d8619982ee96da6076f2af3c7d2fce0af2`。
- Universe：`1623.TW`、`2308.TW`、`2367.TW`、`3017.TW`、`3324.TWO`、`3653.TW`、`6282.TW`。
- Pipelines：每檔各 `v1`、`v2`、`v3`、`v4`，共 28 個預定候選。
- 每個 ticker／pipeline 只取外部 receipt 後第一份符合本 protocol 的新報告；重送、resume 或 fallback 不增加候選數。
- 生成失敗、配額延後、缺報告、證據不足、品質拒絕、停牌或下市均留在 28 個候選分母內，不以成功報告反推 cohort。

最終啟用 manifest 必須在 receipt 前填入明確 `selection_period.start/end`。建議生成窗口為連續 3 個台灣交易日，僅用來容納 provider quota；每份報告仍以自身 `report_available_at` 決定評估起點。

## 3. 版本與生成政策

- `study_id` 建議：`four-mode-credibility-prospective-r1`；若任何已固定政策改變，建立新 study ID。
- `code_commit`：只接受已整合並由 `/api/runtime-identity` 證明的 40 字元 commit；`code_dirty` 必須為 `false`。
- 報告必須保存 prompt fingerprint、實際 model ID、fallback route、input/data snapshot hash、quality metadata hash、結論生成與實際可得時間。
- 可變 model alias 只有在 provider 不提供 immutable revision 時允許，並標記 `model_revision_unknown`；不同模型或 fallback 的結果分組呈現，不合成單一因果效果。
- 已在 receipt 前完成的舊 Job、只刷新 snapshot 的舊本文或缺少新 code／prompt fingerprint 的產物，一律不算新 cohort 報告。
- Job 採 `force=false, resume=true`；若 attach 到既有工作，仍須以產物時間與 fingerprint 證明它符合 receipt 後的新版本，否則記為 `missing_report`。

## 4. 事前登記與封存 receipt

建議使用本 repository 的 GitHub 遠端 commit 作外部登記：先把最終 manifest、候選 hash、研究政策與 evaluator version commit 並 push；保存遠端 commit URL、GitHub 接收時間、commit SHA 與 manifest SHA-256。只有這個 receipt 可查後，才能 reload runtime 或送第一個 Job。

本機檔案時間、Git author date、口頭同意或事後補寫的 hash 均不能單獨證明 prospective。若遠端 receipt 不可查，研究分類維持 `prospective_unverified`，但資料可保留供 retrospective replay。

每份候選必須在首個可評估交易 session 前封存 HTML、Markdown、snapshot、parsed plan 與內容 hash。封存逾時回 `late_seal`，不可移動基準日補救。

## 5. 四模式主要期限與指標

| 模式 | 固定期限 | 主要輸出 |
| --- | --- | --- |
| A／v1 | 3、6、12 曆月 | recommendation／target 校準；direction-only 另列，不混入主要 target 分母 |
| B／v2 | 報告 `position_plan.horizon_trading_days` | 新進場／等待交易路徑；缺期限或既有部位歷史為不足 |
| C／v3 | 報告 `short_setup.horizon_trading_days` | 空方／避免與保守 OHLC 路徑；複合條件不降成單一價格 |
| D／v4 | 5、10 交易日 | `trade_setup` 路徑；兩期限相關，不當成兩份獨立報告 |

共同主要分母：預定候選、實際生成、admitted、成熟、pending、不可評分、未成交／觀察、ambiguous、hit／miss。命中率只用明確 hit／miss；0 個可評分時為 `null`。

不設定跨模式總命中率。第一輪只提供描述統計與完整分母，不做顯著性、排名、參數搜尋或模型優勝宣稱。

## 6. 價格、成本、benchmark 與企業行動

- 價格政策沿用 evaluator 支援的 `raw`；只接受完整收盤後 bar 與明確交易日 calendar。
- 拆股、除權息或其他企業行動狀態未知時，相關 ROI 標記不足，不自行調整。
- 未取得交易成本證據時 net ROI 為 `null`；不得把稅、滑價、借券費或股息猜成 0。
- Benchmark 預設 `not_provided`，因此 excess return 為 `null`；只有同期間、幣別、價格政策與來源證據齊全時才另行啟用。
- 不新增付費資料源。模型與資料成本沿用現行配額，實際 usage 由既有 telemetry 保存；配額失敗仍留在分母。

## 7. 收樣、成熟與版本規則

1. 遠端 receipt 可查後，才建立 final prospective manifest 與不可覆寫 study root。
2. 載入 receipt 所指 code revision，核對 API／Worker identity、health／ready 與四模式 route。
3. 按核定 28 組分批送件；每批保存 pending、Job ID、完成／失敗／未確認，回應不明不得重送。
4. 每份新產物立即封存 bundle、時間鏈、model／prompt／code／input identity 與 quality metadata；所有缺件仍建立 admission record。
5. D 到第 5／10 個完整交易日後評估；B／C 依各報告明示期限；A 到 3／6／12 曆月後評估。未成熟保持 `pending_horizon`。
6. 新 cutoff／dataset 只建立 evaluation revision，不覆寫舊 pending；摘要由明示 cutoff 與完整 ledger 選取 revision。

## 8. 啟用前尚待填定

- [ ] 使用者核定上述 7 ticker × 4 mode 的 28 組 cohort。
- [ ] 填入精確 selection period、final code commit、prompt／model route policy hash 與 evaluator version。
- [ ] 產生 final machine-readable manifest 並通過現有 `oos_research.manifest`／policy validator。
- [ ] push 後保存可查的遠端 receipt；receipt 時間必須早於第一個 Job。
- [ ] 明確授權 runtime reload 與正式 Job 送件；未授權前不得啟用。

最早可報告的真實成熟結果仍受市場時間限制：D 至少 5／10 個交易日，A 至少 3／6／12 個月。工程完成不能縮短這些期限。
