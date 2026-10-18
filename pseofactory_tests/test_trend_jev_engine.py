"""
Tests for pseofactory Jev decision engine.
Enforces TypeSafe AI System One threshold gating (score >= 1.20, durable_prob >= 0.50),
composite profit yield ranking, and Search Intent Doctrine strategic triage.
Zero em-dashes. Zero en-dashes.
"""

import pytest

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


def test_compute_composite_yield_serp_weakness_discount():
    """
    Verifies that serp_weakness_count and position_zero_vacant apply risk discount:
    r_discount = max(0.60, 1.0 - 0.10 * min(serp_weakness_count, 4))
    r = r * r_discount
    """
    engine = JevEngine()
    cand = TrendCandidate(
        id="cand-weakness",
        query="commercial hvac maintenance cost estimator",
        slug="commercial-hvac-maintenance-cost-estimator",
        source="google_suggest",
        velocity=40.0,
        acceleration=5.0,
        z_score=3.0,
        intent_cluster="calculator",
    )
    treg = TregDurabilityResult(
        query=cand.query,
        search_volume=2000,
        cpc_usd=5.0,
        keyword_difficulty=40.0,
        position_zero_vacant=False,
    )

    # Base yield with zero weaknesses and position zero not vacant
    yield_base = engine.compute_composite_yield(
        candidate=cand,
        treg_result=treg,
        jev_score=1.50,
        durable_prob=0.80,
        cannibalization_risk=0.20,
        serp_weakness_count=0,
    )

    # Yield with 2 SERP weaknesses (20% discount on risk r)
    yield_weak_2 = engine.compute_composite_yield(
        candidate=cand,
        treg_result=treg,
        jev_score=1.50,
        durable_prob=0.80,
        cannibalization_risk=0.20,
        serp_weakness_count=2,
    )
    assert yield_weak_2 > yield_base

    # Yield with 4 SERP weaknesses (40% discount, cap)
    yield_weak_4 = engine.compute_composite_yield(
        candidate=cand,
        treg_result=treg,
        jev_score=1.50,
        durable_prob=0.80,
        cannibalization_risk=0.20,
        serp_weakness_count=4,
    )
    assert yield_weak_4 > yield_weak_2

    # Yield with 5 SERP weaknesses (capped at 4 / 0.60 floor)
    yield_weak_5 = engine.compute_composite_yield(
        candidate=cand,
        treg_result=treg,
        jev_score=1.50,
        durable_prob=0.80,
        cannibalization_risk=0.20,
        serp_weakness_count=5,
    )
    assert yield_weak_5 == pytest.approx(yield_weak_4, rel=1e-5)

    # Verification via candidate metadata
    cand.metadata = {"serp_weakness_count": 2}
    yield_meta = engine.compute_composite_yield(
        candidate=cand,
        treg_result=treg,
        jev_score=1.50,
        durable_prob=0.80,
        cannibalization_risk=0.20,
    )
    assert yield_meta == pytest.approx(yield_weak_2, rel=1e-5)

    # Verification of position_zero_vacant discounting risk
    treg_p0 = TregDurabilityResult(
        query=cand.query,
        search_volume=2000,
        cpc_usd=5.0,
        keyword_difficulty=40.0,
        position_zero_vacant=True,
    )
    cand_no_meta = TrendCandidate(
        id="cand-p0",
        query="commercial hvac maintenance cost estimator",
        slug="commercial-hvac-maintenance-cost-estimator",
        source="google_suggest",
        velocity=40.0,
        acceleration=5.0,
        z_score=3.0,
        intent_cluster="calculator",
    )
    yield_p0 = engine.compute_composite_yield(
        candidate=cand_no_meta,
        treg_result=treg_p0,
        jev_score=1.50,
        durable_prob=0.80,
        cannibalization_risk=0.20,
        serp_weakness_count=0,
    )
    assert yield_p0 > yield_base


def test_ai_citation_vacancy_unlocks_moderate_kd_build_and_overlay():
    """
    Verifies that ai_citation_vacant=True:
    1. Discounts composite risk and qualifies moderate-KD (<= 38.0) high-yield voids for BUILD_PAGE
       even when traditional position_zero_vacant is False.
    2. Propagates ai_citation_vacant and ai_cited_domains into candidate_spec and striking-distance overlay_spec.
    """
    engine = JevEngine()
    cand = TrendCandidate(
        id="cand-ai-void",
        query="section 179d commercial clean energy deduction matrix",
        slug="section-179d-commercial-clean-energy-deduction-matrix",
        source="google_suggest",
        velocity=35.0,
        acceleration=11.0,
        z_score=3.6,
        intent_cluster="statutory_compliance",
    )

    # Without AI citation vacancy: KD=31.0 (> 25.0) and position_zero_vacant=False -> MONITOR
    treg_no_ai = TregDurabilityResult(
        query=cand.query,
        search_volume=2400,
        cpc_usd=12.40,
        keyword_difficulty=31.0,
        position_zero_vacant=False,
        ai_citation_vacant=False,
        ai_citation_checked=True,
    )
    dec_no_ai = engine.evaluate(
        candidate=cand,
        treg_result=treg_no_ai,
        jev_mock={"jev_score": 1.85, "durable_prob": 0.95},
    )
    assert dec_no_ai.action == "MONITOR"

    # With AI citation vacancy (e.g. ChatGPT only cites raw IRS PDF + Reddit): qualifies for BUILD_PAGE
    treg_with_ai_void = TregDurabilityResult(
        query=cand.query,
        search_volume=2400,
        cpc_usd=12.40,
        keyword_difficulty=31.0,
        position_zero_vacant=False,
        ai_citation_vacant=True,
        ai_cited_domains=["irs.gov", "reddit.com"],
        ai_citation_checked=True,
    )
    dec_ai_void = engine.evaluate(
        candidate=cand,
        treg_result=treg_with_ai_void,
        jev_mock={"jev_score": 1.85, "durable_prob": 0.95},
    )
    assert dec_ai_void.action == "BUILD_PAGE"
    assert dec_ai_void.composite_profit_yield > dec_no_ai.composite_profit_yield
    assert dec_ai_void.candidate_spec is not None
    assert dec_ai_void.candidate_spec["ai_citation_vacant"] is True
    assert dec_ai_void.candidate_spec["ai_cited_domains"] == ["irs.gov", "reddit.com"]

    # Striking-distance cannibalization propagates AI citation telemetry into overlay_spec
    cann_ctx = {
        "matches_existing_slug": "section-179-tax-deduction-calculator",
        "current_position": 9.5,
        "cannibalization_score": 0.75,
    }
    dec_overlay = engine.evaluate(
        candidate=cand,
        treg_result=treg_with_ai_void,
        cannibalization_context=cann_ctx,
        jev_mock={"jev_score": 1.85, "durable_prob": 0.95},
    )
    assert dec_overlay.action == "REFACTOR_PAGE"
    assert dec_overlay.overlay_spec is not None
    assert dec_overlay.overlay_spec["ai_citation_vacant"] is True
    assert dec_overlay.overlay_spec["ai_cited_domains"] == ["irs.gov", "reddit.com"]

