# PostgreSQL 隔離驗證操作手冊

日期：2026-09-07。這份手冊描述本批 PostgreSQL checkpoint／quality draft
驗證工具的操作邊界與證據語意；它不代表 live PostgreSQL 已驗收。

## 目的與明確邊界

測試把 PostgreSQL server、Python runner 與 deterministic fixtures 放在同一個
拋棄式 `linux/arm64` 容器，以容器內 Unix socket 驗證 checkpoint、quality draft、
恢復、依賴失效與拒寫路徑。正式 runtime、正式資料、provider、報告 artifact 與
四模式 OOS 驗證不在本批範圍。

本工具不會：

- 讀取或修改 `.env`、正式 `.venv`、canonical SQLite DB、Redis 或 `backend/output`；
- 切換 production checkpoint backend、建立正式 schema、enqueue 工作、重啟服務；
- push、merge、部署，或把測試容器拿來承接正式 checkpoint。

## 唯一入口與執行分層

只接受一個新建且不存在的結果目錄；不接受外部 DSN、container ID、volume、
Docker flags 或主機 credentials：

```sh
"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B \
  scripts/run_postgres_validation.py \
  --result-dir /tmp/stock-agent-pg-validation-<new-run-id>
```

建置與驗證是兩個不同階段。`tests/pg_validation/Dockerfile` 固定 base image
`postgres:17.11-trixie@sha256:413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650`、
`linux/arm64`、Python 3.13.5 apt pin（目前為 `3.13.5-2+deb13u4`），以及 `psycopg-binary==3.3.4` 的
SHA-256 lock。建置時才會得到 derived image ID；文件不得以 base digest 冒充
derived image identity，也不得在未成功 build 時填入版本或 libpq 資訊。

驗證階段固定 `network=none`，沒有 host bind mount、port publication、Docker
socket、host PID、privileged 或 anonymous volume；server 只監聽容器內 Unix
socket。容器以 `USER 999:999` 執行，管理角色只負責本次 cluster setup／清理，
app role 不是 superuser。local trust 是 disposable cluster 的測試設定，不是
正式認證建議；bootstrap superuser 只用於 setup，建立資料庫後立即降為
`NOLOGIN`；實際 owner endpoint 是另建的 `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`
角色，且 database owner 為該角色。cluster 以 `UTF8` encoding 建立；這避免 PostgreSQL `SQL_ASCII`
將 binary cursor 的文字欄位退化為 `bytes`，使 checkpoint namespace／identity
的語意驗證失真。

## 離線驗證與結果判讀

一般 runner 仍使用 SQLite／socket boundary。完成實作後的 plan-required
offline regression 命令是：

```sh
"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B \
  tests/run_prompt_boundary_tests.py \
  tests/test_postgres_validation_policy.py tests/test_postgres_validation_launcher.py \
  tests/test_workflow_checkpoint_resume.py tests/test_workflow_quality_draft_resume.py \
  tests/test_workflow_quality_draft_cold_imports.py tests/test_repair_dependencies.py \
  tests/test_runtime_paths.py tests/test_settings_env_loading.py \
  tests/test_storage_inventory.py tests/test_report_artifacts.py \
  -q -p no:cacheprovider --tb=short
```

2026-09-07 fresh output：`231 passed, 2 warnings in 8.47s`，exit code 0。
補充 PostgreSQL result/runtime contract 與 live module 的離線收集為
`36 passed, 1 skipped in 0.97s`；該 skip 是沒有
`STOCK_AGENT_PG_VALIDATION_POLICY` 時的 module-level skip，不能計入 live pass。

## Structured result 與 mandatory registry

容器內插件只寫 `stock-agent.pg-validation.result.v1` 的 allowlisted JSON，
上限 1 MiB。它包含：

- run ID、source manifest SHA-256、base／derived image identity；
- Python、PostgreSQL、psycopg、libpq 的實際版本（無法查得就不能驗收）；
- 固定的 PG-00～PG-08 case IDs、setup/call/teardown phases、counts、exit code；
- `network=none`、`socket=unix-local-only`、tmpfs／container-layer path assertion、
  native TEST-NET negative assertion、SQLite checkpoint absent；
- server stop status。

mandatory registry 是 `tests/pg_validation/result.py` 的固定 17 個 node IDs，
不是由當次 collected set 自我生成。17 個案例各須有三個 phase，共 51 個 phase
reports；缺 case、collection error、任何 fail／skip／xfail／xpass、duplicate
phase、逾時或非零 exit 都 fail closed。

容器內 `tests_passed` 仍不等於交付通過。主機 launcher 會以本次 run 的精確
container ID、label、manifest hash 與 image ID 驗證結果，再在 cleanup 成功後把
結果寫成 final `passed`。測試通過但 `docker rm -f` 前的 identity re-check 或
cleanup 失敗，只能寫 `cleanup_failed` 並回傳非零；不得以 `prune`、名稱前綴掃描
或刪除其他資源補救。`skip` 是未驗證，不是通過。

## 限制與安全使用

這是固定 image／平台／依賴的 adapter contract evidence，不外推至所有
PostgreSQL major、正式環境或正式認證配置。Python socket monkeypatch 不是
native libpq sandbox；native negative case 必須留在已 inspect 的 `network=none`
容器內。結果目錄只保存 structured result，不匯出 PG log、`/tmp`、data
directory、DSN、密碼或 provider key。

若沒有合法 live policy，`tests/test_workflow_postgres_live.py` 只能在離線
runner 顯示 skip；若 policy 存在但 driver、image、PG readiness、case registry
或 cleanup 失敗，live CLI 必須 non-zero，不能降級成 fake／SQLite pass。正式
checkpoint 仍由既有 SQLite/runtime 設定負責；本測試不改 production adapter。
