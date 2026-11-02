# 保留待辦的正式部署窗口

`scripts/paused_runtime_deploy.py` 使用現有 RQ 的 `rq:suspended` 機制，只阻止領取新任務。執行中的工作先自然完成，待辦、排程重試、結果與 checkpoint 保留。這不啟用停用中的 canary 或 `--maintenance-arm`。

部署前先以 `tests/run_prompt_boundary_tests.py --isolated-rq` 演練：獨立 Redis 僅有測試沙盒 Unix socket、TCP 禁用。已測試工作完成、到期重試移入待辦、暫停跨重啟、恢復後僅執行一次；一般測試預設仍禁止所有 socket。

## 維護計畫

外接 `stock-agent-archives` 中的單次 plan 必須綁定已推送的 commit、明確的專案 queue 名稱、全部已覆核 executor/helper SHA-256，以及完整保全結果檔。工具先驗證 Redis 使用本專案的持久目錄、獨立程序與唯一 canonical worker；遇既有暫停或範圍不明就停止。

```bash
scripts/project_exec.sh "$(scripts/project_python.sh)" scripts/paused_runtime_deploy.py --plan /Volumes/.../plan.json
scripts/project_exec.sh "$(scripts/project_python.sh)" scripts/paused_runtime_deploy.py --plan /Volumes/.../plan.json --execute
```

預設只檢查計畫。執行時持有共用部署 flock，在設定暫停前保存 intent；暫停使用獨有 token、沒有 TTL，不會在保全或切換未完成時自行恢復。

完整保全必須核對報告、原件、checkpoint、任務、來源快取／冷卻、排程與秘密／無關檔案，以及實際載入版本、設定、套件與服務健康。SQL 執行中工作與 RQ started work 必須清空，來源寫入與 scheduler claim 仍沿用既有資格檢查。

## 到期重試的合法移動

RQ scheduler 在 worker 暫停時仍可將到期項目從 scheduled 移到同一 queue。`deployment_rq_pause.compare` 只接受這種有完整前後證據的移動：同一 job ID、相同 payload/meta/retry budget/origin、UTC enqueue 時間受 server TIME 與原 ETA 約束，原待辦順序保留，沒有新建／遺失 job 或新執行結果。其他差異拒收，不以「佇列數相同」取代內容保全，也不反序列化 job pickle。

待辦不必為零。這個受控暫停契約取代原先只能依賴自然空檔的 RQ 時間門檻；來源 claim、品質與其餘保全要求保持。

## 失敗與復原

任何完整性、身份、版本或健康檢查失敗都保留原暫停，不自動 `resume`、不刪任務、不改重試時間、不重送不明的服務啟動。保留 intent、單次 shutdown/start 收據與原始失敗結果。

原控制程序已確定退出後，覆核同一 case 的階段與 token，使用已綁定且不會重複 shutdown/start 的恢復 executor：

```bash
scripts/project_exec.sh "$(scripts/project_python.sh)" scripts/paused_runtime_deploy.py --plan /Volumes/.../reviewed-recovery-plan.json --execute --recover-paused
```

恢復需同一 Redis run ID／PID、同一 commit 與原有 token，仍取得共用 flock；不接管其他人的暫停。新讀回的完整保全、RQ 保全、正式版本與健康全部通過後，才以 compare-and-delete 移除自己的 token。恢復接單會讓原本的正式任務繼續，並不新增受控模型請求或重設累計計數。
