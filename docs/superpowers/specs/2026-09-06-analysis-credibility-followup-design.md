# 四模式內容可信度修正：第一批設計

日期：2026-09-06。方向與本書面規格均已獲使用者「同意／核准」；進入實作計畫與 TDD，實際完成狀態以計畫及驗證紀錄為準。

根因依據：`docs/four-mode-quality-followup-2026-09-06.md`。本批只落實已同意的「缺資料不產出 DCF、上游更正後重跑下游、補齊新聞與證據契約」，不重新設計四種投資策略。

## 一、目標與範圍

成功條件是新產製報告的計算來源、單位與引用版本一致，並明確區分可驗證資料、分析判斷與不可用內容；不是把所有 warning／unverifiable 歸零。

本批包含四個相連的工作單元：

1. 量化輸入與 DCF 同口徑計算／稽核。
2. 上游修復後的依賴失效、重算與發布阻擋。
3. A／B／C 最終建議的市場／新聞評估契約。
4. D 明示均線、C compact 期間目標的精確證據匹配及分析評分分類。

不包含 PostgreSQL 環境安裝／live 驗收、樣本外績效研究、歷史全量重建、股票清單擴充、模型路由調整、額度重置、正式重啟或自動發布。這些維持獨立後續批次；使用者尚未選定歷史 49 組最新版或 102 份回放的範圍。

## 二、金融輸入、計算與稽核共用同一份契約

### 2.1 來源與單位

- 事實輸入只接受有明確量綱的原始欄位：股數用 `shares_raw`；金額用 `market_cap_raw`、`total_debt_raw`、`total_cash_raw`、`free_cash_flow_raw` 及既有具單位歷史序列。格式化字串只負責顯示，不能去掉「億」後當原始值。
- 股數、股價與市值為有限正數；總債務、總現金為有限非負數，淨負債可為負。FCF／EPS 的負值可以作為已知事實保存，但非正 FCF 不進入本 DCF 模型，非正 EPS 不產生有效 implied PE。布林、NaN、Infinity、N/A 不能被當成數字。明確的零債務／零現金有效，但缺少資料不是零。
- 不再使用示範 equity、debt、FCF 序列、100 股或 EPS=1 產生「有效」財務指標。FCF、股數、淨負債等必要事實缺失時，僅讓依賴它們的指標不可用，不使其他有完整輸入的指標一起失效。
- 計算沿用既有 `financial_tools`／`financial_dcf_scenarios` 的數學與情境政策，不新增負 FCF 的替代估值模型。既有負 FCF 拒絕條件保留；正常正 FCF、折現與淨負債處理由同一計算路徑完成。
- 稅率、資金成本、成長及終值假設可以沿用已配置政策，但必須和事實來源分開記錄。假設必須標示為假設，不能把缺失的事實欄位補成政策假設。
- FCF 的 billion TWD 與原始 TWD、WACC 的 ratio 與 percentage points、最終 `twd_per_share`，各只在明確邊界轉換一次。不能將每股 DCF 再乘十億除股數。

### 2.2 可用性與來源資料

`quant_metrics.contract_version="quant_metrics.v2"` 標示新契約；`metric_status` 下的 `dcf`／`wacc`／`implied_pe` 各自保存 `status=available|unavailable` 與 `reason_codes`。`input_provenance` 記錄輸入 path／單位，並保存計算方法及獨立的假設。保留現有對外數值欄位以減少消費端變動；不可用值為 null／不可用的情境，不是零或可見的占位估值。

prompt 的 deterministic financial results、任務 metrics snapshot、final audit、報告 DCF 表／圖使用同一來源判定。不可用 DCF 不產生正數圖表、不被當成估值下限，也不能經由另一個 fallback 欄位重新出現；其衍生欄位如 `margin_of_safety` 同樣不可用，不保留占位零值。

歷史資料沒有新契約時，不能憑數值存在宣稱已符合新契約；若已有事實 fallback 記錄，現行唯讀投影不能把它當可信 DCF。保留原 snapshot 與當時 gate，使用明確的目前規則說明，不回寫歷史。

