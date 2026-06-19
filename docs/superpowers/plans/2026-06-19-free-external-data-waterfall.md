# Free External Data Waterfall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立免費新聞、正文萃取、TWSE/MOPS 官方資料與可觀測瀑布流，並正式接入既有 Provider Workflow、Blackboard 與財務斷路器。

**Architecture:** 抓取器只負責單一來源與標準化；`ExternalDataClient` 負責來源排序、降級與 provenance；Provider Workflow 負責 freshness、audit 與 payload merge；財務 reconciliation 僅在官方資料口徑可確認時重新評估 breaker。所有普通測試 mock 網路邊界，live smoke 必須 opt-in。

**Tech Stack:** Python 3.13、pytest、requests、feedparser、ddgs、BeautifulSoup4、trafilatura、pandas、yfinance、Pydantic。

---

## File Map

- Create `backend/news_fetchers.py`: 三個免費新聞/情緒來源與統一 schema。
- Create `backend/text_extractor.py`: 安全下載與 trafilatura 正文萃取。
- Create `backend/official_financials.py`: TWSE 法人與 MOPS 資產負債表 adapter。
- Create `backend/external_data_client.py`: 新聞與財務 waterfall orchestration。
- Create `tests/test_news_fetchers.py`: 新聞正規化及錯誤測試。
- Create `tests/test_text_extractor.py`: URL 安全、timeout 與正文測試。
- Create `tests/test_official_financials.py`: TWSE/MOPS parser 測試。
- Create `tests/test_external_data_client.py`: waterfall 與 circuit breaker 測試。
- Create `tests/live/test_free_external_data_smoke.py`: opt-in 外站 smoke tests。
- Modify `backend/data_fetch/enrichment_providers.py`: 免費新聞 Provider。
- Modify `backend/data_fetch/provider_registry.py`: Provider 排序註冊。
- Modify `backend/data_fetch/enrichment_merge.py`: 標準新聞資料 merge。
- Modify `backend/data_fetch/taiwan_providers.py`: TWSE 法人備援。
- Modify `backend/data_reconciliation.py`: 執行 MOPS 核對與結果契約。
- Modify `backend/pipeline_async.py`: 將官方 reconciliation 寫入 State 並重新驗證 breaker。
- Modify `backend/requirements.txt` and `backend/requirements.lock`: 固定新增依賴。
- Modify `docs/operator-guide.md` and `docs/architecture.md`: 安裝、操作與資料流。

### Task 1: Dependency Contract

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements.lock`
- Test: `tests/test_supply_chain_audit.py`

- [x] **Step 1: Write the failing dependency test**

```python
def test_free_external_data_dependencies_are_locked():
    required = {"feedparser", "ddgs", "beautifulsoup4", "requests", "trafilatura"}
    declared = normalized_requirement_names(BACKEND / "requirements.txt")
    locked = normalized_requirement_names(BACKEND / "requirements.lock")
    assert required <= declared
    assert required <= locked
```

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_supply_chain_audit.py::test_free_external_data_dependencies_are_locked -v`
Expected: FAIL because the five packages are absent.

- [x] **Step 3: Add bounded direct requirements and regenerate the lock**

Add compatible ranges to `requirements.txt`, install them in the project environment, then run the repository's lock generation command or `python -m pip freeze > backend/requirements.lock` using the same environment used by CI.

- [x] **Step 4: Verify GREEN**

Run: `pytest tests/test_supply_chain_audit.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/requirements.lock tests/test_supply_chain_audit.py
git commit -m "build: add free external data dependencies"
```

### Task 2: Free News Fetchers

**Files:**
- Create: `backend/news_fetchers.py`
- Create: `tests/test_news_fetchers.py`

- [x] **Step 1: Write failing normalization and error tests**

```python
def test_google_news_returns_standard_records(monkeypatch):
    monkeypatch.setattr(news_fetchers.feedparser, "parse", lambda *_a, **_k: Feed(entries=[ENTRY]))
    assert news_fetchers.fetch_google_news_rss("台積電", 1) == [{
        "title": "台積電展望", "link": "https://example.test/a",
        "published_date": "2026-06-19T08:00:00+00:00",
        "source": "Google News RSS", "summary": "摘要",
    }]

def test_ptt_timeout_returns_empty_list(monkeypatch, caplog):
    monkeypatch.setattr(news_fetchers.requests, "get", raise_timeout)
    assert news_fetchers.fetch_ptt_stock_sentiment("2330") == []
    assert "timeout" in caplog.text.lower()
```

