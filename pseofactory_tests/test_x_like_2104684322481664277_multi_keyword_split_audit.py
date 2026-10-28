"""
Regression and adversarial falsification suite for x-like:2104684322481664277
(@SEOKeval / Keval Shah | Ecom SEO + AEO: "Targeting too many keywords on one page
can absolutely destroy your SEO" - "enclosed mobility scooter" vs "mobility scooter
with canopy", mid-Page-1 plateau, #1 SERP single-keyword specialization, and $40k/mo
revenue extrapolation) plus thread replies (@VijayAabhas, @AshwiniNK21, @HeySukhwinder,
@mrgadgetstudio, @markdmei).

Validates:
1. 8-claim capability matrix (X_LIKE_2104684322481664277_CAPABILITY_MATRIX) and live
   multi-tenant evaluation across ProfitHelm, Prexvo, and GainHelm.
2. Deterministic SERP Intent Bifurcation vs Shared-Intent Cannibalization discriminator
   (evaluate_serp_intent_bifurcation_vs_consolidation) and integration into
   evaluate_query_modifier_expansion_vs_distinct_tool.
3. Title & H1 Multi-Keyword Stuffing Dilution Gate (detect_multi_keyword_title_h1_dilution)
   and Workflow 4 brief integration.
4. Adversarial falsification of naive gross-volume x AOV ($40,000/mo) revenue claims
   (simulate_page_split_revenue_and_cannibalization_delta).
5. Canonical route & 301-retired clone filtering in compile_quantitative_revenue_forecast
   eliminating phantom /tools/root/, /tools/robots.txt/, pre-pivot sinks, and retired
   301-redirected slugs across ProfitHelm, Prexvo, and GainHelm.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import pseofactory.audit as audit_mod
from pseofactory.contracts import assert_no_forbidden_dashes
import pseofactory.qualification as qual_mod
from pseofactory.seo_growth_loops import (
    compile_quantitative_revenue_forecast,
    compile_search_opportunity_briefs,
)


def test_x_like_2104684322481664277_capability_matrix_and_live_estate() -> None:
    assert hasattr(audit_mod, "X_LIKE_2104684322481664277_CAPABILITY_MATRIX")
    assert hasattr(audit_mod, "evaluate_x_like_2104684322481664277_capability_matrix")

    matrix = audit_mod.X_LIKE_2104684322481664277_CAPABILITY_MATRIX
    assert len(matrix) == 8
    valid_dispositions = {
        "INTEGRATED_COMPOUNDING_UPGRADE",
        "INTEGRATED_DETERMINISTIC_GATE",
        "ALREADY_SOLVED_IN_SUBSTRATE",
        "REJECTED_BLOAT_OR_HYPE",
    }
    for entry in matrix:
        assert entry["disposition"] in valid_dispositions
        assert entry.get("claim_id") in range(1, 9)
        assert entry.get("claim_name")
        assert entry.get("source_ref")
        assert entry.get("pseofactory_stage")
        assert len(entry.get("case_for", "")) >= 30
        assert len(entry.get("case_against", "")) >= 30
        assert_no_forbidden_dashes(str(entry), context=f"claim_{entry['claim_id']}")

    report = audit_mod.evaluate_x_like_2104684322481664277_capability_matrix(include_live_audit=True)
    assert report["pointer"] == "x-like:2104684322481664277"
    assert report["tweet_id"] == "2104684322481664277"
    assert report["author_handle"] == "SEOKeval"
    assert report["integrated_compounding_upgrades_count"] == 2
    assert report["integrated_deterministic_gates_count"] == 2
    assert report["already_solved_in_substrate_count"] == 2
    assert report["rejected_bloat_or_hype_count"] == 2
    assert report["passed"] is True
    assert report["status"] == "PASS"

    for tenant in ("profithelm", "prexvo", "gainhelm"):
        t_sum = report["tenant_summaries"][tenant]
        assert t_sum["status"] == "PASS"
        assert t_sum["phantom_or_retired_forecast_routes"] == []
        assert t_sum["title_h1_dilution_violations"] == []


def test_serp_intent_bifurcation_vs_shared_intent_cannibalization_ablation() -> None:
    assert hasattr(qual_mod, "evaluate_serp_intent_bifurcation_vs_consolidation")

    # 1. True SERP Intent Bifurcation (@AshwiniNK21 + @SEOKeval valid split condition):
    # Disjoint Top-3 SERP URLs, #1 results exclusively target their respective keyword,
    # mid-Page-1 plateau (pos 5.0 and 5.8), distinct statutory/calculation signature, and no indexation ceiling.
    serp_enclosed = [
        {"rank": 1, "url": "https://greenpowermobility.com/collections/enclosed-mobility-scooters", "title": "Enclosed Mobility Scooters | Cabin Scooter Models"},
        {"rank": 2, "url": "https://ewheels.com/enclosed-cabin-scooters/", "title": "Best Enclosed Mobility Scooters for Winter"},
        {"rank": 3, "url": "https://mobilityplus.com/enclosed-scooters/", "title": "Enclosed Mobility Scooter Buyers Guide"},
    ]
    serp_canopy = [
        {"rank": 1, "url": "https://spinlife.com/mobility-scooters-with-canopy/category.cfm", "title": "Mobility Scooters With Canopy | Sun & Rain Shade"},
        {"rank": 2, "url": "https://topmobility.com/canopy-mobility-scooters/", "title": "Mobility Scooter With Canopy Attachments & Models"},
        {"rank": 3, "url": "https://vivehealth.com/blogs/resources/mobility-scooter-with-canopy", "title": "Top Mobility Scooters With Canopy"},
    ]
    split_res = qual_mod.evaluate_serp_intent_bifurcation_vs_consolidation(
        query_a="enclosed mobility scooter",
        query_b="mobility scooter with canopy",
        serp_a=serp_enclosed,
        serp_b=serp_canopy,
        page_rank_a=5.2,
        page_rank_b=5.8,
        inventory_overlap_ratio=0.25,
        ceiling_detected=False,
        cluster_expansion_frozen=False,
    )
    assert split_res["decision"] == "SPLIT_DEDICATED_PAGE"
    assert split_res["recommended_action"] == "BUILD_PAGE"
    assert split_res["top3_url_overlap_ratio"] == 0.0
    assert split_res["rank1_exclusive_targeting"] is True
    assert split_res["mid_page1_plateau"] is True
    assert split_res["cannibalization_risk"] == "LOW_DISJOINT_SERP_INTENT"

    # 2. @VijayAabhas Failure Mode: Shared SERP Intent (Top-3 URLs overlap >= 0.34)
    # Google treats both keywords as the same intent -> splitting creates two cannibalizing pages!
    serp_shared = [
        {"rank": 1, "url": "https://greenpowermobility.com/collections/enclosed-mobility-scooters", "title": "Enclosed Mobility Scooters & Canopy Scooters"},
        {"rank": 2, "url": "https://ewheels.com/enclosed-cabin-scooters/", "title": "Enclosed & Canopy Mobility Scooters"},
        {"rank": 3, "url": "https://spinlife.com/canopy-scooters/", "title": "Mobility Scooters With Canopy"},
    ]
    shared_res = qual_mod.evaluate_serp_intent_bifurcation_vs_consolidation(
        query_a="enclosed mobility scooter",
        query_b="mobility scooter with canopy",
        serp_a=serp_enclosed,
        serp_b=serp_shared,
        page_rank_a=5.2,
        page_rank_b=5.8,
        inventory_overlap_ratio=0.25,
    )
    assert shared_res["decision"] == "CONSOLIDATE_SHARED_SERP_INTENT"
    assert shared_res["recommended_action"] == "REFACTOR_PAGE"
    assert shared_res["top3_url_overlap_ratio"] >= 0.34
    assert shared_res["cannibalization_risk"] == "HIGH_SHARED_SERP_INTENT"

    # 3. Thin Duplicate Inventory / Identical Statutory Signature Failure Mode:
    # Even if external SERP URLs are disjoint, if both pages share >= 70% identical SKUs
    # or identical statutory formula signature, splitting creates a doorway/duplicate clone.
    dup_inv_res = qual_mod.evaluate_serp_intent_bifurcation_vs_consolidation(
        query_a="enclosed mobility scooter",
        query_b="mobility scooter with canopy",
        serp_a=serp_enclosed,
        serp_b=serp_canopy,
        page_rank_a=5.2,
        page_rank_b=5.8,
        inventory_overlap_ratio=0.88,
    )
    assert dup_inv_res["decision"] == "CONSOLIDATE_SHARED_SERP_INTENT"
    assert dup_inv_res["recommended_action"] == "REFACTOR_PAGE"
    assert dup_inv_res["cannibalization_risk"] == "HIGH_DUPLICATE_INVENTORY_OR_FORMULA"

    # 4. Active Indexation Ceiling / Frozen Cluster Expansion Gate:
    # When cluster_expansion_frozen=True (as on Prexvo/GainHelm), splitting is deferred.
    frozen_res = qual_mod.evaluate_serp_intent_bifurcation_vs_consolidation(
        query_a="enclosed mobility scooter",
        query_b="mobility scooter with canopy",
        serp_a=serp_enclosed,
        serp_b=serp_canopy,
        page_rank_a=5.2,
        page_rank_b=5.8,
        inventory_overlap_ratio=0.20,
        cluster_expansion_frozen=True,
    )
    assert frozen_res["decision"] == "DEFER_SPLIT_UNDER_INDEXATION_CEILING"
    assert frozen_res["recommended_action"] == "REFACTOR_PAGE"

    # 5. Integration into evaluate_query_modifier_expansion_vs_distinct_tool:
    # When an existing calculator ranks mid-Page-1 (pos 6.2) for a secondary query that has
    # disjoint Top-3 SERP incumbents and a distinct statutory formula, it upgrades to LAUNCH_DISTINCT_TOOL.
    gsc_rows_mid_p1 = [
        {
            "query": "section 174 r and d amortization calculator",
            "page": "https://profithelm.com/tools/section-179-calculator/",
            "position": 6.2,
            "impressions": 140,
        }
    ]
    serp_179 = [
        {"rank": 1, "url": "https://www.section179.org/section_179_calculator/", "title": "Section 179 Tax Deduction Calculator 2026"},
        {"rank": 2, "url": "https://www.crestcapital.com/tax_deduction_calculator", "title": "Section 179 Deduction Calculator"},
        {"rank": 3, "url": "https://www.nerdwallet.com/article/small-business/section-179-deduction", "title": "Section 179 Deduction Rules"},
    ]
    serp_174 = [
        {"rank": 1, "url": "https://www.kbkg.com/feature/section-174-amortization-calculator", "title": "IRC Section 174 R&D Capitalization & Amortization Calculator"},
        {"rank": 2, "url": "https://www.bdo.com/insights/tax/section-174-research-amortization", "title": "Section 174 R&D Amortization 5-Year & 15-Year Schedule"},
        {"rank": 3, "url": "https://www.claconnect.com/en/resources/articles/section-174-amortization", "title": "Section 174 Research Expense Amortization Model"},
    ]
    existing_only_179 = [
        {
            "slug": "section-179-calculator",
            "title": "Section 179 Tax Deduction Calculator",
            "primary_keyword": "section 179 deduction calculator",
            "statutory_authority": "26 U.S.C. Section 179",
            "formula": "min(equipment_cost, 1250000)",
            "inputs": {"equipment_cost": 150000},
        }
    ]
    upgraded_split = qual_mod.evaluate_query_modifier_expansion_vs_distinct_tool(
        query="section 174 r and d amortization calculator",
        existing_tools=existing_only_179,
        gsc_rows=gsc_rows_mid_p1,
        property_id="profithelm",
        serp_comparison={
            "primary_query": "section 179 deduction calculator",
            "serp_a": serp_179,
            "serp_b": serp_174,
            "page_rank_a": 4.8,
            "page_rank_b": 6.2,
            "spec_a": existing_only_179[0],
            "spec_b": {
                "statutory_authority": "26 U.S.C. Section 174",
                "formula": "domestic_rd * 0.10 + foreign_rd * (1.0 / 30.0)",
                "inputs": {"domestic_rd": 500000, "foreign_rd": 100000},
            },
        },
    )
    assert upgraded_split["decision"] == "LAUNCH_DISTINCT_TOOL"
    assert upgraded_split["recommended_action"] == "BUILD_PAGE"
    assert upgraded_split["serp_intent_bifurcation_detected"] is True


def test_multi_keyword_title_h1_dilution_gate() -> None:
    assert hasattr(qual_mod, "detect_multi_keyword_title_h1_dilution")

    # Diluted multi-keyword stuffed title & H1 (Keval mobility scooter anti-pattern)
    diluted = qual_mod.detect_multi_keyword_title_h1_dilution(
        title="Enclosed Mobility Scooters | Mobility Scooters With Canopy | Covered Scooters | Store",
        h1="Enclosed Mobility Scooters and Mobility Scooters With Canopy and Covered Mobility Scooters",
        primary_keyword="enclosed mobility scooter",
    )
    assert diluted["passed"] is False
    assert diluted["is_diluted"] is True
    assert len(diluted["violations"]) >= 1

    # Clean single-intent primary title with compact parenthetical statutory modifier
    clean = qual_mod.detect_multi_keyword_title_h1_dilution(
        title="Section 179 Deduction Calculator 2026 (Form 4562) | ProfitHelm",
        h1="Section 179 & Bonus Depreciation Tax Calculator",
        primary_keyword="section 179 deduction",
    )
    assert clean["passed"] is True
    assert clean["is_diluted"] is False
    assert clean["violations"] == []


def test_adversarial_falsification_of_naive_40k_revenue_extrapolation() -> None:
    assert hasattr(qual_mod, "simulate_page_split_revenue_and_cannibalization_delta")

    # Test @SEOKeval's exact claim: 3,000 searches/mo, $6,000 AOV ($5k-$7k midpoint), $40,000/mo claimed gain
    sim_valid = qual_mod.simulate_page_split_revenue_and_cannibalization_delta(
        combined_monthly_searches=3000,
        aov_usd=6000.0,
        claimed_monthly_revenue_gain_usd=40000.0,
        baseline_position_a=5.0,
        baseline_position_b=5.5,
        top3_url_overlap_ratio=0.0,
        inventory_overlap_ratio=0.25,
    )
    assert sim_valid["naive_claim_falsified"] is True
    assert sim_valid["overstatement_multiple"] >= 3.0
    assert sim_valid["baseline_already_captured_monthly_revenue_usd"] > 0.0
    assert sim_valid["realistic_monthly_incremental_revenue_usd"] < 15000.0

    # Under shared-intent cannibalization (@VijayAabhas warning), splitting yields negative 90d delta
    sim_cannibal = qual_mod.simulate_page_split_revenue_and_cannibalization_delta(
        combined_monthly_searches=3000,
        aov_usd=6000.0,
        claimed_monthly_revenue_gain_usd=40000.0,
        baseline_position_a=5.0,
        baseline_position_b=5.5,
        top3_url_overlap_ratio=0.67,
        inventory_overlap_ratio=0.90,
    )
    assert sim_cannibal["cannibalization_penalty_applied"] is True
    assert sim_cannibal["net_90d_revenue_delta_usd"] < 0.0


def test_quantitative_revenue_forecast_eliminates_phantom_and_retired_routes_across_tenants() -> None:
    from pathlib import Path

    tenant_roots = {
        "profithelm": Path("/home/ubuntuadmin/projects/profithelm-platform"),
        "prexvo": Path("/home/ubuntuadmin/projects/prexvo"),
        "gainhelm": Path("/home/ubuntuadmin/projects/gainhelm"),
    }
    forbidden_slugs = {
        "root",
        "robots.txt",
        "restoration-job-management-software",
        "fieldedge-alternative",
        "prediction-market-tax-calculator",
        "prediction-market-odds-arbitrage-calculator",
        "rap-vs-ibr-repayment-calculator",
        "mfs-vs-mfj-student-loan-tax-calculator",
        "parent-plus-repayment-cutoff-calculator",
        "cmmc-level-2-audit-cost-calculator",
    }

    for prop, root in tenant_roots.items():
        forecast = compile_quantitative_revenue_forecast(
            property_id=prop,
            repo_root=root,
            dist_dir=root / "dist",
            persist=False,
        )
        assert forecast["status"] == "PASS"
        ranked_slugs = {a["slug"] for a in forecast["ranked_assets"]}
        assert ranked_slugs.isdisjoint(forbidden_slugs), (
            f"Tenant {prop} forecast leaked phantom/retired slugs: {ranked_slugs & forbidden_slugs}"
        )
        for asset in forecast["ranked_assets"]:
            html_file = root / "dist" / "tools" / asset["slug"] / "index.html"
            assert html_file.is_file(), f"Ranked asset {asset['slug']} on {prop} does not exist at {html_file}"
        for p_url in forecast["priority_indexing_urls"]:
            assert not p_url.endswith(("/tools/root/", "/tools/robots.txt/")), (
                f"Invalid priority indexing URL on {prop}: {p_url}"
            )

    briefs_rep = compile_search_opportunity_briefs(
        property_id="profithelm",
        apply_overlays=False,
        persist=False,
    )
    assert briefs_rep["status"] == "PASS"
    assert len(briefs_rep["briefs"]) > 0
    first_brief = briefs_rep["briefs"][0]
    assert "multi_keyword_dilution_and_split_guard" in first_brief
    guard = first_brief["multi_keyword_dilution_and_split_guard"]
    assert guard["title_h1_dilution_passed"] is True
