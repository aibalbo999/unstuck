# 資料來源取得與證據判讀

2026-10-12 新增兩個免費官方月營收備援：政府[上市dataset18420](https://data.gov.tw/dataset/18420)的[上市CSV](https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv)，以及[上櫃dataset56510](https://data.gov.tw/dataset/56510)的[上櫃CSV](https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv)。完整原檔原生HTTP200實测上市163,059bytes／869列／0.367秒，上櫃141,862bytes／761列／0.503秒，出表1151012、資料11509。這是完整下載，不是全發行人覆蓋；只接當月及上月兩個相鄰月份，不能當六個月歷史、TTM、年度財報或PIT。千元單位依官方月營收申報及[台積電原6-K](https://www.sec.gov/Archives/edgar/data/1046179/000104617926000680/tsm-revenue20261008.htm)相同511,857,399千元核對。MOPS歷史頁原生HTTP200只有800byte安全性存取限制，未繞過，也未採作資料。

FinMind成功仍沿用原有最多六月份資料；失敗才用新官方快照。同一次fetch且同股票、市場、uncached typed operation的既有失敗只保留一次，免立即重抓；缺列仍unknown而非零。新獨立原文快取守1800原TTL、完整原bytes／hash／URL／native10欄receipt、原旗標、最終deadline與TTL，cache不當新抓取成功。兩個獨立P2及三個實際RED（duplicate primary audit、矛盾HTTP／shared-only receipt）均保存並關閉。Root相關12模組400pass、必要runtime/storage21pass；獨立相關及原probe424pass、補充5pass（重疊不相加）。五個runtime路徑已由start_mac.command部署，另外110個原runtime檔、環境與158套件保持，health／ready200，15件pending payload／14件scheduled score保留至自然到期；90筆舊零資料列依原90日policy自然到期，精確原列及hash仍留在release證據，未手動刪除或重建。

正式自然工作已觸發備援：2466.TW本次FinMind失敗後，官方CSV冷HTTP200但缺該公司，449013仍記unavailable；6152.TW本次FinMind失敗後，449074以同一正式原件快取补回2026年8月3.12億／9月1.92億，原取得epoch1791802636.789906、partial與primary失敗保留，HTTP0且新SLA成功0。6152整份報告仍因法人分項證據／final_audit gate未發布，不宣稱報告成功；不更動news8／3／30、年度5年9facts、價格、TTM或qualitygate。研究HTTP3（兩CSV、一個被限制的歷史頁），研究provider-cache/SLA seed0、optimizer新模型0；自然watchlist的來源／模型活動另計。詳見`docs/evidence/source-acquisition/20261012/official-monthly-free-fallback-release-proof.json`、`official-monthly-free-fallback-independent-review-fixed.json`、`official-monthly-6152-actual-failed-primary-recovery-proof.json`及`official-monthly-free-fallback-first-live-observations.json`。

2026-10-12T18:58:30.002354+08:00正式24h仍僅10/20原類別各嚴格>80%，整體目標尚未達成，FinMind自然恢復也不歸因本次patch。金融業及未列公司月營收、六月份完整歷史、法人分項／其他10類別缺口仍需新免費入口；不以健康重抓、快取、research或平均數製造達標。


## 盟立與兆豐完整新聞及主體邊界（2026-10-12）

2026-10-12T16:59:00.171280+08:00 盟立2464及兆豐2886兩個完整免費官方新聞入口已部署，兩份實際不足8則的既有報告在主檔修正後各補一次：2464.TW 7→8則／HTTP200／2.2698秒／2 native HTTP；2886.TW 7→10則／HTTP200／2.8867秒／4 native HTTP，均符合原8／3／30門檻。新原文各自只增加一個發行人publisher，不是新增獨立媒體。

完整TWSE主檔綁定盟立自動化股份有限公司／22099478／Mirle／登記mirle.com.tw，以及兆豐金融控股股份有限公司／70796754／MEGA FHC／登記megaholdings.com.tw，再核原生索引、全文、法律主體及日期。盟立[2026新聞中心](https://www.mirle.com.tw/news/?index_m_year=2026)綁定[9/15合資公告](https://www.mirle.com.tw/news-detail/671/)；兩份responsive文字須一致，仍只算一篇。兆豐[原生新聞列表](https://www.megaholdings.com.tw/tc/news.aspx)的四個公開id／cid／chk／param參數原樣保留，只採明确母公司標題，原生ROC首日須符合索引ISO日；不把子銀行或公益活動當母公司年度審計財報。發布頁顯示日不升格首次刊登，影像、事件影響、全文陳述與audit均未獨立證明，窗口保持partial。

獨立P2發現新request可被既有3042 context改寫，兩個實際public provider反例及blocked收據保存；修正以request或resolved context任一屬新route就先核精確主體，不改舊route契約。原UTF8、三種root股票類型、完整三收據、hash、原epoch、cached master HTTP未知、最後deadline及warm failure拒收保持。首次兩次正式补件分別5.1595秒及2.1572秒／502，均止於OpenAPI JSON主檔timeout；原失敗442055／442242及當時report三artifact保持。政府[上市公司基本資料dataset18419](https://data.gov.tw/dataset/18419)直接發布的[完整官方CSV](https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv)已實測HTTP200／673,300bytes／1,095列／出表日1151011，兩公司完整身份吻合。僅此兩新collector改用CSV primary；原CSV bytes／SHA／來源URL／retrieval epoch保存，derived JSON只給既有法名／日期parser，strict UTF8sig／quoted row／unique header／全row shape核對。舊完整JSON收據仍可重播；CSV不得冒充HTTP未知cached JSON。16:07第一研究原件已自然到期而未採用；獨立native context診斷在原5秒上限內另取得完整CSV／4.7372秒，保存獨立新epoch與收據，未延長舊epoch。第二兩次CSV cold正式補件仍逾時，四次fail皆保留。顯式採用新完整原件只在私有receipt retention留原1800TTL剩餘秒、HTTP／SLA／model0，normal provider raw/error cache逐欄保持；新聞仍須native索引及正文。Before use／archive／final重核原TTL與同20秒deadline；兩P2的final deadline漏檢及expired records滲入normal merge已修正，原blocked／RED保留，失敗清當次records保留actual HTTP與error，歷史saved verifier及普通partial policy保持。原件重用不證明API原生cold主檔已恢復穩定；到期仍走原get／guards。JSON原24h於15:33到期，沒有手動續期、seed研究原件或重設error cache／guard；CSV沿原1800秒native raw cache與120秒error cache，5秒／connect2／20秒總期限及2.5MB master上限保持。舊鴻海原件只核完整hash與當時使用資格，未聲稱過期主檔目前仍新鮮。

Root 250相關、前一版1187相關及150補充契約與獨立runs分開記錄；重疊不加總。CSV修正1owned／110preserved＝111runtime、env／158套件、正式程序、health／ready200、既有待處理及排程payload／score保留核對。兩份HTML／Markdown、quote／TTM／財報／社群及核心epoch、analysis evidence、五品質metadata保持，analysis_text_stale=True，本輪補件未呼叫模型或產生新完整報告品質結論；自然watchlist工作仍照原流程使用來源／模型，原則上不能以全域帳本不變或queue0作此輪證據。原job／dispatch／失敗與零筆prefix保持，無force kill、commit或push。

完整本輪同一窗口包含四次保留error及兩次原件重用後success，近期事件success+2／attempt+6，其餘19類逐欄相同；僅移除六個本輪fetch IDs比較，其餘自然來源工作兩側均保留。成功補件實際HTTP另列共6；四次失敗詳細傳輸數未在SLA收據保留，不補造全輪HTTP總數，也不把自然離窗歸因patch。原20類9類嚴格>80，未達：alternative_data 19/67＝28.3582%、dynamic_peer_metrics 38/94＝40.4255%、earnings_call 36/57＝63.1579%、financial_statements 32/46＝69.5652%、institutional_trading 59/113＝52.2124%、monthly_revenue 55/165＝33.3333%、pe_river_chart 94/149＝63.0872%、peer_discovery 30/81＝37.0370%、recent_catalysts 171/425＝40.2353%、search_upstream 295/391＝75.4476%、social_sentiment 49/122＝40.1639%；全部20類目標尚未完成。News8／3／30、財報五年九事實／accepted typed sector、quality／quota／TTL／cooldown／deadline皆保持。

另探查兩個新東元1504官方財報PDF地址：2024回應metadata不合格；2022實際HTTP978、1005bytes HTML，非PDF，確切拒絕原因尚未證明。保留完整body／header／metadata，沒有相同請求重試或放寬transport，不計研究成功為正式SLA；十次native研究請求與正式六次請求分開記錄。

見[盟立正式補件](evidence/source-acquisition/20261012/mirle2464-retained-master-formal-news-refresh-proof.json)、[兆豐正式補件](evidence/source-acquisition/20261012/mega2886-retained-master-formal-news-refresh-proof.json)、[當前全20類驗證](evidence/source-acquisition/20261012/registered-master-original-current-closeout.json)、[修正覆核](evidence/source-acquisition/20261012/registered-master-original-independent-review-fixed.json)、[原阻擋收據](evidence/source-acquisition/20261012/registered-mirle-mega-independent-review.json)、[東元完整native診斷](evidence/source-acquisition/20261012/teco1504-new-2022-full-native-diagnostic.json)。

## 鴻海完整逐字稿與逾時狀態保護（2026-10-12）

2026-10-12T14:05:30.107541+08:00 鴻海2317免費完整法說逐字稿入口已部署。完整TWSE主檔核對2317、鴻海精密工業股份有限公司、統編04541302、HON HAI與登記www.honhai.com；原24小時epoch與HTTP未知保持。由[登記官網單場頁106](https://www.honhai.com/zh-tw/investor-relations/investor-relations-activities/investor-conference/106)原生下載區連到[官方完整逐字稿](https://image.honhai.com/upload/202608/law_talk/Hon_Hai_2Q26_Results_Transcript_Chinese_20260818_4465.pdf)，實際缺正文的8/12場次source-only更新HTTP200／3.3000秒／2 native HTTP，正文0→23頁，完整PDF1,057,998 bytes與三份原件可重播。沒有模型呼叫或新全報告。

原native直連索引失敗保留；單變因HTTP1.1探查取得200但超600KB，全年度索引亦超新入口1MB限額，兩次完整性失敗不當成功或重試灌分。新公布單場頁完整955,110 bytes可在同上限取得，只有新HonHai傳輸用HTTP1.1／頁面1MB，既有source上限與PDF8MB不變；未下載15.6MB投影簡報。單次5秒、connect2秒、同一20秒總deadline、TLS、cooldown、lease、cache原24小時及禁cookies／auth／proxy／redirect／自動retry皆保持。正常查詢仍讀原場次metadata，只補已宣告8/12的matching call，其他日期沿舊流程；既有裸2317 call僅在explicit2317.TW EQUITY根與該日期下相容。

PDF封面宣告會議2026/8/12台北15:00、2026 Q2，`event_date_basis=official_transcript_cover_declared_date_time`；頁面7/29只記顯示日，檔名8/18不當首次發布或文件發布日，兩者未知。`native_text_coverage=complete`只表示完整原生文字可讀，overall coverage仍partial；實際會議、逐字稿準確性、影音／所有陳述未獨立核驗。角色3／5／12取得每角色≤2500字元／6頁的原生文字prefix、原件hash、頁碼與日期依據；新typed transcript全文不進generic base，legacy其他正文保持，內部原件路徑剝除。

獨立覆核的兩項初始P2、後續成功旗標退化及root RED全部保留，固定版另存。冷抓取最後核對逾時保留真2次native HTTP／component，warm逾時記當次HTTP0並保持error，不能標正常cache跳過；reader後、封面後、context equality後及deepcopy交付後都核同deadline。來源核對失敗／逾時保持502及原snapshot，不啟第二metadata workflow。Root 1135相關、150補充契約與獨立runs分開，重疊次數不相加；10owned／100preserved＝110runtime、env／158套件／正式程序、health與ready200／六queue0核對。原job、dispatch、failure及零筆prefix沿原retention保持，無force kill、commit或push。

同一窗口法說success／attempt／HTTP各+2，parent aggregate HTTPfalse且排除，其餘19類逐欄不變；研究未seed正式cache／SLA，自然離窗不算patch貢獻。原20類17類嚴格>80；未達：earnings_call 35/45＝77.7778%、financial_statements 31/50＝62.0000%、recent_catalysts 116/168＝69.0476%。全部20類達標目標尚未完成。原HTML／Markdown、quote／TTM／財報／新聞／社群、核心epoch、analysis evidence及五品質metadata保持，analysis_text_stale=True，未跑新全報告品質；news8／3／30、財報五年九事實及accepted typed sector、quality／quota／TTL／cooldown／deadline門檻皆保持。

見[正式補件](evidence/source-acquisition/20261012/honhai2317-transcript-one-formal-refresh-proof.json)、[當前驗證](evidence/source-acquisition/20261012/honhai2317-transcript-current-closeout.json)、[最終固定版覆核](evidence/source-acquisition/20261012/honhai2317-transcript-independent-fixed-v2-review.json)、[原初始阻擋](evidence/source-acquisition/20261012/honhai2317-transcript-independent-review.json)、[後續旗標阻擋](evidence/source-acquisition/20261012/honhai2317-transcript-independent-fixed-review.json)。

## 晶技完整法說正文與PDF逾時保護（2026-10-12）

2026-10-12 12:23 晶技3042免費完整法說簡報入口已部署。`txc_conference.py` 核對完整TWSE主檔的法名、統編21204867、TXC與登記www.txccorp.com，再由原生法人說明會索引绑定9/10 `/download/219/`完整PDF。一次真正缺口source-only更新HTTP200／5.5773秒／2 native HTTP，原正文0頁補為15頁，來源三份完整原件均可重播，主檔舊epoch與HTTP未知保持。沒有模型呼叫或新全報告。

三種原生符號僅於完整嵌入字型、CMap與CID匹配時，將獨立fragment中的■／◆／✓精確恢復；原件2／13頁視核，總18個替換，其餘字元、數字、順序及PDF逐byte保持。未知字型、混合數字或其他字形仍拒絕。`native_text_coverage=complete`只表示原生文字可讀，整体coverage仍partial；封面沒有場次日，9/10僅為索引連結的活動日期，`event_date_basis`保留於角色3／5／12。首次發布日、文件日與內容期未知，未宣稱實際完成法說、逐字稿、影像／圖表數字、閱讀順序或完整陳述已核驗。

獨立覆核找出的真實child PDF timeout誤啟MOPS fallback已修正：冷抓取與快取重播保持typed timeout並終止，API核對逾時回502、原快照保留。初始blocked收據及root 2失敗反例另存不覆寫；固定版1042相關、194獨立及2保存反例通過，重疊次數不相加。9owned／98preserved＝107runtime、env／158套件、正式程序與health／ready200、六queue0核對。6筆舊job依原30日terminal／保留最近20規則到期，既有failure／zero prefix／dispatch保持，無force kill、commit或push。

同一窗口實際僅法說success／attempt／HTTP各+2，parent aggregate明確HTTPfalse且排除，其餘19類逐欄不變；未seed cache或SLA，不將自然離窗算修復。原20類仍17類嚴格>80：法說33/43＝76.7442%、財報31/50＝62%、近期事件117/169＝69.2308%，全部達標目標尚未完成。原HTML／Markdown、quote／TTM／財報／新聞／社群、核心epoch、analysis evidence與五品質metadata保持，analysis_text_stale=True，未跑新全報告品質；news8／3／30、財報五年九事實及accepted typed sector、品質／quota／TTL／cooldown／deadline都保持。

見[正式補件](evidence/source-acquisition/20261012/txc3042-conference-one-formal-refresh-proof.json)、[當前驗證](evidence/source-acquisition/20261012/txc3042-conference-current-closeout.json)、[固定版覆核](evidence/source-acquisition/20261012/txc3042-conference-independent-fixed-review.json)、[原阻擋收據](evidence/source-acquisition/20261012/txc3042-conference-independent-review.json)。

正式抓取採共享20秒deadline、單次5秒、索引200KB／PDF8MB、native reader最長10秒；不代理、帶cookie、降TLS、重導或自動重試。cache過期不晚於主檔原24小時期限，warm重播不記新HTTP。source-only核對由股票類型／context與來源marker及audit provider共同保護；完整來源損坏或核對未完成不寫新快照。

## 晶技完整月度自結新聞入口（2026-10-12）

3042官網索引与兩篇文章以完整TWSE主檔、精確日期／標題及原生copyLink／全文收據綁定；未發布的canonical／OG URL不猜測。9/15原meta description有截字byte，原件完整保存、不替換；所有採用欄位與全文／表格strict UTF8，正文或身分亂碼拒收。損益表八列、兩層表頭、原空YoY及註解保留，不將自結公告升格為年度財报／TTM。沿原20秒／5秒／600KB／TLS／無重導重試、30分鐘raw cache及persistent cooldown，原主檔epoch與HTTP未知保持。

11:08一次正式source-only補件2.6596秒／HTTP200／3 native HTTP，兩篇原文保存，合格新聞7→9／8 publisher，原8／3／30通過；兩篇同一官網不是兩個獨立publisher，全文不等於審計或獨立查證。HTML／Markdown／原分析證據／五品質metadata／quote／TTM／財報／社群保持，analysis_text_stale=True。104runtime／env／158套件／程序與health／ready200／queue0核對，885相關與151獨立、5反例不相加。5舊job符合原30日到期与terminal error規則，不恢復過期列；原verifier漏認error的失敗及修正證據保持。原20類仍17嚴格>80，同窗僅新聞成功／attempt各+1，其他19類不變。見[正式驗證](evidence/source-acquisition/20261012/txc3042-issuer-current-closeout.json)、[補件](evidence/source-acquisition/20261012/txc3042-issuer-source-formal-refresh-proof.json)。

## 致茂完整官網新聞入口（2026-10-12）

2360的新入口限定登記官網的原生英文新聞索引／文章，以完整TWSE主檔及完整原件收據核對身分、日期、URL、hash、bytes及全文。名錄重讀維持原epoch／TTL及HTTP未知；兩個native來源請求分別保存實際原件。保存新聞的instrument_type／quote_type／quoteType矛盾會被拒絕；沿原20秒總期限、5秒單次、600KB、TLS／無重導重試、persistent cooldown與30分鐘raw cache。

10:40一次真缺口source-only補件HTTP200／2.0128秒，新原文4276字，合格新聞7→8／7 publisher，通過原8／3／30；未來參展、發行人自行陳述及partial窗口保持。原正文／分析證據／五品質metadata／quote／TTM／財報／社群不改，analysis_text_stale=True，完整報告品質仍需重分析。Root849與獨立固定版40不相加，103runtime及正式健康／queue核對；原失敗保留、正常30日job到期1件明列。原20類仍17類嚴格>80，同窗新聞成功／attempt各+1，其餘19類相同；詳見[正式驗證](evidence/source-acquisition/20261012/chroma2360-issuer-current-closeout.json)與[覆核](evidence/source-acquisition/20261012/chroma2360-issuer-fixed-independent-review.json)。

2026-10-12T09:51:31.443916+08:00 南亞科2408原件重用已正式部署並完成一次真缺口source-only補件：HTTP200／2.0514秒，14頁已保存於原報告data snapshot；實際僅MOPS索引1HTTP，PDF原件重用HTTP0、模型297406不增。保留PDF原epoch1791762567.4393559、source TTL上限、Q2 2026／file8/19／event9/21與未知首次刊登；原502回應及439882逾時失敗保留；顯式採用原件時HTTP error cache／MOPS guard逐欄保持，後續依既有到期／快取更新流程運作，未手動重設保護。原HTML／Markdown、quote／TTM／core audit／analysis evidence／五品質metadata保持，analysis_text_stale=True仍需重分析，並非新完整報告品質成功。1owned／101preserved＝102runtime、env／158套件、health／ready200、queue0確認；root410及獨立同410／新10反例分開報告，不相加。原20類仍17類strict>80：earnings_call 31/41=75.6098%, financial_statements 32/51=62.7451%, recent_catalysts 116/168=69.0476%；同窗僅此輪native success+1／attempt+1／HTTP+1、cached original與parent排除，其餘19類逐欄相同，財報比率變動是自然離窗。free-only、8／3／30及五年九科目／typed sector與quality gates保持，全goal未完成、沒有commit/push。見[當前正式驗證](evidence/source-acquisition/20261012/nanya-original-reuse-current-closeout.json)、[原件採用與原TTL](evidence/source-acquisition/20261012/nanya-mops-original-adoption-proof.json)、[正式補件](evidence/source-acquisition/20261012/nanya2408-mops-original-reuse-formal-source-refresh.json)及[獨立覆核](evidence/source-acquisition/20261012/nanya-original-reuse-independent-review.json)。


來源改善不會降低報告的 data trust、引用或品質 gate。`success` 只描述該筆觀測的範圍；來源有回應不代表足以支持投資結論。

## 新聞與商品適用性

- 近期新聞以固定分析 cutoff 和設定的 30 天視窗篩選；未知日期、未來日期及舊聞不占近期名額。原連結與日期保留於快照，`news_selection` 記錄排除原因及不足；過大的快照可裁背景，必須標示截斷。
- `source_applicability.py` 是 planner、merge、freshness、trust 的共同能力表。市場沿用既有台股／美股辨識；ETF 必須由明確 quoteType 判定，不以數字代號猜測。
- 台股不因 SEC 空缺告警；ETF 不抓一般公司財報。現有公司估值流程尚無持倉／NAV 分析能力，因此 ETF 分析明確攔下，不產生一般公司 DCF 結論。

## 部分資料與共用快取

- 匯率分 Bank of Taiwan、open.er-api.com、FRED 實際上游；第三方 spot 沒有銀行 bid/ask，幣別覆蓋依實際有效資料分別判定。
- FRED 各 series 分開取得、共用與恢復。籌碼保存 TDCC、融資券、借券各自狀態；合併不會把 partial/stale 改成完整成功。
- 籌碼取得成功但觀測日期缺失時，保留數值並標 `date_status=unknown`、部分覆蓋；不補造日期，也不把未知說成過期。
- PE 的歷史分位與情境假設在 prompt、快照、圖表及審計分開標示。預設倍數不列為取得歷史分位資料。
- 宏觀、匯率、SEC mapping 與職缺／社群使用既有 JSON cache；Redis named lock 或 SQLite file lock 合併同時請求。取得時間不因其他標的命中快取而更新。
- 搜尋冷卻以 provider/endpoint/credential scope 保存，重啟仍有效。429 尊重 Retry-After；拒絕、付費限制與未知 432 不冒稱日額度耗盡。MOPS 安全拒絕頁記為 access_denied，不繞過。
- MOPS 法說會來源發生已分類錯誤時，改查 [TWSE WebPro 公開站外法說會索引](https://webpro.twse.com.tw/WebPortal/vod/101/?categoryId=170)。僅保存相符公司的已完成場次日期與連結，不擷取摘要、影音或逐字稿；保留 MOPS 錯誤，實際 provider 標 WebPro，覆蓋仍為 partial。索引沒有可用場次不代表公司沒有法說會。
- WebPro 最多查兩個分類各一頁三筆，成功 metadata 共用快取一天、有效空結果五分鐘；錯誤沿用持久冷卻。快取保留原取得時間，實際 HTTP 與外層 aggregate 分開計數。MOPS 正常回傳空結果時維持既有本年度／前年度查詢規則。

法人籌碼由 `data_fetch/institutional_provider.py` 統一同步及 registry 取得。共享快取以股票與 lookback 分開：近期觀測沿既有六小時期限，過期觀測十五分鐘再查、有效空結果一分鐘再查；強制刷新仍可繞過資料快取，但不繞過 provider 冷卻。快取保留原 acquisition 時間，另以 `latest_date`／`observed_at` 判斷觀測新鮮度，重新組裝報告不能刷新它們。

缺列不推定零交易。只計相符股票、有效日期與有限非負買賣股數；原始觀測日及實際筆數保留。近期資料仍可能只有部分期間覆蓋，完整五個交易日無法確認時，`last_5_trading_days_net_buy_thousand_shares` 保留空值。來源例外與成功空回應分開記錄，SDK callback 不當作 HTTP 已送出的證據。

## 觀測與年度日曆

SLA v4 僅新增 `details_json`，保留舊資料。新事件保存有界的 correlation、HTTP、cache/stale、error_kind、retry_at 與分項覆蓋；不保存 key、query 或 response body。HTTP 請求、callback/aggregate、快取與本機冷卻分開計數；舊觀測不回填猜測。來源面板的「取得資料率」仍是供應商觀測口徑，不是報告成功率。

Typed 來源錯誤在報告中顯示可讀原因；HTTP code、回應大小、雜湊與 parser 版本保留於結構化診斷，不嵌入報告訊息而被誤認為財務數字。

Agent 19 的原始「避免」輸出，只有原始進場、回補、風險及重評條件共同通過明確無部位契約，normalizer 才保留原文；不將已驗證回補欄位改成 `N/A`，也不替原始缺漏或衝突補造無部位證據。僅更新 Agent 19 快取版本，品質 gate 仍拒絕缺乏明確語意的原始 `N/A`，也不放寬已有部位或附帶價格的檢查。

Agent 19 的非 Gemma 財務 JSON 只移除字串外的排版空白；所有欄位、數值、字串內空白及引用保持不變。輸入仍使用相同容量上限，State、market context 與原始證據不裁切；這與會轉換資料形狀的 dense/table 編碼分開。

品質重寫在 `repair_candidate_history` 保存同輸入、prompt 與上游證據範圍內最近 16 項退件問題，供後續完整重寫做回歸檢查；它不是目前品質判定，也不增加重試次數。Agent 19 在清除候選結構之前，使用既有價格解析與報酬門檻產生前次決策診斷。建議、目標或交易方案改變後必須重新評估市場來源，不複製舊結論的 `market_context_assessment`；證據不足仍保留警示。退件清單沿既有 graph/draft checkpoint 保存，新 metadata 可增加一個 draft 版本，但重複 defer 不重建初稿或重複新增相同版本。

Agent 19 的交易欄位診斷會將通用檢查的 `entry_zone`、`target_price`、`stop_loss` 對回真正 JSON 路徑 `short_setup.entry_trigger`、`downside_target`、`cover_stop`，列出候選原值與同一交易價格解析器的結果。解析成功不等於來源已驗證，無法解析不等於零；不從現價、均線或其他欄位自動代填。回應 schema 說明相同語意，只有 Agent 19 的 step cache 另行分版，品質門檻及模型修復次數不變。

交易日曆保存來源、版本與適用年度。缺年度資料時標 unknown，行情快取使用較短門檻。事件日曆只有成功且明確覆蓋完整未來窗口，才能判定該窗口沒有事件。

每年更新日曆時，從交易所官方年度公告核對 holidays、early closes、timezone、open/close；保留公告 URL、查驗日期與內容 hash，透過版本審查更新 `BUILTIN_MARKET_CALENDARS`。再用正式 Python 執行 `backend/maintenance.py update-market-calendars --year YYYY --market tw --market us`；已有檔案預設不覆寫，確定差異後才指定 `--overwrite`。執行相關 calendar/freshness 測試，並確認載入的 valid_year、calendar_version。沒有官方年度資料時維持 unknown，不複製前一年日期。

RQ 使用 `worker_rq_scheduler.BoundedSchedulerWorker`，維護檢查及閒置 dequeue 等待上限為三十秒，處理重啟快照中的舊排程鎖自然過期後接手過慢的情況。沿用 RQ 的原子 NX 鎖、排程到期條件與 SimpleWorker 執行方式；worker heartbeat 存活期限、工作逾時與 provider 冷卻不變。worker 忙於執行工作時仍依既有執行模型處理，三十秒不是所有排程延遲的保證上限。

## 發布驗證邊界

先執行隔離 behavior checks、歷史快照離線回放及有界來源探測，再部署、確認 runtime commit/health/queue，最後做單一完整報告 canary。canary 必須以 completed job 和新 artifact 的來源／引用／品質結果驗證；`waiting_retry` 不是完成。先通過代表案例才擴大重跑，歷史 artifact 不覆蓋。

OpenAI/Anthropic 未配置有效憑證時，不得標成已驗證的跨供應商備援。沒有近期新聞、未取得法說公告、未驗證年度日曆均保留不足標示。

最終建議局部重跑沿用正式工作 callback，接通模型呼叫、provider request、回應／錯誤及串流事件，保留匿名 key slot 與工作範圍。非同步 callback 必須等待完成；沒有 callback 的呼叫仍走原非串流路徑。品質判定需比對該工作實際回應、稽核結果與新 artifact，事件完整不等於報告通過品質檢查。

Agent 19 的初稿 JSON 範例與資料提示必須對齊既有 short_setup 檢查：SHORT 研究情境的三個價格欄位需要來源支持的正數價格或單一區間，純事件條件不能代替價格；非 SHORT 且無部位時，則如實寫等待條件與無部位。允許可驗證的來源／原值／推導方法，不允許自動挑選其他欄位補價或為通過檢查強迫改分類。提示變更會透過既有 prompt hash/version 使舊輸出快取失效，不修改數值或證據門檻。

財務散文另以同期間、同指標與相符幣別的來源檢查可證的金額量級與符號錯誤，初始範圍為明確年度的營收／淨利及最新 TTM 自由現金流；年度來源四捨五入到 0.01 billion 的精度必須保留，一般數值差異不因此視為單位紅線。billion_twd 是十億新臺幣，轉億元必須乘以 10；缺期間、未知幣別或無可靠來源時不得猜測或補零。錯誤走原品質修復與最終稽核，提供原值、來源路徑及正確換算，不直接改寫正文。若歷史前序分析也有錯誤，最終建議局部重跑不得跳過上游檢查，應完整重跑；舊 artifact 保留。

## 2026-09-25 資料取得修正

- WebPro 公開索引的 `status.code=1`、`pagingObject.totalCount=0`、空 `result` 是有效空結果；不得當成 parser error 而啟動跨股票冷卻。非零筆數卻缺少資料仍屬格式錯誤，索引仍不能代表逐字稿完整。
- 上市融資券優先採用 TWSE `rwd/zh/marginTrading/MI_MARGN` 的同表日期與數量；驗證表頭、分組、唯一股票列及有限非負整數，核心餘額缺失維持 partial。取得失敗保留既有 OpenAPI 備援及其未知日期，不借用借券來源日期。全股票表共用五分鐘快取，強制刷新略過資料快取，但仍遵守來源冷卻與 Retry-After。
- ExchangeRate-API 的 USD 基底回應可同時提供 USD、EUR、JPY 對 TWD 的 spot。EUR/JPY 以 `rates.TWD / rates.<currency>` 換算並保留原始 rates、公式、單位、來源及觀測日期；不能填入臺銀買賣價。備援幣別齊全仍是第三方 spot，臺銀缺口維持 partial。
- 催化劑搜尋以公司為錨點、主題用 OR 聯集，避免要求每篇新聞同時含所有中英文詞；日期、相關性及來源多樣性門檻沿用。缺乏結果時保留有界公司搜尋備援。
- 職缺觀測保留 104/1111 各次查詢的 `component_statuses` 與 `reason_code`，區分解析失敗、傳輸失敗、有效零筆與新聞質性備援。未知職缺數不補零，新聞不計入數量覆蓋。


## 免費官方文件與本機索引（2026-09-25）

- `official_disclosure_sources.py` 從 TWSE `opendata/t187ap04_L`、TPEx `mopsfin_t187ap04_O` 取得每日全市場公告。每市場共用五分鐘快取；一般報告的 `force_refresh` 也遵守此批次間隔及持久冷卻，避免逐股重複抓整張表。合法空回應與網路／格式錯誤分開。
- `data_fetch.official_disclosures_provider` 將有效公告存入 operational DB 的 `source_documents`，僅回傳相符股票近三十日的最多二十件文件。公告日期、事實日期與取得時間分開；重讀快取不刷新原取得日期，日期未知不進日期篩選結果。每日快照及啟用後累積資料都只算 partial，不能證明整段期間沒有其他公告。
- `source_document_index.py` 保存內容版本並按股票、來源類型、日期、中文關鍵字查詢；相同 URL 的不同公告不互相覆蓋。`GET /api/observability/source-documents?ticker=2330.TW&text=董事會&kind=official_disclosure&limit=20` 只讀本機，不觸發爬網。首次使用尚無資料時回空集合且不建立 DB。`since`、`until` 可用 ISO 日期或時間；日期上限含當天。
- 財務核心快取命中時可單獨補公告，不重抓行情或其他來源。公告獨立放在 `official_disclosures`；不增加新聞媒體數、不假冒逐字稿、不推定未來事件日期，也不降低品質門檻。角色 3、5、12、13、21、24 可使用最多六件各一千字的原文片段，明示截斷；取得的文字保留於索引與新報告資料快照。
- `company_ir_sources.py` / `CompanyIrProvider` 初始白名單是台積電、大聯大（3702；聯強為2347）。部署主機對投資人網站／新聞稿四次小型探測全部 HTTP 403，尚無成功全文解析證據，因此 `execute_in_workflow=False`。能力清單保留停用原因；不繞過網站拒絕，也不把搜尋摘要寫成公司原文。正式啟用前必須驗證真實成功頁及其日期、正文和 issuer。

本次來源驗收以公告端點、parser、共用快取、本機索引、正式查詢端點及模型輸入／快照邊界為準；完整報告品質仍須由完成的分析工作與新 artifact 另行判定。

## 公司證據與來源缺口修復（2026-09-25）

- 公司新聞及社群先驗證公司名稱、正式別名或明確股票標記，再計近期可用量。未知日期、過期、未來及無法核對公司的資料不能占用可用名額；URL、出版者及其他數字不作為公司命中。正文可提供身分依據，摘要仍標 `headline_or_snippet`。
- `raw_count`、`usable_count`、排除原因、取得與品質狀態分開保存。來源面板顯示最近一次篩選，不能當作獨立媒體數。排除原件留於快照的 `source_record_archive`／`identity_rejected_catalysts`，通用與直接 prompt 都排除這些欄位；舊快取再次驗證時效與公司。
- 合格新聞不足時最多兩組查詢；無關的原始結果不能終止補搜。搜尋端點共享 single-flight、總期限與連敗退避，Retry-After 是最早恢復下限。GDELT 公司及國際路徑共用冷卻；FMP news 與 quote 權限分開。
- 法人不足時以 TWSE T86／TPEx dailyTrade 最多五個已發布交易日補齊，依日期／類別合併並保留衝突，不相加重複資料。官方缺股列標 `security_absent`，不補零、不據此宣稱停牌；五日取得不代表三十日完整。新 HTTP 受十二秒總預算與每次五秒上限限制，快取忙碌立即略過。
- 上櫃借券獨立使用 TPEx `tpex_margin_sbl`，驗證日期、代號、欄位與股數，與融資券分開判定；兩項全市場表可跨股共用。
- 同業依最新主檔、普通股及 TW/TWO 身分處理，排除歷史下市與特別股，最多十個候選。身分與可用指標分開計數；FinMind 僅補相符股票、有效日期的 PER/PBR，保留來源及期別限制。銀行不硬套毛利率，分類「其他」的個股不強配半導體同業。
- 職缺頁區分 `client_rendered`、`access_denied`、正常解析與格式未知，保存 hash、大小與 parser 版本。招募新聞另驗公司、時效及主題，只能支持質性資訊；未知職缺數維持 null。WebPro 索引、公司 IR 停用與 spot／銀行報價原有邊界不變。

## 搜尋與缺資料重取修復（2026-09-27）

- 台股免費新聞以官方中文名稱、股票代號及既有時間窗查詢，避免把中英文完整顯示名稱當成必須同時命中的條件。先取得最多二十筆候選，再沿原公司、日期與來源多樣性規則選最多五筆；RSS 的出版者標示保留，仍是標題／摘要證據，不能宣稱已讀全文或完成獨立來源核驗。
- 催化劑的 Google RSS 備援也沿用相同的台股公司名稱、代號與時間窗查詢；其他搜尋引擎保留原語法。維持最多兩組查詢、原筆數上限及共用期限，只有合格證據不足才補搜。上游時間提示不能取代本機日期、公司與來源多樣性檢查。
- WebPro 在既有兩個分類內比較合格場次日期，避免第一個分類有舊資料就停止。第二類失敗時保留第一類合格索引，明示比較不完整，快取最多五分鐘；原排除資料及逐類觀測保留。新的選擇快取以參與比較的最早取得時間限制有效期，不刷新原始證據時間；分類快取及來源冷卻不變。取得最新索引仍不代表取得影音、簡報或逐字稿。
- 搜尋端點忙碌時最多等待兩秒，等待及節流時間均計入原總期限。取得租約後再次檢查持久冷卻與斷路保護，取消時釋放租約；不增加 HTTP 重試、不略過供應商封鎖。超過等待上限仍如實記錄本機略過。
- 「創新板股票」及舊拼字「創新版股票」屬板別，不當成同業產業分類。候選上限、業務可比性及指標來源檢查不變；「其他」產業沒有可靠同業時仍保留不足。
- 職缺頁遇到已識別的 JavaScript 空殼、存取拒絕或無法解析數量，可走原有新聞備援。新聞須符合公司、日期與招募主題，同次取得共用相同查詢並按網址或標題去重。原網站失敗原因及新聞實際來源分開保存；新聞只能計為質性資料，不能補成職缺數或完整取得。
- 職缺來源的存在判斷只計有效數量觀測（含確定為零）與合格去重新聞，不再把診斷文字或覆蓋欄位當成資料。空資料進入下一次 optional provider 規劃時可重新取得；既有核心快取快速路徑與各來源 TTL 不變，因此不保證每十分鐘自動重抓。

來源驗收需比對相同股票、相同時間窗的實際可用內容，並檢查正式版本、來源稽核及保護狀態。二十四小時面板保留舊失敗及 partial/degraded 口徑，不能用單次回復推論全日取得率或完整報告品質。招募網站拒絕、無法取得的銀行買賣匯率、沒有公司相符社群／法說資料等缺口仍需揭露。

## 財報備援的取得期限

FinMind 財報備援在原有來源保護之後，使用一個受控子程序依序讀取損益、資產負債與現金流三表。同一官方資料端點、股票及日期範圍維持不變；沿用此路徑原有的空憑證，不自行套用其他設定的金鑰。最多三次資料請求，不再由 SDK 建構過程呼叫額外登入資訊端點，也不疊加 SDK 與外層重試。拒絕、格式錯誤或逾時會停止後續請求。

整組傳輸共用二十秒期限，涵蓋 DNS、連線、讀取與子程序解析；到期由父程序停止並回收該子程序，回應與程序輸出也有大小上限。程序建立及回收仍可能有作業系統排程延遲，不能保證在任意系統故障下精確二十秒返回。原來源節流等待不包含在此網路期限內；既有非同步呼叫經 `to_thread` 執行，上層取消不表示子程序立即停止，它仍受自己的期限控制。

取得部分表格後才失敗時，保留已完成的原始值與分項診斷，來源稽核仍維持錯誤，不因回傳非空字典改成成功。合法空表與傳輸失敗分開：部分表有值、部分為空時標示部分取得，不把空表當成來源故障。補值觸發、傳輸期限與既有來源保護不變；十二月三十一日只證明財期結束日，不能單憑日期認定是全年累計或已確認單位。逐格補值仍需同財期與會計基礎的原始證據。

FinMind 損益表的營收、毛利、營業利益與歸母淨利，必須具有同一年四個精確季末、各季唯一且有限的原始數值，才能組成全年；先以原幣值加總，再換算系統的十億元單位。不再把第四季單季值當作全年。缺季、重複資料、非數值與無法確認的歸屬口徑均保留缺值。歸母淨利須核對原始中文項目，不能拿合併淨利或綜合損益替代。同名的 `EquityAttributableToOwnersOfParent` 在損益表與資產負債表意義不同，必須按表別處理。只選有效的十二月三十一日年度；只有期中資料時，不改標成年度。

資產負債表使用年末時點，不累加四季。FinMind 現金流表的年末營業現金流也不累加四季；已核對的 5314 原件中，此值是全年累計。該來源的設備支出不足以代表 Yahoo 定義的完整資本支出，且實際回應未提供無形資產取得支出，因此保留營業現金流、設備支出與缺口原因，但不再把兩者相加冒充完整自由現金流。來源依原完整性規則維持部分取得，零與負值仍保留，缺值不補零。

這項修正以 5314 的 2021–2025 年實際季度回應和公司正式合併年報核對。四季加總修正的是已取得資料的使用方式，不是新網路取得，也不代表其他公司均已驗證。沒有更改歷史報告、既有二十四小時觀測或成功率公式。

隔離測試入口會設定 `STOCK_AGENT_TEST_NO_NETWORK=1`；財報子程序遇到此旗標，在送出請求前停止。父程序的 socket 測試替身不會跨越新程序，因此不能只依賴原有的父程序網路封鎖。程序生命週期測試只能使用固定、無網路的測試子程序。

年度自由現金流沿用同一期營業現金流加上帶符號資本支出的計算；分項缺漏而無法計算時，可使用同一 Yahoo 年度現金流表、同一財期唯一的 `Free Cash Flow` 原始數值。零與負值均是有效原值，文字、無限值、重複欄位與無法對齊的日期不能補入。實際採用的財期與原始欄位記入來源說明，不補造資本支出，也不跨年度移用其他值。原三表覆蓋稽核仍保留分項缺漏，補到一格不代表整份財報取得完整。

5314 的實際年度回應顯示，2022 年 `Capital Expenditure` 缺值，但 `Free Cash Flow` 已提供原值；過去僅依分項計算會漏掉此值。2024、2025 的資本支出亦包含不動產設備及無形資產取得支出，不能用僅有設備支出的備援欄位直接代替。這次修正使用已取得的同源原值，不增加來源請求，亦不修改既有報告或快取中的歷史數字。

## Yahoo 台灣個股新聞

Optional `YahooProvider` 對已確認台灣股票代號、市場與普通股身分的資料，讀取 Yahoo 台灣股市的公開個股新聞頁。國際版 SDK 對 5314 的實際 HTTP 200 回應為空清單，而台灣頁面有可用公告摘要；這是地區資料覆蓋差異，不能把空清單解釋為額度耗盡。其他市場、無法確認身分的路徑及同步核心 SDK 保留原行為。

地區頁面沿用原供應商保護及正式稽核寫入流程，單次有界 HTTP 取得，不跟隨重新導向、不執行網頁 JavaScript、不追分頁或文章全文。解析器核對頁面股票與市場，只讀該頁指定的新聞串，並明示實際地區來源與網址。格式改變、身分衝突或存取失敗保留錯誤；不能改用其他頁面內容冒充成功。

先取原有十篇文章上限，再套用原公司與三十日時效規則。廣告不當作新聞；舊聞、日期不明及格式不合的文章保留於排除原件，不為提高成功率而略過。5314 已保存頁面的十篇文章為三篇合格、七篇舊聞，仍須標示部分取得；三篇皆中央社財經公告摘要，不能稱三個獨立來源或三個新增事件。排除原件不進模型提示，快照及稽核保留來源限制。


地區新聞傳輸使用系統 curl 的一般客戶端設定。實際對照曾出現同網址 HTTPX 回 404、普通 curl 回 200；時間及整組客戶端設定均不同，不能把差異單獨歸因於 User-Agent 或 HTTP 版本。此調整只供已確認台股的地區新聞頁，沒有模擬瀏覽器身分。

原來源保護與端點排隊先行，curl 只送一次 HTTPS 請求，停用隱藏設定檔，不跟隨重新導向或自行重試。取得作業共用原期限，curl 傳輸最多九秒，父程序最多十秒或剩餘期限後停止並回收子程序；作業系統排程與程序回收時間另計。正文、回應標頭及傳輸診斷都有限制；curl 缺失或版本不支援接收途中大小上限時明確失敗。這個地區傳輸暫不支援代理設定，遇到既有代理配置即停止，不略過代理自行直連。

即使錯誤頁下載逾時或中斷，已收到的 HTTP 錯誤與 `Retry-After` 仍保留並走原冷卻處理。完整回應與部分接收的雜湊分開；curl 結束碼不等於 HTTP 成功，也不等於新聞通過品質檢查。隔離測試的禁網旗標會在真正啟動任何外部程序之前拒絕傳輸。

### 已核對公司法說簡報內容

`company_conference_content.py` 只配置已核對的世紀民生 `5314.TWO` 官網 `/gov_info`。選取索引明示日期的最新中文法說簡報，事件日由民國年月日標題取得；上傳檔名不當作事件日。先核對索引公司名、HTTPS 同主機 PDF 路徑及 PDF 封面的公司名和股票代號。此路徑取得內容後不再探測 MOPS；失敗才走原有 MOPS／WebPro，保留真實失敗。其他股票不改路徑，也不啟用原先被拒絕的 Company IR。

單次索引／PDF 使用普通 curl、禁止重新導向或重試；索引最多 2 MiB、PDF 最多 16 MiB，公司索引與 PDF 內容取得共用 40 秒預算；逾時、租約失效、忙碌或來源保護不可讀時直接停止，不繼續另一來源。一般上游拒絕才走既有 MOPS／WebPro 備援，其既有期限獨立保留。設定代理而無法忠實套用時停止，封鎖狀態儲存異常時停止，不換身分繞過拒絕。既有有限共用鎖與 24 小時內容快取避免重複下載；快取維持原取得時間。

固定 `pypdf==6.19.0` 在獨立子程序抽取原生文字：最多 100 頁／200,000 字元、解析 10 秒，另有輸出、解壓串流、CPU 與記憶體限制。macOS 使用父程序採樣 RSS，兩次採樣間可能短暫超量，並非作業系統硬位址空間限制；逾時終止並回收子程序，回收另有 2 秒上限。沒有 OCR、模型摘要或財報數值補值。空白／影像頁及明確亂碼保持 partial；原生文字各頁存在也不保證圖像、圖表讀序或投資結論完整。因此本路徑的來源內容仍為 partial，native_text_coverage 另列，不以抽字器的局部 complete 增加成功分子。

索引與 PDF 分別留下真實請求觀測；只有外層合併摘要排除於取得率。實際 2026-04-15 簡報共 60 頁、59 頁含原生文字，第 22 頁為影像，故兩次觀測皆保留 degraded，文件數仍為一，沒有新增完整成功分子。資料取得率公式、舊紀錄與品質 gate 均不調整。

簡報原文只透過 `conference_presentation` 派生提示提供給 Agent 3／5／12；依可見角色關鍵字與頁序選取最多 12 頁、每頁 1,000 字且總量 6,000 字，保留選取方式、省略頁數、頁碼、事件日、URL、原件及節錄 hash。公司宣稱不當作獨立查證；不得從圖片或黏接數字補推財務資料。逐字稿欄位始終獨立，Agent 20 缺逐字稿仍略過且顯示資料不足；簡報內容不進其逐字稿證據；共享 State 與通用 RAG 也排除新簡報文件，原逐字稿與其他既有文件保留，避免繞過角色及篇幅限制。

### 免費入口核查邊界（2026-10-04）

- [勞動部公開職缺資料服務](https://data.gov.tw/dataset/44062)實測可回傳當日更新的 JSON，但單次最多 1,000 筆；以 `世紀民生科技股份有限公司` 精確篩選為空。這只證明該資料集的查詢沒有該公司紀錄，不能推論全市場零職缺，也不能補成 104／1111 的即時職缺數。該入口目前不接入 5314 的數量欄位。
- [104 世紀民生公司頁](https://www.104.com.tw/company/a5hnqe0)於 2026-10-04 的公開搜尋索引顯示「工作機會(3)」，因此勞動部資料集的空結果不能解讀為公司沒有職缺。正式服務主機對該公司頁直接請求，正常瀏覽器 User-Agent 收到 403 驗證頁，服務識別則只得到沒有職缺內容的 JavaScript 空殼；[公司官網招募頁](https://www.myson.com.tw/recruit)只連到 104 搜尋，未明列即時數量。搜尋索引的數字不是正式服務即時取得的公司職缺清單，暫不補入 `job_count` 或當成取得成功；後續需找可直接取得且允許使用的原始入口。
- [證交所人力發展 OpenAPI](https://openapi.twse.com.tw/v1/opendata/t187ap46_L_5)與[櫃買中心人力發展 OpenAPI](https://www.tpex.org.tw/openapi/v1/t187ap46_O_5)於 2026-10-04 可直接回傳年度 ESG 人力資料；同次核對到上市 2330、2882 及上櫃 5314 的公司代號、114 年報告年度和明列的薪酬欄位。這是免費的**年度人力指標**入口，不能推論目前招募職缺或取代 104／1111 的即時數量；若接入，應另設年度人力來源與稽核，不改寫現有職缺取得率。

2026-10-04 已接入獨立 `annual_workforce` 來源：依上市／上櫃市場共用每日官方資料集快取，逐公司驗代號、申報年度、出表日期、員工平均薪資及單位；非主管薪資中位數或女性主管占比缺失時保留部分資料，不宣稱完整。來源稽核保留官方 URL、年度、出表日與完整回應 SHA-256。此資料只代表年度人力揭露；`alternative_data` 的即時職缺來源與 24 小時取得率維持獨立，舊失敗不改寫。

2026-10-04 補入[證交所上市公司基本資料](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)與[櫃買中心上櫃公司基本資料](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O)的法定全名查核。原先只有少數股票手動提供 `legal_name`，其他股票無法進入 104 精確雇主職缺查詢。新入口按市場共用每日快照，逐筆要求股票代號、公司簡稱、十四日內出表日及法定名稱一致；來源失敗、過期或身分衝突則維持原搜尋路徑。公司基本資料只提供雇主身分，不是職缺證據；資料可信度計數會重新檢查官方來源、雜湊、出表日與本公司身分，只有 104 個別職缺的公司全名、雇主代號、連結與日期也通過原門檻，`alternative_data` 才計入取得成功。當日實測 2882、5314 的官方名稱可核對，但 2882 的 104 即時查詢仍未取得可用職缺，不能宣稱取得率已提高。

2026-10-04 再補入[國泰金控官網連出的官方招募站](https://www.cathayholdings.com/holdings/career)。僅對 2882 上市金控、法定名稱與股票身分一致時查詢公開職缺清單，逐筆要求官方公司別 `C0`、可投遞、開放中、獨立職缺編號及官方詳細頁；其餘集團子公司一律排除。儲存查詢時間、原始回應雜湊及有限筆數的職缺樣本，資料可信度再次驗證來源、時效與每筆身分。即時資料只代表招募站回傳的金控本身當下開放職缺，不推定刊登日期、全網職缺總數或 104／1111 取得成功；原來源失敗原因與部分覆蓋狀態仍保留，舊 24 小時紀錄不回寫。
- [ToAlpha MOPS MCP](https://toalpha.tw/MCP/MOPS) 實測能回傳 5314 的現金流量表申報原值及千元單位；2025、2024 年度營業現金流、設備及無形資產取得與公司原件一致。但其[現行條款](https://toalpha.tw/terms)僅授權個人非商業使用，禁止轉供服務或作為批量資料庫來源；正式服務不將它當成免費備援供應商。只有取得適用授權及完成來源精度／期別驗證後才可重新評估。
- [世紀民生官網](https://www.myson.com.tw/financial)及[交易所文件入口](https://doc.twse.com.tw/server-java/t57sb01?co_id=5314&colorchg=1&filename=202504_5314_AI1.pdf&kind=A&step=9)的合併財報可公開下載。現有有界 PDF 讀取器對 2024 年檔可取得含現金流的頁面（整份仍為 partial），對 2025 年解析警告及 2022 年加密檔會拒絕；同一檔案改由交易所文件入口下載，並未消除限制。不得因個別頁可由寬鬆解析器讀出就關閉警告或把完整五年自由現金流標為已取得。

### 交易所原始 XBRL 年報備援（2026-10-04）

公開資訊觀測站另一個官方入口 `mopsov.twse.com.tw/mops/web/t203sb01` 可提供合併年度 iXBRL 下載。新備援只接受同一公司代號、連續五個年度、Q4 合併報表的明列 IFRS 科目；逐筆驗證期間、TWD 單位、千元倍率、正負號、欄位唯一性。資料 payload 的來源稽核保留每份官方 URL、SHA-256 及原始新臺幣數值；持久觀測另保留每年度檔案雜湊與整組摘要雜湊。自由現金流使用同年度營業現金流加上明列為負的設備與無形資產支出；缺值不補零。5314 的 2023 年無形資產支出是 2024 年申報比較欄明列的零，非缺欄推定。資料衝突、格式不符或五年不齊時保留失敗觀測，回到原 Yahoo／FinMind 流程。

直接讀取已核對 5314、2330、2317、2454 的 2021–2025 五年資料。下一年度合併年報若對上一年度九個必要欄位都明列，採該份較新的完整比較期數值，並在稽核保留每個舊值、修訂值及兩份申報年度；原年報缺欄而由比較欄明列補入的值也另記為 `missing_fact_fill`。有衝突但比較欄不完整仍拒絕。1101 的修訂可完整核對；金融服務業的銀行、保險與證券公司欠缺此套一般產業科目，因此已知金融服務業別不嘗試此一般產業科目路徑，仍走原有財報來源。此入口改善年度財報取得，不能代表其他來源類別、完整報告品質或 24 小時面板已達 80%；歷史失敗照原觀測窗口保留。

同一來源的斷路器由多家公司共用。單一申報文件缺欄、格式或比較欄衝突現在仍記為該公司失敗並啟用原備援，但不累積成共用斷路；官方主機拒絕、限流、伺服器錯誤或網路故障仍累積斷路，避免反覆衝擊來源。這不會把缺欄報表計為成功，亦不改寫既有觀測。2026-10-04 隔離測試含跨公司失敗後成功及主機故障仍斷路，相關 225 項通過；正式服務重新啟動後 API、Worker 就緒，4 件既有排程保留。24 小時資料取得率仍包含舊失敗，須待後續真實工作觀測才能評估改善幅度。
- 近 24 小時面板中的 5314 重複觀測使職缺、同業與財報缺口持續出現。改善入口需提供同公司、同財期、完整欄位及允許正式服務使用的證據，再沿原 provider audit 記錄真實取得；舊紀錄保留至時間窗自然結束，不能改分類、減分母或把空結果當成功。

2026-10-04 續查：Yahoo 未回傳產業時，2882 等金融股會誤入一般產業 XBRL 五年欄位路徑，造成可預期的缺欄與不必要的 MOPS 請求。現改以已載入的 FinMind 台股主檔補充**分類判斷**，限七日內、同代號、同上市／上櫃市場、且與主檔最新日期一致的紀錄；過舊或身分不符即不採用。實測當日主檔 2882／2881 為「金融保險」、5314 為「其他」、2330 為「半導體業／電子工業」。這只避免把金融業硬套一般產業報表，不補造缺少的銀行財報科目，也不增加財報成功分子。104 公司頁雖可由既有搜尋供應商的頁面擷取取得公司整體職缺內容，仍缺 1111 即時數量及每關鍵字覆蓋，且額外擷取會消耗免費額度；目前不把它當成 104／1111 完整取得。

同日增加金融業**獨立科目** iXBRL 讀取器：需要連續五年 Q4 合併申報，逐年驗公司代號、期間、TWD、千元倍率、科目唯一性與支出符號。取得利息收入、利息淨收益、手續費淨收益、金融業「淨收益」、母公司業主淨利、資產、權益及現金流，保留官方 URL、文件雜湊與比較期修訂；只在五年該套科目完整時記其自身來源成功。金融業「淨收益」不塞進一般產業 `revenue_history`，也不補造毛利／營業利益。原 Yahoo／FinMind 歷史欄位和品質判定仍獨立，模型提示只在 `history.financial_institution` 明示原始金融業口徑與十億臺幣換算。

即時官方文件試讀：2882、2881 的 2021–2025 五年完整通過；2882 有六筆比較期修訂並保留原值，2883 因 2022 年比較期衝突且不完整而拒絕，2855 文件超過既定安全大小限制而拒絕。這些拒絕不算成功，也不放寬來源上限。5314 的同業主檔仍為「其他」，無法用舊半導體分類或無人機題材名單冒充可比同業；1111 即時職缺仍未取得。5314 官網法說影音公開頁目前沒有字幕軌，不能推稱已取得完整逐字稿。

同日新增 Yahoo 股市公開的台股「同業比較」產業排名作為**候選名單**來源。僅接受 URL 與公司代號一致、頁面資料日期在七日內、逐檔名稱／代號／市場可由當期 FinMind 股票主檔核對且共享細分產業的前五筆；保留原頁 URL、回應 SHA-256、產業及排名。這是網站發布的產業分組，不證明產品、營運、規模或估值數值可比，報告輸入明列 `business_comparability_verified=false` 與 `numeric_comparability_verified=false`。已實測 2882 金融業與 3014 半導體頁各取得五筆；5314 的「其他」／「櫃其他」分類仍拒絕。供應商快取命中與失敗分開記錄，不能把沿用快取當新取得，原搜尋失敗觀測亦不改寫。

同日找到 104 網站實際使用的公開職缺 JSON 搜尋入口，已接入精確公司全名的有限分頁查詢。查詢結果包含贊助及模糊比對職缺，故**不採用頁面 `total` 當公司總數**；只保留公司全名、單一雇主代號、職缺代號與連結、30 日內刊登日期皆可核對的逐筆職缺。內容過大、分頁內容不完整、日期或雇主衝突、找不到精確職缺時都維持未知，絕不推定零。5314 的法定全名由其公開公司資訊核對，2026-10-04 即時查得 3 筆精確職缺，另 6 筆混入結果遭排除；`job_count`（關鍵字數量）仍為未知，1111 驗證頁仍不可用。來源可標示「已取得 104 當期公司職缺樣本」，同時保留 `coverage_status=partial`、1111 失敗及非全網總數的說明；歷史失敗不回寫，24 小時取得率須待新工作自然累積後再驗證。

19:27 台北時間以 2882 強制刷新完整資料流程驗證：`alternative_data` 官方來源讀到 117 列，僅 111 列屬金控本身且開放可投遞，有限樣本 10 筆通過身分與時效再查；正式來源稽核為 `success`、`record_count=10`、`coverage_status=partial`，104 與 1111 各自不可用，報告資料信任狀態為 `fresh`。相關隔離測試 362 項通過，正式 API 與 Worker 重啟後儲存及佇列就緒。19:28 的 24 小時面板僅 20 類中的 13 類超過 80%；職缺 13.4%、同業發現 1.5%、動態同業指標 9.4%、法說會 38.5%、財報 21.1%、近期事件 73.7%、社群 69.4%。近一小時職缺及社群皆有真實新資料，但舊失敗仍留在 24 小時視窗。[世紀民生 113 年度年報](https://www.myson.com.tw/public/uploads/pdf/20250512_111654_OeTOx.pdf)揭露工程、銷貨、廣告與餐飲等不同業務，未給出可直接認定為整家公司可比同業的名單；不得將上游供應商或泛「其他」分類股票硬補成同業成功。

同日續查 [證交所 5314 年報索引](https://doc.twse.com.tw/server-java/t57sb01?co_id=5314&colorchg=1&mtype=F&step=1&year=115)所列修訂後 114 年年報：2025 年銷貨收入占 77.44%、佣金收入占 16.35%，主要銷售生技產品，佣金包含保險經紀。這比 113 年年報更接近當前業務；[5314 公司基本資料](https://www.myson.com.tw/company_info)亦列主要經營保健食品批發、零售。[2026-04-15 官方法說簡報](https://www.myson.com.tw/public/uploads/pdf/20260416_102334_7PIQY.pdf)也呈現保健食品與無人機等多業務，沒有明列可核對的整家公司同業。搜索同業時不得再套舊半導體或無人機主題；保健食品製造商也不能只憑產品交集就當作整家公司估值可比同業。

新增 [國泰金官方投資人頁](https://www.cathayholdings.com/holdings/ir)作為 `2882.TW` 法說活動入口。只選已完成、明示日期的中文法人說明會，保留公司官網活動頁、PDF 與直播連結；HTML 本身不等於簡報或影音已讀取。即時頁面取得 2026-08-28 第二季法說資訊，原始來源觀測可列 `success` 且 `record_count=1`，彙總報告仍為 `metadata_only`／`degraded_enrichment`、`transcript_available=false`。簡報禁止複製、再流通或傳送第三人，因此不抽取或轉供 PDF 內容；若官網無可驗證活動或取得失敗，退回既有 MOPS／WebPro 並保留來源失敗。此入口只改善 2882 法說資料連結的直接性，不能宣稱全類別超過 80%。

同日新增 [MoneyDJ 當期食品生技名單](https://www.moneydj.com/z/zh/zha/zh00.djhtm?A=C017108&B=6) 作為 `5314.TWO` 同業**研究候選**入口。5314 在 FinMind 當期交易所主檔屬廣泛的「其他」，因此原 Yahoo「櫃其他」頁仍拒絕；MoneyDJ 的具日期名單則直接列出 5314。解析器核對固定頁面標題、5314 與候選股票的代號／名稱／市場、七日內逐列日期及回應雜湊，最多選五筆，按股票代號排序只為限制輸出數量，**不是相似度排名**。名單不證明整家公司業務、規模或財務比率可比，仍標示 `business_comparability_verified=false`、`numeric_comparability_verified=false`，也不自動補成 `dynamic_peer_metrics` 的估值比較。當期 [櫃買中心食品生技價值鏈](https://ic.tpex.org.tw/introduce.php?ic=C300) 雖有保健食品通路名單，其 5314 個股頁仍落在舊的裝潢分類，不能用來聲稱交易所已把 5314 歸為食品生技。新來源的快取命中不算新網路取得；既有失敗與 24 小時分母維持原樣。

20:10 台北時間的正式服務重啟後，API、Worker 與佇列就緒，5314 完整資料流程取得五筆候選且仍保留搜尋來源空結果；307 項相關隔離測試通過。正式 24 小時來源面板仍僅 20 類中的 13 類超過 80%；職缺 21.4%、動態同業指標 9.8%、法說會 40.7%、財報 25.9%、同業發現 1.4%、近期事件 74.7%、社群 71.4%。新來源首次實抓成功，但完整流程沿用四小時共享快取，因此這次快取命中不灌入「新取得」分子。後續須以自然出現的真實請求及舊紀錄離開 24 小時窗口再驗證；目前不能宣稱達標。

同日再查 5314 動態同業指標：同步核心已在本次抓取執行 `FinMind/yfinance`，因當期主檔只有廣泛「其他」分類而回傳空名單；缺值補抓流程原本立即再執行同一收集器。現在只在同一 `fetch_id` 可查到具 `operation_id` 與真實 provider attempt 的核心來源稽核時略過即時重試；舊快照或另一次抓取仍可重試，原空資料與失敗觀測不改寫。隔離測試先重現重複嘗試，修正後 5314 正式資料流程的動態同業紀錄由「基礎摘要、核心嘗試、重複補抓」變為「基礎摘要、核心嘗試」，候選名單仍五筆。此修正減少無效請求，沒有產生新的同業數值或證明 80% 達標。

另外核對 5314 官網與 MOPS 的 2026-04-15 中文法說 PDF：兩個網址下載結果 SHA-256 完全相同，皆為 60 頁，換入口不會補齊影像頁。官網英文版為另一份 93 頁簡報，內容並非逐頁對應的中文逐字稿；不能拿它替代缺失頁，也不能把現有 `partial` 改為完整取得。法說稽核中同一 `operation_id` 的兩列是來源紀錄與合併摘要，面板已排除摘要，並非重複讀取 PDF。

修正已在同日正式服務重啟，138 項相關隔離測試通過；實際 5314 完整抓取仍保留五筆 MoneyDJ 候選，動態同業指標稽核只剩基礎摘要與一次核心實抓，沒有即時第二次補抓。重啟後 `/readyz` 的儲存、佇列均通過，API 的 24 小時取得面板為 20 類中 13 類超過 80%，仍未達成逐類門檻。

同業發現改為先讀 Yahoo／MoneyDJ 已發布的當期名單，再按結果決定是否呼叫廣泛搜尋。只有至少兩個不同股票代號的候選逐筆通過既有日期、發行人、代號與來源驗證，才省略廣泛搜尋；出版名單缺失、過期或驗證失敗仍使用搜尋備援。5314 的單次完整實抓由有效 MoneyDJ 快取保留五筆候選，未再呼叫先前反覆回空的 `Alternative Search`。快取沿用、候選發現與可用於數值估值比較仍是三件不同的事：不把快取命中算成新的網路取得，也不把候選升格為已驗證同業指標。隔離測試另確認出版名單不足時會啟動搜尋備援。

20:36 台北時間在正式服務載入此順序；`/readyz` 的儲存與佇列皆通過、佇列待處理及執行中工作均為零。相關隔離測試為 150 項通過，包含快取名單過期時不得省略搜尋；另有一項 5 毫秒極短 deadline 的既有測試在整組執行時對超時發生位置不穩定，單獨執行通過；本次沒有改動其實作。正式面板 24 小時仍只有 20 類中的 13 類超過 80%：同業發現 1.4%、動態同業指標 9.5%、職缺 28.4%、財報 30.5%、法說會 40.7%、近期事件 75.4%、社群 73.7%。此輪節省無效查詢，尚未使逐類門檻達標。

背景追蹤的 `report_catalyst` 若條件**完整且明確**寫成「月營收低於 N 億元／萬元」，改為只取 FinMind 月營收，按最新月份與明列數值判斷；其他文字條件仍沿既有完整資料流程。月營收必須有可解析的年月、與評估日相距不超過 45 天的月末日期、沒有同月矛盾值；利用來源顯示的兩位小數精度，只有可能的上界也低於門檻才觸發。若來源缺失、過期、格式不明或未達門檻，均不排入分析工作。這使已設定的 5314「月營收低於 5 億元」不再每 15 分鐘重抓與該條件無關的財報、同業、法說與社群。2026-10-04 單次正式來源探測只取得 `monthly_revenue` 六筆，最新 2026-08 為 4.65 億元，數值條件成立；探測本身沒有排入報告工作。正式背景追蹤隨後再次評估，依既有「同日 false 可轉 true」規則把當日未命中改為命中，自動排入一件 5314 模式 C 報告 `8b0416ffb70a4321814be2224c60e204`；已為 true 的同日事件不會再新增第二件。

此輪 watchlist／provider 相關隔離測試 81 項通過，正式 API、Worker 與佇列重啟後就緒。上述自動工作於 20:55 完成並產生新的 v3 artifact，`report_lint`、`final_audit`、`evidence_exit_gate` 通過，但 `content_credibility` 與 `report_conformance` 仍有全球市場／國際新聞脈絡未具體評估的警示；完成工作不等於報告無品質警告。20:56 的近 24 小時資料面板仍僅 20 類中 13 類超過 80%；舊失敗紀錄不回寫，須以後續自然工作及時間窗更新重新驗證。

同日晚間修正台股新聞備援判斷：免費新聞 waterfall 即使已有至少三篇日期、連結及發布者可核對的近期文章，仍可能因同批原始搜尋結果有舊聞／不相關內容而保留 `degraded_enrichment`。只有該來源明列 `quality_status=eligible_evidence`，且另一個獨立搜尋來源也各有至少三篇合格文章、合計至少五個不同連結與兩個發布者時，才省略 Yahoo 地區新聞請求；任何缺少品質標記、重複連結、過期文章或第二來源降級仍照舊使用備援。拒絕原件與部分取得狀態不改寫。隔離測試 109 項通過；21:11 對 5314 的單次完整實抓保留免費新聞 `degraded_enrichment`（五篇）、Alternative Search `success`（八篇），並未再呼叫 Yahoo 新聞。這是少一次冗餘請求的即時證據，不代表 24 小時各類取得率已達標。

21:13 正式 API／Worker 重新載入後，`/readyz` 儲存與佇列通過，待處理及執行中工作皆為零；`/api/observability/provider-sla?window=last_24h` 仍只有 20 類中的 13 類超過 80%。未達標者為職缺 31.5%、動態同業指標 9.8%、法說 40.7%、財報 33.3%、同業發現 1.4%、近期事件 76.1%、社群 74.6%。官方 iXBRL 成功時已在年度歷史提取器中先行返回，不再讀取 Yahoo 年度三表；面板的 Yahoo 三表 30 次部分取得屬較早真實紀錄，不需要再加一層跳過邏輯或回寫舊事件。近一小時財報與社群已有真實成功觀測；5314 的官方簡報因未讀影音、圖像及圖表閱讀順序仍屬部分內容，廣泛「其他」類別也沒有已核對的整家公司數值可比同業。這些限制不能靠改標籤或以候選同業數值填補。

21:19 重新核對免費同業入口：[凱基證券 5314 公司頁](https://superpy.kgieworld.com.tw/kgipythonapi/stockInfo/companyDetail?stockCode=5314)雖列「主要競爭對手」，頁面最後更新日為 2026-07-22，所列皆舊 IC 設計公司；其營收構成也仍是較舊的工程、銷貨、廣告與餐飲比例。這與[5314 當前公司基本資料](https://www.myson.com.tw/company_info)及[114 年度合併財報](https://www.myson.com.tw/public/uploads/pdf/20260408_142001_yqHso.pdf)揭露的保健食品和多元子公司結構不能直接對齊，不得導入整家公司估值同業。[公開資訊觀測站財務比較 E 點通](https://mopsfin.twse.com.tw/index)提供使用者自行選公司比較的原始財務數值，沒有發布 5314 的已驗證同業關係；也不能把任意使用者選項當成同業發現。現有 `peer_relationship_evidence.py` 已要求具日期、具名兩公司及明示業務對比的來源，這些入口不符合，不需放寬。官網[法說檔案頁](https://www.myson.com.tw/gov_info)仍提供簡報和影音連結，沒有官方逐字稿；網路上的 AI 摘要不是可核對的完整逐字內容。

21:24 追查另一個免費法說入口：[FinmoConf 的 5314 頁](https://finmoconf.diveinvest.net/presentation/69df9084bab52fb5c8e803de)所謂「音訊錄音」實際指回同一支[公司官網列示的 YouTube 影音](https://youtu.be/IYt2-pqx_Go)，其中文／英文 PDF 也指回 MOPS 原件；頁面其餘敘述是自行整理，含預估數值，不能當作新的獨立逐字稿或已驗證財務數據。直接查該影音公開字幕清單未取得內容；這只證明該次無憑證探測沒有返回字幕，不足以斷言影音永遠沒有字幕。此入口不新增可計完整法說來源。後續若要從影音補原文，需做有界音訊取得、辨識、分段與人工可追溯校驗，並保留轉錄不確定性；不能把 AI 摘要直接改標完整取得。

本機可用 `ffmpeg` 與 Whisper CLI，但沒有已下載的 Whisper 模型，也沒有可用的 `yt-dlp`；這不是已建成的免費轉錄供應商。即使日後取得音訊並跑完語音辨識，該場為多家公司聯合法說，仍需核對發言公司、時間戳與漏聽段落，才能把內容歸屬 5314。缺少這些驗證時，轉錄只能是待查線索，不能提高 `earnings_call` 的完整取得分子。

21:28 重新下載[公司 2026-04-15 法說 PDF](https://www.myson.com.tw/public/uploads/pdf/20260416_102334_7PIQY.pdf)，回應檔案 SHA-256 為 `e54b29e5aca753b6959fef1216f42b7bcd3f269eb406596167001d90730f8549`，共 60 頁。實際渲染第 22 頁可見無人機地面影像與畫面座標疊字；這不是單純漏抽的一頁文字，OCR 只能補局部疊字，無法還原影像示範、動態或講者說明。因此保留 `native_text_coverage` 與 `full_content_coverage_verified=false` 的邊界，不因 OCR 猜測將此 PDF 提升為完整法說內容。

以 21:29 正式觀測事件依原 `provider_acquisition.observation_kind` 做唯讀滑動視窗推算，且**假設後續完全沒有新事件**：舊失敗自然離開後，近期事件最早可能於 10/05 12:00、社群 15:30、職缺 17:25、財報 17:55、法說 19:27 超過 80%；這些不是預報實際服務一定會達標，真實新失敗、快取或沒有取得嘗試均會改變結果。同一推算中，`dynamic_peer_metrics` 與 `peer_discovery` 在現存成功／失敗先後順序下沒有非空且超過 80% 的窗口。兩類須取得新的合格來源事件，不能單靠舊紀錄到期，也不能補造請求或改寫分母。

### 替代免費入口實測（2026-10-05）

- [櫃買中心上櫃一般業綜合損益表](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci)及[資產負債表](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap07_O_ci)均回傳 HTTP 200 JSON、884 筆；以**欄位 `SecuritiesCompanyCode` 精確等於 `5314`** 查得各一筆「世紀*」115 年第 2 季資料。損益表明列營收、營業利益及 EPS，資產負債表明列資產、負債及權益；2026-10-05 實際回應的出表欄位為 `1151004`。[政府資料開放平臺損益表](https://data.gov.tw/dataset/94853)與[資產負債表](https://data.gov.tw/dataset/91967)列為免費、政府資料開放授權條款第 1 版。上市對應的[證交所一般業損益表](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci)同日回傳 HTTP 200 JSON、1,049 筆，精確查得 `2330` 一筆。這是**最新季報摘要的可用備援**，不是五年合併現金流與自由現金流，也不自動滿足目前 `financial_statements` 的完整年度歷史門檻；若接入需核對報表期別、合併/個別口徑、單位與官方原件。
- [櫃買中心上櫃每日重大訊息](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O)及[證交所上市每日重大訊息](https://openapi.twse.com.tw/v1/opendata/t187ap04_L)同日回傳 HTTP 200 JSON，分別為四筆與三筆；上櫃回應沒有 `5314`，因此這次只驗證入口可用，**沒有取得 5314 新事件**。[政府資料開放平臺](https://data.gov.tw/dataset/18418)列上櫃資料每日更新、免費及政府資料開放授權條款第 1 版。這可作具公司代號、發言日期與主旨的正式事件備援；無公告時必須保留空結果，不可把其他公司公告或來源可連線算成 5314 近期事件成功。
- [櫃買中心 5314 產業價值鏈](https://ic.tpex.org.tw/company_chain.php?stk_code=5314)雖可 HTTP 200 讀取，目前仍標「建材營造 > 裝潢業」。它與[公司現行經營資料](https://www.myson.com.tw/company_info)不符，不能作 5314 當期食品生技或整家公司估值同業的驗證。標為 free 的 [TWMD 同業對照組文件](https://twmarketdata.com/zh-TW/docs/api/structure-reference/company-peer-groups)也明說分組是推導判斷、不是官方分類；其[免費方案](https://twmarketdata.com/en/pricing/free)限非商業使用且需金鑰，不能視為此正式服務已有可部署的免費同業來源。

此次僅調查並記錄入口，未改 provider 或正式服務。正式 24 小時面板於調查時仍為 20 類中 13 類超過 80%；未達標的七類為職缺 37.1%、動態同業指標 11.7%、法說 44.0%、財報 41.3%、同業發現 1.7%、近期事件 78.2%、社群 75.8%。新的季報摘要及當日無 5314 紀錄的公告入口不能直接填補同業、完整法說、社群或五年財報缺口；後續接入須先以報告實際用到的欄位寫行為測試，再觀察自然工作的真實來源事件。

### 產品別與同業入口續查（2026-10-05）

- [公開資訊觀測站各項產品業務營收統計](https://mopsov.twse.com.tw/mops/web/t05st08)是另一個免費官方原始入口。實際從 `ajax_t05st08` 以歷史資料、115 年 8 月、公司代號查詢：2002 回傳鋼鐵產品等有金額的產品別資料；5314 與 7780 均明確回傳「採用 IFRSs 後採自願申報，該公司無申報」。再查 5314 的 114、113 年 12 月也無申報。因此這是可用於**有自願申報公司**的產品結構線索，不能填補 5314 的當期產品別資料或同業取得成功。查詢空結果保留空結果。
- [5314 公司官方 114 年度合併財報](https://www.myson.com.tw/public/uploads/pdf/20260408_142001_yqHso.pdf)第 56 頁的客戶合約收入細分列示：生技產品 1,620,533 千元、合併營收總額 2,973,547 千元，產品占比約 54.50%；其他明列服飾配件、生活用品、電子產品、佣金等。這能校驗**114 年度產品結構**，不能推定 115 年當季比重，也不能把「銷貨收入」總項解讀成全是保健食品。MOPS 2025 Q4 合併 iXBRL 原件實際可下載，但未包含這段產品別附註文字；目前不能靠既有九個一般財務科目的 XBRL 解析器機械地得到產品別資料。
- [AHI Journal 的 5314 頁](https://ahijournal.com/stock/5314)列出數家「同做保健食品」的公司，並估計保健食品約占 77%；該頁沒有逐項對應公司申報原件，而且此比重與上項 114 年度公司原始揭露的 54.50% 不符，至少不能視為同年度、同口徑、已核對數字。其[授權說明](https://ahijournal.com/disclaimer)明列禁止未經書面同意的自動擷取、衍生資訊服務及對外報告資料源，因此只保留為人工調查線索，不接正式 provider，也不將產品競爭名單提升為整家公司估值同業。即使有產品重疊，5314 的多元合併營收仍需另核對可比口徑。

本次沒有新的合格 5314 整家公司估值同業或完整法說原文，因此沒有改 provider、品質 gate、正式服務或歷史觀測；上列入口也沒有新增可計入 24 小時面板的取得成功。

### 免費官方券商同業入口（2026-10-08）

[政府資料開放平臺的證券商基本資料](https://data.gov.tw/dataset/20765)列為免費、政府資料開放授權條款第 1 版；其[證交所 OpenAPI](https://openapi.twse.com.tw/v1/opendata/t187ap18)當晚回傳 64 筆。與[證交所上市公司基本資料](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)當晚 1,095 筆按**營利事業統一編號**連接後，2855 統一證與 6005 群益證分別有相同業務種類「經紀、自營、承銷」；上市股票代號不能誤用為證券商代號。新增的候選入口要求兩份名冊日期在 14 日內、統編非零且唯一、公司簡稱與七日內現行股票主檔一致，並保留來源 URL、回應雜湊與兩側統編；取得失敗或快取過期仍回原候選路徑。官方相同業務種類只決定優先嘗試順序，還須由下游細產業與有值的逐欄指標核對，不能冒稱全面業務或規模可比。

隔離測試 60 項通過。以當晚真實官方名冊及 Yahoo 指標對 2855 單次試讀，新增候選 6005 的細產業同為 `Capital Markets`，有本益比 7.32 與股價淨值比 1.34，來源稽核顯示 `official_broker_candidate_status=success`。正式 API／Worker 尚未重新載入這項工作區修改，因此正式 24 小時面板仍無此修改的後續來源事件；23:57 的觀測為 20 類中 13 類高於 80%，動態同業指標 36/60（60.0%）。這次不回寫舊失敗、不以程式單次試讀當正式取得率改善。

另查[經濟部全國五大超商資料集](https://data.gov.tw/dataset/32086)：平台列有統一超與全家的公司統編，官方上市／上櫃公司名冊也能對到 2912 與 5903。但原始檔下載端在本機發生 TLS 憑證驗證錯誤，且現有細產業來源把兩者分為 `Grocery Stores` 與 `Department Stores`。此入口暫作待查候選，不停用 TLS 驗證，也不提升為可用的動態同業指標。

### 櫃買中心最新交易日法人 OpenAPI（2026-10-09）

[政府資料開放平臺的上櫃股票三大法人買賣明細](https://data.gov.tw/dataset/11856)列為每日更新、免費、政府資料開放授權條款第 1 版；櫃買中心[官方 OpenAPI](https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading)於台北時間 10 月 9 日凌晨回傳 2026-10-08 共 892 筆。全部 892 檔與原有具日期 `dailyTrade` 回應按代號核對，外資、投信及自營商買賣超均一致；5314 分別為 -2,508,317、0、-61,862 股。新入口只提供最新交易日，因此僅在查詢最新已完成交易日、達保守收盤後重查時間且回應日期相符時優先使用；其餘日期、較早時段與新入口失敗仍由原有具日期來源取得。解析器要求固定完整欄位、逐欄整數、日期／代號唯一及買賣淨額與總額相符，保留原始 HTTP 回應雜湊；最終採用仍須通過既有收盤後原始來源憑據核驗。回應中的 `Dealers -TotalSell` 與 `Dealers-TotalSell` 實際有 118 檔不相等，不把前者推測為自營商總賣出。

本機隔離相關測試 56 項通過；另用當晚 892 筆原始回應寫入暫存憑據，再由 `institutional_admission` 重讀及核對 5314 三類數值，得到 `eligible=true`。正式服務尚未重新載入此次工作區修改，故直接抓取與測試不計入正式 24 小時取得率。同期正式面板仍有七類低於 80%，其中法人約 56.8%；該比率會隨真實請求與 24 小時視窗變動。

### 台灣就業通免費職缺入口試讀（2026-10-09）

[勞動部台灣就業通職缺清單](https://data.gov.tw/dataset/44062)為免費政府開放資料，含公司名稱、職務、職缺網址、更新日及截止日；其[官方介接說明](https://free.taiwanjobs.gov.tw/webservice_taipei/A17000000J-030144-Taiwanjobs-OpenData.pdf)只列縣市、郵遞區號、職業代碼及最多 1000 筆的回傳限制，沒有公司精確查詢參數。本機以 TLS 驗證連線 `free.taiwanjobs.gov.tw` 成功，`COUNT=1000&T=CSV` 回傳 1000 筆；其預設 XML 標籤含全形括號，標準 XML 解析器拒絕，故若接入須採 CSV 並保留原始回應。全國與台北市、新北市、桃園市各取上限 1000 筆後，找到一筆雇主精確為「群益金鼎證券股份有限公司」的職缺，更新日 2026-09-02、截止日 2026-11-02；同批未見 5314、2330、2855 的精確雇主。各查詢都碰到 1000 筆上限，因此缺列不能解讀為該公司沒有職缺；既有近期職缺標準也不可因截止日尚未到而放寬更新日。勞動部另一 JSON 主機 `apiservice.mol.gov.tw` 在本機 TLS 憑證檢查失敗，不關閉驗證。此來源保留為只在精確雇主與新鮮度通過時可用的候選，尚未接正式 provider，也未計入取得成功。

### 證券商五年官方 iXBRL 科目修復（2026-10-09）

正式財報來源事件顯示 2855 的五年金融業 iXBRL 反覆因 `FilingError` 退件。本機讀取[公開資訊觀測站 iXBRL 原件入口](https://mopsov.twse.com.tw/mops/web/ajax_t203sb01)的 2855 2021–2025 年五份合併年度申報，確認每年均有 `ifrs-full:Revenue`、`ifrs-full:BrokerageFeeIncome`、`tifrs-bsci-bd:RevenuesFromUnderwritingBusiness`、歸屬母公司淨利、資產、權益及三項現金流欄位；原解析器要求金融控股／銀行的 `tifrs-bsci-fh` 淨利息與淨手續費科目，這三項在五份證券商原件都不存在。新增 `broker_consolidated.v1` 專用解析及報告投影，要求五年連續、原件身分／幣別／期間與原始數值相符，保留五份 SHA-256；不把證券商申報營收改標為銀行淨收益，也不補入一般產業毛利。真實 2855 再試讀成功取得 2021–2025 五年及各年九項申報科目；2882 原銀行／金控解析仍成功。相關隔離測試 82 項通過。2851 的官方索引僅列 `A` 個別報表，沒有 `C` 合併報表，故保留五年合併缺口，不將個別報表冒充合併。此修復尚未讓正式服務重新載入，不能計為正式 24 小時取得率提升。

另查[CMoney 個股社群頁](https://www.cmoney.tw/forum/stock/5314?tab=discuss)作為社群候選：本機 `curl` 以系統憑證可取得約 1 MB HTML，頁面有同學風向摘要，但伺服器 HTML 未直接列出可逐筆驗證的貼文連結；正式程式所用 Python HTTP 傳輸因憑證鏈缺少 Subject Key Identifier 而拒絕。此時不能把 AI 摘要當原始貼文，也不關閉 TLS 驗證來提高社群取得率，因此未接入。

### 104 大型搜尋分頁驗證與社群入口複查（2026-10-09）

修正 104 搜尋分頁的過度拒絕：`lastPage` 包含贊助與模糊比對搜尋結果，超過三頁並不妨礙前 1–3 頁的逐筆職缺查核。現仍最多讀三頁，逐頁驗 `currentPage`、分頁總數一致、公司全名、單一雇主代號、職缺連結及 30 日日期；來源結果另記 `searched_page_count`、`pagination_truncated`，超出三頁明示 `bounded_company_recent_postings_sample`，`job_count` 保持未知。即時讀取 2855 前三頁驗得 66 筆、1216 驗得 42 筆，皆為同一雇主代號的近期樣本，不是公司整體職缺總數；這是本機讀取驗證，正式 24 小時取得率仍待載入修改後的新工作驗證。

同日 00:30 左右正式 24 小時面板仍為 20 類中 13 類超過 80%；低於門檻者為 `alternative_data` 26.5%、`dynamic_peer_metrics` 67.6%、`earnings_call` 42.6%、`financial_statements` 30.2%、`institutional_trading` 64.4%、`recent_catalysts` 67.1%、`social_sentiment` 25.0%。這些是正式服務尚未載入本次修正的舊／當期真實事件，不得回寫。[PTT Stock 搜尋](https://www.ptt.cc/bbs/Stock/search?q=1101)的 1101、6409 首頁分別出現 20、5 篇候選，但標題內的股票代號文都超過 30 日有效窗；空結果不是解析器錯誤。[CMoney 6409 公開頁](https://www.cmoney.tw/forum/stock/6409)的伺服器 HTML 仍無可驗證的逐筆討論文連結，且 Python 驗證其 TLS 憑證鏈失敗；故這兩個入口尚不能把社群類補到 80%。[證交所上市公司資料](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)的 2330 統編與 104 雇主代號前綴相同，104 雇主名稱另有括號簡稱；此為可進一步核對的身分候選，尚未放寬精確雇主規則。

隨後接入官方簡稱與統編的窄範圍雇主別名：僅在當期證交所／櫃買名冊的公司代號、法定全名、簡稱、統編與出表日期皆通過既有驗證，且 104 回應的雇主名稱**剛好**為「法定全名(官方簡稱)」、雇主代號剛好等於統編數值加 `000` 時，才把該職缺歸入該公司；逐筆連結與 30 日刊登日期門檻不變。資料信任計數會重新驗證官方收據、原始雇主名稱及代號，篡改其中任一項都不計數。以 2330 當期[證交所名冊](https://openapi.twse.com.tw/v1/opendata/t187ap03_L)與[104 公司頁](https://www.104.com.tw/company/a5h92m0)核對，三頁樣本只驗得 1 筆近期職缺，非 104 頁面顯示的總職缺數；本機資料信任計數也是 1。另以首頁只讀抽查，2206、1229、2912、6282 有 10、10、30、30 筆近期且同名雇主列，2851 有 1 筆；2891、2308 前三頁仍無可接受職缺，保留未知。305 項相關隔離測試通過。正式服務未重新載入，不能聲稱 24 小時面板已改善。

### 證交所／櫃買同業估值 OpenAPI（2026-10-09）

新增[證交所上市個股本益比與股價淨值比](https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL)、[櫃買中心上櫃個股本益比與股價淨值比](https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis)為台股同業缺值備援。10 月 9 日即時回應分別有 1,082、885 筆；逐筆代號核對後，2330 的 10 月 7 日 PE/PB 為 29.96/10.42，5314 的 10 月 8 日為 5.86/4.39，2855 的 10 月 7 日為 5.99/1.92。解析器限定正確市場、單一代號、七日內原始觀測日期、有效正數，並保留官方來源 URL、回應雜湊及每個指標的來源與日期。官方兩項都有值時省下對 FinMind 的同業估值查詢；只有一項時仍可從 FinMind 補另一項，官方已驗欄位不得被覆蓋。市場全表共用短效快取，避免每個候選同業重抓同一官方回應。這只補 PE/PB，不推定業務可比性、毛利率或整組同業指標完整；面板仍要求選中同業的所有適用指標具備值，單有 PE/PB 不計完整成功。

另外即時確認[證交所上市損益表](https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci)及[櫃買中心上櫃損益表](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci)、[資產負債表](https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap07_O_ci)均公開 2026 年第 2 季資料，5314 的官方損益與資產數值可逐欄讀取。這些資料目前是當期季度彙總，不能替代既有五年合併年度 iXBRL 的完整財務報表門檻，因此先列為待接入的補充來源，沒有讓 `financial_statements` 記成成功。正式 API／Worker 尚未重新載入本段新程式；當時 24 小時面板仍有 7 類未達 80%，不得以單次直接讀取宣稱正式成功率提升。


### 恆大完整免費法說簡報與原生符號核對（2026-10-12）

1325.TW 已接入恒大官方法說資料目錄及其直接發布的完整 PDF。來源身分須與保存的完整 TWSE 公司主檔代號、法律名稱、統編及官網一致，並核對索引活動日、公開下載參數與簡報封面；保存三份原件、取得時間、完整 bytes/hash 後，重新解析全部原生文字页。每次傳輸沿匿名普通 curl、單次五秒、總期限二十秒、不跟隨 redirect 或重試、原有冷卻及單一租約規則。

原件 31 頁有 46 個 U+F0A1，來自確切已核對的 Wingdings2 嵌入程式與 ToUnicode，原字形是單一封閉實心方塊；只有完整 visitor 與原生文字相符、獨立符號片段、字型／CMap／CID 雜湊及身分全吻合才轉為 U+25A0。未知字型、夾雜文字、變更 CMap 或其他無法辨識字元仍保持 partial／拒收。原始 PDF 不改寫；文字取得完整不等於影像、圖表閱讀順序或陳述已驗證，整体內容 coverage 仍 partial，逐字稿仍 false。

一次正式既有報告來源補件 HTTP200、7.3987 秒，兩個實際 HTTP 取得完整索引及 637,681 bytes PDF；保存後重播 31 頁／46 個符號一致。原股價、財報、取得時間、HTML／Markdown、分析證據及五品質 metadata 保持，仍需重分析。獨立覆核發現的失去租約／逾時錯誤型別與移除來源標記後可略過原件核對兩项缺陷已修正，原 red 與 finding 保留。見[正式補件原件](evidence/source-acquisition/20261012/uk1325-formal-source-refresh.json)及[修正覆核](evidence/source-acquisition/20261012/uk1325-P2-fixed-independent-review.json)。

實際面板又發現彙總列多算一次取得，原始三筆 ledger 及第一次 closeout 保留。僅精確新 UK provider 且 explicit aggregate 的 parent 排除，兩筆 native 與所有其他 legacy／失敗紀錄保持；同一個保存的 24 小時窗口 4,677 行讀回，法說 30／39 修正為 29／38、其餘十九類完整相同。冷／暖 parent 的 HTTP false 與 workflow source HTTP 分開，不再偽稱另一請求；原帳本不改寫，不為修正計數重抓成功簡報。見[多算判定更正](evidence/source-acquisition/20261012/uk1325-first-closeout-counting-discrepancy.json)與[同窗修正證據](evidence/source-acquisition/20261012/uk1325-counting-same-window-before-after-proof.json)。原二十類須各自有樣本且嚴格超過 80%，原新聞 8 篇／3 個發布者／30 日、五年九科目或既有 typed sector schema 與品質、配額、TTL 門檻不變。

2026-10-12T07:28:51.126990+08:00 最終計數修正已正式重載，99份runtime／env／158套件核對，health／ready200、原source max439880／usage max729590及LLM count297406保持。原20類17達標，法說29／38、財報54／87、近期135／189；完整343項隔離及獨立同343、17原探針、7新探針通過，不相加重複套件。[最新正式查驗](evidence/source-acquisition/20261012/uk1325-counting-current-closeout.json)取代第一次closeout的parent排除判斷；原檔及三筆ledger全部保留。


### 新完整免費法說原件與當日場次選擇修正（2026-10-12）

2026-10-12T08:13:53.266684+08:00 新完整免費法說原件續查與當日未開始場次選擇修正：南亞科2408 MOPS年度完整索引及其實際發布英文簡報，匿名native200、保存原件與收據讀回；PDF656632bytes／14原生文字頁、empty／garbled無，封面Q2 2026及檔案日期2026-08-19與後續9/21、9/15、8/20場次分開，不推定首次發布日、完整影像或逐字稿。RGB色碼數字不當財務觀測；來源用途資格及正文投影仍待接入，未列正式成功。實際新年度索引在早上列當日15:00尚未開始場次，保存原件重播18→17，過往17列及原檔案日期逐欄保持。修正public解析器以單次Asia/Taipei aware時間導出日與時，list終日及same-day start一致；未知或無效當日時間不猜測、start已到不聲稱實際已完成。獨立午夜P2原finding與red保留、已修正覆核；root350及獨立同350／原7探針分開報告，不重複相加。1owned／98preserved＝99runtime正式重載，env／158套件、health／ready200、queue0、原四MOPS與UK補件artifact／job／dispatch／zero／439872與432041保持。冠西新英文完整body仍parser warning且初始local reader呼叫停點遺失原epoch／duration，保持unknown、不重新下載；舊中文exact292 xref offset本地重播仍34頁partial，page31地圖非空白，不放寬reader。3native研究請求、2份直接保存200收據及1次由保存body前提推得200；研究未列正式分子。正式source max439880／usage729590／模型297406未增，原20類17類嚴格>80：earnings_call 29/38=76.3158%、financial_statements 36/55=65.4545%、recent_catalysts 135/189=71.4286%，全goal未完成。free-only、原8/3/30及五年九科目／typed sector、quality／TTL／cooldown／quota保持，沒有commit/push。見[最新正式查驗](evidence/source-acquisition/20261012/post-uk-new-free-entries-and-mops-same-day-current-closeout.json)及[修正覆核](evidence/source-acquisition/20261012/mops-same-day-P2-fixed-independent-review.json)。

南亞科入口為 [MOPS年度法說索引](https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1) 的既有公開POST表單，及實際發布的 [完整英文PDF](https://mopsov.twse.com.tw/nas/STR/240820260819E001.pdf)。核對原TWSE完整代號／法律名稱／統編／官網、精確2408原索引列／檔名及PDF公司footer，不由英文簡稱推定主檔法定英文全名。[新原件資格](evidence/source-acquisition/20261012/nanya2408-new-regulated-complete-presentation-original-final-qualification.json)保持private source qualification，未推定商業重用許可、未啟用正文provider。冠西新完整英文原件及舊PDF xref因果重播均另保存，仍有無法辨識字元及真正影像地圖，不以空頁例外放行。ASE parent IR已得403、不换身份或proxy再試；健策原confidential限制保持。38個真正一般產業財報缺口仍要求完整五年九科目與同口徑，舊入口／已保存成功文件不重抓來刷率。


### 南亞科正文取得器部署、首次逾時及完整舊原件重用資格（2026-10-12）

2026-10-12T09:18:40.243091+08:00 南亞科MOPS準備簡報collector／角色投影／原件核對已正式部署，但首次真缺口補件502未成功，原報告仍欠正文。6owned／96preserved＝102runtime、env／158套件與health／ready200、queue0核對；conference_presentation_prompt是既有檔新加入保護、不是新增module。Root400及獨立同400／14原boundary／7lifecycle探針通過，重複套件不相加。原crossissuer改名red、獨立三P2／red保留並已關閉：完整200本地PDF問題留原document error cache、不停用全MOPS；暖讀觀測best effort、後續lease／deadline再查；當次失敗PDF也計workflow HTTP，舊cached error不重算。遠端403／429／503及不完整response timeout原guards保持，aggregate parent HTTPfalse；活動／filedate／季度／未知pubdate分開，兩精確RGB前綴只省略模型摘錄、原文保持、每角色200word，transcript／image／claim不升格。唯一source-only正式請求6.8964秒；MOPS索引success17列、PDF failure timeout／HTTP200／294912接收bytes，未取得完整原件，沒有用部分body或假完整補入。transport returncode／prefix hash／complete等欄位未全保留在現SLA allowlist，未知不推算。原report三artifact／quote／TTM／core audit／analysis evidence／五quality metadata全部相同，原429/504及439872／432041／新439882 failure不抹除、沒有第二次API重試，模型297406不增。全24h原行保存、相同窗口僅本次native success+1／attempt+2／HTTP+2、parent排除、其餘19類逐欄不變；不以研究／offline當新成功。用本次真正MOPS完整索引與已保存8時的完整PDF、本期主檔再次讀回：14native頁可組出嚴格context，保留pdf原epoch1791762567.4393559和quarterQ2 2026／file8/19／event9/21，但仍是未seed cache、未正式保存的recovery candidate，不能當這次原件取得或報告補件成功。最新原20類17嚴格>80：earnings_call 30/40=75.0000%、financial_statements 33/52=63.4615%、recent_catalysts 116/168=69.0476%；其餘比率變動是自然離窗，全goal未完成。free-only、8/3/30、五年九科目／typed sector、quality／總20秒／reader／quota／cooldown／TTL保持，沒有commit/push。見[真實首次逾時與當前驗證](evidence/source-acquisition/20261012/nanya-mops-first-timeout-current-closeout.json)、[原API回應及失敗紀錄](evidence/source-acquisition/20261012/nanya2408-mops-formal-source-refresh.json)、[既有完整原件重用資格](evidence/source-acquisition/20261012/nanya-mops-existing-complete-original-recovery-candidate.json)、[三P2覆核](evidence/source-acquisition/20261012/nanya-mops-three-P2-fixed-independent-review.json)。


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


## 2026-10-13 FinMind論壇角色及新聞補件結論有效性

`news_source_roles`僅判已觀測的CMoney直接論壇article數字URL；adapter不接受外部social_channel覆寫，續查維持原3日期／10秒及guard。selector与freshness共用source_type=finmind_news角色判讀，論壇原URL/date/receipt留archive或unverified；普通editorial及既有direct social保持。

source-only不重跑正文或quality。`report_refresh_diff`比較selected／additional新聞內容、canonical URL、出版日、publisher；替換論壇／更正新聞需needs_rerun，只有抓取收據／排序／封存不耗新模型。單件已錯標current的legacy補正需真before／actual after完整bytes／SHA，只標四保守metadata旗標與canonical index，不從當前data修造unknown分析packet或freshen quote／TTM／quality。[实际6152修正](evidence/source-acquisition/20261013/6152-news-change-staleness-metadata-repair.json)。

PSC2855的完整12頁PDF仍是研究候選，未啟用、未算SLA，原件文字不證影片、影像、精確場次或五年已查核財報。[資格限制](evidence/source-acquisition/20261013/psc2855-new-complete-free-entries-final-qualification.json)。


## 2026-10-13 PSC原件來源與失敗計數

`2855.TW` 使用 `market_sources.psc_conference`／`psc_conference_transport` 原生匿名GET取得首頁、原公開公告、清單與PDF；只接受已核對的官網與原exact link，4請求各5秒上限／provider共20秒，HTML700KB／PDF8MiB，無proxy、redirect、retry、auth或TLS繞過。原公司主檔fresh完整cache用原epoch與HTTPNone憑證，不偽作HTTP200。24小時原件期限包含主檔，暖cache重播不新增HTTP或成功觀測。

真SourcePdfError timeout保留typed timeout並阻止額外fallback；reader／comparison／copy交付後都重查相同provider deadline。source-only consumer另以既有2秒核對窗驗原件，逾時／無效映射502且不merge／覆寫原snapshot。PSC每個原件有native observation；父彙總無論成功／失敗都`http_request_sent=False`、optional aggregate，HTTP放`source_http_request_sent`，失敗原件不刪除。公開失敗反例4原件（3成功／1timeout）只算4次取得、1次失敗。

private `psc_conference_receipt`不進模型prompt。可見角色保留日期依據、公告場次狀態、time／timezone／content_period及partial閱讀限制；原生文字完整不等於全圖表或逐字稿。`report_refresh_diff._stable_call_evidence`對新增／變更本文要求needs_rerun，純receipt bookkeeping不觸發模型。正式單件補12頁本文／四HTTP結果、原品質警示保持：[正式證據](evidence/source-acquisition/20261013/psc2855-source-only-live-readback.json)。研究原件／isolated fixture與provider健康不替代全20 SLA驗收。


## 2026-10-13 source admission 與實際來源嘗試

`source_audit._mark_unentered_admission_block`只用本次source_operation中真實provider_attempt trace；typed CircuitOpen／RateLimitOpen在lazy callback前被擋住且trace為空才可HTTPFalse／local_block／0usage。保留unavailable／error及品質語意。callback內拋出的同型錯誤不能宣稱無請求；預建awaitable可能已在外執行，同樣維持transport unknown。不用exception文字去推斷HTTP429，不從未知歷史資料回填0。

月營收same-fetch失敗重用加入嚴格typed localblock分支，仍需exact current fetch／ticker／provider／operation、uncached、notstale、marker真／HTTPFalse／整數0／空trace。原epoch、TTL、兩月份partial與失敗audit保持。隔離ledger／APIusage的0單位不是正式provider證明；部署後新guard仍未自然發生，不要用synthetic audit插入正式台帳或改guard做展示。[正式identity與歷史保持](evidence/source-acquisition/20261013/source-admission-final-current-proof.json)。


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


## 公開維護契約：來源補件與證據

- 外部來源走 `data_fetch` 的 provider 與 audit；route 不直接繞過來源 admission、期限、冷卻或同時執行限制。
- 月營收官方 CSV 備援只表示該快照實際提供的月份；缺公司、缺月或缺值保持未知，不冒充六個月歷史、TTM 或年度財報。
- 原始 HTTP bytes 的 SHA-256、精確 URL、HTTP 狀態與取得時間由 `official_response_evidence.py` 保存。一般原件上限 8 MiB，只有明確允許的路徑可到 16 MiB；重新讀回仍核對路徑、長度與雜湊。
- 法說須核公司、活動、附件與原件鏈。會議季度不等於財務季度；單季與累計、合併與個體、預估與實績、圖像缺漏與翻譯限制不得混用。
- `report_source_refresh.py` 的來源補件不改寫原分析結論、HTML、Markdown 或既有品質判定。`analysis_text_stale` 表示分析需要重新執行，不能以資料補件直接宣稱報告通過。
- 年度財務依 `annual_financial_source_provider.py` 的 schema 和每年原件核對；金融業與一般業使用各自契約。未披露金額不能自行補零；只有具明確科目勾稽證據的既有規則可以接受可證明的零。
- 取得率保留實際成功、失敗與降級的分母。有效快取、metadata、離線重播與模型生成不當成新的原生來源取得成功。
- 測試一律經 `tests/run_prompt_boundary_tests.py` 隔離 SQLite、Redis、API 與模型。公開邊界測試不需要本機操作紀錄；私有原始樣本與執行收據另外保存。

這些是程式維護與驗證契約，不是正式來源取得率或新報告品質的完成證明。免費入口目錄見 [公開來源目錄](free-source-candidates-2026-10-09.md)。
