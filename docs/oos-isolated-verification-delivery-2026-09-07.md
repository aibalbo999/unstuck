# OOS 隔離驗證交付紀錄

日期：2026-09-07。這是核准 OOS 規格的合成／離線工程驗收，不是正式績效研究。

## Scope 與輸入身分

- 工作樹：`/Volumes/X10 Pro Mac/stock-agent`
- branch：`codex/analysis-credibility-spec`
- study：`synthetic-four-mode-20260907`
- manifest：`439b89e8c7028adae2371cc71fea90f8060e9ff95a264c5c6188f25d4c333e28`
- fixture SHA-256：manifest `c9cb7abf523987f1b19c439079223e369e241a8e504a89ddf4480ac56c33903f`；inventory `e95f25d8cf0860c903e6451bf94022361931efdca7b0239238ee35d92c74469a`；dataset `f219c8d727e354e6d894c32f8adc976eb5a02c9fecb336a7f77de6cdb5bed5f9`
- evaluator：`oos.evaluator.v1`；dataset hash `31df9ee4fbbf073ec38ee592051fa299dbcac4c93358f746c22caaf7b5227161`；inventory hash `7b44d94502f5dfcf8014191bf5fd06b7061e7ba716ee256d8d1b601bd5716173`

## 實作與驗證

新增 `backend/oos_research/` 的 manifest／record／store、inventory／admission／provenance、dataset／calendar／policies、A 與 B/C/D wrapper、evaluation revision、完整 summary 與薄 CLI；`tests/fixtures/oos_synthetic/` 是明確合成四模式輸入。Store 使用 canonical JSON、SHA-256、content-addressed blobs、exclusive create、原子提交與讀回 hash 驗證；不寫正式 DB／artifact／API。

OOS-01～10：`tests/test_oos_research.py` 共 `11 passed`；隔離結果／bundle 契約：`tests/test_oos_validation_contract.py` 共 `7 passed`；合併 OOS lane 為 `18 passed`；既有模式回歸 `tests/test_decision_backtest.py tests/test_mode_decision_backtest.py tests/test_trade_execution_contract.py` 共 `154 passed`。薄入口輸出 `11 passed`、exit code `0`。

容器 evidence：image `sha256:03e72007e0935195d42d91abb51fe3456bca02e083dbbec829feed6a43781ceb`；`network=none`、read-only root、非 root `65532:65532`、無 host bind／volume、只有 `/tmp`／`/results` tmpfs。實際 container result：`10 passed / 0 failed / exit_code=0`、`status=passed`；精確 CID `ff7f18f33ec9b83e571d460029d284631c53b25618074aebd138693fac1b704e` 已移除，未使用名稱掃描／prune。

CLI 對上述 fixture 產生 `4` candidates、`7` evaluations；v1 3／6／12 月成熟，v2 保留 ambiguous，v4 5 日保留 ambiguous、10 日保留 pending；無可評分結果的組別以 `null` hit rate／ROI 表示。輸出 JSON SHA-256 `9adb2dd7f0d4c6e8d3e93590adf14a0c22348fb3a0e980acaa17deabedfa9216`，Markdown projection SHA-256 `2eef594f866573db860610bd26b5426c9c7dddc0f988cf60d7bb089055045656`。

## 邊界與未交付

本批僅證明 OOS 隔離設施可重現、可拒絕篡改、可保留完整分母及未知狀態。真實 prospective protocol／外部事前 receipt、收樣、A 3／6／12 個月與 D 5／10 日成熟績效仍是 0／未驗證；不把合成命中率寫成投資效果，也未啟動正式 PostgreSQL 切換、報告重建、push 或 merge。

2026-09-08 後續補強：`provenance.verify_registration_receipt()` 現要求結構化 `oos.registration-receipt.v1`，綁 manifest SHA-256、HTTPS Git remote、ref／commit、本機觀測時間與精確 `git ls-remote` evidence；任意 truthy receipt 不再升格 prospective。因 v1 沒有不可回填的外部時間 attestation，canonical verifier 固定回報 `registration_time_not_externally_attested`，`evaluate_candidate()` 不會准入，CLI 也保持 `prospective_unverified`；晚於任一候選 cutoff、malformed URL 等原因會聚合保存，未通過者仍留在 admission 分母。新增 `scripts/capture_oos_registration_receipt.py`，只在乾淨且已提交的 manifest 與遠端 ref 同 revision 時產生 repository 外的 exclusive capture evidence；相關 OOS／capture 隔離 lane `24 passed`。這仍是啟用前工程，不代表已有外部事前 receipt 或 cohort。
