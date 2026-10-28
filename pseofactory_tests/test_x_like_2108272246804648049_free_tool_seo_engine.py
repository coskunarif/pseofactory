"""Tests for x-like:2108272246804648049 (@robj3d3) Free Tool SEO & Agentic Keyword Engine upgrades.

Covers:
1. 10-claim capability matrix decomposition, ROI/crawl-risk scoring, and live evaluation.
2. Zero-signup instant-result tool execution contract and statutory acronym hygiene gates.
3. Competitor 'Free Tools' navigation & Top-Pages footprint extractor.
4. Agentic tool-keyword expansion, rankable SERP tool-intent filtering, shared-SERP URL overlap clustering, and ROI/crawl-budget risk scoring across profithelm, prexvo, and gainhelm.
5. Integration into autonomous SEO growth loops (compile_search_opportunity_briefs & investigate_competitor_traffic_spikes).
6. RetroReflectionEngine healing of Calculator Calculator duplication, HowTo JSON-LD redundancy, and statutory acronym casing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pseofactory import (
    X_LIKE_2108272246804648049_CAPABILITY_MATRIX,
    audit_free_tool_seo_and_instant_ux_readiness,
    evaluate_x_like_2108272246804648049_capability_matrix,
)
from pseofactory.competitor import (
    DEFAULT_TENANT_TOOL_DISCOVERY_SEEDS,
    FREE_TOOL_URL_FOOTPRINTS,
    OFF_VERTICAL_CONSUMER_TOOL_PATTERNS,
    cluster_keywords_by_serp_overlap,
    extract_competitor_free_tool_footprints,
    filter_rankable_tool_keywords,
    run_agentic_free_tool_keyword_pipeline,
    score_tool_cluster_roi_and_crawl_risk,
)
from pseofactory.contracts import (
    UNNORMALIZED_STATUTORY_ACRONYM_PATTERNS,
    assert_zero_signup_instant_result_contract,
    detect_zero_signup_instant_result_issues,
    normalize_statutory_acronym_casing,
)
from pseofactory.gsc_remediation import (
    _normalize_title_50_60,
    compile_remediation_overlay_spec,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.seo_growth_loops import (
    compile_search_opportunity_briefs,
    investigate_competitor_traffic_spikes,
)


def test_capability_matrix_structure_and_dispositions() -> None:
    """Verify 10-claim decomposition and disposition counts for x-like:2108272246804648049."""
    assert len(X_LIKE_2108272246804648049_CAPABILITY_MATRIX) == 10
    claim_ids = [c["claim_id"] for c in X_LIKE_2108272246804648049_CAPABILITY_MATRIX]
    assert len(set(claim_ids)) == 10

    dispositions = [c["disposition"] for c in X_LIKE_2108272246804648049_CAPABILITY_MATRIX]
    assert dispositions.count("INTEGRATED_COMPOUNDING_UPGRADE") == 3
    assert dispositions.count("INTEGRATED_DETERMINISTIC_GATE") == 2
    assert dispositions.count("ALREADY_SOLVED_IN_SUBSTRATE") == 3
    assert dispositions.count("REJECTED_BLOAT_OR_OFF_VERTICAL") == 2

    for item in X_LIKE_2108272246804648049_CAPABILITY_MATRIX:
        assert "\u2014" not in json.dumps(item)
        assert "\u2013" not in json.dumps(item)
        if item["disposition"].startswith("INTEGRATED") or item["disposition"] == "ALREADY_SOLVED_IN_SUBSTRATE":
            assert item["algorithmic_roi_score"] >= 85.0
            assert item["crawl_budget_risk_score"] <= 15.0
        else:
            assert item["algorithmic_roi_score"] <= 20.0
            assert item["crawl_budget_risk_score"] >= 90.0


def test_normalize_statutory_acronym_casing_all_tenants() -> None:
    """Verify multi-tenant statutory acronym casing normalization and Calculator deduplication."""
    raw = (
        "2026 Pslf Forgiveness Calculator & Parent Plus Double Consolidation "
        "vs Grad Plus Tcja Sunset and Hipaa / Hitrust / Fedramp / 3pao / C3pao / Cmmc Calculator Calculator"
    )
    normalized = normalize_statutory_acronym_casing(raw)
    assert "PSLF" in normalized
    assert "Parent PLUS" in normalized
    assert "Grad PLUS" in normalized
    assert "TCJA" in normalized
    assert "HIPAA" in normalized
    assert "HITRUST" in normalized
    assert "FedRAMP" in normalized
    assert "3PAO" in normalized
    assert "C3PAO" in normalized
    assert "CMMC" in normalized
    assert "Calculator Calculator" not in normalized
    for pat, label in UNNORMALIZED_STATUTORY_ACRONYM_PATTERNS:
        assert not pat.search(normalized), f"Pattern {label} still matched in: {normalized}"


def test_gsc_remediation_title_and_overlay_hygiene() -> None:
    """Verify gsc_remediation normalizes statutory acronyms and prevents Calculator Calculator."""
    title = _normalize_title_50_60(
        "Hipaa vs Hitrust Audit Cost Calculator Calculator for 3pao & Cmmc",
        "GainHelm",
        "gainhelm",
    )
    assert "HIPAA" in title
    assert "HITRUST" in title
    assert "Calculator Calculator" not in title

    spec = compile_remediation_overlay_spec(
        candidate={
            "slug": "pslf-for-physicians-calculator",
            "query": "pslf calculator for parent plus and grad plus",
            "grouped_queries": ["pslf calculator", "parent plus vs grad plus idr calculator"],
        },
        tenant_id="prexvo",
    )
    serialized = json.dumps(spec)
    assert "Pslf" not in serialized
    assert "Parent Plus" not in serialized
    assert "Grad Plus" not in serialized
    assert "Calculator Calculator" not in serialized


def test_zero_signup_instant_result_contract_positive_and_negative() -> None:
    """Verify zero-signup instant-result UX & title/schema hygiene contract."""
    clean_tool_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>2026 PSLF Buyback &amp; IDR Calculator | Prexvo</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebApplication",
        "name": "2026 PSLF Buyback & IDR Calculator",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
      },
      {
        "@type": "HowTo",
        "name": "How to Calculate 2026 PSLF Buyback & IDR",
        "description": "Step-by-step instructions to calculate 2026 PSLF Buyback & IDR."
      }
    ]
  }
  </script>
</head>
<body>
  <main>
    <h1>2026 PSLF Buyback &amp; IDR Calculator</h1>
    <form id="calc-form">
      <input type="number" name="loan_balance" value="185000" />
      <output id="res-monthly-payment" class="output-value">$645/mo</output>
    </form>
  </main>
</body>
</html>"""
    assert detect_zero_signup_instant_result_issues(clean_tool_html, require_ssr_output=True) == []
    assert_zero_signup_instant_result_contract(clean_tool_html, require_ssr_output=True)

    violating_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>2026 Pslf Buyback &amp; Parent Plus Calculator Calculator | Prexvo</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "HowTo",
    "name": "How to Calculate 2026 Pslf Buyback Calculator",
    "description": "Step-by-step instructions to calculate 2026 Pslf Buyback Calculator."
  }
  </script>
