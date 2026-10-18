"""
Regression tests for hierarchical URL-matrix spoke isolation, Tax Bracket / TCJA vertical
content isolation, Prexvo modifier-qualified virtual cross-link anchors, GSC overlay
telemetry sanitization, and visual primitives inline-style self-healing.
Zero em-dashes. Zero en-dashes.
"""

import json
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

    veh_html = """<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>
    <title>BMW X5 Section 179 Calculator</title>
    <link rel="canonical" href="https://profithelm.com/tools/section-179-calculator/bmw-x5-xdrive40i/" />
    </head><body><main>
    <h1>BMW X5 Section 179 Calculator</h1>
    <input type="number" id="cost" value="80000" />
    </main></body></html>"""
    retro_veh, _ = RetroReflectionEngine.retrofit_html(
        veh_html,
        property_id="profithelm",
        slug="section-179-calculator/bmw-x5-xdrive40i",
        canonical_url="https://profithelm.com/tools/section-179-calculator/bmw-x5-xdrive40i/",
    )
    assert RetroReflectionEngine.audit_html_mechanics(retro_veh) == []


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


def test_retrofit_estate_injects_and_audits_agy_overlays_including_hierarchical_spokes(tmp_path: Path):
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    agy_ov_dir = repo_root / ".agy" / "overlays"
    agy_ov_dir.mkdir(parents=True, exist_ok=True)

    crypto_dir = dist_dir / "tools" / "crypto-tax-calculator"
    ca_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "california"
    crypto_dir.mkdir(parents=True, exist_ok=True)
    ca_dir.mkdir(parents=True, exist_ok=True)

    base_crypto_html = """<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>
    <title>Crypto Tax Calculator 2027</title>
    <meta name="description" content="Calculate digital asset capital gains and losses under IRS Form 8949 and Rev. Proc. 2024-28 wallet-by-wallet cost basis rules." />
    <link rel="canonical" href="https://profithelm.com/tools/crypto-tax-calculator/" />
    </head><body><main>
    <h1>Crypto Tax Calculator 2027</h1>
    <aside class="quick-answer"><p>Initial answer.</p></aside>
    <input type="number" id="gains" value="50000" aria-label="Gains" />
    </main></body></html>"""

    base_ca_html = """<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>
    <title>California 2027 Tax Brackets Calculator</title>
    <meta name="description" content="Calculate California 2027 marginal income tax brackets and post-TCJA federal sunset tax rates across filing statuses." />
    <link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/california/" />
    </head><body><main>
    <h1>California 2027 Tax Brackets Calculator</h1>
    <aside class="quick-answer"><p>Initial answer.</p></aside>
    <input type="number" id="income" value="150000" aria-label="Income" />
    </main></body></html>"""

    (crypto_dir / "index.html").write_text(base_crypto_html, encoding="utf-8")
    (ca_dir / "index.html").write_text(base_ca_html, encoding="utf-8")

    crypto_ov = compile_remediation_overlay_spec(
        {
            "slug": "crypto-tax-calculator",
            "target_url": "https://profithelm.com/tools/crypto-tax-calculator/",
            "query": "crypto tax calculator 2027",
            "position": 9.5,
            "impressions": 120,
        },
        tenant_id="profithelm",
    )
    ca_ov = compile_remediation_overlay_spec(
        {
            "slug": "irs-2027-tax-brackets/california",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "query": "california 2027 tax brackets",
            "position": 6.3,
            "impressions": 85,
        },
        tenant_id="profithelm",
    )
    (agy_ov_dir / "crypto-tax-calculator.json").write_text(json.dumps(crypto_ov, indent=2), encoding="utf-8")
    (agy_ov_dir / "irs-2027-tax-brackets-california.json").write_text(json.dumps(ca_ov, indent=2), encoding="utf-8")

    RetroReflectionEngine.retrofit_estate(dist_dir, "profithelm", canonical_base="https://profithelm.com")

    crypto_after = (crypto_dir / "index.html").read_text(encoding="utf-8")
    ca_after = (ca_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="gsc-striking-overlay"' in crypto_after
    assert 'id="gsc-striking-overlay"' in ca_after

    audit_after = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert audit_after["status"] == "PASS", f"Expected PASS after retrofit_estate, got: {audit_after}"

    stripped_crypto = crypto_after.split('<div id="gsc-striking-overlay"')[0] + "</main></body></html>"
    (crypto_dir / "index.html").write_text(stripped_crypto, encoding="utf-8")
    audit_stripped = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert audit_stripped["status"] == "STALE"
    assert "gsc_striking_overlay" in audit_stripped["stale_pages"].get("tools/crypto-tax-calculator/index.html", [])


def test_vehicle_spoke_ring_and_non_state_cluster_completeness():
    veh_blocks = render_competitor_winning_pattern_blocks(
        slug="section-179-calculator/land-rover-defender-110",
        title="Land Rover Defender 110 Section 179 Calculator",
        property_id="profithelm",
        canonical_base="https://profithelm.com",
        statutory_authority="IRC Section 179 & 168(k)",
        economic_dataset="IRS Publication 946",
    )
    cluster_html = veh_blocks["three_tier_cluster_html"]
    assert "/tools/section-179-calculator/lincoln-navigator-l/" in cluster_html
    assert "/tools/section-179-calculator/mercedes-benz-sprinter-2500/" in cluster_html
    assert "/tools/section-179-calculator/gmc-yukon-xl/" in cluster_html

    neighbor_blocks = render_competitor_winning_pattern_blocks(
        slug="section-179-calculator/lincoln-navigator-l",
        title="Lincoln Navigator L Section 179 Calculator",
        property_id="profithelm",
        canonical_base="https://profithelm.com",
        statutory_authority="IRC Section 179 & 168(k)",
        economic_dataset="IRS Publication 946",
    )
    assert "/tools/section-179-calculator/land-rover-defender-110/" in neighbor_blocks["three_tier_cluster_html"]

    expected_profithelm_roots = [
        "irs-2027-tax-brackets",
        "section-179-calculator",
        "section-1031-calculator",
        "s-corp-reasonable-salary-tax-calculator",
        "tcja-sunset-capital-gains",
        "crypto-tax-calculator",
        "treasury-yield-calculator",
        "equipment-lease-vs-buy-section-179-calculator",
        "equipment-lease-tax-deduction",
        "invoice-factoring-vs-business-line-of-credit-calculator",
        "saas-runway-calculator",
        "saas-runway-calculator",
        "prediction-market-odds",
        "prediction-market-tax",
        "r-and-d-tax-credit-section-174-amortization-calculator",
        "commercial-heavy-vehicle-section-179-weight-calculator",
        "section-179-vehicle-equipment-deduction",
        "medical-and-dental-equipment-section-179-roi-calculator",
        "crypto-tax-form-1099-da-mandatory-reporting",
        "workers-comp-and-payroll-burden-calculator",
        "contractor-surety-bond-cost-calculator",
        "section-301-tariff-landed-cost-calculator",
    ]
    for root_slug in expected_profithelm_roots:
        assert f"/tools/{root_slug}/" in cluster_html, f"Missing ProfitHelm root tool {root_slug} in cluster nav"
    assert "/tools/saas-burn-multiple-benchmarks-2026/" not in cluster_html

    px_blocks = render_competitor_winning_pattern_blocks(
        slug="student-loan-repayment-calculator",
        title="Student Loan Repayment Calculator",
        property_id="prexvo",
        canonical_base="https://prexvo.com",
        statutory_authority="Higher Education Act Title IV (20 U.S.C. 1070 et seq.); 34 CFR Part 685",
        economic_dataset="Federal Reserve G.19 Consumer Credit Series",
    )
    px_cluster = px_blocks["three_tier_cluster_html"]
    expected_prexvo_peers = [
        "rap-vs-ibr-calculator",
        "rap-payment-calculator",
        "tiered-standard-calculator",
        "pslf-qualifying-payment-simulator",
        "save-plan-litigation-transition",
        "paye-sunset-calculator",
        "ibr-hardship-cap-calculator",
        "married-filing-separately-student-loan-calculator",
        "icr-repayment-calculator",
        "parent-plus-double-consolidation",
        "grad-plus-borrowing-cap-calculator",
    ]
    for px_slug in expected_prexvo_peers:
        assert f"/tools/{px_slug}/" in px_cluster, f"Missing Prexvo tool {px_slug} in cluster nav"
    assert "/tools/student-loan-refinance-break-even-calculator/" not in px_cluster


def test_audit_html_mechanics_passes_on_sentinel_cluster_pages_without_self_links():
    for slug in (
        "prediction-market-tax",
        "crypto-tax-form-1099-da-mandatory-reporting",
        "r-and-d-tax-credit-section-174-amortization-calculator",
        "section-179-calculator/gmc-yukon-xl",
    ):
        raw_html = f"""<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>
        <title>{slug}</title>
        <link rel="canonical" href="https://profithelm.com/tools/{slug}/" />
        </head><body><main><h1>{slug}</h1><input type="number" id="x" value="100" /></main></body></html>"""
        retro_html, _ = RetroReflectionEngine.retrofit_html(
            raw_html,
            property_id="profithelm",
            slug=slug,
            canonical_url=f"https://profithelm.com/tools/{slug}/",
        )
        assert RetroReflectionEngine.audit_html_mechanics(retro_html) == []

    for px_slug in ("paye-sunset-calculator", "tiered-standard-calculator"):
        raw_px = f"""<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>
        <title>{px_slug}</title>
        <link rel="canonical" href="https://prexvo.com/tools/{px_slug}/" />
        </head><body><main><h1>{px_slug}</h1><input type="number" id="x" value="100" /></main></body></html>"""
        retro_px, _ = RetroReflectionEngine.retrofit_html(
            raw_px,
            property_id="prexvo",
            slug=px_slug,
            canonical_url=f"https://prexvo.com/tools/{px_slug}/",
        )
        assert RetroReflectionEngine.audit_html_mechanics(retro_px) == []

