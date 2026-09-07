# PostgreSQL 隔離驗證交付紀錄

日期：2026-09-07（檔名沿用核准計畫日期）。本紀錄補記本批首次完整 live
PostgreSQL 驗收；OOS 與正式 PostgreSQL 切換仍不在本批範圍。

## Scope 與 revision

- 工作樹：`/Volumes/X10 Pro Mac/stock-agent`
- branch：`codex/analysis-credibility-spec`
- 實作交付基線：`9bbeaa83`（`test: require complete isolated PostgreSQL evidence`）
- 本批整合 commit：`test: complete isolated postgres live validation`（以目前
  `HEAD` 為準）；文件提交後以 `git status --short --branch` 重新核對。
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

Fresh output：`233 passed, 2 warnings in 8.44s`，exit code 0。警告是既有
`agent_runner.attempt_final_audit_repair`／`finalize_final_audit` deprecated
warnings，沒有 failure。

Supplementary offline contract command：

```sh
"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B \
  tests/run_prompt_boundary_tests.py \
  tests/test_postgres_validation_result.py tests/test_postgres_validation_runtime.py \
  tests/test_workflow_postgres_live.py -q -p no:cacheprovider --tb=short
```

Fresh output：`37 passed, 1 skipped in 0.87s`，exit code 0。skip 來自缺少
live policy 的保護邊界，並非 PostgreSQL 測試通過。

## Live validation evidence（2026-09-07）

使用既有唯一入口與新建結果目錄，完整 live run exit code `0`：

```text
run_id=07888e5d359ff131
derived_image=sha256:9816a7d97b354827d9bc281974a8b90d81b1733d630657256499677cd601ec3a
base_image=sha256:413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650
network=none; socket=unix-local-only; paths=tmpfs-and-container-layer-only
cases=17/17; phases=51/51; collection_errors=0; exit_code=0
versions=python 3.13.5; postgres server_version_num 170011; psycopg 3.3.4;
         libpq 180000; langgraph-checkpoint-postgres 3.1.0; psycopg_impl binary
server_stop_status=stopped; cleanup_status=removed; status=passed
```

首次建置與 live debug 發現並修正的直接問題均已進入本批 diff：白名單 context
原先漏收 `backend/prompts`、Dockerfile 有錯誤 `COPY prompts`、Debian trixie
候選套件已升至可取得的 `3.13.5-2+deb13u4`、Docker 29 的 tmpfs 應以
`HostConfig.Tmpfs` 驗證而非 `Mounts`、cluster 必須以 `UTF8` 建立，以及
bootstrap superuser 必須與測試 owner 分離並在 setup 後 `NOLOGIN`。修正後 PG-00～08
完整通過；PG-07 的真實 `42501` 拒寫與 restore path 也在同一 live run 通過。

## 目前可交付與未交付

已交付：固定 image／binary lock、白名單 build context、network／mount／identity
guard、非 root bootstrap、policy／conninfo guard、structured result registry、
PG-01～08 測試程式、cleanup fail-closed state machine、完整 17-case／51-phase
live registry、native libpq TEST-NET negative case、真實 migration／checkpoint／draft
reopen、42501 拒寫觀測、container stop／remove cleanup，以及本批正式 PG adapter
隔離驗收結論。

尚未交付：OOS 合成研究流程、正式 PostgreSQL runtime 切換、正式報告重建與真實
前瞻效果樣本；這些仍依總計畫 F2～F5 的獨立關卡處理。

明確未變更：`.env`、正式 `.venv` 套件、production SQLite checkpoint adapter、
canonical DB／Redis／output、API／worker 狀態；未 push、merge、restart、rebuild，
未建立正式 PostgreSQL DB／schema，未呼叫 provider，未重建歷史報告。

## 證據解讀

`tests/pg_validation/result.py` 的 result schema 要求固定 17 個 case IDs、每案
setup/call/teardown 全部 passed、無 skip／xfail／collection error，且 runtime
version 可讀。主機只有在精確 container identity 再驗證、結果與 manifest/image
一致、cleanup 成功後才可產生 final `passed`；任何 cleanup failure 是獨立的
`cleanup_failed` non-zero 結果。結果目錄不保存 PG log、data、DSN 或 credentials。

本批已完成 PostgreSQL 隔離 live completion definition；這只證明 adapter／測試
契約與隔離生命週期成立，不外推四種模式樣本外績效，也不代表正式環境已切換；
OOS 另案處理。
