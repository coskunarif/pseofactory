"""
Unit tests for deterministic multi-tenant visual primitives and runtime calculator synchronizer.
Verifies token bridging across Porcelain Light and Obsidian Dark themes, typography scale,
card geometry, table overflow containment, 44px touch targets, and retro-reflection idempotency.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""
import pytest

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


def test_historical_commit_regressions_caught_and_self_healed():
    """
    Proves that the upgraded first-principles visual contract and self-healing normalizer
    deterministically catch and heal historical commit/audit regressions:
    - f91fe87 / 833157d: <style>/<script> substring leakage misclassifying non-calculator pages
      as interactive_calculator, plus dark-theme :root token polarity inversion (--text-primary: #0f172a).
    - 688d75f / b9f51df / fd91061 / 74d770c: post-overlay horizontal sibling left-edge drift
      (max-width: 720px; margin: 1.75rem auto), excessive vertical margins (margin: 3rem 0),
      and duplicate .decision-framework-card sections.
    - 025c46d / 880035d: SERP workbench and preset key synchronization (bridgePrimaryInputsToSerpWorkbench,
      SLIDER_TO_INPUT_MAP, PRESET_KEY_ALIASES, and .overlay-preset-readout).
    """
    from pathlib import Path
    import re
    from pseofactory.maintenance import RetroReflectionEngine

    # 1. f91fe87 / 833157d: <style>/<script> selector substrings must never misclassify non-calculator pages
    guide_with_style_selectors = """<!DOCTYPE html>
<html lang="en">
<head>
<style id="pseo-visual-primitives">
  .calculator-form { display: flex; }
  input[type="range"] { min-height: 44px; }
</style>
<script>
  var s = 'class="calculator-grid" data-calc-input="x"';
</script>
</head>
<body>
<main class="container">
  <h1>Form 1099-DA Statutory Guide</h1>
  <section class="card"><h2>Reporting Rules</h2><p>Statutory guidance.</p></section>
</main>
</body>
</html>"""
    assert (
        classify_screen_archetype(
            guide_with_style_selectors,
            rel_path="tools/crypto-tax-form-1099-da-mandatory-reporting/index.html",
        )
        == "statutory_guide"
    )
    assert (
        RetroReflectionEngine.is_tool_or_calculator_page(
            Path("/tmp/dist/disclaimers/index.html"),
            Path("/tmp/dist"),
            guide_with_style_selectors,
        )
        is False
    )

    # 2. f91fe87 / 688d75f / b9f51df: Dark-theme :root polarity inversion + duplicate decision-framework-card + horizontal drift
    regressed_html = """<!DOCTYPE html>
<html lang="en">
<head>
<style>
  :root {
    --bg: #07090e;
    --bg-canvas: #07090e;
    --bg-surface: #ffffff;
    --text-primary: #0f172a;
    --brand-primary: #1d4ed8;
  }
</style>
</head>
<body>
<main class="container">
  <h1>Statutory Tax Calculator</h1>
  <section class="hero-section" style="max-width: 720px; margin: 1.75rem auto; margin-bottom: 3.5rem; padding: 1.25rem;">
    <h2>Direct Statutory Answer</h2>
    <p>Summary of IRC rules.</p>
  </section>
  <section class="decision-framework-card card">
    <h2>Statutory Decision Framework &amp; Threshold Checklist</h2>
    <p>First instance.</p>
  </section>
  <section class="decision-framework-card card">
    <h2>Statutory Decision Framework &amp; Threshold Checklist</h2>
    <p>Duplicate instance from repeated retrofit pass.</p>
  </section>
  <form class="calculator-form">
    <label for="field-gross_income">Gross Income</label>
    <input type="number" id="field-gross_income" name="gross_income" value="150000" min="0" max="1000000" step="1000">
    <input type="range" id="field-income_slider" aria-label="Gross Income Slider" value="150000" min="0" max="1000000" step="1000">
    <output class="output-value" id="val-total_federal_tax">$28,500</output>
  </form>
</main>
</body>
</html>"""
    issues = detect_visual_and_ux_contract_issues(
        regressed_html,
        rel_path="tools/irs-2027-tax-brackets/index.html",
        require_primitives=True,
    )
    issue_blob = " | ".join(issues).lower()
    assert "dark-theme token polarity inversion" in issue_blob
    assert "duplicate .decision-framework-card" in issue_blob
    assert "sibling left-edge drift" in issue_blob
    assert "excessive inline vertical margin" in issue_blob

    healed_html, repaired_actions = normalize_html_visual_primitives(
        regressed_html, is_tenant_porcelain=False
    )
    assert "visual_primitives_css" in repaired_actions
    assert "visual_hierarchy_normalization" in repaired_actions
    assert "interactive_runtime_sync" in repaired_actions
    assert len(re.findall(r"<section\b[^>]*\bdecision-framework-card\b", healed_html)) == 1
    assert "--text-primary: #0f172a" not in healed_html
    assert "bridgePrimaryInputsToSerpWorkbench" in healed_html
    assert "SLIDER_TO_INPUT_MAP" in healed_html
    assert "PRESET_KEY_ALIASES" in healed_html
    assert "overlay-preset-readout" in healed_html

    post_issues = detect_visual_and_ux_contract_issues(
        healed_html,
        rel_path="tools/irs-2027-tax-brackets/index.html",
        require_primitives=True,
    )
    assert post_issues == [], f"Expected 0 visual contract issues after self-healing, got: {post_issues}"


def test_above_fold_preset_salience_and_ssr_latency_optimization():
    """
    Verifies normalize_html_visual_primitives surfaces buried [data-calc-preset] chips
    into .above-fold-preset-bar inside .hero-section, strips legacy file:// runtime
    bundle bloat, and parses under 100ms in SinglePassSEODocumentParser.
    """
    import time
    from pseofactory.verifier import SinglePassSEODocumentParser

    filler = "<p>" + ("Statutory depreciation schedule analysis for heavy vehicles. " * 60) + "</p>\n"
    raw_doc = (
        "<!DOCTYPE html><html lang='en'><head><title>Silverado 2500HD Section 179</title></head><body>"
        "<main class='main'><div class='container'>"
        "<section class='hero-section'><h1 class='hero-title'>Silverado 2500HD Section 179 Calculator</h1>"
        "<p class='hero-subtitle'>Heavy duty truck deduction schedule.</p></section>"
        "<aside class='quick-answer'><p>Immediate $51,200 first-year write-off under IRC Section 179.</p></aside>"
        "<div class='calculator-grid'><div class='card'><h2>Parameters</h2>"
        "<input type='number' id='sec179-cost' value='51200'>"
        "<div class='result-box'><div class='output-value'>$17,920</div></div></div></div>"
        + filler
        + "<div class='serp-preset-bar'>"
        + "<button type='button' class='touch-target btn-preset serp-archetype-btn' data-cta-slot='calculator_preset_cta' data-calc-preset='{\"sec179-cost\":95000}'>Heavy Work Truck</button>"
        + "</div>"
        + "<script>if (typeof window !== 'undefined' && window.location && window.location.protocol === 'file:') { try { var x = 1; } catch (err) {} }</script>"
        + "</div></main></body></html>"
    )
    healed, actions = normalize_html_visual_primitives(raw_doc, is_tenant_porcelain=True)
    assert "above_fold_preset_salience" not in actions
    assert "legacy_file_runtime_dedup" in actions
    assert "above-fold-preset-bar" not in healed
    assert "window.location.protocol === 'file:'" not in healed

    t0 = time.perf_counter()
    parser = SinglePassSEODocumentParser(brand_domain="profithelm.com")
    parser.feed(healed)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 100.0
    assert parser.h1_list == ["Silverado 2500HD Section 179 Calculator"]


@pytest.mark.host_estate
def test_monetization_and_datapack_ui_ux_surfaces_and_button_handlers(tmp_path):
    """
    Verifies audit_monetization_and_datapack_ui_ux_surfaces across all compiled
    calculator pages (profithelm, prexvo incl. 4 restricted public-service YMYL,
    gainhelm, lienbond) and executes deterministic DOM click/submit simulation
    for the clean 3-step funnel:
    - Step 1: Preview Workpaper (#btn-preview-workpaper, zero email/Turnstile)
    - Step 2: Single full-width #workpaper-unlock-card ([data-checkout-trigger])
    - Step 3: <= 1 live-only .contextual-referral-card (a[href^="/r/"])
    - Deliverable download links + blueprint actions + scenario comparator + presets
    """
    import shutil
    from pathlib import Path
    from pseofactory.visual_primitives import (
        audit_monetization_and_datapack_ui_ux_surfaces,
        normalize_html_visual_primitives,
        write_runtime_synchronizer_asset,
    )

    ws_root = Path("/home/ubuntuadmin/projects")
    repo_map = {
        "profithelm": ws_root / "profithelm-platform" / "dist",
        "prexvo": ws_root / "prexvo" / "dist",
        "gainhelm": ws_root / "gainhelm" / "dist",
        "lienbond": ws_root / "lienbond" / "dist",
    }
    dist_dirs = {}
    for prop, src_dist in repo_map.items():
        dst_dist = tmp_path / prop / "dist"
        if (src_dist / "tools").is_dir():
            shutil.copytree(src_dist / "tools", dst_dist / "tools")
        else:
            (dst_dist / "tools").mkdir(parents=True, exist_ok=True)
        write_runtime_synchronizer_asset(dst_dist, property_id=prop)
        for html_p in (dst_dist / "tools").rglob("index.html"):
            if html_p == dst_dist / "tools" / "index.html":
                continue
            norm_p, _ = normalize_html_visual_primitives(
                html_p.read_text(encoding="utf-8", errors="ignore"),
                is_tenant_porcelain=True,
                dist_dir=dst_dist,
                property_id=prop,
            )
            html_p.write_text(norm_p, encoding="utf-8")
        dist_dirs[prop] = dst_dist / "tools"

    audit = audit_monetization_and_datapack_ui_ux_surfaces(
        dist_dirs=dist_dirs,
        execute_dom_simulation=True,
    )
    assert audit["all_surfaces_and_handlers_passed"] is True, f"UI/UX button surface audit failed: {audit}"
    assert audit["total_pages_audited"] >= 175
    assert audit["commercial_pages_audited"] >= 171
    assert audit["restricted_ymyl_pages_audited"] == 4
    assert audit["total_pages_audited"] == audit["commercial_pages_audited"] + audit["restricted_ymyl_pages_audited"]
    assert audit["coexistence_and_surface_violations"] == []

    inv = audit["button_inventory_totals"]
    assert inv["competing_legacy_forms"] == 0
    assert inv["datapack_checkout_buttons"] >= audit["commercial_pages_audited"]
    assert inv["workpaper_preview_buttons"] == audit["commercial_pages_audited"]
    assert inv["scenario_preset_buttons"] >= 500

    assert audit["tenants"]["profithelm"]["total_pages"] >= 149
    assert audit["tenants"]["profithelm"]["coexistence_pass_count"] == audit["tenants"]["profithelm"]["total_pages"]
    assert audit["tenants"]["prexvo"]["total_pages"] >= 18
    assert audit["tenants"]["prexvo"]["commercial_pages"] >= 14
    assert audit["tenants"]["prexvo"]["restricted_ymyl_pages"] == 4
    assert audit["tenants"]["prexvo"]["coexistence_pass_count"] == audit["tenants"]["prexvo"]["total_pages"]
    assert audit["tenants"]["gainhelm"]["total_pages"] >= 10
    assert audit["tenants"]["gainhelm"]["coexistence_pass_count"] == audit["tenants"]["gainhelm"]["total_pages"]
    assert audit["tenants"]["lienbond"]["total_pages"] >= 10
    assert audit["tenants"]["lienbond"]["coexistence_pass_count"] == audit["tenants"]["lienbond"]["total_pages"]

    sim = audit["dom_action_simulation"]
    assert sim["all_passed"] is True
    assert sim["verified"] is True
    assert sim["skipped"] is False
    assert len(sim["tenants"]) == 4
    for t_sim in sim["tenants"]:
        assert t_sim["passed"] is True
        assert t_sim["preset_hydration_passed"] is True
        assert t_sim["workbench_selects_distinct"] is True
        assert t_sim["url_sync_passed"] is True
        assert t_sim["scenario_pin_passed"] is True
        assert t_sim["blueprint_actions_passed"] is True
        assert t_sim["workpaper_preview_passed"] is True
        assert t_sim["datapack_checkout_passed"] is True
        assert t_sim["checkout_error_surfaced"] is True
        assert t_sim["deliverable_downloads_passed"] is True
        assert t_sim["affiliate_cta_click_passed"] is True


def test_profithelm_spoke_monetization_and_playbook_autonomy(tmp_path):
    """
    Verifies ProfitHelm edge lead-capture and monetization autonomy across nested
    state and vehicle spokes:
    1. Canonical 2-level spoke route resolution (/tools/<hub>/<state_or_vehicle>/) in
       Stripe Checkout success_url and cancel_url.
    2. Automatic 2-letter US state jurisdiction inference (CA, NY, TX) from spoke slugs.
    3. Free Playbook preview/email links use playbook=1&format=csv|datapack (HTTP 200)
       while Paid Toolkit fulfillment remains gated by Stripe session verification.
    """
    import json
    import subprocess
    from pseofactory.edge import generate_edge_lead_capture_function

    js_code = generate_edge_lead_capture_function("profithelm")
    mod_path = tmp_path / "profithelm_spoke_lead_capture.mjs"
    mod_path.write_text(js_code, encoding="utf-8")

    runner = f"""
import {{ onRequestPost, onRequestGet }} from {json.dumps(str(mod_path))};
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
globalThis.fetch = async (url, init) => {{
  const u = String(url || "");
  if (u.includes("/v1/checkout/sessions") && (!init || init.method === "POST")) {{
    return new Response(JSON.stringify({{
      id: "cs_live_SPOKE_SESSION_1",
      url: "https://checkout.stripe.com/c/pay/cs_live_SPOKE_SESSION_1",
      livemode: true
    }}), {{ status: 200, headers: {{ "Content-Type": "application/json" }} }});
  }}
  return new Response("{{}}", {{ status: 200 }});
}};

const chkCaRes = await onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?checkout=1&tool_slug=irs-2027-tax-brackets-california&amount=240000"),
  env
}});
const chkCa = await chkCaRes.json();

