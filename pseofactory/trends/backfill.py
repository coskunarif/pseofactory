"""
pseofactory Historical Session Crawl & Trend History DB Backfill Engine
Normalizes historical session transcripts, void candidate logs, and autojob execution records
into discrete hourly cycles, replaying longitudinal streaks and discrete second-derivative acceleration.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import re
import json
import time
import fcntl
import random
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Union, Tuple
from concurrent.futures import ThreadPoolExecutor

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
from pseofactory.trends.db import TrendHistoryDB, DEFAULT_DB_PATH
from pseofactory.trends.cron import TrendCronRunner


DEFAULT_STAGING_DIR = Path(".agy/scratch/backfill_staged")
DEFAULT_DLQ_PATH = Path(".agy/runs/5017e890/staging_dlq.jsonl")
DEFAULT_VAULT_VOID_PATH = Path("/home/ubuntuadmin/.local/share/vault/void_candidates.jsonl")
DEFAULT_AUTOJOBS_LOG_PATH = Path("/home/ubuntuadmin/.local/state/autojobs/pseofactory-trend-intake.log")
DEFAULT_BRAIN_DIR = Path("/home/ubuntuadmin/.gemini/antigravity-cli/brain")


def sanitize_forbidden_dashes(text: str) -> str:
    """Replaces Unicode em-dashes and en-dashes with standard ASCII hyphens or spaces."""
    if not text:
        return ""
    return text.replace("\u2014", " ").replace("\u2013", "-")


def parse_iso_utc(ts_str: Optional[str], default_dt: Optional[datetime] = None) -> datetime:
    """Robustly parses ISO-8601 UTC timestamp handling timezone offsets and naive datetimes."""
    if not ts_str:
        return default_dt or datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    s = ts_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(ts_str.split(".")[0].strip(), fmt)
                break
            except Exception:
                pass
        else:
            return default_dt or datetime(2026, 9, 24, 0, 0, 0, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class RawStagedRecord:
    """Normalized intermediate record extracted from historical logs and session stores."""
    source_origin: str
    query: str
    normalized_query: str
    query_slug: str
    observed_at: str
    source: str
    rank_position: int = 0
    observed_velocity: float = 0.0
    observed_acceleration: float = 0.0
    observed_z_score: float = 0.0
    search_volume: int = 0
    cpc_usd: float = 1.50
    competition_index: float = 0.0
    keyword_difficulty: float = 20.0
    position_zero_vacant: int = 1
    historical_stability: float = 0.85
    action: str = "MONITOR"
    jev_score: float = 1.25
    durable_prob: float = 0.55
    composite_profit_yield: float = 20.0
    cannibalization_risk: float = 0.0
    target_asset_type: str = "none"
    decision_reason: str = "Historical backfill observation"
    passed_thresholds: int = 0
    property_id: str = "unassigned"
    assignment_basis: str = "unassigned_cluster"
    contamination_scan_passed: int = 1
    raw_payload: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        assert_no_forbidden_dashes(self.query, "RawStagedRecord.query")
        assert_no_forbidden_dashes(self.normalized_query, "RawStagedRecord.normalized_query")
        assert_no_forbidden_dashes(self.source, "RawStagedRecord.source")
        assert_no_forbidden_dashes(self.action, "RawStagedRecord.action")
        assert_no_forbidden_dashes(self.property_id, "RawStagedRecord.property_id")
        assert_url_safe_slug(self.query_slug)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawStagedRecord":
        return cls(**data)


@dataclass
class StagedCycleBatch:
    """Discrete hourly batch partitioned for chronological simulation and transaction insertion."""
    cycle_id: str
    executed_at: str
    records: List[RawStagedRecord] = field(default_factory=list)
    seeds_used: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    def __post_init__(self):
        assert_no_forbidden_dashes(self.cycle_id, "StagedCycleBatch.cycle_id")


class FlexibleSchemaAdapter:
    """
    Pure transformation adapter normalizing divergent historical schemas across eras:
    - Era 1: profithelm.void_candidate.v1 (September 2026)
    - Era 2: JevDecisionResult (October 2026)
    - Autojob log records
    - Brain session transcripts
    - Test fixtures
    Enforces offline deterministic defaults for missing demand telemetry. Zero live external network calls.
    """

    def __init__(self, cron_runner: Optional[TrendCronRunner] = None):
        self.runner = cron_runner or TrendCronRunner()

    def normalize_record(self, item: Dict[str, Any], source_origin: str = "unknown") -> RawStagedRecord:
        """
        Normalizes any historical record dict into canonical RawStagedRecord.
        Sanitizes forbidden dashes and validates URL-safe slugs.
        """
        # 1. Query extraction and sanitization
        raw_q = str(item.get("query") or item.get("primary_keyword") or "").strip()
        if not raw_q:
            raise ValueError("Record missing query or primary_keyword")

        clean_q = sanitize_forbidden_dashes(raw_q).strip()
        clean_q = " ".join(clean_q.split())
        assert_no_forbidden_dashes(clean_q, "FlexibleSchemaAdapter.clean_q")

        norm_q = " ".join(clean_q.lower().split())

        # 2. Slug sanitization and validation
        raw_slug = item.get("slug") or clean_q
        slug = sanitize_url_slug(sanitize_forbidden_dashes(str(raw_slug)))
        assert_url_safe_slug(slug)

        # 3. Source extraction
        raw_src = str(item.get("source") or "vault_void_harvest")
        src = sanitize_forbidden_dashes(raw_src).strip() or "vault_void_harvest"
        assert_no_forbidden_dashes(src, "FlexibleSchemaAdapter.src")

        # 4. Timestamp normalization
        ts_str = (
            item.get("timestamp")
            or item.get("evaluated_at")
            or item.get("detected_at")
            or item.get("observed_at")
            or item.get("updated_at")
        )
        dt = parse_iso_utc(ts_str)
        observed_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 5. Velocity and acceleration telemetry
        vel = float(item.get("velocity") or item.get("observed_velocity") or 0.0)
        accel = float(item.get("acceleration") or item.get("observed_acceleration") or 0.0)
        z_score = float(item.get("z_score") or item.get("observed_z_score") or 0.0)
        rank_pos = int(item.get("rank_position") or item.get("sample_count") or 0)

        # 6. Demand metrics with offline deterministic defaults
        demand = item.get("demand") if isinstance(item.get("demand"), dict) else {}
        treg_mock = item.get("treg_mock") if isinstance(item.get("treg_mock"), dict) else {}

        sv = int(
            demand.get("search_volume")
            or demand.get("volume")
            or treg_mock.get("search_volume")
            or item.get("search_volume")
            or 0
        )
        cpc = float(
            demand.get("cpc_usd")
            or demand.get("cpc")
            or treg_mock.get("cpc_usd")
            or item.get("cpc_usd")
            or 1.50
        )
        kd = float(
            demand.get("kd")
            or demand.get("keyword_difficulty")
            or treg_mock.get("keyword_difficulty")
            or item.get("keyword_difficulty")
            or 20.0
        )
        comp_idx = float(
            demand.get("competition_index")
            or treg_mock.get("competition_index")
            or item.get("competition_index")
            or 0.0
        )

        # pos0 default 1
        pos0_raw = (
            demand.get("position_zero_vacant")
            if "position_zero_vacant" in demand
            else (
                treg_mock.get("position_zero_vacant")
                if "position_zero_vacant" in treg_mock
                else item.get("position_zero_vacant", True)
            )
        )
        pos0 = 1 if pos0_raw else 0

        stability = float(
            demand.get("historical_stability")
            or treg_mock.get("historical_stability")
            or item.get("historical_stability")
            or 0.85
        )

        # 7. Action mapping
        action_raw = str(item.get("action") or item.get("status") or "MONITOR").strip()
        if action_raw == "BUILT":
            action = "BUILD_PAGE"
        elif action_raw == "REJECTED":
            action = "REJECT"
        elif action_raw == "CANDIDATE":
            action = "MONITOR"
        elif action_raw in ("BUILD_PAGE", "REFACTOR_PAGE", "MONITOR", "REJECT", "PROPOSE_NEW_APP"):
            action = action_raw
        else:
            action = "MONITOR"

        # 8. Jev scoring metrics
        jev_score = float(item.get("jev_score") or (treg_mock.get("jev_score") if treg_mock else None) or 1.25)
        durable_prob = float(
            item.get("durable_prob")
            or item.get("jev_causal_probability")
            or (treg_mock.get("durable_prob") if treg_mock else None)
            or 0.55
        )
        profit_yield = float(
            item.get("composite_profit_yield")
            or item.get("rice_score")
            or 20.0
        )
        cannibal_risk = float(item.get("cannibalization_risk") or 0.0)
        target_asset = sanitize_forbidden_dashes(str(item.get("target_asset_type") or "none"))
        passed_thresh = 1 if item.get("passed_thresholds") else 0

        raw_reason = str(item.get("decision_reason") or item.get("status_reason") or item.get("quick_answer") or "Historical backfill observation")
        decision_reason = sanitize_forbidden_dashes(raw_reason).strip() or "Historical backfill observation"
        assert_no_forbidden_dashes(decision_reason, "FlexibleSchemaAdapter.decision_reason")

        # 9. Tenant property routing via statutory tokens and scanner
        prop_info = self.runner.determine_property_assignment(clean_q)
        property_id = prop_info["property_id"]
        assignment_basis = prop_info["basis"]
        scan_passed = prop_info["contamination_scan_passed"]

        # If explicit property_id passed and conforms, respect it if unassigned
        if "property_id" in item and property_id == "unassigned":
            explicit_p = str(item["property_id"]).strip()
            if explicit_p in ("prexvo", "profithelm", "unassigned"):
                property_id = explicit_p

        assert_no_forbidden_dashes(property_id, "FlexibleSchemaAdapter.property_id")

        return RawStagedRecord(
            source_origin=source_origin,
            query=clean_q,
            normalized_query=norm_q,
            query_slug=slug,
            observed_at=observed_at,
            source=src,
            rank_position=rank_pos,
            observed_velocity=vel,
            observed_acceleration=accel,
            observed_z_score=z_score,
            search_volume=sv,
            cpc_usd=cpc,
            competition_index=comp_idx,
            keyword_difficulty=kd,
            position_zero_vacant=pos0,
            historical_stability=stability,
            action=action,
            jev_score=jev_score,
            durable_prob=durable_prob,
            composite_profit_yield=profit_yield,
            cannibalization_risk=cannibal_risk,
            target_asset_type=target_asset,
            decision_reason=decision_reason,
            passed_thresholds=passed_thresh,
            property_id=property_id,
            assignment_basis=assignment_basis,
            contamination_scan_passed=scan_passed,
            raw_payload=item,
        )


class VaultVoidCandidatesExtractor:
    """Extracts records from void_candidates.jsonl spanning Era 1 and Era 2."""

    def __init__(self, file_path: Union[str, Path] = DEFAULT_VAULT_VOID_PATH):
        self.file_path = Path(file_path).resolve()

    def extract(self, adapter: FlexibleSchemaAdapter, dlq_path: Optional[Path] = None) -> List[RawStagedRecord]:
        records: List[RawStagedRecord] = []
        if not self.file_path.exists():
            return records

        content = self.file_path.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                rec = adapter.normalize_record(data, source_origin=f"vault_void:{self.file_path.name}:{line_num}")
                records.append(rec)
            except Exception as ex:
                if dlq_path:
                    dlq_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(dlq_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"source": str(self.file_path), "line": line_num, "raw": line_str, "error": str(ex)}) + "\n")
        return records


class AutojobLogExtractor:
    """Parses autojobs execution log to capture execution provenance and run cycles."""

    def __init__(self, log_path: Union[str, Path] = DEFAULT_AUTOJOBS_LOG_PATH):
        self.log_path = Path(log_path).resolve()

    def extract_runs(self) -> List[Dict[str, Any]]:
        """Parses execution log lines into structured run records."""
        runs: List[Dict[str, Any]] = []
        if not self.log_path.exists():
            return runs

        content = self.log_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        current_run: Optional[Dict[str, Any]] = None
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check for starting timestamp: [2026-10-08T16:41:50Z] Starting pseofactory-trend-intake
            m_start = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\] Starting pseofactory-trend-intake(?:\s+\(args:\s*(.*?)\))?", line_str)
            if m_start:
                if current_run:
                    runs.append(current_run)
                ts = m_start.group(1)
                args_val = m_start.group(2) or ""
                current_run = {
                    "started_at": ts,
                    "args": args_val,
                    "status": "RUNNING",
                    "processed": 0,
                    "filtered": 0,
                    "approved": 0,
                    "refactor": 0,
                    "monitored": 0,
                    "rejected": 0,
                }
                continue

            # Check for summary line: [TREND INTAKE] Processed: 65 | Filtered Noise: 8 | ...
            if current_run and "[TREND INTAKE]" in line_str:
                m_proc = re.search(r"Processed:\s*(\d+)", line_str)
                m_filt = re.search(r"Filtered Noise:\s*(\d+)", line_str)
                m_appr = re.search(r"Approved Build:\s*(\d+)", line_str)
                m_refa = re.search(r"Refactor Pages:\s*(\d+)", line_str)
                m_moni = re.search(r"Monitored:\s*(\d+)", line_str)
                m_reje = re.search(r"Rejected:\s*(\d+)", line_str)
                if m_proc: current_run["processed"] = int(m_proc.group(1))
                if m_filt: current_run["filtered"] = int(m_filt.group(1))
                if m_appr: current_run["approved"] = int(m_appr.group(1))
                if m_refa: current_run["refactor"] = int(m_refa.group(1))
                if m_moni: current_run["monitored"] = int(m_moni.group(1))
                if m_reje: current_run["rejected"] = int(m_reje.group(1))

            # Check for completion
            if current_run and "[SUCCESS]" in line_str:
                current_run["status"] = "COMPLETED"
            elif current_run and "[ERROR]" in line_str:
                current_run["status"] = "FAILED"

        if current_run:
            runs.append(current_run)
        return runs


class BrainSessionExtractor:
    """Scans agent brain session directories for historical trend evaluations and task artifacts."""

    def __init__(self, brain_dir: Union[str, Path] = DEFAULT_BRAIN_DIR):
        self.brain_dir = Path(brain_dir).resolve()

    def extract(self, adapter: FlexibleSchemaAdapter, dlq_path: Optional[Path] = None) -> List[RawStagedRecord]:
        records: List[RawStagedRecord] = []
        if not self.brain_dir.exists():
            return records

        for p in self.brain_dir.glob("**/*"):
            if not p.is_file():
                continue
            # Target scratch files or artifact files with trend keywords
            if not any(k in p.name.lower() for k in ("candidate", "void", "spike", "trend", "eval")):
                continue
            if p.suffix not in (".json", ".jsonl"):
                continue

            try:
                content = p.read_text(encoding="utf-8")
                if p.suffix == ".jsonl":
                    items = [json.loads(l) for l in content.splitlines() if l.strip()]
                else:
                    loaded = json.loads(content)
                    if isinstance(loaded, list):
                        items = loaded
                    elif isinstance(loaded, dict):
                        items = loaded.get("records") or loaded.get("candidates") or [loaded]
                    else:
                        items = []

                for item in items:
                    if isinstance(item, dict) and (item.get("query") or item.get("primary_keyword")):
                        try:
                            rec = adapter.normalize_record(item, source_origin=f"brain:{p.name}")
                            records.append(rec)
                        except Exception as ex:
                            if dlq_path:
                                dlq_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(dlq_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({"source": str(p), "error": str(ex), "raw": item}) + "\n")
            except Exception:
                pass

        return records


class FixtureExtractor:
    """Loads historical or synthetic vectors from explicit fixture files."""

    def __init__(self, fixture_path: Union[str, Path]):
        self.fixture_path = Path(fixture_path).resolve()

    def extract(self, adapter: FlexibleSchemaAdapter, dlq_path: Optional[Path] = None) -> List[RawStagedRecord]:
        records: List[RawStagedRecord] = []
        if not self.fixture_path.exists():
            return records

        content = self.fixture_path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("records") or data.get("spikes") or [data]
            else:
                items = []

            for item in items:
                if isinstance(item, dict):
                    rec = adapter.normalize_record(item, source_origin=f"fixture:{self.fixture_path.name}")
                    records.append(rec)
        except Exception as ex:
            if dlq_path:
                dlq_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dlq_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"source": str(self.fixture_path), "error": str(ex)}) + "\n")
        return records


class HistoricalSessionCrawler:
    """
    Coordinates multi-source extraction, disk-backed staging, chronological ordering,
    and partitioning into discrete hourly crawl cycles.
    """

    def __init__(
        self,
        staging_dir: Union[str, Path] = DEFAULT_STAGING_DIR,
        dlq_path: Union[str, Path] = DEFAULT_DLQ_PATH,
        vault_path: Union[str, Path] = DEFAULT_VAULT_VOID_PATH,
        autojobs_log_path: Union[str, Path] = DEFAULT_AUTOJOBS_LOG_PATH,
        brain_dir: Union[str, Path] = DEFAULT_BRAIN_DIR,
        fixture_path: Optional[Union[str, Path]] = None,
        adapter: Optional[FlexibleSchemaAdapter] = None,
    ):
        self.staging_dir = Path(staging_dir).resolve()
        self.dlq_path = Path(dlq_path).resolve()
        self.vault_path = Path(vault_path).resolve()
        self.autojobs_log_path = Path(autojobs_log_path).resolve()
        self.brain_dir = Path(brain_dir).resolve()
        self.fixture_path = Path(fixture_path).resolve() if fixture_path else None
        self.adapter = adapter or FlexibleSchemaAdapter()

    def stage_records(self) -> List[Path]:
        """Runs parallel extractors and writes intermediate parsed records into staging_dir."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        staged_files: List[Path] = []

        extractors = [
            ("vault", VaultVoidCandidatesExtractor(self.vault_path)),
            ("brain", BrainSessionExtractor(self.brain_dir)),
        ]
        if self.fixture_path and self.fixture_path.exists():
            extractors.append(("fixture", FixtureExtractor(self.fixture_path)))

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(ext.extract, self.adapter, self.dlq_path): name
                for name, ext in extractors
            }
            for fut in futures:
                name = futures[fut]
                recs = fut.result()
                if recs:
                    batch_file = self.staging_dir / f"batch_{name}_{int(time.time()*1000)}.jsonl"
                    with open(batch_file, "w", encoding="utf-8") as f:
                        for r in recs:
                            f.write(json.dumps(r.to_dict()) + "\n")
                    staged_files.append(batch_file)

        return staged_files

    def consolidate_and_partition(self) -> List[StagedCycleBatch]:
        """
        Loads all staged batch records, sorts strictly by observed_at ASC,
        deduplicates by (normalized_query, cycle_id), and partitions into discrete hourly batches.
        """
        all_records: List[RawStagedRecord] = []
        for batch_file in self.staging_dir.glob("batch_*.jsonl"):
            content = batch_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip():
                    try:
                        d = json.loads(line)
                        all_records.append(RawStagedRecord.from_dict(d))
                    except Exception:
                        pass

        # Sort chronologically by observed_at ASC
        all_records.sort(key=lambda r: (r.observed_at, r.query))

        # Partition into hourly cycles
        cycle_map: Dict[str, List[RawStagedRecord]] = {}
        for r in all_records:
            dt = parse_iso_utc(r.observed_at)
            cycle_id = dt.strftime("cycle_backfill_%Y%m%d_%H00")
            if cycle_id not in cycle_map:
                cycle_map[cycle_id] = []
            cycle_map[cycle_id].append(r)

        batches: List[StagedCycleBatch] = []
        for cycle_id, records in sorted(cycle_map.items()):
            # Deduplicate by normalized_query within cycle to preserve oracle count <= 1
            seen_queries: Set[str] = set()
            deduped_records: List[RawStagedRecord] = []
            seeds: Set[str] = set()
            sources: Set[str] = set()

            min_observed = records[0].observed_at
            for r in records:
                if r.normalized_query not in seen_queries:
                    seen_queries.add(r.normalized_query)
                    deduped_records.append(r)
                    seeds.add(r.normalized_query.split()[0])
                    sources.add(r.source)

            batch = StagedCycleBatch(
                cycle_id=cycle_id,
                executed_at=min_observed,
                records=deduped_records,
                seeds_used=sorted(seeds)[:5] or ["calculator"],
                sources=sorted(sources) or ["backfill"],
            )
            batches.append(batch)

        return batches


