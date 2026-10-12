"""
Unit tests for Factor 14: Keyword Content Angle Discovery Capability.
Verifies:
1. test_factor_14_prompt_schema_and_punctuation: Schema, dividers, Jev scores, zero dashes, zero leakage.
2. test_keyword_content_angles_fixture_integrity: 4 scenarios with valid schema and required keys.
3. test_content_angles_search_intent_triage: Search Intent Doctrine triage across 4 fixture scenarios.
4. test_underdog_angle_divergence_oracle: Jaccard divergence oracle and mathematical bounds.
5. test_underdog_angle_rejects_derivative_clones: Rejection of derivative copy and invalid Grant O triads.
6. test_content_angle_brief_generation_contracts: Anti-slop punctuation and prompt leakage contracts on briefs.

Zero em-dashes. Zero en-dashes.
"""

import json
import os
import re
import pytest

from pseofactory.contracts import assert_no_forbidden_dashes, assert_no_prompt_leakage
from pseofactory.content_angles import (
    GrantOTriad,
    IncumbentSummary,
    UnderdogAngle,
    ContentAngleBrief,
    calculate_token_jaccard_divergence,
    assert_underdog_angle_divergence,
    evaluate_content_angles,
    generate_markdown_brief,
    VALID_UNDERDOG_ARCHETYPES,
    SERP_WEAKNESS_CATEGORIES,
    UGC_FORUM_DOMAINS,
    classify_serp_incumbent,
    classify_serp_incumbents,
)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FACTOR_14_PROMPT_PATH = os.path.join(REPO_ROOT, "prompts", "14_keyword_content_angle_discovery.md")
FIXTURE_PATH = os.path.join(REPO_ROOT, "pseofactory", "fixtures", "keyword_content_angles_fixture.json")


