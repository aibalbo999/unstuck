# 四模式完整後續優化計畫

日期：2026-09-07。狀態：總計畫已核准執行；F1.1、F1.2、F1.3、F2.1～F2.5、F3.1、F3.2 工程／artifact／瀏覽器證據與 G1、G2、G3 已完成；F4 已完成唯讀候選盤點，正式送件／載入／重建仍待核定範圍與目前 runtime revision；F5／F6 受外部資料成熟度與條件約束。

查驗基線：`codex/analysis-credibility-spec`，`32711c4838521816ba565c4acbee13029f7eb4a9`。實際 checkout 為 `/Volumes/X10 Pro Mac/stock-agent`；撰寫前工作樹乾淨。Runtime doctor 指向既有 canonical SQLite、Redis 與 `backend/output`，不能據此推論執行中 API／Worker 已載入此 commit。

## 1. 目標、既有決定與完成定義

目標是讓四模式的新報告具備一致且可追溯的分析來源、可靠的失敗恢復、對應模式期限的評估，以及可以核對樣本分母的效果證據。優先完成既有缺口，再用新取得的證據決定下一輪分析規則調整。

本文件統一後續順序與交付關卡，沿用下列已核准規格，不重寫已完成實作：

- [內容可信度規格](../specs/2026-09-06-analysis-credibility-followup-design.md)與[交付紀錄](../../four-mode-credibility-delivery-2026-09-06.md)。
- [PostgreSQL 規格](../specs/2026-09-06-postgres-isolated-verification-design.md)與[既有實作計畫](2026-09-06-postgres-isolated-verification-implementation-plan.md)。
- [OOS 規格](../specs/2026-09-06-oos-isolated-verification-design.md)：先完成 PG，再實作獨立 OOS 批次；第一個 OOS 交付限定合成／離線資料。
- [四模式既有邏輯](../../four-mode-analysis-logic-2026-09-05.md)：A 為長線研究，B 為部位決策，C 為反證／泡沫風控，D 為短線事件波段。

完成分成三個可獨立核對的層次：

| 完成層次 | 必要證據 | 可作的結論 |
| --- | --- | --- |
| 工程驗收 | PG 真實案例與清理、OOS-01～10、相關回歸與代表報告一致性驗證 | 隔離工具與已修正邏輯符合契約 |
| 使用者可用 | 指定 revision 已載入正式服務，核定清單已有新報告，API／頁面讀到相同內容 | 本批修正在正式工作流生效 |
| 效果驗證 | 事前凍結的真實 cohort、成熟資料、完整分母、同口徑比較與限制 | 對所研究版本及樣本可提出有範圍的效果結論；也可能是無改善或證據不足 |

測試成功不預先承諾勝率、獲利或所有 warning 歸零。效果沒有改善也必須如實交付，不能以不斷換樣本或調門檻追求「成功」。

授權沿用：PG 隔離環境建置／測試與 OOS 合成離線實作已核准，續作時不重新詢問相同事項。本次請求的終點是計畫交付。正式發布、特定歷史重建、真實前瞻收樣，以及新增資料採購／策略變更，依其具體範圍處理；既有 PG／OOS 規格明確排除的外部動作不因本總計畫而自動啟動。

## 2. 已完成基線與本次新確認的缺口

| 項目 | 已有證據 | 後續工作 |
| --- | --- | --- |
| 四模式基本契約 | A 未知護城河、B 等待／零部位、C 不預設做空、D 日 OHLC／5、10 交易日已落地 | 保留相容性並驗證最新修正的實際產物；不重做相同功能 |
| 金融來源、依賴修復、新聞 manifest、精確 evidence | `fec17737`；交付紀錄載明完整隔離回歸 `9,716 passed / 21 skipped / 75 subtests passed` | 當時證據不等於目前正式服務或歷史報告已更新 |
| PG 工具及測試程式 | `32711c48` 的前一輪合併 scoped command：`267 passed / 1 skipped / 2 warnings` | 本批已完成固定 17 個 live cases／51 phases；另以 fresh scoped regression 更新證據 |
| OOS | 已有完整核准規格與可重用的純評估核心 | 尚無研究 store、cohort admission、嚴格摘要或 OOS 容器驗收 |
| 歷史與正式交付 | 舊版曾完成正式驗收，詳見[前輪收尾紀錄](../../remaining-analysis-delivery-2026-09-06.md) | 不能將舊版正式驗收套用到後來的可信度分支 |
| 真實前瞻效果 | 未有本計畫可引用的成熟 cohort | 先完成工具，再凍結 protocol 與未來收樣 |

