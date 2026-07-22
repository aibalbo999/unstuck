from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import report_style_template_parsing as parsing

__all__ = (
    "find_active_report_style_non_css_output_templates",
    "find_active_report_style_template_cycles",
    "find_duplicate_active_report_style_includes",
    "find_dynamic_active_report_style_includes",
    "find_empty_active_report_style_templates",
    "find_inactive_css_emitting_templates",
    "find_inactive_report_style_output_templates",
    "find_missing_active_report_style_templates",
    "find_non_canonical_active_report_style_include_tags",
    "find_non_report_style_active_includes",
    "find_optioned_active_report_style_includes",
    "find_report_style_template_contract_violations",
    "find_single_child_passthrough_templates",
    "find_unapproved_active_report_style_block_tags",
    "find_unapproved_active_report_style_expression_tags",
)

_ENTRY_TEMPLATE = "includes/report_styles.html.j2"
_STYLE_LEAF_PREFIX = "report_styles"


class _ContractCheck(NamedTuple):
    category: str
    finder: Callable[[Path], list[str]]
    sort_offenders: bool = True


def find_single_child_passthrough_templates(templates_dir: Path) -> list[str]:
    """Return report style templates whose only behavior is including one child."""
    includes_dir = templates_dir / "includes"
    offenders: list[str] = []
    for path in sorted(includes_dir.glob("report_styles*.j2")):
        target = parsing.single_include_target(path)
        if target:
            offenders.append(f"{path.relative_to(templates_dir)} -> {target}")
    return offenders


def find_inactive_css_emitting_templates(templates_dir: Path) -> list[str]:
    """Return inactive report style templates that still contain CSS-like output."""
    offenders: list[str] = []
    for path in _inactive_report_style_templates(templates_dir):
        relative = path.relative_to(templates_dir).as_posix()
        text = parsing.commentless_template_text(path).strip()
        if text and parsing.has_css_token(text):
            offenders.append(relative)
    return offenders


def find_inactive_report_style_output_templates(templates_dir: Path) -> list[str]:
    """Return inactive report style templates that still emit non-comment output."""
    offenders: list[str] = []
    for path in _inactive_report_style_templates(templates_dir):
        text = parsing.commentless_template_text(path).strip()
        if text:
            offenders.append(path.relative_to(templates_dir).as_posix())
    return offenders


def find_empty_active_report_style_templates(templates_dir: Path) -> list[str]:
    """Return active report style templates that contain no non-comment output."""
    return [
        name
        for name, path in _existing_active_style_templates(templates_dir)
        if not parsing.commentless_template_text(path).strip()
    ]


def find_active_report_style_non_css_output_templates(templates_dir: Path) -> list[str]:
    """Return active report style templates that emit non-CSS literal output."""
    return [
        name
        for name, path in _existing_active_style_templates(templates_dir)
        if parsing.has_non_css_literal_output(parsing.literal_template_output(path))
    ]


def find_unapproved_active_report_style_expression_tags(templates_dir: Path) -> list[str]:
    """Return active report style Jinja expressions outside the approved CSS variables."""
    return sorted({
        f"{name} -> {expression}"
        for name, path in _existing_active_style_templates(templates_dir)
        for expression, prefix in parsing.jinja_expressions(path)
        if not parsing.is_approved_style_expression_context(expression, prefix)
    })


def find_unapproved_active_report_style_block_tags(templates_dir: Path) -> list[str]:
    """Return active report style Jinja block tags other than static includes."""
    return list(dict.fromkeys(
        f"{name} -> {tag}"
        for name, path in _existing_active_style_templates(templates_dir)
        for tag in parsing.jinja_block_tags(path)
        if not tag.startswith("include ")
    ))


def find_missing_active_report_style_templates(templates_dir: Path) -> list[str]:
    """Return active report style include edges whose target template is missing."""
    missing: list[str] = []
    visited: set[str] = set()
    stack: list[tuple[str, str | None]] = [(_ENTRY_TEMPLATE, None)]
    while stack:
        name, source = stack.pop()
        path = templates_dir / name
        if not path.exists():
            missing.append(name if source is None else f"{source} -> {name}")
            continue
        if name in visited:
            continue
        visited.add(name)
        for child in _style_include_targets(path):
            stack.append((child, name))
    return sorted(set(missing))


def find_active_report_style_template_cycles(templates_dir: Path) -> list[str]:
    """Return include paths that would make the active report style graph recursive."""
    cycles: list[str] = []
    visited: set[str] = set()
    path: list[str] = []
    def walk(name: str) -> None:
        if name in path:
            cycles.append(" -> ".join(path + [name]))
            return
        if name in visited:
            return
        template_path = templates_dir / name
        if not template_path.exists():
            return
        path.append(name)
        for child in _style_include_targets(template_path):
            walk(child)
        path.pop()
        visited.add(name)

    walk(_ENTRY_TEMPLATE)
    return sorted(dict.fromkeys(cycles))


def find_duplicate_active_report_style_includes(templates_dir: Path) -> list[str]:
    """Return active report style include targets that would be emitted more than once."""
    include_sources: dict[str, list[str]] = {}
    for name, path in _existing_active_style_templates(templates_dir):
        for child in _style_include_targets(path):
            include_sources.setdefault(child, []).append(name)
    return [
        f"{target} <- {', '.join(_source_count_labels(sources))}"
        for target, sources in sorted(include_sources.items())
        if len(sources) > 1
    ]


