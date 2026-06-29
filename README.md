# Wall Street AI Stock Research System

這是一套本機版股票研究報告產生系統。使用者輸入股票代號後，後端會抓取公開財務資料，交由多個分析 Agent 依序完成商業模式、財務、護城河、估值、成長潛力、多空辯論與最終投資建議，最後輸出 HTML / Markdown 報告。

> 注意：本專案產生的是研究輔助內容，不是投資建議。所有輸出都應再經人工查核。

## 功能

- FastAPI 後端與簡易前端介面
- SSE 即時推播分析進度
- 支援台股代號，例如 `2330`、`2330.TW`
- 自動切換 `.TW` / `.TWO` 查詢
- 多 Agent 串接分析流程，支援 Mode A（學術深度派）、Mode B（實戰交易派）、Mode C（逆勢交易與泡沫狙擊）與 Mode D（極短線波段與事件驅動）
- 產生 HTML 與 Markdown 報告
- 前端分成「分析」與「報告與維運」頁籤；歷史報告、預覽、比較留在分析頁，API 額度、watchlist、來源健康與本機維護集中在維運頁並於首次開啟時載入
- 歷史報告支援資料可信度、決策追蹤、版本篩選、報告比較與相容性提示
- 報告預覽可只刷新資料快照，也可排隊重跑最終投資建議、Mode B 或完整報告
- 歷史 API 回傳 `decision_freshness`，明確區分「資料快照已更新」與「投資結論是否已依新資料重跑」
- 報告會輸出投資論文、核心假設、紅線、估值錨點與鏡子測試，方便後續追蹤結論是否仍成立
- 報告與 `.data.json` 會揭露 `data_confidence_score`、低信心目標價限制與 reproducibility packet，方便追溯 snapshot hash、provider、prompt/model 與資料時間
- 報告產生時會執行數字證據抽查 exit gate，將 Markdown 數字主張與 data snapshot 比對後寫入 metadata
- 決策追蹤會自動掃描滿 3 / 6 / 12 個月的歷史報告，抓取發布日與到期日股價，計算 ROI、命中率與 Hit/Miss，並在「報告與維運」顯示回測績效
- 新報告會載入同股票上一期報告與回測結果，將 `temporal_memory` 只注入最終決策 Agent，強制檢討先前目標價與投資建議是否失準
- 內建報告刪除 API，會同步刪除 `.html`、`.md` 與資料快照
- 結構化 Agent 使用 JSON 輸出優先解析；Mode A/B 會解析護城河、估值與投資建議，Mode C 會解析泡沫狙擊建議，Mode D 會解析極短線交易設定
- Mode C 的 Agent 19 報告會強制保留做空觸發條件、防軋空停損點，並將 `[投資建議]` 區塊固定放在最終段落尾端；Mode D 則使用 Agent 24 輸出標準化 Trade Setup
- 財務資料使用本地 SQLite 持久化快取，預設 24 小時
- 台股會嘗試以 FinMind / TWSE 官方資料補抓最近四季財報，成功時納入跨來源比對；未取得時 HTML 報告會顯示官方財務資料警示
- yfinance 欄位缺漏時會用 FMP（需 API key）或可追溯的衍生補值補上市場欄位、TTM 營收或 FCF，並在 prompt 中揭露限制
- QuantEngine 若因缺少 `total_equity`、`total_debt`、`free_cash_flows` 等欄位而使用預設假設，會在 `quant_metrics` 標記 `fallback_fields` 與 `data_quality_warning`
- 歷史報告會自動清理孤立 Markdown，並刪除超過保留天數的舊報告
- 長任務透過 SQLite job/event store 與任務佇列抽象執行，可用本地 worker 或切換 RQ/Redis
- 多 Agent 分析流程已改由 LangGraph `StateGraph` 執行；Worker 使用 SQLite checkpoint 以 `job_id:pipeline_id` 恢復 429 / 暫時性中斷，不重跑已完成節點
- Agent step cache 會以 ticker、資料快照 fingerprint、agent、prompt version、model 與 prompt hash 快取成功輸出，讓相同資料與 prompt 的 rerun 可跳過 LLM 呼叫並還原 structured output
- API 額度儀表板使用 `api_usage_events` ledger 統計 Gemini provider request、Google Custom Search 與 FMP 本機觀測用量
- Watchlist 可設定盤前/盤後批次分析，儲存在 SQLite，排程執行會先原子認領 due slot 並保留舊 JSON 一次性匯入相容
- Watchlist 支援事件驅動雷達 triggers：跌破均線、外資連賣、VIX 飆升會自動派送 Mode C；營收創高會自動派送 Mode B，且每日事件以 SQLite 去重
- Daily screener 會為候選股附加 Quality Funnel：基本面不足標示 `gray`，硬性品質缺陷標示 `reject`，完整通過標示 `pass`
- 研究 playbook registry 統一描述 Mode A/B/C/D 與買入前 checklist、投資論文追蹤、組合檢查、品質篩選等非 pipeline 工作流
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
│   ├── watchlist_triggers.py # Watchlist 事件雷達 trigger 判斷
│   ├── decision_backtest_service.py # 決策追蹤到期回測與績效統計
│   ├── temporal_memory_service.py # 上一期報告記憶與最終 Agent 反思 context
│   ├── watchlist_claim_store.py # Watchlist 排程 due slot 原子認領
│   ├── analysis_jobs.py    # 可匯入的分析任務入口，本地/RQ worker 共用
│   ├── report_rerun_service.py # 報告局部/完整重跑 orchestration
│   ├── investment_thesis.py # 投資論文、紅線與鏡子測試輸出
│   ├── evidence_exit_gate.py # 報告數字證據抽查 gate
│   ├── research_playbooks.py # Pipeline 與決策紀律 playbook registry
│   ├── quality_funnel.py # 候選股品質漏斗 pass/gray/reject
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

