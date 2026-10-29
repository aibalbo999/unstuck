"""Display-label grammar only; callers must independently prove issuer IDs."""
import re


def latin_prefix_legal_name(source_employer, legal_name):
    if (not isinstance(source_employer,str) or not isinstance(legal_name,str)
            or not 4<=len(legal_name)<=100
            or any(c in source_employer+legal_name for c in '\r\n')):
        return False
    suffix='_'+legal_name
    if not source_employer.endswith(suffix):
        return False
    prefix=source_employer[:-len(suffix)]
    return re.fullmatch(r"[A-Za-z][A-Za-z0-9 .,&'-]{2,79}",prefix) is not None
