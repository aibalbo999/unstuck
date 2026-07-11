from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_GUIDE = ROOT / "docs" / "operator-guide.md"


def test_operator_guide_explains_the_three_task_oriented_commercial_pages():
    guide = OPERATOR_GUIDE.read_text(encoding="utf-8")

    assert "## Commercial Investment Workspace" in guide
    assert "### 500 萬操作護欄" in guide
    assert "今日決策" in guide and "檢查最高優先股票" in guide
    assert "單股研究" in guide and "更新股票快照" in guide
    assert "組合健檢" in guide and "分析 500 萬組合" in guide
    for amount in ("NT$1,000,000", "NT$750,000", "NT$50,000"):
        assert amount in guide
    assert "海外股票需要匯率" in guide
    assert "不會顯示或改用範例資料" in guide
