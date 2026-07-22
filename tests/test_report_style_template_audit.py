from pathlib import Path
import re

BACKEND = Path(__file__).resolve().parents[1] / "backend"
_INLINE_STYLE_RE = re.compile(r"""style=(["'])(.*?)\1""")


def test_report_markup_templates_do_not_use_static_inline_styles():
    offenders: list[str] = []
    templates_dir = BACKEND / "templates"
    for path in sorted(templates_dir.rglob("*.j2")):
        relative = path.relative_to(templates_dir).as_posix()
        if relative.startswith("includes/report_styles"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in _INLINE_STYLE_RE.finditer(text):
            style_text = match.group(2).strip()
            if "{{" in style_text or "${" in style_text:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{relative}:{line_no} -> {style_text}")

    assert offenders == []


def test_report_markup_templates_do_not_use_dynamic_inline_styles():
    dynamic_styles: list[tuple[str, str]] = []
    templates_dir = BACKEND / "templates"
    for path in sorted(templates_dir.rglob("*.j2")):
        relative = path.relative_to(templates_dir).as_posix()
        if relative.startswith("includes/report_styles"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in _INLINE_STYLE_RE.finditer(text):
            style_text = match.group(2).strip()
            if "{{" in style_text or "${" in style_text:
                dynamic_styles.append((relative, style_text))

    assert dynamic_styles == []


def test_report_markup_static_style_replacements_have_style_template_rules():
    includes_dir = BACKEND / "templates" / "includes"
    verdict_parent = includes_dir / "report_styles_verdict_banner_meta_label.html.j2"
    moat_parent = includes_dir / "report_styles_moat_layout.html.j2"
    reference_parent = includes_dir / "report_styles_reference_item_text.html.j2"
    reference_list_parent = includes_dir / "report_styles_reference_list.html.j2"
    sidebar_footer_parent = includes_dir / "report_styles_sidebar_summary_footer.html.j2"

    assert (
        '{% include "includes/report_styles_verdict_banner_meta_label_spacing.html.j2" %}'
        in verdict_parent.read_text(encoding="utf-8")
    )
    verdict_spacing = (
        includes_dir / "report_styles_verdict_banner_meta_label_spacing.html.j2"
    ).read_text(encoding="utf-8")
    assert ".verdict-meta .vm-value + .vm-label" in verdict_spacing
    assert "margin-top: 8px;" in verdict_spacing

    assert (
        '{% include "includes/report_styles_moat_layout_spacing.html.j2" %}'
        in moat_parent.read_text(encoding="utf-8")
    )
    moat_spacing = (includes_dir / "report_styles_moat_layout_spacing.html.j2").read_text(
        encoding="utf-8"
    )
    assert ".moat-grid" in moat_spacing
    assert "margin-bottom: 24px;" in moat_spacing

    assert (
        '{% include "includes/report_styles_reference_item_text_code.html.j2" %}'
        in reference_parent.read_text(encoding="utf-8")
    )
    reference_code = (
        includes_dir / "report_styles_reference_item_text_code.html.j2"
    ).read_text(encoding="utf-8")
    assert ".ref-desc code" in reference_code
    assert "background: #f1f5f9;" in reference_code
    assert "color: var(--accent-blue);" in reference_code

    assert (
        '{% include "includes/report_styles_reference_notices.html.j2" %}'
        in reference_list_parent.read_text(encoding="utf-8")
    )
    reference_notices = (includes_dir / "report_styles_reference_notices.html.j2").read_text(
        encoding="utf-8"
    )
    assert '{% include "includes/report_styles_reference_official_warning.html.j2" %}' in reference_notices
    assert '{% include "includes/report_styles_reference_data_note.html.j2" %}' in reference_notices
    official_warning = (
        includes_dir / "report_styles_reference_official_warning.html.j2"
    ).read_text(encoding="utf-8")
    assert ".reference-official-warning" in official_warning
    assert "color: var(--accent-amber);" in official_warning
    data_note = (includes_dir / "report_styles_reference_data_note.html.j2").read_text(
        encoding="utf-8"
    )
    assert ".reference-data-note" in data_note
    assert "color: var(--text-muted);" in data_note

    assert (
        '{% include "includes/report_styles_sidebar_summary_footer_warning.html.j2" %}'
        in sidebar_footer_parent.read_text(encoding="utf-8")
    )
    sidebar_warning = (
        includes_dir / "report_styles_sidebar_summary_footer_warning.html.j2"
    ).read_text(encoding="utf-8")
    assert ".sidebar-footer-warning" in sidebar_warning
    assert "color: #374151;" in sidebar_warning


def test_missing_active_report_style_templates_ignores_commented_includes(tmp_path):
    from report_style_template_audit import find_missing_active_report_style_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{# {% include "includes/missing.html.j2" %} #}\n'
        '{% include "includes/real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_missing_active_report_style_templates(templates_dir)

    assert offenders == []


def test_missing_active_report_style_templates_deduplicate_repeated_edges(tmp_path):
    from report_style_template_audit import find_missing_active_report_style_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_missing.html.j2" %}\n'
        '{% include "includes/report_styles_missing.html.j2" %}\n',
        encoding="utf-8",
    )

    offenders = find_missing_active_report_style_templates(templates_dir)

    assert offenders == [
        "includes/report_styles.html.j2 -> includes/report_styles_missing.html.j2"
    ]


def test_inactive_css_emitting_templates_treats_commented_includes_as_inactive(tmp_path):
    from report_style_template_audit import find_inactive_css_emitting_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{# {% include "includes/report_styles_unused.html.j2" %} #}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_unused.html.j2").write_text(".unused { color: red; }\n", encoding="utf-8")

    offenders = find_inactive_css_emitting_templates(templates_dir)

    assert offenders == ["includes/report_styles_unused.html.j2"]


def test_inactive_css_emitting_templates_detects_custom_properties(tmp_path):
    from report_style_template_audit import find_inactive_css_emitting_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text("", encoding="utf-8")
    (includes_dir / "report_styles_unused.html.j2").write_text(
        ":root {\n"
        "  --orphan-token: 1rem;\n"
        "}\n",
        encoding="utf-8",
    )

    offenders = find_inactive_css_emitting_templates(templates_dir)

    assert offenders == ["includes/report_styles_unused.html.j2"]


def test_inactive_css_emitting_templates_detects_scroll_behavior(tmp_path):
    from report_style_template_audit import find_inactive_css_emitting_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text("", encoding="utf-8")
    (includes_dir / "report_styles_unused.html.j2").write_text(
        "html { scroll-behavior: smooth; }\n",
        encoding="utf-8",
    )

    offenders = find_inactive_css_emitting_templates(templates_dir)

    assert offenders == ["includes/report_styles_unused.html.j2"]


def test_inactive_css_emitting_templates_detects_font_family(tmp_path):
    from report_style_template_audit import find_inactive_css_emitting_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text("", encoding="utf-8")
    (includes_dir / "report_styles_unused.html.j2").write_text(
        "body { font-family: system-ui, sans-serif; }\n",
        encoding="utf-8",
    )

    offenders = find_inactive_css_emitting_templates(templates_dir)

    assert offenders == ["includes/report_styles_unused.html.j2"]


def test_inactive_css_emitting_templates_detects_generic_css_declarations(tmp_path):
    from report_style_template_audit import find_inactive_css_emitting_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text("", encoding="utf-8")
    (includes_dir / "report_styles_unused.html.j2").write_text(
        "body { align-items: center; }\n",
        encoding="utf-8",
    )

    offenders = find_inactive_css_emitting_templates(templates_dir)

    assert offenders == ["includes/report_styles_unused.html.j2"]


def test_inactive_report_style_output_templates_detects_plain_text_output(tmp_path):
    from report_style_template_audit import find_inactive_report_style_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text("", encoding="utf-8")
    (includes_dir / "report_styles_unused.html.j2").write_text(
        "legacy dormant note\n",
        encoding="utf-8",
    )

    offenders = find_inactive_report_style_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_unused.html.j2"]


def test_empty_active_report_style_templates_are_reported(tmp_path):
    from report_style_template_audit import (
        find_empty_active_report_style_templates,
        find_report_style_template_contract_violations,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_empty.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_empty.html.j2").write_text("{# dormant active leaf #}\n", encoding="utf-8")
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_empty_active_report_style_templates(templates_dir)
    contract_violations = find_report_style_template_contract_violations(templates_dir)

    assert offenders == ["includes/report_styles_empty.html.j2"]
    assert contract_violations == [
        "empty_active_templates: includes/report_styles_empty.html.j2"
    ]


def test_active_report_style_non_css_output_templates_are_reported(tmp_path):
    from report_style_template_audit import (
        find_active_report_style_non_css_output_templates,
        find_report_style_template_contract_violations,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_note.html.j2").write_text("legacy active note\n", encoding="utf-8")
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)
    contract_violations = find_report_style_template_contract_violations(templates_dir)

    assert offenders == ["includes/report_styles_note.html.j2"]
    assert contract_violations == [
        "active_non_css_output_templates: includes/report_styles_note.html.j2"
    ]


def test_active_report_style_non_css_output_templates_reject_mixed_css_and_prose(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_mixed.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_mixed.html.j2").write_text(
        ".mixed { color: red; }\n"
        "legacy active note\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_mixed.html.j2"]


def test_active_report_style_non_css_output_templates_reject_inline_css_with_trailing_prose(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_mixed.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_mixed.html.j2").write_text(
        ".mixed { color: red; } legacy active note\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_mixed.html.j2"]


def test_active_report_style_non_css_output_templates_reject_inline_rule_body_prose(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_body_note.html.j2" %}\n'
        '{% include "includes/report_styles_mixed_body.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_body_note.html.j2").write_text(
        ".mixed { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_mixed_body.html.j2").write_text(
        ".mixed { color: red; active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(
        ".real { color: red; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_body_note.html.j2",
        "includes/report_styles_mixed_body.html.j2",
    ]


def test_active_report_style_non_css_output_templates_allow_final_declaration_without_semicolon(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_final_color.html.j2" %}\n'
        '{% include "includes/report_styles_final_var.html.j2" %}\n'
        '{% include "includes/report_styles_final_token.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_final_color.html.j2").write_text(
        ".metric { color: red }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_final_var.html.j2").write_text(
        ".metric { margin: 0; color: var(--text-primary) }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_final_token.html.j2").write_text(
        ":root { --report-token: 1rem }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_allow_interactive_pseudo_rules(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_button_hover.html.j2" %}\n'
        '{% include "includes/report_styles_link_focus.html.j2" %}\n'
        '{% include "includes/report_styles_input_disabled.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_button_hover.html.j2").write_text(
        "button:hover { background: var(--accent-blue); }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_link_focus.html.j2").write_text(
        "a:focus-visible { outline: 2px solid var(--accent-blue); }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_input_disabled.html.j2").write_text(
        "input:disabled { opacity: 0.5 }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_allow_a_prefixed_declarations(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_alignment.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_alignment.html.j2").write_text(
        ".metric {\n"
        "  align-items: center;\n"
        "  animation-duration: 120ms;\n"
        "}\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_allow_disclosure_rules(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_disclosure.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_disclosure.html.j2").write_text(
        "details { border: 1px solid var(--border); }\n"
        "summary { cursor: pointer; }\n"
        "details[open] > summary { margin-bottom: 8px; }\n"
        "summary::-webkit-details-marker { display: none; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_allow_definition_list_rules(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_definition_list.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_definition_list.html.j2").write_text(
        "dl { display: grid; }\n"
        "dt { font-weight: 700; }\n"
        "dd { margin: 0; }\n"
        "dl > dd { color: var(--text-secondary); }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_allow_chart_canvas_rules(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_chart_canvas_element.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_chart_canvas_element.html.j2").write_text(
        "canvas { max-width: 100%; }\n"
        "figure canvas { display: block; }\n"
        "main canvas { width: 100%; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_allow_line_break_rules(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_line_breaks.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_line_breaks.html.j2").write_text(
        "br { display: none; }\n"
        "p br { display: block; }\n"
        "small br { display: inline; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_active_report_style_non_css_output_templates_reject_declaration_with_trailing_prose(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_mixed.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_mixed.html.j2").write_text(
        "color: red; legacy active note\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_mixed.html.j2"]


def test_active_report_style_non_css_output_templates_reject_brace_declaration_with_trailing_prose(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_mixed.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_mixed.html.j2").write_text(
        'content: "{"; legacy active note\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_mixed.html.j2"]


def test_active_report_style_non_css_output_templates_reject_prose_colon_notes(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_note.html.j2").write_text("legacy: active note\n", encoding="utf-8")
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_note.html.j2"]


def test_active_report_style_non_css_output_templates_reject_prose_class_and_id_notes(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_note.html.j2").write_text(
        "legacy .note marker #todo marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_note.html.j2"]


def test_active_report_style_non_css_output_templates_reject_prose_brace_notes(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_note.html.j2").write_text(
        "legacy { active note }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_note.html.j2"]


def test_active_report_style_non_css_output_templates_reject_prose_custom_property_notes(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_note.html.j2").write_text(
        "legacy --note: active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_note.html.j2"]


def test_active_report_style_non_css_output_templates_reject_prose_at_rule_notes(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_media_note.html.j2" %}\n'
        '{% include "includes/report_styles_keyframes_note.html.j2" %}\n'
        '{% include "includes/report_styles_supports_note.html.j2" %}\n'
        '{% include "includes/report_styles_container_note.html.j2" %}\n'
        '{% include "includes/report_styles_layer_note.html.j2" %}\n'
        '{% include "includes/report_styles_page_note.html.j2" %}\n'
        '{% include "includes/report_styles_font_face_note.html.j2" %}\n'
        '{% include "includes/report_styles_property_note.html.j2" %}\n'
        '{% include "includes/report_styles_scope_note.html.j2" %}\n'
        '{% include "includes/report_styles_starting_style_note.html.j2" %}\n'
        '{% include "includes/report_styles_counter_style_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_media_note.html.j2").write_text(
        "legacy @media active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_keyframes_note.html.j2").write_text(
        "legacy @keyframes active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_supports_note.html.j2").write_text(
        "legacy @supports active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_container_note.html.j2").write_text(
        "legacy @container active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_layer_note.html.j2").write_text(
        "legacy @layer active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_page_note.html.j2").write_text(
        "legacy @page active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_font_face_note.html.j2").write_text(
        "legacy @font-face active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_property_note.html.j2").write_text(
        "legacy @property active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_scope_note.html.j2").write_text(
        "legacy @scope active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_starting_style_note.html.j2").write_text(
        "legacy @starting-style active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_counter_style_note.html.j2").write_text(
        "legacy @counter-style active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_container_note.html.j2",
        "includes/report_styles_counter_style_note.html.j2",
        "includes/report_styles_font_face_note.html.j2",
        "includes/report_styles_keyframes_note.html.j2",
        "includes/report_styles_layer_note.html.j2",
        "includes/report_styles_media_note.html.j2",
        "includes/report_styles_page_note.html.j2",
        "includes/report_styles_property_note.html.j2",
        "includes/report_styles_scope_note.html.j2",
        "includes/report_styles_starting_style_note.html.j2",
        "includes/report_styles_supports_note.html.j2",
    ]


def test_active_report_style_non_css_output_templates_reject_prose_at_rule_wrappers(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_media_note.html.j2" %}\n'
        '{% include "includes/report_styles_keyframes_note.html.j2" %}\n'
        '{% include "includes/report_styles_supports_note.html.j2" %}\n'
        '{% include "includes/report_styles_container_note.html.j2" %}\n'
        '{% include "includes/report_styles_layer_note.html.j2" %}\n'
        '{% include "includes/report_styles_page_note.html.j2" %}\n'
        '{% include "includes/report_styles_font_face_note.html.j2" %}\n'
        '{% include "includes/report_styles_property_note.html.j2" %}\n'
        '{% include "includes/report_styles_scope_note.html.j2" %}\n'
        '{% include "includes/report_styles_starting_style_note.html.j2" %}\n'
        '{% include "includes/report_styles_counter_style_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_media_note.html.j2").write_text(
        "legacy @media (max-width: 640px) { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_keyframes_note.html.j2").write_text(
        "legacy @keyframes pulse { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_supports_note.html.j2").write_text(
        "legacy @supports (display: grid) { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_container_note.html.j2").write_text(
        "legacy @container (min-width: 480px) { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_layer_note.html.j2").write_text(
        "legacy @layer report { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_page_note.html.j2").write_text(
        "legacy @page { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_font_face_note.html.j2").write_text(
        "legacy @font-face { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_property_note.html.j2").write_text(
        "legacy @property --report-tone { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_scope_note.html.j2").write_text(
        "legacy @scope (.report) { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_starting_style_note.html.j2").write_text(
        "legacy @starting-style { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_counter_style_note.html.j2").write_text(
        "legacy @counter-style report-list { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_container_note.html.j2",
        "includes/report_styles_counter_style_note.html.j2",
        "includes/report_styles_font_face_note.html.j2",
        "includes/report_styles_keyframes_note.html.j2",
        "includes/report_styles_layer_note.html.j2",
        "includes/report_styles_media_note.html.j2",
        "includes/report_styles_page_note.html.j2",
        "includes/report_styles_property_note.html.j2",
        "includes/report_styles_scope_note.html.j2",
        "includes/report_styles_starting_style_note.html.j2",
        "includes/report_styles_supports_note.html.j2",
    ]


def test_active_report_style_non_css_output_templates_reject_unclosed_comment_notes(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_note.html.j2").write_text(
        "legacy /* active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_note.html.j2"]


def test_active_report_style_non_css_output_templates_reject_prose_selector_wrappers(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_class_note.html.j2" %}\n'
        '{% include "includes/report_styles_id_note.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_note.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_element_note.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_function_note.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_function_list_note.html.j2" %}\n'
        '{% include "includes/report_styles_ampersand_note.html.j2" %}\n'
        '{% include "includes/report_styles_attribute_note.html.j2" %}\n'
        '{% include "includes/report_styles_combinator_note.html.j2" %}\n'
        '{% include "includes/report_styles_interactive_attribute_note.html.j2" %}\n'
        '{% include "includes/report_styles_interactive_attribute_list_note.html.j2" %}\n'
        '{% include "includes/report_styles_interactive_element_note.html.j2" %}\n'
        '{% include "includes/report_styles_interactive_element_list_note.html.j2" %}\n'
        '{% include "includes/report_styles_interactive_prefix_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_class_note.html.j2").write_text(
        "legacy .note { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_id_note.html.j2").write_text(
        "legacy #todo { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_note.html.j2").write_text(
        "legacy :root { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_element_note.html.j2").write_text(
        "legacy ::selection { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_function_note.html.j2").write_text(
        "legacy :where(.report) { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_function_list_note.html.j2").write_text(
        "legacy :where(.report), active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_ampersand_note.html.j2").write_text(
        "legacy &:hover { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_attribute_note.html.j2").write_text(
        'legacy [data-density="compact"] { active marker }\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_combinator_note.html.j2").write_text(
        "legacy > .metric { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_interactive_attribute_note.html.j2").write_text(
        'legacy input[type="search"] { active marker }\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_interactive_attribute_list_note.html.j2").write_text(
        'legacy input[type="search"], active marker\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_interactive_element_note.html.j2").write_text(
        "legacy button { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_interactive_element_list_note.html.j2").write_text(
        "legacy button, active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_interactive_prefix_note.html.j2").write_text(
        "audit-note { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_ampersand_note.html.j2",
        "includes/report_styles_attribute_note.html.j2",
        "includes/report_styles_class_note.html.j2",
        "includes/report_styles_combinator_note.html.j2",
        "includes/report_styles_id_note.html.j2",
        "includes/report_styles_interactive_attribute_list_note.html.j2",
        "includes/report_styles_interactive_attribute_note.html.j2",
        "includes/report_styles_interactive_element_list_note.html.j2",
        "includes/report_styles_interactive_element_note.html.j2",
        "includes/report_styles_interactive_prefix_note.html.j2",
        "includes/report_styles_pseudo_element_note.html.j2",
        "includes/report_styles_pseudo_function_list_note.html.j2",
        "includes/report_styles_pseudo_function_note.html.j2",
        "includes/report_styles_pseudo_note.html.j2",
    ]


def test_active_report_style_non_css_output_templates_reject_prose_declaration_notes(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_custom_note.html.j2" %}\n'
        '{% include "includes/report_styles_property_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_custom_note.html.j2").write_text(
        "legacy --note: active marker;\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_property_note.html.j2").write_text(
        "legacy color: red;\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_custom_note.html.j2",
        "includes/report_styles_property_note.html.j2",
    ]


def test_active_report_style_non_css_output_templates_reject_disallowed_interactive_child(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_button_span_child.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_button_span_child.html.j2").write_text(
        "button.report-filter > span {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(
        ".real { color: red; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_button_span_child.html.j2"]


def test_active_report_style_non_css_output_templates_reject_disallowed_pseudo_tail(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_input_placeholder_tail.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_input_placeholder_tail.html.j2").write_text(
        "input::placeholder > span {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(
        ".real { color: red; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == ["includes/report_styles_input_placeholder_tail.html.j2"]


def test_active_report_style_non_css_output_templates_reject_disallowed_interactive_list_tail(
    tmp_path,
):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_button_span_list_tail.html.j2" %}\n'
        '{% include "includes/report_styles_input_placeholder_list_tail.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_button_span_list_tail.html.j2").write_text(
        "button.report-filter > span,\n"
        "input[type=\"search\"] {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_input_placeholder_list_tail.html.j2").write_text(
        "input::placeholder > span,\n"
        "button.report-filter {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(
        ".real { color: red; }\n",
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_button_span_list_tail.html.j2",
        "includes/report_styles_input_placeholder_list_tail.html.j2",
    ]


def test_active_report_style_non_css_output_templates_reject_prose_element_wrappers(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_body_note.html.j2" %}\n'
        '{% include "includes/report_styles_blockquote_note.html.j2" %}\n'
        '{% include "includes/report_styles_caption_note.html.j2" %}\n'
        '{% include "includes/report_styles_charset_note.html.j2" %}\n'
        '{% include "includes/report_styles_code_note.html.j2" %}\n'
        '{% include "includes/report_styles_h2_note.html.j2" %}\n'
        '{% include "includes/report_styles_h2_list_note.html.j2" %}\n'
        '{% include "includes/report_styles_h2_pseudo_note.html.j2" %}\n'
        '{% include "includes/report_styles_h2_pseudo_list_note.html.j2" %}\n'
        '{% include "includes/report_styles_em_note.html.j2" %}\n'
        '{% include "includes/report_styles_figcaption_note.html.j2" %}\n'
        '{% include "includes/report_styles_figure_note.html.j2" %}\n'
        '{% include "includes/report_styles_heading_id_note.html.j2" %}\n'
        '{% include "includes/report_styles_hr_note.html.j2" %}\n'
        '{% include "includes/report_styles_html_note.html.j2" %}\n'
        '{% include "includes/report_styles_import_note.html.j2" %}\n'
        '{% include "includes/report_styles_layer_statement_note.html.j2" %}\n'
        '{% include "includes/report_styles_li_marker_note.html.j2" %}\n'
        '{% include "includes/report_styles_list_attribute_note.html.j2" %}\n'
        '{% include "includes/report_styles_list_child_note.html.j2" %}\n'
        '{% include "includes/report_styles_namespace_note.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph_adjacent_note.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph_class_note.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph_note.html.j2" %}\n'
        '{% include "includes/report_styles_path_note.html.j2" %}\n'
        '{% include "includes/report_styles_pre_note.html.j2" %}\n'
        '{% include "includes/report_styles_small_note.html.j2" %}\n'
        '{% include "includes/report_styles_strong_note.html.j2" %}\n'
        '{% include "includes/report_styles_svg_note.html.j2" %}\n'
        '{% include "includes/report_styles_table_note.html.j2" %}\n'
        '{% include "includes/report_styles_thead_note.html.j2" %}\n'
        '{% include "includes/report_styles_thead_cell_note.html.j2" %}\n'
        '{% include "includes/report_styles_tbody_note.html.j2" %}\n'
        '{% include "includes/report_styles_tbody_row_state_note.html.j2" %}\n'
        '{% include "includes/report_styles_tfoot_note.html.j2" %}\n'
        '{% include "includes/report_styles_tr_note.html.j2" %}\n'
        '{% include "includes/report_styles_th_note.html.j2" %}\n'
        '{% include "includes/report_styles_td_note.html.j2" %}\n'
        '{% include "includes/report_styles_ul_note.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_body_note.html.j2").write_text(
        "legacy body { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_blockquote_note.html.j2").write_text(
        "legacy blockquote { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_caption_note.html.j2").write_text(
        "legacy caption { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_charset_note.html.j2").write_text(
        'legacy @charset "UTF-8";\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_code_note.html.j2").write_text(
        "legacy code { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_h2_note.html.j2").write_text(
        "legacy h2 { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_h2_list_note.html.j2").write_text(
        "legacy h2, active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_h2_pseudo_note.html.j2").write_text(
        "legacy h2:first-child { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_h2_pseudo_list_note.html.j2").write_text(
        "legacy h2:first-child, active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_em_note.html.j2").write_text(
        "legacy em { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_figcaption_note.html.j2").write_text(
        "legacy figcaption.caption { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_figure_note.html.j2").write_text(
        "legacy figure { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading_id_note.html.j2").write_text(
        "legacy h2#summary { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_hr_note.html.j2").write_text(
        "legacy hr.section-divider { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_html_note.html.j2").write_text(
        "legacy html { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_import_note.html.j2").write_text(
        'legacy @import url("/fonts/report.css");\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_layer_statement_note.html.j2").write_text(
        "legacy @layer reset, report;\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_li_marker_note.html.j2").write_text(
        "legacy li::marker { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_list_attribute_note.html.j2").write_text(
        'legacy ul[data-density="compact"] { active marker }\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_list_child_note.html.j2").write_text(
        "legacy ul > li { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_namespace_note.html.j2").write_text(
        'legacy @namespace svg url("http://www.w3.org/2000/svg");\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph_adjacent_note.html.j2").write_text(
        "legacy p + p { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph_class_note.html.j2").write_text(
        "legacy p.lead { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph_note.html.j2").write_text(
        "legacy p { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_path_note.html.j2").write_text(
        "legacy path { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pre_note.html.j2").write_text(
        "legacy pre, active marker\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_small_note.html.j2").write_text(
        "legacy small.disclaimer { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_strong_note.html.j2").write_text(
        "legacy strong { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_svg_note.html.j2").write_text(
        "legacy svg.report-chart { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_note.html.j2").write_text(
        "legacy table { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_thead_note.html.j2").write_text(
        "legacy thead { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_thead_cell_note.html.j2").write_text(
        "legacy thead th { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_tbody_note.html.j2").write_text(
        "legacy tbody { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_tbody_row_state_note.html.j2").write_text(
        "legacy tbody tr:nth-child(even) { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_tfoot_note.html.j2").write_text(
        "legacy tfoot { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_tr_note.html.j2").write_text(
        "legacy tr { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_th_note.html.j2").write_text(
        "legacy th { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_td_note.html.j2").write_text(
        "legacy td { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_ul_note.html.j2").write_text(
        "legacy ul { active marker }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == [
        "includes/report_styles_blockquote_note.html.j2",
        "includes/report_styles_body_note.html.j2",
        "includes/report_styles_caption_note.html.j2",
        "includes/report_styles_charset_note.html.j2",
        "includes/report_styles_code_note.html.j2",
        "includes/report_styles_em_note.html.j2",
        "includes/report_styles_figcaption_note.html.j2",
        "includes/report_styles_figure_note.html.j2",
        "includes/report_styles_h2_list_note.html.j2",
        "includes/report_styles_h2_note.html.j2",
        "includes/report_styles_h2_pseudo_list_note.html.j2",
        "includes/report_styles_h2_pseudo_note.html.j2",
        "includes/report_styles_heading_id_note.html.j2",
        "includes/report_styles_hr_note.html.j2",
        "includes/report_styles_html_note.html.j2",
        "includes/report_styles_import_note.html.j2",
        "includes/report_styles_layer_statement_note.html.j2",
        "includes/report_styles_li_marker_note.html.j2",
        "includes/report_styles_list_attribute_note.html.j2",
        "includes/report_styles_list_child_note.html.j2",
        "includes/report_styles_namespace_note.html.j2",
        "includes/report_styles_paragraph_adjacent_note.html.j2",
        "includes/report_styles_paragraph_class_note.html.j2",
        "includes/report_styles_paragraph_note.html.j2",
        "includes/report_styles_path_note.html.j2",
        "includes/report_styles_pre_note.html.j2",
        "includes/report_styles_small_note.html.j2",
        "includes/report_styles_strong_note.html.j2",
        "includes/report_styles_svg_note.html.j2",
        "includes/report_styles_table_note.html.j2",
        "includes/report_styles_tbody_note.html.j2",
        "includes/report_styles_tbody_row_state_note.html.j2",
        "includes/report_styles_td_note.html.j2",
        "includes/report_styles_tfoot_note.html.j2",
        "includes/report_styles_th_note.html.j2",
        "includes/report_styles_thead_cell_note.html.j2",
        "includes/report_styles_thead_note.html.j2",
        "includes/report_styles_tr_note.html.j2",
        "includes/report_styles_ul_note.html.j2",
    ]


def test_active_report_style_non_css_output_templates_allow_css_wrappers_and_comments(tmp_path):
    from report_style_template_audit import find_active_report_style_non_css_output_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_comment.html.j2" %}\n'
        '{% include "includes/report_styles_comment_block.html.j2" %}\n'
        '{% include "includes/report_styles_reset.html.j2" %}\n'
        '{% include "includes/report_styles_selector_list.html.j2" %}\n'
        '{% include "includes/report_styles_body.html.j2" %}\n'
        '{% include "includes/report_styles_table.html.j2" %}\n'
        '{% include "includes/report_styles_table_cells.html.j2" %}\n'
        '{% include "includes/report_styles_table_rows.html.j2" %}\n'
        '{% include "includes/report_styles_table_sections.html.j2" %}\n'
        '{% include "includes/report_styles_table_section_cells.html.j2" %}\n'
        '{% include "includes/report_styles_table_row_states.html.j2" %}\n'
        '{% include "includes/report_styles_table_caption.html.j2" %}\n'
        '{% include "includes/report_styles_heading.html.j2" %}\n'
        '{% include "includes/report_styles_heading_list.html.j2" %}\n'
        '{% include "includes/report_styles_heading_pseudo.html.j2" %}\n'
        '{% include "includes/report_styles_heading_pseudo_list.html.j2" %}\n'
        '{% include "includes/report_styles_heading_id.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph_adjacent.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph_class.html.j2" %}\n'
        '{% include "includes/report_styles_heading_paragraph.html.j2" %}\n'
        '{% include "includes/report_styles_list.html.j2" %}\n'
        '{% include "includes/report_styles_list_attribute.html.j2" %}\n'
        '{% include "includes/report_styles_list_child.html.j2" %}\n'
        '{% include "includes/report_styles_list_marker.html.j2" %}\n'
        '{% include "includes/report_styles_paragraph_adjacent_list.html.j2" %}\n'
        '{% include "includes/report_styles_qualified_element_list.html.j2" %}\n'
        '{% include "includes/report_styles_strong.html.j2" %}\n'
        '{% include "includes/report_styles_em.html.j2" %}\n'
        '{% include "includes/report_styles_small.html.j2" %}\n'
        '{% include "includes/report_styles_inline_text_list.html.j2" %}\n'
        '{% include "includes/report_styles_figure.html.j2" %}\n'
        '{% include "includes/report_styles_figcaption.html.j2" %}\n'
        '{% include "includes/report_styles_figure_caption_descendant.html.j2" %}\n'
        '{% include "includes/report_styles_blockquote.html.j2" %}\n'
        '{% include "includes/report_styles_pre_code_list.html.j2" %}\n'
        '{% include "includes/report_styles_hr.html.j2" %}\n'
        '{% include "includes/report_styles_landmark_layout.html.j2" %}\n'
        '{% include "includes/report_styles_section_heading_descendant.html.j2" %}\n'
        '{% include "includes/report_styles_section_table_descendant.html.j2" %}\n'
        '{% include "includes/report_styles_section_svg_descendant.html.j2" %}\n'
        '{% include "includes/report_styles_section_button_descendant.html.j2" %}\n'
        '{% include "includes/report_styles_section_child_button.html.j2" %}\n'
        '{% include "includes/report_styles_svg_chart.html.j2" %}\n'
        '{% include "includes/report_styles_tokens.html.j2" %}\n'
        '{% include "includes/report_styles_dynamic_accent.html.j2" %}\n'
        '{% include "includes/report_styles_nested_selector.html.j2" %}\n'
        '{% include "includes/report_styles_nested_combinator.html.j2" %}\n'
        '{% include "includes/report_styles_attribute_selector.html.j2" %}\n'
        '{% include "includes/report_styles_input_placeholder.html.j2" %}\n'
        '{% include "includes/report_styles_button.html.j2" %}\n'
        '{% include "includes/report_styles_button_list.html.j2" %}\n'
        '{% include "includes/report_styles_input_attribute.html.j2" %}\n'
        '{% include "includes/report_styles_input_attribute_list.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_element.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_function.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_function_descendant.html.j2" %}\n'
        '{% include "includes/report_styles_pseudo_function_selector_list.html.j2" %}\n'
        '{% include "includes/report_styles_brace_content.html.j2" %}\n'
        '{% include "includes/report_styles_commented_rule.html.j2" %}\n'
        '{% include "includes/report_styles_media.html.j2" %}\n'
        '{% include "includes/report_styles_supports.html.j2" %}\n'
        '{% include "includes/report_styles_container.html.j2" %}\n'
        '{% include "includes/report_styles_layer.html.j2" %}\n'
        '{% include "includes/report_styles_layer_statement.html.j2" %}\n'
        '{% include "includes/report_styles_page.html.j2" %}\n'
        '{% include "includes/report_styles_font_face.html.j2" %}\n'
        '{% include "includes/report_styles_property.html.j2" %}\n'
        '{% include "includes/report_styles_keyframes.html.j2" %}\n'
        '{% include "includes/report_styles_scope.html.j2" %}\n'
        '{% include "includes/report_styles_starting_style.html.j2" %}\n'
        '{% include "includes/report_styles_counter_style.html.j2" %}\n'
        '{% include "includes/report_styles_import.html.j2" %}\n'
        '{% include "includes/report_styles_charset.html.j2" %}\n'
        '{% include "includes/report_styles_namespace.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_comment.html.j2").write_text(
        "/* report section */\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_comment_block.html.j2").write_text(
        "/*\n"
        "  report section notes\n"
        "*/\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_reset.html.j2").write_text(
        "* { box-sizing: border-box; }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_selector_list.html.j2").write_text(
        ".one,\n"
        ".two {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_body.html.j2").write_text(
        "body {\n"
        '  {% include "includes/report_styles_body_color.html.j2" %}\n'
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_body_color.html.j2").write_text("color: red;\n", encoding="utf-8")
    (includes_dir / "report_styles_table.html.j2").write_text(
        "table {\n"
        "  border-collapse: collapse;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_cells.html.j2").write_text(
        "table,\n"
        "th,\n"
        "td {\n"
        "  border-color: #d1d5db;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_rows.html.j2").write_text(
        "tr {\n"
        "  border-bottom: 1px solid #e5e7eb;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_sections.html.j2").write_text(
        "thead,\n"
        "tbody,\n"
        "tfoot {\n"
        "  background: #f9fafb;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_section_cells.html.j2").write_text(
        "thead th,\n"
        "tbody td {\n"
        "  padding: 0.5rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_row_states.html.j2").write_text(
        "tbody tr:nth-child(even),\n"
        "tbody tr:hover {\n"
        "  background: #eef6ff;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_table_caption.html.j2").write_text(
        "caption,\n"
        "table caption {\n"
        "  caption-side: bottom;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading.html.j2").write_text(
        "h2 {\n"
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading_list.html.j2").write_text(
        "h2,\n"
        "h3 {\n"
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading_pseudo.html.j2").write_text(
        "h2:first-child {\n"
        "  margin-top: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading_pseudo_list.html.j2").write_text(
        "h2:first-child,\n"
        "h3:first-child {\n"
        "  margin-top: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading_id.html.j2").write_text(
        "h2#summary {\n"
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph.html.j2").write_text(
        "p {\n"
        "  line-height: 1.6;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph_adjacent.html.j2").write_text(
        "p + p {\n"
        "  margin-top: 1rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph_class.html.j2").write_text(
        "p.lead {\n"
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_heading_paragraph.html.j2").write_text(
        "h2 + p {\n"
        "  margin-top: 0.5rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_list.html.j2").write_text(
        "ul {\n"
        "  padding-left: 1rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_list_attribute.html.j2").write_text(
        'ul[data-density="compact"] {\n'
        "  gap: 0.25rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_list_child.html.j2").write_text(
        "ul > li {\n"
        "  margin-bottom: 0.25rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_qualified_element_list.html.j2").write_text(
        "p.lead,\n"
        'ul[data-density="compact"] {\n'
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_list_marker.html.j2").write_text(
        "li::marker {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_paragraph_adjacent_list.html.j2").write_text(
        "p + p,\n"
        "ul > li {\n"
        "  margin-top: 1rem;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_strong.html.j2").write_text(
        "strong {\n"
        "  font-weight: 700;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_em.html.j2").write_text(
        "em {\n"
        "  font-style: italic;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_small.html.j2").write_text(
        "small.disclaimer {\n"
        "  color: #666;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_inline_text_list.html.j2").write_text(
        "strong,\n"
        "em {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_figure.html.j2").write_text(
        "figure {\n"
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_figcaption.html.j2").write_text(
        "figcaption.caption {\n"
        "  color: #666;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_figure_caption_descendant.html.j2").write_text(
        "figure figcaption.caption {\n"
        "  color: #666;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_blockquote.html.j2").write_text(
        "blockquote {\n"
        "  margin: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pre_code_list.html.j2").write_text(
        "pre,\n"
        "code {\n"
        "  font-family: monospace;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_hr.html.j2").write_text(
        "hr.section-divider {\n"
        "  border: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_landmark_layout.html.j2").write_text(
        "main,\n"
        "section.report-section,\n"
        "article,\n"
        "aside,\n"
        "header,\n"
        "footer,\n"
        "nav.report-nav {\n"
        "  display: block;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_section_heading_descendant.html.j2").write_text(
        "section.report-section h2 {\n"
        "  margin-top: 0;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_section_table_descendant.html.j2").write_text(
        "section.report-section table {\n"
        "  width: 100%;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_section_svg_descendant.html.j2").write_text(
        "section.report-section svg path {\n"
        "  fill: currentColor;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_section_button_descendant.html.j2").write_text(
        "section.report-section button.report-filter {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_section_child_button.html.j2").write_text(
        "section.report-section > button.report-filter {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_svg_chart.html.j2").write_text(
        "svg.report-chart,\n"
        "svg path,\n"
        "g.axis text,\n"
        "circle.value-marker,\n"
        "rect.bar,\n"
        "line.threshold {\n"
        "  fill: currentColor;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_tokens.html.j2").write_text(
        ":root {\n"
        '  {% include "includes/report_styles_token_value.html.j2" %}\n'
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_token_value.html.j2").write_text("--report-token: 1rem;\n", encoding="utf-8")
    (includes_dir / "report_styles_dynamic_accent.html.j2").write_text(
        ".accent {\n"
        "  color: {{ rec_color }}; /* recommendation tone */\n"
        "  -webkit-background-clip: text;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_nested_selector.html.j2").write_text(
        ".metric {\n"
        "  &:hover,\n"
        "  &:focus {\n"
        "    color: red;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_nested_combinator.html.j2").write_text(
        ".card {\n"
        "  > .metric,\n"
        "  + .metric-alt,\n"
        "  ~ .trend {\n"
        "    margin-top: 0;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_attribute_selector.html.j2").write_text(
        '[data-density="compact"] {\n'
        "  --report-card-gap: 8px;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_input_placeholder.html.j2").write_text(
        "input::placeholder {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_button.html.j2").write_text(
        "button {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_button_list.html.j2").write_text(
        "button,\n"
        'input[type="search"] {\n'
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_input_attribute.html.j2").write_text(
        'input[type="search"] {\n'
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_input_attribute_list.html.j2").write_text(
        'input[type="search"],\n'
        "button.report-filter {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_element.html.j2").write_text(
        "::selection {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_function.html.j2").write_text(
        ":where(.report) {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_function_descendant.html.j2").write_text(
        ":where(.report) .metric {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo_function_selector_list.html.j2").write_text(
        ":where(.report),\n"
        ":where(.report-snapshot) {\n"
        "  color: red;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_brace_content.html.j2").write_text(
        ".brace::after {\n"
        '  content: "}";\n'
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_commented_rule.html.j2").write_text(
        ".commented { color: blue; } /* inline rule note */\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_media.html.j2").write_text(
        "@media (max-width: 640px) {\n"
        "  .real { color: red; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_supports.html.j2").write_text(
        "@supports (display: grid) {\n"
        "  .real { display: grid; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_container.html.j2").write_text(
        "@container (min-width: 480px) {\n"
        "  .real { gap: 12px; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_layer.html.j2").write_text(
        "@layer report {\n"
        "  .real { color: red; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_layer_statement.html.j2").write_text(
        "@layer reset, report;\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_page.html.j2").write_text(
        "@page {\n"
        "  margin: 0.75in;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_font_face.html.j2").write_text(
        "@font-face {\n"
        '  font-family: "ReportSans";\n'
        '  src: url("/fonts/report-sans.woff2") format("woff2");\n'
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_property.html.j2").write_text(
        "@property --report-tone {\n"
        '  syntax: "<color>";\n'
        "  inherits: false;\n"
        "  initial-value: #1f7a4d;\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_keyframes.html.j2").write_text(
        "@keyframes report-pulse {\n"
        "  from { opacity: 0; }\n"
        "  50% { opacity: 0.5; }\n"
        "  to { opacity: 1; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_scope.html.j2").write_text(
        "@scope (.report) {\n"
        "  .metric { color: red; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_starting_style.html.j2").write_text(
        "@starting-style {\n"
        "  .metric { opacity: 0; }\n"
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_counter_style.html.j2").write_text(
        "@counter-style report-list {\n"
        "  system: numeric;\n"
        '  symbols: "0" "1" "2" "3" "4" "5" "6" "7" "8" "9";\n'
        '  suffix: ". ";\n'
        "}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_import.html.j2").write_text(
        '@import url("/fonts/report.css");\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_charset.html.j2").write_text(
        '@charset "UTF-8";\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_namespace.html.j2").write_text(
        '@namespace svg url("http://www.w3.org/2000/svg");\n',
        encoding="utf-8",
    )

    offenders = find_active_report_style_non_css_output_templates(templates_dir)

    assert offenders == []


def test_unapproved_active_report_style_expression_tags_are_reported(tmp_path):
    from report_style_template_audit import (
        find_report_style_template_contract_violations,
        find_unapproved_active_report_style_expression_tags,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_dynamic.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_dynamic.html.j2").write_text(
        ".dynamic { color: {{ user_color }}; }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_unapproved_active_report_style_expression_tags(templates_dir)
    contract_violations = find_report_style_template_contract_violations(templates_dir)

    assert offenders == ["includes/report_styles_dynamic.html.j2 -> user_color"]
    assert contract_violations == [
        "unapproved_expression_tags: includes/report_styles_dynamic.html.j2 -> user_color"
    ]


def test_unapproved_active_report_style_expression_tags_deduplicate_repeated_targets(
    tmp_path,
):
    from report_style_template_audit import find_unapproved_active_report_style_expression_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_dynamic.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_dynamic.html.j2").write_text(
        ".first { color: {{ user_color }}; }\n"
        ".second { border-color: {{ user_color }}; }\n",
        encoding="utf-8",
    )

    offenders = find_unapproved_active_report_style_expression_tags(templates_dir)

    assert offenders == ["includes/report_styles_dynamic.html.j2 -> user_color"]


def test_unapproved_active_report_style_expression_tags_allow_rec_color_and_comments(tmp_path):
    from report_style_template_audit import find_unapproved_active_report_style_expression_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_accent.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_accent.html.j2").write_text(
        "{# {{ user_color }} #}\n"
        ".accent { color: {{ rec_color }}; }\n",
        encoding="utf-8",
    )

    offenders = find_unapproved_active_report_style_expression_tags(templates_dir)

    assert offenders == []


def test_approved_report_style_expression_tags_must_stay_in_declaration_values(tmp_path):
    from report_style_template_audit import (
        find_report_style_template_contract_violations,
        find_unapproved_active_report_style_expression_tags,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_selector.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_selector.html.j2").write_text(
        ".{{ rec_color }} { color: red; }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(
        ".real { border: 1px solid {{ rec_color }}30; }\n",
        encoding="utf-8",
    )

    offenders = find_unapproved_active_report_style_expression_tags(templates_dir)
    contract_violations = find_report_style_template_contract_violations(templates_dir)

    assert offenders == ["includes/report_styles_selector.html.j2 -> rec_color"]
    assert contract_violations == [
        "unapproved_expression_tags: includes/report_styles_selector.html.j2 -> rec_color"
    ]


def test_approved_report_style_expression_tags_reject_pseudo_selector_context(tmp_path):
    from report_style_template_audit import find_unapproved_active_report_style_expression_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_pseudo.html.j2" %}\n'
        '{% include "includes/report_styles_values.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_pseudo.html.j2").write_text(
        ".card:hover {{ rec_color }} { color: red; }\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_values.html.j2").write_text(
        ".value { border: 1px solid {{ rec_color }}30; }\n"
        ".block {\n"
        "  color: {{ rec_color }};\n"
        "}\n",
        encoding="utf-8",
    )

    offenders = find_unapproved_active_report_style_expression_tags(templates_dir)

    assert offenders == ["includes/report_styles_pseudo.html.j2 -> rec_color"]


def test_unapproved_active_report_style_block_tags_are_reported(tmp_path):
    from report_style_template_audit import (
        find_report_style_template_contract_violations,
        find_unapproved_active_report_style_block_tags,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_conditional.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_conditional.html.j2").write_text(
        "{% if show_extra %}\n"
        ".extra { color: red; }\n"
        "{% endif %}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: blue; }\n", encoding="utf-8")

    offenders = find_unapproved_active_report_style_block_tags(templates_dir)
    contract_violations = find_report_style_template_contract_violations(templates_dir)

    assert offenders == [
        "includes/report_styles_conditional.html.j2 -> if show_extra",
        "includes/report_styles_conditional.html.j2 -> endif",
    ]
    assert contract_violations == [
        "unapproved_block_tags: includes/report_styles_conditional.html.j2 -> if show_extra",
        "unapproved_block_tags: includes/report_styles_conditional.html.j2 -> endif",
    ]


def test_unapproved_active_report_style_block_tags_deduplicate_repeated_targets(
    tmp_path,
):
    from report_style_template_audit import find_unapproved_active_report_style_block_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_conditional.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_conditional.html.j2").write_text(
        "{% if show_extra %}\n"
        ".first { color: red; }\n"
        "{% endif %}\n"
        "{% if show_extra %}\n"
        ".second { color: blue; }\n"
        "{% endif %}\n",
        encoding="utf-8",
    )

    offenders = find_unapproved_active_report_style_block_tags(templates_dir)

    assert offenders == [
        "includes/report_styles_conditional.html.j2 -> if show_extra",
        "includes/report_styles_conditional.html.j2 -> endif",
    ]


def test_unapproved_active_report_style_block_tags_allow_includes_and_comments(tmp_path):
    from report_style_template_audit import find_unapproved_active_report_style_block_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        "{# {% if commented %} #}\n"
        '{% include "includes/report_styles_real.html.j2" %}\n'
        "{# {% endif %} #}\n",
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: blue; }\n", encoding="utf-8")

    offenders = find_unapproved_active_report_style_block_tags(templates_dir)

    assert offenders == []


def test_single_child_passthrough_templates_ignore_jinja_comments(tmp_path):
    from report_style_template_audit import find_single_child_passthrough_templates

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{# legacy aggregation note #}\n'
        '{% include "includes/report_styles_base.html.j2" %}\n',
        encoding="utf-8",
    )

    offenders = find_single_child_passthrough_templates(templates_dir)

    assert offenders == [
        "includes/report_styles.html.j2 -> includes/report_styles_base.html.j2"
    ]


def test_active_report_style_template_cycles_are_reported(tmp_path):
    from report_style_template_audit import find_active_report_style_template_cycles

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_a.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_a.html.j2").write_text(
        '{% include "includes/report_styles_b.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_b.html.j2").write_text(
        '{% include "includes/report_styles_a.html.j2" %}\n',
        encoding="utf-8",
    )

    offenders = find_active_report_style_template_cycles(templates_dir)

    assert offenders == [
        "includes/report_styles.html.j2 -> includes/report_styles_a.html.j2 -> "
        "includes/report_styles_b.html.j2 -> includes/report_styles_a.html.j2"
    ]


def test_duplicate_active_report_style_includes_are_reported(tmp_path):
    from report_style_template_audit import find_duplicate_active_report_style_includes

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_real.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_duplicate_active_report_style_includes(templates_dir)

    assert offenders == [
        "includes/report_styles_real.html.j2 <- includes/report_styles.html.j2 (x2)"
    ]


def test_duplicate_active_report_style_includes_ignore_repeated_non_report_style_targets(tmp_path):
    from report_style_template_audit import (
        find_duplicate_active_report_style_includes,
        find_non_report_style_active_includes,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/non_style.html.j2" %}\n'
        '{% include "includes/non_style.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "non_style.html.j2").write_text(".non-style { color: red; }\n", encoding="utf-8")

    duplicates = find_duplicate_active_report_style_includes(templates_dir)
    boundary_violations = find_non_report_style_active_includes(templates_dir)

    assert duplicates == []
    assert boundary_violations == [
        "includes/report_styles.html.j2 -> includes/non_style.html.j2"
    ]


def test_non_report_style_active_includes_are_reported(tmp_path):
    from report_style_template_audit import find_non_report_style_active_includes

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/non_style.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "non_style.html.j2").write_text(".non-style { color: red; }\n", encoding="utf-8")

    offenders = find_non_report_style_active_includes(templates_dir)

    assert offenders == ["includes/report_styles.html.j2 -> includes/non_style.html.j2"]


def test_active_report_style_graph_does_not_recurse_into_non_report_style_includes(tmp_path):
    from report_style_template_audit import (
        find_missing_active_report_style_templates,
        find_non_report_style_active_includes,
    )

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/non_style.html.j2" %}\n'
        '{% include "includes/report_styles_real.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "non_style.html.j2").write_text(
        '{% include "includes/report_styles_missing.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    missing = find_missing_active_report_style_templates(templates_dir)
    boundary_violations = find_non_report_style_active_includes(templates_dir)

    assert missing == []
    assert boundary_violations == [
        "includes/report_styles.html.j2 -> includes/non_style.html.j2"
    ]


def test_dynamic_active_report_style_includes_are_reported(tmp_path):
    from report_style_template_audit import find_dynamic_active_report_style_includes

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        "{% include template_name %}\n",
        encoding="utf-8",
    )

    offenders = find_dynamic_active_report_style_includes(templates_dir)

    assert offenders == ["includes/report_styles.html.j2 -> template_name"]


def test_dynamic_active_report_style_includes_deduplicate_repeated_targets(tmp_path):
    from report_style_template_audit import find_dynamic_active_report_style_includes

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        "{% include template_name %}\n"
        "{% include template_name %}\n",
        encoding="utf-8",
    )

    offenders = find_dynamic_active_report_style_includes(templates_dir)

    assert offenders == ["includes/report_styles.html.j2 -> template_name"]


