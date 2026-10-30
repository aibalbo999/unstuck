# 2026-10-27 保存來源缺口查核與隔離修復

查核截至 2026-10-27 22:39:41 Asia/Taipei。正式 checkout、資料庫、報告與服務均未修改；本文件及變更只位於隔離副本。正式 `reports` 索引以 SQLite `mode=ro` 讀取，實體內容由 `ReportArtifactLocator` 搭配沒有寫入／加鎖方法的唯讀 adapter 載入。取得 API、模型、掃描、交易與固定 76 回填均為 0。

## 範圍及可重現證據

一次全量選取重現 **209 個股票 × pipeline 最新版本**；其中 **181 份 v4** 逐份查核，讀取錯誤 **0**。正式程式基線重現 `v4_trade_reason_source_missing` **80 份**；同批保存的歷史 `content_credibility` 沒有這個封鎖，80 均是當下投影產生，不能解讀成當初生成時 80 次來源取得失敗。

- [基線分類與逐引用證據](audit-source-gap-20261027.json)
- [隔離修復後逐引用比較](audit-source-gap-20261027-after.json)
- [唯讀重現工具](../scripts/audit_saved_source_gaps.py)

工具 stdout 是唯一輸出；文件中的 JSON 由呼叫端重導至隔離 docs。它先比對保存引用身分與重建目錄，不補引用、不修改字句、不把相似數值當作替代來源。腳本可以指定 `--code-root`，避免把修復後的結果冒稱原始基線。

```bash
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' \
  scripts/audit_saved_source_gaps.py \
  --index '/Volumes/X10 Pro Mac/stock-agent/backend/cache/stock_agent_cache.sqlite3' \
  --output-root '/Volumes/X10 Pro Mac/stock-agent/backend/output' \
  --code-root '/Volumes/X10 Pro Mac/stock-agent' --as-of 2026-10-27 --details
```

去掉 `--code-root` 即查核隔離程式。`--as-of` 只控制這次離線查核的時間，不能改寫原始來源時點。

## 80 份的分類

下列四組主分類合計 80。第一層「原目錄可綁定」表示保存 packet、frozen input 與 catalog 身分一致；**不表示原件真實、歷史 PIT、生成輸出引用也已完全驗證**。修復還會核對輸出使用的 fingerprint。

| 主分類 | 份數 | 具體判斷 |
|---|---:|---|
| 保存輸入／目錄中有來源，但現在超過窗口 | 60 | 法人 7 日、新聞／持股 14 日的窗口過期；不應標成從未有來源 |
| 仍在窗口，但目錄重新編號造成路徑失效 | 1 | 3231 原 `records[13]` 在現在目錄變成 `records[9]` |
| 保存目錄或原始輸入不足 | 7 | 2891 的 frozen input 超過 512 KiB 預算而 omitted；另 6 份 manifest unknown |
| 根本沒有明確引用的法人主張／含混條件 | 12 | 不自動補引用或刪除文字；其中有歷史實際主張，也有需要人工判讀的混合未來條件 |

重疊子因：無明確引用共 **16 份**（上表 12 份，加另 4 份同時缺保存目錄）；**3 份**引用整個 event_calendar 物件等非可用觀測。這些不能相加當總數。

另外在整個 181 份集合中找到 **8 份「同一索引現在指向不同紀錄」**，加上 3231 共 **9 份索引漂移／重綁風險**。八份為 6282、3653、3017、3324、2367、2308、6409、1623；完整 filename 與值在基線 JSON。不能只檢查索引是否存在：存在也可能指錯資料。

3231 的可核實例子：2026-10-21 報告引用 `short_term_market_context.institutional_evidence.records[13]`，保存原值是 2026-10-20 三大法人合計單日 **42,702.8 千股**。10/27 仍在七日窗口，但當前重建目錄會濾掉較早紀錄，使原值移至 `[9]`，原 `[13]` 不存在。現有 `source_catalog(data)` 預設使用查核當日，重建後的索引因此不具歷史穩定性。這是已證程式缺口，不是由結果數量猜測。

