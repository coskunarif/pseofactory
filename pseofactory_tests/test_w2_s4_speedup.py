"""
Regression & benchmark tests for Wave 2 Lane S4 speedups:
  1. IndexingPreflightEngine parallel per-file inspection & thread safety
  2. PartnerTrackingEngine lazy once-per-process monetization bootstrap (zero import side effect)
  3. EmailIngestionEngine parallel 5-folder Zoho polling + single coalesced atomic state write
  4. TrendHistoryDB partial index idx_treg_snapshots_poisoned & bounded get_past_velocities

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest

from pseofactory.email_ingest import ZOHO_POLL_MAILBOXES, EmailIngestionEngine
from pseofactory.indexing.preflight import (
    IndexingPreflightEngine,
    _FastPreflightHTMLParser,
    _parse_html_preflight_fast,
)
import pseofactory.partner_tracker as pt_mod
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.trends.models import RawObservationRecord, TregSnapshotRecord


def _make_sample_html(
    canonical_url: str,
    title: str = "Sample Tool",
    words: int = 180,
    robots: str = "",
    viewport: bool = True,
    quick_answer: bool = True,
) -> str:
    body_words = " ".join(["margin"] * words)
    robots_tag = f'<meta name="robots" content="{robots}">' if robots else ""
    vp_tag = '<meta name="viewport" content="width=device-width, initial-scale=1.0">' if viewport else ""
    qa_block = '<aside class="quick-answer">Direct answer summary here.</aside>' if quick_answer else ""
    return (
        f"<!DOCTYPE html><html lang='en'><head>"
        f"<title>{title}</title>"
        f'<link rel="canonical" href="{canonical_url}">'
        f"{robots_tag}{vp_tag}"
        f"</head><body>"
        f"<h1>{title}</h1>"
        f"{qa_block}"
        f"<p>{body_words}</p>"
        f"</body></html>"
    )


def test_preflight_parallel_inspect_dist_deterministic_and_thread_safe(tmp_path: Path) -> None:
    IndexingPreflightEngine.clear_cache()

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)

    # Create 14 pages across pass, thin, canonical mismatch, and noindex states
    expected_pass: List[str] = []
    for idx in range(10):
        slug = f"tool-{idx:02d}"
        page_dir = dist_dir / "tools" / slug
        page_dir.mkdir(parents=True)
        url = f"https://example.com/tools/{slug}/"
        expected_pass.append(url)
        (page_dir / "index.html").write_text(_make_sample_html(url, title=f"Tool {idx}"), encoding="utf-8")

    # 2 thin pages
    for slug in ("thin-a", "thin-b"):
        p = dist_dir / "tools" / slug
        p.mkdir(parents=True)
        url = f"https://example.com/tools/{slug}/"
        (p / "index.html").write_text(_make_sample_html(url, words=20), encoding="utf-8")

    # 1 canonical mismatch
    cm = dist_dir / "tools" / "mismatch"
    cm.mkdir(parents=True)
    (cm / "index.html").write_text(
        _make_sample_html("https://example.com/tools/wrong/"),
        encoding="utf-8",
    )

    # 1 meta noindex
    ni = dist_dir / "tools" / "noindex-page"
    ni.mkdir(parents=True)
    (ni / "index.html").write_text(
        _make_sample_html("https://example.com/tools/noindex-page/", robots="noindex, nofollow"),
        encoding="utf-8",
    )

    eng1 = IndexingPreflightEngine(domain="example.com", property_id="example", dist_dir=dist_dir, tier1_cap=5)
    rep1 = eng1.inspect_dist(dist_dir)

    IndexingPreflightEngine.clear_cache()
    eng2 = IndexingPreflightEngine(domain="example.com", property_id="example", dist_dir=dist_dir, tier1_cap=5)
    rep2 = eng2.inspect_dist(dist_dir)

    assert rep1.total_inspected == 14
    assert rep1.passed_count == 10
    assert rep1.blocked_count == 4
    assert rep1.sitemap_eligible_urls == expected_pass
    assert rep1.push_eligible_urls == expected_pass[:5]
    assert rep1.sitemap_eligible_urls == rep2.sitemap_eligible_urls
    assert rep1.push_eligible_urls == rep2.push_eligible_urls
    assert rep1.blocked_urls == rep2.blocked_urls
    assert rep1.breakdown == rep2.breakdown

    # Verify selectolax metadata matches _FastPreflightHTMLParser exactly
    sample_html = _make_sample_html("https://example.com/tools/check/", robots="index, follow")
    meta_fast, wc_fast = _parse_html_preflight_fast(sample_html)
    fb_parser = _FastPreflightHTMLParser()
    fb_parser.feed(sample_html)
    assert meta_fast.canonical_hrefs == fb_parser.canonical_hrefs
    assert meta_fast.meta_robots == fb_parser.meta_robots
    assert meta_fast.meta_viewport == fb_parser.meta_viewport
    assert meta_fast.h1_count == fb_parser.h1_count
    assert meta_fast.has_early_answer == fb_parser.has_early_answer
    assert wc_fast > 150


def test_partner_tracker_lazy_monetization_bootstrap_no_import_side_effect() -> None:
    repo_root = str(Path(__file__).resolve().parent.parent)
    code = (
        "import pseofactory.partner_tracker as pt\n"
        "assert pt._MONETIZATION_BOOTSTRAP_DONE is False, 'Bootstrap ran at import time!'\n"
        "print('IMPORT_CLEAN')\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, f"stderr={res.stderr}\nstdout={res.stdout}"
    assert "IMPORT_CLEAN" in res.stdout

    # Also verify once-per-process lazy invocation on PartnerTrackingEngine.__init__
    calls = {"n": 0}
    orig_done = pt_mod._MONETIZATION_BOOTSTRAP_DONE
    orig_fn = pt_mod.ensure_canonical_agy_monetization_state

    def fake_bootstrap() -> None:
        calls["n"] += 1
        pt_mod._MONETIZATION_BOOTSTRAP_DONE = True

    try:
        pt_mod._MONETIZATION_BOOTSTRAP_DONE = False
        with patch.object(pt_mod, "ensure_canonical_agy_monetization_state", side_effect=fake_bootstrap):
            pt_mod.PartnerTrackingEngine()
            pt_mod.PartnerTrackingEngine()
        assert calls["n"] == 1
    finally:
        pt_mod._MONETIZATION_BOOTSTRAP_DONE = orig_done
        assert pt_mod.ensure_canonical_agy_monetization_state is orig_fn


def test_email_ingest_sync_all_parallel_five_folders_and_single_state_write(tmp_path: Path) -> None:
    cache_path = tmp_path / "email_cache.json"
    state_path = tmp_path / "email_state.json"
    engine = EmailIngestionEngine(
        cache_path=str(cache_path),
        state_path=str(state_path),
        himalaya_bin="/usr/bin/fake-himalaya",
    )

    polled_folders: List[str] = []
    delay_s = 0.15

    def fake_himalaya(args: List[str]) -> Tuple[int, str, str]:
        if args[:2] == ["envelope", "list"]:
            time.sleep(delay_s)
            folder = args[args.index("-m") + 1]
            polled_folders.append(folder)
            if folder == "Inbox":
                return 0, json.dumps({
                    "envelopes": [{
                        "id": "101",
                        "message_id": "<in-101@gusto.com>",
                        "date": "2026-11-20T10:00:00Z",
                        "subject": "Gusto Partner Application",
                        "from": [{"name": "Gusto Team", "email": "noelle.hyra@gusto.com"}],
                        "flags": [],
                    }]
                }), ""
            if folder == "Sent":
                return 0, json.dumps({
                    "envelopes": [{
                        "id": "201",
                        "message_id": "<sent-201@profithelm.com>",
                        "date": "2026-11-20T11:00:00Z",
                        "subject": "Mercury Partnership Followup",
                        "from": [{"name": "Arif Coskun", "email": "arif.coskun@profithelm.com"}],
                        "to": [{"name": "Mercury", "email": "partnerships@mercury.com"}],
                        "flags": [],
                    }]
                }), ""
            if folder == "Notification":
                return 0, json.dumps({
                    "envelopes": [{
                        "id": "301",
                        "message_id": "<notif-301@cj.com>",
                        "date": "2026-11-20T12:00:00Z",
                        "subject": "FreeTaxUSA Affiliate Program Approved",
                        "from": [{"name": "CJ Affiliate", "email": "affiliates@freetaxusa.com"}],
                        "flags": [],
                    }]
                }), ""
            return 0, json.dumps({"envelopes": []}), ""
        if args[:2] == ["message", "read"]:
            return 0, "Partner details confirmed.", ""
        return 1, "", "unexpected"

    save_state_calls = {"n": 0}
    orig_save_state = engine.save_state

    def counting_save_state(state: Dict[str, Any]) -> None:
        save_state_calls["n"] += 1
        orig_save_state(state)

    with patch.object(engine, "run_himalaya_command", side_effect=fake_himalaya), patch.object(
        engine, "save_state", side_effect=counting_save_state
    ):
        t0 = time.perf_counter()
        msgs = engine.sync_all(force=True)
        elapsed = time.perf_counter() - t0

    assert set(polled_folders) == set(ZOHO_POLL_MAILBOXES)
    assert len(polled_folders) == 5
    # 5 parallel fetches at 0.15s each must complete well below 5 * 0.15s = 0.75s
    assert elapsed < 0.45, f"Expected parallel ~1x latency (<0.45s), got {elapsed:.3f}s"
    # Coalesced into a single atomic save_state write instead of 5 sequential writes
    assert save_state_calls["n"] == 1
    assert len(msgs) == 3
    assert state_path.is_file()
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_data["accounts"]["zoho"]["last_success"] is True


def test_trends_db_partial_index_and_bounded_get_past_velocities(tmp_path: Path) -> None:
    db_path = tmp_path / "test_trends.db"
    with TrendHistoryDB(db_path) as db:
        conn = db.get_connection()
        idx_names = {
            str(r[0])
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
        assert "idx_treg_snapshots_poisoned" in idx_names

        # Verify EXPLAIN QUERY PLAN for purge_poisoned_treg_snapshots uses partial index
        eqp_rows = conn.execute(
            "EXPLAIN QUERY PLAN DELETE FROM treg_metric_snapshots "
            "WHERE search_volume = 0 AND cpc_usd = 0.0 AND keyword_difficulty = 50.0;"
        ).fetchall()
        eqp_text = " ".join(str(r["detail"]) for r in eqp_rows).upper()
        assert "IDX_TREG_SNAPSHOTS_POISONED" in eqp_text

        for cid in ("c1", "c2", "c3", "c4"):
            db.start_cycle(cycle_id=cid, seeds=["q"], sources=["google_trends"])
            db.complete_cycle(cycle_id=cid, total_raw_observations=1, unique_queries_count=1, status="COMPLETED")

        db.upsert_keyword_history(
            query_slug="q",
            query="q",
            cycle_id="c1",
            observed_velocity=1.1,
            intent_cluster="calc",
        )
        db.record_treg_snapshot(
            TregSnapshotRecord(
                snapshot_id="s_poisoned",
                query_slug="q",
                cycle_id="c1",
                search_volume=0,
                cpc_usd=0.0,
                competition_index=0.0,
                keyword_difficulty=50.0,
                position_zero_vacant=0,
                historical_stability=0.5,
                volume_delta_pct=0.0,
                cpc_delta_pct=0.0,
                volatility_score=0.0,
                checked_at="2026-11-20T00:00:00+00:00",
            )
        )
        db.record_treg_snapshot(
            TregSnapshotRecord(
                snapshot_id="s_valid",
                query_slug="q",
                cycle_id="c2",
                search_volume=1200,
                cpc_usd=2.5,
                competition_index=0.3,
                keyword_difficulty=35.0,
                position_zero_vacant=1,
                historical_stability=0.9,
                volume_delta_pct=0.1,
                cpc_delta_pct=0.0,
                volatility_score=0.1,
                checked_at="2026-11-21T00:00:00+00:00",
            )
        )
        purged = db.purge_poisoned_treg_snapshots()
        assert purged == 1
        remaining_ids = [
            r[0] for r in conn.execute("SELECT snapshot_id FROM treg_metric_snapshots;").fetchall()
        ]
        assert remaining_ids == ["s_valid"]

        # Verify bounded get_past_velocities uses covering index + LIMIT ?
        db.record_observations(
            [
                RawObservationRecord("o1", "c1", "google_trends", "q", "q", 1, 1.1, 0.0, 1.0, "2026-11-18T00:00:00+00:00"),
                RawObservationRecord("o2", "c2", "google_trends", "q", "q", 1, 2.2, 0.0, 1.1, "2026-11-19T00:00:00+00:00"),
                RawObservationRecord("o3", "c3", "google_trends", "q", "q", 1, 3.3, 0.0, 1.2, "2026-11-20T00:00:00+00:00"),
                RawObservationRecord("o4", "c4", "google_trends", "q", "q", 1, 4.4, 0.0, 1.3, "2026-11-21T00:00:00+00:00"),
            ]
        )
        vel_eqp = conn.execute(
            "EXPLAIN QUERY PLAN SELECT cycle_id, observed_velocity FROM raw_crawl_observations "
            "WHERE normalized_query = ? ORDER BY observed_at DESC LIMIT ?;",
            ("q", 50),
        ).fetchall()
        vel_plan = " ".join(str(r["detail"]) for r in vel_eqp).upper()
        assert "USING COVERING INDEX IDX_OBSERVATIONS_NORM_QUERY_OBS_COV" in vel_plan
        assert "TEMP B-TREE" not in vel_plan

        assert db.get_past_velocities("q", current_cycle_id="c4") == [3.3, 2.2]
        assert db.get_past_velocities("q", current_cycle_id="c4", limit=2) == [3.3]

        # Drop partial index, then open read_only=True and verify NO DDL is executed
        conn.execute("DROP INDEX idx_treg_snapshots_poisoned;")

    with TrendHistoryDB(db_path, read_only=True) as ro_db:
        ro_conn = ro_db.get_connection()
        ro_indexes = {
            str(r[0])
            for r in ro_conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
        assert "idx_treg_snapshots_poisoned" not in ro_indexes
