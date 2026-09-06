# PostgreSQL checkpoint 隔離驗證設計

日期：2026-09-06。基準程式：`fec17737`。

狀態：**使用者已於 2026-09-06 核准本書面規格；[實作計畫](../plans/2026-09-06-postgres-isolated-verification-implementation-plan.md) 已建立，尚未開始實作或 live PostgreSQL 驗證。**

## 1. 目的與批次邊界

補上真實 PostgreSQL 的 checkpoint／quality draft 恢復證據。第一批四模式內容可信度修正與大量 SQLite／fixture 回歸，不代替這項驗收。

本批先獨立完成；OOS 另依 [OOS 隔離驗證設計](2026-09-06-oos-isolated-verification-design.md) 執行，兩者不共用正式資料庫或完成判定。

本批允許在實作核准後新增測試、測試環境建置與隔離啟動工具、測試依賴鎖定及操作文件；真實測試若暴露 checkpoint 缺陷，只修直接相關邏輯並補回歸。不擴張到 storage 全面遷移。

不包含：push、merge、切換正式 checkpoint backend、修改正式 `.env`／`.venv`、重啟 API／worker／Redis、呼叫供應商、產生正式分析任務、重建或改寫歷史報告。

## 2. 現有入口與缺口

- `backend/workflow_checkpoints.py` 的 `open_postgres_checkpointer()` 已存在，但開啟時會呼叫 `setup()`，不是唯讀操作。
- `backend/workflow_quality_drafts.py` 在 checkpointer 的獨立 namespace 保存尚未通過品質檢查的草稿；恢復草稿不能直接視為成功節點。
- `tests/test_workflow_checkpoint_resume.py` 的 PG wiring 使用 fake saver；`tests/test_workflow_quality_draft_resume.py` 的主要持久化情境目前以 SQLite 驗證。
- 前次唯讀盤點發現 `langgraph-checkpoint-postgres==3.1.0`、`psycopg==3.3.4` 的安裝記錄，但實際 import 因 binary／本機 libpq 缺失而失敗。實作前重新檢查，不以 metadata 當作可用證據。
- `tests/run_prompt_boundary_tests.py` 攔截 Python socket 與 SQLite 路徑，不能據此推論 native libpq 被封鎖。
- `backend/settings/env.py` 會讀取 `backend/.env`，並回填空值環境變數；清空 DSN 字串不是有效隔離。

2026-09-06 的 runtime doctor 仍指向 `backend/cache/stock_agent_cache.sqlite3`、`backend/cache/operational.sqlite3` 與 `backend/output`。這些正式位置不進入測試容器。

## 3. 選定架構與替代方案

