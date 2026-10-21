"""
Unit tests for deterministic multi-tenant visual primitives and runtime calculator synchronizer.
Verifies token bridging across Porcelain Light and Obsidian Dark themes, typography scale,
card geometry, table overflow containment, 44px touch targets, and retro-reflection idempotency.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from pseofactory.visual_primitives import (
    SCREEN_ARCHETYPE_CONTRACTS,
    VISUAL_PRIMITIVES_VERSION,
    classify_screen_archetype,
    detect_visual_and_ux_contract_issues,
    get_screen_archetype_contract,
    render_visual_primitives_style,
    render_runtime_synchronizer_script,
    normalize_html_visual_primitives,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.audit import audit_code_slop_ratchet, audit_visual_ui_quality_contract
from pseofactory.ui import UI_VISUAL_QUALITY_CONTRACT, verify_ui_visual_quality_contract


def test_visual_primitives_style_tokens_and_geometry():
    """Verifies visual primitives CSS block defines tokens, typography hierarchy, cards, tables, and touch targets."""
    porcelain_css = render_visual_primitives_style(is_tenant_porcelain=True)
    obsidian_css = render_visual_primitives_style(is_tenant_porcelain=False)

    assert f'data-version="{VISUAL_PRIMITIVES_VERSION}"' in porcelain_css
    assert 'id="pseo-visual-primitives"' in porcelain_css
    assert "--bg-canvas: #fbfcfd" in porcelain_css
    assert "--bg-elevated: #eff6ff" in porcelain_css
    assert "--bg: #07090e" in obsidian_css
    assert '[data-theme="porcelain"]' in porcelain_css

    # Deterministic typography scale
    assert "font-size: 32px !important;" in porcelain_css
    assert "font-size: 20px !important;" in porcelain_css
    assert "font-size: 16px !important;" in porcelain_css

    # Deterministic card geometry and table wrapper rules
    assert "border-radius: 12px !important;" in porcelain_css
    assert "padding: 24px !important;" in porcelain_css
    assert "overflow-x: auto !important;" in porcelain_css
    assert "font-variant-numeric: tabular-nums !important;" in porcelain_css

    # Deterministic 44px touch targets
    for selector in (
        ".touch-target",
        ".scenario-preset-link",
        ".on-this-page-nav a",
        ".cluster-link",
        ".overlay-hub-list a",
        ".partner-btn",
        ".btn-preset",
    ):
        assert selector in porcelain_css

    # Zero forbidden dashes
    assert "\u2014" not in porcelain_css
    assert "\u2013" not in porcelain_css


def test_runtime_synchronizer_script_contracts():
    """Verifies runtime synchronizer script handles presets, range sliders, and output updates."""
    script_html = render_runtime_synchronizer_script()
    assert 'id="pseo-runtime-sync"' in script_html
    assert f'data-version="{VISUAL_PRIMITIVES_VERSION}"' in script_html
    assert "e.preventDefault()" in script_html
    assert ".scenario-preset-link" in script_html
    assert 'input[type="range"]' in script_html
    assert ".output-value" in script_html
    assert "\u2014" not in script_html
    assert "\u2013" not in script_html


def test_normalize_html_visual_primitives_table_wrapping_and_idempotency():
    """Verifies unwrapped tables and matrix wrappers receive deterministic .table-wrap containment."""
    raw_html = """<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head>
<title>Test Tool</title>
</head>
<body>
<main class="container">
<h1>Primary Calculator Heading</h1>
<div class="card">
<h2>Scenario Matrix</h2>
<table><thead><tr><th>Tier</th><th>Rate</th></tr></thead><tbody><tr><td>1</td><td>10%</td></tr></tbody></table>
<div class="calc-matrix-table-wrap"><table><tr><td>Matrix</td></tr></table></div>
<div style="overflow-x: auto;"><table><tr><td>Inline Scroll</td></tr></table></div>
</div>
</main>
</body>
</html>"""

    normalized_once, actions_once = normalize_html_visual_primitives(raw_html)
    assert "visual_primitives_css" in actions_once
    assert "table_wrapper_normalization" in actions_once
    assert "interactive_runtime_sync" in actions_once
    assert 'id="pseo-visual-primitives"' in normalized_once
    assert 'id="pseo-runtime-sync"' in normalized_once
    assert '<div class="table-wrap pseo-table-wrap">\n<table>' in normalized_once
    assert 'class="calc-matrix-table-wrap table-wrap pseo-table-wrap"' in normalized_once
    assert '<div class="table-wrap pseo-table-wrap"><table><tr><td>Inline Scroll</td></tr></table></div>' in normalized_once

    # Verify strict idempotency on second pass
    normalized_twice, actions_twice = normalize_html_visual_primitives(normalized_once)
    assert actions_twice == []
    assert normalized_once == normalized_twice
    assert normalized_twice.count('id="pseo-visual-primitives"') == 1
    assert normalized_twice.count('id="pseo-runtime-sync"') == 1


def test_retro_reflection_engine_includes_visual_primitives():
    """Verifies RetroReflectionEngine audits and retrofits deterministic_visual_primitives."""
    engine = RetroReflectionEngine()
    sample_tool = """<!DOCTYPE html>
