"""
Wave 1 Lane C regression tests:
- Item 14: SyndicationWALQueue.process_queue flock, COMPLETED skip, concurrent enqueue preservation, bounded retry sleep
- Item 15: dry_run=True trends cron & collector DB isolation, read-only URI in _load_trend_db_cache without DDL side effects
- Item 16: broadcast_ledger.json parse error preserves corrupt file without wiping history
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest


def test_wal_process_queue_skips_completed_and_preserves_history(tmp_path: Path) -> None:
    from pseofactory.distributor import SyndicationWALQueue

    q = SyndicationWALQueue(property_id="tenant_alpha", queues_dir=tmp_path / "queues")
    completed_rec = q.enqueue({"slug": "already-done"}, event_id="evt_done_1")
    q.complete_event(completed_rec["event_id"], status="COMPLETED")
    q.enqueue({"slug": "needs-work"}, event_id="evt_pending_2")

    seen_slugs = []

    def handler(payload: dict) -> bool:
        seen_slugs.append(payload["slug"])
        return True

    res = q.process_queue(handler)
    assert res["processed"] == 1
    assert res["quarantined"] == 0
    assert seen_slugs == ["needs-work"]

    # Completed record must remain preserved in the WAL file
    lines = [json.loads(line) for line in q.queue_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["event_id"] == "evt_done_1"
    assert lines[0]["status"] == "COMPLETED"

    # Re-running process_queue must not re-run the already-COMPLETED item
    res2 = q.process_queue(handler)
    assert res2["processed"] == 0
    assert seen_slugs == ["needs-work"]


def test_wal_process_queue_preserves_concurrent_enqueues_and_serializes(tmp_path: Path) -> None:
    from pseofactory.distributor import SyndicationWALQueue

    queues_dir = tmp_path / "queues"
    q1 = SyndicationWALQueue(property_id="tenant_beta", queues_dir=queues_dir)
    q2 = SyndicationWALQueue(property_id="tenant_beta", queues_dir=queues_dir)
    q1.enqueue({"slug": "first-item"}, event_id="evt_first")

    handled_order = []
    in_handler = threading.Event()
    enqueue_done = threading.Event()

    def slow_handler(payload: dict) -> bool:
        handled_order.append(payload["slug"])
        if payload["slug"] == "first-item":
            in_handler.set()
            assert enqueue_done.wait(timeout=3.0), "Concurrent enqueue deadlocked on queue lock"
        return True

    def concurrent_enqueuer() -> None:
        assert in_handler.wait(timeout=3.0)
        q2.enqueue({"slug": "concurrent-item"}, event_id="evt_concurrent")
        enqueue_done.set()

    t_enq = threading.Thread(target=concurrent_enqueuer)
    t_enq.start()
    res = q1.process_queue(slow_handler)
    t_enq.join(timeout=3.0)

    assert res["processed"] == 1
    assert res["remaining"] == 1
    remaining_records = [
        json.loads(line) for line in q1.queue_file.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert [r["event_id"] for r in remaining_records] == ["evt_concurrent"]

    # Second pass processes the concurrently enqueued event
    res2 = q1.process_queue(lambda payload: handled_order.append(payload["slug"]) or True)
    assert res2["processed"] == 1
    assert res2["remaining"] == 0
    assert handled_order == ["first-item", "concurrent-item"]


def test_wal_process_queue_serializes_concurrent_processors(tmp_path: Path) -> None:
    from pseofactory.distributor import SyndicationWALQueue

    queues_dir = tmp_path / "queues"
    q1 = SyndicationWALQueue(property_id="tenant_gamma", queues_dir=queues_dir)
    q2 = SyndicationWALQueue(property_id="tenant_gamma", queues_dir=queues_dir)
    q1.enqueue({"slug": "single-item"}, event_id="evt_single")

    calls = []
    lock = threading.Lock()
    entered_first = threading.Event()

    def handler(payload: dict) -> bool:
        with lock:
            calls.append(payload["slug"])
        entered_first.set()
        time.sleep(0.05)
        return True

    results = []

    def run_proc(queue_inst: SyndicationWALQueue) -> None:
        results.append(queue_inst.process_queue(handler))

    t1 = threading.Thread(target=run_proc, args=(q1,))
    t1.start()
    assert entered_first.wait(timeout=3.0)
    t2 = threading.Thread(target=run_proc, args=(q2,))
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert calls == ["single-item"]
    assert sum(r["processed"] for r in results) == 1


def test_wal_process_queue_no_sleep_after_final_attempt(tmp_path: Path) -> None:
    from pseofactory.distributor import SyndicationWALQueue

    q = SyndicationWALQueue(
        property_id="tenant_retry",
        queues_dir=tmp_path / "queues",
        max_attempts=3,
    )
    q.enqueue({"slug": "failing-item"}, event_id="evt_fail_1")

    sleeps = []
    attempts_seen = []

    def failing_handler(payload: dict) -> bool:
        attempts_seen.append(payload["slug"])
        raise RuntimeError("upstream 503")

    res = q.process_queue(
        failing_handler,
        backoff_schedule=[0.11, 0.22, 0.44],
        sleep_fn=sleeps.append,
    )
    assert len(attempts_seen) == 3
    # Only 2 sleeps between 3 attempts; never sleep after final failed attempt
    assert sleeps == [0.11, 0.22]
    assert res["processed"] == 0
    assert res["quarantined"] == 1
    assert res["remaining"] == 0

    dlq_lines = [json.loads(line) for line in q.dlq_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(dlq_lines) == 1
    assert dlq_lines[0]["event_id"] == "evt_fail_1"
    assert dlq_lines[0]["status"] == "QUARANTINED"
    assert dlq_lines[0]["attempts"] == 3


def test_dry_run_trends_cron_and_collector_never_mutate_db(tmp_path: Path) -> None:
    from pseofactory.trends.collectors import MultiSourceCollector, StatutoryEconomicDatasetCollector
    from pseofactory.trends.cron import TrendCronRunner
    from pseofactory.trends.db import TrendHistoryDB

    db_dir = tmp_path / "db_ro_dir"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "trend_history.db"

    with TrendHistoryDB(db_path) as db:
        conn = db.get_connection()
        conn.execute("DELETE FROM statutory_economic_timeseries;")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM statutory_economic_timeseries;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM crawl_cycles;").fetchone()[0] == 0

    # Make DB file read-only (0444) so any write attempt or RW pragma would fail or show up
    os.chmod(db_path, 0o444)
    try:
        # 1. Direct collector dry_run=True must not call sync_to_db
        stat_col = StatutoryEconomicDatasetCollector(db_path=db_path, dry_run=True)
        with patch.object(stat_col, "sync_to_db", side_effect=AssertionError("sync_to_db called in dry_run")) as _:
            spikes = stat_col.harvest_statutory_spikes()
            assert len(spikes) > 0

        # 2. MultiSourceCollector dry_run=True must not mutate DB
        multi = MultiSourceCollector(
            collectors=[StatutoryEconomicDatasetCollector(db_path=db_path)],
            dry_run=True,
        )
        m_spikes = multi.harvest(["tax"], dry_run=True)
        assert len(m_spikes) > 0

        # 3. TrendCronRunner.run_cycle(dry_run=True) must never mutate DB or call sync_to_db
        runner = TrendCronRunner(db_path=db_path)
        with patch(
            "pseofactory.trends.collectors.StatutoryEconomicDatasetCollector.sync_to_db",
            side_effect=AssertionError("sync_to_db called during dry_run cron"),
        ), patch("pseofactory.trends.collectors.make_resilient_request", return_value=None):
            res = runner.run_cycle(
                cycle_id="cycle_dry_run_safety",
                seeds=["section 179"],
                dry_run=True,
            )
            assert res["dry_run"] is True
            assert res["status"] == "COMPLETED"

        # Verify DB still has 0 rows in statutory_economic_timeseries and crawl_cycles
        with TrendHistoryDB(db_path, read_only=True) as ro_db:
            ro_conn = ro_db.get_connection()
            assert ro_conn.execute("SELECT COUNT(*) FROM statutory_economic_timeseries;").fetchone()[0] == 0
            assert ro_conn.execute("SELECT COUNT(*) FROM crawl_cycles;").fetchone()[0] == 0
    finally:
        os.chmod(db_path, 0o644)


def test_load_trend_db_cache_read_only_no_ddl_side_effects(tmp_path: Path) -> None:
    from pseofactory.proprietary_signals import _load_trend_db_cache
    from pseofactory.trends.db import TrendHistoryDB

    db_path = tmp_path / "signals_ro.db"
    with TrendHistoryDB(db_path) as db:
        conn = db.get_connection()
        conn.execute("DROP INDEX IF EXISTS idx_jev_eval_query_slug;")
        conn.execute("DROP INDEX IF EXISTS idx_treg_snapshots_slug_metrics;")
        conn.commit()

    # Keep file writable (0644) to prove _load_trend_db_cache does NOT run CREATE INDEX
    cache = _load_trend_db_cache(db_path=db_path)
    assert "series_by_id" in cache
    assert "keywords_by_prop" in cache

    check_conn = sqlite3.connect(str(db_path))
    try:
        idx_names = {
            row[0]
            for row in check_conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
        assert "idx_jev_eval_query_slug" not in idx_names
        assert "idx_treg_snapshots_slug_metrics" not in idx_names
    finally:
        check_conn.close()

    # Also verify read-only mode succeeds against a 0444 DB file
    os.chmod(db_path, 0o444)
    try:
        ro_cache = _load_trend_db_cache(db_path=db_path)
        assert "series_by_id" in ro_cache
    finally:
        os.chmod(db_path, 0o644)


def test_broadcast_ledger_parse_error_preserves_corrupt_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    from pseofactory.distributor import dispatch_to_distribution_lead

    repo_dir = tmp_path / "tenant_repo"
    dist_dir = repo_dir / "dist"
    agy_dir = repo_dir / ".agy"
    tool_slug = "section-179-calculator"
    (dist_dir / "tools" / tool_slug).mkdir(parents=True)
    (dist_dir / "tools" / tool_slug / "index.html").write_text(
        "<html><head><title>Section 179</title></head><body><h1>Section 179</h1></body></html>",
        encoding="utf-8",
    )
    agy_dir.mkdir(parents=True)

    corrupt_payload = '[{"slug": "prior-live-tool", "youtube_video_id": "vid_preserve_999"'
    b_ledger_path = agy_dir / "broadcast_ledger.json"
    b_ledger_path.write_text(corrupt_payload, encoding="utf-8")

    tools = [
        {
            "slug": tool_slug,
            "title": "Section 179 Deduction Calculator",
            "description": "Calculate IRC Section 179 equipment deductions.",
            "parameterized_url": f"https://profithelm.com/tools/{tool_slug}/",
        }
    ]

    with caplog.at_level(logging.ERROR, logger="pseofactory.distributor"):
        res = dispatch_to_distribution_lead(
            run_id="w1-lane-c-corrupt-ledger",
            property_id="profithelm",
            dry_run=False,
            dist_dir=dist_dir,
            tools=tools,
            linkedin_queue_path=agy_dir / "linkedin_queue.json",
        )

    assert res["status"] == "SUCCESS"
    # Original corrupt file must NOT be silently wiped/overwritten
    assert b_ledger_path.read_text(encoding="utf-8") == corrupt_payload
    quarantined = list(agy_dir.glob("broadcast_ledger.corrupt.*.json"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == corrupt_payload
    assert any("Failed to parse broadcast ledger" in rec.message for rec in caplog.records)