def test_optioned_active_report_style_includes_are_reported(tmp_path):
    from report_style_template_audit import find_optioned_active_report_style_includes

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_real.html.j2" ignore missing %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_optioned_active_report_style_includes(templates_dir)

    assert offenders == ['includes/report_styles.html.j2 -> "includes/report_styles_real.html.j2" ignore missing']


def test_optioned_active_report_style_includes_deduplicate_repeated_targets(tmp_path):
    from report_style_template_audit import find_optioned_active_report_style_includes

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_real.html.j2" ignore missing %}\n'
        '{% include "includes/report_styles_real.html.j2" ignore missing %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_real.html.j2").write_text(".real { color: red; }\n", encoding="utf-8")

    offenders = find_optioned_active_report_style_includes(templates_dir)

    assert offenders == [
        'includes/report_styles.html.j2 -> "includes/report_styles_real.html.j2" ignore missing'
    ]


def test_non_canonical_active_report_style_include_tags_are_reported(tmp_path):
    from report_style_template_audit import find_non_canonical_active_report_style_include_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include ["includes/report_styles_a.html.j2", "includes/report_styles_b.html.j2"] %}\n',
        encoding="utf-8",
    )

    offenders = find_non_canonical_active_report_style_include_tags(templates_dir)

    assert offenders == [
        'includes/report_styles.html.j2 -> ["includes/report_styles_a.html.j2", "includes/report_styles_b.html.j2"]'
    ]


