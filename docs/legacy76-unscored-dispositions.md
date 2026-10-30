# 固定 legacy76 批次的未評分處置（待正式套用）

本次僅開發與隔離測試。正式來源、DB、批次狀態與服務尚未套用；部署與寫入處置都要另獲明確確認。

## 範圍與不變量

- 唯一適用批次 `hcs-legacy76-df03143a097e1e25`，固定 manifest SHA256 `df5413aee36f3e6f142a52f0570be5036513a228fa840412b110e0808d3b7720`、76 個原始 scope。
- 原始 `trade_evaluation_results_v1`、報告 artifact、manifest 與 `trade_evidence_revisions_v1` 不改寫。處置日誌不送入績效 population 或評分器。
- `close_unscored` 是停止一般缺證輪詢的審閱處置，沒有報酬、輸贏、成交或 validated 意義，不能標作 `no_trade`。
- 另有 `reopen` 追加事件，必須引用當前 close event；不刪除、不覆蓋既有日誌。
- scheduler 不自動建立處置、不改 900 秒完成後等待、不新增排程。其他批次不讀取本批次處置。

## 預覽與人工審閱

`scripts/manage_legacy76_dispositions.py preview --db <explicit-existing-db>` 僅用 SQLite `mode=ro`，不抓來源、不重評、不建立資料表。沒有環境推導的 DB 預設，避免查錯資料庫。

預覽提供原始分母、交易終態、未評分處置、未解決 scope、每筆原因、原非法價位、官方格點規則連結、原件來源收據、最新版本證據日與保存時間、最早保存的交易計畫綁定。會核對最早與最新保存計畫一致；不是當時可取得性證明。

三筆 `invalid_original_price_grid` 僅為關閉提案：2030 原停損 24.09（格點 0.05）；1301 原進場 65.07／停損 61.07（格點 0.1）；6456 原進場 85.84／停損 81.09（格點 0.1）。不調整任何價位。

6715、2464、3016 預設保持 `review_required`，不因欄位缺少推定不可復原。若日後要以 `unrecoverable_original_evidence` 關閉，需保留具名審閱、明確結論、原始 generation inputs 與 historical archive 兩類查找收據；每份收據內含來源識別、搜尋時間、範圍綁定、查找結果、具體 finding，並核對其 SHA256。這是可稽核的人工處置依據，系統不自動證明資料不存在，更不證明 PIT。

審閱 request 格式：

```json
{
  "batch_id": "hcs-legacy76-df03143a097e1e25",
  "reviewer": "具名審閱者（正式確認後填入）",
  "review_note": "審閱原計畫、價位與引用原件後的明確處置依據",
  "items": [{
    "scope_id": "從預覽 request_binding 原樣取得",
    "revision_id": "從預覽取得",
    "revision_payload_sha256": "從預覽取得",
    "original_payload_sha256": "從預覽取得",
    "manifest_sha256": "從預覽取得",
    "earliest_revision_id": "從預覽取得",
    "earliest_plan_sha256": "從預覽取得",
    "action": "close_unscored",
    "reason": "invalid_original_price_grid"
  }]
}
```

未確認範本的 reviewer／review_note 為 null，程式會拒絕套用。不得把開發同意當正式處置同意。

## 正式確認後才可操作的步驟（本次未執行）

1. 逐檔確認正式來源仍等於開發副本的 baseline；有其他修改時重新合併與測試，不直接覆蓋。保存相關來源與 DB 一致性備份。部署／受控載入另外確認，不在本次授權內。
2. 將確切三筆提案與理由交由使用者確認；填具名審閱者與 note。針對最新正式 DB，執行 `preview --db <db> --request <reviewed-request.json>`，審核其內容與 `preview_sha256`。
3. 審核確認後才使用 `apply --db <db> --request <reviewed-request.json> --confirm-preview-sha256 <request-bound-preview-hash>`。單純不帶 request 的診斷預覽雜湊不能用作套用確認。
4. apply 以單一 SQLite transaction 重核 manifest、原結果 SHA、版本綁定、preview fingerprint，再僅追加 `legacy76_scope_disposition_events_v1`。資料變動須重新預覽；重複同一決策冪等。
5. 若當時仍為 70 no_trade／6 未解決，三筆處置後應為 **70 交易終態 + 3 未評分處置 + 3 待補證 = 76**。`terminal_scope_count` 保留交易終態語意；新增 `unscored_disposition_scope_count` 與 `settled_scope_count`；既有版本數、績效與 validated 不因處置改變。

## 回復

保留原碼版本與新日誌。要恢復某筆輪詢，以新的具名 request 使用 `action=reopen`、`reason=review_reopened`、`reopens_event_id=<目前close event>`，並重新預覽／確認。此操作只追加日誌；既有輪詢會在原同日防重試與證據日規則下重新處理，因此 reopen 本身也需授權。

若回退程式，保留 journal 與所有原始表，不刪表或改結果；舊程式會忽略 journal，重新沿原規則輪詢六筆。服務載入／回退仍需另外確認。

## 錯誤、來源與日期

- `errors`：執行例外；固定批次另列 stage、exception type、scope、證據日；日誌不記 provider error 的私密文字。
- `validation_rejections`：本輪真正執行驗證後得到的未評分拒絕，獨立於例外；同日略過不假裝重新驗證。
- `awaiting_source_evidence`：來源閘門尚未通過；不寫 attempt，仍按原規則可重試。
- 摘要同時列 `as_of_completed_session` 與 `as_of_evidence_session`；後者以台北22:30界線計算。界線不是來源最終性保證。

歷史合格價格全期對齊路徑仍未實作；不放寬 `provider_raw_basis_not_established`。PIT 與實際成本仍未驗證，所有 strategy validated 宣稱仍為 false／0。不可把現在身分／價格或假設成本回填成當時事實。