上述測試數字是已檢視的既有執行證據；本次計畫編寫沒有再跑全套測試。兩個 warning 是 legacy repair facade 棄用提示。舊盤點的 49 組最新版／102 份歷史版本，以及 28 組追蹤工作是不同集合，數量可能已變，不能直接當成新的送件清單。

本次從啟動程式確認，前次「環境無法完成 live 準備」的說法過強：

1. 主機 CLI 不需要 import `psycopg`；driver 安裝在隔離 image。主機缺 PQ wrapper 不是容器測試的阻塞因素。
2. `STOCK_AGENT_PG_VALIDATION_POLICY` 由容器 entrypoint 產生；主機目前沒有 policy 屬正常狀態。
3. Docker server 可用、固定 base image 尚未存在，只表示尚待 build／pull。下載、apt pin、wheel 相容性必須由第一次建置判定，不能先宣稱不可執行。
4. `tests/pg_validation/launcher.py` 在容器非零退出時，先 raise 再進清理，沒有先取回 structured failure result；建置失敗等路徑也可能只留下 exit code。失敗診斷與未清理資源 ID 尚有缺口。
5. `tests/pg_validation/result.py` 現在只記 Python／PG／psycopg／libpq，核准 PG 規格另要求 saver 實際版本；固定 lock 不等於實際 runtime 版本證據。

## 3. 優先順序與相依關係

| 階段 | 優先級 | 工作 | 前置條件／可並行工作 | 交付關卡 |
| --- | --- | --- | --- | --- |
| F1 | P0 | 補 PG 失敗證據與版本，首次完整 live run | 既有授權；可立即開始 | G1：固定環境真實驗收、清理與證據完整 |
| F2 | P1 | 實作 OOS 合成離線研究流程 | G1；儲存本身不依賴 PG，但沿用已驗證隔離基礎 | G2：OOS-01～10、可重現 bundle、真實樣本數 0 |
| F3 | P1 | 可信度修正的代表案例與發布準備 | 可與 F1／F2 的獨立檔案工作並行 | G3：最新交付版本的內容、失敗分支與 UI 證據 |
| F4 | P1 | 正式載入及核定歷史報告更新 | G3 與對應發布／生成範圍；不必等待成熟 OOS | G4：revision、Job、artifact、API／頁面逐項對得上 |
| F5 | P2 | 真實前瞻 protocol、收樣與到期評估 | G2、實際執行版本、具體研究範圍與資料條件 | G5：完整 cohort 與成熟結果，或明確未成熟／不足 |
| F6 | P2／條件式 | 依品質或效果證據調整四模式 | 明確重現的內容缺陷，或 F5 形成可檢驗假設 | 每項有獨立版本、回歸與新驗證資料 |

執行責任：主代理統一管理清單、Git、runtime 與交付；測試／OOS／內容調查可交給各自擁有檔案的代理，重要差異由獨立 reviewer 覆核。共用 launcher、store、Git index、DB 與服務操作依序整合。

排程採關卡而非預填完成日期：F1 首次建置結果決定環境修正工作量；F2 按以下切片交付。F5 的 D 須等待實際 5／10 交易日，A 須 3／6／12 曆月，B／C 依明示期限；工程工期不能縮短市場資料成熟時間。

## 4. F1：完成 PostgreSQL 真實驗收

### F1.1 補失敗診斷與 runtime 身分

- [x] 在既有 `tests/pg_validation/{launcher,result,entrypoint}.py` 與對應 `tests/test_postgres_validation_{launcher,result,runtime}.py` 實作。
- [x] 先加入可重現反例：build 失敗、PG readiness 失敗、collection／case 失敗、timeout／中斷、result 缺失／毀損、cleanup 失敗時，呼叫端能得到安全且具 stage 的結果。
- [x] 新增獨立且版本化的 failure envelope：run ID、stage、穩定 reason code、已知 manifest／image／container ID、exit code、cleanup 狀態；未知欄位保持 unavailable。若目錄本身不安全，僅回受限 stderr／非零，不強行寫入該目錄。
- [x] 容器失敗時只有在身分核對通過後才取回有界 structured result；不得匯出任意檔案、PG raw log、traceback、DSN 或秘密。壞 result 只產生主機建立的失敗摘要，不將未驗證 payload 放入交付。
- [x] 成功結果新增容器內 saver distribution 實際版本及 `psycopg.pq.__impl__`；producer、validator、測試與 schema 版本同步更新，要求 binary 實作。舊結果可保留作歷史，不冒充新版驗收。
- [x] 成功判定仍要求完整 17-case registry／51 個唯一 phases 全通過、有效 runtime 版本、server stopped 與精確 cleanup；failure envelope 永遠不能通過成功 validator。