Also cover DDG key mapping, duplicate removal, limit clamping, PTT relative links, deleted posts, and ticker filtering.

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_news_fetchers.py -v`
Expected: collection FAIL because `news_fetchers` does not exist.

- [x] **Step 3: Implement source-isolated fetchers**

Define `NewsRecord = TypedDict(...)`, `_record(...)`, `_dedupe(...)`, and the three requested public functions. Catch `requests.Timeout`, `requests.RequestException`, feed/parser exceptions and optional DDG import errors; log provider and operation but never response bodies.

- [x] **Step 4: Verify GREEN**

Run: `pytest tests/test_news_fetchers.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/news_fetchers.py tests/test_news_fetchers.py
git commit -m "feat: add free news and PTT fetchers"
```

### Task 3: Safe Article Text Extraction

**Files:**
- Create: `backend/text_extractor.py`
- Create: `tests/test_text_extractor.py`

- [x] **Step 1: Write failing extraction and SSRF tests**

```python
def test_extract_article_text_returns_clean_bounded_text(monkeypatch):
    monkeypatch.setattr(text_extractor.requests, "get", fake_html_response)
    monkeypatch.setattr(text_extractor.trafilatura, "extract", lambda *_a, **_k: "正文  \n\n內容")
    assert text_extractor.extract_article_text("https://news.example/a", max_chars=4) == "正文  內"

@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/a", "http://10.0.0.1/a"])
def test_extract_article_text_rejects_unsafe_urls(url):
    assert text_extractor.extract_article_text(url) is None
```

Cover timeout, blocked response, empty extraction and redirect to private host.

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_text_extractor.py -v`
Expected: collection FAIL because `text_extractor` does not exist.

- [x] **Step 3: Implement bounded secure extraction**

Validate scheme/hostname with `urllib.parse` and `ipaddress`; resolve public DNS before request and validate final response URL. Download with timeout and maximum response bytes, call `trafilatura.extract(include_comments=False, include_tables=False)`, normalize whitespace, truncate to `max_chars`, and return `None` on controlled failures.

- [x] **Step 4: Verify GREEN and commit**

Run: `pytest tests/test_text_extractor.py -v`
Expected: PASS.

```bash
git add backend/text_extractor.py tests/test_text_extractor.py
git commit -m "feat: add safe article text extraction"
```

### Task 4: TWSE and MOPS Official Adapters

**Files:**
- Create: `backend/official_financials.py`
- Create: `tests/test_official_financials.py`

- [x] **Step 1: Write failing TWSE and MOPS parser tests**

```python
def test_twse_filters_ticker_and_normalizes_net_trades(fake_session):
    result = fetch_twse_institutional_trades("2330.TW", "2026-06-18", session=fake_session)
    assert result["ticker"] == "2330"
    assert result["foreign_net"] == 1200
    assert result["total_net"] == 1350
    assert result["source"] == "TWSE OpenAPI"

def test_mops_posts_period_and_extracts_balance_sheet(fake_session, monkeypatch):
    monkeypatch.setattr(pd, "read_html", lambda *_a, **_k: [MOPS_FRAME])
    result = fetch_mops_balance_sheet("2330", 2025, 4, session=fake_session)
    assert fake_session.last_data["co_id"] == "2330"
    assert result["total_liabilities"] == 900000000
    assert result["statement_scope"] == "consolidated"
```

