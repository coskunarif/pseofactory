"""
Comprehensive Revenue, Traffic, Cross-Tenant Isolation, and Niche Qualification Test Suite.
Validates across pseofactory, profithelm, and prexvo:
1. Multi-channel trend intake and pre-treg filtering of transient noise and search intent cannibalization.
2. Untangled commercial B2B, consumer financial, Title IV student loan YMYL, and prospective niche expansion scoring.
3. Strict cross-tenant partner and disclosure isolation (ProfitHelm B2B/consumer vs. Prexvo Title IV YMYL).
4. Multi-cycle greenfield niche expansion qualification (3-cycle durability + monetization qualification -> PROPOSE_NEW_APP).
5. Independent corollary checks on compiled content quality, mathematical grounding, and partner alignment.
Zero em-dashes. Zero en-dashes.
"""

import json
import sys
import pytest

# Ensure profithelm and prexvo are importable for cross-tenant integration tests
for repo_dir in ("/home/ubuntuadmin/projects/profithelm-platform", "/home/ubuntuadmin/projects/prexvo"):
    if repo_dir not in sys.path:
        sys.path.insert(0, repo_dir)

from pseofactory.affiliates import (
    B2B_PARTNER_KEYS,
    ENTERPRISE_B2B_PARTNERS,
    RETAIL_TAX_PARTNERS,
    STUDENT_LOAN_PARTNER_KEYS,
    PREXVO_STANDING_RESTRICTION,
    resolve_optimal_partner_for_slug,
    verify_partner_domain_alignment,
)
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.compiler import compile_high_effort_page
from pseofactory.competitor import CompetitorGapEngine
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.maintenance import CrossPropertyContaminationScanner
from pseofactory.qualification import assert_high_effort_content_qualified
from pseofactory.tenant_facts import TenantFactStore
from pseofactory.trends.cron import TrendCronRunner
from pseofactory.trends.jev_engine import JevEngine
from pseofactory.trends.models import FeedSpike, TrendCandidate, TregDurabilityResult
from pseofactory.trends.pipeline import TrendPipeline


