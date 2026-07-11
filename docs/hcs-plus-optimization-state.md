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
- D589：P3-483 新增 `scripts/check_visual_regression.py` runtime preflight，讓 CI、直接 visual script 與 setup script 都在 visual suite 前實際 launch headless Chromium；browser 缺失時提前輸出 `scripts/setup_visual_regression.sh` 修復命令，不在 CI gate 中偷偷安裝未鎖版本套件；preflight `3 passed`、正式 CI gate `1744 passed, 4 skipped, 1 deselected`、coverage `84%`、visual regression `3 passed`。

## 未解問題

- CI runner 仍需在 image/setup step 安裝 Playwright/Chromium；`check_visual_regression.py` 現在會在 coverage/visual suite 前提前失敗並列出 `scripts/setup_visual_regression.sh`，但為了可重現性不由正式 CI gate 自動安裝未鎖版本 browser dependency。
- 後端 runtime catalog 與前端首屏 fallback 已分別由 `pipeline_mode_catalog.py` 和 generated `pipeline_mode_fallback.js` 提供，CI 會檢查兩者是否漂移；新增模式仍需維護 schema version、生成 artifact 與前端 runtime 相容性。
- 2026-07-08 新一輪 HCS Plus 系統優化已完成 P0/P1/P2 主要工程票；尚未宣稱新一輪嚴格單項三輪巡迴完成。

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
