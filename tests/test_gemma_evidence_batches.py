import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from gemma_evidence_batches import (EvidenceBatchInvalid, batch_input_tokens, evidence_appendix,
                                   plan_batches, prompt_payload, validate_observations)


def prompt_fixture():
    value = {"company": {"ticker": "TEST", "name": "目標公司"}, "unit_contract": {"price": "TWD"},
             "data_trust": {"status": "partial", "notes": ["缺漏不能當成零"]},
             "source_freshness": {"as_of": "2026-09-11", "stale": False},
             "observations": [{"date": "2026-09-11", "net_buy": -i, "url": f"https://source.test/{i}",
                               "text": "風險與反證不可省略。" * 30, "empty": None, "zero": 0, "flag": False} for i in range(80)]}
    return "【財務資料 JSON】\n" + json.dumps(value, ensure_ascii=False) + "\n\n【使用規則】\n原文規則及前序分析"


def answer(batch):
    row = batch["records"][0]
    return {"batch_id": batch["batch_id"], "observations": [{"record_id": row["record_id"], "quote": row["text"][:30]}]}


def test_batches_fit_and_preserve_every_source_record_with_stable_cache_keys():
    prompt = prompt_fixture()
    batches = plan_batches(22, prompt)
    assert 1 < len(batches) <= 8
    assert all(batch_input_tokens(b) <= 9000 for b in batches)
    source = prompt_payload(prompt)
    paths = []
    for batch in batches:
        for row in batch["records"]:
            value = source
            for part in row["path"].strip("/").split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert json.loads(row["text"]) == value
            paths.append(row["path"])
    assert len(set(paths)) == len(paths)
    # Every observation appears once, including dates, links, signs, null/0/false.
    observations = [p for p in paths if p.startswith("/observations/")]
    assert observations == [f"/observations/{i}" for i in range(80)]
    assert batches == plan_batches(22, prompt)
    assert batches[0]["batch_id"] != plan_batches(23, prompt)[0]["batch_id"]
    assert batches[0]["batch_id"] != plan_batches(22, prompt + "upstream changed")[0]["batch_id"]


@pytest.mark.parametrize("mutation", ["quote", "reference", "identity", "extra"])
def test_rejects_invented_or_mismatched_evidence(mutation):
    batch = plan_batches(23, prompt_fixture())[0]
    response = answer(batch)
    if mutation == "quote": response["observations"][0]["quote"] = "改寫淨買超 9999999"
    if mutation == "reference": response["observations"][0]["record_id"] = "r999999"
    if mutation == "identity": response["batch_id"] = "another company"
    if mutation == "extra": response["recommendation"] = "BUY"
    with pytest.raises(EvidenceBatchInvalid): validate_observations(batch, response)


def test_partial_batches_are_not_adopted_and_single_oversize_record_is_not_truncated():
    batches = plan_batches(22, prompt_fixture())
    with pytest.raises(EvidenceBatchInvalid): evidence_appendix(batches, [answer(batches[0])])
    with pytest.raises(EvidenceBatchInvalid):
        plan_batches(22, '【財務資料 JSON】\n' + json.dumps({"source": "完整反證" * 10000}, ensure_ascii=False) + '\n\n【使用規則】')


def test_failed_batch_resumes_from_validated_cache(monkeypatch):
    from agent_runtime import gemma_evidence_runtime as runtime
    cache, calls = {}, []
    monkeypatch.setattr(runtime, "get_cache_json", lambda k: copy.deepcopy(cache.get(k)))
    monkeypatch.setattr(runtime, "set_cache_json", lambda k, v, ttl: cache.__setitem__(k, copy.deepcopy(v)))
    fail = [True]

    async def send(batch, context, rotator):
        calls.append(batch["batch_id"])
        if batch["batch_id"].endswith(":1") and fail[0]:
            raise runtime.AgentTransientError("offline provider failure")
        return answer(batch)

    monkeypatch.setattr(runtime, "call_batch_async", send)
    prompt = prompt_fixture()
    with pytest.raises(runtime.AgentTransientError):
        asyncio.run(runtime.collect_evidence_async(22, prompt, {}, object()))
    first = calls[0]
    fail[0] = False
    appendix = asyncio.run(runtime.collect_evidence_async(22, prompt, {}, object()))
    assert calls.count(first) == 1
    assert "僅供定位" in appendix


