# Historical error-prevention replay

This tool preserves a case registry and runs current deterministic gates. It does **not** rerun models, repair reports, publish results, or prove that the complete generation pipeline will succeed.

Export explicitly named canonical sources using read-only SQLite connections and `ReportArtifactLocator`. Put the corpus outside the service's storage directories:

```bash
"$(scripts/project_python.sh)" scripts/replay_error_prevention.py export \
  --audit-dir '/path/to/original-audit' \
  --corpus '/path/to/private-corpus' \
  --checkpoint-db '/Volumes/X10 Pro Mac/stock-agent/backend/cache/stock_agent_cache.sqlite3' \
  --operational-db '/Volumes/X10 Pro Mac/stock-agent/backend/cache/operational.sqlite3' \
  --output-root '/Volumes/X10 Pro Mac/stock-agent/backend/output'
```

The export preserves decoded original inputs, structured outputs, streamed candidates and their hashes. Credential/header/environment metadata is removed; anonymous key slots remain. Original checkpoint binary is **not** exported: its hash and read-only database locator are retained. Corpus permissions are `0700` and JSON files `0600`. Missing checkpoints, versions and candidate text remain explicitly unknown.

Run the regression checks with the repository's mandatory isolated runner. Set an optional corpus path to replay all retained cases with SQLite/Redis/provider network access disabled:

```bash
STOCK_ERROR_PREVENTION_CORPUS='/path/to/private-corpus' \
  "$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_error_prevention_replay.py tests/test_error_prevention_mode_c.py -q
```

A standalone offline CLI is also available for an already exported corpus:

```bash
"$(scripts/project_python.sh)" scripts/replay_error_prevention.py replay \
  '/path/to/private-corpus/manifest.json' --result '/path/to/private-corpus/current-replay.json'
```

Replay verifies every payload hash and rejects paths outside the corpus. Results include a source-code file manifest covering backend Python and prompt JSON files. The small repository registry `tests/fixtures/error_prevention_manifest_20260922.json` identifies the 41 failed jobs and 49 warning reports; full financial inputs stay in the private release corpus.

Interpretation:

- `fixed_in_scoped_replay`: the current deterministic checks passed with sufficient retained evidence. This is not generation or publication success.
- `true_error_still_blocked`: a manually reviewed, input-hash-bound candidate defect remains blocked. A gate result alone never creates this classification.
- `true_error_unexpectedly_passed`: a known, input-bound true error escaped the current checks. The CLI exits 2 and regression validation fails; this is never labeled a fix.
- `still_reproduced`: a current finding remains; further review may distinguish valid rejection from parser error.
- `evidence_missing`: input/output is unavailable, corrupted, or original report input binding is unknown. A saved artifact checksum alone does not prove which input generated its conclusions.

The original stored `parsed` and final audit stay in the payload. Job replay uses the current parser on the retained outputs and reports that projection separately. Report replay keeps recorded final-audit warnings visible. A refreshed report without a provable original input is never counted as fixed.

## 固定案例、執行收據與基準比較

此入口借鑑 Promptfoo 的固定案例、VCR.py 的唯讀重播、Langfuse 的執行關聯與 DVC 的內容版本綁定；使用 Python 標準函式庫擴充原入口，沒有新增這些套件或常駐服務。

- 沿用 `workflow_telemetry_attribution`、`analysis_job_provenance` 與正式 operational ledger。這裡的 `run_id` 是一次離線驗證的身分，不冒充報告工作或供應商請求；不另外建立正式追蹤資料庫。
- schema 2 結果包含每次執行與逐案例 attempt ID、開始／結束時間、耗時、manifest／payload／結果 SHA-256，以及前後一致的驗證程式檔案清單。Git commit 只是輔助標記；`validator_sha256` 才綁定本次實際檔案，包含尚未提交的修改。
- 同一案例的任一 deterministic finding 改變都列入差異，即使 classification 沒變。程式版本改變而結果相同時，另列 `validator_changed`。
- 只有相同完整 corpus、輸入雜湊及完整 schema 2 收據可以比較。舊 schema 1 結果保留原位；需要時重新執行產出新檔，不推定舊紀錄已有缺少的證據。
- `replay` CLI 自動隔離環境、封鎖 Python socket 連線與 SQLite 開庫；macOS 的 sandbox 留在外接碟 archive。程式呼叫 `replay_manifest()` 時仍必須使用既有隔離測試入口。
- 結果只能新建，權限 `0600`；不能覆寫原件、基準或先前結果。原始 corpus 不會更新，基準不會自動晉升。收據用於重現與差異檢查，並非簽章或人工品質核准。

先產出候選基準，檢查個別 finding，往後比較同一 corpus：

```bash
scripts/project_exec.sh "$(scripts/project_python.sh)" -B scripts/replay_error_prevention.py replay \
  '/path/to/private-corpus/manifest.json' --result '/path/to/new-baseline-candidate.json'

scripts/project_exec.sh "$(scripts/project_python.sh)" -B scripts/replay_error_prevention.py replay \
  '/path/to/private-corpus/manifest.json' --baseline '/path/to/reviewed-baseline.json' \
  --result '/path/to/new-current-replay.json'
```

macOS 的 corpus、基準及結果都應放在 `/Volumes/X10 Pro Mac/stock-agent-archives` 的具名目錄。執行後查看 `run_receipt`、`case_receipts`、`comparison` 與原有 `results`／`counts`。

| Exit code | 意義 |
| --- | --- |
| `0` | 重播完整，且要求比較時結果相同；不代表模型品質或發布通過 |
| `2` | 已人工確認且綁定輸入的錯誤意外通過原有 gate |
| `3` | 證據缺失、程式在執行期間改變、格式錯誤、基準不可比或輸出檔已存在 |
| `4` | 同一固定 corpus 的 finding 有差異，需檢視原因；不自動認定改善或退步 |

相關回歸：

```bash
scripts/project_exec.sh "$(scripts/project_python.sh)" -B tests/run_prompt_boundary_tests.py \
  tests/test_replay_run_receipts.py tests/test_error_prevention_replay.py \
  tests/test_error_prevention_mode_c.py tests/test_workflow_telemetry_attribution.py \
  tests/test_report_runtime_provenance.py tests/test_mode_moat_missing_values.py -q
```

私有完整 corpus 未提供時，該一項歷史回放保持 skip；合成案例與單元回歸不替代真實報告的人工驗收。
