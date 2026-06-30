from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


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


def test_provider_settings_load_cross_provider_llm_keys():
    keys = (
        "GEMINI_API_KEYS",
        "GOOGLE_API_KEYS",
        "OPENAI_API_KEYS",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEYS",
        "ANTHROPIC_API_KEY",
    )
    old_values = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["GEMINI_API_KEYS"] = "google-one,google-two"
        os.environ["OPENAI_API_KEYS"] = "openai-one"
        os.environ["ANTHROPIC_API_KEY"] = "anthropic-one"

        _reload_grouped_settings()
        import settings.app_config as app_config

        assert app_config.API_KEYS == ["google-one", "google-two"]
        assert app_config.LLM_API_KEYS_BY_PROVIDER["google"] == ["google-one", "google-two"]
        assert app_config.LLM_API_KEYS_BY_PROVIDER["openai"] == ["openai-one"]
        assert app_config.LLM_API_KEYS_BY_PROVIDER["anthropic"] == ["anthropic-one"]
        assert app_config.has_api_keys() is True
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reload_grouped_settings()


def test_storage_defaults_consolidate_operational_sqlite_paths(tmp_path):
    keys = (
        "CACHE_DIR",
        "TASK_DB_PATH",
        "OPERATIONAL_DB_PATH",
        "LANGGRAPH_CHECKPOINT_PATH",
        "WATCHLIST_DB_PATH",
        "DECISION_TRACKING_DB_PATH",
    )
    old_values = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["CACHE_DIR"] = str(tmp_path / "cache")

        _reload_grouped_settings()
        import settings.app_config as app_config

        operational_db = tmp_path / "cache" / "operational.sqlite3"
        assert app_config.OPERATIONAL_DB_PATH == str(operational_db)
        assert app_config.TASK_DB_PATH == str(operational_db)
        assert app_config.LANGGRAPH_CHECKPOINT_PATH == app_config.CACHE_DB_PATH
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _reload_grouped_settings()


def test_operational_db_consumers_default_to_task_db(tmp_path):
    keys = (
        "CACHE_DIR",
        "TASK_DB_PATH",
        "OPERATIONAL_DB_PATH",
        "WATCHLIST_PATH",
        "WATCHLIST_DB_PATH",
        "DECISION_TRACKING_DB_PATH",
    )
    old_values = {key: os.environ.get(key) for key in keys}
    for module_name in ("config", "decision_tracking_store", "temporal_memory_service", "watchlist_store"):
        sys.modules.pop(module_name, None)
    try:
        for key in keys:
            os.environ.pop(key, None)
        os.environ["CACHE_DIR"] = str(tmp_path / "cache")

        _reload_grouped_settings()
        import settings.app_config as app_config
        import decision_tracking_store
        import watchlist_store

        operational_db = Path(app_config.TASK_DB_PATH)
        assert decision_tracking_store._db_path() == operational_db
        assert watchlist_store._db_path() == operational_db
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for module_name in ("config", "decision_tracking_store", "temporal_memory_service", "watchlist_store"):
            sys.modules.pop(module_name, None)
        _reload_grouped_settings()


def test_load_local_env_does_not_reopen_unchanged_file(tmp_path, monkeypatch):
    import settings.env as settings_env

    original_base_dir = settings_env.BASE_DIR
    original_signature = getattr(settings_env, "_LOADED_ENV_SIGNATURE", None)
    original_success = getattr(settings_env, "_LOADED_ENV_SUCCESS", False)
    original_read_text = Path.read_text
    old_value = os.environ.get("TEST_ENV_CACHE_KEY")
    read_count = {"value": 0}

    (tmp_path / ".env").write_text("TEST_ENV_CACHE_KEY=loaded-once\n", encoding="utf-8")

    def counting_read_text(self, *args, **kwargs):
        if self == tmp_path / ".env":
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    try:
        os.environ.pop("TEST_ENV_CACHE_KEY", None)
        settings_env.BASE_DIR = tmp_path
        settings_env._LOADED_ENV_SIGNATURE = None
        settings_env._LOADED_ENV_SUCCESS = False
        monkeypatch.setattr(Path, "read_text", counting_read_text)

        settings_env.load_local_env()
        settings_env.load_local_env()
        settings_env.load_local_env()

        assert os.environ["TEST_ENV_CACHE_KEY"] == "loaded-once"
        assert read_count["value"] == 1
    finally:
        settings_env.BASE_DIR = original_base_dir
        settings_env._LOADED_ENV_SIGNATURE = original_signature
        settings_env._LOADED_ENV_SUCCESS = original_success
        if old_value is None:
            os.environ.pop("TEST_ENV_CACHE_KEY", None)
        else:
            os.environ["TEST_ENV_CACHE_KEY"] = old_value


