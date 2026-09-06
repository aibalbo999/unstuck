# 四模式內容可信度第一批 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除占位 DCF、阻止上游修復後發布舊下游結論，並保存可回查的新聞評估與精確證據匹配。

**Architecture:** 沿用既有 financial tools、pipeline groups、final-audit graph node 與 evidence gate。純函式負責來源／版本／引用判斷，runtime 僅執行有界修復；新結果必須通過同一契約，legacy snapshot 不回寫。

**Tech Stack:** Python、Pydantic、LangGraph、pytest、Jinja HTML／Markdown；隔離 SQLite 與無網路測試。

---

核准規格：`docs/superpowers/specs/2026-09-06-analysis-credibility-followup-design.md`。

定版驗證：完整收集 276 檔、9,737 項並分四個隔離程序全部重跑，9,716 passed、21 skipped、75 subtests passed。另行唯讀 artifact replay 1 passed，9 個原始檔案雜湊未變。獨立 spec／quality review 已通過；細節與跳過範圍見 `docs/four-mode-credibility-delivery-2026-09-06.md`。Tasks 1–6 原建議的逐組提交，最終整合為 Task 7.6 的單一 scoped 實作提交，維持跨模組契約一致；不 push／merge／restart。

## 執行與檔案協作

- 正式 checkout：`/Volumes/X10 Pro Mac/stock-agent`。所有 shell 使用 `/bin/sh`、`login=false` 並指定 workdir；不可使用 app 舊的 Desktop 路徑。
- Python 沿用 `/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python`。若切換 worktree，直接以這個 Python 執行該 worktree 的測試 runner，不複製 `.env` 或正式 DB。
- 一般命令：`"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B tests/run_prompt_boundary_tests.py <test files> -q -p no:cacheprovider --tb=short`。
- 已驗證基線：audit repair／state freshness／repair context／price targets／daily OHLC／quant warning／prompt budget 共 7 檔，57 passed。
- 量化 owner：Tasks 1–2；依賴 owner：Task 3；新聞 owner：Tasks 4–5；主工作：Task 6 與 Task 7 整合。僅不重疊檔案可並行，所有共用接線由主工作協調。
- `final_audit.py` 保留主工作接線；`agent_runtime/audit_repair.py`、`workflow_state.py`／`workflow_context.py`／`workflow_services.py` 由依賴 owner 編輯。新聞 owner 的 metadata 欄位由主工作於其完成後整合到 workflow adapters。
- 子工作不操作 Git index／commit，主工作在 spec review、quality review 與驗證後逐組提交。不得修改正式 DB／報告／`.env`、啟動重跑批次或調整模型／額度。

## Task 1：原始金融輸入與共用計算

**Files:** 新增 `backend/quant_input_contract.py`、`backend/quant_metric_contract.py`、`tests/test_quant_metrics_contract.py`；修改 `backend/quant_engine.py`、`backend/financial_tools.py`，必要時局部抽出原有計算 helper，不能新增另一套估值公式。

- [x] **1.1 RED：寫原始股數／負 FCF／缺輸入測試並確認失敗。**

```python
from quant_engine import QuantEngine

def test_negative_raw_fcf_never_uses_sample_cash_flows():
    data = {
        "current_price": 208.0, "shares_raw": 66_000_000,
        "shares_outstanding": "NT$0.66億 (0.07B)",
        "market_cap_raw": 13_728_000_000,
        "total_debt_raw": 2_898_000_000, "total_cash_raw": 500_000_000,
        "free_cash_flow_raw": -461_411_616,
    }
    result = QuantEngine.compute_all(data)
    assert result["dcf_intrinsic_value"] is None
    assert result["margin_of_safety"] is None
    assert result["metric_status"]["dcf"]["status"] == "unavailable"
```

執行 `tests/test_quant_metrics_contract.py`；舊版應因仍返回占位數字失敗，而非缺依賴／測試拼字錯誤。

- [x] **1.2 GREEN：新增純輸入與可用性邊界。** 數字驗證使用下面的有限值原語，path／單位以原始欄位白名單記錄，不呼叫格式化字串剝字 parser：