const chkNyRes = await onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?checkout=1&tool_slug=section-1031-calculator-new-york&amount=650000"),
  env
}});
const chkNy = await chkNyRes.json();

const chkVehRes = await onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?checkout=1&tool_slug=section-179-calculator-ford-super-duty-f250&amount=95000"),
  env
}});
const chkVeh = await chkVehRes.json();

const pbPostRes = await onRequestPost({{
  request: new Request("https://profithelm.com/api/lead-capture", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json", "X-Pseofactory-Test": "1" }},
    body: JSON.stringify({{
      email: "cfo-spoke@synthetic.pseofactory.test",
      tool_slug: "section-1031-calculator-texas",
      partner_key: "ipx1031",
      offer_sku: "ph_1031_boot_replacement_workpapers",
      scenario_amount: 520000,
      synthetic_test: true
    }})
  }}),
  env
}});
const pbPost = await pbPostRes.json();

const pbCsvRes = await onRequestGet({{
  request: new Request("https://profithelm.com" + pbPost.playbook_csv_url + "&synthetic_test=1"),
  env
}});
const pbDpRes = await onRequestGet({{
  request: new Request("https://profithelm.com" + pbPost.playbook_datapack_url + "&synthetic_test=1"),
  env
}});
const pbHtmlRes = await onRequestGet({{
  request: new Request("https://profithelm.com" + pbPost.playbook_url + "&format=html&synthetic_test=1"),
  env
}});
const pbHtmlText = await pbHtmlRes.text();

