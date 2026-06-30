"""Load agent prompt templates from versioned JSON files."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from agent_catalog import AGENT_NAMES


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_FILE = PROMPT_DIR / "agents.json"


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


@lru_cache(maxsize=1)
def load_agent_prompt_config(prompt_file: Optional[str] = None) -> dict:
    """Return validated prompt config used by the analysis pipelines."""
    path = Path(prompt_file) if prompt_file else DEFAULT_PROMPT_FILE
    with path.open("r", encoding="utf-8") as f:
        raw_config = json.load(f)
    try:
        model = AgentPromptConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(f"Prompt config schema invalid: {exc}") from exc
    config = model.model_dump()
    config["prompt_version"] = model.prompt_version or f"agents:v{model.version}"

    for section in ("system_prompts", "analysis_prompts"):
        if section not in config or not isinstance(config[section], dict):
            raise ValueError(f"Prompt config missing section: {section}")

        missing = [str(agent_num) for agent_num in AGENT_NAMES if str(agent_num) not in config[section]]
        if missing:
            raise ValueError(f"Prompt config {section} missing agents: {', '.join(missing)}")

    return config
