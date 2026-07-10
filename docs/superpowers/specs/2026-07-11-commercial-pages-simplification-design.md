# 商業版三頁簡化設計

日期：2026-07-11
狀態：待使用者審閱

## 摘要

商業版保留「今日決策、單股研究、組合健檢」三個獨立網址，但全面改用相同的任務結構：先回答使用者最關心的問題，再顯示必要證據，最後提供唯一下一步。

本次不是替現有頁面換皮，而是移除重複模組、假動作與不必要的互動。只有能觸發真實 API、明確導覽或立即可見狀態變更的元素，才可呈現為按鈕。

## 現況證據

目前 1280 × 720 runtime 畫面的初始 DOM 密度如下：

| 頁面 | 按鈕總數 | 同時可見按鈕 | 區塊數 | 頁面高度 |
| --- | ---: | ---: | ---: | ---: |
| 研究工作台 | 133 | 111 | 110 | 8,945 px |
| 單股研究 | 26 | 26 | 98 | 4,378 px |
| 組合健檢 | 751 | 270 | 86 | 7,019 px |

前端共使用超過 500 種 `data-*` 互動屬性，但實際商業版資料請求只有少數主要路徑：

- `GET /api/decision-tracking`
- `GET /api/stocks/{ticker}/snapshot`
- `POST /api/watchlist/portfolio/risk`
- `GET /api/client-config`，供 mutation token 使用

大量控制只做同頁捲動、複製文字或寫入 `localStorage`，卻與真正資料更新使用相同按鈕外觀。這造成使用者無法預測點擊結果，也無法確認動作是否成功。

## 目標

1. 使用者進入商業版後，五秒內能知道今天先處理什麼。
2. 三頁各自只服務一個主要任務，首屏只保留一個主要 CTA。
3. 所有按鈕都有可驗證結果與載入、成功、失敗回饋。
4. 進階資料仍可取得，但透過分頁或「更多」漸進揭露。
5. 保留現有 API、mutation token、三頁網址與 ticker query。
6. 手機、鍵盤與螢幕閱讀器使用者能完成相同核心任務。

## 非目標

- 不在本次新增新的股票、報告或投資組合 API。
- 不在商業版模擬尚未存在的後端功能。
- 不把營運維護、provider SLA 或內部診斷功能搬進商業版。
- 不保留現有模組，只為了通過以 selector 數量為主的舊測試。

## 採用方案

採用「三頁保留，任務入口統一」。

相較於合併成單一 SPA，此方案能保留深連結、瀏覽器返回行為與既有資料流，實作風險較低。相較於三步精靈，它也保留熟練使用者快速跳到單股或組合頁的能力。

全域導覽固定為：

1. 今日決策
2. 單股研究
3. 組合健檢

「主頁」改由品牌連結承擔，不再與三個商業任務並列成第四個同級選項。

## 共享頁面模型

每頁依固定順序呈現：

1. `PageAnswer`：一句話回答目前最重要的問題。
2. `EvidenceSummary`：最多三到四個必要證據。
3. `PrimaryAction`：唯一主要 CTA。
4. `DetailTabs`：進階內容，預設只展開第一個分頁。
5. `SourceStatus`：資料來源、更新時間與失敗狀態。
6. `MoreActions`：複製、下載、儲存等次級操作。

頁面不得在 `PageAnswer` 前插入摘要雷達、比較鏡頭、自訂視圖、設定教練或重複的快捷動作列。

## 頁面一：今日決策

### 核心問題

今天應先處理哪些股票？

### 首屏

- 標題：`今天有 N 件事要處理`
- 說明：依風險、資料時效與需重跑狀態排序
- 任務列：最多三筆，包含 ticker、原因與單一狀態
- 主要 CTA：`開始檢查 {ticker}`
- 次級連結：`查看全部追蹤股票`

任務列本身使用可深連結的 `<a>`，不是沒有語意的整卡按鈕。

### 資料流

1. 載入 `GET /api/decision-tracking`。
2. 將 `requires_rerun`、錯誤狀態、負報酬與更新時間轉成單一優先序。
3. 點擊主要 CTA 後導覽至：

   `/static/commercial/stock-detail.html?ticker={ticker}&from=decision`

