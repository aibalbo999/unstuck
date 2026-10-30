# 2026-10-27 隔離修復與交付紀錄

V2 四項獨立審查修復與重新驗收見 [market-evidence-repair-v2-20261027.md](market-evidence-repair-v2-20261027.md)。下列整合數字與交付紀錄屬 V1；原紀錄保留。

本次授權是隔離實作與驗證。正式部署、重啟、掃描、付費模型、正式報告重新產生、固定 76 回填及交易均未執行。

## 工作區與基線

- 隔離工作區：`/Users/balbomacmini/Documents/Codex/2026-10-27/task/stock-agent-isolated`
- 隔離分支：`codex/market-evidence-integrity`
- 隔離基線提交：`65163dd`，是正式目錄當時程式狀態的快照，包含其既有未提交變更；不是從舊 HEAD 丟棄變更重建。
- 原目錄 HEAD：`7e85593b7435b871afd9e656f59792fee19f1403`。
- 複製 4,289 個程式／測試／說明檔；排除正式資料庫、執行狀態、報告、憑證及大量歷史原件。
- 讀回比對 4,289 檔內容均未變，正式 API 仍為 PID 76939。這是本次對正式程式的保護證據，不代表原有輪詢停止或整個資料庫沒有自然更新。

## 實際改善

1. 官方年度日曆與有日期、範圍的臨時休市例外分開。TWSE [10/23](https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d6a0fa351b01a1638507940202.pdf)與[7/10](https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d69ef76943019f46cb86ae0110.pdf)颱風休市都有官方 PDF；TPEX 未取得獨立正文，保留未知。後者是整合測試新增缺日檢查揭露的真實日曆漏列，沒有修改四項原測試或保存資料來消除失敗。
2. 日線逐筆檢查交易日、順序、重複、as-of 與窗口缺日，先准入再取 120 筆。合法零量保留；未知列隔離後仍維持缺證，不得刪掉後升級。
3. 技術驗算分開 arithmetic_status、session admission 與來源/PIT 範圍。相同輸入重算及 hash 一致不能替代交易日或價格真實性；原數值矛盾仍維持 mismatch。
4. 行情與法人各自按觀測日和取得階段檢查快取。公布資料可以先取得、標成 provisional，但 22:30 是保守重新核對界線，不能用時間前進升級舊原件。
5. 保存引用改用當時已綁定的 frozen input、manifest、輸出 fingerprint；檢查跨股票／跨市場身分，再另判目前時效。缺完整憑據維持 unknown，不拿今天資料補歷史證據。
6. 看板列出股票×流程最新版分母、今日／較舊群組、可重疊警示與原因分類；分類明示不等於根因判定。FCF 精確分開選用的官方欄位、保存 quote 與年度序列，沒有替 raw scalar 補造期別。
7. 新增純預覽與重建前置檢查；完整、最終及 checkpoint 重跑都不能繞過交易日／身分准入。新版本使用 UUID，若已有任一 artifact 或等於來源檔名即拒絕覆寫；不使用秒級檔名當唯一識別。

## 可獨立複核的測試

在工作區執行：

```bash
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' scripts/validate_market_evidence_isolated.py
```

實際模組清單在 `market-evidence-validation-tests.json`。此入口固定呼叫 `tests/run_prompt_boundary_tests.py`，隔離 SQLite 並禁止 runtime、Redis、供應商網路。結果以 `market-evidence-validation.log` 與 `market-evidence-validation-result.json` 的最後固定版本為準，不能把分組測試次數相加。

最終整合：**49 個模組、769 passed（pytest 15.19 秒）**，執行時間 2026-10-27 22:53:21 至 22:53:38 Asia/Taipei，測試期間程式檔沒有變動。測試樹 SHA-256：`500e2de54aa0a8060061b0b5e0accf65087f1a0537f510ff57d62727db95130c`。前一次 762 passed／6 failed 的完整紀錄另保存在 `market-evidence-validation-attempt1.log`，四項由 7/10 官方休市例外解決、兩項修正測試重複傳入日期參數；未刪除矛盾檢查。

獨立覆核找到並修復六項問題：重建身分缺漏、版本檔名碰撞、異常 JSON、特殊開市與法人窗口不一致、跨股票來源拼接、截止後外層快取仍沿用暫定行情。看板變更由前端契約測試覆蓋，沒有在正式網頁部署驗收。

兩個既有 1301 歷史 fixture 因原隔離複製排除 `docs/evidence`，後來僅為既有回歸補入，**不放入交付程式補丁**：

- `docs/evidence/source-acquisition/20261014/remaining-gaps-after-cht/institutional-recovery/1301.TW/before.data.json`，SHA-256 `d54888de7af913fb66614a5f3efab712247f1487513590ccf59c134b071587a8`。
- `docs/evidence/source-acquisition/20261014/remaining-gaps-after-cht/refresh-metadata-repair/author/actual-after.data.json`，SHA-256 `aa88077be851c96dd83227f9fda86247646d772472bf68d447cfade9d43905a0`。

## 非持久化比較

`rebuild-preview-20261027.json` 包含今天 21 個實體報告版本的 hash 綁定預覽；63 個原 artifact 比較前後一致，沒有寫回。原 209 最新版的來源缺口另見 `audit-source-gap-20261027.md` 及 before/after JSON。

2356 移除已證 10/23 休市列後，SMA5 約 61.06 → 60.78、SMA10 約 59.66 → 59.42、MACD histogram 約 0.63844 → 0.65125、20 日量比約 2.885 → 2.747。這些是保存輸入的反事實算術比較，不是完整新來源查證或新投資結論。

12 份移除錯誤列後行情只到 10/22，9 份到 10/27；日期正確不表示法人、量能口徑、公司行動、FCF 或來源證據全部通過。0 passed 不能以刪警示或放寬門檻修成全綠。

單份唯讀預覽命令：

```bash
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' scripts/preview_market_evidence_rebuild.py --output-dir '/Volumes/X10 Pro Mac/stock-agent/backend/output' --filename 2356_TW_v4_report_job_73ad34c6f955.html --at '2026-10-27T22:39:35+08:00'
```

`--at` 是明示的評估時點，重做目前計畫時應換成實際有時區的時間。預覽兩小時失效、內容／來源 hash 或日曆准入改變即需重建。CLI 沒有 apply／execute 選項，預檢通過也不授予執行權。

## 後續正式重建與風險

部署前需確認正式程式仍與隔離基線相容、先審查補丁，再核准部署／重啟。正式資料重建另核准明確報告清單與模型成本；用新 job、完整取數、完整分析及新版本，不沿用污染 checkpoint、不覆寫舊報告、不自行改固定 76。原品質與發佈門檻照常執行；驗收成功的定義是證據與語義一致，不是全部 209 passed。

限制：本次沒有實際供應商取得或正式 22:30 後流程驗收；歷史原件、PIT、價格調整與年度 FCF 的全面獨立事實查核仍未完成。缺日檢查限窗口首末日間最多 370 日；個股停牌缺日沒有獨立證據准入器，仍 unverifiable。官方臨時日曆例外具來源支援，但未新增自動抓公告或排程。

實際阻擋：`web.open https://www.tpex.org.tw/` 回應 HTTP 403 Forbidden，已停止該動作，沒有繞過；不影響 TWSE 已有官方休市證據。正式服務與資料的執行動作依授權邊界保留，並非逾時失敗。
