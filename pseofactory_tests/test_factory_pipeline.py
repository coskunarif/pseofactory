"""
Tests for pseofactory automated discovery and content generation pipeline.
Covers:
- ProfitHelm qualified opportunity -> compiles compliant HTML, Factor 7 manifest, clean contamination scan
- Prexvo qualified opportunity -> compiles compliant HTML, Title IV provenance, clean contamination scan
- Low Jev durability -> clean abort without page generation (LOW_JEV_DURABILITY)
- High Treg competition -> clean abort without page generation (HIGH_TREG_COMPETITION)
- Decelerating noise spike -> clean abort without page generation (TRANSIENT_NOISE_OR_DECELERATION)
- Cross-property contamination -> clean abort / rejection (CROSS_PROPERTY_CONTAMINATION)
- Derivative SERP angle (< 0.50 Jaccard divergence) -> clean abort (DERIVATIVE_SERP_ANGLE)
- Grant O Triad contract enforcement (empty triad fields rejected)
- Stateless worker physics and scoped environment variable cleanup
- Typography invariants (zero em-dashes and zero en-dashes)
- Atomic flock sink persistence via run_factory_pipeline convenience helper
Zero em-dashes. Zero en-dashes.
"""

import os
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pseofactory.pipeline import (
    FactoryPipeline,
    run_factory_pipeline,
    PipelineConfig,
    DriverExecutionResult,
    RejectionReason,
)
from pseofactory.trends.models import FeedSpike
from pseofactory.maintenance import CrossPropertyContaminationScanner
from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_no_prompt_leakage,
    assert_url_safe_slug,
)


def _make_spike(
    spike_id: str,
    query: str,
    tenant: str,
    velocity: float = 45.0,
    acceleration: float = 12.0,
    z_score: float = 3.5,
    sample_count: int = 1500,
    search_volume: int = 3500,
    cpc_usd: float = 4.50,
    keyword_difficulty: float = 18.0,
    position_zero_vacant: bool = True,
    jev_score: float = 1.75,
    durable_prob: float = 0.90,
    incumbents: list = None,
    candidate_angles: list = None,
    cannibalization_context: dict = None,
    candidate_spec: dict = None,
) -> FeedSpike:
    """Helper creating typed FeedSpike with embedded treg and jev mocks."""
    payload = {
        "id": spike_id,
        "query": query,
        "tenant": tenant,
        "source": "google_suggest",
        "detected_at": "2026-10-09T08:00:00Z",
        "sample_count": sample_count,
        "velocity": velocity,
        "acceleration": acceleration,
        "z_score": z_score,
        "baseline_mean": 8.0,
        "baseline_std": 2.0,
        "treg_mock": {
            "search_volume": search_volume,
            "cpc_usd": cpc_usd,
            "competition_index": 0.25,
            "keyword_difficulty": keyword_difficulty,
            "position_zero_vacant": position_zero_vacant,
        },
        "jev_mock": {
            "jev_score": jev_score,
            "durable_prob": durable_prob,
            "category": "calculator",
        },
    }
    if incumbents:
        payload["incumbents"] = incumbents
    if candidate_angles:
        payload["candidate_angles"] = candidate_angles
    if cannibalization_context:
        payload["cannibalization_context"] = cannibalization_context
    if candidate_spec:
        payload["candidate_spec"] = candidate_spec

    return FeedSpike.from_dict(payload)


