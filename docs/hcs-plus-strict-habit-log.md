# HCS Plus Strict Habit Log

更新時間：2026-07-05

本文件是 `docs/hcs-plus-optimization-state.md` 的嚴格單項輪巡附件。先前已完成四大類批次式優化；本次開始把每個 HCS 單項思考習慣獨立落地、獨立驗證，避免「類別完成」掩蓋單項盲點。

## 專案狀態

- 專案目標：讓本機股票研究系統的報告、前端工作台、資料可信度與維運流程更可掃讀、可驗證、可追溯。
- 已完成範圍：第 1 輪 / 批判思考 / `#拆解問題` 到 `#可驗證性`，第 1 輪 / 創意思考 / `#學習科學` 到 `#研究複製`，第 1 輪 / 溝通思考 / `#受眾` 到 `#多媒體`，第 1 輪 / 互動思考 / `#倫理考量` 到 `#制定策略`，第 2 輪 / 批判思考 / `#拆解問題` 到 `#可驗證性`，第 2 輪 / 創意思考 / `#學習科學` 到 `#研究複製`，第 2 輪 / 溝通思考 / `#受眾` 到 `#多媒體`，第 2 輪 / 互動思考 / `#倫理考量` 到 `#制定策略`，第 3 輪 / 批判思考 / `#拆解問題` 到 `#可驗證性`，第 3 輪 / 創意思考 / `#學習科學` 到 `#研究複製`，第 3 輪 / 溝通思考 / `#受眾` 到 `#多媒體`，第 3 輪 / 互動思考 / `#倫理考量` 到 `#制定策略`。
- 暫定策略：把批判思考發現轉成小型可學、可接續、可驗證的文件與前端契約改善。
- 驗證基準：每批至少有一個自動化測試或文件契約能防止狀態回退。
- 目前限制：尚未重跑完整測試矩陣；本批次先驗證 HCS 文件契約。

## 完整單項輪巡清單

| 分類 | 思考習慣 |
|---|---|
| 批判思考 | #拆解問題、#問對問題、#差距分析、#變數分析、#偏誤辨識、#偏誤降低、#決策樹、#目的、#效用、#信賴區間、#相關性、#描述統計、#機率、#迴歸、#顯著性、#證據基礎、#演繹、#歸納、#謬誤、#來源品質、#情境脈絡、#批判、#估算、#詮釋框架、#合理性、#可驗證性 |
| 創意思考 | #學習科學、#限制條件、#類比、#演算法、#設計思考、#捷思法、#最佳化、#假說發展、#資料視覺化、#建模、#抽樣、#個案研究、#比較組、#介入研究、#訪談調查、#觀察研究、#研究複製 |
| 溝通思考 | #受眾、#組成、#語意含義、#組織結構、#專業性、#論點、#溝通設計、#表達、#媒介、#多媒體 |
| 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷、#複雜因果、#湧現特性、#分析層次、#網絡、#系統動力學、#系統圖像、#談判、#說服、#形塑行為、#從眾、#差異、#情緒智商、#領導原則、#權力動態、#責任、#自我覺察、#制定策略 |

## 嚴格輪巡進度

| 輪次 | 分類 | 思考習慣 | 狀態 | 落地修改 |
|---|---|---|---|---|
| 1 | 批判思考 | #拆解問題 | 完成 | 建立本嚴格輪巡附件與批次邊界 |
| 1 | 批判思考 | #問對問題 | 完成 | 將高影響決策寫成暫定決策與可回答問題 |
| 1 | 批判思考 | #差距分析 | 完成 | 建立現況到目標的缺口矩陣 |
| 1 | 批判思考 | #變數分析 | 完成 | 建立會影響報告可信度與維運體驗的變數清單 |
| 1 | 批判思考 | #偏誤辨識 | 完成 | 建立偏誤風險與對應護欄，並新增文件契約測試 |
| 1 | 批判思考 | #偏誤降低 | 完成 | 將 alias 漂移風險轉成 canonical pipeline 文件護欄 |
| 1 | 批判思考 | #決策樹 | 完成 | 決定本批先修文件範例與契約，而非 runtime 行為 |
| 1 | 批判思考 | #目的 | 完成 | 明確化 pipeline 文件範例的使用者目的 |
| 1 | 批判思考 | #效用 | 完成 | 用低風險文件修改降低新整合者選錯 ID 的成本 |
| 1 | 批判思考 | #信賴區間 | 完成 | Active jobs 顯示共用模式語意，降低操作者對任務類型的不確定性 |
| 1 | 批判思考 | #相關性 | 完成 | 避免任務狀態與 raw pipeline id 產生錯誤關聯 |
| 1 | 批判思考 | #描述統計 | 完成 | 將任務列表摘要維持在可掃讀的 ticker、模式、狀態、進度 |
| 1 | 批判思考 | #機率 | 完成 | Performance panel 顯示樣本信心提示，避免把少量 hit rate 當成穩定機率 |
| 1 | 批判思考 | #迴歸 | 完成 | 將回測績效維持為觀察指標，不把短期 ROI 當成可外推趨勢 |
| 1 | 批判思考 | #顯著性 | 完成 | 10 筆以下標示「樣本不足，僅供觀察」 |
| 1 | 批判思考 | #證據基礎 | 完成 | Preview 頂部顯示 evidence exit gate / report conformance 品質徽章 |
| 1 | 批判思考 | #演繹 | 完成 | 避免從「可預覽」錯推成「證據與格式皆可採用」 |
| 1 | 批判思考 | #歸納 | 完成 | 將 history 的品質警示延續到 preview，維持跨視圖一致性 |
| 1 | 批判思考 | #謬誤 | 完成 | Operator summary 移除 `fresh / sampled` 內部語氣，避免把資料新鮮度誤讀為整體可信 |
| 1 | 批判思考 | #來源品質 | 完成 | 將來源提醒脈絡寫成「無需刷新/重跑 · 資料新鮮 / 抽樣」 |
| 1 | 批判思考 | #情境脈絡 | 完成 | 把摘要樣本範圍明確標成「抽樣」，避免被看成全庫統計 |
| 1 | 批判思考 | #批判 | 完成 | 將 LLM 健康正常改為本機觀測正常，避免過度肯定 |
| 1 | 批判思考 | #估算 | 完成 | API quota summary 明確說明是本機觀測與服務設定數 |
| 1 | 批判思考 | #詮釋框架 | 完成 | 將 LLM/API 面板框架從 provider 健康改成本機觀測 |
| 1 | 批判思考 | #合理性 | 完成 | 補上批判思考第 1 輪 26/26 收尾摘要 |
| 1 | 批判思考 | #可驗證性 | 完成 | 用 HCS 狀態測試鎖住收尾摘要與下一分類入口 |
| 1 | 創意思考 | #學習科學 | 完成 | 在模式契約新增決策問題式速記 |
| 1 | 創意思考 | #限制條件 | 完成 | 不改 UI 與 runtime，只補文件契約測試 |
| 1 | 創意思考 | #類比 | 完成 | 用「分診台」類比說明模式選擇流程 |
| 1 | 創意思考 | #演算法 | 完成 | 新增模式選擇決策樹 |
| 1 | 創意思考 | #設計思考 | 完成 | 以使用者決策情境排列 mode 選擇順序 |
| 1 | 創意思考 | #捷思法 | 完成 | 定義不確定時先用 `v1` 建立基本面基準 |
| 1 | 創意思考 | #最佳化 | 完成 | Report compare summary 使用共用 mode label，降低辨識成本 |
| 1 | 創意思考 | #假說發展 | 完成 | 驗證「比較報告時先看決策模式」的 UI 假說 |
| 1 | 創意思考 | #資料視覺化 | 完成 | 比較選取摘要不再顯示 raw `pipeline_id` |
| 1 | 創意思考 | #建模 | 完成 | Report compare result 顯示左右比較基準 |
| 1 | 創意思考 | #抽樣 | 完成 | Report compare result 顯示左右樣本日期與時間順序 |
| 1 | 創意思考 | #個案研究 | 完成 | 將兩份報告比較框成可審查個案 |
| 1 | 創意思考 | #比較組 | 完成 | 跨模式比較 warning 改用可讀 mode label |
| 1 | 創意思考 | #介入研究 | 完成 | 以前端轉譯介入 raw pipeline warning |
| 1 | 創意思考 | #訪談調查 | 完成 | 將使用者可能誤解的 warning 文案轉成測試契約 |
| 1 | 創意思考 | #觀察研究 | 完成 | 掃描前端 raw mode 使用，區分顯示與資料傳遞 |
| 1 | 創意思考 | #研究複製 | 完成 | 將共用 mode label 模式複製到 compare summary/result/warning |
| 1 | 溝通思考 | #受眾 | 完成 | Compare warning 改用非工程操作者可讀語氣 |
| 1 | 溝通思考 | #組成 | 完成 | Warning 由左右模式與比較性質組成 |
| 1 | 溝通思考 | #語意含義 | 完成 | 將 `vs` 改成「與」，並明示跨視角比較 |
| 1 | 溝通思考 | #組織結構 | 完成 | Report compare result 第一列顯示比較結論 |
| 1 | 溝通思考 | #專業性 | 完成 | 以同股票同模式/跨視角等專業語氣標示比較性質 |
| 1 | 溝通思考 | #論點 | 完成 | 讓比較結論先於檔名與數字出現 |
| 1 | 溝通思考 | #溝通設計 | 完成 | 收斂 compare panel，不再新增複雜視覺元件 |
| 1 | 溝通思考 | #表達 | 完成 | 用收尾摘要固定本輪比較文案原則 |
| 1 | 溝通思考 | #媒介 | 完成 | 確認目前以文字 grid/chip 作為合適媒介 |
| 1 | 溝通思考 | #多媒體 | 完成 | 記錄暫不引入圖表/截圖式比較，避免過度設計 |
| 1 | 互動思考 | #倫理考量 | 完成 | Compare result 增加非即時交易指令提醒 |
| 1 | 互動思考 | #倫理勇氣 | 完成 | 將「建議」改成「報告建議變化」，避免過度順從報告 |
| 1 | 互動思考 | #倫理判斷 | 完成 | 測試鎖住使用提醒與建議語意邊界 |
| 1 | 互動思考 | #複雜因果 | 完成 | Compare result 增加報告差異不等於市場因果提醒 |
| 1 | 互動思考 | #湧現特性 | 完成 | 提醒使用者搭配資料可信度與追蹤報酬判讀 |
| 1 | 互動思考 | #分析層次 | 完成 | 將報告差異、資料可信度、追蹤報酬分層呈現 |
| 1 | 互動思考 | #網絡 | 完成 | Decision-needs-rerun warning 連回重跑流程 |
| 1 | 互動思考 | #系統動力學 | 完成 | 將資料更新後的正確順序寫成先重跑再比較 |
| 1 | 互動思考 | #系統圖像 | 完成 | Compare warning 呈現比較、資料、重跑的系統關係 |
| 1 | 互動思考 | #談判 | 完成 | Rerun warning 改成條件式「若要比較」語氣 |
| 1 | 互動思考 | #說服 | 完成 | 避免 warning 以命令式語氣強推使用者重跑 |
| 1 | 互動思考 | #形塑行為 | 完成 | 用條件式順序引導審慎比較流程 |
| 1 | 互動思考 | #從眾 | 完成 | Preview legacy 預設改為「報告建議」，避免 UI 強化跟隨式採用 |
| 1 | 互動思考 | #差異 | 完成 | 摘要補上「報告建議仍需自行判斷」，區分報告輸出與使用者判斷 |
| 1 | 互動思考 | #情緒智商 | 完成 | 移除預設裸「投資建議/建議」語氣，降低情緒化操作暗示 |
| 1 | 互動思考 | #領導原則 | 完成 | Preview 靜態骨架與 rerun CTA 改用「報告」語氣，帶領使用者看研究產物 |
| 1 | 互動思考 | #權力動態 | 完成 | 將「最終建議」改成「報告結論」，降低系統權威感 |
| 1 | 互動思考 | #責任 | 完成 | 靜態 preview 標題、label、aria 與按鈕一致標示報告層級 |
| 1 | 互動思考 | #自我覺察 | 完成 | History filter 承認自己是在篩選報告欄位，不是發布投資指令 |
| 1 | 互動思考 | #制定策略 | 完成 | 收尾互動思考 20/20，下一輪回到批判思考重新拆解問題 |
| 2 | 批判思考 | #拆解問題 | 完成 | 建立第 2 輪問題雷達，拆出報告正文、prompt 契約與前端顯示層 |
| 2 | 批判思考 | #問對問題 | 完成 | 將下一輪決策轉成「要不要分離契約/顯示層」的關鍵問題 |
| 2 | 批判思考 | #差距分析 | 完成 | 記錄第 1 輪已降權威語氣與剩餘正文契約風險的差距 |
| 2 | 批判思考 | #變數分析 | 完成 | 建立可改名顯示層與需保留契約層的變數表 |
| 2 | 批判思考 | #偏誤辨識 | 完成 | 明確標記字串潔癖偏誤與過度保守契約偏誤 |
| 2 | 批判思考 | #偏誤降低 | 完成 | 用解析契約回歸與前端契約測試作為改名護欄 |
| 2 | 批判思考 | #決策樹 | 完成 | 建立契約詞處理決策樹，分流顯示層、解析契約與完整報告正文 |
| 2 | 批判思考 | #目的 | 完成 | 明確目標是降低使用者入口權威感，同時保住報告解析契約 |
| 2 | 批判思考 | #效用 | 完成 | 選定最高效用路徑：先補 coverage map，再決定是否拆正文顯示詞 |
| 2 | 批判思考 | #信賴區間 | 完成 | 契約詞 coverage map 標示只涵蓋可維護來源檔，排除生成報告輸出 |
| 2 | 批判思考 | #相關性 | 完成 | 記錄「出現契約詞」不等於可替換或不可替換 |
| 2 | 批判思考 | #描述統計 | 完成 | 統計 tests 23 檔、backend 25 檔含契約詞 |
| 2 | 批判思考 | #機率 | 完成 | 將契約詞改動風險分成高/中/低機率回歸 |
| 2 | 批判思考 | #迴歸 | 完成 | 建立契約詞回歸測試組 |
| 2 | 批判思考 | #顯著性 | 完成 | 定義會觸發更廣測試矩陣的顯著性門檻 |
| 2 | 批判思考 | #證據基礎 | 完成 | 將 coverage map 與風險排序轉成契約測試矩陣 |
| 2 | 批判思考 | #演繹 | 完成 | 建立高/中/低顯著性改動到必跑測試的規則 |
| 2 | 批判思考 | #歸納 | 完成 | 記錄測試矩陣只能外推到目前可觀測來源與代表性流程 |
| 2 | 批判思考 | #謬誤 | 完成 | 將契約矩陣可能導致的錯誤推論寫成反謬誤護欄 |
| 2 | 批判思考 | #來源品質 | 完成 | 將測試、source、文件、生成輸出分成可用與不可作為完成證據的來源 |
| 2 | 批判思考 | #情境脈絡 | 完成 | 區分機器契約變更與使用者顯示層改動的適用情境 |
| 2 | 批判思考 | #批判 | 完成 | 評估契約矩陣過重風險，決定暫不新增自動選測腳本 |
| 2 | 批判思考 | #估算 | 完成 | 將高/中/低情境估算成 4/3/2 個測試檔的最小命令分組 |
| 2 | 批判思考 | #詮釋框架 | 完成 | 定義綠燈、紅燈與不得解讀為的結果框架 |
| 2 | 批判思考 | #合理性 | 完成 | 以契約矩陣、反謬誤護欄與最小命令分組作為合理收尾 |
| 2 | 批判思考 | #可驗證性 | 完成 | 建立第 2 輪批判思考 26/26 收尾 checkpoint |
| 2 | 創意思考 | #學習科學 | 完成 | 契約矩陣速學卡用三題降低學習成本 |
| 2 | 創意思考 | #限制條件 | 完成 | 保留不新增自動選測腳本的限制 |
| 2 | 創意思考 | #類比 | 完成 | 用三道安檢通道類比契約風險分流 |
| 2 | 創意思考 | #演算法 | 完成 | 將契約矩陣速學卡轉成四步操作流程 |
| 2 | 創意思考 | #設計思考 | 完成 | 補上 parser/prompt、報告模板、前端文案三個操作者情境 |
| 2 | 創意思考 | #捷思法 | 完成 | 補上三條快速判斷規則 |
| 2 | 創意思考 | #最佳化 | 完成 | 契約矩陣採用觀測板定義最佳化目標 |
| 2 | 創意思考 | #假說發展 | 完成 | 建立三個可觀察假說 |
| 2 | 創意思考 | #資料視覺化 | 完成 | 用綠/黃/紅採用訊號矩陣呈現人工 review 訊號 |
| 2 | 創意思考 | #建模 | 完成 | 建立三類契約矩陣案例模型 |
| 2 | 創意思考 | #抽樣 | 完成 | 定義代表性抽樣規則 |
| 2 | 創意思考 | #個案研究 | 完成 | 建立案例卡格式 |
| 2 | 創意思考 | #比較組 | 完成 | 建立基準組與介入組比較 |
| 2 | 創意思考 | #介入研究 | 完成 | 定義案例卡介入方案 |
| 2 | 創意思考 | #訪談調查 | 完成 | 建立三題操作者回饋 |
| 2 | 創意思考 | #觀察研究 | 完成 | 定義契約矩陣觀察記錄欄位 |
| 2 | 創意思考 | #研究複製 | 完成 | 定義複製檢查清單與完成條件 |
| 2 | 溝通思考 | #受眾 | 完成 | 契約矩陣讀者路徑分出三種維護者受眾 |
| 2 | 溝通思考 | #組成 | 完成 | 建立先讀速學卡、再用操作流程、最後填案例卡的閱讀順序 |
| 2 | 溝通思考 | #語意含義 | 完成 | 明確標出文件契約、觀察紀錄與低顯著性的語意邊界 |
| 2 | 溝通思考 | #組織結構 | 完成 | 契約矩陣維護導覽建立章節順序 |
| 2 | 溝通思考 | #專業性 | 完成 | 維護語氣限制測試綠燈的可宣稱範圍 |
| 2 | 溝通思考 | #論點 | 完成 | 核心論點收斂為人工判斷加最小測試驗證 |
| 2 | 溝通思考 | #溝通設計 | 完成 | 契約矩陣一頁摘要建立三步短版判斷 |
| 2 | 溝通思考 | #表達 | 完成 | 新增通道、命令與限制的建議表達句型 |
| 2 | 溝通思考 | #媒介 | 完成 | 決定文字與表格優先 |
| 2 | 溝通思考 | #多媒體 | 完成 | 暫不新增圖像或多媒體，保留文字限制 |
| 2 | 互動思考 | #倫理考量 | 完成 | 契約矩陣倫理邊界新增不得誇大測試綠燈的底線 |
| 2 | 互動思考 | #倫理勇氣 | 完成 | 明確必要時要說不的阻擋條件 |
| 2 | 互動思考 | #倫理判斷 | 完成 | 建立允許/禁止敘述與升級條件 |
| 2 | 互動思考 | #複雜因果 | 完成 | 建立局部證據到錯誤推論的複雜因果圖譜 |
| 2 | 互動思考 | #湧現特性 | 完成 | 記錄低顯著性累積、跨模式模糊與觀察替代驗證風險 |
| 2 | 互動思考 | #分析層次 | 完成 | 區分文件層、測試層、runtime 層與使用者行為層 |
| 2 | 互動思考 | #網絡 | 完成 | 建立契約矩陣維護網絡 |
| 2 | 互動思考 | #系統動力學 | 完成 | 記錄語氣、觀察與升級條件的動態回路 |
| 2 | 互動思考 | #系統圖像 | 完成 | 建立改動定位、證據對齊與倫理宣稱流程 |
| 2 | 互動思考 | #談判 | 完成 | 契約矩陣 review 對話建立補證據協商 |
| 2 | 互動思考 | #說服 | 完成 | 把補跑、升級與拆分說成降低錯放與 review 成本 |
| 2 | 互動思考 | #形塑行為 | 完成 | 建立一頁摘要、案例卡與採用訊號的預設行為 |
| 2 | 互動思考 | #從眾 | 完成 | review 防從眾檢查禁止用多數同意、前例綠燈或測試全綠取代證據 |
| 2 | 互動思考 | #差異 | 完成 | 差異保留要求通道、模式與證據層分開回報 |
| 2 | 互動思考 | #情緒智商 | 完成 | 高壓 review 先命名壓力，再回到最小補證據路徑與限制句 |
| 2 | 互動思考 | #領導原則 | 完成 | review 責任分工要求主責宣告改動層級並由 review 主導者要求升級 |
| 2 | 互動思考 | #權力動態 | 完成 | 權力護欄禁止用職位、資深度或合併權限取代證據 |
| 2 | 互動思考 | #責任 | 完成 | 改動者、reviewer、合併者分別負責層級、通道命令與限制句 |
| 2 | 互動思考 | #自我覺察 | 完成 | review 自我稽核承認契約矩陣不是自動化審核器，避免過度官僚 |
| 2 | 互動思考 | #制定策略 | 完成 | 收尾策略要求最小足夠路徑，並將下一批推進到第 3 輪批判思考 |
| 3 | 批判思考 | #拆解問題 | 完成 | 契約矩陣第 3 輪問題雷達拆出矩陣過重、2 分鐘選通道、低顯著性被拖慢與限制句落地問題 |
| 3 | 批判思考 | #問對問題 | 完成 | 將下一批焦點改成一頁摘要可取代什麼、完整矩陣何時必須保留、哪個證據層缺 runtime 驗證 |
| 3 | 批判思考 | #差距分析 | 完成 | 對照已完成矩陣能力與仍缺的日常入口、限制句驗證、輕量通道誤用防線 |
| 3 | 批判思考 | #變數分析 | 完成 | 契約矩陣第 3 輪護欄拆出改動層級、證據層、可逆性與時程壓力 |
| 3 | 批判思考 | #偏誤辨識 | 完成 | 標出過度升級、過度降級、工具化幻覺與綠燈擴張偏誤 |
| 3 | 批判思考 | #偏誤降低 | 完成 | 建立一頁摘要優先、跨層改動升級、證據分層回報、限制句必填與案例卡觸發 |
| 3 | 批判思考 | #決策樹 | 完成 | 契約矩陣第 3 輪分流決策把低顯著性、高顯著性、混合層、跨層與文件層排成五步 |
| 3 | 批判思考 | #目的 | 完成 | 目的校準聚焦降低 2 分鐘選通道摩擦、保住高顯著性契約、防止綠燈擴張與保留低顯著性效率 |
| 3 | 批判思考 | #效用 | 完成 | 效用校準列出規則、預期效用、成本與升級或停用條件 |
| 3 | 批判思考 | #信賴區間 | 完成 | 證據校準標出目前樣本、不可外推範圍與觀察窗口 |
| 3 | 批判思考 | #相關性 | 完成 | 觀測訊號只支持關聯，不代表因果或 runtime 已驗證 |
| 3 | 批判思考 | #描述統計 | 完成 | 定義樣本數、中位選通道時間、錯選率、跨層改動比例、案例卡觸發率與限制句出現率 |
| 3 | 批判思考 | #機率 | 完成 | 將錯選率、限制句缺漏率與案例卡漏觸發率轉成風險機率判讀 |
| 3 | 批判思考 | #迴歸 | 完成 | 用連續兩個觀察窗口與紅色高風險例外定義回歸監測 |
| 3 | 批判思考 | #顯著性 | 完成 | 設定至少 5 個案例、升級門檻與不得宣稱改善限制 |
| 3 | 批判思考 | #證據基礎 | 完成 | 將文件契約測試、觀察窗口紀錄與案例卡分成可接受證據，並列出不可作為證據的訊號 |
| 3 | 批判思考 | #演繹 | 完成 | 建立立即升級、小樣本限制與連續窗口回歸的推論規則 |
| 3 | 批判思考 | #歸納 | 完成 | 明確文件測試、觀察窗口與案例卡不得外推到 runtime、使用者理解或生成報告母體 |
| 3 | 批判思考 | #謬誤 | 完成 | 將測試綠燈謬誤、樣本數謬誤與案例代表性謬誤寫成護欄 |
| 3 | 批判思考 | #來源品質 | 完成 | 將高品質來源、次級來源與不得作為完成證據分級 |
| 3 | 批判思考 | #情境脈絡 | 完成 | 限定護欄只適用於契約相關變更，並標出人工 review 與 runtime/使用者研究邊界 |
| 3 | 批判思考 | #批判 | 完成 | 批判矩陣過重風險，區分必留護欄、可短句替代與可延後工具化 |
| 3 | 批判思考 | #估算 | 完成 | 估算低風險 UI、混合層報告呈現與高風險契約的完成回報成本 |
| 3 | 批判思考 | #詮釋框架 | 完成 | 建立文件契約通過、觀察窗口、runtime 驗證與使用者研究的完成回報詮釋框架 |
| 3 | 批判思考 | #合理性 | 完成 | 以第 3 輪契約矩陣能力、人工判斷邊界與不新增自動選測腳本作為合理收尾 |
| 3 | 批判思考 | #可驗證性 | 完成 | 建立第 3 輪批判思考 26/26 收尾 checkpoint 與下一分類入口 |
| 3 | 創意思考 | #學習科學 | 完成 | 契約矩陣創意學習入口用三層學習路徑降低第一次使用負擔 |
| 3 | 創意思考 | #限制條件 | 完成 | 明確不改 runtime、不新增自動選測腳本、不新增遙測、不替代人工 review |
| 3 | 創意思考 | #類比 | 完成 | 用登機前安檢類比快速通道、人工複檢與證據托盤 |
| 3 | 創意思考 | #演算法 | 完成 | 將學習入口轉成判斷、選通道、裝證據托盤、完成回報四步操作 |
| 3 | 創意思考 | #設計思考 | 完成 | 分出低風險 UI、報告模板或正文呈現、高風險契約三個操作者情境 |
| 3 | 創意思考 | #捷思法 | 完成 | 建立核心契約詞先人工複檢、只在前端顯示才快速通道、缺限制句不得完成三條規則 |
| 3 | 創意思考 | #最佳化 | 完成 | 將錯選通道、漏跑命令、限制句缺漏與案例卡漏補定義為採用摩擦 |
| 3 | 創意思考 | #假說發展 | 完成 | 建立四步操作、證據托盤、三條快速規則的三個可觀察假說 |
| 3 | 創意思考 | #資料視覺化 | 完成 | 用綠色、黃色、紅色採用訊號板呈現人工觀察結果 |
| 3 | 創意思考 | #建模 | 完成 | 建立四類代表性案例模型 |
| 3 | 創意思考 | #抽樣 | 完成 | 定義每個觀察窗口的代表性抽樣與黃色/紅色必抽規則 |
| 3 | 創意思考 | #個案研究 | 完成 | 建立案例卡格式與不可外推欄位 |
| 3 | 創意思考 | #比較組 | 完成 | 建立基準組與介入組比較設計 |
| 3 | 創意思考 | #介入研究 | 完成 | 定義改檔前案例模型選擇、三欄回報與補救回放 |
| 3 | 創意思考 | #訪談調查 | 完成 | 建立三題操作者回饋題 |
| 3 | 創意思考 | #觀察研究 | 完成 | 建立第 3 輪觀察記錄欄位 |
| 3 | 創意思考 | #研究複製 | 完成 | 建立複製檢查清單與可複製完成條件 |
| 3 | 溝通思考 | #受眾 | 完成 | 分出四種讀者角色 |
| 3 | 溝通思考 | #組成 | 完成 | 建立四步讀者入口組成 |
| 3 | 溝通思考 | #語意含義 | 完成 | 定義讀者角色、入口、觀察欄位與複製成功的語意邊界 |
| 3 | 溝通思考 | #組織結構 | 完成 | 契約矩陣第 3 輪維護導覽建立章節導覽 |
| 3 | 溝通思考 | #專業性 | 完成 | 維護語氣限制觀察窗口、未跑命令、紅色訊號與測試綠燈的可宣稱範圍 |
| 3 | 溝通思考 | #論點 | 完成 | 核心主張收斂為低風險更快收尾、高風險更早升級、觀察可複製但不誤讀 |
| 3 | 溝通思考 | #溝通設計 | 完成 | 契約矩陣第 3 輪短版回報建立一頁摘要 |
| 3 | 溝通思考 | #表達 | 完成 | 建議句型固定通道、命令與不得解讀為 |
| 3 | 溝通思考 | #媒介 | 完成 | 決定文字與表格優先，不新增圖像流程 |
| 3 | 溝通思考 | #多媒體 | 完成 | 暫不新增圖像或多媒體，保留可搜尋文字、pytest 與人工 review |
| 3 | 互動思考 | #倫理考量 | 完成 | 契約矩陣第 3 輪倫理阻擋建立短版回報倫理底線 |
| 3 | 互動思考 | #倫理勇氣 | 完成 | 必要時說不：缺證據停止合併、交易指令補責任邊界、高風險降級回人工複檢 |
| 3 | 互動思考 | #倫理判斷 | 完成 | 建立允許回報、禁止回報與升級判斷 |
| 3 | 互動思考 | #複雜因果 | 完成 | 建立局部綠燈因果圖，限制文件、前端測試與倫理阻擋的跨層誤推 |
| 3 | 互動思考 | #湧現特性 | 完成 | 記錄快速通道累積、案例卡增加但驗證減少、阻擋規則不敢啟用三種湧現風險 |
| 3 | 互動思考 | #分析層次 | 完成 | 區分文件層、測試層、runtime 層與使用者行為層 |
| 3 | 互動思考 | #網絡 | 完成 | 建立第 3 輪維護網絡，連接文件、測試、runtime、使用者行為與 reviewer 阻擋節點 |
| 3 | 互動思考 | #系統動力學 | 完成 | 記錄快速通道、案例卡、阻擋勇氣與跨層宣稱四個動態回路 |
| 3 | 互動思考 | #系統圖像 | 完成 | 建立先定位證據層、再連節點、接著判斷回路、最後同層宣稱或升級驗證的操作圖像 |
| 3 | 互動思考 | #談判 | 完成 | 建立補證據協商句型，保留同層宣稱但不降低跨層證據標準 |
| 3 | 互動思考 | #說服 | 完成 | 建立先承認證據、再指出缺口、接著提出最小補證據、最後寫限制句的說服路徑 |
| 3 | 互動思考 | #形塑行為 | 完成 | 建立完成回報預設三欄與黃色、紅色、跨層宣稱的預設升級行為 |
| 3 | 互動思考 | #從眾 | 完成 | 建立第 3 輪防從眾檢查，禁止多數同意、前例綠燈、測試全綠與合併壓力取代證據 |
| 3 | 互動思考 | #差異 | 完成 | 建立差異訊號清單，保留改動層級、證據層、pipeline 模式與風險顏色差異 |
| 3 | 互動思考 | #情緒智商 | 完成 | 建立高壓語氣處理，先命名壓力來源，再回到預設三欄與最小補證據路徑 |
| 3 | 互動思考 | #領導原則 | 完成 | 建立證據領導，要求主責、review 主導者與合併者分別維持宣稱層級、升級權與紅黃訊號處理 |
| 3 | 互動思考 | #權力動態 | 完成 | 建立權力護欄，禁止合併權限、資深度或權威催促取代證據層與預設三欄 |
| 3 | 互動思考 | #責任 | 完成 | 建立角色責任，讓改動者、reviewer、合併者分別負責證據、限制句、未跑命令與剩餘風險 |
| 3 | 互動思考 | #自我覺察 | 完成 | 建立輕量使用邊界，避免角色責任變成形式簽核或自動審核假象 |
| 3 | 互動思考 | #制定策略 | 完成 | 以 20/20 收尾第 3 輪互動思考，下一步進入三習慣綜合優化 |
| 綜合 | 三習慣綜合優化 | #可驗證性 | 完成 | 建立驗證閘門，要求完成宣稱對應命令、證據層或限制句 |
| 綜合 | 三習慣綜合優化 | #溝通設計 | 完成 | 建立完成回報格式，固定本次宣稱層級、已補證據、仍不得解讀為與下一個可執行行動 |
| 綜合 | 三習慣綜合優化 | #系統圖像 | 完成 | 建立前端顯示層、報告呈現層、機器契約層與維運決策層的系統圖像收斂 |
| 綜合 | 三習慣綜合優化 2 | #證據基礎 | 完成 | 建立證據來源分級，區分直接證據、間接證據、缺口證據與未跑命令 |
| 綜合 | 三習慣綜合優化 2 | #受眾 | 完成 | 建立讀者角色分流，讓不同維護者先讀對應入口 |
| 綜合 | 三習慣綜合優化 2 | #責任 | 完成 | 建立責任承接，讓改動者、reviewer、合併者分別承擔證據、誤讀與剩餘風險 |
| 綜合 | 三習慣綜合優化 3 | #偏誤降低 | 完成 | 建立偏誤防線，防止表格打勾、證據漂白、升級逃避與流程膨脹 |
| 綜合 | 三習慣綜合優化 3 | #學習科學 | 完成 | 建立速學入口，用 10 秒定位、90 秒分流、5 分鐘復盤降低採用成本 |
| 綜合 | 三習慣綜合優化 3 | #制定策略 | 完成 | 建立策略收斂，保留輕量通道、升級高顯著性、刪減膨脹規則 |
| 綜合 | 三習慣綜合優化 4 | #目的 | 完成 | 建立目標校準，要求矩陣服務股票研究系統核心目標 |
| 綜合 | 三習慣綜合優化 4 | #效用 | 完成 | 建立效用門檻，要求規則降低錯選模式、漏跑命令、跨層外推或維護成本 |
| 綜合 | 三習慣綜合優化 4 | #合理性 | 完成 | 建立合理性審核，固定必要性、比例性、可驗證性與可逆性 |
| 綜合 | 三習慣綜合優化 5 | #限制條件 | 完成 | 建立限制邊界，分出硬限制、軟限制、升級限制與停用限制 |
| 綜合 | 三習慣綜合優化 5 | #決策樹 | 完成 | 建立四步分流決策，依改動層級、顯著性、證據缺口選處理方式 |
| 綜合 | 三習慣綜合優化 5 | #最佳化 | 完成 | 建立成本最佳化，保留輕量通道、合併重複規則、刪除低效用規則 |
| 綜合 | 三習慣綜合優化 6 | #來源品質 | 完成 | 建立來源分級，區分高可信來源、可用但有限來源、不得作為完成證據與缺口來源 |
| 綜合 | 三習慣綜合優化 6 | #情境脈絡 | 完成 | 建立適用情境，分開低風險文件、報告語意、機器契約與維運決策 |
| 綜合 | 三習慣綜合優化 6 | #批判 | 完成 | 建立批判反證，要求規則回答失效情境、證據層級與刪減可能 |
| 綜合 | 三習慣綜合優化 7 | #估算 | 完成 | 建立把握估算，區分高把握、中把握、低把握與不得宣稱 |
| 綜合 | 三習慣綜合優化 7 | #信賴區間 | 完成 | 建立信心邊界，要求標示適用層級、證據覆蓋與剩餘不確定 |
| 綜合 | 三習慣綜合優化 7 | #詮釋框架 | 完成 | 建立解讀框架，分成已驗證、有限支持、暫定假設與未證明 |
| 綜合 | 三習慣綜合優化 8 | #相關性 | 完成 | 建立關聯檢核，分出強支撐、弱支撐、衝突支撐與無關 |
| 綜合 | 三習慣綜合優化 8 | #描述統計 | 完成 | 建立分布摘要，描述完成分布、缺口分布、驗證分布與風險分布 |
| 綜合 | 三習慣綜合優化 8 | #顯著性 | 完成 | 建立顯著性門檻，分出升級、保留、降級與刪減訊號 |
| 綜合 | 三習慣綜合優化 9 | #機率 | 完成 | 建立概率語言，分出高可能、中可能、低可能與未知或不得推定 |
| 綜合 | 三習慣綜合優化 9 | #迴歸 | 完成 | 建立迴歸風險，檢查回到過度宣稱、跨層外推、流程膨脹與弱證據升級 |
| 綜合 | 三習慣綜合優化 9 | #謬誤 | 完成 | 建立謬誤防線，阻止相關當因果、測試當 runtime 安全、文件完整當使用者理解、歷史紀錄當新證據 |
| 綜合 | 三習慣綜合優化 10 | #合理性 | 完成 | 建立合理性收尾，確認十次綜合優化仍服務核心目標與契約安全邊界 |
| 綜合 | 三習慣綜合優化 10 | #可驗證性 | 完成 | 建立驗證門檻，要求聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節 |
| 綜合 | 三習慣綜合優化 10 | #制定策略 | 完成 | 建立完成後維護策略，採文件與測試契約優先、例外升級與定期複檢 |

## 第 1 輪批判思考第一批

### 第 1 輪 / 批判思考 / #拆解問題

狀態：完成

本次使用：把「自主優化」拆成可保存、可驗證、可繼續的工作單位，避免一次性大改造成不可審查的變更。

核心判斷

1. 既有狀態表已完成四大類批次收斂，但未能證明每個 HCS 單項習慣都有獨立落地。
2. 專案規模很大，直接重構程式碼會提高風險；先建立嚴格輪巡紀錄，讓後續修改有清楚檢查點。
3. 最小可逆切入點是文件與文件契約測試，不改動 runtime 行為。

落地修改

1. 新增 `docs/hcs-plus-strict-habit-log.md`，把完整 HCS 單項清單與本批次狀態拆出。
2. 在主狀態表新增嚴格單項輪巡入口，避免後續只看舊的四大類摘要。

優化說明

1. 解決「已完成類別但未完成單項」的追蹤落差。
2. 犧牲的是短期看不到產品功能改變；換來後續每批修改可審查、可接續。
3. 風險是流程文件本身也可能變成形式主義，因此下一步需用測試鎖住最低內容。

驗證方式

- `tests/test_hcs_plus_state.py` 檢查主狀態表有引用嚴格輪巡附件，且附件列出全部 HCS 單項習慣。

### 第 1 輪 / 批判思考 / #問對問題

狀態：完成

本次使用：把接下來的優化從「想改什麼」轉成「哪個決策最影響專案可靠性」。

核心判斷

1. 目前最高影響問題不是新增功能，而是如何降低報告、前端模式、資料可信度與維運文件之間的漂移。
2. 下一批若直接改 UI，可能繞過資料與報告契約；若只改文件，可能沒有使用者可感的進步。
3. 最佳暫定路線是「文件契約 + 小型測試 + 一個實際體驗修正」輪流推進。

落地修改

1. 新增本輪暫定決策：嚴格輪巡每批最多處理 3 到 5 個單項習慣，並至少補一個自動化檢查。
2. 將下一個待決問題寫入本文件：下一批要優先降低偏誤、建立決策樹，還是先收斂目的/效用。

需要你決定