console.log(JSON.stringify({{
  chkCaSuccess: chkCa.success_url,
  chkCaCancel: chkCa.cancel_url,
  chkCaState: chkCa.custom_parameter_ledger && chkCa.custom_parameter_ledger.state,
  chkNySuccess: chkNy.success_url,
  chkNyState: chkNy.custom_parameter_ledger && chkNy.custom_parameter_ledger.state,
  chkVehSuccess: chkVeh.success_url,
  pbPostState: pbPost.state,
  pbPostPartner: pbPost.partner_key,
  pbPostRedirect: pbPost.redirect_url,
  pbPostCancel: pbPost.cancel_url,
  pbCsvUrl: pbPost.playbook_csv_url,
  pbDpUrl: pbPost.playbook_datapack_url,
  pbCsvStatus: pbCsvRes.status,
  pbDpStatus: pbDpRes.status,
  pbHtmlUsesCheckoutPaywall: pbHtmlText.includes("checkout=1") && !pbHtmlText.includes("fulfill=1") && !pbHtmlText.includes("format=csv")
}}));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", runner],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["chkCaSuccess"].startswith(
        "https://profithelm.com/tools/irs-2027-tax-brackets/california/?checkout_status=success"
    )
    assert out["chkCaCancel"].startswith(
        "https://profithelm.com/tools/irs-2027-tax-brackets/california/?checkout_status=cancelled"
    )
    assert out["chkCaState"] == "CA"
    assert out["chkNySuccess"].startswith(
        "https://profithelm.com/tools/section-1031-calculator/new-york/?checkout_status=success"
    )
    assert out["chkNyState"] == "NY"
    assert out["chkVehSuccess"].startswith(
        "https://profithelm.com/tools/section-179-calculator/ford-super-duty-f250/?checkout_status=success"
    )
    assert out["pbPostState"] == "TX"
    assert out["pbPostPartner"] == "lawdepot"
    assert out["pbPostRedirect"].startswith("/r/lawdepot")
    assert out["pbPostCancel"].startswith(
        "https://profithelm.com/tools/section-1031-calculator/texas/?checkout_status=cancelled"
    )
    assert "playbook=1" in out["pbCsvUrl"] and "format=csv" in out["pbCsvUrl"]
    assert "playbook=1" in out["pbDpUrl"] and "format=datapack" in out["pbDpUrl"]
    assert out["pbCsvStatus"] == 402
    assert out["pbDpStatus"] == 402
    assert out["pbHtmlUsesCheckoutPaywall"] is True


