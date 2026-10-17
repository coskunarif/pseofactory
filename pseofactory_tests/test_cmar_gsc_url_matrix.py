"""
Regression tests for hierarchical URL-matrix spoke isolation, Tax Bracket / TCJA vertical
content isolation, Prexvo modifier-qualified virtual cross-link anchors, GSC overlay
telemetry sanitization, and visual primitives inline-style self-healing.
Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path
from pseofactory.competitor import render_competitor_winning_pattern_blocks
from pseofactory.gsc_remediation import (
    _slug_from_url_or_query,
    _resolve_contextual_internal_links,
    compile_remediation_overlay_spec,
    inject_overlay_into_html,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.qualification import check_search_intent_cannibalization
from pseofactory.visual_primitives import (
    detect_visual_and_ux_contract_issues,
    normalize_html_visual_primitives,
)


def test_hierarchical_spoke_slug_and_tax_bracket_vertical_isolation(tmp_path: Path):
    spoke_slug = _slug_from_url_or_query(
        target_url="https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    )
    assert spoke_slug == "irs-2027-tax-brackets/california"

    blocks = render_competitor_winning_pattern_blocks(
        slug="irs-2027-tax-brackets/california",
        title="California 2027 Tax Brackets & TCJA Sunset Calculator",
        property_id="profithelm",
        canonical_base="https://profithelm.com",
        statutory_authority="IRC Section 1(j); IRC Section 199A; IRS Rev. Proc. 2025-32",
        economic_dataset="IRS SOI Individual Tax Statistics and BLS Consumer Price Index (CPI-U)",
    )
    assert "heavy SUV" not in blocks["statutory_compliance_html"]
    assert "Section 179" not in blocks["edge_case_trap_html"]
    assert "IRC Section 1(j)" in blocks["edge_case_trap_html"]
    assert "/tools/section-1031-calculator/california/" in blocks["three_tier_cluster_html"]
    assert "/tools/irs-2027-tax-brackets/connecticut/" in blocks["three_tier_cluster_html"]

    blocks_1031 = render_competitor_winning_pattern_blocks(
        slug="section-1031-calculator/california",
        title="California 1031 Exchange Calculator",
        property_id="profithelm",
        canonical_base="https://profithelm.com",
        statutory_authority="IRC Section 1031(a)(3); Treas. Reg. 1.1031(k)-1; IRS Form 8824",
        economic_dataset="Federal Reserve Z.1 Commercial Real Estate Series and FHFA House Price Index",
    )
    assert "/tools/irs-2027-tax-brackets/california/" in blocks_1031["three_tier_cluster_html"]

    dist = tmp_path / "dist"
    ca_dir = dist / "tools" / "irs-2027-tax-brackets" / "california"
    ca_dir.mkdir(parents=True)
    polluted_html = """<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>
    <title>California 2027 Tax Brackets Calculator</title>
    <link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/california/">
    </head><body><main>
    <h1>California 2027 Tax Brackets &amp; TCJA Sunset Calculator</h1>
    <div class="quick-answer"><p>Quick answer</p></div>
    <form class="calculator-form">
      <label for="f1">Taxable Income</label>
      <input id="f1" type="number" min="0" max="1000000" step="1000" value="150000">
    </form>
    <section class="multi-dataset-join" data-statutory-source="26 U.S.C. Section 179; IRC Section 168(k); CFTC 17 CFR Part 40" data-economic-source="BLS Producer Price Index (PPI) and Federal Reserve Industrial Production Index (G.17)">
      <h2>Dual Dataset Provenance</h2>
    </section>
    <aside id="statutory-trap-alert" class="statutory-edge-case-trap card pseo-card" data-mechanic="instant_edge_case_trap_immediacy">
      <div>Immediate Placed-in-Service Deadline and Recapture Trap Alert (IRC Section 179 &amp; 168(k))</div>
      <p>Claiming full Section 179 deduction on a heavy SUV (6,000 to 14,000 lbs GVWR) without applying IRC 179(b)(5)</p>
    </aside>
    <section id="statutory-compliance-checklist" class="statutory-compliance-section card pseo-card" data-mechanic="statutory_compliance_framing">
      <h2>Beyond the Calculator</h2>
      <p>Claiming full Section 179 deduction on a heavy SUV (6,000 to 14,000 lbs GVWR) without applying IRC 179(b)(5)</p>
    </section>
    <script type="application/json" id="calculation-manifest" class="calculation-manifest">
    {"manifest_id": "california-manifest", "slug": "california", "model_name": "California 2027 Tax Brackets", "statutory_authority": "26 U.S.C. Section 179; IRC Section 168(k); CFTC 17 CFR Part 40", "economic_dataset": "BLS Producer Price Index (PPI) and Federal Reserve Industrial Production Index (G.17)", "formula": "min(cost, 1250000) * (bracket / 100.0)", "inputs": {"cost": 85000, "bracket": 24}, "published_output": 20400.0, "sample_calculation": "Sample", "entity_type": "FinancialProductOrService"}
    </script>
    </main></body></html>"""
    (ca_dir / "index.html").write_text(polluted_html, encoding="utf-8")

    RetroReflectionEngine.retrofit_estate(dist, property_id="profithelm")
    repaired_html = (ca_dir / "index.html").read_text(encoding="utf-8")
    assert '"slug": "irs-2027-tax-brackets/california"' in repaired_html
    assert "heavy SUV" not in repaired_html
    assert "IRC Section 1(j)" in repaired_html
    assert "/tools/section-1031-calculator/california/" in repaired_html


def test_gsc_overlay_tax_bracket_vertical_and_telemetry_sanitization():
    spec = compile_remediation_overlay_spec(
        {
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "query": "ca tax brackets 2027",
            "position": 6.04,
            "impressions": 24,
            "clicks": 2,
            "ctr": 0.0833,
        },
        tenant_id="profithelm",
    )
    assert spec["slug"] == "irs-2027-tax-brackets/california"
    for row in spec["comparison_rows"]:
        assert "Section 179" not in row["authority"]
    assert any("IRC Section 1(j)" in row["authority"] for row in spec["comparison_rows"])

    base_html = """<!DOCTYPE html><html lang="en"><head><title>Student Loan Calculator</title></head>
    <body><main><h1>Student Loan Repayment Calculator</h1></main></body></html>"""
    polluted_overlay = {
        "slug": "student-loan-repayment-calculator",
        "preset_scenarios": [
            {
                "label": "Student Loan Baseline Scenario",
                "query": "student loan repayment calculator",
                "target_position": 15.2,
                "impressions": 38,
            }
        ],
    }
    injected = inject_overlay_into_html(base_html, polluted_overlay)
    assert "target_position" not in injected
    assert '"impressions"' not in injected


def test_prexvo_compound_modifier_qualified_anchors_and_cannibalization():
    links = _resolve_contextual_internal_links(
        "prexvo",
        "rap-vs-ibr-calculator",
        "income based student loan repayment calculator",
    )
    by_href = {item["href"]: item["anchor"] for item in links}
    assert "/tools/student-loan-repayment-calculator/" in by_href
    assert "Income-Based" in by_href["/tools/student-loan-repayment-calculator/"]
    assert "Income-Driven" in by_href["/tools/student-loan-repayment-calculator/"]

    blocks = render_competitor_winning_pattern_blocks(
        slug="rap-vs-ibr-calculator",
        title="RAP vs IBR Calculator",
        property_id="prexvo",
        canonical_base="https://prexvo.com",
        statutory_authority="Higher Education Act Title IV (20 U.S.C. 1070 et seq.); 34 CFR Part 685",
        economic_dataset="Federal Reserve G.19 Consumer Credit Series and BLS Consumer Price Index (CPI-U)",
    )
    assert "Income-Based" in blocks["three_tier_cluster_html"]
    assert "/tools/icr-repayment-calculator/" in blocks["three_tier_cluster_html"]

    tools = [
        {"slug": "student-loan-repayment-calculator", "primary_keyword": "student loan repayment calculator"},
        {"slug": "tiered-standard-calculator", "primary_keyword": "tiered standard repayment plan calculator"},
    ]
    res = check_search_intent_cannibalization(
        "student loan tiered standard calculator 2026",
        existing_tools=tools,
    )
    assert res["parent_slug"] == "tiered-standard-calculator"


def test_visual_primitives_preserves_and_heals_inline_flex_and_padding():
    html_with_styles = """<!DOCTYPE html><html lang="en" data-theme="porcelain"><head><title>T</title></head><body><main>
    <h1>Heading</h1>
    <a href="#trap" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px;">Jump</a>
    <input type="email" name="email" aria-label="email" style="flex: 1; min-height: 44px; padding: 0.625rem 0.875rem;">
    <a href="#corrupted" class="touch-target" style="-flex; align-items: center; min-height: 44px; min-width: 44px; 0px 14px; border-radius: 8px;">Corrupted</a>
    <a href="#btn" class="btn-cta" style="min-height: 44px; .5rem 1rem; -flex;">CTA</a>
    </main></body></html>"""
    healed, _ = normalize_html_visual_primitives(html_with_styles)
    assert 'style="-flex;' not in healed
    assert "; -flex" not in healed
    assert "; 0px 14px" not in healed
    assert "; .625rem 0.875rem" not in healed
    assert "; .5rem 1rem" not in healed
    assert "display: inline-flex" in healed
    assert "padding: 10px 14px" in healed
    assert "padding: 0.625rem 0.875rem" in healed
    assert "padding: 0.5rem 1rem" in healed
    assert detect_visual_and_ux_contract_issues(healed, require_primitives=True) == []
