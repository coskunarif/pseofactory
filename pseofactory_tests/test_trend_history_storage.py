"""
Unit tests for pseofactory SQLite Trend History Persistence Database.
Verifies WAL concurrency, atomic locking, foreign key constraints,
longitudinal streak counting, second-derivative acceleration, and idempotency.
Zero em-dashes. Zero en-dashes.
"""

import os
import sqlite3
import pytest
from pathlib import Path

from pseofactory.trends.db import TrendHistoryDB
from pseofactory.trends.models import (
    CrawlCycleRecord,
    RawObservationRecord,
    LongitudinalKeywordRecord,
    PropertyAssignmentRecord,
    TregSnapshotRecord,
    JevEvaluationRecord,
    NicheClusterProposal,
)


def test_schema_and_wal_pragmas(tmp_path: Path):
    """Verifies schema bootstrap, WAL journal mode, and busy timeout configuration."""
    db_file = tmp_path / "test_trends.db"
    with TrendHistoryDB(db_file) as db:
        conn = db.get_connection()

        # Check WAL mode
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal"

        # Check busy timeout
        busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert busy_timeout == 5000

        # Check foreign keys
        foreign_keys = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert foreign_keys == 1

        # Check all 7 tables exist
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            ).fetchall()
        ]
        expected_tables = [
            "crawl_cycles",
            "jev_evaluations",
            "keyword_history",
            "niche_cluster_proposals",
            "property_assignments",
            "raw_crawl_observations",
            "treg_metric_snapshots",
        ]
        for t in expected_tables:
            assert t in tables, f"Expected table {t} missing from schema"


def test_atomic_file_locking(tmp_path: Path):
    """Verifies non-blocking advisory file lock prevents overlapping writes."""
    db_file = tmp_path / "test_locked.db"
    db1 = TrendHistoryDB(db_file)
    db2 = TrendHistoryDB(db_file)

    with db1.acquire_lock(non_blocking=True):
        # Second instance must fail to acquire the lock non-blockingly
        with pytest.raises((BlockingIOError, OSError)):
            with db2.acquire_lock(non_blocking=True):
                pass

    # After releasing, second instance can acquire the lock
    with db2.acquire_lock(non_blocking=True):
        pass

    db1.close()
    db2.close()


def test_cycle_lifecycle_and_idempotency(tmp_path: Path):
    """Verifies cycle creation, completion, and idempotent replay."""
    db_file = tmp_path / "test_cycles.db"
    with TrendHistoryDB(db_file) as db:
        # Start cycle 1
        cycle1 = db.start_cycle(
            cycle_id="cycle-20261008-01",
            seeds=["calculator", "tax"],
            sources=["google_suggest"],
            metadata={"run_env": "test"},
        )
        assert cycle1.cycle_id == "cycle-20261008-01"
        assert cycle1.status == "RUNNING"
        assert cycle1.seeds_used == ["calculator", "tax"]

        # Re-starting the same cycle returns existing record (idempotent)
        cycle1_dup = db.start_cycle(
            cycle_id="cycle-20261008-01",
            seeds=["other"],
            sources=["other"],
        )
        assert cycle1_dup.cycle_id == "cycle-20261008-01"
        assert cycle1_dup.seeds_used == ["calculator", "tax"]

        # Complete cycle 1
        db.complete_cycle(
            cycle_id="cycle-20261008-01",
            total_raw_observations=10,
            unique_queries_count=5,
            status="COMPLETED",
            metadata={"duration_ms": 120},
        )

        completed = db.get_cycle("cycle-20261008-01")
        assert completed is not None
        assert completed.status == "COMPLETED"
        assert completed.total_raw_observations == 10
        assert completed.unique_queries_count == 5


