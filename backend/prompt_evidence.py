"""Non-mutating projection of evidence across the prompt boundary."""

from __future__ import annotations

import copy
from dataclasses import fields, is_dataclass
from typing import Any

from pydantic import BaseModel


INTERNAL_PROMPT_KEYS = frozenset({"rag_index", "embedding", "embeddings", "vector", "vectors", "analysis_input_evidence", "source_record_archive", "identity_rejected_catalysts", "trading_notice_receipt", "finmind_news_receipt", "tdr_mops_receipt", "mops_json_receipt", "philjobnet_employer_receipt", "uk_conference_receipt", "nanya_mops_receipt", "txc_conference_receipt", "psc_conference_receipt", "honhai_conference_receipt", "tcfhc_qa_receipt", "jentech_conference_receipt", "pcsc_conference_receipt", "guc_conference_receipt", "seec_conference_receipt", "eclat_conference_receipt", "kingslide_conference_receipt", "promate_conference_receipt", "auras_conference_receipt", "delta_transcript_receipt", "tewc_conference_receipt", "unitech_conference_receipt", "chipmos_conference_receipt", "winbond_conference_receipt", "sigurd_conference_receipt", "sigurd_glyph_evidence", "sti_conference_receipt", "mops_material_receipt", "csc_conference_receipt", "allis_conference_receipt", "allis_glyph_evidence", "gce_conference_receipt", "gce_glyph_evidence", "hiwin_conference_receipt", "hiwin_glyph_evidence", "kinik_conference_receipt", "kinik_glyph_evidence", "walsin_conference_receipt", "innocare_conference_receipt", "chb_qa_receipt", "zdt_conference_receipt", "chroma_conference_receipt", "getac_conference_receipt", "npc_conference_receipt", "sinbon_conference_receipt", "fubon_conference_receipt", "voltronic_conference_receipt", "object_header_whitespace_evidence", "macronix_conference_receipt", "tecom_conference_receipt", "eikei_conference_receipt", "nanyapcb_conference_receipt", "wahlee_conference_receipt", "lienhwa_conference_receipt", "lienhwa_glyph_evidence", "cht_conference_receipt", "csc_glyph_evidence", "sti_glyph_evidence", "xref_validation_evidence"})


def is_internal_prompt_key(key: Any) -> bool:
    return isinstance(key, str) and key.lower().lstrip("_") in INTERNAL_PROMPT_KEYS


def prompt_evidence_copy(value: Any) -> Any:
    """Drop internal fields before traversing them; keep evidence paths and values."""
    if isinstance(value, BaseModel):
        model_values = {name: getattr(value, name) for name in type(value).model_fields if not is_internal_prompt_key(name)}
        model_values.update(value.model_extra or {})
        value = model_values
    elif is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value) if not is_internal_prompt_key(field.name)}
    if isinstance(value, dict):
        return {key: prompt_evidence_copy(item) for key, item in dict.items(value) if not is_internal_prompt_key(key)}
    if isinstance(value, list):
        return [prompt_evidence_copy(item) for item in list.__iter__(value)]
    if isinstance(value, tuple):
        return tuple(prompt_evidence_copy(item) for item in tuple.__iter__(value))
    if isinstance(value, (set, frozenset)):
        iterator = set.__iter__(value) if isinstance(value, set) else frozenset.__iter__(value)
        return [prompt_evidence_copy(item) for item in sorted(iterator, key=repr)]
    return copy.deepcopy(value)
