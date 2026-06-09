# Wall Street AI Stock Research System

這是一套本機版股票研究報告產生系統。使用者輸入股票代號後，後端會抓取公開財務資料，交由多個分析 Agent 依序完成商業模式、財務、護城河、估值、成長潛力、多空辯論與最終投資建議，最後輸出 HTML / Markdown 報告。

> 注意：本專案產生的是研究輔助內容，不是投資建議。所有輸出都應再經人工查核。

## 功能

- FastAPI 後端與簡易前端介面
- SSE 即時推播分析進度
- 支援台股代號，例如 `2330`、`2330.TW`
- 自動切換 `.TW` / `.TWO` 查詢
- 多 Agent 串接分析流程
- 產生 HTML 與 Markdown 報告
- 前端分成「分析」與「報告與維運」頁籤；歷史報告、預覽、比較留在分析頁，API 額度、watchlist、來源健康與本機維護集中在維運頁並於首次開啟時載入
- 歷史報告支援資料可信度、決策追蹤、版本篩選、報告比較與相容性提示
- 報告預覽可只刷新資料快照，也可排隊重跑最終投資建議、Mode B 或完整報告
- 歷史 API 回傳 `decision_freshness`，明確區分「資料快照已更新」與「投資結論是否已依新資料重跑」
- 內建報告刪除 API，會同步刪除 `.html`、`.md` 與資料快照
- Agent 3 / 4 / 7 使用 JSON 結構化輸出優先解析，正則表達式僅保留為備援
- 財務資料使用本地 SQLite 持久化快取，預設 24 小時
- yfinance 欄位缺漏時會用 FMP（需 API key）或可追溯的衍生補值補上市場欄位、TTM 營收或 FCF，並在 prompt 中揭露限制
- 歷史報告會自動清理孤立 Markdown，並刪除超過保留天數的舊報告
- 長任務透過 SQLite job/event store 與任務佇列抽象執行，可用本地 worker 或切換 RQ/Redis
- API 額度儀表板使用 `api_usage_events` ledger 統計 Gemini provider request、Google Custom Search 與 FMP 本機觀測用量
- Watchlist 可設定盤前/盤後批次分析，儲存在 SQLite，排程執行會先原子認領 due slot 並保留舊 JSON 一次性匯入相容
- 財務抓取與 Gemini 分析管線提供 async 版本，API 生成報告時走新版 `google-genai` 非同步 client
- 針對常見財務錯誤加入品質檢查，例如 DuPont、DCF / P/E、WACC、FCF 與公司身分一致性

## 專案結構

```text
stock-agent/
├── backend/
│   ├── api.py              # FastAPI 服務與報告 API
│   ├── agent_runner.py     # 多 Agent prompt、模型呼叫、品質檢查
│   ├── prompt_loader.py    # 從 prompts/ 載入 prompt 設定
│   ├── cache_store.py      # SQLite JSON 快取
│   ├── job_store.py        # SQLite job / SSE event store
│   ├── api_usage_store.py  # API 用量 ledger
│   ├── watchlist_service.py # Watchlist SQLite 儲存與批次排程 helper
│   ├── watchlist_claim_store.py # Watchlist 排程 due slot 原子認領
│   ├── analysis_jobs.py    # 可匯入的分析任務入口，本地/RQ worker 共用
│   ├── report_rerun_service.py # 報告局部/完整重跑 orchestration
│   ├── task_queue.py       # 本地長任務佇列抽象，可切換 RQ
│   ├── config.py           # 模型與環境變數設定
│   ├── financial_data.py   # 財務資料抓取與 prompt 資料摘要
│   ├── report_gen.py       # HTML / Markdown 報告產生器
│   ├── prompts/            # Agent system / analysis prompt JSON
│   ├── templates/          # Jinja2 HTML 報告模板
│   ├── requirements.txt    # Python 套件
│   ├── static/             # 前端頁面
│   └── output/             # 產生的報告，已被 Git 忽略
├── main.py                 # CLI 入口
├── docs/
│   ├── architecture.md     # 系統邊界與資料流程
│   ├── operator-guide.md   # 操作者日常流程與維護指南
│   └── api.md              # API 與 mutation token 範例
├── scripts/
│   ├── demo_report.sh      # 列出目前本機報告摘要
│   └── secret_scan.py      # 離線 secret 掃描
├── start_mac.command       # macOS 一鍵啟動腳本
└── README.md
```

