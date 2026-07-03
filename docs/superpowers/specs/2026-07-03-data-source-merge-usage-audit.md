# 資料來源 merge 與 Agent 使用稽核

## 目標

確認外部資料不是「抓取後閒置」，而是經過可驗證解析、merge、source audit、AgentState/prompt 路由，最後成為 AI 可用的 deterministic context。

## 稽核結論

目前數值與 API 型來源不需要整體改成大型文件處理框架；現行 `ProviderRegistry -> ProviderResult -> merge -> source_audit -> data_trust -> prompt/AgentState` 是合適主線。

需要補強的是文件型來源的標準契約，尤其是 HTML/RSS/news article、MOPS investor conference、SEC EDGAR filings，以及未來 PDF/XBRL/company filing。這些來源必須先轉成 canonical document/context，再交給 merge 和 agent，不可讓 LLM 直接從未解析原文猜結論。

## 每個來源的應用路徑

| Source | Merge target | AI usage path |
| --- | --- | --- |
| `market_data` | `current_price`, `market_cap_raw`, valuation fields | `prompt_builder.market_data`, AgentState normalized financials |
| `financial_statements` | annual history arrays | `prompt_builder.history`, AgentState normalized financials |
| `monthly_revenue` | `recent_monthly_revenue` | prompt JSON monthly revenue |
| `twse_official` | official TTM/cash-flow/margin fields | prompt TTM/cash-flow/balance-sheet derived fields |
| `institutional_trading` | `institutional_trading` | prompt JSON and v4 AgentState |
| `dynamic_peer_metrics` | `dynamic_peer_metrics` | prompt peer context and AgentState peer context |
| `pe_river_chart` | `pe_river_chart` | prompt local valuation context |
| `recent_catalysts` | deduped `recent_catalysts` | prompt market catalysts |
| `peer_discovery` | deduped `peer_discovery_results` | prompt peer search discovery |
| `global_market_context` | `global_market_context` | prompt global market context |
| `international_news_context` | `international_news_context` | prompt international news context |
| `macro_indicators` | `macro_indicators` | Agent 11 prompt context and AgentState macro context |
| `chip_data` | `chip_data` | Agents 15/18/23/24 prompt context and AgentState chip context |
| `alternative_data` | `alternative_data` | Agents 13/14 prompt context and AgentState alternative context |
| `social_sentiment` | `social_sentiment`, `sentiment_context.social_sentiment` | Agent 17 prompt context and AgentState sentiment context |
| `sec_edgar` | `sec_edgar.recent_filings` | Agents 13/14/21 prompt/state context |
| `taiwan_open_data` | `taiwan_open_data` | Agent 11 prompt/state context |
| `earnings_call` | `earnings_call` | Agent 20 prompt context and Agents 20/21 AgentState context |

## Multi-format Document Processing 最小標準

文件型來源新增或重構時，必須符合以下 contract：

1. Detect：記錄 `source_kind`, `content_type`, `url`, `provider`, `fetched_at`。
2. Parse：依格式使用 deterministic parser，輸出 `title`, `text`, `tables`, `metadata`, `published_at`, `source_url`。
3. Normalize：轉成該 source 的 canonical schema，例如 `recent_filings`, `transcript_excerpt`, `items`, `topics`。
4. Provenance：保留 parser 名稱、截斷限制、表格品質、錯誤種類與 record count。
5. Merge：只 merge canonical 欄位；source audit 的 `record_count` 必須能由 merge 後 payload 重新計算。
6. Prompt/State：新增來源必須有測試證明至少一個 agent 能在完整 prompt 或 AgentState view 中看到 sentinel 值。
7. No LLM truth extraction：LLM 可摘要或判讀，但不可作為唯一解析器或唯一 record count 來源。

## 外部參考

- `aibalbo999/stock` 的 `company_filing_loaders.py`, `company_filing_parsers.py`, `company_filing_structured_api_documents.py` 值得借鏡：先處理 HTML/PDF/API rows，再轉成 `NewsDocument` / `CompanyFilingDocument`，且記錄 parser provenance、表格品質與 structured API diagnostics。
- Docling 的模式是多格式解析後輸出 unified document representation，適合未來需要 PDF/XBRL/office 文件時參考。
- Unstructured 的模式是先 partition 成 structured elements，適合文件片段、表格、段落的 downstream pipeline。
- MarkItDown 的模式是把多種 office/web/media 格式轉成 LLM-friendly Markdown，適合輕量 ingestion。
- Apache Tika 的模式是格式偵測、metadata 與 text extraction，適合作為內容類型偵測與基本抽取的參考。

## 驗證要求

本稽核新增/要求的測試重點：

- 所有 pipeline agent 的完整 prompt 必須包含 `財務資料 JSON`、`source_audit_summary`、AgentState view，以及 merge 後 sentinel 資料。
- `source_audit_summary.merged_record_count` 必須由 merge 後 payload 重新計算，而不是相信 provider audit claim。
- 每個 workflow source 必須有 prompt 或 AgentState 可見路徑。
- Optional HTTP merge 必須保留原始 deterministic records，包含 `earnings_call`。
