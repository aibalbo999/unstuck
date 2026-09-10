# 四模式內容可信度前瞻研究 Protocol

日期：2026-09-08（Asia/Taipei）。狀態：**selection_closed_waiting_maturity**（2026-09-10 更新）。

本文件把 F4 的 28 組正式重建候選固定為第一個真實 prospective cohort，避免另產生一批報告與模型成本。使用者已核准 GitHub Actions／Sigstore attestation、這 28 組 cohort、manual workflow／PR／push、正式 API／Worker 重啟、分批送件與 artifact 重建；不含 PR merge 或新增付費資料訂閱。在 Sigstore receipt 實際完成並經固定政策離線驗證前，樣本數仍為 0。

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

最終啟用 manifest 的 `selection_period` 固定為 2026-09-09 至 2026-09-11（Asia/Taipei），僅用來容納 provider quota；每份報告仍以自身 `report_available_at` 決定評估起點。

## 3. 版本與生成政策

- `study_id` 建議：`four-mode-credibility-prospective-r1`；若任何已固定政策改變，建立新 study ID。
- `code_commit`：只接受已整合並由 `/api/runtime-identity` 證明的 40 字元 commit；`code_dirty` 必須為 `false`。
- 報告必須保存 prompt fingerprint、實際 model ID、fallback route、input/data snapshot hash、quality metadata hash、結論生成與實際可得時間。
- 可變 model alias 只有在 provider 不提供 immutable revision 時允許，並標記 `model_revision_unknown`；不同模型或 fallback 的結果分組呈現，不合成單一因果效果。
- 已在 receipt 前完成的舊 Job、只刷新 snapshot 的舊本文或缺少新 code／prompt fingerprint 的產物，一律不算新 cohort 報告。
- Job 採 `force=false, resume=true`；若 attach 到既有工作，仍須以產物時間與 fingerprint 證明它符合 receipt 後的新版本，否則記為 `missing_report`。

## 4. 事前登記與封存 receipt

建議使用可查且不可由研究執行者回填時間的外部服務作正式登記：先固定最終 manifest、候選 hash、研究政策與 evaluator version，再由外部 receipt 綁定內容 hash、commit/ref 與服務端時間。只有這種 receipt 可驗證後，才能 reload runtime 或送第一個 Job。單獨 push Git commit 不會留下可由離線 Git 證明的遠端接收時間，因此不能自行完成這個條件。

主機端可使用 `scripts/capture_oos_registration_receipt.py` 擷取 `oos.registration-receipt.v1` capture evidence。工具要求乾淨 worktree、HEAD 等於明示 40 字元 commit、manifest 本機 bytes 與該 commit 內檔案完全相同，且 `git ls-remote --refs` 回傳的遠端 ref 精確指向同一 commit；只保存 HTTPS remote URL、ref、commit、本機觀測時間、manifest hash，以及有界的 `commit<TAB>ref` 證據與 hash。輸出必須是 repository 外、尚不存在的絕對路徑（含 symlink parent 都以實際路徑判斷），工具不執行 push、runtime reload 或 Job 送件。

v1 的 `observed_at` 來自主機時鐘，`git ls-remote` 也不含遠端接收時間或簽章；它只能證明捕捉當下的內容／ref 一致性，不能單獨證明事前登記。OOS runner 因此固定加入 `registration_time_not_externally_attested`，保存 capture record 但不把研究升格為 `prospective`。正式啟用仍需另定可重新查驗、時間不可回填且綁定 manifest/commit/ref 的外部 attestation schema 與 verifier。

### 已核准的外部 attestation

採用 GitHub Actions artifact attestation（Sigstore）：workflow 只給 `contents: read`、`id-token: write`、`attestations: write`，使用 GitHub-hosted `ubuntu-24.04`，且 `actions/checkout`、`actions/attest` 均 pin 到完整 commit SHA。因 workflow 尚未存在於 default branch 且本授權不含 merge，首次 push bootstrap 只允許一個 parent，且該提交只能新增 workflow 與 final manifest；日後以 `workflow_dispatch` 手動執行。

正式 verifier 不只接受 `gh attestation verify` exit 0，還必須固定 `aibalbo999/unstuck`、signer workflow path、OIDC issuer、source commit/ref、SLSA predicate type，拒絕 self-hosted runner，並解析 `--format=json`：subject digest 必須等於 final manifest bytes，`signature.certificate` 身分必須符合固定 workflow，`verifiedTimestamps` 至少一筆且最早不可偽造時間早於所有 candidate cutoff。bundle 與當次 trusted-root snapshot 各自保存 SHA-256；verification 在 network-disabled 環境用 `--bundle` 與 `--custom-trusted-root` 重跑，不接受使用者自行填寫的 `verified=true` 或 timestamp。

