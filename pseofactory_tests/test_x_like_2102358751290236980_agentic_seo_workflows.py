from pathlib import Path
from typing import Dict

from pseofactory.audit import (
    X_LIKE_2102358751290236980_CAPABILITY_MATRIX,
    evaluate_x_like_2102358751290236980_capability_matrix,
)
from pseofactory.seo_growth_loops import (
    compile_ai_citation_digital_pr_queue,
    compile_search_opportunity_briefs,
    compile_technical_seo_sprint,
    discover_internal_linking_opportunities,
    evaluate_content_portfolio_decisions,
    identify_content_decay,
    investigate_competitor_traffic_spikes,
    monitor_post_release_seo_regressions,
)


def _write_html(path: Path, title: str, h1: str, body_links: str = "", noindex: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    robots_tag = '<meta name="robots" content="noindex, nofollow">' if noindex else '<meta name="robots" content="index, follow">'
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="description" content="{title} interactive statutory calculator and 2026 schedule.">
  {robots_tag}
  <link rel="canonical" href="https://profithelm.com/">
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebApplication","name":"{title}"}}</script>
</head>
<body>
  <header><nav><a href="/">Home</a><a href="/tools/">Tools</a></nav></header>
  <main>
    <h1>{h1}</h1>
    <p>Deterministic statutory model.</p>
    {body_links}
  </main>
  <footer><a href="/privacy/">Privacy</a></footer>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")


def test_x_like_2102358751290236980_capability_matrix_completeness() -> None:
    assert len(X_LIKE_2102358751290236980_CAPABILITY_MATRIX) == 8
    workflow_ids = [item["workflow_id"] for item in X_LIKE_2102358751290236980_CAPABILITY_MATRIX]
    assert workflow_ids == [1, 2, 3, 4, 5, 6, 7, 8]
    for item in X_LIKE_2102358751290236980_CAPABILITY_MATRIX:
        assert item["disposition"] == "INTEGRATED_COMPOUNDING_UPGRADE"
        assert "\u2014" not in str(item)
        assert "\u2013" not in str(item)

    res = evaluate_x_like_2102358751290236980_capability_matrix(include_live_workflows_check=False)
    assert res["pointer"] == "x-like:2102358751290236980"
    assert res["tweet_id"] == "2102358751290236980"
    assert res["author_handle"] == "semrush"
    assert res["total_workflows_evaluated"] == 8
    assert res["integrated_compounding_upgrades_count"] == 8
    assert res["passed"] is True


def test_workflow_5_topical_cluster_affinity_donor_scoring(tmp_path: Path) -> None:
    repo_root = tmp_path / "profithelm_topical"
    dist_dir = repo_root / "dist"
    _write_html(
        dist_dir / "index.html",
        "ProfitHelm Tax & Financial Calculators",
        "ProfitHelm Calculators",
        '<a href="/tools/">Tools</a><a href="/tools/crypto-tax-calculator/">Crypto Tax</a>',
    )
    _write_html(
        dist_dir / "tools" / "index.html",
        "All Financial & Tax Calculators",
        "Financial Calculators Directory",
        (
            '<a href="/tools/crypto-tax-calculator/">Crypto Tax Calculator</a>'
            '<a href="/tools/irs-2027-tax-brackets/">IRS 2027 Tax Brackets</a>'
            '<a href="/tools/section-1031-calculator/">Section 1031 Exchange Calculator</a>'
            '<a href="/tools/1031-boot-calculator/">1031 Boot Calculator</a>'
        ),
    )
    # Give crypto-tax-calculator and irs-2027-tax-brackets higher global inbound links
    _write_html(
        dist_dir / "tools" / "crypto-tax-calculator" / "index.html",
        "Crypto Tax Calculator",
        "Crypto Tax Calculator",
        '<a href="/tools/irs-2027-tax-brackets/">2027 Tax Brackets</a>',
    )
    _write_html(
        dist_dir / "tools" / "irs-2027-tax-brackets" / "index.html",
        "IRS 2027 Tax Brackets Calculator",
        "IRS 2027 Tax Brackets Calculator",
        '<a href="/tools/crypto-tax-calculator/">Crypto Tax Calculator</a>',
    )
    _write_html(
        dist_dir / "tools" / "section-1031-calculator" / "index.html",
        "Section 1031 Exchange Calculator",
        "Section 1031 Exchange Calculator",
        '<a href="/tools/1031-boot-calculator/">1031 Boot Calculator</a>',
    )
    _write_html(
        dist_dir / "tools" / "1031-boot-calculator" / "index.html",
        "1031 Exchange Boot & Depreciation Recapture Calculator",
        "1031 Boot Calculator",
        '<a href="/tools/section-1031-calculator/">Section 1031 Exchange Calculator</a>',
    )
    # Underlinked 1031 Ohio spoke
    _write_html(
        dist_dir / "tools" / "section-1031-calculator" / "ohio" / "index.html",
        "Ohio 1031 Exchange Calculator",
        "Ohio 1031 Exchange Calculator",
        '<a href="/tools/section-1031-calculator/">Section 1031 Hub</a>',
    )

    gsc_bundle: Dict[str, object] = {
        "current_rows": [
            {
                "query": "1031 exchange ohio",
                "canonical_path": "/tools/section-1031-calculator/ohio",
                "canonical_url": "https://profithelm.com/tools/section-1031-calculator/ohio/",
                "impressions": 25,
                "clicks": 0,
                "position": 9.2,
            },
            {
                "query": "crypto tax calculator",
                "canonical_path": "/tools/crypto-tax-calculator",
                "canonical_url": "https://profithelm.com/tools/crypto-tax-calculator/",
                "impressions": 200,
                "clicks": 15,
                "position": 4.1,
            },
        ],
        "impressions_by_path": {
            "/tools/section-1031-calculator/ohio": 25,
            "/tools/crypto-tax-calculator": 200,
            "/tools/irs-2027-tax-brackets": 150,
            "/tools/section-1031-calculator": 40,
            "/tools/1031-boot-calculator": 30,
        },
        "clicks_by_path": {"/tools/crypto-tax-calculator": 15},
    }

    rep = discover_internal_linking_opportunities(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        persist=False,
    )
    ohio_opp = next(o for o in rep["opportunities"] if o["target_path"] == "/tools/section-1031-calculator/ohio/")
    donors = ohio_opp["recommended_source_hubs"]
    assert "/tools/section-1031-calculator/" in donors
    assert "/tools/1031-boot-calculator/" in donors
    assert "/tools/crypto-tax-calculator/" not in donors
    assert len(ohio_opp["anchor_variants"]) == 3
    assert len(set(ohio_opp["anchor_variants"])) >= 2
    details = ohio_opp["recommended_donor_details"]
    assert details[0]["fit_strength"] == "Strong"
    assert details[0]["source_path"] == "/tools/section-1031-calculator/"


def test_workflow_7_source_influence_scoring_and_no_outreach_separation(tmp_path: Path) -> None:
    repo_root = tmp_path / "profithelm_pr"
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "llms.txt").write_text("# ProfitHelm\n", encoding="utf-8")
    (dist_dir / "llms-full.txt").write_text("# ProfitHelm Full\n", encoding="utf-8")

    gsc_bundle = {
        "current_rows": [
            {
                "query": "section 179 deduction calculator 2026",
                "canonical_path": "/tools/section-179-calculator",
                "canonical_url": "https://profithelm.com/tools/section-179-calculator/",
                "impressions": 45,
                "clicks": 0,
                "position": 8.4,
            }
        ],
        "baseline_rows": [],
    }
    rep = compile_ai_citation_digital_pr_queue(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        persist=False,
    )
    assert rep["status"] == "PASS"
    assert rep["no_outreach_sources_count"] >= 1
    no_outreach_domains = {s["domain"] for s in rep["no_outreach_sources"]}
    assert "irs.gov" in no_outreach_domains or "reddit.com" in no_outreach_domains

    first_item = rep["queue"][0]
    assert "irs.gov" in first_item["no_outreach_domains"]
    assert "reddit.com" in first_item["community_experience_domains"]
    assert "irs.gov" not in first_item["pitchable_outreach_targets"]
    assert "reddit.com" not in first_item["pitchable_outreach_targets"]


