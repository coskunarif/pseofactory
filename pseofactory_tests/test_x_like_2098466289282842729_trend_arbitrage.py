"""
Tests for x-like:2098466289282842729 (@borjafat / quoted X article 2098138361324347396:
'Ahrefs shows you what was popular. Google Trends shows you what is about to be.')
autonomous trend arbitrage cross-examination, signal velocity, intent qualification,
and closed-loop inflection-to-page routing.
Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path
from unittest.mock import patch

from pseofactory import (
    TENANT_CATEGORY_SEED_TAXONOMY,
    X_LIKE_2098466289282842729_CAPABILITY_MATRIX,
    audit_code_slop_ratchet,
    classify_longitudinal_trajectory,
    drill_down_specific_subtopics,
    evaluate_x_like_2098466289282842729_capability_matrix,
    route_validated_inflection_signals,
)
from pseofactory.trends.collectors import (
    _RSS_FINANCIAL_STATUTORY_TOKENS,
    MultiSourceCollector,
    StatutoryEconomicDatasetCollector,
)
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.trends.filters import NoiseFilter
from pseofactory.trends.jev_engine import JevEngine
from pseofactory.trends.models import (
    FeedSpike,
    RawObservationRecord,
    TregDurabilityResult,
    TrendCandidate,
)
from pseofactory.trends.pipeline import TrendPipeline


def test_capability_matrix_flags_unverified_claims_and_rejects_fragile_dependencies():
    """Verifies primary-evidence cross-examination of all 8 claims in x-like:2098466289282842729."""
    report = evaluate_x_like_2098466289282842729_capability_matrix(include_live_tenant_check=True)
    assert report["status"] == "PASS"
    assert report["passed"] is True
    assert report["pointer"] == "x-like:2098466289282842729"
    assert report["quoted_article_id"] == "2098138361324347396"
    assert report["author_handle"] == "borjafat"
    assert report["total_claims_evaluated"] == 8
    assert report["integrated_compounding_upgrades_count"] == 2
    assert report["integrated_deterministic_gates_count"] == 2
    assert report["already_solved_in_substrate_count"] == 2
    assert report["flagged_unverified_claims_count"] == 1
    assert report["rejected_fragile_or_bloat_count"] == 1

    by_id = {c["claim_id"]: c for c in X_LIKE_2098466289282842729_CAPABILITY_MATRIX}
    # Claim 7: Flagged unverified marketing claim ('New Google Trends feature / GPT-6 automated')
    assert by_id[7]["disposition"] == "FLAGGED_UNVERIFIED_MARKETING_CLAIM"
    assert by_id[7]["verification_status"] == "UNVERIFIED_MARKETING_HYPE_FLAGGED"
    assert "GPT-6" in by_id[7]["claimed_mechanism"]

    # Claim 8: Rejected fragile browser clicking + Distribb SaaS + cold listicle outreach
    assert by_id[8]["disposition"] == "REJECTED_BLOAT_OR_FRAGILE_DEPENDENCY"
    assert "Distribb" in by_id[8]["claimed_mechanism"]


def test_category_seed_taxonomy_and_two_stage_subtopic_drilldown():
    """Verifies Category-First Seed Taxonomy and Stage-2 Sub-Topic Specificity Drill-Down."""
    for tenant in ("profithelm", "prexvo", "gainhelm"):
        assert tenant in TENANT_CATEGORY_SEED_TAXONOMY
        assert len(TENANT_CATEGORY_SEED_TAXONOMY[tenant]) >= 1

    # GainHelm cyber/GRC tokens must be covered in RSS filter tokens
    for tok in ("soc 2", "cmmc", "sprs", "nist 800", "iso 27001", "hipaa", "pci dss"):
        assert tok in _RSS_FINANCIAL_STATUTORY_TOKENS

    subs_ph = drill_down_specific_subtopics("section 179 calculator", property_id="profithelm", max_subtopics=5)
    assert len(subs_ph) == 5
    assert all(len(s.split()) >= 3 for s in subs_ph)
    assert any("phaseout" in s or "schedule" in s for s in subs_ph)

    subs_gh = drill_down_specific_subtopics("cmmc level 2", property_id="gainhelm", max_subtopics=4)
    assert len(subs_gh) == 4
    assert any("audit cost calculator" in s for s in subs_gh)

    collector = MultiSourceCollector(collectors=[StatutoryEconomicDatasetCollector()])
    drill_res = collector.harvest_category_drilldown(property_id="prexvo", drill_down_top_k=2)
    assert drill_res["property_id"] == "prexvo"
    assert len(drill_res["top_parent_topics"]) == 2
    assert len(drill_res["drilled_subtopics"]) >= 4
    assert drill_res["specific_spikes_count"] >= 4
    assert all(len(sp.query.split()) >= 3 for sp in drill_res["spikes"])


def test_breakout_low_baseline_trap_and_relative_index_qualification():
    """
    Verifies Step 2 & Step 4 qualification:
    - >5,000% 'Breakout' starting from near-zero search volume (<100/mo) is classified as
      BREAKOUT_LOW_BASELINE_TRAP and held in MONITOR (never BUILD_PAGE).
    - Relative 0-100 Google Trends index without volume verification is never treated as search volume.
    """
    trap_res = classify_longitudinal_trajectory(
        query="obscure micro tax rumor calculator",
        growth_pct=5800.0,
        is_breakout=True,
        search_volume=45,
        cpc_usd=0.30,
    )
    assert trap_res["classification"] == "BREAKOUT_LOW_BASELINE_TRAP"
    assert trap_res["is_viable"] is False
    assert trap_res["relative_index_is_not_search_volume"] is True
    assert trap_res["recommended_action"] == "HOLD_LOW_BASELINE_TRAP"

    rel_only = classify_longitudinal_trajectory(
        query="unverified trend index query",
        is_breakout=True,
        relative_index_0_100=100.0,
        search_volume=None,
    )
    assert rel_only["classification"] == "BREAKOUT_LOW_BASELINE_TRAP"
    assert rel_only["recommended_action"] == "REQUIRE_VOLUME_CROSS_CHECK"

    engine = JevEngine()
    cand = TrendCandidate(
        id="trap_cand_1",
        query="section 179 obscure micro breakout calculator",
        slug="section-179-obscure-micro-breakout-calculator",
        source="google_suggest",
        discovered_at="2026-10-28T00:00:00Z",
        velocity=92.0,
        acceleration=20.0,
        z_score=4.5,
        intent_cluster="calculator",
        metadata={"is_breakout": True, "growth_pct": 6200.0, "property_id": "profithelm"},
    )
    treg_low_vol = TregDurabilityResult(
        query=cand.query,
        search_volume=40,
        cpc_usd=3.50,
        keyword_difficulty=12.0,
        position_zero_vacant=True,
    )
    decision = engine.evaluate(
        candidate=cand,
        treg_result=treg_low_vol,
        jev_mock={"jev_score": 2.4, "durable_prob": 0.85},
    )
    assert decision.action == "MONITOR"
    assert decision.passed_thresholds is False
    assert "Breakout (>5,000% growth)" in decision.decision_reason


def test_five_year_longitudinal_trajectory_decay_vs_sustained_and_seasonal(tmp_path: Path):
    """
    Verifies Step 4 multi-horizon 5-year longitudinal trajectory gating:
    - POST_SPIKE_DECAY is rejected by both NoiseFilter and JevEngine.
    - SEASONAL_PRE_PEAK and SUSTAINED_GROWTH are approved.
    - TrendPipeline enriches longitudinal history from TrendHistoryDB when available.
    """
    decay_res = classify_longitudinal_trajectory(
        query="one time tax rebate rumor calculator",
        series=[15.0, 98.0, 44.0, 28.0, 12.0],
        velocity=12.0,
        acceleration=-16.0,
        search_volume=600,
    )
    assert decay_res["classification"] == "POST_SPIKE_DECAY"
    assert decay_res["is_viable"] is False

    seasonal_res = classify_longitudinal_trajectory(
        query="section 179 annual deadline tax calculator",
        series=[25.0, 82.0, 30.0, 85.0, 35.0, 62.0],
        velocity=62.0,
        acceleration=14.0,
        search_volume=1400,
    )
    assert seasonal_res["classification"] == "SEASONAL_PRE_PEAK"
    assert seasonal_res["is_viable"] is True
    assert seasonal_res["jev_multiplier"] > 1.0

    sustained_res = classify_longitudinal_trajectory(
        query="qsbs section 1202 state conformity tax calculator",
        series=[20.0, 34.0, 49.0, 66.0, 82.0],
        velocity=82.0,
        acceleration=16.0,
        search_volume=950,
    )
    assert sustained_res["classification"] == "SUSTAINED_GROWTH"
    assert sustained_res["is_viable"] is True

    # Verify NoiseFilter rejects POST_SPIKE_DECAY even when instantaneous acceleration > 0
    nf = NoiseFilter()
    decay_spike = FeedSpike(
        id="sp_decay_1",
        query="expired stimulus check calculator",
        source="google_suggest",
        detected_at="2026-10-28T00:00:00Z",
        sample_count=500,
        velocity=20.0,
        acceleration=2.0,
        z_score=2.5,
        baseline_mean=10.0,
        baseline_std=3.0,
        raw_payload={"longitudinal_series": [20.0, 95.0, 50.0, 32.0, 20.0]},
    )
    passes, reason, _ = nf.evaluate_spike(decay_spike, search_volume=500)
    assert passes is False
    assert "peaked earlier" in reason

    # Verify TrendPipeline enriches longitudinal history from TrendHistoryDB
    db_file = tmp_path / "trend_hist.db"
    tdb = TrendHistoryDB(db_file)
    q_hist = "corporate amt camt book income minimum tax calculator"
    obs_list = []
    for idx, vel_val in enumerate([100.0, 38.0, 22.0]):
        cyc_id = f"cyc_{idx + 1}"
        tdb.start_cycle(cyc_id, seeds=[q_hist], sources=["google_suggest"])
        obs_list.append(
            RawObservationRecord(
                observation_id=f"obs_{idx + 1}",
                cycle_id=cyc_id,
                source="google_suggest",
                query=q_hist,
                normalized_query=q_hist,
                rank_position=1,
                observed_velocity=vel_val,
                observed_acceleration=-10.0 if idx > 0 else 15.0,
                observed_z_score=2.8,
                observed_at=f"2026-0{idx + 1}-01T00:00:00Z",
            )
        )
    tdb.record_observations(obs_list)
    pipe = TrendPipeline(db=tdb)
    spike_with_db_decay = FeedSpike(
        id="sp_db_decay",
        query=q_hist,
        source="google_suggest",
        detected_at="2026-10-28T00:00:00Z",
        sample_count=800,
        velocity=22.0,
        acceleration=3.0,
        z_score=2.6,
        baseline_mean=10.0,
        baseline_std=3.0,
        raw_payload={
            "property_id": "profithelm",
            "treg_mock": {
                "search_volume": 800,
                "cpc_usd": 5.0,
                "keyword_difficulty": 15.0,
                "position_zero_vacant": True,
            },
            "jev_mock": {"jev_score": 2.2, "durable_prob": 0.80},
        },
    )
    pipe_res = pipe.process_spikes([spike_with_db_decay])
    tdb.close()
    assert len(pipe_res["rejected"]) == 1
    assert pipe_res["rejected"][0]["action"] == "REJECT"
    assert "peaked earlier" in pipe_res["rejected"][0]["decision_reason"]


def test_closed_loop_inflection_signal_routing_existing_vs_new(tmp_path: Path):
    """
    Verifies Step 4 existing-page check and closed-loop routing:
    - Matching existing tools route to UPGRADE_EXISTING_PAGE (REFACTOR_PAGE with 28-day lock).
    - Orthogonal validated voids route to BUILD_NEW_PAGE (BUILD_PAGE).
    - Low-baseline breakouts and post-spike decay are held/rejected.
    """
    tools_dir = tmp_path / "dist" / "tools" / "r-and-d-tax-credit-section-174-amortization-calculator"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "index.html").write_text("<html><head><title>Section 174 Calculator</title></head><body></body></html>", encoding="utf-8")

    signals = [
        {
            "query": "section 174 research credit capitalization amortization calculator",
            "velocity": 88.0,
            "acceleration": 18.0,
            "search_volume": 1100,
            "cpc_usd": 6.50,
            "growth_pct": 190.0,
            "longitudinal_series": [25.0, 42.0, 58.0, 74.0, 88.0],
            "matching_tool": "r-and-d-tax-credit-section-174-amortization-calculator",
        },
        {
            "query": "corporate amt camt book income minimum tax calculator",
            "velocity": 94.0,
            "acceleration": 21.0,
            "search_volume": 1450,
            "cpc_usd": 8.20,
            "growth_pct": 240.0,
            "longitudinal_series": [18.0, 35.0, 54.0, 76.0, 94.0],
        },
        {
            "query": "tiny baseline breakout tax rumor calculator",
            "velocity": 90.0,
            "acceleration": 25.0,
            "search_volume": 30,
            "cpc_usd": 0.25,
            "growth_pct": 7500.0,
            "is_breakout": True,
        },
        {
            "query": "collapsed post spike tax rebate calculator",
            "velocity": 15.0,
            "acceleration": -12.0,
            "search_volume": 500,
            "cpc_usd": 2.10,
            "longitudinal_series": [20.0, 96.0, 40.0, 22.0, 15.0],
        },
    ]

    routing = route_validated_inflection_signals(
        property_id="profithelm",
        repo_root=tmp_path,
        candidate_signals=signals,
        persist=True,
    )
    assert routing["status"] == "PASS"
    assert routing["total_signals_evaluated"] == 4
    assert routing["upgrade_existing_page_count"] == 1
    assert routing["build_new_page_count"] == 1
    assert routing["held_low_baseline_traps_count"] == 1
    assert routing["rejected_post_spike_decay_count"] == 1

    upg = routing["validated_refactor_routes"][0]
    assert upg["routed_action"] == "UPGRADE_EXISTING_PAGE"
    assert upg["engine_action"] == "REFACTOR_PAGE"
    assert upg["target_slug"] == "r-and-d-tax-credit-section-174-amortization-calculator"
    assert upg["measurement_lock_days"] == 28

    bld = routing["validated_build_routes"][0]
    assert bld["routed_action"] == "BUILD_NEW_PAGE"
    assert bld["engine_action"] == "BUILD_PAGE"
    assert bld["target_subroute"] == "/tools/corporate-amt-camt-book-income-minimum-tax-calculator/"
    assert (tmp_path / ".agy" / "inflection_signal_routing.json").is_file()


def test_code_slop_ratchet_and_zero_forbidden_dashes():
    """Verifies AST slop ratchet (0 duplicate AST blocks and <=450 lines on all new/modified functions) and zero forbidden dashes."""
    repo_root = Path("/home/ubuntuadmin/projects/pseofactory")
    slop_report = audit_code_slop_ratchet(repo_root / "pseofactory")
    assert slop_report["duplicate_ast_blocks"] == 0, f"Duplicate AST blocks found: {slop_report['duplicate_functions']}"
    oversized_names = {
        (item["file"], item["function"])
        for item in slop_report.get("oversized_functions", [])
    }
    for file_name, fn_name in (
        ("collectors.py", "drill_down_specific_subtopics"),
        ("collectors.py", "harvest_category_drilldown"),
        ("filters.py", "classify_longitudinal_trajectory"),
        ("jev_engine.py", "evaluate"),
        ("pipeline.py", "process_spikes"),
        ("seo_growth_loops.py", "route_validated_inflection_signals"),
        ("verifier.py", "evaluate_x_like_2098466289282842729_capability_matrix"),
    ):
        assert (file_name, fn_name) not in oversized_names, f"Function {file_name}::{fn_name} exceeded 450 lines"

    for rel_file in (
        "pseofactory/trends/collectors.py",
        "pseofactory/trends/filters.py",
        "pseofactory/trends/jev_engine.py",
        "pseofactory/trends/pipeline.py",
        "pseofactory/seo_growth_loops.py",
        "pseofactory/verifier.py",
        "pseofactory_tests/test_x_like_2098466289282842729_trend_arbitrage.py",
    ):
        txt = (repo_root / rel_file).read_text(encoding="utf-8")
        assert "\u2014" not in txt, f"Found forbidden em-dash in {rel_file}"
        assert "\u2013" not in txt, f"Found forbidden en-dash in {rel_file}"