1. 下一批優先方向
A. 先補齊批判思考剩餘習慣的文件與測試護欄
B. 先找一個前端或報告的小型使用者體驗問題落地修正
C. 先做資料可信度或 provider contract 的程式碼改善
建議：B，因為本批次已建立流程護欄，下一批應讓使用者可感的系統品質也跟上。

驗證方式

- 本文件保留決策題與建議選項；若使用者未回答，下一批採用建議 B 並在主狀態表記為暫定決策。

### 第 1 輪 / 批判思考 / #差距分析

狀態：完成

本次使用：比較現況與目標，找出最值得先補的缺口。

核心判斷

1. 現況：`docs/frontend-design-checkpoints.md` 與 `docs/pipeline-mode-contract.md` 已降低 UI/報告模式漂移。
2. 目標：每次自主優化都能說清楚修改位置、驗證方式、下一個檢查點。
3. 缺口：HCS 狀態沒有自動化檢查，且後續嚴格單項輪巡若只靠人工記憶，很容易漏項。

落地修改

1. 新增缺口矩陣作為後續排序依據。
2. 新增 `tests/test_hcs_plus_state.py`，用自動化測試檢查嚴格輪巡清單與第一批完成項。

缺口矩陣

| 目標 | 現況 | 缺口 | 本批處理 |
|---|---|---|---|
| HCS 單項不漏項 | 只有四大類摘要 | 單項清單未被測試鎖住 | 新增嚴格輪巡附件與測試 |
| 修改可追蹤 | 舊摘要列出檔案 | 單項習慣沒有獨立紀錄 | 第一批 5 個習慣逐項記錄 |
| 驗證可重跑 | 多數產品契約已有測試 | HCS 流程文件無測試 | 新增文件契約測試 |

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_strict_habit_log_lists_every_habit`
- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`

### 第 1 輪 / 批判思考 / #變數分析

狀態：完成

本次使用：列出最可能改變優化判斷的變數，避免把單一 UI 或文件問題誤當成全域問題。

核心判斷

1. 系統可靠性由多個變數共同決定：資料來源、pipeline 模式、報告模板、任務佇列、前端呈現、維運文件與測試覆蓋。
2. 同一個修改若影響 pipeline、報告與前端三層，需優先補契約測試。
3. 若變數屬於使用者行為，例如操作者如何選模式，則應優先改善文案、狀態提示與下一步引導。

落地修改

1. 新增 HCS 變數清單，後續每批優化都先標記影響哪幾個變數。
2. 將本批次影響變數標為 `流程可追蹤性`、`測試覆蓋`、`文件一致性`。

變數清單

| 變數 | 影響 | 後續檢查 |
|---|---|---|
| 資料來源可用性 | 影響 data confidence、target price guardrail 與 provider SLA | `tests/test_provider_capabilities.py`、`tests/test_free_mode_contract.py` |
| Pipeline 模式語意 | 影響 UI 選擇、報告模板與 watchlist rerun | `tests/test_report_mode_templates.py`、`tests/test_static_history_filters.py` |
| 報告證據鏈 | 影響數字主張、投資建議與人工信任 | `tests/test_evidence_exit_gate.py`、`tests/test_report_conformance.py` |
| 前端掃讀性 | 影響操作者是否選對模式與是否注意 stale report | `tests/test_static_history_filters.py`、optional visual regression |
| 流程可追蹤性 | 影響 HCS 優化能否接續 | `tests/test_hcs_plus_state.py` |

驗證方式

- 本文件把本批次影響變數與現有測試檔對應，下一批不得只寫抽象建議。

### 第 1 輪 / 批判思考 / #偏誤辨識

狀態：完成

本次使用：找出自主優化最容易出現的判斷偏誤，並建立最低護欄。

核心判斷

1. 最大偏誤是「文件完成感」：寫了漂亮狀態表卻沒有防止漏項或回退。
2. 第二個偏誤是「最近性偏誤」：只因前一輪做前端，就假設下一輪也該繼續前端。
3. 第三個偏誤是「測試可得性偏誤」：只挑容易測的內容，而忽略使用者實際工作流痛點。

落地修改

1. 新增偏誤風險清單，明確要求下一批至少選一個使用者可感的品質改動。
2. 新增文件契約測試，防止 HCS 單項清單與第一批落地紀錄消失。

偏誤護欄

| 偏誤 | 失敗徵兆 | 護欄 |
|---|---|---|
| 文件完成感 | 只有紀錄，沒有測試或產品改動 | 每批至少一個可重跑驗證 |
| 最近性偏誤 | 永遠沿著上一輪主題微調 | 每批先重看 README、架構與近期測試缺口 |
| 測試可得性偏誤 | 只補容易 assert 的字串 | 至少列出一個使用者可感檢查點 |
| 自動化過度自信 | 測試通過就宣稱整體優化完成 | 未完成 3 輪單項巡迴前不得宣稱 HCS Plus 完成 |

驗證方式

- `tests/test_hcs_plus_state.py` 確認第一批完成項都有 `核心判斷`、`落地修改`、`驗證方式` 與 `狀態：完成`。

## 第 1 輪批判思考第二批

### 第 1 輪 / 批判思考 / #偏誤降低

狀態：完成

本次使用：把上一批辨識出的「文件完成感」與「最近性偏誤」轉成具體防護，避免新文件範例和模式契約各說各話。

核心判斷

1. `README.md` 與 `docs/api.md` 的 `POST /api/analysis-jobs` 範例仍使用 `pipeline_id:"mode_a"` alias，和目前 `v1` 到 `v4` 的模式契約不一致。
2. 後端保留 alias 是相容性，不代表新文件應繼續推廣 alias。
3. 最小偏誤降低方式是把文件範例改成 canonical id，並用 docs contract 測試鎖住。

落地修改

1. 將 `README.md` 與 `docs/api.md` 的分析任務範例改為 `pipeline_id:"v1"`。
2. 在 `docs/pipeline-mode-contract.md` 增加規則：新整合與文件範例使用 `v1` / `v2` / `v3` / `v4`，alias 只作相容輸入。
3. 新增 `tests/test_docs_contract.py::test_analysis_job_docs_use_canonical_pipeline_ids`。

優化說明

1. 降低新整合者照文件使用 alias 後，誤以為 `mode_a` 是主要公開契約的風險。
2. 犧牲的是少了一點「舊名稱較直覺」的便利；但 UI 與契約文件已用中文模式名稱補足語意。
3. 保留後端 alias 相容，不破壞現有腳本。

驗證方式

- `tests/test_docs_contract.py::test_analysis_job_docs_use_canonical_pipeline_ids`

### 第 1 輪 / 批判思考 / #決策樹

狀態：完成

本次使用：在三個候選路徑中選擇本批修改：前端體驗、資料可信度或文件契約。

核心判斷

1. 前端體驗修改需要瀏覽器或截圖驗證，適合下一批搭配 visual/DOM 檢查。
2. 資料可信度修改會碰 provider 或 report runtime，風險較高，不適合作為嚴格輪巡剛啟動後的第二步。
3. 文件契約修改最小、可逆、可測，且直接對齊已建立的 `docs/pipeline-mode-contract.md`。

落地修改

1. 採用「文件契約先行」路徑，修改 README/API/模式契約三處。
2. 把決策樹寫入本紀錄，作為下次遇到類似漂移時的選擇依據。

決策樹

| 條件 | 選擇 |
|---|---|
| 發現的是公開文件與既有契約不一致 | 先修文件範例，補 docs contract 測試 |
| 發現的是 UI 文案與資料狀態不一致 | 先修前端，補 DOM/視覺檢查 |
| 發現的是資料可信度或 report guardrail 不一致 | 先補 failing backend test，再改 runtime |

驗證方式

- `tests/test_docs_contract.py` 確保 canonical pipeline id 規則存在於 README、API 參考與模式契約。

### 第 1 輪 / 批判思考 / #目的

狀態：完成

本次使用：把本批修改目的從「整理文件」收斂成使用者結果。

核心判斷

1. 使用者要的是能照文件建立正確分析任務，而不是理解所有 alias 歷史。
2. 文件範例應教 canonical path；相容 alias 只該出現在後端測試或遷移說明。
3. 對本地操作者而言，`v1` 對應模式 A 的關係已由 pipeline mode contract 承擔。

落地修改

1. README 與 API 參考的新任務範例改用 canonical `v1`。
2. 模式契約新增「文件與新整合範例一律使用 canonical pipeline ids」的目的說明。

驗證方式

- docs contract 測試檢查文件含有 `"pipeline_id":"v1"`，且不再含有 `"pipeline_id":"mode_a"`。

### 第 1 輪 / 批判思考 / #效用

狀態：完成

本次使用：衡量本批修改的效用、代價與剩餘風險。

核心判斷

1. 效用：降低 API 使用者照抄文件後產生 ID 語意混亂的機率。
2. 代價：沒有新增產品功能；這是一次低風險一致性修正。
3. 剩餘風險：測試目前只鎖住 `mode_a` 範例，其他 alias 若未來出現在文件，需再擴充測試。

落地修改

1. 將本批效用與剩餘風險寫入 HCS 嚴格紀錄，避免把測試通過誤認為整體流程完成。
2. 主狀態表更新第二批已完成與下一批待辦。

驗證方式

- `tests/test_hcs_plus_state.py` 檢查第二批四個習慣也有獨立的核心判斷、落地修改與驗證方式。

## 第 1 輪批判思考第三批

### 第 1 輪 / 批判思考 / #信賴區間

狀態：完成

本次使用：檢查操作者看到任務狀態時，是否能對「這是哪一種分析」形成足夠信心。

核心判斷

1. Active jobs panel 原本顯示 raw `pipeline_id`，例如 `v1`、`v4`；這對熟悉契約的人可讀，但對日常操作者信心不足。
2. 既有 `StockAgentUi.pipelineModeLabel` 已能輸出「模式 A · 學術深度派」等語意，不應只用在 history/watchlist。
3. 將 active jobs 接上共用 label 可以縮小操作者對任務類型的理解區間。

落地修改

1. `backend/static/active_jobs_panel.js` 新增 `pipelineModeLabel` option 與 `StockAgentUi.pipelineModeLabel` fallback。
2. `backend/static/ops_workspace.js` 呼叫 active jobs render 時傳入 `ui.pipelineModeLabel`。
3. `tests/test_static_history_filters.py` 新增合約檢查，防止 active jobs 回退成 raw pipeline id 顯示。

優化說明

1. 解決 active jobs 與其他模式顯示元件語意不一致的問題。
2. 代價很低：只改前端顯示，不改 API payload 或 job store。
3. 剩餘風險是 operator summary 的簡短卡片仍只顯示 ticker；若後續需要，可再加入目前任務模式摘要。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #相關性

狀態：完成

本次使用：避免操作者把 raw pipeline id 與任務狀態直接關聯，誤以為 `v1` / `v4` 是狀態或優先級，而不是分析模式。

核心判斷

1. Active job chip 同時顯示 ticker、pipeline、status、stage；raw `v1` 容易被看成內部狀態碼。
2. 共用模式 label 把 `pipeline_id` 和分析目的連起來，降低錯誤關聯。
3. 相關性護欄應落在 UI helper 共用，而不是在 active jobs panel 再寫一份 label map。

落地修改

1. Active jobs panel 不新增獨立模式表，改用 `pipelineModeLabel` 注入。
2. 前端契約測試要求 active jobs panel 與 ops workspace 有共用 label 接線。

驗證方式

- 測試檢查 `active_jobs_panel.js` 包含 `pipelineModeLabel`，且 `ops_workspace.js` 傳入 `pipelineModeLabel: ui.pipelineModeLabel`。

### 第 1 輪 / 批判思考 / #描述統計

狀態：完成

本次使用：檢查任務列表摘要是否保留最小有效統計資訊，而不是加入太多欄位造成掃讀負擔。

核心判斷

1. Active jobs 的摘要重點是任務數、ticker、模式、狀態、階段進度與 LLM retry/error 訊號。
2. 既有 panel 已刻意不顯示 token estimate，避免把估算數字當成精準成本。
3. 本批只替換 pipeline 顯示文字，不增加額外統計欄位，保留原本密度。

落地修改

1. 保留 `llmSummary()`、`progressLabel()` 與 summary count 的既有行為。
2. 只把 job chip 的第二段從 raw id 改成共用模式 label。

驗證方式

- 前端合約測試仍要求 `token_estimate` 與 `估算 token` 不出現在 active jobs panel，並新增模式 label 接線要求。

## 第 1 輪批判思考第四批

### 第 1 輪 / 批判思考 / #機率

狀態：完成

本次使用：檢查決策回測的命中率呈現，避免把少量樣本的百分比讀成穩定機率。

核心判斷

1. Performance panel 原本顯示 `命中率 / 平均 ROI / N 筆`，少量樣本也會以同樣語氣呈現。
2. 對本機研究工作台而言，早期回測多半樣本少；命中率應被視為觀察訊號，不是穩定勝率。
3. 最小修正是在 summary 與 horizon chip 加上樣本信心標籤。

落地修改

1. `backend/static/performance_panel.js` 新增 `sampleConfidenceLabel(total)`。
2. Summary 顯示加入 `樣本不足，僅供觀察`、`樣本基礎可追蹤` 或 `尚無樣本`。
3. Horizon chip 的命中率旁同步顯示樣本信心。

優化說明

1. 解決百分比在小樣本下過度精準的閱讀風險。
2. 犧牲的是 summary 變長；但保留同一行密度，沒有新增額外卡片。
3. 目前 10 筆門檻是產品護欄，不是統計顯著性證明。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #迴歸

狀態：完成

本次使用：檢查回測結果是否被 UI 暗示成可外推趨勢。

核心判斷

1. `average_strategy_roi_pct` 是歷史已到期決策的平均結果，不等於下一次報告的預測報酬。
2. 小樣本下高 ROI 容易受單一極端案例影響，不能當成模式品質已穩定的迴歸趨勢。
3. UI 只需要提醒「樣本基礎」即可，不應在前端臨時計算複雜統計模型。

落地修改

1. Performance panel 保留原本平均 ROI，但在同一 summary 補上樣本信心。
2. Horizon chip 以 `total >= 10` 才使用 `is-ok` 語氣，少量樣本維持 warning。

驗證方式

- 前端契約測試檢查 `performance_panel.js` 有 `sampleConfidenceLabel` 與 `total >= 10` 門檻。

### 第 1 輪 / 批判思考 / #顯著性

狀態：完成

本次使用：把「是否足以採信」轉成明確的 UI 文案，而不是讓使用者自行從樣本數推斷。

核心判斷

1. UI 不應宣稱統計顯著；目前資料也沒有 confidence interval 或 p-value。
2. 10 筆以下使用「樣本不足，僅供觀察」比「低信心」更準確，因為不是資料錯誤，而是樣本量不足。
3. 10 筆以上也只標示「樣本基礎可追蹤」，避免過度承諾。

落地修改

1. `tests/test_static_history_filters.py` 新增靜態契約，要求樣本不足文案與門檻保留。
2. HCS 狀態測試擴充到 `#機率`、`#迴歸`、`#顯著性`。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪批判思考第五批

### 第 1 輪 / 批判思考 / #證據基礎

狀態：完成

本次使用：檢查使用者打開報告 preview 時，是否仍能看到證據抽查與報告符合性的品質訊號。

核心判斷

1. History 清單已有 `evidence_exit_gate` 與 `report_conformance` 的警示 badge。
2. Preview 頂部原本只顯示模式、資料信任與日期；使用者一打開 preview，品質警示會從視覺焦點消失。
3. 證據基礎應在 preview 入口保留，而不是只存在 history list 或完整報告內文。

落地修改

1. `backend/static/report_preview_panel.js` 新增 `reportQualityBadge(report, escapeHtml)`。
2. Preview mode row 會在資料信任 badge 後顯示「報告符合性未通過」、「報告符合性需確認」、「證據抽查未通過」或「數字證據需人工核對」。
3. 重用既有 `.history-action-badge` 樣式，不新增 CSS。

優化說明

1. 解決證據/符合性警示在 preview 中斷的問題。
2. 犧牲是 preview 頂部 chip 可能多一個；但只在有警示時出現。
3. 剩餘風險是完整 preview 尚未顯示 failed claim 明細；目前先提供採用前警示。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #演繹

狀態：完成

本次使用：避免使用者從「報告可預覽」演繹出「報告已可直接採用」。

核心判斷

1. Preview 是閱讀入口，不是品質核准。
2. 如果 conformance blocked 或 evidence rejected，preview 仍可用來檢查問題，但不能讓 UI 語氣像一般報告。
3. 將品質徽章放在 preview 頂部，可以把「可讀」與「可採用」拆開。

落地修改

1. `reportQualityBadge()` 優先顯示 report conformance，再顯示 evidence exit gate，對齊 history/operator summary 的行動優先序。
2. Preview 內 `elements.mode.innerHTML` 納入品質徽章。

驗證方式

- 前端契約測試檢查 `report_preview_panel.js` 包含 `reportQualityBadge`、`證據抽查未通過`、`報告符合性未通過`。

### 第 1 輪 / 批判思考 / #歸納

狀態：完成

本次使用：從多個工作台視圖歸納品質訊號的一致呈現規則。

核心判斷

1. History、operator summary 與 preview 都是操作者判斷報告能不能採用的入口。
2. 若只有 history 顯示品質警示，使用者可能在 preview 內忽略同一份報告的風險。
3. 品質警示應跨視圖一致，但不需要每個視圖都顯示完整明細。

落地修改

1. Preview 與 history 共享同樣的警示文字與 tone 類型。
2. `tests/test_static_history_filters.py` 把 preview 納入 evidence/conformance 靜態契約。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪批判思考第六批

### 第 1 輪 / 批判思考 / #謬誤

狀態：完成

本次使用：檢查工作台摘要是否可能讓使用者犯「單一可信度」謬誤，把資料新鮮度、來源健康、報告符合性與證據抽查混成同一種判斷。

核心判斷

1. Operator summary 原本用 `fresh / sampled` 呈現資料狀態，語氣偏內部監控，不像操作者決策語言。
2. `fresh` 容易被誤讀成整份報告都可信；但實際上它只代表資料信任狀態的一部分。
3. 使用中文脈絡能降低把來源健康與結論可信度混淆的風險。

落地修改

1. `backend/static/operator_summary_panel.js` 將 `fresh ${fresh} / sampled ${reports.length}` 改為 `資料新鮮 ${fresh} / 抽樣 ${reports.length}`。
2. `tests/test_static_history_filters.py` 新增不允許舊 `fresh / sampled` 文案的契約。

優化說明

1. 解決 operator summary 中內部英文監控語氣外露的問題。
2. 不改動計算邏輯，只改顯示語意。
3. 剩餘風險是其他 dashboard 仍可能使用英文/內部欄位名稱，需後續逐步掃描。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #來源品質

狀態：完成

本次使用：讓來源提醒與需要重跑/刷新資料的狀態分開。

核心判斷

1. `provider_sla_critical` 型 partial 可能只是來源健康提醒，不一定代表該報告需要刷新或重跑。
2. Operator summary 已有「無需刷新/重跑」語意，但後面接 `fresh / sampled` 會削弱脈絡。
3. 來源品質提示應同時告訴使用者「這是來源層提醒」與「目前不需採取刷新/重跑動作」。

落地修改

1. 來源提醒 detail 改為 `無需刷新/重跑 · 資料新鮮 ${fresh} / 抽樣 ${reports.length}`。
2. 前端契約測試鎖定中文資料新鮮/抽樣文案。

驗證方式

- `tests/test_static_history_filters.py` 檢查 operator summary 包含 `資料新鮮 ${fresh} / 抽樣 ${reports.length}` 並排除舊字串。

### 第 1 輪 / 批判思考 / #情境脈絡

狀態：完成

本次使用：補足 operator summary 的樣本範圍脈絡，避免使用者以為摘要是全庫完整統計。

核心判斷

1. Operator summary 只讀近期報告樣本，不是所有歷史報告。
2. 用「抽樣」比 `sampled` 更貼近操作者語境，也提醒這是摘要視窗。
3. 這與 performance panel 的樣本信心一致：數字要帶著樣本脈絡出現。

落地修改

1. 將 operator summary 的 detail 統一為中文「資料新鮮 / 抽樣」格式。
2. HCS 狀態測試擴充到 `#謬誤`、`#來源品質`、`#情境脈絡`。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪批判思考第七批

### 第 1 輪 / 批判思考 / #批判

狀態：完成

本次使用：質疑 UI 中「健康正常」是否暗示系統掌握外部 provider 真實健康，而不是只有本機觀測。

核心判斷

1. API quota panel 與 operator summary 原本用「LLM/API 健康」或「LLM 健康正常」描述無錯誤狀態。
2. 這容易讓使用者以為供應商本身狀態已被完整驗證；實際上只是本機觀測到的設定與錯誤次數。
3. 更準確的框架是「本機觀測」，有錯誤時才用健康警示。

落地修改

1. `backend/static/api_quota_panel.js` 將無錯誤 summary 改為 `LLM/API 本機觀測：...`。
2. `backend/static/operator_summary_panel.js` 將 `LLM 健康正常` 改為 `LLM 本機觀測正常`。

優化說明

1. 降低把本機統計誤認為供應商 SLA 事實的風險。
2. 保留 `LLM/API 健康警示`，因為錯誤狀態對操作者仍需快速辨識。
3. 剩餘風險是頁籤標題仍使用「LLM 健康」，這是導覽名；目前先修 summary 與 operator card 的判斷語氣。

驗證方式

- `tests/test_static_history_filters.py::test_operator_signals_avoid_misleading_health_and_tracking_copy`

### 第 1 輪 / 批判思考 / #估算

狀態：完成

本次使用：檢查 API quota 數字是否被當成精準供應商狀態，而不是本機觀測估算。

核心判斷

1. API quota 只統計本機觀測到的 requests、errors、reset 與 key count。
2. 無錯誤不代表 provider 全域健康；只代表目前本機觀測沒有錯誤訊號。
3. 「本機觀測」比「健康」更能承載估算/觀測的限制。

落地修改

1. 前端靜態契約要求 `api_quota_panel.js` 包含 `LLM/API 本機觀測：`。
2. 測試同時排除 `LLM/API 健康：` 的無錯誤 summary 字串。

驗證方式

- `tests/test_static_history_filters.py::test_operator_signals_avoid_misleading_health_and_tracking_copy`

### 第 1 輪 / 批判思考 / #詮釋框架

狀態：完成

本次使用：調整使用者詮釋 API quota 面板的框架，從「健康證明」改成「本機觀測視窗」。

核心判斷

1. 使用者在維運頁看到的是本機工作台視角，不是 provider 控制台。
2. `LLM 本機觀測正常` 保留可掃讀性，同時提醒這不是全面 SLA。
3. 這和 provider SLA 面板的「觀測窗口 / 檢查樣本」語氣一致。

落地修改

1. `operator_summary_panel.js` 的 LLM 卡片使用「本機觀測正常」框架。
2. `tests/test_static_history_filters.py` 把這個框架納入 operator signals 測試。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_operator_signals_avoid_misleading_health_and_tracking_copy`

## 第 1 輪批判思考第八批

### 第 1 輪 / 批判思考 / #合理性

狀態：完成

本次使用：檢查批判思考第 1 輪是否能合理收束，而不是把多個局部修補誤認為完整 HCS Plus。

核心判斷

1. 批判思考共有 26 個單項習慣；目前已逐項留下落地修改與驗證欄位。
2. 合理的收尾不能宣稱完整 HCS Plus 完成，因為創意、溝通、互動思考仍未完成三輪單項巡迴。
3. 下一步應明確切到創意思考第一批，避免流程在批判思考尾端停住。

落地修改

1. 本文件新增「第 1 輪批判思考收尾」，標示 `已完成：26/26`。
2. 主狀態表將 `#合理性/#可驗證性` 標成完成，並新增創意思考下一批入口。
3. `tests/test_hcs_plus_state.py` 將 `#合理性` 納入完成習慣檢查。

優化說明

1. 解決流程紀錄沒有收尾檢查點的問題。
2. 犧牲的是本批沒有新增前端 runtime 行為；換來的是下一階段可接續的流程邊界。
3. 剩餘風險是完整 HCS Plus 尚很長，後續仍需每批實際改檔與驗證。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少 `#合理性` section 與收尾摘要會失敗。
- GREEN：`tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`

### 第 1 輪 / 批判思考 / #可驗證性

狀態：完成

本次使用：把「批判思考第 1 輪完成」轉成可重跑檢查，而不是只靠人工閱讀。

核心判斷

1. 已完成習慣需同時具備 `核心判斷`、`落地修改`、`驗證方式` 與 `狀態：完成`。
2. 收尾摘要需明確寫出 26/26 與下一個 HCS 入口，否則後續接續容易跳項。
3. 主狀態表與 strict log 必須一致，避免一份顯示完成、另一份仍顯示下一批。

落地修改

1. `tests/test_hcs_plus_state.py` 新增批判思考收尾檢查，要求 `已完成：26/26` 與 `下一步：第 1 輪 / 創意思考 / #學習科學`。
2. 本文件新增 `#可驗證性` 獨立紀錄與收尾摘要。
3. 主狀態表新增創意思考第一批 `#學習科學/#限制條件/#類比` 的下一批列。

優化說明

1. 讓流程完成條件能被 CI 或本機測試重跑。
2. 保留下一批只處理 3 個相近習慣的節奏，避免創意思考一開始就擴大範圍。
3. 剩餘風險是文件契約無法替代使用者實際操作驗證；後續若改 UI 仍需跑前端相關檢查。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_critical_thinking_round_has_closing_checkpoint`

## 第 1 輪批判思考收尾

已完成：26/26

已落地修改：

- 建立嚴格單項輪巡附件與 HCS 狀態測試。
- 將 pipeline id 範例收斂到 canonical `v1` 到 `v4`。
- Active jobs、performance panel、report preview、operator summary、API quota panel 已補強可讀性與證據/樣本/觀測脈絡。
- 主狀態表與 strict log 已對齊到批判思考第 1 輪完成。

驗證基準：

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`

剩餘風險：

- 尚未完成創意思考、溝通思考、互動思考的嚴格單項輪巡。
- 尚未跑完整專案測試矩陣；目前以貼近修改面的測試作為批次驗證。

下一步：第 1 輪 / 創意思考 / #學習科學

## 第 1 輪創意思考第一批

### 第 1 輪 / 創意思考 / #學習科學

狀態：完成

本次使用：把模式選擇從「讀完整規格表」改成「先回答我要做哪種決策」的學習提示。

核心判斷

1. `docs/pipeline-mode-contract.md` 已有完整對照表，但新人需要先形成可記憶的 mode 選擇入口。
2. 以決策問題作為 retrieval cue，能讓使用者先選出候選 mode，再回到詳細表格驗證。
3. 這比新增更長說明更符合學習科學：短提示、可回想、可反覆查驗。

落地修改

1. `docs/pipeline-mode-contract.md` 新增「模式選擇速記」。
2. 每個 mode 以一句決策 cue 呈現：長線納入、交易動作、過熱/避險、事件窗口、三視角交叉檢查。
3. `tests/test_docs_contract.py` 新增契約測試，防止速記層被移除。

優化說明

1. 降低新整合者和操作者第一次閱讀模式契約的認知成本。
2. 不改前端 UI，避免在工作台增加額外文字密度。
3. 剩餘風險是速記只存在文件；若後續使用者仍常選錯 mode，再評估是否進 UI。

驗證方式

- RED：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection` 先確認缺少「模式選擇速記」會失敗。
- GREEN：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection`

### 第 1 輪 / 創意思考 / #限制條件

狀態：完成

本次使用：在不增加 UI 密度、不改 backend metadata、不影響 runtime 的限制下，選擇最小可逆落點。

核心判斷

1. 目前前端已經有 mode intent 和 label，繼續塞更多文字可能傷害工作台掃讀。
2. 後端 pipeline metadata 仍有雙來源問題，但創意思考第一批不適合大改資料來源。
3. 文件契約是最小改動面：能改善學習入口，也能用現有 docs contract 測試驗證。

落地修改

1. 速記只加在 `docs/pipeline-mode-contract.md`，不改 `backend/static/ui_helpers.js`。
2. 測試只檢查文件契約必要字串，不引入新的 runtime fixture。

優化說明

1. 在限制下保留高可逆性，避免把學習提示直接塞進產品介面。
2. 犧牲的是短期產品畫面不變；收益是新文件與新整合者能更快選對 mode。
3. 後續若要進一步落地，可把這些 cue 轉成 backend/front-end shared metadata。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection`

### 第 1 輪 / 創意思考 / #類比

狀態：完成

本次使用：用「分診台」類比說明模式選擇，讓使用者先分流決策情境，再查細節。

核心判斷

1. 四個 pipeline mode 容易被看成技術版本號；類比能把它們重新框成不同決策入口。
2. 「分診台」比「菜單」更準確，因為它強調先判斷問題性質，再選流程。
3. 類比必須落在文件契約，不應取代下方精確欄位與驗收標準。

落地修改

1. 「模式選擇速記」段落新增：`這個速記像分診台`。
2. 文件說明先用決策分流，再回到表格檢查報告模板、摘要標題與證據要求。

優化說明

1. 降低 `v1/v2/v3/v4` 被誤解成版本新舊或優先級的風險。
2. 保留 canonical id 和 alias normalization 的技術邊界。
3. 剩餘風險是類比可能被過度延伸；因此下方仍保留正式模式對照表。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection`

## 第 1 輪創意思考第二批

### 第 1 輪 / 創意思考 / #演算法

狀態：完成

本次使用：把 mode 選擇從口訣推進成可照順序執行的決策樹。

核心判斷

1. 速記能幫助記憶，但仍需要一個穩定順序處理 `both`、短線事件、過熱風險、交易行動與長線研究。
2. 決策樹應先處理多報告與短效期限，因為選錯會造成最高重跑成本。
3. 文件層的演算法比 runtime 自動選 mode 更安全，因為目前仍需要操作者判斷問題脈絡。

落地修改

1. `docs/pipeline-mode-contract.md` 新增「模式選擇決策樹」。
2. `tests/test_docs_contract.py` 新增 `test_pipeline_mode_contract_has_selection_decision_tree`。

優化說明

1. 將 mode selection 從靜態表格轉成可執行步驟。
2. 不新增自動化選 mode 行為，避免在資訊不足時替使用者做投資流程判斷。
3. 剩餘風險是決策樹仍是文件規範；後續可視使用情況轉成前端輔助。

驗證方式

- RED：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree` 先確認缺少決策樹會失敗。
- GREEN：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree`

### 第 1 輪 / 創意思考 / #設計思考

狀態：完成

本次使用：從使用者任務出發排列 mode 選擇，而不是從系統代碼或內部 agent 數出發。

核心判斷

1. 使用者真正的問題是「我要做哪種決策」，不是「我要跑哪個版本」。
2. 決策樹把 `both`、`v4`、`v3`、`v2`、`v1` 排成情境順序，對應不同任務壓力。
3. 這能讓文件契約服務操作者與整合者，而不只是服務開發者。

落地修改

1. 決策樹每一步都以「如果核心問題是...」開頭。
2. 每一步附上該 mode 的檢查重點，讓使用者知道選完後要看什麼證據。

優化說明

1. 把文件從 reference 擴展成 how-to 入口，但仍保留契約表格的精確性。
2. 犧牲的是文件略長；收益是選 mode 的第一步更明確。
3. 後續若發現文件過長，可把速記與決策樹拆成獨立 how-to。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree`

### 第 1 輪 / 創意思考 / #捷思法

狀態：完成

本次使用：加入一個可接受的預設捷思，處理使用者仍不確定該選哪個 mode 的情境。

核心判斷

1. 不確定時直接選交易或短線 mode 容易讓報告偏向行動建議，但缺少基本面基準。
2. 先用 `v1` 建立基本面基準是較保守的暫定捷思，之後再視結論補跑 `v2`、`v3` 或 `v4`。
3. 捷思必須明確標成 fallback，而不是取代正式判斷。

落地修改

1. 決策樹新增：`若仍不確定，先選 v1 建立基本面基準`。
2. 測試鎖住 fallback 文字，避免後續文件回到模糊狀態。

優化說明

1. 降低新使用者卡在 mode selection 的風險。
2. 保守預設犧牲的是速度；收益是先建立較完整資料脈絡。
3. 後續若有使用者偏好，也可把 fallback 寫成可設定策略。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree`

## 第 1 輪創意思考第三批

### 第 1 輪 / 創意思考 / #最佳化

狀態：完成

本次使用：降低使用者在報告比較摘要中解讀 `v1/v2/v3/v4` 的成本。

核心判斷

1. Report compare summary 原本用 raw `pipeline_id` 顯示兩份報告，使用者需要自己把 `v1` 轉成「學術深度派」。
2. 既有共用 helper `pipelineModeLabel` 已解決其他視圖的同類問題，compare panel 應重用它。
3. 這是小範圍最佳化：不改 compare API、不改資料模型，只改選取摘要的顯示語意。

落地修改

1. `backend/static/report_compare_panel.js` 新增 `pipelineModeLabel` fallback。
2. 比較選取摘要從 `${report.pipeline_id || 'v1'}` 改為共用模式語意 label。
3. `backend/static/history_workspace.js` 將 `ui.pipelineModeLabel` 傳入 report compare panel。

優化說明

1. 減少使用者比較報告時的 mode 解碼負擔。
2. 保持顯示層改動，不影響 compare diff 計算。
3. 剩餘風險是 compare result grid 仍以 filename 呈現左右報告；後續可再評估是否加入 mode badge。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認 compare panel 缺 `pipelineModeLabel` 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #假說發展

狀態：完成

本次使用：將「比較報告前，使用者需要先辨識兩份報告的決策模式」轉成可驗證假說。

核心判斷

1. 若 compare summary 顯示可讀 mode label，使用者更容易判斷兩份報告是否同模式、跨模式或時間序列比較。
2. 該假說可以用靜態契約先驗證接線：compare panel 必須使用 `pipelineModeLabel`，且 history workspace 必須傳入 helper。
3. 若後續要驗證真實效果，可在 UI QA 中檢查 compare summary 的掃讀速度與誤解率。

落地修改

1. `tests/test_static_history_filters.py` 新增 compare panel mode label 接線契約。
2. 測試排除 raw `pipeline_id` summary template，防止回退。

優化說明

1. 先用低成本測試固定假說的最小可觀測行為。
2. 不引入 analytics 或事件追蹤，避免擴大改動面。
3. 剩餘風險是靜態測試不能保證實際 DOM 呈現；完整 UI 驗證可後續用瀏覽器測試補上。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #資料視覺化

狀態：完成

本次使用：讓比較摘要顯示對使用者有意義的 mode 視覺語意，而不是內部代碼。

核心判斷

1. `ticker · v1 · date` 的視覺資訊密度低，且 `v1` 容易被誤讀為版本或優先級。
2. `ticker · 模式 A · 學術深度派 · date` 更接近使用者做比較時需要的視覺分組。
3. 使用既有 label helper 能維持與 history、watchlist、active jobs 的一致視覺語言。

落地修改

1. `report_compare_panel.js` 的 summary 顯示改用 `pipelineModeLabel(report.pipeline_id || 'v1')`。
2. 靜態測試要求 compare panel 包含 `window.StockAgentUi?.pipelineModeLabel` fallback。

優化說明

1. 改善比較視圖的資料可視化語意，而不新增新元件或版面。
2. 犧牲的是 summary 字串略長；但比較區域只有最多兩份報告，仍可掃讀。
3. 剩餘風險是 mobile 寬度下長 label 可能換行；現有 summary 已是文字段落，風險可接受。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考第四批

### 第 1 輪 / 創意思考 / #建模

狀態：完成

本次使用：讓 report compare result 明確顯示左右報告使用的決策模型。

核心判斷

1. 比較報告時，`v1` 與 `v2` 代表不同決策模型；如果只看 filename，使用者不容易先判斷比較基準。
2. 既有 compare payload 已有 `left.pipeline_id` 與 `right.pipeline_id`，前端可直接用共用 mode label 建模。
3. 顯示「比較基準」能讓同模式時間比較與跨模式視角比較先被區分。

落地修改

1. `backend/static/report_compare_panel.js` 在 result grid 新增「比較基準」。
2. 左右基準使用 `pipelineModeLabel(left.pipeline_id || 'v1')` 與 `pipelineModeLabel(right.pipeline_id || 'v1')`。

優化說明

1. 補足比較結果的模型脈絡，避免使用者只看到數字 delta。
2. 不改後端 compare API，因為既有 payload 已足夠。
3. 剩餘風險是跨模式比較的警示仍使用 raw pipeline id；後續可再把 compatibility warning 語意化。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「比較基準」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #抽樣

狀態：完成

本次使用：讓比較結果標示兩份報告的樣本日期與時間順序。

核心判斷

1. 兩份報告比較本質上是小樣本比較，至少要看左右報告日期與時間順序。
2. compare compatibility 已有 `date_order`，但目前只出現在可比較 chip；result grid 缺少可掃讀樣本欄。
3. 「比較樣本」能提醒使用者 delta 來自哪兩個日期，而不是整體模型表現。

落地修改

1. `report_compare_panel.js` 新增「比較樣本」欄位。
2. 欄位顯示 `left.date → right.date · dateOrderLabel(compatibility.date_order)`。

優化說明

1. 強化樣本脈絡，降低把兩份報告差異過度外推的風險。
2. 不新增資料欄位，只重用現有 `date` 與 compatibility。
3. 若日期缺失會顯示 `N/A`，後續可再補後端 metadata 完整性檢查。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #個案研究

狀態：完成

本次使用：把兩份報告比較框成一個可審查個案，而不是泛化統計。

核心判斷

1. Report compare 是針對兩份具體報告的個案比較，不應被看成整體策略績效。
2. 「比較基準」與「比較樣本」一起讓個案邊界更清楚：模式、日期、左右順序都被明示。
3. 這與 performance panel 的樣本信心提示互補，前者處理個案，後者處理聚合樣本。

落地修改

1. compare result grid 新增兩個脈絡欄位，讓個案比較先顯示基準與樣本。
2. HCS 狀態測試納入 `#建模`、`#抽樣`、`#個案研究` 的獨立紀錄。

優化說明

1. 降低使用者把單一比較結果過度推廣的風險。
2. 保持 UI 改動小而可掃讀；沒有新增 nested card 或複雜表格。
3. 剩餘風險是跨模式比較需要更友善的 warning 文案，留給後續 `#比較組`。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考第五批

### 第 1 輪 / 創意思考 / #比較組

狀態：完成

本次使用：讓跨模式比較的 warning 清楚指出左右報告屬於不同決策模式。

核心判斷

1. 後端 compare compatibility 已能判斷 `different_pipeline`，但 message 以 raw pipeline id 呈現。
2. 跨模式比較不是不能比，而是比較組不同；使用者需要看到可讀模式名稱再判斷比較目的。
3. 前端已有 mode label helper，適合在 warning 顯示層把比較組語意補上。