完成條件：上述反例確實檢出目前缺口，修正後通過 scoped regression；symlink／TOCTOU、原子匯出、大小上限與 cleanup-failed 保護維持，無新增正式 runtime 寫入。實際結果：`tests/test_postgres_validation_result.py tests/test_postgres_validation_launcher.py tests/test_postgres_validation_runtime.py` 共 `120 passed`。

### F1.2 固定映像建置、完整案例與直接缺陷修復

- [x] 將 F1.1 整合成可追溯的本機提交；由既有 launcher 產生白名單 build context。沿用 PG 17.11 digest、Python／binary lock 與 `linux/arm64`，記錄實際 derived image ID。
- [x] 公開依賴下載只在建置階段進行；執行階段保留 `network=none`、Unix socket、非 root、無 host bind mount／port publication，2 CPU／2 GiB／256 PIDs。
- [x] 從完整 registry 執行 PG-00～PG-08：migration／重開、原稿與中稿、deferred／取消、新 saver／graph、thread／agent 隔離、真依賴失效、真 `42501` 拒寫、完成 graph 不重複發布及 native 負面案例。
- [x] 若建置因固定版本取得或平台相容性失敗，保存具體失敗階段與證據，再修測試環境；任何 pin 變更必須記錄來源與理由並重新驗證，不改成浮動版本或 fake pass。
- [x] 若 live 揭露缺陷，只修直接相關 checkpoint／draft／測試 fixture 邏輯，加入行為回歸後重跑受影響項及完整 registry；本批修正 build context／apt pin／inspect contract／UTF8 encoding／bootstrap owner setup，未改 production checkpoint adapter。

F1.2 實際證據：`derived_image=sha256:9816a7d97b354827d9bc281974a8b90d81b1733d630657256499677cd601ec3a`；live `17 passed`、固定 registry `17/17 cases`、`51/51 phases`、`collection_errors=0`、`exit_code=0`。runtime attestation 為 Python `3.13.5`、PostgreSQL `server_version_num=170011`、psycopg `3.3.4`、libpq `180000`、saver `3.1.0`、binary implementation。首次 build 的具體修正與理由已寫入 [PG 操作手冊](../../postgres-isolated-verification.md)與[交付紀錄](../../postgres-isolated-verification-delivery-2026-09-06.md)。

### F1.3 驗證清理並更新原交付文件

- [x] 對本次精確 CID 重查身分再清理；成功、失敗、中斷、cleanup failure 都有對應契約測試。真實 run 保存 server stop、CID 移除／殘留觀察；故障注入限本次資源或 fake Docker seam。
- [x] cleanup failure 回非零並列已知本次 CID，不使用名稱掃描／prune；派生 image 是否保留作快取如實記錄。
- [x] 更新既有 PG 計畫未勾選的 live 步驟、操作手冊與交付紀錄，追加實際結果，不抹除先前離線驗證時點。

G1：完成。Plan-required scoped offline regression 為 `233 passed, 2 warnings`；補充 PG contract／live module offline lane 為 `37 passed, 1 skipped`（skip 是無 policy 的保護邊界）；本次 live `17/17 cases`、`51/51 phases`、`status=passed`、`server_stop_status=stopped`、`cleanup_status=removed`。G1 只證明隔離 adapter／測試契約與生命週期，不宣稱切換正式 PostgreSQL。

## 5. F2：實作 OOS 離線研究流程

以下是核准 OOS 規格的實作切片。`backend/oos_research/`、`tests/oos_validation/`、`tests/test_oos_*.py`、`scripts/run_oos_validation.py` 已建立；每個模組保持單一責任；不另建正式 DB table、API 或 UI。

### F2.1 建立 OOS 隔離 profile 與不可變研究 store

