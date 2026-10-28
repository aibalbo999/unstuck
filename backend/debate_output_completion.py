"""Bound the debate's shape without relaxing evidence or provider completion."""

import re

POLICY = 'debate-completion:v1-bounded-recovery'
INSTRUCTION = (
    '\n\nAgent 6 完整性契約：以精煉三輪完成全部攻防，總長目標約 1200–1800 字；'
    '必要證據與品質規則優先於篇幅，不得為縮短而省略反證、引用或資料限制。'
    '每輪多頭、空頭各一段，標題使用 Round 1、Round 2、Round 3；'
    '對話行固定使用「🐂 多頭：」與「🐻 空頭：」。每段聚焦一項主張及對方反駁，'
    '保留來源 path、期間與單位，不重貼原始表格、前序全文或重複背景。'
    '最後務必完成「主持人總結」與「未解爭點」，列出雙方引用及解除矛盾所需證據。'
    '年度、季度、TTM、Yahoo 即期成長率逐項綁定，不把即期值改稱年度。'
    '這是同一模型的模擬辯論，不增加獨立證據，不產生新目標價或最終買賣建議。'
)


def debate_output_issues(text: str) -> list[str]:
    plain = re.sub(r'[*`]', '', text or '')
    rounds = list(re.finditer(r'(?im)^\s*(?:#{1,6}\s*)?Round\s*([123])\s*[：:（(\-]', plain))
    issues = []
    if [m.group(1) for m in rounds] != ['1', '2', '3']:
        issues.append('Agent 6 辯論須依序完整提供 Round 1、Round 2、Round 3。')
    for index, match in enumerate(rounds):
        end = rounds[index + 1].start() if index + 1 < len(rounds) else len(plain)
        section = plain[match.end():end].split('主持人總結', 1)[0]
        turns = list(re.finditer(r'(?m)^[ \t]*(?:🐂|🐻)?[ \t]*(多頭|空頭)[ \t]*[：:]', section))
        present = set()
        for turn_index, turn in enumerate(turns):
            turn_end = turns[turn_index + 1].start() if turn_index + 1 < len(turns) else len(section)
            if re.search(r'[\w\u3400-\u9fff]', section[turn.end():turn_end]):
                present.add(turn.group(1))
        for role in ('多頭', '空頭'):
            if role not in present:
                issues.append(f'Agent 6 Round {match.group(1)} 缺少{role}的實際攻防內容。')
    conclusions = list(re.finditer(r'(?m)^[ \t]*(?:#{1,6}[ \t]*)?(主持人總結|未解爭點)[ \t]*[：:]', plain))
    present = set()
    for index, match in enumerate(conclusions):
        end = conclusions[index + 1].start() if index + 1 < len(conclusions) else len(plain)
        if (rounds and match.start() > rounds[-1].start()
                and re.search(r'[\w\u3400-\u9fff]', plain[match.end():end])):
            present.add(match.group(1))
    for label in ('主持人總結', '未解爭點'):
        if label not in present:
            issues.append(f'Agent 6 缺少完整的{label}。')
    return issues


def debate_retry_spent(context: dict) -> bool:
    counts = context.get('agent_quality_retry_counts') or {}
    history = (context.get('repair_candidate_history') or {}).get('6') or {}
    try:
        return int(counts.get(6, counts.get('6', 0)) or 0) >= 1 or int(history.get('calls', 0)) >= 1
    except (ValueError, TypeError, AttributeError):
        return True


def recoverable_debate_truncation(context: dict) -> bool:
    from memo_output_completion import incomplete_memo_roles
    for role in incomplete_memo_roles(context):
        reasons = set(role['receipt'].get('finish_reasons') or [])
        if role['agent'] == 6 and reasons and reasons <= {'MAX_TOKENS', 'LENGTH'}:
            return not debate_retry_spent(context)
    return False
