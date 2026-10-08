"""
Integration test simulating 3 consecutive daily crawl runs (Cycle 1, Cycle 2, Cycle 3).
Verifies:
1. Multi-cycle longitudinal trend accumulation in history SQLite database.
2. Ephemeral 1-day spike produces zero new app proposals and vanishes.
3. Cross-tenant token contamination is quarantined and fails closed.
4. Existing Prexvo and ProfitHelm assets receive validated improvement actions.
5. Sustained unassigned niche breakout on Day 3 unlocks PROPOSE_NEW_APP with structured proposal.
6. Universal idempotency on replaying cycle execution.
Zero em-dashes. Zero en-dashes.
"""

import json
from pathlib import Path
import pytest

from pseofactory.trends.cron import TrendCronRunner
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.cli import build_parser, cmd_trend_cron


def test_three_cycle_simulation_and_ephemeral_gating(tmp_path: Path):
    """
    Simulates Day 1, Day 2, Day 3 cron execution cycles:
    - Day 1: Ephemeral spike, Prexvo build, ProfitHelm refactor, sustained unassigned niche (streak 1).
    - Day 2: Ephemeral spike disappears; sustained unassigned niche accumulates (streak 2).
    - Day 3: Sustained niche reaches streak 3 and unlocks PROPOSE_NEW_APP.
    - Replay: Re-running Day 3 produces identical DB state with zero duplicate rows.
    """
    db_file = tmp_path / "cron_simulation.db"

    # -------------------------------------------------------------------------
    # Fixture Payloads for Cycle 1, 2, 3
    # -------------------------------------------------------------------------
    day1_payload = [
        # 1. Noise item: entertainment gossip (should be rejected)
        {
            "id": "spike-d1-01",
            "query": "zendaya oscars dress designer 2026",
            "source": "google_suggest",
            "velocity": 90.0,
            "acceleration": 20.0,
            "z_score": 4.5,
            "search_volume": 60000,
            "cpc_usd": 0.15,
        },
        # 2. Ephemeral viral spike: high volume, unassigned, but 1-day fad
        {
            "id": "spike-d1-02",
            "query": "viral fidget gadget 2026",
            "source": "google_suggest",
            "velocity": 85.0,
            "acceleration": 25.0,
            "z_score": 4.0,
            "treg_mock": {
                "search_volume": 50000,
                "cpc_usd": 2.50,
                "keyword_difficulty": 15.0,
                "position_zero_vacant": True,
                "historical_stability": 0.85,
            },
        },
        # 3. Prexvo tenant item: student loan statutory compliance (BUILD_PAGE)
        {
            "id": "spike-d1-03",
            "query": "title iv student loan repayment assistance plan calculator",
            "source": "google_suggest",
            "velocity": 45.0,
            "acceleration": 12.0,
            "z_score": 3.2,
            "treg_mock": {
                "search_volume": 3200,
                "cpc_usd": 6.80,
                "keyword_difficulty": 18.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
        },
        # 4. ProfitHelm tenant item: Section 1031 striking distance (REFACTOR_PAGE)
        {
            "id": "spike-d1-04",
            "query": "section 1031 exchange replacement property timeline calculator",
            "source": "reddit_autocomplete",
            "velocity": 40.0,
            "acceleration": 8.0,
            "z_score": 2.8,
            "matching_tool": "1031-exchange-identification-deadlines",
            "current_position": 8.5,
            "treg_mock": {
                "search_volume": 2800,
                "cpc_usd": 12.50,
                "keyword_difficulty": 28.0,
                "position_zero_vacant": False,
                "historical_stability": 0.88,
            },
        },
        # 5. Sustained unassigned niche candidate: Day 1 appearance
        {
            "id": "spike-d1-05",
            "query": "contractor lien release statutory matrix by state",
            "source": "google_suggest",
            "velocity": 55.0,
            "acceleration": 14.0,
            "z_score": 3.5,
            "treg_mock": {
                "search_volume": 4500,
                "cpc_usd": 14.80,
                "keyword_difficulty": 20.0,
                "position_zero_vacant": True,
                "historical_stability": 0.88,
            },
        },
        # 6. Cross-tenant contamination item: Prexvo query poisoned with ProfitHelm foreign token
        {
            "id": "spike-d1-06",
            "query": "pslf direct consolidation loan section 1031 exchange",
            "source": "google_suggest",
            "velocity": 30.0,
            "acceleration": 5.0,
            "z_score": 2.5,
            "treg_mock": {
                "search_volume": 1200,
                "cpc_usd": 4.00,
                "keyword_difficulty": 15.0,
                "position_zero_vacant": True,
            },
        },
    ]

    day2_payload = [
        # Notice: "viral fidget gadget 2026" has completely vanished
        # Prexvo item: streak 2
        {
            "id": "spike-d2-03",
            "query": "title iv student loan repayment assistance plan calculator",
            "source": "google_suggest",
            "velocity": 52.0,
            "acceleration": 15.0,
            "z_score": 3.6,
            "treg_mock": {
                "search_volume": 3400,
                "cpc_usd": 6.80,
                "keyword_difficulty": 18.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
        },
        # ProfitHelm item: streak 2
        {
            "id": "spike-d2-04",
            "query": "section 1031 exchange replacement property timeline calculator",
            "source": "reddit_autocomplete",
            "velocity": 44.0,
            "acceleration": 10.0,
            "z_score": 3.0,
            "matching_tool": "1031-exchange-identification-deadlines",
            "current_position": 8.0,
            "treg_mock": {
                "search_volume": 2900,
                "cpc_usd": 12.50,
                "keyword_difficulty": 28.0,
                "position_zero_vacant": False,
                "historical_stability": 0.88,
            },
        },
        # Sustained unassigned niche: streak 2
        {
            "id": "spike-d2-05",
            "query": "contractor lien release statutory matrix by state",
            "source": "google_suggest",
            "velocity": 62.0,
            "acceleration": 18.0,
            "z_score": 3.8,
            "treg_mock": {
                "search_volume": 4700,
                "cpc_usd": 14.80,
                "keyword_difficulty": 20.0,
                "position_zero_vacant": True,
                "historical_stability": 0.88,
            },
        },
    ]

    day3_payload = [
        # Prexvo item: streak 3
        {
            "id": "spike-d3-03",
            "query": "title iv student loan repayment assistance plan calculator",
            "source": "google_suggest",
            "velocity": 58.0,
            "acceleration": 16.0,
            "z_score": 3.9,
            "treg_mock": {
                "search_volume": 3500,
                "cpc_usd": 7.00,
                "keyword_difficulty": 18.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
        },
        # ProfitHelm item: streak 3
        {
            "id": "spike-d3-04",
            "query": "section 1031 exchange replacement property timeline calculator",
            "source": "reddit_autocomplete",
            "velocity": 48.0,
            "acceleration": 11.0,
            "z_score": 3.2,
            "matching_tool": "1031-exchange-identification-deadlines",
            "current_position": 7.5,
            "treg_mock": {
                "search_volume": 3000,
                "cpc_usd": 12.80,
                "keyword_difficulty": 28.0,
                "position_zero_vacant": False,
                "historical_stability": 0.88,
            },
        },
        # Sustained unassigned niche: streak 3
        {
            "id": "spike-d3-05",
            "query": "contractor lien release statutory matrix by state",
            "source": "google_suggest",
            "velocity": 70.0,
            "acceleration": 22.0,
            "z_score": 4.1,
            "treg_mock": {
                "search_volume": 5100,
                "cpc_usd": 15.20,
                "keyword_difficulty": 20.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
        },
    ]

    day1_file = tmp_path / "day1.json"
    day2_file = tmp_path / "day2.json"
    day3_file = tmp_path / "day3.json"

    day1_file.write_text(json.dumps(day1_payload), encoding="utf-8")
    day2_file.write_text(json.dumps(day2_payload), encoding="utf-8")
    day3_file.write_text(json.dumps(day3_payload), encoding="utf-8")

    runner = TrendCronRunner(db_path=db_file, min_yield=60.0)

    # =========================================================================
    # EXECUTION 1: Day 1 Cron Run
    # =========================================================================
    res1 = runner.run_cycle(cycle_id="cycle-sim-day1", fixture_path=day1_file)
    assert res1["status"] == "COMPLETED"
    assert res1["filtered_noise_count"] == 1  # Zendaya gossip rejected
    assert len(res1["proposals"]) == 0  # CRITICAL: 0 proposals on Day 1

    # Check Prexvo BUILD_PAGE
    assert len(res1["approved_build"]) >= 1
    assert any(b["property_id"] == "prexvo" for b in res1["approved_build"])

    # Check ProfitHelm REFACTOR_PAGE with 28-day lock
    assert len(res1["refactor_pages"]) >= 1
    ph_refactor = next(r for r in res1["refactor_pages"] if r["property_id"] == "profithelm")
    assert ph_refactor["matching_tool"] == "1031-exchange-identification-deadlines"
    assert "locked_until" in ph_refactor

    # Check Cross-tenant contamination quarantined
    rej_queries = [r["query"] for r in res1["rejected"]]
    assert "pslf direct consolidation loan section 1031 exchange" in rej_queries

    # Check Ephemeral viral spike is held in MONITOR, NOT proposed
    mon_queries = [m["query"] for m in res1["monitored"]]
    assert "viral fidget gadget 2026" in mon_queries
    assert "contractor lien release statutory matrix by state" in mon_queries

    with TrendHistoryDB(db_file) as db:
        gadget_rec = db.get_keyword_history("viral-fidget-gadget-2026")
        assert gadget_rec is not None
        assert gadget_rec.consecutive_cycles_count == 1
        assert gadget_rec.status == "candidate"

        niche_rec1 = db.get_keyword_history("contractor-lien-release-statutory-matrix-by-state")
        assert niche_rec1 is not None
        assert niche_rec1.consecutive_cycles_count == 1
        assert niche_rec1.status == "candidate"

    # =========================================================================
    # EXECUTION 2: Day 2 Cron Run
    # =========================================================================
    res2 = runner.run_cycle(cycle_id="cycle-sim-day2", fixture_path=day2_file)
    assert res2["status"] == "COMPLETED"
    assert len(res2["proposals"]) == 0  # CRITICAL: Still 0 proposals on Day 2

    with TrendHistoryDB(db_file) as db:
        # Ephemeral spike was not seen in Day 2: streak remains 1, total cycles remains 1
        gadget_rec2 = db.get_keyword_history("viral-fidget-gadget-2026")
        assert gadget_rec2.consecutive_cycles_count == 1
        assert gadget_rec2.total_cycles_count == 1

        # Sustained niche was seen in Day 2: streak becomes 2
        niche_rec2 = db.get_keyword_history("contractor-lien-release-statutory-matrix-by-state")
        assert niche_rec2.consecutive_cycles_count == 2
        assert niche_rec2.total_cycles_count == 2
        assert niche_rec2.status == "observed"

    # =========================================================================
    # EXECUTION 3: Day 3 Cron Run
    # =========================================================================
    res3 = runner.run_cycle(cycle_id="cycle-sim-day3", fixture_path=day3_file)
    assert res3["status"] == "COMPLETED"

    # CRITICAL: Day 3 reaches streak >= 3 and unlocks PROPOSE_NEW_APP
    assert len(res3["proposals"]) == 1
    proposal = res3["proposals"][0]
    assert proposal["cluster_slug"] == "contractor-lien-release-statutory-matrix-by-state"
    assert proposal["consecutive_cycles_sustained"] == 3
    assert proposal["mean_composite_yield"] >= 70.0
    assert proposal["treg_stability_index"] >= 0.80
    assert proposal["aggregate_search_volume"] == 5100
    assert proposal["status"] == "PROPOSED"
    assert "blueprint" in proposal["proposal_spec"]

    with TrendHistoryDB(db_file) as db:
        niche_rec3 = db.get_keyword_history("contractor-lien-release-statutory-matrix-by-state")
        assert niche_rec3.consecutive_cycles_count == 3
        assert niche_rec3.status == "action_ready"

        db_proposals = db.get_niche_proposals(status="PROPOSED")
        assert len(db_proposals) == 1
        assert db_proposals[0].cluster_slug == "contractor-lien-release-statutory-matrix-by-state"

        # Check total observations count before replay
        conn = db.get_connection()
        obs_count_before = conn.execute("SELECT COUNT(*) FROM raw_crawl_observations;").fetchone()[0]
        eval_count_before = conn.execute("SELECT COUNT(*) FROM jev_evaluations;").fetchone()[0]

    # =========================================================================
    # EXECUTION 4: Idempotency Replay on Day 3
    # =========================================================================
    res3_replay = runner.run_cycle(cycle_id="cycle-sim-day3", fixture_path=day3_file)
    assert res3_replay["status"] == "COMPLETED"

    with TrendHistoryDB(db_file) as db:
        conn = db.get_connection()
        obs_count_after = conn.execute("SELECT COUNT(*) FROM raw_crawl_observations;").fetchone()[0]
        eval_count_after = conn.execute("SELECT COUNT(*) FROM jev_evaluations;").fetchone()[0]

        # Invariant: 0 duplicate rows generated
        assert obs_count_after == obs_count_before
        assert eval_count_after == eval_count_before

        # Invariant: streak count remains 3 (not incremented on replay)
        niche_replay = db.get_keyword_history("contractor-lien-release-statutory-matrix-by-state")
        assert niche_replay.consecutive_cycles_count == 3
        assert niche_replay.total_cycles_count == 3


def test_cli_trend_cron_subcommand(tmp_path: Path):
    """Verifies pseofactory trend-cron CLI entrypoint parses args and executes cleanly."""
    db_file = tmp_path / "cli_trends.db"
    fixture_file = tmp_path / "cli_fixture.json"
    fixture_payload = [
        {
            "query": "title iv student loan repayment assistance plan calculator",
            "source": "google_suggest",
            "search_volume": 3000,
            "cpc_usd": 5.0,
            "keyword_difficulty": 15.0,
            "position_zero_vacant": True,
        }
    ]
    fixture_file.write_text(json.dumps(fixture_payload), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args([
        "trend-cron",
        "--db-path", str(db_file),
        "--fixture", str(fixture_file),
        "--cycle-id", "cycle-cli-test-01",
        "--min-yield", "60.0",
        "--json",
    ])
    ret = cmd_trend_cron(args)
    assert ret == 0

    # Verify db populated
    with TrendHistoryDB(db_file) as db:
        cycle = db.get_cycle("cycle-cli-test-01")
        assert cycle is not None
        assert cycle.status == "COMPLETED"
        assert cycle.total_raw_observations == 1