def find_non_report_style_active_includes(templates_dir: Path) -> list[str]:
    """Return active report style edges outside the style template family."""
    return sorted({
        f"{name} -> {child}"
        for name, path in _existing_active_style_templates(templates_dir)
        for child in parsing.included_templates(path)
        if not _is_style_name(child)
    })


def find_dynamic_active_report_style_includes(templates_dir: Path) -> list[str]:
    """Return active report style include tags whose targets are not static strings."""
    return sorted({
        f"{name} -> {target}"
        for name, path in _existing_active_style_templates(templates_dir)
        for target in parsing.dynamic_include_targets(path)
    })


def find_optioned_active_report_style_includes(templates_dir: Path) -> list[str]:
    """Return active report style static include tags that use Jinja include options."""
    return sorted({
        f"{name} -> {target}"
        for name, path in _existing_active_style_templates(templates_dir)
        for target in parsing.optioned_static_include_targets(path)
    })


def find_non_canonical_active_report_style_include_tags(templates_dir: Path) -> list[str]:
    """Return active include tags that are not plain quoted-literal includes."""
    return sorted({
        f"{name} -> {target}"
        for name, path in _existing_active_style_templates(templates_dir)
        for target in parsing.non_canonical_include_targets(path)
    })

_find_unapproved_expression_tags = find_unapproved_active_report_style_expression_tags
_find_unapproved_block_tags = find_unapproved_active_report_style_block_tags
_find_inactive_outputs = find_inactive_report_style_output_templates
_find_active_non_css_outputs = find_active_report_style_non_css_output_templates
_find_duplicate_includes = find_duplicate_active_report_style_includes
_find_non_style_includes = find_non_report_style_active_includes
_find_missing_includes = find_missing_active_report_style_templates
_find_optioned_includes = find_optioned_active_report_style_includes
_find_noncanonical_tags = find_non_canonical_active_report_style_include_tags

_CONTRACT_CHECKS = (
    _ContractCheck("single_child_passthrough", find_single_child_passthrough_templates),
    _ContractCheck("inactive_output_templates", _find_inactive_outputs),
    _ContractCheck("inactive_css_emitters", find_inactive_css_emitting_templates),
    _ContractCheck("empty_active_templates", find_empty_active_report_style_templates),
    _ContractCheck("active_non_css_output_templates", _find_active_non_css_outputs),
    _ContractCheck("unapproved_expression_tags", _find_unapproved_expression_tags),
    _ContractCheck("unapproved_block_tags", _find_unapproved_block_tags, False),
    _ContractCheck("missing_active_includes", _find_missing_includes),
    _ContractCheck("active_include_cycles", find_active_report_style_template_cycles),
    _ContractCheck("duplicate_active_include_targets", _find_duplicate_includes),
    _ContractCheck("non_report_style_active_includes", _find_non_style_includes),
    _ContractCheck("dynamic_active_includes", find_dynamic_active_report_style_includes),
    _ContractCheck("optioned_active_includes", _find_optioned_includes),
    _ContractCheck("non_canonical_active_include_tags", _find_noncanonical_tags),
)

def find_report_style_template_contract_violations(templates_dir: Path) -> list[str]:
    """Return all active report style template graph contract violations."""
    violations: list[str] = []
    for check in _CONTRACT_CHECKS:
        offenders = check.finder(templates_dir)
        offenders = sorted(offenders) if check.sort_offenders else offenders
        violations.extend(f"{check.category}: {offender}" for offender in offenders)
    return violations

def _is_style_name(name: str) -> bool:
    path = Path(name)
    base, leaf = path.parent.as_posix(), path.name
    style_leaf = leaf.startswith(_STYLE_LEAF_PREFIX)
    return (base, path.suffix) == ("includes", ".j2") and style_leaf

def _style_include_targets(path: Path) -> list[str]:
    return [child for child in parsing.included_templates(path) if _is_style_name(child)]

def _source_count_labels(sources: list[str]) -> list[str]:
    return [
        source if (count := sources.count(source)) == 1 else f"{source} (x{count})"
        for source in dict.fromkeys(sources)
    ]


def _inactive_report_style_templates(templates_dir: Path) -> list[Path]:
    includes_dir = templates_dir / "includes"
    active = _active_report_style_templates(templates_dir)
    return [
        path
        for path in sorted(includes_dir.glob("report_styles*.j2"))
        if path.relative_to(templates_dir).as_posix() not in active
    ]


def _active_report_style_templates(templates_dir: Path) -> set[str]:
    return {name for name, _ in _existing_active_style_templates(templates_dir)}


def _existing_active_style_templates(templates_dir: Path) -> list[tuple[str, Path]]:
    existing: list[tuple[str, Path]] = []
    active: set[str] = set()
    stack = [_ENTRY_TEMPLATE]
    while stack:
        name = stack.pop()
        if name in active:
            continue
        active.add(name)
        path = templates_dir / name
        if not path.exists():
            continue
        existing.append((name, path))
        stack.extend(_style_include_targets(path))
    return sorted(existing)
