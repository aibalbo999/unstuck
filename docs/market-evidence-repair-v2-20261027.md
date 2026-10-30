# 2026-10-27 V2：四項獨立審查缺陷修復

狀態：隔離實作與固定版本驗收完成，可交同一審查線重新複核。尚未部署或執行正式資料重建；測試通過不授予這些執行權。

## 範圍與版本

- 工作區：`/Users/balbomacmini/Documents/Codex/2026-10-27/task/stock-agent-isolated`
- 分支：`codex/market-evidence-integrity`
- 原始隔離基線：`65163dddcac498836c26999418b4fb1b6b294a8c`。
- V1：`4adf13d4a08d0ecf125739ad6c62412d7179ab3a`；原補丁 SHA-256 `61c22b94d190c20a7fb9ca986dac6e5b89e9817f825120ce562182f8331bb098` 保留。
- V2 完整替代補丁與僅 V1→V2 增量補丁、提交及 SHA-256，列在工作區外 `../market-evidence-delivery-v2.json`。兩份補丁擇一依基線使用，不能重複套用。

原獨立檔完整複製為 `tests/test_independent_market_review.py`，與審查來源逐位元相同。SHA-256：`83765d06798e8f99f5df979cc95fb3844eea742300e750aa386eb342646e0312`。修復前原樣重現 **12 passed／4 failed**，紀錄為 `independent-review-v2-before.log`；沒有改掉反例或其斷言。

## 四項修正

| 缺陷 | V2 行為 | 作者回歸 |
| --- | --- | --- |
| 同日 61／99 被 last-write-wins 覆蓋 | 在去重前分組，衝突日期的所有有效候選都排除，保存候選數值與缺來源選擇證據理由。相同有效 OHLCV 可去重，合法零量保留；同日混有無效列也不能讓另一列自動成真。 | `test_session_projection_conflicts.py`：排列順序、兩端日期、無效同日列、yfinance 路徑。 |
| 不可解析的 quarantine 日期在投影消失 | 容器、列、日期無法解析都保留穩定缺證診斷。再次投影仍不合格、指標 sample_count=0；不修改輸入。 | 同檔：異常容器／列／日期、多次投影、偽造 resolved／verified 標記。 |
| TPEx readiness 借用 TWSE 日曆 | 四個逐檔消費路徑傳遞 ticker；readiness 缺市場身分也維持未知。內層 yfinance gate 同樣傳 ticker。 | `test_readiness_market_identity.py`：TWSE 正例、TPEx 臨時日曆缺證、缺 ticker、候選與報告路徑。 |
| 截止後外層快取短路法人重取 | post_cutoff 重新以法人原件、股票／市場／日期與原始取得時間准入。失敗標單項 stale，價格仍有效時沿既有局部 recovery；不拿 aggregate 時鐘或舊 eligible 代替原件。恢復失敗保留原值／原時鐘及節流。 | `test_institutional_cache_receipt_admission.py`：15 案涵蓋缺證、毀損、身分／日期錯、未來時鐘、截止前後、恢復成功／失敗。 |

兩處舊正例 fixture 也修正其明確前提：readiness 正例加入 `2330.TW` 身分；22:31 的行情快取正例把原先未來 22:45 法人原件改為已取得的 22:30:30。保留原斷言；另有缺身分與未來原件的反例，沒有以這些 fixture 改動掩蓋獨立失敗。

## 固定版本驗收

| 批次 | 結果 | 紀錄 |
| --- | --- | --- |
| V1 原固定 49 模組清單，檔案內容未變 | **769 passed，12.86 秒** | `market-evidence-validation-v2.log` / `market-evidence-validation-v2-result.json` |
| V2 三個作者新增模組 | **39 passed，1.84 秒** | `author-v2.log` |
| 未修改的獨立驗收檔全部 | **16 passed，2.68 秒** | `independent-review-v2-after.log` |
| 四個指定原始反例 | **4 passed，12 deselected，1.44 秒** | `independent-four-v2.log` |

