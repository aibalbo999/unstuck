# 四模式 OOS 隔離驗證設計

日期：2026-09-06。基準程式：`fec17737`。

狀態：**使用者已於 2026-09-06 核准本書面規格；合成／離線 OOS 隔離設施已於 2026-09-07 實作並驗收。真實前瞻 cohort 與成熟 OOS 績效仍未建立。**

## 1. 目的與非目標

建立可以重現、查驗樣本分母與保留未知狀態的研究流程。第一個交付只使用合成／離線 fixtures 驗證封存、準入、評估與摘要，不抓行情、不呼叫模型，不從正式歷史報告事後選出有利樣本。

本批與 [PostgreSQL 隔離驗證](2026-09-06-postgres-isolated-verification-design.md) 分開驗收；先完成 PG 批次，再執行本批獨立計畫。OOS 儲存不依賴 PG，也不沿用正式 operational DB。

不包含：改變四模式分析建議或正式回測規則、增加投資策略、調參／顯著性檢定、實盤交易、任意歷史報告重建、正式 cohort 收樣、排程／外部行情匯入、push、merge、runtime 重啟或 UI 改版。

真實前瞻研究的 ticker universe、期間、版本、主要指標與成本政策，必須在未來另次啟用前固定。本文件核准不是正式分析／收樣任務的授權，也不是回溯資料可改稱前瞻資料的依據。

## 2. 現有核心與不可直接使用的入口

- `backend/decision_backtest.py`：純 `add_calendar_months()`／`evaluate_prediction()`，A 使用 3／6／12 曆月。
- `backend/trade_path_backtest.py`：純 `evaluate_trade_path()`，支援 OHLC、交易期限、未知成本與保守成交狀態。
- `backend/mode_trade_backtest.py`：已有 B `position_plan`、C `short_setup`、D `trade_setup` 契約。僅重用或抽出純解析，不呼叫混合抓行情與保存的 `evaluate_report_trades()`。
- `backend/report_reproducibility.py`／`backend/prompt_loader.py`：沿用現有 prompt fingerprint、code、model、資料 hash 與生成時間，不另造另一套版本真相。
- `backend/data_trust_snapshot_integrity.py`：可重用 hash 計算，但研究準入需額外要求 hash 存在；既有 verifier 對完全沒有 hash 的相容行為不是準入通過。
- `backend/outcome_calibration.py`：可參考品質分組，但目前 filename join 與空集合 `0.0` 不符本研究契約，因此新增嚴格純摘要，不直接搬用結果。

禁止研究 runner 呼叫 `run_due_backtests()`、`compute_performance_stats()`、正式 `trade_backtest_store`／`decision_tracking_store` 或 dashboard 的 50／2000 筆截斷摘要。它們不是凍結全 cohort 的隔離入口。

## 3. 元件與資料流

採用**獨立研究目錄＋不可覆寫的 JSON records／content-addressed blobs**，不建立正式 DB table 或新 API。相較直接複製 production backtest store，這能避免 filename／horizon upsert 覆蓋不同研究版本；代價是需明確實作原子寫入與完整清單驗證。

固定資料流為：登記研究規則 → 記錄完整候選清單 → 驗證並封存每份候選 → 匯入凍結的離線價格資料 → 依模式評估 → 以完整 ledger 產生摘要。評估器不讀目前報告索引，也不根據績效回頭修改規則。

| 元件 | 輸入／輸出 | 責任界線 |
| --- | --- | --- |
| manifest schema／hash | 明確研究設定 → 凍結 manifest | 不選股票、不抓資料、不代填缺失研究政策 |
| isolated study store | 明確 root／JSON／bytes → 原子、不可覆寫 records | 只在本次研究 root 內，不接受 production path 預設 |
| candidate／admission | 凍結候選與原始 bundle → 狀態、理由與版本身分 | 所有候選留在 ledger；缺證據不能刪出分母 |
| dataset validator | offline prices／bars／calendar／provenance → 可用性與 hash | 不連網、不補缺 bar、不推測公布時間 |
| mode evaluators | 通過準入的 immutable inputs → 各模式結果 | 重用純核心，不進正式服務或 store |
| strict summary | 完整 ledger／results → JSON 與簡短 Markdown | 全量聚合、分母可核對，不把未知輸出為零 |