落地修改

1. `backend/static/report_compare_panel.js` 新增 `compareWarningMessage`。
2. `different_pipeline` warning 改顯示 `兩份報告模式不同：模式 A ... vs 模式 B ...`。

優化說明

1. 降低跨模式比較時把 `v1/v2` 誤讀成版本號或優先級的風險。
2. 保留後端 compatibility code，不改 API 契約。
3. 剩餘風險是 ticker 不同的 warning 仍使用後端訊息；目前 ticker 本身已可讀。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少 `compareWarningMessage` 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #介入研究

狀態：完成

本次使用：用最小 UI 介入改善跨模式 warning，而不改後端資料產生邏輯。

核心判斷

1. 這個問題只影響顯示語意；直接改後端 warning 會把前端 mode label 耦合進服務層。
2. 前端介入能就地使用 `pipelineModeLabel`，成本低且與其他前端視圖一致。
3. 介入範圍應限於 `different_pipeline`，避免重寫所有 warning 造成行為漂移。

落地修改

1. warning 渲染從 `item.message || item` 改成 `compareWarningMessage(item, left, right)`。
2. 只有 `item.code === 'different_pipeline'` 被轉譯，其餘 warning 照舊。

優化說明

1. 將介入範圍壓到最小，降低 regressions。
2. 不影響 warning level 與 styling。
3. 後續若有更多 code 需要轉譯，可擴充同一 helper。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #訪談調查

狀態：完成

本次使用：把使用者可能問出的困惑「v1 vs v2 是什麼意思？」轉成前端文案契約。

核心判斷

1. 尚未做真實使用者訪談，但既有批判思考已指出 raw id 在多個視圖中造成理解成本。
2. 對此類小文案問題，最低成本做法是把推定使用者困惑轉成可檢查的顯示契約。
3. 這不取代真實訪談；它只是先移除明顯的語意摩擦。

落地修改

1. `tests/test_static_history_filters.py` 要求 compare panel 包含 `兩份報告模式不同`。
2. HCS 紀錄標明此為推定使用者回饋，不是已完成真實訪談。

優化說明

1. 讓可能的使用者困惑有可重跑的防回歸測試。
2. 犧牲的是沒有外部訪談資料；收益是立即修掉低風險語意摩擦。
3. 後續若做 QA 或訪談，可再驗證這段 warning 是否足夠。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考第六批

### 第 1 輪 / 創意思考 / #觀察研究

狀態：完成

本次使用：觀察前端目前 raw mode 與共用 mode label 的使用位置，區分真正顯示問題與資料傳遞 fallback。

核心判斷

1. 掃描 `backend/static` 後，主要使用者可見 mode 顯示已集中在 `pipelineModeLabel` 或 `renderPipelineModeBadge`。
2. 剩餘 `pipeline_id || 'v1'` 多數是 openReport、action payload、data attribute 或 rerun fallback，不一定是顯示問題。
3. Report compare 是本輪最有代表性的可見缺口：summary、result grid、warning 都會被操作者直接讀到。

落地修改

1. 將觀察結果寫入本 strict log，作為創意思考收尾依據。
2. `tests/test_static_history_filters.py` 已鎖住 compare panel 使用 `pipelineModeLabel`、`比較基準`、`比較樣本`、`compareWarningMessage`。

優化說明

1. 避免為了消滅所有 `pipeline_id` 字串而誤改資料傳遞路徑。
2. 聚焦真正會影響操作者理解的顯示面。
3. 剩餘風險是仍需瀏覽器視覺 QA 驗證 mobile wrapping。

驗證方式

- `rg -n "pipeline_id \\|\\| 'v1'|report\\.pipeline_id|left\\.pipeline_id|right\\.pipeline_id|pipelineModeLabel" backend/static -S`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #研究複製

狀態：完成

本次使用：把已在 history、watchlist、active jobs 生效的共用 mode label 模式複製到 report compare。

核心判斷

1. 既有模式語意改善已在 history/watchlist/active jobs 使用共用 helper；report compare 應複製同一模式，而不是發明新 label。
2. 可複製模式包含三件事：options 傳入 helper、fallback 到 `window.StockAgentUi`、測試鎖住接線。
3. 這讓後續溝通思考可以專注於受眾與語意，而不是繼續修 raw id 顯示。

落地修改

1. `history_workspace.js` 傳入 `pipelineModeLabel: ui.pipelineModeLabel`。
2. `report_compare_panel.js` 同時在 selection summary、result grid 與 warning 使用同一 helper。
3. HCS 狀態測試新增創意思考收尾 checkpoint。

優化說明

1. 複製已驗證 pattern，降低新增不一致抽象的風險。
2. 保留 panel 內 fallback，讓單獨載入時仍可運作。
3. 剩餘風險是其他未掃到的使用者可見字串可能仍有內部語氣，留給溝通思考批次處理。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_creative_thinking_round_has_closing_checkpoint`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考收尾

已完成：17/17

已落地修改：

- `docs/pipeline-mode-contract.md` 新增模式選擇速記與決策樹。
- `backend/static/report_compare_panel.js` 使用共用 mode label 顯示選取摘要、比較基準、比較樣本與跨模式 warning。
- `backend/static/history_workspace.js` 將 `ui.pipelineModeLabel` 傳入 report compare panel。
- `tests/test_docs_contract.py`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py` 鎖住文件與前端語意。

驗證基準：

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`

剩餘風險：

- 尚未完成溝通思考與互動思考的第 1 輪嚴格單項巡迴。
- Report compare 的 mobile wrapping 尚未用瀏覽器截圖驗證。

下一步：第 1 輪 / 溝通思考 / #受眾

## 第 1 輪溝通思考第一批

### 第 1 輪 / 溝通思考 / #受眾

狀態：完成

本次使用：把 report compare warning 從工程讀者語氣調整成操作者可讀語氣。

核心判斷

1. `A vs B` 對工程讀者很短，但對中文操作者而言不如「A 與 B」自然。
2. 跨模式比較 warning 的受眾是正在判斷報告差異的操作者，不是查 debug log 的開發者。
3. 文案應說明比較性質，而不是只列出代碼或縮寫。

落地修改

1. `backend/static/report_compare_panel.js` 將 warning 中的 `vs` 改成中文「與」。
2. `tests/test_static_history_filters.py` 要求 report compare JS 不含 ` vs `。

優化說明

1. 降低非工程使用者閱讀 warning 的摩擦。
2. 不改 warning 觸發條件，只改顯示語氣。
3. 剩餘風險是其他面板仍可能有工程縮寫，後續溝通思考繼續掃描。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認 `跨視角比較` 缺失與 `vs` 存在會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 溝通思考 / #組成

狀態：完成

本次使用：讓 warning 組成包含左右模式與比較性質，而不是只有「不同」。

核心判斷

1. 好的 warning 需要回答三件事：哪兩份模式不同、這是否仍可比較、使用者應如何理解。
2. 目前最小足夠組成是「兩份報告模式不同：A 與 B；這是跨視角比較。」
3. 不必在 warning 裡加入長指令，避免讓 chip 變得太長。

落地修改

1. `compareWarningMessage` 將左右 mode label 與「跨視角比較」放在同一句。
2. 測試鎖住 `兩份報告模式不同` 與 `跨視角比較` 兩個語意元件。

優化說明

1. 讓 warning 同時具備差異資訊與解讀框架。
2. 犧牲的是比原本短句稍長；但 warning 只在跨模式比較時出現。
3. 若 mobile chip 過長，後續可把 compatibility chips 改成多行內容。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 溝通思考 / #語意含義

狀態：完成

本次使用：修正文案中可能造成對立感或工程感的符號語意。

核心判斷

1. `vs` 暗示對抗或技術比較，不如「與」中性。
2. 「不同」若沒有補充，可能被看成不可比較；「跨視角比較」明確說明它是另一種比較目的。
3. 這能降低使用者看到 warning 就停止操作的機率。

落地修改

1. Warning 字串改為 `兩份報告模式不同：... 與 ...；這是跨視角比較。`
2. 靜態測試排除 ` vs `，並要求 `跨視角比較` 存在。

優化說明

1. 讓 warning 從阻斷語意改成解釋語意。
2. 不降低警示強度；只把差異的含義說清楚。
3. 後續可檢查其他 `warning` 是否也有「看起來像錯誤、其實是脈絡」的情況。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪溝通思考第二批

### 第 1 輪 / 溝通思考 / #組織結構

狀態：完成

本次使用：調整 report compare result 的資訊順序，先回答比較性質，再列出檔名與數字。

核心判斷

1. 使用者進入比較結果時，第一個問題是「這兩份報告是不是同一種比較」。
2. 原本 result grid 先列左右檔名，結論需要從 chip 與其他欄位拼湊。
3. 新增「比較結論」作為第一個 grid cell，可以讓資訊結構更符合決策閱讀順序。

落地修改

1. `backend/static/report_compare_panel.js` 新增 `compareSummaryLabel`。
2. Result grid 第一列新增 `比較結論`，內容依 compatibility 顯示同股票同模式、股票不同、跨視角比較或需留意。

優化說明

1. 讓比較結果先交代閱讀框架，再進入左右檔案與 delta。
2. 不改後端 payload，只重排前端顯示。
3. 剩餘風險是 grid cell 變多，仍需後續視覺 QA 檢查 mobile wrapping。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少 `比較結論` 與 `compareSummaryLabel` 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- 行數限制：`tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

### 第 1 輪 / 溝通思考 / #專業性

狀態：完成

本次使用：讓比較性質用專業但不誇大的語氣呈現。

核心判斷

1. 「同股票同模式」能說明這是較直接的時間/版本比較。
2. 「跨視角比較」能說明不同 pipeline 的比較目的，不把它說成錯誤。
3. 「需留意」保留不確定狀態，避免 compatibility 缺資料時過度肯定。

落地修改

1. `compareSummaryLabel` 使用 `同股票同模式`、`股票不同`、`跨視角比較`、`需留意` 四種語氣。
2. 靜態契約要求 `同股票同模式` 存在於 compare panel。

優化說明

1. 補強專業語氣：既不過度阻斷，也不把風險淡化。
2. 不新增投資建議，只描述比較條件。
3. 後續可把同樣語氣套用到 report preview 的 rerun/refresh 判斷。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 溝通思考 / #論點

狀態：完成

本次使用：把 compare result 的論點從隱含狀態變成明確第一句。

核心判斷

1. Result grid 的核心論點不是「左右檔案各是什麼」，而是「這次比較應如何被理解」。
2. 將「比較結論」放第一列，能避免使用者先讀數字再回頭查是否可比。
3. 這與前面批判思考的可驗證性一致：結論必須先聲明條件。

落地修改

1. Grid rows array 第一個元素改為 `['比較結論', compareSummaryLabel(compatibility)]`。
2. 測試鎖定 `compareSummaryLabel` 與 `比較結論`。

優化說明

1. 讓論點先行，數字與檔名作為支持資訊。
2. 犧牲一格版面；換來更清楚的比較閱讀入口。
3. 剩餘風險是 summary label 邏輯目前在前端，若後端也需要同語意需再抽共用。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪溝通思考第三批

### 第 1 輪 / 溝通思考 / #溝通設計

狀態：完成

本次使用：收斂 compare panel 的溝通設計，避免為了表達完整而加入過多視覺與文案。

核心判斷

1. Compare panel 已具備 selection summary、compatibility chip、比較結論、比較基準、比較樣本與核心 delta。
2. 再加入更多說明會降低掃讀效率，尤其是在 preview 側欄內。
3. 本輪更合理的設計是「收尾並測試固定」，把後續大型視覺改善留給專門 QA 或設計批次。

落地修改

1. `tests/test_hcs_plus_state.py` 新增溝通思考收尾 checkpoint。
2. 本文件新增溝通思考收尾，明確記錄暫不擴張 compare panel 的設計決策。

優化說明

1. 避免 compare panel 變成第二個完整報告視圖。
2. 犧牲的是沒有新增圖表或多媒體；收益是維持側欄工具的掃讀性。
3. 剩餘風險是 mobile wrapping 尚未實測，留給後續視覺 QA。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少溝通收尾會失敗。
- GREEN：`tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`

### 第 1 輪 / 溝通思考 / #表達

狀態：完成

本次使用：把本輪 compare 文案原則寫成可接續的收尾摘要。

核心判斷

1. 本輪表達原則是：少用代碼、先說比較性質、再呈現檔名與數字。
2. 「同股票同模式」「跨視角比較」「比較基準」「比較樣本」已形成一致用語。
3. 收尾摘要能讓後續溝通批次沿用這套表達，而不是重新命名。

落地修改

1. 本文件「第 1 輪溝通思考收尾」新增已落地修改與文案原則。
2. `tests/test_hcs_plus_state.py` 要求 `已完成：10/10` 與下一步互動思考入口。

優化說明

1. 固定可重用表達，降低後續回到 raw id 或工程語氣的風險。
2. 不新增產品字串，只把已完成的表達原則寫成狀態契約。
3. 剩餘風險是其他頁面仍可能有未掃到的工程語氣。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`

### 第 1 輪 / 溝通思考 / #媒介

狀態：完成

本次使用：確認 report compare 目前應維持文字 grid 與 chip，而不是切換成圖表或複雜媒介。

核心判斷

1. Report compare 的資訊是左右報告脈絡與少量 delta，文字 grid 比圖表更直接。
2. Compatibility warning 適合 chip，因為它是短狀態訊息，不是完整說明段落。
3. 圖表或多媒體會增加實作與 QA 成本，且不一定提升當前決策效率。

落地修改

1. 在溝通收尾記錄目前媒介選擇：文字 grid/chip。
2. 測試固定 compare panel 不需要新增額外多媒體 artifact 才能完成本輪。

優化說明

1. 把媒介選擇說清楚，避免後續誤以為未加入圖表就是缺漏。
2. 保持現有 CSS 與行數限制穩定。
3. 若未來比較維度增加，再另開視覺設計批次。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`
- `tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

### 第 1 輪 / 溝通思考 / #多媒體

狀態：完成

本次使用：判斷本輪是否需要加入圖表、截圖或多媒體比較；結論是暫不加入。

核心判斷

1. 目前 compare panel 是嵌在 report preview 的輔助工具，不是獨立分析儀表板。
2. 多媒體化會需要額外 responsive QA，且可能與「側欄掃讀」目標衝突。
3. 目前最有價值的多媒體工作是後續瀏覽器截圖驗證，而不是新增使用者可見媒體。

落地修改

1. 溝通收尾明確標示「暫不引入圖表/截圖式比較」。
2. 下一步轉入互動思考，檢查倫理與使用者操作風險，而不是繼續擴張溝通媒介。

優化說明

1. 避免為了多媒體而多媒體，維持工具型 UI 的節制。
2. 承認剩餘風險：仍需實際瀏覽器 QA 驗證視覺 wrapping。
3. 將多媒體相關工作保留為驗證/設計 QA，而不是本輪功能需求。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`

## 第 1 輪溝通思考收尾

已完成：10/10

已落地修改：

- `backend/static/report_compare_panel.js` 的比較結果先顯示「比較結論」，再顯示檔名、比較基準、比較樣本與 delta。
- `backend/static/report_compare_panel.js` 的跨模式 warning 使用完整中文語意，不再使用 `vs`。
- `tests/test_static_history_filters.py` 鎖住 compare panel 的 mode label、比較結論、跨視角文案與前端模組行數。
- `tests/test_hcs_plus_state.py` 鎖住溝通思考 10/10 收尾與下一步入口。

文案原則：

- 少用 raw id 與工程縮寫。
- 先說比較性質，再呈現檔名與數字。
- Warning 以解釋脈絡為主，不把可理解的跨視角比較說成錯誤。

剩餘風險：

- Report compare 的 mobile wrapping 尚未用瀏覽器截圖驗證。
- 其他面板仍可能有未掃到的工程語氣，留給後續互動與第二輪巡檢。

下一步：第 1 輪 / 互動思考 / #倫理考量

## 第 1 輪互動思考第一批

### 第 1 輪 / 互動思考 / #倫理考量

狀態：完成

本次使用：避免 report compare 的建議變化被使用者誤讀成即時交易指令。

核心判斷

1. 比較兩份既有報告只是在回顧報告差異，不等於產生新的交易建議。
2. 原本欄位名稱「建議」過短，容易被掃讀成當下系統指令。
3. 需要在比較結果中明確提醒：此處只比較既有報告。

落地修改

1. `backend/static/report_compare_panel.js` 新增「使用提醒」欄位。
2. 提醒文字為 `僅比較既有報告，不代表即時交易指令`。
3. `tests/test_static_history_filters.py` 鎖住該提醒文字。

優化說明

1. 降低使用者把歷史報告比較當成即時交易訊號的風險。
2. 不移除報告建議資訊，只補上使用邊界。
3. 剩餘風險是完整報告內仍可能有強行動語氣，後續可檢查報告模板。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「使用提醒」與「不代表即時交易指令」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #倫理勇氣

狀態：完成

本次使用：主動弱化過度權威的「建議」標籤，即使它原本較短、較醒目。

核心判斷

1. 投資系統應避免把模型/報告輸出包裝成無條件行動命令。
2. 把「建議」改為「報告建議變化」更誠實，因為它描述的是兩份報告之間的差異。
3. 這會稍微拉長欄位 label，但能降低過度自信使用。

落地修改

1. `report_compare_panel.js` 將 grid row label 從 `建議` 改成 `報告建議變化`。
2. 測試排除 compare panel 的 `['建議'` row。

優化說明

1. 以清楚邊界取代短而權威的命令感。
2. 不改 recommendation delta 的資料來源。
3. 後續可檢查 preview 的 `投資建議` 標題是否也需要更細緻的 context。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #倫理判斷

狀態：完成

本次使用：判斷哪個位置最需要倫理提醒，並避免把提醒灑滿 UI 造成疲乏。

核心判斷

1. Report compare 是最容易被誤讀為「新結論」的位置，因此先在 compare result 補提醒。
2. 不應在每個數字格都加 disclaimer，否則使用者會忽略真正重要的警示。
3. 最小足夠提醒是單一「使用提醒」欄，搭配「報告建議變化」label。

落地修改

1. `tests/test_static_history_filters.py` 要求 `報告建議變化`、`使用提醒`、`不代表即時交易指令` 同時存在。
2. HCS 狀態測試納入 `#倫理考量`、`#倫理勇氣`、`#倫理判斷`。

優化說明

1. 在最可能誤用的互動點放置倫理邊界。
2. 控制提醒密度，避免 UI 噪音。
3. 剩餘風險是 rerun 完成 notification 可能仍讓使用者過度信任新報告，後續可檢查。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪互動思考第二批

### 第 1 輪 / 互動思考 / #複雜因果

狀態：完成

本次使用：避免使用者把兩份報告差異直接歸因為市場因果。

核心判斷

1. 報告建議變化可能來自資料更新、模型輸出差異、時間窗口不同或市場真實變化。
2. Compare panel 若只顯示 delta，使用者容易把報告差異當成市場因果。
3. 需要用一句短提醒把因果邊界說清楚。

落地修改

1. `backend/static/report_compare_panel.js` 新增「判讀層次」欄位。
2. 文案為 `報告差異不等於市場因果；搭配資料可信度與追蹤報酬判讀`。

優化說明

1. 降低把模型/報告差異誤當作市場原因的風險。
2. 不改演算法，只補足互動判讀脈絡。
3. 剩餘風險是完整因果分析仍需要閱讀完整報告與外部資料。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「判讀層次」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #湧現特性

狀態：完成

本次使用：提醒報告差異、資料可信度與追蹤報酬交互後才形成可判讀結果。

核心判斷

1. 單一欄位無法說明決策品質；報告建議、資料可信度與追蹤報酬一起才有意義。
2. 這種交互是湧現特性，不應被單一 delta 簡化。
3. 因此提醒應指向「搭配資料可信度與追蹤報酬判讀」。

落地修改

1. `tests/test_static_history_filters.py` 要求 compare panel 包含 `搭配資料可信度與追蹤報酬判讀`。
2. HCS log 記錄此提醒的湧現判讀理由。

優化說明

1. 引導使用者同時看多個訊號。
2. 不增加新的複雜模型或圖表。
3. 後續可在 performance panel 或 decision tracking 中補更多跨訊號說明。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #分析層次

狀態：完成

本次使用：把 report compare 的判讀分成報告層、資料層與市場追蹤層。

核心判斷

1. 「報告建議變化」屬於報告層。
2. 「資料可信度」屬於資料層。
3. 「追蹤報酬」屬於市場結果追蹤層；三者不能混成同一結論。

落地修改

1. Result grid 新增「判讀層次」欄，並保留「資料可信度」「追蹤報酬」各自欄位。
2. HCS 測試納入 `#複雜因果`、`#湧現特性`、`#分析層次`。

優化說明

1. 幫助使用者在互動中分層判斷，不把所有變化壓成單一買賣訊號。
2. 不重排整個 grid，降低視覺衝擊。
3. 剩餘風險是文字提醒偏長，需後續 mobile QA。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

## 第 1 輪互動思考第三批

### 第 1 輪 / 互動思考 / #網絡

狀態：完成

本次使用：把 report compare 的 warning 連回重跑流程，而不是讓 warning 孤立存在。

核心判斷

1. 當 compare API 回傳 `left_decision_needs_rerun` 或 `right_decision_needs_rerun`，代表資料快照與結論不同步。
2. 這不是單純的比較警告，而是 compare、data refresh、rerun 三個系統節點之間的網絡關係。
3. 前端 warning 應直接指出下一步系統動作：先重跑結論。

落地修改

1. `backend/static/report_compare_panel.js` 的 `compareWarningMessage` 新增 `decision_needs_rerun` 分支。
2. Warning 文字改為 `左側/右側報告需先重跑結論，再比較投資判斷。`

優化說明

1. 將 warning 從狀態描述推進到系統入口提示。
2. 不新增按鈕，避免在 compare panel 複製 rerun 操作面。
3. 剩餘風險是使用者仍需回到 preview 的 rerun 按鈕；後續可評估是否提供更直接入口。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少 `decision_needs_rerun` 與重跑提示會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #系統動力學

狀態：完成

本次使用：呈現資料更新後的正確動態順序：資料刷新後，結論需重跑，再比較投資判斷。

核心判斷

1. 如果資料快照已刷新但投資結論未重跑，直接比較投資判斷會混合不同時間層。
2. 系統正確順序應是 refresh data → rerun conclusion → compare decision。
3. Warning 需要用順序語言「先...再...」提醒使用者。

落地修改

1. Compare warning 文案使用 `需先重跑結論，再比較投資判斷`。
2. 靜態契約測試鎖住該順序語意。

優化說明

1. 減少使用者在資料已變更但結論未更新時做錯比較。
2. 不更改後端狀態機，只讓前端解讀更貼近系統動態。
3. 後續若要更完整，可把 suggested action 放進 compare API。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #系統圖像

狀態：完成

本次使用：讓使用者看到 compare、資料可信度、追蹤報酬與 rerun 不是四個孤立功能。

核心判斷

1. Compare panel 已顯示比較結論、資料可信度、追蹤報酬與使用提醒。
2. 新增 rerun warning 轉譯後，使用者能看到資料更新與重跑結論之間的系統關係。
3. 這讓 compare panel 更像系統地圖上的一個節點，而不是孤立的 diff viewer。

落地修改

1. `tests/test_static_history_filters.py` 要求 compare panel 包含 `decision_needs_rerun` 與重跑提示。
2. HCS 狀態測試納入 `#網絡`、`#系統動力學`、`#系統圖像`。

優化說明

1. 補上跨功能關係提示，而不新增功能入口。
2. 控制改動面：只轉譯現有 warning code。
3. 剩餘風險是缺少可點擊的直接跳轉，留給後續互動思考批次判斷。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

## 第 1 輪互動思考第四批

### 第 1 輪 / 互動思考 / #談判

狀態：完成

本次使用：把 compare warning 的重跑提示從命令式改成條件式，讓系統與使用者共同決定下一步。

核心判斷

1. 「需先重跑結論，再比較投資判斷」是正確順序，但語氣偏命令。
2. 使用者可能只是查看差異，不一定要立刻比較投資判斷。
3. 條件式「若要比較投資判斷，需先重跑結論」更像談判：說明前提與後果，而不是直接強推動作。

落地修改

1. `backend/static/report_compare_panel.js` 將 decision-needs-rerun warning 改成 `若要比較投資判斷，需先重跑結論`。
2. `tests/test_static_history_filters.py` 鎖住新語氣並排除舊命令式文案。

優化說明

1. 保留系統安全順序，同時尊重使用者當下目的。
2. 不新增彈窗或確認流程，避免打斷閱讀。
3. 剩餘風險是沒有直接跳到重跑按鈕的入口，後續可評估。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認舊文案會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #說服

狀態：完成

本次使用：降低系統文案的強說服性，避免把使用者推向立即重跑。

核心判斷

1. 金融決策工具的 warning 應該說明條件，而不是用強勢語氣推動操作。
2. 「若要...需先...」比「需先...再...」更清楚地把重跑放在使用者目標之下。
3. 這種說服方式比較透明：不是要求你重跑，而是說明若要做某種比較，前置條件是什麼。

落地修改

1. 前端靜態測試新增 `需先重跑結論，再比較投資判斷` 不得出現在 compare panel。
2. Compare warning 仍保留 `decision_needs_rerun` code 分支，不隱藏風險。

優化說明

1. 降低 action bias。
2. 不弱化資料不同步風險。
3. 後續可檢查其他成功 toast 是否也過度肯定。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #形塑行為

狀態：完成

本次使用：用條件式順序形塑審慎比較流程。

核心判斷

1. 好的行為引導不是更多按鈕，而是讓使用者知道何時該做哪一步。
2. 「若要比較投資判斷，需先重跑結論」把行為順序明確化。
3. 這有助於避免使用者在資料已更新但結論未重跑時，仍直接比較投資判斷。

落地修改

1. `compareWarningMessage` 的 rerun warning 文案改為條件式順序。
2. HCS 狀態測試納入 `#談判`、`#說服`、`#形塑行為`。

優化說明

1. 以文案形塑正確流程，而不是新增強制流程。
2. 保留使用者自主權。
3. 剩餘風險是沒有強制阻止錯誤比較；目前先採低摩擦提醒。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪互動思考第五批

### 第 1 輪 / 互動思考 / #從眾

狀態：完成

本次使用：檢查 report preview 是否用介面語氣把使用者推向跟隨報告結論。

核心判斷

1. Legacy preview 預設標題是「投資建議」，主指標 label 是「建議」。
2. 對金融研究工具而言，這種裸露語氣容易把報告輸出包裝成使用者應跟隨的行動。
3. 改成「報告建議」能保留資訊，同時提醒這是報告中的欄位，不是群體或系統命令。

落地修改

1. `backend/static/report_preview_panel.js` 將 legacy preview 預設標題從 `${report.ticker} 投資建議` 改成 `${report.ticker} 報告建議`。
2. 同一模組將 primary label 從 `建議` 改成 `報告建議`。
3. `tests/test_static_history_filters.py` 新增靜態與 Node 行為測試，鎖住 legacy preview 的新語氣。

優化說明

1. 解決 preview 預設入口過度強化單一結論的問題。
2. 犧牲是標題略長，但能明確標示來源層級。
3. 剩餘風險是後端已產生的 `preview.title` 仍可能帶有舊語氣，後續可檢查報告生成端。

驗證方式

- RED：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview` 先確認舊標題會失敗。
- GREEN：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview`

### 第 1 輪 / 互動思考 / #差異

狀態：完成

本次使用：區分報告產生的建議與使用者最後採取的判斷。

核心判斷

1. 「報告建議」仍然可能被誤讀成最後決策。
2. Preview 摘要是使用者最容易停留的閱讀點，適合放低摩擦邊界提醒。
3. 「仍需自行判斷」把報告輸出與使用者決策責任分開，不否定報告價值。

落地修改

1. `backend/static/report_preview_panel.js` 新增 `FALLBACK_SUMMARY`，在沒有可讀摘要時顯示「報告建議仍需自行判斷」。
2. `show()` 的 summary fallback 與 `legacyPreview()` 共用同一提醒，避免兩處文案漂移。
3. 靜態測試要求 `report_preview_panel.js` 包含「仍需自行判斷」。

優化說明

1. 補上決策邊界，不新增彈窗或阻斷流程。
2. 只影響缺少摘要的 fallback 與 legacy path，不改動模式化 preview 的既有摘要。
3. 剩餘風險是使用者若只看 primary metric 仍可能忽略提醒。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- `tests/test_static_history_filters.py::test_report_preview_panel_renders_mode_specific_preview_metrics`

### 第 1 輪 / 互動思考 / #情緒智商

狀態：完成

本次使用：降低買入、賣出或持有訊號在 preview 中造成的情緒化操作推力。

核心判斷

1. 使用者看到「投資建議」與「建議：買入」時，容易把資訊當成立即行動。
2. 「報告建議」比「建議」多一層來源標記，能降低被單一詞觸發的急迫感。
3. 摘要提醒保留冷靜判斷空間，適合金融研究場景。

落地修改

1. `tests/test_static_history_filters.py` 明確排除 `${report.ticker} 投資建議` 與 `label: '建議'` 回到 preview source。
2. `backend/static/report_preview_panel.js` 使用「報告建議」與自行判斷提醒作為預設文案。
3. HCS 狀態測試納入 `#從眾`、`#差異`、`#情緒智商` 的完成要求。

優化說明

1. 以語氣調整降低情緒化採用，而非隱藏投資資訊。
2. 維持既有追蹤報酬與 rerun 操作，不改變資料流。
3. 剩餘風險是完整報告內文仍可能使用強烈投資語氣，後續可在報告模板層處理。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「報告建議」與「仍需自行判斷」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- GREEN：`tests/test_hcs_plus_state.py`

## 第 1 輪互動思考第六批

### 第 1 輪 / 互動思考 / #領導原則

狀態：完成

本次使用：檢查系統在 preview/rerun 入口如何帶領使用者理解下一步。

核心判斷

1. 「重跑最終建議」像是系統要重新發布最後判斷，容易把使用者帶向接受結果。
2. 更好的領導方式是說明 rerun 產出的是「報告結論」，讓使用者知道這仍是研究材料。
3. 靜態 preview 骨架也應先呈現「報告建議」，避免 JS 尚未覆寫時露出舊語氣。

落地修改

1. `backend/static/report_preview_panel.js` 將 rerun final button 文字改成 `重跑${shortLabel}報告結論`。
2. `backend/static/index.html` 將 preview 預設標題改為「報告建議」。
3. `tests/test_static_history_filters.py` 用靜態與 Node 測試鎖住 rerun button 的新文案。

優化說明

1. 讓系統帶領使用者回到「報告產物」而非「最終命令」。
2. 不新增流程和確認視窗，保持操作效率。
3. 剩餘風險是後端 `scope_label` 成功通知仍可能使用不同語氣，後續可追蹤。

驗證方式

- RED：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview` 先確認舊 rerun 文案會失敗。
- GREEN：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview`

### 第 1 輪 / 互動思考 / #權力動態

狀態：完成

本次使用：降低 UI 文字把系統放在過高權威位置的風險。

核心判斷

1. 「最終建議」把權威集中在系統輸出，且暗示它已是最後答案。
2. 「報告結論」保留分析結果的專業性，但權力位置比較清楚：報告提供結論，使用者做判斷。
3. Close button 的 aria label 也不應繼續說「投資建議預覽」。

落地修改

1. `backend/static/index.html` 將關閉按鈕 aria label 改為「關閉報告預覽」。
2. 靜態測試排除「關閉投資建議預覽」與「重跑最終建議」。
3. `report_preview_panel.js` 不再包含 `重跑${shortLabel}最終建議`。

優化說明

1. 以用字調整權力關係，不改變功能權限。
2. 改動同時涵蓋可視文字與輔助科技文字。
3. 剩餘風險是其他頁面仍有「投資建議」作為 filter label，需在後續判斷是否屬於欄位名稱或權威語氣。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #責任

狀態：完成

本次使用：讓 preview 初始狀態、動態渲染與 rerun 行為都清楚標示報告層級。

核心判斷

1. 責任邊界不只存在 summary 文字，也存在標題、label、按鈕和 aria label 的一致性。
2. 若靜態 HTML 還留著「建議」和「投資建議」，就會和 JS 的「報告建議」產生責任邊界不一致。
3. 將 HTML fallback 同步為「報告建議」可避免載入前或測試環境中的語意回退。

落地修改

1. `backend/static/index.html` 將 preview 預設 label 從「建議」改為「報告建議」。
2. 同檔將 rerun button fallback 改為「重跑報告結論」。
3. HCS 狀態測試納入 `#領導原則`、`#權力動態`、`#責任`。

優化說明

1. 讓責任邊界從 JS runtime 擴展到 HTML 初始骨架。
2. 避免使用者或輔助工具先接觸到舊的權威語氣。
3. 剩餘風險是完整報告正文與篩選器仍有「投資建議」作為名詞，下一批可用自我覺察/制定策略決定是否收斂。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認 index fallback 舊文案會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- GREEN：`tests/test_hcs_plus_state.py`

## 第 1 輪互動思考第七批

### 第 1 輪 / 互動思考 / #自我覺察

狀態：完成

本次使用：讓前端 UI 清楚知道自己是在呈現報告資料，而不是代替使用者做投資決策。

核心判斷

1. 後端報告、prompt 與測試中的「投資建議」是領域契約，不適合在本批大範圍改名。
2. History filter 的「投資建議 / 全部建議」屬於使用者掃讀入口，會和 preview 的「報告建議」角色不一致。
3. UI 應自覺地把自己定位成報告瀏覽器與決策追蹤工具，而不是交易指令面板。

落地修改

1. `backend/static/index.html` 將 history recommendation filter label 改為「報告建議」。
2. 同一 filter 的 all option 改為「全部報告建議」。
3. `tests/test_frontend_visual_optional.py` 同步 optional visual fixture 的 filter 與 preview label。

優化說明

1. 收斂前端操作入口的角色語氣。
2. 保留後端領域契約中的「投資建議」，避免破壞報告解析與既有測試。
3. 剩餘風險是完整報告正文仍有強烈語氣，下一輪需從批判思考重新拆解是否要動報告生成層。

驗證方式

- RED：`tests/test_static_history_filters.py::test_history_data_trust_filter_is_wired_to_api_params` 先確認舊 filter label 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_history_data_trust_filter_is_wired_to_api_params`

### 第 1 輪 / 互動思考 / #制定策略

狀態：完成

本次使用：把第 1 輪互動思考收尾，並設定第 2 輪從問題拆解重新開始。

核心判斷

1. 第 1 輪互動思考已從倫理、因果、系統、行為引導、權力關係一路收斂到 UI 自我定位。
2. 下一輪不應直接繼續擴大文案修改，而應回到批判思考重新拆解剩餘高風險問題。
3. 最合理的下一批是第 2 輪批判思考的 `#拆解問題`、`#問對問題`、`#差距分析`。

落地修改

1. `tests/test_hcs_plus_state.py` 新增互動思考收尾 checkpoint。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪批判思考第一批標成下一批。
3. 本嚴格輪巡附件記錄互動思考 20/20 完成。

優化說明

1. 把下一步從「繼續改文案」提升為「重新檢查問題結構」。
2. 不宣稱 HCS Plus 完整完成，因為仍需第 2、3 輪與最後綜合優化。
3. 剩餘風險是第 2 輪可能需要重新選擇更高影響的產品層切入點。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少互動思考收尾會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

## 第 1 輪互動思考收尾

- 已完成：20/20。
- 已落地：report compare 的使用提醒、因果層次、重跑條件式提示；report preview 的報告建議語氣、自行判斷提醒、報告結論 rerun CTA；history filter 的報告欄位定位。
- 已驗證：`tests/test_hcs_plus_state.py`、`tests/test_static_history_filters.py` 相關前端契約與 Node 行為測試。
- 剩餘風險：後端報告正文仍使用「投資建議」作為領域契約；是否要調整需在第 2 輪重新拆解成本與風險。
- 下一步：第 2 輪 / 批判思考 / #拆解問題。

## 第 2 輪批判思考第一批

### 第 2 輪 / 批判思考 / #拆解問題

狀態：完成

本次使用：把第 1 輪留下的「投資建議」語氣問題拆成可分別處理的層級。

核心判斷

1. 前端顯示層已改用「報告建議 / 報告結論」，但後端報告正文與 prompt 契約仍保留「投資建議」。
2. 這不一定是錯誤；它可能是報告解析、合規檢查與既有測試依賴的領域契約。
3. 第 2 輪要先拆清楚三層：報告正文契約、prompt/agent 輸出契約、前端顯示層。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考問題雷達」。
2. 問題雷達將「報告正文契約 vs 前端顯示層」列為第一個高風險問題。
3. `tests/test_hcs_plus_state.py` 新增第 2 輪問題雷達測試，避免後續只靠敘述記憶。

優化說明

1. 先拆問題，而不是貿然改報告正文，避免破壞解析契約。
2. 犧牲是本批沒有直接改善 UI；換來後續改動能先看清責任邊界。
3. 剩餘風險是雷達本身仍需下一批變數與偏誤分析來排序。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少第 2 輪 section 與問題雷達會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #問對問題

狀態：完成

本次使用：把下一步從「是否繼續改投資建議」改成可驗證的判斷問題。

核心判斷

1. 壞問題是「還有哪些地方有投資建議四個字？」因為它會推向盲目替換。
2. 好問題是「哪些使用者入口需要顯示層降權威語氣，哪些後端契約必須保留原詞以維持解析？」
3. 第 2 輪需要把問題和證據綁住，避免純文案潔癖。

落地修改

1. 問題雷達新增 `關鍵問題` 欄。
2. 第一列問題要求分辨報告契約與前端顯示層。
3. HCS 狀態測試要求狀態表包含 `關鍵問題`。

優化說明

1. 把思考焦點從字串搜尋轉成契約邊界判斷。
2. 保留後續改正文的可能性，但要求先建立證據。
3. 剩餘風險是尚未列出所有變數，下一批處理。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_problem_radar_tracks_remaining_high_risk_gaps`

### 第 2 輪 / 批判思考 / #差距分析

狀態：完成

本次使用：量出第 1 輪成果與第 2 輪目標之間的缺口。

核心判斷

1. 現況：前端主要入口已標示「報告建議」，但完整報告正文、prompt 與測試仍使用「投資建議」。
2. 目標：使用者入口不把系統輸出表述成交易指令，同時後端契約不因文案調整失去可解析性。
3. 缺口：還沒有明確證據說明哪些層該保留領域詞，哪些層該降權威語氣。

落地修改

1. 問題雷達新增 `差距` 與 `驗證證據` 欄。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第一批標成完成，下一批移到 `#變數分析/#偏誤辨識/#偏誤降低`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #變數分析。

