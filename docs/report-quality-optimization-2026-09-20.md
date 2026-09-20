# 報告品質修正與重稽核（2026-09-20）

本次修正處理日期／分析評分誤入財務抽樣、Agent 19 截斷與不開倉契約，以及已重新驗證的問題仍被歷史 projection 保留的情況。原品質閘門、來源全文、provider 限流與每份工作的修復次數上限不變。

## 行為

- `evidence_claim_types.py` 僅排除有明確日期欄位、有效日曆值且沒有金融單位的 compact 日期。評分與財務數字分開，評分驗證有限值、量尺與範圍；量尺不明或無效仍 caution。Schema 2 的 `claim_count`／`sampled_count`／`verified_count` 只計財務證據；`metadata_*` 獨立計數且不填補財務抽樣分母。原 seed、抽樣比例與 1% 容差不變；修正母體後實際抽樣集合可能改變。
- Agent 19 保留 6144、Agent 18 保留 4096 output token 上限，指定 Google 路由改用 low thinking，完整 JSON 與必要證據優先，縮減重複敘述；修復提示回傳明確 v3 合約問題。未通過的候選評估不移入已接受結果。Agent 19 的四種安全 enum 加入語意與既有報酬門檻說明，提醒各期目標與結論一致，禁止為過關補造價格。
- Google 的結構化安全 enum 在明確模型身分的 response 邊界逆映射；修正「買入 → 偏多觀察 → 持有」錯誤。全域自然語言 alias 與正文不改寫。「中性觀察」原本就是合法映射，並非 5314 失敗原因。
- schema 明確為 0–1 的管理層／下行風險信心，在系統產生的文字標示量尺，保留原數值；自由正文不推測量尺。
- 僅原始 v3「避免」、明確不開倉、無目標與交易／既有部位矛盾的契約，目標價方向檢查才為 `not_applicable`。這不表示市場評估、來源或分析完整性通過。
- current-rule projection 只解除已明確重驗解決的歷史 finding；未知問題、未解釋的歷史嚴重度及本輪新問題保留。conformance 使用已合併的 content credibility，避免不同卡片互相矛盾。原 snapshot、Markdown 與 HTML 保留歷史結果，不重寫成成功。

- 真實 5314 canary 暴露系統觀望模板被自身交易指令檢查拒絕，及股／張數被當進場價。模板改用明確等待重新評估文字；價格解析排除明示股票數量，缺價格仍回報缺價格，多分支／矛盾價位不放行。
- Agent 7／16／18／19／20／21 的 step cache 加輸出契約版本，避免重用本次修正前已正規化的錯誤輸出；其他角色鍵不變，不清除任何快取。

## 驗證邊界

隔離測試使用 `tests/run_prompt_boundary_tests.py`，不得連正式 Redis／API／模型。原始 140 份最新報告與 653 份版本清單在發布證據目錄保存；重稽核走唯讀 index mapper。真實模型 canary 與正式重跑另行記錄，保留包含 503、重試、降級與品質未過的完整分母。

發布證據：`/Volumes/X10 Pro Mac/stock-report-quality-release-20260920.kskpgl8k`。最終測試、正式版本、重稽核比較與模型驗證結果以該目錄 `DELIVERY.md` 為準；本文不把程式修改當成正式服務成功證據。