修改端點會要求 `X-Mutation-Token`。舊版 `X-Admin-Token` alias 預設不再接受；若短期需要相容舊腳本，可暫時設定 `ALLOW_LEGACY_ADMIN_TOKEN=true`。若沒有設定 `MUTATION_API_TOKEN`，後端會在啟動時產生同源 runtime token，前端會自動透過 `/api/client-config` 取得；自動化腳本可參考 [docs/api.md](docs/api.md)。

Production profile 請設定 `UNSTUCK_ENV=production` 或 `DEPLOYMENT_MODE=server`，並明確提供 `MUTATION_API_TOKEN` 與非 wildcard 的 `ALLOWED_ORIGINS`。Production 缺 token 或使用 `ALLOWED_ORIGINS=*` 會 fail fast；production/server/lan CORS 只允許必要 methods / headers，並且需要 `BASIC_AUTH_USERNAME` / `BASIC_AUTH_PASSWORD` 或 `EXTERNAL_ACCESS_CONTROLLED=true` 表示已由 OAuth proxy / Tailscale ACL 等外層控管。local profile 則維持 runtime token 與開發便利性，僅適合綁定 `127.0.0.1` 的本機使用。

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
- `GOOGLE_SEARCH_REFERER`：可選；若 Google Search API key 使用 HTTP Referrer 限制，後端呼叫會把此值送為 `Referer` header。更建議建立一把後端專用 key，Application restriction 使用 IP 或暫時 None，API restriction 限制在 Custom Search JSON API。
- `WEB_SEARCH_PROVIDER_ORDER`：可選，替代搜尋來源順序，預設 `tavily,serpapi,google_news_rss,gdelt,yahoo_rss,brave`；`google_news_rss`、`gdelt`、`yahoo_rss` 不需 key。
- `BRAVE_SEARCH_API_KEY`、`TAVILY_API_KEY`、`SERPAPI_API_KEY`：可選，用於替代 Google Search 的近期催化劑與同業搜尋。Bing Search APIs 已於 2025-08-11 退役，不建議新設定使用。
- `FMP_API_KEY`：可選，用於 yfinance 缺漏時補市場欄位與新聞
- `FINMIND_API_TOKEN`：可選，用於提高 FinMind 台股官方財報、月營收與法人資料抓取穩定度；未設定時仍會嘗試公開額度
- `FRED_API_KEY`：可選，用於抓取 DGS10、CPI 年增率與 VIX；模組使用 15 分鐘記憶體快取以降低請求頻率

