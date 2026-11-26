"""
Unit tests for pseofactory High-Effort Content Qualification Gate.
Verifies:
1. Positive qualification on fully grounded candidate specifications.
2. Rejection of missing statutory legal provenance.
3. Rejection of missing empirical economic dataset series.
4. Rejection of missing formula or formula AST syntax errors.
5. Rejection of missing or empty inputs.
6. Rejection of mathematical mismatches between published output and formula evaluation.
7. Rejection of forbidden dashes (U+2014 em-dash, U+2013 en-dash).
8. Rejection of mock markers and ungrounded synthetic tokens.
9. Integration with Search Intent Doctrine triage.

Zero em-dashes. Zero en-dashes.
"""

import pytest
from pseofactory.qualification import (
    assert_high_effort_content_qualified,
    assert_search_intent_qualified,
    qualify_search_intent,
)


@pytest.fixture
def valid_high_effort_candidate_spec():
    return {
        "query": "section 179 deduction calculator",
        "primary_keyword": "section 179 deduction calculator",
        "slug": "section-179-deduction-calculator",
        "title": "Section 179 Deduction Calculator and Statutory Analysis",
        "model_name": "Section 179 First-Year Expense Model",
        "formula": "max(0.0, min(cost, cap) - max(0.0, cost - phaseout))",
        "inputs": {"cost": 500000, "cap": 1220000, "phaseout": 3050000},
        "published_output": 500000.0,
        "sample_calculation": "Equipment cost 500,000 is under 1,220,000 cap yielding full 500,000 deduction",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
    }


def test_assert_high_effort_content_qualified_valid_spec(valid_high_effort_candidate_spec):
    assert assert_high_effort_content_qualified(valid_high_effort_candidate_spec) is True


def test_assert_high_effort_content_qualified_missing_statutory(valid_high_effort_candidate_spec):
    spec_no_stat = dict(valid_high_effort_candidate_spec)
    spec_no_stat.pop("statutory_authority")
    with pytest.raises(ValueError, match="missing or empty primary statutory authority"):
        assert_high_effort_content_qualified(spec_no_stat)

    spec_invalid_stat = dict(valid_high_effort_candidate_spec)
    spec_invalid_stat["statutory_authority"] = "Internal Company Policy Manual"
    with pytest.raises(ValueError, match="does not cite recognized primary statutory provenance"):
        assert_high_effort_content_qualified(spec_invalid_stat)


def test_assert_high_effort_content_qualified_missing_economic(valid_high_effort_candidate_spec):
    spec_no_econ = dict(valid_high_effort_candidate_spec)
    spec_no_econ.pop("economic_dataset")
    with pytest.raises(ValueError, match="missing or empty empirical economic dataset"):
        assert_high_effort_content_qualified(spec_no_econ)

    spec_invalid_econ = dict(valid_high_effort_candidate_spec)
    spec_invalid_econ["economic_dataset"] = "Proprietary Internal Guesswork Series"
    with pytest.raises(ValueError, match="does not cite recognized empirical economic dataset series"):
        assert_high_effort_content_qualified(spec_invalid_econ)


def test_assert_high_effort_content_qualified_missing_formula(valid_high_effort_candidate_spec):
    spec = dict(valid_high_effort_candidate_spec)
    spec["formula"] = ""
    with pytest.raises(ValueError, match="missing or empty 'formula'"):
        assert_high_effort_content_qualified(spec)


def test_assert_high_effort_content_qualified_formula_syntax_error(valid_high_effort_candidate_spec):
    spec = dict(valid_high_effort_candidate_spec)
    spec["formula"] = "cost * + - /"
    with pytest.raises(ValueError, match="formula.*evaluation failed"):
        assert_high_effort_content_qualified(spec)


def test_assert_high_effort_content_qualified_missing_inputs(valid_high_effort_candidate_spec):
    spec = dict(valid_high_effort_candidate_spec)
    spec["inputs"] = {}
    with pytest.raises(ValueError, match="missing or empty 'inputs'"):
        assert_high_effort_content_qualified(spec)


def test_assert_high_effort_content_qualified_math_mismatch(valid_high_effort_candidate_spec):
    spec = dict(valid_high_effort_candidate_spec)
    spec["published_output"] = 999999.0  # Formula evaluates to 500000.0
    with pytest.raises(ValueError, match="Proprietary model input/output mismatch"):
        assert_high_effort_content_qualified(spec)


def test_assert_high_effort_content_qualified_forbidden_dashes(valid_high_effort_candidate_spec):
    # Em-dash injection
    spec_em = dict(valid_high_effort_candidate_spec)
    spec_em["sample_calculation"] = "Equipment cost \u2014 full deduction"
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_high_effort_content_qualified(spec_em)

    # En-dash injection
    spec_en = dict(valid_high_effort_candidate_spec)
    spec_en["statutory_authority"] = "IRC Section 179(b)(1) \u2013 2024"
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_high_effort_content_qualified(spec_en)


def test_assert_high_effort_content_qualified_ungrounded_synthetic(valid_high_effort_candidate_spec):
    for bad_token in ["mock dataset", "dummy values", "hypothetical benchmark", "placeholder table"]:
        spec = dict(valid_high_effort_candidate_spec)
        spec["sample_calculation"] = f"Using {bad_token} to verify the numbers"
        with pytest.raises(ValueError, match="ungrounded synthetic claims or mock markers detected"):
            assert_high_effort_content_qualified(spec)


