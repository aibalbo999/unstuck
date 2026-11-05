"""2723-only allocation gate; never substitute group profit or sum EPS.

The full issuer master separately fixes this admission to 180 million ordinary
shares, no preferred shares, and the exact Cayman issuer. EPS is only an extra
consistency gate on each cumulative parent-money observation. TTM arithmetic
continues to use money in disjoint periods, not per-share quantities.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re


def verify_parent_allocation(labels,values,*,parent_income,total_income,ordinary_shares):
    from .official_mopsfin_financial import _amount
    if (type(parent_income)is not int or type(total_income)is not int
            or type(ordinary_shares)is not int or ordinary_shares!=180000000
            or len(labels)!=len(values)):
        raise ValueError('qualified parent allocation inputs changed')
    rows={}
    for label,value in zip(labels,values):
        cells=value.find_all('td',recursive=False)
        if len(cells)!=1:raise ValueError('parent allocation row ambiguous')
        rows.setdefault(label.get_text(' ',strip=True),[]).append(cells[0].get_text(' ',strip=True))
    noncontrolling=rows.get('非控制權益（淨利∕損）',[])
    eps=rows.get('基本每股盈餘',[])
    if len(noncontrolling)!=1 or len(eps)!=1:
        raise ValueError('parent allocation or basic EPS missing or duplicate')
    minority=_amount(noncontrolling[0],label='非控制權益（淨利∕損）')
    if total_income!=parent_income+minority:
        raise ValueError('total does not reconcile to parent plus noncontrolling income')
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,4})\.[0-9]{2}',eps[0]):
        raise ValueError('reported basic EPS grammar unverified')
    try:
        per_share=(Decimal(parent_income)/Decimal(ordinary_shares)).quantize(
            Decimal('0.01'),rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError('unrepresentable parent and ordinary-share reconciliation')from None
    if per_share!=Decimal(eps[0]):
        raise ValueError('parent money and qualified ordinary-share EPS do not reconcile')