優化說明

1. 讓第 2 輪後續改動有可對照的目標和缺口。
2. 不把「保留投資建議」或「全部改名」預設成答案。
3. 剩餘風險是尚未衡量各層變數影響，下一批處理。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第二批

### 第 2 輪 / 批判思考 / #變數分析

狀態：完成

本次使用：列出影響「投資建議」契約詞是否可替換的主要變數。

核心判斷

1. 同一個詞在不同層級有不同功能：使用者顯示詞可以降權威，機器契約詞可能必須保留。
2. 變數至少包含：使用者入口、報告正文標題、prompt 區塊、parser/conformance 測試、歷史 fixtures。
3. 沒有變數表就直接替換，容易讓 UI 變漂亮但報告解析壞掉。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考變數與偏誤護欄」。
2. 變數表區分「可改名顯示層」與「需保留契約層」。
3. `tests/test_hcs_plus_state.py` 要求狀態表記錄 `可改名顯示層` 與 `需保留契約層`。

優化說明

1. 把後續改名決策拆成可觀察變數。
2. 避免把所有文字都當成同一種 UI 文案。
3. 剩餘風險是尚未量化每個變數的改動成本，下一批用決策樹處理。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少變數與偏誤護欄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #偏誤辨識

狀態：完成

本次使用：辨識第 2 輪最可能把專案帶偏的兩種偏誤。

核心判斷

1. 字串潔癖偏誤：看到「投資建議」就想全部替換，忽略它在 parser 和測試中的契約用途。
2. 過度保守契約偏誤：因為後端契約需要保留，就拒絕改善使用者入口的權威語氣。
3. 兩種偏誤都會傷害目標；正確方向是依層級分開處理。

落地修改

1. 變數與偏誤護欄表新增 `字串潔癖偏誤`。
2. 同表記錄顯示層與契約層的不同處理方向。
3. HCS 測試要求狀態表包含該偏誤名稱。

優化說明

1. 讓下一批決策不被「全改」或「全不改」綁架。
2. 將偏誤寫進狀態表，方便後續檢查 diff 時回扣。
3. 剩餘風險是偏誤護欄目前仍是文件約束，尚未有專門 parser coverage map。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_variable_and_bias_guardrails_are_recorded`

### 第 2 輪 / 批判思考 / #偏誤降低

狀態：完成

本次使用：把偏誤轉成下一批改動前必查的測試與證據。

核心判斷

1. 降低字串潔癖偏誤的方法不是停止改名，而是要求先跑前端契約與解析契約回歸。
2. 降低過度保守偏誤的方法是允許顯示層改名，只要契約層測試維持綠燈。
3. 「解析契約回歸」必須成為下一批前置證據。

落地修改

1. 變數與偏誤護欄表新增 `解析契約回歸` 證據要求。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第二批標成完成，下一批移到 `#決策樹/#目的/#效用`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #決策樹。

優化說明

1. 讓下一批若要改報告正文或 prompt，必須先說明會跑哪些契約測試。
2. 把「改名」從主觀偏好變成可驗證決策。
3. 剩餘風險是尚未選定最佳決策路徑，下一批處理。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第三批

### 第 2 輪 / 批判思考 / #決策樹

狀態：完成

本次使用：把契約詞後續處理轉成明確分支，避免「全改」或「全不改」。

核心判斷

1. 使用者顯示層：應優先使用「報告建議 / 報告結論」這類降權威語氣。
2. 機器解析契約：若 parser、prompt 或 conformance test 依賴 `[投資建議]`，預設保留契約詞。
3. 完整報告正文：屬於混合層，需先補 coverage map，再決定加註、拆分或保留。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約詞決策樹」。
2. 決策樹用 `使用者顯示層`、`機器解析契約`、`完整報告正文` 三個分支記錄處理策略。
3. `tests/test_hcs_plus_state.py` 要求狀態表包含該決策樹與三個分支。

優化說明

1. 把下一步從主觀命名偏好轉成可分流決策。
2. 避免破壞契約，也避免因契約存在而停止改善顯示層。
3. 剩餘風險是尚未實際列出全部契約依賴，下一批用統計/覆蓋盤點處理。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少契約詞決策樹會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #目的

狀態：完成

本次使用：明確本輪處理契約詞的目的，不讓工作滑向單純美化文案。

核心判斷

1. 目的不是消滅「投資建議」四個字。
2. 目的是真實降低使用者入口的交易指令感，同時保住報告可解析、可稽核、可測試。
3. 若完整報告正文要改，必須服務這個目的，而不是只追求語氣一致。

落地修改

1. 契約詞決策樹新增目的描述：降低權威感與保留解析契約並重。
2. 狀態表將 `最高效用路徑` 指向 coverage map，而非立即改正文。
3. HCS 測試要求狀態表包含 `最高效用路徑`。

優化說明

1. 防止第 2 輪偏離產品可信度目標。
2. 讓後續大改前先問效用與風險。
3. 剩餘風險是 coverage map 還未建立。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_term_decision_tree_is_recorded`

### 第 2 輪 / 批判思考 / #效用

狀態：完成

本次使用：選擇目前期望效用最高、風險最低的下一步。

核心判斷

1. 立即改完整報告正文的效用不明，破壞契約的風險較高。
2. 只停在文件分析效用有限；下一步需要盤點實際測試與契約依賴。
3. 最高效用路徑是先補契約 coverage map，再決定是否拆分正文顯示詞與機器契約詞。

落地修改

1. 契約詞決策樹列出 `最高效用路徑`。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第三批標成完成，下一批移到 `#信賴區間/#相關性/#描述統計`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #信賴區間。

優化說明

1. 用效用判斷避免過早大改。
2. 下一批將從「有哪些契約依賴」走向「依賴覆蓋與統計盤點」。
3. 剩餘風險是 coverage map 若太粗，仍可能低估正文改動成本。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第四批

### 第 2 輪 / 批判思考 / #信賴區間

狀態：完成

本次使用：界定契約詞 coverage map 的可信邊界，避免把 grep 結果誤當完整母體。

核心判斷

1. 直接掃 `backend/` 會把 `backend/output/` 生成報告納入，導致樣本膨脹。
2. 本批 coverage map 只代表可維護來源檔：`tests/` 與排除生成輸出的 `backend/`。
3. 因此這是最低可觀測樣本，不是完整母體信賴區間。

落地修改

1. `tests/test_hcs_plus_state.py` 新增 `_files_containing_contract_terms()`，自動統計契約詞出現在 `tests/` 與 `backend/` 的來源檔數。
2. 同 helper 排除 `backend/output/`、`__pycache__` 與 `.pytest_cache`。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約覆蓋統計」。

優化說明

1. 讓數字有邊界，不把生成輸出當成源碼依賴。
2. 犧牲是 coverage map 暫不涵蓋所有 runtime 產物。
3. 剩餘風險是仍需下一批判斷改正文的機率與顯著性。

驗證方式

- RED：`tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_coverage_map_has_observed_counts` 先確認缺少 coverage 統計會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #相關性

狀態：完成

本次使用：避免把「檔案含有契約詞」直接推論成「該檔必須保留契約詞」或「該檔可以替換」。

核心判斷

1. `tests/test_static_history_filters.py` 含「投資建議」是為了排除前端舊語氣，不代表它依賴契約詞。
2. `backend/structured_output_parser.py` 含 `[投資建議]` 則高度相關於 parser 契約。
3. 因此契約詞出現只是一個警訊，相關不等於可替換，也不等於不可替換。

落地修改

1. coverage 統計加入「相關不等於可替換」說明。
2. 狀態表把測試檔與後端檔分開計數，避免混成單一風險。
3. HCS 測試要求狀態表包含該相關性提醒。

優化說明

1. 降低由字串搜尋導出的錯誤結論。
2. 讓下一批能再按 parser、prompt、UI test 細分。
3. 剩餘風險是尚未人工分類每個檔案的契約強度。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_coverage_map_has_observed_counts`

### 第 2 輪 / 批判思考 / #描述統計

狀態：完成

本次使用：把契約詞依賴從口頭描述變成可更新的檔案數。

核心判斷

1. 目前可維護來源中，`tests/` 有 22 個檔案含契約詞。
2. 排除生成輸出後，`backend/` 有 25 個來源檔含契約詞。
3. 這表示契約詞影響面不小，完整報告正文或 prompt 改名不能只靠單一測試判斷。

落地修改

1. `docs/hcs-plus-optimization-state.md` 記錄 `測試檔案數：22` 與 `後端檔案數：25`。
2. `tests/test_hcs_plus_state.py` 用目前 repo 自動計算這兩個數字，要求狀態表同步。
3. 本嚴格輪巡附件將下一批推進到 `#機率/#迴歸/#顯著性`。

優化說明

1. 讓 coverage map 具備可重跑的描述統計。
2. 未來檔案數變動時，測試會逼狀態表更新。
3. 剩餘風險是描述統計只算檔案數，尚未評估每個檔案的權重。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第五批

### 第 2 輪 / 批判思考 / #機率

狀態：完成

本次使用：估計契約詞改動最可能造成哪類回歸。

核心判斷

1. 直接改 `[投資建議]` 或 `最終投資建議` 的高機率回歸點是 parser、conformance、report preview 與 audit rules。
2. 前端顯示層已由 static tests 鎖住，回歸機率較可控。
3. 完整報告正文屬混合層，回歸機率取決於是否同時改 parser/template/test fixture。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約回歸風險排序」。
2. 風險表標記 `高機率回歸`。
3. `tests/test_hcs_plus_state.py` 要求狀態表包含該風險等級。

優化說明

1. 把「可能會壞」拆成具體高機率風險。
2. 避免下一批只靠直覺選測試。
3. 剩餘風險是尚未實際跑所有解析測試矩陣。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少風險排序會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #迴歸

狀態：完成

本次使用：把契約詞改動的回歸檢查轉成具名測試組。

核心判斷

1. `tests/test_report_preview.py` 能攔住 preview 抽取與 legacy report 行為回歸。
2. `tests/test_report_conformance.py` 能攔住報告結構契約回歸。
3. `tests/test_static_history_filters.py` 能攔住前端顯示層回到交易指令語氣。

落地修改

1. 風險排序表新增 `回歸測試組` 欄。
2. 狀態表列出 `tests/test_report_preview.py`、`tests/test_report_conformance.py`、`tests/test_static_history_filters.py`。
3. HCS 測試要求上述測試檔名出現在狀態表。

優化說明

1. 讓後續契約詞改動有明確測試入口。
2. 測試組橫跨 parser、conformance、front-end 三層。
3. 剩餘風險是還需把 audit/prompt tests 納入更完整的矩陣。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_regression_risk_ranking_is_recorded`

### 第 2 輪 / 批判思考 / #顯著性

狀態：完成

本次使用：定義什麼樣的契約詞改動算顯著，必須提高驗證強度。

核心判斷

1. 只改前端顯示 label 且不碰 parser/template，屬低顯著性，可用前端契約測試驗證。
2. 改 `[投資建議]`、`[/投資建議]`、`最終投資建議` 或 report template decision heading，屬高顯著性。
3. 高顯著性改動必須跑 parser/conformance/report-preview/audit 相關測試，不能只跑單一靜態測試。

落地修改

1. 風險排序表新增 `顯著性門檻`。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第五批標成完成，下一批移到 `#證據基礎/#演繹/#歸納`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #證據基礎。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #證據基礎。

優化說明

1. 把驗證強度與改動風險綁定。
2. 後續若要動完整報告正文，必須先承認是高顯著性改動。
3. 剩餘風險是尚未把完整測試矩陣自動編排成單一命令。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第六批

### 第 2 輪 / 批判思考 / #證據基礎

狀態：完成

本次使用：把上一批 coverage map 與回歸風險排序轉成改檔前可查的測試證據矩陣。

核心判斷

1. 目前最可靠的證據不是單一測試，而是 `tests/` 22 檔與 `backend/` 25 檔的契約詞分布，加上高/中/低回歸風險排序。
2. 高顯著性契約詞改動的證據鏈必須同時看 parser、conformance、audit 與 prompt routing。
3. 前端顯示層已另有 static/visual tests，不能拿來證明 parser 或 prompt 契約安全。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約測試矩陣」。
2. 矩陣把 `高顯著性改動`、混合層正文/模板改動、低顯著性顯示層改動分別映射到必跑測試。
3. `tests/test_hcs_plus_state.py` 新增測試，要求矩陣列出證據基礎、演繹規則、歸納限制與必跑測試。

優化說明

1. 解決「知道風險但不知道下一步跑什麼測試」的落地缺口。
2. 犧牲的是矩陣仍需人工判斷改動層級；不把它包成單一自動命令。
3. 剩餘風險是矩陣仍未評估每個真實報告輸出的語意品質。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少矩陣與第六批紀錄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #演繹

狀態：完成

本次使用：把「改動層級」演繹成最小必跑測試組，避免每次靠臨場直覺選測試。

核心判斷

1. 若改 `[投資建議]`、`[/投資建議]`、`最終投資建議`、prompt 契約、parser regex 或 template decision heading，必須視為高顯著性機器契約變更。
2. 若只改完整報告正文或模板顯示，仍可能經過渲染、儲存與 HTTP preview 流程，不能只跑前端字串測試。
3. 若只改 filter、preview、compare、rerun CTA 等前端 label，才可用前端契約測試作為主要門檻。

落地修改

1. 契約測試矩陣新增 `演繹規則` 欄。
2. 高顯著性改動映射到 `tests/test_report_preview.py`、`tests/test_report_conformance.py`、`tests/test_audit_rules.py`、`tests/test_prompt_context_routing.py`。
3. 混合層與顯示層分別映射到 report template/storage/http 與 static/visual 測試。

優化說明

1. 把測試選擇從模糊風險感轉為明確規則。
2. 避免只因某次小改通過 static tests，就錯誤推論 parser/prompt 合約安全。
3. 剩餘風險是規則需在未來新增契約詞或報告管線時同步更新。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_required_contract_test_matrix_is_recorded`

### 第 2 輪 / 批判思考 / #歸納

狀態：完成

本次使用：標出測試矩陣能外推到哪裡、不能外推到哪裡。

核心判斷

1. 從現有來源檔與測試矩陣只能歸納出「目前可維護來源中的代表性契約風險」。
2. 測試通過不能歸納成所有生成報告、所有 LLM 輸出或所有使用者解讀都安全。
3. 下一批必須檢查謬誤、來源品質與情境脈絡，防止矩陣變成過度自信的保證書。

落地修改

1. 契約測試矩陣新增 `歸納限制` 欄，明確寫出每類測試的外推邊界。
2. 主狀態表把第 2 輪批判思考第六批標成完成，下一批移到 `#謬誤/#來源品質/#情境脈絡`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #謬誤。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #謬誤。

優化說明

1. 保留測試矩陣的實用性，同時避免把測試通過當成語意品質完整證明。
2. 把下一批目標自然接到錯誤推論與來源品質檢查。
3. 剩餘風險是尚未把矩陣做成自動化 pytest marker 或腳本。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第七批

### 第 2 輪 / 批判思考 / #謬誤

狀態：完成

本次使用：檢查契約測試矩陣可能誘發的錯誤推論，避免測試綠燈被誤讀成完整語意安全。

核心判斷

1. 最大謬誤是「測試通過不等於語意安全」：合約測試只證明指定契約未回退，不證明使用者不會把報告當交易指令。
2. 第二個謬誤是「coverage map 不等於完整母體」：22 個測試檔與 25 個後端來源檔不是所有生成報告或未來 LLM 輸出。
3. 第三個謬誤是「frontend tests 不等於 parser/prompt safety」：前端 label 測試不能支持機器契約詞替換。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約矩陣反謬誤護欄」。
2. 護欄表列出三個易犯謬誤、錯誤推論、來源品質分級與情境脈絡護欄。
3. `tests/test_hcs_plus_state.py` 新增測試，要求這些謬誤與第七批紀錄存在。

優化說明

1. 讓矩陣從「測試清單」升級成「有推論邊界的驗證工具」。
2. 犧牲的是狀態表更長，但換來後續改契約詞時不容易把測試結果外推過頭。
3. 剩餘風險是尚未把這些護欄轉成 pytest marker 或自動選測腳本。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少反謬誤護欄與第七批紀錄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #來源品質

狀態：完成

本次使用：標出哪些證據可以支撐契約改動判斷，哪些只能作為輔助觀察，哪些不得當成完成證據。

核心判斷

1. 高品質來源是可重跑測試、parser/template source、prompt routing、audit 與 conformance 規則。
2. 次級來源是文件狀態表、人工閱讀摘要、前端 static/visual tests 對應到的顯示層觀察。
3. 單次生成報告、未重跑截圖、未標來源的口頭判斷不得作為完成證據。

落地修改

1. 反謬誤護欄表新增 `來源品質分級` 欄。
2. 每個謬誤都標明 `高品質來源`、`次級來源` 與 `不得作為完成證據`。
3. 主狀態表新增 D45，記錄測試綠燈不可外推成完整語意安全。

優化說明

1. 避免後續用低品質證據支持高顯著性契約變更。
2. 讓「文件紀錄」回到輔助角色，不取代可重跑測試。
3. 剩餘風險是未來若新增測試或報告生成路徑，來源分級需同步更新。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_matrix_fallacy_source_context_guardrail_is_recorded`

### 第 2 輪 / 批判思考 / #情境脈絡

狀態：完成

本次使用：界定同一個測試矩陣在不同改動情境下的適用方式。

核心判斷

1. 機器契約變更包含 `[投資建議]`、prompt、parser regex、template decision heading，必須走高顯著性測試矩陣。
2. 使用者顯示層改動可以用 front-end static/visual tests 驗證，但不能證明 parser/prompt safety。
3. 完整報告正文改動屬混合情境，需同時看報告渲染、儲存、HTTP preview 與語氣邊界。

落地修改

1. 反謬誤護欄表新增 `情境脈絡護欄` 欄。
2. 主狀態表把第 2 輪批判思考第七批標成完成，下一批移到 `#批判/#估算/#詮釋框架`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #批判。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #批判。

優化說明

1. 讓測試矩陣按改動情境使用，而不是一張表套所有修改。
2. 保留前端顯示層降權威語氣的低成本驗證路徑，同時守住機器契約邊界。
3. 剩餘風險是下一批仍需批判矩陣是否過重，並估算是否值得做成命令分組。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第八批

### 第 2 輪 / 批判思考 / #批判

狀態：完成

本次使用：重新檢查契約測試矩陣本身是否太重，會不會讓操作者因為表格複雜而乾脆不跑測試。

核心判斷

1. 矩陣過重風險是真實存在的：目前已有 coverage、風險排序、測試矩陣與反謬誤護欄四層資訊。
2. 直接做自動選測腳本仍太早，因為改動層級仍需要人工判斷；過早工具化可能把判斷責任藏進命令。
3. 最小批判後的決策是先把矩陣收斂成 3 組命令，而不是新增測試架構。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約矩陣可執行性評估」。
2. 狀態表新增 D46，記錄暫不新增自動選測腳本，先用最小命令分組降低執行摩擦。
3. `tests/test_hcs_plus_state.py` 新增測試，要求可執行性評估、第八批紀錄與下一步 checkpoint 存在。

優化說明

1. 把矩陣從「完整但可能不好用」推向「可依情境直接複製命令」。
2. 犧牲的是還沒有全自動選測；換來人工判斷仍清楚留在流程中。
3. 剩餘風險是下一批仍需檢查這個 4/3/2 分組是否合理且可驗證。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少可執行性評估與第八批紀錄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #估算

狀態：完成

本次使用：估算不同改動情境的最低測試成本，讓操作者能在改檔前快速選測。

核心判斷

1. 高顯著性機器契約變更的 estimated scope 是 4 個測試檔：preview、conformance、audit、prompt routing。
2. 混合層正文或模板顯示改動的 estimated scope 是 3 個測試檔：mode templates、report storage、frontend HTTP e2e。
3. 低顯著性使用者顯示層改動的 estimated scope 是 2 個測試檔：static history filters、optional visual fixture。

落地修改

1. 可執行性評估表新增 `estimated scope` 欄。
2. 評估表列出 4 個測試檔、3 個測試檔與 2 個測試檔三種最小命令分組。
3. 每組都提供可直接執行的 `$(scripts/project_python.sh) -m pytest ... -q` 命令。

優化說明

1. 把「要跑哪些測試」從文件推理降成一眼可選的成本估算。
2. 避免每次小型顯示層改動都被高顯著性矩陣拖慢。
3. 剩餘風險是估算只看檔案數，不代表實際 runtime 或 flakiness 成本。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_matrix_operability_estimate_frame_is_recorded`

### 第 2 輪 / 批判思考 / #詮釋框架

狀態：完成

本次使用：定義最小命令分組的綠燈、紅燈與不得解讀為，避免測試結果再度被過度外推。

核心判斷

1. 綠燈代表該情境下的已知契約未回退，不代表所有生成報告語意安全。
2. 紅燈代表該改動不可繼續合併或宣稱完成，需要回頭修契約或調整改動層級。
3. 不得解讀為用來切斷詮釋過度：前端綠燈不得解讀為 parser/prompt safety，混合層綠燈不得解讀為使用者已正確理解語氣。

落地修改

1. 可執行性評估表新增 `詮釋框架` 欄。
2. 每個改動情境都寫入 `綠燈代表`、`紅燈代表`、`不得解讀為`。
3. 主狀態表把第 2 輪第八批標成完成，下一批移到 `#合理性/#可驗證性`。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #合理性。

優化說明

1. 讓命令分組不只是測試清單，也包含結果判讀規則。
2. 把第七批反謬誤護欄延伸到實際執行後的詮釋。
3. 剩餘風險是下一批需確認整個第 2 輪批判思考是否合理收尾，並用測試鎖住。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第九批

### 第 2 輪 / 批判思考 / #合理性

狀態：完成

本次使用：檢查第 2 輪批判思考是否以合理方式收尾，而不是為了追求表面一致直接改動後端契約詞。

核心判斷

1. 第 2 輪批判思考的合理路徑是先建立契約詞決策、coverage、回歸風險、測試矩陣、反謬誤護欄與最小命令分組。
2. 暫不新增自動選測腳本是合理取捨，因為契約層級仍需人工判斷；過早工具化會掩蓋責任邊界。
3. 此階段可以轉入創意思考，下一輪應把矩陣從可驗證推向更容易被操作者學會與採用。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考收尾檢查」。
2. 主狀態表新增 D47，記錄第 2 輪批判思考以 26/26 單項完成作為合理收尾。
3. 本嚴格輪巡附件將第 2 輪 / 批判思考 / `#合理性` 標成完成。

優化說明

1. 防止本輪停在「下一批待辦」而沒有收斂判斷。
2. 讓下一分類入口有明確理由：接下來不是繼續批判矩陣，而是設計更好學、更好採用的矩陣體驗。
3. 剩餘風險是矩陣仍未工具化，後續需在創意思考中判斷低成本採用方式。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少第 2 輪批判思考收尾與 `#合理性/#可驗證性` 章節會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #可驗證性

狀態：完成

本次使用：把第 2 輪批判思考完成狀態轉成可重跑檢查，避免只靠人工記憶說 26/26 已完成。

核心判斷

1. 可驗證性需要同時鎖住三層：主狀態表收尾檢查、嚴格附件單項章節、下一分類入口。
2. `tests/test_hcs_plus_state.py` 能證明 26 個第 2 輪批判思考單項都有 `核心判斷`、`落地修改`、`驗證方式` 與 `狀態：完成`。
3. 相關回歸仍需搭配 docs/frontend 契約測試，不能只看 HCS 狀態測試。

落地修改

1. 主狀態表新增 `第 2 輪批判思考完成：26/26`、`可重跑驗證` 與 `下一分類入口`。
2. `tests/test_hcs_plus_state.py` 新增 `test_hcs_plus_round2_critical_thinking_closing_checkpoint_is_recorded`。
3. 本嚴格輪巡附件新增「第 2 輪批判思考收尾」，並將下一步推進到第 2 輪 / 創意思考 / #學習科學。

優化說明

1. 將本輪批判思考從一連串矩陣文件收束成可驗證 checkpoint。
2. 明確保留 HCS Plus 尚未完成的事實：目前只是第 2 輪批判思考完成，完整流程還要繼續。
3. 剩餘風險是第 2 輪創意思考尚未開始，還未把矩陣轉成更好學的使用體驗。

驗證方式

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 2 輪批判思考收尾

- 已完成：26/26。
- 合理性結論：契約矩陣、反謬誤護欄與最小命令分組足以支撐下一分類，暫不新增自動選測腳本。
- 可驗證性結論：第 2 輪批判思考 26 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 鎖住。
- 下一步：第 2 輪 / 創意思考 / #學習科學。

## 第 2 輪創意思考第一批

### 第 2 輪 / 創意思考 / #學習科學

狀態：完成

本次使用：把上一批的契約矩陣轉成更容易第一次使用的學習入口，降低操作者需要同時讀多張表的負擔。

核心判斷

1. 第 2 輪批判思考已完成矩陣與命令分組，但新操作者仍可能不知道先看哪裡。
2. 最適合的學習入口不是新增更多表，而是把判斷順序壓成「先問三題」。
3. 速學卡應保留原矩陣的風險邊界，不把學習便利性包裝成語意安全保證。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣速學卡`。
2. 速學卡新增 `先問三題`，分別對應機器契約、混合層報告呈現與前端顯示層。
3. `docs/hcs-plus-optimization-state.md` 新增第 2 輪創意思考速學卡設計 checkpoint。

優化說明

1. 解決契約矩陣可驗證但不好學的問題。
2. 犧牲的是文件多一段重述；換來操作者可以先用三題決定測試路徑。
3. 剩餘風險是速學卡仍是文件型態，尚未變成互動式選測流程。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少速學卡與創意思考第一批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #限制條件

狀態：完成

本次使用：在改善學習成本時保留明確限制，避免把仍需人工判斷的契約層級包成假自動化。

核心判斷

1. 契約矩陣目前最重要的限制條件是：不新增自動選測腳本。
2. 這個限制不是保守拖延，而是承認高顯著性、混合層、顯示層改動仍需人先判斷。
3. 本批最小可逆修改是文件速學卡與測試契約，不改 runtime、不改 parser、不改 prompt。

落地修改

1. `docs/pipeline-mode-contract.md` 明確寫入 `不新增自動選測腳本`。
2. `docs/hcs-plus-optimization-state.md` 新增 D48，記錄三題判斷與三道安檢通道的限制。
3. 主狀態表把第 2 輪創意思考第一批標成完成，下一批才進入演算法化思考。

優化說明

1. 讓創意思考不只追求新穎，也保留工程邊界。
2. 避免操作者誤以為速學卡會自動判斷所有契約風險。
3. 剩餘風險是未來若真的新增選測腳本，必須回頭更新本限制與驗證矩陣。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_quick_learning_card`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_learning_constraint_analogy_is_recorded`

### 第 2 輪 / 創意思考 / #類比

狀態：完成

本次使用：用三道安檢通道類比契約矩陣，讓操作者先分流風險，再執行最小測試命令。

核心判斷

1. 高顯著性機器契約、混合層報告呈現、低顯著性顯示層很像三種安檢通道，通道不同，檢查項目也不同。
2. 類比能降低記憶負擔，但不能取代矩陣裡的推論邊界與測試詮釋。
3. 最好的落地方式是把三個通道直接放在契約文件，讓改檔前可以就地查看。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `高顯著性機器契約通道`、`混合層報告呈現通道`、`低顯著性顯示層通道`。
2. 每個通道都列出進入條件、最小測試命令與判讀方式。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #演算法。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #演算法。

優化說明

1. 把抽象風險矩陣變成可掃讀的操作通道。
2. 保留「不得解讀為所有生成報告語意安全」等判讀限制。
3. 剩餘風險是三通道仍需人手選擇，下一批可檢查是否要把它表述成更明確的演算法。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第二批

### 第 2 輪 / 創意思考 / #演算法

狀態：完成

本次使用：把速學卡轉成可以照順序執行的操作流程，避免操作者只知道三個通道，卻不知道改檔前要先做哪一步。

核心判斷

1. 速學卡已降低記憶負擔，但仍缺少「從改動描述到測試命令」的固定順序。
2. 最小演算法不是自動選測腳本，而是四步人工流程：定位改動層級、選擇通道、執行測試、記錄判讀。
3. 若改動跨層，流程必須要求跑多組命令，不能把複合風險硬塞進單一通道。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣操作流程`。
2. 操作流程新增 `四步演算法`，列出定位、選通道、跑測試、記錄限制。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣操作流程設計」。

優化說明

1. 讓契約矩陣從速學卡推進到可重複執行的改檔前流程。
2. 犧牲的是仍需人工判斷；換來不把契約層級責任藏進工具。
3. 剩餘風險是尚未觀察這套流程是否真的降低錯選測試的比例。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少操作流程與第二批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #設計思考

狀態：完成

本次使用：把操作流程對齊實際操作者情境，讓文件不是抽象分類，而是能支援改 parser、改報告模板、改前端文案三種常見工作。

核心判斷

1. 操作者通常不是先想到「高/中/低顯著性」，而是先知道自己正在改哪個檔案或哪類文案。
2. 三個高頻情境是 parser/prompt/decision heading、完整報告模板或正文標題、純前端顯示文案。
3. 情境設計必須保留交叉情境：若同一改動跨 parser 與前端，不能只跑低顯著性顯示層測試。

落地修改

1. `docs/pipeline-mode-contract.md` 在操作流程中新增 `三個操作者情境` 表格。
2. 三個情境分別對應高顯著性機器契約通道、混合層報告呈現通道、低顯著性顯示層通道。
3. 主狀態表新增第二批設計說明，說明情境設計的驗證邊界。

優化說明

1. 讓文件用操作者實際改檔情境切入，而不是只要求理解內部矩陣術語。
2. 保留「跨層改動跑多組測試」的邊界。
3. 剩餘風險是目前情境只覆蓋最常見三類，未來新增報告輸出路徑時需擴充。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_operation_flow`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_algorithm_design_heuristic_is_recorded`

### 第 2 輪 / 創意思考 / #捷思法

狀態：完成

本次使用：把第一次判斷壓縮成三條快速規則，讓操作者在改檔前能用最短時間初篩測試通道。

核心判斷

1. 契約詞括號、使用者可見報告正文、純前端顯示層，是最容易快速辨識的三種線索。
2. 捷思規則只能做初篩，不能保證語意安全，也不能取代矩陣判讀。
3. 規則必須說清楚「才走低顯著性」的條件，避免前端測試被誤用來支持 parser/prompt 改動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `三條捷思規則`。
2. 規則分別標出括號契約詞走高顯著性、使用者會直接閱讀的報告正文先走混合層、純前端且不被 parser 讀取才走低顯著性。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #最佳化。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #最佳化。

優化說明

1. 讓速學卡與操作流程多一層快速入口。
2. 避免捷思法變成偷懶規則；文件仍保留完整通道與測試命令。
3. 剩餘風險是尚未有資料顯示這些規則會減少錯選命令，下一批可用最佳化與假說發展處理。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第三批

### 第 2 輪 / 創意思考 / #最佳化

狀態：完成

本次使用：把契約矩陣操作流程的最佳化目標從「文件更完整」收斂為「改檔前更不容易選錯測試命令」。

核心判斷

1. 目前最大摩擦不是命令不存在，而是操作者可能選錯通道或跨層改動漏跑命令。
2. 最小最佳化不是新增腳本，而是明確定義三個人工 review 目標：降低錯選、減少漏跑、保留人工判斷責任。
3. 若沒有採用觀測訊號，文件再完整也難判斷是否真的改善流程。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣採用觀測板`。
2. 觀測板新增 `最佳化目標`，列出降低錯選測試命令、減少跨層改動漏跑測試、保留人工判斷責任。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣採用觀測設計」。

優化說明

1. 把文件最佳化聚焦到改檔前選測流程，而不是擴張成新工具。
2. 明確保留不新增遙測或自動化蒐集的限制。
3. 剩餘風險是採用效果仍需未來真實變更案例觀察。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少採用觀測板與第三批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #假說發展

狀態：完成

本次使用：把「這套流程會更好用」拆成可被未來變更紀錄支持或反證的假說。

核心判斷

1. 若只說流程更清楚，缺少可反證性；需要寫出什麼現象代表有效，什麼現象代表仍失敗。
2. 三個最有用的假說分別對應四步流程、三個操作者情境、三條捷思規則。
3. 每個假說都要有反證訊號，避免只收集支持性例子。

落地修改

1. `docs/pipeline-mode-contract.md` 的觀測板新增 `可觀察假說` 表格。
2. 表格列出假說 1、假說 2、假說 3，並寫出預期訊號與反證訊號。
3. 主狀態表 D50 記錄本批用假說與訊號檢查流程採用效果。

優化說明

1. 讓後續 HCS 批次可以用案例檢查假說，而不是只繼續堆文件。
2. 犧牲的是當前尚無真實樣本統計；換來下一批能進入建模與抽樣。
3. 剩餘風險是假說仍是定性觀察，尚未量化成 CI gate。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_adoption_observation_board`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_optimization_hypothesis_visualization_is_recorded`

### 第 2 輪 / 創意思考 / #資料視覺化

狀態：完成

本次使用：把採用訊號做成可掃讀矩陣，讓 review 時一眼看出通道選擇、測試判讀與後續行動落在哪個狀態。

核心判斷

1. 對文件型流程而言，最輕量的資料視覺化是表格矩陣，而不是新 dashboard。
2. 綠色、黃色、紅色三欄能把採用狀態壓成可掃讀判斷，並保留人工 review 語境。
3. 視覺化必須說明它不新增遙測或自動化蒐集，避免被誤解成監控功能已完成。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `採用訊號矩陣`。
2. 矩陣用 `綠色`、`黃色`、`紅色` 三欄呈現通道選擇、測試判讀與後續行動。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #建模。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #建模。

優化說明

1. 讓採用情況從散文說明變成可掃讀矩陣。
2. 保留文件契約的小範圍改動，不新增前端或後端功能。
3. 剩餘風險是矩陣還未連到實際案例；下一批可用建模、抽樣、個案研究補上。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第四批

### 第 2 輪 / 創意思考 / #建模

狀態：完成

本次使用：把採用觀測板轉成可對照的案例模型，讓操作者能把當次改動映射到具體風險型態。

核心判斷

1. 採用觀測板指出綠/黃/紅訊號，但還需要模型來回答「這次改動像哪一類案例」。
2. 三個最小模型應對應既有三條通道：高顯著性機器契約、混合層報告呈現、低顯著性顯示層。
3. 模型只服務改檔前判斷，不應被解讀為涵蓋所有未來資料流。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣案例模型`。
2. 案例模型表新增 `模型 A：高顯著性機器契約案例`、`模型 B：混合層報告呈現案例`、`模型 C：低顯著性顯示層案例`。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣案例模型設計」。

優化說明

1. 讓抽象通道變成可引用的模型，方便 review 時要求改動者對照。
2. 保留模型邊界，不宣稱三類模型可覆蓋所有未來系統變更。
3. 剩餘風險是模型尚未和真實變更樣本比較，下一批可用比較組處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少案例模型與第四批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #抽樣

狀態：完成

本次使用：定義代表性抽樣規則，避免用單一順利案例外推成整個契約矩陣已被驗證。

核心判斷

1. 每次契約相關變更至少要對照一個案例模型，否則採用觀測板容易停在抽象判讀。
2. 跨層改動必須同時抽樣兩個模型，因為單一通道測試不足以代表複合風險。
3. 單一綠燈案例只能支持當次改動，不能代表未來所有改動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `代表性抽樣規則`。
2. 抽樣規則要求每次契約相關變更至少對照一個案例模型。
3. 抽樣規則明示跨層改動同時抽樣兩個模型，並不得以單一綠燈案例代表所有未來改動。

優化說明

1. 把採用觀測從「看訊號」推進到「選代表樣本」。
2. 避免幸存者偏誤：不能只記錄最容易通過的低風險案例。
3. 剩餘風險是抽樣規則目前仍是人工文件要求，尚未成為 PR template 或 CI gate。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_case_model`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_modeling_sampling_case_study_is_recorded`

### 第 2 輪 / 創意思考 / #個案研究

狀態：完成

本次使用：建立案例卡格式，讓後續每次契約改動可以留下可比較、可審查的個案紀錄。

核心判斷

1. 模型與抽樣規則仍需要一個固定欄位格式，否則每次 review 記錄會不一致。
2. 最小案例卡應包含改動描述、選擇通道、必跑命令與採用訊號。
3. 案例卡證明當次有被檢查，不證明歷史報告或未來輸出都安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `案例卡格式`。
2. 案例卡要求記錄 `改動描述`、`選擇通道`、`必跑命令`、`採用訊號`。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #比較組。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #比較組。

優化說明

1. 讓後續契約改動可以留下同構案例，而不是散落在不同 PR 描述裡。
2. 保留文件型態，不新增新工具或模板檔。
3. 剩餘風險是尚未比較有無案例卡時的選測品質差異，下一批可處理比較組與介入研究。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第五批

### 第 2 輪 / 創意思考 / #比較組

狀態：完成

本次使用：把案例模型採用效果拆成基準組與介入組，讓後續 review 可以比較「只看流程」與「加案例卡」的差異。

核心判斷