Cover comma/parentheses numbers, ROC year conversion, MultiIndex columns, no-table HTML, unknown unit, timeout and non-Taiwan ticker.

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_official_financials.py -v`
Expected: collection FAIL because `official_financials` does not exist.

- [x] **Step 3: Implement official adapters**

Use injected `requests.Session`, fixed endpoints, browser-like headers and `(connect, read)` timeout. Flatten pandas columns, identify account/value columns, preserve `raw_line_items`, and only populate canonical totals when unit and statement period are known.

- [x] **Step 4: Verify GREEN and commit**

Run: `pytest tests/test_official_financials.py -v`
Expected: PASS.

```bash
git add backend/official_financials.py tests/test_official_financials.py
git commit -m "feat: add TWSE and MOPS official adapters"
```

### Task 5: External Data Waterfall Client

**Files:**
- Create: `backend/external_data_client.py`
- Create: `tests/test_external_data_client.py`

- [x] **Step 1: Write failing waterfall tests**

```python
def test_news_falls_back_google_to_ddg_to_ptt(caplog):
    client = ExternalDataClient(google_news=lambda *_a: [], ddg_news=lambda *_a: [], ptt_news=lambda *_a: PTT)
    assert client.get_news("2330 台積電", ticker="2330") == PTT
    assert "Google News RSS" in caplog.text and "DuckDuckGo" in caplog.text

def test_invalid_yfinance_debt_uses_mops():
    client = ExternalDataClient(financial_fetcher=lambda *_a: {"total_debt_raw": None}, mops_fetcher=lambda *_a, **_k: MOPS)
    result = client.get_financial_data("2330.TW", year=2025, season=4)
    assert result["total_debt_raw"] == MOPS["total_debt"]
    assert result["field_provenance"]["total_debt_raw"] == "MOPS"
```

Cover no PTT for US ticker, duplicate news, valid debt bypass, negative/NaN debt, open-breaker signal, MOPS failure and unresolved status.

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_external_data_client.py -v`
Expected: collection FAIL because `external_data_client` does not exist.

- [x] **Step 3: Implement orchestration with dependency injection**

Create constructor-injected callables, `get_news`, `get_financial_data`, `_needs_official_debt`, `_latest_closed_quarter`, audit event collection and warning logs. Merge only canonical MOPS fields and retain both original payload and field-level provenance.

- [x] **Step 4: Verify GREEN and commit**

Run: `pytest tests/test_external_data_client.py -v`
Expected: PASS.

```bash
git add backend/external_data_client.py tests/test_external_data_client.py
git commit -m "feat: add external data waterfall client"
```

### Task 6: Provider Workflow Integration

**Files:**
- Modify: `backend/data_fetch/enrichment_providers.py`
- Modify: `backend/data_fetch/provider_registry.py`
- Modify: `backend/data_fetch/enrichment_merge.py`
- Modify: `backend/data_fetch/taiwan_providers.py`
- Test: `tests/test_provider_workflow.py`
- Test: `tests/test_architecture_services.py`

- [x] **Step 1: Write failing registry and merge tests**

```python
def test_default_registry_prefers_free_news_waterfall():
    names = ProviderRegistry().provider_names(FetchRequest.from_ticker("2330.TW"), source="recent_catalysts")
    assert names[0] == "Free news waterfall"

def test_free_news_provider_records_fallback_audits(monkeypatch):
    result = asyncio.run(StockDataService(registry=registry).fetch_async(FetchRequest.from_ticker("2330.TW")))
    assert result.data["recent_catalysts"][0]["source"] == "DuckDuckGo News"
    assert any(row["provider"] == "Google News RSS" and row["status"] == "unavailable" for row in result.source_audit)
```

Add a TWSE institutional fallback assertion when FinMind is unavailable.

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_provider_workflow.py tests/test_architecture_services.py -q`
Expected: FAIL because the provider is unregistered and audits are absent.

- [x] **Step 3: Add providers and deterministic merge**

Add `FreeNewsProvider` and TWSE fallback behavior using existing `ProviderResult` helpers. Preserve all waterfall audit events, normalize to the existing catalyst payload, and avoid duplicate records when paid providers also return the same link/title.

- [x] **Step 4: Verify GREEN and commit**

Run: `pytest tests/test_provider_workflow.py tests/test_architecture_services.py -q`
Expected: PASS.

```bash
git add backend/data_fetch/enrichment_providers.py backend/data_fetch/provider_registry.py backend/data_fetch/enrichment_merge.py backend/data_fetch/taiwan_providers.py tests/test_provider_workflow.py tests/test_architecture_services.py
git commit -m "feat: integrate free data providers"
```

### Task 7: Execute MOPS Reconciliation in Blackboard

**Files:**
- Modify: `backend/data_reconciliation.py`
- Modify: `backend/pipeline_async.py`
- Modify: `backend/state_memory.py`
- Test: `tests/test_data_cross_validator.py`
- Test: `tests/test_agent_state_memory.py`

- [x] **Step 1: Write failing state reconciliation tests**

```python
def test_open_breaker_fetches_mops_and_resolves_matching_debt(monkeypatch):
    monkeypatch.setattr(data_reconciliation, "fetch_mops_balance_sheet", lambda *_a, **_k: OFFICIAL)
    result = reconcile_with_official_filing(state, year=2025, season=4)
    assert result.status == "resolved"
    assert state.provider_values["total_debt"][-1].provider == "MOPS"
    assert state.raw_financial_data["official_filings"][0]["source"] == "MOPS"
    assert state.circuit_breaker.status == "closed"