def test_untangled_monetization_qualification_and_partner_routing():
    """
    Verifies that qualify_monetization_opportunity and MonetizationHub untangle:
    - commercial_b2b (high CPA enterprise B2B offers, zero retail tax offers)
    - consumer_financial (retail tax, crypto, prediction market offers, zero enterprise B2B offers)
    - student_loan_ymyl (Prexvo Title IV relief & vetted student loan offers, zero B2B offers, mandatory disclosures)
    - prospective_niche_expansion (high-intent greenfield calculators with viable CPC/CPA)
    - unmonetizable_noise (rejected with zero revenue projection)
    """
    hub = MonetizationHub()

    # 1. Commercial B2B intent on ProfitHelm (Section 179 equipment deduction)
    b2b_qual = hub.qualify_opportunity(
        query="section 179 equipment deduction calculator 2026",
        slug="section-179-calculator",
        property_id="profithelm",
        search_volume=6500,
        cpc_usd=9.50,
        jev_score=1.85,
        durable_prob=0.92,
    )
    assert b2b_qual["monetization_qualified"] is True
    assert b2b_qual["property_id"] == "profithelm"
    assert b2b_qual["intent_tier"] == "commercial_b2b"
    assert b2b_qual["primary_partner"] in ("crest_capital", "ramp", "mercury")
    assert set(b2b_qual["recommended_partners"]).isdisjoint(RETAIL_TAX_PARTNERS)
    assert set(b2b_qual["recommended_partners"]).isdisjoint(STUDENT_LOAN_PARTNER_KEYS)
    assert b2b_qual["expected_bounty_usd"] >= 200.0
    assert b2b_qual["partner_alignment_verified"] is True

    # 2. Consumer financial intent on ProfitHelm (TCJA retail tax bracket)
    consumer_qual = hub.qualify_opportunity(
        query="2027 tcja tax bracket calculator",
        slug="2027-tcja-sunset-tax-bracket-calculator",
        property_id="profithelm",
        search_volume=6500,
        cpc_usd=5.20,
        jev_score=1.85,
        durable_prob=0.92,
    )
    assert consumer_qual["monetization_qualified"] is True
    assert consumer_qual["property_id"] == "profithelm"
    assert consumer_qual["intent_tier"] == "consumer_financial"
    assert consumer_qual["primary_partner"] in RETAIL_TAX_PARTNERS
    assert set(consumer_qual["recommended_partners"]).isdisjoint(ENTERPRISE_B2B_PARTNERS)
    assert set(consumer_qual["recommended_partners"]).isdisjoint(STUDENT_LOAN_PARTNER_KEYS)
    assert consumer_qual["partner_alignment_verified"] is True

    # Commercial B2B must yield higher expected bounty and monthly revenue than consumer tax at equal volume
    assert b2b_qual["expected_bounty_usd"] > consumer_qual["expected_bounty_usd"]
    assert b2b_qual["estimated_monthly_revenue_usd"] > consumer_qual["estimated_monthly_revenue_usd"]

    # 3. Prediction market intent untangled from generic retail tax
    pred_tax_partner = resolve_optimal_partner_for_slug("profithelm", "prediction-market-tax-calculator")
    assert pred_tax_partner is not None
    assert pred_tax_partner.key == "coinledger"

    pred_odds_qual = hub.qualify_opportunity(
        query="kalshi prediction market implied probability calculator",
        slug="prediction-market-implied-probability-calculator",
        property_id="profithelm",
        search_volume=4200,
        cpc_usd=4.10,
        jev_score=1.65,
        durable_prob=0.84,
    )
    assert pred_odds_qual["monetization_qualified"] is True
    assert pred_odds_qual["intent_tier"] == "consumer_financial"
    assert "kalshi" in pred_odds_qual["recommended_partners"]
    assert set(pred_odds_qual["recommended_partners"]).isdisjoint(ENTERPRISE_B2B_PARTNERS)

    # 4. Student loan YMYL intent on Prexvo
    prexvo_qual = hub.qualify_opportunity(
        query="rap vs ibr student loan repayment calculator 2026",
        slug="rap-vs-ibr-2026-student-loan-calculator",
        property_id="prexvo",
        search_volume=8900,
        cpc_usd=7.50,
        jev_score=1.82,
        durable_prob=0.91,
    )
    assert prexvo_qual["monetization_qualified"] is True
    assert prexvo_qual["property_id"] == "prexvo"
    assert prexvo_qual["intent_tier"] == "student_loan_ymyl"
    assert set(prexvo_qual["recommended_partners"]).isdisjoint(B2B_PARTNER_KEYS)
    assert prexvo_qual["expected_bounty_usd"] >= 45.0
    assert prexvo_qual["partner_alignment_verified"] is True
    disclosures = prexvo_qual["disclosures_required"]
    assert "ymyl_forfeiture_disclaimer" in disclosures
    assert "permanently eliminates federal protections" in disclosures["ymyl_forfeiture_disclaimer"]
    assert "ftc_disclosure" in disclosures
    assert disclosures["standing_restriction"] == PREXVO_STANDING_RESTRICTION

    # 5. Cross-tenant contamination is strictly rejected on both tenants
    b2b_on_prexvo = hub.qualify_opportunity(
        query="section 179 equipment deduction calculator",
        slug="section-179-calculator",
        property_id="prexvo",
        search_volume=5000,
        cpc_usd=8.0,
    )
    assert b2b_on_prexvo["monetization_qualified"] is False
    assert b2b_on_prexvo["intent_tier"] == "cross_tenant_contamination"
    assert b2b_on_prexvo["partner_alignment_verified"] is False

    student_loan_on_profithelm = hub.qualify_opportunity(
        query="pslf student loan forgiveness calculator",
        slug="pslf-student-loan-calculator",
        property_id="profithelm",
        search_volume=5000,
        cpc_usd=8.0,
    )
    assert student_loan_on_profithelm["monetization_qualified"] is False
    assert student_loan_on_profithelm["intent_tier"] == "cross_tenant_contamination"
    assert student_loan_on_profithelm["partner_alignment_verified"] is False

    # 6. Transient noise is rejected with zero revenue
    noise_qual = hub.qualify_opportunity(
        query="celebrity red carpet oscars dress gossip",
        search_volume=50000,
        cpc_usd=0.10,
    )
    assert noise_qual["monetization_qualified"] is False
    assert noise_qual["intent_tier"] == "unmonetizable_noise"
    assert noise_qual["estimated_monthly_revenue_usd"] == 0.0


