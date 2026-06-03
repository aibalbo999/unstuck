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
- 內建報告刪除 API，會同步刪除 `.html` 與 `.md`
- Agent 3 / 4 / 7 使用 JSON 結構化輸出優先解析，正則表達式僅保留為備援
- 財務資料使用本地 SQLite 持久化快取，預設 24 小時
- yfinance 欄位缺漏時會用 FMP（需 API key）或可追溯的衍生補值補上市場欄位、TTM 營收或 FCF，並在 prompt 中揭露限制
- 歷史報告會自動清理孤立 Markdown，並刪除超過保留天數的舊報告
- 長任務透過 SQLite job/event store 與任務佇列抽象執行，可用本地 worker 或切換 RQ/Redis
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
│   ├── analysis_jobs.py    # 可匯入的分析任務入口，本地/RQ worker 共用
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
├── start_mac.command       # macOS 一鍵啟動腳本
└── README.md
```

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

支援的 key 名稱：

- `GEMINI_API_KEYS`
- `GOOGLE_API_KEYS`
- `GOOGLE_API_KEY_1` 到 `GOOGLE_API_KEY_10`
- `GEMINI_API_KEY_1` 到 `GEMINI_API_KEY_10`

可選設定：

- 模型路由固定為 Agent 1-6 與提煉摘要使用 `gemma-4-31b-it`，Agent 7 與最終稽核/修復使用 `gemini-3.5-flash`
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
- `ANALYSIS_JOB_STALE_SECONDS`：queued/running 任務超過此秒數未更新時不再被視為活躍，預設 `21600`
- `FMP_API_KEY`：可選，yfinance 缺少即時報價、市值、P/E、52 週高低時，用 FMP stable quote API 補值
- `FMP_BASE_URL`：FMP API base URL，預設 `https://financialmodelingprep.com/stable`

不要提交這些內容：

- `backend/.env`
- `backend/output/`
- `backend/cache/`
- API key、token、私鑰、憑證檔

## 安裝

建議使用 Python 3.10 以上；目前程式碼仍相容 Python 3.9。Gemini 呼叫使用新版 `google-genai` SDK，不再使用已停止維護的 `google-generativeai`。

```bash
cd backend
python3 -m pip install --user -r requirements.txt
```

如果想使用虛擬環境：

```bash
python3 -m venv .venv
source .venv/bin/activate
cd backend
python -m pip install -r requirements.txt
```

## 啟動方式

### macOS 一鍵啟動

在 Finder 內雙擊：

```text
start_mac.command
```

腳本會啟動後端並開啟：

```text
http://127.0.0.1:8080
```

### 手動啟動

```bash
cd backend
python3 -m uvicorn api:app --host 0.0.0.0 --port 8080
```

然後打開：

```text
http://127.0.0.1:8080
```

## 使用方式

1. 開啟首頁。
2. 輸入股票代號，例如 `2330`、`2059`、`6806.TW`。
3. 按下分析。
4. 等待 7 個 Agent 依序完成。
5. 報告完成後會出現在歷史清單。

分析時間會受模型回應速度與 API 額度影響。部分個股可能需要 10 分鐘以上。

## API

取得歷史報告：

```bash
curl http://127.0.0.1:8080/api/reports
```

分析股票：

```bash
curl -N http://127.0.0.1:8080/api/analyze/2330
```

開啟報告：

```text
http://127.0.0.1:8080/api/report/<filename>
```

刪除報告：

```bash
curl -X DELETE http://127.0.0.1:8080/api/reports/<filename>
```

## 輸出檔案

報告預設輸出到：

```text
backend/output/
```

每份報告會產生：

- `.html`
- `.md`

`backend/output/` 已在 `.gitignore` 中，不會被提交。

`backend/cache/` 也已被 Git 忽略。財務資料快取預設保存 24 小時，可透過 `FINANCIAL_DATA_CACHE_SECONDS` 調整。歷史報告預設保留 30 天，可透過 `REPORT_RETENTION_DAYS` 調整；前端刪除 HTML 報告時，後端會同步刪除同名 Markdown。

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

任務狀態與 SSE 事件會寫入 `TASK_DB_PATH` 指定的 SQLite 檔，所以 API 與 worker 需要共用同一個檔案路徑。

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
