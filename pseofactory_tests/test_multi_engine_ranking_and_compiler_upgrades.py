"""
Binary pass/fail verification suite for:
1. Multi-engine ranking diagnostics and higher-ranked competitor benchmarking across
   Google, Bing, and DuckDuckGo for both profithelm and prexvo.
2. Strict domain isolation of B2B/tax affiliate links on profithelm vs student-loan
   partners on prexvo.
3. YMYL public-service guardrails on prexvo suppressing commercial offers on PSLF,
   SAVE litigation/forbearance, Teacher Loan Forgiveness, TPD discharge, and borrower defense pages.
4. Upgraded pseofactory compiler mechanics (5-point SSR sensitivity grid, crawlable
   URL-parameterized scenario presets, JSON-LD entity triad, and compliant monetization).

Zero em-dashes. Zero en-dashes.
"""

import json
import pytest

from pseofactory.affiliates import (
    B2B_PARTNER_KEYS,
    STUDENT_LOAN_PARTNER_KEYS,
    PREXVO_RESTRICTED_PUBLIC_SERVICE_SLUGS,
    get_affiliate_route,
    is_restricted_public_service_slug,
    qualify_monetization_opportunity,
    resolve_optimal_partner_for_slug,
    verify_partner_domain_alignment,
)
from pseofactory.audit import (
    audit_code_slop_ratchet,
    audit_rendered_asset,
)
from pseofactory.compiler import compile_high_effort_page
from pseofactory.competitor import (
    SUPPORTED_SEARCH_ENGINES,
    TARGET_QUERY_BENCHMARKS,
    WINNING_COMPETITOR_MECHANICS,
    CompetitorGapEngine,
    benchmark_all_properties,
    benchmark_multi_engine_rankings,
)
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.tenant_facts import TenantFactStore


def test_multi_engine_benchmarks_cover_profithelm_and_prexvo():
    """Verifies search positions and higher-ranked competitors across Google, Bing, and DuckDuckGo."""
    all_reports = benchmark_all_properties()
    assert set(all_reports.keys()) == {"profithelm", "prexvo"}

    store = TenantFactStore.get_instance()
    for prop in ("profithelm", "prexvo"):
        report = all_reports[prop]
        assert report["property_id"] == prop
        assert tuple(report["supported_engines"]) == SUPPORTED_SEARCH_ENGINES
        assert report["total_queries_benchmarked"] >= 5
        assert report["isolation_verified"] is True
        assert len(report["top_competing_domains"]) >= 2
        assert len(report["codified_winning_mechanics"]) == len(WINNING_COMPETITOR_MECHANICS)

        for eng in SUPPORTED_SEARCH_ENGINES:
            eng_stats = report["engine_summary"][eng]
            assert eng_stats["total_queries"] == report["total_queries_benchmarked"]
            assert eng_stats["indexed_count"] + eng_stats["unindexed_count"] == report["total_queries_benchmarked"]

        for q_bench in report["query_benchmarks"]:
            assert q_bench["property_id"] == prop
            assert set(q_bench["engine_positions"].keys()) == set(SUPPORTED_SEARCH_ENGINES)
            assert len(q_bench["higher_ranked_competitors"]) >= 2
            assert q_bench["root_cause_diagnosis"]
            assert set(q_bench["compiler_upgrades_applied"]).issuperset({
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            })
            for comp in q_bench["higher_ranked_competitors"]:
                assert comp["domain"]
                assert comp["engine_ranks"]["google"] >= 1
                assert comp["winning_mechanics"]

        serialized = json.dumps(report)
        store.assert_tenant_isolation(prop, serialized)
        assert_no_forbidden_dashes(serialized, context=f"benchmark_report_{prop}")


def test_multi_engine_benchmark_rejects_cross_tenant_contamination():
    """Verifies cross-tenant queries are rejected during multi-engine benchmarking."""
    with pytest.raises(ValueError, match="Strict isolation violation"):
        benchmark_multi_engine_rankings(
            "profithelm",
            queries=["pslf qualifying payment simulator"],
        )

    with pytest.raises(ValueError, match="Strict isolation violation"):
        benchmark_multi_engine_rankings(
            "prexvo",
            queries=["section 179 equipment deduction calculator"],
        )