<html lang="en">
<head><title>Sample Calculator</title></head>
<body>
<main class="container">
<h1>Sample Calculator</h1>
<div class="calculator-shell"><input type="number" id="field-income" value="100000"><output id="val-tax">$20,000</output></div>
</main>
</body>
</html>"""
    missing_before = engine.audit_html_mechanics(sample_tool)
    assert "deterministic_visual_primitives" in missing_before

    retrofitted, actions = engine.retrofit_html(
        sample_tool,
        property_id="profithelm",
        slug="sample-calculator",
        canonical_url="https://profithelm.com/tools/sample-calculator/",
    )
    assert "deterministic_visual_primitives" in actions
    missing_after = engine.audit_html_mechanics(retrofitted)
    assert missing_after == []

    # Second pass must be idempotent
    retrofitted_again, actions_again = engine.retrofit_html(
        retrofitted,
        property_id="profithelm",
        slug="sample-calculator",
        canonical_url="https://profithelm.com/tools/sample-calculator/",
    )
    assert actions_again == []
    assert retrofitted_again == retrofitted


def test_slop_ratchet_passes_with_visual_primitives():
    """Verifies AST maintainability and duplication ratchet passes across all engine modules."""
    report = audit_code_slop_ratchet()
    assert report["passed"] is True, f"Slop ratchet failed: {report}"


def test_screen_archetype_classification_and_contracts():
    """Verifies all 4 screen archetypes are classified and bound to measurable visual quality contracts."""
    assert set(SCREEN_ARCHETYPE_CONTRACTS.keys()) == {
        "interactive_calculator",
        "statutory_guide",
        "comparison_page",
        "index_hub",
    }

    hub_html = "<html><body><main><h1>Directory Hub</h1></main></body></html>"
    assert classify_screen_archetype(hub_html, rel_path="index.html") == "index_hub"
    assert classify_screen_archetype(hub_html, rel_path="tools/index.html") == "index_hub"

    calc_html = '<html><body><main><h1>Calc</h1><form class="calculator-form"><input type="number" data-calc-input="x"></form></main></body></html>'
    assert classify_screen_archetype(calc_html, rel_path="tools/saas-runway-calculator/index.html") == "interactive_calculator"

    comp_html = '<html><body><main><h1>Comparison</h1><section class="comparison-table-section"><div class="table-wrap"><table></table></div></section></main></body></html>'
    assert classify_screen_archetype(comp_html, rel_path="tools/kalshi-vs-polymarket-tax-calculator/index.html") == "comparison_page"

    guide_html = "<html><body><main><h1>Statutory Decision Guide</h1><section class='card'><h2>Overview</h2></section></main></body></html>"
    assert classify_screen_archetype(guide_html, rel_path="tools/crypto-tax-form-1099-da-mandatory-reporting/index.html") == "statutory_guide"

    for arch_key in SCREEN_ARCHETYPE_CONTRACTS:
        contract = get_screen_archetype_contract(guide_html, rel_path="tools/guide/index.html")
        assert contract["viewports"]["desktop"]["width"] == 1440
        assert contract["viewports"]["mobile"]["width"] == 375
        assert contract["ergonomics"]["min_touch_target_px"] == 44.0
        assert contract["ergonomics"]["max_consecutive_cta_callouts"] == 2
        assert contract["typography"]["desktop"]["h1_px"] == 32.0
        assert contract["typography"]["mobile"]["h1_px"] == 24.0


def test_stacked_cta_callout_density_detection_and_self_healing():
    """Verifies stacked callout/CTA density (> 2 consecutive or adjacent trap + handoff) is detected and self-healed."""
    stacked_html = """<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head><title>Stacked Callouts Test</title></head>
<body>
<main class="container">
<h1>Stacked Callouts Test</h1>
<aside id="statutory-trap-alert" class="pseo-card" data-mechanic="instant_edge_case_trap_immediacy"><h2>Trap Alert</h2></aside>
<section id="vetted-commercial-handoff" class="pseo-card" data-mechanic="vetted_commercial_handoff_framing"><h2>Handoff</h2></section>
<section class="monetization-partner-section pseo-card"><h2>Partner</h2></section>
<section id="statutory-compliance-checklist" class="pseo-card" data-mechanic="statutory_compliance_framing"><h2>Compliance Checklist</h2></section>
</main>
</body>
</html>"""
    issues_before = detect_visual_and_ux_contract_issues(stacked_html, rel_path="tools/test/index.html", require_primitives=True)
    assert any("stacked callout/cta density" in i.lower() for i in issues_before)

    healed_html, actions = normalize_html_visual_primitives(stacked_html)
    assert "cta_density_normalization" in actions
    audit_after = audit_visual_ui_quality_contract(healed_html, rel_path="tools/test/index.html", require_primitives=True)
    assert audit_after["passed"] is True, f"Expected healed HTML to pass visual contract: {audit_after}"
    assert healed_html.find('id="statutory-compliance-checklist"') < healed_html.find('id="vetted-commercial-handoff"')


def test_ui_visual_quality_contract_verification():
    """Verifies UI_VISUAL_QUALITY_CONTRACT and verify_ui_visual_quality_contract enforce hierarchy and tabular-nums."""
    assert UI_VISUAL_QUALITY_CONTRACT["typography"]["h1_min_px"] == 24
    assert UI_VISUAL_QUALITY_CONTRACT["typography"]["h2_min_px"] == 18
    valid_ui = """<!DOCTYPE html><html><head><style>
    h1 { font-size: 28px; }
    h2 { font-size: 20px; }
    .metric { font-variant-numeric: tabular-nums; }
    </style></head><body><h1>Dashboard</h1><div class="table-wrap"><table></table></div></body></html>"""
    res = verify_ui_visual_quality_contract(valid_ui, context="test_ui")
    assert res["passed"] is True
