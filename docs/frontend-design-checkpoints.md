# Frontend Design Checkpoints

更新時間：2026-07-04

本文件紀錄前端介面優化的最低驗收基準。它不是設計系統，而是每次調整工作台 UI 前後都要核對的證據清單。

## 目前基準

- 主要介面類型：資料密集型 App UI。
- 主要受眾：本機操作者、研究流程維護者、需要快速判斷報告可信度的投資研究使用者。
- 主要任務：輸入股票代號、選擇分析模式、查看任務/資料/LLM 健康、檢查歷史報告與決策追蹤。
- 最新設計審查 artifact：`~/.gstack/projects/aibalbo999-unstuck/designs/design-audit-20260704-065346/`

## 必檢問題

1. 第一屏是否能在 3 秒內看出「輸入、模式、開始分析」三件事。
2. 所有主要操作是否有至少 44px 的可點擊高度。
3. 主要 CTA 的文字對比是否達到 WCAG AA，不能只靠亮色吸引注意。
4. 決策追蹤、目標價、資料信任狀態是否能用文字和版面讀懂，不能只靠顏色。
5. Mobile 是否沒有水平捲動，且資料卡不會壓成難讀的小格。
6. 每次 UI 修改是否有對應測試、截圖或 DOM 量測。
7. 模式名稱、用途、CTA、watchlist 顯示與報告模板是否符合 `docs/pipeline-mode-contract.md`。

## 已建立的合約測試

- `test_home_tabs_present_three_even_desktop_choices`
- `test_primary_cta_has_readable_contrast_on_cyan_action_background`
- `test_history_version_toggle_checkbox_is_visually_legible`
- `test_decision_tracking_mobile_cards_prioritize_readable_single_column_data`
- `test_pipeline_mode_frontend_labels_share_single_metadata_source`
- `test_pipeline_mode_contract_documents_templates_and_decision_intents`

## 下一個高價值檢查點

- 將 `docs/pipeline-mode-contract.md` 納入 PR/release 檢查，降低使用者選錯模式與報告模板漂移的機率。
- 將設計審查 artifact 的截圖摘要納入 release / PR 說明。
- 評估是否建立正式 `DESIGN.md`，把字級、色彩、密度與資料視覺化規則寫成專案基準。