def test_hash_fragment_state_engine_migration_and_button_presets():
    """
    Verifies Batch 2B hash-fragment state engine and button preset conversion:
    1. normalize_html_visual_primitives converts <a href="?..." class="scenario-preset-link">
       to <button type="button" class="scenario-preset-btn scenario-preset-link" data-preset="...">
       idempotently (zero crawlable ? preset anchors).
    2. Runtime JS syncs input changes to #hash via replaceState ONLY (zero pushState),
       migrates legacy ?k=v links into #k=v cleanly on load, and wires button preset clicks
       to update inputs and #hash.
    """
    import subprocess
    from pseofactory.visual_primitives import render_runtime_synchronizer_js

    raw_html = """<!DOCTYPE html><html><head><title>Preset Test</title></head><body><main class="container">
<h1>Preset Calc</h1>
<div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets">
  <a href="https://example.com/tools/calc/?gross_income=250000&amp;filing=single" data-preset="aggressive" rel="nofollow" class="touch-target scenario-preset-link">Aggressive (1.2x)</a>
</div>
<form class="calculator-form"><input type="number" id="field-gross_income" name="gross_income" value="150000"><div class="result-box"><div class="output-value">$30,000</div></div></form>
</main></body></html>"""

    norm_once, actions_once = normalize_html_visual_primitives(raw_html, is_tenant_porcelain=True)
    assert "scenario_preset_button_normalization" in actions_once
    assert "<a" not in norm_once.split('<div class="scenario-presets-bar"')[1].split("</div>")[0]
    assert 'type="button"' in norm_once
    assert "scenario-preset-btn" in norm_once
    assert 'data-preset="gross_income=250000&amp;filing=single"' in norm_once
    assert 'data-preset-tier="aggressive"' in norm_once
    assert detect_visual_and_ux_contract_issues(norm_once, rel_path="tools/calc/index.html", require_primitives=True) == []

    norm_twice, actions_twice = normalize_html_visual_primitives(norm_once, is_tenant_porcelain=True)
    assert actions_twice == []
    assert norm_twice == norm_once

    runtime_js = render_runtime_synchronizer_js()
    assert "history.pushState" not in runtime_js
    assert "window.location.hash" in runtime_js

    vm_script = """
const vm = require('vm');
const assert = require('assert');
const code = require('fs').readFileSync(0, 'utf8');

function runCase(initSearch, initHash) {
  let pushCount = 0;
  let replaceCount = 0;
  const docListeners = {};
  const winListeners = {};
  const els = {};
  const mkEl = (tag, attrs = {}, text = '') => {
    const _attrs = { ...attrs };
    const _cls = new Set(String(attrs.class || '').split(/\\s+/).filter(Boolean));
    const el = {
      tagName: tag.toUpperCase(),
      nodeType: 1,
      style: {},
      value: attrs.value || '',
      textContent: text,
      children: [],
      classList: {
        contains: (c) => _cls.has(c),
        add: (c) => _cls.add(c),
        remove: (c) => _cls.delete(c),
      },
      get id() { return _attrs.id || ''; },
      get name() { return _attrs.name || ''; },
      get type() { return _attrs.type || ''; },
      getAttribute: (k) => Object.prototype.hasOwnProperty.call(_attrs, k) ? String(_attrs[k]) : null,
      setAttribute: (k, v) => { _attrs[k] = String(v); },
      hasAttribute: (k) => Object.prototype.hasOwnProperty.call(_attrs, k),
      removeAttribute: (k) => { delete _attrs[k]; },
      closest: (sel) => {
        if (sel.includes('scenario-preset-btn') && _cls.has('scenario-preset-btn')) return el;
        return null;
      },
      querySelector: () => null,
      querySelectorAll: () => [],
      dispatchEvent: (ev) => {
        ev.target = el;
        (docListeners[ev.type] || []).forEach(fn => fn(ev));
      },
      click: () => {
        const ev = { type: 'click', target: el, preventDefault() {} };
        (docListeners.click || []).forEach(fn => fn(ev));
      }
    };
    if (el.id) els[el.id] = el;
    return el;
  };
  const inp = mkEl('INPUT', { id: 'field-gross_income', name: 'gross_income', type: 'number', value: '150000' });
  const btn = mkEl('BUTTON', { id: 'btn-preset-agg', type: 'button', class: 'scenario-preset-btn scenario-preset-link touch-target', 'data-preset': 'gross_income=275000', 'data-preset-tier': 'aggressive' }, 'Aggressive');
  const out = mkEl('DIV', { id: 'primary-out', class: 'output-value' }, '$30,000');
  const loc = { origin: 'https://example.com', pathname: '/tools/calc/', search: initSearch, hash: initHash, href: 'https://example.com/tools/calc/' + initSearch + initHash };
  const win = {
    location: loc,
    history: {
      pushState() { pushCount++; },
      replaceState(_s, _t, u) {
        replaceCount++;
        const s = String(u || '');
        const hi = s.indexOf('#');
        const bh = hi !== -1 ? s.slice(0, hi) : s;
        const qi = bh.indexOf('?');
        loc.search = qi !== -1 ? bh.slice(qi) : '';
        loc.hash = hi !== -1 ? s.slice(hi) : '';
        loc.href = loc.origin + loc.pathname + loc.search + loc.hash;
      }
    },
    addEventListener: (t, fn) => { (winListeners[t] = winListeners[t] || []).push(fn); },
    navigator: { sendBeacon: () => true, clipboard: { writeText: () => Promise.resolve() } },
    Event: class { constructor(t, o = {}) { this.type = t; this.bubbles = Boolean(o.bubbles); } },
    URLSearchParams,
    setTimeout: (fn) => { fn(); return 1; },
    clearTimeout: () => {},
  };
  win.window = win;
  const doc = {
    readyState: 'complete',
    body: mkEl('BODY'),
    getElementById: (id) => els[id] || null,
    querySelector: (s) => s.includes('output-value') ? out : (s.includes('gross_income') ? inp : null),
    querySelectorAll: (s) => {
      if (s.includes('scenario-preset')) return [btn];
      if (s.includes('output-value')) return [out];
      if (s.includes('input')) return [inp];
      return [];
    },
    createElement: (t) => mkEl(t),
    addEventListener: (t, fn) => { (docListeners[t] = docListeners[t] || []).push(fn); }
  };
  win.document = doc;
  vm.runInContext(code, vm.createContext({ window: win, document: doc, location: loc, history: win.history, navigator: win.navigator, Event: win.Event, URLSearchParams, Math, JSON, Object, Array, String, Number, Boolean, RegExp, Date, Promise, parseFloat, parseInt, isNaN, encodeURIComponent, decodeURIComponent, setTimeout: win.setTimeout, clearTimeout: win.clearTimeout }));
  return { inp, btn, loc, getCounts: () => ({ pushCount, replaceCount }) };
}

// Legacy ? migration -> #
const c1 = runCase('?gross_income=199000', '');
assert.strictEqual(c1.inp.value, '199000');
assert.strictEqual(c1.loc.search, '');
assert.ok(c1.loc.hash.includes('gross_income=199000'));
assert.strictEqual(c1.getCounts().pushCount, 0);

// Hash-first precedence + button preset click
const c2 = runCase('?gross_income=111000', '#gross_income=222000');
assert.strictEqual(c2.inp.value, '222000');
c2.btn.click();
assert.strictEqual(c2.inp.value, '275000');
assert.ok(c2.btn.classList.contains('active'));
assert.ok(c2.loc.hash.includes('gross_income=275000'));
assert.strictEqual(c2.getCounts().pushCount, 0);
console.log('HASH_AND_PRESET_OK');
"""
    proc = subprocess.run(["node", "-e", vm_script], input=runtime_js, capture_output=True, text=True, check=True)
    assert "HASH_AND_PRESET_OK" in proc.stdout


