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
    GSCDailyMetricRecord,
    GoogleUpdateEvent,
    AlgorithmicCeilingAnalysis,
    CeilingThresholdSpec,
    GSCDeviceMetricRecord,
    GSCSearchAppearanceRecord,
    GSCQueryPageWindowRecord,
    GSCUrlInspectionRecord,
    StatutoryEconomicTimeseriesRecord,
)
from pseofactory.trends.filters import calculate_second_derivative_acceleration


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "trend_history.db"


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
    def acquire_lock(self, non_blocking: bool = True, timeout: float = 0.0) -> Generator[None, None, None]:
        """
        Acquires atomic advisory file lock on <db_path>.lock per HWL-1253.
        Fails fast if non_blocking is True and timeout <= 0.0 when another process holds the lock.
        When timeout > 0.0, waits up to timeout seconds before raising BlockingIOError.
        """
        import time

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o666)
        flags = fcntl.LOCK_EX
        if non_blocking:
            flags |= fcntl.LOCK_NB
        acquired = False
        try:
            if non_blocking and timeout > 0.0:
                deadline = time.monotonic() + float(timeout)
                while True:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                        break
                    except (BlockingIOError, OSError):
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.1)
            else:
                fcntl.flock(lock_fd, flags)
                acquired = True
            yield
        finally:
            try:
                if acquired:
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
                    property_id TEXT NOT NULL CHECK(property_id IN ('prexvo', 'profithelm', 'gainhelm', 'unassigned')),
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
                    property_id TEXT NOT NULL CHECK(property_id IN ('prexvo', 'profithelm', 'gainhelm', 'unassigned')),
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

            # 8. gsc_daily_metrics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsc_daily_metrics (
                    property_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    clicks INTEGER NOT NULL DEFAULT 0 CHECK(clicks >= 0),
                    impressions INTEGER NOT NULL DEFAULT 0 CHECK(impressions >= 0),
                    ctr REAL NOT NULL DEFAULT 0.0 CHECK(ctr >= 0.0 AND ctr <= 1.0),
                    position REAL NOT NULL DEFAULT 0.0 CHECK(position >= 0.0),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (property_id, date)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_daily_property_date ON gsc_daily_metrics(property_id, date DESC);"
            )

            # 9. google_update_events
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS google_update_events (
                    event_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    update_type TEXT NOT NULL CHECK(update_type IN ('CORE', 'SPAM', 'HELPFUL_CONTENT', 'REVIEWS', 'REPUTATION_ABUSE', 'OTHER')),
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    impact_buffer_days INTEGER NOT NULL DEFAULT 14,
                    confirmed INTEGER NOT NULL DEFAULT 1 CHECK(confirmed IN (0, 1)),
                    notes TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_google_updates_date ON google_update_events(start_date, end_date);"
            )

            # 10. gsc_ceiling_snapshots
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsc_ceiling_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    property_id TEXT NOT NULL,
                    computed_at TEXT NOT NULL,
                    analysis_window_days INTEGER NOT NULL DEFAULT 480,
                    peak_impressions_rma28 REAL NOT NULL,
                    current_impressions_rma28 REAL NOT NULL,
                    ceiling_detected INTEGER NOT NULL CHECK(ceiling_detected IN (0, 1)),
                    ceiling_dampening_score REAL NOT NULL,
                    correlated_update_id TEXT,
                    recommendation TEXT NOT NULL CHECK(recommendation IN ('BUILD_PAGE', 'MONITOR', 'AUTHORITY_STRENGTHENING', 'FREEZE_EXPANSION')),
                    metadata TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ceiling_snapshots_prop_time ON gsc_ceiling_snapshots(property_id, computed_at DESC);"
            )

            # 11. market_intel_candidates
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_intel_candidates (
                    tenant_id TEXT PRIMARY KEY,
                    brand_name TEXT NOT NULL,
                    recommended_domain TEXT NOT NULL,
                    vertical_id TEXT NOT NULL,
                    vertical_name TEXT NOT NULL,
                    domain_archetype TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    fast_money_score REAL NOT NULL,
                    composite_profit_yield REAL NOT NULL,
                    buyer_intent_score REAL NOT NULL,
                    ease_of_ranking_score REAL NOT NULL,
                    mean_keyword_difficulty REAL NOT NULL,
                    position_zero_vacant_ratio REAL NOT NULL,
                    commission_offer_score REAL NOT NULL,
                    aggregate_search_volume INTEGER NOT NULL,
                    mean_cpc_usd REAL NOT NULL,
                    expected_bounty_usd REAL NOT NULL,
                    effective_partner_yield REAL NOT NULL,
                    projected_monthly_revenue_usd REAL NOT NULL,
                    estimated_days_to_first_dollar INTEGER NOT NULL,
                    estimated_days_to_top_10 INTEGER NOT NULL,
                    min_approval_friction_days INTEGER NOT NULL,
                    isolation_boundary_verified INTEGER NOT NULL CHECK(isolation_boundary_verified IN (0, 1)),
                    candidate_payload TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_market_intel_candidates_score ON market_intel_candidates(fast_money_score DESC, rank ASC);"
            )

            # 12. gsc_device_metrics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsc_device_metrics (
                    property_id TEXT NOT NULL,
                    window_key TEXT NOT NULL DEFAULT 'recent_28d',
                    page TEXT NOT NULL DEFAULT '',
                    query TEXT NOT NULL DEFAULT '',
                    device TEXT NOT NULL CHECK(device IN ('DESKTOP', 'MOBILE', 'TABLET', 'ALL')),
                    clicks INTEGER NOT NULL DEFAULT 0 CHECK(clicks >= 0),
                    impressions INTEGER NOT NULL DEFAULT 0 CHECK(impressions >= 0),
                    ctr REAL NOT NULL DEFAULT 0.0 CHECK(ctr >= 0.0 AND ctr <= 1.0),
                    position REAL NOT NULL DEFAULT 0.0 CHECK(position >= 0.0),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (property_id, window_key, page, query, device)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_device_prop_page ON gsc_device_metrics(property_id, page, device);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_device_prop_query ON gsc_device_metrics(property_id, query, device);"
            )

            # 13. gsc_search_appearance_metrics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsc_search_appearance_metrics (
                    property_id TEXT NOT NULL,
                    window_key TEXT NOT NULL DEFAULT 'recent_90d',
                    search_appearance TEXT NOT NULL,
                    clicks INTEGER NOT NULL DEFAULT 0 CHECK(clicks >= 0),
                    impressions INTEGER NOT NULL DEFAULT 0 CHECK(impressions >= 0),
                    ctr REAL NOT NULL DEFAULT 0.0 CHECK(ctr >= 0.0 AND ctr <= 1.0),
                    position REAL NOT NULL DEFAULT 0.0 CHECK(position >= 0.0),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (property_id, window_key, search_appearance)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_appearance_prop ON gsc_search_appearance_metrics(property_id, impressions DESC);"
            )

            # 14. gsc_query_page_windows
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsc_query_page_windows (
                    property_id TEXT NOT NULL,
                    window_key TEXT NOT NULL,
                    query TEXT NOT NULL,
                    page TEXT NOT NULL,
                    clicks INTEGER NOT NULL DEFAULT 0 CHECK(clicks >= 0),
                    impressions INTEGER NOT NULL DEFAULT 0 CHECK(impressions >= 0),
                    ctr REAL NOT NULL DEFAULT 0.0 CHECK(ctr >= 0.0 AND ctr <= 1.0),
                    position REAL NOT NULL DEFAULT 0.0 CHECK(position >= 0.0),
                    window_start_date TEXT NOT NULL DEFAULT '',
                    window_end_date TEXT NOT NULL DEFAULT '',
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (property_id, window_key, query, page)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_qp_windows_prop_page ON gsc_query_page_windows(property_id, window_key, page);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_qp_windows_prop_query ON gsc_query_page_windows(property_id, window_key, query);"
            )

            # 15. gsc_url_inspection_states
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsc_url_inspection_states (
                    property_id TEXT NOT NULL,
                    page_url TEXT NOT NULL,
                    verdict TEXT NOT NULL DEFAULT 'NEUTRAL',
                    coverage_state TEXT NOT NULL DEFAULT 'Unknown',
                    indexing_state TEXT NOT NULL DEFAULT 'INDEXING_STATE_UNSPECIFIED',
                    page_fetch_state TEXT NOT NULL DEFAULT 'PAGE_FETCH_STATE_UNSPECIFIED',
                    robots_txt_state TEXT NOT NULL DEFAULT 'ROBOTS_TXT_STATE_UNSPECIFIED',
                    user_canonical TEXT NOT NULL DEFAULT '',
                    google_canonical TEXT NOT NULL DEFAULT '',
                    last_crawl_time TEXT NOT NULL DEFAULT '',
                    crawled_as TEXT NOT NULL DEFAULT 'MOBILE',
                    rich_results_verdict TEXT NOT NULL DEFAULT 'VERDICT_UNSPECIFIED',
                    rich_results_types TEXT NOT NULL DEFAULT '[]',
                    mobile_usability_verdict TEXT NOT NULL DEFAULT 'VERDICT_UNSPECIFIED',
                    referring_urls TEXT NOT NULL DEFAULT '[]',
                    sitemaps TEXT NOT NULL DEFAULT '[]',
                    root_cause_classification TEXT NOT NULL DEFAULT '',
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (property_id, page_url)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsc_inspection_prop_verdict ON gsc_url_inspection_states(property_id, verdict, coverage_state);"
            )

            # 16. statutory_economic_timeseries
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS statutory_economic_timeseries (
                    series_id TEXT NOT NULL,
                    property_id TEXT NOT NULL CHECK(property_id IN ('prexvo', 'profithelm', 'gainhelm', 'shared', 'unassigned')),
                    jurisdiction TEXT NOT NULL DEFAULT 'US-FED',
                    statutory_citation TEXT NOT NULL,
                    metric_key TEXT NOT NULL,
                    metric_label TEXT NOT NULL,
                    effective_year INTEGER NOT NULL,
                    metric_value REAL NOT NULL,
                    unit TEXT NOT NULL DEFAULT 'USD',
                    source_agency TEXT NOT NULL DEFAULT 'IRS',
                    recorded_at TEXT NOT NULL,
                    metadata TEXT,
                    PRIMARY KEY (series_id, effective_year)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_stat_econ_prop_year ON statutory_economic_timeseries(property_id, effective_year ASC);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_stat_econ_metric_key ON statutory_economic_timeseries(metric_key, effective_year ASC);"
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
        """Returns cycle_id of the immediately preceding non-failed cycle."""
        conn = self.get_connection()
        row = conn.execute(
            """
            SELECT cycle_id FROM crawl_cycles
            WHERE cycle_id != ? AND status != 'FAILED'
            ORDER BY executed_at DESC, rowid DESC
            LIMIT 1;
            """,
            (current_cycle_id,),
        ).fetchone()
        return row["cycle_id"] if row else None

    def heal_orphaned_running_cycles(self, exclude_cycle_id: Optional[str] = None) -> int:
        """Marks orphaned RUNNING crawl cycles with 0 observations as FAILED so they do not break consecutive streaks."""
        conn = self.get_connection()
        if exclude_cycle_id:
            cur = conn.execute(
                """
                UPDATE crawl_cycles
                SET status = 'FAILED'
                WHERE status = 'RUNNING' AND total_raw_observations = 0 AND cycle_id != ?;
                """,
                (exclude_cycle_id,),
            )
        else:
            cur = conn.execute(
                """
                UPDATE crawl_cycles
                SET status = 'FAILED'
                WHERE status = 'RUNNING' AND total_raw_observations = 0;
                """
            )
        return int(cur.rowcount or 0)

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
        now_iso = snapshot.checked_at or datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO crawl_cycles (
                cycle_id, executed_at, seeds_used, sources_crawled, status
            ) VALUES (?, ?, '[]', '[]', 'COMPLETED');
            """,
            (snapshot.cycle_id, now_iso),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO keyword_history (
                query_slug, query, intent_cluster, first_seen_at, last_seen_at
            ) VALUES (?, ?, 'informational', ?, ?);
            """,
            (snapshot.query_slug, snapshot.query_slug.replace("-", " "), now_iso, now_iso),
        )
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

    def get_latest_treg_snapshot(
        self,
        query_slug: str,
        max_age_days: Optional[int] = 30,
        ignore_poisoned_zero: bool = True,
    ) -> Optional[TregSnapshotRecord]:
        """
        Retrieves most recent TregSnapshotRecord for given query_slug from treg_metric_snapshots table.
        Optionally validates snapshot freshness against max_age_days and rejects poisoned 0-volume defaults.
        Zero em-dashes. Zero en-dashes.
        """
        assert_url_safe_slug(query_slug)
        conn = self.get_connection()
        if ignore_poisoned_zero:
            row = conn.execute(
                """
                SELECT * FROM treg_metric_snapshots
                WHERE query_slug = ?
                  AND NOT (search_volume = 0 AND cpc_usd = 0.0 AND keyword_difficulty = 50.0)
                ORDER BY checked_at DESC
                LIMIT 1;
                """,
                (query_slug,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM treg_metric_snapshots
                WHERE query_slug = ?
                ORDER BY checked_at DESC
                LIMIT 1;
                """,
                (query_slug,),
            ).fetchone()

        if not row:
            return None

        if max_age_days is not None:
            checked_at_str = row["checked_at"]
            try:
                checked_dt = datetime.fromisoformat(checked_at_str.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                age_days = (now_dt - checked_dt).total_seconds() / 86400.0
                if age_days > max_age_days:
                    return None
            except Exception:
                pass

        return TregSnapshotRecord(
            snapshot_id=row["snapshot_id"],
            query_slug=row["query_slug"],
            cycle_id=row["cycle_id"],
            search_volume=row["search_volume"],
            cpc_usd=row["cpc_usd"],
            competition_index=row["competition_index"],
            keyword_difficulty=row["keyword_difficulty"],
            position_zero_vacant=row["position_zero_vacant"],
            historical_stability=row["historical_stability"],
            volume_delta_pct=row["volume_delta_pct"],
            cpc_delta_pct=row["cpc_delta_pct"],
            volatility_score=row["volatility_score"],
            checked_at=row["checked_at"],
        )

    def purge_poisoned_treg_snapshots(self) -> int:
        """Removes poisoned treg_metric_snapshots rows where search_volume=0, cpc_usd=0.0, and keyword_difficulty=50.0."""
        conn = self.get_connection()
        cur = conn.execute(
            """
            DELETE FROM treg_metric_snapshots
            WHERE search_volume = 0 AND cpc_usd = 0.0 AND keyword_difficulty = 50.0;
            """
        )
        return int(cur.rowcount or 0)

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

    # -------------------------------------------------------------------------
    # Search Console Performance Metrics & Algorithmic Ceiling Operations
    # -------------------------------------------------------------------------

    def upsert_gsc_daily_metrics(self, records: List[GSCDailyMetricRecord]) -> int:
        """Idempotently batch upserts daily Search Console performance metric records."""
        if not records:
            return 0
        with self.transaction() as cur:
            for r in records:
                assert_no_forbidden_dashes(r.property_id, "upsert_gsc_daily_metrics.property_id")
                assert_no_forbidden_dashes(r.date, "upsert_gsc_daily_metrics.date")
                cur.execute(
                    """
                    INSERT OR REPLACE INTO gsc_daily_metrics (
                        property_id, date, clicks, impressions, ctr, position, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        r.property_id,
                        r.date,
                        r.clicks,
                        r.impressions,
                        r.ctr,
                        r.position,
                        r.recorded_at,
                    ),
                )
        return len(records)

    def get_gsc_daily_metrics(self, property_id: str, days: int = 480) -> List[GSCDailyMetricRecord]:
        """Retrieves up to `days` daily Search Console metrics ordered chronologically (date ASC)."""
        assert_no_forbidden_dashes(property_id, "get_gsc_daily_metrics.property_id")
        conn = self.get_connection()
        rows = conn.execute(
            """
            SELECT property_id, date, clicks, impressions, ctr, position, recorded_at
            FROM gsc_daily_metrics
            WHERE property_id = ?
            ORDER BY date DESC
            LIMIT ?;
            """,
            (property_id, days),
        ).fetchall()
        return [
            GSCDailyMetricRecord(
                property_id=r["property_id"],
                date=r["date"],
                clicks=r["clicks"],
                impressions=r["impressions"],
                ctr=r["ctr"],
                position=r["position"],
                recorded_at=r["recorded_at"],
            )
            for r in reversed(rows)
        ]

    def upsert_google_update_events(self, events: List[GoogleUpdateEvent]) -> int:
        """Idempotently batch upserts Google ranking update events."""
        if not events:
            return 0
        with self.transaction() as cur:
            for ev in events:
                assert_no_forbidden_dashes(ev.event_id, "upsert_google_update_events.event_id")
                assert_no_forbidden_dashes(ev.name, "upsert_google_update_events.name")
                cur.execute(
                    """
                    INSERT OR REPLACE INTO google_update_events (
                        event_id, name, update_type, start_date, end_date,
                        impact_buffer_days, confirmed, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ev.event_id,
                        ev.name,
                        ev.update_type,
                        ev.start_date,
                        ev.end_date,
                        ev.impact_buffer_days,
                        ev.confirmed,
                        ev.notes,
                    ),
                )
        return len(events)

    def get_google_update_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[GoogleUpdateEvent]:
        """Retrieves Google update events optionally bounded by date range."""
        conn = self.get_connection()
        query = "SELECT * FROM google_update_events WHERE 1=1"
        params: List[Any] = []
        if start_date:
            query += " AND (end_date IS NULL OR end_date >= ?)"
            params.append(start_date)
        if end_date:
            query += " AND start_date <= ?"
            params.append(end_date)
        query += " ORDER BY start_date ASC;"
        rows = conn.execute(query, params).fetchall()
        return [
            GoogleUpdateEvent(
                event_id=r["event_id"],
                name=r["name"],
                update_type=r["update_type"],
                start_date=r["start_date"],
                end_date=r["end_date"],
                impact_buffer_days=r["impact_buffer_days"],
                confirmed=r["confirmed"],
                notes=r["notes"] or "",
            )
            for r in rows
        ]

    def record_gsc_ceiling_snapshot(self, analysis: AlgorithmicCeilingAnalysis) -> str:
        """Persists an algorithmic ceiling snapshot into gsc_ceiling_snapshots."""
        import uuid
        snapshot_id = f"snap_ceil_{analysis.property_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        corr_id = analysis.correlated_updates[0].get("event_id") if analysis.correlated_updates else None
        meta_json = json.dumps(analysis.metadata) if analysis.metadata else None
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO gsc_ceiling_snapshots (
                    snapshot_id, property_id, computed_at, analysis_window_days,
                    peak_impressions_rma28, current_impressions_rma28, ceiling_detected,
                    ceiling_dampening_score, correlated_update_id, recommendation, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    snapshot_id,
                    analysis.property_id,
                    analysis.computed_at,
                    analysis.analysis_window_days,
                    analysis.peak_impressions_rma28,
                    analysis.current_impressions_rma28,
                    1 if analysis.ceiling_detected else 0,
                    analysis.ceiling_dampening_score,
                    corr_id,
                    analysis.recommendation,
                    meta_json,
                ),
            )
        return snapshot_id

    # -------------------------------------------------------------------------
    # Market Intelligence Tenant Candidate Operations
    # -------------------------------------------------------------------------

    def upsert_market_intel_candidate(
        self,
        candidate: Dict[str, Any],
        evaluated_at: Optional[str] = None,
    ) -> None:
        """Idempotently upserts a ranked greenfield tenant candidate into market_intel_candidates."""
        now_iso = evaluated_at or datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(candidate)
        assert_no_forbidden_dashes(payload_json, "upsert_market_intel_candidate.payload")
        conn = self.get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO market_intel_candidates (
                tenant_id, brand_name, recommended_domain, vertical_id,
                vertical_name, domain_archetype, rank, fast_money_score,
                composite_profit_yield, buyer_intent_score, ease_of_ranking_score,
                mean_keyword_difficulty, position_zero_vacant_ratio,
                commission_offer_score, aggregate_search_volume, mean_cpc_usd,
                expected_bounty_usd, effective_partner_yield,
                projected_monthly_revenue_usd, estimated_days_to_first_dollar,
                estimated_days_to_top_10, min_approval_friction_days,
                isolation_boundary_verified, candidate_payload, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(candidate["tenant_id"]),
                str(candidate["brand_name"]),
                str(candidate["recommended_domain"]),
                str(candidate["vertical_id"]),
                str(candidate["vertical_name"]),
                str(candidate["domain_archetype"]),
                int(candidate.get("rank", 1)),
                float(candidate["fast_money_score"]),
                float(candidate["composite_profit_yield"]),
                float(candidate["buyer_intent_score"]),
                float(candidate["ease_of_ranking_score"]),
                float(candidate["mean_keyword_difficulty"]),
                float(candidate["position_zero_vacant_ratio"]),
                float(candidate["commission_offer_score"]),
                int(candidate["aggregate_search_volume"]),
                float(candidate["mean_cpc_usd"]),
                float(candidate["expected_bounty_usd"]),
                float(candidate["effective_partner_yield"]),
                float(candidate["projected_monthly_revenue_usd"]),
                int(candidate["estimated_days_to_first_dollar"]),
                int(candidate["estimated_days_to_top_10"]),
                int(candidate["min_approval_friction_days"]),
                1 if candidate.get("isolation_boundary_verified", True) else 0,
                payload_json,
                now_iso,
            ),
        )

    def get_market_intel_candidates(self, min_fast_money_score: float = 0.0) -> List[Dict[str, Any]]:
        """Retrieves persisted market intelligence tenant candidates ordered by rank ASC."""
        conn = self.get_connection()
        rows = conn.execute(
            """
            SELECT candidate_payload, evaluated_at
            FROM market_intel_candidates
            WHERE fast_money_score >= ?
            ORDER BY rank ASC, fast_money_score DESC;
            """,
            (float(min_fast_money_score),),
        ).fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            item = json.loads(r["candidate_payload"])
            item["evaluated_at"] = r["evaluated_at"]
            results.append(item)
        return results

    # -------------------------------------------------------------------------
    # Multi-Dimensional GSC Lifecycle Telemetry Operations
    # -------------------------------------------------------------------------

    def get_latest_gsc_ceiling_snapshot(
        self,
        property_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent algorithmic ceiling snapshot for a property."""
        conn = self.get_connection()
        row = conn.execute(
            """
            SELECT snapshot_id, property_id, computed_at, analysis_window_days,
                   peak_impressions_rma28, current_impressions_rma28, ceiling_detected,
                   ceiling_dampening_score, correlated_update_id, recommendation, metadata
            FROM gsc_ceiling_snapshots
            WHERE property_id = ?
            ORDER BY computed_at DESC
            LIMIT 1;
            """,
            (str(property_id),),
        ).fetchone()
        if not row:
            return None
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        return {
            "snapshot_id": row["snapshot_id"],
            "property_id": row["property_id"],
            "computed_at": row["computed_at"],
            "analysis_window_days": int(row["analysis_window_days"]),
            "peak_impressions_rma28": float(row["peak_impressions_rma28"]),
            "current_impressions_rma28": float(row["current_impressions_rma28"]),
            "ceiling_detected": bool(row["ceiling_detected"]),
            "ceiling_dampening_score": float(row["ceiling_dampening_score"]),
            "correlated_update_id": row["correlated_update_id"],
            "recommendation": row["recommendation"],
            "metadata": meta,
        }

    def upsert_gsc_device_metrics(
        self,
        records: List[Union[GSCDeviceMetricRecord, Dict[str, Any]]],
    ) -> int:
        """Idempotently upserts device-level Search Console telemetry records."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        count = 0
        with self.transaction() as cur:
            for item in records:
                rec = (
                    item
                    if isinstance(item, GSCDeviceMetricRecord)
                    else GSCDeviceMetricRecord(
                        property_id=str(item.get("property_id", "")),
                        device=str(item.get("device", "DESKTOP")),
                        page=str(item.get("page", "")),
                        query=str(item.get("query", "")),
                        window_key=str(item.get("window_key", "recent_28d")),
                        clicks=max(0, int(item.get("clicks", 0) or 0)),
                        impressions=max(0, int(item.get("impressions", 0) or 0)),
                        ctr=max(0.0, min(1.0, float(item.get("ctr", 0.0) or 0.0))),
                        position=max(0.0, float(item.get("position", 0.0) or 0.0)),
                        recorded_at=str(item.get("recorded_at") or now_iso),
                    )
                )
                cur.execute(
                    """
                    INSERT INTO gsc_device_metrics (
                        property_id, window_key, page, query, device,
                        clicks, impressions, ctr, position, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(property_id, window_key, page, query, device) DO UPDATE SET
                        clicks = excluded.clicks,
                        impressions = excluded.impressions,
                        ctr = excluded.ctr,
                        position = excluded.position,
                        recorded_at = excluded.recorded_at;
                    """,
                    (
                        rec.property_id,
                        rec.window_key,
                        rec.page,
                        rec.query,
                        rec.device,
                        rec.clicks,
                        rec.impressions,
                        rec.ctr,
                        rec.position,
                        rec.recorded_at,
                    ),
                )
                count += 1
        return count

    def get_gsc_device_metrics(
        self,
        property_id: str,
        window_key: Optional[str] = None,
        page: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[GSCDeviceMetricRecord]:
        """Retrieves persisted device-level Search Console telemetry for a property."""
        conn = self.get_connection()
        clauses = ["property_id = ?"]
        params: List[Any] = [str(property_id)]
        if window_key is not None:
            clauses.append("window_key = ?")
            params.append(str(window_key))
        if page is not None:
            clauses.append("page = ?")
            params.append(str(page))
        if query is not None:
            clauses.append("query = ?")
            params.append(str(query))
        sql = f"""
            SELECT property_id, window_key, page, query, device,
                   clicks, impressions, ctr, position, recorded_at
            FROM gsc_device_metrics
            WHERE {' AND '.join(clauses)}
            ORDER BY impressions DESC, clicks DESC;
        """
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            GSCDeviceMetricRecord(
                property_id=r["property_id"],
                window_key=r["window_key"],
                page=r["page"],
                query=r["query"],
                device=r["device"],
                clicks=int(r["clicks"]),
                impressions=int(r["impressions"]),
                ctr=float(r["ctr"]),
                position=float(r["position"]),
                recorded_at=r["recorded_at"],
            )
            for r in rows
        ]

    def upsert_gsc_search_appearance_metrics(
        self,
        records: List[Union[GSCSearchAppearanceRecord, Dict[str, Any]]],
    ) -> int:
        """Idempotently upserts rich-result Search Appearance telemetry records."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        count = 0
        with self.transaction() as cur:
            for item in records:
                rec = (
                    item
                    if isinstance(item, GSCSearchAppearanceRecord)
                    else GSCSearchAppearanceRecord(
                        property_id=str(item.get("property_id", "")),
                        search_appearance=str(item.get("search_appearance", "")),
                        window_key=str(item.get("window_key", "recent_90d")),
                        clicks=max(0, int(item.get("clicks", 0) or 0)),
                        impressions=max(0, int(item.get("impressions", 0) or 0)),
                        ctr=max(0.0, min(1.0, float(item.get("ctr", 0.0) or 0.0))),
                        position=max(0.0, float(item.get("position", 0.0) or 0.0)),
                        recorded_at=str(item.get("recorded_at") or now_iso),
                    )
                )
                if not rec.search_appearance:
                    continue
                cur.execute(
                    """
                    INSERT INTO gsc_search_appearance_metrics (
                        property_id, window_key, search_appearance,
                        clicks, impressions, ctr, position, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(property_id, window_key, search_appearance) DO UPDATE SET
                        clicks = excluded.clicks,
                        impressions = excluded.impressions,
                        ctr = excluded.ctr,
                        position = excluded.position,
                        recorded_at = excluded.recorded_at;
                    """,
                    (
                        rec.property_id,
                        rec.window_key,
                        rec.search_appearance,
                        rec.clicks,
                        rec.impressions,
                        rec.ctr,
                        rec.position,
                        rec.recorded_at,
                    ),
                )
                count += 1
        return count

    def get_gsc_search_appearance_metrics(
        self,
        property_id: str,
        window_key: str = "recent_90d",
    ) -> List[GSCSearchAppearanceRecord]:
        """Retrieves persisted Search Appearance telemetry records for a property."""
        conn = self.get_connection()
        rows = conn.execute(
            """
            SELECT property_id, window_key, search_appearance,
                   clicks, impressions, ctr, position, recorded_at
            FROM gsc_search_appearance_metrics
            WHERE property_id = ? AND window_key = ?
            ORDER BY impressions DESC, clicks DESC;
            """,
            (str(property_id), str(window_key)),
        ).fetchall()
        return [
            GSCSearchAppearanceRecord(
                property_id=r["property_id"],
                window_key=r["window_key"],
                search_appearance=r["search_appearance"],
                clicks=int(r["clicks"]),
                impressions=int(r["impressions"]),
                ctr=float(r["ctr"]),
                position=float(r["position"]),
                recorded_at=r["recorded_at"],
            )
            for r in rows
        ]

    def upsert_gsc_query_page_windows(
        self,
        records: List[Union[GSCQueryPageWindowRecord, Dict[str, Any]]],
    ) -> int:
        """Idempotently upserts time-windowed query + page telemetry snapshots."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        count = 0
        with self.transaction() as cur:
            for item in records:
                rec = (
                    item
                    if isinstance(item, GSCQueryPageWindowRecord)
                    else GSCQueryPageWindowRecord(
                        property_id=str(item.get("property_id", "")),
                        window_key=str(item.get("window_key", "recent_28d")),
                        query=str(item.get("query", "")),
                        page=str(item.get("page", "")),
                        clicks=max(0, int(item.get("clicks", 0) or 0)),
                        impressions=max(0, int(item.get("impressions", 0) or 0)),
                        ctr=max(0.0, min(1.0, float(item.get("ctr", 0.0) or 0.0))),
                        position=max(0.0, float(item.get("position", 0.0) or 0.0)),
                        window_start_date=str(item.get("window_start_date", "")),
                        window_end_date=str(item.get("window_end_date", "")),
                        recorded_at=str(item.get("recorded_at") or now_iso),
                    )
                )
                if not rec.query and not rec.page:
                    continue
                cur.execute(
                    """
                    INSERT INTO gsc_query_page_windows (
                        property_id, window_key, query, page,
                        clicks, impressions, ctr, position,
                        window_start_date, window_end_date, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(property_id, window_key, query, page) DO UPDATE SET
                        clicks = excluded.clicks,
                        impressions = excluded.impressions,
                        ctr = excluded.ctr,
                        position = excluded.position,
                        window_start_date = excluded.window_start_date,
                        window_end_date = excluded.window_end_date,
                        recorded_at = excluded.recorded_at;
                    """,
                    (
                        rec.property_id,
                        rec.window_key,
                        rec.query,
                        rec.page,
                        rec.clicks,
                        rec.impressions,
                        rec.ctr,
                        rec.position,
                        rec.window_start_date,
                        rec.window_end_date,
                        rec.recorded_at,
                    ),
                )
                count += 1
        return count

    def get_gsc_query_page_windows(
        self,
        property_id: str,
        window_key: str = "recent_28d",
        page: Optional[str] = None,
    ) -> List[GSCQueryPageWindowRecord]:
        """Retrieves persisted time-windowed query + page telemetry snapshots."""
        conn = self.get_connection()
        if page is not None:
            rows = conn.execute(
                """
                SELECT property_id, window_key, query, page,
                       clicks, impressions, ctr, position,
                       window_start_date, window_end_date, recorded_at
                FROM gsc_query_page_windows
                WHERE property_id = ? AND window_key = ? AND page = ?
                ORDER BY impressions DESC, clicks DESC;
                """,
                (str(property_id), str(window_key), str(page)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT property_id, window_key, query, page,
                       clicks, impressions, ctr, position,
                       window_start_date, window_end_date, recorded_at
                FROM gsc_query_page_windows
                WHERE property_id = ? AND window_key = ?
                ORDER BY impressions DESC, clicks DESC;
                """,
                (str(property_id), str(window_key)),
            ).fetchall()
        return [
            GSCQueryPageWindowRecord(
                property_id=r["property_id"],
                window_key=r["window_key"],
                query=r["query"],
                page=r["page"],
                clicks=int(r["clicks"]),
                impressions=int(r["impressions"]),
                ctr=float(r["ctr"]),
                position=float(r["position"]),
                window_start_date=r["window_start_date"],
                window_end_date=r["window_end_date"],
                recorded_at=r["recorded_at"],
            )
            for r in rows
        ]

    def upsert_gsc_url_inspection_states(
        self,
        records: List[Union[GSCUrlInspectionRecord, Dict[str, Any]]],
    ) -> int:
        """Idempotently upserts granular URL Inspection coverage and rich-result/mobile usability states."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        count = 0
        with self.transaction() as cur:
            for item in records:
                rec = (
                    item
                    if isinstance(item, GSCUrlInspectionRecord)
                    else GSCUrlInspectionRecord(
                        property_id=str(item.get("property_id", "")),
                        page_url=str(item.get("page_url", "") or item.get("url", "")),
                        verdict=str(item.get("verdict", "NEUTRAL")),
                        coverage_state=str(item.get("coverage_state", "Unknown")),
                        indexing_state=str(item.get("indexing_state", "INDEXING_STATE_UNSPECIFIED")),
                        page_fetch_state=str(item.get("page_fetch_state", "PAGE_FETCH_STATE_UNSPECIFIED")),
                        robots_txt_state=str(item.get("robots_txt_state", "ROBOTS_TXT_STATE_UNSPECIFIED")),
                        user_canonical=str(item.get("user_canonical", "")),
                        google_canonical=str(item.get("google_canonical", "")),
                        last_crawl_time=str(item.get("last_crawl_time", "")),
                        crawled_as=str(item.get("crawled_as", "MOBILE")),
                        rich_results_verdict=str(item.get("rich_results_verdict", "VERDICT_UNSPECIFIED")),
                        rich_results_types=list(item.get("rich_results_types", [])),
                        mobile_usability_verdict=str(item.get("mobile_usability_verdict", "VERDICT_UNSPECIFIED")),
                        referring_urls=list(item.get("referring_urls", [])),
                        sitemaps=list(item.get("sitemaps", [])),
                        root_cause_classification=str(item.get("root_cause_classification", "")),
                        recorded_at=str(item.get("recorded_at") or now_iso),
                    )
                )
                if not rec.page_url:
                    continue
                cur.execute(
                    """
                    INSERT INTO gsc_url_inspection_states (
                        property_id, page_url, verdict, coverage_state, indexing_state,
                        page_fetch_state, robots_txt_state, user_canonical, google_canonical,
                        last_crawl_time, crawled_as, rich_results_verdict, rich_results_types,
                        mobile_usability_verdict, referring_urls, sitemaps,
                        root_cause_classification, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(property_id, page_url) DO UPDATE SET
                        verdict = excluded.verdict,
                        coverage_state = excluded.coverage_state,
                        indexing_state = excluded.indexing_state,
                        page_fetch_state = excluded.page_fetch_state,
                        robots_txt_state = excluded.robots_txt_state,
                        user_canonical = excluded.user_canonical,
                        google_canonical = excluded.google_canonical,
                        last_crawl_time = excluded.last_crawl_time,
                        crawled_as = excluded.crawled_as,
                        rich_results_verdict = excluded.rich_results_verdict,
                        rich_results_types = excluded.rich_results_types,
                        mobile_usability_verdict = excluded.mobile_usability_verdict,
                        referring_urls = excluded.referring_urls,
                        sitemaps = excluded.sitemaps,
                        root_cause_classification = excluded.root_cause_classification,
                        recorded_at = excluded.recorded_at;
                    """,
                    (
                        rec.property_id,
                        rec.page_url,
                        rec.verdict,
                        rec.coverage_state,
                        rec.indexing_state,
                        rec.page_fetch_state,
                        rec.robots_txt_state,
                        rec.user_canonical,
                        rec.google_canonical,
                        rec.last_crawl_time,
                        rec.crawled_as,
                        rec.rich_results_verdict,
                        json.dumps(rec.rich_results_types),
                        rec.mobile_usability_verdict,
                        json.dumps(rec.referring_urls),
                        json.dumps(rec.sitemaps),
                        rec.root_cause_classification,
                        rec.recorded_at,
                    ),
                )
                count += 1
        return count

    def get_gsc_url_inspection_states(
        self,
        property_id: str,
        page_url: Optional[str] = None,
    ) -> List[GSCUrlInspectionRecord]:
        """Retrieves persisted URL Inspection states for a property."""
        conn = self.get_connection()
        if page_url is not None:
            rows = conn.execute(
                """
                SELECT * FROM gsc_url_inspection_states
                WHERE property_id = ? AND page_url = ?;
                """,
                (str(property_id), str(page_url)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM gsc_url_inspection_states
                WHERE property_id = ?
                ORDER BY recorded_at DESC;
                """,
                (str(property_id),),
            ).fetchall()
        return [
            GSCUrlInspectionRecord(
                property_id=r["property_id"],
                page_url=r["page_url"],
                verdict=r["verdict"],
                coverage_state=r["coverage_state"],
                indexing_state=r["indexing_state"],
                page_fetch_state=r["page_fetch_state"],
                robots_txt_state=r["robots_txt_state"],
                user_canonical=r["user_canonical"],
                google_canonical=r["google_canonical"],
                last_crawl_time=r["last_crawl_time"],
                crawled_as=r["crawled_as"],
                rich_results_verdict=r["rich_results_verdict"],
                rich_results_types=json.loads(r["rich_results_types"] or "[]"),
                mobile_usability_verdict=r["mobile_usability_verdict"],
                referring_urls=json.loads(r["referring_urls"] or "[]"),
                sitemaps=json.loads(r["sitemaps"] or "[]"),
                root_cause_classification=r["root_cause_classification"],
                recorded_at=r["recorded_at"],
            )
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # Longitudinal Statutory & Macroeconomic Time-Series Operations
    # -------------------------------------------------------------------------

    def upsert_statutory_economic_timeseries(
        self,
        records: List[Union[StatutoryEconomicTimeseriesRecord, Dict[str, Any]]],
    ) -> int:
        """Idempotently upserts longitudinal statutory and macroeconomic time-series points."""
        if not records:
            return 0
        now_iso = datetime.now(timezone.utc).isoformat()
        count = 0
        with self.transaction() as cur:
            for item in records:
                rec = (
                    item
                    if isinstance(item, StatutoryEconomicTimeseriesRecord)
                    else StatutoryEconomicTimeseriesRecord.from_dict(item)
                )
                meta_json = json.dumps(rec.metadata) if rec.metadata else None
                cur.execute(
                    """
                    INSERT INTO statutory_economic_timeseries (
                        series_id, property_id, jurisdiction, statutory_citation,
                        metric_key, metric_label, effective_year, metric_value,
                        unit, source_agency, recorded_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(series_id, effective_year) DO UPDATE SET
                        property_id = excluded.property_id,
                        jurisdiction = excluded.jurisdiction,
                        statutory_citation = excluded.statutory_citation,
                        metric_key = excluded.metric_key,
                        metric_label = excluded.metric_label,
                        metric_value = excluded.metric_value,
                        unit = excluded.unit,
                        source_agency = excluded.source_agency,
                        recorded_at = excluded.recorded_at,
                        metadata = COALESCE(excluded.metadata, statutory_economic_timeseries.metadata);
                    """,
                    (
                        rec.series_id,
                        rec.property_id,
                        rec.jurisdiction,
                        rec.statutory_citation,
                        rec.metric_key,
                        rec.metric_label,
                        int(rec.effective_year),
                        float(rec.metric_value),
                        rec.unit,
                        rec.source_agency,
                        rec.recorded_at or now_iso,
                        meta_json,
                    ),
                )
                count += 1
        return count

    def get_statutory_economic_timeseries(
        self,
        property_id: Optional[str] = None,
        metric_key: Optional[str] = None,
    ) -> List[StatutoryEconomicTimeseriesRecord]:
        """Retrieves longitudinal statutory and macroeconomic time-series records."""
        conn = self.get_connection()
        clauses = ["1=1"]
        params: List[Any] = []
        if property_id:
            clauses.append("property_id IN (?, 'shared')")
            params.append(str(property_id))
        if metric_key:
            clauses.append("metric_key = ?")
            params.append(str(metric_key))
        sql = f"""
            SELECT series_id, property_id, jurisdiction, statutory_citation,
                   metric_key, metric_label, effective_year, metric_value,
                   unit, source_agency, recorded_at, metadata
            FROM statutory_economic_timeseries
            WHERE {' AND '.join(clauses)}
            ORDER BY series_id ASC, effective_year ASC;
        """
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            StatutoryEconomicTimeseriesRecord(
                series_id=r["series_id"],
                property_id=r["property_id"],
                jurisdiction=r["jurisdiction"],
                statutory_citation=r["statutory_citation"],
                metric_key=r["metric_key"],
                metric_label=r["metric_label"],
                effective_year=int(r["effective_year"]),
                metric_value=float(r["metric_value"]),
                unit=r["unit"],
                source_agency=r["source_agency"],
                recorded_at=r["recorded_at"],
                metadata=json.loads(r["metadata"]) if r["metadata"] else None,
            )
            for r in rows
        ]

    def compile_statutory_economic_matrix(
        self,
        property_id: str,
        query: str = "",
    ) -> Dict[str, Any]:
        """
        Compiles a longitudinal multi-year statutory and economic matrix (2024 to 2030)
        from archived statutory_economic_timeseries rows for compile-time workbench injection.
        """
        prop = str(property_id or "profithelm").strip().lower()
        if prop not in ("profithelm", "prexvo", "gainhelm"):
            prop = "profithelm"
        records = self.get_statutory_economic_timeseries(property_id=prop)
        if not any(r.property_id == prop for r in records):
            try:
                from pseofactory.trends.collectors import StatutoryEconomicDatasetCollector
                StatutoryEconomicDatasetCollector(db_path=self.db_path).sync_to_db(db=self)
                records = self.get_statutory_economic_timeseries(property_id=prop)
            except Exception:
                pass
        series_map: Dict[str, Dict[str, Any]] = {}
        for rec in records:
            entry = series_map.setdefault(
                rec.series_id,
                {
                    "series_id": rec.series_id,
                    "property_id": rec.property_id,
                    "jurisdiction": rec.jurisdiction,
                    "statutory_citation": rec.statutory_citation,
                    "metric_key": rec.metric_key,
                    "metric_label": rec.metric_label,
                    "unit": rec.unit,
                    "source_agency": rec.source_agency,
                    "points": {},
                    "timeline": [],
                },
            )
            entry["points"][str(rec.effective_year)] = rec.metric_value
            entry["timeline"].append({"year": rec.effective_year, "value": rec.metric_value})

        q_lower = str(query or "").lower()
        ordered_series = sorted(
            series_map.values(),
            key=lambda s: (
                0 if any(tok in q_lower for tok in str(s["metric_key"]).split("_") if len(tok) >= 3) else 1,
                0 if s["property_id"] == prop else 1,
                str(s["series_id"]),
            ),
        )
        default_auth = (
            "Title IV Higher Education Act 34 CFR Part 685.209"
            if prop == "prexvo"
            else (
                "AICPA SSAE 18 Trust Services Criteria & DoD 32 CFR Part 170 CMMC 2.0"
                if prop == "gainhelm"
                else "IRC Section 179 and 26 U.S.C. 168(k) Statutory Depreciation Schedule"
            )
        )
        default_econ = (
            "BLS OEWS SOC 15-1212 Information Security Analysts Wage Dataset"
            if prop == "gainhelm"
            else "FRED Series DGS10 and CPILFESL Longitudinal Macro Dataset"
        )
        top_citation = str(ordered_series[0]["statutory_citation"]) if ordered_series else default_auth
        if prop == "profithelm" and "irc section" not in top_citation.lower():
            top_citation = f"{top_citation} ({default_auth})"
        elif prop == "prexvo" and "title iv" not in top_citation.lower():
            top_citation = f"{top_citation} ({default_auth})"
        elif prop == "gainhelm" and "ssae 18" not in top_citation.lower() and "32 cfr" not in top_citation.lower():
            top_citation = f"{top_citation} ({default_auth})"
        return {
            "property_id": prop,
            "query": str(query or ""),
            "years": [2024, 2025, 2026, 2027, 2028, 2029, 2030],
            "statutory_authority": top_citation,
            "economic_dataset": default_econ,
            "series_count": len(ordered_series),
            "series": ordered_series,
        }
