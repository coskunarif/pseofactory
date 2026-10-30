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