1. 目前文件已有速學卡、操作流程、案例模型，但尚未定義如何比較案例模型是否真的改善選測品質。
2. 最小比較組是基準組只使用速學卡與操作流程，介入組加上案例模型與案例卡。
3. 比較指標需要聚焦錯選通道、漏跑命令、判讀限制缺漏，而不是泛稱使用者覺得更清楚。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣比較與回饋設計`。
2. 新增 `比較組設計`，列出基準組與介入組。
3. 新增 `比較指標`，鎖定錯選通道、漏跑命令與判讀限制缺漏。

優化說明

1. 讓案例模型的價值可以被人工比較，而不是只停在文件完整度。
2. 保留限制：比較組是 review 方法，不是統計實驗。
3. 剩餘風險是尚未觀察真實改動案例，下一批需進入觀察研究。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少比較與回饋設計、第五批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #介入研究

狀態：完成

本次使用：定義低成本介入，讓操作者在改檔前先填案例卡，降低漏跑測試與判讀限制缺漏。

核心判斷

1. 介入不應是新增工具，而是把「先填案例卡」放到改檔前流程中。
2. 跨層改動是最容易漏跑命令的情境，因此要強制列出兩個模型與兩組命令。
3. 黃色或紅色採用訊號需要有回退路徑，回到比較指標補齊通道、命令或判讀限制。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `介入方案`。
2. 介入方案要求改檔前先填案例卡。
3. 介入方案要求跨層改動強制列出兩個模型，並在黃/紅訊號時回到比較指標修正。

優化說明

1. 把案例卡從靜態格式推進成改檔前介入。
2. 不新增產品遙測或自動化蒐集，維持目前文件契約範圍。
3. 剩餘風險是介入效果尚未用真實操作者回饋驗證。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_comparison_feedback_design`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_comparison_intervention_survey_is_recorded`

### 第 2 輪 / 創意思考 / #訪談調查

狀態：完成

本次使用：把採用感受轉成三個低成本回饋題，避免只用作者自己的判斷推論流程好用。

核心判斷

1. 操作者能否在 2 分鐘內選出通道，是最直接的可用性回饋。
2. 哪一條規則讓人猶豫，可以暴露速學卡、捷思法或案例模型仍不清楚的地方。
3. 案例卡是否幫忙發現漏跑命令或判讀限制，是介入是否有效的具體回饋。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `訪談回饋題`。
2. 訪談回饋題包含 2 分鐘選通道、猶豫規則、案例卡是否發現漏跑/判讀限制。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #觀察研究。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #觀察研究。

優化說明

1. 讓下一批觀察研究可以蒐集具體回饋，而不是空泛詢問是否滿意。
2. 明確註記訪談回覆不能替代 pytest 或契約測試。
3. 剩餘風險是目前尚未收集真實回饋，下一批再處理觀察與複製。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第六批

### 第 2 輪 / 創意思考 / #觀察研究

狀態：完成

本次使用：把比較與回饋設計轉成實際觀察欄位，讓後續每次契約變更可以留下可檢查紀錄。

核心判斷

1. 若沒有固定觀察欄位，訪談與案例卡容易只留下散文心得，無法支援後續複製。
2. 最小觀察欄位應包含變更案例、實際選擇通道、實際執行命令與觀察結果。
3. 觀察紀錄不能變成測試替代品；它只輔助判斷流程是否被正確使用。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣觀察與複製準則`。
2. 準則新增 `觀察記錄欄位`，要求記錄 `變更案例`、`實際選擇通道`、`實際執行命令`、`觀察結果`。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣觀察複製設計」。

優化說明

1. 讓契約矩陣採用效果有可觀察紀錄，而不是只看測試是否通過。
2. 保留邊界：不新增產品遙測或自動化蒐集。
3. 剩餘風險是觀察欄位尚未被真實 PR 使用，下一輪溝通思考需讓操作者更容易理解。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少觀察/複製準則與第六批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #研究複製

狀態：完成

本次使用：定義下一位操作者如何複製同一套契約矩陣判斷，而不必閱讀完整 HCS 附件。

核心判斷

1. 可複製的重點是同一案例模型、同一必跑命令、同一判讀限制。
2. 下一位操作者應能只看 `docs/pipeline-mode-contract.md`，找到通道、模型、命令與判讀限制。
3. 研究複製不代表所有未來輸出都安全；它只證明流程可以被重複套用。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `複製檢查清單`。
2. `docs/pipeline-mode-contract.md` 新增 `可複製完成條件`，明確要求下一位操作者不用讀完整 HCS 附件也能套用流程。
3. 主狀態表與嚴格附件新增第 2 輪創意思考 17/17 收尾，下一步推進到第 2 輪 / 溝通思考 / #受眾。

優化說明

1. 將第 2 輪創意思考從學習、流程、採用、案例、比較與觀察收束成可複製契約。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪創意思考完成，完整流程還要繼續。
3. 剩餘風險是契約矩陣語言仍偏流程導向，下一批需用溝通思考改善受眾、組成與語意。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 2 輪創意思考收尾

- 已完成：17/17。
- 收尾結論：第 2 輪創意思考已把契約矩陣從批判性測試矩陣，推進成可學、可操作、可觀測、可建模、可比較、可觀察、可複製的文件契約。
- 可驗證性結論：第 2 輪創意思考 17 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 鎖住。
- 下一步：第 2 輪 / 溝通思考 / #受眾。

## 第 2 輪溝通思考第一批

### 第 2 輪 / 溝通思考 / #受眾

狀態：完成

本次使用：把契約矩陣文件從單一流程文件，改成三種維護者都能找到自己入口的讀者路徑。

核心判斷

1. 一般改文案者最容易誤以為低顯著性文案變更沒有責任邊界。
2. 報告模板維護者需要先判斷自己是否處在混合層，而不是只看 template 測試是否通過。
3. parser/prompt 維護者需要先看到高顯著性機器契約風險，避免把文件通道誤讀成自動化保證。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣讀者路徑`。
2. 讀者路徑新增 `三種受眾` 表格：一般改文案者、報告模板維護者、parser/prompt 維護者。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪溝通思考契約矩陣讀者路徑設計」。

優化說明

1. 讓不同維護者不用先讀完整 HCS 附件，也能找到契約矩陣入口。
2. 犧牲的是文件更長一點；換來更低的誤用與漏讀機率。
3. 剩餘風險是章節排序仍可能偏長，下一批用組織結構與論點再收斂。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少讀者路徑與第 2 輪溝通思考紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 溝通思考 / #組成

狀態：完成

本次使用：把讀者路徑的組成從材料清單改成可執行的閱讀順序，讓操作者知道先判斷、再執行、最後紀錄。

核心判斷

1. 契約矩陣已有速學卡、操作流程、案例模型與觀察準則，但缺少明確順序。
2. 最小清楚順序是先讀速學卡、再用操作流程、最後填案例卡。
3. 組成順序必須保留測試矩陣與必跑命令，不可把文件閱讀本身當成驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 在 `契約矩陣讀者路徑` 中新增 `閱讀順序`。
2. 閱讀順序明確寫出 `先讀速學卡`、`再用操作流程`、`最後填案例卡`。
3. 主狀態表記錄本批把受眾、組成與語意含義合併成一個文件契約 patch。

優化說明

1. 讓文件從「有哪些材料」變成「如何走完一次契約判斷」。
2. 不新增自動選測工具，維持人工判斷與測試命令的責任邊界。
3. 剩餘風險是案例卡尚未被實際 PR 使用，後續仍需觀察真實採用訊號。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_reader_path`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_communication_audience_composition_semantics_is_recorded`

### 第 2 輪 / 溝通思考 / #語意含義

狀態：完成

本次使用：限制讀者對文件契約的推論範圍，避免把文件、觀察紀錄或低顯著性標籤誤解成安全保證。

核心判斷

1. 文件契約不是自動化保證；它只能要求操作者先做人工判斷並執行對應測試。
2. 觀察紀錄不是測試替代品；它記錄流程使用方式，不證明 parser、prompt 或報告模板安全。
3. 低顯著性不代表低責任；純前端顯示文案仍可能影響使用者是否把報告看成交易指令。

落地修改

1. `docs/pipeline-mode-contract.md` 在讀者路徑中新增 `語意邊界`。
2. 語意邊界列出文件契約、觀察紀錄與低顯著性的三個不得誤讀。
3. 嚴格輪巡進度將下一批推進到第 2 輪 / 溝通思考 / #組織結構。
4. 歷史 checkpoint：下一步：第 2 輪 / 溝通思考 / #組織結構。

優化說明

1. 把契約矩陣的溝通風險從「看不懂」推進到「不容易誤解」。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪溝通思考前三個單項完成。
3. 剩餘風險是整份契約仍需要更好的章節排序與核心論點，下一批繼續處理。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪溝通思考第二批

### 第 2 輪 / 溝通思考 / #組織結構

狀態：完成

本次使用：把契約矩陣文件的多個章節整理成可遵循的維護順序，降低讀者在速學卡、案例模型與模式對照之間來回迷路的機率。

核心判斷

1. 讀者路徑已經分出受眾，但整份文件仍需要一條跨章節的導覽。
2. 最小可用組織是先判斷改動層級、再選案例模型、最後確認模式對照。
3. 章節導覽不能改變測試矩陣本身，只能讓維護者更快走到正確章節。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣維護導覽`。
2. 維護導覽新增 `章節導覽` 表格，排列先判斷改動層級、再選案例模型、最後確認模式對照。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪溝通思考契約矩陣維護導覽設計」。

優化說明

1. 把契約矩陣從材料集合整理成維護流程。
2. 犧牲的是文件多一個導覽段落；換來後續維護者更容易引用。
3. 剩餘風險是目前仍以文字和表格為主，下一批再評估溝通媒介是否足夠。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少維護導覽與第二批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 溝通思考 / #專業性

狀態：完成

本次使用：把契約文件的完成敘述限制在專業、可證明的範圍內，避免把測試綠燈包裝成過度安全宣稱。

核心判斷

1. 測試綠燈只能說明已知契約未回退，不應宣稱投資語意安全或使用者一定理解。
2. 跨層改動需要列出多組命令，並說清楚各自保護的契約面。
3. 文件或觀察紀錄只能證明維護判斷已被記錄，不能證明 runtime 行為。

落地修改

1. `docs/pipeline-mode-contract.md` 在維護導覽中新增 `專業維護語氣`。
2. 專業維護語氣明確寫出只證明已知契約未回退、不得宣稱投資語意安全、跨層改動需列出多組命令。
3. 主狀態表 D55 記錄此批把維護導覽收斂成可引用的專業規範。

優化說明

1. 降低文件把測試結果誇大成使用者語意安全的風險。
2. 保留人工責任：跨層改動仍要由維護者列明命令與判讀限制。
3. 剩餘風險是專業語氣仍需在真實 PR 描述中被採用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_maintenance_guide`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_communication_structure_professional_claim_is_recorded`

### 第 2 輪 / 溝通思考 / #論點

狀態：完成

本次使用：把維護導覽的核心主張寫清楚，讓後續改動不把契約矩陣理解成自動選測工具。

核心判斷

1. 契約矩陣的核心論點是人工判斷先行，再用最小測試驗證。
2. 碰到 parser/prompt/template 時，應優先視為契約變更，再判斷是否跨報告呈現或前端顯示。
3. 低顯著性前端通道仍需維持報告層級語氣，不可把報告建議寫成即時交易指令。

落地修改

1. `docs/pipeline-mode-contract.md` 在維護導覽中新增 `核心論點`。
2. 核心論點寫明契約矩陣的目的不是自動化選測，而是先保留人工判斷，再用最小測試驗證。
3. 嚴格輪巡進度將下一批推進到第 2 輪 / 溝通思考 / #溝通設計。
4. 歷史 checkpoint：下一步：第 2 輪 / 溝通思考 / #溝通設計。

優化說明

1. 讓維護者可以引用一段清楚主張，而不是只引用零散表格。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪溝通思考六個單項完成。
3. 剩餘風險是最後四個溝通單項尚未處理文件呈現形式與媒介取捨。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪溝通思考第三批

### 第 2 輪 / 溝通思考 / #溝通設計

狀態：完成

本次使用：把完整契約矩陣設計成可快速引用的一頁摘要，讓維護者在改檔前能先用三步完成初判。

核心判斷

1. 維護導覽適合完整閱讀，但改檔前仍需要更短的入口。
2. 三步短版摘要可涵蓋高顯著性、混合層與低顯著性三種通道。
3. 一頁摘要必須指回完整契約矩陣，不能取代案例模型、測試命令與限制判讀。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣一頁摘要`。
2. 一頁摘要新增 `短版摘要`，包含先看 parser/prompt/template、再看使用者是否直接閱讀、最後看是否只在前端顯示。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪溝通思考契約矩陣摘要與媒介設計」。

優化說明

1. 讓操作者可先用短版摘要進入契約矩陣，而不是在多張表之間尋找入口。
2. 保留完整章節作為詳細判斷來源。
3. 剩餘風險是短版摘要可能被過度簡化使用，因此同節保留不得解讀為的句型。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少一頁摘要與溝通思考收尾會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 溝通思考 / #表達

狀態：完成

本次使用：把維護者回報方式寫成固定句型，降低只貼測試通過、未說明通道與限制的風險。

核心判斷

1. 回報需要同時說明選擇的通道、已執行命令與不得解讀為。
2. 固定句型比散文提醒更容易在 PR、HCS 狀態或變更紀錄中複製。
3. 表達句型不能替代測試證據，只能讓證據與限制更清楚。

落地修改

1. `docs/pipeline-mode-contract.md` 在一頁摘要中新增 `建議表達`。
2. 建議表達包含「我選擇的通道是」、「我已執行的命令是」、「不得解讀為」。
3. 主狀態表 D56 記錄一頁摘要與建議表達完成溝通思考收尾。

優化說明

1. 讓維護者更容易用同一套語句回報契約判斷。
2. 降低測試結果被誇大成投資語意安全的機率。
3. 剩餘風險是句型仍需在實際變更中被採用，後續互動思考會檢查倫理邊界。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_one_page_summary`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_communication_design_expression_media_closing_is_recorded`

### 第 2 輪 / 溝通思考 / #媒介

狀態：完成

本次使用：決定契約矩陣目前應以文字與表格作為主要媒介，優先支援複製判斷、命令與限制。

核心判斷

1. 契約矩陣是維護文件，不是產品儀表板。
2. 文字與表格更適合保留命令、限制與不得解讀為的精確語句。
3. 若改成圖像優先，可能讓操作者跳過文字限制或忽略測試命令。

落地修改

1. `docs/pipeline-mode-contract.md` 在一頁摘要中新增 `媒介取捨`。
2. 媒介取捨明確採用文字與表格優先。
3. 主狀態表記錄媒介選擇的驗證邊界：適用本文件，不禁止未來產品 UI 另行設計。

優化說明

1. 讓文件媒介服務維護任務，而不是為了視覺化而視覺化。
2. 保留未來產品 UI 設計空間，但不在本輪加入。
3. 剩餘風險是文字表格仍可能偏長，後續可用實際採用紀錄再評估。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 2 輪 / 溝通思考 / #多媒體

狀態：完成

本次使用：明確記錄本輪不新增圖像或多媒體，避免把人工判斷包裝成看似自動化的流程圖。

核心判斷

1. 多媒體若只把三通道畫成流程圖，可能強化「自動選測」錯覺。
2. 本文件最重要的是限制條件、命令與不得解讀為，文字不可被圖像取代。
3. 未來若新增圖像，仍必須保留文字版通道、命令與限制。

落地修改

1. `docs/pipeline-mode-contract.md` 的 `媒介取捨` 明確寫出暫不新增圖像或多媒體。
2. 同段寫明避免圖像把人工判斷包成自動流程。
3. 主狀態表與嚴格附件新增第 2 輪溝通思考 10/10 收尾，下一步推進到第 2 輪 / 互動思考 / #倫理考量。

優化說明

1. 把溝通思考從「補更多形式」收斂為「用最適合的形式承載限制」。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪溝通思考完成，仍需第 2 輪互動思考、第 3 輪與綜合優化。
3. 剩餘風險是契約矩陣的倫理宣稱邊界尚未被第 2 輪互動思考檢查。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 2 輪溝通思考收尾

- 已完成：10/10。
- 收尾結論：第 2 輪溝通思考已把契約矩陣轉成分受眾、可導覽、可短版引用、可固定表達且媒介取捨清楚的維護文件。
- 可驗證性結論：第 2 輪溝通思考 10 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 鎖住。
- 下一步：第 2 輪 / 互動思考 / #倫理考量。

## 第 2 輪互動思考第一批

### 第 2 輪 / 互動思考 / #倫理考量

狀態：完成

本次使用：把契約矩陣的測試、文件與低顯著性通道加上倫理底線，避免維護者把有限證據包裝成投資或語意安全。

核心判斷

1. 測試綠燈只證明指定契約未回退，不代表投資建議安全。
2. 契約矩陣是維護者判斷工具，不是可以承擔責任的主體。
3. 低顯著性通道仍可能影響使用者如何理解報告文案，不能被用來淡化使用者風險。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣倫理邊界`。
2. 倫理邊界新增 `倫理底線`，明確禁止把測試綠燈寫成投資建議安全、把責任轉嫁給工具或文件、用低顯著性通道淡化使用者風險。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣倫理邊界設計」。

優化說明

1. 把溝通思考的「不得解讀為」推進到互動層面的責任邊界。
2. 犧牲的是文件多一段倫理規範；換來更低的過度安全宣稱風險。
3. 剩餘風險是局部測試與整體系統行為的因果關係仍需下一批處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少倫理邊界與互動思考第一批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #倫理勇氣

狀態：完成

本次使用：把「必要時要說不」寫成可引用的阻擋條件，讓維護者在證據不足時能暫停高風險改動。

核心判斷

1. 缺少 parser/prompt/template 證據時，不能用文件通道替代高顯著性驗證。
2. 報告文案若可能被讀成交易指令，應先補責任邊界，而不是用低顯著性通道快速放行。
3. 跨層改動只跑單一命令時，應要求補跑或拆分改動。

落地修改

1. `docs/pipeline-mode-contract.md` 在倫理邊界新增 `必要時要說不`。
2. 說不條件包含缺少 parser/prompt/template 證據不可合併高顯著性改動。
3. 說不條件要求交易指令式報告文案先補責任邊界，跨層改動需補跑或拆分。

優化說明

1. 讓維護者有明確理由拒絕看似已通過、實際證據不足的改動。
2. 保留低風險改動的通道，不把所有改動都升級為阻擋。
3. 剩餘風險是阻擋條件仍需在真實 review 中被採用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_ethics_boundary`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_ethics_courage_judgment_is_recorded`

### 第 2 輪 / 互動思考 / #倫理判斷

狀態：完成

本次使用：把允許發布與禁止發布的敘述分開，並定義何時要從低顯著性升級到混合層、從混合層升級到高顯著性。

核心判斷

1. 維護者需要知道哪些敘述可以發布，哪些敘述會誇大證據。
2. 升級條件要把使用者理解、parser/prompt/template 與 runtime 宣稱分開。
3. 文件判斷若被拿來宣稱實際執行行為，就必須升級為 runtime 驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 在倫理邊界新增 `倫理判斷` 表格。
2. 倫理判斷表分開 `允許發布的敘述` 與 `禁止發布的敘述`。
3. 倫理邊界新增 `升級條件`，包含從低顯著性升級為混合層、從混合層升級為高顯著性、從文件判斷升級為 runtime 驗證。
4. 嚴格輪巡進度將下一批推進到第 2 輪 / 互動思考 / #複雜因果。
5. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #複雜因果。

優化說明

1. 把倫理邊界轉成可審查的允許/禁止敘述，降低模糊判斷。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪互動思考前三項完成。
3. 剩餘風險是複雜因果與系統層級風險尚未處理，下一批會接續。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第二批

### 第 2 輪 / 互動思考 / #複雜因果

狀態：完成

本次使用：把局部測試、文件紀錄與前端語氣改善可能造成的錯誤推論寫成因果圖譜，避免把單一綠燈擴張成整體安全。

核心判斷

1. parser/prompt/template 測試通過，仍可能留下使用者誤解或報告語氣風險。
2. 文件與觀察紀錄完整，可能降低漏跑測試，但不能保證真實採用。
3. 前端語氣改善不能保證完整報告正文、preview、儲存流程或使用者閱讀情境一致改善。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣系統風險邊界`。
2. 系統風險邊界新增 `複雜因果圖譜`，列出局部證據、錯誤推論與系統邊界。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣系統風險邊界設計」。

優化說明

1. 把倫理邊界從禁止誇大，推進到說清楚為什麼局部證據不能外推。
2. 保留現有測試矩陣價值，但限制它的可宣稱範圍。
3. 剩餘風險是系統關係尚未整理成維護網絡，下一批處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少系統風險邊界與第二批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #湧現特性

狀態：完成

本次使用：記錄多個低風險改動累積後可能出現的新風險，避免只看單次改動顯著性。

核心判斷

1. 多個低顯著性改動可能累積成高風險，尤其是持續調整責任與報告建議語氣時。
2. 跨模式文案一致可能提高掃讀性，也可能模糊長線、交易與逆勢模式的責任差異。
3. 觀察紀錄增加可能讓維護者誤以為驗證已經足夠，反而減少實際測試。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統風險邊界新增 `湧現風險`。
2. 湧現風險列出低顯著性累積、跨模式責任模糊、觀察紀錄替代實際驗證三種風險。
3. 主狀態表 D58 記錄本批把局部證據與系統風險分開。

優化說明

1. 讓契約矩陣不只處理單次改動，也提醒維護者看累積效果。
2. 不新增遙測或工具，先用文件契約降低誤讀風險。
3. 剩餘風險是湧現風險仍需未來真實變更案例來觀察。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_system_risk_boundary`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_complex_emergent_layers_is_recorded`

### 第 2 輪 / 互動思考 / #分析層次

狀態：完成

本次使用：把文件層、測試層、runtime 層與使用者行為層分開，要求每個宣稱都對齊自己的證據層級。

核心判斷

1. 文件層證據不能替代測試層或 runtime 層。
2. 測試層證據不能替代使用者行為層，也不能保證所有未測 runtime 路徑。
3. 使用者行為層需要真實操作者是否誤解、漏跑或過度採用報告建議的證據。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統風險邊界新增 `分析層次` 表格。
2. 分析層次表區分 `文件層`、`測試層`、`runtime 層`、`使用者行為層`。
3. 同節新增不得用下一層證據替代上一層證據，也不得反向替代的規則。
4. 嚴格輪巡進度將下一批推進到第 2 輪 / 互動思考 / #網絡。
5. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #網絡。

優化說明

1. 讓完成敘述必須說清楚證據層級，降低跨層誇大。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪互動思考六個單項完成。
3. 剩餘風險是尚未把層級關係整理成網絡與系統圖像。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第三批

### 第 2 輪 / 互動思考 / #網絡

狀態：完成

本次使用：把契約矩陣涉及的前端、報告模板、parser/prompt、測試矩陣與使用者判讀整理成維護網絡。

核心判斷

1. 前端顯示層、報告模板層與 parser/prompt 層彼此互相影響，不能只看單一檔案類型。
2. 測試矩陣連接多個層級，但測試綠燈本身不能代表使用者判讀安全。
3. 使用者判讀受到前端文案、報告正文與倫理邊界共同影響。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣系統關係圖`。
2. 系統關係圖新增 `維護網絡` 表格，列出前端顯示層、報告模板層、parser/prompt 層、測試矩陣與使用者判讀。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣系統關係設計」。

優化說明

1. 讓維護者看到契約矩陣不是單張測試表，而是多層互動網絡。
2. 保留文字表格形式，避免新增不可測的圖像 artifact。
3. 剩餘風險是 review 對話如何引導維護者補證據尚未處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少系統關係圖與第三批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #系統動力學

狀態：完成

本次使用：記錄契約矩陣的動態回路，避免單純加規則後忽略維護成本與形式化副作用。

核心判斷

1. 語氣改善會降低權威感，但若不同層不同步，可能增加契約漂移。
2. 更多觀察紀錄會降低漏跑測試，但也可能讓維護者形式化填寫而減少實際驗證。
3. 更嚴格升級條件會降低錯放高風險改動，但可能增加低風險變更的維護成本。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統關係圖新增 `系統動力學`。
2. 系統動力學列出語氣改善、觀察紀錄、升級條件三個回路。
3. 主狀態表 D59 記錄本批把維護網絡與動態回路合併。

優化說明

1. 讓契約矩陣同時呈現風險降低與副作用。
2. 避免把「更多規則」誤認成單向改善。
3. 剩餘風險是目前尚未有真實 review 數據量化這些回路。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_system_relationship_map`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_network_dynamics_system_image_is_recorded`

### 第 2 輪 / 互動思考 / #系統圖像

狀態：完成

本次使用：把維護流程收斂成系統圖像：改動先定位層級、證據再對齊層次、宣稱最後受倫理邊界限制。

核心判斷

1. 若不先定位層級，維護者容易用錯通道。
2. 若證據不對齊層次，容易把文件、測試、runtime 或使用者行為證據互相替代。
3. 若宣稱不受倫理邊界限制，測試綠燈容易被說成投資語意安全。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統關係圖新增 `系統圖像`。
2. 系統圖像明確寫出改動先定位層級、證據再對齊層次、宣稱最後受倫理邊界限制。
3. 嚴格輪巡進度將下一批推進到第 2 輪 / 互動思考 / #談判。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #談判。

優化說明

1. 把前面多個表格收斂成一條維護流程。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪互動思考九個單項完成。
3. 剩餘風險是這套流程尚未轉成 review 對話與行為引導。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第四批

### 第 2 輪 / 互動思考 / #談判

狀態：完成

本次使用：把系統關係與倫理邊界轉成補證據協商，避免 review 只剩下「擋」或「放」兩種立場。

核心判斷

1. 缺證據的改動若直接被否決，容易讓維護者防衛；若直接通過，又會把風險推到使用者。
2. 比較好的談判順序是先承認改動目的，再指出缺少的證據層，最後提出最小補證據路徑。
3. 協商重點不是降低標準，而是把補跑測試、填案例卡或拆分改動變成可接受的下一步。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 對話`。
2. review 對話新增 `補證據協商` 表格，明確寫出先承認改動目的、再指出缺少的證據層、最後提出最小補證據路徑。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣 review 對話設計」。

優化說明

1. 讓 review 的談判語氣從立場對抗改成證據補齊。
2. 犧牲的是文件再增加一段維護規範；換來高風險改動更容易被拆成可驗證步驟。
3. 剩餘風險是團隊仍可能為了趕進度忽略協商句型，下一批需處理從眾與情緒壓力。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少 review 對話與第四批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #說服

狀態：完成

本次使用：把補跑命令、升級通道與拆分改動的理由說成共同降低風險，而不是 review 者單方面增加負擔。

核心判斷

1. 「請再跑測試」若沒有說明風險，很容易被聽成形式要求。
2. 「升級通道」若沒有說明保護對象，很容易被誤解成否定低風險改善。
3. 「拆分改動」若沒有說明成本，容易被看成重工，而不是降低 review 成本。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話新增 `說服原則`。
2. 說服原則要求把補跑命令說成降低錯放風險。
3. 說服原則要求把升級通道說成保護 parser/prompt/template，並把拆分改動說成降低 review 成本。

優化說明

1. 讓維護者知道要求補證據的理由，而不是只看到流程負擔。
2. 保留嚴格邊界：說服語氣不能把測試綠燈說成投資語意安全。
3. 剩餘風險是真實 review 中仍需有人主動引用這段原則。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_review_dialogue`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_negotiation_persuasion_behavior_is_recorded`

### 第 2 輪 / 互動思考 / #形塑行為

狀態：完成

本次使用：把 review 對話轉成預設行為，讓操作者自然留下通道、命令、案例卡與採用訊號限制。

核心判斷

1. 只有規則不夠；若沒有預設格式，操作者仍可能忘記寫通道、命令與不得解讀為。
2. 跨層改動最容易漏掉案例卡，因此應預設先填案例卡再合併。
3. 紅色或黃色採用訊號若被合併成綠燈，會讓契約矩陣失去警示作用。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話新增 `形塑行為`。
2. 形塑行為要求預設使用一頁摘要句型，跨層改動預設填案例卡。
3. 形塑行為明確規定紅色或黃色採用訊號不得合併。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #從眾。

優化說明

1. 把前面的一頁摘要、案例模型與採用觀測板串成 review 預設。
2. 這不新增自動化審核器，仍保留人工判斷與測試命令。
3. 下一批需檢查預設行為是否會造成從眾、忽略差異，或在高壓情境下被情緒化採用。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第五批

### 第 2 輪 / 互動思考 / #從眾

狀態：完成

本次使用：檢查 review 對話是否可能讓操作者因多數同意、前例綠燈或測試全綠而省略證據層判斷。

核心判斷

1. 契約矩陣越完整，越容易被當成「大家都同意就安全」的社會證明。
2. 前例綠燈只能證明前一次改動，不代表本次改動層級相同。
3. 測試全綠如果沒有不得解讀為，仍可能被團隊誤說成語意或使用者行為安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 防從眾檢查`。
2. 防從眾檢查明確寫出不得用多數人同意取代證據層。
3. 防從眾檢查明確寫出不得用前例綠燈取代本次改動層級，且不得用測試全綠取代不得解讀為。

優化說明

1. 讓 review 對話在降低摩擦後，仍保留對群體壓力的抵抗力。
2. 犧牲的是文件多一道檢查；換來高風險合併不會被社會認同感稀釋。
3. 剩餘風險是實際 review 仍需有人願意引用這段檢查。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少防從眾檢查與第五批紀錄會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #差異

狀態：完成

本次使用：避免契約矩陣因格式一致而壓扁高顯著性、混合層、低顯著性，以及不同 pipeline 模式的責任差異。

核心判斷

1. 通道名稱相鄰出現在同一張矩陣時，操作者可能把不同風險合併成一段完成敘述。
2. 長線、交易、逆勢、短線模式的決策用途不同，不能只因報告格式一致就共用同一種責任語氣。
3. 文件層、測試層、runtime 層與使用者行為層若被合併回報，會模糊哪一層已驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 在 review 防從眾檢查中新增 `差異保留`。
2. 差異保留要求高顯著性、混合層、低顯著性不得合併敘述。
3. 差異保留要求不同 pipeline 模式與不同證據層分開回報。

優化說明

1. 讓操作者在追求掃讀性時，不會把責任邊界壓成同一種語氣。
2. 保留了既有矩陣格式，但補上防止格式誤導的語意護欄。
3. 剩餘風險是差異保留仍需要下一批處理誰負責維持。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_review_conformity_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_conformity_difference_emotion_is_recorded`

### 第 2 輪 / 互動思考 / #情緒智商

狀態：完成

本次使用：把高壓 review 的情緒處理寫成順序，避免時程、失敗或疲勞把限制句擠掉。

核心判斷

1. 高壓合併時，操作者常不是不知道規則，而是想快速結束不舒服的 review。
2. 直接要求全面返工會放大壓力，反而讓人更想略過契約矩陣。
3. 較好的情緒順序是先命名壓力，再回到最小補證據路徑，最後用限制句收尾。

落地修改

1. `docs/pipeline-mode-contract.md` 在 review 防從眾檢查中新增 `情緒智商`。
2. 情緒智商要求先命名壓力，例如時程、回歸失敗或 review 疲勞。
3. 情緒智商要求回到最小補證據路徑，最後用限制句收尾。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #領導原則。

優化說明

1. 讓契約矩陣能處理真實 review 中的壓力，而不只是在冷靜情境下成立。
2. 不降低證據要求；只是把補證據限制在最小可執行路徑。
3. 下一批需處理領導原則、權力動態與責任，確定誰要主動要求升級或阻止錯放。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第六批

### 第 2 輪 / 互動思考 / #領導原則

狀態：完成

本次使用：把 review 防從眾檢查推進成主責與 review 主導者必須採取的領導動作。

核心判斷

1. 若沒有人先宣告改動層級，review 會把分類責任推給最晚發現問題的人。
2. review 主導者若不主動要求升級通道，高風險改動可能被低顯著性通道錯放。
3. 完成敘述若沒有不得解讀為，領導者等於把測試綠燈誤導成語意安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 責任分工`。
2. 責任分工新增 `領導原則`，要求主責先宣告改動層級。
3. 領導原則要求 review 主導者必須要求升級通道，並確保完成敘述保留不得解讀為。

優化說明

1. 讓 review 領導不是掌控合併速度，而是保護證據與責任邊界。
2. 犧牲的是每個契約相關 patch 多一段角色宣告；換來錯放通道時有人必須主動攔下。
3. 剩餘風險是責任分工仍是文件契約，沒有自動 enforcement。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少 review 責任分工與第六批紀錄會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #權力動態

狀態：完成

本次使用：防止職位、資深度、產品壓力或合併權限覆蓋證據層與採用訊號。

核心判斷

1. 高權限同意容易被誤當成「不用補證據」。
2. 低權限操作者如果不能引用契約矩陣，紅色或黃色訊號容易被壓過。
3. 合併權限應該用來確認證據完整，而不是把紅色或黃色訊號改成綠色。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 責任分工新增 `權力動態`。
2. 權力動態明確寫出不得用職位或資深度取代證據。
3. 權力動態明確寫出低權限操作者可以引用契約矩陣要求補證據，高權限操作者不得覆蓋紅色或黃色採用訊號。

優化說明

1. 把契約矩陣從「資深者的建議」改成任何操作者都可引用的共同護欄。
2. 保留合併權限，但要求它服務證據，而不是替代證據。
3. 剩餘風險是實際團隊文化仍可能影響低權限操作者是否敢引用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_review_responsibility_map`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_leadership_power_responsibility_is_recorded`

### 第 2 輪 / 互動思考 / #責任

狀態：完成

本次使用：把改動者、reviewer、合併者的責任拆開，避免完成敘述與限制句落在沒有人負責的空白地帶。

核心判斷

1. 改動者最知道碰到哪些層級，因此要負責描述改動層級。
2. reviewer 最適合核對通道與命令是否對齊，不能只看文字是否合理。
3. 合併者最後承擔接受改動的責任，因此要確認限制句與剩餘風險存在。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 責任分工新增 `責任`。
2. 責任段落要求改動者負責描述改動層級。
3. 責任段落要求 reviewer 負責核對通道與命令，合併者負責確認限制句存在。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #自我覺察。

優化說明

1. 讓契約矩陣的完成敘述有角色可追溯，不再只是模糊的「團隊應該」。
2. 不新增工具或權限模型；先把角色責任寫進文件契約。
3. 下一批需用自我覺察與制定策略檢查：這套責任分工是否過度官僚，並收尾第 2 輪互動思考。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第七批

### 第 2 輪 / 互動思考 / #自我覺察

狀態：完成

本次使用：檢查契約矩陣自己是否正在變成過度官僚或假自動化。

核心判斷

1. 契約矩陣已累積倫理邊界、系統風險、review 對話、防從眾與責任分工；若不自我稽核，可能讓低風險改動也背上過重流程。
2. 矩陣不是自動化審核器，不能替維護者判斷所有 runtime 與使用者行為風險。
3. 低顯著性顯示層仍需要輕量通道，否則契約矩陣會阻礙原本要改善的前端語氣與維護效率。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 自我稽核與收尾策略`。
2. 自我覺察段落明確寫出契約矩陣不是自動化審核器。
3. 自我覺察段落明確寫出規則變多可能增加官僚成本，低顯著性顯示層不得被迫跑高顯著性全矩陣。

優化說明

1. 讓契約矩陣有自己的使用邊界，避免保護機制變成新負擔。
2. 保留高風險升級條件，同時維持低風險輕量通道。
3. 剩餘風險是第三輪仍需重新批判矩陣是否過重與是否需要收斂。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少自我稽核與收尾策略會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #制定策略

狀態：完成

本次使用：把第 2 輪互動思考收尾，並把下一輪入口推回批判思考重新拆解問題。

核心判斷

1. 第 2 輪互動思考已完成 20/20，但這不代表 HCS Plus 完成。
2. 最合理的下一步不是繼續往規則堆疊，而是第 3 輪批判思考重新檢查契約矩陣是否過重、是否仍有高風險缺口。
3. 策略上應先選最小足夠路徑，高風險升級，低風險保留輕量通道。

落地修改

1. `docs/pipeline-mode-contract.md` 的自我稽核段落新增 `制定策略` 與 `收尾聲明`。
2. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考完成：20/20」與第 3 輪批判思考入口。
3. 嚴格輪巡進度將下一批推進到第 3 輪 / 批判思考 / #拆解問題。

優化說明

1. 明確收斂第 2 輪互動思考，不讓流程停在下一批待辦。
2. 明確保留 HCS Plus 尚未完成：仍需第 3 輪完整習慣輪巡與後續綜合優化。
3. 下一批要用批判思考重新檢查目前契約矩陣的成本、缺口與可驗證性。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考收尾

- 已完成：20/20。
- 已落地：倫理邊界、系統風險邊界、系統關係圖、review 對話、防從眾檢查、責任分工、自我稽核與收尾策略。
- 取捨：不新增自動審核器或自動選測工具，保留人工判斷與最小測試命令。
- 剩餘風險：契約矩陣可能仍偏重，且尚未經第 3 輪批判思考重新拆解。
- 下一步：第 3 輪 / 批判思考 / #拆解問題。

## 第 3 輪批判思考第一批

### 第 3 輪 / 批判思考 / #拆解問題

狀態：完成

本次使用：把第 2 輪互動思考收尾後的契約矩陣重新拆解，避免完整矩陣在保護高風險改動時拖慢日常低風險維護。

核心判斷

1. 契約矩陣已能保護 parser/prompt/template、報告呈現與前端顯示層，但它本身已形成矩陣過重風險。
2. 最高影響問題不是再新增規則，而是維護者是否能在 2 分鐘內選到通道。
3. 低顯著性顯示層若被高顯著性流程拖慢，原本降低文案權威感的改善會變得難以維護。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪問題雷達`。
2. 問題雷達把矩陣過重、2 分鐘選通道、低顯著性被拖慢與責任分工限制句落地拆成可檢查項。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣瘦身問題雷達，說明目前套用在文件契約與測試層，尚未變成 runtime 自動流程。

優化說明

1. 解決「契約矩陣越完整越難用」的第三輪入口問題。
2. 取捨是暫不新增自動選測工具，先用文件與測試鎖住應用邊界。
3. 剩餘風險是下一批仍需分析哪些變數會造成錯誤升級或錯誤降級。

驗證方式

- `tests/test_docs_contract.py` 檢查 `契約矩陣第 3 輪問題雷達` 與矩陣過重內容。
- `tests/test_hcs_plus_state.py` 檢查第 3 輪批判思考第一批已寫入狀態表與嚴格附件。

### 第 3 輪 / 批判思考 / #問對問題

狀態：完成

本次使用：把「矩陣是不是太重」改成能決定下一步的三個問題，而不是停在籠統抱怨流程複雜。

核心判斷

1. 最該問的是哪個規則可以被一頁摘要取代，因為這直接影響日常維護入口。
2. 仍需問哪個情境必須保留完整矩陣，避免瘦身後削弱高顯著性契約保護。
3. 還要問哪個證據層仍然沒有 runtime 驗證，避免把文件契約誤當系統自動保證。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪問題雷達新增 `關鍵問題`。
2. 關鍵問題明確列出一頁摘要取代範圍、完整矩陣保留情境與 runtime 驗證缺口。
3. 主狀態表同步記錄「如何應用到系統」的邊界：目前是文件契約與測試層，不是 runtime 自動流程。

優化說明

1. 把下一批工作從「繼續加文件」轉成「決定哪些規則應瘦身、哪些不能瘦身」。
2. 保留高風險升級場景，避免一頁摘要被誤用來跳過完整矩陣。
3. 剩餘風險是關鍵問題尚未轉成 PR 模板或自動檢查。

驗證方式

- `tests/test_docs_contract.py` 檢查關鍵問題中的一頁摘要、完整矩陣與 runtime 驗證缺口。
- `tests/test_hcs_plus_state.py` 檢查 `問對問題` 已在第 3 輪第一批紀錄中完成。

### 第 3 輪 / 批判思考 / #差距分析

狀態：完成

本次使用：對照已完成的契約矩陣能力與仍缺的系統套用方式，找出下一批最小可落地缺口。

核心判斷