### 2.3 同方法比較

DCF 稽核改由結構化方法、單位及 bear／base／bull 身分取值，不從「全文含 DCF」推測前三個價格都是 DCF。

- 相對估值的 price targets 不與 DCF 混比；相對估值仍須保有自己的來源與假設。
- 有可信 DCF 時，明確 DCF 數字才與相同情境比較；真正 mismatch 保留，不調寬容差。
- 沒有可信 DCF 卻聲稱系統提供有效 DCF，是可定位的內容錯誤；由既有品質修復流程處理，無法修好不能發布含錯誤來源的正式建議。
- 正規化 DCF 的方法名稱不能替代證據；需有完整的正規化輸入、單位和可重現工具結果，否則為不可用／未驗證，而非另一個可信 canonical 值。

責任邊界：`quant_engine.py` 保留計算彙整入口；原始輸入檢查、單位與 provenance 使用小型純函式模組；既有 financial tools 擁有算式；`final_audit_dcf.py` 擁有同口徑比較；`reporting/analysis_overlays.py` 等報告投影只消費契約，不自己推導估值。

## 三、修復後重算受影響下游

### 3.1 依賴與順序

唯一依賴真相為 `pipeline_modes` 的 groups 與 `context_dependencies.upstream_agent_numbers()`：前群是上游，同群不是。修復順序採群組順序，不能依 Agent 數字排序。

接受一份改變輸出的上游修復後，將其下游依賴範圍標記失效；同一修復輪的範圍取聯集。只重跑受影響且需要更新的節點，同群及不相干已成功節點不重跑。比較使用實際分析正文與 structured output，不包含新增的稽核附錄、時間或 telemetry；若內容沒有改變，不額外使下游失效。

例如 A 修復 Agent 4，至少使 6／21／7 的舊結果失效；Agent 5 與 4 同群，不因 4 的更新被迫重跑。若同時修復 Agent 2，則按更大的實際依賴範圍安排，不能只重跑最終 Agent 7。

### 3.2 版本、快取與 checkpoint

- 每個已採用結果綁定產生它時的上游輸入版本／hash；消費端只能讀取仍符合當前依賴版本的結果。analyses、structured outputs、typed agent reports、Agent 所屬風險與 parsed 視圖必須一致。
- 失效涵蓋舊摘要、衍生決策摘要與受影響的分析 RAG 內容；原始外部證據及外部來源風險不因分析重算被刪除或重新抓取。稽核歷程仍保留，但不能被當成目前有效的決策內容。
- 只對 context 字典做 `pop()` 不算完成。LangGraph 的 merge reducer、typed state 與 checkpoint restore 必須共同阻止舊資料在合併／恢復後重新成為有效結果。
- 採最小一致性單位：沿用現有 `final_audit` graph node，在暫存 context 執行「上游修復＋下游重建＋再稽核」，成功才提交完整一致版本。未成功的中間版本不成為可發布 state，不新增逐 Agent 修復 checkpoint 架構。
- 中途 deferred／取消／崩潰時，不提交新上游配舊下游。恢復從前一個一致 checkpoint 的未完成 final-audit 節點重執行本輪；允許該輪受影響節點再次執行，但不重跑前面不相干的成功節點。
- 採用／回復時有明確的局部替換語意；舊 parsed key 或已解除的本輪 blocker 不得因 merge／append reducer 復活，其他尚未解除的 blocker 不得被清除。草稿與 step cache 的輸入 fingerprint 必須包含當輪最新上游，不能借修復前 state 跨版本復用。
- 同步及非同步 repair 使用同一份依賴計畫；不得出現只有 async 路徑安全的實作。

### 3.3 失敗與發布

下游重算沿用既有品質檢查、修復次數及 provider deferred／quota 政策，不新增無限重試，也不重置 RPD。超出修復限制、寫入失敗、取消或下游未完成時，保留先前一致 checkpoint 及失敗原因作為恢復依據，但不能把該舊結論恢復為此次修復成功，不發布新正式報告。同步路徑也採同樣的暫存／提交語意。

