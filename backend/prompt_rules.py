"""Load reusable prompt rules from backend/prompts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RULES_FILE = BASE_DIR / "prompts" / "runtime_rules.json"


@lru_cache(maxsize=1)
def load_runtime_prompt_rules(rules_file: str | None = None) -> dict:
    path = Path(rules_file) if rules_file else DEFAULT_RULES_FILE
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_output_cleanliness_rule() -> str:
    config = load_runtime_prompt_rules().get("output_cleanliness_rule", {})
    title = config.get("title", "正式報告輸出契約")
    rules = config.get("rules", []) or []
    lines = [f"【{title}】"]
    lines.extend(f"- {rule}" for rule in rules)
    return "\n".join(lines)


def _build_titled_rule_block(config: dict, alert: bool = False) -> str:
    if not config:
        return ""

    title = config.get("title", "")
    prefix = "🚨" if alert else ""
    lines = [f"{prefix}【{title}】"] if title else []

    intro = config.get("intro")
    if intro:
        lines.append(str(intro))

    schema_lines = config.get("schema_lines") or []
    if schema_lines:
        lines.append("JSON schema:")
        lines.extend(str(line) for line in schema_lines)

    lines.extend(f"- {rule}" for rule in config.get("rules", []) or [])
    return "\n".join(lines).strip()


def build_structured_agent_instructions() -> dict[int, str]:
    configs = load_runtime_prompt_rules().get("structured_agent_instructions", {}) or {}
    instructions = {}
    for agent_num, config in configs.items():
        try:
            key = int(agent_num)
        except (TypeError, ValueError):
            continue
        block = _build_titled_rule_block(config, alert=True)
        if block:
            instructions[key] = block
    return instructions


def build_agent_rule_block(section: str, agent_num: int) -> str:
    configs = load_runtime_prompt_rules().get(section, {}) or {}
    config = configs.get(str(agent_num), {})
    return _build_titled_rule_block(config)


def get_task_prompt_config(task_name: str) -> dict:
    configs = load_runtime_prompt_rules().get("assistant_task_prompts", {}) or {}
    config = configs.get(task_name, {})
    return config if isinstance(config, dict) else {}


def get_task_system_instruction(task_name: str, default: str = "") -> str:
    return str(get_task_prompt_config(task_name).get("system_instruction") or default)


def get_task_instruction_lines(task_name: str) -> list[str]:
    lines = get_task_prompt_config(task_name).get("instruction_lines", []) or []
    return [str(line) for line in lines if str(line).strip()]


def build_identity_guard_rule_lines(values: dict) -> list[str]:
    config = load_runtime_prompt_rules().get("identity_guard", {})
    title = config.get("title", "公司身分一致性硬性規則")
    lines = [f"🚨【{title}】"]

    for rule in config.get("rules", []) or []:
        lines.append(f"- {rule.format(**values)}")

    legal_name = values.get("legal_name")
    if legal_name and config.get("legal_name_rule"):
        lines.append(f"- {config['legal_name_rule'].format(**values)}")

    english_names = values.get("english_names")
    if english_names and config.get("english_names_rule"):
        lines.append(f"- {config['english_names_rule'].format(**values)}")

    forbidden_aliases = values.get("forbidden_aliases")
    if forbidden_aliases and config.get("forbidden_aliases_rule"):
        lines.append(f"- {config['forbidden_aliases_rule'].format(**values)}")

    return lines