可選設定：

- 模型路由預設由 `backend/model_routes.json` 管理，也可用 `MODEL_ROUTES_FILE`、`DEFAULT_ANALYSIS_MODEL`、`DEFAULT_DECISION_MODEL`、`AGENT_MODELS_JSON` 或 `AGENT_MODEL_1` 到 `AGENT_MODEL_7` 覆寫
- `LARGE_CONTEXT_MODEL_PATTERN`：預設已包含 `gemma`，確保 gemma-4-31b-it 使用 28,000 字元大 context 預算。
- `OUTPUT_DIR`：報告輸出目錄，預設 `backend/output/`
- `CACHE_DB_PATH`：SQLite 快取檔位置，預設 `backend/cache/stock_agent_cache.sqlite3`
- `FINANCIAL_DATA_CACHE_SECONDS`：財務資料快取秒數，預設 `86400`
- `REPORT_RETENTION_DAYS`：舊報告保留天數，預設 `30`
- `REPORT_CLEANUP_INTERVAL_SECONDS`：Worker maintenance 清理週期秒數，預設 `86400`
- `ANALYSIS_WORKER_COUNT`：舊版本地佇列 worker 數；Web/API 模式不再啟動本地 worker
- `TASK_QUEUE_BACKEND`：任務佇列後端，Web/API 模式必須使用 `rq`，預設 `rq`；`TASK_QUEUE_BACKEND=local` 僅保留給嵌入式測試/本地 helper，API 會以 `API task queue requires Redis and RQ` 拒絕啟動
- `REDIS_URL`：RQ 模式使用的 Redis 連線，預設 `redis://localhost:6379/0`
- `TASK_QUEUE_NAME`：RQ queue 名稱，預設 `stock-analysis`
- `TASK_QUEUE_NAMES`：RQ worker 會同時監聽的 queue 清單，預設包含 `stock-analysis,analysis.high,analysis.normal,watchlist,maintenance,llm.retry`
- `TASK_QUEUE_ROUTE_ANALYSIS` / `TASK_QUEUE_ROUTE_REPORT_RERUN` / `TASK_QUEUE_ROUTE_WATCHLIST`：依任務類型路由到指定 queue，預設分別為 `analysis.high`、`analysis.normal`、`watchlist`
- `UNSTUCK_ENV`：`local` 或 `production`；production 會禁止缺少 mutation token 的不安全啟動
- `MUTATION_API_TOKEN`：production / server / lan profile 必填；mutation endpoints 使用 `X-Mutation-Token`
- `ALLOW_LEGACY_ADMIN_TOKEN`：是否暫時接受舊版 `X-Admin-Token` alias，預設 `false`
- `MUTATION_RATE_LIMIT_MAX_REQUESTS` / `MUTATION_RATE_LIMIT_WINDOW_SECONDS`：mutation endpoint in-memory rate limit，預設 `120` 次 / `60` 秒；設為 `0` 可停用
- `BASIC_AUTH_USERNAME` / `BASIC_AUTH_PASSWORD`：啟用 API/UI 全站 Basic Auth；production/server/lan profile 若沒有外層 access control，必須設定
- `EXTERNAL_ACCESS_CONTROLLED`：設為 `true` 表示已由 OAuth proxy、Tailscale ACL 或等效網路邊界控管；可取代內建 Basic Auth
- `ALLOWED_ORIGINS`：production 必須是明確 allowlist，不可使用 `*`
- `RQ_JOB_MAX_RETRIES`：RQ job 最大重試次數，預設 `4`
- `RQ_JOB_RETRY_INTERVALS`：RQ 延遲重試秒數清單，預設 `60,300,900,1800`
- `RQ_JOB_TIMEOUT_SECONDS`：單一 RQ job 最長執行秒數，預設 `14400`（4 小時），避免完整報告/LLM 重跑被 RQ 預設短 timeout 提早中止
- `LANGGRAPH_CHECKPOINT_PATH`：LangGraph SQLite checkpoint DB，預設 `backend/cache/langgraph_checkpoints.sqlite3`
- `TASK_DB_PATH`：任務與 SSE event SQLite 檔位置，預設 `backend/cache/analysis_jobs.sqlite3`
- `SQLITE_BACKUP_DIR`：SQLite 每日維護備份目錄，預設 `backend/cache/sqlite_backups`
- `API_USAGE_DB_PATH`：API 用量 ledger SQLite 檔位置，預設跟隨 `TASK_DB_PATH`
- `WATCHLIST_PATH`：舊版 watchlist JSON 位置；若存在會一次性匯入 SQLite，預設 `backend/cache/watchlist.json`
- `WATCHLIST_DB_PATH`：watchlist SQLite 檔位置，預設為 `WATCHLIST_PATH` 同名 `.sqlite3`
- `ANALYSIS_JOB_STALE_SECONDS`：queued/running 任務超過此秒數未更新時不再被視為活躍，預設 `21600`
- `ANALYSIS_JOB_HISTORY_RETENTION_DAYS`：已完成/失敗/取消任務紀錄保留天數，預設 `30`
- `LLM_AGENT_CALL_TIMEOUT_SECONDS`：單次 Agent LLM 呼叫 timeout 秒數，預設 `120`；會傳入 Google GenAI `HttpOptions.timeout`，非同步路徑另有外層 `asyncio.wait_for` 保護，設為 `0` 可關閉
- `PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS`：有備援模型時 primary model 單次呼叫 timeout 秒數，預設 `360`，讓 Gemma 等大型 primary 模型有較完整的產出時間
- `FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS`：備援模型單次呼叫 timeout 秒數，預設沿用 `LLM_AGENT_CALL_TIMEOUT_SECONDS`
- `AGENT_STEP_CACHE_ENABLED`：是否啟用 Agent step cache，預設 `true`
- `AGENT_STEP_CACHE_SECONDS`：Agent step cache TTL 秒數，預設 `604800`（7 天）
- `LLM_SERVER_ERROR_MAX_ATTEMPTS`：模型服務 500/503/忙碌時的持續嘗試次數，預設 `6`
- `LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS`：模型服務 5xx 重試 backoff 單次等待上限，預設 `45`
- 429 quota / rate-limit 會至少輪完所有 API key 才判定該模型不可用；任務事件只記錄 `key_slot/key_count`，不保存 key 明文
- `FMP_BASE_URL`：FMP API base URL，預設 `https://financialmodelingprep.com/stable`
- `WACC_COST_OF_EQUITY_PCT`：系統 DCF/WACC 的預設股權成本，預設 `10.0`
- `WACC_COST_OF_DEBT_PCT`：系統 DCF/WACC 的預設債務成本，預設 `3.0`
- `WACC_TAX_RATE_PCT`：系統 DCF/WACC 的預設稅率，預設 `20.0`
- `GDELT_RATE_LIMIT_COOLDOWN_SECONDS`：GDELT 國際新聞遇到 HTTP 429 後的冷卻秒數，預設 `900`
- GDELT 國際新聞會先使用 topic cache；遇到 429 時會進入 cooldown，優先讀快取，否則改用 Google News RSS 備援，避免單次分析連續打爆 GDELT

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
`scripts/ci_gate.sh` 會產生 `backend/cache/sbom.cdx.json` CycloneDX SBOM，並以 `coverage run --source=backend` 執行非 live 測試，要求 backend line coverage 不低於 75%。
報告防回歸測試包含 `tests/test_golden_reports.py`；若報告文字或章節結構是預期變更，請先人工檢查 fixed fake data 的 Markdown 輸出，再更新 `tests/fixtures/golden_reports/2330_v1_markdown.json` 的 SHA-256。