def test_jev_engine_untangles_commercial_vs_consumer_yield_and_blocks_contamination():
    """
    Verifies JevEngine.compute_composite_yield and JevEngine.evaluate prioritize commercial B2B
    over consumer financial at identical traffic metrics, enrich candidate_spec with monetization
    qualification and mandatory disclosures, and reject cross-tenant contamination.
    """
    engine = JevEngine()
    shared_treg = TregDurabilityResult(
        query="shared",
        search_volume=4500,
        cpc_usd=6.00,
        competition_index=0.35,
        keyword_difficulty=16.0,
        position_zero_vacant=True,
        historical_stability=0.88,
    )

    b2b_cand = TrendCandidate(
        id="c-b2b",
        query="section 179 commercial equipment depreciation calculator",
        slug="section-179-commercial-equipment-depreciation-calculator",
        source="google_suggest",
        velocity=45.0,
        acceleration=12.0,
        z_score=3.6,
        is_transient_noise=False,
        intent_cluster="calculator",
        discovered_at="2026-10-13T12:00:00Z",
        metadata={"property_id": "profithelm"},
    )
    consumer_cand = TrendCandidate(
        id="c-cons",
        query="standard deduction marginal tax bracket calculator",
        slug="standard-deduction-marginal-tax-bracket-calculator",
        source="google_suggest",
        velocity=45.0,
        acceleration=12.0,
        z_score=3.6,
        is_transient_noise=False,
        intent_cluster="calculator",
        discovered_at="2026-10-13T12:00:00Z",
        metadata={"property_id": "profithelm"},
    )

    b2b_decision = engine.evaluate(b2b_cand, shared_treg, jev_mock={"jev_score": 1.80, "durable_prob": 0.90})
    consumer_decision = engine.evaluate(consumer_cand, shared_treg, jev_mock={"jev_score": 1.80, "durable_prob": 0.90})

    assert b2b_decision.action == "BUILD_PAGE"
    assert consumer_decision.action == "BUILD_PAGE"
    assert b2b_decision.composite_profit_yield > consumer_decision.composite_profit_yield
    assert b2b_decision.candidate_spec["intent_tier"] == "commercial_b2b"
    assert consumer_decision.candidate_spec["intent_tier"] == "consumer_financial"
    assert b2b_decision.candidate_spec["expected_bounty_usd"] > consumer_decision.candidate_spec["expected_bounty_usd"]
    assert set(b2b_decision.candidate_spec["recommended_partners"]).isdisjoint(RETAIL_TAX_PARTNERS)
    assert set(consumer_decision.candidate_spec["recommended_partners"]).isdisjoint(ENTERPRISE_B2B_PARTNERS)

    # Contaminated candidate (B2B query forced onto Prexvo) must be rejected with 0 yield
    contaminated_cand = TrendCandidate(
        id="c-contam",
        query="saas runway burn rate calculator",
        slug="saas-runway-burn-rate-calculator",
        source="google_suggest",
        velocity=55.0,
        acceleration=15.0,
        z_score=4.0,
        is_transient_noise=False,
        intent_cluster="calculator",
        discovered_at="2026-10-13T12:00:00Z",
        metadata={"property_id": "prexvo"},
    )
    contaminated_decision = engine.evaluate(contaminated_cand, shared_treg, jev_mock={"jev_score": 1.85, "durable_prob": 0.92})
    assert contaminated_decision.action == "REJECT"
    assert contaminated_decision.composite_profit_yield == 0.0
    assert "prohibited on Prexvo" in contaminated_decision.decision_reason