def test_non_canonical_active_report_style_include_tags_deduplicate_repeated_targets(
    tmp_path,
):
    from report_style_template_audit import find_non_canonical_active_report_style_include_tags

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include ["includes/report_styles_a.html.j2", "includes/report_styles_b.html.j2"] %}\n'
        '{% include ["includes/report_styles_a.html.j2", "includes/report_styles_b.html.j2"] %}\n',
        encoding="utf-8",
    )

    offenders = find_non_canonical_active_report_style_include_tags(templates_dir)

    assert offenders == [
        'includes/report_styles.html.j2 -> ["includes/report_styles_a.html.j2", "includes/report_styles_b.html.j2"]'
    ]


def test_report_style_template_contract_aggregates_graph_violations(tmp_path):
    from report_style_template_audit import find_report_style_template_contract_violations

    templates_dir = tmp_path / "templates"
    includes_dir = templates_dir / "includes"
    includes_dir.mkdir(parents=True)
    (includes_dir / "report_styles.html.j2").write_text(
        '{% include "includes/report_styles_base.html.j2" %}\n',
        encoding="utf-8",
    )
    (includes_dir / "report_styles_base.html.j2").write_text(".base { color: red; }\n", encoding="utf-8")

    offenders = find_report_style_template_contract_violations(templates_dir)

    assert offenders == [
        "single_child_passthrough: includes/report_styles.html.j2 -> includes/report_styles_base.html.j2"
    ]


def test_report_style_template_contract_sorts_offenders_within_each_category(tmp_path, monkeypatch):
    import report_style_template_audit

    check_type = report_style_template_audit._CONTRACT_CHECKS[0].__class__

    def unordered_finder(_templates_dir):
        return ["z-template", "a-template"]

    monkeypatch.setattr(
        report_style_template_audit,
        "_CONTRACT_CHECKS",
        (check_type("unstable_category", unordered_finder),),
    )

    offenders = report_style_template_audit.find_report_style_template_contract_violations(tmp_path)

    assert offenders == [
        "unstable_category: a-template",
        "unstable_category: z-template",
    ]