1. 已完成速學卡、一頁摘要、三通道命令、倫理邊界、防從眾與責任分工。
2. 仍缺口是日常入口可能太分散、限制句靠人記得寫、低顯著性通道可能被誤用到 parser/prompt/template。
3. 最小下一步不是立刻工具化，而是先用變數分析、偏誤辨識與偏誤降低定義錯誤升級與錯誤降級的護欄。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪問題雷達新增 `差距分析` 表格。
2. `docs/hcs-plus-optimization-state.md` 將第 3 輪第一批標記為完成，並把下一批推進到 `#變數分析/#偏誤辨識/#偏誤降低`。
3. 本嚴格輪巡附件同步新增第 3 輪批判思考第一批與下一步 checkpoint。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #拆解問題。

優化說明

1. 解決「知道矩陣可能過重，但不知道下一個最小修改是什麼」的缺口。
2. 取捨是暫時只改善文件與測試契約，不聲稱系統已自動判斷 review 層級。
3. 下一批需檢查哪些變數會讓一頁摘要過度簡化，或讓完整矩陣被不必要套用。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪問題雷達與進度更新會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第二批

### 第 3 輪 / 批判思考 / #變數分析

狀態：完成

本次使用：把契約矩陣瘦身的判斷拆成會影響升級或降級的變數，避免只用「看起來小」或「看起來危險」做分類。

核心判斷

1. 改動層級是第一變數：純前端顯示層、報告模板層與 parser/prompt 層需要不同通道。
2. 證據層是第二變數：文件層、測試層、runtime 層與使用者行為層不可互相替代。
3. 可逆性與時程壓力會扭曲判斷；跨層大改或趕合併時，最容易漏掉限制句與案例卡。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪變數與偏誤降低護欄`。
2. `變數分析` 表格列出改動層級、證據層、可逆性與時程壓力。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣變數與偏誤降低護欄。

優化說明

1. 將矩陣瘦身從主觀感覺改成可檢查變數。
2. 保留低風險輕量路徑，但要求跨層改動先升級或拆分。
3. 剩餘風險是變數排序仍需下一批決策樹收斂。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_variable_bias_guardrails`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_variable_bias_reduction_is_recorded`

### 第 3 輪 / 批判思考 / #偏誤辨識

狀態：完成

本次使用：標出契約矩陣瘦身最容易犯的偏誤，避免流程不是變太重，就是變太鬆。

核心判斷

1. 過度升級偏誤會讓低顯著性前端文案被迫跑高顯著性全矩陣。
2. 過度降級偏誤會把 parser/prompt/template 或完整報告正文改動包裝成只改文案。
3. 工具化幻覺與綠燈擴張偏誤會把文件契約或指定測試誤讀成 runtime 與使用者行為已驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 的新護欄章節新增 `偏誤辨識`。
2. 偏誤辨識明確列出過度升級偏誤、過度降級偏誤、工具化幻覺與綠燈擴張偏誤。
3. 本嚴格輪巡附件把上述偏誤列為第 3 輪第二批的完成項。

優化說明

1. 把「矩陣過重」和「矩陣失守」兩種相反風險同時放進護欄。
2. 不把偏誤辨識寫成抽象提醒，而是連到具體誤判：錯誤升級、錯誤降級、錯誤自動化、錯誤宣稱。
3. 剩餘風險是偏誤仍需要下一批決策樹與效用判斷來排序。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #偏誤降低

狀態：完成

本次使用：把偏誤轉成可操作的降低規則，讓維護者知道何時用輕量路徑、何時升級、何時必填限制句。

核心判斷

1. 一頁摘要優先可以降低過度升級偏誤，但不能覆蓋跨層與高顯著性改動。
2. 跨層改動升級、證據分層回報與限制句必填可以降低過度降級與綠燈擴張。
3. 案例卡觸發應只套在跨層、黃色或紅色採用訊號，避免低顯著性改動被過度流程化。

落地修改

1. `docs/pipeline-mode-contract.md` 的新護欄章節新增 `偏誤降低`。
2. 偏誤降低規則包含一頁摘要優先、跨層改動升級、證據分層回報、限制句必填與案例卡觸發。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪批判思考第二批標記為完成，並把下一批推進到 `#決策樹/#目的/#效用`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #變數分析。

優化說明

1. 讓契約矩陣真正能被套用：低風險先輕量，高風險或跨層就升級，完成回報必須分層。
2. 取捨是仍不新增自動工具；目前先把行為規範鎖在文件與測試中。
3. 下一批需要把護欄轉成決策樹、目的與效用檢查，避免維護者不知道先套哪條規則。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少變數與偏誤護欄會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第三批

### 第 3 輪 / 批判思考 / #決策樹

狀態：完成

本次使用：把前一批的變數與偏誤護欄排成可執行的分流順序，讓維護者先照決策樹選路。

核心判斷

1. 分流第一步應先判斷是否只碰前端顯示層，避免低風險改動被完整矩陣拖慢。
2. 一旦碰 parser/prompt/template 或核心契約詞，就直接升級高顯著性機器契約通道。
3. 完整報告正文、報告模板與跨層改動需要獨立分流，不能被前端顯示層或高顯著性通道概括。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪分流決策與效用校準`。
2. `決策樹` 把一頁摘要與低顯著性命令、高顯著性機器契約通道、混合層報告呈現通道、案例卡或拆分 patch、文件契約測試排成五步。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣分流決策與效用校準。

優化說明

1. 解決「知道護欄但不知道先套哪條」的操作缺口。
2. 保留低風險效率，同時讓高風險改動無法繞過升級條件。
3. 剩餘風險是決策樹目前由文件測試鎖住，尚未有實際 review 樣本統計。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_decision_purpose_utility`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_decision_purpose_utility_is_recorded`

### 第 3 輪 / 批判思考 / #目的

狀態：完成

本次使用：校準每條分流規則的目的，避免為了流程完整而增加沒有明確價值的步驟。

核心判斷

1. 決策樹的主要目的，是降低 2 分鐘選通道摩擦，而不是建立更厚的審核文件。
2. 高顯著性保護不能因瘦身而被削弱；parser/prompt/template 仍要直接升級。
3. 每個分流結果都要防止綠燈擴張，並保留低顯著性效率。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `目的校準`。
2. 目的校準列出降低 2 分鐘選通道摩擦、保住高顯著性契約、防止綠燈擴張與保留低顯著性效率。
3. 主狀態表同步記錄此批目的不是新增 runtime 自動選測，而是建立維護流程契約。

優化說明

1. 讓分流規則有可審查目的，避免矩陣瘦身又變成新官僚成本。
2. 把使用者或維護者效益放在前面：快選通道、少誤判、少過度宣稱。
3. 剩餘風險是目的目前仍偏設計假設，需要下一批用信賴區間與相關性檢查證據強度。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #效用

狀態：完成

本次使用：檢查每條分流規則的預期效用、成本與升級或停用條件，避免規則只增加負擔。

核心判斷

1. 一頁摘要優先的效用是降低選通道成本，但跨層或高風險變更時必須停用輕量路徑。
2. 高顯著性與混合層通道的效用是保護契約與報告呈現，但成本是測試與 review 較重。
3. 案例卡、拆分 patch 與證據分層回報有助防止漏跑與過度宣稱，但要保留升級或停用條件。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `效用校準` 表格。
2. 效用校準列出每條規則的預期效用、成本、升級或停用條件。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪第三批標記為完成，並把下一批推進到 `#信賴區間/#相關性/#描述統計`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #決策樹。

優化說明

1. 讓每條規則都能被日後保留、升級或停用，不把流程視為永久正確。
2. 避免只看安全效益而忽略維護成本。
3. 下一批需要用信賴區間、相關性與描述統計整理哪些觀察訊號能支持這些效用假設。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少分流決策、目的與效用校準會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第四批

### 第 3 輪 / 批判思考 / #信賴區間

狀態：完成

本次使用：校準分流決策目前能相信到什麼程度，避免把文件契約與測試綠燈外推成真實 review 或 runtime 行為。

核心判斷

1. 目前樣本只包含文件契約、HCS 狀態測試與相關前端回歸測試。
2. 不可外推成所有 review 都會正確選通道，也不可外推成 runtime 或使用者行為已驗證。
3. 至少需要觀察多個契約相關變更案例，才能討論調整決策樹。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪證據校準與觀測統計`。
2. `信賴區間` 段落列出目前樣本、不可外推範圍與觀察窗口。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣證據校準與觀測統計。

優化說明

1. 把決策樹從「看起來合理」降回「目前證據有限但可觀察」。
2. 保留文件契約的價值，但禁止用它宣稱 runtime 自動化或使用者理解。
3. 下一批需把觀察資料轉成機率與顯著性門檻。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_evidence_observation_stats`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_confidence_correlation_stats_is_recorded`

### 第 3 輪 / 批判思考 / #相關性

狀態：完成

本次使用：區分可觀測訊號與因果宣稱，避免把選通道時間下降或限制句出現率上升誤當成流程必然有效。

核心判斷

1. 選通道時間下降只能支持決策樹可能降低摩擦，不能證明通道一定選對。
2. 錯選通道下降可能和決策樹相關，也可能只是樣本較簡單或 reviewer 較熟。
3. 限制句出現率與案例卡觸發率只能說明流程被採用，不代表風險已降低。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `相關性` 表格。
2. 表格列出選通道時間、錯選通道、限制句出現率與案例卡觸發率的可支持判斷與不可推論事項。
3. 本嚴格輪巡附件將相關性限制寫入第 3 輪第四批。

優化說明

1. 降低「觀測訊號變好就是流程有效」的錯誤推論。
2. 讓後續回顧能同時看訊號與樣本脈絡。
3. 剩餘風險是仍需下一批建立回歸監測與顯著性門檻。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #描述統計

狀態：完成

本次使用：定義後續要記錄哪些統計欄位，讓分流決策的效用可以被觀察，而不是停在主觀回饋。

核心判斷

1. 樣本數是第一欄位；沒有樣本數，任何改善率都可能只是零散個案。
2. 中位選通道時間比平均時間更適合追蹤 2 分鐘摩擦，避免極端案例扭曲。
3. 錯選率、跨層改動比例、案例卡觸發率與限制句出現率能分別觀察分流品質、樣本難度、案例卡採用與完成回報品質。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `描述統計` 表格。
2. 描述統計定義樣本數、中位選通道時間、錯選率、跨層改動比例、案例卡觸發率與限制句出現率。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪第四批標記為完成，並把下一批推進到 `#機率/#迴歸/#顯著性`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #信賴區間。

優化說明

1. 讓分流決策後續能被比較，而不是只能靠文字感覺。
2. 保留「目前不可外推」的邊界，避免小樣本統計被過度使用。
3. 下一批需要判斷哪些機率、回歸與顯著性門檻能支撐後續收斂。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少證據校準與觀測統計會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第五批

### 第 3 輪 / 批判思考 / #機率

狀態：完成

本次使用：把前一批描述統計轉成風險機率判讀，避免錯選率、限制句缺漏率與案例卡漏觸發率只停在記錄欄位。

核心判斷

1. 錯選率是決策樹分流品質的主要風險機率，但少於至少 5 個案例時只能當作個案訊號。
2. 限制句缺漏率只要大於 0%，就代表完成回報仍可能把測試綠燈誇大成安全證明。
3. 案例卡漏觸發率能檢查跨層或黃色紅色訊號是否被低估，尤其是混合層與高顯著性機器契約改動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪風險機率與顯著性門檻`。
2. `機率` 表格定義錯選率、限制句缺漏率、案例卡漏觸發率與對應風險機率判讀。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣風險機率與顯著性門檻。

優化說明

1. 把「觀察到了什麼」推進成「何時應視為風險」。
2. 犧牲的是門檻仍屬暫定文件契約；它不能替代實際 review 或 runtime 自動檢查。
3. 下一批需檢查這些門檻背後的證據品質。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_probability_regression_significance_thresholds`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_probability_regression_significance_is_recorded`

### 第 3 輪 / 批判思考 / #迴歸

狀態：完成

本次使用：定義何時把觀測訊號視為流程回歸，而不是把單一窗口波動誤當成趨勢。

核心判斷

1. 連續兩個觀察窗口同方向惡化，才足以作為穩定回歸監測訊號。
2. 回歸監測必須同時看跨層改動比例；樣本變難時，錯選率上升不一定代表決策樹變差。
3. parser/prompt/template 改動被放入低顯著性通道是紅色高風險案例，可立即升級，不必等待第二窗口。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `迴歸` 規則。
2. `迴歸` 規則要求連續兩個觀察窗口，並保留紅色高風險例外。
3. `docs/hcs-plus-optimization-state.md` 的第五批系統應用方式要求同方向回歸才調整決策樹或案例卡規則。

優化說明

1. 降低單次失敗就過度改規則的機率。
2. 同時保留高風險契約錯放時的立即升級路徑。
3. 剩餘風險是目前仍缺真實窗口資料；本批只建立監測契約。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #顯著性

狀態：完成

本次使用：設定小樣本限制與升級門檻，避免測試通過、文件存在或單一案例變好被宣稱成流程改善。

核心判斷

1. 少於至少 5 個案例時，所有統計只能描述個案與待觀察風險，不得宣稱改善。
2. 至少 5 個案例後，錯選率超過 20%、限制句缺漏率大於 0%、案例卡漏觸發率超過 10% 都應升級 review。
3. 調整決策樹前要確認連續兩個觀察窗口同方向回歸，並排除樣本層級改變。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `顯著性` 規則。
2. `顯著性` 規則明確寫入小樣本、至少 5 個案例、升級門檻、調整決策樹與不得宣稱改善。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#機率/#迴歸/#顯著性` 標記為完成，並把下一批推進到 `#證據基礎/#演繹/#歸納`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #機率。

優化說明

1. 把「看起來有改善」降回可驗證的顯著性條件。
2. 保留小樣本邊界，避免文件契約被包裝成已證實成效。
3. 下一批需要檢查風險門檻背後的證據基礎、演繹規則與歸納限制。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少風險機率、回歸監測與顯著性門檻會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第六批

### 第 3 輪 / 批判思考 / #證據基礎

狀態：完成

本次使用：檢查上一批風險門檻能被哪些證據支持，避免單次測試綠燈、未標樣本數比例或章節存在被誤當成改善證據。

核心判斷

1. 文件契約測試只能證明章節與 checkpoint 還在，不能證明 review 採用或 runtime 安全。
2. 觀察窗口紀錄必須包含樣本數、改動層級與風險欄位，否則比例沒有可解釋性。
3. 案例卡能支持單一跨層案例的升級或拆分判斷，但不能代表全部生成報告母體。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪證據規則與外推邊界`。
2. `證據基礎` 表格列出文件契約測試、觀察窗口紀錄與案例卡三類可接受證據。
3. 同章節新增 `不可作為證據`，排除單次綠燈、未標樣本數比例與單純章節存在。

優化說明

1. 把「有證據」拆成證據類型與可支持判斷，降低證據層混用。
2. 犧牲的是完成回報會更嚴格；換來更少過度宣稱。
3. 下一批需檢查常見謬誤，避免維護者仍把文件綠燈當成流程成效。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_evidence_rules_induction_boundaries`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_evidence_deduction_induction_is_recorded`

### 第 3 輪 / 批判思考 / #演繹

狀態：完成

本次使用：把可接受證據轉成可執行推論規則，避免每次靠臨場判斷是否升級、是否可宣稱改善。

核心判斷

1. 若碰 parser/prompt/template 或核心契約詞，應立即升級到高顯著性機器契約通道，不等待觀察窗口。
2. 若少於至少 5 個案例，只能描述個案與待觀察風險，不能演繹為決策樹已改善。
3. 只有連續兩個觀察窗口同方向回歸，且跨層改動比例未同步升高，才可推論需要調整決策樹或案例卡規則。

落地修改

1. `docs/pipeline-mode-contract.md` 的第六批章節新增 `演繹` 規則。
2. `演繹` 規則明確寫入立即升級、小樣本限制與連續窗口條件。
3. `docs/hcs-plus-optimization-state.md` 的第六批摘要記錄這些規則如何套用到完成回報。

優化說明

1. 讓高風險契約改動不被統計等待拖延。
2. 讓低樣本比例不被誤用成趨勢證明。
3. 剩餘風險是規則仍需來源品質分級支撐，下一批會處理。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #歸納

狀態：完成

本次使用：明確寫出這批證據規則能外推到哪裡、不能外推到哪裡，避免有限文件與案例被包成完整安全證明。

核心判斷

1. 文件契約測試只能歸納到目前文件與 HCS 狀態保留護欄。
2. 觀察窗口紀錄只能歸納到已記錄案例，不能代表未記錄改動或全部 review 行為。
3. 案例卡只能歸納到代表性跨層案例，不能代表生成報告母體、歷史輸出或未來 LLM 回覆。

落地修改

1. `docs/pipeline-mode-contract.md` 的第六批章節新增 `歸納` 與 `外推邊界`。
2. `歸納` 規則明確寫入不得外推到 runtime 安全、真實使用者理解與生成報告母體。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#證據基礎/#演繹/#歸納` 標記為完成，並把下一批推進到 `#謬誤/#來源品質/#情境脈絡`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #證據基礎。

優化說明

1. 把有限觀察的邊界寫明，降低「文件有了所以系統安全」的錯誤歸納。
2. 保留後續升級空間：若要證明 runtime 或使用者理解，仍需新的證據來源。
3. 下一批將處理謬誤、來源品質與情境脈絡，防止證據規則在使用時被誤讀。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少證據規則與外推邊界會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第七批

### 第 3 輪 / 批判思考 / #謬誤

狀態：完成

本次使用：檢查證據規則最容易被誤用成哪些錯誤推論，避免文件護欄反而被包裝成流程成效或安全證明。

核心判斷

1. 測試綠燈謬誤會把文件契約測試通過誤讀成 runtime 安全或真實使用者理解改善。
2. 樣本數謬誤會把未標樣本數的比例變化誤讀成決策樹已改善。
3. 案例代表性謬誤會把單一案例卡誤讀成所有跨層改動或生成報告母體都安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪反謬誤與來源情境邊界`。
2. `謬誤` 表格列出測試綠燈謬誤、樣本數謬誤、案例代表性謬誤，以及各自錯誤推論與反謬誤護欄。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣反謬誤與來源情境邊界。

優化說明

1. 把「證據可以支持什麼」再補上「證據最常被誤用成什麼」。
2. 犧牲的是文件更嚴格；換來完成回報不容易過度宣稱。
3. 下一批需批判目前矩陣是否已過重，避免護欄本身造成摩擦。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_fallacy_source_context_boundaries`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_fallacy_source_context_is_recorded`

### 第 3 輪 / 批判思考 / #來源品質

狀態：完成

本次使用：把證據來源分成高品質來源、次級來源與不得作為完成證據，避免低品質觀察支撐高風險結論。

核心判斷

1. 高品質來源需要可重跑、可對照 diff、含樣本數與改動層級，或完整案例卡。
2. 次級來源可以輔助理解，但不能單獨支持流程改善或使用者理解改善。
3. 單次綠燈、未標樣本數比例、未列改動層級觀察與未寫限制句完成回報，都不得作為完成證據。

落地修改

1. `docs/pipeline-mode-contract.md` 的第七批章節新增 `來源品質` 表格。
2. 來源品質表把可使用來源與不得作為完成證據分開。
3. `docs/hcs-plus-optimization-state.md` 的第七批摘要記錄來源分級如何套用到完成回報。

優化說明

1. 防止低品質證據支撐高風險契約結論。
2. 讓 reviewer 可以要求補測試輸出、補樣本數或補案例卡，而不是只接受口頭說明。
3. 下一批需估算這些來源品質欄位增加多少維護成本。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #情境脈絡

狀態：完成

本次使用：限制反謬誤與來源品質規則適用在哪些情境，避免一般 UI 小改也被完整契約矩陣拖慢。

核心判斷

1. 本護欄只適用於契約相關變更，例如 parser/prompt/template、報告正文、跨層改動、案例卡或分流決策。
2. 一般 UI 文案、純排版、靜態樣式或不碰報告語意的微調，不適用完整契約矩陣。
3. 黃色、紅色、跨層、核心契約詞或樣本不足卻要調整規則的情境，需要人工 review。

落地修改

1. `docs/pipeline-mode-contract.md` 的第七批章節新增 `情境脈絡` 規則。
2. 情境脈絡規則明確寫入只適用於契約相關變更、不適用於一般 UI 文案、需要人工 review、不得替代 runtime 驗證、不得替代使用者研究。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#謬誤/#來源品質/#情境脈絡` 標記為完成，並把下一批推進到 `#批判/#估算/#詮釋框架`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #謬誤。

優化說明

1. 避免安全流程外溢到一般 UI 小改，保留低風險改動效率。
2. 同時保留高風險契約變更的人工 review 與 runtime/使用者研究邊界。
3. 下一批需批判矩陣負擔、估算執行成本，並建立完成回報詮釋框架。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少反謬誤與來源情境邊界會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第八批

### 第 3 輪 / 批判思考 / #批判

狀態：完成

本次使用：批判前面新增的契約矩陣是否已造成矩陣過重，避免護欄本身拖慢低風險 UI 與一般顯示微調。

核心判斷

1. 矩陣過重風險已出現，尤其是把每個 UI 小改都拉進完整案例卡或人工 review 時。
2. 必留護欄應保留給 parser/prompt/template、核心契約詞、跨層改動、黃色或紅色採用訊號。
3. 低風險 UI、純排版、靜態樣式與不碰報告語意的顯示微調，應可短句替代；自動選測、案例卡資料庫與觀察窗口儀表板可延後工具化。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪負擔估算與完成詮釋框架`。
2. `批判` 表格分出必留護欄、可短句替代、可延後工具化，避免同一套矩陣套到所有改動。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣負擔估算與完成詮釋框架，並把本批判斷轉成系統應用方式。

優化說明

1. 這次修改不是降低高風險契約的要求，而是避免高風險規則外溢到低風險 UI。
2. 犧牲的是文件多一層分類；換來 reviewer 可以快速判斷何時用短句、何時用完整矩陣。
3. 下一批需檢查這個分層是否足夠合理，避免又新增無法驗證的抽象語句。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_burden_estimate_interpretation_frame`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_critique_estimation_frame_is_recorded`

### 第 3 輪 / 批判思考 / #估算

狀態：完成

本次使用：估算不同改動層級的完成回報成本，讓系統應用方式不只說「要更嚴謹」，也知道大約要花多少成本。

核心判斷

1. 低風險 UI 完成回報應控制在 2 分鐘內，用 1 句通道判斷加前端測試結果即可。
2. 混合層報告呈現應控制在 3 分鐘內，補上改動層級、測試命令與限制句。
3. 高風險契約不設硬上限，因為 parser/prompt/template 或核心契約詞的錯放成本高於回報成本。

落地修改

1. `docs/pipeline-mode-contract.md` 的 `估算` 表格新增低風險 UI、混合層報告呈現與高風險契約三種完成回報成本。
2. 每種情境都寫入建議上限與最小證據，讓完成回報可以直接引用。
3. `docs/hcs-plus-optimization-state.md` 記錄「低風險 UI 2 分鐘、混合層 3 分鐘、高風險契約不設硬上限」的套用規則。

優化說明

1. 成本估算避免文件契約變成無限擴張的 checklist。
2. 低風險情境保留效率，高風險情境保留完整證據。
3. 仍需下一批用可驗證性把 26/26 完成狀態鎖住，避免估算只停在文字宣稱。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #詮釋框架

狀態：完成

本次使用：建立完成回報詮釋框架，限制文件契約、觀察窗口、runtime 驗證與使用者研究各自能支持的結論。

核心判斷

1. 文件契約通過只能代表護欄仍存在，不得宣稱安全、runtime 已驗證或使用者理解改善。
2. 觀察窗口有樣本只能支持已記錄案例的調整方向，不得宣稱理解改善，也不得推論未記錄案例。
3. runtime 驗證與使用者研究只能各自描述指定路徑或研究樣本中的結果，不能互相替代。

落地修改

1. `docs/pipeline-mode-contract.md` 的 `詮釋框架` 表格新增文件契約通過、觀察窗口有樣本、runtime 驗證通過、使用者研究完成四種證據狀態。
2. 每種證據狀態都新增禁止宣稱範圍，包含不得宣稱安全、不得宣稱理解改善與不得替代 parser/prompt/template 契約驗證。
3. `docs/hcs-plus-optimization-state.md` 將 `#批判/#估算/#詮釋框架` 標記完成，並把下一批推進到 `#合理性/#可驗證性`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #批判。

優化說明

1. 這讓完成回報可以直接回答「這些修改如何應用到系統」：依改動層級選通道，依證據狀態限制宣稱。
2. 犧牲的是完成回報語氣更保守；換來文件測試、runtime 測試與使用者研究不會被混為一談。
3. 下一批需檢查第 3 輪批判思考是否能合理收尾，並用測試鎖住完整單項完成狀態。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少負擔估算與完成詮釋框架會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第九批

### 第 3 輪 / 批判思考 / #合理性

狀態：完成

本次使用：檢查第 3 輪批判思考是否能合理收尾，而不是繼續堆疊契約矩陣、觀察欄位或工具化想像。

核心判斷

1. 第 3 輪批判思考已完成 26/26 單項，涵蓋問題拆解、變數偏誤、分流決策、證據統計、風險門檻、證據規則、反謬誤、來源情境、負擔估算與完成詮釋框架。
2. 目前合理收尾是保留文件契約與人工判斷，不新增自動選測腳本；跨層、黃色/紅色訊號與核心契約詞仍需要 reviewer 判斷。
3. 下一步應轉入第 3 輪創意思考，把矩陣從「可驗證」推向「更容易被操作者學會與採用」。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪收尾與可重跑驗證`。
2. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪批判思考收尾檢查` 與 D72 決策紀錄。
3. 本嚴格輪巡附件將第 3 輪 / 批判思考 / `#合理性` 標成完成，並把下一分類入口推進到第 3 輪創意思考。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #合理性。

優化說明

1. 這次收尾避免批判思考無限延伸，承認目前已足以支撐下一分類。
2. 犧牲的是暫不做自動選測工具；換來責任邊界更清楚，不把人工判斷包成假自動化。
3. 剩餘風險是矩陣仍可能學習成本偏高，因此下一批用創意思考處理學習科學、限制條件與類比。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪收尾與 26/26 checkpoint 會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 批判思考 / #可驗證性

狀態：完成

本次使用：把第 3 輪批判思考完成狀態轉成可重跑檢查，避免只靠人工記憶宣稱 26/26 已完成。

核心判斷

1. 可驗證性需要同時鎖住四層：契約文件、主狀態表、嚴格附件、下一分類入口。
2. `tests/test_hcs_plus_state.py` 需證明第 3 輪批判思考 `#合理性/#可驗證性` 已完成，且第 3 輪創意思考成為下一批。
3. `tests/test_docs_contract.py` 需證明契約文件保留不得宣稱 HCS Plus 完成、保留人工判斷、失敗即回到批判思考等限制。

落地修改

1. `tests/test_docs_contract.py` 新增第 3 輪收尾與可重跑驗證契約測試。
2. `tests/test_hcs_plus_state.py` 新增第 3 輪批判思考收尾 checkpoint 測試，並把進度期待改成 `#合理性/#可驗證性` 完成。
3. 本嚴格輪巡附件新增「第 3 輪批判思考收尾」，並將下一步推進到第 3 輪 / 創意思考 / #學習科學。

優化說明

1. 將第 3 輪批判思考從多個契約矩陣章節收束成可驗證 checkpoint。
2. 明確保留 HCS Plus 尚未完成的事實：目前只是第 3 輪批判思考完成，完整流程還要繼續創意思考、溝通思考、互動思考與綜合優化。
3. 若後續測試或文件缺少限制句，必須回到批判思考補證據，不得直接推進。

驗證方式

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 3 輪批判思考收尾

- 已完成：26/26。
- 合理性結論：第 3 輪批判思考已完成契約矩陣瘦身、證據分層、反謬誤、來源情境、負擔估算與完成詮釋框架；可合理轉入創意思考，不新增自動選測腳本。
- 可驗證性結論：第 3 輪批判思考 26 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 與 `tests/test_docs_contract.py` 鎖住。
- 邊界：不得宣稱 HCS Plus 完成、不得宣稱 runtime 安全、不得宣稱使用者理解改善。
- 下一步：第 3 輪 / 創意思考 / #學習科學。

## 第 3 輪創意思考第一批

### 第 3 輪 / 創意思考 / #學習科學

狀態：完成

本次使用：把第 3 輪批判思考收尾後的契約矩陣，轉成第一次使用也能快速進入的學習路徑。

核心判斷

1. 維護者不應先讀完整矩陣才知道怎麼開始；學習入口應先回答「現在要判斷什麼」。
2. 三層學習路徑最小足夠：10 秒判斷改動風險、90 秒執行命令與限制句、5 分鐘復盤錯選或漏證據。
3. 學習入口必須保留前一輪批判思考的限制，不可把易學性包成安全保證。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪創意學習入口`。
2. 該章節新增 `三層學習路徑`，分成 `10 秒判斷`、`90 秒執行`、`5 分鐘復盤`。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣學習入口`。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #學習科學。

優化說明

1. 這讓契約矩陣從完整規範變成可進入的學習流程。
2. 犧牲的是仍需人工判斷；換來維護者能先做小判斷，再逐步深入。
3. 下一批需把三層路徑轉成更明確的操作演算法。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_creative_learning_entry`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_learning_constraints_analogy_is_recorded`

### 第 3 輪 / 創意思考 / #限制條件

狀態：完成

本次使用：界定學習入口不做哪些事，避免它被誤用成 runtime 改動、自動選測或遙測方案。

核心判斷

1. 本批只改文件契約與學習順序，不改 runtime 行為、parser、prompt、template、報告生成或前端互動。
2. 不新增自動選測腳本，也不新增遙測；目前仍靠操作者判斷改動層級並人工記錄觀察。
3. 黃色/紅色訊號、跨層改動與核心契約詞仍要人工 review，不能被學習入口取代。

落地修改

1. `docs/pipeline-mode-contract.md` 的創意學習入口新增 `限制條件`。
2. 限制條件明確寫入不改 runtime 行為、不新增自動選測腳本、不新增遙測、不替代人工 review。
3. `docs/hcs-plus-optimization-state.md` 將這些限制轉成系統應用方式，要求安檢通過不得外推為 runtime 安全或使用者理解改善。

優化說明

1. 限制條件讓學習入口保持輕量，不漂移成新工具專案。
2. 代價是沒有立即自動化；收益是維護責任與證據邊界仍清楚。
3. 下一批可用設計思考降低限制條件帶來的閱讀阻力。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 創意思考 / #類比

狀態：完成

本次使用：用登機前安檢類比說明契約矩陣如何分流、補證據與限制外推。

核心判斷

1. 快速通道對應低風險 UI 與不碰報告語意的顯示微調。
2. 人工複檢對應黃色/紅色訊號、跨層改動、核心契約詞或高風險契約。
3. 證據托盤對應測試輸出、diff、案例卡、觀察窗口與完成回報限制句；不把安檢通過解讀成航程安全。

落地修改

1. `docs/pipeline-mode-contract.md` 的創意學習入口新增 `類比` 與登機前安檢對照表。
2. 對照表把快速通道、人工複檢、證據托盤連到系統改動層級與不可外推範圍。
3. `docs/hcs-plus-optimization-state.md` 將類比轉成系統應用方式：安檢通過不得宣稱 runtime 安全、使用者理解改善或 HCS Plus 完成。

優化說明

1. 類比降低抽象矩陣的進入成本，讓新維護者先理解分流與證據托盤。
2. 類比仍有邊界：它只輔助學習，不取代實際測試與 review。
3. 下一批需把這個類比轉成可直接套用的捷思規則與操作演算法。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少創意學習入口會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第二批

### 第 3 輪 / 創意思考 / #演算法

狀態：完成

本次使用：把上一批的 10 秒判斷、90 秒執行與 5 分鐘復盤，轉成可直接照做的操作演算法。

核心判斷

1. 三層學習入口仍偏概念；操作者需要明確知道先判斷、再選通道、再裝證據托盤、最後怎麼完成回報。
2. 四步操作演算法可以降低第一次使用時的順序成本，也能讓 reviewer 快速看出缺在哪一步。
3. 演算法仍保留人工判斷，不把選通道自動化。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪操作演算法與捷思規則`。
2. 該章節新增 `四步操作演算法`：`步驟 1：10 秒判斷`、`步驟 2：選擇通道`、`步驟 3：裝好證據托盤`、`步驟 4：完成回報`。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣操作演算法與捷思規則`。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #演算法。

優化說明

1. 這把學習入口從「理解框架」推進成「可照做流程」。
2. 代價是文件稍長；收益是每一步都有明確產出與回退條件。
3. 下一批需檢查這套演算法是否能再最佳化，避免低風險 UI 被過度流程化。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_operation_algorithm_and_heuristics`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_algorithm_design_heuristics_is_recorded`

### 第 3 輪 / 創意思考 / #設計思考

狀態：完成

本次使用：從操作者情境出發，讓不同改動類型走不同預設路徑，而不是要求所有人讀同一套矩陣。

核心判斷

1. 只改低風險 UI 的操作者需要快速通道，不應被高風險契約矩陣拖慢。
2. 改報告模板或正文呈現的操作者需要混合層報告呈現通道，避免只跑前端測試。
3. 改 parser、prompt、template 或核心契約詞的操作者需要先人工複檢，不能用短句帶過。

落地修改

1. `docs/pipeline-mode-contract.md` 的第二批章節新增 `設計思考` 表格。
2. 表格新增 `情境 A：只改低風險 UI`、`情境 B：改報告模板或正文呈現`、`情境 C：改 parser、prompt、template 或核心契約詞`。
3. `docs/hcs-plus-optimization-state.md` 將三個情境轉成系統應用方式。

優化說明

1. 情境化設計讓不同維護者不用自行翻譯矩陣。
2. 犧牲的是仍需判斷自己屬於哪個情境；下一批可用資料視覺化或採用訊號降低誤判。
3. 高風險情境仍保留案例卡、必跑命令與限制句。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 創意思考 / #捷思法

狀態：完成

本次使用：把操作演算法壓成三條快速規則，讓維護者在高壓 review 或小改動時仍能正確分流。

核心判斷

1. 有核心契約詞就先人工複檢，避免把 parser/prompt/template 風險降級。
2. 只在前端顯示才走快速通道，避免前端測試被誤用成 parser/prompt 安全證明。
3. 缺少限制句就不得完成，避免完成回報過度宣稱。

落地修改

1. `docs/pipeline-mode-contract.md` 的第二批章節新增 `捷思法`。
2. 捷思法寫入 `有核心契約詞就先人工複檢`、`只在前端顯示才走快速通道`、`缺少限制句就不得完成`。
3. `docs/hcs-plus-optimization-state.md` 將 `#演算法/#設計思考/#捷思法` 標記完成，並把下一批推進到 `#最佳化/#假說發展/#資料視覺化`。

優化說明

1. 三條捷思規則讓四步演算法更容易在實務 review 中被記住。
2. 捷思規則不是例外通行證；任何命中高風險條件仍要回到完整通道。
3. 下一批需建立採用假說與可視化訊號，觀察這些規則是否降低錯選通道。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少操作演算法與捷思規則會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第三批

### 第 3 輪 / 創意思考 / #最佳化

狀態：完成

本次使用：把操作演算法要最佳化的目標收斂成可觀察的採用摩擦，而不是抽象地說「流程更好用」。

核心判斷

1. 目前最重要的採用摩擦是錯選通道、漏跑命令、限制句缺漏與案例卡漏補。
2. 最佳化目標是降低 review 摩擦與缺漏，不是宣稱流程已改善。
3. 最小調整應先回到四步操作演算法、證據托盤或人工複檢提示，不新增工具或遙測。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪採用最佳化與訊號板`。
2. 該章節新增 `最佳化` 表格，把錯選通道、漏跑命令、限制句缺漏、案例卡漏補寫成採用摩擦。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣採用最佳化與訊號板`。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #最佳化。

優化說明

1. 這讓「操作演算法是否好用」能被具體觀察，而不是只靠主觀感受。
2. 犧牲的是暫時仍靠人工觀察；換來不新增遙測、不擴大 runtime 面。
3. 下一批需把採用摩擦轉成代表性案例模型與案例卡。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_adoption_optimization_signal_board`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_optimization_hypothesis_visualization_is_recorded`

### 第 3 輪 / 創意思考 / #假說發展

狀態：完成

本次使用：把操作演算法、證據托盤與快速規則各自轉成可觀察假說，避免直接宣稱改善。

核心判斷

1. 假說 1：四步操作會降低錯選通道，但只有人工觀察與足夠樣本才能支持趨勢。
2. 假說 2：證據托盤會降低漏跑命令，但不能推論 runtime 安全或測試覆蓋完整。
3. 假說 3：三條快速規則會降低限制句缺漏，但不能推論使用者理解改善。

落地修改

1. `docs/pipeline-mode-contract.md` 的第三批章節新增 `假說發展`。
2. 假說表寫入三個可觀察假說、觀察方式與不可宣稱範圍。
3. `docs/hcs-plus-optimization-state.md` 記錄假說仍需下一批抽樣方式支撐，不得用單一觀察過度外推。

優化說明

1. 假說讓採用觀察有方向，但保留證據不足時不得宣稱改善。
2. 下一批必須處理抽樣與個案，否則訊號板容易只剩主觀顏色。
3. 仍維持文件契約，不新增產品事件或背景收集。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 創意思考 / #資料視覺化

狀態：完成

本次使用：把人工觀察結果做成綠色、黃色、紅色採用訊號板，讓 reviewer 快速知道該保留、補提示或停止合併。

核心判斷

1. 綠色只代表目前人工觀察未見缺漏，不代表已改善。
2. 黃色代表出現 1 到 2 次採用摩擦，需要補案例、補提示或重寫步驟。
3. 紅色代表高風險契約被放進快速通道、核心契約詞缺人工複檢，或完成回報宣稱安全/理解改善，必須停止合併。

落地修改

1. `docs/pipeline-mode-contract.md` 的第三批章節新增 `資料視覺化` 與 `採用訊號板`。
2. 採用訊號板定義綠色、黃色、紅色訊號與對應行動。
3. `docs/hcs-plus-optimization-state.md` 將 `#最佳化/#假說發展/#資料視覺化` 標記完成，並把下一批推進到 `#建模/#抽樣/#個案研究`。

優化說明

1. 視覺化在這裡是文字訊號板，不新增 UI 或產品遙測。
2. 訊號板讓採用摩擦更容易掃讀，但不能替代測試、runtime 驗證或使用者研究。
3. 下一批要建立案例模型，讓每個黃色或紅色訊號可追溯到具體改動。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少採用最佳化與訊號板會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第四批

### 第 3 輪 / 創意思考 / #建模