def test_pre_treg_noise_and_cannibalization_filtering_across_substrate_and_tenants(monkeypatch, tmp_path):
    """
    Verifies that transient noise spikes, cross-tenant contamination, and search intent
    cannibalization are filtered BEFORE calling external demand tools (treg / DataForSEO)
    across pseofactory TrendPipeline, Prexvo validator, and ProfitHelm scanner.
    """
    # 1. pseofactory TrendPipeline pre-treg gate
    pipeline = TrendPipeline()
    treg_called_queries = []
    orig_check = pipeline.treg_checker.check_query

    def tracked_check_query(q, *args, **kwargs):
        treg_called_queries.append(q)
        return orig_check(q, *args, **kwargs)

    monkeypatch.setattr(pipeline.treg_checker, "check_query", tracked_check_query)

    spikes = [
        FeedSpike(
            id="s-noise",
            query="taylor swift concert outfit gossip 2026",
            source="google_suggest",
            detected_at="2026-10-13T12:00:00Z",
            sample_count=9000,
            velocity=200.0,
            acceleration=-40.0,
            z_score=5.2,
            baseline_mean=10.0,
            baseline_std=2.0,
        ),
        FeedSpike(
            id="s-cannibal",
            query="section 179 deduction calculator",
            source="google_suggest",
            detected_at="2026-10-13T12:00:00Z",
            sample_count=1500,
            velocity=40.0,
            acceleration=10.0,
            z_score=3.5,
            baseline_mean=5.0,
            baseline_std=1.5,
            raw_payload={
                "cannibalization_context": {
                    "matches_existing_slug": "section-179-calculator",
                    "cannibalization_score": 0.85,
                    "current_position": 2.1,  # Top-3 ranking, non-striking -> must not call treg
                }
            },
        ),
        FeedSpike(
            id="s-valid",
            query="section 179d commercial energy deduction calculator",
            source="reddit_autocomplete",
            detected_at="2026-10-13T12:00:00Z",
            sample_count=1200,
            velocity=38.0,
            acceleration=11.0,
            z_score=3.4,
            baseline_mean=4.0,
            baseline_std=1.2,
            raw_payload={
                "treg_mock": {
                    "search_volume": 2800,
                    "cpc_usd": 11.50,
                    "competition_index": 0.38,
                    "keyword_difficulty": 15.0,
                    "position_zero_vacant": True,
                },
                "jev_mock": {"jev_score": 1.82, "durable_prob": 0.93},
            },
        ),
    ]
    report = pipeline.process_spikes(raw_spikes=spikes, sink_path=tmp_path / "voids.jsonl")
    assert treg_called_queries == ["section 179d commercial energy deduction calculator"]
    assert len(report["approved_build"]) == 1

    # 2. Prexvo validate_serp_opportunity pre-treg gate
    import prexvo.validator as px_validator

    prexvo_treg_calls = []

    def mock_prexvo_treg(keywords):
        prexvo_treg_calls.extend(keywords)
        return {k: {"volume": 8400, "kd": 11, "cpc": 8.20} for k in keywords}

    monkeypatch.setattr(px_validator, "query_treg_keywords", mock_prexvo_treg)

    existing_px_tools = [
        {
            "slug": "rap-vs-ibr-2026-student-loan-calculator",
            "primary_keyword": "rap vs ibr student loan calculator",
            "title": "RAP vs IBR Student Loan Calculator",
        }
    ]
    # B2B contamination on Prexvo -> 0 treg calls
    res_b2b = px_validator.validate_serp_opportunity(
        "section 179 commercial equipment tax deduction calculator",
        existing_tools=existing_px_tools,
    )
    assert res_b2b["action"] == "REJECTED"
    assert prexvo_treg_calls == []

    # Exact cannibalizing query on Prexvo -> 0 treg calls
    res_cann = px_validator.validate_serp_opportunity(
        "rap vs ibr student loan calculator",
        existing_tools=existing_px_tools,
    )
    assert res_cann["action"] == "REJECTED"
    assert prexvo_treg_calls == []

    # Valid unserved Title IV student loan void -> 1 treg call and BUILD_IMMEDIATE_ASSET
    res_valid_px = px_validator.validate_serp_opportunity(
        "parent plus double consolidation loophole 2026 calculator",
        existing_tools=existing_px_tools,
    )
    assert res_valid_px["action"] == "BUILD_IMMEDIATE_ASSET"
    assert prexvo_treg_calls == ["parent plus double consolidation loophole 2026 calculator"]

    # 3. ProfitHelm scan_breakout_opportunities pre-intake gate
    import profithelm.scanner as ph_scanner
    import profithelm.validator as ph_validator

    ph_dataforseo_queries = []

    def mock_ph_dataforseo(keywords):
        ph_dataforseo_queries.extend(keywords)
        return [
            {
                "keyword": k,
                "search_volume": 5000,
                "keyword_difficulty": 14,
                "cpc": 7.50,
            }
            for k in keywords
        ]

    monkeypatch.setattr(
        ph_scanner,
        "FINANCIAL_KEYWORDS",
        [*ph_scanner.FINANCIAL_KEYWORDS, "section 174", "amortization", "capitalization"],
    )
    monkeypatch.setattr(ph_scanner, "fetch_google_trends_breakouts", lambda geo="US": [
        {"query": "celebrity oscars red carpet dress meme", "approx_traffic": "100K+", "velocity": "Breakout", "geo": "US"},
        {"query": "pslf student loan forgiveness 2026 calculator", "approx_traffic": "40K+", "velocity": "Breakout", "geo": "US"},
        {"query": "saas runway calculator", "approx_traffic": "20K+", "velocity": "Breakout", "geo": "US", "is_cannibalizing": True},
        {"query": "section 174 r&d capitalization amortization calculator", "approx_traffic": "25K+", "velocity": "Breakout", "geo": "US"},
    ])
    monkeypatch.setattr(ph_scanner, "extract_paa_and_autocomplete_dag", lambda seed, max_depth=1: {"interactive_void_leaves": []})
    monkeypatch.setattr(ph_validator, "query_dataforseo_keywords", mock_ph_dataforseo)

    ph_scanner.scan_breakout_opportunities(limit=5, geo="US", include_community=False, gsc_insights={}, filter_datacenter=False)
    lowered_called = [q.lower() for q in ph_dataforseo_queries]
    assert "celebrity oscars red carpet dress meme" not in lowered_called
    assert "pslf student loan forgiveness 2026 calculator" not in lowered_called
    assert "saas runway calculator" not in lowered_called
    assert "section 174 r&d capitalization amortization calculator" in lowered_called


