# 台股兩週觀察報告的發布條件

v4 是條件式研究觀察，允許沒有候選。技術／價量訊號可作觀察理由，未來事件不是必填；事件有日期與來源才可稱為兩週事件催化。模型分數、目標價及歷史區間漲跌都不是已驗證的上漲機率或可實現報酬。

## 程式已執行的必要條件

- 行情有來源、有效觀測日、日線和正值收盤／最新價。最新bar日期須與as_of吻合。
- 觀測日不能晚於生成日；超過七個日曆日未更新阻擋發布。七日只是硬性底線，並非交易日或休市日曆完整性認證；較短延遲降級為warning。
- 最新价與最後日線收盤差異超過1%阻擋，要求釐清時點與調整基準；不自動修價。它是內部一致性檢查，不能替代官方獨立驗價。
- 明確宣稱5／10／20日多頭排列而數值不符 SMA5>SMA10>SMA20，或缺少对应值，阻擋發布。此檢查只涵蓋核心催化和已觀測訊號中的明確主張，不代表自由文字已完整驗證。
- 保存的模型目標／停損等僅能驗證分析轉錄一致性，不能自證金融事實。只匹配模型輸出的數字降為unverifiable/caution，轉錄不一致仍標mismatch。
- content_credibility/report_conformance blocked 或 evidence rejected 由既有 persist_report_bundle 門檻阻擋；不寫HTML／Markdown／JSON或成功索引，不覆蓋既有正式報告。

## 可保存但不能當作無警示推薦的情況

法人與行情日期不同、歷史價格調整基準缺錄，或即期Yahoo info FCF期間／合併範圍／完整CapEx未核實，降級為warning。現有publication gate允許warning/caution研究報告保存；這不等於通過獨立事實驗證或交易核准。年度財務frame的primary_financial_audit不能替即期info FCF背書。

Yahoo日線明示auto_adjust=True並保存基準，維持原調整後歷史資料口徑。官方STOCK_DAY原始OHLC及包含零股／盤後／鉅額交易的量，與Yahoo來源量不可無說明混用。不能對已經吻合官方的拆股後現價再次除以拆股比例。

## 尚須補齊的正式每日推薦條件

- 每次取數的官方價格交叉驗證、明確市場時段及休市日曆；當次官方端點失敗不是造假的證據。
- 即期FCF的實際期間、單位、合併範圍與完整CapEx；所有重大新聞主張的原文／公告、發布時間與事件日。
- 進場是等待條件还是可執行限價，須區分；台股價格跳動單位、費用與滑價未確認不能聲稱淨風險報酬已驗證。
- 回測需point-in-time資訊、樣本外驗證與生存者偏誤控制，未完成不提供勝率。

本次離線重建不呼叫模型、不重新取金融資料、不覆寫正式歷史報告。新門檻需重新載入服務才能保證各常駐程序使用一致版本；禁止在使用者Terminal進行中的服務上自行重啟。

## 每日摘要與歷史重繪

最近已完成交易日由現有 market_calendar_store 按 Asia/Taipei 收盤時間、週末及休市日判定。2026台灣內建休市日已與 [證交所115年開休市表](https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html) 核對；未覆蓋年份不假裝一般平日開市。盤前採前一有效交易日，盤後採當日有效交易日。行情／法人未同達該日，latest_source_dates_aligned=false；七天硬上限不代表最近資料完整。

當前品質投影以檢查時刻重新判定資料資格，不改寫原快照。全索引摘要提供current_blocked_reports，每日dashboard在最近20筆之外也納入需要撤回的舊結論，且當前blocked優先於保存時passed。v4阻斷股票從top_candidates移除，轉成人工審核事項。Screener top_candidates始終標記research_only=true、actionable=false，供待查研究，不是可立即交易或已驗證完整的推薦名單。

只重繪或部分重跑仍要经过相同發布門檻；不能把舊錯誤換成新日期發布。舊靜態HTML／Markdown保留其歷史原文，不會自动變成新結果；須看當前品質摘要／重新完整分析。已快取的舊品質結果需重載後重新投影，不能宣稱修改磁碟檔即已在所有常駐程序生效。

數字抽樣中任何已對應來源而超出容差的mismatch，都會rejected，不再以其他正確樣本或低於50%比例稀釋。未抽到的事實仍不代表通過驗證；關鍵行情另外採必查條件。

## 四份報告收尾：財務／新聞／價位

1101的原快照即期FCF為正421.95222528億元，卻保存負FCF風險旗標，而且沒有對應負值期間或assessment。新發布檢查阻擋這種輸入／衍生旗標矛盾；後續重讀草稿時financial risk policy v3只清除已無輸入支持的系統旗標，維持原High風險級別和方向，不會把缺資料當成財務改善。v3參與現有快取版本，避免默默沿用舊衍生判斷。

即期FCF缺期間及完整CapEx，不能作為方向或催化依據。主摘要的FCF欄只呈現待查狀態，不繼續引用原模型的負值壓力結論。重大新聞的方向主張不能借技術／法人來源背書；核心理由／已觀測訊號和事件資料在每次渲染重新對保存來源做範圍核對。這不等於已驗證所有自由文字或新聞原文。