只有所有必要依賴都屬當前版本，才重新產生 parsed／final audit／chief editor／renderer。未完成可以依既有規則延後或以明確阻擋狀態結束；不能僅因 12 個月目標落在寬鬆情境範圍就判定來源一致。

責任邊界：依賴與版本判定留在共用純函式；`agent_runtime` 執行有界重建；`workflow_state`／`workflow_context`／checkpoint adapter 保留失效語意；renderer 不執行模型重跑。

## 四、最終建議的市場與新聞評估

A Agent 7、B Agent 16、C Agent 19 structured output 根層共用 `market_context_assessment`，分別記錄 `global_market_context` 與 `international_news_context`。新工作 context 的 `market_context_contract_version="market_context.v1"` 啟用新稽核。D 保留現有短線事件／交易契約，不新增不相干的長線新聞欄位。

每個來源的評估包含：

- `impact`：`affects_conclusion`、`no_material_impact` 或 `not_assessed`。
- `reason`：非空、與此次結論有關的理由或限制，不以固定套句自動補「無影響」。
- `source_refs`：指向此次 prompt 可見、且仍存在於該 snapshot 的來源項目。使用系統分配的穩定身分，不接受模型自造網址作為 canonical 引用。

來源可用性和模型可見的來源清單由系統建立、保存與驗證，模型不能自行宣稱有／無資料。精簡 prompt 只給部分 topics 時，不能把完整 snapshot 的全部 topics 宣稱為已評估。每則 topic 是新聞標題／摘要，不代表已取得新聞全文。

來源 manifest 綁定本次輸入資料 fingerprint、canonical path／index、item content hash；成功結果另綁最終 prompt hash 與該次 manifest。fingerprint 不包含之後生成的 manifest 或最終 snapshot hash，避免循環自證。最後 token-budget 裁切後，只將仍完整保留的來源區塊列為可見；只有 ref 存在但正文被截斷，不算完整來源。原始來源可用但全部被省略時，記錄 `not_assessed` 及 prompt 省略原因，不能聲稱原始來源不存在。

primary／fallback、品質 retry／repair、step-cache hit 都必須沿用成功那次輸出的 manifest；snapshot 白名單保存它，後續讀取只能使用該份當時的可見來源紀錄。缺 manifest 的 legacy cache 不可在新契約下直接冒充已驗證評估。

處理規則：

| 來源／輸出情況 | 應有結果 |
| --- | --- |
| 可用、影響結論、引用有效且有理由 | 接受評估；不等於投資結論已被事實證明 |
| 可用、有理由地不改變結論、引用有效 | 接受 no-material-impact，保留理由 |
| 無可用來源或來源全部被 prompt 省略 | `not_assessed`，系統區分缺資料／prompt 省略原因，維持警告，不為此發起補新聞或重試 |
| 可用但未評估／缺欄位 | 進入既有有界品質重試；仍無法評估時明示未評估警告，不替模型補答案 |
| 只有關鍵詞、空理由或偽造 source ref | 不算評估完成；先修復，偽造引用未解決不得以可信來源發布 |

只有明確分類為可修復的 coverage warning 才啟動定向重試，不把所有 warning 都當成自動重跑請求；達上限仍未評估時維持 warning／not-assessed，偽造或不實評估主張未修復則維持 critical。

新生成與局部重跑的最終建議適用新契約；schema 允許 legacy 缺欄位為 None 且呈現「未記錄」，不能自動補成 no-impact。HTML、Markdown、parsed、final audit 及內容可信度投影採同一結果，避免正文有揭露、品質摘要卻說沒有，或反向矛盾；新 visibility 要求僅適用新契約 A／B／C。

責任邊界：schema／parser 定義結構；prompt context 產生 bounded evidence refs；共用純 validator 驗證可用性與引用；現有 quality retry／final audit 分流；renderer 顯示同一份評估與限制。Agent 19 提示詞同步補齊，並更新相應 prompt 版本／fingerprint。

## 五、精確 evidence mapping

