"""
Unit and integration tests for pseofactory trend history backfill engine.
Verifies:
1. FlexibleSchemaAdapter normalization across historical eras (Era 1, Era 2, fixtures).
2. Chronological ordering, longitudinal streak progression, and discrete second-derivative acceleration.
3. Multi-cycle unassigned niche cluster proposal generation.
4. Advisory file locking and contention backoff.
5. Universal idempotency on re-running backfill (zero duplicate rows, zero streak increments).
6. Strict SQLite referential integrity (PRAGMA foreign_key_check is clean).
Zero em-dashes. Zero en-dashes.
"""

import os
import json
import fcntl
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timezone

from pseofactory.trends.backfill import (
    FlexibleSchemaAdapter,
    HistoricalSessionCrawler,
    IdempotentBulkInserter,
    StagedCycleBatch,
    RawStagedRecord,
    run_trend_backfill,
)
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.cli import build_parser, cmd_trend_backfill


def test_schema_adapter_legacy_profithelm_void():
    """Validates Era 1 profithelm.void_candidate.v1 normalization."""
    adapter = FlexibleSchemaAdapter()
    legacy_item = {
        "schema": "profithelm.void_candidate.v1",
        "id": "cand_7cd6e7e00498",
        "status": "REJECTED",
        "slug": "add-funding-rate-liquidation-distance",
        "primary_keyword": "add funding rate liquidation distance calculator",
        "title": "Add Funding Rate Liquidation Distance Calculator 2026-2027",
        "quick_answer": "Quantitative deterministic calculation model.",
        "primary_citation": "mobile://probe/test3",
        "source": "mobile_probe",
        "timestamp": "2026-09-24T22:08:37.877831+00:00",
        "demand": {
            "volume": 120,
            "search_volume": 120,
            "kd": 15.0,
            "cpc_usd": 2.25,
            "position_zero_vacant": True,
            "historical_stability": 0.90,
        },
        "jev_causal_probability": 0.65,
        "rice_score": 45.0,
    }

    rec = adapter.normalize_record(legacy_item, source_origin="test_era1")
    assert rec.query == "add funding rate liquidation distance calculator"
    assert rec.normalized_query == "add funding rate liquidation distance calculator"
    assert rec.query_slug == "add-funding-rate-liquidation-distance"
    assert rec.source == "mobile_probe"
    assert rec.action == "REJECT"  # REJECTED -> REJECT
    assert rec.search_volume == 120
    assert rec.cpc_usd == 2.25
    assert rec.keyword_difficulty == 15.0
    assert rec.position_zero_vacant == 1
    assert rec.historical_stability == 0.90
    assert rec.durable_prob == 0.65
    assert rec.composite_profit_yield == 45.0
    assert rec.observed_at == "2026-09-24T22:08:37Z"

    # Built mapping test
    legacy_built = dict(legacy_item, status="BUILT")
    rec_built = adapter.normalize_record(legacy_built, source_origin="test_era1_built")
    assert rec_built.action == "BUILD_PAGE"


def test_schema_adapter_jev_decision_result():
    """Validates Era 2 JevDecisionResult normalization and offline fallbacks."""
    adapter = FlexibleSchemaAdapter()
    era2_item = {
        "query": "section 179 vehicle bonus depreciation calculator",
        "slug": "section-179-vehicle-bonus-depreciation-calculator",
        "action": "BUILD_PAGE",
        "jev_score": 1.85,
        "durable_prob": 0.72,
        "composite_profit_yield": 88.5,
        "cannibalization_risk": 0.10,
        "target_asset_type": "interactive_calculator",
        "decision_reason": "High yield statutory token match",
        "passed_thresholds": True,
        "evaluated_at": "2026-10-08T21:12:31.456898+00:00",
    }

    rec = adapter.normalize_record(era2_item, source_origin="test_era2")
    assert rec.query == "section 179 vehicle bonus depreciation calculator"
    assert rec.query_slug == "section-179-vehicle-bonus-depreciation-calculator"
    assert rec.action == "BUILD_PAGE"
    assert rec.jev_score == 1.85
    assert rec.durable_prob == 0.72
    assert rec.composite_profit_yield == 88.5
    assert rec.cannibalization_risk == 0.10
    assert rec.property_id == "profithelm"  # Statutory token match
    assert rec.search_volume == 0  # Offline fallback
    assert rec.cpc_usd == 1.50     # Offline fallback
    assert rec.keyword_difficulty == 20.0  # Offline fallback
    assert rec.position_zero_vacant == 1
    assert rec.historical_stability == 0.85