def test_streak_counting_and_gap_reset(tmp_path: Path):
    """
    Verifies consecutive daily streak accumulation across consecutive cycles,
    streak invariant on replay, and reset to 1 when a gap occurs.
    """
    db_file = tmp_path / "test_streaks.db"
    with TrendHistoryDB(db_file) as db:
        # Day 1
        db.start_cycle("cycle-day1", ["calc"], ["google_suggest"])
        rec1 = db.upsert_keyword_history(
            query_slug="form-8829-calculator",
            query="form 8829 calculator",
            cycle_id="cycle-day1",
            observed_velocity=20.0,
            intent_cluster="calculator",
            property_id="profithelm",
            observed_at="2026-10-08T04:00:00Z",
        )
        assert rec1.consecutive_cycles_count == 1
        assert rec1.total_cycles_count == 1
        assert rec1.status == "candidate"
        db.complete_cycle("cycle-day1", 1, 1)

        # Replay Day 1: streak and total cycle count MUST NOT increase
        rec1_replay = db.upsert_keyword_history(
            query_slug="form-8829-calculator",
            query="form 8829 calculator",
            cycle_id="cycle-day1",
            observed_velocity=20.0,
            intent_cluster="calculator",
            property_id="profithelm",
            observed_at="2026-10-08T04:00:00Z",
        )
        assert rec1_replay.consecutive_cycles_count == 1
        assert rec1_replay.total_cycles_count == 1

        # Day 2: consecutive
        db.start_cycle("cycle-day2", ["calc"], ["google_suggest"])
        rec2 = db.upsert_keyword_history(
            query_slug="form-8829-calculator",
            query="form 8829 calculator",
            cycle_id="cycle-day2",
            observed_velocity=35.0,
            intent_cluster="calculator",
            property_id="profithelm",
            observed_at="2026-10-09T04:00:00Z",
        )
        assert rec2.consecutive_cycles_count == 2
        assert rec2.total_cycles_count == 2
        assert rec2.status == "observed"
        assert rec2.velocity_delta == 15.0
        db.complete_cycle("cycle-day2", 1, 1)

        # Day 3: consecutive
        db.start_cycle("cycle-day3", ["calc"], ["google_suggest"])
        rec3 = db.upsert_keyword_history(
            query_slug="form-8829-calculator",
            query="form 8829 calculator",
            cycle_id="cycle-day3",
            observed_velocity=50.0,
            intent_cluster="calculator",
            property_id="profithelm",
            observed_at="2026-10-10T04:00:00Z",
        )
        assert rec3.consecutive_cycles_count == 3
        assert rec3.total_cycles_count == 3
        assert rec3.status == "stabilized"
        db.complete_cycle("cycle-day3", 1, 1)

        # Introduce Day 4 without our query (gap)
        db.start_cycle("cycle-day4", ["other"], ["google_suggest"])
        db.complete_cycle("cycle-day4", 0, 0)

        # Day 5: query returns after gap. Streak should reset to 1
        db.start_cycle("cycle-day5", ["calc"], ["google_suggest"])
        rec5 = db.upsert_keyword_history(
            query_slug="form-8829-calculator",
            query="form 8829 calculator",
            cycle_id="cycle-day5",
            observed_velocity=40.0,
            intent_cluster="calculator",
            property_id="profithelm",
            observed_at="2026-10-12T04:00:00Z",
        )
        assert rec5.consecutive_cycles_count == 1
        assert rec5.total_cycles_count == 4
        db.complete_cycle("cycle-day5", 1, 1)


