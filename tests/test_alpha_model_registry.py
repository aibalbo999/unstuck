import pytest

from alpha_model_registry import get_alpha_model, list_alpha_models, model_for_pipeline


def test_alpha_model_registry_wraps_pipeline_modes_as_versioned_models():
    model = model_for_pipeline("v1")

    assert model["id"] == "mode-a-deep-research"
    assert model["pipeline_id"] == "v1"
    assert model["version"] == "alpha_model.v1"
    assert model["free_mode_policy"]["max_debate_rounds"] == 1
    assert model["minimum_data_confidence"] >= 60
    assert "thesis" in model["required_outputs"]
    assert "invalidation_trigger" in model["required_outputs"]


def test_alpha_model_registry_lists_all_pipeline_models_and_rejects_unknown():
    models = list_alpha_models()

    assert {model["pipeline_id"] for model in models} >= {"v1", "v2", "v3", "v4"}
    assert get_alpha_model("mode-d-event-swing")["pipeline_id"] == "v4"
    with pytest.raises(KeyError):
        get_alpha_model("unknown-model")