class IdempotentBulkInserter:
    """
    Executes atomic, topological DAG insertions into TrendHistoryDB.
    Guarantees advisory file locking with exponential backoff and universal idempotency.
    """

    def __init__(
        self,
        db: TrendHistoryDB,
        dry_run: bool = False,
        min_yield: float = 60.0,
        max_lock_retries: int = 5,
        initial_backoff: float = 0.5,
        max_backoff: float = 10.0,
    ):
        self.db = db
        self.dry_run = dry_run
        self.min_yield = float(min_yield)
        self.max_lock_retries = max_lock_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

    def _acquire_lock_with_backoff(self):
        """Acquires advisory lock on trend_history.db.lock with exponential backoff and jitter."""
        delay = self.initial_backoff
        for attempt in range(self.max_lock_retries):
            try:
                return self.db.acquire_lock(non_blocking=True)
            except (BlockingIOError, OSError):
                if attempt == self.max_lock_retries - 1:
                    raise
                jitter = random.uniform(0.0, 0.2)
                time.sleep(min(delay + jitter, self.max_backoff))
                delay *= 2.0
        return self.db.acquire_lock(non_blocking=True)

    def insert_batch(self, batch: StagedCycleBatch) -> Dict[str, Any]:
        """
        Persists a single cycle batch in strict topological DAG order:
        1. crawl_cycles (RUNNING)
        2. raw_crawl_observations (INSERT OR IGNORE)
        3. keyword_history (upsert_keyword_history)
        4. property_assignments (INSERT OR REPLACE)
        5. treg_metric_snapshots (INSERT OR REPLACE)
        6. jev_evaluations (INSERT OR REPLACE)
        7. niche_cluster_proposals (if sustained >= 3 cycles)
        8. UPDATE crawl_cycles (COMPLETED)
        """
        cycle_id = batch.cycle_id

        # Check idempotency: If cycle already exists with COMPLETED, skip to avoid streak drift
        existing_cycle = self.db.get_cycle(cycle_id)
        if existing_cycle and existing_cycle.status == "COMPLETED":
            return {
                "cycle_id": cycle_id,
                "status": "SKIPPED_ALREADY_COMPLETED",
                "observations_inserted": 0,
                "keywords_upserted": 0,
                "proposals_created": 0,
            }

        if self.dry_run:
            return {
                "cycle_id": cycle_id,
                "status": "DRY_RUN",
                "observations_inserted": len(batch.records),
                "keywords_upserted": len(batch.records),
                "proposals_created": 0,
            }

        proposals_created = 0

        # Acquire lock per-cycle boundary
        with self._acquire_lock_with_backoff():
            with self.db.transaction():
                # Step 1: crawl_cycles (RUNNING)
                self.db.start_cycle(
                    cycle_id=cycle_id,
                    seeds=batch.seeds_used,
                    sources=batch.sources,
                    metadata={"backfill": True, "staged_count": len(batch.records)},
                )

                # Step 2: raw_crawl_observations
                observations: List[RawObservationRecord] = []
                for rec in batch.records:
                    obs_id = hashlib.sha256(f"{cycle_id}:{rec.source}:{rec.normalized_query}".encode("utf-8")).hexdigest()[:16]
                    observations.append(
                        RawObservationRecord(
                            observation_id=obs_id,
                            cycle_id=cycle_id,
                            source=rec.source,
                            query=rec.query,
                            normalized_query=rec.normalized_query,
                            rank_position=rec.rank_position,
                            observed_velocity=rec.observed_velocity or 10.0,
                            observed_acceleration=rec.observed_acceleration,
                            observed_z_score=rec.observed_z_score or 1.0,
                            observed_at=rec.observed_at,
                            raw_payload=rec.raw_payload,
                        )
                    )
                self.db.record_observations(observations)

                # Step 3: keyword_history & downstream tables
                for rec in batch.records:
                    # Upsert keyword history and advance longitudinal streak
                    rollup = self.db.upsert_keyword_history(
                        query_slug=rec.query_slug,
                        query=rec.query,
                        cycle_id=cycle_id,
                        observed_velocity=rec.observed_velocity or 10.0,
                        intent_cluster="informational",
                        property_id=rec.property_id,
                        status="candidate",
                        observed_at=rec.observed_at,
                        override_acceleration=rec.observed_acceleration if rec.observed_acceleration != 0.0 else None,
                    )

                    # Step 4: property_assignments
                    asgn_rec = PropertyAssignmentRecord(
                        assignment_id=f"asgn_{rec.query_slug}_{cycle_id}",
                        query_slug=rec.query_slug,
                        cycle_id=cycle_id,
                        property_id=rec.property_id,
                        assignment_basis=rec.assignment_basis,
                        matched_existing_slug=None,
                        cannibalization_score=rec.cannibalization_risk,
                        current_position=100.0,
                        contamination_scan_passed=rec.contamination_scan_passed,
                        assigned_at=rec.observed_at,
                    )
                    self.db.record_property_assignment(asgn_rec)

                    # Step 5: treg_metric_snapshots
                    treg_rec = TregSnapshotRecord(
                        snapshot_id=f"treg_{rec.query_slug}_{cycle_id}",
                        query_slug=rec.query_slug,
                        cycle_id=cycle_id,
                        search_volume=rec.search_volume,
                        cpc_usd=rec.cpc_usd,
                        competition_index=rec.competition_index,
                        keyword_difficulty=rec.keyword_difficulty,
                        position_zero_vacant=rec.position_zero_vacant,
                        historical_stability=rec.historical_stability,
                        checked_at=rec.observed_at,
                    )
                    self.db.record_treg_snapshot(treg_rec)

                    # Step 6: jev_evaluations
                    jev_rec = JevEvaluationRecord(
                        evaluation_id=f"eval_{rec.query_slug}_{cycle_id}",
                        query_slug=rec.query_slug,
                        cycle_id=cycle_id,
                        property_id=rec.property_id,
                        jev_score=rec.jev_score,
                        durable_prob=rec.durable_prob,
                        composite_profit_yield=rec.composite_profit_yield,
                        cannibalization_risk=rec.cannibalization_risk,
                        action=rec.action,
                        target_asset_type=rec.target_asset_type,
                        passed_thresholds=rec.passed_thresholds,
                        decision_reason=rec.decision_reason,
                        evaluated_at=rec.observed_at,
                    )
                    self.db.record_jev_evaluation(jev_rec)

                    # Step 7: niche_cluster_proposals (Unassigned greenfield niche sustained >= 3 cycles)
                    if rec.property_id == "unassigned" and rollup.consecutive_cycles_count >= 3:
                        yield_qualifies = rec.composite_profit_yield >= 70.0
                        stability_qualifies = rec.historical_stability >= 0.80
                        jev_qualifies = rec.jev_score >= 1.25 and rec.durable_prob >= 0.50
                        volume_qualifies = rec.search_volume >= 500
                        pos0_qualifies = rec.position_zero_vacant == 1 or rec.keyword_difficulty <= 35.0

                        if yield_qualifies and stability_qualifies and jev_qualifies and volume_qualifies and pos0_qualifies:
                            proposal_id = f"prop_{rec.query_slug}"
                            proposal = NicheClusterProposal(
                                proposal_id=proposal_id,
                                cluster_slug=rec.query_slug,
                                cluster_title=rec.query.title(),
                                first_observed_cycle_id=rollup.first_seen_cycle_id,
                                confirmed_cycle_id=cycle_id,
                                consecutive_cycles_sustained=rollup.consecutive_cycles_count,
                                mean_composite_yield=rec.composite_profit_yield,
                                aggregate_search_volume=rec.search_volume,
                                mean_cpc_usd=rec.cpc_usd,
                                treg_stability_index=rec.historical_stability,
                                primary_queries=[rec.query],
                                recommended_domain_archetype="standalone_factory",
                                status="PROPOSED",
                                proposal_spec={"query": rec.query, "slug": rec.query_slug},
                                created_at=rec.observed_at,
                                updated_at=rec.observed_at,
                            )
                            self.db.create_niche_proposal(proposal)
                            proposals_created += 1

                # Step 8: Update crawl_cycles to COMPLETED
                self.db.complete_cycle(
                    cycle_id=cycle_id,
                    total_raw_observations=len(observations),
                    unique_queries_count=len(batch.records),
                    status="COMPLETED",
                )

        return {
            "cycle_id": cycle_id,
            "status": "COMPLETED",
            "observations_inserted": len(batch.records),
            "keywords_upserted": len(batch.records),
            "proposals_created": proposals_created,
        }

    def bulk_insert(self, batches: List[StagedCycleBatch], limit_cycles: Optional[int] = None) -> Dict[str, Any]:
        """Iterates through all chronological cycle batches and executes transactional persistence."""
        target_batches = batches[:limit_cycles] if limit_cycles else batches

        results = []
        total_obs = 0
        total_kws = 0
        total_props = 0
        skipped = 0

        for batch in target_batches:
            res = self.insert_batch(batch)
            results.append(res)
            if res["status"] == "SKIPPED_ALREADY_COMPLETED":
                skipped += 1
            else:
                total_obs += res.get("observations_inserted", 0)
                total_kws += res.get("keywords_upserted", 0)
                total_props += res.get("proposals_created", 0)

        return {
            "total_cycles_evaluated": len(target_batches),
            "cycles_completed": len(target_batches) - skipped,
            "cycles_skipped": skipped,
            "total_observations_inserted": total_obs,
            "total_keywords_upserted": total_kws,
            "total_proposals_created": total_props,
            "dry_run": self.dry_run,
            "status": "SUCCESS",
        }


