"""Load agent prompt templates from versioned JSON files."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from jinja2 import Environment, TemplateSyntaxError, meta
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from agent_catalog import AGENT_NAMES
from prompt_rules import load_runtime_prompt_rules


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_FILE = PROMPT_DIR / "agents.json"
PROMPT_VALIDATION_ENV = Environment()
ANALYSIS_PROMPT_VARIABLES = frozenset({
    "agent_num",
    "context",
    "data",
    "fin_data",
    "name",
    "prev",
    "rag_context",
    "ticker",
})


def _prompt_fingerprint(config: dict, runtime_rules: dict) -> str:
    identity = {
        "version": config.get("version"),
        "state_view_policy": config.get("state_view_policy", {}),
        "system_prompts": config.get("system_prompts", {}),
        "analysis_prompts": config.get("analysis_prompts", {}),
        "runtime_rules": runtime_rules,
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AgentPromptConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    description: str = ""
    state_view_policy: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    system_prompts: dict[str, str]
    analysis_prompts: dict[str, str]
    prompt_version: str | None = None

    @field_validator("system_prompts", "analysis_prompts")
    @classmethod
    def _prompt_values_must_be_text(cls, value: dict[str, str]) -> dict[str, str]:
        for key, prompt in value.items():
            if not str(key).strip():
                raise ValueError("prompt keys must be non-empty strings")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"prompt {key} must be a non-empty string")
        return value

    @field_validator("analysis_prompts")
    @classmethod
    def _analysis_prompts_must_use_known_jinja_variables(cls, value: dict[str, str]) -> dict[str, str]:
        for key, prompt in value.items():
            try:
                parsed = PROMPT_VALIDATION_ENV.parse(prompt)
            except TemplateSyntaxError as exc:
                raise ValueError(f"analysis prompt {key} has invalid Jinja syntax: {exc.message}") from exc
            unknown = sorted(meta.find_undeclared_variables(parsed) - ANALYSIS_PROMPT_VARIABLES)
            if unknown:
                raise ValueError(f"analysis prompt {key} uses unknown Jinja variables: {', '.join(unknown)}")
        return value


@lru_cache(maxsize=1)
def load_agent_prompt_config(prompt_file: Optional[str] = None, runtime_rules_file: Optional[str] = None) -> dict:
    """Return validated prompt config used by the analysis pipelines."""
    path = Path(prompt_file) if prompt_file else DEFAULT_PROMPT_FILE
    with path.open("r", encoding="utf-8") as f:
        raw_config = json.load(f)
    runtime_rules = (
        load_runtime_prompt_rules(str(Path(runtime_rules_file)))
        if runtime_rules_file
        else load_runtime_prompt_rules()
    )
    try:
        model = AgentPromptConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(f"Prompt config schema invalid: {exc}") from exc
    config = model.model_dump()
    fingerprint = _prompt_fingerprint(config, runtime_rules)
    base_version = model.prompt_version or f"agents:v{model.version}"
    config["prompt_fingerprint"] = fingerprint
    config["prompt_version"] = f"{base_version}:{fingerprint[:16]}"

    for section in ("system_prompts", "analysis_prompts"):
        if section not in config or not isinstance(config[section], dict):
            raise ValueError(f"Prompt config missing section: {section}")

        missing = [str(agent_num) for agent_num in AGENT_NAMES if str(agent_num) not in config[section]]
        if missing:
            raise ValueError(f"Prompt config {section} missing agents: {', '.join(missing)}")

    return config