狀態：完成

本次使用：把採用訊號板轉成代表性案例模型，讓綠色、黃色與紅色不只是一個顏色，而是能回到具體改動類型與必看證據。

核心判斷

1. 訊號板若不能連回案例，黃色/紅色很難被複盤。
2. 四類模型足夠覆蓋目前維護情境：低風險快速通道、混合層報告呈現、高風險契約人工複檢、紅色阻擋。
3. 模型只代表案例類型，不代表母體趨勢。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪案例模型與抽樣案例卡`。
2. 章節新增 `代表性案例模型`，包含模型 A：低風險快速通道案例、模型 B：混合層報告呈現案例、模型 C：高風險契約人工複檢案例、模型 D：紅色阻擋案例。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣案例模型與抽樣案例卡`，並把 `#建模` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #建模。

優化說明

1. 建模讓每個訊號可以回到具體案例，不再停在抽象顏色。
2. 代價是文件多一層分類；收益是 review 時能先辨識通道與必看證據。
3. 仍不新增遙測、不新增 runtime 行為，也不把案例模型當作自動判斷器。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少案例模型與抽樣案例卡會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 創意思考 / #抽樣

狀態：完成

本次使用：定義哪些觀察需要抽成案例，避免只挑方便或漂亮的綠色案例。

核心判斷

1. 每個觀察窗口至少要保留實際出現的代表性模型，未出現時要明記「本窗口未觀察到」。
2. 黃色或紅色必抽，因為錯選通道、漏跑命令、限制句缺漏或案例卡漏補才是最需要回放的學習材料。
3. 少於 5 個案例不得宣稱趨勢；只能描述個案與待觀察風險。

落地修改

1. `docs/pipeline-mode-contract.md` 的第四批章節新增 `抽樣`。
2. 抽樣規則寫入 `代表性抽樣規則`、`每個觀察窗口`、`黃色或紅色必抽` 與 `少於 5 個案例不得宣稱趨勢`。
3. `docs/hcs-plus-optimization-state.md` 的系統應用方式明確要求少於 5 個案例不得外推。

優化說明

1. 抽樣規則讓案例卡不只收集成功案例，也收集流程失守案例。
2. 這能支撐下一批比較組與介入研究，但目前仍只是觀察設計，不是改善證明。
3. 若某模型未出現，不得拿其他模型補位，避免代表性被偷換。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_case_models_sampling_cards`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_models_sampling_case_cards_is_recorded`

### 第 3 輪 / 創意思考 / #個案研究

狀態：完成

本次使用：把抽到的案例收斂成案例卡格式，讓每個個案都有可追溯的改動、通道、證據、訊號與不可外推邊界。

核心判斷

1. 個案研究要能回答「這次改了什麼、選了哪條通道、看了哪些證據」。
2. 案例卡必須放入限制句與不可外推，避免單一案例被講成流程改善或 runtime 安全。
3. 補救行動要寫進案例卡，否則黃色或紅色訊號很容易只停在紀錄而沒有回到操作流程。

落地修改

1. `docs/pipeline-mode-contract.md` 的第四批章節新增 `個案研究` 與 `案例卡格式`。
2. 案例卡格式收斂為改動描述、改動層級、選擇通道、證據托盤、採用訊號、限制句、補救行動、不可外推。
3. `docs/hcs-plus-optimization-state.md` 將 `#建模/#抽樣/#個案研究` 標記完成，並把下一批推進到 `#比較組/#介入研究/#訪談調查`。

優化說明

1. 案例卡讓訊號板可被複盤，也讓下一批能比較案例模型使用前後的錯選通道、漏跑命令與限制句缺漏。
2. 目前不宣稱它已改善 review 行為；只宣稱文件契約與測試已鎖住案例格式。
3. 完整 HCS Plus 仍未完成，下一批需繼續創意思考的比較與介入設計。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少案例卡格式會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第五批

### 第 3 輪 / 創意思考 / #比較組

狀態：完成

本次使用：把案例模型的使用前後拆成基準組與介入組，讓「是否更少錯選通道、漏跑命令與限制句缺漏」可以被觀察，而不是靠印象判斷。

核心判斷

1. 基準組只使用四步操作演算法、採用訊號板與既有完成回報，介入組加入案例模型、案例卡與補救回放。
2. 可觀察指標應聚焦錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率。
3. 比較組是 review 方法，不是統計實驗；不得宣稱因果改善。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪比較與介入回饋設計`。
2. 章節新增 `比較組`，定義基準組、介入組、錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣比較與介入回饋設計`，並把 `#比較組` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #比較組。

優化說明

1. 比較組讓上一批案例模型有可觀察的使用前後對照。
2. 代價是仍需人工記錄觀察窗口；收益是下一批能把觀察欄位整理成可複製流程。
3. 目前只建立比較設計，不宣稱改善，也不新增產品遙測。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少比較與介入回饋設計會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 創意思考 / #介入研究

狀態：完成

本次使用：把介入收斂成最小可執行動作，避免把案例模型變成厚重流程。

核心判斷

1. 最小介入應發生在改檔前與完成回報時，而不是等 review 結束才補紀錄。
2. 改檔前 60 秒案例模型選擇能讓操作者先承認風險層級；完成回報三欄補強能降低漏跑命令與限制句缺漏。
3. 介入停止條件必須保護低風險 UI 快速通道，也必須阻擋高風險契約被降級。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `介入研究`。
2. 介入研究寫入 `最小介入方案`、`改檔前 60 秒案例模型選擇`、`完成回報三欄補強`、`黃色或紅色補救回放` 與 `介入停止條件`。
3. `docs/hcs-plus-optimization-state.md` 將介入研究轉成系統應用方式：高風險或混合層改動先走介入組，低風險 UI 可保留快速通道。

優化說明

1. 這讓案例模型從分類工具變成改檔前的輕量介入。
2. 仍保留人工判斷與 pytest；介入只降低漏記與錯放風險，不替代測試。
3. 若介入流程拖慢低風險 UI，應回到短句回報，避免契約過度流程化。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_comparison_intervention_feedback_design`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_comparison_intervention_feedback_is_recorded`

### 第 3 輪 / 創意思考 / #訪談調查

狀態：完成

本次使用：把操作者回饋壓成三題，檢查案例模型與案例卡是否真的可用，而不是只在文件中完整。

核心判斷

1. 回饋題要問能否在 2 分鐘內選出通道，因為選通道時間是第 3 輪一直追蹤的摩擦。
2. 詢問哪個案例模型最難判斷，可以暴露模型邊界不清或通道重疊。
3. 詢問案例卡是否暴露漏跑命令或限制句缺漏，可以檢查介入是否找到實際缺口。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `訪談調查` 與 `操作者回饋題`。
2. 回饋題寫入 `你能否在 2 分鐘內選出通道`、`哪個案例模型最難判斷`、`案例卡是否暴露漏跑命令或限制句缺漏`。
3. `docs/hcs-plus-optimization-state.md` 將 `#比較組/#介入研究/#訪談調查` 標記完成，並把下一批推進到 `#觀察研究/#研究複製`。

優化說明

1. 訪談調查讓比較設計有操作者回饋入口，但回饋答案只作為輔助證據。
2. 不新增產品遙測；也不得用回饋題答案替代 pytest 或人工 review。
3. 下一批需把觀察與複製流程寫清楚，讓同一設計能被下一位操作者重複使用。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少操作者回饋題會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第六批

### 第 3 輪 / 創意思考 / #觀察研究

狀態：完成

本次使用：把比較組、介入方案與操作者回饋題轉成可填寫的觀察記錄欄位，讓觀察不只停在記憶、顏色訊號或完成回報印象。

核心判斷

1. 觀察研究需要固定欄位，否則錯選通道率、漏跑命令率與限制句缺漏率會在不同操作者之間失去口徑。
2. 觀察窗口、變更案例 ID、選定案例模型、實際選擇通道與實際執行命令，是追溯一個案例的最低資訊。
3. 完成回報三欄、觀察結果、操作者回饋摘要、補救行動與不可外推，能避免觀察紀錄被誤讀成改善證明。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪觀察與複製準則`。
2. 該章節新增 `觀察研究` 與 `觀察記錄欄位`，包含觀察窗口、變更案例 ID、選定案例模型、實際選擇通道、實際執行命令、完成回報三欄、觀察結果、操作者回饋摘要、補救行動與不可外推。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣觀察與複製準則`，並把 `#觀察研究` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #觀察研究。

優化說明

1. 觀察欄位讓第五批的比較與介入設計有固定資料入口。
2. 代價是每個觀察窗口需要多填欄位；收益是下一位操作者可以重做同一觀察。
3. 本章節仍不新增產品遙測，不替代 pytest 或人工 review，也不得宣稱改善。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪觀察與複製準則會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 創意思考 / #研究複製

狀態：完成

本次使用：把觀察流程做成可複製檢查清單，讓下一位操作者不用讀完整 HCS 附件，也能用同一口徑記錄案例。

核心判斷

1. 可複製不是代表流程有效，而是代表下一位操作者能用同一觀察窗口定義、同一案例模型選項與同一指標口徑重做紀錄。
2. 同一介入停止條件與同一限制句能避免低風險 UI 被過度流程化，也避免高風險契約被錯誤降級。
3. 若沒有實際案例，必須記錄「本窗口未觀察到」，不得用假案例補位。

落地修改

1. `docs/pipeline-mode-contract.md` 的第六批章節新增 `研究複製`。
2. 複製檢查清單寫入同一觀察窗口定義、同一案例模型選項、同一指標口徑、同一介入停止條件與同一限制句。
3. `docs/hcs-plus-optimization-state.md` 將 `#觀察研究/#研究複製` 標記完成，並把下一批推進到第 3 輪 / 溝通思考 / `#受眾/#組成/#語意含義`。

優化說明

1. 這完成第 3 輪創意思考 17/17，將案例模型、比較介入與觀察複製收斂為一組可重做文件契約。
2. 剩餘風險轉向溝通思考：不同維護者是否能正確理解受眾、欄位組成與語意邊界。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪溝通思考、互動思考與最終綜合優化。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_observation_replication_rules`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_observation_replication_is_recorded`

## 第 3 輪創意思考收尾

- 已完成：17/17。
- 收尾結論：第 3 輪創意思考已把第 3 輪批判矩陣轉成學習入口、操作演算法、採用訊號、案例模型、比較介入、觀察欄位與複製準則。
- 邊界：不得宣稱 HCS Plus 完成、不得宣稱 runtime 安全、不得宣稱使用者理解改善、不得宣稱流程已改善。
- 下一步：第 3 輪 / 溝通思考 / #受眾。

## 第 3 輪溝通思考第一批

### 第 3 輪 / 溝通思考 / #受眾

狀態：完成

本次使用：把第 3 輪創意思考收尾後的觀察與複製準則，分成不同維護者能先進入的讀者角色。

核心判斷

1. 完整契約矩陣對低風險 UI 維護者太重，但對契約複檢維護者又不可省略。
2. 最小受眾分流需要四類：低風險 UI 維護者、報告呈現維護者、契約複檢維護者與觀察流程維護者。
3. 受眾分流只縮短閱讀路徑，不改變證據責任或通道升級條件。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪讀者語意入口`。
2. 該章節新增 `受眾` 表格，定義低風險 UI 維護者、報告呈現維護者、契約複檢維護者與觀察流程維護者。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪溝通思考契約矩陣讀者語意入口`，並把 `#受眾` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 溝通思考 / #受眾。

優化說明

1. 受眾分流讓不同維護者先看自己最容易誤用的入口。
2. 代價是文件多一層角色分類；收益是低風險與高風險路徑不再互相拖慢。
3. 仍不新增產品遙測、不替代 pytest 或人工 review，也不改 runtime。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪讀者語意入口會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 溝通思考 / #組成

狀態：完成

本次使用：把讀者入口拆成四步，避免受眾分類只停在名詞，而沒有可照做的閱讀順序。

核心判斷

1. 第一步要先判斷讀者角色，避免一開始就讀完整矩陣。
2. 第二步只讀對應入口，讓低風險 UI 維護者不被完整流程拖慢，高風險契約也不被誤放快速通道。
3. 第三步補齊觀察欄位，第四步用限制句收尾，讓閱讀入口仍保留證據與語意邊界。

落地修改

1. `docs/pipeline-mode-contract.md` 的讀者語意入口新增 `組成`。
2. 組成寫入 `第一步：先判斷讀者角色`、`第二步：只讀對應入口`、`第三步：補齊觀察欄位`、`第四步：用限制句收尾`。
3. `docs/hcs-plus-optimization-state.md` 將四步組成轉成系統應用方式。

優化說明

1. 組成讓讀者入口從角色表變成可執行順序。
2. 仍保留觀察欄位與限制句，避免簡化閱讀時也簡化責任。
3. 下一批需要把這四步整理成更清楚的章節導覽與專業核心主張。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_reader_semantic_entry`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_audience_composition_semantics_is_recorded`

### 第 3 輪 / 溝通思考 / #語意含義

狀態：完成

本次使用：明確定義讀者角色、入口、觀察欄位、複製成功與低風險的語意邊界，避免讀者把入口誤讀成自動化或安全證明。

核心判斷

1. 讀者角色不是權限等級，不能被用來跳過證據或覆蓋紅色訊號。
2. 入口不是自動判斷器，觀察欄位不是 pytest，複製成功不是改善證明。
3. 低風險不代表低責任；即使走快速通道，也要保留限制句。

落地修改

1. `docs/pipeline-mode-contract.md` 的讀者語意入口新增 `語意含義`。
2. 語意含義寫入讀者角色不是權限等級、入口不是自動判斷器、觀察欄位不是 pytest、複製成功不是改善證明、低風險不代表低責任。
3. `docs/hcs-plus-optimization-state.md` 將 `#受眾/#組成/#語意含義` 標記完成，並把下一批推進到 `#組織結構/#專業性/#論點`。

優化說明

1. 語意邊界讓第 3 輪溝通思考不只改善閱讀，也避免新入口被誤用。
2. 這批仍只是文件契約，不新增產品遙測、不替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成，下一批需整理章節結構、專業語氣與核心論點。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少語意邊界會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪溝通思考第二批

### 第 3 輪 / 溝通思考 / #組織結構

狀態：完成

本次使用：把讀者語意入口整理成可依序操作的章節導覽，讓維護者不用在角色、案例模型、觀察欄位與限制句之間來回找線索。

核心判斷

1. 讀者語意入口已經說明誰要讀什麼，但仍缺一條從入口到完成回報的章節順序。
2. 第 3 輪的組織結構應先定位讀者角色，再選通道與案例模型，接著補觀察欄位，最後用限制句與核心論點收尾。
3. 這個順序只改善維護導覽，不改變 pytest、人工 review 或高風險契約升級條件。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪維護導覽與核心論點`。
2. 章節導覽寫入先定位讀者角色、再選通道與案例模型、接著補觀察欄位、最後用限制句與核心論點收尾。
3. `docs/hcs-plus-optimization-state.md` 新增同名狀態章節，並將本批對應到第 3 輪溝通思考第二批。
4. 歷史 checkpoint：下一步：第 3 輪 / 溝通思考 / #組織結構。

優化說明

1. 組織結構讓前一批的受眾、組成與語意含義變成可照順序引用的維護導覽。
2. 代價是文件增加一個第 3 輪收斂章節；收益是後續完成回報更容易保持同一口徑。
3. 完整 HCS Plus 仍未完成，這批只完成第 3 輪溝通思考的第二組單項習慣。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪維護導覽與核心論點會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 溝通思考 / #專業性

狀態：完成

本次使用：把維護回報語氣限制在可驗證範圍內，避免把文件契約、觀察窗口或測試綠燈誇大成安全證明。

核心判斷

1. 專業性不是把句子寫得更正式，而是準確說出證據層與未驗證範圍。
2. 維護語氣必須只描述觀察窗口、明列未跑命令、把紅色訊號說成停止條件、不得把測試綠燈寫成安全證明。
3. 若回報沒有說明限制，就容易把低風險快速通道誤讀成低責任，或把文件測試誤讀成 runtime 安全。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護導覽新增 `專業性` 與 `維護語氣` 表格。
2. 維護語氣明列四個要求：只描述觀察窗口、明列未跑命令、把紅色訊號說成停止條件、不得把測試綠燈寫成安全證明。
3. `docs/hcs-plus-optimization-state.md` 把專業性對應到同章節，並記錄下一批仍需整理成完成回報表達句型。

優化說明

1. 專業語氣降低了綠燈擴張、觀察替代 pytest 與紅色訊號被淡化的風險。
2. 本批沒有新增 runtime 驗證或產品遙測，因此回報必須明確說出未跑命令與不可宣稱範圍。
3. 這讓後續 review 更容易分辨「已記錄流程」和「已驗證行為」。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_maintenance_guide_core_argument`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_structure_professional_argument_is_recorded`

### 第 3 輪 / 溝通思考 / #論點

狀態：完成

本次使用：把第 3 輪契約矩陣的核心主張收斂成一句可引用的目的，避免讀者以為文件越厚代表系統越安全。

核心判斷

1. 契約矩陣的目的不是提高文件厚度，而是讓低風險改動更快收尾、讓高風險契約更早升級、讓觀察紀錄可複製但不被誤讀。
2. 核心主張必須同時保留限制：不得宣稱改善，不得替代 pytest 或人工 review。
3. 若沒有明確論點，維護導覽會變成另一層形式流程，而不是幫助操作者做正確取捨。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護導覽新增 `論點` 與 `核心主張`。
2. 核心主張明確寫出低風險更快收尾、高風險更早升級、觀察紀錄可複製但不被誤讀。
3. `docs/hcs-plus-optimization-state.md` 將 `#組織結構/#專業性/#論點` 標記完成，並把下一批推進到 `#溝通設計/#表達/#媒介/#多媒體`。

優化說明

1. 論點讓第 3 輪溝通思考第二批有一個可引用的判斷核心。
2. 它把文件加厚的風險拉回維護效率與風險升級，而不是追求更多規則。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪溝通思考第三批、互動思考與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少核心主張會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪溝通思考第三批

### 第 3 輪 / 溝通思考 / #溝通設計

狀態：完成

本次使用：把維護導覽與核心論點壓成可直接貼進回報的一頁摘要，讓操作者不用重寫完整矩陣也能保留改動層級、命令與限制。

核心判斷

1. 第二批已建立章節導覽與核心主張，但日常回報仍需要更短的溝通設計。
2. 一頁摘要必須先說本次改動層級、再列已跑命令與未跑命令、最後寫不得解讀為。
3. 短版回報只降低溝通摩擦，不改變 pytest、人工 review 或高風險契約升級條件。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪短版回報與媒介取捨`。
2. 該章節新增 `溝通設計` 與 `一頁摘要`，固定先說改動層級、再列命令、最後寫不得解讀為。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪溝通思考契約矩陣短版回報與媒介取捨`。
4. 歷史 checkpoint：下一步：第 3 輪 / 溝通思考 / #溝通設計。

優化說明

1. 溝通設計把維護導覽轉成可複製的一頁摘要。
2. 代價是仍要維護一段短版契約；收益是低風險回報不必重述完整矩陣。
3. 本批不新增 runtime、不新增圖像流程、不新增自動選測工具。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪短版回報會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 溝通思考 / #表達

狀態：完成

本次使用：把完成回報收斂成固定句型，避免每次靠臨場表述而漏掉通道、命令或限制。

核心判斷

1. 句型要先固定責任邊界，再允許操作者填入具體內容。
2. 最小表達單位是「我選擇的通道是」、「我已執行的命令是」、「本次不得解讀為」。
3. 表達句型必須同時要求未跑命令原因，避免把未驗證證據層藏在綠燈後面。

落地修改

1. `docs/pipeline-mode-contract.md` 的短版回報章節新增 `表達` 與 `建議句型` 表格。
2. 表格固定通道、命令與限制三類句型。
3. `docs/hcs-plus-optimization-state.md` 把表達對應到同章節，並記錄下一批需檢查責任轉嫁風險。

優化說明

1. 建議句型讓完成回報可搜尋、可複製、可被測試鎖住。
2. 它避免回報只寫「測試通過」，卻沒有說明未跑命令或不得解讀為。
3. 句型仍不是證據本身，後續互動思考需要檢查倫理與責任邊界。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_short_report_media_choice`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_short_report_media_choice_is_recorded`

### 第 3 輪 / 溝通思考 / #媒介

狀態：完成

本次使用：決定短版回報應使用文字與表格，而不是新增圖像流程或媒介切換。

核心判斷

1. 本契約需要被搜尋、複製、貼入 PR 與 HCS 狀態表，因此文字與表格優先。
2. 不要新增圖像流程，避免圖片讓操作者跳過已跑命令、未跑命令與不得解讀為。
3. 不要用多媒體替代限制句；任何示意只能輔助，不能取代文字限制。

落地修改

1. `docs/pipeline-mode-contract.md` 的短版回報章節新增 `媒介`。
2. 媒介規則寫入文字與表格優先、不要新增圖像流程、不要用多媒體替代限制句。
3. `docs/hcs-plus-optimization-state.md` 把媒介取捨記錄為第 3 輪溝通思考的落地決策。

優化說明

1. 媒介取捨把「容易引用」放在視覺表現之前。
2. 這避免為了讓矩陣更漂亮而削弱可測試、可搜尋與可審查性。
3. 若未來真的要加截圖或錄影，仍需保留文字版限制。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_short_report_media_choice`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_short_report_media_choice_is_recorded`

### 第 3 輪 / 溝通思考 / #多媒體

狀態：完成

本次使用：明確暫不新增圖像或多媒體，避免把媒介升級誤當成系統驗證升級。

核心判斷

1. 多媒體會讓文件看起來更完整，但也可能讓操作者跳過文字限制與未跑命令。
2. 本階段應保留可搜尋文字，讓 pytest、review 與 HCS 狀態能直接鎖住關鍵語句。
3. 完成證據仍是 pytest 與人工 review；多媒體不得替代測試、lint、build 或 reviewer 判斷。

落地修改

1. `docs/pipeline-mode-contract.md` 的短版回報章節新增 `多媒體`。
2. 多媒體規則寫入暫不新增圖像或多媒體、保留可搜尋文字、保留 pytest 與人工 review。
3. `docs/hcs-plus-optimization-state.md` 將 `#溝通設計/#表達/#媒介/#多媒體` 標記完成，並把下一批推進到 `#倫理考量/#倫理勇氣/#倫理判斷`。

優化說明

1. 多媒體取捨完成第 3 輪溝通思考 10/10 收尾。
2. 溝通層已收斂成讀者入口、維護導覽、短版回報、句型與媒介限制。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少多媒體邊界與收尾會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪溝通思考收尾

- 已完成：10/10。
- 收尾結論：第 3 輪溝通思考已把契約矩陣整理成讀者語意入口、維護導覽、核心論點、一頁摘要、建議句型、文字表格媒介與多媒體限制。
- 邊界：不得宣稱 HCS Plus 完成、不得宣稱 runtime 安全、不得宣稱使用者理解改善、不得用多媒體替代 pytest 或人工 review。
- 下一步：第 3 輪 / 互動思考 / #倫理考量。

## 第 3 輪互動思考第一批

### 第 3 輪 / 互動思考 / #倫理考量

狀態：完成

本次使用：檢查短版回報是否可能被誤用成安全背書、責任轉嫁或高風險契約降級。

核心判斷

1. 第 3 輪溝通思考已把回報壓短，但越短的回報越容易被誤讀為安全保證。
2. 倫理底線需要明確禁止三件事：不得把短版回報寫成安全背書、不得把責任轉嫁給文件、工具或測試、不得用快速通道淡化高風險契約。
3. 倫理考量的作用是阻止錯誤宣稱，不是擴張流程或新增 runtime 行為。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪倫理阻擋與責任判斷`。
2. 該章節新增 `倫理考量` 與 `短版回報倫理底線`，寫入三條不得誤用規則。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣倫理阻擋與責任判斷`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #倫理考量。

優化說明

1. 這讓短版回報從溝通工具變成有倫理邊界的維護契約。
2. 代價是回報時必須明確說出不能推論的範圍；收益是避免測試綠燈、文件完整或快速通道被誇大。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪倫理阻擋會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 互動思考 / #倫理勇氣

狀態：完成

本次使用：把必要時要說不寫成停止條件，避免高風險契約被短版回報包裝成可合併。

核心判斷

1. 倫理勇氣不是語氣強硬，而是在證據不足時停止合併、要求補證據或回到人工複檢。
2. 缺少 parser/prompt/template 證據時停止合併；報告文案像交易指令時先補責任邊界；高風險契約被降級時回到人工複檢。
3. 這些停止條件保護使用者與維護者，不是把所有低風險改動都升級成重流程。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪倫理章節新增 `倫理勇氣` 與 `必要時要說不`。
2. 必要時要說不寫入缺少 parser/prompt/template 證據時停止合併、報告文案像交易指令時先補責任邊界、高風險契約被降級時回到人工複檢。
3. `docs/hcs-plus-optimization-state.md` 將倫理勇氣對應到同章節，並把停止條件寫入系統應用方式。

優化說明

1. 說不規則把紅色訊號從提醒升級為實際阻擋。
2. 它避免短版回報被用來繞過高風險契約檢查。
3. 下一批需檢查這些停止條件在複雜因果裡是否仍可能被稀釋。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_ethics_stop_and_responsibility_judgment`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_ethics_courage_judgment_is_recorded`

### 第 3 輪 / 互動思考 / #倫理判斷

狀態：完成

本次使用：把允許回報、禁止回報與升級判斷分開，讓 reviewer 能判斷一句回報是否越界。

核心判斷

1. 道德判斷需要可操作的表格，而不是只說「保持謹慎」。
2. 允許回報是通道、命令、未跑命令與限制句；禁止回報是宣稱系統安全、使用者已理解或文件可以替代測試。
3. 升級判斷必須涵蓋低風險使用者行動暗示、混合層核心契約詞、文件或觀察宣稱 runtime 行為。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪倫理章節新增 `倫理判斷` 表格與 `升級判斷`。
2. 倫理判斷分成允許回報、禁止回報與三條升級規則。
3. `docs/hcs-plus-optimization-state.md` 將 `#倫理考量/#倫理勇氣/#倫理判斷` 標記完成，並把下一批推進到 `#複雜因果/#湧現特性/#分析層次`。

優化說明

1. 倫理判斷讓短版回報有可 review 的界線。
2. 它把「不能誇大」轉成具體禁止回報與升級判斷。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少允許/禁止/升級判斷會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第二批

### 第 3 輪 / 互動思考 / #複雜因果

狀態：完成

本次使用：檢查局部綠燈如何造成系統性誤讀，避免把文件、前端測試或倫理阻擋規則外推成全系統安全。

核心判斷

1. 文件契約通過可能造成流程已安全的錯誤推論，但它只證明章節與狀態紀錄存在。
2. 前端測試通過可能造成 parser/prompt 已安全的錯誤推論，但它只保護前端顯示層。
3. 倫理阻擋存在可能造成高風險已被完全阻擋的錯誤推論，但規則仍需要 reviewer 啟用與補證據行動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪系統因果與證據層次`。
2. 該章節新增 `複雜因果` 與 `局部綠燈因果圖`，列出三種局部訊號、錯誤推論與必要修正。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣系統因果與證據層次`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #複雜因果。

優化說明

1. 複雜因果把第 3 輪倫理阻擋規則放回實際系統推論裡檢查。
2. 代價是回報時要更清楚區分證據來源；收益是降低單一綠燈被誇大成全局安全的機率。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪系統因果與證據層次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 互動思考 / #湧現特性

狀態：完成

本次使用：找出單次看似低風險的維護行為如何累積成新的系統風險。

核心判斷

1. 低風險快速通道累積成高風險語氣漂移：單次文案安全，不代表整體責任感不會變。
2. 案例卡增加但實際驗證減少：文件越完整，越可能讓操作者誤以為不必重跑測試。
3. 阻擋規則存在但 reviewer 不敢啟用：規則完整不代表壓力下真的會被使用。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪系統因果章節新增 `湧現特性`。
2. 湧現特性寫入快速通道累積、案例卡增加但驗證減少、阻擋規則不敢啟用三種風險。
3. `docs/hcs-plus-optimization-state.md` 把湧現特性對應到同章節，並記錄下一批需檢查放大或抑制回路。

優化說明

1. 湧現風險提醒我們不要只看單次 patch 的證據層。
2. 它避免把文件完整度誤當成實際驗證密度。
3. 下一批需把這些風險轉成維護網絡與系統動力學回路。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_system_causality_evidence_layers`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_causality_emergent_layers_is_recorded`

### 第 3 輪 / 互動思考 / #分析層次

狀態：完成

本次使用：把文件、測試、runtime 與使用者行為分層，要求每個宣稱都回到對應證據層。

核心判斷

1. 文件層只能證明章節、限制句、案例卡與狀態紀錄存在，不得用文件完整替代 runtime 驗證。
2. 測試層只能證明指定 pytest、lint 或靜態契約未被已知案例打破，不得用測試通過宣稱使用者理解。
3. runtime 層與使用者行為層需要自己的證據，不能被文件層或測試層反向替代。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪系統因果章節新增 `分析層次` 表格與層次規則。
2. 分析層次表區分文件層、測試層、runtime 層與使用者行為層。
3. `docs/hcs-plus-optimization-state.md` 將 `#複雜因果/#湧現特性/#分析層次` 標記完成，並把下一批推進到 `#網絡/#系統動力學/#系統圖像`。

優化說明

1. 分析層次讓完成回報先問「這句話屬於哪一層證據」。
2. 它把跨層宣稱改成明確升級驗證，而不是靠語氣克制。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少證據層次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第三批

### 第 3 輪 / 互動思考 / #網絡

狀態：完成

本次使用：把前一批的證據層次接成維護網絡，讓完成回報能看見文件、測試、runtime、使用者行為與 reviewer 阻擋節點彼此牽動。

核心判斷

1. 文件層節點能降低記憶負擔，但也可能讓文件完整被誤讀成流程安全。
2. 測試層節點能防回退，但若跨層宣稱未升級驗證，仍可能被誤讀成 runtime 或使用者行為安全。
3. reviewer 阻擋節點是維護網絡的關鍵煞車；若阻擋沒有被啟用，前面的倫理與證據規則會留在紙面上。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪維護網絡與動態圖像`。
2. 該章節新增 `維護網絡` 表格，連接文件層節點、測試層節點、runtime 層節點、使用者行為層節點與 reviewer 阻擋節點。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣維護網絡與動態圖像`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #網絡。

優化說明

1. 網絡視角讓「這句完成回報牽動哪個節點」變得可檢查。
2. 代價是回報需多做一層定位；收益是降低文件、測試與 runtime 證據彼此替代的風險。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_maintenance_network_dynamics_image`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_network_dynamics_image_is_recorded`

### 第 3 輪 / 互動思考 / #系統動力學

狀態：完成

本次使用：檢查維護網絡裡哪些行為會互相放大或抑制，避免只列節點而不看回路。

核心判斷

1. 快速通道摩擦降低回路有助於低風險 UI 收尾，但累積語氣漂移時必須回到混合層或高風險檢查。
2. 案例卡形式化回路讓改動更可追溯，但若實際驗證減少，就會把形式完整誤當成安全。
3. 阻擋勇氣回路與跨層宣稱升級回路決定 reviewer 能否把「需要補證據」說出口。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護網絡章節新增 `系統動力學`。
2. 動態回路記錄快速通道摩擦降低回路、案例卡形式化回路、阻擋勇氣回路與跨層宣稱升級回路。
3. `docs/hcs-plus-optimization-state.md` 將這四個回路寫入系統應用方式與下一批缺口。

優化說明

1. 系統動力學讓回報不只問「有沒有規則」，也問「這個規則會不會在壓力下失效」。
2. 它把下一批的談判、說服與形塑行為焦點收斂到降低說不成本。
3. 本批仍維持文件與測試契約優先，不把回路做成自動審核器。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_maintenance_network_dynamics_image`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_network_dynamics_image_is_recorded`

### 第 3 輪 / 互動思考 / #系統圖像

狀態：完成

本次使用：把網絡與回路轉成維護者可照著走的操作圖像，避免系統圖只停在概念。

核心判斷

1. 系統圖像必須從證據層開始，否則很容易直接跳到「看起來已完成」。
2. 圖像要先連到網絡節點，再判斷動態回路，才能看出是否需要升級驗證。
3. 最後的決策不是「通過或不通過」，而是維持同層宣稱，或補 pytest、人工驗收、使用者行為證據後再跨層宣稱。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護網絡章節新增 `系統圖像` 四步路徑。
2. 四步路徑固定為先定位證據層、再連到網絡節點、接著判斷動態回路、最後決定維持同層宣稱或升級驗證。
3. `docs/hcs-plus-optimization-state.md` 將 `#網絡/#系統動力學/#系統圖像` 標記完成，並把下一批推進到 `#談判/#說服/#形塑行為`。

優化說明

1. 系統圖像讓修改如何應用到系統變成可重複流程：定位、連節點、看回路、決定是否升級。
2. 它明確限制不得把網絡圖像當成自動審核器，也不得替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少維護網絡、動態回路與系統圖像會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第四批

### 第 3 輪 / 互動思考 / #談判

狀態：完成

本次使用：把 reviewer 阻擋節點轉成補證據協商，讓 reviewer 能接受同層成果，但不被迫放寬跨層證據標準。

核心判斷

1. 談判不是降低標準，而是把「不能合併」拆成可接受的選項：補跑命令、補限制句、拆分 patch 或降級宣稱。
2. 同層宣稱可以保留，跨層宣稱必須補證據或撤回。
3. review 對話需要可直接複製的句型，否則阻擋勇氣回路仍會卡在抽象規則。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪 review 對話與預設行為`。
2. 該章節新增 `談判` 與 `補證據協商` 表格，列出三種情境、可說句型與不可說法。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣 review 對話與預設行為`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #談判。

優化說明

1. 補證據協商把「說不」轉成「怎樣可以同層合併或升級驗證」。
2. 代價是完成回報需更明確標示宣稱層級；收益是降低合併壓力下的標準滑坡。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_review_dialogue_default_behavior`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_review_dialogue_default_behavior_is_recorded`

### 第 3 輪 / 互動思考 / #說服

狀態：完成

本次使用：把補證據要求說成共同完成工作，而不是否定改動者，降低 reviewer 說不成本。

核心判斷

1. 說服不是美化風險；它應該讓風險更容易被接受與處理。
2. 先承認已完成的證據，可以降低防衛反應；再指出缺口，才能避免把提醒說成抽象否定。
3. 最小可接受補證據讓 reviewer 的要求可執行，限制句則防止綠燈被誇大。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話章節新增 `說服`。
2. 說服路徑固定為先承認已完成的證據、再指出缺口、接著提出最小可接受補證據、最後寫不得解讀為。
3. `docs/hcs-plus-optimization-state.md` 將說服路徑寫入系統應用方式。

優化說明

1. 說服路徑讓 reviewer 不必在「放行」與「否定」之間二選一。
2. 它降低說不成本，但仍保留不得外推到 runtime、parser/prompt、使用者理解或投資判斷安全的限制。
3. 下一批需檢查多數壓力與高壓語氣是否會讓說服路徑失效。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_review_dialogue_default_behavior`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_review_dialogue_default_behavior_is_recorded`

### 第 3 輪 / 互動思考 / #形塑行為

狀態：完成

本次使用：把 review 對話轉成預設行為，讓完成回報自然填上宣稱層級、證據與限制，而不是靠臨場記憶。

核心判斷

1. 若沒有預設欄位，維護者很容易只回報「測試通過」，漏掉不得解讀為的限制。
2. 黃色與紅色訊號需要預設處理路徑，否則會被當成主觀感覺。
3. 跨層宣稱預設升級，可以把補證據變成常規流程，而不是 reviewer 個人對抗。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話章節新增 `形塑行為` 與 `預設行為` 表格。
2. 完成回報預設三欄固定為本次宣稱層級、已補證據、仍不得解讀為。
3. `docs/hcs-plus-optimization-state.md` 將 `#談判/#說服/#形塑行為` 標記完成，並把下一批推進到 `#從眾/#差異/#情緒智商`。

優化說明

1. 形塑行為讓好的 review 對話變成可重複格式，而不是只依賴 reviewer 當下的勇氣。
2. 它明確限制不得把好聽句型當成證據，也不得替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少 review 對話、預設行為與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第五批

### 第 3 輪 / 互動思考 / #從眾

狀態：完成

本次使用：檢查 review 預設行為是否會被多數同意、前例綠燈、測試全綠或合併壓力推著走。

核心判斷

1. 多數同意不是證據；它最多表示團隊傾向，不能替代本次證據層。
2. 前例綠燈不是本次綠燈；每次改動仍要重新定位改動層級與網絡節點。
3. 測試全綠不是限制句；pytest 結果仍需說明不得解讀為什麼。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪防從眾、差異訊號與情緒調節`。
2. 該章節新增 `防從眾檢查` 表格，列出多數同意、前例綠燈、測試全綠與合併壓力的不可取代項與必要回應。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣防從眾、差異訊號與情緒調節`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #從眾。

優化說明

1. 防從眾讓上一批的 review 對話不被團隊壓力稀釋。
2. 代價是完成回報需明確反駁常見捷徑；收益是降低綠燈與多數同意被誇大的風險。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_conformity_difference_emotion_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_conformity_difference_emotion_is_recorded`

### 第 3 輪 / 互動思考 / #差異

狀態：完成

本次使用：保留不同改動、證據、pipeline 模式與風險顏色之間的差異，避免為了快合併而壓平風險。

核心判斷

1. 高顯著性、混合層與低顯著性改動不能被寫成同一種安全程度。
2. 文件層、測試層、runtime 層與使用者行為層必須分開回報。
3. 黃色與紅色訊號若被寫成綠色，review 預設行為就會失去阻擋效果。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪防從眾章節新增 `差異訊號`。
2. 差異訊號列出改動層級差異、證據層差異、pipeline 模式差異與風險顏色差異。
3. `docs/hcs-plus-optimization-state.md` 將差異訊號寫入系統應用方式。

優化說明

1. 差異訊號讓完成回報保留重要不一致，而不是追求表面一致。
2. 它防止黃色與紅色訊號被語氣包裝成綠色。
3. 下一批需檢查誰有權力與責任維持這些差異。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_conformity_difference_emotion_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_conformity_difference_emotion_is_recorded`

### 第 3 輪 / 互動思考 / #情緒智商

狀態：完成

本次使用：處理高壓 review 語氣，避免時程、回歸失敗、疲勞或權威催促讓限制句與補證據被省略。

核心判斷