@pytest.mark.parametrize("entry", ["async", "sync_in_loop"])
@pytest.mark.parametrize("valid", [True, False])
def test_oversize_gemma_batches_then_integrates_with_full_fallback_prompt(monkeypatch, entry, valid):
    from agent_runtime import single_agent as agent
    from agent_runtime import gemma_evidence_runtime as runtime
    prompt = prompt_fixture()
    base = "完整整合來源與反證" + "原文" * 100
    calls = []
    monkeypatch.setattr(runtime, "GEMMA_EVIDENCE_BATCHING_ENABLED", True)
    monkeypatch.setattr(agent, "get_runtime_model_sequence", lambda *a: ["gemma-4-31b-it", "gemini-3-flash-preview"])
    monkeypatch.setattr(agent, "get_cached_agent_step", lambda *a: None)
    monkeypatch.setattr(agent, "store_cached_agent_step", lambda *a, **kw: None)
    monkeypatch.setattr(agent, "_build_model_prompt", lambda n, d, c, model, compact: prompt if model.startswith("gemma") else base)
    monkeypatch.setattr(runtime, "get_cache_json", lambda *a: None)
    monkeypatch.setattr(runtime, "set_cache_json", lambda *a: None)

    def batch(b, *args):
        calls.append(("batch", b["batch_id"]))
        if not valid:raise EvidenceBatchInvalid("invented quote")
        return answer(b)
    async def batch_async(*args):return batch(*args)
    def integrate(n, c, r, model, text, **kw):
        calls.append((model, text))
        assert model == "gemini-3-flash-preview"
        assert (text.startswith(base) and "僅供定位" in text) if valid else text == base
        return "來源核驗後的整合分析" * 30
    async def integrate_async(*args, **kw):return integrate(*args, **kw)
    monkeypatch.setattr(runtime, "call_batch", batch)
    monkeypatch.setattr(runtime, "call_batch_async", batch_async)
    monkeypatch.setattr(agent, "_run_agent_once", integrate)
    monkeypatch.setattr(agent, "_run_agent_once_async", integrate_async)
    async def run():
        fn = agent.run_single_agent if entry == "sync_in_loop" else agent.run_single_agent_async
        result = fn(22, {}, {}, SimpleNamespace(keys=["offline"]))
        return await result if entry == "async" else result
    assert "整合分析" in asyncio.run(run())
    assert len([x for x in calls if x[0] == "batch"]) == (len(plan_batches(22, prompt)) if valid else 1)


@pytest.mark.parametrize("entry", ["async", "sync"])
def test_real_transport_bypasses_unverified_cache_and_preserves_source(monkeypatch, entry):
    import llm_transport as transport
    from llm_evidence_request import is_evidence_request
    from agent_runtime import gemma_evidence_runtime as runtime
    batch = plan_batches(23, prompt_fixture())[0]
    batch["records"][0]["text"] += ' 買進 100 張，short exposure 僅是原文'
    calls = []
    def generate(**kw):
        assert is_evidence_request()
        assert "買進 100 張，short exposure" in kw["contents"]
        assert kw["config"].http_options.timeout == 60000
        calls.append(kw)
        return SimpleNamespace(text=json.dumps(answer(batch), ensure_ascii=False))
    async def generate_async(**kw):return generate(**kw)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate),
                             aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_async)))
    monkeypatch.setattr(transport, "generation_client", lambda *args: client)
    monkeypatch.setattr(transport, "get_cached_llm_response", lambda *a: pytest.fail("unvalidated cache read"))
    monkeypatch.setattr(transport, "store_llm_response", lambda *a, **kw: pytest.fail("unvalidated cache write"))
    class Rotator:
        keys = ["offline"]
        def get_key(self, model, tokens):
            assert model == "gemma-4-31b-it" and tokens == batch_input_tokens(batch)
            return "offline"
        async def async_get_key(self, *args):return self.get_key(*args)
    result = asyncio.run(runtime.call_batch_async(batch, {}, Rotator())) if entry == "async" else runtime.call_batch(batch, {}, Rotator())
    assert result == answer(batch) and len(calls) == 1
    assert not is_evidence_request()