```python
import math

def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None

def metric_status(reasons):
    return {"status": "unavailable" if reasons else "available",
            "reason_codes": list(dict.fromkeys(reasons))}
```

`read_quant_inputs(data)` 回傳 facts、input_provenance、各指標 reason codes。raw missing 不讀格式化欄位；具單位歷史序列可沿用既有來源選擇，但不得跨較舊資料蓋掉最新已知負 FCF。零債務／零現金有效，缺失則 DCF net-debt 不可用；WACC、PE 只依自身必要輸入決定。

- [x] **1.3 GREEN：讓 QuantEngine 和 financial tool context 使用同一份 verified inputs／既有算式。** 新輸出必須包含 `contract_version="quant_metrics.v2"`、`metric_status`、`input_provenance`、unit contract 與獨立 assumptions。舊數值 keys 保留；不可用 DCF／margin_of_safety 為 None。刪除示範 financial defaults，保留已配置的政策假設並標記。
- [x] **1.4 RED→GREEN 邊界矩陣。** 加正 FCF、零債務、淨現金、缺 debt/cash/shares、NaN/Infinity/bool、EPS<=0、raw與格式化值衝突、只缺一指標的案例。正值結果與 `financial_tools.calculate_dcf` 同輸入比較，不能把原錯誤數值改成測試預期。
- [x] **1.5 VERIFY／REVIEW／COMMIT。** 跑新檔及 `tests/test_financial_dcf_scenarios.py`、`tests/test_financial_tool_utils.py`，完成 spec review 後做 quality review，再提交 `fix: enforce raw financial inputs for quantitative metrics`。

## Task 2：同方法 DCF 稽核與可用性顯示

**Files:** 修改 `backend/final_audit_dcf.py`、`backend/reporting/analysis_overlays.py`、`backend/reporting/quant_warning.py`；新增 `tests/test_final_audit_dcf.py`；相關既有 tests：`tests/test_scenario_sentiment_peer_bear.py`、`tests/test_audit_rules.py`、`tests/test_report_quant_warning.py`。

- [x] **2.1 RED：以 relative targets 與獨立 DCF 產生誤比反例。**

```python
def test_relative_targets_are_not_dcf_scenarios():
    from final_audit_dcf import dcf_conflict_warnings
    analyses = {4: "熊市目標 NT$174.5，基本 NT$216.1，牛市 NT$241；DCF 不作主要定價。"}
    structured = {4: {"primary_method": "relative_valuation",
        "price_targets": {"熊市情境": 174.5, "基本情境": 216.1, "牛市情境": 241},
        "dcf_scenarios": {"bear": 9.39, "base": 14.34, "bull": 20.59}}}
    data = {"quant_metrics": {"fallback_fields": ["free_cash_flows"],
        "dcf_scenarios": {name: {"intrinsic_value": value} for name, value in
                          (("bear", 9.39), ("base", 14.34), ("bull", 20.59))}}}
    assert not dcf_conflict_warnings(analyses, data, structured)
```

先定義向後相容的 optional structured argument，再確認錯誤比較本身的 assertion 失敗，不能把 signature error 當行為 RED。

- [x] **2.2 GREEN：`trusted_dcf_scenarios(quant)` 只回傳可用契約的同情境數字。** legacy fact fallback、unknown contract、單位無法判定均不當可信 DCF；不從前三個 prose 價格推斷。`dcf_audit_findings(analyses, data, structured_outputs, valuation_agent=4)` 回傳具 agent／severity／message 的 findings，供 Task 7 分流；保留相容 warning facade。
- [x] **2.3 RED→GREEN：renderer/fallback 不可復活數字。** overlay 遇不可用／legacy fact defaults 不產生有效價格；warning 顯示 reason。明確可信 DCF mismatch 維持原容差。聲稱系統有可用DCF但無可信來源的 structured claim 必須給 critical，不能只關掉 warning。
- [x] **2.4 VERIFY／REVIEW／COMMIT。** 跑上述全部檔案，依序 spec／quality review，提交 `fix: audit and render only comparable DCF values`。