def test_schema_adapter_anti_slop_and_slug_sanitization():
    """Validates removal of forbidden em/en dashes and strict slug validation."""
    adapter = FlexibleSchemaAdapter()
    slop_item = {
        "query": "title iv \u2014 student loan \u2013 forgiveness calculator",
        "slug": "title-iv-loan",
        "action": "MONITOR",
        "timestamp": "2026-09-24T12:00:00Z",
    }
    rec = adapter.normalize_record(slop_item, source_origin="test_slop")
    assert "\u2014" not in rec.query
    assert "\u2013" not in rec.query
    assert "\u2014" not in rec.normalized_query
    assert "\u2013" not in rec.normalized_query
    assert rec.query_slug == "title-iv-loan"
    assert rec.property_id == "prexvo"


def test_chronological_ordering_and_streaks(tmp_path: Path):
    """
    Validates chronological progression across simulated cycles:
    - Verifies consecutive streaks increment on successive cycles.
    - Verifies discrete second-derivative acceleration calculation.
    - Verifies unassigned query sustained across 3 cycles produces a NicheClusterProposal.
    """
    db_file = tmp_path / "test_streaks.db"
    db = TrendHistoryDB(db_file)

    adapter = FlexibleSchemaAdapter()

    # Create 3 cycle batches for query "commercial solar battery investment calculator"
    # Cycle 1: v=20.0
    # Cycle 2: v=30.0
    # Cycle 3: v=45.0
    records_c1 = [
        adapter.normalize_record({
            "query": "commercial solar battery investment calculator",
            "velocity": 20.0,
            "timestamp": "2026-10-01T10:00:00Z",
            "demand": {"search_volume": 1200, "cpc_usd": 4.50, "historical_stability": 0.88, "position_zero_vacant": True, "kd": 22.0},
            "composite_profit_yield": 82.0,
            "jev_score": 1.75,
            "durable_prob": 0.70,
        })
    ]
    records_c2 = [
        adapter.normalize_record({
            "query": "commercial solar battery investment calculator",
            "velocity": 30.0,
            "timestamp": "2026-10-01T11:00:00Z",
            "demand": {"search_volume": 1200, "cpc_usd": 4.50, "historical_stability": 0.88, "position_zero_vacant": True, "kd": 22.0},
            "composite_profit_yield": 82.0,
            "jev_score": 1.75,
            "durable_prob": 0.70,
        })
    ]
    records_c3 = [
        adapter.normalize_record({
            "query": "commercial solar battery investment calculator",
            "velocity": 45.0,
            "timestamp": "2026-10-01T12:00:00Z",
            "demand": {"search_volume": 1200, "cpc_usd": 4.50, "historical_stability": 0.88, "position_zero_vacant": True, "kd": 22.0},
            "composite_profit_yield": 82.0,
            "jev_score": 1.75,
            "durable_prob": 0.70,
        })
    ]

    batches = [
        StagedCycleBatch(cycle_id="cycle_backfill_20261001_1000", executed_at="2026-10-01T10:00:00Z", records=records_c1, seeds_used=["solar"], sources=["test"]),
        StagedCycleBatch(cycle_id="cycle_backfill_20261001_1100", executed_at="2026-10-01T11:00:00Z", records=records_c2, seeds_used=["solar"], sources=["test"]),
        StagedCycleBatch(cycle_id="cycle_backfill_20261001_1200", executed_at="2026-10-01T12:00:00Z", records=records_c3, seeds_used=["solar"], sources=["test"]),
    ]

    inserter = IdempotentBulkInserter(db=db)
    summary = inserter.bulk_insert(batches)

    assert summary["status"] == "SUCCESS"
    assert summary["cycles_completed"] == 3
    assert summary["total_proposals_created"] == 1

    slug = "commercial-solar-battery-investment-calculator"
    kw = db.get_keyword_history(slug)
    assert kw is not None
    assert kw.consecutive_cycles_count == 3
    assert kw.total_cycles_count == 3
    assert kw.latest_velocity == 45.0
    # Velocity delta: 45.0 - 30.0 = 15.0
    assert kw.velocity_delta == 15.0
    # Discrete second-derivative acceleration: v_t - 2*v_{t-1} + v_{t-2} = 45.0 - 2*(30.0) + 20.0 = 5.0
    assert kw.acceleration_2nd_deriv == 5.0

    # Niche proposal created
    proposals = db.get_niche_proposals()
    assert len(proposals) == 1
    assert proposals[0].cluster_slug == slug
    assert proposals[0].consecutive_cycles_sustained == 3
    assert proposals[0].status == "PROPOSED"