def test_multi_cycle_prospective_niche_expansion_and_tenant_routing(tmp_path):
    """
    Executes a 3-cycle longitudinal TrendCronRunner scenario across:
    1. Existing tenant ProfitHelm (commercial B2B void)
    2. Existing tenant Prexvo (Title IV student loan void)
    3. Prospective new niche candidate ("freight factoring invoice advance fee calculator")
    Verifies that existing tenants qualify in cycle 1 with strict isolation, while the prospective
    new niche is held in MONITOR for cycles 1-2 and promoted to PROPOSE_NEW_APP on cycle 3 with
    verified monetization qualification and revenue estimates.
    """
    db_path = tmp_path / "trends_longitudinal.db"
    runner = TrendCronRunner(db_path=db_path)
    fixture_file = tmp_path / "cycle_spikes.json"

    spikes_payload = [
        {
            "id": "sp-ph-b2b",
            "query": "cost segregation commercial warehouse depreciation calculator",
            "source": "google_suggest",
            "detected_at": "2026-10-13T12:00:00Z",
            "sample_count": 1800,
            "velocity": 52.0,
            "acceleration": 14.0,
            "z_score": 3.9,
            "baseline_mean": 6.0,
            "baseline_std": 1.5,
            "treg_mock": {
                "search_volume": 4800,
                "cpc_usd": 11.20,
                "competition_index": 0.42,
                "keyword_difficulty": 16.0,
                "position_zero_vacant": True,
                "historical_stability": 0.91,
            },
            "jev_mock": {"jev_score": 1.84, "durable_prob": 0.93},
        },
        {
            "id": "sp-px-ymyl",
            "query": "title iv parent plus double consolidation calculator 2026",
            "source": "reddit_autocomplete",
            "detected_at": "2026-10-13T12:00:00Z",
            "sample_count": 1650,
            "velocity": 46.0,
            "acceleration": 12.5,
            "z_score": 3.7,
            "baseline_mean": 5.5,
            "baseline_std": 1.4,
            "treg_mock": {
                "search_volume": 6200,
                "cpc_usd": 8.40,
                "competition_index": 0.38,
                "keyword_difficulty": 14.0,
                "position_zero_vacant": True,
                "historical_stability": 0.89,
            },
            "jev_mock": {"jev_score": 1.79, "durable_prob": 0.91},
        },
        {
            "id": "sp-new-niche",
            "query": "freight factoring invoice advance fee calculator",
            "source": "youtube_suggest",
            "detected_at": "2026-10-13T12:00:00Z",
            "sample_count": 2200,
            "velocity": 64.0,
            "acceleration": 18.0,
            "z_score": 4.2,
            "baseline_mean": 7.0,
            "baseline_std": 1.8,
            "treg_mock": {
                "search_volume": 5400,
                "cpc_usd": 14.50,
                "competition_index": 0.44,
                "keyword_difficulty": 18.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
            "jev_mock": {"jev_score": 1.88, "durable_prob": 0.94},
        },
    ]
    fixture_file.write_text(json.dumps(spikes_payload), encoding="utf-8")

    # Cycle 1: Existing tenants build immediately; unassigned greenfield niche held in MONITOR (streak=1)
    c1 = runner.run_cycle(cycle_id="cycle_test_001", fixture_path=fixture_file, dry_run=False)
    assert len(c1["approved_build"]) == 2
    assert len(c1["proposals"]) == 0

    by_prop = {b["property_id"]: b for b in c1["approved_build"]}
    assert "profithelm" in by_prop
    assert "prexvo" in by_prop
    assert by_prop["profithelm"]["intent_tier"] == "commercial_b2b"
    assert set(by_prop["profithelm"]["recommended_partners"]).isdisjoint(STUDENT_LOAN_PARTNER_KEYS)
    assert set(by_prop["profithelm"]["recommended_partners"]).isdisjoint(RETAIL_TAX_PARTNERS)
    assert by_prop["prexvo"]["intent_tier"] == "student_loan_ymyl"
    assert set(by_prop["prexvo"]["recommended_partners"]).isdisjoint(B2B_PARTNER_KEYS)
    assert "ymyl_forfeiture_disclaimer" in by_prop["prexvo"]["mandatory_disclosures"]

    # Cycle 2: Unassigned greenfield niche still held in MONITOR (streak=2 < 3)
    c2 = runner.run_cycle(cycle_id="cycle_test_002", fixture_path=fixture_file, dry_run=False)
    assert len(c2["proposals"]) == 0

    # Cycle 3: Unassigned greenfield niche reaches streak=3 and promotes to PROPOSE_NEW_APP
    c3 = runner.run_cycle(cycle_id="cycle_test_003", fixture_path=fixture_file, dry_run=False)
    assert len(c3["proposals"]) == 1
    proposal = c3["proposals"][0]
    assert proposal["cluster_slug"] == "freight-factoring-invoice-advance-fee-calculator"
    assert proposal["consecutive_cycles_sustained"] == 3
    spec = proposal["proposal_spec"]
    assert spec["monetization_qualified"] is True
    assert spec["intent_tier"] == "prospective_niche_expansion"
    assert spec["expected_bounty_usd"] >= 120.0
    assert spec["estimated_monthly_revenue_usd"] > 0.0


def test_independent_corollary_checks_content_quality_and_partner_alignment():
    """
    Executes independent corollary checks on:
    1. MonetizationHub.audit_domain_boundaries() and profithelm.freshness.audit_affiliate_routes()
    2. CompetitorGapEngine.enrich_candidate_spec partner alignment & cross-tenant rejection
    3. Compiled page content quality (compile_high_effort_page + assert_high_effort_content_qualified),
       TenantFactStore.assert_tenant_isolation, CrossPropertyContaminationScanner, and typography hygiene.
    """
    hub = MonetizationHub()
    boundary_audit = hub.audit_domain_boundaries()
    assert boundary_audit["status"] == "PASS", f"Boundary audit failed: {boundary_audit['violations']}"
    assert boundary_audit["violations"] == []

    from profithelm.freshness import audit_affiliate_routes
    from profithelm.observer import HIGH_VALUE_STATUTORY_VOIDS

    ph_route_audit = audit_affiliate_routes()
    assert ph_route_audit["status"] == "PASS", f"ProfitHelm route audit failed: {ph_route_audit['violations']}"

    for void_item in HIGH_VALUE_STATUTORY_VOIDS:
        alignment = verify_partner_domain_alignment(
            "profithelm",
            void_item["slug"],
            void_item.get("affiliates", []),
        )
        assert alignment["aligned"] is True, f"Void spec alignment violation: {alignment['violations']}"

    # CompetitorGapEngine partner alignment and isolation checks
    fact_store = TenantFactStore.get_instance()
    scanner = CrossPropertyContaminationScanner()

    px_gap_engine = CompetitorGapEngine(fact_store.get_profile("prexvo"))
    ph_gap_engine = CompetitorGapEngine(fact_store.get_profile("profithelm"))

    # Reject B2B partner injected onto Prexvo spec
    with pytest.raises(ValueError, match="isolation violation|alignment violation"):
        px_gap_engine.enrich_candidate_spec({
            "query": "rap vs ibr student loan calculator",
            "slug": "rap-vs-ibr-student-loan-calculator",
            "affiliates": ["mercury"],
        })

    # Reject student loan partner injected onto ProfitHelm spec
    with pytest.raises(ValueError, match="isolation violation|alignment violation"):
        ph_gap_engine.enrich_candidate_spec({
            "query": "section 179 deduction calculator",
            "slug": "section-179-calculator",
            "affiliates": ["splash_financial"],
        })

    # Enrich and compile both a Prexvo and a ProfitHelm candidate spec and verify all quality corollaries
    px_spec = px_gap_engine.enrich_candidate_spec({
        "query": "direct consolidation loan repayment calculator",
        "slug": "direct-consolidation-loan-repayment-calculator",
        "title": "Direct Consolidation Loan Weighted Interest & Repayment Calculator",
        "description": "Calculate weighted average interest rates and Title IV repayment schedules under 34 CFR Part 685.",
    })
    ph_spec = ph_gap_engine.enrich_candidate_spec({
        "query": "section 179 equipment deduction calculator",
        "slug": "section-179-equipment-deduction-calculator",
        "title": "Section 179 Commercial Equipment Expensing & Depreciation Calculator",
        "description": "Calculate IRC Section 179 first-year expensing deductions and phase-out thresholds.",
    })

    assert assert_high_effort_content_qualified(px_spec, context="prexvo_spec") is True
    assert assert_high_effort_content_qualified(ph_spec, context="profithelm_spec") is True

    px_compiled = compile_high_effort_page(px_spec)
    ph_compiled = compile_high_effort_page(ph_spec)
    px_html = px_compiled["html"] if isinstance(px_compiled, dict) else str(px_compiled)
    ph_html = ph_compiled["html"] if isinstance(ph_compiled, dict) else str(ph_compiled)

    assert px_compiled.get("verified") is True and ph_compiled.get("verified") is True
    assert "<form" in px_html and 'class="output-value"' in px_html
    assert "<form" in ph_html and 'class="output-value"' in ph_html
    fact_store.assert_tenant_isolation("prexvo", px_html)
    fact_store.assert_tenant_isolation("profithelm", ph_html)
    with pytest.raises(ValueError):
        fact_store.assert_tenant_isolation("prexvo", ph_html)
    with pytest.raises(ValueError):
        fact_store.assert_tenant_isolation("profithelm", px_html)
    assert scanner.scan_text(px_html, "prexvo") == []
    assert scanner.scan_text(ph_html, "profithelm") == []
    assert_no_forbidden_dashes(px_html, context="compiled prexvo html")
    assert_no_forbidden_dashes(ph_html, context="compiled profithelm html")
    assert "Refinancing federal student loans permanently waives" in px_html
    assert "Circular 230" in ph_html