## Task 3：有界依賴重建與原子採用

**Files:** 新增 `backend/analysis_dependencies.py`、`backend/agent_runtime/repair_transaction.py`、`tests/test_repair_dependencies.py`；修改 `backend/agent_runtime/audit_repair.py`、`repair_loop.py`、公開 `legacy_agent_runner.py`、`backend/context_dependencies.py`、`backend/workflow_state.py`、`workflow_context.py`、`workflow_services.py`、`workflow_quality_drafts.py` 的必要接線。未需修改原先候選的 `repair_state.py`。保留主工作的 `final_audit.py`。

- [x] **3.1 RED：先測群序、同群排除與聯集。**

```python
def dependency_closure(pipeline, requested):
    from analysis_dependencies import downstream_agent_numbers, pipeline_agent_order
    context = {"pipeline_id": pipeline}
    pending = set(requested)
    for agent in requested:
        pending.update(downstream_agent_numbers(agent, context))
    return tuple(agent for agent in pipeline_agent_order(context) if agent in pending)

def test_dependency_order_uses_groups_not_agent_numbers():
    assert dependency_closure("v1", {4}) == (4, 6, 21, 7)
    assert dependency_closure("v1", {2, 4}) == (2, 3, 20, 4, 5, 6, 21, 7)
    assert dependency_closure("v2", {14}) == (14, 21, 16)
    assert dependency_closure("v3", {18}) == (18, 21, 19)
    assert dependency_closure("v4", {22}) == (22, 24)
```

- [x] **3.2 GREEN：純依賴計畫及 output fingerprint。** 實際共用 `pipeline_agent_order`／`downstream_agent_numbers` 與 `RepairRound`，依既有 groups 展平，僅包含 requested agents 與其實際下游；執行時用 pending set 動態啟用閉包，不因未變輸出觸發額外重算。上例只展示純依賴閉包，真正的重建順序另由 sync／async runtime 測試。正文先排除 generated audit section，structured output 穩定 JSON hash；忽略 timing／telemetry。
- [x] **3.3 RED：由真實 finalize sync／async 驅動假模型，修復 4 後檢查 6／21／7 的讀入與輸出新版 sentinel，5 呼叫數零。** 加上游不變、多上游、下游失敗、取消、deferred、修復次數用盡。模型／IO 可 mock，不能 mock 掉待驗證的依賴／transaction 本身。
- [x] **3.4 GREEN：在 final-audit 一致性單位暫存修改。** `repair_transaction` 複製分析狀態及 typed reports，不複製rotator/client/locks。成功只提交完整 accepted maps、parsed、風險與來源版本；失敗保留先前一致 state 並加入阻擋，不回復為當次成功。sync／async 共用計畫，重算用既有品質檢查／額度次數。
- [x] **3.5 RED→GREEN：checkpoint reducer round trip 與冷恢復。** 對需要刪除的 maps 支援局部明確 replacement，不全面改一般並行 merge；清本輪已解除 blocker，不清外部未知 blocker。typed reports／分析RAG／parsed 不得復活；原始RAG與外部風險保留。draft fingerprint 含 live upstream；step cache 此欄位交新聞 owner／主工作整合。
- [x] **3.6 OPTIONAL COVERAGE REPAIR 接口。** Task 7 新增 `coverage_repair_agent_issues` 與既有 critical repair map 分開。finalizer 在此 map 非空時可有界重試；只有 coverage 耗盡仍 warning，不把所有 warning 推為 critical；有真正 critical 或 stale 下游未完成則保持阻擋。
- [x] **3.7 VERIFY／REVIEW／COMMIT。** 跑新檔及 audit repair、repair context/state freshness、context digest dependencies、workflow checkpoint/quality draft tests。先spec再quality review，提交 `fix: rebuild dependent analyses atomically after repair`。

## Task 4：最後送出 prompt 的來源 manifest