def test_factory_pipeline_profithelm_qualified_build(tmp_path):
    """
    Valid high-yield Section 179 opportunity compiles compliant HTML,
    verified Factor 7 manifest, and passes cross-property contamination scan.
    """
    spike = _make_spike(
        spike_id="spike-profithelm-01",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
        search_volume=4500,
        keyword_difficulty=16.0,
        position_zero_vacant=True,
        jev_score=1.85,
        durable_prob=0.92,
        incumbents=[
            {
                "domain": "incumbent-tax.com",
                "rank": 1,
                "title": "General Equipment Tax Guide",
                "weakness_category": "lack_of_formulas",
                "weakness_detail": "Provides static tables without AST formula evaluation",
            }
        ],
        candidate_angles=[
            {
                "angle_id": "profithelm-sec179-underdog",
                "archetype": "Free Interactive Tool/Calculator",
                "target_audience_niche": "B2B commercial equipment purchasers",
                "problem_scope": "Real-time progressive Section 179 deduction calculation",
                "geographic_or_vertical_bound": "US Federal Corporate Tax Code",
                "primary_value_proposition": "Interactive AST verified deduction engine with empirical FRED economic benchmark integration",
                "first_party_utility_asset": "section-179-deduction-calculator",
                "divergence_score_min": 0.55,
            }
        ],
    )

    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline()
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.total_spikes == 1
    assert result.filtered_noise_count == 0
    assert result.evaluated_count == 1
    assert result.approved_count == 1
    assert result.compiled_count == 1
    assert result.aborted_count == 0
    assert len(result.compiled_assets) == 1

    asset = result.compiled_assets[0]
    assert asset.tenant == "profithelm"
    assert asset.audit_passed is True
    assert asset.contamination_clean is True
    assert asset.html_length > 1000
    assert asset.output_file is not None
    assert asset.output_file.exists()

    html = asset.output_file.read_text(encoding="utf-8")
    assert "IRC Section 179(b)(1)" in html
    assert "FRED CPILFESL Series" in html
    assert "min-height: 44px" in html
    assert "min-width: 44px" in html
    assert 'class="touch-target"' in html
    assert 'class="calculation-manifest"' in html

    # Contamination check: ProfitHelm HTML must contain zero Prexvo foreign tokens
    scanner = CrossPropertyContaminationScanner()
    foreign_tokens = scanner.scan_text(html, "profithelm")
    assert foreign_tokens == []

    # Invariants
    assert_no_forbidden_dashes(html, "compiled profithelm HTML")
    assert_no_prompt_leakage(html, "compiled profithelm HTML")


def test_factory_pipeline_prexvo_qualified_build(tmp_path):
    """
    Valid high-yield student loan direct consolidation opportunity compiles
    compliant HTML with Title IV statutory provenance and clean contamination scan.
    """
    spike = _make_spike(
        spike_id="spike-prexvo-01",
        query="direct consolidation loan repayment assistance plan estimator",
        tenant="prexvo",
        search_volume=3800,
        keyword_difficulty=19.0,
        position_zero_vacant=True,
        jev_score=1.78,
        durable_prob=0.89,
        incumbents=[
            {
                "domain": "loan-aggregator.com",
                "rank": 1,
                "title": "Federal Student Loan Options Overview",
                "weakness_category": "dated_guidance",
                "weakness_detail": "Lacks updated Title IV 34 CFR weighted interest logic",
            }
        ],
        candidate_angles=[
            {
                "angle_id": "prexvo-consolidation-underdog",
                "archetype": "Regulatory/Audit Checklist",
                "target_audience_niche": "Federal student loan borrowers with multiple loan servicers",
                "problem_scope": "Weighted average interest rate calculation under Title IV statutory rules",
                "geographic_or_vertical_bound": "US Department of Education Federal Direct Loan Program",
                "primary_value_proposition": "Authoritative Title IV weighted rate estimator with empirical FRED SLSTTOTAL debt series",
                "first_party_utility_asset": "direct-consolidation-estimator",
                "divergence_score_min": 0.55,
            }
        ],
    )

    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline()
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.total_spikes == 1
    assert result.compiled_count == 1
    assert result.aborted_count == 0

    asset = result.compiled_assets[0]
    assert asset.tenant == "prexvo"
    assert asset.audit_passed is True
    assert asset.contamination_clean is True

    html = asset.output_file.read_text(encoding="utf-8")
    assert "34 CFR Part 685" in html
    assert "FRED SLSTTOTAL Series" in html
    assert "https://prexvo.com" in html

    # Contamination check: Prexvo HTML must contain zero ProfitHelm foreign tokens
    scanner = CrossPropertyContaminationScanner()
    foreign_tokens = scanner.scan_text(html, "prexvo")
    assert foreign_tokens == []

    # Invariants
    assert_no_forbidden_dashes(html, "compiled prexvo HTML")
    assert_no_prompt_leakage(html, "compiled prexvo HTML")


