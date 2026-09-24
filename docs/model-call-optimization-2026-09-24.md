# 模型呼叫與資料單位修正（2026-09-24）

本輪依正式工作 `6da5bce519674eb1b51736a0a798bad4` 的事件、保存輸入與最終報告核對。該工作產生報告且自動 gate 全數通過，但不代表研究內容全面正確。

## 殖利率單位

`data_fetch/yfinance_payload.py` 的 `dividend_yield_raw` 原本以百分點顯示，例如 raw `0.19` → `0.19%`。舊 prompt 與 DDM 工具卻按 ratio 再乘 100，造成模型讀到 `19.0%` 並誤判高殖利率。

新 payload 明示 `dividend_yield_raw_unit=percentage_points`。`dividend_yield_units.dividend_yield_pct()` 統一供 prompt 與 DDM 使用；明示 ratio 才乘 100。舊 snapshot 以相容的百分比顯示值核對，未知或互相矛盾的單位回傳不可用，不以數值大小或不同期間的 dividendRate/price 猜測。毛利率與 payout ratio 維持各自既有契約。DDM 的高殖利率條件仍是 5%；金融業的既有獨立條件不變。

同一舊 snapshot 的實際 rendered prompt 與 step cache key 會改變，原報告及原始來源資料不回寫。若前序分析已引用錯誤殖利率，必須完整重跑；只換最後建議不能修正前序理由。

## 缺少逐字稿的修復

Agent 20 初始執行已有無逐字稿時的 deterministic 不可評估結果。final-audit 依賴重建現在共用同一規則，避免在沒有新逐字稿的情況下再次呼叫模型及反思。仍執行取消、身分、輸出品質、結構契約與依賴版本檢查；通過單一 Agent 契約也仍須整份報告稽核。有逐字稿時維持模型路徑。

## 按已保存進度計算退避

`workflow_checkpoints.py` 在模型暫時不可用時，透過 `analysis_retry_progress.py` 讀取已提交的 root checkpoint，將 thread、輸入身分、目前待執行節點及已完成節點的版本憑據附在內部例外上。`analysis_job_retry.py` 只在連續且相符的紀錄證明前一失敗節點已完成後，讓新階段使用自己的 300／600／1,200／1,800 秒退避；回訪舊節點保留累積次數，同一未完成節點不能因重試或新的候選文字重設。

原全工作 availability count、provider quota policy、RQ retry budget 及來源回傳的等待時間保留。來源等待時間與本機退避取較大值；缺少進度憑據、舊 metadata、損毀或身分不符時，沿用保守的原全工作退避。這不提前修改已排定工作，不刪除共享 cooldown、RPD 或排程鎖。

原工作的八次等待為 300、600、1,200、1,800、1,800、1,800、1,800、1,800 秒。按已確認的 Agent21 → final-audit 進度重播，排程等待由 11,100 秒變為 7,800 秒，差 55 分鐘；這是固定同一失敗序列的反事實回放，尚非正式服務觀察到的加速，也不保證供應商稍早恢復。

## 驗證與限制

測試一律使用 `tests/run_prompt_boundary_tests.py`，隔離 DB 並禁用供應商網路。正式來源數字、模型候選、已保存 graph checkpoint、品質通過與 provider 健康分開驗收。

此案原有金額單位錯誤已在最終正文修正，但價格推導、新聞標題可支持的結論範圍仍須個別證據。另確認 final-audit 被 deferred 中斷時，未提交 clone 的 repair counters/history 沒有耐久保存；本輪不宣稱已修正該上限問題，亦不放寬品質規則以接受更多失敗候選。

## 晚間來源生成與並行階段修正

19:28 查核的 26 份模式 D 報告有 15 份來源降級，其中 12 份包含 `catalyst_evidence_scope_mismatch`。保存的原始模型回應顯示，30 日累計淨額被寫成「持續買超」，修復再沿用原句；另有不存在的日 K 索引與新聞標題改寫。這些是生成與來源契約不一致，不能全部歸因於未取得資料。

`trade_source_guidance.py` 在原本完整可見的 source catalog 內，提供有限且帶確切引用路徑的來源事實句。法人句沿用既有主體、期間、觀測日、值與單位驗證；新聞只引用原標題，單根日 K 不變成 52 週高低點。模型仍自行選擇方向與證據，不自動填引用或採納例句。Agent24 的 provider schema 與文字 schema 同步限定 catalog 的 `short_term_market_context` 路徑，步驟快取的契約版本更新，避免重用舊輸出。

`trade_source_diagnostics.py` 在正規化清空不合格 refs 前，保留有界的原引用、原催化句、來源及候選指紋與逐項原因。既有的一次來源修復取得同一 catalog 的實際值、法人期間落差與新聞原標題；來源或候選指紋不同時不沿用舊診斷。所有 admission predicates、修復次數及品質 gate 保持原規則，舊報告不回寫。

`analysis_retry_stages.py` 把 root checkpoint 的 Agent22／23 分支識別為同一並行階段。錯誤在兩分支間切換、單支完成的 pending writes、舊錯誤或候選草稿均不能重設階段次數；只有新 root checkpoint 與兩節點的完成版本證明全階段完成，下一階段才能從基礎退避開始。成功的 pending writes 仍由 LangGraph 原機制重用。

既有工作若 stage ledger 與全工作計數不連續，繼續保守退避，不回填歷史或提前執行已排定工作。實際保存的五個 v4 checkpoint 用於離線重播；同一失敗序列的等待減少只能作反事實測試，不能當正式服務已縮短耗時的證據。供應商回傳的更長等待時間仍優先。