以上批次有重疊，不加總成總測試數。原 V1 的 769 passed 與 V1 的獨立 12/4 結果均保留，不以新版覆蓋。固定整合於 **23:23:31–23:23:45 Asia/Taipei** 執行；2,547 個程式／測試檔在測試期間沒有改變，測試樹 SHA-256 `b99d90d930aa9cc147aa121f63af8f9ed584db579bc566b13c9a259716a6811f`。此 tree hash 的範圍見結果 JSON，不等同交付補丁 hash。

另由未實作這四項的審查代理讀碼與重跑反例，限定本四項未找到可重現的未修缺陷；完整外部審查線仍需重驗。所有測試經專案強制 boundary runner，SQLite 在臨時目錄、memory cache、禁止 runtime／Redis／供應商網路。

在本工作區複核：

```sh
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' scripts/validate_market_evidence_isolated.py
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_session_projection_conflicts.py tests/test_readiness_market_identity.py tests/test_institutional_cache_receipt_admission.py -q
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_independent_market_review.py -q
PYTHONDONTWRITEBYTECODE=1 '/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python' tests/run_prompt_boundary_tests.py tests/test_independent_market_review.py -k 'conflicting_duplicate_must_not_become_admitted_after_normalization or invalid_quarantine_must_survive_context_projection or tpex_readiness_must_use_tpex_calendar_scope or post_cutoff_workflow_must_recheck_provisional_institutional_receipt' -q
```

獨立檔最後一項唯讀正式 21 份原件，輸出本地 `../evidence/preview-readback-independent.json`。另一副本需先建立自身 `../evidence` 目錄。固定 49 模組仍需要 V1 文件列出的兩份已驗 hash 歷史 fixture；它們沒有納入補丁，不能把缺 fixture 的結果當程式通過。

## 非持久化比較與正式保全

23:23:14 Asia/Taipei 重新產生 `rebuild-preview-20261027.json`；V1 另存 `rebuild-preview-20261027-v1.json`。讀取的是原來明確選定的 **21 份當日版本**，沒有新增掃描或重新抓資料。63 個原 artifact 的 hash 仍與 V1 完全相同；再由獨立第16項逐欄重播相同計畫。移除已證 10/23 休市列後仍 **12 份至 10/22、9 份至 10/27**，並未升級成全部可推薦或 passed。2356 的算術比較與 V1 相同，沒有新投資結論。

23:24:23 Asia/Taipei 唯讀比對正式基線 4,289 檔：changed=[]、missing=[]，見 `../formal-source-readback-v2.json`。`lsof` 同時仍顯示 PID 76939 監聽 127.0.0.1:8080。這只證明程式／保存檔保全和同一監聽程序；正式 DB 有原輪詢自然更新，不宣稱整個 DB 位元不動或已載入新碼。

正式部署、重啟、付費生成、重跑掃描、正式報告重建、固定 76 回填／重算與交易均未執行。完整／增量補丁僅生成在本任務工作區；正式目錄只做 `git apply --check` 相容性檢查，結果見交付 manifest，未 apply。

## 未核範圍與執行限制

本輪只閉合四項缺陷，不改品質門檻，不重算正式 209 份狀態。仍未驗收真實供應商取得、正式截止後自然流程、全歷史來源／PIT／價格調整／公司行動／個股停牌、瀏覽器視覺、正式新 job 完整重建及固定 76。TPEx 臨時休市正文仍缺證；不借用 TWSE 補值。無 ticker／非台股 generic normalization 與績效／legacy76 整體日期摘要的既有契約本次沒有擴大修改。

已有 TPEx 首頁 HTTP 403 與審查線 `ps` 的沙箱 `operation not permitted` 限制，均未重試、提權或繞過；完整啟動時間／父程序未核。本輪測試、預覽與保全讀取已完成，沒有新拒絕、待決或結果不明寫入。部署及正式重建仍須父線後續明確確認清單、成本與回復方案。