def test_search_intent_doctrine_high_effort_integration(valid_high_effort_candidate_spec):
    # Valid high-effort spec passes through assert_search_intent_qualified
    assert assert_search_intent_qualified(valid_high_effort_candidate_spec, require_high_effort=True) is True

    # High-effort keys automatically trigger high-effort validation even if require_high_effort=False
    invalid_spec = dict(valid_high_effort_candidate_spec)
    invalid_spec["statutory_authority"] = "Invalid Authority"
    with pytest.raises(ValueError, match="does not cite recognized primary statutory provenance"):
        assert_search_intent_qualified(invalid_spec, require_high_effort=False)

    # Bare spec without high-effort keys passes standard cannibalization check when require_high_effort=False
    bare_spec = {
        "query": "distinct unserved niche topic",
        "primary_keyword": "distinct unserved niche topic",
        "slug": "distinct-unserved-niche-topic",
    }
    assert assert_search_intent_qualified(bare_spec, require_high_effort=False) is True

    # Bare spec fails when require_high_effort=True
    with pytest.raises(ValueError, match="missing or empty primary statutory authority"):
        assert_search_intent_qualified(bare_spec, require_high_effort=True)

    # qualify_search_intent enforces high effort when require_high_effort is True
    q_data_valid = {
        "query": "section 179 deduction calculator",
        "position": 15.0,
        "impressions": 45,
        **valid_high_effort_candidate_spec,
    }
    res = qualify_search_intent(q_data_valid, require_high_effort=True)
    assert res["action"] == "BUILD_PAGE"
    assert "candidate_spec" in res
    assert res["candidate_spec"]["statutory_authority"] == "IRC Section 179(b)(1)"

    q_data_invalid = {
        "query": "section 179 deduction calculator",
        "position": 15.0,
        "impressions": 45,
        "formula": "cost * 0.5",
        "inputs": {"cost": 1000},
        "model_name": "Test Model",
        "sample_calculation": "Test sample",
        "economic_dataset": "FRED CPILFESL Series",
        # missing statutory_authority
    }
    with pytest.raises(ValueError, match="missing or empty primary statutory authority"):
        qualify_search_intent(q_data_invalid, require_high_effort=True)


def test_evergreen_slug_ban_delete_modifier_spoke_gate_and_impression_split():
    """
    Verifies:
      1. Slug validator bans year tokens (\\b20[1-3]\\d\\b) on new tool slugs.
      2. Programmatic child spoke qualification enforces Delete-the-Modifier uniqueness.
      3. evaluate_query_impression_split filters < 100 impr/28d noise and emits merge/anchor directives.
    """
    from pseofactory.qualification import (
        assert_valid_new_tool_slug,
        evaluate_query_impression_split,
        qualify_programmatic_child_spokes,
        qualify_search_intent,
        validate_new_tool_slug,
    )

    assert validate_new_tool_slug("irs-tax-brackets")["valid"] is True
    assert validate_new_tool_slug("irs-2027-tax-brackets")["valid"] is False
    assert validate_new_tool_slug("capital-gains-2021-calculator")["valid"] is False
    with pytest.raises(ValueError, match="Year-stamped tool slug"):
        assert_valid_new_tool_slug("irs-interest-calculator-2027")

    year_verdict = qualify_search_intent(
        {
            "query": "distinct unserved statutory calculator",
            "slug": "distinct-unserved-calculator-2027",
            "impressions": 200,
            "position": 8.0,
            "formula": "round(a * b * c, 2)",
            "inputs": {"a": 1, "b": 2, "c": 3},
        }
    )
    assert year_verdict["action"] == "REJECT_YEAR_SLUG"
    assert year_verdict["status"] == "PRUNE"

    dup_spoke = qualify_programmatic_child_spokes(
        [
            {
                "slug": "tax-california",
                "modifier": "California",
                "html": "<p>Compute federal income tax liability under permanent 10% to 37% brackets in California.</p>",
                "formula": "round(income * 0.22, 2)",
                "inputs": {"income": 100000},
            },
            {
                "slug": "tax-texas",
                "modifier": "Texas",
                "html": "<p>Compute federal income tax liability under permanent 10% to 37% brackets in Texas.</p>",
                "formula": "round(income * 0.22, 2)",
                "inputs": {"income": 100000},
            },
        ]
    )
    assert dup_spoke["approved"] is False
    assert dup_spoke["status"] == "REJECT_NEAR_DUPLICATE_SPOKE"

    low_noise = evaluate_query_impression_split(
        [
            {"url": "/tools/a/", "impressions": 45, "position": 7.0},
            {"url": "/tools/b/", "impressions": 40, "position": 9.0},
        ],
        query="section 179 bonus depreciation",
    )
    assert low_noise["is_true_cannibalization_split"] is False
    assert low_noise["classification"] == "BELOW_MIN_IMPRESSIONS_NOISE"

    true_split = evaluate_query_impression_split(
        [
            {"url": "/tools/a/", "impressions": 120, "position": 6.0},
            {"url": "/tools/b/", "impressions": 80, "position": 8.0},
        ],
        query="section 179 bonus depreciation",
    )
    assert true_split["is_true_cannibalization_split"] is True
    assert true_split["winner_url"] == "/tools/a/"
    assert true_split["loser_urls"] == ["/tools/b/"]
    assert true_split["merge_directives"][0]["http_redirect"] == 301
    assert true_split["internal_anchor_rewrite_directives"][0]["to_target_url"] == "/tools/a/"
