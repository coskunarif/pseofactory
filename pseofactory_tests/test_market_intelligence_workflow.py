"""
Comprehensive Test Suite for pseofactory Market Intelligence Workflow & Multi-Domain Gap Closure.
Verifies:
1. Closure of the property_filter blindspot via include_unassigned=True so tenant maintenance cycles
   accumulate and promote unassigned greenfield niche clusters without polluting tenant builds.
2. Expanded greenfield discovery seeds in DEFAULT_CRON_SEEDS beyond ProfitHelm and Prexvo.
3. Three-pillar Market Intelligence scoring:
   - Pillar 1: Buyer Intent (transactional modifiers, CPC intensity, statutory/financial urgency, B2B deal size)
   - Pillar 2: Organic Ranking Difficulty (inverse KD, Position 0 vacancy, SERP weakness, deterministic moat)
   - Pillar 3: Active Commission Offers (verified CPA/revshare bounties, network density, instant approval, payout speed)
4. End-to-end MarketIntelligenceEngine workflow, SQLite persistence (market_intel_candidates + niche_cluster_proposals),
   and CLI `market-intel` subcommand execution.
5. 100% preservation of all existing guardrails (3-cycle durability gate, cross-tenant contamination firewall,
   Prexvo Title IV YMYL standing restrictions, and zero em/en-dashes).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from pseofactory.affiliates import qualify_monetization_opportunity
from pseofactory.cli import build_parser, cmd_market_intel, main
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.maintenance import CrossPropertyContaminationScanner
from pseofactory.market_intel import (
    GREENFIELD_VERTICAL_CATALOG,
    MarketIntelligenceEngine,
    match_greenfield_vertical,
    score_active_commission_offers,
    score_buyer_intent,
    score_ranking_difficulty,
)
from pseofactory.trends.cron import (
    DEFAULT_CRON_SEEDS,
    GREENFIELD_DISCOVERY_SEEDS,
    TrendCronRunner,
)
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.trends.jev_engine import JevEngine
from pseofactory.trends.models import TrendCandidate
from pseofactory.trends.treg_checker import TregChecker


def test_greenfield_discovery_seeds_and_offline_heuristics():
    """
    Verifies Gap 2 & Gap 4 closures:
    - DEFAULT_CRON_SEEDS includes GREENFIELD_DISCOVERY_SEEDS beyond ProfitHelm and Prexvo.
    - TregChecker._offline_heuristic and JevEngine.resolve_jev_metrics recognize greenfield
      commercial calculators and grant durable commercial metrics.
    """
    for seed in GREENFIELD_DISCOVERY_SEEDS:
        assert seed in DEFAULT_CRON_SEEDS

    checker = TregChecker()
    jev = JevEngine()

    for v_id, v_spec in GREENFIELD_VERTICAL_CATALOG.items():
        anchor = v_spec["anchor_tools"][0]
        query = anchor["query"]

        treg_res = checker.check_query(query, remaining_budget=0.0)
        assert treg_res.search_volume >= 3000
        assert treg_res.cpc_usd >= 10.0
        assert treg_res.keyword_difficulty <= 25.0
        assert treg_res.position_zero_vacant is True
        assert treg_res.historical_stability >= 0.88

        cand = TrendCandidate(
            id=f"cand-{v_id}",
            query=query,
            slug=anchor["slug"],
            source="google_suggest",
        )
        jev_metrics = jev.resolve_jev_metrics(cand)
        assert jev_metrics["jev_score"] >= 1.65
        assert jev_metrics["durable_prob"] >= 0.82


def test_three_pillar_scoring_buyer_intent_ranking_difficulty_and_active_commissions():
    """
    Verifies Gap 3 & Gap 5 closures:
    - score_buyer_intent distinguishes high-ticket B2B commercial calculators from low-intent queries.
    - score_ranking_difficulty rewards low KD, Position 0 vacancy, SERP weakness, and calculation moats.
    - score_active_commission_offers returns verified active affiliate programs with real networks and bounties.
    """
    high_intent = score_buyer_intent(
        "workers compensation class code rate calculator by state",
        cpc_usd=28.40,
    )
    low_intent = score_buyer_intent(
        "what is the history of insurance",
        cpc_usd=0.40,
    )
    assert high_intent.buyer_intent_score >= 85.0
    assert high_intent.commercial_deal_value_tier == "HIGH_TICKET_B2B"
    assert high_intent.buyer_intent_score > low_intent.buyer_intent_score + 40.0

    easy_rank = score_ranking_difficulty(
        "section 301 tariff landed cost calculator hts",
        keyword_difficulty=15.0,
        position_zero_vacant=True,
        serp_weakness_count=4,
    )
    hard_rank = score_ranking_difficulty(
        "generic term",
        keyword_difficulty=78.0,
        position_zero_vacant=False,
        serp_weakness_count=0,
    )
    assert easy_rank.ease_of_ranking_score >= 85.0
    assert easy_rank.estimated_days_to_top_10 <= 25
    assert easy_rank.ease_of_ranking_score > hard_rank.ease_of_ranking_score + 50.0
    assert easy_rank.estimated_days_to_top_10 < hard_rank.estimated_days_to_top_10

    comm = score_active_commission_offers(
        "workers compensation class code rate calculator by state",
        cpc_usd=28.40,
    )
    assert comm.vertical_id == "commercial_surety_insurance"
    assert comm.commission_offer_score >= 80.0
    assert comm.active_offers_count >= 4
    assert comm.instant_active_offers_count >= 2
    assert comm.primary_offer is not None
    assert comm.primary_offer.partner_key in (
        "simply_business",
        "suretybonds_direct",
        "next_insurance_b2b",
        "thimble_contractor",
    )
    assert comm.expected_bounty_usd >= 135.0
    assert len(comm.networks_represented) >= 2

    # Verify qualify_monetization_opportunity surfaces real greenfield offers while preserving contract keys
    qual = qualify_monetization_opportunity(
        query="section 301 tariff landed cost calculator hts",
        slug="section-301-tariff-landed-cost-calculator-hts",
        property_id="unassigned",
        search_volume=6800,
        cpc_usd=14.60,
        jev_score=1.91,
        durable_prob=0.95,
    )
    assert qual["monetization_qualified"] is True
    assert qual["intent_tier"] == "prospective_niche_expansion"
    assert qual["vertical_id"] == "customs_freight_logistics"
    assert qual["recommended_tenant_id"] == "freighttariff"
    assert qual["recommended_domain"] == "freighttariff.com"
    assert qual["active_offers_count"] >= 4
    assert any(
        p in qual["recommended_partners"]
        for p in ("otr_solutions_factoring", "shipbob_3pl", "freightos_marketplace", "easyship_commerce")
    )


def test_property_filter_include_unassigned_closes_tenant_confinement_gap(tmp_path: Path):
    """
    Verifies Gap 1 closure:
    When MaintenanceLifecycle runs per-tenant with property_filter='prexvo' and include_unassigned=True:
    1. Prexvo queries are routed to Prexvo's approved_build.
    2. Unassigned greenfield queries are NOT dropped; they are evaluated and persisted to keyword_history,
       property_assignments, treg_metric_snapshots, and jev_evaluations.
    3. Unassigned greenfield queries NEVER pollute Prexvo's approved_build or refactor_pages.
    4. After 3 consecutive cycles, the unassigned greenfield query unlocks PROPOSE_NEW_APP in
       niche_cluster_proposals with full 3-pillar market_intelligence enrichment.
    """
    db_file = tmp_path / "gap1_closure.db"
    fixture_file = tmp_path / "mixed_tenant_and_greenfield.json"

    spikes = [
        {
            "id": "sp-prexvo-1",
            "query": "title iv student loan repayment assistance plan calculator",
            "source": "google_suggest",
            "velocity": 54.0,
            "acceleration": 14.0,
            "z_score": 3.6,
            "treg_mock": {
                "search_volume": 3600,
                "cpc_usd": 7.20,
                "keyword_difficulty": 16.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
            "jev_mock": {"jev_score": 1.82, "durable_prob": 0.91},
        },
        {
            "id": "sp-greenfield-1",
            "query": "workers compensation class code rate calculator by state",
            "source": "google_suggest",
            "velocity": 68.0,
            "acceleration": 20.0,
            "z_score": 4.2,
            "treg_mock": {
                "search_volume": 6400,
                "cpc_usd": 28.40,
                "keyword_difficulty": 16.0,
                "position_zero_vacant": True,
                "historical_stability": 0.92,
            },
            "jev_mock": {"jev_score": 1.92, "durable_prob": 0.95},
        },
    ]
    fixture_file.write_text(json.dumps(spikes), encoding="utf-8")

    runner = TrendCronRunner(db_path=db_file, min_yield=60.0)

    # Cycle 1 with property_filter="prexvo" and include_unassigned=True (as MaintenanceLifecycle calls it)
    c1 = runner.run_cron_cycle(
        cycle_id="cycle_gap1_01",
        fixture_path=fixture_file,
        property_filter="prexvo",
        include_unassigned=True,
        dry_run=False,
    )
    # Prexvo build contains ONLY the prexvo query, never the unassigned query
    assert len(c1["approved_build"]) == 1
    assert c1["approved_build"][0]["property_id"] == "prexvo"
    # Unassigned query is tracked in monitored on Cycle 1 (3-cycle durability guardrail intact)
    assert len(c1["monitored"]) == 1
    assert c1["monitored"][0]["property_id"] == "unassigned"
    assert c1["monitored"][0]["consecutive_cycles"] == 1
    assert len(c1["proposals"]) == 0

    # Cycle 2 with property_filter="profithelm" and include_unassigned=True
    c2 = runner.run_cron_cycle(
        cycle_id="cycle_gap1_02",
        fixture_path=fixture_file,
        property_filter="profithelm",
        include_unassigned=True,
        dry_run=False,
    )
    assert len(c2["approved_build"]) == 0  # Prexvo query filtered out when running for profithelm
    assert len(c2["monitored"]) == 1
    assert c2["monitored"][0]["property_id"] == "unassigned"
    assert c2["monitored"][0]["consecutive_cycles"] == 2
    assert len(c2["proposals"]) == 0

    # Cycle 3 with property_filter="prexvo" and include_unassigned=True -> promotes to PROPOSE_NEW_APP!
    c3 = runner.run_cron_cycle(
        cycle_id="cycle_gap1_03",
        fixture_path=fixture_file,
        property_filter="prexvo",
        include_unassigned=True,
        dry_run=False,
    )
    assert len(c3["approved_build"]) == 1
    assert c3["approved_build"][0]["property_id"] == "prexvo"
    assert len(c3["proposals"]) == 1

    prop = c3["proposals"][0]
    assert prop["cluster_slug"] == "workers-compensation-class-code-rate-calculator-by-state"
    assert prop["consecutive_cycles_sustained"] == 3
    spec = prop["proposal_spec"]
    assert "market_intelligence" in spec
    mi = spec["market_intelligence"]
    assert mi["recommended_tenant_id"] == "insurebond"
    assert mi["recommended_domain"] == "insurebond.com"
    assert mi["fast_money_score"] >= 85.0
    assert mi["buyer_intent_score"] >= 85.0
    assert mi["ease_of_ranking_score"] >= 85.0
    assert mi["commission_offer_score"] >= 80.0
    assert len(mi["active_commission_offers"]) >= 4
    assert spec["blueprint"]["tenant_id"] == "insurebond"


def test_market_intelligence_engine_ranking_db_sync_and_cli(tmp_path: Path, capsys):
    """
    Verifies end-to-end MarketIntelligenceEngine workflow:
    - Evaluates all 6 greenfield tenant candidates.
    - Verifies 100% cross-tenant isolation against ProfitHelm and Prexvo.
    - Persists candidates to market_intel_candidates and 3-cycle proposals to niche_cluster_proposals.
    - Executes `pseofactory market-intel` CLI in both JSON and table modes with zero forbidden dashes.
    """
    db_file = tmp_path / "market_intel_e2e.db"
    out_json = tmp_path / "market_intel_report.json"

    engine = MarketIntelligenceEngine(db_path=db_file)
    report = engine.run_workflow(
        sync_db=True,
        simulate_three_cycle_confirmation=True,
        output_path=out_json,
    )

    assert report["status"] == "COMPLETED"
    assert report["total_new_tenant_candidates_evaluated"] == 6
    assert report["persisted_to_db_count"] == 6
    assert report["confirmed_niche_proposals_in_db"] >= 6
    assert out_json.is_file()

    candidates = report["top_new_tenant_candidates"]
    assert len(candidates) == 6

    # Verify top 3 fastest-money candidates are InsureBond, FreightTariff, and BuildMargin / CyberAudit
    top_ids = [c["tenant_id"] for c in candidates[:3]]
    assert "insurebond" in top_ids
    assert "freighttariff" in top_ids

    scanner = CrossPropertyContaminationScanner()
    for rank_idx, cand in enumerate(candidates, start=1):
        assert cand["rank"] == rank_idx
        assert cand["fast_money_score"] >= 75.0
        assert cand["buyer_intent_score"] >= 80.0
        assert cand["ease_of_ranking_score"] >= 80.0
        assert cand["commission_offer_score"] >= 75.0
        assert cand["projected_monthly_revenue_usd"] > 1000.0
        assert 12 <= cand["estimated_days_to_first_dollar"] <= 45
        assert cand["isolation_boundary_verified"] is True
        assert len(cand["active_commission_offers"]) >= 3
        assert len(cand["anchor_tools"]) >= 4
        for tool in cand["anchor_tools"]:
            assert scanner.scan_text(tool["query"], "profithelm") == []
            assert scanner.scan_text(tool["query"], "prexvo") == []

    # Verify SQLite persistence
    with TrendHistoryDB(db_file) as db:
        stored_candidates = db.get_market_intel_candidates(min_fast_money_score=70.0)
        assert len(stored_candidates) == 6
        assert stored_candidates[0]["rank"] == 1

        stored_proposals = db.get_niche_proposals(status="PROPOSED")
        assert len(stored_proposals) >= 6

    # Verify CLI execution (--json and human-readable table and --query)
    ret_json = main([
        "market-intel",
        "--db-path", str(db_file),
        "--top", "3",
        "--json",
    ])
    assert ret_json == 0
    captured_json = capsys.readouterr().out
    assert_no_forbidden_dashes(captured_json, "cli_market_intel_json")
    parsed_cli = json.loads(captured_json)
    assert len(parsed_cli["top_new_tenant_candidates"]) == 3

    ret_table = main([
        "market-intel",
        "--db-path", str(db_file),
        "--top", "3",
    ])
    assert ret_table == 0
    captured_table = capsys.readouterr().out
    assert_no_forbidden_dashes(captured_table, "cli_market_intel_table")
    assert "PSEOFACTORY MARKET INTELLIGENCE: TOP NEW TENANT CANDIDATES" in captured_table

    ret_query = main([
        "market-intel",
        "--db-path", str(db_file),
        "--query", "section 301 tariff landed cost calculator by hts code",
        "--json",
    ])
    assert ret_query == 0
    captured_query = capsys.readouterr().out
    assert_no_forbidden_dashes(captured_query, "cli_market_intel_query")
    parsed_query = json.loads(captured_query)
    assert parsed_query["recommended_tenant_id"] == "freighttariff"
