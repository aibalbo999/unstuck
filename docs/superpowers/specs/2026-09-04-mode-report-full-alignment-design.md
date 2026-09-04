# 四模式報告完整適配設計

## 目標

讓 `v1`、`v2`、`v3`、`v4` 的分析模組、結構化輸出、HTML/Markdown 模板與品質閘門使用同一份模式契約。完成後，每個模式不只顯示不同標題，也直接呈現該模式的可執行決策欄位，且不依賴脆弱的正文文字抽取才能填滿模板。

## 設計原則

1. `reporting.mode_templates` 繼續作為模板 profile registry，新增段落 manifest，不建立四套重複 renderer。
2. 資料可信度、來源審計、evidence gate、content credibility 與 conformance 保持共用，模式模板不得自行判定數字是否可信。
3. 模式 B 與模式 C 的執行欄位進入 native structured response schema、normalizer、`parsed` context、final audit 與 renderer。
4. 模式 D 將支撐與壓力從單一目標價拆開，`target_price` 只接受單一可執行目標或明確價格區間。
5. 已保存的舊報告仍可讀，但不會在查看時重新套用新版模板；要取得新版面與原生欄位必須重新產出。新版 renderer 處理舊 context 時，缺少新欄位顯示「資料不足」，不得借用其他欄位或猜測數值。

## 模式契約

### 模式 A：研究型

- 模組來源：財務、護城河、估值、多空辯論與最終建議。
- 專屬摘要：資料可信度、整體護城河、基本情境估值、最終建議。
- 版面：保留結構化分析 overlay 與完整歷史財務圖表。

### 模式 B：實戰交易型

- Agent 16 新增 `position_plan`。
- 欄位：`action`、`entry_zone`、`position_size`、`stop_loss`、`risk_reward`、`invalidation_condition`。
- `action` 只允許「進場、續抱、減碼、等待」。
- 版面：保留估值與財務背景，但專屬摘要優先顯示部位動作與風控，不再只重複 3/12 個月目標。

### 模式 C：逆勢與泡沫狙擊

- Agent 19 新增 `short_setup`。
- 欄位：`entry_trigger`、`downside_target`、`cover_stop`、`squeeze_risk`、`thesis_invalidation`。
- renderer 與 tear sheet 優先讀取結構化欄位；正文標題抽取只保留為舊報告 fallback。
- 版面：保留法證財務背景，專屬摘要直接顯示觸發、目標、停損與軋空風險。

### 模式 D：事件波段

- Agent 24 增加 `support_level` 與 `resistance_level`。
- `target_price` 必須是單一價格或明確區間，不得同時混入支撐與壓力兩個不同情境。
- 專屬摘要顯示方向、進場、目標、停損、催化、風險、支撐與壓力。
- 版面：隱藏長期歷史財務圖表與通用 analysis overlay，維持 1-2 週決策焦點。

## 資料流

`pipeline_modes` 宣告 structured agent -> Google native response schema -> `normalize_structured_output()` -> `structured_outputs` -> `parse_structured_data()` -> `parsed` -> mode focus context -> HTML/Markdown 模板。`final_audit` 在 renderer 前檢查模式必填欄位，`content_credibility` 繼續檢查方向與價位一致性。

## 相容與失敗處理

- 舊版 Agent 16/19/24 context 若重新進入新版 renderer，缺少新欄位時由 schema normalizer 產生明確「資料不足」fallback，避免 renderer 崩潰；既有 HTML/Markdown artifact 不會在查看時重跑 renderer。
- 新生成報告的 prompt 與 response schema 將新欄位列為 required，final audit 對缺漏建立 repair issue。
- 模式 D 多價位但不是區間時列為 final-audit issue，要求 Agent 24 重整，不自動挑選其中一個價格。

## 驗證

- RED/GREEN：structured model、normalizer、parser、final audit、HTML/Markdown mode template。
- 合約回歸：prompt routing、report conformance、golden reports、style/template audit。
- 完整測試：專案全套 pytest。
- Runtime：重啟正式 launcher，確認 health/ready、queue、doctor。
- Live：每個模式至少一份新產物，核對 template marker、預期 agent section、模式欄位與 quality gate；不以舊報告代替新模板證據。