2025 的原 `[13]` 是 10/19 單日 **-146.46 千股**，到 10/27 已八日，屬合理過期。1301 的撤回均線論述不在本修復的放行範圍；保留舊資料不能復活舊推薦。

## 實作行為

新增 `saved_trade_source_identity.py`，正式品質檢查經 `content_credibility.py` 傳入 snapshot：

1. 保存報告只用通過現有 `validate_analysis_evidence` 的原始 packet。原始 input、catalog、visible/version、input fingerprint、輸出的 `source_assessment.source_fingerprint` 及保存日期都需可綁定；缺件保持 `source_binding_unverified`。另要求原始 input、目前 data、catalog 及存在時的 snapshot ticker 一致；紀錄若明列 ticker 也必須相同。不把 TW、TWO 或無市場後綴混為同一身分。
2. 使用保存目錄的原索引，不用今天目錄中的同名索引，也不搜尋相似紀錄自動補證。法人 lineage 以 frozen input 重算，不能拿後來刷新過的資料冒充原分析輸入。
3. 同時獨立檢查目前有效窗口。原來源存在但過期改列 `source_stale`；觀測晚於保存目錄或查核日列 `source_future`；日期缺證列 `source_date_unverified`。已過事件日期不能當未來催化，事件日期也不冒充發布日期。
4. 新 prompt 的 `source_catalog` 支援明確 `as_of` 並採台北日期，避免 UTC 跨日不同步。這不是重建舊引用的替代方案。
5. 不改來源准入門檻、不刪除既有封鎖、不把 hash 當官方證據、不覆寫現存 artifact。

輸出綁定多核一層後，原 60 份中有 1 份（3703）轉為 `binding_unverified`；因此不能把 60 全部稱為完整已驗證。3653、3017 的輸出 fingerprint 也不符；5880、2891 因 frozen input omitted 保持未知，即使有其他財報原件，也不能借此補足交易來源輸入。

## 非持久化前後比較

這是 **trade-basis 子檢查**，不是整份報告 passed 數。每份可有多個原因，數量重疊。

| 修復後原因 | 原 80 份 cohort | 全部 181 份 v4 |
|---|---:|---:|
| `v4_trade_reason_source_stale` | 59 | 89 |
| `v4_trade_reason_source_missing` | 24 | 28 |
| `v4_trade_reason_source_binding_unverified` | 8 | 12 |
| `v4_institutional_lineage_unavailable` | 8 | 8 |
| `v4_unverified_fcf_as_catalyst` | 4 | 5 |

原 80 份只有 **3231** 不再有 trade-basis 封鎖；它仍受行情、法人時效、原始來源等其他品質規則限制，**不代表整份報告通過或可以交易**。89 份 stale 包含以前未被七日保存基準攔住、但目前確已過期的技術引用；這是將目前可用性獨立檢查，並非降低門檻。

## 驗證及限制

先觀察新測試 8 項 RED，再實作；最終 **164 項相關隔離測試通過**。使用專案 runner，SQLite 路徑隔離、socket 禁網。覆蓋正例、索引縮短、相同索引改指他物、真缺引用、過期、保存時點未來觀測、缺 frozen input、錯誤輸出 binding、刷新資料不得借用、事件過期、分母去重、唯讀與路徑逸出保護。獨立審查另外找出跨股票拼接缺口，已補精確身分檢查及兩項反例；修正測試 fixture 的物件共用問題後整組重跑通過。

```bash
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' \
  tests/run_prompt_boundary_tests.py \
  tests/test_saved_trade_source_identity.py tests/test_saved_source_gap_audit.py \
  tests/test_trade_catalyst_reassessment.py tests/test_trade_catalyst_semantics.py \
  tests/test_trade_source_completion.py tests/test_trade_source_precise_guidance.py \
  tests/test_trade_price_reference.py tests/test_content_credibility.py -q
```

這次核對保存結構、值、時間及原始輸入身分，沒有逐筆重新對官方原件做事實核驗，沒有證明歷史可取得時點，也沒有驗證未來報酬。12 份無明確引用中的混合未來條件保留人工判讀，不以推測改寫既有論述。本文結果不能作正式部署或重新生成授權；部署、付費模型、正式報告重建及固定 76 仍保留給父線確認。