4. 不在此頁重複呈現完整股票快照、熱力圖、報告工作室或組合資料。

### 空狀態

顯示 `尚無追蹤股票`，並提供前往既有追蹤設定的單一連結。不得改用範例股票填滿畫面。

## 頁面二：單股研究

### 核心問題

這檔股票目前值得買入、持有、觀察或避開嗎？

### 首屏

- ticker 搜尋輸入
- 一句話結論
- 資料信心、現價、估值狀態、下一事件
- 支持證據與主要風險各一到三條
- 主要 CTA：`更新股票快照`

### 進階內容

只保留四個分頁：

1. 結論
2. 基本面
3. 事件
4. 技術

現有 AI 報告、財務估值、分析師、論點、持有人與新聞等模組，必須映射到上述四類，而不是繼續成為八個同級分頁。

### 資料流

1. 由 URL `ticker` 或輸入欄取得股票代號。
2. 載入 `GET /api/stocks/{ticker}/snapshot`。
3. 成功後更新結論、指標、來源與時間。
4. 更新期間保留舊資料或骨架，主要 CTA 顯示進度並停用。

### 錯誤狀態

- 400：顯示 ticker 格式錯誤。
- 502 或資料來源失敗：保留上一次成功資料，標記為過期並提供 `重試`。
- 沒有上一次成功資料：顯示明確空白錯誤畫面。
- 不得靜默切換為 `fallbackTickers` 或範例快照。

## 頁面三：組合健檢

### 核心問題

目前組合最大的風險是什麼，下一步應如何調整？

### 首屏

- 持股 CSV 輸入或既有持股摘要
- 組合健康度
- 集中度與最大部位
- 最多三項按重要性排序的調整建議
- 主要 CTA：`產生調整建議`

### 進階內容

只保留三個次級分頁：

1. 曝險
2. 情境
3. 貢獻

匯出與客戶包放入 `MoreActions`。Income、Balanced、Growth、Trim、Cash 等模型只在對應分頁內出現，不占用首屏。

### 資料流

1. 在前端先驗證 CSV 必要欄位與每列格式。
2. 使用 mutation token 呼叫 `POST /api/watchlist/portfolio/risk`。
3. 成功後更新健康度、風險與建議。
4. 400 時直接標示問題列與修正方法。
5. 其他失敗顯示重試，不得換成 `fallbackPortfolio`。

## 按鈕與互動契約

### 類型

| 類型 | 用途 | 樣式 |
| --- | --- | --- |
| Primary | 每頁唯一核心任務 | 實色、最高對比 |
| Secondary | 最多三個必要輔助動作 | 外框或文字按鈕 |
| Navigation | 跨頁或分頁切換 | `<a>` 或正確的 tab semantics |
| More | 複製、下載、儲存 | 單一 overflow menu |
| Metric | 純資料展示 | 不可有 button role、hover 或 pointer cursor |

### 結果要求

任何按鈕至少符合一項：

- 產生可觀察的網路請求並更新資料。
- 導覽到可驗證的網址或分頁。
- 立即改變可見狀態，並以 `aria-live` 說明結果。

只捲動到同一頁相似模組、只寫 `localStorage` 或只改一段不明顯文字，都不得作為主要或次級按鈕。

### 回饋

- 非同步按鈕在 100 ms 內顯示按壓或載入回饋。
- 載入期間停用，避免重複提交。
- 成功狀態顯示更新內容、資料來源與時間。
- 失敗狀態說明原因及恢復方法。
- 所有互動目標至少 44 × 44 px。

## Demo 與真實資料界線

正式頁面只顯示真實 API 結果、明確的空狀態或錯誤狀態。

若仍需保留示範資料，必須同時符合：

1. 僅在明確 `?demo=1` 或專用 Demo 入口啟用。
2. 頁首持續顯示 `示範資料` banner。
3. 不使用 `Live data`、`已更新` 或任何可能被理解為真實狀態的文案。
4. 示範按鈕不得呼叫真實 mutation API。

