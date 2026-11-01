# 免費總經原件解析邊界

`backend/free_macro_original_parsers.py` 提供三個無網路、無快取寫入的原件解析器，作為免費來源接入的共用邊界。目前尚未由正式 `MacroIndicatorsProvider` 呼叫；不能因此宣稱已改善正式取得率。

- Cboe `VIX_History.csv`：精確 DATE/OPEN/HIGH/LOW/CLOSE 格式，選 CLOSE；拒絕重複、未來、超過七日與不合法 OHLC。
- BLS `CUSR0000SA0`：季調全項 CPI，精確去年同月計算年增率；最新或去年同月缺值維持不可用，不以別月替代。未註冊 API 每日 25 次限制應在後續傳輸層的共用持久額度防護實作，不得因不同股票重抓。
- Federal Reserve H.15：精確每日、名目、十年期、百分比系列 `RIFLGFCY10_N.B`；拒收實質利率、週資料、錯誤單位、重複日期及過期資料。ZIP 限制輸入 16 MB、解壓總量 85 MB、16 個不重複且未加密成員；不解壓至檔案系統，XML 僅接受 UTF-8，不接受 DTD 或實體。

解析結果保留系列、觀測日期與 `historical_pit_verified=false`。呼叫者仍須核實原始 HTTP 身分、狀態、完整回應、保存 hash/原件與正常快取資格；離線解析結果不是新取得樣本。後續接入須保留既有 FRED 快取與冷卻、逐項 provider 身分、全市場 single-flight、失敗分母和原件重播，品質驗證通過才部署。

公開入口：

- https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
- https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0
- https://www.federalreserve.gov/releases/h15/data/FRB_h15_xml.zip

隔離測試：`scripts/project_exec.sh "$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py tests/test_free_macro_original_parsers.py tests/test_macro_fetcher.py -q`。