def test_prexvo_restricted_public_service_ymyl_guardrails():
    """Verifies commercial offers are strictly blocked on Prexvo public-service pages."""
    restricted_samples = [
        "pslf-qualifying-payment-simulator",
        "save-plan-litigation-transition",
        "teacher-loan-forgiveness-calculator",
        "borrower-defense-to-repayment-discharge-estimator",
        "total-and-permanent-disability-discharge-calculator",
        "closed-school-discharge-calculator",
        "federal-poverty-guideline-discretionary-income-calculator",
    ]
    for slug in restricted_samples:
        assert is_restricted_public_service_slug(slug) is True
        assert resolve_optimal_partner_for_slug("prexvo", slug) is None

        with pytest.raises(ValueError, match="Prexvo YMYL guardrail violation"):
            get_affiliate_route("prexvo", slug)

        qual = qualify_monetization_opportunity(
            query=slug.replace("-", " "),
            slug=slug,
            property_id="prexvo",
        )
        assert qual["restricted_public_service"] is True
        assert qual["commercial_offers_allowed"] is False
        assert qual["recommended_partners"] == []
        assert qual["primary_partner"] == ""
        assert qual["expected_bounty_usd"] == 0.0

        alignment = verify_partner_domain_alignment("prexvo", slug, ["sofi"])
        assert alignment["aligned"] is False
        assert any("Prexvo YMYL public-service guardrail violation" in v for v in alignment["violations"])

        clean_alignment = verify_partner_domain_alignment("prexvo", slug, [])
        assert clean_alignment["aligned"] is True


def test_competitor_gap_engine_suppresses_affiliates_on_restricted_prexvo_pages():
    """Verifies CompetitorGapEngine suppresses commercial affiliates on PSLF and SAVE pages."""
    store = TenantFactStore.get_instance()
    engine = CompetitorGapEngine(store.get_profile("prexvo"))

    candidates = engine.diff_competitor_serp(
        query="pslf qualifying payment buyback simulator",
        competitor_results=[{"interactive_features": ["buyback_slider"]}],
    )
    assert len(candidates) >= 1
    for cand in candidates:
        assert cand.affiliates == []
        enriched = engine.enrich_candidate_spec(cand)
        assert enriched["affiliates"] == []
        assert enriched["commercial_offers_allowed"] is False
        assert enriched["restricted_public_service"] is True


def test_upgraded_compiler_profithelm_b2b_and_tax_pages():
    """Verifies upgraded compiler emits 5-point sensitivity grid, presets, and compliant B2B/tax affiliates on ProfitHelm."""
    specs = [
        {
            "query": "section 179 equipment expense tax deduction calculator",
            "slug": "section-179-equipment-expense-tax-deduction-calculator",
            "tenant": "profithelm",
            "statutory_authority": "IRC Section 179(b)(1)",
            "economic_dataset": "FRED CPILFESL Series",
            "model_name": "Section 179 Grounded Model",
            "formula": "min(cost, cap)",
            "inputs": {"cost": 400000, "cap": 1220000},
            "published_output": 400000.0,
            "sample_calculation": "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
            "canonical_base": "https://profithelm.com",
            "expected_partner": "crest_capital",
        },
        {
            "query": "1031 exchange boot calculation model",
            "slug": "1031-exchange-boot-calculator",
            "tenant": "profithelm",
            "statutory_authority": "IRC Section 1031(a)(1)",
            "economic_dataset": "FRED CPILFESL Series",
            "model_name": "Section 1031 Like-Kind Exchange Model",
            "formula": "relinquished_basis + recognized_gain",
            "inputs": {"relinquished_basis": 450000, "recognized_gain": 25000},
            "published_output": 475000.0,
            "sample_calculation": "Relinquished basis 450,000 plus recognized gain 25,000 yields 475,000",
            "canonical_base": "https://profithelm.com",
            "expected_partner": "ipx1031",
        },
        {
            "query": "crypto staking tax form 8949 calculator",
            "slug": "crypto-staking-tax-calculator",
            "tenant": "profithelm",
            "statutory_authority": "IRC Section 1001 & IRS Form 8949",
            "economic_dataset": "FRED CPILFESL Series",
            "model_name": "Digital Asset Realized Gain Model",
            "formula": "proceeds - cost_basis",
            "inputs": {"proceeds": 85000, "cost_basis": 35000},
            "published_output": 50000.0,
            "sample_calculation": "Proceeds 85,000 minus cost basis 35,000 yields 50,000 net taxable gain",
            "canonical_base": "https://profithelm.com",
            "expected_partner": "coinledger",
        },
    ]

    for spec in specs:
        res = compile_high_effort_page(spec)
        html = res["html"]
        assert res["verified"] is True
        assert res["tenant"] == "profithelm"
        assert res["commercial_offers_allowed"] is True
        assert res["restricted_public_service"] is False
        assert res["affiliate_route"]["partner_key"] == spec["expected_partner"]

        # Verify 5-point sensitivity grid mechanic
        assert 'data-mechanic="server_rendered_sensitivity_grid"' in html
        assert "scenario-baseline" in html
        assert "scenario-conservative" in html
        assert "scenario-moderate-contraction" in html
        assert "scenario-moderate-expansion" in html
        assert "scenario-aggressive" in html

        # Verify deep-link scenario presets mechanic
        assert 'data-mechanic="deep_link_scenario_presets"' in html
        assert "scenario-preset-link" in html

        # Verify compliant affiliate CTA and zero student-loan cross-contamination
        assert f'data-partner="{spec["expected_partner"]}"' in html
        assert 'rel="noopener sponsored nofollow"' in html
        for student_partner in STUDENT_LOAN_PARTNER_KEYS:
            assert f'data-partner="{student_partner}"' not in html

        audit_rep = audit_rendered_asset(html, spec, tenant="profithelm")
        assert audit_rep.passed is True, f"Audit failed for {spec['slug']}: {audit_rep.violations}"