def test_discrete_second_derivative_acceleration(tmp_path: Path):
    """
    Verifies calculation of discrete second-derivative acceleration:
    A_t = v_t - 2*v_{t-1} + v_{t-2} per HWL-1215.
    """
    db_file = tmp_path / "test_accel.db"
    with TrendHistoryDB(db_file) as db:
        # Cycle 1: v_0 = 10.0
        db.start_cycle("c1", ["term"], ["src"])
        db.record_observations([
            RawObservationRecord(
                observation_id="obs1",
                cycle_id="c1",
                source="src",
                query="statutory depreciation matrix",
                normalized_query="statutory depreciation matrix",
                observed_velocity=10.0,
                observed_at="2026-10-08T00:00:00Z",
            )
        ])
        db.upsert_keyword_history(
            query_slug="statutory-depreciation-matrix",
            query="statutory depreciation matrix",
            cycle_id="c1",
            observed_velocity=10.0,
            observed_at="2026-10-08T00:00:00Z",
        )
        db.complete_cycle("c1", 1, 1)

        # Cycle 2: v_1 = 30.0
        db.start_cycle("c2", ["term"], ["src"])
        db.record_observations([
            RawObservationRecord(
                observation_id="obs2",
                cycle_id="c2",
                source="src",
                query="statutory depreciation matrix",
                normalized_query="statutory depreciation matrix",
                observed_velocity=30.0,
                observed_at="2026-10-09T00:00:00Z",
            )
        ])
        r2 = db.upsert_keyword_history(
            query_slug="statutory-depreciation-matrix",
            query="statutory depreciation matrix",
            cycle_id="c2",
            observed_velocity=30.0,
            observed_at="2026-10-09T00:00:00Z",
        )
        # v_t = 30, v_{t-1} = 10, v_{t-2} = 0 -> A_t = 30 - 2(10) + 0 = 10.0
        assert r2.velocity_delta == 20.0
        assert r2.acceleration_2nd_deriv == 10.0
        db.complete_cycle("c2", 1, 1)

        # Cycle 3: v_2 = 60.0
        db.start_cycle("c3", ["term"], ["src"])
        db.record_observations([
            RawObservationRecord(
                observation_id="obs3",
                cycle_id="c3",
                source="src",
                query="statutory depreciation matrix",
                normalized_query="statutory depreciation matrix",
                observed_velocity=60.0,
                observed_at="2026-10-10T00:00:00Z",
            )
        ])
        r3 = db.upsert_keyword_history(
            query_slug="statutory-depreciation-matrix",
            query="statutory depreciation matrix",
            cycle_id="c3",
            observed_velocity=60.0,
            observed_at="2026-10-10T00:00:00Z",
        )
        # v_t = 60, v_{t-1} = 30, v_{t-2} = 10 -> A_t = 60 - 2(30) + 10 = 10.0
        assert r3.velocity_delta == 30.0
        assert r3.acceleration_2nd_deriv == 10.0
        db.complete_cycle("c3", 1, 1)


def test_foreign_key_cascades_and_constraints(tmp_path: Path):
    """Verifies foreign key constraints and cascade deletions."""
    db_file = tmp_path / "test_fk.db"
    with TrendHistoryDB(db_file) as db:
        conn = db.get_connection()
        db.start_cycle("cycle-parent", ["seed"], ["src"])
        db.record_observations([
            RawObservationRecord(
                observation_id="obs-child",
                cycle_id="cycle-parent",
                source="src",
                query="test child query",
                normalized_query="test child query",
            )
        ])

        # Verify child observation exists
        obs_row = conn.execute("SELECT * FROM raw_crawl_observations WHERE observation_id = 'obs-child';").fetchone()
        assert obs_row is not None

        # Delete parent cycle
        conn.execute("DELETE FROM crawl_cycles WHERE cycle_id = 'cycle-parent';")

        # Child observation must be cascade deleted
        obs_after = conn.execute("SELECT * FROM raw_crawl_observations WHERE observation_id = 'obs-child';").fetchone()
        assert obs_after is None


def test_niche_cluster_proposal_persistence(tmp_path: Path):
    """Verifies structured NicheClusterProposal persistence and query retrieval."""
    db_file = tmp_path / "test_proposals.db"
    with TrendHistoryDB(db_file) as db:
        db.start_cycle("cycle-prop-1", ["contractor"], ["google_suggest"])
        prop = NicheClusterProposal(
            proposal_id="prop-contractor-lien",
            cluster_slug="contractor-lien-statutory-matrix",
            cluster_title="Contractor Lien Statutory Matrix",
            first_observed_cycle_id="cycle-prop-1",
            confirmed_cycle_id="cycle-prop-1",
            consecutive_cycles_sustained=3,
            mean_composite_yield=78.5,
            aggregate_search_volume=4500,
            mean_cpc_usd=14.8,
            treg_stability_index=0.88,
            primary_queries=["contractor lien statutory matrix by state"],
            recommended_domain_archetype="statutory_matrix_directory",
            status="PROPOSED",
            proposal_spec={
                "cluster_slug": "contractor-lien-statutory-matrix",
                "recommended_tools": ["statutory_matrix"],
            },
        )
        db.create_niche_proposal(prop)
        proposals = db.get_niche_proposals(status="PROPOSED")
        assert len(proposals) == 1
        assert proposals[0].cluster_slug == "contractor-lien-statutory-matrix"
        assert proposals[0].consecutive_cycles_sustained == 3
        assert proposals[0].mean_composite_yield == 78.5
