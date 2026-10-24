"""
Regression and historical replay tests for SEO Topical Authority, Query Grouping,
Keyword Cannibalization Prevention, Mixed Signal Scrubbing, and Daily Feedback Loops.

Zero em-dashes. Zero en-dashes.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from pseofactory.qualification import (
    check_search_intent_cannibalization,
    qualify_search_intent,
    assert_search_intent_qualified,
)
import pseofactory.qualification as qual_mod
from pseofactory.gsc_remediation import (
    _resolve_contextual_internal_links,
    prioritize_gsc_signals,
    persist_overlay_respecting_lock,
    evaluate_expired_overlays,
)


@pytest.fixture
def canonical_profithelm_hubs():
    return [
        {
            "slug": "irs-2027-tax-brackets",
            "title": "IRS 2027 Tax Brackets & Standard Deduction Calculator",
            "primary_keyword": "2027 irs tax brackets",
            "secondary_keywords": [
                "2027 federal income tax brackets",
                "standard deduction 2027",
            ],
            "url": "https://profithelm.com/tools/irs-2027-tax-brackets/",
        },
        {
            "slug": "section-1031-calculator",
            "title": "Section 1031 Like-Kind Exchange Tax Deferral Calculator",
            "primary_keyword": "section 1031 exchange",
            "secondary_keywords": [
                "1031 exchange boot calculator",
                "like kind exchange capital gains deferral",
            ],
            "url": "https://profithelm.com/tools/section-1031-calculator/",
        },
        {
            "slug": "section-179-calculator",
            "title": "Section 179 & Bonus Depreciation Tax Calculator",
            "primary_keyword": "section 179 deduction",
            "secondary_keywords": [
                "bonus depreciation phase out",
                "section 179 vehicle limits",
            ],
            "url": "https://profithelm.com/tools/section-179-calculator/",
        },
        {
            "slug": "tcja-sunset-capital-gains",
            "title": "TCJA Sunset & Capital Gains Tax Calculator",
            "primary_keyword": "tcja sunset capital gains tax",
            "secondary_keywords": [
                "long term capital gains tax brackets",
                "niit 3.8 surtax threshold",
            ],
            "url": "https://profithelm.com/tools/tcja-sunset-capital-gains/",
        },
        {
            "slug": "prediction-market-odds",
            "title": "Prediction Market Odds & Section 1256 Tax Calculator",
            "primary_keyword": "prediction market odds calculator",
            "secondary_keywords": [
                "kalshi vs polymarket implied probability",
                "event contract arbitrage calculator",
            ],
            "url": "https://profithelm.com/tools/prediction-market-odds/",
        },
        {
            "slug": "crypto-tax-calculator",
            "title": "Crypto Capital Gains & Form 1099-DA Tax Calculator",
            "primary_keyword": "crypto tax calculator",
            "secondary_keywords": [
                "fifo vs hifo crypto cost basis",
                "short term vs long term crypto tax",
            ],
            "url": "https://profithelm.com/tools/crypto-tax-calculator/",
        },
    ]


def test_state_abbreviation_synonym_and_modifier_cannibalization_detection(canonical_profithelm_hubs):
    # 1. State abbreviation + filing status + tax year variants route to /tools/irs-2027-tax-brackets/<state>/
    for ca_query in [
        "ca tax brackets",
        "ca tax brackets 2025",
        "ca tax brackets 2026",
        "ca tax brackets 2026 married jointly",
        "ca tax brackets 2026 single",
        "ca tax brackets married",
        "ca tax brackets 2026 head of household",
        "ca tax brackets married filing jointly",
        "california income tax brackets 2026",
        "california tax brackets 2026",
    ]:
        res = check_search_intent_cannibalization(ca_query, canonical_profithelm_hubs)
        assert res["is_cannibalizing"] is True, f"Failed to detect cannibalization for '{ca_query}'"
        assert res["parent_slug"] == "irs-2027-tax-brackets"
        assert res.get("target_subroute") == "/tools/irs-2027-tax-brackets/california/"

    # 2. Punctuated/hyphenated state abbreviation + 'rate' synonym ('s.c. tax brackets', 'sc income tax rate 2027')
    for sc_query in ["s.c. tax brackets", "sc income tax rate 2027", "s-c-income-tax-rate-2027"]:
        res_sc = check_search_intent_cannibalization(sc_query, canonical_profithelm_hubs)
        assert res_sc["is_cannibalizing"] is True, f"Failed to detect cannibalization for '{sc_query}'"
        assert res_sc["parent_slug"] == "irs-2027-tax-brackets"
        assert res_sc.get("target_subroute") == "/tools/irs-2027-tax-brackets/south-carolina/"

    # 3. State 1031 sub-route queries route to /tools/section-1031-calculator/<state>/
    for az_q, expected_sub in [
        ("1031 exchange rules arizona", "/tools/section-1031-calculator/arizona/"),
        ("1031 exchange in massachusetts", "/tools/section-1031-calculator/massachusetts/"),
        ("ohio 1031 exchange", "/tools/section-1031-calculator/ohio/"),
    ]:
        res_1031 = check_search_intent_cannibalization(az_q, canonical_profithelm_hubs)
        assert res_1031["is_cannibalizing"] is True, f"Failed to detect 1031 state sub-route for '{az_q}'"
        assert res_1031["parent_slug"] == "section-1031-calculator"
        assert res_1031.get("target_subroute") == expected_sub

    # 4. Synonym & scenario-comparison-model clones match canonical hubs
    for clone_q, expected_parent in [
        ("irs 2027 tax rates", "irs-2027-tax-brackets"),
        ("2027 tax tables", "irs-2027-tax-brackets"),
        ("irs capital gains statutory tax", "tcja-sunset-capital-gains"),
        ("kalshi prediction market arbitrage strategy", "prediction-market-odds"),
        ("irs 2027 tax brackets scenario comparison model", "irs-2027-tax-brackets"),
        ("section 1031 calculator scenario comparison model", "section-1031-calculator"),
    ]:
        res_clone = check_search_intent_cannibalization(clone_q, canonical_profithelm_hubs)
        assert res_clone["is_cannibalizing"] is True, f"Failed to detect clone '{clone_q}'"
        assert res_clone["parent_slug"] == expected_parent

    # 5. Distinct specialized multi-factor calculators remain buildable (no false positive)
    distinct_res = check_search_intent_cannibalization(
        "interstate 1031 exchange replacement property rules", canonical_profithelm_hubs
    )
    assert distinct_res["is_cannibalizing"] is False


def test_historical_replay_query_grouping_and_synthetic_rejection(canonical_profithelm_hubs):
    assert hasattr(qual_mod, "group_related_queries_by_intent"), "Missing group_related_queries_by_intent"
    historical_queue = [
        {"slug": "ca-tax-brackets", "query": "ca tax brackets", "impressions": 210, "position": 12.4},
        {"slug": "ca-tax-brackets-2025", "query": "ca tax brackets 2025", "impressions": 140, "position": 14.1},
        {"slug": "ca-tax-brackets-2026", "query": "ca tax brackets 2026", "impressions": 320, "position": 11.2},
        {"slug": "ca-tax-brackets-2026-married-jointly", "query": "ca tax brackets 2026 married jointly", "impressions": 95, "position": 9.8},
        {"slug": "ca-tax-brackets-2026-single", "query": "ca tax brackets 2026 single", "impressions": 88, "position": 10.5},
        {"slug": "ca-tax-brackets-married", "query": "ca tax brackets married", "impressions": 110, "position": 13.0},
        {"slug": "ca-tax-brackets-2026-head-of-household", "query": "ca tax brackets 2026 head of household", "impressions": 65, "position": 15.2},
        {"slug": "ca-tax-brackets-married-filing-jointly", "query": "ca tax brackets married filing jointly", "impressions": 75, "position": 14.8},
        {"slug": "california-income-tax-brackets-2026", "query": "california income tax brackets 2026", "impressions": 180, "position": 11.9},
        {"slug": "california-tax-brackets-2026", "query": "california tax brackets 2026", "impressions": 260, "position": 10.9},
        {"slug": "1031-exchange-rules-arizona", "query": "1031 exchange rules arizona", "impressions": 90, "position": 13.5},
        {"slug": "irs-2027-tax-rates", "query": "irs 2027 tax rates", "impressions": 150, "position": 12.0},
        {"slug": "irs-capital-gains-statutory-tax", "query": "irs capital gains statutory tax", "impressions": 130, "position": 14.0},
        {"slug": "kalshi-prediction-market-arbitrage-strategy", "query": "kalshi prediction market arbitrage strategy", "impressions": 115, "position": 11.7},
        {"slug": "irs-2027-tax-brackets-scenario-comparison-model", "query": "irs 2027 tax brackets scenario comparison model", "impressions": 40, "position": 18.0},
        {"slug": "crypto-tax-calculator-scenario-comparison-model", "query": "crypto tax calculator scenario comparison model", "impressions": 45, "position": 17.5},
        {"slug": "prediction-market-odds-scenario-comparison-model", "query": "prediction market odds scenario comparison model", "impressions": 38, "position": 19.0},
        {"slug": "tcja-sunset-capital-gains-scenario-comparison-model", "query": "tcja sunset capital gains scenario comparison model", "impressions": 42, "position": 16.5},
        {"slug": "section-1031-calculator-scenario-comparison-model", "query": "section 1031 calculator scenario comparison model", "impressions": 50, "position": 16.0},
        {"slug": "query-two-buildable", "query": "query two buildable", "impressions": 85, "position": 24.0},
    ]

    grouped = qual_mod.group_related_queries_by_intent(historical_queue, existing_tools=canonical_profithelm_hubs)
    assert grouped["cannibalization_prevented_count"] == 19
    assert len(grouped["novel_topic_clusters"]) == 0
    assert len(grouped["rejected_synthetic"]) == 1
    assert grouped["rejected_synthetic"][0]["slug"] == "query-two-buildable"
    assert len(grouped["existing_page_groups"]["irs-2027-tax-brackets"]["grouped_queries"]) == 12

    # Verify qualify_search_intent & assert_search_intent_qualified reject synthetic test candidates
    verdict = qualify_search_intent({"query": "query two buildable", "slug": "query-two-buildable", "impressions": 85, "position": 24.0})
    assert verdict["action"] == "REJECT_SYNTHETIC"
    assert verdict.status == "PRUNE"
    with pytest.raises(ValueError, match="Synthetic test fixture"):
        assert_search_intent_qualified({"query": "query two buildable", "slug": "query-two-buildable"})


def test_gsc_remediation_internal_links_and_competing_url_consolidation():
    links = _resolve_contextual_internal_links(
        slug="section-1031-calculator",
        tenant_id="profithelm",
        query="section 1031 like kind exchange",
    )
    hrefs = {item["href"] for item in links}
    assert "/tools/1031-exchange-rules-arizona/" not in hrefs
    assert "/tools/section-1031-calculator-scenario-comparison-model/" not in hrefs
    assert "/tools/irs-capital-gains-statutory-tax/" not in hrefs
    assert "/tools/tcja-sunset-capital-gains/" in hrefs

    # Competing URLs for the same query + multiple queries for the same URL
    signals = [
        {
            "query": "ca tax brackets 2026",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "impressions": 420,
            "position": 8.4,
            "ctr": 0.012,
        },
        {
            "query": "ca tax brackets 2026",
            "target_url": "https://profithelm.com/tools/ca-tax-brackets-2026/",
            "impressions": 95,
            "position": 16.2,
            "ctr": 0.005,
        },
        {
            "query": "california married filing jointly tax brackets 2026",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "impressions": 180,
            "position": 10.1,
            "ctr": 0.015,
        },
    ]
    prioritized = prioritize_gsc_signals(signals, tenant_id="profithelm")
    ca_canonical_recs = [
        r for r in prioritized if r["target_url"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    ]
    assert len(ca_canonical_recs) == 2
    competing_rec = [r for r in ca_canonical_recs if r["query"] == "ca tax brackets 2026"][0]
    assert competing_rec.get("consolidation_needed") is True
    assert competing_rec["canonical_url"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    assert "https://profithelm.com/tools/ca-tax-brackets-2026/" in competing_rec["redirect_candidates"]
    assert set(competing_rec["grouped_queries"]) == {
        "ca tax brackets 2026",
        "california married filing jointly tax brackets 2026",
    }


def test_daily_overlay_lock_groups_new_queries_without_resetting_lock_and_evaluates_agy_dir(tmp_path):
    agy_ov_dir = tmp_path / ".agy" / "overlays"
    agy_ov_dir.mkdir(parents=True)
    ov_file = agy_ov_dir / "irs-2027-tax-brackets.json"

    future_lock = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    initial_spec = {
        "slug": "irs-2027-tax-brackets",
        "query": "2027 irs tax brackets",
        "created_at": "2026-10-01T00:00:00+00:00",
        "locked_until": future_lock,
        "baseline_position": 11.4,
        "h2_headings": ["2027 IRS Tax Brackets Rules and Guidelines"],
        "preset_scenarios": [
            {"label": "2027 Baseline", "query": "2027 irs tax brackets", "target_position": 11.4, "impressions": 300}
        ],
        "faq_entries": [
            {"question": "How are 2027 IRS tax brackets calculated?", "answer": "Inflation-adjusted under IRC Section 1(f)."}
        ],
    }
    res1, written1 = persist_overlay_respecting_lock(ov_file, initial_spec)
    assert written1 is True
    assert res1["grouped_queries"] == ["2027 irs tax brackets"]

    # Re-submitting the SAME query while locked must NOT rewrite or reset the lock
    duplicate_spec = {
        **initial_spec,
        "created_at": "2026-10-15T00:00:00+00:00",
        "locked_until": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
    }
    res_dup, written_dup = persist_overlay_respecting_lock(ov_file, duplicate_spec)
    assert written_dup is False
    assert res_dup["locked_until"] == future_lock

    # Submitting a NEW related striking-distance query for the same page MUST group it without resetting the lock
    new_query_spec = {
        "slug": "irs-2027-tax-brackets",
        "query": "irs 2027 tax rates married filing jointly",
        "created_at": "2026-10-16T00:00:00+00:00",
        "locked_until": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
        "h2_headings": ["IRS 2027 Married Filing Jointly Tax Rates"],
        "preset_scenarios": [
            {
                "label": "MFJ 2027 Scenario",
                "query": "irs 2027 tax rates married filing jointly",
                "target_position": 9.5,
                "impressions": 190,
            }
        ],
        "faq_entries": [
            {"question": "What are the 2027 MFJ tax brackets?", "answer": "Statutory brackets under IRC Section 1(j)."}
        ],
    }
    res_merged, written_merged = persist_overlay_respecting_lock(ov_file, new_query_spec)
    assert written_merged is True
    assert res_merged["created_at"] == "2026-10-01T00:00:00+00:00"
    assert res_merged["locked_until"] == future_lock
    assert res_merged["baseline_position"] == 11.4
    assert res_merged["grouped_queries"] == [
        "2027 irs tax brackets",
        "irs 2027 tax rates married filing jointly",
    ]
    assert len(res_merged["preset_scenarios"]) == 2
    assert len(res_merged["faq_entries"]) == 2

    # Expired overlay inside .agy/overlays (without content/overlays) must be evaluated by evaluate_expired_overlays
    expired_file = agy_ov_dir / "section-1031-calculator.json"
    past_lock = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    expired_file.write_text(
        json.dumps({
            "slug": "section-1031-calculator",
            "query": "section 1031 exchange",
            "locked_until": past_lock,
            "baseline_position": 14.0,
            "baseline_ctr": 0.015,
            "baseline_impressions": 200,
            "post_eval_metrics": {"position": 8.5, "ctr": 0.032, "impressions": 260, "clicks": 8},
        }),
        encoding="utf-8",
    )
    eval_res = evaluate_expired_overlays(base_dir=tmp_path)
    assert eval_res["total_evaluated"] == 2
    assert eval_res["summary"]["ACCRETIVE"] == 1
    assert eval_res["summary"]["MONITORING"] == 1


def test_drift_qualification_signature_and_tenant_topical_reconciliation(tmp_path):
    # 1. Verify drift.py style keyword-arg call and .status attribute
    q_prune = qualify_search_intent(query="obsolete 2011 tax rule", impressions=0, position=90.0, days=120)
    assert q_prune.status == "PRUNE"
    assert q_prune["action"] == "PRUNE_PAGE"

    # 2. Verify reconcile_tenant_topical_authority_and_cannibalization on a tenant fixture
    assert hasattr(qual_mod, "reconcile_tenant_topical_authority_and_cannibalization")
    (tmp_path / "profithelm" / "data").mkdir(parents=True)
    (tmp_path / ".agy" / "overlays").mkdir(parents=True)
    (tmp_path / "content" / "overlays").mkdir(parents=True)
    (tmp_path / "dist" / "tools" / "ca-tax-brackets-2026").mkdir(parents=True)
    (tmp_path / "dist" / "tools" / "ca-tax-brackets-2026" / "index.html").write_text("<html></html>", encoding="utf-8")

    dyn_tools = [
        {
            "slug": "section-301-tariff-landed-cost-calculator",
            "title": "Section 301 Tariff & Landed Cost Calculator",
            "primary_keyword": "section 301 tariff landed cost calculator",
            "secondary_keywords": ["import duty calculator"],
            "statutory_references": ["19 U.S.C. Section 2411 (Section 301 Tariffs)"],
            "adjacent_tools": ["section-179-calculator", "crypto-tax-calculator", "1031-exchange-rules-arizona"],
            "calculation_prompts": [
                {"label": "Baseline", "prompt": "Compute landed cost."},
                {"label": "TCJA Sunset & Statutory Rate Sensitivity", "prompt": "Evaluate TCJA Sunset impact."},
                {"label": "IRC Section 1411 NIIT Exposure", "prompt": "Calculate Section 1411 surtax."},
            ],
            "proprietary_calculation_table": [
                {"scenario": "IRC Section 1202 Exclusion", "notes": "QSBS"},
                {"scenario": "IRC Section 1411 Net Investment Income Tax", "notes": "NIIT"},
            ],
        },
        {
            "slug": "ca-tax-brackets-2026",
            "title": "CA Tax Brackets 2026",
            "primary_keyword": "ca tax brackets 2026",
            "secondary_keywords": ["california tax brackets 2026"],
        },
        {
            "slug": "query-two-buildable",
            "title": "Query Two Buildable",
            "primary_keyword": "query two buildable",
            "secondary_keywords": [],
        },
    ]
    (tmp_path / "profithelm" / "data" / "dynamic_tools.json").write_text(json.dumps(dyn_tools), encoding="utf-8")
    (tmp_path / "content" / "redirects.json").write_text(
        json.dumps({"/shopify-profit-tracker": "/tools/saas-runway-calculator/"}),
        encoding="utf-8",
    )

    summary = qual_mod.reconcile_tenant_topical_authority_and_cannibalization(
        repo_root=tmp_path,
        property_id="profithelm",
        dist_dir=tmp_path / "dist",
    )
    assert "ca-tax-brackets-2026" in summary["consolidated_clones"]
    assert "query-two-buildable" in summary["removed_synthetic_slugs"]
    assert "section-301-tariff-landed-cost-calculator" in summary["cleaned_mixed_signal_slugs"]
    assert not (tmp_path / "dist" / "tools" / "ca-tax-brackets-2026").exists()

    cleaned_tools = json.loads((tmp_path / "profithelm" / "data" / "dynamic_tools.json").read_text(encoding="utf-8"))
    assert len(cleaned_tools) == 1
    b2b_tool = cleaned_tools[0]
    assert "crypto-tax-calculator" not in b2b_tool["adjacent_tools"]
    assert "1031-exchange-rules-arizona" not in b2b_tool["adjacent_tools"]
    assert "section-1031-calculator" in b2b_tool["adjacent_tools"]
    assert "TCJA Sunset" not in json.dumps(b2b_tool["calculation_prompts"])
    assert "IRC Section 1202" not in json.dumps(b2b_tool["proprietary_calculation_table"])

    redirects = json.loads((tmp_path / "content" / "redirects.json").read_text(encoding="utf-8"))
    assert redirects["/tools/ca-tax-brackets-2026/"] == "/tools/irs-2027-tax-brackets/california/"
    assert redirects["/shopify-profit-tracker"] == "/tools/"
    assert redirects["/tools/landed-cost-calculator/"] == "/tools/section-301-tariff-landed-cost-calculator/"


def test_competitor_cluster_and_overlay_hub_links_scrub_retired_clones(tmp_path):
    from pseofactory.competitor import render_competitor_winning_pattern_blocks
    from pseofactory.gsc_remediation import inject_overlay_into_html
    from pseofactory.maintenance import RetroReflectionEngine

    blocks = render_competitor_winning_pattern_blocks(
        slug="irs-2027-tax-brackets",
        title="2027 IRS Tax Brackets & TCJA Sunset Calculator",
        property_id="profithelm",
        canonical_base="https://profithelm.com",
        statutory_authority="IRC Section 1(j)",
        economic_dataset="IRS Rev. Proc. 2025-32",
    )
    assert "/tools/1031-exchange-rules-arizona/" not in blocks["three_tier_cluster_html"]
    assert "/tools/tcja-sunset-capital-gains/" in blocks["three_tier_cluster_html"]

    stale_cluster_html = (
        '<nav data-mechanic="on_this_page_jump_nav"></nav>'
        '<section data-mechanic="three_tier_topic_cluster_nav">'
        '<a href="https://profithelm.com/tools/1031-exchange-rules-arizona/">Stale</a>'
        '</section>'
    )
    missing = RetroReflectionEngine.audit_html_mechanics(stale_cluster_html)
    assert "three_tier_topic_cluster_nav" in missing

    # Verify overlay hub_links reconciliation and HTML re-injection replace stale clone links
    (tmp_path / "profithelm" / "data").mkdir(parents=True)
    (tmp_path / ".agy" / "overlays").mkdir(parents=True)
    (tmp_path / "content" / "overlays").mkdir(parents=True)
    (tmp_path / "profithelm" / "data" / "dynamic_tools.json").write_text("[]", encoding="utf-8")
    stale_overlay = {
        "slug": "section-1031-calculator",
        "query": "section 1031 calculator",
        "h2_headings": ["Section 1031 Rules"],
        "hub_links": [
            {"href": "/tools/1031-exchange-rules-arizona/", "anchor": "AZ 1031 Rules"},
            {"href": "/tools/irs-capital-gains-statutory-tax/", "anchor": "Statutory Capital Gains"},
        ],
    }
    (tmp_path / ".agy" / "overlays" / "section-1031-calculator.json").write_text(
        json.dumps(stale_overlay), encoding="utf-8"
    )
    qual_mod.reconcile_tenant_topical_authority_and_cannibalization(
        repo_root=tmp_path,
        property_id="profithelm",
    )
    refreshed_ov = json.loads(
        (tmp_path / ".agy" / "overlays" / "section-1031-calculator.json").read_text(encoding="utf-8")
    )
    refreshed_hrefs = {item["href"] for item in refreshed_ov["hub_links"]}
    assert "/tools/1031-exchange-rules-arizona/" not in refreshed_hrefs
    assert "/tools/irs-capital-gains-statutory-tax/" not in refreshed_hrefs
    assert "/tools/tcja-sunset-capital-gains/" in refreshed_hrefs

    html_with_stale_overlay = (
        "<html><body><main>"
        '<div id="gsc-striking-overlay" class="gsc-overlay-container">'
        '<section class="overlay-section overlay-hub-links">'
        '<a href="/tools/1031-exchange-rules-arizona/">AZ 1031 Rules</a>'
        "</section></div></main></body></html>"
    )
    reinjected_html = inject_overlay_into_html(html_with_stale_overlay, refreshed_ov)
    assert "/tools/1031-exchange-rules-arizona/" not in reinjected_html
    assert "/tools/tcja-sunset-capital-gains/" in reinjected_html


def test_crawl_budget_consolidation_queue_and_syndication_hygiene(tmp_path):
    from pseofactory.gsc_remediation import _resolve_contextual_internal_links
    from pseofactory.distributor import export_all_syndication_files
    from pseofactory.verifier import MasterSEOVerifier

    # 1. Contextual internal links for tax-bracket queries must never point to retired irs-capital-gains-statutory-tax
    tax_links = _resolve_contextual_internal_links(
        slug="irs-2027-tax-brackets",
        tenant_id="profithelm",
        query="irs 2027 tax brackets",
    )
    tax_hrefs = {item["href"] for item in tax_links}
    assert "/tools/irs-capital-gains-statutory-tax/" not in tax_hrefs
    assert "/tools/tcja-sunset-capital-gains/" in tax_hrefs

    # 2. Real dynamic_tools.json schema cleaning (stringified dicts, title/statutory_reference prompts, dict["rows"] table)
    (tmp_path / "profithelm" / "data").mkdir(parents=True)
    (tmp_path / ".agy" / "overlays").mkdir(parents=True)
    (tmp_path / "content" / "overlays").mkdir(parents=True)
    (tmp_path / "dist" / "tools" / "saas-burn-multiple-benchmarks-2026").mkdir(parents=True)
    (tmp_path / "dist" / "tools" / "saas-burn-multiple-benchmarks-2026" / "index.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    (tmp_path / ".agy" / "tool_spec_ca-tax-brackets-2026.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".agy" / "tool_spec_saas-burn-multiple-benchmarks-2026.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".agy" / "tool_spec_section-179-calculator.json").write_text("{}", encoding="utf-8")

    (tmp_path / "syndication" / "ca-tax-brackets-2026").mkdir(parents=True)
    (tmp_path / "syndication" / "ca-tax-brackets-2026" / "x_post.txt").write_text("stale", encoding="utf-8")
    (tmp_path / "syndication" / "saas-burn-multiple-benchmarks-2026").mkdir(parents=True)
    (tmp_path / "syndication" / "ca-tax-brackets-2026-devto.md").write_text("stale", encoding="utf-8")
    (tmp_path / "syndication" / "facebook_group_targets.md").write_text(
        "# Matrix\n## SaaS Burn\nTarget: https://profithelm.com/tools/saas-burn-multiple-benchmarks-2026/\n## Section 179\nTarget: https://profithelm.com/tools/section-179-calculator/\n",
        encoding="utf-8",
    )

    real_schema_tools = [
        {
            "slug": "contractor-surety-bond-cost-calculator",
            "title": "Contractor License & Performance Surety Bond Cost Calculator",
            "primary_keyword": "contractor surety bond cost calculator",
            "secondary_keywords": ["surety bond rate calculator"],
            "statutory_references": ["40 U.S.C. Sections 3131-3134 (Miller Act)"],
            "adjacent_tools": [
                "{'slug': 'crypto-tax-calculator', 'title': 'Crypto Tax', 'short_title': 'Crypto Tax', 'category': 'Digital Assets', 'canonical_path': '/tools/crypto-tax-calculator/'}",
                "{'slug': 'irs-2027-tax-brackets', 'title': 'IRS 2027 Tax Brackets', 'short_title': 'IRS 2027 Tax Brackets', 'category': 'Tax Intelligence', 'canonical_path': '/tools/irs-2027-tax-brackets/'}",
                "{'slug': 'prediction-market-odds', 'title': 'Prediction Market Arbitrage', 'short_title': 'Prediction Market Arbitrage', 'category': 'Market Arbitrage', 'canonical_path': '/tools/prediction-market-odds/'}",
            ],
            "calculation_prompts": [
                {
                    "title": "TCJA Sunset Rate Simulation",
                    "prompt": "Calculate how 2027 post-TCJA statutory brackets adjust your net liability.",
                    "statutory_reference": "IRC Section 1 (2026-2027 Schedules)",
                    "target_slug": "crypto-tax-calculator",
                },
                {
                    "title": "Net Investment Income Surtax & Capital Deferral",
                    "prompt": "Evaluate capital gains deferral and 3.8% NIIT surtax thresholds.",
                    "statutory_reference": "IRC Section 1411 and Section 1031",
                    "target_slug": "irs-2027-tax-brackets",
                },
            ],
            "proprietary_calculation_table": {
                "title": "Proprietary Matrix",
                "rows": [
                    {"tier": "Standard Growth", "reference": "IRC Section 1202"},
                    {"tier": "Institutional", "reference": "IRC Section 1411"},
                ],
            },
        },
        {
            "slug": "saas-burn-multiple-benchmarks-2026",
            "title": "SaaS Burn Multiple Benchmarks 2026",
            "primary_keyword": "saas burn multiple benchmarks 2026",
            "secondary_keywords": ["david sacks burn multiple"],
        },
    ]
    (tmp_path / "profithelm" / "data" / "dynamic_tools.json").write_text(
        json.dumps(real_schema_tools), encoding="utf-8"
    )
    (tmp_path / ".agy" / "deployed_voids.json").write_text(
        json.dumps([
            {"slug": "qsbs-section-1202-tax-calculator", "query": "qsbs section 1202 tax calculator"},
            {"slug": "saas-burn-multiple-benchmarks-2026", "query": "saas burn multiple benchmarks 2026"},
            {"slug": "valid-edge-tool-2027", "query": "valid edge tool 2027"},
        ]),
        encoding="utf-8",
    )
    (tmp_path / "void_candidates.jsonl").write_text(
        "\n".join([
            json.dumps({"slug": "irs-capital-gains-statutory-tax", "query": "irs capital gains statutory tax", "action": "BUILD_PAGE"}),
            json.dumps({"slug": "saas-burn-multiple-benchmarks-2026", "query": "saas burn multiple benchmarks 2026", "action": "BUILD_PAGE", "status": "PENDING"}),
            json.dumps({"slug": "ionq-stock", "query": "ionq stock", "action": "BUILD_PAGE"}),
            json.dumps({"slug": "section-179-calculator", "query": "section 179 calculator", "action": "BUILD_PAGE", "status": "BUILT"}),
        ]) + "\n",
        encoding="utf-8",
    )

    rec = qual_mod.reconcile_tenant_topical_authority_and_cannibalization(
        repo_root=tmp_path,
        property_id="profithelm",
        dist_dir=tmp_path / "dist",
    )
    assert "saas-burn-multiple-benchmarks-2026" in rec["consolidated_clones"]
    assert rec["stale_tool_specs_removed"] == 2
    assert not (tmp_path / ".agy" / "tool_spec_ca-tax-brackets-2026.json").exists()
    assert not (tmp_path / ".agy" / "tool_spec_saas-burn-multiple-benchmarks-2026.json").exists()
    assert (tmp_path / ".agy" / "tool_spec_section-179-calculator.json").exists()
    assert not (tmp_path / "dist" / "tools" / "saas-burn-multiple-benchmarks-2026").exists()
    assert not (tmp_path / "syndication" / "ca-tax-brackets-2026").exists()
    assert not (tmp_path / "syndication" / "saas-burn-multiple-benchmarks-2026").exists()
    assert not (tmp_path / "syndication" / "ca-tax-brackets-2026-devto.md").exists()
    assert "saas-burn-multiple-benchmarks-2026" not in (tmp_path / "syndication" / "facebook_group_targets.md").read_text(encoding="utf-8")

    cleaned_dyn = json.loads((tmp_path / "profithelm" / "data" / "dynamic_tools.json").read_text(encoding="utf-8"))
    assert len(cleaned_dyn) == 1
    bond_tool = cleaned_dyn[0]
    adj_dump = json.dumps(bond_tool["adjacent_tools"])
    assert "crypto-tax-calculator" not in adj_dump
    assert "prediction-market-odds" not in adj_dump
    assert "s-corp-reasonable-salary-tax-calculator" in adj_dump
    prompts_dump = json.dumps(bond_tool["calculation_prompts"])
    assert "TCJA Sunset" not in prompts_dump
    assert "IRC Section 1411" not in prompts_dump
    assert "crypto-tax-calculator" not in prompts_dump
    table_dump = json.dumps(bond_tool["proprietary_calculation_table"])
    assert "IRC Section 1202" not in table_dump
    assert "IRC Section 1411" not in table_dump
    assert "Miller Act" in table_dump

    dv_after = json.loads((tmp_path / ".agy" / "deployed_voids.json").read_text(encoding="utf-8"))
    assert len(dv_after) == 2
    assert all(item["status"] == "CONSOLIDATED_REDIRECT" for item in dv_after)

    vc_after = [json.loads(line) for line in (tmp_path / "void_candidates.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert vc_after[0]["status"] == "REJECTED"
    assert vc_after[0]["consolidation_status"] == "CONSOLIDATED_REDIRECT"
    assert vc_after[0]["canonical_slug"] == "tcja-sunset-capital-gains"
    assert vc_after[1]["status"] == "REJECTED"
    assert vc_after[1]["canonical_slug"] == "saas-runway-calculator"
    assert vc_after[2]["status"] == "REJECTED"
    assert vc_after[3]["status"] == "BUILT"

    # 3. Verify export_all_syndication_files purges retired folders in output_dir rather than resurrecting them
    (tmp_path / "syndication" / "ca-tax-brackets-2026").mkdir(parents=True)
    export_all_syndication_files(
        tools=[{"slug": "section-179-calculator", "title": "Section 179 Calculator"}],
        output_dir=tmp_path / "syndication",
        dry_run=False,
        property_id="profithelm",
    )
    assert not (tmp_path / "syndication" / "ca-tax-brackets-2026").exists()
    assert (tmp_path / "syndication" / "section-179-calculator").is_dir()

    # 4. Verify check_url_redirects_gate catches internal HTML links pointing to a redirected source
    full_dist = tmp_path / "full_dist"
    (full_dist / "tools" / "section-179-calculator").mkdir(parents=True)
    (full_dist / "index.html").write_text('<html><body><a href="/tools/section-179-calculator/">179</a></body></html>', encoding="utf-8")
    (full_dist / "tools" / "index.html").write_text(
        '<html><body><a href="/tools/ca-tax-brackets-2026/">Stale Redirected Slug</a></body></html>',
        encoding="utf-8",
    )
    (full_dist / "tools" / "section-179-calculator" / "index.html").write_text("<html><body>Ok</body></html>", encoding="utf-8")
    (full_dist / "_redirects").write_text(
        "/tools/ca-tax-brackets-2026/ /tools/section-179-calculator/ 301\n",
        encoding="utf-8",
    )
    verifier = MasterSEOVerifier(dist_dir=full_dist, domain="profithelm.com")
    red_gate = verifier.check_url_redirects_gate(full_dist)
    assert red_gate["status"] == "FAIL"
    assert any("points to redirected source" in issue for issue in red_gate["issues"])


def test_redirected_search_signal_rollup_and_audit_reconciliation(tmp_path):
    from pseofactory import qualification as qual_mod
    from pseofactory.indexing.feedback_loop import (
        DiagnosisResult,
        IndexingFeedbackLoop,
        RootCauseClassification,
    )

    # 0. Verify prioritize_gsc_signals rolls up retired URL even when retired URL has higher impressions than canonical
    signals = [
        {
            "query": "2027 california tax brackets",
            "target_url": "https://profithelm.com/tools/2027-california-tax-brackets/",
            "impressions": 300,
            "clicks": 3,
            "ctr": 0.01,
            "position": 8.0,
        },
        {
            "query": "2027 california tax brackets",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "impressions": 50,
            "clicks": 1,
            "ctr": 0.02,
            "position": 11.5,
        },
        {
            "query": "shopify profit margin calculator",
            "target_url": "https://profithelm.com/tools/shopify-profit-margin-calculator/",
            "impressions": 200,
            "clicks": 0,
            "ctr": 0.0,
            "position": 40.0,
        },
    ]
    prioritized = prioritize_gsc_signals(signals, tenant_id="profithelm")
    assert len(prioritized) == 1
    can_cand = prioritized[0]
    assert can_cand["target_url"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    assert can_cand["canonical_url"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    assert can_cand["impressions"] == 350
    assert can_cand["direct_impressions"] == 50
    assert can_cand["redirected_impressions"] == 300
    assert can_cand["clicks"] == 4
    assert can_cand["consolidation_needed"] is True
    assert "https://profithelm.com/tools/2027-california-tax-brackets/" in can_cand["redirect_candidates"]

    rollup_redirected_gsc_rows = getattr(qual_mod, "rollup_redirected_gsc_rows", None)
    reconcile_metric_recovery_ledger = getattr(qual_mod, "reconcile_metric_recovery_ledger", None)
    reconcile_factory_execution_log = getattr(qual_mod, "reconcile_factory_execution_log", None)
    resolve_redirected_gsc_target = getattr(qual_mod, "resolve_redirected_gsc_target", None)
    assert callable(rollup_redirected_gsc_rows)
    assert callable(reconcile_metric_recovery_ledger)
    assert callable(reconcile_factory_execution_log)
    assert callable(resolve_redirected_gsc_target)

    try:
        state_leaf_res = resolve_redirected_gsc_target(
            slug="irs-2027-tax-brackets-california",
            property_id="profithelm",
        )
    except Exception:
        state_leaf_res = {}
    assert state_leaf_res.get("canonical_path") == "/tools/irs-2027-tax-brackets/california/"
    assert state_leaf_res.get("canonical_slug") == "irs-2027-tax-brackets"
    assert state_leaf_res.get("resolved_via") == "hyphenated_state_leaf"

    # 1. Verify rollup_redirected_gsc_rows rolls up retired 301 URLs into canonical targets and ignores off-topic sinks
    raw_gsc_rows = [
        {
            "page": "https://profithelm.com/tools/2027-california-tax-brackets/",
            "query": "2027 california tax brackets",
            "impressions": 28,
            "clicks": 3,
            "position": 8.0,
        },
        {
            "page": "https://profithelm.com/tools/california-tax-brackets-2027/",
            "query": "2027 california tax brackets",
            "impressions": 45,
            "clicks": 1,
            "position": 8.42,
        },
        {
            "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "query": "2027 california tax brackets",
            "impressions": 19,
            "clicks": 0,
            "position": 9.89,
        },
        {
            "page": "https://profithelm.com/tools/prediction-market-odds-scenario-comparison-model/",
            "query": "prediction market odds",
            "impressions": 9,
            "clicks": 0,
            "position": 5.78,
        },
        {
            "page": "https://profithelm.com/tools/shopify-profit-margin-calculator/",
            "query": "shopify profit margin calculator",
            "impressions": 11,
            "clicks": 0,
            "position": 52.0,
        },
    ]
    rollup = rollup_redirected_gsc_rows(raw_gsc_rows, property_id="profithelm")
    assert rollup["redirected_rows_count"] == 3
    assert rollup["rolled_up_impressions"] == 82
    assert rollup["rolled_up_clicks"] == 4
    assert rollup["ignored_off_topic_rows_count"] == 1
    assert rollup["ignored_off_topic_impressions"] == 11
    # Both the state leaf and parent tool hub are credited in impressions_by_path
    assert rollup["impressions_by_path"]["/tools/irs-2027-tax-brackets/california"] == 92
    assert rollup["impressions_by_path"]["/tools/irs-2027-tax-brackets"] == 92
    assert rollup["impressions_by_path"]["/tools/prediction-market-odds"] == 9
    assert "/tools/shopify-profit-margin-calculator" not in rollup["impressions_by_path"]

    ca_row = [r for r in rollup["rows"] if r["canonical_path"] == "/tools/irs-2027-tax-brackets/california/"][0]
    assert ca_row["impressions"] == 92
    assert ca_row["clicks"] == 4
    assert ca_row["direct_impressions"] == 19
    assert ca_row["redirected_impressions"] == 73
    assert len(ca_row["rolled_up_from"]) == 2
    assert "rolled_up_rows" in rollup

    # 1b. Verify rollup_redirected_gsc_rows is idempotent when called on already-rolled-up rows
    rollup_second_pass = rollup_redirected_gsc_rows(rollup["rows"], property_id="profithelm")
    assert rollup_second_pass["redirected_rows_count"] == 3
    assert rollup_second_pass["rolled_up_impressions"] == 82
    assert rollup_second_pass["rolled_up_clicks"] == 4
    assert (
        rollup_second_pass["canonical_targets_summary"]["/tools/irs-2027-tax-brackets/california/"]["redirected_impressions"]
        == 73
    )

    nj_res = resolve_redirected_gsc_target(query="nj tax bracket", property_id="profithelm")
    assert nj_res["canonical_path"] == "/tools/irs-2027-tax-brackets/new-jersey/"
    crypto_res = resolve_redirected_gsc_target(query="calculate crypto taxes", property_id="profithelm")
    assert crypto_res["canonical_path"] == "/tools/crypto-tax-calculator/"

    # 2. Verify prioritize_gsc_signals rolls up retired URL even when retired URL has higher impressions than canonical
    signals = [
        {
            "query": "2027 california tax brackets",
            "target_url": "https://profithelm.com/tools/2027-california-tax-brackets/",
            "impressions": 300,
            "clicks": 3,
            "ctr": 0.01,
            "position": 8.0,
        },
        {
            "query": "2027 california tax brackets",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "impressions": 50,
            "clicks": 1,
            "ctr": 0.02,
            "position": 11.5,
        },
        {
            "query": "shopify profit margin calculator",
            "target_url": "https://profithelm.com/tools/shopify-profit-margin-calculator/",
            "impressions": 200,
            "clicks": 0,
            "ctr": 0.0,
            "position": 40.0,
        },
    ]
    prioritized = prioritize_gsc_signals(signals, tenant_id="profithelm")
    assert len(prioritized) == 1
    can_cand = prioritized[0]
    assert can_cand["target_url"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    assert can_cand["canonical_url"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    assert can_cand["impressions"] == 350
    assert can_cand["direct_impressions"] == 50
    assert can_cand["redirected_impressions"] == 300
    assert can_cand["clicks"] == 4
    assert can_cand["consolidation_needed"] is True
    assert "https://profithelm.com/tools/2027-california-tax-brackets/" in can_cand["redirect_candidates"]

    # 3. Verify execute_engine_repairs remaps retired slugs to canonical target and never writes retired overlays
    dist_dir = tmp_path / "dist"
    ca_leaf_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "california"
    ca_leaf_dir.mkdir(parents=True)
    ca_leaf_html = ca_leaf_dir / "index.html"
    ca_leaf_html.write_text(
        '<!DOCTYPE html><html><head><title>CA Tax Brackets</title>'
        '<link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/california/"></head>'
        '<body><main><h1>California Tax Brackets</h1>'
        '<aside class="quick-answer"><div class="quick-answer-title">Statutory Summary</div>'
        '<p>Under IRC Section 1 and California Revenue and Taxation Code Section 17041, single and married '
        'taxpayers calculate marginal state income tax rates across nine progressive brackets ranging from '
        '1 percent to 13.3 percent with statutory inflation indexing.</p></aside>'
        '</main></body></html>',
        encoding="utf-8",
    )

    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        base_dir=tmp_path,
        dist_dir=dist_dir,
    )
    retired_diag = DiagnosisResult(
        url="https://profithelm.com/tools/ca-tax-brackets-2026/",
        classification=RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value,
        reason="Crawled - currently not indexed",
        remediation_action="Enrich answer",
        reflection_path="reflect",
    )
    sink_diag = DiagnosisResult(
        url="https://profithelm.com/tools/shopify-profit-margin-calculator/",
        classification=RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value,
        reason="Crawled - currently not indexed",
        remediation_action="Enrich answer",
        reflection_path="reflect",
    )
    repair_res = loop.execute_engine_repairs(
        diagnoses=[retired_diag, sink_diag],
        force=False,
        dry_run=False,
        skip_recompile=True,
    )
    assert not (tmp_path / "content" / "overlays" / "ca-tax-brackets-2026.json").exists()
    assert not (tmp_path / "content" / "overlays" / "shopify-profit-margin-calculator.json").exists()
    assert (tmp_path / "content" / "overlays" / "irs-2027-tax-brackets-california.json").is_file()
    assert "irs-2027-tax-brackets/california" in repair_res["repaired_slugs"]

    # 4. Verify reconcile_metric_recovery_ledger & reconcile_factory_execution_log
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    (agy_dir / "metric_recovery_ledger.json").write_text(
        json.dumps({
            "snapshots": {
                "ca-tax-brackets-2026": {
                    "slug": "ca-tax-brackets-2026",
                    "url": "https://profithelm.com/tools/ca-tax-brackets-2026/",
                    "baseline_impressions": 100,
                    "status": "ACCRETIVE_CONFIRMED",
                },
                "shopify-profit-margin-calculator": {
                    "slug": "shopify-profit-margin-calculator",
                    "url": "https://profithelm.com/tools/shopify-profit-margin-calculator/",
                    "baseline_impressions": 100,
                    "status": "ACCRETIVE_CONFIRMED",
                },
            },
            "evaluations": [
                {"slug": "ca-tax-brackets-2026", "status": "ACCRETIVE_CONFIRMED"},
                {"slug": "shopify-profit-margin-calculator", "status": "ACCRETIVE_CONFIRMED"},
            ],
        }),
        encoding="utf-8",
    )
    m_rec = reconcile_metric_recovery_ledger(tmp_path, property_id="profithelm")
    assert m_rec["retired_snapshots_rolled_up"] == 2
    assert m_rec["retired_evaluations_removed"] == 2
    m_after = json.loads((agy_dir / "metric_recovery_ledger.json").read_text(encoding="utf-8"))
    assert "ca-tax-brackets-2026" not in m_after["snapshots"]
    assert "shopify-profit-margin-calculator" not in m_after["snapshots"]
    assert "irs-2027-tax-brackets" in m_after["snapshots"]
    assert "ca-tax-brackets-2026" in m_after["snapshots"]["irs-2027-tax-brackets"]["rolled_up_redirected_slugs"]

    (agy_dir / "factory_execution_log.json").write_text(
        json.dumps({
            "stages": {
                "1_scan": {
                    "sc_performance_audit": {
                        "audit_items": [
                            {
                                "query": "ca tax brackets",
                                "impressions": 5,
                                "position": 20.6,
                                "matching_tool": None,
                            }
                        ]
                    }
                }
            }
        }),
        encoding="utf-8",
    )
    f_rec = reconcile_factory_execution_log(tmp_path, property_id="profithelm")
    assert f_rec["queries_resolved"] == 1
    f_after = json.loads((agy_dir / "factory_execution_log.json").read_text(encoding="utf-8"))
    item_after = f_after["stages"]["1_scan"]["sc_performance_audit"]["audit_items"][0]
    assert item_after["matching_tool"] == "irs-2027-tax-brackets"
    assert item_after["canonical_target"] == "/tools/irs-2027-tax-brackets/california/"

    # 5. Verify check_snippet_gate & check_no_js_rendering_gate accurately parse <aside class="quick-answer"> with inner <div>
    from pseofactory.verifier import MasterSEOVerifier

    sc_leaf_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "south-carolina"
    sc_leaf_dir.mkdir(parents=True)
    (sc_leaf_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><title>SC Tax Brackets</title>'
        '<link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/south-carolina/"></head>'
        '<body><main><h1>South Carolina Tax Brackets</h1>'
        '<aside class="quick-answer"><div class="quick-answer-title">Statutory Summary</div>'
        '<p>Under IRC Section 1 and South Carolina Code Section 12-6-510, single and married '
        'taxpayers calculate marginal state income tax rates across progressive statutory brackets '
        'ranging from zero percent to 6.2 percent with annual inflation indexing and federal '
        'taxable income conformity adjustments for the 2027 tax year.</p></aside>'
        '<p>Additional statutory calculation methodology and bracket threshold tables for South Carolina residents.</p>'
        '</main></body></html>',
        encoding="utf-8",
    )

    v_leaf = MasterSEOVerifier(dist_dir=dist_dir, domain="profithelm.com")
    snippet_res = v_leaf.check_snippet_gate(dist_dir)
    assert snippet_res["status"] == "PASS"
    assert snippet_res["issues"] == []
    no_js_res = v_leaf.check_no_js_rendering_gate(dist_dir)
    assert no_js_res["status"] == "PASS"
    assert no_js_res["issues"] == []


def test_striking_distance_4_15_duplicate_suppression_title_protection_and_subintent_injection(tmp_path):
    """
    Verifies the end-to-end striking-distance (positions 4-15) upgrade loop:
      1. Suppresses duplicate BUILD_PAGE creation when an existing URL already ranks 4-15
         in GSC or covers the statutory regime (converting to REFACTOR_PAGE on the canonical
         hub or state subroute), while allowing genuinely distinct statutory tools.
      2. Weighs title tightening vs top-3 winner protection (PROTECT_TOP3_WINNER vs
         TIGHTEN_STRIKING_4_15).
      3. Injects exact missing query-level sub-intent H2s and FAQs (MFJ vs Single,
         2026 vs 2027 Tax Tables, State Capital Gains Deferral, Partial 1031 Boot,
         Section 179 vs Bonus Depreciation, RAP 2026 Tiered AGI Schedule, College Loan Estimator).
      4. Reinforces internal anchor links with position 4-15 query-aligned anchors.
      5. Filters 'site:' scraper queries and prevents pos 80-95 queries from masquerading
         as position 4-15 primary brief queries.
    """
    from pseofactory.gsc_remediation import (
        _resolve_contextual_internal_links,
        compile_remediation_overlay_spec,
        resolve_striking_distance_title_strategy,
    )
    from pseofactory.qualification import (
        check_search_intent_cannibalization,
        evaluate_query_modifier_expansion_vs_distinct_tool,
        qualify_search_intent,
        reconcile_void_candidates_queue,
    )
    from pseofactory.seo_growth_loops import compile_search_opportunity_briefs

    gsc_rows = [
        {
            "query": "2027 tax brackets married filing jointly",
            "page": "https://profithelm.com/tools/irs-2027-tax-brackets/",
            "impressions": 37,
            "clicks": 0,
            "position": 9.76,
        },
        {
            "query": "tax deferral calculator",
            "page": "https://profithelm.com/tools/section-1031-calculator/texas/",
            "impressions": 14,
            "clicks": 0,
            "position": 10.5,
        },
    ]

    # 1. Duplicate suppression via GSC rows + sub-intent modifier classification
    mod_mfj = evaluate_query_modifier_expansion_vs_distinct_tool(
        "2027 tax brackets married filing jointly",
        gsc_rows=gsc_rows,
        property_id="profithelm",
    )
    assert mod_mfj["decision"] == "EXPAND_EXISTING_PAGE"
    assert mod_mfj["action"] == "REFACTOR_PAGE"
    assert mod_mfj["parent_slug"] == "irs-2027-tax-brackets"
    assert mod_mfj["ranking_position"] == 9.76

    mod_me = evaluate_query_modifier_expansion_vs_distinct_tool(
        "maine capital gains tax",
        property_id="profithelm",
    )
    assert mod_me["decision"] == "EXPAND_EXISTING_PAGE"
    assert mod_me["action"] == "REFACTOR_PAGE"
    assert mod_me["target_subroute"] == "/tools/section-1031-calculator/maine/"

    mod_boot = evaluate_query_modifier_expansion_vs_distinct_tool(
        "partial 1031 exchange boot calculator",
        property_id="profithelm",
    )
    assert mod_boot["decision"] == "EXPAND_EXISTING_PAGE"
    assert mod_boot["parent_slug"] == "section-1031-calculator"

    mod_179 = evaluate_query_modifier_expansion_vs_distinct_tool(
        "how to calculate section 179 deduction",
        property_id="profithelm",
    )
    assert mod_179["decision"] == "EXPAND_EXISTING_PAGE"
    assert mod_179["parent_slug"] == "section-179-calculator"

    mod_rap = evaluate_query_modifier_expansion_vs_distinct_tool(
        "rap calculator",
        property_id="prexvo",
    )
    assert mod_rap["decision"] == "EXPAND_EXISTING_PAGE"
    assert mod_rap["parent_slug"] == "rap-payment-calculator"

    # Genuinely distinct statutory regime still qualifies for BUILD_PAGE
    mod_distinct = evaluate_query_modifier_expansion_vs_distinct_tool(
        "interstate 1031 exchange replacement property rules",
        property_id="profithelm",
    )
    assert mod_distinct["decision"] == "LAUNCH_DISTINCT_TOOL"
    assert mod_distinct["action"] == "BUILD_PAGE"

    # qualify_search_intent routes ranking 4-15 GSC queries to REFACTOR_PAGE
    qual_res = qualify_search_intent(
        {
            "query": "tax deferral calculator",
            "impressions": 14,
            "gsc_rows": gsc_rows,
        }
    )
    assert qual_res["action"] == "REFACTOR_PAGE"
    assert qual_res["canonical_slug"] == "section-1031-calculator"

    # 2. Queue reconciliation converts cannibalizing BUILD_PAGE:PENDING to REFACTOR_PAGE and drops site: queries
    vc_file = tmp_path / "void_candidates.jsonl"
    vc_file.write_text(
        "\n".join(
            [
                json.dumps({"slug": "site-profithelm-probe", "query": 'site:irs.gov "2026" "section 179"', "action": "BUILD_PAGE", "status": "PENDING"}),
                json.dumps({"slug": "2026-ca-tax-brackets-single", "query": "2026 ca tax brackets single", "action": "BUILD_PAGE", "status": "PENDING"}),
                json.dumps({"slug": "partial-1031-exchange-boot-calculator", "query": "partial 1031 exchange boot calculator", "action": "BUILD_PAGE", "status": "PENDING"}),
                json.dumps({"slug": "qsbs-section-1202-tax-calculator", "query": "qsbs section 1202 tax calculator", "action": "BUILD_PAGE", "status": "PENDING"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rec_summary = reconcile_void_candidates_queue(vc_file)
    assert rec_summary == 4
    reconciled_rows = [json.loads(line) for line in vc_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(reconciled_rows) == 4
    assert reconciled_rows[0]["action"] == "REJECT"
    assert reconciled_rows[0]["status"] == "REJECTED"
    assert all(r["action"] == "REFACTOR_PAGE" and r["status"] in ("REFACTOR_PENDING", "REJECTED") for r in reconciled_rows[1:])

    # 3. Title trade-off: PROTECT_TOP3_WINNER vs TIGHTEN_STRIKING_4_15 + Sub-intent section injection
    spec_protected = compile_remediation_overlay_spec(
        {
            "slug": "irs-2027-tax-brackets",
            "tenant_id": "profithelm",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/",
            "query": "2027 tax brackets married filing jointly",
            "protected_primary_query": "2027 federal tax tables",
            "top_3_winner_queries": ["2027 federal tax tables"],
            "striking_4_15_queries": ["2027 tax brackets married filing jointly", "2027 tax brackets"],
            "grouped_queries": ["2027 federal tax tables", "2027 tax brackets married filing jointly"],
            "position": 2.0,
            "impressions": 152,
            "clicks": 3,
        }
    )
    assert spec_protected["title_protection_mode"] == "PROTECT_TOP3_WINNER"
    assert spec_protected["protected_primary_query"] == "2027 federal tax tables"
    assert 50 <= len(spec_protected["title_rewrite"]) <= 60
    assert "Form 1120-S" not in spec_protected["title_rewrite"]
    assert any("Married Filing Jointly" in h for h in spec_protected["h2_headings"])
    assert any("Tax Tables" in h for h in spec_protected["h2_headings"])

    spec_tightened = compile_remediation_overlay_spec(
        {
            "slug": "rap-payment-calculator",
            "tenant_id": "prexvo",
            "target_url": "https://prexvo.com/tools/rap-payment-calculator/",
            "query": "rap calculator",
            "striking_4_15_queries": ["rap calculator"],
            "position": 10.75,
            "impressions": 8,
            "clicks": 0,
        }
    )
    assert spec_tightened["title_protection_mode"] == "TIGHTEN_STRIKING_4_15"
    assert 50 <= len(spec_tightened["title_rewrite"]) <= 60
    assert "RAP" in spec_tightened["title_rewrite"]
    assert any("RAP Tiered AGI Schedule" in h for h in spec_tightened["h2_headings"])

    # 4. Internal link anchor reinforcement for striking-distance pages
    ph_links = _resolve_contextual_internal_links("profithelm", "irs-2027-tax-brackets", "2027 tax brackets")
    ph_by_href = {item["href"]: item["anchor"] for item in ph_links}
    assert "/tools/irs-2027-tax-brackets/california/" in ph_by_href
    assert "CA Tax Brackets" in ph_by_href["/tools/irs-2027-tax-brackets/california/"]

    # 5. Brief compilation separates pos 4-15 queries from pos 90+ noise and drops site: queries
    brief_rep = compile_search_opportunity_briefs(
        "profithelm",
        repo_root=tmp_path,
        consolidated_gsc={
            "current_rows": [
                {
                    "query": 'site:irs.gov "2026" "section 179"',
                    "canonical_path": "/tools/section-179-calculator",
                    "impressions": 1,
                    "clicks": 0,
                    "position": 4.0,
                },
                {
                    "query": "179 calculator for businesses",
                    "canonical_path": "/tools/section-179-calculator",
                    "impressions": 13,
                    "clicks": 0,
                    "position": 91.8,
                },
                {
                    "query": "how to calculate section 179 deduction",
                    "canonical_path": "/tools/section-179-calculator",
                    "impressions": 4,
                    "clicks": 0,
                    "position": 8.5,
                },
            ]
        },
        apply_overlays=False,
        persist=False,
    )
    assert len(brief_rep["briefs"]) == 1
    b_179 = brief_rep["briefs"][0]
    assert b_179["primary_query"] == "how to calculate section 179 deduction"
    assert b_179["best_striking_4_15_position"] == 8.5
    assert 'site:irs.gov' not in json.dumps(b_179)


def test_seo_checklist_engine_gates_listicle_rejection_unique_meta_and_two_line_quick_answers(tmp_path: Path) -> None:
    """
    Verifies the self-driving SEO checklist engine upgrades:
      1. Thin affiliate listicle rejection (REJECT_LISTICLE_ARCHETYPE) in qualify_search_intent,
         assert_search_intent_qualified, and reconcile_void_candidates_queue.
      2. Abbreviation-safe sentence counting (count_quick_answer_sentences) and strict 2-sentence
         upfront query answers (assert_quick_answer_passage_relevance(..., max_sentences=2)).
      3. Cross-page meta description uniqueness in MasterSEOVerifier.check_meta_descriptions_gate
         and distinct non-truncated vehicle/PSLF descriptions in _normalize_meta_120_155.
      4. Complete Prexvo 3-tier topic cluster routing including PSLF Buyback, 2026 Forgiveness,
         and Tax Bomb Insolvency tools.
    """
    from pseofactory.competitor import _resolve_vertical_competitor_content
    from pseofactory.contracts import (
        assert_no_thin_affiliate_listicle_archetype,
        assert_quick_answer_passage_relevance,
        count_quick_answer_sentences,
        detect_sentence_truncation_issues,
    )
    from pseofactory.gsc_remediation import (
        _normalize_meta_120_155,
        _normalize_quick_answer_40_60_words,
    )
    from pseofactory.qualification import (
        assert_search_intent_qualified,
        is_thin_affiliate_listicle_candidate,
        qualify_search_intent,
        reconcile_void_candidates_queue,
    )
    from pseofactory.verifier import MasterSEOVerifier

    # 1. Reject thin affiliate listicles while preserving statutory comparison calculators
    assert is_thin_affiliate_listicle_candidate("top 10 best crypto tax software in 2026") is True
    assert is_thin_affiliate_listicle_candidate("7 best student loan refinance lenders listicle") is True
    assert is_thin_affiliate_listicle_candidate("section 179 vs bonus depreciation calculator") is False

    verdict_listicle = qualify_search_intent(
        {"query": "10 best tax software apps in 2026", "impressions": 120, "position": 14.0}
    )
    assert verdict_listicle["action"] == "REJECT_LISTICLE_ARCHETYPE"
    assert verdict_listicle.status == "PRUNE"
    assert verdict_listicle["recommended_alternative_archetype"] == "deterministic_statutory_comparison_calculator"

    with pytest.raises(ValueError, match="Thin affiliate listicle"):
        assert_search_intent_qualified({"query": "top 5 student loan refinance companies roundup"})

    with pytest.raises(ValueError, match="Thin affiliate listicle archetype detected"):
        assert_no_thin_affiliate_listicle_archetype("<h1>Top 10 Best Tax Calculators Listicle</h1>")

    vc_listicle = tmp_path / "void_listicle.jsonl"
    vc_listicle.write_text(
        json.dumps({"slug": "top-10-best-tax-software-2026", "query": "top 10 best tax software 2026", "status": "PENDING", "action": "BUILD_PAGE"}) + "\n",
        encoding="utf-8",
    )
    assert reconcile_void_candidates_queue(vc_listicle) == 1
    row_after = json.loads(vc_listicle.read_text(encoding="utf-8").strip())
    assert row_after["status"] == "REJECTED"
    assert row_after["action"] == "REJECT_LISTICLE_ARCHETYPE"

    # 2. Abbreviation-safe sentence counting & 2-sentence upfront query answers
    treasury_qa = _normalize_quick_answer_40_60_words("Treasury Yield Calculator", "profithelm", slug="treasury-yield-calculator")
    assert count_quick_answer_sentences(treasury_qa) == 2
    assert assert_quick_answer_passage_relevance(treasury_qa, max_sentences=2) is True

    insolvency_qa = _normalize_quick_answer_40_60_words(
        "Student Loan Forgiveness Tax Bomb Insolvency Calculator",
        "prexvo",
        slug="student-loan-forgiveness-tax-bomb-insolvency-calculator",
    )
    assert count_quick_answer_sentences(insolvency_qa) == 2
    assert "108(a)(1)(B)" in insolvency_qa
    assert assert_quick_answer_passage_relevance(insolvency_qa, max_sentences=2) is True

    # 3. Distinct, non-truncated meta descriptions for long vehicle spokes and PSLF tools
    meta_silv = _normalize_meta_120_155("", "profithelm", "Chevrolet Silverado 2500HD Section 179")
    meta_espr = _normalize_meta_120_155("", "profithelm", "Mercedes-Benz eSprinter Section 179")
    meta_spr = _normalize_meta_120_155("", "profithelm", "Mercedes-Benz Sprinter 2500 Section 179")
    assert len({meta_silv, meta_espr, meta_spr}) == 3
    for m_txt in (meta_silv, meta_espr, meta_spr):
        assert 120 <= len(m_txt) <= 155
        assert not detect_sentence_truncation_issues(m_txt)

    meta_buyback = _normalize_meta_120_155("", "prexvo", "pslf buyback months reconsideration student loan calculator")
    meta_sim = _normalize_meta_120_155("", "prexvo", "pslf qualifying payment simulator")
    assert meta_buyback != meta_sim
    assert "685.219(g)" in meta_buyback
    assert "685.219(c)" in meta_sim

    # Cross-page duplicate meta description detection in MasterSEOVerifier
    dup_dist = tmp_path / "dup_dist"
    (dup_dist / "page-a").mkdir(parents=True)
    (dup_dist / "page-b").mkdir(parents=True)
    shared_meta = "Calculate federal and state statutory tax obligations using deterministic Internal Revenue Code schedules and verified brackets."
    (dup_dist / "page-a" / "index.html").write_text(
        f'<!DOCTYPE html><html><head><meta name="description" content="{shared_meta}"></head><body></body></html>',
        encoding="utf-8",
    )
    (dup_dist / "page-b" / "index.html").write_text(
        f'<!DOCTYPE html><html><head><meta name="description" content="{shared_meta}"></head><body></body></html>',
        encoding="utf-8",
    )
    v_dup = MasterSEOVerifier(dist_dir=dup_dist)
    gate_dup = v_dup.check_meta_descriptions_gate(require_unique=True)
    assert gate_dup["status"] == "FAIL"
    assert gate_dup["duplicate_meta_descriptions_count"] == 1

    # 4. Prexvo 3-tier topic cluster includes PSLF Buyback, Forgiveness 2026, and Tax Bomb Insolvency
    prexvo_cluster = _resolve_vertical_competitor_content(
        "rap-payment-calculator",
        "prexvo",
        "34 CFR Part 685",
        "https://prexvo.com",
    )
    tier_slugs = {
        s
        for _, items in prexvo_cluster["tier_clusters"]
        for s, _ in items
    }
    assert "pslf-buyback-months-reconsideration-student-loan-calculator" in tier_slugs
    assert "student-loan-forgiveness-2026" in tier_slugs
    assert "student-loan-forgiveness-tax-bomb-insolvency-calculator" in tier_slugs