**Files:** 新增 `backend/market_context_manifest.py`、`tests/test_market_context_manifest.py`；修改 `backend/agent_runtime/prompting.py`、`single_agent.py`、`step_cache.py`，必要時新增 runtime wrapper helper，不膨脹既有大檔。`workflow_*` 接線由主工作整合。

- [x] **4.1 RED：完整來源、compact 被省略、budget 截斷反例。**

```python
def test_partial_source_block_is_not_visible():
    from market_context_manifest import visible_source_items
    block = {"id": "source-1", "text": "完整來源：央行利率新聞與來源網址"}
    assert visible_source_items(block["text"], [block]) == [block]
    assert visible_source_items(block["text"][:8], [block]) == []
```

- [x] **4.2 GREEN：runtime-issued ID 與完整區塊。** ID以input fingerprint＋canonical path/index＋item content hash產生；`visible_source_items(final_prompt, blocks)` 只收完整相符區塊。`prompting.build_prompt` 最後budget完成後保存當次manifest與prompt hash。只保存bounded來源紀錄，不保存secret或完整prompt；不能讓模型控制id、可用性或來源數。
- [x] **4.3 RED→GREEN：每個 primary/fallback/cache/repair 都綁成功版本。** `single_agent` successful output才採用該attempt manifest；失敗版本不污染accepted metadata。step-cache payload附manifest及upstream hash，legacy缺manifest對新契約視為cache miss，舊讀取仍可用。資料fingerprint排除manifest及最終snapshot hash以免循環。
- [x] **4.4 VERIFY／REVIEW／COMMIT。** 真正 build_prompt token裁切、compact=2/8、來源字串可能重複、跨snapshot／agent／attempt、cache命中與冷恢復。先spec再quality review，提交 `feat: bind market citations to visible prompt evidence`。

## Task 5：新聞評估 schema、validator、保存與顯示

**Files:** 新增 `backend/market_context_assessment.py`、`tests/test_market_context_assessment.py`；修改 `backend/structured_output_recommendation_outputs.py`、`structured_output_normalize_dispatch.py`、`structured_output_parser.py`、`structured_output_report_text.py`、`data_trust_snapshot.py`、必要的snapshot size governance、`prompts/runtime_rules.json`。主工作保留 `final_audit.py`。

- [x] **5.1 RED：A7/B16/C19 roundtrip與legacy None。** 測 `impact` 三值、非空 reason、valid/invalid refs，normalize→parsed→snapshot→HTML/Markdown均保留。D不新增欄位要求。
- [x] **5.2 GREEN：最小共用schema與pure validator。** `market_context_assessment` 每個source包含 `impact: affects_conclusion|no_material_impact|not_assessed`、`reason`、`source_refs`。`assess_final_market_context(context)` 回傳 `status/warnings/critical/repair_agent_issues/coverage_repair_agent_issues/checks/assessment`；missing來源或全部prompt省略→warning、不抓外部資料；可見來源但缺評估→repairable coverage warning；引用不存在/不可見/跨版本卻聲稱已評估→critical。reason／visibility由各自責任邊界決定，不固定補無影響。
- [x] **5.3 GREEN：新context版本與prompt要求。** A/B/C新工作標記 `market_context.v1`，Agent19規則同步；D及legacy缺記錄不強迫新visibility。schema None僅作legacy相容，不代表新版通過。普通coverage耗盡顯示not_assessed限制，不能默默將假的impact替換成合法值。
- [x] **5.4 VERIFY／REVIEW／COMMIT。** 跑新檔及structured models/parser/normalization、snapshot sanitizer、report conformance與prompt budget tests；先spec再quality review，提交 `feat: require traceable final market context assessments`。

## Task 6：SMA／compact horizon 與評分分類

**Files:** 新增 `backend/evidence_technical_claims.py`、`tests/test_evidence_exit_gate_technical.py`；修改 `backend/evidence_exit_gate.py`、`evidence_exit_gate_claims.py`，必要時將既有horizon純判斷移到小型helper以守住350行限制。

- [x] **6.1 RED：透過公開 gate 寫 exact path 正反例。**

