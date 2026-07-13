# HCS Plus Optimization State

更新時間：2026-07-11

## 專案目標

優化本機股票研究系統的前端工作台與報告體驗，讓操作者能更快判斷：

- 要跑哪一種分析模式。
- 目前資料、模型、任務與歷史決策是否可信。
- 哪些報告、追蹤項目或警示需要立即處理。

成功標準：

- 前端主工作流在 desktop 與 mobile 均可掃讀。
- 資料視覺化元件不依賴過小字級或顏色單一編碼。
- 重要 UI 決策有測試或截圖證據支撐。
- 每次優化都可用專案既有測試驗證。

## 執行範圍註記

本次採 HCS 四大類別的批次式落地優化：批判、創意、溝通、互動各完成三輪，並做一次三習慣綜合收斂。這是可交付的系統優化批次；若要嚴格符合「每個 HCS 單項習慣逐一三輪」的完整巡迴，仍可在後續從本狀態表繼續展開。

2026-07-04 啟動嚴格單項輪巡附件：`docs/hcs-plus-strict-habit-log.md`。後續 HCS Plus 進度以該附件記錄每個單項思考習慣的核心判斷、落地修改與驗證方式；本狀態表保留總目標、限制、決策與高階進度。

## 專案內容

- FastAPI 本機服務與靜態前端：`backend/static/`
- HTML 報告模板：`backend/templates/`
- 報告與資料可信度渲染：`backend/reporting/`
- 前端合約測試：`tests/test_static_history_filters.py`
- HCS 嚴格單項輪巡：`docs/hcs-plus-strict-habit-log.md`
- 設計審查 artifact：`~/.gstack/projects/aibalbo999-unstuck/designs/design-audit-20260704-065346/`

## 限制條件

- 優先做小範圍、可逆、可測的修改。
- 避免改動資料流程、模型路由與後端管線，除非前端驗收需要。
- 不提交 API key、cache、output 或本機敏感檔案。
- 目前不做大型 redesign；先修正掃讀、對比、行動裝置與操作回饋。

## 決策紀錄

- D1：本輪以「前端工作台可讀性與可驗證品質」為主要優化目標。
- D2：採用 CSS-first 策略，只有必要時才改 JS 或模板。
- D3：每個 HCS 模式至少落一個專案變更，並補上測試或可檢查點。
- D4：首頁模式選擇應直接說明決策用途，而不是只列風格名稱或 Agent 數。
- D5：首頁副標採用使用者結果語言：「研究報告與決策追蹤工作台」。
- D6：模式切換要提供即時 intent 提示，降低使用者選錯分析模式的機率。
- D7：前端模式名稱、用途、CTA 與清單顯示以 `StockAgentUi.PIPELINE_META` 作為共用資料來源。
- D8：watchlist 與 market screener 顯示模式時優先呈現決策語意，不再只顯示 `V1/V2/V3/V4` 代碼。
- D9：新增 `docs/pipeline-mode-contract.md` 作為前端模式、後端 pipeline 與報告模板的對照契約。
- D10：前端設計檢查點納入模式契約，UI 調整需同時檢查報告模板語意。
- D11：嚴格 HCS Plus 輪巡不再以四大類別代表單項完成；每個單項習慣必須在 `docs/hcs-plus-strict-habit-log.md` 留下獨立紀錄。
- D12：每批單項輪巡最多處理 3 到 5 個習慣，避免一次改動過大而無法審查。
- D13：每批至少補上一個可重跑驗證；若只修改文件，需有文件契約測試防止漏項或回退。
- D14：未完成三輪單項巡迴與三習慣綜合前，不得宣稱完整 HCS Plus 自主優化完成。
- D15：下一批暫定採用「小型使用者可感品質改動」作為落地優先方向，除非使用者另行指定。
- D16：新文件與新整合範例一律使用 canonical pipeline ids：`v1` / `v2` / `v3` / `v4`；`mode_a` 等 alias 只作後端相容輸入。
- D17：Active jobs 任務列表顯示模式時必須使用共用 `pipelineModeLabel` 語意，不直接暴露 raw `pipeline_id` 給操作者。
- D18：Performance panel 的命中率與平均 ROI 必須同時顯示樣本信心；10 筆以下標示「樣本不足，僅供觀察」。
- D19：Report preview 頂部必須延續 report conformance 與 evidence exit gate 警示，不讓品質風險只停留在 history 清單。
- D20：Operator summary 的資料狀態 detail 使用「資料新鮮 / 抽樣」中文脈絡，不使用 `fresh / sampled` 內部監控語氣。
- D21：API quota 與 operator summary 的無錯誤狀態使用「本機觀測」框架，不把本機統計表述成供應商整體健康證明。
- D22：批判思考第 1 輪以 26/26 單項完成作為合理收尾，不宣稱完整 HCS Plus 完成，下一批進入創意思考。
- D23：模式契約新增「模式選擇速記」，用決策問題與分診台類比降低新整合者選錯 pipeline mode 的成本。
- D24：模式契約新增決策樹；不確定時先用 `v1` 建立基本面基準，再視需要補跑交易、逆勢或事件模式。
- D25：Report compare summary 顯示共用 pipeline mode label，不再把 raw `pipeline_id` 當成比較視圖的主要模式語意。
- D26：Report compare result 顯示「比較基準」與「比較樣本」，避免把兩份報告個案比較誤讀成整體策略績效。
- D27：Report compare 的跨模式 warning 由前端使用共用 mode label 轉譯，避免 raw pipeline id 出現在主要比較警示。
- D28：第 1 輪創意思考完成 17/17；共用 mode label pattern 已複製到 report compare，下一批進入溝通思考。
- D29：Report compare 的跨模式 warning 改用完整中文語意，明示這是「跨視角比較」而非錯誤或技術版本對照。
- D30：Report compare result 第一列新增「比較結論」，先聲明同股票同模式、股票不同、跨視角比較或需留意，再呈現檔名與數字。
- D31：第 1 輪溝通思考完成 10/10；compare panel 維持文字 grid/chip 媒介，不在本輪加入圖表或多媒體比較。
- D32：Report compare result 將「建議」改為「報告建議變化」，並新增「僅比較既有報告，不代表即時交易指令」使用提醒。
- D33：Report compare result 新增「判讀層次」，明示報告差異不等於市場因果，需搭配資料可信度與追蹤報酬判讀。
- D34：Report compare 的 decision-needs-rerun warning 明確提示「先重跑結論，再比較投資判斷」，連接資料更新、重跑與比較流程。
- D35：Report compare 的 rerun warning 改成條件式「若要比較投資判斷，需先重跑結論」，降低命令式操作推力。
- D36：Report preview legacy 預設文案改用「報告建議」並補上「仍需自行判斷」，降低從眾與情緒化採用報告的風險。
- D37：Preview 靜態骨架與 rerun CTA 改用「報告建議 / 報告結論」，降低系統權威感並清楚標示責任邊界。
- D38：History filter 將「投資建議 / 全部建議」改為「報告建議 / 全部報告建議」，前端顯示層維持報告瀏覽器角色。
- D39：第 2 輪批判思考先建立問題雷達；不盲目替換後端「投資建議」契約詞，先區分報告正文契約、prompt 契約與前端顯示層。
- D40：第 2 輪偏誤護欄明確區分可改名顯示層與需保留契約層；後續改名需同時看前端契約與解析契約回歸。
- D41：契約詞處理採決策樹：使用者顯示層可改名，機器解析契約預設保留，完整報告正文先補 coverage map 再決定。
- D42：契約詞 coverage map 只統計可維護來源檔並排除生成輸出；目前測試檔案數 24、後端檔案數 26，屬最低可觀測樣本。
- D43：契約詞高顯著性改動需跑回歸測試組；`test_report_preview`、`test_report_conformance` 與 front-end static tests 是目前最小核心。
- D44：高顯著性契約詞改動必須先對照契約測試矩陣；沒有把改動層級映射到必跑測試前，不進入正文、prompt 或 parser 修改。
- D45：契約測試矩陣加入反謬誤護欄；測試綠燈只證明指定契約未回退，不可推論成語意安全、完整母體覆蓋或使用者情境已被驗證。
- D46：契約矩陣暫不新增自動選測腳本；先用最小命令分組降低執行摩擦，等第 2 輪批判思考收尾確認合理性與可驗證性後再決定是否工具化。
- D47：第 2 輪批判思考以 26/26 單項完成作為合理收尾；契約矩陣、反謬誤護欄與最小命令分組暫時足以支撐下一輪創意思考，不在此批新增自動選測腳本。
- D48：第 2 輪創意思考先把契約矩陣做成速學卡；以三題判斷與三道安檢通道降低學習成本，不新增自動選測腳本。
- D49：第 2 輪創意思考第二批把速學卡轉成四步操作流程、三個操作者情境與三條捷思規則；仍維持文件契約，不新增自動選測腳本。
- D50：第 2 輪創意思考第三批新增契約矩陣採用觀測板；用最佳化目標、可觀察假說與採用訊號矩陣檢查流程是否降低錯選測試風險，不新增遙測或自動化蒐集。
- D51：第 2 輪創意思考第四批新增契約矩陣案例模型；用三類模型、代表性抽樣規則與案例卡格式，把採用觀測板轉成可對照的變更案例。
- D52：第 2 輪創意思考第五批新增契約矩陣比較與回饋設計；以基準組/介入組、錯選/漏跑/判讀限制指標與訪談回饋題，檢查案例模型是否降低選測摩擦。
- D53：第 2 輪創意思考第六批新增契約矩陣觀察與複製準則，並以 17/17 單項完成作為本輪創意思考收尾；下一批進入第 2 輪溝通思考。
- D54：第 2 輪溝通思考第一批新增契約矩陣讀者路徑；以一般改文案者、報告模板維護者、parser/prompt 維護者三種受眾，重組閱讀順序並明確標出文件契約、觀察紀錄與低顯著性的語意邊界。
- D55：第 2 輪溝通思考第二批新增契約矩陣維護導覽；用章節導覽、專業維護語氣與核心論點，把讀者路徑收斂成可引用的維護規範。
- D56：第 2 輪溝通思考第三批新增契約矩陣一頁摘要；用短版摘要、建議表達與媒介取捨完成溝通思考 10/10 收尾，並明確暫不新增圖像或多媒體。
- D57：第 2 輪互動思考第一批新增契約矩陣倫理邊界；明確禁止把測試綠燈寫成投資建議安全、禁止把責任轉嫁給工具或文件，並定義必要時要說不與升級條件。
- D58：第 2 輪互動思考第二批新增契約矩陣系統風險邊界；用複雜因果圖譜、湧現風險與分析層次，避免把文件、測試、runtime 或使用者行為證據互相替代。
- D59：第 2 輪互動思考第三批新增契約矩陣系統關係圖；整理前端顯示層、報告模板層、parser/prompt 層、測試矩陣與使用者判讀的維護網絡，並記錄系統動力學與系統圖像。
- D60：第 2 輪互動思考第四批新增契約矩陣 review 對話；用補證據協商、說服原則與形塑行為，把倫理與系統邊界轉成可接受、可執行的 review 語句。
- D61：第 2 輪互動思考第五批新增契約矩陣 review 防從眾檢查；要求不得用多數同意、前例綠燈或測試全綠取代證據層、差異邊界與限制句。
- D62：第 2 輪互動思考第六批新增契約矩陣 review 責任分工；明確改動者、reviewer、合併者在改動層級、通道命令與限制句上的責任。
- D63：第 2 輪互動思考第七批新增契約矩陣 review 自我稽核與收尾策略；承認矩陣不是自動化審核器、避免低風險改動被過度流程化，並以 20/20 收尾進入第 3 輪批判思考。
- D64：第 3 輪批判思考第一批新增契約矩陣瘦身問題雷達；重新拆解矩陣過重、2 分鐘選通道、低顯著性被拖慢與責任限制句落地等缺口。
- D65：第 3 輪批判思考第二批新增契約矩陣變數與偏誤降低護欄；用改動層級、證據層、可逆性與時程壓力辨識錯誤升級、錯誤降級、工具化幻覺與綠燈擴張偏誤。
- D66：第 3 輪批判思考第三批新增契約矩陣分流決策與效用校準；把一頁摘要、低顯著性命令、高顯著性通道、混合層通道、案例卡與證據分層回報排成可執行決策樹。
- D67：第 3 輪批判思考第四批新增契約矩陣證據校準與觀測統計；標示目前樣本與不可外推範圍，並定義選通道時間、錯選率、案例卡觸發率與限制句出現率等觀測欄位。
- D68：第 3 輪批判思考第五批新增契約矩陣風險機率與顯著性門檻；把錯選率、限制句缺漏率與案例卡漏觸發率轉成風險機率、回歸監測與升級門檻。
- D69：第 3 輪批判思考第六批新增契約矩陣證據規則與外推邊界；定義可接受證據、不可作為證據、立即升級演繹規則與不得外推到 runtime、使用者理解或生成報告母體。
- D70：第 3 輪批判思考第七批新增契約矩陣反謬誤與來源情境邊界；把測試綠燈謬誤、樣本數謬誤與案例代表性謬誤寫成護欄，並分級高品質來源、次級來源與不得作為完成證據的來源。
- D71：第 3 輪批判思考第八批新增契約矩陣負擔估算與完成詮釋框架；把必留護欄、可短句替代、可延後工具化分開，並估算低風險 UI、混合層報告呈現與高風險契約的完成回報成本。
- D72：第 3 輪批判思考第九批完成 26/26 收尾；新增契約矩陣第 3 輪收尾與可重跑驗證，保留人工判斷、不新增自動選測腳本，並把下一分類入口推進到第 3 輪創意思考。
- D73：第 3 輪創意思考第一批新增契約矩陣創意學習入口；用三層學習路徑、限制條件與登機前安檢類比，把第 3 輪批判矩陣轉成第一次使用也能執行的操作者入口。
- D74：第 3 輪創意思考第二批新增契約矩陣操作演算法與捷思規則；把 10 秒判斷、90 秒執行與 5 分鐘復盤轉成四步操作演算法、三個操作者情境與三條快速規則。
- D75：第 3 輪創意思考第三批新增契約矩陣採用最佳化與訊號板；把錯選通道、漏跑命令、限制句缺漏、案例卡漏補轉成採用摩擦，並用三個可觀察假說與綠/黃/紅訊號板追蹤。
- D76：第 3 輪創意思考第四批新增契約矩陣案例模型與抽樣案例卡；把採用訊號板轉成低風險快速通道、混合層報告呈現、高風險契約人工複檢與紅色阻擋四類代表性案例模型，並定義抽樣規則與案例卡格式。
- D77：第 3 輪創意思考第五批新增契約矩陣比較與介入回饋設計；用基準組與介入組觀察錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率，並用最小介入方案與操作者回饋題檢查案例模型是否可用。
- D78：第 3 輪創意思考第六批新增契約矩陣觀察與複製準則；把比較組、介入方案與操作者回饋題轉成觀察記錄欄位、複製檢查清單與可複製完成條件，並以 17/17 單項完成作為本輪創意思考收尾。
- D79：第 3 輪溝通思考第一批新增契約矩陣讀者語意入口；將低風險 UI 維護者、報告呈現維護者、契約複檢維護者與觀察流程維護者分流，並定義四步組成與語意含義邊界。
- D80：第 3 輪溝通思考第二批新增契約矩陣維護導覽與核心論點；把讀者語意入口整理成章節導覽、維護語氣與核心主張，讓不同維護者能用同一套專業語意收尾。
- D81：第 3 輪溝通思考第三批新增契約矩陣短版回報與媒介取捨；用一頁摘要、建議句型、文字表格優先與暫不新增多媒體完成本輪溝通思考 10/10 收尾。
- D82：第 3 輪互動思考第一批新增契約矩陣倫理阻擋與責任判斷；把短版回報的倫理底線、必要時說不與升級判斷寫成阻擋規則，避免安全背書、責任轉嫁與高風險契約降級。
- D83：第 3 輪互動思考第二批新增契約矩陣系統因果與證據層次；把局部綠燈因果圖、湧現風險與文件/測試/runtime/使用者行為分層寫成跨層外推護欄。
- D84：第 3 輪互動思考第三批新增契約矩陣維護網絡與動態圖像；把文件層、測試層、runtime 層、使用者行為層與 reviewer 阻擋連成維護網絡，並用動態回路與操作圖像支撐跨層升級判斷。
- D85：第 3 輪互動思考第四批新增契約矩陣 review 對話與預設行為；把維護網絡轉成補證據協商、降低說不成本的說服路徑與完成回報預設三欄。
- D86：第 3 輪互動思考第五批新增契約矩陣防從眾、差異訊號與情緒調節；要求多數同意、前例綠燈、測試全綠與合併壓力不得取代證據層，並保留改動層級、證據層、pipeline 模式與風險顏色差異。
- D87：第 3 輪互動思考第六批新增契約矩陣角色責任與權力護欄；把防從眾規則轉成主責、review 主導者、合併者的證據領導、權力邊界與完成回報責任。
- D88：第 3 輪互動思考第七批新增契約矩陣自我稽核與收尾策略；限制角色責任不得變成形式簽核，定義輕量使用邊界與 20/20 互動思考收尾條件，下一步進入三習慣綜合優化。
- D89：三習慣綜合優化第 1 次新增契約矩陣驗證、溝通與系統圖像收斂；把三輪累積規則整合成驗證閘門、完成回報格式、系統圖像收斂與驗收標準。
- D90：三習慣綜合優化第 2 次新增契約矩陣證據來源、讀者角色與責任承接；把直接證據、間接證據、缺口證據與未跑命令分級，並讓改動者、reviewer、合併者分別承接證據、誤讀與剩餘風險。
- D91：三習慣綜合優化第 3 次新增契約矩陣偏誤防線、速學入口與策略收斂；把表格打勾、證據漂白、升級逃避與流程膨脹四種偏誤寫入防線，並用 10 秒定位、90 秒分流、5 分鐘復盤降低採用成本。
- D92：三習慣綜合優化第 4 次新增契約矩陣目標校準、效用門檻與合理性審核；把每條矩陣規則綁回股票研究系統核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。
- D93：三習慣綜合優化第 5 次新增契約矩陣限制邊界、分流決策與成本最佳化；把硬限制、軟限制、升級限制與停用限制轉成四步決策，並要求保留輕量通道、合併重複規則、刪除低效用規則與延後無證據規則。
- D94：三習慣綜合優化第 6 次新增契約矩陣來源分級、適用情境與批判反證；把高可信來源、可用但有限來源、不得作為完成證據與缺口來源分級，並要求情境不符時升級或拆分。
- D95：三習慣綜合優化第 7 次新增契約矩陣把握校準、信心邊界與解讀框架；把完成宣稱分成高把握、中把握、低把握與不得宣稱，並要求每個宣稱標示適用層級、證據覆蓋與剩餘不確定。
- D96：三習慣綜合優化第 8 次新增契約矩陣關聯檢核、分布摘要與顯著性門檻；把規則關聯分成強支撐、弱支撐、衝突支撐與無關，並用完成、缺口、驗證與風險分布決定升級、保留、降級或刪減訊號。
- D97：三習慣綜合優化第 9 次新增契約矩陣概率語言、迴歸風險與謬誤防線；把高可能、中可能、低可能與未知或不得推定分開，並要求回到過度宣稱、跨層外推、流程膨脹或弱證據升級時立即降級或拆分。
- D98：三習慣綜合優化第 10 次新增契約矩陣合理性收尾、驗證門檻與維護策略；把十次綜合優化收斂到核心目標、完成定義、驗證門檻與完成後維護策略，並標記 HCS Plus 自主優化完成。
- D99：2026-07-08 啟動新一輪系統優化，目標從前端契約矩陣擴大到報告品質、provider impact、outcome calibration、模型路由成本與每日操作排序。
- D100：報告品質優先採 deterministic gates 與 repair queue，不用增加 Agent 數量掩蓋資料或內容可信度問題。
- D101：outcome calibration 必須把 backtest miss 連回 report-time quality signal，避免把資料品質或證據不足誤判成 thesis 失敗。
- D102：provider SLA 不只作 observability，必須落到 report-level impact 與 rerun policy，核心來源不穩時可阻擋盲目重跑。
- D103：model route budget 只使用 telemetry 可驗證的 token、latency、retry 與 cache hit；沒有 verified price table 前，USD cost 保持 null。
- D104：daily decision queue 成為每日操作順序來源；blocked repair/provider wait、due backtest、rerun、model route warning、watchlist 與 screener candidate 以 priority score 排序。
- D105：本輪 HCS Plus 系統優化已完成 P0-1、P0-2、P0-3、P1-1、P1-2；尚未宣稱整個嚴格單項三輪巡迴重新完成。
- D106：P2 建立 CI Lane And Contract Map，將 quality signal、repair queue、provider impact、outcome calibration、model route budget、daily decision queue 與 runtime/storage 改動映射到固定測試 lane，並新增 API route boundary guard。
- D107：P3-1 補強 Operator Queue Visibility，讓前端 operator summary 優先呈現 `decision_queue.items`、次要待辦數、來源與 `priority_score`，避免每日排序只停在 API payload。
- D108：P3-2 補強 Watchlist Daily Board Queue，讓 watchlist `今日工作台` 也讀取 `decision_queue`，與 operator summary 使用相同的 top queue、來源、priority 與次要待辦語意。
- D109：P3-3 補強 Operator Action Deep Links，讓非報告型 queue action 從 operator summary 直接切到 provider SLA、決策回測、模型路由、候選清單或 watchlist 對應面板，而不是一律只打開維運頁。
- D110：P3-4 修正 Daily Queue Empty State，將 monitor fallback 保留為 UI 相容項目但不計入 `summary.total_actionable`，watchlist `今日工作台` 也不再把 monitor 顯示成最高優先待辦。
- D111：P3-5 修正 Monitor-Only Notification Quiet，讓 `notification_plan` 跳過 `monitor` fallback；沒有真實待辦時維持 local/free channel 可用但不產生通知訊息。
- D112：P3-6 修正 Operator Summary Quiet Action Count，讓 operator summary header 用 `actionableActionCount` 排除 `monitor` fallback，避免 no-action dashboard 顯示成 1 件快速操作。
- D113：P3-7 補強 Notification Queue Context，讓真實 queue action 的通知訊息保留 `source`、`priority_score`、ticker、filename 與 pipeline context，避免通知層只剩標題與描述。
- D114：P3-8 補強 Notification Queue Primary Source，讓 `notification_plan` 優先讀取 `decision_queue.items` 並輸出 `queue_context`，legacy `actions` 只作相容 fallback，避免通知層脫離每日排序權威來源。
- D115：P3-9 補強 Notification Action Metadata，讓 notification message 保留 `route`、`warning_id`、`horizon_months`、`recommended_action`、`blocks_auto_rerun`、`severity` 與 `action_label` 等 action-specific metadata，避免外部通知失去模型路由、回測期或 provider wait 的可執行診斷脈絡。
- D116：P3-10 補強 Notification Action Targets，讓 notification message 自動帶入 `target_panel` 與 `target_tab`，並與 operator summary 的 provider SLA、決策回測、模型路由、候選清單與 watchlist deep link 規則一致。
- D117：P3-11 補強 Notification CTA Metadata，讓 notification message 自動帶入 `operator_action` 與 `operator_action_label`，並與 operator summary 的 `view-report`、`open-ops`、`run-watchlist` 等 CTA 規則一致。
- D118：P3-12 補強 Notification Queue Rank Metadata，讓 notification message 帶入 `queue_rank`、`queue_displayed_count` 與 `is_top_priority`，並在排除 `monitor` fallback 後依真實通知順序計算，避免外部通知失去每日 queue 排名語意。
- D119：P3-13 補強 Notification Dedupe Keys，讓 notification message 帶入穩定 `dedupe_key` 與 `message_id`，以 source/type/report/route/horizon 等識別欄位為基礎，不使用 title/detail/priority，避免外部 channel 因文案或排序變動重複推播同一個 queue action。
- D120：P3-14 補強 Notification Delivery Outbox，讓 `notification_plan` 針對每個 enabled channel/message pair 產生 pending `delivery_outbox` entry 與 `delivery_summary`，用 channel-specific `delivery_key`、`message_id` 與 `dedupe_key` 支撐後續外部 sender 的稽核與 idempotency。
- D121：P3-15 建立 Notification Delivery Audit Store，將外部 sender 的 sent/failed/pending/skipped 嘗試結果以 `delivery_key` upsert 到 `operational.sqlite3` 的 `notification_delivery_audit`，保留 attempt count、last error、response id 與 success timestamp，避免 delivery 結果混入 report index 或外部 channel dashboard 才可查。
- D122：P3-16 補強 Notification Outbox Audit Reconciliation，讓外部 sender 發送前可用 `reconcile_outbox_with_audit()` 將 pending outbox 與既有 audit row 對齊，對已 sent 的 `delivery_key` 標記 `already_sent = true` 與 `should_send = false`，避免 retry 或重啟時重複推播。
- D123：P3-17 補強 Notification Retry Budget，讓 failed delivery 在 reconcile 時保留有限重試；同一 `delivery_key` 達預設 3 次失敗後標記 `retry_exhausted = true`、`skip_reason = retry_exhausted` 與 `should_send = false`，並在 audit summary 暴露 `retry_exhausted_count`。
- D124：P3-18 補強 Notification Retry Backoff，讓 failed delivery 未達 retry budget 時仍先等待預設 backoff；等待期間回傳 `skip_reason = retry_wait`、`retry_wait_seconds`、`next_retry_at` 與 `should_send = false`，避免 sender loop 立即熱重試同一外部 channel。
- D125：P3-19 補強 Notification Delivery Ops Health，讓 `/api/observability/dashboard` 與 `/api/ops/dashboard` 回傳 `notification_delivery` audit health；當 failed 或 retry-exhausted delivery rows 存在時，ops dashboard `status` 升為 `warning`，避免外部通知斷線卻仍顯示整體健康。
- D126：P3-20 補強 Notification Delivery Daily Queue Repair，讓 `/api/watchlist/daily-dashboard` 將 delivery audit health 接入 `decision_queue`，產生 `fix_notification_delivery` in-app repair action；該 action 帶 `suppress_notification = true`，不進 `notification_plan.messages` 或 `delivery_outbox`，避免用失效外部 channel 通知外部 channel 故障。
- D127：P3-21 補強 Notification Delivery Frontend Action Mapping，讓 operator summary 與 watchlist 今日工作台將 `notification_delivery` 顯示為「通知通道」，`fix_notification_delivery` CTA 顯示「查看通知通道」並導向 ops maintenance area，同時前端尊重後端 `operator_action`、`operator_action_label`、`target_panel` 與 `target_tab`。
- D128：P3-22 補強 Notification Delivery Maintenance Visibility，讓本機維護面板讀取 `/api/observability/dashboard` 的 `notification_delivery` audit health，直接顯示 failed、retry exhausted、pending 與 channel counts，避免操作者點進 maintenance area 後仍看不到通知通道故障細節。
- D129：P3-23 補強 Notification Delivery Prometheus Metrics，讓 `/metrics` 輸出 notification delivery audit count、channel count 與 health gauges，讓外部監控能在 in-app UI 之外偵測 failed 或 retry-exhausted 通知通道。
- D130：P3-24 補強 Notification Delivery Stable Health Metrics，讓 `/metrics` 固定輸出 `stock_agent_notification_delivery_health{state="ok"}` 與 `{state="warning"}` 兩條 one-hot gauges，避免外部告警依賴 disappearing time series。
- D131：P3-25 補強 Notification Delivery Failure Reason Buckets，讓 audit summary 與 `/metrics` 以低基數 reason bucket 統計 failed delivery，例如 timeout、auth、rate_limited、configuration、network、other、unknown，避免 raw `last_error` 成為 high-cardinality metric label。
- D132：P3-26 補強 Notification Delivery Failure Reason Operator Visibility，讓 `fix_notification_delivery` queue item 與 ops maintenance `通知通道` chip 都呈現 `failure_reason_counts` 的低基數摘要，使 operator 在進入 raw audit row 前即可判斷 timeout、auth、rate limit、configuration 或 network 類故障。
- D133：P3-27 補強 Daily Decision Queue Module Headroom，將 notification delivery repair action builder 抽到 `daily_decision_queue_notifications.py`，並新增 `daily_decision_queue.py < 340` 的 focused size guard，避免每日排序主 module 貼著 350 行全域上限演化。
- D134：P3-28 補強 Maintenance Notification Delivery Frontend Headroom，將 ops maintenance 的通知通道 chip render 抽到 `maintenance_notification_delivery.js`，並把 `maintenance_panel.js` focused size guard 收到 130 行，避免本機維護主面板持續貼著 150 行前端上限。
- D135：P3-29 補強 Operator Dashboard Actions Frontend Headroom，將 operator summary 的 daily dashboard action mapping、target panel 與 fallback queue 規則抽到 `operator_dashboard_actions.js`，並把 `operator_summary_panel.js` focused size guard 收到 135 行，避免值班摘要主面板貼著 150 行前端上限。
- D136：P3-30 補強 App Bootstrap Frontend Headroom，將 `app.js` 的 DOM element collection 抽到 `app_elements.js`，並把 `app.js` focused size guard 收到 260 行，避免首頁 bootstrap 主流程貼著 300 行上限演化。
- D137：P3-31 補強 Decision Tracking Frontend Headroom，將 `decision_tracking_panel.js` 的 tracked group 與 recommended action 純資料轉換抽到 `decision_tracking_helpers.js`，並把主 panel focused size guard 收到 125 行，避免追蹤面板貼著 160 行上限演化。
- D138：P3-32 補強 Report Compare Frontend Headroom，將 `report_compare_panel.js` 的 delta/date/status/warning/summary label 純格式化抽到 `report_compare_helpers.js`，並把主 panel focused size guard 收到 125 行，避免報告比較面板貼著 160 行上限演化。
- D139：P3-33 補強 Ops Workspace Frontend Headroom，將 `ops_workspace.js` 的 DOM element collection 抽到 `ops_workspace_elements.js`，並將共用 panel load/fail 流程抽到 `ops_workspace_loaders.js`，把主 workspace focused size guard 收到 125 行，避免維運工作台貼著 160 行上限演化。
- D140：P3-34 補強 Report Navigation Frontend Headroom，將 iframe 報告目錄的 target lookup、section label 與 nav label DOM helper 抽到 `report_navigation_targets.js`，並把 `report_navigation.js` focused size guard 收到 75 行，避免報告導覽事件綁定模組貼著 100 行上限演化。
- D141：P3-35 補強 Watchlist Panel Frontend Headroom，將 watchlist 表單 payload/reset、priority/report button、daily board 與 suggestions helper 抽到 `watchlist_panel_helpers.js`，並把 `watchlist_panel.js` focused size guard 收到 155 行，避免追蹤清單面板貼著 180 行上限演化。
- D142：P3-36 補強 Market Screener Frontend Headroom，將 screener category/filter/metric formatting 與 fallback pipeline choices 抽到 `market_screener_helpers.js`，並把 `market_screener_panel.js` focused size guard 收到 120 行，避免候選清單面板貼著 140 行上限演化。
- D143：P3-37 補強 UI Data Trust Helper Headroom，將 provider SLA partial 判斷、data trust label/class/reason/score 語意抽到 `ui_data_trust.js`，並把 `ui_helpers.js` focused size guard 收到 100 行，避免前端共用 UI helper 同時承擔模式語意與資料信任文案。
- D144：P3-38 補強 API Request Frontend Headroom，將 client config、mutation token header、response text parsing 與 JSON error normalization 抽到 `api_request.js`，並把 `api_client.js` focused size guard 收到 90 行，避免端點 wrapper 與 request transport/error handling 持續耦合。
- D145：P3-39 補強 History Workspace Panel Factory Headroom，將 history filters、history panel、preview panel、compare panel、stock snapshot panel 與 decision tracking panel 建構抽到 `history_workspace_panels.js`，並把 `history_workspace.js` focused size guard 收到 220 行，避免歷史工作區 orchestrator 同時承擔 panel wiring 與 workflow 狀態。
- D146：P3-40 補強 History Panel Helper Headroom，將追蹤報酬格式、data trust repair 判斷、report action badge、tracking action note、pipeline label、target comparison 與 keyboard activation 判斷抽到 `history_panel_helpers.js`，並首次將 `history_panel.js` 納入 focused size guard 300 行內，避免歷史清單 renderer 同時承擔品質/追蹤語意規則。
- D147：P3-41 補強 Report Preview Helper Headroom，將預覽面板的報告品質 badge、legacy preview fallback、追蹤價格等待判斷、tracking view model、metrics card render 與 rerun button 文案抽到 `report_preview_helpers.js`，並把 `report_preview_panel.js` focused size guard 收到 130 行，避免報告預覽面板同時承擔品質語意與畫面流程。
- D148：P3-42 補強 Stock Snapshot Formatting Helper Headroom，將股票快照的價格/百分比/倍數/事件時序/籌碼語意、sparkline points 與 performance range chart helper 抽到 `stock_snapshot_helpers.js`，並把 `stock_snapshot_panel.js` focused size guard 收到 720 行，讓 800+ 行消費者股票頁面先切出可獨立測試的格式化層。
- D149：P3-43 補強 Stock Snapshot Fragment Helper Headroom，將股票快照的 metric card、financial trend row、dividend bars、calendar event、alert suggestion、valuation band、peer row 與 balance detail 小片段 renderer 收斂到 `stock_snapshot_helpers.js` 的 `fragmentMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 560 行，讓主面板更專注在 section 資料流與組裝順序。
- D150：P3-44 補強 Stock Snapshot Section Helper Headroom，將財務健康、財報趨勢、同業比較與籌碼結構 section renderer 抽到 `stock_snapshot_sections.js` 的 `sectionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 500 行、`stock_snapshot_sections.js` 納入 160 行 guard，避免股票快照主面板重新長成 section rendering 聚合檔。
- D151：P3-45 補強 Stock Snapshot Overview Section Headroom，將公司檔案、今日行情、價格趨勢、多週期走勢與技術面 section renderer 抽到 `stock_snapshot_overview_sections.js` 的 `overviewSectionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 460 行、overview sections 納入 130 行 guard，讓主面板只保留互動事件、資料流與少數尚待拆分的下半部 section。
- D152：P3-46 補強 Stock Snapshot Research Section Headroom，將估值區間、分析師展望與盈餘預估 research section renderer 抽到 `stock_snapshot_research_sections.js` 的 `researchSectionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 430 行、research sections 納入 100 行 guard，讓主面板持續收斂為事件、資料流與剩餘下半部輔助 section 的組裝層。
- D153：P3-47 補強 Stock Snapshot Signal Section Headroom，將股本結構、風險與流動性、獲利品質、股利品質、關鍵日期與提醒建議 section renderer 抽到 `stock_snapshot_signal_sections.js` 的 `signalSectionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 380 行、signal sections 納入 120 行 guard，讓主面板更接近純事件、資料流與互動 action 組裝層。
- D154：P3-48 補強 Stock Snapshot Supplemental Section Headroom，將底部 metric grid、事件 strip、新聞列表與模式建議按鈕 renderer 抽到 `stock_snapshot_supplemental_sections.js` 的 `supplementalSectionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 360 行、supplemental sections 納入 90 行 guard，讓主面板只剩資料載入、快捷鍵、summary rail、互動 handler 與 watchlist/alert action 流程。
- D155：P3-49 補強 Stock Snapshot Input Helper Headroom，將 ticker 正規化、input 回填、recent tickers localStorage 與 shortcut rendering 抽到 `stock_snapshot_input_helpers.js` 的 `inputMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 310 行、input helpers 納入 100 行 guard，讓主面板不再同時承擔瀏覽器儲存與輸入格式規則。
- D156：P3-50 補強 Stock Snapshot Action Helper Headroom，將加入追蹤、套用提醒建議、pipeline fallback 與 action loading state 抽到 `stock_snapshot_action_helpers.js` 的 `actionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 250 行、action helpers 納入 120 行 guard，讓主面板收斂為載入、summary rail、render orchestration 與事件委派。
- D157：P3-51 補強 Stock Snapshot Summary Helper Headroom，將 header、summary rail item、summary rail 與 error view 抽到 `stock_snapshot_summary_helpers.js` 的 `summaryMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 180 行、summary helpers 納入 120 行 guard，讓主面板不再同時承擔首屏摘要文案與資料載入 orchestration。
- D158：P3-52 補強 Stock Snapshot Load Helper Headroom，將 input submit、snapshot fetch lifecycle 與 load button state 抽到 `stock_snapshot_load_helpers.js` 的 `loadMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 145 行、load helpers 納入 90 行 guard，讓主面板更接近純事件委派、render orchestration 與 performance range interaction。
- D159：P3-53 補強 Stock Snapshot Interaction Helper Headroom，將 performance range chart 重畫與 active button 切換抽到 `stock_snapshot_interaction_helpers.js` 的 `interactionMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 130 行、interaction helpers 納入 70 行 guard，讓主面板只保留事件委派與 render orchestration。
- D160：P3-54 補強 Stock Snapshot Render Helper Headroom，將 `render(snapshot)` 的 section 組裝順序與 root 顯示狀態抽到 `stock_snapshot_render_helpers.js` 的 `renderMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 115 行、render helpers 納入 80 行 guard，讓主面板收斂為 constructor、事件委派與 helper method 掛載。
- D161：P3-55 補強 Stock Snapshot Event Helper Headroom，將 `bindEvents()` 的 load、Enter、shortcut、watchlist、alert、range 與 pipeline delegation 抽到 `stock_snapshot_event_helpers.js` 的 `eventMethods`，並把 `stock_snapshot_panel.js` focused size guard 收到 80 行、event helpers 納入 80 行 guard，讓主面板只保留建構與 helper method 掛載。
- D162：P3-56 補強 History Workspace Action Helper Headroom，將預覽資料快照刷新、預覽重跑、刪除報告與追蹤切換抽到 `history_workspace_actions.js`，並把 `history_workspace.js` size guard 從 220 行收緊到 180 行、action helper 納入 120 行 guard，讓 history workspace 回到頁面 orchestration 與狀態協調。
- D163：P3-57 補強 App Pipeline Controls Headroom，將 pipeline 選擇、CTA 文案、hint 與 history/watchlist option label 同步抽到 `app_pipeline_controls.js`，並把 `app.js` size guard 從 260 行收緊到 230 行、pipeline controls 納入 90 行 guard，讓首頁啟動檔少背一層模式語意 DOM 同步責任。
- D164：P3-58 補強 Provider SLA Helper Headroom，將 provider source label、核心/補充判斷、健康度聚合、expected context fallback、summary copy 與 insight copy 抽到 `provider_sla_helpers.js`，並把 `provider_sla_panel.js` size guard 從 210 行收緊到 120 行、helper 納入 170 行 guard，讓 panel 回到純 render orchestration。
- D165：P3-59 補強 History Panel Render Helper Headroom，將 history list、tracking group、tracking report card 與 swing trade metric fragment renderer 抽到 `history_panel_renderers.js`，並把 `history_panel.js` size guard 從 300 行收緊到 170 行、renderer 納入 180 行 guard，讓 panel 回到 state、pagination、selection 與事件委派。
- D166：P3-60 補強 Maintenance Panel Helper Headroom，將本機維護 summary copy、storage chips、default result copy 與 cleanup action message 抽到 `maintenance_panel_helpers.js`，並把 `maintenance_panel.js` size guard 從 130 行收緊到 105 行、helper 納入 100 行 guard，讓 panel 專注 API 載入、button 狀態與事件綁定。
- D167：P3-61 補強 Operator Summary Helper Headroom，將 active job/LLM quota/data trust/rerun 狀態文字、provider-SLA-only partial 判斷與 fallback operator action 建立抽到 `operator_summary_helpers.js`，並把 `operator_summary_panel.js` size guard 從 135 行收緊到 105 行、helper 納入 160 行 guard，讓值班摘要 panel 專注資料載入、DOM 渲染與 CTA 點擊。
- D168：P3-62 補強 Watchlist Panel Action Helper Headroom，將 watchlist load/save/import/delete/run/suggestion API lifecycle 抽到 `watchlist_panel_actions.js`，並把 `watchlist_panel.js` size guard 從 155 行收緊到 120 行、action helper 納入 120 行 guard，讓追蹤清單 panel 專注清單 render、snapshot/report click routing 與事件委派。
- D169：P3-63 補強 App Panel Factory Headroom，將 ops workspace、operator summary、market screener、stock snapshot 與 history workspace 的建立、初始 load 與 panel event binding 抽到 `app_panels.js`，並把 `app.js` size guard 從 230 行收緊到 180 行、panel factory 納入 130 行 guard，讓 app 入口專注全域狀態、report navigation、home tabs 與 analysis stream。
- D170：P3-64 補強 Report Compare Renderer Headroom，將報告比較的 selection summary、compatibility warning 與 result grid renderer 抽到 `report_compare_renderers.js`，並把 `report_compare_panel.js` size guard 從 125 行收緊到 90 行、renderer 納入 100 行 guard，讓比較面板專注選取狀態、API compare lifecycle 與清除/新增事件。
- D171：P3-65 補強 Report Rerun Stream Headroom，將報告重跑 SSE/EventSource payload 解析、status copy、done/error resolve/reject 抽到 `report_rerun_stream.js`，並把 `report_rerun.js` 納入 105 行 guard、stream helper 納入 80 行 guard，讓重跑模組專注按鈕狀態、API 建立/取消、history/provider SLA refresh 與通知。
- D172：P3-66 補強 Ops Workspace Panel/Loader Headroom，將 watchlist snapshot/portfolio risk panel factory 與 provider SLA、active jobs、API quota、performance 四個 loader definition 抽到 `ops_workspace_panels.js`，並把 `ops_workspace.js` size guard 從 125 行收緊到 90 行、ops panels helper 納入 130 行 guard，讓 ops workspace 專注 loaded/dirty/watchlist-once 狀態與 refresh event binding。
- D173：P3-67 補強 Analysis Stream Event Helper Headroom，將 analyze SSE event 的 job/status/pipeline/progress/report_done/done/error/audit UI 與 state handling 抽到 `analysis_stream_events.js`，並把 `analysis_stream.js` 納入 95 行 guard、event helper 納入 120 行 guard，讓 stream 主檔專注 EventSource URL、last_event_id、重連與 close/reset。
- D174：P3-68 補強 Report Preview Rerun Helper Headroom，將 preview rerun button 文字、short label fallback 與模式 B 顯隱邏輯抽到 `report_preview_rerun_helpers.js`，並把 `report_preview_helpers.js` size guard 從 140 行收緊到 115 行、rerun helper 納入 60 行 guard，讓 preview helper 專注報告摘要、品質 badge 與 tracking view model。
- D175：P3-69 補強 Report Preview Tracking Helper Headroom，將 preview tracking 的數字格式、報酬 tone、待新價格判斷、tracking view model 與 DOM render 抽到 `report_preview_tracking_helpers.js`，並把 `report_preview_helpers.js` size guard 從 115 行收緊到 75 行、tracking helper 納入 85 行 guard，讓 preview helper 回到 legacy preview、metrics card 與報告品質 badge。
- D176：P3-70 補強 Stock Snapshot Format Helper Headroom，將股票快照 `panelMethods` 的價格/百分比/compact/事件時序/績效區間圖等純格式化與 chart helper 抽到 `stock_snapshot_format_helpers.js`，並把 `stock_snapshot_helpers.js` size guard 從 320 行收緊到 130 行、format helper 納入 160 行 guard，讓原 helper 專注 fragment renderer 並保留既有 `StockAgentStockSnapshotHelpers.panelMethods` 轉接。
- D177：P3-71 補強 Stock Snapshot Performance Helper Headroom，將股票快照績效區間的 `sparklinePoints()`、`performanceRange()` 與 `performanceRangeChart()` 抽到 `stock_snapshot_performance_helpers.js`，並把 `stock_snapshot_format_helpers.js` size guard 從 160 行收緊到 140 行、performance helper 納入 60 行 guard，讓 format helper 專注價格、百分比、compact 與事件時序等純格式化 label。
- D178：P3-72 補強 Stock Snapshot Numeric Format Helper Headroom，將股票快照價格、報酬、百分比、倍數、compact、財務數字與籌碼數字格式化抽到 `stock_snapshot_numeric_format_helpers.js`，並把 `stock_snapshot_format_helpers.js` size guard 從 140 行收緊到 85 行、numeric helper 納入 90 行 guard，讓 format helper 專注事件、籌碼狀態、分析師細節與其他領域語意 label。
- D179：P3-73 補強 Stock Snapshot CSS Shell Headroom，將股票快照快捷鍵、外框 panel、header、quality badge、action row 與 summary rail 基礎樣式抽到 `styles/stock_snapshot_shell.css`，並把 `styles/stock_snapshot.css` 納入 1820 行 guard、shell CSS 納入 230 行 guard，讓剩餘 CSS 專注各 section 與 responsive 規則。
- D180：P3-74 補強 Stock Snapshot Overview CSS Headroom，將 company profile、market session、trend、performance history 與 technical summary 的 base CSS 抽到 `styles/stock_snapshot_overview.css`，並把 `styles/stock_snapshot.css` size guard 從 1820 行收緊到 1450 行、overview CSS 納入 430 行 guard，讓主 stock snapshot CSS 專注 valuation、research、signal、core sections 與 responsive 規則。
- D181：P3-75 補強 Stock Snapshot Research CSS Headroom，將 valuation range、analyst outlook 與 earnings forecast 的 base CSS 抽到 `styles/stock_snapshot_research.css`，並把 `styles/stock_snapshot.css` size guard 從 1450 行收緊到 1230 行、research CSS 納入 250 行 guard，讓主 stock snapshot CSS 從 signal sections 開始承擔剩餘 section 與 responsive 規則。
- D182：P3-76 補強 Stock Snapshot Signal CSS Headroom，將 share statistics、risk liquidity、profitability quality、dividend profile、event calendar 與 alert suggestions 的 base CSS 抽到 `styles/stock_snapshot_signal.css`，並把 `styles/stock_snapshot.css` size guard 從 1230 行收緊到 760 行、signal CSS 納入 520 行 guard，讓主 stock snapshot CSS 從 fundamentals/core sections 開始承擔剩餘 section 與 responsive 規則。
- D183：P3-77 補強 Stock Snapshot Core CSS Headroom，將 financial health、financial trends、peer comparison 與 ownership flow 的 base CSS 抽到 `styles/stock_snapshot_core.css`，並把 `styles/stock_snapshot.css` size guard 從 760 行收緊到 430 行、core CSS 納入 360 行 guard，讓主 stock snapshot CSS 專注 supplemental sections 與 responsive 規則。
- D184：P3-78 補強 Stock Snapshot Responsive CSS Headroom，將股票快照 760px/520px responsive media query 抽到 `styles/stock_snapshot_responsive.css`，並把 `styles/stock_snapshot.css` size guard 從 430 行收緊到 140 行、responsive CSS 納入 290 行 guard，讓主 stock snapshot CSS 專注 supplemental base styles。
- D185：P3-79 補強 Stock Snapshot Supplemental CSS Headroom，將最後的 supplemental base styles 搬到 `styles/stock_snapshot_supplemental.css`，移除 `styles/stock_snapshot.css` monolith import 與檔案，並以 supplemental CSS 140 行 guard 鎖住底部 grid、metric、news、mode suggestions 與 error state 樣式。
- D186：P3-80 補強 Stock Snapshot Domain Format Helper Headroom，將 compact amount、financial value、lots、flow word 與 coverage label 等領域數字語意搬到 `stock_snapshot_domain_format_helpers.js`，並把 `stock_snapshot_numeric_format_helpers.js` size guard 從 90 行收緊到 70 行、domain helper 納入 55 行 guard，讓 numeric helper 回到通用價格、百分比、倍數與正負 tone 格式化。
- D187：P3-81 補強 Report Preview Action CSS Headroom，將預覽面板的 open/refresh/rerun/cancel button 與 mobile rerun layout 搬到 `styles/preview_panel_actions.css`，並把 `styles/preview_panel.css` size guard 從 220 行收緊到 160 行、action CSS 納入 100 行 guard，讓主 preview CSS 回到面板、summary、tracking 與 stale notice base styles。
- D188：P3-82 補強 Provider SLA Controls CSS Headroom，將 provider SLA window/actions 與跨維運面板共用的 maintenance button/details/result controls 搬到 `styles/provider_sla_controls.css`，並把 `styles/provider_sla.css` size guard 從 220 行收緊到 160 行、controls CSS 納入 100 行 guard，讓 provider SLA 主 CSS 專注 panel、chip、insight 與 provider row visual states。
- D189：P3-83 補強 History List Controls CSS Headroom，將 history filters、version toggle、search、delete button 與 pagination controls 搬到 `styles/history_list_controls.css`，並把 `styles/history_list.css` size guard 從 320 行收緊到 240 行、controls CSS 納入 110 行 guard，讓 history list 主 CSS 專注 workspace、list item、data trust、decision 與 tracking visual states。
- D190：P3-84 補強 Stock Snapshot Signal Events CSS Headroom，將股票快照的 event calendar 與 alert suggestions 樣式搬到 `styles/stock_snapshot_signal_events.css`，並把 `styles/stock_snapshot_signal.css` size guard 從 520 行收緊到 340 行、events CSS 納入 180 行 guard，讓 signal CSS 專注 shares、risk、profitability 與 dividend base visual states。
- D191：P3-85 補強 Stock Snapshot Overview Performance CSS Headroom，將股票快照 performance history、range controls 與 chart 樣式搬到 `styles/stock_snapshot_overview_performance.css`，並把 `styles/stock_snapshot_overview.css` size guard 從 430 行收緊到 320 行、performance CSS 納入 120 行 guard，讓 overview CSS 專注 company profile、session、trend 與 technical summary visual states。
- D192：P3-86 補強 Stock Snapshot Core Peer Ownership CSS Headroom，將股票快照 peer comparison 與 ownership flow 樣式搬到 `styles/stock_snapshot_core_peer_ownership.css`，並把 `styles/stock_snapshot_core.css` size guard 從 360 行收緊到 220 行、peer/ownership CSS 納入 180 行 guard，讓 core CSS 專注 financial health 與 financial trends visual states。
- D193：P3-87 補強 Stock Snapshot Signal Dividend CSS Headroom，將股票快照 dividend profile 與 dividend bars 樣式搬到 `styles/stock_snapshot_signal_dividend.css`，並把 `styles/stock_snapshot_signal.css` size guard 從 340 行收緊到 240 行、dividend CSS 納入 130 行 guard，讓 signal CSS 專注 shares、risk 與 profitability base visual states。
- D194：P3-88 補強 Stock Snapshot Overview Technical CSS Headroom，將股票快照 technical summary 樣式搬到 `styles/stock_snapshot_overview_technical.css`，並把 `styles/stock_snapshot_overview.css` size guard 從 320 行收緊到 240 行、technical CSS 納入 90 行 guard，讓 overview CSS 專注 company profile、session 與 price trend visual states。
- D195：P3-89 補強 Stock Snapshot Research Analyst CSS Headroom，將股票快照 analyst outlook 樣式搬到 `styles/stock_snapshot_research_analyst.css`，並把 `styles/stock_snapshot_research.css` size guard 從 250 行收緊到 170 行、analyst CSS 納入 90 行 guard，讓 research CSS 專注 valuation range 與 earnings forecast visual states。
- D196：P3-90 補強 Stock Snapshot Responsive Mobile CSS Headroom，將股票快照 520px mobile-only responsive rules 搬到 `styles/stock_snapshot_responsive_mobile.css`，並把 `styles/stock_snapshot_responsive.css` size guard 從 290 行收緊到 240 行、mobile responsive CSS 納入 60 行 guard，讓主 responsive CSS 專注 760px tablet/narrow desktop layout rules。
- D197：P3-91 補強 History Shell Tabs CSS Headroom，將首頁 history shell tab controls 搬到 `styles/history_shell_tabs.css`，並把 `styles/history_shell.css` 納入 240 行 guard、tabs CSS 納入 50 行 guard，讓 history shell CSS 專注 history section framing 與 commercial entry launchpad layout。
- D198：P3-92 補強 History Shell Commercial CSS Headroom，將 commercial launchpad、operator brief、entry card 與 status grid styles 搬到 `styles/history_shell_commercial.css`，並把 `styles/history_shell.css` size guard 從 240 行收緊到 80 行、commercial CSS 納入 230 行 guard，讓 history shell CSS 專注 section framing 與 home panel resets。
- D199：P3-93 補強 Stock Snapshot Responsive Header CSS Headroom，將股票快照 760px header stacking、section title display 與 header action alignment rules 搬到 `styles/stock_snapshot_responsive_headers.css`，並把 `styles/stock_snapshot_responsive.css` size guard 從 240 行收緊到 90 行、responsive headers CSS 納入 190 行 guard，讓主 responsive CSS 專注 tablet grid、summary rail、peer row 與 trend returns layout rules。
- D200：P3-94 補強 Stock Snapshot Overview Trend CSS Headroom，將股票快照 price trend、sparkline 與 return chips styles 搬到 `styles/stock_snapshot_overview_trend.css`，並把 `styles/stock_snapshot_overview.css` size guard 從 240 行收緊到 170 行、overview trend CSS 納入 90 行 guard，讓 overview 主 CSS 專注 company profile 與 market session visual states。
- D201：P3-95 補強 History Panel Quality Helper Headroom，將 data trust、evidence exit gate、report conformance、action badge 與 tracking action note 判斷搬到 `history_panel_quality_helpers.js`，並把 `history_panel_helpers.js` size guard 從 220 行收緊到 110 行、quality helper 納入 120 行 guard，讓 history panel helpers 專注 tracking format、target comparison 與 keyboard helpers。
- D202：P3-96 補強 Operator Summary Quality Helper Headroom，將 operator summary 的 report action、data trust refreshability、provider SLA-only partial、evidence exit gate 與 report conformance 判斷搬到 `operator_summary_quality_helpers.js`，並把 `operator_summary_helpers.js` size guard 從 160 行收緊到 90 行、quality helper 納入 95 行 guard，讓 operator summary helpers 專注狀態摘要、watchlist detail 與 action list 組裝。
- D203：P3-97 補強 Report Quality Policy Core，將 History Panel 與 Operator Summary 共用的 data trust status、source stale、provider SLA-only partial、report conformance、evidence exit gate、rerun 與 requires data-trust action 判斷收斂到 `report_quality_policy.js`，並讓兩個畫面 helper 只保留各自 UI 文案與 action 組裝，降低品質政策漂移。
- D204：P3-98 補強 Report Preview Quality Policy Hook，將 report preview 的 report conformance 與 evidence exit gate status/verdict 判斷委派給 `report_quality_policy.js`，保留 preview badge copy 與 markup 在 `report_preview_helpers.js`，讓 preview、history 與 operator summary 共用同一套品質狀態判斷。
- D205：P3-99 補強 Decision Tracking Quality Policy Hook，將 tracking bulk action 的 rerun、stale/source-stale refresh 與 provider SLA-only partial 判斷委派給 `report_quality_policy.js`，避免每日追蹤一鍵處理把「來源提醒、無需刷新/重跑」誤判成可刷新 snapshot action。
- D206：P3-100 補強 Report Rerun Message Policy，將 preview stale notice 與 history tracking action note 的 rerun reason fallback 收斂到 `report_quality_policy.js` 的 `reportRerunMessage()`，避免不同入口對同一份 stale report 顯示不同的重跑原因。
- D207：P3-101 補強 Report Compare Decision Status Policy Hook，將 report compare 的決策狀態 label 改由 `report_quality_policy.js` 判斷 report-level rerun，讓 `analysis_text_stale` 的報告即使 `decision_freshness.status=current` 也會在比較視圖顯示「需重跑」。
- D208：P3-102 補強 Report Preview Rerun Visibility Policy Hook，將 preview stale notice 的顯示與隱藏完全委派給 `report_quality_policy.js` 的 `reportNeedsRerun()`，避免 preview panel 自行讀 `analysis_text_stale` 或 `decision_freshness.requires_rerun` 而繞過共用品質政策。
- D209：P3-103 補強 Decision Tracking Rerun Action Policy Boundary，將 decision tracking bulk action 的完整重跑判斷收斂為只使用 `report_quality_policy.js` 的 `reportNeedsRerun()`，避免一鍵處理直接讀 raw rerun flags 而和 preview、history、compare 入口產生政策漂移。
- D210：P3-104 補強 History Tracking Source Notice Policy Boundary，讓 history tracking note 對 provider SLA-only partial 報告保持「來源提醒、無需刷新/重跑」語意，不再把非 refreshable 的來源提醒顯示成「需刷新資料」。
- D211：P3-105 補強 Decision Tracking Data Refresh Policy Boundary，新增 `report_quality_policy.js` 的 `reportNeedsDataRefresh()`，讓 decision tracking bulk action 的資料刷新判斷不再自行解讀 stale、partial 或 provider SLA-only partial。
- D212：P3-106 補強 Report Compare Freshness Label Policy Boundary，新增 `report_quality_policy.js` 的 `reportDecisionStatusLabel()` 與 `decisionFreshnessStatusLabel()`，讓 report compare 不再自行解讀 `decision_freshness.requires_rerun` 或 `status=needs_rerun`。
- D213：P3-107 補強 UI Data Trust Provider SLA Notice Policy Boundary，新增 `report_quality_policy.js` 的 `dataTrustProviderSlaOnlyPartial()`，讓 `ui_data_trust.js` 不再自行解讀 provider SLA-only partial，且 `critical_failures` 不會被誤標成「來源提醒」。
- D214：P3-108 補強 Operator Summary Fresh Count Policy Boundary，新增 `report_quality_policy.js` 的 `reportHasFreshData()`，讓 operator summary 的「資料新鮮」抽樣計數不再直接讀 `report.data_trust.status`。
- D215：P3-109 補強 History Tracking Refresh Note Policy Boundary，讓 `history_panel_quality_helpers.js` 的 tracking note 只使用 `report_quality_policy.js` 的 `reportNeedsDataRefresh()` 判斷是否顯示「需刷新資料」，不再自行組合 refreshable 與 partial 條件。
- D216：P3-110 補強 History Report Action Badge Refresh Policy Boundary，讓 `history_panel_quality_helpers.js` 的 report action badge 也使用 `report_quality_policy.js` 的 `reportNeedsDataRefresh()` 判斷「建議刷新資料」，與 tracking note 和 decision tracking bulk action 共用同一套刷新政策。
- D217：P3-111 補強 Operator Summary Report Action Refresh Policy Boundary，讓 `operator_summary_quality_helpers.js` 的 report action 使用 `report_quality_policy.js` 的 `reportNeedsDataRefresh()` 判斷「建議刷新資料」，與 history badge、tracking note 與 decision tracking bulk action 共用同一套刷新政策。
- D218：P3-112 補強 Operator Summary Rerun Message Policy Boundary，讓 `operator_summary_quality_helpers.js` 的 report action rerun detail 使用 `report_quality_policy.js` 的 `reportRerunMessage()`，與 preview stale notice 和 history tracking note 共用同一套重跑原因文案。
- D219：P3-113 補強 Report Preview Quality Gate Action Policy Boundary，新增 `report_quality_policy.js` 的 `reportQualityGateAction()`，讓 `report_preview_helpers.js` 的 quality badge 不再自行解讀 report conformance 與 evidence exit gate，而是只負責渲染共用 policy action。
- D220：P3-114 補強 History Report Action Badge Quality Gate Policy Boundary，讓 `history_panel_quality_helpers.js` 的 report action badge 使用 `report_quality_policy.js` 的 `reportQualityGateAction()`，不再自行解讀 report conformance 與 evidence exit gate，與 preview quality badge 共用 gate action 優先序。
- D221：P3-115 補強 Operator Summary Report Action Quality Gate Policy Boundary，讓 `operator_summary_quality_helpers.js` 的 report action 使用 `report_quality_policy.js` 的 `reportQualityGateAction()`，不再自行解讀 report conformance 與 evidence exit gate，與 preview quality badge 和 history action badge 共用 gate action 優先序。
- D222：P3-116 補強 Report Quality Gate Policy Headroom，將 report conformance / evidence exit gate action 文案與優先序拆到 `report_quality_gate_policy.js`，讓 `report_quality_policy.js` 回到 core predicates / delegate bridge，並維持 preview、history、operator summary 透過 `reportQualityGateAction()` 共用 gate action。
- D223：P3-117 補強 Decision Tracking Manual Review Policy Boundary，新增 `report_quality_policy.js` 的 `reportRecommendedAction()`，讓 decision tracking recommended actions 也能把 report conformance / evidence exit gate / data source error 轉成 `manual_review`，且 bulk runner 不再把人工審查誤算為已送出的自動動作。
- D224：P3-118 補強 History Report Action Badge Recommended Action Policy Boundary，讓 `history_panel_quality_helpers.js` 的 report action badge 使用 `report_quality_policy.js` 的 `reportRecommendedAction()` 決定 manual review / rerun / refresh 優先序，並保留無 filename quality gate 的 badge fallback。
- D225：P3-119 補強 Operator Summary Report Action Recommended Action Policy Boundary，讓 `operator_summary_quality_helpers.js` 的 report action 使用 `report_quality_policy.js` 的 `reportRecommendedAction()` 決定 manual review / rerun / refresh 優先序，與 history badge 和 decision tracking action 共用同一個 policy。
- D226：P3-120 補強 Report Preview Rerun Notice Recommended Action Policy Boundary，讓 `report_preview_panel.js` 的 stale notice 使用 `report_quality_policy.js` 的 `reportRecommendedAction()` 判斷是否顯示完整重跑提醒，並只在無 action policy 或無 filename 的 legacy report fallback 到 `reportNeedsRerun()`。
- D227：P3-121 補強 Operator Summary Rerun Count Recommended Action Policy Boundary，讓 `operator_summary_helpers.js` 的「需重跑」摘要計數使用 `reportRecommendedAction()` 的 `rerun_full_report` 作主訊號，避免 manual review / refresh 優先序被 raw stale flag 誤算成重跑。
- D228：P3-122 補強 History Tracking Action Note Recommended Action Policy Boundary，讓 `history_panel_quality_helpers.js` 的 tracking action note 使用 `reportRecommendedAction()` 判斷完整重跑與刷新資料提醒，避免 history tracking note 和 action badge 的優先序分岔。
- D229：P3-123 補強 History Report Action Badge Legacy Fallback Boundary，讓 `history_panel_quality_helpers.js` 的 report action badge 只在無 action policy 或無 filename legacy report 時 fallback 到 raw rerun/refresh predicates，避免有 filename 報告繞過 `reportRecommendedAction()`。
- D230：P3-124 補強 Operator Summary Report Action Legacy Fallback Boundary，讓 `operator_summary_quality_helpers.js` 的 report action 只在無 action policy 或無 filename legacy report 時 fallback 到 raw rerun/refresh predicates，避免 operator summary CTA 對有 filename 報告繞過 `reportRecommendedAction()`。
- D231：P3-125 補強 History Report Action Badge Quality Gate Legacy Fallback Boundary，讓 `history_panel_quality_helpers.js` 的 quality gate fallback 只在無 action policy 或無 filename legacy report 時啟用，避免有 filename 報告在 `reportRecommendedAction()` 回 null 時仍顯示 raw gate badge。
- D232：P3-126 補強 Operator Summary Report Action Quality Gate Legacy Fallback Boundary，讓 `operator_summary_quality_helpers.js` 的 quality gate fallback 只在無 action policy 或無 filename legacy report 時啟用，避免有 filename 報告在 `reportRecommendedAction()` 回 null 時仍產生 raw gate CTA。
- D233：P3-127 補強 Operator Summary Data Trust Action Count Recommended Action Boundary，讓 `operator_summary_helpers.js` 的「需處理」摘要計數使用 `reportRecommendedAction()` 作正式 action 訊號，並只在無 action policy 或無 filename legacy report 時 fallback 到 raw `requiresDataTrustAction()`。
- D234：P3-128 補強 Daily Decision Dashboard Direct Rerun Bucket Repair Boundary，讓 `daily_decision_dashboard.py` 的 `reports_needing_rerun` 與 `rerun_reports` 排除已被 repair queue 判定為 manual review、refresh data snapshot 或 wait provider recovery 的報告，避免 blocked 報告同時被摘要成可直接完整重跑。
- D235：P3-129 補強 Daily Decision Dashboard Direct Rerun Bucket Full Repair Coverage，讓 direct rerun bucket 的 repair 排除使用完整 repair coverage，而不是只使用 dashboard 顯示的前 5 筆 repair item，避免第 6 筆以後的 blocked report 因顯示上限漏進可直接重跑摘要。
- D236：P3-130 補強 Daily Decision Queue Full Repair Coverage For Backtest Skip，讓 daily decision queue 使用完整 repair coverage 作為 action/skip 輸入，而不是只使用 dashboard 顯示的前 5 筆 repair item，避免第 6 筆以後的 blocked report 被排進 backtest due 或其他非 repair lane。
- D237：P3-131 補強 Daily Decision Queue Report Identity Fallback Boundary，讓 daily decision queue 在 report/repair/provider 訊號缺少 filename 時使用 `ticker:pipeline_id` 作為 fallback identity，避免同一份報告被重複排成 report repair 與 provider impact 等多個 action。
- D238：P3-132 補強 Daily Decision Queue Report Filename Alias Boundary，讓 repair action payload 保留 `report_filename` alias 並映射成 queue 的 `filename`/`report_filename` identity，避免上游只提供 `report_filename` 時同一 artifact 被重複排成 repair 與 provider impact action。
- D239：P3-133 補強 Daily Decision Queue Backtest Due Report Filename Alias Boundary，讓 computed backtest due 也使用 `filename` 或 `report_filename` 作為 artifact key，避免上游 report row 只有 `report_filename` 時到期回測工作被漏掉。
- D240：P3-134 補強 Daily Decision Queue Provider Impact Report Filename Alias Boundary，讓 provider impact action payload 保留 `report_filename` alias 並輸出可點回 artifact 的 `filename`/`report_filename`，避免來源等待或監控 action 失去報告目標。
- D241：P3-135 補強 Daily Decision Queue Rerun Report Filename Alias Boundary，讓 rerun report action payload 保留 `report_filename` alias 並輸出可點回 artifact 的 `filename`/`report_filename`，避免完整重跑待辦失去報告目標。
- D242：P3-136 補強 Daily Decision Queue Backtest Due Report Filename Alias Payload Boundary，讓 backtest due action payload 保留 `report_filename` alias 並輸出可點回 artifact 的 `filename`/`report_filename`，避免到期回測待辦失去報告目標。
- D243：P3-137 補強 Notification Plan Report Filename Alias Context Boundary，讓 notification message context 保留 `report_filename` alias，避免外部通知與 delivery outbox 只剩 dedupe identity、失去可追溯的報告 artifact alias。
- D244：P3-138 補強 Notification Plan Report Filename Alias Normalization Boundary，讓 notification message context 在只有 `filename` 或只有 `report_filename` 時雙向補齊 `filename`/`report_filename`，避免外部 sender 或前端消費者因 key 名差異失去 artifact target。
- D245：P3-139 補強 Notification Delivery Outbox Report Context Boundary，讓 delivery outbox entry 保留 `source`、`type`、`ticker`、`filename`、`report_filename` 與 `pipeline_id`，避免 sender 或 audit reconciliation 只看 outbox 時失去 report artifact target。
- D246：P3-140 補強 Notification Delivery Outbox Operator Context Boundary，讓 delivery outbox entry 保留 `priority_score`、`target_panel`、`target_tab`、`operator_action`、`operator_action_label`、`queue_rank`、`queue_displayed_count` 與 `is_top_priority`，避免外部 sender 只看 outbox 時失去每日 queue 排名與下一步 CTA。
- D247：P3-141 補強 Notification Delivery Audit Context Snapshot Boundary，讓 `notification_delivery_audit` 在 `operational.sqlite3` 以 `context_json` 持久化 outbox context snapshot，避免 sender 寫入結果後 audit history 只剩 delivery identity、失去 source、ticker、report artifact、target panel/tab、CTA 與 queue rank。
- D248：P3-142 補強 Notification Delivery Reconcile Audit Context Boundary，讓 `reconcile_outbox_with_audit()` 回傳 `audit_context`，避免 sender 發送前只看 reconcile result 時無法取回已持久化的 source、report artifact、CTA 與 queue rank context。
- D249：P3-143 補強 Notification Delivery Audit Summary Attention Context Boundary，讓 `get_delivery_audit_summary()` 回傳低量 `attention_contexts`，避免 ops dashboard 或 daily queue 只看到 failed/retry count、無法定位失敗通知影響的 source、ticker、report artifact、target panel、CTA 或 queue rank。
- D250：P3-144 補強 Daily Decision Queue Notification Delivery Attention Context Boundary，讓 `fix_notification_delivery` queue item 保留 notification delivery summary 的 `attention_contexts`，避免每日工作台只看到通知通道故障 counts/reasons、失去受影響 source、ticker、report artifact、target panel、CTA 與 queue rank。
- D251：P3-145 補強 Daily Workbench Notification Attention Context Rendering Boundary，讓 operator summary 與 watchlist `今日工作台` 共用 `daily_decision_queue_context.js` 顯示 `attention_contexts` 摘要，避免後端已保留 context 但前端只顯示通知通道故障標題、失去受影響 ticker、report 與 CTA。
- D252：P3-146 補強 Maintenance Notification Attention Context Rendering Boundary，讓 ops maintenance `通知通道` chip 重用 daily queue attention context 摘要，避免維護區只顯示 failed/reason counts、仍看不到受影響 ticker、report 與 CTA。
- D253：P3-147 補強 Notification Attention Context Row Metadata Fallback Boundary，讓 `daily_decision_queue_context.js` 在 `attention_contexts[].context` 為空時退回顯示 `channel_id`、`delivery_status` 與 `attempt_count`，避免 legacy audit row 或極簡 row 無法在 operator summary、watchlist 與 maintenance UI 顯示任何定位資訊，同時不暴露 raw `last_error`。
- D254：P3-148 補強 Notification Attention Context Source Rank Rendering Boundary，讓 `daily_decision_queue_context.js` 在 `attention_contexts[].context` 有 `source` 與 `queue_rank` 時顯示原始來源與隊列排名，避免 operator 只能看到受影響 ticker/report/CTA、卻不知道該故障原本來自哪類 daily queue action 與第幾順位。
- D255：P3-149 補強 Notification Attention Context Queue Scope Rendering Boundary，讓 `daily_decision_queue_context.js` 在 `attention_contexts[].context` 有 `queue_displayed_count` 與 `is_top_priority` 時顯示顯示範圍與最高優先旗標，避免 operator 只知道故障 action 的來源與排名、卻不知道它是否位於每日工作台可見的最高優先集合。
- D256：P3-150 補強 Notification Attention Context Source Label Boundary，讓 `daily_decision_queue_context.js` 在 `attention_contexts[].context.source` 為已知 daily queue source key 時顯示可讀標籤並保留 raw key，例如 `資料來源 (provider_impact)`，避免 operator 看到技術代碼卻仍保留維運回查線索。
- D257：P3-151 補強 Daily Queue Source Label Single Authority Boundary，讓 `daily_decision_queue_context.js` 匯出 `sourceLabel` / `sourceText` 並由 `operator_dashboard_actions.js` 共用，避免 operator action `來源` 與 attention context `原始來源` 各自維護 label map 而漂移；同時將 `watchlist` source 顯示為「追蹤清單」。
- D258：P3-152 補強 Watchlist Daily Board Source Label Boundary，讓 `watchlist_panel_helpers.js` 移除自己的 source label map，改用 `StockAgentDailyQueueContext.sourceLabel()` 顯示今日工作台 `來源`，避免 watchlist 今日工作台與 operator summary 再次出現 source 顯示詞漂移。
- D259：P3-153 補強 Daily Queue Monitor Source Label Boundary，讓 `daily_decision_queue_context.js` 將後端 `monitor` fallback source 顯示為「監控」，避免 no-action queue 或除錯入口露出 raw `monitor` key，同時讓 source label map 覆蓋後端 `SOURCE_ORDER` 的 fallback 來源。
- D260：P3-154 補強 Notification Queue Context Source Labels Boundary，讓 `daily_decision_source_labels.py` 提供 backend source label helper，並由 `free_notification_plan.py` 在 `queue_context` 同時輸出 raw `sources` 與可讀 `source_labels`，避免外部通知 sender 只看到 `provider_impact`、`watchlist` 等技術 key，仍保留 raw key 供維運追溯。
- D261：P3-155 補強 Notification Queue Context Source Texts Boundary，讓 `daily_decision_source_labels.py` 提供 `source_texts()`，並由 `free_notification_plan.py` 在 `queue_context` 輸出可直接顯示的 label-plus-raw-key 字串，例如 `資料來源 (provider_impact)`，避免外部 sender 各自拼接來源文字而漂移。
- D262：P3-156 補強 Notification Message Source Display Context Boundary，讓 `free_notification_plan.py` 在每則 `messages[]` 與 `delivery_outbox[]` context 帶出 `source_label` / `source_text`，避免外部 sender 只消費 message 或 outbox 時又退回 raw source key。
- D263：P3-157 補強 Notification Audit Legacy Source Display Enrichment Boundary，讓 `notification_delivery_audit_context.py` 在 legacy outbox 只有 raw `source` 時自動補 `source_label` / `source_text`，避免 audit history、reconcile 與 attention contexts 失去可讀來源語意。
- D264：P3-158 補強 Notification Attention Context Persisted Source Text Boundary，讓 `daily_decision_queue_context.js` 在顯示 failed delivery `attention_contexts` 時優先使用持久化的 `source_text` 或 `source_label`，避免 audit history 已保存的來源文字被瀏覽器端舊 label map 覆蓋。
- D265：P3-159 補強 Daily Queue Source Label Frontend Backend Drift Guard，讓 `daily_decision_queue_context.js` 匯出 frozen `sourceLabels` 並由 static regression 與 backend `SOURCE_LABELS` 比對，避免新增 daily queue source 時前後端來源顯示 map 靜默漂移。
- D266：P3-160 補強 Daily Queue Source Label Backend Coverage Immutability Guard，讓 backend `SOURCE_LABELS` 改為 immutable mapping，並由 daily queue regression 驗證它覆蓋所有 `SOURCE_ORDER` key，避免 runtime mutation 或新增 queue source 時退回 raw technical key。
- D267：P3-161 補強 Daily Queue Summary Source Display Contract，讓 `decision_queue.summary` 在保留 raw `sources` 之外，同步輸出 `source_labels` 與 `source_texts`，避免 API / UI / notification consumers 為來源分布摘要各自重建 label map。
- D268：P3-162 補強 Notification Plan Queue Context Upstream Source Display Boundary，讓 `notification_plan.queue_context` 在 `decision_queue.summary.source_labels/source_texts` 已存在時直接沿用 upstream 契約，避免通知層重新計算來源顯示文字而覆蓋 daily queue summary 的持久化語意。
- D269：P3-163 補強 Notification Message Action Source Display Preservation Boundary，讓 `notification_plan.messages[]` 與 `delivery_outbox[]` 保留 action 自帶的 `source_label/source_text`，只有缺值時才由 raw `source` fallback，避免外部來源或已持久化顯示文字被預設 backend label map 覆蓋。
- D270：P3-164 補強 Notification Queue Context Partial Source Display Merge Boundary，讓 `notification_plan.queue_context` 對 partial upstream `source_labels/source_texts` 先補齊 raw `sources` 的 fallback，再讓 upstream override 勝出，避免 source distribution 中的 active key 因 summary map 不完整而缺少可讀顯示文字。
- D271：P3-165 補強 Notification Queue Context Blank Source Display Override Guard，讓 `notification_plan.queue_context` 忽略 upstream `source_labels/source_texts` 中的空白或 `None` override，避免可讀 fallback label 被洗成空白。
- D272：P3-166 補強 Notification Queue Context Active Source Display Scope Guard，讓 `notification_plan.queue_context.source_labels/source_texts` 丟棄不在 raw `sources` 分布中的 upstream override key，避免 stale summary map 把非 active source 暴露給 notification sender。
- D273：P3-167 補強 Notification Delivery Audit Context Blank Source Display Guard，讓 `notification_delivery_audit_context` 在 outbox 帶空白 `source_label/source_text` 時視為缺值並由 raw `source` 補可讀 fallback，避免 operational audit history 持久化空白來源文字。
- D274：P3-168 補強 Frontend Attention Context Blank Source Display Guard，讓 `daily_decision_queue_context.js` 顯示 failed delivery attention context 時忽略空白 persisted `source_text/source_label`，再回退到前端共享 source map，避免舊 audit row 或外部 payload 把來源 chip 洗成空白。
- D275：P3-169 補強 Backend Source Label Key Normalization Guard，讓 `daily_decision_source_labels.py` 在查找 label/text 與輸出 source display map 前 trim raw source key，避免偶發前後空白讓 canonical source 退回 raw technical key。
- D276：P3-170 補強 Frontend Source Label Key Normalization Guard，讓 `daily_decision_queue_context.js` 的 `sourceLabel()` / `sourceText()` / attention context raw source lookup 先 trim source key，避免瀏覽器端 action detail 因輸入空白退回 raw technical key。
- D277：P3-171 補強 Notification Message Action Blank Source Display Guard，讓 `notification_plan.messages[]` 與 `delivery_outbox[]` 在 action 自帶空白 `source_label/source_text` 時改用 raw source fallback，避免外部 sender payload 先流出空白來源文字。
- D278：P3-172 補強 Notification Queue Context Source Distribution Key Normalization Guard，讓 `notification_plan.queue_context.sources/source_labels/source_texts` 先 trim raw source distribution key 並保留 normalized upstream override，避免 sender 同時收到空白 key 與 canonical display map key。
- D279：P3-173 補強 Notification Message Source Key Normalization Guard，讓 `notification_plan.messages[]` 與 `delivery_outbox[]` 在 action 自帶前後空白 `source` 時輸出 canonical source key，避免 sender payload 的 raw source 與 readable source_text 分裂。
- D280：P3-174 補強 Notification Source Display Value Trimming Guard，讓 `notification_plan.queue_context` upstream display override 與 action 自帶 `source_label/source_text` 在輸出前 trim value，避免 sender payload 保留格式空白。
- D281：P3-175 補強 Notification Blank Action Source Key Drop Guard，讓 `notification_plan.messages[]` 與 `delivery_outbox[]` 在 action 自帶 whitespace-only `source` 時視同缺值，不把空白 source key 暴露給 sender payload。
- D282：P3-176 補強 Backend Source Display Map Blank Key Drop Guard，讓 `daily_decision_source_labels.source_labels()` / `source_texts()` 在輸出 display map 前丟棄 whitespace-only raw source key，避免 API 或 sender payload 收到空白來源標籤。
- D283：P3-177 補強 Backend Source Count Non-Positive Drop Guard，讓 `daily_decision_source_labels.normalize_source_counts()` 在輸出 source distribution 前丟棄 zero、negative 或無法解析的 raw count，避免 API 或 sender payload 把非 active source 顯示成有效來源列。
- D284：P3-178 補強 Backend Source Display Override Active Key Normalization Guard，讓 `daily_decision_source_labels.source_display_overrides()` 在比對 upstream override 前先 normalize active raw source keys，避免合法 override 因 active source map 仍帶格式空白而被丟棄。
- D285：P3-179 補強 Backend Source Count Invalid Numeric Guard，讓 `daily_decision_source_labels.normalize_source_counts()` 將 boolean、NaN 與 infinity 等 raw count 視為 inactive，避免 source distribution 因 malformed count 丟例外或把 `true` 當成 1 件有效來源。
- D286：P3-180 補強 Backend Source Count Fractional Guard，讓 `daily_decision_source_labels.normalize_source_counts()` 將 fractional raw count 視為 inactive，避免 Python `int()` 將 `1.7` 靜默截斷為 1 件有效來源。
- D287：P3-181 補強 Backend Source Count Integral Numeric Guard，讓 `daily_decision_source_labels.normalize_source_counts()` 要求非字串 numeric raw count 必須等於自身整數值，避免 `Decimal("1.7")` 或 `Fraction(3, 2)` 被 `int()` 靜默截斷為 1 件有效來源。
- D288：P3-182 補強 Backend Source Count Non-Mapping Guard，讓 `daily_decision_source_labels.normalize_source_counts()` 對 `None`、list、tuple 等非 mapping raw source distribution 回傳空 map，避免 malformed summary payload 直接因 `.items()` 中斷 source display 生成。
- D289：P3-183 補強 Backend Source Display Override Value Type Guard，讓 `daily_decision_source_labels.source_display_overrides()` 只接受非空字串 override value，避免 upstream `source_labels/source_texts` 的 numeric 或 boolean 值覆蓋 canonical fallback wording。
- D290：P3-184 補強 Backend Source Key Value Type Guard，讓 `daily_decision_source_labels.source_key()` 只接受字串 source key，避免 numeric、boolean 或 bytes raw source key 被 `str()` 轉成 synthetic technical source label。
- D291：P3-185 補強 Backend Source Display Map Non-Mapping Guard，讓 `daily_decision_source_labels.source_labels()` / `source_texts()` 只接受 mapping-like source distribution，避免 `None`、list 或 tuple malformed payload 中斷或生成 synthetic display map。
- D292：P3-186 補強 Backend Source Display Override Active Sources Non-Mapping Guard，讓 `daily_decision_source_labels.source_display_overrides()` 透過 `_source_keys()` 讀取 active source distribution，避免 `None`、list 或 tuple malformed active source input 中斷或生成 override map。
- D293：P3-187 補強 Backend Source Display Mapping Accessor Failure Guard，讓 `daily_decision_source_labels` 透過 `_source_keys()` / `_source_items()` 吸收 source mapping `keys()` / `items()` accessor 例外，避免 malformed mapping-like payload 中斷來源顯示、count normalization 或 override 合併。
- D294：P3-188 補強 Backend Source Display Malformed Mapping Item Guard，讓 `daily_decision_source_labels._source_items()` 過濾非二欄 mapping item entry，避免 malformed `items()` payload 在 count normalization 或 display override 合併時因 unpack 失敗中斷整體來源顯示。
- D295：P3-189 補強 Backend Source Display Malformed Mapping Key Guard，讓 `daily_decision_source_labels._source_keys()` 忽略字串或 bytes 型 key collection，避免 malformed `keys()` payload 被拆成字元或 byte 值並生成 synthetic source labels。
- D296：P3-190 補強 Backend Source Display Mapping Item Unpack Failure Guard，讓 `daily_decision_source_labels._source_items()` 跳過單筆 item unpack 過程拋例外的 malformed entry，避免一筆 broken source item 中斷 count normalization 或 override 合併並壓掉後續合法來源列。
- D297：P3-191 補強 Backend Source Display Mapping Item Iterator Partial Preservation Guard，讓 `daily_decision_source_labels._source_items()` 保留 iterator 失敗前已解析的合法 source item，避免後續 iterator 例外抹掉已可用的來源列或 override。
- D298：P3-192 補強 Backend Source Display Mapping Key Iterator Partial Preservation Guard，讓 `daily_decision_source_labels._source_keys()` 保留 iterator 失敗前已解析的合法 source key，避免後續 iterator 例外抹掉已可用的 `source_labels`、`source_texts` 或 active override match。
- D299：P3-193 補強 Backend Source Count Conversion Failure Guard，讓 `daily_decision_source_labels._source_count()` 將 raw source count truthiness、`int()` 或 equality comparison 例外視為 inactive count，避免一個 malformed count 物件中斷來源分布輸出並壓掉後續合法來源列。
- D300：P3-194 補強 Backend Source Count Arithmetic Conversion Failure Guard，讓 `daily_decision_source_labels._source_count()` 將 raw source count truthiness 或 `int()` 轉型時的 `ArithmeticError` 視為 inactive count，避免 divide-by-zero 或 arithmetic conversion failure 中斷來源分布輸出。
- D301：P3-195 補強 Notification Action Source Display Type Guard，讓 `free_notification_plan._message_context()` 只保留非空字串型 action-provided `source_label` / `source_text`，避免 numeric 或 boolean action metadata 覆蓋 canonical source wording 並污染 message / delivery_outbox。
- D302：P3-196 補強 Notification Legacy Action Source Key Type Guard，讓 `free_notification_plan._source_counts()` 將 legacy actions 的非字串或空白 `source` 歸入 `unknown`，避免 queue_context source distribution 產生 `"123"` / `"True"` 這類 synthetic source rows。
- D303：P3-197 補強 Notification Queue Context Numeric Conversion Failure Guard，讓 `free_notification_plan._int()` 將 queue summary count / priority numeric conversion failure 視為 0，避免 malformed count 或 priority 物件中斷 notification planning。
- D304：P3-198 補強 Notification Dedupe Identity Malformed Value Guard，讓 `free_notification_plan._identity_part()` 在 dedupe identity value comparison 或 string conversion 失敗時使用 fallback identity part，避免一個 malformed title/report/route identifier 中斷 notification delivery identity generation。
- D305：P3-199 補強 Notification Dedupe Override Malformed Value Guard，讓 `free_notification_plan._dedupe_context()` 忽略 malformed action-provided `dedupe_key` / `message_id` override，並以 derived delivery identity fallback，避免外部 queue metadata 破壞 sender idempotency handoff。
- D306：P3-200 補強 Notification Identity Helper Split，將 dedupe / delivery key / identity part helper 從 `free_notification_plan.py` 抽到 `free_notification_identity.py`，讓 planner 專注通知計畫組裝並把 delivery idempotency 邊界集中測試與維護；`free_notification_plan.py` 從 349 行降到 286 行。
- D307：P3-201 補強 Notification Report Identity Branch Truthiness Guard，讓 `free_notification_identity.py` 在 report/ticker/pipeline/route identity branch selection 先用 `identity_part()` 安全判斷欄位是否可用，避免 malformed filename/report_filename/ticker/pipeline 或 route/warning_id 物件於 truthiness 階段中斷 dedupe identity generation。
- D308：P3-202 補強 Notification Report Filename Context Truthiness Guard，讓 `free_notification_plan._message_context()` 用 string-safe selector 正規化 `filename` / `report_filename` alias，避免 malformed filename truthiness 在 message / delivery_outbox context 組裝階段中斷 notification planning。
- D309：P3-203 補強 Notification Message Context Presence Comparison Guard，讓 `free_notification_plan` 在 message 與 delivery_outbox context 欄位篩選時吸收 malformed metadata equality comparison failure，避免單一 action metadata 物件中斷 notification planning。
- D310：P3-204 補強 Notification Suppression Flag Truthiness Guard，讓 `free_notification_plan._suppress_notification()` 將 malformed `suppress_notification` truthiness failure 視為未抑制，同時保留 `monitor` / `fix_notification_delivery` 的 type-based suppression，避免壞 flag 中斷 notification planning 或隱藏真實通知。
- D311：P3-205 補強 Notification Operator CTA Truthiness Guard，讓 `free_notification_plan._operator_cta_context()` 以 string-safe selector 讀取 `operator_action` / `operatorAction` 與 `operator_action_label` / `operatorActionLabel` / `action_label`，避免 malformed custom CTA truthiness 中斷 notification planning，並保留可字串化的自訂 CTA。
- D312：P3-206 補強 Notification Target Metadata Truthiness Guard，讓 `free_notification_plan._target_context()` 以 string-safe selector 讀取 `target_panel` / `targetPanel` 與 `target_tab` / `targetTab`，避免 malformed custom target truthiness 中斷 notification planning，並保留可字串化的自訂 target panel/tab。
- D313：P3-207 補強 Notification Message Envelope Truthiness Guard，讓 `free_notification_plan._messages()` 以 string-safe fallback 輸出 `type` / `title` / `detail`，避免 malformed message envelope truthiness 中斷 notification planning，並保留可字串化的通知主欄位。
- D314：P3-208 補強 Notification Legacy Actions Type Truthiness Guard，讓 `free_notification_plan._legacy_actions_context()` 以 string-safe type filter 排除 `monitor` fallback，避免 legacy `actions[]` 中 malformed type truthiness 中斷 notification planning 或污染 legacy queue context。
- D315：P3-209 補強 Notification Audit Source Display Truthiness Guard，讓 `notification_delivery_audit_context._has_text()` 以 string-safe text conversion 判斷 `source_label` / `source_text` 是否有內容，避免 malformed persisted source display truthiness 中斷 sender audit persistence，並保留可字串化的外部來源顯示文字。
- D316：P3-210 補強 Notification Attention Context Record Truthiness Guard，讓 `notification_delivery_audit_context.attention_contexts_from_records()` 以 string-safe text/int/dict conversion 輸出 failed delivery attention context，避免 malformed audit row 欄位 truthiness 中斷 notification delivery summary。
- D317：P3-211 補強 Notification Audit Source Key Truthiness Guard，讓 `notification_delivery_audit_context.context_json_from_outbox()` 以 string-safe text conversion 與 source key normalization 處理 raw `source`，避免 malformed source truthiness 中斷 sender audit persistence，並在持久化前 trim 可字串化 source key。
- D318：P3-212 補強 Notification Audit Context Value Equality Guard，讓 `notification_delivery_audit_context.context_json_from_outbox()` 以 identity/type-based presence check 過濾 optional outbox metadata，避免 malformed context value equality comparison 中斷 sender audit persistence，並保留可字串化 metadata 進 context snapshot。
- D319：P3-213 補強 Notification Audit Attempt Result Truthiness Guard，讓 `notification_delivery_audit.record_delivery_attempt()` 以 string-safe conversion 處理 sender 回寫的 `status`、`error` 與 `response_id`，避免 malformed attempt result truthiness 中斷 audit persistence，並保留可字串化錯誤與 response id。
- D320：P3-214 補強 Notification Audit Outbox Identity Truthiness Guard，讓 `notification_delivery_audit._required_text()` 以 string-safe required text extraction 讀取 `delivery_key`、`channel_id`、`message_id` 與 `dedupe_key`，避免 malformed outbox identity truthiness 中斷 audit persistence，並在寫入前 trim 可字串化 identity value。
- D321：P3-215 補強 Notification Audit List Limit Truthiness Guard，讓 `notification_delivery_audit.list_delivery_records()` 以共用 `safe_int()` 做 string-safe integer limit conversion，避免 malformed list limit truthiness 中斷 audit record listing 或 delivery summary generation。
- D322：P3-216 補強 Notification Audit Reconcile Delivery Key Truthiness Guard，讓 `notification_delivery_audit.reconcile_outbox_with_audit()` 以 string-safe delivery key lookup 查找既有 audit row，避免 malformed outbox `delivery_key` truthiness 中斷 sender preflight 或 already-sent suppression。
- D323：P3-217 補強 Notification Audit Reconcile Attempt Count Truthiness Guard，讓 `notification_delivery_audit.reconcile_outbox_with_audit()` 與 `_retry_exhausted()` 以 string-safe integer conversion 讀取 persisted attempt metadata，避免 malformed `attempt_count` truthiness 中斷 retry budget 或 next-attempt calculation。
- D324：P3-218 補強 Notification Audit Reconcile Retry Timestamp Truthiness Guard，新增共用 `safe_float()` 並讓 `notification_delivery_audit.reconcile_outbox_with_audit()` / `_next_retry_at()` 以 string-safe float conversion 讀取 retry backoff 與 persisted `last_attempt_at`，避免 malformed retry timestamp truthiness 中斷 retry wait calculation。
- D325：P3-219 補強 Notification Audit Reconcile Status Truthiness Guard，讓 `notification_delivery_audit.reconcile_outbox_with_audit()`、`_retry_exhausted()` 與 `_next_retry_at()` 以 string-safe text conversion 讀取 persisted `delivery_status`，避免 malformed audit status truthiness 中斷 already-sent、retry-exhausted 或 retry-wait decisions。
- D326：P3-220 補強 Notification Audit Reconcile Text Metadata Truthiness Guard，讓 `notification_delivery_audit.reconcile_outbox_with_audit()` 以 string-safe conversion 回傳 persisted `last_error` 與 `last_response_id`，避免 malformed audit text metadata truthiness 中斷 sender preflight result assembly。
- D327：P3-221 補強 Notification Audit Reconcile Context Truthiness Guard，讓 `notification_delivery_audit.reconcile_outbox_with_audit()` 以 dict-safe conversion 回傳 persisted audit context，避免 malformed audit context truthiness 中斷 sender preflight context recovery。
- D328：P3-222 補強 Notification Delivery Observability Summary Truthiness Guard，讓 `notification_delivery_observability.notification_delivery_dashboard_summary()` 以 dict-safe conversion 正規化 summary 與 Prometheus count maps，避免 malformed summary 或 count-map truthiness 中斷外部 delivery health metrics。
- D329：P3-223 補強 Notification Delivery Failure Reason Truthiness Guard，讓 `notification_delivery_reason.failure_reason_bucket()` 以 string-safe error conversion 分類 persisted `last_error`，避免 malformed error truthiness 中斷 low-cardinality delivery health summaries。
- D330：P3-224 補強 Notification Delivery Summary Channel Truthiness Guard，讓 `notification_delivery_audit.get_delivery_audit_summary()` 以 string-safe channel conversion 統計 `channel_counts`，避免 malformed `channel_id` truthiness 中斷 delivery health channel distribution。
- D331：P3-225 補強 Notification Delivery Summary Status Equality Guard，讓 `notification_delivery_audit.get_delivery_audit_summary()` 以 string-safe status conversion 統計 sent/failed/pending 與 failure reason rows，避免 malformed `delivery_status` equality 中斷 delivery health status distribution。
- D332：P3-226 補強 Notification Delivery Observability Count Conversion Guard，讓 `notification_delivery_observability._metric_int()` 以 integer-safe conversion 正規化 dashboard 與 Prometheus counts，避免 malformed count conversion 中斷外部 delivery health metrics。
- D333：P3-227 補強 Notification Delivery Prometheus Label Truthiness Guard，讓 `notification_delivery_observability.notification_delivery_prometheus_lines()` 以 string-safe conversion 正規化 channel/reason labels，避免 malformed label truthiness 中斷外部 delivery health metrics。
- D334：P3-228 補強 Prometheus Label Truthiness Guard，讓 `api_observability_service._labels()` 以 string-safe key/value conversion 渲染 Prometheus labels，避免 malformed provider、queue 或 delivery label truthiness 中斷 metrics output。
- D335：P3-229 補強 Prometheus Alert Level Truthiness Guard，讓 `api_observability_service.build_prometheus_metrics()` 以 string-safe conversion 正規化 provider `alert_level`，避免 malformed alert level truthiness 中斷 provider alert gauges。
- D336：P3-230 補強 Prometheus Queue Label Truthiness Guard，讓 `api_observability_service.build_prometheus_metrics()` 以 string-safe conversion 正規化 queue `backend` 與 `queue_name` labels，避免 malformed queue label truthiness 中斷 queue gauges。
- D337：P3-231 補強 Prometheus Queue Availability Truthiness Guard，讓 `api_observability_service.build_prometheus_metrics()` 以 bool-safe conversion 正規化 queue `available` gauge，避免 malformed queue availability truthiness 中斷 queue gauges。
- D338：P3-232 補強 Prometheus Named Queue Map Truthiness Guard，讓 `api_observability_service.build_prometheus_metrics()` 以 dict-safe conversion 正規化 queue `queues` map 與 named queue details，避免 malformed queue map/detail truthiness 中斷 named queue depth gauges。
- D339：P3-233 補強 Prometheus Integer Metric Conversion Guard，讓 `api_observability_service._metric_int()` 以 integer-safe conversion 正規化 provider attempts/error count 與 queue depth gauges，避免 malformed provider 或 queue count conversion 中斷 metrics output。
- D340：P3-234 補強 Prometheus Float Metric Conversion Guard，讓 `api_observability_service._metric_number()` 以 float-safe conversion 正規化 provider success-rate gauge，避免 malformed provider success-rate conversion 中斷 metrics output。
- D341：P3-235 補強 Provider SLA Window Alert Conversion Guard，讓 `api_observability_service._alert_fields_for_window()` 以 integer-/float-/string-safe conversion 正規化 provider attempts、success-rate、error count 與 status，避免 malformed provider SLA window values 中斷 dashboard alert recalculation。
- D342：P3-236 補強 Provider SLA Window Map Truthiness Guard，讓 `api_observability_service.apply_provider_sla_window()` 以 dict-safe conversion 正規化 provider `windows` 與 selected-window stats maps，避免 malformed provider SLA window map truthiness 中斷 dashboard alert recalculation。
- D343：P3-237 補強 Provider SLA Provider Row Mapping Guard，讓 `api_observability_service.apply_provider_sla_window()` 以 dict-safe conversion 正規化 provider rows，再進行 window selection 與 alert recalculation，避免 malformed provider row mapping conversion 中斷 dashboard alert recalculation。
- D344：P3-238 補強 Provider SLA Alert Projection Guard，讓 `api_observability_service.alerts_from_providers()` 以 dict-safe row conversion 與 string-safe alert-level conversion 投影 warning/critical alerts，避免 malformed alert row mapping 或 alert level hashing 中斷 dashboard alert lists。
- D345：P3-239 補強 Provider SLA All-Window Cumulative Alert Projection Guard，讓 `api_observability_service.build_provider_sla_payload(window="all")` 將 cumulative alerts 也導入 `alerts_from_providers()`，避免 malformed cumulative alert rows 繞過 dashboard alert-list guard。
- D346：P3-240 補強 Provider SLA All-Window Provider Summary Guard，讓 `api_observability_service.build_provider_sla_payload()` 在 payload 邊界先以 dict-safe row conversion 正規化 provider summary rows，避免 malformed cumulative provider rows 繞過 provider-list guard。
- D347：P3-241 補強 Provider SLA Payload Helper Headroom，將 provider SLA window normalization、window projection、alert projection 與 provider SLA payload builder 抽到 `provider_sla_observability.py`，讓 `api_observability_service.py` 回到維運 API 聚合角色並從 348 行降到 248 行。
- D348：P3-242 補強 Prometheus Provider Row Mapping Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 provider gauge 渲染前以 dict-safe row conversion 正規化 provider rows，避免 malformed provider row mapping 中斷 `/metrics` 或產生空 label provider series。
- D349：P3-243 補強 Prometheus Queue Snapshot Mapping Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 queue gauge 渲染前以 dict-safe conversion 正規化整個 queue snapshot，避免 malformed queue snapshot mapping 中斷 `/metrics`，並降級為 unknown/zero queue gauges。
- D350：P3-244 補強 Prometheus Provider Summary Fetch Failure Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 provider SLA summary fetcher 丟例外時降級為空 provider series，避免 provider SLA storage 或 aggregation failure 中斷 queue 與 notification delivery metrics output。
- D351：P3-245 補強 Prometheus Queue Snapshot Fetch Failure Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 queue snapshot fetcher 丟例外時降級為 unknown/zero queue gauges，避免 queue observer 或 backend failure 中斷 provider 與 notification delivery metrics output。
- D352：P3-246 補強 Prometheus Notification Delivery Summary Fetch Failure Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 notification delivery audit summary fetcher 丟例外時降級為空 delivery summary，避免 notification audit storage 或 aggregation failure 中斷 provider 與 queue metrics output。
- D353：P3-247 補強 Prometheus Provider Summary Iterable Shape Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 provider SLA summary payload 不可迭代時降級為空 provider series，避免 malformed provider summary payload shape 中斷 queue 與 notification delivery metrics output。
- D354：P3-248 補強 Prometheus Provider Summary Iterator Partial Failure Guard，讓 `api_observability_service.build_prometheus_metrics()` 在 provider SLA summary iterator 中途丟例外時保留已讀取的合法 provider rows，避免單一 iterator failure 清空先前有效 provider series 或中斷 queue 與 notification delivery metrics output。
- D355：P3-249 補強 Provider SLA Payload Fetch Failure Guard，讓 `provider_sla_observability.build_provider_sla_payload()` 在 provider summary 或 cumulative alert fetcher 丟例外時局部降級為空 providers/alerts，避免 provider SLA storage 或 aggregation failure 中斷 selected-window dashboard payload 或壓掉仍可用的 provider summary rows。
- D356：P3-250 補強 Ops Dashboard Queue Snapshot Fetch Failure Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 queue snapshot fetcher 丟例外時降級為 unavailable unknown queue 並將 dashboard status 標為 critical，避免 queue observer 或 backend failure 壓掉 jobs、provider、API quota 與 notification delivery sections。
- D357：P3-251 補強 Ops Dashboard Notification Delivery Summary Fetch Failure Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 notification delivery audit summary fetcher 丟例外時降級為空 delivery summary，避免 notification audit storage 或 aggregation failure 壓掉 jobs、queue、provider 與 API quota sections。
- D358：P3-252 補強 Ops Dashboard API Quota Payload Failure Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 API quota payload builder 丟例外時降級為空 quota services，避免 local quota ledger 或 aggregation failure 壓掉 jobs、queue、provider 與 notification delivery sections。
- D359：P3-253 補強 Ops Dashboard Job Snapshot Failure Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 job telemetry 或 latency snapshot builder 丟例外時降級為空 job sections 並將 dashboard status 標為 warning，避免 jobs observer failure 壓掉 queue、provider、API quota 與 notification delivery sections。
- D360：P3-254 補強 Ops Dashboard Provider Payload Shape Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 provider SLA payload 無法轉成 mapping 時降級為空 last_24h provider state，避免 malformed provider payload shape 壓掉 jobs、queue、API quota 與 notification delivery sections。
- D361：P3-255 補強 Ops Dashboard Job Payload Shape Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 jobs snapshot payload 無法轉成 mapping 時降級為空 job sections 並將 dashboard status 標為 warning，避免 malformed job payload shape 壓掉 queue、provider、API quota 與 notification delivery sections。
- D362：P3-256 補強 Ops Dashboard API Quota Payload Shape Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 API quota payload 無法轉成 mapping 時降級為空 quota services，避免 malformed quota payload shape 外溢或壓掉 jobs、queue、provider 與 notification delivery sections。
- D363：P3-257 補強 Ops Dashboard Provider Alerts Shape Guard，讓 `api_observability_service.build_ops_dashboard_payload()` 在 provider alert list 無法迭代或中途失敗時降級為空 alerts，避免 malformed provider alert payload shape 壓掉 jobs、queue、API quota 與 notification delivery sections。
- D364：P3-258 補強 Ops Dashboard Provider Alert Source Shape Guard，讓 provider alert impact 分類使用 `safe_text()` 讀取 `source`，避免畸形 source truthiness 中斷 jobs、queue、API quota 與 notification delivery sections。
- D365：P3-259 補強 Ops Dashboard Provider Alert Level Shape Guard，讓 provider alert impact 投影階段以 `safe_text()` 正規化 `alert_level`，避免畸形 alert-level equality 中斷 dashboard status/count 聚合與其他 sections。
- D366：P3-260 補強 Ops Dashboard Queue Availability Shape Guard，讓 `build_ops_dashboard_payload()` 以 `_metric_bool()` 正規化 `queue.available` 後再做 status 聚合與 payload 輸出，避免畸形 queue availability truthiness 壓掉 jobs、provider、API quota 與 notification delivery sections。
- D367：P3-261 補強 Ops Dashboard Stuck Job Count Shape Guard，讓 `_dashboard_status()` 以 `safe_dict()` 與 `safe_int()` 讀取 `jobs.stuck_jobs.count`，避免畸形 stuck job count truthiness 壓掉 queue、provider、API quota 與 notification delivery sections。
- D368：P3-262 補強 Ops Dashboard Job Unavailable Flag Shape Guard，讓 `_dashboard_status()` 以 `_metric_bool()` 讀取 `jobs.observability_unavailable`，避免畸形 job unavailable flag truthiness 壓掉 queue、provider、API quota 與 notification delivery sections。
- D369：P3-263 補強 Ops Dashboard Nested Job Sections Shape Guard，讓 `build_ops_dashboard_payload()` 在輸出 `jobs`、`job_latency`、`stuck_jobs`、`node_telemetry` 與 `model_route_budget` 前以 `safe_dict()` 正規化，避免畸形 nested job telemetry section 外溢或壓掉 queue、provider、API quota 與 notification delivery sections。
- D370：P3-264 補強 Ops Dashboard API Quota Services Shape Guard，讓 `build_ops_dashboard_payload()` 在輸出 `api_quotas.services` 前以 list-of-dict safe conversion 正規化，避免畸形 quota service collection 外溢或壓掉 jobs、queue、provider 與 notification delivery sections。
- D371：P3-265 補強 Ops Dashboard Provider Selected Window Shape Guard，讓 `build_ops_dashboard_payload()` 在輸出 `providers.selected_window` 前以 string-safe conversion 正規化，避免畸形 selected-window 值外溢非 JSON-safe 物件或壓掉 jobs、queue、API quota 與 notification delivery sections。
- D372：P3-266 補強 Ops Dashboard Queue Metadata Shape Guard，讓 `build_ops_dashboard_payload()` 在輸出 queue backend、queue_name、depth 與 queues map 前以 string-, integer- 與 dict-safe conversion 正規化，避免畸形 queue metadata 外溢非 JSON-safe 物件或壓掉 jobs、provider、API quota 與 notification delivery sections。
- D373：P3-267 補強 Ops Dashboard Free Mode Provider Summary Shape Guard，讓 `_free_mode_dashboard_summary()` 以 dict-, list-, bool- 與 string-safe conversion 正規化 free-mode provider contract，避免畸形 provider list 或 cost tier truthiness 壓掉 jobs、queue、provider、API quota 與 notification delivery sections。
- D374：P3-268 補強 Ops Dashboard Free Mode Violations Shape Guard，讓 `_free_mode_dashboard_summary()` 在輸出 `free_mode.violations` 前以 string-safe conversion 正規化，避免畸形 violation entry 外溢非 JSON-safe 物件或壓掉 jobs、queue、provider、API quota 與 notification delivery sections。
- D375：P3-269 補強 Ops Dashboard Named Queue Details Shape Guard，讓 `build_ops_dashboard_payload()` 在輸出 `queue.queues` 前以 string-key 與 dict-safe conversion 正規化每個 named queue detail，避免畸形 queue key/detail 外溢非 JSON-safe 物件或壓掉 jobs、provider、API quota 與 notification delivery sections。
- D376：P3-270 補強 Ops Dashboard Named Queue Detail Fields Shape Guard，讓 `build_ops_dashboard_payload()` 在輸出 `queue.queues.*.depth`、`registries` 與補充欄位前以 integer-, string- 與 registry-map safe conversion 正規化，避免畸形 named queue count 或 supplemental detail 外溢非 JSON-safe 物件或壓掉 jobs、provider、API quota 與 notification delivery sections。
- D377：P3-271 補強 Ops Dashboard Queue Supplemental Fields Shape Guard，並抽出 `queue_dashboard_payload.normalize_ops_queue_payload()`，讓 `queue.registries`、`active_tasks`、`oldest_queued_seconds`、`job_timeout_seconds` 與 `error` 以 integer-, float-, string- 與 registry-map safe conversion 正規化，避免 top-level queue supplemental metadata 外溢非 JSON-safe 物件或壓掉 jobs、provider、API quota 與 notification delivery sections。
- D378：P3-272 補強 Ops Dashboard Queue Age Finite Float Guard，讓 `queue_dashboard_payload.normalize_ops_queue_payload()` 在輸出 `oldest_queued_seconds` 前以 finite-float conversion 將 NaN / Infinity 降級為 `0.0`，避免 queue age 外溢非標準 JSON number。
- D379：P3-273 補強 Ops Dashboard Provider Alert Success Rate Finite Float Guard，讓 `build_ops_dashboard_payload()` 在輸出 `providers.alerts[].success_rate` 前以 finite-float conversion 將 NaN / Infinity 降級為 `0.0`，避免 provider alert rate 外溢非標準 JSON number。
- D380：P3-274 補強 Ops Dashboard Provider Alert Text Fields Shape Guard，將 provider alert dashboard payload shaping 收斂到 `provider_sla_observability.dashboard_provider_alert_payload()`，讓 `source`、`provider`、`alert_message`、`last_status`、`alert_basis`、`selected_window` 與 `windows` 在輸出前走 string- / dict-safe conversion，避免 provider alert 文字與 window 欄位外溢非 JSON-safe 物件。
- D381：P3-275 補強 Provider SLA Alert Projection Output Fields Shape Guard，讓 `provider_sla_observability.alerts_from_providers()` 在輸出 `source`、`provider`、`alert_message`、`success_rate`、`last_status`、`alert_basis`、`selected_window` 與 `windows` 前走 string- / finite-float- / dict-safe conversion，避免 `/api/observability/provider-sla` alert list 外溢非 JSON-safe 值。
- D382：P3-276 補強 Provider SLA Window Numeric Output Fields Shape Guard，讓 `provider_sla_observability.apply_provider_sla_window()` 在輸出 selected-window `attempts`、各類 count、`success_rate`、`avg_duration_ms` 與 `total_records` 前走 integer- / finite-float-safe conversion，避免 `/api/observability/provider-sla` provider row 外溢非 JSON-safe 數值。
- D383：P3-277 補強 Provider SLA All-Window Provider Numeric Output Fields Shape Guard，抽出 `provider_sla_payload_shape.py` 共用數值欄位 shaping，讓 `build_provider_sla_payload(window="all")` 的 cumulative provider `attempts`、各類 count、`success_rate`、`avg_duration_ms` 與 `total_records` 也走 integer- / finite-float-safe conversion，避免 all-window provider row 外溢非 JSON-safe 數值。
- D384：P3-278 補強 Provider SLA Nested Window Numeric Output Fields Shape Guard，讓 `provider_sla_payload_shape.normalize_provider_sla_windows()` 對 provider rows、alert projection 與 ops dashboard alert bridge 裡的 `windows.*` stats 走 integer- / finite-float-safe conversion，避免 nested window map 外溢非 JSON-safe 數值。
- D385：P3-279 補強 Provider SLA Window Selection Shape Guard，讓 `provider_sla_observability.normalize_sla_window()` 以 string-safe conversion 正規化 window 參數，避免 selected-window 物件 truthiness 或 string conversion 畸形時中斷 `/api/observability/provider-sla` payload generation。
- D386：P3-280 補強 Provider SLA Apply Window Nested Output Shape Guard，讓 `apply_provider_sla_window()` 在直接回傳 selected-window provider rows 前也走 `normalize_provider_sla_numeric_fields()`，避免 direct helper callers 繞過 nested `windows.*` numeric shaping。
- D387：P3-281 補強 Provider SLA Nested Window Canonical Key Guard，讓 `provider_sla_payload_shape.normalize_provider_sla_windows()` 將 nested window keys trim/lower 後只保留 `last_1h`、`last_24h`、`last_7d`，避免 experimental 或 malformed window buckets 外溢到 API/UI contracts。
- D388：P3-282 補強 Provider SLA Alert Policy Window Stats Truthiness Guard，讓 `provider_sla_alert_policy.provider_alert_fields()` 與 `alert_basis()` 以 dict-, integer-, float- 與 string-safe conversion 選擇 SLA basis，避免 malformed window stats truthiness 中斷上游 provider alert generation。
- D389：P3-283 補強 Data Trust Provider SLA Evidence Attempts Truthiness Guard，讓 `data_trust_sla_policy._evidence_attempts()` 與 `_safe_int()` 不再透過 truthiness 讀取 alert basis/window attempts，避免 malformed provider SLA alert evidence 中斷報告資料可信度降級決策。
- D390：P3-284 補強 Data Trust Provider SLA Alert Matching Text Truthiness Guard，讓 `data_trust_sla_policy.matched_provider_sla_alerts()` 與 `_compact_alert()` 以 string-safe conversion 讀取 alert source/provider/level/message，避免 malformed alert text truthiness 中斷報告資料可信度降級決策。
- D391：P3-285 補強 Data Trust Provider SLA Source Audit Truthiness Guard，讓 `data_trust_sla_policy.current_provider_entries()`、`current_source_health()`、`_audit_entry_is_healthy()`、`_current_fetch_is_healthy()` 與 `_compact_alert()` 以 string-, integer- 與 bool-safe conversion 讀取本次 `source_audit` entry，避免 malformed current source audit truthiness 中斷報告資料可信度降級決策。
- D392：P3-286 補強 Data Trust Provider SLA Trust Metadata Truthiness Guard，讓 `data_trust_sla_policy.apply_provider_sla_to_trust()` 以 list- 與 string-safe conversion 合併既有 trust `status`、`reason_codes` 與 `notes`，避免 malformed trust metadata truthiness 在 provider SLA alert 已匹配後中斷資料可信度降級決策。
- D393：P3-287 補強 Data Trust Provider SLA Alert Collection Truthiness Guard，讓 `data_trust_sla_policy.matched_provider_sla_alerts()` 以 iterable-safe conversion 走訪 provider SLA alert collection，避免 malformed alert list truthiness 或 iterator failure 在逐筆 alert matching 前中斷報告資料可信度降級決策。
- D394：P3-288 補強 Data Trust Provider SLA Source Audit Collection Iterator Guard，讓 `data_trust_sla_policy.current_provider_entries()` 以 iterable-safe conversion 走訪本次 `source_audit` collection，避免 malformed source audit iterator failure 抹掉已解析的有效 audit entry 或中斷報告資料可信度降級決策。
- D395：P3-289 補強 Data Trust Provider SLA Alert Fetch Failure Guard，讓 `data_trust_sla_policy.matched_provider_sla_alerts()` 在 `alerts=None` 讀取 provider SLA alert helper 或 storage 失敗時降級為空 alerts，避免 provider SLA observability 輔助資料失敗中斷既有報告 trust payload。
- D396：P3-290 補強 Data Trust Provider SLA Trust Metadata Iterator Preserve Guard，讓 `data_trust_sla_policy._safe_text_list()` 逐項保留已成功解析的 trust `reason_codes` 與 `notes`，避免 malformed metadata iterator failure 抹掉既有報告 trust context。
- D397：P3-291 補強 Data Trust Scoring Audit Source Truthiness Guard，讓 `data_trust_scoring.latest_audit_by_source()`、`_stale_sources_from()` 與 `is_core_source()` 以 string-safe conversion 讀取 audit/source freshness source 名稱，避免 malformed source truthiness 中斷報告 trust scoring 或抹掉有效 source audit 判斷。
- D398：P3-292 補強 Data Trust Audit Entry Text Truthiness Guard，讓 `data_trust_audit.build_source_audit_entry()`、`source_label()` 與 `audit_status_label()` 以 string-safe conversion 讀取 source、provider、error kind、message 與 label/status 文字，避免 malformed text truthiness 中斷來源審計證據建立。
- D399：P3-293 補強 Data Trust Source Record Count Truthiness Guard，讓 `data_trust_audit.source_record_count()` 以 string-safe conversion 讀取 source key，避免 malformed source truthiness 中斷 prompt source audit 與 merged evidence count 計算。
- D400：P3-294 補強 Data Trust Audit Entry Status Text Guard，讓 `data_trust_audit.build_source_audit_entry()` 以 string-safe conversion 正規化 status，避免可轉為合法 audit status 的 malformed text 被誤分類為 `unavailable`。
- D401：P3-295 補強 Data Trust Audit Entry Record Count Truthiness Guard，讓 `data_trust_audit.build_source_audit_entry()` 以 integer-safe conversion 寫入 `record_count`，避免可轉整數的 malformed numeric truthiness 中斷來源審計證據建立或抹掉有效筆數。
- D402：P3-296 補強 Data Trust Audit Entry Bool Truthiness Guard，讓 `data_trust_audit.build_source_audit_entry()` 以 bool-safe conversion 寫入 `cache_hit` 與 `stale`，避免 malformed bool truthiness 中斷來源審計證據建立。
- D403：P3-297 補強 Data Trust String List Truthiness Guard，讓 `data_trust_audit.string_list()` 以 string-safe conversion 正規化 scalar/list/tuple 文字，避免 malformed text truthiness 中斷 reason code、score reason 與 trust metadata normalization。
- D404：P3-298 補強 Data Trust Snapshot Existing Trust Truthiness Guard，讓 `data_trust_snapshot.build_data_snapshot()` 以 dict-safe selection 沿用既有 `data_trust` metadata，避免 malformed `data_trust` truthiness 中斷 snapshot generation 或抹掉有效 trust metadata。
- D405：P3-299 補強 Data Trust Snapshot Refresh Flag Truthiness Guard，讓 `data_trust_snapshot.build_data_snapshot()` 以 bool-safe conversion 寫入 `refreshed_without_analysis_rerun`，避免 malformed refresh metadata truthiness 中斷 snapshot generation。
- D406：P3-300 補強 Data Trust Snapshot Rerun Context Text Truthiness Guard，讓 `data_trust_snapshot.snapshot_text()` 與 snapshot size governance 以 string-safe conversion 處理 rerun context analysis text，避免 malformed analysis text truthiness 中斷 snapshot generation 或 rerun context preservation。
- D407：P3-301 補強 Data Trust Snapshot Sanitizer String Conversion Guard，讓 `data_trust_snapshot.sanitize_for_snapshot()` 以 string-safe conversion 處理 snapshot dict key 與 fallback object value，避免 malformed object string conversion 中斷 snapshot generation 或外洩空 key。
- D408：P3-302 補強 Data Trust Snapshot Integrity Hash Truthiness Guard，讓 `data_trust_snapshot.verify_data_snapshot_integrity()` 以 string-safe conversion 讀取 `snapshot_hash` 與 `content_hash`，避免 malformed hash metadata truthiness 中斷 snapshot verification。
- D409：P3-303 補強 Data Trust Snapshot Rerun Context Agent Key Conversion Guard，讓 `data_trust_snapshot.sanitize_rerun_context()` 以 string-safe conversion 正規化 analysis agent key，避免 malformed key string conversion 中斷 snapshot generation 或外洩壞掉的 rerun context key。
- D410：P3-304 補強 Data Trust Snapshot Content Hash Key Conversion Guard，讓 `data_trust_snapshot.snapshot_content_hash()` 以 string-safe conversion 正規化 top-level snapshot key，避免 malformed key 於 JSON sort/encoding 階段中斷 integrity verification 或外洩非 JSON-safe hash input。
- D411：P3-305 補強 Data Trust Snapshot Size Governance Sanitizer Input Guard，讓 `data_trust_snapshot.apply_snapshot_size_governance()` 在 JSON round-trip 前復用 snapshot sanitizer，避免 malformed key 於 size governance 階段中斷 snapshot generation 或外洩非 JSON-safe snapshot input。
- D412：P3-306 補強 Data Trust Snapshot Size Bytes Sanitizer Input Guard，讓 `data_trust_snapshot.snapshot_size_bytes()` 在 JSON size measurement 前復用 snapshot sanitizer，避免 malformed key 中斷 size calculation 或外洩非 JSON-safe snapshot input。
- D413：P3-307 補強 Data Trust Snapshot Identity Field Truthiness Guard，讓 `data_trust_snapshot.build_data_snapshot()` 與 `report_reproducibility.build_reproducibility_packet()` 以 string-safe context/data selection 正規化 ticker、company name 與 pipeline identity，避免 malformed identity truthiness 中斷 snapshot generation 或 reproducibility packet identity。
- D414：P3-308 補強 Data Trust Reproducibility Source Audit Metadata Truthiness Guard，讓 `report_reproducibility.provider_list_from_audit()` 與 `source_data_time()` 以 string-safe provider/timestamp extraction 正規化 source audit metadata，避免 malformed provider 或 fetched-at truthiness 中斷 snapshot generation 或抹掉有效 traceability 欄位。
- D415：P3-309 補強 Data Trust Explicit Target Price Detector String Conversion Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 的 target path key 與 target value 以 string-safe conversion 正規化，避免 malformed parsed 或 structured output 欄位中斷 snapshot guardrail generation 或抹掉後續有效 detected target fields。
- D416：P3-310 補強 Data Trust Explicit Target Price Detector List Iterator Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed 或 structured output list iterator 中途失敗時保留已解析的有效 target fields，避免 malformed collection 抹掉已偵測到的明確目標價欄位。
- D417：P3-311 補強 Data Trust Explicit Target Price Detector Mapping Iterator Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed 或 structured output mapping items iterator 中途失敗時保留已解析的有效 target fields，避免 malformed object 抹掉已偵測到的明確目標價欄位。
- D418：P3-312 補強 Data Trust Explicit Target Price Detector Non-Finite Numeric Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 忽略 NaN 與 Infinity 這類非有限 numeric target，避免 malformed parsed output 產生假的 explicit target-price evidence。
- D419：P3-313 補強 Data Trust Score Normalization Conversion Failure Guard，讓 `data_trust_scoring.normalize_data_trust()` 在既有 trust score 的 float conversion 出現 runtime、arithmetic 或 attribute failure 時回落到 status-derived score，避免 malformed score 中斷 snapshot generation。
- D420：P3-314 補強 Prompt Source Audit Summary Field Conversion Guard，讓 `prompt_source_audit.prompt_source_audit_summary()` 對 provider、status、record_count、cache_hit、stale 與 message 做 string-/integer-/bool-safe conversion，避免 malformed source audit 欄位中斷 prompt JSON generation。
- D421：P3-315 補強 Prompt Compact List Iterator Preserve Guard，讓 `prompt_builder._compact_list()` 不依賴 compact list truthiness，並在 iterator 中途失敗時保留已解析項目，避免 malformed compact source list 中斷 prompt JSON generation。
- D422：P3-316 補強 Prompt History Rows Year Iterator Preserve Guard，讓 `prompt_builder._prompt_history_rows()` 以 truthiness- 與 iterator-safe conversion 讀取 `years`，在 malformed year iterator 中途失敗時保留已解析年度列，避免 history rows 中斷 prompt JSON generation。
- D423：P3-317 補強 Prompt History Value Sequence Guard，讓 `prompt_builder._prompt_history_rows()` 與 `financial_tools.build_financial_tool_context()` 以 truthiness- 與 iterator-safe sequence conversion 讀取 revenue、net income 與 FCF history values，在 malformed value iterator 中途失敗時保留已解析數值，避免 history rows 或 deterministic financial tool context 中斷 prompt JSON generation。
- D424：P3-318 補強 Prompt Agent Context Truthiness Guard，讓 `prompt_builder._agent_context()` 以 truthiness-safe presence checks 保留有效 routed agent context，避免 malformed context truthiness 中斷 prompt JSON generation 或抹掉可用 agent context section。
- D425：P3-319 補強 Prompt Compact PE River Years Tail Guard，讓 `prompt_builder._compact_pe_river()` 以 truthiness- 與 iterator-safe tail conversion 讀取 `pe_river_chart.years`，避免 malformed valuation year list 中斷 compact prompt JSON generation，並保留 iterator failure 前可用的 trailing years。
- D426：P3-320 補強 Prompt Compact PE River Chart Mapping Guard，讓 compact prompt 的 `pe_river_chart` 直接交給 `prompt_builder._compact_pe_river()` 做 dict-safe handoff，避免 malformed chart mapping truthiness 在進入 local valuation context shaping 前中斷 prompt JSON generation。
- D427：P3-321 補強 Prompt Full Market Catalyst Items Iterator Guard，讓 default prompt 的 `market_catalysts.items` 以 truthiness- 與 iterator-safe conversion 讀取 `recent_catalysts`，避免 malformed catalyst list 中斷 prompt JSON generation，並保留 iterator failure 前可用的新聞項目。
- D428：P3-322 補強 Prompt Full Dynamic Peer Metrics Iterator Guard，讓 default prompt 的 `peer_context.dynamic_peer_metrics` 以 truthiness- 與 iterator-safe conversion 讀取 `dynamic_peer_metrics`，避免 malformed peer metrics list 中斷 prompt JSON generation，並保留 iterator failure 前可用的同業列。
- D429：P3-323 補強 Prompt Full Peer Discovery Results Iterator Guard，讓 default prompt 的 `peer_context.search_discovery_results` 以 truthiness- 與 iterator-safe conversion 讀取 `peer_discovery_results`，避免 malformed peer discovery list 中斷 prompt JSON generation，並保留 iterator failure 前可用的 discovered peer rows。
- D430：P3-324 補強 Prompt Full Recent Monthly Revenue Text Iterator Guard，讓 default prompt 的 `recent_monthly_revenue_text` 以 truthiness- 與 iterator-safe conversion 讀取 `recent_monthly_revenue`，避免 malformed monthly revenue list 中斷 prompt JSON generation，並保留 iterator failure 前可用的月營收列。
- D431：P3-325 補強 Prompt Full Data Quality Notes Iterator Guard，讓 default prompt 的 `data_quality_notes` 以 truthiness- 與 iterator-safe conversion 讀取 `data_source_notes`，避免 malformed data source note list 中斷 prompt JSON generation，並保留 iterator failure 前可用的資料品質註記。
- D432：P3-326 補強 Prompt Full PE River Chart Mapping Guard，讓 default prompt 的 `local_valuation_context.pe_river_chart` 以 truthiness-safe handoff 保留有效 valuation chart mapping，避免 malformed chart mapping truthiness 中斷 prompt JSON generation 或抹掉本地估值脈絡。
- D433：P3-327 補強 Prompt Company Identity Mapping Guard，讓 prompt 的 `company.identity` 以 truthiness-safe handoff 讀取 `company_identity`，避免 malformed identity mapping truthiness 中斷 prompt JSON generation 或抹掉 stock identity 與 alias constraints。
- D434：P3-328 補強 Prompt Freshness Mapping Guard，讓 prompt 的 `data_freshness` 與 `source_freshness` 以 truthiness-safe handoff 保留有效 source recency evidence，避免 malformed freshness mapping truthiness 中斷 prompt JSON generation 或抹掉資料時效脈絡。
- D435：P3-329 補強 Prompt Institutional Trading Mapping Guard，讓 prompt 的 `institutional_trading` 以 truthiness-safe handoff 保留有效 chip-flow evidence，避免 malformed institutional trading mapping truthiness 中斷 prompt JSON generation 或抹掉法人籌碼脈絡。
- D436：P3-330 補強 Prompt Data Trust List Fields Guard，讓 prompt 的 `data_trust.critical_failures`、`stale_sources`、`notes` 與 `reason_codes` 以 truthiness- 與 iterator-safe conversion 保留有效 trust evidence，避免 malformed data trust list 中斷 prompt JSON generation 或抹掉資料限制與信心原因。
- D437：P3-331 補強 Agent Runtime Identity Guard Mapping Guard，讓 agent prompt assembly 的 `build_company_identity_guard()` 以 truthiness-safe handoff 保留 hard identity lock，避免 malformed `company_identity` mapping truthiness 中斷 agent prompt construction 或抹掉公司身分約束。
- D438：P3-332 補強 Agent Runtime RAG Context Mapping Guard，讓 agent prompt assembly 的 `rag_context` 以 truthiness-safe handoff 保留目標 agent 的 retrieved context，避免 malformed RAG mapping truthiness 中斷 prompt construction 或抹掉外部檢索脈絡。
- D439：P3-333 補強 Agent Runtime Primary Probe Flag Bool Guard，讓 agent prompt assembly 的 `_primary_probe_prompt` 以 bool-safe conversion 讀取，避免 malformed compact prompt flag truthiness 中斷 prompt construction，並安全回退到 full prompt context。
- D440：P3-334 補強 Agent Runtime Identity Guard Text Field Bool Guard，讓 agent prompt assembly 的 `official_name` 與 `legal_name` 以 string-safe conversion 讀取，避免 malformed identity text truthiness 中斷 hard identity lock construction 或抹掉可字串化公司身分證據。
- D441：P3-335 補強 Agent Runtime Identity Guard Alias List Iterator Guard，讓 agent prompt assembly 的 `english_names` 與 `forbidden_aliases` 以 iterator-safe string conversion 讀取，避免 malformed alias iterator 中斷 hard identity lock construction，並保留 iterator failure 前可用的 alias evidence。
- D442：P3-336 補強 Agent Runtime RAG Context Text Coercion Guard，讓 agent prompt assembly 的目標 agent RAG context 在 compact truncation 前先以 string-safe conversion 固定為文字，避免 malformed retrieved-context length 或 slice behavior 中斷 prompt construction，並保留可字串化的 retrieved context evidence。
- D443：P3-337 補強 Agent Runtime Temporal Memory Reflection Prompt Guard，讓 agent prompt assembly 的 temporal memory `reflection_prompt` 在 section assembly 前先以 string-safe conversion 固定為文字，避免 malformed reflection prompt truthiness 中斷 prompt construction，並保留可字串化的反思證據。
- D444：P3-338 補強 Agent Runtime Temporal Memory Backtests Iterator Guard，讓 agent prompt assembly 的 temporal memory `backtests` 在 JSON rendering 前以 iterator- 與 JSON-safe conversion 讀取，避免 malformed backtest slice 或 iterator failure 中斷 prompt construction，並保留 iterator failure 前可用的回測證據。
- D445：P3-339 補強 Agent Runtime Prompt Safety Helper Split，將 agent prompt assembly 的 string、bool、iterator 與 JSON coercion guards 拆到 `agent_runtime.prompt_safety`，避免 `prompting.py` 在持續 hardening 時逼近 backend module size limit，並讓後續報告品質 guard 可重用同一套安全轉換語意。
- D446：P3-340 補強 Agent Runtime State View JSON Guard，讓 agent prompt assembly 的 AgentState view 在 JSON rendering 前以 recursive JSON-safe conversion 讀取，避免 non-serializable state leaf 或 `allow_nan=False` 不接受的值中斷 prompt construction，並保留可字串化的 state evidence。
- D447：P3-341 補強 Agent Runtime Forensic Warning Text Guard，讓 agent prompt assembly 的 `_v2_forensic_warning` 在警示 section assembly 前以 string-safe conversion 讀取，避免 malformed V2 forensic-warning truthiness 中斷 prompt construction，並保留可字串化的財務排雷警示證據。
- D448：P3-342 補強 Agent Runtime Retry And Audit Instruction Text Guard，讓 agent prompt assembly 的 `_identity_retry_instruction`、`_audit_reflection_instruction` 與 `_audit_retry_instruction` 在 prompt part filtering 前以 string-safe conversion 讀取，避免 malformed retry/audit instruction truthiness 中斷 prompt construction，並保留可字串化的 runtime guidance。
- D449：P3-343 補強 Agent Runtime Final Audit Pipeline ID Text Guard，讓 final audit preflight rule selection 的 `pipeline_id` 在模式規則選取前以 string-safe conversion 正規化，避免 malformed pipeline-id truthiness 中斷 prompt construction，並保留可字串化的 mode-specific audit rules。
- D450：P3-344 補強 Agent Runtime Identity Guard Mapping Length Guard，讓 hard identity lock 的 `company_identity` 空值判斷容忍 malformed mapping length access，避免 `len(identity)` failure 中斷 prompt construction，並保留可讀取的公司身分證據。
- D451：P3-345 補強 Agent Runtime Identity Guard Mapping Accessor Guard，讓 hard identity lock 讀取 `company_identity` 欄位時改用 dict-native field reads，避免 malformed mapping accessor methods 中斷 prompt construction 或抹掉有效公司身分證據。
- D452：P3-346 補強 Agent Runtime Prompt JSON Dict Items Guard，讓 prompt JSON-safe conversion 的 dict item traversal 改用 dict-native field reads，避免 malformed mapping item accessor 抹掉有效 state view / prompt evidence。
- D453：P3-347 補強 Agent Runtime Prompt JSON Sequence Items Guard，讓 prompt JSON-safe conversion 的 list/tuple traversal 改用 native iterators，避免 malformed sequence iterator accessor 抹掉有效 state view / prompt evidence。
- D454：P3-348 補強 Agent Runtime Prompt JSON Collection Items Guard，讓 prompt JSON-safe conversion 的 set/frozenset traversal 改用 native iterators，避免 malformed collection iterator accessor 把有效 state view / prompt evidence 退化成 repr string。
- D455：P3-349 補強 Agent Runtime Identity Guard Alias Native List Limit Guard，讓 hard identity lock 的 English aliases 透過 native sequence iterator 讀取 malformed list subclass，避免 iterator accessor failure 使 bounded alias list 退化成 repr string 並洩漏超過上限的 alias。
- D456：P3-350 補強 Agent Runtime Identity Guard Ticker Text Guard，讓 hard identity lock 的 ticker 與 stock_id 先做 string-safe conversion，避免 malformed ticker/stock-id string conversion 中斷 prompt construction，並回退到可用 identity ticker。
- D457：P3-351 補強 Agent Runtime Final Audit Rule List Text Guard，讓 final audit preflight rule lists 逐條做 string-safe conversion，避免單一 malformed rule text 中斷 prompt construction，並保留其他有效 final-audit 規則。
- D458：P3-352 補強 Agent Runtime Prompt Rule Block Text Guard，讓 runtime prompt rule blocks 的 title、intro、schema_lines 與 rules 逐項做 string-safe conversion，避免 malformed rule block text/truthiness 中斷 prompt construction，並保留有效 runtime guidance。
- D459：P3-353 補強 Agent Runtime Output Cleanliness Rule Text Guard，讓正式報告輸出契約 rule list 共用 string-safe block assembly，避免 malformed formal-output rule text 中斷 prompt construction，並保留有效輸出格式約束。
- D460：P3-354 補強 Agent Runtime Assistant Task Prompt Text Guard，讓背景任務 prompt helper 的 system_instruction 與 instruction_lines 共用 string-safe conversion，避免 malformed task prompt text/truthiness 中斷 tear sheet、context digest 或 repair reflection prompt construction。
- D461：P3-355 補強 Agent Runtime Identity Guard Template Text Guard，讓 hard identity lock 的 runtime rule templates 先做 string-safe formatting，避免 malformed identity rule template 中斷 prompt construction，並保留有效公司身分約束。
- D462：P3-356 補強 Agent Runtime Structured Instructions Mapping Guard，讓 structured-agent runtime rule mapping 以 dict-native traversal 讀取，避免 malformed mapping truthiness 或 item accessor 中斷 structured output constraints assembly。
- D463：P3-357 補強 Agent Runtime Rule Section Mapping Guard，讓 `build_agent_rule_block()` 以 dict-native lookup 讀取 agent-specific runtime rule section，避免 malformed section mapping truthiness 或 get accessor 中斷 agent guidance assembly。
- D464：P3-358 補強 Agent Runtime Rule Block Config Mapping Guard，讓 `_build_titled_rule_block()` 以 dict-native field reads 讀取 rule block config，避免 malformed config truthiness 或 get accessor 中斷 title、intro、schema 與 rules assembly。
- D465：P3-359 補強 Agent Runtime Rule List Mapping Guard，讓 `_coerce_rule_list()` 以 dict-native field reads 讀取 nested rule-list mapping，避免 malformed rule-list get accessor 中斷 runtime rule guidance assembly。
- D466：P3-360 補強 Agent Runtime Final Audit Mapping Guard，讓 `build_final_audit_preflight_rule()` 以 dict-native field reads 讀取 final-audit config、per-agent 與 per-pipeline mappings，避免 malformed mapping accessors 抹掉有效 audit guidance。
- D467：P3-361 補強 Agent Runtime Output Cleanliness Mapping Guard，讓 `build_output_cleanliness_rule()` 以 dict-native field reads 讀取 formal-output config，避免 malformed config get accessor 抹掉正式報告輸出契約。
- D468：P3-362 補強 Agent Runtime Assistant Task Prompt Mapping Guard，讓背景任務 prompt helper 以 dict-native field reads 讀取 task prompt group、task config、system_instruction 與 instruction_lines，避免 malformed mapping accessors 抹掉 tear sheet、context digest 或 repair reflection guidance。
- D469：P3-363 補強 Agent Runtime Top-Level Rule Section Mapping Guard，新增 `_runtime_rule_section()` 以 dict-native field reads 讀取 runtime rules 的 top-level sections，避免 malformed runtime rules mapping accessors 抹掉 output cleanliness、structured instructions、final audit、agent rule block、assistant task prompt 或 identity guard configs。
- D470：P3-364 補強 Agent Runtime Identity Guard Runtime Rule Mapping Guard，讓 hard identity lock 的 runtime identity guard config 以 dict-native field reads 讀取 title、rules 與 identity templates，避免 malformed config accessors 抹掉公司身分一致性約束。
- D471：P3-365 補強 Agent Runtime Identity Guard Values Mapping Guard，讓 hard identity lock 的 identity values 以 dict-native field reads 讀取 legal name、English names 與 forbidden aliases，避免 malformed value accessors 抹掉公司身分補充約束。
- D472：P3-366 補強 Agent Runtime Identity Guard Source Data Mapping Guard，讓 hard identity lock 的 source data 以 dict-native field reads 讀取 company identity、ticker 與 company name，避免 malformed source data accessors 在 prompt assembly 前中斷公司身分鎖。
- D473：P3-367 補強 Prompt Company Identity Field Mapping Guard，讓 prompt JSON 的 company identity 欄位以 dict-native field reads 讀取 stock id、official/legal name、aliases、industry categories 與 peers，避免 malformed identity field accessors 抹掉公司身分證據。
- D474：P3-368 補強 Prompt Company Identity Source Data Mapping Guard，讓 prompt JSON 的 source data 以 dict-native field reads 讀取 company identity、ticker 與 company name，避免 malformed source data accessors 在 prompt output 前中斷公司身分證據輸出。
- D475：P3-369 補強 Terminal Checkpoint Maintenance Implementation Guard，讓 `cleanup_terminal_checkpoints()` 以完整 terminal/active job sets 分類 LangGraph checkpoint threads，保留 missing path/schema 與 sanitized SQLite error 回報，並用批次刪除終態 checkpoints/writes 解除全套測試的 checkpoint maintenance 收集缺口。
- D476：P3-370 補強 Prompt Data Trust Source Data Mapping Guard，讓 prompt JSON 的 data trust source data 以 dict-native field reads 讀取 `data_trust`，避免 malformed source data accessors 在 prompt output 前中斷資料可信度證據輸出。
- D477：P3-371 補強 Prompt Data Trust Field Mapping Guard，讓 prompt JSON 的 data trust 欄位以 dict-native field reads 讀取 status、failures、stale sources、market data timestamp、notes 與 reason codes，避免 malformed data trust field accessors 抹掉資料可信度證據。
- D478：P3-372 補強 Prompt History Source Data Mapping Guard，讓 `prompt_builder._prompt_history_rows()` 以 dict-native field reads 讀取 years、history value sequences 與 history year limit，避免 malformed source data accessors 在 prompt output 前中斷財務歷史列輸出。
- D479：P3-373 補強 Prompt Agent Context Source Data Mapping Guard，讓 `prompt_builder._agent_context()` 以 dict-native field reads 讀取 routed agent context source data，避免 malformed source data accessors 在 prompt output 前中斷總經、籌碼、替代資料、情緒、申報、開放資料或法說會脈絡輸出。
- D480：P3-374 補強 Prompt Compact PE River Chart Field Mapping Guard，讓 `_compact_pe_river()` 以 dict-native field reads 讀取 source、years、multiples 與 bands，避免 malformed PE river chart field accessors 在 compact prompt output 前中斷本益比河流圖估值脈絡輸出。
- D481：P3-375 補強 Prompt Freshness Source Data Mapping Guard，讓 prompt JSON 的 `data_freshness` 與 `source_freshness` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 prompt output 前中斷資料時效與來源時效證據輸出。
- D482：P3-376 補強 Prompt Institutional Trading Source Data Mapping Guard，讓 prompt JSON 的 `institutional_trading` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 prompt output 前中斷法人籌碼證據輸出。
- D483：P3-377 補強 Prompt Market Catalyst Source Data Mapping Guard，讓 prompt JSON 的 `recent_catalysts` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷近期催化事件與新聞證據輸出。
- D484：P3-378 補強 Prompt Peer Context Source Data Mapping Guard，讓 prompt JSON 的 `dynamic_peer_metrics` 與 `peer_discovery_results` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷同業比較與同業探索證據輸出。
- D485：P3-379 補強 Prompt Supplemental Source Data Mapping Guard，讓 prompt JSON 的 `data_source_notes` 與 `recent_monthly_revenue` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷資料品質註記與月營收脈絡證據輸出。
- D486：P3-380 補強 Prompt PE River Chart Source Data Mapping Guard，讓 prompt JSON 的 `pe_river_chart` source data 以 dict-native field reads 讀取並共用單次 safe lookup，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷本益比河流圖估值證據輸出。
- D487：P3-381 補強 Prompt Cross-check Source Data Mapping Guard，讓 prompt JSON 的 `dupont_identity_note`、`equity_multiplier_note` 與 `wacc_capital_structure_note` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷 DuPont fallback 與 WACC 資本結構註記輸出。
- D488：P3-382 補強 Prompt Market Data Source Data Mapping Guard，讓 prompt JSON 的 `current_price`、`market_cap_raw`、`week_52_high` 與 `week_52_low` source data 以 dict-native field reads 讀取，並同步保護 deterministic financial tool context 的 `market_cap_raw` 入口，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷價格、市值與 52 週區間證據輸出。
- D489：P3-383 補強 Prompt Valuation Metrics Source Data Mapping Guard，讓 prompt JSON 的估值倍數、股本、EPS、殖利率、每股股利與 payout ratio source data 以 dict-native field reads 讀取，並同步保護 deterministic financial tool context 的 `shares_raw`、`dividend_rate_raw` 與 `dividend_yield_raw` 入口，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷估值與 DDM 證據輸出。
- D490：P3-384 補強 Prompt TTM Financials Source Data Mapping Guard，讓 prompt JSON 的 trailing revenue、net income、EBITDA、margin 與 net income source data 以 dict-native field reads 讀取，並同步保護 forward EPS implied revenue cross-check 的 `profit_margin_raw` 與 `revenue_ttm_raw` 入口，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷 TTM 基本面與 implied revenue 證據輸出。
- D491：P3-385 補強 Prompt Cash Flow Source Data Mapping Guard，讓 prompt JSON 的 `free_cash_flow_raw` 與 `operating_cash_flow_raw` source data 以 dict-native field reads 讀取，並同步保護 deterministic financial tool context 的 `free_cash_flow_raw` DCF base FCF 入口，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷現金流與 DCF 證據輸出。
- D492：P3-386 補強 Prompt Balance Sheet Source Data Mapping Guard，讓 prompt JSON 的 `total_debt_raw`、`total_cash_raw`、`debt_to_equity`、`current_ratio` 與 `equity_multiplier` source data 以 dict-native field reads 讀取，並同步保護 deterministic financial tool context 的 `total_debt_raw` 與 `total_cash_raw` WACC/DCF net debt 入口，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷槓桿、流動性、淨負債、WACC 與 DCF 證據輸出。
- D493：P3-387 補強 Prompt Growth Source Data Mapping Guard，讓 prompt JSON 的 annual revenue growth、annual net income growth、TTM revenue change、Yahoo revenue/earnings growth 與 5-year revenue CAGR source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷成長證據輸出。
- D494：P3-388 補強 Prompt Company Metadata Source Data Mapping Guard，讓 prompt JSON 的 schema version、sector、industry、country、employees 與 fetch date source data 以 dict-native field reads 讀取，並同步保護 deterministic financial tool context 的 sector/industry 入口，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷公司 metadata 與金融業估值 cross-check context。
- D495：P3-389 補強 Prompt Financial History Source Data Mapping Guard，讓 deterministic financial tool context 的 `revenue_history`、`net_income_history` 與 `fcf_history` source data 以 dict-native field reads 讀取，避免 malformed source data accessors 在 full 或 compact prompt output 前中斷 history rows、revenue CAGR、latest annual revenue growth 與 FCF conversion 證據輸出。
- D496：P3-390 補強 Prompt Source Audit Root Source Data Mapping Guard，讓 prompt source audit summary 的 root `source_audit` collection 以 dict-native field reads 讀取，避免 malformed source data accessors 在 prompt JSON generation 前中斷來源摘要 provider、status、record count、merged count、mismatch、cache/stale 與 message 證據輸出。
- D497：P3-391 補強 Prompt Source Audit Entry Field Mapping Guard，讓 prompt source audit summary 的 entry `source`、`provider`、`status`、`record_count`、`cache_hit`、`stale`、`message` 與 `error_kind` 欄位以 dict-native field reads 讀取，避免 malformed entry accessors 在 prompt JSON generation 前中斷來源摘要 provider、status、record count、merged count、mismatch、cache/stale 與 message 證據輸出。
- D498：P3-392 補強 Report Conformance Quality Gate Mapping Guard，讓 `evaluate_report_conformance()` 在 decision-tree evaluation 前以 dict-native field reads 讀取 report lint、final audit、evidence exit gate 與 content credibility inputs，避免 malformed gate accessors 中斷報告品質分類或抹掉有效 blocking/warning evidence。
- D499：P3-393 補強 Report Renderer Lint Repair Mapping Guard，讓 `ReportRenderer` 的 lint repair gate 在 structured-key scrubbing 前以 dict-native field reads 讀取 `ReportLintError.result.blocking_issues` 與 issue `label`，避免 malformed lint result/issue accessors 中斷可自動修復的 structured JSON key leak repair flow。
- D500：P3-394 補強 Report Execution Summary Quality Mapping Guard，讓 `build_execution_summary_markdown()` / `build_execution_summary_html()` 在 report rendering 前以 dict-native field reads 讀取 final audit、evidence gate、report conformance 與 report lint fields，避免 malformed quality gate accessors 中斷 HTML/Markdown execution summary 或抹掉有效品質狀態證據。
- D501：P3-395 補強 Report Quality Repair Queue Mapping Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 dict-native field reads 讀取 report、content credibility、report conformance、evidence gate、data trust 與 decision freshness fields，避免 malformed quality gate accessors 中斷人工審核排序或抹掉有效 repair reasons。
- D502：P3-396 補強 Outcome Calibration Quality Signal Mapping Guard，讓 `build_outcome_calibration()` 在 miss attribution 前以 dict-native field reads 讀取 backtest、report、data trust、content credibility、report conformance 與 decision freshness fields，避免 malformed quality signal accessors 中斷 outcome learning 或把低品質 miss 誤歸因為 thesis failure。
- D503：P3-397 補強 Provider Impact Report Mapping Guard，讓 `build_provider_impact()` 在 provider recovery decision 前以 dict-native field reads 讀取 report、data trust、reason codes 與 provider SLA alert fields，避免 malformed provider impact accessors 中斷核心來源影響分類或抹掉 wait-provider-recovery blocking evidence。
- D504：P3-398 補強 Daily Decision Queue Action Mapping Guard，讓 `build_daily_decision_queue()` 在 priority ordering 前以 dict-native field reads 讀取 repair、provider impact、notification delivery、backtest、rerun、model route、watchlist 與 screener action fields，避免 malformed queue action accessors 中斷每日操作順序或抹掉有效 queue context。
- D505：P3-399 補強 Notification Plan Action Mapping Guard，讓 `build_daily_notification_plan()` 在 message/outbox handoff 前以 dict-native field reads 讀取 decision queue 與 legacy action fields，避免 malformed notification action accessors 中斷通知計畫或抹掉 source、report artifact、CTA、queue rank 與 delivery identity context。
- D506：P3-400 補強 Notification Delivery Audit Context Mapping Guard，讓 `record_delivery_attempt()`、`reconcile_outbox_with_audit()` 與 attention context summary 在 persistence/reconciliation 前以 dict-native field reads 讀取 outbox 與 audit-record fields，避免 malformed audit context accessors 中斷 sender audit writes 或抹掉 source、report artifact、CTA、queue rank、retry 與 attention context snapshot。
- D507：P3-401 補強 Notification Delivery Observability Mapping Guard，讓 `notification_delivery_observability` 在 attention、dashboard summary 與 Prometheus rendering 前以 dict-native field reads 讀取 delivery summary fields，避免 malformed summary accessors 中斷 notification health visibility 或抹掉 failed、retry-exhausted、channel 與 reason evidence。
- D508：P3-402 補強 Provider SLA Dashboard Alert Payload Mapping Guard，讓 `provider_sla_observability.dashboard_provider_alert_payload()` 與同 module alert/window helpers 在 impact/status projection 前以 dict-native field reads 讀取 provider alert fields，避免 malformed provider alert accessors 中斷 core/enrichment classification 或抹掉 provider、level、message、window 與 success-rate evidence。
- D509：P3-403 補強 Provider SLA Numeric Field Shape Mapping Guard，讓 `provider_sla_payload_shape.normalize_provider_sla_numeric_fields()` 在 provider/window numeric shaping 前先以 dict-safe conversion 正規化 direct helper row inputs，避免 malformed provider row mappings 中斷 attempts、counts、success-rate、duration 與 total-record shaping。
- D510：P3-404 補強 Data Trust Provider SLA Row Mapping Guard，讓 `data_trust_sla_policy` 在 current source audit 與 provider alert matching 前先以 dict-safe conversion 正規化 row inputs，避免 malformed row `.get()` accessors 中斷 data-trust downgrade 或抹掉 provider SLA evidence。
- D511：P3-405 補強 Data Trust Provider SLA Source Data Mapping Guard，讓 `data_trust_sla_policy.current_provider_entries()` 在讀取 current source audit rows 前先以 dict-safe conversion 正規化根 source data payload，避免 malformed root `.get()` accessors 中斷 data-trust downgrade 或抹掉 provider SLA evidence。
- D512：P3-406 補強 Data Trust Provider SLA Nested Window Mapping Guard，讓 `data_trust_sla_policy._evidence_attempts()` 在讀取 nested `windows[alert_basis]` 前先以 dict-safe conversion 正規化 window maps，避免 malformed nested window `.get()` accessors 中斷 data-trust downgrade 或抑制 alert-level attempts fallback。
- D513：P3-407 補強 Provider Impact Current Fetch Truthiness Guard，讓 `provider_impact._current_fetch_healthy()` 在 provider recovery decision 前以 bool-, integer- 與 string-safe conversion 讀取 current fetch fields，避免 malformed truthiness 中斷核心來源影響分類或抹掉 wait-provider-recovery blocking evidence。
- D514：P3-408 補強 Provider Impact Alert Text Truthiness Guard，讓 `provider_impact._impact_for_alert()` 在 provider recovery decision 前以 string-safe conversion 讀取 provider alert source、provider 與 alert level，避免 malformed text truthiness 中斷核心來源影響分類或抹掉 wait-provider-recovery blocking evidence。
- D515：P3-409 補強 Provider Impact Reason Code String Guard，讓 `provider_impact._reason_codes()` 在 provider recovery decision 前以 string-safe conversion 讀取 reason code list，避免 malformed reason-code text 中斷核心來源影響分類或抹掉 wait-provider-recovery blocking evidence。
- D516：P3-410 補強 Provider Impact Reason Code Iterator Guard，讓 `provider_impact._safe_text_list()` 在 reason code iterator failure 時保留已解析的有效 entries，避免 malformed reason-code iteration 中斷核心來源影響分類或抹掉已解析的 wait-provider-recovery blocking evidence。
- D517：P3-411 補強 Provider Impact Alert Iterator Guard，讓 `provider_impact._alerts()` 透過 iterator-safe dict-list conversion 讀取 provider SLA alerts，避免 malformed provider alert iteration 中斷核心來源影響分類或抹掉已解析的 wait-provider-recovery blocking evidence。
- D518：P3-412 補強 Provider Impact Ledger Report Iterator Guard，讓 `build_provider_impact_ledger()` 先以 iterator-safe dict-list conversion 正規化 report collection，避免 malformed report iteration 中斷 ledger 建立或抹掉已解析的 provider recovery impact rows 與 sampled report counts。
- D519：P3-413 補強 Provider Impact Ledger Sort Key Guard，讓 `build_provider_impact_ledger()` 透過 string-safe `_ledger_sort_key()` 排序 impact items，避免 malformed ticker sort-key truthiness 中斷 provider recovery impact ledger output。
- D520：P3-414 補強 Provider Impact Report Identity Truthiness Guard，讓 `build_provider_impact()` 在 provider recovery output 前以 string-safe conversion 讀取 filename/report_filename 與 pipeline_id，避免 malformed report identity truthiness 中斷核心來源影響分類或抹掉 wait-provider-recovery blocking evidence。
- D521：P3-415 補強 Provider Impact Ticker JSON Safety Guard，讓 `build_provider_impact()` 在 provider recovery output 前以 string-safe conversion 輸出 ticker identity，避免 malformed ticker payload object 中斷 JSON serialization 或抹掉 wait-provider-recovery blocking evidence。
- D522：P3-416 補強 Report Quality Repair Queue Report Identity Truthiness Guard，讓 `build_report_quality_repair_queue()` 在 provider-impact handoff 與 action prioritization 前以 string-safe conversion 讀取 ticker、filename/report_filename 與 pipeline_id，避免 malformed report identity truthiness 中斷人工審核排序或抹掉有效 repair reasons。
- D523：P3-417 補強 Report Quality Repair Queue Quality Gate Text Truthiness Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 string-safe conversion 讀取 gate status、summary 與 message，避免 malformed gate text truthiness 中斷人工審核排序或抹掉有效 repair reasons。
- D524：P3-418 補強 Report Quality Repair Queue Reason Code String Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 shared `mapping_fields.safe_text_list()` 讀取 reason codes，避免 malformed reason-code text 中斷人工審核排序或抹掉有效 repair reasons。
- D525：P3-419 補強 Report Quality Repair Queue Stale Source String Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 shared `mapping_fields.safe_text_list()` 讀取 stale sources，避免 malformed stale-source text 中斷 refresh-data 排序或抹掉有效 stale source evidence。
- D526：P3-420 補強 Report Quality Repair Queue Provider Alert Iterator Guard，讓 `build_report_quality_repair_queue()` 在 provider-impact handoff 前以 shared `mapping_fields.safe_dict_list()` 讀取 provider SLA alerts，避免 malformed provider alert iteration 中斷 wait-provider-recovery repair evidence。
- D527：P3-421 補強 Report Quality Repair Queue Decision Freshness Detail Truthiness Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 string-safe fallback 讀取 rerun reason/message，避免 malformed rerun reason truthiness 中斷完整重跑排序或抹掉 freshness repair context。
- D528：P3-422 補強 Report Quality Repair Queue Report Iterator Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 shared `mapping_fields.safe_dict_list()` 正規化 report collections，避免 malformed report iteration 中斷 queue 建立或抹掉已解析的有效 repair reasons。
- D529：P3-423 補強 Report Quality Repair Queue Decision Freshness Flag Truthiness Guard，讓 `build_report_quality_repair_queue()` 在 action prioritization 前以 bool-safe conversion 讀取 decision freshness rerun flags，避免 malformed rerun flag truthiness 中斷完整重跑排序或抹掉 freshness repair context。
- D530：P3-424 補強 Report Quality Repair Queue Limit Truthiness Guard，讓 `build_report_quality_repair_queue()` 在 prioritized actions slicing 前以 integer-safe conversion 讀取 limit，避免 malformed limit truthiness 中斷 action prioritization 或抹掉有效 repair reasons。
- D531：P3-425 補強 Outcome Calibration Report Identity Truthiness Guard，讓 `build_outcome_calibration()` 在 report matching 與 miss attribution 前以 string-safe conversion 讀取 report filename、ticker、pipeline、horizon 與 reason identity fields，避免 malformed identity truthiness 中斷 quality-signal learning 或讓 miss 脫離有效 report-time evidence。
- D532：P3-426 補強 Outcome Calibration Data Trust Score Truthiness Guard，讓 `build_outcome_calibration()` 在 miss attribution 前以 float-safe fallback 讀取 data trust score / data confidence score，避免 malformed score truthiness 中斷 quality-signal learning 或把有效 zero score 誤換成 fallback confidence。
- D533：P3-427 補強 Outcome Calibration Row Collection Truthiness Guard，讓 `build_outcome_calibration()` 在 report matching 與 miss attribution 前以 shared `mapping_fields.safe_dict_list()` 正規化 backtest/report row collections，避免 malformed collection truthiness 中斷 quality-signal learning 或抹掉有效 rows。
- D534：P3-428 補強 Outcome Calibration Decision Freshness Flag Truthiness Guard，讓 `build_outcome_calibration()` 在 miss attribution 前以 bool-safe conversion 讀取 decision freshness rerun flag，避免 malformed flag truthiness 中斷 quality-signal learning 或誤分類 stale report-time evidence。
- D535：P3-429 補強 Outcome Calibration Matched Report Truthiness Guard，讓 `build_outcome_calibration()` 在 miss attribution 前以 dict-safe fallback 傳遞 matched report，避免 malformed matched report truthiness 中斷 quality-signal learning 或讓 miss 脫離有效 report-time evidence。
- D536：P3-430 補強 Outcome Calibration Numeric Conversion Guard，讓 `build_outcome_calibration()` 在 miss attribution 前以 conversion-safe fallback 讀取 ROI、market return 與 data trust score，避免 malformed numeric conversion 中斷 quality-signal learning 或抹掉有效 stale report-time evidence。
- D537：P3-431 補強 Strategy Evaluator Numeric Conversion Guard，讓 `evaluate_strategy_artifacts()` 在 alpha model comparison 前以 conversion-safe fallback 讀取 ROI、excess return 與 drawdown，避免 malformed numeric conversion 中斷 strategy evaluation 或抹掉有效 hit-rate evidence。
- D538：P3-432 補強 Strategy Evaluator Artifact Mapping Guard，讓 `evaluate_strategy_artifacts()` 在 alpha model comparison 前以 dict-native field reads 讀取 artifact、metrics 與 quality funnel 欄位，避免 malformed accessors 中斷 strategy evaluation 或抹掉有效 model、trigger、quality 與 hit-rate evidence。
- D539：P3-433 補強 Strategy Evaluator Hit Flag Truthiness Guard，讓 `evaluate_strategy_artifacts()` 在 alpha model comparison 前以 bool-safe fallback 讀取 `metrics.hit`，避免 malformed hit flag truthiness 中斷 strategy evaluation 或抹掉有效 outcome-based hit-rate evidence。
- D540：P3-434 補強 Strategy Evaluator Artifact Iterator Guard，讓 `evaluate_strategy_artifacts()` 在 alpha model comparison 前以 iterator-safe dict-list conversion 正規化 artifact collections，避免 malformed artifact iteration 中斷 strategy evaluation 或抹掉已解析的 model、trigger、quality 與 hit-rate evidence。
- D541：P3-435 補強 Strategy Evaluator Artifact Tuple Sequence Guard，讓 shared `mapping_fields.safe_dict_list()` 支援 tuple artifact batches，使 `evaluate_strategy_artifacts()` 在 alpha model comparison 前保留 immutable artifact sequence 的 backtest evidence，避免 tuple 批次被誤判為空資料。
- D542：P3-436 補強 Report Quality Repair Queue Text Tuple Sequence Guard，讓 shared `mapping_fields.safe_text_list()` 支援 tuple text batches，使 `build_report_quality_repair_queue()` 在 action prioritization 前保留 immutable reason-code 與 stale-source repair evidence，避免 tuple 批次被誤判為空資料。
- D543：P3-437 補強 Provider Impact Tuple Sequence Guard，讓 `provider_impact` 本地 safe list conversion 支援 tuple reason-code、provider alert 與 ledger report batches，避免 immutable provider impact evidence 被誤判為空資料而失去 wait-provider-recovery blocking decision。
- D544：P3-438 補強 Shared Mapping Native Iterator Fallback Guard，讓 `mapping_fields.safe_text_list()` 與 `safe_dict_list()` 在 list/tuple iterator accessor 建立失敗時 fallback 到 native sequence iterator，避免底層有效 reason-code、stale-source 或 artifact evidence 被 malformed iterator accessor 整批抹掉。
- D545：P3-439 補強 Provider Impact Native Iterator Fallback Guard，讓 `provider_impact` 本地 safe list conversion 在 list/tuple iterator accessor 建立失敗時 fallback 到 native sequence iterator，避免底層有效 reason-code、provider alert 或 ledger report evidence 被 malformed iterator accessor 整批抹掉而失去 wait-provider-recovery blocking decision。
- D546：P3-440 補強 Data Trust Provider SLA Native Iterator Fallback Guard，讓 `data_trust_sla_policy` 本地 safe list conversion 在 list/tuple iterator accessor 建立失敗時 fallback 到 native sequence iterator，避免 source-audit rows、provider SLA alerts、既有 reason codes 或 notes 被 malformed iterator accessor 整批抹掉而錯失 trust downgrade 或既有人工脈絡。
- D547：P3-441 補強 Data Trust Explicit Target Price Detector Native List Fallback Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed/structured output list subclass iterator accessor 建立失敗時 fallback 到 native list iterator，避免底層有效 target-price guardrail evidence 被整批抹掉。
- D548：P3-442 補強 Data Trust Explicit Target Price Detector Native Mapping Fallback Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed/structured output dict subclass `.items()` accessor 建立失敗時 fallback 到 native dict items，避免底層有效 target-price guardrail evidence 被整批抹掉。
- D549：P3-443 補強 Data Trust Snapshot Sanitizer Native Sequence Fallback Guard，讓 `data_trust_snapshot.sanitize_for_snapshot()` 在 snapshot list/tuple subclass iterator accessor 建立失敗時 fallback 到 native sequence iterator，避免底層有效 snapshot list/tuple evidence 被整批抹掉或中斷 snapshot generation。
- D550：P3-444 補強 Data Trust Snapshot Sanitizer Native Mapping Fallback Guard，讓 `data_trust_snapshot.sanitize_for_snapshot()` 在 snapshot dict subclass `.items()` accessor 建立失敗時 fallback 到 native dict items，避免底層有效 snapshot mapping evidence 被整批抹掉或中斷 snapshot generation。
- D551：P3-445 補強 Data Trust Snapshot Sanitizer Mapping Items Iterable Fallback Guard，讓 shared `mapping_fields.safe_mapping_items()` 在 snapshot dict subclass `.items()` 回傳的 custom items iterable 無法建立 iterator 時 fallback 到 native dict items，避免底層有效 snapshot mapping evidence 被空集合取代。
- D552：P3-446 補強 Data Trust Snapshot Sanitizer Sequence First-Next Fallback Guard，讓 shared `mapping_fields.safe_sequence_items()` 在 snapshot list/tuple subclass custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免底層有效 snapshot list/tuple evidence 被空陣列取代。
- D553：P3-447 補強 Shared Mapping Text List First-Next Fallback Guard，讓 shared `mapping_fields.safe_text_list()` 在 report repair reason-code/stale-source list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免有效修復原因或 stale-source evidence 被空集合取代。
- D554：P3-448 補強 Shared Mapping Dict List First-Next Fallback Guard，讓 shared `mapping_fields.safe_dict_list()` 在 report repair provider-alert list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免 provider SLA impact evidence 被空集合取代並錯排 rerun action。
- D555：P3-449 補強 Provider Impact Dict List First-Next Fallback Guard，讓 `provider_impact` 本地 `_safe_dict_list()` 在 provider alert list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免 provider recovery impact evidence 被空集合取代。
- D556：P3-450 補強 Provider Impact Text List First-Next Fallback Guard，讓 `provider_impact` 本地 `_safe_text_list()` 在 reason-code list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免 `provider_sla_critical` blocking evidence 被空集合取代。
- D557：P3-451 補強 Data Trust Provider SLA Dict Rows First-Next Fallback Guard，讓 `data_trust_sla_policy` 本地 `_safe_dict_rows()` 在 source-audit/provider-alert list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免 provider SLA trust downgrade evidence 被空集合取代。
- D558：P3-452 補強 Data Trust Provider SLA Text List First-Next Fallback Guard，讓 `data_trust_sla_policy` 本地 `_safe_text_list()` 在 trust metadata reason-code/note list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native sequence iterator，避免既有 report trust context 被空集合取代。
- D559：P3-453 補強 Data Trust Explicit Target Price Detector List First-Next Fallback Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed/structured output list custom iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native list iterator，避免底層有效 target-price guardrail evidence 被空集合取代。
- D560：P3-454 補強 Data Trust Explicit Target Price Detector Mapping First-Next Fallback Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed/structured output mapping `.items()` iterable 建立成功但第一個 `next()` 失敗時 fallback 到 native dict items，避免底層有效 target-price guardrail evidence 被空集合取代。
- D561：P3-455 補強 Data Trust Explicit Target Price Detector Mapping Items Iterable Fallback Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 在 parsed/structured output mapping `.items()` 回傳的 custom items iterable 無法建立 iterator 時 fallback 到 native dict items，避免底層有效 target-price guardrail evidence 被空集合取代。
- D562：P3-456 補強 Data Trust Explicit Target Price Detector Root Mapping Guard，讓 `report_reproducibility.detect_explicit_target_price_fields()` 以 dict-native field reads 讀取 `parsed` 與 `structured_outputs`，避免 malformed root context accessor 中斷 target-price guardrail generation 或抹掉底層有效 evidence。
- D563：P3-457 補強 Data Trust Reproducibility Packet Mapping Accessor Guard，讓 `report_reproducibility.build_reproducibility_packet()` 與 provenance helpers 以 dict-native field reads 讀取 context、data、source audit entry 與 metadata，避免 malformed mapping accessor 中斷 reproducibility packet generation 或抹掉 identity、model、provider 與 source-time traceability evidence。
- D564：P3-458 補強 Data Trust Normalization Mapping Accessor Guard，讓 `data_trust_scoring.normalize_data_trust()` 以 dict-native field reads 讀取既有 trust mapping，避免 malformed accessor 中斷 status、score、freshness、reason、note 與 provider SLA metadata normalization 或把有效 trust evidence 降為缺失資料。
- D565：P3-459 補強 Data Trust Snapshot Build Mapping Accessor Guard，讓 `data_trust_snapshot.build_data_snapshot()` 與 `sanitize_rerun_context()` 以 dict-native field reads 讀取 context/data mapping，避免 malformed accessor 中斷 snapshot generation 或抹掉 identity、freshness、quality、refresh 與 rerun metadata。
- D566：P3-460 補強 Data Trust Snapshot Validator Mapping Accessor Guard，讓 `verify_data_snapshot_integrity()` 與 `validate_data_snapshot()` 以 dict-native field reads 讀取 snapshot hash、schema、source audit 與 trust 欄位，避免 malformed accessor 中斷 integrity/schema validation 或誤報有效 snapshot 損壞；scoped regression 已通過，但全域 suite 尚待 concurrent queue size 與 commercial mobile viewport gates 收斂。
- D567：P3-461 補強 Data Trust Snapshot Content Hash Mapping Iterator Guard，讓 `snapshot_content_hash()` 透過 shared iterator-safe mapping traversal 讀取 snapshot items，避免 malformed `.items()` accessor 中斷 integrity generation/verification 或讓有效 snapshot 被誤報損壞；scoped regression 已通過，全域 suite 仍待 concurrent queue size 與 commercial mobile viewport gates 收斂。
- D568：P3-462 補強 Data Trust Shared Mapping First-Next Fallback Guard，讓 `mapping_fields.safe_mapping_items()` 在 custom items iterator 建立成功但第一個 `next()` 失敗時 fallback 到 native dict items，避免底層有效 snapshot、repair 或 provider evidence 被空集合取代；scoped regression 已通過，完整 suite 為 `1 failed, 1689 passed, 5 skipped`，唯一 pending gate 是 concurrent `daily_decision_queue.py` size guard。
- D569：P3-463 補強 Daily Decision Route Warning Policy Boundary，將 `slow_route` / `retry_storm` 前台靜音政策與可行動 route-warning payload shaping 抽至 `daily_decision_route_warnings.py`，讓主 queue 專注跨來源組裝與排序；主 module 從 345 行降至 319 行，新 policy module 39 行並受 `< 80` guard 保護，恢復 queue size gate 且不移除底層維運遙測；完整 suite `1691 passed, 5 skipped`。
- D570：P3-464 將正式 analysis prompt config 的 84 個 legacy placeholders 遷移為 Jinja 語法，升版為 `agents:v2` 並新增 no-legacy contract；正式 `build_prompt()` lane 可在 DeprecationWarning 視為 error 時通過，renderer 仍保留舊格式相容與明確警告；完整 suite `1692 passed, 5 skipped` 且 warning summary 從 358 降為 0。
- D571：P3-465 補強 Agent Prompt Jinja Validation Guard，讓 `prompt_loader` 在 config 載入時解析 analysis prompt AST，拒絕未知頂層變數與無效 Jinja 語法，避免 `ChainableUndefined` 將 typo 靜默渲染成空內容；legacy 單大括號自訂模板仍可載入；完整 suite `1695 passed, 5 skipped` 且無 warning summary。
- D572：P3-466 補強 Agent Prompt Content Fingerprint，讓 `prompt_loader` 對 version、state-view policy、system prompts 與 analysis prompts 產生 canonical SHA-256，輸出完整 `prompt_fingerprint` 並將前 16 碼附加到 `prompt_version`，使 workflow、report execution summary 與 reproducibility packet 能區分同一人類版本下的實際 prompt 內容；完整 suite `1698 passed, 5 skipped` 且無 warning summary。
- D573：P3-467 補強 Full Prompt Fingerprint Propagation，將完整 SHA-256 從 prompt loader 傳入 GraphState、AnalysisContext 與 data snapshot reproducibility packet；snapshot sanitizer 只允許 64 位十六進位 fingerprint，避免任意 prompt-like 內容繞過敏感欄位防線；完整 suite `1699 passed, 5 skipped` 且無 warning summary。
- D574：P3-468 補強 Effective Prompt Bundle Fingerprint，將 `runtime_rules.json` 納入 canonical prompt identity，讓 numeric tool、data enrichment、identity guard、final-audit preflight 與 structured-output 規則變更也會切換 workflow/report fingerprint；非 object 規則根節點在載入時直接拒絕；完整 suite `1701 passed, 5 skipped` 且無 warning summary。
- D575：P3-469 補強 Canonical Runtime Rule Snapshot，讓 prompt fingerprint 與實際 prompt injection 共用 `prompt_rules.load_runtime_prompt_rules()` 的 process-stable path snapshot；替代規則檔不再逐出正式規則快照，避免同一 workflow 的稽核 identity 與注入規則在啟動競態中分裂；完整 suite `1702 passed, 5 skipped` 且無 warning summary。
- D576：P3-470 補強 Runtime Code Dirty Provenance，於 workflow 初始化時捕捉 process-stable Git commit 與 dirty state，傳入 GraphState、AnalysisContext、data snapshot reproducibility packet 與報告可重現資訊；`true`、`false`、`null` 分別代表 dirty、clean、unknown，避免未提交程式碼被單一 commit 錯誤背書；focused regression `266 passed`、完整 suite `1710 passed, 5 skipped` 且無 warning summary；新 helper isolated mypy 通過，專案級 mypy 仍有既有 `543 errors in 87 files` baseline。
- D577：P3-471 補強 Commercial Operator Controls First-Viewport Recovery，將 desktop 折疊設定與四格操作護欄改為同列，縮短 desktop 上方留白與 portfolio CSV editor 高度，讓 1280×720 的三個 commercial 頁面主要 CTA 全部留在首屏；375×812 與 768×900 維持堆疊與無水平溢出；commercial layout/Playwright suite `17 passed`，完整 suite `1710 passed, 5 skipped`。
- D578：P3-472 補強 Candidate Next Actions，保留 screener 候選的 ticker、公司名稱、入選理由與 score，將單一「查看候選」改為「查看股票快照」、「加入追蹤」、「選擇分析模式」三個可執行操作；三者沿用既有 StockSnapshotPanel，分析只預填與聚焦、不自動送出；candidate contract `6 passed`、focused suite `202 passed`、live Playwright 桌機/390px 手機與 overflow QA 通過，完整 suite `1720 passed, 5 skipped`。
- D579：P3-473 完成 Daily Decision Frontstage Noise Boundary 的 live projection audit，確認 8080 runtime 的 `model_route_budget` 仍保留 `slow_route` 維運警示，但 frontstage route-warning projection 與 decision queue 都不含 `slow_route` / `retry_storm`；policy/downstream focused suite `209 passed`。
- D580：P3-474 完成 Provider Monitor Queue Boundary 的 live projection audit，確認 provider impact ledger 仍保留 `monitor_reports=13`，但 decision queue 與下游前台沒有 `monitor_provider`；blocking provider recovery 仍保留，並將兩份 implementation plan 的狀態與 dirty-worktree 不提交邊界同步完成。
- D581：P3-475 補強 Frontend/Backend Pipeline Metadata Drift Guard，以正式前端 dependency order 載入 `ui_helpers.js`，對照後端四種 pipeline 與 `both` run contract 的 label、short label、hint、Agent 數與 run metadata；sync test `1 passed`，但仍明確保留兩份來源尚未被宣稱為真正 single source。
- D582：P3-476 建立 canonical pipeline mode catalog，將後端執行 metadata 與使用者決策語意組裝成 `pipeline_modes.v1` 唯讀 API；前端以 `pipeline_mode_catalog.js` 在初始 fallback 後合併 runtime catalog，API 失敗時保留既有操作能力，catalog、loader、script order 與文件契約測試均已補齊。
- D583：P3-477 建立正式 `DESIGN.md` 設計系統基線，將受眾、工作流、字體層級、色彩狀態、密度、可及性、mobile 與驗證門檻集中；`docs/frontend-design-checkpoints.md` 改為操作入口，文件契約測試鎖住基線與實際 CSS token 的對應。
- D584：P3-478 將 pipeline fallback 改為由 `scripts/generate_pipeline_mode_fallback.py` 從 backend canonical catalog 產生的 build-time artifact，`scripts/ci_gate.sh` 以 `--check` 阻擋 stale fallback；前端先載入 generated artifact，再由 runtime API 非阻塞更新；focused suite `287 passed`、完整 suite `1733 passed, 5 skipped`、視覺回歸 `2 passed`，live 8080 catalog 與 HTML order 驗證通過。
- D585：P3-479 將視覺回歸接入 CI 預設 gate；當 `CI=1/true/yes` 且未明確覆寫 `RUN_VISUAL_REGRESSION` 時，`ci_gate.sh` 會以 required 模式執行 `scripts/visual_regression.sh`，本機快速 gate 與手動強制執行行為維持不變；相關 contract `144 passed`、視覺回歸 `2 passed`、完整 suite `1734 passed, 5 skipped`。
- D586：P3-480 將首頁五個平鋪 tab 收斂成「分析工作台」與「監控工作台」兩組，保留既有 panel ID/deep link 與預設商業版入口；keyboard Arrow/Home/End 改在所屬 tablist 內移動，桌面兩組並排、手機單欄，home focused `4 passed`、visual regression `3 passed`、完整 suite `1736 passed, 5 skipped`。
- D587：P3-481 在完整 HTML/Markdown 報告正文頂部新增 `報告使用範圍與判讀限制` reading notice；它讀取既有 `data_trust`、`evidence_exit_gate`、`content_credibility`、`report_conformance`，在 gate 缺漏時保持 pending/warning，只有完整通過才顯示已通過已知檢查，並明確說明不等於即時下單訊號或投資保證；reading notice `4 passed`、高顯著性報告契約組 `250 passed`、完整 suite `1740 passed, 5 skipped`。
- D588：P3-482 將同一個 reading boundary 推到歷史報告 preview，讓舊 artifact 或缺少品質 gate 的 snapshot 在建議數字前先顯示 pending/warning/blocked/passed 採用前提示；新增 `report_reading_boundary_policy.js`、preview DOM/CSS 與明確 app wiring，preview boundary `2 passed`、static/accessibility/size focused `4 passed`、完整 suite `1742 passed, 5 skipped`。
- D589：P3-483 新增 `scripts/check_visual_regression.py` runtime preflight，讓 CI、直接 visual script 與 setup script 都在 visual suite 前實際 launch headless Chromium；browser 缺失時提前輸出 `scripts/setup_visual_regression.sh` 修復命令，不在 CI gate 中偷偷安裝未鎖版本套件；preflight `3 passed`、正式 CI gate `1745 passed, 4 skipped, 1 deselected`、coverage `84%`、visual regression `3 passed`。
- D590：P3-484 固定 visual setup 的 Python Playwright 版本為 `1.60.0`，並將 preflight script 設為可直接執行，避免 setup 入口與診斷文件因套件漂移或檔案權限產生假綠燈；preflight `5 passed`、正式 CI gate `1747 passed, 4 skipped, 1 deselected`、coverage `84%`、visual regression `3 passed`。
- D591：P3-485 將 visual runtime 從單一版本 pin 提升為完整 hash-lock，新增 `scripts/visual_requirements.txt` / `visual_requirements.lock`，供應鏈 audit 同時檢查 backend 與 visual lock，CI 另產生 `backend/cache/visual-sbom.cdx.json`；visual/setup/supply-chain focused `20 passed`、正式 CI gate `1751 passed, 4 skipped, 1 deselected`、coverage `84%`、visual regression `3 passed`。
- D592：P3-486 建立隔離 `.audit-venv` 與 `scripts/security_requirements.txt` / `security_requirements.lock`，讓 `pip-audit 2.10.1` 不污染主 `.venv`；供應鏈 gate 改為缺少 scanner 時 fail-closed，並修補掃描發現的 `aiohttp 3.14.1`、`cryptography 48.0.1`、`pytest 9.0.3`、`starlette 1.3.1`；正式 CI `1755 passed, 4 skipped, 1 deselected, 12 subtests passed`、coverage `84%`、visual regression `3 passed`，三份 lock 均回報無已知漏洞。
- D593：P3-487 新增 `visual_browser_runtime.json` 與 preflight identity guard，核對 Playwright `1.60.0` 對應的 Chromium revision `1223`、Chrome for Testing `148.0.7778.96`、cache install marker 與啟動後 browser version；project-runtime focused visual/docs `9 passed`，系統 Python 載入其他 Playwright 版本時會明確阻擋並要求使用 project Python wrapper。
- D594：P3-488 將既有 snapshot hash 驗證接到報告 row、preview reading boundary 與 daily report repair queue；`verified` 才能維持完整通過，legacy/hashless snapshot 顯示 `unverified` warning，hash mismatch 變成 `invalid` blocked 並阻擋自動重跑；focused quality/preview/boundary/static/dashboard suite `20 + 42 + 7 + 135 + 1 passed`。
- D595：P3-489 修正分層 report artifact 維運漏掃：`verify-snapshots` 與 `storage-summary` 都遞迴掃描 `backend/output/YYYY-MM/TICKER/` 與 legacy flat path，結果以相對 storage key 識別並排除 symlink；nested/symlink/docs focused `5 passed`。
- D596：P3-490 保留 daily decision queue 的 blocked report repair 邊界：report repair action 從 `report_quality_repair_queue` 轉入 `decision_queue.items` 時會保留 `blocks_auto_rerun` 與 `reason_codes`，避免 dashboard/notification/automation 把 integrity/manual-review blocker 誤當可盲目重跑；RED→GREEN 單測與 queue/dashboard/repair focused `69 passed`。
- D597：P3-491 將 blocked report repair `reason_codes` 延伸到 notification 出站上下文：`notification_plan.messages` 與 `delivery_outbox` 保留 report repair reason codes，讓 sender channel 與 delivery audit context 仍能看到 blocked 原因；修正後 `free_notification_plan.py` 維持 299 行 guard，notification/queue/dashboard/audit/docs/HCS/import focused `252 passed`。
- D598：P3-492 加固 notification delivery audit 的 report repair `reason_codes` 持久化邊界：audit context 以 text-list safe conversion 保留壞元素前已解析的 blocked-repair reason code，避免 malformed reason-code object 中斷 delivery audit 寫入或抹掉人工處理原因；RED→GREEN 單測、docs contract 與 audit/notification/docs/HCS focused 驗證通過。
- D599：P3-493 加固 notification delivery audit context 的 outbox metadata 枚舉邊界：`context_json_from_outbox()` 改用 mapping-item safe conversion 讀取 outbox context，避免 malformed `.items()` accessor 中斷 audit persistence 或抹掉 source、ticker、report、CTA、queue rank 與 blocked-repair reason context；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D600：P3-494 加固 notification delivery audit context 的 JSON key 邊界：context snapshot 在 JSON serialization 前忽略非字串 outbox metadata key，避免 mixed key types 讓 `sort_keys=True` 中斷 audit persistence 或產生 synthetic persisted field names；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D601：P3-495 加固 notification delivery audit context 的 metadata value 序列化邊界：context snapshot 在 JSON serialization 前正規化 values，保留安全 scalar/list/dict，丟棄無法安全轉文字的 optional metadata，避免 unstringable value 中斷 audit persistence 或抹掉相鄰 source、ticker、report、rank 與 blocked-repair reason context；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D602：P3-496 加固 notification delivery audit context 的 sequence metadata 邊界：context snapshot 在 JSON serialization 前以 sequence-safe conversion 讀取 list/tuple metadata，避免 malformed sequence iterator 中斷 audit persistence 或抹掉相鄰 source、ticker、report、rank 與 blocked-repair reason context；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D603：P3-497 加固 notification delivery audit context 的 numeric metadata JSON 邊界：context snapshot 在 JSON serialization 前丟棄 NaN/Infinity 等非有限 float metadata，避免 persisted audit context 洩漏非標準 JSON number，同時保留相鄰 source、ticker、report、rank 與 blocked-repair reason context；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D604：P3-498 加固 notification delivery reconcile 的 retry backoff finite-float 邊界：audit retry wait 計算前會把 NaN/Infinity backoff 轉為 0，避免 sender preflight 因 `math.ceil(inf)` 崩潰或產生無限等待，同時保留已失敗 delivery 的可重送判斷；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D605：P3-499 加固 notification delivery reconcile 的 current-time finite-float 邊界：audit retry wait 計算前若呼叫端傳入 NaN/Infinity `now`，會回退到 runtime current time，避免 sender preflight 因 `math.ceil(-inf)` 崩潰，同時保留 retry_wait / should_send 判斷；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D606：P3-500 加固 notification delivery audit row timestamp 輸出邊界：`list_delivery_records()` / summary / sender preflight 讀取既有 audit row 時會以 finite-float conversion 輸出 first_seen、last_attempt、last_success timestamp，避免 legacy 或修復過的 row 洩漏 Infinity 等非標準 numeric values；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D607：P3-501 加固 notification delivery audit row text 輸出邊界：`list_delivery_records()` / summary / sender preflight 讀取既有 audit row 時會以 string-safe conversion 輸出 delivery/channel/message/dedupe/status/error/response id，避免 legacy 或修復過的 row 洩漏 blob bytes 到 API 或 sender JSON；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D608：P3-502 加固 notification delivery audit row attempt-count 輸出邊界：`list_delivery_records()` / summary / sender preflight 讀取既有 audit row 時會以 string-safe integer conversion 輸出 attempt count，避免 legacy 或修復過的 row 因 malformed attempt-count BLOB/TEXT 中斷 API 或 sender JSON；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D609：P3-503 加固 notification delivery audit persisted context JSON 解析邊界：`context_from_json()` 載入 persisted context 前不再做 truthiness fallback，避免 malformed context payload truthiness 中斷 sender preflight、summary 或 API response；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D610：P3-504 改善 notification delivery audit byte-like text 可讀性：共用 `safe_text()` 會先將 bytes/bytearray/memoryview 以 UTF-8 解碼，再輸出 channel/message/status/error/response 等 audit text，避免 sender preflight、summary 或 API response 出現 `b'...'` Python bytes repr；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D611：P3-505 加固 notification delivery audit persisted context JSON numeric 輸出邊界：`context_from_json()` 載入 legacy persisted context 後會套用 JSON-safe normalization，丟棄 NaN/Infinity 等非有限 numeric values，避免 sender preflight、summary 或 API response 洩漏非標準 JSON number；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D612：P3-506 加固 notification delivery reconcile 的 byte-like stored delivery key 查找邊界：sender preflight 查 audit rows 時會同時比對 raw delivery key 與 `CAST(delivery_key AS TEXT)`，並用 string-safe decoded key 建立 lookup map，避免 legacy/repaired BLOB primary key 讓已送紀錄被誤判為 `not_seen` 而重複發送；RED→GREEN 單測、docs contract 與 focused audit/docs 驗證通過。
- D613：P3-507 加固 notification delivery record upsert 的 byte-like stored delivery key 查找邊界：`record_delivery_attempt()` 查找、更新與回讀既有 audit row 時同時比對 raw delivery key 與 `CAST(delivery_key AS TEXT)`，避免 legacy/repaired BLOB primary key 在下一次 attempt 被插入成第二筆 TEXT key row；RED→GREEN 單測與 docs contract 驗證通過。
- D614：P3-508 加固 notification delivery reconcile 的 duplicate decoded delivery key 選擇邊界：sender preflight 查到同一 decoded key 的 BLOB/TEXT duplicate rows 時，會讓 `sent` row 覆蓋 failed/pending row，避免舊資料重複列把已送 suppression 訊號降級成 retry；RED→GREEN 單測與 docs contract 驗證通過。
- D615：P3-509 加固 notification delivery reconcile 的 byte-like sent status duplicate 選擇邊界：duplicate decoded delivery key 排序時會把 `CAST(delivery_status AS TEXT) = 'sent'` 也視為已送，避免 repaired BLOB status row 被 SQL 排序錯過而讓 failed row 覆蓋 suppression 訊號；RED→GREEN 單測與 docs contract 驗證通過。
- D616：P3-510 加固 notification delivery record upsert 的 sent duplicate preservation 邊界：`record_delivery_attempt()` 更新 duplicate decoded delivery key rows 時保留既有 sent status，並在回讀 saved row 時優先回傳 sent row，避免 late failed duplicate attempt 把已送 audit row 降級成 retry；RED→GREEN 單測與 docs contract 驗證通過。
- D617：P3-511 加固 notification delivery record upsert 的 sent duplicate last-error preservation 邊界：`record_delivery_attempt()` 更新既有 sent row 時保留原 `last_error`，避免 late failed duplicate attempt 讓 sent audit row 出現誤導性的 failure error；RED→GREEN 單測與 docs contract 驗證通過。
- D618：P3-512 加固 notification delivery record upsert 的 sent duplicate response-id preservation 邊界：`record_delivery_attempt()` 更新既有 sent row 時保留原 `last_response_id`，避免 late failed duplicate attempt 用錯誤 response id 覆蓋成功 sender response id；RED→GREEN 單測與 docs contract 驗證通過。
- D619：P3-513 加固 notification delivery record upsert 的 sent duplicate context snapshot preservation 邊界：`record_delivery_attempt()` 更新既有 sent row 時保留原 `context_json`，避免 late failed duplicate attempt 改掉已送訊息的 source、ticker、report 與 CTA context；RED→GREEN 單測與 docs contract 驗證通過。
- D620：P3-514 加固 notification delivery record upsert 的 sent duplicate identity metadata preservation 邊界：`record_delivery_attempt()` 更新既有 sent row 時保留原 `channel_id`、`message_id` 與 `dedupe_key`，避免 late failed duplicate attempt 改掉已送訊息的 channel/message/dedupe 身份快照；RED→GREEN 單測與 docs contract 驗證通過。
- D621：P3-515 加固 notification delivery reconcile 的 whitespace-padded stored delivery key 查找邊界：sender preflight 查 audit rows 時會同時比對 `TRIM(CAST(delivery_key AS TEXT))`，並以 stripped decoded key 建立 lookup map，避免 legacy/repaired padding key 讓已送紀錄被誤判為 `not_seen` 而重複發送；RED→GREEN 單測與 docs contract 驗證通過。
- D622：P3-516 加固 notification delivery record upsert 的 whitespace-padded stored delivery key 查找邊界：`record_delivery_attempt()` 查找、更新與回讀既有 audit row 時同時比對 `TRIM(CAST(delivery_key AS TEXT))`，避免 legacy/repaired padding key 在下一次 attempt 被插入成第二筆 trimmed-key row；RED→GREEN 單測與 docs contract 驗證通過。
- D623：P3-517 加固 notification delivery reconcile 的 control-whitespace stored delivery key 查找邊界：sender preflight 查 audit rows 時會用 `TRIM(CAST(delivery_key AS TEXT), CHAR(9) || CHAR(10) || CHAR(13) || CHAR(32))` 對齊 Python `.strip()` 常見 tab/newline/carriage-return/space padding，避免 control whitespace key 被誤判為 `not_seen` 而重複發送；RED→GREEN 單測與 docs contract 驗證通過。
- D624：P3-518 加固 notification delivery record upsert 的 control-whitespace stored delivery key 查找邊界：`record_delivery_attempt()` 查找、更新與回讀既有 audit row 時使用同一組 tab/newline/carriage-return/space trim 字元集，避免 control whitespace key 在下一次 attempt 被插入成第二筆 stripped-key row；RED→GREEN 單測與 docs contract 驗證通過。
- D625：P3-519 加固 notification delivery audit row 的 delivery key 輸出正規化邊界：`_row_to_record()` 會在 record output 前 strip stored `delivery_key`，避免 legacy/repaired padded key 洩漏到 sender preflight、summary 或 API response；RED→GREEN 單測與 docs contract 驗證通過。
- D626：P3-520 加固 notification delivery audit row 的 delivery status 輸出正規化邊界：`_row_to_record()` 會在 record output 前 strip 並 lowercase stored `delivery_status`，避免 legacy/repaired padded 或 uppercase status 洩漏到 sender preflight、summary 或 API response；RED→GREEN 單測與 docs contract 驗證通過。
- D627：P3-521 加固 notification delivery audit row 的 identity 欄位輸出正規化邊界：`_row_to_record()` 會在 record output 前 strip stored `channel_id`、`message_id` 與 `dedupe_key`，避免 legacy/repaired padded identity metadata 洩漏到 sender preflight、summary 或 API response；RED→GREEN 單測與 docs contract 驗證通過。
- D628：P3-522 加固 notification delivery reconcile 的 normalized sent status duplicate 選擇邊界：duplicate decoded delivery key 排序時會以 `LOWER(TRIM(CAST(delivery_status AS TEXT), ...)) = 'sent'` 判斷已送 row，避免 legacy/repaired padded 或 uppercase sent status 被 later failed duplicate 覆蓋 suppression 訊號；RED→GREEN 單測與 docs contract 驗證通過。
- D629：P3-523 加固 notification delivery record upsert 的 normalized sent status preservation 邊界：`record_delivery_attempt()` 更新既有 row 與回讀 saved row 時同樣以 normalized sent predicate 判斷已送狀態，避免 late failed attempt 降級 legacy/repaired padded 或 uppercase sent audit row；RED→GREEN 單測與 docs contract 驗證通過。
- D630：P3-524 加固 notification delivery audit listing 的 explicit zero limit clamp 邊界：`list_delivery_records(limit=0)` 不再被 `or 100` 放大成預設頁面大小，而是 clamp 到最小 1 筆，避免呼叫端要求最小樣本時意外拉出整頁 audit rows；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過，並維持 audit module 349 行。
- D631：P3-525 加固 notification delivery summary 與 attention context 的 normalized status projection 邊界：summary/attention context 讀到 padded 或 uppercase `delivery_status` 時會先 strip/lower 再統計與投影，避免 repaired 或 mocked audit rows 漏掉 failed/sent/pending counts、retry exhausted 與 affected source/ticker/report/CTA context；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過，並維持 audit module 349 行。
- D632：P3-526 加固 notification delivery reconcile 的 normalized status decision 邊界：sender preflight 讀到 padded 或 uppercase `delivery_status` 時會先 strip/lower 再判斷 already-sent suppression 與 retry wait，避免 repaired 或 mocked audit rows 重新發送已送訊息或跳過 backoff；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過，並維持 audit module 349 行。
- D633：P3-527 加固 notification delivery reconcile 的 sent success timestamp output 邊界：sender preflight 讀到 repaired 或 mocked sent audit row 的 `last_success_at = NaN/Infinity` 時會以 finite-float conversion 輸出，避免非標準 JSON number 洩漏到 sender/API payload；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過，並維持 audit module 349 行。
- D634：P3-528 加固 notification delivery response-id output normalization 邊界：`_row_to_record()` 與 `_reconciled_outbox_entry()` 會在 record/list/API 與 sender preflight output 前 strip `last_response_id`，避免 repaired 或 sender-returned response id 的 tab/newline/space padding 洩漏到對外 payload；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過，並維持 audit module 349 行。
- D635：P3-529 加固 notification delivery persisted context JSON string-safe parsing 邊界：`context_from_json()` 會先以 `safe_text()` 轉換 payload 再載入 JSON，避免 repaired 或 mocked stringable context payload 被丟成空 audit context，讓 sender preflight 與維運 context recovery 保留 source、ticker、report 與 CTA 脈絡；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D636：P3-530 加固 notification delivery attention context identity output 邊界：`attention_contexts_from_records()` 會在 summary output 前 strip failed row 的 `delivery_key` 與 `channel_id`，避免 repaired 或 mocked failed audit rows 的 tab/newline/space padding 洩漏到 ops、daily queue 或 sender context 摘要；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D637：P3-531 加固 notification delivery direct context map JSON-safe output 邊界：`safe_dict()` 會在 dict conversion 後套用既有 `_json_safe_context()`，避免 direct/mocked audit context maps 的 NaN/Infinity 洩漏到 reconcile `audit_context`、ops 或 daily queue summary payload；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D638：P3-532 加固 notification delivery audit context whitespace-only metadata 邊界：`_present()` 會把 strip 後為空的字串視為缺值，避免 optional ticker、filename、CTA、nested 或 sequence context 欄位只有格式空白時仍被持久化成 audit history；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D639：P3-533 加固 notification delivery audit context empty collection metadata 邊界：`_present()` 會把 normalization 後為空的 list/dict 視為缺值，避免 optional list/object context 欄位的子項全被清理後仍以空 `[]` / `{}` 持久化成 audit history；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D640：P3-534 加固 notification delivery attention context optional limit 邊界：`attention_contexts_from_records(limit=None)` 會回到預設 5 筆上限，而不是把 safe integer conversion 的 `None -> 0` 當成明確空結果，避免 ops、daily queue 或 sender summary 因 optional caller limit 消失 failed delivery context；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D641：P3-535 加固 notification delivery reconcile optional retry budget 邊界：`reconcile_outbox_with_audit(max_attempts=None)` 會回到預設 3 次 retry budget，而不是把 `None` 經 safe integer conversion 當成 1 次上限，避免 failed delivery 在第一次失敗後因 optional caller configuration 過早標記 `retry_exhausted`；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D642：P3-536 加固 notification delivery reconcile optional retry backoff 邊界：`reconcile_outbox_with_audit(retry_backoff_seconds=None)` 會回到預設 900 秒 backoff，而不是把 `None` 經 safe float conversion 當成 0 秒，避免 optional caller configuration 讓 failed delivery 略過 retry wait 並立即重送；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D643：P3-537 加固 notification delivery reconcile missing outbox entries 邊界：`reconcile_outbox_with_audit(None)` 會回傳空 preflight result，而不是在 audit lookup 前因 `NoneType` iteration 崩潰，讓 sender 對 optional delivery payload 的「沒有待送工作」狀態可安全處理；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D644：P3-538 加固 notification delivery reconcile tuple outbox entries 邊界：`reconcile_outbox_with_audit()` 會保留 tuple outbox entry batches，而不是把 immutable sender payload 視為 missing/empty outbox，避免 pending delivery work 在 audit lookup 前消失；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D645：P3-539 加固 notification delivery reconcile mapping outbox entries 邊界：`reconcile_outbox_with_audit()` 會保留 list/tuple batch 裡的 mapping entry，並在 preflight 入口轉成 dict，避免 immutable entry payload 被 `dict` 型別檢查丟掉而讓 pending delivery work 消失；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D646：P3-540 加固 notification delivery audit persistence mapping outbox entries 邊界：`record_delivery_attempt()` 會在 identity/context extraction 前把 mapping outbox entry 正規化為 dict，避免 sender preflight 已接受的 immutable entry payload 在 audit write 階段因 dict-native helper 崩潰；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D647：P3-541 加固 notification delivery reconcile malformed mapping outbox entry 隔離邊界：`reconcile_outbox_with_audit()` 會透過 `safe_dict_list()` 跳過無法正規化的 mapping entry，避免單筆壞 immutable entry 在 audit lookup 前中斷整批 preflight 並抹掉相鄰 pending delivery work；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D648：P3-542 加固 notification delivery audit persistence malformed mapping outbox entry fail-closed 邊界：`record_delivery_attempt()` 會透過 `safe_mapping_dict()` 將無法正規化的 mapping entry 視為缺少 identity，回到明確的 `delivery_key is required` 錯誤，而不是漏出底層 iterator/accessor exception；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D649：P3-543 加固 notification delivery audit context nested mapping metadata 邊界：`context_json_from_outbox()` 的 JSON-safe normalization 會保留 nested `Mapping` metadata 為結構化 dict，而不是把 immutable nested context 字串化，避免 sender/ops triage 失去 queue rank 或 nested evidence；RED→GREEN 單測、docs contract 與 focused audit/docs/HCS/import 驗證通過。
- D650：P3-544 加固 data trust snapshot content hash mapping wrapper 邊界：`snapshot_content_hash()` 與 `verify_data_snapshot_integrity()` 接受一般 `Mapping` snapshot wrapper，並保留 dict subclass 的 native field read 防護，避免 immutable snapshot container 在 integrity verification 前被誤判成空 hash 或非 object；RED→GREEN 單測、docs contract 與 focused data-trust/docs/HCS/import 驗證通過。
- D651：P3-545 加固 snapshot maintenance falsey hash metadata 邊界：`verify-snapshots` 使用 core integrity verifier 的 `expected_hash` 判斷 hash metadata 是否存在，避免 JSON-safe falsey hash 值（例如 `0`）被誤當 missing hash backfill，而應回報 mismatch 或在 write mode 修復；RED→GREEN 單測、docs contract 與 focused maintenance/docs/HCS/import 驗證通過。
- D652：P3-546 加固 report quality repair queue snapshot integrity mapping 邊界：`snapshot_integrity_repair_item()` 以 shared mapping-safe conversion 接受 immutable `snapshot_integrity` payload，避免 invalid snapshot hash 因 nested mapping wrapper 被忽略而沒有進入 blocked manual-review repair action；RED→GREEN 單測、docs contract 與 focused repair/docs/HCS/import 驗證通過。
- D653：P3-547 加固 report quality repair queue snapshot integrity scalar error detail 邊界：`snapshot_integrity_repair_item()` 會以 string-safe fallback 保留 scalar `snapshot_integrity.errors` mismatch detail，避免 invalid snapshot blocker 只顯示泛用修復文字而失去 operator 可判讀的 hash mismatch 證據；RED→GREEN 單測、docs contract 與 focused repair/docs/HCS/import 驗證通過。
- D654：P3-548 加固 report preview reading boundary snapshot integrity detail 邊界：`report_reading_boundary_policy.js` 會在 invalid snapshot integrity 時把 `errors` detail 以安全文字附加到 blocked preview notice，避免 preview 只顯示泛用品質 gate 文案而漏掉 `snapshot_hash mismatch` 證據；RED→GREEN 單測、docs contract 與 focused preview/docs/HCS/import 驗證通過。
- D655：P3-549 加固 notification delivery outbox report repair detail 邊界：`delivery_outbox` 會保留 report repair action 的 `detail`，避免 sender channel 與 persisted delivery audit context 只看見 `reason_codes` 而漏掉 `snapshot_hash mismatch` 等具體 blocked-repair 證據；RED→GREEN 單測、docs contract 與 focused notification/docs/HCS/import 驗證通過。
- D656：P3-550 加固 daily decision queue report repair detail truthiness 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `detail`，避免 malformed detail truthiness 中斷每日 queue 或抹掉 `snapshot_hash mismatch` 等具體 blocked-repair 證據；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D657：P3-551 加固 daily decision queue report repair title truthiness 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `title`，避免 malformed title truthiness 中斷每日 queue 或讓 operator 看不到哪份報告需要處理；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D658：P3-552 加固 daily decision queue report repair filename alias truthiness 邊界：`_repair_action_payload()` 以 string-safe selection 投影 report repair `filename` / `report_filename`，避免 malformed filename truthiness 中斷每日 queue 或抹掉 report artifact identity；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D659：P3-553 加固 daily decision queue report repair recommended_action truthiness 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `recommended_action`，避免 malformed action truthiness 中斷每日 queue 或抹掉 refresh/rerun/wait/manual-review routing intent；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D660：P3-554 加固 daily decision queue report repair ticker truthiness 與 payload identity 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `ticker` 並回填 queue item，避免 malformed ticker truthiness 中斷每日 queue 或讓非字串 report identity 流向下游 consumer；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D661：P3-555 加固 daily decision queue report repair pipeline_id truthiness 與 payload identity 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `pipeline_id`，避免 malformed pipeline truthiness 中斷每日 queue 或讓非字串 report identity 流向下游 consumer；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D662：P3-556 加固 daily decision queue report repair priority_score truthiness 邊界：`_int()` 不再用 raw truthiness 選擇預設值，避免 malformed priority truthiness 中斷每日 queue 或抹掉可整數化的 report repair priority；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D663：P3-557 加固 daily decision queue report repair severity payload 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `severity`，避免 malformed severity truthiness 或非字串物件流入 queue/notification consumer；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D664：P3-558 加固 daily decision queue report repair action_label payload 邊界：`_repair_action_payload()` 以 string-safe conversion 投影 report repair `action_label`，避免 malformed CTA label truthiness 或非字串物件流入 queue/notification/UI consumer；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D665：P3-559 加固 daily decision queue rerun report ticker truthiness 與 payload identity 邊界：`_rerun_report_payload()` 以 string-safe conversion 投影 rerun report `ticker` 並回填 queue item，避免 malformed ticker truthiness 中斷 stale-report rerun ordering 或讓非字串 report identity 流向下游 consumer；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D666：P3-560 加固 daily decision queue rerun report pipeline_id truthiness 與 payload identity 邊界：`_rerun_report_payload()` 以 string-safe conversion 投影 rerun report `pipeline_id`，避免 malformed pipeline truthiness 中斷 stale-report rerun ordering 或讓非字串 pipeline identity 流向下游 consumer；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D667：P3-561 加固 daily decision queue rerun report filename alias truthiness 與 artifact identity 邊界：`_report_key()` 與 `_rerun_report_payload()` 以 string-safe selection 投影 rerun report `filename` / `report_filename`，避免 malformed filename truthiness 中斷 stale-report rerun dedupe/order 或抹掉 artifact identity；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D668：P3-562 加固 daily decision queue rerun report detail truthiness 與 stale evidence 邊界：`_rerun_report_payload()` 以 string-safe fallback 投影 rerun report `detail`，避免 malformed rerun reason truthiness 中斷 stale-report rerun ordering 或抹掉具體 stale-snapshot 證據；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D669：P3-563 加固 daily decision queue report key ticker truthiness 與 dedupe identity 邊界：`_report_key()` 以 string-safe conversion 投影 `ticker`，避免 malformed ticker truthiness 中斷 report repair 或 stale-report rerun skip-key matching；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D670：P3-564 加固 daily decision queue report key pipeline_id truthiness 與 dedupe identity 邊界：`_report_key()` 以 string-safe conversion 投影 `pipeline_id`，避免 malformed pipeline truthiness 中斷 report repair 或 stale-report rerun skip-key matching；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D671：P3-565 加固 daily decision queue provider impact filename alias truthiness 與 artifact identity 邊界：`_provider_items()` 以 string-safe selection 投影 provider impact `filename` / `report_filename`，避免 malformed filename truthiness 中斷 provider recovery ordering 或抹掉 artifact identity；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D672：P3-566 加固 daily decision queue provider impact blocks_auto_rerun truthiness 與 blocking-filter 邊界：`_provider_items()` 以 bool-safe conversion 讀取 provider impact `blocks_auto_rerun`，避免 malformed blocking flag truthiness 中斷 provider recovery ordering；無法判讀的 flag 保守視為 non-blocking；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D673：P3-567 加固 daily decision queue provider impact recommended_action truthiness 與 wait-policy payload 邊界：`_provider_items()` 以 string-safe fallback 投影 provider impact `recommended_action`，避免 malformed action truthiness 中斷 provider recovery ordering 或抹掉 wait/retry policy intent；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D674：P3-568 加固 daily decision queue provider impact ticker truthiness 與 payload identity 邊界：`_provider_items()` 以 string-safe conversion 投影 provider impact `ticker`，避免 malformed ticker truthiness 中斷 provider recovery ordering 或讓非字串 source identity 流向 queue consumers；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D675：P3-569 加固 daily decision queue provider impact pipeline_id truthiness 與 payload identity 邊界：`_provider_items()` 以 string-safe conversion 投影 provider impact `pipeline_id`，避免 malformed pipeline truthiness 中斷 provider recovery ordering 或讓非字串 pipeline identity 流向 queue consumers；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D676：P3-570 加固 daily decision queue provider impact ledger items truthiness 與 iteration 邊界：`_provider_items()` 以 iterator-safe `safe_dict_list()` 讀取 provider impact ledger `items`，避免 malformed item list truthiness 中斷 provider recovery ordering 或抹掉後續有效 impact rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D677：P3-571 加固 daily decision queue provider impact message truthiness 與 detail evidence 邊界：`_provider_detail()` 以 iterator-safe `safe_dict_list()` 與 string-safe conversion 讀取 provider impact `impacts[].message`，避免 malformed message truthiness 中斷 provider recovery ordering 或抹掉具體 provider evidence；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D678：P3-572 加固 daily decision queue provider impact ledger object truthiness 邊界：`build_daily_decision_queue()` 以 type-safe fallback 傳入 provider impact ledger，避免 malformed ledger truthiness 在 `_provider_items()` 前中斷每日 queue assembly 或抹掉有效 provider impact rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D679：P3-573 加固 daily decision queue report repair collection truthiness 與 row projection 邊界：`build_daily_decision_queue()` 以 iterator-safe `safe_dict_list()` 讀取 report repair collection，避免 malformed repair_items truthiness 在 repair action projection 前中斷每日 queue assembly 或抹掉後續有效 repair rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D680：P3-574 加固 daily decision queue ops payload truthiness 與 ops warning projection 邊界：`build_daily_decision_queue()` 以 type-safe fallback 傳入 notification delivery 與 route warning projection，避免 malformed ops truthiness 中斷每日 queue assembly 或抹掉後續有效 ops warning rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D681：P3-575 加固 daily decision queue explicit backtest collection truthiness 與 due-item projection 邊界：`_backtest_due_items()` 以 iterator-safe `safe_dict_list()` 讀取 `due_backtests` / `backtest_due` collection，避免 malformed explicit backtest truthiness 在 due-item projection 前中斷每日 queue assembly 或抹掉有效 backtest due rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D682：P3-576 加固 daily decision queue backtest evaluation details truthiness 與 computed-due 邊界：`_backtest_due_items()` 以 iterator-safe `safe_dict_list()` 讀取 `performance.details`，避免 malformed evaluation details truthiness 中斷每日 queue assembly 或讓真正到期報告被誤判為已完成回測；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D683：P3-577 加固 daily decision queue computed backtest report collection truthiness 與 due-date 邊界：`_backtest_due_items()` 以 iterator-safe `safe_dict_list()` 讀取 report rows，避免 malformed reports truthiness 中斷每日 queue assembly 或隱藏已到期但尚未回測的 report；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D684：P3-578 加固 daily decision queue rerun report collection truthiness 與 stale-report projection 邊界：`_rerun_items()` 以 iterator-safe `safe_dict_list()` 讀取 rerun report rows，避免 malformed rerun_reports truthiness 在 stale-report action projection 前中斷每日 queue assembly 或抹掉有效 rerun rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D685：P3-579 加固 daily decision queue watchlist collection truthiness 與 watchlist action projection 邊界：`_watchlist_items()` 以 iterator-safe `safe_dict_list()` 讀取 watchlist rows，避免 malformed high_priority_watchlist truthiness 在 watchlist action projection 前中斷每日 queue assembly 或抹掉有效 watchlist rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D686：P3-580 加固 daily decision queue screener candidate collection truthiness 與 candidate action projection 邊界：`_candidate_items()` 以 iterator-safe `safe_dict_list()` 讀取 candidate rows，避免 malformed candidates truthiness 在 candidate action projection 前中斷每日 queue assembly 或抹掉有效 screener candidate rows；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D687：P3-581 加固 daily decision queue screener candidate text field truthiness 與 display projection 邊界：`_candidate_items()` 以 string-safe conversion 讀取 candidate `ticker`、`company_name`、`reason`，避免 malformed text truthiness 中斷 candidate action output 或讓非字串顯示欄位流向 queue consumers；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D688：P3-582 加固 daily decision queue backtest due action text field truthiness 與 artifact identity projection 邊界：`_due_item()` 以 string-safe conversion 讀取 due backtest `ticker`、`filename` / `report_filename`、`pipeline_id`，避免 malformed text truthiness 中斷 backtest due action output 或讓非字串 identity 流向 queue consumers；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D689：P3-583 加固 daily decision queue computed backtest report artifact field truthiness 與 due detection 邊界：`_backtest_due_items()` 以 string-safe conversion 讀取 computed due report `filename` / `report_filename` 與 evaluated detail artifact key，避免 malformed artifact truthiness 中斷 computed backtest due detection 或隱藏到期報告；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D690：P3-584 加固 daily decision queue display limit truthiness 與 rendered slice 邊界：`build_daily_decision_queue()` 以 integer-safe conversion 讀取 display `limit` 後再切片 rendered items，避免 malformed limit truthiness 中斷每日 queue assembly 或讓 secondary count 計算失真；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D691：P3-585 加固 daily decision queue integer conversion failure 邊界：`_int()` 捕捉 malformed numeric payload 在 `__int__()` 階段拋出的轉換例外，避免 priority、horizon、display 與 summary 計算因壞數字欄位中斷 queue assembly；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D692：P3-586 加固 daily decision queue notification delivery count truthiness 邊界：`notification_delivery_items()` 以 integer-safe conversion 讀取 sender audit `failed_count` 與 `retry_exhausted_count`，避免 malformed 通知通道計數 truthiness 中斷每日 queue assembly 或隱藏可見的通知通道修復 action；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D693：P3-587 加固 daily decision queue notification delivery health truthiness 邊界：`notification_delivery_items()` 以 string-safe conversion 讀取 sender audit `health` 後再判斷 warning state，避免 malformed 通知通道健康狀態 truthiness 中斷每日 queue assembly 或隱藏可見的通知通道修復 action；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D694：P3-588 加固 daily decision queue notification delivery channel-count map truthiness 邊界：`notification_delivery_items()` 以 dict-safe conversion 讀取 sender audit `channel_counts` 後再輸出修復 action，避免 malformed 通知通道分布 truthiness 中斷每日 queue assembly 或抹掉可見 channel context；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D695：P3-589 加固 daily decision queue notification delivery failure-reason detail truthiness 邊界：`_notification_delivery_detail()` 不再以 raw mapping truthiness 判斷 `failure_reason_counts` 是否存在，避免 malformed 通知失敗原因分布中斷每日 queue assembly 或抹掉 timeout/auth triage context；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D696：P3-590 加固 daily decision queue notification delivery failure-reason item access 邊界：`_notification_delivery_detail()` 捕捉 `failure_reason_counts.items()` 或 item unpack 失敗並降級為 base detail，避免 malformed 通知失敗原因 map accessor 中斷每日 queue assembly；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D697：P3-591 加固 daily decision queue notification delivery attention-context iterator 邊界：`notification_delivery_items()` 複製 sender audit `attention_contexts` 時捕捉 iterator 失敗並降級為空 context list，避免 malformed 通知 context list 中斷每日 queue assembly 或隱藏可見通知通道修復 action；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D698：P3-592 加固 daily decision queue notification delivery summary mapping 邊界：`notification_delivery_items()` 以 mapping-safe conversion 讀取 sender audit `notification_delivery` summary，避免 immutable mapping summary payload 被當成空摘要而隱藏可見通知通道修復 action；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D699：P3-593 加固 daily decision queue notification delivery nested count mapping 邊界：`notification_delivery_items()` 以 mapping-safe conversion 讀取 sender audit `channel_counts` 與 `failure_reason_counts`，避免 immutable nested count maps 被當成空分布而抹掉通知通道與失敗原因 triage context；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D700：P3-594 加固 daily decision queue notification delivery attention-context tuple 邊界：`notification_delivery_items()` 保留 tuple 形式的 sender audit `attention_contexts`，避免 immutable context batch 被當成空清單而抹掉受影響 ticker/report/CTA triage context；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D701：P3-595 加固 daily decision queue notification delivery attention-context mapping row 邊界：`notification_delivery_items()` 將 sender audit `attention_contexts` 裡的 immutable mapping row 與 nested `context` map 正規化為 plain dict，避免 mapping proxy 物件外溢到 queue API payload 或中斷 JSON serialization；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D702：P3-596 加固 daily decision queue notification delivery attention-context dict-subclass 邊界：`notification_delivery_items()` 將 sender audit `attention_contexts` 裡的 dict subclass row 與 nested `context` wrapper 正規化為 plain dict，避免自訂 context wrapper 外溢到 queue API payload；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D703：P3-597 加固 daily decision queue notification delivery attention-context nested mapping 邊界：`notification_delivery_items()` 遞迴正規化 sender audit `attention_contexts` 裡的 nested mapping metadata，避免 deeper `MappingProxyType` metadata 外溢到 queue API payload 或中斷 JSON serialization；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D704：P3-598 加固 daily decision queue notification delivery attention-context nested mapping item-access 邊界：`_plain_value()` 透過 mapping-item safe traversal 正規化 nested metadata，避免 nested dict subclass `.items()` 故障中斷 queue assembly 或抹掉有效 metadata context；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D705：P3-599 加固 daily decision queue notification delivery attention-context nested sequence iterator 邊界：`_plain_value()` 透過 sequence-item safe traversal 正規化 nested metadata list，避免 nested list subclass iterator 故障抹掉有效 triage tags 或 CTA evidence；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D706：P3-600 加固 daily decision queue notification delivery failure-reason native-item detail 邊界：`_notification_delivery_detail()` 透過 mapping-item safe traversal 產生 reason summary，避免 failure_reason_counts dict subclass `.items()` 故障時只剩 base detail、抹掉有效 timeout/auth 摘要；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D707：P3-601 加固 daily decision queue notification delivery attention-context top-level sequence fallback 邊界：`_safe_list()` 透過 sequence-item safe traversal 複製 top-level `attention_contexts` rows，避免 list subclass iterator 故障時整批抹掉有效 ticker/panel/CTA context；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D708：P3-602 加固 daily decision queue notification delivery failure-reason count rendering 邊界：`_reason_summary_part()` 對 reason count value 先做 string-safe rendering、失敗時回退 integer-safe conversion，避免 count 物件文字化故障時整段 timeout/auth 摘要退回 base detail；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D709：P3-603 加固 daily decision queue notification delivery failure-reason unrenderable-count omission 邊界：`_reason_summary_part()` 在 reason count 文字化與整數化都失敗時略過該 reason 片段，避免 queue detail 產生誤導性的 `reason=... 0` 摘要；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D710：P3-604 加固 daily decision queue notification delivery failure-reason non-positive count omission 邊界：`_reason_summary_part()` 只輸出 positive reason count，避免 0 或負數 sender audit count 出現在 operator detail 中、誤導為 active timeout/auth 摘要；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D711：P3-605 加固 daily decision queue notification delivery failure-reason boolean count omission 邊界：`_safe_positive_count_text()` 明確排除 boolean reason count，避免 `True` 被 Python 整數轉換視為 1 並出現在 operator detail 中、誤導為 active timeout/auth 摘要；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D712：P3-606 加固 daily decision queue notification delivery failure-reason fractional count omission 邊界：`_safe_positive_count_text()` 要求非字串 numeric reason count 必須等於自身整數值，避免 float、Decimal 或 Fraction 小數被 Python 整數轉換截斷後出現在 operator detail 中、誤導為 active timeout/auth 摘要；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D713：P3-607 加固 daily decision queue notification delivery failure-reason malformed key omission 邊界：`_safe_reason_text()` 只讓非空白字串 reason bucket 進入 operator detail，避免 boolean、numeric 或 blank sender audit reason key 被渲染成 synthetic timeout/auth 摘要；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D714：P3-608 加固 daily decision queue notification delivery failure-reason raw key omission 邊界：`_safe_reason_text()` 只允許 canonical low-cardinality reason bucket，避免 raw exception 字串或非標準 sender audit reason key 外洩到 operator detail；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D715：P3-609 加固 daily decision queue notification delivery failure-reason duplicate bucket aggregation 邊界：`_notification_delivery_detail()` 先彙總 canonical reason bucket 再輸出 operator detail，避免 casing 或 whitespace drift 造成 timeout/auth/network 摘要重複顯示；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D716：P3-610 加固 daily decision queue notification delivery failure-reason partial item fallback 邊界：`safe_mapping_items()` 在 dict subclass `.items()` 中途故障時改以 native dict items 重跑，避免前半段 partial item 讓後續 timeout/auth/network 摘要被抹掉；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D717：P3-611 加固 daily decision queue notification delivery attention-context partial iterator fallback 邊界：`safe_sequence_items()` 在 list/tuple subclass iterator 中途故障時改以 native sequence items 重跑，避免前半段 context 讓後續 ticker/report/CTA context 被抹掉；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D718：P3-612 加固 daily decision queue report repair partial iterator fallback 邊界：`safe_dict_list()` 在 list/tuple subclass iterator 中途故障時改以 native dict-list items 重跑，避免前半段 repair row 讓後續 report repair action 被抹掉；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D719：P3-613 加固 daily decision queue report repair reason-code partial iterator fallback 邊界：`safe_text_list()` 在 list/tuple subclass iterator 中途故障時改以 native text-list items 重跑，避免前半段 reason code 讓後續 blocked-repair cause 被抹掉；RED→GREEN 單測、docs contract 與 focused queue/docs/HCS/import 驗證通過。
- D720：P3-614 加固 notification delivery audit context partial sequence metadata 邊界：`context_json_from_outbox()` 先把 optional sequence metadata 交給 JSON-safe normalization，再做 empty collection filtering；`safe_sequence_items()` 只有在 native sequence fallback 有內容時才替換 partial stream，避免 native backing 為空的 list wrapper 抹掉已解析 `related_reports` evidence；RED→GREEN 單測、docs contract 與 focused audit/queue/docs/HCS/import 驗證通過。
- D721：P3-615 加固 shared mapping dict-subclass normalization 邊界：`safe_mapping_dict()` 對 dict subclass 改用 base `dict.items()` 建立 plain dict copy，避免自訂 mapping wrapper 外溢到 queue、repair 或 audit payload，同時避開覆寫失敗的 `items()`/`keys()`/`__iter__()` accessor；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D722：P3-616 加固 shared mapping general Mapping item traversal 邊界：`safe_mapping_dict()` 對非 dict 的 `Mapping` wrapper 改用 `safe_mapping_items()` 建立 plain dict copy，讓 `.items()` 可讀但 `keys()` 或 `__iter__()` 故障的 immutable/custom mapping 仍保留欄位；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D723：P3-617 加固 shared mapping safely-empty Mapping normalization 邊界：`safe_mapping_dict()` 在一般 `Mapping` 無 items 時，只有能安全確認 `len(value) == 0` 才回傳 plain `{}`，讓合法空 metadata wrapper 與 malformed mapping access failure 分流；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D724：P3-618 加固 shared mapping partial dict-subclass item fallback 邊界：`safe_mapping_items()` 在 dict subclass `.items()` 中途故障且 native backing 為空時保留已解析 partial items，避免空 fallback 抹掉 custom item wrapper 先前吐出的有效 metadata；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D725：P3-619 加固 shared mapping malformed string item pair 邊界：`safe_mapping_items()` 跳過 string-like item，避免兩字元字串被 Python 解包成 synthetic key/value 並污染 queue、repair 或 audit payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D726：P3-620 加固 shared mapping unhashable item key 邊界：`safe_mapping_items()` 跳過不可 hash 的 malformed item key，避免 list-like key 在 plain-dict normalization 時丟出 `TypeError` 並中斷 queue、repair 或 audit payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D727：P3-621 加固 shared integer boolean input 邊界：`safe_int()` 將 bool 視為 malformed numeric 並降級為 `0`，避免 `True` 被轉成 synthetic `1` count/limit/attempt 並污染 queue、repair、audit 或 observability payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D728：P3-622 加固 shared integer fractional float input 邊界：`safe_int()` 將非整數 float 視為 malformed numeric 並降級為 `0`，避免 `1.5` 被截斷成 synthetic `1` count/limit/attempt 並污染 queue、repair、audit 或 observability payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D729：P3-623 加固 shared integer fractional exact numeric input 邊界：`safe_int()` 將 fractional `Decimal` / `Fraction` 視為 malformed numeric 並降級為 `0`，避免 exact numeric payload 被截斷成 synthetic count/limit/attempt；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D730：P3-624 加固 shared text boolean input 邊界：`safe_text()` 將 bool 視為 malformed text 並降級為空字串，避免 `True` / `False` 被字串化後污染 queue、repair、audit 或 notification payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D731：P3-625 加固 shared text binary input 邊界：`safe_text()` 將 `bytes` / `bytearray` 視為 malformed text 並降級為空字串，避免 binary payload 被字串化成 Python byte-literal 後污染 queue、repair、audit 或 notification payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D732：P3-626 加固 shared text memory-view input 邊界：`safe_text()` 將 `memoryview` 視為 malformed text 並降級為空字串，避免 buffer-view payload 被字串化成不穩定 memory-address literal 後污染 queue、repair、audit 或 notification payload；RED→GREEN helper 單測、docs contract 與 focused shared-consumer 驗證通過。
- D733：P3-627 收斂 report quality repair queue identity text conversion：`report_quality_repair_queue._safe_text()` 委派 shared `safe_text()`，避免 repair item 的 ticker、filename、report_filename 或 pipeline_id 繞過 bool/binary/memory-view fail-closed 邊界；RED→GREEN repair queue 單測、docs contract 與 focused shared-consumer 驗證通過。
- D734：P3-628 收斂 provider impact identity text conversion：`provider_impact._safe_text()` 委派 shared `safe_text()`，避免 provider recovery ledger 的 ticker、filename、report_filename 或 pipeline_id 繞過 bool/binary/memory-view fail-closed 邊界；RED→GREEN provider impact 單測、docs contract 與 focused shared-consumer 驗證通過。
- D735：P3-629 收斂 data trust scoring audit source name conversion：`data_trust_scoring._safe_text()` 委派 shared `safe_text()`，避免 source audit 的 bool/binary/memory-view source keys 被投影成 synthetic optional-source error reason code；RED→GREEN data trust 單測、docs contract 與 focused shared-consumer 驗證通過。
- D736：P3-630 收斂 data trust reproducibility packet identity conversion：`report_reproducibility._safe_text()` 委派 shared `safe_text()`，避免 reproducibility packet 的 ticker、prompt version、pipeline id、code commit、generated time、model id、provider 或 source time 欄位繞過 bool/binary/memory-view fail-closed 邊界；RED→GREEN reproducibility 單測、docs contract 與 focused shared-consumer 驗證通過。
- D737：P3-631 收斂 prompt source audit summary text conversion：`prompt_source_audit._safe_text()` 委派 shared `safe_text()`，避免 prompt-facing source audit summary 的 source、provider、status 或 message 欄位繞過 bool/binary/memory-view fail-closed 邊界並污染 prompt JSON；RED→GREEN prompt source audit 單測、docs contract 與 focused prompt/data-trust 驗證通過。
- D738：P3-632 收斂 data trust snapshot identity text conversion：`data_trust_snapshot._safe_text()` 委派 shared `safe_text()`，並讓 snapshot pipeline identity 在 context 壞文字時 fallback 到 data `pipeline_id`，避免 `.data.json` 的 ticker、company_name 或 pipeline 欄位繞過 bool/binary/memory-view fail-closed 邊界；RED→GREEN snapshot identity 單測、docs contract 與 focused data-trust 驗證通過。
- D739：P3-633 收斂 data trust audit entry text conversion：`data_trust_audit._safe_text()` 委派 shared `safe_text()`，避免上游 source audit entry 的 source、provider、error_kind 或 message 欄位繞過 bool/binary/memory-view fail-closed 邊界並污染 data trust、prompt 或 snapshot 後續輸出；RED→GREEN source audit entry 單測、docs contract 與 focused data-trust 驗證通過。
- D740：P3-634 收斂 data trust provider SLA trust metadata text conversion：`data_trust_sla_policy._safe_text()` 委派 shared `safe_text()`，避免既有 trust `status`、`reason_codes` 或 `notes` 中的 bool/binary/memory-view 壞值在 provider SLA downgrade 時被保留成 synthetic report trust metadata；RED→GREEN provider SLA trust metadata 單測、docs contract 與 focused prompt/data-trust 驗證通過。
- D741：P3-635 收斂 report key evidence source field text conversion：`reporting.evidence` 在 source 分組、provider 去重、status 判斷與 fetched-at 輸出前使用 shared `safe_text()`，避免報告 HTML/Markdown 的關鍵數據來源對照表外溢 bool/binary/memory-view 壞文字；RED→GREEN report evidence 單測、docs contract 與 focused report/data-trust 驗證通過。
- D742：P3-636 收斂 report evidence matrix payload source field text conversion：`reporting.evidence_matrix` 在 tooltip JSON 的 source id、source label、provider/status/fetched-at/message 欄位輸出前使用 shared `safe_text()` 再做 plain-text sanitize，避免 `report-evidence-data` 外溢 bool/binary/memory-view 壞文字；RED→GREEN evidence matrix payload 單測、docs contract 與 focused report/data-trust 驗證通過。
- D743：P3-637 收斂 report evidence matrix limitation note text conversion：`reporting.evidence_matrix._as_notes()` 使用 shared `safe_text()` 後的 `_text(..., "")` 解析 `data_source_notes`，避免 HTML/Markdown/snapshot/tooltip 的資料限制說明外溢 bool/binary/memory-view 壞文字；RED→GREEN evidence matrix limitation 單測、docs contract 與 focused report/data-trust 驗證通過。
- D744：P3-638 收斂 report execution summary quality text conversion：`reporting.execution_summary._status()` 委派 shared `safe_text()`，避免 final audit、evidence gate、report conformance、report lint、prompt 或 model 欄位中的 bool/binary/memory-view 壞值外溢到 HTML/Markdown runtime trace；RED→GREEN execution summary 單測、docs contract 與 focused report/data-trust 驗證通過。
- D745：P3-639 收斂 report reading notice quality text conversion：`reporting.reading_notice` 以 shared `safe_text()` 正規化 data trust、evidence gate、content credibility 與 conformance 狀態，再決定品質 gate 狀態與 HTML/Markdown 判讀限制顯示，避免 bool/binary/memory-view 壞值外溢到使用前提示；RED→GREEN reading notice 單測、docs contract 與 focused report/data-trust 驗證通過。
- D746：P3-640 收斂 report source audit table text conversion：`reporting.audit_trust` 在來源審計 HTML/Markdown 表格輸出 source、provider、status、fetched-at 與 message 前使用 shared `safe_text()`，避免 legacy 或外部 snapshot 的 bool/binary/memory-view 壞值外溢到來源審計區塊；RED→GREEN source audit table 單測、docs contract 與 focused report/data-trust 驗證通過。
- D747：P3-641 收斂 report data trust summary text conversion：`reporting.audit_trust` 在資料可信度 HTML/Markdown 區塊輸出 status、notes、market timestamp、quant fallback fields 與 warning message 前使用 shared `safe_text()`，避免 legacy 或外部 snapshot 的 bool/binary/memory-view 壞值外溢到本報告資料可信度區塊；RED→GREEN data trust summary 單測、docs contract 與 focused report/data-trust 驗證通過。
- D748：P3-642 收斂 report audit banner abnormality text conversion：`reporting.audit_trust` 在報告頂部異常提醒 HTML/Markdown 區塊輸出 final audit critical/warning/correction、blocking issue 與 repair log 前使用 shared `safe_text()`，避免 bool/binary/memory-view 壞值外溢到仍需注意的異常、自動修復紀錄或非阻斷提醒；RED→GREEN audit banner 單測、docs contract 與 focused report/data-trust 驗證通過。
- D749：P3-643 收斂 report source evidence numeric/boolean display conversion：`reporting.audit_trust` 與 `reporting.evidence` 在來源審計與關鍵數據來源對照輸出 duration、record_count、cache_hit、stale 前使用安全數值與布林轉換，避免 malformed bool/binary/memory-view 壞值外溢成 Python literal 或被 truthy 誤顯示為「是」；RED→GREEN source evidence 單測、docs contract 與 focused report/data-trust 驗證通過。
- D750：P3-644 收斂 report mode template display text conversion：`reporting.mode_templates` 在 HTML/Markdown 報告模板與閱讀路徑卡輸出 template id/name、audience、core question、summary/decision heading、visual-focus chip 與 reading-path item 前使用 shared `safe_text()`，避免 malformed bool/binary/memory-view 壞值外溢到模板卡或章節標題；RED→GREEN mode template 單測、docs contract 與 focused report/template 驗證通過。
- D751：P3-645 收斂 report summary and decision discipline display text conversion：`reporting.sections`、HTML/Markdown renderer、`investment_thesis` 與 `company_display` 在摘要、決策清單、關鍵指標、公司顯示名與投資論文風控紀律段輸出前使用 shared `safe_text()`，避免 malformed ticker/company/recommendation/trade-setup/metric 值外溢成 bool/binary/memory-view Python literal；RED→GREEN mode report summary 單測、docs contract 與 focused report/template 驗證通過。
- D752：P3-646 收斂 report analysis overlay display text conversion：`reporting.analysis_overlays` 在管理層語氣、法說亮點、紅軍下行摘要/風險與同業 comparison name/ticker 送入 HTML template 前使用 shared `safe_text()`，並把 severity class 限縮到允許值，避免 malformed bool/binary/memory-view 壞值外溢到 management sentiment、downside risk 或 peer-comparison 區塊；RED→GREEN HTML overlay 單測、docs contract 與 focused overlay 驗證通過。
- D753：P3-647 收斂 report price target display and chart payload conversion：`reporting.html_renderer` 在 HTML price-target card 與 `report-chart-data.priceTargets` 輸出前把 target value 正規化為 finite number 或 `null`，並讓 `investment_thesis`/`investment_thesis_assumptions` 的估值情境文字使用 shared `safe_text()`，避免 malformed bool/binary/memory-view target 中斷 JSON render、外溢 Python literal 或把 `True` 誤顯示成 `NT$1`；RED→GREEN HTML price target 單測、docs contract 與 focused report 驗證通過。
- D754：P3-648 收斂 report chart payload series conversion：`reporting.html_renderer` 在 `report-chart-data` 輸出前把 year labels、money series、margin/ROE series、price history、moat scores 與 P/E river bands 正規化為 JSON-safe text 或 finite number/`null`，避免 malformed bool/binary/memory-view/non-finite 壞值中斷 chart script render 或外溢 Python literal；RED→GREEN HTML chart payload 單測、docs contract 與 focused report 驗證通過。
- D755：P3-649 收斂 report current price chart literal conversion：`reporting.html_renderer` 透過 `reporting.chart_payload.chart_number()` 正規化 inline `currentPrice` 與目標價 upside 計算用的 current price，避免 malformed bool/binary/memory-view/non-finite 現價輸出 `True`/`nan` 等無效 JavaScript literal，或把 boolean 誤當 NT$1 造成荒謬 upside 百分比；RED→GREEN HTML current-price 單測、docs contract 與 focused report 驗證通過。
- D756：P3-650 收斂 report recommendation banner display text conversion：`reporting.html_renderer` 在 verdict banner 與 final verdict block 輸出 3/6/12 個月目標、信心指數與建議文字前使用 shared `safe_text()` 再做 plain-text sanitize，避免 malformed bool/binary/memory-view recommendation 欄位外溢 `b'...'`、`bytearray(...)`、`<memory at ...>` 或 `True` 等 Python literal；RED→GREEN HTML recommendation banner 單測、docs contract 與 focused report 驗證通過。
- D757：P3-651 收斂 report executive synthesis display text conversion：`reporting.html_renderer` 在首頁「投資核心論點」與「總編輯整合觀點」輸出前使用 shared `safe_text()`，避免 malformed bool/binary/memory-view executive thesis 或 smoothed markdown 外溢 `b'...'`、`bytearray(...)` 等 Python literal 到報告開頭高可見區塊；RED→GREEN HTML editor synthesis 單測、docs contract 與 focused report 驗證通過。
- D758：P3-652 收斂 report cover metadata mapping conversion：`reporting.html_renderer` 在 report cover image URL 處理前使用 shared `safe_mapping_dict()` 正規化 `report_cover`，避免 malformed bool/binary/memory-view 或非 mapping cover payload 以 raw `.get()` 中斷整份 HTML 報告，並避免壞 cover metadata 外溢到 cover style；RED→GREEN HTML report cover metadata 單測、docs contract 與 focused report 驗證通過。
- D759：P3-653 收斂 report parsed payload mapping conversion：`reporting.html_renderer` 與 `reporting.sections` 在 HTML 報告 summary、structured intro、chart、verdict 與 trade setup 組裝前使用 shared `safe_mapping_dict()` 正規化 `parsed` 以及 `price_targets`、`recommendation`、`moat_scores`、`trade_setup` 子 payload，避免 malformed bool/binary/memory-view 或非 mapping parsed payload 以 raw `.get()` / `.items()` 中斷整份 HTML 報告或外溢 Python literal；RED→GREEN HTML parsed mapping 單測、docs contract 與 focused report 驗證通過。
- D760：P3-654 收斂 report data payload mapping conversion：`reporting.html_renderer` 與 `reporting.sections` 在 HTML 報告 summary、metrics、chart 與 tear-sheet 組裝前使用 shared `safe_mapping_dict()` 正規化 `data` 以及 `institutional_trading`、`pe_river_chart` 子 payload，避免 malformed bool/binary/memory-view 或非 mapping data snapshot payload 以 raw `dict(...)` / `.get()` 中斷整份 HTML 報告或外溢 Python literal；RED→GREEN HTML data mapping 單測、docs contract 與 focused report 驗證通過。
- D761：P3-655 收斂 report Markdown renderer payload mapping conversion：`reporting.markdown_renderer` 在 Markdown 報告 summary、metrics、verdict 與 trade setup 組裝前使用 shared `safe_mapping_dict()` 正規化 `data`、`parsed` 以及 `price_targets`、`recommendation`、`trade_setup` 子 payload，避免 malformed bool/binary/memory-view 或非 mapping payload 以 raw `.get()` / `.items()` 中斷 Markdown 報告或外溢 Python literal；RED→GREEN Markdown payload mapping 單測、docs contract 與 focused report 驗證通過。
- D762：P3-656 修正 report tear-sheet target price duplicate currency prefix：`reporting.sections` 在一頁式摘要輸出基本情境目標價前使用 `_target_price_text()` 判斷既有 `NT$` / `TWD` / `NTD` 幣別前綴，避免已格式化的目標價被渲染成 `NT$NT$120`，並更新 golden Markdown snapshot hash；RED→GREEN tear-sheet 幣別單測、docs contract、golden report 與 focused report 驗證通過。
- D763：P3-657 收斂 report agent output map conversion：`reporting.sections` 與 `reporting.html_renderer` 在 HTML/Markdown agent sections、structured tail block 與 next catalysts 收集前使用 shared `safe_mapping_dict()` 正規化 `analyses` 與 `structured_outputs`，避免 malformed bool/binary/memory-view 或非 mapping agent output payload 以 raw `.get()` / `.values()` 中斷整份報告正文或外溢 Python literal；RED→GREEN agent output map 單測、docs contract 與 focused report 驗證通過。
- D764：P3-658 收斂 report agent output string-key id lookup：`reporting.sections` 在 HTML/Markdown agent section 與 structured tail block 取值時同時支援整數與字串 agent id，避免 JSON-loaded `analyses` / `structured_outputs` 已有有效報告卻因 key 型別不同靜默落回 `分析進行中`；RED→GREEN string-key agent payload 單測、docs contract 與 focused report 驗證通過。
- D765：P3-659 收斂 report agent sequence string id normalization：`reporting.sections` 在 HTML/Markdown agent section rendering 前將 JSON-loaded `agent_sequence` 字串 id 正規化為整數，避免章節標題、model label 與 v3 structured tail placement 因 key 型別漂移退化成 generic `Agent 17` 或漏接結構化結論；RED→GREEN string agent sequence 單測、docs contract 與 focused report 驗證通過。
- D766：P3-660 收斂 report malformed agent sequence scalar fallback：`reporting.sections` 與 `reporting.execution_summary` 在 HTML/Markdown section 與執行邏輯摘要產生前，將 bytes/binary 等非 list/tuple `agent_sequence` 視為 malformed 並回落到 pipeline 預設序列，避免報告出現 byte-derived `Agent 98` 假章節或假執行序列；RED→GREEN malformed agent sequence 單測、docs contract 與 focused report 驗證通過。
- D767：P3-661 收斂 report analysis overlay structured-output map conversion：`reporting.analysis_overlays` 在管理層語氣與下行風險 overlay 取 structured agent payload 前使用 shared `safe_mapping_dict()` 正規化 `structured_outputs` 與個別 agent payload，避免 JSON-loaded dict subclass accessor failure 中斷整份 HTML 報告或抹掉有效 overlay evidence；RED→GREEN overlay structured-output map 單測、docs contract 與 focused report 驗證通過。
- D768：P3-662 收斂 report analysis overlay data child map conversion：`reporting.analysis_overlays` 在 DCF 情境矩陣與同業比較 overlay 讀取 `quant_metrics`、deterministic tool results、DCF scenario child maps 與 `dynamic_peer_metrics` rows 前使用 shared mapping/list conversion，避免 JSON-loaded child map accessor failure 中斷 HTML overlay 或抹掉有效 DCF/peer evidence；RED→GREEN overlay data child map 單測、docs contract 與 focused report 驗證通過。
- D769：P3-663 收斂 report key evidence source audit child map conversion：`reporting.evidence` 在產生 key data evidence rows 前使用 shared mapping/list conversion 正規化 data 與 `source_audit` rows，避免 JSON-loaded audit row accessor failure 中斷 HTML/Markdown 關鍵數據來源對照，並保留有效 provider、status 與 record_count evidence；RED→GREEN key evidence source audit child map 單測、docs contract 與 focused report 驗證通過。
- D770：P3-664 收斂 report source audit table child map conversion：`reporting.audit_trust` 在 HTML/Markdown 來源審計表渲染前共用 source audit mapping/list conversion，避免 JSON-loaded audit row accessor failure 中斷來源審計區塊，並保留有效 provider、fetched_at 與 message evidence；RED→GREEN source audit table child map 單測、docs contract 與 focused report 驗證通過。
- D771：P3-665 收斂 report evidence matrix source audit child map conversion：`reporting.evidence_matrix` 在 tooltip JSON payload 產生前使用 shared mapping/list conversion 正規化 context/data/source audit rows，避免 JSON-loaded audit row accessor failure 中斷 `report-evidence-data`，並保留有效 provider/status/fetched_at/message evidence；RED→GREEN evidence matrix source audit child map 單測、docs contract 與 focused report 驗證通過。
- D772：P3-666 收斂 report data trust quant metrics child map conversion：`reporting.audit_trust` 在 HTML/Markdown data trust card 產生前使用 shared mapping conversion 正規化 data 與 `quant_metrics` child map，避免 JSON-loaded quant metric accessor failure 中斷量化模型 fallback warning，並保留有效 fallback warning text；RED→GREEN data trust quant metrics child map 單測、docs contract 與 focused report 驗證通過。
- D773：P3-667 收斂 report audit banner final-audit child map conversion：`reporting.audit_trust` 在 HTML/Markdown top-of-report abnormality banner 產生前使用 shared mapping conversion 正規化 context 與 `final_audit` child map，避免 JSON-loaded final audit accessor failure 中斷異常提醒、非阻斷提醒與校正紀錄 evidence；RED→GREEN audit banner final-audit child map 單測、docs contract 與 focused report 驗證通過。
- D774：P3-668 收斂 report audit banner abnormality list conversion：`reporting.audit_trust` 在 HTML/Markdown top-of-report abnormality banner 輸出前使用 shared list-safe conversion 讀取 `critical`、`warnings`、`corrections`、`blocking_issues` 與 `audit_repair_log`，避免 bytes/bytearray/memoryview scalar 被逐位渲染成 `98` 等假異常提醒；RED→GREEN audit banner malformed scalar list 單測、docs contract 與 focused report 驗證通過。
- D775：P3-669 補強 report trust controls mapping guard：`reporting.trust_controls` 在 HTML/Markdown data confidence controls 輸出前正規化 data 與 context maps，避免 malformed `data_trust` 或 context data accessors 中斷信心分數、目標價 guardrail 與可重現資訊；RED→GREEN trust controls malformed data map 單測與 data-trust focused 驗證通過。
- D776：P3-670 收斂 data trust normalized notes conversion：`data_trust_scoring.normalize_data_trust()` 將 `notes` 對齊既有 `string_list()` conversion，避免 tuple notes 被清空而抹掉有效報告限制脈絡，並丟棄 binary 類壞值；RED→GREEN normalize notes tuple 單測與 data-trust focused 驗證通過。
- D777：P3-671 補強 data trust string-list native fallback：`data_trust_audit.string_list()` 將 list/tuple conversion 委派給 shared `safe_text_list()`，避免 malformed custom iterators 中斷 trust normalization 或抹掉有效 notes、reason codes、stale sources、critical failures 與 score reasons；RED→GREEN normalize text-list native fallback 單測與 data-trust focused 驗證通過。
- D778：P3-672 補強 data trust source record count sequence fallback：`data_trust_audit.list_count()` 改用 shared `safe_sequence_items()` 計算 history/enrichment row counts，避免 malformed custom iterators 中斷 merged evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN source record count native fallback 單測與 data-trust focused 驗證通過。
- D779：P3-673 補強 data trust source record count value presence guard：`data_trust_audit.has_value()` 對 list/dict payload 使用 shared sequence/mapping safe helpers 判斷 presence，避免 malformed truthiness 中斷 merged evidence count 或隱藏有效 market/financial/enrichment evidence；RED→GREEN source record count value-presence 單測與 data-trust focused 驗證通過。
- D780：P3-674 補強 data trust source record count tuple source rows：`data_trust_audit.source_record_count()` 在 default source fallback 中將 tuple source values 視為 row batches，避免 immutable custom enrichment rows 被壓成單一 present scalar 而低估 merged evidence count；RED→GREEN source record count tuple source 單測與 data-trust focused 驗證通過。
- D781：P3-675 補強 data trust source record count root data mapping guard：`data_trust_audit.source_record_count()` 在讀取欄位前使用 shared `safe_mapping_dict()` 正規化 root data map，避免 malformed data snapshot accessor 中斷 merged evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN source record count root data map 單測與 data-trust focused 驗證通過。
- D782：P3-676 補強 data trust source record count institutional trading mapping guard：`data_trust_audit.source_record_count()` 在讀取 institutional trading nested 欄位前使用 shared `safe_mapping_dict()` 正規化 payload，避免 malformed nested accessor 中斷 merged evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN institutional trading source count 單測與 data-trust focused 驗證通過。
- D783：P3-677 補強 data trust source record count global market context mapping guard：`data_trust_audit.source_record_count()` 在讀取 global market context nested `items` 前使用 shared `safe_mapping_dict()` 正規化 payload，避免 malformed nested accessor 中斷 merged evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN global market context source count 單測與 data-trust focused 驗證通過。
- D784：P3-678 補強 data trust source record count international news context mapping guard：`data_trust_audit.source_record_count()` 在讀取 international news context nested `topics` 前使用 shared `safe_mapping_dict()` 正規化 payload，避免 malformed nested accessor 中斷 merged evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN international news context source count 單測與 data-trust focused 驗證通過。
- D785：P3-679 補強 data trust source record count P/E river chart mapping guard：`data_trust_audit.source_record_count()` 在讀取 P/E river chart nested 欄位前使用 shared `safe_mapping_dict()` 正規化 payload，避免 malformed nested accessor 中斷 merged valuation evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN P/E river chart source count 單測與 data-trust focused 驗證通過。
- D786：P3-680 補強 data trust source record count default mapping value guard：`data_trust_audit.source_record_count()` 在 default source fallback 計算 mapping source value key count 前使用 shared `safe_mapping_dict()` 正規化 payload，避免 malformed mapping length accessor 中斷 custom source merged evidence count、prompt source audit 或 source-audit record count 證據；RED→GREEN default mapping source count 單測與 data-trust focused 驗證通過。
- D787：P3-681 補強 data trust source record count tuple value presence guard：`data_trust_audit.has_value()` 對 tuple payload 使用 shared `safe_sequence_items()` 判斷 presence，避免空 tuple history/enrichment payload 被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN tuple value-presence 單測與 data-trust focused 驗證通過。
- D788：P3-682 補強 data trust source record count immutable mapping value presence guard：`data_trust_audit.has_value()` 對一般 `Mapping` payload 使用 shared `safe_mapping_dict()` 判斷 presence，避免空 immutable mapping history/enrichment payload 被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN immutable mapping value-presence 單測與 data-trust focused 驗證通過。
- D789：P3-683 補強 data trust source record count P/E river chart band mapping guard：`data_trust_audit.source_record_count()` 在計算 P/E river chart `bands` valuation rows 前使用 shared `safe_mapping_dict()` 正規化 band payload，避免 immutable band map 被誤判為沒有 valuation evidence 而低估 merged evidence count；RED→GREEN P/E river band mapping 單測與 data-trust focused 驗證通過。
- D790：P3-684 補強 data trust source record count P/E river chart empty-band fallback：`data_trust_audit.source_record_count()` 只在 P/E river chart `bands` 產生正數 valuation row count 時採用 band evidence，否則回落到 `years` / `eps_twd` row count，避免 sparse band payload 抹掉仍有效的估值來源證據；RED→GREEN P/E river empty-band fallback 單測與 data-trust focused 驗證通過。
- D791：P3-685 補強 data trust source record count institutional trading empty-daily guard：`data_trust_audit.source_record_count()` 在法人籌碼 daily rows 為空時，只用其他非 daily 欄位的實際 value presence 做 fallback，避免只有空 `daily_total_net_buy_last_10` 的 shell payload 被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN institutional empty-daily 單測與 data-trust focused 驗證通過。
- D792：P3-686 補強 data trust source record count sequence item-value presence guard：`data_trust_audit.has_value()` 對 list/tuple payload 改為檢查至少一個 item 真的有 value，避免非空但全由 `None`、空字串或 `N/A` 組成的 history/enrichment sequence 被誤算成有效 source evidence；RED→GREEN sequence item-value 單測與 data-trust focused 驗證通過。
- D793：P3-687 補強 data trust source record count mapping child-value presence guard：`data_trust_audit.has_value()` 對 mapping payload 改為檢查至少一個 child value 真的有 value，避免非空但 child values 全為空序列、空字串或 missing 值的 history/enrichment mapping 被誤算成有效 source evidence；RED→GREEN mapping child-value 單測與 data-trust focused 驗證通過。
- D794：P3-688 補強 data trust source record count default mapping child-value count：`data_trust_audit.source_record_count()` 在 default/custom source mapping fallback 中只計算 child value present 的 keys，避免 custom mapping payload 只有空值 key 時被 key count 誤算成有效 source evidence；RED→GREEN default mapping child-value 單測與 data-trust focused 驗證通過。

## 未解問題

- CI runner 仍需在 image/setup step 安裝 Chromium；目前已用 manifest 鎖住 Playwright 對應的 browser revision/version、cache marker 與啟動版本，但大型 browser binary 尚未納入 repository hash-lock，正式 CI gate 仍不自動把 artifact 提交進版本庫。
- 後端 runtime catalog 與前端首屏 fallback 已分別由 `pipeline_mode_catalog.py` 和 generated `pipeline_mode_fallback.js` 提供，CI 會檢查兩者是否漂移；新增模式仍需維護 schema version、生成 artifact 與前端 runtime 相容性。
- 2026-07-08 新一輪 HCS Plus 系統優化已完成 P0/P1/P2 主要工程票；尚未宣稱新一輪嚴格單項三輪巡迴完成。
- 漏洞掃描目前已在隔離 `.audit-venv` 實際執行；若 CI image 未執行 `scripts/setup_security_audit.sh`，gate 會 fail-closed，只有明確 `SUPPLY_CHAIN_SKIP_PIP_AUDIT=1` 才允許受控例外。

## 第 2 輪批判思考問題雷達

| 問題 | 關鍵問題 | 差距 | 驗證證據 |
|---|---|---|---|
| 報告正文契約 vs 前端顯示層 | 哪些使用者入口需要降權威語氣，哪些後端契約必須保留 `投資建議` 以維持解析？ | 前端已改為「報告建議 / 報告結論」，但報告正文、prompt、conformance 測試仍使用「投資建議」契約詞。 | `tests/test_static_history_filters.py` 驗證前端語氣；後端契約需由下一批變數/偏誤分析盤點。 |
| 完整報告正文權威感 | 是否要調整完整報告標題，或只在瀏覽入口標示報告層級？ | 已在 HTML/Markdown 正文頂部加入用途、品質 gate 狀態與採用前限制；仍不替換 `最終投資建議` 等機器契約詞。 | `tests/test_report_reading_notice.py`、`tests/test_report_data_trust.py`、`tests/test_report_conformance.py`；250 件高顯著性報告契約測試。 |
| 契約詞替換風險 | 哪些測試或 parser 依賴 `[投資建議]` / `最終投資建議`？ | 尚未有集中清單說明哪些詞是可顯示替換、哪些詞是機器契約。 | 下一批需建立變數表與偏誤護欄。 |

## 第 2 輪批判思考變數與偏誤護欄

| 層級 | 變數 | 偏誤風險 | 護欄 |
|---|---|---|---|
| 可改名顯示層 | History filter、preview title、preview metric label、rerun CTA、compare result label | 過度保守契約偏誤：因後端契約保留舊詞，就拒絕改善使用者入口語氣。 | 前端契約測試需鎖住「報告建議 / 報告結論」等使用者入口語氣。 |
| 需保留契約層 | `[投資建議]` 區塊、`最終投資建議` report template、conformance parser、legacy fixtures | 字串潔癖偏誤：為了表面一致而破壞 parser、prompt 或 conformance 測試。 | 任何替換前必須先跑解析契約回歸，並列出依賴該契約詞的測試。 |
| 待決策混合層 | 完整報告正文標題、Markdown/HTML 報告對使用者呈現的標題 | 錯誤等同：把給模型/解析器看的契約詞等同於給使用者看的 UI 文案。 | 下一批用決策樹判斷：保留、加註報告層級、或拆分機器契約與顯示文案。 |

## 第 2 輪批判思考契約詞決策樹

| 分支 | 判斷條件 | 決策 | 最高效用路徑 |
|---|---|---|---|
| 使用者顯示層 | UI label、filter、preview、compare、rerun CTA，且不被 parser 讀取。 | 使用「報告建議 / 報告結論」等報告層級語氣。 | 繼續由前端契約測試鎖住，避免回到交易指令語氣。 |
| 機器解析契約 | prompt 區塊、`[投資建議]`、conformance parser、legacy fixtures 或報告抽取測試依賴。 | 預設保留契約詞，除非同時改 parser、prompt 與 fixture。 | 先建立解析契約 coverage map，再評估是否值得拆分機器契約與顯示文案。 |
| 完整報告正文 | 使用者會閱讀，但也可能被 parser、lint 或報告模板測試依賴。 | 暫不直接替換；先判斷它屬於顯示層、契約層或混合層。 | 最高效用路徑是先補 coverage map，再決定保留、加註報告層級，或拆分顯示詞。 |

## 第 2 輪批判思考契約覆蓋統計

- 統計範圍：`tests/` 與 `backend/` 中的 `.py`、`.json`、`.j2`、`.md`、`.html`、`.js` 來源檔。
- 排除範圍：`backend/output/`、`__pycache__`、`.pytest_cache` 等生成或快取產物。
- 測試檔案數：24。
- 後端檔案數：26。
- 信賴區間：最低可觀測樣本；它能證明契約詞依賴面不小，但不能代表所有 runtime 輸出母體。
- 相關性提醒：相關不等於可替換。檔案含「投資建議」可能是在排除舊 UI 語氣，也可能是 parser/prompt 契約。
- 描述統計用途：未來若這兩個檔案數改變，`tests/test_hcs_plus_state.py` 會要求同步更新本狀態表。

## 第 2 輪批判思考契約回歸風險排序

| 風險等級 | 觸發條件 | 回歸測試組 | 顯著性門檻 |
|---|---|---|---|
| 高機率回歸 | 改 `[投資建議]`、`[/投資建議]`、`最終投資建議`、report template decision heading 或 parser regex。 | `tests/test_report_preview.py`、`tests/test_report_conformance.py`、`tests/test_audit_rules.py`、`tests/test_prompt_context_routing.py` | 任一機器契約詞或 template heading 變動，都算高顯著性。 |
| 中機率回歸 | 改完整報告正文標題、HTML/Markdown template 顯示文案，但不改 parser。 | `tests/test_report_mode_templates.py`、`tests/test_report_storage_integration.py`、`tests/test_frontend_http_e2e.py` | 若使用者會直接閱讀且 report lint/conformance 會掃描，需跑報告渲染與儲存測試。 |
| 低機率回歸 | 只改前端 filter、preview、compare、rerun CTA 等顯示層。 | `tests/test_static_history_filters.py`、`tests/test_frontend_visual_optional.py` | 只要不碰 parser/template，可用前端契約測試作為主要門檻。 |

## 第 2 輪批判思考契約測試矩陣

矩陣用途：把 coverage map 與風險排序轉成改檔前的最小驗證清單。此矩陣不是保證完整正確，而是要求每個契約詞改動先說清楚證據基礎、演繹規則與歸納限制。

| 改動類型 | 證據基礎 | 演繹規則 | 歸納限制 | 必跑測試 |
|---|---|---|---|---|
| 高顯著性改動：改 `[投資建議]`、`[/投資建議]`、`最終投資建議`、prompt 契約、parser regex 或 report template decision heading。 | coverage map 顯示契約詞分布於 23 個測試檔與 25 個後端來源檔；風險排序已標記 parser、conformance、audit 與 prompt routing 為高機率回歸面。 | 只要碰到機器契約詞，就演繹為 parser/prompt/template 合約變更；必須同時驗證抽取、格式合規、稽核規則與 prompt context routing。 | 現有矩陣只能覆蓋可維護來源與代表性測試，不代表所有生成報告與真實 LLM 輸出。 | `tests/test_report_preview.py`、`tests/test_report_conformance.py`、`tests/test_audit_rules.py`、`tests/test_prompt_context_routing.py` |
| 混合層正文或模板顯示改動：改完整報告 Markdown/HTML 標題、template 顯示文案或使用者會閱讀且 conformance 可能掃描的段落。 | 風險排序把完整報告正文列為中機率回歸，因它同時是閱讀介面與測試/儲存管線的一部分。 | 若文案仍可能被 report lint、storage 或 HTTP preview 流程讀取，就演繹為報告渲染與儲存合約變更。 | 混合層測試通過只證明現有模板與儲存路徑未破，不證明使用者會降低權威感。 | `tests/test_report_mode_templates.py`、`tests/test_report_storage_integration.py`、`tests/test_frontend_http_e2e.py` |
| 低顯著性顯示層改動：只改 filter、preview、compare、rerun CTA 等前端 label，且不碰 parser/template。 | 第 1 輪互動思考已把前端顯示層降權威語氣鎖到 static 與 optional visual tests。 | 若改動不被 parser 讀取，就演繹為使用者顯示契約；優先驗證文字契約與可視化 fixture。 | 前端測試不能證明後端報告正文安全，也不能用來支持機器契約詞替換。 | `tests/test_static_history_filters.py`、`tests/test_frontend_visual_optional.py` |

## 第 2 輪批判思考契約矩陣反謬誤護欄

本護欄限制契約測試矩陣的推論範圍。矩陣能幫操作者決定改檔前該跑哪些測試，但不能把測試通過擴張成投資語意、全量輸出或使用者解讀都安全。

| 易犯謬誤 | 錯誤推論 | 來源品質分級 | 情境脈絡護欄 |
|---|---|---|---|
| 測試通過不等於語意安全 | `tests/test_report_preview.py` 或 conformance 綠燈，不代表報告文案已降低權威感，也不代表使用者不會把報告當成交易指令。 | 高品質來源：可重跑測試、parser/template source、report conformance 規則。次級來源：文件狀態表、人工閱讀摘要。不得作為完成證據：單次生成報告、未重跑截圖、未標來源的口頭判斷。 | 機器契約變更要先證明 parser/prompt/template 未回退；使用者顯示層改動另需檢查「報告建議 / 報告結論」語氣是否維持。 |
| coverage map 不等於完整母體 | `tests/` 23 檔與 `backend/` 25 檔只代表可維護來源，不代表 `backend/output/`、歷史報告或未來 LLM 輸出都被覆蓋。 | 高品質來源：可維護 source tree 與 pytest 結果。次級來源：生成輸出抽樣。不得作為完成證據：把檔案數當成 runtime 母體大小。 | 若要改完整報告正文，需把情境限定為目前模板與儲存/preview 流程；不能聲稱所有舊報告同步改善。 |
| frontend tests 不等於 parser/prompt safety | `tests/test_static_history_filters.py` 通過，只能證明前端顯示層契約；不能支持 `[投資建議]`、prompt 或 parser regex 替換。 | 高品質來源：parser、prompt routing、audit 與 conformance 測試。次級來源：前端 static/visual tests。不得作為完成證據：只看 UI 文案就判定後端契約安全。 | 使用者顯示層改動可以走前端測試；機器契約變更必須走高顯著性測試矩陣。 |

## 第 2 輪批判思考契約矩陣可執行性評估

批判結論：目前矩陣過重風險在於讀者需要先理解三張表，才知道要跑哪一組測試；但直接做自動選測腳本又可能把仍需人工判斷的契約層級包成假自動化。因此本階段採最小命令分組，先降低執行摩擦，不新增測試架構。

| 改動情境 | 矩陣過重風險 | estimated scope | 最小命令分組 | 詮釋框架 |
|---|---|---|---|---|
| 高顯著性機器契約變更 | 若每次都跑完整前端與報告矩陣，成本高且容易讓操作者跳過。 | 4 個測試檔；涵蓋 preview、conformance、audit、prompt routing。 | `$(scripts/project_python.sh) -m pytest tests/test_report_preview.py tests/test_report_conformance.py tests/test_audit_rules.py tests/test_prompt_context_routing.py -q` | 綠燈代表核心機器契約未被已知測試打破；紅燈代表不可合併契約詞變更；不得解讀為所有生成報告語意安全。 |
| 混合層正文或模板顯示改動 | 若只照高顯著性矩陣跑，會漏掉儲存與 HTTP preview；若全跑，回饋太慢。 | 3 個測試檔；涵蓋 mode template、report storage、HTTP preview。 | `$(scripts/project_python.sh) -m pytest tests/test_report_mode_templates.py tests/test_report_storage_integration.py tests/test_frontend_http_e2e.py -q` | 綠燈代表目前模板/儲存/preview 路徑未回退；紅燈代表報告呈現或保存契約受影響；不得解讀為使用者已正確理解降權威語氣。 |
| 低顯著性使用者顯示層改動 | 若要求 parser/prompt 全矩陣，會阻礙低風險 UI 語氣改善。 | 2 個測試檔；涵蓋 static label 與 optional visual fixture。 | `$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py tests/test_frontend_visual_optional.py -q` | 綠燈代表顯示層文字契約未回退；紅燈代表前端入口可能回到交易指令語氣；不得解讀為 parser/prompt safety。 |

## 第 2 輪批判思考收尾檢查

- 第 2 輪批判思考完成：26/26。
- 合理性結論：本輪沒有直接替換後端 `投資建議` 契約詞，而是先完成問題雷達、變數護欄、決策樹、coverage map、風險排序、契約測試矩陣、反謬誤護欄與最小命令分組；這比立即改正文更合理，因為它保留 parser/prompt/template 安全邊界。
- 合理性取捨：暫不新增自動選測腳本，避免把仍需人工判斷的改動層級包成假自動化；先保留最小命令分組作為可執行中間型態。
- 可重跑驗證：`tests/test_hcs_plus_state.py` 鎖住 26/26 收尾、狀態表 checkpoint 與嚴格附件；`tests/test_docs_contract.py`、`tests/test_static_history_filters.py`、`tests/test_frontend_visual_optional.py` 作為本批文件/前端契約的相關回歸。
- 下一分類入口：第 2 輪創意思考將從 `#學習科學/#限制條件/#類比` 開始，把契約矩陣從「可驗證」推向「更容易被操作者學會與採用」。

## 第 2 輪創意思考契約矩陣速學卡設計

契約矩陣速學卡把前一批的測試矩陣壓成「先問三題、再走三道安檢通道」：先判斷改動層級，再複製對應的最小測試命令。這次只改文件契約，不新增自動選測腳本，讓操作者仍保留對改動層級的人工判斷。

| 思考習慣 | 核心設計 | 落地位置 | 限制條件 |
|---|---|---|---|
| 學習科學 | 把抽象矩陣改成先問三題，降低第一次使用時的記憶負擔。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣速學卡`。 | 只教判斷順序，不取代測試矩陣與人工審查。 |
| 限制條件 | 保留「不新增自動選測腳本」的邊界，避免把仍需人工判斷的契約層級假裝成全自動。 | 速學卡說明與主狀態表 D48。 | 不改 runtime、不新增腳本、不碰 parser/prompt/template。 |
| 類比 | 用三道安檢通道類比高顯著性機器契約、混合層報告呈現、低顯著性顯示層三種路徑。 | `docs/pipeline-mode-contract.md` 的三通道表格。 | 類比只用來分流測試，不保證語意安全或完整母體覆蓋。 |

速學卡目前對應三個通道：`高顯著性機器契約通道`、`混合層報告呈現通道`、`低顯著性顯示層通道`。後續第 2 輪創意思考可再檢查是否需要把這張卡轉成更清楚的演算法流程、設計情境或捷思法，但目前先維持文件型態。

## 第 2 輪創意思考契約矩陣操作流程設計

本批把速學卡從「知道三道通道」推進到「照流程完成一次改檔前判斷」。操作流程仍是文件契約，不新增自動選測腳本，避免把人工責任藏進工具。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 演算法 | 把契約判斷寫成四步演算法：定位改動層級、選擇安檢通道、執行最小測試命令、記錄判讀與限制。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣操作流程`。 | 流程只協助選測，不自動判定語意安全。 |
| 設計思考 | 用三個操作者情境對應實際改檔工作：parser/prompt/decision heading、完整報告模板或正文標題、前端顯示文案。 | 操作流程中的 `三個操作者情境` 表格。 | 情境設計只覆蓋目前最常見契約改動，不代表所有未來工作流。 |
| 捷思法 | 用三條捷思規則把第一次判斷壓到可快速掃讀：括號契約詞走高顯著性、報告正文走混合層、純前端顯示才走低顯著性。 | 操作流程中的 `三條捷思規則`。 | 捷思規則是初篩；跨層改動仍要跑多組測試。 |

下一批可從最佳化、假說發展與資料視覺化檢查：這個流程是否能更快讓操作者選到正確測試、是否需要對照錯選案例，以及是否要把矩陣呈現成更可掃讀的資料視覺化。

## 第 2 輪創意思考契約矩陣採用觀測設計

本批把操作流程從「可照著做」推進到「可觀察是否真的有幫助」。觀測板仍是文件契約，不新增遙測或自動化蒐集；它只定義人工 review 時該看哪些訊號。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 最佳化 | 把採用目標收斂為降低錯選測試命令、減少跨層改動漏跑測試、保留人工判斷責任。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣採用觀測板`。 | 只最佳化選測流程，不保證所有報告語意安全。 |
| 假說發展 | 建立三個可觀察假說：四步流程降低第一次選測摩擦、三個情境降低錯選通道、三條捷思規則減少低顯著性誤用。 | 觀測板中的 `可觀察假說` 表格。 | 假說需要未來實際變更紀錄驗證，目前先定義觀察指標。 |
| 資料視覺化 | 用綠色、黃色、紅色三欄呈現通道選擇、測試判讀與後續行動的採用訊號。 | 觀測板中的 `採用訊號矩陣`。 | 表格是人工 review 輔助，不新增 dashboard 或遙測。 |

下一批可從建模、抽樣與個案研究處理：如何把高顯著性、混合層、低顯著性通道建成案例模型，並選出代表性變更案例作為後續文件或測試樣本。

## 第 2 輪創意思考契約矩陣案例模型設計

本批把採用觀測板轉成可對照的案例模型。模型與案例卡仍是文件契約，不新增工具或資料蒐集；它們提供後續 review 可引用的人工樣本格式。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 建模 | 建立三類案例模型：高顯著性機器契約、混合層報告呈現、低顯著性顯示層。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣案例模型`。 | 模型只覆蓋目前契約矩陣的三條主通道，未涵蓋所有未來資料流。 |
| 抽樣 | 定義代表性抽樣規則：每次契約變更至少對照一個模型，跨層改動同時抽樣兩個模型，不以單一綠燈代表未來所有改動。 | `代表性抽樣規則`。 | 抽樣規則是人工 review 標準，不是統計顯著性證明。 |
| 個案研究 | 建立案例卡格式，要求記錄改動描述、選擇通道、必跑命令與採用訊號。 | `案例卡格式`。 | 案例卡證明當次改動有被檢查，不證明所有歷史報告同步安全。 |

下一批可從比較組、介入研究與訪談調查處理：比較使用案例模型前後是否更少錯選通道，並蒐集操作者在改檔前是否能快速選出測試組。

## 第 2 輪創意思考契約矩陣比較與回饋設計

本批把案例模型從「可填寫」推進到「可比較、可介入、可收回饋」。此設計仍是文件契約，不新增產品遙測或自動化蒐集。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 比較組 | 建立基準組與介入組：基準組只用速學卡/操作流程，介入組加上案例模型與案例卡。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣比較與回饋設計`。 | 比較組是 review 方法，不是統計實驗。 |
| 介入研究 | 介入方案要求改檔前先填案例卡，跨層改動強制列出兩個模型與兩組命令。 | `介入方案`。 | 介入只降低漏跑風險，不取代測試結果。 |
| 訪談調查 | 設計三個訪談回饋題，檢查操作者是否能在 2 分鐘內選通道、哪條規則讓人猶豫、案例卡是否發現漏跑或判讀限制。 | `訪談回饋題`。 | 訪談回覆是輔助證據，不得替代 pytest 或契約測試。 |

下一批可從觀察研究與研究複製處理：如何觀察實際契約變更案例，並讓同一套案例模型/比較流程能被下一位操作者重複使用。

## 第 2 輪創意思考契約矩陣觀察複製設計

本批把比較與回饋設計收斂成可觀察、可複製的文件準則。它仍不新增產品遙測或自動化蒐集；觀察紀錄只輔助 review，不替代測試。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 觀察研究 | 定義觀察記錄欄位：變更案例、實際選擇通道、實際執行命令、觀察結果。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣觀察與複製準則`。 | 觀察紀錄是人工 review 輔助，不是產品遙測。 |
| 研究複製 | 定義複製檢查清單：同一案例模型、同一必跑命令、同一判讀限制。 | `複製檢查清單` 與 `可複製完成條件`。 | 複製完成不代表所有未來 LLM 輸出安全，仍需對應測試。 |

## 第 2 輪創意思考收尾檢查

- 第 2 輪創意思考完成：17/17。
- 收尾結論：本輪把第 2 輪批判思考產出的契約矩陣，逐步轉成速學卡、操作流程、採用觀測板、案例模型、比較與回饋設計，以及觀察複製準則。
- 合理性取捨：本輪仍不新增自動選測腳本或產品遙測，因為契約層級判斷、案例模型與訪談回饋仍需要人工 review；文件契約先確保流程可學、可比較、可複製。
- 可重跑驗證：`tests/test_docs_contract.py` 鎖住模式契約內容；`tests/test_hcs_plus_state.py` 鎖住 HCS 單項紀錄、進度與收尾；`tests/test_static_history_filters.py`、`tests/test_frontend_visual_optional.py` 繼續保護前端顯示層語氣。
- 下一分類入口：第 2 輪溝通思考將從 `#受眾/#組成/#語意含義` 開始，把契約矩陣文件從流程完整推向對操作者更清楚、更少歧義。

## 第 2 輪溝通思考契約矩陣讀者路徑設計

本批把創意思考累積的速學卡、操作流程、案例模型與觀察準則，改寫成不同維護者可以直接使用的讀者路徑。重點不是新增工具，而是降低操作者讀錯層級、讀漏限制或把文件誤解成自動化保證的風險。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 受眾 | 將契約矩陣分成一般改文案者、報告模板維護者、parser/prompt 維護者三種受眾，讓不同角色先看到自己最容易誤用的通道。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣讀者路徑`。 | 受眾分流只改善閱讀入口，不自動判定改動層級。 |
| 組成 | 建立閱讀順序：先讀速學卡、再用操作流程、最後填案例卡，讓操作者從判斷、執行到紀錄逐步完成。 | 讀者路徑中的 `閱讀順序`。 | 組成順序不取代原有測試矩陣與必跑命令。 |
| 語意含義 | 明確寫出文件契約不是自動化保證、觀察紀錄不是測試替代品、低顯著性不代表低責任。 | 讀者路徑中的 `語意邊界`。 | 語意邊界只限制文件推論範圍，仍需實際測試綠燈。 |

下一批可從組織結構、專業性與論點處理：檢查整份契約文件的章節排序是否讓讀者先看決策入口，再看案例與模式對照；同時把核心主張收斂成更專業、可引用的維護規範。

## 第 2 輪溝通思考契約矩陣維護導覽設計

本批把讀者路徑再收斂成可引用的維護導覽，避免操作者只看到多張表，卻不知道整份契約文件該如何使用。設計重點是先讓維護者知道章節順序，再用專業語氣限制測試推論，最後把核心論點寫成可複製的維護規範。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 組織結構 | 建立章節導覽：先判斷改動層級、再選案例模型、最後確認模式對照。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣維護導覽`。 | 章節導覽只改善文件使用順序，不改變原本測試矩陣。 |
| 專業性 | 補上專業維護語氣，要求測試綠燈只說明已知契約未回退，不宣稱投資語意安全；跨層改動需列出多組命令。 | 維護導覽中的 `專業維護語氣`。 | 專業語氣限制完成敘述，不取代實際測試命令。 |
| 論點 | 收斂核心論點：契約矩陣不是自動化選測，而是先保留人工判斷，再用最小測試驗證；碰到 parser/prompt/template，優先視為契約變更。 | 維護導覽中的 `核心論點`。 | 核心論點是維護規範，不代表未來所有改動都能只靠本文件判定。 |

下一批可從溝通設計、表達、媒介與多媒體處理：檢查契約矩陣目前用文字與表格是否足夠，是否需要補更短的前置摘要，或是否應維持不加入圖像以避免過度設計。

## 第 2 輪溝通思考契約矩陣摘要與媒介設計

本批把維護導覽壓成可快速引用的一頁摘要，讓操作者在改檔前可以先用三個問題判斷通道，再用固定句型回報通道、命令與不得解讀為的限制。媒介上維持文字與表格優先，暫不新增圖像或多媒體，避免把仍需人工判斷的契約層級包裝成自動流程。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 溝通設計 | 新增短版摘要，將判斷順序壓成三步：先看 parser/prompt/template、再看使用者是否直接閱讀、最後看是否只在前端顯示。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣一頁摘要`。 | 短版摘要是入口，不取代完整契約矩陣。 |
| 表達 | 新增建議表達句型，要求回報「我選擇的通道是」、「我已執行的命令是」與「不得解讀為」。 | 一頁摘要中的 `建議表達`。 | 句型只約束回報清晰度，不自動產生測試證據。 |
| 媒介 | 明確採用文字與表格優先，因為維護者需要複製判斷、命令與限制。 | 一頁摘要中的 `媒介取捨`。 | 媒介取捨只適用本文件，不禁止未來產品 UI 另行設計。 |
| 多媒體 | 暫不新增圖像或多媒體，避免圖像把人工判斷包成自動流程，或讓操作者跳過限制條件。 | 媒介取捨中的多媒體限制。 | 若未來新增圖像，仍需保留文字版通道、命令與限制。 |

## 第 2 輪溝通思考收尾檢查

- 第 2 輪溝通思考完成：10/10。
- 收尾結論：本輪把契約矩陣從可操作流程，推進成分受眾、可導覽、可引用、可短版回報且媒介取捨明確的維護文件。
- 合理性取捨：本輪不新增圖像或多媒體，因為契約矩陣的主要任務是保留人工判斷、命令與限制，不是做成看似自動化的流程圖。
- 可重跑驗證：`tests/test_docs_contract.py` 鎖住一頁摘要、維護導覽與讀者路徑；`tests/test_hcs_plus_state.py` 鎖住第 2 輪溝通思考 10/10 收尾與下一分類入口。
- 下一分類入口：第 2 輪互動思考將從 `#倫理考量/#倫理勇氣/#倫理判斷` 開始，檢查契約矩陣如何避免過度安全宣稱與責任轉嫁。

## 第 2 輪互動思考契約矩陣倫理邊界設計

本批把溝通思考完成的一頁摘要，再加上互動層面的倫理邊界。重點是避免維護者把測試綠燈、文件紀錄或低顯著性通道，誇大成投資建議安全、工具自動負責或沒有使用者風險。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 倫理考量 | 建立倫理底線：不得把測試綠燈寫成投資建議安全、不得把責任轉嫁給工具或文件、不得用低顯著性通道淡化使用者風險。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣倫理邊界`。 | 倫理底線限制宣稱範圍，不取代測試命令。 |
| 倫理勇氣 | 明確必要時要說不：缺少 parser/prompt/template 證據時不可合併高顯著性改動；報告文案像交易指令時先補責任邊界。 | 倫理邊界中的 `必要時要說不`。 | 說不規則保護高風險改動，不代表所有低風險改動都必須阻擋。 |
| 倫理判斷 | 建立允許與禁止敘述，以及低顯著性到混合層、混合層到高顯著性、文件判斷到 runtime 驗證的升級條件。 | 倫理邊界中的 `倫理判斷` 與 `升級條件`。 | 判斷表是維護準則，不等於自動化審核器。 |

下一批可從複雜因果、湧現特性與分析層次處理：檢查局部測試綠燈、文件契約與使用者行為之間的非線性風險，避免把單一層級的證據擴張成整體系統安全。

## 第 2 輪互動思考契約矩陣系統風險邊界設計

本批把倫理邊界往系統層級推進，說清楚文件、測試、runtime 與使用者行為之間不能互相替代。重點是避免維護者把單一層級的綠燈、紀錄或語氣改善，擴張成整體系統安全。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 複雜因果 | 建立複雜因果圖譜：局部測試綠燈、文件紀錄與前端語氣改善，各自可能導致錯誤推論。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣系統風險邊界`。 | 因果圖譜只限制推論，不證明實際使用者行為。 |
| 湧現特性 | 記錄三種湧現風險：多個低顯著性改動累積成高風險、跨模式文案一致但責任邊界模糊、觀察紀錄增加但實際驗證減少。 | 系統風險邊界中的 `湧現風險`。 | 湧現風險是預警清單，不等於已發生事故。 |
| 分析層次 | 區分文件層、測試層、runtime 層與使用者行為層，要求不得用下一層證據替代上一層證據，也不得反向替代。 | 系統風險邊界中的 `分析層次`。 | 分層規則要求宣稱對齊證據層級，不自動產生證據。 |

下一批可從網絡、系統動力學與系統圖像處理：把前端、報告模板、parser/prompt、測試、文件與使用者行為的關係整理成更清楚的維護網絡。

## 第 2 輪互動思考契約矩陣系統關係設計

本批把系統風險邊界轉成可閱讀的維護網絡與動力回路。契約矩陣現在不只列出風險，還說明前端顯示、報告模板、parser/prompt、測試矩陣與使用者判讀如何互相影響，以及改動應如何在系統圖像中走完。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 網絡 | 建立維護網絡，列出前端顯示層、報告模板層、parser/prompt 層、測試矩陣與使用者判讀的連線與主要風險。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣系統關係圖`。 | 網絡圖是文字表格，不是自動依賴分析工具。 |
| 系統動力學 | 記錄三個動態回路：語氣改善降低權威感但可能增加契約漂移、觀察紀錄降低漏跑但可能增加形式化、升級條件降低錯放但可能增加維護成本。 | 系統關係圖中的 `系統動力學`。 | 動態回路是風險提醒，不代表已量化成本或發生率。 |
| 系統圖像 | 建立改動流程圖像：改動先定位層級、證據再對齊層次、宣稱最後受倫理邊界限制。 | 系統關係圖中的 `系統圖像`。 | 系統圖像限制維護流程，不取代測試矩陣。 |

下一批可從談判、說服與形塑行為處理：把這些邊界轉成 review 對話用語，讓維護者更容易接受補證據、升級通道或拆分改動。

## 第 2 輪互動思考契約矩陣 review 對話設計

本批把倫理邊界、系統風險與維護網絡轉成 review 對話。重點不是增加審查權威，而是讓維護者在需要補證據、升級通道或拆分改動時，有更低摩擦的說法與預設行為。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 談判 | 建立補證據協商：先承認改動目的，再指出缺少的證據層，最後提出最小補證據路徑。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣 review 對話`。 | 協商句型降低防衛感，但不替代測試或案例卡。 |
| 說服 | 建立說服原則：把補跑命令說成降低錯放風險，把升級通道說成保護 parser/prompt/template，把拆分改動說成降低 review 成本。 | review 對話中的 `說服原則`。 | 說服只用於說明風險與成本，不可把測試綠燈包裝成投資語意安全。 |
| 形塑行為 | 建立預設行為：使用一頁摘要句型、跨層改動先填案例卡、紅色或黃色採用訊號不得合併。 | review 對話中的 `形塑行為`。 | 行為預設只約束 review 節奏，不新增自動化審核器。 |

下一批可從從眾、差異與情緒智商處理：檢查 review 對話是否可能讓人盲目跟隨綠燈、壓扁不同情境差異，或在高壓修改中省略不得解讀為的限制。

## 第 2 輪互動思考契約矩陣 review 防從眾設計

本批把 review 對話再加一道防從眾檢查，避免團隊把多數同意、前例綠燈、格式一致或情緒壓力誤當成證據。重點是讓契約矩陣在低摩擦協商之外，仍保留不同層級、不同模式與不同風險的邊界。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 從眾 | 建立防從眾檢查：不得用多數人同意取代證據層，不得用前例綠燈取代本次改動層級，不得用測試全綠取代不得解讀為。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣 review 防從眾檢查`。 | 防從眾檢查限制 review 推論，不代表自動偵測團隊壓力。 |
| 差異 | 建立差異保留：高顯著性、混合層、低顯著性不得合併敘述；不同 pipeline 模式與不同證據層要分開回報。 | review 防從眾檢查中的 `差異保留`。 | 差異保留避免責任邊界被壓平，但不取代各通道測試命令。 |
| 情緒智商 | 建立高壓回報順序：先命名壓力，再回到最小補證據路徑，最後用限制句收尾。 | review 防從眾檢查中的 `情緒智商`。 | 情緒智商處理溝通壓力，不降低合併前的證據要求。 |

下一批可從領導原則、權力動態與責任處理：檢查誰要主動要求升級通道、誰能阻止錯放，以及完成敘述中誰承擔限制與不得解讀為。

## 第 2 輪互動思考契約矩陣 review 責任分工設計

本批把防從眾檢查推進成責任分工：不是只有「有人應該補證據」，而是明確誰要宣告改動層級、誰要要求升級通道、誰要確認限制句存在。重點是讓權限與角色服務證據，而不是取代證據。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 領導原則 | 建立 review 領導原則：主責先宣告改動層級，review 主導者必須要求升級通道，完成敘述必須保留不得解讀為。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣 review 責任分工`。 | 領導原則只規範 review 行為，不自動判斷改動層級。 |
| 權力動態 | 建立權力護欄：不得用職位或資深度取代證據，低權限操作者可以引用契約矩陣要求補證據，高權限操作者不得覆蓋紅色或黃色採用訊號。 | review 責任分工中的 `權力動態`。 | 權力護欄限制合併權限，不取代測試命令或案例卡。 |
| 責任 | 建立角色責任：改動者負責描述改動層級，reviewer 負責核對通道與命令，合併者負責確認限制句存在。 | review 責任分工中的 `責任`。 | 責任分工讓完成敘述可追溯，但不代表所有 runtime 路徑已驗證。 |

下一批可從自我覺察與制定策略處理：檢查契約矩陣是否因規則變多而過度官僚，並收斂第 2 輪互動思考的收尾策略。

## 第 2 輪互動思考契約矩陣 review 自我稽核與收尾設計

本批用自我覺察檢查契約矩陣自身的副作用：規則越完整，越可能變成官僚成本或假自動化。制定策略上，本輪互動思考不新增工具，而是把收尾條件寫清楚，讓下一輪回到批判思考重新拆解矩陣是否過重與缺口是否仍存在。

| 思考習慣 | 核心設計 | 落地位置 | 驗證邊界 |
|---|---|---|---|
| 自我覺察 | 承認契約矩陣不是自動化審核器，規則變多可能增加官僚成本，低顯著性顯示層不得被迫跑高顯著性全矩陣。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣 review 自我稽核與收尾策略`。 | 自我稽核限制矩陣使用方式，不保證每次 review 都會正確取捨。 |
| 制定策略 | 建立收尾策略：先選最小足夠路徑，高風險升級、低風險保留輕量通道，並定義第 2 輪互動思考收尾條件。 | review 自我稽核與收尾策略中的 `制定策略` 與 `收尾聲明`。 | 收尾只代表第 2 輪互動思考 20/20 完成，不代表 HCS Plus 完成。 |

收尾檢查：

- 第 2 輪互動思考完成：20/20。
- 已完成倫理邊界、系統風險、系統關係、review 對話、防從眾、責任分工與自我稽核。
- 下一輪入口是第 3 輪批判思考：從 `#拆解問題/#問對問題/#差距分析` 重新檢查契約矩陣是否過重、是否仍有最高風險缺口。
- 不得宣稱 HCS Plus 完成：仍需第 3 輪全習慣輪巡與後續綜合優化。

## 第 3 輪批判思考契約矩陣瘦身問題雷達

本批把第 2 輪互動思考的自我稽核往前推成第 3 輪批判入口：先承認契約矩陣已足夠完整，但可能過重；再把「如何應用到系統」限定為文件契約、review 回報與測試護欄，而不是宣稱 runtime 自動判斷。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 拆解問題 | 將契約矩陣過重拆成四個子問題：矩陣過重、維護者是否能在 2 分鐘內選到通道、低顯著性是否被高顯著性流程拖慢、責任分工是否讓限制句真的出現。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪問題雷達`。 | 還要判斷哪些變數會讓操作者錯誤升級或錯誤降級。 |
| 問對問題 | 將下一步問題改成：哪個規則可以被一頁摘要取代、哪個情境必須保留完整矩陣、哪個證據層仍然沒有 runtime 驗證。 | 問題雷達中的 `關鍵問題`。 | 仍需把問題轉成可檢查的完成回報欄位。 |
| 差距分析 | 對照已完成的速學卡、一頁摘要、三通道命令、倫理邊界與責任分工，指出仍缺日常入口、限制句驗證與輕量通道誤用防線。 | 問題雷達中的 `差距分析`。 | 下一批需用變數分析與偏誤降低把差距收斂成具體判斷護欄。 |

套用到系統的邊界：

1. 目前套用在文件契約與測試層：維護者依問題雷達選通道、補證據與寫限制句。
2. 尚未套用成 runtime 自動流程：系統不會自動判斷改動層級，也不會自動阻擋合併。
3. 下一批才檢查是否需要把完成回報格式、案例卡或自動檢查擴展到工具層。

## 第 3 輪批判思考契約矩陣變數與偏誤降低護欄

本批把上一批的問題雷達轉成可套用的判斷護欄：先找出會造成錯誤升級、錯誤降級或過度宣稱的變數，再把偏誤寫成明確禁忌與降低規則。這仍是文件契約與測試層，不是 runtime 自動審核器。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 變數分析 | 影響矩陣瘦身的主要變數是改動層級、證據層、可逆性與時程壓力；它們決定要走一頁摘要、完整矩陣、拆分 patch 或補證據。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪變數與偏誤降低護欄`。 | 還需用決策樹把這些變數排成可操作順序。 |
| 偏誤辨識 | 目前最大風險是過度升級偏誤、過度降級偏誤、工具化幻覺與綠燈擴張偏誤；四者會讓矩陣不是太重，就是太鬆。 | 同章節的 `偏誤辨識`。 | 仍需把每個偏誤接到明確分流決策，避免只停在提醒。 |
| 偏誤降低 | 以一頁摘要優先、跨層改動升級、證據分層回報、限制句必填與案例卡觸發作為偏誤降低規則。 | 同章節的 `偏誤降低`。 | 下一批需檢查這些規則的目的與效用，避免又變成新的官僚負擔。 |

系統應用方式：

1. 改動前先標改動層級；只碰低顯著性顯示層時保留一頁摘要與輕量回報。
2. 只要跨層、碰 parser/prompt/template 或完整報告正文，就升級完整矩陣或拆分 patch。
3. 完成回報要分開寫文件層、測試層、runtime 層與使用者行為層，不用單一測試綠燈包裝成全面驗證。

## 第 3 輪批判思考契約矩陣分流決策與效用校準

本批把變數與偏誤降低護欄轉成可執行的分流順序：先判斷是否純前端顯示層，再判斷是否碰 parser/prompt/template，接著處理完整報告正文或跨層改動，最後才決定是否只用文件契約測試。這仍是維護流程契約，不是 runtime 自動選測工具。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 決策樹 | 將一頁摘要、低顯著性命令、高顯著性機器契約通道、混合層報告呈現通道、案例卡或拆分 patch 排成五步分流。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪分流決策與效用校準`。 | 下一批需檢查此決策樹的信賴區間：目前只由文件契約與測試鎖住，尚無實際 review 樣本統計。 |
| 目的 | 目的不是讓矩陣更複雜，而是降低 2 分鐘選通道摩擦、保住高顯著性契約、防止綠燈擴張並保留低顯著性效率。 | 同章節的 `目的校準`。 | 還需檢查哪些目的可以被觀察訊號支持，哪些只是設計假設。 |
| 效用 | 每條規則都需要列出預期效用、成本與升級或停用條件，避免保護規則變成新官僚負擔。 | 同章節的 `效用校準`。 | 下一批需用描述統計與相關性整理哪些訊號可以證明規則真的有用。 |

系統應用方式：

1. 維護者先照決策樹選通道，不再先讀完整矩陣。
2. 目的校準限制每條規則的使用理由，避免為了流程完整而增加無效步驟。
3. 效用校準要求每條規則有成本與升級或停用條件，讓後續可以用觀察資料決定是否保留。

## 第 3 輪批判思考契約矩陣證據校準與觀測統計

本批不再新增分流規則，而是校準分流決策的證據強度：目前決策樹只被文件契約與測試鎖住，尚未有足夠實際 review 樣本。因此本批把可觀測訊號、不可外推範圍與描述統計欄位寫清楚，避免把設計假設當成已證實流程。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 信賴區間 | 目前樣本只包含文件契約、HCS 狀態測試與前端顯示層回歸；不可外推成所有 review、runtime 或使用者行為都已驗證。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪證據校準與觀測統計`。 | 下一批需把觀測欄位轉成機率與門檻，決定何時升級或調整規則。 |
| 相關性 | 選通道時間、錯選通道、限制句出現率與案例卡觸發率只能支持關聯，不代表因果。 | 同章節的 `相關性`。 | 仍需定義哪些訊號可以作為回歸監測，而不是一次性觀察。 |
| 描述統計 | 至少記錄樣本數、中位選通道時間、錯選率、跨層改動比例、案例卡觸發率與限制句出現率。 | 同章節的 `描述統計`。 | 下一批需判斷哪些統計變動夠顯著，哪些只是小樣本波動。 |

系統應用方式：

1. 使用決策樹後，若要宣稱它有效，必須至少記錄樣本數與中位選通道時間。
2. 若要宣稱錯選下降，必須同時記錄錯選率與跨層改動比例，避免樣本變簡單造成假改善。
3. 若要宣稱完成回報品質改善，必須記錄限制句出現率，但仍不能推論限制句內容一定正確。

## 第 3 輪批判思考契約矩陣風險機率與顯著性門檻

本批把前一批的描述統計轉成操作門檻：錯選率、限制句缺漏率與案例卡漏觸發率不是單純報表欄位，而是決定何時升級 review、何時啟動回歸監測、何時不得宣稱改善的風險訊號。這仍是文件與流程契約，不是自動化 runtime 攔截器。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 機率 | 錯選率、限制句缺漏率與案例卡漏觸發率可轉成風險機率判讀；少於至少 5 個案例時只描述個案，不宣稱趨勢。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪風險機率與顯著性門檻`。 | 下一批需檢查這些門檻的證據基礎，避免把暫定比例當成已驗證統計。 |
| 迴歸 | 連續兩個觀察窗口同方向惡化，才視為穩定回歸；單一紅色高風險案例可立即升級。 | 同章節的 `迴歸`。 | 仍需演繹出哪些改動層級一定不能等待第二窗口。 |
| 顯著性 | 至少 5 個案例後才討論升級門檻；測試通過、文件存在或單一案例變好，不得宣稱改善。 | 同章節的 `顯著性`。 | 下一批需寫清楚可外推與不可外推範圍，避免把文件門檻當成真實使用者理解證據。 |

系統應用方式：

1. 契約相關變更完成回報時，先記錄錯選率、限制句缺漏率與案例卡漏觸發率，避免只說「測試綠燈」。
2. 若連續兩個觀察窗口出現同方向回歸，才調整決策樹或案例卡規則；若是 parser/prompt/template 被錯放低顯著性，立即升級 review。
3. 少於至少 5 個案例時，所有改善敘述都必須保留小樣本限制，不得宣稱改善分流品質、使用者理解或 runtime 安全。

## 第 3 輪批判思考契約矩陣證據規則與外推邊界

本批把上一批門檻再收緊成證據規則：不是所有綠燈、比例或案例都能支持同一種結論。文件契約測試只能證明文件護欄存在；觀察窗口只能支持已記錄案例；案例卡只能支持代表性跨層案例，不能自動外推到 runtime、真實使用者理解或生成報告母體。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 證據基礎 | 可接受證據分成文件契約測試、觀察窗口紀錄與案例卡；單次綠燈、未標樣本數比例與單純章節存在不可作為改善證據。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪證據規則與外推邊界`。 | 下一批需拆出哪些常見謬誤仍會把證據層混用。 |
| 演繹 | parser/prompt/template 或核心契約詞改動立即升級；少於至少 5 個案例只能描述個案；連續兩個窗口同方向回歸才調整決策樹。 | 同章節的 `演繹`。 | 仍需檢查來源品質，避免把低品質觀察當成高品質規則依據。 |
| 歸納 | 文件測試、觀察窗口與案例卡都有外推邊界，不得外推到 runtime 安全、真實使用者理解、生成報告母體或未記錄 review 行為。 | 同章節的 `歸納`。 | 下一批需補情境脈絡，說清楚何時可引用、何時必須回到人工 review。 |

系統應用方式：

1. 完成回報若引用文件契約測試，只能說明護欄仍存在，不得宣稱分流品質或 runtime 已改善。
2. 完成回報若引用觀察窗口，必須列出樣本數與改動層級；未標樣本數不得用於改善敘述。
3. 完成回報若引用案例卡，只能支持該代表性案例的升級、拆分或補測判斷，不得宣稱整個生成報告母體安全。

## 第 3 輪批判思考契約矩陣反謬誤與來源情境邊界

本批把證據規則再轉成使用時的防誤讀護欄：測試綠燈、觀察比例與案例卡都常被誇大，因此需要明確列出謬誤、來源品質與情境脈絡。這一批仍屬文件契約，不替代 runtime 驗證、人工 review 或使用者研究。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 謬誤 | 主要風險是測試綠燈謬誤、樣本數謬誤與案例代表性謬誤，會把有限證據誇大成流程成效或安全證明。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪反謬誤與來源情境邊界`。 | 下一批需批判目前矩陣是否已過重，避免護欄本身造成執行摩擦。 |
| 來源品質 | 高品質來源是可重跑測試、契約 diff、含樣本數與改動層級的觀察窗口、完整案例卡；次級來源不能單獨支持改善宣稱。 | 同章節的 `來源品質`。 | 仍需估算維護者填寫來源品質欄位的成本。 |
| 情境脈絡 | 本護欄只適用於契約相關變更；一般 UI 文案不必填完整契約矩陣，但黃色、紅色或跨層情境需要人工 review。 | 同章節的 `情境脈絡`。 | 下一批需建立完成回報的詮釋框架，讓不同情境用不同語氣收尾。 |

系統應用方式：

1. 完成回報若只引用測試綠燈，必須加完成回報限制句，說明不得替代 runtime 驗證與不得替代使用者研究。
2. 完成回報若引用觀察比例，必須列出樣本數、改動層級與觀察窗口，否則不得作為完成證據。
3. 完成回報若引用案例卡，必須標明只適用於契約相關變更與該代表性案例，不得宣稱生成報告母體安全。

## 第 3 輪批判思考契約矩陣負擔估算與完成詮釋框架

本批批判第 3 輪前面新增的護欄是否開始過重：完整矩陣應保留給高風險契約與跨層情境，低風險 UI 與一般顯示微調應使用短句替代。估算上，完成回報成本必須隨風險分層；詮釋框架則讓每種證據只說它能支持的範圍。

| 思考習慣 | 核心判斷 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 批判 | 矩陣過重風險已出現；必留護欄只保留給 parser/prompt/template、核心契約詞、跨層、黃色或紅色訊號，低風險 UI 改動應可短句替代。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪負擔估算與完成詮釋框架`。 | 下一批需判斷第 3 輪批判思考是否已足夠合理，可以收尾到下一分類。 |
| 估算 | 低風險 UI 完成回報上限 2 分鐘，混合層上限 3 分鐘，高風險契約不設硬上限但必須列完整證據。 | 同章節的 `估算`。 | 仍需用可驗證性測試鎖住進度，不讓成本估算只是文字聲明。 |
| 詮釋框架 | 文件契約通過、觀察窗口、runtime 驗證與使用者研究各有不同完成回報詮釋，且都有禁止宣稱範圍。 | 同章節的 `詮釋框架`。 | 下一批需把整輪批判思考收束成可重跑 checkpoint。 |

系統應用方式：

1. 低風險 UI 或一般顯示微調完成回報用短句即可，不填完整案例卡。
2. 混合層與高風險契約完成回報必須保留不得宣稱安全、不得宣稱理解改善或不得替代 runtime 驗證等限制句。
3. 若只有文件契約通過，完成回報只能說護欄仍存在；若有 runtime 驗證或使用者研究，才可各自描述該範圍內的結果。

## 第 3 輪批判思考收尾檢查

- 第 3 輪批判思考完成：26/26。
- 合理性結論：第 3 輪已把契約矩陣從問題雷達、變數偏誤、分流決策、證據統計、風險門檻、證據規則、反謬誤、來源情境、負擔估算到完成詮釋框架全部收束；此時繼續堆疊批判矩陣的效益低於把它轉成更好學、更容易採用的創意思考入口。
- 合理性取捨：不新增自動選測腳本，因為跨層改動、黃色/紅色訊號與核心契約詞仍需保留人工判斷；過早工具化會讓維護者誤以為系統已能自動判斷風險。
- 可重跑驗證：`tests/test_hcs_plus_state.py` 鎖住 26/26 收尾、嚴格附件第九批、下一分類入口與進度表；`tests/test_docs_contract.py` 鎖住 `契約矩陣第 3 輪收尾與可重跑驗證`；`tests/test_static_history_filters.py` 與 `tests/test_frontend_visual_optional.py` 作為相關前端契約回歸。
- 下一分類入口：第 3 輪創意思考將從 `#學習科學/#限制條件/#類比` 開始，把契約矩陣從「可驗證且不過度宣稱」推向「更容易被操作者學會與採用」。
- 邊界：本收尾不得宣稱 HCS Plus 完成，也不得宣稱 runtime 安全、使用者理解改善或自動選測能力已完成。

## 第 3 輪創意思考契約矩陣學習入口

本批把第 3 輪批判思考收尾後的契約矩陣轉成可學習入口：維護者不需要先讀完整矩陣，而是先用 10 秒判斷改動風險，再用 90 秒執行最小命令與限制句，最後用 5 分鐘復盤補案例或觀察。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 學習科學 | 三層學習路徑把契約矩陣切成 10 秒判斷、90 秒執行、5 分鐘復盤，降低第一次使用負擔。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪創意學習入口`。 | 下一批需把三層路徑轉成更明確的操作演算法。 |
| 限制條件 | 本入口不改 runtime 行為、不新增自動選測腳本、不新增遙測、不替代人工 review，也不得把文件契約通過解讀成安全證明。 | 同章節的 `限制條件`。 | 仍需設計低摩擦情境，避免限制條件讓入口看起來太重。 |
| 類比 | 用登機前安檢說明快速通道、人工複檢與證據托盤；安檢通過不等於航程安全。 | 同章節的 `類比`。 | 下一批需把類比轉成可直接套用的捷思規則。 |

系統應用方式：

1. 低風險 UI 改動先走 10 秒判斷與快速通道，完成回報只需短句與前端測試結果。
2. 黃色/紅色訊號、跨層改動或核心契約詞改動走人工複檢，必須放入測試輸出、diff、案例卡或限制句等證據托盤。
3. 任何安檢通過都不得外推成航程安全；在系統語境中，就是不得宣稱 runtime 安全、使用者理解改善或 HCS Plus 完成。

## 第 3 輪創意思考契約矩陣操作演算法與捷思規則

本批把三層學習路徑轉成可照做的操作演算法：先判斷改動風險，再選通道，再裝好證據托盤，最後用限制句完成回報。這仍是文件契約與人工 review 流程，不替代 runtime 驗證。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 演算法 | 四步操作演算法把 10 秒判斷、90 秒執行與 5 分鐘復盤拆成判斷、選通道、裝證據托盤、完成回報。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪操作演算法與捷思規則`。 | 下一批需最佳化步驟順序，避免低風險 UI 被過度流程化。 |
| 設計思考 | 三個操作者情境分別處理只改低風險 UI、改報告模板或正文呈現、改 parser/prompt/template 或核心契約詞。 | 同章節的 `設計思考`。 | 仍需確認不同情境的採用摩擦如何被觀察。 |
| 捷思法 | 三條快速規則是有核心契約詞就先人工複檢、只在前端顯示才走快速通道、缺少限制句就不得完成。 | 同章節的 `捷思法`。 | 下一批需把快速規則變成可觀察假說與採用訊號。 |

系統應用方式：

1. 低風險 UI 改動：套用情境 A，只在前端顯示才走快速通道，完成回報列前端測試結果與不碰 parser/prompt/template。
2. 報告模板或正文呈現：套用情境 B，走混合層報告呈現通道，完成回報保留不得替代 runtime 驗證。
3. parser/prompt/template 或核心契約詞：套用情境 C，有核心契約詞就先人工複檢，證據托盤需包含 diff、必跑命令、案例卡與限制句。
4. 任何情境若缺少限制句就不得完成，回到證據托盤補齊。

## 第 3 輪創意思考契約矩陣採用最佳化與訊號板

本批把操作演算法的採用摩擦轉成可觀察項目：錯選通道、漏跑命令、限制句缺漏與案例卡漏補。此訊號板只用人工觀察與文件紀錄，不新增遙測，也不得宣稱改善。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 最佳化 | 採用摩擦聚焦錯選通道、漏跑命令、限制句缺漏與案例卡漏補；最佳化目標是降低 review 摩擦，不是證明流程已改善。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪採用最佳化與訊號板`。 | 下一批需把摩擦類型轉成代表性案例模型。 |
| 假說發展 | 三個假說分別檢查四步操作是否降低錯選通道、證據托盤是否降低漏跑命令、三條快速規則是否降低限制句缺漏。 | 同章節的 `假說發展`。 | 仍需定義抽樣方式，避免單一觀察被過度外推。 |
| 資料視覺化 | 採用訊號板用綠色、黃色、紅色呈現人工觀察結果；紅色代表停止合併並回到人工複檢。 | 同章節的 `資料視覺化`。 | 下一批需建立案例卡，讓訊號能追溯到具體改動。 |

系統應用方式：

1. 完成回報後若發現錯選通道、漏跑命令、限制句缺漏或案例卡漏補，先記成人工觀察，不新增產品遙測。
2. 綠色只代表目前人工觀察未見上述缺漏；不得宣稱改善。
3. 黃色代表需要補案例、補提示或重寫步驟；紅色代表高風險契約或核心契約詞流程失守，停止合併並回到人工複檢。
4. 採用訊號板不得替代測試、runtime 驗證或使用者研究。

## 第 3 輪創意思考契約矩陣案例模型與抽樣案例卡

本批把採用訊號板轉成可追溯案例模型：每個綠/黃/紅訊號都應能連回具體改動、通道、證據托盤與限制句。這仍是文件契約，不新增遙測，也不得用個案宣稱趨勢。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 建模 | 代表性案例模型分成模型 A：低風險快速通道案例、模型 B：混合層報告呈現案例、模型 C：高風險契約人工複檢案例、模型 D：紅色阻擋案例。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪案例模型與抽樣案例卡`。 | 下一批需比較使用案例模型前後是否更少錯選通道。 |
| 抽樣 | 代表性抽樣規則要求每個觀察窗口抽實際出現模型，黃色或紅色必抽，少於 5 個案例不得宣稱趨勢。 | 同章節的 `抽樣`。 | 仍需定義比較組與介入組。 |
| 個案研究 | 案例卡格式收斂為改動描述、改動層級、選擇通道、證據托盤、採用訊號、限制句、補救行動、不可外推。 | 同章節的 `個案研究`。 | 下一批需用訪談或回饋題檢查案例卡是否可用。 |

系統應用方式：

1. 每個黃色或紅色採用訊號都必須轉成案例卡，不只停在訊號板顏色。
2. 綠色案例也可抽樣保留，但只能說該窗口未觀察到缺漏；不得宣稱趨勢。
3. 少於 5 個案例不得宣稱趨勢；任何個案都不得外推成 runtime 安全、使用者理解改善或 HCS Plus 完成。

## 第 3 輪創意思考契約矩陣比較與介入回饋設計

本批把案例模型推進成最小可比較設計：基準組只使用既有四步操作與訊號板，介入組加入改檔前案例模型選擇、案例卡與補救回放。這仍是 review 方法，不是統計實驗，不新增產品遙測，也不得宣稱因果改善。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 比較組 | 基準組與介入組都只看人工 review 與文件紀錄；觀察錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪比較與介入回饋設計`。 | 下一批需定義觀察紀錄欄位，避免比較結果散落在回憶裡。 |
| 介入研究 | 最小介入方案包含改檔前 60 秒案例模型選擇、完成回報三欄補強、黃色或紅色補救回放與介入停止條件。 | 同章節的 `介入研究`。 | 仍需確認同一介入能否被不同操作者複製。 |
| 訪談調查 | 操作者回饋題聚焦是否能在 2 分鐘內選出通道、哪個案例模型最難判斷、案例卡是否暴露漏跑命令或限制句缺漏。 | 同章節的 `訪談調查`。 | 下一批需把回饋題轉成可複製觀察流程。 |

系統應用方式：

1. 新增高風險或混合層契約改動時，先用介入組流程：改檔前選模型、完成後補三欄回報，黃色或紅色訊號再做補救回放。
2. 低風險 UI 改動仍可留在基準組或快速通道；若介入流程超過 2 分鐘，先回到短句回報，避免文件契約過度流程化。
3. 比較結果只能描述觀察窗口內的錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率；不得宣稱因果改善、runtime 安全、使用者理解改善或 HCS Plus 完成。
4. 訪談調查答案只作為輔助證據，不得替代 pytest 或人工 review。

## 第 3 輪創意思考契約矩陣觀察與複製準則

本批把比較組、介入方案與回饋題轉成可重複填寫的觀察記錄欄位與複製檢查清單。這仍是人工文件流程，不新增產品遙測，不替代 pytest 或人工 review，也不得宣稱改善。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 觀察研究 | 觀察記錄欄位包含觀察窗口、變更案例 ID、選定案例模型、實際選擇通道、實際執行命令、完成回報三欄、觀察結果、操作者回饋摘要、補救行動與不可外推。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪觀察與複製準則`。 | 下一批需用溝通思考整理誰要讀、先讀什麼、哪些詞不能誤解。 |
| 研究複製 | 複製檢查清單要求同一觀察窗口定義、同一案例模型選項、同一指標口徑、同一介入停止條件與同一限制句。 | 同章節的 `研究複製`。 | 仍需將複製準則改寫成不同受眾可快速採用的語意結構。 |

系統應用方式：

1. 每個觀察窗口都要用同一組觀察記錄欄位，不得只留下口頭印象或顏色訊號。
2. 下一位操作者複製流程時，必須維持同一案例模型選項、同一指標口徑與同一介入停止條件。
3. 若沒有實際案例，記錄「本窗口未觀察到」；不得用假案例補位。
4. 可複製只代表下一位操作者能照同一欄位重做紀錄，不代表 runtime 安全、使用者理解改善、流程改善或 HCS Plus 完成。

## 第 3 輪溝通思考契約矩陣讀者語意入口

本批把第 3 輪創意思考收尾後的觀察與複製準則轉成讀者語意入口：不同維護者先看自己需要的通道、欄位與限制句，避免完整矩陣造成低風險流程過重，也避免高風險契約被誤放快速通道。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 受眾 | 分出低風險 UI 維護者、報告呈現維護者、契約複檢維護者與觀察流程維護者四種讀者。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪讀者語意入口`。 | 下一批需把入口整理成更清楚的章節導覽。 |
| 組成 | 閱讀組成是第一步：先判斷讀者角色；第二步：只讀對應入口；第三步：補齊觀察欄位；第四步：用限制句收尾。 | 同章節的 `組成`。 | 仍需用專業性與論點收斂成可引用規範。 |
| 語意含義 | 明確寫出讀者角色不是權限等級、入口不是自動判斷器、觀察欄位不是 pytest、複製成功不是改善證明、低風險不代表低責任。 | 同章節的 `語意含義`。 | 下一批需檢查這些語意邊界是否需要前置摘要。 |

系統應用方式：

1. 改低風險 UI 時先走低風險 UI 維護者入口，但完成回報仍要說明不碰 parser/prompt/template。
2. 改報告呈現、完整報告正文、preview 或儲存路徑時，使用報告呈現維護者入口，不得只用前端顯示測試替代。
3. 改 parser、prompt、template 或核心契約詞時，使用契約複檢維護者入口；入口不是自動判斷器，仍需人工 review。
4. 維護觀察流程時，使用觀察流程維護者入口；觀察欄位不是 pytest，複製成功不是改善證明。
5. 所有入口都必須用限制句收尾，不得宣稱 runtime 安全、使用者理解改善或 HCS Plus 完成。

## 第 3 輪溝通思考契約矩陣維護導覽與核心論點

本批把讀者語意入口整理成更可引用的維護導覽：先讓讀者知道章節順序，再用專業語氣限制可宣稱範圍，最後用核心主張收束為低風險更快、高風險更早升級、觀察可複製但不誤讀。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 組織結構 | 章節導覽依序是先定位讀者角色、再選通道與案例模型、接著補觀察欄位、最後用限制句與核心論點收尾。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪維護導覽與核心論點`。 | 下一批需把導覽壓成更短摘要與可複用句型。 |
| 專業性 | 維護語氣要求只描述觀察窗口、明列未跑命令、把紅色訊號說成停止條件、不得把測試綠燈寫成安全證明。 | 同章節的 `專業性`。 | 仍需整理成完成回報表達句型。 |
| 論點 | 核心主張是契約矩陣的目的不是提高文件厚度，而是讓低風險改動更快收尾、讓高風險契約更早升級、讓觀察紀錄可複製但不被誤讀。 | 同章節的 `論點`。 | 下一批需檢查是否要用一頁摘要或文字表格呈現。 |

系統應用方式：

1. 日常低風險 UI 改動先用章節導覽定位讀者角色，再以快速通道和短句完成；回報仍要保留不碰 parser/prompt/template 的限制句。
2. 報告呈現或混合層改動要先選通道與案例模型，再明列實際執行命令；未跑命令必須寫原因，不得用前端綠燈替代報告呈現契約。
3. 高風險契約或紅色訊號要把紅色訊號說成停止條件，回到人工複檢、補跑 pytest 或拆分 patch；不得把觀察紀錄當成安全證明。
4. 完成回報要引用核心主張：這批矩陣是為了讓低風險改動更快收尾、高風險契約更早升級、觀察紀錄可複製但不被誤讀；不得宣稱改善，也不得替代 pytest 或人工 review。

## 第 3 輪溝通思考契約矩陣短版回報與媒介取捨

本批把維護導覽與核心論點壓成可直接貼進回報的一頁摘要、建議句型與媒介取捨。它完成第 3 輪溝通思考，但只完成溝通層收斂；不新增 runtime、不新增圖像流程、不替代 pytest 或人工 review。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 溝通設計 | 一頁摘要要求先說本次改動層級、再列已跑命令與未跑命令、最後寫不得解讀為。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪短版回報與媒介取捨`。 | 下一批需檢查短版回報是否足以承接倫理底線。 |
| 表達 | 建議句型固定為我選擇的通道是、我已執行的命令是、本次不得解讀為，讓完成回報可複製。 | 同章節的 `表達`。 | 仍需由互動思考檢查是否會把責任轉嫁給文件或工具。 |
| 媒介 | 媒介選擇文字與表格優先，不要新增圖像流程，不要用多媒體替代限制句。 | 同章節的 `媒介`。 | 若未來加入截圖或錄影，仍需保留文字限制。 |
| 多媒體 | 暫不新增圖像或多媒體，保留可搜尋文字，保留 pytest 與人工 review 作為完成證據。 | 同章節的 `多媒體`。 | 下一分類需檢查禁止誇大安全與必要時說不的互動邊界。 |

系統應用方式：

1. 低風險 UI 回報用一頁摘要：先說改動層級，再列已跑與未跑命令，最後寫不得解讀為 runtime 安全或 HCS Plus 完成。
2. 混合層或報告呈現回報必須套用建議句型，清楚寫出我選擇的通道是什麼、我已執行的命令是什麼，以及未跑命令的原因。
3. 高風險契約回報不得被多媒體或截圖取代；仍要保留可搜尋文字、pytest 與人工 review。
4. 本批完成第 3 輪溝通思考，下一步轉入第 3 輪互動思考，檢查倫理考量、倫理勇氣與倫理判斷。

## 第 3 輪互動思考契約矩陣倫理阻擋與責任判斷

本批把短版回報從「怎麼說清楚」推進到「哪些說法必須阻擋」。倫理重點不是讓流程更嚴厲，而是避免短版回報被誤用成安全背書、責任轉嫁或高風險契約降級。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 倫理考量 | 短版回報倫理底線要求不得把短版回報寫成安全背書、不得把責任轉嫁給文件、工具或測試、不得用快速通道淡化高風險契約。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪倫理阻擋與責任判斷`。 | 下一批需檢查局部證據如何造成系統性誤讀。 |
| 倫理勇氣 | 必要時要說不：缺少 parser/prompt/template 證據時停止合併、報告文案像交易指令時先補責任邊界、高風險契約被降級時回到人工複檢。 | 同章節的 `倫理勇氣`。 | 仍需分析停止條件如何在複雜因果中被稀釋。 |
| 倫理判斷 | 倫理判斷分成允許回報、禁止回報與升級判斷；低風險改動若碰到使用者行動暗示、混合層若碰到核心契約詞、文件或觀察若被拿來宣稱 runtime 行為都必須升級。 | 同章節的 `倫理判斷`。 | 下一批需把升級判斷放入證據層與系統層次。 |

系統應用方式：

1. 完成回報若暗示「短版已填所以安全」，必須改寫；短版回報只能作為通道、命令與限制句紀錄。
2. 缺少 parser/prompt/template 證據、報告文案像交易指令或高風險契約被降級時，先停止合併並回到人工複檢。
3. 文件或觀察若被拿來宣稱 runtime 行為、使用者已理解或流程改善，必須升級為 runtime 驗證、使用者研究或人工驗收；不得替代 pytest 或人工 review。
4. 下一批轉入複雜因果、湧現特性與分析層次，檢查局部綠燈如何造成系統性誤讀。

## 第 3 輪互動思考契約矩陣系統因果與證據層次

本批把倫理阻擋規則放進系統因果裡檢查：局部綠燈不會自動阻止系統性誤讀，文件、測試、runtime 與使用者行為也不能彼此替代。它讓完成回報先定位證據層，再決定是否需要升級驗證。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 複雜因果 | 局部綠燈因果圖列出文件契約通過可能造成流程已安全的錯誤推論、前端測試通過可能造成 parser/prompt 已安全的錯誤推論、倫理阻擋存在可能造成高風險已被完全阻擋的錯誤推論。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪系統因果與證據層次`。 | 下一批需把這些因果關係連成維護網絡。 |
| 湧現特性 | 湧現風險包含低風險快速通道累積成高風險語氣漂移、案例卡增加但實際驗證減少、阻擋規則存在但 reviewer 不敢啟用。 | 同章節的 `湧現特性`。 | 仍需檢查哪些回路會放大或抑制湧現風險。 |
| 分析層次 | 分析層次分成文件層、測試層、runtime 層與使用者行為層，要求同層證據只能支持同層宣稱、跨層宣稱必須升級驗證。 | 同章節的 `分析層次`。 | 下一批需把層次規則轉成系統圖像與操作路徑。 |

系統應用方式：

1. 回報若引用文件或案例卡，只能宣稱文件層與觀察層已記錄；不得用文件完整替代 runtime 驗證。
2. 回報若引用 pytest 或前端測試，只能宣稱指定測試層未回退；不得用測試通過宣稱使用者理解，也不得外推 parser/prompt 安全。
3. 若要宣稱 runtime 行為、生成報告安全或使用者理解，必須升級到 runtime 測試、人工驗收或使用者行為證據。
4. 若低風險快速通道、案例卡或倫理阻擋規則本身累積成新風險，下一批需用網絡、系統動力學與系統圖像補上回路與操作路徑。

## 第 3 輪互動思考契約矩陣維護網絡與動態圖像

本批把證據層次轉成可操作的維護網絡：先看文件、測試、runtime、使用者行為與 reviewer 阻擋節點如何連動，再看快速通道、案例卡、阻擋勇氣與跨層宣稱如何形成動態回路，最後用系統圖像決定是否維持同層宣稱或升級驗證。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 網絡 | 維護網絡連接文件層節點、測試層節點、runtime 層節點、使用者行為層節點與 reviewer 阻擋節點。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪維護網絡與動態圖像`。 | 下一批需把網絡語言轉成 review 對話與補證據協商。 |
| 系統動力學 | 動態回路包含快速通道摩擦降低回路、案例卡形式化回路、阻擋勇氣回路與跨層宣稱升級回路。 | 同章節的 `系統動力學`。 | 仍需檢查哪些說法能降低說不成本。 |
| 系統圖像 | 操作圖像是先定位證據層、再連到網絡節點、接著判斷動態回路、最後決定維持同層宣稱或升級驗證。 | 同章節的 `系統圖像`。 | 下一批需把圖像轉成預設行為與 review 句型。 |

系統應用方式：

1. 回報若要跨層宣稱，先用維護網絡找出牽動的節點，特別是 reviewer 阻擋節點是否已啟用。
2. 若快速通道降低摩擦但累積語氣漂移，回到混合層或高風險檢查。
3. 若案例卡增加但實際驗證減少，補跑 pytest 或人工 review，不得用案例卡替代證據。
4. 若阻擋勇氣回路失效，下一批需用談判、說服與形塑行為降低說不成本。

## 第 3 輪互動思考契約矩陣 review 對話與預設行為

本批把維護網絡轉成 reviewer 可直接採用的對話與預設行為：先用補證據協商保留同層成果但不降低標準，再用說服路徑降低說不成本，最後把完成回報預設成三欄，讓跨層宣稱自動回到升級驗證或降級宣稱。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 談判 | 補證據協商明確表示不降低標準；可接受同層宣稱、限制句、拆分 patch 或補跑命令，但不接受跨層宣稱無證據。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪 review 對話與預設行為`。 | 下一批需檢查多數同意或權威壓力是否讓協商失效。 |
| 說服 | 說服路徑是先承認已完成的證據、再指出缺口、接著提出最小可接受補證據、最後寫不得解讀為。 | 同章節的 `說服`。 | 仍需檢查高壓 review 裡哪些語氣會壓縮 reviewer 說不空間。 |
| 形塑行為 | 預設行為把完成回報固定成三欄：本次宣稱層級、已補證據、仍不得解讀為；黃色補限制句、紅色停止合併或拆分 patch。 | 同章節的 `形塑行為`。 | 下一批需檢查從眾、差異與情緒智商如何影響預設行為被採用。 |

系統應用方式：

1. reviewer 遇到跨層宣稱時，先用補證據協商句型要求同層宣稱或補證據，不把合併壓力變成降低標準。
2. 說服時先承認已完成證據，再指出缺口與最小補證據，降低說不成本但不美化風險。
3. 完成回報預設填三欄：本次宣稱層級、已補證據、仍不得解讀為。
4. 黃色訊號可保留同層宣稱但補限制句；紅色訊號停止合併、補跑 pytest 或人工 review、拆分 patch。

## 第 3 輪互動思考契約矩陣防從眾、差異訊號與情緒調節

本批把 review 預設行為加上防從眾與情緒壓力護欄：多數同意、前例綠燈、測試全綠與快要合併都不能取代證據層；差異訊號必須保留到完成回報；高壓語氣需先命名壓力，再回到預設三欄與最小補證據路徑。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 從眾 | 防從眾檢查明確寫出多數同意不是證據、前例綠燈不是本次綠燈、測試全綠不是限制句、快要合併不是降低標準的理由。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪防從眾、差異訊號與情緒調節`。 | 下一批需把防從眾規則轉成角色責任與權力護欄。 |
| 差異 | 差異訊號保留改動層級差異、證據層差異、pipeline 模式差異與風險顏色差異，並要求不得把黃色與紅色訊號寫成綠色。 | 同章節的 `差異訊號`。 | 仍需檢查誰有責任維持差異不被合併壓力壓平。 |
| 情緒智商 | 高壓語氣處理固定為先命名壓力來源、再回到預設三欄、接著保留最小補證據路徑、最後用冷靜限制句收尾。 | 同章節的 `高壓語氣處理`。 | 下一批需檢查權威催促與合併權限如何影響情緒壓力。 |

系統應用方式：

1. review 若出現多數同意、前例綠燈、測試全綠或快要合併，先回到本次證據層與完成回報三欄。
2. 回報必須保留改動層級、證據層、pipeline 模式與風險顏色差異，不得把黃色或紅色訊號寫成綠色。
3. 高壓語氣先命名壓力來源，再回到預設三欄與最小補證據路徑。
4. 不得用趕時間取代證據層，不得用情緒安撫取代 pytest 或人工 review。

## 第 3 輪互動思考契約矩陣角色責任與權力護欄

本批把防從眾規則轉成角色責任：主責負責宣告本次宣稱層級與已補證據，review 主導者負責維持升級權，合併者負責確認黃色、紅色與剩餘風險已被處理；權力不能取代證據，責任不能轉嫁給文件、工具或測試。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 領導原則 | 證據領導要求主責先宣告本次宣稱層級、review 主導者維持升級權、合併者確認紅色與黃色訊號已處理。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪角色責任與權力護欄`。 | 下一批需檢查這套角色責任是否過度官僚。 |
| 權力動態 | 權力護欄要求合併權限不能覆蓋紅色訊號、資深度不能把前例綠燈變成通行證、低權限操作者可以引用契約要求補證據。 | 同章節的 `權力動態`。 | 仍需檢查權力護欄如何在日常 review 中保持輕量。 |
| 責任 | 責任分工要求改動者負責本次宣稱層級與已補證據、reviewer 負責仍不得解讀為、合併者負責未跑命令與剩餘風險。 | 同章節的 `責任`。 | 下一批需用自我覺察與制定策略收斂責任流程。 |

系統應用方式：

1. 完成回報先由主責宣告本次宣稱層級與已補證據。
2. review 主導者遇到跨層宣稱、黃色或紅色訊號時維持升級權。
3. 合併者確認紅色與黃色訊號已處理，並記錄未跑命令與剩餘風險。
4. 權威催促或合併權限不能覆蓋紅色訊號；問題可追溯到角色責任，不得轉嫁給文件、工具或測試。

## 第 3 輪互動思考契約矩陣自我稽核與收尾策略

本批用自我覺察限制上一批的角色責任副作用：角色責任不是流程越多越好，低風險同層改動不應被拖成形式簽核；制定策略上，第 3 輪互動思考以 20/20 單項完成收尾，下一步進入三習慣綜合優化，而不是繼續堆疊互動思考規則。

| 思考習慣 | 核心設計 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 自我覺察 | 建立輕量使用邊界：低風險同層改動只需完成回報三欄，黃色訊號補限制句或最小證據，紅色訊號才要求停止合併、補跑 pytest 或拆分 patch。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣第 3 輪自我稽核與收尾策略`。 | 仍需在綜合優化中整合成最終驗收標準。 |
| 制定策略 | 建立第 3 輪互動思考收尾條件：20/20 單項完成、證據層與角色責任已可追溯、下一步進入三習慣綜合優化。 | 同章節的 `制定策略` 與本狀態表進度列。 | 下一批需用 #可驗證性、#溝通設計、#系統圖像做整體收斂。 |

系統應用方式：

1. 低風險同層改動保留完成回報三欄，不額外要求完整角色責任審核。
2. 黃色訊號先補限制句或最小證據；紅色訊號才停止合併、補跑 pytest 或拆分 patch。
3. 不把角色責任變成形式簽核，不把文件完整當成自動審核器。
4. 第 3 輪互動思考已完成 20/20 單項輪巡；下一步進入三習慣綜合優化，候選為 #可驗證性、#溝通設計、#系統圖像。
5. 不得宣稱 HCS Plus 完成；仍需後續綜合優化，不得新增 runtime、遙測或自動選測工具。

## 三習慣綜合優化第 1 次：驗證、溝通與系統圖像收斂

本批把三輪累積的契約矩陣收斂成最小可用操作面：先用 #可驗證性 固定驗證閘門，再用 #溝通設計 固定完成回報格式，最後用 #系統圖像 把前端顯示層、報告呈現層、機器契約層與維運決策層分開驗證。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 可驗證性 | 驗證閘門要求不跑命令不能宣稱通過，文件契約只支持文件層宣稱，高顯著性機器契約仍要跑 parser、prompt、template 與 audit 回歸。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 1 次：驗證、溝通與系統圖像收斂`。 | 下一批需補證據基礎，檢查證據來源品質與覆蓋邊界。 |
| 溝通設計 | 完成回報格式固定為本次宣稱層級、已補證據、仍不得解讀為、下一個可執行行動。 | 同章節的 `完成回報格式`。 | 下一批需補受眾視角，讓不同維護者知道該讀哪一段。 |
| 系統圖像 | 系統圖像收斂將前端顯示層、報告呈現層、機器契約層與維運決策層分開驗證與回報。 | 同章節的 `系統圖像收斂`。 | 下一批需補責任邊界，確定誰承擔未跑命令與剩餘風險。 |

最終操作收斂：

1. 驗證閘門先定位改動層，再決定命令、限制句或人工 review。
2. 完成回報必留本次宣稱層級、已補證據、仍不得解讀為、下一個可執行行動。
3. 系統圖像收斂要求同層證據支持同層宣稱，跨層宣稱必須升級驗證。

驗收標準：

1. 每個完成宣稱都有對應命令或限制句。
2. 高顯著性機器契約改動仍跑 parser、prompt、template 與 audit 回歸。
3. 低風險同層改動保持輕量三欄。
4. 不得把綜合優化第 1 次解讀為 HCS Plus 完成；下一步進入三習慣綜合優化第 2 次。

## 三習慣綜合優化第 2 次：證據來源、讀者角色與責任承接

本批把第一批的驗證閘門再往前補證據與讀者責任：先分清直接證據、間接證據、缺口證據與未跑命令，再讓不同維護者只讀必要入口，最後由改動者、reviewer、合併者承接證據來源、誤讀風險與剩餘風險。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 證據基礎 | 證據來源分級要求直接證據支持同層行為，間接證據只支持流程存在，缺口證據與未跑命令必須明列。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 2 次：證據來源、讀者角色與責任承接`。 | 下一批需降低證據分級被誤用為表格打勾的偏誤。 |
| 受眾 | 讀者角色分流把低風險 UI 維護者、報告呈現維護者、機器契約維護者、維運決策維護者與合併者分開。 | 同章節的 `讀者角色分流`。 | 下一批需用學習科學讓維護者快速學會入口。 |
| 責任 | 責任承接要求改動者負責證據來源與宣稱層級、reviewer 負責讀者是否會誤讀、合併者負責未跑命令與剩餘風險是否可接受。 | 同章節的 `責任承接`。 | 下一批需制定後續綜合優化策略，避免責任規則繼續膨脹。 |

系統應用方式：

1. 完成回報先分清直接證據、間接證據、缺口證據與未跑命令。
2. 讀者先定位自己是低風險 UI 維護者、報告呈現維護者、機器契約維護者、維運決策維護者或合併者。
3. 改動者承接證據來源與宣稱層級，reviewer 承接讀者誤讀風險，合併者承接未跑命令與剩餘風險。
4. 未跑命令不能消失，剩餘風險必須留到下一步，不得把使用者理解、安全或投資判斷外推。
5. 不得把綜合優化第 2 次解讀為 HCS Plus 完成；下一步進入三習慣綜合優化第 3 次。

## 三習慣綜合優化第 3 次：偏誤防線、速學入口與策略收斂

本批把第 2 次的證據與責任矩陣再往可採用性收斂：先用 #偏誤降低 防止矩陣被拿來打勾或漂白證據，再用 #學習科學 建立 10 秒定位、90 秒分流、5 分鐘復盤的速學入口，最後用 #制定策略 決定哪些規則保留、升級或刪減。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 偏誤降低 | 偏誤防線列出表格打勾偏誤、證據漂白偏誤、升級逃避偏誤與流程膨脹偏誤，讓 reviewer 能抓到矩陣被誤用的訊號。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 3 次：偏誤防線、速學入口與策略收斂`。 | 下一批需用目的檢查這些防線是否仍服務專案成果。 |
| 學習科學 | 速學入口把契約矩陣切成 10 秒定位、90 秒分流、5 分鐘復盤，降低維護者第一次使用時的記憶負擔。 | 同章節的 `速學入口`。 | 下一批需用效用檢查速學入口是否真的比完整矩陣更省成本。 |
| 制定策略 | 策略收斂要求低風險維持輕量、高顯著性必須升級、未跑命令留到下一步、策略膨脹必須刪減。 | 同章節的 `策略收斂`。 | 下一批需用合理性檢查哪些規則應保留，哪些應停止擴張。 |

系統應用方式：

1. reviewer 先檢查是否出現表格打勾偏誤、證據漂白偏誤、升級逃避偏誤或流程膨脹偏誤。
2. 新維護者先跑 10 秒定位、90 秒分流、5 分鐘復盤，不直接背完整矩陣。
3. 低風險維持輕量，高顯著性必須升級，未跑命令留到下一步。
4. 策略膨脹必須刪減；不能降低誤讀、補證據或縮短分流的規則不加入契約矩陣。
5. 不得把矩陣完成誤讀為證據充分，不得把速學入口替代完整契約，也不得把綜合優化第 3 次解讀為 HCS Plus 完成。

## 三習慣綜合優化第 4 次：目標校準、效用門檻與合理性審核

本批把前 3 次綜合優化重新綁回專案目的：先用 #目的 確認契約矩陣服務股票研究系統核心目標、使用者決策用途、維護者合併判斷與契約安全邊界，再用 #效用 設定規則要降低錯選模式、漏跑命令、跨層外推或維護成本，最後用 #合理性 檢查必要性、比例性、可驗證性與可逆性。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 目的 | 目標校準要求契約矩陣服務股票研究系統核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 4 次：目標校準、效用門檻與合理性審核`。 | 下一批需用限制條件決定哪些目標不能再擴張。 |
| 效用 | 效用門檻要求每條規則能降低錯選模式、漏跑命令、跨層外推或維護成本。 | 同章節的 `效用門檻`。 | 下一批需用決策樹把效用門檻轉成實際分流。 |
| 合理性 | 合理性審核固定必要性、比例性、可驗證性與可逆性；低效用規則必須刪減，高成本規則必須有證據。 | 同章節的 `合理性審核`。 | 下一批需用最佳化刪減成本高、證據弱或目的不明的規則。 |

系統應用方式：

1. 新增或保留矩陣規則前，先說明它服務哪個股票研究系統核心目標。
2. 規則必須通過效用門檻：降低錯選模式、漏跑命令、跨層外推或維護成本。
3. 高成本規則必須通過必要性、比例性、可驗證性與可逆性檢查。
4. 低效用規則必須刪減，高成本規則必須有證據，目的不明不能加入矩陣。
5. 不得讓契約矩陣服務文件本身，不得把效用推論寫成已證明改善，也不得把綜合優化第 4 次解讀為 HCS Plus 完成。

## 三習慣綜合優化第 5 次：限制邊界、分流決策與成本最佳化

本批把第 4 次的目的、效用與合理性落成可執行分流：先用 #限制條件 分出硬限制、軟限制、升級限制與停用限制，再用 #決策樹 排成改動層級、顯著性、證據缺口與處理方式四步，最後用 #最佳化 保留低風險輕量通道、合併重複規則、刪除低效用規則與延後無證據規則。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 限制條件 | 限制邊界把硬限制、軟限制、升級限制與停用限制分開，確定哪些規則不能新增、哪些情境能保留輕量通道。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 5 次：限制邊界、分流決策與成本最佳化`。 | 下一批需用來源品質檢查每個限制的依據是否可靠。 |
| 決策樹 | 分流決策固定四步：判斷改動層級、判斷顯著性、判斷證據缺口、選擇輕量/升級/拆分/刪減。 | 同章節的 `分流決策`。 | 下一批需用情境脈絡檢查同一決策在不同維護情境下是否仍適用。 |
| 最佳化 | 成本最佳化要求保留低風險輕量通道、合併重複規則、刪除低效用規則、延後無證據規則。 | 同章節的 `成本最佳化`。 | 下一批需用批判檢查最佳化是否犧牲高顯著性驗證。 |

系統應用方式：

1. 先套限制邊界：硬限制不得突破，軟限制可輕量，升級限制必須補命令或拆分，停用限制不得加入矩陣。
2. 再跑四步分流決策：改動層級、顯著性、證據缺口、處理方式。
3. 成本最佳化只能保留低風險輕量通道、合併重複規則、刪除低效用規則或延後無證據規則。
4. 不得為了最佳化而降低高顯著性驗證，不得把決策樹當成自動選測工具。
5. 不得把綜合優化第 5 次解讀為 HCS Plus 完成；下一步進入三習慣綜合優化第 6 次。

## 三習慣綜合優化第 6 次：來源分級、適用情境與批判反證

本批把第 5 次的限制與分流再往證據品質收斂：先用 #來源品質 分出高可信來源、可用但有限來源、不得作為完成證據與缺口來源，再用 #情境脈絡 限定低風險文件、報告語意、機器契約與維運決策的不同入口，最後用 #批判 要求每條規則先回答反證問題。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 來源品質 | 來源分級要求高可信來源只支持同層行為，可用但有限來源不得替代 pytest 或人工 review，不得作為完成證據的來源不能支持完成宣稱。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 6 次：來源分級、適用情境與批判反證`。 | 下一批需用估算校準目前規則有效性的把握程度。 |
| 情境脈絡 | 適用情境把低風險同層文件改動、報告呈現或使用者語意改動、機器契約或高顯著性改動、維運決策或排程風險改動分開。 | 同章節的 `適用情境`。 | 下一批需用信賴區間描述規則在不同情境下的信心邊界。 |
| 批判 | 批判反證要求每條規則先回答失效情境、證據是否只支持文件存在，以及是否有更小限制句或刪減方式。 | 同章節的 `批判反證`。 | 下一批需用詮釋框架防止反證結果被誤讀。 |

系統應用方式：

1. 完成宣稱先標明來源品質：高可信來源、可用但有限來源、不得作為完成證據或缺口來源。
2. 再確認適用情境：低風險文件、報告語意、機器契約或維運決策。
3. 情境不符必須改走升級或拆分，來源品質不足必須降級宣稱。
4. 批判反證未處理不得合併高顯著性規則，不得把歷史紀錄當成新證據。
5. 不得把適用情境擴張到 runtime 或使用者理解，也不得把綜合優化第 6 次解讀為 HCS Plus 完成。

## 三習慣綜合優化第 7 次：把握校準、信心邊界與解讀框架

本批把第 6 次的來源、情境與反證再校準成可回報的信心語言：先用 #估算 把完成宣稱分成高把握、中把握、低把握與不得宣稱，再用 #信賴區間 標示適用層級、證據覆蓋與剩餘不確定，最後用 #詮釋框架 把結果解讀成已驗證、有限支持、暫定假設或未證明。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 估算 | 把握估算要求完成宣稱先落到高把握、中把握、低把握或不得宣稱，低把握不得升格為完成。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 7 次：把握校準、信心邊界與解讀框架`。 | 下一批需用相關性檢查哪些規則真的互相支撐。 |
| 信賴區間 | 信心邊界要求每個宣稱列出適用層級、證據覆蓋與剩餘不確定，且不得跨過未測層。 | 同章節的 `信心邊界`。 | 下一批需用描述統計整理目前完成與缺口分布。 |
| 詮釋框架 | 解讀框架把結果標成已驗證、有限支持、暫定假設或未證明，防止讀者自行放大含義。 | 同章節的 `解讀框架`。 | 下一批需用顯著性判斷哪些訊號值得升級成規則。 |

系統應用方式：

1. 完成宣稱必須先填把握估算：高把握、中把握、低把握或不得宣稱。
2. 再填信心邊界：適用層級、證據覆蓋與剩餘不確定。
3. 最後填解讀框架：已驗證、有限支持、暫定假設或未證明。
4. 低把握不得升格為完成，信心邊界不得跨過未測層，解讀框架不得替代 pytest、人工 review 或 runtime 驗證。
5. 不得把估算寫成精確量化承諾，也不得把綜合優化第 7 次解讀為 HCS Plus 完成。

## 三習慣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻

本批把第 7 次的把握、邊界與解讀再整理成規則取捨方式：先用 #相關性 分出強支撐、弱支撐、衝突支撐與無關，再用 #描述統計 摘要完成分布、缺口分布、驗證分布與風險分布，最後用 #顯著性 決定升級訊號、保留訊號、降級訊號與刪減訊號。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 相關性 | 關聯檢核要求只有強支撐且跨多個來源層級的關聯才能升級成矩陣規則，弱支撐、衝突支撐與無關都要限制或拆分。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻`。 | 下一批需用機率檢查回報語言是否過度確定。 |
| 描述統計 | 分布摘要只描述目前文件與測試覆蓋，分成完成分布、缺口分布、驗證分布與風險分布。 | 同章節的 `分布摘要`。 | 下一批需用迴歸檢查局部改善是否可能回到舊問題。 |
| 顯著性 | 顯著性門檻把訊號分成升級、保留、降級與刪減，避免任何單一觀察直接升級成規則。 | 同章節的 `顯著性門檻`。 | 下一批需用謬誤檢查相關性、分布與顯著性是否被誤讀。 |

系統應用方式：

1. 新增或合併規則前，先做關聯檢核：強支撐、弱支撐、衝突支撐或無關。
2. 再做分布摘要：完成分布、缺口分布、驗證分布與風險分布。
3. 最後套顯著性門檻：升級訊號、保留訊號、降級訊號或刪減訊號。
4. 只有強支撐且跨多個來源層級的關聯才能升級成矩陣規則；弱支撐只能保留為有限支持。
5. 分布摘要只能描述目前文件與測試覆蓋，不得把相關性解讀為因果，不得把描述統計解讀為改善證明，也不得把綜合優化第 8 次解讀為 HCS Plus 完成。

## 三習慣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線

本批把第 8 次的關聯、分布與顯著性再轉成防誤讀語言：先用 #機率 分出高可能、中可能、低可能與未知或不得推定，再用 #迴歸 檢查是否回到過度宣稱、跨層外推、流程膨脹或弱證據升級，最後用 #謬誤 阻止相關當因果、測試當 runtime 安全、文件完整當使用者理解、歷史紀錄當新證據。

| 綜合習慣 | 核心收斂 | 落地位置 | 下一個缺口 |
|---|---|---|---|
| 機率 | 概率語言要求高可能、中可能、低可能與未知或不得推定分開，且不得使用精確百分比包裝弱證據。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線`。 | 下一批需用合理性檢查十次綜合優化是否仍服務核心目標。 |
| 迴歸 | 迴歸風險列出回到過度宣稱、跨層外推、流程膨脹與弱證據升級時的降級或拆分動作。 | 同章節的 `迴歸風險`。 | 下一批需用可驗證性固定最終完成證據與測試門檻。 |
| 謬誤 | 謬誤防線阻止相關不等於因果、通過測試不等於 runtime 安全、文件完整不等於使用者理解、歷史紀錄不等於新證據。 | 同章節的 `謬誤防線`。 | 下一批需用制定策略列出完成後的維護與交接方式。 |

系統應用方式：

1. 回報概率前，先選概率等級：高可能、中可能、低可能或未知或不得推定。
2. 再檢查迴歸風險：是否回到過度宣稱、跨層外推、流程膨脹或弱證據升級。
3. 最後套謬誤防線：相關不等於因果，通過測試不等於 runtime 安全，文件完整不等於使用者理解，歷史紀錄不等於新證據。
4. 不得把概率語言寫成保證，不得把迴歸風險寫成已修復，不得把謬誤清單替代 pytest、人工 review 或 runtime 驗證。
5. 概率語言、迴歸風險與謬誤防線都只能限制宣稱，不得把綜合優化第 9 次解讀為 HCS Plus 完成。

## 三習慣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略

本批把前九次綜合優化收斂成完成條件：先用 #合理性 確認契約矩陣仍服務核心目標、使用者決策用途、維護者合併判斷與契約安全邊界，再用 #可驗證性 固定聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節，最後用 #制定策略 寫下完成後維護方式。

| 綜合習慣 | 核心收斂 | 落地位置 | 完成後維護 |
|---|---|---|---|
| 合理性 | 合理性收尾確認十次綜合優化只完成文件與測試契約收斂，不代表 runtime 安全、投資結果改善或使用者理解已驗證。 | `docs/pipeline-mode-contract.md` 的 `契約矩陣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略`。 | 定期複檢核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。 |
| 可驗證性 | 驗證門檻要求聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節共同支持完成宣稱。 | 同章節的 `驗證門檻`。 | 任何新增契約章節或完成宣稱都要補對應測試。 |
| 制定策略 | 維護策略採文件與測試契約優先、例外升級與定期複檢。 | 同章節的 `維護策略`。 | 觸及 parser、prompt、template、audit、runtime、交易語氣或使用者理解宣稱時必須升級。 |

系統應用方式：

1. 完成宣稱先檢查合理性：是否仍服務核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。
2. 再檢查可驗證性：聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節是否都支持。
3. 最後套制定策略：文件與測試契約優先、例外升級、定期複檢。
4. 完成只代表 HCS Plus 自主優化流程完成，不代表 runtime 安全或使用者理解已驗證。
5. 不得新增 runtime、遙測或自動選測工具；第 10 次只收尾合理性、可驗證性與制定策略。

## HCS Plus 自主優化完成摘要

完成狀態：完成

已完成十次 3 思考習慣綜合優化。

最終專案內容：

- `docs/pipeline-mode-contract.md`：前後端模式契約與十次綜合護欄。
- `docs/hcs-plus-optimization-state.md`：專案目標、決策紀錄、未解問題、三輪進度、十次綜合進度與完成摘要。
- `docs/hcs-plus-strict-habit-log.md`：每個思考習慣與十次綜合優化的 strict log。
- `tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py`：文件契約與 HCS 狀態測試。

決策紀錄：

- 維持文件與測試契約優先。
- 不新增 runtime、遙測或自動選測工具。
- 高顯著性、跨層、parser、prompt、template、audit、交易語氣或使用者理解宣稱必須升級。
- 完成只代表 HCS Plus 自主優化流程完成。

風險與驗收標準：

- 風險：runtime 安全、使用者理解、投資結果改善與資料新鮮度未因此自動證明。
- 驗收：聚焦測試通過、回歸集合通過、diff check 通過、D89 到 D98 完整、綜合優化 1 到 10 完整、strict log 含完成後下一步。
- 限制：不得把文件完整、測試通過、歷史紀錄或完成摘要外推成 runtime 或使用者行為證據。

下一步可執行行動：

- 完成後維護 / 定期複檢契約矩陣。
- 若後續修改 runtime、parser、prompt、template、audit 或報告交易語氣，先補對應測試與人工 review。
- 若後續新增 pipeline 或報告模式，更新契約章節、狀態表、strict log 與文件契約測試。

## 優化進度

| 輪次 | 模式 | 狀態 | 已修改 |
|---|---|---|---|
| 1 | 批判思考 | 完成 | `docs/frontend-design-checkpoints.md`、本狀態表 |
| 1 | 創意思考 | 完成 | 首頁 pipeline 模式用途文案 |
| 1 | 溝通思考 | 完成 | 首頁副標 |
| 1 | 互動思考 | 完成 | pipeline intent 即時提示 |
| 2 | 批判思考 | 完成 | 前端 mode metadata 單一來源合約 |
| 2 | 創意思考 | 完成 | `pipelineChoices()` / `pipelineCtaLabel()` 共用 helper |
| 2 | 溝通思考 | 完成 | 歷史追蹤、filter、watchlist select 使用共用模式語意 |
| 2 | 互動思考 | 完成 | watchlist 清單顯示可讀模式名稱 |
| 3 | 批判思考 | 完成 | 前後端模式漂移風險文件化 |
| 3 | 創意思考 | 完成 | 低成本模式契約文件 |
| 3 | 溝通思考 | 完成 | 每種模式報告模板拆解 |
| 3 | 互動思考 | 完成 | 下一步與 watchlist/報告用途對照 |
| 綜合 | 可驗證性 + 溝通設計 + 系統圖像 | 完成 | 前端設計檢查點納入模式契約 |

## 嚴格單項輪巡進度

| 輪次 | 分類 | 批次 | 狀態 | 已修改 |
|---|---|---|---|---|
| 1 | 批判思考 | #拆解問題、#問對問題、#差距分析、#變數分析、#偏誤辨識 | 完成 | `docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py`、本狀態表 |
| 1 | 批判思考 | #偏誤降低、#決策樹、#目的、#效用 | 完成 | `README.md`、`docs/api.md`、`docs/pipeline-mode-contract.md`、`tests/test_docs_contract.py`、嚴格輪巡附件 |
| 1 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 | `backend/static/active_jobs_panel.js`、`backend/static/ops_workspace.js`、`tests/test_static_history_filters.py`、嚴格輪巡附件 |
| 1 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 | `backend/static/performance_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 | `backend/static/report_preview_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 | `backend/static/operator_summary_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 | `backend/static/api_quota_panel.js`、`backend/static/operator_summary_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 批判思考 | #合理性、#可驗證性 | 完成 | `docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py`、本狀態表 |
| 1 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 | `docs/pipeline-mode-contract.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 | `docs/pipeline-mode-contract.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 | `backend/static/report_compare_panel.js`、`backend/static/history_workspace.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 創意思考 | #觀察研究、#研究複製 | 完成 | `backend/static/report_compare_panel.js`、`backend/static/history_workspace.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 | `docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #談判、#說服、#形塑行為 | 完成 | `backend/static/report_compare_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 | `backend/static/report_preview_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 | `backend/static/index.html`、`backend/static/report_preview_panel.js`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 1 | 互動思考 | #自我覺察、#制定策略 | 完成 | `backend/static/index.html`、`tests/test_static_history_filters.py`、`tests/test_frontend_visual_optional.py`、`tests/test_hcs_plus_state.py`、嚴格輪巡附件 |
| 2 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #決策樹、#目的、#效用 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 批判思考 | #合理性、#可驗證性 | 完成 | `docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_hcs_plus_state.py` |
| 2 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 創意思考 | #觀察研究、#研究複製 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #談判、#說服、#形塑行為 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 2 | 互動思考 | #自我覺察、#制定策略 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #決策樹、#目的、#效用 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 批判思考 | #合理性、#可驗證性 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |
| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 | `docs/pipeline-mode-contract.md`、`docs/hcs-plus-optimization-state.md`、`docs/hcs-plus-strict-habit-log.md`、`tests/test_docs_contract.py`、`tests/test_hcs_plus_state.py` |

## 第 1 輪摘要

已改善內容：

- 把設計審查從一次性截圖轉成 repo 內可追蹤檢查點。
- 把首頁模式選擇從「模式名稱 + Agent 數」推進到「決策用途 + Agent 數」。
- 把副標從內部技術語言改為使用者工作成果。
- 在模式切換時提供即時 intent 提示，讓操作者知道該模式適合什麼判斷。

已落地修改：

- `docs/hcs-plus-optimization-state.md`
- `docs/frontend-design-checkpoints.md`
- `backend/static/index.html`
- `backend/static/app.js`
- `backend/static/ui_helpers.js`
- `backend/static/styles/forms_controls.css`
- `tests/test_static_history_filters.py`

尚未解決的高風險問題：

- 目前模式 intent 只在首頁顯示，歷史報告、watchlist、market screener 的模式語意仍分散在不同 JS 檔案。
- 前端設計品質仍主要靠靜態合約與人工截圖，尚未形成正式視覺回歸流程。
- `DESIGN.md` 尚未建立，字級、密度、色彩與資料視覺化規則仍散落在 CSS 與測試中。

第 2 輪優先方向：

- 批判思考：檢查模式語意是否有多處來源，降低漂移風險。
- 創意思考：探索不大改架構的方式，讓 mode profile 成為前端共用資料。
- 溝通思考：改善歷史報告與 watchlist 的模式文案一致性。
- 互動思考：補強使用者從待處理項目進入正確下一步的回饋。

## 第 2 輪摘要

已改善內容：

- 將前端模式顯示資料收斂到 `StockAgentUi.PIPELINE_META`，新增 `pipelineChoices()` 與 `pipelineCtaLabel()`。
- 首頁 CTA、首頁模式選項、歷史報告 filter、market screener mode picker、watchlist select 與 watchlist 清單改用共用模式語意。
- 歷史追蹤卡不再維護自己的模式 label 表，降低後續模式命名漂移。
- watchlist 清單不再只顯示 `V1/V2/V3/V4`，改顯示「模式 A · 學術深度派」等可讀名稱。

已落地修改：

- `backend/static/ui_helpers.js`
- `backend/static/app.js`
- `backend/static/history_panel.js`
- `backend/static/market_screener_panel.js`
- `backend/static/watchlist_panel.js`
- `backend/static/ops_workspace.js`
- `backend/static/index.html`
- `tests/test_static_history_filters.py`

驗證證據：

- `tests/test_static_history_filters.py`：27 passed。
- 新增合約：`test_pipeline_mode_frontend_labels_share_single_metadata_source`。

尚未解決的高風險問題：

- 前後端模式定義尚未完全單一來源；後端仍由 `pipeline_modes.py` 定義 pipeline 行為。
- watchlist 顯示已改善，但從 operator action 直接進入正確下一步的引導仍可再強化。

第 3 輪優先方向：

- 批判思考：檢查前後端 pipeline 定義是否需要文件化同步規則。
- 創意思考：補一份低成本設計/模式契約文件，而不是大改架構。
- 溝通思考：讓報告模板與前端模式語意有可查對照。
- 互動思考：補強操作者從警示、待處理、重跑到下一步的行動提示。

## 第 3 輪摘要

已改善內容：

- 新增 `docs/pipeline-mode-contract.md`，把 `v1` 到 `v4` 的前端決策用途、後端模式、報告模板、摘要標題、決策標題、核心問題與下一步拆開。
- 將模式契約寫入 `docs/frontend-design-checkpoints.md`，讓 UI 修改時同時檢查模式語意與報告模板。
- 補上 `test_pipeline_mode_contract_documents_templates_and_decision_intents`，用後端 pipeline definition 與 report template profile 反向驗證文件內容。

已落地修改：

- `docs/pipeline-mode-contract.md`
- `docs/frontend-design-checkpoints.md`
- `docs/hcs-plus-optimization-state.md`
- `tests/test_report_mode_templates.py`

驗證證據：

- `tests/test_report_mode_templates.py`：4 passed。

尚未解決的高風險問題：

- 前端 `PIPELINE_META` 仍未由後端自動產生；目前透過測試與契約文件降低漂移。
- 尚未加入截圖式視覺回歸到 CI。

## 三習慣綜合優化

綜合視角：

- `#可驗證性`：每個模式的報告模板與決策用途必須有測試與文件可查。
- `#溝通設計`：操作者看到的是「該模式能幫我做什麼決策」，而不是內部 Agent 結構。
- `#系統圖像`：前端、後端 pipeline、報告模板、watchlist 與歷史追蹤共同構成一個決策系統，不能各自命名。

最終優化：

- 建立前端共用 mode metadata。
- 建立前後端模式契約文件。
- 把模式契約納入前端設計檢查點。
- 用靜態合約測試鎖定 UI、文件與報告模板。

驗收標準：

- 前端模式 label 與 CTA 由 `StockAgentUi.PIPELINE_META` 驅動。
- watchlist、market screener、歷史追蹤不再維護獨立模式語意表。
- `docs/pipeline-mode-contract.md` 必須包含每個模式的後端 label、short label、template id、summary heading、decision heading、core question 與決策用途。
- 相關測試需通過後才可視為本輪完成。

下一步：

- 若要進一步降低漂移，可把前端 mode metadata 改由後端輸出 JSON 或在 build/test 階段生成。
- 若要提升視覺可靠度，可把設計審查截圖或 Playwright 視覺回歸納入 CI。

- D795：P3-689 補強 data trust source record count boolean scalar presence guard：`data_trust_audit.has_value()` 將 bool scalar 視為 missing evidence，避免 `true`/`false` 這類 malformed numeric/source 欄位被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN boolean scalar 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D796：P3-690 補強 data trust source record count non-finite numeric presence guard：`data_trust_audit.has_value()` 將 `NaN` / `Infinity` / `-Infinity` scalar 視為 missing evidence，避免 malformed market numeric 欄位被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN non-finite numeric 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D797：P3-691 補強 data trust source record count Decimal non-finite presence guard：`data_trust_audit.has_value()` 將 `Decimal("NaN")` / `Decimal("Infinity")` / `Decimal("-Infinity")` 視為 missing evidence，同時保留 `Decimal("0")` 這類有限數值 evidence，避免 decimal market numeric 欄位膨脹 merged evidence count；RED→GREEN Decimal non-finite 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D798：P3-692 補強 data trust source record count binary scalar presence guard：`data_trust_audit.has_value()` 將 `bytes` / `bytearray` / `memoryview` scalar 視為 missing evidence，避免 binary market/source 欄位被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN binary scalar 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D799：P3-693 補強 data trust source record count complex scalar presence guard：`data_trust_audit.has_value()` 將 `complex` scalar 視為 missing evidence，避免 complex-number market/source 欄位被誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN complex scalar 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D800：P3-694 補強 data trust source record count non-finite numeric string presence guard：`data_trust_audit.has_value()` 將 `"NaN"` / `"Infinity"` / `"-Infinity"` 等字串型非有限數值視為 missing evidence，同時保留 `"0"` 這類有限數值字串 evidence，避免 string market numeric 欄位膨脹 merged evidence count；RED→GREEN non-finite numeric string 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D801：P3-695 補強 data trust source record count placeholder string presence guard：`data_trust_audit.has_value()` 將 `"None"` / `"null"` / `"--"` 等 placeholder string 視為 missing evidence，同時保留 `"0"` 這類有限數值字串 evidence，避免 placeholder market/source 欄位膨脹 merged evidence count；RED→GREEN placeholder string 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D802：P3-696 補強 data trust source record count set-aware presence guard：`data_trust_audit.has_value()` 對 `set` / `frozenset` 做 item-aware value presence 判斷，避免空 set history/source 容器被 scalar fallback 誤算成有效 source evidence 而膨脹 merged evidence count；RED→GREEN empty set 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D803：P3-697 補強 data trust source record count set source row batch guard：`data_trust_audit.source_record_count()` 在 default/custom source fallback 中將 `set` / `frozenset` source values 視為 row batches，避免 unordered custom enrichment rows 被壓成單一 present scalar 而低估 merged evidence count；RED→GREEN set source row batch 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D804：P3-698 補強 data trust audit entry record count bool guard：`data_trust_audit._safe_int()` 將 boolean `record_count` 視為 malformed count，避免 source audit row 的 `true` / `false` 被 Python int conversion 轉成 1/0 而膨脹來源證據筆數；RED→GREEN record_count bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D805：P3-699 補強 data trust audit entry record count fractional numeric guard：`data_trust_audit._safe_int()` 改用 shared `mapping_fields.safe_int()`，將非整數 float/Decimal 類 `record_count` 視為 malformed count，避免 fractional source audit rows 被截斷成有效來源證據筆數；RED→GREEN fractional record_count 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D806：P3-700 補強 data trust audit entry duration bool override guard：`data_trust_audit.duration_ms()` 忽略 boolean `duration_ms` override 並回落到 started/finished epoch delta，避免 `true` / `false` source audit duration 欄位取代有效來源抓取時間證據；RED→GREEN duration bool override 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D807：P3-701 補強 data trust audit entry duration non-finite override guard：`data_trust_audit.duration_ms()` 忽略 `NaN` / `Infinity` / `-Infinity` duration override 並回落到 started/finished epoch delta，避免非有限來源抓取時間欄位中斷 source audit entry 建立或取代有效 timing evidence；RED→GREEN duration non-finite override 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D808：P3-702 補強 data trust audit entry duration non-finite epoch guard：`data_trust_audit.duration_ms()` 與 `iso_from_epoch()` 忽略 `NaN` / `Infinity` / `-Infinity` started/finished epoch timestamps，避免非有限 epoch 欄位中斷 source audit entry 建立或產生 synthetic fetch timing evidence；RED→GREEN duration non-finite epoch 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D809：P3-703 補強 data trust audit entry fetched-at text guard：`data_trust_audit.build_source_audit_entry()` 在採用 `fetched_at` 前先走 shared text conversion，讓 boolean/binary/memory-view fetched-at 值回落到有效 epoch timestamp，避免 malformed fetched-at 欄位寫進 source audit rows 或壓掉 valid timing evidence；RED→GREEN fetched_at safe-text 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D810：P3-704 補強 data trust audit entry fetched-at epoch fallback guard：`data_trust_audit.build_source_audit_entry()` 先分別驗證 `fetched_at_epoch` 與 `finished_at_epoch` 再 fallback，避免 boolean 或 `NaN` / `Infinity` fetched-at epoch 先被 truthiness 選中而壓掉有效 finished timestamp；RED→GREEN fetched_at epoch fallback 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D811：P3-705 補強 data trust audit entry finished-at current-time fallback guard：`data_trust_audit.build_source_audit_entry()` 在 current-time fallback 前先用 epoch validator 檢查 `finished_at_epoch`，避免 boolean、非正數或 `NaN` / `Infinity` finished timestamp 讓 source audit `fetched_at` 變成空值而削弱報告資料來源時序證據，同時保留 duration 只由原始有效 timing evidence 計算；RED→GREEN finished_at fallback 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D812：P3-706 補強 data trust audit entry boolean text guard：`data_trust_audit._safe_bool()` 在 truthiness fallback 前解析 explicit false/true text，避免 `"false"`、`"0"`、`"no"`、`"off"` cache-hit / stale 欄位被 Python truthiness 誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN false-text bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D813：P3-707 補強 data trust audit entry boolean binary guard：`data_trust_audit._safe_bool()` 在 truthiness fallback 前將 `bytes` / `bytearray` / `memoryview` 視為 malformed bool，避免非空 binary cache-hit / stale 欄位被 Python truthiness 誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN binary bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D814：P3-708 補強 data trust audit entry boolean non-finite numeric guard：`data_trust_audit._safe_bool()` 在 truthiness fallback 前將 `NaN` / `Infinity` float 與 non-finite `Decimal` 視為 malformed bool，避免非有限 numeric cache-hit / stale 欄位被 Python truthiness 誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN non-finite bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D815：P3-709 補強 data trust audit entry boolean complex guard：`data_trust_audit._safe_bool()` 在 truthiness fallback 前將 `complex` 視為 malformed bool，避免 complex cache-hit / stale 欄位被 Python truthiness 誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN complex bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D816：P3-710 補強 data trust audit entry boolean container guard：`data_trust_audit._safe_bool()` 在 truthiness fallback 前將 `list` / `tuple` / `set` / `frozenset` / mapping 視為 malformed bool，避免非空容器型 cache-hit / stale 欄位被 Python truthiness 誤報成 true source audit evidence，同時保留 source record count 的容器 evidence 計數語義，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN container bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D817：P3-711 補強 data trust audit entry boolean numeric range guard：`data_trust_audit._safe_bool()` 將有限 numeric/Decimal cache-hit / stale 欄位收斂為只接受明確 `0` 或 `1`，避免 `0.5`、`-0.5` 或其他 out-of-range 數字被 Python truthiness 誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN numeric bool range 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D818：P3-712 補強 data trust audit entry boolean rational numeric guard：`data_trust_audit._safe_bool()` 將標準 `numbers.Real` numeric scalar 納入 explicit `0` / `1` 布林契約，避免 `Fraction(1, 2)`、`Fraction(2, 1)` 這類 rational cache-hit / stale 欄位掉回 Python truthiness 而誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN rational bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D819：P3-713 補強 data trust audit entry boolean numeric text guard：`data_trust_audit._safe_bool()` 在字串分支解析 numeric text，將 `"0.0"` / `"1.0"` 收斂為明確布林，並將 `"0.5"`、`"2"`、`"-1"`、`"NaN"`、`"Infinity"` 視為 malformed bool，避免數字字串型 cache-hit / stale 欄位掉回非空字串 truthiness 而誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN numeric text bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D820：P3-714 補強 data trust audit entry boolean free-form text guard：`data_trust_audit._safe_bool()` 將非 explicit true/false、非 numeric 0/1 的自由文字 cache-hit / stale 欄位視為 malformed bool，避免 `"cached"`、`"stale"`、`"unknown"`、`"N/A"` 等非空字串掉回 Python truthiness 而誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN free-form bool text 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D821：P3-715 補強 data trust audit entry boolean overflowing real-number guard：`data_trust_audit._safe_bool()` 在 `numbers.Real` 分支捕捉 `float()` 轉換 overflow/type/value error，將超大 `int` 或 `Fraction` cache-hit / stale 欄位視為 malformed bool，避免 oversized numeric 欄位中斷 source audit entry 建立或誤報成 true source audit evidence，降低報告資料來源 cache/stale 狀態誤標風險；RED→GREEN overflowing real bool 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D822：P3-716 補強 data trust audit entry duration overflowing override guard：`data_trust_audit.duration_ms()` 在 duration override 轉 float 時捕捉 overflow/type/value error，忽略超大 millisecond override 並回落到有效 started/finished epoch delta，避免 oversized duration 欄位中斷 source audit entry 建立或取代有效來源抓取時間證據；RED→GREEN overflowing duration override 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D823：P3-717 補強 data trust audit entry duration overflowing epoch guard：`data_trust_audit.duration_ms()` 與 `iso_from_epoch()` 在 epoch timestamp 轉 float 時捕捉 overflow/type/value error，忽略超大 started/finished timestamp，避免 oversized epoch 欄位中斷 source audit entry 建立或產生 synthetic fetch timing evidence；RED→GREEN overflowing duration epoch 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D824：P3-718 補強 data trust audit entry fetched-at epoch range guard：`data_trust_audit.iso_from_epoch()` 在 `datetime.fromtimestamp()` 階段捕捉 platform timestamp range error，將 out-of-range fetched-at epoch 視為 malformed 並回落到 valid finished timestamp，避免 source audit entry 建立中斷或壓掉有效來源完成時間證據；RED→GREEN fetched_at epoch range 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D825：P3-719 補強 data trust audit entry duration out-of-range epoch guard：`data_trust_audit.duration_ms()` 在 started/finished delta 計算前用 `iso_from_epoch()` 驗證 platform timestamp range，避免 out-of-range epoch 欄位被有限 float 差值轉成巨大 synthetic duration evidence；RED→GREEN out-of-range duration epoch 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D826：P3-720 補強 data trust source record count overflowing numeric scalar guard：`data_trust_audit.has_value()` 對 `numbers.Real` scalar 先捕捉 `float()` overflow/type/value error，再只接受 finite numeric evidence，避免 oversized integer 或 rational market fields 中斷 merged evidence count 或被誤算成有效來源證據；RED→GREEN overflowing source numeric 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D827：P3-721 補強 data trust source record count set iterator fallback：`data_trust_audit.source_record_count()` 與 `has_value()` 的 set/frozenset 分支改用 `_set_items()`，在自訂 iterator 失效時退回 native set/frozenset iterator，避免 malformed set row batch 中斷 merged evidence count 或抹除有效 custom source rows；RED→GREEN set iterator fallback 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D828：P3-722 補強 data trust string list non-finite numeric guard：`data_trust_audit.string_list()` 在轉換 trust notes、reason codes、stale/critical sources 與 score reasons 前丟棄 `NaN` / `Infinity` numeric items，避免非有限數字被轉成 `"nan"` / `"inf"` 顯示於報告、prompt 或 trust metadata；RED→GREEN non-finite text-list 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D829：P3-723 補強 data trust score boolean guard：`data_trust_scoring.normalize_data_trust()` 在既有 trust score 轉 float 前將 boolean score 視為 malformed，改走 status-derived fallback，避免 `true` / `false` 被合成 1 或 0 分並污染報告信心 metadata；RED→GREEN boolean score 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D830：P3-724 補強 data trust last-market timestamp safe-text guard：`data_trust_scoring.normalize_data_trust()` 對 `last_market_data_at` 先走 shared text conversion 並 trim，malformed boolean/binary/memory-view timestamp 轉為 `None`，避免非時間值漏進報告信心 metadata；RED→GREEN last-market timestamp 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D831：P3-725 補強 data trust provider SLA alert list normalization：`data_trust_scoring.normalize_data_trust()` 對 `provider_sla_alerts` 使用 dict-list safe conversion，讓 tuple 或 native-backed alert collections 保留有效 provider health metadata，避免 iterator 漂移中斷 report confidence normalization 或抹除來源健康度證據；RED→GREEN provider SLA alert list 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D832：P3-726 補強 data trust build source data normalization：`data_trust_scoring.build_data_trust()` 在 scoring 前使用 mapping- 與 dict-list-safe conversion 正規化 root source data、`source_freshness` 與 `source_audit`，讓 malformed root accessor、tuple source audit 或 native-backed audit collections 保留有效來源證據，避免 report confidence scoring 中斷或降成 unknown；RED→GREEN build data trust 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D833：P3-727 補強 data trust source freshness child map normalization：`data_trust_scoring.build_data_trust()`、`_stale_sources_from()` 與 `last_market_data_at()` 對 `source_freshness` nested child maps 使用 mapping-safe conversion，讓 malformed nested freshness accessors 不再中斷 stale-source scoring，並保留有效 market-data freshness timestamp；RED→GREEN source freshness child map 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D834：P3-728 補強 data trust source freshness stale flag bool safety：`data_trust_scoring._stale_sources_from()` 對 `source_freshness` 與 latest audit stale flags 使用 bool-safe conversion，讓 malformed stale truthiness 不再中斷 report confidence scoring，也不會把有效 source audit evidence 誤分類成 stale；RED→GREEN freshness stale flag 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D835：P3-729 補強 data trust data source notes presence normalization：`data_trust_scoring.build_data_trust()` 對 `data_source_notes` 使用 string-list conversion 與 typed presence helper，讓 malformed note truthiness 不再中斷 report confidence scoring，也避免 object repr 形成 synthetic data-source limitation metadata；RED→GREEN data source notes 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D836：P3-730 補強 data trust latest audit row mapping normalization：`data_trust_scoring.latest_audit_by_source()` 對 source audit rows 使用 mapping-safe conversion，讓 malformed row accessors 不再中斷 latest-source selection 或抹除有效 source audit status evidence；RED→GREEN latest audit row 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D837：P3-731 補強 data trust optional source status row normalization：`data_trust_scoring.optional_sources_with_status()` 對 latest audit root map 與 optional source audit rows 使用 mapping-safe conversion 與 string-safe status comparison，讓 malformed optional audit row accessors 不再中斷 optional-source reason code projection，也避免核心來源被推進 optional status buckets；RED→GREEN optional source status 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D838：P3-732 補強 data trust usable critical data audit normalization：`data_trust_scoring.has_usable_critical_data()` 對 latest audit root map 與核心來源 audit rows 使用 mapping-safe conversion 與 string-safe status comparison，讓 malformed critical audit accessors 不再中斷 error-vs-partial trust status selection，並保留有效核心來源可用性證據；RED→GREEN usable critical data 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D839：P3-733 補強 data trust source audit status comparison normalization：`data_trust_scoring.build_data_trust()` 與相關 status helper 使用 string-safe status comparison 判斷 source audit rows，讓 malformed-but-valid audit status text 不再被誤分類成 fresh，避免核心來源失敗被隱藏於 report confidence metadata；RED→GREEN audit status comparison 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D840：P3-734 補強 data trust last-market timestamp fallback normalization：`data_trust_scoring.last_market_data_at()` 對 source freshness、root market timestamp 與 market audit timestamp 候選值使用 string-safe conversion 後再 fallback，讓 malformed timestamp truthiness 不再中斷 report confidence metadata，並保留有效 market freshness time evidence；RED→GREEN last-market timestamp 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D841：P3-735 補強 data trust post-SLA metadata final-score normalization：`data_trust_scoring.build_data_trust()` 在 provider SLA policy 回傳後先使用 mapping-safe conversion，再進行 final score calculation，讓 malformed provider-SLA return accessors 不再中斷 report confidence finalization 或抹除有效 trust status / reason evidence；RED→GREEN post-SLA final score 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D842：P3-736 補強 data trust provider SLA policy failure fallback：`data_trust_scoring.build_data_trust()` 在 provider SLA policy 例外時回落到 base trust，再進行 final score calculation，讓 provider SLA policy failures 不再中斷 report confidence finalization 或抹除已計算的 source audit trust evidence；RED→GREEN provider SLA failure fallback 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D843：P3-737 補強 data trust provider SLA policy failure immutable fallback：`data_trust_scoring.build_data_trust()` 將 provider SLA policy input 與 base trust snapshot 分離並複製 list 欄位，讓 provider SLA policy 先 in-place mutation 後例外時仍回落到未污染的 base trust，再進行 final score calculation；RED→GREEN provider SLA mutation failure fallback 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D844：P3-738 補強 data trust post-SLA canonical status normalization：`data_trust_scoring.build_data_trust()` 在 provider SLA policy 回傳與 fallback 後、final score calculation 前正規化 trust `status`，讓 malformed provider SLA status values 不再外溢成非 canonical report confidence state，也避免 status 與 score semantics 漂移；RED→GREEN post-SLA status 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D845：P3-739 補強 data trust post-SLA list metadata output normalization：`data_trust_scoring.build_data_trust()` 在 final score calculation 前將 post-SLA `critical_failures`、`stale_sources`、`notes` 與 `reason_codes` 透過 string-list conversion 寫回 trust payload，讓 malformed provider SLA list metadata 不再以非 list 形狀外溢到 report confidence metadata，同時 score semantics 與輸出 evidence 保持一致；RED→GREEN post-SLA list metadata 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D846：P3-740 補強 data trust post-SLA last-market timestamp output normalization：`data_trust_scoring.build_data_trust()` 在 final score output 前使用 shared text conversion 正規化 post-SLA `last_market_data_at`，讓 malformed provider SLA timestamp values 不再以非 string / untrimmed 形狀外溢到 report confidence metadata；RED→GREEN post-SLA timestamp 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D847：P3-741 補強 data trust post-SLA provider alert output normalization：`data_trust_scoring.build_data_trust()` 在 final score output 前使用 dict-list conversion 正規化 post-SLA `provider_sla_alerts`，讓 malformed provider SLA alert collections 不再以自訂 iterator / 非 list 形狀外溢到 report confidence metadata；RED→GREEN post-SLA provider alert 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D848：P3-742 補強 data trust normalization mapping-safe payload handling：`data_trust_scoring.normalize_data_trust()` 在 field normalization 前使用 mapping-safe conversion 接受有效 Mapping payload，讓 immutable / read-only trust wrappers 不再被誤判成 missing report confidence metadata；RED→GREEN mapping-safe trust payload 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D849：P3-743 補強 data trust build mapping-safe source payload handling：`data_trust_scoring.build_data_trust()` 在 source scoring 入口使用 mapping-safe conversion 接受有效 Mapping payload，讓 immutable / read-only source data wrappers 不再被誤判成 missing report confidence evidence；RED→GREEN mapping-safe source payload 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D850：P3-744 補強 data trust snapshot existing-trust mapping-safe selection：`data_trust_snapshot.build_data_snapshot()` 在選用既有 `data_trust` 時使用 mapping-safe conversion，讓 immutable / read-only trust wrappers 不再被誤判成 missing report confidence metadata 並重算成 unknown；RED→GREEN snapshot existing trust mapping 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D851：P3-745 補強 data trust snapshot source-data mapping-safe selection：`data_trust_snapshot.build_data_snapshot()` 在 trust scoring 前使用 mapping-safe conversion 接受有效 `data` Mapping payload，讓 immutable / read-only source data wrappers 不再抹除 source audit evidence 並將 snapshot data trust 誤算成 unknown；RED→GREEN snapshot source data mapping 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D852：P3-746 補強 data trust snapshot root-context mapping-safe selection：`data_trust_snapshot.build_data_snapshot()` 在 metadata selection 與 trust scoring 前使用 mapping-safe conversion 接受有效 root context Mapping payload，讓 immutable / read-only context wrappers 不再中斷 snapshot generation 或抹除 report confidence evidence；RED→GREEN snapshot root context mapping 單測、data-trust focused 驗證與 report-quality 回歸組通過。

- D853：P3-747 補強 prompt data trust mapping-safe handoff：`prompt_builder._prompt_data_trust()` 在輸出 prompt JSON 前使用 mapping-safe conversion 接受有效 `data_trust` Mapping payload，讓 immutable / read-only trust wrappers 不再被誤判成 missing report confidence metadata，避免模型指令看不到資料可信度狀態與限制理由；RED→GREEN prompt data trust mapping 單測、prompt/data-trust focused 驗證與 report-quality 回歸組通過。

- D854：P3-748 補強 report bundle data trust mapping-safe handoff：`reporting.types.ReportBundle.data_trust` 在 persistence 或後續處理讀取 snapshot trust 前使用 mapping-safe conversion 接受有效 data snapshot Mapping payload，讓 immutable / read-only snapshot wrappers 不再隱藏有效 report confidence metadata；RED→GREEN report bundle data trust mapping 單測、report/data-trust focused 驗證與 report-quality 回歸組通過。

- D855：P3-749 補強 report persistence mapping-safe snapshot handoff：`report_persistence.persist_report_bundle()` 在保存 `.data.json`、傳遞 index metadata 與回傳 API payload 前使用 snapshot-safe conversion 接受有效 data snapshot Mapping payload，讓 immutable / read-only snapshot wrappers 不再中斷 JSON 保存或讓 report confidence metadata 在 storage、index handoff、return payload 之間漂移；RED→GREEN persistence mapping snapshot 單測、storage/report focused 驗證與 report-quality 回歸組通過。

- D856：P3-750 補強 report refresh diff mapping-safe snapshot handoff：`report_refresh_service.refresh_data_diff()` 與 source status map 在比較 data trust 與 source audit status 前使用 mapping-safe conversion 接受有效 snapshot / source-audit Mapping payload，讓 immutable / read-only snapshots 仍能在 preview response 顯示正確 stale→fresh 與 provider recovery evidence；RED→GREEN refresh diff mapping snapshot 單測、refresh/report focused 驗證與 report-quality 回歸組通過。

- D857：P3-751 補強 report refresh rerun mapping-safe decision check：`report_refresh_service.refresh_requires_analysis_rerun()` 在比較 decision-relevant data、refresh diff 子 map 與 data trust reason/status 前使用 mapping-safe conversion 接受有效 snapshot / data Mapping payload，讓 immutable / read-only snapshots 的價格、估值、trust reason 或 failure metadata 變化不再被漏判為 current；RED→GREEN refresh rerun mapping data 單測、refresh/report focused 驗證與 report-quality 回歸組通過。

- D858：P3-752 補強 report refresh stale-source mapping-safe source audit detection：`report_refresh_service._stale_sources()` 與 `_source_audit_timestamp()` 在判斷 high-frequency refresh source 前使用 mapping-safe / sequence-safe conversion 接受有效 snapshot 與 source audit Mapping rows，讓 immutable / read-only snapshots 中 fresh 的 `market_data` / `recent_catalysts` evidence 不再被誤判成 stale refresh source；RED→GREEN stale-source mapping audit 單測、refresh/report focused 驗證與 report-quality 回歸組通過。

- D859：P3-753 補強 report refresh source audit timestamp truthiness guard：`report_refresh_service._source_audit_timestamp()` 與 `_parse_datetime()` 不再用 truthiness 判斷 source audit timestamp，改用 explicit `None` 與 safe text conversion，讓可解析但 falsey 的 timestamp wrapper 仍能保留 fresh source evidence，避免 `market_data` / `recent_catalysts` 被誤判為 stale；RED→GREEN falsey timestamp 單測、refresh/report focused 驗證與 report-quality 回歸組通過。

- D860：P3-754 補強 report refresh refreshed-data mapping-safe provider/cache handoff：`report_refresh_service.refresh_report_data_snapshot()` 在 provider/cache 回傳資料進入 snapshot rebuild 前使用 mapping-safe conversion 與 snapshot sanitizer 接受有效 Mapping payload，讓 read-only refreshed data wrappers 的新價格、source audit rows 與 trust metadata 不再被誤判成 fetch failure 或在 deepcopy 階段中斷；RED→GREEN refreshed-data Mapping payload 單測、refresh/report focused 驗證與 report-quality 回歸組通過。

- D861：P3-755 補強 full-report rerun refreshed-data mapping-safe provider/cache handoff：`report_rerun_service._run_full_pipeline_rerun()` 在完整重跑前的 provider/cache refresh payload 進入 `AnalysisRequest` 前使用 mapping-safe conversion 與 snapshot sanitizer，讓 read-only refreshed data wrappers 的新價格、source audit rows 與 trust metadata 不再被誤判成完整重跑前資料刷新失敗，並能完整傳入 pipeline runner；RED→GREEN full rerun refreshed-data Mapping payload 單測、rerun/report focused 驗證與 report-quality 回歸組通過。

- D862：P3-756 補強 full-report rerun existing snapshot data mapping-safe handoff：`report_rerun_service._run_full_pipeline_rerun()` 在沒有 refresh_service、直接使用既有 snapshot data 進入 `AnalysisRequest` 前使用 mapping-safe conversion 與 snapshot sanitizer，讓 read-only source audit / trust wrappers 轉為 pipeline-safe mutable data，避免完整重跑 pipeline 或 renderer 在補 audit metadata 時遇到 tuple / MappingProxy 中斷；RED→GREEN existing snapshot Mapping payload 單測、rerun/report focused 驗證與 report-quality 回歸組通過。

- D863：P3-757 補強 final-recommendation rerun context data mapping-safe handoff：`report_rerun_service._build_final_rerun_context()` 在只重跑最終建議 agent 前使用 mapping-safe conversion 與 snapshot sanitizer 正規化既有 snapshot data，讓 read-only source audit / trust wrappers 轉為 final agent 可安全補 metadata 的 mutable payload；RED→GREEN final rerun context Mapping payload 單測、rerun/report focused 驗證與 report-quality 回歸組通過。

- D864：P3-758 補強 final-recommendation rerun context mapping-safe previous-analysis handoff：`report_rerun_context.rerun_context_from_snapshot()` 與 `coerce_agent_map()` 在只重跑最終建議 agent 前接受 mapping-safe snapshot / rerun_context / agent maps，讓 read-only previous-agent analyses 與 structured outputs 不再被誤判為缺失而強迫 Markdown fallback 或阻擋 partial rerun；RED→GREEN final rerun context Mapping rerun_context 單測、rerun/report focused 驗證與 report-quality 回歸組通過。

- D865：P3-759 補強 rerun renderer snapshot mapping-safe integrity handoff：`report_rerun_rendering.render_and_save_rerun_report()` 在加上 rerun metadata 與計算 snapshot integrity 前使用 mapping-safe conversion 與 snapshot sanitizer 正規化 renderer 回傳的 data snapshot，讓 read-only source audit / trust wrappers 不再因 `dict(...)` 直接迭代中斷，且保存後的 nested payload 形狀與 `snapshot_hash` 一致；RED→GREEN rerun renderer Mapping snapshot 單測、rerun/report focused 驗證與 report-quality 回歸組通過。

- D866：P3-760 補強 rerun render context mapping-safe metadata handoff：`report_rerun_rendering.render_and_save_rerun_report()` 在新增 partial-rerun metadata 前先用 mapping-safe conversion 建立 top-level mutable render context，讓 read-only pipeline context 仍能帶著 ticker、data 與 rerun provenance 進入 renderer 並保存到 snapshot；RED→GREEN rerun render context Mapping payload 單測、rerun/report focused 驗證與 report-quality 回歸組通過。

- D867：P3-761 補強 rerun progress event mapping-safe job-store handoff：`report_rerun_jobs._append_progress_event()` 在保存背景重跑進度前接受 mapping-safe event payload，讓 read-only progress wrappers 的 phase、message、current/total、rerun scope 與 source filename 不再被抹成預設事件或在 `int(raw_event)` 中斷；RED→GREEN rerun progress event Mapping payload 單測、rerun job/stream focused 驗證與 report-quality 回歸組通過。

- D868：P3-762 補強 rerun completion result mapping-safe job-store handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在寫入 `report_done` / `done` 事件前使用 mapping-safe conversion 與 snapshot sanitizer 正規化重跑結果，讓 read-only data trust、partial rerun 與 metadata payload 不再在 job-store JSON serialization 中斷，且完成事件仍保留 pipeline_id 與 rerun provenance；RED→GREEN rerun completion result Mapping payload 單測、rerun job/stream focused 驗證與 report-quality 回歸組通過。

- D869：P3-763 補強 rerun completion identity field safe-text handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在更新 job row 與寫入 `report_done` / `done` 事件前，對 completion result 的 `filename`、`md_filename`、`data_filename`、`scope_label` 與 `pipeline_id` 使用 safe text normalization，讓 malformed boolean、binary 或 memory-view identity values 不再外溢成 rerun stream 的檔名或 pipeline identity；RED→GREEN malformed completion identity 單測與 rerun job/stream focused 驗證通過。

- D870：P3-764 補強 rerun progress event nested payload snapshot-safe job-store handoff：`report_rerun_jobs._append_progress_event()` 在保存背景重跑進度前使用 snapshot-safe normalization 正規化 progress event payload，讓 nested read-only details、source audit 或 metadata payload 不再在 job-store JSON serialization 中斷，且進度事件仍保留 rerun scope 與 source filename；RED→GREEN nested progress payload 單測與 rerun job/stream focused 驗證通過。

- D871：P3-765 補強 rerun progress scalar fallback integer-safe handoff：`report_rerun_jobs._append_progress_event()` 在 progress callback 只回傳 scalar 時使用 `safe_int()` 產生 fallback `current`，讓 malformed truthiness / integer conversion wrappers 不再中斷 job-store 進度事件，也避免 boolean progress counters 外溢成 1；RED→GREEN malformed scalar progress 單測與 rerun job/stream focused 驗證通過。

- D872：P3-766 補強 rerun HTTPException detail safe-text error-event handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在處理 `HTTPException` 時使用 safe text fallback 產生 terminal error message，讓 malformed exception detail truthiness / string conversion wrappers 不再遮蔽原始重跑錯誤或阻斷 job-store `error` 事件；RED→GREEN malformed HTTP detail 單測與 rerun job/stream focused 驗證通過。

- D873：P3-767 補強 rerun generic exception safe-text error-event handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在處理非 HTTP unexpected exception 時使用 safe text fallback 寫入 terminal `error` 事件，讓 malformed exception `__str__` 不再遮蔽原始例外型別或阻斷 job-store error event，同時仍重新拋出原始 exception 供 worker/queue runtime 處理；RED→GREEN malformed generic exception 單測與 rerun job/stream focused 驗證通過。

- D874：P3-768 補強 rerun HTTPException status_code integer-safe error-event handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在處理 `HTTPException` 時使用 integer-safe status code fallback 寫入 terminal `error` 事件，讓 malformed status code payload 不再中斷 job-store JSON persistence，且非合法 HTTP 範圍統一落回 500；RED→GREEN malformed HTTP status 單測與 rerun job/stream focused 驗證通過。

- D875：P3-769 補強 rerun API key failure source filename error-event handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在 API key 缺失的 terminal `error` 事件中保留 `source_filename`，讓設定失敗也能在 SSE replay / job-store event 中追溯原始報告檔名，與取消、HTTP error、unexpected error 路徑一致；RED→GREEN API key failure source filename 單測與 rerun job/stream focused 驗證通過。

- D876：P3-770 補強 rerun source_filename safe-text job-store handoff：`report_rerun_jobs.run_report_rerun_job_async()` 與 `_append_progress_event()` 在寫入 job-store events 前使用 safe text normalization 產生 `source_filename`，讓 malformed / binary source filename payload 不再中斷 rerun streams 或 terminal error events，同時保留原始 `filename` 傳入 rerun service 的查找語義；RED→GREEN malformed source filename 單測與 rerun job/stream focused 驗證通過。

- D877：P3-771 補強 rerun cancellation message safe-text terminal-event handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在處理 `ReportRerunJobCancelled` 時使用 safe text fallback 產生 cancelled terminal event message，讓 malformed cancellation exception string conversion 不再中斷 job-store `cancelled` 狀態與 SSE event persistence；RED→GREEN malformed cancellation message 單測與 rerun job/stream focused 驗證通過。

- D878：P3-772 補強 rerun invalid scope job-store terminal-event handoff：`report_rerun_jobs.run_report_rerun_job_async()` 將 scope normalization 納入既有 try/HTTPException handler，並使用 safe fallback scope 寫入 terminal `error` event，讓 unsupported / malformed rerun scope 不再直接逃出 worker 而留下 queued/running job；RED→GREEN invalid scope terminal event 單測與 rerun job/stream focused 驗證通過。

- D879：P3-773 補強 rerun progress event scope safe-text job-store handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 safe text fallback 正規化 `rerun_scope`，讓 malformed / binary progress scope payload 不再中斷 rerun stream persistence，正常 `full_report` / `mode_b` / `final_recommendation` scope 行為維持不變；RED→GREEN malformed progress scope 單測與 rerun job/stream focused 驗證通過。

- D880：P3-774 補強 rerun progress event control field safe-text handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前正規化 progress event 的 `type`、`phase` 與 `level` 控制欄位，讓 malformed boolean/binary/container metadata 不再外溢成非字串 SSE event type 或 job-store index metadata；RED→GREEN malformed progress control fields 單測與 rerun job/stream focused 驗證通過。

- D881：P3-775 補強 rerun progress event count integer-safe handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 `safe_int()` 正規化 progress event 的 `current` 與 `total` 欄位，讓 malformed boolean/binary count payload 不再外溢成非整數進度或污染 rerun stream/log；RED→GREEN malformed progress count 單測與 rerun job/stream focused 驗證通過。

- D882：P3-776 補強 rerun progress event message safe-text handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 safe text fallback 正規化 progress event 的 `message` 欄位，讓 malformed boolean/binary/container message payload 不再外溢成非文字操作者訊息或污染 rerun stream/log；RED→GREEN malformed progress message 單測與 rerun job/stream focused 驗證通過。

- D883：P3-777 補強 rerun progress event name safe-text handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 safe text fallback 正規化 progress event 的 `name` 欄位，讓 malformed boolean/binary/container progress label 不再外溢成非文字進度標籤或污染 rerun stream/log；RED→GREEN malformed progress name 單測與 rerun job/stream focused 驗證通過。

- D884：P3-778 補強 rerun progress event detail safe-text handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 safe text fallback 正規化 progress event 的 `detail` 欄位，讓 malformed boolean/binary/container detail payload 不再外溢成非文字 runtime log suffix 或污染 rerun stream/log，同時保留 `details` 巢狀 payload 的 snapshot-safe 行為；RED→GREEN malformed progress detail 單測與 rerun job/stream focused 驗證通過。

- D885：P3-779 補強 rerun progress event agent_num integer-safe handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 `safe_int()` 正規化 progress event 的 `agent_num` 欄位，讓 malformed boolean/binary agent identity payload 不再外溢成非整數 agent number 或污染 rerun stream/job observability；RED→GREEN malformed progress agent_num 單測與 rerun job/stream focused 驗證通過。

- D886：P3-780 補強 rerun progress event pipeline identity safe-text handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 safe text fallback 正規化 progress event 的 `pipeline_id` 與 `pipeline_label` 欄位，讓 malformed boolean/binary/container pipeline identity payload 不再外溢成非文字 pipeline identity 或污染 rerun stream/job observability；RED→GREEN malformed progress pipeline identity 單測與 rerun job/stream focused 驗證通過。

- D887：P3-781 補強 rerun progress event metadata mapping-safe handoff：`report_rerun_jobs._append_progress_event()` 在寫入 job-store 前使用 mapping-safe normalization 正規化 progress event 的 `metadata` 欄位，讓 malformed scalar/sequence metadata payload 不再外溢成非 mapping observability payload 或污染 rerun stream/job observability；RED→GREEN malformed progress metadata 單測與 rerun job/stream focused 驗證通過。

- D888：P3-782 補強 rerun completion structured result mapping-safe handoff：`report_rerun_jobs.run_report_rerun_job_async()` 在寫入 `report_done` / `done` 事件前使用 mapping-safe normalization 正規化 completion result 的 `data_trust` 與 `partial_rerun` 欄位，讓 malformed scalar/sequence structured result payload 不再外溢成非 mapping result context 或污染 rerun stream/job observability；RED→GREEN malformed completion structured result 單測與 rerun job/stream focused 驗證通過。

- D889：P3-783 補強 rerun queue enqueue failure source filename handoff：`api_routes.reports.rerun_report_analysis()` 在報告重跑任務送入 queue 失敗時，於 terminal `error` event 保留 `source_filename`，讓 queue submission failure 也能在 SSE replay / job-store event 中追溯原始報告檔名；RED→GREEN enqueue failure source filename 單測與 rerun endpoint/job-store focused 驗證通過。

- D890：P3-784 補強 rerun stream terminal fallback source filename handoff：`api_routes.reports.stream_report_rerun()` 在 job 已進入 `error` / `cancelled` 但缺少 terminal event 時，合成並持久化的 fallback `error` event 會保留 `rerun_scope` 與 `source_filename`，讓 SSE replay / job-store terminal fallback 仍可追溯原始報告檔名與重跑範圍；RED→GREEN error/cancelled fallback 單測與 rerun stream focused 驗證通過。

- D891：P3-785 補強 rerun stream terminal fallback safe-text handoff：`api_routes.reports.stream_report_rerun()` 在 job 已進入 `done` / `error` / `cancelled` 但缺少 terminal event 時，合成並持久化的 fallback event 會先用 safe text normalization 正規化 generated filename 與 terminal message，讓 malformed job row payload 不再中斷 SSE replay 或 job-store terminal fallback；RED→GREEN done/error/cancelled fallback 單測與 rerun stream focused 驗證通過。

- D892：P3-786 補強 rerun stream terminal fallback empty-scope handoff：`api_routes.reports.stream_report_rerun()` 從 job `pipeline_id` 推導 `rerun_scope` 時會先做 safe text normalization，並在 `rerun:` 空 scope job row 落回 `final_recommendation`，讓合成 terminal fallback event 不再失去重跑範圍脈絡；RED→GREEN empty-scope fallback 單測與 rerun stream focused 驗證通過。

- D893：P3-787 補強 rerun stream task validation safe-text handoff：`api_routes.reports.stream_report_rerun()` 在 SSE setup 前驗證 job `pipeline_id` 是否為 rerun task 時改用 safe text normalization，讓 malformed pipeline id job row 不再讓 API 回 500，而是穩定回 404 `找不到報告重跑任務`；RED→GREEN malformed pipeline id validation 單測與 rerun stream focused 驗證通過。

- D894：P3-788 補強 rerun stream task ticker validation safe-text handoff：`api_routes.reports.stream_report_rerun()` 在 SSE setup 前驗證 job `ticker` 是否匹配 URL report filename 時改用 safe text normalization，讓 malformed ticker job row 不再讓 API 回 500，而是穩定回 404 `找不到報告重跑任務`；RED→GREEN malformed ticker validation 單測與 rerun stream focused 驗證通過。

- D895：P3-789 補強 rerun cancel task validation safe-text handoff：`api_routes.reports.cancel_report_rerun()` 在送出取消要求前驗證 job `pipeline_id` 是否為 rerun task 時改用 safe text normalization，讓 malformed pipeline id job row 不再讓 API 回 500，而是穩定回 `{ok:false, message:"找不到可取消的報告重跑任務"}`；RED→GREEN malformed cancel pipeline id validation 單測與 rerun focused 驗證通過。

- D896：P3-790 補強 rerun cancel task ticker validation safe-text handoff：`api_routes.reports.cancel_report_rerun()` 在送出取消要求前驗證 job `ticker` 是否匹配 URL report filename 時完成 RED→GREEN safe text normalization，讓 malformed ticker job row 不再讓 API 回 500，而是穩定回 `{ok:false, message:"找不到可取消的報告重跑任務"}`；RED→GREEN malformed cancel ticker validation 單測與 rerun focused 驗證通過。

- D897：P3-791 補強 rerun attached job status safe-text queue-recovery handoff：`api_routes.reports.rerun_report_analysis()` 在附加既有 rerun job 並判斷是否需要 queue recovery 前使用 safe text normalization 檢查 job `status`，讓 malformed existing job status row 不再讓 rerun enqueue API 回 500，也不會從不可信狀態值觸發補排 queue；RED→GREEN malformed attached status 單測、rerun endpoint focused 驗證與文件契約更新通過。

- D898：P3-792 補強 rerun queue enqueue failure message safe-text handoff：`api_routes.reports.rerun_report_analysis()` 在 queue enqueue 失敗時使用 safe text fallback 產生 terminal error message，讓 malformed queue exception string conversion 不再讓 rerun enqueue API 回 500，且仍會把 job 標記為 error 並保存含 `source_filename` / `rerun_scope` 的 error event；RED→GREEN malformed enqueue exception 單測、rerun endpoint focused 驗證與文件契約更新通過。

- D899：P3-793 補強 rerun attached job created flag explicit-bool enqueue handoff：`api_routes.reports.rerun_report_analysis()` 在附加既有 rerun job 後只把 `create_or_attach_job()` 回傳的明確布林 `created is True` 視為新任務，讓 malformed created flag truthiness 不再讓 rerun enqueue API 回 500，也不會從不可信旗標值觸發 queue submission；RED→GREEN malformed created flag 單測、rerun endpoint focused 驗證與文件契約更新通過。

- D900：P3-794 補強 rerun stream replay payload mapping-safe SSE handoff：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前使用 mapping-safe fallback 正規化 event `payload`，讓合法 JSON 但非 mapping 的 malformed event payload 不再中斷 SSE replay，而是輸出 warning status event 並繼續 terminal fallback；RED→GREEN malformed replay payload 單測、rerun stream focused 驗證與文件契約更新通過。

- D901：P3-795 補強 rerun stream post-setup missing job terminal fallback：`api_routes.reports.stream_report_rerun()` 在 SSE setup 已通過、後續輪詢 job-store 時若 job row 消失或查不到，會輸出含 `rerun_scope` 與 `source_filename` 的 terminal error event，讓 operational cleanup 或缺失 job row 不再讓 stream 只停在 intro event；RED→GREEN missing job after setup 單測、rerun stream focused 驗證與文件契約更新通過。
- D902：P3-796 補強 rerun stream post-setup missing job terminal fallback persistence：`api_routes.reports.stream_report_rerun()` 在 SSE setup 已通過、後續輪詢 job-store 時若 job row 消失或查不到，會先持久化含 `rerun_scope` 與 `source_filename` 的 terminal error event，讓使用者重連或 SSE resume 時仍能看到「找不到報告重跑任務」結論；RED→GREEN missing job persistence 單測、rerun stream focused 驗證與文件契約更新通過。
- D903：P3-797 補強 analysis SSE replay payload mapping-safe handoff：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前使用 mapping-safe fallback 正規化 event `payload`，讓合法 JSON 但非 mapping 的 malformed analysis event 不再因 `.get()` 中斷 SSE，而是輸出 warning status event 並繼續送出後續 terminal event；RED→GREEN malformed analysis replay payload 單測與文件契約更新通過。
- D904：P3-798 補強 analysis SSE terminal fallback error message safe-text handoff：`api_routes.analysis_sse.terminal_payload_for_job()` 在 job 已進入 `error` 但缺少 terminal event 時，合成 `error` payload 前會使用 safe text fallback 正規化 job `error` 欄位，讓 malformed binary / memory-view error payload 不再中斷 SSE JSON serialization 或阻擋 terminal fallback replay；RED→GREEN malformed analysis error fallback 單測與文件契約更新通過。
- D905：P3-799 補強 analysis SSE terminal fallback cancellation message safe-text handoff：`api_routes.analysis_sse.terminal_payload_for_job()` 在 job 已進入 `cancelled` 但缺少 terminal event 時，合成 cancelled `error` payload 前會使用 safe text fallback 正規化 job `error` 欄位，讓 malformed cancellation reason 不再中斷 SSE JSON serialization 或阻擋取消結論 replay；RED→GREEN malformed analysis cancelled fallback 單測與文件契約更新通過。
- D906：P3-800 補強 analysis SSE terminal fallback done identity safe-text handoff：`api_routes.analysis_sse.terminal_payload_for_job()` 在 job 已進入 `done` 但缺少 terminal event 時，合成 `done` payload 前會使用 safe text fallback 正規化 `filename`、`pipeline_id` 與 `last_pipeline_id`，讓 malformed binary / memory-view identity payload 不再中斷 SSE JSON serialization 或阻擋完成結論 replay；RED→GREEN malformed analysis done fallback 單測與文件契約更新通過。
- D907：P3-801 補強 analysis SSE terminal polling status safe-text handoff：`api_routes.analysis_sse.analysis_event_generator()` 在輪詢 job row 並判斷是否需要 terminal fallback 前，會先用 safe text fallback 正規化 `status`，讓 malformed comparison/string-conversion status payload 不再中斷 SSE polling，也不會從不可信狀態合成 terminal event；RED→GREEN malformed analysis status polling 單測與文件契約更新通過。
- D908：P3-802 補強 analysis SSE replay event-row mapping-safe handoff：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 mapping-safe fallback 正規化 event row，讓 malformed non-mapping row 不再於讀取 `id` 時中斷 SSE，而是輸出 warning status event 並繼續送出後續 terminal event；RED→GREEN malformed analysis replay event-row 單測與文件契約更新通過。
- D909：P3-803 補強 analysis SSE terminal fallback persistence mapping-safe handoff：`api_routes.analysis_sse.persist_terminal_event_if_missing()` 在判斷既有 terminal event 與驗證 append 結果前會先用 mapping-safe fallback 正規化 event row 與 payload，讓 read-only job-store event row 不再被誤判為缺少 terminal event 並重複 append fallback；RED→GREEN mapping event-row presence 單測與文件契約更新通過。
- D910：P3-804 補強 analysis SSE event collection sequence-safe handoff：`api_routes.analysis_sse.analysis_event_generator()` 與 `persist_terminal_event_if_missing()` 在 replay 與 terminal fallback persistence 前會先用 sequence-safe fallback 正規化 event collection，讓 malformed job-store collection payload 不再於迭代 event list 時中斷 SSE，而是交由 job terminal fallback 輸出完成事件；RED→GREEN malformed event collection 單測與文件契約更新通過。
- D911：P3-805 補強 analysis SSE post-setup missing job terminal fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 SSE setup 已通過、後續輪詢 job-store 時若 job row 消失或無法正規化，會輸出 `missing_job` terminal error fallback，讓 operational cleanup 或缺失 job row 不再讓 stream 只停在 intro event 或因 `job.get()` 崩潰；RED→GREEN missing job row 單測與文件契約更新通過。
- D912：P3-806 補強 analysis SSE resume id malformed query fallback：`api_routes.analysis_sse.resolve_resume_after_id()` 在 `since_id` 無法轉成整數時會退回 `Last-Event-ID` 或 `last_event_id`，避免 malformed resume query 直接中斷 SSE setup，並保留有效 `since_id` 的優先權；RED→GREEN malformed since_id 單測與文件契約更新通過。
- D913：P3-807 補強 analysis SSE resume id negative cursor fallback：`api_routes.analysis_sse.resolve_resume_after_id()` 會把負數 `since_id`、`Last-Event-ID` 與 `last_event_id` 視為 malformed resume cursor，避免負數 event cursor 傳入 job-store event query，並在可用時退回下一個 resume 來源；RED→GREEN negative since_id 單測與文件契約更新通過。
- D914：P3-808 補強 analysis SSE resume id boolean cursor fallback：`api_routes.analysis_sse.resolve_resume_after_id()` 會把 boolean `since_id`、`Last-Event-ID` 與 `last_event_id` 視為 malformed resume cursor，避免 Python 將 `True` / `False` 強制轉成 event id 1 / 0 而跳錯 replay cursor；RED→GREEN boolean since_id 單測與文件契約更新通過。
- D915：P3-809 補強 rerun stream replay event-row mapping-safe fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 mapping-safe fallback 正規化 event row 與 integer-safe event id，讓 malformed non-mapping row 或無效 id 不再中斷報告重跑 SSE，而是輸出 warning status event 並繼續後續 terminal event；RED→GREEN malformed rerun event-row 單測與文件契約更新通過。
- D916：P3-810 補強 rerun stream resume id negative header fallback：`api_routes.reports.stream_report_rerun()` 改用共用 `resolve_resume_after_id()` 解析 `Last-Event-ID`，讓負數 header cursor 視為 malformed 並回落到 0，避免負數 replay cursor 傳入 job-store event query；RED→GREEN negative Last-Event-ID 單測與文件契約更新通過。
- D917：P3-811 補強 rerun stream terminal polling status safe-text fallback：`api_routes.reports.stream_report_rerun()` 在輪詢 job row 並判斷是否需要 terminal fallback 前，會先以 safe text fallback 正規化 `status`，讓 malformed comparison/string-conversion status payload 不再中斷報告重跑 SSE polling，也不會從不可信狀態合成 terminal event；RED→GREEN malformed rerun status 單測與文件契約更新通過。
- D918：P3-812 補強 rerun stream event collection sequence-safe fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 sequence-safe fallback 正規化 event collection，讓 malformed collection payload 不再於迭代 event list 時中斷報告重跑 SSE，而是交由 job terminal fallback 輸出完成或錯誤事件；RED→GREEN malformed rerun event collection 單測與文件契約更新通過。
- D919：P3-813 補強 rerun stream setup job-row mapping-safe validation：`api_routes.reports.stream_report_rerun()` 在 SSE setup 驗證 rerun task 前會先用 mapping-safe fallback 正規化 job row，讓 malformed non-mapping job-store row 不再讓 stream setup 回 500，而是穩定回 404 `找不到報告重跑任務`；RED→GREEN malformed setup job-row 單測與文件契約更新通過。
- D920：P3-814 補強 rerun stream replay payload type safe-text fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload `type` 控制欄位，讓 malformed boolean/binary/container type payload 不再中斷報告重跑 SSE JSON output 或 terminal 判斷，而是輸出 warning status event 並繼續後續 terminal event；RED→GREEN malformed rerun payload type 單測與文件契約更新通過。
- D921：P3-815 補強 rerun stream replay message safe-text fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload `message` 欄位，讓 malformed boolean/binary/container message payload 不再中斷報告重跑 SSE JSON output，且後續 terminal event 仍可送達；RED→GREEN malformed rerun replay message 單測與文件契約更新通過。
- D922：P3-816 補強 rerun stream replay filename safe-text fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload 的 `filename`、`md_filename`、`data_filename` 與 `source_filename` 欄位，讓 malformed binary/container filename payload 不再中斷報告重跑 SSE JSON output，完成事件仍可送達；RED→GREEN malformed rerun replay filename 單測與文件契約更新通過。
- D923：P3-817 補強 rerun stream replay control-field safe-text fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload 的 `phase` 與 `level` 控制欄位，讓 malformed binary/container control payload 不再中斷報告重跑 SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed rerun replay control-field 單測與文件契約更新通過。
- D924：P3-818 補強 rerun stream replay context-field safe-text fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload 的 `rerun_scope`、`scope_label`、`pipeline_id` 與 `pipeline_label` 欄位，讓 malformed binary/container context payload 不再中斷報告重跑 SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed rerun replay context-field 單測與文件契約更新通過。
- D925：P3-819 補強 rerun stream replay count-field integer-safe fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 integer-safe fallback 正規化 payload 的 `current`、`total` 與 `agent_num` 欄位，讓 malformed binary count payload 不再中斷報告重跑 SSE JSON output，也不會被轉成看似可信的進度數字；RED→GREEN malformed rerun replay count-field 單測與文件契約更新通過。
- D926：P3-820 補強 rerun stream replay structured-field snapshot-safe fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 snapshot-safe normalization 正規化 payload 的 `data_trust`、`partial_rerun`、`metadata` 與 `details` 欄位，讓 malformed nested binary/container structured payload 不再中斷報告重跑 SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed rerun replay structured-field 單測與文件契約更新通過。
- D927：P3-821 補強 rerun stream replay status-code integer-safe fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 integer-safe fallback 正規化 payload 的 `status_code` 欄位，讓 malformed binary status code payload 不再中斷報告重跑 SSE JSON output，也不會被轉成看似可信的 HTTP 狀態碼；RED→GREEN malformed rerun replay status-code 單測與文件契約更新通過。
- D928：P3-822 補強 rerun stream replay progress-text safe-text fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload 的 `name` 與 `detail` 欄位，讓 malformed binary/container progress text payload 不再中斷報告重跑 SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed rerun replay progress-text 單測與文件契約更新通過。
- D929：P3-823 補強 rerun stream replay event-id integer-safe fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前會先用 event-id 專用 integer-safe fallback 正規化 event row `id`，讓 malformed boolean/binary event id 不再被 Python 轉成可信 SSE cursor，也不會讓該 malformed row 的 progress payload 外溢；RED→GREEN malformed rerun replay event-id 單測與文件契約更新通過。
- D930：P3-824 補強 rerun stream replay payload-type container fallback：`api_routes.reports.stream_report_rerun()` 在 replay job-store events 前要求 payload `type` 必須是原生字串，讓 malformed mapping/list container type 不再被字串化成偽 event type，也不會讓該 malformed row 的 progress payload 外溢；RED→GREEN malformed rerun replay container payload-type 單測通過。
- D931：P3-825 補強 analysis SSE replay event-id integer-safe fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 event-id 專用 integer-safe fallback 正規化 event row `id`，讓 malformed boolean/binary analysis event id 不再被 Python 轉成可信 SSE cursor，也不會讓該 malformed row 的 status payload 外溢；RED→GREEN malformed analysis replay event-id 單測與文件契約更新通過。
- D932：P3-826 補強 analysis SSE replay message safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload `message` 欄位，讓 malformed boolean/binary/container message payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay message 單測與文件契約更新通過。
- D933：P3-827 補強 analysis SSE replay payload-type fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前要求 payload `type` 必須是原生字串，讓 malformed boolean/binary/container event type 不再中斷 analysis SSE JSON output，也不會讓該 malformed row 的 status payload 外溢；RED→GREEN malformed analysis replay payload-type 單測與文件契約更新通過。
- D934：P3-828 補強 analysis SSE replay done-identity safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 done payload 的 `filename`、`pipeline_id` 與 `last_pipeline_id` 欄位，讓 malformed binary/container identity payload 不再中斷 analysis SSE JSON output，完成事件仍可送達；RED→GREEN malformed analysis replay done-identity 單測與文件契約更新通過。
- D935：P3-829 補強 analysis SSE replay control-field safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload 的 `phase` 與 `level` 控制欄位，讓 malformed binary/container control payload 不再中斷 analysis SSE JSON output，錯誤或狀態事件仍可送達；RED→GREEN malformed analysis replay control-field 單測與文件契約更新通過。
- D936：P3-830 補強 analysis SSE replay count-field integer-safe fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 integer-safe fallback 正規化 payload 的 `current`、`total`、`agent_num`、`pipeline_current` 與 `pipeline_total` 欄位，讓 malformed binary progress count payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay count-field 單測與文件契約更新通過。
- D937：P3-831 補強 analysis SSE replay progress-text safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 payload 的 `name`、`detail` 與 `pipeline_label` 欄位，讓 malformed binary/container progress display payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay progress-text 單測與文件契約更新通過。
- D938：P3-832 補強 analysis SSE replay metadata snapshot-safe fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 snapshot-safe fallback 正規化 payload 的 `metadata` 欄位，讓 malformed nested binary/container metadata payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay metadata 單測與文件契約更新通過。
- D939：P3-833 補強 analysis SSE replay telemetry-text safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 telemetry payload 的 `node_name`、`model`、`status` 與 `error` 欄位，讓 malformed binary/container telemetry text payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay telemetry-text 單測與文件契約更新通過。
- D940：P3-834 補強 analysis SSE replay telemetry-metric safe fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 finite-float、integer 與 bool fallback 正規化 telemetry payload 的 `latency_ms`、`retry_count` 與 `quality_gate_pass` 欄位，讓 malformed binary telemetry metric payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay telemetry-metric 單測與文件契約更新通過。
- D941：P3-835 補強 analysis SSE replay pipeline-count integer fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 integer-safe fallback 正規化 pipeline progress payload 的 `pipeline_index`、`agent_total` 與 `agent_offset` 欄位，讓 malformed binary pipeline count payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay pipeline-count 單測與文件契約更新通過。
- D942：P3-836 補強 analysis SSE replay structured-report snapshot-safe fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 snapshot-safe fallback 正規化 report payload 的 `data_trust` 與 `audit` 欄位，讓 malformed nested report_done/done structured payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay structured-report 單測與文件契約更新通過。
- D943：P3-837 補強 analysis SSE replay report-artifact filename safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 report_done payload 的 `md_filename` 與 `data_filename` 欄位，讓 malformed binary artifact filename payload 不再中斷 analysis SSE JSON output，後續 terminal event 仍可送達；RED→GREEN malformed analysis replay report-artifact filename 單測與文件契約更新通過。
- D944：P3-838 補強 analysis SSE replay done-aggregate snapshot-safe fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 snapshot-safe fallback 正規化 done payload 的 `filenames`、`reports` 與 `pipeline_sequence` 欄位，讓 malformed nested completion aggregate payload 不再中斷 analysis SSE JSON output；RED→GREEN malformed analysis replay done-aggregate 單測與文件契約更新通過。
- D945：P3-839 補強 analysis SSE replay workflow-retry thread-id safe-text fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 replay job-store events 前會先用 safe text fallback 正規化 workflow retry payload 的 `thread_id` 欄位，讓 malformed retry checkpoint thread identifier 不再中斷 analysis SSE JSON output；RED→GREEN malformed analysis replay workflow-retry thread-id 單測與文件契約更新通過。
- D946：P3-840 補強 rerun stream post-setup job-row mapping-safe fallback：`api_routes.reports.stream_report_rerun()` 在 SSE setup 通過後的 terminal polling 會先用 mapping-safe fallback 正規化 job row，再讀取 `status`、`filename` 與 `error` 欄位，讓 malformed truthy job-store row 不再中斷報告重跑 SSE，而是輸出缺失任務 terminal error fallback；RED→GREEN malformed rerun post-setup job-row 單測與文件契約更新通過。
- D947：P3-841 補強 rerun cancel endpoint job-row mapping-safe fallback：`api_routes.reports.cancel_report_rerun()` 在驗證取消任務前會先用 mapping-safe fallback 正規化 job row，再讀取 `pipeline_id` 與 `ticker` 欄位，讓 malformed non-mapping job-store row 不再讓取消 API 回 500，而是穩定回傳找不到可取消的重跑任務；RED→GREEN malformed rerun cancel job-row 單測與文件契約更新通過。
- D948：P3-842 補強 analysis job status endpoint job-row mapping-safe fallback：`api_routes.analysis.get_analysis_job()` 在序列化 status response 前會先用 mapping-safe fallback 正規化 job row，讓 missing 或 malformed non-mapping job-store row 不再讓 `/api/analysis-jobs/{job_id}` 回 200 空 payload 或 500，而是穩定回 404 `Analysis job not found`；RED→GREEN missing / malformed analysis job status row 單測與文件契約更新通過。
- D949：P3-843 補強 analysis SSE setup job-row mapping-safe fallback：`api_routes.analysis.stream_analysis_job_events()` 在建立 SSE stream 前會先用 mapping-safe fallback 正規化 job row，再讀取 `ticker` 與 `pipeline_id` 欄位，讓 missing 或 malformed non-mapping job-store row 不再讓 `/api/analysis-jobs/{job_id}/events` 開啟無限 stream 或回 500，而是穩定回 404 `Analysis job not found`；RED→GREEN missing / malformed analysis SSE setup job-row 單測與文件契約更新通過。
- D950：P3-844 補強 analysis SSE post-setup empty job-row terminal fallback：`api_routes.analysis_sse.analysis_event_generator()` 在 SSE setup 已通過、後續輪詢 job-store 時會把 `{}` 空 mapping job row 視為 missing job，輸出 `missing_job` terminal error fallback，避免 operational cleanup 或空 row 讓 stream 只剩 heartbeat ping；RED→GREEN empty analysis job row 單測與文件契約更新通過。
- D951：P3-845 補強 legacy analysis compatibility job-row mapping-safe fallback：`api_routes.analysis.analyze_stock()` 與 legacy `/api/analyze/{ticker}/cancel` 在 stream setup 或 cancellation 前會先用 mapping-safe fallback 正規化 requested / active / cancel job row，讓 malformed requested-job row 回落到 active job，malformed cancel-job row 穩定回「找不到可取消的分析任務」，不再讓 compatibility endpoints 回 500；RED→GREEN legacy malformed setup/cancel 單測與文件契約更新通過。
- D952：P3-846 補強 analysis by-id cancel job-row mapping-safe fallback：`api_routes.analysis.cancel_analysis_job_by_id()` 在呼叫 cancel service 前會先用 mapping-safe fallback 正規化 job row，讓 malformed non-mapping `/api/analysis-jobs/{job_id}/cancel` rows 直接回 404 `Analysis job not found`，不再把壞 row 送進取消流程；RED→GREEN malformed by-id cancel job-row 單測與文件契約更新通過。
- D953：P3-847 補強 analysis cancel service job-row mapping-safe fallback：`analysis_job_service.cancel_analysis_job()` 會先用 mapping-safe fallback 正規化 job-store row，讓 malformed service-level job row 回 `None`，不觸發 queue cancellation 或 job cancel request；取消後重新讀取的 row 也會以 mapping-safe fallback 進入 serialization；RED→GREEN malformed service cancel row 單測與文件契約更新通過。
- D954：P3-848 補強 analysis job serialization mapping-safe fallback：`analysis_job_service.serialize_analysis_job()` 在 shaping public response 前會先用 mapping-safe fallback 正規化 job row，讓 malformed non-mapping job-store row 產生安全空 payload，且不輸出空 job id 的 events/status URL；RED→GREEN malformed serialize row 單測與文件契約更新通過。
- D955：P3-849 補強 analysis job lifecycle result mapping-safe fallback：`analysis_job_service.create_or_attach_analysis_job()` 在 queue 決策前會先用 mapping-safe fallback 正規化 create-or-attach result 與 job row，讓 malformed lifecycle job row 回安全空 payload，且不 enqueue unknown job id；RED→GREEN malformed lifecycle job 單測與文件契約更新通過。
- D956：P3-850 補強 analysis job lifecycle created flag explicit-bool queue gate：`analysis_job_service.create_or_attach_analysis_job()` 只接受 `created is False` 走既有任務附加/queue recovery、`created is True` 走新任務 enqueue，讓 malformed created flag truthiness 不再中斷 create response，也不會 requeue unknown lifecycle state；RED→GREEN malformed created flag 單測與文件契約更新通過。
- D957：P3-851 補強 analysis node telemetry row mapping-safe fallback：`analysis_job_service.serialize_node_telemetry()` 在 response shaping 前會先用 mapping-safe fallback 正規化 telemetry row，讓 malformed telemetry store row 變成安全空 telemetry row，而不是中斷 diagnostics API；RED→GREEN malformed telemetry row 單測與文件契約更新通過。
- D958：P3-852 補強 analysis telemetry endpoint setup job-row mapping-safe fallback：`api_routes.analysis.get_analysis_job_telemetry()` 在 diagnostics response 前會先用 mapping-safe fallback 驗證 job-store row，讓 missing 或 malformed telemetry setup job row 穩定回 404 `Analysis job not found`，不再對 invalid job 暴露 telemetry payload；RED→GREEN malformed telemetry setup row 單測與文件契約更新通過。
- D959：P3-853 補強 analysis job serialization status safe-text fallback：`analysis_job_service.serialize_analysis_job()` 在 public response shaping 前會先用 safe text fallback 正規化 `status` 欄位，讓 malformed status truthiness 或字串轉換不再中斷 status/create/cancel payload；RED→GREEN malformed serialize status 單測與文件契約更新通過。
- D960：P3-854 補強 analysis job serialization identity safe-text fallback：`analysis_job_service.serialize_analysis_job()` 在 public response shaping 前會先用 safe text fallback 正規化 `job_id` 欄位，讓 malformed job id truthiness 或字串轉換不再中斷 status/create/cancel payload，也不會輸出空 job id 的 events/status URL；RED→GREEN malformed serialize job id 單測與文件契約更新通過。
- D961：P3-855 補強 analysis job serialization report filename safe-text fallback：`analysis_job_service.serialize_analysis_job()` 在 public response shaping 前會先用 safe text fallback 正規化 `filename` 欄位，讓 malformed filename truthiness 或字串轉換不再中斷 status/create/cancel payload，也不會產生 invalid report URL；RED→GREEN malformed serialize filename 單測與文件契約更新通過。
- D962：P3-856 補強 analysis job serialization pipeline safe-text fallback：`analysis_job_service.serialize_analysis_job()` 在 public response shaping 前會先用 safe text fallback 正規化 `pipeline_id` 欄位，讓 malformed pipeline id truthiness 或字串轉換不再中斷 status/create/cancel payload，並回落到預設 `v1` pipeline；RED→GREEN malformed serialize pipeline id 單測與文件契約更新通過。
- D963：P3-857 補強 analysis job lifecycle identity safe-text queue gate：`analysis_job_service.create_or_attach_analysis_job()` 在 queue 決策前會先用 safe text fallback 正規化 create-or-attach job row 的 `job_id`，讓 malformed lifecycle job id truthiness 或字串轉換不再中斷 create response，也不會 enqueue unknown job id；RED→GREEN malformed lifecycle job id 單測與文件契約更新通過。
- D964：P3-858 補強 analysis job lifecycle status safe-text recovery gate：`analysis_job_service.create_or_attach_analysis_job()` 在 queue recovery 決策前會先用 safe text fallback 正規化 create-or-attach job row 的 `status`，讓 malformed lifecycle status truthiness 或字串轉換不再中斷 create response，也不會 requeue unknown lifecycle state；RED→GREEN malformed lifecycle status 單測與文件契約更新通過。
- D965：P3-859 補強 analysis job input pipeline safe-text fallback：`analysis_job_service.create_or_attach_analysis_job()` 在 lifecycle creation 前會先用 safe text fallback 正規化輸入 `pipeline_id`，讓 malformed input pipeline id truthiness 或字串轉換不再中斷 job creation，並回落到預設 `v1` pipeline；RED→GREEN malformed input pipeline 單測與文件契約更新通過。
- D966：P3-860 補強 analysis job input ticker safe-text gate：`analysis_job_service.create_or_attach_analysis_job()` 在 lifecycle creation 前會先用 safe text fallback 正規化輸入 `ticker`，讓 malformed 或空 input ticker 不再中斷 job creation，也不會建立或 enqueue unknown ticker job；RED→GREEN malformed input ticker 單測與文件契約更新通過。
- D967：P3-861 補強 analysis job input force bool-safe fallback：`analysis_job_service.create_or_attach_analysis_job()` 在 lifecycle creation 前會先用 bool-safe fallback 正規化輸入 `force`，讓 malformed force truthiness 不再中斷 job creation，並保守回落為 non-force job creation；RED→GREEN malformed force flag 單測與文件契約更新通過。
- D968：P3-862 補強 analysis job input resume bool-safe fallback：`analysis_job_service.create_or_attach_analysis_job()` 在 lifecycle creation 前會先用 bool-safe fallback 正規化輸入 `resume`，讓 malformed resume truthiness 不再中斷 job creation，並回落到預設 active-job attachment 行為；RED→GREEN malformed resume flag 單測與文件契約更新通過。
- D969：P3-863 補強 analysis job serialization ticker safe-text fallback：`analysis_job_service.serialize_analysis_job()` 在 public response shaping 前會先用 safe text fallback 正規化 `ticker` 欄位，讓 malformed ticker truthiness 或字串轉換不再中斷 status/create/cancel payload，也不會把 non-JSON job value 洩漏到 public payload；RED→GREEN malformed serialize ticker 單測與文件契約更新通過。
- D970：P3-864 補強 analysis job serialization timestamp finite-float fallback：`analysis_job_service._iso_timestamp()` 在 public response shaping 前會先用 finite-float fallback 正規化 `created_at`、`updated_at`、`started_at` 與 `finished_at`，讓 malformed 或 out-of-range job timestamp 變成 `null`，不再中斷 status/create/cancel payload；RED→GREEN malformed serialize timestamps 單測與文件契約更新通過。
- D971：P3-865 補強 analysis job serialization timestamp empty-check type-safe guard：`analysis_job_service._iso_timestamp()` 只對字串 timestamp 做 empty-string 判斷，其他 malformed timestamp object 直接進入受保護的 finite-float fallback，讓壞 `__eq__` 不再中斷 status/create/cancel payload；RED→GREEN malformed timestamp equality 單測與文件契約更新通過。
- D972：P3-866 補強 analysis job serialization error safe-sanitizer fallback：`security_sanitizer.sanitize_error_message()` 在 public error response shaping 前會捕捉 malformed error string conversion，讓壞 `error.__str__` 變成 `null`，不再中斷 analysis job status/create/cancel payload，也不會把 non-JSON job value 洩漏到 public payload；RED→GREEN malformed serialize error 單測與文件契約更新通過。
- D973：P3-867 補強 analysis node telemetry diagnostics text safe-text fallback：`analysis_job_service._serialize_telemetry_row()` 在 diagnostics response shaping 前會先用 safe text fallback 正規化 telemetry row 的 `job_id`、`ticker`、`pipeline_id`、`node_name`、`model` 與 `status`，讓 malformed telemetry text values 不再中斷 `/api/analysis-jobs/{job_id}/telemetry` payload，也不會把 non-JSON value 洩漏到 diagnostics；RED→GREEN malformed node telemetry text 單測與文件契約更新通過。
- D974：P3-868 補強 analysis node telemetry diagnostics metric/bool fallback：`analysis_job_service._serialize_telemetry_row()` 在 diagnostics response shaping 前會先用 integer- 與 bool-safe fallback 正規化 telemetry row 的 `id`、`latency_ms`、`retry_count`、`input_tokens`、`output_tokens`、`cache_hit` 與 `quality_gate_pass`，讓 malformed telemetry metric values 不再中斷 `/api/analysis-jobs/{job_id}/telemetry` payload，也不會把 non-JSON value 洩漏到 diagnostics；RED→GREEN malformed node telemetry metric 單測與文件契約更新通過。
- D975：P3-869 補強 analysis node telemetry diagnostics strict bool fallback：`analysis_job_service._serialize_telemetry_row()` 在 diagnostics response shaping 前會用 strict bool fallback 正規化 telemetry row 的 `cache_hit` 與 `quality_gate_pass`，讓 binary/container truthiness 不再把 malformed cache-hit 或 quality-gate values 誤判為 true，且保留 explicit bool、accepted truthy strings 與 finite nonzero numbers；RED→GREEN binary/container telemetry bool 單測與文件契約更新通過。
- D976：P3-870 補強 analysis job queue task status safe-text fallback：`analysis_job_service._rq_job_is_active()` 在 RQ active-state classification 前會用 safe text fallback 正規化 RQ job status，讓 malformed RQ status values 不再中斷 queue recovery 或 duplicate-job checks，並保守回落為 inactive；RED→GREEN malformed RQ status 單測與文件契約更新通過。
- D977：P3-871 補強 analysis job queue task status fetch-failure unknown fallback：`analysis_job_service.task_queue_has_task()` 在 RQ job status lookup 失敗時回傳 unknown inspection result，而不是讓 get_status 例外中斷 queue recovery 或 duplicate-job checks，也不把暫時查詢失敗誤判為 confirmed missing task；RED→GREEN RQ status fetch failure 單測與文件契約更新通過。
- D978：P3-872 補強 analysis job queue enqueue failure message safe-text fallback：`analysis_job_service.create_or_attach_analysis_job()` 在新任務 enqueue 或 queue recovery 失敗時使用 safe text fallback 產生 job-store error message，讓 malformed queue exception string conversion 不再中斷 create response 或阻止 error event 落入 `operational.sqlite3`；RED→GREEN malformed enqueue exception 單測與文件契約更新通過。
- D979：P3-873 補強 analysis job queue metadata fetch-failure unknown fallback：`analysis_job_service.task_queue_has_task()` 在讀取 queue adapter 的 `queues`、`queue` 或 `fetch_job` metadata 失敗時回傳 unknown inspection result，讓 malformed queue adapter property 不再於 task lookup 前中斷 queue recovery 或 duplicate-job checks；RED→GREEN queue metadata failure 單測與文件契約更新通過。
- D980：P3-874 補強 analysis job child queue fetch-job metadata unknown fallback：`analysis_job_service.task_queue_has_task()` 在 multi-queue inspection 逐一讀取 child queue 的 `fetch_job` metadata 失敗時回傳 unknown inspection result，讓 malformed nested queue adapter 不再中斷 queue recovery 或 duplicate-job checks；RED→GREEN child queue fetch_job metadata failure 單測與文件契約更新通過。

- D981：P3-875 補強 analysis job queue dedup identity-only guard：`analysis_job_service.task_queue_has_task()` 在合併 queue adapter 的 `queues` 與 primary `queue` 時改用 object identity 判斷重複，避免 child queue 的 malformed `__eq__` 中斷 multi-queue task lookup，並仍能檢查 primary queue 中的 active task；RED→GREEN child queue equality failure 單測與文件契約更新通過。

- D982：P3-876 補強 analysis job RQ status accessor unknown fallback：`analysis_job_service._rq_job_is_active()` 在讀取 RQ job `get_status` accessor 時改走 safe getattr，讓 malformed RQ job status adapter 回 unknown inspection result，不再中斷 queue recovery 或 duplicate-job checks；RED→GREEN RQ status accessor failure 單測與文件契約更新通過。

- D983：P3-877 補強 analysis job RQ fallback status property unknown fallback：`analysis_job_service._rq_job_is_active()` 在 RQ job 沒有可呼叫 `get_status` 而回落讀取 `status` property 時改走 safe getattr，讓 malformed fallback status field 回 unknown inspection result，不再中斷 queue recovery 或 duplicate-job checks；RED→GREEN RQ status property failure 單測與文件契約更新通過。

- D984：P3-878 補強 analysis cancel service status safe-text queue gate：`analysis_job_service.cancel_analysis_job()` 在判斷 queued job 是否需要同步取消 queue task 前使用 safe text fallback，讓 malformed status equality 不再中斷取消 API，且可文字化為 `queued` 的狀態仍會取消 queue task 並送出取消請求；RED→GREEN malformed cancel status equality 單測與文件契約更新通過。

- D985：P3-879 補強 analysis cancel service queue cancel accessor fallback：`analysis_job_service.cancel_analysis_job()` 在讀取 task queue 的 `cancel` accessor 前改走 safe getattr，讓 malformed queue cancel adapter 不再阻斷 job-store cancellation request；RED→GREEN queue cancel accessor failure 單測與文件契約更新通過。

- D986：P3-880 補強 legacy analysis requested-job ticker safe-text fallback：legacy `/api/analyze/{ticker}` stream setup 在驗證 requested job row 的 `ticker` 前使用 safe text fallback，讓 malformed requested ticker equality 不再讓相容 stream 回 500，而是回落到 active job 繼續輸出；RED→GREEN malformed legacy requested ticker 單測與文件契約更新通過。

- D987：P3-881 補強 legacy analysis requested-job pipeline safe-text fallback：legacy `/api/analyze/{ticker}` stream setup 在驗證 requested job row 的 `pipeline_id` 前使用 safe text fallback，讓 malformed requested pipeline equality 不再讓相容 stream 回 500，而是回落到 active job 繼續輸出；RED→GREEN malformed legacy requested pipeline 單測與文件契約更新通過。

- D988：P3-882 補強 legacy analysis requested-job identity safe-text fallback：legacy `/api/analyze/{ticker}` stream setup 在驗證 requested job row 的 `job_id` 前使用 safe text fallback，讓 malformed requested job-id truthiness 或 string conversion 不再讓相容 stream 回 500，而是回落到 active job 繼續輸出；RED→GREEN malformed legacy requested job id 單測與文件契約更新通過。

- D989：P3-883 補強 legacy analysis cancel ticker safe-text fallback：legacy `/api/analyze/{ticker}/cancel` 在驗證 cancel job row 的 `ticker` 前使用 safe text fallback，讓 malformed cancel ticker equality 不再讓相容取消 API 回 500，而是穩定回 `{ok:false, message:"找不到可取消的分析任務"}` 且不送出取消請求；RED→GREEN malformed legacy cancel ticker 單測與文件契約更新通過。

- D990：P3-884 補強 legacy analysis cancel pipeline safe-text fallback：legacy `/api/analyze/{ticker}/cancel` 在驗證 cancel job row 的 `pipeline_id` 前使用 safe text fallback，讓 malformed cancel pipeline equality 不再讓相容取消 API 回 500，而是穩定回 `{ok:false, message:"找不到可取消的分析任務"}` 且不送出取消請求；RED→GREEN malformed legacy cancel pipeline 單測與文件契約更新通過。

- D991：P3-885 補強 legacy analysis active-job identity safe-text fallback：legacy `/api/analyze/{ticker}` stream setup 在沿用 active job row 的 `job_id` 前使用 safe text fallback，讓 malformed active job-id truthiness 或 string conversion 不再讓相容 stream 回 500，而是回落到 create-or-attach job path 繼續輸出；RED→GREEN malformed legacy active job id 單測與文件契約更新通過。

- D992：P3-886 補強 analysis job legacy create fallback identity safe-text guard：`api_routes.analysis._legacy_create_and_enqueue_via_deps()` 在 queue enqueue 前使用 safe text fallback 正規化 fallback `create_job()` 回傳的 `job_id`，讓 malformed fallback job-id truthiness 或 string conversion 不再讓 create response 回 500，也不 enqueue unknown task；RED→GREEN malformed legacy create fallback job id 單測與文件契約更新通過。

- D993：P3-887 補強 analysis job legacy create fallback queue exception safe-text guard：`api_routes.analysis._legacy_create_and_enqueue_via_deps()` 在 fallback queue enqueue 失敗時使用 safe text fallback 組 job-store error message，讓 malformed fallback queue exception string conversion 不再讓 create response 回 500，也不阻止 terminal error event 落入 job store；RED→GREEN malformed legacy fallback queue exception 單測與文件契約更新通過。

- D994：P3-888 補強 analysis SSE intro identity safe-text guard：`/api/analysis-jobs/{job_id}/events` 在 initial job event 輸出前使用 safe text fallback 正規化 setup job row 的 `ticker` 與 `pipeline_id`，讓 malformed setup identity 不再中斷 SSE intro event，並讓 pipeline 回落 `v1`；RED→GREEN malformed analysis SSE intro identity 單測與文件契約更新通過。

- D995：P3-889 補強 legacy analysis cancel result bool-safe guard：legacy `/api/analyze/{ticker}/cancel` 在 response shaping 前使用 bool-safe fallback 正規化 `request_job_cancel()` 回傳值，讓 malformed cancel adapter result truthiness 不再讓相容取消 API 回 500，而是回落 `ok:false` / `status:not_found`；RED→GREEN malformed legacy cancel result 單測與文件契約更新通過。

- D996：P3-890 補強 analysis job by-id cancel fallback result bool-safe guard：`/api/analysis-jobs/{job_id}/cancel` 在沒有 service-level cancel handler 的 fallback branch 會先用 bool-safe fallback 正規化 `request_job_cancel()` 回傳值，讓 malformed fallback cancel adapter result truthiness 不再讓 by-id cancel API 回 500，而是回落 `status:not_found`；RED→GREEN malformed by-id cancel fallback result 單測與文件契約更新通過。

- D997：P3-891 補強 analysis job by-id cancel service result mapping-safe guard：`/api/analysis-jobs/{job_id}/cancel` 在 service-level cancel handler 回傳後先使用 mapping-safe fallback 驗證 response payload，讓 malformed service result 不再以 200 malformed body 外漏，而是穩定回 404 `Analysis job not found`；RED→GREEN malformed by-id cancel service result 單測與文件契約更新通過。

- D998：P3-892 補強 analysis job telemetry serializer result mapping-safe guard：`/api/analysis-jobs/{job_id}/telemetry` 在確認 job row 存在後，會再用 mapping-safe fallback 驗證 telemetry serializer 回傳 payload，讓 malformed telemetry adapter result 不再以 200 malformed body 外漏，而是穩定回空 telemetry list；RED→GREEN malformed telemetry serializer result 單測與文件契約更新通過。

- D999：P3-893 補強 analysis job create handler result mapping-safe guard：`/api/analysis-jobs` 在 service-level create handler 回傳後先使用 mapping-safe fallback 驗證 response payload，讓 malformed route-level create adapter result 不再以 200 malformed body 外漏，而是穩定回安全空 job payload；RED→GREEN malformed create handler result 單測與文件契約更新通過。

- D1000：P3-894 補強 legacy analysis stream create handler result mapping-safe guard：legacy `/api/analyze/{ticker}` 在沒有 requested/active job 且 service-level create handler 回傳 malformed payload 時，會先用 mapping-safe fallback 驗證 create result，沒有可信 `job_id` 就回落 legacy `create_job + enqueue`，讓相容 stream 不再因壞 create adapter payload 回 500；RED→GREEN malformed legacy create handler result 單測與文件契約更新通過。

- D1001：P3-895 補強 legacy analysis stream fallback queue exception safe-text guard：legacy `/api/analyze/{ticker}` 在回落 `create_job + enqueue` 且 queue enqueue 失敗時使用 safe text fallback 組錯誤訊息，讓 malformed queue exception string conversion 不再讓相容 stream 回 500，也不阻止 terminal error event 落入 job stream；RED→GREEN malformed legacy fallback enqueue exception 單測與文件契約更新通過。

- D1002：P3-896 補強 legacy analysis stream intro pipeline sequence-safe guard：legacy `/api/analyze/{ticker}` 在輸出 deprecated intro payload 前會以 sequence-safe 與 safe text fallback 正規化 `pipeline_sequence`，讓 malformed pipeline metadata adapter 不再因 `list(...)` 或 JSON serialization 中斷相容 stream；RED→GREEN malformed legacy pipeline sequence 單測與文件契約更新通過。

- D1003：P3-897 補強 legacy analysis stream intro pipeline label safe-text guard：legacy `/api/analyze/{ticker}` 在輸出 deprecated intro payload 前會以 safe text fallback 正規化 `pipeline_label`，讓 malformed pipeline label metadata adapter 不再中斷相容 stream 或造成空 SSE 內容；RED→GREEN malformed legacy pipeline label 單測與文件契約更新通過。

- D1004：P3-898 補強 legacy analysis stream intro agent total integer-safe guard：legacy `/api/analyze/{ticker}` 在輸出 deprecated intro payload 前會以 binary/bool-safe integer fallback 正規化 `agent_total`，讓 malformed agent-count metadata 不再中斷相容 stream，也不把二進位內容合成有效 agent count；RED→GREEN malformed legacy agent total 單測與文件契約更新通過。

- D1005：P3-899 補強 legacy analysis stream resume cursor negative-header fallback：legacy `/api/analyze/{ticker}` 改用共用 resume cursor 解析器處理 `Last-Event-ID`，讓負數 reconnect header 不再傳入 job-store event replay query，而是回落到 `0` 並保持 deprecated intro payload 可讀；RED→GREEN negative legacy resume header 單測與文件契約更新通過。

- D1006：P3-900 補強 legacy analysis stream missing API key message safe-text fallback：legacy `/api/analyze/{ticker}` 在缺少 API key 並輸出 SSE error 前使用 safe text fallback 正規化 `api_key_setup_message()`，讓 malformed setup-message payload 不再造成相容 error stream 空白或中斷；RED→GREEN malformed missing-key message 單測與文件契約更新通過。

- D1007：P3-901 補強 legacy analysis stream API key readiness strict-bool fallback：legacy `/api/analyze/{ticker}` 在 stream setup 前以 strict bool fallback 判斷 `has_api_keys()`，讓 malformed truthy readiness payload 保守回落到 missing-key error stream，不再誤建立或 enqueue analysis job；RED→GREEN malformed API-key readiness 單測與文件契約更新通過。

- D1008：P3-902 補強 legacy analysis stream normalized pipeline safe-text fallback：legacy `/api/analyze/{ticker}` 在 stream setup 前使用 safe text fallback 正規化 `normalize_pipeline_run_id()` 回傳值，讓 malformed normalized pipeline payload 回落到 `v1`，不再讓 deprecated intro payload JSON serialization 中斷；RED→GREEN malformed normalized pipeline 單測與文件契約更新通過。

- D1009：P3-903 補強 legacy analysis cancel normalized pipeline safe-text fallback：legacy `/api/analyze/{ticker}/cancel` 在 cancellation validation 前使用同一個 safe text fallback 正規化 `normalize_pipeline_run_id()` 回傳值，讓 malformed normalized pipeline payload 回落到 `v1`，不再把可取消的相容分析任務誤判為 not found；RED→GREEN malformed cancel normalized pipeline 單測與文件契約更新通過。

- D1010：P3-904 補強 analysis job create route normalized pipeline safe-text fallback：`POST /api/analysis-jobs` 在 create handler dispatch 前使用 `_safe_pipeline_id()` 正規化 `normalize_pipeline_run_id()` 回傳值，讓 malformed route-level normalized pipeline payload 回落到 `v1`，不再中斷 create response 或把 malformed pipeline 傳入 create handler；RED→GREEN malformed create normalized pipeline 單測與文件契約更新通過。

- D1011：P3-905 補強 analysis job create handler field JSON-safe fallback：`POST /api/analysis-jobs` 在 service-level create handler 回傳 mapping 後，先用 serializer-backed response shaping 補齊 public job 欄位，再做 JSON-safe fallback，讓 malformed route-level field value 不再讓 create response 回 500 或外漏 non-JSON payload；RED→GREEN malformed create handler field 單測與文件契約更新通過。

- D1012：P3-906 補強 analysis job by-id cancel service field JSON-safe fallback：`POST /api/analysis-jobs/{job_id}/cancel` 在 service-level cancel handler 回傳 mapping 後，會先做 JSON-safe response shaping，讓 malformed service-level cancellation field value 不再讓 cancel response 回 500 或外漏 non-JSON payload；RED→GREEN malformed by-id cancel service field 單測與文件契約更新通過。

- D1013：P3-907 補強 analysis job telemetry serializer field JSON-safe fallback：`GET /api/analysis-jobs/{job_id}/telemetry` 在 telemetry serializer 回傳 mapping 後，會先做 JSON-safe diagnostics response shaping，讓 malformed telemetry adapter field value 不再讓 diagnostics response 回 500 或外漏 non-JSON payload；RED→GREEN malformed telemetry serializer field 單測與文件契約更新通過。

- D1014：P3-908 補強 analysis job status serializer field JSON-safe fallback：`GET /api/analysis-jobs/{job_id}` 在 status serializer 回傳 mapping 後，會先做 JSON-safe response shaping，讓 malformed status adapter field value 不再讓 public status response 回 500 或外漏 non-JSON payload；RED→GREEN malformed status serializer field 單測與文件契約更新通過。

- D1015：P3-909 補強 analysis job legacy create fallback serializer field JSON-safe fallback：legacy create fallback branch 在 `_legacy_create_and_enqueue_via_deps()` 回傳 public create response 前改走 `_serialize_create_result()`，讓 malformed fallback serializer field value 不再讓 legacy create response 回 500 或外漏 non-JSON payload；RED→GREEN malformed legacy create serializer field 單測與文件契約更新通過。

- D1016：P3-910 補強 analysis job telemetry request-id safe-text fallback：analysis telemetry serializer 在查詢 node telemetry 與輸出 diagnostics payload 前會先以 safe text 正規化 requested job id，讓 malformed telemetry request id 不再外漏 non-JSON payload 或傳入 telemetry store lookup；RED→GREEN malformed telemetry request id 單測與文件契約更新通過。

- D1017：P3-911 補強 analysis job cancellation service request-id safe-text fallback：analysis cancel service 在查詢 job-store、queue-side cancellation 與 request cancellation 前會先以 safe text 正規化 requested job id，讓 malformed cancel request id 不再外漏 non-JSON payload 或傳入 cancellation store/queue adapter；RED→GREEN malformed cancel request id 單測與文件契約更新通過。

- D1018：P3-912 補強 analysis job queue task-id safe-text fallback：`analysis_task_id()` 在組 RQ task key 前會先以 safe text 正規化 job id，讓 malformed job id 不再把 Python object representation 外漏到 queue task identity；RED→GREEN malformed task id helper 單測與文件契約更新通過。

- D1019：P3-913 補強 analysis job queue task lookup-id safe-text fallback：`task_queue_has_task()` 在呼叫 queue adapter `fetch_job()` 前會先以 safe text 正規化 task id，讓 malformed lookup id 不再把 Python object representation 傳入 RQ adapter；RED→GREEN malformed task lookup id 單測與文件契約更新通過。

- D1020：P3-914 補強 analysis job id builder input safe-text fallback：`build_analysis_job_id()` 在 ticker/pipeline slug 建構前會先以 safe text 正規化輸入，讓 malformed ticker 或 pipeline id 不再中斷 job creation，也不把 Python object representation 外漏到 job id；RED→GREEN malformed job id builder input 單測與文件契約更新通過。

- D1021：P3-915 補強 analysis job id builder force-flag bool-safe fallback：`build_analysis_job_id()` 在選擇 force/random suffix 前會先以 bool-safe fallback 正規化 force flag，讓 malformed force truthiness 保守回落到 deterministic non-force job id 建構，不再中斷 job creation；RED→GREEN malformed builder force flag 單測與文件契約更新通過。

- D1022：P3-916 補強 analysis job input binary/container force-flag conservative fallback：`create_or_attach_analysis_job()` 共用的 `_safe_bool_flag()` 會將 binary 與 collection payload 視為 malformed 並回落 default，讓 `memoryview` 等 force 輸入不再誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN binary force flag 單測與文件契約更新通過。

- D1023：P3-917 補強 analysis job input string force-flag bool-text fallback：共用 `_safe_bool_flag()` 會先解析 string bool 值，讓 `"false"`、`"0"`、`"no"` 或 blank force 輸入保守回落 non-force job creation，不再誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN string false force flag 單測與文件契約更新通過。

- D1024：P3-918 補強 analysis job input non-finite numeric force-flag fallback：共用 `_safe_bool_flag()` 會先檢查數值 flag 是否為有限值，讓 `NaN` 或 infinite force 輸入保守回落 non-force job creation，不再誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN non-finite force flag 單測與文件契約更新通過。

- D1025：P3-919 補強 analysis job input complex force-flag fallback：共用 `_safe_bool_flag()` 會將 complex force 輸入視為 malformed 並回落 default，讓 complex numbers 不再因 Python truthiness 誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN complex force flag 單測與文件契約更新通過。

- D1026：P3-920 補強 analysis job input Decimal force-flag finite fallback：共用 `_safe_bool_flag()` 會將 Decimal 納入有限數值判斷，讓 Decimal `NaN` 或 infinite force 輸入保守回落 non-force job creation，不再誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN Decimal NaN force flag 單測與文件契約更新通過。

- D1027：P3-921 補強 analysis job input numeric force-flag explicit 0/1 contract：共用 `_safe_bool_flag()` 的 finite numeric 分支只接受明確 `0` 或 `1`，讓 `0.5` 或 out-of-range numeric force 輸入保守回落 non-force job creation，不再因任意非零 truthiness 誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN fractional numeric force flag 單測與文件契約更新通過。

- D1028：P3-922 補強 analysis job input Fraction force-flag explicit 0/1 contract：共用 `_safe_bool_flag()` 會將 Fraction 納入 finite numeric 分支並套用明確 `0`/`1` 合約，讓 `Fraction(1, 2)` 這類 exact fractional numeric force 輸入保守回落 non-force job creation，不再因 Python truthiness 誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN Fraction force flag 單測與文件契約更新通過。

- D1029：P3-923 補強 analysis job input arbitrary object force-flag conservative fallback：共用 `_safe_bool_flag()` 不再對未知物件呼叫 `bool(value)`，只接受明確 bool/text/numeric 合約，讓自訂 truthy object 不再誤觸 forced refresh 或多送 force-refresh queue argument；RED→GREEN arbitrary truthy force flag 單測與文件契約更新通過。

- D1030：P3-924 補強 analysis node telemetry arbitrary object bool fallback：`_serialize_telemetry_row()` 共用的 `_safe_bool_field()` 不再對未知物件呼叫 `bool(value)`，讓自訂 truthy object 不會把 `cache_hit` 或 `quality_gate_pass` 診斷欄位誤標成 true；RED→GREEN arbitrary truthy telemetry bool 單測與文件契約更新通過。

- D1031：P3-925 補強 analysis node telemetry optional metric fractional guard：`_safe_optional_int()` 只接受有限且本身為整數的 numeric payload，讓 `id`、`latency_ms`、`input_tokens`、`output_tokens` 不會把 fractional telemetry 值靜默截斷成看似有效的診斷整數；RED→GREEN fractional optional metric 單測與文件契約更新通過。

- D1032：P3-926 補強 analysis node telemetry retry-count fractional guard：`_safe_int()` 只接受整數、整數字串、有限整數 float、integral Decimal 與 denominator 為 1 的 Fraction，讓 `retry_count` 不會把 fractional telemetry 值靜默截斷成看似有效的重試次數；RED→GREEN fractional retry-count 單測與文件契約更新通過。

- D1033：P3-927 補強 analysis node telemetry optional metric exact-numeric fractional guard：`_safe_optional_int()` 在 float fallback 前先用 Decimal/Fraction 原生整數性判斷，讓高精度 fractional exact numeric `id`、`latency_ms`、`input_tokens`、`output_tokens` 不會因 float 精度丟失被四捨五入成 synthetic diagnostics integer；RED→GREEN fractional exact optional metric 單測與文件契約更新通過。

- D1034：P3-928 補強 analysis node telemetry optional metric arbitrary-object fallback：`_safe_optional_int()` 僅接受明確 primitive numeric/text 與 Decimal/Fraction，讓提供 `__float__` / `__int__` 的未知 telemetry adapter object 不會被合成為可信的 `id`、`latency_ms`、`input_tokens` 或 `output_tokens` 診斷整數；RED→GREEN arbitrary numeric optional metric 單測與文件契約更新通過。

- D1035：P3-929 補強 analysis node telemetry optional metric non-negative guard：`_safe_optional_int()` 會拒收負數 `id`、`latency_ms`、`input_tokens`、`output_tokens`，避免 diagnostics payload 外漏不可能的負 latency 或 token count，並把 malformed telemetry 降級為 `None`；RED→GREEN negative optional metric 單測與文件契約更新通過。

- D1036：P3-930 補強 analysis node telemetry retry-count non-negative guard：`_safe_int()` 會拒收負數 `retry_count` 並回落 `0`，避免 diagnostics payload 外漏不可能的負重試次數，讓 retry diagnostics 和 latency/token count 一樣維持非負計數語意；RED→GREEN negative retry-count 單測與文件契約更新通過。

- D1037：P3-931 補強 analysis node telemetry bool numeric explicit 0/1 guard：`_safe_bool_field()` 的 numeric 分支只接受明確 `0` 或 `1`，讓 `cache_hit` / `quality_gate_pass` 的 out-of-range 數值不會被 Python nonzero truthiness 誤標成 true diagnostics；RED→GREEN out-of-range numeric bool 單測與文件契約更新通過。

- D1038：P3-932 補強 analysis node telemetry bool exact-numeric explicit 0/1 guard：`_safe_bool_field()` 會先用 Decimal/Fraction 原生比較套用明確 `0`/`1` 合約，讓 exact numeric `cache_hit` / `quality_gate_pass` 診斷欄位和 int/float 維持同一個 bool 語意，不會透過 truthiness 或 arbitrary object fallback 被誤報；RED→GREEN exact numeric bool 單測與文件契約更新通過。

- D1039：P3-933 補強 analysis node telemetry timestamp arbitrary-object fallback：`_iso_timestamp()` 只接受明確 primitive/exact numeric timestamp 型別，讓提供 `__float__` 的未知 telemetry adapter object 不會被合成為可信的 `started_at` 或 `finished_at` 診斷時間；RED→GREEN arbitrary numeric timestamp 單測與文件契約更新通過。

- D1040：P3-934 補強 analysis job input Decimal force-flag exact 0/1 guard：`_safe_bool_flag()` 會先用 Decimal 原生有限值與明確 `0`/`1` 比較判斷 force flag，避免 `Decimal("1.0000000000000000001")` 透過 float precision loss 被誤判為 forced refresh 並多送 queue `force_refresh=True` argument；RED→GREEN Decimal fractional force flag 單測與文件契約更新通過。

- D1041：P3-935 補強 analysis node telemetry row collection iterable fallback：`serialize_node_telemetry()` 會先把 telemetry store 回傳的 row collection 正規化為可迭代 tuple，讓 `None` 或 malformed non-iterable result 回落為空 telemetry list，而不是中斷 diagnostics response；RED→GREEN malformed telemetry row collection 單測與文件契約更新通過。

- D1042：P3-936 補強 analysis node telemetry row collection iterator partial-failure fallback：`_safe_telemetry_rows()` 會逐筆收集 telemetry rows，iterator 中途失敗時停止並保留已讀有效 rows，避免部分 telemetry store result failure 抹掉已可用的 diagnostics evidence；RED→GREEN partial iterator failure 單測與文件契約更新通過。

- D1043：P3-937 補強 analysis job serialization report filename path-segment guard：`serialize_analysis_job()` 在輸出 public `report_path` 前會先用 `_safe_report_filename()` 確認 filename 是單一安全 path segment，避免 `../report.html`、absolute path 或 nested path payload 產生 traversal / absolute `/api/report/...` URL；RED→GREEN path-like filename 單測與文件契約更新通過。

- D1044：P3-938 補強 analysis job serialization report filename URL-delimiter guard：`serialize_analysis_job()` 在輸出 public `report_path` 前會拒收 query、fragment 與 percent-encoded separator filename，避免 `report.html?download=1`、`report.html#section` 或 encoded path separator payload 產生 ambiguous `/api/report/...` URL；RED→GREEN URL-like filename 單測與文件契約更新通過。

- D1045：P3-939 補強 analysis job serialization report filename control-character guard：`serialize_analysis_job()` 在輸出 public `report_path` 前會拒收 newline、carriage return、tab、NUL 等 ASCII control characters，避免 invisible delimiter payload 產生 malformed `/api/report/...` URL；RED→GREEN control-character filename 單測與文件契約更新通過。

- D1046：P3-940 補強 analysis job serialization report filename percent-encoded delimiter guard：`serialize_analysis_job()` 在輸出 public `report_path` 前會拒收 `%3F`、`%23`、`%00`、`%0A` 等 encoded delimiter/control payload，避免 URL decode 後才浮現的 query、fragment、separator 或 control 字元產生 ambiguous `/api/report/...` URL；RED→GREEN encoded delimiter filename 單測與文件契約更新通過。

- D1047：P3-941 補強 analysis job serialization identity URL-helper path-segment guard：`serialize_analysis_job()` 在輸出 `events_url` 與 `status_url` 前會先用 public URL segment guard 驗證 `job_id`，讓 path-like、encoded delimiter 或 control-character job id 保留為可診斷文字，但不產生 ambiguous `/api/analysis-jobs/...` helper URL；RED→GREEN path-like job id URL-helper 單測與文件契約更新通過。

- D1048：P3-942 補強 analysis job serialization padded status mapping：`serialize_analysis_job()` 在 `_STATUS_MAP` 查表前會先 strip status safe text，讓 padded internal status 如 `" done "` 或 `"\twaiting_retry\n"` 仍映射為穩定 public status `completed` / `running`，避免 adapter whitespace 讓 UI 接到未正規化狀態；RED→GREEN padded status 單測與文件契約更新通過。

- D1049：P3-943 補強 analysis job serialization known status case mapping：`serialize_analysis_job()` 會用 lowercase key 查 `_STATUS_MAP`，讓 `DONE`、`Waiting_Retry`、`ERROR` 等 uppercase/mixed-case 已知 internal statuses 仍映射為穩定 public status，同時保留未知 status 的 trimmed 原文以利診斷；RED→GREEN known status case 單測與文件契約更新通過。

- D1050：P3-944 補強 analysis job serialization public URL segment whitespace guard：`_safe_public_url_segment()` 會拒收任何 whitespace，讓 `job_id` 或 report filename 內含 visible/invisible spacing 時不再輸出 malformed `events_url`、`status_url` 或 `report_path`，但 `job_id` 文字仍保留供診斷；RED→GREEN whitespace URL segment 單測與文件契約更新通過。

- D1051：P3-945 補強 analysis job serialization public URL segment double-encoded delimiter guard：`_safe_public_url_segment()` 會拒收 encoded percent token，讓 `job_id` 或 report filename 內含 `%252F`、`%253F`、`%250A` 等 double-encoded delimiter/control payload 時不再輸出 ambiguous `events_url`、`status_url` 或 `report_path`，但原始文字仍保留供診斷；RED→GREEN double-encoded URL segment 單測與文件契約更新通過。

- D1052：P3-946 補強 analysis job queue task identity path-segment guard：`analysis_task_id()` 會重用 public URL segment guard 建立 RQ task key，讓 path-like、encoded delimiter、double-encoded delimiter 或 whitespace `job_id` 不再產生 ambiguous `analysis:...` queue key；RED→GREEN path-like task id 單測與文件契約更新通過。

- D1053：P3-947 補強 report quality repair queue snapshot integrity verifier-result guard：`snapshot_integrity_repair_item()` 會把 raw verifier payload 的 `valid = false` 視為 invalid snapshot integrity，避免只有 `valid/hash/expected_hash/errors`、尚未被 report-index 投影成 `status = invalid` 的損壞 snapshot 被 repair queue 漏掉；RED→GREEN valid=false snapshot integrity 單測與文件契約更新通過。

- D1054：P3-948 補強 report quality repair queue snapshot integrity contradictory-status guard：`snapshot_integrity_repair_item()` 會讓 `valid = false` 覆蓋非 invalid 的 `status` 文字，避免 `status = verified` / `valid = false` 這類矛盾 metadata 隱藏 snapshot hash mismatch；RED→GREEN contradictory snapshot integrity 單測與文件契約更新通過。

- D1055：P3-949 補強 report preview reading boundary snapshot integrity contradictory-status guard：`report_reading_boundary_policy.js` 會讓 `snapshot_integrity.valid = false` 直接進入 blocked reading boundary，即使 `status = verified`，避免預覽層把矛盾 snapshot hash metadata 標成可採用；RED→GREEN preview boundary contradictory snapshot integrity 單測與文件契約更新通過。

- D1056：P3-950 補強 report reading notice snapshot integrity contradictory-status guard：`reading_notice` 會讓 `snapshot_integrity.valid = false` 在 HTML/Markdown 使用限制 notice 進入 blocked 狀態，即使 `status = verified`，並把 snapshot hash mismatch 細節帶進 notice，避免完整報告正文把矛盾 snapshot metadata 標成可引用；RED→GREEN reading notice contradictory snapshot integrity 單測與文件契約更新通過。

- D1057：P3-951 補強 report view/download snapshot integrity view-time guard：`get_report_file()` 與 HTML download 會在回傳 stored HTML 前重新讀取同 bundle 的 `.data.json` 並驗證 snapshot hash；若目前 snapshot invalid，`repair_report_html_for_view()` 會以 blocked reading notice 取代 artifact 內舊的 passed notice，避免報告生成後 snapshot 損壞時完整報告頁仍顯示可引用；RED→GREEN view/download invalid snapshot 單測與文件契約更新通過。

- D1058：P3-952 補強 report Markdown download snapshot integrity view-time guard：Markdown download 會在回傳 stored `.md` 前重用同 bundle `.data.json` 的 snapshot integrity 驗證結果；若目前 snapshot invalid，`repair_report_markdown_for_download()` 會以 blocked Markdown reading notice 取代 artifact 內舊的 passed notice，避免複製或下載 Markdown 報告時引用已損壞 snapshot 的舊綠燈文案；RED→GREEN Markdown download invalid snapshot 單測與文件契約更新通過。

- D1059：P3-953 補強 malformed data snapshot artifact notice guard：view-time notice context 會把不可解析 JSON 或非物件 `.data.json` 視為 blocked snapshot integrity，並在 HTML view 與 Markdown download 中替換 artifact 內舊的 passed notice，避免 snapshot 檔案本身損壞時報告仍顯示可引用；RED→GREEN malformed snapshot HTML/Markdown 單測與文件契約更新通過。

- D1060：P3-954 補強 backend reading notice unverified snapshot warning guard：`reading_notice` 會把已記錄但非 verified 的 `snapshot_integrity` 降級為 warning，讓 HTML/Markdown 使用前提示與 preview reading boundary 對齊，避免 legacy 或缺 hash snapshot 在完整報告正文中顯示為 passed；RED→GREEN unverified snapshot reading notice 單測與文件契約更新通過。

- D1061：P3-955 補強 missing data snapshot artifact warning guard：view-time notice context 會把缺少 `.data.json` 視為 unverified snapshot integrity warning，並允許 HTML/Markdown artifact repair 替換 warning notice，避免 legacy report 或遺失 snapshot 的報告仍保留舊 passed 文案；RED→GREEN missing snapshot HTML/Markdown 單測與文件契約更新通過。

- D1062：P3-956 補強 recorded invalid snapshot artifact guard：view-time notice context 會先尊重 `.data.json` 內已記錄的 invalid `snapshot_integrity`（包含 `valid=false` 覆蓋非 invalid 狀態），再回到即時 hash 驗證，讓 hashless 但已被 verifier 判定失敗的 snapshot 不再讓 stored HTML/Markdown artifact 保留舊 passed notice；RED→GREEN recorded invalid snapshot HTML/Markdown 單測與文件契約更新通過。

- D1063：P3-957 補強 nested snapshot integrity artifact guard：view-time notice context 會同時讀取 `.data.json` top-level `snapshot_integrity` 與 nested `data.snapshot_integrity`，讓完整報告 HTML 檢視與 Markdown 下載在遇到 nested invalid snapshot metadata 時同樣替換舊 passed notice，避免 renderer / snapshot 結構差異造成報告品質邊界不一致；RED→GREEN nested invalid snapshot HTML/Markdown 單測與文件契約更新通過。

- D1064：P3-958 補強 recorded snapshot integrity invalid-priority guard：view-time notice context 在 top-level 與 nested `data.snapshot_integrity` 同時存在時，會先挑出任何 `status=invalid` 或 `valid=false` 的 recorded integrity，再考慮 non-invalid 記錄，避免 top-level verified metadata 遮蔽 nested invalid blocker，讓 HTML 檢視與 Markdown 下載都替換舊 passed notice；RED→GREEN conflicting recorded integrity HTML/Markdown 單測與文件契約更新通過。

- D1065：P3-959 補強 recorded snapshot integrity detail-priority guard：view-time notice context 在多個 recorded invalid integrity 同時存在時，會優先選擇帶有具體 `errors` detail 的 blocker，避免 top-level generic invalid metadata 吃掉 nested provider audit / hash mismatch 細節，讓 HTML 檢視與 Markdown 下載保留可診斷的品質失敗原因；RED→GREEN specific invalid detail HTML/Markdown 單測與文件契約更新通過。

- D1066：P3-960 補強 recorded snapshot integrity generic-detail demotion guard：view-time notice context 會把預設泛用 snapshot integrity blocker 文案視為低特異性 detail，若 nested invalid integrity 有 hash / provider-audit mismatch 等具體錯誤，HTML 檢視與 Markdown 下載會優先顯示具體錯誤，避免「非空但泛用」的 top-level errors 遮蔽真正可診斷原因；RED→GREEN generic-detail demotion HTML/Markdown 單測與文件契約更新通過。

- D1067：P3-961 補強 recorded snapshot integrity hash-mismatch detail fallback：view-time notice context 在 recorded invalid integrity 沒有 `errors` 但 `hash` 與 `expected_hash` 同時存在且不一致時，會推導 `snapshot_hash mismatch` 作為 blocked notice detail，讓 HTML 檢視與 Markdown 下載不再只顯示泛用完整性失敗文案；RED→GREEN recorded hash mismatch detail HTML/Markdown 單測與文件契約更新通過。

- D1068：P3-962 補強 same-record generic integrity error demotion guard：view-time notice context 在同一筆 recorded invalid integrity 同時有預設泛用 `errors` 與不一致的 `hash` / `expected_hash` 時，會優先顯示 `snapshot_hash mismatch`，避免 boilerplate blocker text 遮蔽真正可追查的 hash 證據；RED→GREEN same-record generic/hash mismatch HTML/Markdown 單測與文件契約更新通過。

- D1069：P3-963 補強 mixed recorded integrity errors detail cleanup：view-time notice context 在同一筆 recorded invalid integrity 的 `errors` 同時包含預設泛用 blocker 與具體 provider/hash detail 時，會移除泛用 blocker、只保留具體 detail，讓 HTML 檢視與 Markdown 下載更聚焦於可追查的品質失敗原因；RED→GREEN mixed generic/specific errors HTML/Markdown 單測與文件契約更新通過。

- D1070：P3-964 補強 recorded snapshot integrity error deduplication guard：view-time notice context 會在修復 stored HTML/Markdown reading notice 前對 recorded snapshot integrity `errors` 做順序保留去重，避免同一個 provider/hash detail 在報告上重複顯示，讓 blocked notice 更短、更可讀且仍保留首次出現的診斷順序；RED→GREEN duplicate recorded errors HTML/Markdown 單測與文件契約更新通過。

- D1071：P3-965 補強 live reading notice snapshot integrity error deduplication guard：`reporting.reading_notice` 在產生完整報告 HTML/Markdown 使用限制 notice 時，會對 `snapshot_integrity.errors` 做順序保留去重，避免 live/generated report notice 和 stored artifact repair notice 對同一 provider/hash detail 呈現不一致；RED→GREEN duplicate live reading notice errors 單測與文件契約更新通過。

- D1072：P3-966 補強 live reading notice generic snapshot blocker demotion guard：`reporting.reading_notice` 在完整報告 HTML/Markdown 使用限制 notice 中，若 `snapshot_integrity.errors` 同時包含預設泛用 blocker 與具體 provider/hash detail，會移除泛用 blocker、保留具體 detail，讓 live/generated report notice 與 stored artifact repair notice 對 actionable failure reason 的呈現一致；RED→GREEN generic/specific live reading notice 單測與文件契約更新通過。

- D1073：P3-967 補強 preview reading boundary generic snapshot blocker demotion guard：`report_reading_boundary_policy.js` 在 preview reading boundary 中，若 `snapshot_integrity.errors` 同時包含預設泛用 blocker 與具體 provider/hash detail，會移除泛用 blocker、保留具體 detail，讓預覽層在開完整報告前就顯示 actionable failure reason；RED→GREEN generic/specific preview boundary 單測與文件契約更新通過。

- D1074：P3-968 補強 preview reading boundary snapshot detail deduplication guard：`report_reading_boundary_policy.js` 在 preview reading boundary 顯示 snapshot integrity detail 前會做順序保留去重，避免同一 provider/hash detail 在預覽層重複出現，讓 preview、live reading notice 與 stored artifact repair 對重複錯誤的呈現一致；RED→GREEN duplicate preview boundary detail 單測與文件契約更新通過。

- D1075：P3-969 補強 report quality repair queue generic snapshot blocker demotion guard：`snapshot_integrity_repair_item()` 在 repair queue action prioritization 前會移除與具體 provider/hash detail 同列的預設泛用 snapshot integrity blocker，避免人工審核佇列把 boilerplate 與 actionable failure reason 混在一起；RED→GREEN generic/specific repair queue 單測與文件契約更新通過。

- D1076：P3-970 補強 report quality repair queue snapshot detail deduplication guard：`snapshot_integrity_repair_item()` 在 repair queue action prioritization 前會對 snapshot integrity `errors` 做順序保留去重，避免人工審核佇列重複顯示同一 provider/hash blocker，讓 repair queue、preview boundary、live reading notice 與 stored artifact repair 對重複錯誤的呈現一致；RED→GREEN duplicate repair queue detail 單測與文件契約更新通過。

- D1077：P3-971 補強 report quality repair queue hash-mismatch detail fallback：`snapshot_integrity_repair_item()` 在 invalid snapshot integrity 沒有 `errors` 但 `hash` 與 `expected_hash` 不一致時，會推導 `snapshot_hash mismatch` 作為 manual-review detail，避免人工審核佇列只顯示泛用 hash 失敗文案而失去可追查的 hash 證據；RED→GREEN repair queue hash mismatch detail 單測與文件契約更新通過。

- D1078：P3-972 補強 report quality repair queue same-record generic/hash mismatch priority guard：`snapshot_integrity_repair_item()` 在同一筆 invalid snapshot integrity 同時有預設泛用 `errors` 與不一致的 `hash` / `expected_hash` 時，會優先顯示 `snapshot_hash mismatch`，避免人工審核佇列的 boilerplate blocker text 遮蔽真正可追查的 hash 證據；RED→GREEN same-record generic/hash mismatch repair queue 單測與文件契約更新通過。

- D1079：P3-973 補強 live reading notice hash-mismatch detail fallback：`reporting.reading_notice` 在 live/generated report 使用前提示遇到 invalid `snapshot_integrity` 沒有 `errors`、但 `hash` 與 `expected_hash` 不一致時，會推導 `snapshot_hash mismatch` 作為 HTML/Markdown notice detail，避免完整報告正文只顯示 blocked 狀態而漏掉可追查的 hash 證據；RED→GREEN live reading notice hash mismatch detail 單測與文件契約更新通過。

- D1080：P3-974 補強 live reading notice same-record generic/hash mismatch priority guard：`reporting.reading_notice` 在同一筆 invalid `snapshot_integrity` 同時有預設泛用 `errors` 與不一致的 `hash` / `expected_hash` 時，會優先顯示 `snapshot_hash mismatch`，避免 live/generated report 使用前提示的 boilerplate blocker text 遮蔽真正可追查的 hash 證據；RED→GREEN same-record generic/hash mismatch live reading notice 單測與文件契約更新通過。

- D1081：P3-975 補強 preview reading boundary hash-mismatch detail fallback：`report_reading_boundary_policy.js` 在 invalid `snapshot_integrity` 沒有 `errors`、但 `hash` 與 `expected_hash` 不一致時，會推導 `snapshot_hash mismatch` 作為 preview notice detail，避免預覽層只顯示 blocked 狀態而漏掉可追查的 hash 證據；RED→GREEN preview hash mismatch detail 單測與文件契約更新通過。

- D1082：P3-976 補強 preview reading boundary same-record generic/hash mismatch priority guard：`report_reading_boundary_policy.js` 在同一筆 invalid `snapshot_integrity` 同時有預設泛用 `errors` 與不一致的 `hash` / `expected_hash` 時，會優先顯示 `snapshot_hash mismatch`，避免 preview notice 的 boilerplate blocker text 遮蔽真正可追查的 hash 證據；RED→GREEN same-record generic/hash mismatch preview 單測與文件契約更新通過。

- D1083：P3-977 補強 live reading notice nested invalid snapshot priority guard：`reporting.reading_notice` 在 top-level `snapshot_integrity` 顯示 verified、但 nested `data.snapshot_integrity` 為 invalid 或 `valid=false` 時，會以 nested invalid blocker 決定 HTML/Markdown 使用限制，避免 live/generated report 正文把衝突 snapshot metadata 誤顯示為可引用；RED→GREEN nested invalid live reading notice 單測與文件契約更新通過。

- D1084：P3-978 補強 live reading notice invalid detail specificity guard：`reporting.reading_notice` 在 top-level 與 nested `data.snapshot_integrity` 同時 invalid 時，會優先保留 provider/hash 具體 detail，而不是讓 top-level 泛用 blocker 遮蔽 nested 可診斷證據；RED→GREEN specific nested invalid live reading notice 單測與文件契約更新通過。

- D1085：P3-979 補強 live reading notice snapshot integrity mapping-safe guard：`reporting.reading_notice` 會先以 `safe_mapping_dict()` 正規化 top-level 與 nested `snapshot_integrity` payload，讓 immutable / read-only Mapping wrapper 仍能觸發 blocked HTML/Markdown 使用限制並保留 `snapshot_hash mismatch` 證據；RED→GREEN mapping snapshot integrity live reading notice 單測與文件契約更新通過。

- D1086：P3-980 補強 live reading notice quality gate mapping-safe recorded guard：`reporting.reading_notice` 的 quality gate recorded 判定改以 `safe_mapping_dict()` 為準，讓 immutable evidence/content/conformance gate wrapper 在 HTML/Markdown 使用限制中仍被視為已記錄，避免 fully passed gates 被誤降為 pending；RED→GREEN mapping quality gate live reading notice 單測與文件契約更新通過。

- D1087：P3-981 補強 report quality repair queue quality gate child map guard：`report_quality_repair_queue` 的 quality gate / data trust / freshness child map 正規化改以 `safe_mapping_dict()` 為準，讓 immutable content credibility、conformance、evidence、data trust 或 freshness wrapper 仍能進入 repair action prioritization，避免 blocked manual-review 行動被漏掉；RED→GREEN mapping content credibility repair queue 單測與文件契約更新通過。

- D1088：P3-982 補強 report quality repair queue reports envelope mapping-safe guard：`report_quality_repair_queue` 會先以 `safe_mapping_dict()` 讀取 top-level `reports` envelope，讓 immutable report-list wrapper 仍能進入 sampled/action-required 統計與 repair action prioritization，避免整批 stale、blocked 或 invalid 報告被當成空清單；RED→GREEN mapping reports envelope repair queue 單測與文件契約更新通過。

- D1089：P3-983 補強 provider impact report/trust/alert mapping-safe guard：`provider_impact` 會先以 `safe_mapping_dict()` 正規化 report、`data_trust` 與 provider alert payload，讓 immutable report confidence wrapper 仍能保留 `provider_sla_critical` 與核心來源 unavailable 證據，避免 wait-provider-recovery / blocks-auto-rerun 判斷被誤清空；RED→GREEN mapping provider impact 單測與文件契約更新通過。

- D1090：P3-984 補強 provider impact ledger reports envelope mapping-safe guard：`provider_impact.build_provider_impact_ledger()` 會先以 `safe_mapping_dict()` 讀取 top-level `reports` envelope，讓 immutable report-list wrapper 仍能進入 sampled/reports-with-impacts/blocked 統計與 wait-provider-recovery impact ledger，避免每日 queue 或 provider recovery ledger 把整批核心來源阻斷證據當成空清單；RED→GREEN mapping provider impact ledger envelope 單測與文件契約更新通過。

- D1091：P3-985 補強 daily decision queue provider impact ledger mapping-safe guard：`build_daily_decision_queue()` 會先以 `safe_mapping_dict()` 正規化 `provider_impact_ledger`，讓 immutable provider-impact ledger 仍能輸出 wait-provider-recovery daily queue action，避免 provider recovery 阻斷證據已算出卻在每日操作佇列入口被當成空 payload；RED→GREEN mapping provider impact ledger daily queue 單測與文件契約更新通過。

- D1092：P3-986 補強 daily decision queue provider impact summary mapping-safe guard：`_provider_items()` 會先以 `safe_mapping_dict()` 正規化 provider impact item 的 `summary`，讓 immutable summary wrapper 仍能保留 `blocks_auto_rerun` 與 `recommended_action`，避免 wait-provider-recovery 已進 ledger 卻在每日操作佇列子欄位判斷被丟掉；RED→GREEN mapping provider impact summary daily queue 單測與文件契約更新通過。

- D1093：P3-987 補強 daily decision dashboard decision freshness mapping-safe guard：`daily_decision_dashboard` 會以共用 `_decision_freshness()` 對 `decision_freshness` 做 `safe_mapping_dict()` 正規化，讓 immutable freshness wrapper 仍能進入 `rerun_reports` 與 `reports_needing_rerun` 摘要，避免報告需要完整重跑的證據在 dashboard aggregation 層被漏掉；RED→GREEN mapping decision freshness dashboard rerun bucket 單測與文件契約更新通過。

- D1094：P3-988 補強 daily decision dashboard report-row collection truthiness guard：`daily_decision_dashboard` 會以 `safe_dict_list()` 讀取 `reports.reports`，讓 falsey 但含有效報告的 list wrapper 仍能進入 sampled reports、rerun bucket、repair queue 與 provider impact aggregation，避免 dashboard 入口把整批報告品質證據當成空清單；RED→GREEN falsey report rows dashboard 單測與文件契約更新通過。

- D1095：P3-989 補強 daily decision dashboard reports envelope mapping-safe guard：`daily_decision_dashboard` 會先以 `safe_mapping_dict()` 正規化 top-level `reports` envelope，再用 `safe_dict_list()` 讀取 report rows，讓 malformed `.get()` accessor 不能把 sampled reports、rerun evidence、repair actions 或 provider impacts 靜默藏成空清單；RED→GREEN misleading reports envelope dashboard 單測與文件契約更新通過。

- D1096：P3-990 補強 daily decision dashboard performance envelope mapping-safe guard：`daily_decision_dashboard` 會先以 `safe_mapping_dict()` 正規化 top-level `performance` envelope，再把 details 與 summary 分別交給 outcome calibration、daily decision queue 與 dashboard output，讓 malformed `.get()` accessor 不能隱藏回測 evidence、summary metrics 或 due-backtest action；RED→GREEN misleading performance envelope dashboard 單測與文件契約更新通過。

- D1097：P3-991 補強 daily decision dashboard watchlist envelope mapping-safe guard：`daily_decision_dashboard` 會先以 `safe_mapping_dict()` 正規化 top-level `watchlist` envelope，再用 `safe_dict_list()` 讀取 high-priority watchlist rows，讓 malformed `.get()` accessor 不能隱藏 watchlist rerun action、high-priority count 或每日操作佇列來源統計；RED→GREEN misleading watchlist envelope dashboard 單測與文件契約更新通過。

- D1098：P3-992 補強 daily decision dashboard screener envelope mapping-safe guard：`daily_decision_dashboard` 會先以 `safe_mapping_dict()` 正規化 top-level `screener` envelope，再用 `safe_dict_list()` 讀取 candidate rows，讓 malformed `.get()` accessor 不能隱藏 review-candidate action、top-candidate count 或每日操作佇列來源統計；RED→GREEN misleading screener envelope dashboard 單測與文件契約更新通過。

- D1099：P3-993 補強 daily decision dashboard free-mode envelope mapping-safe guard：`daily_decision_dashboard` 會先以 `safe_mapping_dict()` 正規化 top-level `free_mode` envelope，再把同一份 payload 用於 dashboard 顯示與 daily decision queue，讓 malformed `.get()` accessor 不能隱藏 paid-dependency violations、can-run-without-paid-keys 狀態或 fix-free-mode action；RED→GREEN misleading free-mode envelope dashboard 單測與文件契約更新通過。

- D1100：P3-994 補強 daily decision dashboard screener quality-funnel mapping-safe guard：`_top_candidates()` 會以 `safe_mapping_dict()` 正規化 nested `quality_funnel`，讓 immutable / read-only reject outcome 仍能在 candidate filtering 階段被排除，避免已拒絕候選進入 review-candidate action 或 top-candidate count；RED→GREEN mapping quality-funnel dashboard 單測與文件契約更新通過。

- D1101：P3-995 補強 daily decision dashboard screener score conversion guard：`_top_candidates()` 排序前會以 conversion-safe `_score_value()` 讀取候選 score，讓不可轉換、布林或非有限分數降為 0 分而不中斷 dashboard aggregation，也避免 malformed score 壓過有效候選；RED→GREEN broken-score dashboard 單測與文件契約更新通過。

- D1102：P3-996 補強 daily decision dashboard rerun filename alias string-safe guard：`daily_decision_dashboard` 在 rerun report dedupe key 與 `rerun_reports` payload 輸出前，會以 shared `safe_text()` 安全選取 `filename` / `report_filename`，讓 malformed filename truthiness 或字串轉換不再中斷 rerun-bucket aggregation，也避免非字串 artifact identity 外溢；RED→GREEN broken-filename dashboard 單測與文件契約更新通過。

- D1103：P3-997 補強 daily decision dashboard watchlist priority string-safe guard：`daily_decision_dashboard` 的 high-priority watchlist filter 改以 shared `safe_text()` 正規化 `decision_priority`，讓 malformed priority truthiness 或字串轉換不再中斷 dashboard aggregation，且其他有效 high priority watchlist rows 仍會進每日操作佇列；RED→GREEN broken-priority watchlist 單測與文件契約更新通過。

- D1104：P3-998 補強 daily decision dashboard rerun reason string-safe fallback：`daily_decision_dashboard` 在輸出 `rerun_reports.detail` 前，會以 shared `safe_text()` 逐一讀取 freshness reason、analysis stale message 與 report-level rerun reason，讓 malformed reason truthiness 或字串轉換不再中斷 rerun-bucket aggregation，且仍保留下一個有效 stale-snapshot evidence；RED→GREEN broken-reason rerun dashboard 單測與文件契約更新通過。

- D1105：P3-999 補強 daily decision dashboard rerun flag bool-safe fallback：`daily_decision_dashboard` 的 rerun-bucket 判斷改以本地 `_safe_bool()` 逐一讀取 freshness/report-level rerun flags 與 `analysis_text_stale`，讓 malformed flag truthiness 不再中斷 dashboard aggregation，且仍可由下一個有效 stale-report evidence 進入 rerun queue；RED→GREEN broken-rerun-flag dashboard 單測與文件契約更新通過。

- D1106：P3-1000 補強 daily decision dashboard screener quality outcome string-safe guard：`_top_candidates()` 會先以 shared `safe_text()` 正規化 `quality_funnel.outcome`，再做 reject filtering 與 `top_candidates.quality_outcome` 輸出，讓 malformed outcome truthiness 不再中斷 dashboard aggregation，也避免非字串 quality label 外溢；RED→GREEN broken-quality-outcome screener 單測與文件契約更新通過。

- D1107：P3-1001 補強 daily decision dashboard screener candidate text string-safe guard：`_top_candidates()` 會以 shared `safe_text()` 正規化候選 `ticker`、`company_name`、`reason` 與 `category`，並以 `_candidate_reason()` 做 reason/category fallback，讓 malformed candidate text truthiness 不再中斷 dashboard aggregation，也避免非字串候選標籤外溢；RED→GREEN broken-candidate-text screener 單測與文件契約更新通過。

- D1108：P3-1002 補強 daily decision dashboard screener score payload conversion guard：`_top_candidates()` 現在以同一個 `_score_value()` 正規化候選 `score` 的排序與 payload 輸出，讓可轉換分數輸出為乾淨數值，也讓 malformed score objects 不再外溢到 dashboard 或 action payload；RED→GREEN coercible-score payload 單測與文件契約更新通過。

- D1109：P3-1003 補強 daily decision dashboard free-mode violations string-list guard：`daily_decision_dashboard` 會先以 shared `safe_text_list()` 正規化 `free_mode.violations`，再把同一份乾淨 violation list 用於 dashboard 與 daily queue，讓 malformed violation truthiness 不再中斷 aggregation，也避免非字串 paid-dependency labels 外溢；RED→GREEN broken-free-mode-violations 單測與文件契約更新通過。

- D1110：P3-1004 補強 daily decision dashboard free-mode boolean flag bool-safe guard：`daily_decision_dashboard` 會先以本地 `_safe_bool()` 正規化 `free_mode.enabled` 與 `free_mode.can_run_without_paid_keys`，再把同一份 bool-safe payload 用於 dashboard 與 daily queue，讓 malformed enabled/can-run flag truthiness 不再中斷 aggregation，也避免 paid-dependency repair action 被隱藏；RED→GREEN broken-free-mode-flag 單測與文件契約更新通過。

- D1111：P3-1005 補強 daily decision queue free-mode violations string-list guard：`daily_decision_queue._free_mode_items()` 會以 shared `safe_text_list()` 正規化 `free_mode.violations`，讓直接呼叫 queue 的入口也不會漏掉 tuple violation evidence 或外溢非字串 paid-dependency labels；RED→GREEN queue free-mode violations 單測與文件契約更新通過。

- D1112：P3-1006 補強 daily decision queue free-mode can-run bool-safe guard：`daily_decision_queue._free_mode_items()` 會以 `_bool()` 讀取 `free_mode.can_run_without_paid_keys`，讓直接呼叫 queue 的入口遇到 malformed flag truthiness 時不再中斷 queue assembly，也不會隱藏 paid-dependency repair action；RED→GREEN queue free-mode can-run flag 單測與文件契約更新通過。

- D1113：P3-1007 補強 daily decision queue computed backtest report date conversion guard：`daily_decision_queue._report_date()` 會以 shared `safe_text()` 讀取 report `date`，並以 truthiness-free float fallback 讀取 `timestamp`，讓 malformed date/timestamp truthiness 不再中斷 computed backtest due detection，也不會隱藏後續有效 due reports；RED→GREEN computed-backtest date 單測與文件契約更新通過。

- D1114：P3-1008 補強 daily decision queue integer bool guard：`daily_decision_queue._int()` 會把 boolean payload 視為 malformed numeric input，讓 explicit backtest horizon、priority、display limit 與 summary integer fallback 不會把 `True`/`False` 轉成 synthetic 1/0；RED→GREEN boolean horizon 單測與文件契約更新通過。

- D1115：P3-1009 補強 daily decision queue integer fractional-float guard：`daily_decision_queue._int()` 會把非整數 float 視為 malformed numeric input，讓 explicit backtest horizon、priority、display limit 與 summary integer fallback 不會把 `1.7` 這類小數截斷成 synthetic 1；RED→GREEN fractional-float horizon 單測與文件契約更新通過。

- D1116：P3-1010 補強 daily decision queue integer fractional exact numeric guard：`daily_decision_queue._int()` 會委派 shared `safe_int()`，讓 `Decimal("1.7")` 或 `Fraction(3, 2)` 這類 exact numeric 小數也被視為 malformed numeric input，避免 explicit backtest horizon、priority、display limit 與 summary integer fallback 被截斷成 synthetic 1；RED→GREEN exact numeric horizon 單測與文件契約更新通過。

- D1117：P3-1011 收窄 daily decision route warning frontstage noise boundary：`daily_decision_route_warnings.NON_ACTIONABLE_WARNING_IDS` 只排除 `slow_route`，讓 p95 latency noise 不再前台打擾，但 `retry_storm`、`quality_gate_failures` 與 future actionable route warnings 仍進入 daily decision queue，避免重試失敗證據被當成單純慢路由噪音隱藏；RED→GREEN route warning policy 單測與文件契約更新通過。

- D1118：P3-1012 補強 runtime observability payload-safe mapping guard：Prometheus、ops dashboard queue payload、provider SLA payload 與 notification delivery observability 改用 payload-safe mapping conversion，而不是 audit persistence 的 JSON pruning helper，讓 empty job lists、named queue keys、provider SLA `success_rate` / `avg_duration_ms`、notification channel/reason label maps 與 NaN/Infinity 類數字欄位保留輸出欄位並正規化為安全值；既有 13 個 runtime observability RED 測試全部轉 GREEN，整檔 runtime observability 回歸通過。

- D1119：P3-1013 補強 Prometheus named queue malformed-detail zero series guard：`build_prometheus_metrics()` 在 render `stock_agent_queue_depth{queue=...}` 時改用 payload-safe queue map traversal，讓 named queue detail 完全 malformed 時仍保留 queue label 並輸出 zero-depth series，避免 RQ named queue 在 metrics 中靜默消失；RED→GREEN named queue 單測與文件契約更新通過。

- D1120：P3-1014 補強 ops dashboard queue shared-text metadata guard：`queue_dashboard_payload.normalize_ops_queue_payload()` 的 backend、queue name、named queue key、registry、error 與 supplemental text metadata 改用 shared `mapping_fields.safe_text()`，讓 boolean、binary 或 memory-view payload 不會外溢成 `"True"`、bytes decode 或 buffer repr 等 operator-facing 字串；RED→GREEN queue text metadata 單測與文件契約更新通過。

- D1121：P3-1015 補強 Prometheus shared-text label fallback guard：`api_observability_service._labels()` 與 `notification_delivery_observability._metric_label()` 改用 shared `mapping_fields.safe_text()`，並讓不可安全表示的 provider、queue、delivery channel/reason label value 穩定 fallback 為 `unknown`，避免 boolean、binary 或 memory-view payload 外溢成 `"True"`、decoded bytes 或 buffer text，也避免空 label value 形成難追查的 metrics series；RED→GREEN Prometheus label hygiene 單測與文件契約更新通過。

- D1122：P3-1016 補強 provider SLA alert projection shared-text field guard：`provider_sla_observability` 的 alert projection 與 dashboard alert payload text fields 改用 shared `mapping_fields.safe_text()`，讓 boolean、binary 或 memory-view 的 source、provider、message、status、basis 與 selected-window 值不會被字串化或解碼成 operator-facing provider alert payload；RED→GREEN provider SLA alert projection 單測與文件契約更新通過。

- D1123：P3-1017 補強 provider SLA nested window-key shared-text guard：`provider_sla_payload_shape.normalize_provider_sla_windows()` 的 canonical window-key matching 改用 shared `mapping_fields.safe_text()`，讓 `b"last_24h"` 或 `memoryview(b"last_7d")` 這類 malformed binary/buffer key 不會被解碼後混入 `last_1h` / `last_24h` / `last_7d` provider SLA payload；RED→GREEN nested window-key 單測與文件契約更新通過。

- D1124：P3-1018 補強 notification delivery failure reason shared-text guard：`notification_delivery_reason.failure_reason_bucket()` 的 low-cardinality reason bucketing 改用 shared `mapping_fields.safe_text()`，讓 `b"temporary webhook timeout"` 或 `memoryview(b"HTTP 403 invalid token")` 這類 malformed binary/buffer error 不會被解碼後誤分類成 `timeout` 或 `auth`，而是保守落到 `unknown`；RED→GREEN binary error reason 單測與文件契約更新通過。

- D1125：P3-1019 補強 notification delivery dashboard count-map shared-text guard：`notification_delivery_observability.notification_delivery_dashboard_summary()` 會先把 `channel_counts` 與 `failure_reason_counts` 的 map key 轉成 shared-text label、值轉成 integer-safe count，讓 boolean、binary 或 memory-view channel/reason key 不會外溢成 ops dashboard API 的非 JSON-safe map entry，並把 malformed key 保守聚合到 `unknown`；RED→GREEN dashboard count-map JSON-safe 單測與文件契約更新通過。

- D1126：P3-1020 補強 ops dashboard free-mode shared-text guard：`api_observability_service._free_mode_dashboard_summary()` 改用 payload-safe mapping conversion 與 shared `safe_text_list()`，讓 boolean、binary 或 memory-view 的 provider `cost_tier` / violation value 不會被 persistence JSON pruning 解碼成可信 `providers_by_cost_tier` 或可見 violation 文案；RED→GREEN free-mode binary tier/violation 單測與文件契約更新通過。

- D1127：P3-1021 補強 ops dashboard stuck-job strict-count guard：`api_observability_service.build_ops_dashboard_payload()` 與 `_dashboard_status()` 共用 strict stuck-job count conversion，讓 `b"3"`、memory-view 或 boolean `stuck_jobs.count` 不會被解碼成 synthetic stuck-job warning，也不會以非 JSON-safe count 外溢到 ops dashboard payload；RED→GREEN stuck-job binary count 單測與文件契約更新通過。

- D1128：P3-1022 補強 Prometheus provider numeric strict-conversion guard：`api_observability_service._metric_number()` 與 `_metric_int()` 會把 boolean、bytes、bytearray、memory-view provider numeric payload 保守轉為 0，讓 provider SLA success-rate、attempts 與 error-count metrics 不會把 binary/buffer 內容解碼成可信 Prometheus 數值；RED→GREEN provider numeric metrics 單測與文件契約更新通過。

- D1129：P3-1023 補強 queue dashboard / Prometheus queue integer strict-count guard：`queue_dashboard_payload.normalize_ops_queue_payload()` 會以 strict count conversion 正規化 default queue depth、named queue depth、registry counts、active task count 與 timeout 秒數，讓 boolean、bytes、bytearray、memory-view queue payload 不會被解碼成 synthetic backlog、registry 或 timeout metrics；RED→GREEN queue integer payload 與 Prometheus queue depth 單測、文件契約更新通過。

- D1130：P3-1024 補強 ops dashboard queue age strict finite-float guard：`queue_dashboard_payload._safe_finite_float()` 會把 boolean、bytes、bytearray、memory-view `oldest_queued_seconds` 保守轉為 0.0，讓 malformed queue age payload 不會被解碼成 synthetic wait-time 訊號；RED→GREEN queue age binary/bool 單測與文件契約更新通過。

- D1131：P3-1025 補強 provider SLA API payload strict numeric guard：`provider_sla_payload_shape.provider_sla_numeric_value()` 會把 boolean、bytes、bytearray、memory-view provider SLA numeric payload 保守轉為 0 / 0.0，讓 all-window 與 selected-window provider attempts、counts、success-rate、duration、total-record stats 不會被解碼成可信 SLA evidence；RED→GREEN provider SLA all-window / selected-window binary numeric 單測與文件契約更新通過。

- D1132：P3-1026 補強 notification delivery observability strict-count guard：`notification_delivery_observability._metric_int()` 會把 boolean、bytes、bytearray、memory-view audit count payload 保守轉為 0，讓 ops dashboard 與 Prometheus notification delivery counts 不會把 binary/buffer 內容解碼成 failed、retry-exhausted、channel 或 failure-reason 故障 evidence；RED→GREEN dashboard summary / Prometheus notification delivery binary count 單測與文件契約更新通過。

- D1133：P3-1027 補強 API quota observability strict field guard：`api_quota_service.build_api_quota_payload()` 會用 shared-text 與 strict-count/finite-float conversion 正規化 quota limit、usage count、observed model calls 與 FMP provider observation fields，讓 boolean、bytes、bytearray、memory-view payload 不會被解碼成可信 quota limit、provider status 或 success-rate evidence；RED→GREEN API quota binary/bool observation 單測與文件契約更新通過。

- D1134：P3-1028 補強 daily decision queue notification delivery strict-count guard：`daily_decision_queue_notifications.notification_delivery_items()` 會以 strict-count conversion 正規化 failed/retry-exhausted top-level counts 與 channel/failure-reason count maps，並先收斂 channel/reason keys，讓 boolean、bytes、bytearray、memory-view payload 不會被解碼成前台 decision queue 的 synthetic delivery failure evidence；RED→GREEN daily queue notification binary/bool count 單測與文件契約更新通過。

- D1135：P3-1029 補強 notification plan queue-context strict-count guard：`free_notification_plan._int()` 會把 boolean、bytes、bytearray、memory-view queue summary counts 與 priority score 視為 malformed numeric input，讓 `notification_plan.queue_context` 不會把 binary/buffer 或 bool payload 解碼成 synthetic total/displayed/secondary/top-priority workload evidence；RED→GREEN notification plan queue-context binary/bool count 單測與文件契約更新通過。

- D1136：P3-1030 補強 notification plan message-envelope shared-text guard：`free_notification_plan._text()` 改用 shared `mapping_fields.safe_text()`，讓 message `type` / `title` / `detail` 在保留可字串化正常物件的同時，拒絕 boolean、bytes、bytearray、memory-view payload 變成外部 sender message 或 delivery outbox 的可見文字；RED→GREEN notification plan message envelope binary/bool 單測與文件契約更新通過。

- D1137：P3-1031 補強 notification plan suppression flag explicit bool-text guard：`free_notification_plan._suppress_notification()` 改用 explicit bool/text token conversion，讓 `"false"`、binary 或 memory-view `suppress_notification` 不會因 Python truthiness 壓掉真實通知，同時保留 bool/string true 與 `monitor` / `fix_notification_delivery` type-based suppression；RED→GREEN suppression flag 單測與文件契約更新通過。

- D1138：P3-1032 補強 notification plan external channel env shared-text gate：`free_notification_plan._channel_payload()` 會用 shared `safe_text()` 判斷 SMTP、Telegram、Discord、Slack 所需 env 是否為可用文字，讓 boolean、bytes、bytearray、memory-view env payload 留在 `channels[].missing_env`，不會誤啟用外部 channel 或產生外部 delivery outbox；RED→GREEN external channel env 單測與文件契約更新通過。

- D1139：P3-1033 補強 notification plan sender numeric metadata / identity shared-text guard：`free_notification_plan._message_context()` 會用 strict `_int()` 正規化 sender-visible `priority_score` 與 `horizon_months`，`free_notification_identity.identity_part()` 改用 shared `safe_text()` 組成 `dedupe_key` / `message_id` / `delivery_key`，讓 boolean、bytes、bytearray、memory-view metadata 不會外溢到外部 sender payload 或 idempotency identity；RED→GREEN numeric metadata / identity 單測與文件契約更新通過。

- D1140：P3-1034 補強 notification plan sender text metadata shared-text guard：`free_notification_plan._message_context()` 會用 shared `safe_text()` 正規化 sender-visible ticker、filename、report filename、pipeline、route、warning、recommended action、severity 與 action label context，讓 boolean、bytes、bytearray、memory-view metadata 不會外溢到 `notification_plan.messages` 或 `delivery_outbox`，同時保留 `blocks_auto_rerun` 等真正的 boolean contract；RED→GREEN text metadata 單測與文件契約更新通過。

- D1141：P3-1035 補強 notification plan sender boolean metadata explicit bool-text guard：`free_notification_plan._message_context()` 會用 explicit bool/text conversion 正規化 sender-visible `blocks_auto_rerun`，讓 `"false"` 不會因 truthiness 被當成阻擋，也讓 bytes、bytearray、memory-view boolean payload 不會外溢到 `notification_plan.messages` 或 `delivery_outbox`；RED→GREEN boolean metadata 單測與文件契約更新通過。

- D1142：P3-1036 補強 notification plan orphan source display metadata guard：`free_notification_plan._message_context()` 在 action 沒有有效 raw `source` 時會同步移除 `source_label` / `source_text`，讓 malformed display-only metadata 不能繞過 source key normalization 外溢到 `notification_plan.messages` 或 `delivery_outbox`；RED→GREEN orphan source display 單測與文件契約更新通過。

- D1143：P3-1037 補強 notification plan action collection iterator-safe guard：`free_notification_plan._notification_actions()` 會用 shared `safe_dict_list()` 正規化 `decision_queue.items` 與 legacy `actions`，讓 malformed list iterator 不會中斷 `notification_plan.messages` / `delivery_outbox` 組裝，也不會抹掉 native list 中仍有效的 action；RED→GREEN action collection iterator 單測與文件契約更新通過。

- D1144：P3-1038 補強 notification plan action collection tuple guard：`free_notification_plan._notification_actions()` 會把 tuple 形式的 `decision_queue.items` 與 legacy `actions` 交給 shared `safe_dict_list()` 正規化，讓 immutable repaired action batches 不會被當成空資料而跳過 `notification_plan.messages` / `delivery_outbox` 組裝；RED→GREEN tuple action collection 單測與文件契約更新通過。

- D1145：P3-1039 補強 notification plan decision queue mapping payload guard：`free_notification_plan._notification_actions()` / `_decision_queue_context()` 會用 shared `safe_mapping_dict()` 正規化 `decision_queue`、`summary` 與 `sources`，讓 immutable repaired queue payload 不會被降級成 empty legacy actions，也能保留有效 source distribution 與 message/outbox action；RED→GREEN mapping decision queue 單測與文件契約更新通過。

- D1146：P3-1040 補強 notification plan top-level dashboard mapping payload guard：`free_notification_plan._notification_actions()` 會先用 shared `safe_mapping_dict()` 正規化 top-level dashboard，再讀取 `decision_queue` 或 legacy `actions`，讓 immutable repaired dashboard response 不會在 dict-native field read 時中斷 notification planning；RED→GREEN mapping dashboard 單測與文件契約更新通過。

- D1147：P3-1041 補強 notification plan external env container mapping guard：`build_daily_notification_plan()` 會在外部 channel missing-env 檢查前用 shared `safe_mapping_dict()` 正規化 env 容器，讓 malformed env payload 不會中斷 notification planning；本機通知仍啟用，SMTP / Telegram / Discord / Slack 會保守留在 `channels[].missing_env` 並避免產生外部 `delivery_outbox`；RED→GREEN malformed env container 單測與文件契約更新通過。

- D1148：P3-1042 補強 notification plan message-envelope blank text guard：`free_notification_plan._messages()` 會在 fallback 前 trim `type` / `title` / `detail`，讓 whitespace-only envelope metadata 不會外溢成可見 sender message 或 `delivery_outbox` context；RED→GREEN blank envelope 單測與文件契約更新通過。

- D1149：P3-1043 補強 notification plan custom CTA/target blank metadata guard：`free_notification_plan._first_text()` 會在 selector fallback 前 trim action-provided text，讓 whitespace-only `operator_action` / `operator_action_label` / `target_panel` / `target_tab` 不會外溢成可見 sender message 或 `delivery_outbox` context，並回到既有 CTA / deep-link 預設值；RED→GREEN blank CTA/target 單測與文件契約更新通過。

- D1150：P3-1044 補強 notification plan action type normalization guard：`free_notification_plan._action_type()` 會集中 trim raw action `type`，並供 suppression、legacy queue context、CTA default、target default 與 message envelope 共用，讓 whitespace-padded `monitor` 不再變成通知噪音，也讓 padded provider recovery action 保留「查看來源」CTA 與 provider SLA deep link；RED→GREEN padded type 單測與文件契約更新通過。

- D1151：P3-1045 補強 notification plan fractional numeric guard：`free_notification_plan._int()` 會保留 bool/binary 防護並委派 shared `safe_int()`，讓 fractional float、Decimal 與 Fraction payload 不會被 Python `int()` 截斷成 queue_context、message 或 `delivery_outbox` 的 synthetic priority、horizon 或 workload count；RED→GREEN fractional numeric 單測與文件契約更新通過。

- D1152：P3-1046 補強 notification plan non-negative numeric guard：`free_notification_plan._int()` 會將 shared integer conversion 後的負數收斂為 0，讓 negative queue_context count、message priority / horizon 或 `delivery_outbox` metadata 不會外溢成不可能的負工作量或負優先級；RED→GREEN negative numeric 單測與文件契約更新通過。

- D1153：P3-1047 補強 notification plan arbitrary numeric object guard：`free_notification_plan._int()` 只接受明確 primitive / exact numeric 型別後才委派 shared `safe_int()`，讓提供 `__int__` 的未知 adapter object 不會合成 queue_context、message priority / horizon 或 `delivery_outbox` metadata 的可信工作量與優先級；RED→GREEN arbitrary numeric object 單測與文件契約更新通過。

- D1154：P3-1048 補強 notification plan arbitrary bool-token object guard：`free_notification_plan._explicit_bool()` 只接受真正 bool 與 string token，讓提供 `__str__ = "true"` 的未知 wrapper object 不能把 `blocks_auto_rerun` 合成 sender-visible blocking flag，也不能透過 `suppress_notification` 壓掉真實通知；RED→GREEN arbitrary bool-token 單測與文件契約更新通過。

- D1155：P3-1049 補強 notification plan context presence equality-result guard：`free_notification_plan._present()` 改為 identity/type-based empty check，只有 `None` 與真正空字串會被視為 absent，讓任意 metadata object 不能透過 `__eq__("")` 把可字串化的 `recommended_action` 等 sender context 從 message / `delivery_outbox` 中抹掉；RED→GREEN blank-comparable metadata 單測與文件契約更新通過。

- D1156：P3-1050 補強 notification identity blank-comparable override guard：`free_notification_identity.identity_part()` 只用 `None` 與真正空字串判斷缺值，並保留 equality exception fallback，讓任意 identity object 不能透過 `__eq__("")` 抹掉可字串化的 `dedupe_key` / `message_id` override，外部 sender idempotency 仍可使用明確自訂識別；RED→GREEN blank-comparable identity override 單測與文件契約更新通過。

- D1157：P3-1051 補強 notification external channel env arbitrary object gate：`free_notification_plan._env_value_present()` 只接受 concrete nonblank string env value，讓提供 `__str__ = "token"` 的未知 wrapper object 不能誤啟用 SMTP / Telegram / Discord / Slack 外部 channel 或產生外部 `delivery_outbox`；RED→GREEN arbitrary string-like env 單測與文件契約更新通過。

- D1158：P3-1052 補強 backend source count arbitrary numeric object guard：`daily_decision_source_labels._source_count()` 只接受明確 primitive / exact numeric 與字串 count 後才進行整數性判斷，讓提供 `__int__` 且 `__eq__` 自稱等於整數的未知 wrapper object 不能合成 `decision_queue.summary.sources` / `notification_plan.queue_context.sources` 的 active source row；RED→GREEN arbitrary source-count object 單測與文件契約更新通過。

- D1159：P3-1053 補強 backend source display arithmetic mapping accessor guard：`daily_decision_source_labels._source_keys()` / `_source_items()` 共用包含 `ArithmeticError` 的 helper 例外集合，讓 overflow-style `keys()` / `items()` 失敗不會中斷 `source_labels`、`source_texts`、source count normalization 或 display override 合併；RED→GREEN arithmetic mapping accessor 單測與文件契約更新通過。

- D1160：P3-1054 補強 backend source display mapping attribute lookup guard：`daily_decision_source_labels._source_method()` 會先安全取得 `keys` / `items` callable，讓畸形 mapping-like payload 在屬性讀取階段拋 `RuntimeError` 等 helper 例外時被視為空來源分布，不會中斷 `source_labels`、`source_texts`、source count normalization 或 display override 合併；RED→GREEN mapping attribute lookup 單測與文件契約更新通過。

- D1161：P3-1055 補強 backend source key trim failure guard：`daily_decision_source_labels.source_key()` 會吸收 raw source key `.strip()` 的 helper 例外並當作空 key，讓畸形 string subclass 不能中斷 `source_labels`、`source_texts`、source count normalization 或 display override 合併，且不會壓掉後續合法來源列；RED→GREEN source-key trim failure 單測與文件契約更新通過。

- D1162：P3-1056 補強 backend source key trim result type guard：`daily_decision_source_labels.source_key()` 只接受 `.strip()` 後仍為字串的結果，讓畸形 string subclass 不能透過 non-string trim result 把 dict/list 等非字串 key 注入 `source_labels`、`source_texts`、source count normalization 或 display override；RED→GREEN source-key trim result type 單測與文件契約更新通過。

- D1163：P3-1057 補強 backend source display override value trim guard：`daily_decision_source_labels.source_display_overrides()` 改用 shared `_trimmed_source_text()` 正規化 override value，讓畸形 string subclass 的 `.strip()` 例外或 non-string trim result 不會中斷 display override 合併，也不能把非字串 display value 注入 sender/API payload；RED→GREEN override value trim 單測與文件契約更新通過。

- D1164：P3-1058 補強 backend source text plain-string trim result guard：`daily_decision_source_labels._trimmed_source_text()` 只接受 exact/plain `str` trim result，讓覆寫 `__hash__` / `__eq__` 的 string subclass 不能進入 `source_labels`、`source_texts`、source count normalization 或 display override，避免來源顯示 map lookup / aggregation 被畸形文字物件中斷；RED→GREEN plain-string trim result 單測與文件契約更新通過。

- D1165：P3-1059 補強 backend source count plain-string raw count guard：`daily_decision_source_labels._source_count()` 只接受 exact/plain `str` 作為 raw string count，讓覆寫 `__int__` 的 string subclass 不能把看似 `"0"` 的 count 合成 active source row，避免 `decision_queue.summary.sources` / `notification_plan.queue_context.sources` 被畸形文字計數污染；RED→GREEN string-subclass source count 單測與文件契約更新通過。

- D1166：P3-1060 補強 backend source display lookup failure guard：`daily_decision_source_labels.SOURCE_HELPER_ERRORS` 納入 `LookupError`，讓 mapping accessor、iterator 或 item unpacking 中的 `KeyError` / `IndexError` 被視為 empty/skipped source entry，不會中斷 `source_labels`、`source_texts`、source count normalization 或 display override 合併；RED→GREEN lookup failure 單測與文件契約更新通過。

- D1167：P3-1061 補強 report quality repair queue lookup truthiness flag guard：`report_quality_repair_queue._safe_bool()` 納入 `LookupError` fallback，讓 `decision_freshness.requires_rerun` 等 rerun flag 在 `__bool__` 丟 `KeyError` / `IndexError` 時保守視為 false，不會中斷 repair queue action prioritization，且後續有效 stale-report flags 仍可觸發完整重跑修復項；RED→GREEN lookup truthiness freshness flag 單測與文件契約更新通過。

- D1168：P3-1062 補強 shared safe text lookup conversion guard：`mapping_fields.safe_text()` 納入 `LookupError` fallback，讓 report quality repair queue 的 quality gate `summary` / `message` 等文字欄位在 `__str__` 丟 `KeyError` / `IndexError` 時視為 blank，不會中斷 manual-review action prioritization，且後續有效 fallback text 仍可描述修復原因；RED→GREEN lookup string conversion 單測、mapping_fields helper 單測與文件契約更新通過。

- D1169：P3-1063 補強 report quality repair queue lookup integer limit guard：`mapping_fields.safe_int()` 支援 caller default 並納入 `LookupError` fallback，`build_report_quality_repair_queue()` 對 malformed `limit` 轉換失敗時回到預設 cap，讓 `KeyError` / `IndexError` 型 limit adapter 不會中斷 action prioritization，也不會把有效 repair items 切成空清單；RED→GREEN lookup integer limit 單測、mapping_fields helper 單測與文件契約更新通過。

- D1170：P3-1064 補強 shared text-list lookup iterator fallback：`mapping_fields.safe_text_list()` 與 `provider_impact._safe_text_list()` 納入 `LookupError` iterator fallback，讓 reason_codes / stale_sources 類 list wrapper 在 `__next__` 丟 `KeyError` / `IndexError` 時回退 native list/tuple iterator，不會中斷 report repair queue、provider recovery impact 或抹掉底層有效修復原因；RED→GREEN lookup text-list iterator 單測、repair queue/provider impact focused 與文件契約更新通過。

- D1171：P3-1065 補強 shared dict-list lookup iterator fallback：`mapping_fields.safe_dict_list()` 與 `provider_impact._safe_dict_list()` 納入 `LookupError` iterator fallback，讓 provider_sla_alerts 類 list wrapper 在 `__next__` 丟 `KeyError` / `IndexError` 時回退 native list/tuple iterator，不會中斷 report repair queue provider-impact handoff、provider recovery impact 或抹掉底層有效 provider alert evidence；RED→GREEN lookup dict-list iterator 單測、repair queue/provider impact focused 與文件契約更新通過。

- D1172：P3-1066 補強 shared Mapping `.items()` lookup fallback：`mapping_fields.safe_mapping_items()` 在一般 `Mapping.items()` accessor 丟 `KeyError` / `IndexError` 時改用 ABC `Mapping.items(value)` 標準 traversal，讓 content_credibility / data_trust / provider alert 類 mapping wrapper 仍可透過 readable keys 與 item access 保留欄位，不會中斷 report repair queue quality-gate action prioritization 或 provider recovery impact；RED→GREEN mapping items lookup 單測、repair queue/provider impact focused 與文件契約更新通過。

- D1173：P3-1067 補強 shared Mapping item lookup skip fallback：`mapping_fields.safe_mapping_items()` 在 Mapping traversal 期間遇到單一 key 的 `__getitem__` 丟 `KeyError` / `IndexError` 時會跳過該 key 並保留後續有效欄位，讓 content_credibility / data_trust / provider alert 類 mapping wrapper 的局部壞 key 不會中斷 report repair queue quality-gate action prioritization 或 provider recovery impact；RED→GREEN mapping item lookup 單測、repair queue/provider impact focused 與文件契約更新通過。

- D1174：P3-1068 補強 shared sequence lookup iterator fallback：`mapping_fields.safe_sequence_items()` 納入 `LookupError` iterator fallback，讓 source_audit / metadata 類 list wrapper 在 `__next__` 丟 `KeyError` / `IndexError` 時回退 native list/tuple iterator，不會中斷 report refresh stale-source classification 或抹掉底層 fresh source audit evidence；RED→GREEN sequence lookup iterator 單測、report refresh focused 與文件契約更新通過。

- D1175：P3-1069 補強 shared Mapping `.items()` iterable lookup fallback：`mapping_fields.safe_mapping_items()` 在 `.items()` 回傳物件建立 iterator 時遇到 `KeyError` / `IndexError` 會回退 Mapping key traversal，讓 source_audit row / metadata 類 Mapping wrapper 仍可透過 readable keys 與 item access 保留欄位，不會中斷 report refresh stale-source classification 或抹掉 fresh audit evidence；RED→GREEN mapping iterable lookup 單測、report refresh focused 與文件契約更新通過。

- D1176：P3-1070 補強 shared Mapping item unpack lookup skip：`mapping_fields.safe_mapping_items()` 在 `.items()` 迭代期間遇到單一 item pair unpack 丟 `KeyError` / `IndexError` 時會跳過該 pair 並保留後續有效欄位，讓 source_audit row / metadata 類 Mapping wrapper 的局部壞 pair 不會中斷 report refresh stale-source classification 或抹掉同列 fresh audit evidence；RED→GREEN mapping item unpack lookup 單測、report refresh focused 與文件契約更新通過。

- D1177：P3-1071 補強 shared Mapping key hash lookup skip：`mapping_fields.safe_mapping_items()` 在 `.items()` 迭代期間遇到單一 key hash validation 丟 `KeyError` / `IndexError` 時會跳過該 key pair 並保留後續有效欄位，讓 source_audit row / metadata 類 Mapping wrapper 的局部壞 key 不會中斷 report refresh stale-source classification 或抹掉同列 fresh audit evidence；RED→GREEN mapping key hash lookup 單測、report refresh focused 與文件契約更新通過。

- D1178：P3-1072 補強 shared Mapping traversal key hash lookup skip：`mapping_fields._mapping_key_items()` 在 `.items()` fallback 後的 key traversal 期間遇到單一 key hash validation 丟 `KeyError` / `IndexError` 時會跳過該 key 並保留後續有效欄位，讓 source_audit row / metadata 類 Mapping wrapper 在 `.items()` 壞掉後仍不會因局部壞 key 中斷 report refresh stale-source classification 或抹掉同列 fresh audit evidence；RED→GREEN mapping traversal key hash lookup 單測、report refresh focused 與文件契約更新通過。

- D1179：P3-1073 補強 shared sequence iterator creation lookup fallback：`mapping_fields._sequence_iterator()` 在 list/tuple wrapper 的 `__iter__` 建立階段遇到 `KeyError` / `IndexError` 時會回退 native list/tuple iterator，讓 source_audit / metadata 類 sequence wrapper 在 iterator 建立前失敗時仍不會中斷 report refresh stale-source classification 或抹掉底層 fresh source audit evidence；RED→GREEN sequence iterator creation lookup 單測、report refresh focused 與文件契約更新通過。

- D1180：P3-1074 補強 provider impact local list iterator creation lookup fallback：`provider_impact._sequence_iterator()` 在 reason_codes / provider_sla_alerts 這類 list/tuple wrapper 的 `__iter__` 建立階段遇到 `KeyError` / `IndexError` 時會回退 native list/tuple iterator，讓 provider recovery impact 不會在 iterator 尚未開始前中斷，也不會抹掉底層有效 blocking reason code 或 provider alert evidence；RED→GREEN provider impact lookup iterator creation 單測與文件契約更新通過。

- D1181：P3-1075 補強 data trust provider SLA iterator creation lookup fallback：`data_trust_sla_policy._safe_iterator()` 在 source_audit rows、provider SLA alerts、trust reason_codes / notes 的 `__iter__` 建立階段遇到 `KeyError` / `IndexError` 時會回退 native list/tuple iterator，讓 provider SLA 降級判斷不會在 iterator 尚未開始前中斷，也不會抹掉底層有效 source audit、provider alert 或既有 trust metadata；RED→GREEN data trust provider SLA lookup iterator creation 單測與文件契約更新通過。

- D1182：P3-1076 補強 data trust provider SLA lookup iterator fallback：`data_trust_sla_policy._safe_text_list()` 與 `_safe_dict_rows()` 在 source_audit rows、provider SLA alerts、trust reason_codes / notes 的 `next(iterator)` 階段遇到 `KeyError` / `IndexError` 時會回退 native list/tuple iterator，讓 provider SLA 降級判斷不會因 malformed iterator 中斷，也不會抹掉底層有效 source audit、provider alert 或既有 trust metadata；RED→GREEN data trust provider SLA lookup iterator 單測與文件契約更新通過。

- D1183：P3-1077 補強 data trust provider SLA lookup scalar conversion fallback：`data_trust_sla_policy._safe_int()` 與 `_safe_bool()` 在 provider SLA attempts、source_audit record_count / stale 等 scalar 欄位遇到 `KeyError` / `IndexError` 時會保守回退為 0 / false，讓 Provider SLA 降級判斷不會因 malformed scalar adapter 中斷，也不會用不可信 attempts 產生 unsupported downgrade；RED→GREEN data trust provider SLA lookup scalar 單測與文件契約更新通過。

- D1184：P3-1078 補強 provider impact current-fetch lookup scalar fallback：`provider_impact._safe_int()` 與 `_safe_bool()` 在 provider_sla_alerts 的 current_record_count、current_stale、current_source_has_healthy_entry 等欄位遇到 `KeyError` / `IndexError` 時會保守回退為 0 / false，讓 provider recovery impact classification 不會因 malformed scalar adapter 中斷，也不會抹掉底層有效 wait-provider-recovery evidence；RED→GREEN provider impact current-fetch lookup scalar 單測與文件契約更新通過。

- D1185：P3-1079 補強 data trust explicit target price lookup traversal fallback：`report_reproducibility._safe_enumerate_list()` 與 `_safe_dict_items()` 在 parsed / structured output 的目標價偵測期間遇到 `KeyError` / `IndexError` iterator creation、iterator next 或 mapping items accessor 失敗時，會回退 native list / dict traversal，避免低信心報告的 explicit target-price guardrail 因 malformed wrapper 中斷或漏掉底層有效目標價欄位；RED→GREEN target-price lookup traversal 單測與文件契約更新通過。

- D1186：P3-1080 補強 data trust source record count lookup set traversal fallback：`data_trust_audit._set_items()` 在 custom enrichment set / frozenset source values 的 iterator creation 或 `next()` 階段遇到 `KeyError` / `IndexError` 時，會回退 native set / frozenset iterator，避免 unordered enrichment row wrapper 中斷 source record count 或抹掉底層有效資料來源證據；RED→GREEN source record count lookup set traversal 單測與文件契約更新通過。

- D1187：P3-1081 補強 data trust score lookup conversion fallback：`data_trust_scoring.normalize_data_trust()` 在 existing `data_trust.score` 轉換階段遇到 `KeyError` / `IndexError` 時會視為 malformed score 並回落到 status-derived scoring，避免壞掉的 score adapter 中斷 `.data.json` snapshot generation 或漏掉既有 fresh/error status 的 report confidence metadata；RED→GREEN data trust lookup score conversion 單測與文件契約更新通過。

- D1188：P3-1082 補強 data trust provider SLA policy lookup failure fallback：`data_trust_scoring.build_data_trust()` 在 `apply_provider_sla_to_trust()` 回傳前遇到 `KeyError` / `IndexError` policy adapter 失敗時，會回落到未污染的 base trust 並繼續 final score calculation，避免 provider SLA policy lookup failure 中斷 report confidence finalization 或抹掉已計算的 source audit trust evidence；RED→GREEN provider SLA policy lookup failure 單測與文件契約更新通過。

- D1189：P3-1083 補強 data trust snapshot validator lookup field fallback：`data_trust_snapshot_mapping.mapping_get()` 與 `mapping_has_key()` 在 snapshot wrapper 的 `.get()` 或 containment lookup 發生 `KeyError` / `IndexError` 時，會回退 `__getitem__` 欄位讀取，避免 `.data.json` integrity/hash 或 required-field schema verification 中斷，並保留底層有效 snapshot hash 與必填欄位證據；RED→GREEN snapshot lookup field accessor 單測與文件契約更新通過。

- D1190：P3-1084 補強 data trust snapshot refresh flag lookup truthiness fallback：`data_trust_snapshot._safe_bool()` 納入 `LookupError` fallback，讓 `refreshed_without_analysis_rerun` 等 refresh metadata 在 `__bool__` 丟 `KeyError` / `IndexError` 時保守落為 false，避免 `.data.json` snapshot generation 因壞旗標 adapter 中斷；RED→GREEN refresh flag lookup truthiness 單測與文件契約更新通過。

- D1191：P3-1085 補強 data trust source audit bool lookup truthiness fallback：`data_trust_audit._safe_bool()` 納入 `LookupError` fallback，讓 source audit row 的 `cache_hit` / `stale` 在 `__bool__` 丟 `KeyError` / `IndexError` 時保守落為 false，避免來源審計證據列建立因壞布林 adapter 中斷；RED→GREEN source audit bool lookup truthiness 單測與文件契約更新通過。

- D1192：P3-1086 補強 data trust provider SLA row copy lookup fallback：`data_trust_sla_policy._safe_dict()` 在 dict subclass copy 階段遇到 `KeyError` / `IndexError` 時回退 native `dict.items()`，讓 source-audit row 或 provider alert row 的 copy lookup adapter 失敗不會中斷 provider SLA policy，也不會抹掉底層有效 downgrade evidence；RED→GREEN provider SLA row copy lookup 單測與文件契約更新通過。

- D1193：P3-1087 補強 report key evidence aggregated stale lookup truthiness fallback：`reporting.evidence._source_evidence_entry()` 彙總成功 provider 的 stale flag 時改用既有 bool-safe conversion，讓 source-audit stale adapter 的 `__bool__` 丟 `KeyError` / `IndexError` 不會中斷關鍵數據來源對照 HTML / Markdown 輸出，也不會把畸形 stale 值標成過期；RED→GREEN key evidence stale 單測與文件契約更新通過。

- D1194：P3-1088 補強 report evidence matrix payload message fallback truthiness guard：`reporting.evidence_matrix.build_evidence_matrix_payload()` 改用 truthiness-safe message selection helper 選擇 message / error_kind / source，讓 source-audit message adapter 的 `__bool__` 丟 `KeyError` / `IndexError` 不會中斷 tooltip payload 生成，也不會把仍可文字化的 present message 覆寫成 fallback text；RED→GREEN evidence matrix message 單測與文件契約更新通過。

- D1195：P3-1089 補強 report plain-text sanitizer truthiness guard：`reporting.html_sanitizer.sanitize_report_plain_text()` 改用 truthiness-safe string conversion，讓催化事件、摘要、discipline 或 overlay 欄位物件的 `__bool__` 丟 `KeyError` / `IndexError` 時不會中斷 HTML 報告生成，且仍保留可文字化的有效報告文字；RED→GREEN catalyst plain-text 單測與文件契約更新通過。

- D1196：P3-1090 補強 report cover image URL sanitizer truthiness guard：`reporting.html_sanitizer.sanitize_report_image_url()` 改用 truthiness-safe string conversion，讓 report-cover image adapter 的 `__bool__` 丟 `KeyError` / `IndexError` 時不會中斷封面 metadata handling，且仍維持 data/http/https allowlist 阻擋 unsafe image sources；RED→GREEN cover image URL 單測與文件契約更新通過。

- D1197：P3-1091 補強 report HTML sanitizer truthiness guard：`reporting.html_sanitizer.sanitize_report_html()` 與 linkify 前處理改用 truthiness-safe string conversion，讓 model/report HTML fragment adapter 的 `__bool__` 丟 `KeyError` / `IndexError` 時不會中斷 HTML allowlist cleaning，且仍保留可文字化安全內容與既有 linkify 行為；RED→GREEN HTML sanitizer 單測與文件契約更新通過。

- D1198：P3-1092 補強 report analysis overlay list iterator lookup fallback：`reporting.analysis_overlays._highlight_rows()` 與 `_risk_rows()` 改用 shared `safe_dict_list()` 正規化 highlight / downside-risk list fields，讓 malformed iterator 的 `KeyError` / `IndexError` 不會中斷 management sentiment 或 downside-risk HTML 區塊，且底層有效 rows 仍能顯示；RED→GREEN analysis overlay list 單測與文件契約更新通過。

- D1199：P3-1093 補強 report next catalyst list iterator lookup fallback：`reporting.html_renderer._collect_next_catalysts()` 改用 shared `safe_mapping_dict()` 與 `safe_dict_list()` 正規化 catalyst source 與 `next_catalysts` list fields，讓 malformed iterator 的 `KeyError` / `IndexError` 不會中斷事件催化 trigger HTML 區塊，且底層有效 rows 仍能顯示；RED→GREEN next catalyst list 單測與文件契約更新通過。

- D1200：P3-1094 補強 report tear-sheet recent catalyst truthiness fallback：`reporting.sections.build_tear_sheet_summary()`、`investment_thesis_common.information_richness()` 與 `investment_thesis_assumptions.core_assumptions()` 改用 shared `safe_dict_list()` 正規化 `recent_catalysts` rows，讓 malformed list truthiness 的 `KeyError` / `IndexError` 不會中斷一頁式摘要或 investment-thesis discipline HTML 輸出，且有效 catalyst title 仍能進入摘要；RED→GREEN tear-sheet catalyst 單測與文件契約更新通過。

- D1201：P3-1095 補強 report investment-thesis final-audit warnings truthiness fallback：`investment_thesis_common.data_gaps()` 改用 shared `safe_text_list()` 正規化 `final_audit.warnings`，讓 malformed warning list truthiness 的 `KeyError` / `IndexError` 不會中斷 decision-discipline data-gap payload，也能保留有效 audit warning 文字；RED→GREEN investment-thesis warning 單測與文件契約更新通過。

- D1202：P3-1096 補強 report investment-thesis source-audit truthiness fallback：`investment_thesis_common.information_richness()` 改用 shared `safe_dict_list()` 正規化 `source_audit` rows，讓 malformed source-audit list truthiness 的 `KeyError` / `IndexError` 不會中斷 decision-discipline information-richness grading，也不會把有效 audit row count 歸零；RED→GREEN investment-thesis source-audit 單測與文件契約更新通過。

- D1203：P3-1097 補強 report investment-thesis history-series truthiness fallback：`investment_thesis_common.information_richness()` 改用 shared `safe_sequence_items()` 正規化 `revenue_history` / `net_income_history` / `fcf_history` 序列存在性，讓 malformed history list truthiness 的 `KeyError` / `IndexError` 不會中斷 decision-discipline information-richness grading，也不會抹掉有效歷史序列計數；RED→GREEN investment-thesis history-series 單測與文件契約更新通過。

- D1204：P3-1098 補強 report investment-thesis Markdown list-field truthiness fallback：`investment_thesis.investment_thesis_markdown()` 改用 shared `safe_text_list()` / `safe_dict_list()` 正規化 mirror lines、core assumptions、red lines 與 data gaps，讓 malformed list truthiness 的 `KeyError` / `IndexError` 不會中斷 decision-discipline Markdown 輸出，也不會抹掉有效 thesis evidence；RED→GREEN investment-thesis Markdown list-field 單測與文件契約更新通過。

- D1205：P3-1099 補強 report investment-thesis recommendation/trade-setup mapping truthiness fallback：`investment_thesis_common.first_mapping_value()` 與 `trade_setup_from_context()` 改用 shared `safe_mapping_items()` 正規化 recommendation 與 trade setup mapping 欄位，讓 malformed mapping truthiness 的 `KeyError` / `IndexError` 不會中斷 recommendation、target-price、confidence 或交易計畫擷取，也不會抹掉有效 thesis evidence；RED→GREEN investment-thesis mapping 單測與文件契約更新通過。

- D1206：P3-1100 補強 report investment-thesis structured scenario-trigger truthiness fallback：`investment_thesis_common.trigger_from_structured()` 改用 shared `safe_dict_list()` 正規化 `scenario_triggers` rows，讓 malformed trigger list truthiness 的 `KeyError` / `IndexError` 不會中斷 Mode C crash-trigger / stop-condition 擷取，也不會抹掉有效 scenario trigger evidence；RED→GREEN investment-thesis structured-trigger 單測與文件契約更新通過。

- D1207：P3-1101 補強 report investment-thesis data-trust status comparison fallback：`investment_thesis_common.data_gaps()` 與 `investment_thesis_assumptions` 的 Mode A/B red-line status 判斷改用 `safe_text()` 正規化 `data_trust.status` 後比較，讓 malformed status hash / equality adapter 的 `KeyError` / `IndexError` 不會中斷 data-gap 或 red-line rendering，也不會抹掉有效 partial data trust evidence；RED→GREEN investment-thesis data-trust status 單測與文件契約更新通過。

- D1208：P3-1102 補強 report investment-thesis final-audit critical truthiness fallback：`investment_thesis_common.downside_line()` 改用 shared `safe_text_list()` 正規化 `final_audit.critical` rows，讓 malformed critical-list truthiness 的 `KeyError` / `IndexError` 不會中斷 decision-discipline downside-risk rendering，也不會抹掉有效 critical issue evidence；RED→GREEN investment-thesis final-audit critical 單測與文件契約更新通過。

- D1209：P3-1103 補強 report investment-thesis agent analysis truthiness fallback：`investment_thesis_common.agent_text()` 改用欄位存在性與 shared `safe_text()` 選擇 agent analysis text，讓 malformed analysis-text truthiness 的 `KeyError` / `IndexError` 不會中斷 Mode C crash-trigger、stop-condition 或 mirror-line 摘要，也不會抹掉可字串化的有效 agent evidence；RED→GREEN investment-thesis agent-analysis 單測與文件契約更新通過。

- D1210：P3-1104 補強 report investment-thesis current-price truthiness fallback：`investment_thesis._current_price_text()` 集中用 shared `safe_text()` 優先讀取 `current_price_fmt`，再回退 `current_price`，讓 malformed formatted-price truthiness 的 `KeyError` / `IndexError` 不會中斷 mirror lines 或 valuation anchors，也不會抹掉可字串化的有效現價文字；RED→GREEN investment-thesis current-price 單測與文件契約更新通過。

- D1211：P3-1105 補強 report investment-thesis moat-score string conversion fallback：`investment_thesis_common.moat_line()` 改用 shared `safe_text()` 正規化 `moat_scores.整體護城河` 後再輸出，讓 malformed moat-score `__str__` 的 `KeyError` / `IndexError` 不會中斷 long thesis mirror-line rendering，並回到保守的護城河資料不足句；RED→GREEN investment-thesis moat-score 單測與文件契約更新通過。

- D1212：P3-1106 補強 report investment-thesis prebuilt payload truthiness fallback：`reporting.html_renderer.generate_html_report()` 先用 shared `safe_mapping_dict()` 正規化 `context.investment_thesis`，`investment_thesis_markdown()` 也先轉成 mapping-safe payload 後再渲染，讓 malformed prebuilt thesis payload truthiness 的 `KeyError` / `IndexError` 不會中斷 HTML / Markdown report rendering，也能保留有效 decision-discipline rows；RED→GREEN prebuilt investment-thesis payload 單測與文件契約更新通過。

- D1213：P3-1107 補強 report PE river chart payload truthiness fallback：`reporting.html_renderer.generate_html_report()` 交給 `chart_pe_river()` 前不再對 `data.pe_river_chart` 做 `or {}` truthiness handoff，讓 malformed `pe_river_chart` truthiness 的 `KeyError` / `IndexError` 不會中斷 HTML chart JSON rendering，也能保留有效 PE river years / bands / eps rows；RED→GREEN PE river chart payload 單測與文件契約更新通過。

- D1214：P3-1108 補強 report PE river chart payload Mapping wrapper fallback：`reporting.chart_payload.chart_pe_river()` 先用 shared `safe_mapping_dict()` 正規化 PE river root 與 nested `bands`，讓 immutable / Mapping-style `pe_river_chart` 不會被當成空 chart，也能保留 years、bands 與 eps rows 到 HTML chart JSON；RED→GREEN Mapping wrapper PE river chart 單測與文件契約更新通過。

- D1215：P3-1109 補強 report Markdown renderer prebuilt investment-thesis truthiness fallback：`reporting.markdown_renderer.generate_markdown_report()` 與 HTML renderer 一樣先用 shared `safe_mapping_dict()` 正規化 `context.investment_thesis`，讓 malformed prebuilt thesis payload truthiness 的 `KeyError` / `IndexError` 不會中斷 Markdown report rendering，也能保留有效 decision-discipline rows；RED→GREEN Markdown investment-thesis payload 單測與文件契約更新通過。

- D1216：P3-1110 補強 report price history chart payload Mapping wrapper fallback：`reporting.chart_payload.chart_price_history()` 先用 shared `safe_mapping_dict()` 正規化 `price_history`，讓 immutable / Mapping-style price history 不會被當成空 chart，也能保留有效 dates / prices 到 HTML chart JSON；RED→GREEN Mapping wrapper price history chart 單測與文件契約更新通過。

- D1217：P3-1111 補強 report price history chart series truthiness fallback：`reporting.utils.filter_future_price_history()` 與 `reporting.chart_payload.chart_price_history()` 改用 shared `safe_sequence_items()` 正規化 dates / prices 後再判斷與輸出，讓 malformed date/price series truthiness 的 `KeyError` / `IndexError` 不會中斷 HTML chart JSON rendering，也能保留有效 price history rows；RED→GREEN price history series truthiness 單測與文件契約更新通過。

- D1218：P3-1112 補強 report price history date safe-text fallback：`reporting.utils.filter_future_price_history()` 以 shared `safe_text()` 轉換日期欄位後再做 future-date filtering，讓單一 malformed date `__str__` 的 `KeyError` / `IndexError` 不會中斷 HTML chart JSON rendering，也不會遮蔽後續有效 price history rows；RED→GREEN unstringable date 單測與文件契約更新通過。

- D1219：P3-1113 補強 report price history mapping future-date filtering：`reporting.utils.filter_future_price_history()` 在 legacy `{date: price}` mapping payload 沒有 `dates` / `prices` 序列時，也會以 safe-text date key 做 future-date filtering，避免未來收盤價進入 HTML chart JSON scripts；RED→GREEN mapping future-date 單測與文件契約更新通過。

- D1220：P3-1114 補強 report audit banner abnormality list truthiness fallback：`reporting.audit_trust.build_audit_sections()` 在 HTML/Markdown top-of-report abnormality banner 產生前，先以 list-safe text conversion 正規化 `final_audit.critical`、`warnings`、`corrections`、`blocking_issues` 與 `audit_repair_log`，避免 malformed list wrapper 的 `KeyError` / `IndexError` truthiness 中斷異常提醒輸出，且仍保留有效 issue / repair text；RED→GREEN audit banner truthiness 單測與文件契約更新通過。

- D1221：P3-1115 補強 report data trust quant fallback-field truthiness fallback：`reporting.audit_trust.build_data_trust_html()` 與 `build_data_trust_markdown()` 在量化模型警示前以 `safe_text_list()` 正規化 `quant_metrics.fallback_fields`，避免 malformed fallback-field list wrapper 的 `KeyError` / `IndexError` truthiness 中斷資料可信度區塊，也保留有效 fallback 欄位名稱；RED→GREEN data trust quant fallback 單測與文件契約更新通過。

- D1222：P3-1116 補強 report trust-controls generated-at truthiness fallback：`reporting.trust_controls` 在建立 reproducibility packet 前以 shared `safe_text()` 正規化 `context.generated_at`，避免 malformed generated time wrapper 的 `KeyError` / `IndexError` truthiness 中斷資料信心分數與可重現資訊輸出，且仍保留有效 model/provider/code metadata；RED→GREEN trust-controls generated-at 單測與文件契約更新通過。

- D1223：P3-1117 補強 data trust reproducibility source-audit iterator fallback：`report_reproducibility.provider_list_from_audit()` 與 `source_data_time()` 改用 shared `safe_dict_list()` 正規化 `source_audit` rows，避免 malformed source-audit list wrapper 的 `KeyError` / `IndexError` iterator failure 中斷 snapshot reproducibility packet，也保留有效 provider list 與最新 source data time；RED→GREEN reproducibility source-audit iterator 單測與文件契約更新通過。

- D1224：P3-1118 補強 data trust explicit-target detector Mapping wrapper fallback：`report_reproducibility.detect_explicit_target_price_fields()` 與 nested target traversal 改用 shared `safe_mapping_dict()` 正規化 root、`parsed`、`structured_outputs` 與子 mapping，避免 read-only / Mapping-style structured output wrapper 隱藏明確目標價 guardrail evidence；RED→GREEN explicit target Mapping 單測與文件契約更新通過。

- D1225：P3-1119 補強 data trust reproducibility packet Mapping wrapper fallback：`report_reproducibility.build_reproducibility_packet()` 在入口以 shared `safe_mapping_dict()` 正規化 context/data，`_model_id()` 也支援 Mapping-style metadata，避免 read-only provenance payload 隱藏 ticker、pipeline、model、code、provider 或 source-time traceability；RED→GREEN reproducibility packet Mapping 單測與文件契約更新通過。

- D1226：P3-1120 補強 data trust reproducibility source-audit helper Mapping wrapper fallback：`report_reproducibility.provider_list_from_audit()` 與 `source_data_time()` 在 helper 入口以 shared `safe_mapping_dict()` 正規化 data payload，避免 direct helper caller 傳入 read-only Mapping data 時抹掉 provider list 或最新 source data time；RED→GREEN source-audit helper Mapping 單測與文件契約更新通過。

- D1227：P3-1121 補強 data trust explicit-target detector tuple sequence fallback：`report_reproducibility._detect_target_prices()` 將 tuple rows 納入 structured output traversal，並讓 sequence fallback iterator 支援 list / tuple native iterators，避免 immutable parsed 或 structured output row collections 隱藏明確目標價 guardrail evidence；RED→GREEN explicit target tuple 單測與文件契約更新通過。

- D1228：P3-1122 補強 data trust source-audit append tuple preservation：`data_trust_audit.append_source_audit()` 在追加新 audit entry 前會保留 tuple 型既有 `source_audit` batches，避免 immutable upstream source-audit payloads 在 audit enrichment 時丟失既有 provider/source evidence；RED→GREEN append source-audit tuple 單測與文件契約更新通過。

- D1229：P3-1123 補強 report mode-template tuple text-list rendering：`reporting.mode_templates._text_items()` 改用 shared `safe_text_list()`，讓 tuple 型 visual focus 與 reading path profile overrides 在 HTML/Markdown 報告模板區塊中保留 chips 與閱讀路徑，同時維持 binary/memory-view 文字安全；RED→GREEN mode template tuple rendering 單測與文件契約更新通過。

- D1230：P3-1124 補強 report analysis-overlay financial-history tuple fallback：`reporting.analysis_overlays._last_number()` 改用 shared `safe_sequence_items()` 讀取財務歷史序列，讓 tuple 型 `total_assets_history` 仍可進入 peer-comparison target row 的 asset turnover 計算，避免同業比較表漏掉目標公司效率證據；RED→GREEN analysis overlay tuple asset-history 單測與文件契約更新通過。

- D1231：P3-1125 補強 report content-credibility evidence-matrix tuple fallback：`reporting.content_credibility._as_list()` 改用 shared `safe_sequence_items()` 正規化 evidence matrix rows，讓 snapshot 中 tuple 型 evidence rows 仍可通過 coverage check，避免內容可信度 gate 對已覆蓋的最終投資建議產生 false missing-evidence warning；RED→GREEN content credibility tuple evidence-matrix 單測與文件契約更新通過。

- D1232：P3-1126 補強 report content-credibility Mapping wrapper fallback：`reporting.content_credibility._as_dict()` 改用 shared `safe_mapping_dict()` 正規化 context、snapshot、data、parsed 與 recommendation 等 quality-gate payloads，讓 read-only Mapping wrappers 不會隱藏買入/目標價/現價矛盾、evidence gate 或 data-trust blockers；RED→GREEN content credibility Mapping 單測與文件契約更新通過。

- D1233：P3-1127 補強 report conformance Mapping wrapper fallback：`reporting.conformance._as_dict()` 改用 shared `safe_mapping_dict()` 正規化 context、snapshot、report lint、evidence gate 與 content credibility payloads，讓 read-only Mapping wrappers 不會在 decision-tree evaluation 中隱藏 blocker 或 warning evidence；RED→GREEN report conformance Mapping 單測與文件契約更新通過。

- D1234：P3-1128 補強 report conformance issue-list tuple fallback：`reporting.conformance` 將 report lint、final audit 與 content credibility 的 blocking/warning issue lists 改用 shared `safe_sequence_items()` 正規化，讓 tuple 型 blocker/warning rows 不會在 decision-tree evaluation 中被當成空清單而誤判 passed；RED→GREEN report conformance tuple issue-list 單測與文件契約更新通過。

- D1235：P3-1129 補強 report content-credibility evidence-matrix row Mapping fallback：`reporting.content_credibility._has_evidence_claim()` 會先用 shared `safe_mapping_dict()` 正規化每一筆 evidence matrix row，再判斷 `claim` 覆蓋狀態，讓 read-only Mapping evidence rows 不再被誤判缺少最終投資建議證據；RED→GREEN content credibility mapping evidence-row 單測與文件契約更新通過。

- D1236：P3-1130 補強 report execution-summary quality-gate child Mapping fallback：`reporting.execution_summary._execution_summary_values()` 會先用 shared `safe_mapping_dict()` 正規化 context、data、final audit、evidence gate、report conformance 與 report lint child maps，讓 read-only quality-gate wrappers 不會在 HTML/Markdown 執行摘要中被降成 `unknown` 或 `not_recorded`；RED→GREEN execution summary mapping child-map 單測與文件契約更新通過。

- D1237：P3-1131 補強 report HTML renderer structured-output child Mapping fallback：`reporting.html_renderer._structured_output_values()` 會先用 shared `safe_mapping_dict()` 正規化每個 structured output child payload，再萃取 `next_catalysts`，讓 read-only agent payload wrappers 不會隱藏有效催化事件與 watchlist trigger；RED→GREEN structured-output child mapping catalyst 單測與文件契約更新通過。

- D1238：P3-1132 補強 report HTML renderer TWSE official availability banner source-audit fallback：`reporting.html_renderer.generate_html_report()` 的 TWSE/MOPS unavailable banner 判斷改用 shared `safe_dict_list()` 正規化 `source_audit` rows，並用 shared text conversion 比對 `source/status`，讓 tuple 或 read-only 官方來源 success rows 不會誤觸「台股官方財務資料未取得」警示；RED→GREEN TWSE official source-audit banner 單測與文件契約更新通過。

- D1239：P3-1133 補強 report agent section structured-output child Mapping fallback：`reporting.sections.build_agent_sections()` 在 v3 structured tail rendering 前會先用 shared `safe_mapping_dict()` 正規化 agent structured-output child payload，讓 read-only 最終建議 payloads 不會被跳過，HTML/Markdown 仍保留結構化結論與情境觸發器；RED→GREEN agent output child mapping section 單測與文件契約更新通過。

- D1240：P3-1134 補強 report structured-output normalizer Mapping payload fallback：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 前會先用 shared mapping/sequence helpers 將 read-only agent JSON 轉為 plain JSON-like payload，recommendation alias 正規化與 legacy report text rendering 也使用 mapping-safe child reads，避免唯讀 structured agent payload 或 nested recommendation map 在最終建議、信心依據、催化事件與情境觸發器輸出前被丟棄；RED→GREEN readonly structured-output normalizer 單測與文件契約更新通過。

- D1241：P3-1135 補強 report evidence-matrix limitation note tuple fallback：`reporting.evidence_matrix._as_notes()` 對 `data_source_notes` 的 list/tuple payload 改用 shared `safe_text_list()`，讓 tuple 型資料限制說明保留有效文字並過濾 binary 壞值，避免 HTML/Markdown/snapshot 的報告證據矩陣 limitation 欄位出現 Python tuple 或 bytes repr；RED→GREEN tuple data-source notes 單測與文件契約更新通過。

- D1242：P3-1136 補強 report evidence-matrix message fallback text-empty guard：`reporting.evidence_matrix._source_message_text()` 在選用 source-audit `message` / `error_kind` / `source` 前會確認候選值轉成安全文字後非空，讓 binary 或 memory-view 型 malformed `message` 不會擋住有效 `error_kind`，避免報告證據 tooltip 把真實 provider 錯誤原因降成 `N/A`；RED→GREEN text-empty message fallback 單測與文件契約更新通過。

- D1243：P3-1137 補強 Agent 19 required-section scenario-trigger Mapping fallback：`structured_output_rendering.ensure_agent19_required_sections()` 與 `_trigger_lines()` 改用 shared mapping/list/text helpers 讀取 `scenario_triggers`，讓 read-only trigger rows 仍能填入「做空觸發條件」與「防軋空停損點」必填段落，避免有效情境觸發器只出現在尾段摘要、必填風控段落卻落成 placeholder；RED→GREEN readonly Agent 19 stop-loss section 單測與文件契約更新通過。

- D1244：P3-1138 補強 report recommendation block nested Mapping filter：`structured_output_rendering.format_recommendation_block()` 在 legacy report text rendering 前會先用 shared mapping/text helpers 正規化 recommendation payload，並跳過 nested confidence-basis maps，讓 read-only 信心依據仍保留在「信心依據」段落但不會以 Python mapping 表示法洩漏到 `[投資建議]` 摘要；RED→GREEN readonly confidence-basis recommendation-block 單測與文件契約更新通過。

- D1245：P3-1139 補強 Agent 19 recommendation ordered-value text safety：`recommendation_labels.normalize_recommendation_label()` 與 `structured_output_rendering.format_recommendation_block()` 的 Agent 19 固定欄位輸出改用 shared text conversion，讓 binary 或 memory-view 型建議、目標價、信心指數欄位回落 `N/A`，避免 Python literal 洩漏到最終 `[投資建議]` 區塊；RED→GREEN malformed ordered-value 單測與文件契約更新通過。

- D1246：P3-1140 補強 legacy structured display-field text safety：`structured_output_normalizer.structured_output_to_report_text()` 的 Agent 20/21/24 legacy 文本輸出改用 shared text conversion，讓 malformed management tone、highlight、downside-risk 與短線交易計畫欄位回落預設值，避免 binary 或 memory-view Python literal 洩漏到最終報告正文；RED→GREEN malformed legacy display-field 單測與文件契約更新通過。

- D1247：P3-1141 補強 recommendation tail basis/trigger text safety：`structured_output_normalizer.structured_output_to_report_text()` 的信心依據清單改用 shared text-list conversion，情境觸發器條件與 action 改用 shared text conversion 並跳過空條件，讓 malformed confidence-basis items、trigger condition 或 action 不會把 binary/memory-view Python literal 洩漏到最終推薦 tail sections，同時保留有效佐證與有效觸發條件；RED→GREEN malformed basis/trigger tail 單測與文件契約更新通過。

- D1248：P3-1142 補強 legacy score/valuation display safety：`structured_output_normalizer.structured_output_to_report_text()` 的護城河分數、目標股價與估值摘要輸出改用 shared display conversion，讓 malformed moat scores、price targets 或 valuation summary fields 回落 `N/A`，避免目標價格式化中斷報告文字轉換或把 binary/memory-view Python literal 洩漏到 structured report bodies；RED→GREEN malformed score/valuation display 單測與文件契約更新通過。

- D1249：P3-1143 補強 legacy analysis markdown body fallback：`structured_output_normalizer.structured_output_to_report_text()` 會先對 `analysis_markdown` 與 `fallback_text` 做 shared text conversion，再執行 escaped-newline normalization，讓 malformed analysis bodies 不會以 memory-view Python literal 進入報告正文，並能安全回落有效 fallback 正文；RED→GREEN malformed body fallback 單測與文件契約更新通過。

- D1250：P3-1144 補強 recommendation block display-key text safety：`structured_output_rendering.format_recommendation_block()` 的非 Agent 19 recommendation display rows 會同時對 field key 與 value 做 shared text conversion，並跳過 malformed/empty display keys，避免 memory-view 型欄位名稱與其值洩漏到最終 `[投資建議]` 區塊；RED→GREEN malformed recommendation display-key 單測與文件契約更新通過。

- D1251：P3-1145 補強 report moat-score boolean exclusion：`reporting.utils.normalize_moat_scores()` 排除 `bool` 型護城河分數，避免 Python 中 `bool` 為 `int` 子類造成 malformed flags 在 HTML/Markdown 可見報告區塊或圖表 payload 中渲染為 `True`、`False`、1/0 分；RED→GREEN boolean moat-score 單測與文件契約更新通過。

- D1252：P3-1146 補強 evidence-matrix target-price boolean exclusion：`reporting.evidence_matrix._format_price()` 排除 `bool` 型目標價，避免 Python 中 `True` / `False` 被格式化成 `NT$1` / `NT$0` 並出現在報告證據矩陣、snapshot 或 tooltip 的估值依據；RED→GREEN boolean target-price evidence-matrix 單測與文件契約更新通過。

- D1253：P3-1147 補強 key-evidence data-field presence guard：`reporting.evidence._has_evidence_value()` 改用可用值判斷，遞迴保留有效 list/map evidence，同時排除 `bool`、binary 與 memory-view scalar，避免 malformed market-data 欄位合成「股價與市值」來源證據列；RED→GREEN malformed scalar key-evidence 單測與文件契約更新通過。

- D1254：P3-1148 補強 evidence-matrix recommendation-key text safety：`reporting.evidence_matrix._recommendation_basis()` 的 recommendation 欄位 key 比對改用 shared `safe_text()`，避免 malformed key `__str__` 例外中斷報告證據矩陣，也保留有效「建議」與「信心」依據；RED→GREEN malformed recommendation-key evidence-matrix 單測與文件契約更新通過。

- D1255：P3-1149 補強 evidence-matrix moat-metric key text safety：`reporting.evidence_matrix._moat_basis()` 在護城河指標輸出前先取得可用 metric 文字並跳過空值，避免 binary 或 memory-view 壞 key 在報告證據矩陣中渲染成 `N/A: 8/10` 假指標，同時保留有效「整體護城河」與細項指標；RED→GREEN malformed moat-metric-key evidence-matrix 單測與文件契約更新通過。

- D1256：P3-1150 補強 evidence-matrix price-target scenario key text safety：`reporting.evidence_matrix._price_target_basis()` 在估值情境輸出前先取得可用 scenario 文字並跳過空值，避免 binary 或 memory-view 壞 key 在報告證據矩陣中渲染成 `N/A: NT$120` 假情境，同時保留有效「牛市情境」等估值依據；RED→GREEN malformed price-target-scenario-key evidence-matrix 單測與文件契約更新通過。

- D1257：P3-1151 補強 evidence-matrix recommendation value equality safety：`reporting.evidence_matrix._recommendation_basis()` 改用 `_basis_value_text()` 判斷 recommendation value 是否可用，避免 malformed value `__eq__` 在空值 membership 檢查時中斷報告證據矩陣，同時保留可文字化的有效「建議」與「信心」依據；RED→GREEN malformed recommendation-value evidence-matrix 單測與文件契約更新通過。

- D1258：P3-1152 補強 evidence-matrix price-target finite-number guard：`reporting.evidence_matrix._format_price()` 在目標價貨幣格式化前排除 `NaN` / `Infinity` / `-Infinity`，避免 malformed target numbers 在報告證據矩陣、snapshot 或 tooltip 中渲染成 `NT$nan` / `NT$inf` 估值依據，同時保留有限數值的正常格式；RED→GREEN non-finite target-price evidence-matrix 單測與文件契約更新通過。

- D1259：P3-1153 補強 evidence-matrix fetched-at truthiness safety：`reporting.evidence_matrix._latest_fetched_at()` 先以 mapping-safe row normalization 與 shared text conversion 取得 evidence row `fetched_at`，避免 malformed timestamp `__bool__` / equality 在結論證據矩陣的 HTML、Markdown、snapshot 或 tooltip 輸出時中斷渲染，同時保留可文字化的有效抓取時間；RED→GREEN malformed fetched-at evidence-matrix 單測與文件契約更新通過。

- D1260：P3-1154 補強 evidence-matrix row-status truthiness safety：`reporting.evidence_matrix._combined_status()` 先以 mapping-safe row normalization 與 shared text conversion 取得 evidence row `status`，避免 malformed status `__bool__` 在結論證據矩陣狀態彙整時中斷 HTML、Markdown、snapshot 或 tooltip 輸出，同時保留可文字化的有效成功/錯誤狀態；RED→GREEN malformed row-status evidence-matrix 單測與文件契約更新通過。

- D1261：P3-1155 補強 evidence-matrix row-provider truthiness safety：`reporting.evidence_matrix._row()` 在彙整 evidence row provider/source label 前先做 mapping-safe row normalization 與 shared text conversion，避免 malformed provider `__bool__` 中斷結論證據矩陣 HTML、Markdown、snapshot 或 tooltip 輸出，同時保留可文字化的有效 provider evidence；RED→GREEN malformed row-provider evidence-matrix 單測與文件契約更新通過。

- D1262：P3-1156 補強 evidence-matrix stale-source flag bool safety：`reporting.evidence_matrix._data_limitations()` 在彙整 evidence row stale-source limitation 前先做 mapping-safe row normalization 與 bool-safe flag conversion，避免 malformed stale `__bool__` 中斷結論證據矩陣 HTML、Markdown、snapshot 或 tooltip 輸出，也避免畸形 stale 值合成過期來源說明；RED→GREEN malformed stale flag evidence-matrix 單測與文件契約更新通過。

- D1263：P3-1157 補強 evidence-matrix source-label matching safety：`reporting.evidence_matrix._source_rows_by_label()` 在建立 conclusion evidence lookup 前先做 mapping-safe row normalization 與 shared text conversion，避免 malformed label hash / key behavior 中斷結論證據矩陣 HTML、Markdown、snapshot 或 tooltip 輸出，同時保留可文字化的有效 key evidence row；RED→GREEN malformed source-label evidence-matrix 單測與文件契約更新通過。

- D1264：P3-1158 補強 evidence-matrix tooltip message length safety：`reporting.evidence_matrix._has_message_value()` 在檢查 source-audit message container 是否有值時會吸收 length lookup 例外並保守回落為不可用，避免 malformed message container `__len__` 中斷 tooltip payload 生成，也讓有效 `error_kind` fallback 仍能呈現；RED→GREEN malformed message length evidence-matrix payload 單測與文件契約更新通過。

- D1265：P3-1159 補強 evidence-matrix Markdown cell truthiness safety：`reporting.evidence_matrix._markdown_cell()` 改用 shared text conversion 輸出 table cell，避免 malformed cell `__bool__` 中斷 Markdown 匯出，同時保留既有 pipe / newline 清理以維持表格結構；RED→GREEN malformed Markdown cell evidence-matrix 單測與文件契約更新通過。

- D1266：P3-1160 補強 evidence-matrix HTML cell stringification safety：`reporting.evidence_matrix.build_evidence_matrix_html()` 改用 `_html_cell()` 與 shared text conversion 輸出 table cell，避免 malformed cell `__str__` 中斷 HTML 報告渲染或把例外文字洩漏到可見證據矩陣；RED→GREEN malformed HTML cell evidence-matrix 單測與文件契約更新通過。

- D1267：P3-1161 補強 evidence-matrix recommendation value strip safety：`reporting.evidence_matrix._basis_value_text()` 的 string value 分支改用 shared text conversion，避免 malformed recommendation value `.strip()` 中斷結論證據矩陣 HTML、Markdown、snapshot 或 tooltip 輸出，同時保留可文字化的有效「建議」與「信心」依據；RED→GREEN malformed recommendation string-value evidence-matrix 單測與文件契約更新通過。

- D1268：P3-1162 補強 evidence-matrix source-audit message strip safety：`reporting.evidence_matrix._has_message_value()` 的 string message presence check 改用 shared text conversion，避免 malformed source-audit message `.strip()` 中斷 tooltip payload 生成或把仍可文字化的 present message 覆寫成 fallback text；RED→GREEN malformed message string-strip evidence-matrix payload 單測與文件契約更新通過。

- D1269：P3-1163 補強 key-evidence data string strip safety：`reporting.evidence._has_usable_evidence_value()` 的 string data-field presence check 改用 shared text conversion，避免 malformed data string `.strip()` 中斷關鍵數據來源對照 HTML/Markdown 生成或抹掉仍可文字化的有效來源證據；RED→GREEN malformed key-evidence data string-strip 單測與文件契約更新通過。

- D1270：P3-1164 補強 key-evidence Markdown table separator safety：`reporting.evidence.build_key_evidence_markdown()` 改用 Markdown cell helper 輸出 Provider、狀態、抓取時間與筆數欄位，將 `|` 轉成 `/` 並把 newline 壓成空白，避免 provider 或 timestamp 文字破壞關鍵數據來源對照 Markdown table 結構；RED→GREEN key-evidence Markdown separator 單測與文件契約更新通過。

- D1271：P3-1165 補強 source-audit Markdown table separator safety：`reporting.audit_trust.build_source_audit_markdown()` 改用 Markdown cell helper 輸出來源、Provider、狀態、抓取時間、耗時、筆數與訊息欄位，將 `|` 轉成 `/` 並把 newline 壓成空白，避免 source audit provider、timestamp 或 message 文字破壞來源審計 Markdown table 結構；RED→GREEN source-audit Markdown separator 單測與文件契約更新通過。

- D1272：P3-1166 補強 Markdown reference-source table separator safety：`reporting.markdown_renderer.generate_markdown_report()` 在底部參考資料來源 table 輸出前，將動態 model-route summary 與 pipeline 描述套用 Markdown cell helper，將 `|` 轉成 `/` 並把 newline 壓成空白，避免模型路由文字破壞可下載 Markdown 報告的參考來源表格結構；RED→GREEN Markdown reference-source separator 單測與文件契約更新通過。

- D1273：P3-1167 補強 Markdown single-line field newline safety：`reporting.markdown_renderer._display_text()`、`reporting.sections._safe_report_text()` 與 `investment_thesis._display_text()` 在主 Markdown 報告的標題、日期、關鍵指標、決策欄位、tear-sheet 摘要與 investment-thesis 鏡子測試行輸出前，將 embedded newlines 壓成單一空白，避免 ticker/company/fetch-date/metric/target-price 等單行欄位切裂 heading、summary 或 bullet 結構；RED→GREEN Markdown single-line newline 單測與文件契約更新通過。

- D1274：P3-1168 補強 investment-thesis Markdown display-field newline safety：`investment_thesis.investment_thesis_markdown()` 在渲染 prebuilt thesis 的 heading、health label/score、information-richness、mirror status/lines、assumptions、red lines、data gaps 與 next-review 文字前，統一套用 single-line display conversion，避免 embedded newlines 切裂 decision-discipline headings 或 bullet rows；RED→GREEN investment-thesis Markdown display-field newline 單測與文件契約更新通過。

- D1275：P3-1169 補強 mode-template Markdown display-field newline safety：`reporting.mode_templates._text()` 與 `_text_items()` 在閱讀路徑 Markdown 區塊、summary heading 與 decision heading 輸出前，將 template name、audience、core question、visual-focus chip 與 reading-path item 的 embedded newlines 壓成單一空白，避免模板卡 heading 或 bullet rows 被切裂；RED→GREEN mode-template Markdown display-field newline 單測與文件契約更新通過。

- D1276：P3-1170 補強 execution-summary Markdown text-field newline safety：`reporting.execution_summary._status()` 與 model-route summary handoff 在執行邏輯與模型檢查 Markdown 區塊輸出前，將 model routes、quality gate status/summary、prompt version 與 model id 的 embedded newlines 壓成單一空白，避免 runtime trace bullet rows 被切裂；RED→GREEN execution-summary Markdown newline 單測與文件契約更新通過。

- D1277：P3-1171 補強 reading-notice Markdown gate-text newline safety：`reporting.reading_notice._status()` 與 `_unique_texts()` 在報告使用範圍與判讀限制 Markdown 輸出前，將 evidence/content/conformance gate values 與 snapshot integrity detail 的 embedded newlines 壓成單一空白，避免使用限制 checklist rows 或 warning blockquote 被切裂；RED→GREEN reading-notice Markdown gate-text newline 單測與文件契約更新通過。

- D1278：P3-1172 補強 trust-controls Markdown reproducibility-field newline safety：`reporting.trust_controls` 在資料信心控制列輸出前，將 pipeline/model/prompt/code/provider/source-time 等可重現資訊欄位的 embedded newlines 壓成單一空白，避免 Markdown 可重現資訊 bullet 被切裂；RED→GREEN trust-controls reproducibility newline 單測與文件契約更新通過。

- D1279：P3-1173 補強 data-trust Markdown summary-bullet newline safety：`reporting.audit_trust.build_data_trust_markdown()` 在資料可信度摘要輸出前，將市場資料時間、原因 label、notes 與量化模型警示文字的 embedded newlines 壓成單一空白，避免 data-confidence bullets 被切裂；RED→GREEN data-trust Markdown summary newline 單測與文件契約更新通過。

- D1280：P3-1174 補強 audit-banner Markdown abnormality-bullet newline safety：`reporting.audit_trust.build_audit_markdown()` 在系統異常提醒輸出前，將 final audit、blocking issue、repair log、correction 與 warning item 的 embedded newlines 壓成單一空白，避免 top-of-report abnormality bullets 被切裂；RED→GREEN audit-banner Markdown abnormality newline 單測與文件契約更新通過。

- D1281：P3-1175 補強 recommendation-tail Markdown basis/trigger newline safety：`structured_output_normalizer.structured_output_to_report_text()` 在 legacy recommendation tail 輸出前，將 confidence-basis items 與 scenario trigger condition/action 的 embedded newlines 壓成單一空白，避免 final recommendation tail bullets 被切裂，同時保留 analysis_markdown 正文換行；RED→GREEN recommendation-tail Markdown newline 單測與文件契約更新通過。

- D1282：P3-1176 補強 legacy structured Markdown display-field newline safety：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20/21/24 legacy structured report text 輸出前，將 management tone/highlights、downside risks 與 short-term trade-plan display fields 的 embedded newlines 壓成單一空白，避免 heading 與 bullet rows 被切裂，同時保留 analysis_markdown 正文換行；RED→GREEN legacy structured Markdown display-field newline 單測與文件契約更新通過。

- D1283：P3-1177 補強 legacy score/valuation Markdown key-value newline safety：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 3/12 moat-score rows 與 Agent 4/14 valuation-summary bullets 輸出前，將 key/value display fields 的 embedded newlines 壓成單一空白，避免護城河評分列與結構化估值檢查 bullets 被切裂，同時保留 analysis_markdown 正文換行；RED→GREEN legacy score/valuation Markdown key-value newline 單測與文件契約更新通過。

- D1284：P3-1178 補強 recommendation-block Markdown display-row newline safety：`structured_output_rendering.format_recommendation_block()` 在 legacy `[投資建議]` 摘要列輸出前，將非 Agent 19 recommendation labels/values 與 Agent 19 ordered values 的 embedded newlines 壓成單一空白，避免投資建議 key/value rows 被切裂，同時保留 analysis_markdown 正文換行；RED→GREEN recommendation-block Markdown display-row newline 單測與文件契約更新通過。

- D1285：P3-1179 補強 Agent 19 required-section trigger-row newline safety：`structured_output_rendering.ensure_agent19_required_sections()` 的 crash-catalyst 與 stop-loss required-section trigger rows 在輸出前，將 trigger condition/action 的 embedded newlines 壓成單一空白，避免做空觸發條件與防軋空停損點 bullets 被切裂，同時保留 analysis_markdown 正文換行；RED→GREEN Agent 19 required-section trigger-row newline 單測與文件契約更新通過。

- D1286：P3-1180 補強 analysis-overlay HTML display-field newline safety：`reporting.analysis_overlays._text()` 在管理層語氣、法說亮點、紅軍下行摘要/風險與同業比較 name/ticker 送入 HTML overlay 前，將 embedded newlines 壓成單一空白，避免 overlay lead、cards 或 table labels 形成多行碎片；RED→GREEN analysis-overlay display-field newline 單測與文件契約更新通過。

- D1287：P3-1181 補強 content-credibility recommendation/gate text fallback：`reporting.content_credibility` 在 recommendation key fragment matching、target/confidence price parsing、evidence claim/verdict 與 data-trust status label 判讀前改用 shared `safe_text()`，避免 malformed recommendation keys 或 target/confidence values 的 `__str__` 例外中斷內容可信度 gate，並讓後續有效目標價仍能觸發阻斷矛盾；RED→GREEN content-credibility safe-text 單測與文件契約更新通過。

- D1288：P3-1182 補強 report-conformance visible/gate text fallback：`reporting.conformance` 在 visible artifact 掃描與 lint、final audit、evidence gate、content credibility、data-trust status 判讀前改用 shared `safe_text()`，避免 malformed HTML、Markdown 或 gate status 的 `__str__` 例外中斷 report quality decision tree，並讓缺段落與警示仍能被分類為 blocking/warning；RED→GREEN report-conformance safe-text 單測與文件契約更新通過。

- D1289：P3-1183 補強 structured-output normalizer reasoning-step text fallback：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 前先以 shared `safe_text()` 正規化 `reasoning_steps`，保留有效推論步驟並跳過 malformed step values，避免單一壞 reasoning step 讓 otherwise valid recommendation payload 被丟棄、進而削弱最終報告 structured conclusion；RED→GREEN structured-output normalizer reasoning-step 單測與文件契約更新通過。

- D1290：P3-1184 補強 structured-output normalizer scenario-trigger prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 與 next-catalyst derivation 前先用 shared `safe_dict_list()` / `safe_text()` 正規化 `scenario_triggers`，跳過 malformed trigger rows、保留有效崩盤催化與停損 trigger，避免單一壞 trigger condition 的 `__str__` 例外中斷 structured recommendation 並讓 otherwise valid payload 被丟棄；RED→GREEN structured-output scenario-trigger prevalidation 單測與文件契約更新通過。

- D1291：P3-1185 補強 structured-output normalizer confidence-basis prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 前先用 shared `safe_mapping_dict()` / `safe_text_list()` 正規化 `confidence_basis` 的 evidence、risk 與 data-gap lists，跳過 malformed items、保留有效信心依據，避免單一壞 evidence/risk item 讓 otherwise valid recommendation payload 被丟棄；RED→GREEN structured-output confidence-basis prevalidation 單測與文件契約更新通過。

- D1292：P3-1186 補強 structured-output normalizer price-target boolean exclusion：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 後仍用 validation 前的原始 price-target 數值做最終數字轉換，並讓 `_coerce_number()` 排除 `bool`，避免 Pydantic 將 `True`/`False` 轉成 `1.0`/`0.0` 後污染 legacy 估值報告為 `NT$1` 或 `NT$0`；RED→GREEN structured-output boolean price-target 單測與文件契約更新通過。

- D1293：P3-1187 補強 structured-output legacy price-target exception-safe number conversion：`structured_output_normalizer._coerce_number()` 會吸收 malformed target number 的 `__float__` / numeric conversion 例外並降級為 `N/A`，避免單一壞 price-target 物件中斷 legacy `[目標股價]` 報告文字，同時保留其他有效估值情境；RED→GREEN structured-output exception-safe price-target 單測與文件契約更新通過。

- D1294：P3-1188 補強 structured-output legacy price-target finite-number conversion：`structured_output_normalizer._coerce_number()` 在格式化 legacy 估值目標價前排除 `NaN` / `Infinity` / `-Infinity`，讓非有限 target value 顯示為 `N/A`，避免 `[目標股價]` 報告文字外溢 `NT$nan` 或 `NT$inf` 並誤導估值情境；RED→GREEN structured-output non-finite price-target 單測與文件契約更新通過。

- D1295：P3-1189 補強 structured-output legacy price-target scientific-notation parsing：`structured_output_normalizer._coerce_number()` 改用單一 numeric token 解析目標價字串並保留 exponent，讓 `1e3` 類科學記號正確顯示為 `NT$1,000`，避免舊的字元清洗把它合成 `NT$13` 這類錯誤估值；RED→GREEN structured-output scientific-notation price-target 單測與文件契約更新通過。

- D1296：P3-1190 補強 structured-output normalizer price-target scenario-key safe text conversion：`structured_output_normalizer.normalize_structured_output()` 在掃描 raw `price_targets` 情境 key 前先用 shared safe text 顯示轉換，跳過 malformed extra target keys，避免 schema 忽略的額外壞 key 在後處理階段中斷估值 normalizer 並抹掉有效熊/基/牛目標價；RED→GREEN structured-output malformed price-target-key 單測與文件契約更新通過。

- D1297：P3-1191 補強 structured-output normalizer moat-score boolean exclusion：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 後仍用 validation 前的原始 moat-score 數值做最終分數轉換，避免 Pydantic 將 `True`/`False` 轉成 `1.0`/`0.0` 後污染 legacy 護城河評分報告；RED→GREEN structured-output boolean moat-score 單測與文件契約更新通過。

- D1298：P3-1192 補強 structured-output normalizer management-confidence boolean exclusion：`structured_output_normalizer.normalize_structured_output()` 在 Agent 20 管理層語氣信心分數後處理時改用 validation 前的原始 `confidence`，避免 Pydantic 將 `True`/`False` 轉成 `1.0`/`0.0` 後污染 management sentiment payload 為滿分或零分信心；RED→GREEN structured-output boolean management-confidence 單測與文件契約更新通過。

- D1299：P3-1193 補強 structured-output normalizer downside-risk confidence boolean exclusion：`structured_output_normalizer.normalize_structured_output()` 在 Agent 21 下行風險列後處理時用 validation 前的原始 `confidence` 重新轉換，遇到 `True`/`False` 這類 malformed flags 時回落到 schema 預設 `0.7`，避免 downside risk payload 被污染成滿分或零分信心；RED→GREEN structured-output boolean downside-risk-confidence 單測與文件契約更新通過。

- D1300：P3-1194 補強 structured-output normalizer downside-risk confidence zero preservation：`structured_output_normalizer.normalize_structured_output()` 在 Agent 21 下行風險列後處理時保留 `_coerce_number()` 回傳的有效 `0.0`，只在轉換失敗時回落到 schema 預設 `0.7`，避免有效低信心風險訊號被 falsey 判斷靜默升級成預設信心；RED→GREEN structured-output zero downside-risk-confidence 單測與文件契約更新通過。

- D1301：P3-1195 補強 structured-output normalizer trade-plan text prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 24 極短線交易計畫 schema validation 前先用 shared safe text 正規化必要文字欄位，將 malformed entry / target / stop-loss / catalyst 降級為 `N/A`，避免單一壞欄位讓 otherwise valid 1-2 週交易計畫 payload 被整包丟棄；RED→GREEN structured-output trade-plan safe-text 單測與文件契約更新通過。

- D1302：P3-1196 補強 structured-output normalizer management-sentiment text prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 20 管理層語氣 schema validation 前先用 shared safe text 正規化 `guidance_tone` 與 highlights 的 keyword / quote，將 malformed tone 降級為 `資料不足`、壞 highlight 欄位降級為 `亮點` / `資料不足`，避免單一壞文字欄位讓 otherwise valid management sentiment payload 被整包丟棄；RED→GREEN structured-output management safe-text 單測與文件契約更新通過。

- D1303：P3-1197 補強 structured-output normalizer downside-risk text prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 21 下行風險 schema validation 前先用 shared safe text 正規化 `thesis_summary`、risk title / evidence / impact / severity 與 analysis markdown，將 malformed title 降級為 `下行風險`、壞 evidence 降級為 `資料不足`、不合法 severity 降級為 `warning`，避免單一壞文字欄位讓 otherwise valid downside risk payload 被整包丟棄；RED→GREEN structured-output downside-risk safe-text 單測與文件契約更新通過。

- D1304：P3-1198 補強 structured-output normalizer price-target reasoning prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 4/14 目標價 schema validation 前先用 shared safe text 正規化 price-target DCF / peer / scenario reasoning，並在後處理 raw reasoning 失敗時回落到已正規化欄位，避免單一 malformed 推論文字讓 otherwise valid 熊/基/牛估值 payload 被整包丟棄或遺失估值推論；RED→GREEN structured-output price-target reasoning safe-text 單測與文件契約更新通過。

- D1305：P3-1199 補強 structured-output normalizer moat analysis markdown prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 3/12 護城河 schema validation 前先用 shared safe text 正規化 `analysis_markdown`，將 malformed 護城河正文降級為 `資料不足`，避免單一壞正文欄位讓 otherwise valid moat score payload 被整包丟棄；RED→GREEN structured-output moat body safe-text 單測與文件契約更新通過。

- D1306：P3-1200 補強 structured-output normalizer recommendation text prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前先用 shared safe text 正規化 recommendation 目標價、長期潛力與信心指數欄位，將 malformed target / potential / confidence 降級為 `N/A`，避免單一壞文字欄位讓 otherwise valid investment recommendation payload 被整包丟棄；RED→GREEN structured-output recommendation safe-text 單測與文件契約更新通過。

- D1307：P3-1201 補強 structured-output normalizer next-catalyst text prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 schema validation 前先用 shared safe text 正規化 `next_catalysts` 的 event、timeframe、impact 與 trigger 欄位，將 malformed catalyst event 降級為 `待確認催化事件`、缺失 timeframe / trigger 降級為 `待後續資料確認`，避免單一壞催化事件欄位讓 otherwise valid recommendation payload 被整包丟棄；RED→GREEN structured-output next-catalyst safe-text 單測與文件契約更新通過。

- D1308：P3-1202 補強 structured-output normalizer valuation-summary text prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 4/14 目標價 schema validation 前先用 shared safe text 正規化 `valuation_summary.primary_method` 與 `double_counting_check`，將 malformed valuation method 回落到 `blended`、壞 double-counting check 降級為 `資料不足`，避免單一估值摘要文字欄位讓 otherwise valid 熊/基/牛目標價 payload 被整包丟棄；RED→GREEN structured-output valuation-summary safe-text 單測與文件契約更新通過。

- D1309：P3-1203 補強 structured-output normalizer DCF scenario prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 4/14 目標價 schema validation 前先用 shared safe dict-list 與 finite-number conversion 正規化 `dcf_scenarios`，跳過 malformed scenario rows 並保留有效 DCF scenario，避免單一壞 DCF 數字欄位讓 otherwise valid 熊/基/牛目標價 payload 被整包丟棄；RED→GREEN structured-output DCF scenario safe-number 單測與文件契約更新通過。

- D1310：P3-1204 補強 structured-output normalizer valuation-summary boolean prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 4/14 目標價 schema validation 前先用 bool-safe conversion 正規化 `valuation_summary.uses_market_value_wacc` 與 `uses_normalized_fcf`，將 malformed WACC / normalized-FCF flags 保守回落為 `False` 並保留有效目標價 payload，避免單一壞布林欄位讓 otherwise valid 熊/基/牛目標價 payload 被整包丟棄；RED→GREEN structured-output valuation-summary bool-safe 單測與文件契約更新通過。

- D1311：P3-1205 補強 structured-output normalizer management-sentiment highlight row fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 20 管理層語氣 schema validation 前用 sequence-safe conversion 正規化 `highlights`，遇到 malformed highlight row 時以 `亮點` / `資料不足` 明確占位並保留其他有效 highlights，避免單一壞 highlight row 讓 otherwise valid management sentiment payload 被整包丟棄；RED→GREEN structured-output management highlight-row 單測與文件契約更新通過。

- D1312：P3-1206 補強 structured-output normalizer downside-risk row fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 21 下行風險 schema validation 前用 sequence-safe conversion 正規化 `downside_risks`，遇到 malformed risk row 時以 `下行風險` / `資料不足` / `warning` 明確占位；後續 D1326 將 fallback row 延後到 minimum-count repair，避免單一壞風險列讓 otherwise valid downside risk payload 掉到 required row count 以下而整包失效，同時不讓 placeholder 擠掉有效風險；RED→GREEN structured-output downside-risk row 單測與文件契約更新通過。

- D1313：P3-1207 補強 structured-output normalizer scenario-trigger row fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前用 sequence-safe conversion 正規化 `scenario_triggers`，遇到 non-mapping malformed trigger row 時以 `待後續資料確認觸發條件` / `重新檢查投資結論` / `neutral_review` 明確占位；當有效 trigger 已足夠時仍保留壞欄位 skip 行為，避免單一壞 trigger row 讓 otherwise valid recommendation payload 掉到 required trigger count 以下而整包失效；RED→GREEN structured-output scenario-trigger row 單測與文件契約更新通過。

- D1314：P3-1208 補強 structured-output normalizer confidence-basis minimum fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，對 `confidence_basis.evidence_items` 與 `key_risks_acknowledged` 先保留可安全轉文字的有效項目，若原始 list/tuple 中有項目但安全轉換後低於 schema required count，分別補 `待補具體佐證` 與 `待補已納入風險` placeholder；`data_gaps` 維持可空清單，避免單一壞信心依據項目讓 otherwise valid recommendation payload 整包失效；RED→GREEN structured-output confidence-basis minimum fallback 單測與文件契約更新通過。

- D1315：P3-1209 補強 structured-output normalizer reasoning-step minimum fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 3/12/7/16/19 schema validation 前，對 `reasoning_steps` 先保留可安全轉成單行文字的有效步驟，若原始 list/tuple 中有項目但安全轉換後低於 schema required count，補 `待補推論步驟` placeholder，避免單一壞推論步驟讓 otherwise valid structured payload 掉到 required reasoning-step count 以下而整包失效；RED→GREEN structured-output reasoning-step minimum fallback 單測與文件契約更新通過。

- D1316：P3-1210 補強 structured-output normalizer next-catalyst row fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，用 sequence-safe conversion 正規化 `next_catalysts`，遇到 non-mapping malformed catalyst row 時以 `待確認催化事件` / `待後續資料確認` / `volatile` / `待後續資料確認` 明確占位；後續 D1327 將 fallback row 延後到 minimum-count repair，避免單一壞催化事件列讓 otherwise valid recommendation payload 掉到 required catalyst count 以下而整包失效，同時不讓 placeholder 排在有效 catalyst 前；RED→GREEN structured-output next-catalyst row 單測與文件契約更新通過。

- D1317：P3-1211 補強 structured-output normalizer moat-score prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 3/12 護城河 schema validation 前，對 `moat_scores` 先以 1-10 safe number fallback 補齊 schema 必要欄位，讓單一 malformed score value 不會讓 otherwise valid moat payload 整包失效；schema 後輸出仍回看 raw payload 並排除壞 score，避免 fallback placeholder 污染最終護城河評分；RED→GREEN structured-output moat-score prevalidation 單測與文件契約更新通過。

- D1318：P3-1212 補強 structured-output normalizer management-confidence prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 20 管理層語氣 schema validation 前，對 `confidence` 先以 0-1 safe number fallback 正規化，讓單一 malformed confidence value 不會讓 otherwise valid management sentiment payload 整包失效；schema 後輸出仍回看 raw confidence 並排除壞值或布林旗標，避免 fallback 污染最終信心分數；RED→GREEN structured-output management-confidence prevalidation 單測與文件契約更新通過。

- D1319：P3-1213 補強 structured-output normalizer downside-risk confidence prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 21 下行風險 schema validation 前，對每列 `downside_risks[].confidence` 先以 0-1 safe number fallback 正規化，讓單一 malformed risk confidence value 不會讓 otherwise valid downside risk payload 整包失效；schema 後輸出仍回看 raw confidence 並排除壞值或布林旗標，同時保留有效 `0.0` 低信心訊號；RED→GREEN structured-output downside-risk-confidence prevalidation 單測與文件契約更新通過。

- D1320：P3-1214 補強 structured-output normalizer trade-plan enum prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 24 極短線交易計畫 schema validation 前，對 `trade_direction` 與 `risk_level` 做 Literal-safe fallback，非法交易方向降為 `Neutral`、非法風險等級降為 `High`，避免單一 enum 漂移讓 otherwise valid 1-2 週交易計畫整包失效；RED→GREEN structured-output trade-plan enum prevalidation 單測與文件契約更新通過。

- D1321：P3-1215 補強 structured-output normalizer price-target value prevalidation fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 4/14 目標價 schema validation 前，對熊市、基本、牛市目標價先以非負 safe number fallback 補齊 required fields，讓單一 malformed target value 不會讓 otherwise valid bear/base/bull valuation payload 整包失效；schema 後輸出仍回看 raw target values 並排除壞值或布林旗標，避免 fallback placeholder 污染最終目標價；RED→GREEN structured-output price-target prevalidation 單測與文件契約更新通過。

- D1322：P3-1216 補強 structured-output normalizer scenario-trigger field minimum fallback：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，對 `scenario_triggers` 的 mapping row 先保留有效 trigger；若原始 trigger row 數已達 schema 最低需求但壞 `trigger_condition` / `action` 欄位讓有效列數掉到 required trigger count 以下，才用 `待後續資料確認觸發條件` / `重新檢查投資結論` placeholder 補回最低筆數，避免 otherwise valid recommendation payload 因單一壞 trigger 欄位整包失效，同時避免在有效 trigger 已足夠時把 placeholder 推進最終報告；RED→GREEN structured-output scenario-trigger field minimum 單測與文件契約更新通過。

- D1323：P3-1217 補強 structured-output normalizer scenario-trigger schema-limit truncation：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，將 `scenario_triggers` 正規化結果截到 schema 上限 5 筆，保留最前面的觸發條件順序，避免 LLM 多給第 6 筆 valid trigger 時讓 otherwise valid recommendation payload 因 `max_length=5` 整包失效；RED→GREEN structured-output overlong scenario-trigger 單測與文件契約更新通過。

- D1324：P3-1218 補強 structured-output normalizer scenario-trigger fallback priority：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，將 non-mapping trigger row 與壞 `trigger_condition` / `action` 欄位都先放入 fallback queue；只有有效 trigger 低於 schema 最低 2 筆時才補 placeholder，避免 overlong trigger list 截到 5 筆時讓 `待後續資料確認觸發條件` 這類 placeholder 擠掉後方有效觸發條件；RED→GREEN structured-output scenario-trigger fallback priority 單測與文件契約更新通過。

- D1325：P3-1219 補強 structured-output normalizer management-highlight fallback priority：`structured_output_normalizer.normalize_structured_output()` 在 Agent 20 管理層語氣 schema validation 前，將 malformed highlight row 或壞 keyword/quote 欄位先放入 fallback queue；只有有效管理層亮點低於固定 3 筆時才補 `亮點` / `資料不足` placeholder，避免前置壞 row 讓 placeholder 擠掉後方有效管理層亮點；RED→GREEN structured-output management-highlight fallback priority 單測與文件契約更新通過。

- D1326：P3-1220 補強 structured-output normalizer downside-risk fallback priority：`structured_output_normalizer.normalize_structured_output()` 在 Agent 21 下行風險 schema validation 前，將 malformed downside-risk row 或壞 title/evidence 欄位先放入 fallback queue；只有有效下行風險低於 schema 最低 3 筆時才補 `下行風險` / `資料不足` placeholder，並讓後處理信任已正規化 row 的 confidence，避免前置壞 row 擠掉後方有效風險或造成 confidence index 錯位；RED→GREEN structured-output downside-risk fallback priority 單測與文件契約更新通過。

- D1327：P3-1221 補強 structured-output normalizer next-catalyst fallback priority：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，將 malformed next-catalyst row 或壞 event/timeframe/trigger 欄位先放入 fallback queue；只有沒有有效 catalyst 時才補 `待確認催化事件` / `待後續資料確認` placeholder，避免報告的催化事件清單在已有有效催化事件時仍先顯示 placeholder；RED→GREEN structured-output next-catalyst fallback priority 單測與文件契約更新通過。

- D1328：P3-1222 補強 structured-output schema-derived next-catalyst safe trigger：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 自動從 `scenario_triggers` 補 `next_catalysts` 前，先用 safe text 清理 trigger condition/action/direction 並跳過壞列，避免 direct model validation 遇到 malformed trigger row 時以 runtime exception 中斷，且在足夠有效 trigger 存在時仍能產生有效催化事件；RED→GREEN schema-derived next-catalyst 單測與文件契約更新通過。

- D1329：P3-1223 補強 structured-output normalizer next-catalyst trigger length guard：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，將可轉文字但短於 Catalyst schema `trigger_condition` 最低長度的 next-catalyst row 放入 fallback queue；當後方已有有效 catalyst 時不讓短 trigger 片段進最終清單，避免 otherwise valid recommendation payload 因單一太短 trigger 被整包丟棄；RED→GREEN structured-output next-catalyst trigger-length 單測與文件契約更新通過。

- D1330：P3-1224 補強 structured-output normalizer scenario-trigger length guard：`structured_output_normalizer.normalize_structured_output()` 在 Agent 7/16/19 投資建議 schema validation 前，將可轉文字但短於 ScenarioTrigger schema `trigger_condition` / `action` 最低長度的 trigger row 放入 fallback queue；當後方已有足夠有效 trigger 時不讓短片段進最終清單，避免 otherwise valid recommendation payload 因單一太短情境觸發器被整包丟棄；RED→GREEN structured-output scenario-trigger length 單測與文件契約更新通過。

- D1331：P3-1225 補強 structured-output normalizer scenario-trigger fallback schema-safe text：`structured_output_normalizer.normalize_structured_output()` 在有效 trigger 不足、需要用 fallback row 補滿 ScenarioTrigger schema 最低 2 筆時，將太短的 `trigger_condition` / `action` 改為 schema-safe placeholder，而不是把太短原文重新塞回 validation；避免 minimum-count repair 自己產生仍不合 schema 的 fallback row；RED→GREEN structured-output scenario-trigger fallback-safe-text 單測與文件契約更新通過。

- D1332：P3-1226 補強 structured-output normalizer next-catalyst fallback schema-safe trigger：`structured_output_normalizer.normalize_structured_output()` 在有效 next catalyst 不足、需要用 fallback row 補滿 Catalyst schema 最低 1 筆時，將太短的 `trigger_condition` 改為 `待後續資料確認`，而不是把太短原文重新塞回 validation；避免 minimum-count repair 自己產生仍不合 schema 的 catalyst row；RED→GREEN structured-output next-catalyst fallback-safe-trigger 單測與文件契約更新通過。

- D1333：P3-1227 補強 structured-output schema-derived next-catalyst trigger length guard：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 自動從 `scenario_triggers` 補 `next_catalysts` 前，先套用 ScenarioTrigger schema 的 `trigger_condition` / `action` 最短長度門檻，避免 direct model validation 遇到太短但非空的情境觸發器時讓 otherwise valid scenario triggers 與自動產生的 catalyst watchlist 被整包丟棄；RED→GREEN schema-derived next-catalyst length 單測與文件契約更新通過。

- D1334：P3-1228 補強 structured-output schema-derived next-catalyst root Mapping guard：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 入口先用 shared mapping-safe conversion 接受 read-only / immutable structured payload，並用 dict-list safe conversion 讀取 `scenario_triggers`，避免 direct model validation 遇到 `MappingProxyType` root payload 時跳過自動 catalyst watchlist 生成，讓有效 scenario triggers 不會留下空的 `next_catalysts`；RED→GREEN schema-derived root-mapping 單測與文件契約更新通過。

- D1335：P3-1229 補強 structured-output schema-derived next-catalyst null fallback：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 自動派生 `next_catalysts` 時，將 `next_catalysts: null` 視為缺少可用 catalyst list，並從有效 `scenario_triggers` 產生 catalyst watchlist；保留空清單 `[]` 的既有 required-field 驗證，避免模型明確給空清單時被默默放寬；RED→GREEN schema-derived null-catalyst 單測與文件契約更新通過。

- D1336：P3-1230 補強 structured-output schema-derived next-catalyst non-list fallback：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 自動派生 `next_catalysts` 時，將字串等非 list/tuple 的 malformed `next_catalysts` 視為不可用 catalyst payload，改從有效 `scenario_triggers` 產生 catalyst watchlist；仍保留空清單 `[]` 的 required-field 驗證，避免模型明確給空清單時被默默放寬；RED→GREEN schema-derived non-list-catalyst 單測與文件契約更新通過。

- D1337：P3-1231 補強 structured-output schema-derived next-catalyst non-mapping-row fallback：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 自動派生 `next_catalysts` 時，若 `next_catalysts` 是非空 list/tuple 但沒有任何 mapping row，視為 malformed catalyst-list contents，改從有效 `scenario_triggers` 產生 catalyst watchlist；空清單 `[]` 仍保留 required-field 驗證，避免模型明確給空清單時被默默放寬；RED→GREEN schema-derived non-mapping-catalyst-row 單測與文件契約更新通過。

- D1338：P3-1232 補強 structured-output schema-derived next-catalyst mixed-row preservation：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 入口先用 dict-list safe conversion 正規化既有 `next_catalysts`，當 list 裡混有 malformed row 與有效 mapping catalyst row 時，保留有效 catalyst watchlist items 並丟棄壞 row，而不是讓單一壞 row 拖垮 otherwise valid recommendation payload；RED→GREEN schema-derived mixed-catalyst-row 單測與文件契約更新通過。

- D1339：P3-1233 補強 structured-output schema-derived next-catalyst invalid mapping-row filtering：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 入口對既有 `next_catalysts` mapping rows 套用 Catalyst schema-safe 欄位過濾，丟棄 trigger 太短、impact_direction 非白名單或必要文字缺漏的 catalyst row，保留後方有效 catalyst watchlist items；若整包 catalyst rows 都不可用且 `scenario_triggers` 有效，仍可派生 fallback catalysts；RED→GREEN schema-derived mixed-mapping-row 單測與文件契約更新通過。

- D1340：P3-1234 補強 structured-output schema-derived next-catalyst overlong scenario-trigger truncation：`structured_output_models` 在 Recommendation / Bubble Sniper schema model validator 入口收集安全 `scenario_triggers` 時先套用 schema 的 5 筆上限，避免模型輸出第 6 筆有效 trigger 時讓 direct model validation 因 `max_length` 失敗，並保留前 5 筆 trigger 與前 3 筆自動派生 catalyst watchlist；RED→GREEN schema-derived overlong-trigger 單測與文件契約更新通過。

- D1341：P3-1235 補強 structured-output confidence-basis direct safe-text filtering：`structured_output_models` 在 Recommendation / Bubble Sniper 共用的 `ConfidenceBasis` schema model validator 入口，先用 shared safe text list conversion 過濾 evidence、risk、data-gap list 中的 malformed item，避免單一不可字串化項目讓 otherwise valid confidence basis 與整份 recommendation payload 被丟棄；仍保留 evidence 至少 3 筆、risk 至少 2 筆的 schema 品質門檻；RED→GREEN direct confidence-basis 單測與文件契約更新通過。

- D1342：P3-1236 補強 structured-output reasoning-step direct safe-text filtering：`structured_output_models` 新增 Recommendation / Bubble Sniper 共用的 `ReasoningStepsMixin`，在 direct model validation 前只對 list/tuple 型 `reasoning_steps` 套用 shared safe text list conversion，讓單一 malformed reasoning-step item 不會丟掉 otherwise valid recommendation payload；仍保留至少 3 筆 reasoning steps 的 schema 品質門檻；RED→GREEN direct reasoning-step 單測與文件契約更新通過。

- D1343：P3-1237 補強 structured-output recommendation-label direct alias normalization：`structured_output_models` 在 Recommendation / Bubble Sniper recommendation fields schema model validator 入口復用 product-wide `normalize_recommendation_label()`，先把「強烈放空」「strong short」「強烈買入」等 alias 收斂到 canonical labels，再交給 Literal schema 驗證，避免強語氣 recommendation alias 丟掉 otherwise valid recommendation payload；RED→GREEN direct recommendation-label 單測與文件契約更新通過。

- D1344：P3-1238 補強 structured-output recommendation text-field direct fallback：`structured_output_models` 在 Recommendation / Bubble Sniper recommendation fields schema model validator 入口，對短中長期目標、五年潛力與信心指數欄位套用 safe text fallback，讓單一 malformed target/potential/confidence display value 以 `N/A` 保留報告骨架，而不是讓 otherwise valid investment recommendation payload 被 schema validation 丟棄；RED→GREEN direct recommendation-text-field 單測與文件契約更新通過。

- D1345：P3-1239 補強 structured-output analysis-markdown direct fallback：`structured_output_models` 在 Recommendation / Bubble Sniper 共用 schema mixin 入口，對 direct `analysis_markdown` 套用 safe text fallback，將 malformed 或空白報告正文降級為 `資料不足`，避免單一壞正文欄位讓 otherwise valid structured recommendation payload 被 schema validation 丟棄；RED→GREEN direct analysis-markdown 單測與文件契約更新通過。

- D1346：P3-1240 補強 structured-output moat analysis-markdown direct fallback：`structured_output_models` 將既有 `AnalysisMarkdownMixin` 提前成 Moat / Recommendation / Bubble Sniper 可共用的 direct schema 前置清理，讓 `MoatStructuredOutput` 在 model validation 前把 malformed 或空白 `analysis_markdown` 降級為 `資料不足`，避免單一壞護城河正文欄位讓 otherwise valid moat score payload 被丟棄；RED→GREEN direct moat-analysis-markdown 單測與文件契約更新通過。

- D1347：P3-1241 補強 structured-output price-target analysis-markdown direct fallback：`structured_output_models` 讓 `PriceTargetStructuredOutput` 共用 `AnalysisMarkdownMixin`，在 direct model validation 前把 malformed 或空白 `analysis_markdown` 降級為 `資料不足`，避免單一壞估值正文欄位讓 otherwise valid 熊/基/牛目標價 payload 被 schema validation 丟棄；RED→GREEN direct price-target-analysis-markdown 單測與文件契約更新通過。

- D1348：P3-1242 補強 structured-output management-sentiment analysis-markdown direct fallback：`structured_output_models` 讓 `ManagementSentimentStructuredOutput` 共用 `AnalysisMarkdownMixin`，在 direct model validation 前把 malformed 或空白 `analysis_markdown` 降級為 `資料不足`，避免單一壞管理層正文欄位讓 otherwise valid guidance tone、confidence 與 highlights payload 被 schema validation 丟棄；RED→GREEN direct management-analysis-markdown 單測與文件契約更新通過。

- D1349：P3-1243 補強 structured-output downside-risk analysis-markdown direct fallback：`structured_output_models` 讓 `BearAdvocateStructuredOutput` 共用 `AnalysisMarkdownMixin`，在 direct model validation 前把 malformed 或空白 `analysis_markdown` 降級為 `資料不足`，避免單一壞空方風險正文欄位讓 otherwise valid thesis summary 與 downside risks payload 被 schema validation 丟棄；RED→GREEN direct downside-risk-analysis-markdown 單測與文件契約更新通過。

- D1350：P3-1244 補強 structured-output management-sentiment text-field direct fallback：`structured_output_models` 在 direct `ManagementSentimentStructuredOutput` validation 前，將 malformed 或非白名單 `guidance_tone` 降級為 `資料不足`，並將 highlight `keyword` / `quote` 的 malformed 文字欄位分別降級為 `亮點` / `資料不足`，避免單一壞管理層文字欄位讓 otherwise valid management sentiment payload 被 schema validation 丟棄；RED→GREEN direct management-sentiment text-field 單測與文件契約更新通過。

- D1351：P3-1245 補強 structured-output downside-risk text-field direct fallback：`structured_output_models` 在 direct `BearAdvocateStructuredOutput` validation 前，將 malformed `thesis_summary` 降級為 `資料不足`，並將 downside risk `title` / `evidence` / `impact` / `severity` 的 malformed 文字欄位分別降級為 `下行風險` / `資料不足` / 空字串 / `warning`，避免單一壞空方文字欄位讓 otherwise valid downside-risk payload 被 schema validation 丟棄；RED→GREEN direct downside-risk text-field 單測與文件契約更新通過。

- D1352：P3-1246 補強 structured-output price-target text-field direct fallback：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，將 malformed `dcf_reasoning` / `peer_reasoning` / `scenario_reasoning` 與 `double_counting_check` 降級為 `資料不足`，並將 malformed 或非白名單 `primary_method` 降級為 `blended`，避免單一壞估值文字欄位讓 otherwise valid 熊/基/牛目標價 payload 被 schema validation 丟棄；RED→GREEN direct price-target text-field 單測與文件契約更新通過。

- D1353：P3-1247 補強 structured-output trade-plan text-field direct fallback：`structured_output_models` 在 direct `SwingTradeSetup` validation 前，將 malformed 或非白名單 `trade_direction` 降級為 `Neutral`，將 malformed `entry_zone` / `target_price` / `stop_loss` / `core_catalyst` 降級為 `N/A`，並將 malformed 或非白名單 `risk_level` 降級為 `High`，避免單一壞短線交易計畫欄位讓 otherwise valid 1-2 week trade setup payload 被 schema validation 丟棄；RED→GREEN direct trade-plan text-field 單測與文件契約更新通過。

- D1354：P3-1248 補強 structured-output price-target valuation-summary boolean direct fallback：`structured_output_models` 在 direct `ValuationSummary` validation 前，將 malformed `uses_market_value_wacc` / `uses_normalized_fcf` 以 bool-safe 規則降級為 `False`，並保留有效布林值，避免單一壞 WACC 或 normalized-FCF 旗標讓 otherwise valid 熊/基/牛目標價 payload 被 schema validation 丟棄；RED→GREEN direct valuation-summary boolean 單測與文件契約更新通過。

- D1355：P3-1249 補強 structured-output price-target numeric direct fallback：`structured_output_models` 在 direct `PriceTargets` validation 前，將 malformed 或非有限 `熊市情境` / `基本情境` / `牛市情境` 目標價以 safe number 規則降級為 `0.0`，並保留有效數字，避免單一壞目標價欄位讓 otherwise valid 估值 payload 被 schema validation 丟棄；RED→GREEN direct price-target numeric 單測與文件契約更新通過。

- D1356：P3-1250 補強 structured-output moat-score numeric direct fallback：`structured_output_models` 在 direct `MoatScores` validation 前，將 malformed 或非有限 `品牌影響力` / `網路效應` / `轉換成本` / `成本優勢` / `專利技術` / `整體護城河` 分數以 safe number 規則降級為 schema-safe `1.0`，並將可轉換分數限制在 1-10，避免單一壞護城河分數讓 otherwise valid moat payload 被 schema validation 丟棄；RED→GREEN direct moat-score numeric 單測與文件契約更新通過。

- D1357：P3-1251 補強 structured-output management-confidence numeric direct fallback：`structured_output_models` 在 direct `ManagementSentimentStructuredOutput` validation 前，將 malformed 或非有限 `confidence` 以 safe number 規則降級為 `0.0`，並將可轉換信心分數限制在 0-1，避免單一壞管理層信心值讓 otherwise valid guidance tone、highlights 與正文 payload 被 schema validation 丟棄；RED→GREEN direct management-confidence numeric 單測與文件契約更新通過。

- D1358：P3-1252 補強 structured-output downside-risk confidence numeric direct fallback：`structured_output_models` 在 direct `DownsideRisk` validation 前，將 malformed 或非有限 `confidence` 以 safe number 規則降級為 schema 預設 `0.7`，並將可轉換風險信心值限制在 0-1，避免單一壞下行風險信心值讓 otherwise valid thesis summary、risk list 與正文 payload 被 schema validation 丟棄；RED→GREEN direct downside-risk confidence numeric 單測與文件契約更新通過。

- D1359：P3-1253 補強 structured-output DCF scenario numeric direct fallback：`structured_output_models` 在 direct `DcfScenarioOutput` validation 前，將 malformed 或非有限 `revenue_growth_bias_pct` / `margin_bias_pct` / `wacc_pct` / `intrinsic_value` 以 safe number 規則降級為 schema-safe 數值，其中 `wacc_pct` 回落為大於 0 的 `1.0`、`intrinsic_value` 保持非負，避免單一壞 DCF scenario 數字欄位讓 otherwise valid 熊/基/牛估值 payload 被 schema validation 丟棄；RED→GREEN direct DCF scenario numeric 單測與文件契約更新通過。

- D1360：P3-1254 補強 structured-output management-highlight row direct fallback：`structured_output_models` 在 direct `ManagementSentimentStructuredOutput` validation 前逐列正規化 `highlights`，遇到 malformed highlight row 時以 `亮點` / `資料不足` 明確占位並保留其他有效管理層亮點，避免單一壞 highlight row 讓 otherwise valid management sentiment payload 被 schema validation 丟棄；RED→GREEN direct management-highlight row 單測與文件契約更新通過。

- D1361：P3-1255 補強 structured-output downside-risk row direct fallback：`structured_output_models` 在 direct `BearAdvocateStructuredOutput` validation 前逐列正規化 `downside_risks`，遇到 malformed risk row 時以 `下行風險` / `資料不足` / `warning` / `0.7` 明確占位並保留其他有效下行風險，避免單一壞 risk row 讓 otherwise valid downside-risk payload 被 schema validation 丟棄；RED→GREEN direct downside-risk row 單測與文件契約更新通過。

- D1362：P3-1256 補強 structured-output confidence-basis minimum direct fallback：`structured_output_models` 在 direct `ConfidenceBasis` validation 前，對 `evidence_items` 與 `key_risks_acknowledged` 先用 safe text conversion 保留有效項目；若原始 list/tuple 非空但壞項目使有效筆數低於 schema 最低需求，分別補 `待補具體佐證` 與 `待補已納入風險`，避免單一壞信心依據項目讓 otherwise valid recommendation payload 被 schema validation 丟棄；RED→GREEN direct confidence-basis minimum 單測與文件契約更新通過。

- D1363：P3-1257 補強 structured-output reasoning-step minimum direct fallback：`structured_output_models` 在 direct `ReasoningStepsMixin` validation 前，對 `reasoning_steps` 先用 safe text conversion 保留有效推論步驟；若原始 list/tuple 非空但壞 step 使有效筆數低於 schema 最低 3 筆，補 `待補推論步驟` placeholder，避免單一壞 reasoning step 讓 otherwise valid recommendation payload 被 schema validation 丟棄；RED→GREEN direct reasoning-step minimum 單測與文件契約更新通過。

- D1364：P3-1258 補強 structured-output scenario-trigger minimum direct fallback：`structured_output_models` 在 Recommendation / Bubble Sniper direct schema validation 與 next-catalyst derivation 前，對 `scenario_triggers` 先保留 schema-safe 有效 trigger，並把 malformed 或太短欄位放入 fallback queue；若原始 list/tuple 至少 2 筆但有效 trigger 低於 schema 最低 2 筆，補 `待後續資料確認觸發條件` / `重新檢查投資結論` / `neutral_review` placeholder，避免單一壞情境觸發器讓 otherwise valid recommendation payload 被 schema validation 丟棄；RED→GREEN direct scenario-trigger minimum 單測與文件契約更新通過。

- D1365：P3-1259 補強 structured-output moat reasoning-step minimum direct fallback：`structured_output_models` 在 direct `MoatStructuredOutput` validation 前，對 `reasoning_steps` 先用 safe text conversion 保留有效護城河推論步驟；若原始 list/tuple 非空但壞 step 使有效筆數低於 schema 最低 3 筆，補 `待補推論步驟` placeholder，避免單一壞 moat reasoning step 讓 otherwise valid moat score payload 被 schema validation 丟棄；RED→GREEN direct moat reasoning-step minimum 單測與文件契約更新通過。

- D1366：P3-1260 補強 structured-output DCF scenario row direct filtering：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，對 `dcf_scenarios` 先用 sequence-safe / mapping-safe conversion 保留有效 DCF scenario rows、跳過 malformed row 並套用 schema 上限 3 筆，避免單一壞 DCF scenario row 讓 otherwise valid price-target payload 或後方有效 scenario rows 被 schema validation 丟棄；RED→GREEN direct DCF scenario row 單測與文件契約更新通過。

- D1367：P3-1261 補強 structured-output DCF scenario enum direct filtering：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，對 `dcf_scenarios[*].scenario` 先用 safe text 正規化並限制在 `bear` / `base` / `bull`，跳過 `upside` 等 invalid scenario row，避免單一壞 DCF scenario 名稱讓 otherwise valid price-target payload 或後方有效 scenario rows 被 schema validation 丟棄；RED→GREEN direct DCF scenario enum 單測與文件契約更新通過。

- D1368：P3-1262 補強 structured-output DCF scenario collection direct fallback：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，對 malformed scalar / non-list `dcf_scenarios` 容器回落為空清單，避免模型把 DCF scenario collection 輸出成單一物件或不可迭代值時，拖垮 otherwise valid price-target payload；RED→GREEN direct DCF scenario collection 單測與文件契約更新通過。

- D1369：P3-1263 補強 structured-output valuation-summary container direct fallback：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，對 malformed scalar `valuation_summary` 容器回落為空 mapping，交由既有 `ValuationSummary` 欄位 fallback 補 `blended`、bool-safe `False` 與 `資料不足` double-counting check，避免單一壞 valuation summary 容器拖垮 otherwise valid price-target payload；RED→GREEN direct valuation-summary container 單測與文件契約更新通過。

- D1370：P3-1264 補強 structured-output price-target container direct fallback：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，對 malformed scalar `price_targets` 容器回落為空 mapping，交由既有 `PriceTargets` 欄位 fallback 補 valuation reasoning `資料不足` 與熊/基/牛目標價 `0.0`，避免單一壞 price-target 容器拖垮 otherwise valid valuation summary 或正文 payload；RED→GREEN direct price-target container 單測與文件契約更新通過。

- D1371：P3-1265 補強 structured-output moat-score container direct fallback：`structured_output_models` 在 direct `MoatScores` validation 前，對 malformed scalar `moat_scores` 容器回落為空 mapping，交由既有 moat score 欄位 fallback 補六項 schema-safe `1.0` 分數，避免單一壞 moat-score 容器拖垮 otherwise valid moat reasoning steps 或正文 payload；RED→GREEN direct moat-score container 單測與文件契約更新通過。

- D1372：P3-1266 補強 structured-output management-highlight collection direct fallback：`structured_output_models` 在 direct `ManagementSentimentStructuredOutput` validation 前，對 malformed scalar `highlights` 容器回落為三列 `亮點` / `資料不足` placeholder，避免單一壞 highlight collection 拖垮 otherwise valid guidance tone、confidence 與正文 payload；RED→GREEN direct management-highlight collection 單測與文件契約更新通過。

- D1373：P3-1267 補強 structured-output management-highlight minimum direct fallback：`structured_output_models` 在 direct `ManagementSentimentStructuredOutput` validation 前，對非空但低於三列的 `highlights` list 保留有效管理層亮點並補足 `亮點` / `資料不足` placeholder 到 schema 最低 3 筆，避免短 highlight collection 拖垮 otherwise valid guidance tone、confidence 與正文 payload；RED→GREEN direct management-highlight minimum 單測與文件契約更新通過。

- D1374：P3-1268 補強 structured-output downside-risk collection direct fallback：`structured_output_models` 在 direct `BearAdvocateStructuredOutput` validation 前，對 malformed scalar `downside_risks` 容器回落為三列 `下行風險` / `資料不足` / `warning` / `0.7` placeholder，避免單一壞 downside-risk collection 拖垮 otherwise valid thesis summary 與正文 payload；RED→GREEN direct downside-risk collection 單測與文件契約更新通過。

- D1375：P3-1269 補強 structured-output downside-risk minimum direct fallback：`structured_output_models` 在 direct `BearAdvocateStructuredOutput` validation 前，對非空但低於三列的 `downside_risks` list 保留有效下行風險並補足 `下行風險` / `資料不足` / `warning` / `0.7` placeholder 到 schema 最低 3 筆，避免短 downside-risk collection 拖垮 otherwise valid thesis summary 與正文 payload；RED→GREEN direct downside-risk minimum 單測與文件契約更新通過。

- D1376：P3-1270 補強 structured-output trade-plan root direct fallback：`structured_output_models` 在 direct `SwingTradeSetup` validation 前，對 malformed scalar root payload 回落為 `Neutral` / `N/A` / `High` 的 schema-safe 1-2 week trade setup，避免整個短線交易計畫 payload 非 mapping 時直接被 schema validation 丟棄；RED→GREEN direct trade-plan root 單測與文件契約更新通過。

- D1377：P3-1271 補強 structured-output management-sentiment root direct fallback：`structured_output_models` 在 direct `ManagementSentimentStructuredOutput` validation 前，對 malformed scalar root payload 回落為 `資料不足` / `0.0` / 三列 `亮點` placeholder 的 schema-safe 管理層情緒區塊，避免整個 management sentiment payload 非 mapping 時直接被 schema validation 丟棄；RED→GREEN direct management-sentiment root 單測與文件契約更新通過。

- D1378：P3-1272 補強 structured-output downside-risk root direct fallback：`structured_output_models` 在 direct `BearAdvocateStructuredOutput` validation 前，對 malformed scalar root payload 回落為 `資料不足` thesis summary、三列 `下行風險` placeholder 與 `資料不足` 正文，避免整個 downside-risk payload 非 mapping 時直接被 schema validation 丟棄；RED→GREEN direct downside-risk root 單測與文件契約更新通過。

- D1379：P3-1273 補強 structured-output price-target root direct fallback：`structured_output_models` 在 direct `PriceTargetStructuredOutput` validation 前，對 malformed scalar root payload 回落為空 `price_targets` / `valuation_summary`、空 DCF scenario list 與 `資料不足` 正文，交由既有欄位 fallback 補 `資料不足` valuation reasoning、`blended` 方法、bool-safe `False` 與 0.0 熊/基/牛目標價，避免整個估值 payload 非 mapping 時直接被 schema validation 丟棄；RED→GREEN direct price-target root 單測與文件契約更新通過。

- D1380：P3-1274 補強 structured-output moat root direct fallback：`structured_output_models` 在 direct `MoatStructuredOutput` validation 前，對 malformed scalar root payload 回落為三列 `待補推論步驟`、空 `moat_scores` 與 `資料不足` 正文，交由既有 moat score 欄位 fallback 補六項 schema-safe 1.0 分數，避免整個護城河 payload 非 mapping 時直接被 schema validation 丟棄；RED→GREEN direct moat root 單測與文件契約更新通過。

- D1381：P3-1275 補強 structured-output recommendation root direct fallback：`structured_output_models` 在 direct `RecommendationStructuredOutput` validation 前，對 malformed scalar root payload 回落為保守 `持有` 建議、`N/A` 目標價、三列 `待補推論步驟`、最低 confidence basis、兩列 neutral scenario triggers、單列 derived catalyst 與 `資料不足` 正文，避免整個主投資建議 payload 非 mapping 時直接被 schema validation 丟棄；RED→GREEN direct recommendation root 單測與文件契約更新通過。

- D1382：P3-1276 補強 structured-output bubble-sniper root direct fallback：`structured_output_models` 在 direct `BubbleSniperStructuredOutput` validation 前，對 malformed scalar root payload 回落為保守 `避免` 建議、`N/A` 目標價、三列 `待補推論步驟`、最低 confidence basis、兩列 neutral scenario triggers、單列 derived catalyst 與 `資料不足` 正文，避免整個泡沫/做空建議 payload 非 mapping 時直接被 schema validation 丟棄或誤給積極放空訊號；RED→GREEN direct bubble-sniper root 單測與文件契約更新通過。

- D1383：P3-1277 補強 structured-output executive-thesis root direct fallback：`structured_output_models` 在 direct `ExecutiveThesisOutput` validation 前，對 malformed scalar root payload 回落為 `資料不足` core/bull/bear thesis、空 resolved contradictions 與 `資料不足` smoothed markdown，避免整個總編輯整合 payload 非 mapping 時直接被 schema validation 丟棄並讓報告開頭核心論點消失；RED→GREEN direct executive-thesis root 單測與文件契約更新通過。

- D1384：P3-1278 補強 structured-output executive-thesis text-field direct fallback：`structured_output_models` 在 direct `ExecutiveThesisOutput` validation 前，將 malformed `core_thesis` / `bull_case_summary` / `bear_case_summary` / `smoothed_markdown` 降級為 `資料不足`，避免單一壞總編輯文字欄位讓 otherwise valid executive synthesis payload 被 schema validation 丟棄並讓報告開頭核心論點消失；RED→GREEN direct executive-thesis text-field 單測與文件契約更新通過。

- D1385：P3-1279 補強 structured-output executive-thesis resolved-contradiction direct fallback：`structured_output_models` 在 direct `ExecutiveThesisOutput` validation 前，逐項正規化 `resolved_contradictions`，保留有效矛盾說明並將 malformed 或空白項目降級為 `資料不足`，避免單一壞總編輯矛盾列讓 otherwise valid executive synthesis payload 被 schema validation 丟棄；RED→GREEN direct executive-thesis resolved-contradiction 單測與文件契約更新通過。

- D1386：P3-1280 補強 structured-output catalyst text-field direct fallback：`structured_output_models` 在 direct `Catalyst` validation 前，將 malformed `event_name` / `expected_timeframe` / `impact_direction` / `trigger_condition` 分別降級為 `待確認催化事件` / `待後續資料確認` / `volatile` / `待後續資料確認`，避免單一壞催化事件欄位讓 otherwise valid catalyst row 被 schema validation 丟棄；RED→GREEN direct catalyst text-field 單測與文件契約更新通過。

- D1387：P3-1281 補強 structured-output scenario-trigger text-field direct fallback：`structured_output_models` 在 direct `ScenarioTrigger` validation 前，將 malformed 或過短 `trigger_condition` / `action` 與 malformed 或非白名單 `direction` 分別降級為 `待後續資料確認觸發條件` / `重新檢查投資結論` / `neutral_review`，避免單一壞情境觸發欄位讓 otherwise valid scenario trigger row 被 schema validation 丟棄；RED→GREEN direct scenario-trigger text-field 單測與文件契約更新通過。

- D1388：P3-1282 補強 structured-output management-highlight root direct fallback：`structured_output_models` 在 direct `ManagementHighlight` validation 前，對 malformed scalar root payload 回落為 `亮點` / `資料不足` 的 schema-safe 管理層亮點 row，避免單一壞 highlight root 讓 otherwise valid management highlight row 被 schema validation 丟棄；RED→GREEN direct management-highlight root 單測與文件契約更新通過。

- D1389：P3-1283 補強 structured-output downside-risk root direct fallback：`structured_output_models` 在 direct `DownsideRisk` validation 前，對 malformed scalar root payload 回落為 `下行風險` / `資料不足` / `warning` / `0.7` 的 schema-safe 下行風險 row，避免單一壞 downside-risk root 讓 otherwise valid downside-risk row 被 schema validation 丟棄；RED→GREEN direct downside-risk root 單測與文件契約更新通過。

- D1390：P3-1284 補強 structured-output price-target direct target-container fallback：`structured_output_models` 在 direct `PriceTargets` validation 前，對 malformed scalar root payload 視為空 target container，回落為三段 `資料不足` 估值推論與 0.0 熊市 / 基本 / 牛市目標價，避免單一壞 price-target container 讓估值目標欄位 schema validation 直接丟棄；RED→GREEN direct price-target container 單測與文件契約更新通過。

- D1391：P3-1285 補強 structured-output price-target direct valuation-summary fallback：`structured_output_models` 在 direct `ValuationSummary` validation 前，對 malformed scalar root payload 視為空 valuation-summary container，回落為 `blended` 估值方法、兩個 bool-safe `False` 與 `資料不足` double-counting check，避免單一壞 valuation-summary container 讓估值摘要欄位 schema validation 直接丟棄；RED→GREEN direct valuation-summary container 單測與文件契約更新通過。

- D1392：P3-1286 補強 structured-output confidence-basis direct root fallback：`structured_output_models` 在 direct `ConfidenceBasis` validation 前，對 malformed scalar root payload 回落為三列 `待補具體佐證`、兩列 `待補已納入風險` 與空 `data_gaps`，避免單一壞 confidence-basis root 讓投資建議信心依據欄位 schema validation 直接丟棄；RED→GREEN direct confidence-basis root 單測與文件契約更新通過。

- D1393：P3-1287 補強 structured-output recommendation-field direct root fallback：`structured_output_models` 在 direct `RecommendationFields` validation 前，對 malformed scalar root payload 回落為保守 `持有` 建議、四個 `N/A` 目標/潛力欄位與 `N/A` 信心指數，避免單一壞 recommendation field root 讓前台投資建議欄位 schema validation 直接丟棄；RED→GREEN direct recommendation-field root 單測與文件契約更新通過。

- D1394：P3-1288 補強 structured-output bubble-sniper recommendation-field direct root fallback：`structured_output_models` 在 direct `BubbleSniperRecommendationFields` validation 前，對 malformed scalar root payload 回落為保守 `避免` 建議、四個 `N/A` 目標/潛力欄位與 `N/A` 信心指數，避免單一壞 bubble-sniper recommendation field root 讓泡沫/做空建議欄位 schema validation 直接丟棄或誤給積極放空訊號；RED→GREEN direct bubble-sniper recommendation-field root 單測與文件契約更新通過。

- D1395：P3-1289 補強 structured-output price-target direct DCF-scenario root fallback：`structured_output_models` 在 direct `DcfScenarioOutput` validation 前，對 malformed scalar root payload 回落為 `base` 情境、0.0 revenue/margin bias、1.0 WACC 與 0.0 intrinsic value，避免單一壞 DCF scenario root 讓估值三情境欄位 schema validation 直接丟棄；RED→GREEN direct DCF-scenario root 單測與文件契約更新通過。

- D1396：P3-1290 補強 structured-output recommendation reasoning-step collection fallback：`structured_output_models` 在 Recommendation / Bubble Sniper 共用的 `ReasoningStepsMixin` validation 前，對 malformed scalar `reasoning_steps` collection 回落為三列 `待補推論步驟`，避免 otherwise valid recommendation payload 因推論步驟集合不是 list 而被 schema validation 丟棄；RED→GREEN direct recommendation reasoning-step collection 單測與文件契約更新通過。

- D1397：P3-1291 補強 structured-output moat reasoning-step collection fallback：`structured_output_models` 在 direct `MoatStructuredOutput` validation 前，對 malformed scalar `reasoning_steps` collection 回落為三列 `待補推論步驟`，保留 otherwise valid moat scores 與正文，避免護城河區塊因推論步驟集合不是 list 而被 schema validation 丟棄；RED→GREEN direct moat reasoning-step collection 單測與文件契約更新通過。

- D1398：P3-1292 補強 structured-output confidence-basis required collection fallback：`structured_output_models` 在 direct `ConfidenceBasis` validation 前，對 malformed scalar `evidence_items` 與 `key_risks_acknowledged` collections 分別回落為三列 `待補具體佐證` 與兩列 `待補已納入風險`，維持 `data_gaps` 可空清單語義，避免 otherwise valid recommendation payload 因信心依據 required collection 不是 list 而被 schema validation 丟棄；RED→GREEN direct confidence-basis required collection 單測與文件契約更新通過。

- D1399：P3-1293 補強 structured-output schema-derived scenario-trigger collection fallback：`structured_output_models` 在 Recommendation / Bubble Sniper schema validation 與 next-catalyst derivation 前，對 malformed scalar `scenario_triggers` collection 回落為兩列 neutral scenario trigger，並繼續派生 schema-safe catalyst watchlist，避免 otherwise valid recommendation payload 因情境觸發器集合不是 list 而被 schema validation 丟棄；RED→GREEN direct scenario-trigger collection 單測與文件契約更新通過。

- D1400：P3-1294 補強 structured-output price-target direct DCF-scenario enum fallback：`structured_output_models` 在 direct `DcfScenarioOutput` validation 前，將 invalid 或 malformed `scenario` name 以 enum-safe 規則回落為 `base`，並保留其餘 schema-safe 數值欄位，避免單一壞 DCF scenario name 讓 direct DCF scenario row 被 schema validation 丟棄；RED→GREEN direct DCF-scenario enum 單測與文件契約更新通過。

- D1401：P3-1295 補強 structured-output shared analysis-markdown missing-field fallback：`structured_output_models` 在共用 `AnalysisMarkdownMixin` validation 前，對 otherwise valid payload 缺少 `analysis_markdown` 欄位時回落為 `資料不足`，避免單一省略正文欄位讓 Recommendation / Bubble Sniper / Moat / Price Target 等 structured section 被 schema validation 丟棄；RED→GREEN missing analysis-markdown 單測與文件契約更新通過。

- D1402：P3-1296 補強 structured-output recommendation text missing-field fallback：`structured_output_models` 在 `RecommendationFields` / `BubbleSniperRecommendationFields` 共用欄位正規化時，對缺少的短中長期目標、五年潛力與信心指數補 `N/A`，避免 otherwise valid 投資建議 payload 因單一 omitted recommendation display field 被 schema validation 丟棄；RED→GREEN missing recommendation text-field 單測與文件契約更新通過。

- D1403：P3-1297 補強 structured-output recommendation label missing-field fallback：`structured_output_models` 在 `RecommendationFields` / `BubbleSniperRecommendationFields` validation 前，對省略 `建議` label 的 otherwise valid payload 分別回落為一般投資建議 `持有` 與 Bubble Sniper `避免`，避免單一 omitted recommendation label 讓整段投資建議被 schema validation 丟棄，也避免做空/泡沫策略預設成過度積極訊號；RED→GREEN missing recommendation-label 單測與文件契約更新通過。

- D1404：P3-1298 補強 structured-output recommendation object missing-field fallback：`structured_output_models` 在 `RecommendationStructuredOutput` / `BubbleSniperStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `recommendation` 物件時分別補一般投資建議 `持有` 與 Bubble Sniper `避免` 的保守 recommendation object，並保留既有 reasoning steps、confidence basis、scenario triggers 與正文，避免單一 nested object 省略讓整段 structured recommendation section 被 schema validation 丟棄；RED→GREEN missing recommendation-object 單測與文件契約更新通過。

- D1405：P3-1299 補強 structured-output confidence-basis object missing-field fallback：`structured_output_models` 在 `RecommendationStructuredOutput` / `BubbleSniperStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `confidence_basis` 物件時補三列 `待補具體佐證`、兩列 `待補已納入風險` 與空 `data_gaps`，並保留既有 recommendation、reasoning steps、scenario triggers 與正文，避免單一信心依據 nested object 省略讓整段 structured recommendation section 被 schema validation 丟棄；RED→GREEN missing confidence-basis-object 單測與文件契約更新通過。

- D1406：P3-1300 補強 structured-output scenario-trigger collection missing-field fallback：`structured_output_models` 在 `RecommendationStructuredOutput` / `BubbleSniperStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `scenario_triggers` collection 時補兩列 neutral scenario trigger，並保留既有 recommendation、confidence basis、reasoning steps、next catalysts 與正文，避免單一情境觸發器集合省略讓整段 structured recommendation section 被 schema validation 丟棄；RED→GREEN missing scenario-trigger-collection 單測與文件契約更新通過。

- D1407：P3-1301 補強 structured-output missing scenario-trigger fallback catalyst derivation：`structured_output_models` 在 `BubbleSniperStructuredOutput` root validation 前，先把省略的 top-level `scenario_triggers` 補成兩列 neutral trigger，再進入 schema-derived `next_catalysts` 派生，讓 otherwise valid payload 同時省略 trigger 與 catalyst collections 時仍保留 neutral catalyst watchlist 與正文；RED→GREEN missing trigger/catalyst collections 單測與文件契約更新通過。

- D1408：P3-1302 補強 structured-output price-target nested object missing-field fallback：`structured_output_models` 在 `PriceTargetStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `price_targets` 或 `valuation_summary` objects 時分別補空 mapping，沿用既有欄位 fallback 產生 `資料不足` valuation reasoning、0.0 熊/基/牛目標價、`blended` 方法與 bool-safe flags，避免單一估值 nested object 省略讓整段 price-target section 被 schema validation 丟棄；RED→GREEN missing price-target/valuation-summary object 單測與文件契約更新通過。

- D1409：P3-1303 補強 structured-output management-sentiment highlight collection missing-field fallback：`structured_output_models` 在 `ManagementSentimentStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `highlights` collection 時補三列 `亮點` / `資料不足` placeholder，並保留既有 guidance tone、confidence 與正文，避免單一管理層亮點集合省略讓整段 management sentiment section 被 schema validation 丟棄；RED→GREEN missing management highlights 單測與文件契約更新通過。

- D1410：P3-1304 補強 structured-output downside-risk collection missing-field fallback：`structured_output_models` 在 `BearAdvocateStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `downside_risks` collection 時補三列 `下行風險` / `資料不足` / `warning` / `0.7` placeholder，並保留既有 thesis summary 與正文，避免單一空方風險集合省略讓整段 downside-risk section 被 schema validation 丟棄；RED→GREEN missing downside-risks 單測與文件契約更新通過。

- D1411：P3-1305 補強 structured-output moat-score container missing-field fallback：`structured_output_models` 在 `MoatStructuredOutput` root validation 前，對 otherwise valid payload 省略 top-level `moat_scores` object 時補空 mapping，沿用既有 `MoatScores` 欄位 fallback 產生六項 schema-safe 1.0 分數，並保留既有 reasoning steps 與正文，避免單一護城河分數容器省略讓整段 moat section 被 schema validation 丟棄；RED→GREEN missing moat-score object 單測與文件契約更新通過。

- D1412：P3-1306 補強 structured-output normalizer management-highlight collection missing-field fallback：`structured_output_normalizer` 在 Agent 20 schema validation 前，對 otherwise valid management sentiment payload 省略 top-level `highlights` collection 時補三列 `亮點` / `資料不足` placeholder，並保留既有 guidance tone、confidence 與正文，避免 normalizer 先把 missing highlights 轉成空集合後讓整段 management sentiment section 被 schema validation 丟棄；RED→GREEN missing management-highlight normalizer 單測與文件契約更新通過。

- D1413：P3-1307 補強 structured-output normalizer downside-risk collection missing-field fallback：`structured_output_normalizer` 在 Agent 21 schema validation 前，對 otherwise valid bear-advocate payload 省略 top-level `downside_risks` collection 時補三列 `下行風險` / `資料不足` / `warning` / `0.7` placeholder，並保留既有 thesis summary 與正文，避免 normalizer 先把 missing downside risks 轉成空集合後讓整段 downside-risk section 被 schema validation 丟棄；RED→GREEN missing downside-risk normalizer 單測與文件契約更新通過。

- D1414：P3-1308 補強 structured-output normalizer confidence-basis empty required-list fallback：`structured_output_normalizer` 在 Recommendation / Bubble Sniper schema validation 前，對 otherwise valid recommendation payload 的 `confidence_basis.evidence_items=[]` 或 `key_risks_acknowledged=[]` 空集合補足三列 `待補具體佐證` 與兩列 `待補已納入風險` placeholder，避免空 required list 讓整段 recommendation section 被 schema validation 丟棄；RED→GREEN empty confidence-basis required-list 單測與文件契約更新通過。

- D1415：P3-1309 補強 structured-output normalizer scenario-trigger empty-list fallback：`structured_output_normalizer` 在 Recommendation / Bubble Sniper schema validation 前，對 otherwise valid recommendation payload 的 `scenario_triggers=[]` 空集合補兩列 neutral `待後續資料確認觸發條件` / `重新檢查投資結論` placeholder，避免空 trigger list 讓整段 recommendation section 被 schema validation 丟棄；RED→GREEN empty scenario-trigger list 單測與文件契約更新通過。

- D1416：P3-1310 補強 structured-output normalizer next-catalyst empty-list derivation：`structured_output_normalizer` 在 Recommendation / Bubble Sniper schema validation 前，對 otherwise valid recommendation payload 的 `next_catalysts=[]` 空 watchlist 改由已清理過的 `scenario_triggers` 派生 `Scenario trigger N` catalyst rows，避免空 catalyst list 讓整段 recommendation section 被 schema validation 丟棄，同時保留 direct schema 對空 catalyst list 的嚴格驗證；RED→GREEN empty next-catalyst list 單測與文件契約更新通過。

- D1417：P3-1311 補強 structured-output normalizer reasoning-step empty-list fallback：`structured_output_normalizer` 在 schema validation 前，對 otherwise valid structured payload 的 `reasoning_steps=[]` 空集合補三列 `待補推論步驟` placeholder，避免空 reasoning-step list 讓整段 recommendation / Bubble Sniper 等 structured section 被 schema validation 丟棄；RED→GREEN empty reasoning-step list 單測與文件契約更新通過。

- D1418：P3-1312 補強 structured-output normalizer management-highlight empty-list fallback：`structured_output_normalizer` 在 Agent 20 schema validation 前，對 otherwise valid management sentiment payload 的 `highlights=[]` 空集合補三列 `亮點` / `資料不足` placeholder，避免空 highlight list 讓整段 management sentiment section 被 schema validation 丟棄；RED→GREEN empty management-highlight list 單測與文件契約更新通過。

- D1419：P3-1313 補強 structured-output normalizer downside-risk empty-list fallback：`structured_output_normalizer` 在 Agent 21 schema validation 前，對 otherwise valid bear-advocate payload 的 `downside_risks=[]` 空集合補三列 `下行風險` / `資料不足` / `warning` / `0.7` placeholder，避免空 downside-risk list 讓整段 downside-risk section 被 schema validation 丟棄；RED→GREEN empty downside-risk list 單測與文件契約更新通過。

- D1420：P3-1314 補強 structured-output normalizer empty next-catalyst / missing trigger derivation：`structured_output_normalizer` 在 Recommendation / Bubble Sniper schema validation 前，對 otherwise valid recommendation payload 同時省略 `scenario_triggers` 且提供 `next_catalysts=[]` 空 watchlist 的組合，先補兩列 neutral scenario-trigger fallback，再派生 `Scenario trigger N` catalyst rows，避免空 catalyst list 阻斷 schema 的 missing-trigger neutral watchlist；RED→GREEN empty next-catalyst / missing trigger 單測與文件契約更新通過。

- D1421：P3-1315 補強 structured-output normalizer reasoning-step null fallback：`structured_output_normalizer` 在 schema validation 前，對 otherwise valid structured payload 的 `reasoning_steps=None` null 集合補三列 `待補推論步驟` placeholder，避免 null reasoning-step 值被 normalizer 先轉成空集合後讓 recommendation / Bubble Sniper 等 structured section 被 schema validation 丟棄；RED→GREEN null reasoning-step 單測與文件契約更新通過。

- D1422：P3-1316 補強 structured-output normalizer scenario-trigger null fallback：`structured_output_normalizer` 在 Recommendation / Bubble Sniper schema validation 前，對 otherwise valid recommendation payload 的 `scenario_triggers=None` null 集合補兩列 neutral `待後續資料確認觸發條件` / `重新檢查投資結論` placeholder，避免 null trigger collection 被 normalizer 先轉成空集合後讓整段 recommendation section 被 schema validation 丟棄；RED→GREEN null scenario-trigger 單測與文件契約更新通過。

- D1423：P3-1317 補強 structured-output normalizer scenario-trigger scalar collection fallback：`structured_output_normalizer` 在 Recommendation / Bubble Sniper schema validation 前，對 otherwise valid recommendation payload 的 `scenario_triggers="..."` scalar 非清單集合補兩列 neutral `待後續資料確認觸發條件` / `重新檢查投資結論` placeholder，避免 non-list trigger collection 被 normalizer 先轉成空集合後讓整段 recommendation section 被 schema validation 丟棄；RED→GREEN scalar scenario-trigger 單測與文件契約更新通過。

- D1424：P3-1318 補強 structured-output normalizer price-target missing-object fallback projection：`structured_output_normalizer` 在 Agent 4/14 schema validation 後，若 raw `price_targets` 沒有任何有效熊/基/牛目標價，改用 schema validated fallback 的 `0.0` 三情境目標價與 `資料不足` valuation reasoning 保留 otherwise valid valuation summary 與正文；仍保留既有 raw-first 過濾，避免單一壞 target value 被 fallback `0.0` 污染有效估值列；RED→GREEN missing price-target normalizer 單測與文件契約更新通過。

- D1425：P3-1319 補強 structured-output normalizer moat-score missing-object fallback projection：`structured_output_normalizer` 在 Agent 3/12 schema validation 後，若 raw `moat_scores` 沒有任何有效護城河分數，改用 schema validated fallback 的六項 `1.0` 保守分數保留 otherwise valid reasoning steps 與正文；仍保留既有 raw-first 過濾，避免單一壞 moat score 被 fallback `1.0` 污染有效護城河評分列；RED→GREEN missing moat-score normalizer 單測與文件契約更新通過。

- D1426：P3-1320 補強 structured-output normalizer scalar-root schema fallback：`structured_output_normalizer` 讓 strict schema agent 的 scalar root payload 先進入 schema fallback validation，再做 final projection，避免 Agent 3/4/7/20/21/24 等 schema 已可保守補值的 malformed root 在 normalizer 入口先被 `None` 丟掉；RED→GREEN scalar-root normalizer 參數化單測與文件契約更新通過。

- D1427：P3-1321 補強 structured-output normalizer confidence-basis non-list required collection fallback：`structured_output_normalizer` 在 Agent 7/16/19 schema validation 前，對 `confidence_basis.evidence_items` 與 `key_risks_acknowledged` 的 missing、null 或 scalar 非清單 required collections 補足 `待補具體佐證` / `待補已納入風險` minimum fallback，避免 direct schema 原本可保守補值的信心依據欄位被 normalizer 先轉成空 list 後整段 recommendation / bubble-sniper section 掉成 `None`；RED→GREEN non-list confidence-basis normalizer 參數化單測與文件契約更新通過。

- D1428：P3-1322 補強 structured-output normalizer DCF scenario numeric fallback：`structured_output_normalizer` 在 Agent 4/14 schema validation 前，對 enum 合法的 `dcf_scenarios[]` rows 保留 row 並將 malformed growth、margin、WACC、intrinsic value 數字轉為 schema-safe fallback（0.0 / 1.0 / non-negative），避免 direct schema 原本可保守補值的 DCF 情境列在 normalizer 前處理時被整列丟掉；RED→GREEN DCF scenario numeric fallback 單測與文件契約更新通過。

- D1429：P3-1323 補強 structured-output normalizer reasoning-step scalar-object fallback：`structured_output_normalizer` 在 Agent 3/12/7/16/19 schema validation 前，對 `reasoning_steps` 的 malformed scalar/object 非清單值補三列 `待補推論步驟` minimum fallback，避免 direct schema 原本可保守補值的推論步驟集合被 normalizer 先轉成空 list 後整段 moat / recommendation / bubble-sniper section 掉成 `None`；RED→GREEN reasoning-step scalar-object normalizer 參數化單測與文件契約更新通過。

- D1430：P3-1324 補強 structured-output normalizer bubble-sniper recommendation fallback bias：`structured_output_normalizer` 在 Agent 19 schema validation 前，對 malformed `recommendation.建議` / `recommendation.recommendation` 標籤套用 bubble-sniper 的 `避免` fallback，而不是共用 Agent 7/16 的 generic `持有` fallback，避免空方風險段在壞標籤時被預先洗成中性持有結論；RED→GREEN Agent 7/19 fallback-bias 參數化單測與文件契約更新通過。

- D1431：P3-1325 補強 recommendation legacy text next-catalyst rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 7/16/19 legacy report text 中新增 `下一步催化觀察` 段落，將 structured `next_catalysts` 的事件、時間、方向與 trigger condition 以 shared display conversion 安全輸出，讓純文字 agent section 保留與 HTML sidebar 相同的 catalyst watchlist evidence；Agent 19 仍保證 `[投資建議]` 是全文最後區塊；RED→GREEN next-catalyst text 單測與文件契約更新通過。

- D1432：P3-1326 補強 downside-risk legacy text thesis-summary rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy report text 中新增 `空方論點摘要` 段落，將 schema/normalizer 已保留的 `thesis_summary` 放在個別 downside-risk 清單前，並以 shared display conversion 壓平 embedded newline，避免純文字報告只列風險項目卻漏掉空方核心論點；RED→GREEN thesis-summary text 單測與文件契約更新通過。

- D1433：P3-1327 補強 valuation legacy text valuation-reasoning rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 4/14 legacy report text 中新增 `估值推論` 段落，將 schema/normalizer 已保留的 DCF、同業與情境推論放在目標價表後、正文前，並以 shared display conversion 壓平 embedded newline，避免純文字估值報告只給目標價卻漏掉可追溯的估值依據；RED→GREEN valuation-reasoning text 單測與文件契約更新通過。

- D1434：P3-1328 補強 downside-risk legacy text priority-metadata rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy report text 的每列 downside risk 中加入 schema/normalizer 已保留的 `severity`、`confidence` 與 `impact`，並以 shared display conversion 壓平 embedded newline，避免純文字空方風險清單只列證據卻漏掉風險優先級與影響判讀；RED→GREEN downside-risk priority metadata 單測與文件契約更新通過。

- D1435：P3-1329 補強 management-sentiment legacy text confidence rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20 legacy report text 中新增 `信心分數`，將 schema/normalizer 已保留的 `confidence` 放在管理層語氣標題下，並以 0-1 numeric conversion 安全輸出，避免純文字管理層段落只給語氣與亮點卻漏掉確定性；RED→GREEN management-confidence text 單測與文件契約更新通過。

- D1436：P3-1330 補強 moat legacy text reasoning-step rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 3/12 legacy report text 中新增 `護城河推論步驟`，將 schema/normalizer 已要求的 `reasoning_steps` 放在護城河評分後、正文前，並以 shared display conversion 壓平 embedded newline，避免純文字護城河段落只列分數卻漏掉評分推論鏈；RED→GREEN moat reasoning-step text 單測與文件契約更新通過。

- D1437：P3-1331 補強 valuation legacy text DCF-scenario rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 4/14 legacy report text 中新增 `DCF 情境假設`，將 schema/normalizer 已保留的 `dcf_scenarios` 以熊市/基本/牛市列呈現營收成長偏差、利潤率偏差、WACC 與內在價值，並以 finite-number conversion 安全輸出，避免純文字估值段落只給目標價與推論卻漏掉模型敏感度；RED→GREEN DCF scenario text 單測與文件契約更新通過。

- D1438：P3-1332 補強 recommendation legacy text reasoning-step rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 7/16/19 legacy report text 中新增 `投資推論步驟`，將 schema/normalizer 已要求的 `reasoning_steps` 以 shared display conversion 壓平 embedded newline 後輸出，避免純文字投資建議段落只給結論、信心依據與觸發器卻漏掉推論鏈；Agent 19 仍保證 `[投資建議]` 是全文最後區塊；RED→GREEN recommendation reasoning-step text 單測與文件契約更新通過。

- D1439：P3-1333 補強 short-term trade-plan legacy text body fallback rendering：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 24 legacy report text 的極短線交易計畫清單後保留 `analysis_markdown` / `fallback_text` 正文脈絡，並沿用 shared body conversion 避免 malformed body 洩漏 Python literal，避免純文字短線交易段落只剩進出場清單卻漏掉交易背景；RED→GREEN trade-plan body fallback 單測與文件契約更新通過。

- D1440：P3-1334 補強 short-term trade-plan normalizer body projection：`structured_output_normalizer.normalize_structured_output()` 在 Agent 24 final projection 中保留 `analysis_markdown`，並以 safe text conversion 避免 malformed body truthiness 或 Python literal 外洩，讓標準 normalized payload 進入 `structured_output_to_report_text()` 時也能保留短線交易正文脈絡；RED→GREEN trade-plan normalized body 單測與文件契約更新通過。

- D1441：P3-1335 補強 downside-risk legacy text impact separator：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 風險列的 evidence 缺少句末標點時，會在 `impact` 前補入分號分隔，避免純文字空方風險清單把證據與「影響」標籤黏成同一句；RED→GREEN downside-risk impact separator 單測與文件契約更新通過。

- D1442：P3-1336 補強 recommendation tail empty-section rendering：`structured_output_normalizer.structured_output_to_report_text()` 會先累積 Agent 7/16/19 的信心依據與情境觸發器條目，只有存在可顯示條目時才輸出 `信心依據` / `情境觸發器` 標題，避免 malformed confidence-basis 或 trigger row 被 safe conversion 清空後，在純文字報告留下孤立空段落；RED→GREEN empty-section 單測與文件契約更新通過。

- D1443：P3-1337 補強 recommendation tail trigger-action fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 7/16/19 legacy 情境觸發器列中，若 `trigger_condition` 可顯示但 `action` 經 safe conversion 後為空，會輸出保守的 `重新檢查投資結論`，避免純文字報告留下只有「建議」但沒有動作的半句；RED→GREEN trigger-action fallback 單測與文件契約更新通過。

- D1444：P3-1338 補強 management-sentiment legacy quote fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20 管理層亮點列中，若 keyword 可顯示但 quote 經 safe conversion 後為空，會輸出 `資料不足`，避免純文字管理層段落留下只有亮點標籤卻沒有引述內容的空尾巴；RED→GREEN management quote fallback 單測與文件契約更新通過。

- D1445：P3-1339 補強 valuation summary legacy key fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 4/14 結構化估值檢查列中，若 summary key 經 safe display conversion 後為空，會輸出語意化的 `估值檢查項目`，避免純文字估值摘要以 `N/A` 作為欄位名稱而降低可讀性；RED→GREEN valuation summary key fallback 單測與文件契約更新通過。

- D1446：P3-1340 補強 moat score legacy key fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 3/12 護城河評分列中，若 score key 經 safe display conversion 後為空，會輸出語意化的 `護城河指標`，避免純文字護城河評分以 `N/A` 作為指標名稱而降低可讀性；RED→GREEN moat score key fallback 單測與文件契約更新通過。

- D1447：P3-1341 補強 valuation legacy empty price-target fallback row：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 4/14 legacy 目標股價段落沒有任何可顯示情境價格時，會輸出 `目標價: N/A`，避免純文字估值報告留下空白 `[目標股價]` 區塊；RED→GREEN empty price-target row 單測與文件契約更新通過。

- D1448：P3-1342 補強 management-sentiment legacy empty-highlight fallback row：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20 legacy 管理層亮點沒有任何可顯示列時，會輸出 `- **亮點**：資料不足`，避免純文字管理層語氣段落只剩 tone / confidence 與正文、缺少任何可掃描亮點列；RED→GREEN empty highlight row 單測與文件契約更新通過。

- D1449：P3-1343 補強 downside-risk legacy empty-risk fallback row：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 最大下行風險段落沒有任何可顯示風險列時，會輸出 `- **下行風險**（嚴重度：warning；信心：0.7）：資料不足`，避免純文字空方風險報告留下空白風險區塊；RED→GREEN empty downside-risk row 單測與文件契約更新通過。

- D1450：P3-1344 補強 moat-score legacy empty-score fallback row：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 3/12 legacy 護城河評分段落沒有任何可顯示 score row 時，會輸出 `護城河指標: N/A`，避免純文字護城河報告留下空白 `[護城河評分]` 區塊；RED→GREEN empty moat-score row 單測與文件契約更新通過。

- D1451：P3-1345 補強 recommendation block legacy empty-standard fallback row：`structured_output_rendering.format_recommendation_block()` 在 Agent 7/16 standard recommendation block 沒有任何可顯示 recommendation row 時，會輸出 `建議: N/A`，避免純文字投資建議報告留下空白 `[投資建議]` 區塊；Agent 19 仍沿用既有 ordered N/A rows；RED→GREEN empty standard recommendation row 單測與文件契約更新通過。

- D1452：P3-1346 補強 Agent 19 required trigger action fallback：`structured_output_rendering.ensure_agent19_required_sections()` 在做空觸發條件與防軋空停損點的 scenario trigger 有條件但 action 缺失或 malformed 時，會分別補 `重新檢查空方假設` / `回補或暫停空方假設`，避免純文字 crash/stop-loss bullet 只剩觸發條件而沒有可操作回應；RED→GREEN required trigger action fallback 單測與文件契約更新通過。

- D1453：P3-1347 補強 recommendation legacy next-catalyst trigger fallback：`structured_output_normalizer._next_catalyst_text()` 在 recommendation legacy tail 的 catalyst 事件可顯示但 trigger condition 缺失或 malformed 時，會輸出 `待後續資料確認`，避免純文字報告直接丟掉整個 `下一步催化觀察` 段落；RED→GREEN blank next-catalyst trigger 單測與文件契約更新通過。

- D1454：P3-1348 補強 recommendation legacy next-catalyst impact-direction fallback：`structured_output_normalizer._next_catalyst_text()` 在 recommendation legacy tail 的 catalyst direction 不是 `bullish` / `bearish` / `volatile` 時，會輸出 `volatile`，避免純文字報告把任意模型字串或換行片段直接放進 `下一步催化觀察` 方向欄位；RED→GREEN invalid next-catalyst impact-direction 單測與文件契約更新通過。

- D1455：P3-1349 補強 recommendation legacy next-catalyst trigger-length fallback：`structured_output_normalizer._next_catalyst_text()` 在 recommendation legacy tail 的 catalyst trigger condition 太短而不可操作時，會輸出 `待後續資料確認`，避免純文字報告把短碎片誤呈現為可執行催化觀察條件；RED→GREEN too-short next-catalyst trigger 單測與文件契約更新通過。

- D1456：P3-1350 補強 recommendation legacy scenario-trigger single-fragment guard：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 7/16/19 legacy 情境觸發器列中略過單字 trigger condition 碎片，避免純文字報告把不可操作的一字模型殘片呈現為觸發條件，同時保留既有短中文有效條件；RED→GREEN single-character scenario-trigger 單測與文件契約更新通過。

- D1457：P3-1351 補強 recommendation legacy scenario-trigger action single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 7/16/19 legacy 情境觸發器列中若 action 只有一字殘片，會保留有效 trigger condition 並補 `重新檢查投資結論`，避免純文字報告留下「建議 改」這類不可操作動作；RED→GREEN single-character scenario-trigger action 單測與文件契約更新通過。

- D1458：P3-1352 補強 legacy reasoning-step single-fragment guard：`structured_output_normalizer._reasoning_steps_text()` 在 Agent 3/12/7/16/19 legacy 推論步驟輸出時略過單字 reasoning step 碎片，避免純文字報告把不可操作的一字模型殘片呈現為推論鏈，同時保留有效推論步驟；RED→GREEN single-character reasoning-step 單測與文件契約更新通過。

- D1459：P3-1353 補強 recommendation legacy confidence-basis single-fragment guard：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 7/16/19 legacy 信心依據輸出時略過單字 evidence / risk / data-gap 碎片，避免純文字報告把不可操作的一字模型殘片呈現為佐證或風險，且在全被濾掉時不留下空 `信心依據` 標題；RED→GREEN single-character confidence-basis 單測與文件契約更新通過。

- D1460：P3-1354 補強 downside-risk legacy evidence single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 最大下行風險列中若 evidence 只有單字殘片，會保留風險標題、severity、confidence 與 impact，並將 evidence 顯示為 `資料不足`，避免純文字空方風險報告把不可操作的一字模型殘片當成證據；RED→GREEN single-character downside-risk evidence 單測與文件契約更新通過。

- D1461：P3-1355 補強 downside-risk legacy title single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 最大下行風險列中若 title 只有單字殘片，會保留 evidence、severity、confidence 與 impact，並將風險標題顯示為 `下行風險`，避免純文字空方風險報告把不可操作的一字模型殘片當成風險名稱；RED→GREEN single-character downside-risk title 單測與文件契約更新通過。

- D1462：P3-1356 補強 downside-risk legacy impact single-fragment omission：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 最大下行風險列中若 impact 只有單字殘片，會保留 title、evidence、severity 與 confidence，並省略 `影響` 片段，避免純文字空方風險報告把不可操作的一字模型殘片當成影響判讀；RED→GREEN single-character downside-risk impact 單測與文件契約更新通過。

- D1463：P3-1357 補強 downside-risk legacy severity metadata fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 最大下行風險列中若 severity metadata 不屬於 schema enum `warning/high/critical`，會回落為 `warning`，避免 direct legacy rendering 把任意嚴重度標籤呈現在純文字空方風險報告；RED→GREEN invalid downside-risk severity 單測與文件契約更新通過。

- D1464：P3-1358 補強 downside-risk legacy confidence metadata fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 最大下行風險列中若 confidence metadata 不是 0 到 1 的有限數字，會回落為 schema 預設 `0.7`，避免 direct legacy rendering 把任意信心標籤或非數值呈現在純文字空方風險報告；RED→GREEN invalid downside-risk confidence 單測與文件契約更新通過。

- D1465：P3-1359 補強 downside-risk legacy thesis-summary single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 空方論點摘要段落中若 thesis_summary 只有單字殘片，會保留摘要段落並顯示 `資料不足`，避免純文字空方報告把不可操作的一字模型殘片當成核心空方論點；RED→GREEN single-character thesis-summary 單測與文件契約更新通過。

- D1466：P3-1360 補強 downside-risk legacy analysis-body single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 21 legacy 空方報告本文中若 analysis_markdown 只有單字殘片，會將本文顯示為 `資料不足`，避免純文字空方報告結尾把不可操作的一字模型殘片當成正式分析正文；RED→GREEN single-character downside-risk body 單測與文件契約更新通過。

- D1467：P3-1361 補強 management-sentiment legacy guidance-tone metadata fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20 legacy 管理層語氣 metadata 不屬於 schema enum `樂觀/中立/保守/資料不足` 時，會顯示 `資料不足`，避免 direct legacy rendering 把任意 guidance-tone 標籤呈現在純文字管理層報告；RED→GREEN invalid guidance-tone 單測與文件契約更新通過。

- D1468：P3-1362 補強 management-sentiment legacy highlight single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20 legacy 管理層亮點列中若 keyword 或 quote 只有單字殘片，會分別回落為 `亮點` / `資料不足`，避免純文字管理層報告把不可操作的一字模型殘片呈現為正式亮點；RED→GREEN single-character management highlight 單測與文件契約更新通過。

- D1469：P3-1363 補強 management-sentiment legacy analysis-body single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 20 legacy 管理層正文中若 analysis_markdown 只有單字殘片，會將正文顯示為 `資料不足`，避免純文字管理層報告結尾把不可操作的一字模型殘片當成正式分析正文；RED→GREEN single-character management body 單測與文件契約更新通過。

- D1470：P3-1364 補強 short-term trade-plan legacy enum metadata fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 24 legacy 極短線交易計畫中若 trade_direction 或 risk_level metadata 不屬於 schema enum，會分別顯示 `Neutral` / `High`，避免 direct legacy rendering 把任意交易方向或風險等級標籤呈現在純文字短線交易報告；RED→GREEN invalid trade-plan enum 單測與文件契約更新通過。

- D1471：P3-1365 補強 short-term trade-plan legacy field single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 24 legacy 極短線交易計畫中若 entry_zone、target_price、stop_loss 或 core_catalyst 只有單字殘片，會顯示 `N/A`，避免純文字短線交易報告把不可操作的一字模型殘片當成進出場、停損或催化指令；RED→GREEN single-character trade-plan field 單測與文件契約更新通過。

- D1472：P3-1366 補強 short-term trade-plan legacy analysis-body single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 24 legacy 極短線交易計畫正文中若 analysis_markdown 只有單字殘片，會將正文顯示為 `資料不足`，避免純文字短線交易報告結尾把不可操作的一字模型殘片當成正式交易脈絡；RED→GREEN single-character trade-plan body 單測與文件契約更新通過。

- D1473：P3-1367 補強 valuation summary legacy row single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 4/14 legacy 結構化估值檢查列中若 summary key 或 value 只有單字殘片，會分別顯示 `估值檢查項目` / `N/A`，避免純文字估值摘要把不可操作的一字模型殘片當成估值檢查欄位或結論；RED→GREEN single-character valuation-summary row 單測與文件契約更新通過。

- D1474：P3-1368 補強 moat-score legacy key single-fragment fallback：`structured_output_normalizer.structured_output_to_report_text()` 在 Agent 3/12 legacy 護城河評分列中若 score key 只有單字殘片，會顯示 `護城河指標`，同時保留合法的一位數 score value，避免純文字護城河報告把不可操作的一字模型殘片當成正式指標名稱；RED→GREEN single-character moat-score key 單測與文件契約更新通過。