1. 高壓情境下，人容易把「先過」當成解法；因此要先命名壓力來源。
2. 命名壓力後仍要回到預設三欄，而不是只做情緒安撫。
3. 最小補證據路徑能降低緊張感，但不能降低證據要求。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪防從眾章節新增 `高壓語氣處理`。
2. 高壓語氣處理固定為先命名壓力來源、再回到預設三欄、接著保留最小補證據路徑、最後用冷靜限制句收尾。
3. `docs/hcs-plus-optimization-state.md` 將 `#從眾/#差異/#情緒智商` 標記完成，並把下一批推進到 `#領導原則/#權力動態/#責任`。

優化說明

1. 情緒智商讓 review 在壓力下仍能維持證據層與限制句。
2. 它明確限制不得用趕時間取代證據層，也不得用情緒安撫取代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少防從眾、差異訊號、情緒調節與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第六批

### 第 3 輪 / 互動思考 / #領導原則

狀態：完成

本次使用：把防從眾與高壓語氣護欄轉成證據領導，避免 review 只由速度、資深度或合併窗口帶節奏。

核心判斷

1. 領導原則應該先保護證據層，而不是先保護合併速度。
2. 主責若不先宣告本次宣稱層級，review 會把分類責任推到最晚發現問題的人。
3. review 主導者需要保留升級權，合併者需要確認紅色與黃色訊號已處理。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪角色責任與權力護欄`。
2. 該章節新增 `證據領導`，要求主責先宣告本次宣稱層級、review 主導者維持升級權、合併者確認紅色與黃色訊號已處理。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣角色責任與權力護欄`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #領導原則。

優化說明

1. 證據領導讓 review 領導權服務宣稱層級與補證據，而不是服務快合併。
2. 代價是完成回報要多說明角色責任；收益是錯放責任時能追溯到具體角色。
3. 本批仍維持文件與測試契約，不新增 runtime、遙測、圖像流程或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_role_responsibility_power_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_role_responsibility_power_is_recorded`

### 第 3 輪 / 互動思考 / #權力動態

狀態：完成

本次使用：檢查合併權限、資深度與權威催促如何影響證據層，並把權力壓力轉成可引用的護欄。

核心判斷

1. 合併權限不能覆蓋紅色訊號；紅色訊號仍要停止合併、補證據或拆分 patch。
2. 資深度不能把前例綠燈變成本次通行證。
3. 低權限操作者需要能引用契約要求補證據，否則防從眾規則會被權力差距稀釋。

落地修改

1. `docs/pipeline-mode-contract.md` 的角色責任章節新增 `權力動態`。
2. 權力動態寫入合併權限不能覆蓋紅色訊號、資深度不能把前例綠燈變成通行證。
3. 權力動態允許低權限操作者引用契約要求補證據，並要求權威催促回到預設三欄。

優化說明

1. 權力護欄讓證據層有明確優先級，避免權限、資深度或催促取代補證據。
2. 這不新增正式權限模型；它只定義 review 對話中的最低證據邊界。
3. 下一批需檢查這套權力護欄是否過度官僚。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_role_responsibility_power_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_role_responsibility_power_is_recorded`

### 第 3 輪 / 互動思考 / #責任

狀態：完成

本次使用：把改動者、reviewer 與合併者的完成責任拆開，避免責任被轉嫁給文件、工具或測試。

核心判斷

1. 改動者負責本次宣稱層級與已補證據。
2. reviewer 負責仍不得解讀為，並核對黃色、紅色與跨層宣稱。
3. 合併者負責未跑命令與剩餘風險，不能把風險留給文件或工具代背。

落地修改

1. `docs/pipeline-mode-contract.md` 的角色責任章節新增 `責任` 表格。
2. 責任表格拆分改動者、reviewer 與合併者的責任與完成回報必留內容。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#領導原則/#權力動態/#責任` 標記完成，並把下一批推進到 `#自我覺察/#制定策略`。

優化說明

1. 角色責任讓問題可追溯到具體環節，而不是籠統說文件沒有寫清楚。
2. 它明確限制不得把責任轉嫁給文件、工具或測試，也不得替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續需用自我覺察與制定策略檢查是否過度官僚，並收尾第 3 輪互動思考。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少角色責任、權力護欄與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第七批

### 第 3 輪 / 互動思考 / #自我覺察

狀態：完成

本次使用：檢查角色責任與權力護欄是否會反過來增加官僚成本，並限制契約矩陣自身的副作用。

核心判斷

1. 角色責任不是流程越多越好；它應該只在風險、跨層宣稱與證據不足時增加摩擦。
2. 低風險同層改動若也被拖進完整責任審核，會讓契約矩陣變成形式簽核。
3. 文件完整不等於自動審核；完整矩陣仍不能替代 pytest 或人工 review。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪自我稽核與收尾策略`。
2. 該章節新增 `輕量使用邊界`，把低風險同層改動、黃色訊號與紅色訊號分成不同摩擦等級。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣自我稽核與收尾策略`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #自我覺察。

優化說明

1. 自我稽核讓角色責任保持輕量，不把低風險同層改動拖成重流程。
2. 代價是仍需人工判斷風險顏色；收益是避免契約矩陣變成假自動化或形式簽核。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_self_audit_and_closing_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_self_audit_strategy_is_recorded`

### 第 3 輪 / 互動思考 / #制定策略

狀態：完成

本次使用：定義第 3 輪互動思考的收尾條件，並把下一步從單項輪巡推進到三習慣綜合優化。

核心判斷

1. 第 3 輪互動思考已補齊倫理、系統因果、維護網絡、review 對話、防從眾、角色責任與自我稽核。
2. 最合理的下一步不是繼續堆疊互動規則，而是用高影響三習慣整合整個專案契約。
3. 綜合優化候選先採用 #可驗證性、#溝通設計、#系統圖像，因為它們分別對應證據、使用者理解與系統關係。

落地修改

1. `docs/pipeline-mode-contract.md` 的自我稽核章節新增 `第 3 輪互動思考收尾條件`。
2. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#自我覺察/#制定策略` 標記完成，並新增 `綜合 / 三習慣綜合優化 / #可驗證性、#溝通設計、#系統圖像` 下一批。
3. 本嚴格輪巡附件新增第 3 輪互動思考收尾 checkpoint，明確保留 HCS Plus 尚未完成。

優化說明

1. 制定策略讓第 3 輪互動思考以 20/20 單項完成收尾。
2. 它把下一步轉為整體收斂，而不是繼續擴張局部規則。
3. 不得宣稱 HCS Plus 完成；完整流程仍需後續綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少自我稽核、收尾策略與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考收尾

已完成：20/20

已改善內容：

1. 把短版回報倫理、系統因果、維護網絡、review 對話、防從眾、角色責任與自我稽核串成可追溯的契約矩陣。
2. 把證據層、角色責任、限制句、風險顏色與完成回報三欄寫成可測試文件契約。
3. 把互動思考最後缺口收斂到三習慣綜合優化。

剩餘風險：

1. 契約矩陣仍是文件與測試契約，不是自動審核器。
2. 未新增 runtime、遙測或自動選測工具；高風險改動仍需人工 review 與對應 pytest。
3. HCS Plus 尚未完成，仍需三習慣綜合優化。

下一步：三習慣綜合優化 / #可驗證性

## 三習慣綜合優化第 1 次

### 綜合 / 三習慣綜合優化第 1 次 / #可驗證性

狀態：完成

本次使用：把三輪累積的契約矩陣收斂成驗證閘門，避免完成宣稱只靠文件存在或測試綠燈外推。

核心判斷

1. 完成宣稱必須回到同層證據；文件契約只支持文件層宣稱。
2. 高顯著性機器契約改動仍要跑 parser、prompt、template 與 audit 回歸。
3. 不跑命令不能宣稱通過；只能明列未跑命令與剩餘風險。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 1 次：驗證、溝通與系統圖像收斂`。
2. 該章節新增 `驗證閘門`，分出低風險同層改動、報告呈現層、高顯著性機器契約與維運決策層。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 1 次：驗證、溝通與系統圖像收斂`。
4. 歷史 checkpoint：下一步：三習慣綜合優化 / #可驗證性。

優化說明

1. 可驗證性把「已完成」收斂成命令、證據層與限制句。
2. 代價是完成回報需要更明確列出未跑命令；收益是避免跨層安全宣稱。
3. 本批不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_verification_communication_system_view`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_verification_communication_system_view_is_recorded`

### 綜合 / 三習慣綜合優化第 1 次 / #溝通設計

狀態：完成

本次使用：把完成回報設計成維護者能快速判斷證據範圍、限制與下一步的格式。

核心判斷

1. 完成回報若先講結果，容易讓讀者忽略證據層。
2. 最小可用格式應先說本次宣稱層級，再列已補證據與仍不得解讀為。
3. 下一個可執行行動能避免綜合優化停在抽象原則。

落地修改

1. `docs/pipeline-mode-contract.md` 的綜合優化章節新增 `完成回報格式`。
2. 格式固定為本次宣稱層級、已補證據、仍不得解讀為、下一個可執行行動。
3. `docs/hcs-plus-optimization-state.md` 將溝通設計對應到同章節的完成回報格式。

優化說明

1. 溝通設計讓回報先限制宣稱範圍，再呈現成果。
2. 它保留低風險同層改動的輕量三欄，不把所有改動拖進完整矩陣。
3. 下一批需用受眾視角再檢查不同維護者是否能快速找到自己該讀的段落。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_verification_communication_system_view`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_verification_communication_system_view_is_recorded`

### 綜合 / 三習慣綜合優化第 1 次 / #系統圖像

狀態：完成

本次使用：把前端、報告、機器契約與維運決策分成不同系統層，避免局部證據被外推成全系統安全。

核心判斷

1. 前端顯示層、報告呈現層、機器契約層與維運決策層需要不同證據入口。
2. 同層證據只能支持同層宣稱；跨層宣稱必須升級驗證。
3. 系統圖像應幫助維護者選證據，不應變成另一張形式圖表。

落地修改

1. `docs/pipeline-mode-contract.md` 的綜合優化章節新增 `系統圖像收斂`。
2. 系統圖像收斂列出四層：前端顯示層、報告呈現層、機器契約層、維運決策層。
3. `docs/hcs-plus-optimization-state.md` 將第一個綜合批次標記完成，並把下一批推進到 `#證據基礎/#受眾/#責任`。

優化說明

1. 系統圖像收斂讓證據入口與改動層一致。
2. 它保留人工 review 與 pytest 的位置，不把文件圖像當成自動審核。
3. 不得把綜合優化第 1 次解讀為 HCS Plus 完成；完成定義仍要求後續綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 1 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 2 次

### 綜合 / 三習慣綜合優化第 2 次 / #證據基礎

狀態：完成

本次使用：把第一批的驗證閘門往前補證據來源分級，避免文件、測試、人工 review 與未跑命令被混成同一種綠燈。

核心判斷

1. 直接證據只能支持它實際覆蓋的同層行為。
2. 間接證據只能支持流程或文件存在，不能外推到 runtime 或使用者理解。
3. 缺口證據與未跑命令如果不被明列，就會被完成敘述吞掉。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 2 次：證據來源、讀者角色與責任承接`。
2. 該章節新增 `證據來源分級`，區分直接證據、間接證據、缺口證據與未跑命令。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 2 次：證據來源、讀者角色與責任承接`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 2 次 / #證據基礎。

優化說明

1. 證據基礎讓第一批的驗證閘門不只列命令，也說清楚證據等級。
2. 代價是完成回報需明列缺口；收益是未跑命令不能消失。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_evidence_audience_responsibility`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_evidence_audience_responsibility_is_recorded`

### 綜合 / 三習慣綜合優化第 2 次 / #受眾

狀態：完成

本次使用：把第 1 批的完成回報格式轉成讀者入口，避免低風險 UI 維護者被迫讀完整機器契約，也避免高風險維護者只看短版結論。

核心判斷

1. 低風險 UI 維護者需要輕量三欄與前端顯示層證據。
2. 報告呈現維護者與機器契約維護者需要保留不同證據入口。
3. 合併者需要同時看到證據來源、讀者角色、未跑命令與剩餘風險。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 2 次綜合優化章節新增 `讀者角色分流`。
2. 分流列出低風險 UI 維護者、報告呈現維護者、機器契約維護者、維運決策維護者與合併者。
3. `docs/hcs-plus-optimization-state.md` 將受眾對應到同章節的讀者角色分流。

優化說明

1. 受眾分流降低閱讀成本，但不降低證據要求。
2. 不同讀者先讀不同入口，仍需保留不得外推到 runtime、安全或投資判斷的限制。
3. 下一批需用學習科學檢查入口是否真的容易學會。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_evidence_audience_responsibility`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_evidence_audience_responsibility_is_recorded`

### 綜合 / 三習慣綜合優化第 2 次 / #責任

狀態：完成

本次使用：把證據來源與讀者角色轉成責任承接，避免未跑命令、剩餘風險或讀者誤讀在交接時消失。

核心判斷

1. 改動者負責證據來源與宣稱層級。
2. reviewer 負責讀者是否會誤讀，尤其是低風險入口被外推到高風險層。
3. 合併者負責未跑命令與剩餘風險是否可接受。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 2 次綜合優化章節新增 `責任承接`。
2. 責任承接寫入改動者、reviewer、合併者三方責任。
3. `docs/hcs-plus-optimization-state.md` 將下一批推進到三習慣綜合優化第 3 次 / `#偏誤降低`、`#學習科學`、`#制定策略`。

優化說明

1. 責任承接讓未跑命令不能消失，剩餘風險必須留到下一步。
2. 不得把使用者理解、安全或投資判斷外推。
3. 不得把綜合優化第 2 次解讀為 HCS Plus 完成；下一批需要控制責任規則繼續膨脹的風險。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 2 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 3 次

### 綜合 / 三習慣綜合優化第 3 次 / #偏誤降低

狀態：完成

本次使用：把第 2 次的證據、讀者與責任矩陣加上誤用偵測，避免矩陣被拿來打勾、漂白證據、逃避升級或繼續膨脹。

核心判斷

1. 表格打勾偏誤會讓每欄都有文字，卻沒有任何同層證據支持宣稱。
2. 證據漂白偏誤會把文件契約、案例卡或觀察紀錄寫成直接證據。
3. 升級逃避與流程膨脹會同時出現：一邊不補高風險命令，一邊新增更多低價值欄位。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 3 次：偏誤防線、速學入口與策略收斂`。
2. 該章節新增 `偏誤防線`，列出表格打勾偏誤、證據漂白偏誤、升級逃避偏誤與流程膨脹偏誤。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 3 次：偏誤防線、速學入口與策略收斂`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 3 次 / #偏誤降低。

優化說明

1. 偏誤降低讓第 2 次矩陣不只要求證據，也能辨識矩陣本身被誤用。
2. 代價是 reviewer 多一個偏誤掃描步驟；收益是避免空表格被當成完成證據。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_bias_learning_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_bias_learning_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 3 次 / #學習科學

狀態：完成

本次使用：把完整契約矩陣轉成可快速啟動的速學入口，降低新維護者第一次使用時的記憶負擔。

核心判斷

1. 維護者一開始不需要背完整矩陣，只需要知道先定位改動層級。
2. 90 秒內應能分清證據來源與讀者角色，否則矩陣會變成阻力。
3. 5 分鐘復盤應產出限制句、未跑命令與下一個可執行行動，而不是新的抽象原則。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 次綜合優化章節新增 `速學入口`。
2. 速學入口分成 10 秒定位、90 秒分流、5 分鐘復盤。
3. `docs/hcs-plus-optimization-state.md` 將學習科學對應到同章節的速學入口。

優化說明

1. 學習科學把契約矩陣從完整規則書降成可先用的三段入口。
2. 速學入口不得替代完整契約；遇到高顯著性或跨層宣稱仍要回到完整矩陣。
3. 下一批需用效用檢查速學入口是否真的比完整矩陣更省成本。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_bias_learning_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_bias_learning_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 3 次 / #制定策略

狀態：完成

本次使用：把偏誤防線與速學入口收斂成策略規則，決定哪些情境保持輕量、哪些必須升級、哪些規則必須刪減。

核心判斷

1. 低風險維持輕量，才能避免契約矩陣拖慢同層小改。
2. 高顯著性必須升級，才能避免速學入口被拿來逃避 parser、prompt、template 或 audit 回歸。
3. 策略膨脹必須刪減，否則綜合優化會服務文件本身而不是服務專案。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 次綜合優化章節新增 `策略收斂`。
2. 策略收斂固定低風險維持輕量、高顯著性必須升級、未跑命令留到下一步、策略膨脹必須刪減。
3. `docs/hcs-plus-optimization-state.md` 將進度推進到三習慣綜合優化第 4 次 / `#目的`、`#效用`、`#合理性`。

優化說明

1. 制定策略讓第 3 次綜合優化以規則刪減與升級判斷收尾。
2. 不得把矩陣完成誤讀為證據充分，也不得把速學入口替代完整契約。
3. 不得把綜合優化第 3 次解讀為 HCS Plus 完成；下一批需要回到目的、效用與合理性。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 3 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 4 次

### 綜合 / 三習慣綜合優化第 4 次 / #目的

狀態：完成

本次使用：把前 3 次綜合優化重新綁回股票研究系統的核心目標，避免契約矩陣服務文件本身。

核心判斷

1. 契約矩陣的目的不是增加文件厚度，而是讓操作者選對分析模式並理解報告層級。
2. 使用者決策用途、維護者合併判斷與契約安全邊界需要同時保留。
3. 目的不明的規則會讓矩陣膨脹，並削弱低風險通道的效率。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 4 次：目標校準、效用門檻與合理性審核`。
2. 該章節新增 `目標校準`，把矩陣規則連回股票研究系統核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 4 次：目標校準、效用門檻與合理性審核`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 4 次 / #目的。

優化說明

1. 目的校準讓每條規則先說明服務哪個系統目標。
2. 代價是新增規則需要說清楚目的；收益是目的不明不能加入矩陣。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_goal_utility_reasonability`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_goal_utility_reasonability_is_recorded`

### 綜合 / 三習慣綜合優化第 4 次 / #效用

狀態：完成

本次使用：把矩陣規則的保留條件改成效用門檻，只有能降低錯選模式、漏跑命令、跨層外推或維護成本的規則才保留。

核心判斷

1. 規則若不能降低錯選模式，就只是重複模式名稱。
2. 規則若不能降低漏跑命令或跨層外推，就不能支撐完成宣稱。
3. 規則若不能降低維護成本，就必須有更強的風險降低證據。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 4 次綜合優化章節新增 `效用門檻`。
2. 效用門檻固定四項：降低錯選模式、降低漏跑命令、降低跨層外推、降低維護成本。
3. `docs/hcs-plus-optimization-state.md` 將效用對應到同章節的效用門檻。

優化說明

1. 效用門檻讓矩陣規則有保留理由，而不是只因為看起來完整就留下。
2. 不得把效用推論寫成已證明改善；目前只作為文件契約與 review 判斷。
3. 下一批需用決策樹把效用門檻轉成實際分流。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_goal_utility_reasonability`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_goal_utility_reasonability_is_recorded`

### 綜合 / 三習慣綜合優化第 4 次 / #合理性

狀態：完成

本次使用：把目的與效用轉成合理性審核，要求高成本規則通過必要性、比例性、可驗證性與可逆性。

核心判斷

1. 高成本規則必須有證據，不能只用「更安全」當理由。
2. 低風險同層改動需要比例性，不能被完整矩陣拖慢。
3. 可逆性讓流程膨脹能被刪減，而不是一路累積。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 4 次綜合優化章節新增 `合理性審核`。
2. 合理性審核固定必要性、比例性、可驗證性與可逆性。
3. `docs/hcs-plus-optimization-state.md` 將進度推進到三習慣綜合優化第 5 次 / `#限制條件`、`#決策樹`、`#最佳化`。

優化說明

1. 合理性讓低效用規則必須刪減，高成本規則必須有證據，目的不明不能加入矩陣。
2. 不得讓契約矩陣服務文件本身，也不得把效用推論寫成已證明改善。
3. 不得把綜合優化第 4 次解讀為 HCS Plus 完成；下一批需把限制、決策與最佳化落成分流。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 4 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 5 次

### 綜合 / 三習慣綜合優化第 5 次 / #限制條件

狀態：完成

本次使用：把目的、效用與合理性轉成限制邊界，清楚分出哪些情境不能做、哪些能輕量、哪些必須升級、哪些要停用。

核心判斷

1. 硬限制要阻止新增 runtime、遙測、自動選測工具，以及文件替代 pytest 或人工 review。
2. 軟限制保留低風險輕量通道，但仍要留宣稱層級、證據與限制句。
3. 升級限制與停用限制能避免高顯著性改動被降級，或低效用規則繼續膨脹。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 5 次：限制邊界、分流決策與成本最佳化`。
2. 該章節新增 `限制邊界`，列出硬限制、軟限制、升級限制與停用限制。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 5 次：限制邊界、分流決策與成本最佳化`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 5 次 / #限制條件。

優化說明

1. 限制條件把「不得」類規則變成可操作邊界，而不是散落在各章的提醒。
2. 代價是規則前置判斷變多；收益是硬限制不再被輕量通道稀釋。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_constraints_decision_optimization`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_constraints_decision_optimization_is_recorded`

### 綜合 / 三習慣綜合優化第 5 次 / #決策樹

狀態：完成

本次使用：把限制邊界排成四步分流決策，讓 reviewer 不需要靠記憶整份矩陣來決定下一步。

核心判斷

1. 分流必須先判斷改動層級，否則低風險與高顯著性改動會混在一起。
2. 顯著性與證據缺口決定是否升級、拆分或刪減。
3. 決策樹只能輔助人工判斷，不是自動選測工具。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 5 次綜合優化章節新增 `分流決策`。
2. 分流決策固定四步：判斷改動層級、判斷顯著性、判斷證據缺口、選擇輕量/升級/拆分/刪減。
3. `docs/hcs-plus-optimization-state.md` 將決策樹對應到同章節的分流決策。

優化說明

1. 決策樹把目的、效用與合理性落成順序，降低 reviewer 的臨場判斷負擔。
2. 不得把決策樹當成自動選測工具；命令與人工 review 仍由改動層級與證據缺口決定。
3. 下一批需用情境脈絡檢查同一決策在不同維護情境下是否仍適用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_constraints_decision_optimization`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_constraints_decision_optimization_is_recorded`

### 綜合 / 三習慣綜合優化第 5 次 / #最佳化

狀態：完成

本次使用：把矩陣成本最佳化明文化，保留能降低風險的規則，刪除或延後低效用、重複或無證據規則。

核心判斷

1. 最佳化不是降低標準，而是刪掉不降低風險的成本。
2. 保留低風險輕量通道與高顯著性升級，是同一套成本最佳化的一體兩面。
3. 無證據規則應延後，不應寫成已完成或已證明有效。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 5 次綜合優化章節新增 `成本最佳化`。
2. 成本最佳化固定四種動作：保留低風險輕量通道、合併重複規則、刪除低效用規則、延後無證據規則。
3. `docs/hcs-plus-optimization-state.md` 將進度推進到三習慣綜合優化第 6 次 / `#來源品質`、`#情境脈絡`、`#批判`。

優化說明

1. 最佳化讓矩陣能縮短而不是一路增厚。
2. 不得為了最佳化而降低高顯著性驗證，也不得把決策樹當成自動選測工具。
3. 不得把綜合優化第 5 次解讀為 HCS Plus 完成；下一批需檢查來源品質、情境脈絡與批判反證。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 5 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 6 次

### 綜合 / 三習慣綜合優化第 6 次 / #來源品質

狀態：完成

本次使用：把矩陣可引用的來源分級，避免歷史紀錄、文件契約或模型自信語氣被誤寫成完成證據。

核心判斷

1. 高可信來源只能支持它實際覆蓋的同層行為。
2. 可用但有限來源可以支持流程存在，不能替代 pytest 或人工 review。
3. 不得作為完成證據與缺口來源必須限制宣稱，而不是被改寫成綠燈。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 6 次：來源分級、適用情境與批判反證`。
2. 該章節新增 `來源分級`，分出高可信來源、可用但有限來源、不得作為完成證據與缺口來源。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 6 次：來源分級、適用情境與批判反證`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 6 次 / #來源品質。

優化說明

1. 來源品質讓第 5 次分流決策有證據等級依據。
2. 代價是完成回報需更精確標明來源；收益是歷史紀錄不能被當成新證據。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_source_context_critique`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_source_context_critique_is_recorded`

### 綜合 / 三習慣綜合優化第 6 次 / #情境脈絡

狀態：完成

本次使用：把同一條矩陣規則放回具體維護情境，避免低風險文件規則被外推成 runtime、parser 或使用者理解保證。

核心判斷

1. 低風險同層文件改動可以走輕量入口，但不能支持 runtime 或使用者理解。
2. 報告呈現或使用者語意改動要檢查交易指令、安全背書與投資判斷保證。
3. 機器契約、高顯著性與維運決策情境必須有對應回歸、review 或排程風險紀錄。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 6 次綜合優化章節新增 `適用情境`。
2. 適用情境分成低風險同層文件改動、報告呈現或使用者語意改動、機器契約或高顯著性改動、維運決策或排程風險改動。
3. `docs/hcs-plus-optimization-state.md` 的第 6 次狀態章節新增系統應用方式，要求先標明來源品質，再確認適用情境。

優化說明

1. 情境脈絡把第 5 次的分流決策從抽象層級拉回實際維護入口。
2. 情境不符必須升級或拆分，不能把文件同層規則擴張到高顯著性改動。
3. 下一批需用信賴區間描述不同情境下的信心邊界。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_source_context_critique`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_source_context_critique_is_recorded`

### 綜合 / 三習慣綜合優化第 6 次 / #批判

狀態：完成

本次使用：每次新增、保留或合併規則前，先用反證問題檢查它在哪裡可能失效、證據是否只支持文件存在，以及是否有更小的限制句。

核心判斷

1. 失效情境若碰到高顯著性或跨層宣稱，必須改走升級或拆分。
2. 證據若只支持文件存在，來源品質不足必須降級宣稱。
3. 若有更小限制句或刪減方式，優先縮小規則而不是擴張矩陣。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 6 次綜合優化章節新增 `批判反證`。
2. 批判反證固定三個反問，並明訂情境不符、來源品質不足與反證未處理時的處理方式。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 6 次標為完成，並把下一批推進到 `#估算`、`#信賴區間`、`#詮釋框架`。

優化說明

1. 批判反證防止契約矩陣只因形式完整就繼續膨脹。
2. 反證未處理不得合併高顯著性規則，也不得把歷史紀錄當成新證據。
3. 不得把綜合優化第 6 次解讀為 HCS Plus 完成；下一批需校準把握程度與解讀框架。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 6 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 7 次

### 綜合 / 三習慣綜合優化第 7 次 / #估算

狀態：完成

本次使用：把完成宣稱先估成高把握、中把握、低把握或不得宣稱，避免有限證據被寫成確定結論。

核心判斷

1. 高把握只能來自覆蓋同層行為的高可信來源。
2. 中把握必須列出缺口與未跑命令，不能寫成完全完成。
3. 低把握不得升格為完成，不得宣稱等級只能改成限制句或下一步。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 7 次：把握校準、信心邊界與解讀框架`。
2. 該章節新增 `把握估算`，分出高把握、中把握、低把握與不得宣稱。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 7 次：把握校準、信心邊界與解讀框架`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 7 次 / #估算。

優化說明

1. 估算把第 6 次的來源品質轉成回報語氣，降低過度宣稱。
2. 代價是完成回報多一步把握標記；收益是弱證據不能被包裝成完成。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_estimation_confidence_interpretation`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_estimation_confidence_interpretation_is_recorded`

### 綜合 / 三習慣綜合優化第 7 次 / #信賴區間

狀態：完成

本次使用：把每個完成宣稱的信心邊界寫清楚，避免文件層、測試層、runtime 層與使用者行為層互相外推。

核心判斷

1. 適用層級必須標示是文件層、測試層、runtime 層、使用者行為層或維運決策層。
2. 證據覆蓋必須標示已跑命令、已檢 diff、已 review、已渲染、已抽樣或仍未驗證。
3. 剩餘不確定必須明列，信心邊界不得跨過未測層。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 7 次綜合優化章節新增 `信心邊界`。
2. 信心邊界要求同時列出適用層級、證據覆蓋與剩餘不確定。
3. `docs/hcs-plus-optimization-state.md` 的第 7 次狀態章節新增系統應用方式，要求完成宣稱先填把握估算，再填信心邊界。

優化說明

1. 信賴區間讓完成宣稱不再只有單點結論，而有可檢查的邊界。
2. 這會限制文件層結果被推成 runtime 或使用者理解證明。
3. 下一批需用描述統計整理完成與缺口分布。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_estimation_confidence_interpretation`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_estimation_confidence_interpretation_is_recorded`

### 綜合 / 三習慣綜合優化第 7 次 / #詮釋框架

狀態：完成

本次使用：把宣稱結果解讀成已驗證、有限支持、暫定假設或未證明，避免讀者把同一段證據自行放大成更高層級結論。

核心判斷

1. 已驗證只代表同層證據已覆蓋該宣稱。
2. 有限支持與暫定假設不能替代 pytest、人工 review 或 runtime 驗證。
3. 未證明不能被包裝成低風險，也不能待補後自動通過。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 7 次綜合優化章節新增 `解讀框架`。
2. 解讀框架分成已驗證、有限支持、暫定假設與未證明。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 7 次標為完成，並把下一批推進到 `#相關性`、`#描述統計`、`#顯著性`。

優化說明

1. 詮釋框架把估算與信心邊界轉成讀者能理解的結果標籤。
2. 解讀框架不得替代 pytest、人工 review 或 runtime 驗證。
3. 不得把綜合優化第 7 次解讀為 HCS Plus 完成；下一批需檢查關聯、摘要分布與顯著性門檻。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 7 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 8 次

### 綜合 / 三習慣綜合優化第 8 次 / #相關性

狀態：完成

本次使用：檢查矩陣規則之間是否真的互相支撐，避免只因文字相近就合併或升級。

核心判斷

1. 強支撐必須同時有共同目標、來源層級、適用情境、把握等級與信心邊界。
2. 弱支撐只能保留為有限支持，不能合併成高顯著性規則。
3. 衝突支撐與無關規則必須拆分、降級或刪減。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻`。
2. 該章節新增 `關聯檢核`，分出強支撐、弱支撐、衝突支撐與無關。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 8 次 / #相關性。

優化說明

1. 相關性讓第 7 次的把握與信心邊界不只停在單條宣稱，而能檢查規則之間是否真的互相支持。
2. 代價是合併規則前多一層關聯判斷；收益是文字相似不再等於可合併。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_correlation_summary_significance`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_correlation_summary_significance_is_recorded`

### 綜合 / 三習慣綜合優化第 8 次 / #描述統計

狀態：完成

本次使用：把目前文件與測試覆蓋整理成分布摘要，避免把零散觀察寫成改善證明。

核心判斷

1. 完成分布用來檢查完成是否過度集中在文件層或低風險通道。
2. 缺口分布與驗證分布用來找下一批該補哪一種證據。
3. 風險分布只能標出風險出現的位置，不能宣稱風險已被消除。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 8 次綜合優化章節新增 `分布摘要`。
2. 分布摘要分成完成分布、缺口分布、驗證分布與風險分布。
3. `docs/hcs-plus-optimization-state.md` 的第 8 次狀態章節新增系統應用方式，要求新增或合併規則前先做關聯檢核，再做分布摘要。

優化說明

1. 描述統計讓矩陣維護者看見完成與缺口集中在哪裡。
2. 分布摘要只能描述目前文件與測試覆蓋，不得解讀為改善證明。
3. 下一批需用迴歸檢查局部改善是否可能回到舊問題。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_correlation_summary_significance`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_correlation_summary_significance_is_recorded`

### 綜合 / 三習慣綜合優化第 8 次 / #顯著性

狀態：完成

本次使用：設定哪些訊號值得升級成規則，哪些只能保留、降級或刪減。

核心判斷

1. 升級訊號必須跨多個章節、來源層級與測試缺口重複出現，且影響高顯著性改動。
2. 保留訊號可以降低風險但證據仍有限，因此不能擴張宣稱。
3. 降級訊號與刪減訊號防止弱支撐、無關或高成本低效用規則繼續膨脹。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 8 次綜合優化章節新增 `顯著性門檻`。
2. 顯著性門檻分成升級訊號、保留訊號、降級訊號與刪減訊號。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 8 次標為完成，並把下一批推進到 `#機率`、`#迴歸`、`#謬誤`。

優化說明

1. 顯著性門檻讓矩陣只升級反覆出現且影響高顯著性改動的訊號。
2. 顯著性門檻不得替代 pytest、人工 review 或 runtime 驗證。
3. 不得把綜合優化第 8 次解讀為 HCS Plus 完成；下一批需檢查概率語言、回歸風險與推論謬誤。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 8 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 9 次

### 綜合 / 三習慣綜合優化第 9 次 / #機率

狀態：完成

本次使用：把概率語言分成高可能、中可能、低可能與未知或不得推定，避免「可能」被寫成保證或精確承諾。

核心判斷

1. 高可能需要多個高可信來源在同層證據、關聯檢核與顯著性門檻上互相支持。
2. 中可能與低可能必須保留剩餘不確定，不能寫成完成。
3. 未知或不得推定不得使用精確百分比，也不得宣稱改善、安全、通過或使用者已理解。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線`。
2. 該章節新增 `概率語言`，分出高可能、中可能、低可能與未知或不得推定。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 9 次 / #機率。

優化說明

1. 機率讓第 8 次的顯著性門檻不會被回報語氣放大。
2. 代價是回報需避免精確百分比；收益是弱證據不能被包裝成高概率保證。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_probability_regression_fallacy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_probability_regression_fallacy_is_recorded`

### 綜合 / 三習慣綜合優化第 9 次 / #迴歸

狀態：完成

本次使用：檢查新規則是否回到過度宣稱、跨層外推、流程膨脹或弱證據升級等舊問題。

核心判斷

1. 回到過度宣稱時，必須降級宣稱並補限制句與未跑命令。
2. 回到跨層外推時，必須拆回同層宣稱，必要時升級驗證。
3. 回到流程膨脹或弱證據升級時，必須刪減、延後或回到關聯檢核與顯著性門檻。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 9 次綜合優化章節新增 `迴歸風險`。
2. 迴歸風險列出回到過度宣稱、回到跨層外推、回到流程膨脹與回到弱證據升級。
3. `docs/hcs-plus-optimization-state.md` 的第 9 次狀態章節新增系統應用方式，要求回報概率後檢查迴歸風險。

優化說明

1. 迴歸檢查讓矩陣不只新增規則，也檢查是否回到舊錯誤。
2. 迴歸風險不得寫成已修復，只能列出回歸訊號與必須動作。
3. 下一批需用可驗證性固定最終完成證據與測試門檻。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_probability_regression_fallacy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_probability_regression_fallacy_is_recorded`

### 綜合 / 三習慣綜合優化第 9 次 / #謬誤

狀態：完成

本次使用：建立謬誤防線，阻止相關當因果、測試當 runtime 安全、文件完整當使用者理解、歷史紀錄當新證據。

核心判斷

1. 相關不等於因果；規則同時出現只能寫關聯，不能宣稱造成改善。
2. 通過測試不等於 runtime 安全，文件完整不等於使用者理解。
3. 歷史紀錄不等於新證據，只能當脈絡，不能替代新驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 9 次綜合優化章節新增 `謬誤防線`。
2. 謬誤防線列出相關不等於因果、通過測試不等於 runtime 安全、文件完整不等於使用者理解、歷史紀錄不等於新證據。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 9 次標為完成，並把下一批推進到 `#合理性`、`#可驗證性`、`#制定策略`。

優化說明

1. 謬誤防線讓第 9 次的概率與迴歸規則不被誤讀成完成證據。
2. 謬誤清單不得替代 pytest、人工 review 或 runtime 驗證。
3. 不得把綜合優化第 9 次解讀為 HCS Plus 完成；下一批需收尾完成定義、驗收標準與下一步策略。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 9 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 10 次

### 綜合 / 三習慣綜合優化第 10 次 / #合理性

狀態：完成

本次使用：確認十次綜合優化仍服務股票研究系統的核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。

核心判斷

1. 十次綜合優化只完成文件與測試契約收斂。
2. 完成不代表 runtime 安全、投資結果改善或使用者理解已驗證。
3. 合理性收尾必須把核心目標、使用者決策用途、維護者合併判斷與契約安全邊界同時列出。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略`。
2. 該章節新增 `合理性收尾` 與 `完成定義`。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 10 次 / #合理性。

優化說明

1. 合理性把十次綜合優化從不斷加規則收回完成定義。
2. 代價是完成宣稱受限；收益是完成只代表 HCS Plus 自主優化流程完成。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_final_reasonability_verification_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_final_reasonability_verification_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 10 次 / #可驗證性

狀態：完成

本次使用：把完成定義轉成聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節共同支持的驗證門檻。

核心判斷

1. 完成宣稱需要聚焦測試與回歸集合共同支持。
2. diff check 只支持格式乾淨，不能替代測試。
3. strict log、狀態表與契約章節必須同時存在，才支持 HCS Plus 流程完成。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 10 次綜合優化章節新增 `驗證門檻`。
2. `docs/hcs-plus-optimization-state.md` 新增 `HCS Plus 自主優化完成摘要`。
3. 完成摘要列出最終專案內容、決策紀錄、風險與驗收標準、下一步可執行行動。

優化說明

1. 可驗證性把完成定義從口頭宣稱變成可跑命令與可查文件。
2. 完成摘要不得外推為 runtime 安全或使用者理解。
3. 後續若新增契約章節或完成宣稱，必須補對應測試。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_final_reasonability_verification_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_final_reasonability_verification_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 10 次 / #制定策略

狀態：完成

本次使用：把完成後維護策略寫成文件與測試契約優先、例外升級與定期複檢。

核心判斷

1. 完成後不是停止維護，而是改成定期複檢契約矩陣。
2. 涉及 parser、prompt、template、audit、runtime、交易語氣或使用者理解宣稱時必須例外升級。
3. 下一步可執行行動必須能被維護者照著做。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 10 次綜合優化章節新增 `維護策略`。
2. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 10 次標為完成。
3. `docs/hcs-plus-optimization-state.md` 將 HCS Plus 自主優化完成狀態標為完成。

優化說明

1. 制定策略讓 HCS Plus 完成後仍有清楚維護入口。
2. 例外升級防止高風險變更被文件完成狀態掩蓋。
3. 完成只代表本次 HCS Plus 自主優化流程完成，不代表後續工作不需要驗證。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 10 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 下一步

- 完成後維護 / 定期複檢契約矩陣：後續新增 pipeline、模式語意、報告模板或完成回報規則時，先更新契約章節與測試。
- 例外升級：碰到 parser、prompt、template、audit、runtime、交易語氣或使用者理解宣稱時，先補對應測試與人工 review。
- 下一步：完成後維護 / 定期複檢契約矩陣。