def test_upgraded_compiler_prexvo_public_service_vs_refinance_isolation():
    """Verifies Prexvo public-service pages have zero commercial offers while refinance pages include compliant CTAs."""
    pslf_spec = {
        "query": "pslf qualifying payment simulator",
        "slug": "pslf-qualifying-payment-simulator",
        "tenant": "prexvo",
        "statutory_authority": "34 CFR Part 685",
        "economic_dataset": "FRED SLSTTOTAL Series",
        "model_name": "PSLF Qualifying Payment Progress Model",
        "formula": "max(0, 120 - qualifying_payments) * monthly_payment",
        "inputs": {"qualifying_payments": 72, "monthly_payment": 350},
        "published_output": 16800.0,
        "sample_calculation": "48 remaining payments at 350 per month yields 16,800 remaining outlay before forgiveness",
        "canonical_base": "https://prexvo.com",
    }
    res_pslf = compile_high_effort_page(pslf_spec)
    html_pslf = res_pslf["html"]
    assert res_pslf["tenant"] == "prexvo"
    assert res_pslf["restricted_public_service"] is True
    assert res_pslf["commercial_offers_allowed"] is False
    assert res_pslf["affiliate_route"] is None
    assert 'data-commercial-offers="none"' in html_pslf
    assert 'data-restricted-public-service="true"' in html_pslf
    assert "affiliate-cta-link" not in html_pslf
    for domain in ("splashfinancial.com", "sofi.com", "credible.com", "earnest.com", "lendkey.com"):
        assert domain not in html_pslf

    audit_pslf = audit_rendered_asset(html_pslf, pslf_spec, tenant="prexvo")
    assert audit_pslf.passed is True, f"PSLF audit failed: {audit_pslf.violations}"

    refi_spec = {
        "query": "student loan refinance break even calculator",
        "slug": "student-loan-refinance-break-even",
        "tenant": "prexvo",
        "statutory_authority": "34 CFR Part 685",
        "economic_dataset": "FRED SLSTTOTAL Series",
        "model_name": "Refinance Interest Savings Model",
        "formula": "balance * ((current_rate - refi_rate) / 100.0)",
        "inputs": {"balance": 60000, "current_rate": 7.0, "refi_rate": 5.0},
        "published_output": 1200.0,
        "sample_calculation": "Balance 60,000 with 2 percent rate reduction yields 1,200 annual interest reduction",
        "canonical_base": "https://prexvo.com",
    }
    res_refi = compile_high_effort_page(refi_spec)
    html_refi = res_refi["html"]
    assert res_refi["tenant"] == "prexvo"
    assert res_refi["restricted_public_service"] is False
    assert res_refi["commercial_offers_allowed"] is True
    assert res_refi["affiliate_route"] is not None
    assert res_refi["affiliate_route"]["partner_key"] in STUDENT_LOAN_PARTNER_KEYS
    assert 'data-commercial-offers="compliant-refinance"' in html_refi
    assert "affiliate-cta-link" in html_refi
    assert "waives federal protections" in html_refi.lower()
    for b2b_partner in B2B_PARTNER_KEYS:
        assert f'data-partner="{b2b_partner}"' not in html_refi

    audit_refi = audit_rendered_asset(html_refi, refi_spec, tenant="prexvo")
    assert audit_refi.passed is True, f"Refi audit failed: {audit_refi.violations}"