- [x] 新增 `tests/oos_validation/{launcher,entrypoint,result}.py` 與測試 image 設定、薄入口 `scripts/run_oos_validation.py`。OOS profile 固定 image digest、network none、read-only root、無 host mount，結果只由安全 envelope 匯出。
- [x] OOS 容器不啟動 PG，無網路及正式目錄掛載；一般單元測試走既有隔離 runner。純研究核心只 import 純 evaluator／stdlib，未 import config、fetcher、正式 stores。
- [x] 新增 `backend/oos_research/{manifest,records,store}.py`：manifest 必填政策、版本化 canonical JSON、原始 bytes hash、content-addressed blobs、exclusive create、原子提交、讀回校驗。
- [x] root 明示且以 `.oos-study` 綁定 study；空值、repo／cache／output、越界、symlink 拒絕。半檔、同 ID 異內容、缺 record／hash 錯誤不會變成空研究或覆寫成功。

驗收：OOS-01／02 及 PG 共用部分回歸。相同 inputs 重跑保持身分，不同內容明確衝突；本機 mtime 不構成事前登記證據。

### F2.2 完整候選 ledger、準入與時間證據

- [x] 新增 `backend/oos_research/{inventory,admission,provenance}.py`；每個候選保留 admission 狀態與理由，缺報告／缺資料不從分母刪除。
- [x] 驗證 HTML／Markdown／snapshot／parsed plan 原始 hash、pipeline／ticker、prompt fingerprint、code／dirty、model、quality metadata；不以 filename 作版本 join。
- [x] 時間一律帶時區並驗證首次可得→input cutoff→生成→可得順序；缺公布時間、dirty、只刷新舊結論、prospective 無 receipt 均維持不足或失敗，study kind 不自動升級。
- [x] 固定首個評估 session 為可得日之後第一個 session；prospective late seal 保留 `late_seal`，inventory 保留 provisional／closed／incomplete 與 hash。

驗收：OOS-03／04，包括公布晚於結論但早於評估、跨到期才封存、缺報告、未知來源與跨版本混用反例。

### F2.3 凍結離線行情與嚴格四模式 wrapper

- [x] 新增 `backend/oos_research/{dataset,calendar,policies,prediction,trades}.py`；dataset 固定來源、時區、session、bar 完成時間、as-of、raw 價格及企業行動政策與 hash。
- [x] 嚴格拒絕重複／非法／未完成 bar、混合政策與未知資料；A 使用既有 `add_calendar_months`／`evaluate_prediction` 並固定 3／6／12 月，未知 label／價格不產生 miss。
- [x] B／C／D 使用純 `evaluate_trade_path` wrapper，拒絕未知 direction、缺期限與不可執行 plan，不呼叫 `evaluate_report_trades()`；保留未成交、觀察、ambiguous、成本未知等狀態。
- [x] 成本與 benchmark 缺失保持 null，gross／net 分開；研究資料未經 `run_due_backtests()`、`compute_performance_stats()` 或正式 store 取寫。

驗收：OOS-05／06／07，加既有 mode backtest 相容性回歸。研究資料不能經 `run_due_backtests()`、`compute_performance_stats()` 或正式 store 取寫。

### F2.4 結果版本與完整分母摘要

- [x] 新增 `backend/oos_research/{evaluation,summary}.py`；結果 identity 綁定 study、candidate、bundle、horizon、evaluator、dataset／calendar、policy、as-of，執行時間另置 metadata。
- [x] pending→成熟以新 revision 保存；摘要由完整 ledger 及明示 cutoff 選 revision，0 個可評分時 hit rate／ROI 為 null，gross／net／benchmark 各有分母。
- [x] 摘要聚合 admission、report identity、ticker、模式／期限及狀態；分頁欄位明示 total／returned／truncated，未使用 production 50／2000 筆截斷。

驗收：OOS-08／09；以合成資料確認計數守恆、版本唯一與每個分母能回查候選。

### F2.5 薄 CLI、完整重播與交付

- [x] 新增 `backend/oos_research/cli.py`，串接登記→候選→準入→離線 dataset→評估→摘要；root、manifest、inventory、dataset 均必填，不從正式 config 補預設。
- [x] 合成四模式 cohort 可重跑並輸出完整 JSON bundle；OOS-01～10 有明確正反例測試，外層 validation CLI 只執行本批 synthetic suite。
- [x] 已保存 study／input／evaluator／image hash 與 isolation／cleanup evidence；完整 JSON 摘要由 CLI／store 產生，尚未宣稱真實 prospective 效果。