選定：**PostgreSQL 與 Python 測試 runner 在同一個拋棄式容器，驗證階段使用 `--network none`，只透過容器內 Unix socket 連線。** Docker 此模式只建立 loopback 介面；搭配不掛載主機資料與 socket，作為本批 native 連線的主要隔離邊界。[Docker 官方說明](https://docs.docker.com/engine/network/drivers/none/)

替代方案是主機安裝 libpq／PostgreSQL 並指定專用 DB；啟動路徑較短，但需要處理主機既有 DSN、角色、port 與清理。因此本批不採用。也不接受使用者提供任意外部測試 DSN 的模式。

元件責任：

| 元件 | 單一責任 | 不得做的事 |
| --- | --- | --- |
| 主機啟動工具 | 檢查 Docker、準備白名單程式副本、建立本次資源、取回結果及精確清理 | 載入正式 config、連正式 DB、傳遞主機憑證 |
| 測試 image | 固定 Python／PG／driver 及測試依賴，保存建置身分 | 複製 `.env`、cache、output、`.git`、主機 `.venv` 或使用整個 repo 作未篩選 context |
| 容器入口 | 建立空 PG cluster、socket、專用角色／DB，呼叫既有隔離 runner | 開 TCP listener、公開 port、掛 Docker socket、使用 privileged／host network |
| PG 邊界 guard | 在 driver 呼叫前核對本次 endpoint 身分與允許參數 | 回退到環境、service file、多 host 或其他 socket |
| Live 測試 | 用真 saver 驗證保存與恢復；模型及發布出口用測試替身 | 使用 fake PG 當 live 結果、呼叫供應商或正式 renderer 儲存 |
| 驗證紀錄 | 保存版本、測試結果、隔離證據與清理結果 | 保存 DSN、密碼、正式資料或宣稱部署完成 |

建置依賴可以在獨立準備階段下載；**測試執行階段不得有外網**。下載僅使用公開套件／官方映像來源，不帶 repo 憑證或正式資料。image 建置 context 使用逐檔白名單，拒絕 symlink、非一般檔及越界路徑。

## 4. 環境與連線不變量

1. 測試使用同一個明確解析到 image ID／digest 的映像，不用浮動 tag 作驗收身分。以 Python 3.13、PostgreSQL 17、`langgraph-checkpoint-postgres==3.1.0`、`psycopg[binary]==3.3.4` 為相容基線；鎖定 PG 17 的單一 patch 版本及其餘必要依賴後才執行。實作計畫需記錄精確解析版本與 digest，不靜默升級以求通過，也不把此測試外推到其他 PG major。
2. binary 安裝自帶所需 client libraries，因此只安裝在測試 image，正式 `.venv` 不補套件；若指定版本不支援目標平台，回報準備失敗，不降級成 fake 測試。[Psycopg 官方安裝說明](https://www.psycopg.org/psycopg3/docs/basic/install.html)
3. 不發布任何 host port；PG 設 `listen_addresses=''`，socket 與 cluster 只存在本次容器內。使用唯一 run ID 與資源標籤，DB、role、socket 位置都由入口產生，不能由任意 DSN 覆寫。
4. 容器不使用主機 bind mount、Docker socket、host PID namespace 或 privileged。測試資料、PG data、SQLite 與輸出放容器內臨時位置；需要的暫存 volume 必須由本次建立並記錄精確 ID，不使用既有 volume。
5. PG server 與 runner 用非 root 身分執行。初始化／schema owner 與應用測試角色分開；應用角色不是 superuser，也不是受拒寫測試資料表的 owner。憑證只留容器內受限檔案，不放命令列、公開日誌或主機環境。
6. runner 啟動前排除正式 `.env` 與所有主機 `PG*`／DSN 來源；明確設測試 `CACHE_DIR`、`CACHE_DB_PATH`、`OPERATIONAL_DB_PATH`、`TASK_DB_PATH`、`LANGGRAPH_CHECKPOINT_PATH`、`OUTPUT_DIR`、memory cache 及 checkpoint backend。不能以空值阻止 `.env` 回填。libpq 可由環境變數取得連線預設，故測試不能依賴省略參數。[PostgreSQL 官方環境參數說明](https://www.postgresql.org/docs/current/libpq-envars.html)
7. 接受的 connection identity 是本次產生的唯一 Unix socket directory、port、DB 與應用角色；內部固定的管理角色僅供 setup／拒寫故障注入。拒絕 hostaddr、TCP host、其他 socket、URI、重複鍵、多 host、service／servicefile、隱含預設及不在白名單的參數。
8. 一般隔離 runner 預設不開放 PostgreSQL；live opt-in 只在上述專用容器入口成立。針對 psycopg 同步、非同步及專案使用的 aliases 驗證 guard。native PQ 直接入口的安全性由容器網路及檔案隔離承擔，**不宣稱 Python monkeypatch 是完整 native sandbox**。
9. 連線 timeout 為 5 秒、PG readiness 最多 60 秒、單案例最多 60 秒、整套 live 測試最多 10 分鐘；限額 2 CPU／2 GiB memory／256 PIDs。逾時、權限不足或資源不足明確失敗，不擴大到主機服務或無限制重試。

## 5. Live 驗收契約

所有 live 案例從容器中的 `tests/run_prompt_boundary_tests.py` 進入；SQLite 與 cache guard 保留。只允許本次 PG socket，模型／provider／發布動作由 deterministic fixture 或 spy 代替。

| ID | 情境 | 必須觀察到的結果 |
| --- | --- | --- |
| PG-01 | 空 DB setup，再關閉並開啟 | 真實 migration／建表成功，重開 setup 冪等 |
| PG-02 | 保存原稿及中間修復稿，關閉 saver 後建立新 saver | 正文、structured output、manifest、RAG／digest 與上游 fingerprint 完整一致；使用 saver 的版本語意確認遞增，不能假設版本是整數 |
| PG-03 | deferred 後恢復，再通過 gate | 原稿不再生成，已完成節點不重跑，未驗證稿重新檢查，測試發布出口只呼叫一次 |
| PG-04 | 取消執行後，以新 saver／新 graph instance 恢復 | 取消不成成功；已持久化草稿與完成節點可恢復，沒有半套採用狀態 |
| PG-05 | 兩 agent／兩 thread、平行 sibling 一個完成一個 deferred | namespace 與內容互不污染；completed sibling 保留，另一份草稿可恢復 |
| PG-06 | 同 thread／agent 的 draft 以相同／不同上游 fingerprint 載入；既有依賴失效路徑另驗證 | 不變恢復原 evidence；改變拒絕舊稿；需要成功結果失效時使用既有 dependency invalidation 路徑，不以更換 `initial_state` 代替 |
| PG-07 | 可讀 graph／草稿基線已建立，在原稿／中間修復稿實際 `aput` 前撤銷非 owner 應用角色的寫入權限 | 草稿 namespace 的真 PG 拒寫，SQLSTATE `42501`；未進入該保存步驟後的 gate／採用／發布；舊稿仍可讀且未被替換，graph 保持未完成 |
| PG-08 | 相同 identity 與持久化輸入的已完成 graph 再次開啟 | 完成狀態正確返回，不重跑模型節點或重複發布 |

PG-06 沿用第一批的 `analysis_dependencies.py` 與 repair transaction 契約，從既有上游更正／失效轉換驗證，不新增「同 thread 傳不同 initial_state 即覆寫已完成分析」行為。`execute_persistent_graph()` 在已有 snapshot 時採持久化狀態；只改傳入 initial_state 不是有效失效測試。

PG-07 使用 fixture barrier／spy 辨識 `checkpoint_unvalidated_draft()` 的草稿 namespace 寫入時點，但仍呼叫真 saver。原稿及中間修復稿保存分開覆蓋；只在 setup 或 graph 初始 checkpoint 失敗不算通過。不得以 monkeypatch `put` 丟例外代替這項 live 證據。角色、schema 與權限操作只限本次專用 cluster；恢復或清理由測試管理角色完成。

## 6. 隔離與失敗處理驗收

- 建立容器前驗證白名單來源沒有 `.env`、正式 artifact／DB、憑證或 symlink。來源驗證失敗則不啟動測試。
- 執行前 inspect 精確容器 ID：network=none、沒有 port binding／主機 bind mount／Docker socket、沒有 privileged 或 host namespaces。任一不符先停止本次測試，不嘗試 DB 連線。
- 在隔離容器內用測試建立的 sink／不可達位址分開驗證 Python 網路 guard、conninfo wrapper 的呼叫前拒絕，以及 native PQ 的容器外 endpoint 不可達／timeout；network=none 仍有 loopback，不宣稱阻止一切容器內 native 通訊。不以正式 DB／API／provider 作負面測試目標。
- 測試 `.env` 回填、`PGSERVICE`／`PGHOSTADDR`／多 host／其他 socket 等注入反例；確認呼叫 native driver 之前就拒絕，且錯誤不洩漏完整 conninfo。
- 明確 opt-in live suite 缺 driver、PG 不可用、setup 失敗或未執行案例時必須 nonzero；不得以 skip 形成「live 通過」。一般 offline suite 可明確顯示 live 未啟用，但不得把它納入 live 成功數。
- 按精確記錄的 container／volume ID 清理本次資源；拒絕名稱前綴掃描後批量刪除、`prune` 或動到既有容器。成功、失敗與中斷都走同一清理流程。
- 清理失敗單獨記為 `cleanup_failed`，列出本次未移除資源的非敏感 ID，整次交付不算完整。測試專用 image 是否保留作快取須在紀錄明示；不得清理共用 image/cache。

## 7. 回歸與交付證據

實作採失敗案例先行，至少執行：

- 新隔離啟動工具／白名單／conninfo guard 的離線單元測試。
- `test_workflow_checkpoint_resume.py`、`test_workflow_quality_draft_resume.py`、`test_workflow_quality_draft_cold_imports.py`，以及新增 PG live 案例。
- `test_runtime_paths.py`、`test_settings_env_loading.py`、`test_storage_inventory.py`、`test_report_artifacts.py`：符合維護指南的 runtime/storage 回歸。
- 若觸及草稿或修復採用邏輯，再納入第一批依賴版本、repair transaction 與 fail-closed 回歸，不以 PG 測試取代 SQLite 相容性。

交付紀錄保存：測試程式 commit／dirty 狀態與輸入清單 hash、image ID／digest、Python／PG／saver／psycopg／libpq 實際版本、案例 ID 對照與 passed/failed/skipped、隔離設定檢查、測試資料根目錄識別及清理結果。只有本次真實測試輸出可作本批通過證據。

**完成定義：** PG-01～08、隔離反例及相關回歸全部符合，且本次臨時服務／資料已清理。這只表示該固定環境的 PostgreSQL adapter 契約通過，不表示正式環境已安裝驅動、已切換 PG、所有 PG 版本皆支援，或四模式已有 OOS 績效。

## 8. 審核狀態

- [x] 現況與正式路徑已盤點。
- [x] 容器與主機安裝方案已比較。
- [x] 使用者已同意容器隔離及不修改正式 runtime 的界線。
- [x] 規格已自我檢核範圍、錯誤處理、隔離與驗收語意。
- [x] 使用者檢視並核准本書面規格（2026-09-06）。
- [x] 建立獨立實作計畫。
- [ ] 執行實作計畫。
- [ ] 真實 PostgreSQL 驗收與清理完成。