def test_idempotent_reexecution(tmp_path: Path):
    """
    Universal Idempotency Invariant:
    Asserts that replaying backfill against an existing database yields:
    - 0 new rows across all tables
    - 0 streak increments
    - 0 broken records
    """
    db_file = tmp_path / "test_idempotency.db"
    db = TrendHistoryDB(db_file)

    adapter = FlexibleSchemaAdapter()
    records = [
        adapter.normalize_record({
            "query": "section 1031 exchange replacement property timeline calculator",
            "velocity": 15.0,
            "timestamp": "2026-10-02T08:00:00Z",
            "demand": {"search_volume": 800, "cpc_usd": 3.00},
        }),
        adapter.normalize_record({
            "query": "student loan save plan monthly amortization calculator",
            "velocity": 25.0,
            "timestamp": "2026-10-02T08:00:00Z",
            "demand": {"search_volume": 1500, "cpc_usd": 2.10},
        }),
    ]

    batch = StagedCycleBatch(
        cycle_id="cycle_backfill_20261002_0800",
        executed_at="2026-10-02T08:00:00Z",
        records=records,
        seeds_used=["1031", "save"],
        sources=["test"],
    )

    inserter = IdempotentBulkInserter(db=db)

    # First execution
    res1 = inserter.bulk_insert([batch])
    assert res1["cycles_completed"] == 1
    assert res1["cycles_skipped"] == 0

    conn = db.get_connection()
    c_cycles_1 = conn.execute("SELECT count(*) FROM crawl_cycles").fetchone()[0]
    c_obs_1 = conn.execute("SELECT count(*) FROM raw_crawl_observations").fetchone()[0]
    c_kw_1 = conn.execute("SELECT count(*) FROM keyword_history").fetchone()[0]
    c_pa_1 = conn.execute("SELECT count(*) FROM property_assignments").fetchone()[0]
    c_ts_1 = conn.execute("SELECT count(*) FROM treg_metric_snapshots").fetchone()[0]
    c_je_1 = conn.execute("SELECT count(*) FROM jev_evaluations").fetchone()[0]

    kw1 = db.get_keyword_history("section-1031-exchange-replacement-property-timeline-calculator")
    assert kw1.consecutive_cycles_count == 1

    # Second execution (Replay)
    res2 = inserter.bulk_insert([batch])
    assert res2["cycles_completed"] == 0
    assert res2["cycles_skipped"] == 1
    assert res2["total_observations_inserted"] == 0
    assert res2["total_keywords_upserted"] == 0

    c_cycles_2 = conn.execute("SELECT count(*) FROM crawl_cycles").fetchone()[0]
    c_obs_2 = conn.execute("SELECT count(*) FROM raw_crawl_observations").fetchone()[0]
    c_kw_2 = conn.execute("SELECT count(*) FROM keyword_history").fetchone()[0]
    c_pa_2 = conn.execute("SELECT count(*) FROM property_assignments").fetchone()[0]
    c_ts_2 = conn.execute("SELECT count(*) FROM treg_metric_snapshots").fetchone()[0]
    c_je_2 = conn.execute("SELECT count(*) FROM jev_evaluations").fetchone()[0]

    # Row counts strictly invariant
    assert c_cycles_1 == c_cycles_2
    assert c_obs_1 == c_obs_2
    assert c_kw_1 == c_kw_2
    assert c_pa_1 == c_pa_2
    assert c_ts_1 == c_ts_2
    assert c_je_1 == c_je_2

    # Streak strictly invariant
    kw2 = db.get_keyword_history("section-1031-exchange-replacement-property-timeline-calculator")
    assert kw2.consecutive_cycles_count == 1
    assert kw2.total_cycles_count == 1


