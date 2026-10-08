"""
Tests for pseofactory Jev decision engine.
Enforces TypeSafe AI System One threshold gating (score >= 1.20, durable_prob >= 0.50),
composite profit yield ranking, and Search Intent Doctrine strategic triage.
Zero em-dashes. Zero en-dashes.
"""

from pseofactory.trends.models import TrendCandidate, TregDurabilityResult, JevDecisionResult
from pseofactory.trends.jev_engine import (
    JevEngine,
    calculate_normalized_velocity,
    calculate_normalized_volume,
    calculate_intent_weight,
    determine_target_asset_type,
)


def test_jev_threshold_gate():
    """
    Enforces Jev decision threshold gate:
    Candidate with jev_score < 1.20 or durable_prob < 0.50 must be REJECTED.
    """
    engine = JevEngine(min_score=1.20, min_durable_prob=0.50)

    cand = TrendCandidate(
        id="cand-01",
        query="super bowl halftime performer leak 2027",
        slug="super-bowl-halftime-performer-leak-2027",
        source="google_suggest",
        velocity=78.0,
        acceleration=2.0,
        z_score=3.9,
        intent_cluster="informational",
        is_transient_noise=False,
    )
    treg_res = TregDurabilityResult(
        query=cand.query,
        search_volume=1800,
        cpc_usd=0.25,
        keyword_difficulty=62.0,
        position_zero_vacant=False,
    )

    # Low Jev score (0.22 < 1.20) and low durable_prob (0.08 < 0.50)
    decision = engine.evaluate(
        candidate=cand,
        treg_result=treg_res,
        jev_mock={"jev_score": 0.22, "durable_prob": 0.08},
    )
    assert decision.action == "REJECT"
    assert decision.passed_thresholds is False
    assert "Failed Jev durability invariant threshold" in decision.decision_reason


def test_composite_profit_yield_ranking():
    """Verifies composite profit yield reflects velocity, search volume, durability, and intent."""
    engine = JevEngine()

    cand_high = TrendCandidate(
        id="cand-stat",
        query="form 8829 home office deduction calculator 2026",
        slug="form-8829-home-office-deduction-calculator-2026",
        source="google_suggest",
        velocity=48.0,
        acceleration=14.5,
        z_score=3.8,
        intent_cluster="statutory_compliance",
    )
    treg_high = TregDurabilityResult(
        query=cand_high.query,
        search_volume=3600,
        cpc_usd=4.80,
        keyword_difficulty=18.0,
        position_zero_vacant=True,
    )

    score_high = engine.compute_composite_yield(
        candidate=cand_high,
        treg_result=treg_high,
        jev_score=1.85,
        durable_prob=0.94,
        cannibalization_risk=0.0,
    )
    assert score_high >= 60.0

    # Low utility, high difficulty query has lower yield
    cand_low = TrendCandidate(
        id="cand-info",
        query="general office supply checklist",
        slug="general-office-supply-checklist",
        source="google_suggest",
        velocity=10.0,
        acceleration=1.0,
        z_score=1.8,
        intent_cluster="informational",
    )
    treg_low = TregDurabilityResult(
        query=cand_low.query,
        search_volume=500,
        cpc_usd=0.40,
        keyword_difficulty=65.0,
        position_zero_vacant=False,
    )
    score_low = engine.compute_composite_yield(
        candidate=cand_low,
        treg_result=treg_low,
        jev_score=1.25,
        durable_prob=0.55,
        cannibalization_risk=0.3,
    )
    assert score_high > score_low


def test_striking_distance_cannibalization_routes_to_refactor():
    """
    Enforces Search Intent Doctrine:
    Cannibalizing candidate in striking distance (position 4-20) routes to REFACTOR_PAGE
    with a 28-day measurement lock overlay spec.
    """
    engine = JevEngine()
    cand = TrendCandidate(
        id="cand-loan",
        query="direct consolidation loan repayment estimator",
        slug="direct-consolidation-loan-repayment-estimator",
        source="google_suggest",
        velocity=34.0,
        acceleration=8.2,
        z_score=3.1,
        intent_cluster="calculator",
    )
    treg_res = TregDurabilityResult(
        query=cand.query,
        search_volume=2900,
        cpc_usd=6.20,
        keyword_difficulty=22.0,
        position_zero_vacant=False,
    )
    cann_ctx = {
        "matches_existing_slug": "direct-consolidation-loan-calculator",
        "current_position": 11.2,
        "cannibalization_score": 0.78,
    }

    decision = engine.evaluate(
        candidate=cand,
        treg_result=treg_res,
        cannibalization_context=cann_ctx,
        jev_mock={"jev_score": 1.75, "durable_prob": 0.90},
    )
    assert decision.action == "REFACTOR_PAGE"
    assert decision.matching_tool == "direct-consolidation-loan-calculator"
    assert decision.overlay_spec is not None
    assert decision.overlay_spec["measurement_lock_days"] == 28
    assert "Striking distance query" in decision.decision_reason


def test_build_page_qualification_gate():
    """Verifies clean void query with vacant Position 0 qualifies for BUILD_PAGE."""
    engine = JevEngine()
    cand = TrendCandidate(
        id="cand-clean",
        query="section 179d commercial clean energy deduction matrix",
        slug="section-179d-commercial-clean-energy-deduction-matrix",
        source="reddit_autocomplete",
        velocity=28.0,
        acceleration=9.8,
        z_score=3.4,
        intent_cluster="statutory_compliance",
    )
    treg_res = TregDurabilityResult(
        query=cand.query,
        search_volume=1600,
        cpc_usd=12.40,
        keyword_difficulty=14.0,
        position_zero_vacant=True,
    )

    decision = engine.evaluate(
        candidate=cand,
        treg_result=treg_res,
        jev_mock={"jev_score": 1.80, "durable_prob": 0.95},
    )
    assert decision.action == "BUILD_PAGE"
    assert decision.passed_thresholds is True
    assert decision.target_asset_type == "statutory_matrix"
    assert decision.candidate_spec is not None
    assert decision.candidate_spec["status"] == "APPROVED_BUILD"


def test_determine_target_asset_type():
    """Verifies programmatic asset generator template selection."""
    assert determine_target_asset_type("form 8829 deduction calculator", "calculator") == "interactive_calculator"
    assert determine_target_asset_type("commercial clean energy matrix", "statutory_compliance") == "statutory_matrix"
    assert determine_target_asset_type("stripe vs paypal fee comparison", "comparison") == "comparison_engine"
