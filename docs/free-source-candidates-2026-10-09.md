# 免費資料入口實測：2026-10-09

2026-10-15 06:09：緯穎6669新版官方新聞格式已修正並正式補入兩篇10/12、10/13新原文，近期7→8篇且通過現行8篇／3來源／30天檢查；一次POST200／3.339秒／4 native HTTP。奇鋐3324既有缺件正常重試一次200／6.911秒，補回15頁法說，仍partial；未增加timeout。158相關＋6 helper隔離檢查通過，1 owned＋264 preserved＝265 runtime、health／ready200、模型0；原分析與品質gates、其他148報告與jobs／兩個目標checkpoint保持。原20類17類>80：法說46/83、財報25/44、近期77/121，目標未完成。[正式證據、免費入口與限制](evidence/source-acquisition/20261015/wiwynn-updated-news-profile/README.md)。

2026-10-15 05:53 合庫金5880問答分支已接上既有完整CSV／JSON官方名冊備援；389相關＋5防重送隔離檢查通過。正式一次來源補件200／2.858秒／3 native HTTP，補回10頁問答，453119只計1成功。265 runtime（2 owned＋263 preserved）、health／ready200、模型0及原分析／gates／其他149報告與jobs／checkpoint保持；本次沿有效CSV快取，JSON故障切換只由隔離測試證明。原20類17類>80：法說46/83、財報25/44、近期76/120，目標未完成。見[正式證據與限制](evidence/source-acquisition/20261015/tcfhc-qa-shared-master/README.md)。另[禾伸堂新67頁比較財報](evidence/source-acquisition/20261015/holystone-comparative-financial/README.md)完整下載，但主要財務表為影像、仍缺明列無形購置，未計正式成功。

2026-10-15 05:37 信邦3023免費MOPS英文69頁法說已正式接入並一次補件成功：200／3.960秒／3 native HTTP，453118只計1成功。582相關＋12矽格隔離回歸通過；9 owned＋255 preserved＝264 runtime，health／ready200，模型0。修正共用MOPS URL誤選矽格驗證器；全69頁保留、整體partial、角色僅1/2/5/14/17/57，原分析／品質gates及其他149報告保持。原20類仍17類>80，法說45/82、財報25/44、近期76/120；[正式證據與限制](evidence/source-acquisition/20261015/sinbon-conference-integration/README.md)。

同輪南電新比較財報53頁已能以既有有界工具唯讀開啟，但三表9頁無文字層、無形現金購置仍缺；未放寬正式reader或補零。[原件查核](evidence/source-acquisition/20261015/nanyapcb-permitted-native-text/README.md)。新央廣財經入口4次研究GET為1×302＋3×200，公開索引可讀，但官方全文授權另有申請條件，未啟用免費全文provider。[資格與原始證據](evidence/source-acquisition/20261015/rti-news-entry/README.md)。


2026-10-15 05:15 新驗信邦公開投資人／新聞API與東訊官方RSS：7次研究GET皆完整200，信邦觀測192筆投資訊息／176筆新聞，1篇10/6原文與detail完全一致；pagination總數不符與月粒度日期保留限制。東訊9篇正文均過期，不補近期件數。未改runtime／正式cache／SLA，原20類仍17類>80；[入口、完整原件與待接入限制](evidence/source-acquisition/20261015/free-news-and-sinbon-mops/README.md)。

2026-10-15 05:08 東訊2321官方21頁法說已接入並唯一正式補件成功：200／2.296秒／2 native HTTP，453117只計1成功。350隔離測試通過，9 owned＋253 preserved＝262 runtime，health／ready200、模型0；原分析／品質gates、報告與jobs／checkpoint保持。整體partial／角色限1、2、16、18、19，估算與圖像未擅補。原20類仍17類>80，法說45/82、財報25/44、近期76/120；[完整證據與限制](evidence/source-acquisition/20261015/tecom-conference-integration/README.md)。

2026-10-15 04:55 榮惠6924免費官網入口正式接入：完整HTML靜態mark表格→8/20中文23頁PDF，3 native HTTP，唯一補件200／4.948秒，453116只增1成功／1嘗試。392隔離檢查、260runtime與原報告保護通過，模型0。角色僅1/2/13，圖像／遮罩客戶／展望／五年財報缺口保持。信邦財報API重查確認為既有候選，未重取灌分；原20類仍17類>80。 [正式證據與限制](evidence/source-acquisition/20261015/eikei-conference-integration/README.md)。

2026-10-15 04:38 續查新免費原件：榮惠6924官網內嵌靜態法說表取得8/20中文23頁；信邦3023公開營運API取得7月版68頁，另沿已存MOPS索引首次下載9月版68頁，核出封面及7／8月營收差異，舊官網版不得覆蓋新會議；東訊2321取得12/17/2025法說21頁。10次native研究GET中9個完整200、1個大聯大403，四份不同PDF／三家公司，未接正式provider或計SLA。榮惠native complete仍漏圖像比較與頁尾預測，整體partial；信邦五年損益摘要不能補現金流缺科目，東訊字形／原件用途標示保留。258 runtime／env／程序、150報告、jobs／模型及ledger453115保持，health／ready200；原20類17類>80，法說44/81、財報25/44、近期76/120未達。[完整入口、原件與內容資格](evidence/source-acquisition/20261015/new-free-originals/README.md)。

2026-10-15 03:59 神基3005免費官方21頁法說已正式接入並唯一補件成功：200／11.297秒／4 native HTTP，453113只計1成功。整體partial、角色限1/2/7/8完整頁；原6000字總上限內保留持股註腳，精確主站302根網址正規化已核對。316相關回歸、最終113專項與5 helper通過（重疊不相加）；9 owned＋244 preserved＝253 runtime，health／ready200，0模型。原分析／gates／HTMLMD、其他149報告及jobs／目標checkpoint保持。原20類17類>80，法說42/79、財報25/44、近期76/120仍不足；[正式原件、helper修正與驗收](evidence/source-acquisition/20261015/getac-conference-integration/README.md)。南電／南亞新原件仍待接入；原法人119件需依新runtime重新凍結基準。

2026-10-15 03:40 續查：新取得南電8046官方14頁、南亞1303官方15頁完整簡報，5次研究GET中4完整200、1財報尺寸限制。兩份簡報的日期／期間與特定字型項目符號已定位，保持partial、未接正式provider或計SLA；見[新免費入口及限制](evidence/source-acquisition/20261015/nanya8046-new-originals/README.md)。同輪法人首六件真缺口已各一次正常補齊90筆，同窗156/196→162/202＝80.1980%，原20類17類嚴格>80；仍不足法說41/78、財報25/44、近期76/120。模型0、原本文與品質保持；119件凍結目標尚未送出，6488 checkpoint身分另待處理，見[正式補件與完整驗收](evidence/source-acquisition/20261015/institutional-remaining-gaps/README.md)。

2026-10-15 03:21 華立3010官方20頁法說已部署並正式補件：200／3.744秒／3 native HTTP，453106只計1成功。266隔離回歸與4防重送檢查通過；9變更＋242保持＝251 runtime，health／ready200。整體partial、角色僅6頁，活動日期／封面月份／財務期間分開；原分析、品質gates、其他149報告及jobs／checkpoint保持，模型0。原20類16類>80，法說42/79、財報25/44、法人156/196、近期77/121；同窗只有法說+1成功/+1嘗試。見[正式證據與限制](evidence/source-acquisition/20261015/wahlee-conference-integration/README.md)。

同輪新取得神基中英文年度財報121／105頁，4次研究GET皆完整200，2025／2024關鍵現金流科目對上。中文部分頁無原生文字，均超一般100頁reader，未放寬限制；神基五年財報原已完整，列免費備援候選、未計SLA。其法說正文仍缺件。見[新免費財報原件](evidence/source-acquisition/20261015/getac-financial-originals/README.md)。

2026-10-15 03:02 更新：既有免費TWSE／MOPS公告補件入口由2851擴充9家真實partial缺件（統一、台達電、富邦金、國泰金、元大金、中信金、材料*-KY、精誠、潤泰新）。9次正式補件全數200／success／30天window_complete，共126篇正文／143 native HTTP，canonical僅+9成功/+9嘗試；API1.382–7.802秒。4個runtime修改＋245保持，226相關隔離測試與12防重送測試通過，正式重載一次／health ready200／6queue idle；原HTML／Markdown、分析與品質gates、其他報告與jobs／目標checkpoint保持，模型0且分析仍需重跑。原20類仍16類>80，近期事件同窗68/112→77/121＝63.636%；法說41/78、財報26/45、法人156/196未達標。公告完整不等於多發布者新聞或報告品質通過；見[正式來源、原件重播與驗收](evidence/source-acquisition/20261015/remaining-provider-causes/README.md)。

2026-10-15 02:40 更新：[臻鼎官方免費法說入口](https://www.zdtco.com/public/tw/investor/events)最新10/13–14場次已接入，採10月38頁原件（10,837,119 bytes），不沿用先前8月24頁版本。精確PDF允許20秒／固定大小，總25秒、原TTL／冷卻／品質邊界及共用reader保持。完整保存原件，角色僅使用已核對1/2/5/22頁；32/33不可視Q4模板字、36比例疑義整頁排除。275隔離檢查及4補件歷史驗證通過（重疊不加總）；9變更＋240保持runtime正式重載，一次200／19.567秒／3原生HTTP，453096＝1成功，模型0。舊分析與品質gates及其他149份報告保持且原分析需重跑。原20類仍16類>80，法說41/78、財報26/45、法人156/196、近期68/112；見[正式原件與驗證](evidence/source-acquisition/20261015/zdt-conference-integration/README.md)。

2026-10-15 02:20 左右續查：台泥1101一次指定財報補件200／3.295秒，2021–2025五年原件重播通過，2021 FCF空值恢復；453095只計1成功，原正文／分析品質gates保持且需重新分析。鴻準2354一次補件502，19 HTTP全部200但比較數缺欄衝突，453094失敗保留；新原件數值與既有研究相同，不再當傳輸問題重試。新運錩72頁、高力英文64頁2021官方合併財報完整下載並視讀現金流表，但仍缺gross無形購置，不補零、不計五年成功。六次native研究GET與正式兩次POST分開；未改runtime／未重載，0模型，原20類仍16類>80。見[原件、正式補件與同窗驗收](evidence/source-acquisition/20261015/remaining-four-shared-gaps/README.md)。

2026-10-15 01:08 更新：睿生光電6861官方19頁法說已正式恢復，唯一補件200／7.682秒／3原生HTTP，事件453091＝1成功；原分析與品質gates保持、需重分析。201隔離測試＋4 helper檢查，243 runtime正式核對。原20類仍16類>80，法說39/76、財報25/43、法人156/196、近期68/112；見[部署與實測](evidence/source-acquisition/20261015/innocare-integration/README.md)。

新找到[彰銀官方法說／問答](https://www.bankchb.com/frontend/earningsCall.jsp)與[華立新版簡報](https://www.wahlee.com/zh-TW/financial-calendar-presentation)。兩個完整索引＋三份完整PDF均原生200；彰銀32頁簡報partial、7頁問答整理原生文字complete；華立9/4場次連結8月製作的20頁簡報，原生文字complete、內容H1／營收至7月。正文與原件已保存，尚未正式接入、未計SLA。問答非逐字稿，華立長投頁口徑差異不硬湊；[查驗與後續](evidence/source-acquisition/20261015/chb-wahlee-free-entrances/README.md)。

2026-10-15 00:48 免費入口續查：新完整取得睿生6861（19頁）與臻鼎4958（24頁）官方簡報；臻鼎首次5秒不完整保留，精確同檔10秒研究取得完整原件。中興電1513既有38頁原檔逐核364物件後可安全讀取，但2空頁／2異常頁仍partial。身份／原epoch／內容限制保存，研究5 GET不列正式SLA，4隔離資格檢查通過；本輪無正式code／POST／模型，150最新快照保持，原20類仍16類>80。見[新入口、實測與接入限制](evidence/source-acquisition/20261015/next-source-recovery/README.md)。

2026-10-15 00:35 續查免費入口並正式驗證：2308恢復2021–2025財報、1605補入11頁法說；三陽合併器依原主檔24h與新聞30m各自核原件期限，修正後新聞4→7／3發布者（仍未達8篇）。1修改＋240保持runtime經正式入口載入，194回歸通過，4次指定來源POST共3成功1失敗，模型0；453089歷史誤標local_block保留，已修未來HTTP失敗分類。新台塑化445頁年報／96頁議事手冊完整取得但仍缺無形購置，不算五年成功；臻鼎別名為重複原件。原20類仍16類>80，所有類別達標目標未完成。見[本輪正式證據與完整限制](evidence/source-acquisition/20261015/current-gap-followup/README.md)。


2026-10-14 22:32 聯華1229官方30頁法說已正式補入最新報告。根據前次453048的PDF5秒timeout證據，只將exact PDF單次預算改10秒，整體25秒／HTML5秒／connect2秒／8MiB／零重試與品質界線不變。原admission自然到期後唯一POST200／12.562秒／3 native HTTP；453050只記1成功，前次失敗保留。主檔沿真實原epoch warm命中，原件30頁仍partial／6圖像頁缺文字／角色只1、22、24、25；原HTML／Markdown／分析gates、其他149報告及index、jobs／target checkpoint、MOPS guard保持，0模型，分析仍需重跑。

1 owned＋226 preserved＝227 runtime、env／158套件保持，health／ready200。作者193、root21＋40、獨立2檢查通過（覆蓋不相加）。原20類仍16類>80：法說38/75、財報25/44、法人155/196、近期67/111。整輪固定同窗新增1成功／2嘗試，不抹前次失敗或把自然離窗算成效；453049月營收cache為背景觀測。見[本輪正式恢復與限制](evidence/source-acquisition/20261014/lienhwa-pdf-budget/README.md)。

2026-10-14 22:21 聯華1229免費官方30頁PDF路由已部署：10 owned＋217 preserved＝227 runtime，env／158套件保持，health／ready200。精確主檔／索引／場次／PDF原件鏈、no-store與partial角色限制均保留，6圖像頁與p15不當作已驗證內容。唯一正式補件502／11.685秒／4 native HTTP／timeout，453048失敗保留，未宣稱正文恢復；全部150份原報告／index、分析gates、jobs／target checkpoint與MOPS guard保持，0模型。原20類16類>80：法說37/74、財報25/44、法人155/196、近期67/111；同窗法說+1失敗，月營收453047屬獨立觀測。見[本輪部署與首次失敗證據](evidence/source-acquisition/20261014/lienhwa-conference-integration/README.md)。

另新取得材料-KY官方69頁2021／2020英文財報；原2021–2025五份CF與比較欄均未明列無形購置，不是單年傳輸問題，沒有填零或計五年成功。研究2 GET與正式SLA分開；見[全年度缺口與改善方向](evidence/source-acquisition/20261014/annual-next-gap/findings.md)。

2026-10-14 21:47 續查新增可實際讀取入口：三陽公司官網明列的 `tw.sym-global.com` 與國際站，完整取得三篇近期產品／公司原文；舊 `sym.com.tw` native TLS 憑證過期，不降級驗證或重試。彰源現行年報下載已移至官網直接發布的 Azure Blob，2021 年報完整210頁／1,720,407bytes；禾伸堂2021英文年報完整260頁／3,345,807bytes。兩份合併現金流仍未明列無形購置，不填零、不算五年補齊；彰源另有母公司歸屬口徑待核。北極星公司pipeline精確連到 ClinicalTrials.gov v2，三份完整匿名JSON可補目前試驗狀態與actual／estimated日期；舊更新不算近期新聞、登錄不等於FDA核准。

聯華既有原件的限定字型研究可修p15三個bullet，但該頁還有被覆蓋文字，不能供角色直接引用；六個圖像頁及p2免責仍保留partial，沒有放寬generic reader或接入正式來源。原研究缺取得epoch不能種入正式cache。本輪研究未部署；223 runtime／env／程序、SLA453046／usage749930、舊零值prefix、九份新聞候選最新snapshot與MOPS guard均前後相同。原20類仍16類>80；法說38/75、財報25/44、法人155/196、近期67/111。先前39/76→38/75是舊觀測自然離窗，不歸功研究。完整入口、用途與限制見[本輪研究證據](evidence/source-acquisition/20261014/free-entry-followup/README.md)。

2026-10-14 21:26 新發現聯華1229公司官網直接簡報入口，完整取得30頁PDF／6,793,541bytes／3.93秒，封面與官網場次頁對應9/30。原生reader仍為partial：6頁無文字、p15字元異常；第2頁免責說明是圖像，不能忽略。這是研究候選，未正式接入或計SLA，沒有重試MOPS。

同輪已部署1623／2308／2367完整主檔CSV→JSON與4profile歷史法說保留；223受核對runtime、環境／158套件保持。三份最新缺件各一次200，分別48／13／16頁與12.64／3.90／1.70秒，5／2／2 native HTTP；本次真正取得CSV，後兩份沿原epoch共用，JSON分支以隔離重播驗證。0模型，HTML／Markdown／原分析gates、其他149報告與jobs／target checkpoints保持。法說同窗成功／嘗試各+3，月營收453043是獨立背景觀測；原20類仍16類>80，法說39/76、財報25/44、法人155/196、近期67/111。歷史保留不算新成功，雙鴻現有缺正文未在本輪恢復。見[入口與正式驗證完整證據](evidence/source-acquisition/20261014/conference-resilience/README.md)。

2026-10-14 20:52 華航免費IR的exact gzip傳輸已部署並正式補齊2021–2025財報：200／15.620秒／24 native HTTP，完整wire／decoded與五年原件重播通過，453041只記1成功。3 owned＋217 preserved＝220 runtime、環境／158套件保持、health／ready200。作者最終119、root獨立192、helper22＋1與最新目標2通過（重疊不相加）。

聯華1229舊報告目標於POST前被latest檢查擋下；修正到真正最新0e4320990e4e後只做1次補件，502／10.679秒／2 native HTTP。官方9/30索引完整取得，但PPTX取得2,424,832 bytes後timeout，453042保留失敗，原snapshot／HTML／Markdown與分析gates保持，0模型；guard未清除。兩次各自核對其他149份最新報告／index、所有job rows與各目標checkpoint原件。原20類16類>80：法說36/73＝49.315%、財報25/44＝56.818%、法人155/196＝79.082%、近期67/111＝60.36%。本輪兩次來源同窗財報+1成功/+1嘗試、法說+0成功/+1失敗，另月營收453040為獨立觀測；全目標未達。四份同報告法說正文因一般刷新失敗被空值覆蓋已查明，防覆蓋仍待下一段實作，不宣稱已恢復。見[本輪正式補件與剩餘缺口](evidence/source-acquisition/20261014/cal-gzip-and-gap-recovery/README.md)。

2026-10-14 20:21 年度財報主檔備援與完整歷史保留已正式部署：CAL／TCFHC共用完整官方CSV→gzip JSON，保留45秒總期限、5秒單次、原epoch／expiry與guards；舊完整MOPS五年只在可完整重播且同口徑暫時失敗時保留，不拼接Yahoo年度或重設取得時間。8 owned＋211 preserved＝219 runtime、環境／158套件、health／ready200。相關317、作者385與63、獨立77與34、保存後原件重播2通過（重疊不相加）。

合庫金5880唯一正式補件200／13.471秒／6 native HTTP，2021–2025金融業財報已完整保存與重播；453039只計1成功，主檔沿真正取得的原epoch warm命中。華航2610唯一補件502／10.192秒，CSV＋19份MOPS原件已取得，依固定流程推定第21次IR列表timeout；453038失敗保留、原快照保持。兩份HTML／Markdown、分析／品質gates、其他149份最新報告／index、jobs／checkpoints保持，0報告模型；5880其他freshness只沿原audit同或較早epoch，結論仍需重分析。原20類16類>80：法說36/72＝50%、財報24/43＝55.814%、法人155/196＝79.082%、近期67/111＝60.36%。同窗本輪只帶來財報成功+1／嘗試+2；全目標未達。

另一次華航exact IR gzip研究200／1.207秒，139,712wire→1,103,229decoded bytes與三份已發布PDF連結核對通過；尚未接入正式transport、未抓PDF、不計SLA。2308是預防修正，未恢復現有正式四年快照；1229冷卻已自然過期但未重抓，法人仍待既定定稿時間。見[本輪正式補件、研究入口與剩餘缺口](evidence/source-acquisition/20261014/annual-master-and-retention/README.md)。

2026-10-14 19:29 中砂1560免費官方法說正文已接入正式服務。完整38筆內嵌索引按實際場次日期選9/21–22，避免Seq排序誤取舊場次；精確36頁原件、嵌入字型／CID及每頁hash核對後，只恢復25圓點與7菱形，p5／6／7不拼回重複Form文字。角色保留季度／H1、單位、子公司、產能差異與展望限制；原生文字complete、整體partial，非逐字稿與完整財報。原件私存查核，新取得每次原生讀index／PDF。

11 owned＋206 preserved＝217 runtime、環境／158套件保持，health／ready200；原6件retry在重載前4 done／1品質blocked error／1 waiting_retry，六份原payload hash均保持，現有1排程與future score保存。相關374、reader164、獨立164、helper18通過（重疊不加總）。唯一正式補件200／13.071秒／3 native HTTP，正文0→36頁；453036只記1次成功，0報告模型。HTML／Markdown、分析與品質gates、其餘149份最新報告／index、jobs/checkpoints保持；股價／財報freshness只回投原audit較早epoch，其餘沒有刷新取得時間，仍需重新分析。原20類16類>80：法說36/72＝50%、財報23/42＝54.762%、法人155/196＝79.082%、近期67/111＝60.36%。全目標未達；CAL／TCFHC年度master備援及2308完整財報保存回歸仍待修，法人待22:30後確認。見[本輪入口、正式補件與剩餘缺口](evidence/source-acquisition/20261014/kinik-conference-integration/README.md)。

2026-10-14 18:57 上銀2049免費官方法說正文已正式接入：精確13頁原件／117物件xref／11圓點符號、完整TWSE主檔與當期官網索引共同核對；保留整體partial與非逐字稿限制，角色排除5頁不可見原生文字，index/PDF/整包結果不重用成功快取。11 owned＋202 preserved＝213 runtime，環境／158套件保持，health／ready200、6件retry保存。相關334、獨立161、helper18通過（覆蓋不加總）。唯一正式補抓200／7.007秒／3 native HTTP，正文0→13頁；453034只計一次成功，HTML／Markdown、分析與品質gates、其餘149份最新報告、jobs/checkpoints、其他取得epoch保持，0模型，仍需重新分析。原20類16類>80：法說35/71、財報23/42、法人155/196、近期67/111。中砂36頁原件仍研究待字形資格；MOPS冷卻20:08:23保持。見[本輪免費入口與正式驗證](evidence/source-acquisition/20261014/hiwin-conference-integration/README.md)。

## 2026-10-14 18:28：MOPS 主檔備援部署與新公司官網入口

後續中砂已完整下載38筆內嵌索引實際引用的2026Q2原檔，**8,125,407 bytes／36頁／3.497秒**，現有reader得10,649字元，13頁有未核私用字元；上銀全117object的xref-leading-LF原因已離線證實，可保留原bytes提取13頁，但11頁仍含U+F06C。兩份完整檔案均維持partial／held，沒有當正式成功；沒有把未解析圖表或Q&A當已讀正文。見[中砂完整資格紀錄](evidence/source-acquisition/20261014/remaining-originals-after-json/kinik-new-conference-entry/qualification.json)與[上銀離線診斷](evidence/source-acquisition/20261014/remaining-originals-after-json/hiwin-new-entry/offline-qualification/result.json)。

既有2330／1229法說collector已接完整CSV→壓縮JSON主檔備援，同一25秒、原1800或較短expiry、403／429與未知guard保護保持。最後交付三原件期限P2已修。2owned＋207preserved＝209runtime、env／158套件、health／ready200與7retry保存；固定版355、獨立103、helper14通過（重疊不加總）。MOPS冷卻至20:08:23，沒有新正式補抓或模型；原1229失敗452365保持，未宣稱native恢復。原20類最新16類>80，法說34/70、財報23/42、法人155/196、近期67/111；新8筆自然法人工作因當日暫定資料保持partial，不修改驗收口徑。

新[上銀法說頁](https://www.hiwin.tw/stock/meeting_info.aspx)及[13頁英文PDF](https://www.hiwin.tw/uploadfiles/file/conference/20260508_final_E.pdf)均完整native200，約0.56／0.59秒，PDF978,367bytes，但generic reader有header警告，不能當正式正文。新[中砂法說頁](https://www.kinik.com.tw/zh-tw/Investor/Conference.html)完整HTML含38筆內嵌資料，已找到9月場次實際引用的Q2PDF入口，正文資格續查。新[川湖法說頁](https://www.kingslide.com/investor_stockholderservice_reports/)一次5秒timeout／0bytes，不重試；[遠東新新版法說頁](https://www.fenc.com/en-US/investor/presentations)已有10/6附件線索，尚未證明完整native正文。詳見[本輪完整證據](evidence/source-acquisition/20261014/mops-master-recovery/README.md)；研究不seed正式cache／SLA。

## 2026-10-14 14:15：壓縮JSON入口已正式補回金像電法說

[TWSE免費JSON主檔](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)已接入GCE／Allis的CSV暫時故障備援。正式2368缺件補抓一次200／13.906秒：CSV先逾時，完整gzip JSON再取得302,549wirebytes／1,327,577decodedbytes／1095公司，接續金像電原生索引及11頁英文PDF，共4native HTTP，只計1筆source成功。真實來源URL、wire／decoded原件與各自hash、原epoch／TTL、403／429與deadline保護保持；研究未種正式cache，原451597／451598失敗保持。

本次新增451599；同一窗口法說成功與嘗試各+1，其他19類不變。原20類17類>80，法說29/56＝51.786%、財報22/33＝66.667%、近期60/106＝56.604%，整體目標未達。只補來源，原報告HTML／Markdown與品質gate保持且仍需重新分析；11頁原生文字完整不等於圖表／Q&A或財報完整。6owned＋202held＝208runtime、health／ready200；作者269、獨立96、helper31通過，無新模型。見[正式驗證、完整收據及限制](evidence/source-acquisition/20261014/issuer-master-json-fallback/README.md)。

另重讀2883五年既有資料與2021／2022完整英文IR原件，仍未證明必要的無形資產現金購置款；2022比較數衝突的舊失敗未留當次逐原件綁定，不能命名確切差異或以其他版本代證。維持held，不補零、不重抓健康2610／5880；[離線缺口調查](evidence/source-acquisition/20261014/issuer-master-json-fallback/financial-gap-research/findings.md)。

## 2026-10-14 13:48：完整TWSE壓縮JSON與當日個股PDF（接入前）

[官方JSON主檔](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)正常gzip協商實測200／4.132秒，302,549wirebytes完整解壓1,327,577bytes、1095個唯一代號；全公司七個身分欄與完整CSV逐值相同，出表2026-10-13。先前未壓縮5秒只收到部分body，本件是完整候選，尚未接入、不是正式成功。另[2368當日個股PDF](https://www.twse.com.tw/pdf/ch/2368_ch.pdf)5頁／393,362bytes／0.241秒，legal+ticker+website可核但無UBN，不能替代含統編主檔契約。

本輪只部署GCE／Allis完整CSV主檔的原1800秒共用與single-flight；正式缺正文2368再一次5.280秒master timeout，原件未補上，451598及451597失敗保留、全150最新報告保持。原20類仍17類>80。研究三次HTTP沒有種正式cache／SLA；下一步優先獨立typed compressed JSON接入，保留所有期限／證據要求。見[研究資格、部署及完整限制](evidence/source-acquisition/20261014/issuer-master-reliability/README.md)。

2026-10-12 新增兩個免費官方月營收備援：政府[上市dataset18420](https://data.gov.tw/dataset/18420)的[上市CSV](https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv)，以及[上櫃dataset56510](https://data.gov.tw/dataset/56510)的[上櫃CSV](https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv)。完整原檔原生HTTP200實测上市163,059bytes／869列／0.367秒，上櫃141,862bytes／761列／0.503秒，出表1151012、資料11509。這是完整下載，不是全發行人覆蓋；只接當月及上月兩個相鄰月份，不能當六個月歷史、TTM、年度財報或PIT。千元單位依官方月營收申報及[台積電原6-K](https://www.sec.gov/Archives/edgar/data/1046179/000104617926000680/tsm-revenue20261008.htm)相同511,857,399千元核對。MOPS歷史頁原生HTTP200只有800byte安全性存取限制，未繞過，也未採作資料。

FinMind成功仍沿用原有最多六月份資料；失敗才用新官方快照。同一次fetch且同股票、市場、uncached typed operation的既有失敗只保留一次，免立即重抓；缺列仍unknown而非零。新獨立原文快取守1800原TTL、完整原bytes／hash／URL／native10欄receipt、原旗標、最終deadline與TTL，cache不當新抓取成功。兩個獨立P2及三個實際RED（duplicate primary audit、矛盾HTTP／shared-only receipt）均保存並關閉。Root相關12模組400pass、必要runtime/storage21pass；獨立相關及原probe424pass、補充5pass（重疊不相加）。五個runtime路徑已由start_mac.command部署，另外110個原runtime檔、環境與158套件保持，health／ready200，15件pending payload／14件scheduled score保留至自然到期；90筆舊零資料列依原90日policy自然到期，精確原列及hash仍留在release證據，未手動刪除或重建。

正式自然工作已觸發備援：2466.TW本次FinMind失敗後，官方CSV冷HTTP200但缺該公司，449013仍記unavailable；6152.TW本次FinMind失敗後，449074以同一正式原件快取补回2026年8月3.12億／9月1.92億，原取得epoch1791802636.789906、partial與primary失敗保留，HTTP0且新SLA成功0。6152整份報告仍因法人分項證據／final_audit gate未發布，不宣稱報告成功；不更動news8／3／30、年度5年9facts、價格、TTM或qualitygate。研究HTTP3（兩CSV、一個被限制的歷史頁），研究provider-cache/SLA seed0、optimizer新模型0；自然watchlist的來源／模型活動另計。詳見`docs/evidence/source-acquisition/20261012/official-monthly-free-fallback-release-proof.json`、`official-monthly-free-fallback-independent-review-fixed.json`、`official-monthly-6152-actual-failed-primary-recovery-proof.json`及`official-monthly-free-fallback-first-live-observations.json`。

2026-10-12T18:58:30.002354+08:00正式24h仍僅10/20原類別各嚴格>80%，整體目標尚未達成，FinMind自然恢復也不歸因本次patch。金融業及未列公司月營收、六月份完整歷史、法人分項／其他10類別缺口仍需新免費入口；不以健康重抓、快取、research或平均數製造達標。


## 盟立2464／兆豐2886：兩個完整免費新聞入口正式補件（2026-10-12）

2026-10-12T16:59:00.171280+08:00 盟立2464及兆豐2886兩個完整免費官方新聞入口已部署，兩份實際不足8則的既有報告在主檔修正後各補一次：2464.TW 7→8則／HTTP200／2.2698秒／2 native HTTP；2886.TW 7→10則／HTTP200／2.8867秒／4 native HTTP，均符合原8／3／30門檻。新原文各自只增加一個發行人publisher，不是新增獨立媒體。

完整TWSE主檔綁定盟立自動化股份有限公司／22099478／Mirle／登記mirle.com.tw，以及兆豐金融控股股份有限公司／70796754／MEGA FHC／登記megaholdings.com.tw，再核原生索引、全文、法律主體及日期。盟立[2026新聞中心](https://www.mirle.com.tw/news/?index_m_year=2026)綁定[9/15合資公告](https://www.mirle.com.tw/news-detail/671/)；兩份responsive文字須一致，仍只算一篇。兆豐[原生新聞列表](https://www.megaholdings.com.tw/tc/news.aspx)的四個公開id／cid／chk／param參數原樣保留，只採明确母公司標題，原生ROC首日須符合索引ISO日；不把子銀行或公益活動當母公司年度審計財報。發布頁顯示日不升格首次刊登，影像、事件影響、全文陳述與audit均未獨立證明，窗口保持partial。

獨立P2發現新request可被既有3042 context改寫，兩個實際public provider反例及blocked收據保存；修正以request或resolved context任一屬新route就先核精確主體，不改舊route契約。原UTF8、三種root股票類型、完整三收據、hash、原epoch、cached master HTTP未知、最後deadline及warm failure拒收保持。首次兩次正式补件分別5.1595秒及2.1572秒／502，均止於OpenAPI JSON主檔timeout；原失敗442055／442242及當時report三artifact保持。政府[上市公司基本資料dataset18419](https://data.gov.tw/dataset/18419)直接發布的[完整官方CSV](https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv)已實測HTTP200／673,300bytes／1,095列／出表日1151011，兩公司完整身份吻合。僅此兩新collector改用CSV primary；原CSV bytes／SHA／來源URL／retrieval epoch保存，derived JSON只給既有法名／日期parser，strict UTF8sig／quoted row／unique header／全row shape核對。舊完整JSON收據仍可重播；CSV不得冒充HTTP未知cached JSON。16:07第一研究原件已自然到期而未採用；獨立native context診斷在原5秒上限內另取得完整CSV／4.7372秒，保存獨立新epoch與收據，未延長舊epoch。第二兩次CSV cold正式補件仍逾時，四次fail皆保留。顯式採用新完整原件只在私有receipt retention留原1800TTL剩餘秒、HTTP／SLA／model0，normal provider raw/error cache逐欄保持；新聞仍須native索引及正文。Before use／archive／final重核原TTL與同20秒deadline；兩P2的final deadline漏檢及expired records滲入normal merge已修正，原blocked／RED保留，失敗清當次records保留actual HTTP與error，歷史saved verifier及普通partial policy保持。原件重用不證明API原生cold主檔已恢復穩定；到期仍走原get／guards。JSON原24h於15:33到期，沒有手動續期、seed研究原件或重設error cache／guard；CSV沿原1800秒native raw cache與120秒error cache，5秒／connect2／20秒總期限及2.5MB master上限保持。舊鴻海原件只核完整hash與當時使用資格，未聲稱過期主檔目前仍新鮮。

Root 250相關、前一版1187相關及150補充契約與獨立runs分開記錄；重疊不加總。CSV修正1owned／110preserved＝111runtime、env／158套件、正式程序、health／ready200、既有待處理及排程payload／score保留核對。兩份HTML／Markdown、quote／TTM／財報／社群及核心epoch、analysis evidence、五品質metadata保持，analysis_text_stale=True，本輪補件未呼叫模型或產生新完整報告品質結論；自然watchlist工作仍照原流程使用來源／模型，原則上不能以全域帳本不變或queue0作此輪證據。原job／dispatch／失敗與零筆prefix保持，無force kill、commit或push。

完整本輪同一窗口包含四次保留error及兩次原件重用後success，近期事件success+2／attempt+6，其餘19類逐欄相同；僅移除六個本輪fetch IDs比較，其餘自然來源工作兩側均保留。成功補件實際HTTP另列共6；四次失敗詳細傳輸數未在SLA收據保留，不補造全輪HTTP總數，也不把自然離窗歸因patch。原20類9類嚴格>80，未達：alternative_data 19/67＝28.3582%、dynamic_peer_metrics 38/94＝40.4255%、earnings_call 36/57＝63.1579%、financial_statements 32/46＝69.5652%、institutional_trading 59/113＝52.2124%、monthly_revenue 55/165＝33.3333%、pe_river_chart 94/149＝63.0872%、peer_discovery 30/81＝37.0370%、recent_catalysts 171/425＝40.2353%、search_upstream 295/391＝75.4476%、social_sentiment 49/122＝40.1639%；全部20類目標尚未完成。News8／3／30、財報五年九事實／accepted typed sector、quality／quota／TTL／cooldown／deadline皆保持。

另探查兩個新東元1504官方財報PDF地址：2024回應metadata不合格；2022實際HTTP978、1005bytes HTML，非PDF，確切拒絕原因尚未證明。保留完整body／header／metadata，沒有相同請求重試或放寬transport，不計研究成功為正式SLA；十次native研究請求與正式六次請求分開記錄。

見[盟立正式補件](evidence/source-acquisition/20261012/mirle2464-retained-master-formal-news-refresh-proof.json)、[兆豐正式補件](evidence/source-acquisition/20261012/mega2886-retained-master-formal-news-refresh-proof.json)、[當前全20類驗證](evidence/source-acquisition/20261012/registered-master-original-current-closeout.json)、[修正覆核](evidence/source-acquisition/20261012/registered-master-original-independent-review-fixed.json)、[原阻擋收據](evidence/source-acquisition/20261012/registered-mirle-mega-independent-review.json)、[東元完整native診斷](evidence/source-acquisition/20261012/teco1504-new-2022-full-native-diagnostic.json)。

## 鴻海2317：免費完整單場索引與逐字稿已部署（2026-10-12）

2026-10-12T14:05:30.107541+08:00 鴻海2317免費完整法說逐字稿入口已部署。完整TWSE主檔核對2317、鴻海精密工業股份有限公司、統編04541302、HON HAI與登記www.honhai.com；原24小時epoch與HTTP未知保持。由[登記官網單場頁106](https://www.honhai.com/zh-tw/investor-relations/investor-relations-activities/investor-conference/106)原生下載區連到[官方完整逐字稿](https://image.honhai.com/upload/202608/law_talk/Hon_Hai_2Q26_Results_Transcript_Chinese_20260818_4465.pdf)，實際缺正文的8/12場次source-only更新HTTP200／3.3000秒／2 native HTTP，正文0→23頁，完整PDF1,057,998 bytes與三份原件可重播。沒有模型呼叫或新全報告。

原native直連索引失敗保留；單變因HTTP1.1探查取得200但超600KB，全年度索引亦超新入口1MB限額，兩次完整性失敗不當成功或重試灌分。新公布單場頁完整955,110 bytes可在同上限取得，只有新HonHai傳輸用HTTP1.1／頁面1MB，既有source上限與PDF8MB不變；未下載15.6MB投影簡報。單次5秒、connect2秒、同一20秒總deadline、TLS、cooldown、lease、cache原24小時及禁cookies／auth／proxy／redirect／自動retry皆保持。正常查詢仍讀原場次metadata，只補已宣告8/12的matching call，其他日期沿舊流程；既有裸2317 call僅在explicit2317.TW EQUITY根與該日期下相容。

PDF封面宣告會議2026/8/12台北15:00、2026 Q2，`event_date_basis=official_transcript_cover_declared_date_time`；頁面7/29只記顯示日，檔名8/18不當首次發布或文件發布日，兩者未知。`native_text_coverage=complete`只表示完整原生文字可讀，overall coverage仍partial；實際會議、逐字稿準確性、影音／所有陳述未獨立核驗。角色3／5／12取得每角色≤2500字元／6頁的原生文字prefix、原件hash、頁碼與日期依據；新typed transcript全文不進generic base，legacy其他正文保持，內部原件路徑剝除。

獨立覆核的兩項初始P2、後續成功旗標退化及root RED全部保留，固定版另存。冷抓取最後核對逾時保留真2次native HTTP／component，warm逾時記當次HTTP0並保持error，不能標正常cache跳過；reader後、封面後、context equality後及deepcopy交付後都核同deadline。來源核對失敗／逾時保持502及原snapshot，不啟第二metadata workflow。Root 1135相關、150補充契約與獨立runs分開，重疊次數不相加；10owned／100preserved＝110runtime、env／158套件／正式程序、health與ready200／六queue0核對。原job、dispatch、failure及零筆prefix沿原retention保持，無force kill、commit或push。

同一窗口法說success／attempt／HTTP各+2，parent aggregate HTTPfalse且排除，其餘19類逐欄不變；研究未seed正式cache／SLA，自然離窗不算patch貢獻。原20類17類嚴格>80；未達：earnings_call 35/45＝77.7778%、financial_statements 31/50＝62.0000%、recent_catalysts 116/168＝69.0476%。全部20類達標目標尚未完成。原HTML／Markdown、quote／TTM／財報／新聞／社群、核心epoch、analysis evidence及五品質metadata保持，analysis_text_stale=True，未跑新全報告品質；news8／3／30、財報五年九事實及accepted typed sector、quality／quota／TTL／cooldown／deadline門檻皆保持。

見[正式補件](evidence/source-acquisition/20261012/honhai2317-transcript-one-formal-refresh-proof.json)、[當前驗證](evidence/source-acquisition/20261012/honhai2317-transcript-current-closeout.json)、[最終固定版覆核](evidence/source-acquisition/20261012/honhai2317-transcript-independent-fixed-v2-review.json)、[原初始阻擋](evidence/source-acquisition/20261012/honhai2317-transcript-independent-review.json)、[後續旗標阻擋](evidence/source-acquisition/20261012/honhai2317-transcript-independent-fixed-review.json)。

## 鴻海2317：新完整官方CDN逐字稿入口，正式接入待核（2026-10-12）

[官方法說目錄](https://www.foxconn.com/zh-tw/investor-relations/investor-relations-activities/investor-conference) web公布的[2026年第二季中文逐字稿](https://image.honhai.com/upload/202608/law_talk/Hon_Hai_2Q26_Results_Transcript_Chinese_20260818_4465.pdf)已用本機native HTTPS實際取得：HTTP200／0.6408秒／1,057,998 bytes／23頁，完整原件與原生文字已保存，無empty／garbled pages。原件SHA f4e0ac83018b188c4df7a8d84e0aab73ff046501b0445756138ac1970839e227。完整TWSE主檔綁定2317、鴻海精密工業股份有限公司、統編04541302與登記www.honhai.com，PDF封面法名、官方網站與2026/8/12台北15:00會議日期時間吻合。當前真實報告仍只有8/12metadata／正文0頁；這次只研究及資格核對，没有source-only正式刷新。

主站www.honhai.com與替代www.foxconn.com兩個索引native直連各1次transport_error，均保留、不重試；CDN原件1次成功，因此新增研究共3次native HTTP。完整native索引與替代網域橋接／正式provider契約尚未核可，不猜最新場次，不算正式SLA成功。web披露中文投影簡報15,598,386 bytes已超原8MB限制，沒有native下載或提高上限；改讀官方另外公布的完整23頁逐字稿，不截斷大檔或假稱取得簡報。檔名20260818不是會議日或首次發布日證據，首次／文件發布日未知；全文可讀不等於逐字稿準確性、所有陳述或財務數字已獨立確認。

研究未seed正式provider cache／SLA，未呼叫模型／報告刷新或改snapshot／HTML／Markdown／原結論；正式source439891／usage729601保持。見[完整原件](evidence/source-acquisition/20261012/honhai2317-new-transcript-native-research.json)、[當前缺口與原件核對](evidence/source-acquisition/20261012/honhai2317-complete-transcript-and-current-gap-qualification.json)、[原索引失敗](evidence/source-acquisition/20261012/honhai2317-new-conference-index-native-research.json)、[替代索引失敗](evidence/source-acquisition/20261012/honhai2317-alternative-conference-index-native-research.json)。

## 晶技3042：完整法說原件免費入口（2026-10-12）

[官方法說索引](https://www.txccorp.com/investor/corporatebriefing/175/461/)原生列出的[9/10完整PDF](https://www.txccorp.com/download/219/)為2,667,196 bytes／15頁；原件SHA f54205054979cf1a896cf72a344795d113df78e9c1193ac9be4ef369cd2ca214。

2026-10-12 12:23 晶技3042免費完整法說簡報入口已部署。`txc_conference.py` 核對完整TWSE主檔的法名、統編21204867、TXC與登記www.txccorp.com，再由原生法人說明會索引绑定9/10 `/download/219/`完整PDF。一次真正缺口source-only更新HTTP200／5.5773秒／2 native HTTP，原正文0頁補為15頁，來源三份完整原件均可重播，主檔舊epoch與HTTP未知保持。沒有模型呼叫或新全報告。

三種原生符號僅於完整嵌入字型、CMap與CID匹配時，將獨立fragment中的■／◆／✓精確恢復；原件2／13頁視核，總18個替換，其餘字元、數字、順序及PDF逐byte保持。未知字型、混合數字或其他字形仍拒絕。`native_text_coverage=complete`只表示原生文字可讀，整体coverage仍partial；封面沒有場次日，9/10僅為索引連結的活動日期，`event_date_basis`保留於角色3／5／12。首次發布日、文件日與內容期未知，未宣稱實際完成法說、逐字稿、影像／圖表數字、閱讀順序或完整陳述已核驗。

獨立覆核找出的真實child PDF timeout誤啟MOPS fallback已修正：冷抓取與快取重播保持typed timeout並終止，API核對逾時回502、原快照保留。初始blocked收據及root 2失敗反例另存不覆寫；固定版1042相關、194獨立及2保存反例通過，重疊次數不相加。9owned／98preserved＝107runtime、env／158套件、正式程序與health／ready200、六queue0核對。6筆舊job依原30日terminal／保留最近20規則到期，既有failure／zero prefix／dispatch保持，無force kill、commit或push。

同一窗口實際僅法說success／attempt／HTTP各+2，parent aggregate明確HTTPfalse且排除，其餘19類逐欄不變；未seed cache或SLA，不將自然離窗算修復。原20類仍17類嚴格>80：法說33/43＝76.7442%、財報31/50＝62%、近期事件117/169＝69.2308%，全部達標目標尚未完成。原HTML／Markdown、quote／TTM／財報／新聞／社群、核心epoch、analysis evidence與五品質metadata保持，analysis_text_stale=True，未跑新全報告品質；news8／3／30、財報五年九事實及accepted typed sector、品質／quota／TTL／cooldown／deadline都保持。

見[正式補件](evidence/source-acquisition/20261012/txc3042-conference-one-formal-refresh-proof.json)、[當前驗證](evidence/source-acquisition/20261012/txc3042-conference-current-closeout.json)、[固定版覆核](evidence/source-acquisition/20261012/txc3042-conference-independent-fixed-review.json)、[原阻擋收據](evidence/source-acquisition/20261012/txc3042-conference-independent-review.json)。

另由web發現[官方財報目錄](https://www.txccorp.com/investor/financialinformation/financial-report/458/)展示2025四季合併及年度個體財報。僅列備援候選，原件下載／科目未資格驗證；3042當前財報已完整，沒有重複正式刷新。合併和個體不得混用，不能算財報修復或goal成功。見[目錄候選](evidence/source-acquisition/20261012/txc3042-additional-free-financial-entry-web-discovery.json)。

## 晶技3042：完整自結公告免費入口（2026-10-12）

[官網原生索引](https://www.txccorp.com/news/)實際列出[10/5營收公告](https://www.txccorp.com/news-detail/consolidated-revenue__47/)及[9/15自結損益公告](https://www.txccorp.com/news-detail/73__52/)；native完整340835／156563／158323 bytes，正文154／384字，發布日不同9月／8月內容期。完整TWSE主檔核對3042、台灣晶技股份有限公司、統編21204867、TXC及登記www.txccorp.com。第一個研究helper因dict回傳格式錯誤未保存body，原失敗保留；修正後保存3份原件，實際新聞研究總4 HTTP另立更正，不seed正式cache／SLA或模型。

9/15搜尋meta原有截字byte保留，不修補；正文、日期、身分及完整八列表格採用strict UTF8，兩層表頭、空YoY與註解保持，不算年度九事實／TTM。native頁沒有canonical／OG URL，只核原生copyLink的slashless文章身分、不追隨、不造新網址。4owned／100preserved＝104runtime部署完成；885相關、151獨立及5反例通過、不相加。

11:08一次真缺口補件HTTP200／2.6596秒／3 native HTTP，兩篇已保存，合格新聞7→9／8 publisher，通過原8／3／30；兩篇仍一個官網publisher、未驗證審計財報／事件影響／完整窗口。原正文與分析證據／五品質metadata／quote／TTM／財報／社群保持，analysis_text_stale=True，未重跑全報告品質。正式程序／env／158套件／health／ready200／queue0核對；5筆舊job原30日到期規則獨立明列，保留錯誤verifier與舊工作原件。原20類仍17嚴格>80：法說75.61%、財報62%、新聞69.23%。同窗新聞成功／attempt各+1，其餘19類不變，自然離窗不算修復貢獻；free／品質／五年九事實及typed sector／quota／TTL／cooldown保持，全goal未完成。見[資格](evidence/source-acquisition/20261012/txc3042-original-semantic-and-current-gap-qualification.json)、[正式補件](evidence/source-acquisition/20261012/txc3042-issuer-source-formal-refresh-proof.json)、[當前驗證](evidence/source-acquisition/20261012/txc3042-issuer-current-closeout.json)、[研究HTTP更正](evidence/source-acquisition/20261012/txc3042-native-request-accounting-correction.json)。

## 致茂2360：新完整免費官網新聞入口（2026-10-12）

[原生索引](https://www.chromaate.com/en/newsroom/news_list)與其列出的[2026-10-07文章](https://www.chromaate.com/en/newsroom/news1189)已匿名native HTTPS取得，完整112042／106891 bytes，正文4276字；標題、URL、索引／正文／JSONLD發布日一致。完整TWSE主檔綁定2360、致茂電子股份有限公司、統編09461025、CHROMA與登記www.chromaate.com，其他同名網域不採用。研究2個HTTP沒有seed正式cache／SLA或模型計數。

10:40已部署並一次正式補件HTTP200／2.0128秒／2 native HTTP，原文保存，全部舊新聞桶7則合格資料補至8則／7 publisher，通過原8／3／30。並非8篇完整原文或獨立確認，10/14–16參展仍是未來計畫，窗口partial。原HTML／Markdown／分析證據／五品質metadata／quote／TTM／財報／社群保持，analysis_text_stale=True，未重跑完整報告品質。Root849、獨立固定版40分開，P2原red保留並已關閉；4owned／99preserved＝103runtime、env／158套件／health／ready200／queue0核對。原20類仍17類嚴格>80：法說31/41=75.61%、財報32/51=62.75%、新聞116/168=69.05%。同窗僅新聞成功／attempt各+1，其餘19類相同，自然離窗不算修復功勞。品質／五年九事實／typed sector／TTL／quota／cooldown保持，全goal未完成，未commit/push。見[原件缺口資格](evidence/source-acquisition/20261012/chroma2360-original-semantic-and-current-gap-qualification.json)、[正式補件](evidence/source-acquisition/20261012/chroma2360-issuer-source-formal-refresh-proof.json)、[當前驗證](evidence/source-acquisition/20261012/chroma2360-issuer-current-closeout.json)。

目標仍是正式服務近 24 小時的 20 個資料來源類別，各自取得成功且非空的實際抓取率超過 80%。本頁只記錄新入口的實測範圍；沒有把可連線、空資料或部分文件當成完整取得。

## CMoney 新版公開個股討論頁

- 舊版個股頁不能從累積討論量證明有近況貼文；新版 [1605 華新個股討論頁](https://forum-web.cmoney.tw/stocks/1605)直接列出逐篇公開連結及 UTC 發文時間。[1605 逐篇貼文](https://www.cmoney.tw/forum/article/185070877)另有單一 `1605華新` 股票標籤、台灣時間、可讀正文；列表與逐篇時間一致。新入口的 `robots.txt` 允許公開頁，排除 `/api/`，因此只讀公開 HTML，不用內嵌 session、私有 API 或登入。
- 對近 24 小時正式來源紀錄中社群抓空的 13 檔逐一檢查，新版頁面只有 1605 的兩篇近期原生貼文符合嚴格篩選。2606 的近期貼文標記多檔股票並轉貼新聞；9945 的近期貼文同時標記加權指數與數檔股票；9904、6409、2851、2855、2206、1229、1319、2023、2912、1216 的頁面無可核對的 30 天內個股貼文。不能因為頁面 HTTP 200 或歷史貼文而算取得成功。
- `cmoney_stock_posts.py` 僅在既有 Dcard／Mobile01／PTT 搜尋及 PTT 直接入口均無合格樣本時備援；限定頁面股票代號、逐篇**唯一**股票標籤、索引／逐篇發文時間一致、30 天內、正文可讀且無外部轉貼連結。保留來源連結及標籤，`sentiment_assessment` 仍是 `not_assessed`，不推定情緒分數。現場直讀 1605 取得 2 篇，其他三檔 9945／2606／9904 為 0；215 項相關隔離測試通過。正式重載後強制抓取 1605，`social_sentiment` 確實保存 2 篇，但其他渠道有被剔除的結果，整體仍是 `degraded_enrichment`，面板依原嚴格規則不算成功。近 24 小時仍是 13/20 類別超過 80%，社群 62/250（24.8%）。
- [9904 寶成舊站「風向」頁](https://mobile.cmoney.tw/forum/stock/9904?tab=AISummary)雖顯示 10/08 對多篇貼文的摘要，公開頁沒有逐篇原文連結；「討論」頁的伺服器正文則顯示沒有討論。兩頁不能互相替代原始貼文驗證，沒有把平台 AI 摘要當成取得成功。
- 同時重查 6409、6282 的官方 2021–2025 年 iXBRL 文件，各篇約 0.58–0.90 MB、九個要求的事實欄位均可解析；先前「超過 6 MB 或含外部宣告」失敗不是持續的文件大小缺口，不能以放大下載限制當作修復。3023 的 2021 年原始及次年比較 XBRL 均缺「購置無形資產」明確事實；[公司公開的 2022／2021 合併現金流量表](https://sinbon.com/tw/files/2023_3023_20230530F02_20230901_140944.pdf)第 33 頁只列「其他無形資產減少」，並非取得無形資產金額，不能拿來填零或替代缺欄。

## 勞動部「台灣就業通」職缺資料

- [政府資料集 44062](https://data.gov.tw/dataset/44062)標為免費、政府資料開放授權條款第 1 版，包含公司名稱、職務名稱、雇用人數、更新日、截止日與職缺連結。[勞動部 OAS](https://apiservice.mol.gov.tw/OdService/doc/v3.json)的 `rest/datastore/{resourceID}` 支援欄位精確 `filters`、`limit` 與 `offset`。
- 2026-10-09 實測 `A17000000J-030144-VAL` 回應 `success=true`、`updateTime=20261009T010001`；完整下載回傳 1,000 列（資料集備註也說明單次最多 1,000 列）。用 `COMPNAME（公司名稱）` 精確篩選「年代網際事業股份有限公司」取得 28 列，證明查詢功能可用。
- 同法查「台灣積體電路製造股份有限公司」、「聯華電子股份有限公司」、「京元電子股份有限公司」、「統一綜合證券股份有限公司」、「世紀民生科技股份有限公司」、「旭隼科技股份有限公司」、「國泰金融控股股份有限公司」、「群創光電股份有限公司」、「台灣大哥大股份有限公司」、「德勝科技股份有限公司」，各回 0 列。這些空結果不能推定公司沒有徵才；資料集也沒有股票代號或統編可直接核對。此來源可在精確法定名稱且列內日期、連結皆合格時補個案職缺，不能當作現有 104/1111 的全面替代或提高上述股票的取得率。
- 另找到[臺北市就業服務處求職求才職缺資訊](https://data.gov.tw/dataset/135021)，欄位含公司名稱、職缺、活動時間，授權免費。但官方下載清單目前兩個 CSV 僅約 1.14 KB、2.19 KB，更新頻率標「不定期」；正式 Python 直接下載又遇到 HTTPS 憑證驗證錯誤。這是地方就業活動的窄資料集，沒有證據顯示能覆蓋近期股票樣本，暫不接入正式備援。

## 櫃買中心產業價值鏈的公司事件附件

- [櫃買中心產業價值鏈公司事件頁](https://ic.tpex.org.tw/company_list.php?stk=8048&stkName=%E5%BE%B7%E5%8B%9D&t=company_event)對 8048 德勝公開列出簡報附件。2026-10-09 從頁面連結實抓 PDF：HTTP 200、`application/pdf`、1,327,369 bytes、31 頁，首頁原生文字可讀到「德勝科技 RUBYTECH 法人說明會 2025年12月18日」。頁面的年份欄標 2026，但檔名和簡報首頁為 2025，不能直接拿列表年份當場次日期。
- 同頁型查 5314 世紀*僅有 2014 年指向公司網址的紀錄，沒有 PDF；查 3324 雙鴻的近期紀錄也沒有 PDF。這個入口可對有附件的上櫃個案補「簡報原文」，不能推定有逐字稿、完整影音內容或廣泛覆蓋。接入前需以官方股票主檔核對公司名稱，以 PDF 封面核對股票／公司與實際日期，保存原網址、內容雜湊、頁面文字覆蓋與無附件結果。

## 公開資訊觀測站官方鏡像的法說年度列表

- 舊 `mops.twse.com.tw` 查詢在正式 Python HTTPS 請求會被安全頁拒絕；官方 `mopsov.twse.com.tw` 的年度列表 `ajax_t100sb02_1` 與 `/nas/STR/` 原始 PDF 可正常取得，無需停用憑證驗證。[統一證券 2026-08-26 官方簡報](https://mopsov.twse.com.tw/nas/STR/285520260826M001.pdf)實際下載為 PDF，封面可核對公司及日期。
- 2026-10-09 對正式服務近期 23 個台股樣本查 `ajax_t100sb07_1` 最新場次，22 個有中文 PDF，但 2308 最新場次日期是未來的 2026-11-03，不能算已完成法說。年度列表另有 2308 已完成的 2026-07-30 場次及原始 PDF；因此正式 adapter 改以年度列表，按股票代號、場次日期及原始檔名精確核對，再過濾未來場次。此入口提供法說場次元資料與簡報連結，不等於逐字稿或完整影音內容。
- 本次接入範圍僅為 `earnings_call` 使用的官方 MOPS adapter。PDF 連結經過原站下載驗證；系統目前仍是保留連結，未把整份 PDF 文字解析成報告可引用全文。其他六個低於 80% 的類別不因這個入口而達標。
- 對 23 檔近期正式工作股票逐檔查年度列表（先 2026，若無場次再查 2025），23/23 有已完成場次，22/23 有官方簡報連結；1229 僅有場次而無簡報。這是來源端手動探測，不等於報告工作成功，亦不寫入 24 小時取得率。

## 證交所 OpenAPI 近期財報彙總

- [證交所 OpenAPI 定義](https://openapi.twse.com.tw/v1/swagger.json)提供上市公司一般業、金融業、證券期貨業、金控業等分類的損益表與資產負債表；[政府資料集 94831](https://data.gov.tw/dataset/94831)標示免費、政府資料開放授權條款第 1 版、每三個月更新。
- 2026-10-09 以正式 Python HTTPS 實測 `t187ap06_L_ci` 與 `t187ap07_L_ci`，均為 HTTP 200，分別有 1,049 列，含 6409 旭隼，年度 115、季別 2；`_L_bd` 均有 3 列，含 2855 統一證；`_L_fh` 均有 13 列，含 2882 國泰金。這是可按股票代號核對的免費官方近期季度交叉證據。
- API 本次只回傳最近一期，沒有五年連續年度歷史，也沒有現金流量表。現有 `financial_statements` 正式契約需五年歷史及自由現金流，不能把這份單季彙總算作完整年度財報；可先作季度數字交叉核對與部分資料來源，保留來源、期別與單位。
- 現有 `external_data_twse.py` 的 OpenAPI fallback 指向 `t187ap03_L`（官方規格標為「上市公司基本資料」）及不存在於規格的 `t187ap03_O`，未接到上述損益與資產負債資料。要接入時需分業別取 `t187ap06`／`t187ap07`，且不得把單季數值直接放進 TTM 或五年欄位。
- 近 24 小時 iXBRL 失敗紀錄中，6409 與 6282 有「超過 6 MB 或外部宣告」錯誤；重新抓取 2021–2025 文件，每份均小於 1 MB 且無 `DOCTYPE`／`ENTITY`，表明原錯誤可能是間歇性 HTTP 200 非 XBRL 頁。已讓原始下載將這類非 XML 回應視為可有限重試、且不觸發全來源熔斷；真正的 XBRL 仍經原本公司、期間、幣別及科目驗證。這只處理間歇性回應，不解決確實缺少的年報科目。
- 後續把這種驗證頁的第一次重試限於同一份年度文件：一般業、銀行／金控與證券商五年抓取不再因單一年度驗證頁立即重抓已成功的其他年份；同一文件最多重試一次，持續異常仍失敗。隔離測試分別通過一般業 20、金融業 9、證券商 7 項；正式服務重啟後，2855 與 6282 各自再次直接取得 2021–2025 五份官方文件。這些是 adapter 活網驗證，仍不是完整報告或 24 小時類別成功率。
- 2026-10-09 再檢查正式財報稽核，除驗證頁外還有 MOPS HTTP 502、連線錯誤及讀取逾時。舊的 `FilingTransportError` 不啟動外層重試，導致單一短暫失敗就放棄五年來源；因此把 HTTP 500／502／503／504 和短暫連線／讀取錯誤加入「同一份年度文件或索引最多再試一次」。403／429、缺科目、公司不符與持續錯誤仍失敗。隔離測試證明 2023 文件首次 502 後可恢復，2021、2022、2024、2025 不會重抓；已在空佇列下重載正式服務並恢復 worker。6409 的完整強制資料抓取再次得到官方 2021–2025 五份年報、五年自由現金流及一筆 `financial_statements` 成功稽核。活網本次沒有發生 502；短暫失敗的恢復能力僅由隔離注入測試證明。
- 另以原始文件逐年解析：2206、3023 的 2021 及 2022 年均缺 `PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities`。同期間的其他 `Intangible`、`Software`、`Acquisition`、`Purchase` 科目沒有等價的無形資產購置現金流；3023 的「出售無形資產收入」尤其不能替代購置。沒有明列值便不能填零或宣稱完整自由現金流。
- 正式服務重啟後，來源層直接抓取 2855 統一證的官方證券商 iXBRL，取得 2021–2025 五年、五份文件；6282 **康舒**的官方一般業 iXBRL 也取得 2021–2025 五年、五份文件（公司名稱依[證交所公司主檔](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)核對）。這驗證來源 adapter 可用，但直接探測未經完整報告工作，也沒有寫入正式 24 小時來源取得率。
- 2851 中再保在 [MOPS 年報索引](https://mopsov.twse.com.tw/mops/web/ajax_t203sb01)沒有 2021–2025 的 `report_id=C` 合併年報，但每年都有 `report_id=A` 個體年報。逐份原始 iXBRL 均有保險業營業收入、營業淨利、本期損益、資產、權益、營業現金流及兩項購置現金流，且同一發行人、年度與新臺幣單位可驗證。已加入獨立的 `insurer_individual.v1` 解析與提示詞投影；它標明個體範圍，不冒充合併資料，也不代填一般產業營收或毛利。來源層活網重新取得 2021–2025 五份文件，沒有比較年度修訂；正式服務完整抓取驗證見下方。

## 社群與新聞候選入口

- Yahoo 股市搜尋結果仍列出 RSS 說明頁，但 2026-10-09 從正式 Python HTTPS 直連 `https://tw.finance.yahoo.com/rss-index` 和 `/rss-help` 都回 HTTP 404；不能把搜尋索引視為仍可使用的 RSS 入口。舊說明也將免費使用範圍限於個人、非商業用途，未作正式服務備援。
- [CMoney 股市爆料同學會的 2855 個股頁](https://www.cmoney.tw/forum/stock/2855)在搜尋索引顯示累積討論量；直接 Python HTTPS 請求遇憑證驗證錯誤，但 macOS 系統 `curl` 啟用憑證驗證後實取 HTTP 200、約 1.07 MB HTML。頁面標題可核對股票代號，然而頁面可見正文寫「目前沒有任何討論」，且嵌入的其他股票貼文不可歸屬 2855；因此連線成功仍沒有可計入的近況社群樣本。頁內還嵌入會話資料，不以其權杖呼叫未公開接口；沒有逐篇股票、日期與公開使用邊界的證據前，不計為 `social_sentiment` 成功。
- 對近 24 小時 PTT 代號搜尋為空的 14 檔上市股，改查官方公司簡稱：2855 統一證、6409 旭隼、2606 裕民、2206 三陽工業等仍沒有近 30 天標題相符的貼文；2002 中鋼與 1101 台泥有可解析日期的近期文章。1605 華新的簡稱搜尋混入 2492 華新科，1216 統一也可能混淆集團公司，不能直接把簡稱命中當作股票歸屬。6282 康舒的搜尋列表雖有近期代號標題，文章頁卻沒有可驗證的發文時間，現行來源閘門正確拒絕。這些結果說明通用簡稱備援需嚴格身份與文章日期驗證，不能靠放寬比對把社群取得率灌高。

## 同業估值入口再核對

- [證交所 `BWIBBU_ALL`](https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL)與[櫃買中心個股本益比 API](https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis)均為免費官方入口，現有 `official_peer_valuation.py` 已接入。2026-10-09 來源層直接查 2851、2855、1229、2912、1605、5314、9945 七個近期同業指標失敗樣本，7/7 都有近七天可核對日期的 P/E 與 P/B；這不代表同業群已建立。
- 2851、2855、1229、2912、1605 在當日官方股票主檔有 16–32 個同大類候選；5314、9945 只有過於籠統的「其他」類別而不產生可比較候選。`dynamic_peer_metrics` 的失敗因此主要是同業身分、細產業可比性或候選指標完整性，不是缺少這兩項估值的免費數值。不可把目標股票自己的 P/E／P/B 當成同業資料，也不可將銀行、保險、證券商或「其他」大類直接視為業務可比。
- [證交所綜合損益表 OpenAPI](https://openapi.twse.com.tw/)另有依保險業 `t187ap06_L_ins`、證券期貨業 `t187ap06_L_bd`、銀行業 `t187ap06_L_basi`、金控業 `t187ap06_L_fh` 分列的免費名單。當日直接取得保險業五家公司（2816、2832、2850、2851、2852）及證券期貨業三家公司（含 2855）；這是比「金融保險」主檔更精確的官方候選身分。2851 中再保仍是該保險業名單中唯一再保險公司，其他公司不可僅憑同頁名單升格為業務可比同業。
- 直接執行 2851 的同業抓取，從 30 個同大類候選試取 10 個，10 個都有完整或部分數值，但十個的細產業全被判定不符（產險、銀行或證券商），正確選出 0 個可比同業。官方 2851 自身 P/E、P/B 可取得，不能拿自身值充當同業。這個案例的 `dynamic_peer_metrics` 低取得率是缺少合格比較對象，不是資料 API 失效。
- 5314 的 MoneyDJ 發布者食品生技名單仍可驗證 2026-10-08 的五個候選，但當日 Yahoo 個股頁把 5314 的現有產業列為 `Semiconductors`，五個候選則分別為食品、生技或藥品。故發布者同頁只作候選發現，不足以填入數值同業比較；需先釐清公司轉型與各候選業務，再決定哪些可比較。

## 其他候選的阻礙

- [統一證券官網法人說明會頁](https://www.pscnet.com.tw/pscnetAbout/menuContent.do?main_id=38c76fac5100000005f667edd9ab95b4&sub_id=38c77041ac000000057f9a2e44f27b9e)列有 2026 年 8 月簡報 PDF，但正式 `.venv` Python 3.13 的 HTTPS 驗證報 `Missing Subject Key Identifier`。已找到上節可驗證的公開資訊觀測站官方原始 PDF，可避開該官網的憑證問題；不關閉憑證驗證。
- [集保公司投資人關係整合平台法說活動列表](https://irplatform.tdcc.com.tw/ir/event/list?lang=zh&max=20&offset=17)可看到跨市場場次，部分有資料下載連結；其[服務條款](https://irplatform.tdcc.com.tw/ir/event/list?lang=zh&max=20&offset=17)對授權研究資料的重製、儲存、傳輸及衍生利用設有限制。未釐清場次／附件的可用授權前，不作正式自動擷取來源；且活動列表本身沒有法說全文。

## 正式服務驗收邊界

調查時 `/api/observability/provider-sla?window=last_24h` 為 20 類中 13 類高於 80%；未達標的類別是 `alternative_data` 13/49、`dynamic_peer_metrics` 50/74、`earnings_call` 20/47、`financial_statements` 38/126、`institutional_trading` 121/188、`recent_catalysts` 212/316、`social_sentiment` 52/208。正式服務重啟後，對 2308 執行一筆真實 MOPS 抓取，來源稽核記錄 `mops-conference-v3`、HTTP 200、`results`；`earnings_call` 變為 21/48（43.75%），20 類中仍只有 13 類高於 80%。其餘手動探測不計入正式成功率，舊觀測也不回寫；仍須觀察後續正式工作與 24 小時滑動窗口。

後續在正式 runtime 使用 `StockDataService.fetch_async(force_refresh=True, record_provider_sla=True)` 各抓取一次 2855 與 6409：2855 的官方金融業 iXBRL、法說、同業取得成功；6409 的官方一般業 iXBRL 成功，核心 `years` 與自由現金流均有 2021–2025 五年，法說與同業也成功。這兩次是真實完整資料抓取及來源稽核，但不是 AI 報告產出或品質通過。最新近 24 小時儀表板仍只有 13/20 類超過 80%；七個未達標率為職缺 15/51（29.4%）、同業 52/76（68.4%）、法說 25/52（48.1%）、財報 40/129（31.0%）、法人 133/200（66.5%）、近期事件 217/325（66.8%）、社群 52/214（24.3%）。

2851 的保險業個體財報接入後，在空佇列下重啟正式 `start_mac.command`，`/readyz` 顯示 storage 與 queue 均通過。完整強制資料抓取回傳 `insurer_individual.v1`、個體範圍、2021–2025 五年及五份原始文件；正式 `provider_sla_events` 記錄官方金融業 iXBRL `success`、五筆，訊息明示「保險業個體年報」。隔離測試含保險業、銀行／金控、證券商、一般業與財報稽核共 103 項通過。最新 24 小時來源儀表板仍是 13/20 類超過 80%：職缺 16/52（30.8%）、同業 52/77（67.5%）、法說 27/54（50.0%）、財報 41/132（31.1%）、法人 139/206（67.5%）、近期事件 218/330（66.1%）、社群 52/217（24.0%）。此結果只證明資料抓取與稽核，尚未證明 2851 的 AI 報告品質。

上述 MOPS 短暫錯誤重試接入後的最新近 24 小時正式儀表板仍為 **13/20** 類超過 80%：職缺 17/53（32.1%）、同業 53/78（67.9%）、法說 29/56（51.8%）、財報 42/133（31.6%）、法人 145/212（68.4%）、近期事件 221/334（66.2%）、社群 52/220（23.6%）。這是滑動窗口，含修正前歷史失敗；不能從單筆成功推論各類別達標。

## 104 雇主識別再驗證

- [證交所公開發行公司基本資料](https://data.gov.tw/dataset/28567)是免費、每日更新且明列「公司代號、公司名稱、公司簡稱、營利事業統一編號」的官方入口。2026-10-09 直接查現行 `t187ap03_L` 原始回應，1101 臺灣水泥確實有統編 `11913502`；同一正式服務的舊 `official-company-roster:v1` 共用快取卻回傳 `official_ubn=None`。將快取鍵升版後，重新抓官方主檔即可核對統編，沒有憑職缺網站自行宣稱股票身分。
- 104 近期職缺 JSON 對 1101 回傳 `custName=(台泥)臺灣水泥股份有限公司`、`custNo=11913502000`，原本只接受公司全名或後綴 `(台泥)`，因而漏掉前綴式別名。現在只在官方公司全名、官方簡稱、官方八碼統編與 104 雇主代號 `統編+000` 同時相符，且個別職缺有有效連結與近 30 天刊登日期時接受這種前綴；資料信任閘門也獨立重驗同一條件。沒有把台／臺模糊比對、集團公司或職缺搜尋總數當成發行人職缺。
- 來源層活網再查：1101 取得已查詢三頁中的 90 筆合格近期職缺，2206 三陽工業 10 筆、1229 聯華 13 筆；2002 中鋼仍沒有公司本體可核對職缺，維持未取得。304 個隔離測試加 75 個子測試通過；在五個佇列均無 queued／started／scheduled／deferred 工作後，保存 Redis 並重啟正式 `start_mac.command`，`/readyz` 的 storage、queue 均通過，worker 已恢復。1101 的一次完整強制資料抓取在正式 operational store 記錄 `alternative_data` 成功、90 筆及前綴識別依據；這是資料抓取，不是完整 AI 報告品質驗證。
- 該次正式抓取後，近 24 小時仍只有 **13/20** 類超過 80%。七類未達標依序為職缺 18/54（33.3%）、同業 54/79（68.4%）、法說 31/58（53.4%）、財報 43/134（32.1%）、法人 151/218（69.3%）、近期事件 224/338（66.3%）、社群 55/231（23.8%）；不可把來源層單筆成功解讀成整類已超過 80%。
- 再檢查近期失敗名單的 104 原始 JSON，2308 台達電在三個受限查詢分頁中以 `台達電子工業股份有限公司 _DELTA ELECTRONICS INC.` 刊登；其雇主代號 `34051920000` 與證交所官方統編 `34051920` 相符。新增僅接受「法定全名 + ` _` + 限長拉丁字元後綴」且統編對應雇主代號的比對規則，資料信任閘門重新驗證同樣條件；非拉丁子公司名稱及錯誤雇主代號仍拒絕。2308 來源層取得 90 筆近期職缺；6282 康舒、3023 信邦、2912 統一超也分別可直接核對 68、90、88 筆精確法定名稱職缺，但尚未替它們各自執行正式完整抓取。2002 中鋼與 2891 中信金在已查分頁沒有公司本體職缺，維持未取得。
- 補測後隔離測試為 305 個通過、75 個子測試通過；於所有六個 RQ 佇列均無 queued／started／scheduled／deferred 工作時再次保存 Redis 並重載正式服務，`/readyz` 仍為 storage、queue 通過且 worker 已恢復。2308 完整強制抓取在正式來源稽核記錄 `alternative_data` 成功、90 筆 104 職缺及拉丁後綴身分依據；資料信任計數 91 含另外 1 筆徵才新聞，不應將 91 誤寫為 104 職缺數。最新 24 小時看板仍是 **13/20** 類超過 80%，職缺僅 19/55（34.5%）；其餘未達標為同業 55/80（68.8%）、法說 33/60（55.0%）、財報 44/135（32.6%）、法人 157/224（70.1%）、近期事件 228/342（66.7%）、社群 57/234（24.4%）。
- 再查 2002 中鋼，原本一般關鍵字搜尋在前三頁找不到；第 8 頁才有一筆全名與統編代號相符的職缺。104 另一個免金鑰的公司職缺 JSON 入口以 `統編+000` 的 36 進位代碼作網址：中鋼官方統編 `30414175` 對應 `dyztbmg`。`/api/companies/dyztbmg/jobs` 第一頁列一筆；逐筆 `/job/ajax/content/965f7` 回傳同一公司代碼、法定全名、相同職稱與完整日期 `2026/09/23`。它是已驗證的近期職缺，不是搜尋結果總數；先前「中鋼未取得」的個案結論由本次更新取代。
- 正式程式只在既有 104 精確公司搜尋失敗、且官方公司主檔的統編收據可核對時啟用公司清單備援。清單第一頁至多查驗五筆詳情，逐筆檢查公司網址／代碼、法定名稱或已界定的別名、職稱、職缺 URL、完整日期與近 30 天範圍；回傳的是已驗證樣本數，絕非清單宣稱的完整總數。隔離回歸為 339 項及 75 個子測試通過；空佇列下保存 Redis 並重載正式服務，`/readyz` storage／queue 通過，worker 已恢復。2002 完整強制資料抓取在正式來源稽核記錄 `alternative_data` 成功、1 筆，資料信任計數也是 1。來源層另對 1101、2308 的公司清單各驗證五筆，但這不是它們新的正式完整抓取。
- 最新正式 24 小時仍只 **13/20** 類高於 80%，職缺 20/56（35.7%）；其他未達標為同業 56/81（69.1%）、法說 35/62（56.5%）、財報 45/136（33.1%）、法人 163/230（70.9%）、近期事件 231/346（66.8%）、社群 57/237（24.1%）。最近一小時的改善不能替代 24 小時驗收，且空社群資料仍不可算成功。

## 續查：PTT 原文時間與台灣就業通公司職缺

- PTT Stock 的 6282 康舒文章有公開原文、文章網址與搜尋索引 10/02，但缺標準 `article-metaline` 時間。`ptt-search-v3` 僅在文章網址的 epoch 日期、索引月日、原文平台自我連結及股票代號均一致時使用該日期；任一訊號缺失仍拒絕。正式服務重載後，6282 完整強制抓取留下 PTT Stock 1 筆、`parser_version=ptt-search-v3` 的來源事件；社群整體仍是部分取得。這篇與 PTTWeb 已有的貼文重複，不代表增加獨立討論量。
- [台灣就業通公司搜尋](https://job.taiwanjobs.gov.tw/internet/index/job_search_list.aspx)是另一個公開免費入口，與其[每次最多 1,000 筆的開放資料清單](https://data.gov.tw/dataset/44062)不同。以證交所公司主檔的全名與統編核對公司頁，3023 信邦與 9904 寶成的公開公司頁分別列 10 與 6 個職務；逐篇職缺明細直測各有 5 筆雇主、工作代碼、尚未過期截止日皆一致。另 2912 統一超、1605 華新、1216 統一亦可查到精確公司頁與同一統編；2206、1229、2851、2891、6214 等樣本未得到精確公司結果，不能算有職缺。
- 新備援只在 104 未取得合格公司職缺且官方全名、統編都有效時啟動；每次最多抽查 5 筆原文，不把公司頁總職務數或歷史刊登日當作已驗證數量。隔離回歸 182 項通過，來源直測 3023 與 9904 各通過 5 筆。正式服務在空佇列下重載、`/readyz` 通過；但對 3023 與 9904 的完整強制抓取，104 已先成功，故新備援沒有被正式流程啟動。這只能證明來源入口與隔離整合，不能宣稱正式備援成功率已提高。
- 最新近 24 小時看板仍是 **13/20** 類高於 80%；未達標依序為職缺 23/59（39.0%）、同業 59/84（70.2%）、法說 41/68（60.3%）、財報 47/140（33.6%）、法人 181/248（73.0%）、近期事件 242/358（67.6%）、社群 62/247（25.1%）。舊失敗仍在滑動視窗內；沒有近期職缺、事件或討論時，也不能以空回應灌成成功。

## 續查：證交所逐公司歷史公告原文

- [證交所投資資訊中心單一公司資訊揭露](https://wwwc.twse.com.tw/IIH2/zh/company/information.html?code=2855)的公開頁面使用 `GET /rwd/zh/IIH/company/events?code=2855`，回傳最近十筆公司重大訊息、財報公告及法說公告；每筆重大訊息有官方 MOPS 原文連結。這與目前已接入的 TWSE／TPEx「每日全市場快照」不同，可補當日以外的公告，但只有最近十筆，不能假裝是完整歷史資料庫。
- 2026-10-09 對 12 檔近期低取得的上市樣本直讀索引，11 檔有 30 天內逐公司公告；2851 中再保沒有。2855 統一證 2026-10-06 的「9 月份損益」及 1605 華新 2026-09-30 的「研發主管異動」原文均可直接讀取；索引與原文的公司代號、簡稱、發言日期時間、主旨一致，且原文「說明」非空。公告內容只是事件證據，沒有自動推斷利多、利空或情緒分數。
- 新 `twse_company_history.py` 最多查十筆索引及十篇原文，限定上市 `.TW`、官方 HTTPS 網域與路徑、公司代號、發言時間、30 天窗口及正文；如果最近十筆中的最舊公告已落在窗口外，且窗口內原文都核對，才標記該 30 天窗口可覆蓋。否則或任何正文遭截斷、身分／時間不符時維持部分取得。獨立 provider 的快取限時，正式流水線已接入 `recent_catalysts` 並保留原始 URL、正文雜湊與未評估的事件性質。直接來源測試：2855 與 1605 各成功 1 篇，2851 為未取得，5314 上櫃不適用；隔離回歸 98 項通過。這還不是正式 24 小時面板或報告品質的成功率證明。
- [櫃買中心市場重大訊息頁](https://www.tpex.org.tw/zh-tw/market-important.html)導向公開資訊觀測站的綜合查詢；搜尋結果中的舊 `info.tpex.org.tw/IIH` 逐公司頁在本機直連會轉往錯誤頁。另找到可用的[公開資訊觀測站歷史重大訊息](https://mopsov.twse.com.tw/mops/web/t05st01?co_id=5314&year=115&firstin=true&step=1)：以年度與公司代號取回上櫃公告列表，逐筆「詳細資料」可由公開頁給出的序號、發言日期時間與公司代號開啟官方原文；不需停用 HTTPS 憑證驗證。
- 新 `tpex_company_history.py` 限 `.TWO`、官方 MOPS 年度索引與原文、`TYPEK=otc`、公司代號、發言時間及主旨一致，最多查兩個年度與十篇近期原文。若 30 天內超過十篇或有身分／內容缺口，仍標示部分取得。來源層活網取得 5314 世紀* 2 篇、3324 雙鴻 3 篇，8048 德勝 30 天內為 0；兩檔取得者正文非空且窗口完整。新的上櫃 provider 已接入 `recent_catalysts`，隔離測試包含錯誤市場、錯誤發行人、過期與資料信任選擇。
- 另在 MOPS 財報適配器對 HTTP 200 卻夾帶 `DOCTYPE`／`ENTITY` 的 XML 安全頁作「同一年度文件最多再試一次」的封閉式恢復；持續回傳安全頁仍拒絕，沒有放寬原本解析的發行人、年份、幣別與必要財務欄位。6409／6282 一般業及 2851／2855 金融業來源層活網各取得 2021–2025 五份文件；曾失敗時的原始 HTTP 回應未留存，無法確認先前錯誤是否由這種安全頁造成。一般業與金融業合併回歸 50 項通過。
- 在六個正式 RQ 佇列均無 queued、started、scheduled、deferred 工作時，保存 Redis 並由 `start_mac.command` 重載；`/readyz` 的 storage／queue 均通過，worker 已恢復。正式 operational store 的完整強制資料抓取：2206 三陽工業新入口記錄 `success`、原文 3 篇、30 天窗口完整且 `http_request_sent=true`，3 篇都進入近期事件清單；2855 統一證因前一步直測已佔用共享快取，完整抓取記錄 `skipped_fresh_cache`，仍保留 1 篇已核對原文，不能另算當次 HTTP 成功。正式近 24 小時面板仍為 **13/20** 類超過 80%：職缺 26/62（41.9%）、同業 61/87（70.1%）、法說 47/74（63.5%）、財報 49/145（33.8%）、法人 199/266（74.8%）、近期事件 249/373（66.8%）、社群 62/256（24.2%）。新增來源增加了真實公告，也增加了總觀測分母；不能從單筆成功宣稱近期事件整類已達標。

## 續查：上櫃歷史公告正式驗證與剩餘缺口

- 對櫃買新 provider 的 47 項隔離回歸、`py_compile` 及 `git diff --check` 均通過。確認六個正式 RQ 佇列 queued／started／scheduled／deferred 均為 0，先暫停 worker 並保存 Redis，再重載 `start_mac.command`，恢復 worker；`/readyz` storage／queue 通過。3587 閎康的正式完整強制抓取記錄 `TPEx MOPS company announcement history` 為 `success`、2 篇原文、30 天窗口完整、`http_request_sent=true`、非快取；近期事件資料清單因既有容量限制收錄其中 1 篇，不能把來源兩篇誤記為最終清單兩篇。
- 重載後的正式近 24 小時看板仍為 **13/20** 類高於 80%。七類未達標為職缺 27/63（42.9%）、同業 61/88（69.3%）、法說 49/76（64.5%）、財報 50/146（34.2%）、法人 205/272（75.4%）、近期事件 253/378（66.9%）、社群 62/259（23.9%）。這是保留舊失敗的滑動窗口，也是各 provider 的觀測，不是唯一股票或報告成功率。
- 以正式觀測拆解缺口：社群 PTT 185 次中有 124 次空結果，跨站論壇 74 次有 45 次空結果、27 次降級；直接讀 CMoney 個股頁，3587、3023 近 30 天均無文章，2002 有兩篇，2855 頁未提供可核對公司簡稱且最新一篇已過期。無討論的股票無法用另一入口保證取得 80%，不能把搜尋命中數或舊貼文算近期樣本。財報官方 iXBRL 有 2021 必要欄位不完整、HTTP 502／連線錯誤與文件安全頁三種不同失敗；其中 2206、3023 的 2021 無形資產購置缺項，在已查核的官方報表亦未找到可證明數字，不能推成 0。法說與職缺同樣可能在指定窗口內確實沒有原始活動，需分別呈現真空缺與取得故障。
- 另檢查 [Mobile01 官方 RSS 說明](https://www.mobile01.com/rss.php)與[股票討論區](https://www.mobile01.com/topiclist.php?f=793)：公開頁有主題、發布與回覆時間，可作精確個股貼文的候選索引，但本機直接讀該股票分區回 `HTTP 403`，目前沒有可驗證的免登入來源層抓取，因此未接入正式社群 provider。Yahoo 股市舊 `rss-index` 公開搜尋結果在本機查為 404，也不列為可用入口。

## 續查：同業的公開承銷採樣依據

- 2026-10-09 近 1 小時正式觀測顯示職缺 7/7、法說 14/14、法人 42/42 均有非空成功；近 24 小時較低的比率仍含前一日舊失敗。其餘近 1 小時同業 5/7、財報 5/10、近期事件 22/32、社群 5/22，不能把前三類的近期改善套用到全部類別。
- [凱基證券汎銓承銷評估文件](https://www.kgi.com.tw/zh-tw/-/media/files/kgis/3_2_6_ipo/competitive-bidding/6830-3.pdf)將 3587 閎康與 3289 宜特列作材料／故障分析採樣同業；[國泰證券公開承銷文件](https://www.cathaysec.com.tw/RiskManage/4A80A899-F884-4399-8AC4-03BB77ACDFA0.pdf)又將 3587 與 6830 汎銓同列為半導體檢測採樣公司，並明示汎銓當時本益比偏高屬極端值。今日 FinMind 交易所公司主檔逐碼核對 3587、3289、6830 的名稱、上市／上櫃市場及細類別。這些歷史承銷樣本可作候選搜尋線索，仍不足以宣稱 2026 年兩家公司整體業務與所有估值倍數可直接比較。
- 另讀 [閎康 2026 年材料／故障分析服務](https://materialsanalysis.com/zh-TW/News_Release/detail/News/all/20260513)、[宜特 2026 年分析服務](https://www.istgroup.com/tw/activity_20261004/?cat=%E6%9C%80%E6%96%B0%E6%B6%88%E6%81%AF)與[汎銓 2026 年法說簡報](https://www.msscorps.com/rwd1520/store/F3/683020260416M001.pdf)，三家公司當前均仍涉及相關分析業務；但產品組合、收入權重、獲利期間及估值仍不同，不能僅憑服務重疊就放行整體倍數比較。
- 搜尋 5314 亦找到 2015 年承銷文件中的「世紀民生」同業採樣，但它距今太久且公司業務／名稱已變，未接入；2851 是專業再保險公司，不能直接拿一般銀行或產險公司湊成同業。
- 新 `official_underwriter_peer_cohort.py` 僅為 3587 提供上述具文件 URL／年份的兩檔候選；每日先用近期交易所主檔驗證代號、名稱、市場與類別，身分不符即不接入。候選標記 `business_comparability_verified_current=false`；取得的數值不進入自動同業估值中位數及報告比較表。隔離回歸 63 項、語法與 diff 檢查通過；正式服務於六佇列空閒時保存 Redis、重載、恢復 worker，`/readyz` 通過。3587 完整強制抓取的 `dynamic_peer_metrics` 稽核標記 `cache_hit=false`、成功取得 2 檔候選的可追溯數值；yfinance 自身內部快取未知，不宣稱每檔都發出新 HTTP。自動估值仍回「同業資料不足」，沒有拿汎銓約 2120 倍本益比替閎康定價。
- 本次正式抓取後近 24 小時仍只有 **13/20** 類高於 80%；七類為職缺 28/64（43.8%）、同業 62/89（69.7%）、法說 51/78（65.4%）、財報 51/147（34.7%）、法人 211/278（75.9%）、近期事件 256/382（67.0%）、社群 62/262（23.7%）。

## 續查：櫃買中心產業價值鏈的細分環節

- [櫃買中心產業價值鏈資訊平台](https://ic.tpex.org.tw/ic_report_index.php)可免費讀取逐公司所屬環節及同環節公司清單。2026-10-09 直接以正式 Python HTTPS 讀取 `company_chain.php?stk_code=1605`，HTTP 200、約 11.9 KB；頁面將華新列在鋼鐵多個環節（含「鋼線鋼纜」）、智慧電網「高／低壓輸電設施」及風力發電「電纜」，比交易所的單一大類更能反映跨業務。`introduce.php?ic=Q000` 的「鋼線鋼纜」節點列出華新、春雨、官田鋼、志聯、佳大、松和，且每家公司有股票代號連結。這些是可核對的**候選搜尋入口**，仍要逐家公司驗證當前產品與收入組合，不能把同節點直接當成估值可比同業。
- 同樣實測 `company_chain.php?stk_code=5314`，頁面仍將世紀*列為「建材營造 > 裝潢業」，同環節另列潤弘、匯僑設計、潤泰新及全譜；此分類未附觀測／更新日期，且世紀*業務已有變動。平台頁腳亦明示個別公司資料由公司輸入並自行負責。故**不把這份可能過期的分類接入自動同業倍數或宣稱取得率提升**。`2851` 只歸入合併的「金控業／銀行業／保險業」，無法據此找到再保險直接同業。
- 修正先前承銷候選的 `master_observed_at`：現在寫入交易所公司主檔的實際觀測日期；過期或身分不符回傳空候選，不再誤寫為今日。63 項隔離回歸、語法與差異檢查通過；在無待處理 RQ 工作時保存 Redis 並重載正式服務，`/readyz` storage／queue 通過、worker 已恢復。修正只改來源收據日期，不是新報告品質驗證；近 24 小時的 13/20 驗收狀態尚未突破。

## 續查：證交所財務比較站與公開留言

- [證交所財務比較 E 點通](https://mopsfin.twse.com.tw/)是免登入官方入口；[使用說明](https://mopsfin.twse.com.tw/terms)載明上市、上櫃財務資料自 2013 年起，資料庫每日更新一次。公開頁的 `POST /compare/report` 可按公司代號、年度第 4 季與三表類別讀取「合併」、新台幣仟元的原始列。實測 6409、6282 的 2021–2025 年三表各五份，營收、母公司業主淨利、毛利、營業利益、資產、母公司權益、營業現金流、設備支出與無形資產支出都有明確數值。3023 的 2021、2022、2023、2025 年現金流表沒有「取得無形資產」列，不能推成零。
- 此入口**不能直接代替完整 iXBRL 備援**：6409 的 2022 年資產，財務比較站及當年原始 XBRL 均為 NT$16,040,730,000，但 2023 年 XBRL 對 2022 年的比較列為 NT$16,085,375,000；6282 的 2022 年營收，財務比較站及當年原始 XBRL 均為 NT$25,321,167,000，而 2023 年 XBRL 比較列為 NT$24,789,577,000。現有五年 iXBRL 解析器會保留並採用後一年完整比較列，因此盲目以財務比較站回填會覆蓋可核對的較新比較數值。現在只在單一年度 iXBRL 經有限重試後仍遇暫時性文件錯誤時，才讀該年度比較站三表；較早年度還須有次年 XBRL 九項完整比較列，否則整份五年資料仍失敗。403、429、內容缺欄與身分錯誤不啟動此備援。逐份保存來源、請求期間與回應雜湊；一旦次年比較列不同，就記下修訂並採用較新值。隔離與實際來源驗證結果另見下方驗收紀錄。
- [Yahoo 閎康個股頁](https://tw.stock.yahoo.com/quote/3587.TWO/)的留言板在瀏覽器點開後可讀逐篇內容；實測顯示 48 個留言、最近一篇標「前天」，張貼需登入，但讀取免登入。直接 HTTP 取得的初始 HTML 沒有逐篇正文，頁面只顯示「前天／10 天前」等相對時間；目前沒有驗證到可供後端穩定抓取的公開原始時間與逐篇連結。因此它仍是社群入口線索，不計入 `social_sentiment` 取得，也不以留言總數替代近期逐篇證據。

## 單年度財報備援驗收

- `official_mopsfin_financial.py` 只讀一個發行人的一個年度，要求合併、股票代號、新台幣仟元及九項明確數值，缺項、重複列或正號支出皆退件。`official_xbrl_financial.py` 只在單份原件暫時性下載錯誤且已完成原文件局部重試後使用；不針對 403／429、原件本身缺科目或身分錯誤改走比較站。較早的備援年度還要求次年 XBRL 的九項完整比較列；若比較列與比較站當年原值不同，保留修訂紀錄並以比較列為準。
- 2026-10-09 現場強制模擬 2022 年原件安全頁，6409 與 6282 均只恢復該年度；6409 的 2022 年資產仍採 NT$16,085,375,000，6282 的 2022 年營收仍採 NT$24,789,577,000，沒有回退到比較站較舊的當年數值。來源稽核的 `filing_2022` 標示比較站 provider、三表回應雜湊及原本 iXBRL 下載錯誤。3023 的 2022 年比較站缺「取得無形資產」時仍失敗，不當作零。
- 相關 136 項隔離測試與語法檢查通過。正式服務於 RQ 佇列空閒時保存 Redis、重新由 `start_mac.command` 載入；`/readyz`、股票快照 API 與 Worker 均正常。這證明程式已進正式程序，**不代表已有自然發生的正式備援成功事件**。重新讀取近 24 小時面板仍為 13/20 類高於 80%；歷史失敗事件未改寫，財報為 51/147（34.7%）。

## 續查：法說原文及職缺候選（同日）

- 正式近 24 小時法說稽核曾有許多舊版 MOPS 安全頁失敗，新的官方 `mopsov.twse.com.tw` adapter 是獨立入口。對先前只得到 WebPro 部分資料的 12 檔直接查當年度官方 MOPS：1216、1229、1319、2023、2367、2606、2891、2912、3017、6214、9945 共 11 檔有已完成場次，3653 當年度空白；另外指定 2025 年可核對 3653 在 2025-11-28 的場次與中、英文簡報。這是來源層的當下結果，不會回寫舊失敗；是否讓正式 24 小時法說類別超過 80%，仍要等真實工作與窗口重新觀測。
- 官方 MOPS 簡報雖有連結，不能一律當作已讀到內容。實際下載三份當期中文 PDF 並以現有隔離 PDF parser 檢查：3587 閎康的 15 頁有原生文字且首頁寫 `MA-tek (3587) 2026/09/09`；2308 台達電檔案是加密 PDF；6409 旭隼檔案觸發 parser warning。若要將 MOPS 原文接入 `earnings_call`，只能對可完整解析且首頁身分、日期與索引吻合的單份文件採納，並標為簡報而非逐字稿；加密或解析警示仍維持連結／部分覆蓋。
- [鴻海官方法說列表](https://www.honhai.com/en-us/investor-relations/investor-relations-activities/investor-conference)直接列 2026-08-12 等場次的原始簡報和逐字稿 PDF；[光寶科官方法說頁](https://www.liteon.com/zh-tw/download/investor-conference)亦列簡報、影片與逐字稿。這是優先於第三方整理站的發行人原始內容入口，但目前僅核對站上揭露與個別公司覆蓋，沒有通用的跨公司逐字稿 feed，也沒有接入正式 provider。
- [集保 IR 平台公開活動頁](https://irplatform.tdcc.com.tw/ir/event/list?lang=zh&max=20&offset=16)有逐場公司代號、日期及部分 MOPS PDF 連結，可作活動發現與交叉核對；例如 2308 的 2026-11-03 是**未來場次**，不得算已完成法說。平台條款對授權研究數據的再利用有明確限制，因此仍以 MOPS 原件作正式內容來源。
- [臺北市公開職缺 CSV](https://data.gov.tw/dataset/135021)雖免費，實取資源只有五筆瓦城泰統職缺，活動日期均是 2022-06-02，無法補目前 30 天職缺；已排除，不接入。 [AlphaMemo 公開逐字稿頁](https://www.alphamemo.ai/free-transcripts)雖顯示部分逐字稿，其[服務條款](https://www.alphamemo.ai/terms)第 2.2 條明確禁止未經書面許可的自動造訪、複製、下載或重製，因此不作自動來源。
- [518 閎康公司頁](https://www.518.com.tw/company-ynlQXN.html)能核對公司全名，但現場頁面明列「所有工作機會共 0 筆」；同一家公司在其他徵才平台有沒有職缺需各自核對，這筆不能補成成功，也不能由空頁推論全網零職缺。

## 續查：官方便利商店同業候選與現行財報重試

- [櫃買中心 2912 產業鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=2912)及[5903 產業鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=5903)的逐公司頁均直接回 HTTP 200，分別列「2912 統一超」「5903 全家」，同屬「貿易百貨 > 零售通路」。[櫃買中心產業簡介](https://ic.tpex.org.tw/introduce.php?ic=V000)的便利商店段落也同時明列統一超商與全家便利商店。這個分類頁沒有資料更新日期，不能單憑同環節斷言兩家目前的整體業務、收入結構或估值倍數可比。
- [統一超官方公司資料](https://ir.7-11.com.tw/tw/companyprofile.php)列公司全名及「超級商店之經營」；[全家官方公司資料](https://www.family.com.tw/web_enterprise/page/information.aspx)列全名及股票代號 5903。再以 2026-10-09 交易所股票主檔核對 2912 上市「統一超」、5903 上櫃「全家」，建立僅限 2912→5903 的候選入口，保存四頁 SHA-256、官方 URL、主檔觀測日與抓取時間。網頁內容或當前股票身分不符時回空候選，舊的廣義搜尋仍可繼續。
- 直接來源層測試：`5903.TWO` 的七個 yfinance 欄位均有數值，同一個 2025-12-31 年度的營收／資產表可核對資產周轉率 1.3532；新候選在 2912 的 10 個下載上限內排在前面，最後 1 筆完整指標。但它的 `business_comparability_verified_current=false`，仍排除自動同業估值中位數與報告比較表。這是**單檔來源層**驗證，尚非正式 24 小時類別達標證明。
- 正式近 24 小時面板在本輪重載前仍只有 13/20 類高於 80%，同業 62/89（69.7%），財報 51/147（34.7%）。其中 2851 中再保與 2855 統一證的舊財報錯誤仍留在視窗，但當前官方 iXBRL 入口直接重試均成功取得 2021–2025 五年；前者明確標 `insurer_individual.v1`，後者是 `broker_consolidated.v1`，不可把兩種報表範圍混用。證交所、櫃買中心公開 OpenAPI 規格目前找不到完整年度現金流量表 feed；「法說會觀測站」頁面禁止未授權大量擷取，因此未接入。
- 新候選相關 67 項隔離回歸、語法與 diff 檢查通過。六佇列無 queued／started／scheduled／deferred 工作，Redis BGSAVE 成功後重載 `start_mac.command`；新 API 與 Worker 程序運作，`/readyz` 的 storage、queue 通過。尚未有重載後、2912 正式工作觸發的同業 provider 新觀測；不得把來源層完整指標直接寫成正式 24 小時突破 80%。
- 同一[櫃買中心鋼鐵產業鏈](https://ic.tpex.org.tw/introduce.php?ic=Q000)的「鋼線鋼纜」節點另列 1605 華新、2012 春雨、2017 官田鋼、2024 志聯、2033 佳大、5016 松和六檔；2026-10-09 交易所主檔逐碼名稱與上市／上櫃市場均相符。這是下一個較廣的免費**候選搜尋**入口；華新跨多個產業環節，其他五檔的 Yahoo 細產業標示為 `Steel`，與華新的 `Copper` 不同。沒有目前營收組合與產品比重的直接可比證據前，不把同節點候選當成自動估值同業，也不宣稱 1605 的正式來源成功率已恢復。

## 續查：華新鋼線鋼纜候選的有界接入

- [櫃買中心 1605 逐公司產業鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=1605)與[鋼鐵產業鏈「鋼線鋼纜」清單](https://ic.tpex.org.tw/introduce.php?ic=Q000)原始頁均直接 HTTP 200，兩頁交叉核對 1605 華新與 2024 志聯、2033 佳大、5016 松和的代號及簡稱；本日交易所股票主檔再核對上市／上櫃身分。新 adapter 只對 1605 產生這三檔候選，頁面變更、收據損壞或主檔過期就回空，並保存官方 URL、SHA-256、抓取時間與主檔觀測日。其他同節點公司暫不擴大，以免任意鋼鐵品類被視為整體同業。
- 來源層活網查到這三檔各有七項 Yahoo 財務／估值欄位，並可由同一 2025-12-31 年度的營收與資產算出資產周轉率；三檔皆 `metrics_status=complete`，1605 候選搜尋的 `coverage_status=success`。這是**候選自己的指標**，不是華新與它們的業務比重或全公司估值可比證明；全部標 `business_comparability_verified_current=false`。
- 同一標記現在同時由自動估值、報告同業比較表、財務提示資料與 AgentState 提示投影排除。完整候選及來源收據留在原始快照供人工查核，避免為了來源取得率讓 Agent 把約 44 倍、154 倍的候選本益比直接套到華新。相關同業／提示回歸共 244 項隔離測試通過；正式設定下 1605 一次完整強制資料抓取保留三筆候選與 `business_comparability_verified_current=false`，同業 provider 記錄成功。這不是自然報告工作或近 24 小時整類達標證明。

## 續查：發行人原始財報與公開個股討論入口

- [三陽工業 110 年合併財報原文](https://www.sanyang.com.tw/financial/system/investor/shareholders/2022/111-02.pdf)是發行人網站的公開 PDF，合併現金流量表在 PDF 第 29–30 頁（頁面標示 28–29）列 110 年營業及投資現金流、取得不動產廠房設備，沒有另列「取得無形資產」。[信邦 111 年年報原文](https://sinbon.com/tw/files/2023_3023_20230530F02_20230901_140944.pdf)的 110／111 年合併現金流量表在 PDF 第 33–34 頁（頁面標示 31–32），列「其他無形資產減少」110 年 22,673 仟元，這是現金流入／減少，不能代替無形資產購置現金流。兩份免費原件可做 issuer-hosted 交叉核對與 MOPS 傳輸失敗時的候選入口，但**不能補出 2206／3023 的缺失數值**；每家 URL 結構不同，尚無可驗證的通用自動入口，未接入 `financial_statements`。
- [TradingView 中鋼個股想法頁](https://tw.tradingview.com/symbols/TWSE-2002/ideas/)免登入可看到逐篇標題、作者及連結，屬另一個公開討論入口；實際列表沒有可核對的逐篇發布日期，索引頁亦可能保留多年舊想法。[同站中鋼 Minds 頁](https://tw.tradingview.com/symbols/TWSE-2002/minds/)當前明示「還沒有看法」。因此目前不能把它們作為 30 天 `social_sentiment` 成功樣本。[nStock 中鋼公司百科](https://www.nstock.tw/%E4%B8%AD%E9%8B%BC%E5%81%9A%E4%BB%80%E9%BA%BC.html)雖列 PTT 原文連結，但同頁新聞仍停在 2023 年，不能用頁面更新時間替那些貼文定日期。
- 2026-10-09 正式 `provider-acquisition.v1` 近 24 小時仍為 **13/20** 類嚴格高於 80%。未達標：職缺 29/65（44.6%）、同業 63/90（70.0%）、法說 68/96（70.8%）、財報 52/148（35.1%）、法人 227/294（77.2%）、近期事件 260/387（67.2%）、社群 62/265（23.4%）。這是逐 provider 的非空抓取觀測，不是獨立股票或報告成功率；本節只新增來源查核，沒有把空結果改算成功、沒有部署新 adapter。

## 續查：新聞與社群分流，避免重抓 PTT

- 正式觀測顯示 `PTT Stock` 同時被新聞瀑布與社群 provider 抓取；過去 24 小時 `recent_catalysts` 的 PTT 為 27/90 非空、63 次無資料或失敗，`social_sentiment` 另有獨立 PTT 觀測。使用者貼文不能單憑個股代號與日期當成公司事件原始證據。`ExternalDataClient` 現只把 Google News RSS 與 DuckDuckGo News 當新聞來源；PTT 原文仍由 `SocialSentimentProvider` 抓取及查驗，不再為每次新聞抓取重複請求。這是語義和成本修正，不會把空貼文改算成功。
- 先更新公開介面行為測試，舊程式有 4 個預期失敗；修正後新聞、社群與合併流程相關 **91 項**隔離測試通過。正式六佇列無 queued／started／scheduled／deferred，Redis BGSAVE 成功後由 `start_mac.command` 重載；`/readyz` 的 storage／queue 通過。正式設定下 6282 康舒完整強制抓取的同一 `fetch_id` 有 `social_sentiment` 的 `PTT Stock` 成功 1 筆，`recent_catalysts` 沒有 PTT provider 事件；Google News RSS、FinMind news、交易所公告及 Alternative Search 仍回傳資料。這是正式資料抓取驗證，尚非自然報告品質驗證。
- 該次抓取後近 24 小時驗收仍為 **13/20** 類高於 80%：職缺 30/66（45.5%）、同業 64/91（70.3%）、法說 70/98（71.4%）、財報 53/149（35.6%）、法人 233/300（77.7%）、近期事件 264/391（67.5%）、社群 63/267（23.6%）。舊 PTT 事件仍在滑動窗口，後續須看自然工作與時間窗更新後的實際率；不能只由這次改動推算整類已達標。

## 續查：放寬社群搜尋的來源適格性

- 用免金鑰 DuckDuckGo 文字搜尋測試 3587 閎康、2851 中再保、2002 中鋼的 PTT Stock 精確代碼／名稱結果；即使加一個月時間限制，前列原文仍是 2025、2024 或更早的舊文章，搜尋結果亦沒有可靠逐篇日期。它不能代替既有 PTT 原文時間與 30 天檢查，也不能補上述個股近期討論。
- 把 Dcard 查詢由公司名稱＋代號放寬為只用「中鋼」時，Google News RSS 從 1 筆增至 10 筆，現有通用公司／時間選擇器甚至會接受其中 3 筆；逐頁核對卻是[Dcard 中鋼主題彙整](https://www.dcard.tw/topics/%E4%B8%AD%E9%8B%BC?tab=latest)及國營、工作板的求職／轉職討論，而非股票投資原文。3587、2851、3023 的同類放寬查詢沒有新增合格原文。故不放寬正式社群查詢，也不把主題頁或就業討論算成投資情緒；後續若擴新社群入口，須驗證原始貼文網址、板別、正文、發文日期及股票身分。
- 讀取正式 `provider_sla_events` 近 24 小時 `social_sentiment` 的 `details_json.ticker`，有觀測的 27 檔中只有 **11 檔**至少一次 `success` 且 `record_count>0`；若連非空但 `degraded_enrichment` 也算入，只有 **14 檔**。這是去重後的股票覆蓋，不是看板的 63/267 provider 非空成功率；同檔重試不會增加股票數。現有免費入口在這批股票上的可查近期內容遠低於 80%，單靠放寬搜尋或把部分取得改標成功無法滿足驗收。
- 找到現行選擇器把 Dcard「中鋼的最新討論」主題頁當成個別社群貼文的錯誤：Google News RSS 連結仍是 `news.google.com` 包裝頁，其發佈時間不能證明原帖時間，主題列表本身亦非單篇原文。現在凡 Dcard／Mobile01／PTTweb 社群候選仍指向 Google News 包裝頁，或 Dcard `/topics/` 彙整頁，都以 `forum_original_unverified` 拒收並保留原件於來源封存；PTT Stock 直接原文不受影響。先重現失敗，再以隔離測試驗證選擇器、社群查詢、外部新聞與資料信任共 **129 項通過**。對 2002 來源層即時查詢，先前那一筆 Dcard 主題頁已不進樣本；當次五個渠道均無合格樣本，沒有把修正寫成取得率改善。
- 再查免金鑰海外社群：[Stocktwits 官方開源 MCP](https://github.com/stocktwits/stocktwits-mcp)宣稱公開 endpoint 可取逐篇時間、文字與情緒，但同一公司[開發者頁](https://api.stocktwits.com/developers)目前停止新應用註冊；本機正式 Python 直接向其程式所用的 `/api/2/streams/symbol/` 查 AAPL、TSM、2002、2002.TW，四次皆 HTTP 403 HTML，沒有任何可核對貼文或台股代號對應。現時不列為可部署免費入口，也不以第三方鏡像或公開程式宣稱的額度代替活網取得證據。
- 對 PTT 官方精確名稱搜尋，`中鋼` 近期只找到一篇 `[新聞]` 轉載標題，`台泥` 找到兩篇 `[新聞]`；`閎康`、`中再保` 均為空，`康舒` 才有一篇 `[標的]`。只用公司名稱搜尋會把新聞轉貼誤當投資討論，且簡稱可能混淆發行人，暫不擴大正式社群入口。CMoney 2002 個股列表的兩篇 30 天內文章逐頁驗證分別同時標記 2002/2014 與 2002/2014/2027，依單一股票歸屬閘門退件；列表有文章不等於有合格的中鋼獨立原文。
- 正式六個 RQ 佇列再次核對 queued／started／scheduled／deferred 均為 0，Redis BGSAVE 已完成且狀態 `ok`，重載 `start_mac.command` 後 API 與 `worker_main.py --role all` 正常，`/readyz` 的 storage／queue 通過。重新讀取正式近 24 小時 `provider-acquisition.v1`，仍只有 **13/20** 類嚴格高於 80%；七個缺口依序為職缺 30/66（45.5%）、同業 64/91（70.3%）、法說 70/98（71.4%）、財報 53/149（35.6%）、法人 233/300（77.7%）、近期事件 264/391（67.5%）、社群 63/269（23.4%）。API 快照請求成功，但命中既有資料快取，不能拿它宣稱重載後自然抓到新的社群原文。
- 近 1 小時窗口有 18/20 類顯示超過 80%，但 `annual_workforce` 在該小時沒有新抓取、無法評比，社群僅 4/12（33.3%）。這個短窗樣本不足以取代使用者指定的近 24 小時逐類驗收。

## 續查：直接論壇原文取代無效搜尋索引

- 前一輪已證實 Dcard／Mobile01／PTTweb 的 Google News RSS 包裝連結沒有原帖發文時間與逐篇網址，現行來源選擇器會全部退件。社群 provider 因此停止這三次無法產生合格證據的外部請求，保留三個空渠道欄位供既有快照相容；只查 PTT Stock 原文，無合格 PTT 時才查 CMoney 逐篇公開原文。舊快照再選取時仍拒收索引包裝頁。這減少每次社群抓取三個無效搜尋請求，且不把缺資料改成成功。
- [CMoney 2002 個股原始列表](https://forum-web.cmoney.tw/stocks/2002)在 30 天內有兩篇候選。其中 185107125 是附外部新聞連結的轉貼，繼續拒收；[185096463 原文](https://www.cmoney.tw/forum/article/185096463)雖同時貼三個股票標籤，但第一個標籤與首個標題是 `2002中鋼`，正文只明確談中鋼，不談另外兩個標籤股票，且列表／原文時間一致、正文可讀、無外部連結。因此新增嚴格多標籤歸屬分支：最多三個合格股票標籤、目標必須排第一、正文必須明示目標且不能提及其他標籤股票；其餘混談、多標籤指數、新聞轉貼仍退件。保留所有標籤與 `explicit_target_multitag_forum_post`，不推算情緒分數。2026-10-09 來源層實抓 2002 為 1 篇，2606、9945 為 0；1605 原有單一股票貼文仍為 2 篇。
- 先寫失敗行為測試，再修正；相關社群／來源／信任／合併 **185 項**隔離測試、語法及差異檢查通過。正式六佇列沒有 queued／started／scheduled／deferred 工作，Redis BGSAVE 成功後重載 `start_mac.command`；API 與 worker 運行，`/readyz` storage／queue 通過。正式設定的 2002 完整強制抓取 `cache_hit=false`，`social_sentiment` provider 稽核為 `success`、1 筆 CMoney 原文、0 筆拒收，保留原文 URL 與多標籤證據。這是單檔真實取得，不是 20 類整體達標。
- 再查有近期 CMoney 列表文章的 1101、2606、3653、9945：1101 的三篇是多股與指數混合，目標不是第一標籤；2606 三篇皆含外部新聞連結；3653 三篇為多股／指數混談且目標不是第一標籤；9945 三篇的正文均未明示公司。全部仍為 0，不能用列表貼文數換算取得率。正式近 24 小時看板目前仍為 **13/20** 類高於 80%；七個缺口為職缺 31/67（46.3%）、同業 65/92（70.7%）、法說 73/101（72.3%）、財報 54/150（36.0%）、法人 244/311（78.5%）、近期事件 268/395（67.8%）、社群 67/279（24.0%）。舊失敗仍留在滑動窗口；後續需觀察新流程的自然工作樣本，不能靠同檔反覆重試灌高比率。

## 續查：證交所三大法人官方鏡像入口

- 找到同一 T86 報表的第二個免費官方主機：[TWSE 主站](https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20261008&selectType=ALLBUT0999)與[TWSE 第二入口](https://wwwc.twse.com.tw/rwd/zh/fund/T86?response=json&date=20261008&selectType=ALLBUT0999)。2026-10-09 兩者直接 HTTPS 均回 HTTP 200、2026-10-08 共 1,325 家逐股原始資料，逐碼欄位值相同，僅列表排序不同。`IIH` 投資人頁雖有另一資料路徑，股數單位被四捨五入，不能當 T86 原始股數備援。
- `official_institutional_source.py` 現只在主站 timeout、傳輸錯誤或 5xx 時，於同日 8 秒預算內嘗試第二官方主機；403／429、日期不符、解析或欄位錯誤不繞過。沿用完整報表日期、公司代碼與三類法人股數的驗證；分別記錄主站失敗與鏡像結果、實際 URL、原始回應收據，不因主站暫時錯誤直接開來源冷卻。隔離回歸含主站逾時後恢復、403 不繞過、鏡像日期不符退件與整體法人取得流程，共 **73 項通過**；語法與差異檢查通過。
- 正式六個 RQ 佇列無 queued／started／scheduled／deferred 工作，Redis BGSAVE 狀態 `ok` 後重載 `start_mac.command`；API、`worker_main.py --role all` 運行，`/readyz` 的 storage／queue 均通過。本次活網是兩入口資料相等驗證，沒有自然發生主站逾時後切鏡像，因此不能宣稱正式 failover 已觸發。正式近 24 小時看板仍為 **13/20** 類嚴格高於 80%；七類未達標依序是職缺 31/67（46.3%）、同業 65/92（70.7%）、法說 73/101（72.3%）、財報 54/150（36.0%）、法人 244/311（78.5%）、近期事件 268/395（67.8%）、社群 67/279（24.0%）。

## 續查：聚財網公開股票標籤頁

- [聚財網最新討論](https://www.wearn.com/bbs/active.asp)與逐股[中鋼標籤頁](https://www.wearn.com/bbs/active_tag.asp?id=2002)可在免登入的公開 HTML 讀取逐篇連結、發文時間及股票標籤，是新社群候選入口；Python `requests` 在本機被連線重設，系統 `curl` 可正常 HTTPS 取得。這不是保證後端可穩定批次抓取的憑據。
- 活網抽查標籤 2002、2851、3587、3023、6409、2606、9945 的首頁：2002 近 30 天六篇皆標記 5–112 檔股票，2851 只有一篇 112 股綜合盤勢，3587、3023、9945 無近 30 天貼文，6409 兩篇為 67–71 股盤勢，2606 六篇最少也標記五股。標籤命中並非公司獨立討論，且部分文章需付費閱讀；目前沒有合格原文可補這批低覆蓋股票，因此不接入正式 `social_sentiment`，也不把標籤頁筆數當取得成功。

## 續查：Yahoo 個股留言的自動取得邊界

- [Yahoo 閎康個股頁](https://tw.stock.yahoo.com/quote/3587.TWO/)免登入展開留言後，瀏覽器載入回應確有逐篇 `messageId`、`createdAt`、正文及 `contextId`；原始頁 HTML 亦有股票專屬留言 context。直接 HTTPS 驗證七檔個股頁與對應回應均為 HTTP 200，其中 3587、2002、2851、6409、2606、9945 的最新十篇至少一篇落在 30 天內，3023 最新留言已是 2026-07-02。這證明此前「只有相對時間」的限制可以被克服，但不代表可作正式自動來源。
- [Yahoo 股市 robots.txt](https://tw.stock.yahoo.com/robots.txt)對 `User-agent: *` 明確列出 `Disallow: /_td-stock`、`Disallow: /*?bcmt=*` 及 `Disallow: /comments/`；留言回應正走 `/_td-stock`。故不把該內部留言 API、頁面留言參數或瀏覽器攔截方法接入正式批次抓取，也不以這七檔的人工查核數灌入 `social_sentiment` 取得率。仍需找允許批次讀取且有原始時間、正文與股票歸屬的免費入口。

## 續查：論壇留言與個股歸屬

- CMoney [裕民標籤頁](https://forum-web.cmoney.tw/stocks/2606)的近期候選文章實際是先以長榮為主標、再兼標其他航運股的新聞轉貼。免登入瀏覽器可展開其中一篇[原文下方留言](https://www.cmoney.tw/forum/article/184970522)；部分留言有日期與正文，但多數是泛論航運或原作者重貼報導。不能憑母文章標籤把全部留言算成裕民獨立討論。瀏覽器資料請求帶 `Authorization`、`X-Version` 等欄位；正式 Python `requests` 遇憑證鏈錯誤，系統 `curl` 在取得普通訪客 cookie 後無該授權／版本仍回 HTTP 400 `UnsupportedApiVersion`。不複製瀏覽器會話憑證到後端，故尚無穩定的免授權收據，不接入正式 provider。
- 正式近 1 小時面板為 18/20 類嚴格高於 80%，但 `annual_workforce` 該小時 0 次抓取而不可評比，社群 5/17（29.4%）；近 24 小時仍是 13/20。不能把小時視窗或瀏覽器可見的留言替代使用者指定的 24 小時正式驗收。

## 續查：官方年度現金流彙總與開放社群 API

- [公開資訊觀測站現金流量表](https://mopsov.twse.com.tw/mops/web/t163sb20)是另一個可免登入的官方入口；`ajax_t163sb20` 以市場、民國年度與季度查詢。正式機器直接查上市 `110` 年第 `04` 季及 `114` 年第 `04` 季都回 HTTP 200，分別約 516 KB、541 KB，能以公司代號找到 3023 信邦與 2206 三陽工業。2021 年彙總列的營業活動淨現金流量分別是新台幣 **1,345,496 千元**與 **1,444,612 千元**。但整份彙總頁只列營業、投資、籌資與期末現金等總額，完全沒有「取得無形資產」科目；不能用投資活動淨額冒充設備／無形資產支出，也不能因此補成五年自由現金流。可作年度現金流獨立交叉核對，對這兩檔的 2021 缺欄無完整修復作用。
- [Bluesky 官方 HTTP API 說明](https://bsky.network/docs/category/http-reference/)提供免登入讀取的 `app.bsky.feed.searchPosts`，逐篇資料含原始時間、正文與作者。正式機器讀 `api.bsky.app` 回 HTTP 200；`public.api.bsky.app` 在本機由 CDN 回 403。以公司名稱搜尋並核對近 30 天正文，`中鋼` 50 筆結果中有 11 筆精確名稱近期貼文、`信邦` 有 2 筆；抽樣主要是中央社新聞自動轉貼及盤勢清單，非獨立投資討論。`閎康`、`康舒` 的近期精確名稱貼文各為 0；`王道銀行` 大量命中日本流行文化梗、`統一超` 命中發票新聞。故此 API 是可連通的免費候選，現有樣本無法補足 `social_sentiment` 的投資討論覆蓋；不把媒體鏡像、公司名稱碰巧命中或頁面可連通記為社群成功。
- 再以最近 50 筆搜尋結果抽查 `裕民`、`潤泰新`、`寶成`、`旭隼`、`中再保`、`統一證`、`三陽工業`、`東陽`、`燁輝`、`聯華`、`台泥`、`國泰金` 共 12 個名稱；逐筆限 30 天且正文須含精確名稱後，仍沒有一篇可直接採信的原生個股投資討論。非空命中多為中央社／廣播新聞轉貼、日文同名企業與地震訊息，或公司名稱字串出現在無關內容。這個抽樣不是全站窮盡搜尋，但足以否定「接上 API 就能顯著補齊這批台股社群」的假設。
- 另用 [PTT 股票板搜尋](https://www.ptt.cc/bbs/Stock/search?q=%E7%9B%A4%E5%BE%8C%E9%96%92%E8%81%8A)找到 2026-10-08 盤中／盤後閒聊原文，兩篇均 HTTP 200、各約 1,490 則推文。以這批低覆蓋股票的 17 個代號及 17 個名稱逐則比對：盤後無代號命中，只有一則「華新科」而非華新；盤中亦無代號命中，只有一則含「華新」字樣，尚未證明指 1605 華新。推文雖可讀，對目前缺口的原始股票歸屬沒有明確增益，暫不接入高量逐推文抓取。
- [中央社官方 RSS 規範](https://www.cna.com.tw/about/rss.aspx)只同意個人或非營利組織的非商業使用，且只供標題、前言及連結；在正式系統的使用身分與授權未確認前，不把它接成新聞資料入口。[MoneyDJ robots.txt](https://www.moneydj.com/robots.txt)明示禁止 AI 相關用途及未經同意的資料探勘，亦不列為候選批次來源。
- 本輪未修改 provider 程式或重載正式服務。正式 24 小時視窗仍僅 **13/20** 類別嚴格高於 80%；新增入口的可連線與局部交叉資料，不能替代正式來源取得成功率。

## 續查：公開投資論壇與職缺網站的原文覆蓋

- [HiStock 哈拉版](https://histock.tw/talk/gtalk)與[嗨問答](https://histock.tw/question/default.aspx)在正式機器均可直接讀取，`robots.txt` 也未禁止這兩個公開路徑；但問答首頁的最新逐篇問題停在 **2020-03-10**。哈拉版現行首頁主要列講座與舊部落格連結，不能拿頁面尾端顯示的 2026-10-09 現在時間當貼文日期。此入口未提供可補目前低覆蓋股票的近期原文。
- [TradingView 中鋼交易想法](https://tw.tradingview.com/symbols/TWSE-2002/ideas/)可讀逐篇內容；點入前兩篇原文的 `<time datetime>` 分別為 **2024-10-04**、**2023-12-17**，非近 30 天。3587 閎康、2851 中再保、3023 信邦的相應想法路徑只回個股概要，未提供可核對的近期想法。搜尋列表排序及當前行情日期不能替代每篇發表日期，因此不接為社群備援。
- [盈再表公開討論區](https://stocks.ddns.net/Forum.aspx)於正式機器回 HTTP 200，`robots.txt` 只禁止管理路徑；討論頁可讀逐則作者、UTC 時間與正文。抽查近期[科技電子零件台股串](https://stocks.ddns.net/Forum/430/%E7%A7%91%E6%8A%80-%E9%9B%BB%E5%AD%90%E9%9B%B6%E4%BB%B6-%E5%8F%B0.aspx?goto=17644)，近 30 天主要談台達電、神基與川湖，沒有 1605、2002、3587、3023、6409、6282 或相應公司名稱；[金融保險台股串](https://stocks.ddns.net/Forum/259/%E9%87%91%E8%9E%8D-%E9%8A%80%E8%A1%8C-%E4%BF%9D%E9%9A%AA-%E8%AD%89%E5%88%B8-%E5%8F%B0.aspx?goto=16506)可見中再保討論，但最新落在 2026-06-15。這是連線與局部內容可用的候選，對當前社群缺口沒有已驗證的近期股票覆蓋；不把產業串或舊留言算作股票原文成功。
- [1111 中鋼公司頁](https://www.1111.com.tw/corp/50743241)雖有搜尋索引，正式 Python 直讀只回「背景驗證中／安全驗證失敗」頁，無逐筆職缺、雇主身分與刊登日期；現有 1111 搜尋稽核也記錄 `page_kind=challenge`。不以索引的「徵才中」或挑戰頁當成職缺取得。[Dcard 股票板](https://www.dcard.tw/f/stock)的直接搜尋頁與搜尋 API 在正式機器回 403；第三方鏡像亦不是 Dcard 原站收據。
- 再讀正式 `/api/observability/provider-sla?window=last_24h`，目前仍只有 **13/20** 類別高於 80%；`alternative_data` 31/67（46.3%）、`social_sentiment` 67/279（24.0%）。本節未變更 provider 或重啟正式服務；下一個新入口必須在低覆蓋股票上交出近期逐篇原文與可驗證股票歸屬，才有接入價值。

## 續查：第三方年度現金流欄位

- [ifa.ai 信邦「取得無形資產」](https://info.ifa.ai/tw-stock/3023/indicators/channel%2F65e8220c3de6e6ea157538b2)與[三陽工業同欄](https://info.ifa.ai/tw-stock/2206/indicators/channel%2F65e8220c3de6e6ea157538b2)在正式機器均回 HTTP 200，公開表格把 2021 年年度值列為 `0`。但兩家公司 2021 年官方 iXBRL 都沒有可對應的「取得無形資產」年度事實；ifa.ai 頁面沒有列出該數字的原始申報文件、科目映射或「缺值與真零」區別。信邦同頁的 2021 年上半年累計又列 `9,047` 千元，與年度 `0` 的關係未能由頁面驗證。此來源可作待核對的線索，不能把顯示的 `0` 當成官方確認的零支出，亦不能用它補齊五年自由現金流。

## 續查：發行人原文及免費搜尋入口

- [台達電官方法說頁](https://www.deltaww.com/zh-TW/investors/analyst-meeting)在 2026 年第二季場次直接列出[英文逐字稿 PDF](https://filecenter.deltaww.com/IR/download/calendar/2Q26_Transcript.pdf)。正式機器 HTTPS 下載為 HTTP 200、259,508 bytes、13 頁，`pypdf` 可擷取約 38,674 字，封面明列 2026-07-30 與台達電子，內文含具講者及時間戳的問答。這是比 MOPS 法說場次／簡報連結更完整、可追溯的**單一發行人**免費原文入口；英文稿首頁也明示依中文口述編製、可能有翻譯錯漏，涉及關鍵數值或措辭仍應與中文原音／官方簡報交叉核對。尚未接入正式 provider，不能由此宣稱整類 `earnings_call` 取得率上升。
- [國泰金官方法說簡報列表](https://www.cathayholdings.com/holdings/ir/financial_information/results_presentation)逐場提供 2026-08-28 第二季中英文 PDF 與 Webcast；可作 2882 的發行人原件候選，不等於已取得逐字稿。頁面需逐一驗證 PDF 內容、日期及公司身分後才可進 provider；目前 `Cathay Financial Holdings official IR` 稽核仍只列活動與資料連結、狀態為部分取得。兩個公司專屬入口沒有證據可廣泛覆蓋其他發行人。
- 再讀[三陽工業官方 2022／2021 合併財報](https://www.sanyang.com.tw/financial/system/investor/financialreport/2022/111Q4.pdf)的現金流量表（印刷第 8 與 8-1 頁，PDF 第 12／13 頁）：2021 年營業現金流為新台幣 1,444,612 千元，取得不動產、廠房及設備為 1,259,712 千元；表內沒有單列「取得無形資產」。該 PDF 為掃描頁，不能因為 OCR 未命中就判定真零；目視核對後仍無法把 2021 年自由現金流缺項補齊。
- [yes123 雇主公開頁](https://www.yes123.com.tw/wk_index/comp_info.asp?p_id=74002_24004006)的 `robots.txt` 沒有限制 `/wk_index/`，系統 `curl` 對三陽工業、統一證券、聯華食品、閎康四頁均取得 HTML；但四頁只有雇主介紹，沒有當前逐筆職缺、刊登日期及可驗證工作連結。搜尋索引或圖片的「徵才中」不足以當 `alternative_data` 的非空職缺證據。聯華食品另有官方人才網站，但其 `robots.txt` 為 `Disallow: /`，不列入批次備援。
- [GDELT DOC 2.0 官方搜尋 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)提供免金鑰新聞文章網址、標題與日期的候選入口；正式 Python 對「閎康」一週文章清單查詢兩次均得 HTTP 429，間隔超過 5 秒仍未恢復。回應要求每 5 秒至多一次，顯示共享出口或服務端額度目前不足以作可靠正式備援；沒有取得任何原始文章，因此未接入 `recent_catalysts`。
- 逐筆對照 `alternative_data` 同一 `fetch_id`：104 取得經驗證的個別職缺時，來源稽核為 `success` 並附 `verified_company_postings`；稍後的 `optional 外部來源已合併` 稽核為 `degraded_enrichment`，是合併後仍缺 1111 的覆蓋註記。現有取得率投影以訊息將後者歸為摘要，沒有把它當來源失敗；不能透過改標合併列來提高真實資料取得。當前正式近 24 小時仍是 **13/20** 類別嚴格高於 80%，七個缺口沒有因本節調查而達標。

## 續查：噗浪原文與短窗取得

- [Plurk 公開搜尋](https://www.plurk.com/search?q=%E5%8F%B0%E6%B3%A5)的站點 `robots.txt` 允許 `/search` 及公開貼文；免登入的網站搜尋回應可取得逐篇 ID、UTC 發文時間、作者及正文。對 1101 台泥找到[一篇 2026-09-29 的原生持股貼文](https://www.plurk.com/p/3j7n7j6dl3)：搜尋結果與原文頁的日期及「買了台泥的股票」文字一致，直接原文 HTTP 200。這是可以補單檔 PTT 空結果的候選，還不是已接入的來源。
- 對同批缺口查 `中再保` 0 篇、`閎康` 2 篇但為新聞轉貼、`康舒` 3 篇但為新聞連結或「健康舒服」字串碰巧命中、`信邦` 0 篇、`裕民` 4 篇中抽到的是員工職場抱怨；`中鋼` 前列則為多股自動掃描、新聞分段轉貼或「鋼之鍊金術師」。不能把關鍵字命中直接當成個股投資原文。
- 搜尋端連續少量查詢後回 HTTP 400 `{"code":"rate-limit-exceeded"}`，之後換搜尋詞仍持續受限。此入口目前只驗證一篇台泥原文，既無跨股票覆蓋，也沒有可供正式批次查詢的已驗證額度；暫不讓它對每份報告都觸發請求，避免把額度限制變成新的取得失敗。
- 查正式近 1 小時 `provider-acquisition.v1`：職缺、同業、法說、財報、法人及近期事件這六個缺口在該短窗各有非空成功樣本且顯示 100%，社群只有 4/12（33.3%）；有其他類別沒有足量新抓取，不能把 1 小時視窗當近 24 小時驗收。近 24 小時仍為 **13/20**，社群 67/279（24.0%）。`institutional_trading` 近 12 小時已為 229/261（87.7%），顯示先前失敗正在滑出視窗；社群仍是真正持續的覆蓋缺口。沒有變更正式 provider 或重啟服務。

## 續查：StockGo 原文索引與 Cake 公開職缺

- [StockGo 2206 個股頁](https://stockgo.tw/stock/2206/)可作 PTT 原文發現線索，但其 PTT 討論欄近期索引仍停在舊文；2851、2855、3587 等低覆蓋股票也沒有驗證到近 30 天獨立投資貼文。搜尋引擎把當前股價頁日期與歷史 PTT 討論並列，不能把股價更新日當貼文發表日。直接查[PTT 股票板](https://www.ptt.cc/bbs/Stock/search?q=2851)時，搜尋結果亦混有法人買賣超排行，股票只出現在長名單；這類表格不構成投資者對該股的獨立意見。
- 找到新的免費職缺候選 [Cake 精誠資訊公司頁](https://www.cake.me/companies/systex)：正式機器免登入取得 HTTP 200，頁面 `Organization` 結構化資料寫明「精誠資訊（台股代號 6214）」，公司頁列逐筆職缺連結。[客服工程師原文](https://www.cake.me/companies/systex/jobs/customer-support-engineer-v701)亦取得 HTTP 200，`JobPosting` 結構化資料含職名、雇主公司頁、`datePosted=2026-08-04` 及 `validThrough=2026-11-04`。抽查另四筆同公司原文，三筆 HTTP 200、`datePosted` 為 2026-08-05 或 08-26，另一筆 HTTP 429；原頁確有可追溯職缺，但這批刊登日已超過現行 30 天「近期刊登」規則，不能只因截止日尚未到就算近期新增職缺。
- [Cake 統一超商公司頁](https://www.cake.me/companies/7eleventw)也在免登入 HTTP 200 頁列逐筆工作連結；[iOS 工程師原文](https://www.cake.me/companies/7eleventw/jobs/senior-ios-app-engineer-at-7-eleven-uniopen)的雇主為統一超商、`datePosted=2026-05-27`、`validThrough=2026-11-29`，仍不符合 30 天刊登時效。[統一證券公司頁](https://www.cake.me/companies/pscnet-pscnetstock-index-do?locale=zh-TW)顯示職缺 0。Cake `/robots.txt` 沒有禁止公開公司／職缺路徑，但 `/jobs/` 搜尋頁直接回 Cloudflare 403，短時間查數篇原文後又出現 429；目前沒有穩定跨公司批次額度與近期合格樣本，不接入正式 provider，也不把搜尋摘要或有效截止日當成近期刊登日。
- 本輪只做來源端查核，沒有變更程式、稽核定義或正式服務。再次讀取正式近 24 小時取得投影，仍為 **13/20** 類高於 80%；職缺 31/67（46.3%）、同業 65/92（70.7%）、法說 73/101（72.3%）、財報 54/150（36.0%）、法人 244/311（78.5%）、近期事件 268/395（67.8%）、社群 67/279（24.0%）。這些數字包含尚未滑出視窗的舊失敗；新入口的手動探測不寫入正式驗收。

## 續查：近期討論原文與正式失敗時段

- [Mobile01 主動式 ETF 討論第 2 頁](https://www.mobile01.com/topicdetail.php?f=291&p=2&t=7302294)的公開搜尋索引列出 2026-09-25 一則「我開始慢慢買統一證」的投資者留言，若原站可驗證留言 ID、發表時間及正文，屬比純代號搜尋更有價值的單檔社群線索。但正式機器對文章及 `/robots.txt` 直連均得 HTTP 403 `Access Denied`，行動版主機亦同；目前無法由後端取得原站收據，更不能把搜尋摘要或第三方鏡像寫入正式來源。其他低覆蓋股的 Mobile01 搜尋結果仍以數月前的討論、長篇法人排行或非投資內容為主。
- 重新核對正式近 3 小時逐來源觀測：`recent_catalysts` 為 26/37，其中 PTT 的 6 筆失敗都發生在 2026-10-09 04:39 以前；新程式由正式 worker 於 05:16 載入，`ExternalDataClient` 現行新聞瀑布只調 Google News RSS 與 DuckDuckGo News。故這些 PTT 列是舊流程仍留在滑動視窗，不能當作新流程再次向 PTT 抓新聞的證據，也不應以改投影分母抹去歷史失敗。近 1 小時近期事件 4/4；社群仍只有 4/10。近 3 小時財報 7/10，失敗主因含 2206 的 2021 年官方原文確實缺必要的無形資產購置事實，以及 Yahoo SDK 來源的 HTTP／快取狀態未觀測，不能將部分財報或未知傳輸狀態升格為完整成功。
- 本輪只做原站可達性及正式事件時間線查核；沒有更動 provider 或重啟服務。正式近 24 小時仍是 **13/20** 類高於 80%，`social_sentiment` **67/279（24.0%）**。下個可接入入口仍須在低覆蓋股票上具備正式機器可重複讀取的原文、日期、股票歸屬與可承受的查詢額度。

## 續查：CMoney 個股概覽的原文入口

- 發現先前未覆蓋的 [CMoney 信邦個股概覽討論區](https://www.cmoney.tw/finance/3023/f00025)：免登入 HTML 含近期逐篇文章 ID 與直接原文連結，但列表只顯示「1天前」等相對時間。由列表導向[信邦原文 185184304](https://www.cmoney.tw/forum/article/185184304)可在原文頁核對 `article:published_time=2026-10-07T08:23:10+08:00`、唯一股票標籤 `3023信邦`、標題及正文；不以列表相對時間推定發文日期。公開 `robots.txt` 允許這些路徑。
- 同法抽查 3023、3587、2606、9945、1101、2851、6409、2002、5314、2206 十檔，正式來源程式的直接抓取各有 1–3 篇通過原文／時效／股票標籤檢查，合計 **18 篇、10/10 檔有來源層樣本**；其中 2002、5314 由既有論壇列表取得，其餘八檔由新個股概覽補到。多股排行、外部新聞連結、無正文貼文仍被拒收；`sentiment_assessment` 保持 `not_assessed`。後續通用公司歸屬閘門對 5314 的一篇短文仍判 `issuer_unverified`，不能算成正式社群非空成功。這是定向來源層樣本，不是 24 小時報告工作成功率的代表性估計。
- 已讓 CMoney 抓取在原論壇列表無合格貼文時查公開個股概覽，仍須到逐篇原文核對日期、首個精確股票標籤、正文及外連；兩個列表共用 **12 秒**預算，避免新增入口使缺資料工作長時間卡住。先寫失敗測試後修正，社群、來源選擇及信任相關 **124 項**隔離回歸通過；3023、3587、2851 在加上共用時限後再次活網取得 3、2、2 篇。
- 五個 RQ 佇列及 `llm.retry` 均沒有 queued／started／scheduled／deferred 工作，Redis BGSAVE 完成後用正式 `start_mac.command` 重載；新 API／worker 啟動，`/readyz` storage／queue 通過。完整 `force_refresh=True` 真實資料抓取：3023 社群 1 篇成功，但來自 PTT，不證明新入口；2851 社群 2 篇成功，均帶 `source_listing=https://www.cmoney.tw/finance/2851/f00025` 與各自原文網址，`cache_hit=false`、來源稽核 `success`。再次讀正式 24 小時面板仍只有 **13/20** 類嚴格高於 80%，社群升至 **70/283（24.7%）**；本次單檔成功不能外推至全系統達標。
- [PTT 2026-10-07 盤中閒聊](https://www.ptt.cc/bbs/Stock/M.1791333003.A.7A2.html)推文原文確有數則明確指向閎康的投資討論。進一步對近 30 天 42 篇盤中／盤後閒聊原文抽樣，閎康 14 次名稱命中，信邦及寶成各有 1 次可辨識推文；「華新」常撞上華新科、`2023` 常是年份，原始關鍵字筆數遠高於可歸屬個股筆數。這條高量推文抓取對少數股票有增益，但尚無證據顯示足以支撐全體社群 >80%，故未接入每份報告的同步路徑。
- 再查正式 2851 完整抓取，CMoney 已有兩篇合格原文，但原流程先送 PTT 搜尋，得到 20 篇過期標題候選與一次 `degraded_enrichment` 空結果觀測，接著 CMoney 才成功。將 `social_sentiment` 順序改為先查逐篇原文可驗證的 CMoney，僅其無合格紀錄時才查 PTT；並非修改稽核分母或把空結果算成功。先加入會失敗的呼叫順序測試，再修正；相關 **125 項**隔離回歸通過。六個 RQ 佇列清空且 Redis BGSAVE 狀態 `ok` 後再次用正式啟動器重載，API、worker 及健康檢查均正常。
- 重載後 2851 的完整 `force_refresh=True` 抓取為 `cache_hit=false`，社群 2 篇均來自 [CMoney 2851 個股概覽](https://www.cmoney.tw/finance/2851/f00025)，保留兩篇不同原文 URL、發文時間及 `single_stock_forum_post` 類型，`social_sentiment` 兩筆 aggregate 稽核均為 `success`；同一 `fetch_id` 沒有 PTT HTTP 空結果觀測。此次抓取總耗時約 13.6 秒，前一次同股約 19.1 秒，但外部來源耗時有波動，不能將 5.5 秒全歸因於順序修改。正式近 24 小時仍僅 **13/20** 類嚴格高於 80%，社群 **71/284（25.0%）**；近 1 小時社群 4/5（80.0%）也未嚴格超過門檻。
- 對近 24 小時社群零筆最多、尚未在上一輪抽查的 2855、1229、1319、2023、2912、2308、1216 七檔逐股重抓 CMoney；六檔即有來源層原文。2855 個股概覽首頁其實有五篇近期候選：前三篇依序為外部連結新聞轉貼、雙股未明指本股、其他股票為首標籤；[第四篇統一證原文](https://www.cmoney.tw/forum/article/185203210)是 2026-10-07 有原文時間、唯一 `2855統一證` 標籤及可讀正文的單股討論。原三篇候選上限使它漏收。個股概覽現在最多檢查五篇，仍最多收三篇並共用 12 秒時限；先有失敗測試，再修正，相關 **126 項**隔離回歸通過。2855 來源程式活網在約 4.5 秒取得該篇；六個 RQ 佇列無活動工作、Redis BGSAVE `ok` 後以正式啟動器重載，API／worker 正常。
- 2855 重載後的完整 `force_refresh=True` 抓取為 `cache_hit=false`、社群 `success` 1 篇，保留新個股概覽與該篇原文 URL，PTT 渠道為空且沒有額外 PTT HTTP 查詢。正式近 1 小時社群是 **5/6（83.3%）**，但樣本小且包含舊流程事件；使用者指定的近 24 小時仍僅 **13/20** 類超過 80%，社群 **72/285（25.3%）**。來源層抽樣及單檔完整抓取都不能取代自然工作 24 小時逐類驗收。

## 續查：不同股票的社群原文及官方免費資料限制

- 依近 24 小時社群來源失敗最多、且前次未抽查的股票挑選 1605、9904、3653、6282、2882、2891、2367。已接入的 CMoney 原文入口在這七檔各取得 1–3 篇符合逐篇日期、股票標籤與正文檢查的貼文，來源層 **7/7**；這是定向樣本，不能外推成全體股票成功率。再以正式 `StockDataService.fetch(force_refresh=True, record_provider_sla=True)` 完整抓取 1605、9904，兩者 `_cache_hit=false`，`social_sentiment` 各有 2、1 篇保留原文網址的紀錄，來源稽核 `success`，表示通用公司歸屬閘門也接受這兩檔；沒有因本節修改 provider 程式或重啟服務。
- [勞動部台灣就業通網站職缺清單](https://data.gov.tw/dataset/44062)是免費 JSON/CSV 入口，含公司名稱、職缺原文 URL、更新日及截止日。然而官方說明每次最多 1,000 筆；實際 JSON 回應恰為 1,000 筆，抽查統一證券、中再保、信邦、台泥、精誠等十個公司名均無匹配。它不支援按公司完整取回全站職缺，不能取代已接入、會核對雇主身分與開放中職缺的台灣就業通公司頁。Python `requests` 對 `apiservice.mol.gov.tw` 的目前憑證鏈報 `Missing Subject Key Identifier`，雖然系統 `curl` 驗證成功；不能為了接入而關閉 TLS 檢查。
- [證交所重大訊息 OpenAPI](https://openapi.twse.com.tw/v1/opendata/t187ap04_L)目前回 116 筆當日快照，抽查 2851、2855、3023 都沒有當日列；系統 `official_disclosures` 已接這個端點並保留當日快照的限制。它不是補近 30 日歷史新聞的另一個入口。保險業損益 [OpenAPI](https://openapi.twse.com.tw/v1/opendata/t187ap06_X_ins)目前 17 筆當期列、無 2851；也不是五年年報替代品。
- 找到[三陽工業官方 2022／2021 合併財報 PDF](https://www.sanyang.com.tw/financial/system/investor/financialreport/2022/111Q4.pdf)與[信邦電子官方 2022／2021 合併財報 PDF](https://sinbon.com/tw/files/2023_3023_20230530F02_20230901_140944.pdf)。人工查原始現金流量表：三陽 2021 投資活動沒有獨立「取得無形資產」項；信邦的 2021 比較欄是「其他無形資產減少」正值，不等同無形資產購置流出。這些正式 PDF 可作缺值診斷原文，但**沒有**提供現有五年自由現金流計算缺少的明確同口徑購置值；不可把缺項補成 0 或改列五年完整成功。
- 本節完成後讀正式 `/api/observability/provider-sla?window=last_24h`，嚴格高於 80% 已變成 **14/20**；法人資料 268/335 正好 80.0% 時尚未達標，稍後舊失敗離窗後才越過門檻。六個仍未達標：職缺 37/73（50.7%）、同業 69/98（70.4%）、法說 85/113（75.2%）、五年財報 59/162（36.4%）、近期事件 285/421（67.7%）、社群 74/287（25.8%）。近 1 小時社群 7/8（87.5%），但這兩筆手動完整抓取屬定向驗證，仍須觀察自然工作進入完整 24 小時窗；`/readyz` storage／queue 通過。
- 中再保 2851 的台灣同業候選會因現行細產業核對被拒。找到免費可讀的海外再保險公司公開原文：[RenaissanceRe 2025 年報](https://investor.renre.com/reports-filings/sec-filings/content/0001140361-26-010190/0001140361-26-010190.pdf)、[Hannover Re 2025 年報](https://www.hannover-re.com/en/investors/results-and-reports/annual-report)、[Munich Re 2025 年報](https://www.munichre.com/en/company/investors/reports-and-presentations/annual-report.item-25aee387f438d61e0e9115a79623698d.html)、[Swiss Re 2025 年報](https://www.swissre.com/investors/annual-report-2025.html)。現行免費 Yahoo SDK 對 `RNR`、`HNR1.DE`、`MUV2.DE`、`SREN.SW` 實測均回 `EQUITY`、`Insurance - Reinsurance` 及 P/E、P/B、ROE 等非空欄位，具有同業候選價值。但 SDK 指標未附可核對財報期間，跨國會計、幣別、產品組合亦不同；當時先列候選，後續接入與正式驗證見下節。
- [公開資訊觀測站歷史重大訊息頁](https://mops.twse.com.tw/mops/web/t05st01)理論上可依公司與期間查詢，但本機對 2851 的一般直連查詢只得到「FOR SECURITY REASONS」頁，不是公告正文；未用它替代既有可查原文的證交所個股歷史入口，也未繞過站點安全措施。

## 續作：中再保跨市場再保險同業候選

- 現行官方台股產業主檔為 2851 找到 30 個廣義「金融保險」候選，但代碼優先順序使前十個多為銀行；細產業核對全部退件。僅對 `2851.TW` 且目標細產業恰為 `Insurance - Reinsurance` 時，將四家有公司年報線索的海外再保險公司排在廣義台股候選前。每次仍核對 Yahoo SDK 回覆的完整 ticker、`EQUITY` 及相同細產業；缺少身分收據、產業不符或下載失敗者不進可用同業列。每列另附官方公司年報連結、`cross_market_reinsurance` 範圍與 `financial_period_unverified`、`cross_market_accounting_and_currency` 限制；不把跨國指標冒稱同期間可直接比較。
- 先新增會失敗的行為測試，確認廣義銀行不會擠掉具體再保險候選，以及海外股票無 ticker 收據時必須退件；修正後八組同業相關隔離測試 **44 passed**。來源程式活網：十次候選下載中四家海外再保險公司通過股票身分、細產業及非空指標核對，六家廣義國內候選因業務不符退件；P/E、P/B、ROE 均非空，但財報期間仍未知。
- 六個 RQ 佇列皆無 queued／started／scheduled／deferred 工作時，透過正式 `start_mac.command` 重載 API 與 worker。再用 `StockDataService.fetch(force_refresh=True, record_provider_sla=True)` 完整抓取 2851：`cache_hit=false`，`dynamic_peer_metrics` 有 `RNR`、`HNR1.DE`、`MUV2.DE`、`SREN.SW` 四筆，每筆留有跨市場限制，來源稽核兩筆 aggregate 均為 `success`、`record_count=4`；`/readyz` storage／queue 通過。正式近 24 小時同業取得率僅從 69/98 變成 **70/99（70.7%）**，整體仍 **14/20** 類嚴格超過 80%；單檔成功無法代表全部股票或報告品質。

## 續找：證交所／櫃買中心年度 ESG 營運資料

- [證交所 OpenAPI 規格](https://openapi.twse.com.tw/v1/swagger.json)公開年度「[投資人溝通](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_7)」及「[職業安全衛生](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_21)」彙總；櫃買中心提供同型的[投資人溝通](https://www.tpex.org.tw/openapi/v1/t187ap46_O_7)與[職業安全衛生](https://www.tpex.org.tw/openapi/v1/t187ap46_O_21)端點。2026-10-09 用正式 Python、維持 TLS 驗證直接讀取四個 JSON：上市端各 1,077 列，上櫃端各 887 列。以正式近 24 小時職缺來源紀錄涉及的 24 檔台股代號抽樣，四端合併後兩種資料都找到 **24/24** 個同代號、報告年度 114（2025）的列；上市端出表日期 1151009，上櫃端 1151008。此為來源探測，不是 24 小時工作成功率。
- 投資人溝通端點明列「公司年度召開法說會次數(次)」，例：2851 中再保 4 次、2855 統一證 4 次、3023 信邦 1 次、3587 閎康 7 次、5314 世紀* 6 次。這是**前一年度總次數**，不能推出最近一次法說的日期、簡報或逐字內容；目前 `earnings_call` 使用的 MOPS 場次／PDF 仍須獨立核對。它適合做年度完整性比對，不能將一列年度統計當作近期法說取得成功。
- 職業安全衛生端點有「職業災害人數及比率」與火災件數等明列指標；抽樣 24/24 的職災人數欄均非 `N/A`。零是公司申報數值，但仍需標明年度、發行人及欄位；不能把它當成即時徵才、社群情緒、新聞事件或投資結論的直接證據。這是一個**尚未接入**的獨立營運風險候選資料源，不應為衝高既有 `alternative_data` 取得率而混入職缺契約。
- 同組官方 API 的[供應鏈管理](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_13)、[產品生命週期](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_14)與[資訊安全](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_16)也可讀取，但在 24 檔樣本中，上市端按代號且關鍵欄非 `N/A` 分別只有 8、11、15 檔；上櫃端供應鏈的 3587 有 290 家受稽核供應商，5314 無該列，產品生命週期兩檔均無列。這些欄位有產業適用性與揭露缺口，不能一律算資料成功。既有「年度人力揭露」已使用同組 `_L_5`／`_O_5`，不是新入口。
- 本輪只記錄來源實測與用途界線，**未修改 provider 或重載正式服務**。五年財報的 2206／3023 明確缺科目、社群無近期原文及職缺無當前可核對職位，均不因年度 ESG 列而補齊。正式 24 小時 20 類來源仍須各自嚴格超過 80% 驗收。

## 續查：近期事件與金融業財報的持續缺口

- 正式 `/api/observability/provider-sla?window=last_1h` 於 2026-10-09 約 06:45（台灣時間）顯示：同業 5/7（71.4%）、五年財報 6/15（40.0%）、近期事件 18/31（58.1%）；24 小時仍是 14/20 類超過 80%。同業的兩筆 2851 失敗均發生於 06:15／06:18，早於 06:37 跨市場再保候選重載；重載後 06:38 的完整抓取為 4 筆同業成功。不能將舊失敗誤判成新候選已回歸失效。
- 直接在免費搜尋流程重播 2851：原始 21 筆、合格 6 筆，6 筆 `unknown_date` 分別為兩篇富果歷史法說（網址日期 2026-09-04／2026-03-27，均早於 30 天）、玩股網／鉅亨網／Yahoo／CMoney 靜態個股頁。2855 的 9 筆 `unknown_date` 包含其他發行人（1216、2454、6274、9907）的富果法說、舊旺得富法說及靜態個股頁；即使擷取頁內日期也不能升格為近期 2855 事件。缺日期退件目前是必要的，不應從網址或搜尋排名猜日期。
- 免費新聞 waterfall 直接重播 2851 得原始 7 筆、合格 6 筆，唯一退件是沒有可核對中再保身分的泛台股標題；2855 原始 11 筆、合格 7 筆，四筆退件亦為未明確歸屬統一證的泛市場標題。替代搜尋對兩股仍分別補到 waterfall 前五筆之外 1、2 條不同連結，故直接停止替代搜尋會丟失合格來源，不能只靠縮減觀測次數改善面板。
- 正式快取中 2851 的官方五年 `insurer_individual.v1` 確有 2021 本期損益與自由現金流；一般欄位的 2021 淨利和自由現金流仍為 `None`，但 Yahoo／FinMind 路徑另補一般欄位並提供其他年份。2855 的官方五年 `broker_consolidated.v1` 與 Yahoo 四年一般營收值口徑不同。現行提取器在官方專用年報成功後仍抓 Yahoo／FinMind，因此產生降級來源觀測；直接略過會失去一般欄位及衍生計算，且不能把保險或證券商收入無標註代填一般產業營收。下一個實作切口應是有範圍／科目標籤的共同欄位對齊，並先驗證報告的衍生比率與來源門檻，再考慮減少真正冗餘的備援呼叫。

## 續找：官方法說影音與政府營運事件入口

- [證交所 WebPro 影音傳播網](https://webpro.twse.com.tw/WebPortal/)的「法人說明會」分類 `101` 是既有 adapter 僅查的 `170`／`148` 之外另一個免費公開入口。[2851 中再保 2026-09-04 法說原頁](https://webpro.twse.com.tw/WebPortal/vod/101/83646AF21158-5C1E0729-A839-11F1-96AA/?categoryId=101)顯示公司代碼、日期、摘要與原始影片；直接讀其公開 HLS 播放清單為 HTTP 200、`application/vnd.apple.mpegurl`。這是可連結的**實際影音**，比只有索引日期的 WebPro 備援有更多原始內容；目前沒有逐字稿或自動驗證的影片語句，不能憑摘要臆造管理層說法。2851 此場次距 2026-10-09 已超過 30 天，亦不能作近期事件。
- 用站方公開分類查詢對 23 個近期來源缺口代號作有限抽樣：分類 `101` 的 2026 年場次只見 2851（09-04）與 9945（07-02）；3023 最近為 2025-11-04，其餘樣本查無場次或只返回舊片。代號 `2023` 查詢甚至回傳其他股票，必須逐列以 `agentUserName`／原頁 `companyCode` 核對，不能以搜尋命中算取得。這個入口適合補個案法說**原始影音連結**，抽樣證據不足以支撐全類別 `earnings_call` 超過 80%。
- [櫃買中心「法人說明會／業績發表會」](https://www.tpex.org.tw/zh-tw/about/company/media/investor-conference.html)公開依股票代碼查詢的 `News/mediaList` 列表，2026-04-09 至 10-09 無代號篩選時有 50 場並附 Vimeo／YouTube 原頁；[公司自辦法說](https://www.tpex.org.tw/zh-tw/about/company/media/investor-conference-company.html)同期間僅 1 場（4126）。對 3587、5314、8048、3653、6282、3324 等本次樣本代號逐股查兩類，均為 0 場；不能用整體 50 場推定缺口股票已有資料。該頁是可用的窄場次入口，尚未證明能提高目前來源取得率。
- 另查[經濟部上市櫃公司對外投資事業名錄](https://data.gov.tw/dataset/7076)，官方標示免費、按年更新且有統編與核准日期，可作歷史海外投資背景；實際下載資源在本機 HTTP 403，且年度核准紀錄不是近 30 天新聞、職缺或社群。[公共工程委員會巨額採購廠商名單](https://data.gov.tw/dataset/7264)標示每日更新且有廠商代碼，但所列原始 XML 資源實際導向錯誤頁，無法當成穩定新入口。兩者均未接入正式資料流程。
- 本輪只作官方來源探測並記錄結果，未改 provider、稽核分母或重載服務。2026-10-09 06:53（台灣時間）正式 24 小時面板仍為 **14/20** 類嚴格高於 80%；六個未達標為職缺 38/74（51.4%）、同業 70/99（70.7%）、法說 87/115（75.7%）、財報 60/165（36.4%）、近期事件 286/426（67.1%）、社群 75/288（26.0%）。

## 續找：公告快易查的完整 30 天個股索引

- [證交所公告快易查](https://mopsov.twse.com.tw/mops/web/ezsearch)公開按公司代號與日期查詢重大訊息，原頁具有公司代號、發言日期時間、主旨及說明。既有 `IIH/company/events` 只回最近十筆；對 2882、2317、2308 抽樣，30 天公告快易查分別有 15、18、11 筆重大訊息，舊索引僅 10、10、9 筆可核對。2855、2206、3023 的近期重大訊息與舊來源相同，不能把重複結果算新來源增益。
- 新備援只在上市公司最近十筆索引無法覆蓋 30 天時查詢公告快易查；查詢必須按精確公司代號與日期返回不足 1,000 列，重大訊息候選最多 30 篇，索引市場別須為「上市」，逐篇核對官方 HTTPS 原頁的公司、主旨、發言日期時間與正文。索引不一致、拒收列、超出上限或原文缺失時保留 `partial`，不把部分覆蓋升格為成功。2026-09-15 的 2308 公告連結 `SPOKE_TIME=64117` 省略前導零，已在逐秒核對仍相等的前提下支援。
- 先寫失敗行為測試；相關隔離回歸 **53 passed**。直接活網來源層：2882 由 10 增至 15、2317 由 10 增至 18、2308 由 9 增至 11，三者皆核對原頁且 30 天窗口完整。先確認六個 RQ 佇列無 queued／started／scheduled／deferred、Redis BGSAVE `ok`，再由正式 `start_mac.command` 重載；`/readyz` storage／queue 通過。重載後正式近 24 小時仍為 **14/20** 類高於 80%，近期事件 **286/426（67.1%）**；尚無新版本自然工作形成的全類別成效證明。
- [Bing 新聞 RSS](https://blogs.bing.com/search/April-2008/News-Search-%E2%80%93-now-with-RSS)免 API key，2855、2206 有近期文章，但與 Google 新聞多數同題；2851 的近期結果全是行情／歷史頁，暫不接入。[MoneyDJ 使用條款](https://www.moneydj.com/z/ABMoneydj/aboutTermsService.djhtm)限制未同意的自動下載與 AI 快取，雖其個股 RSS 樣本有日期與標題，也不接入正式自動流程。Yahoo 股市舊 RSS 說明頁所列 `tw.stock.yahoo.com/rss` 在本機實測 HTTP 404；鉅亨分類 RSS 只有約半日的最新 99 篇，均不足以作 30 天個股備援。[金管會「現金流量表」開放資料](https://data.gov.tw/dataset/11139)是年度統計，不是逐公司五年現金流量表，不能補五年財報缺口。

## 續查：排除重複入口，辨識剩餘財報瓶頸

- 正式 24 小時資料來源面板仍為 **14/20** 類嚴格高於 80%；六類未達標依序是職缺 38/74（51.4%）、同業 70/99（70.7%）、法說 87/115（75.7%）、五年財報 60/165（36.4%）、近期事件 286/426（67.1%）、社群 75/288（26.0%）。近 1 小時職缺 5/5、法說 10/10、社群 5/5；這是小樣本且含定向抓取，不能推論未來自然工作或取代 24 小時驗收。
- 公告快易查對上櫃 5314、3587、3324 的 30 天重大訊息各回 2、2、3 筆；既有上櫃年度歷史索引逐篇核對後也各有 2、2、3 筆，均標 `window_complete`。上櫃路徑目前沒有可證明的新增覆蓋，故不重複接入。
- [統一證券官方招募頁](https://eservices.pscnet.com.tw/dm/HR/)明確連至其 [104 雇主招募頁](https://ehrweb.104.com.tw/job.do?uno=23218183)，當時公開頁顯示 138 個職缺。既有 `fetch_104_company_jobs_by_ubn` 以官方統編 `23218183` 實際核對到 5 筆近期個別職缺；138 是另一頁的當前列表總數，不能當成本次逐筆取得數，且現有公司備援已涵蓋此雇主。沒有新增 adapter 或重算舊失敗。
- 財報近 1 小時 5/10（50%）：一般業 9904、1605 的官方五年年報直接成功；金融業 2851、2855 的五年專用 iXBRL 成功，但仍另讀 Yahoo 四年一般欄位（部分取得），2851 還觸發 FinMind 部分補值。不能把金融業專用營收／個體保險數值無標籤轉成一般業欄位，也不能將 Yahoo 四年資料升格為五年成功。下一個實作需先以具範圍／科目標籤的欄位契約與報告使用處驗證，才能減少真正冗餘的抓取。

## 續作：上市公告第一索引失敗時的官方接手

- 原上市公告抓取在 `IIH/company/events` 連線或索引格式失敗時直接返回，未嘗試上一節已核對的公告快易查。現改由公告快易查獨立查詢：每列仍核對上市市場、股票代號、日期時間與原頁；若備援索引混入異公司列，只回傳已核對原文並標 `partial`，不宣稱 30 天完整。第一索引失敗的類型另存 `primary_index_error_kind`。
- 先以模擬第一索引連線錯誤的兩個行為測試確認原流程失敗，再修正；另確認雙索引皆失敗時仍報錯。上市／上櫃及近期事件相關隔離回歸 **56 passed**。來源層活網以受控第一索引故障重播 2855，備援查得 1 篇、逐篇原頁核對成功，`window_complete`，且保留 `ConnectError` 第一索引診斷。這是故障切換驗證，不是正式來源取得率增加或完整報告品質驗收。
- 重啟前六個 RQ 佇列均無 queued／started／scheduled／deferred 工作，Redis BGSAVE 完成且狀態 `ok`；只有本次 `twse_company_history.py` 在上次正式啟動後變動。由 `start_mac.command` 重載後，API 與 `worker_main.py --role all` 為新程序，`/readyz` storage／queue 均通過。正式近 24 小時仍為 **14/20** 類高於 80%，近期事件 **286/426（67.1%）**；此時尚無自然發生的第一索引故障可證明正式流程實際用到新備援，舊事件亦不會回寫。

## 續找：發行人逐字稿與法說索引的實際可用邊界

- [聯發科官方財務資訊頁](https://www.mediatek.com/zh-tw/investor-relations/financial-information)的 2026 Q2「說明會逐字稿」連至[發行人原始 PDF](https://www.mediatek.com/hubfs/MediaTek%20Assets/Pdfs/Quarterly%20Earnings%20Release/2026/Quarterly%20Earnings%20Release-2026Q2/%E8%AA%AA%E6%98%8E%E6%9C%83%E9%80%90%E5%AD%97%E7%A8%BF.pdf)。正式機器直接取回 HTTP 200、272,654 bytes、15 頁，可擷取約 38,646 字；首頁明示 MediaTek 2Q26、2026-07-31、與會者及後續 Q&A。這是 2454 的**完整原始逐字稿候選**，比既有 MOPS 場次／簡報索引有實質內容增益。接入時仍須逐檔檢查發行人、會議日期、季度與 PDF 文字可讀性，不可把其他公司的檔案或下一季預告當本季稿。
- [研華官方法說活動頁](https://www.advantech.com/zh-tw/investor/investor-events?cmsid=8643A167-3378-4CB4-B9C3-3D0F11E7513A)連至[2026 年上半年法說文字 PDF](https://advcloudfiles.advantech.com/investor/Events/Advantech_1H26_Earnings_Call_Transcript_Chinese.pdf)。正式機器取回 HTTP 200、639,129 bytes、8 頁、約 10,799 字，封面標示 2395、2026-08-05；但文件自稱 `Transcript (Summary)`，只能標成摘要，不能升格為完整逐字稿。[光寶科官方頁](https://www.liteon.com/zh-tw/download/investor-conference)也連出 2026 Q2 稿；檔案封面及內文為 LSEG StreetEvents 作品，明載未經書面同意禁止再發布或再散布，故暫不將其全文送入自動報告流程。
- [臺灣指數公司 IR 議合平台法說列表](https://irengage.taiwanindex.com.tw/conferenceList)可免登入按代號與月份找到 2308 於 2026-10-05～13 的場次及直連 MOPS 的 2026-07-30 簡報；2851、2855、2606、6282、6409、3023 的較早場次也能找到。該列表是另一個**索引**，簡報本身仍是同一份 MOPS 原件，並非新的逐字稿。平台[會員條款](https://irengage.taiwanindex.com.tw/account/register)限制未經書面同意使用、重製、引用或轉載網站內容，因此不把列表做正式批次抓取，也不以其連結灌高 `earnings_call` 成功率。證交所 [IIH2 資訊揭露頁](https://www.twse.com.tw/IIH2/zh/company/information.html?code=2855)經頁面程式核對仍呼叫既有 `IIH/company/events`，不是獨立來源。
- [518 熊班統一證券雇主頁](https://www.518.com.tw/company-yMDXdR.html)與[三陽工業雇主頁](https://www.518.com.tw/company-N6jplq.html)目前各顯示 **0 筆**工作機會；搜尋索引還留有「已徵到」的舊職缺，但不得算當前徵才。`robots.txt` 無路徑禁止，卻沒有能補這兩檔的有效逐筆職缺。本輪僅研究與記錄入口，未新增 provider、未重載正式服務。
- 正式 `last_24h` 仍為 **14/20** 類嚴格高於 80%；六類未達標值分別為職缺 51.4%、同業 70.7%、法說 75.7%、五年財報 36.4%、近期事件 67.1%、社群 26.0%。新增的 2454 發行人稿尚未接入，亦無自然工作可證明全類別取得率改善。

## 續作：已有足量近期新聞時省略重複 Yahoo 備援

- 近期事件正式稽核仍有 Yahoo 台股新聞 0 筆成功、28 筆降級；其中部分抓取已有免費新聞與 Alternative Search 的近期合格文章，卻因 Alternative Search 未達它自己的 8 筆候選容量門檻而繼續呼叫 Yahoo。流程現只在 `Alternative Search` 回傳的 `usable_count` 與實際合格列表一致，且兩個來源各有至少 3 筆具日期、發布者與 URL 的文章、合計至少 5 個不同連結及 2 個發布者時，省略 Yahoo。個別來源保留原本的 `insufficient_candidates` 觀測；空缺、過期、重複連結或稽核不一致仍觸發 Yahoo。
- 先以隔離行為測試證明舊流程多呼叫 Yahoo，再修正；工作流與 Yahoo 相關隔離回歸 **72 passed**。另嘗試包含 `test_recent_google_query_window.py` 的擴大測試，出現 **3 個世紀民生／世紀名稱預期差異**，涉及本次未修改的公司名稱查詢流程；該測試組其餘 82 項通過，不能宣稱擴大組全綠。六個 RQ 佇列在重載前後均無排隊、執行、預定或延後工作，Redis 最近 BGSAVE `ok`；正式啟動器重載後 `/readyz` storage／queue 均通過。此時沒有新版本的自然新聞抓取，**24 小時 14/20 仍未改善的正式證據**，不可把隔離測試等同達標。

## 續找：分區政府職缺開放資料與個股 RSS

- [台灣就業通官方開放資料介接說明](https://free.taiwanjobs.gov.tw/webservice_taipei/A17000000J-030144-Taiwanjobs-OpenData.pdf)列有 `CITY`、`ZIPNO`、`COUNT` 與 CSV 格式，欄位包括公司名稱、職缺原頁、更新日及應徵截止日。`https://free.taiwanjobs.gov.tw/WebService_Taipei/Webservice.ashx?CITY=33&COUNT=1000&T=CSV` 等分區端點於正式機器免金鑰、維持 TLS 驗證取得 HTTP 200。XML 回應把中文字放進標籤名，標準 XML parser 無法解析；CSV 可正常解析 19 欄。22 個縣市逐區抽樣時 13 區恰好碰到單次 1,000 筆上限，因此**不是全站完整資料**，也不能把未命中解讀成公司沒有職缺。
- 在近 24 小時原職缺來源只有降級觀測的五檔抽樣中，CSV 找到 2912 統一超 30 筆、1216 統一企業 3 筆；[證交所發行人主檔](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)與台灣就業通個別雇主頁均可核對法定公司名稱及統編：2912／22555003、1216／73251209。另逐筆打開原始職缺頁，抽樣 2912 的 `HIRE_ID=14712117` 與 1216 的 `HIRE_ID=14717673` 皆 HTTP 200，職稱、雇主及尚未過期的截止日一致。這些只是可核對的當前職缺樣本，不能聲稱全部筆數均已逐頁驗證。2891 中信金與 6214 精誠在受 1,000 筆限制的分區清單未命中。
- 1229 的 19 筆表面命中實為**聯華食品工業股份有限公司**；證交所 1229 發行人是**聯華實業控股股份有限公司**，統編也不同。此批職缺一律排除，不得藉子公司資料提高母公司 `alternative_data` 取得率。若接入分區 CSV，應先有逐筆公司全名／統編／原頁／職稱／更新日／截止日驗證，並共用有時效的分區快取與總時限；每次單股抓取不能無界地重讀 22 區。
- [Yahoo 股市官方個股 RSS 設定頁](https://tw.stock.yahoo.com/rss-index)與[使用條款](https://tw.finance.yahoo.com/rss-help)提供免費個股 RSS（限個人、非營利用途並須標示出處）。實測 `https://tw.stock.yahoo.com/rss/s/2855` 等 13 檔皆回 20 篇原連結、發稿時間與摘要；按既有公司／30 天閘門，每檔有 1–11 篇合格候選。但其前幾篇與既有 Yahoo 台股個股新聞頁高度重複；2855、3023 各僅 3 篇近期合格，其餘多是過期，不能把 20 篇全算成功或當作獨立新聞出版者。此 RSS 目前宜作既有 Yahoo HTML 傳輸失敗時的候選備援，尚無證據顯示可顯著提高 `recent_catalysts` 正式成功率。
- [Bing News RSS 搜尋](https://www.bing.com/news/search?q=%E4%BF%A1%E9%82%A6%203023&format=rss)亦可免金鑰取得原文章連結與日期。五檔抽樣的 2855、3023、5314 各有 5–10 篇通過現行時間／公司文字篩選，但 2851 的唯一「近期」結果其實是靜態個股頁，5314 也有靜態報導列表。須再排除非文章頁並核對原站日期，且與現有 Google／Yahoo 新聞去重，才可能接入；本輪未把搜尋索引時間冒稱原文日期。
- 本節僅完成來源可達性、原頁抽樣與發行人身分核對，**未修改 provider、未重載服務、未重算舊觀測**。正式近 24 小時仍為 **14/20** 類嚴格超過 80%；政府 CSV 對 2912、1216 的潛在增益還不是正式來源或報告成功率驗證。

## 續作：台灣就業通分區 CSV 作為公司搜尋失敗備援

- 在既有 104 精確公司職缺與台灣就業通公司搜尋都未取得時，新增政府分區 CSV 備援。每個縣市最多讀官方 1,000 筆、回應上限 3.5 MB，分區資料共用 30 分鐘快取與 12 秒總期限；一旦找到候選就停止跨區掃描，候選至多五筆。CSV 的公司名稱、職缺網址、更新日與截止日只是線索，還要到台灣就業通雇主頁核對法定名稱及統編，再到逐筆原頁核對工作代碼、職稱及截止日。多個雇主 ID 混入、子公司、過期、網址異常或證據不完整都維持未取得；回傳的是核對過的樣本，不推定全站總數。對原公司搜尋的 500 KB 頁面上限不變，分區備援的雇主頁另外允許 600 KB，以容納實測 2912 頁的 508,099 bytes。
- 先寫失敗測試，再接入原 `alternative_data` 職缺欄與資料信任覆核。真實來源層測試：2912 取得 **2** 筆、1216 **1** 筆，保存官方 CSV 城市 URL、雇主頁及逐筆原頁，`verified_taiwanjobs_job_count` 分別覆核為 2、1；1229 因發行人與聯華食品不同，仍回未取得。職缺、來源稽核與 provider workflow 的隔離回歸 **314 passed**。
- 重載前檢查六個 RQ 佇列 queued／started／scheduled／deferred 全為 0，Redis 上次 BGSAVE 為 `ok`。透過正式 `start_mac.command` 重載後，新 API／worker 就位、`/readyz` storage／queue 通過。對 2912、1216 各執行一次 `force_refresh=True` 完整資料抓取，兩次 `cache_hit=false`、`alternative_data` 個別取得稽核為 `success`、合併 coverage 仍為 `partial`，但**均由既有 104 取得**，分區備援沒有被觸發；不能把這兩次成功歸功於新入口。後續對 24 小時有職缺稽核的股票，22 區原始 CSV 與證交所發行人法定名稱交叉比對：2912、1216、3023、6409、1605、2308、9904 有精確公司列，而這些股票在現有 104 路徑已出現成功觀測；目前尚未找到可自然觸發備援且新增成功的股票。本版主要提供 104 失敗時的可驗證韌性，不宣稱當下全類別達標。
- 最新正式 24 小時仍為 **14/20** 類嚴格超過 80%；職缺 **40/76（52.6%）**。其餘未達標仍是同業 72/101、法說 91/119、財報 62/167、近期事件 294/434、社群 76/291。舊觀測不重寫，單兩檔受控抓取也不等於自然工作 24 小時驗收。
- 最後補上分區 CSV 職缺 URL 的重複 `HIRE_ID` 參數退件，再跑相同隔離回歸仍為 **314 passed**。六佇列再次確認無 queued／started／scheduled／deferred 工作後第二次重載正式啟動器；新程序 `/readyz` storage／queue 通過。最終程式的來源層活網再驗 2912 仍為 2 筆且驗證計數 2；這次仍非正式完整工作觸發該備援。
- 為免延長既有成功工作，分區 CSV 備援延後至 104 關鍵字候選、官方職缺及台灣就業通公司頁都沒有核對過的職缺後才執行；隔離測試確認 104 已有合格職缺時不呼叫分區入口。相同回歸仍 **314 passed**，六佇列空且 BGSAVE `ok` 後再次以正式啟動器重載，最後新 API／worker `/readyz` storage／queue 通過。這項順序修正尚無自然工作量測可證明縮短實際耗時。

## 續作：社群入口優先順序與原文驗證

- 2912 在正式 07:45 的完整強制資料抓取中社群為空，接著實際直讀 [CMoney 統一超個股概覽](https://www.cmoney.tw/finance/2912/f00025)時，舊 `forum-web` 列表沒有近期候選，概覽前五筆中的第三篇卻有 2026-10-07 的[可核對原文](https://www.cmoney.tw/forum/article/185201404)。來源程式可通過原文時間、唯一 `2912統一超` 股票標籤、正文及 URL 檢查；2855 也有相同的「舊列表空、概覽有合格原文」情形。這說明原先先等空舊列表會花掉共用 12 秒查詢期限的一部分；無先前失敗時的逐 HTTP 診斷，仍不能斷言 07:45 空結果只由呼叫順序造成。
- 現讓 CMoney 個股概覽先查，有合格原文即停止；概覽未取得時仍查保留絕對發文時間的 `forum-web` 列表。先用 2912 呼叫順序行為測試重現舊流程多查空列表，再修正；另以 1605 確認舊列表在概覽無文章時仍能回復。相關社群、來源選擇與職缺回歸 **301 passed**。活網新順序直接讀 2912、2855 各 1 篇；2912 通用社群 provider 再取得 1 篇、狀態 `success`。
- 重載前六個 RQ 佇列 queued／started／scheduled／deferred 全為 0、Redis BGSAVE `ok`，再由正式 `start_mac.command` 啟動新 API／worker；`/readyz` storage／queue 通過。重載後 2912 `force_refresh=True` 完整資料抓取 `cache_hit=false`，社群來源稽核兩列 aggregate 均為 `success`、各 1 篇，快照保留上述原文 URL；這是受控抓取，不是自然工作 24 小時成效或情緒分數。正式 24 小時仍是 **14/20** 類高於 80%；社群 **77/292（26.4%）**，尚待舊失敗離窗與自然工作驗證。

## 續找：社群覆蓋樣本與公開 Workday 職缺

- 用目前已部署的 CMoney 原文 adapter，再對先前正式來源常空的 1229、2855、2891、6214、9945、5314、1605、2002 逐檔直讀：八檔均有 30 天內的原文，分別得到 3、1、1、2、3、3、3、2 篇。每篇保留原始 URL 與絕對時間；1229、9945、5314 另經通用公司／日期篩選，各 3 篇均入選。這是來源層定向測試，並非八次完整正式工作；不能推算自然流量成功率，也沒有重新標記舊觀測。
- [中信金控人才招募頁](https://www.ctbcholding.com/content/twhoo/zh_tw/Careers.html)的「最新職缺」指向公開 [Workday 職缺站](https://ctbcholding.wd3.myworkdayjobs.com/zh-TW/External)。其 [robots.txt](https://ctbcholding.wd3.myworkdayjobs.com/robots.txt)允許 `/External/`，並列出 [公開 sitemap](https://ctbcholding.wd3.myworkdayjobs.com/External/siteMap.xml)。正式機器免登入取得 sitemap HTTP 200，當下列 100 個逐筆職缺 URL。逐筆 HTML 的 `JobPosting` JSON-LD 明列 `hiringOrganization.name`、`datePosted`、職稱及 requisition ID；因此可以不用內部搜尋 API，以原頁驗證雇主與刊登日。
- 抽查 sitemap 前 18 筆，第一筆是中國信託**商業銀行** 2026-10-06 的科技金融職缺，而非上市公司 2891 中信金控；[金控本體的一筆實習職缺](https://ctbcholding.wd3.myworkdayjobs.com/External/job/Taipei/XMLNAME-2026--Rising-Star_JR8971)則明列 2026-08-24，已超過現行 30 天近期刊登窗。前 18 筆依刊登日從 2026-10-06 退至 2026-02-03，不能把銀行、壽險等子公司或過期金控職缺算成 2891 的新職缺；目前沒有驗證到可讓 2891 `alternative_data` 轉成功的合格原文。因此先記為有結構化收據的免費候選，不接入正式批次抓取。
- 另核對先前職缺稽核全空的 1229 與 6214：現有 104 精確公司入口可活網取得聯華實業控股的 14 筆、精誠資訊的 90 筆近期刊登候選；兩家公司以官方全名及證交所統編核對的 104 公司頁細節備援，各可另外核對前 5 筆。對 1229 執行目前的 `AlternativeJobOpeningsProvider` 來源層路徑，回傳 `success`、14 筆、且保留 1111 不可用造成的 `partial` 覆蓋說明；前三筆刊登日為 10/08、10/06、10/02。這是未記入正式 SLA 的受控來源測試，說明先前空觀測不代表公司現在沒有職缺，後續要等自然工作驗證。
- 本輪沒有變更 provider 程式或重啟服務。正式近 24 小時仍是 **14/20** 類高於 80%；財報 **63/168（37.5%）**、社群 **77/292（26.4%）**。2206、3023 的 2021 年原始 iXBRL、次年比較列，以及證交所財務比較站均缺同一「取得無形資產」科目；不能以零填補或用不等價科目換算自由現金流。
- 財報低率還有口徑問題：近 3 小時的官方一般業／金融業 iXBRL 合計 10/11 筆成功，但 Yahoo 年度三表 5/5、FinMind 補值 3/3 仍是部分取得。報告目前仍把通用年度營收、淨利、現金流、資產、權益供歷史列、比率、量化估值與金額查核使用；金融業官方專用科目另有明確的合併／個體範圍。不能為提高來源比率直接停抓 Yahoo／FinMind、把金融業淨收益當一般業營收，或把保險個體數字混入合併序列。若要移除不適用的抓取，須先逐欄完成同口徑投影與報告回歸；本輪沒有做這項高影響改動。

## 續查：正式股票群的當前來源覆蓋

- 正式近 24 小時社群觀測涉及 27 檔不同股票。前兩批及本批來源層直讀已逐檔覆蓋這 27 檔；本批新增的 1319、2023、2308、2367、2882、3017、3324、3653、6282、9904 十檔，各由 CMoney 公開逐篇原文取得 2–3 篇 30 天內樣本。連同前兩批，目前 **27/27 檔在受控來源層有原文樣本**。再用五檔先前同業或職缺常空的完整快照身分（1229、5314、9945、1319、9904）進入現行社群 provider，五檔皆為 `success`，原文數 3、3、3、3、2，通用公司／日期選擇無拒收。這證明新入口對這批股票的可行覆蓋，但仍未證明正式自然工作 24 小時成功率；不回寫舊事件，也不靠受控抓取沖高面板。
- 從最新已存報告的實際公司身分與今日 FinMind 股票主檔重跑同業候選：1229 是交易所食品工業，但 Yahoo 細業為 conglomerates，不能把其他食品公司當已驗證業務可比；5314、9945 目前官方主檔只給「其他」寬類，不能按其歷史或 Yahoo 細業自行擴充同業。2855 證券商與 2851 再保險的現行來源直讀則分別取得 1 與 4 個完整可比指標列。這些定向成功不等於舊報告或自然工作已更新；若要讓同業來源長期超過 80%，必須取得 1229、5314、9945 的**當前**可比企業原始證據，不可把市場同類或舊產業標籤直接當可比性。

## 續找：發行人法說原件與券商競爭名單的時效風險

- [FinMind 官方現金流資料說明](https://finmind.github.io/tutor/TaiwanMarket/Fundamental/)確認逐列有 `type` 與原始科目名。以免金鑰 v4 API 直讀 2206、3023 的 2021 年底現金流，各得 25、22 列；均有營業現金流與取得不動產廠房設備，沒有取得無形資產支出列。這和先前官方 iXBRL／比較站的缺口一致，不能由 FinMind 補成完整自由現金流，也不能把缺列當零。
- [凱基 Super PY 的 1229 公司頁](https://superpy.kgieworld.com.tw/kgipythonapi/stockInfo/companyDetail?stockCode=1229)公開列統一、福懋油、德麥、南僑等「主要競爭對手」；[9945 公司頁](https://superpy.kgieworld.com.tw/kgipythonapi/stockInfo/companyDetail?stockCode=9945)也列多家建商。可是 [5314 同一入口](https://superpy.kgieworld.com.tw/kgipythonapi/stockInfo/companyDetail?stockCode=5314)在現行營收組合已含工程、廣告、餐飲時仍列舊 IC 設計公司，證明該欄不能無條件視為當期業務可比。1229 是持股公司，食品競爭名單至多用於食品部門；9945 須另核對建設部門占比與同口徑估值。[凱基 API 服務條款](https://superpy.kgieworld.com.tw/kgipythonapi/guide/tw/terms)另要求正式 API 使用前簽署文件；公開頁雖可用系統 `curl` 驗證 HTTP 200，Python `requests` 在現行憑證鏈下驗證失敗。此入口僅列研究線索，**未接入自動抓取或同業數值**。
- [聯華控股發行人法說索引](https://www.lhicholdings.com/investors/3news/)免登入列法說活動、簡報與影音。[2025 Q4 簡報原件](https://www.lhicholdings.com/investors/3newsFile/Investor-Conference-dw-2025Q4/)由正式機器取得 `application/pdf`、24 頁，前兩頁可直接擷取公司名、簡報標示的 2026-03-31 日期與免責說明；第 4 頁的合併營收圖亦明列麵食、資訊整合、股利及租賃等不同業務，支持不可用純食品同業代表整體 1229。[2026 Q1 簡報原件](https://www.lhicholdings.com/investors/3newsFile/Investor-Conference-dw-2026Q1/)為 27 頁但文字擷取為空，不能以頁面索引冒稱已有可供模型引用的簡報文字。這是 `earnings_call` 的發行人原件備援候選，後續若接入須驗證文件身分、日期、可解析文字與逐頁證據；本輪沒有新增 adapter 或重載正式服務。

## 續作：社群原文短暫傳輸失敗修復

- 2026-10-09 07:45 台灣時間，正式 `2912.TW` 的社群 provider 回傳 `empty_unknown` 並落到 PTT 空結果；07:54 同股票另一個正式抓取取得 CMoney 原文 1 篇。當前直接讀取 2912 的 CMoney finance 列表有五個原文候選、stock 列表沒有近期候選，逐篇核對可取得 2026-10-07 的原文。這說明列表找到候選後，單篇傳輸失敗可能使整次來源落空；舊紀錄沒有逐 URL 傳輸原因，不能斷言 07:45 的唯一成因。
- 在 `cmoney_stock_posts.py` 增加一次有界恢復：兩個公開列表都未產生合格樣本後，只對首次**傳輸失敗**的原文 URL 再試一次，至多五個、仍受原本 12 秒整體期限約束。錯誤股票標籤、日期、內容或有效空列表不重試、不變成成功。先新增失敗測試，修復後與社群、來源稽核相關的 **241 項**隔離測試通過；把舊測試中只有標題的 Dcard 假樣本改為應排除，沒有放寬原文證據門檻。
- 佇列 queued／started／scheduled／deferred 均為 0、Redis BGSAVE 為 `ok` 後，由 `start_mac.command` 載入正式 API／Worker；最後一次約 08:20 重載的是完成嚴格傳輸錯誤分類後的程式，`/readyz` storage／queue 均通過。重載後正式近 24 小時仍 **14/20** 類嚴格超過 80%：職缺 41/77、同業 73/102、法說 93/121、財報 63/168、近期事件 297/437、社群 77/292。這次只證明具體傳輸失敗能在測試中恢復、修正程式已載入；尚無自然工作觸發同一失敗並恢復的正式憑據，也不能重寫 24 小時舊空觀測。

## 續作：完整證券商官方年報取代重複年度備援

- 2855 的官方 `broker_consolidated.v1` 五年原件在活網仍可取得 2021–2025。2025 年明列證券商營業收入 13,541,305,000 TWD、母公司淨利 4,804,426,000 TWD、自由現金流 -10,230,221,000 TWD；舊報告的 Yahoo 通用營收為 12.42 billion TWD，不能假設兩者科目相同。新增有明確來源欄位與 scope 的年度投影，只接受同一公司、五份同年度 C-scope 官方 URL、原件 hash、完整整數科目與可核對 FCF 算式；年度序列依原始 TWD 換成 billion TWD。毛利及營業利益仍為 `None`，銀行淨收益及保險個體 schema 均不代填。
- 完整 broker 年度序列保留 `financial_history_basis`，供 prompt、角色 State view、金額查核及快照保存使用；有效資料停止通用 Yahoo／FinMind 年度備援，資本結構提示也不再另讀 Yahoo 年度資產負債表，改用同一年官方資產及期末母公司權益並明確標示此 ROE 口徑。缺 hash／年份／來源索引、畸形 URL、錯公司、非合併範圍、缺科目或 FCF 算式不合時拒絕投影，保留降級診斷與既有備援。金融業年度雷達 cache namespace 更新，避免舊快取缺少憑據卻進入新投影。
- 先失敗的公共提取器、prompt 及 State view 測試已通過；活網官方收據保存為 `tests/fixtures/source_acquisition/broker_2855_20261009.json`，可禁止網路重播。最後回歸 **700 passed、1 skipped、1 deselected**：跳過是既有 optional private complete report replay；排除是既有 Agent24 JSON 表格編碼測試，關閉本次 broker prompt basis 後仍重現相同失敗，未修改該測試。獨立覆核最後另有 76 項通過、無未解重大 finding。
- 正式六佇列 queued／started／scheduled／deferred 均為 0，BGSAVE `ok` 後由正式啟動器載入；API／Worker 與 `/readyz` storage／queue 正常。08:38 用完整 `StockDataService` 強制抓取 2855（未執行模型）驗證：五年年度序列、broker 科目標籤、官方負 FCF、EM 6.355x、資料信任 `fresh` 均回傳，年度財報 audit 只有官方成功與整批摘要，沒有 Yahoo 年度三表或 FinMind 年度備援。另一個 `twse_official` 近四季來源仍呼叫 FinMind 三表，因期間不同保留此取數。本次受控程序只攔截 telemetry 寫入並保留在記憶體，實際來源與快取路徑照常執行，同一 fetch_id 在正式 SLA DB 的列數為 **0**；因此沒有用這次 smoke 提高正式成功率。
- 另外兩個行為測試先重現「數值相同但報表 scope 改變仍未標重跑」；`report_refresh_diff.py` 現在將科目依據及專用年報變更列為分析相關資料，避免快照刷新後沿用不同口徑的舊結論。依專案要求完成追蹤刷新、decision workflow、incremental refresh、artifact 與 runtime path **54 項**隔離回歸，最後約 08:41 再由正式啟動器載入，`/readyz` storage／queue 通過。
- 08:38 後正式近 24 小時仍為 **14/20** 類嚴格超過 80%，六類缺口仍是職缺 41/77（53.2%）、同業 73/102（71.6%）、法說 93/121（76.9%）、財報 63/168（37.5%）、近期事件 297/437（68.0%）、社群 77/292（26.4%）。本次證明完整 broker 的實際資料取得流程已使用五年官方科目並減少不必要年度取數，尚未取得自然工作 24 小時成功率或新模型報告品質的驗收憑據；歷史報告與來源事件未改寫。

## 續作：中信金控官方 Workday 精確公司職缺

- 2026-10-09 重新檢查 [官方 Workday 搜尋頁](https://ctbcholding.wd3.myworkdayjobs.com/zh-TW/External)。先前 sitemap 的前 18 筆抽樣沒有完整覆蓋金控本體；公開 UI 的「公司」篩選實際列出 `中國信託金融控股公司`，公司 ID `1e73f5b107d8012217d8aa3be2e00000`，當時有 8 筆。瀏覽器實際觀測免登入 `POST /wday/cxs/ctbcholding/External/jobs` 與逐筆 `GET /wday/cxs/ctbcholding/External/job/...`，再以系統 curl、不帶瀏覽器 token 或 cookie 取得相同回應。公司篩選只是候選，仍須逐筆核對 `hiringOrganization.name`、requisition ID、原頁 URL、絕對 `startDate`、`posted=true` 與 `canApply=true`。
- 逐筆原件核對取得 **4 筆金控本體近期職缺**：JR7016、JR9297 刊登日 2026-10-06；JR7300、JR8696 為 2026-10-01。其餘四筆超過 30 天近期刊登窗而排除。Rising Star 的 2026-08-24 是舊刊登日，不等於職缺已關閉；本 adapter 保守維持近期刊登窗。搜尋引擎顯示暑期實習的「應徵」來自舊頁内容，這次直接開官方 JR6220 頁已顯示不存在；不能用舊搜尋摘要或按鈕取代當前可用性證據。
- 新增 `ctbc_careers.py`，只允許已核對的 2891 金控身分、固定官方 host 與公司篩選；上市公司 legal name 和官方招募名稱的已知對應明列於 adapter。只保存核對過的樣本數，`job_count=None`，不將官方清單 8 筆當近期職缺總數。外部傳輸共用 12 秒期限、每次至多 4 秒、1 MB 上限、無重試、無 redirect；列表明示超過 30 天的候選先排除，其他入選仍要求逐筆絕對日期。子公司、已截止、申請期限不明、身分衝突、未知回應或畸形網址保持未取得。
- 在現有 104 憑據未通過 `source_record_count` 時啟用此備援；缺 hash／query scope 的 104 非空 rows 不得阻止備援，有效 104 不增加 Workday 呼叫。新官方資料由 `data_trust_audit.py` 的 2891 分派再驗身分、日期、當前開放欄位、每筆來源與 hash；國泰金 2882 原規則維持相容。部分來源取得仍保持 `partial` coverage，不把 1111 失敗變成成功或零職缺。
- 保存真實公開 JSON 回應 `tests/fixtures/source_acquisition/ctbc_2891_jobs_20261009.json` 供禁止網路重播。活網 adapter 取得 4 筆、覆核計數 4；另從實際 `legal_name=None` 的公司身分進入完整 `AlternativeJobOpeningsProvider._fetch_uncached`，由交易所收據取得公司全名，最終 `success`、`partial`、audit count 與 trust count 都是 **4**，耗時 **14.35 秒**。這是直接來源／provider 測試，不是完整模型報告；沒有寫入正式 provider SLA。
- 先重現缺 adapter、真實 `_JR9297` slug 格式、截止同義句、異常時間戳與 104 備援守門失敗，再完成修正。最後相關來源、provider workflow、資料信任與 prompt 回歸 **396 passed**；獨立覆核指出的截止語意、`10**400` 時間戳溢位與申請期間兩端日期已補失敗測試再修正，最終獨立 CTBC 隔離覆核 **39 passed**、無未解重大 finding。
- 六個正式佇列 queued／started／scheduled／deferred 都為 0、Redis BGSAVE `ok` 後，由 `start_mac.command` 重載；新 Worker／API 分別於 **09:00:27／09:00:28** 啟動，晚於三個 runtime 檔案最後修改時間。`/readyz` storage／queue 通過；重載後六佇列仍空，10 個既有 stale failed jobs 未改寫。09:01 正式 24 小時仍為 **14/20** 類嚴格超過 80%，職缺 **41/77（53.2%）**；其餘缺口為同業 73/102、法說 93/121、財報 63/168、近期事件 297/437、社群 77/292。這證明可核對的新增免費入口已接入並載入正式程式，尚無自然工作觸發此入口或完整新模型報告的成效憑據；未重寫歷史觀測，也未以這次來源測試提高 SLA。

## 續作：完整金融業合併年報接入獨立淨收益年度序列

- 本輪正式基準仍為原 20 類中的 14 類超過 80%。法說 MOPS 鏡像已取得 45/47 筆；較大當前缺口是財報 63/168。中信金 2891 的實際官方 iXBRL 原件完整提供 2021–2025 `financial_institution_consolidated.v1`；2025 合併淨收益 244,894,671,000 TWD、母公司淨利 80,619,233,000 TWD，自由現金流算式結果 67,802,000 TWD。原件五年各有發行人、年度、合併 scope 及 hash，保存公開收據 `tests/fixtures/source_acquisition/financial_institution_2891_20261009.json`。
- `financial_history_basis.py` 共用原 broker 的五年公司／C-scope／年度／科目／整數／現金流算式驗證。完整金融業合併原件以獨立 `net_revenue_history` 保留淨收益；一般產業營收、毛利與營業利益仍為 `None`。已核對的母公司淨利、合併資產、母公司權益及同年現金流對齊五年序列，停止通用年度 SDK／FinMind 備援。保險個體 schema 不套用；不完整或不一致的收據保留降級與既有備援。金融業年度雷達 namespace 更新為 v3，其他產業原 namespace 不變。
- core／payload／State view／快照保護／追蹤重跑皆保留淨收益與科目依據。財務 prompt 增獨立淨收益欄，預先計算只產生有淨收益名稱與來源路徑的 CAGR／YoY／母公司淨利對淨收益比率。報告圖表改用「年度合併淨收益」及相應 series，仍維持一般業原圖；JavaScript 原模板行為測試驗證兩種實際 dataset 設定，rendered HTML 驗證標題與 JSON payload，未當成像素視覺驗收。資本結構提示以同年度期末母公司權益，保留非平均權益 ROE 的口徑。
- 金額查核只在幣別、年度、公司範圍與原件依據可核對時驗淨收益單位；同公司未限定的「營收／營業收入」不能借淨收益改名。明示他公司／同業／金融業整體或不明主體維持未驗證，不用本公司淨收益誤擋他公司實績。新金融業原件現金流算式未驗證一般業 FCF/WACC DCF 所需的正常化企業現金流，也未提供金融業可分配股東現金流的模型。本輪先重現完整市場輸入會將此 FCF 放行 DCF，再加可用性限制；對派生陣列損壞、缺 basis、缺 hash 亦維持不可用，沒有透過驗證失敗重新放行。這項適用性判斷參考 [Damodaran 金融業估值章節](https://pages.stern.nyu.edu/~adamodar/pdfiles/val3ed/c21.pdf)對金融業再投資與現金流口徑的區分；本實作沒有新增金融業 FCFE 模型、改寫原年報金額或改變其他產業 DCF。
- 活網國泰金 2882 的 extractors 亦取得五年淨收益 625.962605、341.433658、296.528560、357.716917、350.404915 billion TWD，來源為 `success`、年度 SDK 與 FinMind fallback 均未執行，耗時 17.39 秒。09:22 對 2891 執行完整 `StockDataService force_refresh=True`（無模型），耗時 24.59 秒、`cache_hit=false`，五年淨收益正確、年度財報 audits 僅官方 `success` 5 筆及整批摘要 5 筆、沒有 Yahoo／FinMind 年度備援，資料信任 `fresh`，年度資本提示、圖表標籤與淨收益 CAGR 7.1107% 均回傳。另一個 `twse_official` 近四季來源仍獨立抓取 FinMind 三表，沒有停止不同期間的必要資料。這次受控程序僅攔截來源 telemetry 寫入，實際資料與快取路徑照常執行，同 fetch IDs 在正式 SLA 的列數 **0**。
- 先重現原公共提取器仍查 SDK、typed prompt／State／chart 缺欄、年度現金流誤入 DCF、DCF 失敗驗證重新放行，以及他公司金額被誤判為本公司科目，再完成修正。最後相關金融、broker、insurer、財期、quant、prompt、chart 與金額回歸 **400 passed、1 skipped**；skip 為既有 optional private complete report replay。另依專案要求完成 tracking workflow／decision workflow／incremental refresh／artifact／runtime／settings／storage 與新投影 **72 passed**。最終獨立覆核 **187 passed、1 相同 optional skip**，無未解重大 finding。
- 六個正式佇列 queued／started／scheduled／deferred 全為 0、Redis BGSAVE `ok` 後，由 `start_mac.command` 重載；API／Worker 約 **09:39:45** 啟動，晚於本輪 runtime 檔案最後修改時間。09:42 `/readyz` storage／queue 通過，六佇列仍空，10 個既有 stale failed jobs 未改寫。正式近 24 小時仍 **14/20** 類嚴格超過 80%；財報 **63/168（37.5%）**、職缺 41/77、同業 73/102、法說 93/121、近期事件 297/437、社群 77/292。這證明完整金融業原件已接入並載入正式程式；尚無自然工作觸發此版或完整新模型報告的驗收憑據，不能以本輪受控抓取宣稱原 20 類達標。

## 續找與接入：中再保無子公司的完整個別年報

- 本輪從 [MOPS 官方年度原件索引](https://mopsov.twse.com.tw/mops/web/ajax_t203sb01)重新核對 2851：沒有 C-scope 合併年報，A-scope 的 2021–2025 五份原件各在同公司、同完整年度的 `tifrs-notes:BasisOfPreparation` 明示「本公司並無子公司，故本財務報告係個別財務報告」。[2025 原件](https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=2851&year=2025&season=4&report_id=A)列保險業營業收入 22,898,381,000 TWD、本期損益 2,932,619,000 TWD、資產 59,835,174,000 TWD、權益 21,706,032,000 TWD。五年各有完整收入／損益／資產／權益／CFO／設備及無形資產支出；保存公開原件的 scope 註記、科目、網址及 hash 至 `tests/fixtures/source_acquisition/insurer_standalone_2851_20261009.json`。這個缺口是原先把 A-scope 一律留在不投影的 individual 路徑，並非沒有官方完整資料。
- [中再保發行人財報索引](https://www.centralre.com/content/financial/financial02.htm)也免登入連出五年完整年度 PDF；正式機器的系統 curl 可驗證 TLS 讀到索引，Python httpx 目前遇憑證鏈驗證失敗。2025 PDF 回應約 26.2 MB，在 20 秒、50 秒有界下載均未完成，不能當本輪已取得可解析的完整備援文件；未關閉 TLS 驗證，也未把它接入每股抓取。主路徑使用已能完整取回的官方 iXBRL。
- 新 `insurer_standalone.v1` 只有五年原件均通過同公司／年度／唯一 BasisOfPreparation 註記才成立；A-scope 本身、其他公司／期間的註記、缺註記或重複註記都不夠。下游重新核對五年文件、原件 hash、scope 證據、原科目整數與現金流算式後，才將保險業個別營業收入、本期損益、資產、權益及同年 CFO+capex 對齊 annual arrays。一般業毛利及營業利益維持 None，原 insurer individual 路徑不升格，完整新契約停止年度 SDK／FinMind 備援；金融業年度雷達 namespace 為 v4，其他產業不變。
- Prompt、State、圖表及資本結構提示保留個別範圍、本期損益與期末個別權益；圖表實際 JavaScript dataset 和 rendered HTML 均有隔離行為驗證。金額查核只借用同公司、同年、可核對契約；他公司保持未驗證，本公司誤稱合併或母公司科目會攔截。現金流算式不證明一般業 FCF/WACC DCF 適用，原件／basis／派生陣列損壞亦不得重新放行；其他產業與無新契約的歷史輸入不改寫。
- 活網年度提取器 2851 成功回五年，耗時 **20.26 秒**、官方 audit `success`／5 筆、scope `standalone`；年度 SDK 與 FinMind fallback audit 均 null。完整 `StockDataService force_refresh=True`（無模型）耗時 **35.43 秒**、`cache_hit=false`、data trust `fresh`、basis 重新核對成功，財報 audits 只有官方 success 5 筆及整批摘要 5 筆，圖表與資本提示 scope 正確，DCF unavailable。近四季 `twse_official` 的 FinMind 三表仍獨立取得。來源 telemetry 僅捕捉至記憶體，fetch ID `40ec58d8ef694357b5a502776ddc74f7` 在正式 SLA 的列數 **0**，未將受控測試灌入 24 小時驗收。
- 先重現 scope 沒有分流、已完整卻重查 SDK、DCF 放行、prompt 缺原件仍標無子公司、以及母公司用詞未被攔截，再修正。最後相關金融／broker／insurer／quant／財期／prompt／chart／來源回歸 **497 passed、1 skipped**；skip 是既有 optional private complete report replay。另完成專案 tracking／runtime／settings／storage 相關 **88 passed**。最終獨立 scoped 覆核 **238 passed、1 相同 optional skip**，無未解重大 finding；前期／否定引用與同文反證的無子公司註記均已補退件測試。10:09 Redis BGSAVE `ok`、六佇列無 queued／started／scheduled／deferred 工作後，透過正式 `start_mac.command` 重載；新 Worker／API 分別 PID 52425／52427，於 **10:11:13** 左右啟動，所有本輪 runtime 檔案均早於啟動。10:11 `/readyz` storage／queue 通過，六佇列仍空，10 個既有 stale failed jobs 未改寫。正式近 24 小時仍 **14/20** 類嚴格高於 80%；財報 **63/168（37.5%）**、職缺 41/77、同業 73/102、法說 93/121、近期事件 297/437、社群 77/292。尚無自然工作觸發新個別年報路徑或新完整模型報告的驗收憑據，不能以本輪受控來源測試宣稱原 20 類已達標。

## 續驗與接入：四檔完整流程與潤泰新營造候選

- 以已部署來源路由對 1229、5314、9945、6214 各執行一次 `StockDataService force_refresh=True`（無模型），耗時 30.80、19.07、24.66、17.42 秒，各 `cache_hit=false`、data trust `fresh`。四檔皆取得五年官方財報、104 精確公司近期職缺（14、3、20、90 筆）與 CMoney 原文樣本（3、3、2、2 篇）。6214 已取得 2 個完整同業指標列；1229、5314、9945 仍無候選指標。5314 法說保留已有官方簡報的 partial 快取，其餘三檔 MOPS 活動取得；未把快取當新抓取。這些定向診斷的來源 telemetry 捕捉至記憶體，四次同 fetch IDs 在正式 SLA 均 **0** 列，不能當正式 24 小時成效。
- 財報再查 2206、3023 的 2021 原件及 2022 比較列：仍無「取得無形資產」支出。3023 原件明列 B04600 處分無形資產 22,673,000 TWD，不能換成購買支出。另從 [信邦發行人 2023 股東會議事手冊](https://www.sinbon.com/cn/files/2023_3023_20230530FE3_20230901_141259.pdf)完整取得 604,832 bytes、29 頁，在第 23 頁的 2022／2021 現金流原頁視覺核對同筆 22,673 仟元；英文行名是 Decrease in other intangible assets，不能由此推導未揭露的 gross purchase 等於零。保留原始 PDF 至 `docs/evidence/source-acquisition/20261009/sinbon-2022-shareholder-handbook.pdf`，不補零、不用處分收入代填 FCF。
- 新免費線索由 [TPEx 潤泰新個體公司產業鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=9945)及[建材營造鏈](https://ic.tpex.org.tw/introduce.php?ic=S000)同一「營造業」區塊核對。頁面未標產業分類發布日，僅供營造部門候選；不能證明公司整體業務或不同財期估值可比。9945、2535 達欣工、2546 根基、5515 建國、2597 潤弘均用當日主檔核對代碼／名稱／市場；公開 HTML 原件保存兩份 fixture。來源名稱、membership hash、兩頁 URL、主檔日期及未驗證限制隨候選保存。
- `official_construction_peer_cohort.py` 只接 9945，並沿原 `peers.py` 十次候選下載／五筆輸出上限安排。目標公司鏈綁定自己 `div.content`，不能從頁尾他公司取得 membership；desktop／mobile 各對單筆核對，退件一筆不清除其他有效候選。快取重新檢查非 bool、有限、非未來且 24 小時內的取得時間與兩份 hash；缺／損壞／過期收據不供應候選。傳輸改用 `construction_cohort_transport.py` 與既有 capped child collector：兩個固定 HTTPS URL、每頁 250 KB、各至多 6 秒、整批 12 秒；slow-drip／overflow 的真實無網路子程序測試確認停止並回收。TLS、proxy 不繞路、無 retry／redirect，實際 429／403／5xx 與 Retry-After 保留於來源錯誤與冷卻。
- 沿用 `official_segment_candidate` 與 `business_comparability_verified_current=False`：四筆各自公司數值可以保存，`prompt_peer_projection` 與 snapshot 自動估值仍排除。活網候選／指標直查得四筆 complete（含同年度營收／期末資產週轉率），3.03 秒；最後有界傳輸再直讀兩頁 **0.51 秒**。完整 9945 流程 **39.52 秒**、`cache_hit=false`、data trust `fresh`，兩列來源 audit 為 success／4 筆，但自動估值與 prompt 可比較列仍 **0**。另一個免費搜尋來源發生 SerpAPI ReadTimeout，未改成成功；本輪不宣稱端到端速度縮短。此受控 fetch ID `20dcb6d37a824767a5cb3b44ce337adf` 在正式 SLA 為 **0** 列。
- Public 動態來源原本 empty 已先重現，再接入；覆核發現的跨公司區塊借用與 invalid cache timestamp 也先補失敗測試再修正。來源／peer／transport／prompt／snapshot／provider 回歸 **270 passed**，專案 tracking／runtime／settings／storage 與新來源相關檢查 **80 passed**，有部分重疊，不加總。最終獨立 scoped 覆核 **33 passed**、無未解重大 finding。
- 2026-10-09 10:57 透過正式 `start_mac.command` 載入上述三個 runtime 檔，Redis BGSAVE 已確認後才重啟。launcher PID 61006、worker all PID 61662（10:57:49）、API PID 61664（10:57:51）；三個來源檔修改時間均早於新 API。11:00:51 `/readyz` storage／queue pass，六個 queue 的 queued／started／scheduled／deferred 均 0；stock-analysis 既有 10 筆 stale failed 未增加，其他 queue failed 0。runtime doctor 確認 operational 與 report index 仍走 canonical DB。
- 同時間正式 `last_24h acquisition.sources` 仍為原 **14／20 類嚴格超過 80%**；未達標為 alternative_data 41／77（53.2%）、dynamic_peer_metrics 73／102（71.6%）、earnings_call 93／121（76.9%）、financial_statements 63／168（37.5%）、recent_catalysts 297／437（68.0%）、social_sentiment 77／292（26.4%）。診斷未灌入 SLA，未重新產出模型報告；候選取得不等同可用估值同業、報告品質過關或原 20 類全達標。

## 續查與接入：Yahoo 免登入個股留言原文

- 在 [Yahoo 閎康個股頁](https://tw.stock.yahoo.com/quote/3587.TWO)點開留言，觀測到同站公開 Canvass resource；簽出狀態提供逐篇 messageId、meta.createdAt、PUBLIC/TEXT/COMMENT、namespace、contextId 與 userText。將同一 GET 以一般 curl（無 cookie、登入、OAuth 憑據或偽造 browser headers）再次讀取成功；拿掉導覽 query/request ID 後仍取得十篇原件。URL 中 oauthConsumerKey/Secret 只是公開頁 literal resource names，沒有擷取或保存任何使用者憑據。
- 新 yahoo_stock_comments.py 先讀已解析台股 EQUITY 的 quoteOverview，核對股票代號、市場、正式 context 中公司簡稱、路由、Canvass 實例與 DOM 的唯一 board，再核對每篇同 board/namespace、PUBLIC 原文、UUID 與原始 createdAt。更新日期不能把舊留言變近期；只接受 30 天內、清理後至少五字且非連結/HTML 的正文。最多讀前十篇，不分頁、不採平台 sentimentLabel 或留言總數作樣本/情緒分數。
- 原站目前未觀測到逐篇分享連結。保留原 board URL、批次 source_document_url、message_id、原始發布秒數、quote 與 batch SHA-256；以這些收據識別原件，不偽造 permalink，也不宣稱每句都可當公司事實。兩個普通 HTTPS GET 共用 15 秒期限，各最多 9 秒，沿既有有界 curl collector/2 MB cap、TLS、proxy fail-closed、無 redirect/retry。HTTP 403/429/5xx 及 Retry-After 的原錯誤與冷卻保留。
- 社群 waterfall 維持 CMoney 優先，有合格原文就跳過後續請求。沒有合格原文時查 Yahoo；Yahoo 仍無合格樣本才查 PTT，避免已取得原文後又發出通常只得到舊文的 PTT 請求。來源名稱與 yahoo_stock_direct channel 保留在同一 social_sentiment 類別；不改正式取得率的計算或舊事件。snapshot 重選與 source_record_count 共用收據驗證，缺/壞收據、錯公司/日期/board 不計成功；Yahoo 按 board+UUID 去重，其他來源規則保持原狀。
- 定向來源實測閎康四則、統一證三則、統一超十則，各約 1.3–1.6 秒，收據均可重新核對。信邦前十篇都超過 30 天，維持零樣本。中央再初查手填簡稱「中央再」無法核對 quote 公司名，維持拒絕；改用正式核心快照中既有「中再保 / Central Reinsurance Corporation」身分後取得五則，未新增或放寬 alias。這是當下五檔診斷，不是正式 24h 成效。
- 3587 的完整 force-refresh 已走新 provider wiring，data trust fresh，但 CMoney 本次先取得三篇，因此正確跳過 Yahoo；該次保存快照 source_audit 為 success/3，fetch_id 296fc371f1044636b82f47fa0e944729 在正式 SLA 為零列。採樣腳本最後誤讀 FetchResult.audit_entries，改從已保存的同次快照恢復證據，未重做網路抓取。2855 的實際社群 provider 也先取得 CMoney 一篇、成功/1，未強迫它使用 Yahoo。2851 的實際社群備援結果與部署回讀補於下列狀態。
- 已先重現沒有 Yahoo 備援的 empty 行為；獨立覆核四項 material（缺收據、解析後租約/期限、空 entity 正文、不同 UUID 同文去重）各以失敗測試重現後修正。相關 provider/source/transport/prompt/data-trust/tracking/runtime/settings/storage 隔離回歸 523 passed；獨立 source/transport/selection 覆核 98 passed，無未解重大 finding。測試與活網診斷沒有模型呼叫，不能當新報告品質證明。

- 2851 的自然社群 provider 本次也是 CMoney 先取得三篇、success/3，因此沒有強迫查 Yahoo。另做一次受控 CMoney 空結果故障情境，其他環節與 Yahoo HTTP 均維持真實：1.31 秒由 Yahoo 取得五篇，provider success/5，snapshot 重選與 source_record_count 均五篇，PTT 請求零次、捕捉的 SLA 列零；不冒稱自然失敗已發生或正式面板已改善。最終上述整組隔離檢查仍為 523 passed。
- 2026-10-09 11:26:28 Redis BGSAVE ok 後以正式 start_mac.command 重載：launcher 67614、worker all 68283（11:26:39）、API 68285（11:26:40），worker 與 API cwd 均 canonical backend，全部 runtime Python 修改時間早於新 API。11:27:35 readyz storage/queue pass，六佇列 depth/started/scheduled/deferred 均零；stock-analysis 原有十筆 stale failed 未增加、其他 failed 零。
- 同時間正式 last_24h acquisition.sources 仍為原 14/20 類嚴格高於 80%；職缺 41/77、同業 73/102、法說 93/121、財報 63/168、近期事件 297/437、社群 77/292 未達標，與部署前相同。診斷與受控故障切換未計入正式 SLA；未新增模型報告，不宣稱報告品質已改善或全部目標完成。

## 正式報告驗證：康舒模式 C 財報恢復

- 2026-10-09 11:34 由正式 API 排入既有 6282 模式 C 報告的 full_report 更新，來源為 6282_TW_v3_report_20261009_015318.html；job f16771e135bc4190a0d445f6373b7827 在原 worker 執行、11:37:19 done，約 185 秒，未建立第二個相同工作或重啟程序。新 artifact 為 6282_TW_v3_report_20261009_113716.html，透過 ReportArtifactLocator 核對 HTML/Markdown/data bundle，三份 SHA-256 均與報告索引一致，snapshot_integrity verified。
- 舊報告官方五年 iXBRL 失敗，Yahoo 與 FinMind 年度備援均 partial；本次官方 iXBRL 2021–2025 success/5、cache_hit=false，無年度 Yahoo/FinMind fallback audit。財報 source_error 已清除，data trust 由 partial 53/100 變 fresh 88/100；原則並未補零或放寬科目門檻。
- 同次實際資料另取得兩筆同業指標、67 筆 104 職缺（來源成功但整體職缺覆蓋仍 partial）、3 篇 CMoney 社群、11 場 MOPS 活動及近期原文／公告候選。Yahoo 社群備援沒有被觸發；法說活動不能當已讀逐字稿。SLA 事件帶相同 job_id 與 fetch_id 232c88750be04bd2a26c6fb2dc2dc220，這是有新分析產出的正式工作，與先前不寫入 SLA 的診斷分開。
- 實際模型回應：Agent17/21 gemini-3-flash-preview、Agent18 gemini-3.6-flash、Agent19 先 gemini-3.8-flash，兩次 bounded 稽核修復使用 gemini-3-flash-preview；Agent20 保留無逐字稿規則。未見本 job llm_error/llm_retry/error event，沒有把路由名稱當實際 model identity。
- 新報告 report_lint passed、final_audit passed、無 critical，但 report_conformance/content_credibility 仍 warning，analysis_completeness 仍 quality_warning。證據 gate 是 caution：35/35 數字均經檢查，12 verified、23 unverifiable、0 failed；舊版則 31 checked、8 verified、23 unverifiable。剩餘警示包括沒有主要目標價的方向檢查輸入，以及財期／單位／同語意路徑未能綁定，另有未觀測的財務投射與觀察條件。不得把「發布成功」或「全數已檢查」冒稱全部內容已查證。
- 11:37 正式 last_24h 仍只有原 14/20 類嚴格高於 80%；職缺 42/78（53.8%）、同業 74/103（71.8%）、法說 95/123（77.2%）、財報 64/169（37.9%）、近期事件 301/441（68.3%）、社群 78/293（26.6%）。更新改善這份原來財報異常的實際報告，沒有達成原 20 類全部 >80%。
- 另重新取得 [信邦 2021 原始股東會財報附錄](https://www.sinbon.com/files/2022_3023_20220530FE3_20220531_100147.pdf)，bare host 明示 302 至 www，同 host 原件下載 1,525,528 bytes、84 頁。原 PDF 保存 docs/evidence/source-acquisition/20261009/sinbon-2021-shareholder-handbook.pdf。原件第 26 頁渲染並視覺核對 2021/2020 合併現金流，列不動產設備購置 -541,353 仟元與其他無形資產減少 +22,673 仟元；沒有明列取得無形資產支出。這份原件也不能證明 gross purchase 為零，不回填 FCF。搜尋到的 113 年年報是 2023 年報表，不能代替 2021 年現金支出科目。此輪未修改 runtime 檔或放寬品質門檻。

## 月營收原分析證據綁定與正式回讀

- 上述康舒新報告的原分析輸入已保存 `2026年9月: NT$38.33億`，但舊金額核對只支援年度／TTM，因此同月份營收仍未能核對。新增有界的 canonical 月營收 adapter：同公司、唯一明示年月、TWD／NTD 幣別與唯一同月份格式列才可核對；不搜尋任意快照字串、不用其他月份或年度／TTM代填。仍用原分析輸入 hash 與 cutoff，格式列只核對已保存的顯示金額，`independent_primary_source_verified=False`。
- 先重現缺少月營收路徑，再補覆核指出的他公司前後綴、累計／截至／月均／季度／全年口徑、postfix 金額、共享情境標題與公司 alias 內含「達」的失敗案例後修正。相關金額、evidence、analysis-input、projection、current-quality 與 content-credibility 隔離回歸 **551 passed、1 skipped**；skip 是原有 optional private complete report replay。獨立最後覆核 **128 passed**，沒有未解重大 finding；原容差與年度契約未改。
- 同一份 `6282_TW_v3_report_20261009_113716.html` 重播，35 筆全數檢查，從保存結果 **12 verified／23 unverifiable／0 failed** 改善為 current rules **15／20／0**；三筆新增核對均指向原 `analysis_evidence.sections.analysis_input.data.recent_monthly_revenue[5]`，cutoff `2026-10-09T03:34:35.142547+00:00`。未驗證仍有財務投射 8、財期／幣別／單位 8、口徑未綁定 3、語意路徑缺漏 1。品質 verdict 保留 caution，並非官方事實認證或全面品質通過。
- 12:11:31 六佇列均無 queued／started／scheduled／deferred，Redis BGSAVE ok，確認只有本輪 `evidence_financial_amounts.py` 比前次 API 新後，以正式 `start_mac.command` 載入。launcher 75754（12:11:48）、worker all 76215（12:11:59）、API 76217（12:12:00）；兩程序 cwd 均 canonical backend，runtime doctor 核對 operational／report-index 路徑正確。12:12:55 `/readyz` storage／queue pass，六佇列仍空，10 筆既有 stale failed 未增加。
- 正式 `/api/reports?q=6282&pipeline=v3&include_versions=true` 的 `markdown+snapshot.current_rules` 投影回讀確認 **15 verified／20 unverifiable／0 failed**。三份原 HTML／Markdown／data 的 SHA-256 均未變，未重寫保存 gate、歷史來源事件或 artifact。12:12:56 原 `last_24h acquisition.sources` 仍 **14/20** 類嚴格高於 80%；六項未達標數值與 11:37 相同。本輪沒有新增模型報告或來源 SLA 成功事件。

## 新免費候選：1111 TECH+ 公開職缺 JSON

- 新查 [1111 TECH+ 科技專區](https://techplus.1111.com.tw/jobs)，免登入一般 HTTPS GET 可取得服務端已渲染的職缺與 Nuxt 原始資料。其公開 `/robots.txt` 為 `Allow: /`；公開職缺 view/client 明示 `GET /api/jobs`，參數包含 `keyword`、`d0`、`c0`、`page`、`pageSize`、`sort`。以頁面實際使用的 58 個子職類、第一頁十筆作定向查詢，沒有 cookie、憑據、偽裝 browser headers 或挑戰破解。帶公司 keyword 的 HTML 頁對康舒／信邦各於 15 秒逾時，但直接讀同站公開 JSON 成功。
- 對齊上述子職類的康舒 JSON 查詢 **HTTP 200，17,326 bytes，0.47 秒，十筆**；公司名均 `康舒科技股份有限公司`，每筆具 job ID、organNo 436068、原文／公司連結、`dateIn`、`dateChange` 與正文。然而十筆 `dateIn` 均在 7 月，10 月 6 日是更新日，不能當近 30 天新刊登。平台 `total_rows=27` 是技術職類篩選後的宣稱總數，亦不是本次逐筆取得數。
- 同範圍的統一證券查詢 **HTTP 200，15,240 bytes，0.48 秒，十筆**，其中兩筆建立日為 10 月 7 日與 9 月 23 日。平台公司名為 `統一綜合證券股份有限公司-總公司 (統一證券)`、organNo 410000；仍須完整核對發行人身分／別名及逐筆開放狀態，暫不當 verified 近期職缺。信邦／閎康的初查包含額外五個父職類，各 **HTTP 200、零列、約 0.36 秒**，未重查子職類範圍；這些篩選結果不能推定公司沒有徵才。
- 原始 HTML、公開兩個 client/view 檔、robots、六份 JSON 原件及 request URLs／SHA-256 保存至 `docs/evidence/source-acquisition/20261009/techplus-free-entry-proof.json` 所列檔案；初查與對齊子職類的查詢各自保留。這是新找到且已實際讀取的免費入口，尚未接入正式 provider，也沒有計入來源 SLA；近期建立候選不等於已通過公司與當前開放查核。
- 同頁另發現 [科技島新聞](https://www.technice.com.tw/issues/semicon/322652/)的 WordPress 公開文章 metadata／原文入口；[WordPress 官方文件](https://developer.wordpress.org/rest-api/reference/posts/)界定 `date` 為發布日、`modified` 為更新日。正式機器對康舒／崇越的限定近 30 天 JSON 查詢各在 15 秒連線逾時，robots 查詢亦在 10 秒逾時、沒有原始回應；搜尋／瀏覽器工具看得到文章，不能當正式下載已成功。本輪不接入此新聞備援。

## 續作：正式缺漏報告重跑與聯華食品部門入口

- TECH+ 候選再逐筆讀康舒／統一證券原文，HTTP 200 仍是安全驗證頁，沒有 JobPosting 或可核對的開放欄位；`api.1111.com.tw/corp/410000` 回 301，未自動跟隨。近期建立候選仍未接入正式職缺備援。查詢原 24 小時來源紀錄時，先以 `provider_acquisition.observation_kind` 排除流程摘要，確認最近仍空的職缺股票為 6214、2891、1229；沒有用摘要的零列猜測來源失敗。
- 正式完整重跑精誠原模式 D 報告：job `bc893f0e8c764dada931d5dd236c1a7c` 完成並產出 `6214_TW_v4_report_20261009_123411.html`。五年財報由原 2022–2025 補為 2021–2025，data trust 由 stale 52 變 fresh 88；同次正式來源有 90 筆 104 職缺、2 篇社群、2 個完整同業指標及官方財報 success/5。HTML／Markdown／data SHA-256 均與索引一致；lint、final audit passed，但 conformance／content credibility warning，evidence caution（13 verified、11 unverifiable、0 failed），analysis completeness quality_warning，不能當全面品質通過。
- 中信金原模式 D 正式重跑 job `e27f6baeb42d4a78854d11a5215de2cb` 完成，產出 `2891_TW_v4_report_20261009_124820.html`。data trust 同樣 stale 52 → fresh 88，五年官方金融業原件 success/5、4 筆金控本體官方職缺、1 篇社群、5 個同業指標。三份 SHA-256 與索引一致；lint、final audit passed，evidence approved（8 verified、0 unverifiable、0 failed），但 conformance／content credibility warning、analysis completeness degraded 仍保留。
- 聯華完整重跑 job `223a52bc7c7c4f458eed52fdf0b7b487` 取得五年官方年報、14 筆職缺及 3 篇社群，但同業仍為零。Agent24 曾遇模型暫時不可用／至少 61 秒冷卻，同一 job 後續回到 started 並產生回應；最後在 `report_quality_blocked` 終止，未發布。原因包括依賴重建失敗、修復次數上限及主力籌碼角色同主體／同期間法人淨額不符，沒有放寬千股／張／千張與買賣方向規則。三個正式 job 各有獨立 fetch_id，完整摘要保存 `docs/evidence/source-acquisition/20261009/formal-source-rerun-summary.json`；成功回應事件的 model_id 不冒稱獨立供應商身分認證。
- 新免費入口為 [TPEx 聯華個體公司鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=1229)與[食品鏈加工食品名單](https://ic.tpex.org.tw/introduce.php?ic=M000)。公司鏈同時列食品加工與雲端系統整合，因此不能用純食品公司代表持股公司整體。本次只接食品部門四個數值候選：大統益 1232、福懋油 1225、統一 1216、南僑 1702；兩份原頁、同段 desktop/mobile 身分與最新主檔逐筆核對。主檔是全市場最新有效日期、最舊七日，原日期明示，不要求休市日供應商必須發布當日版本，也不把昨日日期改寫成今日。原件未標分類發布日；整體業務與財期可比性仍未核對。
- 新 `official_food_processing_peer_cohort.py` 只接 1229；沿 `peers.py` 原十次候選下載／五筆輸出上限，與既有固定 TPEx curl 傳輸、同 host 冷卻共用。兩頁共十二秒、各六秒／250 KB，TLS、無 retry／redirect、403／429／5xx 與 Retry-After 保留；候選必須有 24 小時內、有限且非未來的取得時間及兩份 hash。公司外的區塊、錯段、舊／改名主檔、損壞收據不供應候選，退件一筆不清除其他獨立有效公司。每筆只保存該公司的指標，`comparison_scope=food_processing_segment`、`business_comparability_verified_current=False`；prompt／snapshot 自動估值仍為零。
- 先以公開入口重現空候選，再實作。來源／peer／prompt／snapshot／provider／acquisition 及專案 tracking／runtime／settings／storage 隔離回歸 **192 passed**；獨立 scoped 覆核 **55 passed**、無未解重大 finding。真實候選／指標直讀 **4.49 秒**，四筆皆完整，prompt 與自動估值可比數均零；定向診斷攔截來源 ledger，正式同時間無 job 的 1229 觀測列 **0**。證據保存 `food-processing-live-probe.json`，不以這次探測提高正式來源分子。
- 12:53:12 Redis BGSAVE ok、六佇列 queued／started／scheduled／deferred 均零後，由正式 `start_mac.command` 重載；確認只有本輪三個 runtime 檔比前次 API 新。launcher 83503（12:53:38）、worker all 83857（12:53:48）、API 83859（12:53:49），cwd 均 canonical backend；runtime doctor 核對 canonical DB，readyz storage／queue pass，原十筆 stale failed 未增加。
- 部署後由正式 `/api/report/1229_TW_v4_report_job_d2b7a2d73e80.html/refresh/data` 更新現有資料，**26.54 秒**取得四筆 complete 食品候選、五年財報、14 筆職缺與 3 篇社群，data trust partial 50 → fresh 88。保存原分析 evidence 與 gate，HTML／Markdown 保留，三份 artifact hash 與索引一致，`decision_freshness=needs_rerun`；資料更新不是新模型報告或新的投資結論。prompt／自動估值仍排除這四筆候選。
- 此 API 既有 `record_provider_sla=False` 抑制 provider-result 整批寫入，但底層真實 HTTP 觀測仍保存：本次另有 **12 筆 fetched、8 筆 local_block**，包括官方法人、MOPS、公告、籌碼與搜尋；它們不是流程摘要，不能刪除或假稱零紀錄。本次食品同業的整批 success/4 只在報告快照，沒有以其冒充來源面板的新增成功。完整驗證保存 `food-processing-formal-refresh.json`、`food-processing-completion-check.json`。
- 13:02:40 原 `last_24h acquisition.sources` 仍 **14/20** 類嚴格高於 80%；未達標為職缺 **45/81（55.6%）**、同業 **76/106（71.7%）**、法說 **102/130（78.5%）**、財報 **67/172（39.0%）**、近期事件 **311/453（68.7%）**、社群 **81/296（27.4%）**。新入口、資料刷新及兩份新報告是實際進展，不能當成原 20 類全部達標；聯華仍需修正模型法人數值敘述後才能發布完整更新。

## 續查：新版 MOPS 月索引與法人逐日句型

- 保存中信金正式 source audit 後確認：EZSearch 返回 51 列、其中 41 筆近期重大訊息，但舊安全上限三十筆使來源只採最近十篇。新免費入口是 [MOPS 新版歷史重大訊息](https://mops.twse.com.tw/mops/#/web/t05st01) 的公開 `POST /mops/api/t05st01`；前端 `assets/t05st01.js` 明列 companyId/year/month/firstDay/lastDay。2026-10-09 公開直讀 9 月三十九筆、10 月兩筆；另一個前端提供的 `t05st01_detail` 可取得完整「說明」，非搜尋摘要。原始公開收據為 `2891-new-mops-sep-index.json`／`2891-new-mops-oct-index.json`／`2891-new-mops-detail.json`。
- 接入 `twse_json_history.py`：僅在 EZSearch 超過三十候選且無拒絕列時備援；最多三個月份、六十四候選，逐列核對公司、市場、日期時間、非空主旨及 detail action 的發行人／市場／發言日期／序號。完整月索引必須含既有候選且總數一致，再逐篇核對官方 MOPS HTML 原文；主旨、發行時間秒、正文與 hash 仍沿原門檻。索引不一致、漏篇、正文截斷或超過上限都保留 partial。
- `twse_history_transport.py` 使用同一二十秒期限，每次傳輸最長四秒；原文與月份回應各 256 KB，EZSearch 2 MB，子程序 pipe 亦有硬上限及回收。索引或原文遇 403／429／5xx 停止後續原文，保存實際拒絕及 Retry-After；截斷 header 不採其前綴。新版固定 API 預選既有普通 httpx 子程序，舊官方 HTML／EZSearch 使用 curl；沒有拒絕後輪替身分、cookie、重試、重導或停用 TLS。EZSearch 真 JSON 的 text/html 標籤僅限該端點且需先 JSON 解碼，HTML 安全頁仍拒絕。新 provider 快取 v3 不沿用舊 partial 快取。
- 保存 41 筆公開索引先重現只取十篇及 429 後仍發十次原文請求，再修正。來源、合併、acquisition、追蹤與 runtime/storage 隔離回歸 **125 passed**；獨立來源覆核 **45 passed**。審查的索引拒絕、最後一篇解析跨 deadline 及 Retry-After 截斷三項均修正。真實來源直讀在 **13:34:13** 取得 **41/41 原文、window_complete、19.016 秒**，45 次傳輸且無拒絕列；保存 `mops-monthly-2891-live-proof.json`。先前兩次 partial 的收據保留；診斷使用臨時 DB，正式 SLA 不寫入，不能當成來源類別達標。
- 聯華正式失敗 job `223a52bc7c7c4f458eed52fdf0b7b487` 的 Agent23 原句是「10/07 與 10/08 單日法人合計轉為淨買超，分別為 523.37 千股與 846.27 千股」，凍結資料同兩日也恰為 523.37／846.27。舊 gate 未識別此句型，把第一數值與兩日合計 1369.64 比較；因此前節「需修正模型數值敘述」的判斷須修正為本例存在 gate 誤判。新增精確的明示單日／兩日期／兩數值句型，仍逐日查證，數值容忍度、方向、主體、單位、來源可見性及合計規則不變。
- 法人 gate 先 **2 failed** 重現；獨立覆核再重現前置區間、匿名衝突主體及非法月份／ROC 年份被截掉的漏驗，僅對新 explicit_daily 文法封閉 prefix/suffix 及第一日期左邊界。最終 **289 passed**、獨立三檔 **72 passed**。完整保存 Agent23 文本及同一凍結 input 唯讀重播，該法人 issue **1 → 0**，沒有模型呼叫，也不改寫舊失敗 job。缺第二日、wrong value/date/population/unit/sign、第三項或混期間仍阻擋。收據 `institutional-1229-daily-pair-replay.json` 保存 checkpoint ID 與原文 hash；離線 replay 不等於正式新報告成功。
- 六佇列無 queued／started／scheduled／deferred，停止既有 worker 並 Redis BGSAVE 後由 `start_mac.command` 重載本輪七個 runtime module。launcher **94262（13:47:37）**、worker all **94290（13:47:38）**、API **94292（13:47:39）** 均為 canonical backend；doctor、readyz storage／queue 通過。來源與 gate 共 **414 passed**，獨立 **45／72 passed**；`mops-monthly-release-proof.json` 保存本輪七份 module SHA 與 runtime 真相，未 commit／push。
- 正式中信金資料刷新首輪 **34.67 秒**，新月索引完整，但第九篇原文收到真實 **HTTP 502**，立即停止並保存八篇／partial，host guard 冷卻六十秒。保存 first-partial 收據；冷卻到期後，僅將這一個衍生 partial provider cache 的 freshness 失效（保存原值／取得時間／backup，沒有重設 provider guard 或改寫 ledger），再由正式 API 定向刷新一次。來源 **11.395 秒、41/41、window_complete、success、非快取、45 次傳輸**，fetch_id `26c5d8a38a4b43ada336b59481746070`；最終 snapshot 的 source audit 與 source cache 均一致。API 回應的 source_audit 是部分增量，不能只查回應而忽略完整保存快照。三個 artifact hash 與 reports 索引一致；原 HTML／Markdown／analysis evidence／quality gates 保留，decision freshness needs_rerun，此資料更新不是中信金的新模型結論。收據 `mops-monthly-formal-refresh.json`。
- 修正後聯華完整正式重跑 job `6736e0e296604595b9d81c5d192a3a6e` **completed／done**，產出 `1229_TW_v4_report_20261009_135236.html`；舊失敗 job 仍 failed，未回寫成功。新三個 artifact hash 與 reports 索引一致；data trust fresh **88**、無 critical／stale，lint 與 final audit **passed**。仍保留 evidence **caution（8 verified、6 unverifiable、0 failed）**、content credibility／conformance warning，以及 observed catalyst evidence scope mismatch 引起的 analysis completeness degraded；不能當全面品質通過。四筆食品數值候選的整體可比性仍不成立。完整收據 `institutional-1229-formal-rerun-proof.json`。
- 本輪結束的原 `last_24h acquisition.sources` 仍 **14/20** 嚴格高於 80%。未達標為職缺 **46/82（56.1%）**、同業 **77/107（72.0%）**、法說 **106/134（79.1%）**、財報 **68/173（39.3%）**、近期事件 **314/457（68.7%）**、社群 **82/297（27.6%）**；free source／報告修復是實際進展，原全類別驗收仍未完成。readyz pass，佇列 depth／started／scheduled／deferred 均零、十筆原有 stale failed 未增加。保存 `mops-monthly-completion-check.json`；資料刷新抑制 provider batch，實際底層 HTTP 觀測仍可能追加，不以診斷或重標歷史衝高比率。

### 續查：既有原件足夠時停止重複搜尋

- 聯華 1229 的上一份正式輸入中，補充搜尋原始 22 筆、可用 7 筆、拒收 15 筆（公司不符 2、缺日期 6、重複 7）。擴大 Google RSS 首輪由 8 到 24 筆仍只有 7 筆通過，公司不符的其他結果不能補數；保存 `alternative-1229-search-gap.json`。其中 [富果 9/30 聯華備忘錄](https://blog.fugle.tw/post/earnings-call-1229-2026-09-30) 原頁有文章日期與 JSON-LD，但已在 RSS 合格七筆中，不能再算新增獨立資料。它是二手法說整理，不能升格成官方逐字稿或核心財務事實。
- 富果原始 HTML 另含 [官方法說影片](https://irconference.twse.com.tw/1229_19_20260930_ch.mp4) 與 [官方簡報路徑](https://mopsov.twse.com.tw/nas/STR/122920260930M001.pptx)。固定入口普通 HEAD 查驗：影片 HTTP 200、video/mp4、64,332,782 bytes；簡報 HTTP 307，未取得簡報內容。這兩條只是可追溯候選，未下載、轉寫或接入，不將影片 header 200 算法說內容取得成功，也不追隨未核對重導。收據 `fugle-linked-official-conference-entry-check.json`，正式 SLA 寫入零。
- 真正瓶頸是主來源已有足夠資料仍並行補搜。`catalyst_search_plan.py` 重新以同一公司、30 日窗口、原八筆／三發布來源品質 gate 評估，要求至少兩個 curated feed，各至少三筆。官方來源必須 window_complete，原文 title/body/hash 與官方 issuer／日期／秒／序號一致；新鮮快取只採原 fetched_at_epoch 三十分鐘內，拒絕巨大整數、NaN／Inf／bool、未來或舊時間。SEQ_NO=1/01/001 去重為同一原件，不能靠別名湊足三篇。Free waterfall 仍要求 company-time-v1／eligible_evidence。
- Alternative Search 只有真實缺口才執行，使用等待主來源前建立的原總期限；前置檢查、admission 後及第一查詢前均分開處理過期，零查詢 local_block／HTTP False／零 API units，已送出的空查詢仍為真實嘗試。其他市場的並行計畫與所有原品質門檻保持。最初三個失敗行為測試與覆核再找出的時間溢位、公告別名、admission 過期均先重現再修正。第一輪 **133 passed**，獨立 **42 passed**。
- 實際 Free news waterfall 五筆加官方六筆，**2.969 秒**，原 gate 選八筆、六發布來源；此次來源診斷攔截正式 ledger 寫入，不能提高正式成功率。以最終 helper 重選同一保存原件仍八／六，無新 HTTP；見 `conditional-catalyst-search-live-proof.json` 與 `conditional-catalyst-search-saved-proof-recheck.json`。
- 六佇列空、停止舊 worker、Redis BGSAVE ok 後由正式啟動器載入第一版：launcher **5399（14:52:26）**、worker **5427（14:52:27）**、API **5429（14:52:28）**，canonical cwd／doctor／readyz pass。正式刷新既有 `1229_TW_v4_report_job_d2b7a2d73e80.html` **20.731 秒**，Alternative Search 實際 not_applicable、local_block、HTTP False、零筆，existing_evidence 八／六。data trust fresh 88；HTML／Markdown／分析 evidence／五項品質 gate 保留，三份 artifact hash 與索引一致，仍為資料更新而非新模型結論。收據 `conditional-catalyst-search-formal-refresh.json`。
- 同一次刷新揭露後續 Yahoo 仍被舊兩 feed 判斷觸發，因此新增四個行為案例，先重現 **2 failed**，再使 Yahoo 共用嚴格主來源證據判斷；足夠時同樣 local_block／HTTP False／零筆，不足仍使用既有 fallback，未配置 Alternative Search 時亦可採已核對主來源。包含來源、合併、搜尋、追蹤、runtime／storage 的隔離回歸 **170 passed**；第二版尚待部署及正式再驗，第一版載入憑據不可當成第二版。
- 為修復過期報告，正式 9945 完整重跑 job `a7193e80b6cd4b79a86ba705a9dcc6e1` 已取得五年官方財報、四個完整營造數值候選、五篇完整官方公告、二十筆職缺、二篇社群，data trust **fresh 88**，無 critical／stale。候選仍不代表全公司可比。模型在 Agent23／final-audit 修正遇到真實 HTTP429（細項未明），保存同一 job 的 checkpoint thread 與凍結輸入，scheduled **15:01:08 台灣時間** 再試；此時報告未完成，舊報告不改寫為成功。見 `conditional-catalyst-search-9945-checkpoint-proof.json`。
- 第二版獨立覆核 **46 passed**、無 unresolved material finding。重載前只新增 `workflow.py` 變動；queued／started／deferred 為零、僅上述同一重試工作 scheduled 一筆，核對 Redis 原 job id／timestamp、停止空閒 worker、BGSAVE ok，排程與 timestamp 未變後才停止舊啟動器。正式 launcher **7266（15:01:05）**、worker **7294（15:01:06）**、API **7296（15:01:07）**，四份 module SHA／mtime、canonical cwd／doctor／readyz 通過；沒有取消或改期 retry。收據 `conditional-yahoo-release-proof.json`，未 commit／push。
- 第二版正式聯華資料刷新 **34.065 秒**，此次官方六篇為 success／非快取；Alternative Search 與 Yahoo 均 not_applicable、local_block、HTTP False、零筆／零 API units，保留八筆合格主來源，合併 Recent catalysts 為 **success**。HTML／Markdown／分析 evidence／五項 gate 保留，三份 hash 與索引一致，data trust fresh 88。這次官方原文需重取，第一輪採快取，因此兩次總耗時不可當相同條件的速度比較；也不以資料刷新或零請求 skip 提高正式成功率。收據 `conditional-yahoo-formal-refresh.json`。
- 9945 重試於原排程接續同一 checkpoint，完成 `9945_TW_v4_report_20261009_150150.html`，job **completed／done**，保存來源稽核與凍結輸入，未重新取得資料；續作模型請求只涉及 Agent23／24。三份 artifact hash 與索引一致，data trust fresh **88**、無 critical／stale，lint／final audit **passed**、evidence **approved（8 verified、0 unverifiable、0 failed）**。仍有 content credibility／conformance warning：市場觀測日期、同日成交量口徑、即期 FCF 期間及法人原始證據尚未獨立核驗；analysis completeness degraded（deterministic_fallback、source_evidence_unverified）。本輪沒有放寬這些 gate 或把 completed 當成全部品質通過。收據 `conditional-search-9945-formal-rerun-proof.json`。
- **15:03:14** 正式原近 24 小時仍 **14/20** 類嚴格超過 80%：職缺 **47/83（56.6%）**、同業 **78/108（72.2%）**、法說 **110/138（79.7%）**、財報 **69/174（39.7%）**、近期事件 **316/461（68.5%）**、社群 **83/298（27.9%）** 尚未達標。readyz pass，queued／started／scheduled／deferred 為零，十筆原有 stale failed、零新增 failed。完整快照 `conditional-search-completion-check.json`；原全類別目標保持未完成。
- 接續調查 5314，固定 [MoneyDJ 食品生技同頁名單](https://www.moneydj.com/z/zh/zha/zh00.djhtm?A=C017108&B=6) 普通 GET 有八秒硬期限／200 KB 上限／無重導或重試，**0.560 秒、HTTP200、30,481 bytes**。以當期 stock master 核對，5314 世紀* 與漢田生技1294、生合1295、葡萄王1707、生達1720、杏輝1734 均有 **2026-10-08** 原頁觀測日期；三十個原始候選只採既定最多五筆。`moneydj-5314-current-candidate-probe.json` 保存頁面 hash、公司名／市場與日期核驗，正式 SLA 寫入零。它只提供研究候選，數值及全公司業務可比性仍未驗；尚未接入 dynamic_peer_metrics，也沒有據此解除 prompt 或自動估值排除。

### 續作：世紀公開候選的完整數值取得

- 沿用原全部二十類嚴格超過 80% 驗收。開工正式原近 24 小時仍 **14/20**，同業 **78/108（72.2%）**；5314 最新既有報告 `5314_TWO_v3_report_job_6d4d98252427.html` 的同業為零筆／unavailable，data trust stale 52。MoneyDJ 的「同業評比」`/z/zh/zhk/zhk.djhtm?A=C017108` 與「同業財務」`/z/zh/zhl/zhl.djhtm?A=C017108` 均導向會員登入，沒有採用或繞過登入。本輪改用已核對公開名單與既有免費數值來源。
- 五個公開候選的普通 yfinance SDK 實測都有八項指標，資產週轉率可沿相同年度損益／資產負債表 **2025-12-31** 原欄位計算；僅確認數值可取得，沒有證明整體業務或財期可比。此 probe 約 **1.010 秒**，SDK HTTP cache 狀態未知，不能當完全未快取速度；來源診斷攔截 SLA 寫入零，`moneydj-5314-numeric-feasibility.json` 保存逐欄數值／缺欄與身份檢查。
- 三個行為測試先重現公開候選沒有數值入口、缺欄場景失去整批資料，以及被新版主檔移除的股票仍拿舊列當「當期」（**3 failed、1 passed**）。`moneydj_peer_cohort._current_identity` 現在只採全市場最新有效主檔日期的同代碼、同名稱／市場；休市仍保留實際最後交易日。新 `moneydj_numeric_candidates.py` 只替 5314 回傳原頁候選，`peers.py` 沿既有十次下載／五筆輸出上限及欄位來源取得數值，要求這類候選的 live quote 同 symbol／EQUITY，拒絕錯公司。缺欄保留 None／partial，沒有補零或降低原 completeness 門檻。
- 本類數值仍 `published_segment_candidate`／`business_comparability_verified_current=False`，分類只來自發布者同頁名單，不代表 5314 全公司可比；不進 prompt 的同業比較與 snapshot 自動估值。每欄保留原 yfinance reporting-period 未提供註記；資產週轉率仍採同一年度日期，不混 TTM 營收與年度資產，也不推論跨公司財期可比。
- 新 `moneydj_cohort_transport.py` 固定一個普通 curl HTTPS URL、無重導／重試／自訂身份，七秒傳輸與八秒解析後期限、200 KB 及子程序管線上限；403／429／5xx 與 Retry-After 優先保留，慢速或超量真實無網路子程序被停止並收回。來源沿原 persistent cooldown；冷卻／proxy block／逾時前阻擋皆零 HTTP，實際已啟動嘗試不偽裝 skip。`acquire_published_cohort` 讓 discovery／數值共用 **v2、四小時** cache，保留 bounded original bytes／SHA；回讀重新解析 bytes/hash、發布日期、公司與最新主檔，不信任 cached parsed fields，已退市舊列不採且保留其他獨立有效原件。舊 v1 cache 保留，未重設 guard 或 ledger。
- 來源、候選／估值隔離、新聞 fallback、合併、取得率、追蹤與 runtime／storage 的 **208 項**隔離回歸通過，包含實際 30,481-byte 原頁 fixture、stale／future／NaN／巨大時間、錯 body/hash/URL、parsed cache 修改、缺欄、錯 quote、冷卻零 API units，以及 slow-drip／overflow 子程序退出。本輪新增 fixture test 首次收集有括號語法錯誤，已修正後完整重跑通過，不能把收集失敗算行為 red。
- 真實新 `DynamicPeerMetricsProvider` 路徑 **3.789 秒、success、五笔 complete、五次候選下載**，prompt 與自動估值仍零合格同業，正式 SLA 寫入零；`moneydj-5314-numeric-provider-live-proof.json` 保存 runtime module SHA、每欄與比較邊界。隨後 discovery 由同一 v2 原頁回 `skipped_fresh_cache`／零 HTTP，頁面 SHA 與原取得時間一致；generic source audit 將 epoch 正規化為 fetched_at ISO，回讀 ISO 比較才是正確契約，初始讀不存在的 audit epoch 欄位失敗收據亦保留。`moneydj-5314-shared-receipt-proof.json` 核對兩流程同一憑據；這些診斷不當正式部署或成功率成效。
- 獨立覆核找出真實 cold 取得在 numeric→discovery 共用快取時會漏失 HTTP 收據，以及未標財期的 quote totalRevenue/totalAssets 可能搶先填 asset_turnover。先重現 **6 failed** 再修正：numeric getter 保留 canonical cohort source_audit，沿 `peers.related_entries`、typed provider、missing-core flatten 及 legacy sync 回到來源保存；後續 cache reader 不改為 HTTP True。published asset_turnover 強制先留 None，只使用同年度函式，沒有共同年度保持 partial；其他 legacy 計算不變。獨立 **66 passed** 與公共 cold success／failure→later cache／cooldown probe 均通過，真實 HTTP child 各一筆，後續零 HTTP／零 API units。
- 接著主代理發現 sync typed source 若仍留在 audited scheduler 會對同一 FinMind/yfinance 做兩次 resilience admission，兩個行為案例先 **2 failed**。只對 5314 改由 copy_context 的獨立 typed future 與法人同時執行，移出外層 audited spec；parent 與 related child 各保存一次，其餘 ticker 原 scheduler 保持。最終來源／候選／同業、sync、fixture／audit、新聞、追蹤及 runtime／storage **247 passed**；最新實際 provider **3.168 秒、五組 complete、同財年資產週轉率、估值與 prompt 排除、單一 related 原頁 cache 收據**，正式 SLA 寫入零。最終七份 module SHA 與收據見 `moneydj-5314-final-numeric-live-proof.json`。
- 部署前現場出現八個既有 watchlist 任務，正依模型冷卻接續 queued／started／scheduled；第一次 idle 檢查未通過，重啟腳本在任何停止動作前退出，舊 API／worker 保持運行。先等待實際任務轉到 idle，保留原 scheduled IDs／timestamps，再進行已授權重載，不為部署取消、改期或重設 quota 保護。本輪沒有額外排入模型工作。
- 最後 sync future slice 的獨立檢查 **45 passed**，確認 copy_context 保留 fetch identity、只一次 resilience admission、parent／child 各一笔，2330 仍用原 scheduler；無未解 material finding。七個本輪 runtime 檔案是上次啟動後唯一程式變動。queued／started／deferred 為零且八筆 scheduled 的最近到期仍超過三十秒時，核對原 ID／score、停止空閒 worker、BGSAVE ok、再次確認八筆 ID／score未變後重載。正式 launcher **17004（15:57:34）**、worker **17032（15:57:35）**、API **17034（15:57:36）**，canonical cwd、七份 SHA／mtime、doctor／readyz 通過；未 commit／push。收據 `moneydj-numeric-release-proof.json`。
- 重載後正式 `/api/report/5314_TWO_v3_report_job_6d4d98252427.html/refresh/data` **18.607 秒**成功，原零筆同業數值變為五組完整候選，含各欄來源與同財年資產週轉率。完整保存快照的 typed peer audit 為 success／五筆，原頁相關收據與後續 discovery 為新鮮 cache／HTTP False，沒有為驗證製造 cold 請求。data trust **stale 52→fresh 88**、無 critical／stale；候選 whole-business False、prompt 與自動估值仍零合格同業。HTML／Markdown／analysis evidence／五項 quality gate 保留，三份 hash 與 reports 索引一致；snapshot decision_validity_status **needs_rerun**、index analysis_text_stale **1**。此資料刷新不是新模型報告，也不是取得率 benchmark。完整收據 `moneydj-5314-formal-refresh-proof.json`。
- 部署後稍晚核對原排程，3023 已於其原 due **15:59:51** 自然接續（第一 event 15:59:51.527），其餘七筆 ID／score仍相同；八筆全數可追溯保留或按原到期執行。晚讀取的 zset 與重載前不同，是 due 工作已自然執行，不能把它誤當排程遺失或宣稱晚讀取完全相等。3023 於約 **16:00:41** 因報告契約／證據 gate 擋下而未發布，保存 `moneydj-existing-3023-quality-block.json`；本輪没有降低品質檢查，單檔資料修復不能外推全部報告品質通過。
- **16:03:05** 正式原 `last_24h acquisition.sources` **15/20** 類嚴格超過 80%，法說 **125/143（87.4%）** 已達標；尚不足為職缺 **51/81（63.0%）**、同業 **82/108（75.9%）**、財報 **74/166（44.6%）**、近期事件 **315/457（68.9%）**、社群 **74/264（28.0%）**。自然 work／舊事件離窗也會改變比率，沒有將15/20全部歸功於本輪5314刷新或未執行搜尋。七個既有 watchlist 任務仍等待重試；原二十類全部超過80%與全面報告品質驗收仍未完成。快照 `moneydj-numeric-completion-check.json`。

### 續找：發行人完整新聞與證券商自建招募入口

- [三陽工業公開新聞索引](https://www.sanyang.com.tw/newslist)在正式機器普通 HTTPS GET 回 HTTP200、45,399 bytes，列出 [10 月 2 日淨零綠生活原文](https://www.sanyang.com.tw/busnessnews-page693)。原文 HTTP200、31,844 bytes，有明確 `Oct 02 2026`、公司名稱與完整正文；既有 `select_company_records` 原門檻接受一篇。同一 URL 的 web 工具快取索引一度仍顯示八月為最新，因此本輪結論採活網原頁，不把搜尋快取當今日實況。這是公司自行發布的 ESG 活動，不推論為訂單、盈餘或股價催化已實現；僅驗證此篇，未宣稱全窗口完整，也尚未接入正式 provider。
- [信邦公開新聞頁](https://www.sinbon.com/news)用 Vue，普通 HTML 只有殼。從實際頁載入的公開 `app.js` 找到其 `GET /api/news/items` 與 `GET /api/news/detail/<slug>`；不用金鑰、登入或會話權杖。列表 HTTP200、581,229 bytes，回 176 列，但 pagination 標 184，不能以列表計數推論全量覆蓋。[10 月 6 日 electronica 公告原文](https://www.sinbon.com/news/from-connection-to-impact-sinbon-builds-sinbon-city-at-electronica-2026-hall-a3-booth-341)的明細 API HTTP200、2,907 bytes；id `217`、逐日日期 `2026.10.06`、title、description 與列表一致。文章是宣布 11 月活動，發布日與未來活動日分開；中文 `lang=tw` 列表此篇仍用英文，不能假定切語言會補中文公司名。
- 信邦現行輸入只有英文全名，沒有簡稱 `SINBON`，故新原文由現行選擇器正確拒絕為 `issuer_unverified`。當日證交所 [公司主檔](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)原觀測日為 **2026-10-08**，3023 同列明示信邦電子股份有限公司、英文簡稱 `SINBON`、網址 `www.sinbon.com`。只在診斷副本加入這個有官方依據的別名後，原選擇器接受一篇；未修改正式 identity、未放寬全域公司比對。正式接入前需要同 ticker／官網 host／原觀測日及原件 hash 的別名憑據。另一個 `GET /api/invnews/items` 可讀 192 筆投資人訊息，但 `publish_on` 只有 `2026/10` 等月份，不能補成 10 月 1 日或當作精確近期事件。
- [統一證券官方人力資源頁](https://eservices.pscnet.com.tw/dm/HR/)連出 [104 eRecruitor 公司職缺頁](https://ehrweb.104.com.tw/job.do?uno=23218183)，`uno=23218183` 與同日證交所 2855 官方統編一致，頁面公司全名亦相符。普通 GET HTTP200，但職缺明細由 JavaScript 載入；以免登入公開瀏覽器自然載入並點開「總公司稽核人員」，取得工作正文、全職、需求一人、公開 job id `1613781649555324659` 及 **異動日期 2026/10/05**。這個日期不是已證明的首次刊登日；頁面顯示 138 個職缺，本輪只核對一件，不將總數列為已取得 138 件。沒有登入、投遞、解驗證碼或讀私人履歷。它是不同於現有 104 搜尋／company jobs 的備援候選；自動明細取得與日期語意尚待整合驗證。
- [中再保官方徵才頁](https://www.centralre.com/content/hr/hr01.htm)也可普通 GET HTTP200，但更新日期仍是 **2026.08.14**，不當作近三十日新職缺。[信邦 2021 年英文合併財報](https://www.sinbon.com/files/2022_3023_20220530FE3_20220531_100147.pdf)原件 HTTP200、1,525,528 bytes、84 頁，PDF 第 26 頁仍只列 `Decrease in other intangible assets`，2021 年 22,673 仟元；不是取得無形資產現金流。新增英文原件仍未補出缺欄，不填零或解除完整年度財報門檻。
- 本輪只新增來源研究與憑據文件，沒有 provider 程式變更、模型工作或正式 SLA 寫入。普通 curl 使用 TLS 驗證、10–12 秒期限、回應大小上限、不自動重導；英文財報先遇非 www 的 302，只在核對同一發行人 www 目的網址後讀取。完整核對收據 `issuer-news-and-psc-ehr-free-entry-proof.json` 保存日期精度、原頁／正文 SHA、現行與有官方別名的診斷選擇差異及未整合邊界。正式原近 24 小時於 **16:34:31** 為 **16/20** 嚴格超過 80%，同業 **77/95（81.1%）**；這些變動發生於本輪新入口接入前，不能歸因於來源診斷。仍不足為職缺、財報、近期事件及社群，原二十類全部達標目標維持未完成。

### 續作：發行人完整原文正式接入

- 兩個公共介面行為測試先重現「未規劃新 provider」及「issuer_news bundle 未合併」**2 failed**。新 `issuer_news_provider.py` 在 registry 僅規劃 2206／3023 上市股；`workflow.py` 與 `enrichment_merge.py` 把原件送入既有公司／時間篩選，沒有增加市場搜尋名單或將未支援股票變成成功。`issuer_news.py` 要求當期證交所同代號、精確中文全名／簡稱、英文簡稱、官網 host 都相符；主檔重複、錯公司、錯網域、過期／未來日期先擋下，未再抓新聞。
- 三陽逐篇核對列表與明細標題／日期；信邦逐篇核對 id／slug／標題／日期／正文。只查三十日內最多五篇，不把月份補成日期，也不把整個列表視為窗口完整。保存原文與原始逐日日期，精度仍為 day；發行人自行陳述 `issuer_statement`、影響 `not_assessed`、`window_complete=False` 都保留。現有年月日時正規化只做日期內部排序，原字串在 `publication_date_original.issuer_article_date` 留存，不聲稱原網頁提供午夜發布時間。
- 英文簡稱只由固定發行人路徑的完整 identity／內容收據供 `issuer_match` 使用，不加入全域公司 aliases。第一版已找到的兩項真實缺陷均先用公共行為重現：日期正規化造成原件 hash 驗證失效（fetch→merge→repeat／async workflow **2 failed**），以及禁用別名大小寫／空白／HTML 不一致（**3 failed**）。現在 date-only 與現有 UTC 午夜正規化可核對同一內容 hash，其餘日期或明示時刻不同仍拒收；原日期 dict 不被覆寫，禁用別名沿既有 clean_text／strip／casefold，沒有取消內容驗證或放寬公司禁用。
- `issuer_news_transport.py` 固定普通 TLS curl，原二十秒全流程、單次最多五秒與大小上限（官方主檔2.5MB、JSON1MB、HTML150KB），無重導、重試、自訂身份或代理替換。403／429／5xx 優先保留實際 HTTP 與 Retry-After，沿 persistent cooldown；冷卻、錯網址及期限前阻擋零請求。原 bytes／SHA／網址快取三十分鐘，每次回讀重算 hash／重解析主檔與文章；未知、過大、未來或非法 epoch、修改 bytes/hash、有效目的網址與 redirect 不一致均拒收。真實無網路 slow-drip／overflow child 會停止並回收。此 provider 沿現有**來源批次觀測**，snapshot 的 `http_request_count`／component receipts 是底層診斷，沒有宣稱正式 API usage ledger 改為逐 HTTP 計數。
- 最終来源、傳输、快取、完整原件 fixture、registry／async merge、公司／時間篩選、新聞補搜策略、追蹤與 runtime／storage **199 passed**；獨立 scoped 覆核 **68 passed**，無未解 material finding。HTML fixture 僅保留真實文章／列表片段，主檔及新聞列表 fixture 是已觀測列的子集；不含網站表單、session／CSRF 或無關頁面 chrome，不冒稱完整 HTTP 原 bytes。活網新 provider 三陽 **3.206秒**、信邦 **1.143秒**各一篇 success／無公司拒收，兩個獨立 fetch IDs 正式 SLA 各 **0列**；三陽有3次底層請求，信邦共用主檔而有2次，並非各有3次 API usage。來源收據 `issuer-news-provider-live-proof.json`。
- 隨後最終快取直讀兩股各一篇 `skipped_fresh_cache`、零 HTTP，原取得 epoch 均為 **17:05:13**，不是此次回讀時間；七份最終 module SHA 保存於 `issuer-news-final-cache-live-proof.json`。正式服務先前已於15:57啟動，其後僅本輪七個 runtime 檔案有變動。第一次 idle 驗證因本機 RQ 方法參數不支援 cleanup=False 在任何停止前退出，舊 API／worker 未停止；改以現有 registry.key 的只讀 zcard 核對。六佇列 queued／started／deferred 均為零，保存兩個原 scheduled IDs／scores，停止空閒 owned worker、BGSAVE ok、再次確認原排程未變後才停止 owned launcher。正式 launcher **28406（17:12:42）**、worker **28434（17:12:43）**、API **28436（17:12:44）**，canonical cwd、七份 SHA／mtime、readyz 通過，兩筆排程ID／scores保留；未 commit／push。收據 `issuer-news-release-proof.json`。
- 新服務的三陽既有 `2206_TW_v4_report_job_ed8b69fc0449.html` 正式資料刷新 **HTTP200、28.504秒**，新原文一篇已保存於實際 snapshot，typed audit `skipped_fresh_cache`／HTTP False／零底層請求，保留原主檔、文章與内容 hash。初次沒有帶正常 mutation token 的請求被403拒絕、未執行刷新；隨後依現行本機 client-config 能力正常授權，未改安全設定或公開權杖。HTML／Markdown／analysis evidence／五項品質 gate 保留，四項 artifact／snapshot hash 與索引一致。原財報 critical failure 仍存在，data trust **partial 53→partial 53**；snapshot **needs_rerun**、index analysis_text_stale **1**，是資料更新而非新模型結論。收據 `issuer-news-2206-formal-refresh-proof.json`。
- 信邦既有 `3023_TW_v4_report_job_903e36396561.html` 也以正式同一資料刷新入口 **HTTP200、21.559秒**取得新原文一篇；保存後的 snapshot 再用完整收據驗證返回 `SINBON`，沒有被現行新聞篩選丟掉。typed audit 同樣新鮮 cache／HTTP False／零底層請求，原 epoch 未更新為回讀時間。HTML／Markdown／analysis evidence／五項 gate 保留，四項 hash 與索引一致；原財報 critical failure 維持 **partial 53→partial 53**、**needs_rerun／analysis_text_stale=1**。收據 `issuer-news-3023-formal-refresh-proof.json`。兩份資料刷新均抑制整批 provider SLA，不將快取或診斷寫成新 HTTP 成功；新自然模型報告的品質仍未由此驗證。
- **17:21:02** 正式原近24小時仍 **16/20** 類嚴格超過80%。尚不足為職缺 **51/75（68.0%）**、財報 **64/130（49.2%）**、近期事件 **261/382（68.3%）**、社群 **62/226（27.4%）**。同一 formal 觀測口徑、歷史事件及品質 gates 保持，沒有將新 provider 的受控樣本灌進成功率。readyz pass，七份 module SHA 與部署一致；兩筆原排程已按原到期自然接續，2606 被法人證據的主體／日期／期間紅線與修正上限擋下而未發布，2855 仍 `waiting_retry` 並自然重排。重載時原 ID／score 確實相同，後來的不同是實際工作執行及重試，不是排程遺失。沒有新增完整模型工作。收據 `issuer-news-completion-check.json`；原全部二十類驗收與全面報告品質仍未完成，下一步集中剩餘四類及自然品質阻斷。

### 續作：修復仍沿用舊財報的正式報告資料

- 原近24小時最新失敗只剩 2206／3023 官方完整年度欄位缺漏，其餘多數年度 fallback 失敗是舊事件。再核對 **153檔最新已存台股報告**，與近24小時 financial_statements 實際觀測的 **23檔**交集，發現 2855、2851、2023、2912、1605、2002 六份正式報告仍有舊四年／FCF缺值，儘管現有修正已能取得完整所需原件。這次先修實際報告缺口，沒有重標歷史錯誤或對所有153檔製造來源呼叫；來源盤點保存 `/tmp/stock-agent-financial-latest-report-inventory.json`。
- 2855 的同一既有 `49bf7ff921e45c43a6aaa2ae9a1c21ed` waiting-retry 工作已保存當日五年 `broker_consolidated.v1` 年報。以現有 `project_broker_histories` 重驗 ticker、scope、年度、原件 URL／hash、原始科目與現金流算式，與保存 input 的 revenue／net income／assets／equity／FCF各array完全一致；再用現有 trust evaluator重算分數，保留 source_freshness原時間。沿 `refresh_report_data_snapshot(..., refreshed_data=...)` 的既有公共 service修復旧報告，不重新取來源、不另排模型，不改 pending job／checkpoint。重用前後 SQL 保存 input SHA 相同；收據 `financial-broker-saved-source-preflight.json`。
- 其餘五份各沿正式 API `refresh/data`，HTTP200；中再保 **24.807秒**、燁輝 **20.249秒**、統一超 **19.181秒**、華新 **20.320秒**、中鋼 **20.857秒**。六份現在年度序列均為 **2021–2025**，FCF無缺值；這些來自明列原件及原算式，沒有填零或改期。金融業 scope 保留：2855合併證券商、2851明示無子公司的個別保險年報，不填一般業毛利／營業利益，也不因此啟用金融業一般企業DCF。六份 data trust 分數：2855 **52→91**、2851 **52→88**、2023 **50→88**、2912 **50→88**、1605 **50→88**、2002 **91→88**；均為 fresh。中鋼原score91不證明其舊四年已滿足五年要求，修復後亦不為維持高分更改計分。
- 六份 HTML／Markdown及原五項品質metadata保持，三個artifact hash與snapshot hash均和canonical reports index一致，snapshot **needs_rerun**、index **analysis_text_stale=1**。前五份既有 analysis evidence packet逐位保留。中鋼是9/10的legacy schema3，原本沒有 packet，故首次 raw-equality assertion失敗；依既有 `preserve_analysis_evidence(before)` 獨立核對後，實際新 packet完全符合原 preservation contract。其 `legacy_hash_verified`／`input_verification=hash_verified` 只捕捉經原始hash核對的舊 **2022–2025四年模型輸入**，與新data五年不同，沒有用更新資料冒稱原分析證據。首次assertion與後續判讀紀錄均保留；沒有為此改程式、回寫舊input或降低gate。
- 完整實際artifact、科目／scope、前後score、五gate／evidence／hash／needs_rerun查驗在 `financial-old-report-repair-proof.json`。本輪沒有runtime程式變動、重啟或新增模型工作；資料刷新未重新執行分析或重評原報告五項品質gate，不能當新完整報告成功或以fresh88取代結論驗證。`record_provider_sla=False` 抑制整批觀測，保存來源或快取不當作本輪新HTTP成功；實際下層HTTP觀測仍按原規則。獨立覆核及主代理以修復期間和各實際snapshot fetch ID交叉查canonical ledger：2855重用保存來源零列，其餘五次API刷新共57筆leaf事件（43筆http_attempt、14筆local_block），新增analysis_jobs為0；不是全程SLA零寫入。收據 `financial-report-repair-ledger-check.json`。
- **17:42:17** 正式原全部二十類仍 **16/20** 嚴格超過80%，未達標維持職缺 **51/75（68.0%）**、財報 **64/130（49.2%）**、近期事件 **261/382（68.3%）**、社群 **62/226（27.4%）**。原二十類驗收沒有改用「六份修復成功」作替代；readyz pass、2855原工作仍waiting_retry且原input SHA未改。收據 `financial-report-repair-completion-check.json`。2206／3023仍未取得缺失的年度現金流事實，六份新資料也仍需符合原模型與發布品質gate的分析重跑。


### 續查：eRecruitor 免登入清單與完整明細

- 沿已核對的[統一證券官方招募連結](https://eservices.pscnet.com.tw/dm/HR/)繼續追查[公司公開職缺頁](https://ehrweb.104.com.tw/job.do?uno=23218183)。頁面實際匿名搜尋／點開明細使用 `normalAjaxService.searchJobs` 和 `normalAjaxService.getJobDetailByCustId` 的公開 DWR read-only POST；不使用其他履歷、投遞或聯絡服務。普通 TLS curl 不帶 cookie、登入、瀏覽器權杖，`scriptSessionId` 留空仍 HTTP200。清單原回應 **79,581 bytes、138列，與回報total138一致**；這只證明當次清單完整，不表示138件明細均核對或全歷史窗口完整。
- 額外核對「資訊系統部網路管理工程師」、「資訊系統部LINUX 系統程式設計師」，以及先前的「總公司稽核人員」，共 **3筆完整明細**。list／detail 的職缺id與標題一致；root `custId=9900000736`、`custNo=23218183000`、`coName=統一綜合證券股份有限公司`、`enable=True`、未關閉／刪除，與已保存当期官方全名／統編23218183憑據相符。保存工作內容、需求人數、工作性質、原日期與每份原件SHA；不把138列或需求1–2人當作已驗證總職缺／雇員總數。
- 三件原 `formattedCreateDate` 分別是 **2023/03/10、2022/12/08、2024/04/10**，`formattedInputDate` 同日，最近 `formattedUpdateDate` 都是 **2026/10/05 18:21:54**。原件「異動日期」可核對，建立日也不自行升格為已證明首次發布日；這些可作目前開放職缺樣本，不能說是三十日內新增職缺、擴編或招募增長。近期新職缺數仍為未知。
- CLI只解析DWR固定wrapper中的資料literal，不eval／執行遠端JavaScript；超出20層／100,000節點或500KB拒收。saved-body的截斷、未知wrapper、可執行值、重複key與Infinity五種離線負例均拒收。初版research assertion錯把清單的 `cleanI18nName` 當成明細root欄位，已直接重讀保存原件，改核對實際root `job`；沒有擴大名稱別名或重抓既有回應。robots同日200只排除另一個key限定職缺頁，未列本次uno與兩個read路徑；原robots SHA保留，不將這點當作授權重發網站內容。
- 收據 [psc-ehr-anonymous-full-detail-proof.json](evidence/source-acquisition/20261009/psc-ehr-anonymous-full-detail-proof.json)。這是已實測可自動讀取的新候選入口，尚未接入正式provider。沒有runtime程式變更、重啟、新模型工作或用研究呼叫寫入正式SLA；自動整合仍須加入固定issuer映射、原件hash／日期／欄位重驗、全流程期限、大小上限、快取原時間及provider冷卻，不能只靠root聲稱或把異動日期改成發布日。
- **18:09:58** 正式原近24小時 **15/20** 類嚴格超過80%。未達標為職缺 **53/77（68.8%）**、同業指標 **73/92（79.3%）**、財報 **69/130（53.1%）**、近期事件 **270/385（70.1%）**、社群 **66/214（30.8%）**；與上一輪16/20相比，同業重新落到門檻下。原分母、歷史事件與品質gate未改，這些自然來源觀測不歸因於本輪候選研究。readyz storage／queue pass，當時started／deferred皆0、watchlist scheduled10、舊RQ failed10；不宣稱排程為零或所有重試已完成。二十類均超80%的原目標仍未完成。


### 續作：統一證券完整職缺備援接入與正式驗證

- 新 `psc_careers.py`／`psc_careers_literals.py`／`psc_careers_transport.py` 接入既有 `AlternativeJobOpeningsProvider` 與 `data_trust_audit.py`。只支援2855.TW／EQUITY、精確簡稱統一證、當期官方全名與統編23218183；主檔原取得時間須在24小時內、原觀測日距今最多14日。已有合格104／TaiwanJobs逐筆憑據就省略PSC；沒有才讀固定公司匿名清單與最多五個候選、最多保存三篇逐筆明細。PSC已合格時省略通用104／1111 keyword呼叫，有primary failure dict仍保留；單一未核對numeric總數不能抑制備援。
- 列表完整性、公司custId／雇主統編／全名、職缺id與標題、啟用／未關閉／未刪除、完整工作內容及原日期／hash逐筆核對。建立／輸入／異動日保留原字串，published_date維持null，不推近期新增、擴編或138筆已驗證明細。首次活網冷讀六次底層HTTP200、0.957秒，五候選僅一筆被接納；保存原件再查發現四件只是未揭露需求人數。公共parser先重現失敗，再把來源空字串保留為headcount_text=null；沒有填0或改公司／日期／全文門檻。最終回讀前三筆皆合格、0.012秒／零HTTP，仍保留原取得epoch1791542247.791919（18:37:27）。三筆為彰化分公司財富管理組長、台中與宜蘭分公司財富管理顧問；同公司分公司原件custNo／coName均相符，不混入子公司。
- 普通匿名TLS POST不帶cookie／登入／瀏覽器權杖，scriptSessionId空值，無UA／代理替換／重導／重試；總二十秒／單次五秒／500KB、硬停止並回收子程序，403／429／5xx及Retry-After優先保留且沿persistent cooldown。三十分鐘共享快取保留原bytes／URL／request identity／hash／epoch，每次重解析重驗；日期相對原取得epoch，而非回讀時間。只有固定DWR wrapper中的資料literal可解析，不執行遠端JavaScript；缺data、重複key、可執行值、非有限數、過深／過大資料安全拒收。
- 三個初始公共行為缺口先red再green：source counter漏接、provider未備援、原bytes進入提示詞。獨立覆核再重現三項P2：缺data KeyError、numeric誤抑制備援、None primary時誤做keyword且宣稱省略，均先用公共行為red修正。來源／傳輸／snapshot序列化／prompt／既有職缺與runtime-storage共 **291 passed**，獨立來源／既有CTBC **120 passed**，未解material finding0。`psc_ehr_jobs_20261009.json`只是實際公開欄位子集，明示不是原HTTPbytes。原件放既有source_record_archive，不更改全域prompt filter；PSC原件 **191,441 bytes**保存，提示詞部分 **5,653 bytes**保留工作正文、原日期與每篇hash，沒有把原件塞入模型或裁掉職缺內容。冷／暖活網收據分別為 `psc-careers-provider-live-proof.json`、`psc-careers-final-cache-live-proof.json`。
- 正式重載前確認六個RQ佇列queued／started／deferred皆0，六筆watchlist原scheduled ID／score保存，距最近到期逾兩分鐘。只停止owned worker、Redis BGSAVE ok、再確認原排程相同才關閉owned launcher；自上次17:12啟動後變動的runtime Python僅本輪五檔。新launcher **48561（18:52:13）**、worker **48596（18:52:14）**、API **48598（18:52:15）**，canonical cwd、五檔SHA與readyz通過；未commit／push。後續原排程到期自然接續，一筆finished／app品質error、四筆waiting_retry重排、一筆當時原score未變，六個原RQ job全仍存在，不能把到期後新score說成排程遺失，也不宣稱所有模型工作成功。收據 `psc-careers-release-proof.json`。
- 選取實際缺職缺憑據的既有 `2855_TW_v4_report_job_9d88127999a7.html`：來源記錄原 **0**，正式API全資料刷新 **HTTP200／36.617秒**後主104現已可用取得 **66**。因此本次API沒有自然觸發PSC，不虛構primary failure。再沿現有公共 `refresh_report_data_snapshot(..., refreshed_data=...)` service，在當前正式API資料中保留主來源、加入已核對保存的PSC三筆補充，實際snapshot總來源記錄 **69＝66＋3**；補充階段零新PSC HTTP，原epoch／原件hash可重新核對。這是具名可追溯的保存來源補充，不冒稱API的live failover已被觀察。
- 原HTML／Markdown、原分析封包、五個品質gate metadata均不變，四項artifact／snapshot hash與canonical reports index一致；獨立Locator讀回再次核對69與PSC3。data trust **91→91／fresh**，仍 **needs_rerun／analysis_text_stale=1**，未重新生成分析或重評品質gate，不能當新報告品質通過。正式資料刷新期間依actual snapshot fetch ID查ledger，共 **21筆leaf事件（14 http_attempt、7 local_block；12 success、9 unavailable）**，整批觀測抑制，並非全程SLA零寫入。期間新增analysis_jobs0；原保存模型工作／品質阻斷未修改。收據 `psc-careers-formal-gap-refresh-proof.json`。
- **19:03:26** 正式原二十類 **15/20** 嚴格超過80%。職缺 **53/70（75.7%）**、財報 **59/103（57.3%）**、近期事件 **228/304（75.0%）**、社群 **63/174（36.2%）**仍不足；年度人力在此滾動窗口 **0抓取／rate=null**，不能當0%失敗或宣稱超80%。同業指標已回門檻上，但這些窗口自然流動與來源觀測不可歸因於未寫SLA的PSC診斷／保存補充。原分母、歷史事件、所有原二十類與品質gate保持；原全部類別驗收仍未完成，下一步需處理四個低取得類與年度人力的實際有效觀測。收據 `psc-careers-completion-check.json`。

### 續查：四個官方免費財報入口與原件驗證

- 本輪針對新自然工作出現的6672／1325／7740／9103財報缺口，實測四個官方入口HTTP200，取得八份完整PDF原件；另保存6672、1325各一份官方iXBRL索引及五份年度原件。研究呼叫沒有計入正式SLA，沒有模型工作、報告改寫、runtime程式修改或重啟。每件原bytes／URL／取得時間／SHA封存至既有內容定址公開原件archive，全部重新解壓核對相同。詳細收據 [free-financial-portals-research-proof.json](evidence/source-acquisition/20261009/free-financial-portals-research-proof.json)。

| 股票 | 新查核的官方入口 | 實際原件與可補資料 | 完整資料限制 |
| --- | --- | --- | --- |
| 9103 美德醫療-DR | [美德財務資訊](https://www.medtecs.com/investor-relations/financials/) | 2021–2025五份年報全部匿名下載成功，各5.7–7.8MB；2025現金流PDF第42頁明列2025／2024設備支出4,523／1,683、無形資產支出3／30，均為US$仟元及現金流出。 | 原2021／2022現金流未明列無形資產支出，2022設備支出在2023比較欄又有差異，不能直接拼成五年FCF。正式舊snapshot已保留financial_currency=USD，不是要把它改為台幣；TDR／原股與幣別仍需保持。 |
| 6672 騰輝電子-KY | [騰輝歷年財務報表](https://www.ventec-group.com/zh/investors/financials/financial-reports/) | 入口列2021–2025年度合併原件；2025全文65頁／2,096,184bytes下載成功，PDF第11–12頁有營業現金流225,012及設備購置343,767，單位新台幣仟元。 | 2025PDF也未明列無形資產支出。2023PDF回HTTP200但超過本輪有界下載期限，未取得完整原件／hash，不能算成功。 |
| 1325 恒大 | [恒大財務資訊](https://www.uk.com.tw/zh-tw/download-c4793/%E8%B2%A1%E5%8B%99%E8%B3%87%E8%A8%8A.html)及其第二頁 | 2021合併財報59頁／2,162,569bytes，固定公開下載`download_file.asp?re_id=2174&fid=40303`取得成功；PDF第12–13頁營業現金流(4,927)、設備購置(92,659)，新台幣仟元。 | 原件同樣沒有無形資產購置列；五份年度iXBRL及次年比較欄都缺此項，不是換下載入口就能證明0。 |
| 7740 熙特爾-創 | [熙特爾每季財務報告](https://www.seetel-energy.com/download.php?cid=45&lang=tw&tb=1) | 官方公開列表固定`go_download`參數以匿名POST送`/include/download.php`，回200的iframe指向同官方host `/archive/doc/download/2023年度合併財務報告.pdf`；再GET取得62頁／1,409,776bytes。原件明示112及111年度，2023設備／無形資產支出(60,167)／(3,286)，新台幣仟元。 | 列表只有2023–2025合併年報，2023原件可補2022比較欄；2021完整合併資料尚未證明。2022無形資產是原表破折號，保留原符號，沒有升格為數字0。 |

- 官方原件揭露與機器下載成功要分開：美德頁面的「2026年度／全年度」標題實際指向2026上半年檔案，部分2025重複區塊指向2023。不能靠HTML年份或檔案名稱判定完整年度；必須核對檔內發行人、完整年度、合併／個體欄、幣別與每次修訂。其官方[股價資訊](https://www.medtecs.com/zh/investor-relations/stock-information/)明示546.SI原股與9103.TW台灣存託憑證，不能混同。
- 新自然財報失敗重現：6672的2022資產總額原件為5,007,482,000TWD，次年比較欄為5,023,032,000TWD；比較列缺必要無形資產支出，現有`reconcile_comparative_rows`安全拒收合理，不為提高成功率略過矛盾。1325五年同樣缺無形資產購置。以上PDF補上可查閱的完整原報告與已明列科目，但尚無足夠證據直接替代現有五年完整FCF契約，因此本輪沒有接入新的自動財務投影或降低gate。
- 初次文字工具對旋轉字及空白PDF頁有讀取限制，改用PDFium重讀保存原bytes並視覺核對美德2023／2025、恒大2021、騰輝2025、熙特爾2023五個相關現金流頁；未用排版錯置的文字結果填報。PDF頁數與資料期分開記錄，雙頁合版不把左右欄／兩個年度混在一起。
- **19:42:32** 正式原近24小時仍為 **15/20** 類嚴格超過80%；職缺53/68（77.9%）、財報58/98（59.2%）、近期事件222/290（76.6%）、社群63/165（38.2%），年度人力0抓取／rate=null。原二十類與分母不變，研究下載不灌入SLA；readyz200。原全部類別目標仍未達成。收據 [free-financial-portals-completion-check.json](evidence/source-acquisition/20261009/free-financial-portals-completion-check.json)。

### 續作：PTT正文保留、引用界線修正及正式驗證

- 前輪為已完成來源原件研究，本輪沿原二十類／每類嚴格高於80%繼續。先檢查社群失敗，假說為只查代號會漏掉公司名稱原文；以七檔現有報告的已知中文名稱有限實測，五檔只有歷史結果、6282／3023各找到一篇。再核對同篇代號查詢與今天正式ledger，兩檔本來都已取得，因此不增加名稱查詢、額外HTTP或寬鬆別名。2236在當時canonical reports表沒有既有報告，未杜撰snapshot或別名；本輪另由CMoney公開索引核對百達-KY名稱。研究原件／診斷保存在 `/tmp/stock-agent-ptt-company-recall-20261009/`；沒有寫入正式SLA。
- 發現可重現的程式缺口：原PTT已讀正文，`acquire_recent_posts`卻只回title摘要，Social provider又只留標題／日期／link。四個公共行為先red：正文及原回應hash遺失、正文公司名被剔除、長文未提供有界正文、真實台達電原件僅靠括號代碼的issuer evidence遺失。兩個作者帳號／推文不作公司證據的負例原先即green。新 `tests/fixtures/source_acquisition/ptt_2308_body_20261009.json`只是本日重新取得原件的已選欄位，明示不是完整HTTPbytes／歷史PIT；在舊觀測cutoff重播不是當時內容未變或目前活網成功的證明。今日台達電的PTT leaf1筆與Social0筆實際存在，但原job當時context未保存，不能把正文遺失說成該工作唯一原因。
- `ptt_stock_search.py`改為v4，Social provider保留正文、原HTML／正規化正文hash、字元數／截斷與parser版本。最多2,000字元，保留原發布時間，不新增查詢、不把原文數推為情緒結論。獨立覆核再重現兩項P2：引用者暱稱被當公司名、引用的發信站尾註截掉後續真正正文。均先公共provider red，再以原換行／br判結構修正；只去除完整 attribution行，包含巢狀`:／>`前綴，不全刪`.f2`；只有非引述行首官方發信站與六行內同篇原URL才裁真正尾註。普通`.f2`與引用正文仍保留。原公司selector、三十天、metadata／URL日期佐證、deadline與persistent cooldown不變。
- 最終相關九模組 **160 passed**；獨立四套 **52 passed**，兩項material及巢狀引用反例均已修、未解material0。重新解析保存的真實6282／3023 HTTP回應，實際公司identity下各仍1筆，正文由0增加至314／506字元，各有原件hash；不能把兩個原本成功樣本說成新取得。沒有公司名稱的測試context在這兩檔仍不合格，沒有放寬issuer規則。收據 [ptt-body-saved-live-response-replay.json](evidence/source-acquisition/20261009/ptt-body-saved-live-response-replay.json)。
- 重載前六個RQ佇列queued／started／deferred全0；自上次18:52啟動後runtime Python只有本輪兩檔變動。停止owned worker、核對原watchlist scheduled ID／score、Redis BGSAVE ok，再關閉owned launcher／API。原排程一筆完整保留，未取消、重排或清理歷史failed job。正式 `start_mac.command` 新launcher **64001（20:13:23）**、worker **64029（20:13:24）**、API **64031（20:13:25）**，父子／canonical backend cwd、兩檔SHA及readyz200核對。首次唯讀identity verifier錯要求`/bin/bash`前綴，實際是等效`bash ./start_mac.command`；讀回實際命令後修正核對，不再次重啟。收據 [ptt-body-release-proof.json](evidence/source-acquisition/20261009/ptt-body-release-proof.json)。
- 對實際既有信邦 `3023_TW_v4_report_job_903e36396561.html` 走正式資料刷新API，HTTP200／32.578秒。主CMoney當前3筆合格，所以依既有條件沒有觸發Yahoo／PTT，不能宣稱此API request觀察到PTT活網fallback。HTML／Markdown、原分析封包與五個品質gate metadata保持；四項hash與canonical reports index一致。仍 `needs_rerun／analysis_text_stale=1`，不是新模型分析或重新通過品質gate。期間對該ticker共17筆leaf觀測（11 http_attempt、6 local_block），整批觀測抑制不代表全程SLA零寫入；期間新增analysis_jobs0。收據 [ptt-body-formal-report-refresh-proof.json](evidence/source-acquisition/20261009/ptt-body-formal-report-refresh-proof.json)。
- 再以原生 `fetch_ptt_stock_sentiment('6282', limit=5)`單獨驗證活網，未替換HTTP結果、parser、時間或冷卻；只在獨立程序攔截診斷ledger寫入，避免把研究算入正式取得率。兩次HTTP200，**1.251秒／1篇合格／314字元／ptt-search-v4**，原responsebytes封存並解壓核對hash。這證明原生新parser與實際PTT相容，完整Social整合由隔離行為測試支持，不能推成上述正式API已走fallback。收據 [ptt-body-native-live-proof.json](evidence/source-acquisition/20261009/ptt-body-native-live-proof.json)。
- **20:30:18** 正式原近24小時為 **16/20** 類嚴格超過80%。職缺已跨門檻，未歸因於本輪PTT修正／未記SLA的研究。尚未達標：財報 **58/94（61.7%）**、近期事件 **218/280（77.9%）**、社群 **63/159（39.6%）**、年度人力 **0抓取／rate=null**。原二十類、歷史事件與分母均保持；null不是0%失敗或80%通過。readyz200、六佇列queued／started／deferred全0、一筆原watchlist job仍scheduled且原score1791549399不變。原全部類別目標仍未完成。收據 [ptt-body-completion-check.json](evidence/source-acquisition/20261009/ptt-body-completion-check.json)。


### 續作：CMoney -KY／-DR 免費原文漏收修正

- 原二十類、每類嚴格高於80%的口徑不變。本輪先讀正式SLA與今日社群缺口，再核對CMoney公開 `finance/{ticker}/f00025`／`forum-web.cmoney.tw/stocks/{ticker}` 索引和逐篇原件。不是增加供應商數量，而是修復現有免費入口對正常 `-KY`／`-DR` 名稱的漏收。
- 舊 `PAGE_TITLE`、finance標題與 `STOCK_TAG` 都只有中文／星號／hyphen，拒收百達-KY 2236、美德醫療-DR 9103、騰輝電子-KY 6672。三檔各保存兩個真索引及五篇真原文；正式9103既有報告 `9103_TW_v4_report_job_4c75689b2e28.html` 在改版前社群0筆／empty_unknown、data trust 56。2236在canonical reports沒有既有報告，名稱只由公開索引核對，不捏造報告或公司歷史快照。
- `cmoney_stock_posts.py` 共用精確中文核心加可選uppercase `-KY`／`-DR`，未知／串接／大小寫錯誤後綴仍拒收。原始bytes hash、大小、parser_version新增到每筆已通過樣本，沿既有SocialSentimentProvider及company-time selection保存；平台看多／看空不是驗證情緒，仍 `not_assessed`。
- 原十二秒整體、最多五候選／三筆、原有下載／恢復流程、TLS驗證、日期／原文／公司篩選及來源分母不變。新增後綴不自動授權target簡稱。review發現other-tagged issuer正文省略市場後綴會漏判混合內容，已以四個KY／DR×target負例重現4 fail/18 pass，再只補同行排除檢查；四個純target多tag正例仍有效。
- 第一版正式red為4 fail/9 pass（不含初期fixture缺檔與stub KeyError的setup失敗）；最終九個相關module **168 passed**。fixture是擷取公開title/tag/date/body欄位，不是完整原HTTP bytes；其原件hash與擷取測試輸入hash分開。真bytes另封存既有 `official-response-evidence` 並逐件讀回，`http_status=None`／`http_status_observed=False`，不將curl成功臆測為可觀測HTTP200。
- 完整原件before/after replay：三檔finance候選都由0→5；2236合格0→2，9103合格0→3，6672仍0（外部連結／多公司噪音不放行），company-time selection計數一致。`cmoney-qualified-names-replay-proof.json` 保存原件憑據與本輪前後程式hash，不拿離線replay當正式成功率。
- 百達-KY一次native來源實測 **5.233秒／六次真TLS傳輸／兩筆合格**，逐篇原hash核對；review補強後重播同批實測原件仍通過，未增加HTTP。證據 `cmoney-qualified-names-native-live-proof.json`，沒有把研究呼叫寫進正式SLA。
- 更新正式服務前確認自20:13:25起只有本次CMoney runtime檔變動（連JSON/YAML與.env檔mtime均查驗），六queue queued/started/deferred全0、scheduled為空；前輪a9ab watchlist job已依原排程自然跑完成error，不是本輪取消或遺失。本節下列收據已完成部署及9103資料刷新，未新增模型job。

- 獨立review最終無未解material finding，三套隔離 **49 passed**，另純重播三個finance索引與十五篇真gzip原件，hash／大小／current code hash一致；`cmoney-qualified-names-review-proof.json`。review不等於live或歷史PIT驗證。
- 已經 `./start_mac.command` 控制重載正式服務；新launcher **72439**、worker **72467**、API **72469** 同父程序／canonical backend cwd，`/healthz`、`/readyz` HTTP200。Redis BGSAVE ok、六queue與scheduled空集合重啟前後相同、code hash一致；`cmoney-qualified-names-release-proof.json`。驗證腳本最初誤讀 `/health` 得404，改查既有 `/healthz` 通過，沒有因此再次重啟服務。
- 正式9103既有報告只刷新一次資料，HTTP200／**25.642秒**，社群 **0→3筆**，新 `cmoney-stock-posts-v2` 及逐篇回應hash/bytes已保存，未走Yahoo或PTT。HTML、Markdown、原analysis_evidence及五份原品質gate metadata均保持原值，四個index hash讀回相符；`analysis_text_stale=1`、`decision_validity_status=needs_rerun`，實際operation前後 `analysis_jobs` 差集0。data trust仍 **56／partial**，不能將新社群樣本當完整報告品質通過。`cmoney-qualified-names-formal-report-refresh-proof.json`。
- **21:15:32台灣時間** 正式近24小時原二十類仍 **16／20嚴格高於80%**。財報 **58／94=61.702%**、近期催化劑 **218／280=77.857%**、社群 **63／159=39.623%**；年度人力資料沒有新增fetch attempt、rate=null，不是0%失敗也未算達標。保留來源快取／原分母，未刷研究流量灌成功率；`cmoney-qualified-names-before-sla.json`、`cmoney-qualified-names-after-sla.json`、`cmoney-qualified-names-completion-check.json`。goal繼續active；剩餘優先實證補財報缺列／期間一致性、年度人力缺欄、近期新聞原文與稀疏社群來源，不能靠零值或放寬gate達標。


### 續作：年度人力已揭露欄位保留與財報期間邊界

- 上輪為progress：CMoney修正已部署並由正式9103報告取得0→3筆。本輪保持原二十類逐類嚴格高於80%的驗收，先讀今日financial_statements ledger；目前官方一般業48/60、金融業9/9成功，最新實際未通過為2206/3023/1325缺科目、6672不完整比較年衝突、7740/9103不足五份年報。舊6282/6409等fallback失敗不代表目前已修好的官方入口仍失效；`financial-remaining-gaps-baseline.json`保存今日原事件分類，沒有重標歷史狀態。
- 新找到[永豐承銷熙特爾公開公告](https://www.sinotrade.com.tw/UploadFiles/2025/202505/29e24274-0d83-4ae1-8e76-326b03b5017d.pdf)，原PDF249,861bytes，TLS普通curl HTTP200、六頁、原件封存並讀回一致。第4/6頁註明2023首次編合併、附2022比較，第5頁個體IFRS自2022採用、附2021比較；因此現有入口不是單純漏了2021下載連結，不能將2021個體拼成五年合併。httpx原現代鏈驗證缺SKI錯誤，未繞過TLS；`seetel-early-scope-proof.json`只記真下載收據與範圍限制，未接成完整財報或灌SLA。
- 讀回正式TWSE全市場annual-workforce:v1:.TW shared cache，原668,442bytes／1,077列、出表1151009、報告114年度、原取得2026-10-09 19:00:50.824；二十四小時TTL當前有效。2236/6672薪資平均及中位明示N/A，但管理職女性主管22.70%／32.94%，舊parser因缺平均薪資整筆None。原byte/hash/epoch封存在`workforce-partial-before-proof.json`，fixture只挑三筆實際官方列，與完整原HTTPbytes區分。
- 修正只保留有至少一項有效明列metric的partial；N/A／空白／官方破折號仍None，不補0；錯平均薪資NaN／Infinity／負值／零仍拒收，沒有有效metric仍None。平均薪資缺失的female-only源記錄在原data trust salary gate仍0；只讓現有正薪資partial的狀態由錯誤stale改為partial，保留舊可用record count1。Meta.stale仍唯一過期來源；平均薪資未揭露的provider及aggregate維持unavailable/count0，payload仍coverage_status=partial，不升健康success；有原有效平均薪資的partial仍沿原degraded/count1契約。
- 新公共行為red **8 failed／6 passed**，最終來源、共用cache、完整來源gate、optional merge、prompt boundary、report data trust及runtime/storage隔離測試 **364 passed**。完整原件逐檔before/after重播1,077列，原985可用仍可用、另92家由丟棄變partial，均薪資仍None；`workforce-partial-replay-proof.json`。這不表示1,077份完整成功，也未將重播灌入SLA。
- 來源新module實際讀當前canonical cache驗證2236、6672partial，2330仍完整success；原取得epoch／hash／TTL相同、零HTTP，`workforce-partial-cache-provider-proof.json`。當前正式6672既有`6672_TW_v4_report_job_9548c590ccfd.html`的annual_workforce=null，data trust56，接續用這個真缺口驗證正式保存。獨立review、部署與正式API保存驗證均已完成，結果如下。

- 獨立review重現兩個material seam：female-only以degraded/count1會被既有legacy SLA健康計數升格；超大median從有限Decimal轉float可變inf。先用公共SLA／health及partial merge／數值負例重現 **7 failed／12 passed**（不含list API誤用的setup錯誤），再修provider完整availability／fact value分流及轉換後finite檢查。`enrichment_merge.py` 的受限annual partial收據分支保留matching issuer/hash、原epoch／stale/cache，aggregate unavailable/count0、無假的async_fetch_error；全域SLA公式沒有修改。
- 最終獨立 **29 passed**；cold/cache/真正stale三種公共provider→merge→隔離SLA均success_rate0、source_healthFalse，原日期／partial內容／旗標保留。`workforce-partial-review-proof.json`。最終整個1,077列重播：原985份metrics／報告年度／raw hash逐件與舊版一致、92新增partial，`workforce-partial-replay-proof.json`已更新final code hash。第一版native cache結果另保留作審查診斷，最終cache proof已重讀unavailable/count0；沒有把舊結果冒充final。
- 擴大provider workflow／acquisition／integration／source merge檢查 **48 passed、1 failed**。失敗為既有 `test_taiwan_yahoo_news_runs_only_when_other_verified_feeds_leave_a_gap` 仍期待Free waterfall與Alternative同批並行，而目前既有流程已序列化；測試本身把merge替換成stub，未走年度人力。用isolated runner插件只在測試process載入本輪三檔saved-before bytes後，同一assert仍fail；初次overlay import cycle是probe setup錯誤，修正後baseline重現有效。正式檔／既有news排程／測試未改，非本輪回歸，不阻塞本次三檔release。

- 已以正式 `./start_mac.command` 重載，只載入本輪三個runtime檔差異；新launcher **78766**、worker **78794**、API **78796** 同canonical backend cwd／父子關係，healthz／readyz HTTP200。原六queue全0、scheduled空集合保存，Redis BGSAVE ok，三份程式SHA核對；`workforce-partial-release-proof.json`。未commit／push，無關dirty修改不整理或覆寫。
- 真正缺年度欄位的6672既有report只刷新一次資料，**HTTP200／43.664秒**；原annual_workforce=null，現在保存2025年度女性主管 **32.94%**、平均／中位薪資null、payload partial。Provider與aggregate audit均 **unavailable／record_count0／staleFalse**，原byte hash4722f0…、原取得 **19:00:50.824**、出表1151009及24h快取日期保留；新freshness正確以原取得時間算age，不以刷新時間充當新HTTP。`workforce-partial-formal-report-refresh-proof.json`。
- Locator重新讀回HTML／Markdown／data/snapshot四個index hash一致；原正文、原analysis_evidence、五份品質gate metadata原值不變，data trust仍 **56／partial**，`needs_rerun`／analysis_text_stale1，實際operation前後analysis_jobs差集0。這是已保存的有效部分資料，不是完整報告、完整年度人力來源或品質gate通過。
- **21:53:53台灣時間** 正式近24h原二十類仍 **16／20嚴格高於80%**：財報58／94（61.702%）、近期事件218／280（77.857%）、社群63／159（39.623%）；年度人力0新fetch／rate=null，不能算0%故障或過門檻。保留源分母、TTL與歷史觀測，沒有把92份partial或研究probe計為成功；`workforce-partial-after-sla.json`、`workforce-partial-completion-check.json`。所有原類別的goal仍active；剩餘缺口繼續按完整科目／期間與原文證據處理。

### CMoney 同股票轉貼的原文入口（2026-10-09）

- 新入口來自真實 6672 公開轉貼 [185353826](https://www.cmoney.tw/forum/article/185353826)，指向 [185141811](https://www.cmoney.tw/forum/article/185141811)。後者獨立標示 `6672騰輝電子-KY`、2026-10-05 發布日期及無外連的原文。實際匿名 TLS curl 取得 669,918 bytes、SHA256 `2ca1dab4b48a5d5cf63bdfdd0b58b0ebc33b4465faf0e2c858d5e9df0bbdbfec`，原有逐篇 parser 即能接受；轉貼本身仍被拒收。curl helper 沒有回傳精確 HTTP status，因此證據使用 `transport_succeeded`／`http_status_observed=false`，不宣稱 HTTP200。
- `cmoney_stock_posts.py` 現在只在同一索引尚無合格記錄時，從精確單一股票 tag、有效日期、公司標題及至少五字作者文字的轉貼，追查最多一篇同站 HTTPS 公開 article。只容許已知 `forum_app`／`share` UTM，拒絕私有路徑、未知 query、裸 www、隱藏或不一致 anchor href、複數連結、自指與遞迴。子文章仍通過原公司／三十天／正文門檻，父文章只供發現；父日期與 raw hash 明示。共用原十二秒期限與三筆輸出上限，成功下載 bytes 在同次取得共用，仍按每個候選重驗身分及索引日期。
- 真實選取欄位 fixture 與公共行為先重現缺少追查的失敗；獨立審查再重現重複下載及隱藏外連兩個問題，已修正。最終相關 **208 passed**；獨立 **65 passed**、四個公共反例已覆核、沒有未解決 material finding。Fixture 是選取 HTML，不能把其 hash 當成原 HTTP hash；完整回應由 archive receipt 另行核對。`cmoney-reference-review-proof.json` 保存 final code hash。
- 同一批真實父／子原始回應的規則重播，確認父文章仍不合格、只發現精確原文 URL、子文章通過原 gate，兩份 raw hash 回讀一致；`cmoney-reference-real-response-rule-proof.json`。父子分別在不同時間取得，不代表歷史 point-in-time，也不是完整 native fallback 成功證據。
- **22:34** 的舊版 native baseline 已因新直接貼文 `185358901` 出現而取得一則，使用完整相同回應重播前／後都為 **1 則**，未走新增追查分支；`cmoney-reference-before-after-proof.json`。不得將較早空結果與較晚一則混合宣稱新程式的 native 0→1 效果。
- 最新 high-level `SocialSentimentProvider` 使用既有 6672 報告公司 context、原 TLS／期限／篩選的自然流程，**6.312秒／六次傳輸／一則／success**；沒有強制 failover、未寫正式 SLA，原文 SHA256 與封存回應一致。這次仍由直接索引取得，**完整 native reference branch 尚未觀察到**；`cmoney-reference-native-live-proof.json`。
- Mobile01／Dcard、HiStock／Wantgoo 的近期搜尋仍沒有增加可核對近三十天原文；搜尋引擎新爬取日、舊排行文章及靜態行情頁不當作新社群樣本。原本免費、真實原文與品質門檻保持不變。

- 正式服務只重載本輪 CMoney runtime 檔；launcher **89302**、worker **89330**、API **89332** 同 canonical backend cwd／父子關係，healthz／readyz HTTP200，六 queue 全0、scheduled 空集合保留、Redis BGSAVE ok，程式 hash 與 final review 相同；`cmoney-reference-release-proof.json`。首次 preflight 把生成報告 JSON 誤列為 runtime 檔而在停止任何 process 前拒絕；改以排除 output／cache／logs 的程式及設定範圍再確認，未放行未知 runtime 變更。無關 dirty 檔與 `.env` 保留，未 commit／push。
- 6672 既有報告只經正式 API 刷新資料一次，**HTTP200／34.526秒**。Locator 讀回確認原先 **Yahoo 2 則、CMoney 0 則、總計2**，刷新後是 **CMoney 1 則、Yahoo 0 則、總計1**；自然 waterfall 在 CMoney 合格時略過 Yahoo。不能把 CMoney 的0→1說成社群總數0→1，也不能據此宣稱取得率或品質提升。完整 native reference 分支未出現，這則是直接索引貼文；`cmoney-reference-formal-report-refresh-proof.json`。
- 原 HTML／Markdown、analysis_evidence 與五份品質 gate 完全相同，四份 index hash 一致；data trust **56→56／partial**，仍為 `needs_rerun`／analysis_text_stale1，實際 analysis_jobs 差集0。這次新增入口具備隔離回歸與真实回應規則證據，正式環境尚沒有自然走到它的證據；不以部署或單篇資料代替完整 report-quality 驗收。
- **22:43:28 台灣時間** 原近24h二十類仍 **16／20嚴格高於80%**：財報 **58／94（61.702%）**、近期事件 **218／280（77.857%）**、社群 **63／159（39.623%）**；年度人力0新fetch／rate=null，不能驗收通過。研究 probe、快取／aggregate與此次 data-only refresh 沒有變成額外 acquisition 成功；保留原分母／TTL／歷史。`cmoney-reference-after-sla.json`、`cmoney-reference-completion-check.json`。全部類別達標的 goal 仍未完成。

### SGX 原件與匿名機器查詢的差異（2026-10-09）

- 上輪為 progress：CMoney 同股票轉貼探索已上線，但正式自然流程未觀察到追查分支。本輪保持原二十類／近24h／逐類嚴格>80%的驗收，先重新核對 runtime doctor、正式 SLA、目前報告與本輪改動基準。未以新視窗、快取或研究流量替代正式取得率。
- 新查 [熙特爾官網](https://www.seetel-energy.com/?lang=tw)／[媒體列表](https://www.seetel-energy.com/article.php?lang=tw&tb=4)：現行證交所主檔確認7740、熙特爾新能源股份有限公司、SEETEL、官網與國別一致。Native TLS 已取得完整列表與兩份原文；2026參展頁的首頁日期2026-10-08與列表2025-10-13矛盾，原文沒有可核對發布日；近期3794是引用TechNews的文章，亦無原文獨立日期。7740目前報告已有8筆近期候選，不以矛盾日期或鏡像新聞新增獨立證據。沒有新增此站正式路由。首次頁面研究在診斷列印遭NavigableString誤用而停止；保留已下載首頁，只對尚未取得的三個具體原頁續查，不把研究程式錯誤當來源故障。
- [美德醫療官網公告導讀](https://www.medtecs.com/investor-relations/announcements/)明示由SGX以 `MEDTECS INTERNATIONAL CORP LTD` 搜尋。正常匿名官方瀏覽器頁已找到 [2026-10-09 處分完成原公告](https://links.sgx.com/1.0.0/corporate-announcements/NS5OFIA2R7WXB5B4/6e0783d954dc878882b51d5471c5cf3f8e86a0d2dda8a1dd5e1e3757230c4405)，含原股代碼546、ISIN BMG5958R1043、廣播時間17:31:58、reference SG261009OTHRW6Y4。這些不是9103 TDR價格／股數／幣別。Native公開標準公司query與原HTML分別HTTP200；原附件入口以302指向同站固定FileOpen，僅讀取並核對其明示URL，未開啟自動重導。
- 真正PDF原件 [Medtecs – Completion of the RMKH Disposal](https://links.sgx.com/FileOpen/Medtecs%20-%20Completion%20of%20the%20RMKH%20Disposal.ashx?App=Announcement&FileID=906536) HTTP200、163,077bytes／1頁，既有受限PDF worker完整提取2,049字元，原byte hash回讀一致。公司英文全名、Bermuda註冊、標題、2026-10-09簽署日可核對。它是公司自行陳述，SGX並未核准其內容；同一處分的中文／英文或不同發布場所不能當作獨立新事件。
- **關鍵反證：** 原網站標準20年索引URL曾匿名HTTP200，並不足以證明任意日期查詢是穩定免費API。新候選用三十天、同公司、二十筆的原生傳輸，實際在第二次HTTP取得 **authentication（401）／0筆**；正常官方網頁request header名稱含 `authorizationToken`，其值未查看、列印或重用。沒有用其他URL重試來規避拒絕，也未清除cooldown或複製網站session。`sgx-news-native-live-proof.json`保留失敗；不得稱為正式免費備援成功。
- 因此 `IssuerNewsProvider` 已精確恢復本輪saved-before bytes，**9103不在正式provider plan**。候選 `sgx_issuer_news.py` 保留單一TDR身分、API→原HTML→固定PDF mapping、簽署日／標題／完整PDF與四份hash驗證；source selector的SGX收據專用分支及transport callback只是尚未重載的研究修改，正式API／worker沒有因此新增抓取。不得將fixture正例或原件可達性冒稱自動介接已完成。
- 首次公共route測試先 **1 failed**；首輪94項、擴大249項隔離檢查通過。獨立review發現三項P2：禁止別名正規化不足、saved attachment未重綁同公告與canonical FileOpen、移除source_type後可能透過一般alias放行。四個公共反例先取得 **4 failed**，修正後最終相關 **253 passed**、獨立 **100 passed**；不存在未解material finding。停用route測試確認正式plan不含SGX，直接provider亦零SGX請求。這是研究／邊界驗證，不是活網成功。
- 同時追查Yahoo官方個股RSS：舊 `/rss/s/9103` 現回301，原body明示新的 `/rss?s=9103`；只向這個明示的同站URL讀一次，HTTP200、688bytes、有效RSS2.0 channel但 **0 item**。舊 `/rss-index` 說明頁現回404。沒有猜測多組query／代碼、繞過拒絕或把空XML當取得資料。`yahoo-9103-rss-gap-research-proof.json`、`yahoo-9103-rss-canonical-research-proof.json`。
- 詳細原件收據、停用狀態、review與限制見 `sgx-news-research-completion-proof.json`；每份成功研究原bytes重新解壓／hash核對。所有研究未寫正式SLA、未改保存報告、未啟模型工作，亦未重啟服務或commit／push。API仍89332，healthz／readyz HTTP200。
- **23:33:19 台灣時間** 近24h原二十類仍 **16／20嚴格>80%**；財報58／94（61.702%）、近期事件218／280（77.857%）、社群63／159（39.623%），年度人力0新fetch／rate=null，不能驗收通過。六queue與scheduled狀態保留在 `free-source-auth-completion-check.json`，完整SLA在 `free-source-auth-after-sla.json`。全部類別達標goal仍active；這輪證據已否定SGX匿名機器查詢與Yahoo空RSS能立即補足缺口的假設。

### 正式資料刷新補齊來源取得觀測（2026-10-10）

- 找到可重現的觀測缺口：`report_refresh_service.py` 在既有報告的真實資料刷新傳入 `record_provider_sla=False`，整批來源觀測因此未記錄；底層原HTTP事件仍可能存在，不能說過往刷新完全沒有記錄。改由現有 `StockDataService` 在取得邊界記一次，成功、失敗、快取與彙總全部保存；多報告共用的 `refreshed_data` 分支不重抓、不重記。沒有補登歷史、篩掉失敗、改分母或修改品質 gate。
- 新公共流程測試先 **2 failed**，修正後來源／追蹤／storage／snapshot／新聞邊界 **310 passed**；獨立審查 **32 passed**，另核對多報告共用、刷新502及保存失敗三種情境。真正發生的來源工作即使未成功保存報告，取得紀錄仍保留；快取沒有變成新fetch。review收據在 [refresh-sla-review-proof.json](evidence/source-acquisition/20261010/refresh-sla-review-proof.json)。測試建置的import錯誤及不存在測試檔的初次指令不是行為red。
- 正式重載前，精確核對上次啟動後五個owned runtime檔（取得紀錄修正、SGX候選／selector／transport guard及恢復原bytes的provider）；全部通過相關隔離驗證，SGX獨立邊界review另100項。SGX仍不在正式plan，不因重載啟用匿名401路由。只停止owned worker／launcher，Redis BGSAVE成功，六queue的queued／started／deferred均0、scheduled空集合保留。新launcher **8007**、worker **8035**、API **8037**同canonical backend cwd與父子關係，五份SHA、healthz／readyz HTTP200；[refresh-sla-release-proof.json](evidence/source-acquisition/20261010/refresh-sla-release-proof.json)。保留無關dirty修改與`.env`，未commit／push。
- 5314既有 `5314_TWO_v3_report_job_6d4d98252427.html` 的TPEx全市場年度raw cache已於10/09 **16:02:11.575**自然過期。未清cache、改TTL或先以研究程式刷新，只經正式API刷新一次，**HTTP200／38.134秒**。保存2025年度人力原件的出表日由10/08變10/09，平均薪資758、中位372仟元與女性主管53.57%保持；新raw hash **9a6b99a6…**與快取及保存snapshot一致，原取得epoch在本次實際操作內。data trust **fresh88→fresh91**。
- 同一保存snapshot fetch ID **b26b161fd3884fb4b3d8b8498488da67**對回canonical ledger：年度provider只有 **1筆 fetched_count**，optional合併的另一筆是原projection排除的aggregate，年度fetch_attempts仍1。全部matching事件另保留31筆fetched、3筆degraded、10筆local block、20筆aggregate及1筆fresh cache，沒有只挑成功。初次驗證程式把provider與aggregate兩列都當取得而assert失敗；直接唯讀重查既有artifact／ledger完成更正，沒有重送正式刷新。收據 [refresh-sla-formal-report-refresh-proof.json](evidence/source-acquisition/20261010/refresh-sla-formal-report-refresh-proof.json)及linked-events。
- Locator讀回原HTML／Markdown、analysis_evidence及五份品質metadata相同，四份index hash全部一致，新增analysis_jobs差集0；原 `needs_rerun`／analysis_text_stale1保持。這是新資料取得及觀測保存的驗證，不是重新生成報告或品質gate通過。正式原近24h目前 **17／20嚴格>80%**；年度人力由不可評比變真實1／1，其他比率也受舊事件自然離窗影響，不能將所有變化歸功於修改。完整即時值在 [refresh-sla-completion-check.json](evidence/source-acquisition/20261010/refresh-sla-completion-check.json)，全部二十類達標goal仍active。

### 新候選：台泥原文新聞與統一超IR營運公告（2026-10-10）

- 沿新查到的 [台泥官方新聞](https://www.tccgroupholdings.com/news)，native普通TLS匿名取得完整索引 **HTTP200／415,668bytes**。另逐篇核對 [10/01原文](https://www.tccgroupholdings.com/news/6abf40a1b0a2d)及 [9/23原文](https://www.tccgroupholdings.com/news/6ab3447d7b066)，均HTTP200，原回應406,762／407,990bytes，正文723／1,171字元。只讀各自文章標題旁的原日期及唯一`editorPanel`，排除側欄相關文章日期；不以頁面爬取時間判发布日。
- 當期TWSE原始主檔 **1,327,573bytes／HTTP200**，原觀測日10/08，確認1101臺灣水泥股份有限公司／台泥／TCC，官方網址`https://www.tccgroupholdings.com/tw/`，與文章同網域。兩篇同屬公司對同一烏克蘭收購案的自行陳述，影響尚未評估，不能算兩個獨立來源或已完成兩筆不同事件。沒有將子公司名稱／信評轉述升格為獨立查證。
- [統一超IR新聞](https://ir.7-11.com.tw/tw/news.php)及 [最新營運原文](https://ir.7-11.com.tw/tw/news-inner.php?id=205)也匿名HTTP200，索引38,293／原文47,353bytes；原日期 **2026-09-10**，最新仍是8月營收，不能改標為10月新聞。它目前位於30天的日精度邊界，並非剛發布的消息；原HTML摘要與正文有重複段落，字元數也不當作獨立事實數。2912統一超商股份有限公司／PCSC與當期主檔一致；正式自動路由仍須核對IR子網域的官方連結收據與日期範圍。
- 全部完整raw bytes封存／解壓hash讀回一致，收據 [issuer-news-entrances-research-proof.json](evidence/source-acquisition/20261010/issuer-news-entrances-research-proof.json)。這兩個新候選尚未接入provider：台泥需為官方`/tw/`網址與約408KB文章建立專用有限路由，不能放寬其他公司的host/path或原150KB上限；仍需公共流程／cache／cooldown／snapshot及正式自然fallback驗證。研究不寫正式SLA、不啟模型、不改現有報告。
- 本輪重新下載恒大1325的2021合併PDF，實際59頁／2,162,569bytes，與先前相同原件hash；第12–13頁視覺核對仍只有營業現金流(4,927)及設備購置(92,659)仟元，沒有無形資產購置列。這是**舊入口重查**，不是新增來源或五年FCF修復；[universal-financial-research-proof.json](evidence/source-acquisition/20261010/universal-financial-research-proof.json)保留重查身分。web工具PDF截圖逾時不代表native原件下載失敗，已直接渲染保存bytes核對。

### 台泥官方原文接入與正式保存驗證（2026-10-10）

- 上輪為progress：正式資料刷新來源觀測已補齊，5314年度來源有真實取得；二十類仍17／20。本輪沿原驗收與免費限制接入台泥，不改歷史事件、分母、來源完整性或品質gate。精確owned scope為`issuer_news.py`／`issuer_news_transport.py`／`issuer_news_provider.py`／`source_content_selection.py`及新`tcc_issuer_news.py`，基準在`/tmp/stock-agent-tcc-news-before-20261010`，無關dirty成果保留。
- 只支援1101.TW：當期TWSE主檔同代號、臺灣水泥股份有限公司、台泥、TCC及原官網`https://www.tccgroupholdings.com/tw/`相符才读索引。原profile其他兩家仍只接受原root網址；台泥固定`/news`及同host單層公開文章路徑有專用600KB上限，其他路由不擴大。三十分鐘raw快取、原取得epoch、二十秒整體／單次五秒／連線兩秒、無重導／重試／代理及persistent cooldown保持。
- `tcc_issuer_news.py`只讀原觀測的直接標題／日期欄位與唯一`editorPanel`正文，列表／原文一致才建收據，保存主檔、索引、文章及parsed-content hash。正文超出上限、缺日、未知／未來／歷史日期、重複矛盾、錯誤route或公司身分均拒收。公司自行陳述、日精度與事件影響未評估維持；不是獨立新聞或不同事件數的證明。新三篇依原五候選上限取得，不查額外頁面，也不宣稱完整三十天窗口。
- 公共provider plan、目前原文、既有selector與收據類型邊界先取得 **17 failed**。其中也重現既有first-party收據移除`source_type`後可能一般alias放行，現凡有`issuer_news_receipt`就重驗原身分、日期、內容hash及路由。初版fixture選取漏掉一般card，改從已保存完整原件補正選取HTML；fixture明示不是raw HTTPbytes或歷史PIT。首次implementation分支位置錯誤導致八項失敗，已在隔離驗證中修復，未載入正式服務。
- 獨立review重現P2：標頭容器缺原日期時，巢狀related-news日期會被接受。文章／featured index／card index三種公開流程均先 **3 failed**，改為只讀已觀測的直接段落／同層标题後拒收。最終相關來源、cache／transport／merge／snapshot／prompt／runtime-storage **274 passed**，獨立 **128 passed**、未解material finding0；SGX9103仍停用。[tcc-news-review-proof.json](evidence/source-acquisition/20261010/tcc-news-review-proof.json)。
- 原生第一次試跑只在TWSE主檔連線逾時，台泥HTTP尚未發生；原失敗／shared retry_after保留，沒有清cooldown、換URL、UA、TLS或增重試。原兩分鐘shared冷卻自然到期後才做第二次，**4.902秒／五次HTTP／三篇／success**。這是日期guard修正前的版本，不能當final冷抓證明；[first-attempt-proof](evidence/source-acquisition/20261010/tcc-news-native-first-attempt-proof.json)及 [native-live-proof](evidence/source-acquisition/20261010/tcc-news-native-live-proof.json)均保留。
- 最終版本原生沿同一raw cache重新解析／重驗 **0.131秒／零HTTP／三篇／skipped_fresh_cache**，與前一版有效records、原取得epoch逐項相同。完整三篇原件与主檔／索引raw hash已回讀核對；selected fixture與完整raw重播都不當活網冷抓或正式取得率。[tcc-news-native-final-cache-proof.json](evidence/source-acquisition/20261010/tcc-news-native-final-cache-proof.json)、final-readback-proof及complete-response-replay-proof。三次診斷的formal SLA新增均0。
- 已在六queue空閒、scheduled空集合核對後保存Redis BGSAVE，僅停止owned worker／launcher並經`start_mac.command`重載。本輪五份runtime檔與final review／cache probe SHA相同；新launcher **14758**、worker **14786**、API **14788**同canonical backend cwd與父子關係，healthz／readyz HTTP200，原排程、`.env`、無關dirty成果保留。未commit／push；[tcc-news-release-proof.json](evidence/source-acquisition/20261010/tcc-news-release-proof.json)。
- 真正過期的1101既有`1101_TW_v4_report_job_5195a0c65e76.html`只經正式API刷新一次，**HTTP200／43.222秒**。先前沒有台泥原件，現在保存三篇：一篇在原八筆`recent_catalysts`，兩篇在`additional_recent_catalysts`；近期摘要仍 **8→8**，不能宣稱變11或增加三筆獨立事件。每篇原日期、全文、link與收據hash均可對回原native；UTC午夜日期正規化仍由公開validator通過。
- 新snapshot fetch ID **94aa48a1c98f449faf91a42968a5f810**對回`Verified issuer news`一筆fresh-cache觀測／record_count3／HTTP False，原epoch **1791563750.578281**保持，不算新fetch。最初verifier誤要求三篇都在八筆摘要且日期格式字串完全相等而assert失敗，直接唯讀全news buckets及公開validator更正，没有重送API。原HTML／Markdown／analysis_evidence／五份品質metadata相同，四份index hash一致、新analysis_jobs0；data trust **stale52→fresh91**，原正文仍需重跑，`needs_rerun`／analysis_text_stale1。這不是新模型報告或品質gate通過；[tcc-news-formal-report-refresh-proof.json](evidence/source-acquisition/20261010/tcc-news-formal-report-refresh-proof.json)及linked-events。
- **00:43:43台灣時間**正式原近24h二十類仍 **17／20嚴格>80%**。未達標：財報 **47／76（61.842%）**、近期事件 **170／224（75.893%）**、社群 **49／113（43.363%）**。原二十類、分母與歷史不改，資料刷新其他真實源成功／失敗照記，台泥這次是cache不貢獻新取得率；原目標仍active。[tcc-news-after-sla.json](evidence/source-acquisition/20261010/tcc-news-after-sla.json)、[tcc-news-completion-check.json](evidence/source-acquisition/20261010/tcc-news-completion-check.json)。

### CMoney 原始股票 tag 在報告選取流程的保留（2026-10-10）

- 繼續沿正式近24h原二十類逐類嚴格>80%驗收。唯讀來源ledger核對新缺口：5314上次正式資料刷新原文raw3、usable2、issuer_unverified1，並非供應商無資料。新查到的[原文185359540](https://www.cmoney.tw/forum/article/185359540)明示單一`5314世紀*`、原日期2026-10-09 14:53:35 UTC及作者正文，但標題沒有代號；原一般「世紀」歧義保護因此誤排除已核對的股票tag。原665,270bytes完整回應封存／解壓hash一致，curl helper未回傳HTTP status，仍記transport_succeeded及http_status_observed=false。財報主路徑成功後本來就不抓Yahoo／FinMind年度備援，沒有為否定的重複抓取假設改排程。[remaining-gap-ledger-audit-proof.json](evidence/source-acquisition/20261010/remaining-gap-ledger-audit-proof.json)、[original-research-proof](evidence/source-acquisition/20261010/cmoney-5314-original-research-proof.json)。
- 精確owned runtime scope只有新`cmoney_stock_context.py`、原`cmoney_stock_posts.py`及`source_content_selection.py`；既有dirty基準另存`/tmp/stock-agent-cmoney-context-before-20261010`。原parser核對股票／單tag／日期／作者文字後才建5314.TWO／世紀*收據，綁原HTTP hash／大小與解析內容hash；selector及snapshot重選重驗原公司、市場、禁止別名、原來源／索引／日期／正文／parser。保留作者title/text，不前置代號、不擴一般「世紀」aliases；十二秒、五候選、三筆及not_assessed口徑不變。
- 公開行為red為 **16 failed／8 passed**。移除收據及明示malformed identity另 **3 failed**，再加basis guard與缺值／錯型分流；獨立review指出official_name／stock_id的False／0會被`or`遮蔽，先 **4 failed**再只允許None／空字串的既有fallback。最終來源／社群／snapshot／prompt／新聞／runtime-storage相關 **355 passed**，獨立 **109 passed**、未解material finding0，八個異常身分與移除收據反例拒收。[cmoney-context-review-proof.json](evidence/source-acquisition/20261010/cmoney-context-review-proof.json)。selected fixture不是完整HTTP bytes，不能用其hash當原件hash。
- 第一版native SocialSentimentProvider沿既有5314報告公司context自然取得 **3.569秒／四次匿名TLS傳輸／三筆／success**；保存所有完整索引／文章回應，以完全同一批bytes重播saved-before parser及原selector只有 **兩筆**。這是basis及異常身分修正前版本，不冒稱final live SHA；[native-live-proof](evidence/source-acquisition/20261010/cmoney-5314-context-native-live-proof.json)。final程式另用同批四份完整原件重播公開Social provider、JSON snapshot及重選，仍舊2→新3、原title/text/date/source逐筆相同、零HTTP與零正式SLA；[final-complete-response-replay-proof](evidence/source-acquisition/20261010/cmoney-5314-context-final-complete-response-replay-proof.json)。不以較晚新貼文或離線replay灌正式成功率。
- 重載前核對自00:40:23上次API啟動後僅上述三個runtime檔變動，final review／完整原件replay SHA一致、`.env`及無關修改保留。六queue queued/started/deferred均0、scheduled空集合，Redis BGSAVE成功，僅停owned worker／launcher，再經`start_mac.command`啟動。新launcher **20294**、worker **20322**、API **20326**同canonical backend cwd／父子關係，healthz／readyz HTTP200，原排程保留；未commit／push。[cmoney-context-release-proof.json](evidence/source-acquisition/20261010/cmoney-context-release-proof.json)。
- 正式既有`5314_TWO_v3_report_job_6d4d98252427.html`只刷新一次資料，**HTTP200／21.327秒**；社群 **2→3筆、partial→success**，上述被誤排除的185359540已保存，raw3／usable3／rejected0。每筆final收據重驗通過，原作者標題／正文／發布時間與同URL研究相同；动态HTML在不同取得時間的raw hash不宣稱相同。四個index hash讀回一致，原HTML／Markdown／analysis_evidence／五份品質metadata保持，data trust **fresh91→fresh91**、analysis_text_stale1／needs_rerun、新analysis_jobs差集0。這是資料補齊，不是生成報告或通過品質gate。[cmoney-context-formal-report-refresh-proof.json](evidence/source-acquisition/20261010/cmoney-context-formal-report-refresh-proof.json)。
- Canonical fetch ID **aace349e8ae949879ee89b7602688ab6**的social ledger有同provider label兩列：原來源 **1 fetched_count**，optional合併 **1 aggregate_count**被原projection排除，並非兩次取得。初始verifier誤要求provider label只有一列，唯讀重新查artifact／DB後已更正，沒有重送API。全部同fetch觀測仍保留29 fetched、10 local block、20 aggregate、3 fresh cache、1 degraded；[linked-events](evidence/source-acquisition/20261010/cmoney-context-formal-report-linked-events.json)。
- **01:13:28台灣時間**正式原近24h二十類仍 **17／20嚴格>80%**：財報 **48／77（62.338%）**、近期事件 **173／228（75.877%）**、社群 **50／114（43.860%）**。社群本次只增加一個真實取得觀測；其他來源變化亦包含同一真實刷新與歷史自然離窗，不能全歸功於收據。沒有重寫分母／历史／空結果或品質gate；[cmoney-context-post-refresh-sla.json](evidence/source-acquisition/20261010/cmoney-context-post-refresh-sla.json)、[completion-check](evidence/source-acquisition/20261010/cmoney-context-post-refresh-completion-check.json)。全部原二十類達標goal仍active；接續找有原始日期／完整財務口徑的免費入口。

### 新免費候選：世紀民生五年合併財報原件與美德公司新聞（2026-10-10）

- 新找到[世紀民生5314官網財務頁](https://www.myson.com.tw/financial)，匿名普通TLS GET **HTTP200／97,606bytes**；頁面直接連31份合併／個體／英文PDF。僅依明示`110–114年第四季(合併)`選五份，不把個體、英文同年度副本或季度資料混成不同年度。五份固定公開URL均HTTP200、完整PDF下載／解壓hash讀回相同；封面逐份渲染目視核對股票5314、世紀民生科技股份有限公司及子公司、合併年度及會計師查核範圍。完整入口原件已取得，但還沒有驗證全部財務科目投影、比較年修訂或當期exchange master的官網綁定，因此尚未啟用自動provider，也不算正式取得率。[myson-five-year-financial-new-entrance-research-proof.json](evidence/source-acquisition/20261010/myson-five-year-financial-new-entrance-research-proof.json)。

| 年度 | 完整原PDF | 頁數 | 原件大小 |
|---|---|---:|---:|
| 2025 | [合併財報](evidence/source-acquisition/20261010/myson-2025-consolidated-original.pdf) | 79 | 1,527,242 bytes |
| 2024 | [合併財報](evidence/source-acquisition/20261010/myson-2024-consolidated-original.pdf) | 58 | 1,408,807 bytes |
| 2023 | [合併財報](evidence/source-acquisition/20261010/myson-2023-consolidated-original.pdf) | 50 | 1,634,687 bytes |
| 2022 | [合併財報](evidence/source-acquisition/20261010/myson-2022-consolidated-original.pdf) | 54 | 828,240 bytes |
| 2021 | [合併財報](evidence/source-acquisition/20261010/myson-2021-consolidated-original.pdf) | 52 | 2,063,028 bytes |

- 公開檔名的2025／2026上傳時間不代表財報年度、首次發布日或歷史PIT。這些原件可作5314免費備援候選，不能拿另一家公司原件補2206／3023／1325未明示無形資產支出，也不能自動解除6672比較年度衝突或7740／9103五年口徑不足。
- 另由[美德官網](https://www.medtecs.com/)明示連到business子站，發現[RFID制服管理中心公司原文](https://business.medtecs.com/zh-hant/medtecs-tri-service-general-hospital-rfid-collaboration/)，普通TLS GET **HTTP200／198,396bytes**；HTML原發布時間2025-12-04 14:13:29+08:00與可見日期一致，已超出本輪三十天窗口，不能升格近期事件。首頁2026法務獎項banner未找到可核對原發布時間／完整文章；[Announcements頁](https://www.medtecs.com/investor-relations/announcements/)仍指向原SGX入口，沒有以此繞过401。這是本輪有限原件查驗結果，不宣稱該公司完全沒有近期事件。
- [美德news索引](https://www.medtecs.com/news/)亦匿名HTTP200／372,396bytes；索引頁自身article:published_time是2021年，不能當所有子文章的發布日。[研究收據](evidence/source-acquisition/20261010/medtecs-myson-new-public-entrances-research-proof.json)保存每份完整raw及URL／狀態／hash。新研究沒有正式SLA事件、cache清除、報告重寫或模型工作。5314原報告已在前節正式刷新，這輪新財報候選沒有再次刷新報告。

### 自由財經公開原文備援接入與正式保存（2026-10-10）

- 上輪為實際progress：CMoney原tag修正正式保存5314社群2→3；本輪仍按原近24h二十類逐類嚴格>80%驗收，不改歷史事件、分母、來源完整性或品質gate。重新唯讀ledger確認現行CMoney/Yahoo/PTT版已有25 fetched／2 empty／1 degraded，社群低率包含大量舊PTT empty；兩筆18:03／18:07舊空結果已有後續正式CMoney資料保存，不能假設新路由仍完全無原文。最新近期資料不足是5314 Alternative Search raw24／usable7／rejected17；8個unknown_date主要是靜態行情與舊文章，不將爬取或修改日補成發布日。[remaining-gap-ledger-followup-proof.json](evidence/source-acquisition/20261010/remaining-gap-ledger-followup-proof.json)。
- 新入口為自由時報[公開財經搜尋](https://search.ltn.com.tw/list?keyword=5314&type=business&sort=date&start_time=20260910&end_time=20261010)及[逐篇原文](https://ec.ltn.com.tw/article/breakingnews/5574307)。本機普通匿名TLS兩頁均HTTP200，索引有明示title／日期／原文URL，原文直接h1／發布meta／可見時鐘／作者正文能核對5314。Web工具未能讀搜尋頁不代表native失敗；沒有更換UA、登入cookie、重導或停用TLS。完整原件封存並逐份讀回hash。[ltn-news-original-research-proof.json](evidence/source-acquisition/20261010/ltn-news-original-research-proof.json)。
- 精確owned scope為新`ltn_stock_news.py`及原`external_search_providers.py`／`external_search_quality.py`／`source_content_selection.py`，原後三份dirty bytes另存`/tmp/stock-agent-ltn-before-20261010`。只接受完整可核對的台股EQUITY公司context、四位股票代號及固定publisher host/path/query；原搜尋不足八筆／多publisher才在父期限剩餘時間讀新入口。只補缺額，最多三筆、五候選、十秒且不得延長原搜尋期限；單次HTTP最多三秒，原三十分鐘raw cache／單工／persistent cooldown保存。
- Parser只讀非template原文容器的直接h1／可見日期與head發布meta；原站兩份完全相同meta可用，矛盾、缺失、naive或側欄時間拒收。原文與索引title／台灣日相符，正文需明示目標代號；圖片說明、模板、側欄與推廣文字不能補公司身分。保存完整作者正文及原發布字典／回應hash／解析收據，影響not_assessed；原文提及多檔股票時不宣稱是5314獨立事件。刪除或修改收據不能走一般alias，實際news projection／JSON snapshot重選仍核對同一內容hash。
- 公共不足行為先 **1 failed／1 passed**；同篇wrapper／原文被算不同publisher與以尾碼差異補滿門檻另先 **2 failed／2 passed**。現在LTN子站及其RSS歸同publisher，同publisher／同標題／同台灣日的wrapper由原文取代，但舊記錄保留archive與raw／rejected計數。沒有降低八筆或來源多樣性門檻。selected fixture只擷取實際HTML，不能用其hash冒稱完整HTTP原件。
- 獨立review四個P2及真實publication projection先在公共介面重現 **10 failed**：解析後期限／lease失效仍發布、NaN／bool／零／未來／過期cache epoch被當fresh、未啟動被算HTTP、429的Retry-After丟失、原發布string被既有projection改寫而失去收據。逐項修正後又以公共Alternative流程重現巨整數epoch **1 failed**，再安全拒收數值轉換溢位並保留原七筆進度。最終相關搜尋／正文／cache／receipt／prompt／snapshot／runtime-storage **282 passed**；獨立 **78 passed**、未解material finding0。[ltn-news-review-proof.json](evidence/source-acquisition/20261010/ltn-news-review-proof.json)。初版template／重複meta及basis驗證回呼問題也已在隔離中修正，未載入正式。
- 第一次native完整搜尋 **4.945秒**，既有providers共12次callback（含local block，不能當12次HTTP），LTN有五次真匿名HTTP、三篇合格原文、一篇不合格、完整索引／原文共五份封存回讀。用同一批已解析的既有搜尋結果重播saved-before為 **七筆**，加原件為 **八筆／sufficient_candidates**，未把較晚新搜尋結果混入比較，也未把回傳SearchResult當原API完整bytes。這是期限／cache等最後guard修正前版本；[ltn-news-native-search-proof.json](evidence/source-acquisition/20261010/ltn-news-native-search-proof.json)不冒稱final冷抓。
- Final版本重用同一批captured SearchResult，沿真raw cache重解析／重驗目前只缺一筆的索引與原文，**零HTTP／原epochs及raw hash不變／七→八**；原title／text／date／URL一致，實際news normalization與JSON snapshot保留一篇LTN原文。沒有清cache或灌正式SLA；[ltn-news-final-cache-replay-proof.json](evidence/source-acquisition/20261010/ltn-news-final-cache-replay-proof.json)。最後guard版本的獨立冷抓仍未觀察，正式cache保存驗證如下。
- 自前次API **01:10:51**啟動後僅上述四個runtime檔改動；final review／cache重驗SHA一致，`.env`及無關dirty成果保留。六queue全0、scheduled空集合，Redis BGSAVE成功；經原`start_mac.command`重載，新launcher **30479**、worker **30507**、API **30517**同canonical backend cwd與父子關係，healthz／readyz HTTP200。初次health讀取在啟動尚未完成時Connection refused，沿同一launch handle再次查驗通過，沒有再次啟動或擅自終止新服務。未commit／push；[ltn-news-release-proof.json](evidence/source-acquisition/20261010/ltn-news-release-proof.json)。
- 正式既有`5314_TWO_v3_report_job_6d4d98252427.html`僅刷新一次資料，**HTTP200／26.425秒**。Alternative Search **degraded／7／insufficient_candidates → success／8／sufficient_candidates**；raw **24→25**、rejected **17→17**，舊錯日期／公司不符／重複記錄沒有消失。新保存[9/22原文](https://ec.ltn.com.tw/article/breakingnews/5582751)，完整136,458bytes原hash／日期與final native cache相同、收據重驗通過；它是多檔注意／處置股票的新聞，5314影響未評估，不能宣稱不同獨立事件或經模型確認的投資結論。
- LTN子入口本次沿同原index／article raw cache、**零HTTP**，原取得epoch **1791568390.174797／1791568390.4827409**保持；父Alternative仍有真搜尋工作，對回canonical fetch ID **35a05779f38c444b96b63504d97a5fcc**及event **430075**一筆fetched_count／record_count8。全部同fetch事件保存30 fetched、10 local block、20 aggregate、3 fresh cache，沒有只挑成功。原HTML／Markdown／analysis_evidence／五份品質metadata不變、四份index hash一致、新analysis_jobs差集0；data trust **fresh91→fresh91**、needs_rerun／analysis_text_stale1。這是資料與來源品質門檻補齊，不是重新產出AI報告或通過原報告品質gate。[formal-report-refresh-proof](evidence/source-acquisition/20261010/ltn-news-formal-report-refresh-proof.json)、[linked-events](evidence/source-acquisition/20261010/ltn-news-formal-report-linked-events.json)。
- **02:15:24台灣時間**正式原近24h二十類仍 **17／20嚴格>80%**；財報 **45／71（63.380%）**、近期事件 **168／214（78.505%）**、社群 **48／95（50.526%）**。父搜尋本次有一個真成功觀測，其他變化亦包含真資料刷新與舊事件自然離窗，不能全歸功於新入口。全部原二十類goal仍active，未改驗收或重標歷史。[ltn-news-after-sla.json](evidence/source-acquisition/20261010/ltn-news-after-sla.json)、[completion-check](evidence/source-acquisition/20261010/ltn-news-completion-check.json)。

### 自由財經最新文章與缺全名公司的入口修正（2026-10-10）

- 續查美德醫療9103既有報告：社群已三筆／success，近期搜尋仍七筆／不足八筆；company_identity來自既有quote／公司設定，legal_name為null。原LTN備援因此直接停止。普通匿名原索引實際HTTP200／35,013bytes，找到三個結果，但最新文章的直接時間是「1天前／2天前」，舊parser也全數跳過。兩個可分辨問題已各以公開行為先重現，共 **2 failed**；不是假設供應商沒有內容。[official-anchor-new-entry-research-proof](evidence/source-acquisition/20261010/ltn-9103-official-anchor-new-entry-research-proof.json)。
- 同一原索引的三篇完整原件逐份讀回，其中[10/08市場注意股新聞](https://ec.ltn.com.tw/article/breakingnews/5600182)及[10/07處置股票新聞](https://ec.ltn.com.tw/article/breakingnews/5598886)正文都明示美德醫療-DR（9103）；中間特殊號碼鈔券文章沒有9103股票身分，不以搜尋命中收錄。10/08原文meta兩份相同 **2026-10-08T18:15:16+08:00**，直接可見clock **2026/10/08 18:15**；標題提及處置10/12是未來生效日，不當發布日期或宣稱9103本身遭處置。[relative-date-complete-originals-research-proof](evidence/source-acquisition/20261010/ltn-relative-date-complete-originals-research-proof.json)。
- 唯一owned runtime修改為`ltn_stock_news.py`，saved-before在`/tmp/stock-agent-ltn-anchor-before-20261010`。已觀測的相對時間只發現原文，原精確絕對日期／三十天／未來日期／原文meta與直接clock門檻保持；收據標`relative_discovery_only`並綁內容hash。缺法人全名時，讀固定同市場TWSE／TPEx主檔，以代號、精確公司簡稱、完整全名與十四天內出表日建立anchor，保留原取得epoch／完整raw hash；沒有更動原identity、alias或八筆／多publisher門檻，也沒有啟用SGX。
- 主檔沿既有IssuerNewsHttp的匿名固定URL、TLS、大小／deadline、raw cache與cooldown，工作在原十秒／父期限之內；缺值才查、異常型別不救回、主檔錯公司／過期／矛盾或期限／lease失效時不讀新聞。只有已封存完整主檔才建anchor，hash／當期出表日／原取得時間隨文章通過實際news projection／JSON snapshot重驗；改動或移除anchor／日期提示不能generic fallback。
- 修正後基本 **52 passed**，新增的主檔／原發布／期限／收據負測及相關十八組 **285 passed**；其後新增TPEx市場分派驗證，沿同一未變runtime的聚焦檢查 **31 passed**。一次套件檔名錯誤造成no tests ran，不算測試通過；另一次人工構造的非空全名負測與原完整設定信任契約不符，改為真正有anchor收據遭遇衝突全名的保存重選場景，不冒稱它是新來源錯誤修復。舊5314正式保存的絕對日期收據保持逐欄相同，current validator仍接受；[existing-formal-receipt-compatibility-proof](evidence/source-acquisition/20261010/ltn-anchor-existing-formal-receipt-compatibility-proof.json)。
- 真父Alternative流程 **3.140秒／八筆／sufficient_candidates**。完全同一批captured SearchResult只換saved-before LTN，仍 **七筆**；不拿前後不同搜尋結果比較。新原文由真TWSE／LTN原bytes暖cache重驗，子來源零HTTP、原epochs／hash未更新，既有搜尋仍有十二次provider callback（包含local block，不當十二次HTTP）。研究觀測沒有寫正式SLA或改報告；[ltn-anchor-native-search-proof](evidence/source-acquisition/20261010/ltn-anchor-native-search-proof.json)。
- 獨立覆核 **101 passed**，三份完整原件hash重播、TPEx缺全名及舊5314收據hash相容通過，未解material finding0；final runtime SHA **d16d0fdf0e1141ed0541607d3fb49a0e343e1dc5cbfee3ce30bc5644b1d57b7b**。[ltn-anchor-review-proof](evidence/source-acquisition/20261010/ltn-anchor-review-proof.json)。自前次API **02:12:41**啟動後runtime與env完整mtime盤點只有該檔改動，六queue全0、scheduled空集合保留，Redis BGSAVE成功。沿原start_mac.command重載，新launcher **36650**／worker **36678**／API **36680**與canonical backend cwd／父子關係核對，healthz／readyz200、目前SHA同覆核。[ltn-anchor-release-proof](evidence/source-acquisition/20261010/ltn-anchor-release-proof.json)。
- 正式既有`9103_TW_v4_report_job_4c75689b2e28.html`只刷新一次資料，**HTTP200／22.615秒**。Alternative **degraded／七筆／insufficient_candidates → success／八筆／sufficient_candidates**；新增5600182原文收據重新選取通過，title／text／date與native probe同值。正式前後raw **22→22**、rejected **15→14**是不同時間的upstream結果，不據此聲稱排除紀錄被修正；來源修正因果由前節同批SearchResult舊七→新八支持。
- 主檔／LTN索引／文章均沿真raw暖cache，原取得epoch **1791570551.3784451／1791570551.79669／1791570651.561375**保持，子來源零HTTP；父搜尋有真實工作。保存fetch ID **44a3f2c9870247d8aadaa7ac0223e5b4**、Alternative event **430152**為一筆fetched_count。全部同fetch事件保留 **26 fetched／6 empty／18 local block／1 degraded／17 aggregate／8 failed／1 empty cache／1 stale cache**，未只挑成功。原HTML／Markdown／analysis_evidence／五份gate相同、四份index hash一致、新analysis_jobs0；data trust **partial56→partial56**，財報critical／analysis_text_stale1／needs_rerun仍保留。這次補到新聞來源品質門檻，沒有產出新AI報告或解除財報警示。[formal-report-refresh-proof](evidence/source-acquisition/20261010/ltn-anchor-formal-report-refresh-proof.json)、[linked-events](evidence/source-acquisition/20261010/ltn-anchor-formal-report-linked-events.json)。
- **02:52:11台灣時間**正式原近24h二十類只有 **16／20嚴格>80%**：同業 **40／50（80.000%，等於80仍不通過）**、財報 **41／70（58.571%）**、近期事件 **156／202（77.228%）**、社群 **44／83（53.012%）**未達標。此次真資料刷新仍有原財報／同業／新聞來源失敗；刷新前同業40／49（81.633%），新增一筆失敗後變40／50，不能略過它或把goal改成≥80%。其他時段比較亦有歷史自然離窗，不能把個案新八筆說成全系統取得率已改善。原分母／歷史／免費與quality契約保持，goal仍active、未達成；[ltn-anchor-after-sla](evidence/source-acquisition/20261010/ltn-anchor-after-sla.json)、[completion-check](evidence/source-acquisition/20261010/ltn-anchor-completion-check.json)。

### 財報與投資網誌免費原件續查（2026-10-10）

- 騰輝[英文財務列表](https://www.ventec-group.com/investors/financials/financial-reports/)另提供2023中英文原件。今次普通匿名TLS GET完整取得[英文版](https://www.ventec-group.com/media/114640/2023q4fr-english.pdf) **864,163bytes／72頁**及[中文版](https://www.ventec-group.com/media/114646/2023q4fr-ch.pdf) **11,753,378bytes／65頁**。前次中文有界下載未完成，這輪以單一研究12.5MB上限取得原件，正式XBRL／archive／provider限額未放寬。中文版超過既有archive8MiB，archive明記unavailable，另保存未更改的完整原PDF與hash；英文原件也按hash封存，英文封面明示中文優先。
- 目視核對中文第7、11、12頁及英文11、12頁：2022比較欄資產總額 **5,023,032仟元**、明標重編後，與舊iXBRL的5,007,482仟元差異有原件支持；2022營業現金流1,465,504與設備購置85,429仟元中英文一致。兩份現金流表仍無明示無形資產購置列，不能把無列當零或自行解除不完整比較表衝突。2022中文另一份原件本次HTTP200後傳輸15秒逾時，rc28，沒有完整bytes/hash，不算取得成功。[ventec-alternate-financial-and-notes-research-proof](evidence/source-acquisition/20261010/ventec-alternate-financial-and-notes-research-proof.json)。
- 新免費[CMoney投資網誌9103索引](https://www.cmoney.tw/notes/?tag=75447)在native讀取為當期10/08；Web工具讀回舊2025索引，不能將其cache當現行站況。原[1279557文章](https://www.cmoney.tw/notes/note-detail.aspx?nid=1279557)匿名HTTP200／170,918bytes，head與NewsArticle明示同一發布時間 **2026-10-08T09:16:35+08:00**、原URL與股票對。完整原HTML可免費取得，但本文容器有推廣／作者尾註，並明示CMoney研究員透過AI產出新聞；這是publisher研究新聞候選，不是一般社群原文或獨立財務／情緒驗證。沒有接入social_sentiment、判斷情緒或灌成功率；[cmoney-notes-original-new-entrance-research-proof](evidence/source-acquisition/20261010/cmoney-notes-original-new-entrance-research-proof.json)。

### 美德9103當期醫材候選與數值缺口（2026-10-10）

- 上輪為progress，本輪沿用原二十類／近24小時／逐類嚴格>80%及免費限制。新免費[MoneyDJ其他醫療器材同業表](https://m.moneydj.com/z/zh/zha/zh00.djhtm?A=C017137&B=5)普通匿名TLS HTTP200、完整16,914bytes Big5原件，含9103美德醫療-DR與十家公司，逐列直接交易日2026/10/08；股價／報酬欄不用作同業數值。當期TWSE公司主檔精確美德向邦醫療國際股份有限公司／MEDTECS／官網／BM註冊地支持目標身分，FinMind原4333列中的9103仍是2024-12-04，不改舊列日期或借存託憑證大類作產業證據。[new-entrance-research-proof](evidence/source-acquisition/20261010/medtecs-published-medical-cohort-new-entrance-research-proof.json)。
- 原流程用同一份完整current master重播仍零家。新public DynamicPeerMetricsProvider native取得 **五家complete數值**：4107／4116／4126／4735／6730.TWO。原精細產業門檻另排除五家；最多十次candidate SDK查詢／五家輸出。七項quote數值與2025-12-31同年度營收／資產計算的週轉率取得成功，SDK未提供quote ratios財期或真HTTP／cache狀態，保持unknown；整體業務、財期與估值可比性仍False。[native-provider-proof](evidence/source-acquisition/20261010/medtecs-medical-peer-native-provider-proof.json)：3.796秒，兩個真普通TLS transport；[final-native-proof](evidence/source-acquisition/20261010/medtecs-medical-peer-final-native-provider-proof.json)：3.024秒，兩原件暖快取／零HTTP、原epoch/hash相同。兩次研究formal SLA新增觀測均零。
- 身分／日期／產業／symbol／EQUITY／年度週轉與公開sync partial保留已有failing behavior後修正；另獨立覆核抓出來源HTTP診斷未flatten，先六模式 **6 failed**，再補一筆composite peer_discovery候選觀測與兩份component receipt。冷讀／混合／HTTP失敗／local cooldown／暖cache解析失敗均保留，原身分主檔不另計數值同業。主相關隔離 **177 passed**，獨立 **76 passed**、無未解material finding。[review-proof](evidence/source-acquisition/20261010/medtecs-medical-peer-review-proof.json)。
- 正式重載只包含三個reviewed runtime檔，自舊API啟動後連JSON/YAML/.env mtime核對均無無關變動；六queue queued／started／deferred全零、原scheduled空集合保持、Redis BGSAVE成功。新launcher46202／worker46230／API46232，healthz／readyz皆200，code hash相符。[release-proof](evidence/source-acquisition/20261010/medtecs-medical-peer-release-proof.json)。
- 正式既有`9103_TW_v4_report_job_4c75689b2e28.html`只刷新一次，**HTTP200／23.050秒**，數值同業 **0→5**。canonical fetch `6159679acf714c5eb6cb74375384be26` 的實際成功event430209／5筆，另既有aggregate430204不計取得；MoneyDJ／TWSE event430210保存十個候選及兩份原epoch/hash／cache，屬fresh_cache_count／零新HTTP。首次驗證腳本錯把aggregate與canonical兩筆當重複取得而assert失敗，完整保留診斷；只readback修正驗證假設，沒有第二次refresh。[formal-report-refresh-proof](evidence/source-acquisition/20261010/medtecs-medical-peer-formal-report-refresh-proof.json)。
- HTML／Markdown、analysis_evidence與五份原品質gate保持，四個index hash讀回一致、analysis_jobs差集0；prompt及自動相對估值候選均零。data trust **56→56／partial**、financial_statements仍critical、needs_rerun／analysis_text_stale1。完整fetch紀錄含27 fetched、6 empty、18 local、1 degraded、17 aggregate、7 failed及三種cache，失敗未藏；[linked-events](evidence/source-acquisition/20261010/medtecs-medical-peer-formal-report-linked-events.json)。
- **03:48:22台灣時間**最新原近24h仍 **16／20嚴格>80%**。dynamic_peer_metrics已通過；未通過是財報 **36/63=57.1429%**、同業發現 **24/31=77.4194%**、近期事件 **137/174=78.7356%**、社群 **43/63=68.2540%**。變化包含實際取得與舊觀測自然離窗，不把暖快取、研究或彙總灌入原分母／成功數。全部二十類goal仍active，該輪為有可驗證正式進展，非complete或blocked。[after-sla](evidence/source-acquisition/20261010/medtecs-medical-peer-after-sla.json)、[completion-check](evidence/source-acquisition/20261010/medtecs-medical-peer-completion-check.json)。

### TDR財報入口與全年度公告續查（2026-10-10）

- 按原分類讀今日canonical ledger，最新未解財報是9103：Yahoo SDK四年partial、FinMind空結果與iXBRL少於五份年度合併申報。最新Alternative近期八筆／社群三筆已有真success，不能把舊低率都解讀為現行路由完全失效；同業發現仍有9103 Alternative Search empty。[post-medical-remaining-gaps-today-ledger](evidence/source-acquisition/20261010/post-medical-remaining-gaps-today-ledger.json)。
- 新查[官方財務比較e點通使用說明](https://mopsfin.twse.com.tw/terms)，完整匿名native HTML **HTTP200／27,882bytes** 明示資料涵蓋範圍不包含TDR公司。這可解釋該備援不能補9103；沒有因此重標歷史失敗、刪除財報類或宣稱TDR不需要財務證據。
- 美德官網另提供[2021英文全年度公告](https://www.medtecs.com/file/2021FullYear.pdf)、[2021中文](https://www.medtecs.com/file/2021FullYear_CH.pdf)、[2022英文](https://www.medtecs.com/wp-content/uploads/2022-full-year-EN.pdf)及[2022中文](https://www.medtecs.com/wp-content/uploads/2022-full-year-CH.pdf)。普通匿名TLS各HTTP200、無重導／重試，分別完整 **717,257／779,497／688,556／810,017bytes**，各 **29／27／31／28頁**，原PDF／hash與archive readback一致。這些是另一組全文原件，不是先前已讀的annual-report file。
- 逐頁提取並完整目視兩中文原件第6／7頁：均為USD仟元／集團年度現金流表，當年度標未經查核。2021公告當年CFO33,915與2022公告的2021查核比較數29,727不同；不能用取得較早的未查核公告覆蓋後續查核年度數。兩份完整現金流仍未明列無形資產購置，無列不填零，尚未建立完整五年typed projection或TWD／TDR換算。四份新原件可免費完整取得，但仍research-only、provider未啟用、formal SLA新增0。[research-proof](evidence/source-acquisition/20261010/medtecs-full-year-announcements-research-proof.json)。
- 本輪正式醫材數值來源已有可追溯保存進展，dynamic_peer_metrics近24h **36/44=81.8182%**；未達全類別驗收。後續續作保留既有已發布成果，優先處理9103已驗證醫材候選的peer-discovery公開整合，以及有年度／查核／幣別與原股對應證据的TDR財報來源；不能把原件可下載等同財報品質已通過。

### 美德醫材候選接入公開同業發現（2026-10-10）

- 上輪為progress：五家numeric候選已正式保存。本輪讀回doctor、正式PID、原SLA與snapshot，發現數值來源取得十個publisher leads，但`peer_discovery_results`仍零；最後Alternative Search回empty。新`MedicalPublishedPeerCohortProvider`只支持9103.TW精確公司context與原精細industry，沿原有界匿名getter提供至多五個publisher候選，兩個不同可重驗候選已足量時才省去一般搜尋；不足仍fallback，未放寬原八筆新聞或同業可比性門檻。[baseline-sla](evidence/source-acquisition/20261010/medical-discovery-baseline-sla.json)。
- 新record保存兩份完整HTTP原件receipt與明示selected SDK master mapping，日／名稱／市場／hash保存後再驗；原件body不進model。三個comparability旗標仍布林False；目標／peer日期必須不晚於原取得日。醫材source type／policy／archive marker強制專用驗證，不能走generic文字同業或以數字0冒充False；公開prompt投影移除archive路徑。新功能先18個缺入口red，再重現一個public prompt洩漏；獨立覆核的四類P2另以 **7 failed** 反例重現後修正。相關主隔離 **235 passed**、獨立 **98 passed**（新integration30項），無未解material finding。[review-proof](evidence/source-acquisition/20261010/medical-discovery-review-proof.json)。
- Native public provider先 **2.422秒／success／五筆**，raw cache自然過期後普通TLS兩入口實際回200；TWSE完整1,327,573bytes、MoneyDJ完整16,913bytes。最終修正後再驗 **0.679秒／skipped_fresh_cache／五筆／零HTTP**，原兩份epoch/hash相同。對同一批真records，saved-before sufficiency=False、現在=True；local JSON merge保存五筆並重驗、prompt numeric peers仍零。研究沒有cache_financial_payload或正式ledger寫入，formal SLA新增觀測0。[native-proof](evidence/source-acquisition/20261010/medical-discovery-native-provider-proof.json)、[final-native-proof](evidence/source-acquisition/20261010/medical-discovery-final-native-provider-proof.json)。
- 正式只重載六份reviewed runtime檔，API原啟動03:39:15後含JSON/YAML/.env mtime查驗沒有無關變更；六queue queued／started／deferred全零、scheduled空集合保持、Redis BGSAVE成功。新launcher51270／worker51298／API51300，healthz／readyz200，檔案SHA與review相符。[release-proof](evidence/source-acquisition/20261010/medical-discovery-release-proof.json)。
- 正式9103既有報告僅刷新一次，**HTTP200／27.548秒**，同業發現 **0→5筆**，完整原件保存後逐筆重驗True；canonical fetch `5e13d3a16d5240a49fe685652ac03da0` 無Alternative peer-search event。醫材來源在數值／發現步驟各一次暖讀，event430277／十個候選與430298／五筆均fresh_cache_count／零新HTTP，不冒充兩次新取得。HTML／Markdown、analysis_evidence與五份品質gate保持；四個index hash一致、analysis_jobs差集0、needs_rerun／analysis_text_stale1。data trust仍 **56／partial**、financial_statements critical，prompt及自動相對估值numeric peer count零。[formal-report-refresh-proof](evidence/source-acquisition/20261010/medical-discovery-formal-report-refresh-proof.json)。
- 完整operation保留23 fetched、5 empty、9 local、8 failed、1 degraded、17 aggregate與兩fresh／一empty／一stale cache。實際另有SerpAPI timeout、FinMind月營收／財報／新聞空結果、iXBRL不足五年與TWSE公告索引未取得；未藏失敗或宣稱這次改善全部來源。[linked-events](evidence/source-acquisition/20261010/medical-discovery-formal-report-linked-events.json)。
- **04:08:56台灣時間**原近24h仍 **16／20嚴格>80%**：財報 **36/66=54.5455%**、同業發現 **24/31=77.4194%**、近期事件 **139/178=78.0899%**、社群 **44/64=68.75%** 未過。這次候選實際保存且避免真空搜尋，但暖讀未讓原取得率增加；原二十類／分母／TTL／歷史及品質門檻不變。goal仍active，上一輪與本輪均有正式進展，不標complete或blocked。[after-sla](evidence/source-acquisition/20261010/medical-discovery-after-sla.json)、[completion-check](evidence/source-acquisition/20261010/medical-discovery-completion-check.json)。


### 官方財報重複下載改善與新免費入口續查（2026-10-10）

- 再核對四份免費[MOPS 財務比較](https://mopsfin.twse.com.tw/compare/report)原始現金流 HTML：3023／2206／1325 的2021年、6672的2022年仍無明示「取得無形資產」支出。信邦有「處分無形資產」正值，不能當取得支出或補零；維持既有缺科目及重編比較表衝突。[comparison-research-proof](evidence/source-acquisition/20261010/missing-cashflow-official-comparison-research-proof.json)。本次Yahoo免費SDK實读的3023／2206三表2022–2025適用欄位有值，但額外2021欄仍缺必要值；未改原五年完整性、觀測口徑或partial狀態。[SDK-research-proof](evidence/source-acquisition/20261010/yahoo-aligned-period-new-research-proof.json)。
- 新試讀[StockAnalysis 信邦損益表](https://stockanalysis.com/quote/tpe/3023/financials/income-statement/)、[資產負債表](https://stockanalysis.com/quote/tpe/3023/financials/balance-sheet/)、[現金流量表](https://stockanalysis.com/quote/tpe/3023/financials/cash-flow-statement/)，三份普通匿名TLS完整HTTP200，189,765／253,935／240,044bytes，列FY2021–2025、百萬TWD。但S&P標準化營業利益與原申報口徑不同，無形資產列是買賣淨額，不能補成取得支出；[使用條款](https://stockanalysis.com/terms-of-use/)限制一般自動／批量存取與資料產品用途，依robots的AI搜尋例外不等於正式供應商授權。[資料來源说明](https://stockanalysis.com/data-sources/)也明示S&P不允許下載。保留人工核對候選，未接正式provider、未填缺值。[native-original-proof](evidence/source-acquisition/20261010/stockanalysis-free-financial-portals-research-proof.json)。
- 新窄範圍改善只保留**五份同公司、同年度、TWD官方原件均解析成功，且每年九科目僅可能缺明示無形資產取得支出**的已驗證失敗300秒。manifest含五份原件URL／year／hash與已解析原值；parser檔案hash變更、到期、儲存不可用或證據不符即重試。安全驗證頁、不足五份索引、錯公司／幣別／空XML、quota／transport／其他解析錯誤均不得持續暫停來源重試。成功資料與原raw／radar TTL未改，缺值不补零、FilingError／error／record_count=0保持。暖讀重新驗manifest與parsed facts、不重新下載原件；保留原取得時間，清除全部舊correlation含data_fingerprint，使用本次fetch／operation，HTTP=false、attempts=0。
- 先以正式collector的HTTP200安全頁、錯公司與舊fingerprint反例重現 **3 failed／15 passed**，修正後主相關隔離 **243 passed**、獨立 **101 passed**，另六個schema／issuer／year／金額／缺科目反例均保留來源退路，無未解material finding。[review-proof](evidence/source-acquisition/20261010/financial-gap-cache-review-proof.json)。最後真实官方六原件測試首次 **6.872647秒**、暖讀 **0.001407秒／零新增HTTP**，error／零筆完整官方資料、原時間、八個history输出與Yahoo degraded均相同。研究用私有InMemoryCache，正式SLA新增0。[final-native-proof](evidence/source-acquisition/20261010/financial-gap-cache-final-native-provider-proof.json)。
- 正式僅重載三份reviewed runtime檔；實際舊API起始04:06:52後，包含JSON／YAML／.env的mtime查驗只有本輪三檔，六queue待處理／執行／deferred皆0、scheduled空集合保持、Redis BGSAVE成功。新launcher59784／worker59812／API59814，healthz／readyz200、三份SHA吻合。[release-proof](evidence/source-acquisition/20261010/financial-gap-cache-release-proof.json)。
- 3023既有報告兩次真正data-only刷新用於一次cold／warm驗證，皆HTTP200，整體 **26.809607秒→14.870159秒**；官方財報步驟 **8348ms→2ms**、暖讀zero HTTP／provider attempts。原error及零完整記錄保留，cold fetch `618e9c4567fb42959edb87de7353c4e3`／warm `08414f092be6435390d22beaa11082a7`、operation不同、ISO原取得時間相同。正式gap receipt實際在SQLite cache_entries讀回；不能只憑doctor宣告Redis設定猜測此facade的持有位置。初版驗證程式假定cold audit有可選numeric epoch而中止，後以實際ISO欄位只讀完成核對，沒有再刷新或重抓。HTML／Markdown、analysis_evidence、五quality gates、四index hashes與原年度輸出均保持，期間analysis_jobs新增0。[formal-refresh-proof](evidence/source-acquisition/20261010/financial-gap-cache-formal-report-refresh-proof.json)。
- 完整兩次operation保留55 fetched、5 failed、12 local、2 degraded、38 aggregate、4 fresh cache及3 empty cache；官方財報僅首次failed_count、暖讀empty_cache_count，均count0，未改歷史／分母／公式、未當成功。[all-linked-events](evidence/source-acquisition/20261010/financial-gap-cache-formal-report-linked-events.json)。**05:08:01台灣時間**近24h因真實新增與舊事件自然離窗，目前 **16／20嚴格>80%**；法說98/123=79.6748%、財報34/67=50.7463%、同業發現24/31=77.4194%、近期事件136/177=76.8362%仍未過。社群本輪未改程式，因旧觀測自然離窗重新超過80%，不能歸功於財報快取修正。未宣稱取得率或品質全面提升；goal仍active，不標complete／blocked。[completion-check](evidence/source-acquisition/20261010/financial-gap-cache-completion-check.json)。

### 新免費官方注意交易公告入口（2026-10-10）

- 由[證交所「公布注意有價證券」公開表單](https://www.twse.com.tw/zh/announcement/notice.html)的data-api及官方web-report.js／main.js靜態介面宣告核對原生 `/rwd/zh/announcement/notice`。普通TLS匿名GET不使用token、帳號或cookie，頁面HTTP200／16,570bytes；同站JSON查詢HTTP200／1,355bytes／0.148332秒，全部完整原件archive／readback／hash一致，研究formal SLA新增0。
- 查詢2026-09-10至10-09、精確9103美德醫療-DR，原JSON `stat=OK`、params／固定八欄／count／total均可核對，共四筆官方具名公告：2026-10-08、10-07、10-06、09-23。按明示民國年轉日期，保留原交易溢價與注意原因，不補造盤中發布時間；收盤價／本益比欄不當新即時行情。這是**近期官方交易風險事件**候選，非社群樣本、財務報表完整性或同業可比性證據。尚未掛入正式provider／snapshot，因此不增加正式取得成功分子。[page-original-proof](evidence/source-acquisition/20261010/twse-notice-new-free-entry-research-proof.json)、[JSON-original-proof](evidence/source-acquisition/20261010/twse-notice-json-new-free-entry-research-proof.json)。


### 免費官方注意交易公告接入正式近期事件（2026-10-10）

- 上輪為progress：財報反覆下載修正正式驗證、找到四筆真正官方公告。本輪沿原二十類／近24h／各嚴格>80%免費門檻，將證交所[注意交易公告JSON](https://www.twse.com.tw/rwd/zh/announcement/notice?startDate=20260910&endDate=20261010&stockNo=9103&querytype=2&sortKind=DATE&response=json)接入台股四位上市股票的近期事件備援。普通匿名TLS、固定host/path/六query參數、單一股票／最多30日／250KB，沿既有零重導／零retry／5秒单次與8秒整體上限、persistent cooldown與1800秒原始bytes快取；不使用登入／token、不开TLS例外。
- 固定八欄、stockNo/query/title/params/issuer/date/count/total與日期唯一性均須可核對，完整原JSON先封存，再按指定股票／日期原行構建record；保存後每次重選重讀原件，重新建構critical fields與digest。日期保持day precision，未補造盤中時間；原公告原因完整保留，價格／PE欄不填即時行情、公告不充作社群或財報證據。receipt/source_type/source/source_role強制專用驗證，刪receipt或改文字／日期／link／scope／bool類型不能走generic alias放行。
- Workflow只在原curated evidence不足時讀此補充入口；已有原八筆、三publisher及兩feed完整證據才作local_block／zero HTTP略過。新notice不加進CURATED_FEEDS，不降低Alternative Search/Yahoo原門檻、筆數上限或延長總deadline；新record經原bundle／公司日期／recent/additional選取保存，失敗／空列／部分來源仍留帳。真实3023原查詢为statOK/data=[]，保持unavailable/count0，不能推論無事件／中性。[no-row-native-proof](evidence/source-acquisition/20261010/trading-notice-no-row-native-proof.json)。HTTP200错误JSON須在raw-cache成功callback前驗證，不能獲成功1800秒TTL；原source error120秒retry protection保持，不假稱已確認公司缺口。
- 新入口初始22項missing-feature／catalog／workflow驗證失敗；兩項獨立P2（原件重驗後deadline漏查、request/context換股或市場）先重現 **6 failed／36 passed** 再修正。collector最終重驗後查deadline，request僅允許同issuer明示.TW或plain→同代碼.TW，其他local_block／zero HTTP。主相關隔離 **250 passed**、獨立 **158 passed**及兩種合法request/context組合通過，無未解material finding。[review-proof](evidence/source-acquisition/20261010/trading-notice-review-proof.json)。另用saved-before workflow確認旧test_provider_workflow的並行search expectation原本已失敗，僅修三個测试期望配合既有分階段流程，無改runtime gate；新測試frozen cutoff的lazy import副作用也已隔離修復。
- 最後native public provider **0.161868秒／success／四筆**，warm **0.001019秒／skipped_fresh_cache／零HTTP**、同hash／原epoch。四笔merge後再验都過；同一批真record的saved-before merge0、newmerge4（这是离线對照，非新取得）。研究私有InMemoryCache、正式raw cache未被暖入，研究formal events0。[last-native-proof](evidence/source-acquisition/20261010/trading-notice-last-native-provider-proof.json)。
- 正式只重載七份reviewed runtime檔；舊API實際05:01:42啟動後，包含JSON/YAML/.env的mtime查驗無無關修改。六queue待處理／執行／deferred皆零、scheduled空集合保持，Redis BGSAVE成功；新launcher65656／worker65684／API65686，healthz/readyz200、七份SHA一致。[release-proof](evidence/source-acquisition/20261010/trading-notice-release-proof.json)。
- 美德9103既有報告只刷新一次，**HTTP200／18.814478秒**，官方注意公告 **0→4筆**、可用近期內容 **8→12筆**（recent/additional共同保存），每笔原件重验通過。帳本event **430485／success／record_count4／fetched_count／HTTPtrue**，canonical fetch `5ec7f0ffa1aa4fcbbd418c7a2f74a3de`，不是cache或研究紀錄灌入成功。舊五家醫材候選仍保存且可重驗；HTML/Markdown、analysis_evidence及五quality gates保持，四index hashes吻合、analysis_jobs差集0。data trust仍 **56／partial**，needs_rerun／analysis_text_stale1，未宣稱旧分析已吸收新增事實或品質警示已消除。[formal-refresh-proof](evidence/source-acquisition/20261010/trading-notice-formal-report-refresh-proof.json)。
- 该operation全ledger仍保留25 fetched、5 empty、10 local、1 degraded、17 aggregate、7 failed、1 empty cache／1 fresh／1 stale cache，未刪FinMind／MOPS／搜尋失敗。[all-linked-events](evidence/source-acquisition/20261010/trading-notice-formal-report-linked-events.json)。**05:34:29台北時間**最新原近24h为 **15／20嚴格>80%**：職缺33/42=78.5714%、法說96/124=77.4194%、財報33/69=47.8261%、同業發現25/32=78.125%、近期事件135/178=75.8427%未过；舊觀測自然離窗與本輪真實其他失敗均保留。這次新增可追溯官方風險事實，仍不是全系統80%完成；goal維持active，不標complete／blocked。[completion-check](evidence/source-acquisition/20261010/trading-notice-completion-check.json)。


同輪新增公告的model邊界再驗：正式saved report的正常full formatter原本仍帶內部 `trading_notice_receipt.original.raw_response_path`。先以pure copy與公共formatter各重現一個失敗，再將notice receipt加入既有internal keys，並讓market_catalysts.items走既有非mutation投影，原typed source guard及存檔收据不刪。對同一實際saved snapshot，兩筆prompt內notice的正文／日期／source／link保留，四筆saved原件receipt仍在；snapshot hash不變。正常full prompt **115,779→113,733字元，實測少2,046字元**；另四筆notice-only projection7,608→4,276字元。這是字元測量，不代表已量測token或模型延遲；未呼叫模型。[final-prompt-boundary-proof](evidence/source-acquisition/20261010/trading-notice-final-prompt-boundary-proof.json)。相關來源／信任／prompt budget隔離 **282 passed**，此兩行尾修獨立 **77 passed**，無未解material finding。[prompt-review-proof](evidence/source-acquisition/20261010/trading-notice-prompt-review-proof.json)。較廣Agent19/24 lossless suite為291passed／2 optional skipped／3 Agent24 Gemini3.5FlashLite compact expectation failed；用saved-before formatter與keys在隔離重現同三assert，非此尾修引入，未修改generation config／agent model routing，不能宣稱全模型capacity驗證完成。

尾修正式僅再重載prompt_evidence.py／prompt_builder.py，API實際05:31:47起始後包括JSON/YAML/.env查驗只有兩owned檔；原七source檔SHA保持。新launcher67591／worker67619／API67627，healthz/readyz200、六queue待處理／執行／deferred皆0、scheduled空集合保持、Redis BGSAVE成功；九個active runtime檔hash核對，沒有再刷新報告、呼叫provider／模型或回寫artifact。[prompt-release-proof](evidence/source-acquisition/20261010/trading-notice-prompt-release-proof.json)。**05:44:22台灣時間**原20類近24h仍15類嚴格>80%，未過者與05:34觀測相同：職缺78.5714%、法說77.4194%、財報47.8261%、同業發現78.125%、近期事件75.8427%。本輪有正式四筆新資料與模型輸入減量進展，goal仍active，未標complete／blocked。[final-completion-check](evidence/source-acquisition/20261010/trading-notice-prompt-completion-check.json)。

### 櫃買官方細分產業鏈接入同業發現備援（2026-10-10）

- 新匿名原件為 [9945 公司鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=9945)、[營造產業鏈](https://ic.tpex.org.tw/introduce.php?ic=S000)、[1216 公司鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=1216)與[食品產業鏈](https://ic.tpex.org.tw/introduce.php?ic=M000)。四頁普通 TLS GET 均 HTTP200，完整 bytes 封存／讀回；沒有帳號、付費授權或 bot/proxy bypass。exact issuer section、同段名單及 SDK 最新全市場身分日共同核對。SDK 保存的是 selected mapping，未冒稱完整原主檔 HTTP。頁面沒有成員生效日，觀測日只來自原頁取得時間；公司自行輸入的產業鏈列示不證明整家公司或財務可比。
- 新 `official_segment_discovery.py` 與四份既有 wiring 檔為本輪五檔 runtime 範圍；saved-before 保留在 `/tmp/stock-agent-official-segment-before-20261010/`。只支援潤泰新9945／統一1216的明示上市 EQUITY context；營造名單核對達欣工2535、根基2546、建國5515、潤弘2597，食品加工核對聯華1229、福懋油1225、大統益1232、南僑1702。四個可比性／生效日旗標只接受布林False，無發布日期欄。原頁限定兩個固定URL、每頁250KB／五秒、collector原件取得解析十二秒、1800秒原bytes快取；錯原件不能獲正TTL。期限、raw hash、原取得epoch與snapshot重驗均保持，typed record不能generic fallback，prompt不含內部archive。SDK master載入沿既有共用流程，不列入這十二秒collector上限。
- 初始缺功能19項red；接入後擴充至相關 **215 passed**、儲存／刷新／取得率 **229 passed**。原站桌面 panel 只在title標段名、mobile才有bold，曾因額外要求兩個panel均有bold而13failed；依完整原件修正格式判定後全過，未曾載入正式。另一次測試命令含不存在檔名，no tests ran不當成功。獨立覆核 **215 passed**／未解material finding0、五SHA核對。[review](evidence/source-acquisition/20261010/official-segment-review-proof.json)、[scoped diff](evidence/source-acquisition/20261010/official-segment-scoped.patch)。
- 最終 native public provider：9945 **0.995秒 cold→0.108秒 warm**，1216 **0.446→0.089秒**，各四筆；暖讀零HTTP、相同原epochs與hash。JSON保存後全部重驗通過，模型投影無原件路徑。同一批真候選 saved-before merge0／newmerge4；此為重播對照，非正式新取得。研究私有InMemoryCache，正式SLA新增0；先前因上述panel判定造成的native error亦未當成功。[native proof](evidence/source-acquisition/20261010/official-segment-native-provider-proof.json)。
- 本輪 fallback 在既有至少兩家已核對 publisher 候選足夠時 local_block／zero HTTP；新候選不足、錯誤或原件不可重驗時仍走原搜尋。統一既有報告已有五筆，所以未另作不必要正式刷新。舊API05:43:55啟動後含JSON/YAML/.env的mtime查驗僅五owned檔變動；六queue待處理／started／deferred全0、scheduled空集合與Redis BGSAVE成功。依start_mac.command重載，新launcher **72330**／worker **72358**／API **72360**、canonical backend cwd與父子關係核對、healthz/readyz200；五owned及六preserved先前runtime檔SHA一致。未commit/push。[release proof](evidence/source-acquisition/20261010/official-segment-release-proof.json)。
- 正式只刷新一次既有 `9945_TW_v4_report_20261009_150150.html`，**HTTP200／24.979秒**。同業發現 **0→4筆**，每筆原件重驗通過，Alternative peer search未執行。真來源帳本event **430544**／success／record_count4／fetched_count／HTTPtrue，fetch ID `3ac03069cc5e40ba815f1cbecc6caec5`；完整operation保存30 fetched、8 local、19 aggregate、1 degraded、1 fresh cache、1 failed，沒有刪除其他失敗。HTML／Markdown、analysis_evidence與五quality gates保持，四index hashes吻合、analysis_jobs新增0。data trust **fresh88→fresh91**，仍needs_rerun／analysis_text_stale1，不宣稱舊AI分析已採用新增資料或原品質警示已消除。[formal proof](evidence/source-acquisition/20261010/official-segment-formal-report-refresh-proof.json)、[all linked events](evidence/source-acquisition/20261010/official-segment-formal-report-linked-events.json)。
- **06:13:22台灣時間**原二十類近24h仍 **15／20嚴格>80%**；職缺34/43=79.070%、法說98/126=77.778%、財報34/70=48.571%、同業發現26/33=78.788%、近期事件138/183=75.410%。只有該新來源的一次真成功可直接歸因本輪接入，其他變化包含這次其他provider工作與原事件自然離窗；未改歷史、分母、分類或門檻，goal仍active。[completion](evidence/source-acquisition/20261010/official-segment-completion-check.json)。

### 信邦原生財報API與騰輝2022英文完整原件（2026-10-10）

- 上輪有正式0→4同業候選進展，本輪續查最低取得率的財報缺口。讀原近24hcanonical ledger，當時33 fetched／16 failed／16 degraded；主要仍是9103五年不足／FinMind空、3023／2206／1325缺明示無形資產現金購置、6672不完整重編比較、7740首次合併年度不足，2851／2855舊fallback部分資料亦保留。未重標歷史。[financial-current-gap-audit.json](evidence/source-acquisition/20261010/financial-current-gap-audit.json)。初次web搜尋混入東元1504而非三陽2206，以及同名香港信邦；均未採用或混到公司資料。
- 信邦[官方財務頁](https://www.sinbon.com/tw/financial-info)普通匿名TLS HTTP200／17,210bytes，原HTML明示BASE_URI=/tw/及原app.js；同一官方JS HTTP200／1,467,481bytes，財務元件實際GET `invreport/items`，其原生[公開API](https://www.sinbon.com/tw/api/invreport/items)HTTP200／8,096bytes，共47列年度／季度／個體／合併財報。未猜query、執行網站腳本或使用登入。API、HTML與JS全部原件按hash封存／讀回。[catalog proof](evidence/source-acquisition/20261010/sinbon-new-financial-catalog-proof.json)、[script discovery](evidence/source-acquisition/20261010/sinbon-financial-script-discovery-proof.json)。
- API原2021合併file列，沿網站本身宣告移除`/download`，取得[完整2021合併原件](https://www.sinbon.com/tw/files/40ec4eb77d3531b)：HTTP200／5,159,294bytes／101頁／1.172秒。前14頁没有text layer，目視核對第2頁目錄、8頁EY查核、9頁資產與13–14頁年度現金流；2021營業現金流1,345,496仟TWD、設備購置541,353仟TWD、無形資產**減少**22,673仟TWD。後者是流入／處分，不是取得支出，原表未明列購置額；不能拿它補0或湊完整FCF。[sinbon-2021-consolidated-new-original-proof](evidence/source-acquisition/20261010/sinbon-2021-consolidated-new-original-proof.json)。
- 騰輝[官方歷年列表](https://www.ventec-group.com/cht/investors/financials/financial-reports/)另外的[2022英文合併原件](https://www.ventec-group.com/media/114508/7financial-report-2022q4-eng.pdf)普通TLS完整HTTP200／1,197,649bytes／69頁／9.903秒、archive讀回一致。第1頁聲明英文翻譯未獨立查核且中文優先；完整目視11–12頁，2022 CFO1,465,504／PPE85,429仟TWD，仍無明示無形資產購置。舊2022資產5,007,482仟TWD與後續重編5,023,032仟TWD差異仍保留。重讀已保存2023中文附註14、44頁，IAS12遞延稅資產／負債各增加15,550仟TWD可解釋資產差額，但它沒有補出現金購置額；不解除缺欄gate。[new original proof](evidence/source-acquisition/20261010/ventec-2022-english-new-original-proof.json)。
- 研究程式初有syntax與project interpreter缺PDFium錯誤，均發生在請求前；改用既有bundled PDF runtime讀原件，未安裝套件或改正式環境。新原件與catalog可供後續來源備援研究，**沒有建立完整五年財務投影**。未更動backend／正式cache holder／報告／模型／history或SLA公式，原11個runtime SHA及API72360確認相同；未正式refresh。[research verification](evidence/source-acquisition/20261010/new-financial-originals-research-verification.json)。
- **06:23:02台灣時間**最新正式原二十類仍15類嚴格>80%；職缺31/40=77.5%、法說91/119=76.471%、財報32/62=51.613%、同業25/32=78.125%、近期事件132/170=77.647%。本輪沒有正式provider工作，比例變化僅反映既有觀測自然離窗，不歸功於新原件。goal維持active。[completion check](evidence/source-acquisition/20261010/new-financial-originals-completion-check.json)。

同輪職缺入口排除：104公開公司頁顯示美德向邦股份有限公司（UBN70541649／wemocq0），政府登記英名MEDTECS(TAIWAN)CORP.，不是9103上市TDR法人本身。普通匿名公司jobs API實際403／5,504bytes，原拒絕回應封存；沒有把搜尋頁23職缺當issuer總數或將子公司名稱改為issuer alias。[104 boundary proof](evidence/source-acquisition/20261010/medtecs-subsidiary-job-entry-boundary-proof.json)。Jobstreet搜尋頁包含三筆具名Medtecs以及一筆其他雇主，雇主查詢連結另混入不相干公司；相對刊登日期在不同cache頁不同，未補造絕對日。單篇普通匿名native也回403／5,732bytes，未重試。其[條款](https://ph.jobstreet.com/terms)7d／9b明示自動資料取得需書面同意或特定API及其條款；目前無此授權，所以未列入免費自動provider，未啟用／補記錄或繞過拒絕。[Jobstreet boundary proof](evidence/source-acquisition/20261010/jobstreet-medtecs-free-entry-boundary-proof.json)。下一個安全調查方向是政府或issuer自有招募入口，仍須明確保留母子公司雇主範圍。

### 政府與企業招募新入口，以及7740舊簡稱銜接（2026-10-10）

- 原帳本職缺空資料案例包括9103、7740、6672、2236、1301；2236沒有可供本次刷新的既有報告。逐筆比對原saved context與當期TWSE名冊，7740舊SDK簡稱是「熙特爾」，當期官方簡稱是「熙特爾-創」、全名「熙特爾新能源股份有限公司」、統編55118186。原精確簡稱門檻使官方全名查詢落空。[gap audit](evidence/source-acquisition/20261010/job-gap-current-audit.json)、[saved contexts](evidence/source-acquisition/20261010/job-gap-saved-contexts.json)。
- 用當期官方簡稱作研究假說，104精確全名入口取得9筆近期職缺；修正後以**完全未改identity的原saved context**再做native查驗，4.329秒／success／9筆。每筆有精確雇主、編號、連結及2026-10-02或10-07刊登日，範圍僅為近期刊登樣本，不是完整職缺總數。1111仍被拒絕，沒有隱藏。兩次研究均formal SLA新增0。[hypothesis](evidence/source-acquisition/20261010/seetel-current-board-label-provider-native-proof.json)、[original-context proof](evidence/source-acquisition/20261010/seetel-original-context-provider-native-proof.json)。
- 唯一runtime修改在 `official_company_legal_name.py`：僅指定7740.TW的舊／新簡稱、當期全名與統編全部吻合，才返回帶 `seetel-current-twse-name-v1` marker的官方anchor；保存後重驗同一組欄位与marker。原市場／來源／hash／十四天出表日及取得epoch gate保持，不泛化刪除板別後綴，不改原company_identity或global aliases。Red 3 failed／9 passed；接入後名稱／職缺／trust等236 passed，刷新／runtime／其他official caller195 passed，獨立覆核247 passed且無未解material finding。[scoped diff](evidence/source-acquisition/20261010/seetel-name-scoped.patch)、[implementation](evidence/source-acquisition/20261010/seetel-name-implementation-proof.json)、[review](evidence/source-acquisition/20261010/seetel-name-review-proof.json)。
- 新[台灣就業通公司入口](https://job.taiwanjobs.gov.tw/internet/jobwanted/company_desc2.aspx?EMPLOYER_ID=4632&BRANCH_ID=)普通TLS HTTP200／155,425bytes，列出美德向邦股份有限公司、UBN70541649及五個職缺連結；沿原鏈結取得[洗滌作業員完整明細](https://job.taiwanjobs.gov.tw/internet/index/JobDetail.aspx?R2=11&EMPLOYER_ID=4632&HIRE_ID=14646671)，HTTP200／138,251bytes，工作編號14646671／截止2026-11-30。它是台灣子公司，不是9103發行法人；原職缺契約明示不含子公司，因此不接成issuer職缺、不計入原取得率。[company original](evidence/source-acquisition/20261010/medtecs-taiwanjobs-new-company-original-proof.json)、[job original](evidence/source-acquisition/20261010/medtecs-taiwanjobs-new-job-original-proof.json)。
- 台塑公司官網實際連至[自有招募站](https://cloud.fpcetg.com.tw/FPC/WEB/OM/Recruit/)，HTTP200／87,721bytes；職務介紹與人才儲備類別未明示個別開放期限，不能當作五個職缺。既有1301 exact-employer provider native24.508秒仍degraded/count0，但已正確取得當期全名／UBN75708007，不是缺統編快取遮蔽。[official portal](evidence/source-acquisition/20261010/fpc-official-careers-new-original-proof.json)、[1301 provider](evidence/source-acquisition/20261010/fpc-current-exact-employer-provider-native-proof.json)。
- [台塑企業新版招募站](https://hr.fpg.com.tw/job)自身JS明示公開 `fpghr-api` base、匿名 `selectJobsCurrentData_FD`／`selectJobsDetail_FD`唯讀查詢；普通TLS成功取得第一頁十筆樣本及五筆完整JSON明細，實際雇主為南亞兩筆、台塑石化一筆、台化兩筆，均非1301台塑。STS=P及列在current list只是該站當時發布狀態；TXTM是原異動時間，未推定首次刊登日或截止日。完整原件按hash封存、讀回一致，未登入／申請／註冊，這些研究未掛進formal provider或計數。[detail originals](evidence/source-acquisition/20261010/fpg-current-published-job-detail-research-proof.json)、[discovery verification](evidence/source-acquisition/20261010/government-and-fpg-careers-discovery-verification.json)。
- **06:51:03台灣時間**正式服務已載入唯一runtime修正，launcher78790／worker78818／API78820；preflight相對原06:12:33 API確認只有owned一檔異動，原十一檔hash保持。六queue空、scheduled原樣空、Redis BGSAVE成功、healthz／readyz200，未更動環境或模型路由。[release proof](evidence/source-acquisition/20261010/seetel-name-release-proof.json)。
- 正式只刷新一次 `7740_TW_v4_report_job_416a604d07f9.html`，**HTTP200／17.288秒／可驗職缺0→9**。原identity保持；HTML／Markdown／analysis_evidence／五quality gates未改，四index hashes吻合，新增analysis_jobs0。實際沿formal holder的Oct8官方raw cache（原取得epoch1791571868.112563）核對錨點，沒有拿研究Oct9時間覆蓋它。職缺source event **430590**／success／count9／canonical fetched_count／cache_hitFalse、fetch ID `5b20cd58e01b4d5889d3407009b1f77e`；後續merge **430602**是excluded aggregate，不另增成功。這個legacy provider沒有明示HTTP-request旗標，因此只宣稱一次來源取得觀測，不猜HTTP次數。初始驗證腳本誤套新segment來源的一筆HTTP收據假設，已以原classifier與snapshot／ledger唯讀核對修正，保存初始錯誤且**沒有重做refresh**。data trust仍partial56，needs_rerun／analysis_text_stale1；未宣稱報告正文或品質警示已改善。[formal proof](evidence/source-acquisition/20261010/seetel-name-formal-report-refresh-proof.json)、[linked events](evidence/source-acquisition/20261010/seetel-name-formal-report-linked-events.json)。
- **06:52:37台灣時間**正式原二十類近24h仍 **15／20嚴格>80%**：職缺28/37=75.676%、法說86/114=75.439%、財報29/57=50.877%、同業25/32=78.125%、近期事件123/155=79.355%。一次修正恢復7740真正缺口，不能代表歷史／其他雇主缺口都修好；較早06:23 snapshot的比例差異含既有觀測自然離窗。原分類／分母／歷史／公式／品質門檻保持，goal仍active；下一輪持續最低財報及上述剩餘真正來源缺口。[completion check](evidence/source-acquisition/20261010/seetel-name-completion-check.json)。

### 新財報索引實測與剩餘來源缺口覆核（2026-10-10）

- 前輪7740的0→9正式職缺修復屬真進展，本輪先重讀canonical近24h帳本；財報29 fetched／17 failed／11 degraded。仍集中9103／7740不足五年合併索引，3023／2206／1325缺2021明示無形資產購置、6672缺2022同欄及完整重編比較，沒有把歷史失敗重標成功。[new financial gap audit](evidence/source-acquisition/20261010/financial-new-entry-gap-audit.json)。研究初稱1325為全宇是口頭公司名稱錯誤；當期TWSE完整名冊核對為恒大股份有限公司／簡稱恆大／www.uk.com.tw，已更正，未將另一家公司資料送進snapshot。
- 新找到 [Treelazy信邦](https://treelazy.com/stock-en/tw/3023)、[熙特爾](https://treelazy.com/stock-en/tw/7740)、[騰輝](https://treelazy.com/stock-en/tw/6672)免費索引。普通匿名TLS原件全部HTTP200，0.908／0.690／0.748秒；完整bytes／hash封存並讀回一致。原件含年度／季度數值表與第一方證交所文件連結，但本次三頁的年報PDF href都只列2024、2025年，並非五年財報原件。現金流數值表是營業／投資／籌資等總額，不含所需明示gross無形資產購置；不拿投資淨額補FCF，也不把四捨五入至十億的圖表數字還原成精確原始TWD值。僅是發現候選，未下載連結文件、未接provider、未宣稱這個索引涵蓋公司所有歷年財報。
- [愛玩股信邦現金流](https://www.istock.tw/stock/3023/cash-flow)在web索引可看到資料，但正式機器普通匿名TLS直接回HTTP403／Cloudflare challenge，0.519秒，拒絕原件也封存；没有重試或繞過。四個入口的實際研究區間formal SLA新增0，完整五年inputs恢復0。[native proof](evidence/source-acquisition/20261010/new-free-financial-index-native-proof.json)。初版研究link filter只找mopsov，後從同一已下載HTML核對實際doc.twse.com.tw href並保存原filename／年度；沒有多抓頁面或誤稱MOPS沒有文件。
- 同時讀原法說／同業／近期事件gap ledger，再核對目前報告：6672已保存5筆同業、8筆近期資料及2026-08-07 MOPS簡報連結；7740亦有5筆候選、2026-09-10 MOPS簡報連結；9103已保存醫材候選。舊source失敗仍在24h窗口，沒有因此重刷已補齊項目或把簡報連結說成完整逐字稿。這些current資料不證明9103缺少的法說、2021支出或舊primary-provider失敗已修復。[remaining gap audit](evidence/source-acquisition/20261010/remaining-conference-peer-news-new-gap-audit.json)。
- **07:03:38台灣時間**原二十類仍15／20嚴格>80%，五類比例與前節相同；本輪沒有backend修改／service restart／formal report refresh或模型工作，十二個release hash保持、API78820 healthz／readyz200、六queue空、scheduled空。這輪新索引尚未提高取得率，goal未達成；繼續只追真缺口與可核對的免費原件。[completion](evidence/source-acquisition/20261010/new-financial-index-completion-check.json)。

### 完整台塑招募候選調查與台化政府職缺缺口（2026-10-10）

- 台塑新版公開平台按原20筆分頁完整取得15頁、290個唯一XUID，並核對290份明細原件；總數前後290保持，只是多時點取得，不能稱原子歷史快照。初次連線逾時保留為HTTP status0／curl28，停止後另做正常能力查詢才以0.6秒間隔續查未完成項目；原逾時未被覆寫。legacy proof欄位 `http_requests` 實為transport attempts，不能把未收到HTTP回應當已送出的HTTP請求。單一台化38、台塑石化5、南亞102；未找到CO01或單一台塑標籤，不推論別處無職缺。[完整原件](evidence/source-acquisition/20261010/fpg-issuer-discovery-resume-proof.json)、[原逾時](evidence/source-acquisition/20261010/fpg-bounded-issuer-discovery-proof.json)。
- 獨立覆核仍認定CO03／04、CONM及STS=P沒有完整直接雇主／仍開放橋接，不啟用FPG provider或補職缺數。新增公開產品頁／註冊條款／應徵流程皆普通TLS200，舊版含截止日清單404；由應徵頁JS明示的匿名唯讀Q&A取得10項，原回答明示平台整合子公司及事業群，仍未定義P為open或CO的法人映射。公司官網403／security redirect、大學404／connect timeout、政府VAC job HTTP200但空欄並跳首頁的原件都保留，不把web索引內容當native成功。[覆核](evidence/source-acquisition/20261010/fpg-employer-binding-review-proof.json)、[公開條款](evidence/source-acquisition/20261010/fpg-public-identity-terms-research-proof.json)、[Q&A原件](evidence/source-acquisition/20261010/fpg-public-qa-research-proof.json)、[VAC原件](evidence/source-acquisition/20261010/fcfc-vac-government-job-original-proof.json)。
- 從實際報告核對新增真缺口：1326台化與6505台塑化原職缺均0；1303南亞已9筆，不因找到更多集團樣本重刷。6505原existing provider native仍degraded/0、19.906秒。新[台化政府公司入口](https://job.taiwanjobs.gov.tw/Internet/jobwanted/company_desc2.aspx?BRANCH_ID=&EMPLOYER_ID=84773)普通TLS200，完整全名「臺灣化學纖維股份有限公司」／統編58650902與當期TWSE上市法人一致。沿三個原鏈結得到工作14728225／14713667／14713641，雇主ID84773、工作碼與標題吻合，截止2026-12-07／10-31／10-31；三份完整原件200/hash封存後讀回，沒有登入或投遞。[新公司原件](evidence/source-acquisition/20261010/fpg-new-exact-employer-portals-research-proof.json)、[工作原件](evidence/source-acquisition/20261010/fcfc-government-job-details-research-proof.json)。
- 原TWSE「台灣」政府查詢native重現unavailable／2份200回應，政府「臺灣」來源拼法假說取得3筆／6份回應。窄修正只匹配1326.TW、canonical全名、統編58650902，query採政府精確全名且公司頁仍核對UBN；保存canonical公司及每筆來源拼法／policy，saved verifier重驗同tuple與marker，不改global aliases、原company_identity、30日刊登門檻或其他provider。開放職缺沿原current_open契約、保留刊登日未知。另對實際 `/Internet/` 路徑在原host/path/IDs驗證後輸出原verifier要求的canonical URL；重複雇主／工作query值拒絕，避免normalization掩蓋歧義。Red7 failed／12 passed、重複ID追加red2 failed，最終主相關隔離234 passed，runtime／storage／報告刷新47 passed。[scoped patch](evidence/source-acquisition/20261010/fcfc-government-name-scoped.patch)、[implementation](evidence/source-acquisition/20261010/fcfc-government-name-implementation-proof.json)。
- 以完全未改的台化saved report context native實測success／3筆／6.390秒，私有InMemoryCache、formal SLA新增0；最後query單值修正後，用保存6份政府原件重播最終檔案仍3筆、可信計數3、原epoch不變且零新增HTTP。這是正式發布前的驗證，不能冒稱已刷新報告。[原context native](evidence/source-acquisition/20261010/fpg-report-gap-1326-existing-provider-native-proof.json)、[最終原件重播](evidence/source-acquisition/20261010/fcfc-government-final-validation-proof.json)。
- 另找到[台塑石化yes123公司頁](https://www.yes123.com.tw/wk_index/comp_info.asp?p_id=20230417152104_86522210)與其唯一工作原件，皆匿名普通TLS200；工作JSON-LD明示完整hiringOrganization、sameAs、datePosted=2026-10-8及validThrough=2027-10-10。保留為後續候選，尚未完成使用條款、日期語義及formal provider設計，不能把URL末碼當已核對的統編正文，也不能把schema日期推成首次刊登／實際招募截止；本輪未啟用此入口。[工作原件](evidence/source-acquisition/20261010/fpcc-yes123-job-native-research-proof.json)。
- 獨立read-only覆核最終檔案SHA `0c64542c8e8b8559de05ad91f464fda2411aea19a0937ccd0c78c84f872ee4d1`，213 passed且無未解material finding；重讀政府完整公司／三工作原件核對全名、UBN、ID、截止及saved marker。**08:06:32台灣時間**正式服務載入唯一owned來源檔，原12份release hash保持，launcher91015／worker91043／API91046；API原06:51:03後僅owned一檔runtime異動，六queue idle、scheduled空集合保持、Redis BGSAVE成功、healthz／readyz200。[review](evidence/source-acquisition/20261010/fcfc-government-name-review-proof.json)、[release](evidence/source-acquisition/20261010/fcfc-government-name-release-proof.json)。
- 正式台化既有 `1326_TW_v4_report_job_9751daff756d.html` **僅刷新一次**，HTTP200／33.111秒，職缺0→3，saved政府employer拼法／canonical身分／marker／逐筆工作ID與截止日重驗通過，原identity不改。source event430647／success／count3／fetched_count／cache_hitFalse；merge430661／aggregate_count保留但不另算取得成功，fetch ID `e5a06aae2a0a4c04b3079a4397bec0e2`。legacy正式provider未保存這次六份原HTTP bytes、也未明示HTTP-request旗標；本輪研究六份原件有archive且讀回，兩者分開，不把研究hash替代formal本次合成response digest或推算HTTP次數。HTML／Markdown／analysis_evidence及五quality gates保持，四index hash相符，analysis_jobs新增0。資料可信度fresh91，但正文needs_rerun／analysis_text_stale1，不能說報告品質警示全面消失。[formal refresh](evidence/source-acquisition/20261010/fcfc-government-name-formal-report-refresh-proof.json)、[linked events](evidence/source-acquisition/20261010/fcfc-government-name-formal-report-linked-events.json)。
- 完整operation保留31 fetched／1 failed／7 local／19 aggregate／1 fresh cache，未抹去失敗或重標歷史。這一次真正缺口刷新前後，職缺25/34=73.529%→26/35=74.286%、法說80/108→82/110、財報26/54→27/55、同業23/30→24/31、近期事件112/144→116/149。**08:07:48台灣時間**原二十類仍15／20嚴格>80%：職缺74.286%、法說74.545%、財報49.091%、同業77.419%、近期事件77.852%未過。與07:03 snapshot的差異包含舊成功觀測自然離窗，不能假稱整段比例下降是這次修正效果；本次before/after及新增source event另存。[before/after](evidence/source-acquisition/20261010/fcfc-government-name-before-after-acquisition-proof.json)、[completion](evidence/source-acquisition/20261010/fcfc-government-name-completion-check.json)。原分類／窗口／分母／公式／TTL／品質門檻不變；goal仍active。下一輪續查台塑石化新候選的授權、日期與保存契約，以及最低財報缺科目的免費原件，不能重刷已有3筆台化或已9筆南亞來湊取得率。

### 職缺用途／開放邊界與三份新查核原件續查（2026-10-10）

- 前輪1326正式0→3職缺修復屬progress；本輪沿原20類及last_24h核對新基準，仍15類>80%。新的[yes123求職規約](https://www.yes123.com.tw/admin/integrate/memberrights.asp)、[軟體補充條款](https://www.yes123.com.tw/admin/campaign/stickyjob/legal.asp)、[隱私聲明](https://www.yes123.com.tw/admin/integrate/privacy.asp)均匿名200並完整封存。獨立覆核公司／職缺／三份條款HTML原件hash及當期TWSE6505：完整雇主名、官網、公司链接及地址可支援這一筆精確雇主辨識，但10/8是來源更新日，published_date仍未知；schema validThrough沒有正文截止或可驗狀態定義，無FPG XUID／CO04對照。條款含資料庫取得、用途及轉載限制，部分限於會員／分享，不能擴張為所有公開事實一律禁取；目前沒有此股票研究自動取得／原文保存的明確允許。保留候選，不啟用formal provider或重刷6505。[native terms](evidence/source-acquisition/20261010/fpcc-entry-terms-and-fpc-government-research-proof.json)、[獨立判讀](evidence/source-acquisition/20261010/fpcc-yes123-source-boundary-review-proof.json)。
- 新[台塑政府公司舊入口53453](https://job.taiwanjobs.gov.tw/Internet/jobwanted/company_desc2.aspx?BRANCH_ID=&EMPLOYER_ID=53453)native302明示跳首頁；以政府「臺灣塑膠工業股份有限公司」拼法另做有界原查詢，兩份200回應仍無精確公司連結，不把web快取公司頁當native取得或盲目擴張台／臺alias。未證明台塑全公司無職缺。[查詢原件](evidence/source-acquisition/20261010/fpc-government-name-hypothesis-native-proof.json)。
- 由原issuer catalog中的實際href取得兩份**此前未下載的2022合併查核財報原件**：[信邦](https://www.sinbon.com/tw/files/download/acc717a64ffcad8)、[恒大](https://www.uk.com.tw/v_comm/inc/download_file.asp?re_id=2174&fid=40761)，普通TLS200／1.287、0.775秒，完整PDF/hash封存讀回。封面、scope及2021比較欄以實際頁面視覺核對，不把image-only statement pages的空text layer當空財報。信邦p14列2021PPE支出-541,353千TWD與其他無形資產減少+22,673千TWD，仍沒有購置支出；恒大p12–13列2021CFO-4,927千TWD、PPE支出-92,659千TWD，仍缺同科目。兩份不能補成原九科目五年完整inputs、不能補零或用收入/減少冒購置。[新比較原件](evidence/source-acquisition/20261010/next-year-comparative-new-originals-research-proof.json)。
- 新[SGX美德2021完整年報](https://links.sgx.com/FileOpen/Medtecs%20AR%202021.ashx?App=Announcement&FileID=712304)普通匿名200／1.582秒，完整176頁原件封存；沿公開附件直接讀取，未再探401的token API。p91–92為Bermuda母公司及子公司2021／2020合併cashflow，USD千元：2021CFO29,760、PPE购置-14,094、租賃資產購置-2,280，沒有明示無形資產購置；租賃資產不能代該科目，美元不能直接合併既有台幣序列。增加新的交易所原件證據，仍未恢復完整financial contract。[SGX原件](evidence/source-acquisition/20261010/medtecs-sgx-2021-annual-original-research-proof.json)。目前實際失敗仍集中9103官方/FinMind/Yahoo、7740不足五年與3023／6672／1325／2206缺特定科目；不是多下載一份即可消除。[current gaps](evidence/source-acquisition/20261010/comparative-new-entry-current-financial-gaps.json)。
- 新[PhilJobNet母公司名稱職缺原頁](https://philjobnet.gov.ph/job-vacancies/job/textile-technologist-1256823)普通匿名200，正文Employer明示Medtecs International Corporation Limited，沿原鏈結取得[公司2912](https://philjobnet.gov.ph/job-vacancies/company/medtecs-intl-corp-ltd-2912)完整200原件。職缺Posted on2025-08-23，current公司頁明示No job vacancies、沒有工作鏈結；舊detail仍有Apply now，不足以證明still-open或近期刊登，不能補進9103 count。僅已驗這個政府刊登的母公司名稱入口，沒有把其他Medtex／Universal Weavers子公司納入；未登入、送履歷、存取帳戶或推定整個母公司各地職缺總數為零。[job original](evidence/source-acquisition/20261010/philjobnet-medtecs-public-job-research-proof.json)、[company original](evidence/source-acquisition/20261010/philjobnet-medtecs-public-company-research-proof.json)。
- 同時核對剩餘法說例外的現在artifact：6152／3653已保存MOPS日期與簡報連結，2466沒有既有報告；5314已存60頁原PDF/native text，但full graphic coverage未驗、保留partial及無逐字稿，沒有重刷或把native text改稱完整讀圖。9103在web找到的conference link仍是2021資料；沒有用網誌更新日期充法說日期。
- **08:27:33台灣時間**原20類仍15／20嚴格>80%；財報49.091%、職缺74.286%、法說74.545%、同業77.419%、近期事件77.852%。本輪backend/code/env未改、服務未重啟、formal report refresh0、model jobs0、研究未增加formal SLA觀測；13份release hash保持，API91046健康／ready200、六queue queued/started/deferred0、scheduled空、原legacy failed10保持。新原件驗證與排除候選改变下一安全行動，屬研究進展；沒有數值或取得率提升、不能標goal complete。本輪無實作變更，不重跑無關測試，改核完整原件與scope。[research verification](evidence/source-acquisition/20261010/source-entry-boundaries-research-verification.json)、[formal completion audit](evidence/source-acquisition/20261010/source-entry-boundaries-completion-check.json)。後續只追新而可核對的精確法人、有效職缺或缺科目；不重抓同一缺科目原件、舊刊登頁或已補齊報告來冒充進展。


### FinMind 單日新聞查詢修正（2026-10-10）

- 官方 [TaiwanStockNews 說明](https://finmind.github.io/tutor/TaiwanMarket/Others/)明示單次僅回傳指定一天。原 `fetch_finmind_news_catalysts` 使用 30 天前起日、空 `end_date`，不會取得後續 29 天；本機 SDK 1.9.10 又把新聞 timeout 預設為 None，內建多次 transport retry，例外原本吞成空結果。
- 研究先保存完整公開匿名回應：3023 的 2026-09-10 與 2026-10-09 均 HTTP200／0 筆；指定 2026-10-02 則 HTTP200／37 筆且全為 exact stock_id 3023。1326 控制請求舊起日成功 3 筆，但日期全是 2026-09-10。另帶 `end_date` 的範圍請求 HTTP400；這不等於正式程式同樣遭到400。所有研究新增正式 SLA0。[單日證據](evidence/source-acquisition/20261010/finmind-news-single-day-research-proof.json)、[原日期對照](evidence/source-acquisition/20261010/finmind-news-observed-date-control-research-proof.json)。3023 是信邦電子，不是貿聯。
- 新專用 `finmind_news.py`／`finmind_news_transport.py` 使用同一免費公開 API，最多三個近期完成日取樣（前一日、前二日、前八日），有資料即停止。原 30 天內容時間窗不變；明示 bounded_daily_samples，不能宣稱完整時間窗或空結果代表沒有事件。總十秒、單次三秒、零 curl retry／redirect；SDK 不再介入新聞傳輸，不更換 token、UA、TLS 或代理路由。HTTP／JSON 拒絕或逾時停止後續日期，保留原件與冷卻。
- 逐列核對原件中的 exact issuer／query date、必要標題／來源／公開連結；同 URL 去重，最多二十筆。原時間未附 timezone，保留原字串但只使用日期精度，不能補造時區或全文。30分鐘原始回應 cache／5分鐘空回應 cache、120秒失敗重查下限與 endpoint cooldown；暖讀重新核對 archive／hash／URL／時間，不更新觀測 epoch。不把快取算新取得；同步核心保存一份 canonical FinMind source audit，避免通用 scheduling wrapper 重算。
- 公共介面先重現 **1 failed**：僅查舊日期、近期有資料仍空。原 red 測試保存在 `/tmp/stock-agent-finmind-news-original-red-test-20261010.py`；因正式傳輸改為 capped curl，綠測試以相同單日回應取代外部 process seam，不再替代 SDK。相關來源／core／shared cache／correlation／provider ledger／FinMind財報隔離 **230 passed**；另兩項排程測試先指出舊 generic scheduling 假設，更新為 canonical typed-news scheduling。一次測試路徑拼錯造成0 tests，未當成測試通過。
- 本輪原生 exact 3023 測試 **0.691秒／三次HTTP／37原列／20公司合格新聞／17筆未存在原保存資料**。所有原列 row index／hash及完整bytes回讀相符；暖讀0HTTP／同records／原epoch保留。使用隔離 InMemory cache，未修改報告、模型工作或正式SLA。[原生證據](evidence/source-acquisition/20261010/finmind-news-native-recovery-proof.json)。正式重載／報告驗證仍須依最後 review／runtime proof 記錄，不能把此診斷当正式改善。

- 獨立 review 先重現六個失敗反例（投影deadline、warm429原原因、receipt狀態／原bytes類型／size、prompt內部path），修正後又重現deadline覆蓋HTTP429的反例。逐項修復並納入專案測試，最後 **237 passed**；runtime／storage／refresh／新聞／prompt相關 **175 passed**，獨立七反例 **7 passed**、無未解material finding。初始來源／綠測試狀態與最後修復分開保留。兩項 `test_search_catalyst_queries` 斷言與原已部署 quoted-search syntax 不合，以修正前core bytes重播仍2 failed，非本次引入；沒有擴大改搜尋邏輯。原件完整重播是隔離memory／歷史有效cache時點／network-disabled驗證，不是新活網冷抓。[implementation](evidence/source-acquisition/20261010/finmind-news-implementation-proof.json)、[review](evidence/source-acquisition/20261010/finmind-news-review-proof.json)、[final original replay](evidence/source-acquisition/20261010/finmind-news-final-original-replay-proof.json)。
- 五份runtime檔在六queue空閒、scheduled空集合後，先保存Redis BGSAVE、只停止owned launcher／worker並以 `start_mac.command`重載：launcher1003／worker1033／API1037，2026-10-10 08:59:07台灣時間。檔案hash與最後review/replay相同，healthz／readyz200、原queue／scheduled保留；無commit／push或env更動。[release](evidence/source-acquisition/20261010/finmind-news-release-proof.json)。
- 正式一次 existing 3023 report 資料刷新 **HTTP200／45.501秒**，FinMind來源 **0→20筆**（三次HTTP／760ms），snapshot保存 **19筆**，逐列stock/date/原row hash及完整bytes可核對。原HTML／Markdown／analysis_evidence／五份品質metadata不變，四份index hash一致，analysis_jobs新增0。data trust仍partial，舊正文 `analysis_text_stale=1`／需重跑；不宣稱新完整報告或品質gate已通過。[formal refresh](evidence/source-acquisition/20261010/finmind-news-formal-report-refresh-proof.json)、[linked events](evidence/source-acquisition/20261010/finmind-news-formal-report-linked-events.json)。
- **09:01:32台灣時間**原近24h二十類仍 **15/20嚴格>80%**：職缺27/36=75%、法說84/112=75%、財報27/57=47.368%、同業24/31=77.419%、近期事件119/155=76.774%。FinMind這次已恢復，但近期事件整類116/149→119/155，因同次三個其他來源失敗如實保留而下降；財報亦保留官方2021缺欄及Yahoo四年partial。不能把單一provider修復冒稱整類改善或已達20類目標。[before/after](evidence/source-acquisition/20261010/finmind-news-before-after-acquisition-proof.json)、[formal completion](evidence/source-acquisition/20261010/finmind-news-completion-check.json)。目前source goal仍active。


### 公司名錄完整原件共用與混合快取計數（2026-10-10）

- 原保存3023報告的 Verified issuer news 在唯一公司名錄請求逾時5006ms，原官網全文0筆；尚未讀信邦索引或文章。正式 shared roster 已有完整1095列／1,327,573bytes，原取得epoch1791571868.112563，hash與archive重讀一致。新唯讀helper核對既有完整bytes、全名單、原網址與原24h期限；不重建欄位為原件、不續期、不清除失敗或冷卻。新鮮有效的較新專用完整raw優先，仍沿原公司全名／英文／官網及十四天出表日門檻。
- 原生隔離測試取得信邦2026-10-06公告全文 **1筆／0.946秒**，名錄 **0HTTP**、索引及文章 **2HTTP**；全部原件完整封存／readback，公開公司selector合格、原記錄重驗通過。暖讀0HTTP、同內容及原epoch，研究新增formal SLA0。它是公司聲明原文樣本，不是整個三十天完整新聞或已驗事件影響。[native proof](evidence/source-acquisition/20261010/issuer-roster-native-proof.json)。
- 另重現 FinMind「新HTTP日期均空，唯一非空結果仍為有效cache」被重算新取得的 **1 failed**；改保留原件、內容、HTTP與原epoch，明示partial/degraded，不升格fetched_count。舊公式／歷史不改。名錄公共介面原red1 failed；獨立覆核較新損壞原件優先權3個失敗反例，修復後23專案＋3獨立通過；最後合併本次來源、runtime、refresh、snapshot及ledger隔離 **246 passed**。正式重載及一次真正缺口刷新結果另見release/formal proof，不把native成功當正式驗收。

- 獨立覆核另重現「expired空快取保留後真正HTTP429」被歸empty_cache_count的P2；專案先重播1 failed／3 passed，再將aggregate cache_hit限於本次零HTTP，component原cache／429／epoch不改。最後 **250 passed**、獨立相關35＋四模式4 passed，無未解material finding。[implementation](evidence/source-acquisition/20261010/issuer-roster-implementation-proof.json)、[review](evidence/source-acquisition/20261010/issuer-roster-review-proof.json)。
- **09:37:08台灣時間**正式API7212已載入最後三檔，launcher7181／role-all worker7210；相對原API只owned三檔有異動、其餘15份runtime SHA保留。先保存Redis BGSAVE，空閒六queue與scheduled空集合保持；healthz／readyz200，原legacy failed10保持，沒有env／model route／commit／push變更。[release](evidence/source-acquisition/20261010/issuer-roster-release-proof.json)。
- 只刷新一次原缺官網全文的3023既有report，**HTTP200／30.064秒**；Verified issuer news **0→1篇正文**，來源 **804ms／2HTTP**（索引及文章）、名錄 **0HTTP**，仍用原epoch1791571868.112563。完整名錄、索引與文章hash／原文字／公司及日期核對通過；source event430763為canonical fetched_count，fetch ID6eccac13f547411992cdf18f5f1d2a7b。HTML／Markdown／analysis_evidence／五quality metadata保持，四index hash一致，analysis_jobs新增0。data trust仍partial、analysis_text_stale1、需重跑；沒有稱報告正文已重生或品質全部改善。[formal proof](evidence/source-acquisition/20261010/issuer-roster-formal-report-refresh-proof.json)、[linked events](evidence/source-acquisition/20261010/issuer-roster-formal-report-linked-events.json)。
- 同次其他真實來源仍有三個失敗（官方2021財報缺欄、公司公告歷史、注意交易公告）；FinMind本次三個指定日實際重新HTTP、20合格metadata，new_record_count20／cached0。混合快取及429反例修復由隔離測試驗證，本次活網沒有刻意制造429或二次重刷。研究仍formal SLA0，原失敗未重標。[before/after acquisition](evidence/source-acquisition/20261010/issuer-roster-before-after-acquisition-proof.json)。
- **09:38:27台灣時間**原20類last_24h仍 **15/20嚴格>80%**：職缺28/37=75.676%、法說86/114=75.439%、財報27/59=45.763%、同業25/32=78.125%、近期事件123/161=76.398%。近期事件原119/155→123/161，四次真取得與兩次失敗都保留，整類比率沒有提高。公式／窗口／分母／分類／歷史／品質門檻保持；goal仍active，不能重刷本次已補齊的全文或原已有職缺來湊比例。[completion](evidence/source-acquisition/20261010/issuer-roster-completion-check.json)。下一輪追原五類仍缺的可驗免費原件，不重抓已排除的同科目PDF、子公司或舊職缺。

### 精誠同業完整原件與新職缺入口（2026-10-10）

- 從台塑官網目前清單，以普通「了解職務」連結找到一個新的[獨立職缺詳頁](https://cloud.fpcetg.com.tw/FPC/WEB/OM/Recruit/Detail.aspx?id=f967413e-e248-447d-bbb0-ec402786e228)。匿名 HTTP200／0.396秒，完整74,737 bytes可回讀；「大專儲備人員」宣告需求20人，但只有一個工作ID，不能算20個職缺。尚無可驗首次刊登日、截止日及目前開放狀態；「我要應徵」指向登入，不當成開放證據，也未登入或送出履歷。HTML含隱藏成功訊息模板，不能當實際交易結果。入口保留研究狀態，formal SLA新增0。[原件與限制](evidence/source-acquisition/20261010/fpc-unique-job-detail-new-original-research-proof.json)。
- 另以已修正的 FinMind 單日查詢檢查9103原新聞缺口：2026-10-09／10-08／10-02三份完整匿名回應均空，合計0.633秒；暖讀0HTTP、原epoch保持。只證明這三個樣本日未取得新聞，未推論三十天沒有事件，也未再次刷新正式報告。初始研究cooldown查詢用了host而非canonical endpoint key；事後唯讀確認正確key當時無guard row，保留錯誤及修正說明，沒有重送供應商請求。[研究證據](evidence/source-acquisition/20261010/finmind-news-9103-fixed-date-native-proof.json)。
- 精誠6214既有報告的公開同業候選原為0筆，前次Yahoo取得紀錄為single_flight_busy。這次原生公共介面取得5筆可核對產業候選，0.607秒／兩次HTTP（完整匿名4,333列主檔及Yahoo排行）；暖讀0HTTP／內容及epoch不變。主檔最新有效日期由完整原件重讀確認為2026-10-10，原lexical max錯誤「None」及修正保留。候選仍是產業發現線索，業務與數值可比性均False。[原生證據](evidence/source-acquisition/20261010/systex-published-peer-native-proof.json)。
- `yahoo_peer_ranking.py` 在原解析成功後封存完整decoded HTTP response body，並由`enrichment_search_providers.py`將原URL／HTTP200／取得epoch／hash／byte count及archive收據留在source audit。這是解碼後完整body，沒有稱為壓縮wire bytes。暖讀重新讀原件、驗URL／hash／size／原四小時期限及當期主檔，再重播比對所有候選；損壞收據不能作成功快取。既有無收據cache保留原契約、不假補原件；原產業、日期、身分、比較門檻及TTL不變。[實作](evidence/source-acquisition/20261010/systex-peer-implementation-proof.json)。
- 原公共介面先重現完整原件與封存失敗的2個failed；獨立review再指出暖讀缺檔及錯URL，修正前重現2 failed／2 passed，補入專案四模式測試。最後來源／prompt／runtime／refresh／ledger隔離 **115 passed**，獨立相關76＋反例8，共 **84 passed**，無未解material finding。最後完整原件重播使用隔離memory、原取得時點及禁網環境，不當新活網成功。[review](evidence/source-acquisition/20261010/systex-peer-review-proof.json)、[original replay](evidence/source-acquisition/20261010/systex-peer-final-original-replay-proof.json)。
- **10:12:01台灣時間**正式API13298載入最後兩檔，launcher13268／role-all worker13296。其餘17份runtime SHA保持；空閒六queue與scheduled空集合、Redis BGSAVE及healthz／readyz200均核對，沒有env／model route／commit／push更動。[正式重載](evidence/source-acquisition/20261010/systex-peer-release-proof.json)。
- 只刷新一次原缺同業候選的6214既有report：**HTTP200／39.116秒**，Yahoo source **642ms／0→5筆**；完整367,715 bytes body保存並與候選逐筆重播相符。五個代號為2468／5203／2480／2427／2471；2026-10-10是Yahoo頁面的觀測日期，不宣稱交易日。source event430835為真正canonical fetched_count，fetch ID3f6192a1e9474151b92836d4ae2e70ee。[正式保存](evidence/source-acquisition/20261010/systex-peer-formal-report-refresh-proof.json)、[事件帳本](evidence/source-acquisition/20261010/systex-peer-formal-report-linked-events.json)。
- HTML／Markdown／analysis_evidence及五quality metadata不變、四index hash一致、analysis_jobs新增0。核心data trust為fresh→fresh，但舊正文analysis_text_stale1／needs_rerun，沒有宣稱正文已重新分析或品質gate新通過。初始驗證器要求整份prompt沒有任何raw_response_path，被原已有九個institutional SDK paths攔下；唯讀比較確認新增Yahoo原件路徑未進實際prompt或候選，原前後九個key不變。保留初始失敗及scope修正，沒有為此再刷新報告或修改其他prompt契約。[範圍核對](evidence/source-acquisition/20261010/systex-peer-scoped-prompt-receipt-proof.json)。
- 同次MOPS法說HTTP502、公告歷史partial及其他來源未取得資料如實保留。**10:16:38**原20類仍 **15/20嚴格>80%**；同業25/32→26/33（78.788%）有真取得改善，尚未達標。職缺29/38=76.316%、法說87/118=73.729%、財報28/60=46.667%、近期事件125/166=75.301%。原窗口、分母、分類、歷史與品質門檻保持，研究沒有加入formal SLA。[前後對照](evidence/source-acquisition/20261010/systex-peer-before-after-acquisition-proof.json)、[驗收](evidence/source-acquisition/20261010/systex-peer-completion-check.json)。**10:25:20**最後唯讀核對以上比例、API13298、所有owned／preserved hashes及healthz／readyz200仍相同，provider／報告新增mutation0。[最後讀回](evidence/source-acquisition/20261010/systex-peer-final-readback-check.json)。Goal仍active，後續只追仍有真缺口的免費原件，不重刷已補齊資料湊比例。

### 三陽完整比較財報與雲林政府徵才新入口（2026-10-10）

- 上輪分類為progress：精誠正式同業0→5與兩檔已驗修正。本輪先追最低的財報取得率，從三陽官網實際2022索引的第四季合併連結取得新的[2022年度及2021比較完整PDF](https://www.sanyang.com.tw/financial/system/investor/financialreport/2022/111Q4.pdf)，不是猜檔名。匿名HTTP200／1.950秒、6,263,827 bytes／93頁，完整archive/hash/readback相符；原文字81頁，兩頁現金流量表為影像，另render並逐頁核對PDF12／13頁（印刷頁8／8-1）。原件明列新臺幣千元、合併範圍、2021 CFO1,444,612／PPE購置-1,259,712、2022 CFO2,033,829／PPE購置-2,278,212，但兩年均未列無形資產購置現金流。無形資產成本／企業合併附註不替代該現金流科目；未補零或升格完整五年。[索引原件](evidence/source-acquisition/20261010/sanyang-2022-official-financial-index-research-proof.json)、[財報原件與視讀結論](evidence/source-acquisition/20261010/sanyang-2022-consolidated-new-original-research-proof.json)。
- 嘗試既有公開MOPS router已列的法說模組`/mops/assets/t100sb02_1.js`，實際HTTP200 body為800 bytes安全拒絕HTML，不是JavaScript或API schema。完整拒絕原件保存，沒有因HTTP200稱取得成功，也未在拒絕後重送或試其他路徑。[拒絕證據](evidence/source-acquisition/20261010/mops-new-conference-front-module-research-proof.json)。
- 新免費政府入口由雲林縣府新聞原連結找到[雲林就業徵才網](https://work.yunlin.gov.tw/)。匿名native首頁HTTP200／0.181秒、完整42,437 bytes；[全部廠商](https://work.yunlin.gov.tw/companylist.asp?tag=0)0.157秒／77,104 bytes、[全部職缺](https://work.yunlin.gov.tw/joblist.asp)0.164秒／37,171 bytes，三份原件均封存回讀。廠商頁當次有43個公司連結，未找到可驗台塑本體／麥寮分公司；職缺首頁10列，顯示1490總數不是逐筆確認數，且可見表格無首次刊登日與應徵截止欄位。沒有登入、送履歷或使用應徵function；入口暫留研究。[首頁](evidence/source-acquisition/20261010/yunlin-work-new-entrance-native-research-proof.json)、[公開清單原件](evidence/source-acquisition/20261010/yunlin-work-public-listing-new-original-research-proof.json)。
- 沿實際joblist公開表單POST`kw=台塑,tag=`，HTTP200／0.142秒，回「此分類暫無職缺」；只證明此關鍵字查詢空，不推論台塑全公司沒有職缺。舊748job索引只作尋找官方入口的線索，未作身分／日期／開放狀態證據；其他集團公司及過期職缺不納入。現有22個政府分區CSV共用cache均無可用的fresh payload（該cache原本為正規化列與hash，未視為完整原件），未重新下載全分區來湊取得率。[查詢原件](evidence/source-acquisition/20261010/yunlin-work-fpc-keyword-research-proof.json)。
- 本輪新原件排除了三陽PDF可補缺欄與雲林入口可直接補台塑的假說，未新增合格財報／職缺、修改runtime或正式刷新報告。正式provider_sla_events最大ID前後均430849、研究SLA新增0；原公式／分類／窗口／分母／歷史／品質門檻保留。[本輪範圍與結果](evidence/source-acquisition/20261010/new-free-financial-government-entrance-round-proof.json)。最後唯讀原20類驗收仍15類嚴格>80%、API13298／runtime hashes與healthz／readyz均核對，goal仍active、未冒稱80%完成。[正式驗收](evidence/source-acquisition/20261010/new-free-financial-government-entrance-completion-check.json)。下一步只追新的、可驗明列現金購置值或精確雇主／日期／開放狀態原件，不重試本輪未變的空／拒絕入口或已補齊報告。

### 精誠新版官網完整法說入口與指定來源刷新（2026-10-10）

- 本輪有實質進展：找到精誠新的完整官方法說資料入口，並修正、重載及實測指定来源刷新；原二十類全數嚴格>80%的goal仍未完成。TWSE OpenAPI完整schema有143個path，但ESG投資人溝通次數不是場次／簡報內容；MYSON同場官方影片的匿名頁面playability OK、caption tracks0，也沒有冒稱取得完整逐字稿。[TWSE目錄](evidence/source-acquisition/20261010/twse-openapi-conference-full-catalog-research-proof.json)、[MYSON字幕可用性](evidence/source-acquisition/20261010/myson-official-video-caption-availability-research-proof.json)。
- 6214原保存快照只有WebPro metadata、MOPS上次HTTP502。原persistent guard已自然到期，一次普通匿名診斷POST取得完整10,849-byte MOPS HTML，HTTP200／0.227秒，純parser核對三個已完成場次，最新2026-09-17。未清除冷卻／歷史、未用研究觀測增加formal SLA。[自然到期診斷](evidence/source-acquisition/20261010/mops-6214-expired-502-native-diagnostic-proof.json)。
- 從新版精誠首頁實際導航「投資人專區→財務業務資訊→法人說明會資訊」，找到[官方法說入口](https://tw.systex.com/systex/ch/app/tabfolder/22344)。完整首頁5,574 bytes與當期main script3,875,062 bytes均保存；第一次script超過本機2MB cap、0body／exit63另存，第二次10MB有界取得完整script HTTP200／1.594秒，不是安全拒絕後繞路。官網公開config的apiUrl與main script的viewTabFolder規格可推導原頁面的[公開JSON endpoint](https://tw.systex.com/api/v2/systex/ch/api/tabfolder/22344)；省略一般頁面參數cspstr回400，完整原件保留。沿匿名HTML由server發布、官網XHR實際使用的參數後，普通GET回200／0.662秒、46,838-byte完整JSON；沒有Authorization／cookie／既有browser credentials、參數值不進proof或模型。JSON含11個年度panel；2026 panel有3個場次，最新日期、元大地點、中文簡報與影音與匿名UI相符。沒有猜URL序列、偽造參數或把400稱成功。[導航及完整原件](evidence/source-acquisition/20261010/systex-issuer-current-navigation-research-proof.json)、[第一次400](evidence/source-acquisition/20261010/systex-current-conference-public-entry-research-proof.json)、[完整公開JSON](evidence/source-acquisition/20261010/systex-current-conference-native-public-xhr-research-proof.json)。
- 實際索引同場[2026-09-17官方中文簡報](https://tw.systex.com/userfiles/systexch/files/1550066653948022784.pdf)一次匿名下載HTTP200／0.828秒、2,733,281 bytes，完整binary與hash保存。pdfinfo確認20頁、封面另render視讀精誠／2026.09.17；文件metadata建立日期不是發布日期。原有隔離PDF parser回parser_warning，沒有忽略警示來宣稱完整內容、完整native text或逐字稿，尚未啟用這個issuer candidate為正式provider。系統未提供pdftotext命令，沒有安裝工具或假造抽頁結果。[完整PDF研究及限制](evidence/source-acquisition/20261010/systex-latest-issuer-presentation-research-proof.json)。研究階段在正式source刷新前新增ledger0；其後的官網原件研究也沒有正式來源事件。
- `POST /api/report/{filename}/refresh/data?source=earnings_call` 經原修改授權，只取得既有免費earnings provider；未指定query仍是原完整刷新。實作在`report_source_refresh.py`及`StockDataService.fetch_source_async`，失敗也經canonical _build_result保存來源觀測、失敗不覆蓋原快照。原價格／財報／其他值與audit保持，原source age／trust重算而不續期；同筆ISO／epoch衝突在任何取得前拒絕，normal workflow freshness晚於provider結束時間則採較早原core時間。[範圍diff](evidence/source-acquisition/20261010/report-source-refresh-scoped.patch)、[實作證據](evidence/source-acquisition/20261010/report-source-refresh-implementation-proof.json)。
- 原公開API缺參數先重現1 failed；review新增失敗漏觀測／舊trust沿用兩反例2 failed，再新增原時間矛盾兩反例2 failed／1 passed。修後相關 **269 passed、1 deselected**，獨立 **29+7=36 passed**，最後四份runtime hash吻合、無未解material finding。唯一deselected為既有`test_persist_report_bundle_rolls_back_saved_content_when_data_save_fails`，已只在memory載入修改前兩個模組重播同樣失敗；原本預期deleted順序沒有含attempted data清理，未改本輪以外persistence或assertion，沒有稱全部測試通過。[獨立review](evidence/source-acquisition/20261010/report-source-refresh-review-proof.json)。
- **11:21:20台灣時間**API25184重載最後四份程式，launcher25154／role-all worker25182；前輪19份runtime及env hashes保持，六queue idle、scheduled空集合、Redis BGSAVE及healthz／readyz200核對。沒有commit／push、金鑰／model routes修改。startup既有daily-dashboard cold read曾503／28.23秒後cache完成，不當成source-refresh效能或全前端健康驗收。[正式重載](evidence/source-acquisition/20261010/report-source-refresh-release-proof.json)。
- 對原有真法說缺口的`6214_TW_v4_report_20261009_123411.html`只執行一次source query，**HTTP200／0.964秒**，補回2026-09-17 MOPS活動說明與中文／英文材料連結；這是索引內容，沒有稱下載MOPS PDF或逐字稿。只送一次上游HTTP，按原公式保存原HTTP及provider結果兩筆fetched_count，不把兩筆稱兩次HTTP／兩份報告；其他來源事件0、model job新增0，原同業5笔保持。HTML／Markdown、analysis_evidence與五quality metadata不變，所有非指定資料值、其他原audit及四index hash一致。source_freshness派生core時間採原audit較早值，原market fields／audit epoch無續期；舊正文仍analysis_text_stale1／needs_rerun。[正式刷新](evidence/source-acquisition/20261010/report-source-refresh-formal-gap-proof.json)、[真實事件](evidence/source-acquisition/20261010/report-source-refresh-formal-linked-events.json)、[最後讀回](evidence/source-acquisition/20261010/report-source-refresh-final-readback-proof.json)。0.964秒的scope只有法說，前輪39.116秒包含全來源，兩者不是相同工作量的benchmark。
- **11:24:04**原20類仍 **15/20嚴格>80%**。法說87/118=73.729%→89/120=74.167%；職缺29/38=76.316%、財報28/60=46.667%、同業26/33=78.788%、近期事件125/166=75.301%仍未達標。原窗口／分類／分母／歷史及品質門檻保持；新官網入口尚為研究candidate，沒有加入formal成功。後續優先處理新官方PDF的具體parser_warning及public JSON selector／原件保存，只有新修正後的真內容缺口才驗證，不重刷已取得場次來湊比率。[原驗收](evidence/source-acquisition/20261010/report-source-refresh-completion-check.json)。


### 精誠免費法說備援與 PDF 字型解碼修復（2026-10-10）

- 先保留上一節的 `parser_warning` 原失敗，重播原完整 20 頁 PDF 後定位為 pypdf 缺少 CFF Type1 字型解碼依賴，沒有忽略 parser 警示。官方 PyPI 的 fonttools 4.66.1 wheel 經完整 hash 核對，在隔離 target 先安裝／回歸，再以 `--no-index --no-deps --require-hashes` 加入正式 `.venv`；原 157 個 package 版本不變，僅新增 fonttools，requirements 與 lock 同步保留固定版本及 wheel hash。獨立覆核 32 passed，正式 affected 97 passed；正式 PDF 子程序無測試 override 提取 20 個非空頁，0.236 秒，仍有第 6、19 頁亂碼，coverage=partial。沒有把缺字頁稱完整、取得逐字稿或新增報告模型工作。[原警示](evidence/source-acquisition/20261010/systex-20260917-pdf-parser-warning-diagnostic-proof.json)、[依賴覆核](evidence/source-acquisition/20261010/fonttools-pdf-dependency-review-proof.json)、[正式提取](evidence/source-acquisition/20261010/fonttools-pdf-dependency-formal-runtime-proof.json)。
- 新 `systex_conference_index.py`／`systex_conference_transport.py` 只支援 6214／6214.TW，固定精誠 HTTPS 匿名首頁與原公開 JSON endpoint；沿普通 HTML 的 server-issued `cspstr` 查詢參數，無 cookie／Authorization／重導／重試。只在原 MOPS 暫時性 server/transport/timeout/rate-limit/cooldown 失敗後加入，健康 MOPS、其他公司及原 WebPro 最後備援保持。兩份完整回應按 hash 封存；日期、場次描述與同場簡報／影音連結可核對，但 provider 不下載文件、coverage 明示 metadata_only，不當作營運展望全文。
- 一次 private-memory native 操作兩次 HTTP、共 0.758 秒，完整首頁 5,574 bytes／JSON 46,838 bytes，最新已發生場次 2026-09-17 14:00；暖讀零 HTTP、原 epoch 保持。這是研究成功，formal SLA 新增 0。bootstrap 不獨立算一份法說資料；原 classifier 核對一個 logical fetched_count，provider 彙總沿既有 optional 外部來源規則排除，不改二十類／分母／歷史。公開查詢參數值及新內部封存路徑沒有進入實際 prompt。[完整 native 原件研究](evidence/source-acquisition/20261010/systex-conference-index-native-research-proof.json)。
- 獨立 review 重現六個反例：暖收據的 archived／完整原件類型／bytes 不符仍放行、極大 epoch 中斷 WebPro、collector 與原件回讀漏掉期限。修正後要求嚴格正整數大小／上限／實際完整 body 一致，先限界數值再檢查 finite，異常保持 typed failure；單次 transfer deadline 最多 5 秒，整次 cold/warm context 共用 12 秒，原件回讀及解析後再次核對，遲到結果不能發布。磁碟 read 不宣稱可在作業系統層強制取消。Persistent 加原 probes 共 30 passed，相關來源／刷新／財報／PDF／runtime-storage 回歸 266 passed。[scoped patch](evidence/source-acquisition/20261010/systex-conference-index-scoped.patch)、[實作證據](evidence/source-acquisition/20261010/systex-conference-index-implementation-proof.json)。
- 最後修正後只用已保存的完整 native 原件與原取得時間，重建 private cache 再回讀；沒有再抓官網、沒有 restamp、沒有正式 cache 或 provider ledger 寫入。前一個 native proof 的 code hash 屬修正前實測，另留最後修正的原件 replay proof，不混成新的 live 成功。[最後原件重播](evidence/source-acquisition/20261010/systex-conference-index-repaired-original-replay-proof.json)。6214 的正式 MOPS 真缺口前輪已補齊，本輪不重刷該報告湊比例。
- 三組 P2 的獨立隔離套件 84 passed，原六反例 6 passed、無未解 material finding；初次正式重載於12:19:52完成，proof與已覆核原 code另存，未把研究當正式取得。[第一次覆核](evidence/source-acquisition/20261010/systex-conference-index-review-proof.json)、[第一次正式重載](evidence/source-acquisition/20261010/systex-conference-index-initial-release-proof.json)。最後檢查另重現非dict的cached diagnostic中斷WebPro：四型別測試修正前3 failed／1 passed，先核對mapping再賦值後，最後related **270 passed**；增量獨立62 passed＋7額外反例、無未解material finding。[增量覆核](evidence/source-acquisition/20261010/systex-conference-index-diagnostic-review-proof.json)。最後原件暖讀用同一原取得時間與新hash，不新增HTTP或正式觀測。[最後版本原件讀回](evidence/source-acquisition/20261010/systex-conference-index-final-original-replay-proof.json)。
- **12:24:06台灣時間**最後增量已由正式 `start_mac.command` 載入，launcher39591／role-all worker39620／API39627；只重載index一檔、其他25份runtime hash保持（含首次已載入的另外兩個新來源檔）。兩次空閒重載都核對六queue與scheduled原樣、Redis BGSAVE成功、healthz／readyz200；158個已安裝版本在重載後完全保持，啟動以PIP_NO_INDEX防止另行升級，`.env`原hash保持。未commit／push、未改模型路由、未重刷已補齊6214。[最後正式重載](evidence/source-acquisition/20261010/systex-conference-index-release-proof.json)。
- **12:24:31台灣時間**原二十類近24h仍 **15／20嚴格>80%**：職缺28/37=75.676%、法說87/118=73.729%、財報27/59=45.763%、同業25/32=78.125%、近期事件121/162=74.691%。ledger始終430851、analysis_jobs始終1134，本輪沒有正式來源、報告刷新或模型工作；與前輪較早snapshot的比例變化是既有觀測自然離開24h窗口，沒有回補或刪除紀錄。精誠備援已部署，正式實際fallthrough尚待自然失敗觸發；隔離MOPS502重播及native研究不冒稱新的正式報告成功。Goal仍active，後續以財報原件缺口及其他真正未補齊來源為優先。[最後原口徑驗收](evidence/source-acquisition/20261010/systex-conference-index-completion-check.json)。


### 新公開說明書完整原件與年度缺口核對（2026-10-10）

- 上輪為progress：精誠備援與fonttools已部署。本輪重讀26個reviewed runtime hash、canonical20類與原財報失敗；官方合格五年資料原本已先於Yahoo/FinMind返回，沒有重做已存在的official-first優化。從[永豐參與承銷案件](https://www.sinotrade.com.tw/Underwriter/Underwriter_2)實際熙特爾、騰輝列連到TWSE電子文件索引。三份匿名native HTML均200，完整bytes／hash封存讀回；交易所原件明示Big5且native正確解析，web工具7740頁的Unicode error不當作來源失效。[完整索引](evidence/source-acquisition/20261010/new-prospectus-index-native-proof.json)。
- 沿原頁`readfile2`及POST form的既有`step=9/kind=B/co_id/filename`唯讀文件下載流程，取得server當次返回的兩個PDF链接，沒有猜動態檔名、登入或改源。完整原件熙特爾**7,838,372bytes／1.804秒／792頁**、騰輝**18,799,371bytes／7.719秒／600頁**均HTTP200、整檔SHA与disk重新讀回一致；熙特爾沿原8MiB archive封存，騰輝超出原archive上限，只保存研究整檔與完整hash，不調高production archive cap或冒稱canonical封存。[原下載form](evidence/source-acquisition/20261010/new-prospectus-public-download-form-proof.json)、[完整PDF](evidence/source-acquisition/20261010/new-prospectus-complete-pdf-native-proof.json)。動態URL的時間是當次server下載檔名，不能當作文件首次發布日。
- 正式PDF reader原100頁／16MiB限制保持，分別拒收page_limit／invalid_input，不稱provider取得成功。研究另外用正式已安裝pypdf，在25秒／512MiB父程序限制內逐頁找財報：792／600頁文本scan各9.66／10.00秒、峰值約99／244MB、parser warning0；這是人工查找頁次，非production acceptance、OCR、完整讀圖或逐字稿。現有Swift compiler與選定SDK版本不合，只保留診斷，未改toolchain；頁面render用已有bundled pdftoppm。[有界研究頁次](evidence/source-acquisition/20261010/new-prospectus-research-page-inspection-proof.json)。
- 騰輝新原件實際PDF238／239頁（原財報11／12頁）完整視讀同一2023／2022合併現金流，TWD千元：CFO743,024／1,465,504，PPE購置-82,785／-85,429，沒有明列無形資產購置。不能由欄位不存在推0，亦未補成原九科目五年inputs。熙特爾native可核對的資料包括2024／2023合併、同年度個體與2025Q1／2024Q1合併，沒有因此宣稱有2021合併資料。已有early-scope proof保持，不混報表範圍。[原件驗證與欄位結論](evidence/source-acquisition/20261010/new-prospectus-final-raw-verification-and-completion-check.json)。因此不為這兩個仍缺事實的candidate放寬PDF limits或financial gate。
- **12:48:22台灣時間**原20類近24h為**16／20嚴格>80%**，同業舊觀測自然離窗後跨線，不能歸功本輪研究。剩職缺25/34=73.529%、法說81/112=72.321%、財報24/56=42.857%、近期事件111/150=74%。formal ledger仍430851、jobs仍1134，研究7次native HTTP未加入SLA；runtime26檔、env、API39627及healthz／readyz200保持，無backend修改／restart／正式報告刷新。Goal未達；接續其他真正未填的免費來源缺口。[原口徑驗收](evidence/source-acquisition/20261010/new-prospectus-final-raw-verification-and-completion-check.json)。


### 台塑新政府入口與郵遞區號樣本排除（2026-10-10）

- 新找[台塑舊政府公司入口](https://job.taiwanjobs.gov.tw/Internet/jobwanted/company_desc2.aspx?BRANCH_ID=&EMPLOYER_ID=53453)，web索引仍有「臺灣塑膠工業股份有限公司」／統編75708007；native普通TLS現在302／143bytes，未取得公司原件或職缺，沒有為搜尋索引資料放行。這次首次302僅保存transport metadata，沒有完整失敗body archive，故不稱完整原件已封存。[native現況](evidence/source-acquisition/20261010/fpc-government-exact-parent-new-entry-native-proof.json)。
- 沿[官方介接說明](https://free.taiwanjobs.gov.tw/webservice_taipei/A17000000J-030144-Taiwanjobs-OpenData.pdf)已有ZIPNO／COUNT／CSV規格，對原官方地址所在地麥寮637、仁武814各做一次有界匿名查詢；完整CSV各HTTP200／27,643與132,549bytes／0.325與0.725秒，19欄company欄位存在、38與192列、皆未碰1,000 cap，但只涵蓋這兩個postal query，不是全站或所有issuer據點完整覆蓋。兩份當次樣本無台塑／塑膠工業名稱候選，不推論台塑沒有職缺，不用南亞／台化／子公司補1301。[麥寮](evidence/source-acquisition/20261010/fpc-mailiao-postal-job-list-research-proof.json)、[仁武](evidence/source-acquisition/20261010/fpc-renwu-postal-job-list-research-proof.json)。
- 新[經濟部統編查分公司資料](https://data.gov.tw/dataset/84877)提供總公司／分公司統編及status欄位，可用作後續同法人證據候選，但公開JSON catalog的native HTTPS現回504／0bytes，立即停止，沒有再探其他API路徑或假借第三方推定關係。這是GCIS資料入口504，不是模型504；不啟用automatic branch binding、不擴alias。[native catalog診斷](evidence/source-acquisition/20261010/gcis-branch-new-public-catalog-native-proof.json)。
- 本輪總11次native研究HTTP、正式provider ledger／analysis_jobs／report刷新新增0，原26份reviewed runtime hash保持；沒有因negative研究新增backend修改或更改原quality門檻。最後canonical20類／原24h驗收仍未全部>80%，目前跨線含原觀測自然離窗；目標維持原範圍且active。[最後總核對](evidence/source-acquisition/20261010/new-free-prospectus-and-fpc-final-completion-proof.json)。


### 信邦完整投資人公告與騰輝有日期轉載入口（2026-10-10）

- 本輪轉查近期事件真正缺口，原 canonical 帳本的 TWSE history 空結果不等於傳輸錯誤；3023 最近索引公告為2026-09-09。另用官方月份查詢分別核對9月10–30日與10月1–10日，兩個完整 HTTP200 回應都是 application code406「查無相符資料」，沒有把成功連線當成近期事件成功，也沒有重試原空窗口或改寫舊事件。[原始分流稽核](evidence/source-acquisition/20261010/recent-events-current-failure-routing-audit.json)、[月別查詢判讀](evidence/source-acquisition/20261010/sinbon-mops-monthly-crosscheck-interpretation.json)。研究腳本在證據保存後的summary列印誤對null result呼叫get，原錯誤保留，後續只讀既有原件修正判讀，沒有重做HTTP。
- 新找到[信邦投資人新聞](https://www.sinbon.com/investors-news/1)。沿已保存官方app.js真正的`invnews/items`路由與公開頁BASE_URI，取得[匿名公開API](https://www.sinbon.com/api/invnews/items) **HTTP200／521,639bytes／1.147秒／192列**完整回應；bootstrap HTML另200／16,985bytes。最新列id198，標題為2026年9月未查核營收，內文明示SINBON/TWSE3023，但原`publish_on`只有 **2026/10**。完整回應含192列不代表已驗證官網所有歷史公告覆蓋；沒有推定確切日、使用營收月份代發表月份，或把API列數當來源成功率。原精確day門檻保持，月份精度的使用選擇已問使用者、目前待答，尚未接入正式provider。[完整原件收據](evidence/source-acquisition/20261010/sinbon-investor-news-public-api-native-proof.json)。
- 新[騰輝官網新聞入口](https://www.ventec-group.com/cht/news/)普通匿名GET **200／54,750bytes／1.585秒**，沿原card href取得[9月22日投資文章](https://www.ventec-group.com/cht/news/ventec-makes-a-decisive-investment-in-speed-capacity-and-capability/) **200／48,223bytes／1.898秒**完整HTML。當期TWSE原始全名／6672／英文Ventec／官方host吻合；只重用原已取得完整主檔及其epoch1791571868.112563，沒有續期或新增主檔HTTP。清單`22.09.2026`與內文`22 九月 2026`一致，主段落13段／4,984字元可讀。原文末明示DigiTimes及原新聞link，因此角色是 **issuer_hosted_press_republication**，此日僅官網轉載日，DigiTimes原始發布日未知。不能把它當公司自行撰寫、獨立第二個publisher，或由原URL日期字串推原發布日。保存完整兩份HTTPbytes及研究用selected body，四份新入口原件均重新解壓核對bytes/hash一致。[完整候選資格與限制](evidence/source-acquisition/20261010/new-free-news-entrances-qualification-proof.json)。此原文是可用研究入口，尚未實作正式adapter；接入時須一併保留兩種日期、原作者歸屬／原URL、轉載去重及typed receipt在selector／prompt的語意。
- 精誠新版官網經實際匿名UI「新聞中心→最新消息／媒體報導」導航，兩個清單最晚發布日期各為 **2026-09-01／2026-03-18**，均不在當日近30天窗口；頁尾115年10月08日只是網站更新日。此查驗是visible browser listing，沒有保存完整HTTP原件，不冒稱native bytes archive或全站歷史覆蓋。也沒有啟用先前401的SGX候選；Medtecs原SGX導讀與舊官網news不提供本輪新的已驗免費匿名自動介接。
- 本輪只有研究／文件，backend修改、restart、正式報告refresh與模型呼叫均0；provider ledger始終430851，analysis_jobs始終1134。**13:27:27台灣時間**最新原20類近24h仍 **16／20嚴格>80%**，職缺25/34=73.529%、法說80/111=72.072%、財報24/56=42.857%、近期事件111/150=74%；原分類／分母／歷史／窗口及quality gates保持。26份reviewed runtime hashes相符、API39627、healthz／readyz200、六queue無執行工作且scheduled原樣空。新入口研究沒有灌入formal SLA，goal仍active且未達。[正式原口徑驗收](evidence/source-acquisition/20261010/new-free-news-entrances-completion-check.json)。


### 騰輝完整轉載正式接入與單來源增量刷新（2026-10-10）

- 上節研究入口已接入正式 `Verified issuer news`：6672沿精確當期TWSE公司身分、固定[官網索引](https://www.ventec-group.com/cht/news/)與逐篇完整原文，最多五篇、原二十秒總期限／單次五秒／三十分鐘快取及persistent cooldown保持。新 `ventec_issuer_news.py` 僅解析已核對區塊及完整原件收據；官網轉載日2026-09-22與未知DigiTimes原發布日分開，全文及摘要明示原媒體／日期限制，同一原URL與DigiTimes publisher去重，不能增加獨立來源數。身分False／空列表及格式化禁止alias也不能繞過typed驗證。來源仍partial／window_complete False／影響未評估；信邦月份資料尚待使用者答覆，SGX原匿名401路由保持停用。
- 新 `POST /api/report/{filename}/refresh/data?source=issuer_news` 沿原修改授權，只呼叫這個component。其他news合併並保留排除原因，價格、財報、社群、同業等值及其他audit保持，原core取得時間不續期；無效原bucket／衝突core時間在provider前拒絕。合格暖快取維持原epoch、cache狀態及零HTTP，不能記為新取得。`enrichment_merge.py` 只在公司／時間／收據均合格的新文章存在時更新news audit；被排除原件不續期舊資料，覆蓋partial仍保留。[實作與最後hash](evidence/source-acquisition/20261010/ventec-issuer-news-implementation-proof.json)、[本輪範圍diff](evidence/source-acquisition/20261010/ventec-issuer-news-scoped.patch)。
- 起始provider／component分別重現8／4 failed，獨立覆核提出身分、alias與publisher去重反例，另修正暖快取與「無合格新文仍更新舊取得時間」問題。最後來源、日期、component、原refresh及runtime／storage隔離測試 **196 passed**；初始與增量獨立覆核均無未解material finding，增量另27相關測試及3保留狀態反例通過。[初始覆核](evidence/source-acquisition/20261010/ventec-issuer-news-initial-review-proof.json)、[增量覆核](evidence/source-acquisition/20261010/ventec-issuer-news-incremental-review-proof.json)。native private adapter取得一篇完整原文，2次HTTP／2.627秒；保存後按同原件、原主檔及原epoch禁網重播相符，研究與暖讀不寫入正式SLA。[native查驗](evidence/source-acquisition/20261010/ventec-issuer-news-native-private-proof.json)、[原件重播](evidence/source-acquisition/20261010/ventec-issuer-news-final-original-replay-proof.json)。native與原件重播證明來源adapter，增量merge由隔離反例與獨立覆核驗證，沒有冒稱所有最後runtime都重做native。
- 原確實缺這篇完整文章的既有6672報告只刷新一次：**HTTP200／3.883秒／一篇5,028字元／全部news 9→10**，原九筆與其他資料、HTML／Markdown、analysis_evidence及五quality metadata保持。四個report index hash與artifact／snapshot一致，只有一筆canonical fetched_count事件430852，analysis_jobs維持1134、模型新增0。[正式單次保存](evidence/source-acquisition/20261010/ventec-issuer-news-formal-component-refresh-proof.json)、[事件帳本](evidence/source-acquisition/20261010/ventec-issuer-news-formal-linked-events.json)。財報缺欄仍存在，原core年齡重新計算後institutional_trading跨新鮮度門檻，data_trust仍partial、score56→50；沒有靠新文章續期其他來源。原正文 `analysis_text_stale=1`／needs_rerun，並未重新分析或新通過品質gate。
- 初次來源九檔已正式載入並完成上述refresh；最後merge一檔再增量重載，另外已載入來源與無關成果保持。正式入口仍 `start_mac.command`、role-all worker、uvicorn API，PIP_NO_INDEX使158個已安裝版本不變；`.env`原hash、原queue／scheduled、Redis BGSAVE均核對。停worker首次20秒bounded wait到期時API未停，稍後唯讀確認worker正常結束後才續作，沒有強制kill。[首次正式重載](evidence/source-acquisition/20261010/ventec-issuer-news-initial-release-proof.json)、[最後正式重載](evidence/source-acquisition/20261010/ventec-issuer-news-release-proof.json)。最後launcher62094／worker62122／API62124，總計30份owned與preserved runtime hash相符、healthz／readyz200；無commit／push、路由或模型設定變更，未再刷新已填補報告。
- **14:10:08台灣時間**按原二十類近24h仍 **16／20嚴格>80%**：職缺24/33=72.727%、法說76/107=71.028%、財報23/55=41.818%、近期事件109/147=74.150%。ledger430852與jobs1134保持，當輪只有上述一次真實來源取得；其餘比例變動來自24h窗口，沒有回補／刪除歷史或算入研究HTTP，原分母、分類、窗口與quality gates保持。Goal仍active／未達全類別80%；後續仍須補財報完整年度欄位、法說與精確雇主職缺等真正缺口。[最後正式驗收](evidence/source-acquisition/20261010/ventec-issuer-news-completion-check.json)。


### 不足五年財報的重複查詢修正與新原件（2026-10-10）

- 上輪為progress：騰輝完整轉載已補入既有報告。本輪重讀canonical帳本與30份runtime hash，剩財報、法說、職缺及近期事件，沒有把已填補報告再刷新。[新缺口基準](evidence/source-acquisition/20261010/free-source-next-gap-baseline-20261010.json)。新查財報狗7740電子書頁，2022／2023「年報電子書」實際是空href，不能把標籤當成完整年報。搜尋找到熙特爾2024股東會手冊含110年度查核報表，但原非www下載回301、當期官網www host同原檔名回404；這兩次只有transport metadata，沒有完整失敗body archive，不冒稱已取得那份2021現金流。[原301](evidence/source-acquisition/20261010/seetel-2021-meeting-new-original-native-proof.json)、[當期host404](evidence/source-acquisition/20261010/seetel-2021-meeting-canonical-host-native-proof.json)。
- 改沿前輪已完整取得的交易所索引，選另一份**此前未下載、索引標示生效、2024-11-07上傳**的`202411_7740_B06.pdf`。原readfile2／step9 form回HTTP200，再沿server當次發布下載連結取得 **10,100,597bytes／290頁／5.702秒**完整PDF，binary及讀回SHA一致。大於原8MiB archive且超過正式100頁限制，僅保存完整研究原件、保留page_limit拒收，沒有提高正式限制或接成成功provider。[原form與下載](evidence/source-acquisition/20261010/seetel-2024-earlier-prospectus-public-form-proof.json)、[完整PDF](evidence/source-acquisition/20261010/seetel-2024-earlier-prospectus-complete-pdf-native-proof.json)。有界25秒／512MiB研究逐頁scan約4.15秒、峰值約84MB、warning0；選定相關頁另render完整視讀，不稱290頁完整圖像覆蓋。
- 新原件PDF58–59頁（印刷51–52）明示 **2023首次編列合併財報、2022比較數字，2019–2021合併摘要不適用**；PDF60–62另區分自2022採用IFRS的2021個體比較與原企業會計準則個體資料。PDF91–92合併現金流只有2023／2022，CFO -15,035／80,502、PPE現金支出-60,167／-45,581仟TWD，無2021欄；不能混個體／合併補五年，或由資產負債表無形資產符號推出購置現金流。這份特定原件把「年度／範圍本來不同」與傳輸錯誤分開，不推論日後永遠不會有其他重編原件。[年限／範圍核對](evidence/source-acquisition/20261010/seetel-earlier-prospectus-financial-availability-qualification-proof.json)。
- 一次普通native MOPS 7740索引 **HTTP200／7,587bytes／0.123秒**，完整原件封存讀回，只列2023／2024／2025三份Q4合併文件；2022比較期間不能當成第四份索引文件。原記錄的persistent供應商guard檢查未見active row，沒有清除保護。[當期完整索引](evidence/source-acquisition/20261010/seetel-current-short-annual-index-native-proof.json)。現有300秒缺口快取只接受五份已驗原件的缺科目案例，因此short index每次仍做真查詢。新增 `annual_filing_index_gap.py`，僅完整非空的固定MOPS表格、原申報scope、年度／季度／issuer／查詢與下載兩種連結一致、原bytes／hash及1–4個連續Q4年份全部通過時，才重用原不足五年失敗。空／security／截斷／未驗字串及矛盾收據不能抑制下一次取得；未知表格保持原失敗路徑，300秒、transport／quota及五年科目要求不變。年份欄位是索引文件年，不代表已驗證的所有比較財務期間。
- 原完整fixture重播先 **1 failed／9 passed** 證明重複POST；新收據audit年份、coverage與空query反例再 **3 failed／13 passed**，均修正。最後分兩批16個來源／財報備援／runtime／storage套件 **132＋202＝334 passed**；獨立 **71相關＋7額外反例**，無未解material finding。[範圍diff](evidence/source-acquisition/20261010/short-annual-gap-scoped.patch)、[實作](evidence/source-acquisition/20261010/short-annual-gap-implementation-proof.json)、[獨立覆核](evidence/source-acquisition/20261010/short-annual-gap-review-proof.json)。最後原件禁網重播使用同一完整body及原epoch、隔離memory，first failed_count／warm empty_cache_count，實際HTTP0／正式ledger新增0；initial verifier的float精度斷言改用既有微秒容差，沒有改production時間契約或重抓來源。[原件重播與限制](evidence/source-acquisition/20261010/short-annual-index-final-original-replay-proof.json)。
- 三份最後runtime已由正式 `start_mac.command` 載入，launcher69497／role-all worker69525／API69527；其他30份已部署hash、158套件、`.env`、六queue與scheduled保持，Redis BGSAVE及healthz／readyz200核對，無force kill／commit／push／模型路由變更。[正式重載](evidence/source-acquisition/20261010/short-annual-gap-release-proof.json)。其後僅對原缺口7740做一次正式共用Redis來源探測及暖讀，**首次173.13ms／1 HTTP，暖讀2.37ms／0 HTTP**；兩次均value None／error／count0、原ISO與300秒保持。原canonical帳本如實新增430853 failed_count及430854 empty_cache_count，**新增成功0、報告refresh0、模型工作0**，沒有把快取重分類為成功。[正式快取實測](evidence/source-acquisition/20261010/short-annual-gap-formal-shared-cache-probe-proof.json)。CLI探測沿正式cache factory／namespace與相同已部署來源版本，這不是報告重分析或API報告成功。
- 另找到新的 [AFAB勞工中心網站Medtecs集團職缺原頁](https://www.afablabor.com/job-opportunities/medtecs-group-of-companies9383773)，native **HTTP200／115,874bytes／0.779秒**、完整原件archive與hash讀回一致。頁面刊登2026-09-17、opening2026-09-14、closing2026-10-14，BASS MACHINE OPERATOR需求7人是**一篇公告**，不是七個職缺。只明示MEDTECS GROUP OF COMPANIES，沒有9103母公司精確法人橋接；該網站到政府domain的反向官方橋接也未驗。未登入／申請、未接成issuer計數。[完整原件與缺口](evidence/source-acquisition/20261010/afab-medtecs-dated-group-job-new-original-proof.json)。後續須先補精確直接雇主證據，不能以集團名稱擴alias。
- **14:53:58台灣時間**原20類近24h仍 **16／20嚴格>80%**：財報23/56=41.071%、法說75/106=70.755%、職缺24/33=72.727%、近期事件109/147=74.150%。本輪探測新增一次真不足年限觀測，財報取得率因此未上升；法說比例含24h滑動窗口。ledger430854、jobs1134、原歷史／分母／分類／窗口／品質gate不改；研究六次native HTTP未灌入正式SLA。Goal仍active且未達，這輪完成新的完整原件、來源年限判讀及重複查詢修正，不宣稱恢復五年財報或所有缺口。[最後原口徑驗收](evidence/source-acquisition/20261010/short-annual-gap-completion-check.json)。 **14:58:00最後唯讀讀回**仍16／20：財報22/55=40%、法說73/104=70.192%、職缺23/32=71.875%、近期事件107/143=74.825%；cache probe之後provider新增mutation0、ledger430854／jobs1134、API69527與33份runtime hash相符、原件及文件連結核對。此後比例變化為原觀測自然離窗，沒有新增取得或重標歷史。[最後讀回](evidence/source-acquisition/20261010/short-annual-gap-final-readback-check.json)。


### AFAB現行職缺明細與免費入口資格續查（2026-10-10）

- 上輪為progress：不足五年財報的重複查詢已正式修正。本輪沿原二十類／近24h／逐類嚴格>80%及免費限制，先讀runtime doctor、原canonical ledger與已部署版本；未重刷已補齊報告。[本輪來源與最後驗收](evidence/source-acquisition/20261010/new-free-employer-entrances-qualification-and-completion-proof.json)。
- 新完整原件為[美德官方聯絡頁](https://www.medtecs.com/contact/)與[公司架構頁](https://www.medtecs.com/medtecs-corporate-structure/)，普通匿名TLS HTTP200／297,272與386,633bytes／2.222與2.694秒。聯絡頁列菲律賓及百慕達的Medtecs International Corporation Limited；架構頁明示2021 Corporate Structure及Philippine Branch，不能由歷史架構推定當期集團職缺的直接法人。LinkedIn所列medtecsphilippines.com native DNS解析失敗、未取得原件。AFAB.gov.ph首頁403 challenge的5,342bytes拒收原件已保存，沒有重試、繞過或宣稱反向官方domain橋接完成。[原件與失敗診斷](evidence/source-acquisition/20261010/new-free-employer-authority-and-announcement-entry-native-proof.json)。
- 新[AFAB勞工中心網站首頁](https://www.afablabor.com/)實際連到[Job Quick Search](https://www.afablabor.com/job-quick-search.html)，完整HTML分別HTTP200／59,729与49,176bytes／0.356與0.394秒。普通匿名瀏覽器頁載入公開Cognito查詢，僅選公司、職務及唯讀明細，未登入、註冊、申請或傳送履歷。頁面明示查詢是目前需人力的公司及職務；MEDTECS GROUP OF COMPANIES提供BASS MACHINE OPERATOR、FACEMASK MACHINE OPERATOR、MACHINE FABRICATOR、SAFETY OFFICER四種選項，**四種職務不等於四筆已核對的獨立職缺**。Safety Officer明細需求1人、截止2026-10-23，工作內容可見；這是dynamic visible UI evidence，不冒稱完整native HTTP data body archive。[首頁原件](evidence/source-acquisition/20261010/afab-public-home-quick-tool-new-entry-native-proof.json)、[查詢頁原件](evidence/source-acquisition/20261010/afab-public-quick-tool-complete-native-proof.json)。
- 沿舊完整公告中實際category href取得[Medtecs公司分類頁](https://www.afablabor.com/job-opportunities/category/medtecs-group-of-companies)，HTTP200／141,171bytes／0.455秒。第一個研究selector假設body位於blog-post容器內，得到parsed0；原HTML有不符合此假設的巢狀結構，這是研究parser失配，**不是valid empty來源**。後續僅讀同一保存原件的直接title/header日期，未重抓分類頁。沿其實際9/24 href取得[新的Safety Officer完整公告](https://www.afablabor.com/job-opportunities/medtecs-group-of-companies8563839)，HTTP200／115,827bytes／0.487秒；原文刊登2026-09-24、opening2026-09-23、closing2026-10-23、需求1人與上列UI相符。公告仍只寫集團名，沒有直接雇主全名／法人橋接，因此**未歸入9103母公司職缺、未啟用正式計數**。[初始selector診斷](evidence/source-acquisition/20261010/afab-medtecs-new-safety-post-complete-native-proof.json)、[新完整原件與修正判讀](evidence/source-acquisition/20261010/afab-medtecs-new-september-detail-native-proof.json)。
- 另找到ShareInvestor匿名公開Medtecs SGXNet頁，原5月公告與實際related link連出的10/09處分公告均HTTP200／143,362与143,250bytes／4.353与4.366秒。**網站使用條款明確禁止自動及人工監控／複製，資料授權另收費**，故不符合本次免費自動來源限制；查閱條款後未繼續附件／JS追查、不接正式adapter、不改原SGX API401停用路由。只保留本次已取得的來源資格診斷，不把免費可開啟HTML當免費自動介接許可。[條款及連結原件](evidence/source-acquisition/20261010/shareinvestor-medtecs-current-linked-article-native-proof.json)。
- 本輪11次有界native研究請求，十份有body完整原件（九份HTTP200及一份403拒收body）逐件archive及本地hash讀回相符，DNS失敗沒有原件。正式provider ledger新增0、report refresh0、模型job0、backend修改0、restart0；33份已部署runtime及.env原hash保持，healthz／readyz200、API69527。沒有程式行為修改，未重跑無關測試。**15:16:14台灣時間**原二十類近24h仍**16／20嚴格>80%**：職缺23/32=71.875%、法說72/103=69.903%、財報22/55=40%、近期事件107/143=74.825%；ledger430854、jobs1134不變。比例變動含原觀測自然離窗，不能歸功研究取得；本輪進展為新完整原件、公開職務與截止日查驗及排除不適合免費自動使用的入口。Goal未達、維持active，精確雇主／財報欄位／法說與近期事件缺口仍需補足，SINBON月份精度選擇仍待答。[完整原口徑SLA](evidence/source-acquisition/20261010/new-free-employer-entrances-final-sla.json)。


### 真實法人逐日分項引用缺口修正（2026-10-10）

- 原二十類逐類嚴格>80%的goal仍active。本輪先核對真缺口與保存失敗報告，找到9103的Agent23明示2026-10-08外資買超690,000股、自營商買超304,496股，原FinMind逐日分項與封存完整TWSE T86皆吻合；原引用投影只有逐日總額及期間分項，未供給逐日法人分項，導致四項正確數字被誤擋。未用推算／別公司／其他日期／錯誤單位補值。[原失敗及完整原件核对](evidence/source-acquisition/20261010/institutional-daily-category-gap-baseline-proof.json)。
- 新增純函式`institutional_daily_evidence.py`，僅接明列ISO日期、原供應商、shares單位及有限整數的外資／投信／自營商列；宣告日期最多100、原列最多300，只投影最後十個原宣告日期、最多30列。任何相同日期／分項的重複列拒收該項，缺項不补零；原十九筆引用前綴及索引保留，明列typed records不能借未宣告的raw欄位。prompt只加最新原日期三列，三份保存報告增加約533–542字元；若最新資料無效，不轉用舊日冒充最新。股、千股、日期、法人及多日窗口原限制保留。[範圍diff](evidence/source-acquisition/20261010/institutional-daily-category-scoped.patch)、[實作](evidence/source-acquisition/20261010/institutional-daily-category-implementation-proof.json)。
- 新行為先7 failed／17 passed；最終兩批相關測試206+167=373 passed，另四項既有失敗已用修改前兩模組overlay逐一重現（兩項固定10/02舊日期、兩項既有trade-sources:v2期望）。沒有改日期／manifest契約或斷言來通過；獨立134相關＋9額外=143 passed、最後三份runtime hash吻合、無未解material finding。[原版本失敗核對](evidence/source-acquisition/20261010/institutional-daily-category-baseline-failure-check.json)、[獨立覆核](evidence/source-acquisition/20261010/institutional-daily-category-review-proof.json)。
- 原保存文字及來源不變重播：9103法人diagnostics **4→0**、1301 **5→1**、2855 **1→1**；後兩份模糊多日27,000千股及主體／期間不符仍阻擋。重播HTTP0、模型呼叫0、正式寫入0，不等於這三份報告重分析／發布成功。最初probe把上一輪ledger430854當固定值，遇正式排程自然開始而斷言失敗；初始診斷留存，改成當次唯讀before/after及本身零呼叫核對，不重標自然排程為probe活動。[原文字重播](evidence/source-acquisition/20261010/institutional-daily-category-original-replay-proof.json)、[初始診斷](evidence/source-acquisition/20261010/institutional-daily-category-original-replay-initial-diagnostic.json)。
- 正式自然watchlist工作在研究期間已開始。取得六queue queued／started／deferred全零空檔後，正常TERM role-all worker，**21件scheduled IDs及scores原樣保留**，Redis BGSAVE成功；stop helper一度錯讀legacy watchlist.sqlite3，唯讀回無dispatch table，未修改該DB；即時依`watchlist_store._db_path`改讀canonical operational.sqlite3，核對**61筆durable dispatch**後完成正常launcher/API停止。無force kill／取消／清空重試。由正式`PIP_NO_INDEX=1 ./start_mac.command`重載，launcher82272／worker82300／API82302，三份本輪及前33份runtime、158套件及.env hash保持，healthz／readyz200。重載後已到期工作正常轉queued／started，逐件RQ及canonical job讀回原21件仍在，acknowledged派送及其身分／收據保留。[正式重載及完整排程核對](evidence/source-acquisition/20261010/institutional-daily-category-release-proof.json)。
- **15:54:54台灣時間**讀回重載後原排程`21f4aab...`／2023.TW v4的真Agent23新checkpoint，原數字外資415,332股、投信5,000股與完整官方原件吻合；相同新保存文字用旧／新validator，誤判**3→0**。該工作當時還在Agent24因Gemini備援503及冷卻等待，不把角色輸出當整份報告成功，Gemma備援錯誤也未冒稱已修好。probe本身未新增來源或模型呼叫。[真實排程角色讀回](evidence/source-acquisition/20261010/institutional-daily-category-natural-job-readback-proof.json)。另6152.TW原排程重載後自然done並發布，新HTML／Markdown／data三原件hash讀回、lint passed、evidence approved，內容可信度與契約仍warning；未宣稱全部品質警示已消失或可因果歸功本次修改。[發布結果及保留警示](evidence/source-acquisition/20261010/institutional-daily-category-natural-report-publication-proof.json)。
- **15:55:26**原二十類近24h仍**16／20嚴格>80%**：財報38/80=47.500%、法說98/135=72.593%、職缺36/49=73.469%、近期事件177/234=75.641%。自然排程本輪已26件（done5／waiting_retry19／error1／running1），formal ledger432959、current jobs1154；這些自然取得／重試與24h離窗可能改變比率，不能歸功純證據投影或唯讀驗收。研究HTTP／模型呼叫／手動報告refresh新增皆0，原分類／分母／歷史／品質gate保持、80%未達。後續仍補財報完整年度科目、法說內容、精確直接雇主與事件原件；SINBON月份精度選擇仍待答。無commit／push或model routes変更。[原口徑正式驗收](evidence/source-acquisition/20261010/institutional-daily-category-completion-check.json)。


### Contact TAIWAN 新公開招募入口資格查驗（2026-10-10）

- 新找到[Contact TAIWAN美德招募案例原頁](https://contacttaiwan.tw/MainOne/DocList2.aspx?docid=11329&pid=1186&uid=1189)，普通匿名TLS HTTP200／48,477bytes／1.261秒，完整原件及archive讀回一致。頁面標題明示Medtecs International Corporation Limited、正文說2024加入平台及成功招募外國人才；沒有文章原發布metadata、單一職缺刊登／截止日期，不能當2026仍開放的母公司職缺。[案例原件](evidence/source-acquisition/20261010/contact-taiwan-medtecs-new-public-entry-native-proof.json)。
- 只沿該原頁實際公開href取得[About US](https://contacttaiwan.tw/MainOne/DocList2.aspx?uid=412&pid=412&docid=104)與[Job Opportunities](https://contacttaiwan.tw/MainOne/JobList2.aspx)，HTTP200／43,268及51,981bytes／0.697及1.150秒、兩份完整原件與hash相符。About頁明示經濟部委託外貿協會營運；匿名job list可見九列雇主／職稱／產業，沒有逐筆刊登／截止日、stable job ID及原職缺link，亦無美德列。頁面明示更多職缺需加入個人會員，未註冊／登入／聯絡或猜測會員API，不以九列當已驗當期職缺數。[官方自述及公開清單原件](evidence/source-acquisition/20261010/contact-taiwan-authority-and-jobs-new-public-native-proof.json)。
- 新入口與三份完整原件已保存，但仍research-only、新增合格職缺0、自動provider未啟用。三次native研究不寫formal SLA、不新增模型工作、不刷新已補齊報告；搜尋結果中的舊PhilJobNet及已拒絕Jobstreet入口未重試，Goodinfo僅搜尋線索、未當成MOPS法說原件。本輪新發現可排除「成功案例就代表當期職缺」假說；原二十類逐類>80%仍未達，維持active，後续只追具名直接雇主與明確日期／開放狀態的完整資料。[資格及限制](evidence/source-acquisition/20261010/contact-taiwan-new-entrance-qualification-proof.json)。


- **16:04:15台灣時間最後唯讀驗收**：API82302／36份runtime及.env hash保持；原20類仍16／20，財報39/81=48.148%、法說100/137=72.993%、職缺37/50=74%、近期事件180/239=75.314%，goal未達。自然26件為done7／waiting_retry16／error2／running1，ledger433242、current jobs1154；原分母及失敗歷史保留，不歸功三次Contact TAIWAN研究或純證據投影。[最後原口徑讀回](evidence/source-acquisition/20261010/institutional-daily-category-final-readback-check.json)。
- 原2023.TW `21f4aab...`後續自然重試已done／正式發布`2023_TW_v4_report_job_65a5c5bbda7c.html`，透過ReportArtifactLocator核對HTML／Markdown／data完整hash及保存品質metadata；仍按實際warning狀態記錄，不稱全部警示已消失。7740自然新工作則仍因法人主體／日期／期間及final_audit阻斷未發布，沒有放寬gate掩蓋。[2023正式發布及品質](evidence/source-acquisition/20261010/institutional-daily-category-natural-2023-report-publication-proof.json)。


### 證交所注意公告條款標記修復與正式取得（2026-10-10）

- 上輪為progress：法人引用修正已部署並驗真排程。本輪按原二十類／近24h／逐類嚴格>80%驗收，先核對API89290之前的82302與36份runtime／.env、doctor及canonical source ledger。初始兩個唯讀SQL誤假設timestamp／metric欄，經PRAGMA改用created_at／status／details_json；沒有正式写入。新基準與當期失敗分開保存，未把cache success字樣當新HTTP。[新基準](evidence/source-acquisition/20261010/free-source-after-institutional-next-gap-baseline.json)。
- 找到真parse_error兩筆：川湖2059（ledger431204）及健策3653（432868）。有界讀取15:26後125個小型本地封存檔，精確找到兩份完整TWSE官方JSON，835／1,081bytes及原hash吻合；stat／query／fields／日期／stockNo／total均相符。原第三／第二列含`<font color='#FF0000'>﹝第十一款﹞</font>`裝飾，舊parser因尖括號將整份拒收，不是來源空或body截斷。原canonical事件未保留精確取得epoch／完整archive指標，未由檔案mtime捏造取得收據；研究重播觀測時間明示fixture cutoff。[原件與錯誤重現](evidence/source-acquisition/20261010/twse-notice-current-parser-failure-original-baseline.json)、[before與完整fixture hash](evidence/source-acquisition/20261010/twse-notice-clause-markup-owned-baseline.json)。
- 只修改`data_fetch/market_sources/twse_trading_notices.py`：固定已觀測的第十一款red font字串替換成同一完整條款文字；原JSON bytes仍完整保存。未知tag／attribute、script、URL及錯誤股票／日期／query／總筆數保持拒收；源頭max4,000及正規化後min10字檢查保持，原30日／31列／單次與八秒期限／單工／cooldown不變。只對檢查副本最多八輪unescape至固定點、大小寫無關檢查URL；保存text不decode、不通用strip HTML、不渲染来源HTML。[範圍diff](evidence/source-acquisition/20261010/twse-notice-clause-markup-scoped.patch)、[實作與測試](evidence/source-acquisition/20261010/twse-notice-clause-markup-implementation-proof.json)。
- 新公開行為先5 failed／14 passed（其中IndexError為原資料空的衍生結果，不當額外根因），第一版九組265 passed。一次錯誤test檔名造成0 tests，不算通過。獨立覆核找到兩組P2：多層encoding／大寫URL及移除後低於min10字；root新增反例實際4 failed／19 passed，再修正。最後九組 **269 passed**；限定再覆核 **67相關＋10額外passed**，最後SHA37fd04f1...、無未解material finding。未在finding開放時部署。[初始覆核問題](evidence/source-acquisition/20261010/twse-notice-clause-markup-review-initial-findings.json)、[最後獨立覆核](evidence/source-acquisition/20261010/twse-notice-clause-markup-review-proof.json)。
- 最後版對同一兩份完整原件離線重播，舊版皆notice issuer row unverified，新版健策3／川湖2列；source row原文字／日期／JSON保持。四筆先前正式9103無裝飾公告的record及digest與saved-before逐位相同，沒有改寫既有報告或門檻。重播HTTP0、formal SLA寫入0、模型呼叫0，不當正式成功。[最後版原件及legacy相容重播](evidence/source-acquisition/20261010/twse-notice-clause-markup-final-original-replay-proof.json)。
- 六queue空檔正常TERM worker後，**13件待重試IDs／scores及61筆durable dispatch**保持，Redis BGSAVE成功，正常停止launcher／API，未force kill／清queue／取消工作。正式`PIP_NO_INDEX=1 ./start_mac.command`重載，launcher89260／role-all worker89288／API89290及父子／cwd核對；本輪一份與前35份runtime、158套件及.env保持，healthz／readyz200，原13件RQ與canonical jobs逐件讀回。[正式重載](evidence/source-acquisition/20261010/twse-notice-clause-markup-release-proof.json)。
- 重載後只對上述兩個真失敗來源各做一次正式native provider查驗，沿原共用Redis cache、原guard與canonical`record_source_audit_entries`，沒有清冷卻或改TTL。健策 **success／3列／0.161秒**，川湖 **success／2列／0.167秒**；兩次真正HTTP，兩份完整body與原失敗原件**完全相同**，保存後五列重驗通過，證明是解析修正，非網站新增內容。原431204／432868失敗列逐欄保持，canonical如實新增兩個success；五列不是五次成功請求，亦未稱投資影響已驗證。這是正式相同來源factory的CLI查驗，不是API報告刷新或整份報告成功；模型jobs0、report refresh0。[正式來源成功與完整原件](evidence/source-acquisition/20261010/twse-notice-clause-markup-formal-provider-proof.json)。
- **16:25:12台灣時間**原二十類仍 **16／20嚴格>80%**。近期事件180/239=75.314%→182/241=75.519%；財報39/81=48.148%、法說100/137=72.993%、職缺37/50=74%，四類仍未達。原source分類／窗口／分母／失敗歷史與品質gate不變，不將offline研究灌入SLA。自然26件done10／error3／waiting_retry13，ledger433588、current jobs1146；除本輪兩個有fetch_id的真取得事件外，其他觀測及job變化由正式背景工作處理，未冒稱本輪新增分析或消除所有報告警示。Goal active／未達，後續仍需補財報年度完整科目、法說與直接雇主職缺。[最後原口徑驗收](evidence/source-acquisition/20261010/twse-notice-clause-markup-completion-check.json)。


### 大東電免費財報新入口、加密限制與官方 iXBRL 原件（2026-10-10）

- 上輪為progress：兩個真注意公告parse_error已修復、正式同body取得3+2公告。本輪仍按原二十類／近24h／逐類嚴格>80%驗收，先核對API89290、36份已部署runtime與.env、canonical source帳本；最低財報仍39/81=48.148%。新原失敗股票1623的官方primary在取得索引後就因fewer than five consolidated annual filings拒收，不能先假定它是HTTP錯誤或科目解析遺漏。[本輪新基準](evidence/source-acquisition/20261010/financial-after-notice-fix-next-gap-baseline.json)。
- 新找到[大東電官方財報入口](https://tewc.com.tw/investor/financial/)，一次普通匿名TLS **200／155,881bytes／0.189秒**，完整body/archive/hash讀回一致。頁面明示1623，13個document links包含同一111Q4合併URL重複，不能當十三個已核對期間；個體／個別／合併及季度資料分開，未用檔名或上傳年補成財年。Google Drive連結尚不能據此推定anonymous backend可讀。[新官網完整索引](evidence/source-acquisition/20261010/tewc-1623-new-financial-entry-native-proof.json)。
- 沿Primary web搜尋可觀測的[官網合併PDF](https://tewc.com.tw/wp-content/uploads/2025/06/IFRSs%E5%90%88%E4%BD%B5%E8%B2%A1%E5%A0%B1.pdf)及原索引實際個體href各取得一次，普通匿名TLS均200，**1,622,880／1,683,170bytes、0.333／0.360秒**，完整binary及原件讀回一致。合併PDF目前未列於這份官網index，沒有由此推論未發布或財年；兩份原native parser都返回parser_warning，沒有宣稱封面／所有頁或財務科目已成功解析。[完整原件及拒收](evidence/source-acquisition/20261010/tewc-1623-new-complete-financial-pdfs-native-proof.json)。
- 套用Google Drive技能，以官網原href的精確IDs讀metadata後`fetch(download_raw_file=True,include_base64=False)`，取得標示「111第四季合併財務報告.pdf」及「114年第四季財務報告書(個別).pdf」兩個完整file_uri。用無回顯PTY把工具回傳的opaque file reference供有界materialization，取得**1,759,568／1,611,479bytes**，byte count與connector回報相符、PDF binary及本地hash重讀一致。憑據明示`google_drive_connector_raw_file`，不是直接匿名Google Drive HTTP原件；metadata `access_not_verified`保留、modified_time非首次發布日／財年。未查使用者其他Drive檔、未登入新帳戶／改共享；signed download URL及inline base64未寫repo。[metadata及限制](evidence/source-acquisition/20261010/tewc-1623-drive-connector-metadata-proof.json)、[111標示原件](evidence/source-acquisition/20261010/tewc-1623-drive-2022-consolidated-complete-original-research-proof.json)、[114標示原件](evidence/source-acquisition/20261010/tewc-1623-drive-2025-individual-complete-original-research-proof.json)。檔名年度不是已驗證正文年度。
- 四份PDF現行解析均拒收；在相同pypdf6.19.0 Configuration、512MiB／10秒有界child中，僅擷取first warning後立即拒收，全部為`pypdf._encryption: ignore '/Perms' verify failed`。再僅讀plaintext Encrypt dictionary，不保存password hashes：各V5／R5／P2244／Length256、declared copy/extract bit False，permission integrity仍未驗。未關閉警示、解密保護、用OCR／其他parser繞過擷取限制、假稱native全文或解讀財務圖像；也不因此武斷宣稱所有免費財報都不能用。[第一警示及原門檻](evidence/source-acquisition/20261010/tewc-1623-pdf-rejection-first-warning-diagnostic.json)、[加密宣告診斷](evidence/source-acquisition/20261010/tewc-1623-pdf-encryption-declaration-diagnostic.json)。
- 轉查另一個原已允許的公開MOPS入口，先核對persistent guard無active row、未清保護，再一次普通POST精確1623，**200／7,159bytes／0.131秒**、完整索引原件保存。當次只列2023／2024兩份Q4合併及2025Q4個別，不能串成五年同口徑，也不推論別處永遠無其他文件。[當期scope索引](evidence/source-acquisition/20261010/tewc-1623-current-native-xbrl-index-proof.json)。
- 僅沿該索引實際2024C download href取得一份**未受上述PDF限制的官方inline XHTML**，普通匿名TLS **200／518,891bytes／0.591秒**，完整binary/archive/hash核對。原strict parser逐issuer／原period／TWD／scale／sign核對，2024及其2023比較數各 **9/9科目**完整；2024 CFO147,693,000 TWD、PPE現金購置-63,442,000、無形資產現金購置-5,558,000，這些是原文明示數字，不推估missing為零。仍只是兩年已驗數字，非五年series／完整財報provider或報告成功，未啟用新route或覆蓋原financial歷史。[新公開官方原件及科目](evidence/source-acquisition/20261010/tewc-1623-current-official-xbrl-original-research-proof.json)。
- 本輪共核對**七份完整原件**：官網index、兩份官網PDF、兩份connector PDF、MOPS index與一份iXBRL；來源native請求5次、Drive metadata2操作／raw fetch2操作、file_uri有界materialization2次，connector內部HTTP數未觀測，不能混算為七次Google請求。研究SLA寫入0、model jobs0、report refresh0、runtime changes／restart0，沒有重抓已填補的其他股票來增加比例。[本輪資格與完整原件](evidence/source-acquisition/20261010/tewc-1623-new-financial-entrances-qualification-proof.json)。
- **16:48:37台灣時間**原二十類仍**16／20嚴格>80%**：財報39/81=48.148%、法說100/137=72.993%、職缺37/50=74%、近期事件182/241=75.519%。API89290、36份runtime及.env相符、healthz／readyz200，前次release十三個job IDs仍在canonical state／無取消，原自然排程與quota保護保持。ledger433851／current jobs1146反映背景活動，不把本輪研究或兩年原文科目算正式成功。Goal仍active／未達；本輪進展是新完整財報入口、權限限制分辨，以及另一路已驗九科目原文；後續追缺年度的同口徑公開原件，保留個別與合併的差異。[最後原口徑驗收](evidence/source-acquisition/20261010/tewc-new-financial-entrances-completion-check.json)。


### 騰輝與百達新免費招募入口續查（2026-10-10）

- 沿用原20類近24h逐類嚴格>80%的驗收。重新讀完整TWSE主檔既有cache，2236全名百達精密工業股份有限公司／統編42299452、6672騰輝電子國際集團股份有限公司／72952251及官方host吻合；主檔原epoch1791571868.112563未續期、未重新取得HTTP。另26筆原未取得職缺觀測逐欄保存。[本輪基準](evidence/source-acquisition/20261010/zero-job-source-after-tewc-next-baseline.json)。
- LinkedIn公開短連結原件提供真正外部href，沿它取得新的[騰輝官方Vacancies](https://www.ventec-group.com/about/vacancies/)完整原件：HTTP200／54,471bytes／1.982秒。原表8個不同PDF href，分別為美國銷售主管、法／義／英業務、英／德客服、英行政及德機器操作；刊登日2026-04-10、04-20、04-23或07-20直接取自表格，沒有用搜尋結果的「3w」或檔名推發布日。[正式host與原入口](evidence/source-acquisition/20261010/parent-recruiting-official-destinations-native-proof.json)。
- 原8秒研究下載有6次HTTP200／curl28未完成，原失敗保持；對這六份各做一次15秒有界下載驗證，未重抓兩份已完整PDF。最後8份PDF完整原件均archive及hash讀回相符；native text **6 complete／2 partial**（義大利、英國業務PDF各garbled page1），原解析警示未放寬。六份後續取得不等於證明延長秒數單独導致恢復，傳輸延遲也有變動；正式下載設定未改。[初次下載](evidence/source-acquisition/20261010/ventec-new-job-pdfs-complete-native-research-proof.json)、[有界後續驗證](evidence/source-acquisition/20261010/ventec-job-pdf-bounded-download-followup-research-proof.json)。
- 此8列屬issuer官網的海外regional group recruiting candidates；Ventec USA／Ventec Central Europe未證明為6672上市母公司直接雇主，無明示截止日期，不能以列在當期清單或應徵信箱證明仍有效。`current_open_job_count=null`，新增合格母公司職缺0，未啟用正式provider／擴alias。新Legal Information原件是企業倫理及銷售／採購條款，不能冒稱已取得開放資料授權。[資格、原日期與限制](evidence/source-acquisition/20261010/parent-recruiting-new-entrances-qualification-proof.json)。
- 百達www首頁回301／146bytes；只沿完整moved-document body的實際href到非www官方host，取得首頁200／13,112bytes，再沿原href取得[Job Opportunities](https://patec-intl.com/careers_jobopportunities.html)200／10,920bytes。該頁只有一般人才邀請和履歷信箱，沒有職稱／刊登日／截止日，不能當已驗職缺或valid empty count0。初次研究helper不保存Location header，null不能解讀成無redirect target；本次由原body明示目的地，沒有猜URL或TLS繞過。[新招募及條款原件](evidence/source-acquisition/20261010/parent-recruiting-source-qualification-pages-native-proof.json)。
- 另外取得經濟部兩份官方dataset metadata完整原件，但分公司、公司名稱的資源都指向先前回504的同一GCIS catalog，沒有重試故障入口或據此建立同法人／子公司binding。台塑大學招募搜尋仍為舊活動或其他集團法人，原已取得FPC unique detail無公開日期的限制保持，未重抓既有已填補報告。[入口metadata及研究請求](evidence/source-acquisition/20261010/parent-recruiting-new-entrances-native-proof.json)。
- 本輪22次有界native研究請求、16份完整原件（含1份301移動頁）、8份完整PDF；研究新增formal SLA0、model jobs0、report refresh0、runtime changes／restart0。沒有程式行為修改，未重跑無關測試，以原件readback、現行parser結果、runtime doctor及健康檢查驗證。
- **17:12:38台灣時間**原20類仍**16／20嚴格>80%**：財報39/81=48.148%、法說100/137=72.993%、職缺37/50=74%、近期事件182/241=75.519%。API89290、36份runtime與.env hash相符、healthz／readyz200；原13件release retry jobs仍存在／無取消（done2／error2／waiting_retry9），帳本433913／jobs1146包含背景活動，非研究成功。原分母、歷史及品質gate保持，goal仍active／未達；本輪進展是新的完整官網與職缺PDF、原日期及雇主scope判讀，下一步仍需可明示直接雇主及有效日期的資料。[最後原口徑驗收](evidence/source-acquisition/20261010/parent-recruiting-new-entrances-completion-check.json)。


### 9103 新 MOPS 外國發行人完整公告入口正式接入（2026-10-10）

- 找到既有 IIH/EZSearch 普通公司公告格式未涵蓋的新入口：[MOPS重大訊息](https://mops.twse.com.tw/mops/#/web/t05st01)公開UI實際使用 `t05st01` POST月索引及 `t59sb01_detail` 外國發行人原件。對照同一9103，IIH原件是 `查無相關資料` error envelope；不能把它說成已驗完整空窗，也不能靠普通公告parser的零筆判斷外國發行人沒有事件。新公開索引／detail／PDF均以普通匿名HTTPS取得，無登入、金鑰、cookie、TLS繞過或遭拒後改用另一身分。公司橋接使用完整TWSE當期原主檔、9103／美德醫療-DR／美德向邦醫療國際股份有限公司／MEDTECS／官網／BM註冊地；重用的主檔原epoch1791571868.112563未續期。[新的原件研究](evidence/source-acquisition/20261010/tdr-new-mops-foreign-issuer-original-native-research-proof.json)、[前月原文](evidence/source-acquisition/20261010/tdr-9103-prior-month-and-direct-body-native-research-proof.json)。
- 新adapter限9103、原20秒parent期限／單次4秒HTTPS、最多3個月索引／10件事件、1MB PDF及有界原文解析。2026-10-09處分公告中文／英文是同一件，優先中文完整PDF；2026-09-24注意交易公告detail含完整已公布財務資訊。後者原文單位**仟美元／EPS分美元**、2026H1／2025H1／2025全年及負值 `-4,760`全部保留，不能補成TWD、完整五年series或法說逐字稿。原件封存後saved selector每次重讀完整master／index／detail／PDF、核對公司／日期／title／條款／附件綁定並從原件重建正文；只重算可改的projection digest仍不能變造幣別、負值或金額。此為事件樣本、`coverage_status=partial/window_complete=false`，未證明30日完整公告覆蓋。[本輪範圍patch](evidence/source-acquisition/20261010/tdr-mops-history-scoped-working.patch)。
- 補上 `source=tdr_announcements`既有資料刷新參數，僅9103及原TWSE company announcement history provider，未擴大其他來源取得。保留核心資料、其他audit／原取得時間、HTML／Markdown、analysis_evidence及品質gate；公告原文通過typed重驗才合併，重複舊標題進archive。POST-only無附件原件維持真實MOPS頁面連結，以原公告參數做內部事件去重，不編造可訪問detail URL。暖cache本輪HTTP count為0，原requests／原epoch保持，不能記新取得；receipt排除於prompt。
- public來源最初2 failed；獨立反例11 failed涵蓋PDF MIME、UTC日期、原件缺失／正文改寫、解析超時、非法identity／禁止alias、不同公告被泛頁連結誤去重；component起始2 failed，實際provider暖cache再2 failed。已逐一修正。最後來源／新聞／報告component／PDF／prompt／runtime／storage **288 passed**；獨立最後 **157 passed**（138回歸＋19反例），10份runtime SHA精確符合凍結範圍、無未解material finding，均隔離禁外網。[凍結狀態](evidence/source-acquisition/20261010/tdr-mops-history-review-state.json)、[獨立覆核](evidence/source-acquisition/20261010/tdr-mops-history-review-proof.json)。早先兩原件禁網重播仍為研究、不是formal SLA或部署證明。[原件重播限制](evidence/source-acquisition/20261010/tdr-mops-history-complete-original-offline-replay-proof.json)。
- 10份runtime透過正式 `start_mac.command`載入；31份此前來源成果、`.env`、158套件版本保持。worker先正常終止才停launcher/API，Redis BGSAVE成功、六queue無執行工作，3件scheduled及原13件job IDs／61件durable dispatch全保留，無force kill／取消／刪queue／commit／push。最後launcher14263／role-all worker14291／API14296、healthz／readyz200。[正式載入與保留證據](evidence/source-acquisition/20261010/tdr-mops-history-release-proof.json)。
- 真正缺此完整原文的9103既有報告 `9103_TW_v4_report_job_e35ec5d65a6a.html` **僅刷新一次**：HTTP200／**3.366秒／5次真實來源HTTP／新增2件完整原文／全部news12→14**。原12件、其他資料、HTML／Markdown／analysis_evidence、五份quality metadata及四種index hash核對一致。canonical帳本如實新增 **434243 fetched_count／record_count2**，舊失敗432041及129,719筆原零筆觀測不變。模型工作／LLM呼叫新增0；有1筆 `Data Provider` API-usage記錄，正確與模型區分。初版驗證script錯把所有API usage當LLM、並假設canonical摘要保留HTTP count而觸發斷言；其後只讀重驗原件／保存欄位／帳本完成核對，**未再發刷新請求**，失敗及更正證據仍保留。五次HTTP來自完整source audit，canonical聚合觀測只算一次取得，不把五次傳輸或兩件原文放大成五次／兩次成功。[正式單次刷新與重驗](evidence/source-acquisition/20261010/tdr-mops-history-formal-component-refresh-proof.json)、[匹配帳本](evidence/source-acquisition/20261010/tdr-mops-history-formal-linked-events.json)。
- 原`content_credibility`及`report_conformance`仍warning、未重新分析或新通過品質gate；新增原文沒有更換財報或法說。現行刷新政策此次維持 `analysis_text_stale=0/decision_validity_status=current`，這不是已將新原文重做分析或證明警示消除。
- **18:23:21台灣時間**原20類近24h仍**16／20嚴格>80%**：職缺32/40=80%（等於80不算突破）、法說77/103=74.757%、財報32/66=48.485%、近期事件153/204=75%。當次新入口只有一個真實成功觀測；其他變化包含24h窗口與原自然排程，沒有回補／刪失敗、降低gate、改分類或灌成功次數。原13件重試此時done8／error2／waiting_retry3均保留，goal仍active／未達全部類別門檻。[最後原口徑驗收](evidence/source-acquisition/20261010/tdr-mops-history-completion-check.json)。接續仍找可補完整年度／科目、法說正文及精確母公司雇主有效日期的免費原件。


## 9103 新 PhilJobNet 官方雇主入口與狹義零職缺數值（2026-10-10）

以完整當期 TWSE 上市公司名冊的 9103／MEDTECS／BM 註冊地／medtecs.com 官網，接續核對 [Medtecs Contact](https://www.medtecs.com/contact/) 的 Bermuda 與 Philippines 分頁法人全名，再核對 [PhilJobNet 雇主 2912](https://philjobnet.gov.ph/job-vacancies/company/medtecs-intl-corp-ltd-2912) 的公司主區、英文全名、雇主編號與 jobs 區唯一伺服器表格。完整 HTTP200 原件明示 `No job vacancies`；`Coming soon` 位於 review 區，並非 jobs 載入狀態。2021 Corporate Structure 僅是歷史分支佐證，未當成現行持股證據；全零台灣統編未當有效身分。

新 typed slot `job_openings_philjobnet` 保留 `portal_job_count=0`、`global_job_count=None`、`job_postings=[]`、`single_philjobnet_employer_listing`。依原數值觀測口徑只取得一個零值觀測，並非取得一筆職缺，也不代表全球沒有招募、招募縮減、首次刊登日期或集團總人數。完整三方原件重讀、hash／法人／分頁／來源時間核對後才接受；HTTP拒絕、部分回應、缺原件、錯型身分、HTML禁止別名、typed slot被移除、快取來源混用及同 jobs 區的矛盾列表均拒收。只 9103 使用包含 provider 身分的新 cache namespace，其他股票原 cadence 保留；暖讀保留原取得時間並以 HTTP0 記錄。內部收據不進入模型正文，狹義數值與未知範圍說明保留。

`AlternativeJobOpeningsProvider` 對 9103 優先走合格的新入口，失敗仍留原有備援。既有 source-only refresh 新增 `source=philjobnet_jobs`，只取得此雇主元件；原 104／1111 欄位、限制說明、失敗 audit、其他來源、核心時間、HTML／Markdown、analysis evidence 與五項品質 metadata 保留。沒有重寫舊失敗、分母、正式公式或品質門檻。

原公開行為檢查先失敗（期待一個數值觀測而實際為0）。獨立初審提出4組、9個可重現反例，均已修復並重驗。最終 root 同次隔離 runner **460 passed**，獨立覆核 **79 passed**（原9反例＋70相關回歸），8份 runtime hash 全符合最終 manifest，無未解 material finding；隔離測試未連正式資料庫／Redis／API／模型供應商。

正式 `start_mac.command` 重載後核對8份本次 runtime與38份既有 runtime、env、158套件、13既有jobs、61 durable dispatches、2排程；health／ready均200。舊零值 ledger **129,727列**（本次停止前截止）hash未改。僅針對原先缺這筆數值的 `9103_TW_v4_report_job_e35ec5d65a6a.html` 執行一次正式元件刷新：HTTP200，**3.670秒**，**2次原生HTTP**（Contact＋Profile；完整官方名冊沿用原取得時間），正式新增一筆 `fetched_count`／record_count1。原值、原audit、本文、analysis evidence、品質 metadata及index四hash核對通過；新增analysis job0、模型API事件0，只有1筆 Data Provider API usage觀測。沒有把研究HTTP加入正式SLA。

**2026-10-10 19:35:15台灣時間** last_24h 原20類維持，**17／20嚴格 >80%**。另類資料 **33／41＝80.4878%**（先前32／40＝80%）；剩餘法說 **76／102＝74.5098%**、財報 **32／66＝48.4848%**、近期事件 **153／204＝75%**。全部超過80的原目標尚未達成。法說比稍早77／103少一筆是24小時窗口移動，不是本次入口修改；原報告內容可信度與conformance警示仍保留，未重新生成投資分析。

本輪同時實查外國發行人2026-04-13重大訊息新入口，索引七筆分別為股東會／股份買回附錄／2025年報中英文／2025及2024財報，不能把年報誤當法說簡報。第7筆完整 detail 綁定官方財報PDF；相關網頁只取得完整空殼HTML，PDF GET在原8MB限額下HTTP200但curl63且body0，HEAD307並未提供可識別大小，尚未取得完整PDF、未擴限或繞過。FPC官方chemical detail雖有完整角色文字，但只有儲備人力／不限人數／無現行職缺ID與期限，未當新增開放職缺或數值零。這些研究只封存原件，不計正式成功。

證據：[qualification原件](evidence/source-acquisition/20261010/philjobnet-exact-medtecs-employer-new-native-proof.json)、[原始失敗與範圍驗證](evidence/source-acquisition/20261010/philjobnet-medtecs-isolated-verification-proof.json)、[獨立覆核](evidence/source-acquisition/20261010/philjobnet-medtecs-review-proof.json)、[正式runtime](evidence/source-acquisition/20261010/philjobnet-medtecs-release-proof.json)、[單一元件正式補取](evidence/source-acquisition/20261010/philjobnet-medtecs-formal-component-refresh-proof.json)、[原20類驗收](evidence/source-acquisition/20261010/philjobnet-medtecs-completion-check.json)、[外國發行人財報入口](evidence/source-acquisition/20261010/medtecs-2025-official-short-financial-entry-native-proof.json)、[FPC角色原件](evidence/source-acquisition/20261010/fpc-official-chemical-role-detail-new-original-proof.json)。


## 一般分析年度資料共用、強制更新及冷卻保護（2026-10-10）

上一輪為progress：PhilJobNet新增一筆合格正式數值觀測，另類資料33/41突破80%。本輪重讀doctor、current runtime、canonical last_24h與既有財報原件，財報缺口仍為缺年度／無形資產現金支出／不完整比較列，不由缺欄推零、不混個體／合併／幣別，也未再重查已否定的比較資料或財報下載。

發現一般非forced core／quote刷新沒有使用既有年度來源共用快取，只在radar啟用；股價重抓時會重讀年度三表，capital notes又讀一次balance。`yfinance_core_fetch.py`現在讓正常分析沿原年度cadence；原完整4h、部分1h、空5m、金融業profile及基金不適用契約保留。明確forced report仍真讀原供應商，FinMind亦保持冷讀；新`shared_fetch(force_refresh=True)`在原single-flight鎖內更新該key，後續normal沿用剛取得新值，其他key及供應商quota／cooldown保持。

SDK第一次讀到的未四捨五入資產／權益以`primary_balance_snapshot`保留，只在ticker、年度／期間、balance品質、原時間、原數值fingerprint、獨立audit raw-input SHA及原history均可對齊時供capital notes使用；不合格／官方其他basis保持原退路，不能以相同rounded值允許原值篡改。source-only時間由`annual_history_cache_freshness.py`重建，cached原epoch／ISO不隨新quote續期；缺值、bool、非有限數、巨大整數溢位、矛盾／無時區時間均為unknown。暖讀HTTP0／attempts0／新call歸屬，原partial、FCF缺值與child stale保持；未知／壞histories走原供應商恢復，cache cleanup故障不丟掉取得值。force失敗保留原值／epoch／retention／retry，但到期freshness，下一normal正確沿stale cooldown，不能隱藏失敗。

原public core兩次正常quote120→125先2failed（financials／cashflow各2讀，balance4讀）。修正後合格SDK資料cold三表各1、warm新增0；數字與原SDK時間不變，新quote／market時間更新；partial FCF仍None。新增強制營收1.2→3.0後正常刷新130仍3.0、巨epoch、錯型cache、raw-value小幅篡改、child stale與force失敗反例。最終17檔同次隔離runner **272 passed**。獨立初審5個公共反例failed、修正後112相關＋5反例passed；追加shared force失敗反例1failed亦修正，最後shared／年度邊界26passed及該反例1passed，六份runtime SHA均match，無未解material finding。階段測試有重疊，不將階段數字相加成獨立總數。

正式重載前第一次檢查因原排程自然推進而拒絕停止，worker／API仍在；重讀實際六queue空閒、原13job狀態與目前1個scheduled job，再SIGTERM自有worker／launcher，無強制kill／取消。Redis BGSAVE成功；新launcher36637／role-all worker36665／API36667，六份本輪及46份保留runtime、env、158套件、61 durable dispatches、13原job與1排程均核對；healthz／readyz200。舊零值ledger截止 **129,733列** hash不改。

**2026-10-10 20:17:02台灣時間**按原20類／last_24h仍 **17／20嚴格>80%**。法說76/102＝74.5098%、財報32/66＝48.4848%、近期事件153/204＝75%，目標尚未達成。原13job現done9／error3／waiting_retry1是自然排程進展，重載前後保持。本輪操作觸發的source acquisition、正式report refresh與模型呼叫均0；沒有把隔離cache行為算正式成功或更改原分母／歷史／formula／quality gate。latest25report的exact-key查驗沒有現有outer annualcache，因此**未宣稱正式活網warm延遲改善或新取得五年財報**；已驗證real core public path的隔離行為、部署code identity及正式健康，實際新來源成功率仍須從後續真實工作驗收。

證據：[基準](evidence/source-acquisition/20261010/next-missing-financial-source-baseline-20261010.json)、[範圍diff與最終manifest](evidence/source-acquisition/20261010/normal-annual-reuse-review-input.json)、[原反例及隔離驗證](evidence/source-acquisition/20261010/normal-annual-reuse-isolated-verification-proof.json)、[獨立覆核](evidence/source-acquisition/20261010/normal-annual-reuse-review-proof.json)、[安全停止未放行紀錄](evidence/source-acquisition/20261010/normal-annual-reuse-safe-reload-deferral-check.json)、[正式runtime](evidence/source-acquisition/20261010/normal-annual-reuse-release-proof.json)、[當前cache查驗限制](evidence/source-acquisition/20261010/normal-annual-reuse-existing-source-cache-inventory.json)、[原20類驗收](evidence/source-acquisition/20261010/normal-annual-reuse-completion-check.json)。

## 繼續找免費原件：四個公司法說／股東問答入口（2026-10-10）

重讀當期失敗後，找到恆大1325、冠西2466、健策3653的官方法說下載入口，以及美德醫療9103的官方股東會紀錄。公司全名／代號／官網以既有完整TWSE主檔重驗，沿用原取得epoch1791571868.112563，不重新取得或續期身分主檔。

| 公司／官方入口 | 實際取得與限制 |
| --- | --- |
| [美德醫療 AGM & SGM](https://www.medtecs.com/investor-relations/agm-and-sgm/) | 完整PDF292,877bytes，13頁native文字complete；原件明示2026-04-28，附錄有14組股東問答。可補有日期的管理階層說明，仍是股東會紀錄，不是法說逐字稿，不能列作近30日新事件；首次發布日未驗。 |
| [恆大法人說明會](https://www.uk.com.tw/zh-tw/download-c16560/%E6%B3%95%E4%BA%BA%E8%AA%AA%E6%98%8E%E6%9C%83.html) | 完整PDF637,681bytes、31頁，原件代號1325／2025-12-19相符；13頁含未映射的私用字元U+F0A1，現行reader仍partial，未全域放行或刪掉亂碼警示。 |
| [冠西法人說明會](https://www.cosmo-inc.com/tw/investor/conference.aspx) | 原表的圖示a href提供真正官方PDF下載；完整原件已保存，但現行reader報parser_warning，未跳過。索引只有2025年，沒有補造特定召開日或已讀正文。 |
| [健策法人說明會](https://www.jentech.com.tw/institutional-investor-conference-information) | 瀏覽器實際顯示2025-11-28及下載href，沿原301明示的filesusr.com Location取得完整PDF2,735,790bytes／24頁；7頁仍garbled／partial。官網HTML與條款的兩次有界native下載未完成，原失敗保留；條款由可見頁面核對，商業複製／再利用需先取得書面同意，未把免費匿名下載當商業授權。 |

另找到百一6152官方法人說明會頁，但直接web取得403，沒有改身分、重試或啟用。美德公告頁只提供SGX查詢指引，不是新的完整公告清單；MYSON影音此前已驗無字幕，本輪未重試。沒有重查已證明缺欄的年度財報，也未將股東問答當五年合併數值。

本輪10次有界匿名native研究請求，取得7份完整HTTP200正文，其中4份完整PDF；文字1complete／2partial／1parser拒收。研究helper起初因冠西parser_warning中止，先保留原下載，再僅本機重播恢復證據，沒有重抓前三份PDF。原件hash／bytes／身分及14問答序號已逐一重讀；所有來源仍research-only，未改runtime、重啟、觸發模型或正式report refresh，也未把研究數算正式取得率。

**20:36:59台灣時間**重新讀正式last_24h原20類：**17／20嚴格>80%**，法說75/101＝74.2574%、財報32/66＝48.4848%、近期事件153/204＝75%。API36667、52份runtime及env hash相符，health／ready200；原口徑與品質gate保持，goal未完成。本輪進展是新的完整PDF入口與內容資格，後續優先處理合格來源的文字解析與有日期的管理階層證據，不能靠放寬partial或改分類達標。

證據：[索引原件](evidence/source-acquisition/20261010/new-issuer-conference-and-agm-entrances-research-proof.json)、[前三份PDF及解析](evidence/source-acquisition/20261010/new-issuer-conference-and-agm-attachments-native-proof.json)、[健策原下載與CDN](evidence/source-acquisition/20261010/jentech-new-official-conference-attachment-native-proof.json)、[來源資格重驗](evidence/source-acquisition/20261010/new-issuer-entrances-source-qualification-proof.json)、[正式原20類驗收](evidence/source-acquisition/20261010/new-issuer-entrances-completion-check.json)。

## MOPS 法說年度原件重用、強制更新及誠實計數（2026-10-10）

一般法說取得原先會重查當年空列表及前一年的有效活動。新增 `mops_conference_cache.py`，只供明示 opt-in 的既有 earnings-call 流程；public helper 預設與明確 session 保持直接取得。保存完整原回應 bytes、exact decoder、HTTP200及原時間到既有內容定址 archive，正常暖讀重新使用相同 parser 驗證股票／市場／年份／URL／hash／大小／原時間。成功期限沿原 earnings-call policy、空回應600秒；force 在原 single-flight 內更新同 key，不繞過 MOPS 冷卻。

原取得時間不因寫快取續期；暖讀為 HTTP0/cache_hit，native child 與父 aggregate 分開。當年新空列表加上前一年快取活動保持 partial，不算新取得成功或新增父 HTTP。503與 access_denied 保留真實原因，force失敗讓原值失去fresh資格；stale 即使沒有 error_kind 也拒收。暖快取收據／archive 壞值不偷偷重抓；冷讀封存或讀回故障保留已完成的native資料與原時間，清理只限精確key，不丟掉實際工作。

公開 provider cold兩年2 HTTP／warm0、強制更新後正常沿新值、空TTL到期只重查當年、force失敗、壞收據、封存IO、stale及混合計數均經隔離反例驗證。最終20檔同次 runner **286 passed**；獨立覆核最終 **64 passed**、四份runtime SHA相符、無未解重大發現。既有MYSON lost-lease測試的「fresh_until欄位必須不存在」在修正前也failed，改驗沒有value且fresh_until已到期，第二次public呼叫保持拒收及零額外HTTP；shared cache與MYSON runtime本輪未修改。兩次測試有重疊，不加成獨立總數。

正式入口重載後 launcher48116／role-all worker48146／API48148，54份runtime hash、env及158套件皆相符；health／ready200。13原job為done9／error4、61耐久dispatch保留、六佇列與排程空閒，原最後scheduled job在停止前已自然error，未取消或重排。截止129,733列舊零值ledger hash及舊失敗432041保持。

**21:22:39台灣時間**原20類／last_24h仍 **17／20嚴格>80%**：法說75/99＝75.7576%、財報32/66＝48.4848%、近期事件153/204＝75%，goal未完成。法說分母101→99是舊事件滑出24h，不能歸因新cache。沒有觸發正式source-only report refresh；啟動後正常背景radar另外產生兩筆5314營收觀測434477／434478，並非MOPS效果。已觀測股票的新MOPS exact cache key查驗為空，未補種cache或重抓已補齊報告，因此**尚未量測正式活網warm效能，亦未宣稱三個來源取得率已因本修正改善**。

證據：[隔離驗證](evidence/source-acquisition/20261010/mops-conference-reuse-isolated-verification-proof.json)、[獨立覆核](evidence/source-acquisition/20261010/mops-conference-reuse-review-proof.json)、[部署與原工作保留](evidence/source-acquisition/20261010/mops-conference-reuse-release-proof.json)、[原20類及量測限制](evidence/source-acquisition/20261010/mops-conference-reuse-completion-check.json)。

## 再找免費入口：瑞昱完整官網原文及未合格的新頁（2026-10-10）

排除先前已查的聯發科逐字稿、信邦投資人新聞及既有財報原件後，找到瑞昱2379新的[官方新聞列表](https://www.realtek.com/Article/News?lang=en-GB&app_id=18)。從實際首頁href及列表取得[英文原文](https://www.realtek.com/Article/NewsDetail?id=4840&app_id=18&lang=en-GB)，HTTP200／91,464bytes；另取得[中文原文](https://www.realtek.com/Article/NewsDetail?app_id=18&id=4839&lang=zh-TW)，HTTP200／90,058bytes。完整body封存並讀回hash／大小／URL，列表日期與原文直接dateline均為2026-10-08；當期完整TWSE主檔核對2379、瑞昱半導體股份有限公司、統編22671299及www.realtek.com，沿原主檔epoch1791571868.112563，不重新取得或續期。

這是發行人對10月12–16日工博會的預定參展聲明，不能稱已參展或影響／營收已實現；發稿日與未來活動日分開。中英文是同一公告、同一publisher，只列一個合格候選事件，不能灌兩筆或兩個獨立來源。來源仍research-only，尚未實作正式typed provider admission，也未放寬原三發布者／八篇或時間、身分、內容品質門檻。

[官方robots.txt](https://www.realtek.com/robots.txt)完整HTTP200／2,130bytes，明示一般與GPTBot／OAI-SearchBot等AI引擎可讀公開頁，但禁止`/Article/GetAllNewsTitle`等動態端點；本輪沒有讀那些端點或使用登入。這不等同取得商業全文再發布授權。[公開sitemap索引](https://www.realtek.com/sitemap_index.xml)實際列兩份；只再讀[main sitemap](https://www.realtek.com/sitemap_main.xml)，HTTP200／66,240bytes，97個導覽網址及四語新聞列表、沒有NewsDetail逐篇原文。其lastmod為2026-09-07，不能當公告發稿日或完整30日新聞窗口；未抓第二份category sitemap。generic研究helper對XML的HTML初讀有警示，原警示保留，真正URL驗證由stdlib XML ElementTree解析，沒有用HTML猜XML欄位。

另取得[美德MEDICA2026新專頁](https://business.medtecs.com/medica-2026/)完整HTTP200／231,631bytes及其條款原件。頁面只有`og:updated_time=2026-10-09T22:08:54+08:00`，沒有首次刊登時間，活動為11月16–19日；更新日／未來展期不能替代近期發布日，因此近期公告候選0，未啟用。南亞科官方calendar短網址HTTP302，僅沿明示同站Location一次，destination六秒內未完成、curl28／body0，尚無法說原文。日月光投控目前results入口web回403，未再原生重試、換身分或啟用；第三方全文不冒稱發行人稿。

本輪11次有界匿名native請求，9份完整HTTP200正文、1份完整302回應、1次逾時；十份實際原件收據均重讀。資料下載與本機資格驗證不是正式成功次數。首次本機readback用了系統Python3.9，因typing.NotRequired無法import，在任何該命令的網路操作前失敗，改用project interpreter完成；未改runtime或安裝依賴。

**21:41:46台灣時間**重新查驗54份runtime與env hash相符、health／ready200、API48148。source研究基準之後正式來源新增0、1110個現存analysis job數不變，本輪沒有觸發模型或source-only report refresh；截止129,733列舊零值ledger hash及舊失敗432041保持。原20類／last_24h仍 **17／20嚴格>80%**：法說75/99＝75.7576%、財報32/66＝48.4848%、近期事件153/204＝75%。來源候選有新原件進展，全部類別超過80的goal仍未完成。

證據：[初始原頁](evidence/source-acquisition/20261010/additional-issuer-free-entrances-index-native-proof.json)、[列表及英文原文](evidence/source-acquisition/20261010/additional-issuer-free-entrances-detail-native-proof.json)、[中文原文及robots](evidence/source-acquisition/20261010/realtek-new-official-chinese-original-and-robots-native-proof.json)、[sitemap限制](evidence/source-acquisition/20261010/realtek-new-public-sitemap-main-native-proof.json)、[資格重驗與原20類正式驗收](evidence/source-acquisition/20261010/additional-issuer-entrances-source-qualification-and-completion-proof.json)。

## 合格新聞保留容量與原補查門檻一致（2026-10-10）

上一輪有新完整來源及資格證據，屬progress；本輪從原20類／last_24h缺口找出一個可修流程。`FreeNewsWaterfallProvider`已請求最多20筆、完成公司／日期篩選，卻固定只交出5筆，後續仍按原8筆及來源門檻判斷需否補查。讀取28個最新有相關audit的保存報告，信邦20個合格候選只保留5、另15在audit；恆大7只保留5、另2在audit。大部分報告最後已由其他來源湊到8，不以這份盤點重抓全部報告或宣稱新取得。

只有 `backend/data_fetch/enrichment_providers.py` 這一份runtime改動：保留容量改沿原 `SEARCH_CATALYST_MAX_RESULTS`（正式8），原Google/DDG請求候選上限20不增加。現有公司／30日／未來與未知日期／來源多樣性／去重，以及兩個curated feed各至少3、至少3publisher、原8筆的補查條件保持。拒收原件與degraded仍保存；可用只有7就保留7，沒有補值。source容量以外的合格證據仍放 `additional_recent_catalysts`，取得率公式、所有20類、歷史及報告品質gate沒有變更。

先以public provider與public workflow取得8個預期失敗：已有8筆的pool被截5，重複官方3筆後仍多查notice／search／Yahoo；設定容量、7筆不足及拒收案例亦呈相同問題。修正後19檔同次隔離runner **265 passed**，含runtime/storage四項必要組。獨立同次runner **69 passed**（63個repository案例、6個reviewer反例），runtime與兩測試SHA相符、無未解重大發現。重複、單publisher、官方只有2筆／partial／缺失及空新聞仍走原fallback；充分才產生local_block／HTTPFalse／count0，不能灌取得成功。測試階段有重疊，不加成獨立總數。

前次重載後只有這一份runtime新修改；六queue／scheduled均空閒，13原job為done9／error4、61耐久dispatch保留。SIGTERM原worker／launcher，Redis BGSAVE ok，無強制kill或取消。由canonical `start_mac.command`重載後 launcher54850／role-all worker54880／API54882，54份runtime、env及158套件皆核對，health／ready200；截止129,733列舊零值ledger hash及舊失敗432041保持。

另選目前保存報告只有7／8近期證據的1325作**一次來源層活網測試**。使用已部署同SHA的public provider，原Google RSS HTTP200完整回應、0.785秒；14筆候選中7筆通過原公司／日期篩選，實際保留7筆、5個reported publisher，另外7筆仍拒收，狀態 **degraded_enrichment**。這證明新code不再截掉第6、7筆，仍未取得8筆或通過完整報告品質。保存原文是httpx已解碼response.content，明示不是wire bytes；原回應hash／大小已讀回。

此活網測試在維護process執行既有provider，沒有透過正式預設報告workflow，沒有手工登錄SLA成功、source-only report refresh、模型呼叫或新job；1325的HTML／Markdown／snapshot hash完整保持。因此不能將它當自然正式報告流程或整類成功率改善。重載後有一筆正常背景5314營收觀測434479／6筆，另列為background radar，不歸因本新聞修正。

**22:11:40台灣時間**正式原20類／last_24h仍 **17／20嚴格>80%**：法說74/98＝75.5102%、財報32/66＝48.4848%、近期事件153/204＝75%。法說75/99→74/98是舊成功滑出窗口，不能解釋為此新聞patch的效果。所有類別都超過80的goal仍未完成；後續須用自然正式工作驗證保留更多合格資料及減少多餘補查的實際效果，也繼續補真正缺乏的年度科目與法說原件。

證據：[保存報告盤點](evidence/source-acquisition/20261010/free-news-retained-capacity-saved-report-baseline.json)、[scope與測試manifest](evidence/source-acquisition/20261010/free-news-capacity-review-input.json)、[獨立覆核](evidence/source-acquisition/20261010/free-news-capacity-review-proof.json)、[正式runtime與原工作保留](evidence/source-acquisition/20261010/free-news-capacity-release-proof.json)、[單次來源活網與原件](evidence/source-acquisition/20261010/free-news-capacity-one-live-source-probe-proof.json)、[原20類正式驗收](evidence/source-acquisition/20261010/free-news-capacity-completion-check.json)。

## 瑞昱免費新聞入口接入、原件重驗與提示資料界線（2026-10-10）

沿用「每個原始20類在正式last_24h嚴格超過80%」及免費入口限制。上一輪完成合格新聞保留容量修正與單次來源實測，屬實質進展；本輪把先前僅研究的瑞昱2379官網入口接入正式provider，沒有重算分母或改寫歷史。工作區的其他修改保持，runtime doctor確認canonical operational／report index及role-all啟動入口。

`realtek_issuer_news.py`只讀已觀測的[固定公開英文列表](https://www.realtek.com/Article/News?lang=en-GB&app_id=18)，再讀列表實際href所對應的[英文原文](https://www.realtek.com/Article/NewsDetail?id=4840&app_id=18&lang=en-GB)。沿原TWSE完整主檔核對2379.TW、瑞昱、瑞昱半導體股份有限公司、英文簡稱RT、www.realtek.com及統編22671299；不加入全域英文alias。正文的Realtek英文法人由這份原件重建身分。只採英文，同一篇中英文公告不當兩個事件／publisher；不讀robots禁用的動態GetAllNewsTitle／API、不使用登入或token。既有三陽、信邦、台泥、騰輝、SGX停用狀態保持。

列表直接日期、原文直接標題及首個plain發稿段落必須相符；完整正文不截斷。發稿日2026-10-08與未來CIIF展期10/12–16分開，保持issuer_statement／event_assessment=not_assessed及window_complete=False。用既有日期parser按完整now−30日窗口先排除過期候選，避免只按日曆多取邊界文章。傳輸沿原20秒總期限、單次5秒、無重導／重試、TLS、持續冷卻、30分鐘原bytes cache與原取得epoch；400KB列表上限只限新固定入口，原文150KB及其他host上限不變。

完整主檔、列表、原文均先封存、讀回hash／大小／URL／原取得epoch，再由相同parser重播。列表與原文沿實際HTTP200傳輸契約；主檔來源快取保留HTTP0／http_status_observed=False，不宣稱本次TWSE HTTP200。保存receipt改放內部`source_record_archive`欄位，既有prompt投影會在遞迴前排除原件路徑；仍保留完整正文、日期、連結與publisher，不能修改snapshot。原主檔取得時間不能早於其出表日，引用／圖說／帶不明屬性的首段不能充當發稿日。逾20秒的當篇不能採用，前面準時完成的原件仍保留；全部暖讀仍是skipped_fresh_cache／HTTP0，不能當本次新取得。原八筆／三publisher、兩個curated feed各至少三及品質gate保持。

先以原公開入口取得3個預期red，精確30日窗口再1個red。獨立覆核發現超時後採用、主檔時間矛盾及引用日期3項P2，實際修正後重播反例。最後透過public `format_data_for_prompt`取得原件路徑洩入提示資料的1個red，僅調整新adapter的receipt封裝，不改通用prompt runtime。最後19檔隔離回歸**468 passed**；最終獨立同次**114 passed**（107 repository與7 reviewer反例），runtime四份及兩份測試SHA一致、無未解material finding。兩批passed含重疊，不相加當不同測試數。中途fixture納入恰好邊界候選卻未提供該原文、測試預期日期未沿既有UTC正規化、兩次測試檔名拼錯均已更正；不把setup error當行為red。選取DOM fixture不是完整HTTP原件、離線通過也不是正式來源成功。

首次四個runtime檔重載後冷讀一次：**4.026秒／HTTP2／合格1篇／8,178字元**；180筆列表有179筆原窗口過期而排除，僅下載合格當篇。完整列表297,734bytes、原文91,464bytes；當期完整TWSE主檔1,327,573bytes沿原epoch1791571868.112563，沒有重抓或續期。三份原件逐一讀回，原文hash與研究原件一致。之後提示封裝修正再重載，只有這一份adapter是首次重載後新增runtime變動；**0.185秒／HTTP0／同一篇／skipped_fresh_cache**，三份原件epoch及hash完全保持，public prompt無本機原件路徑，snapshot receipt未被投影改寫。冷／暖兩次均在維護process走實際provider，未手工登錄SLA成功。

最終canonical runtime：launcher**64567**、role-all worker**64596**、API**64603**（22:42台北）；55份runtime hash、env及158套件保持，healthz／readyz均200。原13件任務done9／error4及61筆durable dispatch完全保留，六個RQ佇列與scheduled均零；129,733筆原zero ledger和原失敗432041保持。正常SIGTERM終止確認、BGSAVE ok，未force kill、取消或重排。兩次重載各有一筆正常5314月營收背景觀測434480／434481，均6筆，與新新聞入口效果分開；未commit／push。

報告索引沒有2379報告，故沒有製造新報告或已補齊報告重抓來增加觀測：正式source-only report refresh **0**、新報告**0**、模型呼叫**0**。新入口已部署且來源冷／暖讀已驗證，正式預設報告流程的效果仍未驗證。**22:43:30台北正式last_24h仍17／20嚴格超80%**：法說73／97=**75.26%**、財報32／66=**48.48%**、近期153／204=**75%**。法說74／98變73／97是舊成功滑出24小時，不歸因新聞修正；研究／直接來源probe／暖快取不計成新成功。完整目標仍未達成，保持active。

證據：[本輪scope／最終SHA](evidence/source-acquisition/20261010/realtek-issuer-news-review-input.json)、[最終獨立覆核](evidence/source-acquisition/20261010/realtek-issuer-news-prompt-review-proof.json)、[首次正式重載](evidence/source-acquisition/20261010/realtek-issuer-news-release-proof.json)、[最終正式重載與保留驗證](evidence/source-acquisition/20261010/realtek-issuer-news-prompt-release-proof.json)、[單次冷讀與完整原件](evidence/source-acquisition/20261010/realtek-issuer-news-one-live-source-probe-proof.json)、[原件暖讀與public prompt](evidence/source-acquisition/20261010/realtek-issuer-news-warm-source-projection-proof.json)、[原20類最終正式驗收](evidence/source-acquisition/20261010/realtek-issuer-news-final-completion-check.json)。

## 證交所另一個公開財報文件入口與資料缺口（2026-10-10）

上一輪完成瑞昱入口正式接入、冷／暖讀及提示資料界線，屬實質進展。本輪集中最低的財報來源，重讀canonical operational事件及正式last_24h後，失敗分布仍在1623、9103、7740、6672、3023、2206、1325七檔。原provider彙總／快取／SDK列不能直接當看板分母；五年同口徑、必要現金流科目、外國發行人及權限限制仍分開處理，不將缺值補零或把個體／合併混接。[失敗分組原紀錄](evidence/source-acquisition/20261010/twse-doc-financial-entry-failure-baseline.json)。

從[新版MOPS公開財報查詢](https://mops.twse.com.tw/mops/#/web/t57sb01_q1)實際操作公司1623／民國111年，取得新的`doc.twse.com.tw/server-java/t57sb01`公開文件庫網址。該索引明示「111年第四季、IFRSs合併財報、202204_1623_AI1.pdf、1,550,271bytes」，另一列是個體財報，沒有互換。普通匿名TLS取得完整4,520bytes索引；首次誤用UTF8在保存原件後出現解碼錯誤，按HTML宣告以strict Big5離線重讀恢復，沒有再送請求。HTTP200／無重導等native guard在保存原件前已通過，但該次精確取得epoch／完整headers及duration未保存，收據明示retrieved_at=None，不能當新鮮來源或手工登錄正式成功。[完整索引與限制](evidence/source-acquisition/20261010/tewc-1623-doc-2022-file-index-native-proof.json)。

僅沿實際第一個form的POST action與`readfile2`所示欄位：step9／kindA／1623／精確filename，取得HTTP200／491bytes的完整下載頁。再只讀該回應實際href，HTTP200／0.407秒取得完整**1,550,271bytes PDF**，與官方索引大小相符，原件SHA為`d95d03ec61758e47a6d93f0f3c457a52d700e62a001b7aa3388fb68e73470a8a`，與先前官網／Drive版本的binary不同。臨時PDF網址上的20261010時間是下載檔案路徑，不是財年或首次發布日；穩定來源仍為原公開索引與表單。不使用登入、cookie、token、重導、重試或增加8MB傳輸上限。[完整下載頁](evidence/source-acquisition/20261010/tewc-1623-doc-2022-consolidated-native-proof.json)、[完整PDF原件](evidence/source-acquisition/20261010/tewc-1623-doc-2022-pdf-native-proof.json)。

這份新PDF沿既有pypdf6.19.0／512MiB／10秒有界reader仍回parser_warning。只保留第一個警示後立即拒收：`pypdf._encryption: ignore '/Perms' verify failed`；plaintext Encrypt dictionary宣告V5／R5／P2244，copy/extract bit False，Length未確認。沒有保存owner/user password hashes、關閉警示、繞過複製限制、用其他parser或OCR擷取。索引的2022／合併標示已確認，PDF正文公司、期間及財務科目仍未讀取或驗證；完整binary不等於可採用的財務事實，也不能據此啟用來源。[有界警示與權限宣告](evidence/source-acquisition/20261010/tewc-1623-doc-2022-pdf-permission-diagnostic.json)。

另在同一已觀測的公開查詢UI精確查1623／民國110年，沿實際回傳連結取得完整HTTP200／1,003bytes原件，直接顯示「查無所需資料」，沒有年度document row／download link。這只證明此入口此次沒有2021文件，不能推論其他免費入口永遠無原件，也不能把2022檔名或比較值猜成已取得完整2021財報。[2021公開索引](evidence/source-acquisition/20261010/tewc-1623-doc-2021-file-index-native-proof.json)。四次native HTTP各有完整原件讀回；瀏覽器內部請求數未觀測，不混算。qualification初次僅因預期文字「查無資料」與原文「查無所需資料」不同而停止，實際原文核對後完成；沒有追加網路請求。

本輪沒有runtime變動／重載、正式report refresh、模型呼叫或手工SLA寫入；55份已部署runtime、env、原13件job、61筆durable dispatch、129,733筆原zero ledger與失敗432041保持，healthz／readyz200。**23:08:25台北**原20類／last_24h仍**17／20嚴格超80%**：法說73/97=75.26%、財報32/66=48.48%、近期153/204=75%。目標仍active／未完成。本輪新增另一個完整免費財報入口及權限／缺年度證據；該PDF不能補數字或證明五年完整性，後續仍須同年度、同口徑且可合法讀取的另一份原件。[來源資格與原20類正式驗收](evidence/source-acquisition/20261010/twse-doc-financial-entry-qualification-and-completion-proof.json)。

## 股票快照共用入口稽核修正與瑞昱正式 API 驗證（2026-10-10）

延續免費入口與原20類／last_24h嚴格>80%目標。發現預設 `GET /api/stocks/{ticker}/snapshot` 直接呼叫 workflow，繞過 `StockDataService._build_result` 的 canonical source audit 與 fetch correlation。只修改 `api_routes/stock_snapshot.py`：透過原 `fetch_stock_data_async` 取 `.data` 再由原 consumer builder 回傳。注入依賴、正常免費 provider plan、force=False、skip_optional_http=False及HTTP200／502保持；route不手工寫SLA，不建立報告、job或模型呼叫，也不切換快取。configured ApiRuntime Redis與 provider facade 的實際SQLite cache分開，未遷移／清除／補種。

三項public API行為先因無source event而red；修正後13檔同次隔離runner **151 passed**，含必要runtime/storage組。獨立同次 **83 passed**（78repository及5 reviewer反例），runtime／test SHA符合manifest、無未解重大發現。成功與失敗保存原狀態一次、正常快取仍skipped_fresh_cache／零新取得，重複GET各有新fetch ID但不續期原epoch，例外／取消會清理scope，注入依賴契約保持。首次green的fixture未接受workflow registry參數，修正fixture後重跑；不將setup錯誤當新runtime問題。兩批數有重疊，不相加成不同測試總數。

六queue／scheduled空閒、其他55份已部署runtime均相符後，正常SIGTERM原worker／launcher，BGSAVE ok，無force kill、取消或重排。canonical `start_mac.command` 重載後 launcher**76257**／role-all worker**76285**／API**76287**，56份runtime與env、158套件保持，healthz／readyz200。原13件job為done9／error4、61筆耐久dispatch、129,733筆原零值ledger prefix與原失敗432041保持。重載後正常5314月營收背景觀測434482為6筆，與後面的API案例分開。

2379沒有既有報告或 `financial_data:2379.TW` 整份cache，因此只送**一次正式預設GET**，沒有force、client retry或已補齊報告重抓。**23:37:32台北開始，20.803秒回HTTP200**；正式同一fetch ID `330ce272f2f548ccb9dd01b9f3ae5ab2` 有61筆SLA，其中18筆lower-level觀測及一次43筆canonical batch逐列匹配payload。它們不是61次新成功；按原取得率分類，法說新增1／1、財報1／1、近期來源5／6。61筆API usage都是Data Provider、實際model_id皆空；新model／analysis job／報告／quality gate均0，沒有手工source audit寫入。

新瑞昱入口沿原冷卻／期限發出2次HTTP，取得完整英文原文**8,178字元**，並進入正式recent_catalysts。完整主檔1,327,573bytes／列表297,734bytes／原文91,464bytes讀回hash與原parser重播通過；主檔保留epoch1791571868.112563，新列表／文章epoch在本次API期間。單一英文公告、issuer_statement、event_assessment=not_assessed、window_complete=False保持，不把未來10/12–16展期當已發生。MOPS年度provider回2021–25五年同口徑合併TWD資料、各9個原始科目及FCF關係成立，2022比較值修訂紀錄保持；legacy adapter只保存文件URL／SHA及解析fact，本次未具備五份完整bytes重讀，不宣稱獨立原件重播。法說仍是2026-09-15活動metadata，transcript_available=False、excerpt空；近期整體仍degraded及品質警示，HTTP200並不等於報告品質gate通過。

保存的完整snapshot經 `format_data_for_prompt` 本機查驗，瑞昱單一record的內部原件路徑確實排除，snapshot未變動；但整份snapshot其他provider診斷仍有9次 `raw_response_path`／archive path。該完整投影assertion保留為實際新發現，不換成全系統已通過；此route-only部署未修改其他provider提示界線。可沿本次保存資料離線重現，不需再抓2379。沒有因發現改寫source ledger或放寬品質gate。

**23:42:47台北**正式原20類仍**17／20嚴格>80%**：法說74／98=**75.51%**、財報33／67=**49.25%**、近期158／210=**75.24%**。相較本輪preflight，三類新增觀測由這一次API可追溯；仍無法宣稱全部達標或報告品質完成。goal保持active；剩餘來源缺口與完整prompt診斷原件路徑需繼續處理。未commit／push。

證據：[scope與root測試](evidence/source-acquisition/20261010/stock-snapshot-acquisition-audit-review-input.json)、[獨立覆核](evidence/source-acquisition/20261010/stock-snapshot-acquisition-audit-review-proof.json)、[正式重載及保留](evidence/source-acquisition/20261010/stock-snapshot-acquisition-audit-release-proof.json)、[唯一正式API請求](evidence/source-acquisition/20261010/stock-snapshot-acquisition-audit-one-live-api-proof.json)、[原件重驗及品質限制](evidence/source-acquisition/20261010/stock-snapshot-acquisition-audit-live-source-qualification-proof.json)、[原20類正式驗收](evidence/source-acquisition/20261010/stock-snapshot-acquisition-audit-completion-check.json)。

## 三陽當期官網目錄重驗與未揭露科目（2026-10-10）

上一goal turn已部署股票快照共用入口並完成2379一次正式取得，屬progress。本輪先重讀canonical runtime doctor／原20類與今天financial失敗，維持原免費限制、五年／同口徑／必要現金流科目與品質gate。公開搜尋未找到新的合格科目；不把其他公司恆大、季度三陽報表或個體報表混進目標合併年度。

沿三陽實際首頁href，分別有界普通匿名TLS取得首頁、`/revenue`及`/financialreport`完整HTTP200 HTML，47,625／29,147／34,182bytes，三次native請求、無重導或重試。完整原件archive讀回相同。native確認網站仍可用；web工具先前首頁讀取timeout不是native HTTP拒絕，未用另一身分／token。Web搜尋及讀取的內部請求數未觀測，不混為三次native。

最新目錄2022行的「第四季合併」精確指向今天10:28已保存的同一2022／2021合併PDF；不是新入口或新財務原件，因此沒有再下載。僅本機解壓原6,263,827bytes PDF、核對原URL／SHA與原epoch1791599320.625849；原先12／13實體頁視覺核對的2021／2022明列CFO與設備購置，gross intangible purchase均未揭露。沒有把null／缺列變0、用無形資產餘額或比較變動替代支出，新增合格科目與五年series均0。既有2206正式失敗431243保持「annual XBRL facts are incomplete for2021」。

本輪沒有新增可採用資料，分類為 **no progress**；不是verified wait，也不以三份新取得HTML或重述狀態充作資料改善。這是上一progress後第一個連續no-progress turn，blocked audit尚未達三turn；goal仍active，未complete／blocked。這項當期原件缺口已確認，但不宣稱世界上所有免費入口均已耗盡。

**23:52:20台北**正式last_24h原20類仍**17／20嚴格>80%**：法說74／98=75.51%、財報33／67=49.25%、近期158／210=75.24%。上一輪正式source cutoff之後新增0，模型／analysis job／報告0；本輪runtime變動／重載0、56份已部署SHA與env符合，healthz／readyz200，原13件job、61dispatch、129,733列zero prefix及原失敗432041保持。未修改取得率口徑、分類、歷史或品質gate，也未做無法改善原件缺口的程式patch。

證據：[首頁完整原件](evidence/source-acquisition/20261010/sanyang-new-financial-home-native-proof.json)、[實際財務導覽](evidence/source-acquisition/20261010/sanyang-new-financial-index-native-proof.json)、[當期財報目錄](evidence/source-acquisition/20261010/sanyang-new-financial-report-catalog-native-proof.json)、[原PDF／正式紀錄／原20類重驗](evidence/source-acquisition/20261010/sanyang-current-disclosure-gap-and-formal-goal-check.json)。

## 現存報告財報缺口盤點與台郡實際修復（2026-10-11）

上一goal turn重驗三陽原件未補到新科目，分類no progress。本輪不繼續重抓同一缺列PDF，改以canonical reports index及ReportArtifactLocator讀901份索引中的155檔最新快照，全部可讀。原先只盤今天已被觀測的股票，漏掉現存尚未修復報告；這份全量盤點找到台郡2313及南亞1303仍有舊ConnectError造成的financial critical failure。1560原先已是2021必要科目不足，本輪不重試。沒有以資料單純過期挑已補齊報告。

初掃111筆為篩選訊號，不是111個已確認同類故障或可修復工作：ETF／未知工具類型與金融業FCF語意須另外處理。後續只用缺年度數或明示financial critical failure篩選，金融業FCF null不能直接判錯。修復後仍79筆訊號，其中54份有明示EQUITY、25份工具類型unknown；unknown含0050，未用代號猜ETF，也不得直接依這份名單批次刷新。原分類與provider gate保持。[初掃](evidence/source-acquisition/20261010/current-latest-report-financial-backlog-inventory.json)、[校正後候選與限制](evidence/source-acquisition/20261010/qualified-latest-report-annual-history-backlog-after-two-refresh.json)。

兩份確有critical／原ConnectError的最新報告各送一次既有正式 `POST /api/report/{filename}/refresh/data`，一般client-config mutation能力沿原授權，未輸出token、改安全設定、重試或重排。2313在10/10 23:59:50台北開始、10/11 00:00:20回HTTP200／**30.117秒**；1303再一次HTTP200／**36.496秒**。兩次為實際缺資料報告的正常full data-only refresh，不是source-only、研究probe或反覆刷healthy report，沒有手工SLA寫入。[兩次唯一請求及保存查驗](evidence/source-acquisition/20261010/confirmed-financial-backlog-two-formal-refresh-proof.json)。

台郡由2022–25四年補為**2021–25五年官方合併TWD資料**，每年九項必要fact、CFO＋PPE現金支出＋無形資產現金支出與保存FCF逐項匹配；原financial critical failure解除，data trust **fresh／91**。原件URL／SHA／issuer／year／scope／currency沿現行native parser admission保存；legacy adapter沒有完整原始bytes封存，本次未獨立重播五份原件，不宣稱該部分已驗。南亞連線已恢復，但真正解析後仍 `annual XBRL facts are incomplete for2021`，原2021FCF null保留、data trust partial／56、financial critical failure保持；HTTP200不等於財報完整或報告品質通過，這項新揭露缺口加入後續避免反覆重抓名單。

兩份原HTML／Markdown／analysis_evidence及五份quality gate metadata逐項不變，snapshot／HTML／Markdown／data file與canonical index hash讀回相符。資料更新依原規則標 `analysis_text_stale=1`／`needs_rerun`，未執行模型重分析或重新評分quality gate。原13job／61durable dispatch／129,733筆zero ledger prefix及432041原失敗保留，runtime變動／重載0，56份已部署runtime與env相符、healthz／readyz200、六queue與scheduled空閒。兩次實際來源觀測113筆及Data Provider usage113筆按同一fetch IDs查驗，實際model_id皆空；不是113次HTTP或113個成功。新增模型／analysis job／報告／quality gate均0。

**10/11 00:06:51台北**正式原20類／last_24h仍**17／20嚴格>80%**：法說76／100=**76%**、財報34／71=**47.89%**、近期166／220=**75.45%**。台郡新增一個真實完整取得，南亞的error與兩個degraded財報觀測均如實納入，因此財報整類比例沒有因修好一份就達標。保持原公式、分類、歷史與品質門檻；本輪是新全量盤點改變下一步且完成一份實際修復，分類progress，上一no-progress連續審計中斷，goal仍active／未完成。

後續先對EQUITY缺年度候選逐一核對來源與既有缺口，不能把79訊號全當可恢復或為門檻製造工作。若以指定財報元件刷新降低其他已具備來源的額外HTTP，必須先驗證年度／幣別／scope、歷史派生值、舊股價時間、本文與品質憑據保持的完整merge契約，再接正式服務；不以未實作計畫冒稱改善。

證據：[原20類、原件限制、報告保留及正式結果](evidence/source-acquisition/20261010/confirmed-financial-backlog-completion-check-20261011.json)。


## 指定官方年度財報刷新與新士電官網入口（2026-10-11）

沿原20類／last_24h嚴格>80%及僅免費來源目標，新增既有 `POST /api/report/{filename}/refresh/data?source=financial_statements`。`StockDataService.fetch_source_async` 只執行原MOPS年度取得器；一般產業與既有支援金融業schema分別核對公司、台股EQUITY／TWD context、五個連續年度、合併／明示standalone口徑、九項必要科目、文件URL／SHA及原native audit。成功與失敗先經canonical audit一次；完整五年才合併，錯誤或未驗來源不覆蓋原報告。不呼叫quote、SDK、FinMind、optional來源或模型，不改既有冷卻／negative gap cache及原品質門檻。

年度歷史與margin／ROE／CAGR／成長率／年度杜邦派生值共同更新；股價、TTM純量、其他來源與原audit保留。原financial audit內部封存；既有可見notes首位保存保留TTM的原財務來源最早可核對時間及原標記，明示此觀測並不證明每個純量來源完整、本次年度時間不適用TTM，compact及重複刷新仍可見。超大舊TTM不能使補件崩潰：safe finite comparison及原 `financial_tool_utils.safe_float` 拒絕overflow，保留原scalar、比較值N/A；無效的舊degraded時間僅標未確認，不續期。原HTML／Markdown、analysis_evidence及五份quality metadata不改，分析本文仍按原規則needs_rerun；shared financial cache及default stock完整資料未宣稱修復。

Public behavior先red，再完成5份runtime範圍。Root最終同次隔離 **208 passed**（含必要runtime/storage組）；獨立同次 **192 passed**，含原7及新增1個反例，5份runtime及tests／fixture SHA符合manifest，無未解material。反例涵蓋重複空值issuer參數、矛盾HTTP／calendar時間、金融業明示USD、超大舊TTM、被新年度時間掩蓋的舊TTM，以及無效舊degraded epoch。Legacy缺HTTP診斷仍為unknown，不假補HTTP200；兩批有重疊，不相加成不同測試總數。初次額外test command拼錯不存在檔名未執行tests，已用實際檔名完成上述green；不把setup失敗當已驗。

六queue／scheduled空閒時正常SIGTERM worker／launcher，BGSAVE ok，無force kill／取消／重排。10/11約00:59台北沿canonical `start_mac.command` 正式重載，launcher **93387**／role-all worker **93415**／API **93417**；5份owned＋54份preserved共59份runtime、env及158套件相符，healthz／readyz200。原13件job、61筆durable dispatch、129,756筆重載前zero ledger prefix與432041原失敗完整保留；無commit／push。

只挑仍缺2021年度、明示EQUITY且台幣口徑可核對的最新報告，各送一次指定財報刷新：**鴻海2317／14.675秒及遠東新1402／14.077秒HTTP200**，2022–25四年補為2021–25五年官方合併TWD資料；每年原科目／FCF關係與保存series一致。其他來源、quote／TTM值、原market時間、原本文與五份quality metadata及canonical index hash逐項確認。舊股價與optional資料仍過期，因此新snapshot trust為stale／34，不把年度補齊稱為全報告資料新鮮或品質gate重新通過。**士林電機1503／5.913秒HTTP502**，原報告三份artifact byte/hash保持；actual MOPS FilingError為2021科目不足，原negative-gap receipt讀回明確缺 `PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities`，不補零。失敗前原snapshot內fresh／91屬原生成時儲存metadata，未重評，不能當今日報價新鮮的證據。

三次請求恰有三筆canonical financial source events：兩筆success5與一筆error0，fetch IDs逐一匹配；Data Provider usage3筆、model0、新analysis job／報告／quality gate0，無其他來源請求及手工SLA寫入。相同本輪preflight→01:02:42台北，財報 **32/69=46.38%→34/72=47.22%**；法說 **74/96=77.08%**、近期 **158/212=74.53%**，仍 **17/20嚴格>80%／goal active**。先前00:06觀測與本輪preflight差異為24h窗口舊紀錄滑出，不歸因本patch。901報告／155檔最新快照重讀後，原79篩選訊號降77（52 EQUITY／25 unknown）；不是77個已確認可修復項目，unknown須另核對，1503新增已確認缺科目名單，禁止依訊號直接自動批次刷新。

口頭進度曾將1503誤寫為東元，已立即更正：1503實際是士林電機，正式請求與native issuer驗證始終是1503；東元1504搜尋結果未用於來源或報告。另找到[士林電機官方財報列表](https://cht.seec.com.tw/Content/IRFinQ/List.aspx?MmmID=707067512341436617&SiteID=10)，當期完整TWSE主檔核對1503／士電／士林電機廠股份有限公司／統編11039306與www.seec.com.tw。沿原有界普通TLS、無登入／cookie／重導／重試與persistent cooldown，研究取得HTTP200完整157,547bytes HTML並封存，原列表確有2021及2022第四季合併報表及精確下載href。主檔沿原epoch1791571868.112563，不重抓或續期。2021下載首讀因unexpected_content_type被原guard拒收；明示HEAD實測HTTP200／application/save-as後，只有/tmp研究adapter對同一已觀測固定連結接受此類型，仍要求PDF magic及原8MB／無重導重試／冷卻／十秒512MiB有界reader，正式transport與guard未改。完整2021 PDF **3,431,632bytes／95頁／81,621字元**及2022 PDF **2,420,176bytes／97頁／122,125字元**均封存讀回原hash並沿同一pypdf6.19.0完整重播。首頁公司1503／全名／合併年度及現金流表台幣仟元核對；兩份第15頁的2021 CFO **2,299,153仟元**與PPE現金支出 **(718,535)仟元**均與native MOPS facts相符，但投資活動表沒有B04500／無形資產購置單列，不能將其他非流動資產淨額或無列推成gross零值，不計算完整FCF。native coverage complete只代表啟發式沒有空頁或明顯亂碼，不是所有文字／數字或財務事實已證真。源頭新入口原件已完整取得，但必要科目仍未補到，source維持OFF；研究共5次native HTTP（index GET1、2021首次格式拒收GET1、HEAD1、格式核對後2021 GET1、2022 GET1），browser內部HTTP數未觀測，不計入正式SLA成功。Legacy MOPS財報仍只有URL／SHA／解析fact，本輪沒有其五份完整HTTP bytes獨立重播。

證據：[範圍與root](evidence/source-acquisition/20261011/annual-financial-source-review-input.json)、[獨立覆核](evidence/source-acquisition/20261011/annual-financial-source-independent-review.json)、[正式重載與保留](evidence/source-acquisition/20261011/annual-financial-source-release-proof.json)、[三次正式結果與原20類](evidence/source-acquisition/20261011/annual-financial-source-completion-check.json)、[更新缺口名單](evidence/source-acquisition/20261011/qualified-latest-report-annual-history-backlog-after-source-only-refresh.json)、[士電官方完整索引](evidence/source-acquisition/20261011/shihlin1503-official-financial-index-research-proof.json)、[首次PDF拒收](evidence/source-acquisition/20261011/shihlin1503-2021-consolidated-pdf-research-proof.json)。完整prompt內其他provider診斷的archive path仍是既有待處理項，未宣稱本輪修復。


本輪最後 **01:15:48台北** 重讀正式原20類仍 **17/20嚴格>80%**：法說74/96=**77.08%**、財報33/71=**46.48%**、近期155/208=**74.52%**。相較01:02驗收，ledger沒有新增、刪除或改寫：financial一筆舊成功及近期四筆舊觀測滑出24h窗口；研究未增加任何SLA／API usage／model／analysis job。59份runtime、env、服務PID保持且healthz／readyz200。goal active／未完成，本輪兩份真實五年資料修復及完整士電新入口均屬progress；不宣稱找到已可補滿科目的來源或所有免費入口均已窮盡。其他provider完整prompt的原件路徑問題仍未修，本次不放寬report品質gate。

最終新入口資格與原20類：[完整讀回、數值口徑、尚缺科目及正式驗收](evidence/source-acquisition/20261011/shihlin1503-official-financial-entry-qualification-and-final-goal-check.json)、[實測HEAD](evidence/source-acquisition/20261011/shihlin1503-2021-pdf-header-diagnostic.json)、[2021完整PDF](evidence/source-acquisition/20261011/shihlin1503-2021-save-as-pdf-research-proof.json)、[2022完整PDF](evidence/source-acquisition/20261011/shihlin1503-2022-save-as-pdf-research-proof.json)。


## 既有空白快照的年度財報與法說單來源補件（2026-10-11）

只納入現存最新快照中的明示缺口、已確認EQUITY／原幣別與原核心時間。國泰金2882、富邦金2881、強茂2481、神達3706及聯強2347各一次正式 `source=financial_statements`，取得2021–25同口徑TWD年度資料；股價、TTM純量、原可見時間、其他來源、本文、analysis_evidence及五項品質metadata保持，索引／artifact hash一致，分析結論仍標needs_rerun。富邦金舊raw資料雖含五年，但原ticker／report_scope／文件口徑憑據不足，沒有僅補註記便當成合格資料。大聯大3702單次502明示2021 XBRL科目不完整；原artifact保持，零值失敗留存，下輪未有新原件前不再重試。原77筆財報訊號是盤點而非自動批准。

另一盤點讀155份最新快照，57份法說空值訊號中，17份具明示EQUITY及原核心時間；39份股別未知與9103已知空來源排除。對8201、2408、2254、6902、2892、2492、3055、1709、8996、4956、3711、2468、2449、3094、7799、6715、6226各一次正式 `source=earnings_call`，17份均保存MOPS實際活動日期／標題／摘要或材料連結。4956、2468、6226當年度空回應後沿原下一年度退路取到資料，三筆empty如實保留；parent aggregate不是另一筆成功。所有 `transcript_available=False` 保持，未把資料連結當已讀簡報或逐字稿，本文與品質gate未重跑。

共23次正式單來源請求，5份五年財報與17份空法說context補件；43筆來源觀測逐一對應43筆Data Provider usage，actual model_id皆空。新模型、analysis job、報告、品質審核均0；原13件job、61筆durable dispatch、原129,756筆zero-ledger prefix及失敗432041保持，healthz／readyz200。這階段使用00:59:52已部署年度來源runtime，沒有再重載或更新shared整份股票cache。

**01:52:47台北**正式原20類／last_24h仍17／20嚴格>80%：法說91／116=78.45%、財報38／77=49.35%、近期155／208=74.52%。補件有實際進展，但原完整目標及報告品質仍未完成；不改分母、歷史失敗、分類或品質門檻。

證據：[財報六案事前資格](evidence/source-acquisition/20261011/annual-source-next-six-qualified-requests-plan.json)、[法說空值盤點與排除](evidence/source-acquisition/20261011/earnings-source-empty-report-qualified-inventory.json)、[23案正式完成與保留查驗](evidence/source-acquisition/20261011/six-financial-and17-earnings-formal-completion-proof.json)、[原20類正式取得率](evidence/source-acquisition/20261011/six-financial-and17-earnings-after-formal-sla.json)。


## ISIN免費股別入口、創新板與擴充字元，以及現存資料補件（2026-10-11）

新增證交所公開[ISIN單一證券查詢](https://isin.twse.com.tw/isin/single_main.jsp?owncode=6669&stockname=)，不需資料訂閱、登入或金鑰。只有原快照股別unknown才以 `source=instrument_identity` 讀固定匿名入口；完整原件嚴格解碼、十欄表與唯一同代碼列、ISIN檢查碼，以及精確市場／證券別／CFI三元組均成立才採用。股票另與完整當期TWSE公司主檔的同代碼、簡稱、全名及原出表日核對；0050採表內ETF／CEOGEU，未從代碼前綴猜股票或基金。保留quote_type、company_identity、其他開放資料、原取得時間、股價／TTM純量、本文與五項品質metadata，只有股別資訊及其憑據新增，分析仍needs_rerun。此入口只接既有報告的指定來源刷新，沒有宣稱預設完整股票workflow已接上。

獨立覆核先找出五項public反例：舊法人全名衝突、非raw原件種類、畸形矛盾同代碼列、最後封存越過十五秒期限、重試暖快取抹去首次HTTP失敗。逐項修正後root120／獨立83隔離通過；解析及原件錯誤不可重試，global重試策略與看板公式不變。正式部署後晶技3042原報告無analysis_evidence，既有刷新規則補建legacy_hash_verified packet，首次驗證腳本因要求欄位完全相同而停止。從同一保存原快照重讀確認packet只引用原分析hash，未包含新股別；本文／gate保持，原exception留存，沒有重送資料請求。相關既有legacy保留測試另31項通過。

兩份首次正式原件揭露新差異：6924榮惠-KY創的市場別為上市臺灣創新板、證券別創新板、CFI為ESVUFR；2353宏碁的碁字包含CP950擴充bytes。保留兩筆正式失敗及原report，從同一完整HTTP原件、原epoch、當期主檔離線查驗；沒有加HTTP、改別名或改市場。僅增加上述精確三元組，以及Big5 strict解碼失敗時的strict CP950退路；既有Big5收據政策不變，非法bytes不替換。Python列出[CP950繁體中文codec](https://docs.python.org/3/library/codecs.html#standard-encodings)，瀏覽器[Big5規格包含常見擴充](https://encoding.spec.whatwg.org/#index-big5)，實際接受仍逐份依保存原件與主檔核對，不宣稱CP950等同整套瀏覽器編碼。兩項public positive先red，root127／獨立93隔離通過，原30份已保存收據重播不變。

兩次正常重載都先確認六queue空閒及13件舊job／61筆durable dispatch，正常SIGTERM／BGSAVE，不force kill、取消、重排或裝新套件。最後launcher15475／role-all worker15503／API15505；63份runtime與env、158套件保持，healthz／readyz200。二次停止worker初次20秒觀測未terminal，後續同一process自然結束才停止API，沒有另送force kill或重啟第二份worker。

37份原股別未知的上市快照已正式核對為36股票／1ETF；兩份原拒收快照各只在新行為部署後補驗一次，沿原raw暖快取／原epoch，HTTP0與fresh_cache分類保持，未變成新取得。再只對原earnings_call空值且保存EQUITY的36份各一次正式補取，全數保存活動metadata、摘要／材料連結；transcript_available=False保持。原17份已補案不重抓，ETF不抓公司法說或財報，8069.TWO／3105.TWO仍未確認股別。另22份明示四年／TWD／原核心時間的財報缺口，各一次取得；11份補成2021–25五年，11份因必要科目、少於五份申報、比較期衝突或HTTP200非XBRL頁拒收，原report保持，不補零或換成成功。這些拒收需不同原件或已修正行為才再次採用，不能一律當成永久無資料。

股別階段共97次正式單來源請求：39股別、36法說、22財報。139筆source ledger逐一對應139筆Data Provider usage及fetch ID；新模型、analysis job、報告或品質gate均0，1110筆原analysis jobs／901筆reports、原13件job／61筆dispatch、129,767筆zero-ledger prefix及失敗432041保持。37份最終artifact／index hash、原本文、gate、quote／TTM純量與原分析身分保留政策皆重讀核對。加上本輪較早六財報／17法說階段，合計補成16份五年財報、53份法說空context；不把139筆觀測算成139次成功。

最後重驗時，主檔原取得時間自然跨過24小時，36份股票收據的「當前fresh」驗證回False。完整bytes／hash／URL／同parser仍一致，各份原正式接受時都在原24小時限內；這兩種驗證分開記錄，沒有調clock、修改epoch／TTL、重抓健康報告或把現在失效的fresh判斷改True。0050不需公司主檔，仍通過當前驗證。這項限制作為下一次新來源採用的freshness guard保留，歷史取得成功與原失敗不改寫。

**02:58:19台北**正式原20類／last_24h已18／20嚴格>80%；法說127／155=81.94%，財報48／95=50.53%，近期149／200=74.50%。相較較早80.38%與財報分母98，差異有舊觀測自然滑出窗口，未歸因額外來源呼叫。補充資料先因成功滑出降至32／40=恰好80%，最後舊失敗滑出後恢復嚴格超80%，不是補抓健康來源。完整目標仍active／未完成，原本文仍需重新分析，沒有新報告品質通過宣稱。當前財報盤點剩60筆適用訊號（58EQUITY／2unknown），訊號不等於自動批准，免費完整原件與比較期／金融業科目仍需追查。

證據：[初次scope與原件](evidence/source-acquisition/20261011/security-identity-source-review-input.json)、[初次覆核](evidence/source-acquisition/20261011/security-identity-source-independent-review.json)、[初次正式部署](evidence/source-acquisition/20261011/security-identity-source-release-proof.json)、[兩種原生差異的同原件資格](evidence/source-acquisition/20261011/security-identity-native-variants-offline-qualification.json)、[新修正scope](evidence/source-acquisition/20261011/security-identity-native-variants-review-input.json)、[最終覆核](evidence/source-acquisition/20261011/security-identity-native-variants-independent-review.json)、[最終正式部署](evidence/source-acquisition/20261011/security-identity-native-variants-release-proof.json)、[全部正式補件與限制](evidence/source-acquisition/20261011/security-identity-formal-completion-proof.json)、[最終原20類看板](evidence/source-acquisition/20261011/security-identity-final-formal-sla.json)、[剩餘財報訊號與拒收原因](evidence/source-acquisition/20261011/financial-backlog-after-security-identity-repairs.json)。

## 銀行 BASI 五年財報與上海商銀完整免費 PDF 入口（2026-10-11）

沿原 20 類／last_24h 嚴格 >80% 與僅免費來源目標，本輪從原失敗臺企銀 2834 找到六份實際原件：MOPS index 與 2021–2025 五份完整年度 iXBRL。銀行的利息淨收益、手續費淨收益、淨收益使用 BASI 科目，舊金融業解析器僅認 FH 金控科目，造成 2021 必要科目不足。三個實際 BASI tag 保留原名、原 issuer／calendar period／TWD／千元 scale／sign／scope／duplicate 與完整五年 gate；不以淨收益代填一般產業 Revenue、GrossProfit 或 OperatingIncome，不將缺值填零。

新增獨立 `bank_consolidated.v1`，完整五份 decoded HTTP body 封存與重讀、parse／reconciliation 重播符合才投影。獨立覆核初次找到兩組真實 P2：錯型 ticker／archive 會拋 AttributeError；移除 taxonomy／archive 會退回金控格式並誤標 FH 科目。先保存 public red，再修正型別 admission 與獨立 schema，年度補件、SDK、prompt／state、金額核對、CAGR／年度杜邦、DCF 排除共同接入。Root 同次 **234 passed**，修正後獨立同次 **344 passed、1 optional skipped**，包含原九個未修改反例；10 個 runtime 與測試／fixture SHA 相符、無未解 material。兩批有重疊，不相加成不同測試總數。

六 queue／scheduled 空閒時正常 SIGTERM worker／launcher、BGSAVE，再沿 `PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 ./start_mac.command` 重載。當前 launcher **29065**／role-all worker **29093**／API **29095**，69 個 guarded runtime SHA（本輪 owned10、preserved59）、env、158 個套件保持，healthz／readyz200。原 13 件 job、61 durable dispatch、129,780 筆 zero-ledger prefix與失敗432041 保留；未強制 kill 或重新安排工作。

四份確有缺年度／先前 failure 的最新快照各送一次正式 `source=financial_statements`，不是反覆刷新 healthy report：

| 股票 | 正式結果 | 用時 | 保留或修復範圍 |
| --- | --- | --- | --- |
| 2834 臺企銀 | HTTP200、五年補齊 | 3.734秒 | BASI bank 原件與投影重播通過 |
| 5876 上海商銀 | HTTP200、五年補齊 | 3.879秒 | BASI bank 原件與投影重播通過 |
| 2845 遠東銀 | HTTP502、原快照保持 | 3.755秒 | 新揭露 `conflicting incomplete financial-institution comparative for 2021`，不重試或混用不完整比較數 |
| 2880 華南金 | HTTP200、五年補齊 | 3.798秒 | legacy FH 金控原 structural contract；未聲稱五份完整原始 bytes 已獨立重播 |

三份成功的 quote／TTM／原取得時間、其他來源、HTML／Markdown、analysis_evidence及五份quality metadata不變，canonical index hashes讀回相符，仍 `analysis_text_stale=1`／需重分析。失敗的三份artifact與原snapshot完整不變。新增 canonical financial 觀測4（成功3、error1）與 Data Provider usage4，實際 model_id皆空；analysis job／報告／quality review均0，現有1110 jobs／901報告保持。資料補件不代表舊分析或品質警示已解除。

另找到 **上海商銀官網 2021–2025 五年合併財報 PDF 免費入口**。直接匿名普通 TLS 讀實際目錄 href，五份完整原件均取得並以原 bytes／SHA／來源URL／取得epoch讀回；封面公司、股票代碼5876、合併口徑與110–114年度相符。2021–2025 sizes分別 **5,521,342／2,792,680／6,590,612／2,990,071／20,050,418 bytes**。2021 共130頁，掃描財務表的 pypdf 文字抽取為空；渲染實體頁8、9、10、13、14、15核對，七項 Bank income／CFO／PPE／無形資產支出樣本與正式保存2021原科目數值全部一致。這是抽樣，不是十科目完整年度或五年財務 parser 驗證。

2025 第一次因8MB body上限停止，第二次一般HTTP200 header確認20,050,418 bytes超過20MB研究界線並未讀全body；兩次拒收紀錄保留。依實際已知大小另以21MB／30秒研究 bound取完整原件，使用獨立 `research_complete_original.v1_not_canonical_source_receipt` gzip封存、checksum與byte讀回。**沒有改正常8MiB封存 gate、source input大小、重試／cooldown或快取期限，也沒有將大PDF研究收據送入正式投影。** 上海商銀 native 共8 attempts（catalog1、PDF7，含兩次大小拒收），不是8個成功。自動掃描表格解析、跨年度 comparative與大型原件 provider契約尚未實作，因此新PDF入口仍 source OFF／SLA0。

遠東銀行的官網目錄與實際英文2022合併PDF href在 web 資料可查，但 native 對 `www.feib.com.tw` 與 `clbankw.feib.com.tw` 各一次都在 TLS certificate verify 報 Missing Subject Key Identifier 失敗；沒有關掉驗證、加cookie/token或重試，不能宣稱 native入口已可用。Web工具內部請求數未觀測，不混進 native request count。整輪研究 native16 attempts，含2次TLS失敗、2次大小停止，12份完整原件；研究沒有 canonical SLA／usage／模型觀測。

**03:47台北**正式 original20／last_24h仍 **18／20 嚴格>80%**：財報 **51／96=53.125%**、近期事件 **147／196=75%**。相較03:04的48／95，財報實際新增3成功／1失敗；分母另外有3個舊失敗自然離開滾動窗口。近期事件本輪沒有新取得，數值變化來自窗口，不能歸功於本輪程式。原公式、類別與歷史保持；goal未達成。本輪有新原件、具體 parser 修正與三份正式修復，屬 **progress**，無連續 blocked condition；goal保持active，未complete／blocked。未commit／push。

證據：[五份銀行native原件](evidence/source-acquisition/20261011/bank-2834-five-originals-native-qualification.json)、[scope／public red／234 root](evidence/source-acquisition/20261011/bank-taxonomy-review-input.json)、[344獨立覆核與初次P2](evidence/source-acquisition/20261011/bank-taxonomy-independent-review.json)、[正式重載](evidence/source-acquisition/20261011/bank-taxonomy-release-proof.json)、[四份正式補件／保存／原20類驗收](evidence/source-acquisition/20261011/bank-taxonomy-formal-completion-proof.json)、[最新正式看板](evidence/source-acquisition/20261011/bank-taxonomy-final-formal-sla.json)、[上海商銀五份完整替代原件入口](evidence/source-acquisition/20261011/scsb-five-complete-free-entry-availability-proof.json)、[2021實體頁抽樣](evidence/source-acquisition/20261011/scsb-2021-native-original-visual-qualification.json)、[遠東銀行native入口限制](evidence/source-acquisition/20261011/feib-2022-comparative-free-original-native-research.json)。


## 2026-10-11 近期搜尋指定補件與正式四件驗證

全155檔最新快照可讀；以公司／三十天／原八筆及來源多樣性篩選，77檔目前不足。此數是待核對候選，不能把每檔都稱為原本有實質缺口或可成功修復。京元電子2449、宏碁2353、陽明2609、大同2371另以備份bytes SHA及原搜尋／結論時間重播，當時與目前均未通過原門檻（原可用3、3、0、0筆），才各執行一次正式補件。

新 `source=recent_catalysts` 經既有 StockDataService 與 Alternative Search，僅採原設定已啟用的匿名 google_news_rss／gdelt／yahoo_rss 子集；不啟用 disabled、不改原一般workflow。來源 receipt 在 canonical ledger 前確認公司別名、當次 ticker／fetch／job、日期、八筆及整理後去重／發布者門檻；legacy缺診斷不虛構HTTP200，nested operation保留。錯型scalar／alias、錯股票／舊fetch、standalone冒用舊job與矛盾HTTP反例均先red再修復。root **253 passed**、獨立 **154 passed**，兩者為不同覆蓋且不相加。舊Alternative Search封存，其他來源、quote／TTM／financial／social、原核心時間、本文／analysis evidence及五項quality metadata保留；原結論仍標needs_rerun。

正式入口start_mac.command已重載：launcher37913／role-all worker37941／API37943，healthz及readyz200。五個本輪runtime檔與66個沿用runtime檔hash、env、158套件、13舊job／61dispatch、六佇列／scheduled0及129781筆舊zero prefix均核對。無commit／push、模型、新analysis job、報告或quality review。

| 指定補件 | 正式HTTP | 保存後合格搜尋筆數 | 單次秒數 |
| --- | --- | --- | --- |
| 2449 京元電子 | 200 | 8 | 1.894 |
| 2353 宏碁 | 200 | 8 | 1.571 |
| 2609 陽明 | 200 | 8 | 0.712 |
| 2371 大同 | 200 | 8 | 1.362 |

四件只有19筆canonical／DataProvider觀測：4筆近期父success8、7筆GoogleRSS實際HTTP200、8筆GDELT／YahooRSS既有cooldown local_block／HTTPFalse。冷卻provider未送HTTP、未reset或重試；第一件最初寬泛any-message-cooldown停止旗標原樣保留，再明示這些是既有local skip、不是本次transport拒絕，才續驗其他原已核准缺口。headline／snippet門檻通過未驗完整發布者原文、獨立性或事件影響，provider coverage_status仍partial，原gate/status/formula不放寬。

同一preflight至正式核對：近期 **145/192=75.52%→149/196=76.02%**（4筆新父成功）；搜尋上游93/96→100/103。財報 **51/93=54.84%**未變；更早bank baseline51/96的差異為舊紀錄自然離開24h窗口，不歸因本輪。原20類仍 **18/20嚴格>80%**，goal active，不宣稱四件100%等於全系統達標。此次有新來源補件功能與四件正式修復，屬progress，沒有blocked streak。

後續155檔再唯讀核對原saved cutoff與目前門檻，尚有51檔具原始且目前缺口；21檔僅因後來時間經過而過期者排除，3檔context／artifact未核准者保留診斷。這是已具條件的待補件名單，不是51個新入口或可成功保證，尚未送後續provider請求；每件仍需當下hash／公司／core時間及原門檻核對，見[後續資格名單](evidence/source-acquisition/20261011/recent-source-next-qualified-gap-admission.json)。

免費官網研究追加複查：遠東銀英文目錄仍列2022完整合併PDF，但web工具讀已觀測href回403；未再做native請求、未繞過TLS/cookie/token，不能升格native可用。士電官網列表為先前已取得入口，未冒稱新發現，其缺無形資產購置單列仍未補零。

證據：[scope與root](evidence/source-acquisition/20261011/recent-source-review-input.json)、[154獨立覆核](evidence/source-acquisition/20261011/recent-source-independent-review.json)、[正式重載](evidence/source-acquisition/20261011/recent-source-release-proof.json)、[原時間缺口核對](evidence/source-acquisition/20261011/recent-source-original-gap-qualification.json)、[四件正式／原20類／保存查驗](evidence/source-acquisition/20261011/recent-source-formal-completion-proof.json)、[當前正式看板](evidence/source-acquisition/20261011/recent-source-final-formal-sla.json)、[官網web複查限制](evidence/source-acquisition/20261011/free-entry-web-followup-20261011.json)。


## 2026-10-11 Gogolook 新官網入口與三份完整原件

對後續原始新聞為0的6902，新增找到[官方財報目錄](https://www.gogolook.com/investors/financial/financial-reports)與[中文新聞中心](https://www.gogolook.com/zh-tw/newsroom)。正式主檔快取自然過期，沿原IssuerNewsHttp的normal shared cadence取得一次完整TWSE原件，不force、不seed、不延長舊時間，核對6902／走著瞧股份有限公司／GOGOLOOK／www.gogolook.com。只在/tmp research adapter允許兩個精確HTTPS入口，五秒單次／二十秒共同期限、普通TLS、無登入／cookie／重導／重試及原cooldown保持；完整HTML50,121及215,567bytes封存。財報列表有17個實際公開PDF href，新聞有54個列表連結；web與native均顯示最新可見新聞在2026-08-12，未進目前三十天門檻，不宣稱0→近期成功。

從同一完整目錄bytes重讀，僅下載已觀測精確三個CDN PDF網址，保留8MiB原件上限／五秒單次／共同二十秒：2023合併PDF5,403,224bytes／54頁、2024合併PDF5,484,625bytes／64頁、2025合併PDF3,178,601bytes／66頁。原件保存後hash／bytes完整重讀；有界原pypdf reader10秒／512MiB提取後核對公司／合併／年度封面。2023與2025為官網英文翻譯本且明示中文版本優先；2024為中文民國113／112年度，實際封面股票代碼6902。初版只用英文詞檢查時2024未過，保留該診斷，再依同一已保存原件的中文精確封面核對，沒有重新HTTP或改bytes。

完整原件可得不等於所有文字或金額已驗；三份reader coverage均partial，此新官網入口尚未取得2021／2022獨立原件或完成五年欄位解析，source OFF、沒有正式report／模型／source API請求。此輪研究總native HTTP6次（自然過期主檔1、目錄／新聞2、PDF3），沒有重試、手工canonical SLA或品質gate放寬，canonical ledger max仍434864；不將研究資料加進原二十類成功率。此前研究程式在HTTP前因已過期主檔None停止，該次HTTP0，不是失敗供應商重試。

四件新聞正式成果另已完成唯讀獨立覆核：71runtime hashes與三個process identity、四份實際artifact／四個index hashes、原input／本文／gates、19來源與用量、7HTTP成功及8HTTP0cooldown均一致，無material不實claim，原20類18／20保持。[正式成果獨立收據](evidence/source-acquisition/20261011/recent-source-live-proof-independent-review.json)含其驗證限制；env／套件／health／queue為原deployment證據，獨立覆核沒有重做這些請求。

證據：[新入口完整native HTML與主檔](evidence/source-acquisition/20261011/gogolook-new-official-entry-native-research.json)、[三份完整PDF與封面資格](evidence/source-acquisition/20261011/gogolook-three-complete-official-pdfs-native-research.json)。

## 2026-10-11 原始新聞缺口批次與 RSS 候選截斷修正

前述51件原始且當前都不足的新聞個案已逐一核對 artifact hash、公司身分與原 core epoch，各送一次既有 `source=recent_catalysts`。39件 HTTP200，均保存當次八筆、至少三個發布者；12件 HTTP502 保持原件。共236筆 canonical／DataProvider用量、51筆父觀測（39 success8／12 degraded）、沒有模型、新 analysis job、新報告或品質覆核。1325最初只因臨時驗證程式誤以為保留舊 quote 一定須 stale 而停止；該 quote 仍在週末原86400秒有效期內，同一請求早已成功且原epoch保持。按相同已保存回應時間離線核對後續作，不重新取得1325。舊失敗與零值帳本保留，headline門檻未被稱為全文／影響已證真。[51件正式完成證據](evidence/source-acquisition/20261011/news-backlog-all51-formal-completion-proof.json)保存各件當時結果；後來另有資料補件者依後續憑據追溯。

12件不足的診斷顯示 Google 每份 RSS 原回應先截八筆，再篩公司／日期與去重。新修正僅在 company context／recent／target≤8 時保留最多20候選；HTTP query、body、provider順序／disabled、兩個查詢與共同期限保持，最後仍採最多八筆及原三發布者門檻。先公開介面 red 3 failed／3 passed，再最小修改一份runtime檔；259項 root與161項獨立覆核（含10項獨立檢查）通過。正式重載只載入這一檔差異，其餘70份已載入檔、環境與158套件保持；新 launcher48638、role-all worker48667、API48669，healthz／readyz200，六隊列／排程空、13舊jobs／61dispatches及舊失敗432041／129894零值前綴相符。

逐份 feed record_count 核對後，只有九件曾碰到八筆候選上限；6902兩份0／0、2069為6／7、1623為3／4，這項修正不能改變該三件原失敗，不送額外重試。九件不同已部署行為的請求各一次，臺企銀2834與合庫金5880成功；其餘2442、2845、2851、6550、2254、2321、6924仍按原品質門檻拒收，七件原報告在請求當時保持。臺企銀候選 raw40、合庫金raw20，兩者最終仍八筆；沒有將其他股票標題或重複值湊數。九件共56 canonical／DataProvider觀測，2父success8／7 degraded，既有GDELT／Yahoo冷卻均HTTPFalse；沒有實際新transport拒絕或模型／job／quality review。原39件已補齊個案不重抓。合計這兩批補齊41個不同原新聞缺口，60次正式 source-only request；不將批次成功率或自然移出窗口當全系統達標。

證據：[獨立審查與scope](evidence/source-acquisition/20261011/google-candidate-independent-review.json)、[正式重載](evidence/source-acquisition/20261011/google-candidate-release-proof.json)、[九件資格與三件不重抓](evidence/source-acquisition/20261011/google-candidate-prioritized-admission.json)、[九件正式完成與原20類](evidence/source-acquisition/20261011/google-candidate-all9-formal-completion-proof.json)。

九件正式結果另完成唯讀獨立覆核：56筆帳本及用量一致，包含17次實際HTTP、30次冷卻跳過與9筆父彙總；1 owned＋70 preserved runtime hashes、正式generation、原本文／analysis input／五gate／core時間均相符。2321在九件news批次結束後的年度補件，依補件前保存檔分開核對，沒有把後續合法變更誤算新聞越界。獨立隔離證據檢查1 passed、無未解material finding，未重跑259／161原套件、未送來源或正式服務請求。[正式結果獨立收據](evidence/source-acquisition/20261011/google-candidate-live-proof-independent-review.json)。

## 2026-10-11 東訊新官方完整財報入口與五年正式補件

新增找到[東訊官方財報目錄](https://www.tecom.com.tw/investor-relations/financial-report/)。重讀此前已封存完整TWSE主檔核對2321／東訊股份有限公司／官網host，不重新取得主檔或續期。一次普通匿名TLS200取得完整250893bytes HTML，27個實際PDF href；按各年度合併標題與同一份完整目錄選2021–2025五個href，不採個體或季度、不把上傳路徑年份當財年。五份普通匿名TLS PDF各一次，原8MiB上限／單次五秒／共同三十秒、無登入cookie／重導／重試與原冷卻保持。

| 官網年度標題 | 完整 PDF bytes | 原 native reader 結果 |
| --- | --- | --- |
| 2021 合併 | 6,901,715 | 71頁／封面公司年度可核，財務表9–14頁原生文字空白 |
| 2022 合併 | 7,101,718 | 原 parser_warning 拒收，不繼續抽頁 |
| 2023 合併 | 4,187,605 | 70頁／封面公司年度可核，財務表9–14頁原生文字空白 |
| 2024 合併 | 870,243 | 67頁／native coverage complete |
| 2025 合併 | 2,599,142 | 67頁／native coverage partial，查核報告5–8頁空白 |

五份共21,660,423bytes，全部原件archive／hash／完整大小讀回一致。相同有界10秒／512MiB子程序只捕捉2022第一警示：`Xref table not zero-indexed. ID numbers for objects will be corrected.`，隨即拒收；沒有關閉警示、轉換／修補PDF、OCR或假補數字。2024／2025現金流量表13–14頁的年度與TWD仟元欄可核，包含2023比較值；兩份2024重疊三個現金流科目一致。這僅是三年明示現金流列，未成五年九科目資料。臨時研究程式第一次移除數字欄間空白導致兩個正數接在一起，其assert拒收；改保留原行／欄間空白，在同一原件離線重播，沒有新HTTP或正式資料寫入。新PDF route仍OFF，六次研究HTTP（目錄1／PDF5）不手工寫canonical SLA。[完整目錄](evidence/source-acquisition/20261011/tecom-2321-new-official-financial-entry-native-research.json)、[五份完整PDF與封面](evidence/source-acquisition/20261011/tecom-2321-five-complete-official-pdfs-native-research.json)、[警示／空白頁／逐列限制](evidence/source-acquisition/20261011/tecom-2321-native-financial-entry-qualification.json)。

東訊原報告只有2022–2025四年，historical ledger只見Yahoo及原aggregate，沒有官方年度來源嘗試；重新核對EQUITY／TWD／原core audit與當下artifact hash後，首次走既有 `source=financial_statements` 免費官方 MOPS。單次正式request **HTTP200／2.169秒**，原嚴格issuer／年度／consolidated／TWD／scale／sign及九科目流程取得2021–2025完整五年，canonical父success5及DataProvider用量各一筆。此成功用既有MOPS iXBRL，不是採用新PDF候選。保留quote／TTM原值與時間、其他來源audit、HTML／Markdown、analysis evidence及五項原品質metadata，分析正文仍標需重新分析。原MOPS decoded HTTP bodies未另行保存／獨立原件重播；保存的是實際來源文件URL／SHA、raw TWD科目與原流程驗證，不冒稱完成額外原件稽核。[首次官方補件資格](evidence/source-acquisition/20261011/tecom-first-official-annual-admission.json)、[正式五年補齊](evidence/source-acquisition/20261011/tecom-first-official-annual-2321-formal-refresh-proof.json)。

最後原20類近24h驗收仍 **18/20嚴格>80%**：財報 **52/88=59.09%**、近期事件 **182/243=74.90%**。本輪真正新增是41個原新聞缺口及一個五年財報缺口；歷史自然離開24h窗口的分母／成功數差異不歸因程式。runtime71份與.env／PIDs／套件、health／readyz、六隊列與舊jobs／dispatch／失敗／零值前綴均核對；新模型、job、report或quality review為零。全20類目標仍active，屬progress，未宣稱達標或品質警示消失。[最後完整查驗](evidence/source-acquisition/20261011/free-entry-continued-final-check.json)、[正式完整SLA](evidence/source-acquisition/20261011/free-entry-continued-final-formal-sla.json)。

## 2026-10-11 35件首次官方年度嘗試與新版MOPS JSON免費入口

接續原20類嚴格>80%目標，從目前真正四年報告挑選35件沒有任何先前官方年度父觀測的缺口；原候選60件中的25件因已五年、已有官方失敗或context不符排除。每件既有 `source=financial_statements` API僅一次，3231先行完成後依同一terminal proof續作，沒有額外重抓。結果 **11件完整2021–2025補齊、24件HTTP502保留原件**。35個canonical父事件及35筆DataProvider用量逐一關聯；沒有新增模型、job、report或品質審閱。成功保留原quote／TTM與時間、其他source audit、HTML／Markdown、analysis input與五gate，只修年度history／衍生值並標分析待重跑。2892的金融機構net_revenue保持獨立科目，不套一般產業Revenue。未成功的24件完整bundle bytes不變。

失敗原因有11件缺較新完整比較期（2023兩件、2022兩件、2021七件）、五件舊MOPS暫不可读且comparison缺／重複無形資產購置、三件2021必要事實不完整、一件2021比較值衝突且不完整、四件官方合併annual少於五年。這些不是429／額度錯誤，不用模型或把缺值補零解決。實際歷史加入24失敗後，財報由52/88降至 **63/123=51.22%**；近期事件 **182/243=74.90%**，原20類仍18/20嚴格>80%。11件修補不等於整體率改善，旧失敗仍按24h窗口保留。完整原件body未在此既有MOPS路徑另行封存，現有事實／申報URL／SHA與投影驗證不冒稱獨立HTTP原文抽取。[35件資格](evidence/source-acquisition/20261011/next-untried-annual-admission.json)、[逐件terminal進度](evidence/source-acquisition/20261011/next-untried-annual-sequential-progress.json)、[35件完成／逐股票失敗原因](evidence/source-acquisition/20261011/next-untried-annual-all35-completion-proof.json)。

新找到[新版MOPS資產負債表](https://mops.twse.com.tw/mops/#/web/t164sb03)、[綜合損益表](https://mops.twse.com.tw/mops/#/web/t164sb04)、[現金流量表](https://mops.twse.com.tw/mops/#/web/t164sb05)實際使用的免費公開POST JSON入口：`/mops/api/t164sb03`、`t164sb04`、`t164sb05`。從同一創意3443官方UI查詢所送出的實際URL與五欄payload探索，不猜路由或搬cookie／token。payload為 `companyId=3443,dataType=2,season=4,year=民國年,subsidiaryCompanyId=''`。

第一個curl prototype雖HTTP200但content-type不符合JSON，保留protocol拒收，source OFF；沒有403／429／登入拒絕，也沒有清掉冷卻。接續普通httpx HTTP1.1匿名POST，fresh cookie-empty client／普通TLS／不redirect、retry、proxy、auth，單次五秒、共同45秒與250,000bytes單件上限：創意2021–2025五年三表 **15/15 native HTTP200完整body**，皆封存archive／SHA／bytes讀回。精確檢查code actual int200、合併、ROC年、Q4、calendar fiscalYear空白、當期及前期欄名、同issuer申報URL與唯一九科目、兩個年度amount欄，purchase保持負號；未填任何缺值。較新四份annual內的完整比較值可按原 `reconcile_comparative_rows`／`assemble_annual_histories`組成五年九科目，創意原2023比較數不足的缺口有了新候選原件。[第一protocol拒收](evidence/source-acquisition/20261011/mops-json-3443-five-year-native-research.json)、[15份完整原件與當期／比較期候選](evidence/source-acquisition/20261011/mops-json-3443-five-year-httpx-research.json)。

JSON body本身沒有currency／unit欄，不能聲稱內建TWD；相同3443／113年Q4官方UI明示「單位：新台幣仟元」。實際pageAssets另觀察到三個官方 `t164sb03.js`／`t164sb04.js`／`t164sb05.js`；各一次普通native GET取得完整6549／6507／6480bytes，archive／hash讀回一致，每份有唯一、無条件靜態h3相同單位literal。研究Decimal×1000換算以此官方renderer contract為依據，未把它偽裝成JSON欄位。三份完整模板不自行執行或轉用cookie。[官方unit模板原件](evidence/source-acquisition/20261011/mops-json-official-unit-template-research.json)。

新版來源仍 **OFF**：本轮只做/tmp研究transport／解析，不改backend、provider、報告投影或正式SLA；15次POST與3次模板GET不計正式分子。只验证3443 calendar ordinary合併五年，不能泛化為全部issuer、金融機構、非曆年或任意缺項皆成功。下一個接入工作需獨立實作named provider、bounded transport、原件receipt與單位契約投影，先測wrong issuer／年度／scope／單位／duplicate／缺科目／符號／超時／429／comparative conflicts，再部署、針對原拒收件驗證。沿用原20類與80%分母、TTL、歷史及品質gate，不重抓已成功11件來墊高比例。

35件正式補件另完成唯讀獨立覆核（1個隔離evidence check passed），完整bundle／歷史帳本／科目投影／quote與時間均相符，無material finding；新版來源獨立覆核從19個不同完整原件（15JSON、3官方模板、1先前主檔）查34份收據，45列／90個當期及前期金額，以獨立Decimal×1000重算五年候選及四年較新比較值：無補零、無修訂差異，2025 FCF保留負 **−2,313,966,000元**。1個隔離evidence check passed，無material finding；僅原件研究資格，不能取代尚未實作的provider整合／正式接入驗證。[35件獨立覆核](evidence/source-acquisition/20261011/next-untried-annual-independent-review.json)、[新版MOPS原件獨立覆核](evidence/source-acquisition/20261011/mops-json-independent-review.json)。

最後重新讀正式近24h看板：原20類仍18/20嚴格>80%，財報 **62/122=50.82%**、近期事件 **179/238=75.21%**。相對35件完成時63/123及182/243的變動，是舊觀測自然離開時間窗，不歸因研究入口。新版JSON、模板研究後沒有任何新canonical／用量紀錄；保持同一71檔runtime、158套件與.env、launcher48638／worker48667／API48669，health／readyz200，六隊列及scheduled為零；原13jobs／61dispatch、failure432041與129894個舊零值前綴不變。901reports／1110jobs／2qualityreviews保持，原20類目標active且本輪有11件實質修補及新完整入口證據。[最後正式查驗](evidence/source-acquisition/20261011/mops-free-entry-final-check.json)、[正式完整SLA](evidence/source-acquisition/20261011/mops-free-entry-final-formal-sla.json)。

## 2026-10-11 新版MOPS正式接入與11件原比較數缺口實測

延續上述source-OFF研究，新增 `backend/data_fetch/market_sources/mops_public_annual.py`，並只修改原 `annual_financial_source_provider.py`、`official_financial_gap_cache.py`、`yfinance_extractors.py` 的接入。Default ordinary台股的正常uncached與指定年度source-only改用明示provider **TWSE MOPS public annual JSON**；原bank／broker／insurer routing保留。舊explicit legacy fetcher的缺口cache仍在原namespace，既有年度shared cache／source原時間、TTL、保留與force契約不清除、不seed、不延長。模板新hash或非calendar／金融業一般科目缺漏皆拒收，不能以新provider名稱绕過既有拒絕或冷卻。

Source transport按五年公布合併申報index選期，每次index1／unit templates3／三表15，最多19次普通匿名HTTPS。來源URI與payload固定、單件JSON／JS250,000bytes／index2,500,000bytes，45秒共用admission期限及各httpx階段至多5秒，進行中階段可另等餘timeout，不能冒稱45秒硬wall。原件整體重驗後查同一deadline；无redirect、retry、auth／cookie／proxy、原件成功cache或模板自动更新。429／403／5xx停止後續，保留Retry-After與host冷卻，API host被拒時不為下一次重讀index；未知例外及archive錯誤也禁止整個multi-year operation隱性重試。

接入前兩個真red：現有投影拒絕完整public receipts，以及default仍選old-iXBRL。原件fixture共15JSON／3模板107,618bytes；測試只用隔離runner。獨立初版覆核提出4組P2（6個反例）：錯型components拋例外、早於年度結束的原件取得日、完整readback逾時仍成功、同批單份公司簡稱矛盾。修正typed拒收、JSON原件取得日≥該年度期末／模板≥最新年度期末、admission後再驗期限、全15份公司簡稱一致；subsidiary選項清單不等於已選child，仍核空request／exact parent XBRLref、list型別及explicit selected ID为空。再補真壞deflate archive的 `zlib.error`拒收與禁止首次archive故障觸發整批重試。全部反例已存永久回歸，root **187 passed**、最終獨立限定recheck **56 passed**，初版134、修正版149及兩份red範圍分開保存，最後無material finding。三個legacy workflow測試只改explicit legacy注入，原assertions保留；新測試核default／normal／source-only路径及原正文／gate保存。[actual scope與SHA](evidence/source-acquisition/20261011/mops-json-integration-review-input.json)、[分階段獨立覆核](evidence/source-acquisition/20261011/mops-json-integration-independent-review.json)。

在68preserved＋4owned＝72runtime paths、.env及158packages、六隊列／scheduled零、原13jobs／61dispatch與舊零值前綴均核對後，graceful停止原owned worker／launcher，不force-kill，经canonical `start_mac.command` 重載。新launcher **61248**、worker **61276**、API **61278**，health／readyz200、packages与source revision完整讀回；Redis bgsave成功、無新analysis／retry排程。啟動後原frontend cold quality-read曾30.807秒並回503，這是既有品質投影冷啟動，不是新版來源HTTP504或取得成功；source-only request另依實際elapsed計。[正式重載與原狀保存](evidence/source-acquisition/20261011/mops-json-integration-release-proof.json)。

首次實測創意3443原「2023缺完整較新比較數」報告：僅一次正式request，**HTTP200／3.607秒**、19來源HTTP均200，取得2021–2025完整九科目與比較數，2025 FCF保留負值，quote／TTM、正文、analysis input及五gate不變並標待重分析。接續剩餘10件原同類被拒件各一次、逐件terminal後再送，**8完整／2held**；不重抓原11件已健康財報或3443來增加分子。本轮共 **11件真缺口／9補齊／2原件不變**，197 physical HTTP均200，只新增11 canonical父觀測及11 DataProvider用量、無模型／job／report／quality review新增。9成功為3443、3481、6168、6456、3605、2492、8201、6488.TWO、6770；2409及6550缺明示「取得無形資產」仍拒，不能從沒有此列推斷0。9/11=81.8%僅本輪資格樣本，不是全20類驗收。[逐件進度](evidence/source-acquisition/20261011/mops-json-comparative-sequential-progress.json)、[11件完整根查驗](evidence/source-acquisition/20261011/mops-json-eleven-formal-completion-proof.json)。

同輪最後正式近24h仍 **18/20嚴格>80%**：財報 **70/131=53.44%**、近期事件 **176/235=74.89%**，目標active、有實質progress；與前一窗口差異中的舊觀測自然離開不歸因新接入。舊failed／zero history及formula、20類、TTL、品質門檻保留，901reports／1110jobs／2reviews及129948個release前零值前綴維持。正常uncached已用MockHTTP證明在SDK前採新來源，這次live只做舊報告source-only，沒有產生新full report或宣稱模型／報告品質成功率改善；原年度shared cache未補寫，會按既有期限自然失效。[完整正式SLA](evidence/source-acquisition/20261011/mops-json-eleven-after-formal-sla.json)。

兩件held另做有界只讀原件查找：重讀本輪已封存failed CF完整body，友達2024／北極星2022都沒有任何「無形」列，非label別名，不能補0。各只查一個尚未取得的下一年CF：友達2025明列 **取得無形資產 current −145,227仟元／2024比較0**，北極星2023仍無此列。這兩次研究HTTP完整archive，不寫canonical／用量、不重試或重抓九件成功。友達有可驗證的明示比較0，值得接續原年度缺列的受控比較值修補；需完整同issuer／年度三表及九科目、各原件與原品質規則對照後才可正式採用，不能把一份CF研究當五年成功。北極星仍須不同公開原件／明示註記，不從’absence’推0；尚未實作或再次正式重試兩件。[下一年CF原件與實際列](evidence/source-acquisition/20261011/mops-json-two-missing-facts-next-comparative-research.json)。

## 2026-10-11 繼續查找：官方電子書英文合併財報完整入口

從[北極星公司年報](https://polarispharma.com/investors/annual-report/)的原公開連結，以普通匿名 HTTPS 取得 2022／2023 年報完整 PDF，分別 2,983,861／3,110,869 bytes、157／184頁；索引與原件皆封存完整 bytes 並讀回 hash。2023 年報後段財報是掃描表格，純文字擷取不能定位現金流量；實際 render 核對 PDF 第127頁（印刷123頁）合併現金流量表，2023當期／2022比較期及新台幣仟元皆明示，但仍沒有取得無形資產列。未從掃描文字空白、科目餘額或商譽變動推算購置現金流。[原件入口研究](evidence/source-acquisition/20261011/issuer-financial-new-entries-research.json)。

友達官網 financial results 的完整 HTML 明示合併／個體選項，原公開 inline handler 提供 `ajaxSubcategory?id=financial`；普通 GET 取得完整年度 JSON，含2016–2026。2024實際 category ID 與同一 handler 組成的年度列表在五秒單次讀取逾時；保留一次 timeout，不延長本輪期限或重試該列表。這是可發現的入口，尚不是可用完整年度表。[年度選項原件](evidence/source-acquisition/20261011/auo-official-financial-categories-research.json)、[年度列表逾時](evidence/source-acquisition/20261011/auo-official-annual-financial-index-research.json)。

改從[公開資訊觀測站財務報告書](https://mops.twse.com.tw/mops/#/web/t57sb01_q1)實際 UI 分別查6550／民國112、2409／113；頁面公布 `doc.twse.com.tw/server-java/t57sb01` 索引。原索引明示曆年制、第四季、**IFRSs英文版-合併財報**，與個體財報分列，取得確切檔名、大小及申報日。讀取原 `readfile2` public form 的 step9／kind／issuer／filename，再由其完整原回應中唯一 href 取得動態 PDF；不猜日期尾碼，不把索引或 HTML 當 PDF、不搬 cookie／token。北極星原英文財報 **1,071,799 bytes／76頁**，友達 **819,211 bytes／139頁**，都匿名普通 TLS 三步取得並封存讀回；英文文字可直接抽取，是此輪新驗證的完整文件入口。動態 URL 只作當次下載，後續應重新從正式索引核對原申報與修訂，不能把臨時 URL 當長期靜態 API。[北極星完整索引／form](evidence/source-acquisition/20261011/mops-english-financial-book-native-research.json)、[北極星英文PDF](evidence/source-acquisition/20261011/mops-english-financial-book-complete-pdf-research.json)、[友達完整索引](evidence/source-acquisition/20261011/auo-official-financial-book-list-research.json)、[友達英文PDF](evidence/source-acquisition/20261011/auo-official-financial-book-complete-pdf-research.json)。

英文 PDF 亦做完整相關頁面 render：北極星第17頁、友達第11頁，標頭、年度、合併、TWD仟元與現金流科目相符；友達頁面明示為原中文合併財報的英文翻譯，不能把它視為另一個獨立發布者。兩份仍沒有原先缺少的無形資產購置列；北極星第39頁 intangible asset roll-forward 是資產餘額及合併取得，不能換成該現金流科目。友達2025 JSON的2024明示比較0保持既有研究資格，2023較新比較期缺列仍須完整證據處理。本輪沒有降低原品質 gate、改 parser、重試兩份 held 報告或增加正式來源成功；新入口應接續用來核對其他原 XBRL 暫不可讀的真缺口，完整九科目與五年資格仍逐件驗證。

本輪 **12次 native research request／11完整HTTP200原件／1timeout**，含四份完整PDF；這是文件與入口研究數量，不計正式分子。最後重新查原72 runtime paths、.env、正式來源帳本／DataProvider用量、901reports／1110jobs／2qualityreviews與兩份held的HTML／Markdown／snapshot保持；health／readyz200。原20類及24h公式保持，仍18/20嚴格>80%，新的完整文件入口不代表財報缺口或全20類目標完成。[原件、正式原狀與完整20類最後查驗](evidence/source-acquisition/20261011/free-financial-entries-next-final-check.json)、[正式近24hSLA](evidence/source-acquisition/20261011/free-financial-entries-next-formal-sla.json)。

## 2026-10-11 明示較新比較值補缺：友達正式五年補齊

原35件失敗中尚未採新版協議的九件，只先查原失敗年度的官方 CF；完整原件及精確 issuer／annual／scope／unit 核對後，僅國巨2327的2021現金流三科目明示完整。一次正式新版來源請求在2022缺「取得無形資產」被拒，10次來源HTTP均200，原報告三個artifact保持。其餘八件原CF缺列沒有送相同版本正式重試。這份窄查只證明指定年度CF，不能當五年資格。[九件預查](evidence/source-acquisition/20261011/next-public-annual-nine-missing-fact-research.json)、[國巨一次正式拒收](evidence/source-acquisition/20261011/mops-json-formal-2327-formal-refresh-proof.json)。

發現 public JSON 五年流程過早停止：某年度完全沒有無形資產購置列時，尚未讀下一年度的明示比較欄就整批失敗。只改3個已部署檔 `mops_public_annual.py`、`annual_financial_source_provider.py`、`yfinance_extractors.py`。Standalone `parse_statement` 預設strict保持；五年 acquisition及原件readback才允許該單一完全不存在的科目先保持unknown，不接受duplicate／dash／bool／null／其他缺科目。原 `reconcile_comparative_rows`、`assemble_annual_histories` 逐位未改：較新官方明示值才補 original missing，保留原申報年、比較申報年及 `missing_fact_fill`；不完整比較期只要任何已明示值與primary衝突仍拒收，無衝突者保留已明示原年度值。最終五年×九科目仍全部required、整數、同口徑，未解缺項拒收，不從’absence’或資產餘額補0。`comparative_coverage` 由完整原件重算，分列available／missing／retained primary facts；顯式metadata矛盾拒收，舊完整public receipts可重讀導出覆蓋。Audit與SDK notes按實際覆蓋描述，不把partial比較期稱完整。

先保存真red：public fetch在缺2024列、2025明示2024比較0時仍early reject。修正後明示0及非零的補證、七組未解缺項／partial conflict／壞值拒收均通過。另重讀2409原2021–2024及2025CF完整原件，只新增2025BS／IS兩次普通匿名 JSON POST，組185,148bytes實際15JSON／3模板fixture；舊failed component只有原取得區間，不假造exact child receipt時間，只作offline replay。Actual AnnualFinancialSourceProvider test使用合法fetch correlation，19個MockHTTP重播成功，2024比較0、2023partial8及三筆補值／重述完整保留。Root **197 passed**，獨立 **100 passed**，無material finding；獨立source-only及正常uncached integration也保持正文、gate、quote／TTM。[原before／3檔SHA與驗收](evidence/source-acquisition/20261011/mops-comparative-recovery-review-input.json)、[actual友達原件研究](evidence/source-acquisition/20261011/mops-auo-explicit-comparative-full-original-research.json)、[獨立設計／實作覆核](evidence/source-acquisition/20261011/mops-comparative-recovery-independent-review.json)。

3owned＋69preserved＝72runtime paths、.env、158packages、13jobs／61dispatch、旧zero前綴129951保持；canonical graceful重載，新launcher69695／worker69723／API69725，health／readyz200、六隊列及scheduled零。重載後前端原cold quality-read約30.79秒、daily-dashboard一次503仍存在，非來源504，本修正未處理該既有讀取問題。[正式重載查驗](evidence/source-acquisition/20261011/mops-comparative-recovery-release-proof.json)。

友達2409**只做一次新版正式source-only**，HTTP200／**5.775秒**、19個來源HTTP全部200，2021–2025完整必要科目補齊。2024無形資產購置由2025明示比較0補齊，保留 `original_twd=null`及來源年份；2023較新比較表只8科目、原年度明示0保持，metadata明示partial；2021設備與無形資產兩筆完整比較重述亦逐筆保存，不把原38,000,000元無形支出抹成從未發生。HTML／Markdown、analysis evidence、五gate、原股價／TTM及時間和其他來源保持，analysis_text_stale=1，不能宣稱重新分析或新報告品質成功。[友達正式逐件證據](evidence/source-acquisition/20261011/mops-comparative-formal-2409-formal-refresh-proof.json)。

接續八件下一年／最新年CF原件窄查：七件連2022明示比較科目仍缺，不送正式。光鼎6226的2025表有2024明示比較0，因此只做一次新版完整補件；19來源HTTP全部200，但完整五年final發現2021未解科目，仍HTTP502且原三artifact逐位保持，沒有因某一年度可補就放行全五年。這段預查另8次native研究HTTP不入正式分子。[八件下一年比較預查](evidence/source-acquisition/20261011/mops-comparative-next-eight-explicit-fact-preflight.json)、[光鼎一次正式拒收](evidence/source-acquisition/20261011/mops-comparative-formal-6226-formal-refresh-proof.json)。

本goal turn含改碼前國巨，合計3次正式請求、1個真五年缺口補齊、2件held；48次來源HTTP全部200，HTTP200本身不是年度完整資格。新重載後只有2canonical／2DataProvider，無新增模型／job／report／qualityreview；共享年度cache未purge、seed、續期，先前健康來源不重抓。原20類嚴格>80%仍 **18/20**，財報 **71/134=52.985%**、近期 **176/235=74.894%**。財報比例受两次真实拒收影响，不能把一件補齊、197隔離或100覆核當整體率達標；goal仍active。[正式原狀／帳本及20類完整根查驗](evidence/source-acquisition/20261011/mops-comparative-recovery-formal-completion-proof.json)、[正式近24hSLA](evidence/source-acquisition/20261011/mops-comparative-recovery-after-formal-sla.json)。

正式成果另完成唯讀獨立覆核，1個隔離evidence check passed，無未解material finding；友達15JSON／3模板、45年度必要科目、比較coverage、三筆補值／重述與FCF一致，國巨／光鼎held原件、source帳本及正文／analysis／五gate／quote／TTM均相符。另只重讀先前九件完整public報告及原件，四份complete比較覆蓋可由舊無新metadata的manifest導出；9件三artifact hash逐位保持，HTTP0／寫入0，不將replay當新取得。最後當前runtime／health及正式20類仍18/20，保留未完成目標與cold dashboard503限制。[正式成果獨立覆核](evidence/source-acquisition/20261011/mops-comparative-recovery-live-independent-review.json)、[九份舊完整原件相容性](evidence/source-acquisition/20261011/mops-comparative-nine-existing-complete-archive-compatibility.json)、[最後當前查验](evidence/source-acquisition/20261011/mops-comparative-recovery-final-current-check.json)。


## 2026-10-11 全155家公司逐欄盤點與17份新年度補件

本輪重讀901份既有報告中155家公司的最新快照，沿 ReportArtifactLocator／storage helper 找原件，沒有provider或模型請求。不能只數 `years`：多份雖列2021–2025，2021的必要history仍為null。另一層資格核對沿既有金融業schema，9份專用五年history完整者不因一般Revenue／GrossProfit為null重抓；7份原年度及較新public比較科目都已證明缺失、已驗未滿五年的申報、已有public正式嘗試與context不符者另行保留。[155家原盤點](evidence/source-acquisition/20261011/next-annual-all155-latest-inventory.json)、[逐schema資格](evidence/source-acquisition/20261011/next-annual-all155-typed-gap-admission.json)。

先處理25家沒有任何官方年度觀測、但確實少必要數值的一般產業及4家金融業，每家公司只做一次既有正式 `source=financial_statements`；沒有full分析、重試或重抓健康報告。29次中16份通過現有完整五年投影（12份public、彰銀bank及3份holding），13份API502保存原三artifact。拒收為4份transport／timeout、3份公布合併annual不足五年、3份不完整比較數衝突、2份最終必要事實不足與1份設備購置列缺失。Source原429／拒絕／cooldown仍先檢；沒有把下游API502當來源原生HTTP502。25份public的canonical僅保存350個component diagnostics，其中346個HTTP200及4個未取得HTTP status；不能把diagnostic數當精確physical HTTP，4份金融業也沒有原生HTTP telemetry。完整public成功audit的送出旗標另存在report；不為未知填0。[29件逐件完成與保護](evidence/source-acquisition/20261011/mops-additional-gaps-29-formal-completion-proof.json)。

接續14家曾由舊年度路徑拒收、仍沒有public正式觀測的候選，以最新年度及首年現金流做有界窄查；2家原申報已不足五年不發新HTTP，另外12家合計15次匿名POST。10家最新年必要科目仍缺、三陽2021及2022明示比較都缺，只有宏碁首年及最新年三個現金流科目明示完整。窄查不當完整五年資格／正式分子，不補0；原官方單位模板只重讀原receipt而未续期。[14家新協議窄查](evidence/source-acquisition/20261011/mops-old-gap-new-public-explicit-cashflow-preflight.json)。

宏碁2353沿同一已部署來源只送一次正式完整補件，HTTP200／3.511秒，從2022–2025四年補齊2021–2025，完整15份JSON及3份單位模板再重播；HTML／Markdown、analysis evidence、五品質metadata、原quote／TTM及時間、其他source audit保持，正文標待重新分析。合計本輪30個canonical parents／30筆DataProvider，新增17份合格五年history，沒有新增model／job／report／qualityreview。72個runtime／env hashes、158套件、原13jobs／61dispatch、failure432041與129951個舊零值prefix、六隊列及scheduled保持；canonical API69725未重啟。[宏碁正式證據](evidence/source-acquisition/20261011/mops-additional-gaps-formal-2353-formal-refresh-proof.json)、[30件完成、科目與帳本讀回](evidence/source-acquisition/20261011/mops-additional-gaps-30-formal-completion-proof.json)。

獨立覆核揭露必要的證據分級限制：玉山金2884、台新新光金2887、合庫金5880沿既有 `financial_institution_consolidated.v1` 取得五年明示facts／申報URL／SHA，但該legacy holding分支沒有持久封存五份完整body，不能冒稱完整原件重播。本輪共14份可重播完整原件（13 public及彰銀bank）、3份僅現有typed契約／文件hash及history核對。原逐件helper誤把 `full_native_http_bytes_replayed_by_public_projection=True` 通用到3份holding，已另存明確correction receipt；不重寫正式success史／snapshot或重抓健康3家灌高比例。新holding取得的完整body封存／重播是後續待補強項，原品質metadata保持也不代表新報告品質通過。[證據分級更正](evidence/source-acquisition/20261011/mops-additional-gaps-29-evidence-tier-correction.json)。

另找到上銀2049[官網財報列表](https://www.hiwin.tw/stock/fn_report.aspx)公布的2025Q4合併英文PDF，與母公司個體檔分列。只讀完整native列表後跟隨exact published href，普通TLS／無cookie、auth、redirect、retry與proxy，2次匿名GET取得99,430 bytes完整HTML及1,881,785 bytes／73頁PDF。檔名雖以202504開始，實際封面及列表是2025／2024合併，不能以檔名猜報表年度。保存bytes重讀並render第11／12頁：仍未明示無形資產購置現金流，不能將不存在列或資產餘額補0；這個完整文件入口尚未接入provider、沒有解除2049比較數衝突或算新成功。英文為中文報告翻譯，不增加獨立發布者。研究初版issuer title assertion因PDF換行失敗，僅用已封存bytes正規化空白修正讀回，沒有追加HTTP。[native完整原件](evidence/source-acquisition/20261011/hiwin-complete-2025-free-financial-book-native-research.json)、[完整PDF及視覺讀回](evidence/source-acquisition/20261011/hiwin-complete-2025-financial-book-original-readback.json)。

30件完成時正式近24h原20類仍18／20嚴格>80%，財報87／163＝53.374%、近期172／230＝74.783%；窗口自然移出舊觀測也會改變分母，不能把17份補件或14份原件重播當全系統80%達標。保留全部歷史、原公式與未完成goal。[完整正式SLA](evidence/source-acquisition/20261011/mops-additional-gaps-30-after-formal-sla.json)。


30件成果已完成唯讀獨立覆核，2個隔離evidence checks通過，原29件與宏碁附項分開核對，無其他未解material finding。13 public共585個年度必要數值與完整bank原件可重讀；3holding限制及更正收據已核對，未假造total physical HTTP或新的報告品質成功。[獨立覆核與宏碁附項](evidence/source-acquisition/20261011/mops-additional-gaps-29-independent-live-review.json)。

同時再查[富威電力官網歷史財報](https://www.fwp.com.tw/Investor)：頁面2021–2026年度selector不能當五年合併證據。只各讀一次完整HTML與其實際公布的Investor bundle（不執行script），bundle的固定table明示2021／2022為「個體財務報告」，2022另有重編個體，合併列表2023才開始。因此有新的早期文件入口，但不能把個體與2023–2025合併混成同口徑五年；未下载早年PDF、送新正式補件或算成功。新代[官網年報列表](https://www.syntecclub.com/AnnualRepo.aspx)目前也僅公布2023–2025並連到doc.twse，未證明2021／2022可用。[富威完整native頁](evidence/source-acquisition/20261011/fwp-official-financial-entry-native-index-research.json)、[native公布bundle](evidence/source-acquisition/20261011/fwp-official-financial-native-published-bundle-research.json)、[早年報表範圍資格](evidence/source-acquisition/20261011/fwp-early-financial-entry-scope-qualification.json)。

## 2026-10-11 MOPS單次查詢連線重用與3件先前傳輸缺口補齊

前輪2027、2344、6861、8150的完整財報正式補件曾因transport／timeout中止。先各一次普通匿名 native research，不送正式API／模型、不寫canonical／用量：2344在原逐份fresh client取得19份HTTP200並通過五年資格，trace實測19次TCP及19次TLS；2027研究單次共用client取得19份HTTP200並通過資格，實測2次TCP／2次TLS。兩家公司與不同時間的量測只能證明實際連線生命週期，不能算因果延遲改善百分比或整體故障率。[原傳輸與候選連線研究](evidence/source-acquisition/20261011/mops-connection-lifetime-two-failed-case-native-research.json)。

只修改 `backend/data_fetch/market_sources/mops_public_annual.py`：完整五年operation用一個匿名HTTP client，連線僅在該批存活；每次請求前後清空cookies，離開operation必定清除／close，單份及不同批隔離。每份保留原allowlist／普通TLS／無proxy與auth、host冷卻、回應大小與原件封存；重新計算原共同45秒admission與單階段最多5秒、connect最多2秒的剩餘timeout，client close後再查同一deadline。沒有延長期限、增加retry、放寬科目／比較數或更新shared cache TTL；進行中的階段仍可能等剩餘timeout，不能稱45秒硬wall。十九份HTTP不縮減成兩份，重用的是連線。

真正的修改前失敗測試觀察到完整查詢建立19個client，修改後要求1個，永久回歸另覆蓋response cookies不帶到下一次、403／429／503／transport／壞JSON與unit失敗關閉且不retry、期限縮減、單份與不同批隔離、close跨過期限拒收。root相關13檔 **208 passed**；獨立覆核另 **8 passed**，含中途冷卻／期限及cleanup failure拒收，無未解material finding。只針對這一檔owned範圍覆核，既有大量無關dirty成果保持。[immutable覆核範圍](evidence/source-acquisition/20261011/mops-pooled-http-independent-review-input.json)、[獨立程式覆核](evidence/source-acquisition/20261011/mops-pooled-http-independent-review.json)。

新實作再各一次研究8150與6861，都取得完整19份HTTP200、一個client、2次TCP／TLS並確實close；6861通過完整五年資格，8150最終仍是「annual XBRL facts are incomplete for2021」。這表示傳輸完成不能代替年度必要事實；8150保留缺口且不送相同正式重試。本輪4個研究查詢共76個HTTP200沒有算進正式分子，未重抓健康公司。[新實作兩件原件研究](evidence/source-acquisition/20261011/mops-pooled-current-two-remaining-gap-native-research.json)、[僅3個真正缺口正式資格](evidence/source-acquisition/20261011/mops-pooled-http-three-actual-gap-formal-admission.json)。

在1owned＋71preserved＝72 runtime files、.env／158packages、13jobs／61dispatch、failure432041與129965舊zero前綴核對後，graceful重載canonical `start_mac.command`，launcher79982／worker80010／API80012，health／readyz200、六隊列與scheduled為零；沒有force kill、依賴更新或額外model／analysis。啟動時原前端daily-dashboard仍一次503；此既有品質讀取問題未由來源連線重用處理。[正式重載及保留證據](evidence/source-acquisition/20261011/mops-pooled-http-release-proof.json)。

新runtime只對2027／2344／6861各一次既有正式 `source=financial_statements`，全部 **HTTP200、2021–2025完整五年**，實際耗時 **3.009／2.331／2.503秒**。三份各15JSON／3unit模板完整原件重新投影，五年九科目與數值一致；quote／TTM／原時間、其他data與source audit、HTML／Markdown、analysis evidence及五原品質metadata保留，index與artifact hash相符且analysis_text_stale=1。source-only修補不等於新報告品質通過。正式新增恰好3canonical父事件435237–435239及3筆DataProvider，57來源HTTP全部200，不把57個component算57次成功；原901reports／1110jobs／2qualityreviews保持。[3件完整正式讀回](evidence/source-acquisition/20261011/mops-pooled-http-three-formal-completion-proof.json)。

本輪當前原20類正式近24h仍 **18／20嚴格>80%**：財報 **90／166＝54.217%**、近期事件 **172／230＝74.783%**。三件真缺口已修補，但不能以3／3成功或研究76HTTP宣稱全系統突破80%、全部504／transport已解；原全部歷史與分母公式保留，窗口自然移出仍獨立看待。全20類goal仍active、此輪有實質progress。[完整正式SLA](evidence/source-acquisition/20261011/mops-pooled-http-three-after-formal-sla.json)。

部署後3件成果另完成唯讀獨立覆核，**1個隔離證據檢查通過**，重播45份JSON、51個distinct完整原件、135個年度必要數值與2筆比較修訂；原件保存、帳本與runtime身分相符，無未解material finding。158套件、queue／health等保護範圍依root封閉讀回核對，不冒稱reviewer另發live API／Redis request；three-case success不泛化成整體可靠度。[正式成果獨立覆核](evidence/source-acquisition/20261011/mops-pooled-http-three-independent-live-review.json)、[當前runtime與原20類最終讀回](evidence/source-acquisition/20261011/mops-pooled-http-final-current-check.json)、[最終正式SLA](evidence/source-acquisition/20261011/mops-pooled-http-final-current-sla.json)。

## 2026-10-11 南茂完整免費年報與SEC候選入口

為8150原2021缺項另找[南茂官網歷年年報](https://www.chipmos.com/english/ir/year.aspx)及[同公司官方申報導覽](https://www.chipmos.com/english/ir/shareholders.aspx)，各一次native匿名GET取得完整28,493／28,193bytes並封存讀回。年報列表的2022列實際公布[完整英文2022年報](https://www.chipmos.com/upfiles/ADUpload/english/en_ir_year_1760255301.pdf)，跟隨exact href只讀一次，取得 **2,298,787bytes／304頁**，原件hash與bytes一致，未重抓MOPS或已完整的3家。PDF第161／162頁（印刷157／158頁）完整合併現金流明示2022／2021及新台幣仟元；抽取與render均核對，仍未明示無形資產購置列，不能將缺列或其他非流動資產變動補為0／代替该科目。英文翻譯與公司財報不是新的獨立publisher。此完整免費文件入口尚未接入provider、未補齊8150五年資格，也不算source success。[完整native索引](evidence/source-acquisition/20261011/chipmos-8150-new-official-financial-index-native-research.json)、[完整native年報](evidence/source-acquisition/20261011/chipmos-8150-2022-published-full-annual-pdf-native-research.json)、[現金流原件與兩頁視覺核對](evidence/source-acquisition/20261011/chipmos-8150-2022-consolidated-cashflow-original-readback.json)。

官網同時明示8150的MOPS與IMOS的SEC入口；[SEC 2023年20-F索引](https://www.sec.gov/Archives/edgar/data/1123134/000095017024043516/0000950170-24-043516-index.htm)公布CIK0001123134、2023-12-31期末、2024-04-11申報日及exact document。Web研究索引不是native完整文件證據。一次普通匿名native GET該5,762,492bytes文件收到 **403 access_denied**，保留既有host冷卻且停止，不改header身分、不retry／proxy／cookie／redirect或找同一受拒文件鏡像绕過。先前Web開2022文件也只得到工具4MiB大小限制，不能冒稱已完整讀取。SEC目前僅候選，未證2021完整數值；這一段3個HTTP200原件及1個403研究請求，正式canonical／用量、report／job／model／qualityreview均未新增，原20類驗收保持。[SEC一次原生拒收與保留](evidence/source-acquisition/20261011/chipmos-8150-2023-SEC-published-full-filing-native-research.json)。

台灣時間08:48最後讀回仍同一已部署runtime、health／readyz200，三個source parents、完整原件投影、保護資料與六隊列保持。官網PDF及SEC研究後沒有額外正式canonical／DataProvider或模型呼叫；原20類仍18／20，財報90／166、近期172／230。[新入口研究後最後當前查驗](evidence/source-acquisition/20261011/mops-pooled-http-after-new-entry-final-current-check.json)、[完整正式SLA](evidence/source-acquisition/20261011/mops-pooled-http-after-new-entry-final-current-sla.json)。

## 2026-10-11 目前30日新聞窗口更新：21份各一次、19份目前足量

上一goal turn已正式部署一個MOPS連線改動並修補3家真年度缺口，屬progress；本輪沿同一72檔runtime重新唯讀盤點155家最新報告與原20類正式24h。31家在目前30日截止下未達原8筆／至少3發布者／公司門檻。排除10家已有source-only嘗試，另124家目前充分者不重抓；其餘21家只送一次既有免費 `source=recent_catalysts`，沒有新provider／backend／env變更或重載。[本輪正式基準](evidence/source-acquisition/20261011/post-pooled-next-source-optimization-baseline-sla.json)、[目前完整盤點](evidence/source-acquisition/20261011/post-pooled-current-latest-report-news-gap-inventory.json)、[21家當前窗口資格](evidence/source-acquisition/20261011/post-pooled-untried-news-real-gap-admission.json)。

獨立覆核補上必要的雙截止區分：20家在原snapshot的 `news_selection.selection_cutoff` 已通過8／3，隨時間移出窗口才形成目前不足；其18家成功更新、2855／1514兩家仍只取得7筆且原bundle逐位保持。6225缺原截止，不能判斷最初是否不足，本次目前窗口更新成功。前輪51件「原截止與目前截止都不足」的資格未套用到這20份renewal，也未冒稱該雙截止契約通過。原逐件helper沿用的 `original_strict_news_gap_recovered` 及 `original_search_gate_before` 名稱容易誤解，另存明確correction；逐件terminal proof、正式success／failure史與報告不改寫。這批是必要的目前窗口更新，不能當20個原報告初始取得失敗的可靠度修復。[逐件terminal進度](evidence/source-acquisition/20261011/post-pooled-untried-news-sequential-progress.json)、[原截止重播與語義更正](evidence/source-acquisition/20261011/post-pooled-untried-news-current-window-semantic-correction.json)。

21次正式請求中19 HTTP200、2 HTTP502；成功的當次source返回8筆並通過原公司／日期／3發布者門檻，保存的additional與原近期資料另按當下窗口重選，不將混入舊資料算作當次新取得。HTML／Markdown、analysis evidence、五品質metadata、quote／TTM／財報／社群、其他source audit與原core時間均保持，index四hash相符、analysis_text_stale=1，沒有新增analysis、model、job、report或qualityreview。全部69canonical events435240–435308及69筆DataProvider逐fetch關聯，只有21個新聞父觀測（19 success count8、2 degraded count7）；28Google RSS真HTTP200與20 GDELT／Yahoo原冷卻HTTP0分開。RSS索引／headline契約不是publisher全文、獨立發布者或事件影響驗真；本輪正式RSS完整body未另行封存，不稱原件重播。[完整報告保存與帳本核對](evidence/source-acquisition/20261011/post-pooled-untried-news-all21-formal-completion-proof.json)。

两件不足的Google RSS回傳量分別5／7及9／11，未碰20筆候選上限，目前沒有證據支持再擴上限來修復這兩家。GDELT及Yahoo RSS既有12次失敗冷卻保持，不清掉等待或換provider別名繞過。元大金2885另只檢視原sector payload：缺ticker，當前投影未通過，未確認可安全投影；其過去五年sector success不代表當前快照已完整投影，未重抓、修改或升格歷史來源。

本輪完成時原20類仍 **18／20嚴格>80%**；近期事件 **191／251＝76.096%**（基準172／230＝74.783%），財報 **90／166＝54.217%**。19／21的本輪更新成功率不代替原20類24h驗收；當前窗口更新帶來真新資料，但未證初始抓取品質、全部來源可靠度或新報告品質已通過。原13jobs／61dispatch、failure432041與129965舊zero prefix保持，901reports／1110jobs／2qualityreviews仍在。Goal仍active。

## 2026-10-11 殘餘1514的Bing RSS候選與原站拒收

[Bing官方歷史RSS說明](https://blogs.bing.com/search/2008/4/News-Search-%E2%80%93-now-with-RSS/)及先前樣本已證此為舊候選入口，不稱本輪新發現。針對目前1514未足量，僅一次普通匿名native GET實際RSS query，完整body封存讀回12items。從同一已保存bytes重建 `http／https www.bing.com/news/apiclick.aspx` query內明示原站URL，不實際跟隨tracking redirect；原helper只處理https wrapper，另存讀回收據修正。排除MSN的同篇轉載，原公司／RSS日期篩選有8個候選，仍是index時間，不宣稱原文章日期。未用這8個候選或與舊snapshot的union寫正式成功，也未啟用retired Bing Search API或新provider。[完整native RSS](evidence/source-acquisition/20261011/bing-news-1514-new-residual-full-RSS-native-research.json)、[原件href重建及轉載排除](evidence/source-acquisition/20261011/bing-news-1514-published-link-readback-and-candidate-boundaries.json)。

只對其中明示的中時20261011原文章做一次匿名GET以核原站日期，收到403 access_denied，保留host冷卻而停止，未補造原文日期、重試、代理、登入或追同篇鏡像。全8篇原站／日期尚未驗證，所以Bing來源仍OFF；這2個native研究請求沒有正式canonical／DataProvider、model或report寫入。下一步仍需合法可讀的原站日期與去重資格，不能只依索引有8items接入。[單篇原站拒收](evidence/source-acquisition/20261011/bing-news-1514-one-published-original-native-date-research.json)。

21件正式成果獨立覆核 **1個隔離證據檢查通過**，已核語義更正及21份terminal proof SHA未變，無未解material finding；18 renewal／2 renewal held／1原截止未知的分級保留。台灣時間09:12再讀正式原20類仍18／20，財報 **90／164＝54.878%**、近期 **188／245＝76.735%**。相對批次完成時90／166與191／251的差異是舊觀測移出24h窗口，不歸因RSS研究或新程式。本輪沒有backend改動或重載；72runtime／env／158packages、原PIDs、13jobs／61dispatch／failure432041／zero prefix129965、六隊列及scheduled0、health／readyz200皆核對。Goal仍active，本輪19份目前窗口新資料屬實質progress，未稱全系統80%或新報告品質通過。[獨立覆核](evidence/source-acquisition/20261011/post-pooled-untried-news-independent-live-review.json)、[最後當前查驗](evidence/source-acquisition/20261011/post-pooled-untried-news-final-current-check.json)、[完整正式SLA](evidence/source-acquisition/20261011/post-pooled-untried-news-final-current-sla.json)。

## 2026-10-11 金控原件 v2 正式修復及元大官網新入口

元大金2885最新報告的舊 `financial_institution_consolidated.v1` 保存五年 typed facts，但缺 ticker／report_scope／currency、各年範圍與完整 body；目前公共 projection 不通過，且通用2021 FCF缺值、無已驗證 financial_history_basis。此前7次官方success與1次ConnectError仍保留，不能把舊success等同目前consumer投影完整，也不能自行補造舊原件身分。已核此真目前缺口而只允許一次改契約後補件；先前已健康的2884／2887／5880不重抓。[單件資格](evidence/source-acquisition/20261011/holding-full-originals-2885-one-qualified-admission.json)。

新取得的金控資料用獨立 `financial_holding_consolidated.v2`，五份完整XHTML body封存／重讀／SHA／大小／URL股票年度Q4合併／TWD／taxonomy及比較修訂逐項重建；缺原件、改facts、異股票／範圍／單位等拒收，不退回legacy驗證。正常uncached與source-only均接入，淨收益不代填一般營收、毛利、營業利益；FCF仍受金融業使用邊界保護。獨立覆核先重現P2：完全刪除taxonomy／archive標記時，public prompt曾讓v2走facts-only；root再以真正public反例得到1 failed後修兩行，bank及v2均強制重驗，舊legacy保留。最终同次438 passed／1 skipped（optional private complete report replay未提供），獨立18 checks pass、無未解material finding。[真red／green與精確5檔manifest](evidence/source-acquisition/20261011/holding-full-originals-root-validation.json)、[獨立程式覆核](evidence/source-acquisition/20261011/holding-full-originals-independent-review.json)。

已沿正式 `start_mac.command` 溫和重載5 owned＋67 preserved＝72runtime檔；158packages／env、13jobs／61dispatch、failure432041及129985舊zero prefix（到435308）保持，六隊列／scheduled0，health／readyz200。不強制kill、不把dirty checkout其他成果覆寫或清理。[正式release](evidence/source-acquisition/20261011/holding-full-originals-release-proof.json)。

2885只一次正式 `source=financial_statements`：HTTP200／6.386秒，2021–2025完整typed projection及五份原件共4,874,997 bytes重播；2021 FCF history補齊，淨收益與一般營收保持不同欄位。唯一canonical父觀測435309、1筆DataProvider usage722633，沒有新model／analysis／job／report／qualityreview。原HTML／Markdown、analysis evidence、五品質metadata、quote／TTM／其他source audit與原core時間保持，index四hash相符、analysis_text_stale=1；補數據不冒稱原結論已重驗。底層HTTP總次數沒有telemetry，不能用mock的6次或五原件冒充已觀測實際請求數。[當次正式請求](evidence/source-acquisition/20261011/holding-full-originals-2885-formal-refresh-proof.json)、[全部原件、報告、帳本及目前runtime核對](evidence/source-acquisition/20261011/holding-full-originals-final-current-check.json)。

另找到[元大官網合併財報入口](https://www.yuanta.com/TW/IR/Financials/Financial-Reports)與[公司年報入口](https://www.yuanta.com/TW/IR/Financials/Annual-Reports)：普通匿名GET兩頁HTTP200並完整封存，從同一已保存HTML的literal JSON重建2021–2025五個合併Q4PDF連結及五個公司年報連結，不執行JS／猜API。2021合併財報另一次GET200、4,830,296 bytes／273頁完整原件讀回；封面2885／110及109年度／合併，頁16–17現金流單位TWD仟元視覺核對，原三個CF值與此次2021 iXBRL原件相符。2022 PDF第一次下載已超既有8MiB封存上限而停止，未封存完整body；精確總bytes及HTTP狀態未記錄，不假称200。2023–2025未下載，沒有同輸入重試、登入、cookies、proxy或放寬原件上限。總共4個native研究請求，入口仍OFF／無正式SLA成功；尚無完整五年PDF數值projector，不能稱備援已接入或五份PDF完整可得。[索引完整原件](evidence/source-acquisition/20261011/yuanta-2885-official-ir-published-index-native-research.json)、[同bytes五年連結讀回](evidence/source-acquisition/20261011/yuanta-2885-official-ir-five-year-published-links-from-saved-originals.json)、[2021全文原件](evidence/source-acquisition/20261011/yuanta-2885-2021-consolidated-pdf-one-native-research.json)、[新入口實際邊界](evidence/source-acquisition/20261011/yuanta-2885-new-official-ir-entry-current-boundaries.json)。

本次最後正式24h原20類仍 **18／20嚴格>80%**；財報 **91／165＝55.152%**、近期事件 **188／245＝76.735%**。本次一次真補件有進展，但1／1不是全20類驗收，研究PDF與隔離tests不加入正式success。Goal仍active，quality gate／公式／歷史／分類／TTL／cache／provider保護未改，原缺項不補零。[完整正式SLA](evidence/source-acquisition/20261011/holding-full-originals-final-current-sla.json)。

正式成果另由獨立唯讀輸出與1個隔離證據檢查通過，五份XHTML／50個年度原科目／1筆2024比較修訂、報告保留、單一parent／DataProvider與研究OFF分級均核對；無未解material finding。新holding五個archive path不入public prompt；整份formatter仍有before／after皆相同的既有SDK診斷path，不宣稱全域prompt隱私已檢查。reviewer重播PDF完整bytes並比對root保存的頁16–17手動數字，未另做PDF視覺重驗。[獨立正式成果覆核](evidence/source-acquisition/20261011/holding-full-originals-independent-live-review.json)。

收尾再讀正式窗口（2026-10-11T09:44:13.174575+08:00）仍18／20：財報 91／163＝55.828%、近期 184／239＝76.987%。與前一次91／165、188／245的變動是原觀測移出24h；ledger最大435309及usage722633保持，這段沒有再送來源或模型請求。新runtime／env／158packages、六隊列0與health／readyz200保持，Goal active。[最後當前收尾](evidence/source-acquisition/20261011/holding-full-originals-closeout-proof.json)、[最新完整SLA](evidence/source-acquisition/20261011/holding-full-originals-closeout-current-sla.json)。

## 2026-10-11 Gogolook 官方身分核對、免費品牌查詢與單件零新聞缺口補齊

本輪再唯讀重選155家最新快照，12家目前窗口仍不足，其餘健康者不重抓。6902原 saved recent／additional 都是0筆，所以此次不是舊窗口已充分的renewal。先各一次匿名native研究取得完整TWSE公司名冊與新查詢 `"Gogolook" 6902 when:30d` 的Google RSS；官方row為6902／GOGOLOOK／走著瞧股份有限公司／53755364，RSS完整11,513bytes／9items封存讀回。舊名稱選擇器只留5筆，新局部品牌識別可留8筆與5個來源標識；第9筆仍 issuer_unverified，不改成歷史或合格。此兩次研究不是正式SLA成功；也不是新增Google provider、全文新聞或獨立出版社驗真。[目前完整盤點](evidence/source-acquisition/20261011/post-holding-current-latest-report-news-gap-inventory.json)、[官方名冊原件](evidence/source-acquisition/20261011/post-holding-news-issuer-labels-official-roster-native-research.json)、[唯一品牌新查詢原件](evidence/source-acquisition/20261011/post-holding-gogolook-verified-brand-query-one-native-RSS-research.json)。

只改三個既有檔案：`company_news_queries` 定義 context-bound alias；`source_content_selection` 只在合格6902 context的局部alias projection加入Gogolook；`external_search_providers` 讓既有兩個query都使用這個已核品牌且保留股票代號／30日窗口。ticker／identity ticker／stock_id／商品類型／official name需一致，legal name／UBN如有矛盾拒收；不加入常見中文片語「走著瞧」，不全面去掉創／KY後綴，不回寫既有company identity。獨立覆核先發現禁止別名格式可漏驗，root以8個真正public red反例後修復；明示壞容器／非字串及HTML、星號、全形Gogolook禁止標記均拒收。原預算、兩query、8筆／至少3來源、公司／日期資格、fallback／cache TTL／cooldown與disabled candidates保持。[精確before／after範圍及red證據](evidence/source-acquisition/20261011/gogolook-query-after-review-independent-input.json)、[獨立程式覆核](evidence/source-acquisition/20261011/gogolook-query-independent-review.json)。

最終root相關測試179 passed、broader209 passed；兩組有重疊，不能稱388個distinct tests。獨立31個檢查通過、無未解material finding。正式graceful重載3 owned＋70 preserved＝73runtime檔（既有company_news_queries原未列入舊72檔manifest，已以exact before backup納入），env與158packages保持；launcher99085／role-all worker99113／API99115，health／readyz200。原13jobs／61dispatch、failure432041及129985舊zero rows through435309核對一致，六隊列／scheduled0，無force kill／dependency upgrade。[正式重載與保留證據](evidence/source-acquisition/20261011/gogolook-query-release-proof.json)。

只對具有因果不同的新query／selector條件的6902送一次既有正式 `source=recent_catalysts`：HTTP200／4.481秒，新取得8筆通過原8／3與公司／日期gate。6個reported publisher/source labels不稱六家獨立新聞機構，當次RSS原body未另封存，研究raw不替代正式原件。原HTML／Markdown、analysis evidence、五品質metadata、quote／TTM／財報／社群、其他source audit與原core時間保持，index四hash一致，analysis_text_stale=1；不是新分析或結論品質重新通過。`valid_recent_receipt`既有60秒是當次admission age，收尾只在已保存return epoch本地重播該檢查，再以真目前時間重選8筆；初次收尾直接用現在時間的預期拒收不是新的provider失敗，也沒有放寬或改runtime時計。[單件真缺口資格](evidence/source-acquisition/20261011/gogolook-query-6902-one-qualified-admission.json)、[當次正式terminal proof](evidence/source-acquisition/20261011/gogolook-query-6902-formal-refresh-proof.json)。

正式新增5個canonical events435310–435314及5筆同fetch的Data Provider usage722634–722638，但只有435314一個recent_catalysts success parent/count8；兩個Google RSS真HTTP200，另兩個GDELT／Yahoo是既有cooldown且http_request_sent=false，不把舊Yahoo http_status500當本次HTTP請求。無新model／analysis／job／report／qualityreview；原901reports／1110jobs／2qualityreviews保持。[完整artifact、帳本及目前runtime查驗](evidence/source-acquisition/20261011/gogolook-query-final-current-check.json)。

當前正式近24h原20類仍 **18／20嚴格>80%**：財報 **91／163＝55.828%**、近期事件 **185／240＝77.083%**；比較同窗前184／239，本輪恰新增1真新聞成功。研究／tests／child HTTP均不加入父成功分子。未達全20類80%，Goal仍active，本輪部署與原零資料缺口修復屬實質progress。Bing／SEC等舊拒收、缺科目與未滿五年案例仍保留，不重試同一失敗輸入、不補零、不重抓健康公司。[完整正式SLA](evidence/source-acquisition/20261011/gogolook-query-final-current-sla.json)。

正式成果再經唯讀獨立覆核與1個隔離證據檢查通過：mode=ro／query_only讀目前bundle、index、同fetch帳本、保存native fixtures與sealed SLA，無API／provider／model／Redis request或runtime mutation。當次return epoch的receipt與真目前窗口8／3分開驗證，原零新聞、core時間與所有保留項相符，無未解material finding；root health／ready／queues讀回不冒稱reviewer另送live request。最後root再次核73runtime／env／158packages／PIDs與六隊列0，仍18／20、財報91／163、近期185／240，canonical max435314／usage722638後未新增來源或模型請求。[正式成果獨立覆核](evidence/source-acquisition/20261011/gogolook-query-independent-live-review.json)、[最後當前收尾](evidence/source-acquisition/20261011/gogolook-query-closeout-proof.json)、[最後完整SLA](evidence/source-acquisition/20261011/gogolook-query-closeout-current-sla.json)。

## 2026-10-11 兆豐金完整公開JSON新入口及整批重試邊界修復

上一輪6902正式修復屬progress。本輪重讀155家最新快照，按一般科目有94家充分、另14家金融業完整typed投影，均不重抓；40家一般年度仍有缺項／期間問題、3家金融業typed缺口及4個目前context未准案例保留。兆豐金2886雖有舊五個年度陣列，沒有sector_specific_financials／financial_history_basis，原官方失敗為`duplicate XBRL context`；不能把部分SDK／FinMind陣列當全部10金融科目與原件已驗。新入口的正式資格是這個真typed／原件缺口，不是健康公司原件升格。[完整目前盘點](evidence/source-acquisition/20261011/post-gogolook-all155-annual-inventory.json)、[金融業型別重驗](evidence/source-acquisition/20261011/post-gogolook-all155-typed-annual-gaps.json)、[單件正式資格](evidence/source-acquisition/20261011/public-holding-UI-2886-one-qualified-admission.json)。

先研究兩個新免費官網：[南電財務資訊](https://www.nanyapcb.com.tw/nypcb/chinese/InvestorRelations/FinancialReports)与[晟鈦財報列表](https://www.cheer-time.com.tw/index.php?d=41&g=14&view=news)，各一次native HTTP200完整91,351／27,641bytes封存。南電同bytes明列2021–2025五個合併年度PDF href，但只下載一次2022原件，HTTP200／4,872,325bytes／53頁；封面8046與2022／2021合併身分核對，PDF第10／11頁（印刷8／8-1）完整視覺核對仍沒有明列無形資產購置。其他非流動資產增加不代該科目，不補零；掃描表沒有extractable文字，最初text scan的第2頁只是目錄，另存更正。晟鈦当前native列表未找到2021／2022年度href，不能推論文件從未存在。兩入口仍研究OFF，未接provider或算正式成功；初次網搜南亞塑膠母公司頁沒有混到南電。[完整native索引](evidence/source-acquisition/20261011/nanya8046-cheertime3229-new-free-annual-index-native-research.json)、[南電完整PDF](evidence/source-acquisition/20261011/nanya8046-published-2022-full-consolidated-pdf-native-research.json)、[原件視覺資格與目錄更正](evidence/source-acquisition/20261011/nanya8046-2022-cashflow-original-visual-qualification.json)。

對2886另查與舊iXBRL不同的[MOPS公開合併三表UI](https://mops.twse.com.tw/mops/#/web/t164sb03)：2025三表各一次native HTTP200，完整JSON含原10科目。只追加尚未讀過的2021–2024三表及published index；初次在2023 balance的null未選子公司ID／三期column layout資格停止後，保留全部已取得raw，不重抓；用exact已保存metadata核對同股票C與第三期為前一年1月1日期初餘額，再讀餘下5份未取得原件。2025的3份、初次8次與續段5次共 **16 native HTTP**；15完整JSON、1完整published index及重用3份既有完整unit JS原件，共19原件、50原科目及40比較值。3unit JS的full-byte fingerprints沿原官方renderer，TWD仟元／calendar契約未放寬，重用不續期也不算新HTTP。沿原financial reconciler完整比較數取得5筆修訂；研究全部未寫正式SLA／usage／model。[首年新入口](evidence/source-acquisition/20261011/mega2886-financial-holding-public-JSON-first-year-native-research.json)、[初次layout拒收保留](evidence/source-acquisition/20261011/mega2886-public-JSON-five-year-ten-fact-qualified-research.json)、[保存原件重播及完整五年研究](evidence/source-acquisition/20261011/mega2886-public-JSON-five-year-ten-fact-qualified-research-v2.json)。

新 `mops_public_holding.py` 定義獨立`financial_holding_public_annual.v1`，目前只認已證2886 layout，沒有全面啟用其他金控／銀行，也沒有假裝新JSON是iXBRL。consumer逐次重讀15JSON／3unit template／index，核股票reference、合併C、年度Q4、幣別契約、10明示科目、SHA／bytes／取得日及比較修訂；親公司淨利與權益保持原科目，淨收益獨立、不代一般營收／毛利／營業利益，金融DCF限制保留。三期balance取明示當期及前期12月31日，不取期初欄；equity同label的exact全空heading只當非金額標題，兩金額列／兩heading／partial empty／dash／bool仍拒。新schema即使刪除所有marker也強制完整驗證，不退facts-only。指定source-only與normal SDK皆接入，完整時免多做SDK／FinMind；其他股票、普通JSON、bank／broker／insurer／legacy原契約、cache／TTL／公式及source gates保持。[精確before及五檔scope](evidence/source-acquisition/20261011/public-holding-UI-owned-before.json)。

真正public red先觀察新schema不能投影：1 failed／8 expected denial pass。獨立覆核另找到P2：未知TypeError或取得19份後cleanup RuntimeError，原直接`audited_fetch(lambda)`會把全批重做並變success（20／38 components）。root再以兩public red重現，修成與普通入口一致的nonretryable acquire boundary；既有FilingError／SourceResponseError保留，未知本機／cleanup例外只一次整批、保留1／19 components且valueNone。不改shared retry／circuit／throttle规则、不清正式保护。最终root **231 affected**、另 **107 broader**通過，分別列結果，不在未核node IDs時加總成distinct；獨立owned31＋3反例同次 **34 passed**，無未解material finding。最初測試的兩integration failures是isolated合成429跨case殘留，僅在先核tmp runner DB的fixture清本provider，與production保护无關。[最終精確diff／red／green](evidence/source-acquisition/20261011/public-holding-UI-after-review-input.json)、[獨立程式覆核及初次失敗](evidence/source-acquisition/20261011/public-holding-UI-independent-review.json)。

已graceful重載5 owned＋69 preserved＝74runtime檔，launcher8033／role-all worker8061／API8063，health／readyz200。env／158packages、13原jobs／61dispatch、failure432041與129987舊zero prefix through435314核對保持，六隊列／scheduled0，無force kill／dependency upgrade。啟動UI原cold daily quality dashboard仍一次503；本財報入口未處理該問題。[正式reload與保留](evidence/source-acquisition/20261011/public-holding-UI-release-proof.json)。

2886只一次正式 `source=financial_statements`，**HTTP200／3.905秒**，完整五年50科目／40比較值及5修訂採用；19份完整原件可重播，15JSON合計103,652bytes，含3unit與index總 **153,974bytes**。實際19來源HTTP皆200，只新增canonical **435315一個父success／count5**及一筆Data Provider，不當19父成功。原HTML／Markdown、analysis evidence、五品質metadata、quote／TTM、其他source audit與原core時間保持，index四hash一致、analysis_text_stale=1；不是新model／analysis／job／report／qualityreview或新結論已重驗。oldXBRL duplicate拒收歷史保留，不重送相同XBRL查詢。[正式單次terminal proof](evidence/source-acquisition/20261011/public-holding-UI-2886-formal-refresh-proof.json)、[全部原件、artifact、帳本與runtime核對](evidence/source-acquisition/20261011/public-holding-UI-final-current-check.json)。

当下近24h原20類仍 **18／20嚴格>80%**：財報 **91／163＝55.828%**、近期事件 **183／235＝77.872%**。相對turn初91／163與185／240，窗口旧觀測移出另看：本轮恰新增一個financial parent，沒有抓新聞，不能將新聞率變動或財報分母變動歸因新入口。研究／隔離tests／19個child HTTP不加正式父成功分子；全20類尚未達標，Goal保持active，本輪新增完整可用入口、正式修補及no-whole-retry修復屬progress。[完整正式SLA](evidence/source-acquisition/20261011/public-holding-UI-final-current-sla.json)。

正式成果已完成唯讀獨立覆核：19份完整原件共153,974bytes逐份讀回，以獨立Decimal仟元換算核50個當期科目與40個比較值，再重播5筆修訂、typed投影及金融DCF邊界，1項隔離證據檢查通過，無未解material finding。原artifact、五品質metadata、quote／TTM與時間、index、帳本及runtime保留均核對；這是source-only資料補件成功，不是新的報告品質結論。最後再次以真現在時間讀正式近24h面板，仍財報91／163、近期183／235、18／20；74檔runtime／env／套件、六隊列、舊零值觀測與保留job／dispatch未漂移，沒有追加來源取得或模型呼叫。[獨立正式覆核](evidence/source-acquisition/20261011/public-holding-UI-independent-live-review.json)、[最後讀回證據](evidence/source-acquisition/20261011/public-holding-UI-closeout-proof.json)、[最後正式SLA](evidence/source-acquisition/20261011/public-holding-UI-closeout-current-sla.json)。

## 2026-10-11 新金融業入口缺口與完整JSON驗證失敗的短暫重用

續輪另對凱基金2883、遠東銀2845尚未補齊的快照，各一次讀新的官方公開UI三表，共6個native HTTP200，完整原件與股票／2025／2024合併欄位保存。兩家現金流表均未明列無形資產購置，其他投資活動或其他資產增加不能代填，故沒有啟用新金融業layout、下載其他年度或送相同失敗正式補件。銀行損益表兩列同名「母公司業主」分屬淨利與綜合損益，也不以第一個同名列概括接受。[六份新原件](evidence/source-acquisition/20261011/kgi2883-feib2845-new-financial-public-UI-first-year-native-research.json)、[必要科目資格拒收](evidence/source-acquisition/20261011/kgi2883-feib2845-public-UI-required-facts-qualification-held.json)。

鴻準2354、騰輝電子6672各一次研究不同於舊iXBRL的公開JSON入口，兩批均19個HTTP200、索引／3單位模板／15完整JSON保存；仍重現2024／2022比較數缺項衝突，沒有把取得完整body當成五年必要事實成功。研究期間canonical SLA及API用量保持，原iXBRL拒收史不改写。[兩批新公開原件](evidence/source-acquisition/20261011/2354-6672-distinct-ordinary-public-UI-complete-native-research.json)。

發現原 `official_financial_gap_cache` 的300秒缺口重用只適用explicit legacy fetcher，新公開入口直接繞過，會在相同已驗缺口上再次下載全批19份。新增 `mops_public_gap_cache.py`，由原公開入口共用：只有19份完整原件逐份核URL／request／issuer／HTTP200／SHA／bytes／原取得時間，再沿同一collector重播仍是完全相同的年度必要科目缺項或不完整比較數衝突才重用；cache保留原失敗、None／count0及原fetched_at，warm用新correlation、HTTP0／attempt0與empty_cache_count，不是新成功或又一次provider失敗。原300秒重查、TTL、歷史與SLA公式保持；取得不全、壞scope／metadata、quota／transport、未知例外及cleanup失敗不當issuer gap。

首個public red確認第二次仍19次下载。另以真紅修復cache讀取暫失效後來源已恢復卻留old gap；成功清除同key、寫入失败仍維持原來源退路。獨立覆核的3個反例重現錯型component逃出fallback，以及完整原件重播途中超過原300秒或同monotonic deadline仍採warm；加入明示dict驗證與重播後同期限重查，replay timeout亦回原取得，不以保存缺口阻擋已過期的新查詢。30永久case及相關入口root **182 passed**，另broader **131 passed**分開記、不加總distinct；首次failed logs與修正scope均保留，正式部署及live結果另列。[精確before](evidence/source-acquisition/20261011/public-annual-gap-cache-owned-before.json)、[首次獨立問題](evidence/source-acquisition/20261011/public-annual-gap-cache-independent-review.json)、[修正版scope及紅綠](evidence/source-acquisition/20261011/public-annual-gap-cache-after-review-final-input.json)。

修正版程式獨立覆核 **33 passed**、無未解material finding後，已正式graceful重載2 owned＋73 preserved＝75檔，launcher14856／role-all worker14884／API14886，health／readyz200。原env／158套件、13jobs／61dispatch、failure432041及129987個舊零值觀測through435315保持，六隊列／scheduled0，沒有forcekill或dependency upgrade。[修正版獨立覆核](evidence/source-acquisition/20261011/public-annual-gap-cache-independent-fixed-review.json)、[正式部署](evidence/source-acquisition/20261011/public-annual-gap-cache-release-proof.json)。

正式live驗證用原四年快照缺口的士電1503、之前未嘗試的不同公開JSON表示。先一次native research沿新入口，2.368秒取得19個HTTP200／19完整原件共129,511bytes，仍為`annual XBRL facts are incomplete for 2021`；由同collector重播確認後自動存原300秒gap，這次research沒有寫canonical SLA／usage。隨即唯一一次正式source-only請求 **502／0.07326秒／實際來源HTTP0**，canonical435316仍error／count0，分類empty_cache_count及attempt0、新fetchID；一筆DataProvider722640不是模型。原三artifact完全一樣，current四indexhash一致，原品質metadata／quote／TTM／時間保持；root在當場另assert完整row與before相同，但before全row沒有獨立序列化，不能稱後續獨立完整before-row比對。gap原取得日及retry不續，沒有再下載相同失敗資料，不把saved gap、研究或HTTP200當成功。[native及正式單次證據](evidence/source-acquisition/20261011/public-annual-gap-cache-1503-native-and-formal-proof.json)、[所有原件、帳本與runtime最後讀回](evidence/source-acquisition/20261011/public-annual-gap-cache-closeout-proof.json)。

最新近24h原20類仍18／20嚴格>80%，財報91／163＝55.828%、近期183／235＝77.872%；本輪沒有新增取得成功，也沒有重寫舊failure、成功率公式或將cached error算新分子。實際改善是新公開來源已驗缺口不在五分鐘內重複花19次下載；所有資料缺口及整體>80%目标仍保留，新增免費入口研究、完整重播與已部署live HTTP0驗證屬progress。[最新正式SLA](evidence/source-acquisition/20261011/public-annual-gap-cache-closeout-current-sla.json)。

正式結果已再獨立唯讀覆核：19原件129,511bytes讀回並复制到私有fixture沿同collector驗exact2021缺口，1項隔離證據檢查通過；研究fetchID在正式SLA／usage均0，唯一435316是empty_cache_count，原stamp至正式created_at只有0.08734秒，沒有修改runtime時鐘或重填過期cache。原三artifact逐位保存及current四indexhash、75runtime／env／隊列／job／dispatch／舊failure與零值前綴均核對。用同一時間窗對有／無435316重算，正式fetch分子／分母相同，沒有把預期502藏成成功；無未解material finding。全20類驗收仍未完成。[獨立正式覆核](evidence/source-acquisition/20261011/public-annual-gap-cache-independent-live-review.json)、[目前狀態再核對](evidence/source-acquisition/20261011/public-annual-gap-cache-final-current-proof.json)。

## 2026-10-11 再查十三個財報缺口與Bing原文資格

中砂1560、南亞1303、信邦3023先前只有iXBRL缺項紀錄，另各一次取得未試過的公開JSON三表，共57個native HTTP200。索引／3單位模板／15JSON全部封存及原collector重播，三家2021皆只有8個明示必要科目，仍缺gross intangible cash purchase；中砂與南亞五年均未提供該科目，信邦仍缺2021／2022／2025。不能以其他非流動資產增加、資產餘額或處分／淨變動填gross purchase或0。信邦2025「處分無形資產」列為負值且比較值與2024購置相同，只能保留語意疑點，未當購置採用或稱公司報表已證錯；三件未送相同失敗正式補件。[57完整原件](evidence/source-acquisition/20261011/1560-1303-3023-new-public-annual-complete-native-research.json)、[必要科目與比較值重播](evidence/source-acquisition/20261011/1560-1303-3023-new-public-annual-required-facts-qualification.json)。

再讀信邦搜尋索引指向的完整文件：bare hostname回302後保留，不重送同URL；用當期官網的www hostname作明示canonical hypothesis，一次匿名普通TLS取得 **1,525,528bytes／84頁**完整PDF。沒有聲稱native索引href已驗，也不以檔名2022推年度；實際是2022召開的股東會文件，附2021／2020合併財報。渲染及完整查看第21、25、26頁核公司／consolidated／NTD thousands，2021 OCF、PPE及assets與新MOPS原件相符，但所列intangible decrease／other noncurrent increase仍不明示gross acquisition，保持未知、不補0；英文翻譯不增publisher。初次helper成功分支未填top-level http_status的限制另註，成功transport invariants與完整raw_receipt均驗HTTP200，不把缺頂層欄當新HTTP失敗。[完整文件native收據](evidence/source-acquisition/20261011/sinbon3023-canonical-www-complete-financial-original-native-research.json)、[完整頁面與科目資格](evidence/source-acquisition/20261011/sinbon3023-complete-booklet-original-visual-financial-qualification.json)。

新聞另以1514保存的Allis Electric名稱作新OR查詢，沒有重送原「亞力1514」query；Bing News RSS一次HTTP200只有6個raw／2個company-time候選，仍不足原8／3。使用先前feed公布的三個未讀原文URL，經濟日報、三立各一次HTTP200完整266,167／171,811bytes，東森一次403即停止，沒有重送舊CT403、碰Yahoo保護、使用mirror／proxy／特殊cookie或啟用已停用Bing API。經濟日報JSON-LD及主本文日期可核；三立RSS「散熱三雄」與原文「逆變器」headline不符，且原文JSON-LD的UTC聲明與可見naive日期時間需分開，未把RSS／sidebar／改稿日當已驗原文發布時刻。原文皆保留內部，不向報告転載全文，來源仍OFF，不能算8條新聞或新正式成功。[不同別名query](evidence/source-acquisition/20261011/bing-news-1514-bound-english-alias-full-RSS-native-research.json)、[三個新原文讀取](evidence/source-acquisition/20261011/bing-news-1514-three-unread-original-articles-native-date-research.json)、[標題／日期與拒收資格](evidence/source-acquisition/20261011/bing-news-1514-original-title-date-qualification-held.json)。

為避免每件都再下載19份，接著只讀三陽2206、運錩2069、大聯大3702、材料4763、禾伸堂3026、華航2610、台塑化6505、臻鼎4958、全友2305、高力8996尚未試過的2021／2022兩份公開現金流原件。沿同批45秒、原每份5秒／host protection、原context與unit fingerprint，重用先前完整unit bytes不續期；20個HTTP200完整封存，兩期都未提供可補最早2021的gross intangible purchase，十件均停止後續全套查詢。這僅是研究admission節省查詢，未修改production collector先後順序或把兩份CF當完整五年；沒有宣稱假設會花190次HTTP的量測節省百分比。[二十份新現金流原件及停止理由](evidence/source-acquisition/20261011/ten-remaining-earliest-cashflow-new-entry-native-probes.json)。

前半輪63次native（57三表、1 bare302、1完整PDF、1 RSS、2文章200、1文章403），追加20份CF合計83次研究；皆沒有新增canonical／APIusage／model／job／report／qualityreview、正式補件或backend變更。75runtime／env／原13jobs／61dispatch與歷史失敗／零值保持，健康／ready200；原20類仍18／20，財報91／163＝55.828%、近期183／235＝77.872%。新完整入口與科目／原文披露限制改變後續查找方向，不能將研究原件量代替全類80%成功。原goal保持active。[前半輪原件及正式狀態讀回](evidence/source-acquisition/20261011/three-financial-and-bing-originals-final-research-proof.json)。

本輪後續找到中砂官方公布的[110年度完整年報](https://www.kinik.com.tw/upload/Investors/AnnualReport/%E5%B9%B4%E5%A0%B1110.pdf)，網址來自公開索引而非猜檔名。只做一次普通匿名、原TLS／5秒／8MiB上限的native下載；回應HTTP200但transport_error，沒有完整原件收據，具體傳輸原因未由研究收據保存，不能推定為大小、TLS或逾時。網路搜尋能讀到255頁不等於正式機器取得成功；不重試、換鏡像或放寬transport。[一次native不完整下載](evidence/source-acquisition/20261011/kinik1560-indexed-2021-complete-annual-original-native-research.json)。

亞力再只讀原Bing feed明示、尚未讀過的兩個UDN原文，均HTTP200且完整265,610／190,620bytes。NewsArticle的URL／mainEntity／headline與原文、主本文1514／亞力、aware datePublished及可見主文日期可核；改稿時間與sidebar時間未充當發布日期。經濟日報原文2026-10-08T00:05:01+08:00，聯合新聞網原文2026-09-24T00:59:18+08:00。兩者同屬聯合報系，且營收新聞不冒稱新的獨立催化事件；合計四份完整原文只有三份發布時刻明確，三立標題錯配與時區疑點保留，至多兩個publisher families，尚不符8／3。研究DOM helper首次使用不適用經濟日報的selector失敗，保留舊helper後，僅對同一保存bytes辨識實際主文容器重播，不多發HTTP或修改production parser。[兩篇完整原文](evidence/source-acquisition/20261011/bing-news-1514-last-two-unread-UDN-originals-native-research.json)、[主文與日期資格](evidence/source-acquisition/20261011/bing-news-1514-last-originals-title-date-qualification-held.json)。

另查[亞力官方新聞索引](https://www.allis.com.tw/zh-tw/news.html)，web搜尋目前看見最新2026-09-01，已在30日窗口外；未對全站native遍歷，不能宣稱全站沒有更新。中央社仍受前述RSS非商業使用條件限制，未繞到tag頁做批次native取得。南亞官方財報頁雖提供年度選擇，未新增native下載；這些web索引發現不算完整來源或正式成功。

截至2026-10-11 12:15臺灣時間，本輪86次native研究、83份完整body收據讀回；其餘是bare302、EBC403及中砂HTTP200但傳輸未完成。75個runtime檔／env／158packages／PIDs、六隊列、原13jobs／61dispatch與failure432041／129,987筆歷史零值保持，health／ready200；canonical最高435316、usage最高722640、reports901／jobs1110／qualityreviews2均沒有本輪新增。財報91／163＝55.828%、近期183／235＝77.872%，原20類18／20，整體目標未完成。[86次研究與正式狀態結案證據](evidence/source-acquisition/20261011/extended-thirteen-financial-and-four-news-originals-research-closeout.json)、[同時點原20類面板](evidence/source-acquisition/20261011/extended-thirteen-financial-and-four-news-originals-current-sla.json)。

已提供可審閱的[八項核心財報選項](source-annual-core-options-2026-10-11.md)：部分核心資料與完整財報須明確區別，缺項保持未知、完整現金流未驗不得放行DCF；若選擇調整成功範圍，須明示新含義，不沿原九項判定宣稱達標。尚未收到範圍選擇、實作或啟用，正式判定沿用原標準。本輪只做來源研究及文件，不重跑backend tests，也不冒稱新報告品質已通過。

## 2026-10-11 巨鎧精密明確別名修正：正式補件已驗

上一輪新增完整原件／標題與日期資格，改變後續查找方向，屬研究進展，未取得新的正式成功。這輪不繼續抓十三家相同缺項三表，改查其他解析／身分分支：天瀚6225已保存2021現金流明示無形資產購置但沒有設備購置，新增一次2022CF仍沒有明示前一年設備購置，原解析缺口不能填0，未修改parser；彰源2030原iXBRL／比較頁失敗，首次分別讀公開JSON2021／2022CF，共兩個HTTP200，仍未明示最早年度無形資產購置，停止全套／正式補件。[天瀚新次年CF](evidence/source-acquisition/20261011/aiplex6225-unread-next-year-cashflow-purchase-qualification.json)、[彰源兩份新原件](evidence/source-acquisition/20261011/froch2030-new-earliest-public-cashflow-entry-probes.json)。

重用同一份完整TWSE主檔原時間／hash，核對2254巨鎧精密-創、54297090、巨鎧精密工業股份有限公司；6924榮惠-KY創與6550北極星藥業-KY各自不同公司／統編，不能全域刪除板別或KY。各擬一個新且不同於原失敗查詢的code／30日query；2254與6550各一次native RSS200，6924因保存的identity缺instrument_type在網路前拒收，未補造型別或清舊保護。2254原比對7／新增明確「巨鎧精密」8筆，CMoney不同名稱合併後仍有中時、富聯網及CMoney三個family；6550新增別名只7筆，未接入。這是既有免費Google RSS的新查詢，不是新provider，也不啟用retired API／CNA／已拒入口。[主檔／stock code／統編綁定及完整RSS](evidence/source-acquisition/20261011/three-stock-code-legal-UBN-bound-news-alias-new-RSS-research.json)。

`company_news_queries.py` 只增加2254的明確context mapping，原6902規則、forbidden清理、其他股查詢、8／3、30日與最多兩查詢保持。真RSS及完整主檔放portable fixtures；首個fixture建立發現舊Gogolook主檔bytes與本次master不同而停止，該setup failure不當TDD red，另保存本次完整主檔，沒有替換舊fixture。有效行為red為2 failed／16 passed，focused修正後56 passed；broader117 passed／2失敗，完全相同兩個query舊預期亦在exact-before私有副本重現2 failed／1 passed，未改那些tests或他股行為。補件前按當前時間重選6筆；獨立live覆核發現原保存的結論時間與新聞截止時間都有值，分別重選均7筆。先前proof的「原截止缺失」描述不正確，另存更正收據，不改原proof或ledger；原逐字analysis_input capture未保存，不能據此重建當時模型輸入或判定整份原報告品質。[scoped input／差異與檢查](evidence/source-acquisition/20261011/coplus-news-alias-independent-input.json)、[單件正式資格](evidence/source-acquisition/20261011/coplus-news-alias-2254-one-qualified-admission.json)、[截止時間更正](evidence/source-acquisition/20261011/coplus-news-alias-original-cutoff-correction.json)。

獨立code／離線原件覆核106項通過、無未解material finding；只將一個company query檔與74個原runtime／env一併核對後，沿canonical入口優雅重載，RedisBGSAVE、158packages、原13jobs／61dispatch、failure432041與至435316的129,988筆原零值保持，沒有forcekill或清冷卻。新launcher32772／role-all worker32800／API32802，health／ready200；canonical session51612保持運行。[獨立code覆核](evidence/source-acquisition/20261011/coplus-news-alias-independent-review.json)、[實際重載](evidence/source-acquisition/20261011/coplus-news-alias-release-proof.json)。

只對原2254真目前缺口送一次正式source-only request，HTTP200／1.957951秒。原目前6筆；此次父觀測435321明確取得8筆，去重合併保存的一筆舊資料後總可用9筆，不能稱九筆都是本次新取得。兩個Google原請求435317／435320為HTTP200，GDELT／Yahoo435318／435319仍是原冷卻HTTPFalse，沒有新transport拒收；五個DataProvider usage、無模型／新job／新report／qualityreview。其他quote／TTM／金融／社群／核心時間、HTML／Markdown與五gate／analysis input保持，index四hash可核，stale1仍需重新分析正文。正式RSS完整raw未另封存，研究RSS不能冒充這次formal response；publisher labels不代表各原文全文／首次發布時刻／事件影響已證真。[單次正式補件](evidence/source-acquisition/20261011/coplus-news-alias-2254-formal-refresh-proof.json)、[當前完整核對](evidence/source-acquisition/20261011/coplus-news-alias-final-current-check.json)。

既有30日背景retention繼續運行，整體report計數901→898、job1110→1109，不能假稱全部計數未變。Oct8備份讀回三份3105舊報告與一筆已結束job都符合當前30日到期條件；沒有手動刪除或修改retention。未保存全部preflight IDs、亦無逐刪execution log，所以備份／既有maintenance code只支持相符原因，未單獨證明全before差異及確切執行因果；原13個保護job／61dispatch、此次2254全部bundle與原provider ledger均逐筆保持，新created job及report為0。最初readonly checker把901當常數而停止，保留舊checker後改為核對實際新建數及特定不變條件，沒有重試正式補件。[計數與retention資格限制](evidence/source-acquisition/20261011/coplus-news-alias-current-retention-count-qualification.json)。

正式原20類仍18／20嚴格>80%，財報91／163＝55.828%，近期184／236＝77.966%。本輪新研究只有五次native（天瀚1／彰源2／兩公司Google2）；6924在網路前因缺明確identity型別拒收，不混算第三次RSS。6550八筆raw中的第八筆為一般大盤標題、未有公司證據，別名重選仍7筆，不湊八筆；web搜尋未取得該ETtoday原文，未造URL或啟用新來源。財報核心範圍選項仍無回覆、沒有更動原判定。新正式9筆保存及已部署修正屬實質progress，goal仍active，未稱全系統80%或新報告品質通過。[同時點原20類面板](evidence/source-acquisition/20261011/coplus-news-alias-final-current-sla.json)。

獨立live覆核另有1項隔離證據檢查通過，完整before／after bundle、五筆canonical與五筆DataProvider、75檔runtime／env／158套件／process及4470筆封閉24小時觀測重投影相符；原截止描述的finding已用追加更正收據處理，無未解material finding。這1項與前述106項code檢查分開記錄，不能把保存的RSS候選稱為已驗全文或新報告品質通過。root於2026-10-11 12:57臺灣時間再唯讀查health／ready均200，原20類仍18／20、財報91／163、新聞184／236，沒有追加補件或模型分析。[獨立正式補件覆核及限制](evidence/source-acquisition/20261011/coplus-news-alias-independent-live-review.json)。


## 2026-10-11 凱基金官方IR入口與券商新聞主體修正

前輪有2254正式6→9補件與部署，屬progress；本輪維持原20類嚴格>80%、免費入口、原完整財報必要事實與品質要求。先核對runtime doctor、git、現行主檔、報告Locator與實際source ledger，未將上輪結果當本輪新成功。

由[凱基金官網](https://www.kgi.com/zh-tw)實際連出的CDF投資人關係入口，web明示正常轉向KGI IR，再沿[官方財務資訊](https://kgi.irpro.co/tw/financials.php)。三份native索引HTTP200完整153,450／78,906／248,474bytes保存；同一原TWSE主檔核對2883／凱基金融控股股份有限公司／70827383／www.kgi.com，原取得時間不續。財報表的公司列、2021–2025各Q4及openfile第一參數對應合併財報明示，排除子公司與非合併欄位；CDF→KGI redirect是web證據，未冒稱有native301收據。初始網搜kgif期貨及npc南亞塑膠母公司均未採用或native抓取。[三份完整官方入口](evidence/source-acquisition/20261011/kgi2883-new-official-IR-linked-index-native-research.json)。

先僅讀尚未下載的2021與2022原件，各一個nativeHTTP200，完整7,468,384／5,187,130bytes、295／292頁封存讀回；相同8MiB／單次5秒／TLS／無重導或重試。兩封面2883、中華開發金融控股及子公司、各110／109和111／110年度、合併scope可核；兩份CF全14–16頁視覺核對TWD仟元，2021CFO65,484,306及PPE現金購置1,872,123的2022比較欄相同，但兩期均未明示gross intangible現金購置。B09900其他投資活動、附註單獨取得成本498,277不可代IAS現金付款或填0，故剩餘三個已列URL未下載、未啟用provider，也未稱完整五年資格。2021text scan只命中目錄2與附註51，不把它們當CF主表；實際14–16是影像表，2022文字表亦全頁視覺核對。[2021完整原件](evidence/source-acquisition/20261011/kgi2883-published-2021-complete-IR-financial-original-native-research.json)、[2021CF資格](evidence/source-acquisition/20261011/kgi2883-2021-cashflow-complete-original-visual-qualification-held.json)、[2022完整比較原件](evidence/source-acquisition/20261011/kgi2883-published-2022-complete-IR-comparative-original-native-research.json)、[2022CF資格](evidence/source-acquisition/20261011/kgi2883-2022-comparative-cashflow-complete-original-visual-qualification-held.json)。

統一證2855／23218183與中再保2851／11081991均有目前不足快照，各最多兩個不同的新精確名稱RSS查詢：第一個含stock code，第二個只保留精確公司名稱，身分仍由同一主檔／原報告context綁定。四個nativeRSS200完整封存；中再保兩次0，統一證2與17raw。離線合併在舊selector表面得到8／4發布者，但其中三篇為2330台積電板的統一證券台股技術評論，一篇為6945圓祥的券商研究，不能當2855自身近況。另有生活網／品觀點相同新聞，未宣稱發布者、事件獨立性或原全文／首次發稿時刻已驗。原機械8筆proof維持，以下修正收據解釋其角色限制，不把它當正式成功。[第一精確查詢](evidence/source-acquisition/20261011/broker-insurer-bound-untried-local-query-RSS-research.json)、[第二精確查詢](evidence/source-acquisition/20261011/broker-insurer-second-exact-name-without-code-RSS-research.json)、[修正前機械合併重播](evidence/source-acquisition/20261011/broker-insurer-two-query-merged-RSS-offline-qualification.json)。

owned只有source_content_selection.py，exact-before bdcb17…與其餘74檔保持。真RSS portable fixtures建立11cases，行為RED4failed／7passed，首版6模組106passed；獨立覆核找到兩組誤拒：report regex跨自身財報子句借附件他股代碼，以及CMoney前綴把年份當股票／把他股板轉貼自身EPS當他股主體。兩輪各重現2failed／11passed及2failed／13passed，再限於明示直接發布對象、分隔後立即研究作者署名，保留日期與自身結果。最後6模組110passed，獨立同範圍加15probes共125passed，計數重疊不相加；兩P2皆實際關閉，初版與中間錯誤／patch／input／source副本保留。失效typed receipt及獨立marker去收據仍failclosed；直接社群、其他2330target與2254／6902別名不變。沒有宣稱涵蓋全部券商歧義或全repo綠燈；先前兩個query舊測試失敗仍另存baseline，未改測試或他股查詢。[最後實際diff及input](evidence/source-acquisition/20261011/broker-subject-role-independent-final-input.json)、[首版獨立finding](evidence/source-acquisition/20261011/broker-subject-role-independent-review.json)、[最後125項獨立覆核](evidence/source-acquisition/20261011/broker-subject-role-independent-fixed-review.json)。

正式沿canonical入口graceful重載1owned＋74preserved＝75檔，env／158套件保持，沒有forcekill／dependency upgrade／清冷卻。launcher41067／role-all worker41095／API41097，health／ready200；canonical session58568保持live。新preflight保存完整jobID與reportID列，重啟後1109jobs／898reports全部所列ID及時間／status相同，原13個保護job／61dispatch、failure432041與至435321的129,990筆零值prefix保持；六隊列／scheduled0。2855真最新保存快照按當前時間仍7筆、dataSHA與index四hash可核，未改原資料或聲稱原報告修好。新版對兩RSS研究資料重播只留4，四筆他股研究原文記錄留在拒收archive，原8／3不符；沒有正式source-only POST、活網新provider response行為或完整報告重分析驗證。此處部署／隔離重播與live acquisition清楚分開。[正式部署](evidence/source-acquisition/20261011/broker-subject-role-release-proof.json)、[當前全ID／帳本／runtime核對與角色更正](evidence/source-acquisition/20261011/broker-subject-role-current-closeout.json)。

截至13:45臺灣時間，本輪9個研究nativeHTTP200（四RSS／三索引／兩PDF），canonical最大435321／DataProvider最大722645不增、quality reviews2不增，沒有新模型／正式補件。原20類仍18／20嚴格>80%，財報91／163＝55.828%、近期184／236＝77.966%；沒有將HTTP200、完整PDF、8筆錯主體候選或研究量當正式成功，也沒有改舊histories／formula／門檻。財報核心範圍問題仍無人類回覆，沿原判定；本輪新官方完整原件與已部署錯歸屬防護屬progress，整體goal保持active，未達成。[同時點原20類完整面板](evidence/source-acquisition/20261011/broker-subject-role-current-formal-sla.json)。

## 2026-10-11 遠東銀品牌新聞入口與正式零筆缺口修復

本輪沿用原二十類各嚴格>80%的目標，上一輪券商主體修正及凱基金完整IR原件屬progress。先對四家目前新聞不足的報告嘗試新的精確名稱、不加股票代碼的RSS研究；其中2442／2069／2845最新快照將EQUITY放在root，identity無該欄位，研究helper在HTTP前遇KeyError，原失敗收據保留。依原正式route的商品類型介面核對後，只送這三個尚未發出的query，不重送已查1623。共四個native HTTP200完整RSS：新美齊2442有5筆公司候選，大東電1623為0，運錩2069機械上9筆。每次原件完整封存、readback核對，20候選／8筆／3來源標籤／30日及兩查詢期限不變。[原研究與HTTP前拒收](evidence/source-acquisition/20261011/four-untried-exact-name-without-code-RSS-research.json)、[三個未發出查詢及原context讀回](evidence/source-acquisition/20261011/three-previously-unissued-exact-name-RSS-after-context-readback.json)。後者沿用helper的four狀態文字；實際cases與native_http_requests均為3，沒有四個HTTP。

遠東集團的[銀行公司頁](https://www.feg.com.tw/tw/business/company.aspx?id=78)另一次匿名native200取得完整45,095bytes；同頁全名「遠東國際商業銀行股份有限公司」、2845、「遠東商銀／遠銀」及exact `https://www.feib.com.tw/` href可核，並與原取得時間仍有效的TWSE全名／統編86517096／官方簡稱「遠東銀」銜接。沒有重試先前銀行官網TLS拒收或放寬TLS。兩個不同的新品牌RSS各一次200：`"遠銀" when:30d` 保留11筆合格metadata／7來源標籤，另一公司業務topic查詢在20候選內有10筆。完整group頁加兩RSS共3個native收據，僅公司頁是品牌身分依據，不當近期新聞本身；RSS為標題／摘要，Yahoo與UDN標籤未驗成獨立媒體家族或獨立事件。[新完整第一方集團入口及兩RSS](evidence/source-acquisition/20261011/feib2845-official-group-brand-anchor-and-two-new-RSS-research.json)。

運錩9筆中兩篇有新索引日期，原新聞較舊。各一次取得CMoney與鉅亨exact公開原文，均HTTP200、完整171,921／251,391bytes封存讀回；原站 `article:published_time` 為2026-09-11T09:22:43+08:00及2026-09-08T09:12:51+08:00，均已超出當前30日。LINE討論牆與後者的股票、22.4元、678張與標題吻合，但沒有實際resolve其Google wrapper，不宣稱已核對追蹤URL指向。兩篇不當新事件，候選最多7，不啟用2069 query／alias、不送正式補件或湊8。這也未泛化改寫所有Google日期或把已保存報告當新分析輸入。[兩個完整原文](evidence/source-acquisition/20261011/yuenchang2069-two-original-date-discrepancies-native-research.json)、[原文日期及候選拒收](evidence/source-acquisition/20261011/yuenchang2069-original-date-qualification-held.json)。研究腳本首次syntax錯誤在網路前發生，原helper留存，修正後兩URL各僅一次。

僅修改兩個runtime：`company_news_queries.py` 限定2845.TW／stock_id2845／官方簡稱，存在時的legal／UBN及root／identity類型矛盾均拒收，forbidden或格式錯誤不加品牌，legacy缺identity類型不補寫；品牌只提供新聞query／selection，原公司identity及2254／6902 mapping保持。`company_news_query` 使用已驗「遠銀」精確名稱，不要求公開文章含股票代碼；原兩查詢／20候選／8筆3標籤／30日／期限及其他公司的查詢規則保持。`source_content_selection.py` 排除已觀測的鉅亨「【遠東商銀】」署名宏觀匯市評論，明示本行或自身業績／存款等仍可用，typed原件驗證先於泛用名稱。只處理這個已驗format，不稱全面的文章主體語意判定。

七個相關模組先RED7failed／16passed，修正後133passed。獨立覆核找到「美元獲利了結」被裸「獲利」例外誤收，追加獲利了結／回吐兩案例先RED2failed／23passed，最小修正後根代理135passed2.06s；獨立同七模組135passed2.12s、額外13probes passed1.44s，無未解重大finding，兩個135套件重疊不相加。額外5314三項query-window失敗在exact-before兩模組原樣重現，不是本輪回歸；另兩項較舊search_catalyst_queries既有失敗未重跑，不宣稱全repository綠。[exact-before及初次input](evidence/source-acquisition/20261011/feib-news-independent-input.json)、[最終input與scoped diff](evidence/source-acquisition/20261011/feib-news-independent-fixed-input.json)、[獨立覆核](evidence/source-acquisition/20261011/feib-news-independent-review.json)。初次preflight的覆核schema假設不符，在停止服務前拒收；依實際bool／135與13兩run／input及log hashes核對後才執行。

正式graceful重載2owned＋73preserved＝75檔，env／158套件與原13jobs／61dispatch／129,990筆至435321零值prefix保持，Redis BGSAVE ok、不forcekill、不清冷卻／升級依賴。舊58568 canonical session因本次已授權重載確認terminal，新 `./start_mac.command` session93890保持live，launcher48988／role-all worker49019／API49021，health／ready200。preflight完整1109 jobID／status／時間列、898 reportID／時間列均在重啟及補件後一致。正常啟動的requirements檢查仍會執行，實際套件版本保持。[正式部署憑據](evidence/source-acquisition/20261011/feib-news-release-proof.json)。

只對2845當前0筆真缺口送一次既有 `source=recent_catalysts`，新query原件在同一原門檻可得11筆才准入；不是重抓健康報告。正式API200 **1.610509秒**，新取得並保存 **8筆**，目前0→8，模型／新分析0。原HTML／Markdown、analysis_evidence、五項品質metadata、company_identity及其他股價／TTM／年度財報／社群與原核心取得時間保持，index四hash一致，analysis_text_stale=1。原snapshot的news_selection cutoff未保存，conclusion_generated_at存在但不是新聞選擇截止；只證目前缺口，不聲稱初次分析新聞為0。[單件准入](evidence/source-acquisition/20261011/feib-news-one-qualified-admission.json)、[正式保存結果](evidence/source-acquisition/20261011/feib-news-2845-formal-refresh-proof.json)。實際正式RSS完整response bytes未另收集，兩份研究RSS不能冒稱正式回應原件；亦未新跑模型或宣稱完整報告品質通過。

canonical435322／435325為兩個GoogleHTTP200、435323／435324為GDELT與Yahoo既有冷卻HTTP0，435326為一個近期新聞父成功8；Yahoo冷卻列上的500是原錯誤，不是本次HTTP500。usage722646–722650均為 `service=Data Provider`、model_id null，包含兩個local block，不能把5筆觀測當5個HTTP或模型調用。全6queue queued／started／deferred／scheduled為0，failure432041保持，沒有再次retry其他held目標。九個研究HTTP200與兩個正式HTTP分開，研究數不入正式成功分子。

2026-10-11 **14:31臺灣時間**的同窗正式原20類仍 **18／20嚴格>80%**。財報91／163＝**55.828%**；近期新聞由本輪preflight183／235＝77.872%到184／236＝**77.966%**，新增一件必要的成功。前輪14:00前也曾184／236，rolling24h已有舊列自然移出，不能拿跨時刻相同值否定這次新canonical成功或將歷史改寫。全部20類未達標，goal active；本輪新原件、主體／日期拒收及正式0→8屬progress，沒有改為較小驗收。財報五年九項、免費來源與品質門檻仍保持。[全部20類／正式帳本／原報告及佇列讀回](evidence/source-acquisition/20261011/feib-news-current-closeout.json)、[完整同窗SLA](evidence/source-acquisition/20261011/feib-news-current-formal-sla.json)。


## 2026-10-11 元太完整上櫃身分入口與五年財報缺口修復

本輪先核東元1504的canonical435209：缺口是2024不完整比較值有衝突，完整2025公開CF原件中，本期及2024比較期都未明示無形資產現金購置，非2022文件缺失。新[公司財務頁](https://www.teco.com.tw/en-us/investor/finance/)一次native取回metadata_invalid且未保存可接受原件；另一份由原公開index列出的2025合併iXBRL新GET回HTTP200但content-type不符，沒有完整文件或財務facts成功。不同HEAD只觀測307、無正文、不跟redirect／重試，也未放寬TLS／mime／缺科目，沒有再送東元正式補件。較舊2022PDF不能補2025／2024缺口，未下載無關文件或填0。[東元索引拒收](evidence/source-acquisition/20261011/teco1504-new-official-financial-index-native-research.json)、[新2025文件格式拒收](evidence/source-acquisition/20261011/teco1504-untried-2025-inline-original-native-research.json)、[不同HEAD僅格式metadata](evidence/source-acquisition/20261011/teco1504-inline-HEAD-published-format-native-research.json)。

元太最新保存報告8069.TWO原股別unknown，原年度只有2022–2025四年，不能以`.TWO`代碼直接補EQUITY。這次新取得[官方ISIN精確股別表](https://isin.twse.com.tw/isin/single_main.jsp?owncode=8069&stockname=)與[TPEx完整公司主檔](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O)，兩個普通TLS native200原件封存讀回。ISIN明示上櫃／股票／ESVUFR／TW0008069006；893家公司完整主檔中，8069／元太／元太科技工業股份有限公司／22099890與2026-10-10出表日相符。舊共享TPEx cache有parsed893列但無完整bytes，未把選取欄位合成原件或刷新舊epoch，才取得新完整master。之前3105.TWO已不在canonical report index，沒有復活已到期報告。[兩個完整官方新原件](evidence/source-acquisition/20261011/eink8069-OTC-classification-and-full-master-native-research.json)。

在只讀研究copy、由這兩原件確認身分後，先驗2021／2022現金流，再查五年完整公開MOPS三表，每年九必要facts及TWD仟元官方renderer契約、合併calendar年度、比較修訂與FCF重算均通過原投影。16次新HTTP200（index加十五JSON），三份已核完整unitJS重用原receipt／epoch；兩個earliestCF先驗後在完整collector原件重用、不重新下載。19份不同完整財報原件全部readback核SHA／大小，不能把5個reuse entries（其中兩個也在新原件表）再算五個新HTTP。本輪研究原生HTTP共21：東元3次held、元太2身分加16財報成功；18個新完整成功原件，研究不入canonical成功分子。[完整五年九項資格](evidence/source-acquisition/20261011/eink8069-new-five-year-public-finance-qualification-research.json)。

只修改`data_fetch/market_sources/twse_security_identity.py`及`report_security_identity_refresh.py`。上市／上櫃後綴必須與ISIN明示市場相符，OTC僅採上櫃／股票／ESVUFR；ETF／創新板／strictCP950原行為保持。上櫃要求不同URL／schema的完整TPEx master，獨立`otc_master`rawreceipt，`listed_company_legal_name`為相容欄名，值實際由匹配市場的完整master解析；上市仍沿原`listed_master`。完整數量範圍、唯一issuer、精確名稱、主檔日期、原件hash／HTTP200／大小／epoch、15秒期限與原cache／cooldown／不重試保持。只接既有source-only unknown股別修復，未宣稱預設完整workflow自動恢復所有unknown OTC；原公司identity不改寫。[exact-before與scope](evidence/source-acquisition/20261011/eink8069-independent-input.json)。

新增真native兩原件fixture先RED9failed／2passed，確實被`.TWO`preHTTP400擋住；最後八模組123passed3.26秒，獨立同範圍123passed3.45秒及14個實際傳輸／shared rawcache／TTL探測1.47秒，無未解重大問題。兩個123重疊不相加；既有5314三個query-window及兩個舊query測試失敗範圍外，沒有全repo綠燈主張。第一次驗證helper把fixtureepoch誤置未來、誤認compactledger有HTTPcount，僅修測試期待，未放寬runtime；RED與中間命令輸出可追溯。[獨立review](evidence/source-acquisition/20261011/eink8069-independent-review.json)。

正式空六佇列、保存Redis後沿`./start_mac.command`graceful重載2owned＋73preserved＝75檔；env與158套件版本保持。舊session93890受控終止；新session24677持續執行，launcher57895／role-all worker57924／API57926，health／ready200，無forcekill／清冷卻／升級依賴。原1109job ID／status／時間、898report ID／時間、13保護job／61dispatch與failure432041，以及至435326的129,992筆零值prefix保持。[正式部署](evidence/source-acquisition/20261011/eink8069-release-proof.json)。

第一次正式helper前置檢查假設old report已存analysis_evidence而拒收，尚未發POST／provider，ledger435326／usage722650不變。讀回實際legacy報告，既有`preserve_analysis_evidence(original_snapshot)`核原snapshot完整性與舊analysis_input_hash，得到`legacy_hash_verified`歷史packet；helper改成驗證此原packet，沒有改runtime或以新財報生成舊證據。[前置期待修正](evidence/source-acquisition/20261011/eink8069-preflight-legacy-input-correction.json)。

正式只對這個真unknown／四年缺口各送一次：身分1.112310秒200、2底層HTTP；接著財報3.011993秒200、19底層HTTP，保存2021–2025五年九項及比較期。自由現金流（十億TWD）2.817232／2.894333／8.166853／4.197599／5.310034，原本2021未提供，沒有用0替代。完整2身分＋15三表＋3unit原始receipt可核，index完整body與正式HTTP200／URL／SHA／大小匹配，但saved compactaudit沒有完整原epochreceipt，沒有發明取得時間。共21完整body讀回；底層21HTTP只計2canonical父觀測435327（taiwan_open_data成功1）／435328（financial_statements成功5），新增usage兩筆都是DataProvider且model_id null，模型／新report／analysis／quality review皆0。[身分保存](evidence/source-acquisition/20261011/eink8069-instrument_identity-formal-refresh-proof.json)、[完整財報保存](evidence/source-acquisition/20261011/eink8069-financial_statements-formal-refresh-proof.json)。

原HTML／Markdown、五品質metadata、company_identity、quote／TTM／新聞／社群及原核心時間保持；hash驗證的legacy原輸入packet於身分補件時新增並在財報補件後完全相同，不說原本就有packet。index四hash吻合，analysis_text_stale=1，補資料不等於重新通過報告品質。2026-10-11 **15:18臺灣時間**正式原20類仍 **18／20各嚴格>80%**：財報preflight91／162＝56.173%，新成功後92／163＝**56.442%**；近期新聞184／236＝**77.966%**。與14:31的91／163不同，是rolling24h舊列自然移出，不改歷史或公式。五年九項免費門檻與尚無回答的8核心範圍選項保持；本輪有實際新原件、部署及元太缺口修復progress，goal仍active且未達全部20類驗收。[全runtime／原件／保存／帳本closeout](evidence/source-acquisition/20261011/eink8069-current-closeout.json)、[同窗完整20類SLA](evidence/source-acquisition/20261011/eink8069-current-formal-sla.json)。


## 2026-10-11 搜尋概覽／論壇角色排除與元太完整官網入口

上一輪元太unknown→EQUITY與四年→五年正式補件是progress。本輪重讀canonical最新154份報告，3105已到期未復活；近期原8／3門檻不足32份。年度raw盤點95份numeric歷史完整，57份表面缺欄包含15份金融業typed科目，不能稱57個一般業缺口；沿前一typed判定區分不適用科目，不重抓已完整者。[年度盤點](evidence/source-acquisition/20261011/post-eink-current-all-latest-annual-inventory.json)、[新聞缺口盤點](evidence/source-acquisition/20261011/post-eink-current-all-latest-news-gap-inventory.json)。

8069.TWO目前0筆，原公司code query與不同主題query各一個native RSS200完整封存：前者15raw／14issuer-time候選，機械8gate通過卻選到CMoney概覽及兩forum；首版proof不回改，不能當正式成功。新增真15-item fixture先4failed／4passed。只改source_content_selection.py，交叉核Googlewrapperhost／CMoney發布者／已觀測固定平台suffix或概覽format，排除8個indexed_non_article_unverified，完整輸入留archive。另個topic query11raw只有2合格且重複，兩query合併仍6；未送正式新聞POST、不加第三query或重試同query。原8／3／30日、兩次／20候選／期限／SLA公式保持；editorial、直接社群與typed原件先驗保持。[原機械候選](evidence/source-acquisition/20261011/eink8069-newly-admitted-news-native-research.json)、[新主題query](evidence/source-acquisition/20261011/eink8069-new-topical-news-native-research.json)、[六筆與資格更正](evidence/source-acquisition/20261011/eink8069-official-news-complete-original-qualification-held.json)。

最後11模組211passed2.27秒、獨立211passed2.34秒，無未解重大finding，重疊不相加。舊2855真fixture含一篇forum轉貼，原4改3；舊6902亦含一篇forum營收轉貼，原8改7，原publisher備援max_records1補找。修改的是不正確的expectation，fixture bytes／品牌mapping／舊canonicalsuccess不回寫。舊5314及兩query baseline另存，未稱全repo綠。[實際scope／diff](evidence/source-acquisition/20261011/eink-news-role-independent-input.json)、[獨立覆核](evidence/source-acquisition/20261011/eink-news-role-independent-review.json)。

新[元太英文官網新聞中心](https://www.eink.com/news)與兩個原index發佈的新聞稿，各native200，完整67,824／57,444／56,698bytes讀回。重用完整TPEx master的8069／元太／法人全名／22099890／WebAddress www.eink.com與原epoch，不seed／renew；普通TLS、無cookie／auth／proxy／重導／同檔重試。index和文章outline日期／title一致，完整_articleBlock正文hash／長度可核，不取隱藏h1／navbar。9/30 ANREALAGE篇只明示8069.TWO，為research-only合格原件；9/25 Flint篇本文8069.TW、About8069.TWO矛盾，held。沒有以官網字樣豁免矛盾；ANREALAGE已見RSS，不能稱兩個新增獨立事件，9/10舊文不塞入30日。新provider尚未啟用、正式新聞POST0；原8069已補五年snapshot及index四hash保持。[三份新完整第一方原件](evidence/source-acquisition/20261011/eink8069-new-official-news-index-and-two-full-press-native-research.json)、[日期／正文／身分資格](evidence/source-acquisition/20261011/eink8069-official-news-complete-original-qualification-held.json)。

重載前每日watchlist自行開始工作，前置檢查先擋住busy。只發一次RQ1.16.2 SimpleWorker支持的warm shutdown，在工作邊界退出，不stop-job／kill-horse。role-all TERM後，已取消asyncio.to_thread的enqueue_watchlist_items整批仍每件sleep45並派發，shutdown_default_executor等待；native sample確認main從kevent到threadjoin、背景sleep，是真關閉bug。Redisstarted／SQLrunning0、RQ PID terminal、BGSAVE成功及完整durable／payload憑據後，只對已知scheduler清理階段採app標準INT，再一次TERM終止失去合作停止機制的背景thread，無SIGKILL或終止進行中分析。不是所有子程序都順利graceful退出；future cooperativebatch停止仍待修。[原live queue擋下](evidence/source-acquisition/20261011/eink-news-role-deploy-preflight-live-queue-hold.json)、[一次warm邊界](evidence/source-acquisition/20261011/eink-news-role-safe-queue-boundary.json)、[已知scheduler清理與完整保存](evidence/source-acquisition/20261011/eink-news-role-known-scheduler-cleanup-termination.json)。

正式canonical重載1owned／74preserved＝75檔、env／158套件保持。舊session24677本次部署終止，新session93499 live，launcher63943／role-all63975／API63977／RQ63984，health／ready200。19個pending job原ID／payload SHA保持；6原retry啟動前exact score保留，到期者依原RQ正常入列，不人工重排或複製。82個dispatch靜態身分保持，新的leased→ack是批次收尾或正常replay，不要求live status靜止；原13保護job、61舊dispatch整列不變。八個較舊done jobs按原30日maintenance到期，非本次手動刪，pending／running沒刪，原終端行留evidence。原所有jobID恒等斷言不再適用。[正式部署／恢復](evidence/source-acquisition/20261011/eink-news-role-release-proof.json)。

原90日retention在startup自然移除34個舊零值行，130,048整prefix hash因此不同。從已存在10/08只讀SQLite backup取回原34行，加當前130,014保留行離線重建，恰等原prefix SHA；前一輪129,992舊prefix SHA也相同，證明原內容沒有回改。沒runtime重插、freshen舊行、清理公式或關維護；failure432041保持，90日到期行不是當前24h樣本。[exact-byte歷史重建](evidence/source-acquisition/20261011/eink-news-role-source-retention-byte-reconstruction.json)。

截至2026-10-11 15:53臺灣時間，原20類仍18／20各嚴格>80%；financial_statements 95／167＝56.886%；recent_catalysts 190／268＝70.896%。近期率比上一輪77.966%下降，本輪optimizer沒有新聞POST；每日watchlist自主新增觀測與真失敗仍計入，沒有用縮小分母／改公式湊80%。五個研究HTTP200、分類部署與第一方原件資格屬progress，goal active；自主來源1360筆／usage1816筆，含456筆model_id觀測。optimizer沒送模型不等於全服務無模型調用。cold daily quality503及cooperative關閉仍待修。[全部20類／保存／原件／目前runtime](evidence/source-acquisition/20261011/eink-news-role-current-closeout.json)、[同窗SLA](evidence/source-acquisition/20261011/eink-news-role-current-formal-sla.json)。

## 2026-10-11 續找：元太繁中與緯穎完整官網新聞稿

本輪沿用免費入口、原二十類逐類嚴格超過80%、完整原件與既有品質門檻。新取得五份完整原件（兩個索引／首頁、三篇新聞稿），均普通TLS匿名GET HTTP200，沒有cookie／auth／proxy／redirect／retry，全部封存完整bytes、原URL、取得時間與SHA後讀回核對。來源研究未啟用provider、未送正式補件、未啟模型或改寫報告。

| 新入口 | 完整原文及發布日 | 實際取得與核對 | 限制 |
| --- | --- | --- | --- |
| [元太繁中新聞中心](https://tw.eink.com/news) | [ANREALAGE合作](https://tw.eink.com/news/detail/3L5OW59BOY)，2026-10-01；[天下永續公民獎](https://tw.eink.com/news/detail/SXLRVIQTJF)，2026-09-30 | 索引67,012bytes、兩篇54,906／59,861bytes；正文1,120／2,535字元，索引與文章標題、日期、新聞發佈角色一致。TPEx完整主檔的8069／元太科技工業股份有限公司／22099890／www.eink.com及已保存英文官網明示繁中href共同綁定tw.eink.com，不從子網域後綴猜官方身分。 | 兩事件已有新聞搜尋metadata，ANREALAGE亦有英文原稿，不冒稱兩個額外獨立事件。兩篇無明示TW／TWO矛盾，英文Flint的矛盾原件仍held。只跟索引當期兩篇新聞發佈，沒有將部落格或過期稿湊數。 |
| [緯穎官網](https://www.wiwynn.com/) | [德州先進製造廠啟用](https://www.wiwynn.com/news/wiwynn-strengthens-global-supply-chain-resilience-with-grand-opening-of-advanced-manufacturing-facility-in-texas)，2026-09-15 | 首页306,820bytes、原文301,223bytes；精確公開href與標題匹配，`div.blog-post__body`完整正文4,509字元，排除導覽與相關稿件。TWSE完整主檔6669／緯穎科技服務股份有限公司／53687704／Wiwynn／同官網網址一致，沿原主檔bytes／時間重用、不续期。 | 原文事件日期2026-09-14與發布日期2026-09-15分開保存。企業自行陳述不等於獨立證實事件影響；相對保存新聞是否增加獨立事件尚未判定。首頁另篇9月10日已超出30日，不新增下載或計入當期。 |

元太收據：[完整原件與文章資格](evidence/source-acquisition/20261011/eink8069-zh-official-two-press-new-native-research.json)。緯穎收據：[完整首頁／原文](evidence/source-acquisition/20261011/wiwynn6669-new-official-news-home-and-press-native-research.json)、[正文／發布日／事件日資格](evidence/source-acquisition/20261011/wiwynn6669-new-complete-press-body-date-qualification.json)。這些原件提供新的完整免費入口，但仍需限定host/path/期限與typed receipt、consumer验证，再進正式資料取得；沒有把研究HTTP200直接灌成正式成功。

### 已套用：排程取消時完成提交確認並歸還未派發租約

前輪正式重載時發現整批`time.sleep(45)`在async取消後仍繼續派發。先以隔離SQLite及installed RQ原子enqueue行為重現，再修改`watchlist_service.py`／`watchlist_scheduler.py`：保留原45秒節奏，批次改為可中斷`Event.wait`，停止後按原lease_token歸還未處理意圖；已提交的工作完成ack，durable ID、600秒lease及重試規則不變。事件雷達改用可取消的`asyncio.sleep(45)`。

獨立覆核新增P2：第二次cancel會穿透一次shield，令scheduler早於真正producer結束。原probe與root兩案例均RED；固定版改直接持有保存ContextVar的私有executor Future，重複取消及`all_tasks`掃除不能取消producer的完成憑據，完成原提交與租約歸還後才傳遞原CancelledError。132項相關root測試11.60秒及132項獨立12.00秒通過，原失敗probe另1passed1.64秒。兩套相關測試重疊，不能相加冒稱264個獨立案例；74項installed RQ deprecation warnings未變更套件。[原blocked覆核](evidence/source-acquisition/20261011/cooperative-watchlist-independent-review.json)保留，[固定版覆核](evidence/source-acquisition/20261011/cooperative-watchlist-fixed-independent-review.json)無未解material finding。最初fixed patch誤用basename導致四檔顯示新增，已按真before相對路徑修正為375行，runtime／test／input hashes未改；恢復驗證也已將RQ`analysis:<id>`與其原args的analysis job ID分開比對，允許到期任務正常續作，不放寬payload相等檢查。

本輪正式更新只加入兩份owned runtime、保留75份既有runtime，共77份與原env／158套件核對。RQ無執行中任務時送一次支援的warm stop，確認相同RQ terminal後才TERM role-all／launcher；這次正常停止，沒有force kill或中斷分析。以正式`./start_mac.command` session58653啟動新launcher71393／worker71421／API71423，healthz／readyz200。17件原retry serialized payload、原args及未到期scheduled score保持，已到期工作允許正常恢復，durable dispatch完整列保持。[正式更新證據](evidence/source-acquisition/20261011/cooperative-watchlist-release-proof.json)。

既有maintenance在本輪啟動自然清除17筆超過30日的terminal done job及167筆超過90日的source零值記錄；已保存原完整行並依剩餘行加回離線重建，原zero前綴hash完全一致。未刪當期失敗、未補寫runtime、未將旧失敗重新標成功，原432041保持。舊通用驗證誤將serialized RQ ID當analysis job ID的相等檢查已修正為實際args，正式服務未因此重啟第二次。

最新正式近24小時原二十類仍18／20嚴格>80%，財報90／166＝54.2169%、近期173／248＝69.7581%；新研究未算入分子或分母，來源成功也不代表新報告品質通過。全目標仍未完成；本輪為有實際來源與正式修正的progress，沒有blocked streak、沒有commit／push。[目前驗收與完成範圍](evidence/source-acquisition/20261011/cooperative-watchlist-and-new-free-press-current-closeout.json)、[完整正式SLA](evidence/source-acquisition/20261011/cooperative-watchlist-current-formal-sla.json)。

## 2026-10-11 元太完整官網原文接入與正式補件驗證

上一輪取得三篇完整新官網原件、部署cooperative停止，屬progress。本輪接續原20類逐類嚴格>80%目標，沒有將未達門檻的元太RSS6筆再重抓或把英文翻譯當新事件，而是接入已驗證的繁中全文入口。`eink_issuer_news.py` 僅允許8069.TWO：完整TPEx主檔（最低500列、代碼唯一）核元太／元太科技工業股份有限公司／22099890／www.eink.com／原出表日，英文官網的明示繁中href再綁tw.eink.com。四種完整原件（主檔、官方語系索引、繁中索引、文章）與各自原epoch／URL／bytes／SHA全部保存並在consumer重播，不合成主檔或延長原快取時效。

只取`div.news-content`內已公開、原30日內的「新聞發佈」；原最多5篇、20秒共享期限、普通TLS與無cookie／auth／proxy／redirect／retry、既有冷卻及1800秒快取保持。文章與自身索引日期／h1標題／角色一致，正文取自己`_articleBlock`，不從導覽、相關稿件或event日期填發布日，拒絕明示8069.TW市場矛盾及script／iframe等錯型內容。英文Flint的矛盾原件仍held，英文翻譯、活動、部落格與過期稿不湊數；原文標`issuer_statement`／`event_assessment=not_assessed`，不冒稱事件影響獨立證真。`issuer_news.py` 與`IssuerNewsProvider`只增加此精確上櫃路由，其他firstparty入口、全域alias及來源啟用設定保持。

五份完整已讀原件gzip／manifest作隔離fixtures，未讀正式cache／API／Redis；先公開interface兩項RED證明缺入口，再245／247項相關green。獨立覆核揭露P2：source-only merge只傳ticker/name/identity，漏掉原root instrument_type，ETF矛盾可繞過新typed verifier。原獨立probe及rootcase均RED；已在精確元太source preflight於HTTP／audit前拒收矛盾，merge保留root instrument_type再核對，不給其他firstparty加新門檻。固定版root11modules **252 passed in10.12s**、獨立同範圍 **252 passed in9.85s**，原獨立probes **2 passed in1.46s**；不將重疊兩套相加為504。原blocked覆核保留，[固定版覆核](evidence/source-acquisition/20261011/eink-issuer-source-fixed-independent-review.json)無未解material finding。[初版證據](evidence/source-acquisition/20261011/eink-issuer-source-independent-review.json)、[固定input／runtime與fixtures hashes](evidence/source-acquisition/20261011/eink-issuer-source-fixed-independent-input.json)。

正式目前runtime77中只有既有三檔加新增一模組受影響，**4owned／74preserved＝78**檔與原env／158套件核對。趁RQ無執行中工作，單次支援warm stop，确认相同RQ terminal才TERM role-all／launcher，再由`./start_mac.command` session68078重載；新launcher76158／worker76188／API76190，healthz／readyz200。15個原pending retry serialized payload／原args、未到期scheduled score及durable dispatch列保持。相對本輪preflight，原maintenance自然清除8筆超過30日terminal done job及5筆超過90日的舊零值source rows；原列與保留列離線合併重建zero prefix SHA完全一致，未刪當期失敗或補寫runtime，432041保持。[正式更新證據](evidence/source-acquisition/20261011/eink-issuer-source-release-proof.json)。

針對目前最新8069.TWO同一份原v2報告（`8069_TWO_v2_report_job_c2d763a8268d.html`），事先核對EQUITY與原核心audits有有效時間、目前合格新聞0且無firstparty完整原文，備份HTML／Markdown／snapshot，再只送一次`source=issuer_news`補件。正式API **HTTP200／5.715秒**，保存兩篇10月1日ANREALAGE、9月30日天下永續公民獎完整正文1,120／2,535字元；全部五個底層HTTP原件可重新解壓／hash／typedconsumer核對，來源status=success、record_count=2、HTTPcount=5。只有 **1筆canonical source成功**（event437975，fetch1972c2fc37584f0098be30d8e6fb8911），不把5HTTP或2文章當5／2次成功。

首次helper把API回傳`refresh_sources`錯預期為alias`issuer_news`而停止後段檢查；既有`report_refresh_service.py:165`實際回canonical`recent_catalysts`並另標`refresh_component=Verified issuer news`。此時200已保存，未重送或重啟；初次失敗收據完整保留，再從同一snapshot／原備份／canonical fetchID完成readback。原HTML、Markdown、analysis_evidence、五quality metadata、公司identity／quote／TTM／完整五年財報與其source audits／原取得時間均保持；index四hash相符，analysis_text_stale=1。僅新聞投影、來源audit與freshness/data trust變動，沒有新model／analysis job／quality review。[完整正式補件與原件](evidence/source-acquisition/20261011/eink-issuer-source-formal-refresh-proof.json)、[初次驗證失敗保留](evidence/source-acquisition/20261011/eink-issuer-source-formal-initial-verifier.json)。

兩篇firstparty原文達成既有發行人元件contract，但**沒有達成AlternativeSearch的8筆／3發布者門檻，也沒有新的全報告品質通過**。最新正式近24h原20類仍18／20嚴格>80%，財報90／166＝54.2169%、近期174／249＝69.8795%。原公式、歷史失敗、期限、來源多樣性與全部goal保持；本輪為已部署及真實補件的progress，未標complete、未commit／push。緯穎入口仍研究候選，未擴大本輪runtime範圍。[現在驗收與限制](evidence/source-acquisition/20261011/eink-issuer-source-current-closeout.json)、[全原20類正式SLA](evidence/source-acquisition/20261011/eink-issuer-source-current-formal-sla.json)。

## 2026-10-11 續找：MOPS一般業期初餘額版面修復與燁輝正式補齊

讀回目前財報失敗台帳，發現燁輝2023.TW／2024年與冠西電2466.TW／2023年的完整官方資產負債表，均明示當期12月31日、前期12月31日及前期1月1日三期。原普通parser只接受兩期，合法期初欄因此觸發`public MOPS annual amount-column alignment mismatch`，不是來源沒有資料。兩份完整JSON原件6402／6561bytes與三份完整官方unit renderer以gzip fixtures保存；歷史失敗compactaudit未保留native取得epoch，manifest明示未知，不從檔案mtime或SLA事件時間推造。

owned runtime只有`data_fetch/market_sources/mops_public_annual.py`：第三期僅允許BalanceSheet的精確前一年1月1日，金額／百分比subcolumns與必要科目列寬須匹配；輸出仍取columns1／3當期及前期期末，columns5／6期初不能填缺值。IncomeStatement／CashflowStatement仍只准兩期，日期錯置、次序、單位、issuer、scope、重複／缺必要科目與dash／bool仍拒收，五年九必要科目、gross PPE／intangible purchase、比較修訂、貨幣及FCF公式保持。原失敗先RED2failed；最後十一模組root **204passed5.17秒**、獨立同範圍 **204passed5.06秒**，另六個closing缺值／include_prior邊界probe **6passed1.08秒**；兩套204重疊，不相加。正式前所有runtime與fixture input hashes保持。[精確diff與覆核輸入](evidence/source-acquisition/20261011/mops-opening-balance-independent-input.json)、[獨立覆核](evidence/source-acquisition/20261011/mops-opening-balance-independent-review.json)。

先對當前已知失敗的燁輝普通TLS匿名活網研究一次：19actualHTTP200、19份完整原件，2021–2025五年九科目與完整comparative projection通過；研究canonical SLA／usage最大ID保持，模型0、正式POST0。沒有將研究原件seed入正式快取，也沒有為測試重抓目前完整的冠西電。[燁輝新完整公開原件研究](evidence/source-acquisition/20261011/mops-opening-balance-2023-native-full-research.json)。此入口是MOPS公開合併三表，官方查詢路徑可見[證交所操作說明](https://dsp.twse.com.tw/public/static/downloads/announcement/official/R-1140600094-1.pdf)；HTTP可得仍須通過本系統完整原件與科目契約。

正式更新 **1owned／77preserved＝78**runtime，原env／158套件保持。RQ無執行中工作時單次支援warm stop，確認相同RQ terminal後才TERM role-all／launcher，以`./start_mac.command` session29685重載；新launcher81162／worker81190／API81192，healthz／readyz200，正常停止、forcekill0。14個原retry serialized payload／原args與未到期scheduled score、durable dispatch整列保持；本輪30日terminal job與90日old zero source到期均0，原失敗432041與435668保留。[正式重載與排程保存](evidence/source-acquisition/20261011/mops-opening-balance-release-proof.json)。

燁輝最新同一份`2023_TW_v4_report_job_90987cb79786.html`實際`fcf_history[2021]=null`，只有cache audit且無完整九科目憑據；2022資產／權益103.62／41.62（十億TWD）也與原完整官方合併口徑93.151389／31.582868不同。10/10舊報告曾完整不代表10/11最新快照完整，所以先保存最新三artifact及source audits，再僅送一次`source=financial_statements`。目前ordinary正式入口讀回確由`fetch_official_financial_result(fetcher=None)`接到public JSON，不強制來源、清gap／cooldown或改路由。正式 **HTTP200／4.727896秒／19底層HTTP**，五年九科目完整，2021FCF由null補為 **1.289126十億TWD**，2022assets／parent equity按同口徑補齊。僅 **1canonical success438279**，fetch0838f17402424db8903e6c9c6ab69aed；一筆DataProvider usage、model_id null，analysis jobs／quality reviews新增0。[單次正式補件及保存比較](evidence/source-acquisition/20261011/mops-opening-balance-2023-formal-refresh-proof.json)。

consumer及readback完整重播15JSON／3unit renderer的18份原epoch收據，另索引完整34344bytes與正式component URL／HTTP200／SHA吻合並重播五個published年度；索引compactaudit沒有完整epoch收據，沒有補造取得日。首次closeout列舉器誤找`source_record_archive`而非`raw_response_path`得到0收據，原結果保留；修正後read-only列舉18收據加完整索引。附加probe又誤期待新完整body SHA等於舊失敗body，實際只有server `datetime`由15:45:37變17:17:44，兩完整原件保留且去除這一已觀測response時間後整JSON完全相同，財期／欄位／金額沒改。兩處只修查驗器，不重送POST、HTTP、重啟或修改runtime gate。原HTML／Markdown、analysis_evidence、五quality metadata、quote／TTM、company identity、其他source audits及原取得時間保持，index四hash一致，analysis_text_stale=1；沒有新的整份報告品質通過。[初次列舉結果保留](evidence/source-acquisition/20261011/mops-opening-balance-current-closeout.json)、[修正readback與完整原件](evidence/source-acquisition/20261011/mops-opening-balance-current-closeout-v2.json)。

截至**2026-10-11 17:21:59臺灣時間**，正式近24h原20類仍 **18／20**逐類嚴格>80%；財報 **91／167＝54.4910%**、近期 **174／249＝69.8795%**。原公式、過去失敗與原品質门檻保持，沒有用研究HTTP或healthy重抓墊高分子。此輪有真失敗格式修復、正式部署及真缺值補齊，屬progress，goal仍active；未commit／push，未標全目標完成。[完整原20類正式SLA](evidence/source-acquisition/20261011/mops-opening-balance-current-formal-sla-v2.json)。

## 2026-10-11 續找：超豐四份官方年報的完整五年比較欄入口

最新150份報告年度盤點，先排除93份numeric歷史完整及13份已通過金融業typed契約者；尚有42份一般年度缺口，另2份context不准入。完整已封存公開索引顯示2441的合併C申報只有2022–2025四份；6994／7750／7740只有三份、1623兩份、9103沒有C，不能用相同比較欄規則湊五年。超豐當前同一份`2441_TW_v4_report_job_fcf21739a72d.html`的2021七個history欄位均null，原只有fresh-cache audit，沒有五年九科目憑據，具備真補件需求。[當前年度盤點](evidence/source-acquisition/20261011/post-opening-current-all-latest-annual-inventory.json)、[完整索引分流](evidence/source-acquisition/20261011/short-public-four-filings-comparative-start-candidate-index-readback.json)、[正式准入](evidence/source-acquisition/20261011/greatek2441-current-actual-gap-formal-admission.json)。

新公開2022合併CF明示2021營業現金流7,414,609,000、PPE購置-5,419,052,000、無形購置-18,773,000TWD，FCF＝1,976,784,000。讀取完整firstparty[超豐年度財報頁](https://www.greatek.com.tw/investor2.html)，以完整TWSE主檔的2441／超豐／超豐電子股份有限公司／UBN05126366／GTK／官網綁定。2022公司完整PDF可核2021所有九項合併數值；2023公司PDF明示copy:no且AES256，未抽文字、OCR或解密，也未續抓無关2024／2025PDF。PDF只供研究核對，正式provider採既有公開MOPS三表JSON。[最早CF原件](evidence/source-acquisition/20261011/greatek2441-new-earliest-published-comparative-CF-native-probe.json)、[完整IR頁與檔案限制](evidence/source-acquisition/20261011/greatek2441-new-full-IR-four-consolidated-reports-native-research-v3.json)。

初次2022BS transport_error保存並停止；後續先成功取得原未讀2023CF，證明同host實際恢復，才對2022BS做一次重試及讀取剩餘未讀原件。共17個本輪研究HTTP，16HTTP200、1transport_error；完整12JSON、3unit renderer及1index共16份唯一原件可重播，部分原件沿已保存原epoch重用，不重標時間。研究階段不是一次不間斷cold batch，也不計正式SLA或seed正式cache。每個stage自己的ledger前後保持，全服務另有背景排程活動，不能說全日模型0。[完整五年九項研究](evidence/source-acquisition/20261011/greatek2441-four-filings-five-complete-periods-native-research-v2.json)、[原件typed重播與PDF界線](evidence/source-acquisition/20261011/greatek2441-native-originals-typed-replay-and-PDF-boundaries.json)。

owned runtime只有`mops_public_annual.py`、`annual_financial_source_refresh.py`及`yfinance_extractors.py`。四文件variant必須完整公開index恰為四個連續C年度，首期由第一份次年合併報表明示完整九科目；保存first_period_basis及index native收據，後三份不能藏額外basis，完整bytes／hash／原epoch／issuer／scope／單位／報表財期與比較修訂均重播。輸出仍是五個完整財期，不宣稱存在2021原始C申報，不接受三文件、phantom第五文件、缺值／dash／bool或值更動。一般五份年報契約、期限／冷卻／來源選擇／九科目門檻保持。source-only來源說明靠前，原quote／TTM純量來源說明仍保留第一位；compact prompt與一般SDK入口都可見比較欄來源。

完整native fixtures先RED3failed；來源說明被原長notes截斷的RED1failed亦保存。獨立覆核發現P2：Python dict equality把2021.0與2021視為相等，admission可過而note拒收。新增兩year型別反例先RED2failed，修正為共用exact-int marker驗證，拒收float／bool、不正規化。最後十二模組root **229passed5.11秒**、獨立 **229passed5.07秒**，原獨立probe **1passed1.32秒**；重疊suite不相加。16完整原件／25收據引用、22檔案hash及exact-before diff可核，原blockedreview／失敗probe保持。[原覆核](evidence/source-acquisition/20261011/greatek-comparative-start-independent-review.json)、[固定輸入](evidence/source-acquisition/20261011/greatek-comparative-start-fixed-independent-input.json)、[固定覆核](evidence/source-acquisition/20261011/greatek-comparative-start-fixed-independent-review.json)。

release第一個preflight遇到每日watchlist原排程busy而停止，未發shutdown；等待原工作完成後，12件retry待排程、queued／started0才保存payload／score／durable列。只對原RQ發一次支援warm stop，確認terminal後TERM role-all／launcher，以`./start_mac.command` session31596正式重載；new launcher92178／worker92206／API92208，healthz／readyz200，forcekill0。**3owned／75preserved＝78runtime**、原env與158套件、12件retry serialized payload／原args、未到期score及durable dispatch保持。既有maintenance自然移除6筆超過30日terminal jobs及78筆超過90日old zero rows；原列加現存列離線重建zero prefix SHA完全吻合，432041保持，沒有改當期失敗或公式。[busy前置證據](evidence/source-acquisition/20261011/greatek-comparative-start-busy-preflight.json)、[正式重載及排程保存](evidence/source-acquisition/20261011/greatek-comparative-start-release-proof.json)。

只對目前首年全空的超豐同一份報告送一次既有`source=financial_statements`。正式 **HTTP200／2.728757秒／16底層HTTP**，保存2021–2025九必要科目，實際四份primary filing仍2022–2025、首年FCF由null→**1.976784十億TWD**，比較欄origin及原財務純量觀測時間均在compact prompt可見。完整16份正式native原件及各原epoch可重新核對，index收據本次亦保存。只新增 **1canonical成功438847**，fetch`d3ca7ed5f522418fb6bf352e39cec0ee`，不能把16HTTP或5財期當16／5次成功；此request範圍新增一筆DataProvider usage、model_id null，analysis jobs／quality reviews新增0。[單次正式補件](evidence/source-acquisition/20261011/greatek-comparative-start-2441-formal-refresh-proof.json)。

原HTML／Markdown、analysis_evidence、五品質metadata、company identity、quote／TTM、其他source audits與原核心時間均保持，index四hash吻合，analysis_text_stale=1。補齊來源不是新的整份報告品質通過。截至 **2026-10-11 18:20:56臺灣時間**，近24h完整原20類仍 **18／20**逐類嚴格>80%；財報 **92／168＝54.7619%**、近期 **173／248＝69.7581%**。原五年九項／新聞8筆3發布者／品質／公式／歷史失敗與全部20類目標保持，沒有健康報告重抓墊高分子。本輪有新原件、修正、部署及真缺口補齊，屬progress，goal仍active，未commit／push。[當前完整驗證與限制](evidence/source-acquisition/20261011/greatek-comparative-start-current-closeout.json)、[同窗原20類SLA](evidence/source-acquisition/20261011/greatek-comparative-start-current-formal-sla.json)。

## 2026-10-11 緯穎完整免費新聞入口、正式補件及快取憑據修正

接續原全部20類嚴格>80%目標。重新讀回150份最新快照、無不可讀artifact：94份一般numeric年度歷史完整、13份typed金融業完整、41份年度缺口與2份context不准入；當前65份新聞不足原8則／3來源／30日。這是現在的資料不足盤點，不能把全65份都當原始報告缺口。緯穎同一份`6669_TW_v4_report_job_c60ac7eceb0e.html`原存8則，在原真正`news_selection.cutoff`重播排除1個CMoney個股概覽，合格7；現在再排除2則過期內容，合格5，未存firstparty完整原文，符合單項補件資格。[當前150份年度](evidence/source-acquisition/20261011/post-greatek-current-all-latest-annual-inventory.json)、[當前150份新聞](evidence/source-acquisition/20261011/post-greatek-current-all-latest-news-gap-inventory.json)、[原與目前截止的單件准入](evidence/source-acquisition/20261011/wiwynn6669-one-qualified-firstparty-source-admission.json)。

沿先前已完整取得的TWSE主檔、[緯穎官網](https://www.wiwynn.com/)公開card及[完整公司新聞稿](https://www.wiwynn.com/news/wiwynn-strengthens-global-supply-chain-resilience-with-grand-opening-of-advanced-manufacturing-facility-in-texas)三份完整bytes建立gzip隔離fixtures，原hash／大小／取得epoch保持，未seed正式cache。本輪native研究HTTP0，web核對官網可見內容另不屬本機formal SLA。日期來源明示2026-09-15T01:07:01.000Z，與索引9/15、可見September15及Asia/Taipei日一致；文內September14是事件日期，不能當發布日期。parser只取`span#hs_cos_wrapper_post_body`的完整4383字元主文，朗讀標題／4:39、分享Tweet及sidebar不混入。role=issuer_statement、event_assessment=not_assessed、window_complete=False；同一德州事件已有工商時報標題，不宣稱新增獨立事件、獨立媒體或歷史PIT。[先前完整研究原件](evidence/source-acquisition/20261011/wiwynn6669-new-official-news-home-and-press-native-research.json)。

新增`wiwynn_issuer_news.py`，只改既有`issuer_news.py`、`issuer_news_provider.py`與`report_source_refresh.py`，正常optional與單項刷新共用既有免費provider／限定ordinary HTTPS transport。master代號6669／緯穎／緯穎科技服務股份有限公司／53687704／Wiwynn／www.wiwynn.com完全核對；索引href／title／day、原文canonical／title／visible date／作者Wiwynn／Corporate及JSONLD原始aware datePublished均重播。snapshot不允許改成TWO／ETF／他家公司／其他來源，收到錯字節、壞deflate、改正文／日期／作者／publisher／角色、future／naive／dateModified-only、未知／私人URL及超時皆拒收。共享20秒、最多5篇、30日、原source cache／host cooldown與所有其他routes保持。單項商品矛盾在取得或audit前拒收；一篇不通過8／3搜尋門檻。最初2案例真RED，壞deflate原件另RED1；初版14模組331passed及獨立331passed、3probes通過。[初版完整範圍](evidence/source-acquisition/20261011/wiwynn-issuer-source-independent-input.json)、[初版覆核](evidence/source-acquisition/20261011/wiwynn-issuer-source-independent-review.json)。

初次正式以4owned／75preserved＝79runtime、原env／158套件核對；無執行工作、12件retry payload／原args／未到期score與durable dispatch保持，canonical`./start_mac.command` session89939、launcher96924／worker96954／API96956、health／ready200。既有retention自然移除5筆超過30日terminal jobs、6筆超過90日old zero rows；離線原列＋現存列重建prefix SHA一致，432041保留。[初次正式重載](evidence/source-acquisition/20261011/wiwynn-issuer-source-release-proof.json)。

對准入的同份報告，只送一次新來源補件`source=issuer_news`，回canonical recent_catalysts／Verified issuer news，**HTTP200／2.312225秒／2個native HTTP**。主檔沿已核驗完整共用cache、HTTPsentFalse；首頁及完整新聞稿新GET。保存一篇完整原文，當前合格5→6，仍不滿8／3。只新增 **1canonical成功438849**、fetch`de745d8d67a14d01a0f73bb628d0b215`，不是把2HTTP或6則當2／6次成功。原HTML／Markdown、analysis_evidence、五品質metadata、company identity／quote／TTM／全部財報與其他source audits／原核心時間保持，index四hash吻合，analysis_text_stale=1。[初次正式資料與實際請求](evidence/source-acquisition/20261011/wiwynn-issuer-source-6669-formal-refresh-proof.json)。

最後readback揭露本次collector標記錯誤：共用master metadata原本明示HTTP未觀測，但`archive_response`預設寫200／raw_http_response_bytes；其完整raw payload、SHA／大小／URL／epoch已可核，卻不能冒稱原HTTP200憑據。初版正式與closeout均保留，沒有改歷史成功438849。新增真RED1後，改存`evidence_kind=cached_complete_source_payload_verified_by_digest`、HTTPNone、http_status_observedFalse與cache_source／digest／bytes，只有master可用；index／article仍需原native receipt。獨立覆核再發現native kind接受cache-only矛盾欄位、collector會正規化矛盾HTTP200；root三反例先RED3，兩入口均已嚴格拒收，不正規化錯標。最後14模組 **337passed15.65秒**，獨立 **337passed**與原9反例 **9passed**，原blockedreview／紅燈保持、無material finding；重疊suite不相加。[原blocked覆核](evidence/source-acquisition/20261011/wiwynn-cached-master-kind-independent-review.json)、[固定輸入](evidence/source-acquisition/20261011/wiwynn-cached-master-kind-fixed-independent-input.json)、[固定覆核](evidence/source-acquisition/20261011/wiwynn-cached-master-kind-fixed-independent-review.json)。

metadata修正只有1owned／78preserved＝79runtime重載，原env／158套件保持。等待RQ idle，9件待retry payload／未到期score與durable rows保持；較前次12件少3件為原排程自主續作，不是本輪取消。新canonical keepalive session34482、launcher99335／worker99369／API99371，health／ready200，本次30／90日到期清理0。最後API-stop exec尚未觀測completion時曾啟動canonical start handle；其既有owner／port／cleanup guard生效，重poll同stop handle exit0，確認oldAPI／launcher terminal，實際new身份／hash與全部pending均核對，無forcekill或第二次RQ warm。此處不宣稱tool觀測完全串行，序列收據保留。[目前正式release與觀測限制](evidence/source-acquisition/20261011/wiwynn-cached-master-kind-release-proof.json)。

事先只讀核對首頁／文章cache尚有效、fullbody SHA與原epoch相同，透過原本已支持的fresh-cache單項刷新更正同一篇的master receipt。**HTTP200／0.870550秒／新HTTP0／新來源成功0**，status=skipped_fresh_cache、全部3components HTTPsentFalse。主檔HTTPNone與honest kind已保存，所有正文／datePublished／其他receipt／hash／epoch及quote／TTM／財報／原輸入／五品質metadata均保持。首次helper誤以為compact canonical details保留HTTPcount而KeyError；200與初次verifier保留，只讀同一snapshot／原backup／saved audit0及全3cachecomponents，補完成驗證，無額外POST／provider／restart。原實際成功438849仍是success1，快取更正觀測不加入fetch_attempts或成功分子。[初次verifier保留](evidence/source-acquisition/20261011/wiwynn-cached-master-kind-cache-repair-initial-verifier.json)、[同次快取更正完成](evidence/source-acquisition/20261011/wiwynn-cached-master-kind-cache-repair-proof.json)。

截至 **2026-10-11 19:00:43臺灣時間**，完整原20類仍 **18／20**逐類嚴格>80%；財報 **92／168＝54.7619%**、近期 **174／249＝69.8795%**。本輪有完整新入口接入、正式真缺口及憑據修正，屬progress；原五年九項／8則3來源／品質／公式／歷史失敗／全部20類目標保持，沒有用healthy重抓或cache metadata更正墊高分子。原報告需重新分析，不宣稱新全報告品質成功，goal仍active，未commit／push。[初次closeout保留](evidence/source-acquisition/20261011/wiwynn-issuer-source-current-closeout.json)、[更正後目前完整驗證](evidence/source-acquisition/20261011/wiwynn-issuer-source-current-closeout-v2.json)、[同窗原20類SLA](evidence/source-acquisition/20261011/wiwynn-issuer-source-current-formal-sla-v2.json)。

## 2026-10-11 精確品牌免費查詢、索引角色拒收與新聞專用保存投影

既有Google RSS新增第二個品牌專用查詢 `"Gogolook" when:30d`，沿當前6902／GOGOLOOK／走著瞧股份有限公司／53755364的既有局部綁定；2254巨鎧精密同機制，FEIB已是品牌主查詢則保持。只有完整且同ticker／name／identity的original company_context與非矛盾root type才准入；AlternativeSearchProvider傳原context，legacy缺context保留code anchor。原第一個code/topics、paid／其他engine、兩query共享30秒、最多20候選、8合格／3來源／30日、cooldown及disabled candidates保持。研究一次匿名native取得完整32895bytes／27items，原epoch/hash讀回不更新、不seed正式cache；20head最初9eligible中的TradingView「股東人數 – TWSE:6902」只是索引統計頁，獨立覆核後明確拒收，仍8eligible通過原gate。只有來源標識，未驗獨立出版社、全文、歷史PIT或事件影響。[完整新查詢研究](evidence/source-acquisition/20261011/gogolook-name-only-brand-new-native-RSS-research.json)、[排索引後准入](evidence/source-acquisition/20261011/bound-brand-fallback-static-filter-one-qualified-admission.json)。

修改company_news_queries／external_search_providers／enrichment_search_providers／source_content_selection四個既有runtime；初版root type未傳實際provider的P2、TradingView索引佔八筆的P2均先保存RED再修。Googlewrapper＋TradingView＋精確股東人數標題才拒收，真正editorial不泛化排除；舊Gogolook全bytes fixture也含同頁，正確候選由7減為6，歷史native proof7／9保持為舊分類證據。只准入同份6902原saved cutoff及當前均不足8的報告，2254當前及原均9則已足量，不重抓。[四檔穩定覆核](evidence/source-acquisition/20261011/bound-brand-fallback-static-filter-independent-review.json)、[初次發布](evidence/source-acquisition/20261011/bound-brand-fallback-release-proof.json)。

只送一次6902 recent_catalysts API，HTTP200／1.882323秒／兩個真正Google HTTP200，得到8個合格來源候選與canonical439281、fetch11c7dd4c3b7248f9bfefa4bd0e6fe5aa；兩個既有gdelt/yahoo cooldown沒有HTTP，歷史500不能說成此次新500。保存後verifier發現merge_recent_source用generic freshness又升格OLD metric，初次200＋AssertionError證據保持、沒有重送來源。修news_freshness_policy在identity通過後沿同一indexed-role拒收，原行放unverified／source_role_status而非刪除；五種old buckets、反覆投影、publisher/date與原epoch均隔離RED後驗證。[初次正式請求及失敗](evidence/source-acquisition/20261011/bound-brand-fallback-6902-formal-refresh-proof.json)、[角色重播覆核](evidence/source-acquisition/20261011/news-role-projection-independent-review.json)。

第一次既有report_refresh_service(refreshed_data,NoProvider)保存角色更正時，generic投影同時重新篩社群，違反本次news-only範圍；檢查失敗及實際已寫入readback保持，SLA/APIusage/job/quality counter完全未增。新增公開apply_news_only_freshness wrapper只copy公司與新聞context、只寫回五news buckets及news_selection；既有generic social行為不改。從已核SHA的原native取得後immutable快照取回原social／sentiment，再一次0provider saved-data修正；不是重抓、重設原fetched epoch或補canonical成功。340項相關與340項獨立、3個public wrapper probe通過，2個既有query expectation exact-before亦失敗則明示deselect；Oct5另一無關source-admission equality失敗亦已before證實，不宣稱全repo綠色。[首個維護副作用readback](evidence/source-acquisition/20261011/news-role-projection-initial-saved-correction-readback.json)、[新聞專用穩定覆核](evidence/source-acquisition/20261011/news-only-projection-independent-review.json)、[最後保存驗證](evidence/source-acquisition/20261011/news-only-projection-saved-data-correction-proof.json)。

最後runtime1owned＋78preserved＝79，env／158package保持；一次支援RQ warm等既有工作終止，不force／cancel或再發第二shutdown。canonical session76476，launcher10773／worker10801／API10803，health／ready200；6件排程payload與未到期score、durable dispatch及舊failure432041／全部舊zero prefix保持。最後同份snapshot近期欄位8、eligible union9，TradingView索引及CMoney索引留unverified2；原social／sentiment、股價／TTM／財報、其他audit與原時間、HTML／Markdown／analysis input／五品質metadata全比對，index hash吻合，analysis_text_stale=1。原receipt只在真正native return epoch重播驗憑據，另用現在時鐘驗新聞窗口；沒有偽更新60秒收據、沒有模型或新報告品質驗證。[最後發布](evidence/source-acquisition/20261011/news-only-projection-release-proof.json)、[現在完整closeout](evidence/source-acquisition/20261011/bound-brand-fallback-current-closeout.json)。

2026-10-11 20:01:36台北，原全部20類仍18／20嚴格>80%；financial_statements92／168＝54.7619%，recent_catalysts175／250＝70.0%。同窗公式、分母、舊失敗不改，不以健康重抓或兩次cache維護灌分子；全20目標仍active，無commit／push。[原20類正式SLA](evidence/source-acquisition/20261011/bound-brand-fallback-current-formal-sla.json)。

## 2026-10-11 冠西電新報告真缺口補件與南亞新官方下載入口

最新150份年度盤點發現冠西電2466的最新`2466_TW_v4_report_job_b2faf9bc57fa.html`只有2022–2025四年；較舊完整報告仍保留且未重抓。該新報告沿用07:48 UTC取得、早於09:14 UTC期初版面修復發布的原輸入，不能據此判定新版正常parser仍失敗。11份已保存完整失敗原件hash／bytes離線重讀，2021及2022各九科目、2023資產負債表期初版面已由目前parser正確處理，沒有重造未知的舊component取得時間。[原輸入及版面重播](evidence/source-acquisition/20261011/post-brand-role-2466-post-format-fix-gap-replay.json)。

對同一份已done報告只送一次既有`source=financial_statements`，**HTTP200／2.833454秒／19actual HTTP200**，補成2021–2025五年九科目。2021FCF由缺年度補為-0.173258十億TWD，其他年份沿完整官方同口徑重算；所有新完整官方原件及原epoch經既有consumer重播。只新增一個canonical成功**439568**，fetch`c123211e7438408682ca3f85c577566c`；一筆DataProvider usage、model_id null，沒有新分析或quality review。原HTML／Markdown／analysis_evidence／五品質metadata、quote／TTM／其他資料及source audits原時間保持，index四hash相符、analysis_text_stale=1；不宣稱新報告品質通過。本輪79runtime／env／158套件與正式程序未變、未重啟，health／ready200，六件原retry payload保持，其中一件依原排程已finished、其餘五件scheduled。[唯一正式補件](evidence/source-acquisition/20261011/post-brand-role-2466-post-format-fix-formal-refresh-proof.json)、[現在完整readback](evidence/source-acquisition/20261011/post-brand-role-financial-current-closeout.json)。

南亞1303先只查iXBRL舊缺項而另讀兩次公開JSON現金流；交叉核對完整台帳後確認今天早上03:22 UTC的19份public原件已包括相同2021／2022請求。兩次新body SHA不同但typed facts相同，皆未明列無形資產現金購置，不能算新入口或新資料；初次helper的「new」狀態原件保留，現在明示更正為**兩次重複研究**，沒有追加正式重試、補0或寫SLA成功。[早上已讀完整原件](evidence/source-acquisition/20261011/1560-1303-3023-new-public-annual-complete-native-research.json)、[交叉比對及更正](evidence/source-acquisition/20261011/post-brand-role-financial-current-closeout.json)。

轉向[南亞官方年報索引](https://www.npc.com.tw/j2npc/zhtw/investor/Annual%20Reports)與[官方財報索引](https://www.npc.com.tw/j2npc/zhtw/investor/Financial%20Reports)，兩次native HTTP200取得完整55,401／51,865bytes；年報明列2021–2025 href，財報目前年度選項為2022–2026，不能推論2021文件在其他入口不存在。沿已讀完整HTML實際`doSelectYr`表單action／hidden fields及2022選項，只POST一次原公開form，HTTP200完整53,332bytes；逐列區分2022Q4合併／個體與季度，沒有猜網址或沿檔案上傳日推財年。[完整年報索引](evidence/source-acquisition/20261011/nanya1303-new-official-annual-index-native-research.json)、[完整財報索引](evidence/source-acquisition/20261011/nanya1303-new-official-financial-index-native-research.json)、[觀測表單與2022下載列](evidence/source-acquisition/20261011/nanya1303-observed-2022-financial-form-native-research.json)。

僅下載上述原表單明列的[2022Q4合併PDF](https://www.npc.com.tw/npcfile/public/report/finreport/20230309155547598.pdf)，HTTP200／**5,958,090bytes**完整archive/hash讀回；現行有界native reader回`encrypted_pdf`即停止，未解密、換parser或OCR。合併／年期只是索引標示，PDF正文issuer、財期、scope及科目仍未驗；公開著作權告示保留。這四份新完整原件仍是研究候選OFF，未seed正式cache／接provider／算取得成功，南亞原snapshot SHA及2021FCF null保持。[完整PDF及拒收](evidence/source-acquisition/20261011/nanya1303-new-2022-consolidated-pdf-native-research.json)、[四原件資格及完整限制](evidence/source-acquisition/20261011/nanya1303-new-official-entry-final-qualification.json)。研究共四個新HTTP另加兩個已更正重複HTTP，與冠西電19底層HTTP及1canonical成功分開計算。

**2026-10-11 21:04:57台北**原全部20類仍**18／20**嚴格>80%；財報**93／169＝55.0296%**、近期**175／250＝70.0%**。本輪有真實最新報告財報修復，屬progress；南亞新PDF沒有造成成功增量，完整門檻、公式、期限與歷史失敗保持，goal仍active／未完成，無commit／push。[同窗原20類正式SLA](evidence/source-acquisition/20261011/post-financial-new-official-entry-final-formal-sla.json)。

## 2026-10-11 榮惠與裕慶四份合併年報比較欄正式補齊五年

上一輪冠西電補件屬progress。本輪先重讀目前150份最新快照，94份一般numeric充分及13份金融typed完整者不重抓；41份剩餘年度缺口與2份context未准維持原狀。交叉掃描1,493份既有source-acquisition JSON的完整native receipt／companyId／原請求，不只看canonical SLA：正式台帳稱未試新public的22家，15家其實已有public cashflow研究原件，南亞等不再重查。另7家舊iXBRL全部為`fewer than five consolidated annual filings`；舊formal錯誤保留，缺研究reference不武斷當從未連線。[目前最新年度盤點](evidence/source-acquisition/20261011/post-nanya-current-all-latest-annual-inventory.json)、[正式與研究原件交叉准入](evidence/source-acquisition/20261011/post-nanya-financial-research-coverage-admission.json)。

以已部署四C申報比較欄規則，對2033／6657／6902／6924／6957／7711／7799各一次有界native索引，7個HTTP200完整原件皆保存讀回。6902、6924、6957列2022–2025四份連續合併C；6657、7711各只有2024–2025兩C，2033、7799未抽到C，不能由此推論其他入口無財報或將個體混接。再只查上述三家2022年度現金流：6902的2021比較欄只有CFO與PPE兩必要fact、無無形資產支出，立即停止其他三表／formal。6924與6957各再讀資產負債與損益，2021比較欄九科目明示完整；generic unit renderer只重讀既有完整原件、原epoch保持、0HTTP。合計研究14個native HTTP／14份新完整原件、formal及模型0，不seed正式cache或補成功分子。[七索引及scope限制](evidence/source-acquisition/20261011/seven-old-short-index-new-comparative-eligibility-native-research.json)、[三家首期必要科目](evidence/source-acquisition/20261011/three-four-filings-first-comparative-facts-native-research.json)。

對當前同份四年真缺口報告，各送一次既有`source=financial_statements`：榮惠6924 **HTTP200／2.392950秒**，裕慶6957 **HTTP200／3.430139秒**，各16actual HTTP200，由四份2022–2025官方三表保存完整2021–2025五個財期／每期九科目。2021 FCF分別 **-0.014252／-0.036905十億TWD**；首年在source audit明示`period_year=2021`／`source_filing_year=2022`／`no_primary_filing_for_first_period_claimed=True`，不冒稱存在五份原始年報。各自完整index／3unitJS／12JSON原件與原epoch經現行consumer及readback重播，保留原公式與comparative修訂規則。只新增兩個canonical成功 **439672／439673**，fetch`f2c50228990943b0b9e71c0e9b760320`／`2e2da701f43e4afcbe02a3d376e3ad2b`，32底層HTTP不是32次成功；兩筆DataProvider usage、model_id null、analysis jobs及quality reviews未增。[兩次唯一正式補件](evidence/source-acquisition/20261011/two-four-filings-one-formal-refresh-each-proof.json)。

6924首次200後helper把first_period_basis的`period_year`誤寫成`year`，KeyError及已保存artifact收據原件另存；未再POST或重抓，按實際完整contract以同一份after snapshot／immutable before backup完成只讀readback，才執行原尚未送出的6957請求。原HTML／Markdown、analysis_evidence、五品質metadata、quote／TTM／其他data及source audits原時間皆保持，兩個index四hash吻合，analysis_text_stale=1，沒有新全報告品質結論。本輪runtime79／env／158套件／程序身份未變、未重啟，health／ready200；六件原retry serialized payload全部保持，三件依原排程finished、三件scheduled，未手工重排或取消；old failure432041及全部原零值ledger prefix SHA保持。[首次驗證錯鍵保留](evidence/source-acquisition/20261011/two-four-filings-first-200-initial-verifier-error.json)、[目前完整收尾驗證](evidence/source-acquisition/20261011/two-four-filings-current-closeout.json)。

**2026-10-11 21:21:27台北**原20類仍**18／20**嚴格>80%；financial_statements **95／171＝55.5556%**、recent_catalysts **175／250＝70.0%**。本輪兩件真財報缺口已正式補齊，屬progress；目標仍active／未完成，原全部20類、品質門檻、期限、公式與歷史失敗保持，無新runtime patch／commit／push。[同窗原20類正式SLA](evidence/source-acquisition/20261011/two-four-filings-current-formal-sla.json)。

## 2026-10-11 新公開財報短索引的重複失敗保護

上一輪榮惠與裕慶正式補齊屬progress。本輪重讀近24h財報失敗分布，通用年度SDK降級只有少數，不能因猜測而重排全流程；已存在的普通年度共用快取、官方完整來源先行及300秒19原件缺科目cache保持。真正缺口是新公開入口只讀一份索引後的`fewer than five contiguous published consolidated annual filings`：現行public cache固定要求19份完整原件，六筆已觀測short-index失敗都無法重用。

owned僅`data_fetch/market_sources/mops_public_gap_cache.py`：1份完整native HTTP200索引／原URL及request／SHA／bytes／原取得epoch均可核，且沿原`confirmed_short_annual_index`確認全部issuer／合併scope／headers／preview及download／連續已發布年度後，只有**1–3個C年報**可沿原300秒cache。四C可能完整五財期，不能被誤判短缺；空body、混個體、未知版面、wrongissuer、傳輸／quota或取得不全不快取。warm保留error／None／count0與原fetched_at、retry_at＝原epoch＋300，HTTP／provider attempt0與`empty_cache_count`，不是新成功或新失敗；指紋加入既有strict index helper，原19份完整原件缺科目／比較衝突路徑保持。公開interface先真RED1顯示warm仍重送1HTTP，再63相關green。[精確before與初版input](evidence/source-acquisition/20261011/public-short-index-cache-independent-input.json)。

獨立覆核以46秒前置原件讀取發現P2：短索引預驗證在建立45秒重播deadline前，會重新取得預算。保留原blocked覆核及獨立反例；root新增相同公開反例先RED1，將同一`_ReplayTransport`／deadline建立在原件讀取／parse之前、耗盡立即拒收，collector及final admission沿同一實例。最後11modules含必跑runtime／env／storage／artifact，以及原獨立probe合跑**222passed（221相關＋1probe）**；獨立同範圍**222passed**，沒有未解material finding，重疊不相加444。source-only冷／暖均502且原三artifact不變、expiry與指紋／損毀原件／四C繼續抓取等邊界均覆蓋。[原P2及反例](evidence/source-acquisition/20261011/public-short-index-cache-independent-review.json)、[固定input](evidence/source-acquisition/20261011/public-short-index-cache-fixed-independent-input.json)、[固定版獨立覆核](evidence/source-acquisition/20261011/public-short-index-cache-fixed-independent-review.json)。

六份已保存failed index從compact component SHA／bytes重讀完整gzip，7750及7740符合新short結構；2441四C不能阻擋，6994及1623缺完整strict結構，9103無C，皆不擴張接受。compact未保存原native URL／receipt epoch，初次helper誤預期URL欄位而KeyError後，只讀同原台帳重驗並明示未知，沒有拿SLA時間／mtime造收據。這僅為結構盤點，不是fresh cache admission，沒有將這些原件seed正式cache、重查1623／7740或新增SLA成功。[原失敗原件及精確限制](evidence/source-acquisition/20261011/public-short-index-original-failure-structural-replay.json)。

一檔owned／78preserved＝79runtime、env／158套件核對後，RQ idle時只送一次支援warm shutdown，確認同RQ terminal才TERM role-all／launcher；API-stop session40829觀測exit0、舊canonical76476因受控launcher SIGTERM觀測exit143後，才啟動`./start_mac.command`新keepalive **67209**。新launcher**32003**／worker**32041**／API**32043**及backend cwd吻合，health／ready200；兩件原pending serialized payload、未到期score與durable dispatch保持，本次30／90日retention清理0，old failure432041及全原零值ledger prefix SHA保持，force kill0。冠西電、榮惠、裕慶三份已補齊報告的最新已驗三artifact hashes亦保持。[正式更新與排程保存](evidence/source-acquisition/20261011/public-short-index-cache-release-proof.json)、[現在完整closeout](evidence/source-acquisition/20261011/public-short-index-cache-current-closeout.json)。

本輪formal／native research／manual model／新報告請求皆0，沒有為驗保護再故意送已知失敗或刷healthy。隔離fixture證明冷讀1HTTP、後續有效warm0；正式runtime已更新，但截至**2026-10-11 21:50:38台北**未觀測自然short-cache命中，不冒稱已活網命中或新完整資料。原全部20類仍**18／20**嚴格>80%，財報**95／171＝55.5556%**、近期**175／250＝70.0%**；品質、五年九科目／8則3來源30日、TTL、公式與歷史失敗不改。本輪為已驗實作及部署的progress，goal仍active／未完成，無commit／push。[同窗原20類正式SLA](evidence/source-acquisition/20261011/public-short-index-cache-current-formal-sla.json)。

## 2026-10-11 中華電信完整免費新聞入口正式補齊

金融業盤點重讀凱基金2883、遠東銀2845既有公開完整三表，仍未明列必要的無形資產現金支出，沒有把其他資產變動／未列示值補0或重新送已知失敗。改查當前150份最新報告，64份仍不滿足新聞門檻；中華電2412當前僅4則／4發布者，未取得第一方完整新聞稿。[當前原件缺口盤點](evidence/source-acquisition/20261011/post-short-index-cache-current-all-latest-news-gap-inventory.json)。

新入口為[中華電信訊息專區](https://www.cht.com.tw/zh-tw/home/cht/messages)。以6次ordinary TLS／無登入、重試或轉址的native研究，保存完整索引及其5個實際發布href的完整原文。由完整TWSE主檔精確2412／中華電／中華電信股份有限公司／96979933／CHT／官網host綁定；新聞稿active category GUID、索引tag及日期、原文canonical／h1／og:title／日期／tag及主文均一致。保存全部正文與備註，不拿導覽、公告、未知角色或搜尋摘要當完整文章；來源標issuer_statement／event_assessment not_assessed／coverage partial、window_complete false，5篇全算同一CHT publisher。研究原件不seed正式共用cache或補SLA分子。[六份新完整原件](evidence/source-acquisition/20261011/cht2412-five-new-official-press-originals-native-research.json)、[正式前原件與真缺口准入](evidence/source-acquisition/20261011/cht2412-five-qualified-firstparty-source-admission-v2.json)。

新增`cht_issuer_news.py`並接入normal optional及指定issuer_news補件，沿原30日／8則／3來源、最多5篇／20秒總期限／每HTTP5秒。初次公開interface RED2確認舊版無此入口；邊界測試另抓出root quote aliases衝突並修正。獨立覆核再以source-only public interface重現 first-recognized type 加合併丟alias的P2，初版342passed及原2failed證據保留；修為新2412 preflight逐項核對root instrument_type／quote_type／quoteType，合併context保留兩aliases。最後14modules344＋原2probe＝**346passed**，獨立同範圍**346passed**，P2已關閉，重疊結果不相加。[初版覆核](evidence/source-acquisition/20261011/cht2412-issuer-source-independent-review.json)、[固定input](evidence/source-acquisition/20261011/cht2412-issuer-source-fixed-independent-input.json)、[固定版獨立覆核](evidence/source-acquisition/20261011/cht2412-issuer-source-fixed-independent-review.json)。

4owned／76preserved＝80runtime、env／158套件與程序身份核對；RQ idle只送一次支援warm shutdown，確認terminal後停止owned role-all／launcher。舊canonical67209受控SIGTERM exit143、stop helper exit0後啟動`./start_mac.command`新keepalive **38431**；新launcher40835／worker40863／API40865及backend cwd吻合，health／ready200。一件原pending serialized payload與未到期score、durable dispatch、old failure432041及全部原零值ledger prefix保持，30／90日清理0、force kill0；先前2466／6924／6957已補齊三份報告的三artifact hash保持。[正式重載與排程保存](evidence/source-acquisition/20261011/cht2412-issuer-source-release-proof.json)。

只對當前同份`2412_TW_v4_report_job_aca3c6e3db5a.html`送一次`source=issuer_news`，**HTTP200／4.518688秒／6actual HTTP**，保存5篇完整原文，合格新聞**4→9**，通過原8／3／30門檻。完整主檔是既有共享payload，保存原epoch／digest，HTTP None、cached payload evidence kind明示，不冒稱新native200；完整索引與5文章為native原件，7份唯一原件全部SHA／bytes／epoch重播。僅新增1canonical來源成功 **439844**、fetch`ac00eea801434341a9bb074473c20340`、1筆DataProvider usage（model_id null），沒有model／new analysis／quality review。原HTML／Markdown／analysis_evidence／五品質metadata／quote／TTM／財報／其他source audit原時間保持，index四hash吻合，analysis_text_stale=1；這是資料補齊，尚無新全報告品質結論。[唯一正式補件](evidence/source-acquisition/20261011/cht2412-issuer-source-2412-formal-refresh-proof.json)。

**2026-10-11 22:28:57台北**原20類仍**18／20**嚴格>80%，財報**97／173＝56.0694%**、近期**185／261＝70.8812%**。此輪只新增一個canonical成功；整體數字包含自然執行與視窗移動，不全歸功於此入口。不重抓healthy或其他已知失敗來刷分，完整目標仍active／未完成，五年九科目、期限、公式、品質門檻與歷史失敗保持，無commit／push。[完整正式收尾驗證](evidence/source-acquisition/20261011/cht2412-issuer-source-current-closeout.json)、[同窗原20類SLA](evidence/source-acquisition/20261011/cht2412-issuer-source-current-formal-sla.json)。

## 2026-10-11 創意完整免費新聞稿入口正式補齊

上一輪中華電原文補齊並正式部署為progress。本輪重讀runtime80／env／程序身份與當前150份最新snapshot；仍有63份新聞門檻真缺口，中華電已不在缺口名單，創意3443目前7則／6發布者。官網查找中，日月光與京元目前已索引新聞多為窗口外，未為湊數native下載過期文章；華新非目前新聞gap，未重查healthy。創意官網提供10月5日營收稿與9月22日HBM4E稿，均在原30日內。[當前完整缺口盤點](evidence/source-acquisition/20261011/post-cht-current-all-latest-news-gap-inventory.json)。

新入口為[創意繁中官網](https://www.guc-asic.com/tw)。3次有界ordinary TLS／無cookie、登入、proxy、retry或轉址的native請求保存完整首頁索引與其兩個實際PressReleases href原文；TWSE完整主檔為3443／創意／創意電子股份有限公司／16299879／GUC／裸host `www.guc-asic.com`。第一個helper把無scheme官網交`urlsplit`取hostname而於任何HTTP前AssertionError，已保留setup0HTTP證據，再沿已觀測裸host格式綁定；不是來源失敗或拒絕後換身分重試。索引news card日期／標題／新聞稿角色與原文可見日期／h2／category href／OG URL／zh_TW／site guc／完整主文共同核對；原頁沒有canonical，保留實際metadata，不補造canonical。營收稿144字元正文與IP稿832字元正文完整取得，外部營收附件未下載且不當已讀；導覽、SHARE與附件button文字不墊正文。兩篇均issuer_statement、event_assessment not_assessed，僅一個GUC publisher，窗口仍partial／window_complete false。研究不seed正式cache／補SLA分子。[三份新完整原件](evidence/source-acquisition/20261011/guc3443-new-official-index-and-two-press-native-research.json)、[0HTTP setup錯誤保留](evidence/source-acquisition/20261011/guc3443-initial-bare-master-URL-parser-setup-failure.json)、[完整原件與真缺口准入](evidence/source-acquisition/20261011/guc3443-two-qualified-firstparty-source-admission-v2.json)。

新增`guc_issuer_news.py`並接入normal optional及指定issuer_news補件；沿原30日／8則／3來源、最多5篇／共享20秒總期限及每HTTP5秒。初公開interface RED2確認舊版未支援入口，再以原件可重播的GUC forbidden alias反例RED1修正新adapter中的舊品牌literal。最終15modules **403passed／31.94秒**；獨立同範圍 **403passed／31.74秒**，另4個針對性probe **4passed／2.06秒**，無未解material finding，重疊suite不相加。原master衝突、壞URL／locale／category／article日期／body／saved receipt drift、quote aliases與股種衝突、historical／future先不送article、warm0HTTP與原epoch、deadline含重播、normal optional及source-only保留等邊界均實測。[精確before與input](evidence/source-acquisition/20261011/guc3443-issuer-source-independent-input.json)、[獨立覆核](evidence/source-acquisition/20261011/guc3443-issuer-source-independent-review.json)。

第一次release preflight遇到6449原retry已按22:44:38排程started，queue guard如實阻止重啟；先保存原SLA與live PID／RQ／job證據。只送一次支援warm shutdown，讓同一工作自行完成：原serialized payload SHA保持、RQ finished、analysis_job done、同RQ40872已terminal，才重讀新的quiescent preflight，無取消、強制中斷或手工重排。4owned／77preserved＝81runtime、env／158套件／cwd／identity核對後，stop helper exit0、舊canonical38431受控SIGTERM exit143，才啟動`./start_mac.command`新keepalive **12105**；新launcher45509／worker45537／API45539、health／ready200。所有durable dispatch與零值ledger prefix、old failure432041保持，30／90日retention清理0；原pending完成而不是丟失。[首次live guard](evidence/source-acquisition/20261011/guc3443-first-release-preflight-held-by-live-original-retry.json)、[同一工作完成及唯一warm](evidence/source-acquisition/20261011/guc3443-issuer-source-supported-warm-quiesce.json)、[正式更新](evidence/source-acquisition/20261011/guc3443-issuer-source-release-proof.json)。

只對同份真缺口`3443_TW_v4_report_job_97c5fa336671.html`送一次`source=issuer_news`：**HTTP200／2.705782秒／3actual HTTP**，保存兩篇完整新聞，合格數**7→9**，通過原8／3／30。主檔沿既有共享payload原epoch／SHA、HTTP None與cached kind誠實保存；索引及兩文章為完整native原件，4份唯一原件全部讀回SHA／bytes／epoch並由consumer重播。僅新增1canonical來源成功 **439867**、fetch`e4fed0ba85ab49a6a1408ebb31d6b5c4`、1筆DataProvider usage（model_id null），無額外model／新analysis／quality review。原HTML／Markdown／analysis_evidence／五品質metadata／quote／TTM／財報／其他data與來源時間全保持，index四hash吻合、analysis_text_stale=1，沒有新全報告品質結論；原中華電及三份財報補件bundle hash亦保持。[唯一正式補件](evidence/source-acquisition/20261011/guc3443-issuer-source-3443-formal-refresh-proof.json)、[完整readback](evidence/source-acquisition/20261011/guc3443-issuer-source-current-closeout.json)。

**2026-10-11 22:51:32台北**原20類仍**18／20**嚴格>80%，財報**97／173＝56.0694%**、近期**186／262＝70.9924%**。本輪新完整入口已正式補齊創意新聞缺口，屬progress；全20類目標仍active／未完成，不能把單一個案、離線union或重疊測試數替代整體驗收。沒有為刷分重抓healthy、沒有放寬五年九科目／品質／公式／TTL或刪原失敗，無commit／push。[同窗原20類正式SLA](evidence/source-acquisition/20261011/guc3443-issuer-source-current-formal-sla.json)。


## 2026-10-11 宏碁完整免費新聞入口正式補齊

[宏碁繁中新聞專用官網](https://news.acer.com/zh)的完整索引與五篇實際發布原文經匿名TLS取得及封存，TWSE精確2353／宏碁／宏碁股份有限公司／20828393／ACER與網站owner、回連registered網站共同綁定。五篇保留449／1181／1400／5745／1377字元全文、原發布日、完整收據；dateModified不當新發布，一個ACER publisher、issuer_statement、事件影響未評估、窗口partial。另corporate頁傳輸失敗保持，沒有同失敗URL重試。正常optional及source-only共用新adapter，30日／8則／3來源、20秒總期限與各品質門檻保持。

470項相關與獨立同470項、另3probe通過，4owned／78preserved＝82runtime、env／158套件、佇列與原零值帳本核對。一次正式source-only刷新同份2353報告，HTTP200／7.629秒／6actual HTTP，當前合格新聞6→11；只新增1canonical成功439869。完整7份唯一原件讀回，cached主檔HTTP None與原epoch不續期。正文／Markdown／analysis_evidence／五品質metadata／quote／TTM／財報及其他來源時間保持，需重分析，不是新報告品質通過。見[正式補件](evidence/source-acquisition/20261011/acer2353-issuer-source-2353-formal-refresh-proof.json)、[完整驗證](evidence/source-acquisition/20261011/acer2353-issuer-source-current-closeout.json)。

## 2026-10-12 南茂完整免費新聞入口正式補齊

[南茂新聞訊息索引](https://www.chipmos.com/chinese/news/news-list.aspx?MID=1)與其實際[2026年9月及Q3營收原文](https://www.chipmos.com/chinese/news/news-detail.aspx?NID=271)完整匿名原件HTTP200保存。精確TWSE8150／南茂／南茂科技股份有限公司／16130042／ChipMOS與registered網站綁定；MID=1索引URL、原標題／日期、原文Oct8發布日／pressline／TWSE8150／4293字元完整正文共同重播。官網共用首頁canonical與Facebook OG保持原貌，不能作文章URL證據。未稽核數字、Forward-Looking Statements與全文聯絡資訊保留；一篇只算一個ChipMOS publisher，不宣稱事件影響或完整時間窗。

最初未支援路由的2案例RED保持，native header/card實際格式按完整原件修正。62新案例及相關17模組532passed／40.96秒；獨立同532passed／43.32秒、另3probe，無material finding，重疊suite不相加。4owned／79preserved＝83runtime，空閒前檢後只送一次支援warm，原canonical48678受控exit143，新canonical37815（launcher60491／worker60519／API60521）、health／ready200；env與158套件、全部原佇列、failure432041及零值帳本prefix保持。見[覆核](evidence/source-acquisition/20261011/chipmos8150-issuer-source-independent-review.json)、[正式重載](evidence/source-acquisition/20261011/chipmos8150-issuer-source-release-proof.json)。

唯一正式刷新同份8150報告，HTTP200／1.203316秒／2actual HTTP、fetch17b0584e3e9740deb42180e70bdff968；合格新聞7→8通過原8／3／30，只新增1canonical成功439870。共享主檔、索引、原文共3唯一完整收據讀回，主檔原epoch／cached kind／HTTP None誠實保持。正文、Markdown、analysis_evidence、五品質metadata、quote、TTM、財報與全部其他audit保持，index四hash吻合，analysis_text_stale=1；既有宏碁、創意、中華電及三份財報bundle hash也保持，無模型、新報告或品質review請求。見[唯一正式刷新](evidence/source-acquisition/20261011/chipmos8150-issuer-source-8150-formal-refresh-proof.json)、[完整驗證](evidence/source-acquisition/20261011/chipmos8150-issuer-source-current-closeout.json)。

**2026-10-12 00:20:16台北**原20類仍18類嚴格>80%，財報95／168＝56.5476%、近期175／248＝70.5645%。rolling24h舊事件自然移出，不能把比率變化全歸新入口；全20類目標未完成，保持免費、五年九科目與所有品質／公式／TTL／歷史失敗。新代104頁完整2022未加密財報研究仍未入正式：前12頁與第10頁原生視讀未證明2021歸母淨利，不能用總淨利替代。佳大2033新公開2021CF為個別、無明列無形資產取得，亦不補零或升格合併；兩者保留研究原件及未知。見[同窗正式SLA](evidence/source-acquisition/20261011/chipmos8150-issuer-source-current-formal-sla.json)、[新代視讀](evidence/source-acquisition/20261011/syntec7750-2021-parent-attribution-equity-visual-research.json)、[佳大同原件讀回](evidence/source-acquisition/20261011/chiata2033-individual-earliest-cashflow-same-original-readback.json)。


## 2026-10-12 玉山完整免費新聞及報價索引排除正式驗證

[玉山金控新聞入口](https://www.esunfhc.com/zh-tw/news-center/news-center/news)的完整162281-byte索引及三篇實際href原文，以4次匿名TLS原生HTTP取得，全部完整原件封存。三篇發布日10月5日／9月24日／9月21日，正文583／605／755字元；供應商活動9月23日不取代原發布9月24日。TWSE精確2884／玉山金／玉山金融控股股份有限公司／70796305／E.S.F.H／registered網站綁定，索引雙連結／h3／日／完整描述與原文h1／可見日／footer owner／全文重播。上游article canonical與OG實際含重複https://，完整保留且不修復、跟隨或作文章身分；無標題文章不補造，child-only或非母公司正文起首不升格。僅一個E.SUN FHC publisher／issuer_statement／事件影響未評估／partial，不改原8則3來源30日。

發現當前玉山6筆內含1筆「玉山金融控股 | 2884.TW 股價走勢與即時報價 - BigGo 財經」Google wrapper。新規則僅對精確publisher及完整報價索引標題排除，原件保持unverified；其他publisher、direct原文及一般文章不變。4個初始公開behavior RED保持；67新案例與20模組621項相關通過，獨立同621passed／47.21秒、另7probe／1.73秒，無未解material finding。額外實際snapshot source-only隔離replay1passed／2.13秒確認quote的title/link/source/summary原值保留、core與舊audit保持；最初/tmp probe缺import path失敗保留，未操作provider。重疊suite不相加。見[完整原件准入](evidence/source-acquisition/20261012/esun2884-three-qualified-parent-firstparty-source-admission.json)、[凍結範圍](evidence/source-acquisition/20261012/esun2884-issuer-source-independent-input.json)、[獨立覆核](evidence/source-acquisition/20261012/esun2884-issuer-source-independent-review.json)。

5owned／79preserved＝84runtime、env／158套件及PID/cwd核對，空閒前檢後只送一次支援warm；原canonical37815受控exit143，新canonical11738（launcher66058／worker66086／API66088），health／ready200，六佇列／durable jobs／零值ledger prefix與原failure432041保持。唯一source-only正式刷新同份2884報告，HTTP200／4.109138秒／4actual HTTP，正確合格5→8（舊6含報價索引），通過原8／3／30；只新增1canonical成功439871、fetchd248ec979b3b48138cc4172407f065b2。5唯一完整保存原件全部重播，cached完整主檔原epoch／HTTP None不續期。原HTML／Markdown／analysis_evidence／五gate／quote／TTM／財報及所有其他來源audit保持，index四hash吻合、analysis_text_stale=1；原南茂、宏碁、創意、中華電及三份財報bundle hash保持，無模型／新報告／quality review請求。closeout helper一個錯檔名在任何讀回前FileNotFound的證據保存，只修/tmp helper，再讀同一次已成功正式結果，沒有重送API。見[正式重載](evidence/source-acquisition/20261012/esun2884-issuer-source-release-proof.json)、[唯一正式刷新](evidence/source-acquisition/20261012/esun2884-issuer-source-2884-formal-refresh-proof.json)、[完整closeout](evidence/source-acquisition/20261012/esun2884-issuer-source-current-closeout.json)。

**2026-10-12 00:49:04台北**原20類仍18類各嚴格>80%，財報95／168＝56.5476%、近期176／249＝70.6827%，全目標未完成。同輪南茂與玉山共2次真缺口正式刷新；研究16次native HTTP保持研究用途，不seed正式快取、不灌正式分子、不重抓健康或同已知失敗來刷分。見[同窗正式SLA](evidence/source-acquisition/20261012/esun2884-issuer-source-current-formal-sla.json)。

新代7750另取得新的2023、2024、2025官方三表完整原件，共9次native HTTP，九科目及2023比較欄2022全明示；同已取得的2022原生完整104頁未加密財報可提供2021比較資料候選。原pypdf6.19.0在原10秒／512MB／零parser warning約束內只讀新physical50–64頁；62頁EPS附註明列歸屬母公司普通股持有人淨利、63頁2022/2021年度numerator536502／941291千元，兩頁完整圖像視讀。2022九科目與2023比較欄全部一致；2024CFO在2025比較欄由1392304000修訂為1393999000 TWD，原件兩版保留，候選五期FCF依原帶符號PPE＋intangible公式為−153714000／922757000／1078066000／1206991000／2017627000 TWD。2021九科目目前仍為人工研究讀值，尚無專用有界PDF parser／發行人書冊與完整五期typed consumer契約，**未啟財報provider、未修改既有報告、未增加財報成功**；generic PDF100頁與五年九科目不放寬。另p7 renderer helper guard失敗、回傳診斷未保留的限制如實記錄，未重跑或換parser；不聲稱整本104頁全文覆蓋。見[新增三年九科目原件](evidence/source-acquisition/20261012/syntec7750-two-new-published-2024to2025-all-nine-facts-native-research.json)、[2023三表及2022比較](evidence/source-acquisition/20261012/syntec7750-2023-new-published-consolidated-structured-facts-native-research.json)、[五期候選研究及修訂](evidence/source-acquisition/20261012/syntec7750-new-free-complete-five-period-originals-candidate-admission-research.json)。

重啟後自然UI讀取另外顯示daily-dashboard先503，quality read於31.845秒完成status ok；沒有為驗證另送一次request，來源修正未宣稱前端冷啟動已改善。該剩餘限制與provider來源／模型429分開記錄，見[自然讀取證據](evidence/source-acquisition/20261012/esun84-natural-UI-daily-cold-read-remaining-limitation.json)。本輪無commit／push。


## 2026-10-12 新代五年完整免費財報入口正式驗證

[證交所電子資料查詢下載目錄](https://doc.twse.com.tw/server-java/t57sb01?co_id=7750&colorchg=1&mtype=A&seamon=&step=1&year=111)公布的新代2022查核合併財報原件，與MOPS2023、2024、2025公開三表，已由新bridge同口徑連成2021–2025完整五年九科目。2021是2022原件明示比較年度，來源manifest為4份，沒有冒稱五份primary filings。完整TWSE名冊／7750／新代科技股份有限公司／89660813／Syntec／registered網站核對，catalog/form實際公布PDF連結、全2865508bytes／104頁SHA保持；2021採期末而非開帳欄，母公司普通股EPS定義／基本與稀釋numerator／僅母公司普通股權益核對，PL總淨利僅crosscheck。FCF2021為−153714000 TWD，沒有把負值或缺值補零；2024CFO按2025比較欄修訂為1393999000 TWD，原兩版保留。

專用reader讀明列physical1、4、6、7、8、9、10、11、62、63頁；不是整本104頁native全文覆蓋。沿原pypdf6.19.0 strict、10秒、512MB、8MB stream、零warning、stdio／kill-reap界線，generic100頁worker不改；ContentStream bytes及root CM原型誤用先以synthetic重現修正，初版診斷保留。CPU退出與taskinfo更新競態最多20ms結算，活程序accounting失敗仍拒絕。保存audit完整17原件（master/index/catalog/form/book、3templates、9三表），full receipt projector可從保存報告重建；金融逐格證據名為monetary_cells，原secret redaction保持。官方名冊24h cache與issuer-news-raw30min cache分開核對actualnamespace／完整bytes／digest／URL／原epoch／當時有效TTL，HTTP None／無新HTTP如實保留，矛盾cache/native標記拒絕。

首次正式補件502／0.998秒、原報告3artifact保持，ledger439872保留。同次已封存491bytes nativeform讀回發現server temporary-path stamp02:29:03，比本機取得02:29:02.059056快0.940944秒；同原件RED 2failed3passed，最小修正只讓receiptEpoch−serverGenerationStamp下限0→−1，上限300不變；publication/asof/freshness/原epoch不改。489相關及獨立同489／另5無效時間或網址反例通過；initial9owned82preserved、後clock1owned90preserved，正式runtime仍91，canon8148／health、ready200／158packages與env保持／所有queues0，不forcekill、不改排程。見[初版正式失敗](evidence/source-acquisition/20261012/syntec7750-bridge-7750-formal-refresh-proof.json)、[同原件失敗定位](evidence/source-acquisition/20261012/syntec7750-first-formal-download-clock-failure-same-original-readback.json)、[時鐘覆核](evidence/source-acquisition/20261012/syntec7750-download-clock-independent-review.json)。

修正正式重載後僅一個新state真缺口補件，HTTP200／4.212秒／16actual HTTP，7750_TW_v4_report_job_ae34b52d5113.html已補齊2021–2025，17完整原件從保存audit重新核對，parent439873為唯一新financial成功。HTML／Markdown／原analysis_evidence／五品質metadata／quote／即時TTM／非財報來源及時間保持、analysis_text_stale=1；不聲稱新全報告品質通過。原3金融與5新聞共8份既有改善bundle hash保持，舊失敗432041與439872及零筆台帳保持；沒有model、新report、qualityreview、commit/push。見[實際成功補件](evidence/source-acquisition/20261012/syntec7750-post-clock-repair-7750-formal-refresh-proof.json)、[最終正式驗證](evidence/source-acquisition/20261012/syntec7750-bridge-current-closeout.json)。

**2026-10-12T02:39:55.118075+08:00台北**原20類18類各嚴格>80%，財報83／154＝53.8961%、近期176／249＝70.6827%，尚未達成全goal。此turn只有financial新failure1＋success1；滾動窗既有成功離窗，不能把總比率變化全歸功於新入口；研究與offline不灌正式分子。見[同窗SLA](evidence/source-acquisition/20261012/syntec7750-bridge-current-formal-sla.json)、[滾動窗與新兩筆觀測核算](evidence/source-acquisition/20261012/syntec7750-rolling-window-and-new-formal-events-accounting.json)。先前前端daily-dashboard冷讀503仍在natural啟動紀錄，本次財報入口不宣稱修好該問題。

## 2026-10-12 新完整免費原件與公開消息入口續查

高力8996改查證交所實際公布的2021、2022第四季查核合併財報書冊，兩份完整原件分別3,686,871／1,954,966 bytes，與既有缺欄的公開JSON是不同資料入口。沿原資源與parser guard，2022原件遇parser warning後不重試或換parser；2021原生文字為partial，完整現金流量physical12／13頁按有界renderer視讀。2021營業現金流295,299仟元、PPE購入100,621仟元、其他非流動資產增加19,960仟元可見，但沒有單列取得無形資產；不得拿其他非流動資產替代、由淨額平衡推毛額零或把未列科目補零。未啟用財報provider、未改報告或當成九科目成功。見[兩份完整原件最終判定](evidence/source-acquisition/20261012/kaori8996-new-two-full-books-final-qualification-held.json)。

完整TWSE原名冊核對後，一次取得新美齊、中再保、榮惠、東訊四個registered官網root及四個實際公布的後續入口。東訊root所列最新新聞仍2025、中再保root所列信評2026-08-13及公告2026-09-03均過30日。新美齊root是前端空殼；公開main asset顯示Base/GetMenu，但無session的native POST400保持。普通新瀏覽器從公開首頁正常取得防偽session，無使用者登入或匯入cookies，讀到[重大新聞](https://www.jean.com.tw/page/news/1739?tab=1742)、[公司訊息](https://www.jean.com.tw/page/news/1739?tab=1745)、[最新活動](https://www.jean.com.tw/page/news/1739?tab=1748)完整三分類8／7／4則。全部超過30日，部分2026列表日期內文另列2021／2022原始報導日；不把轉載／上架日當原始新聞發布日。保存derived browser DOM、snapshot、同host網路觀測與圖像；不是native完整HTTP原件重播，也沒有複製瀏覽器防偽session到正式provider。

[北極星官方投資人頁](https://polarispharma.com/investors/)與[榮惠官網](https://www.ei-kei.com/)另核對公司名稱入口。四個新RSS query的完整原件只作研究，原20筆candidate headroom與原時間／公司／非文章／去重／publisher gate保持。北極星名稱query9筆中研究alias模擬合格7、帶代號query8筆中合格6；榮惠完整集團名query為0、較短股票名稱query13筆中模擬合格5。都不足8則，沒有啟用alias或增加正式來源成功。首個RSS的研究helper誤把既有accepted／audit二元回傳當三元；保存同一完整原件重播修正、沒有HTTP重試，遺失的精確取得epoch保留unknown，檔案建立時間不冒稱取得時間。

共19次有界native curl研究HTTP，另外是一般公開瀏覽器讀取；來源研究不計正式SLA或model API成功。正式ledger最大439873、model API帳本最大729583保持；runtime91、env、canonical8148、health／ready200、queues0保持，無重載／模型／新報告／正式補件／commit／push。**2026-10-12T03:41:54.264673+08:00**原20類17類各嚴格>80%，財報75／135＝55.5556%、近期176／249＝70.6827%、法說27／36＝75%，全目標未達成。見[續查與當前正式驗證](evidence/source-acquisition/20261012/post-syntec-new-free-entries-research-current-closeout.json)。

## 2026-10-12 天瀚獨立合併財報、FinMind精確期間與SEC候選續查

[天瀚官方年報列表](https://www.aiptek.com.tw/web/information/information_year.jsp?lang=en)公布兩份原始href，年度由原表格核對，不猜檔名。2022年報完整5,566,147 bytes／HTTP200封存，但同一pypdf6.19 strict／10秒512MB有界reader的generic100頁上限拒收；原件保持，不改上限、重試或截短原年報。再由同一完整原頁的實際導覽，取得[季度合併財報列表](https://www.aiptek.com.tw/web/information/information_season.jsp?lang=en)另行發布的2022第四季文件，這是獨立完整財務報告原件，不是前一年報的截取。完整5,209,856 bytes／37頁，原生coverage partial、empty4–7、garbled0；1頁封面明列6225／天瀚科技股份有限公司及子公司／111與110年度，8–11頁財務主表有native文字。查核報告4–7頁沒有原生文字，不聲稱查核意見或整本全文已驗證。

完整physical11合併現金流明示新台幣仟元、2022／2021日期欄。2021 CFO−8,506仟元、取得無形資產−100仟元明示，2022各為−3,186／−22仟元；但兩期未單列取得PPE現金。第21頁資產增添dash不是現金支付，投資活動淨額與唯一列相等也不推毛額PPE0，重大交易揭露門檻不能證明所有購置均為0。未計算完整FCF、補舊報告或啟用來源。見[新年報原件與拒收](evidence/source-acquisition/20261012/aiptek6225-new-published2022-full-annual-book-native-research.json)、[獨立財報完整原件及reader](evidence/source-acquisition/20261012/aiptek6225-new-published2022-standalone-financial-book-native-research.json)、[精確缺欄判定](evidence/source-acquisition/20261012/aiptek6225-new-complete-originals-final-qualification-held.json)。

[FinMind官方個股現金流dataset契約](https://github.com/FinMind/FinMind-Doc/blob/master/docs/tutor/TaiwanMarket/Fundamental.md)支持免費單一data_id；只對6225／2021-12-31一次新精確期間query，沿空token身分，無key發現或borrow、redirect／retry／proxy／TLS降低。HTTP200完整API20筆的CashFlowsFromOperatingActivities為−8506000 TWD，與原財報×1000相符；API未提供必要PPE或intangible現金列，即使原財報明列intangible也不能假設此API已有該欄。沒有把單期CFO相符當所有年度、scope、三表或商用授權已驗證；現有FinMind fallback的capex_scope_unverified／FCF None保持。見[新精確期間原件](evidence/source-acquisition/20261012/finmind6225-new-exact2021-cashflow-native-research.json)。

[統新官方財報列表](https://www.nextapogee.com.tw/ch/investors2-3.php)native首次回curl60／無HTTP status，正常TLS驗證未通過，停止、不改TLS／hostname／header或繞過。新增[SEC官方Company Facts API候選](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)，官方說明免auth／API key，僅aggregate非custom taxonomy及entity-wide facts，仍不能假設所有必要科目存在。既有sec_edgar_provider的contact@stockagent.local為不可聯絡占位值；依[官方自動化存取規則](https://www.sec.gov/about/webmaster-frequently-asked-questions)已詢問真實系統聯絡資訊，native新SEC API0，舊SEC filing403與原host限制保留、不換身分或取受拒原件鏡像。

本輪6次有界native研究請求／5份完整HTTP200原件／1次TLS拒收，含兩份完整PDF；研究未計正式分子。更正先前快取判定：doctor的CACHE_BACKEND=redis為ApiRuntime設定，不等於source facade。cache_store預設建立SQLite、backend無setter接線；provider shared cache／endpoint cooldown／persisted circuit使用此facade。當時Redis guard讀取不證明來源guard不存在；[更正證據](evidence/source-acquisition/20261012/source-cache-backend-previous-evidence-correction.json)保留原誤判檔／hash，不遷移快取、不改既有guard或TTL。**2026-10-12T04:23:46.251104+08:00**原20類仍17類嚴格>80%，財報75／135＝55.5556%、近期176／249＝70.6827%、法說27／36＝75%。canonical8148、runtime91／env／process、health與ready200、queues0、ledger最大439873與模型帳本729583保持；無runtime修改、正式補件、模型、新報告、重載或commit/push。見[當前完整驗證](evidence/source-acquisition/20261012/aiptek-apogee-new-free-entries-current-closeout.json)與[正式同窗SLA](evidence/source-acquisition/20261012/aiptek-apogee-new-free-entries-current-formal-sla.json)。

## 2026-10-12 新版MOPS匿名原件入口與補充公告日期實測

- 沿既有免費來源搜尋要求，只作新入口研究。原公開月索引的action提供固定`POST https://mops.twse.com.tw/mops/api/t05st01_detail`與四個公開參數；現有程式卻映射回legacy GET。本輪使用普通httpx固定子程序，HTTPS正常驗證、無auth／cookie／代理／redirect／retry，每請求4秒、256KB且每公司20秒；查當前source facade SQLite冷卻，沒有以Redis key空缺推定可用。
- **19次實際研究HTTP，七份完整公告原文**：2442新美齊2、2845遠東銀1、6550北極星藥業-KY2、6924榮惠-KY創2。索引與原文的公司代號／短名／市場／序號／主旨／發言日期時間逐筆一致，完整「說明」為61–2053字；原件bytes／hash／public POST參數／原取得時間保存，未截字、沒有以摘要或搜尋結果冒充原件。六份HTTP200內的payload406「查無相符資料」保留不算成功，其中2851／2321兩月份皆空。native response完整不等於報告門檻通過或整類來源成功。
- 初輪2851空回應被研究程式當成code200形狀而停止；保存原失敗，只本機讀回判明payload406，不重抓9月。下一次讀不同10月及東訊兩月，同樣保留空回應。另一輪6924的既有月索引日期規則拒收亦保留；只對尚未請求的兩個原published action取原文，不改參數或猜新的日期URL。
- 榮惠10/8「補充公告」的原action enterDate仍10/7，但原JSON發言日期／時間為10/8 14:48:37，與索引完全一致。現有`fetch_monthly_candidates`對同份保存索引的**離線重播**只回一筆、invalid_row1／partial，證明強制enterDate等於公布日期會漏掉已核對的補充公告。此日期假說已證實；未放寬正式驗證或部署修正。未來接入必須保存原action／原件收據，核對原文公布日期與完整序號／主旨，且為POST原件提供內部唯一key，不能為每篇偽造GET網址或讓共用Page URL吞掉其他公告。
- 七篇來源都是同一官方publisher，只適用official disclosure，**不充當三家獨立媒體、法說逐字稿或五年九科目**。本輪沒有啟用provider、改runtime、送正式補件／模型／新報告、重載或commit/push；研究不寫入正式SLA。原93組aggregate重複已正確排除，其中62組只有一筆fetched、31組兩筆都aggregate，沒有多筆同時進分母，所以未做去重或刪改歷史計數。
- **04:59:44+08**原20類仍17類嚴格>80%；法說27／36=75%、財報75／135=55.5556%、近期171／244=70.082%。相對04:23的176／249，五筆舊成功自然退出rolling24h窗口，不是本輪多了失敗；原source ledger與model ledger最大439873／729583保持。canon8148、protected91／env／process保持，health／ready200、六queue均0、running0。見[當前完整查驗](evidence/source-acquisition/20261012/mops-new-json-entrances-current-closeout.json)、[補充公告原件](evidence/source-acquisition/20261012/mops6924-published-unchanged-actions-original-detail-native-research.json)、[解析器離線重播](evidence/source-acquisition/20261012/mops6924-supplementary-announcement-existing-parser-offline-replay.json)、[窗口變動證明](evidence/source-acquisition/20261012/mops-current-recent-rate-natural-window-change.json)。全goal未達；本次新原件及日期語义是實質進展，後續仍需完整接入與正式真缺口驗證。


## 2026-10-12 新版MOPS完整公告正式接入與原20類驗收

- 本輪把前一輪新入口研究轉成正式元件。公開`POST https://mops.twse.com.tw/mops/api/t05st01`索引公布的`POST https://mops.twse.com.tw/mops/api/t05st01_detail`和四個原參數原樣保存；只開啟已分別native驗證的2442新美齊、2845遠東銀、6550北極星藥業-KY、6924榮惠-KY創。其他公司、9103 TDR、既有cache／限額與來源退路保持。固定匿名httpx從新入口第一次請求起使用、不輪換身分，4秒單次／20秒共同期限／256KB／最多64候選與三月份；payload406明確空回應保持非成功，無TLS／proxy／auth／cookie繞過或重試。
- 索引與原文代號／公司／市場／序號／主旨／發言日期時間逐項核對，完整「說明」20–12000字、未截短。榮惠10/8 14:48:37補充公告的原action enterDate=1151007在正式原件仍成立；不把action日當公布日或改參數。typed收據存完整索引及原文bytes／sha256／byte count／原取得epoch／POST參數，保存後由`verified_json_record`重播；公司矛盾、刪marker、body修改甚至重算hash、原件不可讀仍拒絕。內部資料不帶入模型prompt。
- 獨立覆核找到一項P2：三篇MOPS原件轉SearchResult後共用實際Page URL，原通用去重錯誤合為一篇，5篇外部＋3篇官方只有6篇而非8篇。相同／不同標題兩項隔離反例先失敗；修正僅讓已通過原件核對的trusted caller以獨立action key提供可選內部identity，不改SearchResult公開URL、dataclass、外部parser或一般去重，也不接受外部payload自帶身份覆寫。原覆核與失敗保存，[修正後完整覆核](evidence/source-acquisition/20261012/mops-json-originals-fixed-independent-review.json)已無未解material findings。root隔離23檔321passed；獨立同321加原11probe共332passed，另9trust／compatibility probes含500組default前後比對，不把321＋332當不同653項。
- 13owned／82preserved共95runtime經正式`start_mac.command`重載；原RQ支援warm shutdown、worker及owned launcher正常SIGTERM、無force kill，Redis BGSAVE成功。95檔、原env、158套件版本與process identity重核；canon46252，worker --role all／uvicorn8080，health／ready200。原source零筆prefix、439872及432041失敗、分析job／dispatch與retry內容保持。source guard沿實際cache_store SQLite，不把ApiRuntime Redis設定當guard真相；不遷移／清空／延長TTL。見[正式重載憑據](evidence/source-acquisition/20261012/mops-json-originals-release-proof.json)。
- 四份實際缺口報告source-only刷新均HTTP200：2442兩則（4actual HTTP）、2845一則（3）、6550兩則（4）、6924兩則（4），合計15actual HTTP、七則完整原文／四筆新正式success439874–439877。保存後再讀完整原件及報告index hash；HTML／Markdown、分析evidence、五品質metadata、quote／TTM／財報與core原audit保持，analysis_text_stale=True，沒有whole report或模型呼叫，非Data Provider計數297406保持。七則只算一個official publisher，不當三家媒體、法說逐字稿或五年財報。個別公告成功不代表報告原8篇／3發布者／30日已過。
- 初次四個本地API403是helper未附既有mutation token，沒有送外部provider、無成功分子；原403回應與證據完整保留。只沿既有`/api/client-config`讀token於記憶體、使用原X-Mutation-Token，不記錄／改token或停授權guard。2442和6550取得後，驗證腳本因錯把derived freshness當不可變core／忽略較早原audit而停；本機重讀原件與既有快照補正驗證、未再次請求成功公司。6550 assessment取得epoch採原provider audit1790840696.473673，較舊workflow summary1790840700.1087549早約4秒，原top-level quote epoch與audit保持；這是已部署既有保守重評，不是假fresh。兩件elapsed在停止前未保存則記None、不推算。見[帶原失敗的正式元件證據](evidence/source-acquisition/20261012/mops-json-originals-authenticated-formal-source-refresh.json)。
- **2026-10-12T05:57:42.373612+08:00**最新同窗原20類仍17類嚴格>80%；法說27／36=75%、財報63／99=63.6364%、近期135／189=71.4286%。比率來自真實rolling24h，舊資料自然離窗；財報本次沒有新請求，不能把其比率變動歸因公告補件。原8／3／30、五年九科目／typed sector、FCF公式／quality gates、quota／TTL／cooldown保持，原空回應及拒收不刪。**全goal未完成**；目前是可驗證的新免費入口實質進展，後續仍補法說、財報與獨立新聞來源。沒有commit/push。見[當前完整查驗](evidence/source-acquisition/20261012/mops-json-originals-current-closeout.json)及[原20類正式SLA](evidence/source-acquisition/20261012/mops-json-originals-current-formal-sla.json)。


## 2026-10-12 富威及佳大新完整原件、合併口徑與現金流重分類

- 上一輪新版MOPS來源正式接入及四份真缺口元件補件屬progress，本輪沿原20類各strict >80%的免費來源目標，先查實際earnings空回應。1325／3653／2466／6152為當年度MOPS valid_empty後有舊年度metadata，9103兩年度空；沒有把它們改列not_applicable、刪除失敗或重抓健康context。原百一官網拒絕保持，不換身分／TLS／cookie或拿鏡像繞過。
- 最初找到了[Fositek官方財報PDF目錄](https://www.fositek.com/Portals/0/zh-tw/FileUpload/%E6%8A%95%E8%B3%87%E4%BA%BA%E5%B0%88%E5%8D%80/%E5%B9%B4%E5%BA%A6%E5%8F%8A%E6%9C%9F%E4%B8%AD%E8%B2%A1%E5%8B%99%E5%A0%B1%E5%91%8A/FinancialReports.pdf?v1=)，原始三頁／218565bytes及132annotations完整保存。physical2視覺核对2021年度合併欄和原annotation連結；只一次原published HTTP URL回301，沿實際Location到同host／同path HTTPS取得2021完整1258615bytes／55頁原件，沒有自行換scheme、身份、重試或降低TLS。封面明示6805／富世達，與缺口6994／富威電力不同；完整TWSE主檔legal／UBN及當前report快照再次核對，**不把這份來源或數值用於6994**。原研究filename中的fositek6994是已否定的目標關聯，原檔名／原失敗思路及hash保留，另列正確資格拒收；2023年度目錄link實際指2022Q2、2020個體欄指2019合併，也不按可見標籤猜年份。generic reader的4–7頁空文及51garbled保持、不宣稱audit opinion或全文完整解析。見[錯目標資格](evidence/source-acquisition/20261012/fositek6805-new-original-wrong-target6994-qualification-held.json)。
- 改查[富威6994官方IR頁](https://www.fwp.com.tw/Investor)，一次native200完整167419bytes，同原TWSE主檔6994／富威電力股份有限公司／82921412／官網以及原report一致。頁面實際發布的Next script再一次200完整19566bytes；它明列2021個體、2022個體及重編、2023個體／合併、2024–25合併，並明列file server base及year/key生成式。只沿這個實際公開生成式下載兩份新原件，不猜檔名，不送script中的SessionConverApi或匯入session：2022重編財報54頁／3280074bytes、2023合併53頁／2155617bytes，普通匿名5秒／8MiB／共同20秒、無重導／retry／proxy／auth／cookie／TLS bypass，每份200完整bytes／sha256／epoch重讀。source facade SQLite未有active fwp host guard；未用ApiRuntime Redis absence推定source readiness。見[完整IR入口](evidence/source-acquisition/20261012/foxwell6994-new-complete-official-financial-index-native-research.json)、[公開財報生成式](evidence/source-acquisition/20261012/foxwell6994-published-financial-page-script-native-research.json)、[2022重編原件](evidence/source-acquisition/20261012/foxwell6994-new-published-2022-restated-original-native-research.json)、[2023合併原件](evidence/source-acquisition/20261012/foxwell6994-new-published-2023-consolidated-original-native-research.json)。
- 2022重編完整physical7／8／9／11原生文字提供2021比較年度九科目；physical11全頁視覺核對CFO11551、PPE現金−11879、INT現金−820（TWD仟元），均明列、不填0。這仍是研究手工轉錄，不是production parser或五年C scope成功。2023合併physical13／16再完整視覺核對：2022比較CFO−126645，相對舊個體−128570差+1925；應收租賃款減少1925由投資列移到營業，投資淨額−1595667→−1597592，現金淨變動117303保持，PPE−186600／INT−2500保持。scope表明示旭威認證於2023成立／100%、2022欄為dash，不當數字持股0。這是實際期別／分類差異；**不能由2022比較重分類推算2021 CFO，也不能因部分科目相等直接拼五年個體與合併**。2021同口徑或重分類CFO仍未證，剩餘2024–25不先抓、provider不啟用，原五年九科目／品質／FCF公式保持。generic reader對兩份audit掃描空頁標partial保留，未假稱查核意見已讀。見[2021比較資格](evidence/source-acquisition/20261012/foxwell6994-new-2022-complete-original-comparative-scope-qualification-held.json)及[合併比較與重分類資格](evidence/source-acquisition/20261012/foxwell6994-new-2023-consolidated-comparative-reclassification-qualification-held.json)。
- 另只讀回已保存的佳大2033完整MOPS index原bytes，確認2021–25五份A個別申報，而非C合併。沒有重抓index、修改原435180的無C失敗或seed正式cache。只對尚未請求的2021 A published download一次native200，完整484360bytes iXBRL保存，明示ProfitLoss14725000 TWD／Equity1046890000 TWD（same issuer/calendar/TWD/scale），這兩個A科目不同於C-owner tags；原parser正確不互代。原明示CFO−65557000及PPE現金−9052000，但沒有無形資產現金支出tag，其他investment property明列0亦不能移作INT0。停止其餘四期下載，不稱同scope五年九科目已完整或啟用來源。見[五份A原索引讀回](evidence/source-acquisition/20261012/chiata2033-five-published-individual-filings-existing-index-readback.json)、[新完整第一期原件](evidence/source-acquisition/20261012/chiata2033-new-published-2021-individual-XBRL-native-research.json)及[必要欄位與scope資格](evidence/source-acquisition/20261012/chiata2033-new-complete-individual-original-first-period-qualification-held.json)。
- 合計8native研究HTTP，7完整200原回應及1個同resource301；其中3份完整PDF財報與1份完整iXBRL，另外為目錄／IR／公開script。研究未計SLA分子或分母、未送正式source-only／模型／whole report、未改runtime／部署／commit/push，read-only無需重跑runtime tests。**2026-10-12T06:16:49.941630+08:00**原20類仍17類嚴格>80%；法說27／36=75%、財報63／99=63.6364%、近期135／189=71.4286%。95runtime／env／158套件／canonical46252與正式程序保持，health／ready200、六queue均0、RQ idle；上輪四個MOPS補件的三artifact hash、原job／dispatch、zero prefix、439872／432041失敗保持，正式來源max439877、usage max729587、非DataProvider模型count297406都未變。新完整入口、實際scope／reclassification及必要科目原件證據改變下一步，分類progress，**全goal未完成**。見[當前完整查驗](evidence/source-acquisition/20261012/foxwell-chiata-new-free-entries-current-closeout.json)及[正式原20類同窗SLA](evidence/source-acquisition/20261012/foxwell-chiata-new-free-entries-current-formal-sla.json)。


### 恆大原生符號法說入口及彙總計數正式修正（2026-10-12）

2026-10-12T07:28:51.126990+08:00 恆大原生符號法說入口及彙總計數正式修正：1325.TW 原先僅有MOPS日期／資料連結，新增恒大官方目錄及直接發布PDF。完整主檔代號／法律全名／統編／registered官網、索引活動日／action與封面共同核對，三份保存原件可重播。637,681bytes、31原生文字頁；精確已核嵌入Wingdings2程式、CMap、Identity CID及獨立片段才將46個F0A1轉實心方塊，原PDF不改，其他未知字元仍partial。正文coverage仍partial、逐字稿false、影像／圖表顺序／claim未驗證。獨立P2原件標記移除與失去租約錯誤型别缺陷已修正，原finding／red保留；一次真正缺內容的既有報告補件200／7.3987秒／2native HTTP，股價／財報／原核心audit／HTML／MD／分析證據及五品質metadata保持、仍需重分析、模型計數297406不變。另從實際三笔帳本发现彙總多算，僅新UK typed aggregate排除；保存同窗4677行重播法說30／39→29／38，其餘19類完整相同，原ledger與第一次closeout保留並另立更正，不重抓成功來源。343相關＋獨立同343、原17及新7探針通過；最後2owned／97preserved＝99runtime已重載，canon28100、health／ready200、queue0、原四份MOPS補件及zero／439872／432041／jobs／dispatch保持。新增既有provider_acquisition至保護清單而不是宣稱新module。最新原20類17類嚴格>80：法說29／38＝76.3158%、財報54／87＝62.0690%、近期135／189＝71.4286%；財報自然滾動離窗不歸因本次法說。原8／3／30、五年九科目／typed sector、quota／cooldown／TTL／deadline保持，沒有commit/push，全goal未完成。見[最新正式查驗及判定更正](evidence/source-acquisition/20261012/uk1325-counting-current-closeout.json)、[同窗原件計數驗證](evidence/source-acquisition/20261012/uk1325-counting-same-window-before-after-proof.json)及[免費来源台帳](free-source-candidates-2026-10-09.md)。


### 新完整免費法說原件與當日場次選擇修正（2026-10-12）

2026-10-12T08:13:53.266684+08:00 新完整免費法說原件續查與當日未開始場次選擇修正：南亞科2408 MOPS年度完整索引及其實際發布英文簡報，匿名native200、保存原件與收據讀回；PDF656632bytes／14原生文字頁、empty／garbled無，封面Q2 2026及檔案日期2026-08-19與後續9/21、9/15、8/20場次分開，不推定首次發布日、完整影像或逐字稿。RGB色碼數字不當財務觀測；來源用途資格及正文投影仍待接入，未列正式成功。實際新年度索引在早上列當日15:00尚未開始場次，保存原件重播18→17，過往17列及原檔案日期逐欄保持。修正public解析器以單次Asia/Taipei aware時間導出日與時，list終日及same-day start一致；未知或無效當日時間不猜測、start已到不聲稱實際已完成。獨立午夜P2原finding與red保留、已修正覆核；root350及獨立同350／原7探針分開報告，不重複相加。1owned／98preserved＝99runtime正式重載，env／158套件、health／ready200、queue0、原四MOPS與UK補件artifact／job／dispatch／zero／439872與432041保持。冠西新英文完整body仍parser warning且初始local reader呼叫停點遺失原epoch／duration，保持unknown、不重新下載；舊中文exact292 xref offset本地重播仍34頁partial，page31地圖非空白，不放寬reader。3native研究請求、2份直接保存200收據及1次由保存body前提推得200；研究未列正式分子。正式source max439880／usage729590／模型297406未增，原20類17類嚴格>80：earnings_call 29/38=76.3158%、financial_statements 36/55=65.4545%、recent_catalysts 135/189=71.4286%，全goal未完成。free-only、原8/3/30及五年九科目／typed sector、quality／TTL／cooldown／quota保持，沒有commit/push。見[最新正式查驗](evidence/source-acquisition/20261012/post-uk-new-free-entries-and-mops-same-day-current-closeout.json)及[修正覆核](evidence/source-acquisition/20261012/mops-same-day-P2-fixed-independent-review.json)。

南亞科入口為 [MOPS年度法說索引](https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1) 的既有公開POST表單，及實際發布的 [完整英文PDF](https://mopsov.twse.com.tw/nas/STR/240820260819E001.pdf)。核對原TWSE完整代號／法律名稱／統編／官網、精確2408原索引列／檔名及PDF公司footer，不由英文簡稱推定主檔法定英文全名。[新原件資格](evidence/source-acquisition/20261012/nanya2408-new-regulated-complete-presentation-original-final-qualification.json)保持private source qualification，未推定商業重用許可、未啟用正文provider。冠西新完整英文原件及舊PDF xref因果重播均另保存，仍有無法辨識字元及真正影像地圖，不以空頁例外放行。ASE parent IR已得403、不换身份或proxy再試；健策原confidential限制保持。38個真正一般產業財報缺口仍要求完整五年九科目與同口徑，舊入口／已保存成功文件不重抓來刷率。


### 南亞科正文取得器部署、首次逾時及完整舊原件重用資格（2026-10-12）

2026-10-12T09:18:40.243091+08:00 南亞科MOPS準備簡報collector／角色投影／原件核對已正式部署，但首次真缺口補件502未成功，原報告仍欠正文。6owned／96preserved＝102runtime、env／158套件與health／ready200、queue0核對；conference_presentation_prompt是既有檔新加入保護、不是新增module。Root400及獨立同400／14原boundary／7lifecycle探針通過，重複套件不相加。原crossissuer改名red、獨立三P2／red保留並已關閉：完整200本地PDF問題留原document error cache、不停用全MOPS；暖讀觀測best effort、後續lease／deadline再查；當次失敗PDF也計workflow HTTP，舊cached error不重算。遠端403／429／503及不完整response timeout原guards保持，aggregate parent HTTPfalse；活動／filedate／季度／未知pubdate分開，兩精確RGB前綴只省略模型摘錄、原文保持、每角色200word，transcript／image／claim不升格。唯一source-only正式請求6.8964秒；MOPS索引success17列、PDF failure timeout／HTTP200／294912接收bytes，未取得完整原件，沒有用部分body或假完整補入。transport returncode／prefix hash／complete等欄位未全保留在現SLA allowlist，未知不推算。原report三artifact／quote／TTM／core audit／analysis evidence／五quality metadata全部相同，原429/504及439872／432041／新439882 failure不抹除、沒有第二次API重試，模型297406不增。全24h原行保存、相同窗口僅本次native success+1／attempt+2／HTTP+2、parent排除、其餘19類逐欄不變；不以研究／offline當新成功。用本次真正MOPS完整索引與已保存8時的完整PDF、本期主檔再次讀回：14native頁可組出嚴格context，保留pdf原epoch1791762567.4393559和quarterQ2 2026／file8/19／event9/21，但仍是未seed cache、未正式保存的recovery candidate，不能當這次原件取得或報告補件成功。最新原20類17嚴格>80：earnings_call 30/40=75.0000%、financial_statements 33/52=63.4615%、recent_catalysts 116/168=69.0476%；其餘比率變動是自然離窗，全goal未完成。free-only、8/3/30、五年九科目／typed sector、quality／總20秒／reader／quota／cooldown／TTL保持，沒有commit/push。見[真實首次逾時與當前驗證](evidence/source-acquisition/20261012/nanya-mops-first-timeout-current-closeout.json)、[原API回應及失敗紀錄](evidence/source-acquisition/20261012/nanya2408-mops-formal-source-refresh.json)、[既有完整原件重用資格](evidence/source-acquisition/20261012/nanya-mops-existing-complete-original-recovery-candidate.json)、[三P2覆核](evidence/source-acquisition/20261012/nanya-mops-three-P2-fixed-independent-review.json)。

### 南亞科完整原件重用及首次逾時後正式補件成功（2026-10-12）

2026-10-12T09:51:31.443916+08:00 南亞科2408原件重用已正式部署並完成一次真缺口source-only補件：HTTP200／2.0514秒，14頁已保存於原報告data snapshot；實際僅MOPS索引1HTTP，PDF原件重用HTTP0、模型297406不增。保留PDF原epoch1791762567.4393559、source TTL上限、Q2 2026／file8/19／event9/21與未知首次刊登；原502回應及439882逾時失敗保留；顯式採用原件時HTTP error cache／MOPS guard逐欄保持，後續依既有到期／快取更新流程運作，未手動重設保護。原HTML／Markdown、quote／TTM／core audit／analysis evidence／五品質metadata保持，analysis_text_stale=True仍需重分析，並非新完整報告品質成功。1owned／101preserved＝102runtime、env／158套件、health／ready200、queue0確認；root410及獨立同410／新10反例分開報告，不相加。原20類仍17類strict>80：earnings_call 31/41=75.6098%, financial_statements 32/51=62.7451%, recent_catalysts 116/168=69.0476%；同窗僅此輪native success+1／attempt+1／HTTP+1、cached original與parent排除，其餘19類逐欄相同，財報比率變動是自然離窗。free-only、8／3／30及五年九科目／typed sector與quality gates保持，全goal未完成、沒有commit/push。見[當前正式驗證](evidence/source-acquisition/20261012/nanya-original-reuse-current-closeout.json)、[原件採用與原TTL](evidence/source-acquisition/20261012/nanya-mops-original-adoption-proof.json)、[正式補件](evidence/source-acquisition/20261012/nanya2408-mops-original-reuse-formal-source-refresh.json)及[獨立覆核](evidence/source-acquisition/20261012/nanya-original-reuse-independent-review.json)。

本輪另以公開primary頁重查恒大2021／2022及士電2021／2022官方財報入口，交叉既有native receipts發現均已研究，不稱新入口、不再下載相同文件。恒大2021沒有明列必要無形資產現金購置；士電原3.43MB／2.42MB已完整保存但尚未財務qualified，不能用搜尋頁或舊「未attempt」formal標籤替代原件科目核對。原來源缺口維持，研究／offline／cache不灌正式success分子。參照[恒大既有完整研究](evidence/source-acquisition/20261010/universal-financial-research-proof.json)、[士電既有2021原件](evidence/source-acquisition/20261011/shihlin1503-2021-save-as-pdf-research-proof.json)及[士電既有2022原件](evidence/source-acquisition/20261011/shihlin1503-2022-save-as-pdf-research-proof.json)。


### 2026-10-12 法人 30 個交易日缺口與免費日報回補

20:04:23（台北時間）已將兩項修正載入正式服務：FinMind 起始日依實際交易日曆涵蓋所需 30 日，未知日曆仍沿原 45 日保守查詢；TWSE／TPEx 回補先核對最新日，再優先抓原視窗真正缺少的日期。最多 5 份日報、共享 12 秒、冷卻／單飛／快取原期限及 22:30 最新日確認規則均保持。完整 primary 30 日仍走原最近 5 日核對順序。SDK 原 29 日收據另保留於既有 private prompt-stripped `_source_record_archive`，不將 SDK 表格當原生 HTTP 或擴稱已驗證 30 份官方原件。

6152.TW 實際失敗工作原 29 日缺少 8/27，連假使固定 45 個日曆日只涵蓋 29 個交易日。新找到的[證交所該日完整免費原件](https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20260827&selectType=ALLBUT0999)有 1,333 列／195,259 bytes；精確 6152 外資 122,271 股、投信 0 股、自營商 -8,000 股。研究原件未灌快取或列正式成功。部署後直接從 operational.sqlite3 該失敗 job 讀取原資料，走正常回補函式一次：1.875726 秒、2 個真正 cold HTTP（最新日與 8/27）、其餘三日沿原快取時間、增加 3 筆分項觀測，**29→30／視窗 complete／缺日 0／衝突 0**；5 日計畫與 12 秒預算保持。完整 native bytes／日期／單位／身分／SHA 讀回，原工作逐欄相同，無新增 analysis 或模型請求。這是實際失敗來源回補資格驗證，未改原工作／報告或新增 canonical aggregate success；最新日仍 provisional／`official_observation_is_provisional`，不是全報告品質、官方全 30 日原件核對、歷史 PIT 或 finality 通過。

225 項相關測試及必跑 tracking 30 項通過；獨立同範圍 225、tracking＋runtime/storage 47、6 個反例各通過，重疊結果不相加。5 個既有測試失敗以 exact-before 與目前版各重播相同 assertion，原 log 保留並明列排除，不宣稱全 repo green。正式重載 2 owned／114 preserved＝116 runtime、環境／158 套件保持，health／ready 200；canonical session 29304（launcher 88818／worker 88846／API 88861），舊 session1745 exit143。一次支援 RQ warm shutdown，當時 idle，原 1 件排程 payload 與 future score 保留，零值帳本及原失敗紀錄保持，無 force kill、取消或手動重試排程，沒有 commit／push。

同一正式近 24 小時窗的**原 20 類只有 9 類嚴格 >80%**，全目標仍未完成；法人 85/216＝39.3519%、財報 38/67＝56.7164%、月營收 127/276＝46.0145%、近期事件 409/820＝49.8780%、搜尋 513/650＝78.9231%。自然工作新增觀測使比例變動，不能歸因於本次兩份原件；本 slice 原 baseline 到最新非 DataProvider 帳本 +200 是系統自然活動，本次 optimizer 模型請求 0，非 DataProvider 帳本不等於物理模型 HTTP 數。所有原 8 則／3 來源／30 日與五年九科目／typed sector、quote／TTM 及品質 gate 保持。

見[實際來源回補](evidence/source-acquisition/20261012/institutional-full30-6152-one-actual-gap-recovery-proof.json)、[獨立覆核](evidence/source-acquisition/20261012/institutional-full30-independent-review.json)、[正式重載](evidence/source-acquisition/20261012/institutional-full30-release-proof.json)及[全 20 類當前驗證](evidence/source-acquisition/20261012/institutional-full30-current-goal-turn-proof.json)。


### 2026-10-12 正常分析工作續跑的資料綁定修正

21:08:13 台北時間，正常分析工作新增 `analysis_job_checkpoint.py`：先讀同 job／mode 的實際凍結 checkpoint，再決定是否抓來源；新 job 仍正常取得資料，同 job 續跑沿原 source／quant／temporal／cutoff／hash／已完成 Agent，未開始模式以原來源建立自己的輸入憑據。回傳 context 的實際分析資料存回 job，既有 thin custom runner 缺 data 時保留已供給的 mode input。原 2891 工作曾有 6 次 freeze 收據：第一份匹配 checkpoint 的 29 日，最後一次新 30 日收據未被 graph 採用；兩者差异由實際原件／job／checkpoint 及事件唯讀核對，並非推測。舊報告與歷史仍保持，不將新數字混入已完成分析，也不宣稱已發布報告變成 30 日或品質警示消失。

獨立 P2 發現裸碼 2330→2330.TW 及 8069.TW→8069.TWO 的合法 provider resolver 結果遭 exact-request guard 誤擋；原 blocked review、反例与 RED 保留，固定版用 server-owned 原 request／pipeline、已存 job 的 resolved ticker、CP state／input 同一 ticker 與 resolver 的純候選關係綁定，沒有新報價請求或無條件 TW/TWO 等同。另以真 checkpoint 反例確認不能將 state/input 同時改為另一市場代號覆蓋原解析結果；未知／錯股／錯工作／錯模式／空持久輸入在外部請求前拒絕，legacy 無收據仍 unknown，不補造新 freeze。21 新測試，root 14 模組 267 passed／7 既有失敗明列排除，必跑 runtime／tracking 47 passed；獨立同 267／47、原 3 反例及新 11 邊界檢查通過，重疊次數不相加。沒有全 repo green 宣稱。

2 owned／116 preserved＝118 runtime、環境及 158 套件已由 canonical `start_mac.command` 重載，session62568／launcher3328／worker3356／API3358，舊 session29304 exit143，health／ready 200。一次支援 RQ warm shutdown，當時 idle／pending0；1093 原 job、原失敗／零值 ledger prefix／全部來源門檻保持。部署後用唯讀 SQLite IO adapter 將兩筆實際已完成／失敗工作的原 checkpoint 送入新 admission，輸入逐欄匹配且只 SELECT，job／checkpoint／provider／model ledger 未改；這是實際保存資料資格核對，加上隔離續跑控制流程，尚不是新的正式 queued retry。沒有新 analysis、模型或正式 provider 請求，無 commit／push。原 news8/3/30、年度五年九事實與 typed sector、quote／TTM／品質、quota／cooldown／TTL／deadline 均保持。

另原生取得[證交所單股財務頁](https://wwwc.twse.com.tw/IIH2/zh/company/financial.html?code=2891)及其兩份完整公開程式（6167／10405／233234 bytes），由實際程式找到新 `GET /rwd/zh/IIH/company/financial?code=2891`。wwwc 與官方 www 主機各一次正常 TLS、零 proxy/cookie/auth/redirect/retry、5 秒原生請求均 timeout，HTTP status／數值 body 未證明；五個研究 HTTP、三份完整 metadata 原件、兩次失敗全部保留，未接入、未 seed 標準 cache 或 SLA，研究正式成功 0。現行[申報特殊適用範圍辦法第三條](https://twse-regulation.twse.com.tw/TW/law/DAT0201.aspx?FLCODE=FL067432)允許保險及有保險子公司者在符合條件時延至每月 15 日，不能據此將所有金融業當成免申報／不適用或證明個別公司已用延期；本轮没有更改 applicability 或來源失敗分類。

最新原 20 類仍只有 9 類嚴格 >80%，全目標未完成；不能以省下未使用重抓、research metadata、快取或平均數宣稱達標。接續需找到真正完整數值入口，並觀察下一個實際排程續跑；舊 2891 的 29 日報告与來源／品質警示仍是歷史事實。詳見[根因原件](evidence/source-acquisition/20261012/checkpoint-input-2891-readonly-root-cause-proof.json)、[固定覆核](evidence/source-acquisition/20261012/checkpoint-input-independent-review-fixed.json)、[正式重載](evidence/source-acquisition/20261012/checkpoint-input-release-proof.json)、[實際資料唯讀資格](evidence/source-acquisition/20261012/checkpoint-input-actual-production-records-readonly-qualification.json)、[免費入口研究](evidence/source-acquisition/20261012/checkpoint-input-new-free-financial-entry-research-closeout.json)及[全 20 類驗證](evidence/source-acquisition/20261012/checkpoint-input-current-goal-turn-proof.json)。


### 2026-10-12 正常分析續跑交付的來源請求歸因更正

本 slice 起點到21:08凍結驗證，正式來源帳本新增2筆 FinMind 月營收觀測（5314.TWO），非 Data Provider 帳本觀測增量0。兩份既有 canonical log 各有同代號／dataset、時間相符的背景雷達抓取，支持背景雷達路徑的推論，但無 fetch_id 直接 join；重載亦會開啟頁面，尚未排除本次操作間接觸發，精確因果與物理 HTTP 次數保持未知。沒有直接送出分析工作或來源刷新／補件 API，不可將此限制擴成全部正式 provider 請求0。 原21:08 proof、原措辭與 blocked delivery review 保留，本段取代其未限界的「正式 provider 0／全部自然活動」宣稱。部署、測試、凍結9/20及原job／CP／報告保持的證據不變；不更改來源分子、分母或原失敗。見 [來源歸因更正](evidence/source-acquisition/20261012/checkpoint-input-delivery-source-attribution-correction.json)。


### 2026-10-12 新完整個股資訊 PDF：60 月營收候選入口

由 primary 官方公開網址取得新的[東陽1319個股資訊原件](https://www.twse.com.tw/pdf/ch/1319_ch.pdf)及[百一6152個股資訊原件](https://www.twse.com.tw/pdf/ch/6152_ch.pdf)，不是先前逾時的 IIH JSON 或僅兩個月份的官方 CSV。原生正常 TLS、無 proxy／auth／cookie／redirect／retry、單次5秒，各 HTTP200 完整368612／353083 bytes，產製日均2026-10-12。既有pypdf6.19 strict、10秒／512MB／100頁有界reader取得全部5頁native文字、空／garbled皆0；完整physical4按原有界renderer1600px視讀，五組月／營收欄順序已核對。兩原件各60唯一連續月份2021-10至2026-09，最新六個月2026-04至09全部有數值；完整原件／SHA／原取得時間與原生每列保存。百一原error job仍保留兩月，此候選有機會補缺4月至7月，尚未修改job／報告或走正式補件。

此表只有「月／營收」標籤，沒有直接標新台幣元或合併範圍。每issuer以已保存完整官方CSV的2026-08、2026-09與2025-09三期做逐碼／期間／金額×1000精確核對，六次皆相符；CSV原epoch保持，不將同publisher說成獨立來源。這支持新台幣元與相同月營收的解讀，仍不能宣稱全部60期單位／報表範圍／修订或商用重用許可都驗證。每日價格及法人欄只到10/8，不能把10/12產製日當10/12市場資料或拿來補所需最新法人日；不將月表當五年九科目、TTM、歷史PIT或新聞8/3/30。

東陽另一次取得新的英文IR完整HTML311036bytes，提供Q1/Q2/Q3及年度合併書冊的公開sdm download action，沒有月表、未下載那些財報或聲稱九科目補齊。長榮[每月營運統計公開索引](https://www.evaair.com/zh-tw/about-eva-air/investor-relations/financial-reports/monthly-statistic/)雖可由web讀到PDF連結，本機原生匿名HTTP首次403，原guard與失敗保持，不換browser身分、mirror或下載受拒原件。此階段4次native研究HTTP、3份完整HTTP200原件及1次403，標準cache／SLA／分析／模型／報告補件0。研究helper最初以檔名是否含pdf判型，錯將東陽stock-sheet PDF送HTML derivation；完整PDF bytes／SHA保持，原錯derived字段保留且隔離，後續用同原件正確strict reader，沒有HTTP重試或改parser。

這是一個新、具有完整歷史數值的免費候選入口，仍只驗證兩檔上市公司，未啟用provider或將研究列入成功率。見[兩份原件資格及語意限制](evidence/source-acquisition/20261012/twse-two-new-complete-monthly-stock-sheets-final-qualification.json)、[完整月表有界render收據](evidence/source-acquisition/20261012/twse-two-new-stock-sheets-monthly-pages-guarded-render.json)與[長榮原403](evidence/source-acquisition/20261012/eva2618-new-published-monthly-index-native-research.json)。


#### 百一官網每月合併營收入口的原生403（同輪續查）

另找到[百一官網財務資訊](https://www.pesi.com.tw/finance)，web抽取列2026年1月至9月並明寫「每月營收（合併）（單位：新台幣仟元）」，是補明確單位／範圍的公開候選。以原生匿名固定transport第一次直讀0.2596秒HTTP403，沒有取得可封存完整HTML，不改語系／身分／proxy／cookie／TLS、下載鏡像或原URL重試。Web抽取與TWSE PDF／CSV的相符不能稱此官網原生後端已可用，原scope unknown及未接入保持。本階段native研究累計5次：完整3原件（東陽IR＋兩份TWSE PDF）／403兩次（長榮、百一），研究正式成功0；原21:31四次研究快照保留，以新403收據補充，不回寫原失敗或先前數量。見[百一首次403](evidence/source-acquisition/20261012/pesi6152-new-complete-consolidated-monthly-native-research.json)與[後續限制收據](evidence/source-acquisition/20261012/pesi6152-new-published-monthly-entry-native403-held-closeout.json)。


## 2026-10-13 統一證券完整免費法說原件與正式補件

從正式2855的MOPS暫時失敗轉查[統一證券投資人頁](https://www.pscnet.com.tw/pscnetAbout/about.do)及[財報目錄](https://www.pscnet.com.tw/pscnetAbout/financialAffairs/list.do)，沿實際沒有session參數的公開法說href取得完整索引。33個材料連結只下載最新[2026/08/26原簡報](https://www.pscnet.com.tw/upload/pscnet/file/20260826164426662249.pdf)，1,507,318bytes，現有strict有界reader的12頁native文字complete／empty0／garbled0；目錄明列股票2855、PDF第二實體頁法人名吻合，封面日期與索引2026年8月一致。4次native research HTTP／4份完整原件，未進正式cache／SLA／模型或補件，候選尚未啟用。不下載其他wwwuat材料或影片、不替換原URL，不當逐字稿、完整影像、精確場次時間／首次發布日、三家新聞或五年九科目。[資格原件](evidence/source-acquisition/20261013/psc2855-new-complete-free-entries-final-qualification.json)與[獨立研究覆核](evidence/source-acquisition/20261013/psc2855-new-free-entries-independent-research-review.json)。

真正舊失敗股票百一6152只提交一件正常force=False新模式D分析，同一工作按原300秒排程實際恢復後done，freeze／resume各一次、Agent22／23未重跑。法人30交易日／最新10/12及6個月營收均在工作／checkpoint／報告回讀吻合，舊error與checkpoint不重置。[真排程證據](evidence/source-acquisition/20261013/6152-new-analysis-real-resume-report-readback.json)。報告仍有credibility／conformance warning與unknown歷史analysis_evidence，未稱全部品質通過。

正式FinMind新聞誤含CMoney /forum/article/185387548。adapter、selector及保存資料freshness現在共用精確角色排除，仍保持3日期／10秒、所有guard與news8/3/30。獨立覆核先抓到consumer重納forum的P2，blocked證據保存，修後241相關／21必跑通過。一次實際免費source=recent_catalysts補件HTTP200／2.061秒，两筆search_upstream觀測與一筆canonical新聞成功450250；8則入選、eligible14→13、reported publisher8→7，論壇原欄位與receipt留unverified。發布者標籤／domain不當已驗獨立性。此端點只實測free Alternative Search及保存consumer，adapter續日期仍只有離線證明。[正式補件](evidence/source-acquisition/20261013/6152-role-source-only-refresh-live-readback.json)。

實測另發現fresh core／來源status未變時，新聞變更仍錯標舊結論current。新增selected／additional新聞的內容、URL、出版日、publisher比較，忽略收據epoch／ID、排序与純封存，不增加無效模型重跑。6真RED／2控制保存，108相關／21必跑及獨立6探針通過。正式重載後用原before／actual after精確bytes，只補四個保守stale/needs_rerun旗標與canonical index；正文、data、quote／TTM、六品質欄位及CP／job保持，無第二新聞補件或新模型。API讀回analysis_text_stale=True／needs_rerun，unknown分析packet不回填。[唯metadata證據](evidence/source-acquisition/20261013/6152-news-change-staleness-metadata-repair.json)。

兩次正式重載均用支援RQ warm shutdown及正常TERM，原零列隨既有90日retention退出並以原prefix重構核對，不刪改分母／冷卻。第二重載helper的暫存前SLA檔名碰撞，覆寫第一個暫存，已另存第二快照並[記錄限制](evidence/source-acquisition/20261013/release-preflight-SLA-artifact-name-collision-disclosure.json)；不重造第一次暫存原件，07:20基準與原覆核原件保持，碰撞未修改正式台帳。尚未commit／push。

2026-10-13T08:12:41.407670+08:00 原20類仍9/20各嚴格>80%，全目標未達。119 runtime、原env／158套件保持；canonical start_mac.command／role-all／uvicorn8080，health／ready200、六queue／scheduled0。[最新完整驗證](evidence/source-acquisition/20261013/new-free-entry-role-and-staleness-final-current-proof.json)。


## 2026-10-13 統一證券完整法說簡報正式接入

2855.TW的新免費官網入口已由研究候選接入正式 `earnings_call` provider：官網首頁原法說公告連結、完整簡報清單、原公告與最新正常主機PDF，並用既有證交所完整公司主檔核對統一綜合證券股份有限公司／23218183／官網。此次新原公告研究HTTP1次，研究fixture未種入正式cache／SLA。原公告確認2026-08-26 14:00（台北）及2026Q2內容，PDF封面與12頁原生文字相符；不證明活動實際舉行、首次發布、完整圖像、影音或逐字稿。主檔保存原取得epoch／SHA／HTTP未觀測的類型，不以重播更新時間。舊UAT下載連結保持原件，不更換主機。

正式單件 `2855_TW_v4_report_job_a4b5f630daed.html` 原本已有成功MOPS場次metadata，缺口是簡報本文。一次earnings_call source-only POST在3.0695秒HTTP200，原件HTTP4次各200／成功native observations450251–450254，父450255為aggregate不算第五次取得。完整12頁本文已存入snapshot並重讀核對5份原件；156項非該來源data、其他audit、HTML／Markdown、六品質欄位、舊analysis_evidence、job與CP保持。新增本文標needs_rerun，credibility／conformance warning尚在，沒有新模型或新全報告。[正式來源證據](evidence/source-acquisition/20261013/psc2855-source-only-live-readback.json)。

4項有反例的P2已修：真PDF timeout不啟用後續MOPS fallback；同一provider deadline在reader／equality／handoff重查；consumer逾時映射502且保留快照；PSC失敗父件不重算取得失敗。394相關／21必跑及[獨立最終覆核](evidence/source-acquisition/20261013/psc-conference-final-independent-review.json)通過。8項owned／113項保持，正式121 runtime／原env與158套件核對；無commit／push。

2026-10-13T09:09:54.220493+08:00，原20類仍9/20各嚴格>80%，法說46/76＝60.5263%，整體目標未達。24小時窗口會自然移出舊觀測，不改原失敗、分母或快取；僅真正新取得計數。[當前完整查驗](evidence/source-acquisition/20261013/psc-conference-final-current-proof.json)。


## 2026-10-13 共通熔斷紀錄與同次月營收備援

09:13原20類仍9/20嚴格>80；11未達類別所有24h未成功取得觀測共1,298筆已逐筆盤點，不以最近250列代表全集。115筆FinMind月營收CircuitOpen的provider_attempts／count均為空／0，沒有呼叫callback，卻保留legacy failed投影。修正僅向後：`source_audit`對typed circuit／throttle與真空attempttrace及尚未啟動的callback標local_block／HTTPFalse／count0／units0，status仍unavailable，原error、quote／TTM／品質不放寬。已進callback的同型錯誤及預建coro／Task／Future都保持傳輸未知。歷史115原列與投影逐欄保持，不回寫降低舊分母。

`MonthlyRevenueProvider`同次core的typed localblock只重用一次；精確current fetch／ticker／provider／op、uncached／notstale、明確marker／HTTPFalse／strict int0／空trace仍必須成立。不重查同一primary admission，直接用已接入的官方CSV，原兩相鄰月份partial／原件epoch／TTL不變。7個scope／boolcount／trace反例保持，隔離持久台帳證明新blocked unavailable／record0／units0與oldrow不變。145相關與21必跑，獨立95＋4案例通過（有重疊不相加）；2owned／120held＝122 runtime、原env／158套件、canonical程序及health／ready200核對。尚無新正式guard事件，不宣稱已由正式資料取得成功驗證；沒有強制插入測試guard。

新查[證交所上市](https://isin.twse.com.tw/isin/C_public.jsp?strMode=2)與[上櫃](https://isin.twse.com.tw/isin/C_public.jsp?strMode=4)完整名冊，普通匿名各HTTP200但5秒內未完整下載，研究2HTTP原failure保存、不重試、不採作完整原件或cache／SLAseed。[研究證據](evidence/source-acquisition/20261013/isin-complete-free-master-native-research.json)。同業76個primary失敗不可一概歸因空master cache：實查最新5報告有4件已有metrics，1325仍有真缺口；本輪未放寬同業門檻。

09:43:16.987988台北原20仍9/20>80，全目標未達；六queues／scheduled0、既有jobs與PSC12頁三artifact保持，沒有新source refresh／分析／模型。30舊零列依90日retention自然到期，原prefix重構驗證保持。[當前證據](evidence/source-acquisition/20261013/source-admission-final-current-proof.json)、[最終覆核](evidence/source-acquisition/20261013/source-admission-independent-review.json)。下一個共通修正線索：31筆真正FinMind SDK上限異常各3callback（合93，不能當physical HTTP）；尚未修正，[原件依據](evidence/source-acquisition/20261013/finmind-sdk-quota-retry-next-action-evidence.json)。無commit／push。


## 2026-10-13 額度重試修正與兩組新免費入口研究

10:34:51台北正式近24h的原20類仍只有9類各嚴格>80%，整體目標未達。[當前正式驗證](evidence/source-acquisition/20261013/finmind-sdk-quota-final-current-proof.json)核對125個runtime檔、原環境與158套件、canonical start_mac.command／role-all／uvicorn8080、health／ready200及六queues／scheduled0。僅3個owned runtime修正，其餘122檔保持；provider_resilience以本輪前的既有dirty原件為基準，未抹掉舊修改。支援RQ warm shutdown僅一次，再正常TERM自有程序；舊session99708 exit143、新81440保持。30舊零列依原90日retention自然到期，原prefix重構核對；所有jobs、PSC12頁三artifact與舊失敗保持，無forcekill、取消／手動重排、commit／push。

原31筆FinMind月營收SDK額度錯誤各3次callback（共93，非已觀測physicalHTTP）。安裝FinMind1.9.10的真_extract_data會丟出plain Exception並丟掉HTTPresponse；現在只辨識真decoder框架及原始、明確的官方quota payload，不從保存字串或body402偽造原生HTTP。此訊號與既有設定指定的HTTP402／403／429，立即retry由3→1並沿用原provider namespace／duration冷卻；未知文字、wrapped／矛盾payload、native500及配置排除的403維持原retry。SDK檔／套件不改，本地冷卻不當帳戶全域額度或供應商reset時間。原兩月官方CSVpartial／TTL／TTM／quality保持，歷史31錯誤及115localguard原列／legacyfailed投影逐欄相同，不回寫降低舊分母。兩組真RED各6failure及6／2控制保留，root260相關／21必跑與獨立106／4探針通過（重疊不相加），[code覆核](evidence/source-acquisition/20261013/finmind-sdk-quota-independent-review.json)沒有未解重要問題。尚無新的正式quota或guard事件；載入修正與隔離SDK測試不是實際額度恢復／來源成功率提升的證明，未強迫耗盡額度或塞假事件。

另外用7次普通匿名TLS請求，完整取得7份HTTP200原件，未進provider cache／SLA／報告或模型。[中央社官方RSS條款](https://www.cna.com.tw/about/rss.aspx)提供[產經RSS](https://feeds.feedburner.com/rsscna/finance)20項、[股市清單](https://www.cna.com.tw/list/ass.aspx)20項；從實際原文發布的[台塑標籤頁](https://www.cna.com.tw/tag/4665/)取得150項原列表，僅7项在30日內，3項短名title候選且相關文章未全核對。它們都只有一個CNA publisher，RSS僅headline／lead／links並有個人／非營利非商業及標示來源條款；CNA business投稿不可當獨立新聞，發布與更新日分開，不能湊原8／3／30。

新[冠西電2466官網月營收](https://www.cosmo-inc.com/tw/investor/financial.aspx)按原2026年／「全部」查詢表單，GET與POST各1次200，完整12列中1–9月9筆數字，4–9月連續6個月金額都有；10–12月「-」保留未公布，不轉零。原仟元單位與既有完整TWSE master法名／34348590一致，重用原SHA／epoch／HTTP未知，不刷新取得時間。9月116,057仟元與8月224,958仟元算出的MoM約-48.4095%，卻標增減308.16%；比率保持未知，未補造成MoM／YoY。頁面未明示合併／個體，仍須原申報核對，因此只是新完整原件候選，未正式採用、不得當TTM或五年九科目。[完整資格](evidence/source-acquisition/20261013/cna-and-cosmo-new-free-entry-qualification.json)及[434項檔案獨立核對](evidence/source-acquisition/20261013/cna-and-cosmo-new-free-entry-independent-research-review.json)保留此限制。國泰「每月營收」頁實為自結盈餘，未替代營收；舊MYSON／冠西簡報不稱新入口，PESI先前403頁不重試／繞過。

下一步先核對冠西連續六月的合併口徑及原申報金額，再接有界取得器；CNA候選保留日期、publisher、公司身分及使用範圍。全20類成功率仍依實際正常取得驗收，不以研究／replay／cache／重抓健康來源計新成功。


## 2026-10-13 官方月營收歷史備援正式啟用

將10/12已研究的TWSE個股PDF歷史入口接為上市四碼股票的免費備援；本輪2466／1301兩份完整HTTP200原件均有5頁native文字、60月資料（2021-10至2026-09）。正常FinMind成功仍沿原路；只有primary未取到資料、官方CSV兩月可用且完整現行主檔／公司名稱相符，才在既有合計8秒budget內取固定`https://www.twse.com.tw/pdf/ch/<code>_ch.pdf`。擷取月表，不把同頁本益比数字誤當月營收；要求最近六月連續、日期不未來、原CSV兩個金額×1000精確相符。異股、名稱矛盾、少月、金額衝突、原件過期或deadline耗盡保留既有兩月partial與實際失敗。新原件cache1800秒、error120秒；warm不新算取得、不續原epoch，merge使用CSV／PDF原取得時間較早者。

獨立覆核先重現兩個P2：原CSV名稱與master矛盾仍升格六月、最後archive read跨TTL仍回warm success；blocked原件保留，窄修加入native名稱→master exact short/legal綁定及所有原件I/O後／handoff原TTL重驗，master24h也重驗。新增4個公開邊界案例，root修正RED2 failed、fixed179相關／21必跑與獨立66（含原3反例）passed；重疊次數不相加。只3個owned／123 preserved共126runtime，以canonical start_mac.command正常重載，session65900／launcher73561／worker73589／API73591；health／ready200，環境与158套件、舊31 quota／115 guard失敗投影、全部jobs保持。84筆舊零列依既有90日retention自然到期，原prefix重構核對；沒有重寫分母、取消／手排或強制kill。

正式collector直接驗證兩個既有報告的真正缺口：原2466與1301雖有六月份，最新僅到8月且原取得已過24h。2466正常CSV+PDF兩次HTTP200、2.5855秒，1301重用原CSV再取自己的PDF一次HTTP200、0.5267秒，皆實際取得2026-04至09六個金額、原receipt／SHA／法名核對。2466再讀warm HTTP0，原epoch不變；共6筆真觀測為3 fetched與3 fresh-cache，cache排除取得率。研究原件不seed標準cache，沒有強迫primary／quota失敗、SDKfirst完整分析、來源刷新API或新模型；兩份報告／index／quality与PSC三artifact全部保持。這是正式有界collector取得驗證，尚不是舊報告品質已修復或正常queued分析fallback已走過的證明。

12:23:32台北時間原20類近24h仍9類各嚴格>80%，月營收129／278＝46.4029%；全目標未達，不能用研究、warm、同publisher獨立性或平均數代替验收。10/13官方CSV自然更新首次列入冠西本期，不把此原更新歸因於程式修正。PDF只採月營收金額，未升格完整影像、合併財報口徑、五年九科目、TTM或PIT／finality。免費新聞與其他來源缺口仍需真正可用原件，所有原news8/3/30、年度／sector、quote／TTM／quality、cooldown／TTL／deadline保持；無commit／push。詳見[原生入口](evidence/source-acquisition/20261013/twse-monthly-history-new-complete-native-research.json)、[固定覆核](evidence/source-acquisition/20261013/twse-monthly-history-fixed-independent-review.json)、[正式重載](evidence/source-acquisition/20261013/twse-monthly-history-release-proof.json)、[2466冷暖實測](evidence/source-acquisition/20261013/twse-monthly-history-production-collector-live-proof.json)、[1301實測](evidence/source-acquisition/20261013/twse-monthly-history-1301-production-collector-live-proof.json)及[全20當前驗證](evidence/source-acquisition/20261013/twse-monthly-history-final-current-proof.json)。


## 2026-10-13 雙鴻新版公開 API 與散熱產業鏈入口研究

本輪沿用原二十類逐類嚴格高於80%的免費來源目標，新增可重播入口研究；未修改runtime程式、部署、重啟、commit/push、送模型或重新產生報告。27次普通匿名原生HTTP研究，完整回應與既有TWSE主檔共27個不同原件讀回驗hash；不將研究資料寫入provider快取或正式SLA。最後正式帳本仍450261／743397、原二十類9／20達標。[完整判定與更正](evidence/source-acquisition/20261013/auras-thermal-free-entry-qualified-closeout.json)。

- **雙鴻官網舊路徑已變成SPA空殼。** `https://www.auras.com.tw/node/9`實回1031bytes HTML，只有app與script；不能因HTTP200算正文。沿原頁公開script、同站`static/urlConfig.json`與其實際GET函式，找到同站`https://www.auras.com.tw/CmsApi/api`。沒有猜測管理介面、登入、變更身分、繞驗證或呼叫任何寫入／寄信功能。原件包含前端版本與公開查詢預設參數，避免只留下無法追溯的猜測URL。
- **營收／財報清單：** [FinancialReport公開GET](https://www.auras.com.tw/CmsApi/api/FinancialReport/getFinancialReportAsync?Year=&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true)原生200／33785bytes／1.454秒，`totalCount=12`與2015–2026十二年度列相符。2026年1–9月有數值，10–12月為null，不能補零。原生前端財務模組明載「合併營收金額 (NT$仟元)」；8月3141249、9月2884061仟元與本日官方上櫃CSV逐值相等。已具六連續月備援的來源線索，仍只獨立核對最新兩月，不能聲稱九個月份或十二年資料均已全數驗證、PIT已成立。[API原件](evidence/source-acquisition/20261013/auras-current-public-content-native-research.json)、[官方CSV對照](evidence/source-acquisition/20261013/auras-new-original-payload-research.json)。
- **PDF附件可直接下載：** 沿API明列附件取得2025年中文合併財報2801166bytes／74頁，以及2021年英文合併財報835995bytes／79頁，封面／前兩頁核對公司、年度及合併範圍；英文版明示中文原文優先。只證明整份下載與身分，不宣稱所有頁面文字、五年九必要科目或報告品質已通過；2021／2022索引沒有中文合併附件，不可改拿個體附件頂替。
- **公司正文：** 公開導覽列明列`unitId=9`為集團概述，照公開前端`Unit/getUnitContentAsync`與`IsFront=true`取得23306bytes JSON，正文含3324及雙鴻完整名稱與散熱業務。這是舊HTML空殼的有效替代正文入口。新聞API則列9筆，其中一筆標題為疑似測試內容；本輪記錄異常，不整批自動接入或計作已驗證新聞，仍未通過原8筆／3發布者／30天品質門檻。
- **同業搜尋候選：** [3324公司链](https://ic.tpex.org.tw/company_chain.php?stk_code=3324)9480bytes與[電腦及週邊設備鏈](https://ic.tpex.org.tw/introduce.php?ic=F000)331394bytes均原生200。`companyList_FB00`散熱片／風扇馬達／散熱模組桌面及行動名單27碼一致，與完整交易所主檔核對3324、3017奇鋐、3338泰碩、6230尼得科超眾、2421建準、3483力致市場／名稱／代碼。這是已知平台上的新細環節覆蓋，不是新平台；未標成員生效日，也不證明整體業務或財期可比。完整F000大於現有250KB讀取器，需要固定入口專用上限及跨上市／上櫃身分，不能截斷或全域放寬。[原件](evidence/source-acquisition/20261013/thermal-segment-new-native-research.json)、[主檔](evidence/source-acquisition/20261013/thermal-segment-current-identity-research.json)。
- **正文失敗仍保留：** 力致官網實抓111760bytes正文，代號／散熱描述相符；奇鋐實回212bytes Incapsula驗證頁，停止且不繞過；泰碩雖HTTP200但5秒內未完整下載，仍失敗。初始研究欄位`complete_native_original`僅描述完整transport bytes，對雙鴻空殼及奇鋐驗證頁不等於业务正文成功；[逐項更正](evidence/source-acquisition/20261013/thermal-free-entrances-evaluation.json)和最終判定已明示。2059／1325公司鏈也成功取得，但分類仍偏廣，不新增整體估值同業宣稱。

接入優先順序：先做exact-issuer雙鴻月營收API備援，保留公開前端單位、合併口徑、原件及官方最新月份交叉核對；散熱名單另作限定環節候選，逐項核對業務和指標。已保存3324同業指標為0，3017的Yahoo產業與3324不同，不能靜默跳過現有可比性gate來填滿數值。以上尚未部署，不代表正式來源取得率或報告品質已改善。


## 2026-10-13 雙鴻備援已部署，新增世紀公開月營收歷史

雙鴻月營收API備援已完成實作、227項相關隔離測試及獨立102項回歸／3項新增反例（重疊不相加）。空暫存、原生連網的受控collector首次4次HTTP在3.97670秒取回2026年4–9月六筆；暖讀0次HTTP／0.03871秒，保留原epoch。沒有強迫FinMind失敗、刷新已完整的3324報告或把測試記入正式SLA。固定3個owned路徑已經canonical start_mac.command正常重載，124個其他runtime、原環境與158套件保持，health／ready200；20筆舊零資料列只依既有90日retention到期，原prefix重構核對。來源仍須精確3324.TWO、完整當前主檔、版本化單位合約、官方CSV最新兩月相等、六連續月、原件TTL及原合計8秒deadline。這證明備援已可用，尚無正常正式primary失敗後的自然採用證據。[独立覆核](evidence/source-acquisition/20261013/auras-monthly-independent-review.json)、[受控連網](evidence/source-acquisition/20261013/auras-monthly-isolated-live-validation.json)、[部署核對](evidence/source-acquisition/20261013/auras-monthly-release-proof.json)。

新查得[世紀民生5314官網財務頁](https://www.myson.com.tw/financial)直接發布的五份免費公開Google試算表，普通匿名讀取不需帳號、金鑰、付費或轉址。8次原生HTTP完整取得官網、2022–2026五份表及兩份官方核對原件；每份表約0.61–0.67秒，可讀2022年1月到2026年9月57個連續月份。全57筆累計與同表月值加總相等，45筆與下一年度「去年同期」逐值相等（同一發行人，並非45個獨立來源）。單位明示新台幣仟元及合併申報說明；2023年3／4／7月明示0，2026年10–12月空白維持未知。現行TPEx主檔核5314／世紀民生科技股份有限公司／統編22099815／www.myson.com.tw；8月465313、9月472835仟元及今年累計4359156與官方CSV一致。

這是新的完整月營收入口，尚未接入正式provider。近24h該股票有6筆舊零資料列，屬3次fetch，不能冒稱6次獨立HTTP失敗；最新保存報告已有3–8月六筆，並非整份無資料。新入口具備將下一次正常取得更新至4–9月的資料，但尚未改報告、TTM或年度財報，不宣稱57月PIT或五年九科目財報完整。正式原20類仍9類各嚴格>80%，全目標未達；研究與受控測試沒有新增正式成功筆數。[世紀完整原件及逐項核對](evidence/source-acquisition/20261013/myson-monthly-free-entry-qualified.json)、[當前正式20類](evidence/source-acquisition/20261013/myson-search-after-release-formal-sla.json)。下一步可接精確發行人公開表備援，保留來源頁實際連結、完整回應及相同deadline，不全域放寬transport上限。


## 2026-10-13 世紀月營收備援正式啟用

先前已驗證的世紀公開試算表現已接入`MonthlyRevenueProvider`：精確5314.TWO且FinMind無資料時，官方CSV兩月及現行TPEx主檔核公司法名／22099815／登記官網，再沿財務頁「每月營業額報告」實際發布的Google Sheets連結取得最近六個月；跨年最多取兩年度表。維持原合計8秒（含CSV）、單次5秒／connect2秒、無轉址／重試／登入／proxy，以及原件1800秒TTL；只有新固定Google表路徑採500KB上限，未全域放寬。零值保持數值、空白未知；schema／身分／單位／合併口徑／缺月／未來月／重複表格任一不符，退回原兩月partial並保留失敗，健康FinMind及其他ticker路徑不變。

獨立P2指出，僅核最新两月与同表累計仍可接受與官方CSV同年累計矛盾的早期月份；原反例讓4月493736→593736仟元且同步調整同表累計，原版錯誤通過。已限定新Myson路徑從完整原CSV取得本年累計，與當年1月至最新月總和精確核對；錯誤歷史現在拒絕，明示0與跨年正例保持。Root固定版176相關＋95整合（含獨立原3探針）271pass，定向獨立88pass（重疊不相加）；初版blocked／RED與[修正後覆核](evidence/source-acquisition/20261013/myson-monthly-fixed-independent-review.json)均保留。

空暫存原生連網4次HTTP，在4.06965秒取得2026年4–9月六筆，當年累計4359156仟元與官方原件相符；warm0HTTP／0.09347秒、原epoch不改。[受控實測](evidence/source-acquisition/20261013/myson-monthly-isolated-live-validation.json)在fixedreview尚進行時執行，後續acceptedreview已核同一frozen input；不是正式自然primary失敗採用證明。四份原件另存evidence，未seed正式providercache或SLA。3owned／125held＝128runtime已由canonical啟動器正常重載，158套件與環境保持，health／ready200、pending／scheduled0，這次沒有舊列到期或重寫。[正式部署](evidence/source-acquisition/20261013/myson-monthly-release-proof.json)。

最新失敗5314工作9ea39e106d255300a8325dc5798a3db8本已有4–9月完整營收，失敗在報告契約／證據gate；此次備援不能宣稱修復該報告，工作snapshot與已保存報告保持。[因果核對](evidence/source-acquisition/20261013/myson-monthly-goal-causality-check.json)。最後原20類仍9類各嚴格>80%，月營收129/278＝46.40%，新正式成功0、模型0，未commit／push。全目標未達；後續需處理其餘來源真缺口，不能用研究、cache或健康來源重抓沖高比例。[全20當前核對](evidence/source-acquisition/20261013/myson-monthly-final-current-proof.json)。


## 2026-10-13 建準、尼得科超眾與力致新免費原件

本輪續找免費資料入口，以普通匿名 HTTPS 完整取得 16/16 份 HTTP 200 原件（9 HTML、7 PDF），保存原 bytes/hash、實際連結與取得時間，未寫入 provider cache／正式 SLA，也未修改 runtime、部署或產生新報告。128 個既有 runtime 檔案雜湊保持，health／ready200，正式台帳仍 450261／743397。原二十類近24h仍9類各嚴格高於80%，整體目標未達。[完整來源資格與原件索引](evidence/source-acquisition/20261013/thermal-additional-entrances/qualification.json)。

| 免費入口 | 實際驗證與用途 | 保留限制 |
|---|---|---|
| [建準月營收](https://www.sunon.com/inv2_1.aspx) | 完整1頁原表，2024-01至2026-09共33月合併營收；逐月累計加總全部相符，2026上半年合計也與另一份合併財報相同。可作2421月營收備援候選。 | 接入前仍須當期交易所CSV交叉核對；空白未來月份不是0。 |
| [建準合併財報](https://www.sunon.com/en/inv2_2.aspx) | 實抓2026Q2完整74頁；損益表分別列第二季與上半年，日期、合併範圍、新台幣仟元已核對。可供同期間財務指標。 | 尚未整合自動解析，不把上半年毛利率當TTM或年度值。 |
| [力致中文財務資訊](https://www.forcecon.com/zh-hant/investor/financial-information/)及[英文年度入口](https://www.forcecon.com/investor/financial-information/) | 實抓2026Q2 49頁，以及2025／2024 65頁、2023／2022 62頁、2022／2021 60頁合併原件；比較年度覆蓋2021至2025。三份年度現金流量表均明列無形資產取得支出，可保留原欄位而不用淨額或差額代替。 | 尚未做五年全欄位契約與重編差異整合，非歷史PIT。官網頁尾3483.TW不作市場真相；官方當期主檔為3483.TWO。 |
| [尼得科超眾財務摘要](https://ccic.com.tw/autopage/2/156)及[業務正文](https://ccic.com.tw/about/1) | 原生取得完整2頁摘要與正文；摘要明列2026-08-28，提供年度績效與產品組合，可補熱管理業務與比較期間的查核線索。 | 摘要不是完整財報；2026Q2欄與截至六月累計數並列，不自動當單季。年度財報連結仍指向TWSE，不能算獨立上游備援。 |

另排除[力致英文月營收頁](https://www.forcecon.com/investor/monthly-revenue/)作為近期備援：HTTP200、正文完整，但表格僅到2024年；僅可作歷史原件。新研究没有將相同issuer視為多個獨立publisher。

使用 ReportArtifactLocator 重新讀回正式報告：3324.TWO有5筆Yahoo大分類同業搜尋候選但dynamic_peer_metrics仍0；3017.TW也是5筆搜尋候選、僅1筆指標。這是候選內容與可用指標的缺口，不能靠繼續增加搜尋數量解決。下一步先將官方散熱細環節、已核對業務正文、同期間財報做可比性驗證，再接入適當來源；不放寬整體業務／估值／品質門檻。[當前報告缺口](evidence/source-acquisition/20261013/thermal-additional-entrances/current-report-gaps.json)。


## 2026-10-13 雙鴻官方散熱候選指標：已部署並補回實際缺口

14:39 的正式 source-only 補件取得 HTTP200，12.2466 秒把 `3324_TWO_v4_report_20260929_093913.html` 的 `dynamic_peer_metrics` 從 0 家補成 5 家：奇鋐3017、泰碩3338、尼得科超眾6230、建準2421、力致3483.TWO。四家八項指標齊全；6230仍缺 `pe_ttm`，因此正式450262如實保留 `degraded_enrichment`／partial／5筆，沒有增加 fetched 成功數。不是把候選名單筆數或研究下載當成功率；本次 SLA 分母+1、degraded+1，取得成功數+0。

[櫃買雙鴻產業鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=3324)及[電腦周邊產業鏈完整頁](https://ic.tpex.org.tw/introduce.php?ic=F000)的「散熱片、風扇馬達、散熱模組」組別，連同完整上市／上櫃主檔核精確市場、法名、簡稱、統編及日期。原頁兩個desktop/mobile名單對採用成員須一致。共用上市主檔原epoch1791790405.013688、expiry1791876805.013688及HTTP未知保留，沒有研究seed或續期；本次官方cohort真HTTP3（上櫃主檔、公司鏈、產業頁），yfinance／SDK實際HTTP未由callback或觀測筆數猜測。五家仍是未核實整家公司業務及期間可比性的產業候選，`business_comparability_verified_current=False`，既有prompt／自動估值排除契約保持。資產周轉率只接受同一天年度營收與年末資產，不能取無日期的quote總數互除。

實作限五個runtime路徑：`data_fetch/market_sources/official_thermal_peer_cohort.py`、`data_fetch/market_sources/peers.py`、`thermal_peer_source_refresh.py`、`report_source_refresh.py`及`data_fetch/service.py`。既有 `/api/report/{filename}/refresh/data?source=dynamic_peer_metrics` 僅允許已核實的3324股票context，不觸發其他來源或模型。12秒官方原件總deadline、每HTTP5秒/connect2、無redirect／retry、原TTL／冷卻保持；raw master1800秒、原有shared master最多24小時並守實際更短expiry。獨立審查重現兩個P2：shared master被錯寫HTTP200，及丟失較短fresh_until；原blocked及root RED2fail1pass均保留。窄修只新subclass核原cache digest／stamp／expiry，HTTPNone和cached kind傳到保存原件，archive及metrics handoff後重驗。固定版root207相關、115必要及獨立50定向全通過（重疊不相加）；126其他runtime、原環境與158套件保持，正常start_mac.command重載，health／ready200，六queue無pending，無強制kill、commit／push。

報告152個非同業原資料欄位、所有非同業audit、HTML／Markdown、analysis evidence與品質判定保持，index標示 `analysis_text_stale=True`／`needs_rerun`。原lint／final_audit passed，content_credibility及report_conformance warning仍在。這是資料缺口補件，沒有新完整報告或品質過關主張。

冷入口穩定性尚未解決：兩次空隔離cache實測分別在TPEx傳輸錯誤、TWSE JSON逾時止步；完整native直接診斷與同bounded helper另各取得TPEx HTTP200／1,074,417bytes，不能據此抹掉前兩次失敗。新查[官方上市CSV資料集18419](https://data.gov.tw/dataset/18419)及[上櫃CSV資料集25036](https://data.gov.tw/dataset/25036)，兩個原下載各5秒逾時，只得到484,042／333,706bytes部分body，均拒收，不用來取代完整主檔，不放寬deadline。本次正式成功依賴仍有效的上市原快取，不證明冷JSON／CSV已恢復可靠。

正式當前20類仍只有9類各嚴格超過80%；dynamic_peer_metrics111/194，完整目標未達。下一步針對6230本益比的官方適用性與冷主檔穩定入口補證；不因缺值把未知改為零、不改成功定義，也不重抓已齊全同業來增加分子。

證據：[正式補件](evidence/source-acquisition/20261013/thermal3324-source-only-live-readback.json)、[當前正式狀態](evidence/source-acquisition/20261013/thermal-metrics-final-current-proof.json)、[固定版獨立覆核](evidence/source-acquisition/20261013/thermal-metrics-fixed-independent-review.json)、[首次冷測](evidence/source-acquisition/20261013/thermal-metrics-isolated-live-validation.json)、[第二次冷測](evidence/source-acquisition/20261013/thermal-metrics-isolated-live-validation-second.json)、[CSV完整性拒收](evidence/source-acquisition/20261013/thermal-csv-master-native-research.json)。


## 2026-10-13 統一公開職缺 API 新入口與一般分析稽核修正

從[統一企業官網](https://www.uni-president.com.tw/)的公開人力資源連結，確認[統一企業職缺入口](https://hr.pec.com.tw/en-US/job)。完整原生 HTML／原模組宣告公開 API base 與 `GET /api/jobs`，沒有猜登入 API、使用 cookie、權杖、履歷或投遞功能。按原畫面十筆分頁及原 targetDate 查兩頁，HTTP200分別12,854／6,957 bytes、0.319／0.279秒；10+6共16個唯一 jobId，兩頁totalCount都16，第一頁完整物件與HTML內原生JSON十筆逐欄一致。這是多次請求的當前觀察，不是原子或歷史快照。

16筆均有工作正文、有效開始／截止日、active Y／closed N／deleted N。集團MA的5901為GRP／isSubJob true，排除；15筆PEC／isSubJob false保留候選。日期是既有開放區間及來源修改日，不能算近期新增刊登。正式接入前仍需以完整當期交易所名冊與此站公司代碼建立精確法人契約，並驗證個別職缺身分；不能拿全站16或候選15當已通過正式來源驗收。最新1216報告已有104成功樣本41筆，因此沒有為增加取得率而重抓健康來源。研究未寫正式快取／SLA，未生成報告或模型請求。[完整資格核對與原件收據](evidence/source-acquisition/20261013/unipresident-public-careers-qualification.json)。

首次匿名下載HTTP200／curl56但正文0 bytes保留，原因未由該次證據確認；單變因HTTP1.1診斷則明確回curl63、Content-Length1,159,613，超過當次研究1MB上限。新入口研究改用2MB有界讀取後完整取得1,159,613bytes／0.935秒；兩個API頁共19,811bytes，較完整HTML小，單次樣本不代表長期延遲保證。所有5秒、TLS、無重導／自動重試限制維持；未改任何正式provider上限。原錯誤不覆寫，回應Set-Cookie未保留或送回。

另外完成 `yfinance_sync_enrichment.py` 唯一runtime修正：3324.TWO沿既有typed provider入口，在一般分析保留動態同業的partial、usable_count及原始收據。原流程會將五筆但缺6230PE的資料誤記success並遺失coverage；RED兩個真失敗，修正後相關102 passed、補充12 passed；獨立四個測試含零usable及不適用控制，與root重疊不加總。[實際diff](evidence/source-acquisition/20261013/thermal-sync-owned.patch)、[獨立覆核](evidence/source-acquisition/20261013/thermal-sync-independent-review.json)。

已以正式start_mac.command重載，API／worker identity、health與ready200、六個queue空均核對；1個owned／130個held runtime、env與158套件保持。原90天來源失敗列保持；3個舊終止job由原30天保留規則自然到期，發布驗證逐筆核對，沒有手動刪除或取消任務。沒有commit／push，也未執行新完整報告驗證。這項修正保留資料缺口的真實狀態，不把partial改成成功。[部署及當前驗證](evidence/source-acquisition/20261013/thermal-sync-final-current-proof.json)。

冷TWSE完整主檔另以gzip及HTTP1.1+gzip各做有界診斷：皆HTTP200但5秒內僅得180,224／114,688 wire bytes，完整解碼／公司數都0；不採用這個傳輸假說。TPEx普通identity回應完整1,074,417bytes／893家成功，只證明該次入口可用，不是新備援。6230官方PE空白仍保留未知，不從其他期間或不適用情形硬補。原20類目前仍9類各嚴格>80%，本輪formal provider/model ledger沒有增加；全目標未完成。[gzip診斷](evidence/source-acquisition/20261013/thermal-master-gzip-new-transport-research.json)、[HTTP1.1診斷](evidence/source-acquisition/20261013/thermal-master-http11-gzip-new-transport-research.json)。


## 2026-10-13 禾榮新官網財報／法說原件與兩檔月營收缺口驗證

依「繼續找」延續免費來源調查，本輪找到尚未記入本清單的禾榮7799官網原件入口。普通匿名TLS、每次5秒、無自動重試／重導／cookie／登入，11次native請求中10份完整下載；研究下載與离線解析不寫正式provider cache或SLA，也不等同正式報告成功。僅更新本清單與研究證據，沒有修改runtime程式、部署或補寫報告。

- [禾榮財務報表](https://www.heron-neutron.com/investors/financial/report)：原生HTML有9個公開PDF連結，網頁搜尋工具的文字擷取漏列這個表格，因此不能將其結果當作空頁。按原href實抓2026Q2合併財報2,776,305bytes／46頁／1.565秒，以及2025年度財報5,463,254bytes／58頁／1.726秒。前者的會計師核閱頁4–5沒有原生文字，仍是partial text；後者原生58頁可讀。2025封面及內文為本公司財報，2026Q2附註14頁列三家於2026新設子公司，須保留報表主體與期間，不能把兩者直接當成同口徑連續合併年報。原2023附件Content-Length9,148,536超出8MB請求上限，本次curl56、0bytes；確切傳輸失敗原因未另確認，該件不採用、不增加上限或重試。未驗證五年九必要事實完整。
- [禾榮法人說明會](https://www.heron-neutron.com/investors/conference)：今天10/13的20th QIC CEO Week明列[官網簡報PDF](https://www.heron-neutron.com/files/InvestorRelations/2.%20InvestorConference/20261013_IRConferencePresentation_CN.pdf)。完整4,000,939bytes／17頁／1.080秒；第1及17頁為無原生文字頁，partial text如實保留。封面目視為禾榮品牌，沒有日期；場次日期取自原索引與其精確附件連結，不由檔名或Last-Modified推首次發布／實際開會完成，也不是逐字稿。舊7799報告保存的場次仍是9/9，尚未補件；同一公司仍只是一個publisher。
- [禾榮月營收官網](https://www.heron-neutron.com/investors/financial/monthly-turnover)：4／6／7月顯示「-」，10–12月空白，不能自行補零。新取得的[證交所7799原件](https://www.twse.com.tw/pdf/ch/7799_ch.pdf)明列前三個月份為0；2026/04–09六個金額為0／504,000／0／0／334,000／1,105,000元。[燁輝2023原件](https://www.twse.com.tw/pdf/ch/2023_ch.pdf)同樣有最近六個月，這是既有官方入口的新個案覆蓋驗證，不冒稱新增平台。兩份PDF各5頁、產製10/13；與本次完整官方CSV1,072列的8／9月金額及千元單位逐值核對後，既有純parser均通過。沒有呼叫正式provider、沒有seed快取，也未證明需完整主檔的正式cold路徑已通過。

兩份實際報告經ReportArtifactLocator讀回hash保持：7799月營收仍3筆，2023仍0筆。另確認三個現行FinMind formatter以value真值篩選，會丟掉數值0；官方零值支持此缺陷可能造成7799少列，但原SDK回應未重新取得，本輪未修改程式或宣稱已修復歷史快照。下一步是保留0與缺值差異、補上有原件驗證的月營收單來源刷新，再按正確公司／場次／報表口徑接入新官網附件。

15:35:33台北正式近24h仍9/20原類別各嚴格>80%，全目標未達。與較早thermal-sync證據相比，正式帳本另有197筆來源及351筆usage新觀測，並非本輪精確起點差分；已分組保存，未調查精確發起者，不能宣稱全系統來源／模型請求為0或把其他工作變化歸因此研究。兩份報告保持、health／ready200；研究脚本不含來源補件POST、模型调用或台帳寫入。

證據：[來源資格與兩檔純解析驗證](evidence/source-acquisition/20261013/heron-yiehphui-free-entries/qualification.json)、[完整原生收據](evidence/source-acquisition/20261013/heron-yiehphui-free-entries/native-receipts.json)、[財報成功及拒收收據](evidence/source-acquisition/20261013/heron-yiehphui-free-entries/financial-native-receipts.json)、[同時段正式活動邊界](evidence/source-acquisition/20261013/heron-yiehphui-free-entries/concurrent-formal-activity.json)。


## 2026-10-13 月營收零值正式修正與兩家金控新免費招募入口

- 三條 FinMind 月營收 formatter 原本用金額真值篩選，會把已申報的 0 漏掉；現在共用 `monthly_revenue_rows`，保留明示零值、負值與合法數字字串，拒收缺值、非有限數、bool、不合法年度／月份。維持 SDK 最後六列選取及既有官方 fallback、額度／冷卻／審核規則。這改善月份完整度，不代表原本已有三筆的來源請求原先必定算失敗，也不是以列數增加取得成功次數。
- 公共行為測試先 **12 failed／3 passed**，修正後相關測試 **205 passed**，runtime／storage **21 passed**；獨立覆核 **156 passed** 及147項hash核對，無未解material finding。這些測試群有重疊，不相加成獨立總數。另修正測試fixture的lazy import洩漏：原production formatter回放也重現同45項日期失敗；在patch前先匯入transport再局部mock後通過，未修改正式時間邏輯。[範圍與測試](evidence/source-acquisition/20261013/monthly-zero-independent-input.json)、[獨立覆核](evidence/source-acquisition/20261013/monthly-zero-independent-review.json)。
- **正式載入完成**：透過一次RQ warm shutdown讓1216當前工作正常進入waiting_retry，再由 `start_mac.command` 重載。4份本次runtime、128份既有runtime、env及158套件版本核對，11件pending payload／未到期scheduled score保持，無force kill／取消工作／手動重排。新launcher23784、role-all worker23812、API23814；healthz／readyz200。啟動的既有保留政策自然到期28件30天terminal jobs與109列90天來源觀測，依原時間／規則核對並重建原zero ledger hash，並非人工刪除失敗；原診斷失敗保留。[正式重載](evidence/source-acquisition/20261013/monthly-zero-release-proof.json)。
- 禾榮7799在已載入修正後，以公共collector及現有FinMind SDK設定實取一次，**0.401秒／六筆**。保存的實際SDK response最後六列為2026/04–09：**0／504000／0／0／334000／1105000 NTD**，與此前完整TWSE PDF／官方CSV研究值逐筆一致；同份response放入舊真值formatter只有三列，證明目前修正有效。SDK response archive不是raw HTTP；callback次數也不冒充HTTP數。此次來源probe未寫正式報告或canonical SLA，其fetch_id在正式SLA查無新增；原9/23 SDK原件未保留，不能把此當舊報告完全同response的歷史重播。原兩位小數億元顯示仍可能把8月334000顯示成0.00，該精度限制未在此修改。[實際取得](evidence/source-acquisition/20261013/monthly-zero-live-7799.json)、[原數值與同輸入新舊對照](evidence/source-acquisition/20261013/monthly-zero-live-exact-value-verification.json)。

依今天2887與2883職缺來源確實0筆的紀錄，續找兩個尚未列入本清單的發行人招募入口：

| 新免費入口 | 已取得的原件 | 仍需保留的界線 |
| --- | --- | --- |
| [台新新光金控官網招募](https://www.tsholdings.com.tw/tsh/recruiting/?__locale=zh) → [自有職缺平台](https://tshr.taishinholdings.com.tw/Job/List?companyidstring=33) | 22次有界匿名GET全HTTP200／完整原件。原HTML checkbox與公開script明示母公司分類參數，不猜API。第1頁10列、第2頁累積15列且更多按鈕父容器b-hide；15個unique ID的完整明細、刊登日／公司分類／職類／工作地點／職務內容全部取得。兩筆明示金控角色2004／2003刊登日為2026-06-11／06-10。 | 15是平台該分類列出的紀錄，不是招募15人／全公司總數，也不證明每筆仍有效。刊登日跨2021-11-15至2026-10-08；2071實習與1990培訓含子公司角色，不能直接算母公司職缺。2011官方說明僅26字，完整原文不等於內容詳盡。尚無production adapter或正式補件。 |
| [凱基金控人才招募](https://www.kgi.com/zh-tw/career/talent) → [官網明示Workday入口](https://cdfh.wd3.myworkdayjobs.com/zh-TW/External) | 2次普通匿名GET均HTTP200，完整98,229／7,425bytes原件，官方頁明示兩個同一Workday link。 | Workday目前僅取得JavaScript入口殼頁，未取得職缺列表／明細；數量是unknown，不是0，不能列為職缺來源成功。未呼叫登入／應徵／token API或猜測API endpoint。 |

兩家股票代號／法人／官網以已封存完整1095列TWSE主檔重新核對：2887／台新新光金融控股股份有限公司／80328055及2883／凱基金融控股股份有限公司／70827383。該原件出表10/11、取得epoch1791790405.013688，原24h cache已到期，研究僅沿原epoch與hash核身分，**未續期、seed cache或冒稱正式fresh master已通過**。招募網站免費可讀不等同開放授權。所有研究僅存原件，未把新列表、15筆明細或24次下載手工加入正式成功率。台新研究第一次以任意>50字assert拒收2011的完整26字說明，已保存診斷並改為原文非空／完整檢查；沒有改production品質門檻或再HTTP。[台新原件資格](evidence/source-acquisition/20261013/tsh-2887-free-recruiting-entry/qualification.json)、[凱基入口限制](evidence/source-acquisition/20261013/kgi-2883-free-recruiting-entry/qualification-held.json)。

**16:18:38台灣時間**按原20類／rolling last_24h／逐類嚴格>80%仍為 **9／20**。月營收114/197=57.87%、職缺22/70=31.43%、財報27/46=58.70%、法說23/52=44.23%；search_upstream336/420=80%，等於80不算突破。其餘變化含自然排程與窗口移動，不歸因本次研究；目標保持未完成。11件原pending jobs仍存在且沒有取消；原排程自然繼續，有背景provider／模型活動，未聲稱全系統零新增呼叫。下一步是讓新入口通過逐筆雇主／有效性契約並接入來源刷新，以及補上月營收單來源刷新，不直接改舊分析或品質警示。[當前正式原口徑驗收](evidence/source-acquisition/20261013/monthly-zero-final-current-proof.json)。


## 2026-10-13 月營收共用快取正式上線與凱基完整免費職缺入口

### 實際修正與驗證

本輪將 FinMind 月營收的 market、legacy/core 及 typed provider 三個入口共用同股票／台北曆月的 1800 秒觀測快取，保留原取得時間；普通核心報價更新不再順便重抓仍新鮮的月營收，顯式 force 仍走原供應商 circuit／quota admission 並寫回替換資料。失敗 force 保留實際失敗，不把 last-good 當新鮮成功；官方最新月營收與六月份歷史備援仍適用。這是 SDK 觀測快取，不是新的 raw HTTP 原件。

獨立覆核重現兩個恢復缺陷，均以實際 RED 保存並關閉：時間 metadata 損壞時原本直接重抓却未寫回；以及合法 JSON 可表示的巨大整數造成 math.isfinite OverflowError。現在在共用鎖內拒收損壞時間，保留合法 error cooldown，下一次實際結果／失敗會正常寫回。新 module 不再有繞過共用鎖的 acquire 例外旁路。原始四欄時間、並行、ticker／月份隔離、TTL、強制失敗及額度保護均有隔離行為驗證。Root 最終相關含必要 runtime/storage 共303 pass；獨立271 pass，彼此重疊，不相加。

core payload 的 generic 月營收摘要改成同次真實 acquisition/cache audit；舊 generic「本次重新抓取完成」本來就被 canonical acquisition 當 aggregate 排除，因此本輪不是修正歷史 SLA 灌水。暖快取仍為 skipped_fresh_cache、HTTP0、SDK0，使用新 fetch/operation correlation 並保留原 epoch。隔離 canonical 寫入驗證 cold＋warm 為 fetched1／attempt1／fresh_cache1。

正式用 start_mac.command 重啟：8 owned＋125 preserved＝133 runtime檔，環境與158套件 hash／版本核對保持；healthz／readyz200。11件待重試payload與scheduled scores保存至自然到期，無人工取消、刪除失敗或重設冷卻。原30日維護自然清掉2件終態job、原90日維護自然清掉92筆零資料列，release原列與完整重建hash保留；不得拿此自然retention當本輪刪除或成功率改善。詳見 monthly-sharing-release-proof.json、monthly-sharing-supported-warm-quiesce.json。

上線後以公開 collector 對7799.TW作一次真實取得與兩次跨入口重讀：第一次6月份／0.358130秒／SDK1；legacy重讀0.000325秒／SDK0；market重讀0.000254秒／SDK0。三次values相同，原取得epoch1791882161.020052保持，兩次warm的HTTP0明確記錄。Cold只有SDK呼叫觀測，沒有將SDK call count冒充physical HTTP次數。SDK六筆原dataframe另存；測試沒有手動寫SLA、產生模型工作或覆寫正式報告，三個fetch_id在正式SLA皆0列。自然背景5314月營收另有正式success觀測，不能混成這次probe的成功。詳見 monthly-sharing-live-7799.json 與 monthly-sharing-final-current-proof.json。

17:03:54台灣時間正式rolling24h：原20類中11類各嚴格>80%，目標仍未完成。月營收106/145＝73.10%；社群92/115＝80.00%仍不算突破。其餘未過：另類20/47、動態同業87/116、法說22/49、財報27/44、法人73/175、同業探索29/56、新聞283/468。這是新窗口現況；不把舊失敗移出24h、既有背景工作或新研究資料歸功於剛上線的快取。尚需自然正式執行樣本驗證長期減少429效果。

### 凱基金融控股2883：由空HTML補到完整公開清單與11份明細

官方[人才招募](https://www.kgi.com/zh-tw/career/talent)直接連[公開Workday入口](https://cdfh.wd3.myworkdayjobs.com/zh-TW/External)。普通瀏覽器頁面確實載入全站495筆，包含多家子公司；公司facet精確選擇「凱基金融控股股份有限公司 KGI Financial Holding Co., Ltd.」後，顯示[母公司11筆／1頁](https://cdfh.wd3.myworkdayjobs.com/zh-TW/External?hiringCompany=39d77424bb861000fb161fa41a5e0000)，不能把495全歸母公司。

藉正常UI及只讀Network觀察取得原生 POST `/wday/cxs/cdfh/External/jobs`、hiringCompany=`39d77424bb861000fb161fa41a5e0000`／limit20／offset0／空searchText；明細 GET `/wday/cxs/cdfh/External/job/<清單中的原identifier>`。匿名重播不用cookie、登入、權杖或應徵操作：1清單＋11明細全HTTP200，完整bytes/hash保存，单次最慢1.331秒；12只計原生研究重播，不含瀏覽器自動網路請求。11筆id、title與清單吻合，hiringOrganization逐筆皆母公司全名，posted/canApply為true，userAuthenticated為false，description均非空。

11筆編號為 JR106341、JR106307、JR106263、JR106262、JR105952、JR106074、JR105994、JR105993、JR105957、JR105956、JR103676。來源startDate為2026-01-20至09-21，保留原欄位意義；「超過30天」不推算成精確首次刊登日，沒有證明初次刊登、關閉日期或每職缺招聘人數。11是當時篩選清單及明細數，不是11人、全產業或全球完整職缺量。

仍屬研究入口，尚未接入正式provider／SLA／報告。先前全上市主檔原件已超過其24h有效期，僅可作研究身分線索，不能續期或seed成當期正式身分收據。後續接入必須沿現有合法主體、日期、原件hash及原quality gate，並處理原生查詢deadline／冷卻／原文快取；不為11笔清單降低原替代資料門檻。證據在 kgi-2883-free-recruiting-entry/qualification-native-complete.json、browser-discovery-readback.json及12份native receipt/raw JSON。先前 qualification-held.json 保留當時只取得JS shell的判讀，沒有覆寫成當時成功。


### 2026-10-13 17:45 凱基金 2883 免費官方職缺備援已部署

[凱基金控人才招募](https://www.kgi.com/zh-tw/career/talent)明示連到[公開 Workday 平台](https://cdfh.wd3.myworkdayjobs.com/zh-TW/External?hiringCompany=39d77424bb861000fb161fa41a5e0000)。完整母公司清單11筆及11份明細已以匿名原生請求核對；只將JR106341（來源startDate 9/21）及JR106307（9/18）兩筆通過原30日窗口、母公司身分與仍開放欄位者接入2883.TW備援。清單11筆不代表11個近期職缺或招募人數；startDate不是首次公開發布的獨立證明，涵蓋仍partial。其餘9筆未放寬日期納入。來源免費可讀，不宣稱開放再授權。

新 `kgi_careers.py`／`kgi_careers_transport.py` 經既有AlternativeJobOpeningsProvider與data_trust_audit接入；先核官方主檔凱基金／凱基金融控股股份有限公司／70827383及EQUITY、ticker／stock_id一致，104／TaiwanJobs無已驗證筆數才用官方備援。成功後省略重複關鍵字搜尋，保留原主來源失敗。保留完整JSON原bytes、SHA、URL、method、固定母公司filter、個別明細與原取得epoch；計數重讀原件，prompt保留職務描述但不含body_b64。匿名讀取無cookies／登入token／重導／重試，原單請求5秒／總12秒／500KB與cooldown保留；12秒限官方子流程，不是含原104流程的全流程上限。

獨立P2發現雙層context cache可把原1800秒延為接近3600秒。原兩個RED保存在-before-ttl-fix與log，已修正context TTL採原件最早取得時間的剩餘秒，每次讀回再核1800秒；含整數TTL最少1秒邊界，過期只走同shared lock正常重抓一次，error／retained舊資料不能fresh。歷史snapshot24h原件重驗上限保持，不作live續期依據。root整組465pass（包含required runtime/storage21）、独立211pass與補充1pass分開記錄，不加總重疊數。

五個runtime檔透過start_mac.command部署；其餘130檔、環境設定及158套件完全保持，health／ready皆HTTP200，11件pending的payload與scheduled score保存，未force kill、手動刪失敗、修改quota或commit／push。這輪重啟沒有30日job或90日source自然到期刪除。正常公開provider使用既有2883報告identity實測：原104及TaiwanJobs均unavailable，官方實際冷HTTP3取得合格2筆，全流程15.115秒；下一次暖讀0.001924秒／HTTP0，原epoch1791884709.2099142相同。官方原件已有完整封存；主檔使用仍有效的15:38既有parsed官方收據，這次沒有取得新的完整主檔body，不混為新主檔HTTP成功。

這是已部署程式的來源單項實測，沒有重寫報告HTML／Markdown／snapshot或呼叫模型，也沒有呼叫手工SLA記帳；兩個probe fetch IDs在正式provider_sla_events均0筆。17:45:33時尚無重啟後自然alternative_data觀測，因此不宣稱已驗證新正式完整報告成功。正式rolling24h仍僅10/20原類別各嚴格>80%；alternative_data16/43=37.21%、dynamic_peer_metrics72/99、earnings_call22/47、financial_statements27/42、institutional_trading68/153、monthly_revenue90/129、peer_discovery29/54、recent_catalysts230/384、search_upstream174/218、social_sentiment75/98未過線。窗口離出／背景工作會改變比例，不能把研究、診斷、暖cache或自然到期歸因成patch成功，全部20類目標仍未完成。

[正式部署](evidence/source-acquisition/20261013/kgi-careers-release-proof.json)、[來源實測](evidence/source-acquisition/20261013/kgi-careers-live-public-provider.json)、[修正後独立覆核](evidence/source-acquisition/20261013/kgi-careers-independent-review.json)、[當前全20類](evidence/source-acquisition/20261013/kgi-careers-final-current-proof.json)。台新新光2887原15筆入口研究仍不能推定近期母公司職缺；其新鮮度、雇主與有效狀態缺口保持，未為補成功率而納入。

### 2026-10-13 18:10 新免費入口：銀行局現行機構名冊與金控財務原表（研究已驗證，尚未接入）

本轮依原資料缺口續找，發現此前未接入的銀行局官方入口。17次匿名原生GET均HTTP200，單次5秒／connect2秒／2.5MB限額，無cookie、登入、重導或自動重試；完整原bytes、SHA256、URL及取得epoch在 `evidence/source-acquisition/20261013/fsc-public-data-entry/`。17次包括索引、JavaScript、查詢回覆及實際資料檔，不等於17個新來源或正式成功。來源驗收與17份收據見[qualification.json](evidence/source-acquisition/20261013/fsc-public-data-entry/qualification.json)。

| 新入口 | 本機原生取得與內容 | 可以補的缺口／限制 |
| --- | --- | --- |
| [銀行局金融控股公司名錄](https://www.banking.gov.tw/ch/home.jsp?id=606&mcustomize=FscSearch_BankType.jsp&parentpath=0,590,604&type=F)及其[全機構下載](https://www.banking.gov.tw/ch/ap/bankno_excel.jsp) | HTML完整141,690bytes、0.169秒；下載檔1,125,720bytes、1.739秒。5328筆機構／分支／關聯紀錄，10分類；金控段109筆中14筆母機構、95筆分支欄非空的關聯機構。14母機構法名與HTML逐一相同，異動日期2026-09-16至10-12。 | 金控法名、機構代碼、官網及關聯機構發現。不是5328家上市公司；沒有股票代碼或統編，不可直接取代TWSE身分綁定。異動日不是首次發布日或全檔as-of日。 |
| [銀行局金融業務統計查詢](https://survey.banking.gov.tw/statis/webMain.aspx?funid=r1021&sys=100)：11-1金控合併財務資料 | 原生查詢最新上限11507，依公開JS參數取得ODS下載頁及完整12,035bytes原表／0.107秒；含14家金控。 | 合併資產、權益為2026-06-30，母公司業主稅後淨利為2026上半年；合格資本與資本適足率為2025-12-31，單位分別新台幣百萬元／%。原件說明截至2026年8月底申報自結數；查詢年月不能覆蓋各欄期間，也不是PIT或經審計財報。 |
| 同入口11-2金控財務及業務比率 | 2026年7月底表10,930bytes／0.109秒；2025年12月底表11,010bytes／0.145秒；兩表各14家，完整ZIP CRC可讀且法名可與新名冊核對。 | 7月底只有負債／淨值、負債／資產、雙重槓桿三比率；ROE、ROA原為「－」，保留未知。2025年度表才有五比率，元大年度ROE11.24%、ROA9.75%。尚未證明其與generic合併TTM口徑相同，不覆寫當期指標、不年化或補零。 |
| [本國銀行ROA／ROE原始ODS](https://www.banking.gov.tw/webdowndoc?file=/stat/roa_e.ods) | 完整41,953bytes／0.160秒，歷史列到2026年8月。 | 產業總體背景、稅前當年累計口徑；不是逐公司資料，不能拿來填任一上市金控。 |

可公開免費讀取；銀行局網站所連[資料開放宣告](https://www.banking.gov.tw/ch/main.jsp?websitelink=artsublink.jsp&dataserno=201605130005&mtitle=%E6%9C%AC%E6%9C%83%E7%B6%B2%E7%AB%99%E8%B3%87%E6%96%99%E9%96%8B%E6%94%BE%E5%AE%A3%E5%91%8A)採政府資料開放授權條款第1版並要求標示出處，仍保留第三方另行聲明例外。該頁原件亦已保存。

另核金管會[公開API規格](https://stat.fsc.gov.tw/api/swagger/openapi.json)與189資料集目錄，確實無須認證。[dataset6041](https://data.gov.tw/dataset/6041)雖metadata更新至2026-06-22，原生CSV5,293列的公告日期全部仍為20241202，仍含台新與新光分立舊名單。判定不適用目前身分，不能以HTTP200或剛下載將舊內容當新鮮資料；上列銀行局現行名冊是實際找到的替代入口。API目錄189不代表189個合格補件來源。

解析細節已保留：銀行局名為CSV的檔案實為UTF-16LE BOM、tab分隔與 `="文字"` 欄位，原檔尾有U+0A0D；以UTF8／CP950解碼的初次研究失敗後只重讀同份bytes，沒有網路重試。只剝除精確文字包裝，不執行Excel公式。金控段初次整段计數109，核對後明確分為14母機構＋95關聯項，不能一律作109家金控。表格名稱做NFKC後與法名核對僅供研究；尚未完成股票代碼／統編、業務可比性或持股比例核驗。

下一個實作切片：以當期TWSE法名／股票身分綁定新名冊，新增有明確報表期間的金控監理補充資料，再做候選同業備援；各欄保留單位、個別期間、self-reported狀態、完整原件與原取得epoch。金控資格不等於經濟業務可比；優先核2885及實際缺件目標，不批次重抓健康來源。上述三表不能補五年完整財報或缺少的無形資產現金購置金額，也不能直接消除法說／新聞缺口。

同期國泰2882最新簡報已完整下載56頁，但原件有轉傳限制與82個未辨識符號，維持metadata／連結模式；旭隼6409官網Financial-Information頁完整取得，但尚無可用新法說原件。兩項保留未接入，見 cathay-2882-presentation-entry/qualification-held.json 與 voltronic-6409-presentation-entry/native-financial-index.json。

本轮僅研究與紀錄，未修改runtime、重啟、seed provider cache／SLA、呼叫模型或改報告。135個目前已部署runtime檔及.env hashes仍一致、原三程序保持，health／ready200。18:10:24正式rolling24h仍10/20原類別各嚴格>80%；未達為alternative14/41、dynamic peer64/91、earnings20/47、financial25/40、institutional66/143、monthly81/120、peer discovery28/51、recent206/345、search141/185、social67/90。研究HTTP成功不計正式SLA，窗口自然離出／背景工作不歸為本輪改善，全部20類目標仍未完成。

### 2026-10-13 18:31 續找：元大月度盈餘、活動簡報與國票月度業績（原生取得；未接正式 provider）

續作先核元大2885真正的同業缺口。保存的報告 `2885_TW_v4_report_job_753d498f1f9c.html` 已有8則近期新聞、7個reported publisher、六個月營收及2026-09-18法說metadata；缺的是可比同業。一次公開collector診斷1.4667秒，30候選中10個candidate callbacks均取得complete指標，但10個都因Yahoo細產業與目標 `FinancialConglomerates` 不符而排除，結果0。這是業務分類差異；本次diagnostic沒有支持網路／quota失敗的證據。callback10不冒充底層HTTP10，沒有重跑健康來源以灌正式成功率。獨立覆核確認：銀行局「同為金控」不能直接改cohort status繞過此條件；新監理數值必須獨立typed supplement，不能塞入原dynamic peers／ROE／自動同業估值。

新找到並實際匿名下載6個原件（3個資料入口、2個所連PDF及1個當期TWSE主檔），全部原生HTTP200；單次5秒、connect2秒，HTML/CSV上限2.5MB、PDF8MB，無cookie、授權、重導或自動重試。SHA、完整bytes、URL、原取得epoch與診斷均在 [yuanta-free-ir-entry/qualification.json](evidence/source-acquisition/20261013/yuanta-free-ir-entry/qualification.json)。不是6個新資料家族或6筆正式SLA成功。

| 新免費入口 | 原生實測與有效資料 | 語意及待處理 |
| --- | --- | --- |
| [元大集團每月營運概況](https://www.yuanta.com/TW/IR/Financials/Monthly-Earnings) | HTML400,179bytes／0.296秒；安全JSON decoder讀取內嵌 `var data`，不執行JS。2002-01至2026-09共297個連續月份鍵、1695個公司月份列；2026九個月的54列／162數值欄格式檢查完成。最新金控當月5,018、累計54,959百萬元，EPS3.96；人壽當月(49)保留负值。 | 這是月度自結盈餘，不是月營收。網頁只選列主要子公司；不能說1695家或完整所有集團成員。頁面明示2013-01至2014-05合併口徑、2014-06起各母公司口徑；歷史更名、股權及期間身分尚未逐一驗證。最新一頁PDF269,300bytes／0.469秒，原生只抽出日期與標題51字，但完整渲染頁已目視核對最新6列／18數值；文件宣告日期2026-10-13，不升格首次發布時間。PDF另有其他子公司及分項，不能說HTML完整覆蓋PDF。 |
| [元大公司簡報與活動](https://www.yuanta.com/EN/IR/Financials/Presentations-and-Events) | HTML102,291bytes／0.697秒；內嵌JSON有2006–2026共21年、174筆活動。最新2026-09-18第一金證券線上投資人會議，與已保存MOPS場次吻合，並有明確公開PDF／影音連結。當場PDF2,989,487bytes／0.903秒、39頁已完整下載。 | 不是174份完整逐字稿，也不是174次已核實實際舉辦。PDF圖表大量為影像，native text缺主要數字；只完整渲染並目視檢查第2、6、8頁，尚未完成全39頁OCR／內容驗證。仍不把簡報稱為逐字稿，不因下載200而解除正文品質門檻。 |
| [國票月度業績報告](https://www.ibf.com.tw/performance_reports) | 純HTML129,422bytes／0.668秒，34張月份表，2023-12至2026-09，可直接讀母公司與主要子公司月度／累計盈餘及EPS。最新母公司當月3億4,579萬元、累計36億9,267萬元。 | 掃描發現2026-06累計表頭寫1–5月而敘述為1–6月；2024-01金控金額含「2億1.867萬元」歧義標點。保留完整原表及兩個隔離原因，不靜默修正為推測值，不稱全34期已合格。仍需逐欄口徑、發布日期與負值核對，不能填monthly_revenue。 |

當期[TWSE完整上市CSV](https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv)673,299bytes／4.864秒，1095列、出表1151013；元大2885／70796749／元大金融控股股份有限公司／yuanta.com及國票2889／80330257／國票金融控股股份有限公司／ibf.com.tw均吻合。與上一輪銀行局14個母金控法名做NFKC後逐一對應，13個唯一上市股票／統編，臺灣金融控股未在此上市名錄找到，保持排除；銀行代碼258不當股票代碼。這只證明當期身分，不證明歷史組成或業務可比。

13個上市金控的銀行局11-1共65個事實已轉為**研究用**結構，逐欄保留原期間、單位、合併／監理集團範圍、自結數、原欄名、SHA、原取得epoch與當期身分原件：`regulatory-holding-facts.research.json`。没有匯入provider、snapshot、同業估值、財報或SLA。元大2026-06資產在銀行局自結表為5,151,051百萬元，簡報第8頁為5,150,931百萬元；差120百萬元且確切原因未證明，保留兩個版本，不自動互相覆蓋。簡報的standalone equity／annualized ROE也不替代合併權益或TTM ROE。

研究腳本與原件驗證已保存並重新讀回；沒有runtime修改、部署重啟、provider cache/SLA seed、模型呼叫或報告改寫。135個已部署runtime檔及.env hash仍一致，原三程序保持，health／ready200。18:30:56正式rolling24h仍10/20原類別各嚴格>80%，未達為alternative12/36、dynamic37/61、earnings17/42、financial22/33、institutional61/119、monthly62/79、peer discovery24/46、recent134/255、search93/135、social52/75。研究來源可讀不等於正式報告／來源成功；自然窗口變化不歸因本輪，完整20類目標仍未完成。

下一步以這批已取得的完整原件做獨立金控監理補充表與月度盈餘的typed設計，明示所有期間、衝突與不適用欄位；原dynamic-peer細行業／business comparability gate及原20類分母保持。元大同業0的問題仍須真正的同期間業務組合與可比選擇證據，不能靠新增資料名稱宣稱已解決。


### 2026-10-13 18:59 華航五年財報缺欄與民航局航空業免費入口

續查正式華航2610.TW失敗事件451307：19份MOPS公開JSON／renderer／索引原件完整hash均重驗，但2021–2025各年只具8/9必要事實，全部缺無形資產現金支出。JSON「其他投資活動」是合計，不拿來代填或補零。

找到官方新儲存站完整[2022Q4合併財報](https://cms-externalcontent-prod.s3.ap-northeast-1.amazonaws.com/ci/Investor-relations/Consolidated-Financial-Statements/EN/2022Q4.pdf)、[2024Q4合併財報](https://cms-externalcontent-prod.s3.ap-northeast-1.amazonaws.com/ci/Investor-relations/Consolidated-Financial-Statements/EN/2024Q4.pdf)、[2025Q4合併財報](https://cms-externalcontent-prod.s3.ap-northeast-1.amazonaws.com/ci/Investor-relations/Consolidated-Financial-Statements/EN/2025Q4.pdf)。三份原生匿名GET均HTTP200，分別2,378,818／2,084,245／2,823,333 bytes、90／94／91頁、0.956／1.297／0.869秒。未登入、帶cookie、重試或使用模型。2025連結由公開搜尋命中官方檔案；2022／2024路徑由官網正常UI已發布的ECL原件路徑解碼，沿同一官方CDN存放位置取得，非猜測檔案編號。官網下載查詢API三次403及首頁5秒截斷均保留失敗，不升格來源成功、不繞過限制。

三份第12頁完整渲染核對合併scope、雙年度欄位、仟元與括號負值，補得無形資產支出2021 −203,116、2022 −151,010、2023 −167,860、2024 −204,657、2025 −269,314（皆仟元）。十個既有CFO／PPE數字與原MOPS一致；2021–2024原8項事實亦與次年MOPS比較欄一致；2024兩份PDF重複數字一致。研究重建五年45個必要事實，不更改原provider error。2021／2023來自次年比較披露，不能冒稱原年度發布時即可取得。原[年報目錄](https://calec.china-airlines.com/annual-report/)亦可直下載；2024、2025年報本冊缺該完整附表，2023年報有字型編碼異常，改用上述純財報原檔。原2022年報162頁及2023年報174頁目視同值；不以字母平移猜編碼。證據：`china-airlines-2610-annual-entry/qualification.json`、三原檔／收據、visual-readback與可重播研究腳本。

新增兩個民航局完整免費官方入口：

| 入口 | 本次原件驗證 | 可補內容及限制 |
|---|---|---|
| [國籍航空業營運概況](https://www.caa.gov.tw/Article.aspx?a=518&lang=1) | 索引372,915bytes／1.843秒；列出38期，最新115年第2季索引10/2更新。ODS7,364bytes／0.280秒、PDF63,798bytes／0.235秒，均200。7家公司21數值ODS／PDF逐欄一致並完整目視。 | 內容實為2026上半年營收、稅後淨利及累積盈餘；個體口徑，非Q2單季、非合併或TTM。以當日TWSE完整原件精確法名／統編綁定2610、2618、2646、6757，可提供航空候選排序；不直接覆蓋dynamic_peer數值。 |
| [國籍航空業財務重點](https://www.caa.gov.tw/Article.aspx?a=2789&lang=1) | 索引列出27期；最新2026Q2文件內註115.9，索引10/2更新。ODT19,861bytes／0.179秒、PDF238,516bytes／0.426秒，均200，完整一頁目視。 | 20項財務監理指標、現金流／負債／流動比率與注意事項。除立榮、星宇、虎航為核閱審定數，其餘為自結個體資料；華航非無保留標記的註釋為部分子公司與權益法投資未核閱，不能推成繼續經營疑慮。自動判讀仍需保留合併儲存格、字色及每欄期間。 |

CAA兩索引＋四原件共六次原生GET均200；完整原件、欄位與當期身份保存在`caa-airline-entry/qualification.json`。虎航屬華航集團，不能當獨立佐證。名單只改善候選排序；原exact-stock、Airlines細產業、數值完整度、業務可比及最多10次／5筆限制仍需保持。上一輪實測華航原候選前十家皆海運物流而全數被細產業排除，長榮／星宇尚未輪到；本次尚未重新抓取同業指標，不能宣稱同業成功。

本輪完成入口研究與缺口重建，未改runtime、接入provider、補seed、改報告、呼叫模型或重啟服務。135個正式runtime檔hash及.env保持，原三程序身分一致，healthz／readyz200。2026-10-13T18:58:22+08:00正式rolling24h為11/20原類別嚴格>80%；仍未全部达標，窗口自然變化不歸因研究。本次讀錯`hours=24`參數的all-window原回應、`/health`404也保留，驗收只採後續正確`window=last_24h`及`/healthz`。下步為新財報來源補上可自動重驗的發行人／發布鏈與有界解析，再接來源備援；CAA先做候選排序而非放寬數值可比gate。


### 2026-10-13 19:26 民航局免費航空候選入口已接入正式查詢

華航2610原同業查詢先耗用10次於海運、物流，全部細產業不符。新增[民航局國籍民用航空運輸業營運概況](https://www.caa.gov.tw/Article.aspx?a=518&lang=1)的最新期完整ODS入口，先核航空業者、當期股票主檔與精確名稱，再排航空候選；四個已綁定的上市航空代碼可使用。華航／台灣虎航已知集團pair從候選及legacy尾列排除。仍守10次候選、Yahoo exact symbol/EQUITY/Airlines、同年度營收／期末資產、缺值和partial，所有CAA財務欄不混作合併、TTM或同業估值；whole-business/size comparability仍未驗證，原prompt及估值排除旗標不放寬。

同一缺口的未改public collector真實研究驗證：FinMind當日4336主檔、CAA原生2GET，在5.9067秒得到長榮航2618八項完整、星宇2646七項／缺pe_ttm（0→2可用同業，整體partial）。獨立快取／SQLite，正式cache與SLA未seed、模型0；原件SHA與最終parser再核，不代表已產生新正式報告或正式同業類別已達80%。目前只資格化最新Q2/H1表，新季度或附件改版拒收，禁止暗退旧季度。全表7業者僅作帶2026-06-30期末的搜尋線索，非現時營運或完整財務可比證明。

單次5秒/connect2、CAA總12秒、native TLS、禁proxy/cookie/auth/redirect/retry與原件1800秒TTL保留。兩項獨立P2已重現並修：鎖等待限剩餘deadline，最新季度先由列期別判定再核附件格式及一致性。原件／cache篡改、過期、拒絕、8併發共用2HTTP均驗證；4個航空ticker的正常分析改typed provider，partial不能被外層list包裝升成success。Root164pass、獨立145pass（有重疊，不加總，含必要21項runtime/storage）；另擴大醫材回歸有11項在修改前後一致失敗，原日誌保留，未改醫材route或聲稱全套全綠。

3 owned＋133 preserved＝136 runtime檔、環境與158套件已核對；由start_mac.command部署，API／worker新PID與healthz／readyz 200；4件排程payload及原score保持。134筆90日前來源零資料列按原retention自然到期，完整原列與hash在release證據可重建；未手動刪除、取消任務、灌成功或重寫report。19:26正式24h仍11/20原類別各嚴格>80%，同業22/33（66.7%）；rolling自然離窗不歸因本修正。全部20類目標未完成，後續仍需將已找到的華航原生完整財報缺欄橋接與其他低成功率入口完成資格化。

證據：[release](evidence/source-acquisition/20261013/caa-airline-release-proof.json)、[真實public collector](evidence/source-acquisition/20261013/caa-airline-integration/live-public-collector.json)、[獨立覆核](evidence/source-acquisition/20261013/caa-airline-integration/independent-review.json)、[全20類正式24h](evidence/source-acquisition/20261013/caa-airline-integration/formal-24h-readback.json)。


### 2026-10-13 20:24 華航五年財報橋接已部署；正式首次補件仍逾時

[華航官方英文財報目錄](https://www.china-airlines.com/nz/en/about-china-airlines/investor-relations?tab=FinancialReportsTab)完整 Next JSON 發布鏈已讀取，精確指向官方 CDN 的2022、2024、2025合併查核財報。新增固定華航2610入口：完整當期TWSE公司名冊、MOPS索引／renderer／五年三表共19原件、完整IR頁及三PDF，共24次請求。只補原MOPS缺少的無形資產現金支出；同年營業現金流及設備支出必須與MOPS主期、次年比較欄全部吻合，再重建2021–2025五年45個必要事實。2021及2023明示為次年比較披露；英文譯本以中文原件為準，未證明歷史PIT或最終版本。五年、九科目、品質門檻、5秒單次／45秒整批deadline及host cooldown保持。

真實未改public collector於獨立cache／SQLite在12.9946秒完成24個原生HTTP請求與五年45facts；未seed正式cache/SLA，未呼叫模型。最後程式再讀原件1.2008秒／HTTP0仍可重建。Root最終267pass，獨立287pass（包括額外20個receipt／deadline／SLA等反例，重疊不加總）；PIT/finality旗標可被改寫的P2已補實際反例並關閉。新固定PDF子程序有大小、頁數、頁面範圍、10秒與資源限制，保留中文／英文與比較期語意。8 owned＋133 preserved＝141 runtime檔已由start_mac.command部署；env及158套件、4件pending payload／scheduled score保持，無force kill、取消任務、retention刪除、commit或push。新launcher73839／worker73867／API73869，healthz／readyz200；20:23同hash及程序再次核對。

正式既有缺五年報告`2610_TW_v4_report_job_bd9994877f11.html`只送一次annual來源補件，5.4179秒回HTTP502。第一個完整CSV名冊回HTTP200後，body在5秒內未完成；事件451450仍是error／record0，不發出後續MOPS/PDF請求。HTML、Markdown及原四年JSON快照hash全部保持，沒有把獨立成功冒充正式報告成功。正式完整end-to-end補件尚未通過，不能宣稱這項資料缺口已在正式報告消除。

另一次原生JSON全市場名冊也於5秒逾時，只取得245760 bytes，未採作完整資料。後續嘗試標準Accept-Encoding的CSV研究下載取得完整673299 bytes／1095列／出表1151013／2.0936秒，與先前完整原件SHA一致；但未觀察到content-encoding，wire大小亦相同，不能歸因壓縮改善，沒有改runtime傳輸、使用研究seed、延長deadline或再送第二次正式補件。

見[正式部署](evidence/source-acquisition/20261013/cal-annual-release-proof.json)、[267項測試](evidence/source-acquisition/20261013/china-airlines-annual-integration/green-final-v3.txt)、[獨立覆核](evidence/source-acquisition/20261013/china-airlines-annual-integration/independent-review.json)、[真實隔離取得](evidence/source-acquisition/20261013/china-airlines-annual-integration/live-public-collector.json)、[正式首次失敗](evidence/source-acquisition/20261013/cal2610-annual-one-source-refresh-attempt.json)、[收尾查驗](evidence/source-acquisition/20261013/china-airlines-annual-integration/closeout.json)。

### 2026-10-13 20:24 新找到 TWSE 單一公司三個小型免費入口

從官方HTML所發布的JS及共同`/rwd`前綴確認三個JSON入口；全程普通匿名GET、TLS、5秒單次／connect2秒、完整body及SHA、無重導或自動重試。此批11次研究請求（6頁面／JS、3主要API、1 T86交叉比對、1失敗公司API）為10次完整HTTP200及1次逾時，不是11個新資料家族或正式成功。未修改runtime、重啟、seed provider cache/SLA、呼叫模型或改報告。

| 免費入口 | 實測與核對 | 接入界線 |
|---|---|---|
| [TWSE單一公司財務分析](https://www.twse.com.tw/IIH2/zh/company/financial.html?code=2610)／[公開JSON](https://www.twse.com.tw/rwd/zh/IIH/company/financial?code=2610) | 華航完整2826 bytes／0.1189秒，2025-09至2026-09連續13個月營收。官方JS明示元／NTD、直接讀取數列；2025-09、2026-08、2026-09三點與既有正式完整月營收CSV千元×1000逐值一致。原CSV只重讀保存原件，不算新HTTP。 | 優先資格化為六月份營收的補充備援；其餘10期未獨立交叉核對、未證明PIT或全市場覆蓋。另查原失敗冠西電2466在5秒內0bytes逾時，保持失敗，不能說全公司可用。EPS／利潤率等不是五年九項完整財報；「同業平均」成員及可比性不明，不能直接充當dynamic peers。 |
| [TWSE單一公司法人交易](https://www.twse.com.tw/IIH2/zh/company/investors.html?code=2610)／[公開JSON](https://www.twse.com.tw/rwd/zh/IIH/company/foreign?code=2610&start=20260901&end=20261013) | 完整2565 bytes／0.2276秒，2026-09-01至10-13有28個日期，外資／投信／自營商／總買賣超四列。官方JS最終axis及suffix為張；與10/13原生T86同公司核對。 | 圖表為0.01張精度。自營商-36.61張換算-36610股，原T86為-36608股；總數10540.85張換算10540850股，原T86為10540852股。保留概略趨勢候選，不注入要求精確股數的歷史或以四捨五入修正原數。僅最新日核對，未核全部28日。 |
| [TWSE單一公司資訊揭露](https://www.twse.com.tw/IIH2/zh/company/information.html?code=2610)／[公開JSON](https://www.twse.com.tw/rwd/zh/IIH/company/events?code=2610) | 完整8609 bytes／0.4012秒，重大訊息、財報文件、法說各列10筆。保留代碼／名稱、ROC日期時間、原文URL。財報10列只有9個不同row、2個目標URL；有同期間多次更新。 | 這是文件索引，不是30篇原文或完整逐字稿。30日內新聞只有2列，且含代子公司公告；不能繞過8／3／30或獨立publisher門檻。後續須逐件取得合法公開原文及核對scope。 |

同源[單一公司借券](https://www.twse.com.tw/IIH2/zh/company/sbl.html?code=2610)先前已完整取得1826bytes／0.3095秒，可提供股票代碼、法名及官網；但沒有統編或出表日期，不替代本轮CAL完整名冊anchor，查詢range也不冒當出表日。price到10/13，而sell／sellAll／diff／lend只到10/12，須各序列保留自身日期。兩個MOPS app／renderer回HTTP200卻是800bytes安全限制HTML，維持blocked而非有效renderer；商工API公告要求來源IP白名單，未註冊、寄信或繞過。

20:23:46正式rolling24h仍15/20原類別各嚴格>80%。未達：alternative_data12/15（恰80%亦不算通過）、earnings_call17/39、financial_statements21/31、institutional_trading49/82、recent_catalysts65/110。相較先前11/20的提升來自舊觀測自然離窗，不能歸因CAL patch或本批研究；全部20類目標仍未完成。原成功率分母、quality gate及失敗事件保留。

證據：[完整資格化與數值比對](evidence/source-acquisition/20261013/twse-infohub-free-entry/qualification.json)、[正式24h](evidence/source-acquisition/20261013/twse-infohub-free-entry/formal-24h-readback.json)、[程序及141檔保持](evidence/source-acquisition/20261013/twse-infohub-free-entry/runtime-preservation.json)。下一個實作優先項是13月營收的有界typed備援；法人另找完整股數入口，events只供原文發現，不降低正文驗證。

新InfoHub研究獨立覆核完成，18組receipt/body與完整CSV三點逐值核對，無未解material finding；此覆核只確認研究原件與接入限制，未核准正式provider admission。見[獨立研究覆核](evidence/source-acquisition/20261013/twse-infohub-free-entry/independent-review.json)，SHA `76adefa95b269df41562085e8fde4dee1c708e2153ab88d425b9ac84000a6998`。

### 2026-10-13 20:47 續找：合庫、中再保及雙鴻完整法說原件入口

針對當日法說仍只有metadata的5880、2851及3324，新增三條發行人原件發現路徑。此批共19次普通匿名原生GET，18次完整HTTP200、1次康舒首頁HTTP403；包含索引、JS及職缺入口探索，不是19個有效資料來源。保持TLS、單次5秒／connect2秒、無登入／cookie／重導／自動重試；PDF單件上限8MB，其餘沿研究讀取器上限。共七份PDF完整bytes及SHA、HTTP收據、文字擷取結果留存，但「完整下載」與「完整內容理解」分開。

| 入口 | 已取得與核對 | 適用範圍及剩餘缺口 |
|---|---|---|
| [合庫金2026年第二季法說](https://www.tcfhc.com.tw/investors-relations/event/2026year/2026q2) | 官方頁明示2026-08-31場次及同日版本問答摘要。簡報2,096,200bytes／36頁／1.434秒；問答258,127bytes／10頁／0.496秒；native文字無空頁／garbled頁。 | 問答是發行人整理摘要，並非逐字稿；金控、本行、子公司及預測語句需各自標示。簡報第2頁限制未授權重製／傳送，暫留原件連結。問答原件適合作為後續內容備援候選，尚無正式adapter或全頁視覺驗證，不能當五年經審計財報。 |
| [中再保115年法說專頁](https://www.centralre.com/content/information/investorconference115.htm) | 由官網information06.htm實際發布的年度連結找到三份PDF，均完整HTTP200；封面日期3/27、5/29、9/4，分別35／34／34頁，每份1.88–2.06MB、3.70–4.17秒。股票2851與公司名、當日官方主檔一致。 | 搜尋引擎舊頁顯示112年，不能據此判斷2026不存在。三份原件仍有2／3／3頁native garbled標記，且第2頁明列不得轉傳第三人／重製出版；保持連結候選，不把簡報接成完整逐字稿或送入報告prompt。9/4不是30日內新聞。 |
| [雙鴻新版公開法說API](https://www.auras.com.tw/CmsApi/api/Unit/getUnitContentAsync?UnitId=46&Keyword=&IsFront=true&IsList=false&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true) | 已知新版官網平台上的新法說內容路徑。沿保存的公開導覽列unitId46、原生GET方法及前端預設參數取得78,550bytes／1.927秒；中文57附件列、英文48附件列，各含2026年17列。同group57的9/4場次中英PDF各15頁、1,494,404／1,435,123bytes、3.670／3.271秒。 | 附件列不是不同內容或獨立publisher；未下載全部105列。場次日9/4、封面8月、財務2Q26、API createDate9/10分開。末頁「Q&A」僅結束投影片，沒有問答正文。native reader回complete，但第8頁實際78%等圖表數字未擷取，不能升格完整視覺覆蓋。第12頁中英營收8,700,121、淨利1,038,861（仟元）與EPS10.41元一致，並核對中文渲染；這是同發行人兩語版本一致，非獨立財報證真。 |

2883與2887職缺探索沿用先前成果：凱基官方Workday兩個合格近期母公司職缺的adapter已於17:45部署，不冒稱本輪新發現；原缺件2883取得時間早於該部署。實讀`_fresh_epoch`為86400秒，並非摘要推測的1800秒身分門檻，故沒有據此改TTL。台新自有平台companyidstring33明示台新新光金控，但先前15列中存在舊日期及跨子公司實習，不能直接轉成近期母公司職缺。合庫徵才頁主要為子銀行／證券；銀行甄試報名期3/2–4/8已過，不能算金控本體目前職缺。康舒首頁403維持失敗，未繞過。免費公開讀取不等於開放再授權。

公司主體重驗沿同日既有完整主檔：TWSE CSV1095列／出表1151013，2851中央再保險股份有限公司／11081991及5880合作金庫金融控股股份有限公司／53021433；TPEx完整893列／出表1151012核3324雙鴻科技股份有限公司／16619628。只重讀原bytes並核SHA及原epoch，未續期或seed正式快取。研究初次PDF輸出腳本誤用page而非page_number，及離線收據核對遇康舒根URL自動補斜線，均以同份原件修正讀法，沒有重新HTTP或改403狀態。

**20:47:30台灣時間正式rolling24h仍15／20類嚴格>80%**：未達alternative_data12/15（恰80%）、earnings_call17/39、financial_statements21/31、institutional_trading49/82、recent_catalysts65/110。19次研究下載沒有寫入正式成功率、provider cache或舊報告；本輪runtime修改／重啟／來源補件POST／模型呼叫均0，原141檔及env hash保持、原launcher／worker／API持續運作，health／ready200。未宣稱背景排程沒有活動，亦不宣稱報告品質已修復。

下一個可實作切片優先是合庫問答摘要及雙鴻公開附件的exact-issuer內容備援，保存原索引、場次／財季／語言、bytes／hash／取得時間，限制在可驗文字或逐圖取得證據的範圍。中再保保留發行人連結並另找可自動採用的內容；不以附件數、圖表漏值或索引createDate降低原品質門檻。財報、法人精確股數、近期新聞與金控本體職缺仍有缺口，整體80%目標未完成。

證據：[完整資格及收據](evidence/source-acquisition/20261013/holding-free-entry/qualification.json)、[可離線重驗腳本](evidence/source-acquisition/20261013/holding-free-entry/verify-research.py)、[正式20類](evidence/source-acquisition/20261013/holding-free-entry/formal-24h-readback.json)、[runtime保持](evidence/source-acquisition/20261013/holding-free-entry/runtime-preservation.json)。


## 2026-10-13T21:34:37.930912+08:00 合庫金5880官方問答免費入口正式補件

沿前輪已找到的[合庫金2026Q2法說官網](https://www.tcfhc.com.tw/investors-relations/event/2026year/2026q2)，新增`market_sources.tcfhc_conference`與有界原生transport。完整TWSE CSV綁定法名／統編53021433／官網，再由年度索引、8/31 14:30場次頁及其exact QA連結取得原始PDF；檔案版本8/31、內容期2026Q2、事件時間及首次發布未知各自保存。10頁native文字可重播，不是假定逐字稿、已獨立證明舉行、完整視覺理解或已核實預測。金控／本行／子公司與預算展望保持語意；角色3／5／12取得最多6000字的有頁碼摘錄，原件私有憑據不進prompt。

本輪主隔離220與獨立335項通過（重疊不相加）。獨立六組P2先實際重現再修：根層公司名稱衝突／alias型別、假PIT/finality憑据旗標、鎖等待超過總deadline、force旗標漏傳、dict欄位誤算資料筆數、讀可用但寫失效仍連續HTTP。最終以原有shared singleflight保護4個HTTP，force保留active raw／provider冷卻；HTTP前source-local120秒reservation必須set/readback，儲存不可寫則0HTTP，HTTP後失效仍擋立即重打。原raw TTL1800不續期，暖cache不算新成功，來源每次至多一份問答，不是4 HTTP或16欄位。沒有放寬任何既有品質門檻。

正式以start_mac.command正常重載7 owned／136 held＝143 runtime，env與158套件保持；health／ready200。舊零資料ledger完整prefix保持，沒有手動清quota／cooldown、刪job、調scheduled score、強殺或commit/push。本次重載前待執行0；上次release的4個待執行項已在本次變更前自然結束：3 done，5314.TWO因原報告契約／證據品質gate為error，未隱藏或重設。

對既有`5880_TW_v4_report_job_f2ef907bcb49.html`只送一次earnings_call來源補件，HTTP200／4.3546秒／4次原生請求，原metadata-only正文0頁→10頁QA。正式provider_sla_event451453為success／record_count1，單次project acquisition恰1成功／1attempt。完整保存原件再重播核對，HTML／Markdown、分析evidence、五個原品質metadata、quote／年度歷史／其他來源、所有job及checkpoint保持；analysis_text_stale=True、模型0，未宣稱整份舊報告品質已恢復。

**當前原20類仍15類嚴格>80%**；法說17/39→18/40＝45%，另外alternative_data12/15恰80%、financial_statements21/31＝67.74%、institutional_trading49/82＝59.76%、recent_catalysts65/110＝59.09%。全目標未完成；沒有把隔離research、warmcache、新類別、重抓健康來源或平均數計入達標。下一個可驗證切片仍是雙鴻新版公开法說原件，保留圖表抽字缺漏／兩語同來源限制；中再保仍保持限制原件連結，另找可依法自動採用的內容。

證據：[正式補件與保持](evidence/source-acquisition/20261013/tcfhc-qa-integration/formal-source-refresh-verified.json)、[独立覆核](evidence/source-acquisition/20261013/tcfhc-qa-integration/independent-review.json)、[正式重載](evidence/source-acquisition/20261013/tcfhc-qa-release-proof.json)、[本輪結案／持續目標](evidence/source-acquisition/20261013/tcfhc-qa-integration/closeout.json)。


## 2026-10-13 雙鴻免費法說附件：正式補件及 PDF 逾時修正

已將雙鴻3324.TWO官網法人說明會的完整附件API接入來源流程。櫃買中心完整公司主檔核對法名、統編16619628及登記官網；索引選出2026-09-04場次、2026Q2中文簡報，15頁原生文字可重播。同日兩場資訊保留，groupNumber只作確定性選擇，不推定活動先後；封面2026-08、附件標題日期、財季及無時區的9/10資料列建立時間分開，不冒充首次發布或實際舉行證據。第8頁圖表百分比缺少原生文字，保持partial視覺覆蓋；末頁Q&A並無回答正文，不當逐字稿。主要財季必須來自主欄，不可由比較欄推定；原件TTL在最後PDF重播後再查。

隔離native探測3 GET皆200，7.55秒取得完整原件，不seed正式cache/SLA。正式第一次單來源刷新10.29秒回502，PDF超出原5秒上限，事件451455仍為error/0資料；HTML、Markdown、snapshot及原品質門檻保持。以可重現6秒PDF測試先RED再修，只將Auras中文PDF單次上限改8秒，其他來源/索引/主檔5秒、connect2秒、流程總20秒、3MB、無重試/重導、120秒冷卻與單一抓取鎖保持。

兩次限定重載皆走start_mac.command；最終145個runtime檔、env、158套件、既有zero ledger保持，health/ready200；沒有手動改jobs/排程或commit/push。原冷卻自然到期且修正通過覆核後，第二次刷新9.84秒HTTP200，3次native GET與15頁原件核對成功，只新增一筆canonical來源成功451457。報告3324_TWO_v4_report_20260929_093913.html由2025-12-16 metadata-only補為本次原件，原結論、其他來源、分析證據及品質警示保持，analysis_text_stale=true；沒有模型重跑。兩次正式POST一失敗一成功均保留。第二次PDF約2.46秒取得，這次成功不能單獨證明延長上限是成功原因或已長期穩定。

來源整合主測374/獨立383；PDF預算修正主測311/獨立202，重疊不相加。首次主回歸曾因錯列不存在test檔而0tests，獨立探針也曾誤用UBN欄名，均保留原log、修正測試後再驗，沒有掩蓋產品失敗。

最後原20類rolling24h仍15/20嚴格超過80%；未達者：職缺12/15=80%、法說19/42=45.238%、財報21/31=67.742%、法人49/82=59.756%、近期事件65/110=59.091%。研究、cache、HTTP數及重複健康刷新不計入新成功，整體目標未完成。

證據：[本輪狀態與限制](evidence/source-acquisition/20261013/auras-conference-integration/closeout.json)、[正式補件](evidence/source-acquisition/20261013/auras-conference-integration/pdf-timeout-fix/formal-source-refresh-verified.json)、[首次失敗保持](evidence/source-acquisition/20261013/auras-conference-integration/formal-source-refresh-verified.json)、[來源覆核](evidence/source-acquisition/20261013/auras-conference-integration/independent-review.json)、[PDF預算覆核](evidence/source-acquisition/20261013/auras-conference-integration/pdf-timeout-fix/independent-review.json)、[最終重載](evidence/source-acquisition/20261013/auras-pdf-timeout-release-proof.json)。


### 2026-10-13T23:00:30.002464+08:00：官方法人鏡站准入與華航主檔備援

證交所[官方鏡站](https://wwwc.twse.com.tw/zh/trading/foreign/t86.html)的完整 T86 已原生取得 1,341 列，與主站 parsed rows 全數相同；兩份原文各 195,936 bytes，hash 不同，不宣稱逐 byte 相同或增加獨立 publisher。現有 transport 本來會在主站傳輸失敗後改用鏡站，但 admission 漏列該精確 HTTPS URL。本次只補 exact path/day/query 准入，22:30 post_cutoff、原 bytes/hash、三法人分項股數及 finality/PIT 限制不變。四股票原件重播鏡站 before False→after True，主站保持 True；研究不入正式 SLA，也不等於完整 30 日窗口。Root 175 passed／1 明示排除的既有失敗，獨立 124 passed；原失敗是 before/current 同樣發生的完整 dict 比較，不改舊測試或品質 gate。

華航第二次來源補抓仍在 CSV 主檔逾時：451459 error/0，約 5.246 秒，原 snapshot/HTML/Markdown 及舊失敗保持。另查[政府免費公司資料](https://data.gov.tw/dataset/18419)連結的[證交所 OpenAPI](https://openapi.twse.com.tw/v1/swagger.json)，完整 JSON 主檔原生取得 1,327,580 bytes／1,095 列／7.131 秒，原五秒 probe timeout 保留。新主檔出表 1151012，舊 CSV 原件 1151013；華航名稱／代號／統編／英文／官網吻合，日期保持原值、不升格首次公布或財報期間證據。僅華航 bridge 在 CSV timeout/transport_error/server_error 後，允許一次精確 JSON URL 備援；401/403/429/cooldown、格式／身分錯誤不切換。JSON 上限 10 秒，其餘 5 秒、connect 2 秒、共享 45 秒、大小／TLS／原件／無重導無自動重試／host cooldown 不变；不新增來源快取。完整新原件保存於隔離研究與fixture，未 seed 正式 cache。Root 165 passed，獨立 148 passed（均含相關／必要檢查，重疊不相加）；原 CSV 五年科目與新 JSON 路徑一致，失敗 component 留存，25 個底層 HTTP 仍不是 25 次來源成功。

兩個 slice 已以 start_mac.command 套用正式服務，最後 2 owned／144 preserved＝146 個追蹤 runtime 檔、.env／158 套件保持；health/ready 200，原 job、排程、失敗與零筆 ledger prefix 保持。RQ 當時沒有執行或待排工作；worker 首次等待未退出，API stop guard 阻擋，後續只等同一 PID 正常退出，沒有再送 signal 或 force kill；實際退出延遲原因未另外診斷。

唯一修正後正式財報補件 HTTP200／15.114秒／24底層HTTP，451461 success/5，`2610_TW_v4_report_job_bd9994877f11.html` 由2022–2025四年補為2021–2025五年／45必要科目，完整原件可重播，只增加1 canonical成功。**這次正式主 CSV 自然恢復，JSON_master_used=False；不能把成功歸因新備援，也尚未觀測正式完整 JSON 備援流程。** 原本文、分析輸入、五品質 metadata、價格／TTM／其他來源及核心取得epoch保持，analysis_text_stale=True；沒有模型呼叫或新全報告品質結論。

原20類當前15類各嚴格>80%；未達：alternative_data 12/15=80%、earnings_call19/42=45.238%、financial_statements22/33=66.667%、institutional_trading49/82=59.756%、recent_catalysts65/110=59.091%。研究／cache不灌分，既有失敗不移除，整體目標仍未完成。見[本輪正式驗證](evidence/source-acquisition/20261013/institutional-financial-followup/closeout.json)、[鏡站覆核](evidence/source-acquisition/20261013/institutional-financial-followup/mirror-admission/independent-review.json)、[主檔覆核](evidence/source-acquisition/20261013/institutional-financial-followup/cal-master-fallback/independent-review.json)、[正式五年補齊](evidence/source-acquisition/20261013/institutional-financial-followup/cal-master-fallback/formal-source-refresh-verified.json)。


2026-10-13 23:36 法人來源單項补抓已部署：`institutional_source_refresh.py`、`report_source_refresh.py`、`data_fetch/service.py`沿原FinMind30日觀測及TWSE T86／TPEx dailyTrade官方原件核對，新增post-cutoff身分一致的來源單項更新；仅此來源force_refresh=False，依既有v2日期／phase共用全市場原件，不續原epoch、不把cache當新成功。30日×3分項整數股數與重算摘要、最新官方bytes/hash/精確URL/日期/市場及原TTL均通過才存入，原value/audit封存，其餘来源與股價／財報epoch、HTML/Markdown、analysis_evidence及五品質metadata保持，analysis_text_stale=True。

23份實際缺件各補一次全部HTTP200，最新日均2026-10-13、完整30日；兩市場共下載10份官方全市場原件供115次逐檔使用，其中105次保留原epoch的cache使用。其餘21件API回應0.650–1.520秒、中位0.976秒；第一上市16.724秒、第一上櫃10.018秒，未宣稱只由cache造成所有速度差異。TPEx institutional OpenAPI有一筆unavailable451485，既有dailyTrade備援成功；原失敗完整保留。原生HTTP確切旗標共11，FinMind primary實際HTTP總數未完整觀測，不以來源觀測替代。

Root126、獨立162隔離檢查通過（有重疊不相加），3owned／144preserved共147runtime由start_mac.command正式重載；環境、158套件、所有既有job、原零資料ledger prefix、health/ready200核對，來源補抓模型0，無commit/push。本輪同一24h移除23個fetch IDs比較：法人33success／34attempt，其餘19類逐欄相同。全系統仍15/20類嚴格>80；法人由49/82=59.756%至82/116=70.690%，其餘未達為另類12/15=80%、法說19/42=45.238%、財報22/33=66.667%、近期65/110=59.091%。完整30日觀測不等同全期逐日官方獨立認證；只補來源不代表新報告品質過關。FinMind自然恢復不歸因patch。見[實際補件與目前驗證](evidence/source-acquisition/20261013/institutional-post-cutoff-followup/closeout.json)、[同窗口歸因](evidence/source-acquisition/20261013/institutional-post-cutoff-followup/same-window-attribution.json)及[独立覆核](evidence/source-acquisition/20261013/institutional-post-cutoff-followup/source-only/independent-review.json)。


### 2026-10-14T00:12:02.811223+08:00 台達電官方免費英文逐字稿已補入正式來源

[台達電官方法說索引](https://www.deltaww.com/en-US/investors/analyst-meeting)發布[2026第二季英文逐字稿](https://filecenter.deltaww.com/IR/download/calendar/2Q26_Transcript.pdf)，會議日2026-07-30。新增 `data_fetch/market_sources/delta_conference.py` 與 transport，股票2308／當期完整官方CSV／法名統編／官網身分、最新已完成會議與精確附件路徑、封面期別日期與中文原音優先聲明逐一綁定。原生三個匿名GET、每次5秒/connect2、總20秒，無重導或自動重試，原件1800秒TTL、lock／guard、bytes/hash均保持；研究原件不seed正式cache或SLA。

PDF原本13頁均有嵌入字體CMap缺損；只對這份完整PDF SHA與兩個FontFile2／原CMap SHA、Identity CID及已目視原字形的ft/tf/ti/tt，作記憶體解碼並留下原/解碼CMap與CID證據，檔案bytes不改。未知PDF、字體或原件不匹配仍拒絕，不以拼字猜測放寬門檻。13頁原生文字取得完整，但英文稿依中文口述編製，官方明示可能翻譯錯漏，原中文優先；translation_accuracy_verified=False、full_content_coverage_verified=False，role prompt每次最多200英文words並保留限制。

獨立覆核3項P2均先重現後修正：新場次尚無任何附件也不能悄退舊稿、未知文件的dict/list標記不讓共用prompt TypeError、MOPS備援回傳須標示真正來源且保留Delta失敗component。289項相關隔離測試通過；獨立三種source-only篡改文字／翻譯聲明／原件receipt皆502且HTML／Markdown／snapshot逐byte保持。獨立結果詳見收據，重疊不加總；probe自身中文轉義錯誤的失敗log也保留，修fixture後乾淨跑次另列。

10 owned＋140 preserved＝150追蹤runtime檔由start_mac.command正式重載，.env／158套件及舊失敗保持，healthz／readyz200。對實際缺口 `2308_TW_v1_report_20261009_015945.html` 只執行一次既有earnings_call來源刷新：HTTP200、3.714秒、3次底層HTTP，從WebPro僅日期連結補成13頁官方原稿，可重播原件。只記1個canonical來源取得（event IDs [451497]），沒有新模型呼叫；股價／TTM／其他來源／HTML／Markdown／舊分析與五品質metadata／所有jobs及checkpoint保持，analysis_text_stale=True，不宣稱新報告品質已通過。

同一24h排除本次fetch ID只減去法說1 success/1 attempt，其餘19類計數一致；原零資料ledger保持，rolling自然離窗不歸因程式。當前仍15/20類各嚴格>80%，未達：alternative_data 12/15=80.0%、earnings_call 20/43=46.512%、financial_statements 22/33=66.667%、institutional_trading 82/116=70.69%、recent_catalysts 65/110=59.091%。整體目標未完成，後續只補真實缺件，不以暖快取、研究結果或重抓健康來源灌分；無commit/push。

證據：[本轮部署與當前狀態](evidence/source-acquisition/20261013/delta-transcript-integration/closeout.json)、[正式補件](evidence/source-acquisition/20261013/delta-transcript-integration/formal-source-refresh-verified.json)、[獨立覆核](evidence/source-acquisition/20261013/delta-transcript-integration/implementation/independent-review.json)、[同窗口歸因](evidence/source-acquisition/20261013/delta-transcript-integration/same-window-attribution.json)。


### 2026-10-14 凱基金官方職缺來源單項補件

沿既有[凱基金官方 Workday 公開入口](https://cdfh.wd3.myworkdayjobs.com/zh-TW/External?hiringCompany=39d77424bb861000fb161fa41a5e0000)，新增 alternative_data 單來源刷新，精確雇主與股票 EQUITY 身分、逐筆原文及日期收據核對後才替換該來源。沿用原1800秒原件與既有cache/cooldown；純徵才新聞不能冒充職缺、暖快取不算新取得。獨立覆核先重現供應商外層失敗被內層成功蓋過、異常巨大數字使失敗帳本中斷兩群P2，修正後root165與獨立269項通過，含必要runtime/storage21，重疊不相加。

3 owned＋148 preserved＝151 runtime檔由start_mac.command部署；環境與158套件保持，health/ready200，RQ正常停止後重載，無強殺、清冷卻或修改排程。本輪正式既有2883_TW_v4_report_job_c2577fa8f6e1.html缺口只POST一次，HTTP200／16.9603秒，取得2筆官方母公司職缺（JR106341、JR106307），原清單11筆不當已驗證近期職缺數。官方Workday leg為3次HTTP，primary來源HTTP總數未完整觀測。原HTML/Markdown、分析證據／五品質metadata、價格／TTM／其他來源與原epoch、所有jobs/checkpoints保持；analysis_text_stale=True，模型0，未宣稱舊報告品質已通過。

正式event451498為success/record_count2，但canonical只記1次取得。相同24h移除此fetch ID只減alternative1成功/1attempt，其餘19類逐欄一致，原失敗與zero ledger保留。另類12/15＝80%→13/16＝81.25%；原20類現16類嚴格>80%。尚未達：法說20/43＝46.512%、財報22/33＝66.667%、法人82/116＝70.690%、近期事件65/110＝59.091%。全目標仍未完成，沒有commit/push或把研究、暖快取、健康重抓算成正式成功。

證據：[本輪部署與正式驗證](evidence/source-acquisition/20261014/alternative-source-refresh/closeout.json)、[獨立覆核](evidence/source-acquisition/20261014/alternative-source-refresh/independent-review.json)、[同窗口歸因](evidence/source-acquisition/20261014/alternative-source-refresh/same-window-attribution.json)。

### 2026-10-14 證交所免費活動附件索引與全市場注意交易原件

從[證交所活動頁](https://www.twse.com.tw/zh/about/news/event/list.html)公開設定核對 `rwd/zh/news/eventList` 及 `eventDetail`，本次完整索引42筆；AI／綠能系列場次提供10份簡報連結，只實際下載其中奇鋐4/21一份PDF（4,144,324 bytes、10頁），不宣稱10份正文皆已驗。該PDF五頁無原生文字、五頁亂碼；目視只核對前兩頁，日期依官方年度／附件標籤，亦早於既有3017報告8/12場次，因此不以舊簡報替換最新metadata。三個較新場次目前只有議程連結，沒有簡報下載欄位。

[證交所注意交易頁](https://www.twse.com.tw/zh/announcement/notice.html)公開全上市市場查詢，一次取得2026-09-14至10-14完整381列／123種證券／19日群組，98,397 bytes、0.233秒。包含權證及TDR，不是123家公司或全上市櫃。全市場「編號」為日期群序、「累計次數」為該日群筆數，與個股查詢欄位不同；股票、名稱、日期、正文、價格及PE才是四份原件實際比對一致的欄位。這個入口仍為研究候選，尚未接入正式全市場快取。原24h的15檔空公告股票在完整原件也都沒有資料，空缺保持。

原件另揭露既有個股parser只接受第十一款紅字標記，導致第九、十、十二、十三款的真實公告被拒。本輪只擴充五個精確官方標記、保留條款文字，未知HTML／entity／身分／query／原件hash與TTL仍照原規則拒絕。四份逐股完整原件先RED（4 failed、6 passed），修正後相關163項及獨立103項隔離測試通過（重疊不相加）。純文字重播同批381列由280可讀到381，恢復101列／57種證券；這不是全市場provider准入或新增正式成功。

已由start_mac.command套用一個runtime檔、保持其他150檔，env／158套件、所有既有job、零資料ledger、排程與health/ready200驗證。新launcher23375／worker23403／API23405，沒有force kill、額外模型呼叫、健康報告重抓或commit/push。研究21次原生HTTP皆取得回應，另有AVC挑戰頁與Unitech無公司內容頁，HTTP200不當取得資料；Voltronic只有MOPS／YouTube連結，未當法說正文。沒有seed正式cache，研究與parser修正新增正式取得0，ledger仍451498。

目前原20類仍16類嚴格>80%；法說20/43＝46.512%、財報22/33＝66.667%、法人82/116＝70.690%、近期65/110＝59.091%未達。後續優先尋找這四類的當期完整原件，維持缺件及實際取得口徑。證據：[本輪部署與限制](evidence/source-acquisition/20261014/remaining-free-entries/closeout.json)、[入口及完整收據](evidence/source-acquisition/20261014/remaining-free-entries/qualification.json)、[獨立覆核](evidence/source-acquisition/20261014/remaining-free-entries/notice-markup-fix/independent-review.json)、[原20類讀回](evidence/source-acquisition/20261014/remaining-free-entries/goal-readback.json)。


### 2026-10-14 續找：大東電完整免費英文簡報優先候選

由[大東電股東服務](https://tewc.com.tw/investor/shareholder/)實際發布的115/05/27 13:30法說資料，追至公開Google Drive中英文附件；兩個viewer原件連出的uc網址均先得到原生303，再按原Location人工逐段取回，無登入、API key、代理、自動重導或自動重試。沿前輪完整TWSE主檔原bytes／SHA／原epoch重驗1623／大東電業廠股份有限公司／18523000／TEWC／tewc.com.tw，沒有重取或續期。

**英文版是較佳的新入口**：[官網發布的英文檔](https://drive.google.com/file/d/1Bwvj4q4IFxlah18p5F7HTPTQvPmMPEwq/view?usp=sharing)完整16,076,336 bytes／48頁，原現行source_pdf_reader不做任何例外即讀得16,500字、空頁0／亂碼0；原檔SHA `4514db4ca2c720a5113298397baff01075175ff1ac4d16e1b9d23c2732a38c48`。封面1623／公司名／May 2026與官方場次月份一致，首次刊登及實際舉行仍未獨立證實。英文先有8MiB研究上限拒收，再有8秒逾時的11,206,429 bytes部分檔；確認原Content-Length後，只對同一URL做一次12秒上限研究下載，7.0405秒完成，舊部分檔是完整原件exact prefix。保留全部失敗，不以單次成功宣稱長期可靠，不更改正式下載預算。

中文檔16,245,274 bytes／48頁亦完整下載，但正式reader仍拒parser_warning。獨立核對三個classic xref、hybrid xref及六個ObjStm，2,801個壓縮物件索引與strict pypdf映射一致；其研究性警告診斷沒有接入正式程式。英文入口已不需這項例外，因此不為中文另開寬鬆解析。

兩份均只是prepared presentation，非逐字稿或完整圖像內容。英文p12比中文多出可抽取的827字，但p19／p34圖像內容仍缺；p29只有標題／單位／圖例，不能推算逐期訂單；p22明示「以6.6億推算EPS」，不得替代法定EPS／TTM。財年與Q1須區分，所有展望保留公司說法。**尚未正式接入**：兩份檔案均超過現有8MiB原件archive/readback上限；需另做有界大原件儲存與重播、日期／主體鏈及partial內容投影，再驗正常provider與單項補件。本輪未放大上限、未seed正式快取、未改品質gate。

另沿[健策官方法說索引](https://www.jentech.com.tw/zh/institutional-investor-conference-information)實際發布的301 Location，取得2025/11/28同場次中英兩份24頁原件（2,614,119／2,735,790 bytes）；仍有6／7頁native亂碼，且原件標confidential及重製限制，保持官方連結候選、不自動送prompt。康舒www.acbel.com.tw原生403保留，沒有繞過。凱基原2021／2022財报已知無形資產現金支出缺欄未被新搜尋證實補齊，沒有盲抓同件或填零。

本輪16次native研究HTTP（另有web搜尋／讀頁不列入），四份完整PDF不等於四次正式成功。中文結構研究隔離44項、英文獨立補充4項通過；151 runtime、環境與158套件、三個正式PID保持，health/ready200，source ledger最大451498不變。原20類仍16類嚴格>80%；法說20/43=46.512%、財報22/33=66.667%、法人82/116=70.690%、近期事件65/110=59.091%未達。無新模型／報告請求、部署、commit或push。

證據：[本輪結果](evidence/source-acquisition/20261014/continued-free-entry/closeout.json)、[完整下載及資格](evidence/source-acquisition/20261014/continued-free-entry/qualification.json)、[英文獨立覆核](evidence/source-acquisition/20261014/continued-free-entry/independent-english-review.json)、[中文結構覆核](evidence/source-acquisition/20261014/continued-free-entry/independent-research-review.json)。


### 2026-10-14 大東電免費英文法說正式接入並補抓成功

已接入[大東電股東服務](https://tewc.com.tw/investor/shareholder/)發布的2026-05-27英文法說附件，核对官方主檔、當期活動表、Drive viewer、原生303空本文與Location、完整PDF五段證據。16MiB僅明確允許此大原件，其他封存預設8MiB不變；1800秒TTL、120秒失敗冷卻與共享單次抓取保持，交付時再次統一核對五份原件期限。無中文xref例外、代理、登入、API key、自動重導或自動重試。

正式缺件報告1623_TW_v3_report_20260929_092952.html原earnings_call={}，source-only POST一次，HTTP200／7.803秒，取得16,076,336bytes／48頁英文原件，SHA與研究完整原件相同。五個HTTP組件（200、200、200、303、200）只記正式事件451499一次有資料成功；沒有研究fixture灌入正式cache或新模型／完整報告請求。HTML、Markdown、核心資料原取得時間、analysis_evidence、五個品質gate及其他來源audit逐項保持，analysis_text_stale=True，不能視為新分析報告通過。

仍標示presentation／partial、非逐字稿或已核對英文翻譯；p19／29／34圖像缺漏、p22「以6.6億推算EPS」與content_period=None保持。英文角色可依財務／市場／策略詞彙選頁，內部原件憑證排除於prompt。相關回歸150passed；獨立266passed含required21，彼此重疊不加總。獨立審查發現的最早原件於最後PDF讀回過期P2已修並保存RED反例。正式入口已重載9個變更檔、保留145個其他runtime及.env／158套件，health/readyz200，原失敗紀錄保持。

原20類仍16類嚴格>80%；法說21/44=47.727%、財報22/33=66.667%、法人82/116=70.690%、近期事件65/110=59.091%，全部類別目標未達成。證據：[交付](evidence/source-acquisition/20261014/tewc-conference-integration/closeout.json)、[原件鏈](evidence/source-acquisition/20261014/tewc-conference-integration/formal-original-chain-readback.json)、[報告保全](evidence/source-acquisition/20261014/tewc-conference-integration/formal-source-refresh-verified.json)、[獨立覆核](evidence/source-acquisition/20261014/tewc-conference-integration/implementation/independent-review.json)、[部署](evidence/source-acquisition/20261014/tewc-conference-release-proof.json)。


### 2026-10-14 燿華法說與合庫金控五年英文財報／新聞新入口

沿最新真實缺口查新免費入口。本輪只做原件取得與資格化，未接入新provider、未部署、未改正式報告或研究seed。合庫金控[英文查核財報列表](https://www.tcfhc.com.tw/investors-relations/financial-info/financial-reports?sc_lang=en)明確發布2021–2025五個完整PDF，各一次native HTTP200，原件5,728,762／5,807,849／947,497／884,281／1,014,440bytes，頁數240／238／242／245／247。中文2022原件5,062,268bytes／255頁也完整取得，但前18頁沒有native文字；英文五份前20頁均可讀且無加密、strict parser未警告。研究核對已找到十項holding必要科目，2021現金流三科目與2022比較及中文原件相同。這不代表整份PDF或五年所有比較值已自動核驗；2024對2023總資產有修訂，2025金額與百分比文字可能黏連，必須以明確欄位與座標解析。英文版有中文優先聲明；production通用PDF100頁限制維持，未提高上限或直接採手抄數字。

[燿華官方法說片段](https://www.pcbut.com.tw/portal/IP/5/IN5_3.html)是由官網動態公司治理頁發布的入口；2026-06-26場次[原始簡報](https://www.pcbut.com.tw/downloads/InvestorConference2026.pdf)完整804,506bytes／16頁，原生文字無空頁或亂碼，但p3／5／9／10／11圖像資訊未完整取得，不能稱全內容覆蓋或逐字稿。p2有所有權／機密性文字，未宣稱開放授權。一般搜尋未必看到動態片段；保存完整原始HTML鏈，不執行或採納無關隱藏外部連結。

合庫金控[2026新聞列表](https://www.tcfhc.com.tw/news/message/news/2026)native HTTP200，首頁10筆；其中[2026-10-07母公司永續新聞](https://www.tcfhc.com.tw/news/message/news/2026/021-1151007)取得完整HTML與529字正文，主檔5880／53021433／TCFHC／登記官網相符。只新增一個publisher候選，沒有把銀行／壽險子公司新聞自動當母公司，首頁非全年完整列表；原8篇／3發布者／30天門檻不變。旭隼[官方投資人概況](https://voltronicpower.com/en-US/Investors/CompanyOverview)另有YouTube法說嵌入，但場次與逐字稿未確認，不能補作法說正文。

MOPS 5880現金流公開JSON研究請求HTTP200只有800byte安全性拒絕頁，停止該host後續研究，未改身分、proxy或重試；不當財報成功。法人原82／116中的34筆非成功原因保留；23個歷史降級股票的最新報告均已具30日／90分項，隔離重播27passed，無需補抓健康報告。原34筆含10個截止前空回應、23個截止前降級與1個已有同次備援成功的TPEx timeout。

本輪24次native研究HTTP，完整下載23個正常內容與1個拒絕頁；正式新增SLA／模型／完整報告請求0。154個runtime hash、環境、158套件及三個服務PID保持，health/ready200，ledger仍451499。原20類16類嚴格>80%；法說21/44=47.727%、財報22/33=66.667%、法人82/116=70.690%、近期事件65/110=59.091%，目標尚未完成。下一個適合實作的切片是合庫英文財報的有界選頁／座標科目與比較期重播，及母公司新聞collector；先建立行為反例，不放寬原件、scope、unit、來源多樣性或quality gates。

證據：[原始下載清單](evidence/source-acquisition/20261014/remaining-four-next/native-research-manifest.json)、[燿華資格](evidence/source-acquisition/20261014/remaining-four-next/unitech-qualification.json)、[合庫新聞資格](evidence/source-acquisition/20261014/remaining-four-next/tcfhc-news-qualification.json)、[財報缺口](evidence/source-acquisition/20261014/remaining-four-next/financial-candidates.json)、[法人獨立重播](evidence/source-acquisition/20261014/remaining-four-next/institutional-candidates.json)、[正式runtime與ledger](evidence/source-acquisition/20261014/remaining-four-next/runtime-and-ledger-readback.json)。

財報後續覆核已保存：[五年英文原件獨立資格](evidence/source-acquisition/20261014/remaining-four-next/tcfhc-financial-independent-qualification.json)、[本輪交付](evidence/source-acquisition/20261014/remaining-four-next/closeout.json)。原件共1,212頁；僅各前20頁選頁研究，現有正式reader實測仍以page_limit拒收，不能把研究值當已部署資料。

### 2026-10-14 合庫金控5880五年查核財報免費入口正式接入
合庫金控官網英文 Financial Statements 索引已提供2021–2025完整查核合併PDF。新 tcfhc_annual_transport／tcfhc_annual_financial 與專用有界PDF reader採7份完整原件（官方主檔、索引、5本財報），逐年核對10科目、次年比較欄與重編依據；金融業淨收益獨立於一般營收，保留母公司淨利／期末權益與金融業DCF限制。原件以新schema financial_holding_audited_annual.v1保存；原epoch／1800秒TTL、45秒總期限、既有冷卻與失敗紀錄保留，完整處理及batch退出後再次核TTL。英文與中文衝突時中文優先，僅聲稱指定完整原生財報頁可驗，不聲稱全書圖像及譯文皆已核對。

最終507項隔離通過、1項選用私有報告樣本略過；獨立覆核關閉最終handoff TTL P2，修正後35項獨立檢查通過。10 owned＋149 preserved＝159 runtime檔正常重載、health/ready200、.env及158套件保持。正式5880既有缺口只送1次財報來源刷新，14.000秒、7 HTTP、50當期＋50比較期明列事實成功，成功事件451500／5年度；2021 FCF由缺值補為57.997511十億元，其餘年度保留原始精度。HTML／Markdown、分析證據、品質metadata、quote／TTM原時間、其他來源、jobs及checkpoint保持，模型呼叫0；原報告仍需重分析，正常完整分析路徑僅隔離驗證。

此次讀回原20類16類嚴格>80%；財報23/34=67.647%、法說21/44=47.727%、法人82/116=70.690%、近期65/110=59.091%，目標未完成。接續候選是燿華2367官方2026法說、合庫金控親公司新聞與尚缺金融原件；不得重抓健康來源灌高SLA。完整證據見[接入與正式讀回](evidence/source-acquisition/20261014/tcfhc-financial-integration/closeout.json)。


### 2026-10-14 燿華2367法說與合庫金控5880母公司新聞正式接入

新增燿華[官方法說索引](https://www.pcbut.com.tw/portal/IP/5/IN5_3.html)及其2026-06-26完整PDF入口，以及合庫金控[官方新聞首頁](https://www.tcfhc.com.tw/news/message/news/2026)與逐篇原文入口。燿華使用完整當期主檔、索引、PDF三份原件，16頁原生文字保留；p3／5／9／10／11圖像資訊缺漏、p2所有權聲明、未知首次發布時間與混合財務期間保持明示，不當逐字稿或開放授權。合庫新聞核母公司5880／53021433，首頁10則只接1則明確母公司永續新聞；銀行、人壽與球隊消息排除，後段雙重職稱不能證明母公司事件。只新增一個TCFHC publisher，非完整年度或30天窗口。

本輪修正共享日期正規化後的原文誤拒、顯式異常context被當空值、warm正文搭配新索引HTTP的計數，以及原403／429／503在component的保留。原文bytes／hash／日期／URL／身分須可重播，當次原1800秒TTL與最後deadline保持；燿華25秒、新聞20秒總期限及單次5秒、既有cooldown無放寬。原8篇／3發布者／30天與品質gate保持。混合快取可正確供一般provider使用；既有指定新聞補件仍可能依HTTP0快取契約保守拒收，此限制未冒稱已改善。

Root相關22模組531 passed；獨立燿華／shared208與最終新聞／整合119通過，重疊不加總。已依start_mac.command部署11 owned＋151 preserved＝162 runtime檔，health/ready200，環境與158套件保持，原排程及工作狀態保留。正式只補2個既有缺口：2367補16頁簡報，HTTP200／2.089秒／3 native HTTP／事件451501；5880補529字母公司原文，HTTP200／1.991秒／3 native HTTP／事件451502（主檔沿原正式快取，非研究seed）。5880所有新聞桶24→25，原24筆仍保留；既有五年金融財報、其他來源與核心原epoch、HTML／Markdown、分析證據及品質metadata、jobs／checkpoint均保持，模型0。原報告分析正文未重生成，analysis_text_stale=True。

最新同一24h窗口仍16/20類嚴格>80%，法說22/45=48.889%、財報23/34=67.647%、法人82/116=70.690%、近期事件66/111=59.459%。只移除本輪2個fetch IDs比較，各補件類別success/attempt均+1，其餘18類完全相同；不把自然離窗或cache當改善。全部20類目標尚未完成。見[正式補件與全20類讀回](evidence/source-acquisition/20261014/unitech-and-parent-news/closeout.json)。


### 2026-10-14 全150份最新報告缺口盤點與新增免費入口研究

唯讀核對150個ticker的最新報告／snapshot（0讀取錯誤），再將金融業、ETF與一般企業的年度口徑分開。新增完整研究原件包含：凱基金控英文2022查核財報、大東電2024年5月公開說明書及2023財報、中砂2022中文合併財報與英文年報，共5份PDF。下載成功不代表已補齊科目，也不代表正式provider成功。

- [凱基金英文財報索引](https://kgi.irpro.co/en/financials.php)列2021–2025；本輪只完整下載2022年274頁原件，前20頁及現金流選頁核對，仍未找到gross無形資產現金購買科目，無法建立完整五年十科目橋接。
- [大東電官方財報](https://tewc.com.tw/investor/financial/)與證交所公開說明書另取得391頁未加密歷史定本。第181頁明示共同控制重組及2022重編；2022 CFO/PPE原值為-333,919/-50,144千元，重編後為-233,526/-50,063千元。2021缺同重編口徑，合併附錄132頁缺原生文字，2025個別報表不能直接接入合併序列；不實作跨口徑拼接。
- [中砂官方合併財報索引](https://www.kinik.com.tw/zh-tw/Investor/Consolidated.html)以公開inline資料提供下載路徑，一般文字搜尋可能只看到空頁。完整中文69頁／5,953,350bytes、英文年報288頁／5,692,151bytes均HTTP200；中文第14頁與英文第157頁目視比對相同CFO/PPE，但兩者都沒有無形資產購買列。英文需另建有界選頁才可自動消費，通用100頁上限未動；沒有以其他非流動資產或攤銷代替缺科目，也未盲重抓舊1560報告。
- [FinancialFilings官方API文件](https://financialfilings.com/developers/)提供免費帳號/key方案，500credits/月、5次/分鐘；明確免費Level1是metadata／文件URLs，全文Level2及財務KPI Level3權限未驗，不能由點數推定全文免費。康舒公開索引／PDF可由web工具閱讀，但首次native公開頁為403挑戰，停止後未取CDN或申請帳號。平台9/14發布日與公告9/15 13:30活動日分開。未找到自動化明示授權不等於禁止；實际停止依據是403。
- 聯電官方IR、台積電官方Q2頁、以及獨立SEC台積電12頁簡報申報入口各首次native403，均保留原拒絕頁，未重試、換身分或啟用來源。web可見正文／連結不當完整原生HTTP證據。

另以57份保存原件重播士電1503、東元1504及南電8046，其中45份完整三表JSON，隔離4passed。1503/8046各年度只有8/9科目；1504缺無形資產列且比較數真的有重編差異。未證實共通parser錯誤，保持拒收與缺值，不製造patch或填零。測試harness首輪選錯索引範圍的4 errors與修正後結果都保存。

本輪共16次native研究HTTP：11個200、1個303、4個403；5份完整PDF中一份Drive財報有加密權限限制，未解密。研究沒有seed正式cache／SLA，也沒有新模型或正式來源補件。162個已部署runtime檔、環境與158套件及程序保持，health/ready200，正式source ledger仍451502。原20類仍16类各嚴格>80%：法說22/45=48.889%、財報23/34=67.647%、法人82/116=70.690%、近期66/111=59.459%未達，整體目標未完成。此輪沒有可直接新增啟用的完整備援；後續需同口徑明列缺科目的原件，或完成免費API帳號/實際tier驗證，不能用研究下載灌分。

證據：[全部候選與正式狀態](evidence/source-acquisition/20261014/remaining-gaps-search/closeout.json)、[150份最新報告](evidence/source-acquisition/20261014/remaining-gaps-search/all-latest-report-source-gaps.json)、[16份原生收據完整性](evidence/source-acquisition/20261014/remaining-gaps-search/native-research-integrity.json)、[共通parser診斷](evidence/source-acquisition/20261014/remaining-gaps-search/parser-review/diagnosis-final.json)、[免費API層級補充](evidence/source-acquisition/20261014/remaining-gaps-search/financialfilings/access-tier-addendum.json)。


### 2026-10-14 富邦金／統一超商新官方全文與全市場公告共用查詢

新增兩個免費第一方全文候選，研究共7次native GET均完整HTTP200，未seed正式cache或計入SLA：

- 富邦金2881：[官方新聞列表](https://www.fubon.com/Fubon_Portal/financialholdings/news/list.jsp)連到[10/12 Run For Green原文](https://www.fubon.com/financialholdings/news/news_1261012_803022.htm)與[10/1 AI治理原文](https://www.fubon.com/financialholdings/news/news_1261001_844642.htm)，正文1531／1732字。完整主檔2881／03374805綁定官方domain，兩篇仍只算一個publisher；母公司與子公司段落須分別處理，CSR／治理消息未評估投資影響。canonical／OG是共用模板URL，不能替代實際index href／文章URL／日期核對。
- 統一超商2912：[ESG官方列表](https://www.7-11.com.tw/Company/esg/news.aspx)連到[10/12公布2026年9月合併營收](https://www.7-11.com.tw/Company/esg/news_detail.aspx?id=1140)，完整28,703bytes、正文1,461字，主檔2912／22555003吻合。首頁六筆非完整歷史；報告已有同事件媒體摘要，這是官方原文備援候選，尚未接入。
- 統一企業1216最新官方9/14文章已超過現有rolling30天且正文僅未下載圖片，保持不合格。2881／2912最新報告均已有8則近期新聞，不能說這兩份目前新聞數量不足，也不重抓健康報告灌分。

證交所[全市場注意公告入口](https://www.twse.com.tw/rwd/zh/announcement/notice?querytype=1&stockNo=&selectType=&startDate=20260914&endDate=20261014&sortKind=DATE&response=json)先前完整保存98,397bytes，381列／123個證券／19個日期群組，本輪用原件隔離重播，沒有重新下載或seed研究原件。舊逐股查詢改為全市場原件共用；實際ticker只取得其列，原件整體count／total／日期群組／query echo／每列內容皆驗證。注意公告不涵蓋全部公司事件，空結果仍unknown；全市場原件不含近期15個空查ticker，這次主要減少重複請求，不能補造公告或宣稱內容缺口已消失。

獨立覆核發現兩個P2：新receipt的HTTP矛盾／bytes不符，以及最後handoff漏核較短fresh_until。均保存RED反例後修正，原blocked收據不改寫。Root相關121通過、來源篩選／取得率顯示25通過；獨立最終123通過，重疊不加總。8秒總期限、5秒單次、250KB上限、原1800TTL與既有冷卻保持；較短有效期優先，historical replay與當次fresh admission分開。冷非空算實際成功，warm非空算快取，warm空算空快取；快取HTTP0，不算新抓取成功。

已依start_mac.command正式重載4檔，保留160個其他runtime檔／環境／158套件；health及ready200，pending／scheduled0，既有jobs與失敗列保持，無force kill。奇鋐3324診斷另證實已有後續451457成功及15頁正文，原451455仍保留；不再補健康報告。

本輪正式來源／報告／模型呼叫0，ledger仍451502。原20類仍16類各嚴格>80%，法說22/45=48.889%、財報23/34=67.647%、法人82/116=70.690%、近期事件66/111=59.459%，部署不等於實際取得率提升。下一切片是新官方全文collector；正式80%驗收仍需真實工作觀測，不能用研究或快取替代。

證據：[本輪交付](evidence/source-acquisition/20261014/news-conference-next/closeout.json)、[富邦資格](evidence/source-acquisition/20261014/news-conference-next/fubon-news/qualification.json)、[統一資格](evidence/source-acquisition/20261014/news-conference-next/uni-news/qualification.json)、[獨立覆核](evidence/source-acquisition/20261014/news-conference-next/market-notice-integration/review/review-final.json)、[正式部署](evidence/source-acquisition/20261014/twse-market-notice-release-proof.json)。


### 2026-10-14 南茂8150官方翻譯逐字稿正式接入

[官方法說索引](https://www.chipmos.com/english/ir/info2.aspx)公布[2026Q2英文翻譯逐字稿](https://www.chipmos.com/upfiles/ADUpload/english/en_pdf_1857263878.pdf)，完整680,428bytes／8頁，會議日2026-08-11 15:00台北。完整主檔核8150／南茂科技股份有限公司／16130042／ChipMOS／登記官網。第7–8頁免責聲明保留；翻譯、原音、公司陳述及視覺完整性未獨立驗證，首次發布時間未知，展望不得當已實現結果。

新增精確原件限定的private-child reader，核全部68個xref與唯一header後僅移動單一LF cursor；原件不改寫，其他警告及CPU／RSS／stream／time上限保持。三收據須完整重播，原1800秒及較短expiry綁回獨立保存的相同bytes與原epoch；25秒耗盡即typed timeout，不再開新index fallback。兩項獨立P2（延長較短期限、逾時後storage錯誤啟動fallback）均有RED與closure。Root最終176pass含必要21；獨立19與37pass及先前仍有效證據分開保存，不加總重疊數量。

正式更新10owned＋158preserved＝168runtime，環境／158套件保持，health／ready200。只對缺正文的8150報告補一次：HTTP200／4.2547秒／3 native GET，事件451503只計一次取得，保存8頁。HTML／Markdown、分析證據、品質metadata、其他來源及原時間、jobs／checkpoints保持，模型0，analysis_text_stale=True，分析正文尚未重生成。

05:04台北原20類仍16類嚴格>80%；同窗口只移除本次事件對照，法說22/45→23/46=50%，其餘19類相同。財報23/34=67.647%、法人82/116=70.690%、近期66/111=59.459%也未達。研究9次GET（8完整200、1不完整timeout）不進SLA、不seedcache；另取得2022合併財報66頁仍缺2021 gross無形資產購買，未填零或混接口徑。6257／2344／1216／2882仍是缺正文候選，未宣稱已取得。

證據：[本輪結案與未達目標](evidence/source-acquisition/20261014/source-gap-priorities/closeout.json)、[正式讀回](evidence/source-acquisition/20261014/source-gap-priorities/chipmos-integration/chipmos-formal-verified.json)、[獨立覆核](evidence/source-acquisition/20261014/source-gap-priorities/chipmos-integration/review/review-final.json)、[研究收據](evidence/source-acquisition/20261014/source-gap-priorities/chipmos-source/qualification.json)。


### 2026-10-14 華邦電免費法說正文已接入，另外三個候選已核對

華邦電2344的[官方法說索引](https://www.winbond.com.tw/hq/about-winbond/investor/investor-conference/?__locale=zh_TW)及其直接發布的[2026Q2中文簡報](https://www.winbond.com.tw/export/sites/winbond/about-winbond/investor/investor-conference/2Q26-investor-conference_CH_Final.pdf)已接入。完整原件1,759,017bytes、SHA256 `8fea53d7b591124ce63c2ae1ae623d9494fece1dd052979812b75f166cc1ff3a`，通用有界reader讀出31頁，無空白或未知字元頁；整體仍partial，非逐字稿。第18／24／29頁圖形不可由文字還原，第12–13頁新唐子公司與華邦母公司口徑分開，Q2／H1 EPS與未查核／展望限制保留。

新collector／transport核TWSE完整主檔、索引場次與已資格化PDF；25秒總期限、單次5秒、原1800秒TTL與較短實存expiry、限流冷卻及single-flight保持。暖PDF不計新的取得成功；source-only沿原公司身分核對，prompt排除內部收據並保留上述限制。先保存缺正文、context遺失及prompt保留限制的RED，再修正。Root125、來源與相關197、獨立修正後10項邊界通過；重疊不相加。獨立初次174pass／1個probe JSON路徑錯誤的原log亦保留，無未解material finding。

8個變更runtime加162個原runtime已由start_mac.command正式重載，health／ready200。真正缺正文的 `2344_TW_v4_report_job_969f79427282.html` 僅補一次，HTTP200／3.822856秒／3 native HTTP／31頁，正式event451504。HTML／MD、其他來源、analysis_evidence及原品質gate、job／checkpoint保持，analysis_text_stale=True，新增模型0；這不是重新生成分析或宣稱整份報告品質已通過。

本輪另外確認：統一1216官網active frame連到sp88 IR，8/11–12場次之15頁H1英文簡報完整取得；8/10檔名、8/11封面及HK0220子公司分開，保留首頁no-redistribute與PDFpersonal-reference限制，僅作候選。矽格6257在官網403後停止該來源，改讀已發布的MOPS中英文原件，各23頁；未知Wingdings U+F075須先精確驗證，未放寬garbled gate。國泰2882索引仍指向已保存56頁原件，40頁含未知U+F070且有使用限制，保持held。研究10次native請求中9次完整200、1次403；沒有研究cache／SLA seed。

05:28台北正式滾動24h仍16／20類嚴格>80%；法說24／47=51.064%、財報23／34=67.647%、法人82／116=70.690%、近期事件66／111=59.459%。同一時間窗只排除此正式補件event時，法說為23／46=50%，其餘19類相同；不將自然離窗、研究或快取算成本次改善。全部20類目標尚未完成。完整證據見[closeout](evidence/source-acquisition/20261014/conference-free-next/closeout.json)。


### 2026-10-14 矽格 MOPS 英文簡報正式補齊；新聞與財報候選資格再核對

公開資訊觀測站的[矽格法說索引](https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1)需使用完整公開表單 POST（6257、115 年）；索引明列 10/6 14:30 場次及[英文原件](https://mopsov.twse.com.tw/nas/STR/625720261006E001.pdf)。完整 PDF 1,962,766 bytes、SHA256 `2e90848f7ad58715bf828870749eed8bf9f14ebcf47a9914e022324f56812aee`，共23頁。只對此精確原件及嵌入字型／CMap所證明的10個菱形符號修正文字解碼，其他字元與數字逐字保持；原始PDF未改寫，未知原件及一般reader警告門檻保持。

新collector核完整公司主檔、最新已到時場次與精確附件；transport保留實際POST method/form、完整原件及Content-Length驗證。1800秒與較短實存TTL、原MOPS冷卻／single-flight、25秒總期限及5秒單次期限均保持。混合2026Q2、H1、1–8月與1–9月、子公司、圖像缺漏與展望限制進入角色提示，整體仍partial且非逐字稿；不得由10月場次推為Q4財報或更新TTM。

10個本輪runtime加164個既有runtime正式重載後health／ready200，環境及158套件保持。真正缺正文的 `6257_TW_v4_report_job_f7f17ed5c709.html` 一次來源更新HTTP200／8.288秒／3 native HTTP，保存23頁，正式事件451505只計1次成功。其他data值、來源audits、HTML／MD、analysis_evidence、5項品質metadata、jobs／checkpoints保持；新增模型0、analysis_text_stale=True，未重新生成分析。Root134、作者238及受影響3、獨立reader144與整合228項通過，重疊不相加；獨立中止111項紀錄不計成功。

新新聞研究找到MoneyDJ的2851原始文章與公開分類／RSS連結，完整原文可讀，但[使用條款](https://www.moneydj.com/z/ABMoneydj/aboutTermsService.djhtm)第五、六條限制未經同意自動擷取與AI快取／資料庫用途，停止後續請求並保持held；不將TTV轉載當不同原始來源或繞過入口。研究僅索引POST1次、MoneyDJ文章及條款GET各1次，共3次native、無cache／SLA seed。1623的FinMind股票概覽誤列新聞另記錄，尚未修改。

法人23份受影響最新報告仍全具30日×3類，無新補件需求，快取自然到期不觸發重抓。財報2610／5880已完整修復，保留歷史失敗；2883／2845的既有公開UI／完整PDF已查過且仍缺必要科目，補充紀錄已更正本輪初步候選描述，不能當新可修入口重試或填零。

2026-10-14T05:59:45.605250+08:00 滾動24h仍16／20類嚴格>80%；法說25／48=52.083%、財報23／34=67.647%、法人82／116=70.690%、近期事件66／111=59.459%。同一時間窗只排除事件451505，法說為24／47=51.064%，其餘19類不變。全部類別目標仍未完成。見[本輪證據](evidence/source-acquisition/20261014/remaining-source-recovery/closeout.json)、[正式補件](evidence/source-acquisition/20261014/remaining-source-recovery/sigurd-integration/sigurd-formal-verified.json)及[獨立覆核](evidence/source-acquisition/20261014/remaining-source-recovery/sigurd-review/review-final.json)。


## 2026-10-14 新免費入口續查：敦陽原件與東電綠能公告

本輪研究原生請求15次，全部取得完整HTTP200回應，涵蓋索引、robots、公司介紹、六份PDF及一篇公告；不是15個可直接接入來源，也未記為正式SLA成功。全程匿名、TLS正常、單次5秒/connect2秒、無自動轉址或重試，正式runtime、provider快取、報告及品質門檻均未修改。

- [敦陽2480官網法說索引](https://www.sti.com.tw/earnings-call)新找到原生圖示連結的2026Q2中文簡報；完整2,955,446bytes/44頁/3.83秒，原報告只有MOPS連結而無正文。英文MOPS附件亦完整2,659,069bytes/44頁/1.72秒。兩份均因physical5三個U+F070項目符號維持native partial；中文原頁視讀確認為空心方框，未修改parser。physical24為期末合併資產負債表、25為1–6月累計損益，不將H1當單季。26等圖表主要數字及37圓餅文字不是native text，44僅Q&A結束頁，不能宣稱取得逐字稿或全圖語意。優先候選仍須正規來源接入與文字界線驗證。
- [東電綠能10/5能源週公告](https://www.tungreen.com/news/display/77)完整13,019bytes/264字，正文直接列大東電業，與保存的10/12合作新聞是不同事件。發布者維持東電綠能，不改名母公司或當獨立媒體；10/14–16是計畫參展日，尚未證明實際發生。最多新增1篇第一方公告，圖片未讀、股權關係與商業重製授權未確認。1623原5筆中仍有CMoney股票概覽誤列，新增此篇仍不足8/3/30；本輪未變更分類器或正式報告。
- 新康舒6282英文附件16頁native complete，但第15頁明示禁止未授權揭露，維持held；新旭隼6409英文附件對應9/14場次，比正式保存的6/9新，但reader仍拒絕parser_warning，32頁僅metadata診斷，不當已讀正文。
- 新凱基金控2883的2021英文合併財報與大東電1623的2024英文年報均完整下載，但前者現金流量表仍無gross intangible purchase，後者只見2023/24現金流摘要，沒有所需2021同口徑明細。維持未知，不以Others、淨額、子公司或期中報表補值。既有generic100頁上限仍拒收280/141頁原件，未放寬。

本輪未部署、未送來源更新或模型請求。正式帳本仍451505，174個runtime檔、環境與程序核對保持，health/ready200。原20類仍16類各嚴格>80%；未達為法說25/48、財報23/34、法人82/116、近期新聞66/111。研究成功不得替代正式取得率，完整下載不等同內容資格或報告品質。

[完整結論與查驗](evidence/source-acquisition/20261014/free-entrance-next/closeout.json)；各來源原件、SHA、收據、擷取與限制在同目錄保存。


### 2026-10-14 敦陽2480官方中文法說正文已正式接入

[敦陽官方法說索引](https://www.sti.com.tw/earnings-call)及其直接發布的2026Q2中文原件已完成接線。完整PDF 2,955,446 bytes，SHA256 `61a4dececbdb1a30bb4ea6529de24001b4cdf10a26e8a33a85f4feb4378c6e0b`；44頁、6,993原生文字字元。只有第5頁三個U+F070經實際嵌入字型、CMap、CID135與反向內外封閉方框輪廓核對後轉為U+25A1，原始PDF、其他文字數字與頁序均保持。未知原件與通用reader警告門檻不變。

整體仍為partial／prepared presentation：圖像圖表未完整核對，44頁Q&A不當逐字稿；第24頁三個資產負債日期、第25/39頁H1累計、EPS元與其餘表千元、第5頁敦陽資訊子公司，以及第36頁未履約義務的未來語意均保留。事件日期2026-08-05來自官方索引；實際舉行、確切時間及首次發布時間未驗證，不由URL日期推定。

先保存七項整合RED、reader與collector原件RED、真快照公司英文別名拒收RED，再最小修正。Root145、collector251、獨立276項檢查終態通過，各suite有重疊不相加，無未解material finding。完整主檔／索引／PDF的三原件GET保留25秒總期限、單請求5秒、原件1800秒及較短實存期限、限流冷卻、同時請求合併與實際HTTP計數。快取不計新增取得，internal receipt不進角色prompt。

正式以start_mac.command重載10個本輪檔案並保留168個原runtime，178個檔案與環境／套件均核對，health／ready200。僅對真正缺正文的 `2480_TW_v4_report_job_62e4d23d8c16.html` 補一次，HTTP200／6.927669秒／3 native GET，取得44頁，正式event451506只計一筆。HTML／Markdown、analysis_evidence與原品質gate、其他來源、job／checkpoint保持；來源新鮮度與可信度metadata依原流程更新，analysis_text_stale=True，模型新增0，沒有重新生成分析。

06:36台北滾動24h仍16／20類嚴格>80%。同窗口只排除此正式event對照，法說25／48→26／49=53.061%；其餘19類相同。財報23／34=67.647%、法人82／116=70.690%、近期事件66／111=59.459%仍未達；歷史失敗保持，未將研究、快取或自然離窗當成本輪改善。原目標尚未完成。

證據：[本輪結案](evidence/source-acquisition/20261014/sti-presentation-integration/closeout.json)、[正式補件讀回](evidence/source-acquisition/20261014/sti-presentation-integration/integration/sti-formal-verified.json)、[獨立覆核](evidence/source-acquisition/20261014/sti-presentation-integration/review/review-final.json)。

### 2026-10-14 共用 MOPS 公開附件入口：台積電 PDF 與聯華 PPTX

新完整原生 POST 表單入口已驗證：台積電2330取得585,360 bytes／12頁PDF；聯華1229取得9/30已公布的3,883,370 bytes／32張PPTX（30張可見、2張隱藏）。前者通過現有有界PDF reader，仍有第5／6頁圖像資訊缺漏；後者已做有界ZIP／XML研究，4張圖像頁、11個外部關係及內嵌xlsx不當完整正文，不執行或取用外連。兩者皆prepared presentation／partial，不是逐字稿或新年度財報。台積電9/14場次明示重用7/16原件，10/15未來場次不得用舊稿填補。

已重現共通程式缺口：一般MOPS流程只有metadata／附件連結，而`.pdf`限定規則會把聯華原頁兩份PPTX解析成`materials=[]`。獨立評估確認應做共用的已發布表單下載與PPTX解析；同下載URL的POST cache／receipt須綁定完整form／檔名／公司，同日場次、文件日期和新場次無附件亦須保留。這比繼續逐股硬編檔名更能處理實際正文缺口，尚未實作或部署。

聯電新完整14頁PDF雖HTTP200，但加密且copy:no，原reader正確拒收；台泥有明示重製限制、緯穎新全文的用途與同事件計數待確認、旭隼仍有未核定字形，均未升格正式成功。總13次native研究請求為12次完整200、1次301未跟隨；沒有正式SLA／provider cache寫入、模型呼叫或runtime變更。07:00回讀178檔與服務保持，原20類仍16類嚴格>80%，目標未完成。

完整證據：[本輪發現與後續切片](evidence/source-acquisition/20261014/remaining-gap-next/findings.md)、[台積電／聯電](evidence/source-acquisition/20261014/remaining-gap-next/largecap-conference/qualification-final.json)、[聯華PPTX](evidence/source-acquisition/20261014/remaining-gap-next/lienhwa/qualification.json)、[共用入口獨立評估](evidence/source-acquisition/20261014/remaining-gap-next/news/mops-reuse-review.json)。

### 2026-10-14 共用 MOPS 附件與 PPTX 已部署，台積電正式補齊、聯華仍待實測

共用公開POST表單／request-bound原件快取／PPTX隔離reader已接入，先資格化2330與1229。最新已到時場次、公司身分、全部form、檔名、原始bytes與1800秒及較短expiry須重播一致；新場次缺附件不得拿舊稿充數，隱藏頁、圖像、內嵌檔和外部關係不冒稱完整文字。台積電12頁原件於正式source-only更新HTTP200／3.819秒成功，event451507只計一次，模型0；HTML/MD及分析品質metadata保持，analysis_text_stale=True。

聯華第一個正式event451508完整收到3,883,370bytes但被空白MIME拒收。已修為僅公開PPTX精確Content-Disposition檔名及完整package可接受，原MIME不改寫。修正部署後僅對該已確認本機誤判guard做一次精確CAS修復，只改retry_at並保留count7/expiry/updated/歷史失敗。第二次event451509則HTTP200但5秒時只收到3,293,184bytes，正式API502／5.905秒，原快照保持。

最終僅把PDF/PPTX單次下載改10秒；index5/connect2/整體25秒/8MiB/較短callerdeadline及品質gate保持。真RED先重現，獨立169項終態通過；初始487、MIME151及必要storage21屬不同階段重疊suite，不相加。正式正常入口重載後184檔、環境/158套件、health/ready200及jobs/原失敗帳本均核对；最新timeout guard維持不動至09:53:02台北。未發第三次聯華請求，因此聯華正式補件與新10秒上限的live成功尚未證明。150份最新快照僅台積電補件改變，其餘149份保持。

另續查[玉山金官方法說](https://www.esunfhc.com/en/investor-relations/ir-events/investor-conference)與[友達官方簡報](https://www.auo.com/en-global/financial_results/index/investor_conference_presentation/)：玉山完整37頁原件仍有parser warning及重製限制；友達原件TLS驗證失敗，未降低驗證。4次研究嘗試為3次完整200、1次TLS失敗，沒有正式SLA/快取seed，也沒有新增可啟用來源。

07:57台北原20類仍16類各嚴格>80%。法說27/51=52.941%、財報22/33=66.667%、法人76/110=69.091%、近期事件60/105=57.143%。同窗口排除本切片1成功/2失敗時法說為26/48=54.167%，故本切片未使嘗試成功率提高；其餘19類相同，不把研究、暖快取或自然離窗算成改善。全部類別目標仍未完成。

證據：[本輪說明](evidence/source-acquisition/20261014/mops-material-integration/findings.md)、[完整收據](evidence/source-acquisition/20261014/mops-material-integration/closeout.json)、[最終獨立覆核](evidence/source-acquisition/20261014/mops-material-integration/body-budget/review/review-final.json)、[正式部署](evidence/source-acquisition/20261014/mops-material-budget-release-proof.json)。


### 2026-10-14 FinMind概覽誤判修正與新免費入口核實

最新進度另見下方「中鋼官方入口正式驗證」。

1623既有快照重現FinMind CMoney個股概覽誤作新聞、提前結束日期搜尋。精確URL角色排除已接入intake／selection／saved projection，原最多3日期、10秒、429冷卻與8／3／30保持；同cutoff重播5→4，保留原件與未驗證概覽，沒有改原存檔。Root137／獨立126通過（重疊不加），4owned＋180preserved正式重載，health／ready200。新核實南亞10/13法說15頁受明示使用條件及9頁字形限制held；台塑索引只到Q1，北極星首頁六篇全2025，榮惠10/13快訊權限／日期待驗。4研究GET完整200但0新合格來源、0正式補件、0模型，ledger451509保持；原20類仍16類>80%。[本輪結果](evidence/source-acquisition/20261014/news-gap-next/findings.md)、[部署](evidence/source-acquisition/20261014/finmind-overview-release-proof.json)。

### 2026-10-14 08:40 中鋼官方入口正式驗證

新增[中鋼官方法說清單](https://www.csc.com.tw/csc_e/ss/pst/pst_index.html)的 2026-09-23 英文簡報：匿名 GET 核對公司主檔、清單與 4,006,437 bytes PDF，完整取得 35 頁原生文字。五種字形共 27 個標記及每頁文字雜湊已核實；未知新版須重新核對。上半年、1–7 月初估、個體／合併與展望限制保持，圖表語意仍 partial，不當逐字稿或年度查核財報。

正式 source-only 補件一次，HTTP 200／5.773 秒、事件 451510、模型 0 次。法說會同窗口 27/51→28/52，原 20 類仍 16 類各嚴格 >80%。原分析／品質／HTML／Markdown 與另外 149 份快照保持。儒鴻 403、東元 978 challenge、聚陽明示下載授權要求及年度財報缺口未當成成功；研究 7 次請求與正式計數分開。Root 192 與獨立 36 passed（重疊不相加），最後診斷交付 deadline／TTL 問題已修復。詳見[完整查核](evidence/source-acquisition/20261014/free-gap-followup/findings.md)、[正式歸因](evidence/source-acquisition/20261014/free-gap-followup/csc-formal-attribution.json)。


### 2026-10-14 09:23 中華電最新完整原件，國巨歷史原件候選

[中華電官方投資人行事曆](https://www.cht.com.tw/home/web/home/investors/shareholder-services/ir-calendar)核實10/13 IBF最新已到時場次，17頁英文PDF原生文字完整。首次正式回應使用另一種官網發布路徑而502；已核相同PDF並只接入兩個exact URL，完整保留初次失敗。修正後第二次補件200／4.318秒／3GET／0模型，正式新增1份正文，原分析需重跑。隱藏編輯文字第4／14頁不進角色節錄，Q2／H1不能當Q3或查核年報，圖表語意仍partial。Root238及獨立修正21通過，190runtime正式核實。

[國巨新官網](https://yageogroup.com/)已由主檔登記舊域名的301核身分；7/29官方原件14頁完整，屬既存報告同場歷史候選。完整法說場次清單仍缺native核實，新IR頁面為動態殼，不當最新入口啟用。緯創403停止，友達先前TLS／用途限制仍保留。公告診斷另外找出兩筆20秒期限耗盡與11個缺typed error的原文失敗；先補證據再調抓取。

本輪10native研究與正式2POST（初次502、修正200）分開，未seed研究資料或改分母。09:23原20類仍16類各>80%：法說27/52、財報22/33、法人76/110、近期60/105。法說計數含2筆真實WebPro metadata，完整正文只補回1份；4筆早先成功自然離窗，原帳本仍在。[本輪完整證據](evidence/source-acquisition/20261014/remaining-gaps-after-csc/findings.md)、[同窗口歸因](evidence/source-acquisition/20261014/remaining-gaps-after-csc/cht-whole-turn-attribution.json)、[國巨收據](evidence/source-acquisition/20261014/remaining-gaps-after-csc/yageo-followup/qualification.json)。


### 2026-10-14 10:01 國巨使用限制、免費法人入口補17份

國巨新官網公開IR畫面確認146筆、最新7/29，並觀測公開GraphQL路由；但[官方條款](https://www.yageogroup.com/SalesResources/ResourceLibrary/article/11867)明示自動擷取限制，停止native API與整合，3次研究GET不入SLA，完整native索引仍未核實。不可將前輪14頁PDF升為新合格／最新入口。

以既有免費官方TWSE T86＋FinMind正常補件，17份缺10/12、10/13的法人報告全部200、30交易日×3類核實；共用原件保留原epoch、既有23健康cohort不重刷。首份刷新遺失兩分析欄位已從精確原快照恢复且修正刷新器，其餘16份讀回保持原metadata。22筆新增成功觀測為5全市場原件＋17provider結果，非22份報告。法人同窗76/110→98/132；原20類仍16類>80%，model0。公告續抓已部署、37合成案例隔離補齊，尚無正式公告續抓成功。見[本輪完整查核](evidence/source-acquisition/20261014/remaining-gaps-after-cht/findings.md)。

### 2026-10-15 免費來源續找：產業月統計與 OTC／逐字稿入口

- 新候選：[經濟部統計處製造業生產指數](https://service.moea.gov.tw/EE521/common/Common.aspx?code=D&no=4)匿名 TLS-verified GET HTTP 200，頁面內含按月的製造業／中分類表，明確列出基本金屬、電子零組件、電腦／電子／光學等產業，最新可見月份為2026-08。頁面列有XLS／ODS／PDF匯出，但單次正常公開表單匯出在本機30秒等待內未取得回應；尚未確認可穩定下載、開放授權或商用重用。只適合作為落後一期的產業景氣背景，不是公司個別數據、即時新聞或財報。未接 provider，未計SLA。見[實測與限制](evidence/source-acquisition/20261015/moea-industrial-production/README.md)。
- [上櫃公司每日重大訊息](https://data.gov.tw/dataset/18418)的MOPSFIN CSV直連已匿名GET HTTP 200；40筆當日列含公司、標題、事實日期及說明全文。政府資料平台標示每日更新、免費及政府資料開放授權第1版。這是可補上櫃原文的寬覆蓋入口，但僅日快照且與MOPS同源，須由正式端逐日保存並檢查日期缺口，不能當第二個獨立交叉來源。未接入或納入成功率；見[原件與收據](evidence/source-acquisition/20261015/mops-otc-daily-disclosures/README.md)。
- [上市／上櫃財報CSV與TWSE／TPEx OpenAPI](evidence/source-acquisition/20261015/official-open-data-latest-quarter-probe/README.md)有最新季損益表及資產負債表快照，可覆蓋部分上市與上櫃公司；但並非五年歷史或現金流量表，且同為MOPS來源，不能補齊年度FCF缺科目。未接入正式provider。
- 聯發科2454官方逐字稿不是本輪首次發現：10/9候選紀錄已有入口。本輪按正式project PDF reader重新抓2026Q2原件並重驗HTTP 200、15頁native text完整、38,646字及Q&A／管理層講者標記；仍為單一發行人候選，商業重用權未確認，未接入。詳見[本輪重驗證據](evidence/source-acquisition/20261015/mediatek-ir-transcript/README.md)。
- 關務署的免費統計可查商品／國別，但互動查詢頁顯示CAPTCHA；資料平台上的月度總額欄位不能代替公司或商品明細。本輪未自動提交驗證碼，也未將它列為可直接接入的來源。FSC「現金流量表」出口端點仍因TLS憑證驗證失敗而未下載，不以停用TLS驗證補取；見[失敗收據及資格限制](evidence/source-acquisition/20261015/fsc-cashflow-open-data/README.md)。

- 同一MOEA入口另有[主要貨品外銷訂單金額](https://service.moea.gov.tw/EE521/common/Common.aspx?code=B&no=2)：本機匿名GET HTTP 200，頁面列每月USD百萬元及資訊通信、電子產品、光學器材、基本金屬等類別，最新可見期為2026-08；表單列XLS／ODS／PDF，但這個系列尚未下載檔案，也沒有確認開放授權或商業重用。比生產指數更接近未來需求，但仍是產業調查，不是上市公司個別訂單。見[實測收據](evidence/source-acquisition/20261015/moea-export-orders/README.md)。

本輪只有來源研究及證據記錄，沒有修改正式資料流程、報告、provider cache或SLA，因此不能據此宣稱任何類別超過80%。

### 2026-10-15 12:27 新入口續查：公發公司財報與 ACE 4763

TWSE OpenAPI 的 `t187ap06_X_ci`／`t187ap07_X_ci` 公發公司損益／資產負債表端點匿名 GET 均 HTTP 200、各215筆，但全是115年第2季快照，沒有現金流量表或五年序列；不符合年度財報來源資格。SEC CompanyFacts 已是先前候選；本次查到TSMC 2025 20-F 已於2026-04-16出現在submissions，但試查的標準 IFRS Revenue／ProfitLoss／Assets facts 仍只到2024，必須回到該 accession 核實，不能假設CompanyFacts涵蓋所有最新申報。ACE Chemical官方頁列出4763多年季報及法說資料，但正常TLS驗證失敗、Web頁也逾時／502，且再利用條款未確認，暫不接入。正式服務12:29讀回仍是20類中16類嚴格>80%，其餘法說42/76、財報25/44、法人102/142、近期事件77/120；本輪沒有修改runtime或SLA。完整證據及限制見[12:29新來源續查](evidence/source-acquisition/20261015/new-free-source-entrances/README.md)。

### 2026-10-15 13:44 TWSE 英文事件原文備援與 ACE TLS 再查

正式服務最新 `last_24h` 的4個缺口類別為法說42/75（56.00%）、財報25/44（56.82%）、法人102/142（71.83%）、近期事件77/120（64.17%）。provider audit 中，TWSE公司公告歷史的2筆真失敗正好是1101與2354，另有7筆部分涵蓋。

新增核對TWSE英語版單一公司事件入口：[1101 JSON](https://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=1101)、[2354 JSON](https://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=2354)。兩個匿名TLS GET均HTTP 200，各回10列並將公司代碼、公告日期時間、標題與連結綁在同列。各取首筆官方英文公告原文連結也均HTTP 200：台泥1101公告日2026-10-13、detail 1,869 bytes；鴻準2354公告日2026-10-12、detail 2,805 bytes；頁面均可讀到issuer header、公告時間、subject與說明正文。此入口可作現有中文個股索引／MOPS detail失敗的精確語言備援候選；仍是TWSE／MOPS官方資料，不算獨立發布者，也尚未通過parser、transport allowlist、正式接入或SLA驗收。TWSE官方頁說明投資資訊中心確含上市公司重大訊息、財報及法說資料。[TWSE資訊揭露頁](https://wwwc.twse.com.tw/IIH2/zh/company/information.html)

再次查驗材料KY 4763官方[2021年英文合併查核財報](https://www.acetekgroup.com/pdf/2021ywcb.pdf)及`www`／apex兩種hostname；系統端兩次TLS憑證驗證皆失敗，未關閉驗證或讀取原件。搜尋索引顯示該PDF涵蓋2021、2020年度經查核合併財報，但來源目前仍不可由正式正常HTTPS客戶端取得，保持held。[公司官方財報索引](https://www.acetekgroup.com/list_21/)列有2021年報及多期財報。

同時找到TWSE的[MOPS電子書財報索引](https://doc.twse.com.tw/server-java/t57sb01_e?step=1&colorchg=1&year=2021&stockcode=4763&mtype=A&dtype=AE)。索引列出4763的2021Q4財報，按公開表單取回官方PDF為812,862 bytes、SHA256 `4193fd25d84d43661d2ed51bb5418f6e58d203ee275a8123655586ff9ea51554`；既有`source_pdf_reader`驗證69頁、無空白／亂碼頁，文字157,995字元。原件明示2021及2020查核合併報表、千元新台幣，包含營收2,714,866、歸屬母公司淨利357,500、總資產3,635,190、營業現金流455,147及設備支出(424,779)。現金流量表沒有明列無形資產購置，故不能把它推成零或補足自由現金流完整欄位；是可核對核心報表的正式新入口，但目前不能修復該項全科目品質門檻。

對應現行2354年度財報比較值衝突，電子書索引也列出2024Q4官方查核PDF；原件HTTP 200、1,216,996 bytes，但既有通用PDF reader回`character_limit`，尚未能安全讀回所需表格。4763最新法說亦可由英語版事件頁連到[MOPS發行的簡報](https://emops.twse.com.tw/nas/STR/476320260930E001.pdf)：HTTP 200、5,599,455 bytes／26頁，但reader標為partial、7頁空白且僅234個文字字元，不能做合格法說正文。需保留一般reader限制，未驗證前不可把回應成功當內容成功。

另對1229目前的MOPS發表簡報timeout，英語公司事件頁所列[2026-09-30會議資料頁](https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=1229&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09)返回精確PPTX附件`122920260930E001.pptx`，直接GET為HTTP 200、3,883,370 bytes。這是可用來測試MOPS host／附件路徑fallback的候選，但同份簡報已由聯華官方入口取得，不能當作新增獨立publisher或額外內容覆蓋；正式MOPS collector與parser仍待驗。

上櫃公告另有[政府資料開放平台的每日CSV](https://data.gov.tw/dataset/18418)，含公司、公告日期、標題及說明，免費、每日更新且採政府資料開放授權第1版；但只覆蓋上櫃、是MOPS同源日快照，需要逐日留存並檢查缺日。當前24小時上櫃公告樣本3324／5314已由TPEx歷史公告成功取得，因此這個入口擴大潛在覆蓋，不是本次觀測到的低成功樣本修復，也不應再計為第二個獨立來源。

本次僅做官方來源研究及文件追加，未改正式抓取器、報告、provider cache或SLA，也未呼叫模型。當前所有20類別尚未全部超過80%；公告路徑已有明確可修候選，財報部分有新文件入口但仍有核心科目／文字限制，法說原件仍要經現有內容品質門檻，法人 provisional／valid-empty 個案沒有找到新的可驗證完整股數來源。

### 2026-10-15 14:52 凱基金控五年摘要與免費 XBRL 入口續查

正式24小時來源率：法說41/73（56.16%）、財報25/44（56.82%）、法人102/142（71.83%）、近期事件77/120（64.17%）。2883凱基金控官方 IR 新核實一頁五年摘要PDF，完整可讀2021–2025年度摘要，含淨收益、稅前淨利、純益、EPS、總資產與權益；但缺利息／手續費收益、營業現金流及資本支出，不能解決現行完整財報schema或2022比較數衝突，重用授權也未核實。MOPS XBRL package在TWSE Data E-Shop標價每月NT$40,000；免費filings.xbrl.org API的台灣country查詢HTTP200但0筆。研究未接入正式來源、未寫SLA/cache、不計取得率改善。完整原件、SHA-256與限制見[續查紀錄](evidence/source-acquisition/20261015/kgi-financial-source-and-xbrl-followup/README.md)。

### 2026-10-15 14:59 免費市場新聞 API 與法說替代入口續核

Marketaux官方API支援市場清單包含台灣，免費額度是每日100次、每次最多3篇；匿名測試 `2330.TW` HTTP401，需 token。官方網站條款限個人非商業及禁止未授權自動化，API專用商用／報告重用權尚不清楚，因此保留為候選，未取得資料或接入。另核對法說逾時標的：雙鴻3324官網標準GET只回1,031-byte JS shell，未找到公開法說API；燿華2367正式站 `pcbut.com.tw` 的 TLS 驗證失敗，未降級驗證；錯誤的 `unitech.com.tw` 是2414精技電腦，不能套用到2367。此輪未取得合格新法說原件。詳見[入口與資格證據](evidence/source-acquisition/20261015/kgi-financial-source-and-xbrl-followup/README.md)。

### 2026-10-15 15:03 官方／開放入口再查

禾伸堂3026官網列有與現行缺件相符的2026-09-04法說PDF，但網站條款禁止未授權重製，僅保留待授權候選；TDCC IR平台有跨公司場次索引，平台條款不允許資料儲存、整合或用於應用程式；緯創3231官方法說頁本機標準HTTPS GET回403。政府平台上市公司季資產負債與綜損表為免費開放授權，但沒有公司現金流量表／五年年度完整科目；已存在的上市公司每日重大訊息CSV是同日快照，不是新的獨立入口。本輪未改runtime或SLA。四個未達標類別及完整查證見[本輪證據](evidence/source-acquisition/20261015/public-open-source-round2/README.md)。

### 2026-10-15 15:17 SEC EDGAR 台灣交叉上市公司原始申報續查

SEC 官方 EDGAR 找到台股2330、2303、3711、2412、8150的2025年 `20-F` 原始申報；其中2330、2303、3711、8150申報直接提供三年查核財報／現金流。另確認ChipMOS 8150的2026-02-24 `6-K` 附件是2025全年法說簡報。SEC說明EDGAR公開申報可免費重用，程式化存取要宣告User-Agent並遵守每秒10次上限。這是 `financial_statements` 及部分 `earnings_call`／`recent_catalysts` 的新候選，但限SEC申報公司；五年序列需跨年度申報對齊，簡報也須通過現有原件與內容品質檢查。現有SEC provider只取申報清單，且User-Agent是`.local`聯絡佔位值，尚不適合正式接入。本輪沒呼叫SEC API／下載原件、沒改runtime／ledger或計入成功；正式24小時基準仍為法說41/73、財報25/44、法人102/142、近期事件77/120。詳細證據見[SEC EDGAR續查](evidence/source-acquisition/20261015/sec-edgar-taiwan-crosslisting/README.md)。

### 2026-10-15 15:20 SITCA 月度基金持倉入口再查

SITCA 官方頁仍確認「基金投資明細－月前十大」及「季占基金淨資產價值1%以上」按月／季更新；月度前十大能揭露個別基金、證券代號與持倉，不是每日三大法人買賣超。這次未在官方查詢頁或公開條款找到可確認資料自動儲存、整合及正式應用的再利用授權，故維持 held；未下載、整合或計入 `institutional_trading` 成功。[官方投資資料入口](https://www.sitca.org.tw/ROC/Industry/IN2002.aspx?PGMID=LA01)、[月前十大頁](https://www.sitca.org.tw/ROC/Industry/IN2629.aspx?pid=IN22601_04)。

### 2026-10-15 15:28 延伸查驗 MOPS 公開簡報索引與官方 RSS

TWSE/MOPS 英文公開簡報索引 `t100sb07_1_e` 為 MOPS timeout 的備援路徑：1101 的 2026-09 查詢沒有附件連結，2354 可定位 9/30 官方 PDF，3017 可定位 8/12 PDF（索引重複列四次）。兩份文件各下載一次皆 HTTP 200，但現有有界 PDF reader 都 timeout，因此尚不能作為正式正文成功，也不增加獨立發布者。另查奇鋐官網財務資訊頁，標準 TLS 只回 212-byte Incapsula script stub，未取得內容，沒有嘗試繞過。經濟部國際貿易署官方 RSS 新聞稿 20 項只提供產業／政策背景，目標公司沒有精確命中；公告 feed 的寬鬆命中是非公司字串，排除個人公告後沒有目標公司事件。貿易署網站明示採政府資料開放授權第1版，可保留為產業背景候選，但不計個股近期事件。另查 FinancialFilings 台灣 API，每月 500 credits 免費額度，但 API 條款限制內部使用、禁止組織外 App 顯示與再散布，且需帳戶金鑰，不符合直接接入正式資料服務的免費開放來源條件。以上研究沒有寫入 provider、cache、SLA 或報告。實測與限制見[續查證據](evidence/source-acquisition/20261015/emops-index-and-government-rss/README.md)。
