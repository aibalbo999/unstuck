# 四模式內容可信度第一批交付紀錄

核准依據：`docs/superpowers/specs/2026-09-06-analysis-credibility-followup-design.md`。
執行計畫：`docs/superpowers/plans/2026-09-06-analysis-credibility-followup-plan.md`。

目前狀態：第一批程式、獨立 spec／quality 審查及完整隔離回歸已完成；本紀錄不代表已正式發布。

## 本批變更

- 原始股數、金額與現金流使用具單位的金融輸入契約，DCF／WACC／本益比各自記錄可用性；必要事實缺失或負 FCF 不產出占位 DCF。提示、稽核與報表共用同一計算來源。
- 修復依照四模式的實際群組依賴安排。上游內容改變才重建受影響下游，整輪通過才原子採用；同步、非同步、checkpoint、typed state、RAG 與快取保留一致語意。取消、deferred 或下游未完成不發布半套結果。
- A／B／C 最終市場與新聞評估只能引用最後提示內容完整可見的來源。缺資料／未評估與假引用分級處理，重試次數有界；只重跑最終建議也適用，不能暗中更正前序分析。
- 明示 SMA 只匹配自身 canonical 期間欄位；最終建議列的 compact 3／6／12 個月只匹配各自保存欄位。過熱評分仍是分析判斷，真 mismatch、缺資料與不確定性不改成 verified。

## 驗證方式與已取得證據

所有 pytest 經 `tests/run_prompt_boundary_tests.py`，使用臨時 SQLite／memory cache 並封鎖 Python 網路；沒有呼叫正式分析重跑 API。

- 基線：7 個高風險檔案，57 passed。
- 量化／證據的六項獨立審查發現已有對應回歸並複審通過。
- 修復依賴／局部最終重跑的群組、原子性、阻擋狀態往返及發布閘門已完成獨立 spec 與 quality review。
- 唯讀 artifact replay：1623 A、1623 D、2308 C 三組共 9 個 Markdown／HTML／snapshot 檔案，前後 SHA-256 相同；負 FCF 不產生 DCF／安全邊際，D 的 205.4 匹配 SMA20，C 的 6 個月 1380 匹配自身目標。分析信心仍不可驗證。
- 快照與刷新：裁切保存原始主張，不將清理過的顯示投影重新當證據；保存憑據不可跨資料刷新借用。已經真實 refresh service 的臨時儲存路徑驗證，完成獨立複審。
- 第一輪完整回歸：12 failed、9,654 passed、21 skipped、75 subtests passed，耗時 1,082.74 秒。10 個失敗來自量化新增入口的自訂 mapping accessor 相容性，另 1 個為 legacy 新增空 metadata，1 個為來源檔契約詞統計待同步；均已取得 RED→GREEN 與相關複驗。
- 定版完整回歸：由 pytest 收集 276 檔、9,737 項，檔名排序後依 index modulo 4 分成四組（各 69 檔），每組使用獨立隔離 runner。所有收集檔恰好執行一次，總計 **9,716 passed、21 skipped、75 subtests passed**，沒有失敗；通過與跳過合計等於收集總數。

| 組別 | Passed | Skipped | 耗時（秒） |
| --- | ---: | ---: | ---: |
| 1 | 2,487 | 6 | 247.01 |
| 2 | 3,437 | 3 | 496.93 |
| 3 | 2,876 | 11 | 279.10 |
| 4 | 916 | 1 | 82.45 |

21 個跳過項目為：live provider／公開外部資料 4、真實瀏覽器／Chart.js 14、Redis worker 1、需明確指定離線 checkpoint 1、需明確指定 artifact 目錄 1。最後一項另外 opt-in 重跑 **1 passed**，並再次確認 9 個原始檔案雜湊不變。75 subtests 在第 4 組通過；第 1 組有 2 個既有公開 legacy facade deprecated 警告，不是測試失敗。未將 skip、fake PostgreSQL 或無網路測試當成 live 驗收。

上述 replay 使用保存資料，不是 live 模型生成，也不是樣本外績效驗證；不同抽樣範圍的 gate 數字不作改善百分比。

## 發布與後續邊界

| 項目 | 本批狀態 |
| --- | --- |
| 程式、測試與審查 | 第一批完成，9,716 passed／21 skipped；獨立 spec 與 quality review 通過 |
| Git | 專用分支 `codex/analysis-credibility-spec`；本紀錄隨 scoped 實作提交交付，不 push／merge |
| 正式 API／Worker | 未重啟，未宣稱已載入新程式 |
| 正式資料、報告與設定 | 未改寫 `.env`、正式 DB、既有報告、模型路由、RPD／cooldown |
| 歷史報告 | 未重新產製；49 組最新版或 102 份全量重建仍待另定範圍 |
| PostgreSQL | 未安裝或 live 驗收；fake／optional tests 不等於 live 通過 |
| 投資效果 | 未執行樣本外（OOS）績效研究，無績效提升承諾 |

本批的跨模組接線共同構成來源可信度與發布邊界，最後以一個已驗證的 scoped 實作提交交付，不把相互依賴的中間狀態拆成可發布版本。設計／計畫的前置提交另行保留。

## 2026-09-07 後續驗證追加

- 既有代表 artifact（1623 A、1623 D、2308 C）以目前 host renderer 做 1280／375 兩種 viewport 的唯讀 QA；六組均通過圖表／layout、tooltip 與 zero errors。對應 HTML／Markdown／snapshot 均可由 `/api/reports` 下載，HTML header 的 CSP、`X-Content-Type-Options` 與 content-type 檢查通過。
- 受影響的 OOS／artifact replay／四模式 scoped lane 為 `170 passed`；OOS 合成與隔離 bundle 契約為 `18 passed`；另既有模式回歸 `154 passed`。這些結果證明目前 checkout 的工程與保存 artifact 行為，不代表已重啟的正式 API／Worker 已載入本分支。
- 唯讀候選盤點見[正式報告更新候選清單](report-update-candidate-inventory-2026-09-07.md)：indexed reports 共 `148`（`current=109`、`needs_rerun=39`），完整排序清單 hash 為 `0e870f7451506bdcccfd7753191a6661766d4db4774102aca5bf5c5d8c2417cd`。尚未核定更新範圍、送出 Job、重啟服務或改寫正式 artifacts。
