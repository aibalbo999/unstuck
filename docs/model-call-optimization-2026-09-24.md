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

## 正式實測後的輸入容量修正

晚間 3037 完整重跑的 Agent24 實際估算為 66,577 tokens，超過 Lite 的本機 64,000 上限；其餘候選遇到 503，工作依既有流程等待。保存 checkpoint 重建約 65,324 tokens，缺少該次未保存的 RAG 部分，不能冒稱已精確重建正式請求，也不能認定移除新增提示就一定容納得下。

Agent24 現在沿用 Agent19 已有的 `compact_json` 序列化：僅移除 JSON 結構外的縮排與多餘空白，字串內空白、所有 key、數值、清單、null、來源與上游分析均保留；不使用會改變投影欄位的 `dense`／`role_scoped` 模式。單一 checkpoint 的本機估算降到約 56,511 tokens，仍須實際 provider 呼叫與報告結果驗證。容量上限與供應商 cooldown 不變；不同 prompt bytes 自然使用不同步驟快取 key。

## Agent 設定盤點後的共同修正

Agent 4／14 保留 native JSON schema，估值只引用既有 QuantEngine／deterministic tool results 與可追溯參數。提示不再要求模型呼叫本次沒有提供的工具，也不再強迫在缺乏依據時湊出三情境價格或固定折讓；缺口仍交由原品質 gate 阻擋。這沒有新增動態計算或放寬估值門檻。

所有非 Gemma 候選的財務與 AgentState JSON 使用無損 compact serialization，包含品質重寫。原始欄位、數值、字串內空白、來源與必要規則保留；Gemma 的既有 table representation 不變。補充 RAG 的規劃額度以本次候選模型的 context／輸入／TPM 門檻及 system/schema/tools 開銷計算。完整 prompt 不再以通用 head/tail 中段裁切方式縮短；仍超限時必須由 admission 拒絕並走既有 fallback，不能刪來源換取通過。

`LLM_KEY_ADMISSION_TIMEOUT_SECONDS` 預設 15 秒，將「等待本機可用 key」與主模型 360 秒／備援 120 秒的生成 timeout 分開。較短的既有呼叫期限優先；非法或非正數 admission 設定保守回到 15 秒。未送出即逾時不扣每日用量、不停用 key、不縮短 provider cooldown；下一模型或 persistent retry 保留原有政策。context digest／tear sheet／audit reflection 也有有界 key 等待，無法取得 key 時使用既有 deterministic fallback；有 context 的輔助步驟仍傳遞取消。

`GET /api/observability/agent-settings` 提供不含秘密的有效路由與角色設定，包括旗標追加的 Lite、實際 tools/native schema、生成參數、候選容量、本機限流、timeout 及設定 hash。API 快照只證明 API process；worker request events 和 report completion provenance 中的 `effective_settings_sha256` 才能用來核對執行者設定。不可將 API ready 或路由存在宣稱為 provider 健康。

重跑事件的 snapshot sanitizer 原本以 `token` 名称過濾秘密，誤刪 generation_config.max_output_tokens；現在只放行數值與列舉生成設定，仍拒絕 request body、system instruction、API key 或任意額外欄位。歷史缺欄事件不回填。

跨供應商部署仍受實際憑證與角色契約驗證限制。當次正式設定只載入 Google；OpenAI／Anthropic 未配置，未加入未驗證模型或調高任何 provider 額度。key slot 數與獨立 quota project 數繼續分開，未知 mapping 明確標示 unknown。既有 quota／cooldown／RPD 標記、排程、報告及 .env 不因本輪修改而重設。

本輪隔離整合驗證：956 passed、75 subtests passed、1 optional Agent19 私有 checkpoint skipped、4 個已確認 baseline deselected。四項為 PE river accessor 的兩個舊測試，以及 Agent24 trade-source manifest 對 context mutation 的兩個舊斷言。3037 保存輸入重播中，Agent22／23／24 的預估完整輸入分別由 34,909／35,720／56,551 降為 25,549／27,125／54,540 tokens；這是同資料的離線估算，不是供應商實際用量或正式成功率。原 architecture suite 有七項既有 size/facade 失敗；本輪新增的 context-digest 行數退步已經由抽出生成 helper 修復。

### 部署後實測與查驗端點隔離

PR #31 合併後，原定 22:15（Asia/Taipei）的 3702.TW 重試自然執行。Gemma 證據分批有四次成功回應、三次 500；Gemini 備援有三次 503，另一並行請求隨工作延後而取消。工作沿用既有退避排至 22:45，未產生完成報告，不能宣稱端到端成功率已改善。四次 worker `llm_provider_request` 均保留 `max_output_tokens`，設定指紋與正式 API 查詢一致。823 份既有報告及 2,472 個受保護檔案的比對沒有差異，原工作 ID 和重試排程延續；冷卻期限未被縮短。

部署後曾發生 `/readyz` 與 `/api/observability/agent-settings` 逾時，當時 health／runtime identity 正常。API 程序取樣顯示共用 executor 的 14 個執行緒全忙於 SQLite／JSON 等背景工作，查詢消化後兩端點恢復約 0.08 秒；單獨設定快照建構約 0.07 秒。為避免輕量查驗被大量資料查詢拖住，兩端點各使用一個有界專用 worker，不增加一般查詢的共用 pool。忙碌或逾時回傳 503；取消／逾時不會讓尚未完成的工作失去占位，因此連續輪詢不會堆積 executor 工作。這是查驗可用性保護，不表示其他儀表板查詢的執行時間或供應商 503 已修復。

追加驗證 189 passed，涵蓋共用 pool 飽和、probe 逾時／取消／恢復、真實失敗與查驗逾時區分、router lifespan 關閉與跨 event loop 重啟，以及原有效設定、runtime observability、path／storage／artifact 測試。獨立審查未发现阻擋問題。