## 維護工具

本機維護命令請透過 wrapper 執行，腳本會自動套用專案 Python 與 `PYTHONPATH`：

```bash
scripts/maintenance.sh storage-summary
scripts/maintenance.sh sqlite-maintenance --write
scripts/maintenance.sh cleanup-provider-sla
scripts/maintenance.sh cleanup-report-index --write
scripts/maintenance.sh cleanup-analysis-history --write
scripts/maintenance.sh verify-snapshots --write
```

`cleanup-report-index` 預設只會 dry-run；加上 `--write` 才會刪除已不存在輸出目錄的報告索引列。
`cleanup-analysis-history` 預設也只會 dry-run；加上 `--write` 才會刪除過舊且已結束的任務與孤兒事件，queued/running 任務會保留。
`sqlite-maintenance` 預設只會 dry-run；加上 `--write` 會對 runtime SQLite DB 建立每日備份、執行 WAL checkpoint 與 `VACUUM`。每日備份以 `SQLITE_BACKUP_DIR` 為目錄，同一天重跑會沿用既有備份。

## 啟動方式

### macOS 一鍵啟動

在 Finder 內雙擊：

```text
start_mac.command
```

腳本會優先使用專案 `.venv`；若尚未建立，會優先用 `/opt/homebrew/bin/python3.13` 建立虛擬環境並安裝 `backend/requirements.txt`。合併 API / Worker 拆分後，這個一鍵腳本也會自動：