本次已查到[台泥2026/9/23官方公告](https://www.tccgroupholdings.com/news/6ab3447d7b066)：9/22董事會授權最多7.5億歐元推進烏克蘭收購，尚須多國核准；沒有兩週交割日期。這是過去公告背景，不作兩週排定催化。6456的年底出貨標題不代表兩週內事件；2327的AI需求／漲價描述未在本輪取得公司原始公告核實，只可視為報導背景。1301的短期多頭排列論述已由保存數值否證，不用新聞補足該錯誤。

價格依[證交所股票升降單位](https://www.twse.com.tw/downloads/zh/trading/introduce/introduce004.pdf)按明示EQUITY類型核对。6456的85.84進場端點／81.09停損、1301的65.02–65.34端點／61.23停損、2327的605.5目標／556.3停損不符合相應格點；均保留為分析參考，不自動改價或下單。毛風險報酬只列最差進場端點的條件算式；手續費、適用交易稅與滑價未知時，淨風險報酬維持未驗證，不能假設成本為零。

兩項既有取數測試失敗不代表本輪台股行情壞掉：美股monthly_revenue目前合理回not_applicable；2330.TW測試期待FMP error，但現行台股路由刻意跳過FMP，使用免費台灣來源。未更動無關美股或放寬來源測試。

來源可信度與有無下單計畫分開：台股報告沒有trade_setup或方向為Neutral，仍須披露行情／法人原始證據。缺證時source_eligible與eligible為false，另以source_warnings記錄等待原因；數字對照通過只能標示caution，不能略過來源查核而顯示approved。Long／Short既有來源與格點阻擋保持不變，未知商品類型不猜測，無交易結論不計勝負。此為唯讀目前規則投影，不改寫保存原件、固定76範圍或歷史績效。

## 財務金額與原分析時間邊界

明示金額先確認指標、年度或TTM、財務幣別及單位，再比較同口徑來源。年度陣列依保存的years索引及billion_twd契約換算；TTM取命名raw-TWD欄位，不可挑歷史正FCF替代當期負值。financial_currency缺失、財期含糊、外幣、月均／變動端點等尚未有同口徑來源時保持unverifiable；不把情境、預測或模型估值目標當已觀測事實。表格期間欄不當作金額，但保留實際金額的核對。

財務文字以保存且雜湊核驗的原analysis_input比較。合法資料刷新後，最新TTM不得改寫原分析時點的金額；原輸入無法核验時不能以今日資料補認證。核對結果披露來源路徑、原值／單位、同財期、換算值及analysis_input_cutoff。TTM欄位值相同只證明保存輸入一致，未獨立核實財報截止日、合併口徑、完整CapEx或當時可取得性；既有來源、FCF催化與下單限制保持有效。all_extracted_numeric_claims代表全部已抽取主張，不代表全文每項事實都已辨識。歷史原件與當時保存評分不覆寫，現行規則投影另列。


### 收盤衍生引用的基準同義核對

`trade_price_reference.py` 僅在保存來源明示 `yfinance 5y history`，且價格基準完整記錄 `Adj Close / Close` 還原 OHLC 公式時，將模型的 `adjusted_close` 宣告對齊該 provider 收盤基準。路徑限 SMA/EMA 的收盤衍生指標或 daily bar 的 close；不適用 high、low、open、ATR、其他 provider、原始價、split-only、dividend-only 或泛稱 adjusted。未知調整 metadata 保持未核驗。

原宣告、來源描述、catalog 與原件不改寫；等價核對另附可追溯 metadata，日期、期間、數值、推導公式與來源雜湊仍逐項檢查。這是共用核對邏輯，不按 A/B/C/D 放寬規則，也不是官方原始價、可成交價、來源 finality、PIT 或交易許可。


## TPEX 成熟日原始行情邊界

上櫃自然poll以TPEX官方個股月份原文，核對payload code、month、table與唯一成熟日列；月份date不是日觀測date。只有四位exact .TWO映射，未推論商品類型。原始HTTP位元組、SHA、URL、實際acquisition time均保存，post-cutoff仍不保證finality/PIT或整段歷史行情真實可得。成交張數維持lots，鉅額排除註記保留，不換成TWSE股數或混源量比；來源unit/scope宣告必須與原文相符。TWSE原文不能替.TWO背書，TPEX原文不能替.TW背書。缺日期/欄位/原文、stale/busy、價差或hash不符均維持來源等待，不記attempt；無手工append。原快照的instrument/basis缺口不補造。

官方契約來源：[TPEX個股日成交資訊](https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html)，已保存頁面與script證明afterTrading/tradingStock參數code/date/response及月首日期，回應原文fixture另保留取得憑據。


## Scheduled dispatch recovery (Phase38)

Watchlist slot dates acknowledge a confirmed dispatch, not a SQLite claim. New due
slots receive durable `watchlist_dispatches` intents in operational storage, with
a stable job id, a 600-second owner lease and an owner-token compare-and-set ack.
Existing legacy last-run dates remain authoritative; no historical slot is
backfilled on upgrade. Only new pending intents can recover across days/restarts.

Known failures release only the affected lease; unprocessed items remain eligible
after their lease expires. A retry creates or retrieves the same SQLite job and
uses RQ WATCH/MULTI/EXEC with the same task id. Lost EXEC replies are reconciled
against queue/active/terminal evidence. A job hash without such evidence is held
pending, not blindly re-enqueued. Intent/date acknowledgement and dispatch receipt
are committed in one SQLite transaction. Unknown states fail closed.

Pending intents protect their queued jobs from startup abandonment and manual API
attach recovery races. An already running/terminal stable job is acknowledged
without another model execution. Another verified active ticker/mode task can be
attached, preserving the original active-job deduplication behavior. Cancelled
jobs remain cancelled. Retry routing, job timeout, RQ budgets and 45-second
spacing for newly enqueued tasks remain unchanged. External sends are separate.

This path is verified with isolated SQLite and installed RQ against a simulated
Redis command boundary, including competing producers and real subprocess exits.
It does not claim tolerance of arbitrary Redis data corruption/deletion, power
loss during SQLite commits, permanently unavailable storage, or every ARQ runtime.
The production Mac uses RQ; unsupported queue protocols keep intents pending.