def test_load_local_env_uses_cached_values_when_reopen_hits_oserror(tmp_path, monkeypatch):
    import settings.env as settings_env

    original_base_dir = settings_env.BASE_DIR
    original_signature = getattr(settings_env, "_LOADED_ENV_SIGNATURE", None)
    original_success = getattr(settings_env, "_LOADED_ENV_SUCCESS", False)
    original_read_text = Path.read_text
    old_value = os.environ.get("TEST_ENV_OSERROR_KEY")
    calls = {"value": 0}

    (tmp_path / ".env").write_text("TEST_ENV_OSERROR_KEY=survives\n", encoding="utf-8")

    def flaky_read_text(self, *args, **kwargs):
        if self == tmp_path / ".env":
            calls["value"] += 1
            if calls["value"] > 1:
                raise OSError(24, "Too many open files")
        return original_read_text(self, *args, **kwargs)

    try:
        os.environ.pop("TEST_ENV_OSERROR_KEY", None)
        settings_env.BASE_DIR = tmp_path
        settings_env._LOADED_ENV_SIGNATURE = None
        settings_env._LOADED_ENV_SUCCESS = False
        monkeypatch.setattr(Path, "read_text", flaky_read_text)

        settings_env.load_local_env()
        settings_env._LOADED_ENV_SIGNATURE = None
        settings_env.load_local_env()

        assert os.environ["TEST_ENV_OSERROR_KEY"] == "survives"
        assert calls["value"] == 2
    finally:
        settings_env.BASE_DIR = original_base_dir
        settings_env._LOADED_ENV_SIGNATURE = original_signature
        settings_env._LOADED_ENV_SUCCESS = original_success
        if old_value is None:
            os.environ.pop("TEST_ENV_OSERROR_KEY", None)
        else:
            os.environ["TEST_ENV_OSERROR_KEY"] = old_value


def test_load_local_env_replaces_empty_environment_value(tmp_path):
    import settings.env as settings_env

    original_base_dir = settings_env.BASE_DIR
    original_signature = getattr(settings_env, "_LOADED_ENV_SIGNATURE", None)
    original_success = getattr(settings_env, "_LOADED_ENV_SUCCESS", False)
    old_value = os.environ.get("TEST_ENV_EMPTY_KEY")

    (tmp_path / ".env").write_text("TEST_ENV_EMPTY_KEY=filled\n", encoding="utf-8")

    try:
        os.environ["TEST_ENV_EMPTY_KEY"] = ""
        settings_env.BASE_DIR = tmp_path
        settings_env._LOADED_ENV_SIGNATURE = None
        settings_env._LOADED_ENV_SUCCESS = False

        settings_env.load_local_env()

        assert os.environ["TEST_ENV_EMPTY_KEY"] == "filled"
    finally:
        settings_env.BASE_DIR = original_base_dir
        settings_env._LOADED_ENV_SIGNATURE = original_signature
        settings_env._LOADED_ENV_SUCCESS = original_success
        if old_value is None:
            os.environ.pop("TEST_ENV_EMPTY_KEY", None)
        else:
            os.environ["TEST_ENV_EMPTY_KEY"] = old_value
