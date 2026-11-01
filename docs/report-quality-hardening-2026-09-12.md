# 四模式報告品質：系統修正與交付證據

## 2026-11-01 工程整合範圍（優先於下方歷史進度）

本次依使用者新決定，只整合工程接點並準備部署，**canary 保持停用**。
`backend/canary_release_policy.py` 為寫死的拒絕政策，沒有環境變數或 API 開關；
凍結輸入、raw／semantic claim、enrollment、dispatcher、campaign 建立／送件、
owned runner 均在來源／Redis／帳本／子程序副作用前拒絕。公開
`--maintenance-arm` 在讀計畫或改維護狀態前拒絕。既有嘗試的唯讀盤點、
原 owner 停止與結算工具保留，但不代表可以自動接管或重播。

正常啟動經來源綁定的 Python owner → owned Bash → API／worker；仍使用原
Redis、排程、報告與 checkpoint。正常報告原 seal 驗證與覆寫失敗復原、
watchlist intent／lease／ACK 及取消收尾沿用現行 main；不復活已移除的舊品質投影。
私有診斷只統計指定 cohort 的事件，請求、供應商 quota、本地阻擋、其他錯誤與
品質拒收分開，`qualified_success_rate=null`，不讀正式資料庫補造品質結論。

下方 2026-09 的預算、時限、模型、來源／計費核准與測試數字都是歷史證據，
**不是本次新授權或目前資格**。本次不呼叫模型、不恢復或重設舊 campaign，
不宣稱真來源、計費、四模式品質或正式 canary 已驗收；未完成框架繼續保留。
隔離測試只以顯式 Python mock 驗 dormant 實作，停用政策的負向測試不套用該 mock。

## 統一收尾方案（2026-09-14，已集中核准；S0 部分完成）

**目前決策接點（2026-09-16，唯讀接續核對）：** 舊 scheduler 的缺失不是再寫一個
判定 helper 就能還原的資料。原 baseline 真 WAL 反例已證明 claim 與 completion 產生
相同日期觀察；空 queue、exit0、terminal job 或 `readback_complete` 均不證明未決 claim
為零。首次移交需要真正 quiescence 證據，或對精確未知項目的另行處置決策；不能自動
補 job ID、重送、改日期、清 queue 或把 unknown 改成 settled。完整 controller 仍待實作，
但新增一個永遠 false 的 helper 不能冒充這項能力已完成。
獨立唯讀覆核確認相同結論：baseline觸發成功也不補event.job_id、job／RQ不帶claim關聯，
且retention／cleanup會刪去舊證據。保留不重送須明示接受可能漏派與歷史未知；補做則
須精確新工作與模型預算。後續最多只能證明獲准處置與資料保全，不能改稱歷史結算已證明。
本輪尚無正式受影響筆數或持有者真值，不預先授予任何處置或正式停止操作。

本輪另核對原 S0 的8小時主動工時上限與05:07保守牆鐘收尾紀錄：沒有精確帳本能證明
尚餘多少主動工時，不能把牆鐘時間等同主動工時，也不能把續作視為無限新增額度。
先前續作在這項餘額紀錄上不足；保留所有已完成修改／驗證，不據此推定新批次仍有餘額。
本輪未開始新的產品實作或測試批次，只核對既有原碼／收據並收斂下一次有界執行條件。
375px商業組合頁是前節明示排除的既有問題；曾考慮作獨立修正，但核對原邊界後沒有改碼。

**集中待確認的有界續作提案（尚未核准，不執行）：**

- 另給最多4小時連續工程窗口，用於原維護／安全移交與必要隔離整合；包含一次正式側
  唯讀 metadata 盤點以列出精確未知 claim／程序及 Redis ownership。只讀指定本系統
  SQLite metadata、程序身分與 Redis server/config metadata；不讀／輸出金鑰、不改業務
  紀錄、不發 signal、不 SAVE／CONFIG SET／SHUTDOWN／消費 queue。共用 Redis 不擴權。
  未決 claim 的處置仍須先有具體清單，不預先授予猜測重建或跳過原安全條件的權限。
- 在上述窗口內另開最多2小時、100次唯讀 HTTP（失敗／重導向亦扣帳）、最多17份新增
  公開官方 IR／財報／法說文字來源，累計 corpus 不超過原30份；只補金融業逐字稿與
  cohort來源缺口。不登入、新增金鑰、購買服務、音訊轉寫或呼叫模型；保存原97-GET
  ledger與13份來源不改，新增窗口用新收據，不把已過期的103次剩餘額度重新啟用。
- 模型152 jobs／2400 physical HTTP与transport各自上限／160M tokens／US$50估價
  停送線、首次live後7日與S0–S4 gate保持原樣，不要求重核准整體模型預算。
  仍需實際匿名key slot→Google project→tier／billing對照；不能由公開價目或檔名
  推定免費，也不能只用「核准」取代帳戶證據。請提供遮蔽後證據，不提供金鑰。

本輪實際來源讀回仍13份、4個逐字稿候選、0份`qualified_for_live=true`，台達390缺字
保留；corpus SHA256 `7c7c51f10c00115415d646e468bc218324ec0540ed0a7bc99586a0d48dbc1eeb`，
原HTTP ledger SHA256 `577c6f0365be194af88828342cd3e59f31f6a840b17034f63a4ceaa50aea442b`。
來源窗口已到期，沒有新增GET／provider呼叫；正式Git仍clean。這是尚缺條件與範圍的
校正，不是新模型成功率、正式claim盤點、工程驗收或整體完成。

**最新接續（2026-09-16，來源載入綁定切片已驗）：** 公開 entry 與私有 dispatcher
共用19份已核对 source buffers；十個 controls／七個 harness 均核對實際 loaded identity，
拒絕舊 bytecode／外來同名／預載與 reload，child admission 前再驗。末版相關
**193 passed**、真私有 child 四模式／品質拒收／停止／漂移 **11 passed**、獨立原反例
與載入覆核 **36 passed**，均0 failed／0 skipped、重疊不相加。前版29項完整派發／roster
另保留版本界線。下一片為舊 scheduler claim 歧義處置與資料保存移交；S0／整體仍未完成。
以下833／56項是上一切片證據。本輪0新provider呼叫，未commit／push／部署／重啟。

**最新接續（2026-09-16，原預算結算切片已驗）：** original-owner cleanup-only
reservation 驗真、禁止 child 再建 Python 程序與 RQ ACK 後的 job budget 結算已接上，
保持無退款、不重送、不放行 stage。另修復首個停止打斷 SDK 清理，晚到取消只等待
同一有界 close task。末版同碼 **833 passed** 交叉回歸、**56 passed** 真私有 Redis／
四模式／正常 child 整合，均 0 failed／0 skipped；獨立反例覆核已關閉。
原 55 passed／1 failed 與前版 827 passed 保留、不相加；不是 S0／整體發布完成。
本輪 0 新 provider 呼叫，未 commit／push／部署／重啟；詳細證據及限制見下方新節。

**前一切片（2026-09-16，獨立逾時／取消監督已驗）：** 已接原 reservation 的
monotonic deadline、單次 TERM、獨立 session／group 與退出讀回；長時間 wait 不再
卡住停止，journal 被改或回傳物件被改亦不能偽造成功。最後修改後定向 **208 passed**、
真私有 Redis／正常 child／四模式 **11 passed**，兩個 P2 經獨立唯讀覆核關閉。
較早 814／41／40 項回歸另列版本界線，不與末版測試相加。不是 hard real-time、
逃離 session 的 descendants 證明或 budget settlement；整體 S0／發布仍未完成。
本輪 0 新 provider 呼叫，未 commit／push／部署／重啟。詳見「獨立逾時與原紀錄讀回」節。

**上一切片（2026-09-16，原父程序 admission 已驗）：** 受限 dispatcher 已接
真一次性 pipe admission，綁 child PID／ticket／manifest／reservation／operation；
新 lane 不再建立合成 watchdog-start claim，保留舊 watchdog 相容路徑。
同碼 **805 passed／193.43 秒**交叉回歸、**40 passed／349.96 秒**真私有 Redis／
正常子程序／四模式與順序案例全部通過。另舊啟動／Redis 保留 37 項及真舊 API 2 項
分別通過，原路徑過長 failure／未供封存檔 skip 保留。原收據降級 P2 已由獨立覆核
22 項定向測試確認關閉。完整 controller、deadline／descendant／budget 結算、
正式移交／release／rollback、來源／billing／live 仍未完成；沒有新增正式入口權限。
本輪 0 新 provider 呼叫、未 commit／push／部署／重啟。詳細證據見「原父程序送件准入」節。

**上一切片進度（2026-09-16）：** 私有 canary 登記→semantic claim→真 owned normal job→
RQ terminal 結算的離線接線已驗證；同一 roster 的四模式依序結算，v2 拒收時保留 v3/v4。
另修正 FinMind／nest_asyncio 的 async-generator 登記缺漏，清理期間新建但未關閉者
不得取得成功收據。最後真私有 Redis／normal child 整合 **30 passed／271.81 秒**，
同版交叉回歸 **643 passed／180.62 秒**，均 0 failed／0 skipped；獨立原始反例已關閉，
重疊／較早結果不相加。完整 controller 的正式移交／dispatch／budget 與 descendant
結算／release／rollback 仍未完成，不能寫成只等市場。
研究來源、實際計費與 live S1–S4 亦未通過；0 新 provider 呼叫、0 live-qualified samples，
正式 checkout 仍 clean `75824229`，未提交／發布／重啟。詳細新證據見下方 9月16日接續各節；
後續歷史紀錄保留原時點與結果，不合併重疊的測試計數。

**目前結果（2026-09-15，維護整合候選）：** 已接上可持久保存的維護閘門、一般啟動與
Worker 啟動保護、分析 admission、RQ 每次取件、watchlist／decision 排程與週期清理。
維護階段只到 `cooperatively_drained`，不是正式 `protected` 或 canary 放行。
拆分後 root 啟動／guard／worker 回歸 **112 passed**；periodic 最終 **743 passed**、
watchlist 最終 **672 passed**，交叉覆核無該限定範圍的未解重大問題，重疊不相加。
私有真 RQ／原 CLI smoke 與既有 RQ 同版 26 passed、原三份 artifact replay 1 passed、
兩項隔離 browser 2 passed、商業 UI 原 8 項通過。商業 UI 另有既有 375px 排版反例，未修。
首次整庫的 13 個 campaign 失敗已定位並修正為舊 timeout 測試的 SDK 狀態污染，
同順序加永久反例 35 passed。最後整庫為 **12,750 passed／1 failed／23 skipped／
1 deselected**；唯一 failure 是沙箱禁止 Chromium 啟動。相同凍結碼的原 preflight／
frontend 10 項已在精確工具升權後全部通過，但不把原整庫 XML 的 exit 1 改稱 exit 0。
原 6 項 Chart.js browser tests 亦已全部補驗通過，保留真 CSP／資料、版本與像素斷言。
先前 705 項 campaign helper 證據保留，但不冒稱覆蓋本次新 backend 修改。
13 份官方文件及 4 份未資格核准候選不變；2330／9月12日與 2412／9月14日通過 v4
核心技術來源必要條件覆核，尚非完整 source_review／預登記。本批新模型外送=0、
live-qualified samples=0；
DEV 基底 `cf0ab0d1` 的工作樹已有本批修改，正式 `main` clean `75824229`（已再次唯讀
核對），未發布／重啟；這不是正式 API／Worker 載入版本的健康證明。
其後新增舊版 API 私有探測與唯讀 readiness、真 Redis 最後保存／回載隔離證據；同版
維護接點加 raw canary claim 最終 **220 passed**。這些元件尚未接成正式移交 controller；舊 scheduler 排空、
受限 canary／rollback、來源資格／金融業逐字稿、實際計費 review 及 live S1–S4
仍未完成，不宣稱全部完成或四模式成功率提升。

**21:48 Taipei 接續更新：** 依使用者「繼續執行」完成下方 frozen-input 窄切片；
不重設來源／模型／費用預算，不把先前保守牆鐘界線改稱精確主動工時帳本。
正常 job → pipeline → SQLite checkpoint 已接上凍結輸入身分與拒絕舊 state 的防線，
但正式 controller／不可覆寫 publication 尚未完成，因此 frozen job 保持發布前硬停止。
本次限定回歸 **371 passed／8.19 秒、0 failed／0 skipped**，包含新 80 項診斷；
不是四份真模型 canary 合格，也不與前述 220／整庫案例相加。正式 checkout 仍 clean
`758242290e795146520f58f68ffa113cac35e52c`，本輪沒有正式 DB／Redis／API 操作、
新模型呼叫、commit／push／PR／部署／重啟。

**23:00 Taipei 接續更新：** 已將舊排程紀錄的唯讀盤點接入原 maintenance／Mac 入口；
指定資料讀完與「已安全結束」分開，空紀錄、terminal job 均不產生 pending_count=0。
同版入口、盤點、readiness、runtime/storage 與 architecture 回歸 **189 passed／3.95 秒**；
真 shell 的完整／缺檔兩條路徑均停在診斷，不進正常啟動。獨立唯讀覆核已關閉
外來 module／先執行後驗 hash 的缺口。這不是首次正式排空，也不是 controller 完成；
正式 checkout 再次核對 clean `75824229`，仍 0 新模型呼叫、未提交／發布／重啟。

**23:23 Taipei 目標接續：** controller-owned 子程序的持久 attempt、單次 warm-stop 與
退出讀回元件已驗證，且已由既有完整舊版 API 私有 UDS lane 真正使用；同版總回歸
**250 passed／10.00 秒、0 failed／0 skipped**。它尚未接正式 entry／移交 controller，
不接管既有 PID、不授予 protected／release；程序退出與 app／descendant cleanup 分開。
新增正式側檢查只限 lsof／ps／Git：API PID 42636、父 PID 42603、cwd 為正式 backend，
仍有 8080 listener，checkout clean `75824229`；沒有正式 DB 查詢、Redis command、API
request 或 signal，也不據此宣称 loaded SHA／健康已驗證。完整目標仍進行中。

本節是目前唯一的收尾執行入口，承接原 `output/quality-pilot-20260912/OPTIMIZATION-PLAN.md`
的全部 P0／P1／P2，不取代或改寫後面的歷史失敗證據。使用者這次要求先整合問題、總測試預算與
驗收條件；使用者已在此方案交付後明確回覆「核准」，**整體實測預算及條件式發布已核准。**
2026-09-14 21:07 Taipei 開始 S0；首個 live 尚未啟動，7 日 live 有效期尚未起算。
舊的單次 6-call／4-minute 收據均不重用。本節獲核准後，同一方案內的例行修正、分批測試與
達標後發布沿用該次核准，不再每修一項就要求新的 6 次呼叫核准。

**23:56 Taipei 接續：不可覆寫報告發布的限定離線接線已完成。** 在原
render／quality gate／report index 流程增加顯式 create-only 路徑，衝突（含 legacy
path／metadata）保留原 bytes 與索引；失敗或取消不清除不確定產物、不自動重送。
可信 process-local controller 可綁既有 0700 私有 output directory，預設未綁的
frozen scope 仍硬停止，不藉此授予正式 controller／模型送件權限。四模式診斷已經
正常 job、真 renderer、私有 job DB／index／artifacts、SSE 與真 reports router 讀回；
pipeline fixture 是明示 synthetic legacy context，並非完整 agent graph／真模型驗收。
獨立覆核指出 partial HTML 可能被普通 reader auto-index，已加持久 attempt／complete
邊界與忠實反例修正；正常清單／下載不放行 pending，但保留原 bytes 和 uncertain row。
最後整合 **486 passed／12.81 秒、0 failed／0 skipped**；獨立覆核的同一 P2 已關閉。
這是私有診斷產物，不是 live-qualified report；S0 與整體發布條件仍未完成。

### 私有 create-only 發布：本輪驗證範圍（2026-09-15）

- `analysis_jobs → analysis_job_reports → ReportRenderer → persist_report_bundle` 保留
  真實品質 veto；controller 的 optional 私有 outlet 綁 root inode、job、ticker、mode、
  stable filename 與 frozen workflow data hash。未綁 outlet 的原 scope 仍停止於 renderer 前。
  同時修正一般 job 在排版期間取消後仍可能寫入的缺口：renderer 返回後再檢查取消。
- `create_only=True` 只接受顯式且相符的 LocalFileStorage／output root，nested／flat
  HTML、Markdown、snapshot、sidecars、review 或 index 已存在即拒絕。root lock 覆蓋
  全 bundle 與 index insert；檔案 O_EXCL，metadata 用 plain SQLite INSERT 而非 upsert。
  partial、fsync、取消或 index 回覆遺失都不進舊路徑的 rollback delete，不自動重新發布。
- 專屬 reserved namespace 的 attempt 先持久寫入，complete 只在三份產物與 index
  INSERT 確认後，以已 fsync 的內容及 exclusive link 建立。未完成／破損 receipt 不讓
  reader 自動建 index 或下載；uncertain index row 保留。讀取前後均檢查 pending，
  包含 reader 先看到無 marker、其後等待 writer 失敗的並行窗口；沒有 nested flock。
  無此 receipt 的舊報告保持原讀寫語意。一般維護刪檔與非合作 writer 不在這個保證內，
  controller 仍需確認專用 root／sole-writer，不把此元件稱為跨 DB／檔案系統原子交易。
- 四模式使用明示 synthetic legacy 上游 context，真量化、renderer、品質投影、私有
  job DB、report index、HTML／MD／snapshot、SSE replay 與真 reports router 已讀回。
  原 cutoff 在 snapshot.data 保留；renderer metadata 如實為 `legacy_unverified`，
  不插入或冒造模型的 generation receipt。v4 fixture 明示無交易診斷；不是完整 Agent
  22–24／final-audit 的模型成功。第二次同名輸出被拒，原 bytes 保持不變。
- TDD 原始行為反例保留：create-only 原路徑 **8 failed／1 passed**、排版取消 **1 failed／
  15 passed**、partial→reader auto-index **3 failed**、並行 reader **2 failed**。
  中途 fixture 使用錯誤的 cutoff 層級／缺 v4 必要可見段落已依真 renderer 契約修正，
  沒有改品質 gate；marker 首版局部變數遮蔽造成的 17 failures 亦保留，修正產品變數名。
  這些實作／fixture 失敗不冒稱新的來源問題，也不以後續綠燈覆寫原 XML。

最終同版 21 個相關模組 **486 passed／12.81 秒**，包括本輪 33 個 create-only 案例、
既有與新增 frozen scope、normal publication／storage／index／renderer／job API／telemetry、
campaign graph 與必跑 runtime/storage／architecture。XML：
`/private/tmp/stock-agent-private-publication-closed-integration-20260915.xml`，SHA256
`3be0a30c2a8a40a293e23d548e656dbb6d4af553f56c9193b1b966e73fc778a3`。
前面 469／484 與定向 185 項是重疊或較早狀態，不相加。獨立覆核最末僅唯讀確認
reader 四行修正與永久反例，未冒称它重跑主代理最後整合。

本輪新增 product module 僅 `storage/create_only_reports.py`，其 SHA256
`c74319ab557c5f1cbf6b243dd010507d295c74b3f5dc03567caedc9e2d970f00`；最後 reader
`report_history_storage.py` SHA256 `921df8ad46e8adbed12e51f02d6b14445bb271e604490b4c10fa1dde85e6964f`。
正式 checkout 唯讀重核仍 clean `758242290e795146520f58f68ffa113cac35e52c`；本輪未操作
正式 DB／Redis／API／服務，0 新模型呼叫，未 commit／push／PR／部署／重啟。
以上為 9月15日最後狀態；正常業務入口的 shared SDK／HTTP ledger 與 strict rotator
已於下方 9月16日切片接續。exact 預登記／zero-retry execution、controller 移交／
rollback、來源資格與帳戶計費證據仍缺；原集中測試預算不重設，不重新要求同範圍批准。

### 正常報告工作與共享預算接線（2026-09-16，私有離線驗證）

- 私有 `quality_campaign_runner.owned_job` 已由單獨 graph helper 改呼叫
  `quality_campaign_graph.run_normal_job`，傳入同一 reserved ledger／transport／manifest
  SHA。保留原乾淨環境、寫入／socket／SQLite 防護、watchdog 與 parent cleanup ownership；
  adapter 不送 RQ、不 finish ledger、不放行 stage，也不把 diagnostic 升為 qualified。
- 正常 `analysis_jobs → QuantEngine → provenance → AnalysisPipelineRunner → SQLite graph`
  保留原 aware cutoff、凍結來源、品質 gate 與 normal job/events。process-local scope 在
  service factory 前注入 controller 的 strict rotator，避免正常 factory 另建未受該 wrapper
  保護的 rotator。SDK 同步／非同步／串流皆沿用同一 SDK／HTTP ledger；串流過程共享額度
  失效亦即停止，不只在下一個 HTTP 前檢查，不補回 job retry budget。
- `run_normal_job` 在 private DB 操作前核對精確 paths／cache／SQLite 設定，拒絕已有
  job 或 active ticker，保留原 job status，不將 hard abort 偽裝成 DB 成功。parent preflight
  同時拒絕沒有原 aware cutoff、ticker/date/trust 的歷史來源，不能補成今天日期。
- 真 renderer 後的 process-local validator 在任何 artifact 前阻擋 credential-shaped text，
  不改寫已通過 gate 的文字；保存三份預期 bytes/hash，normal publication 返回並完成 SDK
  cleanup 後，再核對 job、report_done、HTML／MD／snapshot 與 index。破損 bytes 保留，
  不宣稱 published；底層 job 已 done 與 controller outcome partial 可同時如實存在。
- 上一版 complete marker 的 exclusive hard link 被既有 write guard 拒絕，已以真 child
  反例修正成同一 root lock 內 precheck＋fsync 後 atomic rename，仍不覆寫合作 writer 的
  receipt。guard 禁止 link 的規則不變；非合作 writer 與正式 sole-writer 仍須由 controller
  保證。SQLite resource、report index opener 與 checkpoint opener 現在只在父目錄不存在
  時 mkdir，避免對已存在的私有 root 發出多餘寫入；沒有放寬 root 可寫範圍。
- 四模式真 graph＋真 SDK/HTTPX MockTransport 案例刻意以 final-audit veto 拒收，保留
  quant／cutoff／SQLite／job events。四模式成功產物案例則使用明示 synthetic legacy
  pipeline＋真 renderer，snapshot `generation_contract={}`，不造模型 receipts。
  新鮮 child 的兩條路徑（真 graph／SDK 拒收；synthetic legacy 真 renderer 發布）均在
  原 write/sqlite guard、PostgreSQL import veto、全禁外部網路下完成，已定向 **2 passed**。
  這不是全套真 Agent 模型成功率，也不是正式 UI／controller 驗收。

本輪行為 RED 保留：guard hard link／缺 rotator **2 failed**；舊 graph helper 缺正常
job 寫入 **4 failed**；串流額度失效後仍收到三段而非一段 **1 failed**；parent 無 cutoff
仍受理 **3 failed**。同一批測試曾有 fixture 誤將 transport/HTTP 兩個 reservation 合為
一次、誤以為 BudgetDenied 不轉 ReplayAbort，以及 fresh child 漏裝既有 NoPostgres
veto；這些 setup/assertion 失敗與產品失敗分開保留，不藉此放寬防線。補 guard 後又以
真堆疊重現 existing root mkdir 被拒，三個 opener 已最小修正。

先行私有 graph／normal job／publication 整合 **180 passed／13.14 秒**，獨立覆核限定
normal/graph/create-only **80 passed／7.40 秒**，當時未見 material finding；兩份均為
較早且相互重疊狀態，不與最後整合相加。

最後同版 30 模組整合 **778 passed／52.49 秒、0 failed／0 skipped**，包含新 normal
23 cases、真 shared ledger 的 HTTP／transport 各自上限、runner/regressions、
budget/transport/watchdog、frozen/create-only、checkpoint resume、publication/storage/
index/renderer/job API，以及 AGENTS 指定 runtime/storage 與 architecture 回歸。
XML `/private/tmp/stock-agent-normal-job-shared-budget-integration-20260916.xml`，SHA256
`3403ad1d12a9d3717937529def46940eb26e84a16af8569294ec9bdafb4a52a6`。
最後新增 runner/storage delta 獨立 **67 passed／10.22 秒**，未見 material finding；
XML `/private/tmp/stock-agent-owned-normal-delta-independent-20260916.xml`。覆核者沒有
重跑主代理 778 項，案例數不相加。當時 owned/watchdog lane 仍替換 normal-job seam，另一
fresh-child lane 才是真 normal job＋原 guards；這是互補接點，不冒稱單一完整
「owned watchdog→真 normal graph→真模型合格發布」端到端驗證。下節接續補齊單一
私有父子程序路徑；真模型合格發布仍未取得。

最後 harness graph SHA256 `3f354f08a7fc48052b7fe24e105ecfc5da73fbf099f8623fea5fedab097f2b26`；
runner `72d1674f1ae7a34fc7201910b9767dc39204c527b59adba105ab2964dd6970a9`；create-only helper
`2a3db3a6bfcbec27d69b5c628b6897ee37df41174064621d53a817d662430cf6`。
DEV 仍在 `cf0ab0d1` dirty 工作樹；正式 checkout 唯讀重核 clean
`758242290e795146520f58f68ffa113cac35e52c`，不是 loaded SHA／服務健康驗證。
本輪仍 0 新 provider 呼叫、0 live-qualified sample；未 commit／push／PR／部署／重啟。
下一段是白名單業務函式／callback／零 retry 語義、舊 claim 結算及完整移交／rollback
controller；來源資格、152-slot 預登記與實際帳戶計費 review 仍為 live 前置条件。

### 單一 owned-normal 路徑與 SQLite sidecar 競爭修正（2026-09-16）

本片從 controller 整合檢查接續，沒有把隔離 campaign watchdog 的 owned process-group
強制清理直接套到正式移交。正式服務仍要求資料保存與 single warm-stop；這裡只補
私有 campaign 的實際父子程序、正常業務入口與結算接點。

- 新 `test_quality_campaign_owned_normal.py`／`_child.py` 呼叫原
  `execute_reserved_job → run_reserved_process → owned_job → run_normal_job`，保留
  FrozenJob／code/runtime inventory、child 環境、原 write／SQLite／PostgreSQL／socket
  guards、normal job DB／量化／cutoff、renderer／private persistence、watchdog cleanup
  與 parent artifact/hash／ledger readback。bootstrap 只屬測試，不新增 runtime test flag。
- 四模式各有兩條路徑：真 graph＋受控 agent/audit 葉節點＋真 SDK/HTTPX MockTransport
  回覆，最後品質 veto；另一條為明示 synthetic legacy 上游＋真 renderer，驗證三份
  artifacts／index／job/events 與 parent 結算。兩者均禁止實際 network，limiter PING
  是明示 fixture；billing/source review 與 S1 prerequisite 都是隔離測試資料，不是批准證據。
  成功產物仍無 generation receipt、不升格 qualified；S2 batch／stage 保持 open。
- 最初真完整路徑在 published 分支出現 `sqlite3.DatabaseError`，重 trace 後同碼通過，
  沒有把那次偶然綠燈當修復。另以 parent 密集 `ledger.check()`＋fresh child guarded
  `:memory:` SELECT 最小化，在兩次真多程序測試分別第 604／171 次讀取重現
  `not authorized`。當次 journal `lstat`：regular mode `33152`（0600）、uid 501 正確、
  `nlink=0`；macOS 在 SQLite COMMIT unlink 期間回報已消失 inode，原 guard 誤判。
  原始 stat／stack XML `/private/tmp/stock-agent-sidecar-race-stat-diagnosis-20260916.xml`，
  SHA256 `fee544bb927c02b426214898e41d3bcb4d19409af88a4a60a8571d1cf2247e33`。
- `quality_campaign_safety._regular` 新增預設關閉的 `unlinked_is_missing`；唯一啟用點
  是 `_Scope.check` 的 exact `-journal／-wal／-shm`，並同時要求 missing/private。
  只有 type／owner／0600 正確的 nlink=0 視為已不存在，不重試、不刪除、不採用新 inode。
  主 ledger／HTTP journal／artifact／descriptor／真正 write 檢查仍要求 nlink=1；
  hardlink、symlink、公用權限、異主與 ledger replacement 仍拒絕。
- 三種 sidecar 的 deterministic RED **3 failed／6 passed** 保留；修後 50 項通過。
  最終加上「可觀測已消失 sidecar 不授權寫入」負例，共 11 個 regression（含真
  5,000 次 SELECT 並行 ledger commits）。觀測用 trace／Connection subclass／Path
  probe 已全部移除；最後整合使用原 guard 與原 SQLite connection，不靠追蹤改變時序。

四模式 8 個單一父子程序情境＋11 個新 race regression＋40 個原 safety tests，最終
**59 passed／70.80 秒、0 failed／0 skipped**。XML
`/private/tmp/stock-agent-owned-normal-four-mode-green-20260916.xml`，SHA256
`42f9352dfc7a4158afaf7f4e0c0627d045680d910c15e951eff96c9cc128502f`。
獨立覆核已讀原始 stat 並限定驗證初版修正 **9 passed／1 deselected、1.13 秒**，
XML `/private/tmp/stock-agent-sidecar-unlinked-independent-20260916.xml`；後續 private
條件加嚴與 write 負例由主代理驗證，不冒稱覆核者重跑最後 59 項。初次 fixture 用錯
limits section 的 2 failures 與產品 failure 分開保留。重複診斷 6／3 項不計新增覆蓋。

同版 17 模組交叉回歸 **481 passed／48.98 秒、0 failed／0 skipped**，包括
runner/parent receipts、watchdog、safety/sidecar、normal job/graph、transport/budget、
create-only/frozen scope，及 AGENTS 必跑 runtime/storage/architecture。XML
`/private/tmp/stock-agent-owned-normal-sidecar-closed-integration-20260916.xml`，SHA256
`b253b9f9198a02d2e0f55c82744af4227df64018d711a6be9cdb703ff0080632`。它沒有重跑上述
8 個 owned-normal 端到端案例，但最後 safety／test 檔案 hashes 與該 59 項測試時一致。

最後 safety SHA256 `83a1319981ae5d3a6d2504e01a776c99b53d6e1b21894f602b28a4ed344fec77`。
這關閉先前「owned lane 與 real normal-job lane 只有分開驗證」的私有整合缺口，
不代表正向真 Agent 模型品質已驗證。RQ 登記／claim→owned dispatch→RQ settlement、
舊排程結算、正式 warm-stop 移交／rollback controller 與來源／billing/live gates 仍缺。
正式 Git 唯讀讀回 clean `758242290e795146520f58f68ffa113cac35e52c`；沒有正式
DB／Redis／API／signal／新模型呼叫，未 commit／push／部署／重啟。

### Owned normal job 的溫和停止與清理真值（2026-09-16）

沿用既有執行授權及來源／計費／live 預算，不操作正式服務。這片直接修正私有
`quality_campaign_runner` 的 CLI，不另建可繞過 frozen reservation 的正式入口。
使用 TDD 與獨立覆核補足停止生命週期；原私有 watchdog 的 group TERM→KILL 政策
沒有拿來代替正式服務的 single warm-stop。

- 真 `OwnedProcess.request_stop()` 對等待 MockTransport 回應的 normal job 發一次
  SIGTERM；原程式三個情境皆以 **-15 直接退出**，未完成 SDK finally。RED
  `/private/tmp/stock-agent-warm-stop-red-20260916.xml`：3 failed／18.63 秒。
  新 `run_owned_job` 保留原 Popen owner 之外的子程序 loop owner，第一個 TERM
  排入一次 task cancellation，重複 TERM 不再次 cancel；handler 保留到 Runner.close
  與最終收據完成，再恢復原 handler。同步／不合作工作不會被它強制中斷。
- `sdk_context` 只有真 SDK close／cache empty／hook ownership 全部成立才記
  `cleanup_verified=True`；原 exception 與 SDK close error 保留，不以 cache 被清空
  冒充資源已關閉。`owned_job` 只提供記憶體觀測，CLI 在真 loop／executor shutdown
  後重新讀回 ticket/outcome bytes 才寫 O_EXCL＋fsync `child-cleanup.json`。
- 獨立覆核找到「已完成的 `asyncio.to_thread()` 留下 idle executor」反例，原先
  提前看 thread 數會把成功 report 結算為 failed。真 owned normal＋renderer 的
  RED 1 failed／8 deselected、10.11 秒，XML
  `/private/tmp/stock-agent-warm-stop-executor-red-20260916.xml`。最終判定已移到
  Runner.close 後，不直接忽略任意 thread。
- 另以 pending task 的 finally 呼叫真 SDK／MockTransport，重現正常 hooks 已退出後
  又送 HTTP：RED 1 failed／5 deselected、8.04 秒，XML
  `/private/tmp/stock-agent-warm-stop-finalizer-send-red-20260916.xml`。
  `_close_owned_loop` 使用原 `instrument_http` physical seam 的 terminal veto，
  並固定已載入 Google SDK 使用 HTTPX；清理時不准新 HTTP，不增加 reservation／
  call budget。拒送計數及關閉後 cache 必須納入收據，不能只看 exit code。
- Python Runner 會 gather 部分清理 exceptions，只交給 loop exception handler，
  不讓 close 本身 raise。真 owned normal 的 pending-finalizer RuntimeError RED
  1 failed／6 deselected、7.82 秒：
  `/private/tmp/stock-agent-warm-stop-finalizer-error-red-20260916.xml`。
  新觀測器保留既有 custom handler、記錄其自身錯誤及 ownership drift；不輸出預設
  exception/body/task repr，只存總數與最多 32 個、每個最多 80 字的 type 名稱。
  task／async-generator／callback 清理錯誤即使 task 已 done 也不能 cleanup=True。
  獨立相同短反例已由 RED 變 **1 passed／0.05 秒**，XML
  `/private/tmp/stock-agent-shutdown-error-independent-green-20260916.xml`；覆核無新增
  material finding，但沒有冒稱覆核者跑過全部長整合。

驗證包含四模式原 8 路徑、v4 成功且用過 executor、真 OwnedProcess 的正常停止／
重複訊號／SDK close error／pending task 清理／清理中新送件拒絕／finalizer error。
研究、billing、limiter PING 和 HTTP 回覆均是明示離線 fixture；OwnedProcess lane 的
既有 watchdog-start claim 亦是 fixture，不代表 maintenance enrollment／dispatch 已接通。
SDK close 被取消／卡住或任意非合作 cleanup 不保證能完成；無成功收據就不得解除 gate。
`descendant_settlement_verified`／`handover_verified` 固定 false；CLI 不 finish／refund
campaign job、batch 或 stage。正式 RQ 結算、舊排程排空、完整移交／rollback controller、
來源與計費資格及 live S1–S4 仍未完成。無新 provider 呼叫，無提交／發布／重啟。

最後同碼主路徑／停止測試 **16 passed／114.24 秒、0 failed／0 skipped**：9 個
owned normal 父子程序案例、6 個 OwnedProcess 停止案例、1 個 CLI signal 單元案例。XML
`/private/tmp/stock-agent-warm-stop-final-paths-20260916.xml`，SHA256
`d389979edccd18879172081227e428abcaa62187a48a528ddb32edb34f2596e4`。
20 模組交叉回歸 **616 passed／56.96 秒、0 failed／0 skipped**，含原
runner/watchdog/graph/transport/budget/safety、normal/create-only/frozen scope、
OwnedProcess、canary claim/enrollment 與 AGENTS 必跑 runtime/storage/architecture。
68 warnings 為已安裝 RQ 的 utcnow deprecation。XML
`/private/tmp/stock-agent-warm-stop-final-integration-20260916.xml`，SHA256
`d1fa82afaca2385d8549c6d28f9ed8aeec631bfac96fafdb57aa452dd57bca37`。
最後追加 3 個 async-generator／callback／原 handler 拋錯案例與 3 個 architecture
checks，共 **6 passed／7 deselected、1.01 秒**，XML
`/private/tmp/stock-agent-warm-stop-shutdown-and-docs-20260916.xml`，SHA256
`053470d71aeb92629708f10da3717e79702beede2b6a5bf03f5c1035e0fae0b1`。
前版 31／119／15／616 及反例重跑保留，不與最終結果相加。

最終 runner SHA256 `c20b2bc2d5c749178fdc67fb025aae7439e72ff5a7882fb166c17a8cb72da24d`，
graph `be773fb2695a457b242fe826aaa5fcbdfbe7f15a02cc753c52ce9fb3ab767115`，
warm-stop test `8f19a4bf7486b62ab57078edd34482b88cacdb89e2f70594a4da6426af388394`。
DEV 仍為 dirty `cf0ab0d1`；正式 Git 唯讀確認 clean `75824229`，不推論 loaded SHA／
服務健康。controller、來源、billing 與 live gates 狀態均維持未完成。

### Canary 取件、正常執行與 terminal 結算（2026-09-16 接續）

本片新增 `scripts/maintenance_canary_settlement.py`，接續原登記／semantic claim 與
真 owned normal child；仍不接正式入口，不把離線 fixture 升為 live-qualified report。

- 取件回覆必須綁完整 frozen raw pins／normal function invocation，程序必須是原
  `OwnedProcess`。以其 durable lifecycle binding 比對 operation／control／backend
  identity，而非可改寫的 public `process.binding`。child-started 與 child-cleanup
  新增真 PID；ticket／manifest／outcome 的 SHA、SDK／loop／HTTP hook／pending tasks／
  generators／threads 清理結果都必須一致，非 published+exit0 不判 RQ finished。
- bounded evidence 讀取拒 symbolic links／hardlinks／異主／非 0600 檔案／非 0700
  私有父目錄及 inode／mode 漂移。成功發布另讀回真 HTML／Markdown／snapshot bytes，
  不只相信 exit code 或存在一份 JSON；普通 source/billing qualification 仍由 controller
  負責，這個 helper 不給自身送件權限。
- WATCH 原 enrollment marker、exact queue／唯一 intermediate、全部剩餘 job hashes、
  relations／results／registries。原 roster suffix／immutable pins 完整才進單次 EXEC，
  更新 finished／failed、server-time ended_at、七日 job／registry retention，新增不過期
  settlement marker，並 LPOP 這一件 intermediate；同 EXEC 讀回各結果。
  只有觀察到 MULTI OK／完整 QUEUED／EXEC nil 才稱 conflict；lost reply、runtime error、
  提交後取消或 evidence drift 保留 uncertain，不 replay、補償、回填或更新舊 marker TTL。
- 真私有 Redis（TCP port 0）與真 OwnedProcess／normal job／renderer／私有 SQLite
  接線，涵蓋四模式、品質拒收、warm stop、檔案與 PID／manifest 漂移、活程序、WATCH
  race、遺失回覆、取消、EXEC WRONGTYPE、重複結算、零 retry 與清理觀測缺漏。
  另外以同一 enrollment、同一 ledger 連續跑 v1–v4，及 v2 blocked 後必須留下 v3/v4。
  pending 的預期從原 roster 推导，不用 helper 回傳值自行證明正確；prior／ordinary
  bytes 保留，未執行的 mode 不 reserve。原 pipeline 上游、source／billing、S1 prerequisite
  與 between-job ledger.finish_job 均明示 fixture，不是正式 dispatch／campaign settlement。

獨立覆核指出 public process.binding 可變的反例，真 normal path RED
`/private/tmp/stock-agent-canary-settlement-binding-red-20260916.xml`：1 failed／9.85 秒。
修正改比 durable lifecycle，原獨立短反例 GREEN 1 passed／0.10 秒，XML
`/private/tmp/stock-agent-settlement-binding-independent-green-20260916.xml`，SHA256
`68462932c08dc751ad1ae1fc34df2bb01b7e9b67c1fa6f0a03a482a0ed4c3c39`。
覆核亦補強 stop-after-second 的独立 expected suffix，未宣稱產品曾刪掉 v3/v4。

#### 交叉回歸發現的 async-generator 清理缺口

初次較大回歸為 **634 passed／1 failed／168.72 秒**，XML
`/private/tmp/stock-agent-canary-settlement-closed-integration-20260916.xml`；不能改稱全綠。
原 async-generator cleanup test 單跑過、在 normal-job suite 後失敗。暫時 probe 證明
失敗時 hooks=None、未登記於 loop._asyncgens，run_until_complete 來自 nest_asyncio；
FinMind.utility.request 匯入的 apply 是實際來源，非隨機 timing 猜測。probe 已移除。

- 真 FinMind 匯入 before／during／shutdown 三個 fresh guarded CLI 反例，在修前
  **2 failed／1 passed／2.49 秒**（XML `stock-agent-owned-asyncgen-finmind-red-20260916.xml`，
  位於 `/private/tmp`）。`nest_asyncio.run_until_complete` 不安裝 asyncgen hooks；
  初次 native loop 已在跑時有 hooks，故 during 可過，預先 patch 與 shutdown 新建者漏掉。
  `_owned_asyncgen_tracking` 現覆蓋工作及關閉，使用目前 thread／owned loop 的原 hooks；
  不 undo/reload 全域套件，不蒐集別的 loop 的 generators，正常退出還原 caller hooks。
  ownership drift 否決；真 normal child 的 pending-task finally 建 generator 並拋錯，
  最終收據亦正確否決 application_cleanup_verified。
- 獨立覆核再重現 generator.finally 建立另一個 retained generator：Python
  shutdown_asyncgens 只處理一次 snapshot，後建者未關閉卻原判 exit0／cleanup=True。
  原 RED `stock-agent-nested-asyncgen-independent-red-20260916.xml`：1 failed／0.67 秒。
  close 後現記 `pending_async_generators`，只數本 loop 登記且 ag_frame 非 None 者；
  大於零即否決 CLI success 和 RQ settlement，不無限遞迴清理，不誤阻已自行關閉者。
  原獨立斷言未改，加永久 open／closed 兩分支 **3 passed／2.50 秒**，XML
  `/private/tmp/stock-agent-nested-asyncgen-independent-green-20260916.xml`，SHA256
  `0e671026d4ea2be3767fa96cfb1d1794893bed6f1c77ed9c110bcfd96518f4d3`。
  這個短 CLI 反例使用明示 synthetic completion 前提；真正常 child／RQ coverage 另列。

最終短套件 **11 passed／7 deselected／3.28 秒**；原獨立覆核確認限定 P2 已關閉，
不冒稱其重跑全部長套件。最後兩輪測試前後的九個相關程式／測試檔 hashes 一致：

- 真私有 Redis／normal child **30 passed／271.81 秒、0 failed／0 skipped**：28 個
  單件情境（含殘留／缺漏 generator count 拒絕）與 2 個完整 roster 情境。XML
  `/private/tmp/stock-agent-canary-settlement-residual-final-paths-20260916.xml`，SHA256
  `89f1a8388dc17ce058b99208196c8200c49658bb5d27bfdfbbadcf016b70ad1f`。
- 23 模組交叉回歸 **643 passed／180.62 秒、0 failed／0 skipped**，包括正常 child、
  warm-stop／FinMind／nested generator、原 runner／budget／safety／sidecar／graph／
  transport、create-only／frozen scope、claim／enrollment、runtime/storage／architecture。
  68 warnings 均為既有 RQ utcnow deprecation。XML
  `/private/tmp/stock-agent-canary-settlement-residual-closed-integration-20260916.xml`，SHA256
  `0c1e1d9560361ae614ceb2c8a76b7d8454fbed97422500306ea70f62296b100e`。

前面的 26／28／193／641 等中途綠燈是不同切點、互有重疊，不相加或當最後同碼驗收。
641 那輪另有一個 SDK AsyncClient.aclose 未 await warning；最後 643 原順序未再出現，
不宣稱已另外修復該跨測試 SDK 析構警示，亦不改寫較早 XML 的實際結果。
最後 settlement helper SHA256
`f41208449e4c1b213b7f1da471040b5dcfd2ccda53e322d5ccd2524597ce2e52`，runner
`0d20e0aebb45ac87594351ff9505fcf2fc9d75808e9feade0f93d68edae17744`。

完整 controller 的 enrollment→original owned dispatch→RQ/budget/descendant settlement→
release／rollback 仍未完成；watchdog-start claim 在上述 lane 仍是明示 fixture。
不能把 helper 接線當成正式 entry/control digest、舊服務／scheduler 排空、Redis 磁碟
保存移交或 public readiness release 已完成。來源資格、152-slot 預登記、實際帳戶計費
及 live S1–S4 均未通過；本輪 0 新 provider 呼叫，未 commit／push／部署／重啟。
下一個程式接續點是把原 owner／reservation／launch receipt 接入同一個受限 dispatcher，
消除現有測試的合成 watchdog-start claim；不得把該 fixture 直接搬到正式 controller
充當移交證據。正式 Git 最末唯讀確認仍 clean `758242290e795146520f58f68ffa113cac35e52c`；
沒有正式 DB／Redis／API request 或 signal，不據此宣稱 loaded SHA／健康驗證。

### 原預算結算與清理取消（2026-09-16，私有離線切片完成）

- 新 lane 只在原 dispatcher／supervisor 證明退出、原 group 不存在且完整清理、
  ticket／intent／outcome／artifact bytes 都未漂移時，取得一次 RQ terminal ACK；
  接著保存 create-only ACK，SQLite 交易以 exact original reservation CAS 結算 job。
  attempts、spent、batch 與 stage 不被重置；原期限到達仍可 cleanup-only，但 blocked
  保留、不授權新的工作。完整 manifest 仍須通過，billing review 到期並不豁免。
- RQ ACK 遺失／取消不結算 ledger；ledger 已 commit 但回覆遺失也只回 uncertain，
  不重試、不退額度、不重建收據或接管失聯程序。這不是 Redis／SQLite 原子交易。
  ACK 檔案更動、missing／bool 冒充 0 的程序計數、缺少或更動 Git 身分均拒收。
- child 在 app／credential imports 前禁止標準 Python 程序建立。獨立反例揭露
  CPython 3.13 的 multiprocessing spawn／forkserver 不發 audit event；永久反例
  修前 **4 failed／2 passed**，現一併封鎖 public start、spawnv_passfds、兩個 fork_exec
  接點。原獨立反例加永久案例 **11 passed／2.22 秒**，P2 已關閉。僅是受檢 Python
  應用邊界，不是 native／raw-syscall／hostile-code sandbox。
- 真 graph 原需 subprocess 讀 Git，新增 no-spawn 後暴露相容失敗；改由原 parent
  在乾淨環境讀真 HEAD／dirty，與 frozen code hash 綁在 intent。child 驗真再提供兩個
  Git 環境值；不是測試假版本，也不是正式服務 loaded-SHA 證明。四模式 graph 測例
  保留 mock HTTP＋原 final-audit 拒收，synthetic legacy publication 另列，不混成
  模型產出合格報告。

#### 首個停止打斷 SDK 清理：真實反例與修正

前一候選交叉回歸 **827 passed／228.35 秒**，私有整合卻 **55 passed／1 failed／
551.31 秒**。單跑 deadline 曾通過，與 normal-job 同跑再次失敗；新增唯讀診斷確認
pending HTTP 已進入，原錯誤為 TimeoutError，cleanup error 為 CancelledError，
cache 未清空；其餘 loop／hooks／tasks／threads／generators 都正常。系統原本正確
fail-closed，不能把此次失敗寫成普通負例通過或調長正式 deadline 來遮掩。

主代理真 SDK＋MockTransport、close 前取消 1／2 次與原 TimeoutError／無原錯誤
四個永久案例先 **4 failed**；首版漏 maxOutputTokens 而被既有 guard 阻擋的四個
setup failure 另存，不算缺陷 RED。獨立原 close helper＋client.aclose await 亦先
**1 failed**，證明不只 fixture 的 close 前 .02 秒延遲會受影響。
`sdk_context` 現只建立一個既有 10 秒上限的 close task，用 shield 隔開 parent cancel；
只等待原 task，不重做 close／重設期限，完成與 hooks 還原後保留原錯誤或傳回新取消。
close 自身取消／逾時仍否決；非合作 close 仍不冒稱 hard real-time 保證。
定向 graph／transport **80 passed／2.69 秒**，追加真正十秒 timeout 與自身 cancel
後完整 graph **34 passed／12.49 秒**。獨立原反例＋graph **33 passed／2.38 秒**，
另內部取消負例與原例 **2 passed／1.77 秒**（重疊不相加），限定覆核無新重大問題。

本節 XML 均在 `/private/tmp`：
`stock-agent-owned-multiprocessing-permanent-red-20260916.xml`、
`stock-agent-owned-spawn-independent-green-20260916.xml`、
`stock-agent-owned-budget-final-cross-regression-20260916.xml`（清理修正前827項）、
`stock-agent-owned-budget-final-private-integration-20260916.xml`（保留55P／1F）、
`stock-agent-owned-budget-deadline-cleanup-reason-20260916.xml`、
`stock-agent-owned-sdk-late-cancel-faithful-red-20260916.xml`、
`stock-agent-owned-sdk-late-cancel-and-timeout-green-20260916.xml`、
`stock-agent-sdk-close-cancel-independent-green-20260916.xml`、
`stock-agent-sdk-close-internal-cancel-independent-green-20260916.xml`。
前版827項含69個RQ deprecation及1個既有 in-process fixture 未await close coroutine
warning，不抹除，也不拿來替代真私有 child cleanup 證據。

最後同版結果（不與前版或重疊定向結果相加）：

- **833 passed／211.26 秒／0 failed／0 skipped**：campaign runner／graph／transport／
  budget／safety、正常工作、取消、async-generator、publication、owner／supervision／
  pipe／entry／claim／enrollment、runtime/storage 與 architecture。71 warnings 為
  69 RQ deprecation與2個既有 in-process fixture 的未await close coroutine；未稱零警告。
  `/private/tmp/stock-agent-owned-budget-cleanup-final-cross-regression-20260916.xml`，
  SHA256 `dfc9c9e97fa240494a83ceb9157be1688f753a0cd43ba3a02012237603c78a56`。
- **56 passed／517.08 秒／0 failed／0 skipped**：26個 original-parent dispatcher、
  28個 legacy settlement與2個完整 roster；四模式包含 synthetic publication與真
  graph＋mock HTTP品質拒收。原12秒 deadline案例在與normal-job回歸並行時亦通過，
  沒有調長期限或放寬cleanup。RQ／budget ACK遺失、取消、檔案漂移、receipt欄位型別
  與降級、ordinary bytes與pending suffix保留全部核對。
  `/private/tmp/stock-agent-owned-budget-cleanup-final-private-integration-20260916.xml`，
  SHA256 `d1c93bb31bd788f67d1b80c6fc90f4aa1357f836ff60e39e16db138576ef00fc`。

最末 source SHA256：

- dispatcher `0be8a6b6099b9bfafb853a7ecb35ce9d5c4fdb74ed35fe2d5df94f31590cd147`；
  settlement `c0183bbfd7c0c1e73b4973c4bc4369fcbafa30750deec4bdc52f268be750abc2`。
- budget `49e7b62767b5abe493aaea32832c5cb8f91ae0cc024838250c7d1d60f3f06165`；
  safety `5584da30238acf68db9a4771068853f55ea4c466f636a63bd289bd64a8b0e2d4`。
- runner `36e1f4a87c34aaad39ad5b5a2edb19113a2f04191c8e7e5ba07a31516427c7b6`；
  graph `7fe100b0355d68b146831c56d0bba1be69d6792cb3739059b8ef8681847629bb`。

**當時接續工作（controls 已於下節實作，驗證範圍另列）：** 把全部 controls 的實際載入 source buffers 綁至 controller，
再整合舊 scheduler claim→enqueue 歧義排空、Redis最後保存／磁碟移交、正式 entry與
protected／release／rollback。單筆 job 結算不等於上述流程完成；來源資格／152-slot
預登記、匿名 project／tier／billing 證據、live S1–S4仍缺，不重設既有預算或IR窗口。
正式 Git 最後唯讀確認 clean `758242290e795146520f58f68ffa113cac35e52c`；DEV dirty
`cf0ab0d1`，未操作正式 DB／Redis／API／服務、未新增 provider 呼叫或發布。

### 控制程式實際載入綁定（2026-09-16，私有離線切片）

`maintenance_entry.load_control_bundle` 以有界 nonsymlink fd 擷取全部控制來源，
驗證 digest 後才 compile 同一批 bytes。新 `maintenance_control_sources.py` 本身亦
從已核對 buffer 執行；十個 Python 控制模組、七個 campaign harness 及 loader／shell
共19份來源 bytes 都納入 digest。dispatch 僅取此 snapshot 的 harness bytes，
在專用 finder 有效時明確載入全部七個，而非只載入四個、將其餘 None 當身分證據。
公開 CLI 在載入前用共用 argparse 核對 arm／inventory manifest，支援原有分離、
等號與縮寫語法。所有操作仍沿用原授權；自動計算 digest 不代表新的人為批准。

- fresh single-thread controller 拒絕預載 controls／harness、應用與 credential startup；
  不擴增 backend／tests 搜尋路徑。忽略 timestamp pyc／外來同名檔，以原 buffer 編譯。
- finder 保留到 dedicated controller 結束，在 reload／重載前拒絕；部分載入失敗即
  poisoned，不能續用。動作前核對原 PID、完整模組、finder／spec／origin／loader 身分
  與磁碟來源；receipt 每次重建，不授予 production_ready，shell_execution_verified=false。
- inventory 使用原 bound module，不在公開路徑暫換 sys.modules；未綁定 library
  seam 保留舊隔離測試相容性，但不算 bound-controller 證明。
- dispatcher 不接受直接裸 import；除 launch／settle preflight 外，在 child 啟動後、
  送 admission 前再驗 loaded controls。身分漂移保留 RQ intermediate／原 reservation／
  ordinary queue，不送許可、不自動重送、不退預算。cleanup 仍由原 owner 負責。

實際反例與修正：

1. `stock-agent-control-source-binding-red-20260916.xml`：9 failed；其中公開 CLI
   實際採用同尺寸／mtime 舊 guard pyc 是行為反例，其餘8項是新 API 缺失，不混稱。
2. `stock-agent-control-source-plan-arguments-red-20260916.xml`：2 failed／1 passed；
   手寫 argv 判定漏掉 equals／abbreviated，私有 marker 在拒收 manifest 前執行。
   共用 parser 後原三種語法均拒絕。原 entry 整合174P／1F 是舊測試仍 patch
   Path.read_bytes、未攔到新 fd capture；改 patch 真 `_control_source`，保留拒絕斷言。
3. 獨立 `stock-agent-control-reload-independent-red-20260916.xml` 1 failed；
   成功載入即移除 finder 使 importlib.reload 先執行變更 source。保留 finder 後原
   harmless-marker 斷言不變，與 source/import tests **26 passed／6.75 秒**，
   `stock-agent-control-reload-independent-green-20260916.xml`，限定 P2 已關閉。
   permanent RED 另保留 missing-spec 非標準例外與 finder 尚未保留的 setup failure，
   不把三項都寫成同一個 reload 漏洞。
4. `stock-agent-bound-inventory-admission-red-20260916.xml`：2 failed／3 passed；
   bound inventory 未使用原模組、以及啟動後控制模組被換仍送出許可。修正後
   `stock-agent-bound-controls-dispatch-first-green-20260916.xml` **4 passed／34.16 秒**，
   包含 v1 published、v4 warm stop／deadline／control drift，23 deselected 是未選取。
5. `stock-agent-bound-controls-final-entry-integration-20260916.xml`
   **184 passed／8.53 秒／0 failed／0 skipped**，1個既有 RQ deprecation warning。
   shell fixture 補齊全部控制檔，明確斷言進入 descriptor 拒絕、不因 loader 缺檔假綠；
   同時涵蓋來源載入、entry、inventory、readiness、runtime／storage。

前版完整私有 dispatcher／roster 為 **29 passed／272.66 秒**，
`stock-agent-bound-controls-final-private-dispatch-20260916.xml`；這是末兩個 harness
來源邊界修正前結果，不冒稱末版整組。owner／guard／shell／architecture 另
**86 passed／2.51 秒**（`stock-agent-bound-controls-owner-shell-regression-20260916.xml`）。

末輪來源邊界修正與證據：

- 專用 finder 加入七個 harness 的 reload／reimport veto；原
  `stock-agent-bound-harness-reload-red-20260916.xml` **1 failed／4 passed** 保留，
  獨立對應回驗8 passed／14 deselected。其後入口回歸187 passed、真child11 passed
  是同納 snapshot 前的歷史結果，不冒稱末版。
- 獨立實際公開 CLI 證明未將 harness 納入 control digest 會先執行私有 marker、
  才因後續 arm 檢查回75；RED `stock-agent-unbound-harness-cli-independent-red-20260916.xml`。
  永久三種CLI語法及 capture後變動為 **4 failed／3 passed**，
  `stock-agent-control-harness-snapshot-red-20260916.xml`。現在19份同批 buffer 在
  任一 exec 前驗真，dispatch 不另讀新版 bytes 來執行；保留磁碟 drift 檢查。
- 新增的 harness module／spec 漂移原 **2 failed**，
  `stock-agent-bound-harness-proof-red-20260916.xml`。bundle receipt 現逐一核對
  七個實際 loaded module／spec／loader／path，且 reload/reimport 在執行前拒絕。
  中途190 passed／1 failed亦保留：全檔pyc測試揭露原 transport 尚未載入，不抹除。
- 末版相關 **193 passed／10.27 秒／0 failed／0 skipped**，1個既有 RQ warning；
  `stock-agent-bound-all-sources-final-entry-20260916.xml`。
- 末版真私有 Redis＋原 child 四模式 published／graph-blocked、取消、deadline、
  control drift **11 passed／100.66 秒／0 failed／0 skipped**，16 deselected是未選取；
  `stock-agent-bound-all-sources-final-private-20260916.xml`。模型／來源／計費leaf仍為fixture，
  不代表live品質或成功率。沒有再次重跑未受影響的全部舊settlement／roster案例。
- 末版獨立原CLI／reload反例未改斷言，連同source/import測試 **36 passed／8.41 秒**，
  `stock-agent-control-all-buffers-independent-green-20260916.xml`；兩個限定P2已關閉，
  未見新實質問題。獨立覆核不是正式移交或發布授權。

以上 XML 均在 `/private/tmp`，重疊／前版測試不相加。此處是應用來源／生命週期防護，不是惡意 Python/native sandbox；
不認證 shell 已執行之 bytes、controller crash guardian、正式服務 loaded SHA 或發布。
最末 loader／entry／dispatch source SHA256 分別為
`d0fa8c4280fde41b607f7173baf96a2c945a4bb19608e20f947ef8c2bc7c7d0a`、
`b24e6a9ad2c301c26443c8db34cac6c6cb70cfc247ea19ae8804f8f205638c04`、
`afed48f799a4a31de8c0ee6176ba82ee11b21345befd1ce4b089905c2a78fbdd`。
DEV 原始公開 `--maintenance-control-digest` 實際 exit0，control digest
`325905ea93972461889ae848804ccf37dc33527136118fb37ec90effb61284f6`，
列出十個 control／七個 harness 的載入檔案，shell與production readiness仍false。

**後續仍未完成：** 舊 scheduler claim→enqueue 歧義排空、Redis 最後保存／磁碟移交、
正式 entry 的 protected／release／rollback；來源資格／152-slot 預登記、匿名 project／
tier／billing 證據與 live S1–S4。保持原預算／IR窗口／Gemma OFF；0新 provider 呼叫、
未 commit／push／部署／重啟，正式 Git 本輪唯讀仍 clean `75824229`。

### 獨立逾時與原紀錄讀回（2026-09-16，私有離線切片完成）

此片沿用集中核准，只補 controller 自有 canary 的停止／讀回接線；不新增模型外送、
RQ 重送、正式控制入口或預算退款。`OwnedProcess` 舊無 session lane 保留相容性。

- 原 `CampaignBudget` reservation 的 wall deadline 只映射一次到 monotonic deadline，
  同時綁 launch intent；不重開一個 job_seconds 時窗。真 Popen 建立新 session，
  PID／PGID／SID 相同且不等於 parent group。child 新 lane 也核對真 session。
- `OwnedProcessSupervisor` 在 post-launch ledger 檢查前啟動，監督 thread 不碰
  ledger／Redis／SDK；caller 不 wait、或 ledger 檢查卡住，亦會提出原 owner 單次
  SIGTERM。deadline 與手動取消只選一個原停止原因，不 SIGKILL／接管既有 PID。
  非合作程序不自動重送或當作已清理，需保留原 handle／reservation。
- 原 dispatcher 與已 supervised owner 的外部 wait 使用 Event；worker 只做零秒
  poll，不將長時間 wait 放在 lifecycle lock 內。獨立覆核以真 child 重現的鎖延遲
  P2 已修正，原 .2 秒 deadline／單次 TERM 行為反例補驗通過。
- `supervisor.snapshot` 每次經原 owner 驗真並重新解碼 journal，不用記憶體快照取代
  檔案真值；nested binding 亦為新物件。只對「尚未開始操作」的 ProcessBusy 做
  最多50ms讀回競爭等待，不重試 I/O／signal 不確定失敗。admission、wait、settlement
  共用此路徑；journal 破損與改回傳 binding 的三個永久反例均先紅後綠。
- leader exit 後以 `killpg(pgid, 0)` 查原群組存在性，不向 descendants 發停止訊號。
  有殘留、權限或未知狀態不放行。group absence 不等於任意逃離 session 的程序
  已清理，也不是 OS sandbox／controller crash guardian／hard real-time 保證；
  `descendant_settlement_verified`、`handover_verified` 仍為 false。
- 真四模式 normal child／renderer、warm-stop、重送拒絕與 ticket 降級拒收皆通過。
  新 blocked-ledger 案例用3秒原 reservation、4秒父程序阻塞，證明 timer 自行停止，
  admission 未發出，RQ intermediate／ordinary queue／ledger job 原樣保留。
  這些模型與來源仍為明示 fixture，不是 live-qualified 報告。

最後修改後的直接證據（0 failed／0 skipped；重疊不相加）：

- **208 passed／6.66 秒**：原 owner／group／supervisor／永久與獨立反例、admission FD、
  entry／inventory／readiness、runtime/storage／architecture。1 個既有 RQ utcnow warning。
  XML `/private/tmp/stock-agent-supervision-readback-final-targeted-20260916.xml`，SHA256
  `85fa24dede0c6977d378f2dde060a32f0ebd4acf77fbe27c0f110e42cb8102b9`。
- **11 passed／85.44 秒**：真私有 Redis 與 original-parent normal child 的四模式及
  failure／downgrade／warm-stop／replay／blocked-ledger。XML
  `/private/tmp/stock-agent-supervision-readback-final-dispatch-20260916.xml`，SHA256
  `b682f0fc6c37b54810b8a91fb817be3a4e5de17938bef514af05ebc006a9b999`。
- 獨立覆核確認 wait-lock 與 cached-readback 兩個 P2 均關閉，未見限定新重大問題；
  最末 review 為唯讀 source delta，不冒稱 reviewer 重跑主代理最後整合。

末版 readback 修復前已完成的廣度／相容證據另外保留，不冒稱同碼重跑：
`stock-agent-owned-supervision-cross-regression-20260916.xml` 為 **814 passed／199.46秒**，
SHA256 `5ed6806befe840a658327b2e62e1d93e4e48ce857b471c8905b272309fedc43d`；
其中71 warnings含69 RQ deprecation及2個 in-process fixture 的未await close coroutine，
不抹除或稱零warning，也不據此推論真私有 child cleanup 失敗。
`stock-agent-owned-supervision-private-integration-20260916.xml` 為 **41 passed／368.19秒**，
含11 dispatcher／28 legacy settlement／2完整 roster，SHA256
`7b4ce13298b1781d657c4d1d11507ae3205573724c809ca4eb9462cdf92ead0d`。
`stock-agent-owned-supervision-legacy-regression-20260916.xml` 為 **40 passed／10.60秒**，
含真舊 API 完整 archive／UDS、Worker 啟動與 Redis 最後保存，SHA256
`391dc117335ae07cf584646ba8b45df763ddc1001953ed299bbb27a435222df2`。
皆位於 `/private/tmp/`；末版僅改 supervised readback，受影響範圍已由上述208／11補驗。

中途證據保留：原 session 行為1F、supervisor API缺失3F、dispatcher未獨立session 1F；
readback 永久反例3F XML `stock-agent-supervision-readback-permanent-red-20260916.xml`，
SHA256 `2200361c20c0202fb6b1d1a8699d7900d6ce4e8822662730e8bbad152c6ed49c`。
最初 blocked-ledger fixture 給6秒期限，但child先因5秒pipe timeout退出，已把測例改3秒，
未改產品時限。主代理 owner-wait 測例首版因未收集thread exception呈表面2P，不能當
RED；已改捕捉並斷言thread errors，以獨立真鎖反例1F建立缺陷證據。原scratch觀測
`Popen.wait(2)` 在委派修正後不再適用，產生1F／40P；改觀測公開owner wait進入，
保留真deadline／TERM斷言再綠，沒有為過時觀測點改產品。

最末 product SHA256：owned process
`93c35900d7752a6d07af792bc484c4b22780684690e6b799f0408370de729645`；dispatcher
`a4e85602be34b91f73e3980cffe031b57697dc5aa983e10c77a28360eec43da9`；settlement
`e7006647e6057d2553fcda27ef52a099ed9b3b65c96eae5d9103aa69c4d01e68`；runner
`03ec3926ba9a4f80dd1787cd106ad487a848530cd917711ec1604e499c98e1a3`。

**下一個未完成接點：** 將 deadline／取消後的唯讀原 reservation 驗真、RQ terminal
ACK與campaign budget收尾順序接成同一 original-owner controller。現 `_preflight`
仍保守拒絕 expired ledger 的 RQ 結算；保留原額度／attempt，不是已完成收尾。
另需命令不逃離session的資格、舊 scheduler claim歧義排空、controls精確載入、
Redis磁碟移交及正式 entry／release／rollback。來源資格／152-slot預登記、實際帳戶
計費與live S1–S4仍未通過；GEMMA_EVIDENCE_BATCHING_ENABLED保持OFF。正式checkout
唯讀確認仍clean `758242290e795146520f58f68ffa113cac35e52c`，未操作正式DB／Redis／API。

### 原父程序送件准入（2026-09-16，私有離線切片完成）

`ClaimedCanaryDispatch` 只接一件已登記／semantic claim／reserved 的正常 canary，
不建立、重置或 finish campaign ledger。使用者原集中核准、研究／模型／費用上限不變。

- 固定正常 owned CLI 由原 `OwnedProcess` 建立，繼承唯一 read-only pipe。parent
  持久保存 intent／ticket／started 後，才送綁原父／child PID、pipe identity、ticket／
  intent hash、journal started prefix 的一次性訊息；child 必須收到有界完整訊息及 EOF，
  比對原父與 frozen reservation，才讀 credential environment。檔案本身不構成新 lane
  的 launch authority，缺 pipe 不回退到既有 watchdog claim。parent 送件失敗保留 attempt、
  原 owner、RQ intermediate、job 預留；不重送、不補造成功或退額度。
- fresh dedicated controller 精確編譯七個 harness source buffers；拒預載模組、外來
  sys.path 同名檔及同 timestamp 的 stale pyc。preflight 重核 module object 與 source
  bytes；不對整個 tests 目錄開 import search path，也不宣稱整套 controls 已精確載入。
  source read 的 identity 檢查不將正常 atime 更新誤判為修改，mtime／ctime／inode 等仍核對。
- ledger configured job_seconds 不得超過已驗真 RQ timeout_seconds；相同值綁 intent／
  child／settlement。這是保守准入上界，不是已完成 parent deadline watchdog。停止請求在
  admission 後與 environment 前再檢查；原 owner 單次 warm-stop、最終 cleanup veto 保留。
- 獨立覆核以真 new lane 重現：刪 ticket／started／cleanup 的 admission 標記、更新
  ticket hash 後，舊 helper 原仍完成 RQ 結算。現要求 durable lifecycle 有 pipe 當且僅當
  ticket 有新 lane；dispatcher 再比對原 ticket／intent hash。兩條永久反例均在 RQ 寫入前
  拒絕，原 bytes／intermediate／普通 queue 與 campaign job 留存。舊無pipe路徑仍通過。
- 新 lane 四模式均由真 normal job／renderer 產生並讀回三份 private artifacts，未造
  watchdog-start file。模型與上游仍是明示 synthetic legacy fixture，S1 prerequisite
  亦是 fixture；不是四份 live-qualified Agent 報告。舊同 roster 四模式與中途拒收保留
  suffix 的案例仍驗證，沒有把其 between-job ledger bookkeeping 當正式結算實作。

最後同碼結果（重疊定向／獨立測試不相加）：

- 31 模組 **805 passed／193.43 秒、0 failed／0 skipped**，涵蓋 runner／budget／
  transport／graph／normal child／asyncgen／warm-stop、pipe protocol、精確載入、claim／
  enrollment／owned process、maintenance entry／legacy inventory／readiness、create-only／
  frozen scope 及必跑 runtime/storage／architecture；69 warnings 是既有 RQ utcnow。
  XML `/private/tmp/stock-agent-original-parent-dispatch-cross-regression-20260916.xml`，
  SHA256 `a4eb1149ab222bcd339b7dfa502d81fdcec4961f723d07e1f952b25c2bd5fd74`。
- 真私有 Redis／正常子程序 **40 passed／349.96 秒、0 failed／0 skipped**：10 個新
  dispatcher cases，加28個舊 settlement cases及2個完整 roster cases。XML
  `/private/tmp/stock-agent-original-parent-dispatch-private-paths-20260916.xml`，SHA256
  `c581fa4551c7b275aecb9490c9912d0af4172c05c34b764136c04fe87ae398c8`。
- 舊 Mac 啟動／私有 UDS listener／Redis 最後保存測試 **37 passed／2 skipped／4.95秒**；
  兩個 skip 為未供原版 archive，供應既有 `/private/tmp/stock-agent-legacy-probe-20260915.cD8iV7`
  後，真舊 API／完整 lifespan／readonly UDS **2 passed／5.86 秒**，重新驗2240 Git blobs，
  不使用正式 checkout 執行服務。XML 分別 `stock-agent-original-parent-dispatch-legacy-short-path-20260916.xml`
  與 `stock-agent-original-parent-dispatch-legacy-api-20260916.xml`，皆在 `/private/tmp/`。
  原 legacy-startup XML 的1 failed／36 passed／2 skipped是 macOS AF_UNIX 暫存路徑過長，
  以 `TMPDIR=/private/tmp` 重跑，未放寬 socket guard 或修改 production listener。
- 獨立覆核 **22 passed／30.66 秒**，原 downgrade P2 關閉，未見新限定重大問題。
  XML `/private/tmp/stock-agent-dispatch-repaired-independent-green-20260916.xml`，SHA256
  `868245c36e2e1626528ec0f79aaebff9be15d48476629e881f0772497514116e`。
  原 parent／helper downgrade 與 timeout RED 3 failed、fresh import RED 3 failed 保留。
  中途錯誤的 public reason 斷言、inline Python 轉義及 atime 誤判亦留原 XML，不冒稱全部
  中途測試皆通過。macOS anonymous pipe 為0660且不支援fchmod；只在dev=0／nlink=0
  且readonly／正確owner的匿名pipe接受此平台模式，named0660 FIFO／一般檔案／write end仍拒絕。

最後實作 SHA256：dispatcher `beafa04b1b01fb17c945c1a9f0e863d8298282844d69960b0b314d164efecbbe`，
settlement `6abbe759a68edebc49a2c5714387432b1b76f750225cd5829d69d481994c7a6d`，
runner `ab78ed21fd5ce1e3f47749bdfead596fb275675f1fc8a8eab5cba8f137a6c69e`；最後核對
相關10檔 hashes 與測試期間記錄相同。files 納入 control digest 不等於正式公開執行授權。

**下一個可執行接點：** 沿用原 owner 整合 deadline／取消監督與 OS descendant 真值，
再讓 RQ terminal 與 budget settlement 的先後／失聯保留接入同一 controller；不能把
目前 app cleanup 或 RQ finished 當作 ledger 可 finish 的證據。完整 controls 精確載入、
首次舊 claim 排空／歧義處置、Redis 磁碟移交、entry dispatch／release／rollback 仍缺。
來源資格、152-slot 預登記、匿名帳戶實際計費與 live S1–S4 均未通過。
正式 Git 本輪唯讀確認 clean `758242290e795146520f58f68ffa113cac35e52c`，DEV 仍未提交；
沒有正式 DB／Redis／API request、服務 signal、新 provider 呼叫或部署／重啟。

### Canary 業務語義與 create-only 登記（2026-09-16，私有離線驗證）

白名單函式、精確三個業務參數／manifest、空 callback／dependencies 與明確零 retry
已加入取件前檢查；四模式整批驗證，不先取走合法第一件後才發現後件不合法。
`prepare_analysis_job` 只建構未儲存的 RQ Job，不呼叫 save／enqueue／restore。
同版 15 模組整合 **384 passed／45.65 秒、0 failed／0 skipped**，XML
`/private/tmp/stock-agent-canary-analysis-semantics-integration-20260916.xml`；獨立限定
非私有 Redis 案例 **71 passed／2 deselected、1.23 秒**，未見新增 material finding，
XML `/private/tmp/stock-agent-canary-analysis-independent-20260916.xml`。兩者重疊不相加。

- `claim_analysis_next` 在 WATCH 前驗證完整登記名單，不只目前 queue head：只接受
  `analysis_jobs.run_stock_analysis_job`、exact job/ticker/v1–v4、`force_refresh=False`、
  同一 campaign／各自 manifest SHA、timeout 與七日 retention、空 callbacks 及明確
  `retries_left=0`／`retry_intervals=[]`。已安裝 RQ 1.16.2 的 `Retry(max=0)` 不合法，
  constructor 直接設定未保存 Job 的零預算，不經一般 `RQTaskQueue` 的 retry defaults。
- Redis data 只做有界單一 zlib member 解壓，與本機 primitive tuple 的 canonical
  pickle5 bytes 比對；meta 同樣只比對 bytes，不呼叫 pickle.loads／Job.restore。
  GLOBAL／REDUCE、超限／截斷／多段壓縮、未知欄位／callback timeout／旧 result 均拒絕。
  copied bindings 防 caller 改寫驗收值；不確定結果不回傳 invocation。時間格式合法只
  表示 RQ schema 合法，不證明來源新鮮、資料資格或目前預算仍有效。
- 新 `scripts/maintenance_canary_enrollment.py:enroll_analysis_jobs` 重用相同語義驗證，
  但要求一次包含全部 1–4 jobs；不接受只有部分 remaining 的首次登記。
  WATCH 固定的 queue／intermediate／job hashes／relations／results／first_seen、
  queue-specific registries／worker／scheduler／cleaner keys、create-once marker 與
  `rq:queues`。任何舊 key、既有 queue membership 或錯誤型別都拒絕，不採用或清除。
- 單一 EXEC 先建立無 TTL marker，再寫入 raw hashes／ordered queue／registry membership，
  同交易讀回原 bytes／roster。只有確認回覆相符才返回後續 claim inputs；只有實際收到
  nil EXEC 才稱 conflict。連線回覆遺失、真正 Redis WRONGTYPE 交易錯誤、讀回不符及
  EXEC 後取消均為 uncertain，保留現場，不重送、刪除、退額或補償；交易中的部分錯誤
  不假設 Redis 已自動 rollback。早期取消仍明示 cancelled。
- 真私有 Redis／RQ lane 完成四模式登記→第一件 semantic claim，驗證相同 digest、
  全部 raw hashes、remaining order 與 intermediate；沒有 Job.perform／backend import。
  ordinary queue／job／expired failed registry 原 DUMP 與 registry member 保持不變。
  lost reply／runtime error 即使工作已寫入也不回傳可繼續執行的 enrollment。
- 原始行為 RED 保留：raw-only 接受不安全語義 **9 failed**、一般 RQ 未設定明確零 retry
  **1 failed**、真 RQ 覆寫已存在工作／重複 append **2 failed**；不是 missing-function
  setup errors。語義首版 fixture 曾誤用 `str(JobStatus)` 而非 Redis 的 str subclass
  encoding，已依已安裝 RQ 修正 fixture，沒有放寬產品規則。

最後 canary claim＋enrollment 定向 **108 passed／7.02 秒**，其中 claim 73、enrollment
35；XML `/private/tmp/stock-agent-canary-enrollment-boundaries-final-20260916.xml`。
enrollment 的獨立真私有 Redis 覆核 **24 passed／6.25 秒**，沒有 material finding；
XML `/private/tmp/stock-agent-canary-enrollment-independent-20260916.xml`。它與最終測試
使用相同 product SHA，但沒有重跑後加的 11 個案例。首次獨立測試因 sandbox 拒絕
UDS bind 而未觸及產品的 XML 另保留，不將環境限制當產品 RED；重疊案例不相加。

最後同版 16 個模組交叉回歸 **419 passed／51.45 秒、0 failed／0 skipped**，包括
維護 entry／guard／admission／RQ、正常 campaign runner／normal job／frozen scope，
以及 AGENTS 指定 runtime/storage 與 architecture。80 個警告為已安裝 RQ 的 utcnow
棄用警告，不是 provider 或報告品質失敗。XML
`/private/tmp/stock-agent-canary-enrollment-closed-integration-20260916.xml`，SHA256
`a6452a9b96ad4b4f77357eea354541e59d17c630216d2ff1783034923da069b6`。
產品 claim SHA256 `ab9df8b175a88d5297a4cc02413d12de61a1c4d574ee802952465b6b08e33f3a`；
enrollment `58f2a667b066cacb5a313a1837cd8229c7ff9f5f11150cd5b75a1af418728a6d`。
此結果不與較早 384／108／独立 24 項相加，也不要求重跑未受影響的前片 778 項。

以上 constructor／登記／claim 接點尚未接到正式 entry／control digest 或完整 controller。
caller 仍需可信預登記、durable attempt journal、專用 Redis／queue 的 exclusive ownership、
有限 timeout、來源／code／billing 資格及 shared budget。指定 keys 新建不證明全 Redis
不存在其他 queue 的同 ID 孤兒引用；Redis 收到交易不證明磁碟保存完成。成功登記／取件
仍 `execution_authorized=False`、`production_ready=False`，不執行 worker、不進 protected／
release。正式 Git 唯讀讀回仍 clean `758242290e795146520f58f68ffa113cac35e52c`；這不是
loaded SHA／健康證明。本輪未接觸正式 DB／Redis／API／模型；沒有 commit／push／部署／重啟。

### S0 維護整合：已驗證範圍與保留限制（2026-09-15）

本片仍沿用 21:07 起點、S0 8 小時及原集中修正限制；沒有重開模型／來源額度。
`maintenance_state.py` 負責檔案身分與狀態、`maintenance_guard.py` 負責公開生命週期。
0700 namespace、0600 bootstrap/state/locks、create-once 與 inode/hash 綁定均 fail-closed；
整個 namespace 遺失亦不重建 normal。原有或不完整 namespace 不自動解除。
`start_mac.command` 在 .env／pip／stop/start 前進入同一控制入口，normal 啟動持共享
descriptor 到自身 readiness；owner 遺失時已繼承 descriptor 的 launcher 仍保留 lease。
readiness observer 異常與啟動前／Popen 交接期間取消已有忠實反例及永久回歸；只向
自己擁有的 launcher 最多一次 graceful signal，清理未確認時明示，不謊稱排空。
初版控制 hash 包含兩個 maintenance 模組與入口，不以 backend commit 單獨代替；
23:00 接續再納入 readonly readiness／legacy inventory，完整六檔見下節。

- 分析 create/force/orphan recovery、legacy GET 新建、rerun 都在首次副作用前取得 lease；
  已受理 create→enqueue 可收尾，新的要求回固定白話 503；指定既有 job SSE／取消／權限保留。
- RQ 每次真 lpop/lmove 前檢查，stale ID／timeout 不借前一件的 lease。已取工作持到
  execute cleanup，下一件在 arming 後保留 queued。這不代表 RQ 獨立 scheduler 或
  worker teardown 的最後 Redis 寫入已全部受到同一 lease 保護。
- watchlist 從整批 claim 到全部派發維持原原子區段，原 N×45 秒節流不移除，drain 可能長。
  decision refresh 的已知 source Task 和 watchlist cache waiter 在重複取消後仍等實際
  source 完成；同步 backtest／清理／手動 mutation 在真正 action thread 內持 lease。
  caller 取消不是 thread 已停止；未知 provider 內部 timeout／脫離的 native 工作不作全域保證。
- 新 guard 只約束載入新碼的合作程序。舊入口 API-first cleanup、volatile Redis 保存、
  舊 scheduler quiescence、原版 rollback 保護與四個 frozen canary identity/queue allowlist
  都仍需正式 adapter 證據；**尚無 protected／release 指令，不操作正式控制狀態**。
  watchlist CRUD／GET metadata、其他 refresh／冷啟動 lazy migration 並非本片全部涵蓋；
  不宣稱「所有 GET 零寫入」或整個 formal runtime 已安全凍結。

主要證據（均在 `/private/tmp/`，前後重疊不得相加）：
`stock-agent-maintenance-state-split-green-20260915.xml` 112 passed／4.59 秒；
`stock-agent-maintenance-periodic-final-green-20260915.xml` 743 passed／14.97 秒；
`stock-agent-maintenance-watchlist-final-freeze-green-20260915.xml` 672 passed／60.77 秒；
`stock-agent-maintenance-rq-private-green-20260915.xml` 8 passed／9.27 秒；
`stock-agent-saved-artifact-replay-20260915.xml` 1 passed／1.57 秒；
`stock-agent-frontend-browser-isolated-20260915.xml` 2 passed／2.43 秒。
三份原 artifact 的 9 個檔案先複製至 `stock-agent-artifact-replay-20260915.HDcH3T`，
測後 cmp 與原檔一致；避免 storage getter 的 lock-file 副作用觸及正式 output。
歷史 v4／v3 artifact 仍各有 5 個 failed claims，另 6／10 unverifiable；此測試只證明
原有 gate 行為與數值匹配，不把原稿回補成合格。瀏覽器使用真 Chromium、私有 fixture
與禁止所有頁面請求的 test-only hook；桌面預覽 screenshot 已保存並目視核對，非正式畫面。

**必要 lane 補驗與適用性（03:26 讀回）：**

- `stock-agent-maintenance-rq-private-original-cli-final-20260915.xml`：26 passed／13.90 秒，
  新 10 項加既有 adapter 16 項。私有 Redis 僅 UNIX socket、TCP port 0；真 accepted job
  在 arming 後完成，下一件仍 queued；stale ID 與空佇列真 blocking pop 亦受控。
  原 CLI smoke 函式與 assertions 未改，API import 不消費、真 `worker_main --role queue
  --burst --max-jobs 1` 回讀 finished／9.0。fresh child 先驗 guard 載入，TCP／DNS／
  `.env`／formal SQLite／外部寫入／外部 dir_fd 均拒絕，只有精確私有 socket／DB 放行。
  原 `subprocess.run` 只在 test-only wrapper 換成自有 Popen 的一次 TERM／reap；沒有
  採用其 timeout 隱式 KILL。保留 scheduler raw exitcode 0 或 -15，不把已停止／join
  冒稱為其 Redis scheduler lock 已完成自行清理。此 lane 不證明正式 Redis 最後寫入保存。
- `stock-agent-commercial-qa-20260915.run2.xml`：原 8 browser cases 8 passed／17.90 秒。
  同版 source/static bytes、300 次被攔截私有 origin 請求、27 張 hash 讀回 PNG；人工看
  8 張，0 pageerror／passthrough，3 次 console 502 為原 error fixture。FastAPI 只提供
  實體 static bytes、不啟動 lifespan；API 回應為明示 fixtures／原 mocks，不是正式 readback。
  覆核 `/private/tmp/stock-agent-commercial-qa-20260915.review.md` 保留完整證據。
- `COMMERCIAL-UI-375-001`：375px 組合頁的加入持股按鈕為 46×170px 並超 form 12px；
  document-only 原斷言未抓到。獨立 containment 原期待為 1 failed／3 passed，375 失敗、
  390／768／1280 通過。相關 CSS 及整 commercial 目錄對 DEV HEAD／正式基底相同，
  屬既有非本批 regression；保留反例但不擴張四模式／維護片至組合頁 UI 修改。
- Chart.js 原 6 cases 尚未驗證：缺有來源／版本／完整 hash 憑據的本地 Chart.js 4.4.0
  UMD bytes；沒有新增 CDN 下載或以 stub 取代圖表。Python 禁 socket 不等於 Chromium
  禁網，後續須精確 URL fulfil 已驗 bytes、其餘 abort；仍為發布前置缺口。
- 兩項 checkpoint optional 不標通過：舊 prompt 80% 比較的 HEAD 已與候選程式相同，
  需找回真正歷史 baseline／fixture；Gemma 12k 是指定 profile／fixture 條件，不准截斷
  完整來源硬湊容量。唯一抽查的較新私有 DB，latest inline channel_values 只有
  quality_draft，與舊直接讀列的完整 graph reader 不相容。readonly 診斷 1 failed 保留，
  DB before/after hash 相同；不以合成 state 或 12 組 graph doubles 替代原 benchmarks。
  `/private/tmp/stock-agent-optional-lanes-applicability-20260915.md` 是適用性盤點，不是這 8 項通過。

首次整庫 `stock-agent-maintenance-full-nonlive-20260915.xml` 保留：1127.60 秒，75 subtests
另列、不加總成更多獨立案例；21 skips 含 PostgreSQL collection 1、fresh external 3、
commercial 8、兩個 checkpoint、Chart.js 6、原 RQ 1。commercial／RQ 已由上列同版隔離
原測試另驗，其餘依適用性保留。原 live 2449 為 1 deselected，不代表已驗證。
整庫前後 backend／scripts／start entry manifest 均為
`f659369325c203c229367bace85df6274b50e9dbeb7ae63573582425fe3cc9c0`。

**最後候選讀回與前述待驗狀態的更新（03:55）：**

- 13 個原失敗全來自 `test_genai_client_receives_request_timeout` 遺留 fake client；
  facade 同時直接寫入 transport 的 timeout 與 SDK module。原順序重現 13 failed／
  16 passed，另 6 個 ownership 反例先紅；只在污染來源測試隔離自有 cache 並登記
  兩個 seam 的還原，保留其他 owner cache 身分／內容、不關閉他人 client、不放寬
  campaign 的 fresh-client gate。修後 35 passed／2.38 秒；主代理已讀實際 diff／反例。
  `stock-agent-sdk-cache-test-order-green-20260915.xml` SHA
  `9058941a4b7662305c6b32deb4d17d760b9f0618cd527c5e93cc767290204fec`。
- 最後整庫明確使用不存在的私有 pycache prefix 且 `-B`，由當前 source 重新載入，
  不沿用搬遷前 pytest bytecode 路徑。`stock-agent-maintenance-full-nonlive-final-20260915.xml`
  為 12,750 passed／1 failed／23 skipped／1 deselected、75 subtests，1156.45 秒；SHA
  `c6c334b12285037b61bb956139ae5b8917a2f01817d19af5900a9de5e8b62025`。
  唯一 failure 是原 Chromium launch preflight；另兩個 frontend skip 的原 browser log
  明確是 MachPort bootstrap permission denied。這是工具沙箱環境失敗，不安裝／升級
  套件或改 assertions；相同 source 與冷載入設定精確升權後原 preflight 8＋frontend 2
  為 10 passed／3.55 秒，`stock-agent-maintenance-final-browser-preflight-20260915.xml`，
  SHA `d47eefe1792441d84c6012a9e7354d7dc230e50385892b964f76ef14ba5b6c71`。
  完整 backend／scripts／entry／tests inventory 在最後整庫前後相同：
  `2a6f626ff5c7534e8b526975d5e6574337013141703bc40f7a72db1814be093c`。
- Chart.js 缺檔是當時盤點，不是必須再次向使用者要求一般核准：核對原 S0 的必測
  browser lane 後，只取得既有 HTML 固定的 4.4.0 URL 作測試相依，不新增或升級依賴。
  精確工具升權核准的單次無認證 GET 在 19:44:58 UTC 回 HTTP 200，205,222 bytes，
  header `x-jsd-version=4.4.0`；沒有登入、cookie、研究資料或模型外送。這不是 IR 文件
  取得，不延長到期來源窗口；原 97-GET ledger／13-document corpus hashes 不變。
  私有 acquisition receipt：`/private/tmp/stock-agent-chartjs-existing-20260915.2fSp7n/acquisition.json`；
  bytes SHA `0e2326c6868072bec1592760c6729043caeea2960a2b46cee6a2192aac6abff0`。
  它證明 HTTPS／版本 metadata／凍結 bytes，不冒稱 Sigstore 或獨立 source build 證明。
  原六項 `stock-agent-chart-qa-20260915.run3.xml` 為 6 passed／14.50 秒，SHA
  `e5dadfaa2372c353e750292ff02dae14a26df8c652e82721b4cef79c1c9b3b46`。
  只有精確 GET library URL 與預登記私有 HTML bytes 可 fulfil，其餘 abort；原 CSP
  不改，沒有一般 network passthrough。原 security 兩頁均阻擋注入，未接正式 API。
  最後保存截圖的 run4 為 **6 passed／29.11 秒**，只有原斷言後的 capture wait，不改
  測試期待；XML SHA `e8ccc794647add9f4c707b21fdfc87d9cc0322e7943f4eda6c1178d8e82c81c8`。
  18 張 PNG 與 12 份頁面讀回；9 個成功頁的實際 Chart.version 均為 4.4.0，另 3 頁
  是原測試刻意阻擋依賴。36 次 browser GET 全受限，沒有 passthrough／pageerror；
  預期 CSP／資源阻擋及 parser warning 仍保留，並非 console 完全為零。
  目視的兩個疑點另以原保存 HTML／CSP 做 **2 passed／8.47 秒** 的有界診斷：
  security canvas 捲動前後像素相同、捲至圖區後截圖正常，是離屏截圖現象；十圖頁
  不干預動畫、自然載入後所有線點與 scale 位置相符，先前異常來自原測試中途 update。
  主代理已目視原零值手機圖、原安全圖區與自然載入十圖；沒有為圖表改產品程式。
  診斷 XML SHA `08031586e90cd6a97e0dada9cdad123b630f00817428237349a15d0eeb602d47`；
  最後覆核 `/private/tmp/stock-agent-chart-qa-20260915.review.md` SHA
  `26608fccf21e81b50eba997f2fafc3c1b4f729307c1a7e0788c125184512a7da`。
  以上只關閉本次 Chart.js 必測 lane，不是正式報告品質、Safari 或全站視覺驗收。
- 正式程序唯讀核对補足「由誰啟動」而非安全移交：03:39–03:52 看到正式
  `start_mac.command` PID 42603 管理 Redis 42632、`worker_main --role all` 42634
  及 `uvicorn api:app` 42636，均在正式 backend／其 cache/redis 目錄，9月12日啟動；
  Redis 6379、API 8080 有 listener。沒有發 signal／Redis command／API request。
  同一父程序不證明沒有其他 Redis clients，亦不證明目前 persistence 設定、最後寫入
  保存、loaded SHA 或健康；首次移交／canary／rollback 缺口仍保留。

**舊 API 探測與 Redis 保存元件補齊（04:35；不是正式移交完成）：**

- 新 `scripts/maintenance_probe_app.py` 是不自啟動、不讀 settings／backend 的版本中立
  ASGI filter。私有既有 0700 目錄中只建立新的 0600 UNIX socket，沒有 TCP listener，
  只允許 exact GET／空 body 的 `/healthz`、`/api/runtime-identity`；`/readyz` 必須注入
  獨立 handler，絕不轉入原 mutating route。其他路由／方法／query／body／websocket 拒絕。
  關閉保留 socket marker，不自動刪除或接管；原 app lifespan 明確仍會初始化儲存。
  它不代表 OS sandbox，controller 仍須綁定來源、程序與 namespace ownership。
- 原 `readyz` 的忠實反例證明 storage initializer 會建立 DB，RQ registry.count 會清理
  過期資料。因此新增 `scripts/maintenance_readiness.py`，要求精確目錄／5 個 SQLite
  路徑／來源已知的必要表名／queue manifest。讀取採 mode=ro、query_only、trusted_schema
  關閉；WAL 必須已有 WAL／SHM，不用 immutable 跳過真實 locking。沒有 mkdir、migration、
  job 反序列化或 registry cleanup；Redis 僅 PING／LLEN／ZCARD，保留過期與 dangling 項目。
  現存 SHM 的讀取協調位元可能改變，故聲明是 logical read-only，**不是 filesystem-inert**；
  這與 [SQLite WAL 唯讀條件](https://www.sqlite.org/wal.html#readonly) 一致。
  結果另用 `stock-agent.maintenance-readonly-probe.v1`，成功仍 `production_ready=false`。
  不驗全 schema／writeability、worker 健康或跨資源原子快照；精確 endpoint／timeout 與
  防止檢查期間路徑被置換仍是 controller 前提，不由 helper 自簽。
- 真完整 baseline API：`git archive 758242290e795146520f58f68ffa113cac35e52c backend`
  至 `/private/tmp/stock-agent-legacy-probe-20260915.cD8iV7`，**2,240 個 Git blob** 前後
  以 Git object 格式 hash／完整清單驗證，沒有 `.env`／正式 cache／output。
  fresh `-I -B` 子程序先安裝 audit 邊界，再載入原 app 與完整 lifespan，實際 Uvicorn 僅
  使用上述 UDS；原一般 SQLite job 與真 RQ 普通工作保持 queued。缺 readonly handler
  的 readyz 回 503；接入真 baseline builder 後回 probe_pass，仍不是 production ready。
  request 前後 DB／WAL hash、家族檔案清單、expired registry sentinel／一般 queue 不變。
  原 startup 只初始化私有 warm-state，不冒稱原 API 啟動零寫入；測試非正式 runtime readback。
  Uvicorn 完成 shutdown 後會重送 SIGTERM，保留 raw exit -15 並另外要求實際 lifespan
  close receipt／listener fd=-1，不以改 exit code 假造 graceful cleanup。
- 新唯讀 URI 放行的 test-only audit 曾被獨立反例發現 bytes URI 可繞過 str 判斷。
  固定先用 os.fspath 並拒絕非 str；URI 只放行完整註冊的原始 str，其他模式與附加 query
  均拒絕。原 **3 failed／8 passed** 反例不改期待，修後 **11 passed**；另固化 11 項
  永久回歸。一般 Path DB 仍可用，三份 sentinel 值未變。這是測試隔離缺口的閉合，
  不宣稱正式服務遭存取或憑證洩漏。最終 bootstrap SHA
  `ca712bafc2d40347ad468f499cb9d1cc2d4d8b3e6a76947b8a1de1e412ac7ab4`。
  獨立 closure `/private/tmp/stock-agent-maintenance-readonly-guard-independent-review-20260915.md`
  SHA `540def9ee62fed15b5f835650416baffbe43012346b48091e1619df8cabb68e3`。
- Redis 保存證明使用既有 Redis 8.8.0／RQ 1.16.2、port 0／唯一私有 UNIX socket，沒有
  應用程式／provider import。初次 SAVE 後再寫 queued／scheduled／deferred 工作、quota
  與 reservation。NOSAVE 負例確實遺失晚寫資料；**SHUTDOWN SAVE** 後同二進位真重啟，
  key 型別／原始值、順序、score、payload 及絕對 expiry 完整讀回（另驗原本到期的一項）。
  不重置排程時間或 quota，也不由 fixture 推論 provider 額度。4 個自有 Redis 程序均
  return 0／reaped，每個只下達一次 shutdown；沒有正式 Redis command／signal。
  `stock-agent-maintenance-redis-preservation-final-green-20260915.xml` 為 2 passed／4.89 秒，
  SHA `55aaa42db80ee9a0e9c6249a3d3db862c1a2e887d0182f0cca3d40e7a9a6d676`。
  **這不證明舊 launcher 的 SIGTERM／save 空設定有同樣保存語義，也尚無正式移交順序。**
- 最後同版整合 `/private/tmp/stock-agent-maintenance-handover-components-final-20260915.xml`
  **198 passed／0 failed／0 skipped／26.20 秒**，13 個 upstream utcnow warnings 保留；
  SHA `0f69c219de7bceb8ab6b79875098d77049bbb414675b2ff44554f811486fca6a`。
  包含 probe／readonly／guard URI／兩個真原版 app 變體、原私有 RQ／CLI、entry／worker
  啟動／maintenance guard 與 Redis 保存。私有 socket lane 採精確工具升權，內部禁止
  TCP／DNS／`.env`／正式 DB／外部寫入邊界保留；無額外模型或正式服務存取。
  baseline lane 必須給已驗 archive 路徑，預設 skip 不算發布證據；本次已明確給值並執行。
  readonly helper 獨立 69 passed、private probe 獨立 13 passed 與此 suite 重疊不相加。
  本版 backend／scripts／entry／tests inventory 為
  `efa0829982e0cd53995ffae628e119cada3650fd8adb23416f586f26e208d2e6`；diff --check 通過。
  前述 12,750 項整庫是較早凍結點，不冒稱包含其後新增的兩個 scripts／測試。

以上兩個產品 helper 尚未接到 maintenance entry，未列入其 control digest；沒有
protected／release／rollback 指令。entry 真正引用時必須同步納入控制身分及受影響回歸。
現存單元、隔離整合及特定 shutdown-save 機制已可重用；不能以元件綠燈代替第一個舊程序
完整交接或四份正常業務 canary 的 gate。

**取件前 raw claim 元件（05:00 已限定驗證；不是完整 worker）：** 原 RQ 1.16.2 的 `work()` 在 dequeue
前先 bootstrap／maintenance；`Queue.dequeue_any()` 是 LMOVE／LPOP 後才 fetch，
`Job.restore()` 本身已可反序列化 meta／result。成功及失敗處理還可能派送其他 queue
的 dependents。因此不能靠 max_jobs=4、execute-only 檢查或空一般佇列 fixture 來驗收。
本片實作有界 raw claim：先核对完整剩餘 roster、已預登記 raw byte pins、空 intermediate
與 dependencies，再原子移動一個精確 ID；衝突或不確定提交不得自行重試。這不會直接
執行工作，也不代表已完成 frozen 業務入口、預算、callback／retry 語義及 controller。

- `scripts/maintenance_canary_claim.py` 只接受精確 queue、最多四份唯一已註冊 ID／完整
  bytes pins 與剩餘順序；先複製 pins，避免 caller 在 WATCH 中改驗收值。WATCH 同時覆蓋
  queue／intermediate／所有剩餘 hash／dependencies／dependents，未全部相符不進 MULTI。
  只有一個 LMOVE，沒有 Job.fetch／restore／反序列化、worker／scheduler 或一般 queue cleanup。
  精確連線／有限 timeout、可信來源與函式／callback／retry 語義、維護授權仍由 controller 提供。
- 檢查 WATCH 實際租用的 installed Retry 必須為 0，不修改共享 client／連線策略。只有觀察到
  MULTI OK、LMOVE QUEUED、EXEC nil 才判 conflict；EXEC 後 I/O 失敗即使 redis-py 包裝成
  WatchError 也維持 uncertain，不重試、退額、回填或假設工作沒有移動。只包本次私有 pipeline
  的 parse handler 並恢復；沒有修改全域 Redis 類別。
- 原 9 項行為先紅後綠；加入真私有 Redis 後 14 passed。獨立發現 EXEC 前取消被混成一般
  rejected，原 2 failed／4 passed 與作者 6 個 pre/post × cancellation 紅例保留；修成
  cancelled／uncertain 並保留 cancellation_requested。root 再以真 dict.update C-return
  中斷重現最後收據窗口：outcome 已改 uncertain 卻殘留 stop_required=False／raw_snapshot。
  原 2 failed／0.11 秒保留，沒有偽造 result；最窄修正是在回傳前統一清除非 claimed 的
  raw_snapshot／job_id 並要求停止。兩個原反例同期待固化永久測試，沒有放寬驗收。
- 最後 22 個永久案例包含真私有 Redis 五情境：claimed、payload drift、第二連線 WATCH 後
  插入 foreign job、真 EXEC commit 後遺失回應、真 commit 後取消。每案最多一次 EXEC；
  committed 未知情境的 job 確實留在 intermediate，沒有回填；ordinary queue／job hash／
  expired failed registry 的 DUMP 前後相同。該 lane 不執行應用工作，不能推論已完成 S4。
  原作者＋root scratch 24 passed 有兩個重複案例，不當 24 個獨立永久測試。
- 原獨立 6＋root 原 2 之檔案與 assertions 不改，最後 **8 passed／0.14 秒**，
  `/private/tmp/stock-agent-canary-claim-independent-final-20260915.xml` SHA
  `2e48303f444d48d65c23d4101d6a6e456dceb53e5604e776890aacd246e3788b`。
  這是限定 raw claim 的獨立 closure，非整體 controller／正式發布認證。
- root 最後同版整合 **220 passed／0 failed／0 skipped／26.13 秒**，13 個 upstream
  warnings 保留；`/private/tmp/stock-agent-maintenance-handover-claims-closed-20260915.xml`
  SHA `7bf7b28ca4ae053ad29de83208a2a7ca486e7ba8e148df5793f6f67195dca773`。
  包含先前 198 個維護接點與最後 22 個 raw claim 永久案例，重疊不另加總。修前 218-pass
  XML 與兩代取消紅例均保留，不借修前綠燈作修後證據。
  helper SHA `c41064a587b48bc72186f4a850e501e58ca9cd8df1cdd77101a313a7c23fce9d`；
  test SHA `96b76f57567139452c4eed1fee3be15cb77ee28d093b430dc919c06f2c137e7d`；
  child SHA `5fb1e95d81218546195c351a39ab785c959ae47c2ae76364b52d292b1d6d532f`。
  最後 backend／scripts／entry／tests inventory 前後同為
  `4a697bbc765044b7d1fe4e2eb2ab93e236b03c1f4abce6c86e1219db9d2ce2d4`，diff --check 通過。

05:00 保守牆鐘檢查：沿用 21:07 起點已過 7 小時 53 分鐘，**不是另開 8 小時**；這是
牆鐘讀回，不冒稱精確主動工時帳本。S0 尚未達全部出口；不在僅餘約 7 分鐘的保守窗口
啟動無法完整整合驗證的首次移交／業務 canary 大切片。三個已驗 helper 都未接 entry／
control digest，保留凍結待整合狀態，不將時間將盡改標全部完成，也不開始依賴缺證的 live。

05:07 保守牆鐘界線已到；仍不將牆鐘當成精確主動工時帳本。此後僅收錄已取得的
歷史版本證據及交付狀態，不另開實作／測試批次，不延長來源或模型送件預算。

**集中剩餘清單（2026-09-16 接續更新；不重設來源／模型預算）：**

| 工作 | 目前證據與接續條件 |
| --- | --- |
| 維護基礎與最後候選回歸 | 本批已驗證；整庫唯一環境失敗由同版原測試補驗，原失敗 XML 保留。沒有重新計算或合併相互重疊的案例數。 |
| 舊服務安全移交、canary／rollback | **完整程式仍未完成**，不能寫成只等市場。原父pipe／deadline／group／journal已接claim→normal child→RQ terminal→原job預算CAS，無退款或stage放行。最新十個controls＋七個harness與loader／shell共19份來源同批綁定，末版193項相關、11項真私有四模式／拒收／停止／漂移與36項獨立覆核通過；前版833／56與本輪前版29項保留版本界線、不相加。這不是native sandbox或protected。接續舊scheduler claim歧義處置、Redis磁碟移交及正式entry／release／rollback。S1 prerequisite仍為fixture；來源／billing／live尚未通過。 |
| 研究來源與預登記 | 兩份 v4 核心候選不等於 source_review 通過；還需財務口徑裁定、精確來源綁定、完整 152-slot 名單，尤其 S3 金融業原始法說文字與跨產業／日期樣本。到期 IR 窗口不得自行延長；簡報、問答摘要與破字稿不能代替完整來源。 |
| 真實計費與路由上界 | 缺匿名 key slot→Google project→tier／billing 狀態的可查證對照；已讀公開價格文件不證明實際帳戶免費。需要遮蔽憑證的帳戶證據，不能要求把金鑰貼到對話，也不能用測試標籤自行宣告 verified_free。 |
| 兩個 checkpoint benchmark | 保留未驗證：已定位 prompt boundary 修正前的 Git parent，見下節；仍缺原 checkpoint 的精確 DB／thread／hash 及 Gemma 原設定，尚未验证歷史模組相容性與原 benchmark。不以當前 HEAD 或合成 graph 假充。PostgreSQL 非本次 SQLite 後端，仍未驗但不據此宣稱舊 PG 任務完成。 |
| 真實 S1–S4、提交／發布 | 本批 0 新模型呼叫、0 合格完整報告；尚未 commit／push／PR／部署／重啟。只有原條件全部成立才沿用已核准 152 jobs／2,400 HTTP 與 transport 各自上限／160M tokens／US$50 預估停送線，不重用舊單次收據。 |

接續者從此清單及 `/private/tmp/stock-agent-maintenance-handoff-20260915.md` 的未完成
adapter 開始，不重跑已凍結且未受影響的整庫／圖表測試。來源與計費缺口要求的是實際
文件／遮蔽後對照證據，不是使用者再回覆一次「核准」。本批交付不等於 S0 或整體目標完成。

### 凍結輸入正常入口：21:48 接續證據與限制

`backend/analysis_frozen_canary.py` 是 controller-only process-local scope，不是 launcher、
source_review 或 SDK/network sandbox；沒有公開 API／環境變數／序列化 payload 開關。
唯有同一 async owner 可 claim 一次 exact job／ticker／單一 v1–v4；immutable UTF-8 JSON
需 raw SHA256、manifest SHA256、原始 aware cutoff 與 data_trust。拒 duplicate keys、
非有限數字、身份不符、force-refresh、nested/reused/expired scope。Graph child tasks
可沿用仍有效的 scope，但不可重新 claim job；跨 thread/process 或生命週期結束拒絕。

- 正常 `analysis_jobs` 在第一次 job write 前驗 binding；凍結分支不用 StockDataService
  或 temporal-memory lookup，保留原 memory、fetch_date、analysis_input_cutoff，仍用真
  QuantEngine、input provenance、pipeline runner 與正常品質 veto。Source bytes 不改，
  derived workflow data 另綁 hash；輸入收據明示 production_ready/publication_authorized=false。
- Workflow request 在 service factory 前檢查，避免錯誤輸入先造成 KeyRotator 的 Redis
  PING。只接受 controller 指定的 absolute SQLite path，不接受另一 saver／PostgreSQL；
  真 saver 在 graph deserialization 前查同 thread 所有 namespace 的 checkpoints／writes，
  completed、pending、其他 namespace、quality draft、orphan write 均拒絕。
  空 thread **不是** sole-writer／精確 filesystem isolation 證明，不授權使用正式 DB。
- Prepare／official reconciliation 明示 unavailable；RAG 的同步／非同步 build 和 agent-level
  ensure 均在 cache/embedding 前擋下，清除未資格核驗的舊 index/context。不依賴只換 prepare。
  Agent-step cache、內層模型 retry、HTTP／token ledger、真正工具網路／通知／交易出口
  仍須由後续 controller／transport 綁定與驗證；不能由本片推論全面零外送。
- Provider transient/rate-limit 保留原 exception，但不呼叫 prepare_analysis_retry 補回 RQ
  預算；DB 標 error，event 明示 queue_retry_state=controller_must_verify_zero。
  這不證明既有 RQ payload 的 retries 已清零，controller 尚須取件前驗 raw 零 retry。
- Frozen output 先過原 publication gate，再固定停在 renderer／artifact/index 寫入前，
  不回 done/report_done。這不是零檔案寫入：私有 job/event/checkpoint／目錄仍可寫入。
  一般任務未安裝 scope，原 fetch、memory、retry、品質與 checkpoint resume 行為維持。

本輪獨立唯讀覆核關閉 checkpoint resume／agent-level RAG 兩個實質缺口，未替代執行證據。
最終 XML `/private/tmp/stock-agent-frozen-canary-input-final-green-20260915.xml`，SHA256
`255fd292d0b827d3aa5fb4d01c35111ca80f241b552bfc218242753106dd5cb9`，
**371 passed／8.19 秒**；其中新 80 項測試包括真 normal entry＋真 initialize＋真 SQLite／
LangGraph 的四模式單節點 diagnostic fixture，但沒有真模型，不能當完整報告合格樣本。
同批涵蓋原 publication veto、normal retry/resume、quality drafts、RAG 與必跑 runtime/storage。
另一份互補 admission／RQ wrapper／analysis API／architecture 回歸為 **201 passed／3.15 秒**，
`/private/tmp/stock-agent-frozen-canary-admission-integration-20260915.xml`；12 個 warnings
來自 RQ 的既有 utcnow deprecation。兩份結果分別保留，不與歷史跨版本收據相加。
新增 input、cutoff、RAG、checkpoint 的真行為 RED XML 均保留；中途 fixture API 欄位修正
及既有 settings reload 的測試順序污染也保留原失敗收據，沒有刪測試／降低斷言。
`test_prompt_rag_evidence_budget` 現明確綁定它正在設定的真 models.get_agent_rag_budget；
修前單跑 9 passed，但 settings→budget 同序 1 failed；產品設定與預算函式未修改。

此片最終 source/test SHA256（不以 DEV 基底 commit 冒充 dirty tree 身分）：

```text
backend/analysis_frozen_canary.py c84c1fb5cceadf84a849c1b015c8c11916b6a7e22497bf2bda5d450d1de209a1
backend/analysis_jobs.py 9356d5486d034e73e6c8474b740d93b8eb459ac3366364547ff7c579a792d655
backend/analysis_job_provenance.py df6b1c6e4ed6caa52cb6dcb937e14f4c80b046a1e06b1a50dc0caca385306574
backend/agent_runtime/pipeline_runner.py 0ef5577a41577eabeaa56402386884db69749b98b9d086458ecb54a3b246478c
backend/rag_runtime/service.py f20720b5222c3912f7833c717b34fea5ef053495d67cb91c9ece7d24886b473f
backend/workflow_checkpoints.py 527805ab1caace30ba4a739ef27b4eaed7a6ed8067343f0e5e55aecfd90066d9
tests/test_analysis_frozen_canary.py 1f42ff1a9c6cb70d60a06b9d27b60550171bae77e8f0e61e87fb3d4c66c831ad
tests/test_prompt_rag_evidence_budget.py b25c9f34fbc13313ca4bc541ed01896f784b04b85eeb2d6024973380f7eb0b0e
```

舊 scheduler 移交仍是獨立阻擋：舊 `last_run_dates` 同時表示 claim／完成，trigger event
可先保存空 job_id，與合法略過／派發前中斷無法一一區分；退出碼 0 或空 queue 不能證明
pending_claims=0。23:00 接續只讀 inventory 已把 ambiguity 留為 pending_count=null／
settlement_proven=false，不自動 backfill、重送或刪 claim。正式首次移交不得用本片略過。

### 舊排程唯讀盤點與原入口接線（2026-09-15 23:00 Taipei）

`scripts/maintenance_legacy_inventory.py` 只讀 manifest 指定的 exact absolute path；
支援明確聲明的舊版 `758242290e795146520f58f68ffa113cac35e52c` metadata 契約。
它不自行探索環境、不 import backend/store、不建立／遷移 DB，不接 Redis、重試或改 claim。
backend_revision 是呼叫者的宣告與 reader 支援範圍，不是 reader 已核對正式 PID／版本。
controller 對實際路徑、舊程序、排空與 sole-writer 的核驗仍不可省略。

- current watchlist、trigger configs/events、meta markers、全部保留中的 active／terminal jobs
  及 job event 摘要一起盤點。保留 disabled、orphan item、跨日與月初原日期、source mode／
  selected mode；不只取最新紀錄。job 候選關聯與 explicit job_id 都不證明完成派發。
  event payload、報告正文、錯誤原文和模型資料不讀；worker identity／meta marker 只輸出 hash。
- canonical／task／legacy 的相同 literal path 共用單一 read transaction；同 canonical 的
  legacy 角色不重複列出事件。不同路徑不是原子快照；不同 legacy 來源中的重複歷史亦
  不視為獨立待辦數。`observed_ambiguous_claims` 只是標記／matched event 觀察數。
- SQLite 用 `mode=ro`／query_only／trusted_schema=OFF／memory temp，拒 journal、symlink、
  缺 table／column 與未齊備 WAL sidecars。讀取既有 live WAL，DB／WAL metadata 變動拒收；
  既有 SHM read marks 可變，明示 filesystem_inert=false，不宣稱作業系統級隔離。
- 每 table 最多 10,000 rows、每 DB 選定值 JSON bytes 最多 8 MiB、SQL progress deadline
  5 秒，legacy JSON 8 MiB。這不是 OS memory／整個 JSON 輸出大小的硬上限。
  超限保留 table_counts／truncated_tables 與部分觀察，readback_complete=false；缺檔、
  權限錯誤、壞 JSON／metadata 也不默認空集合成功。原始資料不正規化、不回寫。
- `readback_complete=true` 只代表指定路徑的保留 metadata projection 讀取完整。
  固定 `history_complete=false`、`settlement_proven=false`、`pending_count=null`、
  `legacy_handover_verified=false`、`production_ready=false`，不讀 queue／process state。

原 `start_mac.command --maintenance-legacy-inventory ABSOLUTE_MANIFEST_JSON` 會在正常
啟動、.env、服務操作與維護 state 初始化之前返回 JSON。exit 0 **只代表 projection 讀完**；
partial/unavailable 回 75，不能以 exit 0 自動繼續移交。manifest 範本如下，佔位路徑不可照用，
本輪沒有建立或執行正式 manifest：

```json
{
  "schema_version": "stock-agent.legacy-dispatch-inventory.v1",
  "backend_revision": "758242290e795146520f58f68ffa113cac35e52c",
  "control_sha256": "REPLACE_WITH_CURRENT_MAINTENANCE_CONTROL_DIGEST",
  "paths": {
    "watchlist_db": "/EXACT/VERIFIED/watchlist-or-operational.sqlite3",
    "task_db": "/EXACT/VERIFIED/operational.sqlite3",
    "legacy_watchlist_db": "/EXACT/VERIFIED/legacy-watchlist.sqlite3",
    "legacy_watchlist_json": "/EXACT/VERIFIED/watchlist.json"
  }
}
```

control digest 為 `start_mac.command`、entry、maintenance_state、maintenance_guard、
maintenance_readiness、maintenance_legacy_inventory 六檔的 path→SHA256 map digest。
先讀齊 source buffers 並驗 manifest digest，再只 compile/exec 同批已驗 bytes；另保留
後置 drift check，finally 還原原 sys.modules。不能執行其他 checkout 預載 module 或
先執行未綁 bytes 再宣稱驗證失敗。這不是防禦任意 host-owner 修改的 OS sandbox。

**驗證：** 私有隔離、禁止網路的正式測試入口，共 **189 passed／3.95 秒、0 failed／
0 skipped**，包含新增 59 項 inventory 測試及真 shell complete/incomplete 路徑、舊版
schema／claim／mark 函式（先逐檔與 git show baseline 比對）在真私有 WAL 的反例。
覆蓋真 WAL／缺 sidecar、缺檔／view／缺欄、manifest drift、歷史留存、錯誤資料與
runtime/storage 必跑案例。唯一 warning 是既有 RQ utcnow deprecation；獨立 source
覆核不替代這份執行證據。新增兩個 shell 案例在 source 覆核後加入，產品 SHA 未再變動。

XML `/private/tmp/stock-agent-legacy-inventory-entry-integration-green-20260915.xml`，SHA256
`89283cdfa981e403a05cce60d93d58273280fdee6de6cb0fe342ef84300d7193`。
CLI 缺接點、foreign sys.modules、壞 trigger metadata、pre-exec source drift 的原始 RED
XML 均保留；不改寫成綠燈，也不把先前重疊 109／135／187 項相加。

```text
scripts/maintenance_entry.py a786ffec2baf74c770e08c34f287668fa5e6c6036c2e4c26c1fec23092f6d9f8
scripts/maintenance_legacy_inventory.py 1710700015adba336553564f6f325f3ab9bb01f8a20c2577edf2cbb05c49d78a
tests/test_maintenance_legacy_inventory.py f212b22e61d0165b8ace4503f2ffc7d5dba97ed10a5049fc973f91ec31fea0a8
```

**下一個未完成接點：** 首次移交 controller 必須消費這份盤點並對 unknown 保持停止，
再與舊程序 graceful exit／UDS probe／Redis 保存回載串成有失敗回復證據的順序。
本片沒有執行正式盤點，沒有取得 claim 已安全結束的證據；不以新補模組改標 S0 完成。
受限業務 canary、SDK／預算、不可覆寫發布及 rollback 也仍未接成完整 controller。

### Controller-owned 程序生命週期（2026-09-15 23:23 Taipei）

`scripts/maintenance_owned_process.py` 使用 caller 明列的專用既有 0700 namespace，
create-once 0600 `process-attempt.jsonl` 保存 hash-linked 有界紀錄。namespace、cwd
與 readback 均拒缺值，不能沿用環境 fallback。只保存 command／environment hash，
不抄入 secret values；binding 的 revision 是 caller 宣告，不冒充實際 child 已載入證明。

- reserve／namespace fsync 後，先保存 launch intent，再執行一次 Popen；只有此 object
  實際持有的 child handle 可收一次控制器發出的 SIGTERM。先持久 stop intent 才送信號，
  失敗或取消不自動重試、補第二次 TERM、KILL、接管任意 PID 或刪掉紀錄重來。
- public start／stop／wait／snapshot／close 使用非阻塞、不可重入 Lock；同 thread 的
  signal handler 重入也拒絕。原 RLock check-then-set 窗口曾真送出兩次 SIGTERM，
  保留原 RED 和相同期待的永久反例；close 也先移除 object 持有的 FD 才關閉。
- 觀察 interval 上限 60 秒；timeout 只代表退出未確認，不代表停止或重新啟動的許可。
  close 只關 controller FD，不暗中送 signal，也不代表 child／descendants 已清理。
  真 parent os._exit 後，實際 private child 仍活著；原 journal 保留且新 owner 不可
  readopt／relaunch。測試只讓該 fixture 透過專屬 finish 訊號自行退出，未向 orphan
  發 signal；即使已觀察其退出，沒有原 controller 的 exit 記錄也不回補假收據。
- process_exited／raw returncode 與 cleanup／descendant settlement／handover 完全分開；
  後三者和 resume_authorized 固定 false。journal 是歷史觀察，不是目前 liveness 證明。
  這不是任意 host-owner／same-UID 攻擊防護，也不提供既有正式程序的 adoption。

**驗證：** 新增 27 個永久案例，包含真慢 child、取消的 pre/post signal、launch return
  遺失、fsync 失敗、原 reentrant start/stop、close、壞紀錄、exit 7、secret projection
  與真 owner loss。最初缺 module 的 RED 只是 setup 失敗，不當成功抓到行為缺陷；
  其後 None path 與真雙 SIGTERM 的 RED 才是有效的邊界反例。獨立唯讀覆核關閉兩項
  finding，未代替主代理執行證據。

既有 `test_maintenance_legacy_probe_integration.py` 改由此 owner 啟／停完整 `75824229`
原 API，保留原 archive 2,240 blobs 前後核對、lifespan、UDS-only、readonly／缺 handler
兩情境、一般 job／queue、DB／WAL 不變與 app close 斷言。owner 的控制 hash 明列它與
maintenance_state source，與 backend revision 分開；不冒稱整個進程都是純 baseline。
Uvicorn 自身 cleanup 後重送 SIGTERM 的 raw -15 保留，不改成 0；本 controller 不重送。
這是原生應用的私有整合，不是正式 drain／恢復一般服務，也未增加新模型呼叫。

最終同版整合 **250 passed／10.00 秒、0 failed／0 skipped**，包含上述兩個完整 API
情境、owned-process、legacy inventory、readiness、entry／guard、runtime/storage 與
architecture。唯一 warning 是既有 RQ utcnow deprecation；不將先前 126／2 項相加。
XML `/private/tmp/stock-agent-owned-process-final-integration-20260915.xml`，SHA256
`d7ba48f718869fabbcdf23cf9608157c626785a96d09e2b1d17804c15c34d95a`。

```text
scripts/maintenance_owned_process.py fb54f1b397998ccbbbbd1fd9e836c8a8e4ce9b21fd0b9e0b779c4b0fff15c2ff
tests/test_maintenance_owned_process.py 1b5c1110612a554d0471e4cf69b24c6963d9e4d154e0d518a7b7856977437bd5
tests/test_maintenance_legacy_probe_integration.py 735ed300248c66afe494c784727075b5579d185a1cffbe3ae531895c207e8511
```

此 owned-process 元件目前僅被私有整合 lane 使用，尚未被正式 entry 引用或納入其
control digest；不能把新增 library 當成 controller 已可執行。下一步仍需沿用同一
收尾方案，把首次舊程序 ownership／unknown-claim 判定、最後 Redis 保存／readback、
受限業務 canary 與 rollback 接成完整順序，並保留各自安全拒絕和失敗恢復邊界。

### checkpoint benchmark 歷史 baseline 定位（05:07 收尾）

本輪只有本機唯讀 Git／文件／檔名查核，沒有執行模型、benchmark 或正式 DB 查詢。
`tests/test_prompt_checkpoint_replay_optional.py` 以 HEAD 載入所謂 pre-boundary 模組，
但目前 HEAD 已包含修正，不能拿它冒充修正前基準。Git 歷史確認
`c0ffa00f214c661c27c273a1595bd347ca14baf6` 同時引入該測試並修改兩個邊界模組；
其唯一 parent `c29b8108476da7778bfaad732632dfeb3e9dca0e` 是可追溯的修正前
**原始碼候選**。已讀實際 diff，並再次對 git show 的原始位元組計算 SHA-256：

- `backend/state_memory.py`：`4a4fe0de0f21bba1bf9c4050eb7f8ecd9f8a20d98c1407663fb0c7cf5f8497b9`。
- `backend/agent_runtime/prompting.py`：`dc93889ccf4cee63773074585145be3fa2fc2cfc508a73216600f98618a834b8`。

這只補足歷史來源定位，不證明舊模組在目前依賴下可載入，也沒有將測試偷偷改綁或改標通過。
歷史 implementation plan 記載六個角色縮短 92.53–93.19%；usage-aware routing 文件
記載 6409／Agent 11 約 19,500→11,257 tokens，但均未提供本項可核對的原 checkpoint
DB／thread／hash。因此只當歷史記載，不當本輪驗收或實際模型成功率證據。
本輪 /private/tmp 檔名清單只檢視前 55 筆，不宣稱已窮盡所有檔案；已知 2330 新 capture
也不能替代原始 fixture。兩個 benchmark 仍未驗證，測試本身、原資料及 gate 均未修改。
維持先前同版整合 220 passed 的原收據；唯讀考證及本文件更新不增加測試通過數。

### 同輪來源及效能覆核的具體結果

`/private/tmp/stock-agent-source-s1-qualification-review-20260915.md`，SHA
`f30a00048c39b787765f84dedc0f71cc066038edc45a7776c096bb8d1a2fb71d`：四份各 120 根
OHLCV 共 480 根；SMA／RSI／ATR／MACD／量能共 52 個值獨立重算相符，原資料不改。
若只使用嵌入的原 `base_data_snapshot`，2330／9月12日與 2412／9月14日是 v4 的
兩個不同非 OOS 候選；2412 籌碼仍為9月11日，不能寫成9月14日籌碼。
合併新 addendum 是另一種輸入資格：取得時間晚於原 cutoff、exact-version PIT 未知，
不能倒填；Delta 的390個缺字仍未解。v4 不需要逐字稿，不能因 addendum 壞字就否定
其原始技術資料；也不能因 v4 可行就認定四模式 S3 金融業與30組／模式已具備。

真 `initialize_graph_state`／`validate_graph_state` 及兩個 route 的私有讀回為
4 passed／1.97 秒，`stock-agent-source-s1-graph-qualification-20260915.xml`。
四份都走 prepare_analysis，但原 cross_validation 財務衝突不是 circuit loader 讀取的
financial_metric_validation.comparisons 形態；因此 closed 不是衝突已經核驗通過。
這只描述該 graph 接點，不推論所有其他報告 gate 都沒有處理。source_review 仍須
明示財務口徑／採用範圍，不能以技術重算或空的 circuit 比較結果自動簽核。
後續限定資料流覆核確認：`canonical_fact_registry.py` 對缺期間的財務數字保留
`unknown_period`，`generation_report_gate.py` 仍重验原 payload／registry，並非只看
circuit closed；`confidence_calibration.py` 也保留 cross_validation 的未解衝突上限。
覆核實際以既有 env-i／私有 DB／禁網 runner 安裝邊界後做 inline assertions（exit 0，
**不是 pytest 四項或完整發布重播**）：四份原 `base_data_snapshot` 經真
format_data_for_prompt → registry_from_prompt(agent_num=24)，financial.debt 皆為
unavailable／unknown_period；合法 `[[fact:financial.debt|億]]` 均收到
unresolved_or_incompatible_fact。第一次以非允許的「億元」所做檢查不作此結論的證據。
另一次同入口逐份 before/after assertion 資料未變、conflict retained、confidence cap=6；
來源檔 hashes 與前表相同，主代理重新核對相關六個模組與四份來源 hash 及实际 grammar。
這證明本批無期間 debt 引用的防線，不證明所有財務主張／定性因果或完整報告已合格。
但這不是同口徑財報已核驗：TWSE adapter 的 TOTAL_DEBT_ALIASES 優先 TotalLiabilities，
Yahoo provenance 則是 info.totalDebt，不能直接把兩種語義 alias 到同一 comparison。
本輪沒有因此改 gate、替來源簽核或宣稱已完成全文／正式發布驗證。
缺 exact source binding、完整來源裁定、152份 roster、S3金融業文字與實際帳戶計費證據
仍阻擋 live。未創造 qualified receipt、未改原輸入或旗標。

另完成低優先效能診斷 `/private/tmp/stock-agent-price-parser-latency-review-20260915.md`，
SHA `6a9e7c4e8f360fed9a52819d4d6db96d267aeeadf4b314968f5786518d77b60a`。
原測試每 node 有4,320／6,480次呼叫，4–6秒不等於單段短文卡數秒；已重現 execution
中的 cut 誤觸 revision regex，約6–7ms／筆走慢路徑，但價格仍正確。CPU與wall已分開
核對。未修改高風險價格 grammar，不宣稱正式 latency／provider 成功率已改善。

**測試隔離失誤及已完成處置：** 初次 entry 測試在新 guard 尚未存在前，誤執行 DEV 舊
啟動腳本；02:33:05 建立 DEV `.venv`，在 key 輸入 EOF 結束，未到 requirements 安裝／
Worker／API 啟動。依 birth time 與 pyvenv.cfg 核對是該次新建產物後，已可恢復地移至
`/private/tmp/stock-agent-entry-test-venv-20260915.YokZh7/created-venv`；DEV `.venv` 再次不存在。
沒有刪除原資料。原失敗測試保留；新測試先斷言 guarded preamble，再複製入口至私有
fixture 才執行，所有後續 Python 驗證仍使用正式既有 3.13 interpreter。
拆檔期間曾有 `maintenance_state` 載入失敗，沒有測試執行；已在隔離 runner 與 -I 入口
明確先載入 state 再載入 guard，112 項整合驗證通過。沒有將這些中間錯誤改寫為成功。

### S0 第一項執行結果：來源資格盤點（2026-09-14）

已核准授權未遺失、未消耗新模型額度。完成來源池的必要條件排除與讀檔保護，**不是全部 S0
已完成**，也不是模型成功率測試。本輪沒有新 provider 呼叫、市場抓取、key／`.env` 讀取、
commit／push／PR／部署／重啟；正式 checkout 仍保留原版本與無改動狀態。

| 已盤點來源 | 實際數量 | 非空原始逐字稿 | 解讀 |
| --- | ---: | ---: | --- |
| `backend/output` 的報告快照 | 436 | 0 | 兩次完整讀回 hash 與檔案清單不變，0 讀取／JSON 失敗 |
| canonical `analysis_jobs.data_snapshot` | 1,174 有效 JSON／1,216 jobs | 0 | 唯讀聚合；其餘 42 不充當來源，與報告快照可重疊，不相加 |

- 原始報告來源分模式為 v1 21、v2 22、v3 24、v4 369。前三模式全部缺逐字稿，不能作本方案
  S3 的完整研究樣本；v4 去重後 260 個 ticker／資料截點配對僅為待核對候選，不是已合格，
  也不代表全部品質失敗。任何非空逐字稿也仍須核對來源／日期，不自動升格。
- 核對的是 production `_earnings_call_transcript` 真正讀取的 `transcript_excerpt`／`transcript`／
  `content` 三欄。`state_memory` 由原 data 建 normalized financials，不能借前序生成文字補稿；
  v1–v3 固定包含 Agent 20，缺稿會保留 unavailable，發布只能為 `research_with_limitations`
  或更差，不能計成 `verified_research`／`verified_no_action`。跨模式借同一批 data 也補不出稿。
- 既有免費法說 adapter `data_fetch/earnings_call_fetcher.py` 明確將 `transcript_excerpt` 設空、
  `transcript_available=false`，提供的是法說資訊／素材連結。這是本地程式的行為證據，不是
  宣稱所有外部公司網站都沒有逐字稿；本輪沒有對外尋找或啟用其他資料取得路徑。
- 新增 `tests/quality_campaign_sources.py`／`tests/test_quality_campaign_sources.py` 作必要排除、
  精確模式／ticker／資料截點及同配對去重；輸出永不自行宣稱 live 合格。檔案在盤點中消失／
  無法讀取會保留 unreadable；讀取由 directory fd 逐層 `O_NOFOLLOW`、regular-file／有界 read
  保護，不因檢查後換成 symlink 讀到目錄外，也不被 FIFO 阻塞。
- TDD 首輪 16 failed，修正後相關 96 passed；獨立覆核另找出檔案消失與 symlink 換檔兩個反例，
  已修正並留下永久測試，最終整合 **112 passed／2.35 秒**，獨立 **67 passed**，不相加。
  獨立覆核已核對 source 判斷與兩份聚合證據，無未解 material finding。
- 最終來源盤點 **1 passed／1.16 秒**；manifest
  `/private/tmp/stock-agent-campaign-source-inventory-v2-20260914.json`，JUnit
  `/private/tmp/stock-agent-campaign-source-inventory-v3-20260914.xml`。原版 manifest 保留，
  新舊 rows／by_mode 相同。首次 scratch collection 缺 backend import path 未執行盤點；修正
  測試入口後成功，未放寬測試或改原始來源。
- DB 聚合證據 `/private/tmp/stock-agent-campaign-db-source-summary-20260914.json` 保存查詢與
  觀測時間；以 SQLite `mode=ro`＋`query_only=ON` 執行，不是 production integration test，
  不是 DB 凍結複本，也未更新任何 job。一般測試仍走 env-i／私有 DB／禁網 runner。
- 整合 XML `/private/tmp/stock-agent-campaign-sources-integrated-20260914.xml`。reviewed helper SHA
  `0ee937e52b7aa2786de8ff5043ff7f21044570fe7e3512d4182b393740ae6780`，test SHA
  `ed8ffdfbf31abbfada35bf6fb9f68b14e772551635df3e9b4f2d6661fd8cb684`。產品 backend 未改，仍為
  `cf0ab0d1`；本輪新增的是測試支援／來源盤點，不宣稱產品報告品質已改善。

**對計劃的影響：** S3 與正式發布的資料前提不成立；原方案已規定不得補抓資料或更改完整研究
定義，故不能靠重送、放鬆 gate 或增加模型額度解除。S1 的 v4 資格、整體 campaign 預算守衛、
錯誤分類整合、計費身分／單價與維護隔離能力仍未完成，不宣稱 S0 全部完成或已有 live runner
可執行。在不可達成的來源條件下先解決這項整體方案決策，不再堆疊零碎提示修改或提前發布。

已獲使用者核准的**單一範圍修訂**：允許在原 S0 8 小時上限內，最多使用 2 小時、200 次
唯讀 HTTP，從公開公司 IR／官方財報與法說文字資料查找最多 30 份必要來源（逐字稿及其
公告日期／期間）。不登入、不使用新金鑰、不購買服務、不做音訊轉寫／額外模型呼叫；保留
來源 URL、取得時間、原始 bytes hash 及適用截點。只建立新命名的獨立研究輸入，不改原 12 組
凍結對照、既有報告或 28 OOS；沿用原模型預算、品質標準及停止條件。找不到即集中交付
不足清單，不能以新聞／簡報摘要冒充逐字稿。使用者於本次交付後明確回覆「核准」，此資料
取得修訂**已核准，2026-09-14 21:28 Taipei 接續執行**。範圍與原模型預算不變；所有 GET
先寫入私有累計 ledger，失敗／取消不退回名額、重新導向另扣一次，不自動登入或載入金鑰。
查詢導覽頁只作 discovery evidence，不冒充納入的研究來源；最終來源 corpus 至多 30 份。
目前獨立查詢守衛 13 passed（禁網測試），不是全 campaign 的模型預算守衛已完成。

### S0 來源修訂執行結果（2026-09-14 22:06 Taipei 讀回）

本節承接上方已核准的來源修訂；前節「沒有市場抓取」是修訂前的歷史盤點，不是本節的執行
狀態。本次只讀取公開官方資料與導覽頁，**沒有模型呼叫、key／`.env` 讀取或正式資料寫入**。
第一筆 HTTP 預留為 21:33:09.630620 Taipei，兩小時來源請求截止為 23:33:09.630620；不是
重開程序就重設期限，也不是必須把額度用完。
**續作已確認該窗口到期，停止新增來源下載**；97 GET／13 文件的 ledger 與 corpus hashes
讀回不變，不能把剩餘 103 次 HTTP 當作無期限授權。後續本機驗證不延長此窗口。

| 來源修訂成果 | 數量與處理 |
| --- | --- |
| 已預留 HTTP GET | 97／200，包含失敗與重新導向；目前全部有終態記錄 |
| 已取得來源文件 | 13／30，分屬 12 公司；13 份均有 HTTP 200、原始 bytes 與 SHA-256 |
| 逐字稿／講稿候選 | 台積電、中華電、台達電、鴻海，共 4 份、79 頁 |
| 其他文件 | 7 份金融業簡報、1 份財報新聞稿、1 份官方問答摘要；不當作逐字稿 |
| 待核對獨立輸入 | 4 份 addendum；保留原 data snapshot，另附來源文字，尚非可執行 job |
| 已資格核准的 live 樣本 | **0**；來源全文、敏感資料、數字／模式與資料時點尚未完成資格核對 |

- 台達電 PDF 的 pypdf 文字含 **390 個 U+FFFD**；pdfplumber、Poppler、PDFium 亦出現，
  但第一頁渲染可讀。未猜字、未 OCR、未以模型修補；該候選隔離。其餘三份沒有這類破字，
  不等於全文語意或所有數字已通過核對。台達英文檔亦明示原中文發言為準。
- 合庫資料封面為「法人提問重點摘要」，故明列摘要，未借其官方身分冒充逐字稿。
  金融業簡報不能解除 v1–v3 Agent 20 的原始逐字稿缺口。
- 4 個有逐字稿候選 ticker 在既有快照中最多只有 **14 個不同 ticker／資料截點配對**；
  排除台達破字後最多 **11 個**。這只是尚未做完整資格核對、尚未扣 S1／S2 排除的上界，
  不是 14／11 個合格樣本；仍缺金融業逐字稿，未滿 S3 每模式 30 組、10 ticker 的前提。
- 所有文件均保留官方 IR 連結頁、下載 URL、取得時間、raw／text hash、會議或公告日期。
  **會議日期、PDF metadata、HTTP Last-Modified 不證明相同 bytes 在舊 cutoff 已公開**；
  首次公開時點保留未知，不倒填日期。4 份新命名候選尚未分配 S1／S2／S3，不能避開排除規則。
- 原始 12 組凍結對照、4 份候選的父快照、既有報告及 28 OOS 均未改；候選保留
  `qualified_for_live=false`，沒有注入 graph、重算原 input hash 或產生 synthetic 報告。
- 取得的 13 份不是全網完整普查。403／timeout／TLS 失敗如實保留，未登入、降低 TLS 驗證、
  越過網站存取限制或購買來源。三次搜尋 RSS 只作導覽，未納入研究來源；下載器拒絕把搜尋
  站列為 `kind=source`。Python 3.13 部分站點因 strict TLS 失敗，後續使用現有 bundled
  Python 3.12 的預設有效憑證／hostname 驗證，沒有關閉驗證。
- 私有成果清冊：`/private/tmp/stock-agent-public-sources-20260914/source-corpus.json`；
  原始取得 ledger：同目錄 `http-ledger.jsonl`，讀回 SHA-256
  `577c6f0365be194af88828342cd3e59f31f6a840b17034f63a4ceaa50aea442b`。
  4 份候選為同目錄 `candidate-input-{2330,2412,2308,2317}-TW.json`。皆為本機暫存證據，
  不是正式 artifacts，也沒有提交 repo 或上傳 GitHub。

本批新增的必要排除守衛：公司識別明確為 ETF 時，不採同份 data 的「半導體」欄位冒充公司
產業樣本；一般產業欄位亦維持待驗證。v1–v3 的三個原始逐字稿欄位含 U+FFFD 即阻擋，
v4 的選用逐字稿不被套用成新的必備條件。這些是來源資格保護，**不是放寬產品 gate**。

| 驗證 | 實際結果與證據 |
| --- | --- |
| 來源資格新行為 TDD | 3 failed／21 passed，補實作後整合通過；不是改測試來放行 |
| 取得守衛獨立反例 | clock rollback 與 fsync 後跨 deadline：2 failed／20 passed，已修正 |
| root 來源／取得整合 | **97 passed／2.24 秒**，`/private/tmp/stock-agent-public-source-qualification-integration-20260914.xml` |
| 來源資格獨立覆核 | **69 passed／1.39 秒**，`/private/tmp/stock-agent-source-qualification-independent-20260914.xml`，無未解 material finding |
| 取得守衛獨立覆核 | **22 passed／0.183 秒**，`/private/tmp/stock-agent-public-sources-independent-closed-20260914.xml`，無未解 material finding |
| 來源 corpus 獨立讀回 | **20 passed／3.79 秒**，`/private/tmp/stock-agent-public-corpus-independent-final-20260914.xml`，無未解 material finding |

各組測試重疊，不相加。沒有重跑全庫或真實 provider 測試；禁網測試不證明外站可用性，也
不是跨程序模型 runner 已完成。此批 backend 未改，Gemma batching 未調整。来源 corpus
獨立覆核已逐一核對 13 PDF 的 raw／extraction hashes、IR→PDF 實際連結及 4 父快照前後 hash；
有限敏感欄位／常見憑證特徵掃描無命中，但不是完整 DLP／全文語意或歷史可得性認證。收據
為 `/private/tmp/stock-agent-public-corpus-independent-review-20260914.md`，清冊 SHA-256
`7c7c51f10c00115415d646e468bc218324ec0540ed0a7bc99586a0d48dbc1eeb`。跨程序模型預算帳本的
離線核心已在同一 S0 批次中實作並進入獨立覆核，尚未接上實際
transport／HTTP、計費核對或 cleanup watchdog。S0、S1–S4 與發布均未完成。

### S0 跨程序模型預算帳本（離線核心，尚非 live runner）

新增 `tests/quality_campaign_budget.py` 及行為測試。只使用呼叫者明確指定的私有 SQLite，
不是正式 quota／DB schema 變更，也沒有建立本次 live campaign 或啟動 7 日模型期限。

- 以 `BEGIN IMMEDIATE` 原子預留；append-only events 保存 campaign、階段、job、attempt、
  code／source／route bindings 與消耗。重開、取消、crash 不退回已預留的 job／呼叫額度；
  crash 的 active slot 須明確記錄 abandoned，不能直接視為完成。
- 已核准各階段及總 jobs／transport／HTTP／tokens／US$50 預估停送線同時成立，最多兩個
  active jobs；階段須有明確驗收收據且完成 cleanup 才能推進。數字是預留／停送機制，不
  證明請求已送達、品質合格或實際帳單受硬限制。
- 已知 baseline／candidate 的 immutable allowlist 可綁各 job／attempt 的實際 hash；
  不同版本不混成同一份程式證據。初版尚無 candidate2 受控追加，現由下節續作補上；
  **不可換新帳本繞過總消耗**。初始版本角色與 S1 准入仍須完整 runner 約束，不能宣稱
  完整 S1–S4 都已可執行。
- partial／missing 用量保留 `max(預留, 已觀測)`；只有本次明確提供、且呼叫者已驗真的
  final 數量才能結算該維度。tokens 與費用分維，不能用費用 final 讓部分 tokens 退款，
  反向亦同；cached input 不額外相加。實際超過保守預留時保留真值並持久停止後續送件。
- 首個明確 live batch 才起算七日；初始化不開始倒數。批次到 cleanup 的牆鐘時間累計，
  job deadline、階段 deadline、總日曆 deadline 與時鐘倒退皆有檢查。這是合作式 API 守衛，
  尚未接程序 watchdog，不能聲稱它可自行中止卡住的 SDK／清理程序。

TDD 已保留 reservation 初始紅測試、partial 退款與跨維 finality 的真實反例；窄範圍
**37 passed／1.59 秒**，`/private/tmp/stock-agent-campaign-budget-handoff-green-20260914.xml`。
含真正 8-process job slot 競爭、8-process token 競爭及 `os._exit` crash 留帳，不只 mock。
root 把兩個新 helper、來源／取得守衛、原 generation availability 與 13 PDF／4 候選讀回
放在同一禁網 runner，**177 passed／6.55 秒**，
`/private/tmp/stock-agent-s0-sources-budget-integrated-20260914.xml`；與前述各組重疊，不相加。

尚未完成的接線必須保留：每次真 transport／HTTP 的先預留與回應結算、真實計費及 token
上界核對、每次送出前的實際磁碟 hash 核驗、cleanup／finality 證據核驗、固定 ledger path
保護與 outer watchdog。孤立 core 不攔截沒有接入它的 SDK 呼叫，亦不能抵抗操作者換掉 DB
檔案；不能直接以一份 `verified_free` 標籤或 SHA 字串代替外部事實證據。尚未做完整
2,400-call 規模的效能／長時間測試。

獨立覆核新增一個實際反例：時鐘 30 時因容量拒收，未保存該觀測時間，重開回到 20 時仍可
准入。原獨立 **1 failed／46 passed** 保留於
`/private/tmp/stock-agent-campaign-budget-independent-red-20260914.xml`。現已在同一交易
保存 guard 通過的時間水位，即使後續 `BudgetDenied` 也提交，但不扣未准入的 job／calls。
永久反例及原獨立期待均未放寬；窄範圍 **48 passed／1.41 秒**，
`/private/tmp/stock-agent-campaign-budget-clock-integrated-green-20260914.xml`。

上述修復後同版 root 最終來源／budget／原 generation availability／PDF corpus／獨立反例
整合 **188 passed／6.29 秒**，`/private/tmp/stock-agent-s0-sources-budget-final-20260914.xml`。
測試前後 helper SHA `c36b94661c7edf962ae38b8742785ff77652097c869d96a05216ea581c9c81b8`、
test SHA `623eedb925fe192f7f0b6c78e1313c85ab14c03fb108192f899d39c5716b17e6` 不變，原 source
corpus／HTTP ledger hash 亦不變。前述 37／177 是先前版本的測試結果，不取代本次最終結果；
各分母重疊，不相加。獨立修復讀回 **48 passed／1.405 秒**，原反例期待不變、hash 前後一致，
無未解 material core finding。收據 `/private/tmp/stock-agent-campaign-budget-independent-review-20260914.md`，
XML `/private/tmp/stock-agent-campaign-budget-independent-closed-20260914.xml`。這只關閉核心
計帳問題，不代表已完成 SDK／HTTP 接線、watchdog 或 live 預算控制，未因此放行發布。

### S0 續作：同帳本修訂、HTTP／SDK 接線及滿載量測

本節是前述 188-test 狀態之後的同一 S0 準備批次，不新增產品提示修正批次；backend 未改。
沒有讀取 key／`.env`、新增 model calls、改正式 DB／Redis、commit／push／PR／部署或重啟。

- `register_s1_candidate_revision` 只在 S1 尚開放、已有失敗 job、全部 batch 清理且無 active job
  或持久封鎖時，追加最多一次 candidate2。新增綁定保留父 source／route，只允許一個新 code
  SHA；不得覆蓋舊 ID、重設時間或總消耗。6-process 競爭只准一個追加；重新開啟仍核對原
  manifest。初始 manifest 的 baseline／candidate 角色限制仍屬未接好的 runner，不把此 API
  當作完整 S1 最多兩個版本的全部證明。核心及獨立修訂測試 **100 passed／1.760 秒**，
  `/private/tmp/stock-agent-budget-revision-independent-20260914.xml`。
- logical transport 與 physical HTTP 分開計數：前者預留一次 transport、零 HTTP／tokens／費用；
  每次實體 HTTP 另預留保守 tokens／預估費用及 HTTP 次數，仍須計費身分／估算依據 SHA。
  這不是把 provider 呼叫標成免費；真實計費身分、價格及含 thinking／工具的上界尚未核對。
- `quality_campaign_transport.py`／`quality_campaign_wire.py` 將核對與預留接到 HTTPX
  `_send_single_request`：在 request hook 之後、每個 auth resend／SDK retry／AFC HTTP 之前。
  Client.send 禁止自動 redirect；路由限既有 Google HTTPS endpoint、同一預留模型、完整明確
  JSON／output cap。拒绝憑證入 body、重複 JSON members、外部 cache／hosted tools、非文字
  Part 及 functionResponse.parts 巢狀多模態；不改送出的 bytes，不把原稿、thought 或 key
  重複寫入預算 journal。這不是 OS sandbox，仍須由完整 launcher 強制所有 SDK／socket 路徑接入。
- 用量從每個 HTTP 的明確 provider metadata 保存，不累加同串流的 cumulative frames。
  installed SDK 的 total 包含 prompt＋candidates＋tool-use prompt＋thoughts；cached 是 input
  子集，不再加一次。缺漏／中斷／格式不合法／cached 大於 input／未知終態不釋放預留。
  費用是已核准最高單價套全部 tokens 的保守估計，**不是 provider invoice**。超額真值先落帳
  再停止當次呼叫；不能把失敗當作零 tokens 或退回已消耗次數。
- 獨立反例發現並修正三組問題：不合法 usage 被濾掉後誤釋放、nested modality 未擋、HTTPX
  auth 重送及 request hook 改 body 繞過較早攔截。原 **8 failed／1 passed** 期待保留；改 hook
  後再捕獲 response 尚未交還 caller 即失敗的 sync／async close 缺口（**2 failed／41 passed**），
  已補 close／aclose，僅記錄 cleanup error type，保留原 abort。原 11 例機械保留為永久
  `test_quality_campaign_transport_regressions.py`，未放寬期待。
- 真實已安裝 Google SDK 的 sync／async retry、AFC、串流、gzip、取消及 HTTP cap 用
  `httpx.MockTransport` 驗證，不對外呼叫；目前含原獨立反例及 stream cadence 邊界的 root
  窄整合 **48 passed／1.94 秒**，`/private/tmp/stock-agent-campaign-wire-stream-cadence-green-20260914.xml`。
  最後限定覆核與後續全切片整合另記錄，不以此窄測試冒充完整 graph／live 驗收。

帳本原先每次 check 全量解碼歷史；TDD **1 failed／10 passed** 證明重讀 257 筆已驗證事件。
增量重播每次仍從 SQLite 核對 init／已驗證 seq anchor 並讀跨程序新增 tail；只有 commit 成功
（包含 BudgetDenied）後採納快取，rollback／commit error 不產生 phantom state，reopen 全量
重建、snapshot／events 回傳與 cache 隔離。未改 DB schema／預算／時鐘／append-only 規則。
核心加既存獨立反例 **111 passed／1.89 秒**，
`/private/tmp/stock-agent-campaign-budget-incremental-final-green-20260914.xml`；不是完整 runner。

| 離線量測情境 | 實測結果 | 不能推論的範圍 |
| --- | --- | --- |
| 10,000 events，多數為 check；同腳本前後各 7 次 | check median 10.435 → 0.576 ms；整輪 53.81 → 6.06 秒，事件組成／DB bytes／consumed 不變 | 不是完整 2,400 attempts 狀態或多程序爭用 |
| 2,400 reservations＋2,400 dummy final settlements、152 jobs | S1–S4 48／360／1,920／72；1 passed／70.301 秒，CPU 69.661 秒；全數 dummy cleanup/pass，非品質驗收 | 沒有 provider 呼叫或實際費用；不證明 missing-usage／正式服務負載 |
| 滿 2,400 attempts 後各 7 次 | check median/max 26.651/28.299 ms；snapshot 26.886/29.894 ms；reopen 31.639/32.781 ms | 完整 state 的 deepcopy 成本仍在，不能引用 0.576 ms 當滿載結果 |

滿載證據 `/private/tmp/stock-agent-budget-attempt-scale-performance-20260914.xml` 保存完整 JSON；
10,241 events，量測再新增 7 個 check 為 10,248；DB 3,514,368 bytes。dummy 9,600 tokens／
4,800 microUSD 僅是測試數字。兩輪原始 check-heavy XML 為
`/private/tmp/stock-agent-campaign-budget-performance-20260914.xml` 及
`/private/tmp/stock-agent-campaign-budget-performance-incremental-20260914.xml`，分母不相加。

因滿載成本，純 stream chunk 改為每片檢查 local wall／monotonic 時鐘與 deadline；共享帳本在
首個達 250 ms 的片段重新檢查。**每次新 physical HTTP、logical transport 與明確 usage 結算
仍立即完整核對，不因節流跳過預算。** 跨程序 stop 最晚在下一個達該間隔的 chunk 被看見，
無 chunk 的卡住請求仍仰賴 HTTP timeout／outer watchdog，不宣稱 250 ms 就能殺掉任何卡死。
100 個同瞬間純片段原先寫 100 個 check 的 TDD 反例已修正；wall rollback／deadline、monotonic
deadline、跨 instance 超額仍攔住，沒有增加已保守預留的在途額度。

**限定獨立覆核已關閉：** HTTP／wire 原 4 組 material finding 全部修正；最後 **52 passed／
2.019 秒**，包含新 HTTP 與明確 usage 在 +100 ms 仍立即讀取共享 stop、sync／async cleanup
本身失敗不蓋掉原 abort 且不記錄錯誤正文。四檔 hashes 前後不變，收據
`/private/tmp/stock-agent-campaign-wire-independent-review-20260914.md`，XML
`/private/tmp/stock-agent-campaign-wire-independent-final-20260914.xml`。與 root 的測試有重疊，不相加。

`quality_campaign_watchdog.py` 另補單一已預留 job 的 outer helper：固定 ledger 旁的 exclusive
start claim，換 output 不能重啟同一 job；明確 env／無 shell、不繼承 ambient env／stdin，也
不捕捉 stdout／stderr。fresh-session guardian 保留自己建立的 process group，TERM→有限 grace
→KILL，只 reap 自己的 guardian；確認該 group 消失才寫 private cleanup receipt。無關程序
保持存活；非零退出不變成品質成功，不自行 finish_job／退款／settle／pass_stage。

- 獨立 monotonic timer 即使主迴圈的 ledger.check 被卡住仍清理子程序；真正卡住 SDK 由此
  處理，不依賴一定收到下一個 stream chunk。外層取消、exception、cleanup 中 SIGINT、
  command leader 先退出仍留下 descendant、post-spawn timer failure 均有本機程序測試。
- root 覆核要求 owner 在任何 Popen 前準備，失敗不得留孤兒；file／directory fsync 完成後
  仍須在 Popen 前 full check＋原 active job 完整綁定 readback＋原 monotonic deadline。
  第二 instance 在 claim fsync 後造成 overrun／durable rollback／finish 的 **3 個真實紅例**
  已關閉：Popen 零呼叫、claim 保留、不退款、不產生假的 cleanup receipt。
- 最後 watchdog **26 passed**，budget＋watchdog **113 passed／7.27 秒**；
  `/private/tmp/stock-agent-watchdog-pre-spawn-budget-integrated-20260915.xml`。不是 OS sandbox，
  不允許 command daemonize／setsid 逃逸；parent SIGKILL 或 host／storage failure 後不能假定
  cleanup 成功或重開額度，仍需重新稽核。完整 launcher 的 child socket／transport 與真實
  graph／artifact 清理尚未整合，本 helper 不會自行放行 live。

**本批最終同版整合：329 passed／13.17 秒。** 使用 env-i、正式 Python 的禁網 runner／
私有 SQLite，合併來源／取得／PDF corpus 讀回、原 generation availability、budget／candidate2、
HTTP／SDK／永久及獨立反例、watchdog 真實本機子程序。JUnit：
`/private/tmp/stock-agent-s0-sources-budget-wire-watchdog-final-20260915.xml`。前一輪不含 watchdog
的 **303 passed／7.51 秒** 為中間證據，與本次重疊、不相加，也沒有重跑全庫非 live 或 provider。

本次凍結 helper SHA-256：budget `d2cb37ca2747a7598a36bdea12e6a27681f1e5c8ba03e10a361176f28b2520ea`，
transport `c56c8b393ac17ae37a891f9d459d6b581b642458027d336f7e16104e98642440`，
wire `8672200d72849dedf266a362ffbe08261e9ee4a3ec0c4d351d92e8517dfd2585`，
watchdog `8c20a135fd27415e502c0096f828944e2cd236bebdf96c0b0f63a9eb94cf702b`。
來源 helper／13-document corpus／97-GET ledger 沿用前述未變更 hashes。所有測試子程序已退出；
正式 checkout 仍 clean `75824229`，不據此宣稱即時 API／Worker 健康或已載入新 helper。

續作仍欠：完整 fresh-process launcher／實際磁碟 hash verifier／固定 ledger path 與政策真實性
核對、來源及 stage／version-role preregistration、outer cleanup 與 graph artifact 證據整合、正式
maintenance/canary 隔離及 S1–S4。來源窗口已結束且仍無合格金融業逐字稿，這項 S3 資料缺口
不能靠測試守衛、重送或放寬品質 gate 補足。上述進展未放行發布，也未宣稱報告品質或成功率改善。

### S0 續作：已預留任務的 fresh-process 執行器（2026-09-15 00:53 Taipei）

本節接續前批 329 項 helper 整合，修復的是同一預算／隔離執行鏈路；前批「尚未接線」是
歷史狀態，本節不改寫其測試證據。新增 `quality_campaign_safety.py`、`quality_campaign_graph.py`、
`quality_campaign_runner.py` 及其測試，均放 `tests/`；未改產品 backend、正式資料或模型配置。

- runner 只接手**既有 active reservation**，不初始化／重置 campaign、不自動 pass_stage／
  finish_batch、不重送舊 output。父子程序核對同一 manifest、ledger init／device／inode、
  binding、完整 start claim／deadline／actual hashes；child 啟動前與 parent 記終態前均核對。
  cleanup 未確認或帳本被換檔時不釋放 active slot；正常 cleanup 後的失敗仍消耗原 job／用量。
- child 使用明確私有 output、乾淨 env、Python `-I -B` 與固定 harness importer，沒有把整個
  tests 目錄重加為 SDK import 搜尋路徑。明確 credential 檔只在真正 child setup 讀取；本次
  所有測試用 dummy fixture，沒有讀真實 key／`.env`，沒有將研究資料傳送到模型。
- SQLite／audit 守衛額外只放行精確共用 ledger、`-journal/-wal/-shm` 與 append-only 0600
  HTTP journal；禁止跨 job、links、外部 ATTACH／URI、主帳本 truncate／replace／schema reset。
  SQLite 暫存固定 memory；socket 邊界保留 Google generation 與既有 shared Redis。
  這是應用層隔離，不是 native syscall／惡意外部競態的 OS sandbox。
- 磁碟核對包含 backend 程式、真實 `.j2` 模板、相關靜態資產、7 個 harness、原 source／routes／
  明確 env／policy／review 實體檔；同版程式跨來源仍有同一 candidate code identity。Python
  executable 與 13 個關鍵 SDK／HTTP／graph／renderer 套件逐檔讀回，不只相信套件版本或
  RECORD。RECORD 不能引導讀取安裝目錄外檔案，也不能靠 metadata 假裝有 code；固定 package
  roots 下新增未列於 RECORD 的程式也會改變身份。不是完整 transitive OS／供應鏈稽核。
- 真 graph 只由原 `data_snapshot` 初始化，不採用舊 analyses／outputs／receipts；RAG／embedding／
  外部補抓維持 unavailable，Gemma batching OFF。HTTPX／SDK retry=1、shared quota、原 graph／
  品質／final audit／renderer／publication gates 保留。公開回覆／delta／usage 保存且去敏，
  不紀錄 thoughts。父程序再讀 HTML／Markdown／snapshot 的 storage key、bytes、SHA；只有
  private pipeline completion，`formal_publication`／`qualified_for_campaign` 永遠 false。
- 獨立反例修復包括：claim／cleanup 截止時間及 returncode 不相符、child 後 ledger 換 inode、
  漏凍結 `.j2`、SDK metadata／RECORD 範圍與實際 namespace、只有 published scalar 卻沒有效
  artifact，以及原始 stop 被 Evidence／SDK close 次生錯誤覆蓋。真 client close 失敗不再被
  app shutdown helper 的 exception suppression 誤當成功；所有 SDK patches 復原。
- **已解析 usage** 即使 Evidence 寫入耗盡仍先結算真值、保留 durable overrun block。初始
  max1 反例其實先在 headers 階段停止，尚未觀測 usage，不能宣稱丟失已知用量；該紅收據保留。
  已改以第一個 `wire.jsonl` 解析到 101／reserve 100 才觸發 Evidence failure 的正確 failpoint，
  並用 scratch-only 舊 bridge controlled mutation 確認反例有效，未吞停止訊號續讀網路。

驗證與版本（各組有重疊，不能相加為獨立樣本）：

| 層次 | 最末證據 |
| --- | --- |
| safety 及既有 budget／transport／wire／watchdog | 200 passed／10.14 秒；`stock-agent-campaign-safety-five-helper-verified-20260915.xml` |
| graph 獨立反例及永久測試 | 36 passed／2.24 秒；`stock-agent-campaign-graph-independent-freeze-verified-20260915.xml` |
| runner／runtime 獨立反例及永久測試 | 58 passed／20.57 秒；`stock-agent-campaign-runner-runtime-independent-final-20260915.xml` |
| root 主整合、runtime/storage 接點與永久 runner regressions | **463 passed／31.47 秒**；`stock-agent-campaign-fresh-runner-isolated-final-20260915.xml` |
| PDF corpus 獨立程序完整讀回 | **20 passed／3.90 秒**；`stock-agent-campaign-corpus-separate-final-20260915.xml` |

以上 XML 均在 `/private/tmp/`。主整合包含真 watchdog→fresh child→精確 guards→真 Google SDK
HTTPX MockTransport→共用帳本計數／cleanup，以及四模式真 graph diagnostic 與真 renderer 拒收
缺 contract 的負例。renderer 的成功 I/O 測試明示使用合成 bundle；不代表真實研究品質通過。
原獨立 runner 15／runtime 5 例已機械保存為 `test_quality_campaign_runner_regressions.py`，
保留所有 assert；合法 published fixture 需真三檔與 hash，不再只給成功字串。

首次全部混跑為 **482 passed／1 failed**：舊 corpus scratch 在 collection 全域加入 bundled
Python 3.12 site-packages，使 parent 找到 pydantic 2.13.5、fresh Python 3.13 child 為 2.13.4，
凍結檢查正確拒收。另以只選一個 child case、仍 collect 全組的診斷重現並讀回版本／路徑差異；
兩份失敗 XML 保留，沒有放寬 runtime 規則或重寫舊 corpus。最終拆成上表兩個私有程序執行，
所有 case 仍跑，無 skip。這次僅加 dummy fixture 的安全診斷資訊，runner code 未再修改。

同版主整合的 runtime inventory 三次 **119.263／114.140／113.339 ms**，median **114.140 ms**，
每次 1,035 reads／17,390,335 bytes／13 packages；不是完整 FrozenJob.verify 或模型 job 成本。
獨立先前 median 116.827 ms 是同版另一組量測，不能冒充實際 live latency。

最末 helper SHA256：safety `721085682e957e735ca4ac877ccba3048b5490d4ce0b90ae0ccc9d4e970c0f4e`；
graph `5af6caf871692bb24826346d103f52dece1db7f040c52cf23d4614be4712bf0e`；
runner `c5b1866959fef2c7f9fda169e759d90708190bc08292174752dc5f57061e29b7`。
主整合 XML SHA `d2c98cbd9d46141926f636ae863e64db8c4600af0253db5f61151502dd48decb`；
corpus XML SHA `8db0e9beda5660f09d6ffe54a562b9b32de6fc26e7c2739ddae025152a5e8d79`。
前批 budget／transport／wire／watchdog、13 文件 corpus 與 97-GET ledger hashes 讀回不變；
本輪測試 owned child 已退出。沒有 commit／push／PR／部署／重啟，也未宣稱 API／Worker 健康。

另在已核准 S0 計費核對範圍**只讀官方文件**，未延長 IR 來源窗口、登入帳戶或發模型請求。
[官方價格表](https://ai.google.dev/gemini-api/docs/pricing) 已核對：3.6／3.8 Flash 在 2026 年底前
Standard 文字 input/output 每百萬 USD 0.75／3.75，Priority 1.35／6.75，output 含 thinking；
Gemma 4 欄位是 Free Tier 免費、Paid Tier 不提供，不能把 paid unavailable 當免費可用。
這些只是公開單價，不生成任何 `verified_paid`／`verified_free` 真實 review receipt。
[Google 計費文件](https://ai.google.dev/gemini-api/docs/billing) 說明 API key 繼承 project／billing
account 狀態，仍須核對現有匿名 key slots 的實際對應、服務 tier、計費有效期與每模型完整
token／request 上界；USD50 維持預估停止值而非帳單硬保證。

**00:53 當時仍未完成的依賴（下一節記錄後續進度）：** 唯一 campaign 根目錄／全樣本 manifest 的 bootstrap 與 resume 政策、
S1 candidate2／S2 baseline 的全域角色預登記、S1–S3 全文 rubric／配對／逐模式分母／提前停止
驗收控制器，尚未因單 job executor 完成就自動具備。來源 review 仍無合格金融業逐字稿，
4 addenda 仍不可執行；帳戶計費 review 未完成；正式維護／canary 隔離未實作。後续沿用集中
核准與原預算接續這些依賴，不提前送件、升格來源、擴充下載窗口或發布。

### S0 續作：固定整批名單與外部證據驗收（2026-09-15）

本切片沿用 executing-plans／test-driven-development，由 root 整合固定名單、帳本與報告
收據；獨立 implementer 建立純階段驗收器，再由不同 reviewer 驗證門檻及初始 bootstrap。
這是原集中計劃的續作，不是新增模型測試窗口；未建立真實 campaign anchor、未讀入真實
金鑰、未送模型、未發布或重啟服務。來源 corpus／HTTP ledger 的原始 SHA 保持不變。

新增支援檔：`tests/quality_campaign_protocol.py`、`tests/quality_campaign_acceptance.py`
與各自永久測試及 controller regressions；既有 budget 新增保留消耗量的 durable stop／
review reference 綁定，既有 runner 的終態 parent receipt 加入 prompts digest。backend 行為未改。

**固定預登記與續跑：**

- 預先列出 152 個固定 slot：S1 4、S2 24、S3 120、S4 4；job ID 不重複，不能事後刪除
  失敗、替換來源或改抽樣。S3 每模式 30 個不同 ticker／截點，至少 10 ticker、5 個已覆核
  產業、3 日期，含金融／非金融；排除 S1／S2 使用過的配對，預選每模式 5 份全文覆核。
- 逐份對 FrozenJob 的 campaign／job／stage／role／source hashes、來源 review 和證據
  bytes；S2 原始 12 組另須由 S0 review 核對，且新舊 routes／environment／billing／
  reservation／policy bytes 相同。來源 metadata／證據存在不自動證明來源資格；仍由外部
  source review 負責 PIT／產業／內容真實性，不會把現有 addenda 自動升格。
- 一個初始 candidate code、一個隔離 baseline；baseline 必須為真正 checkout root，
  HEAD=`75824229` 且 backend clean，不能使用正式 checkout 或借祖先 repo 的 revision。
- create 先驗 prerequisites，再寫入不可重用的 exclusive anchor；中斷後不自動重建帳本。
  resume 驗原 anchor／root／protocol／ledger inode、init 與固定 rubric/controller bytes。
  coordinator 使用同一 anchor inode lock；必須沿用原已授權 anchor，這不是對抗 host owner
  刻意刪除全部證據／另換 authority 的 OS 安全邊界。

**執行與驗收接線：**

- `run_next()` 先要求綁定本名單／candidate 的 S0 review，包括全庫非 live、必測 lane、
  skips 分類、獨立 review、維護隔離的既有證據。未具備時不啟動 live deadline。
  依固定順序一次執行一個 fresh job；每次為一份的 batch，符合「最多 12／每模式最多 3」
  上限，cleanup 完成即結束該 batch，再等待外部內容覆核。不是把 12 個 slot 隱式當一批。
- 真實 parent receipt／cleanup／outcome／HTML／MD／snapshot 必須讀回，不能用
  `private_pipeline_completed` 或模型自報 gate 直接當完整研究。tokens 從 physical HTTP
  ledger 的最終已觀測用量計算；缺用量保留 `None`，不把預留量或外部 reviewer 填的數字當實測。
  實際模型和 generation knobs 從原 calls／HTTP／prompts 證據取得；缺身分不算可比。
- 外部內容 review 綁 source／parent／outcome／artifacts／rubric SHA，並引用實際 byte 位置。
  `source` 文檔是原 `data_snapshot` 的無資訊損失 canonical JSON view，不含舊 `analyses`；
  其他位置讀實際報告 bytes。這只能證明引用存在及未變更，不能自動認證 reviewer 的語意判斷。
- 格式不正確或尚未完成必要覆核，拒收 review 而不寫 pointer／鎖死 campaign；完成後才將
  exact review reference SHA 綁進 append-only ledger，stage 前後都不能換 reviewer／review
  bytes。真正來源改寫一旦觀察即 durable stop，事後恢復原檔也不能當沒發生而續送。
- generation knobs 先由執行結束時的 parent receipt 綁定 prompts SHA，再由 review 綁定；
  覆核前或後改動設定都不能變成「實際同設定」的配對證據。
- 完整研究樣本的 required roles 事前核對 hashed `pipeline_modes.py` 的 literal 契約，不
  執行任意模組或讀現行 code 冒稱舊版。每角色須有本 job 的 logical／physical ledger ID、
  completed public response；再 AND 外部的內容可採用性判斷。HTTP／角色完成仍不等於品質
  通過，缺 23／24 的 v4 不可用 `required_roles_valid=true` 補造。資料不足壓力組不硬套
  完整研究的全角色條件，保留正常略過／降級。
- S1 必須最後同一候選連續兩份事前合格的完整報告；未使用的尾端 slot 不強迫耗完。
  S2 保留 12-pair／24-job 分母及 model-confounded 標記，至少 8 組可比且每模式至少 2 組，
  候選壓力組須全數正確降級／拒收；完整研究至少 ceil(90%)，同模式可比完成率不低於基準。
  p95／每份合格報告 token 惡化超過 25% 不放行；缺資料 pending，0／0 和零基準成本不補假值。
- S3 每模式至少 29／30，所有已發布重要來源／決策逐份 review，所有失敗／警示額外 review，
  固定全文 20 份須至少 18 份達 8 分且各模式平均至少 8 分。第二個模式失敗、三個連續同根因
  或來源／秘密／已發布重大錯誤觸發停止。S4 明確拒絕由此私有 controller 放行正式發布。
  S3 另有独立 rubric 一票否決：已完成外部覆核的重大失實，即使是未發布草稿，也會停止；
  不與「重大錯誤漏過發布」的全域安全停止混為同一條件。一般未發布失敗仍可保留為 29／30
  中的 1 份，沒有提高成 30／30 或把未審稿冒充已完成審查。
- ledger 內僅有 `stage_pass` 和任意 hash 不足以跳關：送下一階段前須重讀對應 acceptance
  收據並按原 artifact/review 重新判定。S2／S3 candidate 額外核對 S1 實際通過 code。

**已發現並關閉的忠實反例：** 產業名稱前後空白被當成五個產業；baseline 子目錄借父 repo
HEAD；已完成 snapshot 被改動仍可能续送。最後一項現會 durable stop，不能把 artifact 變更
當普通一次失敗後繼續。另補來源／report 位置越界、錯 hash、未知引用和假 stage hash 拒收。
曾有「固定名單每 12 slot 必須是同一 batch」的 reviewer 假設，查實單 job batch 後已撤回，
歷史 red 收據保留，最終選擇明示排除此非產品缺陷，不修改名單迎合錯誤測試。

**驗證快照（後續若有審查修正，以追加的 final readback 為準）：** 主整合
`/private/tmp/stock-agent-campaign-protocol-full-integration-20260915.xml`
為 **569 passed／33.79 秒、1 deselected**；排除的是上述撤回假設，不是未解產品失敗。
此輪包含真 SQLite／累計預算／fresh child／SDK mock／renderer 邊界及 controller 合成 executor
收據整合。合成的 reviewer／來源／報告只驗控制流程，不能充作真實來源核准、S1 通過或供應商
成功率。PDF corpus 維持使用上一輪独立 Python 程序的有效 20 項證據，不混入本次主程序。

**01:41 最終同版 readback：** 後續独立審查的格式／pending review 被鎖死、prompts 設定
漂移、stage review reference 替換、來源改寫未 durable stop 等反例均已關閉。另補 reviewed
未發布草稿的 S3 rubric veto、完整研究的真角色完成證據，以及失敗 gate／classification
尚未完成額外 review 時不能提前寫死 pointer。格式錯誤或 pending review 不消耗新 job，也不
誤造 irreversible safety stop；真正風險仍停送，現有證據與消耗額度保留。

- root 相關整合 **595 passed／37.47 秒、1 deselected**，無 failures／errors／skips：
  `/private/tmp/stock-agent-campaign-controller-review-closed-final-20260915.xml`，
  SHA256 `5f318ab6ca3e63dfd7aa8677f65c709824eac716ab4eab885c7afd351534e174`。
- 獨立 controller／acceptance 與相依接線限定覆核 **287 passed／27.77 秒**，無未解範圍內
  重大 finding：`/private/tmp/stock-agent-campaign-controller-independent-final-verified-20260915.xml`，
  SHA256 `4578d3b19a7d3ca35097cea7f8e4cccc74d09786ab352ae9bb996e164fe23313`。
  包含 review bind commit 前／後中斷不重設、重開仍停送與單次綁定不能覆寫。
- 最終核心 SHA256：protocol `35e3888979da90742edd2876ba2a4c7780c8ca10be30d895f632eb101959fb47`；
  acceptance `2200669c68d27c3b8e0e08995ac5258a8c78a92caabbb0a8bab98540265463a2`；
  budget `6937af97afbdbb6adf20dd855b7ba7a839d2fdd05ca624928e9cd116c8972cf9`；
  runner `8cbe6c54698d499c2c093c21167dc2e34ae2606b4d1dafb85494291a9b7fd76d`。
- 原始反例仍保留：`stock-agent-campaign-controller-independent-red-20260915.xml`、
  `stock-agent-campaign-controller-independent-pending-failure-red-20260915.xml`、
  `stock-agent-campaign-controller-terminal-config-red-20260915.xml`、
  `stock-agent-campaign-controller-role-evidence-red-20260915.xml`、
  `stock-agent-campaign-acceptance-rubric-veto-exact-red-20260915.xml` 均在 `/private/tmp/`。
  角色正向 fixture 後來補齊所有角色與 logical／HTTP 帳本，原「只有 22」反例以忠實縮減原始
  call evidence 保留；不是刪掉缺角色失敗來維持綠燈。
- S0 仍沿用 21:07 起點與原 8 小時／修正批次限制，不因新增文件段落歸零。IR/source 兩小時
  窗口已到期，原 corpus／HTTP ledger SHA 讀回不變。本批未啟動 live 的 7 日期限。

**01:41 當時尚未完成（下節記錄續作）：** S1 candidate2 的整批 manifest 映射／修正收據接線、異常中斷後的人工驗證
回收流程、完整統計輸出（含區間／15-30-60 分鐘／恢復事件未觀察等分類）、正式 maintenance／
frozen canary／API-UI 讀回、完整 campaign 實際預登記來源及
真實帳戶計費 review。現有 ledger 雖能追加一次 candidate2，此 controller 尚未接線，不能
宣稱已具備兩版完整執行流程。S3 合格金融業逐字稿及 30 組／模式來源仍不足，原 IR 下載窗口
已到期，不重開。未進行新的完整 repo regression、live S1–S4 或任何 release。

### S0 續作：第二候選、統計與有證據的中斷收尾（2026-09-15）

沿用既有 executing-plans／TDD／獨立覆核分工，root 接候選及 controller，獨立 implementer
完成純統計後由另一 reviewer 覆核。不是新增 live 核准或重開 S0；21:07 起點、8 小時主動
執行上限、最多兩批有證據的集中修正，以及已到期 IR/source 取得窗口均維持原狀。

**第二候選已接線：** `quality_campaign_revision.py` 與 Campaign 公開修訂 API。

- 僅 S1 尚未通過、所有既有工作已終態／批次已清理，且仍有原名單兩個合格 S1 slots 才能
  登記一次修正版。失敗既可為執行失敗，也可為「私有 pipeline 完成，但外部品質審查未過」；
  後者必須是已綁定原 review 且由共同驗收 predicate 判為真失敗，不能借成功報告重跑。
- 外部 repair review 綁失敗原因、原／新 code、原 failure review／rubric 與修復重現、全庫
  非 live、必要整合 lane、獨立審查的檔案證據。這是驗真接線，不是本輪建立真實 repair approval。
- 必須一次映射 S1–S4 **全部尚未使用的 candidate slots**，不能替換 baseline／已用工作、
  source／routes／environment／billing／reservation／source review／policies／runtime／harness。
  只容許後端 code/root 與新 binding ID；所需角色另對 frozen mode registry 核對。
- 原 protocol、job 分母、已消耗 HTTP／transport／tokens、批次牆鐘及 7 日期限均不重設。
  修訂內容 SHA 綁在原 append-only ledger，重開重建的是「登記修訂之前」的 unused 集合，
  不會把後來已跑的第二版誤退回第一版。內容相同而外層檔案位置不同不改變此內容身分保證。
- raw ledger append 不構成放行權：resume 重新核對真失敗及整批映射，run_next 仍強制 S1
  winner 貫穿 S2／S3。pointer 已寫但 ledger 未記錄時保留阻擋，不自動採用、刪除或重建。
- 24 項 faithful reds 與其後兩項 raw-ledger／時間來源 reds 已保留；修正後整合 264 passed。
  獨立 reviewer 加入原日曆逾期、raw 成功冒充失敗、只映射一個 S4 slot、兩側中斷等 17 反例。

**統計已接線：** `quality_campaign_statistics.py`、`Campaign.statistics()`。

- 每次使用原固定 152-slot roster，不以已完成工作的數量代替分母；分 stage／mode／role，
  將 completed、正式合格分類、壓力組正確處理、未審／失敗／取消／未知分開。
- 起訖時間由實際 `job_reserve`／`job_finish` 事件覆寫外部輸入，輸出 15／30／60 分鐘觀測、
  p50／p95 nearest-rank、Wilson95 及 source／results／ledger digests。cutoff 指執行完成時間，
  不是「當時已知 reviewer 結論」；尚無 terminal result 的 active job 仍列 age_unknown，
  不冒稱已完成全在途工作的即時 censoring。S2 pooled 數值不當作新舊 treatment effect。
- 未觀測／待覆核不灌成失敗以造信賴區間；pilot 全部已觀測且可評定才出固定分母 CI。
  Wilson 僅為未校正 ticker／日期相關性的描述參考，不能宣稱長期成功率下界。
- result final tokens 與 ledger 保守扣帳分別呈現、不相加；partial／未知用量保留預留，
  cached input 不重算。沒有首選意圖、因果 fallback／429／5xx 恢復時間線就回 null/unverified。
  尚未取得這些實際資料，不能因欄位存在就標記整體成功率／恢復率驗證完成。

**明示回收子集（已經獨立覆核）：** 補綁已存在的原 review，或補關唯一已有終態及完整原始
收據的 batch。重用正常 review 驗證，不接受「cleanup=true」或任意 PID、替代 review／status；
不送模型、不改原 job 狀態、不退額度、不升級階段。batch 間中斷時間仍計入原 elapsed，
不能倒填 cleanup 時間。缺 parent／cleanup、仍 active、host／guardian ownership 遺失、
空 batch 尚未 reserve 等狀態仍拒絕；未實作較廣的失敗／unknown recovery receipt，絕不補造成功。

**正式維護不是已完成：** 獨立唯讀調查與 24 項 characterization 確認舊入口有三個阻礙：
關 API 可連動 launcher 關閉未持久化 Redis；scheduler 中斷可留下 record 已保存但未 enqueue；
只監聽 canary queue 的舊 worker startup reconciliation 可把一般 queue 任務誤標 abandoned。
這些測試刻意重現原不安全行為，**不是維護驗收通過**。尚須版本中立的既有入口 adapter、
合作式 admission／claim 保護、最後 Redis 保存證據與受限 canary／rollback。若 Redis 是共用
服務，server-wide CONFIG/SAVE 不因只使用本系統 DB 就自動在授權內；未操作正式程序或 Redis。
交接 `/private/tmp/stock-agent-maintenance-handoff-20260915.md`，不以新 gate 能讀回冒稱舊 process
已遵守，也不使用 SIGSTOP／SIGKILL 或清 queue 迴避首次移交缺口。

**原全庫 25 skips 已按原 XML 逐项歸類，非改成通過：**

| 原測試檔／案例組 | 原 skips | 本次處置 |
| --- | ---: | --- |
| `test_workflow_postgres_live` collection | 1 | 若本次仍為 SQLite 部署則不適用於該發布；PG 原任務仍未驗證，不能標完成 |
| live 2449 及 free external data 的 Google News／TWSE／MOPS | 4 | 本次凍結來源驗收不適用，不打開 fresh fetch 或到期來源窗口；S1–S4 provider 品質仍另外必測 |
| `test_commercial_visual_optional` 全 8 cases | 8 | 必測、尚缺隔離瀏覽器／測試 API 實跑；不得連預設正式 8080 充數 |
| `test_frontend_visual_optional` history／home | 2 | 必測、尚缺；舊 sandbox Chromium 啟動失敗不是 UI 通過 |
| chart QA 3、chart security 2、chart visual 1 | 6 | 必測、尚缺真 Chart.js browser lane；保留 6 個原節點，不以 renderer 單元測試替代 |
| `test_worker_process_smoke` 真 RQ job | 1 | 必測、尚缺；須既有私有 Redis/獨立 queue，不可接正式 queue 或據 skip 放行 |
| `test_credibility_artifact_replay_optional` | 1 | 歷史原 artifact 只讀核對仍列待驗；不能用 synthetic report 代替原三 bundle |
| Gemma／prompt checkpoint optional | 2 | 指定歷史 checkpoint benchmark 尚未驗；先核對其舊 12k／HEAD 比較假設是否適用，不把 12 組 graph double 測試冒稱同一覆蓋 |

原 XML `/private/tmp/stock-agent-report-quality-checkpoint-full-suite-20260913.xml` 已讀回。
除明列不適用的條件式 PG／fresh-fetch 項外，沒有把尚未重驗的歷史證據標成有效通過；後續
最後候選全庫及必要 lanes 仍未完成。新 helper／controller 的測試通過不取代這些部署前置。

本節中間證據：`stock-agent-campaign-revision-statistics-full-integration-20260915.xml`
（673 passed／1 deselected，SHA `2d655d506688f67ef8973be910b96c2cfeb23b94209941bf978ce38539f02fbb`）；
`stock-agent-campaign-revision-independent-final-verified-20260915.xml`（301 passed，
SHA `eec3a84defa5c43129b326c455fbf43daeff35b658a34169144fa17a4e1a3bdd`）；
`stock-agent-campaign-statistics-independent-integrated-20260915.xml`（40 passed，
SHA `a8cee4b154bf0582ea65e0be55cd36b7ab4a2ced23e9143f8d2a598b5905dfcd`），均在 `/private/tmp/`。
前兩者早於最後明示回收接線，不冒稱同版最終驗證。

**02:20 同版最終 readback：**

- root **705 passed／53.35 秒、1 deselected**；JUnit 實際 705 tests，0 failures／errors／skips。
  `/private/tmp/stock-agent-campaign-revision-recovery-statistics-final-verified-20260915.xml`，
  SHA256 `f0157c5df1812f4816e57f980b118553db9b11550499c865a309b7e8921b1262`。
  包含原來源／預算／真 fresh-process／SDK double／renderer、controller／rubric、候選／統計／
  回收及四項 mandatory runtime/storage lanes；不等於 12,000+ 全 repo 或真 provider 回歸。
- 回收獨立 8 反例＋22 永久測試 **30 passed／5.10 秒**，
  `/private/tmp/stock-agent-campaign-recovery-independent-verified-20260915.xml`，
  SHA `0a52ea01cb14a2fe0f66f4aa79a8391e4272ac7de90282e5c3c351d442338ef9`。
  到期／時鐘回退只可收尾但仍 durable blocked；原 stop、job status、attempts、spent 與 deadline
  保留；另一份 unbound pointer 不被略過；缺 parent 不補造；重複 bind 不增加 event。
- 最終 helper SHA：protocol `2eed739d0513242fa36933bfd6af9850960e1820c4e2bd3a510ee8748dd99166`；
  revision `bbea18efa63aabef51d5e2082a187ce962b7d270fc180b1ebb4d6c23b496863b`；
  statistics `f5c6864969838d673ea0d68658787e6aa0cd6c6aca0eb9bf65e5d9e45913902a`；
  budget `b867d97dd7cdc3d633a05f661b2e82ccffb9ef5dcb61f10e7c2d323ba0bd36f2`。
- 最後主整合首次誤寫獨立 recovery scratch 檔名，exit 4、0 tests；原
  `stock-agent-campaign-revision-recovery-statistics-final-20260915.xml` 保留。查實檔名後以上述
  `final-verified` 新收據執行，未降低 assertion、覆寫失敗記錄或更改程式迎合結果。
- `git diff --check` 通過，本輪 owned watchdog 子程序已退出。正式 checkout 仍 clean
  `758242290e795146520f58f68ffa113cac35e52c`；未聲稱 loaded API／Worker SHA 或健康已重驗。
  原 source-corpus／97-GET ledger hashes 讀回不變，4 addenda 仍未資格核准；新模型呼叫=0。
- **接續項目：** 先實作已有明確反例的版本中立 maintenance／合作式 gate 與 frozen canary，
  再補必要隔離 UI/RQ 及最後候選全庫回歸。source qualification／金融業逐字稿與真實 billing
  review 仍是實測硬前置；資料 HTTP 窗口不延長，不靠 helper 測試啟動不合格的 152-slot campaign。
  缺父收據／active guardian 等較廣 crash recovery 保持 fail-closed，不在此子集冒稱已解。

### S0 錯誤分類與尚未具備的執行能力

本次另讀回 9 月 14 日 `events.jsonl`／`outcome.json` 與已保存的原稿重播收據，將来源修訂
和實測拒收分開處理。這是既有證據整合，不是新報告或新 provider 測試：

| 分類 | 具體證據 | 處理邊界 |
| --- | --- | --- |
| 來源確實不足／尚未核對 | 原 12 組中的 9 個 v1–v3 沒有原始逐字稿；新 corpus 未補足金融業或 30 組合格配對 | 原 12 組仍作缺資料壓力組；不能強求完整研究、不能用提示補造資料 |
| 模型未遵循既有契約 | 9 月 14 日三份完整稿 schema 可解析，仍有 23／36／29 項診斷出現；含未綁定日期／數字與來源關聯 | 不把 issue 數當獨立錯誤事實數，不改稿或 gate 讓舊失敗變成功 |
| 提示／schema 指引落差 | 原實測 wire 的六欄只有型別；`cf0ab0d1` 已加欄位描述且保留其他配置 | 屬已測離線修正；效果假說尚無同版 live 證據，不繼續猜測性小修 |
| validator 誤拒／有限漏檢 | 前批來源期間／指標 grammar 的忠實正反例與修正已保存；語意覆蓋明列 `not_checked` | 沿用未變更回歸，仍需全文人工覆核；有限 matcher 沒抓到不等於內容正確 |
| 流程／呈現及分母 | events 124／138／239 明示內容退件；241 為取消。outcome=`error`、publication=null；checkpoint next 不是執行中 | 不混成 HTTP 429／5xx／市場成熟等待，不把 HTTP 200 或部分串流算研究成功 |

原稿重播為 `/private/tmp/stock-agent-prose-live-readback-20260914.json`，欄位指引後讀回為
`/private/tmp/stock-agent-schema-guidance-readback-20260914.json`。後者確認原 capture／退件
不變、新 provider calls=0／qualified reports=0；本節没有重跑或篡改這些歷史收據。

計費方面，`backend/model_route_budget.py` 的觀測輸出明列 `estimated_cost_available=false`
及 `estimated_cost_usd=None`。這不是現有 key 免費的證據，也不能拿本機 token 估算代替
實際計費身分／價格與保守上界核對；新帳本即使可接受有證據的費用預留，仍不等於已完成
真實帳戶核對。本次沒有讀 key／`.env` 或呼叫供應商以探查計費。

正式 canary 隔離接點另由獨立唯讀調查及 root 讀回確認：

- `worker_queue_runners.py` 的 `SimpleWorker` 直接監聽一般 queues，且 `with_scheduler=True`；
  `max_jobs=4` 只限制數量，不能指定只跑 4 筆預登記樣本。
- `analysis_jobs.py` 正式入口仍會 `fetch_async`、載入 temporal memory；另有 graph 的補抓來源
  路徑。獨立 frozen graph probe 不能冒充同一正式 worker 路徑的凍結注入能力。
- `watchlist_claim_store.py` 會在 enqueue 前先寫入當日 `last_run_dates`，因此只在 enqueue
  拒收可能消耗原排程機會；需要在 claim 前保護並驗證 gate 切換競態。
- `start_mac.command` 啟動 `--role all`；`worker_maintenance.py` 會做歷史報告／cache／index
  cleanup。新 code 中的 gate 也無法反向保護還在執行的舊 API／Worker；須先證明切換及回復
  流程隔離，不能以「已核准重啟」跳過在途 job／原 queue 保留條件。
- `free_notification_suppression.py` 有 suppression 接點，但尚未證明 canary provenance
  經 snapshot／report row／dashboard action 到通知 outbox 的完整抑制链路。

既有 queue／watchlist claim／notification 接點隔離檢查 **8 passed／2.08 秒**，
`/private/tmp/stock-agent-s0-maintenance-seams-readonly-20260914.xml`。這只驗既有行為，未實作
新 gate、未做跨程序競態／真正 RQ canary／重啟或 rollback 測試；不能據此解除發布條件。

### 目標與現況

- 終點：四模式的新報告能完成、來源與數字可核對、結論自洽；有固定版本的實測結果，達標後
  完成 commit／push／PR／合併／部署／API 與 Worker 重啟及 canary。不是只把單元測試跑綠。
- 本次唯讀核對：DEV 為乾淨的 `codex/report-quality-hardening-20260912`，HEAD
  `cf0ab0d12db2f447ef6f376ae7f0e478d9bff9de`；正式 checkout 為乾淨 `main`，HEAD
  `758242290e795146520f58f68ffa113cac35e52c`。本次沒有重驗正式服務健康，checkout 不等於載入版本。
- 最近 live 測的是前一版 `ccdc3ce6`：4 次 HTTP 嘗試、3 份完整 JSON、1 份取消串流，
  **0／1 合格完整報告**；Agent 22／23 的日期、數字引用及研究敘述不符合契約，未到 Agent 24。
  最新 schema 欄位指引僅有離線證據，不能宣稱已改善成功率。
- 最近完整離線回歸的歷史結果是 12,030 passed／2 failed／25 skipped；兩項失敗有後續窄範圍
  補驗，但不是同版全庫全綠。最新 schema 相關整合 1,121 passed／75 subtests；不同版本與重疊
  分母不相加。後文保存原始 XML 與限制。
- 本次額外核對原 12 組矩陣：9 個 v1／v2／v3 工作的 Agent 20 都預期因缺逐字稿而略過；
  `generation_report_gate.py` 將此列為 `research_with_limitations`，不是完整研究。
  原始對照集不能兼作全模式完整研究的正向驗收集，S3 來源資格不足是必須先查清的真實風險。
- 本次使用 outcome-first 整理終點、writing-plans 整合切片与停止條件；方案交付不表示開始實作。

### 剩餘問題總表

| 原項目 | 已有工程／離線證據 | 必須收尾的證據或問題 |
| --- | --- | --- |
| P0-1 完整性、工具 JSON、快取及有界修復 | 應用契約、validated cache、失敗不發布已實作 | 集中核對 22／23 首稿與整稿重寫是否收到一致、可遵循的規則；走完 2／13／18 工具回合、22／23→24、final audit→真實完整 artifact；不能以 HTTP 200 或 synthetic patch 當完成 |
| P0-2 數字、單位、期間與來源 | fact registry、格式化、股／張、幣別／期間與來源保真已有回歸 | 補齊現有裸日期、期間鄰接、同筆引用及研究敘述反例的整合驗收；財報發布時點／口徑不明保留限制，不倒填凍結資料 |
| P0-3 估值及最終決策 | decision contract、價格方向、來源不足的安全邊界已實作 | 真報告核對 4→7、14→16、18／21→19、22／23→24；當期 DCF 不冒充未來目標；缺乏方法橋接不得產生交易價 |
| P0-4 等待語意、實體及 fallback | intent、公司語境、N/A 分數、state round-trip 已有測試 | 同一發布路徑驗證安全觀望與真正條件式下單；graph／checkpoint／snapshot／HTML 不丟失降級原因 |
| P1-1 角色／模型預算 | 共用估算、完整來源保留、schema 成本可見 | 同版實測各角色截斷、thinking／tool／cache 用量、首選送達與備援；不靠提高 Gemma cap、刪資料或放寬 gate 達標 |
| P1-2 可用性與重試 | 有界 retry、quota、checkpoint；私有真 Redis 原子冷卻已驗證 | 本次整體預算必須跨程序／重啟累計；相關未跑的隔離 worker／儲存整合與發布前排程保護仍須逐項核對，不能重跑全部已有效證據充數 |
| P1-3 成功率與觀測 | job／node／attempt 分母及實際模型分類已實作 | 真報告的 events、snapshot、API、UI 四方讀回一致；缺失用量、取消、未送達、cache、診斷不可混算 |
| P1-4 領域與可讀性 | 金融業／製造業分流、缺逐字稿、renderer 已有修正 | 全文核對股數不寫成金額、無比較不稱穩定、無來源不作因果推論；四模式版面無截斷 JSON、教學佔位或結論矛盾 |
| P2 比較、樣本及正式交付 | 12 組凍結來源與離線接點可重用 | 同條件新舊對照、每模式 30 個不同 ticker／資料截點樣本、獨立內容覆核、整合發布及 4 模式 canary，均未完成 |

不再假設所有問題都來自提示。S0 必須把每類拒收分成「來源確實不足」「模型未遵循」
「提示／schema 衝突」「validator 誤拒或漏檢」「流程／呈現缺陷」，由原稿與來源建立反例。
只修有證據的錯誤；可證明無須修改的項目直接沿用。不新增一長串猜測性的提示小修。

### 一次核准的總測試預算

以下是**已核准上限，不是必須用完的量，也不保證在上限內必定達標**。階段串行，前段過關才解鎖下一段。

| 階段 | 報告工作上限 | 模型 physical HTTP／transport 嘗試上限 | token 停送預算 | 累計批次運行時間上限 |
| --- | ---: | ---: | ---: | ---: |
| S1 聚焦 v4 端到端驗證 | 4 | 48 | 4,000,000 | 40 分鐘 |
| S2 12 組凍結輸入 × 新舊各一次 | 24 | 360 | 25,000,000 | 240 分鐘 |
| S3 固定候選：四模式各 30 個樣本 | 120 | 1,920 | 126,000,000 | 1,200 分鐘 |
| S4 正式 runtime canary：各模式一次 | 4 | 72 | 5,000,000 | 40 分鐘 |
| **總計** | **152** | **2,400** | **160,000,000** | **1,520 分鐘（25 小時 20 分）** |

- 估算依據：`pipeline_modes.py` 的 v1／v2／v3／v4 分別有 10／8／5／3 個主要角色；
  S2 共 156 個主要節點、S3 共 780 個，不含額外工具續接、修復、fallback 及 audit。
  12 組離線矩陣的 287 條可送路由估算 input 約 40,041–88,825，平均約 56,317；它不是
  287 次 API 呼叫。最近 v4 的實際單次 input 約五萬量級，故不能以報告份數代替 API 預算。
- HTTP／transport 為硬上限：SDK 重試、換 key、fallback、工具續接、品質修復、失敗與已送出後取消
  均扣帳；preflight 未送出不算模型 HTTP 成功。各階段上限及總上限同時成立，不能跨階段借額度。
- token 是「已觀測用量＋在途保守預留」的**停送線**，非 provider 帳單硬上限。送出前計入完整
  system／schema／tools／prompt 及 output／thinking 預留；估算不足或回傳超額，立即停後續送件並
  公開實際超額，不改寫數據。回應用量缺失時不釋放預留；cached input 不重複相加。
- 任何未取得可支持保守預留的 input／output／thinking 上界路由，先判為不可送，不用平均值
  當保證。執行前須離線驗證跨程序原子預留、取消／崩潰扣帳及總 deadline；目前 harness 尚無本表
  的整體執行證據，S0 必須補齊，不能只寫一份預算 JSON 就直接開始。
- 同時最多 2 個報告工作；單 job 最長 60 分鐘且受剩餘階段時間限制。批次從 launcher 啟動到
  所有子程序清理的牆鐘時間累計，重開批次不歸零；provider 冷卻等待也受階段時間及總日曆期限限制。
- S0 離線整理、修正及整合驗證最多 8 小時主動執行時間，最多 2 個有證據的修正批次；整體 live
  授權在第一次 live 啟動後 7 個日曆日到期。這是資源／有效期上限，不是交付日期保證。
- 費用：不購買額度、不新增金鑰、不開啟付費方案。既有帳戶若已計費，建議另設 **US$50 預估費用
  停送線**，与 token／呼叫限制取先到者；執行前須核對既有路由的實際計費身分、單價與可用的
  保守估價依據。不能核對時不送該付費／計費未知路由，不能從 `free` 檔名推定免費。應用程式
  估價不取代供應商硬性帳單上限，也不保證 US$50 足以完成全部樣本。

### 執行順序、檔案與驗收

#### S0 集中修正、凍結版本與預登記（不呼叫模型）

- 檢查 `backend/agent_runtime/{quality_completion,repair_reflection,generation_config}.py`、
  `backend/generation_schema_guidance.py`、`backend/canonical_fact_prompt.py`、
  `backend/{research_assertion_contract,technical_research_assertions,source_bound_periods}.py`；
  連同 `generation_report_gate.py`、`decision_contract.py` 及 `report_quality_outcomes.py` 的發布接點。
- 以 9 月 14 日完整原稿與原 12 組失敗片段一次建立錯誤分類及行為矩陣；保留完整原始檔，
  不替模型補寫研究、不扩大 metadata／prose patch 權限以迎合測試。先證明真實反例會失敗，
  再集中修正；相關成功路徑及錯來源／錯期間／缺資料負例都必須保持有效。
- 重用 `tests/quality_pilot_{budget,graph,numeric}_probe.py` 及既有隔離 runner。
  把目前 `/private/tmp/stock_agent_graph_replay.py`、`_safety.py`、`_wire.py` 的已驗證邊界
  整合成單一 campaign runner／累計 ledger；可移入測試支援目錄，不再每次重建單次授權 launcher。
  ledger 綁 campaign、stage、attempt、code／source／route hashes、實際用量與截止時間；只追加，
  舊一次性 consumed receipts 不修改。崩潰／重啟不恢復已消耗額度。
- 12 組固定 regression set 不補新資料。另從既有股票研究 snapshots 選出 S3 的每模式 30 個不同
  ticker／資料截點配對：至少 10 個 ticker、5 個來源可核對的產業類別、3 個實際資料截點；
  同一 ticker 同截點的多次報告不得充數。金融與非金融均須涵蓋，S1／S2 已用資料不得放入 S3。
  在模型呼叫前按 source completeness 預登記完整研究組與缺資料壓力組，不能看結果後挑樣本。
- S3 的 30 個樣本／模式須是事前可支持完整研究的輸入；缺資料案例留在壓力組，不拿來湊 30。
  如既有資料不足，記錄實際缺口並停止依賴它的階段；不倒填日期、不新增市場抓取、不冒稱已
  具備 120 個合格輸入。本次只確認既有 artifacts 可查，尚未完成此來源資格盤點。
- 在來源資格盤點同時核對已存在證據的公告時点與期間口徑；無 point-in-time 證據即保留未知。
  凍結快照代表可重播，不代表可直接作 OOS；只評估當份資料能支持的研究，不加入未來資料。
- 先跑相關隔離回歸，最後候選凍結後跑一次全庫非 live 回歸及有風險的整合 lane。
  已驗證而未變更的證據沿用。25 skips 逐項標為本次必測／有效既有證據／不適用；正式採用的
  SQLite／RQ worker、publication／cache／renderer／UI 路徑不能因 skip 就放行。
  PostgreSQL live 若非本次部署後端，不阻擋 SQLite 發布，但仍列為未驗證，不標原任務完成。
- 隔離 Redis／PG／瀏覽器只使用既有可用 runtime、唯一私有 DB／socket／測試頁，不接正式資料庫
  或清正式 queue；不因測試需要擅自安裝／升級或切換儲存後端。缺能力先完成不依賴的工作，
  必測 lane 缺失則禁止發布，集中交代一次。
- **出口**：一份修正候選、完整錯誤分類、可執行總預算守衛、來源／樣本 manifest、固定驗收
  rubric、相關測試與獨立覆核無未解重大發現。不要求每個微小編輯獨立 commit。

已核對存在的針對性驗證入口（實作時按實際影響增減；此處沒有執行）：

```bash
env -i PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin PYTHONDONTWRITEBYTECODE=1 \
  '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' -B tests/run_prompt_boundary_tests.py \
  tests/test_generation_schema_guidance.py tests/test_generation_numeric_integration.py \
  tests/test_research_assertion_lifecycle.py tests/test_decision_contract.py \
  tests/test_generation_graph_roundtrip.py tests/test_generation_publication_integration.py \
  tests/test_generation_research_availability.py tests/test_model_identity_lifecycle.py \
  -q --tb=short -p no:cacheprovider
```

同一 DEV 目錄的最後全庫入口為相同 env／Python／runner 接 `tests -m 'not live' -q --tb=short
-p no:cacheprovider`；實際執行另指定不覆寫舊檔的 JUnit 路徑。需要 live 的 lane 不能由此命令推定通過。

#### S1 v4 端到端（先證明有資格進入擴大測試）

- 原 2330.TW／v4 凍結來源仍做 regression；S0 若判定它只能支持診斷，預先明示，不要求模型
  補造來源以變成研究成功。4 個工作額度內至少安排 2 個事前合格的 v4 研究輸入。
- 使用正常 22／23→24→final audit→renderer／snapshot／私有 report index 流程，不直接塞入
  synthetic accepted output。整體最多測 2 個候選版本；第一次失敗可依新證據集中修正一次，
  仍共用原階段額度。相同輸入／相同候選／相同錯誤不作無意義重送。
- **出口**：最後同一版本至少 2 次連續合格完整 v4 報告，含 22／23／24 全節點與落檔讀回；
  不只單角色通過。metadata／prose repair 若自然啟動則核對來源／原稿／patch／rollback；若未
  觸發則標「未觀察」，不能硬改原稿誘發後稱 live 成功，也不以此單一指標無限延長測試。

#### S2 12 組新舊配對（跨四模式）

- 基準使用 `75824229` 的隔離副本，不啟動或改動正式 checkout；候選固定為 S1 最後通過版本。
  同一組 source bytes／截止時間、同一逐角色模型路由及相同 generation knobs／資源政策，
  新舊各跑一次。原本想評估的程式／提示差異保留，不回補新版 validator 到舊版。
- 順序交錯以減少 provider 時段偏差；觀測 actual request／response model 標籤。
  若 fallback 使實際模型不同，保留該 job 在整體成功率分母並標 model-confounded，不當作相同
  模型的提升證據。不可刪失敗重跑到對得上；若無足夠配對，判定比較未完成。
- 至少 8／12 為可比較同模型配對且每模式至少 2／3。四模式候選都須達到預登記的端到端
  結果：可產生有限研究／診斷者要完成 artifact 讀回，必須拒收者則證明未發布。資料不足壓力組
  須 100% 正確降級／拒收，不把診斷計為完整成功；如有事前完整研究組，至少 90% 合格
  （向上取整），無候選新造成的重大內容錯誤。全 12 組原始分母另外完整公布。
- 某模式沒有完整研究合格輸入，就明示該模式研究成功率改善不可比較，不以 0／0 作 100%；
  S2 只能支持其結構、來源忠實與正確拒收等對照，真正完整研究門檻仍須 S3 證明。
  使用預登記、版本中立的外部 rubric 評分新舊 artifacts，不能直接比較不同版本的自報 gate。
- 完成率在各模式具有研究資格的可比較組不得低於基準；若只達持平，不宣稱成功率改善。已知重大內容缺陷的
  避免率須改善或維持原已正確行為。只對足夠且同條件的數據描述樣本內差異，不宣稱統計證實。
- p95 時間與每份合格報告 token 成本若較可比較基準惡化超過 25%，禁止直接發布，集中交代
  品質／成本取捨；若基準零份合格則成本比值為不可計算，不補零或無限改善。
- **出口**：四模式配對結果、來源資格與完整失敗清單、角色設定建議；S3 前鎖定 code、prompt、
  schema、validator、routes、generation profile、評分規則及樣本。S2／S3 期間不得邊改邊混算。

#### S3 120 個預登記樣本（正式候選品質驗收）

- 四模式各 30 個不同 ticker／截點輸入；按預登記順序每批最多 12 份（每模式 3 份），
  同一份 job 的正常有界 retry 不變成新獨立樣本。只跑固定版本；不能失敗後替換標的／日期。
- **完整研究成功**：實際存下 HTML／Markdown／snapshot，所有必需角色有可採用完整輸出，
  generation／final audit／來源與結論驗收通過，分類為 `verified_research` 或
  `verified_no_action`。有充分研究依據的觀望可以合格；`diagnostic_no_action`、
  `research_with_limitations`、模板／資料不足、未完成、取消与未知均不計此成功分子。
- **硬驗收**：每模式至少 **29／30** 合格完整研究；所有已發布樣本重要數字與引用 100%
  可核對、無重大數值／單位／期間／來源錯誤、無未解結論矛盾、無不安全交易指令；每份報告的
  重要決策與關鍵來源逐份覆核。自動 gate 通過不等於全文語意保證。
- 另對每模式按預登記抽樣 5 份（20 份）做獨立全文覆核，所有失敗／警示額外覆核。
  rubric 為「來源忠實、模式相關、結論推理、反證限制、清楚可讀」各 0–2 分，逐項有原文／
  來源位置；至少 18／20 達 8／10 且各模式平均至少 8／10，任何重大失實一票否決。
  獨立覆核是工程內容檢查，不冒稱真人投資專家審閱；不把未抽到的正文稱為全面語意驗證。
- 生成成功率、無缺段率、數字／來源覆蓋、結論一致、觀望／診斷比例、首選送達／合格率、
  fallback、15／30／60 分鐘完成率、延遲分位、token 覆蓋與缺失分開報告；每項附分母／cutoff。
  若未觀察 provider 恢復事件，恢復後完成率列未觀察，不為取數故意製造正式 429／5xx。
- 公布比例的信賴區間與同 ticker／日期相關性；30 個不同配對不代表統計上完全獨立，
  29／30 是本次先導放行標準，不保證未來長期成功率下限。
- **出口**：全部模式達標、同一候選未漂移、沒有靠移除失敗或改 gate 達標，才進 S4。

#### S4 條件式發布、重啟與四模式 canary

- S0–S3 通過及取得本方案整體核准才執行：scoped commit／push 至既有 origin 分支、
  建立或更新該分支 PR、完成必需 CI／review 後合併；不帶 `.env`、金鑰、原始 prompts、
  private captures、DB、快取或研究 artifacts 上 GitHub，不 bypass 分支保護。
- 發布前核對實際 main 與 API／Worker 版本、任務佇列／active jobs、相容性及原版本可回復性。
  正式 main 若已有其他合法修改，先做整合／回歸，不覆蓋。整合導致被測行為或 profile 改變，
  舊 cohort 不冒充新版本；在現有餘額內不足以重新驗收則停發布，不擴額度。
- 只經 `start_mac.command` 既有入口部署／重啟 API／Worker；先等在途 job 安全結束／可恢復，
  不 kill 其他任務、清 queue、清 quota、重置 circuit 或升級 DB schema。
- 本方案的条件式發布授權包含短暫維護保護：暫停本系統新分析 admission、排程送件及一般
  queue 消費，保留原 queue／scheduled jobs，讓新 runtime 先只處理 4 份已登記 canary。
  這個限制必須在重啟前生效、重啟後可讀回，並在 S0 以隔離測試證明；不能只看 active jobs=0
  就認為之後不會送件。4／4 通過才恢復一般工作；失敗則先回復已核對版本再恢復。
  如沒有安全可驗證的維護／canary 隔離能力，停在發布前，不用正式一般任務代替 canary。
- canary 使用預先核對的凍結輸入及正常正式 worker／發布路徑，各模式一次，新增可追溯的
  canary artifacts，不覆寫歷史報告；標明研究截止日，不刷新行情或對外發送通知／交易。
  若既有正式入口無法安全注入凍結輸入並抑制額外外送，須在 S0 完成此能力及測試，否則不能發布。
- **出口**：API 和 Worker 都載入預期 SHA／設定，readiness 的 storage／queue 健康；4／4
  canary 合格，events→snapshot→API／UI 分母和模型標籤一致；記錄重啟前後與回復路徑。
- 任一 canary 未達標、出現重大內容／服務回歸，或驗收前預算／時限已到，維持一般送件隔離並
  停止本 campaign 新送件，透過既有可回復發布流程
  恢復先前已核對版本並重啟本次服務；不回滾／刪除 DB 或歷史 artifacts，不強制 git reset。
  如安全回復需要新破壞性操作或無法隔離本次服務，停止並一次說明精確必要授權。

### 保留邊界與終止規則

- 外送範圍：只向既有 Google Gemini generation 路由傳送本方案預登記、經敏感資料排除的
  股票研究來源與提示；沿用既有金鑰認證，key 不入 prompt／artifact。保留正常受驗證工具，
  只允許本地計算及凍結來源讀取；不新增供應商、不上傳私人持倉／帳戶資料、不開 embedding
  或市場資料刷新。其他網路仅限必要 GitHub 發布／CI 及既有授權的 quota 控制端點。
- Gemma batching 維持 OFF；原路由可自然 preflight／fallback，但沒實際 Gemma 回應就不計
  Gemma 成功。本方案不承諾改善 Gemma 成功率，也不把既有 local cap 當 provider quota。
- 原 28 組 OOS 與市場成熟等待是獨立工作，不重送、重建或擴樣；本次報告品質驗收不能證明
  投資勝率／OOS alpha，也不能把上述外部等待改標全部完成。
- S1 兩個候選仍無完整報告、任何預算／時限先到、S3 任一模式已有 2 個不合格樣本（即不可能
  達 29／30），立即停止相應 campaign 的後續 live；保留已跑結果及未跑清單，不開新窗口補測。
- 任何階段出現秘密外洩風險、來源被改写、重大錯誤漏過發布，停止整批外送／發布並保留證據。
  同一根因连续 3 個 job 失敗也提前停止；provider 429／5xx 遵守既有 cooldown，不能不停換 key
  或用重啟清除。不得用降低品質標準解除停止條件。
- 停止是「本次預算內未達標」，不是全部完成。集中交付：已完成、未達標原因、已消耗總量、
  精確剩餘缺口與是否需要新的方案／預算；不再每個小修後重複問核准。
- 進度只報實質里程碑、原因改變、完成或需使用者決策。需要跨回合等待時使用產品原生續作／
  監控機制，未變化保持安靜，campaign 完成或到期即停止；本次提案不建立背景排程。

### 集中核准項目

核准本節即同意：在上述範圍內集中修正及驗證，最多 152 個報告工作、2,400 次模型 HTTP／
transport 嘗試，採 1.6 億 token／US$50 預估費用停送線与階段時間／7 日有效期；傳送預登記
凍結研究資料至既有 Google 路由並使用既有認證；**僅當全部放行標準通過，才 commit／push／
PR／合併／部署／重啟與 4 份 canary，失敗時在既有安全範圍回復。** 不授權擴額度、擴供應商、
放寬 gate、啟用 Gemma batching、變更原 28 OOS 或破壞性資料操作。

## 2026-09-13 接續執行狀態

使用者要求「繼續，直到全部完成」。沿用原 P0／P1／P2，以下為同一份工作清單，不將第一批測試通過誤報為完整計畫完成：

**最新離線候選為 `69ae5fb347c7…`（752 核心檔），完整 backend `d68af90e9240…`（919 檔）：承接來源／品質退件與 attempt 去重，再加入保留原稿的有界問題句修稿；尚未 live／部署。** 最近一次 21:07 真人核准的 live 仍是 `5ec8f5b868f1…`／`8f4fb9c29a67…`：4 次 HTTP 200／4 份完整 STOP JSON，12.874 秒，**0 合格完整報告／1 job**，授權已消耗。原四稿離線重放 issue 數目前 **2／1／17／2**，全部 rejected；以明示 synthetic patch 修正前兩份首稿可通過有限 gate，但不是新模型回應、完整報告或成功率證據。原事件不回補成新版紀錄。具體來源主張、完整語意與新候選 live 驗收仍待；四模式 paired／cohort、完整品質驗收及正式發布仍未完成，詳見末節。

- P0：數字／來源與決策契約、完整 JSON、單次有界品質重寫、validated cache、安全 fallback 及發布邊界已實作。DCF 新資料 producer 已接上同年度報表來源，公開財報實取與 readback 已驗證；財報幣別不可由交易幣別猜測，舊快照已保存的反證亦不可忽略。當期內在價值與歷史技術指標不可冒充未來／交易價格，原始 schema 預檢堵住 tolerant normalizer 補值。歷史 live 候選 `49c5f074…` 包含來源保真、同筆 fact／ASOF、有界 metadata repair 及來源綁定的有限期間語法；之後離線新增比較證據、有限敘述核對與可逆 wire v2，見末節。17:46–18:04 全庫非 live 回歸於 `fd4c7561…` 完成：11,659 passed／1 failed／24 skipped／2 deselected／75 subtests passed。唯一失敗為事件 helper 長度 162 行不符合既有 <160 規則；僅統一參數排版至 155 行、AST 不變，相關 763 項補驗通過，形成 `49c5f074…`。不將原全庫結果改寫為零失敗。12 組凍結 graph／checkpoint／snapshot 另有通過證據。不同版本及重疊測試不相加；全文仍明示語意未全面驗證，live 正向完整報告仍未通過，不能標記完整計畫完成。
- P1-1／P1-2：共同 mixed-language estimator、SDK 工具宣告計量、完整 JSON 路由 admission、實際 role output reserve、短期跨 job 5xx 冷卻已整合。21:07 最新窗口的 4 次請求均由 `gemini-3.5-flash-lite` 回覆 HTTP 200／完整 STOP JSON，未抵達 Agent 24／final audit／發布。Gemma 因既有 12k local input cap 未送達，其他 Gemini 路由遵守既有 circuit；沒有清除或繞過。前次 19:09 的 `49c5f074…` 是 3 份完整 JSON／1 次取消、零合格報告，仍保留其原始結果。兩次均非本輪 provider 429／5xx／逾時或市場成熟等待；不能由 HTTP 完整、單角色 gate pass 推定四模式品質成功率上升。
- P1-3／P1-4：job／node／provider-attempt 分母、cutoff／censored、模型實際回傳標籤、品質分類 API／UI、金融業適用性及 Agent 20 缺逐字稿處理已整合；後續逐項驗收補上恢復後完成率、跨重試身分與發布漏檢修正，見末節。正式 UI 尚未載入。
- 全域整合：新生成品質 gate／final audit／renderer／snapshot／checkpoint 共用本輪輸入與輸出來源綁定；摘要及 tear sheet 為已核驗輸出的 deterministic projection。歷史 reader 不回寫。
- P2：凍結輸入離線回歸與四模式真實 graph／checkpoint 接點測試已完成；同輸入 live 對照、每模式至少 30 次跨產業／日期先導、部署 canary 尚未完成。不能以離線測試或輸入預檢替代真實品質／成功率。
- 正式 DB、歷史 artifacts、Gemma dark launch、既有 28 OOS cohort 都不因開發測試改動。Git／發布／正式送件由主代理單一擁有者處理。

新生成接點：`numeric_claim_contract_version=1`、`decision_contract_version=1`。
數字側 `build_fact_registry(data, visible_payload, agent_num=...)`、
`validate_numeric_claims(markdown, registry, required_fact_ids=..., decision_facts=...)`；
估值側 `build_decision_contract(context, require_complete=True, fact_registry=...)`。
純文字假設與 metadata 不可借作已驗證金融事實，缺值保持 unavailable。

本批承接 `output/quality-pilot-20260912/OPTIMIZATION-PLAN.md` 的已核准方向。
實作基底為 `758242290e795146520f58f68ffa113cac35e52c`，分支為
`codex/report-quality-hardening-20260912`。正式 main／API／Worker 未切換。
開發工作樹保存在 `/Volumes/X10 Pro Mac/stock-agent-report-quality-dev`，
與正式 checkout 分離；原始 pilot 證據仍保留於正式 checkout 的原路徑。

## 已實作的行為

| 問題 | 本批修正 | 驗證邊界 |
| --- | --- | --- |
| 截斷 JSON 被修補成正常報告 | 新生成內容先驗證完整 JSON 與必要根欄位，再進寬容 normalizer；財務與證據角色明示日期、信心、正文、來源、反證 | 原始片段及正常完整 JSON 都有回歸；歷史 reader 不改寫 artifact |
| 工具角色 2／13／18 跳過契約 | 應用層強制結構，不啟用不相容的 native JSON + tools | 保留原 calculators／function tools |
| 結構重試命中同一份壞快取 | 未驗證輸出只暫存 pending；通過本輪 gate 才保存 schema v2 validated cache；修復 bypass、舊 schema miss | 有真實 runner orchestration／mock provider 計次；合法快取仍重用 |
| 第二次不完整仍算完成 | 初始、身分、品質重寫及同步／非同步最終稽核共用完整性判定，失敗不直接採用 | 取消／deferred、草稿 checkpoint、修復 rollback 維持獨立 |
| 1.16% 變 116%、年度混用 | 殖利率來源明示 percentage points／ratio；FCF 與淨利按同年度索引配對 | 極端值、缺值、金融業與 5% 邊界皆涵蓋 |
| 億／B、股／張不清楚 | 選定財務 facts 共用 formatter；TWSE 借券保留 shares 與明示 lots 換算 | 不從數字大小猜單位；未知幣別／期間不補造 |
| 觀望被當成下單 | 按實際文字區分不交易、再評估、條件式及立即下單 | 真正延後下單仍攔截，不信任模型自填 intent |
| 光罩技術名詞被當公司 | 窄幅技術語境消歧 | 明確公司／ticker 綁錯仍阻擋 |
| 護城河 fallback 補造固定分數 | 缺證據為 N/A／unassessed，保留模板來源 | 不把缺資料當低分、高分或模型成功 |
| snapshot 遺失 fallback／模型資訊 | graph、checkpoint、repair replacement 保留或清除對應 receipts；token 白名單只保留合法數字 | 秘密欄位仍移除；SSE 保留品質未知與模型來源 |
| 原始 JSON 再次附於正文 | 結構 renderer 不把 raw JSON 當分析段落；Neutral 缺引用的支撐壓力不保留數字 | 有來源的價格仍由既有 provenance gate 判定 |
| 技術指標有數字但沒有可核對引用 | Agent 22／24 保留一份完整計算日線，逐次重算建立 typed facts；RSI 是點數，不是百分比 | 不把均線／ATR 等指標提升為支撐、壓力或可交易目標；來源缺失拒絕 |

模型身分指的是程式觀察到的 route ID，不是獨立驗證 provider 內部版本。
節點未拋例外不再推定品質通過。Cache、deterministic fallback 與 provider response 分列；
新模型沒有用量資訊時保持未知，不能繼承前次用量。

## 接續批次：新生成契約

- `canonical_fact_*` 保留值、單位、幣別、期間、原始來源與可見提示路徑；未知期間／來源保留 unavailable。正文使用可核驗 fact token，由 server formatter 顯示，不從數字大小猜單位。純文字未綁定數字、未解析 token 或來源都會留下阻擋。
- 每個 Agent 的 registry 保留自己的 `visible_ref`；跨 Agent 合併只忽略提示列位置，不能忽略值、單位、幣別、期間或來源衝突。凍結 12 組／156 個提示變體的 7,674 次相同來源比較已無遺失。
- `decision_contract_*` 重算 EPS × P/E、DCF 工具結果、同期間加權及 Long／Short 價序；最終目標必須引用已核驗上游 anchor。來源不明的零成本、無橋接的目標差異、raw 價格被 normalize 成 N/A 仍會攔截。詳細欄位見 `docs/decision-contract-v1.md`。
- `dcf_history_lineage.py` 額外核對 calculator 實際使用的兩年營收，以及 FCF 正規化的淨利／現金流；來源必須可見且值、單位、幣別與年度一致，growth 年度必須相鄰，normalization 兩值必須同年。收據保留完整消費來源；不改舊 calculator 或編造缺少的 producer。
- `statement_facts` 從已抓取的年度 balance_sheet／cashflow 保留 exact value、原始欄日期、row identity；DCF 選用同一報表期的股數、現金、負債及 FCF，不冒用 undated info 或把缺 CapEx 當零。實際 core fetch → tool input_provenance → visible registry → JSON replay 已有隔離正向／負向測試；來源晚於估值觀測日會拒絕。這不表示已核验財報公告時點，也不把期末股數宣稱為即時股數。
- DCF `value_kind=current_intrinsic`、`calculation_validated=true`、`decision_validated=false`：可說明當期內在價值，不提供虛構目標期限；缺乏獨立未来價格方法時三個 `price_targets` 維持 null。既有凍結資料不回補新 producer 欄位。
- Provider schema 只投影解碼提示，保留欄位／型別／required／enum／references，不修改 enum／const／examples 的 literal data。本機 raw schema 先核驗原 payload，再進既有 normalizer／領域 gate；不能以補齊 highlights、clip bounds、default 或重新綁 hash 洗成通過。Legacy reader 不啟用新生成預檢。
- 數字契約 system-format 只在實際 prompt 帶版本 marker 時啟用，sync／async／stream／estimator 共用；精準修稿回饋提供 bounded 欄位／裸數字／來源樣本及修正要求，完整 raw payload 與全部 issues 不刪減，仍全量驗證。
- raw payload、normalized output、accepted text 與本輪市場輸入各有綁定；repair、rollback、cache、draft resume 與 partial rerun 不可沿用失效收據。舊報告缺少完整前序證據、資料變更或重複 Agent 別名時，局部重跑回覆 HTTP 409，要求完整重跑；不妨礙歷史閱讀。
- final audit、renderer 與 snapshot replay 重新核驗，而非只信任上游 passed 標籤；摘要與 tear sheet 不再於稽核後另呼叫模型。新生成 snapshot 對證據使用 lossless 軟上限，超出會記錄 `snapshot_size_limit_exceeded`，不剪掉原始輸入／輸出後仍保留綠燈。舊 snapshot 保留既有截減規則。
- 發布分類為 `verified_research`、`verified_no_action`、`research_with_limitations`、`diagnostic_no_action`；缺收據或衝突則 `blocked`。安全診斷可讀，但不算完整研究或 provider 品質成功；缺逐字稿的 Agent 20 是明示可選限制，不能套用到其他關鍵 Agent。
- provider 有完整回應但內容不合格，分別記錄「provider response」與「content rejected」；partial stream 中斷仍是 provider error。cache、fallback、node complete 不冒充 provider 成功。15／30／60 分鐘完成率保留 pending／失敗與未滿觀測時間的 censored 樣本。

這是可控數字語法、來源與決策一致性的程式核驗，不等同所有自然語言主張已由外部來源獨立查證，也不證明投資績效。

## 第一批測試與證據（歷史紀錄）

- 所有驗證透過 `tests/run_prompt_boundary_tests.py`，使用暫存 SQLite、memory cache、禁止網路；未連正式 DB、Redis 或 provider。
- `tests/fixtures/quality_pilot_20260912.json` 保存三筆真實回應，逐字核對凍結來源一致：
  - Agent 2，event `1020367`：270 字元，MAX_TOKENS，必須拒絕。
  - Agent 22，event `1025655`：463 字元，MAX_TOKENS，必須拒絕。
  - Agent 24，event `1025722`：527 字元，STOP，JSON 本身完整；可讀取但不得把 raw JSON 再附為正文。此筆不是 provider 截斷案例。
- 專用負例先取得失敗訊號，再修正；另保留合法 JSON、calculator 配置、合法快取、非交易 fallback 與錯誤 ticker 等控制案例。
- 獨立交叉審查發現的 confidence 型別例外、pending cache 錯綁、final-audit 旁路、數值溢位、SSE null 與跨模型 token 錯歸已補回歸。
- 整合回歸結果記錄於本工作樹 `output/quality-hardening-validation.xml`；最終結果以下方驗證紀錄為準。
- 最終回歸涵蓋 43 個測試檔：結構與品質 gate、同步／非同步最終修復、checkpoint／cache、財務單位、公司身分與交易契約、模型用量與 SSE、路由降級、架構邊界及報告 artifacts；不是全 repository 測試，也不是 live provider 成功率測試。

## 目前未完成／未驗證

本文件不表示完整 P0／P1／P2 計畫完成。

1. **最新候選已實測，但仍無合格完整報告**：2026-09-13 19:09（Asia/Taipei）依使用者新一次「核准」執行核心 `49c5f074…` 的單次 6 calls／4 分鐘窗口；4 次 HTTP 200、3 份完整 STOP JSON／1 次取消，13.268 秒結束。Agent 22 首稿 7 項數字／引用位置問題，重寫後 10 項（包含未知 sma_999）；Agent 23 已有 3 個來源期間通過，但剩 3 項裸日期數字與 2 項同筆 source_refs 缺漏。仍為 0 合格完整報告／1 job，未執行 Agent 24／final audit／renderer。該窗口已消費並結束，不沿用剩餘次數；後續先處理已觀察到的格式遵循／修稿問題，任何新的外送實測另需明確有界核准。17:20、16:19、14:14 及其他版本分列歷史。
2. **P1 配額只有初步角色證據**：已觀察 schema HTTP 400、provider 503、推理消耗 output cap 導致 MAX_TOKENS，以及完整 JSON 仍因數字／來源契約拒收。不能宣稱四模式成功率上升。Gemma 在目前完整來源輸入下仍超過本機 12k input cap；保留完整證據與既有 dark-launch 關閉，不以截斷來源或放寬 gate 增加表面成功率。
3. **P2 未完成**：完整 12 組同輸入 live 對照未完成；只有原 2330／v4 的有界實驗，沒有合格完整報告。每模式至少 30 次跨產業／日期先導尚未執行。不得把同一舊輸入重複執行視為獨立日期樣本；provider 回應率、研究合格率、診斷發布率與投資結果必須分開。
4. **DCF 公開財報實取已驗證，公告時間／口徑及正式 runtime 仍未驗證**：2330.TW 的三份年度財報已實際取得，通過實際 extractor、同報表期 selector 與逐值 readback；24 筆有效及 6 筆缺值均保留原始來源，詳見「DCF 年報 producer 的真實來源正向路徑」。此結果不會補回凍結資料，不是 point-in-time 公告證據或新估值報告。當期 DCF 仍不是未來價格模型，不能以可說明的內在價值冒充已驗證目標價，也不需要編造 `valuation_target_horizon`。
5. **來源限制與建模決策**：凍結輸入未記錄的報表期間、forward EPS 預估期、目標估值期間及股數日期不能由現在時間補造。新 yfinance adapter 只保留未被 fallback／calibration 改寫的 provider 欄位與報告期間；DCF 現金流 forecast years 不等於目標價期限。不能任意加上 12 個月期限來解除 gate，安全 N/A 也不算完整研究成功。
6. **未發布**：未 commit／push／建立 PR／部署／重啟服務；正式 runtime 仍是 `758242290e795146520f58f68ffa113cac35e52c`。未變更路由、Gemma dark launch 開關、28 組 OOS、歷史報告或正式 artifacts。

## 第一批驗證紀錄（2026-09-12 中午，非接續批次結果）

- 2026-09-12 12:19–12:23（Asia/Taipei），在上述永久開發工作樹完成最後一次 43 檔整合回歸。
- **2,518 passed、75 subtests passed；0 failed、0 errors、0 skipped**，耗時 240.77 秒，process exit code 0。JUnit 將主測試與子測試合計為 2,593。
- 2 項既有 `DeprecationWarning` 來自 `tests/test_repair_dependencies.py` 對舊同步相容入口的刻意驗證；沒有放寬 assertion 或忽略失敗。
- 獨立交叉審查完成；所發現問題皆已修正並納入本次通過的回歸。`git diff --check` 通過。
- 正式 checkout 仍是乾淨的 `main`／`758242290e795146520f58f68ffa113cac35e52c`；本批修改保留於專屬分支，尚未提交或部署。

這些結果證明已測行為符合預期，不證明四模式真實產出率、內容正確率或投資成效改善。
正式 runtime 尚未載入本批修改，後續應先完成剩餘高優先修正，再以明確版本進行部署與同輸入實測。

## 接續批次驗證紀錄

- 隔離全庫首次結果：10,536 passed、15 failed、22 skipped、1 deselected、75 subtests passed；15 個失敗均已逐項核對並修正，不把此輪計為全綠。
- 失敗檔案與四模式 graph 整合重跑：259 passed，11.07 秒；`output/quality-hardening-regression-repairs.xml`。
- 最新 generation registry／fallback／局部重跑／audit／import boundary 整合：556 passed，14.48 秒。交叉審查補驗 119 passed，2.09 秒；未見剩餘 material finding（限該審查範圍）。
- 真實凍結來源可見路徑重現：12 cases、156 variants、7,674 comparisons，losses 為空，1 passed，7.38 秒；這是離線來源合併驗證。
- 四模式真實 LangGraph、adapter、InMemorySaver、final audit 及 snapshot replay 均通過；provider 為明示離線 double，輸出是安全診斷，不宣稱 live 報告成功。
- 品質觀測 UI fixture 於桌面 1280×1000／手機 390×844 驗證 API 200、console error 0、手機無水平溢出；惡意 model-version 字串保持跳脫。不是正式部署驗證。
- 全庫非 live 回歸完成：2026-09-12 13:45:54–14:03:53（Asia/Taipei），10,607 passed、75 subtests passed、22 skipped、1 deselected、0 failed／errors，1078.08 秒、exit 0；`output/quality-hardening-full-regression-final.xml`。JUnit 合計 10,704 含子測試／跳過。這是最後 DCF history lineage 與凍結 graph 公司名稱補強之前的凍結程式，後续小修另列相關回歸，不宣稱同版全庫重跑。
- 最後小修：DCF history 先取得 12 個 faithful red，修正後相關 292 tests 通過；公司名稱誤判先取得 3 failed／4 positive passed，修正後 7 tests 通過，擴大 177 tests／75 subtests 通過。只排除完整「重新產生／重新產出」動詞中的單次「新產」，真正公司主體／錯 ticker／同句混入公司名仍阻擋。
- 協調者於最後 source 狀態執行 15 個來源／決策／graph／cache／snapshot／partial-rerun／架構 suite：778 passed，15.42 秒、exit 0；`output/quality-hardening-final-source-integration.xml`。
- 完整 12 組凍結資料透過真實 graph、final audit、checkpoint 與 snapshot replay：12 passed，12.11 秒；`output/quality-hardening-frozen-graph-persistent.xml`。持久入口 `tests/quality_pilot_graph_probe.py` 需乾淨環境與 `QUALITY_PILOT_GRAPH_PROBE=1`，未啟用實測為 1 skipped，沒有隱性觸發。provider 為明示離線 double，所有輸出屬安全診斷。
- 上述離線診斷 snapshot 的 JSON UTF-8 長度 566,854–1,681,454 bytes，12 組都未超過 2,097,152-byte soft limit，來源 hashes 讀回不變；不代表真實長報告也必定低於上限。
- 22 skips 涵蓋未開啟 isolated PostgreSQL live suite、外部公開來源、live commercial browser、Chart.js／visual browser、指定歷史 artifact／checkpoint 複本與 Redis smoke 等條件；測試隔離刻意禁止連正式 runtime、Redis、provider。3 warnings 是 RQ 舊 UTC API 與兩個 legacy sync 入口 deprecation，並非失敗。
- 最後小修後的離線預算矩陣：12 jobs、369 rows、304 admitted，1 passed，14.68 秒；`output/quality-hardening-budget-matrix-lineage-final.json`。程式集 SHA256 `b8c670d5eb844a4e667ad08ac266924980a31e81a97eaba084b5b4376a2a363e`，路由檔 SHA256 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`；讀回原始來源 hashes 不變、紀錄中的 backend 程式檔無 drift。前一版矩陣保留、不覆寫。
- 矩陣以完整 production AgentState／market context 建提示，但使用歷史前序分析；不含新 RAG、重算前序輸出或 provider countTokens。歷史-only 路由與 Agent 20 假設請求不能混入目前需執行路由的分母。
- 僅目前 configured 且非 deterministic skip：69 個 job/agent 位置皆至少有一條預檢可接受路由。Gemma 51/51 超量（15,084–31,944 tokens）；Gemini 3-flash-preview 69/69、3.6-flash 69/69、3.8-flash 69/69、3.5-flash-lite 51/51 輸入預檢可接受；這些都不是 provider 請求或品質成功數。
- scoped pattern-only secret scan：162 個 changed／untracked nonignored 檔案，常見 API key／private key patterns 無發現；不是完整秘密資料稽核。`git diff --check` 通過。
- 正式服務本輪唯讀基線：runtime SHA 如上、dirty=false、readyz ready、storage/queue pass；RQ 待執行／執行中／deferred／scheduled 均 0，既存 failed 12（recent 2／stale 10）未清除。此為發布前基線，不代表本批已上線。

## 下一個可接續點

更新於 2026-09-13 19:09 實測後：核心候選仍為 `49c5f074…`。使用者新的 6 次／4 分鐘授權已執行，4 次呼叫、0 合格完整報告；三份完整原稿已離線讀回確認，來源與程式不變。下一個工程重點是均線／指標名稱的來源綁定格式，以及引用／日期錯誤時整篇重寫帶來的額外錯誤；先做來源明確的反例與方案驗證，不立即重複相同 live 測試。詳見末節，不擴大 metadata patch 權限或將裸數字一律豁免。

17:42 版本紀錄：期間綁定在 DEV 完成有限語法與獨立覆核，當時核心 **`fd4c7561…`**、953 項相關整合通過；17:20 原稿離線重驗與四模式流程／容量證據見「來源綁定的期間語法」一節。沒有新增 provider 呼叫；原 live job 仍失敗，尚未證明全文語意或正式產出率改善，不能略過後續 paired／cohort／部署驗收。

1. 新期間候選的全庫非 live 已完成：11,659 passed／1 failed；唯一事件 helper 排版長度問題已修正，763 項相關補驗通過且 AST 不變。24 skips／2 deselected 不算通過；原結果、前版全庫及 graph／容量等局部證據分列，不覆寫、不相加，也不為自動續作重跑未變更測試。
2. 最新有界 2330.TW／v4 live 已在 19:09 執行並失敗；先以保存原稿評估來源明確的指標名稱／期間語法及 prompt／修稿引導。完整來源、同筆引用、日期、正文／決策與發布 gate 不變，`semantic_coverage: not_checked` 不變。不把未知 fact 自動替換成另一個指標，不把安全診斷當完整報告。新的外送實測另需明確有界核准；原窗口不重用剩餘次數，原凍結輸入不回補新來源。
3. 小實驗通過後再準備完整四模式同輸入新對照與 >=30/mode 的跨產業／日期 cohort，保留所有提交／等待／失敗／診斷分母。依結果決定配額與路由，不預先認定更大 output cap 就會提高品質。
4. 完成上述必要驗證後才推進 scoped commit／PR／合併、正式 runtime 切換與 canary；核對 exact deployed SHA、readyz、API/Worker 與 artifact 讀回，不清除既有 failed queue 或修改 OOS／市場成熟條件。

## 明確核准後的真實 provider 證據

使用者於 2026-09-12 14:37（Asia/Taipei）回覆「核准」，所對應問題明確包含「將凍結研究資料與提示送至既有 Google Gemini 路由測試」；金鑰僅供 API 驗證、不放入提示。完整 graph 曾再次被 auto-review 擋下，主代理唯讀核對原始問題／回覆後附上時間與原文，同一範圍執行才獲准。被拒絕的那次程序沒有啟動，也不計入 provider 分母。

### 十三筆單角色實驗

來源都是原 2330 v4 `database-job.json`，包含十二筆 Agent 22 及一筆 Agent 23。每筆只測單一角色、保持原資料、共用正式 quota guard；不是十三筆完整報告，也不能當成精確 physical HTTP 請求數。證據位於 `/private/tmp/stock-agent-quality-live-*-20260912/`。

| 結果 | 筆數 | 判讀 |
| --- | ---: | --- |
| 原 native schema／直接 response_json_schema HTTP 400 | 4 | 同形狀去除 provider 不接受的 schema hints 後抵達生成；不能移除本機驗證 |
| Provider 503 | 3 | 包含兩筆部分串流後中斷；不能計完整回應 |
| 完整 transport response，但 MAX_TOKENS 截斷 JSON | 2 | 原 3072 及放大 6144 均曾遭推理消耗；加大 cap 不是品質保證 |
| STOP／完整 JSON，仍因數字／來源契約拒收 | 4 | 完整結構不等於內容合格；接受數仍為零 |

3.8 + system-format 實驗在 6144／3072 均保留六個 verified facts，剩兩個未綁定的標題数字；不是品質成功。兩份 prompt 除 run_id 外相同，但不能寫成 exact-prompt A/B。3.6 + process-only low／3072 能輸出完整 JSON，仍有未綁定數字與錯誤來源前綴。缺少 provider reasoning usage 欄位時保持未知，不以 total-input-output 推定為零。

### 完整 graph v4 對照（不是四模式完成）

主代理讀完 scratch main／safety／wire／tests 並完成安全複核。原 33 項離線安全測試包含真 SDK 的一般／gzip MockTransport、真 graph／renderer 拒絕、RAG lazy rebuild 禁用、共享 quota 失聯中止、SQLite／PG／外部寫入隔離、取消 checkpoint 及 evidence 預算中止收據。首次入口遇 bound-method RLock 複製錯誤，HTTP=0；改成與正式 job 相同的 closure 回呼，兩個 faithful red 後 33 passed。後加 process-only thinking 對照，34 passed；沒有以此宣稱 live 成功。

- `/private/tmp/stock-agent-quality-graph-2330-v4-20260912/`：測試工具錯誤，HTTP=0，未發 provider 請求。
- `/private/tmp/stock-agent-quality-graph-2330-v4-r2-20260912/`：原 source 設定，4 次 HTTP attempts；3 次 HTTP 200／完整 transport response 都是 MAX_TOKENS，reasoning 分別 2945／2948／2945，正文 82／107／111 tokens。Agent 23 第二次不完整觸發品質草稿失敗，並取消仍在執行的 Agent 22 修稿；第四次為 CancelledError、未收到 header，不是已確認 provider 5xx。未發布。
- `/private/tmp/stock-agent-quality-graph-2330-v4-low-20260912/`：只在程序對既有 3.6／3-flash-preview 採用 bounded thinking，原 output cap 與所有品質門檻不變。20 次 HTTP attempts 中 19 次 429、一份完整 STOP JSON（Agent 22／3-flash-preview，output 1591 tokens），仍觸發契約修稿；達 20 transport-call 上限後 partial 中止，未發布。429 沒有明確 violations／retry delay，不能推定為 authoritative RPD 用盡，也沒有據此永久停用 key/model。

三份 graph source／code／routes hashes 讀回不變；backend code inventory SHA256 為 `c8463ed23b899e32cff382af723ace01c8c939ff4f3f7cb8c871fd48ddcb7afc`。每次新 run_id、缺原 RAG、當下日期與重生上游文字均明列限制，不是 exact-prompt replay。HTTP 分母、角色契約與 job 發布分列；至此新生成完整合格報告仍為零，未向其他十一份凍結資料或擴大 cohort 推廣。

Google GenerateContent 文件說明 thinking level 與 output cap 的關係，3.6／3-flash 支援 low；此文件只支持參數語意，不支持本系統品質提升的宣稱：[Thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking)、[Structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en)。正式 source 的 thinking-model set、output profiles 與 runtime 路由尚未採納這次 process-only 實驗。

### 本輪新增的離線驗證

- schema projection／literal data 不變／system-format opt-in／raw schema before-normalizer 防補值均有負例與相應回歸；同一強度套用於 provider 回覆、fallback、snapshot 重新驗證與 actual v1 graph 的 Agent 20。
- DCF statement＋current-only＋future-period 拒絕相關 123 passed；整合 raw/schema/DCF/source/audit/cache/checkpoint/架構曾完成 783 passed（早於最後 fallback 映射與精準修稿小修）。
- 精準修稿兩個 faithful red → 122 related passed；估值 fallback 相容性三個實測失敗 → 修正後 168 related passed。完整 raw reasoning 保留於收據，display 三價格只有 null，限制說明放 valuation_reasoning。
- 獨立唯讀審查核對上述 code hash：94 passed，所審 raw/schema/system/fallback/repair 邊界未發現可重現 material finding；不是全库或 live 成功證據。
- 本輪 12 組凍結 graph／checkpoint／snapshot 離線重跑 12 passed，12.60 秒；`/private/tmp/stock-agent-quality-frozen-graph-post-provider-20260912.xml`。新版預算 probe 1 passed，15.21 秒；`/private/tmp/stock-agent-quality-budget-post-provider-20260912.json`。這兩項早於最後 fallback 映射修正，相關後續差異另驗。
- 全庫第一輪在已定位 fallback 相容性缺陷後由主代理中止，保留 1407 passed／3 failed／12 skipped／1 deselected／75 subtests、230.63 秒，不能計為完成。
- 修正後同一 backend inventory `c8463ed…` 的全庫非 live 回歸完成：10,713 passed、1 failed、24 skipped、1 deselected、75 subtests，1091.59 秒；`/private/tmp/stock-agent-quality-post-provider-full-regression-fixed-20260912.xml`。唯一失敗為 Chromium preflight 在 sandbox 無法啟動。相同 runner／相同單測先於 sandbox 重現，再於 require_escalated 通過 1 passed／1.67 秒，驗證 Chromium revision 1223／version 148.0.7778.96；無安裝、改碼或存取正式網頁。這是環境差異的補验，不是把原全庫結果改成零失敗。

## 最後補強：技術指標來源與輸入容量

根因來自實際 Agent 22 prompt，而非只看內部 State：financial JSON 及 AgentState 各只展示 20 根日線；AgentState 的 normalized_financials 只有 current_price，沒有另藏完整 120 根。原資料保存 2026-03-24～2026-09-11 的 120 根；以完整資料重算與保存值一致，但只用可見 20 根會改變 Wilder RSI／ATR，且無法產生 SMA60／MACD。因此單有保存值／hash 不足以宣稱完整輸入可見。

- 新 `canonical_technical_facts.py` 在 Agent 22／24 financial JSON 提供一份 `technical_calculation_inputs`：完整日線、as_of、來源、sample count、明示計算政策及調整價口徑未獨立核對的限制。使用既有無損 record-table；不在每個 fact 重複日線。缺日期／來源、不合法 bars、重複／逆序／未來日期、policy／snapshot／可見值不一致皆拒絕。
- registry 逐次重算 13 類指標，保存 exact raw／visible 路徑、完整輸入 SHA256、`calculation_validated=true`、`decision_validated=false`、`value_kind=historical_indicator`。不足樣本／缺 high-low／零均量按指標保留 unavailable；合法負 MACD、零柱狀差不誤判。RSI 量綱為 index_points，顯示單位「點」；不能套百分比或 metadata score。
- 稽核負例堵住 Python `False == 0` 的可見值混淆，並禁止歷史指標直接或加權混成未來／交易 anchor，即使注入 horizon／passed flag 亦拒絕。均線與 ATR 並未因此取得支撐／壓力價資格。
- 獨立審查發現 `unknown`／`N/A`／帶空白的 `unavailable` 能通過的來源漏洞，已先重現 4 個失敗後修正；缺值辨識只使用 strip/lower，原始有效來源字串保留。窄複驗 103 passed，含原 2330／v4 一般／dense 實際 wire 完整還原 120 根、13 技術 facts。最後僅 JSON 縮排精簡由主代理再驗，未把該小修冒稱已受同一獨立審查。
- 首版新來源補齊使 2330／Agent 22／3.5-lite 從 53,344 預估 tokens 增至 66,424、超過本機 64k；單做 record-table 後 65,352，仍超量。最後移除該 financial JSON 的裝飾縮排，完整保留所有欄位與 120 根後降為 52,156，該路由恢復 admission。這是本機 mixed-language estimate，不是 provider tokenizer／實際消耗。
- 最後預算矩陣：12 jobs／369 rows／304 admitted，38 個來源檔 hashes 讀回不變；`/private/tmp/stock-agent-quality-budget-technical-final-20260912.json`，1 passed／14.51 秒。Gemma 完整來源仍超本機 cap，未放寬 cap、未啟用 batching，未宣稱改善 live 成功率。
- 技術來源初版 9 faithful reds；布林／blended 負例 2 faithful reds；表格線路 1 faithful red；來源 sentinel 4 faithful reds。改前 50 個相關 suite 整合 2126 passed／1 skipped／75 subtests、231.45 秒；最後修改後 256 passed／3.29 秒，`/private/tmp/stock-agent-quality-technical-final-scoped-20260912.xml`。12 組凍結 graph／checkpoint／snapshot 再驗 12 passed／12.60 秒，`/private/tmp/stock-agent-quality-frozen-graph-technical-final-20260912.xml`。都是離線驗證，不是正向 live 研究報告。
- 最後 backend 完整 source inventory SHA256：`99e7f1824e79997b092ec1351c310135e08fc97dff529d9a2b75da391effe300`；與預算 probe 的較窄 `.py + agents.json` hash 口徑不同，不能混為同一 hash。scratch graph 安全測試 34 passed／4.12 秒；在本節原紀錄時新實驗未獲啟動，其後的明確授權與實際結果另列下節。
- scoped pattern-only scan 覆蓋 180 個 changed／untracked nonignored 檔案，常見 Google key／private key patterns 無發現；不是完整秘密資料稽核。`git diff --check` 通過。正式 checkout 仍乾淨、HEAD 保持原版本；未 commit／push／PR／merge／部署／重啟，原 pilot、OOS 與正式 artifacts 不回寫。

## 2026-09-12 16:54：明確範圍核准後的技術來源 live 實測

本次只執行使用者明列的單一 2330.TW／v4 隔離實驗，未把剩餘呼叫額度自動轉成其他實驗或 cohort。程式／原始資料／正式路由雜湊逐次核對及完成後讀回均不變；backend inventory 同上。來源、checkpoint、HTTP 與原始公開回應保存在 `/private/tmp/stock-agent-quality-graph-2330-v4-technical-20260912/`，金鑰不在提示或證據輸出中。

- 限額 6 transport calls／6 physical HTTP／240 秒；實際 4 calls／4 HTTP，graph 耗時 8.6169 秒，exit 2。4 次均收到 HTTP 200 header，只有 3 次串流完整；不可把 header 成功當作 4 份完整模型回應。
- 共用可用性 guard 顯示 3.6、3-flash-preview、3.8 暫時 circuit-open，按既有路由跳過；Gemma 在完整來源下仍被 input admission 擋下。4 次實際請求皆為 `gemini-3.5-flash-lite`，provider 回傳同名標籤但不是獨立身分 attestation。沒有解除 circuit 或重置 quota。本次沒有觀察到 429／5xx，不能据此推論其他路由或全日額度已恢復。
- CLI 的 process-only bounded-thinking 實驗仍保留，但此輪未實際呼叫 3.6／preview；Lite 使用既有 low 設定。這不是 thinking policy 的有效 A/B 對照，也未修改正式 source policy。

| Attempt | 角色 | 結果 | 原始輸出核對 |
| --- | --- | --- | --- |
| 1 | Agent 22 | HTTP 200、STOP、完整 JSON | raw schema／完整性通過；32 項數字／來源問題：25 個 token 未獨立成行、4 個來源路徑未解析、3 個未綁定數字 |
| 2 | Agent 23 | HTTP 200、STOP、完整 JSON | raw schema／完整性通過；37 項數字／來源診斷，包含未綁定數字、錯誤來源與無效引用 |
| 3 | Agent 23 重寫 | HTTP 200、STOP、完整 JSON | raw schema／完整性通過；仍有 8 項數字／來源診斷，含不存在的 `institutional_trading.total_net_buy_shares` fact |
| 4 | Agent 22 重寫 | HTTP 200 header、部分串流 | Agent 23 重寫耗盡品質重試後引發 graph 失敗，本份收到 CancelledError；不是已證實的 provider 5xx 或 MAX_TOKENS |

Agent 22 真實 prompt 中完整 120 根計算日線可見；第一份回應使用 24 次技術 fact token，涉及 12 個不同技術指標，這些 IDs 均存在於該輸入 registry，RSI 使用「點」。但引用混在句子中、來源省略 `prompt.`／使用非 exact path，以及裸數字仍未通過。這只證明模型開始使用新來源，不代表 24 次引用可作已接受證據，也不代表完整報告品質合格。

Agent 23 的重寫提示確實帶有首次 37 項診斷的有界樣本與完整修正規則，Agent 22 則帶 32 項；回覆仍未遵循。第二份 Agent 23 輸出由 1519 降到 573 字元、問題數减少，但它仍引用不存在的 fact 並省略不少內容，不能用變短或錯誤較少宣稱品質提升。最終 `AgentQualityDraftError` 阻止進入 Agent 24／正式發布；本次 submission 1、合格完整報告 0，沒有 population success estimate。

實際 usage 的新觀察：Agent 22 第一份以保存的實際 prompt＋system/schema 重算本機預估 52,161 tokens，provider 回報 input 65,778；Agent 23 初次 40,640 對 43,139、重寫 41,730 對 43,787。本機估算不是保守上界，應列為後續校準項，不把 local 64k budget 當成 provider 的硬上限或拒絕證據。缺 reasoning counter 仍為未知，不以 total 差額補零。

讀回驗證：`/private/tmp/test_stock_agent_technical_live_readback.py` 透過同一隔離 runner，在禁止網路／隔離 DB 下使用實際 prompt、原始完整 JSON 與現行 public validators 重驗；1 passed／1.01 秒。輸出 `offline-readback.json` 保留分項診斷及原證據 hashes，沒有新 provider calls，也未變更原始實驗證據。此輪只新增 scratch 實驗／讀回成果並更新本文件，沒有修改 backend 程式。

實驗前後正式 API commit 都是 `758242290e795146520f58f68ffa113cac35e52c`、dirty=false；完成後 readyz=ready，storage／queue=pass，正式 checkout 乾淨。未 commit／push／PR／merge／部署／重啟，也未寫入正式報告或 OOS cohort。

## 有界實驗後續：引用提示、法人型別來源與結構敏感估算

本節是獨立的離線程式續作，不改寫前節失敗結果，也没有新增 provider 請求。完整 backend inventory 為 `068e92ee42d3f60587acdeacbd453003720a93a17cdd3499aa09f8bd75383791`，較廣整合與矩陣執行前後讀回一致。

- Agent 22／23 原任務保留，但正文標題改用定性名稱，明確區分當期指標與跨期變化。啟用數字契約時不再叫模型優先引用未被接受的裸 State 路徑；舊版未啟用契約的 State 指引保留。前序分析不能自證原始事實。
- `canonical_fact_prompt.build_fact_example` 僅從當次角色可用 registry 產生一段 JSON 格式範例；解析後是真換行，fact token 獨立一行，source_refs 用相同 exact fact_id。無相容事實就不提供範例，範例不是完整報告、不建立 accepted receipt，不代替反證、時點或研究內容。原本的 inline token、雙重跳脫換行、裸路徑、自創 ID 仍拒絕。
- `canonical_chip_facts.py` 以真正 FinMind producer 的契約介接法人數據。在 2330／v4 保存資料建立 15 項 reported facts：全觀察窗合計與三個分類、最近五個已觀測日期合計、十個逐日合計。保存 raw source 與 model-visible 完整記錄、SHA256、觀測窗、凍結日期與四捨五入精度；千股只換算一次，精度限制也進入實際顯示。
- 法人資料是來源彙總，不是原始 buy/sell rows 的獨立重播；未保存全觀察窗逐日資料時不補造起始日。全窗分類值不能當作最近單日／五日分類流向。未知／未來 cutoff、過期收據、單位矛盾、缺欄位、錯序、極值、非數字／布林與 malformed trend 均 fail closed。真 producer 的 NumPy float64 在離線 DataLoader double 下有驗證，不是 live FinMind fetch。
- TDCC 缺原始分級 rows／邊界、MI_MARGN 缺可驗證日期／單位的部分明列 unavailable；原始內容仍在 prompt，不刪資料。既有 TWT93U 借券來源介接保留。這些限制不因增加法人 facts 就消失。
- 七筆已保存且完整的 graph provider 回應涵蓋 Agent 22／23 與三個 Gemini 路由，舊估算比明示 input usage 低 4.7–20.7%。`llm_input_capacity.py` 為 JSON 分隔符號／跳脫字元保留結構餘量，其餘 prose 計量不乘全域倍率；在這七筆同來源樣本中，新估算高於 usage 約 4.7–18.0%。這是已見樣本的離線校準，不是獨立 holdout、provider tokenizer 或未知輸入的上界保證。`/private/tmp/test_stock_agent_request_estimate_readback_20260912.py`：1 passed／0.11 秒，原 evidence hashes 不變。
- 沒有提高任何 input cap、TPM／每日額度、output cap 或改 thinking policy；沒有剪除來源、放寬 gate 或啟用 Gemma。真實 provider 成功率與完整報告品質尚未確認。

驗證與限制：

- 法人 adapter 的 55 項隔離測試通過；包括實際 formatter 的四種 compact／dense 組合，以及 producer 的短、中、完整觀察窗。協調者檢查實際 source、producer 與測試，提出並修復極值、凍結 cutoff、顯示精度及非字串 trend 問題。
- 協調者完成 prompt→registry→數字驗證→graph／publication／decision／架構的 270 項整合測試，3.22 秒；`/private/tmp/stock-agent-quality-citation-chip-estimator-scoped-20260912.xml`。真實 Agent23 prompt 的一般 Gemini／dense Gemma 接線先得到兩個 faithful red，再通過；沒有以 helper 單测冒充 runtime 接線。
- 同一 backend inventory 的 56 檔較廣回歸完成：2,801 passed、1 skipped、75 subtests passed、0 failed／errors，242.15 秒、exit 0；`/private/tmp/stock-agent-quality-citation-chip-estimator-integration-20260912.xml`。JUnit 合計 2,877 包含子測試與跳過。唯一 skip 為需要明確提供離線 checkpoint DB 的 optional replay。程序退出時另出現一則隔離 SQLite connection 的 ResourceWarning，來源未進一步定位；不把它改寫成無警告，也不是正式 DB 故障證據。本次未再跑全庫，先前全庫紀錄保留其版本與限制。
- 獨立唯讀覆核 root 的 prompt／example／estimator 改動未見 material finding；23 tests passed／1.69 秒，兩個核心檔案 hashes 與協調者讀回一致。未把代理對自己 adapter 的單測當成獨立審查。
- 十二個原始凍結資料經真 graph、audit、checkpoint、snapshot：12 passed／13.09 秒；`/private/tmp/stock-agent-quality-frozen-graph-citation-chip-estimator-20260912.xml`。provider 仍為明示離線 double，不能計成十二份真實研究報告。
- 新容量矩陣：12 jobs／369 rows／278 admitted，38 份原始來源 hashes 讀回不變；1 passed／18.15 秒，`/private/tmp/stock-agent-quality-budget-citation-chip-estimator-20260912.json`。目前 configured 且非 deterministic-skip 的 69 個 job/agent 位置皆至少有一條輸入預檢可接受路由；不代表 provider 當下可用。
- 矩陣相對前版有 26 個 Lite 路由列改為 local budget rejection，包含部分 historical-only 路由，不能混為 26 份新失敗報告。2330／v4 Agent22 Lite 估算 78,633 超過 local 64,000，三個較大 Gemini 路由仍 admitted；Agent23 Lite 58,550 admitted。不是用恢復舊低估或提高 cap 維持可送數。該矩陣仍使用歷史前序分析、無新 RAG，不能預測新 graph 的確切 usage。
- 預算 probe 的較窄程式指紋現在包含所有 `backend/prompts/*.json`，補上原本未涵蓋的 runtime_rules；仍不同於完整 backend inventory。此前證據不回寫、不覆蓋。
- `git diff --check` 通過；184 個 modified／untracked nonignored 檔案的常見 Google key／private-key pattern-only scan 無發現，未輸出匹配內容；不是完整秘密資料稽核。
- 正式 API 唯讀回查仍為原 SHA／dirty=false、readyz ready、storage／queue pass；既有 failed 12 與 watchlist scheduled 23 保留，未介入送件。未 commit／push／PR／merge／部署／重啟；四模式 paired live、跨產業／日期 cohort 與正式發布驗收仍未完成。

## 後續驗收補強：未評估分類、凍結日期及舊快取

此節是原 P0-1／P1-3 的本機續作，沒有新增 Gemini 呼叫；先前單次 6-call／4-minute 授權已於上述實驗結束，不將餘額視為另一個實驗的授權。backend inventory 為 `9cbc554626f1fb32e14ed587d21a91401e2aa6ec17dc5a39b075a434b8baf2ff`；較早章節的驗證仍只適用各自版本。

- 獨立驗收以真角色品質流程重現：Agent 22 完整 JSON 明示 `confidence=unassessed`，沒有 unavailable token 時，仍得到 `passed`／`verified_no_action`。新判定只讀 schema 的未評估宣告與推薦信心 `N/A`（含合法別名），保存 `research_availability` 的 exact path／reason；不靠全文關鍵字，也不把缺評估冒充缺少一筆數字。低信心與合法數值零不等於未評估；原始 schema 不接受的 null／N/A confidence 仍拒絕。
- 未評估 upstream 可保留完整安全觀望診斷，但不計完整研究成功，不保存 validated cache；若最後仍提供可採用交易，既有關鍵來源不足 gate 繼續阻擋。低信心、有證據的合法研究仍可重用快取。來源、raw payload、verified fact counts 及數字缺值分母不回寫。
- 另一重現為凍結 `fetch_date=2026-09-12`，model `as_of_date=2099-01-01` 仍通過且渲染成資料時點。新 `generation_observation_dates.py` 在 generation、final audit 及 partial rerun 以凍結日期為上限；不引用執行／重播當日。具體日期沒有已知 cutoff 就拒絕；明示資料時點未提供保留 unavailable／diagnostic，不補造日期。
- 這只是 `not_after_frozen_fetch_date` 上限檢查，不宣稱已驗證實際來源發布日或 freshness；各 fact 原有期間與來源時效仍獨立。早於 cutoff 的研究日期不任意改成新日期，future `next_catalysts.date` 仍按事件日期處理，不套用資料觀測上限。歷史 reader 沒有新生成 marker 時不重新標成合格或修改原 artifact。
- 新舊收據都必須面對目前宣告規則：cache admission 與 role `numeric_quality_status` 不再只信舊 `passed`；局部重跑重驗來源與輸出後再核對資料 cutoff。重綁 hash 不能讓未來資料日期進入部分重跑，該情況回覆 HTTP 409、要求完整重跑。

本輪證據：

- 未評估分類 13 個 faithful reds 後修正；日期初版 29 failed／2 passed，包含 7 個 dated evidence roles 的未來資料日期、未知 cutoff、final-audit 繞過及缺少新 helper。後續 cache／partial-rerun 五個 faithful reds 另重現後補齊；沒有以跳過失敗冒稱驗收完成。
- 日期、研究可用性、raw schema、publication、fallback、partial rerun、graph 共 171 passed／4.05 秒；`/private/tmp/stock-agent-metadata-cache-scoped-20260912.xml`。一次前置執行的測試缺 import 為 170 passed／1 failed，修正 test import 後同組重跑通過，沒有更改產品判定來迎合測試。
- 獨立唯讀 review 核對資料日期 helper、runtime／final／cache／partial-rerun 接線，未見 material finding；7 suites 共 167 passed／3.50 秒，核心 source hashes 與主代理讀回一致。另補 workflow quality draft resume／cold import 與報告品質可觀測性 API／frontend 53 passed／6.83 秒，`/private/tmp/stock-agent-metadata-resume-observability-20260912.xml`。不把既有離線測試當成正式 UI 或 provider 成功率證據。
- 12 組原始凍結資料的 graph／audit／checkpoint／snapshot 為 12 passed／12.93 秒；`/private/tmp/stock-agent-metadata-frozen-graph-20260912.xml`。provider 是明示 offline double，不是十二份真實合格研究報告。
- 同版容量 probe：1 passed／17.59 秒，12 jobs／369 rows／278 admitted、69 個非 deterministic-skip 的 configured job/agent 位置均至少一條 admission；`/private/tmp/stock-agent-metadata-budget-20260912.json`。38 份來源 hashes 不變，正式 routes hash 保持 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`。input admission 不是 provider 可用性或報告品質證明。
- TDCC producer 的原始分級保留與缺值解析另有待處理；本輪沒有在官方分級邊界未核對前改統計口徑，也未將旧凍結彙總升級為可核驗分級來源。不能將本輪兩個漏洞修正說成所有可本機執行項目已完成。
- 正式唯讀回查維持原 SHA `758242290e795146520f58f68ffa113cac35e52c`／dirty=false，readyz ready、storage／queue pass；failed 12／watchlist scheduled 23 保留。未 commit／push／PR／merge／部署／重啟，未改正式 DB、Gemma dark launch 或 OOS cohorts。新版本的正向 live 報告、四模式 paired live、跨產業／日期 cohort 及發布驗收仍未完成。

最末版本核對：

- 上述 `9cbc554…` 同版較廣 58 檔回歸完整結束：2,873 passed／1 skipped／75 subtests passed、0 failures／errors、241.85 秒，`/private/tmp/stock-agent-metadata-integration-20260912.xml`。JUnit 2,949 含子測試與唯一 optional checkpoint replay skip。退出時仍有一則隔離 SQLite connection ResourceWarning，未進一步定位；不是正式 DB 健康故障判定。
- 主代理最末逐欄 review 另重現推薦信心的 `unassessed`／`資料不足`／`資料時點未提供`（兩個 alias 共六個 faithful reds）；它們原本已能通過 typed-metadata/schema，不應只因未填 N/A 就升級為完整研究。窄修同一 helper，完整涵蓋既有缺值標記，reason.value 保留原文，未放寬 raw schema。
- 此最末 backend inventory 為 `8f622104dbe9e68f2b93388c771b1bb38100be1d4042bc3a3c7ee82318fc682b`，上述 2,873 項較廣回歸早於此 tuple 小修；不冒稱同一完整 run。最末差異及 generation／publication／graph／品質可觀測性共有 206 passed／3.96 秒，`/private/tmp/stock-agent-metadata-final-scoped-20260912.xml`；独立窄審核 35 passed／1.80 秒、無 material finding，source hash `e6546a3aa0af2399ffe9b406917a42b86b5c058647e4d004adbd00a3729c60a4` 與讀回一致。
- 最末 inventory 再驗原始 12 組凍結 graph：12 passed／12.53 秒，`/private/tmp/stock-agent-metadata-final-frozen-graph-20260912.xml`。容量 probe 1 passed／17.28 秒，仍為 12 jobs／369 rows／278 admitted、38 份來源 hashes 不變；`/private/tmp/stock-agent-metadata-final-budget-20260912.json`。均無 provider 呼叫。
- 開發工作樹共 187 個 modified／untracked nonignored 檔案，包含此前已授權且未提交的工作；非本輪新增 187 檔。pattern-only Google key／private-key scan 未發現匹配，`git diff --check` 通過；不是完整秘密資料稽核。

## TDCC 來源、持股邊界與成功計數補強

此批接續原 P0-2／P1-4；沒有增加 Gemini 呼叫，沒有替原凍結資料補入新公開來源。既有單次限額實驗仍是 4 次呼叫、8.6169 秒、3 份完整 JSON、0 份合格完整報告。下述公開 CSV 取回與離線重播不是新的模型實驗。

### 修改與證據口徑

- `chip_data_fetcher.py` 的 TDCC 入口不再將空值、`--`、NaN 或解析錯誤轉成零。六個原始欄位均保存字串，完整 17 級原值、來源 digest、單位與 source-contract v1 一起保存；缺級、重複級距、錯誤股數／人數／比例或不能對帳均 unavailable。資料庫外層 `ChipDataProvider` 保留失敗原值；`source_record_count` 只計成功來源，錯誤物件有內容不等於成功。
- 官方第 8 級包含 50,000 股，因此新增 `retail_holders_le_50_lots_pct` 表示「50張以下」；嚴格小於邊界的舊 `retail_holders_lt_50_lots_pct` 在新來源維持 null。第 15 級為超過 1,000,000 股。兩個比例都由所選原始股數除以第 17 級合計重算，百分比小數四位、ROUND_HALF_UP；不相加官方已公布的小數比例。官方定義見[分級附件](https://schema.nat.gov.tw/gsp/frontstage/resource.download/9f7d9184-20a0-49eb-b7dd-96e23686c4ef)，附件 SHA256 `e0687f68e9a119fcf18589fdeea8630312658412650f03691c9974c9b8b2ecb8`。同版歷史適用期間與 provider 百分比捨入政策未獨立核證。
- 首次全市場公開檢查找出我方初版調整加號假設有誤：2,955 個四位數代碼候選中 48 個不能對帳。1101 實際前 15 級合計 7,523,189,741 股、差異 7,999 股、合計 7,523,181,742 股，支持固定減法而非加法；2303／2317 亦同。新式固定為 `sum_grade_1_to_15_shares - grade_16_shares = grade_17_shares`，不逐筆挑符號以求通過；第 16 級人數不另加到持有人合計。原始 signed adjustment 與「符號適用歷史未獨立核證」限制仍保存。
- `canonical_tdcc_facts.py` 重算實際 role prompt 可見的完整資料，核對 ticker、日期、單位、source URL、digest、row count 與全部計算收據，再以凍結 `fetch_date` 為上限。只有兩個 derived holding-ratio facts 可引用，`calculation_validated=true`、`decision_validated=false`；不產生持股變化、主力進出或交易價格。低階純 replay 不依賴當天時鐘，抓取層另外記錄 Asia/Taipei 當次 cutoff 並拒絕未來資料。
- 經獨立審查另修正重複 CSV 表頭被 pandas 自動改名而挑到任一值的漏洞。解析前檢查唯一表頭及行寬；失敗保留 response-text digest 與有界 header。只有 ticker/date 唯一時才保留該檔該期 cell arrays，最多 128 列／64 KiB；無法唯一選取時只留原因，不能把全市場 CSV 塞入提示。requested date 只接受 date/datetime、YYYYMMDD 或 YYYY-MM-DD，格式不符於 HTTP 前拒絕。
- UI 使用「50張以下持股（股數重算）」與「逾千張持股」，並保留 legacy「歷史小戶比例（口徑未核驗）」。新版 null／unavailable 不借用舊 alias，JS 不將 null／空字串／boolean 變成 0；真實零可正常顯示。快照仍保存完整 raw source，不回寫歷史 artifacts；對應本機 asset cache-bust 已更新，尚未部署。

### 最末驗證

最末 backend inventory：`71cbb03cb40f4d5e958e6e1eb503a214f81fe0b7e187718bee4d1cff39756929`。API／操作指南／架構與本紀錄同步，但下列程式指紋不含 docs。

- RED → GREEN 證據涵蓋缺值原值保留、provider wrapper 丟資料與錯算成功、canonical 可見性、日期／CSV 歧義、固定差異減法、實際 Agent 23 prompt/parser、總計百分比不誤用小數容忍。首輪相關整合 930 passed／1 failed：舊測試把無狀態的 `{"major":42}` 也要求計為來源成功，已將測試改為讀值保留但成功數為零；沒有為了通過測試恢復誤算。
- 同版 31 檔相關回歸：**933 passed／19.30 秒**，`/private/tmp/stock-agent-tdcc-final-integration-20260912.xml`。包含來源可信度、角色 routing、canonical、generation、partial rerun、graph、snapshot、JS、架構等；不是全庫或 provider 測試。
- 公開 CSV 共 68,935 列，資料日期 20260911，全文 SHA256 `cbb1fefcf39e7f9c88298065340992913075bb2048273e5b58667aa61e45f048`；更正後 **2,955 個四位數代碼候選全數算術核對通過**，其中 48 組有非零差異。原始公开檔 `/private/tmp/stock-agent-tdcc-public-source-20260911.csv`，結果 `/private/tmp/stock-agent-tdcc-public-source-reconciled-20260912.json`。此候選集合不宣稱為獨立核定的完整股票類別清冊。
- 2330：原始小數級距加總 8.76 不等於按股數重算的 8.7946；大額持股重算 84.8245。原始字串與兩种精度口徑保留，不能將系統重算冒稱 provider 直接回傳。2330 的完整 producer → 四角色（15／18／23／24）及四個 compact/dense 組合 → registry → Agent 23 application quality → snapshot／實際 JS 已重播；未使用 live LLM。最末再驗公開全表與 1101／2330／2882／8069：**8 passed／2.48 秒**，`/private/tmp/stock-agent-tdcc-final-public-replay-20260912.xml`。
- 獨立唯讀 review 在指定 canonical/source/wrapper 範圍未見 material finding，54 passed／2.58 秒；主代理另補總計必為 100% 的兩個 faithful reds 並修正，已涵蓋於上列最末回歸與公開全表檢查，不將最末窄修冒稱經同一獨立 review。
- 原 12 組凍結資料 graph／audit／checkpoint／snapshot：**12 passed／12.75 秒**，`/private/tmp/stock-agent-tdcc-final-frozen-graph-20260912.xml`；明示 offline double，不是十二份合格真實研報。容量 probe **1 passed／17.29 秒**，仍是 12 jobs／369 rows／278 admitted／91 rejected，38 份來源 hashes 不變；`/private/tmp/stock-agent-tdcc-final-budget-20260912.json`。routes SHA256 維持 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`。
- 開發工作樹共 204 個 modified／untracked nonignored 檔案，包含此前未提交工作，非本批新增 204 檔。`git diff --check` 通過；pattern-only Google key／private-key scan 無匹配，未讀取正式 `.env`，不是完整秘密資料稽核。
- 正式 checkout 仍是 clean main `758242290e795146520f58f68ffa113cac35e52c`。本次實際監聽綁定本機 LAN 位址，不是 loopback；依 `lsof` 找到位址後，`readyz` 回覆 ready、storage／queue pass，runtime identity 同 SHA／dirty=false，failed 12／watchlist scheduled 23。未操作這些工作，未 commit／push／PR／merge／部署／重啟，未更動正式 DB、Gemma dark launch 或 OOS cohort。

### 尚未完成

TWSE MI_MARGN 的獨立日期／單位原始證據介接仍未完成，不能借 TWT93U 借券日期替代。新版本的正向 live 報告、原四模式 paired live、跨產業／日期 cohort 與正式發布驗收亦未完成。這批完成 TDCC 來源品質修正，不代表所有優化完成或模型報告成功率已改善。

## TWSE 融資融券來源與獨立日期介接完成

本節接續上節仍未完成的 MI_MARGN 來源 slice，對應原 P0-2／P1-4。只修改隔離開發工作目錄；沒有新增 Gemini 呼叫、重開先前單次限額實驗，或向原凍結資料補入新來源。

### 原因與修改

- 舊 [MI_MARGN OpenAPI](https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN) 20260912 取回的 1,297 列沒有資料日期，2330 幾個零值欄位回傳空白。不能把另一份 TWT93U 日期當作其日期，也不能推定空白等於零。公開 capture SHA256 `19f71da444fa4474b5c6c2666f79487e0b85a45e3616d4df1d9f816087bee5f5`。
- 改接 [有日期的 MI_MARGN STOCK 報表](https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=STOCK)。已讀回 `stat=OK`、`date=20260911`、標題 `115年09月11日 融資融券彙總 (股票)`；1,063 列含一個合計列、1,062 個證券，並非 1,063 支普通股。STOCK 的確排除 ALL 中 235 個代碼（包含 ETF），但仍有七個 DR；本 adapter 只接納四位、非零開頭且非 DR 候選，不宣稱已核定完整股票類別清冊。
- 中文表格的買進、賣出、前日／今日餘額有重複欄名。`twse_margin_source.py` 同時驗證 16 個欄位位置、groups、日期與標題，不用 dict(zip) 覆蓋同名欄；只保存所選證券原始 cell arrays、notes、schema、獨立日期及 hashes，最多八列／16 KiB 診斷證據，不將全市場資料塞入提示。
- `margin_as_of_date` 是融資自己的日期，`borrowed_short_as_of_date` 是借券自己的日期；舊 `as_of_date` 僅留作借券 alias。`margin_status`／`borrowed_short_status` 分開，外層 `success` 只表示至少一份來源可用。融資失敗仍可取得借券；非法市場／代號與融資特定單位適用範圍分開，不能因融資未支援 ETF／DR 而把既有借券資料丟棄。
- 股票交易單位換算依[營業細則第 60 條](https://twse-regulation.twse.com.tw/TW/law/DAT0201.aspx?FLCODE=FL007304)，融資與融券群組使用交易單位亦由[英文正式報表](https://www.twse.com.tw/rwd/en/marginTrading/MI_MARGN?response=json&selectType=ALL) 核對；英文 capture SHA256 `7e5f45b402fcd30dda1c2a99bc6129e68e4fe0745f7bff071d97a482aaf42c39`。原始十個流量／餘額欄保留整交易單位，canonical fact 才乘 1,000 成股數；記錄 source precision，不補造逐股精度。借券原值已是股数，不再乘千；本次沒有將既有 TWT93U adapter 升級為完整原始來源品質收據。
- `canonical_twse_margin.py` 重播實際角色可見的原始列，核對 source URL、version、units、digest、衍生值、自己的資料日與凍結 `fetch_date`。缺值不由等式補零、分數／非數字／布林不截斷或強制轉換。完整數值須同報表對帳；不再扣一次資券互抵，不補造公司事件調整。這是內部算術一致性，不是跨日買賣量、公司行動或歷史單位版本證明。
- 「前日餘額」標示為當期報表列示值；[官方統計說明](https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=MS) 指出後續調帳，因此不能冒充獨立核對的前一天快照。互抵欄位不在英文 trading-unit groups 內，未另有充分單位證據，不建立股數 fact；次日限額也不當作當日餘額。停止融券註記不推論成特定公司事件。所有新 facts `decision_validated=false`，單次餘額不產生趨勢／交易訊號。
- 快照與真實 JS 不再把融資缺值顯示成 0 張，真零仍保留；融資資料日不回退到借券日期，歷史數值加上「歷史口徑未核驗」。不回寫歷史 artifacts，asset cache-bust 已更新但尚未部署。

### 同版驗證與限制

最末 backend inventory：`393a3af016ad7c5dfa689c676d713ec77f1f169119a5d62f45c3e66ff63ed6db`。本節與 API／操作／架構文件同步；程式指紋不含 docs。

- 初始相關基線 85 passed。來源契約先有九個 faithful reds；實際 prompt／numeric gate 十個預期 reds；UI 有八個日期／缺值 reds。中間一次 numeric 綠測有 126 passed／1 failed，是測試誤要求 formatter 的千分位逗號，依實際既有輸出文法修正測試，未改品質判定。
- 獨立唯讀 review 重現兩類 P2／四個 reds：共用入口 scope 誤擋借券、非空但缺日期／數值的借券物件誤計成功。修正後原資料保留，availability 須有有效非未來日期且至少一個可用整數（真零有效）；registry／snapshot 尊重新來源失敗狀態，legacy 缺 status 保留相容。獨立最末窄審查 **161 passed／3.07 秒**，未見新增 material finding。受審 chip fetcher SHA256 `0db22b02053a0266dd8e216d0207a03dd2e72b5090c599b041c516b31ab197bd` 與主代理讀回一致。
- 最末 35 檔受影響整合：**875 passed／7.76 秒**，`/private/tmp/stock-agent-margin-final-integration-20260912.xml`。含 TDCC／借券相容、實際 Agent 23 prompt/parser、數值 gate、generation、partial rerun、graph、snapshot、JS、資料信任與架構；不是全庫或模型測試。
- 公開 STOCK capture `/private/tmp/stock-agent-twse-margin-contract.qH2Tsk/mi-margn-rwd-stock.json`，SHA256 `706990f882046bff884b265226787e6cf809aa8ed443cbf6be70878766a12c3b`。**1,055 個適用候選全部同報表算術核對通過**；排除合計與四個長碼、三個四碼 DR。2330 原值融資今日餘額 `28,901`、融券今日餘額 `0`、註記 `X ` 皆原樣保留；只將有單位根據的融資值換算成 canonical 28,901,000 股。
- 公開 2330 → 四角色／四種 compact-dense → registry → snapshot／真實 JS，以及獨立公開 1101／2330／2882 producer/prompt 正控制已通過。主代理最末含原 review 重現檔與 public replay：**113 passed／4.34 秒**，`/private/tmp/stock-agent-margin-review-green-20260912.xml`。日期差異、其他證券排除、缺值與錯單位均有反例；沒有 live LLM。
- 原始 12 組凍結 graph／audit／checkpoint／snapshot：**12 passed／12.94 秒**，`/private/tmp/stock-agent-margin-frozen-graph-20260912.xml`。容量矩陣 **1 passed／17.23 秒**，12 jobs／369 rows／278 admitted、91 rejected；38 份來源 hashes 未變，routes SHA256 仍 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`。JSON：`/private/tmp/stock-agent-margin-budget-20260912.json`。該 probe 的 python/prompt-only code manifest digest 為 `a5a596b77a97cbf2e79622b6953f191e983090086d4de1d72846d52c917fdadf`，與包含 static assets 的 backend inventory 算法不同。
- 另外只在記憶體副本加入新公開融資來源，確認新增證據後的實際 2330/v4 容量：**1 passed／2.25 秒**，`/private/tmp/stock-agent-margin-new-source-capacity-20260912.xml`。Agent 23 三條 Gemini 路由 admitted、Gemma 及 lite 因既有限額 rejected；Agent 24 三條 admitted。沒有提高上限或刪證據。這是來源增補副本，不能冒稱原封不動的凍結矩陣或 provider 可用性證明。
- 最末開發工作樹 210 個 modified／untracked nonignored 檔案，含前批未提交工作，非本批新增 210 檔；`git diff --check` 通過。正式 checkout/runtime 仍 clean main `758242290e795146520f58f68ffa113cac35e52c`，readiness ready、storage／queue pass；failed 12／watchlist scheduled 23 原狀保留。沒有 commit／push／PR／merge／部署／重啟、正式 DB 或 OOS cohort 操作，未變更 Gemma dark launch。

本批完成 MI_MARGN 來源 slice。新版本正向 live 報告、原四模式 paired live、跨產業／日期 cohort 與正式發布驗收仍未完成；目前沒有新增模型報告成功率證據，不能宣稱全部優化完成。

## 原計畫逐項驗收：發布完整性、DCF 正向路徑與模型身分

本輪不是新增另一份優化計畫，而是核對原 P0／P1 的整合接點。發現並修正四類會使報告或觀測失真的缺陷：

- **重複 JSON 欄位遮蔽原始主張**：解碼後同一 object 的 key 必須唯一，包含 nested source_refs、相同值及 Unicode escaped key。不能用後一個正文覆蓋前一個錯誤數字，再讓品質 gate 只看到合法版本。完整 fence、正文中的 JSON 字樣及不同 evidence object 的同名欄仍合法；真實品質重寫與 validated cache 邊界一併核驗，歷史 reader 不改寫。
- **可變 Agent 清單繞過模式完整性**：新版 final audit／publication gate 以 `pipeline_modes` 的固定角色為準；`agent_sequence` 缺省可用 canonical default，明示值必須精確相同，不接受刪減、重排、重複或錯型別。所有 required role 的來源收據都要檢查，分母只計各角色一次。真實 renderer 不能發布只保留 Agent 24 而缺 Agent 22／23 的 v4；legacy 無新版 marker 的讀取不重分類。
- **合法當期 DCF 被舊 quant 轉換覆寫**：Agent 4／14 只有當本輪 raw／normalized／input 收據成立且三情境逐參數重算一致時，保留 current_intrinsic 結果及 parameter_inputs。選填的 row source 必須是同一個 intrinsic price 收據。Final audit 使用同一當期計算核對每項 structured／正文主張，不拿舊 quant 的另一套數字覆寫或比較，也不略過正文；沒有方法證據的「正規化 DCF」名稱仍拒絕。當期內在價值不提升為未來／交易價格。
- **模型身分跨失敗／重試不一致**：內容品質失敗不抹去已觀察到的 provider response 身分；新 `llm_model_call` 或 provider request 開始後，清除前次回應／版本／usage，但保留 route history。API/store 現保留未送出的 attempt，snapshot 保留 resolved-only 狀態；沒有當期回應時報告 model_id 是 unknown，不能借用舊模型或品質通過。

### 本輪已核對的局部證據

- JSON 邊界先 **8 failed／2 passed**，修後含品質重寫／cache：四檔 **106 passed／2.17 秒**；`/private/tmp/stock-agent-json-members-green-20260912.xml`。
- 模式範圍先 **15 failed／4 passed**，修後六檔 **94 passed／3.41 秒**；`/private/tmp/stock-agent-agent-scope-green-20260912.xml`。中間一次測試錯把既有 final audit 狀態預期為 blocked，實際契約是 needs_attention＋critical；只修正 assertion，真實 renderer 拒絕發布仍由例外驗證。
- JSON／範圍獨立唯讀審查五檔 **129 passed／2.47 秒**，六個受審檔 hash 前後不變，指定範圍無剩餘 material finding。
- DCF runtime 兩個、final audit 兩個、row-source 三個及 normalized prose 一個 faithful red 已轉綠；十檔 **219 passed／3.64 秒**。主代理檢視實際程式與所有新增正負例，讀回四檔 hashes 與交付一致。這只證明合法估值角色的接點，不是全模式完整報告成功。
- 模型生命週期先 **8 failed／1 passed**，修後原兩個獨立重現也通過。主代理八檔 **88 passed／2.84 秒**；`/private/tmp/stock-agent-identity-lifecycle-integration-20260912.xml`。本次修正不代表 provider 內部模型版本已被獨立驗證。

原 P1-2 的「恢復後最終完成率」另確認為程式缺項，而非只有 live 證據尚缺；本輪已補上有明確恢復觀測點、分母與截止時間的唯讀投影，詳見下節。原有 15／30／60 分鐘完成率、共享 cooldown 及 checkpoint 證據保留；本輪沒有實測正式 Redis 跨程序 cooldown，也未新增恢復後 live 完成率證據。

### 當期 DCF 方法旗標補驗

主代理再檢查「保留合法當期 DCF」時，發現普通 FCF 的收據雖有 `base_fcf_note=latest available FCF`，原稿仍可宣稱 `uses_normalized_fcf=true`。Agent 4／14 真 runtime 兩個反例確認 accepted=true 且 decision issues 為空；不是模型真實執行結果，而是既有程式輸出邊界的正向誤放。

- 共用 `valuation_receipt_errors` 將 WACC 與正規化 FCF 分開。正規化必須由同一 current price receipt 的具體 calculator 政策、實際消費歷史来源、單位／年度／subject、成長與 FCF/淨利條件證明；不能只憑 current DCF 可用就放行旗標。
- 在原始 payload 驗證時拒絕不實宣告，保留 raw payload，不事後改旗標洗成通過。普通 FCF 的正向 fixture 明示 false；真正 calculator 觸發「淨利 80%」政策的 Agent 4／14 保留 true 正向案例。當期值仍不產生未來／交易目標。
- 先取得 **11 個 faithful reds**，修後相關 **177 passed**。擴大回歸曾為 **615 passed＋75 subtests／1 failed**：`test_decision_tool_lineage.py` 的普通 FCF fixture 仍明示 normalized=true。主代理核對真 source note 後只修正 fixture 並新增 note 斷言；最末整合已通過，沒有放寬實際 validator。

### P1-2 恢復後完成率：事件、store、API 與畫面

`modes[vN].provider_recovery` 為 additive 唯讀投影，口徑是同 job／Agent／route 的 request → 明確 availability error → scheduled workflow_retry → 再送出並取得完整非 cache 傳輸回應。`workflow_retry` 目前不帶 Agent；多個失敗角色無法唯一綁定時保持 unknown，不從 error message 猜測。

- 完整短文或 MAX_TOKENS 可以是傳輸恢復，但不能當內容合格；partial stream、其他 route／Agent、cache、預檢跳過不能冒充恢復。內容處理拒收另列 `content_rejected_recovery_jobs`。
- 已觀測恢復的 distinct jobs 是分母，pending／failed／cancelled 不剔除；未觀測恢復與未能綁定的 retry jobs 另列。發布率與完整研究率分開，後者只含 `verified_research`／`verified_no_action`，不含安全診斷或有資料限制的研究。這是截至 cutoff 的結果，不是 provider 全站恢復或保證最終完成。
- 日期未知、事件截斷、實際 malformed、最新發布品質未知都不能借舊分類。未知時間的 DB event 不在 SQL cutoff 階段偷偷丟棄，而須進入 bounded sample／total 使品質率保持未知；有限且已知的 cutoff 後事件仍排除，查詢仍 read-only，未移除 LIMIT 或放寬 job／phase 篩選。
- API／操作／架構文件及實際 JS 已同步；UI 分開顯示恢復、發布、研究合格、等待／失敗及未知證據，未部署。
- 初始 API 缺項取得 **32 reds**，後續補 malformed／舊分類／stale failure 等負例；主代理十檔含真 runtime-event → API projection → Node JS：**156 passed／3.05 秒**，`/private/tmp/stock-agent-recovery-integration-20260912.xml`。
- 獨立審查以真 SQLite schema 重現兩個未知時間被 SQL 濾掉的 reds。主代理新增持久化測試（2 reds／2 正控制）並修正；含原 scratch 的五檔 **79 passed／2.52 秒**，`/private/tmp/stock-agent-recovery-store-green-20260912.xml`。獨立修復覆核 **55 passed／2.25 秒**，驗證原反例、cutoff 等值、有限 future、其他 job／phase 及 LIMIT／total；該 finding 已解決，source hash 前後一致。

### 最末同版整合與未完成範圍

- backend inventory 測試前／後一致：`e8c06fab993da700631b9d94a6b7f515f85944488c205f794817c202ef4f325f`。程式已停止變動後才執行本節整合，文件不在此 backend 指紋範圍內。
- **49 檔：913 passed＋75 subtests passed／10.42 秒，0 failed**；`/private/tmp/stock-agent-plan-acceptance-integration-20260912.xml`。含上述新契約、DCF 方法、決策／raw schema／repair、checkpoint／draft、模型身分、恢復率與 JS、發布／歷史讀取及 AGENTS 要求的 runtime／storage／架構檢查。這不是同版全 repository 或 live provider 測試。
- 原始 **12 組凍結 graph／audit／checkpoint／snapshot：12 passed／13.07 秒**；`/private/tmp/stock-agent-plan-acceptance-frozen-graph-20260912.xml`。輸出仍是離線診斷，不算新增模型研究成功。
- 離線容量矩陣 **1 passed／17.78 秒**；12 jobs／369 rows／278 admitted、91 rejected，38 份來源 hashes 未變。`/private/tmp/stock-agent-plan-acceptance-budget-20260912.json`；python/prompt-only manifest 為 `8fc531c85643a0855a8e4b76fb0cc5b8bc8a07b31841d89bb7310b486d6be077`，routes SHA256 仍為 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`。輸入預檢不是 provider 可用性或品質成功率。
- 開發工作樹共 220 個 modified／untracked nonignored 檔案，包含前批工作，非本輪新增 220 檔。`git diff --check` 通過；正式 checkout 再讀仍 clean main `758242290e795146520f58f68ffa113cac35e52c`。本輪沒有 Gemini 呼叫、金鑰／`.env`／正式 DB 讀寫、Git mutation、cohort 送件或服務重啟。

這批程式缺陷與 P1 觀測缺項已完成局部及整合驗證。**整體計畫仍未完成**：新版正向 live 報告、12 組同輸入 paired live、每模式至少 30 次跨產業／日期 cohort、DCF 新財報 producer 的公開 live fetch／公告時點、正式發布及 canary 均仍須完成或明確補足證據。本節整合完成時，先前單一 6 calls／4 分鐘 Gemini 實驗已結束（實際 4 calls、8.62 秒、0 合格完整報告），沒有把剩餘兩次重用為新實驗；之後新取得的授權與結果另記於下節。

## 新一輪明確核准的隔離測試（2026-09-12 22:20，送出前阻擋）

使用者本輪明列核准：將 2330.TW／v4 凍結研究資料與提示送至既有 Google Gemini 路由，現有金鑰只供驗證，最多 6 次呼叫、4 分鐘。本輪並非重用先前剩餘次數。

- 原始 source SHA256 仍為 `cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd`；backend inventory `e8c06fab993da700631b9d94a6b7f515f85944488c205f794817c202ef4f325f`、routes SHA256 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a` 均前後不變。沿用既有 process-only bounded-thinking 對照，不改正式 output cap／route／品質門檻；本輪無 provider dispatch，因此不是 thinking 效果證據。
- 測試前只補強 scratch HTTP 邊界：明文或 JSON Unicode escape 的金鑰出現在任何 request body 即中止；驗證 header 保留正常作用，不保存金鑰。新增測試先 **4 failed／1 passed**，修後與既有真 SDK MockTransport、quota／socket／DB／取消／發布安全測試合計 **39 passed／4.25 秒**，`/private/tmp/stock-agent-live-harness-preflight-20260912.xml`。這是防護測試，不是 live 成功。
- 真實 graph 22:20:49.772–22:20:50.238（Asia/Taipei）以 `AgentDeferredError` 結束，耗時 **0.4659 秒**。原限制為 6 transport calls／6 HTTP／240 秒；實際 **0 calls／0 HTTP／0 provider 回應／0 合格報告**。沒有請求正文送出、沒有報告 artifact 或 publication receipt；API/provider 品質率的分母為零，值保持 unknown，不寫成 0% 回應率。

| Agent 22 路由 | 實際送出前結果 |
| --- | --- |
| `gemma-4-31b-it` | 本機預估 52,725 tokens，高於 12,000 input budget |
| `gemini-3.6-flash` | shared circuit-open，未送出 |
| `gemini-3-flash-preview` | shared circuit-open，未送出 |
| `gemini-3.8-flash` | shared circuit-open，未送出 |
| `gemini-3.5-flash-lite` | 本機預估 78,742 tokens，高於 64,000 input budget |

原凍結資料與新 checkpoint 的 model circuits 都是空值；這些 circuit skips 來自既有共享 guard，不是借用歷史輸出。22:23:07 的額外唯讀檢查只對三個 exact model-circuit key 執行 `PTTL`，均為 -2（當時已無該紀錄），未清除或寫入任何 guard。紀錄消失不等於 provider 已恢復，也不能反推本次遇到 429／5xx 或每日額度用盡；本輪沒有這些 provider 回應。

在同一授權的原始絕對截止時間 22:24:49.772 內，曾準備一個不重設總時限的重試入口；執行時僅剩 34.615 秒，未達該入口預留啟動／30 秒子測試／清理的 45 秒條件，因此 exit 3、子程序未啟動、沒有第二個 evidence 目錄與新呼叫。截止後未再送件，沒有另開 240 秒實驗。

證據目录：`/private/tmp/stock-agent-quality-graph-2330-v4-approved-20260912T142015Z/`。原始 manifest／events／outcome／metrics／checkpoint／source-copy 以離線唯讀測試核對，**1 passed／0.03 秒**，`/private/tmp/stock-agent-authorized-preflight-readback-20260912.xml`；原 artifacts hashes 不變，checkpoint 保留未完成 Agent 22／23，沒有已接受分析或數字收據。

本輪只改 scratch 防護與本文件；正式 checkout 仍為 clean main `758242290e795146520f58f68ffa113cac35e52c`。未 commit／push／PR／部署／重啟、未變更正式 DB／報告／路由／Gemma 開關／OOS cohort。下一個實測前應先核對可用且容納完整 prompt 的路由；Agent 22 的輸入縮減只能做可重建的去重／表示法優化，不能刪必要證據或調高限額來冒充改善。**新版 provider 內容與完整報告品質仍未取得新證據，整體計畫未完成。**

## 測試後續：公開財報來源驗證與無損提示容量修正

本節在上述單次 Gemini 授權截止後執行；沒有延長、重新計時或重用其剩餘次數。新增外部請求僅為不需帳號金鑰的公開 Yahoo 年報 GET，未再呼叫 Gemini，也未讀取正式 `.env`、Redis 或正式 DB。

### DCF 年報 producer 的真實來源正向路徑

- 2026-09-12 22:33:40–22:33:43（Asia/Taipei）以目前安裝的 yfinance 0.2.66 和實際 extractor 取得 2330.TW 三份年度財報；**5 GET／2.912 秒**，沒有 LLM 請求。第一個 cookie-bootstrap GET 為 404，crumb 與三份 financial timeseries 都為 200。請求限白名單 host/path、GET、最多 8 次／120 秒、禁止 redirect／帳號驗證／request body；cookie／cache／DB 僅在新建私有暫存目錄。沒有把 cookie、crumb 或完整 query 寫進證據。
- 當期同期間選取成功：股數、債務、現金與 FCF 皆來自 `2025-12-31` 的 dated statement records，不再借用無日期的 `info` 值。FCF 與保存的 OCF 加上**負號保留**的 CapEx 完全一致；這只驗證輸入來源，不是新的 DCF 估值或完整研究報告。
- 三份原始 public JSON 的回放逐筆核對了 **24 筆有效 source facts** 的 raw value、currency、period、row/column；另外 **6 筆缺值**維持 unavailable／None，未補零。資料及所有 capture JSON hashes 在 readback 前後不變；四種缺股數／錯幣別／錯期間／FCF 衝突的 mutation 均拒絕回退至 legacy `info`。
- Yahoo 的 annual `asOfDate` 是財報截止日，不是公告日，capture 的 publication date 保持 null。另查 issuer 原始 [SEC 6-K 會計口徑調節說明](https://www.sec.gov/Archives/edgar/data/1046179/000104617926000201/tsm_20260416.htm)：相同年度可能有不同準則下的數字；Yahoo 此次淨利／資產／權益的四捨五入值與 IASB 口徑相符只是交叉比對推論，**不是 Yahoo 來源 filing 或公告時間已核實**。沒有把該 filing 日期、準則名稱或新資料回填至凍結 12 組 inputs，也未將本結果當成 OOS point-in-time 證明。
- 安全邊界測試 **9 passed／0.02 秒**：`/private/tmp/stock-agent-statement-public-probe-safety-20260912.xml`。正式回放入口 `tests/statement_public_source_replay_probe.py` opt-in **7 passed／1.36 秒**：`/private/tmp/stock-agent-statement-public-replay-20260912.xml`。相關 DCF 回歸 **44 passed／7 skipped／1.52 秒**：`/private/tmp/stock-agent-statement-source-related-20260912.xml`；7 個 skip 是正常模式下未開啟上述明確 opt-in probe。
- 第一個 capture 嘗試因可選 PostgreSQL driver 在 import 時要執行 `pg_config` 而被隔離環境拒絕，發生在任何網路請求之前。後續僅在 scratch harness 禁用不需要的可選 PG imports；沒有開放子程序或正式資料庫來繞過隔離。成功證據位於 `/private/tmp/stock-agent-statement-public-20260912-v2/`，不是第一個空目錄。

### Agent 22 完整輸入的表示法優化

原 registry 把異質 fact 放進單一 union 欄位表，產生大量缺欄索引和 null 占位。新版 `prompt_record_groups.py` 只在編碼更短時，依**原欄位順序**分組；全域 `row_keys` 保留 fact 順序，各組 `columns/row_indices/rows` 可完全還原。不把缺欄與 null、false、0 合併，也不刪 fact、來源、反證或原值。解碼拒絕重複／漏列／越界／布林索引、重複欄名與錯誤列寬；沒有群組表時不附加群組規則。共用 registry 表示法適用新版契約的各角色。

Agent 22 的新版 Gemini 提示另將**完整** financial payload 和 State view 使用既有可逆表格編碼；沒有啟用 role projection 或 compact 刪減，也沒有引入 freshness `$ref`。舊契約 Agent 22 及其他角色的 financial wire 不變，既有 Gemma 角色投影與 dark-launch 開關不變。所有模型輸出、數字、來源和發布 gate 仍照常執行；新表示法是否容易被實際模型理解仍須 live 驗證。

同一份 2330.TW／v4 授權測試 source-copy，重建**真實** `initialize_graph_state → build_model_prompt → generation_config`，沒有既有上游輸出，沒有替換 formatter 或調高上限：

| 項目 | 優化前 | 優化後 |
| --- | ---: | ---: |
| Agent 22 Lite 完整輸入的本機估計 | 78,742 tokens | 61,141 tokens |
| 同一既有本機 input budget | 64,000 | 64,000 |
| 可還原 facts | 162 | 162 |
| 完整日線 bars | 120 | 120 |

新版含 system/schema 的輸入估计減少 17,601 tokens（約 22.4%），保留 2,859 tokens 的本機預檢餘量。實際 wire 解碼與未打包的 full financial／State baseline、當輪 numeric registry **ordered JSON 完全相等**，亦不改原始 source；5 個 fact groups 不是刪掉 157 筆事實。實際 prompt SHA256 `52dfb8e181210348bfb3b5a5de054b2a3553b07c3345b52bc6917dc1cee3ac11`。讀回測試為 `/private/tmp/stock-agent-agent22-prompt-audit.i42AfV/test_agent22_grouped_current.py`；這是本機容量與可逆性證據，不是 Google countTokens、回覆成功或報告品質證明。

### 審查前的回歸與容量矩陣（最末修正版見下節）

- backend inventory：`99423085c464c647f831688fddcc7265724ecad80b275076d6b75655f950c820`；matrix 後再次讀回相同。19 檔回歸 **371 passed／1 skipped／3.85 秒**，`/private/tmp/stock-agent-lossless-integration-20260912.xml`。單一 skip 是未指定外部 offline checkpoint DB；另外的凍結 graph 測試已使用隔離 checkpoint，兩者不是相同覆蓋。
- 原始 **12 組凍結 graph／audit／checkpoint／snapshot：12 passed／12.85 秒**，`/private/tmp/stock-agent-lossless-frozen-graph-20260912.xml`；仍為離線診斷，不計模型研究成功。
- 容量矩陣 **1 passed／17.64 秒**，`/private/tmp/stock-agent-lossless-budget-20260912.json` 和同名 `.xml`：12 jobs／369 rows，**284 admitted、85 rejected**，相較同輸入舊版新增 6 admitted、0 退步。改善是 2330 v1 Agent 5、2330 v2 Agent 12、8069 v1 Agent 3 與三標的 v4 Agent 22 的 Lite 路由；不等於新增 6 份成功報告。
- 38 份原始來源 hashes、routes SHA256 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`、所有 369 rows 的 fact／required／unavailable／source-path **數量**均與基準相同；指定 2330/v4 probe 另完成逐值／逐路徑 ordered readback。矩陣 python/prompt-only code SHA256 為 `da75460b9df3e93bca478e97e07d458b3c7b074cd8368f46d2ece0fcafd87d85`，算法不同於 backend inventory。矩陣中的 2330/v4 Lite 為 61,133 tokens；它沿用矩陣 context 初始化，而上表忠實重建單次授權測試的 graph metadata／RAG 不可用標記，不能混稱同一 prompt SHA。
- 正式 checkout 再讀仍為 clean main `758242290e795146520f58f68ffa113cac35e52c`。本節無 commit／push／PR／merge／部署／重啟、正式 DB／cohort 寫入，也未重新檢查正式服務即時健康；不能將開發測試當成 runtime 已更新。

本批補上 DCF 公開 fetch/readback 與可容納完整 Agent 22 輸入的 Lite 候選路由。**未完成：新表示法的 live 模型理解與完整報告品質、12 組 paired live、每模式至少 30 次跨產業／日期 cohort、財報公告時點／口徑來源核實，以及正式發布與 canary。**前一輪 Gemini 授權已截止，下一輪仍須獨立的明確有界授權；不清除共享 circuit、不重置時限或關閉 gate 來製造成功。

### 獨立審查修正與最末驗證

審查找到一個實際來源保留缺陷：舊 `_unpack` 在任意巢狀物件看到 `__record_table_groups__` 就嘗試解碼。來源若剛好含同名 literal metadata，有效形狀會被改寫成新路徑，錯型別形狀會讓 visible payload 變空。主代理將 group 解碼限縮至明確的 `unpack_fact_registry` **頂層 facts wire 邊界**；financial／State 與 facts 內的巢狀來源保持原值。群組提示也明示同一界線，並未刪除來源欄位或容忍 malformed wire。

- 持久化反例先 **8 failed／30 passed**；修後四檔 **85 passed／2.26 秒**，`/private/tmp/stock-agent-group-literal-green-final-20260912.xml`。中途一次多檔 patch 只完成 decoder、尚未更新舊測試的可信解碼入口，測試因此有 22 failures；完成接線後全部通過，沒有移除 malformed wire 反例或放寬原值斷言。
- 獨立限定覆核 **84 passed／2.26 秒**，以及 cache／partial-rerun／publication 整合 **85 passed／2.53 秒**；原 literal source 反例和新增 valid／malformed case 均通過，受審範圍無剩餘 material finding。review 不等於 provider 模型理解或發布授權。
- 最末 backend inventory **`791de90770cdf0f8ec8e8af59d5e4eb841daea494d35c947beea15ab76e3b060`**；主代理再讀兩個受審 source hashes 與 reviewer 相同。19 檔回歸 **379 passed／1 skipped／3.88 秒**，`/private/tmp/stock-agent-lossless-reviewed-integration-20260912.xml`。原 12 組凍結 graph **12 passed／12.98 秒**，`/private/tmp/stock-agent-lossless-reviewed-frozen-graph-20260912.xml`。
- 最末真凍結 2330/v4 replay 為 **61,189 tokens**，新限界規則增加 48 tokens，仍比優化前 78,742 少 17,553（約 22.3%），低於 64,000 門檻 2,811。**162 facts／120 bars／全部來源與順序仍逐值相同**。新 prompt SHA256 `4c55fb339f8a17e30fe868ccafa20f0d06f903e7338b41474772ab303f77e06e`；證據 `/private/tmp/stock-agent-agent22-prompt-audit.i42AfV/AFTER-REVIEW-EVIDENCE.md`。主代理亦透過隔離 runner 重跑 exact readback，JUnit：`/private/tmp/stock-agent-lossless-reviewed-exact-readback-20260912.xml`。前節 61,141 的舊 prompt／證據保留，不當成最末版本。
- 最末容量矩陣 **1 passed／17.52 秒**，`/private/tmp/stock-agent-lossless-reviewed-budget-20260912.json` 和 `.xml`：仍 **284 admitted／85 rejected**，相較原基準新增 6、退步 0，38 份來源 hashes 和所有 rows 的 fact counts 保持原狀。matrix code SHA256 `b024f1d2f19174c8fef25161c2096b435eba0e18c30a655f23f718e8a0d981d0`，2330/v4 Lite 在矩陣 context 為 61,182 tokens；不混同上項授權 graph metadata replay。
- 正式 checkout 最末完整 `git status --porcelain=v1` 為空，HEAD 仍 `758242290e795146520f58f68ffa113cac35e52c`；開發樹 **224 個 modified／untracked nonignored 檔案**包含前批工作，非本輪新增 224 檔。`git diff --check` 通過。無新 Gemini／金鑰／正式 DB／Redis 操作，無 commit／push／部署／重啟。

離線可逆性、來源 producer readback 與容量修正已完成本批驗證；本節沒有產生任何新模型回覆或合格研報。整體計畫及上述 live／cohort／公告時點／發布驗收仍未完成。

## 財報幣別來源與舊快照重播修正

接續檢查資料取得／公告時間與會計口徑時，發現實際 yfinance core fetch 仍在 `financialCurrency` 缺省或 null 時，以交易 `currency` 補成財報幣別。`financial_fact_units` 的金額顯示及年度 FCF 轉換率輸入也有同一個 fallback。這會把未確認幣別升格成明示 TWD／USD，並讓原本只核對 typed 幣別的 DCF source selector 接受該值。

### 新 fetch 與來源投影

- `financial_currency_provenance.py` 保留明示的三位大寫代碼；這是格式檢查，不是 ISO 清單、FX 匯率或供應商正確性的獨立驗證。缺省、null、空字串、NaN、錯型別或非代碼保持 None，不從 ticker、交易幣別或數字大小猜測。
- 原始金額、股數、source row/column、財報期間與交易幣別不變。未知幣別的 source facts 保留 raw value，但不產生帶推測幣別的 display；年度同年 FCF 比例可以保留算式診斷，輸入幣別仍為 None，不能因此形成可採用的金融 fact。
- 實際 `fetch_stock_data → payload → statement_facts → tool → registry` 取得 **16 faithful reds／3 positive controls**；修後相關七檔 **132 passed／10.45 秒**，`/private/tmp/stock-agent-reporting-currency-green-20260912.xml`。再補明示 TWD／USD 與不同 quote 的真 core fetch、時間語意與 JSON 不變性，15 檔 **225 passed／10.24 秒**，`/private/tmp/stock-agent-reporting-currency-integration-20260912.xml`；不是 provider live fetch。

### 審查發現的舊快照旁路

第一次獨立審查確認 fresh-code 正向／負向路徑，但忠實重現既有 replay 旁路：top-level `financial_currency="TWD"` 曾由 quote 推定，而同一快照的 `financial_fact_provenance.*.financial_currency` 明示 None，registry 仍採 top-level 值。這不是本輪新增 regression，但違反新報告不能忽略已保存反證的來源契約，因此本轮一併修正。

- 新分析以唯讀 `financial_reporting_currency` 核對保存的報告幣別紀錄；有明示 null、不同代碼或無效值反證，就不讓 top-level 舊推定勝出。核對不受 metadata 列順序影響，不使用「最後一筆覆蓋」。
- scalar／年度 history registry、money display、FCF input provenance、DCF receipt 皆使用同一判定；`select_statement_inputs` 亦在 legacy bundle=None 前拒絕矛盾，避免退回 raw 或舊 history 產出 DCF。股價、市值等市場幣別保持獨立。
- **不回寫**原始快照、舊報告、cache 或 DB；source 的曾推定 TWD 值仍保留作為可稽核反例。metadata 完全未保存、None、缺幣別欄位的舊來源保留既有相容性，不能反推當時 provider 是否提供財報幣別，也不把這類資料宣稱已獲獨立核證。
- 新增 replay 測試先 **8 failed／2 passed**，包含真 Agent 2 generation 錯誤接受；修後八檔 **145 passed／2.41 秒**，`/private/tmp/stock-agent-reporting-currency-replay-green-20260912.xml`。独立限定覆核 **152 passed／2.48 秒**，含 28 個 scratch cases：真 cache-hit → 新生成、已知相符正控制、null／異幣別／錯型別反證、順序與原快照不變性。原 finding 已關閉，指定範圍沒有剩餘 material finding；scratch `/private/tmp/test_stock_agent_reporting_currency_review.py`。

### 最末同版證據與限制

- backend inventory 前後為 **`908515b662ba317462a93047675370d7c3716c47cdfb24bd09bf02bf4098d517`**。24 檔整合 **343 passed／10.48 秒**，`/private/tmp/stock-agent-currency-provenance-integration-20260912.xml`，涵蓋 fetch、quant／DCF、numeric generation、發布、graph／cache、snapshot、prompt codec 與 runtime/storage/架構 guardrails；非全庫重跑。
- 先前真正取得的公開財報 JSON 再回放 **7 passed／1.22 秒**，`/private/tmp/stock-agent-currency-provenance-public-replay-20260912.xml`；原 24 筆有效／6 筆缺值及 source artifacts hashes 不變，本輪沒有新增 public GET。
- 原 12 組凍結 graph／audit／checkpoint／snapshot **12 passed／12.68 秒**，`/private/tmp/stock-agent-currency-provenance-frozen-graph-20260912.xml`。容量矩陣 **1 passed／17.61 秒**，`/private/tmp/stock-agent-currency-provenance-budget-20260912.json` 和 `.xml`：369 rows 仍 **284 admitted／85 rejected**，所有 row 的 token estimate／fact counts／容量狀態、38 份來源 hashes 及 routes SHA256 與上一版矩陣一致。
- 本版 matrix code SHA256 為 `9e11fbd6598311a71cbdbe1771640e7e9ed8497f3ce83d41192eb8da82aead33`。矩陣每列呼叫 `initialize_graph_state` 會產生新 run UUID，而 `state_view_for` 會呈現它，因此本輪的 prompt hashes 與前輪不同；未將跨次 matrix 的 byte hash 相等當作語意未變的證據。固定授權 graph metadata 的 Agent 22 exact readback 與此矩陣是不同 probe，本輪不借用其舊 prompt hash 冒稱新 live 結果。
- `source_freshness.financial_statements.fetched_at` 是資料取得時間，`statement_facts.period_end` 是報表截止日；本輪實際 core 測試確認未補造 publication_date／published_at／accounting_basis。精確公告時間與 provider 原始會計口徑仍未取得可直接綁定的證據。

正式 checkout 仍未修改；本輪沒有 `.env`／金鑰／Gemini／Redis／正式 DB 操作，也没有 commit／push／PR／部署／重啟或 cohort 送件。開發工作樹 227 個 modified／untracked nonignored 檔案包含前批工作，`git diff --check` 通過。本批來源缺陷已完成修正及覆核；整體目標仍缺獨立核准的新 Gemini 實測、原 12 組 paired live、跨產業／日期 cohort、公告口徑來源核實與正式發布驗收。

## 完整非 live 回歸與跨事件身分修正

2026-09-12 23:21（Asia/Taipei）開始，使用 `env -i` 與既有隔離 runner 跑全 `tests -m 'not live'`；全部 SQLite／cache／checkpoint 為私有暫存，網路禁用，沒有 provider、Redis、正式 DB 或金鑰操作。測試期間 backend inventory 維持 `908515b662ba317462a93047675370d7c3716c47cdfb24bd09bf02bf4098d517`，僅交付文件更新。

### 原始完整結果與處置

- **11,286 passed／5 failed／24 skipped／1 deselected／75 subtests passed**，1065.55 秒、exit 1；原始 JUnit `/private/tmp/stock-agent-current-full-nonlive-20260912.xml`。JUnit tests=11,390 包含子測試／跳過，非另一個成功數字。3 warnings 是既有 RQ UTC API 與 legacy sync 相容入口 deprecation。
- `test_gemma_evidence_batches` 揭露主角色模型身分 regression：新增的未回覆 route projection 對所有帶 model ID 的事件設定 resolved model，讓純 `gemma_evidence_response` 形成主角色紀錄；batch request 還會清掉已存在的主角色回覆與用量。`model_execution_provenance` 現將取證 prefix 與主角色生命週期分開；保留 batch request／failed-model 歷史，不改 API usage ledger，不把 batch response 或 cache 算成主角色回覆。
- 相同反例擴展至直接品質投影：`report_quality_observability_events` 排除取證事件，與 store 的已知 phase 選取一致，亦避免 legacy NULL-index rows 進入投影後污染身分。無主角色事件時不建立虛構模型 observation；真正 pending／重試仍可清除前次主角色 response，沒有恢復舊身分旁路。
- 兩個 architecture failure 分別為 `yfinance_core_fetch.py` 281 行（要求 <280）與 `final_audit.py` 260 行（要求 <260）。只整理單一名稱 import、將等價的 moat 雙層條件合併，成為 279／258 行；保留未知幣別／未評估警示與原門檻，不新增檔案拆分或刪除行為。
- `test_provider_workflow` 的舊 fixture 只有 `SENT_CHIP` note、沒有成功來源；新版 `source_record_count` 正確回覆 0，optional merge 維持 degraded／stale。校正舊測試預期，保留完整原始 payload／prompt 相等斷言；source provider／counting／freshness 生產程式未改，成功來源正控制另由既有 TDCC/TWSE suites 驗證。
- `test_visual_regression_preflight` 是 sandbox 無法啟動 Chromium。只對同一個啟動／讀版本／關閉、無導航的單測獨立提權補驗，**1 passed／1.91 秒**，`/private/tmp/stock-agent-current-chromium-preflight-20260912.xml`；version 148.0.7778.96、revision 1223 與原 assert 相符。沒有安裝瀏覽器、開啟網站或放行完整 suite 網路。
- 24 skips 仍含未啟用 PostgreSQL／Redis、公開來源 smoke、指定 artifact/checkpoint replay 與 optional browser/Chart.js；不是已取得這些驗收。Chromium 啟動補驗不代表 optional 視覺項目已重跑。

### 分母覆核前的修正版證據

- 新增真實 batch event producer 的 7 phases × 無主角色／pending／已回覆共 **21 個 faithful reds**；原先完整 body／金鑰防護測試不動。第一次 green run 另揭露新增測試漏算既有 snapshot `total_tokens=120` 的 7 個錯誤預期，改為加 batch 前後真 snapshot usage 逐值比較，不更改用量正規化。舊 optional fixture 首次校正尚漏 stale 預期，亦保留該中間失敗紀錄。
- backend inventory **`e80cd4897562cbd81df054f9b50d44167d9bdae1fce71818685d1af19d423ca4`**。身分／batch／觀測與全 import-boundaries 四檔 **595 passed／15.30 秒**，`/private/tmp/stock-agent-full-suite-identity-green-final-20260912.xml`。
- provider workflow／來源真值與信任五檔 **302 passed／1.84 秒**，`/private/tmp/stock-agent-full-suite-provider-regression-final-20260912.xml`。稽核／觀測 API-UI／snapshot／generation／currency 17 檔 **327 passed／75 subtests passed／5.33 秒**，`/private/tmp/stock-agent-full-suite-fixes-integration-20260912.xml`；三組選取有重疊，不能相加當唯一總測試數。
- 原 **12 組凍結 graph／final audit／checkpoint／snapshot 全通過，12.04 秒**，`/private/tmp/stock-agent-full-suite-fixes-frozen-graph-20260912.xml`；原始 source hashes 不變，仍為離線診斷而非 live 研報。
- 本次修改只有事件／身分投影與等價 code layout，未改 prompt、schema、路由或來源資料；上節容量與公開來源回放不因這些修改失效，但不將其舊 backend hash 換成新版本冒稱重跑。

### 獨立審查分母修正與最末版本

覆核發現分子和身分已正確，但 `stage_measures` 的事件分母仍取 `len(events)`。真 producer 的 7 batch＋4 main，typed store 為 4，legacy NULL columns／direct 為 11；同一個主模型 response 分子不變。這不是多算模型成功，但 API 分母不應因 indexed phase 欄位是否補齊而漂移。

- 持久化反例先 **23 failed／10 deselected**，`/private/tmp/stock-agent-batch-denominator-red-20260912.xml`，含原 21 個 phase/lifecycle cases 加上 typed／legacy SQLite 與 direct 比對。現只計未被跳過的事件，明示 `basis=retained_events_excluding_evidence_batches`；distinct agent node 分母不改，raw `scope.events_selected` 保留實際讀入筆數，沒有改 DB／ledger 或把事件筆數當 HTTP 請求總數。
- 最末七檔身分、batch、品質 API／UI 與 recovery 回歸 **174 passed／5.47 秒**，`/private/tmp/stock-agent-batch-denominator-green-20260912.xml`。独立原 22-case scratch 加兩組 lifecycle/batch 回歸 **81 passed／4.74 秒**；typed／legacy／direct 的 stage 分母一致，同 Gemma 主模型、fallback、pending／response／cache 與前後交錯事件不改主角色 count／用量／品質。原始 events 和隔離 SQLite 讀回未改，API usage ledger 仍保留 batch。原 finding 關閉，限定受審範圍無剩餘 material finding；scratch `/private/tmp/stock-agent-batch-identity-review.GtqExg/test_batch_identity_review.py`。
- 最末 backend inventory **`194a95b43ce958f36a8ed8cf6cc396fef319b724abcc2bc1527cff8f081e3202`**；受審 `model_execution_provenance.py` SHA256 `cf2900711c4bfd181ba86f08cfc715046819e2d5cb9a7829286fb864efe9ac20`，`report_quality_observability_events.py` SHA256 `c797e5329544aecaa6a95bec1f59ad20dfa060206084fe23aa1b8b523322d3a1`，主代理與 reviewer 讀回一致。
- 文件同步後再讀 inventory 相同；原兩個模組大小 guard **2 passed／1.12 秒**，`/private/tmp/stock-agent-final-module-size-20260912.xml`。開發樹 228 個 modified／untracked nonignored 檔案包含全部前批工作；本輪新增納入修改的是原 provider workflow 測試，不是新增 228 個檔案。`git diff --check` 通過；228 檔常見 literal key／private-key 格式掃描無命中，僅有限靜態掃描，非完整秘密稽核。開發 `.env` 與 `backend/.env` 均不存在。

以上补驗不是修正版全庫重跑，不覆寫原 5 failed。正式 checkout 唯讀核對仍是 clean main `758242290e795146520f58f68ffa113cac35e52c`；未重檢服務即時健康，亦未 commit／push／PR／部署／重啟。此前 6 calls／4 分鐘的單次 Gemini 授權已結束；本輪無新 Gemini 呼叫。新版 live 品質、paired/cohort、公告口徑來源及發布驗收仍未完成。

## 全庫補驗完成與跨午夜凍結截點修正（2026-09-13）

### 全庫結果屬於日期修正前版本

- `194a95b43ce958f36a8ed8cf6cc396fef319b724abcc2bc1527cff8f081e3202` 的 backend inventory 在全庫執行前後相同，期間未修改 backend 或 repo tests。`env -i`、網路禁用與私有 DB runner 的全 `tests -m 'not live'` 完成 **11,313 passed／0 failed／24 skipped／2 deselected／75 subtests passed／3 warnings**，1064.84 秒、exit 0；JUnit `/private/tmp/stock-agent-reviewed-full-nonlive-20260912T1556Z.xml`。
- 2 deselected 為 live 測試與 Chromium launch-only preflight；後者沿用同一未變更測試／script／Chromium 的已檢視提權補驗 **1 passed／1.91 秒**，不是本次全庫再執行。24 skips 的 PostgreSQL／Redis／public／optional browser 等限制不變，3 warnings 為既有 deprecation。不把排除／跳過計成通過，也不覆寫先前 5 failed 的歷史結果。

### 已重現的日期漂移與限定修復

固定原 2330.TW／v4 source、routes、run/job metadata，只將 `short_term_market_data.date.today()` 從 9 月 12 日移至 13 日，完整提示 hash 從 `4c55fb33…` 變成 `8d7437b0…`；財務與 State 共有 8 個 as_of／requested_as_of／事件 window_end 值改變，原始數字未變。獨立 probe 另證明 `canonical_technical_facts._replay` 的 `date.today()` 會讓 cutoff 後的原始日線在跨午夜時突然進入 full-input bundle。這不是 UUID 或來源內容變動。

- 新 `prompt_observation.py` 重用既有嚴格 `observation_period(data)`，一次從本輪主資料產生 `observation={cutoff, source_ref}`。新生成 Agent 22／24 的 financial、State、technical input 與 registry replay 共用該截點；來源為 `data.fetch_date`，支援原契約的 ISO／中文年月日，不把 timestamp、compact/week date、缺失或非法日期當今天。
- observation **None 才是 legacy**；已提供但未知／不符的 declaration 不回退系統日期。State 自己的 fetch_date 與本輪不符時回 `observation_cutoff_mismatch`、as_of=null，保留 source_fetch_date 和完整原始 source_evidence，不改寫 State／主資料。
- 事件仍取 frozen cutoff 至第 14 日（含首尾），合法未來事件不當成 future observation 刪除；原始 event_calendar 額外保留作證據。超出 cutoff／無法重播的 daily rows、stored indicators 與矛盾 interval/sample_count 都保留在 source_evidence，不升格成已驗證 facts。財務与 State 各核對自己的原始資料，不以一邊通過替另一邊背書。
- 原 acquisition normalizer、明示 legacy as_of、歷史 reader、數值／來源／發布 gate、正式 routes／Gemma dark flag 不變。Legacy State 注入接點保留原兩個 positional arguments。

### 負例、修正及獨立覆核

- 跨日／缺日期初始 **42 failed／1 passed**；future bars／State 不同截點 **4 failed**；無法重播 metadata 完整保留 **2 failed／7 passed**。scratch 初次未載入 backend 的 collection error 與原 exact probe 未指定 usage-aware routes 的前置失敗均是設定問題，不計為 faithful red。證據位於 `/private/tmp/stock-agent-frozen-prompt-dates-red-configured-20260913.xml`、`stock-agent-frozen-prompt-boundaries-red-20260913.xml`、`stock-agent-frozen-unreplayable-red-20260913.xml`。
- 初輪修正版 159 passed；追加邊界後 168 passed。擴大整合為 815 passed／12 failed：7 個 legacy 注入函式拒收新增 keyword，已恢復原調用；5 個 numeric-format 正控制沒有 fetch_date，校正 fixture 明示截點，另加缺截點不製造範例的負控制。未放寬數字 gate。
- 獨立覆核發現 State-only metadata 正規化遮蔽反證的 4 個 faithful reds，已補 State 自身 full-input replay 與原值保留。最末覆核 **116 passed／3.26 秒**，另 legacy State **6 passed／108 deselected／1.43 秒**；scratch `/private/tmp/test_stock_agent_frozen_clock_review.py`。原 finding 關閉，限定日期／來源投影範圍無剩餘 material finding；不是整個專案或 provider 品質認證。

### 最末同版驗收及未完成事項

- backend inventory **`0c21fba84dfda3e773cf26c5261e2b566046e43185c2ba0ce0c6f7b7ae4d4505`**。24 檔相關整合 **1,000 passed／16.86 秒**，JUnit `/private/tmp/stock-agent-frozen-clock-reviewed-integration-20260913.xml`；涵蓋完整提示、State、安全／數字契約、發布／graph／cache/rerun 及全 import-boundaries。這是日期修正後的相關回歸，不冒稱又做一次全庫測試。
- 原 12 組凍結 graph／final audit／checkpoint／lossless snapshot **12 passed／12.36 秒**，`/private/tmp/stock-agent-frozen-clock-12-graph-20260913.xml`。容量矩陣 **1 passed／16.55 秒**，`/private/tmp/stock-agent-frozen-clock-budget-20260913.json`／`.xml`：369 rows 仍 **284 admitted／85 rejected**，38 份 source hashes、routes、schema catalog、generation configs、fact available/unavailable/required counts 與前版一致。只有 Agent 22／24 的 24 rows 增加來源可見路徑及 token estimate；不等於新增或刪除 canonical facts。
- 原授權 source-copy 的真實 graph → routed prompt → system/schema estimator 在 9 月 12、13 日與 10 月 15 日三種模擬時鐘下 **完整 prompt 逐字一致**。三個 section 的 ordered JSON 可逆讀回、162 facts、120 bars 與 source／routes hashes 均保留。**61,758 estimated tokens／64,000 input cap，餘量 2,242**；prompt SHA256 `b519020a4ddaf566ee3b9790c44723764787d62c67f80dfca4985781a63fc528`。`/private/tmp/stock-agent-fixed-clock-reviewed-readback-20260913.xml` **1 passed／2.26 秒**，scratch `stock-agent-final-prompt-readback.pYW5TW/test_fixed_clock_readback.py`。新增明示截點與原始日曆使估計較前一版 61,189 增加 569；不是降低上限或刪來源。這仍是本機估計，不是 Google tokenizer 或 live 成功。
- 本輪無 `.env`／金鑰／provider／Redis／正式 DB 操作，沒有新增 public GET、送件、commit／push／PR／部署／重啟。正式 checkout 唯讀核對 clean HEAD 仍為 `758242290e795146520f58f68ffa113cac35e52c`；沒有聲稱即時 API／Worker 健康。232 個修改／未追蹤檔包含既有各批工作，不是本輪新增 232 檔。

原 2026-09-12 22:20:49.772–22:24:49.772 Taipei 的單次 Gemini 授權已結束（實際 0 calls），不能重新起算。離線可修的本項已完成；新 Gemini 正向報告、12 組 paired live、每模式至少 30 次 cohort、公告／口徑外部來源核實與正式發布驗收仍未完成，需分開交代，不將本節測試數當成四模式成功率。

## 官方年報交叉佐證與供應商來源邊界（2026-09-13）

本輪承接尚未完成的財報口徑／日期核對，僅讀公開文件及既存 public capture，沒有新 Gemini 授權或模型呼叫。

- [台積電官方 2025 Form 20-F](https://investor.tsmc.com/sites/ir/sec-filings/2025_20F%20Report.pdf) 的 IASB 口徑、2025-12-31 欄及原表單位已核對：期末普通股數（PDF 第 2 頁）、現金（F-4）及 OCF（F-10）三項，按原表精度／單位換算後，與既存 Yahoo capture 完全相符。不是已證明 Yahoo 的 upstream filing ID。
- F-5 的流動長期負債、非流動公司債、長期銀行借款與租賃負債合計，與保存的 `Total Debt` 數值相同；F-11 的設備／無形資產取得與租賃預付款增加合計，與 signed `Capital Expenditure` 相同。再與 OCF 相加可重現保存的 FCF。這三項是**算術交叉佐證／組成推論**，不宣稱 issuer 原表有同名聚合欄，也不把其作為 Yahoo 已明示的計算定義。CapEx 不可直接改名為 issuer 的設備支出單列。
- 該文件的 management authorization 為 **2026-04-16**；[官方年報目錄](https://investor.tsmc.com/english/annual-reports) 的 20-F 日期標籤為 **2026-04-17**。兩種事件分列，不擅自猜測時區或首次公告時刻。[SEC 6-K 口徑調節](https://www.sec.gov/Archives/edgar/data/1046179/000104617926000201/tsm_20260416.htm) 證明同年度 Taiwan-IFRSs 與 IASB 數值可不同，但不能替 Yahoo 宣告其來源版本。
- 人工摘錄／定位與單位保存在 `/private/tmp/stock-agent-issuer-annual-audit.V7YIQw/issuer-observations.json`。Decimal 唯讀比對完成 **3 個直接值＋3 個算術關係**；三份原始 public response SHA256 仍與原 capture 相同。此為資料比對，不是新增六項生產測試、DCF 估值或合格研究報告。
- SEC 巨型 HTML 超過讀取工具大小限制；官方 PDF web text 可讀，但 screenshot 入口未返回可檢視圖片，直接下載則 HTTP 403。因此本輪只有含欄名／單位的文字表格核對，**未宣稱完成 PDF 視覺驗證**，沒有換身分或繞過存取限制。無本機 PDF 產出。

**已縮小的缺口**：上述保存值有具體官方文件的交叉佐證，issuer 文件日期與口徑亦已定位。**仍未知**：Yahoo 的逐值上游 filing/version、首次可用時間及明示 accounting basis。原 capture 沒有這些欄位，不能由同值反推；須有供應商 lineage 證據，或經另行來源介接保留明示 filing 與取得時點。未回填凍結 12 組／28 OOS／歷史 artifacts，未改 backend、品質 gate 或正式 runtime；先前版本測試不因本輪只讀核對失效。新版 live、paired/cohort 與發布仍未完成，下一個 Gemini 實驗等待新的明確有界授權。

## 接續阻擋核對（2026-09-13）

前兩次接續分別完成凍結日期修正及官方來源交叉佐證，屬實質進展；但兩次結尾均仍缺新 Gemini 實測授權。本次再核對 backend inventory 與上述 JUnit 均相同，所有限定覆核代理已完成，上一輪測試程序已正常退出；沒有需要繼續等待的實驗 handle，也沒有新的實際使用者同意。此核對本身不計新的模型／品質驗證進展。

同一授權阻擋已連續三次確認，獨立可做的限定修正及來源查核已處理。依既有順序，下一個必要步驟是新版本真實 provider 小實驗；不能以內部 goal 續作當新同意、把舊 4 分鐘重設、跳過 live 驗收直接部署，或擴大其他來源工程代替原目標。暫停自動續作以等待新的明確有界授權，完整目標仍未達成。

接續所需：重新核准將 **2330.TW／v4 同一凍結研究資料及新版提示**送到既有 Google Gemini 路由，现有金鑰只用於驗證，**最多 6 次呼叫／4 分鐘**。獲准後從本節的第一個未完成步驟開始，不重啟整份計畫；不自動擴張為 12 組／跨日期 cohort 或正式發布授權的替代驗收。

### 單次窗口啟動送審未執行（2026-09-13）

本次可見請求明列 2330.TW／v4、既有 Gemini 路由與金鑰、最多 6 次／4 分鐘。主代理完成唯讀核對：原 source／routes／env 與先前 manifest 相符，backend inventory 仍為 `0c21fba84dfda3e773cf26c5261e2b566046e43185c2ba0ce0c6f7b7ae4d4505`，三個 scratch harness hashes 與先前 39 passed 的驗證版本相同；正式 checkout 仍 clean main `758242290e795146520f58f68ffa113cac35e52c`。沒有因此重跑離線 suites。

僅新增暫存啟動器 `/private/tmp/stock_agent_authorized_2330_v4_20260913.py`：沿用既有實驗設定，6 transport calls／6 HTTP 雙上限，inner 220 秒及 outer 240 秒整個子程序硬上限，無自動重試或時間重設，SQLite／reports 只在新私有目錄。

兩次相同命令送審都在 CreateProcess 前被 auto-review 拒絕，理由均是可信授權紀錄仍被判定為已到期的舊窗口；第二次補充本輪可見請求並未被接受。沒有改端點、間接執行或繞過審查，亦未將代理說明當使用者授權。**測試未啟動、0 provider calls、無新的實驗 outcome／報告**；這不是 Gemini 回應失敗或品質驗證結果。待使用者明示重新核准「現在啟動新的單次窗口」並通過工具審查後才可執行；不重用未啟動程序作完成證據。本節只記錄啟動阻擋，未修改 backend、正式 DB、routes、cohort、Gemma 開關或發布狀態。

## 重新核准後的真實 Lite 回應與品質阻擋（2026-09-13 09:51）

使用者在上一輪拒絕與重新核准請求之後，再次直接核准同一 2330.TW／v4 凍結資料、既有 Google Gemini 路由及金鑰、最多 6 次呼叫／4 分鐘；本輪啟動通過工具審查，不是重用舊窗口。啟動器限制 6 transport calls／6 HTTP、inner 220 秒、outer 240 秒；金鑰只作正常驗證，HTTP guard 在 dispatch 前拒絕正文含金鑰，完整品質／額度／熔斷保護均保留。原先 process-only bounded-thinking 對照也保留，但本輪未呼叫該對照的 3.6／Preview，不能主張它有效。

### 實際執行與分母

- outer 啟動時間 `1789264271.922858`（09:51:11.923 Taipei），絕對截止 `1789264511.922858`（09:55:11.923）；**13.434 秒正常退出，exit 2**，不是超時或達次數上限。graph 09:51:14.366–09:51:25.053，共 **10.687 秒**；Agent 22 第二份草稿仍未通過，`AgentQualityDraftError` 使流程停止並取消 Agent 23 的並行重寫。
- 實際 **4 transport calls／4 HTTP attempts**，全部走既有 `gemini-3.5-flash-lite`，回傳的 modelVersion 同名，只是 provider 自報標籤而非獨立 attestation。**4／4 收到 HTTP 200、3／4 完整串流 STOP、1／4 CancelledError／未完整串流**。取消的 response 已有 header／部分文字與 usage，不是 provider 5xx、429 或額度耗盡。
- **0 合格完整報告／1 個隔離 job**。3 份完整回應均通過完整 JSON、raw schema 與必填欄位檢查，但數字契約未通過；不能把這個小樣本解讀為四模式成功率。Agent 24／final audit／renderer 未執行到正式完成，checkpoint 的 pending 為 Agent 22／23，無 accepted analyses／structured_outputs、report_done 或 reports artifacts。
- 本次共享 guard 對 3.6／Preview／3.8 仍回 circuit-open，沒有清除或绕過；Gemma Agent 22／23 本機預估 47,512／27,517 高於 12,000，未送出。Lite admission 成功。沒有額外重送、延長或把剩餘兩次轉成另一個實驗。

### 完整原稿回放定位

| 完整回應 | JSON／schema／必填欄位 | 未綁定數字問題 | 本機 input estimate／provider input |
| --- | --- | --- | --- |
| Agent 22 初稿，attempt 1 | 通過 | 14 | 61,758／60,819 |
| Agent 23 初稿，attempt 2 | 通過 | 8 | 57,807／49,388 |
| Agent 22 重寫，attempt 4 | 通過 | 11 | 62,858／61,421 |

上述問題碼都是 `unbound_numeric_claim`，具體在 finding／freshness_note／analysis_markdown 中直接寫日期、觀測天數及指標週期。不是缺必填欄位，也不是 MAX_TOKENS 截斷；這次完整回應 finish reason 都為 STOP。原稿 fact token 可解析計數分別 13／12／18，但這些不是合格研究數，也不證明定性判斷正確。Agent 22 兩份實際提示都仍有完整 120 根日線；没有刪來源、放寬數字 gate 或由程式替模型補假證據。

實際重寫提示已包含 14／8 項總數、path/code/text 診斷樣本與日期 metadata-token 規則；因此不能把失敗說成「完全沒把錯誤回傳模型」。下一個優化候選應先做離線反例：核對角色任務中的裸日期／週期示例與輸出規則是否相衝，將適用格式與完整來源綁定教清楚；角色 22／23 的 repair instruction 中仍有不適用的估值規則及 `正式報告輸出契約 None`，可評估只清理指令雜訊、保留全部來源／schema／gate。尚未實作或取得修正版 live 效果，不能承諾成功率上升。

### 證據、隔離與未完成

原始 evidence：`/private/tmp/stock-agent-quality-graph-2330-v4-renewed-20260913T015111Z/`，包含 manifest/source-copy/prompts/requests/wire/calls/http/events、私有 operational DB／checkpoint、outcome/metrics。外層時間上限另有啟動 tool receipt。離線唯讀回放 **1 passed／1.07 秒**，`/private/tmp/stock-agent-renewed-live-readback-configured-20260913.xml`；scratch `/private/tmp/test_stock_agent_renewed_live_readback_20260913.py`。該測試核對所有 evidence 檔案前後 hashes 不變、來源 digest、呼叫上限與截止、完整回應的實際 registry／numeric gate 及無發布。初次回放未載入 backend path 的 1 failed 是測試入口設定錯誤，修正後重跑；不是生產 regression。回放禁網、乾淨 env、私有 DB，新增 provider calls=0。

本輪 backend inventory 前後均 `0c21fba84dfda3e773cf26c5261e2b566046e43185c2ba0ce0c6f7b7ae4d4505`；source SHA256 `cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd`、routes SHA256 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a` 不變。正式 checkout 再讀仍 clean main `758242290e795146520f58f68ffa113cac35e52c`。本輪只新增 scratch 回放與更新本文，未修改 backend、正式 SQLite／報告／routes／Gemma 開關；共享 Redis 僅沿用正常 quota/circuit guard，沒有清除保護。未 commit／push／PR／部署／重啟或送出 cohort。

**本次有界實驗已完成，整體優化未完成**：現在有新版 Lite 真實回應的正向傳輸證據，但合格完整研報、12 組 paired live、跨產業／日期 cohort 及發布驗收仍未取得；不能用傳輸改善替代內容品質驗收。

## 實測後的診斷取樣與角色重寫修正（2026-09-13）

前一輪屬實質進展：得到 4 次真实 HTTP 及完整原稿，下一步由輸入容量轉為數字／日期格式遵循。本輪繼續既有 P0/P1 的本機實作，不使用內部 goal 續作當新 Gemini 授權，不延長已結束的 6 calls／4 分鐘窗口。

### 可重現問題與範圍

- `prompt_rules._safe_rule_text` 原先將缺省/null 轉成字串 `None`，由真實 `build_output_cleanliness_rule()` 注入完整提示。現在只有 Python None 使用既有 fallback；字面文字、數字零、False 與原規則都保留。來源 JSON 不經此修正，也不刪其 null。
- `generation_numeric_runtime.numeric_repair_detail` 原來依 code/path 只留一項，同段首個年份可遮蔽後面的指標週期。現在最多六筆診斷，優先涵蓋不同 code/path，再納入同欄其他錯誤片段；每段最多 120 字，只引用原稿、以 JSON 表示且明標資料而非指令。完整原稿／全部 issues／receipt 不變，不生成替換值，也不改來源或 numeric gate。
- `quality_retry.install_quality_retry_context` 現把前置品質重寫明示為 `agent_quality`，不再誤標「最終跨 Agent 稽核」。真正 final-audit 入口保留原預設標籤。`repair_reflection.build_audit_retry_instruction` 的 Agent 22／23 保留技術／籌碼完整任務、來源／反證／限制與完整 JSON，移除該角色不適用的杜邦／營收成長財務修復段；其他角色財務規則不變。legacy 未提供數字契約時仍沿用原來源格式，禁止猜造 fact id。重寫次數、路由、取消、restore／cache／發布行為沒有改動。

### 紅綠測試與覆核修正

- 新 `tests/test_numeric_repair_feedback.py` 初次 **5 failed／6 passed**，`/private/tmp/stock-agent-repair-feedback-red-20260913.xml`，均為預期行為失敗。首版與相關四檔 **165 passed／2.01 秒**，`stock-agent-repair-feedback-green-20260913.xml`。
- 首輪整合 backend inventory `3fe80c35d9276b5602755317c901006967a261773eaa7fe39a017eaf331a3a18`：15 檔 **404 passed／4.68 秒**，`stock-agent-repair-feedback-integration-20260913.xml`；全 import-boundaries／prompt evidence／Google safety **541 passed／13.19 秒**，`stock-agent-repair-feedback-import-safety-20260913.xml`。兩組選取與較早測試有重疊，不相加成唯一總數。
- 獨立覆核再抓到 P2：長段落同一日期的年／月／日可產生略微平移片段，仍占滿六樣本。原 scratch 為 **94 passed／1 failed，2.13 秒**；反例已保留在 repo，主代理重現 **1 failed／6 passed／7 deselected**，`stock-agent-repair-feedback-review-red-20260913.xml`。修正為同 code/path 中，完整錯誤 text span 已被入選片段覆蓋時不重複占位；未入選片段不記為已覆蓋。原 token 等長遮罩的 offset、不可信文字作 JSON data、完整 receipt 與容量上限不變。
- 最末上述四檔相關補驗 **66 passed／1.90 秒**，`/private/tmp/stock-agent-repair-feedback-reviewed-green-20260913.xml`。最末 backend inventory **`047ed0e262a7211f5c549760911e49d9ddc270781cbbfe70e9b4d0f5e65063d7`**。較早 404／541 是覆核修正前證據，不能將其 hash 換成新版冒稱完整重跑；這次只補驗受影響接點。

### 原始來源、實際提示與容量

- 最末新版以同一凍結 source → 真實 graph 初始化 → routed prompt → 原 provider 完整原稿 → 生產 parser/numeric gate → 一次重寫提示，**2 passed／2.36 秒**；`/private/tmp/stock-agent-repair-prompt-reviewed-readback-20260913.xml`，scratch `test_stock_agent_repair_prompt_readback_20260913.py`。Agent 22／23 的原稿仍分別因 **14／8** 項問題被拒絕，無 accepted output；只是改善診斷，不是離線替模型修稿。
- Agent 22 初稿／修稿預估 **61,754／63,132**，162 facts、120 bars；Agent 23 為 **57,804／59,195**，52 facts，均低於 64,000。修稿新增明確片段而非刪除資料，source payload、facts／required／unavailable、全部 capture 檔案 hashes 逐值不變。這是本機 estimator，不是本輪新的 Google token usage。
- 首輪三項旁證：原 12 組凍結 graph／checkpoint／snapshot **12 passed／13.02 秒**（`stock-agent-repair-feedback-12-graph-20260913.xml`）；容量矩陣 **1 passed／17.50 秒**（`stock-agent-repair-feedback-budget-20260913.json`／`.xml`）。369 rows 仍 **284 admitted／85 rejected**，38 份來源 hashes、schemas、facts、generation configs、路由與 preflight 逐項相同；缺省 None 移除使初稿 input estimates 每列減少 1–5。後續窄修只改重寫診斷取樣，不影響該初稿矩陣，未無故重跑。比較脚本初次誤用不存在的 `model` key，依實際 `requested_model` 更正後完成，未改矩陣或來源。
- 三項首輪測試各有一項 pytest cache 無權寫入開發 `.pytest_cache` 的環境警示，沒有測試失敗；後續補驗以 `-p no:cacheprovider` 關閉非必要 pytest cache。全部測試經隔離 runner 禁網／私有 DB，沒有 provider 或正式 DB 存取。

本輪實作為上述四個 backend 檔及一個新測試，開發樹 235 個 modified／untracked 項目含所有前批工作，不是本輪新增 235 檔。`git diff --check` 通過；正式發布、12 組 paired、cohort、合格新版 live 研報仍未完成。新的實測需要另行明確有界授權；本輪沒有再呼叫 Gemini、commit／push／PR／部署／重啟或改 Gemma 開關。限定覆核的最終確認另補下列紀錄。

限定獨立覆核最終確認原 P2 已關閉：**31 passed／1.75 秒**，包含原反例、只涵蓋部分的長數字不得略過、不同 code/path 不互相消除、六樣本／120 字上限與 receipt 不變；未發現新 material 問題。主代理讀回 `generation_numeric_runtime.py` SHA256 `28fb73fdc2f32033b49dcd0c20557130692afde715916e88d02aebc29aa7bc14` 與 reviewer 相同，並將兩個新增邊界正控制保存進原測試檔。這是本機修正 readiness 的限定證據，不是新的 provider 品質或正式部署。

最後永久邊界單檔 **16 passed／1.83 秒**，`/private/tmp/stock-agent-repair-feedback-final-boundaries-20260913.xml`；文件同步後 backend inventory 仍為 `047ed0e2…`、`git diff --check` 通過。所有本輪測試程序均已正常退出，覆核代理已完成，沒有需要继续等待的 live handle。本輪是已驗證程式進展，整體目標仍未完成。

## 修正版的第二次明確核准實测（2026-09-13 12:25）

使用者在「是否核准現在啟動新的 2330.TW／v4 Gemini 隔離實測，沿用凍結資料、修正版提示及現有金鑰，最多 6 次呼叫／4 分鐘，金鑰不進提示」後回覆「核准」。本次是新授權，不是內部 goal 續作或重用 09:51 窗口。新 launcher `/private/tmp/stock_agent_authorized_repair_feedback_2330_v4_20260913.py` 僅更新目標版本、實驗目錄及加入既有 env digest 核對；三個已覆核 harness 的 hashes 不變，正常 quota／circuit／品質保護保留。

- outer 開始 `1789273517.3865118`（12:25:17.387 Taipei），硬截止 `1789273757.3865118`；inner 220 秒、outer 240 秒，6 transport／6 HTTP 雙上限。實際 **14.466 秒，exit 2**，未觸及時間／次數上限，也無自動重試；原生 session `91970` 已確認終止。
- graph 12:25:19.836–12:25:31.602，**11.765 秒**。**4／4 HTTP 200、3／4 完整 STOP 回應、1／4 CancelledError**；全部實際請求與 provider 自報身分為 `gemini-3.5-flash-lite`，仍不是 provider 內部版本 attestation。Gemma 因本機輸入超量未送出，3.6／Preview／3.8 由正常 shared circuit 攔下；没有清除保護。
- Agent 23 第二份草稿仍不合格，`AgentQualityDraftError` 停止流程並取消 Agent 22 重寫，並非 provider 網路失敗。**0 合格完整報告／1 個隔離 job**，Agent 24／final audit／renderer 未完成，無 publication／report_done／reports artifacts。checkpoint 的 pending 不是仍在執行的證據。

| 完整回應 | JSON／raw schema／必填欄位 | 裸數字問題數 | 引用未獨立成行問題數 | 本機 input estimate／provider input |
| --- | --- | ---: | ---: | --- |
| Agent 22 初稿，attempt 1 | 通過 | 12 | 0 | 61,757／60,816 |
| Agent 23 初稿，attempt 2 | 通過 | 9 | 9 | 57,806／49,385 |
| Agent 23 重寫，attempt 3 | 通過 | 8 | 8 | 59,643／50,408 |

問題碼為 `unbound_numeric_claim`、`numeric_token_must_stand_alone`；前者包含 freshness_note 的日期、觀察天數、Agent 22 的 RSI 附近數字及情境期間，後者為正文將 fact token 夾在其他文字之間。日期可拆成多筆問題，因此這些是 validator occurrence counts，不是獨立錯誤事實數、財務正確率或品質改善幅度。三份完整回應可解析 fact token 計數為 24／12／13，不是合格研究數。Agent 22 原提示保留 **162 facts／120 bars**，Agent 23 為 **52 facts**。單次樣本及生成段落本身不同，不把局部數量變動當成統計改善或 exact-prompt A/B。

唯讀回放逐項確認：新版 `角色品質檢查要求重寫本段` 與 excerpt 在實際 attempt 3／4 提示中，沒有舊的最終跨 Agent 稽核標籤及缺省 None 文案；並以實際 prompt registry 重新執行完整 JSON、schema 與 numeric gate。**1 passed／1.28 秒**，`/private/tmp/stock-agent-repair-feedback-live-readback-20260913.xml`；入口 `/private/tmp/test_stock_agent_repair_feedback_live_readback_20260913.py` 經隔離 runner 禁網／私有 DB，新增 provider calls=0。原始 15 個 evidence files hashes 前後相同；未以修改原稿換取通過。

本次 evidence：`/private/tmp/stock-agent-quality-graph-2330-v4-repair-feedback-20260913T042517Z/`。backend inventory 前後均 **`047ed0e262a7211f5c549760911e49d9ddc270781cbbfe70e9b4d0f5e65063d7`**，source／routes／env 與前次 manifest 核對相符；正式 checkout 前後 clean main **`758242290e795146520f58f68ffa113cac35e52c`**。只新增 scratch launcher／回放與更新本文，沒有修改 backend、正式 SQLite、歷史報告、路由、Gemma 開關、OOS cohort，沒有 commit／push／PR／部署／重啟。本次窗口已結束，不將剩餘兩次改作另一個實驗。

結論：診斷修正已載入實測，但尚未取得合格報告，不能宣稱提高四模式品質／成功率。下一步先離線檢查角色輸出示例與完整模板的格式一致性，再決定有證據的改動及必要實測；完整同輸入對照、每模式至少 30 次先導與發布驗收仍未完成。

## 角色格式片段的欄位補齊（2026-09-13，離線）

上一輪取得新版真實原稿，屬實質進展。本輪檢查 Agent 22／23 角色模板、system 數字規則、修稿提示及 validator，沒有發現允許內嵌 token 的相反指令；原規則已要求日期／數字 token 獨立一行。因此不把失敗說成「系統沒有提供規則」。具體可補的教學缺口是 `build_fact_example()` 原本只示範 finding／source_refs，沒有 JSON 字串內的 freshness_note 及正文段落範例，與實際常失敗欄位不完整對應。

- 本輪只改 `backend/canonical_fact_prompt.py` 的格式片段：同一已存在且角色適用的 fact，分別示範 finding 與 analysis_markdown 的獨立行；新增 freshness_note。日期只取該 fact 明示且嚴格 ISO 的 `ASOF:YYYY-MM-DD`，不取其他來源較新日期、OBS／FY、全體 fetch_date 或執行時鐘；缺少此日期時明示該片段未示範日期，不猜造。文案另明示單筆來源日期不代表全部資料更新時間、無延遲或比較期完整。
- 保留原 sorted fact 選取、完整 registry、來源資料、單位 formatter、numeric／schema／發布 gate、路由、次數及輸出 cap。片段仍不是完整研究報告，完整角色 parser 必須拒收；沒有補造 confidence／結論／反證，不以範例取代完整角色任務。Legacy／未支援角色／沒有適用 fact 時維持原行為。
- 這是有界提示改善，**不證明它是 Lite 失敗的唯一原因，也不證明成功率提升**。未把原稿改成修復後模型輸出；大樣本與 live 驗收仍保留。

驗證與狀態：

- `tests/test_numeric_prompt_examples.py` 新增欄位與日期反例先 **9 failed／12 deselected，1.87 秒**（`/private/tmp/stock-agent-role-field-examples-red-20260913.xml`），均為舊範例缺欄的預期失敗。修正後四檔 **133 passed／3.23 秒**（`stock-agent-role-field-examples-green-20260913.xml`）；同一來源分別出現在 finding／正文，原測試的 token 解析次數由一次改為兩次，不是新增事實數。
- 七檔相關 integration／graph round-trip／lossless prompt／全 import-boundaries **676 passed／13.68 秒**（`/private/tmp/stock-agent-role-field-integration-20260913.xml`）。沒有重跑未受影響的全庫或假稱全四模式 live 測試。
- 最新 12:25 capture 的真實 frozen graph → prompt → 原失敗輸出 → 同一 numeric gate → 一次修稿提示回放 **2 passed／2.40 秒**（`/private/tmp/stock-agent-role-field-prompt-readback-20260913.xml`）。Agent 22 初稿／修稿預估 **61,953／63,389**，保留 **162 facts／120 bars**；Agent 23 **58,004／59,761**，保留 **52 facts**。均低於既有 64,000 input cap。原稿仍分別因 12／18 項問題拒收，無 accepted output；原 capture hashes 及 source payload 全部保持不變。入口 `/private/tmp/test_stock_agent_role_field_prompt_readback_20260913.py` 重用既有 readback，不新增 provider 呼叫。
- 12 jobs／369-row 容量矩陣 **1 passed／17.07 秒**（`/private/tmp/stock-agent-role-field-budget-20260913.json`／`.xml`）。對照 `stock-agent-repair-feedback-budget-20260913.json`，38 份 source hashes、schema catalog、每列 facts／generation config／routes／preflight 與全部非 prompt 欄位相同，仍 **284 admitted／85 rejected**。只有 Agent 22／23 的 30 rows 增加 **195–204** 預估 tokens，其餘估計不變；不是減來源或調高上限。各次初始化的 prompt hash 不一致，不宣稱 exact-prompt A/B。
- 限定獨立覆核 **48 passed／2.00 秒**，確認日期來源、JSON 真換行、片段不能成為完整報告、legacy／角色邊界與資料不變；無 material finding。選取為 `tests/test_numeric_prompt_examples.py`、`tests/test_generation_numeric_integration.py` 及 `/private/tmp/test_stock_agent_role_examples_review.py`，經同一 env-i 隔離 runner；stdout session `31485`／完成 chunk `2c9257`／exit 0，未另存 JUnit。主代理已讀回 scratch 的公用 parser 拒收與不得借用其他來源日期／執行時鐘反例，未為覆核階段重跑。覆核及主代理 source SHA256 均為 `856a936033dddfe7b526acb95f800763d549fc56bf28998dc7484ddc9c660519`。測試選取有重疊，不將上述數字相加為唯一總數。

本輪 backend inventory **`be3740a4d3d10322e39e0a50356e03b5ef225bcbcb30813b1e77b76ca317b631`**。全部檢查用隔離 runner／禁網／私有 DB；没有新 Gemini 授權或呼叫，不重開已終止的實驗，不改正式 runtime／DB／artifacts／cohort／Gemma 開關，未 commit／push／PR／部署／重啟。最新 backend 仍需新的有界 provider 驗證，完整優化目標未完成。

## 角色欄位範例版的明確核准實測（2026-09-13 14:14）

使用者對新版最多 6 次／4 分鐘的隔離實測回覆「核准」，本輪使用該次新授權啟動一次，不是自動 goal 續作代替同意。Launcher `/private/tmp/stock_agent_authorized_role_examples_2330_v4_20260913.py` 沿用已覆核的三個 harness、來源／路由／env digest，只更新版本、授權標記與新的私有輸出目錄；未改正式 backend 或設定。

- outer 開始 `1789280085.1444879`（14:14:45.144 Taipei），硬截止 `1789280325.1444879`；inner 220 秒、outer 240 秒、6 transport／6 HTTP 雙上限。實際 **16.049 秒、exit 2**，沒有觸及時間／次數上限；session `21714` 已終止，無自動重送。
- graph 14:14:47.332–14:15:00.926，**13.594 秒**；**4／4 HTTP 200、3／4 完整 STOP JSON、1／4 CancelledError**。全部實際路由及 provider 自報標籤為 `gemini-3.5-flash-lite`，不是 Google 內部模型身分的獨立認證。Gemma 仍因本機輸入容量跳過，3.6／Preview／3.8 仍由既有 shared circuit 攔下，未繞過 quota／circuit。
- Agent 23 第二份草稿被品質契約拒收，引發 `AgentQualityDraftError`，同一 graph 隨即取消 Agent 22 並行重寫。不是 provider 429／5xx、output cap 截斷、逾時或人工停止。**0 合格完整報告／1 個隔離 job**；Agent 24／final audit／renderer 未完成，沒有 accepted analyses／structured outputs、publication、report_done 或 reports artifacts。剩餘兩次呼叫不挪作新實驗。

| 完整回應 | JSON／raw schema／必填欄位 | 裸數字問題數 | token 未獨立成行 | 本機 input estimate／provider input |
| --- | --- | ---: | ---: | --- |
| Agent 22 初稿，attempt 1 | 通過 | 6 | 0 | 61,952／60,932 |
| Agent 23 初稿，attempt 2 | 通過 | 7 | 0 | 58,003／49,503 |
| Agent 23 重寫，attempt 3 | 通過 | 3 | 0 | 59,485／50,304 |

三份原稿的 `as_of_date` 均為凍結截止 2026-09-12，通過 not-after-cutoff 檢查；這不是每筆來源日期／新鮮度的證明。Agent 22 裸數字是均線週期及 RSI 中線敘述；Agent 23 初稿包含觀察窗與日期，重寫剩下 freshness_note 的同一個 2026-09-11 日期，validator 將年／月／日計為三項。上述數字是 occurrence counts，非獨立錯誤事實數或正確率。可解析 fact token 次數為 20／10／7，也不是合格研究數。新版同一樣本的 token 換行問題確實未再出現，但生成內容及長度不同，不能認定因果、穩定改善或四模式成功率提高。

人工原稿讀回另見尚須處理的語意風險：Agent 23 重寫在「大戶持股比例與分級變化」敘述下放 `chip.borrowed_short_sale_balance`，借券餘額不是持股分布證據；同段稱「維持穩定」卻又承認缺乏前期比較。Agent 22 的「盤後無延遲」不能僅由來源日期 token 證成。數字 grammar 明文不是自然語言事實檢查器，沒有 token 格式問題不等於這些論述通過；本次原稿全部已遭拒收，未讓上述風險進入正式報告。不替模型改寫原稿，不放寬 gate，也不將重寫中改用中文數字或縮短段落算成研究品質提升。

唯讀驗證 `/private/tmp/test_stock_agent_role_examples_live_readback_20260913.py` 透過隔離 runner／禁網／私有 DB，**1 passed／1.38 秒、exit 0**，JUnit `/private/tmp/stock-agent-role-examples-live-readback-verified-20260913.xml`。確認新範例在全部四次實際 HTTP body 中、兩次重寫含既有角色診斷及 excerpt；重新走完整 JSON、raw schema、必填、數字與觀測截止檢查，Agent 22 保留 **162 facts／120 bars**，Agent 23 **52 facts**；15 個原 capture files hashes 前後不變，新增 provider calls=0。

此回放起初兩次失敗是 scratch 對 transport 的假設錯誤，分別誤設原 prompt 與 HTTP text 全等／substring，**1 failed／1.26 秒**及 **1 failed／1.25 秒**，保留於 `stock-agent-role-examples-live-readback-20260913.xml`、`stock-agent-role-examples-live-readback-green-20260913.xml`，不是 backend regression。查明既有 `sanitize_google_prompt` 同時加安全框架及字詞替換後，改為要求 wire text 完全等於此既有生產轉換，並獨立確認新 JSON 範例逐值不變；沒有變更／移除安全框架。原始凍結 source hash 不變不代表 pre-transport prompt 與 HTTP body 逐字相同，不能混用此兩種保真主張。

Evidence 目錄：`/private/tmp/stock-agent-quality-graph-2330-v4-role-examples-20260913T061445Z/`。backend inventory 前後均 **`be3740a4d3d10322e39e0a50356e03b5ef225bcbcb30813b1e77b76ca317b631`**；來源／路由／env digest 符合已固定值。正式 checkout 前後仍為 clean main **`758242290e795146520f58f68ffa113cac35e52c`**；這是 checkout 證據，沒有另宣稱本輪 API／Worker 健康實測。本輪僅新增 scratch launcher／readback 和更新本文，無 backend 修改、正式資料／artifacts 修改、commit／push／PR／部署／重啟、Gemma 開關或 OOS cohort 改動。

本次授權的隔離測試已結束，完整優化目標未完成。下一步應針對日期／週期引用與段落來源關聯建立可驗證修正，而非反覆追加提示或提高重試數；12 組 paired、每模式至少 30 次先導及發布驗收仍須待合格完整報告證據後推進。

## Google 結構化來源傳遞保真與快取邊界（2026-09-13，離線）

本輪沿用已核准的系統優化範圍，沒有新的 provider 授權或呼叫。上一轮 live 實驗已終止；本輪只分析其原始 capture 並修正可重現的資料傳遞缺陷，不重用剩餘兩次呼叫。

### 證據與修正範圍

- `/private/tmp/test_stock_agent_wire_source_semantics_20260913.py` 將四份 pre-transport prompt 與保存的真實 HTTP body 分別解析為 financial／registry／State JSON，逐值比較。Agent 22 兩次沒有資料值差異；Agent 23 初稿、重寫各有同樣 **2 個 registry label** 被改寫：`當日借券賣出` → `當日借券偏空風險觀察`、`借券賣出餘額` → `借券偏空風險觀察餘額`。其他已比較的 JSON 值保持不變，不宣稱全部來源數字被污染。
- 根因是既有 `sanitize_google_prompt()` 對整串內容套用交易措辭 replacement，無法區分角色指令與 registry 的固定來源名稱。這是已證實的來源傳遞缺陷，**不是已證明的裸日期、來源錯配或模型拒收唯一根因**。
- 新 `backend/google_prompt_sources.py` 僅在既有版本化金融數字契約路徑解析指定 JSON 邊界：必要的 financial JSON／registry JSON、存在時的 AgentState JSON。用 JSON decoder 確認邊界並保留原 bytes，不重新編碼、不改 key／label／quote／value／period／source_ref；引文內跳脫的標題、括號不截斷來源。重複段落／JSON key、缺必要來源、畸形 JSON、非有限值、非物件或不符 registry v1 直接拒收，不退回可悄悄改寫來源的路徑。
- `google_prompt_safety.py` 仍正規化來源之外的任務措辭及既有 system／schema 安全規則，保留資料摘要角色與外層英文 disclaimer，另明示來源資料不是指令、保真不代表內容正確。只对 versioned lane 保持重複 framing 冪等；legacy 與 evidence-request 專用入口未改。不將資料內文字提升為系統權限，不宣稱任意非 JSON 來源段落已逐字保真。
- `llm_semantic_cache.py` 的 exact key／相似 index、`agent_runtime/step_cache.py` 的 step key 加入受影響的 `google-source-json:v1` namespace，且 cache return 前同樣驗證來源。舊資料原地保留，不清空共享 cache；legacy／OpenAI／Anthropic namespace 保持不變。沒有更換路由、調整 similarity threshold、重試數、token cap 或品質 gate。

### 驗證與獨立覆核

- 原始差異 readback **1 passed／0.05 秒**，`/private/tmp/stock-agent-wire-source-semantics-readback-20260913.xml`；最初 scratch 忘記加入 backend import path 為 **1 failed／0.04 秒**（`stock-agent-wire-source-semantics-20260913.xml`），屬檢查工具 setup 問題，不計 faithful red。
- 永久 `tests/test_google_source_fidelity.py` 先 **11 failed／1 passed，1.60 秒**（`stock-agent-google-source-fidelity-red-20260913.xml`），包括來源 key／標籤／引文被改寫及 sync／async／stream 三個真實 transport 入口的 SDK double。首版轉綠過程另發現重複 framing 會改寫自己 disclaimer，**2 failed／26 passed，1.90 秒**（`stock-agent-google-source-fidelity-green-20260913.xml`）；已在新 lane 修正，不覆寫該歷史失敗紀錄。
- 永久 `tests/test_google_source_cache.py` 先 **5 failed／6 passed，1.74 秒**（`stock-agent-google-source-cache-red-20260913.xml`），證明受影響舊 exact／semantic／step cache 會被重用。首版六檔相關套件 **67 passed／2.30 秒**（`stock-agent-google-source-cache-green-20260913.xml`）。八檔 import-boundaries／Gemma evidence batching／graph／numeric／market-context／prompt 整合 **692 passed／17.70 秒**（`stock-agent-source-fidelity-integration-20260913.xml`）；這是以下兩項覆核補強前的證據，不冒稱最終版全庫重跑。
- 獨立覆核重現兩個 P2：新 namespace 的相似快取可在 sanitizer 前返回，繞過畸形來源檢查（sync／async × 3 類畸形，**6 failed／36 passed，JUnit 1.831 秒**，`stock-agent-google-source-review-20260913.xml`）；來源內完整 disclaimer literal 可抑制外層聲明（**1 failed，JUnit 0.063 秒**，`stock-agent-google-source-frame-review-20260913.xml`）。兩者已修正，反例保存到上述永久測試；cache policy 在回傳前執行共用 source validator，versioned safety 分支固定在來源外附加聲明。
- 最終六檔相關 suite 與 reviewer scratch **88 passed／2.33 秒，0 failed／errors／skips**，`/private/tmp/stock-agent-google-source-reviewed-green-20260913.xml`。Reviewer 已讀回結果與實際窄修，確認兩個原 P2 關閉、限定範圍沒有剩餘重大問題，未為確認重跑。Scratch `/private/tmp/test_stock_agent_google_source_review.py` 保留 CRLF／pretty JSON／引號／巢狀重複 key 旁證；主代理已讀回其完整測試內容。

### 最終版凍結提示與容量證據

- `/private/tmp/test_stock_agent_source_fidelity_replay_20260913.py` 在最末 backend 執行 **2 passed／28.16 秒**（`stock-agent-source-fidelity-reviewed-replay-20260913.xml`），前一覆核前回放為 2 passed／28.63 秒，分開保存。入口使用 env-i、明示 `QUALITY_PILOT_BUDGET_PROBE=1`、隔離 runner／禁網／私有 DB，沒有 provider、formal .env、Redis 或正式 DB 存取。
- 已保存的四份實際提示，其三個指定 JSON 區塊與新版輸出 HTTP text 的對應片段逐字相同；原 15 個 capture 檔 hashes 保持不變。原始完整模型回覆仍由同一 numeric gate 分別以 **6／7／3** 項問題拒收，沒有離線改稿或 accepted report。新 wrapped text 的本機 input estimates 為 **62,299／58,351／59,833／63,654**，均低於 64,000；這不是新的 Google usage，也不是 provider tokenizer 上界。
- 12 jobs／369 rows 三個指定 JSON 區塊皆逐字保留；矩陣 `/private/tmp/stock-agent-source-fidelity-reviewed-budget-20260913.json`。對照原 `stock-agent-role-field-budget-20260913.json`，38 份 source hashes、route hash、schema catalog、facts／limits／generation config／preflight 逐項相同，仍 **284 admitted／85 rejected**；沒有放寬門檻或刪除證據。新安全框架相較以舊 sanitizer 重播同一 raw prompt 的本機 wire estimate 差額 **-31 至 +78**，補查 input／TPM／context cap 均無舊→新跨界。run IDs 仍可能造成跨次 raw prompt hashes 不同，不宣稱 exact-prompt model A/B。

最末 backend inventory **`1a500572a44dda53b9687d384a3e00695b7963021e0f42870f3b1cec11e65f04`**；`google_prompt_sources.py` SHA256 **`84260ebc3c0b5be7dac6d6370e9a5bdf08881a3b8bcd7080891400681da59082`**，`google_prompt_safety.py` **`b3ad71e3fb8aa3525b432420eee9423ac6cacf4895c94b52eb1cacb068d38085`**，與覆核相符。此輪修改為四個 backend 檔、兩個永久測試及兩份既有文件；其餘開發樹修改保留。正式 checkout 仍 clean main `758242290e795146520f58f68ffa113cac35e52c`，未 commit／push／PR／部署／重啟，未改正式 artifacts／Gemma 開關／28 組 OOS。

本輪完成的是指定結構化來源的傳遞保真與已測快取邊界，不是日期／週期數字綁定、段落證據語意或四模式成功率驗收。最新 live 結果仍是 `be3740a4…` 的 0 合格完整報告；下一步繼續離線處理已保存原稿的日期／週期與來源關聯缺口，不重啟已結束窗口，不把此次傳遞修復當作再送相同樣本的理由。完整優化目標仍未完成。

## 同筆證據來源與 ASOF 日期綁定（2026-09-13，離線）

沿用已核准優化工作；本輪沒有新 provider 授權或呼叫。設計檢視將範圍限定在既有 typed evidence_items 的可重現契約缺口，不新增通用關鍵字／自然語言事實判定，不替模型修稿，也不把縮短內容算成品質改善。

### 已修改

- 新 `generation_evidence_binding.py` 在同筆 finding／freshness_note／counterevidence 內核對可解析 fact token 是否由該筆 source_refs 支持。保留 exact fact ID、唯一 raw source alias、實際非空 prompt 路徑下的已註冊 descendants；相同數值、相似字首、別筆引用與 prompt 根節點都不能借用。既有 raw schema、unavailable token 與數字 grammar 各自保留職責。
- freshness_note 內的 `metadata:date` 只接受該筆已宣告來源 facts 的共同嚴格 `ASOF:YYYY-MM-DD`。沒有可綁定 fact、任一來源未知、FY／MONTH／OBS 或跨日期，不將抓取日或別筆日期變成共用來源日；可用完整 fact tokens 分別保留期間或定性揭露限制。催化事件日期欄位不受此新來源規則限制。對應 ASOF 不等於證成來源出版時間、無延遲或完整比較資料。
- 共用核對進入 `validate_payload`、accepted receipt、numeric quality／cache restore；最終發布也不能採用舊 passed 收據。保留 raw／normalized／text hashes 與原稿，不刪歷史快取或改寫收據。來源修復補充只在兩種新錯誤出現時加入，避免無關 retry 重複增長。
- 兩份永久測試 `test_evidence_source_binding.py`、`test_evidence_binding_lifecycle.py` 共 45 項；後者保存獨立覆核的 12 個來源身分、legacy／unavailable、sync／async 修復與回滾案例。修改共四個 backend 檔、两個永久測試及兩份既有文件，其他 dirty work 保留。

### 驗證證據

- Faithful RED：**8 failed／6 passed，1.84 秒**，`/private/tmp/stock-agent-evidence-binding-red-20260913.xml`。8 種可解析但錯筆來源／日期原本均被真實 parser 接受；合法 exact aliases、共同日期、定性限制及未來催化控制組正常。
- 初版相關測試 **104 passed／2.31 秒**，生命周期擴充 **122 passed／2.39 秒**；第一版 25 suites **1,018 passed／17.28 秒**（`stock-agent-evidence-binding-integration-20260913.xml`）。這些是後續指引精簡前結果，保留不覆寫。
- 獨立限定覆核 **56 passed／1.94 秒**（`/private/tmp/stock-agent-evidence-binding-review-20260913.xml`、scratch `test_stock_agent_evidence_binding_review.py`），未發現 actionable finding；主代理已讀回全部測試後移植。修復測試隔離無關篇幅／身分規則，generation／normalization／binding／repair transaction 保持真實，provider 為明示本機 double。
- 指引精簡後受影響 8 suites **126 passed／2.62 秒**；最末含永久覆核案例的 26 suites **1,031 passed／17.67 秒，0 failed／errors／skips**，`/private/tmp/stock-agent-evidence-binding-final-integration-20260913.xml`。涵蓋來源、解析、raw schema、no-action／unavailable、legacy、快取、修復、graph、snapshot／partial rerun、決策、發布及 import boundaries，不冒稱全库或 live 重跑。

### 保存原稿與容量回放

- `/private/tmp/test_stock_agent_evidence_binding_replay_20260913.py` 最末在 env-i／隔離 DB／禁網執行 **2 passed／25.81 秒**，`stock-agent-evidence-binding-replay-targeted-20260913.xml`。15 個 capture hashes 保持不變；原三份完整回覆仍拒收，Agent 22 初稿問題數仍 6，Agent 23 初稿由 7 變 8（新增錯筆 fact source），重寫由 3 變 4（新增來源 ASOF 不符）。不是新 provider 輸出或品質下降的估計。
- 明示 synthetic counterfactual：僅在 Agent 23 重寫的深拷貝移除裸日期句「資料截至 2026-09-11。」，保留其 `metadata:date|2026-09-12`。先前規則可通過，新規則因來源實際 ASOF 為 09-11 而拒收；原 capture 完全不改。這證明只修 token 格式仍可掩蓋來源日期錯誤，**不是已修好的模型原稿或合格報告**。讀回 `/private/tmp/stock-agent-evidence-binding-readback-targeted-20260913.json`。
- 當前 12 jobs／369 rows 矩陣 `/private/tmp/stock-agent-evidence-binding-budget-targeted-20260913.json` 對照上一來源保真版，38 份來源 hashes、route hash、schema catalog、facts／limits／generation config／preflight 逐項不變，仍 **284 admitted／85 rejected**；三個指定 JSON 區塊逐字保留。wire estimate 增加 **71–72**，input／TPM／context cap 無跨界；不是 provider tokenizer 上界或配額可用性證據。
- 初版無條件長指引曾讓保存的 Agent 22 retry 本機餘裕只剩 113 tokens；離線結果仍保留 `stock-agent-evidence-binding-replay-20260913.xml`（2 passed／25.72 秒）及其矩陣，不以 pass 掩蓋容量風險。精簡及相關錯誤才補充後，四份原提示的 **instruction-only counterfactual** 估算為 **62,371／58,422／59,976／63,725**，最小餘裕 **275／64,000**，仍偏緊。沒有模擬新模型稿、完整新診斷抽樣或下游內容，不宣稱未來 retry 必能送出；實際 admission 必須繼續拒收超量，不能加 cap 或刪來源。
- 最後窄覆核確認精簡指引及永久案例移植無新問題。Reviewer 一度將 attempt 2 誤歸 Agent 22 而質疑容量少算，雙方直接核對原始 calls.jsonl 後撤回：1／4 為 Agent 22，2／3 為 Agent 23。Scratch 再改為由實際 agent_num、前份完整原稿與重驗 issues 決定是否補充，不硬編 attempt；**1 passed／1.19 秒**（`/private/tmp/stock-agent-evidence-binding-attribution-20260913.xml`），四個估算與原先完全相同。自描述讀回 `stock-agent-evidence-binding-readback-attributed-20260913.json`；此為證據可讀性補強，未修改 backend 或重跑未變更的 369-row 矩陣。本輪覆核無剩餘 actionable finding。

最末 backend inventory **`b346413aebec04b4b146b9dffb68060dffe3f9ecf280baf77dfdc78fb9204bc6`**，四個修改 backend hashes 與最末矩陣讀回一致；binding helper SHA **`4b0f829aa572a1eb88da33e9c55909fd59c09bae035198306b7ed44e3c360dae`** 與獨立覆核相符。正式 checkout 仍 clean main **`758242290e795146520f58f68ffa113cac35e52c`**；僅 checkout 唯讀確認，不另宣稱本輪 API／Worker 健康實測。沒有 provider／正式 DB／artifacts 寫入、commit／push／PR／部署／重啟、Gemma flag 或 OOS 改動。

本輪完成的是 typed 同筆來源與日期關係的核對。自由段落的語意證據關聯、裸數字／週期生成遵循、合格完整 live 報告、四模式 paired／cohort 及發布仍未完成；最新 live 結果仍為 `be3740a4…` 的 0 合格完整報告。後續繼續可執行的離線問題，不重用已結束的六次／四分鐘窗口。

## 已知高風險敘述的有限防護（2026-09-13，離線）

本輪沿用優化授權，沒有新增 provider 呼叫或重啟已結束窗口。先核對現有責任邊界：`content_credibility` 已有決策／信心／來源可信度檢查；`review_pipeline.run_ai_review_pipeline` 未由 repo 其他入口接入，且只傳報告前 30,000 字元而沒有來源上下文，不能冒稱現成的全文來源語意審查。本輪未啟用或修改該 pipeline，也未新增 provider lane。

### 已修改與明示限制

- 新 `research_assertion_contract.py` 只檢查有限中文肯定句型，不是通用 NLP／投資結論認證。缺可驗證的持股比較收據時，不能肯定大戶持股／集中度穩定或升降；缺出版時序收據時，不能肯定資料無延遲。兩個四捨五入後數值、ASOF／fetch_date 或模型宣告不能補成這些收據；沒有臆造穩定閾值。
- 明示融資／融券／借券餘額肯定句，必須在同一 Markdown 段塊有對應 exact semantic 的可解析 fact。借券當日賣出／還券流量不能代替餘額，借券不能代替融資，其他段落或全域 registry 存在該數字也不能借用。此核對只證明指定指標引用，不證明後續槓桿／賣壓因果解釋。
- 檢查實際 prose fields，token 來源名稱與結構化 source_refs 不當敘述。保留真正否定、條件、疑問、明示不採用的同一引文及純主題名詞；不因放進標題／粗體而放過肯定句，也不讓後面的缺資料聲明抹去前面的斷言。
- 共用 predicate 接入 `generation_numeric_payload`、`generation_numeric_runtime` 與 `generation_report_gate`；原稿、舊 passed 收據、品質／cache restore、修復與發布重驗保持一致，raw／hash 不改寫。新錯誤才附短修復指引，不加初始提示、不增 retry、不改來源／路由／schema／gate。
- 新收據及 versioned final 結果明示 `research_validation.policy: known_research_assertions_v1`、`semantic_coverage: not_checked`、三類 checked_families 與有限中文句型限制。無已知違規不等於全文語意通過；未覆蓋改寫、英文、任意主張與因果論述。Legacy 不新增此驗證宣稱。
- 本輪範圍為四個 backend 檔（其中一個新增）、兩個新永久測試檔（71 項）及兩份既有文件，其他開發樹工作保留。

### 可重現反例、覆核與最終驗證

- 凍結來源衍生的 synthetic counterfactual 先只修既有日期／數字格式，保留錯誤自由敘述。兩份仍曾通過真實品質入口並排入可驗證 cache：**2 failed／1 passed，2.03 秒**，`/private/tmp/stock-agent-narrative-source-red-20260913.xml`。這不是原稿已合格，也不是新的 provider 產出；provider／RAG 為明示 double，數字／來源／角色／長度等實際 validators 保持真實。
- 永久行為 RED：**27 failed／8 passed，1.86 秒**（`stock-agent-research-assertions-red-20260913.xml`）；初版相關 **96 passed／2.09 秒**，第一版 28 suites **1,072 passed／18.25 秒**（`stock-agent-research-assertions-integration-20260913.xml`）。分版保留，不冒稱最終全庫。
- 獨立覆核重現 3 個 P2：肯定句的標題豁免、否定／引文免責太寬、明示疑問／未核對誤擋，共 **11 failed**，永久原 35 項仍通過（`stock-agent-research-assertion-review-20260913.xml`）。移植全部反例並擴充四種 prose fields 後，相關 **142 passed／2.41 秒**；覆核後的中間 28 suites **1,101 passed／18.71 秒**（`stock-agent-research-assertions-final-integration-20260913.xml`）。
- 再覆核發現直接回歸：「大戶持股穩定性檢查」的主題名詞被當成肯定句。永久 RED **1 failed／64 passed，1.98 秒**（`stock-agent-research-assertions-topic-red-20260913.xml`）；僅將 `穩定` 謂語限縮為 `穩定(?!性)`，不恢復標題全面豁免。含 reviewer scratch 的相關 **156 passed／2.38 秒**（`stock-agent-research-assertions-topic-green-20260913.xml`）。Reviewer 讀回實際一行修正、XML 與 SHA，確認最後 P2 及原反例關閉，限定範圍無剩餘 finding；未為確認重跑。
- 最末 28 suites **1,102 passed／18.31 秒，0 failed／errors／skips**，`/private/tmp/stock-agent-research-assertions-topic-final-integration-20260913.xml`。涵蓋新 predicate／生命週期、來源／日期、raw schema、repair、cache、Google source preservation、graph／partial rerun、final publication、legacy／fallback 及 import boundaries；不是全庫或 live 成功率測量。

### 不可變原稿回放與容量

- 最末 `/private/tmp/test_stock_agent_research_assertions_replay_20260913.py` 在 env-i、私有 DB、禁網執行 **3 passed／18.22 秒**，`stock-agent-research-assertions-replay-final-20260913.xml`。15 個原 capture hashes 保持不變；原三份完整模型稿仍拒收，按實際角色歸屬：attempt 1／Agent 22 有 7 項、attempt 2／Agent 23 有 9 項、attempt 3／Agent 23 重寫有 7 項。讀回 `stock-agent-research-assertions-readback-final-20260913.json`。新增攔截不是模型品質提高或下降估計。
- 真實品質入口拒收保留已知壞敘述的來源衍生副本。Positive control 在另一份副本明示替換兩段不受支持的敘述、保留每一原 fact token 後可通過，但仍 `semantic_coverage: not_checked`；不是自動修稿、provider 新稿或合格完整研報。
- 同一保存稿重新產生**完整目前修復診斷**（不僅加一段指引），四份 Google wire 本機估算為 **62,371／58,422／60,338／63,903**；Agent 22 retry 距 64,000 僅 **97 tokens**。前節 275-token 餘裕是 instruction-only counterfactual，兩者方法不同，不混稱同條件退步。指定 financial／registry／State JSON 逐字不變。此回放不模擬新模型輸出，不是 provider tokenizer 上界，未來 retry 超量仍須拒收；不得加 cap、刪證據或把「低於上限」等同可靠容量。
- 最末 12 jobs／369 rows 矩陣 `stock-agent-research-assertions-budget-final-20260913.json` 對照 `b346413a…`：38 份來源 hashes、route hash、schema catalog、facts／limits／generation config／preflight／估計 input tokens 不變，仍 **284 admitted／85 rejected**。初始提示不變；這不是 369 次呼叫或四模式品質驗收。覆核前兩次 3-test replay 與矩陣另留 `stock-agent-research-assertions-replay-20260913.xml`、`stock-agent-research-assertions-replay-reviewed-20260913.xml`，不覆寫。

最末 backend inventory **`a4847a2ae7c62bad0a0b258c1a4e13ac287fcdaadfe857760f196a9c9b2c3835`**，四個本輪 backend hashes 與最末矩陣讀回一致；新 helper SHA **`e40d431dd99d3b6fe3002043cda4569f4279464c68073672a56057783ebeb077`** 與獨立覆核相同。正式 checkout 仍 clean main **`758242290e795146520f58f68ffa113cac35e52c`**，僅 checkout 唯讀，不另宣稱本輪 API／Worker 健康實測。沒有 provider／正式 DB／artifacts 寫入、commit／push／PR／部署／重啟、Gemma flag 或 28 組 OOS 改動。

本輪只完成已重現類別的有限敘述防護。最新 live 仍是 14:14 的 **0 合格完整報告／1 個隔離 job**；全文來源語意、模型數字／日期遵循、新設定四模式 paired／cohort 與發布驗收均未完成。任何下一次 provider 實測必須取得新的明確有界授權，不重用已結束窗口的剩餘次數。

## 候選版本全庫補驗與容量定位（2026-09-13）

本輪為內部 goal 續作，沒有新的真人 Gemini 授權；上輪已完成實作與限定覆核，屬實質進展，不是尚在執行的 provider job。此次先診斷 97-token 修復餘裕，再補目前候選版本尚缺的全庫跨模組回歸，沒有為取得綠燈另改來源或編碼協定。

### 容量定位：未修改提示

- `/private/tmp/test_stock_agent_repair_capacity_sections_20260913.py` 唯讀分析保存的四份 14:14 提示，隔離 runner **1 passed／0.11 秒**，JUnit `stock-agent-repair-capacity-sections-20260913.xml`。15 個 capture hashes 不變。這只定位原有來源區塊成本，不是新模型呼叫、當前完整 feedback 的第二次估算或可用性證明。
- Agent 22 的 financial／State／registry JSON 分別為 **44,913／3,676／60,185 字元**，各自本機估算 **22,678／1,790／27,665 tokens**；四次中的 Agent 22 修復提示在來源區塊之外為 9,034 字元。分段估算不可直接加總成含 system／schema 的完整請求，也不等於 provider usage。
- Registry 已使用可逆分組表，financial／State 已有完整資料表編碼；主要成本不是單次修復說明。進一步壓縮 registry 需評估新表示法對模型理解的影響，不能視為無風險去字。本輪沒有新增編碼、刪證據、增 cap 或 retry；前節的**目前完整 feedback 餘裕仍為 97 tokens**，沒有宣稱已改善此風險。

### 全庫非 live 原始結果與唯一修正

- 同一 backend inventory **`a4847a2ae7c62bad0a0b258c1a4e13ac287fcdaadfe857760f196a9c9b2c3835`**，15:48（Asia/Taipei）開始，在 env-i／私有 SQLite／禁網 runner 執行全 `tests -m 'not live'`，另 deselect 已知 sandbox 無法啟動的 Chromium launch-only preflight。原生 session `19146` 正常結束、exit 1；沒有因觀察等待而重啟。
- **11,544 passed／1 failed／24 skipped／2 deselected／75 subtests passed／3 warnings，1101.04 秒**。原始 JUnit `/private/tmp/stock-agent-current-candidate-full-nonlive-20260913T0748Z.xml`，XML tests=11,644 包含失敗、子測試與跳過，不當成另一個成功數字。
- 唯一失敗 `test_hcs_plus_round2_contract_coverage_map_has_observed_counts`：既有規則掃描到含契約詞的 tests 檔案 36 個，文件仍記 35；backend 實際／文件同為 30。新增 `test_google_source_fidelity.py` 含來源保真反例，應計入同一文字出現統計。只更新 `docs/hcs-plus-optimization-state.md` 的現行數字與有日期的範圍註記，保留歷史紀錄、原測試、掃描規則及所有 backend；不是改斷言或 gate 迎合結果。
- 修正後 HCS state／docs contract／Google source fidelity 三檔 **148 passed／4.11 秒，0 failed／errors／skips**，`/private/tmp/stock-agent-current-candidate-doc-count-green-20260913.xml`。沒有重新跑未受文件數字影響的全庫，也不覆寫原 1 failed 或將部分補驗冒稱另一輪全庫零失敗。
- 24 skips 已讀回：PostgreSQL collection、公開來源 opt-in、live commercial browser、未指定 artifact／checkpoint 複本、sandbox Chromium、Chart.js 與 Redis/RQ smoke 等。2 deselected 為 live test 與 launch-only preflight；後者的測試／script／manifest 仍與 HEAD 相同，先前單獨提權通過證據保持歷史身分，本輪沒有重跑或宣稱目前瀏覽器健康。3 warnings 為既有 RQ UTC API 與兩個 legacy sync 入口 deprecation。

### 四模式凍結流程與狀態保存

- 明示 `QUALITY_PILOT_GRAPH_PROBE=1`、相同 env-i／禁網／私有 DB，原三標的四模式 **12 passed／13.16 秒**，`/private/tmp/stock-agent-current-candidate-frozen-graphs-20260913T0751Z.xml`。使用真實 graph／adapter／InMemorySaver、final-audit generation gate 與 snapshot replay；provider 及部分服務為明示 offline doubles，結果只允許 `diagnostic_no_action`，沒有 provider usage 或正式報告發布。
- 此取樣快照 UTF-8 為 **773,779–1,876,561 bytes**，均未超過 2,097,152-byte soft limit；不是未來完整模型研報的容量保證。另按既有矩陣 manifest 讀回全部 **38 份原始來源 hashes** 一致。
- 全庫前後 backend inventory 與四個上輪修改 hashes 保持一致；本輪無 backend／repo tests 修改，只修現行 HCS 統計及本交付紀錄，新增一份 scratch 容量定位測試。正式 checkout 仍為 clean main `758242290e795146520f58f68ffa113cac35e52c`；runtime doctor 只確認 canonical 路徑與檔案存在性，不當 API／Worker 健康證明。

新一輪真實 Gemini 測試仍待上一則提出的明確有界授權；本輪沒有 provider 呼叫、正式 DB／artifacts 寫入、commit／push／PR／部署／重啟，Gemma OFF 與原 28 組 OOS 不變。全庫補驗與文件修正不取代合格完整 live 報告、12 組 paired、每模式至少 30 次 cohort 或發布驗收，完整目標仍未完成。

## 目前候選版的明確核准實測（2026-09-13 16:19）

使用者本次真人回覆「核准」，承接新一輪 2330.TW／v4 凍結研究資料與提示送至既有 Google Gemini 路由、既有金鑰只用於 API 驗證、最多 6 次／4 分鐘的範圍。沒有把內部續作或前次剩餘額度當新授權。新的單次 launcher 先通過無網路預檢，使用 exclusive consumed receipt 防止同一授權重開；原三份 graph／safety／wire harness hashes 未變。

### 範圍與版本

- 核心離線矩陣涵蓋 742 個 Python／prompt JSON 檔，SHA256 `a4847a2ae7c62bad0a0b258c1a4e13ac287fcdaadfe857760f196a9c9b2c3835`；live 工具另納入路由、靜態資產等，共 909 檔，SHA256 `0462841e86a3e802e84ac99eb5b71bceb087681fbce7be2e624a9967258cd487`。二者範圍不同，不是候選程式突然變動。最初把核心摘要傳給完整 inventory 預檢遭拒，未啟動模型；核對全 742 檔、額外檔案與歷史遮罩欄位後，分別固定兩種摘要，沒有移除任何版本護欄。測試前後兩份 inventory 均一致。
- 唯一輸入為原 `analysis-2330tw-v4-1789180457187-a810b422/database-job.json`，SHA256 `cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd`；路由 SHA256 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`，明示 env digest 與上次一致。每次實際 HTTP 前重驗來源／路由／完整程式與 request body 金鑰排除。
- 沿用私有 DB／checkpoint／artifacts、共用 Redis 配額 guard、6 transport／6 physical HTTP 雙上限、inner 220 秒／outer 240 秒及既有 process-only bounded-thinking override。不重放舊草稿或 receipt；RAG 原索引不可得、外部市場更新停用，因此不是逐字相同提示的 paired 對照。

### 實際結果

- 開始 `1789287596.8504572`（16:19:56.850 Taipei），硬截止 `1789287836.8504572`；原生 session `2049` 已正常結束，**24.783 秒、exit 2**，沒有觸發時間或呼叫上限。沒有重送，剩餘兩次不再使用。
- **4 次 HTTP 200／4 attempts；3 份完整 STOP JSON／4 attempts；0 合格完整報告／1 隔離 job**。Agent 22 的 attempt 1／4 為 `gemini-3.6-flash`，Agent 23 的 attempt 2／3 為 `gemini-3-flash-preview`；provider 自報標籤相同，但不是對其內部模型的獨立認證。這次與 14:14 Lite 路由不同，不能直接比較品質／推定同模型成功率提高。
- Agent 22 重写後仍不符合來源／數字契約，觸發 `AgentQualityDraftError`，graph 取消尚在串流的 Agent 23 attempt 3。取消回應不能計完整成功；沒有 429、5xx、MAX_TOKENS 或逾時證據，也不是等待市場成熟。未到 Agent 24、最終稽核或 renderer，checkpoint 的 accepted analyses／structured outputs 為空、publication=null，未建立正式報告。
- 四個 HTTP 回應都有 explicit usage snapshot，合計 input 223,098／output 5,516／total 228,614 tokens，含取消串流最後觀測值；不是計費稽核、最終取消用量或本機預算權益。3 次完整回應耗時 p50 10.409 秒／p95 11.207 秒，仅此小樣本。

### 原稿與傳遞保真讀回

| 完整原稿 | 角色 | 原始 schema | 來源／數字問題 |
| --- | --- | --- | --- |
| attempt 1 | Agent 22 首稿 | 通過 | 3：共同 ASOF 不一致 1、反證 fact 未列於同筆 source_refs 2 |
| attempt 2 | Agent 23 首稿 | 通過 | 20：裸數字 12、token 非獨立行 3、無法解析／相容 fact 2、其衍生 invalid token 2、同筆日期 1 |
| attempt 4 | Agent 22 重寫 | 通過 | 26：新裸數字 23、反證 fact 未列於同筆 source_refs 3 |

- 上表是以不可變原稿和實際提示重建 registry 的離線重驗；重疊／衍生錯誤不當成 20 個獨立事實錯誤，也不代表整份敘述語意已驗證。首稿引用格式拒收與實質事實錯誤須分開；不能把訊息「結構不完整」解讀成這三份 JSON 解析失敗。Agent 22 的修復提示已包含全部首稿 3 項診斷，但新稿沒有遵循同筆反證引用要求，還加入未綁定的代碼／週期數字。
- 每次請求 financial／State／registry 三個指定來源 JSON 區塊都與送出前提示**逐字一致（4／4）**；這證明此邊界的傳遞保真，不證明模型理解或來源語意關聯。
- 四次完整 wire 本機輸入估算依序 **62,371／58,513／60,207／63,847**；對 64,000 cap 餘裕 **1,629／5,487／3,793／153**。provider 回報的 tokenizer 值另列，不以本機估算當 provider 限額。153-token 餘裕仍很薄，不保證未來修復可送出；本輪未增 cap、刪來源或延長重試。
- 隔離禁網讀回 **1 passed／1.14 秒**，原生 session `35166` exit 0；JUnit `/private/tmp/stock-agent-current-guard-readback-20260913T081956Z.xml`，診斷 `/private/tmp/stock-agent-current-guard-readback-20260913T081956Z.json`。完整 capture hashes 與原 source hash 不變；不是新增一次 live 成功或完整語意測試。

證據目錄：`/private/tmp/stock-agent-quality-graph-2330-v4-current-guard-20260913T081956Z/`。本輪只新增 scratch launcher／讀回測試與私有證據、更新本文件，沒有 backend／repo tests 修改。正式 checkout 仍為 clean main `758242290e795146520f58f68ffa113cac35e52c`；沒有部署、重啟、正式 DB／artifacts 寫入、Gemma 開關或原 28 OOS 改動。未重新跑未變更的全庫離線測試，沿用同版本前述證據。

**本次核准的隔離實測已結束，完整優化計畫尚未完成。** 建議下個限定工程切片評估 field-scoped 修復與不可變內容綁定，先用這批壞稿做離線正反例及完整重驗，再申請有界 live 驗證。四模式 12 組 paired、每模式至少 30 次 cohort 與發布 canary 仍待完成；不因這次 HTTP 成功就擴大送件或直接發布。

## 有界引用／日期局部修復候選（2026-09-13，離線完成）

承接上述實測證據，在隔離 DEV 實作局部修復；**沒有新增 provider 呼叫**，已結束的 6 次／4 分鐘授權窗口不重開，也不消費其剩餘兩次。正式 checkout 仍為 clean main `758242290e795146520f58f68ffa113cac35e52c`，本節不是部署／重啟或 live 品質成功證明。

### 已修改

- `evidence_metadata_repair.py`／`agent_runtime/evidence_metadata_repair.py`：僅 Agent 22／23、完整原始 schema 且全部錯誤均為 `evidence_fact_not_in_item_sources`／`evidence_source_date_mismatch` 才可啟用。原 receipt 與重新計算的 raw-decision／來源／數字／日期檢查都納入 eligibility；已修過、來源變動、未綁定或其他錯誤不走局部路徑。
- 模型必須實際回覆完整 patch envelope，含綁定原稿／來源的 `repair_id` 與 exact target indexes。`source_refs` 只能保留原順序並追加原稿已使用但漏列的 exact facts；`freshness_note` 只能逐字回覆 `allowed_freshness_note`，只替換原日期 token，未知／異期明示限制。不可改 finding、反證、正文、信心、數值、決策或其他資料。預檢確認 exact append 不超過原 schema 六個 refs／note 2,000 字限制，不對已知無解的局部修復送件；不放寬 schema、不截斷引用。
- `quality_completion` 沿用既有一次結構修復的 router／quota／取消路徑；patch prompt 以局部任務取代重複的全篇產稿指令，financial／State／registry 三個來源 JSON 與解碼規則完整保留。Google 傳輸也逐字保留局部目標 JSON；marker 本身不能開啟 patch mode，process-local scope 不跨非同步任務。
- 合併稿完整重跑現有 gates；`raw_payload_kind=evidence_metadata_patch.v1` 與 `field_repair` 保存原稿、原模型資訊、原 binding、原始模型 patch、來源 digest 與合併 hash。accepted／cache／snapshot replay／發布路徑重新組合及驗證此鏈，不能僅信任 passed 標籤。這些是有限 schema／數字／引用／日期／已知句型 checks，`semantic_coverage: not_checked` 不變。
- 取消或錯誤撤回該 Agent 的候選 receipt／structured／pending cache，保留其他 Agent、已發生的 usage／events 與原稿失敗證據；checkpoint 的文字與回復後原稿收據一致。草稿 SQLite 還原保存安全的原稿模型資訊，明示 cache、清該 Agent 的 int／str 舊用量，不清歷史事件。重讀相同草稿不增 checkpoint 版本或冒稱新作者。
- `model_composition.py` 將受限組合種類與匿名路由標籤傳到 response/error event、node/job telemetry、SSE、snapshot 及真實 sync／async cache-hit。品質面板另列 `composite_qualified`，與首選／備援使用相同可觀測 Agent 分母，但不把最後補丁模型算成整稿作者；快取與後續未完成嘗試不能沿用前次模型成功。未暴露原稿、patch 或金鑰到公開模型 metadata。

### 已驗證

所有執行均使用 `env -i`、`PYTHONDONTWRITEBYTECODE=1`、正式 venv 的 Python 與 `tests/run_prompt_boundary_tests.py`；禁網、私有 SQLite，沒有正式 DB／Redis／provider 或 artifacts 寫入。原始反例與失敗結果保留，未修改 assertion 放寬品質。

| 驗證 | 結果與證據 |
| --- | --- |
| 局部欄位限制、來源保真、cache 篡改等早期邊界 | 125 passed；`/private/tmp/stock-agent-evidence-metadata-repair-boundaries-v2-20260913.xml`，後續整合選集包含其相關測試，不相加當總數 |
| 大範圍 generation／numeric／quality／source／schema／workflow／telemetry／UI／architecture 回歸 | **2,546 passed、0 failed／errors／skips、2 既有 deprecation warnings，237.89 秒**；`/private/tmp/stock-agent-metadata-repair-integrated-20260913.xml`。執行期间完成最後兩個 cache 邊界修正，因此不能把此結果單獨當最後版本完整驗證 |
| 最後 cache 用量與品質失效修正後相關補驗 | **106 passed，3.52 秒**；`/private/tmp/stock-agent-metadata-repair-cache-transition-green-20260913.xml`，涵蓋新增反例、完整 draft resume、model identity、metrics、UI 與 telemetry；與上列重疊，不相加 |
| 原三標的四模式凍結 graph／checkpoint／snapshot | **12 passed，13.21 秒**；`/private/tmp/stock-agent-metadata-repair-frozen-graphs-20260913.xml`。真 graph／adapter／InMemorySaver／generation gate，provider 等為明示離線 doubles，只驗證 `diagnostic_no_action`，不是 12 組 live paired |
| 真實 Agent 22 首稿＋明示 synthetic patch | **1 passed，1.87 秒**；`/private/tmp/stock-agent-metadata-patch-frozen-final-20260913.xml`，詳下方 |
| 獨立覆核 | 原取消、eligibility、composition、refs 上限及 checkpoint 舊用量缺口均已修正並重驗；最後實際 SQLite／telemetry 用量反例 1 passed／1 deselected（另一已驗證情境），`/private/tmp/metadata-repair-independent-checkpoint-usage-closed-20260913.xml`。真 sync／async cache runner 覆核通過；曾因 scratch 省略 caller 參數造成的 cache finding 已撤回，不列為真缺陷 |

最後核心 inventory 涵蓋 **745 個 Python／prompt JSON 檔**，SHA256 `29189c5abe70b067318546ac9041cb5412c4d240cba098850d460d92d4206b05`；每檔 hash 保存於 `/private/tmp/stock-agent-metadata-patch-frozen-final-20260913.json`。此範圍不包含 UI；本次已測的 `backend/static/report_quality_panel.js` SHA256 為 `db4066654f2f24b5744f04139145368ff4ae3d0c3fd2086247a15df483c9af68`。不是 16:19 舊版 `a4847a2a…` 的 live 證據。

17:05 最後文件／架構／局部修復／持久化／UI 讀回選集 **76 passed，2.99 秒**，`/private/tmp/stock-agent-metadata-repair-final-readback-20260913.xml`；再次讀回上述 JUnit 的 failures／errors／skipped 均為零、745 檔 inventory 全部未變，`git diff --check` 通過。這仍是按修改風險選取的非 live 驗證，不冒稱重跑最後版本全庫。

### 凍結原稿回放結果與限制

以 16:19 capture 的 Agent 22 attempt 1 原文及實際 prompt 重建綁定 registry；原 3 項問題仍可重現。**測試程式產生的 synthetic patch 不是模型新回覆**，僅驗證可滿足性與保存邊界。它只修改 `evidence_items[0/1].source_refs/freshness_note` 四個欄位，合併稿通過既有檢查，其餘原始 JSON、反證、正文、數值、決策與信心完全不變。

局部提示 financial／State／registry JSON 與實際原提示三段逐字相同，Google 安全轉換後亦相同；本機輸入估算 **54,795，對 64,000 cap 餘裕 9,205**。這不是 provider tokenizer 或同模型成功率改善。原 capture 全檔 hashes、原 `database-job.json` hash `cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd` 均不變；未回補市場來源、未重建正式報告。

**本切片離線完成，但完整優化仍未完成。** 下一步為新的明確有界 Gemini live 驗證，檢查模型是否遵循 patch，以及 Agent 23／Agent 24／final audit 能否繼續到合格完整報告；後續仍需四模式 12 組 paired、每模式至少 30 次 cohort、scoped integration／部署 canary。這批未 commit／push／PR／部署／重啟；Gemma OFF、原 28 組 OOS 與市場成熟條件不變。

## 不可核驗來源的修復說明補強（2026-09-13，離線）

16:19 Agent 23 原稿引用的兩個 TDCC 持股比例，在凍結 registry 與實際提示中已明列 unavailable，原因為 `raw_tier_rows_and_tier_boundaries_not_preserved`。不是引用拼字錯誤，不回補原始分級、不升格成可核驗 fact。

- `generation_numeric_runtime.numeric_repair_detail()` 僅在 rejected receipt／目前資料／Agent／registry binding 相符，且 exact reference 確實位於 unavailable 清單時，附上 `registry_status=unavailable_fact` 與有界原因代碼；不接受任意錯誤文字、不模糊比對。六個診斷樣本及原稿全量驗證保持不變。
- 新增反例先得 1 failed／4 passed／16 deselected，修正後相關 integration **294 passed，3.50 秒**；`/private/tmp/stock-agent-unavailable-feedback-integrated-20260913.xml`。原稿回放 **1 passed，1.93 秒**；`/private/tmp/stock-agent-unavailable-feedback-frozen-20260913.xml`。原稿仍有 20 項並拒收，沒有 synthetic 合格報告；六個樣本中一個 exact TDCC reference 帶出原因，其他完整 issues 不刪除。
- 保存的 Agent 23 retry 完整提示本機估算從 60,207 到 60,392（增加 185、距 64,000 餘裕 3,608），financial／State／registry JSON 逐字不變，原 capture／source hashes 不變。這只是離線回放，不是 provider tokenizer 或遵循率改善。
- 相對前節 `29189c5a…` 的 745 檔核心 inventory，只有 `backend/generation_numeric_runtime.py` 改變，SHA256 `e0465b2eb156f7cf9367ac27ceb4b1acb1fb9feabf4c1e6b1e176f28719db04e`。新核心 SHA256 **`914d77e6a30dd765048aadf85cec257f86a89c8f95ac8efc639eda320bde55e0`**；既有大範圍驗證與本次相關補驗分開記錄，沒有冒稱最後版本全庫重跑。

## 局部修復候選的明確核准實測（2026-09-13 17:20）

使用者再次真人回覆「核准」，承接下一輪 2330.TW／v4 凍結資料與提示送至既有 Google Gemini 路由、既有金鑰僅供 API 驗證、最多 6 次／4 分鐘。建立獨立 launcher 與 exclusive consumed receipt，沒有重開 16:19 的授權。無網路預檢核對上述核心、294＋1 測試結果、來源／路由／環境與原三個 harness hashes。

### 實際執行與版本

- 核心 745 檔 SHA256 `914d77e6a30dd765048aadf85cec257f86a89c8f95ac8efc639eda320bde55e0`；完整 backend inventory 912 檔 SHA256 **`881996a1289e206e013c87bb728f5738a5d477577c279fd0e1fc2c4b3b36d59f`**。兩者範圍不同，測試前後皆不變。
- 來源仍是原 `analysis-2330tw-v4-1789180457187-a810b422/database-job.json`，SHA256 `cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd`；路由 SHA256 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`。未導入歷史草稿或 receipt，未更新外部市場／RAG，非完全相同提示的 paired 測試。
- 17:20:42.654 開始，原生 session `96334` 結束、exit 2，**15.437 秒**。4 transport／4 HTTP，未達 6 次或 240 秒限制；無重新送件，窗口結束後剩餘兩次不再使用。inner 220 秒／outer 240 秒、私有 SQLite／checkpoint／artifacts、既有共用 Redis 配額 guard 與原 process-only thinking override 保留。
- Gemma 在 HTTP 前被既有 input capacity 擋下；3.6／Preview／3.8 路由被共用 circuit 冷卻狀態跳過，沒有清除或繞過。四次實際模型均為 **`gemini-3.5-flash-lite`**，provider 回傳標籤同名，非獨立身分認證。不能將本次結果與 16:19 的不同模型當成同模型成功率對照；本次紀錄不足以判定既有 circuit 的原始觸發原因或 Google authoritative quota。
- **4 次 HTTP 200，3 份完整 STOP JSON，0 合格完整報告／1 個隔離 job**。Agent 23 重寫未過品質契約引發 `AgentQualityDraftError`，取消 Agent 22 的第四次串流；非本輪 429／5xx／MAX_TOKENS／逾時或市場成熟阻擋。未進 Agent 24、final audit 或 renderer，checkpoint accepted analyses／structured outputs 為空，publication=null，formal_publication=false。
- 四個 HTTP 的最後 explicit usage snapshot 合計 input **222,629**／output **2,945**／total **225,574**，另觀測 cached input 32,001；包括取消中的最後快照，不是最終帳單。完整回應僅三筆，p50 6.133 秒／p95 7.171 秒，不外推母體。

### 不可變原稿讀回

| 回覆 | 原始 schema | 拒收問題 | 局部 metadata patch |
| --- | --- | --- | --- |
| Agent 22 首稿，attempt 1 | 通過 | 6 項裸期間數字：均線日數與均量期間 | 不符合；不是僅引用／日期錯誤 |
| Agent 23 首稿，attempt 2 | 通過 | 2 項裸 `30` 日觀察窗數字 | 不符合 |
| Agent 23 重寫，attempt 3 | 通過 | 4 項裸期間數字、1 項反證 fact 未列於同筆 source_refs | 不符合 |

所有請求均未進 `evidence_metadata_patch.v1` 路徑，不能把這輪算成局部補丁模型遵循實驗成功或失敗。新 unavailable 原因說明也未被本輪相應錯誤觸發；這次三份完整稿未使用那兩個 TDCC fact token，不證明自由敘述中的持股／延遲等主張有根據。`semantic_coverage: not_checked` 仍是重大限制。

`/private/tmp/test_stock_agent_metadata_live_readback_20260913.py` 以實際提示及原凍結資料重建 registry、重算上述診斷與 patch eligibility；完整 source／capture hashes 保持不變。四次 financial／State／registry JSON 逐字保真（4／4）；本機 wire 輸入估算 **62,372／58,423／59,739／63,764**，對 64,000 的餘裕 **1,628／5,577／4,261／236**。不是 provider tokenizer 或未來 retry 容量保證。

初次 scratch 讀回誤把 journal 的 `credential_body_check` 當未遮罩值而失敗，原 JUnit `stock-agent-metadata-live-readback-20260913T092042Z.xml` 保留。核對原安全 writer 對 credential-named 欄位一律遮罩，修正讀回預期為 `[redacted]`，不修改 provider 原稿、harness 或 gate；每次實際 dispatch 前的 body 檢查仍由固定 hash 的 harness 執行，遮罩欄位本身不當成獨立驗證證據。最終禁網隔離讀回 **1 passed，1.10 秒**，`/private/tmp/stock-agent-metadata-live-readback-green-20260913T092042Z.xml`，明細 `stock-agent-metadata-live-readback-20260913T092042Z.json`。

證據目錄：`/private/tmp/stock-agent-quality-graph-2330-v4-metadata-repair-20260913T092042Z/`。本次只新增 scratch launcher／讀回與私有證據、同步文件；backend 與 repo tests 沒有新增修改，正式仍 clean main `758242290e795146520f58f68ffa113cac35e52c`。未 commit／push／PR／部署／重啟，未改正式 DB／artifacts、Gemma OFF 或 28 OOS。

**本次已核准測試已完成，完整優化尚未完成。** 建議下一個限定工程切片評估「來源綁定的期間表達」：精確對應 SMA／均量與法人觀察窗，不以全文 regex 豁免或中文數字迴避檢查，不改金融數值。以本次壞稿做正反例，再驗來源／schema／publication 邊界；不要先擴大 cohort 或反覆重寫整稿。新的模型呼叫仍需新的有界授權；四模式 12 組 paired、每模式至少 30 次 cohort 與正式发布 canary 均未完成。

## 來源綁定的期間語法（2026-09-13 17:42，DEV 離線完成）

本輪為內部 goal 續作，承接已授權工程優化；上一輪真人核准的 6 次／4 分鐘 Gemini 窗口已結束，沒有新呼叫、重開 launcher 或消費剩餘次數。

### 行為與不可跨越邊界

- 新增 `source_bound_periods.py`，由 `numeric_claim_contract` 僅傳入已解析、單位相容、獨立成行的 fact token。prose 行必須緊接有效 citation 行；空行、另一 prose 行、標題或另一欄位不可借用。不是任意日期／金融數值的全域豁免，也不將 metadata／decision／unavailable token 當來源。
- 有限格式涵蓋 `5日、10日、20日與60日均線`、`20日均量`、同 clause 明確法人主詞的 `近 N 個交易日`／`最近 N 個已觀測交易日`。技術來源限已重播的 SMA／成交量計算 catalog 與 input digest；日數是保存日線的計算根數，不聲稱完整交易日曆。法人來源限 FinMind exact record 與 typed observation_window；已知完整性／原始買賣未重播限制保留，不把近五日、較長窗、日曆日或有限明示未來語氣互換。
- 每個被接受的期間保存 exact offset、原数字、value、basis、source_fact_ids、path 與有限語意範圍。原文字與 fact／金融數字完全不改寫。`source_bound_periods` 是獨立計數，不增加 `verified` 或金融數值 denominator；新舊分類的統計不可拿來冒稱模型本身準確率提高。
- system／user／retry／reflection 指引同步這個限定格式；legacy 無 generation marker 不安裝新收據。`generation_numeric_payload` 保存 evidence，`generation_report_gate` 從 raw／來源重算期間，不信任篡改的 counter。schema、同筆引用、日期、決策及全文已知 assertion checks 維持；可綁期間不代表 surrounding trend／因果／未來價格獲認證。

### 可追溯驗證

所有測試皆由 env-i、禁網、私有 SQLite runner 執行，沒有正式 DB 或 provider 寫入。

| 範圍 | 結果與證據 |
| --- | --- |
| 原有合法期間被拒收的 faithful red | **5 failed／35 passed，1.37 秒**；`/private/tmp/stock-agent-source-bound-periods-red-20260913.xml` |
| 第一批 numeric／parser／publication／architecture | 124 passed，2.52 秒；`stock-agent-source-bound-periods-green-20260913.xml` |
| 獨立覆核反例 | 重現跨句借法人、後置未來語氣與 heading 邊界；repo red 4 failed／40 passed，`stock-agent-source-bound-periods-review-red-20260913.xml`，修正後相關 90 passed |
| 獨立重驗及 cache／lifecycle | **76 passed，2.44 秒**；`/private/tmp/stock-agent-period-independent-review-closed-20260913.xml`，兩項 findings 均關閉，測前後四個核心檔案 hashes 不變 |
| 最後 numeric／generation／schema／binding／repair／snapshot／source-cache／workflow／architecture／metrics 整合 | **953 passed／0 failed／errors／skips，8.21 秒**；`/private/tmp/stock-agent-source-bound-periods-integrated-final-20260913.xml`。前一輪 951 passed／2 failed 保留；僅兩個舊 system 文案斷言需同步，改為限定期間規則及其餘定性標題、另增加不可跨段借引用斷言，沒有放寬拒收測試 |
| 三標的四模式凍結 graph／checkpoint／snapshot | **12 passed，12.34 秒**；`/private/tmp/stock-agent-source-bound-periods-graphs-20260913.xml`，provider 為明示 doubles，只有 diagnostic_no_action，不是 live paired |
| 原十二份凍結資料的輸入容量矩陣 | **1 passed，16.53 秒**；`stock-agent-source-bound-periods-budget-20260913.xml/json`，12 jobs／369 rows／284 admitted／85 rejected。38 份原始來源 hashes、facts／limits／generation configs／schema catalog／路由及每列 preflight 狀態與既有矩陣一致；提示有變，估算不是 provider tokenizer 或配額可用性證明 |

本節 17:42 核心 inventory **746 個 Python／prompt JSON 檔**，SHA256 **`fd4c7561628362fbd590fa0ebdf426370b65ec0e1a8990029521803509755802`**，逐檔 hashes 同存 matrix 與下列原稿回放 JSON。這是新候選，不是 17:20 live 的 `914d77e6…`。上列測試有重疊，不相加當全庫總數；後續全庫與排版補驗另見下一節。

### 原 17:20 回覆完整保留的離線重验

`/private/tmp/test_stock_agent_period_frozen_20260913.py` 以原始提示／完整凍結資料重建 registry，走真 `process_agent_response`；未重寫 raw JSON、未建立新 provider 回覆、未產製報告。初次 scratch 對 Agent 23 重寫稿預期過寬：以為沒有法人主詞的 counterevidence 也可綁期間；測試如實拒收，原失敗 JUnit 保留。修正預期符合已明示的同 clause 邊界，沒有改 code 放行，最終 **1 passed，1.89 秒**，`/private/tmp/stock-agent-period-frozen-final-20260913.xml`，明細 `stock-agent-period-frozen-20260913.json`。

| 原稿 | 舊問題數 | 新有限檢查 | 限制 |
| --- | --- | --- | --- |
| Agent 22 首稿 | 6 | 綁定 5 個期間，仍拒收 1 項 | 最後技術劇本的均量日數沒有緊鄰引用，不能跨段借來源 |
| Agent 23 首稿 | 2 | 綁定 2 個期間，有限 schema／numeric checks 通過 | 不是完整語意通過；原稿的持股區間與「延遲符合規範」等自由敘述仍未獨立核證 |
| Agent 23 重寫稿 | 5 | 綁定 1 個期間，仍拒收 4 項 | 其餘期間缺緊鄰來源／同 clause 主詞，另有反證 fact 未列同筆 source_refs |

三份原稿與所有 15 個 capture files hashes 保持不變；**原 live outcome 仍 error／publication=null，新增 live 合格報告仍 0**。這是 grammar counterfactual，不是把舊失敗樣本重新分類為實測成功。

針對保存請求替換當前 grammar／system 規則，Agent 22 retry 另完整替換當前 numeric feedback；financial／State／registry 三段 JSON 在替換前後及 Google safety 後逐字一致。兩份首稿本機估算 **62,457／58,508**，Agent 22 retry **63,725**（餘裕 **275**）；舊值為 62,372／58,423／63,764。這是固定原上下文的反事實估計，非未來完整 graph 承諾；Agent 23 首稿現在通過有限檢查，因此不杜撰它仍會發生的 retry。沒有增加 cap、刪來源或新增重試。

本輪修改限上述七個 backend 檔（含新 helper）、兩份新 period 測試、既有 schema 文案測試與本文件／架構說明。正式 checkout 仍 clean main `758242290e795146520f58f68ffa113cac35e52c`；未 commit／push／PR／部署／重啟，未改正式 artifacts、Gemma OFF、28 OOS 或市場成熟條件。

**期間綁定切片離線完成，完整優化仍未完成。** 下一個 live 窗口仍須新的明確有界真人授權，用相同 2330.TW／v4 凍結輸入核對新稿能否通過完整流程；不能由本節預先宣稱模型成功率上升。四模式 12 組 paired、每模式至少 30 次 cohort、全文內容評估及授權發布 canary 仍待完成。

## 期間候選的全庫非 live 回歸（2026-09-13 18:07）

先前全庫證據早於有界 metadata repair 與期間語法變更，因此補上目前候選的跨模組回歸；不是因新 goal 訊息重跑未變更的同一組測試。全程使用 env-i、`tests/run_prompt_boundary_tests.py`、私有 SQLite／memory cache、禁網及 PostgreSQL guard；沒有 provider 呼叫、正式 DB 或 runtime 寫入。

- **17:46:08–18:04，全庫完成，exit 1**：11,659 passed／1 failed／24 skipped／2 deselected／75 subtests passed，1071.49 秒、3 warnings。JUnit 合計 11,759（含 subtests 與 skips），`/private/tmp/stock-agent-period-candidate-full-nonlive-20260913T0946Z.xml`，SHA256 `d6d0d4650a9e1e90113d8652ae7b5347828e2e451952a5e4e21444a8c4883dec`。
- 測試完成後、修正前核對 **746 檔 inventory 仍為 `fd4c7561…`**，與 17:42 的逐檔 hashes 完全一致；17:20 的 15 個 capture 檔 hashes 亦未變。
- 唯一失敗：`test_llm_call_event_helpers_are_split_from_call_attempt_flow` 要求 `llm_call_events.py` **少於 160 行**，目前 162 行。沒有改 assertion、排除失敗或刪事件欄位；只將三處 `_model_event_fields` 的共同四參數按同檔既有風格並列，恢復函式間分隔，變成 **155 行**。不是新的事件判定或報告品質修正。
- 修正前／後 `ast.dump(ast.parse(source), include_attributes=False)` SHA256 均為 **`31e00ee75ccd1d1b64d6ecbfc658414f77a3604eb20e423cae8645a03bc1626d`**；只有這一個核心檔案的文字 hash 改變。最終 746 檔核心 SHA256 **`49c5f0743a0797c571f2624823df62e45cf98960df1b75788658cdb50dfc5f33`**。其餘 period／repair／generation／prompt 內容完全不變，可沿用其相關證據；不宣稱排版後再跑過完整全庫。
- **18:06 補驗，exit 0：763 passed／0 failures／errors／skips，13.32 秒**。涵蓋完整 import boundaries／architecture services、事件模型身分、品質觀測與 recovery、quota／input capacity、metadata repair provenance、request budget 及完整輸出 gate，共 12 個測試檔；`/private/tmp/stock-agent-period-candidate-full-followup-20260913.xml`，SHA256 `427594d7df81a68a7faaa35f538045ccf2c8467ff7fbe5ced4b3ba4322a912ba`。與全庫重疊，不把兩次通過數相加，原失敗結果保留。
- **24 skips**：PostgreSQL live collection 1、外部公開來源 3、commercial live browser 8、歷史 artifact 1、sandbox Chromium visual 2、指定 Gemma／prompt checkpoint 複本 2、Chart.js／security／visual 6、Redis worker smoke 1。**2 deselected**：live 2449 smoke 與本輪明確排除的 Chromium runtime 啟動 preflight。這些不是通過證據；沒有安裝 browser、打開正式頁面或變更隔離條件。
- 3 warnings 是 RQ 的舊 UTC API 與兩個既有 legacy sync repair 入口 deprecation。沒有將 warning 或 skip 當成系統／provider 的品質結果。

本輪僅修改 DEV 的事件 helper 排版與本文件的當前狀態／證據，沿用其餘工作。未 commit／push／PR／部署／重啟，未動正式 artifacts、Gemma dark launch、28 組 OOS 或市場成熟條件。**工程回歸缺口已補；最新候選 live、四模式 paired、跨產業／日期 cohort、全文品質評估及發布 canary 仍未完成。** 下一次傳送仍需新的明確有界真人核准；自動 goal 續作不是新核准。

## 新真人核准的期間候選實測（2026-09-13 19:09）

使用者在前次待授權訊息後重新回覆「核准」，明確承接同一份 2330.TW／v4 凍結資料與新版提示、既有 Google Gemini 路由、最多 6 次呼叫／4 分鐘，現有金鑰僅供 API 驗證、不放提示。這不是自動 goal 訊息，也不是沿用 17:20 的剩餘次數。

- 新入口 `/private/tmp/stock_agent_authorized_period_2330_v4_20260913.py` 的 `--check` 通過、0 provider calls；核對既有三個隔離 harness hashes、完整來源、明確環境及同一套已驗證核心。一次性收據 `/private/tmp/stock-agent-period-approval-20260913-human-next-window.consumed.json` 已消費，沒有重新啟動窗口。
- 完整 backend inventory **913 檔／`023d4dafe81e0dcb7e19307857157ec9a20f4b73022d3f27b8723cee6186ef2c`**，核心 746 檔 **`49c5f074…`**；來源 SHA256 **`cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd`**，路由 SHA256 **`2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`**。沒有改 code、prompt、cap、retry 或 shared circuit 來取得這次結果。
- 執行於 **19:09:36 起，13.268 秒，child exit 2**，沒有觸發 240 秒 outer kill。4 transport calls／4 HTTP 200、3 complete STOP JSON／1 並行串流取消，均由 provider 標示為 **`gemini-3.5-flash-lite`**；不是獨立驗證 provider 內部版本。Gemma 的 Agent 22／23 完整輸入預估為 47,863／27,870，超過既有 12k local input cap；3.6／Preview／3.8 因既有 shared circuit 被略過，未清除或繞過，未由本輪證明其原始熔斷原因。
- **0 合格完整報告／1 隔離 job**；Agent 22 重寫仍拒收，取消 Agent 23 重寫，未抵達 Agent 24、final audit、renderer 或發布。這是已終止的 `AgentQualityDraftError`，不是 429／5xx／MAX_TOKENS／timeout 或市場成熟等待。
- Capture：`/private/tmp/stock-agent-quality-graph-2330-v4-source-periods-20260913T110936Z`；source-copy、prompts、requests、raw drafts、events、checkpoint、outcome 與 metrics 均保留。三份完整 payload 的 raw schema 都通過，不能把事件中的通用「結構不完整」文字誤解為 JSON 截斷。

| 實際稿件 | 拒收問題 | 新期間規則與限制 |
| --- | --- | --- |
| Agent 22 首稿（attempt 1） | 7 個 unbound_numeric_claim | 均線日數寫在引用之後，非規則要求的文字行後緊接來源；source_bound_periods=0 |
| Agent 23 首稿（attempt 2） | 3 個裸日期數字、2 個同筆 source_refs 缺漏 | 30／5／30 的來源期間確實通過，共 3 個；但日期 2026-09-11 仍須 metadata token，反證中的兩個 fact 未列入同筆 source_refs |
| Agent 22 重寫（attempt 3） | 1 unknown fact、1 invalid token、8 unbound numeric claims | 新增不存在的 sma_999；5／10／20／60「期」與 RSI14／ATR14、未來 1–2 週不在本次可接受寫法中；source_bound_periods=0 |

三份稿件都不符合「只有同筆引用／來源日期 metadata 問題」的有限 patch 啟用條件，因此沒有使用局部補丁；不能刪去裸日期錯誤或改寫正文以強行啟用。`sma_999` 不在任何本輪 prompt 中，registry 亦沒有此 fact，而真實 sma_60 仍存在；不能自動將未知 ID 改綁為另一事實。上述為格式／來源與有限語意核驗，不是完整自然語言正確性評分。

### 完整讀回與限制

- `/private/tmp/test_stock_agent_period_live_readback_20260913.py` 以真正 registry／payload validator／observation-date contract／metadata-repair planner 讀回三份原稿，**1 passed，1.34 秒**；`/private/tmp/stock-agent-period-live-readback-green-20260913T110936Z.xml` 與同名明細 JSON（無 `-green`）。該檢查不呼叫模型，不生成新報告，也不改 raw payload。所有 capture 檔與原來源 hashes 前後不變，完整 913 檔 code digest 一致。
- 初次 readback 有 1 failed：既有 Evidence sanitizer 把四個檔名含 `token` 的逐檔 hash 遮罩成 `[redacted]`，不是 code drift。僅修正 scratch 檢查，改核對完整 aggregate、完整檔案集合、其餘逐檔 hashes 及精確四個已遮罩欄位；原 red JUnit 保留，未改 harness 或 source。credential_body_check 同樣被遮罩，不把該字串當作獨立的金鑰掃描結果；dispatch 防護由本次已核對 hash 的既有 harness 執行。
- 四份 wire 的 financial／AgentState／registry JSON 均與各次完整 prompt **逐字相同，4/4**。本機 input estimates 分別 **62,456／58,508／63,861／60,151**，Agent 22 重寫距 64k 只剩 **139**；不是 provider tokenizer 或下一次 graph 的容量保證。
- usage 有明示欄位 **4/4**，input **223,080**／output **2,858**／total **225,938**，cached input **32,141**。這是每個 HTTP response 最新明示 snapshot 的加總，含已取消串流，不等於正式帳單，也不跨 frame 重複累加。HTTP 完整率 3/4 與完整研究合格率 0/1 分開。
- 正式 checkout 仍乾淨；沒有 commit／push／PR／部署／重啟，沒有修改正式 DB、歷史 artifacts、Gemma OFF 或 28 OOS。既有元件／資料來源的外部成熟時間不會解除本次內容錯誤。

### 19:09 後續工程切片（原決策，完成證據見下節）

19:09 實測後續作：來源固定指標標籤的期數綁定進入 TDD；先保存正例誤拒收與錯來源／數值／未來期限反例，再修正有限 grammar。格式範例及錯誤訊息是接續項目；沒有新 provider 呼叫，不宣稱修稿成功率已改善。

1. 用這次原稿建立正反例，評估「來源固定標籤中的指標名稱／期數」是否能在緊鄰有效 fact 下有限接受；SMA999、錯引用、未來期限與跨段借來源仍須拒收。不要只為通過把所有裸數字豁免。
2. 核對並改善 Agent 22／23 的完整來源格式範例與修稿引導：期間文字先於來源、日期用 metadata、反證的引用也列在同筆 source_refs；不把來源、正文或錯誤清單刪掉來縮減輸入。
3. 完整 JSON 的內容契約錯誤應與真正 JSON 截斷分開呈現；保留實際錯誤分類及 retry 分母。先做離線行為／容量檢查，再決定是否值得新的有界 live 窗口，而非立即重複同一實驗。

**本次真人核准的隔離測試已完成，整體優化仍未完成。** 19:09 的期間規則局部成功不足以證明四模式報告品質／成功率提升；正式 paired、每模式至少 30 次跨產業／日期 cohort、全文品質評估與授權發布 canary 仍待完成。

## 固定指標名稱、反證範例與重試說明：離線完成（2026-09-13）

沿用已核准工程工作，不重啟已消費的 19:09 provider 窗口。DEV 的本輪 scope 為三個 backend 檔、四個測試檔與本文件／架構圖；其餘既有開發改動保留。未 commit／push／部署／重啟，正式 checkout 最後讀回仍乾淨；不修改正式 DB、原 artifacts、Gemma OFF 或 28 OOS。

### 修改與驗證邊界

- `source_bound_periods.py` 新增来源固定 SMA「N 期收盤均線」、RSI14 指標、ATR14 真實波幅的有限 grammar。必須緊接正確且有效的 standalone fact，使用封閉 catalog／原計算 receipt；同為 14 的 RSI／ATR 不能互借。錯來源、SMA999、跨段、裸金融數值、未來期限仍拒收。只增獨立 period counter，不增 financial verified／denominator；snapshot／發布仍重新驗原稿與來源。全文 semantic coverage 保持 `not_checked`。
- `canonical_fact_prompt.py` 範例先示範固定標籤，再緊接 token；counterevidence 的第二筆 fact 同時列於同筆 source_refs。僅選相同 period 的第二來源，否則用定性限制，不借另一來源日期；不把第二數值自動解釋成反向結論。範例仍是無法通過完整角色 schema 的局部格式教學。只精簡重複教學文字，未刪來源、原稿或錯誤紀錄。
- `agent_runtime/quality_completion.py` 改善狀態說明：可解析 JSON 但被 gate 拒收，顯示欄位／內容驗證未通過；待驗文字不可解析時，明示原始回覆是否截斷尚未確認。非 JSON 角色使用通用內容訊息。保留 `structured_retry`、一次重寫、metadata-only 分支、取消與 rollback，不改 retry prompt detail。
- 獨立審查找出一項 P2：回覆可能已轉 Markdown 或 sanitize，不能將當前文字當 provider 原始 JSON。Agent 4 單位警示、Agent 23 key collision 兩個反例如實 red；修正文案並固化測試後關閉。未借旧 receipt 推斷，也未新增 gate 豁免。

### 測試與證據

所有測試均使用 env-i、禁網、私有 SQLite／memory cache。下列 suite 互有重疊，不相加成另一分母；全部路徑在 `/private/tmp/`。

| 證據 | 結果 |
| --- | --- |
| 指標 grammar TDD | `stock-agent-indicator-labels-red-20260913.xml`：10 failed／33 passed；green：173 passed／3.65 秒 |
| 反證範例 TDD | `stock-agent-counter-source-example-red-20260913.xml`：5 failed／21 passed；green：145 passed／3.26 秒 |
| 重試說明 TDD／審查修正 | 初始 9 faithful reds；獨立 P2 2 failed／9 passed；`stock-agent-retry-messages-reviewed-20260913.xml`：107 passed／2.65 秒；原審查反例不變，獨立複驗 13 passed／1.88 秒 |
| 最末 29 檔整合 | **`stock-agent-indicator-counter-final-integration-20260913.xml`：1,112 passed／19.33 秒**；包含 import boundaries、schema、來源、cache／rerun／snapshot／publication 接點 |
| 獨立來源與範例覆核 | `stock-agent-indicator-independent-review-20260913.xml`：192 passed；`stock-agent-prompt-example-independent-review-20260913.xml`：203 passed；無未關閉 material finding |
| 原 12 組凍結 graph／checkpoint／snapshot | `stock-agent-indicator-counter-graphs-20260913.xml`：12 passed／13.62 秒；provider 為明示 offline doubles，只驗證安全診斷，非 12 份真實合格研報 |
| 原 12 組容量矩陣 | `stock-agent-indicator-counter-budget-20260913.xml/json`：1 passed／18.20 秒；369 rows 仍 284 admitted／85 rejected，38 份來源 hashes、facts、limits、schema、generation configs、preflight 均未變 |

範例 helper 依賴 server-owned registry：直接塞入 calculation receipt 損壞但仍可 render 的 technical fact，可能生成 validator 拒收的範例。正常 caller 先全量重建 registry，獨立五類壞來源測試不產生 technical 範例；未發現可達 runtime regression 或 bypass。此限制不當作完整來源語意驗證。

### 19:09 原稿反事實重放：不是新 live 成功

`test_stock_agent_indicator_counter_frozen_20260913.py` 保留原三份 raw JSON，使用目前真 parser／registry／numeric gate：**1 passed／2.04 秒**；明細 `stock-agent-indicator-counter-frozen-20260913.json`，JUnit `stock-agent-indicator-counter-frozen-green-20260913.xml`。

| 原稿 | 新版離線結果 |
| --- | --- |
| Agent 22 首稿 | 仍拒收 7 項；先引用再寫日數仍不符合相鄰方向 |
| Agent 23 首稿 | 仍拒收 5 項；3 個來源期間通過，裸日期／同筆 refs 缺漏不放行 |
| Agent 22 重寫 | 原 10 項降為 5 項；5 個固定標籤參數正確綁定。未知 sma_999、無效 token、錯來源的 60、未來 1–2 仍拒收 |

初次 scratch 預期把 unknown token 的第二錯誤名稱寫成 `unresolved_source_ref`；實際為既有 `invalid_numeric_token`。只修正測試期待，不修改 gate；原失敗 XML 保留。所有 capture／原始 source hashes 不變，原 live job 仍 failed、publication=null，新增合格 live 報告為零。

四份原 wire 提示只替換當次格式範例與 system 教學後，本機 input estimates 為 **62,441／58,501／63,846／60,144**；financial／State／registry 三段 JSON 均逐字不變。Agent 22 重寫僅餘 **154** token，仍是重要容量風險；這不是新 graph、provider tokenizer 或配額可用性保證。

最末核心 digest **`cd9dda543d9848748fa7716c8e3e5827fe9805a5e89501cf2975583817b1c22e`**；完整 backend **`16a8968994b4c5a164e468268fdd6dd1982ee9ee99ab861578c2ccd2da9a0a60`**。矩陣／原稿重放時為 `2e198821…`，其後只有上述 P2 狀態句與 comment 修改。`stock-agent-indicator-counter-final-receipt-20260913.json/xml`（1 passed／0.34 秒）逐檔證明僅此差異，核對完整原來源、capture、路由、測試 XML 與最末 inventory；容量／來源證據可沿用，不將舊 hash 冒稱新 live 版本。

### 剩餘任務與下一關

本切片三項工程工作已完成；**整體 P0／P1／P2 未完成**。新的實際輸出能否遵循格式尚未測得，不能由 5 個誤拒收消失就宣稱 Gemini／Gemma 成功率上升。下一關為新候選的有界 2330.TW／v4 live 驗證，再依證據推進 paired 四模式、每模式至少 30 次 cohort、全文品質與發布 canary。19:09 收據已消費，任何新 provider 傳送須新的真人核准；自動續作不能重開窗口。正式 runtime 仍未載入此候選。

## 原稿內容核對與籌碼敘述漏檢修正（2026-09-13 續作）

上輪屬實質工程進展；本輪自動 goal 續作沒有新傳送授權，改做已核准 P0-2／P1-4／P2 範圍內的離線來源與敘述核對。發現新證據後，下一步優先補技術比較證據，不將上述原定 live 下一關當成必須立即重試的命令。

### 原稿與來源的實際差異

| 19:09 原稿主張 | 目前可核對的來源證據 | 判讀與限制 |
| --- | --- | --- |
| Agent 22 首稿：短天期均線斜率向上 | 按相同保存日線起點、最後兩個實際觀測列重算，SMA5 差 0、SMA10 差 -1、SMA20 差 +0.75、SMA60 差 0 | 不能由當期多頭排列推定短天期斜率普遍向上；原文未指定比較窗口。當期 SMA5 > SMA10 > SMA20 > SMA60 的排列本身成立 |
| Agent 22 首稿：MACD 柱狀差微幅擴張 | 同口徑前筆 5.51511463、當筆 1.97667086，差 -3.53844377 | 最近觀測列是縮小，與原敘述相反。現有 fact 只證明當期值，尚未建立可供敘述 gate 使用的跨期比較 receipt |
| Agent 22 重寫：ATR 波動度維持歷史平均區間 | 有當期 ATR 43.42659721 及完整保存日線，但原文未指定平均窗口、區間或門檻 | 沒有充分依據判定該平均區間；不能自行選一個窗口就宣布主張正確 |
| Agent 23：外資淨買、投信淨賣、近五筆合計淨買、最後一筆淨賣 | 四筆 canonical shares 的正負方向相符 | 這些方向可核對，不代表資金匯出入、投資人身分或未來走勢已證明 |
| Agent 23：買賣超「金額」起伏明顯 | 引用的是 shares，不是貨幣金額 | 新增有限 monetary-flow 主張阻擋；現有 registry 沒有相應金額 receipt，不能借其他金融數值或同數字通過 |
| Agent 23：大戶持股維持高檔、散戶持股維持穩定 | 舊 TDCC 僅保留彙總比例，沒有 raw tiers、可靠級距與比較期 receipt | 擴充已知 ownership-comparison 形式；不得用一個日期或已保存的 rounded 比例證明高檔／穩定 |
| Agent 23：融資與借券餘額維持一定水準 | 借券 balance 可核驗，但舊 margin source 未保留必要單位證據，margin canonical fact unavailable | 應逐指標核對，借券餘額不能替融資餘額背書；新增 locative／並列敘述檢查 |

上表是凍結來源下的有限語意／計算核對，不是新的行情查詢、價格調整口徑獨立核證或完整投資判定。未來劇本屬條件敘述，不當作已驗證市場結果；「溫和」「強勢」「歷史平均」等沒有明示門檻的程度詞仍不能獲得全面語意合格標章。

### 已修正與未修正

- 本輪只改 `backend/research_assertion_contract.py`、`backend/generation_numeric_runtime.py`、新增 `tests/test_research_live_wording.py` 及既有文件。擴充有限主張語法與 conditional 研究修稿提醒；沒有改資料來源、raw drafts、facts、provider routes、caps、retry 次數、metadata repair 啟用範圍或正式 artifacts。
- 持股「維持在高檔／穩定水位」、已知「買賣超金額」變動主張，以及「在現階段」並列餘額，進入原有全量數字／研究驗證及 cache／publication 重新核驗。每個餘額仍需自己的 exact source；比較、發布延遲與 monetary flow 不接受模型自填聲明當 receipt。
- 主代理與獨立審查重現六個合法否定／疑問／資料不足的誤拒收並修正。最後又補原「待核對」前綴漏洞：只有完整分句才能豁免，`待核對但已維持…` 不再直接放行；`待核對，但其他來源仍須評估` 仍可保留。所有原 red 保留，不把草稿或來源改成容易通過的內容。
- 尚未修復技術趨勢比較證據與全文 entailment。`research_validation.semantic_coverage` 明確仍是 `not_checked`。現有 Agent 22 原稿並未因籌碼修正就通過，不能宣稱完整品質或成功率上升。

### 驗證收據

以下檔案位於 `/private/tmp/`；全部 env-i／禁網／私有 DB，不相加重疊測試分母。

- 原始漏檢 red：`stock-agent-research-live-wording-red-20260913.xml`，14 failed／9 passed。第一修正 3 failed／168 passed，對應合法否定／問句；修正後 174 passed。獨立新三反例 3 failed／10 passed，修正後連同相關 tests 191 passed。最後前綴 red 1 failed／31 passed，綠燈 **193 passed／3.07 秒**，`stock-agent-research-pending-boundary-green-20260913.xml`。
- 跨來源、schema、metadata repair、cache／rerun、snapshot／publication、prompt 與 import boundaries 整合：**1,213 passed／20.40 秒**，`stock-agent-research-live-final-integration-20260913.xml`。之後僅一行待核對句界變更，由上列 193 項及獨立 **138 passed／2.51 秒**（原 13 反例＋原 22 邊界 probe，期待值未改）覆核；`stock-agent-research-pending-independent-closed-20260913.xml`。無剩餘 material finding，但不是全面 NLU。
- 原 12 組凍結 graph／checkpoint／snapshot：**12 passed／13.55 秒**，`stock-agent-research-live-frozen-graphs-20260913.xml`；明示 offline doubles、安全診斷，非 live 成功。
- 最末容量矩陣：**1 passed／18.03 秒**，`stock-agent-research-live-budget-20260913.json/xml`；12 jobs／369 rows、284 admitted／85 rejected。與上一版比較，除了 graph run UUID 造成的 prompt hash 差异，其餘每列（含 estimates／limits／facts／generation configs／preflight）完全一致；38 原始 source hashes、schema catalog、routes 不變。
- 最末原稿／修稿提示讀回 `stock-agent-research-semantic-final-20260913.json`：原三份稿件仍 rejected，問題数依次 **7／9／5**。Agent 23 比上一版多抓到 2 個 ownership、1 個 monetary、1 個 margin-source 問題；這是更完整的拒收證據，不是四次新模型失敗。四份來源 JSON 仍逐字保留；完整修稿反馈 input estimates **62,441／58,501／63,846／60,763**，Agent 22 仍僅剩 154、Agent 23 重寫剩 3,237，皆為本機估算而非 provider tokenizer。
- 最末來源與程式收據：`stock-agent-research-final-receipt-20260913.json/xml`，**1 passed／2.32 秒**。核心 SHA256 **`66759f53d6954ec502966daee00dd1c6a940b9171bae8b77c9420f24672bba53`**；完整 backend **`bb7d083d2054e8e484583ff87eede3590cece54d7bec448372a05c3e4c61f69f`**。逐檔證明整合後只改最後一行句界，重新讀回原 capture／38 份來源／測試 XML／目前 matrix；原 19:09 live 結果、四次呼叫分母與 consumed 收據不變。

### 已授權離線工程切片：技術跨觀測日比較

本輪已進入執行：先補 registry 群組表的可逆共值欄位編碼（新 wire version，保留旧 decoder），用原 12 組來源檢查容量與 round-trip；再建立最後兩個已觀測點的技術比較 receipt，採用／發布時從完整保存日線重算。新增比較只描述指定窗口的數值／絕對值變化，不取得交易價格、長期趨勢或預測資格。這是既有容量不足風險下的必要前置，不刪原來源或放大 cap。

先針對已重現的「MACD 正值不等於柱狀差擴張」「均線排列不等於斜率向上」建立可信比較輸入與正反例，再接到原有來源／敘述驗證；明示前後觀測日期、窗口、計算口徑、輸入 hash 與比較方向，不能由模型自填 receipt。維持完整 120 根原始日線、不外取或回填歷史來源、不放大 input cap；先驗證新增證據是否能在既有提示容量下 losslessly 傳遞。本切片目前已在隔離開發工作樹實作與離線驗證，詳下節；正式 runtime 尚未載入。

**整體任務仍 active 且未完成。** 正式 checkout 讀回乾淨，HEAD 仍 `758242290e795146520f58f68ffa113cac35e52c`；未 commit／push／PR／部署／重啟。下一輪 live、四模式 paired、每模式至少 30 次 cohort、完整品質驗收與 canary 仍待；本輪沒有新 provider 呼叫，Gemma OFF／28 OOS／正式 DB 與歷史報告不變。

## 技術比較切片：已修改與離線驗證（2026-09-13 續作）

本輪只修改隔離 DEV，不使用已消耗的 19:09 provider 授權。`prompt_record_groups.py` 新增可逆 v2 共值欄位，保留 v1 與最短格式選擇；所有 fact、欄序、型別、完整 120 根日線都保留，不裁切來源或放大 64,000 cap。新增比較資料只在 exact 5／10／20／60 SMA 與 MACD histogram facts 的 `comparison` 欄中，沿用既有完整輸入 SHA、歷史指標身分與 `decision_validated=False`，不新增金融 verified 分母。

`canonical_technical_facts.py` 比較最後兩個**已觀測**點，前綴只去掉末根，不移動 EMA 起始 seed。收據保留 from/to、樣本數、前值、公開八位精度差值與方向；histogram 另記絕對值差。前期窗口不足時仍可保留當期 fact，但不製造 comparison。`technical_research_assertions.py` 對已識別有限中文形式要求 exact 指標、緊接有效來源行、明確前一觀測日窗口，並從當次完整 data 重建 fact。當期排列、符號、數值變化、絕對值變化各自核對，不把兩點差宣稱回歸斜率／持續／長期／微幅趨勢。資料、raw、fact 或比較收據被改動時，舊 passed 不能繞過採用／quality／cache／metadata repair／rerun／publication；保留真正否定、問句與未採用引文。

### 原稿結果與容量

- 原 2330.TW／v4 capture 及 source SHA 不改，三份 STOP JSON 原稿仍全部 rejected，問題數由 7／9／5 變成 **12／9／5**。第一份新增抓到技術比較敘述問題；不是新增模型失敗，也不是新成功率分母。ATR「歷史平均區間」沒有明確窗口／基準、TDCC 比較來源缺失與其他自由語句仍未全面核證，`semantic_coverage: not_checked` 保留。
- 同一保存序列的 9/10→9/11：SMA5 `2451→2451`，SMA10 `2429.5→2428.5`，SMA20 `2410.25→2411`，SMA60 `2399.75→2399.75`；MACD histogram `5.51511463→1.97667086`，絕對值縮小。當期四條均線確實按短到長遞減，但不能證明它們的斜率都向上。
- 目前完整 contract／修稿回饋在原四份凍結 prompt 的本機 estimates：**59,158／56,188／61,222／58,450**，最緊 Agent22 retry 餘裕由 **154→2,778**。financial／AgentState JSON bytes 不變；registry 只新增 comparison，移除新增欄後與舊版完整解碼內容完全相同；Google framing 前後當次三個來源 JSON bytes 相同。這不是 provider tokenizer 保證。
- 原 12 jobs／369 配置矩陣：**287 admitted／82 rejected**，比原 284／85 多三個低於容量限制的候選。恢復者為 2330/v1 Agent6、2330/v3 Agent21、2882/v1 Agent21 的 Lite 路由；其他不變限制、配置、schema 與 38 個來源檔 hash 保留。這是本機 admission，不代表 HTTP 成功或報告合格。

### 測試與獨立覆核

所有執行皆 env-i、私有 SQLite、禁網 runner；`/private/tmp/` 收據分母重疊不相加。

- v2 wire：red 2 failed／16 passed → **101 passed／2.64 秒**；獨立 51 cases 加原 scope **137 passed／2.07 秒**，`stock-agent-group-v2-independent-final-20260913.xml`，未見 material finding。
- comparison producer：缺少收據的 **5 failed** → 指標與期間回歸 **132 passed／2.86 秒**。assertion 初始測試先暴露缺 data 介面；接好介面後有效 behavior red **17 failed／10 passed** → **135 passed／2.64 秒**。真實 parser／snapshot／metadata／rerun 整合 **177 passed／5.49 秒**。
- 獨立覆核重現「MACD 負值被當成絕對值負值且能發布」與「不能確認目前…被誤拒」；前者先以真實 publication seam 證明失敗。修正後 repo 加 signed／abs／跨零／否定與 publication cases，**168 passed／3.59 秒**；原 10 獨立反例期待不改，另含 repo scope **77 passed／3.20 秒**，`stock-agent-technical-comparison-independent-closed-20260913.xml`，兩項 material finding 已關閉。
- 最後擴大來源、schema、raw/normalized、cache、repair、snapshot、publication、rerun、prompt／wire／Google 邊界與 import／architecture 整合 **1,949 passed／25.17 秒**，`stock-agent-technical-comparison-full-integration-corrected-20260913.xml`。首次命令指定不存在的舊測試路徑而未收集，已更正；不算測試失敗或通過分母。
- 原 12 組凍結 graph／checkpoint／snapshot **12 passed／13.97 秒**，`stock-agent-technical-comparison-frozen-graphs-20260913.xml`；使用 offline provider/service doubles 的安全診斷，不是 live 報告品質驗收。
- 最末同程式矩陣 **1 passed／18.23 秒**，`stock-agent-technical-comparison-final-budget-20260913.json/xml`；最後原稿／新提示與證據合併收據 **1 passed／2.41 秒**，`stock-agent-technical-comparison-final-receipt-20260913.json/xml`，原稿詳情 `stock-agent-technical-comparison-final-readback-20260913.json`。核心 747 檔 SHA256 **`a9aba9591949471b40e693672395f44bd8c065731b111f8e9518eb8c9f3e1792`**；完整 backend 914 檔 **`73eae4229f7be5dae1ed66ace855c7942d2dc485a88fdd8a42029c9be5ea596c`**。逐檔核對 38 原始 source hashes、routes、schema、matrix 非容量欄位、三份原稿和全部引用 XML；本輪核心差異限定列出的 10 個檔案，前後 evidence 均未改寫。`git diff --check` 通過；正式 checkout 再讀回乾淨、HEAD 不變。

本輪 endpoint 為**已驗證本機候選**，不是「全部完成」或「正式上線」。原 19:09 四次 provider 呼叫／零合格完整報告的結果不改；沒有新 provider 呼叫、正式服務重啟、Git 發布或 artifacts 重建。接續仍需實際模型對新 wire／比較規則的限額驗證、四模式 paired／cohort、完整品質驗收與授權發布；非有限形式的語意與欠缺的來源比較不得冒稱已解决。

## P1-2：真 Redis 跨程序冷卻競態（2026-09-13 續作）

回到原計畫的共享冷卻／隔離驗證，發現 `RedisFixedWindowRateLimiter.open_model_circuit` 將 PTTL 讀取與 SET 分開：短等待 Worker 讀取後，另一 Worker 先設 30 秒，短等待 Worker 再寫 10 秒會蓋掉較長期限。真 Redis 控制交錯下，舊版剩餘 **9.618 秒**而失敗；不是只有 mock 推測。這會讓其他 job 過早重試同一故障模型，但不是 provider quota 或報告內容品質的直接證據。

本次僅改 `backend/shared_runtime_guards.py`：用同一 model key 的單次 Lua 原子操作讀取並延長 TTL，保留較長有效等待；不變更模型雜湊、namespace、RPD、冷卻政策或正式設定。更新原 fake 並新增永久 `tests/test_shared_model_circuit_atomicity.py`，覆蓋短／長寫入與 Redis 故障的 job-local fallback。若 Redis 不可用，仍只有 job-local 保護，不宣稱此時能跨 Worker 共享。

### 實測、覆核與證據重用

- 真 Redis probe `/private/tmp/stock_agent_private_redis_circuit_probe.py`：Redis 8.8.0、TCP port 0、唯一新建私有 Unix socket、700 權限、不持久化；parent／各獨立 Python Worker 都套 env-i／私有 DB／禁網 runner，只有固定 socket closure 例外。synthetic error／假 key，不載入正式金鑰、不連正式 Redis／provider。測試結束原生 handle 為成功終態，之前必經自建 Redis `server.wait` 與臨時目錄退出；獨立 reviewer 未因 sandbox 受限的 ps 而宣稱另外完成 OS 程序盤點。
- 真 Redis red **1 failed／4 passed／23.12 秒**（唯一為交錯短寫覆蓋），green **5 passed／21.92 秒**。涵蓋 server failure→另一程序立即讀到冷卻、不同模型不受影響、request-local／quality error 不擴成跨 job 封鎖、真 TTL 到期自然恢復及交錯 TTL 保護。XML：`/private/tmp/stock-agent-private-redis-circuit-red-20260913.xml`、`/private/tmp/stock-agent-private-redis-circuit-green-20260913.xml`。parent 的 worker-only helper 為 1 deselected，不是 skipped；兩次 sandbox Unix bind 不允許的初始啟動未收集測試，不算產品失敗或通過。
- 永久測試先 red **2 failed／1 passed**，修正後相關 quota／budget／reliability／runtime／storage tests **119 passed／6.12 秒**；唯一 warning 為既有 RQ datetime.utcnow deprecation。重試、deferred、workflow、quality recovery、事件與 import／architecture 整合 **692 passed／14.37 秒**。XML：`/private/tmp/stock-agent-redis-atomicity-unit-red-20260913.xml`、`/private/tmp/stock-agent-redis-atomicity-green-20260913.xml`、`/private/tmp/stock-agent-redis-cooldown-integration-20260913.xml`。
- 獨立 reviewer 親讀真 Redis red／green 與 socket 隔離，不把 fake 當 Lua 執行證據；另跑永久單元 **14 passed／4.94 秒**，`/private/tmp/stock-agent-redis-model-circuit-independent-review-20260913.xml`，無 material finding。覆核後四份程式／測試／probe SHA 再核對相同。
- 最末收據 `/private/tmp/stock-agent-redis-atomicity-final-receipt-20260913.json/xml`，**1 passed／0.32 秒**：核心 747 檔 SHA256 **`5ec8f5b868f106cd14d0e614f176b1bd55eebbb89768eac23e5292e0e0ff223b`**；完整 backend 914 檔 **`8f4fb9c29a6737f4def84d0a2fed38aceb0cdd4370a2fb2e76e9d2ee666e7403`**。逐檔證明相對上一技術比較候選只改 `shared_runtime_guards.py`；38 個凍結來源、routes 及其他 backend／prompt／schema 未變。前一輪 1,949 項／12 graph／容量矩陣依此重用，**不是本輪重跑**，所有重疊分母不相加。

本切片已修改、隔離驗證與獨立覆核；完整原 P0／P1／P2 仍未完成。正式 checkout 再读回乾淨、HEAD 仍 `758242290e795146520f58f68ffa113cac35e52c`；未 commit／push／PR／部署／重啟，provider 呼叫增量為 0。19:09 限額窗口已消耗，不重用舊核准；新候選 live 仍待新的限額核准。後續還有四模式同輸入 paired、每模式至少 30 次跨產業／日期 cohort、完整報告品質驗收與發布 canary；Gemma OFF、28 OOS、正式 DB／歷史 artifacts 不变。

## 新真人核准的比較候選實測（2026-09-13 21:07）

使用者於目標待核准後真人回覆「核准」，承接同一份 2330.TW／v4 凍結研究資料與新版提示、既有 Google Gemini 路由、最多 6 次呼叫／4 分鐘；現有金鑰只供 API 驗證，不放入提示。新的 `/private/tmp/stock_agent_authorized_comparison_2330_v4_20260913.py` 先完成 `--check`（0 provider calls），核對 747 核心／914 backend inventory、原三份 harness、環境 hash、來源與既有測試證據，未修改 backend。新的 exclusive 收據 `/private/tmp/stock-agent-comparison-approval-20260913-human-next-window.consumed.json` 已消耗，不重開 19:09 窗口，也不追加本次剩餘兩次。

### 執行與完整報告結果

- **21:07:51 開始，12.874 秒，child exit 2**；inner 220 秒／outer 240 秒、6 transport／6 physical HTTP 雙上限保留。未觸發外層終止，正常因 `AgentQualityDraftError` 結束；原生 session `14223` 已終止，不是背景仍在等待。
- **4 transport／4 HTTP 200／4 份完整 STOP JSON**，全部 provider 標示 `gemini-3.5-flash-lite`；這是回傳標籤，不是獨立證明內部模型版本。Gemma 因既有 local input cap 預檢略過，3.6／Preview／3.8 因既有 circuit 略過；不將本輪略過視為新 provider 故障，也未清除共享配額／冷卻。
- **0 合格完整報告／1 隔離 job**。Agent 22 最後通過有限 `agent_content_contract`，Agent 23 品質重寫失敗；未抵達 Agent 24、final audit、renderer 或發布。checkpoint 保存 Agent 22 passed 與 `next=[agent_23]`；其中 `status=running` 只描述保存狀態，不代表 native process 還活著，也未自動重新送件。
- 原 capture：`/private/tmp/stock-agent-quality-graph-2330-v4-comparison-20260913T130751Z`，含 manifest、原始公開回覆、實際 prompt／wire、事件、checkpoint、outcome、metrics。來源 SHA256 仍 `cbccb6409482ea0d9000ec349ce1f951a24d9164f2cd37467c33469a22ef79cd`；routes 仍 `2dd7d0ba509c738025e8b84ce1d9e6c960454c721f6931cae5704a5baae39d7a`。四次 wire 的各三段來源 JSON 逐字相同，Agent 22 完整 120 根保存日線仍在，沒有以刪除來源換取通過。
- Wire usage 覆蓋 **4/4**：input **211,559**、output **2,854**、total **214,413**；cached input **64,074** 是 provider 回傳子項，不另加到 total、也不是重用本地草稿。四次完整 HTTP 延遲 p50 **4.403 秒**／p95 **5.130 秒**，樣本只有 4，不推估長期 SLO。15／30／60 分鐘分母尚為 0、censored 1；不能報成長期完成率 0% 或達標。

### 原文與來源核對

| 輸出 | 實際有限契約結果 | 內容判讀與限制 |
| --- | --- | --- |
| Agent 22 首稿（attempt 1） | rejected，2 項 | 四條 SMA 的前後觀測日方向與保存資料一致；MACD 縮小未明寫絕對值口徑，且條件段落的泛稱均線排列未列 exact 指標／引用。不能把這兩項都描述成金融數字錯誤。 |
| Agent 23 首稿（attempt 2） | rejected，3 項 | `recent5` 用了不支援的 `千股` display token（衍生 2 個錯誤），另無多期來源卻宣稱大戶持股比例穩定。 |
| Agent 23 重寫（attempt 3） | rejected，29 項 | 6 個 token 的 fact 實際存在，但顯示單位 `千股`／`shares` 不在現行 formatter 文法；又增加裸日期、84.82／8.76／28,901、同筆 dealer 反證未列 source_refs，以及融資餘額來源綁定缺漏。29 是驗證 issue 數，包含重複及日期拆分，不是 29 個獨立錯誤事實。 |
| Agent 22 重寫（attempt 4） | passed，0 項 | 拿掉比較後通過有限契約，checkpoint 保存成功；但 finding 寫成「引用格式」、counterevidence 寫成「反證引用格式；此筆不自動構成反向結論」，且主要是指標列表。這不是有用研究與有效反證已驗收的證據；`semantic_coverage=not_checked` 不變。 |

離線以同一實際 prompt registry／原始 payload 重走 production parser，與 runtime 結果一致：`/private/tmp/stock-agent-comparison-live-readback-20260913.json/xml`，**1 passed／2.04 秒**。另以 real `resolve_fact`／`render_fact` 核對上述六個 token，來源都存在、canonical unit 是 `shares`，可用顯示為 `股`／`張`，原錯誤顯示皆拒收；`/private/tmp/stock-agent-comparison-live-unit-audit-20260913.json/xml`，**1 passed／0.32 秒、1 deselected**。兩項為 env-i／禁網／私有 DB 讀回，沒有新呼叫、沒有替模型修改原稿。

觀測限制另有具體證據：metrics 的 `content_rejections=0` 只計目前 `llm_model_error` 的 response-processing 事件，沒有計到結構重試後 `AgentQualityDraftError` 的拒收；因此不能當「沒有內容問題」。`quality_completion.reject_incomplete_output` 已在 job-local context 設 failed，但失敗 node 沒有結果 delta，telemetry 仍顯示 unverified。job failed／publication 0 與保存原文才是本次完成判定。

### 依本次證據調整下一個優化切片

1. **先降低單位與修稿的非必要失敗**：讓 canonical source unit 與可輸出的 display token 一致可理解，來源存在但格式不支援時提供 exact 可用格式；研究是否可將有界修復限制在真正錯誤欄位／片段，保留已核對段落，不能以整稿重寫新增數值、删證據或讓 validator 自動採用未授權來源。新增顯示 alias 如需實作，仍須有精確換算與精度測試，不從字面或大小猜單位。
2. **教學格式不得取代研究內容**：隔離示例與正式 finding／counterevidence，驗證有實際的資料解讀與相反情境／限制；先以這份照抄稿建立可重現驗收。不要將所有語意規則綠燈宣稱為全文 NLU 完成，也不能只靠增加字數補出假研究。
3. **補品質拒收觀測接點**：結構／來源拒收保留明確 agent、phase、attempt 與 reason；與 HTTP／provider failure 分開，避免重試／node 事件重複計數。以本次 retained events 與真正 failure path 建立回歸，不回寫舊事件冒充原本存在。

上述為原 P0-1／P1-3／P1-4 的下一個有證據切片，**本節未宣稱已實作**。本輪只有新測試 launcher、讀回證據與此交付紀錄，backend 候選 hash 未變；正式 checkout 仍乾淨、HEAD `758242290e795146520f58f68ffa113cac35e52c`，未 commit／push／PR／部署／重啟或重建正式 artifacts。四模式 paired、每模式至少 30 次跨產業／日期 cohort、完整內容品質與授權發布 canary 仍未完成；Gemma OFF 與原 28 OOS 不變。

## 股數顯示與保存來源發布重核（2026-09-13 續作）

本節接續上一輪的離線工程，不重用已消耗的 21:07 核准。新增 provider calls **0**、新增合格完整報告 **0**；正式 runtime／DB／Redis／artifacts 未改動。適用 `test-driven-development` 的真實反例先行與 `requesting-code-review` 的獨立覆核；沒有為了測試綠燈改寫原稿、放寬來源或刪除反例。

### 已修改

- `numeric_claim_format.py` 明確支援 `shares`（與股同值）及 `千股`（canonical shares 除以 1000、三位小數），保留原值、正負、零、整股差、來源日期及四捨五入精度說明。原 `股／張` 順序與範例不變；不接受 `lots`、`千張` 等未定義猜測。`canonical_fact_prompt.py` 補明確換算說明，不改 schema、來源 JSON、route 或 cap。
- 發布反例另重現既有缺口：保存 registry 的法人期間改成 FY2025，只檢查 input／prompt binding 仍可能放行；若再走真 parser／binding，錯期間可進入正文並抵達 HTML seam。原股／張與新 shares／千股都重現，因此不是 alias 引入；也不表示模型能直接修改 server-owned registry。只改 registry 而不重繪，原正文不會自動改變，兩種情境分別測試。
- 新 `generation_source_projection.py` 抽出原 partial-rerun 的唯讀比較，支援四種既有來源形狀：normal full、normal compact、Gemma role-scoped、Gemma full-dense/repair。保存在 snapshot 的路由暫時旗標可能不存在，因此有界重建，不只假設 full。每個 stored fact／unavailable 必須與**同一個**候選完整相等，含 nested visible_ref；visible paths 為 subset、required IDs 集合完整相等，不聯集不同候選。
- `generation_report_gate.py` 在 final audit／renderer／snapshot replay 先按模式固定順序重核，final 只借已重核上游 facts；combined decision 也只使用這些來源。失敗留下 `source_registry_changed`、阻擋發布、標示 verified coverage 不完整，不沿用舊 passed。`generation_contract_rerun.py` 共用同一比較，維持 HTTP 409／完整重跑邊界。沒有將重建放進一般 `accepted_numeric_output`，因此不宣稱所有中間 parser 都提前拒收；關鍵是錯來源不能發布或沿用至部分重跑。
- 原始來源是保存資料的可重建投影，不是外部來源真實性／公告時點或新 provider attestation。既有語意 `not_checked`、unavailable、Neutral／價格及原始 schema 規則維持。

### 原始稿件與容量讀回

原四份 raw／capture、各 prompt 三段來源 JSON 與 Agent 22 全部 120 根日線逐字不變。production parser 原稿離線重放結果為 **2／1／17／0 issues**，狀態仍 rejected／rejected／rejected／passed。消除 Agent 23 六筆有來源但顯示格式不支援的拒收；不把日期拆分 issue 當獨立事實，也沒有替模型生成修正稿。Agent 22 教學範例式 finding／反證仍不是完整研究品質通過。

四份新版提示估算（按 attempts 1／2／3／4）：**59,209／56,238／57,723／60,829**；最小 64,000 cap 餘裕 **3,171**。這是既有本機估算，不是 provider tokenizer 保證。`stock-agent-share-display-replay-20260913.json` 同時證明每份原 registry 可由保存來源重建。

12 jobs／369 配置仍為 **287 admitted／82 rejected**，38 份來源 hashes、schema catalog、routes、限制與生成配置逐欄不變；除了 prompt hash 與 input estimates，其餘矩陣欄位與前一技術比較矩陣一致。`stock-agent-share-display-budget-20260913.json` 不是 369 次模型呼叫或成功率。

來源投影成本另外以四份真實原提示 registry、正例／改錯期間各 5 次量測：正例 median **17.4–25.2 ms**，遍歷四候選後拒收 median **53.9–80.5 ms**；首次含匯入暖機的最大值 **732.3 ms**，不可只報熱態。見 `stock-agent-source-projection-cost-20260913.json`；該檔 scope 的 warm-process 標籤不排除此首筆暖機值，這裡明列。未量測所有大型正式 context／全服務延遲，也不是 live SLO 保證。

### 測試、覆核與完整性

全部 `/private/tmp/` 證據，env-i／禁網／私有 SQLite／memory cache；分母重疊不相加。

- 單位 red **12 failed／15 passed** → 初次相關 **241 passed**。新增發布反例原 **2 failed／49 passed**；獨立對照原股／張／shares／千股 **8 failed／21 passed**，確認問題存在後才修復。
- 永久 source-projection red **16 failed／1 passed** → 初次整合 **80 passed／4.29 秒**。加入四形狀及四模式實際 graph 後，相關 **369 passed／7.02 秒**，`stock-agent-share-source-integration-20260913.xml`。
- schema、來源、metadata repair、cache／rerun、publication／snapshot、workflow、import／architecture 擴大整合 **961 passed／22.45 秒**，`stock-agent-share-source-boundaries-20260913.xml`；原 12 組凍結 graph／checkpoint／snapshot **12 passed／21.46 秒**，`stock-agent-share-source-frozen-graph-20260913.xml`。graph 明示 offline doubles，產物是安全診斷，不是真實模型報告。
- 獨立原反例與接點整合 **155 passed／5.21 秒**，`stock-agent-source-projection-independent-closure-20260913.xml`；额外 **10 passed／2.03 秒**，`stock-agent-source-projection-independent-probes-final-20260913.xml`。涵蓋不可聯集 views、通過後變動重核、巢狀來源欄位及真实 anchor；三份 registry 同步改錯且相互一致、重算全部收據也不能互相背書。原 8 反例期待未改，無剩餘 material finding。
- 將合法 anchor 與三份一致篡改兩個覆核案例保留為永久測試；最终永久 source 測試 35 項＋獨立 10 項 **45 passed／3.80 秒**，`stock-agent-source-projection-permanent-review-20260913.xml`。此時 backend 未再變，不將前一 961 項誤稱包含後加的兩項。
- 容量矩陣 **1 passed／17.79 秒**；原稿／來源逐字重放 **1 passed／2.43 秒**，`stock-agent-share-display-replay-source-20260913.xml`。末輪 inventory／38 sources／矩陣差異／capture／XML 及局部成本 **2 passed／3.93 秒**，`stock-agent-share-source-final-receipt-20260913.xml`，詳 `stock-agent-share-source-final-receipt-20260913.json`。
- Live manifest 的 4 個檔名含 tokens 的 hash 值被既有 sanitizer 遮為 `[redacted]`，一開始的 replay scope assert 因直接比較遮罩值失敗；**不是另外四個檔案改動**。改用當次 launcher 已逐檔核對的 pre-call `stock-agent-redis-atomicity-final-receipt-20260913.json`，完整 inventory SHA 與 manifest 相符，四檔實際未變；保留第一次失敗 XML，不覆寫證據。

目前相對 21:07 live 僅四個既有 backend 檔修改、增加一個 source-projection 模組。核心 748 檔 SHA256 **`4df880e5fffef145c7b640eb3cc5f7ac07ac4000c8a4ff59872066d5074ae3fc`**；完整 915 檔 **`c596c3cc7821dba2d59ccf59a0f8e53245bb91b115187fb9ab2ffd6c300d339e`**。正式 checkout 再讀回乾淨，HEAD 仍 `758242290e795146520f58f68ffa113cac35e52c`。

**整體目標仍未完成。** 可继续的離線項目：抄寫格式片段不能冒充研究 finding／反證；保留已核對段落的有界修稿；品質拒收事件及 attempt 去重。之後仍需新候選的限額 live、四模式 paired／每模式至少 30 次跨產業與日期 cohort、完整內容驗收及已授權範圍內的 Git／PR／部署／重啟／canary。此切片未進行任何上述外部送件或正式發布，Gemma OFF、28 OOS 與歷史 artifacts 不變。

## 教學佔位與研究完成度分類（2026-09-13 22:07）

上一目標回合已修改可驗證狀態，屬 progress，不是等待或停滯。本輪接續原 P0-1／P1-3 的內容可信度，使用 TDD 與獨立反例覆核；未建立新目標或縮減「直到全部完成」範圍，provider 呼叫增量仍為 **0**。

### 根因與實作

21:07 attempt 4 的 finding、counterevidence、freshness_note 逐字來自當次 `build_fact_example`。數字／來源／日期有效，但「均線的引用格式」「反證引用格式；此筆不自動構成反向結論」是教學內容，不是完成研究；原 schema 的非空字串檢查無法辨別。

- `canonical_fact_prompt.py` 移除可直接填入 finding／counterevidence／freshness_note／analysis_markdown 的示例成品。獨立物件只含 `fact_lines_json_string`、`source_refs`、`source_date_line`：示範 JSON 真換行、獨立 token、同筆引用聯集與共同 ASOF；第二筆 fact 不自動構成反證，無有效日期則 null，不借執行日期。研究要求寫在 JSON 外，不編造新的研究結論。
- 新 `research_evidence_content.py` 只檢查 exact evidence 欄位：已知明確教學行、去 token 後整欄只有 schema 佔位詞、或完全沒有解讀文字的 token 列表。保留原 path／offset／raw output，經 `research_assertion_issues` 接入原採用、quality、cache、metadata repair、snapshot、rerun／publication 重核。`generation_numeric_runtime.py` 對該類失敗加入精準修稿理由，不替模型改稿，不增加重試次數或放寬數字驗證。
- 獨立覆核指出「## 技術發現」作正常小標題，後接解讀及來源時曾被誤拒；先新增真 red，再把一般 schema 詞限定為**整欄**純佔位。明確舊教學行仍逐行檢查；原照抄反例未改期待。短限制、來源格式差異、合理反證不足及明示不採用的行內引用不會因泛稱詞被拒收。
- 另以真 parser／publication 證明：全部 finding 僅「資料不足。」、confidence=low，原先仍可能為 verified_no_action。新增**明確文字分類契約**，不是宣稱原 typed confidence 已涵蓋：所有 finding 去 token／有限標點後均精確為 `資料不足`、`N/A`、`unassessed` 或 `未評估`，才以 `declared_finding_unavailable` 分類研究 unavailable。保留原文、數字 verified 及原 unavailable-fact 分母，不因有數字就計研究成功；既有 no_action 規則允許診斷報告，禁止升格可採用交易或 validated cache。
- 只有 counterevidence 缺資料、任一 finding 已有研究內容、混合句帶有資料不足，或單純低／零 confidence，都不因此推定整份未評估。原本無來源數字、錯 schema、來源衝突仍優先 rejected，不能用 missing marker 繞過。

這是有限、可重現的品質缺口修正；`semantic_coverage=not_checked` 保留。額外一句空泛話或任意改寫是否構成有用研究，仍未由本切片全面認證；不能把沒有命中已知規則當成完整語意合格。

### 原稿、来源與容量

- 四份原始公開回覆不改，production parser 離線重放得到 **2／1／17／2 issues、全部 rejected**。只有最後一份新增精確 finding／counterevidence 兩項；其餘 issue、每份 numeric counts 與 source counts 跟上一候選相同。這是原報告重新驗收，不新增 HTTP failure 或合格報告分母；21:07 live 的 **0／1** 仍原樣保存。
- 四份新版完整提示 estimates 為 **59,353／56,384／57,868／60,973**，64,000 cap 最小餘裕 **3,027**。所有三段來源 JSON、registry、完整 120 根保存日線逐字保持，不刪原來源換取較短提示。這仍是本機 estimator，不保證 provider tokenizer 上界。
- 最新 12 jobs／369 配置仍 **287 admitted／82 rejected**；38 個來源 hashes、routes、schema catalog、配置與 preflight 結果不變。除了 prompt hash／input estimates，各列與前一股數候選一致。無新市場取得、provider call、RAG／embedding，沒有篡改原 capture 或已消耗授權。

### 驗證收據

全部 `/private/tmp/` 檔案，env-i／禁網／私有 DB；不同回合與重疊測試分母不相加。

- 佔位原 red **13 failed／12 passed**；初版 newline 處理錯誤 **5 failed／26 passed**，修正後連同原獨立凍結例 **31 passed／2.01 秒**。泛稱標題反例 **2 failed／25 deselected**，修正後 guide／原例相關 **59 passed／2.24 秒**。舊失敗 XML 不覆寫。
- all-findings availability 原 red **14 failed／4 passed**，新增分類後包含實際 quality、validated cache、snapshot 的 **121 passed／2.73 秒**，`stock-agent-research-findings-availability-green-20260913.xml`。
- 最終 source／schema／evidence／quality／repair／cache／snapshot／rerun／publication／workflow／import／architecture／觀測既有接點整合：**1,275 passed／26.42 秒**，`stock-agent-research-placeholder-final-integration-20260913.xml`。包括 copied output 只重試一次後保留 rejected 草稿、不得走 metadata patch 或 cache 的真 orchestration 測試。
- 原 12 組凍結 graph／checkpoint／snapshot **12 passed／22.97 秒**，`stock-agent-research-placeholder-frozen-graphs-20260913.xml`，仍是 offline doubles、安全診斷，不是 live 報告品質驗收。
- 獨立原照抄／合法控制／heading 修正 **102 passed／1 deselected**；当时唯一 deselected 為尚未決策的新 availability 提案。新增契約後該原反例不再 deselect，**116 passed**，`stock-agent-finding-availability-independent-20260913.xml`。不把前次 deferred 當產品 skip，也不將標題修正留為未處理 finding。
- 最後再補舊 passed 快取／snapshot／部分重跑與有限標記負例，獨立 **139 passed／3.59 秒**，`stock-agent-finding-availability-independent-final-20260913.xml`，含额外 11 項 scratch 對照；production 檔覆核前後 hashes 與下列 final receipt 相同，無剩餘 material finding。部分重跑使用實際支援的 v1（v4 不支援 final-only）；初始 scratch 曾選錯模式及漏重建 parsed，修正為正常流程後驗證，不列為產品缺陷或更改行為以迎合測試。
- 最後容量矩陣 **1 passed／18.41 秒**，`stock-agent-research-placeholder-final-budget-20260913.json/xml`；完整原稿與來源讀回 **1 passed／2.33 秒**，`stock-agent-research-placeholder-readback-20260913.json/xml`；當前程式、38 sources、矩陣比較、schema／route、原 capture 與測試收據核對 **1 passed／0.34 秒**，`stock-agent-research-placeholder-final-receipt-20260913.json/xml`。

本切片相對上一候選只改四個既有 backend 檔、新增 `research_evidence_content.py`；核心 749 檔 SHA256 **`52609e97ac94ed18aa1488113fdb8d36f28fcf1986c7fa643975837ba51b399f`**，完整 916 檔 **`d5fd150568cc844007ac24dfeb03c8252b0277ced96adc85972de35e9b22e8da`**。正式 checkout 再讀回乾淨、HEAD 仍 `758242290e795146520f58f68ffa113cac35e52c`；未 commit／push／PR／部署／重啟、未重建正式 artifacts，Gemma／OOS 與正式 DB 不因本切片變更。

整體仍 active。下一個可執行項目為**品質拒收事件與 attempt 去重**、**保留已核對段落的有界修稿**；之後仍有新候選限額 live、四模式同輸入 paired、每模式至少 30 次跨產業／日期 cohort、完整報告內容驗收及 Git／PR／部署／重啟／canary。不可將本節有限規則、離線流程或 admission 當成已完成上述正式成果。

## 品質退件事件與 attempt 去重（2026-09-13 22:35）

本節完成上一節第一個待辦，保留原歷史紀錄，不代表整體目標完成。

### 修改與邊界

- 根因：原 `event_metrics` 只計 `llm_model_error` 的內容處理失敗。結構／內容 gate 之後拋 `AgentQualityDraftError` 時，graph node 沒有 result delta，telemetry 因而只剩未確認狀態；HTTP 200 仍是真實 transport response，但品質退件被漏掉。
- 新增 `agent_runtime/quality_events.py`，在初始結構、身分／prompt 洩漏、一般品質重寫、最終拒絕及同步／非同步稽核修稿退件當下，發出 typed `agent_content_rejected`。只含 Agent、phase、固定分類與安全路由／匿名 ID；不帶原稿、提示、validator 全文、金鑰或虛構 HTTP code。原稿、checkpoint、rollback、品質 gate 和呼叫上限不變。
- `llm_attempt_identity.py` 僅接受 32 位 hex 的應用程式隨機 ID；每次實際 call attempt 重新生成，同次 request／response／error／quality event 共用。graph telemetry → event adapter → SSE 保留安全 ID；unvalidated draft 存取保留原 ID，但還原仍為 cache、無新 responded model 或 tokens。
- 內容失敗依同 job／Agent／attempt 去重，回應用量及傳輸事件依同 attempt／phase 去重；同 Agent 真正的新嘗試仍分開。無 ID 的舊事件維持逐事件計數，明列 linked attempts／unlinked events，不由時間或文字推測去重。節點例外不得清除已觀測的退件，也不能擦掉真實 provider response。
- 舊 attempt 的成功／失敗 telemetry、延遲 response 不覆蓋新嘗試的狀態。供應商恢復仍需要原失敗→已排重試→同路由新請求→完整傳輸的證據；只有相同 attempt 的後續內容退件，才更新該恢復事件的內容分類。
- 獨立覆核發現一個可重現缺口：新 503 已消耗 pending request 後，遲到舊 response 仍清除該失敗，讓 recovered 從 1 變成 0。以同 Agent latest attempt 隔離修正；原 scratch 期待不改，已重驗關閉。

### 驗證證據

全數 env-i、暫存 SQLite／memory cache、禁止網路；重疊分母不可相加。

- 初始漏記／去重／checkpoint ID／store red：**5 failed／3 passed**；相關首次修正 **105 passed／2.26 秒**。
- 真 node telemetry、延遲回覆及恢復後內容分類 red：**3 failed／10 passed**；修正後 **141 passed／2.63 秒**。同步／非同步 audit red **4 failed／19 passed**；稽核相關整合 **168 passed／75 subtests passed／4.10 秒**。
- 最終 **1,285 passed／75 subtests passed／16.52 秒**，`/private/tmp/stock-agent-quality-rejection-final-integration-20260913.xml`。包括永久 24 項新測試、實際 node wrapper、三次 SQLite 草稿恢復、SSE／唯讀 store、cache、provider／quality／repair／publication、runtime/storage 與架構檢查。
- 原 12 組凍結 graph／checkpoint／snapshot **12 passed／21.12 秒**，`stock-agent-quality-rejection-frozen-graphs-20260913.xml`。仍採 offline provider/service doubles，不能作為 live 品質成果。
- 獨立原反例及相關測試 **92 passed／2.03 秒**，`stock-agent-quality-telemetry-independent-final-20260913.xml`；15 個覆核檔案前後 hash 相同，唯一 material finding 已關閉。詳細唯讀收據為 `/private/tmp/stock-agent-quality-telemetry-independent-review-20260913.md`。早期檔名帶 stale-red 的 4-pass XML 實際已遇主代理同時修正，不當成 faithful red。
- 12 jobs／369 列配置矩陣 **1 passed／17.48 秒**：仍 **287 admitted／82 rejected**；38 sources、routes、schema、配置、input estimates、容量預檢全部與上一候選相同。來源與原 live capture hashes 再逐檔核對未變。
- 最初收據錯把完整 prompt hash 當跨次穩定值，因此留下 **1 failed** 的 `stock-agent-quality-rejection-final-receipt-20260913.xml`。調查確認既有 `initialize_agent_state` 每次生成 UUID、並寫入 AgentState view 的 `run_id`；兩次實際同輸入 prompt 除這一個 UUID 外逐字相同。修正證據比較而非產品行為：369 列除 prompt hash 外所有欄位相同，保留原失敗 XML，不宣稱跨次 prompt hash 相同。
- 修正後完整版本／來源／矩陣／原 capture 收據 **1 passed／2.19 秒**，`stock-agent-quality-rejection-final-receipt-corrected-20260913.xml`，資料收據 `/private/tmp/stock-agent-quality-rejection-final-receipt-20260913.json`。

本切片相對上一候選只變動 14 個 backend 檔（其中新模組 2 個），另新增永久回歸檔與更新本文件／架構導航。核心 SHA256 **`1c8f904c1b3e07e10193410a67a731031588e517392bebeaedb86f037fc090cf`**；完整 backend **`af5eea1dc1cb7f1bc9c6244fc5a6b89db9b8335388e88a389f2eec427d0994ae`**。正式 checkout 讀回乾淨、HEAD 仍 `758242290e795146520f58f68ffa113cac35e52c`；未讀金鑰、未新增 provider call、未改正式 DB／artifacts、未 commit／push／部署／重啟。

下一個離線項目為**保留已核對段落的有界修稿**。仍缺新候選有界 live、四模式 paired／至少每模式 30 次獨立 cohort、完整內容驗收及正式發布／canary。觀測更正只讓失敗原因與分母可信，不代表 Gemma 或四模式實際成功率已提高。

## 保留原稿的有界問題句修稿（2026-09-13）

本節完成上一節的局部修稿切片；整體目標仍 active，未新增 provider 呼叫、完整報告、發布或重啟。

### 修改範圍

- `evidence_prose_repair.py` 只處理 Agent 22／23 完整原稿中的三類已定位錯誤：`unsupported_research_assertion`、`research_metric_source_mismatch`、`research_technical_comparison_mismatch`。若混有 schema、數值、日期或引用錯誤，不走此修稿路徑；原 metadata-only 修復保留。
- 只允許 `analysis_markdown` 或同筆 evidence 的 finding／counterevidence 中已定位的問題句。最多 8 個、不超過各 2,000 字及合計 6,000 字的原稿片段；重複診斷合併，歧義重疊拒絕。定位與替換共用保留原 offset 的句界規則，包含 CRLF／CR 及其他已明定換行符號，不能把鄰接標題納入或新增段落。
- 模型回覆僅含 `repair_id` 和 `target_id/replacement`。所有原 fact／metadata token 保留且不可增補；來源、日期、信心、決策與範圍外文字不可改動。替換後仍經完整 schema、數字、來源、有限敘述與決策驗證；不是 server 自動代寫研究，也不是整篇語意證書。
- 沿用既有單次品質重試、路由、容量及 provider circuit，不增加呼叫上限。修稿提示含完整原稿、diagnostics 及全部來源 JSON；Google framing 保持其 bytes，標示資料不是指令。native schema 仍走既有 provider 相容性投影，應用層嚴格欄位驗證不鬆綁。
- 收據保存原稿、patch、原始輸入／來源綁定及合併 hash。只有完全沒有 repair 標記的收據可視為普通稿，未知／混合格式及移除 provenance 的修稿一律拒收。cache／checkpoint／snapshot／發布重驗；失敗或取消撤回候選與 pending cache，保留原拒收稿。rollback 不再擦掉已觀測的 terminal failed verdict，也不把取消捏造成內容失敗。
- `model_composition`、telemetry 與 UI 分列原稿作者及局部修稿路由，顯示「最後回應僅修正問題句」，計入 `composite_qualified`，不計成最後模型獨力完成整份報告。

### 最後版本驗證

全部 env-i、私有 SQLite／memory cache、禁網；分母有重疊，不相加：

- 最末 78 個相關測試模組 **2,400 passed／36.34 秒**，`/private/tmp/stock-agent-prose-repair-final-integration-closed-20260913.xml`；包含來源、原始 schema、修稿、cache／checkpoint、模型身分、品質事件、發布、UI、imports 與架構。
- 初次擴大回歸保留 **2,373 passed／4 failed** 的原 XML。兩個 failures 是 rollback 擦掉品質 failed，另兩個為上一批 telemetry 增補後的模組行數護欄；前者修正原行為，後者僅合併 import 排版，`quality_gates.py`／`repair_loop.py` 各 257 行、AST 均逐一核對完全不變。未放寬測試門檻；相關補驗 **608 passed／14.09 秒**。
- 最末真實保存原稿＋明示 synthetic patch 重播，以及原三標的四模式 graph／checkpoint／snapshot，合計 **13 passed／23.02 秒**，`stock-agent-prose-repair-final-frozen-20260913.xml`。其中 12 graph 使用明示 offline provider/service doubles，仍只驗證安全診斷流程，不是 12 份 live 成功報告。
- 最末 12 jobs／369 列正常請求矩陣 **1 passed／17.76 秒**，`stock-agent-prose-repair-final-budget-20260913.json/xml`；仍 287 admitted／82 rejected。38 sources、路由、schema、配置、input estimates 與預檢結果未變。既有 AgentState 隨機 run_id 造成跨次 prompt hash 不同，未冒稱 raw prompt hash 相同。
- 最末版本、原稿、完整來源、矩陣與 XML 讀回 **1 passed／0.33 秒**，`stock-agent-prose-repair-final-receipt-20260913.json/xml`。最初問題句重試、未知 kind、句界、Google native schema／source framing 的 red 均保存，沒有覆寫成綠燈。
- 最末獨立覆核 **202 passed／2.66 秒**，`stock-agent-prose-rollback-independent-final-20260913.xml`；包含原 11 個反例及新增 metadata／prose rollback 正負案例、有效 patch 後取消，不改原期待。未知 kind、CR 額外段落、原稿 CR 跨標題與 failed verdict 缺口均關閉。15 個覆核 scope 的 hashes 及限制見 `/private/tmp/stock-agent-prose-rollback-independent-closed-review-20260913.md`；獨立覆核未重跑主代理 2,400 項整合或 graph／矩陣，不混稱其覆蓋。

### 真實首稿的離線修稿證據與限制

原始 21:07 capture 的四份 raw JSON 完全未改，仍分別有 2／1／17／2 個阻擋。首稿 Agent 22 的 MACD 比較與均線排列兩個片段、Agent 23 的持股穩定一句，可由**測試 double 提供的明示 synthetic replacement**通過目前有限 gate；其餘欄位、引用、日期與正文不變。原另外兩份混合錯誤／教學佔位重寫稿不允許局部修稿。

| 首稿 | 原問題片段 | 修稿完整 input 估計 | 距 64k 本機上限 |
| --- | ---: | ---: | ---: |
| Agent 22 | 2 | 51,969 tokens | 12,031 tokens |
| Agent 23 | 1 | 49,368 tokens | 14,632 tokens |

新提示額外包含一段局部修稿資料；原財務、AgentState、registry 三段 JSON 在 Google framing 前後 bytes 完全相同，Agent 22 完整 120 根日線亦保留。詳 `/private/tmp/stock-agent-prose-repair-final-frozen-readback-20260913.json`。這些估计不是 Google 實際 token 帳單，也不是模型能成功產生 patch 的證據。

本切片新增 1 個 backend 模組，合計變動 13 個 backend 檔（其中 2 檔僅 AST 不變的 import 排版），另新增 2 個永久測試檔及更新本文件／架構導航。核心 **`69ae5fb347c78fa6fe235f77398e2b0d5ba6b9bedfeb5cfa6e990e6f7eec8615`**；完整 backend **`d68af90e9240072959106119f5a4bbe06825c899a1ae37b7c7b787d113482941`**。正式 checkout 仍 clean／`758242290e795146520f58f68ffa113cac35e52c`，未改正式 DB、artifacts、Gemma flag、OOS、Git 或服務。

剩餘：新候選限額 live、完整 Agent 24／final audit／報告內容驗收、四模式 paired、至少每模式 30 次跨產業／日期 cohort，以及正式 Git／PR／部署／重啟／canary。既有 21:07 授權已消耗，不以本節離線續作重開 provider 窗口。有限 gate 仍明示 `semantic_coverage=not_checked`，不能宣稱全文正確或成功率已上升。

## 本地 checkpoint 與全庫隔離回歸（2026-09-13）

承接原 P2 的獨立版本保存要求，提交範圍僅為 `codex/report-quality-hardening-20260912` 自基底 `758242290e795146520f58f68ffa113cac35e52c` 累積的本任務來源、測試與文件。這是本地候選 checkpoint，不是 ready-to-merge 或正式發布；新候選 live／完整報告驗收仍待核准及執行。

- 全庫隔離回歸於 23:14 起執行約 18 分鐘，**12,030 passed／2 failed／25 skipped／75 subtests passed**，1084.56 秒，3 個既有 deprecation warnings；原始 JUnit `/private/tmp/stock-agent-report-quality-checkpoint-full-suite-20260913.xml` 保留，不改寫成全綠。全程 env-i、私有 DB／memory cache、禁止正式 Redis／API／provider 存取；未啟用 live flags。
- 第一項失敗為 `test_hcs_plus_round2_contract_coverage_map_has_observed_counts`：局部修稿指令含既有契約詞，使後端檔案數由 30 變 31，測試檔仍 36。依原掃描規則僅同步 `docs/hcs-plus-optimization-state.md`，不改產品或測試期望。原定向 red 為 1 failed／66 passed；文件與架構重驗 **70 passed／3.08 秒**，`stock-agent-report-quality-checkpoint-doc-count-green-20260913.xml`。
- 第二項失敗為既有 Chromium 啟動 preflight；sandbox log 顯示 MachPort `bootstrap_check_in` permission denied。單獨於允許啟動子程序的環境重跑原 8 個 preflight／版本／依賴鎖檢查，**8 passed／1.78 秒**，`stock-agent-report-quality-checkpoint-browser-host-20260913.xml`。未改碼、安裝或升級套件，也未開正式頁面；此結果不是完整瀏覽器視覺驗收。
- 25 skips 仍不當通過：PostgreSQL collection 1、live 2449 smoke 1、外部公開來源 3、commercial live browser 8、歷史 artifacts 1、sandbox browser 2、指定 checkpoint replay 2、Chart.js／visual 6、Redis worker smoke 1。後續真實與部署驗收須按各自邊界執行，不能以本節補驗代替。
- backend 全 919 檔逐一重核，與上一節 `d68af90e9240…` inventory 完全一致；核心 752 檔亦仍 `69ae5fb347c7…`。全庫期間僅上述文件計數同步，後續加本節證據紀錄。沒有為取得測試綠燈更改金融、來源、品質 gate 或模型設定。
- 精確來源清單共 **278 檔：118 modified／160 added**，涵蓋此任務原未追蹤的必要模組與 fixtures。未納入 `.env`、金鑰、DB、cache、正式 output／reports、Git metadata 或其他工作樹。已知秘密特徵掃描零命中，但不將特徵掃描誇大為任意機密內容的完整證明。
- 獨立提交範圍覆核無 material finding：261 Python 檔可解析、1,839 個已識別本地 import、105 個靜態引用與 2 個 literal fixtures 均有 index 對應。詳 `/private/tmp/stock-agent-checkpoint-scope-independent-review-20260913.md`。這不是另一輪完整功能 review；原凍結 captures／歷史私有收據刻意不進 Git，普通 regression fixtures 可重建，但 checkpoint 不包含全部歷史重播資料。

提交時以最後 scope manifest 逐檔比對 working／index，保留原清單與文件修正前證據；本地 commit 不觸發 push、PR、merge、部署、重啟或新 Gemini 呼叫。正式 main／runtime 仍未切換。其餘 P2 live paired／cohort、完整報告品質與發布 canary 不因版本保存而完成。

## 新版限額隔離實測（2026-09-14）

依本次真人「核准」執行新的單次窗口，並未重用 9 月 13 日的授權。測試版本為本地 commit `ccdc3ce68de4e569565f5848dedfe5956365081d`；完整 backend 919 檔 hash 仍為 `d68af90e9240072959106119f5a4bbe06825c899a1ae37b7c7b787d113482941`。同一份 2330.TW／v4 凍結來源、既有 routes 與 explicit environment 均通過 hash 核对。沿用 process-only bounded thinking、單次 SDK HTTP 嘗試、全局最多 6 次 HTTP／transport、內層 220 秒／外層 240 秒；Gemma batching 維持 OFF，不改正式額度、冷卻或品質 gate。

### 本次觀測結果

- 19:53:23 Taipei 啟動，外層總耗時 **22.06 秒**，子程序 exit 2；不是四分鐘期限到達。`AgentQualityDraftError` 導致流程終止，沒有自動重送；剩餘呼叫上限不移作下一輪。
- **4 次 transport／HTTP 嘗試，4 次 HTTP 200 headers，3 份完整 STOP JSON，1 份由流程取消的部分串流。** HTTP 200 不等於完整回覆，更不等於內容合格；取消不是 provider 500／429。
- **完整合格報告 0／1 job**，Agent 24／final audit／renderer 未取得完整上游輸出，沒有正式或隔離發布的 HTML。checkpoint 的 next 是 Agent 22／23，僅為保存狀態，不是程序仍在執行。
- Agent 22 實際回應為 `gemini-3.6-flash`，Agent 23 為 `gemini-3-flash-preview`；這是 request／provider 回傳標籤，不是 provider 內部版本的獨立證明。前次 capture 實際為 Lite，本次不能冒稱相同模型的 paired comparison。
- Gemma 原始角色的兩次 preflight 估計輸入為 45,205／26,322，超過其本機 12,000 輸入預算而使用既有備援；**本次沒有 Gemma HTTP 呼叫，不能推論 Gemma 成功率提升。**
- wire 明示累計 input 212,509、output 5,353、total 217,862 tokens；cached input 32,109 是 input 子集，不另加。包含已取消串流的最後觀測用量，不保證是 provider 最终帳單。

### 退件原因與局部修稿適用範圍

三份完整原稿以同版本正式 validator 離線重播，結果如下；數量是診斷出現次數，不是互相獨立的錯誤數，一個未綁定日期可能拆成數個數字。未綁定不代表數值已證明錯誤，而是不能依目前契約採用。

| 嘗試 | 角色／階段 | 未綁定數字 | 無足夠來源支持的敘述 | token 非獨立成行 | 合計 |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Agent 22 首稿 | 19 | 4 | 0 | 23 |
| 2 | Agent 23 首稿 | 35 | 0 | 1 | 36 |
| 3 | Agent 22 整稿重寫 | 27 | 2 | 0 | 29 |

例如 freshness_note 直接寫數字日期、evidence finding／counterevidence 的均線日數未緊接相符 fact 行、正文自行寫百分比與餘額、RSI／ATR 期間寫法不符合指定格式。部分「均線多頭排列」／MACD 比較敘述也缺其要求的直接來源關聯。Agent 23 正文另有無前週比較卻稱持股穩定、將股數說成金額等值得人工追查的內容；不能以表內有限 matcher 的零筆敘述錯誤宣稱全文無誤。

由於首稿混有數字／格式問題，不符合 metadata-only 或 prose-only 修復的保留範圍，**這次沒有啟動 `evidence_prose_retry`**，而是既有單次完整 JSON 重寫。Agent 22 第二稿仍拒收後，Agent 23 的第二稿被取消；不將後者部分文字當作完整研究或品質退件樣本。此次不能宣稱局部修稿已取得 live 成功或失敗驗證。

### 證據、驗證與下一項優先工作

- 原始隔離 capture：`/private/tmp/stock-agent-quality-graph-2330-v4-prose-20260914T115323Z`，保留 manifest／prompts／requests／raw／wire／events／outcome／metrics／checkpoint，沒有改寫失敗原稿。
- 一次性授權收據：`/private/tmp/stock-agent-prose-approval-20260914T115115Z.consumed.json`；launcher `stock_agent_authorized_prose_2330_v4_20260914.py` 在啟動前獨佔建立並 fsync，保留外層硬截止，禁止重用。
- 原始回覆／來源／分母離線重播 **1 passed／2.09 秒**，`/private/tmp/stock-agent-prose-live-readback-20260914.xml`；對應測試 `test_stock_agent_prose_live_readback_20260914.py` 和結果 `stock-agent-prose-live-readback-20260914.json`。四次請求的三段 source JSON 均逐段 bytes 相同，Agent 22 的 120 根日線保持完整；完整 capture 所有檔案前後 hash 未變。重播新增 provider 呼叫為零。
- 優先調查 **模型可見的欄位指引與應用契約對齊**：本次實際 native responseSchema 的 finding／freshness_note／counterevidence／analysis_markdown 只有 STRING 型別，沒有欄位層來源格式描述；數值規則目前依賴外層 prompt。可評估為這些欄位加入簡短、一致的來源／日期／期間指引，並確認送出的 schema 與預算估計一致。這是由 wire 證據提出的優化假說，尚未實作或證明能改善模型遵循。
- 接續檢查整稿修復指令是否對各類錯誤提供足夠而不矛盾的定位；保留完整診斷及原稿，不為讓局部修稿啟用而忽略數字錯誤，不以伺服器補寫研究或刪除品質 gate 達成表面成功。
- 本輪只完成此次限額 live 與離線核對，未變更產品程式、模型路由、正式 DB／artifacts、Gemma flag 或服務，未 commit／push／部署。仍欠合格完整報告、局部修稿 live 效果、四模式同條件 paired／跨產業日期 cohort 與授權發布 canary；不能宣稱整體優化完成或成功率提升。

## 模型欄位來源指引對齊（2026-09-14，離線候選）

承接上述 live 發現，完成可在既有授權內執行的本地優化，不重開 provider 窗口。這一批只改善指令位置，尚未證明模型遵循或完整報告成功率會提升。

- 新增 `generation_schema_guidance.py`：僅對 Agent 22／23 且具有既有精確版本化數字契約 marker 的正常原稿請求，為 finding、source_refs、freshness_note、counterevidence、as_of_date、analysis_markdown 六欄加入靜態描述。明示同筆來源、fact／metadata 獨立行、共同 ASOF、凍結 fetch_date 上限、指標期間及未知資料限制；不插入來源自由文字或生成研究結論。
- `agent_runtime/generation_config.py` 增加可省略的 prompt 參數；同步／非同步／串流與輸入估算共用。同時同步既有 `quality_pilot_budget_probe.py`，避免觀測工具漏掉描述成本。原 provider schema 只加 description，application schema 的型別、必填、enum、bounds 及所有品質 gate 原封不動。
- 原本的 metadata／prose 局部修復 schema 優先返回，不混入整份報告提示；其他角色、tool-backed 角色與無版本契約的舊請求不變。source JSON、路由、generation profile、output／thinking 限制、quota、retry、cache、發布與正式服務未修改。

### 驗證結果

- TDD 首次實際 request-config 測試 **2 failed**，原因均為欄位 description 空白；首轮相關 **136 passed**。原 red 檔保留 `/private/tmp/stock-agent-schema-guidance-red-20260914.xml`。
- 擴大含真實 Google SDK 的 MockTransport 序列化後 **167 passed／2.66 秒**，`stock-agent-schema-guidance-sdk-green-20260914.xml`。初次 SDK 測試因套件原地展開 `$defs`，在錯誤時點讀 expected 而產生 2 failures；改為序列化前深拷貝 expected，仍逐欄核對送出的 wire，沒有放寬期待或修改產品以配合測試。
- 最終 24 個相關模組 **1,121 passed／75 subtests passed／19.97 秒**，`stock-agent-schema-guidance-integration-v2-20260914.xml`；涵蓋三種 transport、schema、budget、input admission、來源、原始數字／日期、修稿、graph／publication、audit 與 imports／architecture。最初整合命令誤用不存在的 architecture 測試檔而未執行測試，其輸出保留，正確模組重跑如上。
- 12 組凍結輸入／369 列矩陣 **1 passed／17.27 秒**，`stock-agent-schema-guidance-budget-20260914.json/xml`；30 列 Agent 22／23 的本機輸入估計增加 **1,084–1,085 tokens**，其他角色估計及 schema 不變。38 份來源與 route hash 不變，仍 **287 admitted／82 rejected**，沒有新增超限。不把本機估算當 provider token／quota 真相。
- 9 月 14 日四次原始請求的配置、來源 bytes、完整原稿及 gate 離線讀回 **1 passed／2.20 秒**，`stock-agent-schema-guidance-readback-v2-20260914.xml`；結果 `stock-agent-schema-guidance-readback-20260914.json`。除了新增六個 description，配置逐項相同；三份完整原稿的全部 rejection issues 與原測試相同，取消串流不納入品質成功分母。原 capture 每檔 hash 不變，未新增 provider 呼叫。
- 獨立覆核 **160 passed／2.91 秒**，其中 20 個獨立案例；無 material finding。`stock-agent-schema-guidance-independent-final-v2-20260914.xml`；收據 `/private/tmp/stock-agent-schema-guidance-independent-review-20260914.md`（SHA `4145567cd2d9bf39647fecfbe8b0160fd5eb91aa99546c41e208140e83f73836`）。含 exact marker／角色隔離、來源不注入提示、SDK wire、估算及原始 wrong-date／wrong-ref 仍拒收。以上測試分母互有重疊，不相加。

核心 753 檔 hash `a9632542918d63908529dbd1dbe1e2507a95651debc901499a911a946db36d1b`；完整 backend 920 檔 hash `adab3613991babc4f893af8e46af368ab3cc4b8c421f889c2539a29a023e8cf2`。相較 `ccdc3ce6`，後端僅 generation_config 與新 guidance 模組兩檔不同，其餘 918 個既有 backend 檔保持原值。

本地版本保存不代表 ready-to-merge 或正式發布。下一個必要證據仍是新候選限額 live（需新的真人授權）、合格完整報告與同條件四模式 paired／cohort；也仍未完成授權發布／重啟／canary。不能將上一節 0／1 live 結果重新歸因為這一批已成功。
