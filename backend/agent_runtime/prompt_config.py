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

# Evidence availability, not assigned stance, governs both simulated speakers.
SYSTEM_PROMPTS[6] = SYSTEM_PROMPTS[6].replace(
    '多頭必須用未來成長潛力、品質改善或估值折讓來反駁。',
    '多頭須直接檢驗空頭前提；只有同口徑證據支持時才提出成長、改善或估值反證，否則承認未核實並提出可證偽條件。')
SYSTEM_PROMPTS[6] = SYSTEM_PROMPTS[6].replace(
    '多頭先提出護城河或商業模式優勢；',
    '多頭先評估是否存在已核實護城河或商業模式優勢，未核實則明示假設與所缺證據；')
ANALYSIS_PROMPTS[6] = ANALYSIS_PROMPTS[6].replace(
    '多頭先提出商業模式、供應鏈地位或護城河優勢；',
    '多頭先檢驗商業模式、供應鏈地位或護城河優勢的證據，缺證據則明示為未核實假設；')
ANALYSIS_PROMPTS[6] = ANALYSIS_PROMPTS[6].replace(
    '多頭必須用未來成長潛力、營運效率、估值折讓或情境假設來反駁。',
    '多頭須直接檢驗空頭前提，依可追溯證據反駁或承認未核實；不能為維持立場而把情境、效率或折價假設寫成既成事實。')
