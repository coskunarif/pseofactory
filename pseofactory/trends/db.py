"""
pseofactory SQLite Trend History Persistence Database
Maintains multi-day trend history, longitudinal keyword velocity, and multi-cycle durability records.
Configured with WAL mode, busy timeout, and atomic file advisory locking (fcntl.flock).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import json
import fcntl
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union, Generator

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_url_safe_slug,
    sanitize_url_slug,
)
from pseofactory.trends.models import (
    CrawlCycleRecord,
    RawObservationRecord,
    LongitudinalKeywordRecord,
    PropertyAssignmentRecord,
    TregSnapshotRecord,
    JevEvaluationRecord,
    NicheClusterProposal,
)
from pseofactory.trends.filters import calculate_second_derivative_acceleration


DEFAULT_DB_PATH = Path("pseofactory/trends/data/trend_history.db")


class TrendHistoryDB:
    """
    ACID-compliant SQLite relational store for longitudinal trend intelligence.
    Enforces WAL journal mode, 5000ms busy timeout, and non-blocking file advisory locks.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = Path(f"{self.db_path}.lock")
        self._lock_file = None
        self._conn: Optional[sqlite3.Connection] = None
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with WAL mode and pragmas configured."""
        if self._conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=10.0,
                isolation_level=None,  # Autocommit mode; transactions handled explicitly
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._conn = conn
        return self._conn

    def close(self) -> None:
        """Closes the open database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "TrendHistoryDB":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @contextmanager
    def acquire_lock(self, non_blocking: bool = True) -> Generator[None, None, None]:
        """
        Acquires atomic advisory file lock on <db_path>.lock per HWL-1253.
        Fails fast if non_blocking is True and another process holds the lock.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o666)
        flags = fcntl.LOCK_EX
        if non_blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(lock_fd, flags)
            yield
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager wrapping atomic SQLite transaction."""
        conn = self.get_connection()
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()
        try:
            yield cursor
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    def init_schema(self) -> None:
        """Initializes idempotent relational schema across all 7 tables and indexes."""
        conn = self.get_connection()
        with conn:
            # 1. crawl_cycles
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    executed_at TEXT NOT NULL,
                    seeds_used TEXT NOT NULL,
                    sources_crawled TEXT NOT NULL,
                    total_raw_observations INTEGER NOT NULL DEFAULT 0,
                    unique_queries_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL CHECK(status IN ('RUNNING', 'COMPLETED', 'FAILED')),
                    metadata TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_crawl_cycles_executed_at ON crawl_cycles(executed_at);"
            )

            # 2. raw_crawl_observations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_crawl_observations (
                    observation_id TEXT PRIMARY KEY,
                    cycle_id TEXT NOT NULL REFERENCES crawl_cycles(cycle_id) ON DELETE CASCADE,
                    source TEXT NOT NULL,
                    query TEXT NOT NULL,
                    normalized_query TEXT NOT NULL,
                    rank_position INTEGER NOT NULL DEFAULT 0,
                    observed_velocity REAL NOT NULL DEFAULT 0.0,
                    observed_acceleration REAL NOT NULL DEFAULT 0.0,
                    observed_z_score REAL NOT NULL DEFAULT 0.0,
                    observed_at TEXT NOT NULL,
                    raw_payload TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_observations_norm_query_observed_at ON raw_crawl_observations(normalized_query, observed_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_observations_cycle ON raw_crawl_observations(cycle_id);"
            )

            # 3. keyword_history
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS keyword_history (
                    query_slug TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    intent_cluster TEXT NOT NULL,
                    first_seen_cycle_id TEXT REFERENCES crawl_cycles(cycle_id),
                    first_seen_at TEXT NOT NULL,
                    last_seen_cycle_id TEXT REFERENCES crawl_cycles(cycle_id),
                    last_seen_at TEXT NOT NULL,
                    consecutive_cycles_count INTEGER NOT NULL DEFAULT 1,
                    total_cycles_count INTEGER NOT NULL DEFAULT 1,
                    lifetime_observations_count INTEGER NOT NULL DEFAULT 1,
                    current_property_id TEXT NOT NULL DEFAULT 'unassigned',
                    status TEXT NOT NULL DEFAULT 'candidate',
                    latest_velocity REAL NOT NULL DEFAULT 0.0,
                    velocity_delta REAL NOT NULL DEFAULT 0.0,
                    acceleration_2nd_deriv REAL NOT NULL DEFAULT 0.0,
                    velocity_variance REAL NOT NULL DEFAULT 0.0
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_keyword_history_property_status ON keyword_history(current_property_id, status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_keyword_history_consecutive ON keyword_history(consecutive_cycles_count DESC);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_keyword_history_last_seen ON keyword_history(last_seen_at DESC);"
            )

            # 4. property_assignments
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS property_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    query_slug TEXT NOT NULL REFERENCES keyword_history(query_slug),
                    cycle_id TEXT NOT NULL REFERENCES crawl_cycles(cycle_id),
                    property_id TEXT NOT NULL CHECK(property_id IN ('prexvo', 'profithelm', 'unassigned')),
                    assignment_basis TEXT NOT NULL,
                    matched_existing_slug TEXT,
                    cannibalization_score REAL NOT NULL DEFAULT 0.0,
                    current_position REAL NOT NULL DEFAULT 100.0,
                    contamination_scan_passed INTEGER NOT NULL DEFAULT 1 CHECK(contamination_scan_passed IN (0, 1)),
                    assigned_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_property_assignments_property ON property_assignments(property_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_property_assignments_slug ON property_assignments(query_slug);"
            )

            # 5. treg_metric_snapshots
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS treg_metric_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    query_slug TEXT NOT NULL REFERENCES keyword_history(query_slug),
                    cycle_id TEXT NOT NULL REFERENCES crawl_cycles(cycle_id),
                    search_volume INTEGER NOT NULL DEFAULT 0,
                    cpc_usd REAL NOT NULL DEFAULT 0.0,
                    competition_index REAL NOT NULL DEFAULT 0.0,
                    keyword_difficulty REAL NOT NULL DEFAULT 0.0,
                    position_zero_vacant INTEGER NOT NULL DEFAULT 0 CHECK(position_zero_vacant IN (0, 1)),
                    historical_stability REAL NOT NULL DEFAULT 0.85,
                    volume_delta_pct REAL NOT NULL DEFAULT 0.0,
                    cpc_delta_pct REAL NOT NULL DEFAULT 0.0,
                    volatility_score REAL NOT NULL DEFAULT 0.0,
                    checked_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_treg_snapshots_slug_checked ON treg_metric_snapshots(query_slug, checked_at DESC);"
            )

            # 6. jev_evaluations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jev_evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    query_slug TEXT NOT NULL REFERENCES keyword_history(query_slug),
                    cycle_id TEXT NOT NULL REFERENCES crawl_cycles(cycle_id),
                    property_id TEXT NOT NULL CHECK(property_id IN ('prexvo', 'profithelm', 'unassigned')),
                    jev_score REAL NOT NULL,
                    durable_prob REAL NOT NULL,
                    composite_profit_yield REAL NOT NULL,
                    cannibalization_risk REAL NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('BUILD_PAGE', 'REFACTOR_PAGE', 'MONITOR', 'REJECT', 'PROPOSE_NEW_APP')),
                    target_asset_type TEXT NOT NULL,
                    passed_thresholds INTEGER NOT NULL CHECK(passed_thresholds IN (0, 1)),
                    decision_reason TEXT NOT NULL,
                    spec_payload TEXT,
                    evaluated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jev_eval_cycle_action ON jev_evaluations(cycle_id, action);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jev_eval_property_action ON jev_evaluations(property_id, action);"
            )

            # 7. niche_cluster_proposals
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS niche_cluster_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    cluster_slug TEXT NOT NULL UNIQUE,
                    cluster_title TEXT NOT NULL,
                    first_observed_cycle_id TEXT REFERENCES crawl_cycles(cycle_id),
                    confirmed_cycle_id TEXT REFERENCES crawl_cycles(cycle_id),
                    consecutive_cycles_sustained INTEGER NOT NULL CHECK(consecutive_cycles_sustained >= 3),
                    mean_composite_yield REAL NOT NULL,
                    aggregate_search_volume INTEGER NOT NULL,
                    mean_cpc_usd REAL NOT NULL,
                    treg_stability_index REAL NOT NULL,
                    primary_queries TEXT NOT NULL,
                    recommended_domain_archetype TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK(status IN ('PROBATIONARY', 'PROPOSED', 'APPROVED', 'DISCARDED')),
                    proposal_spec TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_niche_proposals_status ON niche_cluster_proposals(status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_niche_proposals_yield ON niche_cluster_proposals(mean_composite_yield DESC);"
            )

    # -------------------------------------------------------------------------
    # Crawl Cycle Operations
    # -------------------------------------------------------------------------

    def start_cycle(
        self,
        cycle_id: str,
        seeds: List[str],
        sources: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CrawlCycleRecord:
        """Initializes or retrieves crawl cycle record in RUNNING state."""
        assert_no_forbidden_dashes(cycle_id, "start_cycle.cycle_id")
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM crawl_cycles WHERE cycle_id = ?",
            (cycle_id,),
        ).fetchone()

        if row:
            meta = json.loads(row["metadata"]) if row["metadata"] else None
            return CrawlCycleRecord(
                cycle_id=row["cycle_id"],
                executed_at=row["executed_at"],
                seeds_used=json.loads(row["seeds_used"]),
                sources_crawled=json.loads(row["sources_crawled"]),
                total_raw_observations=row["total_raw_observations"],
                unique_queries_count=row["unique_queries_count"],
                status=row["status"],
                metadata=meta,
            )

        now = datetime.now(timezone.utc).isoformat()
        seeds_json = json.dumps(seeds)
        sources_json = json.dumps(sources)
        meta_json = json.dumps(metadata) if metadata else None

        conn.execute(
            """
            INSERT INTO crawl_cycles (
                cycle_id, executed_at, seeds_used, sources_crawled,
                total_raw_observations, unique_queries_count, status, metadata
            ) VALUES (?, ?, ?, ?, 0, 0, 'RUNNING', ?);
            """,
            (cycle_id, now, seeds_json, sources_json, meta_json),
        )

        return CrawlCycleRecord(
            cycle_id=cycle_id,
            executed_at=now,
            seeds_used=seeds,
            sources_crawled=sources,
            total_raw_observations=0,
            unique_queries_count=0,
            status="RUNNING",
            metadata=metadata,
        )

    def complete_cycle(
        self,
        cycle_id: str,
        total_raw_observations: int,
        unique_queries_count: int,
        status: str = "COMPLETED",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Marks crawl cycle as COMPLETED or FAILED with final counters."""
        assert_no_forbidden_dashes(cycle_id, "complete_cycle.cycle_id")
        conn = self.get_connection()
        meta_json = json.dumps(metadata) if metadata else None
        conn.execute(
            """
            UPDATE crawl_cycles
            SET total_raw_observations = ?,
                unique_queries_count = ?,
                status = ?,
                metadata = COALESCE(?, metadata)
            WHERE cycle_id = ?;
            """,
            (total_raw_observations, unique_queries_count, status, meta_json, cycle_id),
        )

    def get_cycle(self, cycle_id: str) -> Optional[CrawlCycleRecord]:
        """Retrieves CrawlCycleRecord by cycle_id."""
        conn = self.get_connection()
        row = conn.execute("SELECT * FROM crawl_cycles WHERE cycle_id = ?", (cycle_id,)).fetchone()
        if not row:
            return None
        meta = json.loads(row["metadata"]) if row["metadata"] else None
        return CrawlCycleRecord(
            cycle_id=row["cycle_id"],
            executed_at=row["executed_at"],
            seeds_used=json.loads(row["seeds_used"]),
            sources_crawled=json.loads(row["sources_crawled"]),
            total_raw_observations=row["total_raw_observations"],
            unique_queries_count=row["unique_queries_count"],
            status=row["status"],
            metadata=meta,
        )

    def get_previous_cycle_id(self, current_cycle_id: str) -> Optional[str]:
        """Returns cycle_id of the immediately preceding cycle."""
        conn = self.get_connection()
        row = conn.execute(
            """
            SELECT cycle_id FROM crawl_cycles
            WHERE cycle_id != ?
            ORDER BY executed_at DESC, rowid DESC
            LIMIT 1;
            """,
            (current_cycle_id,),
        ).fetchone()
        return row["cycle_id"] if row else None

    # -------------------------------------------------------------------------
    # Observation Records
    # -------------------------------------------------------------------------

    def record_observations(self, observations: List[RawObservationRecord]) -> None:
        """Idempotently inserts raw crawl observation records."""
        if not observations:
            return
        conn = self.get_connection()
        rows = [
            (
                obs.observation_id,
                obs.cycle_id,
                obs.source,
                obs.query,
                obs.normalized_query,
                obs.rank_position,
                obs.observed_velocity,
                obs.observed_acceleration,
                obs.observed_z_score,
                obs.observed_at,
                json.dumps(obs.raw_payload) if obs.raw_payload else None,
            )
            for obs in observations
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO raw_crawl_observations (
                observation_id, cycle_id, source, query, normalized_query,
                rank_position, observed_velocity, observed_acceleration,
                observed_z_score, observed_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            rows,
        )

    def get_past_velocities(self, normalized_query: str, current_cycle_id: str) -> List[float]:
        """Returns past observed velocities for query ordered by most recent first."""
        conn = self.get_connection()
        rows = conn.execute(
            """
            SELECT observed_velocity FROM raw_crawl_observations
            WHERE normalized_query = ? AND cycle_id != ?
            GROUP BY cycle_id
            ORDER BY observed_at DESC
            LIMIT 2;
            """,
            (normalized_query, current_cycle_id),
        ).fetchall()
        return [float(r["observed_velocity"]) for r in rows]

    # -------------------------------------------------------------------------
    # Keyword History Rollups
    # -------------------------------------------------------------------------

    def get_keyword_history(self, query_slug: str) -> Optional[LongitudinalKeywordRecord]:
        """Retrieves LongitudinalKeywordRecord by slug."""
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM keyword_history WHERE query_slug = ?",
            (query_slug,),
        ).fetchone()
        if not row:
            return None
        return LongitudinalKeywordRecord(
            query_slug=row["query_slug"],
            query=row["query"],
            intent_cluster=row["intent_cluster"],
            first_seen_cycle_id=row["first_seen_cycle_id"],
            first_seen_at=row["first_seen_at"],
            last_seen_cycle_id=row["last_seen_cycle_id"],
            last_seen_at=row["last_seen_at"],
            consecutive_cycles_count=row["consecutive_cycles_count"],
            total_cycles_count=row["total_cycles_count"],
            lifetime_observations_count=row["lifetime_observations_count"],
            current_property_id=row["current_property_id"],
            status=row["status"],
            latest_velocity=row["latest_velocity"],
            velocity_delta=row["velocity_delta"],
            acceleration_2nd_deriv=row["acceleration_2nd_deriv"],
            velocity_variance=row["velocity_variance"],
        )

    def list_keyword_history(
        self,
        property_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[LongitudinalKeywordRecord]:
        """Lists keyword history entities filtered by property or status."""
        conn = self.get_connection()
        query = "SELECT * FROM keyword_history WHERE 1=1"
        params: List[Any] = []
        if property_id:
            query += " AND current_property_id = ?"
            params.append(property_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY consecutive_cycles_count DESC, latest_velocity DESC;"

        rows = conn.execute(query, params).fetchall()
        return [
            LongitudinalKeywordRecord(
                query_slug=r["query_slug"],
                query=r["query"],
                intent_cluster=r["intent_cluster"],
                first_seen_cycle_id=r["first_seen_cycle_id"],
                first_seen_at=r["first_seen_at"],
                last_seen_cycle_id=r["last_seen_cycle_id"],
                last_seen_at=r["last_seen_at"],
                consecutive_cycles_count=r["consecutive_cycles_count"],
                total_cycles_count=r["total_cycles_count"],
                lifetime_observations_count=r["lifetime_observations_count"],
                current_property_id=r["current_property_id"],
                status=r["status"],
                latest_velocity=r["latest_velocity"],
                velocity_delta=r["velocity_delta"],
                acceleration_2nd_deriv=r["acceleration_2nd_deriv"],
                velocity_variance=r["velocity_variance"],
            )
            for r in rows
        ]

    def upsert_keyword_history(
        self,
        query_slug: str,
        query: str,
        cycle_id: str,
        observed_velocity: float,
        intent_cluster: str = "informational",
        property_id: str = "unassigned",
        status: Optional[str] = None,
        observation_count: int = 1,
        observed_at: Optional[str] = None,
        override_acceleration: Optional[float] = None,
    ) -> LongitudinalKeywordRecord:
        """
        Updates longitudinal keyword entity:
        - Calculates velocity delta (v_t - v_{t-1})
        - Calculates discrete second-derivative acceleration A_t = v_t - 2*v_{t-1} + v_{t-2} per HWL-1215
        - Maintains consecutive cycles streak (reset on gap, invariant on replay)
        """
        assert_url_safe_slug(query_slug)
        assert_no_forbidden_dashes(query, "upsert_keyword_history.query")

        conn = self.get_connection()
        now_iso = observed_at or datetime.now(timezone.utc).isoformat()
        clean_norm = " ".join(query.lower().strip().split())

        existing = self.get_keyword_history(query_slug)
        prev_cycle_id = self.get_previous_cycle_id(cycle_id)

        v_t = float(observed_velocity)

        if existing is None:
            # First time query observed
            consecutive = 1
            total = 1
            lifetime_obs = observation_count
            delta_v = 0.0
            accel = override_acceleration if override_acceleration is not None else 0.0
            computed_status = status or "candidate"
            first_seen_cycle = cycle_id
            first_seen_time = now_iso
        else:
            first_seen_cycle = existing.first_seen_cycle_id
            first_seen_time = existing.first_seen_at

            # Check if this invocation is a replay of the same cycle
            if existing.last_seen_cycle_id == cycle_id:
                # Idempotent replay: preserve streak and total count
                consecutive = existing.consecutive_cycles_count
                total = existing.total_cycles_count
                lifetime_obs = existing.lifetime_observations_count
                delta_v = existing.velocity_delta
                accel = existing.acceleration_2nd_deriv
                computed_status = status or existing.status
            else:
                # New cycle run: check if consecutive to previous cycle
                if existing.last_seen_cycle_id == prev_cycle_id:
                    consecutive = existing.consecutive_cycles_count + 1
                else:
                    consecutive = 1  # Streak broken by missing cycle

                total = existing.total_cycles_count + 1
                lifetime_obs = existing.lifetime_observations_count + observation_count

                # Fetch past velocities for discrete second derivative acceleration (HWL-1215)
                past_vels = self.get_past_velocities(clean_norm, cycle_id)
                if len(past_vels) >= 2:
                    v_prev1 = past_vels[0]
                    v_prev2 = past_vels[1]
                elif len(past_vels) == 1:
                    v_prev1 = past_vels[0]
                    v_prev2 = 0.0
                else:
                    v_prev1 = existing.latest_velocity
                    v_prev2 = 0.0

                delta_v = v_t - v_prev1
                accel = calculate_second_derivative_acceleration(v_t, v_prev1, v_prev2)
                if override_acceleration is not None:
                    accel = override_acceleration

                # Determine status progression
                if status:
                    computed_status = status
                elif consecutive == 1:
                    computed_status = "candidate"
                elif consecutive == 2:
                    computed_status = "observed"
                else:
                    computed_status = "stabilized"

        record = LongitudinalKeywordRecord(
            query_slug=query_slug,
            query=query,
            intent_cluster=intent_cluster,
            first_seen_cycle_id=first_seen_cycle,
            first_seen_at=first_seen_time,
            last_seen_cycle_id=cycle_id,
            last_seen_at=now_iso,
            consecutive_cycles_count=consecutive,
            total_cycles_count=total,
            lifetime_observations_count=lifetime_obs,
            current_property_id=property_id,
            status=computed_status,
            latest_velocity=v_t,
            velocity_delta=delta_v,
            acceleration_2nd_deriv=accel,
            velocity_variance=0.0,
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO keyword_history (
                query_slug, query, intent_cluster, first_seen_cycle_id,
                first_seen_at, last_seen_cycle_id, last_seen_at,
                consecutive_cycles_count, total_cycles_count,
                lifetime_observations_count, current_property_id, status,
                latest_velocity, velocity_delta, acceleration_2nd_deriv,
                velocity_variance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                record.query_slug,
                record.query,
                record.intent_cluster,
                record.first_seen_cycle_id,
                record.first_seen_at,
                record.last_seen_cycle_id,
                record.last_seen_at,
                record.consecutive_cycles_count,
                record.total_cycles_count,
                record.lifetime_observations_count,
                record.current_property_id,
                record.status,
                record.latest_velocity,
                record.velocity_delta,
                record.acceleration_2nd_deriv,
                record.velocity_variance,
            ),
        )

        return record

    # -------------------------------------------------------------------------
    # Property Assignments, Treg Snapshots, Jev Evaluations
    # -------------------------------------------------------------------------

    def record_property_assignment(self, assignment: PropertyAssignmentRecord) -> None:
        """Records property tenant assignment record."""
        conn = self.get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO property_assignments (
                assignment_id, query_slug, cycle_id, property_id,
                assignment_basis, matched_existing_slug, cannibalization_score,
                current_position, contamination_scan_passed, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                assignment.assignment_id,
                assignment.query_slug,
                assignment.cycle_id,
                assignment.property_id,
                assignment.assignment_basis,
                assignment.matched_existing_slug,
                assignment.cannibalization_score,
                assignment.current_position,
                assignment.contamination_scan_passed,
                assignment.assigned_at,
            ),
        )

    def record_treg_snapshot(self, snapshot: TregSnapshotRecord) -> None:
        """Records Treg metric snapshot."""
        conn = self.get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO treg_metric_snapshots (
                snapshot_id, query_slug, cycle_id, search_volume, cpc_usd,
                competition_index, keyword_difficulty, position_zero_vacant,
                historical_stability, volume_delta_pct, cpc_delta_pct,
                volatility_score, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                snapshot.snapshot_id,
                snapshot.query_slug,
                snapshot.cycle_id,
                snapshot.search_volume,
                snapshot.cpc_usd,
                snapshot.competition_index,
                snapshot.keyword_difficulty,
                snapshot.position_zero_vacant,
                snapshot.historical_stability,
                snapshot.volume_delta_pct,
                snapshot.cpc_delta_pct,
                snapshot.volatility_score,
                snapshot.checked_at,
            ),
        )

    def record_jev_evaluation(self, evaluation: JevEvaluationRecord) -> None:
        """Records strategic Jev evaluation record."""
        conn = self.get_connection()
        payload_json = json.dumps(evaluation.spec_payload) if evaluation.spec_payload else None
        conn.execute(
            """
            INSERT OR REPLACE INTO jev_evaluations (
                evaluation_id, query_slug, cycle_id, property_id, jev_score,
                durable_prob, composite_profit_yield, cannibalization_risk,
                action, target_asset_type, passed_thresholds, decision_reason,
                spec_payload, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                evaluation.evaluation_id,
                evaluation.query_slug,
                evaluation.cycle_id,
                evaluation.property_id,
                evaluation.jev_score,
                evaluation.durable_prob,
                evaluation.composite_profit_yield,
                evaluation.cannibalization_risk,
                evaluation.action,
                evaluation.target_asset_type,
                evaluation.passed_thresholds,
                evaluation.decision_reason,
                payload_json,
                evaluation.evaluated_at,
            ),
        )

    # -------------------------------------------------------------------------
    # Niche Cluster Proposals
    # -------------------------------------------------------------------------

    def create_niche_proposal(self, proposal: NicheClusterProposal) -> None:
        """Creates or updates a NicheClusterProposal."""
        conn = self.get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO niche_cluster_proposals (
                proposal_id, cluster_slug, cluster_title,
                first_observed_cycle_id, confirmed_cycle_id,
                consecutive_cycles_sustained, mean_composite_yield,
                aggregate_search_volume, mean_cpc_usd, treg_stability_index,
                primary_queries, recommended_domain_archetype, status,
                proposal_spec, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                proposal.proposal_id,
                proposal.cluster_slug,
                proposal.cluster_title,
                proposal.first_observed_cycle_id,
                proposal.confirmed_cycle_id,
                proposal.consecutive_cycles_sustained,
                proposal.mean_composite_yield,
                proposal.aggregate_search_volume,
                proposal.mean_cpc_usd,
                proposal.treg_stability_index,
                json.dumps(proposal.primary_queries),
                proposal.recommended_domain_archetype,
                proposal.status,
                json.dumps(proposal.proposal_spec),
                proposal.created_at,
                proposal.updated_at,
            ),
        )

    def get_niche_proposals(self, status: Optional[str] = None) -> List[NicheClusterProposal]:
        """Lists all NicheClusterProposal records."""
        conn = self.get_connection()
        query = "SELECT * FROM niche_cluster_proposals WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY mean_composite_yield DESC, created_at DESC;"

        rows = conn.execute(query, params).fetchall()
        return [
            NicheClusterProposal(
                proposal_id=r["proposal_id"],
                cluster_slug=r["cluster_slug"],
                cluster_title=r["cluster_title"],
                first_observed_cycle_id=r["first_observed_cycle_id"],
                confirmed_cycle_id=r["confirmed_cycle_id"],
                consecutive_cycles_sustained=r["consecutive_cycles_sustained"],
                mean_composite_yield=r["mean_composite_yield"],
                aggregate_search_volume=r["aggregate_search_volume"],
                mean_cpc_usd=r["mean_cpc_usd"],
                treg_stability_index=r["treg_stability_index"],
                primary_queries=json.loads(r["primary_queries"]),
                recommended_domain_archetype=r["recommended_domain_archetype"],
                status=r["status"],
                proposal_spec=json.loads(r["proposal_spec"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
