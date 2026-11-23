"""
Wave 3: Autonomy & Indexation + Wave 2 host_estate CI Fixes Regression Suite.
Covers:
  0. Wave 2 host_estate CI fixes (restricted YMYL commercial /r/ link stripping + ProfitHelm GSC metrics preservation)
  1. trend_history.db PRAGMAs, covering indexes, EXPLAIN QUERY PLAN (0 temp B-trees), and gsc_daily_metrics unfreeze
  2. Fair per-tenant GSC quota partitioning, tool-over-governance push priority, rollover preservation,
     unified fast-index IndexNow key, and per-tenant indexmysite_project_id
  3. Cross-day BUILD_PAGE stranded-slug recovery with bounded retry/cooldown + GitOps auto_rollback hook
  4. Safe closed-loop auto-remediation shipping via dispatch_to_shipper (daily cap + dist fingerprint +
     cross-domain broadcast ledger repair + honest total_recompiled)
  5. Supervisor containment & resilience (require_manifest=True default, SIGTERM streak recording,
     ROLLBACK_CI_FAILED circuit-breaker, and /tmp/ DLQ pruning)
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 0. Wave 2 host_estate CI Fixes
# ---------------------------------------------------------------------------


def test_restricted_ymyl_page_strips_commercial_r_links_in_overlay_and_retrofit(tmp_path: Path) -> None:
    """
    Verifies both halves of Prexvo YMYL / commercial parity:
    1. Genuinely restricted public-service YMYL slugs (e.g. pslf-qualifying-payment-simulator)
       NEVER emit or retain commercial /r/ links across inject_overlay_into_html,
       reposition_affiliate_placements_from_gsc_signals, and RetroReflectionEngine.retrofit_estate
       (Pass 1 -> Pass 2 -> Pass 3).
    2. Non-restricted commercial slugs (e.g. student-loan-forgiveness-tax-bomb-insolvency-calculator)
       carrying a stale PSLF overlay with restricted_public_service=True self-heal by stripping
       the stale guardrail overlay while preserving commercial /r/ links so Plane 3 and
       audit_monetization_and_datapack_ui_ux_surfaces both pass with 0 violations.
    """
    from pseofactory.affiliates import (
        reposition_affiliate_placements_from_gsc_signals,
        strip_commercial_affiliate_blocks_for_restricted_ymyl,
    )
    from pseofactory.contracts import detect_asset_partner_roster_and_slot_issues
    from pseofactory.gsc_remediation import inject_overlay_into_html
    from pseofactory.maintenance import RetroReflectionEngine

    # Part A: Genuinely restricted public-service YMYL slug
    pslf_slug = "pslf-qualifying-payment-simulator"
    mixed_pslf_html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><title>PSLF Qualifying Payment Simulator 2026 | Prexvo</title>
<meta name="description" content="Calculate PSLF 120 qualifying monthly payments, tax-free discharge timelines, and ECF certification progress under Title IV 34 CFR 685.219(c).">
<link rel="canonical" href="https://prexvo.com/tools/{pslf_slug}/">
</head><body><main>
<h1>PSLF 120 Qualifying Payment Simulator</h1>
<div class="calc-inline-cta" data-partner="splash_financial">
  <div class="calc-inline-cta-copy"><p>Compare fixed refinance rates.</p></div>
  <a href="/r/splash_financial?source_tool={pslf_slug}&amp;cta_slot=calculator_result_inline" rel="noopener sponsored nofollow">Check Rates</a>
</div>
<section class="refinance-partner-section" data-primary-partner="splash_financial">
  <div class="partner-card" data-partner="splash_financial">
    <a href="/r/splash_financial?source_tool={pslf_slug}&amp;cta_slot=calculator_primary_cta">Splash</a>
  </div>
  <div class="partner-card" data-partner="credible">
    <a href="/r/credible?source_tool={pslf_slug}&amp;cta_slot=partner_matrix_card">Credible</a>
  </div>
  <div class="partner-card" data-partner="lendkey">
    <a href="/r/lendkey?source_tool={pslf_slug}&amp;cta_slot=partner_matrix_card">LendKey</a>
  </div>
</section>
<div class="comparison-table-cta-bar" data-partner="splash_financial">
  <a href="/r/splash_financial?source_tool={pslf_slug}&amp;cta_slot=comparison_table_cta">Compare Refi</a>
</div>
<section class="overlay-section overlay-partner-guardrail ymyl-public-service-guardrail card" data-commercial-offers="none" data-restricted-public-service="true">
  <div class="partner-card"><h3>Title IV Public Service Protection</h3><p>Protected under 34 CFR Part 685.</p></div>
</section>
</main></body></html>"""

    before_issues = detect_asset_partner_roster_and_slot_issues(
        mixed_pslf_html,
        property_id="prexvo",
        slug=pslf_slug,
        rel_path=f"tools/{pslf_slug}/index.html",
    )
    assert any("Restricted public-service YMYL page contains forbidden commercial /r/ links" in x for x in before_issues)

    stripped = strip_commercial_affiliate_blocks_for_restricted_ymyl(mixed_pslf_html)
    assert "/r/" not in stripped
    assert "calc-inline-cta" not in stripped
    assert "comparison-table-cta-bar" not in stripped
    assert detect_asset_partner_roster_and_slot_issues(
        stripped, property_id="prexvo", slug=pslf_slug, rel_path=f"tools/{pslf_slug}/index.html"
    ) == []

    overlay_injected = inject_overlay_into_html(
        mixed_pslf_html.replace('data-restricted-public-service="true"', ""),
        {
            "slug": pslf_slug,
            "property_id": "prexvo",
            "tenant_id": "prexvo",
            "query": "public service loan forgiveness calculator",
            "restricted_public_service": True,
            "commercial_offers_allowed": False,
        },
    )
    assert "/r/" not in overlay_injected
    assert detect_asset_partner_roster_and_slot_issues(
        overlay_injected, property_id="prexvo", slug=pslf_slug, rel_path=f"tools/{pslf_slug}/index.html"
    ) == []

    repositioned, rep_meta = reposition_affiliate_placements_from_gsc_signals(
        mixed_pslf_html, property_id="prexvo", slug=pslf_slug
    )
    assert rep_meta["restricted_public_service"] is True
    assert "/r/" not in repositioned

    dist_dir = tmp_path / "prexvo" / "dist"
    page_path = dist_dir / "tools" / pslf_slug / "index.html"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(mixed_pslf_html, encoding="utf-8")

    RetroReflectionEngine.retrofit_estate(dist_dir=dist_dir, property_id="prexvo")
    after_p1 = page_path.read_text(encoding="utf-8")
    assert "/r/" not in after_p1
    assert detect_asset_partner_roster_and_slot_issues(
        after_p1, property_id="prexvo", slug=pslf_slug, rel_path=f"tools/{pslf_slug}/index.html"
    ) == []

    RetroReflectionEngine.retrofit_estate(dist_dir=dist_dir, property_id="prexvo")
    after_p2 = page_path.read_text(encoding="utf-8")
    assert "/r/" not in after_p2
    RetroReflectionEngine.retrofit_estate(dist_dir=dist_dir, property_id="prexvo")
    assert page_path.read_text(encoding="utf-8") == after_p2

    # Part B: Commercial insolvency calculator carrying stale restricted overlay self-heals
    insolv_slug = "student-loan-forgiveness-tax-bomb-insolvency-calculator"
    stale_insolv_html = mixed_pslf_html.replace(pslf_slug, insolv_slug).replace(
        "PSLF Qualifying Payment Simulator", "Student Loan Forgiveness Tax Bomb Calculator"
    )
    insolv_path = dist_dir / "tools" / insolv_slug / "index.html"
    insolv_path.parent.mkdir(parents=True, exist_ok=True)
    insolv_path.write_text(stale_insolv_html, encoding="utf-8")
    ov_dir = tmp_path / "prexvo" / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    (ov_dir / f"{insolv_slug}.json").write_text(
        json.dumps(
            {
                "slug": insolv_slug,
                "property_id": "prexvo",
                "tenant_id": "prexvo",
                "query": "public service loan forgiveness calculator",
                "title_rewrite": "Public Service Loan Forgiveness Calculator 2026 | Prexvo",
                "meta_description": "Calculate IDR student loan forgiveness tax bomb liability and IRS Form 982 insolvency exclusion relief under IRC Section 108(a)(1)(B) in 2026.",
                "restricted_public_service": True,
                "commercial_offers_allowed": False,
                "partner_offer": None,
            }
        ),
        encoding="utf-8",
    )
    RetroReflectionEngine.retrofit_estate(dist_dir=dist_dir, property_id="prexvo")
    healed_insolv = insolv_path.read_text(encoding="utf-8")
    assert 'data-restricted-public-service="true"' not in healed_insolv
    assert "/r/" in healed_insolv
    healed_ov = json.loads((ov_dir / f"{insolv_slug}.json").read_text(encoding="utf-8"))
    assert healed_ov.get("restricted_public_service") is False
    assert healed_ov.get("commercial_offers_allowed") is True
    assert isinstance(healed_ov.get("partner_offer"), dict)