評估核心只收參數，不 import runtime config、DB store 或 fetcher。薄 CLI 負責明確檔案輸入、驗證與寫入；路徑未指定立即失敗。新檔案依上述責任拆分，不把所有流程堆成單一模組。

## 4. 研究種類與不可變身分

`study_kind` 分成三類：

- `synthetic_validation`：合成 fixtures，用於本批驗收，不進任何真實績效聲稱。
- `retrospective_replay`：已知歷史輸出的研究重播；即使 hash 完整，也不得自動升級為前瞻 OOS。
- `prospective`：先登記規則，未來依規則收樣，且報告在可評估結果出現前已封存。缺事前時間證據只標記待核實，不因使用者填了此字串而通過。

manifest 至少固定：`schema_version`、`study_id`、`study_kind`、UTC 登記時間、選樣期間與時區、完整 ticker universe、模式／允許版本、候選生成及版本選擇規則、主要期限／指標、排除規則、價格／交易日／成本／benchmark／企業行動政策與 evaluator 版本。

manifest hash 使用版本化 canonical JSON 規則：UTF-8、固定 key 排序與分隔、禁止 NaN／Infinity，hash 欄位本身不參與計算。原始 artifact bytes 另做 SHA-256，不以 JSON 重排後的 hash 取代原檔 hash。

同一 `study_id` 不允許第二份不同 manifest；修改規則只能另建 study，保留原研究。每次登記、候選輸入與 admission 形成不可覆寫 record；研究目錄不是可任意更新的「最新版」資料夾。

應用層不可覆寫與 hash 只能提供一致性／篡改偵測，**不能單獨證明事前登記時間或防止主機管理員重寫所有檔案**。未來真實 prospective 啟用必須帶可查的事前登記與封存 receipt（來源、時間、內容 hash），並分開記錄其驗證狀態；本批不建置外部公證服務，也不把本機 mtime 或自填 timestamp 當獨立證據。

## 5. 候選清單、準入與時間界線

候選清單記錄每個預定 ticker／模式／產製時段與報告版本選擇規則；正式未來接入時還需完整生成事件／遺漏報告對照。當前只支援明確提供的離線 candidate inventory，不從最新報告或命中結果倒推候選。

每一候選都有唯一 ID 與 admission record，狀態包括 `admitted`、`excluded_by_protocol`、`insufficient_provenance`、`integrity_failed`、`missing_report`。多個理由用穩定 reason codes 保存；評估 `pending_horizon` 與是否準入分開。

每份 report bundle 至少保存：

- 原 HTML／Markdown／snapshot bytes 與各自 hash、資料 snapshot canonical hash、parsed plan hash，以及原始 filename／ticker／pipeline identity；不以相同 filename 當版本相同。
- `conclusion_generated_at`、報告實際可得時間／時區與封存 receipt；若只有生成時間而無可得時間，不推測報告已可交易。
- 使用到的資料公布／首次可得時間、來源時區及證據；`fetched_at`、財報期末日與 snapshot refresh time 不能替代公布時間。缺證據維持 `insufficient_provenance`。
- prompt version／完整 fingerprint、code commit／dirty、實際 model ID 與可取得的 fallback route。只有可變 model alias 時另標 revision unknown，不能捏造 provider 版本；是否允許 alias 必須在 protocol 明定。
- 產製時的 quality metadata 與其 hash；缺失保持未知，不用今日 current-quality projection 補成當時通過。

snapshot 若顯示結論後只刷新資料，且無原始分析時快照，不可當作原分析輸入。完整 hash 只能證明本次保存內容，不能解除這個時間矛盾。

時間驗證一律使用帶時區 timestamp，另保存交易所 session date；naive timestamp 不自動補 UTC。每項實際使用之輸入版本的首次可得時間必須 `<= analysis_input_cutoff <= conclusion_generated_at <= report_available_at`；缺證據保持不足，已知逆序拒絕準入。即使資料在評估前已公布，若晚於結論產生，仍不能當成當時的分析輸入。