1. 使用 `TASK_QUEUE_BACKEND=rq` 與預設 `REDIS_URL=redis://localhost:6379/0`。
2. 檢查 Redis；若本機 Redis 尚未啟動，會用 `redis-server` 啟動一個本腳本管理的 Redis。
3. 啟動 `python backend/worker_main.py --role all`，讓分析 queue、watchlist scheduler、decision tracking scheduler 與 maintenance 背景任務都能運作。
4. 啟動 FastAPI / uvicorn 並開啟：

```text
http://127.0.0.1:8080
```

關閉終端機或按下 `Ctrl+C` 時，腳本會停止本次啟動的 API、Worker，以及本次由腳本啟動的 Redis；如果 Redis 原本就已經在跑，腳本只會共用它，不會關掉你的既有 Redis。

啟動前腳本會先清理同專案殘留的 `worker_main.py --role all`、`queue`、`schedulers`、`maintenance` worker，避免舊 worker 仍吃著 Redis/RQ 任務，造成前端按下分析或 watchlist 操作後看似沒有新終端訊息。

如果第一次啟動時尚未安裝 Redis，但系統有 Homebrew，腳本會詢問是否執行 `brew install redis`；按 Enter 或輸入 `Y` 即可安裝後繼續啟動。

若要用同一個 Wi-Fi 上的手機或平板開啟，請雙擊：

```text
start_mac_lan.command
```

或在終端機執行：

```bash
LAN_ACCESS=1 ./start_mac.command
```

`start_mac_lan.command` 只是設定 `LAN_ACCESS=1` 後執行同一份 `start_mac.command`，因此會套用相同的 Redis、Worker、排程器與殘留 worker 清理流程。

啟動後終端機會顯示手機可開啟的區網網址，例如：

```text
http://192.168.1.115:8080
```

