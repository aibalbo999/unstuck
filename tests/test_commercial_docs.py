from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_GUIDE = ROOT / "docs" / "operator-guide.md"


def test_operator_guide_explains_the_three_task_oriented_commercial_pages():
    guide = OPERATOR_GUIDE.read_text(encoding="utf-8")

    assert "## Commercial Investment Workspace" in guide
    assert "### 可調整操作設定" in guide
    assert "今日決策" in guide and "檢查最高優先股票" in guide
    assert "單股研究" in guide and "從清單選擇" in guide and "更新股票快照" in guide
    assert "組合健檢" in guide and "選擇 .csv 檔案" in guide and "分析目前組合" in guide
    assert "保存在目前瀏覽器" in guide
    assert "market_value" in guide and "檔案實際總額" in guide
    for amount in ("NT$1,000,000", "NT$750,000", "NT$50,000"):
        assert amount in guide
    assert "海外股票需要匯率" in guide
    assert "不會顯示或改用範例資料" in guide