## 文件入口

- [docs/architecture.md](docs/architecture.md)：系統資料流、服務邊界、`decision_freshness` 與 mutation token 設計。
- [docs/operator-guide.md](docs/operator-guide.md)：操作者日常分析、報告重跑、維護與安全注意事項。
- [docs/api.md](docs/api.md)：常用 API、修改端點 token header、維護 dry-run 範例。
- [scripts/demo_report.sh](scripts/demo_report.sh)：不啟動伺服器也能列出本機報告摘要。

## 安全設定

API key 不會也不應該提交到 Git。請使用本機環境變數或 `backend/.env`。

建立本機設定檔：

```bash
cp backend/.env.example backend/.env
```

編輯 `backend/.env`：

```bash
GEMINI_API_KEYS=your_key_1,your_key_2
```

`replace_with_key_1`、`your_key_1` 這類範例字串會被系統忽略。設定或修改 `backend/.env` 後，請重新啟動 `start_mac.command` 或 uvicorn。

也可以直接用環境變數：

```bash
export GEMINI_API_KEYS="your_key_1,your_key_2"
```

修改端點會要求 `X-Mutation-Token`。若沒有設定 `MUTATION_API_TOKEN`，後端會在啟動時產生同源 runtime token，前端會自動透過 `/api/client-config` 取得；自動化腳本可參考 [docs/api.md](docs/api.md)。

提交前可執行離線 secret 掃描：

```bash
"$(scripts/project_python.sh)" scripts/secret_scan.py
```

支援的 key 名稱：

- `GEMINI_API_KEYS`
- `GOOGLE_API_KEYS`
- `GOOGLE_API_KEY_1` 到 `GOOGLE_API_KEY_10`
- `GEMINI_API_KEY_1` 到 `GEMINI_API_KEY_10`
- `GOOGLE_SEARCH_API_KEY`、`GOOGLE_CSE_ID`：可選，用於近期新聞與催化劑搜尋
- `FMP_API_KEY`：可選，用於 yfinance 缺漏時補市場欄位與新聞

可選設定：

- 模型路由預設由 `backend/model_routes.json` 管理，也可用 `MODEL_ROUTES_FILE`、`DEFAULT_ANALYSIS_MODEL`、`DEFAULT_DECISION_MODEL`、`AGENT_MODELS_JSON` 或 `AGENT_MODEL_1` 到 `AGENT_MODEL_7` 覆寫
- `OUTPUT_DIR`：報告輸出目錄，預設 `backend/output/`
- `CACHE_DB_PATH`：SQLite 快取檔位置，預設 `backend/cache/stock_agent_cache.sqlite3`
- `FINANCIAL_DATA_CACHE_SECONDS`：財務資料快取秒數，預設 `86400`
- `REPORT_RETENTION_DAYS`：舊報告保留天數，預設 `30`
- `REPORT_CLEANUP_INTERVAL_SECONDS`：背景清理週期秒數，預設 `86400`
- `ANALYSIS_WORKER_COUNT`：本地分析 worker 數，預設 `2`
- `TASK_QUEUE_BACKEND`：任務佇列後端，`local` 或 `rq`，預設 `local`
- `REDIS_URL`：RQ 模式使用的 Redis 連線，預設 `redis://localhost:6379/0`
- `TASK_QUEUE_NAME`：RQ queue 名稱，預設 `stock-analysis`
- `TASK_DB_PATH`：任務與 SSE event SQLite 檔位置，預設 `backend/cache/analysis_jobs.sqlite3`
- `API_USAGE_DB_PATH`：API 用量 ledger SQLite 檔位置，預設跟隨 `TASK_DB_PATH`
- `WATCHLIST_PATH`：舊版 watchlist JSON 位置；若存在會一次性匯入 SQLite，預設 `backend/cache/watchlist.json`
- `WATCHLIST_DB_PATH`：watchlist SQLite 檔位置，預設為 `WATCHLIST_PATH` 同名 `.sqlite3`
- `ANALYSIS_JOB_STALE_SECONDS`：queued/running 任務超過此秒數未更新時不再被視為活躍，預設 `21600`
- `ANALYSIS_JOB_HISTORY_RETENTION_DAYS`：已完成/失敗/取消任務紀錄保留天數，預設 `30`
- `LLM_AGENT_CALL_TIMEOUT_SECONDS`：單次 Agent LLM 呼叫 timeout 秒數，預設 `120`；會傳入 Google GenAI `HttpOptions.timeout`，非同步路徑另有外層 `asyncio.wait_for` 保護，設為 `0` 可關閉
- `PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS`：有備援模型時 primary model 單次呼叫 timeout 秒數，預設 `360`，讓 Gemma 等大型 primary 模型有較完整的產出時間
- `FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS`：備援模型單次呼叫 timeout 秒數，預設沿用 `LLM_AGENT_CALL_TIMEOUT_SECONDS`
- `LLM_SERVER_ERROR_MAX_ATTEMPTS`：模型服務 500/503/忙碌時的持續嘗試次數，預設 `6`
- `LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS`：模型服務 5xx 重試 backoff 單次等待上限，預設 `45`
- 429 quota / rate-limit 會至少輪完所有 API key 才判定該模型不可用；任務事件只記錄 `key_slot/key_count`，不保存 key 明文
- `FMP_BASE_URL`：FMP API base URL，預設 `https://financialmodelingprep.com/stable`