`LAN_ACCESS=1` 只建議在可信任的私人 Wi-Fi 使用；公共網路請維持預設的本機模式。LAN/server profile 不應只靠 mutation token；請設定 Basic Auth，或確認前方有 OAuth proxy / Tailscale ACL 並設 `EXTERNAL_ACCESS_CONTROLLED=true`。

### 手動啟動

Web/API 模式需要 Redis/RQ worker。macOS 一鍵腳本會自動完成這些步驟；若要手動啟動，順序如下：

```bash
redis-server
python backend/worker_main.py --role all
uvicorn api:app --app-dir backend --host 127.0.0.1 --port 8080
```

然後打開：

```text
http://127.0.0.1:8080
```

## 使用方式

1. 開啟首頁，預設停在「分析」頁籤。
2. 輸入股票代號，例如 `2330`、`2059`、`6806.TW`。
3. 選擇分析模式；預設是 Mode A，也可選 Mode B、Mode C 或 Mode D。
4. 等待 Agent 依序完成。
5. 報告完成後會出現在同一頁的歷史清單，可直接預覽、下載、比較或重跑。
6. 到「報告與維運」查看決策回測績效、API/來源健康、Watchlist 批次排程與事件雷達 trigger。

分析時間會受模型回應速度與 API 額度影響。部分個股可能需要 10 分鐘以上。

日常操作建議：

- 「分析」頁籤：新分析、查找歷史報告、篩選 Mode A/B/C/D、查看決策追蹤、刷新資料快照、重跑報告與比較報告。
- 「報告與維運」頁籤：查看 API 額度、本機 watchlist、來源健康、任務狀態與清理工具；首次打開頁籤才會載入這些維運資料。
- 「資料快照已刷新，但 HTML/Markdown 分析本文未重新執行」代表只更新了 `.data.json` 的最新股價/來源/可信度，原本報告正文和投資結論還是舊模型在原生成時間做出的判斷；若要讓文字與結論一起更新，請使用重跑功能。

## API

Migration note：新整合請使用 `POST /api/analysis-jobs` 建立任務，再用 `GET /api/analysis-jobs/{job_id}/events` 讀 SSE。舊 `GET /api/analyze/{ticker}` 仍保留給既有 UI / script，但已標示 deprecated，未來不應再新增依賴。

取得歷史報告：

```bash
curl http://127.0.0.1:8080/api/reports
curl "http://127.0.0.1:8080/api/reports?q=2308&pipeline=v2&include_versions=true"
curl "http://127.0.0.1:8080/api/reports?q=2308&pipeline=v3&include_versions=true"
```

分析股票：

```bash
TOKEN="$(curl -fsS http://127.0.0.1:8080/api/client-config | python -c 'import json,sys; print(json.load(sys.stdin)["mutation_token"])')"
JOB_ID="$(curl -fsS -X POST http://127.0.0.1:8080/api/analysis-jobs \
  -H "Content-Type: application/json" \
  -H "X-Mutation-Token: $TOKEN" \
  -d '{"ticker":"2330.TW","pipeline_id":"mode_a","force":false,"resume":true}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"
curl -N "http://127.0.0.1:8080/api/analysis-jobs/${JOB_ID}/events"
```

舊相容 endpoint 仍可讀：