def test_factor_14_prompt_schema_and_punctuation():
    """Validates Factor 14 prompt file exists, matches schema, and passes contracts."""
    assert os.path.isfile(FACTOR_14_PROMPT_PATH), f"Missing Factor 14 prompt at {FACTOR_14_PROMPT_PATH}"

    with open(FACTOR_14_PROMPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Punctuation and prompt leakage contracts
    assert_no_forbidden_dashes(content, "Factor 14 Prompt")
    assert_no_prompt_leakage(content, "Factor 14 Prompt")

    # 2. Top-level H1 header
    assert content.startswith("# Factor 14: Keyword Content Angle Discovery (+1.75)")

    # 3. Execution prompt section
    assert "## Execution Prompt (Jev Score: 1.55)" in content

    # 4. Raw prompt output section with invariant notice
    assert "## Raw Prompt Output" in content
    assert "```text" in content
    assert "Assumed: Standing decision enforces zero em-dashes and zero en-dashes across all pseofactory code and text assets." in content

    # 5. Exactly 3 parallel prompts with Jev scores
    dividers = re.findall(r"── Prompt \d · Jev Score: \d\.\d\d ──+", content)
    assert len(dividers) == 3, f"Expected exactly 3 prompt dividers, found {len(dividers)}"

    scores = re.findall(r"Jev Score: (1\.\d\d)", content)
    # Execution prompt header has 1.55, raw prompts have 1.55, 1.52, 1.48
    expected_scores = ["1.55", "1.55", "1.52", "1.48"]
    assert scores == expected_scores, f"Expected scores {expected_scores}, found {scores}"


def test_keyword_content_angles_fixture_integrity():
    """Validates JSON schema, completeness, and non-empty values across 4 test scenarios."""
    assert os.path.isfile(FIXTURE_PATH), f"Missing fixture file at {FIXTURE_PATH}"

    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()
        fixtures = json.loads(raw_text)

    # Contract checks on fixture json
    assert_no_forbidden_dashes(raw_text, "keyword_content_angles_fixture")
    assert_no_prompt_leakage(raw_text, "keyword_content_angles_fixture")

    assert isinstance(fixtures, list)
    assert len(fixtures) == 4

    required_scenario_keys = [
        "fixture_id",
        "query",
        "market_segment",
        "search_intent",
        "gsc_metrics",
        "incumbents",
        "existing_site_catalog",
        "expected_triage_action",
        "underdog_angle_specs",
    ]

    expected_ids = {
        "b2b_saas_fleet_dispatch_underdog",
        "fintech_section_179_cannibalization_trap",
        "exploratory_impression_monitor_trap",
        "local_service_cold_chain_underdog",
    }
    found_ids = {f["fixture_id"] for f in fixtures}
    assert found_ids == expected_ids

    for fx in fixtures:
        for k in required_scenario_keys:
            assert k in fx, f"Fixture {fx.get('fixture_id')} missing key '{k}'"
            assert fx[k] is not None

        # Validate gsc_metrics
        gsc = fx["gsc_metrics"]
        for gk in ["impressions", "clicks", "position", "days_observed"]:
            assert gk in gsc
            assert isinstance(gsc[gk], (int, float))

        # Validate incumbents
        assert isinstance(fx["incumbents"], list)
        for inc in fx["incumbents"]:
            for ik in ["domain", "rank", "title", "weakness_category", "weakness_detail"]:
                assert ik in inc
                assert len(str(inc[ik]).strip()) > 0

        # Validate underdog angle specs
        assert isinstance(fx["underdog_angle_specs"], list)
        assert len(fx["underdog_angle_specs"]) >= 1
        for angle in fx["underdog_angle_specs"]:
            for ak in [
                "angle_id",
                "target_audience_niche",
                "problem_scope",
                "geographic_or_vertical_bound",
                "primary_value_proposition",
                "first_party_utility_asset",
                "divergence_score_min",
            ]:
                assert ak in angle
                assert len(str(angle[ak]).strip()) > 0


def test_content_angles_search_intent_triage():
    """Validates Search Intent Doctrine qualification triage across all 4 scenarios."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    fixture_map = {f["fixture_id"]: f for f in fixtures}

    # Scenario 1: B2B SaaS Underdog -> BUILD_PAGE
    b2b = fixture_map["b2b_saas_fleet_dispatch_underdog"]
    brief_b2b = evaluate_content_angles(b2b, total_site_impressions=500)
    assert brief_b2b.triage_action == "BUILD_PAGE"
    assert brief_b2b.candidate_spec is not None
    assert brief_b2b.candidate_spec["status"] == "PENDING"
    assert len(brief_b2b.angles) == 1
    assert brief_b2b.angles[0].divergence_score >= 0.55

    # Scenario 2: Fintech Section 179 Cannibalization Trap -> REFACTOR_PAGE
    fintech = fixture_map["fintech_section_179_cannibalization_trap"]
    brief_fintech = evaluate_content_angles(fintech, total_site_impressions=500)
    assert brief_fintech.triage_action == "REFACTOR_PAGE"
    assert brief_fintech.overlay_spec is not None
    assert brief_fintech.overlay_spec["slug"] == "section-179-calculator"
    assert brief_fintech.overlay_spec["measurement_lock_days"] == 28
    assert "locked_until" in brief_fintech.overlay_spec
    assert len(brief_fintech.angles) == 1

    # Scenario 3: Exploratory Impression Trap -> MONITOR
    exploratory = fixture_map["exploratory_impression_monitor_trap"]
    brief_exp = evaluate_content_angles(exploratory, total_site_impressions=500)
    assert brief_exp.triage_action == "MONITOR"
    assert "qualification floor" in brief_exp.evaluation_summary.lower()

    # Scenario 4: Local Service Cold Chain Underdog -> BUILD_PAGE
    local = fixture_map["local_service_cold_chain_underdog"]
    brief_local = evaluate_content_angles(local, total_site_impressions=500)
    assert brief_local.triage_action == "BUILD_PAGE"
    assert brief_local.candidate_spec is not None
    assert len(brief_local.angles) == 1
    assert brief_local.angles[0].divergence_score >= 0.60


def test_underdog_angle_divergence_oracle():
    """Validates token Jaccard divergence calculation and mathematical bounds."""
    # 1. Identical copy gives divergence 0.0
    cand_identical = "commercial walk-in freezer compressor replacement austin tx"
    inc_identical = ["commercial walk-in freezer compressor replacement austin tx"]
    div_identical = calculate_token_jaccard_divergence(cand_identical, inc_identical)
    assert div_identical == 0.0

    # 2. Completely distinct vocabulary gives divergence 1.0
    cand_distinct = "quantum algorithmic arbitrage matrix"
    inc_distinct = ["residential kitchen plumbing unclogging service"]
    div_distinct = calculate_token_jaccard_divergence(cand_distinct, inc_distinct)
    assert div_distinct == 1.0

    # 3. Empty candidate text gives 0.0
    assert calculate_token_jaccard_divergence("", inc_distinct) == 0.0

    # 4. Empty incumbent list gives 1.0
    assert calculate_token_jaccard_divergence(cand_distinct, []) == 1.0

    # 5. Fixture validation across competitive scenarios
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    for fx in fixtures:
        if fx["expected_triage_action"] == "BUILD_PAGE":
            inc_titles = [inc["title"] for inc in fx["incumbents"]]
            for angle in fx["underdog_angle_specs"]:
                prop = angle["primary_value_proposition"]
                div = calculate_token_jaccard_divergence(prop, inc_titles)
                assert div >= angle["divergence_score_min"]
                assert div >= 0.50


def test_underdog_angle_rejects_derivative_clones():
    """Validates that derivative copy and invalid Grant O triads raise ValueError."""
    incumbent_titles = [
        "Enterprise Field Service Management Software",
        "HVAC Software & App for Contractors",
    ]

    # 1. Derivative clone copying incumbent vocabulary fails divergence check
    clone_prop = "Enterprise Field Service Management Software for HVAC Contractors"
    with pytest.raises(ValueError, match="Derivative clone rejected"):
        assert_underdog_angle_divergence(clone_prop, incumbent_titles, min_threshold=0.50)

    # 2. Grant O Triad rejects empty audience niche
    with pytest.raises(ValueError, match="audience niche"):
        GrantOTriad(
            audience_niche="",
            problem_scope="Two-way dispatch calendar sync",
            geographic_or_vertical_bound="Residential HVAC",
        )

    # 3. Grant O Triad rejects empty problem scope
    with pytest.raises(ValueError, match="problem scope"):
        GrantOTriad(
            audience_niche="2-person HVAC technicians",
            problem_scope="",
            geographic_or_vertical_bound="Residential HVAC",
        )

    # 4. Grant O Triad rejects empty geographic or vertical bound
    with pytest.raises(ValueError, match="geographic or vertical bound"):
        GrantOTriad(
            audience_niche="2-person HVAC technicians",
            problem_scope="Two-way dispatch calendar sync",
            geographic_or_vertical_bound="   ",
        )

    # 5. evaluate_content_angles rejects candidate angle with clone copy for BUILD_PAGE
    clone_angle_spec = {
        "angle_id": "derivative_clone_angle",
        "target_audience_niche": "Contractors",
        "problem_scope": "Field service software",
        "geographic_or_vertical_bound": "North America",
        "primary_value_proposition": "Enterprise Field Service Management Software for Contractors",
        "first_party_utility_asset": "None",
        "divergence_score_min": 0.50,
    }

    b2b_scenario_with_clone = {
        "query": "field service dispatch software for 2 person hvac team",
        "gsc_metrics": {"position": 14.2, "impressions": 68, "days_observed": 45, "clicks": 4},
        "incumbents": [
            {"domain": "servicetitan.com", "rank": 1, "title": "Enterprise Field Service Management Software", "weakness_category": "gate", "weakness_detail": "enterprise"}
        ],
        "existing_site_catalog": [],
        "underdog_angle_specs": [clone_angle_spec],
    }

    with pytest.raises(ValueError, match="below 0.50 minimum"):
        evaluate_content_angles(b2b_scenario_with_clone, total_site_impressions=500)


def test_content_angle_brief_generation_contracts():
    """Validates markdown briefs satisfy zero forbidden dashes and zero prompt leakage."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    for fx in fixtures:
        brief = evaluate_content_angles(fx, total_site_impressions=500)
        markdown = brief.to_markdown()

        # Contract assertions
        assert_no_forbidden_dashes(markdown, f"Brief for {fx['fixture_id']}")
        assert_no_prompt_leakage(markdown, f"Brief for {fx['fixture_id']}")

        # Structural assertions
        assert f"# Content Angle Brief: {fx['query']}" in markdown
        assert "## Search Intent Doctrine Triage" in markdown
        assert f"- Triage Action: {fx['expected_triage_action']}" in markdown

        if fx["expected_triage_action"] == "REFACTOR_PAGE":
            assert "## Refactoring Overlay Specification" in markdown
            assert "- Measurement Lock: 28 days" in markdown

        if fx["expected_triage_action"] == "BUILD_PAGE":
            assert "## Underdog Angles (Grant O Triad)" in markdown
            assert "- Audience Niche:" in markdown
            assert "- Problem Scope:" in markdown
            assert "- Geographic or Vertical Bound:" in markdown
            assert "- Value Proposition:" in markdown
            assert "- First-Party Utility Asset:" in markdown


def test_classify_serp_incumbent_forum_domains():
    """Validates classify_serp_incumbent assigns FORUM_INCOMPLETE_ANSWER for UGC forum domains."""
    for forum in UGC_FORUM_DOMAINS:
        item = {
            "domain": forum,
            "rank": 1,
            "title": f"Community discussion on {forum}",
            "snippet": "User questions and opinions",
        }
        res = classify_serp_incumbent(item, target_query="equipment lease calculator")
        assert res.weakness_category == "FORUM_INCOMPLETE_ANSWER"
        assert res.domain == forum
        assert "UGC forum discussion" in res.weakness_detail

    # Test subdomain and www prefix
    item_subdomain = {
        "domain": "old.reddit.com",
        "rank": 2,
        "title": "Subreddit advice thread",
        "snippet": "Casual answers",
    }
    res_sub = classify_serp_incumbent(item_subdomain)
    assert res_sub.weakness_category == "FORUM_INCOMPLETE_ANSWER"

    # Test URL extraction
    item_url = {
        "url": "https://www.quora.com/What-is-section-179",
        "rank": 3,
        "title": "Quora answers",
        "snippet": "Answers by contributors",
    }
    res_url = classify_serp_incumbent(item_url)
    assert res_url.weakness_category == "FORUM_INCOMPLETE_ANSWER"


def test_classify_serp_incumbent_outdated_statutory_data():
    """Validates classify_serp_incumbent assigns OUTDATED_STATUTORY_DATA for old items."""
    # Year-based item
    item_old_year = {
        "domain": "taxadvisorblog.com",
        "rank": 1,
        "title": "Section 179 Limits and Thresholds Guide",
        "year": 2020,
        "snippet": "Guide to the 2020 deduction limits",
    }
    res_year = classify_serp_incumbent(item_old_year)
    assert res_year.weakness_category == "OUTDATED_STATUTORY_DATA"
    assert "older than statutory threshold" in res_year.weakness_detail

    # Date string item
    item_old_date = {
        "domain": "accountingtoday.com",
        "rank": 2,
        "title": "Bonus depreciation breakdown",
        "date": "2021-08-14",
        "snippet": "Rules for asset expensing in 2021",
    }
    res_date = classify_serp_incumbent(item_old_date)
    assert res_date.weakness_category == "OUTDATED_STATUTORY_DATA"


def test_classify_serp_incumbent_missing_specs():
    """Validates classify_serp_incumbent assigns MISSING_QUANTITATIVE_SPECIFICATIONS."""
    # Mentions missing specs in title
    item_title_specs = {
        "domain": "industryreview.com",
        "rank": 1,
        "title": "HVAC Software Overview (Missing Specs Comparison)",
        "snippet": "General features and screenshots",
    }
    res_title = classify_serp_incumbent(item_title_specs)
    assert res_title.weakness_category == "MISSING_QUANTITATIVE_SPECIFICATIONS"

    # Mentions lacks data in snippet
    item_snippet_data = {
        "domain": "softwarelist.com",
        "rank": 2,
        "title": "Top Dispatch Platforms for Contractors",
        "snippet": "Summary of products, but lacks data on pricing tiers or limits",
    }
    res_snippet = classify_serp_incumbent(item_snippet_data)
    assert res_snippet.weakness_category == "MISSING_QUANTITATIVE_SPECIFICATIONS"


def test_classify_serp_incumbent_generic_article_default():
    """Validates default fallback to GENERIC_THIN_ARTICLE when no specific triggers fire."""
    item_generic = {
        "domain": "freshb2bblog.org",
        "rank": 1,
        "title": "Fleet Management Platform Best Practices",
        "year": 2026,
        "snippet": "Comprehensive operational workflow guide for dispatching teams",
    }
    res_generic = classify_serp_incumbent(item_generic)
    assert res_generic.weakness_category == "GENERIC_THIN_ARTICLE"
    assert "Generic thin article" in res_generic.weakness_detail


def test_classify_serp_incumbents_batch_and_evaluate_angles_integration():
    """Validates batch classification and evaluate_content_angles integration with raw SERP dicts."""
    raw_serp_items = [
        {
            "domain": "reddit.com",
            "rank": 1,
            "title": "What tools do you use for cold chain dispatch?",
            "snippet": "Looking for recommendations on cold chain temperature sync",
        },
        {
            "domain": "coldchaininsider.com",
            "rank": 2,
            "title": "Cold Storage Transport Standards",
            "year": 2021,
            "snippet": "Historical standards from 2021 regulatory revisions",
        },
        {
            "domain": "logisticsdaily.com",
            "rank": 3,
            "title": "Commercial Refrigerated Truck Fleet Guide",
            "snippet": "General marketing article outlining cold chain benefits",
        },
    ]

    # Batch classify
    classified_list = classify_serp_incumbents(raw_serp_items, target_query="cold chain dispatch tool")
    assert len(classified_list) == 3
    assert classified_list[0].weakness_category == "FORUM_INCOMPLETE_ANSWER"
    assert classified_list[1].weakness_category == "OUTDATED_STATUTORY_DATA"
    assert classified_list[2].weakness_category == "GENERIC_THIN_ARTICLE"

    # Direct integration with evaluate_content_angles accepting raw SERP dicts
    query_payload = {
        "query": "cold chain reefer dispatch software 2 truck fleet",
        "gsc_metrics": {
            "position": 12.0,
            "impressions": 45,
            "days_observed": 30,
            "clicks": 3,
        },
        "incumbents": raw_serp_items,
        "existing_site_catalog": [],
        "underdog_angle_specs": [
            {
                "angle_id": "cold_chain_realtime_temp_telemetry",
                "target_audience_niche": "Independent 2-truck reefer fleet owner-operators",
                "problem_scope": "Continuous temperature audit logging without enterprise telematics contracts",
                "geographic_or_vertical_bound": "North American interstate refrigerated transport",
                "primary_value_proposition": "Self-serve reefer compliance telemetry calculator with HACCP export",
                "first_party_utility_asset": "Interactive reefer HACCP compliance logger and trip audit tool",
                "divergence_score_min": 0.50,
            }
        ],
    }

    brief = evaluate_content_angles(query_payload, total_site_impressions=500)
    assert brief.triage_action == "BUILD_PAGE"
    markdown = brief.to_markdown()

    # Invariants verification
    assert_no_forbidden_dashes(markdown, "raw SERP dict brief")
    assert_no_prompt_leakage(markdown, "raw SERP dict brief")

    # Verify classified weaknesses are properly rendered in markdown
    assert "FORUM_INCOMPLETE_ANSWER" in markdown
    assert "OUTDATED_STATUTORY_DATA" in markdown
    assert "GENERIC_THIN_ARTICLE" in markdown