</head>
<body>
  <main>
    <h1>2026 Pslf Buyback &amp; Hipaa Calculator Calculator</h1>
    <form id="calc-form" data-paywall="true">
      <input type="email" name="user_email" required />
      <input type="password" name="user_password" />
    </form>
  </main>
</body>
</html>"""
    issues = detect_zero_signup_instant_result_issues(violating_html, require_ssr_output=True)
    assert any("forbidden password input" in i for i in issues)
    assert any("forbidden signup/paywall gate" in i for i in issues)
    assert any("required email input" in i for i in issues)
    assert any("Missing instant server-rendered baseline output" in i for i in issues)
    assert any("duplicate 'Calculator Calculator'" in i for i in issues)
    assert any("redundant 'How to Calculate ... Calculator'" in i for i in issues)
    assert any("unnormalized statutory acronym" in i for i in issues)

    with pytest.raises(ValueError, match="Zero-signup instant-result tool contract violation"):
        assert_zero_signup_instant_result_contract(violating_html, require_ssr_output=True)


def test_competitor_free_tool_footprint_extraction_and_pipeline() -> None:
    """Verify Steps 1-8 of the Agentic Free-Tool Keyword Discovery & Clustering Pipeline."""
    assert len(FREE_TOOL_URL_FOOTPRINTS) >= 8
    assert len(OFF_VERTICAL_CONSUMER_TOOL_PATTERNS) >= 7
    assert set(DEFAULT_TENANT_TOOL_DISCOVERY_SEEDS.keys()) == {"profithelm", "prexvo", "gainhelm"}

    # Step 1-2: Extract competitor free-tool footprints and reject off-vertical consumer bloat
    sample_competitor_pages = [
        {
            "domain": "competitor.example.com",
            "url": "https://competitor.example.com/tools/section-179-calculator",
            "tool_title": "Section 179 Deduction Calculator",
            "organic_traffic": 1400,
            "in_top_nav_free_tools": True,
        },
        {
            "domain": "competitor.example.com",
            "url": "https://competitor.example.com/free-tools/s-corp-tax-estimator",
            "tool_title": "Free S-Corp Tax Estimator",
            "organic_traffic": 920,
            "in_top_nav_free_tools": True,
        },
        {
            "domain": "superx.so",
            "url": "https://superx.so/tools/twitter-video-downloader",
            "tool_title": "Twitter Video Downloader",
            "organic_traffic": 15000,
        },
        {
            "domain": "canivibecodeit.com",
            "url": "https://canivibecodeit.com/alternatives/clone",
            "tool_title": "Can I Vibe Code It Clone",
            "organic_traffic": 50,
        },
        {
            "domain": "competitor.example.com",
            "url": "https://competitor.example.com/blog/what-is-accounting",
            "tool_title": "What is Accounting Guide",
            "organic_traffic": 300,
        },
    ]
    footprints = extract_competitor_free_tool_footprints(
        competitor_pages=sample_competitor_pages,
        tenant_id="profithelm",
    )
    assert footprints["qualified_count"] == 2
    assert footprints["rejected_count"] == 3
    urls = [f["url"] for f in footprints["qualified_tool_pages"]]
    assert "https://competitor.example.com/tools/section-179-calculator" in urls
    assert "https://competitor.example.com/free-tools/s-corp-tax-estimator" in urls

    # Step 3-5: Filter rankable tool keywords (reject high-KD, non-tool SERPs, video/news SERPs, off-vertical)
    candidates = [
        {
            "keyword": "section 179 deduction calculator",
            "position": 4,
            "volume": 3200,
            "traffic": 850,
            "kd": 22.0,
            "tool_results_in_top10": 6,
            "avg_top10_dr": 48.0,
            "serp_dominant_format": "interactive_tool",
            "top10_urls": [
                "https://www.section179.org/section_179_calculator/",
                "https://www.crestcapital.com/section-179-calculator",
            ],
        },
        {
            "keyword": "bonus depreciation section 179 calculator",
            "position": 6,
            "volume": 1400,
            "traffic": 390,
            "kd": 20.0,
            "tool_results_in_top10": 5,
            "avg_top10_dr": 46.0,
            "serp_dominant_format": "interactive_tool",
            "top10_urls": [
                "https://www.section179.org/section_179_calculator/",
                "https://www.crestcapital.com/section-179-calculator",
            ],
        },
        {
            "keyword": "twitter video downloader free",
            "position": 2,
            "volume": 45000,
            "kd": 10.0,
            "tool_results_in_top10": 8,
            "avg_top10_dr": 35.0,
        },
        {
            "keyword": "impossible high kd calculator",
            "position": 3,
            "volume": 5000,
            "kd": 78.0,
            "tool_results_in_top10": 4,
            "avg_top10_dr": 85.0,
        },
        {
            "keyword": "breaking tax news video",
            "position": 5,
            "volume": 400,
            "kd": 12.0,
            "serp_dominant_format": "video",
            "tool_results_in_top10": 3,
        },
    ]
    filter_res = filter_rankable_tool_keywords(candidates, tenant_id="profithelm", tenant_dr=28.0)
    assert filter_res["surviving_count"] == 2
    assert filter_res["dropped_count"] == 3

    # Step 6: Cluster by shared SERP URL overlap (single build brief for overlapping keywords)
    clusters = cluster_keywords_by_serp_overlap(filter_res["surviving_keywords"], tenant_id="profithelm")
    assert len(clusters) == 1
    assert clusters[0]["keywords_count"] == 2
    assert clusters[0]["combined_volume"] == 3200 + 1400

    # Step 7-8: Score ROI and crawl-budget risk
    scored = score_tool_cluster_roi_and_crawl_risk(clusters[0], tenant_id="profithelm")
    assert scored["recommended_action"] in ("BUILD_NEW_CANONICAL_TOOL", "UPGRADE_EXISTING_CANONICAL_TOOL")
    assert scored["algorithmic_roi_score"] >= 60.0
    assert scored["crawl_budget_risk_score"] <= 25.0
    assert "zero-signup instant-result" in scored["what_to_build"]

    # Full pipeline execution across all 3 tenants
    for prop in ("profithelm", "prexvo", "gainhelm"):
        pipe = run_agentic_free_tool_keyword_pipeline(tenant_id=prop)
        assert pipe["status"] == "PASS"
        assert pipe["property_id"] == prop
        assert pipe["ranked_clusters_count"] >= 1
        assert len(pipe["top_build_briefs"]) >= 1
        for brief in pipe["top_build_briefs"]:
            assert brief["algorithmic_roi_score"] >= 60.0
            assert brief["crawl_budget_risk_score"] <= 25.0


def test_seo_growth_loops_agentic_tool_integration() -> None:
    """Verify compile_search_opportunity_briefs and investigate_competitor_traffic_spikes expose agentic tool briefs."""
    briefs = compile_search_opportunity_briefs(
        property_id="prexvo",
        apply_overlays=False,
        persist=False,
    )
    assert briefs["agentic_free_tool_clusters_count"] >= 1
    assert len(briefs["agentic_free_tool_build_briefs"]) >= 1

    spikes = investigate_competitor_traffic_spikes(
        property_id="gainhelm",
        persist=False,
    )
    assert spikes["agentic_free_tool_clusters_count"] >= 1
    assert len(spikes["agentic_free_tool_build_briefs"]) >= 1


def test_retro_reflection_heals_title_howto_and_acronyms(tmp_path: Path) -> None:
    """Verify RetroReflectionEngine deterministically heals Calculator Calculator, HowTo redundancy, and acronym casing."""
    dist_dir = tmp_path / "dist"
    page_dir = dist_dir / "tools" / "pslf-calculator"
    page_dir.mkdir(parents=True)

    dirty_html = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>2026 Pslf &amp; Parent Plus Calculator Calculator | Prexvo</title>
  <meta property="og:title" content="2026 Pslf &amp; Parent Plus Calculator Calculator | Prexvo" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "HowTo",
        "name": "How to Calculate 2026 Pslf & Parent Plus Calculator",
        "description": "Step-by-step instructions to calculate 2026 Pslf & Parent Plus Calculator."
      }
    ]
  }
  </script>
</head>
<body>
  <main>
    <h1>2026 Pslf &amp; Parent Plus Calculator Calculator</h1>
    <form id="calc">
      <input type="number" name="balance" value="200000" />
      <output id="res-monthly-payment" class="output-value">$820/mo</output>
    </form>
  </main>
</body>
</html>"""
    html_file = page_dir / "index.html"
    html_file.write_text(dirty_html, encoding="utf-8")

    RetroReflectionEngine.retrofit_estate(dist_dir, property_id="prexvo")
    healed = html_file.read_text(encoding="utf-8")
    assert "Calculator Calculator" not in healed
    assert "Pslf" not in healed
    assert "Parent Plus" not in healed
    assert "PSLF" in healed
    assert "Parent PLUS" in healed
    assert "How to Calculate 2026 PSLF & Parent PLUS Calculator" not in healed
    assert detect_zero_signup_instant_result_issues(healed, require_ssr_output=True) == []


def test_live_capability_matrix_and_tenant_readiness() -> None:
    """Verify evaluate_x_like_2108272246804648049_capability_matrix passes across live compiled tenants."""
    report = evaluate_x_like_2108272246804648049_capability_matrix(include_live_tenant_check=True)
    assert report["status"] == "PASS"
    assert report["passed"] is True
    assert report["total_claims_evaluated"] == 10
    for tenant_id, tenant_rep in report["tenant_readiness"].items():
        assert tenant_rep["status"] == "PASS", f"Tenant {tenant_id} failed readiness: {tenant_rep['issues']}"
        assert tenant_rep["issues_count"] == 0
        assert tenant_rep["tool_pages_scanned"] >= 10
