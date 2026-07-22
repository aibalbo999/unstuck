import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from final_audit_price_targets import price_target_audit_issues  # noqa: E402


def test_price_target_audit_flags_missing_required_scenarios():
    issues = price_target_audit_issues(
        {"熊市情境": 80, "基本情境": 100},
        current_price=100,
        valuation_agent=4,
    )

    assert issues == [
        {
            "critical": "Agent 4 缺少目標價情境：牛市情境",
            "repair_agent": 4,
            "repair_issue": "缺少目標價情境：牛市情境",
        }
    ]


def test_price_target_audit_flags_tiny_targets_against_current_price():
    issues = price_target_audit_issues(
        {"熊市情境": 3, "基本情境": 5, "牛市情境": 6},
        current_price=1000,
        valuation_agent=4,
    )

    assert issues[0]["critical"] == "目標價疑似單位縮小錯誤：熊市情境=NT$3, 基本情境=NT$5, 牛市情境=NT$6"
    assert issues[0]["repair_agent"] == 4
    assert issues[0]["repair_issue"] == issues[0]["critical"]


def test_price_target_audit_flags_unsorted_scenarios():
    issues = price_target_audit_issues(
        {"熊市情境": 1200, "基本情境": 1000, "牛市情境": 800},
        current_price=1000,
        valuation_agent=4,
    )

    assert issues == [
        {
            "critical": "三情境目標價順序不合理：熊市 1200、基本 1000、牛市 800。",
            "repair_agent": 4,
            "repair_issue": "三情境目標價順序不合理：熊市 1200、基本 1000、牛市 800。",
        }
    ]