不要提交這些內容：

- `backend/.env`
- `backend/output/`
- `backend/cache/`
- API key、token、私鑰、憑證檔

## 安裝

建議使用 Python 3.13；macOS 建議使用 Homebrew / python.org Python，避免 Apple Command Line Tools Python 3.9 與 LibreSSL 觸發 Google 套件與 urllib3 相容性警告。專案根目錄提供 `.python-version`，部署前可用 `.venv/bin/python scripts/check_runtime.py --strict` 擋掉過舊 runtime。本機已驗證 Python 3.13 + OpenSSL 可消除這些 warning。Gemini 呼叫使用新版 `google-genai` SDK，不再使用已停止維護的 `google-generativeai`。

```bash
scripts/bootstrap_venv.sh
```

如果你的 `python3` 仍是 macOS 系統 Python，也可以手動指定 Homebrew Python 3.13：

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

CI 與 smoke scripts 會優先使用 `PYTHON_BIN`，其次使用專案 `.venv/bin/python`：

```bash
scripts/ci_gate.sh
```

前端/報告圖表視覺回歸可用 Playwright 跑；直接執行時會要求瀏覽器可用：

```bash
scripts/setup_visual_regression.sh
scripts/visual_regression.sh
```

CI 可用 `RUN_VISUAL_REGRESSION=1 scripts/ci_gate.sh` 一併執行；一般 `pytest` 仍會在 Playwright 不可用時 skip。

## 維護工具

本機維護命令請透過 wrapper 執行，腳本會自動套用專案 Python 與 `PYTHONPATH`：

```bash
scripts/maintenance.sh storage-summary
scripts/maintenance.sh cleanup-provider-sla
scripts/maintenance.sh cleanup-report-index --write
scripts/maintenance.sh cleanup-analysis-history --write
scripts/maintenance.sh verify-snapshots --write
```

`cleanup-report-index` 預設只會 dry-run；加上 `--write` 才會刪除已不存在輸出目錄的報告索引列。
`cleanup-analysis-history` 預設也只會 dry-run；加上 `--write` 才會刪除過舊且已結束的任務與孤兒事件，queued/running 任務會保留。

## 啟動方式

### macOS 一鍵啟動

在 Finder 內雙擊：

```text
start_mac.command
```

腳本會優先使用專案 `.venv`；若尚未建立，會優先用 `/opt/homebrew/bin/python3.13` 建立虛擬環境並安裝 `backend/requirements.txt`，再啟動後端並開啟：