def run_trend_backfill(
    db_path: Optional[Union[str, Path]] = None,
    staging_dir: Optional[Union[str, Path]] = None,
    dlq_path: Optional[Union[str, Path]] = None,
    vault_path: Optional[Union[str, Path]] = None,
    autojobs_log_path: Optional[Union[str, Path]] = None,
    brain_dir: Optional[Union[str, Path]] = None,
    fixture_path: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    limit_cycles: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint coordinating historical session crawl, staging, and bulk insertion.
    Zero em-dashes. Zero en-dashes.
    """
    db_p = Path(db_path or DEFAULT_DB_PATH).resolve()
    stg_p = Path(staging_dir or DEFAULT_STAGING_DIR).resolve()
    dlq_p = Path(dlq_path or DEFAULT_DLQ_PATH).resolve()
    v_p = Path(vault_path or DEFAULT_VAULT_VOID_PATH).resolve()
    log_p = Path(autojobs_log_path or DEFAULT_AUTOJOBS_LOG_PATH).resolve()
    b_p = Path(brain_dir or DEFAULT_BRAIN_DIR).resolve()
    f_p = Path(fixture_path).resolve() if fixture_path else None

    # Step 1: Initialize DB schema
    db = TrendHistoryDB(db_path=db_p)

    # Step 2: Crawl and stage records
    crawler = HistoricalSessionCrawler(
        staging_dir=stg_p,
        dlq_path=dlq_p,
        vault_path=v_p,
        autojobs_log_path=log_p,
        brain_dir=b_p,
        fixture_path=f_p,
    )
    crawler.stage_records()

    # Step 3: Consolidate and partition into chronological batches
    batches = crawler.consolidate_and_partition()

    # Step 4: Idempotent bulk insertion
    inserter = IdempotentBulkInserter(db=db, dry_run=dry_run)
    summary = inserter.bulk_insert(batches, limit_cycles=limit_cycles)
    summary["db_path"] = str(db_p)
    return summary
