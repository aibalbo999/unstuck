"""Load reusable prompt rules from backend/prompts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RULES_FILE = BASE_DIR / "prompts" / "runtime_rules.json"


@lru_cache(maxsize=None)
def load_runtime_prompt_rules(rules_file: str | None = None) -> dict:
    """Return the process-stable runtime rule snapshot for one rules path."""
    path = Path(rules_file) if rules_file else DEFAULT_RULES_FILE
    with path.open("r", encoding="utf-8") as handle:
        rules = json.load(handle)
    if not isinstance(rules, dict):
        raise ValueError("Runtime prompt rules root must be an object")
    return rules


def _safe_rule_text(value, fallback: str = "") -> str:
    try:
        text = str(value).strip()
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return fallback
    return text if text else fallback


def _safe_format_rule_template(template, values: dict) -> str:
    template_text = _safe_rule_text(template)
    if not template_text:
        return ""
    try:
        return template_text.format(**values).strip()
    except (KeyError, IndexError, TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return ""


def _rule_config_is_empty(config: dict) -> bool:
    try:
        return dict.__len__(config) == 0
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


def _rule_config_get(config: dict, key: str, default=None):
    return dict.get(config, key, default)


def _runtime_rule_section(section: str, default=None):
    fallback = {} if default is None else default
    rules = load_runtime_prompt_rules()
    if not isinstance(rules, dict):
        return fallback
    return dict.get(rules, section, fallback)


def build_output_cleanliness_rule() -> str:
    config = _runtime_rule_section("output_cleanliness_rule")
    if not isinstance(config, dict):
        config = {}
    block_config = {
        "title": _safe_rule_text(_rule_config_get(config, "title", ""), "正式報告輸出契約"),
        "rules": _rule_config_get(config, "rules", []),
    }
    return _build_titled_rule_block(block_config)


def _build_titled_rule_block(config: dict, alert: bool = False) -> str:
    if not isinstance(config, dict):
        return ""
    if _rule_config_is_empty(config):
        return ""

    title = _safe_rule_text(_rule_config_get(config, "title", ""))
    prefix = "🚨" if alert else ""
    lines = [f"{prefix}【{title}】"] if title else []

    intro = _safe_rule_text(_rule_config_get(config, "intro"))
    if intro:
        lines.append(intro)

    schema_lines = _coerce_rule_list(_rule_config_get(config, "schema_lines", []))
    if schema_lines:
        lines.append("JSON schema:")
        lines.extend(schema_lines)

    lines.extend(f"- {rule}" for rule in _coerce_rule_list(_rule_config_get(config, "rules", [])))
    return "\n".join(lines).strip()


def build_structured_agent_instructions() -> dict[int, str]:
    configs = _runtime_rule_section("structured_agent_instructions")
    if not isinstance(configs, dict):
        configs = {}
    instructions = {}
    for agent_num, config in dict.items(configs):
        try:
            key = int(agent_num)
        except (TypeError, ValueError):
            continue
        block = _build_titled_rule_block(config, alert=True)
        if block:
            instructions[key] = block
    return instructions


def _coerce_rule_list(value) -> list[str]:
    if isinstance(value, dict):
        value = dict.get(value, "rules", [])
    if not isinstance(value, list):
        return []
    rules = []
    try:
        iterator = iter(value)
        for rule in iterator:
            text = _safe_rule_text(rule)
            if text:
                rules.append(text)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        pass
    return rules


def build_final_audit_preflight_rule(agent_num: int, pipeline_id: str = "") -> str:
    """Build the pre-output checklist that mirrors final audit failure modes."""
    config = _runtime_rule_section("final_audit_preflight_rule")
    if not isinstance(config, dict):
        return ""

    rules = _coerce_rule_list(_rule_config_get(config, "rules", []))
    per_agent = _rule_config_get(config, "per_agent", {})
    if not isinstance(per_agent, dict):
        per_agent = {}
    rules.extend(_coerce_rule_list(_rule_config_get(per_agent, str(agent_num), [])))

    try:
        normalized_pipeline = "" if pipeline_id is None else str(pipeline_id).strip()
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        normalized_pipeline = ""
    per_pipeline = _rule_config_get(config, "per_pipeline", {})
    if not isinstance(per_pipeline, dict):
        per_pipeline = {}
    if normalized_pipeline:
        rules.extend(_coerce_rule_list(_rule_config_get(per_pipeline, normalized_pipeline, [])))

    block_config = {
        "title": _rule_config_get(config, "title", "最終審核前自檢"),
        "intro": _rule_config_get(config, "intro", ""),
        "rules": rules,
    }
    return _build_titled_rule_block(block_config, alert=True)


def build_agent_rule_block(section: str, agent_num: int) -> str:
    configs = _runtime_rule_section(section)
    if not isinstance(configs, dict):
        configs = {}
    config = dict.get(configs, str(agent_num), {})
    return _build_titled_rule_block(config)


def get_task_prompt_config(task_name: str) -> dict:
    configs = _runtime_rule_section("assistant_task_prompts")
    if not isinstance(configs, dict):
        return {}
    config = _rule_config_get(configs, task_name, {})
    return config if isinstance(config, dict) else {}


def get_task_system_instruction(task_name: str, default: str = "") -> str:
    return _safe_rule_text(_rule_config_get(get_task_prompt_config(task_name), "system_instruction"), default)


def get_task_instruction_lines(task_name: str) -> list[str]:
    return _coerce_rule_list(_rule_config_get(get_task_prompt_config(task_name), "instruction_lines", []))


def build_identity_guard_rule_lines(values: dict) -> list[str]:
    config = _runtime_rule_section("identity_guard")
    if not isinstance(config, dict):
        config = {}
    title = _safe_rule_text(_rule_config_get(config, "title", ""), "公司身分一致性硬性規則")
    lines = [f"🚨【{title}】"]

    for rule in _coerce_rule_list(_rule_config_get(config, "rules", [])):
        formatted_rule = _safe_format_rule_template(rule, values)
        if formatted_rule:
            lines.append(f"- {formatted_rule}")

    legal_name = _safe_rule_text(_rule_config_get(values, "legal_name"))
    legal_name_rule = _safe_format_rule_template(_rule_config_get(config, "legal_name_rule"), values)
    if legal_name and legal_name_rule:
        lines.append(f"- {legal_name_rule}")

    english_names = _safe_rule_text(_rule_config_get(values, "english_names"))
    english_names_rule = _safe_format_rule_template(_rule_config_get(config, "english_names_rule"), values)
    if english_names and english_names_rule:
        lines.append(f"- {english_names_rule}")

    forbidden_aliases = _safe_rule_text(_rule_config_get(values, "forbidden_aliases"))
    forbidden_aliases_rule = _safe_format_rule_template(_rule_config_get(config, "forbidden_aliases_rule"), values)
    if forbidden_aliases and forbidden_aliases_rule:
        lines.append(f"- {forbidden_aliases_rule}")

    return lines