def test_slop_ratchet_passes_after_compiler_and_competitor_upgrades():
    """Verifies AST slop ratchet passes with zero oversized functions or duplicate blocks."""
    ratchet = audit_code_slop_ratchet()
    assert ratchet["passed"] is True, f"Slop ratchet failed: {ratchet}"


def test_serp_incumbent_depth_upgrade_workbench_and_title_modifiers():
    """Verifies SERP incumbent depth upgrade workbenches across all 6 verticals and CTR title modifiers."""
    from pseofactory.competitor import render_serp_incumbent_depth_upgrade_block
    from pseofactory.gsc_remediation import _normalize_title_50_60

    cases = [
        ("crypto-tax-calculator", "2026 Crypto Tax Calculator", "profithelm", "https://profithelm.com", "IRC Section 1(h)", "IRS Rev. Proc. 2024-28", "crypto", "serp-crypto-proceeds", "Form 8949"),
        ("irs-2027-tax-brackets/california", "California 2027 Tax Brackets", "profithelm", "https://profithelm.com", "IRC Section 1(j)", "IRS Rev. Proc. 2025-32", "tax_brackets", "serp-tax-pretax", "CA State Tier 6: 9.3%"),
        ("section-179-calculator", "2026 Section 179 Calculator", "profithelm", "https://profithelm.com", "IRC Section 179", "IRS Pub. 946", "sec179", "serp-179-class", "$31,300"),
        ("section-1031-calculator", "2026 Section 1031 Exchange Calculator", "profithelm", "https://profithelm.com", "IRC Section 1031", "IRS Form 8824", "sec1031", "serp-1031-rel-debt", "45-Day Written Identification"),
        ("student-loan-repayment-calculator", "2026 Student Loan Repayment Calculator", "prexvo", "https://prexvo.com", "34 CFR Part 685", "FRED SLSTTOTAL", "repayment_loan", "serp-loan-spouse-agi", "Repayment Assistance Plan (RAP)"),
        ("s-corp-tax-calculator", "2026 S-Corp Tax Calculator", "profithelm", "https://profithelm.com", "IRC Section 1366", "SSA OASDI", "b2b", "serp-b2b-deduction", "S-Corp Reasonable Salary"),
    ]
    for slug, title, prop, base, auth, ds, expected_mode, expected_input, expected_fact in cases:
        block = render_serp_incumbent_depth_upgrade_block(
            slug=slug,
            title=title,
            property_id=prop,
            canonical_base=base,
            statutory_authority=auth,
            economic_dataset=ds,
        )
        assert 'id="serp-incumbent-depth-workbench"' in block
        assert f'data-workbench-mode="{expected_mode}"' in block
        assert expected_input in block
        assert expected_fact in block
        assert 'id="serp-svg-bar-retained"' in block
        assert "<title>" not in block
        assert "<desc>Interactive Retained Capital versus Statutory Exposure Breakdown</desc>" in block
        assert 'id="dynamic-commercial-intent-banner"' in block
        assert 'class="comparison-table serp-statutory-reference-table"' in block

    # Verify CTR title normalization strips (Rules), fixes Section179, and injects high-intent form modifiers
    t_179 = _normalize_title_50_60("2026 Cadillac Escalade Section179 Calculator (Rules) | ProfitHelm", "profithelm", "ProfitHelm")
    assert "Section179" not in t_179
    assert "(Rules)" not in t_179
    assert 50 <= len(t_179) <= 60

    t_crypto = _normalize_title_50_60("2026 Crypto Tax Calculator | ProfitHelm", "profithelm", "ProfitHelm")
    assert "Form 8949" in t_crypto
    assert 50 <= len(t_crypto) <= 60


