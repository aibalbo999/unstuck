"""Narrow contradiction check: research BUY is not an immediate position order."""
import re


def _conditional_clause(text):
    text = text.strip()
    return bool(re.fullmatch(r'(?:若|如果|假設).+|(?:待|等待).+(?:後|時|才|再)', text))


def waiting_plan_has_immediate_order(text):
    if not isinstance(text, str):
        return False
    for sentence in re.split(r'[。！？\n；;]', text):
        for match in re.finditer(r'(?:立即|現在就|馬上|即刻|立刻)\s*(?:買入|進場|建倉|做多|做空|放空|加碼|減碼|續抱|持有|賣出|出場|平倉)', sentence):
            prefix = sentence[:match.start()].rstrip()
            if re.search(r'(?:不應|不要|不可|不得|禁止|勿|不建議|不能|暫不)\s*$', prefix):
                continue
            clauses = re.split(r'[，,]', prefix)
            local = clauses[-1].strip()
            # Only an explicit conditional clause can qualify an immediate verb.
            # A word such as 期待 or 不必等待 elsewhere is not a condition.
            if _conditional_clause(local):
                continue
            if len(clauses) >= 2 and local in ('', '請', '即可', '可以', '則', '才可') and _conditional_clause(clauses[-2]):
                continue
            return True
    return False
