"""Load agent prompt templates from versioned JSON files."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from agent_catalog import AGENT_NAMES


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_FILE = PROMPT_DIR / "agents.json"


@lru_cache(maxsize=1)
def load_agent_prompt_config(prompt_file: Optional[str] = None) -> dict:
    """Return validated prompt config used by the analysis pipelines."""
    path = Path(prompt_file) if prompt_file else DEFAULT_PROMPT_FILE
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    for section in ("system_prompts", "analysis_prompts"):
        if section not in config or not isinstance(config[section], dict):
            raise ValueError(f"Prompt config missing section: {section}")

        missing = [str(agent_num) for agent_num in AGENT_NAMES if str(agent_num) not in config[section]]
        if missing:
            raise ValueError(f"Prompt config {section} missing agents: {', '.join(missing)}")

    return config