def test_factory_pipeline_low_jev_durability_aborts():
    """
    Candidate with Jev durability score < 1.20 or durable_prob < 0.50
    aborts cleanly with LOW_JEV_DURABILITY and zero page compilation.
    """
    spike = _make_spike(
        spike_id="spike-low-jev",
        query="bitcoin staking reward calculator 2026",
        tenant="profithelm",
        jev_score=0.25,
        durable_prob=0.08,
        search_volume=8500,
        keyword_difficulty=20.0,
        position_zero_vacant=True,
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.total_spikes == 1
    assert result.compiled_count == 0
    assert result.aborted_count == 1

    aborted = result.aborted_opportunities[0]
    assert aborted.reason == "LOW_JEV_DURABILITY"
    assert aborted.action == "REJECT"
    assert aborted.jev_score == 0.25
    assert aborted.durable_prob == 0.08


def test_factory_pipeline_decelerating_noise_aborts():
    """
    Candidate with negative acceleration and modest volume aborts
    cleanly with TRANSIENT_NOISE_OR_DECELERATION before downstream API spend.
    """
    spike = _make_spike(
        spike_id="spike-noise",
        query="hawk tuah soundboard remix generator",
        tenant="prexvo",
        velocity=80.0,
        acceleration=-35.0,
        z_score=1.2,
        search_volume=450,
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.total_spikes == 1
    assert result.filtered_noise_count == 1
    assert result.compiled_count == 0
    assert result.aborted_count == 1

    aborted = result.aborted_opportunities[0]
    assert aborted.reason == "TRANSIENT_NOISE_OR_DECELERATION"
    assert aborted.action == "REJECT"


def test_factory_pipeline_high_treg_competition_aborts():
    """
    Candidate with keyword difficulty >= 25.0 and occupied Position 0
    aborts cleanly with HIGH_TREG_COMPETITION and action MONITOR.
    """
    spike = _make_spike(
        spike_id="spike-high-comp",
        query="commercial equipment financing tax guide",
        tenant="profithelm",
        search_volume=6000,
        keyword_difficulty=42.0,
        position_zero_vacant=False,
        jev_score=1.60,
        durable_prob=0.80,
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.total_spikes == 1
    assert result.compiled_count == 0
    assert result.aborted_count == 1

    aborted = result.aborted_opportunities[0]
    assert aborted.reason == "HIGH_TREG_COMPETITION"
    assert aborted.action == "MONITOR"
    assert aborted.keyword_difficulty == 42.0


def test_factory_pipeline_striking_distance_cannibalization():
    """
    Query matching existing tool in striking distance (position 11.2)
    routes to REFACTOR_PAGE_CANNIBALIZATION with 28-day measurement lock.
    """
    spike = _make_spike(
        spike_id="spike-cannibal",
        query="section 179 equipment tax deduction",
        tenant="profithelm",
        search_volume=5000,
        keyword_difficulty=18.0,
        position_zero_vacant=True,
        jev_score=1.65,
        durable_prob=0.85,
        cannibalization_context={
            "cannibalization_score": 0.85,
            "matches_existing_slug": "section-179-calculator",
            "current_position": 11.2,
        },
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.total_spikes == 1
    assert result.compiled_count == 0
    assert result.aborted_count == 1

    aborted = result.aborted_opportunities[0]
    assert aborted.reason == "REFACTOR_PAGE_CANNIBALIZATION"
    assert aborted.action == "REFACTOR_PAGE"


def test_factory_pipeline_cross_property_contamination_rejection():
    """
    Cross-property contamination between Prexvo and ProfitHelm fails closed
    with CROSS_PROPERTY_CONTAMINATION.
    """
    pipeline = FactoryPipeline()

    # Prexvo opportunity containing ProfitHelm statutory token (1031 exchange)
    spike_prexvo_contaminated = _make_spike(
        spike_id="spike-prexvo-bad",
        query="student loan direct consolidation 1031 exchange rules",
        tenant="prexvo",
        jev_score=1.70,
        durable_prob=0.85,
        search_volume=3000,
    )
    res1 = pipeline.execute([spike_prexvo_contaminated])
    assert res1.compiled_count == 0
    assert res1.aborted_count == 1
    assert res1.aborted_opportunities[0].reason == "CROSS_PROPERTY_CONTAMINATION"
    assert res1.aborted_opportunities[0].action == "REJECT"

    # ProfitHelm opportunity containing Prexvo statutory token (title iv)
    spike_profithelm_contaminated = _make_spike(
        spike_id="spike-profithelm-bad",
        query="section 179 commercial equipment title iv repayment plan",
        tenant="profithelm",
        jev_score=1.70,
        durable_prob=0.85,
        search_volume=3000,
    )
    res2 = pipeline.execute([spike_profithelm_contaminated])
    assert res2.compiled_count == 0
    assert res2.aborted_count == 1
    assert res2.aborted_opportunities[0].reason == "CROSS_PROPERTY_CONTAMINATION"
    assert res2.aborted_opportunities[0].action == "REJECT"


def test_factory_pipeline_derivative_serp_angle_rejection():
    """
    Candidate underdog angle with token Jaccard divergence < 0.50
    aborts with DERIVATIVE_SERP_ANGLE and zero page compilation.
    """
    spike = _make_spike(
        spike_id="spike-derivative",
        query="section 179 equipment expense calculator",
        tenant="profithelm",
        search_volume=4000,
        keyword_difficulty=15.0,
        position_zero_vacant=True,
        jev_score=1.80,
        durable_prob=0.90,
        incumbents=[
            {
                "domain": "incumbent-one.com",
                "rank": 1,
                "title": "Section 179 Equipment Expense Calculator",
                "weakness_category": "thin",
                "weakness_detail": "Calculator lacks empirical economic series",
            }
        ],
        candidate_angles=[
            {
                "angle_id": "derivative-clone-angle",
                "archetype": "Free Interactive Tool/Calculator",
                "target_audience_niche": "Equipment buyers",
                "problem_scope": "Section 179 calculations",
                "geographic_or_vertical_bound": "US Tax",
                # Directly clones incumbent title - divergence will be < 0.50
                "primary_value_proposition": "Section 179 Equipment Expense Calculator",
                "first_party_utility_asset": "clone-calc",
                "divergence_score_min": 0.50,
            }
        ],
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.total_spikes == 1
    assert result.compiled_count == 0
    assert result.aborted_count == 1

    aborted = result.aborted_opportunities[0]
    assert aborted.reason == "DERIVATIVE_SERP_ANGLE"
    assert aborted.action == "REJECT"


def test_factory_pipeline_grant_o_triad_contract_enforcement():
    """
    Candidate underdog angle with invalid/empty Grant O Triad dimensions
    fails validation and aborts with DERIVATIVE_SERP_ANGLE.
    """
    spike = _make_spike(
        spike_id="spike-invalid-triad",
        query="section 179 equipment expense deduction",
        tenant="profithelm",
        search_volume=4000,
        keyword_difficulty=15.0,
        position_zero_vacant=True,
        jev_score=1.80,
        durable_prob=0.90,
        incumbents=[
            {
                "domain": "generic.com",
                "rank": 1,
                "title": "General Guide",
                "weakness_category": "none",
                "weakness_detail": "none",
            }
        ],
        candidate_angles=[
            {
                "angle_id": "empty-triad-angle",
                "archetype": "Free Interactive Tool/Calculator",
                # Empty target audience niche violates Grant O Triad contract
                "target_audience_niche": "",
                "problem_scope": "Equipment calculations",
                "geographic_or_vertical_bound": "US Tax",
                "primary_value_proposition": "Completely novel and unique calculation methodology",
                "first_party_utility_asset": "novel-calc",
                "divergence_score_min": 0.50,
            }
        ],
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.total_spikes == 1
    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == "DERIVATIVE_SERP_ANGLE"


def test_factory_pipeline_stateless_worker_physics_and_environment_restoration():
    """
    Asserts that FACTORY_* environment variables are restored cleanly
    after scoped execution, preserving stateless worker physics.
    """
    os.environ["FACTORY_CANONICAL_BASE"] = "https://baseline-sentinel.com"
    os.environ["FACTORY_DOMAIN"] = "baseline-sentinel.com"

    spike = _make_spike(
        spike_id="spike-stateless-01",
        query="section 179 equipment expense deduction calculator",
        tenant="profithelm",
        search_volume=3000,
        keyword_difficulty=15.0,
        position_zero_vacant=True,
        jev_score=1.80,
        durable_prob=0.90,
    )

    pipeline = FactoryPipeline()
    result = pipeline.execute([spike])

    assert result.compiled_count == 1

    # Environment variables must be restored to their original values
    assert os.environ.get("FACTORY_CANONICAL_BASE") == "https://baseline-sentinel.com"
    assert os.environ.get("FACTORY_DOMAIN") == "baseline-sentinel.com"

    # Clean up test keys
    del os.environ["FACTORY_CANONICAL_BASE"]
    del os.environ["FACTORY_DOMAIN"]


def test_factory_pipeline_typography_invariants():
    """
    Verifies that all compiled assets and aborted opportunity records
    strictly contain zero em-dashes (U+2014) and zero en-dashes (U+2013).
    """
    spikes = [
        _make_spike(
            spike_id="spike-typo-01",
            query="section 179 equipment expense tax deduction calculator",
            tenant="profithelm",
            search_volume=4000,
            keyword_difficulty=15.0,
            position_zero_vacant=True,
            jev_score=1.80,
            durable_prob=0.90,
        ),
        _make_spike(
            spike_id="spike-typo-02",
            query="viral celebrity meme soundboard",
            tenant="prexvo",
            jev_score=0.10,
            durable_prob=0.05,
            search_volume=5000,
        ),
    ]

    pipeline = FactoryPipeline()
    result = pipeline.execute(spikes)

    assert result.compiled_count == 1
    assert result.aborted_count == 1

    # Compiled asset typography check
    for asset in result.compiled_assets:
        assert_no_forbidden_dashes(asset.query, "compiled asset query")
        assert_no_forbidden_dashes(asset.slug, "compiled asset slug")

    # Aborted opportunity typography check
    for aborted in result.aborted_opportunities:
        assert_no_forbidden_dashes(aborted.query, "aborted opportunity query")
        assert_no_forbidden_dashes(aborted.slug, "aborted opportunity slug")
        assert_no_forbidden_dashes(aborted.reason, "aborted opportunity reason")

    # Rankings typography check
    for rank in result.rankings:
        assert_no_forbidden_dashes(rank.get("query", ""), "ranking query")
        assert_no_forbidden_dashes(rank.get("decision_reason", ""), "ranking decision reason")


def test_run_factory_pipeline_convenience_helper_and_flock_sink(tmp_path):
    """
    Validates run_factory_pipeline convenience helper and atomic flock sink persistence.
    """
    sink_file = tmp_path / "factory_rankings.jsonl"
    config = PipelineConfig(sink_path=sink_file)

    spikes = [
        _make_spike(
            spike_id="spike-sink-01",
            query="section 179 equipment expense tax deduction calculator",
            tenant="profithelm",
            search_volume=4000,
            keyword_difficulty=15.0,
            position_zero_vacant=True,
            jev_score=1.85,
            durable_prob=0.92,
        ),
        _make_spike(
            spike_id="spike-sink-02",
            query="direct consolidation loan repayment assistance plan estimator",
            tenant="prexvo",
            search_volume=3500,
            keyword_difficulty=18.0,
            position_zero_vacant=True,
            jev_score=1.75,
            durable_prob=0.88,
        ),
    ]

    result = run_factory_pipeline(spikes=spikes, config=config)

    assert result.total_spikes == 2
    assert result.compiled_count == 2
    assert sink_file.exists()

    lines = sink_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert "composite_profit_yield" in record
        assert "action" in record


def test_pipeline_closed_loop_indexing_feedback_governor():
    """
    Validates closed-loop indexing feedback governor in FactoryPipeline:
    a) Elevated Jev durability floor bumps from 1.20 to 1.50 under GSC backlog,
       causing marginal candidates (jev_score=1.30) to abort with LOW_JEV_DURABILITY.
    b) High-yield candidates (jev_score=1.80) proceed to compilation.
    c) Quarantined route candidates abort with ALGORITHMIC_EXPANSION_FREEZE.
    Zero em-dashes. Zero en-dashes.
    """
    mock_inspector = MagicMock()
    mock_inspector.audit_gsc_rollover_queue.return_value = {
        "status": "FAIL",
        "queue_size": 250,
        "backlog_exceeded": True,
        "quota_exhausted": False,
        "quota_reasons": ["Backlog exceeded 200 URLs"],
        "sample_urls": [],
    }

    quarantined_slug = "bonus-depreciation-commercial-equipment-allowance-matrix"
    mock_inspector.get_quarantined_urls.return_value = [
        f"https://profithelm.com/tools/{quarantined_slug}/"
    ]
    mock_inspector.quarantined_urls = [
        f"https://profithelm.com/tools/{quarantined_slug}/"
    ]

    # Spike A: Marginal candidate (normally passes at min 1.20, but fails elevated 1.50)
    spike_marginal = _make_spike(
        spike_id="spike-gov-marginal",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
        search_volume=10000,
        cpc_usd=8.5,
        z_score=4.5,
        keyword_difficulty=10.0,
        position_zero_vacant=True,
        jev_score=1.30,
        durable_prob=0.90,
    )

    # Spike B: High-yield candidate (passes elevated 1.50 floor)
    spike_high_yield = _make_spike(
        spike_id="spike-gov-high-yield",
        query="1031 exchange replacement property boot gain tax calculator",
        tenant="profithelm",
        search_volume=10000,
        cpc_usd=8.5,
        z_score=4.5,
        keyword_difficulty=10.0,
        position_zero_vacant=True,
        jev_score=1.80,
        durable_prob=0.90,
    )

    # Spike C: Quarantined candidate (matches quarantined URL)
    spike_quarantined = _make_spike(
        spike_id="spike-gov-quarantined",
        query="bonus depreciation commercial equipment allowance matrix",
        tenant="profithelm",
        search_volume=10000,
        cpc_usd=8.5,
        z_score=4.5,
        keyword_difficulty=10.0,
        position_zero_vacant=True,
        jev_score=1.85,
        durable_prob=0.95,
    )

    config = PipelineConfig(
        enable_indexing_feedback=True,
        min_jev_score=1.20,
        min_durable_prob=0.50,
        adaptive_jev_floor_bump=0.30,
    )

    pipeline = FactoryPipeline(
        config=config,
        indexing_inspector=mock_inspector,
    )

    result = pipeline.execute([spike_marginal, spike_high_yield, spike_quarantined])

    # 1. Verification of counts
    assert result.total_spikes == 3
    assert result.compiled_count == 1
    assert result.aborted_count == 2

    # 2. High-yield candidate proceeded to compilation
    assert len(result.compiled_assets) == 1
    assert result.compiled_assets[0].query == spike_high_yield.query

    # 3. Marginal candidate aborted with LOW_JEV_DURABILITY
    marginal_aborted = next(
        a for a in result.aborted_opportunities if a.query == spike_marginal.query
    )
    assert marginal_aborted.reason == "LOW_JEV_DURABILITY"
    assert marginal_aborted.action == "REJECT"
    assert marginal_aborted.jev_score == 1.30

    # 4. Quarantined candidate aborted with ALGORITHMIC_EXPANSION_FREEZE
    quarantined_aborted = next(
        a for a in result.aborted_opportunities if a.query == spike_quarantined.query
    )
    assert quarantined_aborted.reason == "ALGORITHMIC_EXPANSION_FREEZE"
    assert quarantined_aborted.action == "REJECT"

    # 5. Preflight reports record indexing feedback audit
    assert result.preflight_reports is not None
    assert "indexing_feedback_audit" in result.preflight_reports
    audit = result.preflight_reports["indexing_feedback_audit"]
    assert audit["backlog_exceeded"] is True
    assert audit["feedback_governor_active"] is True
    assert audit["effective_min_jev"] == pytest.approx(1.50)
    assert audit["effective_min_durable"] == pytest.approx(0.60)