def test_workflows_1_2_3_4_6_8_enriched_mechanisms(tmp_path: Path) -> None:
    repo_root = tmp_path / "profithelm_all"
    dist_dir = repo_root / "dist"
    _write_html(
        dist_dir / "index.html",
        "ProfitHelm Financial Calculators",
        "ProfitHelm",
        '<a href="/tools/section-179-calculator/">Section 179</a>',
    )
    _write_html(
        dist_dir / "tools" / "index.html",
        "Tools Directory",
        "Tools Directory",
        '<a href="/tools/section-179-calculator/">Section 179 Calculator</a>',
    )
    _write_html(
        dist_dir / "tools" / "section-179-calculator" / "index.html",
        "Section 179 Tax Deduction Calculator 2026",
        "Section 179 Tax Deduction Calculator",
        '<a href="/tools/">Tools</a>',
    )
    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    gsc_bundle = {
        "earliest_snapshot_id": "2026-09-01",
        "latest_snapshot_id": "2026-10-01",
        "baseline_rows": [
            {
                "query": "section 179 calculator",
                "canonical_path": "/tools/section-179-calculator",
                "canonical_url": "https://profithelm.com/tools/section-179-calculator/",
                "impressions": 40,
                "clicks": 4,
                "ctr": 0.10,
                "position": 7.5,
            }
        ],
        "current_rows": [
            {
                "query": "section 179 calculator",
                "canonical_path": "/tools/section-179-calculator",
                "canonical_url": "https://profithelm.com/tools/section-179-calculator/",
                "impressions": 50,
                "clicks": 0,
                "ctr": 0.0,
                "position": 12.4,
            }
        ],
        "impressions_by_path": {"/tools/section-179-calculator": 50},
        "clicks_by_path": {"/tools/section-179-calculator": 0},
        "redirect_rollup_summary": {
            "redirected_rows_count": 1,
            "rolled_up_impressions": 10,
            "rolled_up_clicks": 1,
        },
    }

    decay_rep = identify_content_decay(
        property_id="profithelm",
        repo_root=repo_root,
        consolidated_gsc=gsc_bundle,
        persist=False,
    )
    assert decay_rep["total_decaying_queries"] == 1
    cand = decay_rep["decay_candidates"][0]
    assert cand["decay_type"] == "PAGE_1_DROPOUT"
    assert cand["decline_taxonomy_cause"] == "COMPETITOR_REPLACED_PAGE"
    assert cand["indexation_checked_first"] is True
    assert cand["indexation_status"] == "INDEXED_OK"
    assert cand["fixability_weight"] > 1.0
    assert cand["confidence"] == "High"
    assert "Indexation=INDEXED_OK" in cand["supporting_evidence"]

    briefs_rep = compile_search_opportunity_briefs(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        apply_overlays=False,
        persist=False,
    )
    b0 = briefs_rep["briefs"][0]
    assert b0["coverage_decision"] == "UPDATE"
    assert "what_ranking_pages_omit" in b0["differentiation_angle"]
    assert len(b0["claims_requiring_verification"]) >= 1

    portfolio_rep = evaluate_content_portfolio_decisions(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        decay_report=decay_rep,
        persist=False,
    )
    d0 = next(d for d in portfolio_rep["decisions"] if d["url_path"] == "/tools/section-179-calculator")
    assert d0["matched_rule"] == "R2_REFRESH_HISTORICAL_DECAY"
    assert d0["destination_validation"]["target_exists_in_dist"] is True

    spike_rep = investigate_competitor_traffic_spikes(
        property_id="profithelm",
        repo_root=repo_root,
        consolidated_gsc=gsc_bundle,
        persist=False,
    )
    assert len(spike_rep["investigations"]) >= 1
    inv0 = spike_rep["investigations"][0]
    assert inv0["likely_driver"] in (
        "CONTENT_REFRESH_AND_STATUTORY_TIMELINESS",
        "SERP_FEATURE_CAPTURE_AND_INTERACTIVE_TOOL_DEPTH",
        "SEASONAL_OR_REGULATORY_DEMAND_SURGE",
    )
    assert inv0["branded_vs_non_branded"] == "NON_BRANDED_COMMERCIAL_TOOL"
    assert inv0["recommended_response"] in ("counter_immediately", "queue_for_roadmap")

    mon_rep = monitor_post_release_seo_regressions(
        property_id="profithelm",
        repo_root=repo_root,
        consolidated_gsc=gsc_bundle,
        decay_report=decay_rep,
        persist=False,
    )
    assert mon_rep["crawl_structural_audit"]["status"] == "PASS"
    assert mon_rep["p0_sitewide_blockers_count"] == 0
    assert mon_rep["route_regressions"][0]["change_classification"] == "UNPLANNED"
    assert "acceptance_criteria" in mon_rep["route_regressions"][0]

    sprint_rep = compile_technical_seo_sprint(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        decay_report=decay_rep,
        briefs_report=briefs_rep,
        portfolio_report=portfolio_rep,
        regression_report=mon_rep,
        persist=False,
    )
    assert sprint_rep["root_cause_groups_count"] >= 1
    assert len(sprint_rep["fix_dependencies"]) == 4
    assert len(sprint_rep["excluded_low_value_items"]) >= 2
    for t in sprint_rep["tickets"]:
        assert t["fix_type"] in ("template", "page", "configuration", "infrastructure", "investigative")
        assert "acceptance_criteria" in t
