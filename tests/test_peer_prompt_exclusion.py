"""Candidate-only numeric rows must not become a comparable peer claim in prompts."""

import json


def test_unverified_candidate_numbers_stay_in_snapshot_but_not_prompt_or_state_view():
    from prompt_builder import format_data_for_prompt
    from state_memory import initialize_agent_state, state_view_for

    data = {"ticker": "1605.TW", "company_name": "華新", "dynamic_peer_metrics": [
        {"ticker": "5016.TWO", "pe_ttm": 13.8, "business_comparability_verified_current": False},
        {"ticker": "2024.TW", "pe_ttm": 44.3, "business_comparability_verified_current": False},
        {"ticker": "2330.TW", "pe_ttm": 18.0, "comparison_status": "business_industry_matched"},
    ]}
    state = initialize_agent_state(data)
    for compact in (False, True):
        prompt = format_data_for_prompt(data, compact=compact)
        payload, _ = json.JSONDecoder().raw_decode(prompt[prompt.index("{"):])
        assert [row["ticker"] for row in payload["peer_context"]["dynamic_peer_metrics"]] == ["2330.TW"]
    assert [row["ticker"] for row in state_view_for(4, state)["peer_context"]["dynamic_peer_metrics"]] == ["2330.TW"]
    assert len(data["dynamic_peer_metrics"]) == 3
    assert len(state.peer_context["dynamic_peer_metrics"]) == 3