def test_supervisor_lock_inherited_fd_prevents_self_deadlock(tmp_path):
    """Verifies _ancestor_or_inherited_fd_holds_lock detects an open FD on the lock file to prevent release_pipeline FD 209 self-deadlock."""
    import fcntl
    import pseofactory.cli as cli_mod

    fn = getattr(cli_mod, "_ancestor_or_inherited_fd_holds_lock", None)
    assert callable(fn), "Missing _ancestor_or_inherited_fd_holds_lock in pseofactory.cli"

    lock_path = tmp_path / "supervisor_test.lock"
    assert fn(lock_path) is False

    with open(lock_path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert fn(lock_path) is True
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def test_overlay_injection_and_callout_normalization_idempotency():
    """Verifies inject_overlay_into_html and normalize_html_callout_message_match are strictly idempotent after GSC affiliate placement feedback."""
    from pseofactory.affiliates import (
        normalize_html_callout_message_match,
        reposition_affiliate_placements_from_gsc_signals,
    )
    from pseofactory.gsc_remediation import (
        compile_remediation_overlay_spec,
        inject_overlay_into_html,
    )

    spec = compile_remediation_overlay_spec(
        {
            "slug": "parent-plus-double-consolidation",
            "tenant_id": "prexvo",
            "target_url": "https://prexvo.com/tools/parent-plus-double-consolidation/",
            "query": "parent plus double consolidation",
            "impressions": 100,
            "position": 12.0,
        },
        tenant_id="prexvo",
    )
    seed_html = (
        "<!DOCTYPE html><html><head>"
        "<title>Parent PLUS Double Consolidation Calculator | Prexvo</title>"
        '<link rel="canonical" href="https://prexvo.com/tools/parent-plus-double-consolidation/">'
        "</head><body><main>"
        "<h1>Parent PLUS Double Consolidation Calculator</h1>"
        '<aside class="quick-answer"><p>Initial quick answer.</p></aside>'
        '<div class="calc-results-column"><h3 class="calc-column-title">Monthly Repayment Obligations</h3></div>'
        '<section class="refinance-partner-section"><a href="/r/splash_financial">Splash Financial</a></section>'
        "</main></body></html>"
    )
    with_ov = inject_overlay_into_html(seed_html, spec)
    repositioned, _ = reposition_affiliate_placements_from_gsc_signals(
        with_ov,
        property_id="prexvo",
        slug="parent-plus-double-consolidation",
        query="parent plus double consolidation",
    )
    normalized_once = normalize_html_callout_message_match(repositioned, property_id="prexvo")
    after_reinject = inject_overlay_into_html(normalized_once, spec)
    normalized_twice = normalize_html_callout_message_match(after_reinject, property_id="prexvo")
    assert after_reinject == normalized_once
    assert normalized_twice == normalized_once


def test_reflect_zero_drift_fastpath_does_not_raise_unbound_local(tmp_path, monkeypatch):
    """Verifies reflect_and_recompile_all_assets succeeds when force=False and zero assets are drifted."""
    from types import SimpleNamespace
    import pseofactory.maintenance as maint_mod

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    mock_adapter = SimpleNamespace(
        property_id="prexvo",
        canonical_base="https://prexvo.com",
        dist_dir=dist_dir,
        repo_path=None,
        tools=[],
    )
    mock_report = SimpleNamespace(
        property_id="prexvo",
        status="PASS",
        total_assets_checked=10,
        compliant_assets=10,
        compliant_assets_count=10,
        drifted_assets=[],
        to_dict=lambda: {"property_id": "prexvo", "status": "PASS", "total_assets_checked": 10, "compliant_assets": 10, "drifted_assets": []},
    )
    mock_registry = SimpleNamespace(
        list_adapters=lambda: {"prexvo": mock_adapter},
    )
    monkeypatch.setattr(
        maint_mod.AssetIntegrityEvaluator,
        "audit_all",
        lambda self, adapter: mock_report,
    )
    res = maint_mod.reflect_and_recompile_all_assets(
        properties=["prexvo"],
        registry=mock_registry,
        force=False,
        latch_state=False,
        run_downstream=False,
        defer_live_indexing=True,
    )
    assert res["status"] == "PASS"
    assert res["total_drifted"] == 0
    assert res["total_recompiled"] == 0




