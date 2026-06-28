# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from prompt_loader import load_agent_prompt_config

PROMPT_CONFIG = load_agent_prompt_config()


def _numeric_prompt_map(section: str) -> dict[int, str]:
    prompts = {}
    for key, value in PROMPT_CONFIG[section].items():
        try:
            prompts[int(key)] = value
        except (TypeError, ValueError):
            continue
    return prompts


SYSTEM_PROMPTS = _numeric_prompt_map("system_prompts")
ANALYSIS_PROMPTS = _numeric_prompt_map("analysis_prompts")
NAMED_SYSTEM_PROMPTS = {
    str(k): v for k, v in PROMPT_CONFIG["system_prompts"].items() if not str(k).isdigit()
}
NAMED_ANALYSIS_PROMPTS = {
    str(k): v for k, v in PROMPT_CONFIG["analysis_prompts"].items() if not str(k).isdigit()
}
FINAL_AUDIT_REPAIR_PASSES = 2