1. 明示的單一均線 claim，例如「205.4（20 日均線）」，僅匹配 exact `data.technical_indicators.sma_20`；205.425 可按既有容差核驗。不得借 `volume_sma_20`、`sma_200`、其他期間、risk price 或同值欄位。
2. 均線來源／可用性缺失、null、多個期間或多個價位、混合依據、新聞語境不猜測來源；真實不同值維持 mismatch。未明示 SMA 的一般支撐／壓力保留原邊界。
3. 只有明確「最終投資建議」列中的 bare 3／6／12 個月，才映射對應 parsed recommendation 欄位；缺同期間 canonical path 仍不可驗證，不能借另一期間同值目標。
4. `情緒過熱評分`、`過熱評分` 以 exact label 擴充既有分析 metadata 分類，仍是 unverifiable，不擴為「所有含評分」的泛用規則。
5. 信心、護城河評分與情境假設維持原始邊界。canonical path 不可用時不把 null 變零，亦不降低抽樣／容差／證據門檻。

責任邊界：沿用 `evidence_exit_gate`／claim helper 和既有細分純函式模組。新增匹配不得使既有模組超出 import／檔案大小限制，也不修改保存的歷史抽查結果。

## 六、驗收與交付條件

所有一般測試使用 `"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py`，隔離 SQLite、Redis 與 Python 網路；不得在正式 checkout 執行裸 pytest。正式 API、模型與資料庫不作單元測試替身。

| 驗收領域 | 必須覆蓋的案例 |
| --- | --- |
| 金融來源 | 1623 原始輸入不再產生占位 DCF；格式化股數不被當 raw；負 FCF／缺股數／缺淨負債／非有限值為不可用；已知零債務有效 |
| 計算一致性 | 正 FCF 算式維持；TWD／billion TWD、ratio／百分點、每股值各轉換一次；prompt、metrics、audit、表格／圖表結果一致 |
| 方法稽核 | 相對估值不混比；同情境真 DCF mismatch 保留；不可用 DCF 不被當可信來源；正規化標籤不能自證 |
| 依賴重建 | A 修復 4 後重建 6／21／7 而不重跑 5；多上游聯集；依群序非數字排序；沒有內容變更不重跑 |
| 持久化／失敗 | stale 結果不能經 reducer／typed state／checkpoint 復活；deferred 恢復重執未提交的修復輪、不重跑無關成功節點；失敗／取消／次數用盡不發布；sync／async 一致 |
| 新聞 | 有效 impact、有效 no-impact、缺來源、精簡來源集、最後 budget 省略／截斷、fallback／cache manifest、缺欄位、空理由、只有關鍵詞、偽造／跨 snapshot refs、legacy 未記錄 |
| 證據 | SMA exact path／日期及期間歧義／缺值／真 mismatch；3／6／12 月各自綁定；兩種過熱評分與同值碰撞仍 unverifiable |
| 四模式相容 | B 等待／零部位、C 空方計畫、D Neutral／不交易及未知成本保留；既有品質 gate、來源審計與歷史讀取不被繞過 |

實作採 TDD：先加入能重現舊問題的失敗案例，再做最小修正，完成局部、跨模組與全套回歸及獨立程式審查。先用保存的資料副本在隔離儲存重放，不覆寫來源 snapshot 或正式報告。

交付紀錄必須分開列出「程式／測試完成」「正式 runtime 是否已載入」「代表報告是否重新產製」「仍需等待的外部驗證」。未重新產製的歷史報告仍是舊版，不能因程式修正就宣稱全部內容已更新。

## 七、設計自我檢核

- [x] 所有第一批核准項目都有明確責任模組、失敗行為及驗收案例。
- [x] 不存在以 unknown、零、相同數字或任意來源補成 verified 的路徑。
- [x] 上游版本、下游有效性、checkpoint 恢復與發布閘門使用同一語意。
- [x] 新聞未評估與偽造來源分級處理，不因可選來源缺失就阻擋所有報告。
- [x] PostgreSQL、OOS、全量歷史重建與正式發布沒有被混入本批已完成承諾。

本文件不是已完成程式的證明。書面規格已核准，後續依逐步實作計畫執行。