```bash
curl -N http://127.0.0.1:8080/api/analyze/2330
curl -N "http://127.0.0.1:8080/api/analyze/2330?pipeline=v3"
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

`full` 會先強制刷新資料，再用原報告 pipeline 完整重跑；`final_recommendation` 只重跑該報告 pipeline 的最終建議 Agent；`mode_b` 會以 Mode B 重新分析。

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
curl http://127.0.0.1:8080/api/observability/dashboard
curl http://127.0.0.1:8080/readyz
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

`.data.json` 是資料快照，包含來源審計、資料可信度、`data_confidence_score`、結論 guardrails、`reproducibility_packet`、決策追蹤基準與重跑 context。當資料信心低於 60/100 時，snapshot 會標記明確目標價不可用，最終結論只能保留區間或資料不足說明。只刷新資料快照時，HTML / Markdown 正文不會自動改寫。

`backend/cache/` 也已被 Git 忽略。財務資料快取預設保存 24 小時，可透過 `FINANCIAL_DATA_CACHE_SECONDS` 調整。歷史報告預設保留 30 天，可透過 `REPORT_RETENTION_DAYS` 調整；前端刪除 HTML 報告時，後端會同步刪除同名 Markdown 與資料快照。

## API / Worker 分離與任務佇列

FastAPI 現在只負責 HTTP 與送任務進 Redis/RQ；耗時分析、watchlist scheduler、decision tracking scheduler 與 maintenance cleanup 都由獨立 Worker process 執行。最小本機啟動順序：

```bash
redis-server
python backend/worker_main.py --role all
uvicorn api:app --app-dir backend
```

`backend/.env` 至少確認：

```bash
TASK_QUEUE_BACKEND=rq
REDIS_URL=redis://localhost:6379/0
TASK_QUEUE_NAME=stock-analysis
TASK_QUEUE_NAMES=stock-analysis,analysis.high,analysis.normal,watchlist,maintenance,llm.retry
RQ_JOB_TIMEOUT_SECONDS=14400
```

可拆成正式 process roles：

```bash
python backend/worker_main.py --role queue        # RQ analysis worker
python backend/worker_main.py --role schedulers   # watchlist + decision tracking
python backend/worker_main.py --role maintenance  # report/cache/index cleanup
```

也就是 `queue / schedulers / maintenance` 三個角色可獨立交給 process manager 管理。`--role all` 使用 multiprocessing `spawn` 在本機一次啟動三個 child processes；收到 `SIGTERM` / `SIGINT` 時會轉送終止訊號並等待子程序收尾。Queue smoke test 可用 `python backend/worker_main.py --role queue --burst --max-jobs 1` 處理一筆 job 後退出。

Redis health check 可用 `redis-cli -u "$REDIS_URL" ping`（預期 `PONG`），RQ queue 可用 `rq info --url "$REDIS_URL"` 檢查。Worker queue role 會監聽 `TASK_QUEUE_NAMES` 內所有 queue，並以 RQ scheduler 推進 `ScheduledJobRegistry` 內的 delayed retry；人工分析預設進 `analysis.high`，報告重跑進 `analysis.normal`，watchlist 批次進 `watchlist`。LLM 429 / transient failure 會依 `RQ_JOB_MAX_RETRIES` 與 `RQ_JOB_RETRY_INTERVALS` 延遲重試，`waiting_retry` 仍會被視為 active job，避免 API/scheduler 重複送同一檔分析。

若 SQLite job store 仍有 `queued` / `running` / `waiting_retry` 紀錄，但 Redis/RQ 已找不到對應 active 任務，API 與 scheduler 會把該紀錄標為 abandoned，讓前端按鈕、watchlist 批次與後續分析可以重新排隊；若只是既有 `queued` job 遺失 RQ task，建立任務 API 會重新 enqueue 並留下 `queue_recovered` 事件。

API process manager 可用 `/healthz` 做 liveness probe，用 `/readyz` 做 readiness probe；`/readyz` 會檢查 runtime storage 與 Redis/RQ queue，不可用時回 HTTP 503。Operator 可用 `/api/observability/dashboard` 查看報告耗時 p50/p95/p99、stuck jobs、node/model telemetry、prompt token budget、RQ queue depth、provider degradation 與 API quota ledger 摘要。

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

若來源健康或終端機出現 `GDELT ... 429 Too Many Requests`，代表 GDELT 國際新聞來源暫時限流。系統會自動進入 cooldown、讀取 GDELT topic cache，或改用 Google News RSS 備援；通常不需要人工中止分析。若要拉長冷卻時間，可調整 `GDELT_RATE_LIMIT_COOLDOWN_SECONDS`。

### 3. FinMind 顯示 `Requests reach the upper limit`

這代表 FinMind 公開資料額度已達上限。系統仍會使用 Yahoo Finance / yfinance 資料繼續分析，但近期月營收、官方四季財報或法人資料可能缺漏；HTML 報告會標示「台股官方財務資料（TWSE/MOPS）本次未取得」。若你有 FinMind token，可設定 `FINMIND_API_TOKEN` 後重啟。

### 4. 8080 port 被占用

`start_mac.command` 會嘗試停止舊的 8080 服務。若手動處理：

```bash
lsof -ti tcp:8080
kill <PID>
```

### 5. 手機無法開啟系統

手機不能使用 `http://127.0.0.1:8080`，因為那只代表「手機自己」。請確認 Mac 和手機在同一個 Wi-Fi，然後使用 `start_mac_lan.command` 啟動，依終端機顯示的 `http://<Mac區網IP>:8080` 開啟。

