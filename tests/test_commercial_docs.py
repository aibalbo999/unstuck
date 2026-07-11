from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR_GUIDE = ROOT / "docs" / "operator-guide.md"


def test_operator_guide_explains_the_three_task_oriented_commercial_pages():
    guide = OPERATOR_GUIDE.read_text(encoding="utf-8")

    assert "## Commercial Investment Workspace" in guide
    assert "今日決策" in guide and "開始檢查" in guide
    assert "單股研究" in guide and "更新股票快照" in guide
    assert "組合健檢" in guide and "產生調整建議" in guide
    assert "不會顯示範例資料" in guide
