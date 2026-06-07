# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from prompt_loader import load_agent_prompt_config

PROMPT_CONFIG = load_agent_prompt_config()
SYSTEM_PROMPTS = {int(k): v for k, v in PROMPT_CONFIG["system_prompts"].items()}
ANALYSIS_PROMPTS = {int(k): v for k, v in PROMPT_CONFIG["analysis_prompts"].items()}
FINAL_AUDIT_REPAIR_PASSES = 2