固定 revisions：`actions/checkout@11d5960a326750d5838078e36cf38b85af677262`、`actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`。workflow 的實際成功 run、bundle 下載、trusted-root snapshot 與離線 verifier 結果仍須以執行證據填回，不因程式已存在而預先算通過。

官方參考：

- <https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations>
- <https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/verify-attestations-offline>
- <https://cli.github.com/manual/gh_attestation_verify>

OOS verifier 支援舊的 `oos.registration-receipt.v1` capture 與新的 v2 GitHub/Sigstore receipt。v2 必須由同一程序以 manifest、bundle、trusted root 重新執行離線 `gh attestation verify` 後取得 process-local capability；把 v2 projection 寫成 JSON 再讀回不會重建驗證權限。任意 truthy 值、malformed receipt、manifest／subject／certificate／commit／ref mismatch，或 verified timestamp 晚於候選 `analysis_input_cutoff`，都維持 `prospective_unverified`／`insufficient_provenance`，admission 分母不會消失。

本機檔案時間、Git author date、口頭同意或事後補寫的 hash 均不能單獨證明 prospective。若遠端 receipt 不可查，研究分類維持 `prospective_unverified`，但資料可保留供 retrospective replay。

每份候選必須在首個可評估交易 session 前封存 HTML、Markdown、snapshot、parsed plan 與內容 hash。正常盤開盤時間固定為 Asia/Taipei 09:00；開盤前完成的報告以當日為首個後續 session，開盤後完成則以下一交易日為首個後續 session。封存逾時回 `late_seal`，不可移動基準日補救。

## 5. 四模式主要期限與指標

| 模式 | 固定期限 | 主要輸出 |
| --- | --- | --- |
| A／v1 | 3、6、12 曆月 | recommendation／target 校準；direction-only 另列，不混入主要 target 分母 |
| B／v2 | 主要期限固定 5 交易日，且報告 `position_plan.horizon_trading_days` 必須明示為 5 | 新進場／等待交易路徑；期限不符或既有部位歷史為不足 |
| C／v3 | 主要期限固定 5 交易日，且報告 `short_setup.horizon_trading_days` 必須明示為 5 | 空方／避免與保守 OHLC 路徑；複合條件不降成單一價格 |
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

1. 帶不可回填外部時間且綁定研究身分的 receipt 可查後，才建立 final prospective manifest 與不可覆寫 study root；v1 Git capture 不足以通過。
2. 載入 receipt 所指 code revision，核對 API／Worker identity、health／ready 與四模式 route。
3. 按核定 28 組分批送件；每批保存 pending、Job ID、完成／失敗／未確認，回應不明不得重送。
4. 每份新產物立即封存 bundle、時間鏈、model／prompt／code／input identity 與 quality metadata；所有缺件仍建立 admission record。
5. D 到第 5／10 個完整交易日後評估；B／C 依各報告明示期限；A 到 3／6／12 曆月後評估。未成熟保持 `pending_horizon`。
6. 新 cutoff／dataset 只建立 evaluation revision，不覆寫舊 pending；摘要由明示 cutoff 與完整 ledger 選取 revision。

## 8. 啟用執行清單

- [x] 使用者核定上述 7 ticker × 4 mode 的 28 組 cohort、GitHub/Sigstore attestation、push／PR、runtime reload、分批送件與 artifact 重建；merge 未授權。
- [x] 固定 selection period 2026-09-09 至 2026-09-11、prompt fingerprint、model-route policy hash、evaluator version 與 28 組來源 SHA-256；final code commit 由 bootstrap revision 綁定。
- [x] 實作 v2 process-local verifier、嚴格 admission、唯一 `report_done` 時間鏈、content-addressed candidate seal、分批送件與 pending 防重送。
- [x] 產生 final machine-readable manifest，與 workflow 形成僅兩檔案的 bootstrap commit 並 push。
- [x] GitHub Actions 成功產生 attestation；下載 bundle／trusted-root，離線驗證並保存非秘密 projection 與 hashes。
- [x] 以 attested clean revision 重啟 API／Worker，驗證 runtime identity、health／ready，再按 28 組分批送件並封存正式 artifacts。最終 26 份報告 sealed，`3324.TWO` v1／v3 以 `missing_report` 留在固定 28 分母，沒有補送或替代。

成熟日的正式執行入口與 append-only 命名規則見 [`oos-maturity-checkpoint-runbook.md`](./oos-maturity-checkpoint-runbook.md)。

最早可報告的真實成熟結果仍受市場時間限制：D 至少 5／10 個交易日，A 至少 3／6／12 個月。工程完成不能縮短這些期限。