G2：完成。OOS-01～10 合成離線驗收 `11 passed`、隔離結果／bundle 契約 `7 passed`（合併 `18 passed`）、既有 mode regression `154 passed`；實際容器 image `sha256:03e72007e0935195d42d91abb51fe3456bca02e083dbbec829feed6a43781ceb`，network none、read-only、無 host mount，結果 `10 passed / 0 failed / exit_code=0`，並已移除精確 CID。交付中的真實 prospective 樣本數仍為 0，成熟前瞻績效仍未驗證。

## 6. F3：四模式內容與發布準備

### F3.1 凍結代表驗收案例

- [x] 保留已查驗的 1623 A、1623 D、2308 C 作錯誤來源回放；`tests/test_credibility_artifact_replay_optional.py` 已用 `ReportArtifactLocator` 解析 bundle，讀取實際 keys 並記 hash，不依賴 `unknown-month` 路徑作定位。
- [x] 既有三案斷言保留；缺 fixture 仍明確 skip，不能抓另一份最新版代替。opt-in replay（指定 `CREDIBILITY_REPLAY_OUTPUT_DIR=backend/output`）通過 `1 passed`，9 個原始 artifact hash 前後不變。
- [x] 以既有內容／證據／模式契約測試與 deterministic OOS fixtures 覆蓋下表的拒絕、等待、未知、精確 mapping、失敗恢復與四模式期限行為；正式模型樣本仍只作產物驗收，不要求模型必定生成某個缺值／取消分支。

| 模式／共同層 | 必須證明的行為 | 相關既有責任模組 |
| --- | --- | --- |
| A | 負 FCF／缺事實無占位 DCF；可用 DCF 同方法同單位；相對估值不混比；護城河未知保留；上游變動後最終結論使用新版本 | `quant_input_contract.py`、`quant_metric_contract.py`、`final_audit_dcf.py`、`analysis_dependencies.py` |
| B | Long／Short 價格順序與風報比正確；等待＋0% 合法；未知成本不產 net ROI；續抱／減碼無持倉歷史明示不足 | `final_audit_mode_contracts.py`、`mode_trade_backtest.py`、`reporting/content_credibility_trade_setup.py` |
| C | 估值、催化時點與可執行空單分開；反證不足可不放空；複合條件不降成單一價格；期限與來源一致 | `final_audit_mode_contracts.py`、`trade_path_backtest.py`、`evidence_recommendation_claims.py` |
| D | 日 OHLC／SMA 精確欄位；Neutral 無交易；未來 14 日事件需日期／來源；5／10 交易日期限；同根順序不明保留 | `short_term_market_data.py`、`evidence_daily_price_claims.py`、`evidence_technical_claims.py`、`trade_path_backtest.py` |
| 共通 | 原稿／中稿恢復重驗；上游修復與下游重建原子採用；新聞只引用最後 prompt 可見來源；失敗／假引用阻擋發布；HTML／Markdown／snapshot／API 投影一致 | `agent_runtime/repair_transaction.py`、`workflow_quality_drafts.py`、`market_context_manifest.py`、`market_context_snapshot.py`、`report_rerun_audit.py`、`reporting/market_context.py` |

### F3.2 驗證交付 revision 與可見產物

- [x] 對 OOS／artifact locator／既有四模式差異執行必要回歸與秘密／不應提交檔案檢查；內容可信度／證據／模式契約 scoped lane 共 `1630 passed, 1 skipped`，另 opt-in artifact replay `1 passed`。
- [x] 正式 API／真瀏覽器 1280／375、CSP／圖表的唯讀驗證已執行：1623 A、1623 D、2308 C 於 1280／375 各一組均通過 charts／layout、tooltip 與 zero errors；HTML 下載與 CSP／content-type header 亦通過。Redis／provider 仍是 optional，未執行項目維持 unverified，不算 pass。
- [x] 以同一保存 artifact cohort 進行新規則 replay：負 FCF／占位 DCF、錯誤 evidence path、版本／來源 mismatch、未知資訊的反例均由既有 gate 拒絕或標示 unverifiable；合法等待／未知仍保留。未將不同抽樣或資料集換算成品質改善百分比。
- [x] 已整理發布候選 revision（本分支最新 commit）、OOS／四模式依賴、可回復前一版、影響範圍、通過／未執行驗證與 1623 A／D、2308 C 代表清單；正式 runtime 載入仍明示未驗證。