首個評估 session 固定為報告可得日期（交易所時區）之後第一個 calendar session，不使用可得當日資料；此錨點不隨封存時間移動。`prospective` 要求結論生成後、該 session 開始前完成封存，逾期回 `late_seal`、不可評分，不能移動基準日以補救。真實 prospective 還需登記早於選樣開始及可查 receipt。`retrospective_replay` 可在結果已知後封存，但始終明示回溯，仍沿用原報告可得時間作錨點，不取得 prospective 身分。合成時間序列只能證明驗證器行為。

候選 inventory 有 `coverage_status=provisional|closed|incomplete` 與內容 hash；未證明收樣完整時仍可出示已收資料，但摘要必須標示分母不完整，不可宣稱完整前瞻 cohort。停牌、下市、缺報告與被排除候選仍留在 ledger，不因沒有價格而消失。

## 6. 離線價格輸入與研究政策

價格資料需含 provider／來源識別、取得時間、來源／交易所時區、session dates、每個 bar 完成時間、資料截至時間、原始或調整價政策、企業行動資訊，以及 dataset／calendar hash。

本批使用原始價格與明確 session calendar fixtures；只接受完整收盤後資料。calendar 已到期但缺 bar 是資料不足，不是延長期限等待下一個可用 bar；calendar 尚未到期才是 `pending_horizon`。重複日期、非有限或非法 OHLC、時區矛盾、部分當日 bar 均不可默默修補。

若 evaluation window 涉及未處理的拆股／除權息，或企業行動狀態未知，結果不可當可比較的交易 ROI；保留明確不足理由。本批不新增企業行動調整演算法。

成本未提供時 net ROI 為 `null`；提供時沿用 `transaction_cost` 的「每股來回成本金額」單位，不當成百分比。成本組成、適用 currency／shares basis 與未含項目明示；不把未知稅費、借券費、滑價、股息或融券可得性猜成零。

benchmark 預設可為明確 `not_provided`，此時 excess 為 `null`；提供時需同一凍結期間、幣別、價格政策與來源證據。沿用核心所得為 gross excess，不冒稱扣成本後超額報酬。MDD 等核心未計算的欄位維持 `null`。

## 7. 四模式評估契約

| 模式 | 期限 | 本批評估語意 | 不得混用 |
| --- | --- | --- | --- |
| A／v1 | 3／6／12 曆月 | 純預測校準，未模擬成交 | 不套 D 的 5／10 日，不稱實際交易報酬 |
| B／v2 | `position_plan` 明示的交易日數 | 新進場／等待的交易路徑；既有部位動作需歷史 | 不為減碼／續抱捏造持倉成本或股數 |
| C／v3 | `short_setup` 明示的交易日數 | 空方／避免契約與保守 OHLC 路徑 | 不把事件＋價格複合條件簡化成純價格 |
| D／v4 | 5／10 交易日 | `trade_setup` 路徑，各期限獨立輸出 | 一份報告兩期限不算兩份獨立報告 |

A 本批實作薄研究 wrapper，直接重用 `add_calendar_months()`／`evaluate_prediction()`，不使用現有抓價服務的 nearest-close fallback。基準價採第 5 節固定首個評估 session 的收盤價；到期日由報告可得時間的交易所日期加曆月，終點採到期日當日或之後第一個 protocol calendar session 的收盤價，該 session 未完整結束仍為 pending。強制 `baseline_session < endpoint_session`，否則回 `invalid_evaluation_window`；過晚封存不能改動基準或到期日。所有選價身分進 result。

A 的 recommendation 必須由凍結 parsed 原始欄位明確提供，不以 schema 預設的「持有」補缺值。未知 label 為不可評分，不沿用核心的 unsupported→miss。基準價、到期價及有提供的 target 均要求有限正數且不是 bool；零、負值、NaN／Infinity、不可解析或 bool 價格回 `invalid_price_input`／`invalid_target_price`，不能交給核心變成命中。

買入／放空以方向＋目標校準為主要分類；target 缺失或非法時主要 outcome 與 target error 保持未知，不進主要分母。若 protocol 明確啟用方向-only，僅在 recommendation、基準與到期價格均有效時另列 `metric_basis=direction_only`，保留 target 不足理由，不混入主要命中率。買入的 target 90%、放空的 110% 與持有 ±10% 門檻沿用現有核心並寫入凍結政策，不視為本次策略最佳化。

A 的「避免」與「持有」分別標示現金零利息及既有多頭假設，只作預測校準；不把它們與可執行的新交易 ROI 混算。A 三期限相關，未成熟先回 pending，不縮短期限以取得結果。