```text
http://127.0.0.1:8080
```

### 手動啟動

```bash
cd backend
python3 -m uvicorn api:app --host 127.0.0.1 --port 8080
```

然後打開：

```text
http://127.0.0.1:8080
```

## 使用方式

1. 開啟首頁，預設停在「分析」頁籤。
2. 輸入股票代號，例如 `2330`、`2059`、`6806.TW`。
3. 按下分析。
4. 等待 Agent 依序完成。
5. 報告完成後會出現在同一頁的歷史清單，可直接預覽、下載、比較或重跑。

分析時間會受模型回應速度與 API 額度影響。部分個股可能需要 10 分鐘以上。

日常操作建議：

- 「分析」頁籤：新分析、查找歷史報告、篩選 Mode A/B、查看決策追蹤、刷新資料快照、重跑報告與比較報告。
- 「報告與維運」頁籤：查看 API 額度、本機 watchlist、來源健康、任務狀態與清理工具；首次打開頁籤才會載入這些維運資料。
- 「資料快照已刷新，但 HTML/Markdown 分析本文未重新執行」代表只更新了 `.data.json` 的最新股價/來源/可信度，原本報告正文和投資結論還是舊模型在原生成時間做出的判斷；若要讓文字與結論一起更新，請使用重跑功能。

## API

取得歷史報告：

```bash
curl http://127.0.0.1:8080/api/reports
curl "http://127.0.0.1:8080/api/reports?q=2308&pipeline=v2&include_versions=true"
```

分析股票：

```bash
curl -N http://127.0.0.1:8080/api/analyze/2330
```

開啟報告：

```text
http://127.0.0.1:8080/api/report/<filename>
```

比較兩份報告：

```bash
curl "http://127.0.0.1:8080/api/reports/compare?left=<old.html>&right=<new.html>"
```

回傳會包含 `compatibility`，用來提示是否同股票、同 pipeline，以及左右時間順序是否合理。

修改端點需先取得 mutation token：

```bash
TOKEN="$(curl -fsS http://127.0.0.1:8080/api/client-config | python -c 'import json,sys; print(json.load(sys.stdin)["mutation_token"])')"
```

刷新資料快照：

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/report/<filename>/refresh/data
```

重跑報告：

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/report/<filename>/rerun?scope=final_recommendation"
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/report/<filename>/rerun?scope=mode_b"
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/report/<filename>/rerun?scope=full"
```

`full` 會先強制刷新資料，再用原報告 pipeline 完整重跑；`final_recommendation` 只重跑最終投資建議 Agent。

刪除報告：

```bash
curl -X DELETE -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/reports/<filename>
```

歷史報告預覽支援資料快照刷新與局部重跑；局部重跑會建立 background job 並透過 SSE 回放進度，可用 `/api/report/<filename>/rerun/cancel?job_id=<job_id>` 要求取消。

觀測與維護：

```bash
curl http://127.0.0.1:8080/api/observability/api-quotas
curl http://127.0.0.1:8080/api/observability/provider-sla
curl -H "X-Mutation-Token: $TOKEN" http://127.0.0.1:8080/api/maintenance/storage-summary
curl http://127.0.0.1:8080/api/watchlist
```

## 輸出檔案

報告預設輸出到：

```text
backend/output/
```

每份報告會產生：

- `.html`
- `.md`
- `.data.json`

`backend/output/` 已在 `.gitignore` 中，不會被提交。

`.data.json` 是資料快照，包含來源審計、資料可信度、決策追蹤基準與重跑 context。只刷新資料快照時，HTML / Markdown 正文不會自動改寫。

`backend/cache/` 也已被 Git 忽略。財務資料快取預設保存 24 小時，可透過 `FINANCIAL_DATA_CACHE_SECONDS` 調整。歷史報告預設保留 30 天，可透過 `REPORT_RETENTION_DAYS` 調整；前端刪除 HTML 報告時，後端會同步刪除同名 Markdown 與資料快照。

## 任務佇列

預設使用本地 worker：

