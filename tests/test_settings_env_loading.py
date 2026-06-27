from __future__ import annotations

import importlib
import os
import sys


def _reload_grouped_settings():
    import settings

    for name in (
        "settings.app_config",
        "settings.models",
        "settings.providers",
        "settings.runtime_limits",
        "settings.security",
        "settings.storage",
    ):
        sys.modules.pop(name, None)
    return importlib.reload(settings)


def test_settings_package_loads_local_env_before_grouped_modules(tmp_path):
    import settings
    import settings.env as settings_env

    original_base_dir = settings_env.BASE_DIR
    original_model_routes_file = settings_env.DEFAULT_MODEL_ROUTES_FILE
    keys = [
        "DEFAULT_ANALYSIS_MODEL",
        "DEFAULT_DECISION_MODEL",
        "TASK_QUEUE_BACKEND",
        "OUTPUT_DIR",
    ]
    old_values = {key: os.environ.get(key) for key in keys}

    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "DEFAULT_ANALYSIS_MODEL=env-analysis-model",
                "DEFAULT_DECISION_MODEL=env-decision-model",
                "TASK_QUEUE_BACKEND=local",
                f"OUTPUT_DIR={tmp_path / 'reports'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        for key in keys:
            os.environ.pop(key, None)
        settings_env.BASE_DIR = tmp_path
        settings_env.DEFAULT_MODEL_ROUTES_FILE = tmp_path / "missing-model-routes.json"

        _reload_grouped_settings()
        import settings.app_config as app_config

        assert app_config.DEFAULT_ANALYSIS_MODEL == "env-analysis-model"
        assert app_config.DEFAULT_DECISION_MODEL == "env-decision-model"
        assert app_config.TASK_QUEUE_BACKEND == "local"
        assert app_config.OUTPUT_DIR == str(tmp_path / "reports")
    finally:
        settings_env.BASE_DIR = original_base_dir
        settings_env.DEFAULT_MODEL_ROUTES_FILE = original_model_routes_file
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reload_grouped_settings()