G3：工程與保存 artifact 驗收完成；代表案例 `ReportArtifactLocator` replay 通過，既有內容／證據／模式回歸 `1630 passed, 1 skipped`，三組代表報告的 1280／375 browser QA、HTML／Markdown／snapshot download、CSP 與 content-type 檢查通過。執行中的 API 程序仍早於本分支最新 revision，故 runtime 載入與正式發布維持未驗證；F3 不要求等待數月才發布已證實的內容錯誤修正。

## 7. F4：正式載入與歷史報告更新

這是正式服務與生成資源的外部動作階段。先完成 F3 的可審閱發布候選與明確清單，再依已有且適用的授權執行；不把早期另一批 commit／push 的同意推定為本分支 merge、重啟或無上限生成的授權。

目前狀態（2026-09-07）：已完成唯讀前置盤點，但尚未送件。`/healthz`／`/readyz`、`/api/reports`、`/api/observability/active-jobs` 與 `/api/decision-tracking` 均可讀；decision-tracking 在較寬的 10 秒界線內約 4.03 秒回應，active jobs 為 `0`（回傳 10 筆歷史均 `done`），tracking items 為 `7` 且 enabled `7`。仍沒有可驗證的 API／Worker revision 或核定歷史範圍，故不送件、不重啟、不改寫正式 output。這是可定位的外部 runtime／範圍前置條件，不把未確認當完成。

更新：`/healthz`、`/readyz`、`/api/observability/active-jobs`、`/api/decision-tracking` 與 `/api/reports` 已可讀；新增唯讀工具並完成兩頁盤點，完整 indexed reports `148`、`current=109`、`needs_rerun=39`，清單 hash `0e870f7451506bdcccfd7753191a6661766d4db4774102aca5bf5c5d8c2417cd`。active jobs=0、tracking=7／7。仍未核定送件範圍，亦未送 Job／重啟／改寫正式 artifacts。

- [x] 重新唯讀盤點 indexed reports 的全部版本與每 ticker／模式狀態；產生有時間與 hash 的候選清單，區分 `current`／`needs_rerun`，並保留 148 筆完整分母與 39 筆候選的理由。追蹤清單現可在 10 秒界線內讀取（7／7 enabled），但仍未冒稱已核定送件範圍。
- [ ] 建議預設更新「核定每組最新版」，保留原歷史。102 份歷史回放若被選定，另建版本並標 retrospective，不冒稱原日期的前瞻分析。先前 49／102 只是舊盤點，不是固定配額。
- [x] 新增 `scripts/rebuild_tracked_reports.py prepare-indexed` 與 `tests/test_rebuild_tracked_reports.py` 回歸；以 `/api/reports` 全分頁建立 `prepare_only` manifest，實際 148 筆／57 個 ticker-mode 最新群組／28 個最新重跑候選。`submit` 明確拒絕 prepare-only manifest，未把追蹤 28 組冒稱全量完成。
- [x] 已核對本分支 scoped diff、驗證證據並建立本地提交（前序實作提交亦保留）；未推送／建立 PR／merge，因本輪未重新核定外部發布授權。
- [ ] 核對 remote／base 後，在適用授權內完成 push／PR／merge 與必要 CI；整合後若程式變動，對實際整合 revision 補必要回歸，再進入 runtime 載入。
- [ ] 發布前核對執行中程序的 owner、checkout、queue／active jobs；保留 `.env`、歷史 artifact hashes、queue 與 quota 狀態基線。用現有正式啟動入口載入指定版本並驗證 health／ready、API／Worker 版本及四模式路由。
- [ ] 先送具體代表工作，核對實際 Job 與產物的 code／prompt／input fingerprint，確認有新結論；不能把 resume 舊完成工作或 metadata refresh 當新版重建。
- [ ] 再按核定清單小批新增報告，尊重原 provider quota／deferred 政策。每批保存送件前 pending、返回 Job ID、完成／失敗／未確認與新舊 artifact 對照；回應不明先查既有 Job，不自動重送。
- [ ] 歷史失敗與舊報告保留；失敗不算更新完成。逐份核對最新內容、final gate、可見 warning 與 provenance，並確認新報告可由正式 API／頁面讀取。

G4：核定清單 `completed + failed + pending + unconfirmed = total`，可逐份查證；宣稱「全部更新」時 failed／pending／unconfirmed 必須為 0，且每份確為核定版本的新結論。