```bash
TASK_QUEUE_BACKEND=local
ANALYSIS_WORKER_COUNT=2
```

若要切換為 RQ / Redis，先啟動 Redis，並在 `backend/.env` 設定：

```bash
TASK_QUEUE_BACKEND=rq
REDIS_URL=redis://localhost:6379/0
TASK_QUEUE_NAME=stock-analysis
```

API 會把任務送進 RQ。另開 worker：

```bash
cd backend
rq worker stock-analysis --url redis://localhost:6379/0
```

任務狀態、SSE 事件與預設 API 用量 ledger 會寫入 `TASK_DB_PATH` 指定的 SQLite 檔，所以 API 與 worker 需要共用同一個檔案路徑。若另外設定 `API_USAGE_DB_PATH` 或 `WATCHLIST_DB_PATH`，也要讓 API 與背景 worker 指向同一份檔案。

## 常見問題

### 1. 顯示缺少 API key

確認已設定：

```bash
cat backend/.env
```

應該包含：

```bash
GEMINI_API_KEYS=...
```

### 2. 分析很久沒有完成

通常是模型 API 回應慢、API quota 接近限制，或個股資料很異常導致 Agent 重試。後端會透過 SSE 持續送出 ping，前端沒有立即完成不一定代表失敗。

### 3. FinMind 顯示 `Requests reach the upper limit`

這代表 FinMind 公開資料額度已達上限。系統仍會使用 Yahoo Finance / yfinance 資料繼續分析，但近期月營收或官方中文名稱可能缺漏。部分常用台股名稱已加入 fallback。

### 4. 8080 port 被占用

`start_mac.command` 會嘗試停止舊的 8080 服務。若手動處理：

```bash
lsof -ti tcp:8080
kill <PID>
```

### 5. 雙擊 `start_mac.command` 無法啟動

確認檔案有執行權限：

```bash
chmod +x start_mac.command
```

如果 macOS 隔離標記造成阻擋：

```bash
xattr -d com.apple.quarantine start_mac.command
```

### 6. API key 每天什麼時候重置額度？

- Gemini / Google AI：每日額度通常依 Google project 在 Pacific Time 00:00 重置，台灣時間會隨夏令時間約為 15:00 或 16:00。
- Google Custom Search：每日 quota 也以 Pacific Time 00:00 為常見基準。
- Financial Modeling Prep：FAQ 使用 3 PM EST 字樣，台灣時間約為隔日 04:00；若其系統依美東夏令時間運作，可能約為隔日 03:00。

前端「API 額度」只顯示本機 `api_usage_events` 觀測到的 provider request；最終剩餘額度仍以 Google Cloud / AI Studio / FMP 後台為準。

### 7. 為什麼顯示「資料快照已刷新，但 HTML/Markdown 分析本文未重新執行」？

這代表系統只更新了該報告旁邊的 `.data.json`，例如最新股價、來源審計與資料可信度；原 HTML / Markdown 的段落文字、估值敘述與投資結論仍是原本生成時間的模型輸出。若要更新結論，請在報告預覽使用重跑功能。

## 開發注意事項

- 不要把生成報告提交到 Git。
- 不要把真實 API key 寫進程式碼。
- Prompt 主要放在 `backend/prompts/agents.json`，修改後請確認 1 到 7 號 Agent 都保留 system 與 analysis prompt。
- HTML 報告版型主要放在 `backend/templates/report.html.j2`，Python 只負責整理資料與渲染模板。
- 修改 prompt 或品質檢查後，建議至少跑一次 `python3 -m py_compile`。
- 若調整公司身分檢查，請測試「同業比較」與「公司錯置」兩種情境，避免誤殺產業普通名詞。

## 快速檢查

```bash
python3 -m py_compile backend/config.py backend/cache_store.py backend/job_store.py backend/analysis_jobs.py backend/task_queue.py backend/prompt_loader.py backend/agent_runner.py backend/api.py backend/financial_data.py backend/report_gen.py main.py
rg -n "API_KEY|PRIVATE KEY|github[_-]pat" .
```

第二個指令不應在可提交檔案中找到任何秘密資訊。
