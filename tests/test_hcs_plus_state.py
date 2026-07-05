from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CONTRACT_TERMS = ("投資建議", "最終投資建議", "[投資建議]", "[/投資建議]")


def _files_containing_contract_terms(folder: str) -> list[Path]:
    base = ROOT / folder
    files = []
    for path in base.rglob("*"):
        if {"output", "__pycache__", ".pytest_cache"} & set(path.relative_to(base).parts):
            continue
        if not path.is_file() or path.suffix not in {".py", ".json", ".j2", ".md", ".html", ".js"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(term in text for term in CONTRACT_TERMS):
            files.append(path.relative_to(ROOT))
    return sorted(files)


HCS_HABITS = [
    "拆解問題",
    "問對問題",
    "差距分析",
    "變數分析",
    "偏誤辨識",
    "偏誤降低",
    "決策樹",
    "目的",
    "效用",
    "信賴區間",
    "相關性",
    "描述統計",
    "機率",
    "迴歸",
    "顯著性",
    "證據基礎",
    "演繹",
    "歸納",
    "謬誤",
    "來源品質",
    "情境脈絡",
    "批判",
    "估算",
    "詮釋框架",
    "合理性",
    "可驗證性",
    "學習科學",
    "限制條件",
    "類比",
    "演算法",
    "設計思考",
    "捷思法",
    "最佳化",
    "假說發展",
    "資料視覺化",
    "建模",
    "抽樣",
    "個案研究",
    "比較組",
    "介入研究",
    "訪談調查",
    "觀察研究",
    "研究複製",
    "受眾",
    "組成",
    "語意含義",
    "組織結構",
    "專業性",
    "論點",
    "溝通設計",
    "表達",
    "媒介",
    "多媒體",
    "倫理考量",
    "倫理勇氣",
    "倫理判斷",
    "複雜因果",
    "湧現特性",
    "分析層次",
    "網絡",
    "系統動力學",
    "系統圖像",
    "談判",
    "說服",
    "形塑行為",
    "從眾",
    "差異",
    "情緒智商",
    "領導原則",
    "權力動態",
    "責任",
    "自我覺察",
    "制定策略",
]


def test_hcs_plus_strict_habit_log_lists_every_habit():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = ROOT / "docs" / "hcs-plus-strict-habit-log.md"

    assert "hcs-plus-strict-habit-log.md" in state
    assert strict_log.exists()

    text = strict_log.read_text(encoding="utf-8")
    for habit in HCS_HABITS:
        assert f"#{habit}" in text


def test_hcs_plus_completed_batches_have_traceable_changes_and_checks():
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    completed_sections = [("批判思考", habit) for habit in [
        "拆解問題",
        "問對問題",
        "差距分析",
        "變數分析",
        "偏誤辨識",
        "偏誤降低",
        "決策樹",
        "目的",
        "效用",
        "信賴區間",
        "相關性",
        "描述統計",
        "機率",
        "迴歸",
        "顯著性",
        "證據基礎",
        "演繹",
        "歸納",
        "謬誤",
        "來源品質",
        "情境脈絡",
        "批判",
        "估算",
        "詮釋框架",
        "合理性",
        "可驗證性",
    ]]
    completed_sections.extend([
        ("創意思考", "學習科學"),
        ("創意思考", "限制條件"),
        ("創意思考", "類比"),
        ("創意思考", "演算法"),
        ("創意思考", "設計思考"),
        ("創意思考", "捷思法"),
        ("創意思考", "最佳化"),
        ("創意思考", "假說發展"),
        ("創意思考", "資料視覺化"),
        ("創意思考", "建模"),
        ("創意思考", "抽樣"),
        ("創意思考", "個案研究"),
        ("創意思考", "比較組"),
        ("創意思考", "介入研究"),
        ("創意思考", "訪談調查"),
        ("創意思考", "觀察研究"),
        ("創意思考", "研究複製"),
        ("溝通思考", "受眾"),
        ("溝通思考", "組成"),
        ("溝通思考", "語意含義"),
        ("溝通思考", "組織結構"),
        ("溝通思考", "專業性"),
        ("溝通思考", "論點"),
        ("溝通思考", "溝通設計"),
        ("溝通思考", "表達"),
        ("溝通思考", "媒介"),
        ("溝通思考", "多媒體"),
        ("互動思考", "倫理考量"),
        ("互動思考", "倫理勇氣"),
        ("互動思考", "倫理判斷"),
        ("互動思考", "複雜因果"),
        ("互動思考", "湧現特性"),
        ("互動思考", "分析層次"),
        ("互動思考", "網絡"),
        ("互動思考", "系統動力學"),
        ("互動思考", "系統圖像"),
        ("互動思考", "談判"),
        ("互動思考", "說服"),
        ("互動思考", "形塑行為"),
        ("互動思考", "從眾"),
        ("互動思考", "差異"),
        ("互動思考", "情緒智商"),
        ("互動思考", "領導原則"),
        ("互動思考", "權力動態"),
        ("互動思考", "責任"),
        ("互動思考", "自我覺察"),
        ("互動思考", "制定策略"),
    ])
    for category, habit in completed_sections:
        marker = f"### 第 1 輪 / {category} / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section


def test_hcs_plus_round2_completed_batches_have_traceable_changes_and_checks():
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    for habit in [
        "拆解問題",
        "問對問題",
        "差距分析",
        "變數分析",
        "偏誤辨識",
        "偏誤降低",
        "決策樹",
        "目的",
        "效用",
        "信賴區間",
        "相關性",
        "描述統計",
        "機率",
        "迴歸",
        "顯著性",
        "證據基礎",
        "演繹",
        "歸納",
        "謬誤",
        "來源品質",
        "情境脈絡",
        "批判",
        "估算",
        "詮釋框架",
        "合理性",
        "可驗證性",
    ]:
        marker = f"### 第 2 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section


def test_hcs_plus_round2_problem_radar_tracks_remaining_high_risk_gaps():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考問題雷達" in state
    assert "報告正文契約 vs 前端顯示層" in state
    assert "關鍵問題" in state
    assert "差距" in state
    assert "驗證證據" in state
    assert "第 2 輪批判思考第一批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #差距分析" in strict_log


def test_hcs_plus_round2_variable_and_bias_guardrails_are_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考變數與偏誤護欄" in state
    assert "可改名顯示層" in state
    assert "需保留契約層" in state
    assert "字串潔癖偏誤" in state
    assert "解析契約回歸" in state
    assert "第 2 輪批判思考第二批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #偏誤降低" in strict_log


def test_hcs_plus_round2_contract_term_decision_tree_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考契約詞決策樹" in state
    assert "使用者顯示層" in state
    assert "機器解析契約" in state
    assert "完整報告正文" in state
    assert "最高效用路徑" in state
    assert "第 2 輪批判思考第三批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #效用" in strict_log


def test_hcs_plus_round2_contract_coverage_map_has_observed_counts():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    test_files = _files_containing_contract_terms("tests")
    backend_files = _files_containing_contract_terms("backend")

    assert "## 第 2 輪批判思考契約覆蓋統計" in state
    assert f"測試檔案數：{len(test_files)}" in state
    assert f"後端檔案數：{len(backend_files)}" in state
    assert "最低可觀測樣本" in state
    assert "相關不等於可替換" in state
    assert "第 2 輪批判思考第四批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #描述統計" in strict_log


def test_hcs_plus_round2_contract_regression_risk_ranking_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考契約回歸風險排序" in state
    assert "高機率回歸" in state
    assert "回歸測試組" in state
    assert "顯著性門檻" in state
    assert "tests/test_report_preview.py" in state
    assert "tests/test_report_conformance.py" in state
    assert "tests/test_static_history_filters.py" in state
    assert "第 2 輪批判思考第五批" in strict_log
    assert "下一步：第 2 輪 / 批判思考 / #證據基礎" in strict_log


def test_hcs_plus_round2_required_contract_test_matrix_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考契約測試矩陣" in state
    assert "高顯著性改動" in state
    assert "必跑測試" in state
    assert "證據基礎" in state
    assert "演繹規則" in state
    assert "歸納限制" in state
    for test_path in [
        "tests/test_report_preview.py",
        "tests/test_report_conformance.py",
        "tests/test_audit_rules.py",
        "tests/test_prompt_context_routing.py",
        "tests/test_report_mode_templates.py",
        "tests/test_report_storage_integration.py",
        "tests/test_frontend_http_e2e.py",
        "tests/test_static_history_filters.py",
        "tests/test_frontend_visual_optional.py",
    ]:
        assert test_path in state
    assert "第 2 輪批判思考第六批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #歸納" in strict_log
    assert "下一步：第 2 輪 / 批判思考 / #謬誤" in strict_log


def test_hcs_plus_round2_contract_matrix_fallacy_source_context_guardrail_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考契約矩陣反謬誤護欄" in state
    assert "測試通過不等於語意安全" in state
    assert "coverage map 不等於完整母體" in state
    assert "frontend tests 不等於 parser/prompt safety" in state
    assert "來源品質分級" in state
    assert "高品質來源" in state
    assert "次級來源" in state
    assert "不得作為完成證據" in state
    assert "情境脈絡" in state
    assert "機器契約變更" in state
    assert "使用者顯示層改動" in state
    assert "第 2 輪批判思考第七批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #情境脈絡" in strict_log
    assert "下一步：第 2 輪 / 批判思考 / #批判" in strict_log


def test_hcs_plus_round2_contract_matrix_operability_estimate_frame_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考契約矩陣可執行性評估" in state
    assert "矩陣過重風險" in state
    assert "最小命令分組" in state
    assert "estimated scope" in state
    assert "4 個測試檔" in state
    assert "3 個測試檔" in state
    assert "2 個測試檔" in state
    assert "詮釋框架" in state
    assert "綠燈代表" in state
    assert "紅燈代表" in state
    assert "不得解讀為" in state
    assert "第 2 輪批判思考第八批" in strict_log
    assert "### 第 2 輪 / 批判思考 / #詮釋框架" in strict_log
    assert "下一步：第 2 輪 / 批判思考 / #合理性" in strict_log


def test_hcs_plus_round2_critical_thinking_closing_checkpoint_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 2 輪批判思考收尾檢查" in state
    assert "第 2 輪批判思考完成：26/26" in state
    assert "合理性結論" in state
    assert "可重跑驗證" in state
    assert "暫不新增自動選測腳本" in state
    assert "最小命令分組" in state
    assert "下一分類入口" in state
    assert "第 2 輪創意思考" in state
    assert "## 第 2 輪批判思考收尾" in strict_log
    assert "已完成：26/26" in strict_log
    assert "### 第 2 輪 / 批判思考 / #可驗證性" in strict_log
    assert "下一步：第 2 輪 / 創意思考 / #學習科學" in strict_log


def test_hcs_plus_round2_creative_learning_constraint_analogy_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪創意思考契約矩陣速學卡設計" in state
    assert "學習科學" in state
    assert "限制條件" in state
    assert "類比" in state
    assert "契約矩陣速學卡" in contract
    assert "先問三題" in contract
    assert "三道安檢通道" in contract
    assert "不新增自動選測腳本" in contract
    assert "第 2 輪創意思考第一批" in strict_log
    for habit in ["學習科學", "限制條件", "類比"]:
        marker = f"### 第 2 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 創意思考 / #演算法" in strict_log


def test_hcs_plus_round2_creative_algorithm_design_heuristic_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪創意思考契約矩陣操作流程設計" in state
    assert "演算法" in state
    assert "設計思考" in state
    assert "捷思法" in state
    assert "契約矩陣操作流程" in contract
    assert "四步演算法" in contract
    assert "三個操作者情境" in contract
    assert "三條捷思規則" in contract
    assert "第 2 輪創意思考第二批" in strict_log
    for habit in ["演算法", "設計思考", "捷思法"]:
        marker = f"### 第 2 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 創意思考 / #最佳化" in strict_log


def test_hcs_plus_round2_creative_optimization_hypothesis_visualization_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪創意思考契約矩陣採用觀測設計" in state
    assert "最佳化" in state
    assert "假說發展" in state
    assert "資料視覺化" in state
    assert "契約矩陣採用觀測板" in contract
    assert "最佳化目標" in contract
    assert "可觀察假說" in contract
    assert "採用訊號矩陣" in contract
    assert "第 2 輪創意思考第三批" in strict_log
    for habit in ["最佳化", "假說發展", "資料視覺化"]:
        marker = f"### 第 2 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 創意思考 / #建模" in strict_log


def test_hcs_plus_round2_creative_modeling_sampling_case_study_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪創意思考契約矩陣案例模型設計" in state
    assert "建模" in state
    assert "抽樣" in state
    assert "個案研究" in state
    assert "契約矩陣案例模型" in contract
    assert "三類案例模型" in contract
    assert "代表性抽樣規則" in contract
    assert "案例卡格式" in contract
    assert "第 2 輪創意思考第四批" in strict_log
    for habit in ["建模", "抽樣", "個案研究"]:
        marker = f"### 第 2 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 創意思考 / #比較組" in strict_log


def test_hcs_plus_round2_creative_comparison_intervention_survey_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪創意思考契約矩陣比較與回饋設計" in state
    assert "比較組" in state
    assert "介入研究" in state
    assert "訪談調查" in state
    assert "契約矩陣比較與回饋設計" in contract
    assert "比較組設計" in contract
    assert "介入方案" in contract
    assert "訪談回饋題" in contract
    assert "第 2 輪創意思考第五批" in strict_log
    for habit in ["比較組", "介入研究", "訪談調查"]:
        marker = f"### 第 2 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 創意思考 / #觀察研究" in strict_log


def test_hcs_plus_round2_creative_observation_replication_closing_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪創意思考契約矩陣觀察複製設計" in state
    assert "觀察研究" in state
    assert "研究複製" in state
    assert "契約矩陣觀察與複製準則" in contract
    assert "觀察記錄欄位" in contract
    assert "複製檢查清單" in contract
    assert "第 2 輪創意思考第六批" in strict_log
    for habit in ["觀察研究", "研究複製"]:
        marker = f"### 第 2 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "## 第 2 輪創意思考收尾" in strict_log
    assert "已完成：17/17" in strict_log
    assert "第 2 輪創意思考完成：17/17" in state
    assert "下一步：第 2 輪 / 溝通思考 / #受眾" in strict_log


def test_hcs_plus_round2_communication_audience_composition_semantics_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪溝通思考契約矩陣讀者路徑設計" in state
    assert "受眾" in state
    assert "組成" in state
    assert "語意含義" in state
    assert "契約矩陣讀者路徑" in contract
    assert "三種受眾" in contract
    assert "閱讀順序" in contract
    assert "語意邊界" in contract
    assert "第 2 輪溝通思考第一批" in strict_log
    for habit in ["受眾", "組成", "語意含義"]:
        marker = f"### 第 2 輪 / 溝通思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 溝通思考 / #組織結構" in strict_log


def test_hcs_plus_round2_communication_structure_professional_claim_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪溝通思考契約矩陣維護導覽設計" in state
    assert "組織結構" in state
    assert "專業性" in state
    assert "論點" in state
    assert "契約矩陣維護導覽" in contract
    assert "章節導覽" in contract
    assert "專業維護語氣" in contract
    assert "核心論點" in contract
    assert "第 2 輪溝通思考第二批" in strict_log
    for habit in ["組織結構", "專業性", "論點"]:
        marker = f"### 第 2 輪 / 溝通思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 溝通思考 / #溝通設計" in strict_log


def test_hcs_plus_round2_communication_design_expression_media_closing_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪溝通思考契約矩陣摘要與媒介設計" in state
    assert "溝通設計" in state
    assert "表達" in state
    assert "媒介" in state
    assert "多媒體" in state
    assert "契約矩陣一頁摘要" in contract
    assert "短版摘要" in contract
    assert "建議表達" in contract
    assert "媒介取捨" in contract
    assert "暫不新增圖像或多媒體" in contract
    assert "第 2 輪溝通思考第三批" in strict_log
    for habit in ["溝通設計", "表達", "媒介", "多媒體"]:
        marker = f"### 第 2 輪 / 溝通思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "## 第 2 輪溝通思考收尾" in strict_log
    assert "已完成：10/10" in strict_log
    assert "第 2 輪溝通思考完成：10/10" in state
    assert "下一步：第 2 輪 / 互動思考 / #倫理考量" in strict_log


def test_hcs_plus_round2_interaction_ethics_courage_judgment_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣倫理邊界設計" in state
    assert "倫理考量" in state
    assert "倫理勇氣" in state
    assert "倫理判斷" in state
    assert "契約矩陣倫理邊界" in contract
    assert "倫理底線" in contract
    assert "必要時要說不" in contract
    assert "升級條件" in contract
    assert "第 2 輪互動思考第一批" in strict_log
    for habit in ["倫理考量", "倫理勇氣", "倫理判斷"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 互動思考 / #複雜因果" in strict_log


def test_hcs_plus_round2_interaction_complex_emergent_layers_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣系統風險邊界設計" in state
    assert "複雜因果" in state
    assert "湧現特性" in state
    assert "分析層次" in state
    assert "契約矩陣系統風險邊界" in contract
    assert "複雜因果圖譜" in contract
    assert "湧現風險" in contract
    assert "分析層次" in contract
    assert "第 2 輪互動思考第二批" in strict_log
    for habit in ["複雜因果", "湧現特性", "分析層次"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 互動思考 / #網絡" in strict_log


def test_hcs_plus_round2_interaction_network_dynamics_system_image_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣系統關係設計" in state
    assert "網絡" in state
    assert "系統動力學" in state
    assert "系統圖像" in state
    assert "契約矩陣系統關係圖" in contract
    assert "維護網絡" in contract
    assert "系統動力學" in contract
    assert "系統圖像" in contract
    assert "第 2 輪互動思考第三批" in strict_log
    for habit in ["網絡", "系統動力學", "系統圖像"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 互動思考 / #談判" in strict_log


def test_hcs_plus_round2_interaction_negotiation_persuasion_behavior_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣 review 對話設計" in state
    assert "談判" in state
    assert "說服" in state
    assert "形塑行為" in state
    assert "契約矩陣 review 對話" in contract
    assert "補證據協商" in contract
    assert "說服原則" in contract
    assert "形塑行為" in contract
    assert "第 2 輪互動思考第四批" in strict_log
    for habit in ["談判", "說服", "形塑行為"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 互動思考 / #從眾" in strict_log


def test_hcs_plus_round2_interaction_conformity_difference_emotion_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣 review 防從眾設計" in state
    assert "從眾" in state
    assert "差異" in state
    assert "情緒智商" in state
    assert "契約矩陣 review 防從眾檢查" in contract
    assert "防從眾檢查" in contract
    assert "差異保留" in contract
    assert "情緒智商" in contract
    assert "第 2 輪互動思考第五批" in strict_log
    for habit in ["從眾", "差異", "情緒智商"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 互動思考 / #領導原則" in strict_log


def test_hcs_plus_round2_interaction_leadership_power_responsibility_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣 review 責任分工設計" in state
    assert "領導原則" in state
    assert "權力動態" in state
    assert "責任" in state
    assert "契約矩陣 review 責任分工" in contract
    assert "領導原則" in contract
    assert "權力動態" in contract
    assert "責任" in contract
    assert "第 2 輪互動思考第六批" in strict_log
    for habit in ["領導原則", "權力動態", "責任"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 2 輪 / 互動思考 / #自我覺察" in strict_log


def test_hcs_plus_round2_interaction_self_awareness_strategy_closing_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 2 輪互動思考契約矩陣 review 自我稽核與收尾設計" in state
    assert "自我覺察" in state
    assert "制定策略" in state
    assert "第 2 輪互動思考完成：20/20" in state
    assert "契約矩陣 review 自我稽核與收尾策略" in contract
    assert "自我覺察" in contract
    assert "制定策略" in contract
    assert "第 2 輪互動思考第七批" in strict_log
    for habit in ["自我覺察", "制定策略"]:
        marker = f"### 第 2 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "## 第 2 輪互動思考收尾" in strict_log
    assert "已完成：20/20" in strict_log
    assert "下一步：第 3 輪 / 批判思考 / #拆解問題" in strict_log


def test_hcs_plus_round3_critical_problem_question_gap_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣瘦身問題雷達" in state
    assert "拆解問題" in state
    assert "問對問題" in state
    assert "差距分析" in state
    assert "契約矩陣第 3 輪問題雷達" in contract
    assert "矩陣過重" in contract
    assert "關鍵問題" in contract
    assert "差距分析" in contract
    assert "第 3 輪批判思考第一批" in strict_log
    for habit in ["拆解問題", "問對問題", "差距分析"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #變數分析" in strict_log


def test_hcs_plus_round3_critical_variable_bias_reduction_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣變數與偏誤降低護欄" in state
    assert "變數分析" in state
    assert "偏誤辨識" in state
    assert "偏誤降低" in state
    assert "契約矩陣第 3 輪變數與偏誤降低護欄" in contract
    for expected in [
        "過度升級偏誤",
        "過度降級偏誤",
        "工具化幻覺",
        "綠燈擴張偏誤",
        "證據分層回報",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第二批" in strict_log
    for habit in ["變數分析", "偏誤辨識", "偏誤降低"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #決策樹" in strict_log


def test_hcs_plus_round3_critical_decision_purpose_utility_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣分流決策與效用校準" in state
    assert "決策樹" in state
    assert "目的" in state
    assert "效用" in state
    assert "契約矩陣第 3 輪分流決策與效用校準" in contract
    for expected in [
        "一頁摘要與低顯著性命令",
        "高顯著性機器契約通道",
        "混合層報告呈現通道",
        "案例卡或拆分 patch",
        "效用校準",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第三批" in strict_log
    for habit in ["決策樹", "目的", "效用"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #信賴區間" in strict_log


def test_hcs_plus_round3_critical_confidence_correlation_stats_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣證據校準與觀測統計" in state
    assert "信賴區間" in state
    assert "相關性" in state
    assert "描述統計" in state
    assert "契約矩陣第 3 輪證據校準與觀測統計" in contract
    for expected in [
        "目前樣本",
        "不可外推",
        "選通道時間",
        "錯選通道",
        "限制句出現率",
        "中位選通道時間",
        "案例卡觸發率",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第四批" in strict_log
    for habit in ["信賴區間", "相關性", "描述統計"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #機率" in strict_log


def test_hcs_plus_round3_critical_probability_regression_significance_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣風險機率與顯著性門檻" in state
    assert "機率" in state
    assert "迴歸" in state
    assert "顯著性" in state
    assert "契約矩陣第 3 輪風險機率與顯著性門檻" in contract
    for expected in [
        "錯選率",
        "限制句缺漏率",
        "案例卡漏觸發率",
        "連續兩個觀察窗口",
        "不得宣稱改善",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第五批" in strict_log
    for habit in ["機率", "迴歸", "顯著性"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #證據基礎" in strict_log


def test_hcs_plus_round3_critical_evidence_deduction_induction_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣證據規則與外推邊界" in state
    assert "證據基礎" in state
    assert "演繹" in state
    assert "歸納" in state
    assert "契約矩陣第 3 輪證據規則與外推邊界" in contract
    for expected in [
        "可接受證據",
        "不可作為證據",
        "若碰 parser/prompt/template",
        "立即升級",
        "不得外推",
        "真實使用者理解",
        "runtime 安全",
        "生成報告母體",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第六批" in strict_log
    for habit in ["證據基礎", "演繹", "歸納"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #謬誤" in strict_log


def test_hcs_plus_round3_critical_fallacy_source_context_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣反謬誤與來源情境邊界" in state
    assert "謬誤" in state
    assert "來源品質" in state
    assert "情境脈絡" in state
    assert "契約矩陣第 3 輪反謬誤與來源情境邊界" in contract
    for expected in [
        "測試綠燈謬誤",
        "樣本數謬誤",
        "案例代表性謬誤",
        "高品質來源",
        "次級來源",
        "不得作為完成證據",
        "只適用於契約相關變更",
        "不得替代 runtime 驗證",
        "不得替代使用者研究",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第七批" in strict_log
    for habit in ["謬誤", "來源品質", "情境脈絡"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #批判" in strict_log


def test_hcs_plus_round3_critical_critique_estimation_frame_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考契約矩陣負擔估算與完成詮釋框架" in state
    assert "批判" in state
    assert "估算" in state
    assert "詮釋框架" in state
    assert "契約矩陣第 3 輪負擔估算與完成詮釋框架" in contract
    for expected in [
        "矩陣過重",
        "必留護欄",
        "可短句替代",
        "完成回報成本",
        "低風險 UI",
        "高風險契約",
        "文件契約通過",
        "不得宣稱安全",
        "不得宣稱理解改善",
    ]:
        assert expected in contract
    assert "第 3 輪批判思考第八批" in strict_log
    for habit in ["批判", "估算", "詮釋框架"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "下一步：第 3 輪 / 批判思考 / #合理性" in strict_log


def test_hcs_plus_round3_critical_thinking_closing_checkpoint_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪批判思考收尾檢查" in state
    assert "第 3 輪批判思考完成：26/26" in state
    assert "合理性結論" in state
    assert "可重跑驗證" in state
    assert "不新增自動選測腳本" in state
    assert "契約矩陣第 3 輪收尾與可重跑驗證" in contract
    assert "下一分類入口" in state
    assert "第 3 輪創意思考" in state
    assert "## 第 3 輪批判思考第九批" in strict_log
    for habit in ["合理性", "可驗證性"]:
        marker = f"### 第 3 輪 / 批判思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "## 第 3 輪批判思考收尾" in strict_log
    assert "已完成：26/26" in strict_log
    assert "下一步：第 3 輪 / 創意思考 / #學習科學" in strict_log


def test_hcs_plus_round3_creative_learning_constraints_analogy_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪創意思考契約矩陣學習入口" in state
    assert "學習科學" in state
    assert "限制條件" in state
    assert "類比" in state
    assert "契約矩陣第 3 輪創意學習入口" in contract
    for expected in [
        "三層學習路徑",
        "10 秒判斷",
        "90 秒執行",
        "5 分鐘復盤",
        "不改 runtime 行為",
        "不新增自動選測腳本",
        "不新增遙測",
        "不替代人工 review",
        "登機前安檢",
        "快速通道",
        "人工複檢",
        "證據托盤",
    ]:
        assert expected in contract
    assert "第 3 輪創意思考第一批" in strict_log
    for habit in ["學習科學", "限制條件", "類比"]:
        marker = f"### 第 3 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 3 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 3 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 3 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "下一步：第 3 輪 / 創意思考 / #演算法" in strict_log


def test_hcs_plus_round3_creative_algorithm_design_heuristics_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪創意思考契約矩陣操作演算法與捷思規則" in state
    assert "演算法" in state
    assert "設計思考" in state
    assert "捷思法" in state
    assert "契約矩陣第 3 輪操作演算法與捷思規則" in contract
    for expected in [
        "四步操作演算法",
        "步驟 1：10 秒判斷",
        "步驟 2：選擇通道",
        "步驟 3：裝好證據托盤",
        "步驟 4：完成回報",
        "三個操作者情境",
        "情境 A：只改低風險 UI",
        "情境 B：改報告模板或正文呈現",
        "情境 C：改 parser、prompt、template 或核心契約詞",
        "三條快速規則",
        "有核心契約詞就先人工複檢",
        "只在前端顯示才走快速通道",
        "缺少限制句就不得完成",
    ]:
        assert expected in contract
    assert "第 3 輪創意思考第二批" in strict_log
    for habit in ["演算法", "設計思考", "捷思法"]:
        marker = f"### 第 3 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 3 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 3 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "下一步：第 3 輪 / 創意思考 / #最佳化" in strict_log


def test_hcs_plus_round3_creative_optimization_hypothesis_visualization_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪創意思考契約矩陣採用最佳化與訊號板" in state
    assert "最佳化" in state
    assert "假說發展" in state
    assert "資料視覺化" in state
    assert "契約矩陣第 3 輪採用最佳化與訊號板" in contract
    for expected in [
        "採用摩擦",
        "錯選通道",
        "漏跑命令",
        "限制句缺漏",
        "案例卡漏補",
        "假說 1：四步操作會降低錯選通道",
        "假說 2：證據托盤會降低漏跑命令",
        "假說 3：三條快速規則會降低限制句缺漏",
        "採用訊號板",
        "綠色",
        "黃色",
        "紅色",
        "人工觀察",
        "不新增遙測",
        "不得宣稱改善",
    ]:
        assert expected in contract
    assert "第 3 輪創意思考第三批" in strict_log
    for habit in ["最佳化", "假說發展", "資料視覺化"]:
        marker = f"### 第 3 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 3 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "下一步：第 3 輪 / 創意思考 / #建模" in strict_log


def test_hcs_plus_round3_creative_models_sampling_case_cards_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪創意思考契約矩陣案例模型與抽樣案例卡" in state
    assert "建模" in state
    assert "抽樣" in state
    assert "個案研究" in state
    assert "契約矩陣第 3 輪案例模型與抽樣案例卡" in contract
    for expected in [
        "代表性案例模型",
        "模型 A：低風險快速通道案例",
        "模型 B：混合層報告呈現案例",
        "模型 C：高風險契約人工複檢案例",
        "模型 D：紅色阻擋案例",
        "代表性抽樣規則",
        "黃色或紅色必抽",
        "少於 5 個案例不得宣稱趨勢",
        "案例卡格式",
        "改動描述",
        "改動層級",
        "選擇通道",
        "證據托盤",
        "採用訊號",
        "限制句",
        "補救行動",
        "不可外推",
    ]:
        assert expected in contract
    assert "第 3 輪創意思考第四批" in strict_log
    for habit in ["建模", "抽樣", "個案研究"]:
        marker = f"### 第 3 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "下一步：第 3 輪 / 創意思考 / #比較組" in strict_log


def test_hcs_plus_round3_creative_comparison_intervention_feedback_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪創意思考契約矩陣比較與介入回饋設計" in state
    assert "比較組" in state
    assert "介入研究" in state
    assert "訪談調查" in state
    assert "契約矩陣第 3 輪比較與介入回饋設計" in contract
    for expected in [
        "基準組",
        "介入組",
        "錯選通道率",
        "漏跑命令率",
        "限制句缺漏率",
        "案例卡補救率",
        "不得宣稱因果改善",
        "最小介入方案",
        "改檔前 60 秒案例模型選擇",
        "完成回報三欄補強",
        "黃色或紅色補救回放",
        "介入停止條件",
        "操作者回饋題",
        "你能否在 2 分鐘內選出通道",
        "哪個案例模型最難判斷",
        "案例卡是否暴露漏跑命令或限制句缺漏",
        "不新增產品遙測",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪創意思考第五批" in strict_log
    for habit in ["比較組", "介入研究", "訪談調查"]:
        marker = f"### 第 3 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "下一步：第 3 輪 / 創意思考 / #觀察研究" in strict_log


def test_hcs_plus_round3_creative_observation_replication_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪創意思考契約矩陣觀察與複製準則" in state
    assert "觀察研究" in state
    assert "研究複製" in state
    assert "契約矩陣第 3 輪觀察與複製準則" in contract
    for expected in [
        "觀察記錄欄位",
        "觀察窗口",
        "變更案例 ID",
        "選定案例模型",
        "實際選擇通道",
        "實際執行命令",
        "完成回報三欄",
        "觀察結果",
        "操作者回饋摘要",
        "補救行動",
        "不可外推",
        "複製檢查清單",
        "同一觀察窗口定義",
        "同一案例模型選項",
        "同一指標口徑",
        "同一介入停止條件",
        "同一限制句",
        "可複製完成條件",
        "下一位操作者不用讀完整 HCS 附件",
        "不新增產品遙測",
        "不得替代 pytest 或人工 review",
        "不得宣稱改善",
    ]:
        assert expected in contract
    assert "第 3 輪創意思考第六批" in strict_log
    for habit in ["觀察研究", "研究複製"]:
        marker = f"### 第 3 輪 / 創意思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "下一步：第 3 輪 / 溝通思考 / #受眾" in strict_log


def test_hcs_plus_round3_communication_audience_composition_semantics_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪溝通思考契約矩陣讀者語意入口" in state
    assert "受眾" in state
    assert "組成" in state
    assert "語意含義" in state
    assert "契約矩陣第 3 輪讀者語意入口" in contract
    for expected in [
        "低風險 UI 維護者",
        "報告呈現維護者",
        "契約複檢維護者",
        "觀察流程維護者",
        "第一步：先判斷讀者角色",
        "第二步：只讀對應入口",
        "第三步：補齊觀察欄位",
        "第四步：用限制句收尾",
        "讀者角色不是權限等級",
        "入口不是自動判斷器",
        "觀察欄位不是 pytest",
        "複製成功不是改善證明",
        "低風險不代表低責任",
        "不得宣稱 runtime 安全",
        "不得宣稱使用者理解改善",
        "不得宣稱 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "第 3 輪溝通思考第一批" in strict_log
    for habit in ["受眾", "組成", "語意含義"]:
        marker = f"### 第 3 輪 / 溝通思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 3 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 3 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 3 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 溝通思考 / #組織結構" in strict_log


def test_hcs_plus_round3_communication_structure_professional_argument_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪溝通思考契約矩陣維護導覽與核心論點" in state
    assert "組織結構" in state
    assert "專業性" in state
    assert "論點" in state
    assert "契約矩陣第 3 輪維護導覽與核心論點" in contract
    for expected in [
        "章節導覽",
        "先定位讀者角色",
        "再選通道與案例模型",
        "接著補觀察欄位",
        "最後用限制句與核心論點收尾",
        "維護語氣",
        "只描述觀察窗口",
        "明列未跑命令",
        "把紅色訊號說成停止條件",
        "不得把測試綠燈寫成安全證明",
        "核心主張",
        "契約矩陣的目的不是提高文件厚度",
        "讓低風險改動更快收尾",
        "讓高風險契約更早升級",
        "讓觀察紀錄可複製但不被誤讀",
        "不得宣稱改善",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪溝通思考第二批" in strict_log
    for habit in ["組織結構", "專業性", "論點"]:
        marker = f"### 第 3 輪 / 溝通思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 3 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 3 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 溝通思考 / #溝通設計" in strict_log


def test_hcs_plus_round3_communication_short_report_media_choice_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪溝通思考契約矩陣短版回報與媒介取捨" in state
    assert "溝通設計" in state
    assert "表達" in state
    assert "媒介" in state
    assert "多媒體" in state
    assert "契約矩陣第 3 輪短版回報與媒介取捨" in contract
    for expected in [
        "一頁摘要",
        "先說本次改動層級",
        "再列已跑命令與未跑命令",
        "最後寫不得解讀為",
        "建議句型",
        "我選擇的通道是",
        "我已執行的命令是",
        "本次不得解讀為",
        "文字與表格優先",
        "不要新增圖像流程",
        "不要用多媒體替代限制句",
        "暫不新增圖像或多媒體",
        "保留可搜尋文字",
        "保留 pytest 與人工 review",
        "完成第 3 輪溝通思考",
    ]:
        assert expected in contract
    assert "第 3 輪溝通思考第三批" in strict_log
    for habit in ["溝通設計", "表達", "媒介", "多媒體"]:
        marker = f"### 第 3 輪 / 溝通思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "## 第 3 輪溝通思考收尾" in strict_log
    assert "已完成：10/10" in strict_log
    assert "| 3 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 3 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #倫理考量" in strict_log


def test_hcs_plus_round3_interaction_ethics_courage_judgment_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣倫理阻擋與責任判斷" in state
    assert "倫理考量" in state
    assert "倫理勇氣" in state
    assert "倫理判斷" in state
    assert "契約矩陣第 3 輪倫理阻擋與責任判斷" in contract
    for expected in [
        "短版回報倫理底線",
        "不得把短版回報寫成安全背書",
        "不得把責任轉嫁給文件、工具或測試",
        "不得用快速通道淡化高風險契約",
        "必要時要說不",
        "缺少 parser/prompt/template 證據時停止合併",
        "報告文案像交易指令時先補責任邊界",
        "高風險契約被降級時回到人工複檢",
        "允許回報",
        "禁止回報",
        "升級判斷",
        "低風險改動若碰到使用者行動暗示",
        "混合層若碰到核心契約詞",
        "文件或觀察若被拿來宣稱 runtime 行為",
        "不得宣稱使用者已理解",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第一批" in strict_log
    for habit in ["倫理考量", "倫理勇氣", "倫理判斷"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #複雜因果" in strict_log


def test_hcs_plus_round3_interaction_causality_emergent_layers_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣系統因果與證據層次" in state
    assert "複雜因果" in state
    assert "湧現特性" in state
    assert "分析層次" in state
    assert "契約矩陣第 3 輪系統因果與證據層次" in contract
    for expected in [
        "局部綠燈因果圖",
        "文件契約通過可能造成流程已安全的錯誤推論",
        "前端測試通過可能造成 parser/prompt 已安全的錯誤推論",
        "倫理阻擋存在可能造成高風險已被完全阻擋的錯誤推論",
        "低風險快速通道累積成高風險語氣漂移",
        "案例卡增加但實際驗證減少",
        "阻擋規則存在但 reviewer 不敢啟用",
        "文件層",
        "測試層",
        "runtime 層",
        "使用者行為層",
        "同層證據只能支持同層宣稱",
        "跨層宣稱必須升級驗證",
        "不得用文件完整替代 runtime 驗證",
        "不得用測試通過宣稱使用者理解",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第二批" in strict_log
    for habit in ["複雜因果", "湧現特性", "分析層次"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #網絡" in strict_log


def test_hcs_plus_round3_interaction_network_dynamics_image_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣維護網絡與動態圖像" in state
    assert "網絡" in state
    assert "系統動力學" in state
    assert "系統圖像" in state
    assert "契約矩陣第 3 輪維護網絡與動態圖像" in contract
    for expected in [
        "維護網絡",
        "文件層節點",
        "測試層節點",
        "runtime 層節點",
        "使用者行為層節點",
        "reviewer 阻擋節點",
        "快速通道摩擦降低回路",
        "案例卡形式化回路",
        "阻擋勇氣回路",
        "跨層宣稱升級回路",
        "先定位證據層",
        "再連到網絡節點",
        "接著判斷動態回路",
        "最後決定維持同層宣稱或升級驗證",
        "不得把網絡圖像當成自動審核器",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第三批" in strict_log
    for habit in ["網絡", "系統動力學", "系統圖像"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #談判" in strict_log


def test_hcs_plus_round3_interaction_review_dialogue_default_behavior_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣 review 對話與預設行為" in state
    assert "談判" in state
    assert "說服" in state
    assert "形塑行為" in state
    assert "契約矩陣第 3 輪 review 對話與預設行為" in contract
    for expected in [
        "補證據協商",
        "不降低標準",
        "我可以接受同層宣稱，但跨層宣稱需要補證據",
        "若要保留快速通道，請移除 runtime 或使用者行為宣稱",
        "若要宣稱 parser/prompt 安全，請補高顯著性命令或拆分改動",
        "說服不是美化風險",
        "先承認已完成的證據",
        "再指出缺口",
        "接著提出最小可接受補證據",
        "最後寫不得解讀為",
        "降低說不成本",
        "完成回報預設三欄",
        "本次宣稱層級",
        "已補證據",
        "仍不得解讀為",
        "黃色：同層宣稱可合併但補限制句",
        "紅色：停止合併、補跑 pytest 或人工 review、拆分 patch",
        "跨層宣稱預設升級",
        "不得把好聽句型當成證據",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第四批" in strict_log
    for habit in ["談判", "說服", "形塑行為"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #從眾" in strict_log


def test_hcs_plus_round3_interaction_conformity_difference_emotion_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣防從眾、差異訊號與情緒調節" in state
    assert "從眾" in state
    assert "差異" in state
    assert "情緒智商" in state
    assert "契約矩陣第 3 輪防從眾、差異訊號與情緒調節" in contract
    for expected in [
        "防從眾檢查",
        "多數同意不是證據",
        "前例綠燈不是本次綠燈",
        "測試全綠不是限制句",
        "快要合併不是降低標準的理由",
        "差異訊號",
        "改動層級差異",
        "證據層差異",
        "pipeline 模式差異",
        "風險顏色差異",
        "不得把黃色與紅色訊號寫成綠色",
        "高壓語氣處理",
        "先命名壓力來源",
        "再回到預設三欄",
        "接著保留最小補證據路徑",
        "最後用冷靜限制句收尾",
        "不得用趕時間取代證據層",
        "不得用情緒安撫取代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第五批" in strict_log
    for habit in ["從眾", "差異", "情緒智商"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #領導原則" in strict_log


def test_hcs_plus_round3_interaction_role_responsibility_power_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣角色責任與權力護欄" in state
    assert "領導原則" in state
    assert "權力動態" in state
    assert "責任" in state
    assert "契約矩陣第 3 輪角色責任與權力護欄" in contract
    for expected in [
        "證據領導",
        "主責先宣告本次宣稱層級",
        "review 主導者維持升級權",
        "合併者確認紅色與黃色訊號已處理",
        "不以速度領導取代證據領導",
        "合併權限不能覆蓋紅色訊號",
        "資深度不能把前例綠燈變成通行證",
        "低權限操作者可以引用契約要求補證據",
        "權威催促必須回到預設三欄",
        "改動者負責本次宣稱層級與已補證據",
        "reviewer 負責仍不得解讀為",
        "合併者負責未跑命令與剩餘風險",
        "問題可追溯到角色責任",
        "不得把責任轉嫁給文件、工具或測試",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第六批" in strict_log
    for habit in ["領導原則", "權力動態", "責任"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：第 3 輪 / 互動思考 / #自我覺察" in strict_log


def test_hcs_plus_round3_interaction_self_audit_strategy_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "## 第 3 輪互動思考契約矩陣自我稽核與收尾策略" in state
    assert "自我覺察" in state
    assert "制定策略" in state
    assert "契約矩陣第 3 輪自我稽核與收尾策略" in contract
    for expected in [
        "角色責任不是流程越多越好",
        "輕量使用邊界",
        "低風險同層改動只需完成回報三欄",
        "黃色訊號補限制句或最小證據",
        "紅色訊號才要求停止合併、補跑 pytest 或拆分 patch",
        "不把角色責任變成形式簽核",
        "不把文件完整當成自動審核器",
        "第 3 輪互動思考收尾條件",
        "20/20 單項完成",
        "證據層與角色責任已可追溯",
        "下一步進入三習慣綜合優化",
        "綜合優化候選：#可驗證性、#溝通設計、#系統圖像",
        "不得宣稱 HCS Plus 完成",
        "不得新增 runtime、遙測或自動選測工具",
        "不得替代 pytest 或人工 review",
    ]:
        assert expected in contract
    assert "第 3 輪互動思考第七批" in strict_log
    for habit in ["自我覺察", "制定策略"]:
        marker = f"### 第 3 輪 / 互動思考 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "## 第 3 輪互動思考收尾" in strict_log
    assert "已完成：20/20" in strict_log
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化 / #可驗證性" in strict_log


def test_hcs_plus_integrated_verification_communication_system_view_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D89：三習慣綜合優化第 1 次" in state
    assert "## 三習慣綜合優化第 1 次：驗證、溝通與系統圖像收斂" in state
    assert "契約矩陣綜合優化第 1 次：驗證、溝通與系統圖像收斂" in contract
    for expected in [
        "綜合視角",
        "#可驗證性",
        "#溝通設計",
        "#系統圖像",
        "驗證閘門",
        "不跑命令不能宣稱通過",
        "文件契約只支持文件層宣稱",
        "完成回報格式",
        "本次宣稱層級",
        "已補證據",
        "仍不得解讀為",
        "下一個可執行行動",
        "系統圖像收斂",
        "前端顯示層",
        "報告呈現層",
        "機器契約層",
        "維運決策層",
        "每個完成宣稱都有對應命令或限制句",
        "不得把綜合優化第 1 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 1 次" in strict_log
    for habit in ["可驗證性", "溝通設計", "系統圖像"]:
        marker = f"### 綜合 / 三習慣綜合優化第 1 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 2 次 / #證據基礎" in strict_log


def test_hcs_plus_integrated_evidence_audience_responsibility_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D90：三習慣綜合優化第 2 次" in state
    assert "## 三習慣綜合優化第 2 次：證據來源、讀者角色與責任承接" in state
    assert "契約矩陣綜合優化第 2 次：證據來源、讀者角色與責任承接" in contract
    for expected in [
        "證據來源分級",
        "直接證據",
        "間接證據",
        "缺口證據",
        "未跑命令",
        "讀者角色分流",
        "低風險 UI 維護者",
        "報告呈現維護者",
        "機器契約維護者",
        "維運決策維護者",
        "合併者",
        "責任承接",
        "改動者負責證據來源與宣稱層級",
        "reviewer 負責讀者是否會誤讀",
        "合併者負責未跑命令與剩餘風險是否可接受",
        "未跑命令不能消失",
        "剩餘風險必須留到下一步",
        "不得把使用者理解、安全或投資判斷外推",
        "不得把綜合優化第 2 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 2 次" in strict_log
    for habit in ["證據基礎", "受眾", "責任"]:
        marker = f"### 綜合 / 三習慣綜合優化第 2 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 3 次 / #偏誤降低" in strict_log


def test_hcs_plus_integrated_bias_learning_strategy_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D91：三習慣綜合優化第 3 次" in state
    assert "## 三習慣綜合優化第 3 次：偏誤防線、速學入口與策略收斂" in state
    assert "契約矩陣綜合優化第 3 次：偏誤防線、速學入口與策略收斂" in contract
    for expected in [
        "偏誤防線",
        "表格打勾偏誤",
        "證據漂白偏誤",
        "升級逃避偏誤",
        "流程膨脹偏誤",
        "速學入口",
        "10 秒定位",
        "90 秒分流",
        "5 分鐘復盤",
        "策略收斂",
        "低風險維持輕量",
        "高顯著性必須升級",
        "未跑命令留到下一步",
        "策略膨脹必須刪減",
        "不得把矩陣完成誤讀為證據充分",
        "不得把速學入口替代完整契約",
        "不得把綜合優化第 3 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 3 次" in strict_log
    for habit in ["偏誤降低", "學習科學", "制定策略"]:
        marker = f"### 綜合 / 三習慣綜合優化第 3 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 4 次 / #目的" in strict_log


def test_hcs_plus_integrated_goal_utility_reasonability_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D92：三習慣綜合優化第 4 次" in state
    assert "## 三習慣綜合優化第 4 次：目標校準、效用門檻與合理性審核" in state
    assert "契約矩陣綜合優化第 4 次：目標校準、效用門檻與合理性審核" in contract
    for expected in [
        "目標校準",
        "股票研究系統核心目標",
        "使用者決策用途",
        "維護者合併判斷",
        "契約安全邊界",
        "效用門檻",
        "降低錯選模式",
        "降低漏跑命令",
        "降低跨層外推",
        "降低維護成本",
        "合理性審核",
        "必要性",
        "比例性",
        "可驗證性",
        "可逆性",
        "低效用規則必須刪減",
        "高成本規則必須有證據",
        "目的不明不能加入矩陣",
        "不得讓契約矩陣服務文件本身",
        "不得把效用推論寫成已證明改善",
        "不得把綜合優化第 4 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 4 次" in strict_log
    for habit in ["目的", "效用", "合理性"]:
        marker = f"### 綜合 / 三習慣綜合優化第 4 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 5 次 / #限制條件" in strict_log


def test_hcs_plus_integrated_constraints_decision_optimization_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D93：三習慣綜合優化第 5 次" in state
    assert "## 三習慣綜合優化第 5 次：限制邊界、分流決策與成本最佳化" in state
    assert "契約矩陣綜合優化第 5 次：限制邊界、分流決策與成本最佳化" in contract
    for expected in [
        "限制邊界",
        "硬限制",
        "軟限制",
        "升級限制",
        "停用限制",
        "不得新增 runtime、遙測或自動選測工具",
        "不得替代 pytest 或人工 review",
        "不得生成交易指令或安全背書",
        "分流決策",
        "第一步：判斷改動層級",
        "第二步：判斷顯著性",
        "第三步：判斷證據缺口",
        "第四步：選擇輕量、升級、拆分或刪減",
        "成本最佳化",
        "保留低風險輕量通道",
        "合併重複規則",
        "刪除低效用規則",
        "延後無證據規則",
        "不得為了最佳化而降低高顯著性驗證",
        "不得把決策樹當成自動選測工具",
        "不得把綜合優化第 5 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 5 次" in strict_log
    for habit in ["限制條件", "決策樹", "最佳化"]:
        marker = f"### 綜合 / 三習慣綜合優化第 5 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 6 次 / #來源品質" in strict_log


def test_hcs_plus_integrated_source_context_critique_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D94：三習慣綜合優化第 6 次" in state
    assert "## 三習慣綜合優化第 6 次：來源分級、適用情境與批判反證" in state
    assert "契約矩陣綜合優化第 6 次：來源分級、適用情境與批判反證" in contract
    for expected in [
        "來源分級",
        "高可信來源",
        "可用但有限來源",
        "不得作為完成證據",
        "缺口來源",
        "適用情境",
        "低風險同層文件改動",
        "報告呈現或使用者語意改動",
        "機器契約或高顯著性改動",
        "維運決策或排程風險改動",
        "批判反證",
        "反問一：這條規則可能在哪裡失效",
        "反問二：目前證據是否只支持文件存在",
        "反問三：是否有更小的限制句或刪減方式",
        "來源品質不足必須降級宣稱",
        "情境不符必須改走升級或拆分",
        "批判反證未處理不得合併高顯著性規則",
        "不得把歷史紀錄當成新證據",
        "不得把適用情境擴張到 runtime 或使用者理解",
        "不得把綜合優化第 6 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 6 次" in strict_log
    for habit in ["來源品質", "情境脈絡", "批判"]:
        marker = f"### 綜合 / 三習慣綜合優化第 6 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 7 次 / #估算" in strict_log


def test_hcs_plus_integrated_estimation_confidence_interpretation_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D95：三習慣綜合優化第 7 次" in state
    assert "## 三習慣綜合優化第 7 次：把握校準、信心邊界與解讀框架" in state
    assert "契約矩陣綜合優化第 7 次：把握校準、信心邊界與解讀框架" in contract
    for expected in [
        "把握估算",
        "估算等級",
        "高把握",
        "中把握",
        "低把握",
        "不得宣稱",
        "信心邊界",
        "適用層級",
        "證據覆蓋",
        "剩餘不確定",
        "不得跨過未測層",
        "解讀框架",
        "已驗證",
        "有限支持",
        "暫定假設",
        "未證明",
        "每個完成宣稱必須同時寫出把握等級、信心邊界與解讀框架",
        "低把握不得升格為完成",
        "信心邊界不得跨過未測層",
        "解讀框架不得替代 pytest、人工 review 或 runtime 驗證",
        "不得把估算寫成精確量化承諾",
        "不得把綜合優化第 7 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 7 次" in strict_log
    for habit in ["估算", "信賴區間", "詮釋框架"]:
        marker = f"### 綜合 / 三習慣綜合優化第 7 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 8 次 / #相關性" in strict_log


def test_hcs_plus_integrated_correlation_summary_significance_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D96：三習慣綜合優化第 8 次" in state
    assert "## 三習慣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻" in state
    assert "契約矩陣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻" in contract
    for expected in [
        "關聯檢核",
        "規則關聯",
        "強支撐",
        "弱支撐",
        "衝突支撐",
        "無關",
        "分布摘要",
        "完成分布",
        "缺口分布",
        "驗證分布",
        "風險分布",
        "顯著性門檻",
        "升級訊號",
        "保留訊號",
        "降級訊號",
        "刪減訊號",
        "只有強支撐且跨多個來源層級的關聯才能升級成矩陣規則",
        "分布摘要只能描述目前文件與測試覆蓋",
        "顯著性門檻不得替代 pytest、人工 review 或 runtime 驗證",
        "不得把相關性解讀為因果",
        "不得把描述統計解讀為改善證明",
        "不得把綜合優化第 8 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 8 次" in strict_log
    for habit in ["相關性", "描述統計", "顯著性"]:
        marker = f"### 綜合 / 三習慣綜合優化第 8 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 9 次 / #機率" in strict_log


def test_hcs_plus_integrated_probability_regression_fallacy_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D97：三習慣綜合優化第 9 次" in state
    assert "## 三習慣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線" in state
    assert "契約矩陣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線" in contract
    for expected in [
        "概率語言",
        "概率等級",
        "高可能",
        "中可能",
        "低可能",
        "未知或不得推定",
        "不得使用精確百分比",
        "迴歸風險",
        "舊問題",
        "回到過度宣稱",
        "回到跨層外推",
        "回到流程膨脹",
        "回到弱證據升級",
        "謬誤防線",
        "相關不等於因果",
        "通過測試不等於 runtime 安全",
        "文件完整不等於使用者理解",
        "歷史紀錄不等於新證據",
        "不得把概率語言寫成保證",
        "不得把迴歸風險寫成已修復",
        "不得把謬誤清單替代 pytest、人工 review 或 runtime 驗證",
        "不得把綜合優化第 9 次解讀為 HCS Plus 完成",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 9 次" in strict_log
    for habit in ["機率", "迴歸", "謬誤"]:
        marker = f"### 綜合 / 三習慣綜合優化第 9 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "下一步：三習慣綜合優化第 10 次 / #合理性" in strict_log


def test_hcs_plus_integrated_final_reasonability_verification_strategy_is_recorded():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "pipeline-mode-contract.md").read_text(encoding="utf-8")

    assert "D98：三習慣綜合優化第 10 次" in state
    assert "## 三習慣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略" in state
    assert "契約矩陣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略" in contract
    for expected in [
        "合理性收尾",
        "核心目標",
        "使用者決策用途",
        "維護者合併判斷",
        "契約安全邊界",
        "完成定義",
        "三輪 HCS 思考習慣",
        "十次三習慣綜合優化",
        "每批至少一次實際檔案修改與驗證",
        "最終專案內容",
        "決策紀錄",
        "風險與驗收標準",
        "下一步可執行行動",
        "驗證門檻",
        "聚焦測試",
        "回歸集合",
        "diff check",
        "strict log",
        "狀態表",
        "契約章節",
        "維護策略",
        "文件與測試契約優先",
        "例外升級",
        "定期複檢",
        "完成只代表 HCS Plus 自主優化流程完成",
        "不得把第 10 次收尾解讀為 runtime 安全或使用者理解已驗證",
    ]:
        assert expected in contract
    assert "## 三習慣綜合優化第 10 次" in strict_log
    for habit in ["合理性", "可驗證性", "制定策略"]:
        marker = f"### 綜合 / 三習慣綜合優化第 10 次 / #{habit}"
        assert marker in strict_log
        section = strict_log.split(marker, 1)[1].split("\n### ", 1)[0]
        assert "核心判斷" in section
        assert "落地修改" in section
        assert "驗證方式" in section
        assert "狀態：完成" in section
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state
    assert "## HCS Plus 自主優化完成摘要" in state
    assert "完成狀態：完成" in state
    assert "已完成十次 3 思考習慣綜合優化" in state
    assert "最終專案內容" in state
    assert "決策紀錄" in state
    assert "風險與驗收標準" in state
    assert "下一步可執行行動" in state
    assert "下一步：完成後維護 / 定期複檢契約矩陣" in strict_log


def test_hcs_plus_critical_thinking_round_has_closing_checkpoint():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 1 輪批判思考收尾" in strict_log
    assert "已完成：26/26" in strict_log
    assert "下一步：第 1 輪 / 創意思考 / #學習科學" in strict_log
    assert "| 1 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
    assert "| 1 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 1 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 1 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 1 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 1 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 1 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 1 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 1 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 1 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 1 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 1 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 1 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 1 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 1 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 1 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 1 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 2 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 2 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 2 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 2 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 2 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 2 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 2 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 2 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 2 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
    assert "| 2 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 2 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 2 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 2 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 2 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 2 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 2 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 2 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 2 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 2 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 2 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 2 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 2 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 2 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 2 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 2 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 3 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 3 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 3 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 3 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 3 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 3 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 3 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 3 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 3 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
    assert "| 3 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 3 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 3 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 3 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 3 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 3 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 3 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 3 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 3 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 3 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 3 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 3 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 3 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 3 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 3 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 3 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 | #可驗證性、#溝通設計、#系統圖像 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 2 | #證據基礎、#受眾、#責任 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 3 | #偏誤降低、#學習科學、#制定策略 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 4 | #目的、#效用、#合理性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 5 | #限制條件、#決策樹、#最佳化 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 6 | #來源品質、#情境脈絡、#批判 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 7 | #估算、#信賴區間、#詮釋框架 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 8 | #相關性、#描述統計、#顯著性 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 9 | #機率、#迴歸、#謬誤 | 完成 |" in state
    assert "| 綜合 | 三習慣綜合優化 10 | #合理性、#可驗證性、#制定策略 | 完成 |" in state


def test_hcs_plus_creative_thinking_round_has_closing_checkpoint():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 1 輪創意思考收尾" in strict_log
    assert "已完成：17/17" in strict_log
    assert "下一步：第 1 輪 / 溝通思考 / #受眾" in strict_log
    assert "| 1 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 1 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 1 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 1 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 1 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 1 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 1 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 1 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 1 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 1 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 1 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 2 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 2 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 2 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 2 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 2 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 2 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 2 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 2 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 2 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
    assert "| 2 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 2 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 2 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 2 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 2 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 2 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 2 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 2 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 2 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 2 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 2 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 2 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 2 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 2 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 2 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 2 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 3 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 3 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 3 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 3 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 3 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 3 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 3 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 3 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 3 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state


def test_hcs_plus_communication_thinking_round_has_closing_checkpoint():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 1 輪溝通思考收尾" in strict_log
    assert "已完成：10/10" in strict_log
    assert "下一步：第 1 輪 / 互動思考 / #倫理考量" in strict_log
    assert "| 1 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 1 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 1 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 1 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 1 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 1 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 1 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 1 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 2 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 2 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 2 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 2 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 2 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 2 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 2 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 2 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 2 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
    assert "| 2 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 2 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 2 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 2 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 2 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 2 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 2 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 2 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 2 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 2 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 2 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 2 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 2 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 2 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 2 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 2 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 3 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 3 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 3 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 3 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 3 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 3 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 3 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 3 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 3 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state


def test_hcs_plus_interaction_thinking_round_has_closing_checkpoint():
    state = (ROOT / "docs" / "hcs-plus-optimization-state.md").read_text(encoding="utf-8")
    strict_log = (ROOT / "docs" / "hcs-plus-strict-habit-log.md").read_text(encoding="utf-8")

    assert "## 第 1 輪互動思考收尾" in strict_log
    assert "已完成：20/20" in strict_log
    assert "下一步：第 2 輪 / 批判思考 / #拆解問題" in strict_log
    assert "| 1 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 2 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 2 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 2 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 2 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 2 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 2 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 2 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 2 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 2 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
    assert "| 2 | 創意思考 | #學習科學、#限制條件、#類比 | 完成 |" in state
    assert "| 2 | 創意思考 | #演算法、#設計思考、#捷思法 | 完成 |" in state
    assert "| 2 | 創意思考 | #最佳化、#假說發展、#資料視覺化 | 完成 |" in state
    assert "| 2 | 創意思考 | #建模、#抽樣、#個案研究 | 完成 |" in state
    assert "| 2 | 創意思考 | #比較組、#介入研究、#訪談調查 | 完成 |" in state
    assert "| 2 | 創意思考 | #觀察研究、#研究複製 | 完成 |" in state
    assert "| 2 | 溝通思考 | #受眾、#組成、#語意含義 | 完成 |" in state
    assert "| 2 | 溝通思考 | #組織結構、#專業性、#論點 | 完成 |" in state
    assert "| 2 | 溝通思考 | #溝通設計、#表達、#媒介、#多媒體 | 完成 |" in state
    assert "| 2 | 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷 | 完成 |" in state
    assert "| 2 | 互動思考 | #複雜因果、#湧現特性、#分析層次 | 完成 |" in state
    assert "| 2 | 互動思考 | #網絡、#系統動力學、#系統圖像 | 完成 |" in state
    assert "| 2 | 互動思考 | #談判、#說服、#形塑行為 | 完成 |" in state
    assert "| 2 | 互動思考 | #從眾、#差異、#情緒智商 | 完成 |" in state
    assert "| 2 | 互動思考 | #領導原則、#權力動態、#責任 | 完成 |" in state
    assert "| 2 | 互動思考 | #自我覺察、#制定策略 | 完成 |" in state
    assert "| 3 | 批判思考 | #拆解問題、#問對問題、#差距分析 | 完成 |" in state
    assert "| 3 | 批判思考 | #變數分析、#偏誤辨識、#偏誤降低 | 完成 |" in state
    assert "| 3 | 批判思考 | #決策樹、#目的、#效用 | 完成 |" in state
    assert "| 3 | 批判思考 | #信賴區間、#相關性、#描述統計 | 完成 |" in state
    assert "| 3 | 批判思考 | #機率、#迴歸、#顯著性 | 完成 |" in state
    assert "| 3 | 批判思考 | #證據基礎、#演繹、#歸納 | 完成 |" in state
    assert "| 3 | 批判思考 | #謬誤、#來源品質、#情境脈絡 | 完成 |" in state
    assert "| 3 | 批判思考 | #批判、#估算、#詮釋框架 | 完成 |" in state
    assert "| 3 | 批判思考 | #合理性、#可驗證性 | 完成 |" in state
