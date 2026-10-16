"""
Unit tests for deterministic multi-tenant visual primitives and runtime calculator synchronizer.
Verifies token bridging across Porcelain Light and Obsidian Dark themes, typography scale,
card geometry, table overflow containment, 44px touch targets, and retro-reflection idempotency.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from pseofactory.visual_primitives import (
    VISUAL_PRIMITIVES_VERSION,
    render_visual_primitives_style,
    render_runtime_synchronizer_script,
    normalize_html_visual_primitives,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.audit import audit_code_slop_ratchet


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