def test_advisory_file_locking_contention(tmp_path: Path):
    """Asserts that IdempotentBulkInserter respects advisory file locking on <db_path>.lock."""
    db_file = tmp_path / "test_locking.db"
    lock_file = tmp_path / "test_locking.db.lock"
    db = TrendHistoryDB(db_file)

    adapter = FlexibleSchemaAdapter()
    records = [
        adapter.normalize_record({
            "query": "cost segregation bonus depreciation deduction model",
            "timestamp": "2026-10-03T10:00:00Z",
        })
    ]
    batch = StagedCycleBatch(
        cycle_id="cycle_backfill_20261003_1000",
        executed_at="2026-10-03T10:00:00Z",
        records=records,
    )

    # Hold external advisory lock
    lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o666)
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    inserter = IdempotentBulkInserter(db=db, max_lock_retries=2, initial_backoff=0.05, max_backoff=0.1)

    try:
        # Should raise OSError or BlockingIOError due to lock contention after retries
        with pytest.raises((BlockingIOError, OSError)):
            inserter.bulk_insert([batch])
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    # Now that lock is released, insertion succeeds
    res = inserter.bulk_insert([batch])
    assert res["status"] == "SUCCESS"
    assert res["cycles_completed"] == 1


def test_referential_integrity_pragmas(tmp_path: Path):
    """
    Validates SQLite foreign key integrity:
    PRAGMA foreign_key_check must be empty.
    Zero orphaned foreign key references.
    """
    db_file = tmp_path / "test_fk.db"
    db = TrendHistoryDB(db_file)

    adapter = FlexibleSchemaAdapter()
    records = [
        adapter.normalize_record({
            "query": "pslf direct consolidation loan repayment estimator",
            "timestamp": "2026-10-04T14:00:00Z",
            "demand": {"search_volume": 450, "cpc_usd": 1.75},
        }),
        adapter.normalize_record({
            "query": "commercial clean energy 179d deduction tax model",
            "timestamp": "2026-10-04T14:00:00Z",
            "demand": {"search_volume": 900, "cpc_usd": 5.20},
        }),
    ]

    batch = StagedCycleBatch(
        cycle_id="cycle_backfill_20261004_1400",
        executed_at="2026-10-04T14:00:00Z",
        records=records,
        seeds_used=["pslf", "179d"],
        sources=["test"],
    )

    inserter = IdempotentBulkInserter(db=db)
    inserter.bulk_insert([batch])

    conn = db.get_connection()
    fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(fk_errors) == 0

    # Explicit referential integrity assertion query
    orphan_query = """
    SELECT 
      (SELECT count(*) FROM raw_crawl_observations WHERE cycle_id NOT IN (SELECT cycle_id FROM crawl_cycles)) +
      (SELECT count(*) FROM property_assignments WHERE cycle_id NOT IN (SELECT cycle_id FROM crawl_cycles) OR query_slug NOT IN (SELECT query_slug FROM keyword_history)) +
      (SELECT count(*) FROM treg_metric_snapshots WHERE cycle_id NOT IN (SELECT cycle_id FROM crawl_cycles) OR query_slug NOT IN (SELECT query_slug FROM keyword_history)) +
      (SELECT count(*) FROM jev_evaluations WHERE cycle_id NOT IN (SELECT cycle_id FROM crawl_cycles) OR query_slug NOT IN (SELECT query_slug FROM keyword_history)) +
      (SELECT count(*) FROM crawl_cycles WHERE status != 'COMPLETED') as total_violations;
    """
    violations = conn.execute(orphan_query).fetchone()[0]
    assert violations == 0


def test_cli_trend_backfill_subcommand(tmp_path: Path):
    """Asserts that CLI subcommand trend-backfill executes cleanly with --dry-run and --json."""
    db_file = tmp_path / "cli_backfill.db"
    staging_dir = tmp_path / "staging"
    dlq_path = tmp_path / "dlq.jsonl"

    parser = build_parser()
    args = parser.parse_args([
        "trend-backfill",
        "--db-path", str(db_file),
        "--staging-dir", str(staging_dir),
        "--dlq-path", str(dlq_path),
        "--dry-run",
        "--json",
    ])

    exit_code = cmd_trend_backfill(args)
    assert exit_code == 0
