"""
Unit tests for pseofactory Search Intent Doctrine & Opportunity Qualification Engine.
Verifies:
1. check_search_intent_cannibalization detects primary keywords, secondary keywords, and slug token overlap.
2. qualify_search_intent enforces Adrien Russo taxonomy with Search Intent Doctrine triage.
3. assert_search_intent_qualified raises ValueError for cannibalizing candidate specs.

Zero em-dashes. Zero en-dashes.
"""

import pytest
from pseofactory.qualification import (
    check_search_intent_cannibalization,
    qualify_search_intent,
    assert_search_intent_qualified,
)


@pytest.fixture
def mock_existing_tools():
    return [
        {
            "slug": "direct-consolidation-loan-calculator",
            "title": "Direct Consolidation Loan Calculator",
            "primary_keyword": "direct consolidation loan",
            "secondary_keywords": [
                "consolidation loan repayment options",
                "loan repayment options",
                "federal consolidation options",
            ],
            "url": "https://example.com/tools/direct-consolidation-loan-calculator/",
        },
        {
            "slug": "section-179-calculator",
            "title": "Section 179 Calculator",
            "primary_keyword": "section 179 deduction",
            "secondary_keywords": [
                "first year equipment tax deduction",
                "bonus depreciation limits",
            ],
            "url": "https://example.com/tools/section-179-calculator/",
        },
    ]


def test_cannibalization_primary_keyword_match(mock_existing_tools):
    res = check_search_intent_cannibalization("direct consolidation loan", mock_existing_tools)
    assert res["is_cannibalizing"] is True
    assert res["cannibalized"] is True
    assert res["parent_slug"] == "direct-consolidation-loan-calculator"
    assert res["reason"] == "matches_primary_keyword"


def test_cannibalization_secondary_keyword_match(mock_existing_tools):
    res = check_search_intent_cannibalization("consolidation loan repayment options", mock_existing_tools)
    assert res["is_cannibalizing"] is True
    assert res["cannibalized"] is True
    assert res["parent_slug"] == "direct-consolidation-loan-calculator"
    assert res["reason"] == "matches_secondary_keyword"


def test_cannibalization_high_slug_token_overlap(mock_existing_tools):
    # 3 matching words in 3-word query -> overlap
    res = check_search_intent_cannibalization("consolidation loan calculator", mock_existing_tools)
    assert res["is_cannibalizing"] is True
    assert res["parent_slug"] == "direct-consolidation-loan-calculator"
    assert res["reason"] == "high_slug_token_overlap"


def test_cannibalization_distinct_novel_opportunity(mock_existing_tools):
    res = check_search_intent_cannibalization("autonomous electric vehicle fleet tax credit", mock_existing_tools)
    assert res["is_cannibalizing"] is False
    assert res["cannibalized"] is False
    assert res["parent_slug"] == "none"
    assert res["reason"] == "distinct_asset"


def test_cannibalization_empty_and_safe_handling(mock_existing_tools):
    assert check_search_intent_cannibalization("", mock_existing_tools)["is_cannibalizing"] is False
    assert check_search_intent_cannibalization(None, mock_existing_tools)["is_cannibalizing"] is False
    assert check_search_intent_cannibalization("some query", None)["is_cannibalizing"] is False


def test_qualify_search_intent_consolidate_competing_pages(mock_existing_tools):
    q_data = {
        "query": "federal student aid repayment",
        "position": 12.0,
        "impressions": 50,
        "competing_pages": [
            "https://example.com/tools/page-a/",
            "https://example.com/tools/page-b/",
        ],
    }
    res = qualify_search_intent(q_data, mock_existing_tools)
    assert res["action"] == "CONSOLIDATE_PAGES"
    assert res["canonical_url"] == "https://example.com/tools/page-a/"
    assert len(res["redirect_candidates"]) == 1


def test_qualify_search_intent_prune_zero_impressions(mock_existing_tools):
    q_data = {
        "query": "obsolete tax rule 2012",
        "position": 85.0,
        "impressions": 0,
        "days": 95,
    }
    res = qualify_search_intent(q_data, mock_existing_tools)
    assert res["action"] == "PRUNE_PAGE"
    assert res["recommendation"] == "noindex_follow"


def test_qualify_search_intent_refactor_striking_distance(mock_existing_tools):
    q_data = {
        "query": "consolidation loan repayment options",
        "position": 11.5,
        "impressions": 40,
    }
    res = qualify_search_intent(q_data, mock_existing_tools)
    assert res["action"] == "REFACTOR_PAGE"
    assert res["matching_tool"] == "direct-consolidation-loan-calculator"
    assert res["measurement_lock_days"] == 28
    assert "overlay_spec" in res


def test_qualify_search_intent_monitor_top_ranking(mock_existing_tools):
    q_data = {
        "query": "direct consolidation loan",
        "position": 2.1,
        "impressions": 120,
    }
    res = qualify_search_intent(q_data, mock_existing_tools)
    assert res["action"] == "MONITOR"
    assert "preserve existing authority" in res["reason"]


def test_qualify_search_intent_monitor_pos_above_20_matching(mock_existing_tools):
    q_data = {
        "query": "direct consolidation loan repayment options",
        "position": 24.0,
        "impressions": 30,
    }
    res = qualify_search_intent(q_data, mock_existing_tools)
    assert res["action"] == "MONITOR"
    assert "URL bloat" in res["reason"]


def test_qualify_search_intent_exploratory_impressions_monitored(mock_existing_tools):
    # Total impressions = 500, dynamic floor = max(2, min(25, 25)) = 25
    q_data = {
        "query": "novel unrelated solar microgrid incentive",
        "position": 15.0,
        "impressions": 10,  # below 25
    }
    res = qualify_search_intent(q_data, mock_existing_tools, total_site_impressions=500)
    assert res["action"] == "MONITOR"
    assert "below qualification floor" in res["reason"]


def test_qualify_search_intent_genuine_unserved_void_build_page(mock_existing_tools):
    q_data = {
        "query": "novel unrelated solar microgrid incentive",
        "position": 15.0,
        "impressions": 45,  # above 25
    }
    res = qualify_search_intent(q_data, mock_existing_tools, total_site_impressions=500)
    assert res["action"] == "BUILD_PAGE"
    assert "candidate_spec" in res
    assert res["candidate_spec"]["primary_keyword"] == "novel unrelated solar microgrid incentive"


def test_assert_search_intent_qualified_raises_on_cannibalization(mock_existing_tools):
    spec = {
        "query": "direct consolidation loan repayment options",
        "primary_keyword": "direct consolidation loan repayment options",
        "slug": "direct-consolidation-loan-repayment-options",
    }
    with pytest.raises(ValueError, match="Search intent cannibalization detected"):
        assert_search_intent_qualified(spec, mock_existing_tools)


def test_assert_search_intent_qualified_passes_on_distinct(mock_existing_tools):
    spec = {
        "query": "autonomous electric vehicle fleet tax credit",
        "primary_keyword": "autonomous electric vehicle fleet tax credit",
        "slug": "autonomous-electric-vehicle-fleet-tax-credit",
    }
    assert assert_search_intent_qualified(spec, mock_existing_tools) is True