def test_unknown_mops_unit_keeps_breaker_open(monkeypatch):
    monkeypatch.setattr(data_reconciliation, "fetch_mops_balance_sheet", lambda *_a, **_k: UNKNOWN_UNIT)
    reconcile_with_official_filing(state, year=2025, season=4)
    assert state.circuit_breaker.status == "open"
```

Cover period mismatch, consolidated mismatch, MOPS unavailable and multiple blocking fields.

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_data_cross_validator.py tests/test_agent_state_memory.py -q`
Expected: FAIL because reconciliation is currently plan-only.

- [x] **Step 3: Implement official reconciliation**

Add a typed reconciliation result, append official `ProviderValue` entries, preserve filing payload, rerun existing critical-field validation, resolve only compatible fields within tolerance, and sync updated State back to context before valuation agents run.

- [x] **Step 4: Verify GREEN and commit**

Run: `pytest tests/test_data_cross_validator.py tests/test_agent_state_memory.py -q`
Expected: PASS.

```bash
git add backend/data_reconciliation.py backend/pipeline_async.py backend/state_memory.py tests/test_data_cross_validator.py tests/test_agent_state_memory.py
git commit -m "feat: reconcile financial conflicts with MOPS"
```

### Task 8: Live Smoke, Documentation, and Completion Audit

**Files:**
- Create: `tests/live/test_free_external_data_smoke.py`
- Modify: `docs/operator-guide.md`
- Modify: `docs/architecture.md`
- Modify: `docs/superpowers/plans/2026-06-19-free-external-data-waterfall.md`

- [x] **Step 1: Add opt-in live tests**

```python
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FREE_DATA_TESTS") != "1",
    reason="set RUN_LIVE_FREE_DATA_TESTS=1 to call public external sources",
)

def test_google_news_live_returns_standard_shape():
    records = fetch_google_news_rss("台積電", limit=1)
    assert not records or set(records[0]) == {"title", "link", "published_date", "source", "summary"}
```

Add TWSE and MOPS tests that accept either a correctly shaped result or a controlled `None`/empty result while asserting no uncaught exception.

- [x] **Step 2: Document installation and operations**

Document `python -m pip install feedparser ddgs beautifulsoup4 requests trafilatura`, fallback ordering, warning/audit interpretation, live test command, robots/access-policy limitations, and breaker resume conditions. Extend the architecture Mermaid graph with free news and MOPS execution.

- [x] **Step 3: Run focused and full verification**

Run:

```bash
pytest tests/test_news_fetchers.py tests/test_text_extractor.py tests/test_official_financials.py tests/test_external_data_client.py tests/test_provider_workflow.py tests/test_data_cross_validator.py -q
scripts/ci_gate.sh
git diff --check
```

Expected: all focused tests pass; full gate reports zero failures; diff check is silent.

- [x] **Step 4: Audit every objective requirement**

Confirm each requested public function exists, standard news keys are exact, timeouts are covered, MOPS POST and parsing are tested, warning logs identify fallback layers, Pipeline receives free data, Blackboard receives official values, and unresolved official conflicts remain fail-closed. Mark every plan checkbox complete only after its evidence exists.

- [x] **Step 5: Commit**

```bash
git add tests/live/test_free_external_data_smoke.py docs/operator-guide.md docs/architecture.md docs/superpowers/plans/2026-06-19-free-external-data-waterfall.md
git commit -m "docs: document free external data waterfall"
```
