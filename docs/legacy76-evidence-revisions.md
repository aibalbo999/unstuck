# 76 筆歷史結果的追加版本

固定批次另有[未評分處置設計與待套用流程](legacy76-unscored-dispositions.md)。處置保留原始76分母與歷史，不是交易終態或validated；正式套用需另行確認。

2026-10-02 使用者明確「核准」76 筆固定範圍的追加證據版本、到期評分與可回復流程。固定批次 `hcs-legacy76-df03143a097e1e25`，完整 76 個 scope ID、原始 payload SHA256、原始 payload、10 個交易日和到期日見 `legacy76-revision-scope.json`。只涵蓋原先固定主樣本中的 76 筆 `insufficient_data/missing_ohlc`；不擴及其他歷史結果，不依報酬換版本。

## 寫入與保留

- `operational.sqlite3.trade_evaluation_results_v1`：不新增、不修改、不刪除原件；啟用前逐筆核對 SHA256。
- `trade_evidence_revision_batches_v1`：一列不可變清單與 SHA256，另有 active 開關；同 ID 不容許換清單。
- `trade_evidence_revisions_v1`：只追加新版本。revision ID 由批次、scope ID、已完成交易日、完整證據 payload 與政策雜湊產生；批次/scope/交易日唯一，重試不會多寫。保留行情原始列、擷取時間、provider 設定、SHA256、當時報告完整 snapshot 及其 SHA256。

新版本不默默代換原始績效；API 的 legacy_evidence_revisions 與報告摘要顯示批次／版本狀態。既有績效母體和原始結果仍保留。新增證據不能倒推當時可取得性；所有版本 `point_in_time_verified=false`、`actual_cost_verified=false`、`strategy_validated=false`。未知成本不當零。Neutral 僅在原始觀察契約有效時產生無交易結果。

## 每筆到期觸發

沿用現有回測輪詢（工作結束後約 900 秒再次檢查），不新增排程。使用 Asia/Taipei 的最新已完成交易日；收盤前不評估當日。需同時滿足批次 active、原件 SHA 不變、官方日曆仍等於 frozen 10 sessions、最新已完成交易日 >= maturity_date，才擷取報告日後至原定到期日的行情。未成熟不抓行情、不寫結果。

嚴格既有評分器要求完整且不重複的 10 根每日 OHLC、日期精確、商品/價格基準/公司行動可比性及可執行原計畫。資料缺口、價格基準未知、契約無法解析時保存未評分的新證據版本，不灌報酬；同日最多嘗試一次，隔日可重試未評分版本。已完成 target/stop/horizon/no_trade/not_entered/ambiguous 版本不再次抓取。ambiguous 不評正負報酬。

到期分布：10/02 5、10/05 4、10/06 18、10/07 2、10/08 5、10/12 10、10/13 14、10/14 2、10/15 7、10/16 9。所有原件 evaluation_date 缺失，不能證明原始缺資料原因是未成熟。

## 回復

以專案 Python 執行 `scripts/manage_legacy_evidence_revisions.py --deactivate-batch hcs-legacy76-df03143a097e1e25`。只改批次 active=0，停止後續取證；已追加版本仍保留，原件始終不變，既有績效未被新版本代換。啟用是冪等，重新執行 activate 不會復活已停用批次；重啟需另有明確授權流程。
