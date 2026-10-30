# 維護驗證模式

此模式是獨立、暫時的本機驗證 listener，不是正常 API 的唯讀開關，也不是停止全機背景工作的工具。只在另行批准正式檔案部署與服務暫停後使用；測試通過不構成部署授權。

## 明確啟用與行為

正式入口新增一個明確參數：`./start_mac.command --maintenance-verify`。不接受額外參數、拼錯的模式參數或 LAN 設定。省略參數仍走原正常啟動流程，會啟動原有背景工作；不得把省略參數當成安全重載方式。

維護分支在正常 launcher 的 PATH／環境載入、trap、安裝與清理流程前退出到專用入口。只使用本專案既有 `.venv/bin/python` 的 `-I -B` 隔離模式；缺少 Python／Uvicorn 時失敗，不安裝、不建立環境、不讀 `.env`。其他 `PYTHON_BIN` 覆寫會被拒絕。

入口只綁定 `127.0.0.1:8080`；埠占用或重複啟動直接失敗，不查 PID、不發停止訊號、不改埠、不清理既有服務。它不啟動 queue、worker、scheduler、maintenance、Redis 或瀏覽器，沒有正式 API fallback。結束時只釋放自己的 socket，不會自動恢復正常服務。

## 對外介面與判讀

只接受無 query、無 root prefix、raw path 與 decoded path 完全一致的 GET：

| 路徑 | 實際檢查 |
|---|---|
| `/healthz` | 維護 ASGI lifespan 已啟動；永遠明示 `production_ready=false` |
| `/readyz` | 維護 listener 與指定來源檔身分快照可用；明示 `operational_checks_performed=false`，缺檔或不可讀則503 |
| `/api/runtime-identity` | 維護啟動時讀取固定11個來源檔的 SHA256／讀取狀態；明示 `production_runtime_loaded=false` |

其餘 HTTP 路徑、其他方法（包括 HEAD／OPTIONS）、帶 query 或非標準路徑全部直接503；WebSocket拒絕。沒有 static、docs、一般 UI、報告列表、股票快照、daily-dashboard 或績效入口，也不轉交正常 router。

身分資料是 **source_files_at_maintenance_startup**，並非目前 Git HEAD、已載入的正式 API 版本或金融事實核驗。後續請求不再讀檔，因此外部改檔不會悄悄改寫此快照。它只讀 launcher、維護入口、維護 ASGI、法人 V3 四檔、精確查找兩檔及政策兩檔；不讀 reports、DB、`.env`、PID 檔或 Redis。原件 hash、完整性或模式 ready 都不能當成績效或品質 gate 的通過證明。

## 正式使用前必須另外批准／確認

本模式不檢查也不停止既有 API／worker。尤其另一介面的 API 或殘留 worker 可能仍在執行背景工作；「本 listener 不啟動工作」不代表「全機已無工作」。在批准的正式維護窗口，應由原操作者或另獲授權的受控流程確認相關任務已收尾、原 launcher／worker 已停止、8080 可用。既有 PID／程序查核限制不能以此模式繞過。

正常 launcher 的退出可能連帶關閉其自有 Redis，這屬原 launcher 的生命週期，必須包含在另行批准的停機範圍。本維護模式 **完全不需要 Redis**，不會啟動、連線、清空或重設它；也不修改固定76批次的 active 狀態、22:30 規則或品質門檻。

維護期間一般 UI、分析與原背景服務會暫停；不重新生成報告。既有 HTML／Markdown 不會自動取得新呈現。驗收只限核定檔案、維護模式介面及獨立的本地純函式測試，不應開啟既有被拒的工作台或 file:// 預覽。

## 結束、恢復與回復

1. 關閉本次維護入口（例如由啟動者送出 Ctrl+C），只結束它自己的 listener。啟動失敗或中斷也不會轉入正常 launcher。
2. 恢復正常服務須另行批准：無參數的原 launcher 會安裝／核對套件、啟動原 Redis／workers，可能立即取得資料、回測及清理。不得在驗證後自動執行它。
3. 若需撤回此補丁，先停止本模式，再核對當前檔案仍等於凍結版本，僅反向套用維護補丁。它與法人 V3／精確查找是分開的變更；不可撤回它們或還原正式 DB。

## 測試與限制

一般測試使用 `tests/run_prompt_boundary_tests.py`，禁網並隔離 SQLite。ASGI測試直接傳入 scope／lifespan，launcher 使用臨時專案與假 interpreter，socket／Uvicorn server 使用 stub；另以已安裝 Uvicorn 的真實 Config.load 檢查相容性，不開 listener。

涵蓋啟動前／結束後、重複 startup、占用埠、同時第二次啟動、缺依賴、失敗／中斷、錯誤參數／LAN設定、所有非允許入口、固定來源檔讀取界線、禁止寫入／DB／外部socket／subprocess／thread／process／signal，以及正常 launcher 既有回歸。未完成真正 macOS listener／OS信號／瀏覽器驗收、正式服務轉場或任何金融資料核驗；不宣稱這些已通過。
