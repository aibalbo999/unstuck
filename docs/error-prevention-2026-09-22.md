# 錯誤防再發：修復候選、來源、狀態與限流觀測

本次源於 9/16–9/22 的 303 件新工作與 41 件品質終止，以及 2305 的正式失敗。它包含模型真錯與 parser 誤判；不以增加重試次數或放寬發布門檻處理所有原因。

## 修復候選與快取

2305 的最後一次修復曾讀回同一份被拒的 step cache。`llm_cache_policy` 現在以 task-local ContextVar，僅在當次品質／身分／來源／final-audit 修復呼叫樹略過 step 與 raw semantic cache 的讀取。完整稽核前的候選快取不等於已驗證結果；正常前序節點及並行工作仍使用原快取，不清空全域快取。原有限修復呼叫上限與 provider 扣帳維持。

採用修復呼叫範圍跳過兩層讀取，是為了讓尚未有拒絕收據的舊快取也不能成為「新」候選。這比只依文字hash過濾更保守，但只影響修復呼叫。provider 若再次產生相同內容，仍驗證、記錄重複並受原上限限制，沒有額外無限迴圈。

`repair_candidate_history` 記錄 agent、input／prompt／contract身分的hash、拒絕原因hash、候選hash、呼叫／失敗／重複數與cache讀取略過次數。它經實際節點 delta、平行節點 reducer 和 SQLite 往返；deferred 時保存到原有 unvalidated draft sidecar，failed repair只保留診斷而不接納被拒輸出。診斷追加寫入失敗會留下 warning，且不遮蔽原始失敗；首次原稿保存仍維持失敗即停止。`calls` 是 routed repair呼叫數、`call_failures` 是該呼叫拋出例外的次數，不能拿來當供應商HTTP計數或全部都是transport錯誤；供應商嘗試仍查原usage事件。取消不將候選當成功。

## 可核驗的事實與觀望

Agent23 prompt逐record明寫主體、期間、觀測日、數值、單位和source ref，每句須先通過原gate與allowed_paths；原始來源仍完整保留。修復提示另提供原文字元位置、解析到的主體／期間及同scope來源；其他可用來源僅是候選，不是原主張的證明。不增加容差、不跨段猜測5／30日，不把total當foreign。

交易執行契約只排除有界的「重新評估是否有明確進場時點」與「等待可驗證做空觸發後再評估」名詞片語；後續及跨句買入／開倉命令仍檢查。明確的營業利益率／費用率變化可作重新評估條件，其他必填條件仍須完整。Neutral不要求補造交易價格，也不能靠改Neutral標籤接受實際下單。

## 狀態與額度真相

分析工作新增execution_state等唯讀狀態欄位，保留舊status相容；等待、執行、品質終止與registry無法確認分開顯示。查驗實際RQ membership不做cleanup或enqueue，不依畫面倒數自動重送。

`llm_congestion_transition` 是units=0的觀測事件，記錄匿名attempt、generation、probe、原子轉移與等待期限；晚到success不等於recovered，cache-only探測釋放不等於provider成功。它不改變既有共享冷卻、半開單探測、RPD或backoff政策，也不增加request/error統計。記錄失敗不能遮蔽原provider錯誤。

本機預算以key slot/model命名，舊project欄位只保留相容alias並標示deprecated。既有「16個獨立project」是使用者規劃宣告；沒有可驗證slot→project映射，verified project count仍未知。尚不啟用假定共享project的新限流，也不在沒有probe成功後再爆量證據時任意增加恢復限制。

## 驗證與發布

所有一般測試經`tests/run_prompt_boundary_tests.py`，禁止正式Redis／API／模型網路。歷史fixture以原輸入、原文、版本和hash重播，缺證據明示未知；保留原artifact與原判定，現版重評另存。全模式的真錯、缺來源、取消、重啟及manifest身分是必要反例。

正式發布以實際commit、runtime identity、health、原報告hash、設定、RQ排程和RPD標記核對。分批canary只有在前批完成並核對來源／品質後才擴大；waiting_retry不是品質通過，模型可用性不足時保持未驗證，不重複強制提交。

本機實作及正式驗證證據目錄：`stock-error-prevention-release-20260922.bbjudp_a`；當日原始稽核與方案在`stock-error-prevention-20260922.r5y1rr_f`。各項驗證結果以該目錄實際紀錄為準。