若仍無法連線，請檢查 macOS 防火牆是否阻擋 Python / uvicorn 接收區網連線。

### 6. 雙擊 `start_mac.command` 無法啟動

確認檔案有執行權限：

```bash
chmod +x start_mac.command
chmod +x start_mac_lan.command
```

如果 macOS 隔離標記造成阻擋：

```bash
xattr -d com.apple.quarantine start_mac.command
xattr -d com.apple.quarantine start_mac_lan.command
```

### 7. API key 每天什麼時候重置額度？

- Gemini / Google AI：每日額度通常依 Google project 在 Pacific Time 00:00 重置，台灣時間會隨夏令時間約為 15:00 或 16:00。
- Google Custom Search：每日 quota 也以 Pacific Time 00:00 為常見基準。
- Financial Modeling Prep：FAQ 使用 3 PM EST 字樣，台灣時間約為隔日 04:00；若其系統依美東夏令時間運作，可能約為隔日 03:00。

前端「API 額度」只顯示本機 `api_usage_events` 觀測到的 provider request；最終剩餘額度仍以 Google Cloud / AI Studio / FMP 後台為準。

### 7. 為什麼顯示「資料快照已刷新，但 HTML/Markdown 分析本文未重新執行」？

這代表系統只更新了該報告旁邊的 `.data.json`，例如最新股價、來源審計與資料可信度；原 HTML / Markdown 的段落文字、估值敘述與投資結論仍是原本生成時間的模型輸出。若要更新結論，請在報告預覽使用重跑功能。

## 開發注意事項

- 不要把生成報告提交到 Git。
- 不要把真實 API key 寫進程式碼。
- Prompt 主要放在 `backend/prompts/agents.json`，修改後請確認各 pipeline 的 Agent 都保留 system 與 analysis prompt；Mode C 使用 Agent 17 / 18 / 19，Mode D 使用 Agent 22 / 23 / 24。
- HTML 報告版型主要放在 `backend/templates/report.html.j2`，Python 只負責整理資料與渲染模板。
- 修改 prompt 或品質檢查後，建議至少跑一次 `python3 -m py_compile`。
- 修改 DCF/WACC 或 `quant_metrics` 時，請確認 `fallback_fields`、`data_quality_warning`、Agent 7【資料警示】與 final audit 的 DCF 衝突檢查仍一致。
- 修改台股資料 provider 時，請確認 `twse_official` source audit、跨來源比對與報告警示仍能同時運作。
- 若調整公司身分檢查，請測試「同業比較」與「公司錯置」兩種情境，避免誤殺產業普通名詞。

## 快速檢查

```bash
python3 -m py_compile backend/config.py backend/cache_store.py backend/job_store.py backend/analysis_jobs.py backend/task_queue.py backend/prompt_loader.py backend/agent_runner.py backend/api.py backend/financial_data.py backend/report_gen.py main.py
rg -n "API_KEY|PRIVATE KEY|github[_-]pat" .
```

第二個指令不應在可提交檔案中找到任何秘密資訊。
