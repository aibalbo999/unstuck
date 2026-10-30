# 本機證據與公開回歸測試

`docs/evidence/` 的原始回應、收據、報告快照與執行結果保留在本機，不隨程式提交。文件中指向這個目錄的連結是本機查核線索；下載原始碼不會取得這些資料。

既有已追蹤的公開測試與去識別化 fixture 保留。新增公開測試使用人工構造輸入、隔離資料庫與替代傳輸；`tests/fixtures/official_price_cache.py` 只生成明示為 synthetic 的固定行情，不是交易所實際取得紀錄。私有原件回放及其測試版本另留在原工作區，不以刪除既有公開測試的方式整理。

`docs/market-evidence-validation-tests.json` 是測試選擇清單；`docs/cost-profile-assumptions.json` 是明示假設的成本政策。兩者可隨程式提交，不能當作實際金融資料、成本或策略成效的驗證證據。其他來源稽核結果、資料快照與固定批次的私人輸入不包含在提交中；相關工具從明確 CLI 參數接收外部輸入。

所有一般回歸測試使用 `tests/run_prompt_boundary_tests.py`，隔離正式 SQLite 並禁止正式 Redis、API 與模型供應商連線。測試通過只證明被測行為，不代表已取得來源、完成報告或完成服務重載。