B／C／D 從第 5 節固定首個評估 session 起，只提供經 calendar 證明完整的 sessions 給純 evaluator；prospective 另先通過封存期限檢查。核對明確 direction／期限／價格／成本契約，缺失或未知 direction 不回退成 Long。保留 `not_entered`、`no_trade`、`ambiguous`、`insufficient_data`，未知不算 miss。

事件觸發、價格與時間條件不能靠抽取其中一個數字替代；未支援的完整條件回 `unsupported_conditional_entry`。同根 target／stop 或盤中成交後先後不明保留 ambiguous，不能挑有利順序。等待／避免的零 ROI 只限明確現金無部位政策，並與交易樣本分開。

## 8. 不可覆寫結果與摘要分母

result identity 至少綁定 `study_id + candidate_id + report_bundle_hash + horizon_unit/value + evaluator_version + dataset/calendar_hash + policy_hash + as_of`。同一身分及 frozen inputs 重跑必須輸出相同評估 payload；不同內容不能覆蓋既有 record。pending 隨新 cutoff／dataset 成熟時建立新 evaluation revision，保留舊紀錄。

執行耗時／觀測時間另放 run metadata，不混入 deterministic payload。摘要必須指定 evaluation revision 集合與 cutoff，不能把同份報告的歷次 pending／成熟結果重複計數，或由「最後寫入」隱含選版本。

摘要分開提供：

- 候選總數、inventory 完整性、每種 admission 狀態及排除原因。
- 不重複報告數、ticker 數與各 horizon 的結果數；「不同報告」不宣稱統計獨立，同 ticker／重疊持有期明示相依。
- 每種模式／期限／metric basis 的成熟、pending、不可評分、未成交、觀察、ambiguous 與可評分數。
- 命中率只用明確 hit／miss 作分母，並同時顯示可評分數與全體候選數；未成交／觀察不混入交易勝率。沒有可評分樣本，命中率與平均 ROI 都為 `null`。
- gross、net 與 benchmark 各有可用樣本分母；成本未知者不進 net 平均。A 預測、B／C／D 交易、現金假設及 direction-only 結果分組呈現。

摘要由完整 ledger 計算，若明細分頁必須明示 total／returned／truncated；不得沿用 production 50／2000 筆上限當作完整資料。hash／record 缺失或互相矛盾時摘要 fail closed，不輸出看似完整的 aggregate。

## 9. 隔離、寫入與失敗處理

- 使用 PG 批次的已驗證隔離啟動基礎，但 OOS profile 不啟動 PG；容器 network=none、沒有正式 DB／artifact 或主機 socket mount。只複製白名單程式與合成 fixtures，結果經明確匯出步驟取回。
- root 必須是本次建立的研究暫存目錄，正規化並核對所有輸入／輸出路徑；空 path、根目錄、repo root、正式 cache/output、`..`、symlink 與越界路徑一律拒絕。不得靠預設 config 補 root。
- store 以 exclusive create、驗證既有內容、同檔案系統原子提交處理重跑；衝突非靜默覆蓋。並行寫入及中斷不留下可被認為完整的半檔；讀取時重新驗證 hash，缺 record 或損壞不當成空研究。
- malformed manifest／hash 衝突／隔離失效使命令 nonzero；個別候選缺資料是可記錄的科學狀態，不使其他候選消失，也不直接成為研究命中率失敗。
- 只匯出本次研究 JSON／Markdown／驗證 log；不含 secrets、正式 artifact 或未授權原始資料。清理限本次容器與臨時資料，不清理正式或共用資源。

## 10. 最小驗收矩陣

