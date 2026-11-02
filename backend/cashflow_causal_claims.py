"""Reject operating-driver facts inferred from negative cash-flow totals alone.

This bounded text gate does not authenticate management explanations. No caller
flag or citation label supplies that proof; absent a separately reviewed causal
source adapter, specific drivers must be presented as hypotheses. Generic cash
pressure and cash-flow arithmetic are outside this check.
"""
from __future__ import annotations
import re

_NEGATIVE = re.compile(
 r'現金流流出|負(?:向|值)?\s*(?:自由)?(?:現金流|FCF)|'
 r'(?:自由現金流|FCF).{0,60}?(?:為負|負值|[=:：]\s*-\s*\d|'
 r'-\s*\d+(?:\.\d+)?\s*(?:億|元|billion|million))|'
 r'(?:自由現金流|FCF).{0,60}?(?:淨流出|淨支出)|'
 r'negative\s+(?:free\s+cash\s*flow|FCF)',re.I)
_CAUSE = re.compile(r'應視為|代表其處於|主因|因應|源於|源自|顯示|反映|證實|證明|導致|致使|'
 r'主要受|implies|shows|proves|because|caused\s+by',re.I)
_DEPENDENCE = re.compile(r'(?:高度)?依賴\s*(?:外部|external)\s*融資', re.I)
_DRIVER = re.compile(r'備料|擴產|擴張|營運資金(?!(?:管理)?壓力)|'
 r'(?:存貨|應收帳款|應收款).{0,12}(?:鎖定|佔用|占用|墊付)|'
 r'(?:鎖定|佔用|占用).{0,12}(?:存貨|應收帳款|應收款)|'
 r'inventory|receivables|working\s+capital|capacity\s+expansion',re.I)
_UNCERTAIN = re.compile(r'可能|或許|假設|推測|不(?:構成|能|足以|證明|代表|是)|無法|尚無|尚待|'
 r'缺乏.{0,18}(?:證據|原件|說明)|'
 r'待.{0,6}(?:核實|驗證)|未(?:經|能|獲).{0,6}(?:核實|驗證)|'
 r'\b(?:if|may|might|could|cannot|hypothesis)\b|not\s+prove|does\s+not',re.I)


def cashflow_driver_inference_issues(text: str) -> list[dict]:
    issues=[]
    for line_number,line in enumerate(str(text or '').splitlines(),1):
        for raw in re.split(r'[。！？!?;；]',line):
            clause=re.sub(r'[*`]', '', raw)
            negative=_NEGATIVE.search(clause)
            drivers=[]
            for mention in _DRIVER.finditer(clause):
                if mention.group() == '營運資金':
                    suffix=clause[mention.end():]
                    prefix=clause[:mention.start()]
                    # A request to monitor a driver is not an assertion that
                    # the driver caused the observed total. Do not suppress
                    # another, earlier unqualified driver in this clause.
                    if (re.match(r'^(?:需求|運用|配置)?(?:仍|尚|應|須|需)(?:要)?(?:持續|密切){0,2}(?:追蹤|核實|觀察|驗證|檢視|監控)',suffix)
                            or re.search(r'(?:應|須|需)(?:要)?(?:持續|密切){0,2}(?:追蹤|核實|觀察|驗證|檢視|監控)(?:其|公司|相關)?$',prefix)):
                        continue
                drivers.append(mention)
            driver=drivers[0] if drivers else None
            dependency = _DEPENDENCE.search(clause)
            cause=_CAUSE.search(clause) or dependency
            if not (negative and driver and cause):
                continue
            start=max(0,min(negative.start(),driver.start(),cause.start())-16)
            end=max(driver.start(),cause.start())
            uncertain = _UNCERTAIN.search(clause[start:end])
            if dependency and uncertain is None:
                uncertain = re.search(r'若|如果|是否|能否', clause[start:end])
            if uncertain:
                later_assertion = False
                if uncertain.group() in ('不構成', '若', '如果', '是否', '能否'):
                    # A denial of proof cannot excuse a new positive assertion
                    # introduced after a contrast in the same sentence.
                    tail = clause[start + uncertain.end():]
                    for part in re.split(r'但(?:是)?|然而|不過|卻', tail)[1:]:
                        later_cause = _CAUSE.search(part) or (_DEPENDENCE.search(part) if dependency else None)
                        later_driver = _DRIVER.search(part)
                        if later_cause and later_driver and not _UNCERTAIN.search(
                                part[:max(later_cause.start(), later_driver.start())]):
                            later_assertion = True
                if not later_assertion:
                    continue
            # A local whether-question plus explicit missing evidence is not
            # an asserted cause. Earlier standalone assertions stay blocked.
            question=re.search(r'是否(?:確)?(?:為|因|由)',clause[start:end])
            if question and re.search(r'缺乏.{0,18}(?:支持|證據)|尚無.{0,18}(?:支持|證據)',clause[end:]):
                earlier=clause[start:start+question.start()]
                if not _CAUSE.search(earlier):
                    continue
            issues.append({'line_number':line_number,'status':'rejected',
                'reason_code':'cashflow_total_does_not_establish_operating_driver',
                'text':raw.strip()[:500]})
    # A negative observation does not invalidate the valuation method itself.
    for line_number,line in enumerate(str(text or '').splitlines(),1):
        for clause in re.split(r'[。！？!?;；]', re.sub(r'[*`]', '', line)):
            if re.search(r'DCF.{0,24}(?:因|由於).{0,24}(?:現金流|FCF).{0,12}(?:負|流出).{0,18}(?:失去參考價值|理論上不可用|必然不可用)',clause,re.I):
                if not re.search(r'不能|不代表|不可推論|並非|錯誤|未核實',clause):
                    issues.append({'line_number':line_number,'status':'rejected','reason_code':'negative_fcf_does_not_invalidate_dcf_method','text':clause[:500]})
    return issues
