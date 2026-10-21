# 歷史報告篩選與模式分類

前端選項、報告卡片與模式專屬 API 篩選共用
`backend/report_history_decision.py` 的分類契約。

| 模式 | 篩選欄位 | 可用值 |
|---|---|---|
| A (`v1`) | 研究評級 | 買入、持有、觀望、避免、放空、未知 |
| B (`v2`) | 部位動作 | 進場、續抱、減碼、等待、未知 |
| C (`v3`) | 空方判斷 | 買入、持有、觀望、避免、放空、未知 |
| D (`v4`) | 交易方向 | Long、Short、Neutral、未知 |

各模式保留原本不同的判斷語意：B 的「等待」不等於持有既有部位；
D 的 `Short` 不等於長線研究評級「放空」。缺值保持未知，不能補為
等待或 Neutral。這些分類不代表報告已通過品質檢查或交易可以執行。

## API

`GET /api/reports` 的 `recommendation` 可使用含模式的分類 key：

```text
/api/reports?pipeline=v2&recommendation=v2:等待
/api/reports?pipeline=v4&recommendation=v4:Neutral
/api/reports?pipeline=v4&recommendation=v4:unknown
```

模式專屬選項由 `GET /api/pipeline-modes` 各模式的 `historyFilter` 提供。
每份報告回傳 `history_decision`，包含 `key`、`value`、欄位名稱 `label`
與卡片顯示文字 `display_value`。前端切換模式時，移除不適用的選擇。

既有不含模式的「買入／持有／避免／放空」參數維持舊研究評級查詢相容性；
新前端使用模式專屬 key，避免將研究評級與部位動作混用。

## 目前版本與歷史版本

`include_versions=false` 時，先選每股票、每模式的目前報告，才套用
搜尋、研究評級、模式分類與資料狀態條件。較舊報告符合條件時，不會因此
取代目前版本。`include_versions=true` 才在保留的歷史報告全集中篩選。

資料狀態 `partial` 在選單顯示「資料需留意／來源提醒」，包含真正的資料
缺口及只有來源穩定度提醒的報告；原有品質與來源限制仍保留。

## 驗證與維護

`tests/test_history_mode_filter_contract.py` 覆蓋各模式分類、未知值、觀望與
持有的區別、等待與續抱的區別，以及舊版條件不能回填目前清單的行為。
一般測試須使用專案隔離入口：

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_history_mode_filter_contract.py \
  tests/test_report_index_query.py \
  tests/test_report_preview.py \
  tests/test_pipeline_mode_metadata_sync.py -q
```

修改分類 catalog 後執行 `scripts/generate_pipeline_mode_fallback.py`，並以
`--check` 核對生成檔。生產原始紀錄、報告快照、畫面截圖與金鑰不納入此契約。