| ID | 驗證 | 通過條件 |
| --- | --- | --- |
| OOS-01 | root／網路／正式 DB 邊界 | 不指定 root、越界／symlink、外部連線與正式 store import 均被阻止 |
| OOS-02 | manifest／record immutable | 缺必填、未知政策、NaN／Infinity、hash 篡改、同 ID 異內容與並行衝突明確失敗 |
| OOS-03 | 四模式 admission | artifact／snapshot／plan／prompt／code／time 驗證各有正反例；缺 hash、dirty 未符合政策、只刷新舊結論、未知公布時間與「公布晚於結論但早於評估」不通過 |
| OOS-04 | 時間與研究分類 | retrospective 不升級 prospective；自填 timestamp／mtime 不當外部 receipt；prospective 首個 session 後甚至跨到期封存為 late_seal、不移錨點；合成資料始終標示 synthetic |
| OOS-05 | A 預測 | 3／6／12 曆月、月底／閏日、休市後到期、未成熟與起訖順序；缺 label／target、零／負值／bool／非有限／不可解析價格不產生主要命中；direction-only 分組及 unsupported 不算 miss |
| OOS-06 | B／C／D 路徑 | 既有 5／10D、short gap、未成交、現金觀察、同根 ambiguous、未知成本；缺 B/C 期限與需部位歷史明示不足 |
| OOS-07 | dataset／事件 | 缺 session、重複 bar、當日未完成、調整價混用／未知企業行動、缺事件時間均不可冒充完整結果 |
| OOS-08 | 重現性 | 同 frozen inputs 輸出相同；變更 artifact／bar／calendar／政策／cutoff 拒絕覆寫或建立獨立 revision |
| OOS-09 | 分母與摘要 | 0 個可評分是 null；單報告多期限不重複算報告；超過 50／2000 筆仍全量；缺 record 或 revision 衝突拒絕聚合 |
| OOS-10 | 端到端離線重播 | 合成四模式 cohort 經登記、準入、pending 到成熟新 revision、摘要、重跑、匯出與清理；真實 prospective 樣本數仍為 0 |

沿用隔離 runner 執行新增測試及 `tests/test_mode_decision_backtest.py`、`tests/test_outcome_calibration.py`；若抽出解析或修改公用 helper，補相關 import-boundary、mode contract 與原服務相容性回歸。測試以失敗反例先行，純函式回歸與端到端容器驗證分開記錄。

交付需保存 study／inputs／evaluator／image 的版本及 hash、驗收案例對照、test totals、完整 synthetic 摘要、隔離與清理證據；不引用舊測試計數當成本批完成證據。

## 11. 完成定義與後續分界

本批完成需 OOS-01～10 與相關回歸通過，並交付可重現的離線研究 bundle。此時可說「OOS 隔離設施驗證完成」，但仍須分開列示：

1. 真實 prospective protocol／cohort：尚未啟用或登記。
2. 真實前瞻樣本：尚未收集。
3. 成熟前瞻績效／優化效益：尚未驗證。

日後真實研究需先核定 universe、收樣／缺樣證明、時間 receipt、版本與價格政策，再以未來樣本執行。D 最早仍需實際後續 5／10 交易日；A 是 3／6／12 個月，不能把完成測試設施寫成所有優化效果已證明。

## 12. 審核狀態

- [x] 四模式現有純核心、期限與正式副作用入口已盤點。
- [x] 使用者已同意離線 fixtures、樣本／版本凍結與不宣稱成熟績效的界線。
- [x] 規格已自我檢核未知值、時間、分母、重現性及隔離語意。
- [x] 使用者檢視並核准本書面規格（2026-09-06）。
- [x] PG 批次完成後建立並執行本批獨立實作計畫。
- [x] 離線隔離設施驗收完成。

## 13. 合成離線實作證據（2026-09-07）

- 純研究核心：`backend/oos_research/` 的 manifest、canonical hash、不可變 store、candidate admission、provenance、dataset/calendar/policy validator、A 與 B/C/D wrapper、evaluation revision 與完整 summary。
- 驗收案例：`tests/test_oos_research.py` 的 OOS-01～10 共 `11 passed`，`tests/test_oos_validation_contract.py` 的隔離結果／bundle 契約共 `7 passed`；合併 OOS lane `18 passed`，既有 mode regression `154 passed`。
- 容器 evidence：image `sha256:03e72007e0935195d42d91abb51fe3456bca02e083dbbec829feed6a43781ceb`；`network=none`、read-only root、非 root、只有 `/tmp`／`/results` tmpfs、`Mounts=[]`；結果 `10 passed / 0 failed / exit_code=0`，精確 CID 已移除。
- 輸出界線：CLI 只接受明確 manifest／inventory／dataset／root；研究 bundle 不使用正式 config、PG、fetcher、formal store 或 API。合成研究不外推投資績效。
