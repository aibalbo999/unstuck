import json
from pathlib import Path


def test_usage_aware_profile_is_scoped_to_validated_roles():
    path = Path(__file__).resolve().parents[1] / "backend" / "model_routes_usage_aware_free.json"
    assert path.exists()
    profile = json.loads(path.read_text())
    assert profile["context_digest_model"] == "gemini-3.5-flash-lite"
    assert profile["tear_sheet_model"] == "gemini-3.5-flash-lite"
    for agent in [7, 16, 19, 24]:
        assert profile["agents"][str(agent)] == "gemini-3.8-flash"
        assert "gemini-3-flash-preview" in profile["agent_fallbacks"][str(agent)]
    assert profile["default_analysis_model"] == "gemma-4-31b-it"
    assert profile["input_token_limits"]["gemma-4-31b-it"] < profile["tpm_limits"]["gemma-4-31b-it"]
    assert profile["embedding_model"] == "gemini-embedding-2"
    assert profile["rpd_limits"] == {
        "gemma-4-31b-it": 11520, "gemini-3.8-flash": 16,
        "gemini-3-flash-preview": 16, "gemini-3.6-flash": 16,
        "gemini-3.5-flash-lite": 400, "gemini-embedding-2": 800,
    }
    assert profile["limit_basis"] == "local_operating_budgets_not_provider_entitlements"
    assert "gemini-3.7-flash" not in json.dumps(profile)


def test_efficiency_profile_balances_fallbacks_and_protects_minutes():
    from agent_catalog import AGENT_NAMES
    profile = json.loads((Path(__file__).resolve().parents[1] / 'backend/model_routes_usage_aware_free.json').read_text())
    assert {int(agent) for agent in profile['agent_fallbacks']}.issubset(AGENT_NAMES)
    assert profile['project_quota_assumption'] == 'user_declared_independent_free_projects'
    assert profile['assumed_project_count'] == 16
    assert profile['agent_fallbacks']['22'][0] != profile['analysis_fallback_models'][0]
    assert profile['agent_fallbacks']['16'][0] != profile['agent_fallbacks']['7'][0]
    assert profile['quota_max_attempts_per_model'] == 4
    assert profile['server_error_max_attempts'] == 2
    for model in profile['rpd_limits']:
        assert profile['tpm_limits'][model] > 0
        assert profile['rpd_limits'][model] == int(profile['assumed_provider_rpd'][model] * 0.8)