停止／回復：錯誤發布、來源身分漂移或健康檢查退化時，停止後續送件並恢復前一個已驗證程式版本；已建立的新 Job／artifact 不以刪除掩蓋，保留其狀態與修復記錄。除非另有精確刪除範圍，本流程不使用 purge。

## 8. F5：真實前瞻 protocol 與到期評估

目前狀態：尚未啟用。真實 prospective 需要使用者另行固定 ticker universe、收樣起訖、模型／版本政策、事前 receipt 來源與資料成本；即使立即啟用，A 的 3／6／12 個月及 D 的 5／10 交易日仍須等待資料成熟。合成 OOS 只證明工具行為，不可替代這些外部證據。

### F5.1 在收樣前固定研究內容

- [ ] 先根據 G2 工具能力產出具體 protocol：ticker universe、四模式、收樣起訖、產製頻率、版本選擇規則、模型／prompt／code 政策、每模式主要期限與指標、缺樣／排除規則、成本／benchmark／企業行動／calendar 政策。
- [ ] 建議 universe 使用核定當下的追蹤清單快照；實際 ticker 列表、開始日、生成預算及模型成本在啟用前明列。不能用結果挑股票或預先填勝率／最小樣本已足夠的結論。
- [ ] 明定可查的事前登記與 artifact 封存 receipt 來源、時間、hash 及驗證方式。本機 timestamp 不能單獨自證；若現有工具無此證據，保持未驗證 prospective 或 retrospective 身分，先完成有用的離線研究。
- [ ] 盤點並補真正需要的時間 provenance／事件 ledger 接線：資料首次可得、分析 input cutoff、report available、實際模型／fallback、生成失敗與未產製事件。從 `report_reproducibility.py`、資料來源 audit 與 job telemetry 接入，不把 `fetched_at` 重新命名成公布時間。
- [ ] 凍結未來評估資料的取得／匯入流程與 allowed inputs；完整收樣與企業行動／成本缺口若無法取得，明確保留 insufficient 狀態，不暗增資料訂閱。

### F5.2 收集、成熟與比較

- [ ] 依固定生成清單登記全部成功／缺報告／失敗／排除候選，封存原始版本。進行中的規則變更另開 study；保留原 study 的分母與結果。
- [ ] 到期後匯入帶來源與完成時間的完整 sessions；D 5／10 日、A 3／6／12 月、B／C 明示期限各自評估。未成熟原樣 pending，不前移日期。
- [ ] 提供完整候選、可評分、成本可用、benchmark 可用分母，分開四模式與期限；不把多期限／重疊持有期當獨立樣本。沒有淨成本證據不能報 net 改善。
- [ ] 若要比較兩個分析版本，必須事前固定同候選、同資料可得時間、模型／prompt 政策與指標，保存實際版本差異；改策略與改模型的效果不能混為單一因果結論。
- [ ] 首輪只給與資料量相稱的描述結果；顯著性／樣本量設計、調參與策略選擇是另個明示研究切片，不從少量樣本推導可靠勝率。

G5：取得有可驗證 provenance 與完整分母的結果，或清楚列出成熟時間／資料不足。若需跨日觀察，再依使用者要求建立持續監測；本計畫不自動建立排程。

## 9. F6：依證據安排第二輪模式優化

目前狀態：條件尚未觸發。F2／F3 的工程驗收沒有提供真實 cohort 的穩定偏差或可檢驗策略假設，因此本階段不擅自調參、改策略或宣稱效果改善。

下列為條件式候選，並非本次已確認 bug 或已核准的新策略。先用 F3／F5 分類實際問題；只有可重現品質缺陷或事前可檢驗假設才安排實作。