def test_profithelm_feedback_pass_preserves_gsc_metrics_from_lifecycle_telemetry(tmp_path: Path) -> None:
    """
    Verifies run_gsc_affiliate_placement_feedback_pass hydrates real page-level GSC metrics
    from .agy/gsc_lifecycle_telemetry.json and preserves persisted ledger metrics when
    statutory.db is not present in an isolated tmp copy.
    """
    from pseofactory.affiliates import (
        load_persisted_gsc_placement_metrics_by_slug,
        run_gsc_affiliate_placement_feedback_pass,
    )

    repo_root = tmp_path / "profithelm"
    dist_dir = repo_root / "dist"
    agy_dir = repo_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    tool_html = """<!DOCTYPE html>
<html lang="en"><head><title>Section 179 Deduction Calculator</title>
<link rel="canonical" href="https://profithelm.com/tools/section-179-calculator/"></head>
<body><main><h1>Section 179 Calculator</h1></main></body></html>"""
    s179 = dist_dir / "tools" / "section-179-calculator" / "index.html"
    s179.parent.mkdir(parents=True, exist_ok=True)
    s179.write_text(tool_html, encoding="utf-8")

    # Sparse remediation queue WITHOUT section-179-calculator (matching live host_estate condition)
    (agy_dir / "gsc_remediation_queue.json").write_text(
        json.dumps({"tenants": {"profithelm": {"tasks": [{"slug": "other-tool", "query": "other", "impressions": 5, "position": 40.0}]}}}),
        encoding="utf-8",
    )
    # Real multidimensional lifecycle telemetry WITH section-179-calculator windows + device splits
    (agy_dir / "gsc_lifecycle_telemetry.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "property_id": "profithelm",
                "page_windows_by_path": {
                    "/tools/section-179-calculator": {
                        "recent_28d": {"rolled_up": {"clicks": 0, "impressions": 77, "ctr": 0.0, "position": 63.91}},
                        "recent_90d": {"rolled_up": {"clicks": 0, "impressions": 192, "ctr": 0.0, "position": 67.95}},
                    }
                },
                "page_device_diagnostics": {
                    "/tools/section-179-calculator": {
                        "mobile_impressions": 30,
                        "desktop_impressions": 108,
                        "mobile_ctr": 0.0,
                        "desktop_ctr": 0.0,
                        "mobile_ctr_gap": 0.0,
                        "device_focus": "DESKTOP_DOMINANT",
                    }
                },
                "query_page_device_splits": {
                    "/tools/section-179-calculator::section 179 calculator": {
                        "DESKTOP": {"clicks": 0, "impressions": 20, "ctr": 0.0, "position": 85.15},
                        "MOBILE": {"clicks": 0, "impressions": 5, "ctr": 0.0, "position": 76.4},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    run_gsc_affiliate_placement_feedback_pass(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        dry_run=False,
    )
    persisted = load_persisted_gsc_placement_metrics_by_slug(agy_dir, "profithelm")
    assert "section-179-calculator" in persisted
    assert persisted["section-179-calculator"]["impressions"] >= 70
    assert persisted["section-179-calculator"]["mobile_impressions"] == 30
    assert persisted["section-179-calculator"]["desktop_impressions"] == 108
    assert persisted["section-179-calculator"]["query"] == "section 179 calculator"


# ---------------------------------------------------------------------------
# 1. trend_history.db Indexes + PRAGMAs + Unfreeze gsc_daily_metrics
# ---------------------------------------------------------------------------


def test_trend_db_pragmas_covering_indexes_explain_plan_and_zero_row_deletion(tmp_path: Path) -> None:
    """
    Verifies:
    - PRAGMAs set on both read-write and read-only connections
    - All 6 new composite/covering indexes created idempotently (even on pre-existing DBs)
      with ZERO row deletion
    - EXPLAIN QUERY PLAN for get_past_velocities uses COVERING INDEX with 0 TEMP B-TREEs
    - get_past_velocities returns top 2 distinct past cycles ordered by observed_at DESC
    """
    from pseofactory.trends.db import TrendHistoryDB
    from pseofactory.trends.models import CrawlCycleRecord, RawObservationRecord

    db_path = tmp_path / "trend_history.db"
    with TrendHistoryDB(db_path) as db:
        conn = db.get_connection()
        assert int(conn.execute("PRAGMA cache_size;").fetchone()[0]) == -65536
        assert int(conn.execute("PRAGMA mmap_size;").fetchone()[0]) == 268435456
        assert int(conn.execute("PRAGMA temp_store;").fetchone()[0]) == 2  # MEMORY
        assert int(conn.execute("PRAGMA wal_autocheckpoint;").fetchone()[0]) == 1000

        existing_indexes = {
            str(r[0])
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
        expected_indexes = {
            "idx_observations_norm_query_obs_cov",
            "idx_jev_eval_prop_action_eval",
            "idx_jev_eval_evaluated_at",
            "idx_crawl_cycles_status_executed",
            "idx_property_assignments_cycle",
            "idx_treg_snapshots_cycle",
        }
        assert expected_indexes.issubset(existing_indexes)

        for cid in ("c1", "c2", "c3", "c4"):
            db.start_cycle(cycle_id=cid, seeds=["q"], sources=["google_trends"])
            db.complete_cycle(cycle_id=cid, total_raw_observations=1, unique_queries_count=1, status="COMPLETED")

        db.record_observations(
            [
                RawObservationRecord("o1", "c1", "google_trends", "q", "q", 1, 1.5, 0.1, 1.0, "2026-11-18T01:00:00+00:00"),
                RawObservationRecord("o2a", "c2", "google_trends", "q", "q", 1, 2.5, 0.2, 1.2, "2026-11-19T01:00:00+00:00"),
                RawObservationRecord("o2b", "c2", "reddit", "q", "q", 2, 2.9, 0.3, 1.3, "2026-11-19T02:00:00+00:00"),
                RawObservationRecord("o3", "c3", "google_trends", "q", "q", 1, 4.2, 0.4, 1.8, "2026-11-20T01:00:00+00:00"),
                RawObservationRecord("o4", "c4", "google_trends", "q", "q", 1, 9.9, 0.9, 2.5, "2026-11-21T01:00:00+00:00"),
            ]
        )

        # Verify EXPLAIN QUERY PLAN uses COVERING INDEX with 0 TEMP B-TREEs
        plan_rows = conn.execute(
            "EXPLAIN QUERY PLAN SELECT cycle_id, observed_velocity FROM raw_crawl_observations "
            "WHERE normalized_query = ? ORDER BY observed_at DESC;",
            ("q",),
        ).fetchall()
        plan_text = " ".join(str(r["detail"]) for r in plan_rows).upper()
        assert "USING COVERING INDEX IDX_OBSERVATIONS_NORM_QUERY_OBS_COV" in plan_text
        assert "TEMP B-TREE" not in plan_text

        # Verify top 2 distinct past cycles excluding current_cycle_id='c4'
        past_v = db.get_past_velocities("q", current_cycle_id="c4")
        assert past_v == [4.2, 2.9]

        # Simulate legacy DB missing the new indexes and verify auto-upgrade preserves ALL rows
        for idx_name in expected_indexes:
            conn.execute(f"DROP INDEX IF EXISTS {idx_name};")
        before_count = conn.execute("SELECT COUNT(*) FROM raw_crawl_observations;").fetchone()[0]
        assert before_count == 5

    with TrendHistoryDB(db_path) as db_upgraded:
        conn2 = db_upgraded.get_connection()
        after_indexes = {
            str(r[0])
            for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
        assert expected_indexes.issubset(after_indexes)
        after_count = conn2.execute("SELECT COUNT(*) FROM raw_crawl_observations;").fetchone()[0]
        assert after_count == 5

    # Read-only connection also gets performance PRAGMAs
    with TrendHistoryDB(db_path, read_only=True) as ro_db:
        ro_conn = ro_db.get_connection()
        assert int(ro_conn.execute("PRAGMA cache_size;").fetchone()[0]) == -65536
        assert int(ro_conn.execute("PRAGMA mmap_size;").fetchone()[0]) == 268435456
        assert int(ro_conn.execute("PRAGMA temp_store;").fetchone()[0]) == 2


def test_gsc_daily_metrics_unfrozen_and_multidim_rollup_includes_lienbond(tmp_path: Path) -> None:
    """
    Verifies:
    1. harvest_and_sync_gsc_multidimensional_telemetry(..., persist=True) rolls up
       page_daily_records into gsc_daily_metrics for all tenants including lienbond.
    2. harvest_and_sync_gsc_daily_timeline(..., db_path=tmp_db) persists even when
       repo_root is a live tenant path because _resolve_safe_persist_flag checks target_db_path only.
    3. DailyIndexingInspector.audit_search_traffic passes persist=(not dry_run) guarded by
       _is_live_repo_mutation_blocked instead of hardcoded False.
    """
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.seo_growth_loops import (
        harvest_and_sync_gsc_daily_timeline,
        harvest_and_sync_gsc_multidimensional_telemetry,
    )
    from pseofactory.trends.db import TrendHistoryDB

    db_path = tmp_path / "trend_history.db"
    repo_root = tmp_path / "lienbond"
    (repo_root / ".agy").mkdir(parents=True, exist_ok=True)

    fixture_payload = {
        "page_daily": [
            {"date": "2026-11-19", "page": "https://lienbond.com/tools/preliminary-notice-deadline-calculator/", "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 12.0},
            {"date": "2026-11-19", "page": "https://lienbond.com/tools/mechanics-lien-deadline-calculator/", "clicks": 2, "impressions": 60, "ctr": 0.0333, "position": 18.0},
            {"date": "2026-11-20", "page": "https://lienbond.com/tools/preliminary-notice-deadline-calculator/", "clicks": 5, "impressions": 80, "ctr": 0.0625, "position": 10.0},
        ]
    }
    harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="lienbond",
        repo_root=repo_root,
        db_path=db_path,
        live_gsc=False,
        persist=True,
        fixture_payload=fixture_payload,
    )
    with TrendHistoryDB(db_path, read_only=True) as tdb:
        daily = tdb.get_gsc_daily_metrics("lienbond", days=30)
    by_date = {r.date: r for r in daily}
    assert "2026-11-19" in by_date and by_date["2026-11-19"].impressions == 100 and by_date["2026-11-19"].clicks == 5
    assert "2026-11-20" in by_date and by_date["2026-11-20"].impressions == 80 and by_date["2026-11-20"].clicks == 5

    # Verify _resolve_safe_persist_flag checks target_db_path only (not tenant root)
    db_path2 = tmp_path / "trend_history_2.db"
    harvest_and_sync_gsc_daily_timeline(
        property_id="profithelm",
        repo_root="/home/ubuntuadmin/projects/profithelm-platform",
        db_path=db_path2,
        persist=True,
        fixture_records=[
            {"property_id": "profithelm", "date": "2026-11-20", "clicks": 4, "impressions": 120, "ctr": 0.0333, "position": 14.5}
        ],
    )
    with TrendHistoryDB(db_path2, read_only=True) as tdb2:
        ph_daily = tdb2.get_gsc_daily_metrics("profithelm", days=30)
    assert len(ph_daily) == 1 and ph_daily[0].impressions == 120

    # Verify DailyIndexingInspector.audit_search_traffic forwards persist=(not dry_run) when not blocked
    inspector = DailyIndexingInspector(tenant_id="lienbond", base_dir=repo_root)
    captured = {}

    def _fake_harvest(**kwargs):
        captured.update(kwargs)
        return []

    env_without_pytest = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    with (
        patch.dict(os.environ, env_without_pytest, clear=True),
        patch("pseofactory.maintenance._is_live_repo_mutation_blocked", return_value=False),
        patch("pseofactory.seo_growth_loops.harvest_and_sync_gsc_daily_timeline", side_effect=_fake_harvest),
    ):
        inspector.audit_search_traffic(dry_run=False)
        assert captured.get("persist") is True
        captured.clear()
        inspector.audit_search_traffic(dry_run=True)
        assert captured.get("persist") is False


# ---------------------------------------------------------------------------
# 2. Indexation Unblocking for gainhelm & lienbond
# ---------------------------------------------------------------------------


def test_fair_gsc_quota_partitioning_tool_priority_rollover_indexnow_and_project_id(tmp_path: Path) -> None:
    """
    Verifies all 5 indexation unblocking fixes:
    1. Fair per-tenant GSC quota partitioning (profithelm/prexvo/gainhelm cannot starve lienbond)
    2. Tool-over-governance priority push (/tools/<slug>/ ahead of /methodology/, /disclaimers/, etc.)
    3. Rollover queue preservation when urls_pushed == 0 or partial ACCEPTED batch
    4. Unified fast-index IndexNow key from deployed dist/<key>.txt
    5. Per-tenant indexmysite_project_id (profithelm-platform ONLY for profithelm)
    """
    from pseofactory.indexer import DEFAULT_INDEXMYSITE_PROJECT_ID, PushIndexer
    from pseofactory.indexing_inspector import DailyIndexingInspector

    shared_gov = tmp_path / "gsc_quota_governor.json"

    def _make_indexer(tid: str, dom: str) -> PushIndexer:
        b = tmp_path / tid
        d = b / "dist"
        d.mkdir(parents=True, exist_ok=True)
        (b / ".agy").mkdir(parents=True, exist_ok=True)
        (d / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        idx = PushIndexer(domain=dom, canonical_base=f"https://{dom}", base_dir=b, dist_dir=d, tenant_id=tid)
        idx.quota_governor_path = shared_gov
        idx.repo_root = b
        return idx

    idx_ph = _make_indexer("profithelm", "profithelm.com")
    idx_px = _make_indexer("prexvo", "prexvo.com")
    idx_gh = _make_indexer("gainhelm", "gainhelm.com")
    idx_lb = _make_indexer("lienbond", "lienbond.com")

    # 5. Per-tenant indexmysite_project_id
    assert idx_ph.indexmysite_project_id == DEFAULT_INDEXMYSITE_PROJECT_ID
    assert idx_px.indexmysite_project_id == "prexvo"
    assert idx_gh.indexmysite_project_id == "gainhelm"
    assert idx_lb.indexmysite_project_id == "lienbond"

    # 1. Fair per-tenant GSC quota partitioning: earlier tenants CANNOT starve lienbond
    ph_max = idx_ph.check_and_consume_gsc_quota(units=0, bucket="indexing")
    assert ph_max["remaining"] == 80  # 40 floor + 40 spillover (120 reserved for px/gh/lb)
    assert idx_ph.check_and_consume_gsc_quota(units=80, bucket="indexing")["allowed"] is True
    assert idx_ph.check_and_consume_gsc_quota(units=1, bucket="indexing")["allowed"] is False

    assert idx_px.check_and_consume_gsc_quota(units=40, bucket="indexing")["allowed"] is True
    assert idx_gh.check_and_consume_gsc_quota(units=40, bucket="indexing")["allowed"] is True

    # lienbond STILL has its guaranteed 40-unit floor!
    lb_avail = idx_lb.check_and_consume_gsc_quota(units=0, bucket="indexing")
    assert lb_avail["remaining"] == 40
    assert idx_lb.check_and_consume_gsc_quota(units=40, bucket="indexing")["allowed"] is True
    gov_json = json.loads(shared_gov.read_text(encoding="utf-8"))
    assert gov_json["indexing_by_tenant"] == {"profithelm": 80, "prexvo": 40, "gainhelm": 40, "lienbond": 40}

    # 1b. Quota floor degrades gracefully to 0 at >200 active tenants (no starvation at >=201)
    from pseofactory.indexer import _gsc_quota_day_pt
    scale_gov = tmp_path / "gsc_quota_governor_scale.json"
    scale_gov.write_text(
        json.dumps(
            {
                "date": _gsc_quota_day_pt(),
                "inspection_used": 0,
                "indexing_used": 10,
                "indexing_by_tenant": {f"tenant_{i}": 0 for i in range(205)},
            }
        ),
        encoding="utf-8",
    )
    idx_lb.quota_governor_path = scale_gov
    scale_chk = idx_lb.check_and_consume_gsc_quota(units=1, bucket="indexing")
    assert scale_chk["tenant_floor"] == 0
    assert scale_chk["allowed"] is True
    idx_lb.quota_governor_path = shared_gov

    # 2. Tool-over-governance priority push (even when governance pages are also unindexed)
    (idx_gh.base_dir / ".agy" / "gsc_lifecycle_telemetry.json").write_text(
        json.dumps(
            {
                "url_states": {
                    "https://gainhelm.com/about/": {"verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"},
                    "https://gainhelm.com/methodology/": {"verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"},
                    "https://gainhelm.com/disclaimers/": {"verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"},
                    "https://gainhelm.com/tools/soc-2-audit-cost-calculator/": {"verdict": "NEUTRAL", "coverageState": "Discovered - currently not indexed"},
                }
            }
        ),
        encoding="utf-8",
    )
    candidates = [
        "https://gainhelm.com/about/",
        "https://gainhelm.com/disclaimers/",
        "https://gainhelm.com/methodology/",
        "https://gainhelm.com/privacy/",
        "https://gainhelm.com/terms/",
        "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
        "https://gainhelm.com/tools/hipaa-compliance-cost-calculator/",
    ]
    ranked = idx_gh.prioritize_urls_for_indexing_allocation(candidates)
    tool_positions = [ranked.index(u) for u in ranked if "/tools/" in u]
    gov_positions = [ranked.index(u) for u in ranked if any(g in u for g in ("/about/", "/disclaimers/", "/methodology/", "/privacy/", "/terms/"))]
    assert max(tool_positions) < min(gov_positions), f"Governance pages ranked ahead of tools: {ranked}"

    # 4. Unified IndexNow key for fast-index from dist/<key>.txt (excluding ProfitHelm key on LienBond!)
    ph_v2_key = "dc89e030b25b96ac58c9dbff024da881"
    lb_key = "eb621d3e7fc5a6d8ff995c5caf86951f"
    (idx_lb.dist_dir / f"{ph_v2_key}.txt").write_text(ph_v2_key, encoding="utf-8")
    (idx_lb.dist_dir / f"{lb_key}.txt").write_text(lb_key, encoding="utf-8")
    # Even if self.indexnow_key was initialized to ProfitHelm's key, fast-path must reject it
    idx_lb.indexnow_key = ph_v2_key
    assert idx_lb._resolve_deployed_indexnow_key() == lb_key
    tool_html = '<!DOCTYPE html><html><head><title>Lien Calc</title><link rel="canonical" href="https://lienbond.com/tools/calc/"></head><body><h1>Calc</h1></body></html>'
    (idx_lb.dist_dir / "tools" / "calc").mkdir(parents=True, exist_ok=True)
    (idx_lb.dist_dir / "tools" / "calc" / "index.html").write_text(tool_html, encoding="utf-8")
    fake_fi = tmp_path / "fast-index"
    fake_fi.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    captured_env = {}

    def _fake_subproc(cmd, **kwargs):
        captured_env.update(kwargs.get("env") or {})
        m = MagicMock()
        m.stdout = json.dumps({"ok": True, "actions": [{"protocol": "indexnow", "ok": True}]})
        m.returncode = 0
        return m

    with (
        patch("pseofactory.indexer.shutil.which", return_value=str(fake_fi)),
        patch("subprocess.run", side_effect=_fake_subproc),
    ):
        fi_res = idx_lb.submit_fast_index(urls=["https://lienbond.com/tools/calc/"], dry_run=True)
    assert fi_res["indexnow_key"] == lb_key
    assert captured_env.get("INDEXNOW_KEY") == lb_key
    assert captured_env.get("SEO_INDEXNOW_KEY") == lb_key

    # 3. Rollover queue preservation when urls_pushed == 0 and partial ACCEPTED drain
    # using the REAL dispatch_automated_indexing() nested notifications schema!
    u1 = "https://lienbond.com/tools/calc-1/"
    u2 = "https://lienbond.com/tools/calc-2/"
    rollover_q = idx_lb.base_dir / ".agy" / "gsc_rollover_queue.json"
    rollover_q.write_text(json.dumps([u1, u2]), encoding="utf-8")

    inspector = DailyIndexingInspector(tenant_id="lienbond", base_dir=idx_lb.base_dir)

    class _FakeLoopZeroPush:
        def __init__(self, indexer):
            self.indexer = indexer

        def run_feedback_cycle(self, **kwargs):
            return {"status": "SUCCESS", "push_summary": {"urls_pushed": 0, "push_results": {}}}

    with (
        patch.object(inspector, "audit_child_sitemaps_and_section_coverage", return_value={"status": "PASS", "unindexed_urls": []}),
        patch.object(inspector, "audit_airlock_quarantine", return_value={"status": "PASS", "quarantined_count": 0}),
        patch.object(inspector, "audit_velocity_stagnation", return_value={"status": "PASS"}),
        patch.object(inspector, "audit_search_traffic", return_value={"status": "PASS"}),
        patch("pseofactory.indexing.feedback_loop.IndexingFeedbackLoop", return_value=_FakeLoopZeroPush(idx_lb)),
    ):
        inspector.run_inspection(dry_run=False, auto_remediate=True, vertex_diagnose=False)
    # Must NOT have wiped the rollover queue when urls_pushed == 0
    assert json.loads(rollover_q.read_text(encoding="utf-8")) == [u1, u2]

    class _FakeLoopRealNotificationSchema:
        def __init__(self, indexer):
            self.indexer = indexer

        def run_feedback_cycle(self, **kwargs):
            return {
                "status": "SUCCESS",
                "push_summary": {
                    "urls_pushed": 1,
                    "push_results": {
                        "google_indexing_api": {
                            "status": "PARTIAL",
                            "results": [
                                {
                                    "engine": "google_indexing_api",
                                    "status": "DISPATCHED",
                                    "notifications": [
                                        {"url": u1, "status": "ACCEPTED"},
                                        {"url": u2, "status": "QUOTA_EXCEEDED"},
                                    ],
                                }
                            ],
                        }
                    },
                },
            }

    with (
        patch.object(inspector, "audit_child_sitemaps_and_section_coverage", return_value={"status": "PASS", "unindexed_urls": []}),
        patch.object(inspector, "audit_airlock_quarantine", return_value={"status": "PASS", "quarantined_count": 0}),
        patch.object(inspector, "audit_velocity_stagnation", return_value={"status": "PASS"}),
        patch.object(inspector, "audit_search_traffic", return_value={"status": "PASS"}),
        patch("pseofactory.indexing.feedback_loop.IndexingFeedbackLoop", return_value=_FakeLoopRealNotificationSchema(idx_lb)),
    ):
        rep_partial = inspector.run_inspection(dry_run=False, auto_remediate=True, vertex_diagnose=False)
    # u1 accepted & drained; u2 unpushed spillover preserved!
    assert json.loads(rollover_q.read_text(encoding="utf-8")) == [u2]
    assert rep_partial["gsc_rollover"]["queue_size"] == 1


# ---------------------------------------------------------------------------
# 3. Autonomous BUILD_PAGE Stranded-Slug Recovery + Rollback Hook
# ---------------------------------------------------------------------------


def test_stranded_built_slug_reconciliation_bounded_retry_and_gitops_rollback_hook(tmp_path: Path) -> None:
    """
    Verifies:
    1. Cross-day BUILT entries missing dist/tools/<slug>/index.html re-open to PENDING
       across all dates in daily_page_build_ledger.json.
    2. Cooldown (24h) and max_rollback_retries=3 prevent infinite build/rollback loops
       (transitioning to ROLLBACK_EXHAUSTED at retry limit).
    3. GitOpsCoordinator._mark_rolled_back_void_candidates marks reverted daily-built slugs
       as ROLLED_BACK with rollback_reason and failed_sha.
    """
    from pseofactory.gitops import GitOpsCoordinator
    from pseofactory.maintenance import ConfigurablePropertyAdapter, TenantRegistry
    from pseofactory.pipeline import execute_autonomous_daily_trend_page_build

    dist_dir = tmp_path / "gainhelm" / "dist"
    (dist_dir / "tools").mkdir(parents=True, exist_ok=True)

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="gainhelm",
            brand_name="GainHelm",
            domain="gainhelm.com",
            canonical_base="https://gainhelm.com",
            dist_dir=dist_dir,
        )
    )

    vc_path = tmp_path / ".agy" / "void_candidates.jsonl"
    ledger_path = tmp_path / ".agy" / "daily_page_build_ledger.json"
    vc_path.parent.mkdir(parents=True, exist_ok=True)

    yesterday_iso = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    recent_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    entries = [
        # 1. Cross-day BUILT slug missing on disk -> should re-open to PENDING
        {
            "property_id": "gainhelm",
            "slug": "stranded-cross-day-calc",
            "query": "stranded cross day calc",
            "action": "BUILD_PAGE",
            "status": "BUILT",
            "built_at": yesterday_iso,
        },
        # 2. Recently rolled-back slug within 24h cooldown -> must stay ROLLED_BACK
        {
            "property_id": "gainhelm",
            "slug": "recent-cooldown-calc",
            "query": "recent cooldown calc",
            "action": "BUILD_PAGE",
            "status": "ROLLED_BACK",
            "rolled_back_at": recent_iso,
            "rollback_retry_count": 1,
        },
        # 3. Exhausted retries (3/3) -> must transition to ROLLBACK_EXHAUSTED
        {
            "property_id": "gainhelm",
            "slug": "exhausted-broken-calc",
            "query": "exhausted broken calc",
            "action": "BUILD_PAGE",
            "status": "BUILT",
            "rollback_retry_count": 3,
        },
    ]
    vc_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    ledger_path.write_text(
        json.dumps(
            {
                "days": {
                    "2026-11-19": {
                        "gainhelm": [
                            {
                                "slug": "stranded-cross-day-calc",
                                "output_file": str(dist_dir / "tools" / "stranded-cross-day-calc" / "index.html"),
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    res = execute_autonomous_daily_trend_page_build(
        property_ids=["gainhelm"],
        void_candidates_path=vc_path,
        ledger_path=ledger_path,
        date_key="2026-11-21",
        registry=reg,
        dry_run=True,
        max_rollback_retries=3,
        cooldown_hours=24.0,
    )
    assert res["reconciled_stale_ledger_count"] == 1
    assert res["reconciled_stranded_built_count"] == 1
    assert res["rollback_exhausted_count"] == 1

    # Verify GitOps rollback hook marks newly added dist/tools/<slug>/index.html as ROLLED_BACK
    repo = tmp_path / "git_tenant"
    repo.mkdir()
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, env=git_env, capture_output=True)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=git_env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, env=git_env, capture_output=True)
    known_good = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    new_tool = repo / "dist" / "tools" / "auto-built-slug" / "index.html"
    new_tool.parent.mkdir(parents=True, exist_ok=True)
    new_tool.write_text("<html><body>tool</body></html>", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=git_env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add tool"], check=True, env=git_env, capture_output=True)
    failed_sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    vc_rb = tmp_path / "rb_void_candidates.jsonl"
    vc_rb.write_text(
        json.dumps({"property_id": "gainhelm", "slug": "auto-built-slug", "status": "BUILT"}) + "\n",
        encoding="utf-8",
    )
    coord = GitOpsCoordinator(repo_path=repo, dry_run=True)
    marked = coord._mark_rolled_back_void_candidates(
        rp=repo,
        failed_sha=failed_sha,
        known_good_sha=known_good,
        property_id="gainhelm",
        reason="CI failed on page audit",
        env=git_env,
        void_candidates_path=vc_rb,
    )
    assert marked == ["auto-built-slug"]
    updated_rec = json.loads(vc_rb.read_text(encoding="utf-8").strip())
    assert updated_rec["status"] == "ROLLED_BACK"
    assert updated_rec["failed_sha"] == failed_sha
    assert "CI failed on page audit" in updated_rec["rollback_reason"]

    # 4. End-to-end pipeline rollback: void_candidates retains ROLLED_BACK, daily ledger pops build,
    #    and dispatch_push_indexing does NOT push-index the rolled-back URL!
    from pseofactory.gitops import GitOpsResult

    rb_dist = tmp_path / "gainhelm_rb" / "dist"
    (rb_dist / "tools").mkdir(parents=True, exist_ok=True)
    reg_rb = TenantRegistry()
    reg_rb.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="gainhelm",
            brand_name="GainHelm",
            domain="gainhelm.com",
            canonical_base="https://gainhelm.com",
            dist_dir=rb_dist,
            repo_path=rb_dist.parent,
        )
    )
    vc_rb2 = tmp_path / ".agy" / "void_candidates_rb2.jsonl"
    ledger_rb2 = tmp_path / ".agy" / "daily_page_build_ledger_rb2.json"
    vc_rb2.write_text(
        json.dumps(
            {
                "property_id": "gainhelm",
                "tenant": "gainhelm",
                "slug": "dora-ict-third-party-risk-compliance-cost-calculator",
                "query": "dora ict third party risk compliance cost calculator",
                "title": "DORA ICT Third-Party Risk Compliance Cost Model",
                "action": "BUILD_PAGE",
                "status": "PENDING",
                "composite_profit_yield": 92.4,
                "statutory_authority": "EU Digital Operational Resilience Act (Regulation (EU) 2022/2554 Articles 17, 26 & 28)",
                "economic_dataset": "ESAs Joint DORA Oversight Cost Series & BLS OEWS SOC 15-1212 Wage Series",
                "model_name": "GainHelm-EU-DORA-ICT-ThirdParty-Risk-Cost-Model-2026",
                "formula": "round(tlpt_red_team_fee + (critical_ict_vendors * fee_per_ict_vendor) + register_of_information_cost + (remediation_hours * engineering_hourly_rate), 2)",
                "inputs": {
                    "tlpt_red_team_fee": 42000.0,
                    "critical_ict_vendors": 12.0,
                    "fee_per_ict_vendor": 2800.0,
                    "register_of_information_cost": 16500.0,
                    "remediation_hours": 160.0,
                    "engineering_hourly_rate": 125.0,
                },
                "published_output": 112100.0,
                "sample_calculation": (
                    "Financial entity scoping EU DORA compliance across 12 critical ICT third-party providers: "
                    "Article 26 threat-led penetration testing ($42,000.00) + 12 ICT vendor exit-strategy and "
                    "contractual audits at $2,800 ($33,600.00) + Article 28 Register of Information automation "
                    "($16,500.00) + 160 remediation hours at $125/hr ($20,000.00) = $112,100.00 total first-year DORA compliance cost."
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    fake_rb_res = GitOpsResult(
        status="ROLLED_BACK",
        property_id="gainhelm",
        head_sha="deadbeef1234",
        error="CI failed on page audit",
        details={"rollback": {"status": "ROLLED_BACK", "failed_sha": "deadbeef1234", "reason": "CI failed on page audit"}},
    )
    pushed_urls_seen: list = []

    def _capture_push(self, urls=None, **kwargs):
        pushed_urls_seen.extend(urls or [])
        return {"status": "SUCCESS"}

    env_no_pytest = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    with (
        patch.dict(os.environ, env_no_pytest, clear=True),
        patch("pseofactory.gitops.GitOpsCoordinator.dispatch_to_shipper", return_value=fake_rb_res),
        patch("pseofactory.indexer.PushIndexer.dispatch_automated_indexing", new=_capture_push),
        patch("pseofactory.maintenance.RetroReflectionEngine.retrofit_estate"),
        patch("pseofactory.drift.write_substrate_lock"),
    ):
        rb_pipe_res = execute_autonomous_daily_trend_page_build(
            property_ids=["gainhelm"],
            void_candidates_path=vc_rb2,
            ledger_path=ledger_rb2,
            date_key="2026-11-21",
            registry=reg_rb,
            dry_run=False,
            enable_gitops=True,
            dispatch_push_indexing=True,
        )
    assert rb_pipe_res["built_count"] == 0
    persisted_vc = json.loads(vc_rb2.read_text(encoding="utf-8").strip())
    assert persisted_vc["status"] == "ROLLED_BACK"
    assert persisted_vc["failed_sha"] == "deadbeef1234"
    assert "CI failed on page audit" in persisted_vc["rollback_reason"]
    persisted_ledger = json.loads(ledger_rb2.read_text(encoding="utf-8"))
    assert persisted_ledger.get("days", {}).get("2026-11-21", {}).get("gainhelm", []) == []
    assert pushed_urls_seen == []


# ---------------------------------------------------------------------------
# 4. Safe Closed-Loop Auto-Remediation Shipping
# ---------------------------------------------------------------------------


def test_feedback_loop_dispatch_to_shipper_daily_cap_broadcast_and_honest_recompile(tmp_path: Path) -> None:
    """
    Verifies:
    1. Real GitOpsCoordinator routes through dispatch_to_shipper (zero AttributeError on
       nonexistent commit_and_push_atomic).
    2. Repeat run with unchanged dist_fingerprint returns SKIPPED_UNCHANGED_DIST;
       repeat run with changed dist within 24h returns SKIPPED_DAILY_CAP_REACHED.
    3. broadcast_ledger.json overwrites stale cross-domain URL with self.domain URL.
    4. Never reports total_recompiled > 0 when HTML was NOT actually compiled.
    """
    from pseofactory.gitops import GitOpsCoordinator, GitOpsResult
    from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop

    base_dir = tmp_path / "gainhelm"
    dist_dir = base_dir / "dist"
    (dist_dir / "tools" / "soc-2-calc").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "soc-2-calc" / "index.html").write_text("<html><body>v1</body></html>", encoding="utf-8")
    (base_dir / ".agy").mkdir(parents=True, exist_ok=True)

    # 3. Cross-domain broadcast_ledger.json repair
    b_ledger = base_dir / ".agy" / "broadcast_ledger.json"
    b_ledger.write_text(
        json.dumps([{"slug": "soc-2-calc", "url": "https://profithelm.com/tools/soc-2-calc/", "channels": []}]),
        encoding="utf-8",
    )

    real_coord = GitOpsCoordinator(repo_path=base_dir, dry_run=False)
    mock_indexer = MagicMock()
    mock_indexer.load_gsc_rollover_queue.return_value = []
    mock_preflight = MagicMock()
    mock_preflight.inspect_dist.return_value = MagicMock(
        total_inspected=1,
        passed_count=1,
        blocked_count=0,
        push_eligible_urls=["https://gainhelm.com/tools/soc-2-calc/"],
        sitemap_eligible_urls=["https://gainhelm.com/tools/soc-2-calc/"],
        blocked_urls={},
    )

    loop = IndexingFeedbackLoop(
        property_id="gainhelm",
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        base_dir=base_dir,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        preflight_engine=mock_preflight,
        gitops_coordinator=real_coord,
    )

    loop._sync_external_distribution_for_candidate(
        slug="soc-2-calc",
        target_url="https://gainhelm.com/tools/soc-2-calc/",
        overlay_spec={"title_rewrite": "SOC 2 Calc", "quick_answer": "Fast answer."},
    )
    b_after = json.loads(b_ledger.read_text(encoding="utf-8"))
    assert "gainhelm.com" in b_after[0]["url"]
    assert "profithelm.com" not in b_after[0]["url"]

    # 1. Real GitOpsCoordinator calls dispatch_to_shipper (never commit_and_push_atomic)
    fake_git_res = GitOpsResult(
        status="SUCCESS",
        property_id="gainhelm",
        head_sha="bbb",
        branch="main",
    )
    repair_stub = {
        "recompiled_assets_count": 1,
        "html_files_repaired": 1,
        "dead_routes_quarantined": 0,
        "sitemaps_pruned": 0,
        "overlays_written": ["soc-2-calc"],
    }
    with (
        patch.object(real_coord, "dispatch_to_shipper", return_value=fake_git_res) as ship_mock,
        patch.object(loop, "execute_engine_repairs", return_value=repair_stub),
        patch.object(loop, "dispatch_multi_engine_push", return_value={"status": "SUCCESS", "urls_pushed": 1}),
    ):
        r1 = loop.run_feedback_cycle(
            unindexed_records=[{"url": "https://gainhelm.com/tools/soc-2-calc/", "coverageState": "Crawled - currently not indexed"}],
            dry_run=False,
            enable_gitops=True,
        )
        assert ship_mock.call_count == 1
        assert r1["gitops_summary"]["status"] == "SUCCESS"

        # 2a. Unchanged dist_fingerprint -> SKIPPED_UNCHANGED_DIST
        r2 = loop.run_feedback_cycle(
            unindexed_records=[{"url": "https://gainhelm.com/tools/soc-2-calc/", "coverageState": "Crawled - currently not indexed"}],
            dry_run=False,
            enable_gitops=True,
        )
        assert ship_mock.call_count == 1
        assert r2["gitops_summary"]["status"] == "SKIPPED_UNCHANGED_DIST"

        # 2b. Changed dist within 24h -> SKIPPED_DAILY_CAP_REACHED
        (dist_dir / "tools" / "soc-2-calc" / "index.html").write_text("<html><body>v2</body></html>", encoding="utf-8")
        r3 = loop.run_feedback_cycle(
            unindexed_records=[{"url": "https://gainhelm.com/tools/soc-2-calc/", "coverageState": "Crawled - currently not indexed"}],
            dry_run=False,
            enable_gitops=True,
        )
        assert ship_mock.call_count == 1
        assert r3["gitops_summary"]["status"] == "SKIPPED_DAILY_CAP_REACHED"

    # 4. Honest total_recompiled == 0 when skip_recompile=True and 0 HTML files repaired
    loop_no_gitops = IndexingFeedbackLoop(
        property_id="gainhelm",
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        base_dir=base_dir,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        preflight_engine=mock_preflight,
        gitops_coordinator=None,
    )
    with patch.object(loop_no_gitops, "_is_prod_tenant_repo", return_value=True):
        rep_staged = loop_no_gitops.execute_engine_repairs(
            diagnoses=[],
            prioritized_candidates=[
                {
                    "slug": "soc-2-calc",
                    "target_url": "https://gainhelm.com/tools/soc-2-calc/",
                    "query": "soc 2 cost calculator",
                    "anomaly_type": "STRIKING_DISTANCE_QUERY",
                    "impressions": 50,
                    "position": 12.0,
                }
            ],
            dry_run=False,
            skip_recompile=False,
        )
    assert rep_staged["html_files_repaired"] == 0
    assert rep_staged["reflection"]["total_recompiled"] == 0
    assert rep_staged["recompiled_assets_count"] == 0


# ---------------------------------------------------------------------------
# 5. Supervisor Containment & Resilience
# ---------------------------------------------------------------------------


def test_supervisor_containment_manifest_sigterm_breaker_and_tmp_dlq_guard(tmp_path: Path) -> None:
    """
    Verifies:
    1. WorkspacePropertyScanner defaults require_manifest=True unconditionally so unrelated
       projects (e.g. extreme-roku-cinema) are never adopted.
    2. SIGTERM inside AutonomousLifecycleSupervisor.run_cycle raises SupervisorTimeoutError
       and records supervisor_failure_streak.json cleanly.
    3. RollbackCircuitBreaker stops re-trying (tenant_id, engine_hash) after 1 ROLLBACK_CI_FAILED
       until engine_hash changes.
    4. RefactorCascadeEngine refuses to persist /tmp/ asset paths into a live DLQ and
       auto-prunes existing /tmp/ entries on load/save.
    """
    from pseofactory.maintenance import (
        AssetDriftRecord,
        ConfigurablePropertyAdapter,
        DriftReason,
        MaintenanceResult,
        RefactorCascadeEngine,
        TenantRegistry,
        WorkspacePropertyScanner,
    )
    from pseofactory.supervisor import (
        AutonomousLifecycleSupervisor,
        RollbackCircuitBreaker,
        SupervisorTimeoutError,
    )

    # 1. WorkspacePropertyScanner default require_manifest=True blocks unrelated projects
    ws = tmp_path / "ws"
    roku = ws / "extreme-roku-cinema"
    (roku / "dist").mkdir(parents=True, exist_ok=True)
    (roku / "dist" / "sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset><url><loc>https://extremeroku.com/</loc></url></urlset>',
        encoding="utf-8",
    )
    (roku / "pyproject.toml").write_text('[project]\nname = "extreme-roku-cinema"\n', encoding="utf-8")

    valid_tenant = ws / "valid-tenant"
    (valid_tenant / "dist").mkdir(parents=True, exist_ok=True)
    (valid_tenant / ".pseofactory.json").write_text(
        json.dumps({"property_id": "valid_tenant", "domain": "valid.com", "dist_dir": "dist"}),
        encoding="utf-8",
    )

    scanner = WorkspacePropertyScanner(workspace_root=ws)
    assert scanner.require_manifest is True
    found_ids = {a.property_id for a in scanner.discover_properties()}
    assert found_ids == {"valid_tenant"}
    assert "extreme-roku-cinema" not in found_ids

    # 2. SIGTERM cleanly records supervisor_failure_streak.json via SupervisorTimeoutError
    reg = TenantRegistry()
    t_dist = ws / "valid-tenant" / "dist"
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="valid_tenant",
            brand_name="Valid",
            domain="valid.com",
            canonical_base="https://valid.com",
            dist_dir=t_dist,
        )
    )
    mock_coord = MagicMock()
    mock_coord.registry = reg

    def _raise_sigterm(**kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        return {}

    mock_coord.run_fleet.side_effect = _raise_sigterm
    sup = AutonomousLifecycleSupervisor(
        workspace_root=ws,
        registry=reg,
        coordinator=mock_coord,
        state_file=ws / ".agy" / "engine_hash.json",
        ledger_file=ws / ".agy" / "asset_ledger.json",
        heartbeat_path=ws / ".agy" / "supervisor_heartbeat.json",
    )
    sig_res = sup.run_cycle(force=True, dry_run=False, property_ids=["valid_tenant"])
    assert sig_res["sigterm_interrupted"] is True
    assert sig_res["status"] in ("TIMEOUT", "DEGRADED")
    streak_data = json.loads((ws / ".agy" / "supervisor_failure_streak.json").read_text(encoding="utf-8"))
    assert streak_data["consecutive_failures"] >= 1
    assert "valid_tenant" in streak_data["tenants"]

    # 3. RollbackCircuitBreaker stops re-trying (tenant_id, engine_hash) after 1 ROLLBACK_CI_FAILED
    mock_coord2 = MagicMock()
    mock_coord2.registry = reg
    mock_coord2.run_fleet.return_value = {
        "valid_tenant": MaintenanceResult(
            property_id="valid_tenant",
            status="FAILED",
            assets_audited=1,
            assets_drifted=1,
            assets_refactored=0,
            assets_failed=1,
            failed_records=[{"status": "ROLLBACK_CI_FAILED", "error": "ROLLBACK_CI_FAILED on ci.yml"}],
        )
    }
    sup2 = AutonomousLifecycleSupervisor(
        workspace_root=ws,
        registry=reg,
        coordinator=mock_coord2,
        state_file=ws / ".agy" / "engine_hash2.json",
        ledger_file=ws / ".agy" / "asset_ledger2.json",
        heartbeat_path=ws / ".agy" / "supervisor_heartbeat2.json",
    )
    with patch("pseofactory.supervisor.detect_engine_drift", return_value={"current_hash": "hash_aaa", "drift_detected": True}):
        sup2.run_cycle(force=True, dry_run=False, property_ids=["valid_tenant"])
        assert mock_coord2.run_fleet.call_count == 1

        # Second cycle with SAME engine_hash must skip valid_tenant (CIRCUIT_BREAKER_OPEN)
        res_open = sup2.run_cycle(force=True, dry_run=False, property_ids=["valid_tenant"])
        assert mock_coord2.run_fleet.call_count == 1
        assert res_open["properties"]["valid_tenant"]["status"] == "CIRCUIT_BREAKER_OPEN"

    # Once engine_hash changes, circuit-breaker clears automatically and retries
    with patch("pseofactory.supervisor.detect_engine_drift", return_value={"current_hash": "hash_bbb", "drift_detected": True}):
        mock_coord2.run_fleet.return_value = {
            "valid_tenant": MaintenanceResult(
                property_id="valid_tenant",
                status="SUCCESS",
                assets_audited=1,
                assets_drifted=0,
                assets_refactored=0,
                assets_failed=0,
                failed_records=[],
            )
        }
        sup2.run_cycle(force=True, dry_run=False, property_ids=["valid_tenant"])
        assert mock_coord2.run_fleet.call_count == 2

    # 4. /tmp/ DLQ guard rejects temp asset paths and auto-prunes stale /tmp/ entries on live DLQ
    live_style_dlq = tmp_path / "dlq_sim" / "maintenance_dlq.json"
    live_style_dlq.parent.mkdir(parents=True, exist_ok=True)
    live_style_dlq.write_text(
        json.dumps(
            [
                {"property_id": "prexvo", "asset_path": "/tmp/pytest-of-user/stale.html", "slug": "stale"},
                {"property_id": "prexvo", "asset_path": "/home/ubuntuadmin/projects/prexvo/dist/tools/a/index.html", "slug": "a"},
            ]
        ),
        encoding="utf-8",
    )
    engine = RefactorCascadeEngine(dlq_path=live_style_dlq)
    with patch.object(engine, "_is_live_dlq_path", return_value=True):
        # Attempt to route a /tmp/ asset -> must be rejected AND stale /tmp/ entry pruned
        engine.route_to_dlq(
            "prexvo",
            AssetDriftRecord(
                asset_path=f"{tempfile.gettempdir()}/ephemeral_test_page.html",
                slug="ephemeral",
                reasons=[DriftReason.STRUCTURAL_CONTRACT_VIOLATION],
                details="test",
            ),
            "boom",
        )
        remaining = engine.list_dlq()
        assert len(remaining) == 1
        assert remaining[0]["slug"] == "a"
        assert all("/tmp/" not in str(e.get("asset_path", "")) for e in remaining)
