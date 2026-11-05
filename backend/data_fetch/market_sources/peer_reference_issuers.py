"""Explicit independently qualified consolidated reference-income issuers.

This registry is not issuer discovery or a mutable runtime configuration.
Individual/TDR/other issuers require their own evidence and admission contract.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ConsolidatedIssuer:
    ticker: str
    code: str
    short: str
    legal: str
    ubn: str
    industry_code: str
    company_header: str
    published_company_label: str
    ordinary_shares: int | None = None
    registered_country: str | None = None


_ISSUERS = MappingProxyType({
    '6230.TW': ConsolidatedIssuer('6230.TW', '6230', '尼得科超眾',
        '尼得科超眾科技股份有限公司', '34005476', '25',
        '6230 尼得科超眾 (上市電腦及週邊設備業)',
        '6230 尼得科超眾 (上市電腦及週邊設備業)'),
    '6558.TW': ConsolidatedIssuer('6558.TW', '6558', '興能高',
        '興能高科技股份有限公司', '97430131', '31',
        '6558 興能高 (上市其他電子業)', '6558 興能高'),
    '2723.TW': ConsolidatedIssuer('2723.TW', '2723', '美食-KY',
        '開曼美食達人股份有限公司', '39682101', '16',
        '2723 美食-KY (上市觀光事業)', '2723 美食-KY',
        ordinary_shares=180000000, registered_country='KY 開曼群島'),
})


def consolidated_issuer(ticker='6230.TW'):
    if type(ticker) is not str or ticker not in _ISSUERS:
        raise ValueError('unsupported consolidated reference-income issuer')
    return _ISSUERS[ticker]