## 前端模組邊界

目前單一 `commercial_pages.js` 超過 23,000 行，`commercial_pages.css` 超過 24,000 行。實作時應改成無建置步驟的頁面模組：

```text
backend/static/commercial/
├── research-workbench.html
├── stock-detail.html
├── portfolio-dashboard.html
├── shared/
│   ├── api.js
│   ├── async_state.js
│   ├── shell.js
│   └── source_status.js
├── pages/
│   ├── decision_page.js
│   ├── stock_page.js
│   └── portfolio_page.js
└── styles/
    ├── tokens.css
    ├── shell.css
    ├── components.css
    └── responsive.css
```

每個頁面 Module 只負責該頁 state 與資料映射，共用 Module 不知道特定頁面 DOM ID。API route 不需修改。

## 響應式與無障礙

- 桌面內容最大寬度 1,200 px，首屏不得使用四到五欄資訊牆。
- 375 px 手機改為單欄，主要 CTA 固定在內容流中，不使用遮住內容的底部動作列。
- 導覽在小螢幕仍保留三個文字標籤，不用無標籤圖示。
- tab 使用 `role="tablist"`、`role="tab"`、`aria-selected` 與鍵盤左右鍵。
- 請求錯誤使用 `role="alert"`，成功更新使用 `aria-live="polite"`。
- focus ring 不得移除；路由或內容切換後 focus 移至頁面標題。
- 顏色不得是唯一狀態訊號。

## 驗證策略

### 靜態契約

- 每頁首屏只有一個 `.is-primary` CTA。
- 初始可見 `<button>` 不超過 12 個；全域導覽連結不計入。
- 指標卡不得有 `button` role 或 `cursor: pointer`。
- 正式頁面不得在 API 失敗後渲染 fallback sample。
- 三頁載入各自的 page module，不再共同載入單一巨大頁面實作。

### 瀏覽器行為

1. 今日決策成功載入真實追蹤清單。
2. 今日決策空資料時顯示設定入口，不顯示範例股票。
3. 點擊第一項任務會導覽至正確 ticker 的單股頁。
4. 單股快照載入成功、錯誤、重試與 loading disabled 狀態均可重現。
5. 組合 CSV 有效時送出一次 POST；無效時不送出並定位錯誤列。
6. 每個可見按鈕皆造成網路、導覽或可見狀態變化。
7. 375、768、1280 px 無水平捲動，主要答案在首屏可見。
8. 鍵盤能依序完成三頁核心任務。

### 既有後端回歸

前端變更不得改變三個既有 API 契約。實作驗證至少包含：

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_frontend_http_e2e.py \
  tests/test_stock_snapshot.py \
  tests/test_portfolio_risk.py \
  tests/test_decision_tracking_workflow.py \
  -q
```

## 驗收標準

1. 三頁各只有一個明確主要任務與一個主要 CTA。
2. 1280 × 720 首屏直接看得到答案與下一步，不需先捲動。
3. 初始可見按鈕每頁不超過 12 個。
4. 所有可見按鈕通過自動或人工 click audit。
5. API 失敗不會顯示未標示的範例資料。
6. 深連結、瀏覽器返回、ticker query 與 mutation token 正常。
7. 375 px 與 1280 px 均無水平捲動，觸控目標和鍵盤 focus 合格。
8. 商業版 focused tests 與相關後端回歸全部通過。

## 移除清單

實作時預設移除下列首屏或重複模組，除非它們能明確映射到三頁的新次級分頁：

- 重複的 primary snapshot、answer、compare、customize strips
- command map、jump deck、action dock、mobile dock 的重複入口
- decision radar、visual pulse、technical pulse、coverage matrix 等同義摘要
- setup coach、onboarding beacon、progress coach 的多套上手流程
- report locator、report studio、report composer 的多套報告入口
- 各模組重複的 Copy、Save、Export 按鈕
- 未接 API 的 Add to Watchlist、Save Mission、Apply Template 等動作

如果功能仍有價值，先保留資料定義與對應後端能力，待後續獨立規格重新加入；本次不可因為「已經寫了」而保留在使用者介面。
