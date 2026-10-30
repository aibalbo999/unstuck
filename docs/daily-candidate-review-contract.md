# 每日兩週研究名單的可讀說明

第三批僅改善每日 GET projection 和讀取後的畫面，不建立每日新排程、不取價、不呼叫模型、不發送通知、不回填營運歷史。

`top_candidates` 中未知分數保留 null；具有 `separate_dimensions_not_calibrated` 的輸入按 ticker 顯示，不把單一訊號或舊混合分數當上漲排名。既有 numeric legacy fixture 保留其描述值供相容，所有候選仍 `research_only=true/actionable=false`。

品質漏斗可能保存於頂層或 `triggers[].quality_funnel`，以 reject > gray > pass 的保守順序判讀；任一保存的拒絕不能被另一份綠色蓋過。這不是當前品質獨立補驗，來源與 scope 明確保存，未知不變 pass。全索引 latest v4 的當前 withdrawn_reports 仍優先，1301/1101 等撤回不因掃描分數或歷史綠色重入。

每筆 evidence 分開保存掃描日、行情觀測日、法人觀測日、量的觀測日與報告生成時間。只有明確的 `metrics.price_observation_date`、`metrics.flow_observation_date` 可以進行情/法人日期判定；scan/update/report timestamp 不得代填。日期與最新完成交易日相同，也只代表日期對齊，不核准進場、催化事件或成本。既有來源只記 screen_date 時，畫面如實顯示行情/法人未確認。

`candidate_review` 的互斥分區涵蓋回傳 screener page：顯示研究、當前品質阻擋、保存漏斗拒絕、顯示上限外。上限外不代表品質淘汰；returned_count 與 screener 分頁 total 分開，不稱全市場。完整當前撤回集合仍獨立在 withdrawn_reports，不宣稱只回傳20筆就涵蓋所有品質阻擋。

主集合成熟度來自既有 `performance.population.net_result_diagnostics`，明示全索引10交易日不重疊決策 scope。待成熟76筆不是對畫面五檔逐股下的結論；沒有逐候選 window linkage 时不能推定 maturity_date。沒有資料時顯示 unavailable。

新增前端唯讀研究說明，呈現取樣範圍、入選理由、品質缺漏、各證據日期與排除/未顯示原因，不新增可交易按鈕。供應商文字經 HTML escape。未建立可驗證淨報酬證據、沒有降低 gate，也沒有在本批加成本情境或資料回算。未來仍需要原始價格同基準核對、成本來源与真正 point-in-time dataset。
