"""Ground-truth calculation and claim audit tests for pseofactory and compiled tenants."""

from __future__ import annotations

import json

from pseofactory.audit import audit_rendered_asset, safe_eval_mathematical_formula
from pseofactory.maintenance import (
    LiveTruthAuditEngine,
    RetroReflectionEngine,
)
from pseofactory.tenant_facts import TenantFactStore

BANNED_TAUTOLOGICAL_SUBSTRINGS = (
    "gross_income - net_take_home_pay",
    "federal_deferred_tax + state_deferred_tax",
    "effective_sunset_rate",
    "4880.0",
    "48212.5",
)


def _wrap_valid_page(
    manifest: dict,
    body_inner: str,
    quick_answer: str | None = None,
) -> tuple[str, dict]:
    spec = {
        "slug": "verified-statutory-calculator",
        "title": "Verified Statutory Calculator and Statutory Analysis",
        "model_name": "Verified Statutory Model",
        "statutory_authority": "26 U.S.C. Section 179; IRC Section 168(k)",
        "economic_dataset": "IRS SOI Tax Stats",
        "formula": manifest["formula"],
        "inputs": manifest["inputs"],
        "published_output": manifest["published_output"],
    }
    full_manifest = {
        **manifest,
        "model_name": spec["model_name"],
        "statutory_authority": spec["statutory_authority"],
        "economic_dataset": spec["economic_dataset"],
    }
    qa = quick_answer or (
        "Under the 2026 OBBBA statutory baseline, the verified output is "
        f"{manifest['published_output']} based on 26 U.S.C. Section 179; IRC Section 168(k) and IRS SOI Tax Stats."
    )
    filler = " ".join(
        [
            "Statutory calculation audit under 26 U.S.C. Section 179; IRC Section 168(k) and IRS SOI Tax Stats."
            for _ in range(45)
        ]
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<title>{spec["title"]}</title>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"SoftwareApplication","name":"{spec["title"]}","applicationCategory":"FinanceApplication","operatingSystem":"All"}}</script>
<script class="calculation-manifest" type="application/json">{json.dumps(full_manifest)}</script>
</head>
<body>
<header><p class="takeaway">{spec["model_name"]} benchmark analysis.</p></header>
<main>
<h1>{spec["title"]}</h1>
<aside class="quick-answer"><p class="answer-target"><strong>Quick Answer:</strong> {qa}</p></aside>
<div id="calculator-workspace-anchor">
<form class="calculator-form"></form>
<div class="result-box"><strong class="output-value">{manifest["published_output"]}</strong></div>
{body_inner}
</div>
<h2>{spec["model_name"]}</h2>
<div class="multi-dataset-join" data-statutory-source="{spec["statutory_authority"]}" data-economic-source="{spec["economic_dataset"]}">
<p>{filler}</p>
</div>
<table class="calculation-table" data-statutory-source="{spec["statutory_authority"]}" data-economic-source="{spec["economic_dataset"]}">
<thead><tr><th>Metric</th><th>Value</th></tr></thead>
<tbody>
<tr><td>Primary Output</td><td>{manifest["published_output"]}</td></tr>
<tr><td>Statutory Cap</td><td>$30,500</td></tr>
</tbody>
</table>
<section class="methodology">
<p>Methodology grounded in {spec["statutory_authority"]} and {spec["economic_dataset"]}.</p>
<ul><li><a href="/tools/section-179-calculator/">Section 179 Calculator</a></li></ul>
</section>
<a href="https://www.irs.gov/publications/p946">IRS Pub 946</a>
</main>
</body>
</html>"""
    return html, spec


def test_audit_rendered_asset_rejects_tautological_manifests() -> None:
    """Gate 5 and LiveTruthAuditEngine must reject tautological subtraction/identity formulas."""
    tautological_manifest = {
        "inputs": {"gross_income": 150000.0, "net_take_home_pay": 120714.0},
        "formula": "round(gross_income - net_take_home_pay, 2)",
        "published_output": 29286.0,
    }
    html, spec = _wrap_valid_page(
        tautological_manifest,
        '<div id="res-total-tax">$29,286</div>',
    )
    report = audit_rendered_asset(html, spec, "profithelm")
    assert not report.passed
    assert any("tautological" in v.lower() for v in report.violations)

    engine = LiveTruthAuditEngine()
    live_violations = engine.audit_html(html, "profithelm", "tools/irs-2027-tax-brackets/california/index.html")
    assert any("tautological" in v.lower() for v in live_violations)


def test_audit_rendered_asset_rejects_ssr_metric_divergence() -> None:
    """Gate 5 and LiveTruthAuditEngine must reject pages where .output-value diverges from SSR metric card."""
    manifest = {
        "inputs": {
            "agi": 65000.0,
            "poverty_guideline": 15650.0,
            "discretionary_rate": 0.20,
            "income_adjusted_12yr_payment": 784.12,
        },
        "formula": "round(min(max(0, agi - poverty_guideline) * discretionary_rate / 12, income_adjusted_12yr_payment), 2)",
        "published_output": 784.12,
    }
    html, spec = _wrap_valid_page(
        manifest,
        '<div class="calc-metric-card"><span class="calc-metric-value" id="metric-icr_payment">$651.25</span></div>',
    )
    report = audit_rendered_asset(html, spec, "prexvo")
    assert not report.passed
    assert any("ssr" in v.lower() or "metric" in v.lower() or "tautological" in v.lower() for v in report.violations)

    engine = LiveTruthAuditEngine()
    live_violations = engine.audit_html(html, "prexvo", "tools/icr-repayment-calculator/index.html")
    assert any("651.25" in v or "784.12" in v or "ssr" in v.lower() or "metric" in v.lower() for v in live_violations)


def test_live_truth_audit_engine_enforces_strict_one_cent_precision() -> None:
    """LiveTruthAuditEngine must reject a 2-cent (0.02) formula/output drift (strictly <= 0.01 tolerance)."""
    manifest = {
        "inputs": {"loan_balance": 60000.0, "base_12yr_payment": 601.1489786, "agi": 65000.0},
        "formula": "round(base_12yr_payment * (agi / 60000.0), 2)",
        "published_output": 651.26,  # Evaluates to 651.24 (0.02 drift)
    }
    html, _ = _wrap_valid_page(
        manifest,
        '<div id="metric-icr_payment">$651.26</div>',
    )
    engine = LiveTruthAuditEngine()
    violations = engine.audit_html(html, "prexvo", "tools/icr-repayment-calculator/index.html")
    assert any("diverges from published_output" in v for v in violations)


def test_live_truth_audit_engine_scans_inline_scripts_for_stale_claims() -> None:
    """LiveTruthAuditEngine must not strip <script> tags when checking statutory claims."""
    manifest = {
        "inputs": {"vehicle_cost": 85000.0, "business_use_rate": 0.80},
        "formula": "round(min(vehicle_cost * business_use_rate, 30500.0) + max(0.0, (vehicle_cost * business_use_rate) - 30500.0) * 0.20, 2)",
        "published_output": 38000.0,
    }
    html, _ = _wrap_valid_page(
        manifest,
        """
        <div id="sec179-res-deduction">$38,000</div>
        <script>
        // Stale 2024 SUV cap and 60% bonus depreciation inside inline calculator script
        const suvCap = 31300;
        const label = "$31,300 SUV cap and 60% bonus depreciation";
        </script>
        """,
    )
    engine = LiveTruthAuditEngine()
    violations = engine.audit_html(html, "profithelm", "tools/section-179-vehicle-deduction/index.html")
    assert any("31,300" in v or "60% bonus" in v for v in violations)


def test_prexvo_fallback_manifests_match_ground_truth_repayment_math() -> None:
    """Every Prexvo fallback manifest must evaluate without tautologies and match statutory repayment outputs."""
    manifests = RetroReflectionEngine.PREXVO_FALLBACK_MANIFESTS
    assert manifests["icr-repayment-calculator"]["published_output"] == 651.25
    assert manifests["ibr-hardship-cap-calculator"]["published_output"] == 346.04
    assert manifests["paye-sunset-calculator"]["published_output"] == 346.04
    assert manifests["tiered-standard-calculator"]["published_output"] == 379.24
    assert manifests["save-plan-litigation-transition"]["published_output"] == 248.23

    mfs = manifests["married-filing-separately-student-loan-calculator"]
    assert "48212.5" not in mfs["formula"]

    for slug, manifest in manifests.items():
        formula = str(manifest["formula"])
        for banned in BANNED_TAUTOLOGICAL_SUBSTRINGS:
            assert banned not in formula, f"Banned tautology {banned!r} in Prexvo manifest {slug}"
        val = safe_eval_mathematical_formula(formula, manifest["inputs"])
        assert abs(val - float(manifest["published_output"])) <= 0.01, f"Prexvo {slug} drift: {val} != {manifest['published_output']}"


def test_profithelm_fallback_manifests_match_ground_truth_statutory_math() -> None:
    """Every ProfitHelm fallback manifest must use non-tautological statutory formulas and match SSR outputs."""
    manifests = RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS
    assert manifests["s-corp-reasonable-salary-tax-calculator"]["published_output"] == 13193.0
    assert manifests["treasury-yield-calculator"]["published_output"] == 6.13
    assert manifests["section-179-vehicle-deduction"]["published_output"] == 38000.0
    assert manifests["commercial-heavy-vehicle-section-179-weight-calculator"]["published_output"] == 14525.0

    for slug, manifest in manifests.items():
        formula = str(manifest["formula"])
        for banned in BANNED_TAUTOLOGICAL_SUBSTRINGS:
            assert banned not in formula, f"Banned tautology {banned!r} in ProfitHelm manifest {slug}"
        val = safe_eval_mathematical_formula(formula, manifest["inputs"])
        assert abs(val - float(manifest["published_output"])) <= 0.01, (
            f"ProfitHelm {slug} drift: {val} != {manifest['published_output']}"
        )


def test_spoke_manifest_and_quick_answer_ground_truth() -> None:
    """State spoke extraction and quick-answer synthesis must avoid tautologies and cite 2027 post-sunset law."""
    sample_tax_spoke = """
    <html>
    <head><link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/california/"></head>
    <body>
    <main>
    <h1>2027 Federal &amp; California Tax Brackets</h1>
    <aside class="quick-answer"><p>Placeholder</p></aside>
    <input id="tax-income" value="150000">
    <div id="res-total-tax">$29,286</div>
    <div id="res-effective-rate">19.5%</div>
    <div id="res-take-home">$120,714</div>
    <h2>Analysis</h2>
    </main>
    </body></html>
    """
    tax_manifest = RetroReflectionEngine._extract_spoke_manifest_from_html(
        sample_tax_spoke,
        "irs-2027-tax-brackets/california",
        "26 U.S.C. Section 1(j)",
        "IRS SOI Tax Stats",
    )
    assert tax_manifest is not None
    assert "gross_income - net_take_home_pay" not in tax_manifest["formula"]
    assert abs(safe_eval_mathematical_formula(tax_manifest["formula"], tax_manifest["inputs"]) - 29286.0) <= 0.01

    retro_html, _ = RetroReflectionEngine.retrofit_html(
        sample_tax_spoke,
        property_id="profithelm",
        slug="irs-2027-tax-brackets/california",
        canonical_url="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
    )
    assert "combined 2026 federal" not in retro_html.lower()

    sample_1031_spoke = """
    <html><body>
    <h1>California Section 1031 Exchange Calculator</h1>
    <div id="sec1031-res-deferred">$310,950</div>
    <div id="sec1031-res-fed-tax">$204,000</div>
    <div id="sec1031-res-state-tax">$106,950</div>
    </body></html>
    """
    m1031 = RetroReflectionEngine._extract_spoke_manifest_from_html(
        sample_1031_spoke,
        "section-1031-calculator/california",
        "26 U.S.C. Section 1031",
        "IRS Form 8824 Telemetry",
    )
    assert m1031 is not None
    assert "federal_deferred_tax + state_deferred_tax" not in m1031["formula"]
    assert abs(safe_eval_mathematical_formula(m1031["formula"], m1031["inputs"]) - 310950.0) <= 0.01


def test_tenant_fact_store_2026_poverty_guideline_consistency() -> None:
    """TenantFactStore must use $15,650 for 2026 individual poverty guideline across all fields."""
    store = TenantFactStore()
    profile = store.get_profile("prexvo")
    assert profile is not None
    prexvo_facts = profile.statutory_truth.limits_and_thresholds
    assert prexvo_facts["poverty_guidelines_2026_hhs_contiguous"] == 15650.0
    assert prexvo_facts["poverty_guidelines"][2026]["individual"] == 15650.0


def test_sidecar_manifest_lockstep_audit_and_healing(tmp_path) -> None:
    """Sidecar manifests in dist/manifests/ must be audited and healed into lockstep with embedded HTML manifests."""
    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / "prediction-market-odds"
    manifests_dir = dist_dir / "manifests"
    tool_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)

    preset = RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS["prediction-market-odds"]
    html_raw, _ = _wrap_valid_page(
        preset,
        '<div id="res-profit">$235</div>',
        quick_answer="Under CFTC 17 CFR Part 40, the verified output is <strong class=\"output-value\">235.0</strong>.",
    )
    retro_html, _ = RetroReflectionEngine.retrofit_html(
        html_raw,
        property_id="profithelm",
        slug="prediction-market-odds",
        canonical_url="https://profithelm.com/tools/prediction-market-odds/",
    )
    html_file = tool_dir / "index.html"
    html_file.write_text(retro_html, encoding="utf-8")

    # Write a stale pre-upgrade sidecar manifest (350.0 instead of 235.0)
    stale_sidecar = {
        "slug": "prediction-market-odds",
        "model_name": "PredictionMarketArbitrageModel",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "CFTC Rule 40.11",
        "economic_dataset": "FRED Series DGS10",
        "inputs": {"contracts_count": 1000, "cost_basis": 650},
        "formula": "contracts_count * 1.0 - cost_basis",
        "published_output": 350.0,
        "sample_calculation": "Stale sample",
    }
    sidecar_file = manifests_dir / "prediction-market-odds.json"
    sidecar_file.write_text(json.dumps(stale_sidecar), encoding="utf-8")

    engine = LiveTruthAuditEngine()
    file_violations = engine.audit_file(html_file, property_id="profithelm")
    assert any("Sidecar manifest" in v for v in file_violations)

    # RetroReflectionEngine must detect and heal the stale sidecar even when HTML mechanics are already complete
    _, repaired = RetroReflectionEngine.retrofit_html(
        retro_html,
        property_id="profithelm",
        slug="prediction-market-odds",
        canonical_url="https://profithelm.com/tools/prediction-market-odds/",
        dist_dir=dist_dir,
    )
    assert "calculation_manifest" in repaired
    healed_sidecar = json.loads(sidecar_file.read_text(encoding="utf-8"))
    assert healed_sidecar["published_output"] == 235.0
    assert healed_sidecar["formula"] == preset["formula"]
    assert engine.audit_file(html_file, property_id="profithelm") == []


def test_proprietary_signals_multivariable_synthesis_and_state_tax_isolation() -> None:
    """Verifies non-linear statutory AST sensitivity, 2024-2030 longitudinal trajectory, and non-CA state isolation."""
    from pseofactory.competitor import render_serp_incumbent_depth_upgrade_block
    from pseofactory.proprietary_signals import (
        compute_5point_nonlinear_sensitivity_rows,
        compute_multi_year_longitudinal_trajectory,
        resolve_proprietary_signal_bundle,
    )

    rap_preset = RetroReflectionEngine.PREXVO_FALLBACK_MANIFESTS["rap-payment-calculator"]
    rows = compute_5point_nonlinear_sensitivity_rows(
        rap_preset["formula"], rap_preset["inputs"], float(rap_preset["published_output"])
    )
    assert len(rows) == 5
    # Under 225% HHS FPL ($35,212.50 fixed shield), 0.8x AGI ($52,000) yields $139.90/mo vs $198.58 linear
    cons_row = next(r for r in rows if r["css_class"] == "scenario-conservative")
    assert cons_row["linear_output"] == "198.58"
    assert cons_row["ast_output"] == "139.90"
    assert cons_row["cliff_delta"] == "-58.68 Non-Linear Cliff"

    bundle = resolve_proprietary_signal_bundle(
        property_id="prexvo",
        slug="student-loan-forgiveness-tax-bomb-insolvency-calculator",
        formula=RetroReflectionEngine.PREXVO_FALLBACK_MANIFESTS[
            "student-loan-forgiveness-tax-bomb-insolvency-calculator"
        ]["formula"],
        inputs=RetroReflectionEngine.PREXVO_FALLBACK_MANIFESTS[
            "student-loan-forgiveness-tax-bomb-insolvency-calculator"
        ]["inputs"],
        published_output=10730.0,
    )
    assert bundle["statutory_economic_matrix"]["series_count"] >= 4
    assert bundle["proprietary_telemetry"]["demand_telemetry"]["jev_score"] > 0

    tx_depth = render_serp_incumbent_depth_upgrade_block(
        slug="irs-2027-tax-brackets/texas",
        title="2027 Texas Tax Brackets Calculator",
        property_id="profithelm",
        statutory_authority="26 U.S.C. Section 1(j); Texas Constitution Article VIII Section 1-e",
    )
    assert "California FTB Form 540" not in tx_depth
    assert "0.00%" in tx_depth
    assert "$42,800" not in tx_depth

    traj_scorp = compute_multi_year_longitudinal_trajectory(
        "profithelm", "s-corp-reasonable-salary-tax-calculator", "S-Corp FICA Optimization"
    )
    assert "$176,100" in traj_scorp["summary_default"]
    assert all("$42,800" not in r[4] for r in traj_scorp["rows"])


def test_closed_loop_empirical_substrate_three_tenant_parity() -> None:
    """
    Verifies x-like:2093323034195378306 closed-loop empirical substrate parity across
    profithelm, prexvo, and gainhelm:
    1. Domain-specific statutory series ranking & epoch timeline serialization (zero 'year' key inflation).
    2. Non-linear statutory AST gradient evaluation across GainHelm (10/10), ProfitHelm, and Prexvo.
    3. Grounded longitudinal trajectories and stateful comparators across GainHelm compliance verticals.
    """
    import pseofactory.proprietary_signals as ps

    ps._TREND_DB_CACHE = None
    scorp_bundle = ps.resolve_proprietary_signal_bundle(
        property_id="profithelm",
        slug="s-corp-reasonable-salary-tax-calculator",
    )
    top_ph_series = scorp_bundle["statutory_economic_matrix"]["series"][0]["series_id"]
    assert top_ph_series in ("irs_sec199a_qbi", "ssa_fica_wage_base")
    assert '"year":' not in json.dumps(scorp_bundle["statutory_economic_matrix"])
    assert '"epoch":' in json.dumps(scorp_bundle["statutory_economic_matrix"])

    cmmc_bundle = ps.resolve_proprietary_signal_bundle(
        property_id="gainhelm",
        slug="cmmc-2-0-compliance-cost-calculator",
    )
    assert cmmc_bundle["statutory_economic_matrix"]["series"][0]["series_id"] == "dod_cmmc_l2_c3pao_mandatory_pct"

    hipaa_bundle = ps.resolve_proprietary_signal_bundle(
        property_id="gainhelm",
        slug="hipaa-violation-penalty-breach-cost-calculator",
    )
    assert hipaa_bundle["statutory_economic_matrix"]["series"][0]["series_id"] == "hhs_ocr_hipaa_tier4_annual_cap_usd"

    # All 10 GainHelm fallback manifests must evaluate to non-linear statutory cliffs (not Linear Parity)
    for gh_slug, gh_spec in RetroReflectionEngine.GAINHELM_FALLBACK_MANIFESTS.items():
        gh_rows = ps.compute_5point_nonlinear_sensitivity_rows(
            gh_spec["formula"], gh_spec["inputs"], float(gh_spec["published_output"])
        )
        cons = next(r for r in gh_rows if r["css_class"] == "scenario-conservative")
        assert "Non-Linear Cliff" in cons["cliff_delta"], f"{gh_slug} unexpectedly linear: {cons}"

    # ProfitHelm & Prexvo fixed-basis / historical-cap calculators must evaluate to non-linear cliffs
    for prop_map, slug_key in [
        (RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS, "section-1031-calculator"),
        (RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS, "r-and-d-tax-credit-section-174-amortization-calculator"),
        (RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS, "section-301-tariff-landed-cost-calculator"),
        (RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS, "crypto-tax-form-1099-da-mandatory-reporting"),
        (RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS, "equipment-lease-vs-buy-section-179-calculator"),
        (RetroReflectionEngine.PREXVO_FALLBACK_MANIFESTS, "grad-plus-borrowing-cap-calculator"),
        (RetroReflectionEngine.PREXVO_FALLBACK_MANIFESTS, "student-loan-forgiveness-tax-bomb-insolvency-calculator"),
    ]:
        spec = prop_map[slug_key]
        rows = ps.compute_5point_nonlinear_sensitivity_rows(
            spec["formula"], spec["inputs"], float(spec["published_output"])
        )
        cons = next(r for r in rows if r["css_class"] == "scenario-conservative")
        assert "Non-Linear Cliff" in cons["cliff_delta"], f"{slug_key} unexpectedly linear: {cons}"

    # GainHelm vertical trajectories and comparators must be distinct across compliance families
    t_soc2 = ps.compute_multi_year_longitudinal_trajectory("gainhelm", "soc-2-audit-cost-calculator", "SOC 2")
    t_cmmc = ps.compute_multi_year_longitudinal_trajectory("gainhelm", "cmmc-2-0-compliance-cost-calculator", "CMMC 2.0")
    t_hipaa = ps.compute_multi_year_longitudinal_trajectory("gainhelm", "hipaa-violation-penalty-breach-cost-calculator", "HIPAA")
    t_pci = ps.compute_multi_year_longitudinal_trajectory("gainhelm", "pci-dss-4-0-compliance-cost-calculator", "PCI DSS")
    assert len({t_soc2["summary_default"], t_cmmc["summary_default"], t_hipaa["summary_default"], t_pci["summary_default"]}) == 4
    assert all("Proprietary Signal Telemetry:" in t["summary_default"] for t in (t_soc2, t_cmmc, t_hipaa, t_pci))

    c_soc2 = ps.compute_stateful_comparator_defaults("gainhelm", "soc-2-audit-cost-calculator")
    c_cmmc = ps.compute_stateful_comparator_defaults("gainhelm", "cmmc-2-0-compliance-cost-calculator")
    c_fedramp = ps.compute_stateful_comparator_defaults("gainhelm", "fedramp-authorization-3pao-cost-calculator")
    c_hipaa = ps.compute_stateful_comparator_defaults("gainhelm", "hipaa-violation-penalty-breach-cost-calculator")
    assert len({c_soc2["base_a"], c_cmmc["base_a"], c_fedramp["base_a"], c_hipaa["base_a"]}) == 4


def test_gainhelm_fallback_manifests_match_ground_truth_compliance_formulas() -> None:
    """Every GainHelm fallback manifest must match compliance_formulas.py ground truth without tautologies."""
    expected_outputs = {
        "soc-2-audit-cost-calculator": 78100.40,
        "cmmc-2-0-compliance-cost-calculator": 132000.00,
        "nist-800-171-sprs-score-calculator": 87.00,
        "iso-27001-certification-cost-calculator": 67000.40,
        "hipaa-violation-penalty-breach-cost-calculator": 2455313.00,
        "pci-dss-4-0-compliance-cost-calculator": 94800.00,
        "fedramp-authorization-3pao-cost-calculator": 500000.00,
        "hitrust-csf-e1-i1-r2-certification-cost-calculator": 115000.00,
        "penetration-testing-scoping-cost-calculator": 23300.00,
        "cyber-liability-insurance-breach-exposure-calculator": 40900.00,
    }
    manifests = RetroReflectionEngine.GAINHELM_FALLBACK_MANIFESTS
    assert set(manifests.keys()) == set(expected_outputs.keys())

    for slug, expected in expected_outputs.items():
        spec = manifests[slug]
        formula = str(spec["formula"])
        for banned in BANNED_TAUTOLOGICAL_SUBSTRINGS:
            assert banned not in formula, f"Banned formula pattern {banned!r} in GainHelm manifest {slug}"
        calc_val = safe_eval_mathematical_formula(formula, spec["inputs"])
        assert abs(calc_val - expected) <= 0.01, f"GainHelm {slug} formula eval {calc_val} != {expected}"
        assert abs(float(spec["published_output"]) - expected) <= 0.01, (
            f"GainHelm {slug} published_output {spec['published_output']} != {expected}"
        )


def test_adversarial_seeded_false_claims_caught_and_rejected_across_all_three_tenants() -> None:
    """
    Adversarial verification gate test across ProfitHelm, Prexvo, and GainHelm:
    Seeds false statutory claims, wrong year labels, cross-tool overlay misattributions,
    and prose-vs-SSR math contradictions, proving they are deterministically caught and rejected.
    """
    from pseofactory.tenant_facts import TruthReconciliationEngine

    store = TenantFactStore.get_instance()
    engine = LiveTruthAuditEngine()

    # 1. ProfitHelm: zero-income-tax state spoke claiming 2027 post-sunset figure is "2026 federal tax"
    ph_zero_tax_ok, ph_zero_tax_violations = store.verify_claim(
        "profithelm",
        "Under IRC Section 1(j), a $150,000 Alaska household with 0% state income tax leaves $10,539 in 2026 federal tax (a 7.03% effective rate).",
        context="tools/irs-2027-tax-brackets/alaska/index.html",
    )
    assert not ph_zero_tax_ok
    assert any("2027 post-sunset" in v for v in ph_zero_tax_violations)

    # 2. ProfitHelm: equipment lease page falsely claiming operating lease payments are Section 179 capital expensing
    ph_lease_ok, ph_lease_violations = store.verify_claim(
        "profithelm",
        "Under IRC Section 179($2,560,000 cap) and Section 168(k) (20% bonus depreciation), this model calculates first-year equipment expensing.",
        context="tools/equipment-lease-tax-deduction/index.html",
    )
    assert not ph_lease_ok
    assert any("IRC Section 162(a)(3)" in v for v in ph_lease_violations)

    # 3. ProfitHelm: SaaS Runway catch-all overlay injected onto a non-runway calculator page
    ph_runway_pollution = TruthReconciliationEngine.audit_html_truth_reconciliation(
        """
        <html><body>
        <h1>Commercial Heavy Vehicle Section 179 Weight Calculator</h1>
        <section class="overlay-section" id="gsc-striking-overlay">
          <p>Benchmarks monthly net burn against institutional venture thresholds requiring 12 to 18 months of net cash runway.</p>
          <td>High-Growth Operator ($1.5M ARR, 14-Month Runway)</td>
        </section>
        </body></html>
        """,
        tenant="profithelm",
        rel_path="tools/commercial-heavy-vehicle-section-179-weight-calculator/index.html",
        slug="commercial-heavy-vehicle-section-179-weight-calculator",
        include_fact_store=True,
    )
    assert any("SaaS Runway" in v for v in ph_runway_pollution)

    # 4. Prexvo: calculator striking-distance overlay injected onto non-tool /disclaimers/ page
    px_non_tool_overlay = TruthReconciliationEngine.audit_html_truth_reconciliation(
        """
        <html><body>
        <h1>Legal Disclaimers &amp; Statutory Notice</h1>
        <section class="overlay-section" id="gsc-striking-overlay" data-overlay-slug="disclaimers">
          <h2>2026 Statutory Verification &amp; Autonomous Citation Assertions: Disclaimers</h2>
        </section>
        </body></html>
        """,
        tenant="prexvo",
        rel_path="disclaimers/index.html",
        slug="disclaimers",
        include_fact_store=True,
    )
    assert any("Non-calculator route" in v or "overlay" in v.lower() for v in px_non_tool_overlay)

    # 5. GainHelm: seeded stale HIPAA cap ($2,134,831), stale ISO auditor days (9.0 / $16,200), and stale BLS wage ($95/hr)
    gh_hipaa_ok, gh_hipaa_violations = store.verify_claim(
        "gainhelm",
        "Under 45 CFR 160.404, HHS OCR Tier 4 penalties reach an annual cap of $2,134,831 per identical provision.",
        context="tools/hipaa-violation-penalty-breach-cost-calculator/index.html",
    )
    assert not gh_hipaa_ok
    assert any("2,067,813" in v for v in gh_hipaa_violations)

    gh_iso_ok, gh_iso_violations = store.verify_claim(
        "gainhelm",
        "For a 75-employee organization requiring 9.0 accredited Stage 1 and Stage 2 auditor days, Certification Body fee ($16,200) yields $67,000.00.",
        context="tools/iso-27001-certification-cost-calculator/index.html",
    )
    assert not gh_iso_ok
    assert any("11.0" in v for v in gh_iso_violations)

    gh_wage_ok, gh_wage_violations = store.verify_claim(
        "gainhelm",
        "Internal security engineering labor is valued at the BLS SOC 15-1212 rate ($95/hr).",
        context="tools/soc-2-audit-cost-calculator/index.html",
    )
    assert not gh_wage_ok
    assert any("121.67/hr" in v for v in gh_wage_violations)

    # 6. GainHelm: seeded .calc-geo-answer-text ($78,100.00) diverging from SSR #metric-soc2_total_cost ($78,100.40)
    soc2_spec = {"slug": "soc-2-audit-cost-calculator", **RetroReflectionEngine.GAINHELM_FALLBACK_MANIFESTS["soc-2-audit-cost-calculator"]}
    bad_soc2_html, _ = _wrap_valid_page(
        soc2_spec,
        """
        <div id="metric-soc2_total_cost">$78,100.40</div>
        <p class="calc-geo-answer-text">Combining $37,000.00 CPA fees, $15,000.00 GRC, $11,500.00 pentest, and $14,600.40 labor, total outlay totals $78,100.00.</p>
        """,
    )
    soc2_violations = engine.audit_html(bad_soc2_html, "gainhelm", "tools/soc-2-audit-cost-calculator/index.html")
    assert any("78,100.00" in v or "calc-geo-answer-text" in v for v in soc2_violations)




