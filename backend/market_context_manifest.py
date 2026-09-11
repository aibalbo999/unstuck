"""Runtime-issued identities for complete, visible market evidence blocks."""

from __future__ import annotations

import hashlib
import json
import re
import copy
import math
from contextlib import contextmanager

from data_trust_snapshot_sanitizer import sanitize_for_snapshot
from prompt_context_sections import compact_global_market_items

CONTRACT_VERSION = "market_context.v1"
FINAL_AGENTS = {7, 16, 19}
SOURCE_FIELDS = {"global_market_context": "items", "international_news_context": "topics"}
_GENERATED_KEYS = {"market_context_manifests", "market_context_contract_version", "snapshot_hash", "content_hash",
                   "data_snapshot_hash", "snapshot_integrity", "snapshot_size_bytes"}


def _encoded(value) -> str:
    return json.dumps(sanitize_for_snapshot(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str)


def prompt_fingerprint(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def market_input_fingerprint(data: dict) -> str:
    return prompt_fingerprint(_encoded({key: value for key, value in data.items() if key not in _GENERATED_KEYS}))


def _source_rows(data: dict, source: str) -> list:
    context = data.get(source)
    if isinstance(context, dict) and context.get("availability") == "unavailable":
        return []
    rows = context.get(SOURCE_FIELDS[source]) if isinstance(context, dict) else None
    return rows if isinstance(rows, list) else []


def _usable_source_item(item, source: str) -> bool:
    if not isinstance(item, dict) or item.get("error"):
        return False
    text_fields = ("headline", "title", "summary") if source == "international_news_context" else ("summary", "description")
    has_text = any(isinstance(item.get(key), str) and item[key].strip() for key in text_fields)
    if source == "international_news_context":
        return has_text
    has_value = any(type(item.get(key)) in (int, float) and math.isfinite(item[key])
                    for key in ("latest", "close", "price", "change_1d_pct", "change_5d_pct"))
    return isinstance(item.get("symbol"), str) and bool(item["symbol"].strip()) and (has_text or has_value)


def available_source_count(data: dict, source: str) -> int:
    return sum(_usable_source_item(row, source) for row in _source_rows(data, source))


def build_source_blocks(data: dict, *, agent_num: int, compact: bool = False) -> list[dict]:
    """Bound whole items; never shorten a topic then call the original item visible."""
    return _build_source_blocks(data, agent_num=agent_num, compact=compact, fingerprint=market_input_fingerprint(data))


def _build_source_blocks(data: dict, *, agent_num: int, compact: bool, fingerprint: str) -> list[dict]:
    blocks = []
    for source, field in SOURCE_FIELDS.items():
        rows = _source_rows(data, source)
        selected = (compact_global_market_items(rows) if source == "global_market_context" else rows[:2]) if compact else rows
        selected_ids = {id(row) for row in selected[:32]}
        for index, item in enumerate(rows):
            if id(item) not in selected_ids or not _usable_source_item(item, source):
                continue
            item_text = _encoded(item)
            if len(item_text) > 6000:
                continue
            path = f"data.{source}.{field}[{index}]"
            item_hash = prompt_fingerprint(item_text)
            ref = "mc:" + prompt_fingerprint(f"{fingerprint}:{agent_num}:{path}:{item_hash}")[:32]
            text = f"[market-source:{ref}]\n{_encoded({'source_ref': ref, 'path': path, 'item': item})}\n[/market-source:{ref}]"
            blocks.append({"ref": ref, "source": source, "index": index, "path": path,
                           "item_hash": item_hash, "block_hash": prompt_fingerprint(text), "text": text})
    return blocks


def visible_source_items(final_prompt: str, blocks: list[dict]) -> list[dict]:
    return [block for block in blocks if isinstance(block.get("text"), str)
            and block["text"] and block["text"] in final_prompt]


def build_market_context_manifest(data: dict, final_prompt: str, blocks: list[dict], *, agent_num: int) -> dict:
    visible = visible_source_items(final_prompt, blocks)
    sources = {}
    for source in SOURCE_FIELDS:
        count = available_source_count(data, source)
        refs = [block["ref"] for block in visible if block["source"] == source]
        sources[source] = {"available_count": count, "visible_refs": refs,
                           "availability": "available" if count else "unavailable",
                           "omission_reason": "source_unavailable" if not count else "prompt_omitted" if not refs else ""}
    return {"contract_version": CONTRACT_VERSION, "agent_num": agent_num,
            "input_fingerprint": market_input_fingerprint(data), "prompt_hash": prompt_fingerprint(final_prompt),
            "sources": sources, "items": [{key: value for key, value in block.items() if key != "text"} for block in visible]}


def record_prompt_manifest(context: dict, data: dict, agent_num: int, prompt: str, blocks: list[dict]) -> str:
    if agent_num in FINAL_AGENTS and context.get("market_context_contract_version") == CONTRACT_VERSION:
        context.setdefault("_market_context_attempt_manifests", {})[agent_num] = build_market_context_manifest(
            data, prompt, blocks, agent_num=agent_num)
    return prompt


def manifest_matches_input(manifest: dict, data: dict, agent_num: int) -> bool:
    return _manifest_matches_input(manifest, data, agent_num, fingerprint=market_input_fingerprint(data))


def _manifest_matches_input(manifest: dict, data: dict, agent_num: int, *, fingerprint: str) -> bool:
    """Internal shared validator; a snapshot-only caller must first verify its preservation receipt."""
    if not isinstance(manifest, dict) or manifest.get("contract_version") != CONTRACT_VERSION:
        return False
    if manifest.get("agent_num") != agent_num or manifest.get("input_fingerprint") != fingerprint:
        return False
    prompt_hash = manifest.get("prompt_hash")
    if not isinstance(prompt_hash, str) or re.fullmatch(r"[0-9a-f]{64}", prompt_hash) is None:
        return False
    candidates = {block["ref"]: block for compact in (False, True)
                  for block in _build_source_blocks(data, agent_num=agent_num, compact=compact, fingerprint=fingerprint)}
    items = manifest.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        return False
    if any(not isinstance(item.get("ref"), str) or type(item.get("index")) is not int for item in items):
        return False
    if len({item["ref"] for item in items}) != len(items):
        return False
    for item in items:
        candidate = candidates.get(item.get("ref"))
        if candidate is None or any(item.get(key) != candidate[key] for key in ("source", "index", "path", "item_hash", "block_hash")):
            return False
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        return False
    for source in SOURCE_FIELDS:
        info = sources.get(source)
        count = available_source_count(data, source)
        if not isinstance(info, dict) or type(info.get("available_count")) is not int or info["available_count"] != count:
            return False
        if info.get("visible_refs") != [item["ref"] for item in items if item["source"] == source]:
            return False
        if info.get("availability") != ("available" if count else "unavailable"):
            return False
        expected_reason = "source_unavailable" if not count else "prompt_omitted" if not info["visible_refs"] else ""
        if info.get("omission_reason") != expected_reason:
            return False
    return True


def clear_market_context_output(context: dict, agent_num: int) -> None:
    """Remove only this agent's accepted output before a replacement attempt."""
    if agent_num in FINAL_AGENTS and context.get("market_context_contract_version") == CONTRACT_VERSION:
        for name in ("structured_outputs", "market_context_manifests"):
            values = context.get(name)
            if isinstance(values, dict):
                values.pop(agent_num, None)
                values.pop(str(agent_num), None)


@contextmanager
def market_output_attempt(context: dict, agent_num: int):
    """A failed response cannot lend its structured claims to the next route."""
    if agent_num not in FINAL_AGENTS or context.get("market_context_contract_version") != CONTRACT_VERSION:
        yield
        return
    saved = {name: {key: copy.deepcopy(value) for key, value in context.get(name, {}).items()
                    if key in (agent_num, str(agent_num))}
             for name in ("structured_outputs", "market_context_manifests")}
    clear_market_context_output(context, agent_num)
    try:
        yield
    except BaseException:
        clear_market_context_output(context, agent_num)
        for name, values in saved.items():
            if values:
                context.setdefault(name, {}).update(values)
        raise


def adopt_market_context_result(context: dict, agent_num: int, data: dict, prompt: str, text: str) -> str:
    """Commit only the successful attempt's manifest; raw model assertions remain intact."""
    if agent_num not in FINAL_AGENTS or context.get("market_context_contract_version") != CONTRACT_VERSION:
        return text
    attempts = context.get("_market_context_attempt_manifests", {})
    candidate = attempts.get(agent_num) if isinstance(attempts, dict) else None
    manifests = context.setdefault("market_context_manifests", {})
    manifests.pop(str(agent_num), None)
    if manifest_matches_input(candidate, data, agent_num) and candidate["prompt_hash"] == prompt_fingerprint(prompt):
        manifests[agent_num] = copy.deepcopy(candidate)
    else:
        manifests.pop(agent_num, None)
    from market_context_assessment import assess_final_market_context, market_assessment_text
    from structured_output_report_text import structured_output_to_report_text

    projection = assess_final_market_context({**context, "data": data})["assessment"]
    outputs = context.get("structured_outputs", {})
    output = outputs.get(agent_num, outputs.get(str(agent_num))) if isinstance(outputs, dict) else None
    if isinstance(output, dict):
        return structured_output_to_report_text(agent_num, {**output, "market_context_assessment": projection}, text)
    return text + market_assessment_text(projection)