```python
from evidence_exit_gate import evaluate_report_evidence

def test_sma_support_only_matches_its_exact_period():
    snapshot = {"data": {"technical_indicators": {
        "availability": "available", "as_of": "2026-09-04", "source": "daily_market_data", "sma_20": 205.425,
        "volume_sma_20": 205.4, "sma_200": 205.4}, "risk_price": 205.4}}
    result = evaluate_report_evidence("支撐位：205.4 元（20日均線）", snapshot,
                                      sample_ratio=1.0, min_sample=1)
    claim = result["sampled_claims"][0]
    assert claim["matched_path"] == "data.technical_indicators.sma_20"
    assert claim["candidate_count"] == 1
```

- [x] **6.2 GREEN：精確路徑與 fail-closed分流。** SMA新增exact selector不能用normalized substring；唯一相鄰價格/期間，拒EMA、多期間多價位、新聞/券商/混合語意與缺可用來源。selector已辨識但欄位缺失時不能回riskprice。compact3/6/12僅在最終建議列綁自身horizon，多組需逐對明確切分。
- [x] **6.3 RED→GREEN：兩種過熱評分 exact label分流。** 即使其他scalar同值，`情緒過熱評分`、`過熱評分` 仍unverifiable／analysis_metadata；confidence與其他分析假設邊界不變。加SMA真mismatch、null、缺欄、nearby日期、其他期間同值與legacy無parsed反例。
- [x] **6.4 VERIFY／REVIEW／COMMIT。** 完整evidence相關tests＋import/architecture guards，先spec再quality review，提交 `fix: bind explicit SMA and recommendation horizon evidence`。

## Task 7：共用接線、回歸與交付

**Files:** 主工作修改 `backend/final_audit.py`、`analysis_jobs.py`／`prompt_builder.py`必要接線及各owner交付的workflow metadata adapter；新增 `tests/test_analysis_credibility_integration.py`；更新架構圖、核准spec狀態及本計畫。

- [x] **7.1 RED→GREEN：稽核回傳分流。** 從 Task2 findings 將真正unavailable-DCF主張加到對應critical repair；同method warning保留。Task5 validator critical加入既有repair map，普通可修復coverage單獨放 `coverage_repair_agent_issues`。在沒有新market版本的legacy保留舊coverage檢查。
- [x] **7.2 RED→GREEN：保存／恢復一致性。** 新工作設定market版本；workflow context/state、draft、stepcache、snapshot、局部rerun adapter使用相同 manifest/assessment/provenance。metadata遺失視為未驗證，不從現況資料重造歷史。成功新output不被另一輪/agent的metadata覆蓋。
- [x] **7.3 回歸與唯讀fixture重放。** 將保存1623/2308輸入作資料副本，檢查占位DCF不再有效、精確SMA/horizon改善、真unknown保留。四模式長線/部位/空方/Neutral契約不退化；舊檔hash保持，不呼叫正式重跑API。
- [x] **7.4 全套驗證。** 先跑高風險跨層tests，再完整隔離runner；瀏覽器測試只有臨時資料與必要allowlist。實際skip分開列明，不將fake PG測試當live。
- [x] **7.5 雙階段總審查。** 按spec各節核對程式及測試後，另審code quality／持久化／信任邊界；發現問題先修並重新驗證，不以現有passed count代替新案例。
- [x] **7.6 提交與交付紀錄。** 只提交verified scoped code/tests/docs，`git diff --check`、secret/dirty scope檢查；不push／merge／restart，保留分支。交付清楚標示程式完成與尚未重啟／正式runtime驗收，並列PG/OOS/歷史重建後續範圍。

## 計畫自我檢核

- [x] 規格第2節對應Tasks1–2，第3節Task3，第4節Tasks4–5，第5節Task6，第6節Task7。
- [x] 公開介面／欄位命名固定；caller接線與legacy行為有owner，不靠implicit資料遺留。
- [x] 失敗案例、positive/negative邊界、隔離測試、spec/quality review及scoped commit均有步驟。
- [x] 外部環境、模型配額、歷史重建和正式發布沒有混入本批自動操作。
