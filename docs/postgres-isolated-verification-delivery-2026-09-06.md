# PostgreSQL 隔離驗證交付紀錄

日期：2026-09-07（檔名沿用核准計畫日期）。本紀錄只記錄可重現的離線證據與
live 準備狀態；**沒有 live PostgreSQL pass 結論**。

## Scope 與 revision

- 工作樹：`/Volumes/X10 Pro Mac/stock-agent`
- branch：`codex/analysis-credibility-spec`
- 實作交付基線：`9bbeaa83`（`test: require complete isolated PostgreSQL evidence`）
- 基線檢查：該次執行前 worktree clean；文件提交後以 `git status --short --branch`
  重新核對。
- OOS：尚未實作、尚未驗證；依核准設計與 PostgreSQL 批次分開。

## 實際離線命令與結果

Plan-required scoped regression：

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

Fresh output：`231 passed, 2 warnings in 8.47s`，exit code 0。警告是既有
`agent_runner.attempt_final_audit_repair`／`finalize_final_audit` deprecated
warnings，沒有 failure。

Supplementary offline contract command：

```sh
"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B \
  tests/run_prompt_boundary_tests.py \
  tests/test_postgres_validation_result.py tests/test_postgres_validation_runtime.py \
  tests/test_workflow_postgres_live.py -q -p no:cacheprovider --tb=short
```

Fresh output：`36 passed, 1 skipped in 0.97s`，exit code 0。skip 來自缺少
live policy 的保護邊界，並非 PostgreSQL 測試通過。

## Live preparation evidence（未執行）

本次沒有執行 live CLI、Docker build 或容器內 native PG case，因為目前環境無法
完成其準備條件；這是 preparation limitation，不是 live test fail 或 pass：

- Docker server 可回報 `29.3.0`，但 pinned base image inspect 回傳 exit 1：
  `No such image: postgres:17.11-trixie@sha256:...`；因此沒有可填的 derived
  image ID。
- host `.venv` import `psycopg` 回報 `ImportError: no pq wrapper available`，
  c／binary wrapper 與 system libpq 都不可用。這只證明 host 不可作 live runner，
  不把它改寫成 image 版本證據。
- 沒有合法 `STOCK_AGENT_PG_VALIDATION_POLICY`，因此沒有 dedicated DB／role、
  manifest runtime hash、Python／PG／psycopg／libpq 實際版本、native TEST-NET
  結果、container inspect、server stop 或 cleanup evidence。

故本紀錄的 live 欄位均標示 unavailable；不填造 image ID、derived digest、
版本、case counts、container ID 或 cleanup status，也不把 offline SQLite／fake
adapter 回歸當成 PG live 證據。

## 目前可交付與未交付

已交付：固定 image／binary lock、白名單 build context、network／mount／identity
guard、非 root bootstrap、policy／conninfo guard、structured result registry、
PG-01～08 測試程式、cleanup fail-closed state machine，以及上述 offline contracts。

尚未交付：從 committed worktree 建 image、完整 17-case live registry 的 51 phase
reports、native libpq TEST-NET negative case、真實 migration／checkpoint／draft
reopen、42501 拒寫觀測、container stop／remove cleanup，以及正式 PG adapter
驗收結論。

明確未變更：`.env`、正式 `.venv` 套件、production SQLite checkpoint adapter、
canonical DB／Redis／output、API／worker 狀態；未 push、merge、restart、rebuild，
未建立正式 PostgreSQL DB／schema，未呼叫 provider，未重建歷史報告。

## 證據解讀

`tests/pg_validation/result.py` 的 result schema 要求固定 17 個 case IDs、每案
setup/call/teardown 全部 passed、無 skip／xfail／collection error，且 runtime
version 可讀。主機只有在精確 container identity 再驗證、結果與 manifest/image
一致、cleanup 成功後才可產生 final `passed`；任何 cleanup failure 是獨立的
`cleanup_failed` non-zero 結果。結果目錄不保存 PG log、data、DSN 或 credentials。

本批仍未完成 PostgreSQL live completion definition，因此四種模式分析優化不能
引用本紀錄作為樣本外績效或正式環境切換證據；OOS 另案處理。