@pytest.mark.parametrize("entry", ["async", "sync"])
def test_cancellation_while_waiting_for_key_never_sends_request(monkeypatch, entry):
    from agent_runtime import gemma_evidence_runtime as runtime
    cancelled = [False]
    class Cancelled(Exception):pass
    def check():
        if cancelled[0]:raise Cancelled()
    class Rotator:
        keys = ["offline"]
        def get_key(self, *args):
            cancelled[0] = True
            return "offline"
        async def async_get_key(self, *args):return self.get_key(*args)
    monkeypatch.setattr(runtime, "generate_content", lambda *a: pytest.fail("sent after cancellation"))
    monkeypatch.setattr(runtime, "generate_content_async", lambda *a: pytest.fail("sent after cancellation"))
    batch = plan_batches(22, prompt_fixture())[0]
    with pytest.raises(Cancelled):
        if entry == "async":asyncio.run(runtime.call_batch_async(batch, {"_cancel_check": check}, Rotator()))
        else:runtime.call_batch(batch, {"_cancel_check": check}, Rotator())


def test_batch_response_is_not_final_agent_model_and_usage_remains_recorded(monkeypatch):
    from model_execution_provenance import model_executions_from_events
    import api_usage_recorders as usage
    recorded = []
    monkeypatch.setattr(usage, "record_api_usage", lambda **kw: recorded.append(kw))
    def event(phase, model):
        return {"phase": phase, "agent_num": 22, "pipeline_id": "v4", "metadata": {"model_id": model}}
    batch = event("gemma_evidence_response", "gemma-4-31b-it")
    assert model_executions_from_events([{"payload": batch}], "v4") == {}
    events = [event("gemma_evidence_request", "gemma-4-31b-it"), batch,
              event("llm_model_response", "gemini-3-flash-preview")]
    result = model_executions_from_events([{"payload": e} for e in events], "v4")[22]
    assert result["model_id"] == "gemini-3-flash-preview"
    assert "gemma-4-31b-it" in result["provider_call_models"]
    usage.record_runtime_event_usage("test", events[0])
    usage.record_runtime_event_usage("test", batch)
    assert [e["status"] for e in recorded] == ["attempt", "success"]


def test_repair_and_other_roles_keep_original_routing_and_full_context(monkeypatch):
    from agent_runtime import gemma_evidence_runtime as runtime
    monkeypatch.setattr(runtime, "GEMMA_EVIDENCE_BATCHING_ENABLED", True)
    prompt = prompt_fixture()
    for role, context in [(13, {}), (22, {"_audit_retry_instruction": "full repair"}),
                          (23, {"_identity_retry_instruction": "correct identity"}),
                          (22, {"_model_sequence_override": {22: ["gemma-4-31b-it"]}})]:
        assert not runtime.should_batch(role, "gemma-4-31b-it", prompt, context)


def test_full_fallback_prompt_is_preserved_when_appendix_does_not_fit(monkeypatch):
    from agent_runtime import gemma_evidence_runtime as runtime
    model, prompt, notes = "gemini-3-flash-preview", "來源與反證" * 500, "附加摘錄" * 200
    limit = runtime.estimate_agent_input_tokens(22, model, prompt)
    monkeypatch.setitem(runtime.MODEL_INPUT_TOKEN_LIMITS, model, limit)
    context = {"pipeline_id": "v4"}
    assert runtime.append_if_capacity_allows(22, model, prompt, notes, context) == prompt
    event = context["_runtime_events"][-1]
    assert event["metadata"]["evidence_appendix_attached"] is False
    assert "略過附加摘錄" in event["message"]
    monkeypatch.setitem(runtime.MODEL_INPUT_TOKEN_LIMITS, model, limit * 3)
    assert runtime.append_if_capacity_allows(22, model, prompt, notes, context) == prompt + notes
    assert context["_runtime_events"][-1]["metadata"]["evidence_appendix_attached"] is True


def test_batch_phases_record_planning_quota_and_no_new_usage_for_cache(monkeypatch):
    import api_usage_recorders as usage
    recorded = []
    monkeypatch.setattr(usage, "record_api_usage", lambda **kw: recorded.append(kw))
    for phase in ("gemma_evidence_call", "gemma_evidence_error", "gemma_evidence_cache_hit"):
        usage.record_runtime_event_usage("test", {"phase": phase, "metadata": {
            "model_id": "gemma-4-31b-it", "call_purpose": "evidence_batch", "error_category": "quota"}})
    assert [(row["status"], row["units"]) for row in recorded] == [("planned", 0), ("quota_error", 0)]
    assert all(row["metadata"]["call_purpose"] == "evidence_batch" for row in recorded)