| 方向 | 啟動證據 | 可研究的具體改進 | 驗收與停止條件 |
| --- | --- | --- | --- |
| A 估值與長線論點 | 真實輸入／估值方法仍有可定位缺口，或同口徑校準顯示偏差 | 改善必要財務資料完整度、明列假設敏感度與反證；未知仍保持不可用 | 數值可重算；只用訓練／驗證資料選方案，新未見樣本驗證；無證據不放寬 DCF 適用條件 |
| B 部位管理 | 既有部位動作因缺成交／持倉歷史不能驗證 | 在取得明確資料來源後加入持倉歷史契約、部位風險與成本核對 | 不捏造成本、股數；新進場／等待相容；收益證據須來自實際可得歷史 |
| C 事件與空方反證 | 大量真實候選因複合條件或借券條件不足不可評估 | 有發布時間證據後支援明確的事件＋價格條件解析；拆分空方執行成本與反證 | 不只抽價格數字；反例／軋空條件可追溯，缺事件／借券資訊仍不足 |
| D 短線成交可信度 | 同根 ambiguous、跳空或事件時點造成可量測缺口 | 比較更細時間解析度資料的價值，先做有限資料樣本；再決定是否擴充 | 有資料授權與時間證據才擴充；無法判先後仍 ambiguous；維持 5／10 日及不交易契約 |
| 共通品質與信心 | 錯誤分類可重現、品質分組／信心與結果存在穩定差異 | 修正明確 evidence mapping；評估分模式信心校準及 bounded repair 成本 | 不以信心自證，不用測試集反覆調門檻；記成功率、錯誤發布、重跑次數／耗時與樣本分母 |

每個被選項採「凍結基準→失敗案例或研究假設→最小變更→行為回歸→獨立審查→另版效果驗證」。沒有必要變更時可直接保留現行版本；不將候選清單變成無止境的完成條件。

## 10. 實際入口、驗證與交付管理

以下現有命令均由 repo root 執行。一般 pytest 必須經隔離 runner；依變更選擇有意義的案例，已有效的證據沿用。

PG 修改後的 scoped offline regression：

```sh
"$(scripts/project_python.sh)" -B tests/run_prompt_boundary_tests.py \
  tests/test_postgres_validation_policy.py tests/test_postgres_validation_launcher.py \
  tests/test_postgres_validation_result.py tests/test_postgres_validation_runtime.py \
  tests/test_workflow_checkpoint_resume.py tests/test_workflow_quality_draft_resume.py \
  tests/test_workflow_quality_draft_cold_imports.py tests/test_repair_dependencies.py \
  tests/test_runtime_paths.py tests/test_settings_env_loading.py \
  tests/test_storage_inventory.py tests/test_report_artifacts.py \
  -q -p no:cacheprovider --tb=short
```

PG live 使用現有入口；先建立安全的唯一父目錄，再傳入尚不存在的子結果目錄：

```sh
pg_followup_parent="$(mktemp -d /tmp/stock-agent-pg-followup.XXXXXX)"
"$(scripts/project_python.sh)" -B scripts/run_postgres_validation.py \
  --result-dir "$pg_followup_parent/result"
```

保留回傳狀態與結果檔，再依 G1 驗收。不得改用整個 repo 當 `docker build .` 的 context；不在主機手工指定正式 DSN 或執行 native 負面案例。

OOS 新增單元測試由上述 runner 逐一明列，並納入既有：

```sh
"$(scripts/project_python.sh)" -B tests/run_prompt_boundary_tests.py \
  tests/test_decision_backtest.py tests/test_mode_decision_backtest.py \
  tests/test_trade_execution_contract.py tests/test_outcome_calibration.py \
  tests/test_import_boundaries.py \
  -q -p no:cacheprovider --tb=short
```

`scripts/run_oos_validation.py --result-dir` 是 F2 擬新增入口，完成前不能宣稱可執行；容器端合成 end-to-end 與一般單元測試分開記錄。

每個階段交付至少包含：

- [ ] 變更與驗收所對應的 commit／dirty、manifest／input hash；程式修正、工具驗收、正式載入、資料產製與效果各自狀態。
- [ ] requirement→案例→實際結果對照；passed／failed／skip／尚未執行，不重複加總同一案例。
- [ ] 產物／Job／case 的可追溯清單，保留失敗與未知原因；新舊結果只有同資料、同抽樣、同口徑時才比較。
- [ ] 範圍內完整 diff 與必要 review；`.env`、DB、歷史資料、秘密與他人修改不進 scoped commit。
- [ ] 風險、停止／回復方式與首個未完成步驟；原 PG／OOS 文件記錄詳細證據，本文件僅更新總關卡狀態。

本計畫已完成 PG／OOS 與可信度交付的獨立交叉審查，結果 Approved；審查建議的精確 admission enum 與第一批原始價格政策已納入。文件審查不等於上述工作已實作或通過測試。

本次計畫的下一個可執行步驟是 **F2.1：建立 OOS 隔離 profile 與不可變研究 store**。F2 仍須逐項實作與驗證；本次 PG 交付不會啟動模型生成、正式發布或研究收樣。
