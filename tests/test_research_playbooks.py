def test_research_playbook_registry_mirrors_pipeline_modes():
    from pipeline_modes import get_pipeline_definition
    from research_playbooks import get_playbook, list_playbooks

    playbooks = {item["id"]: item for item in list_playbooks()}

    for pipeline_id in ("v1", "v2", "v3", "v4"):
        definition = get_pipeline_definition(pipeline_id)
        playbook = get_playbook(pipeline_id)
        assert playbook["id"] == pipeline_id
        assert playbook["label"] == definition["label"]
        assert playbook["pipeline_id"] == pipeline_id
        assert playbook["agent_sequence"] == list(definition["agents"])
        assert playbook["category"] in {"deep_research", "trading", "contrarian", "event_driven"}
        assert pipeline_id in playbooks


def test_research_playbook_registry_exposes_non_pipeline_workflows():
    from research_playbooks import get_playbook, list_playbooks

    playbooks = {item["id"]: item for item in list_playbooks()}

    for playbook_id in ("investment-checklist", "thesis-tracker", "portfolio-review", "quality-screen"):
        playbook = get_playbook(playbook_id)
        assert playbook["id"] == playbook_id
        assert playbook["pipeline_id"] is None
        assert playbook["gates"]
        assert playbook["output_contract"]
        assert playbook_id in playbooks

    assert "鏡子測試" in get_playbook("investment-checklist")["gates"]
    assert "核心假設" in get_playbook("thesis-tracker")["output_contract"]


def test_pipeline_modes_can_return_matching_playbook_summary():
    from pipeline_modes import get_pipeline_playbook_summary

    summary = get_pipeline_playbook_summary("v3")

    assert summary["id"] == "v3"
    assert summary["pipeline_id"] == "v3"
    assert summary["category"] == "contrarian"
    assert "泡沫" in summary["label"]