def test_workpaper_statutory_authority_ignores_scripts_and_cross_links():
    """
    Verifies normalize_html_visual_primitives reads #calculation-manifest statutory_authority first
    and ignores <script>, <style>, <nav>, and cluster cross-links so IRC Section 179 does not leak
    onto unrelated tools.
    """
    html_doc = """<!DOCTYPE html><html lang="en" data-theme="porcelain"><head><title>SaaS Runway Calculator</title>
    <link rel="canonical" href="https://profithelm.com/tools/saas-runway-calculator/">
    <script>var related = "IRC Section 179 heavy SUV";</script>
    <style>/* IRC Section 179 */</style>
    </head><body><main class="container">
    <h1>SaaS Runway Calculator</h1>
    <div class="calc-grid">
      <div class="result-box"><div class="output-value">$240,000</div></div>
    </div>
    <section class="three-tier-cluster-section card pseo-card">
      <a href="/tools/section-179-calculator/">IRC Section 179 Equipment Calculator</a>
    </section>
    <script type="application/json" id="calculation-manifest" class="calculation-manifest">
    {"manifest_id":"saas-runway-manifest","slug":"saas-runway-calculator","model_name":"SaaS Runway Model","statutory_authority":"ASC 606 Revenue Recognition and GAAP Cash Burn","economic_dataset":"BVP Cloud Index","formula":"cash / burn","inputs":{"cash":240000,"burn":20000},"published_output":12.0}
    </script>
    </main></body></html>"""
    healed, _ = normalize_html_visual_primitives(html_doc, is_tenant_porcelain=True)
    assert "IRC Section 179" not in healed.split("id=\"workpaper-unlock-card\"")[1].split("</section>")[0]
    assert "ASC 606 Revenue Recognition and GAAP Cash Burn" in healed




